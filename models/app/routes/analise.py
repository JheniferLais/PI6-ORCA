"""
POST /analyze: analisa uma página com as duas IAs, combina (app/decisao.py) e,
se for o caso, grava o log do usuário logado com a causa e a URL. Cada URL gera
no máximo 1 log por usuário: as análises seguintes da mesma URL devolvem o log
que já existe (log_ja_existia = true), e ele só é ATUALIZADO se a decisão nova for
mais grave ou tiver causa mais confiável (app/decisao.py: substitui_log).

Recebe o mesmo JSON que a extensão monta (url, title, timestamp, text, images[]).
A IA de imagem é a real (vision/pipeline.py): o modelo é carregado uma vez só,
na primeira análise (ou na subida do servidor, via carregar_ia_imagem()).
"""
import threading
from typing import List, Optional

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.decisao import combinar, log_no_maximo, substitui_log
from app.routes.logs import atualizar_log, buscar_log_da_url, salvar_log
from app.schemas import LogCreate
from nlp.nlp_router import TextoClassificacaoRequest, classificar_texto
from vision.pipeline import ConteudoEntrada, ImagemEntrada, PipelineImagens

router = APIRouter(tags=["analise"])

_URL = TypeAdapter(HttpUrl)


class AnaliseRequest(TextoClassificacaoRequest):
    title: str = ""
    images: List[ImagemEntrada] = []


_pipeline_imagens: Optional[PipelineImagens] = None
_trava = threading.Lock()


def carregar_ia_imagem() -> PipelineImagens:
    """Carrega o modelo de imagem uma vez só (baixa os pesos na primeira vez)."""
    global _pipeline_imagens
    if _pipeline_imagens is None:
        with _trava:
            if _pipeline_imagens is None:
                from vision.classificador import Classificador  # importa torch/timm
                _pipeline_imagens = PipelineImagens(Classificador())
    return _pipeline_imagens


def processar_imagens(req: AnaliseRequest) -> dict:
    """Resposta completa do pipeline de imagens (summary, page, images)."""
    conteudo = ConteudoEntrada(url=req.url, title=req.title, timestamp=req.timestamp, images=req.images)
    return carregar_ia_imagem().processar(conteudo)


def classificar_imagens(req: AnaliseRequest) -> dict:
    """Resultado da IA de imagem no formato comum às duas IAs (o "page" do pipeline)."""
    return processar_imagens(req)["page"]


def _fmt(resultado: dict) -> str:
    score = "-" if resultado["score"] is None else f"{resultado['score']:.2f}"
    return f"{resultado['category']} {score}"


def registrar(req: AnaliseRequest, texto: dict, resposta_imagens: dict, decisao: dict, acao: str) -> None:
    """Uma linha por análise no terminal: dá para ver por que a página virou log (ou não)."""
    s = resposta_imagens["summary"]
    erros = sorted({i["reason"] for i in resposta_imagens["images"] if i["status"] == "error"})
    resultado = (f"{decisao['level']} ({decisao['reason']}){' ' + acao if acao else ''}"
                 if decisao["level"] else "sem log")
    print(f"[ORCA analyze] {req.url[:80]}\n"
          f"    texto: {_fmt(texto)} | imagem: {_fmt(resposta_imagens['page'])} "
          f"(recebidas {s['received']}, classificadas {s['classified']}, puladas {s['skipped']}, "
          f"erros {s['errors']}{' ' + ', '.join(erros) if erros else ''}) -> {resultado}")


@router.post("/analyze")
def analyze(req: AnaliseRequest, user=Depends(get_current_user)):
    # a extensão reenvia a página a cada mudança: se o log dessa URL já está no
    # máximo, nenhuma análise nova mudaria nada, então nem roda os modelos
    try:
        url_normalizada = str(_URL.validate_python(req.url))  # a mesma forma que é gravada no log
    except ValidationError:
        url_normalizada = None
    existente = buscar_log_da_url(url_normalizada, user["id_user"]) if url_normalizada else None
    if existente and log_no_maximo(existente):
        print(f"[ORCA analyze] {req.url[:80]} -> já tem log {existente['level']} "
              f"({existente['reason']}), não analisa de novo")
        return {"url": req.url, "text": None, "image": None, "decision": None,
                "log": existente, "log_ja_existia": True, "final": True}

    texto = classificar_texto(req.text)
    resposta_imagens = processar_imagens(req)
    imagem = resposta_imagens["page"]
    decisao = combinar(texto, imagem)

    # no máximo 1 log por URL (por usuário): se a página já gerou log, ele só é
    # atualizado quando a decisão nova é mais grave ou tem causa mais confiável
    log, log_ja_existia, acao = None, False, ""
    if decisao["level"] and url_normalizada:  # URL inválida não vira log
        novo = LogCreate(url=req.url, level=decisao["level"], reason=decisao["reason"])
        log = existente  # buscado no início, com a mesma URL normalizada que é gravada
        log_ja_existia = log is not None
        if not log_ja_existia:
            log, acao = salvar_log(novo, user["id_user"]), "NOVO LOG"
        elif substitui_log(novo.level, novo.reason, log):
            antes = f"{log['level']} ({log['reason']})"
            log, acao = atualizar_log(log["id_log"], novo), f"LOG ATUALIZADO, era {antes}"

    registrar(req, texto, resposta_imagens, decisao, acao)
    return {
        "url": req.url,
        "text": texto,
        "image": imagem,
        "decision": decisao,
        "log": log,
        "log_ja_existia": log_ja_existia,
        # true = o log dessa URL não muda mais: a extensão pode parar de reenviar a página
        "final": bool(log) and log_no_maximo(log),
    }
