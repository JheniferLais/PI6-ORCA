"""
POST /analyze: analisa uma página com as duas IAs, combina (app/decisao.py) e,
se for o caso, grava o log do usuário logado com a causa e a URL.
"""
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.decisao import combinar
from app.routes.logs import salvar_log
from app.schemas import LogCreate
from nlp.nlp_router import TextoClassificacaoRequest, classificar_texto
from vision.simulado import classificar_imagens_simulado  # trocar pela IA real quando entrar

router = APIRouter(tags=["analise"])


@router.post("/analyze")
def analyze(req: TextoClassificacaoRequest, user=Depends(get_current_user)):
    texto = classificar_texto(req.text)
    imagem = classificar_imagens_simulado(req.url) # TODO: substituir pelo real
    decisao = combinar(texto, imagem)

    log = None
    if decisao["level"]:
        log = salvar_log(
            LogCreate(url=req.url, level=decisao["level"], reason=decisao["reason"]),
            user["id_user"],
        )

    return {
        "url": req.url,
        "text": texto,
        "image": imagem,
        "decision": decisao,
        "log": log,
    }
