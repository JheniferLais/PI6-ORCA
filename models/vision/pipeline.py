"""
ORCA — pipeline de imagens (servidor): recebe o POST da extensão, filtra as imagens
e devolve, para cada uma, as pontuações de SFW, NSFW e NSFL (3 floats de 0 a 1).

Só imagens: o campo "text" que a extensão manda é ignorado.

Como rodar (a partir de models/, porta que a extensão espera: localhost:8000):
    pip install -r vision/requirements.txt
    python -m vision                     # ou: python vision/pipeline.py

Fluxo de cada POST /content (do mais barato pro mais caro, pra gastar o mínimo
de tempo de modelo):
    1. descarta o que não vale classificar (svg, esquema estranho, muito pequena,
       proporção de banner)                                  -> sem rede, sem modelo
    2. agrupa URLs repetidas (o mesmo ícone 8x na página vira 1)
    3. cache por URL: a extensão reenvia a página a cada mudança no DOM, então
       o que já foi classificado volta na hora
    4. limita as imagens novas às MAX_IMAGENS_POR_PAGINA maiores
    5. baixa em paralelo (data: URI é decodificado direto, sem rede)
    6. cache por conteúdo (hash dos bytes): URL diferente, mesma imagem -> 1 só
    7. UMA chamada do modelo em lote com tudo que sobrou

Imagem que não deu pra baixar/abrir volta com status "error", NUNCA como SFW:
quem decide o que fazer com isso é a camada de política (app/decisao.py).

Resposta (uma entrada por imagem recebida, na ordem original):
    {"index": 0, "src": "...", "status": "classified", "label": "NSFW",
     "scores": {"SFW": 0.03, "NSFW": 0.95, "NSFL": 0.02}, "cached": false}
    status: "classified" | "skipped" | "error"   (skipped/error trazem "reason")
Mais "summary" (contagens e tempo) e "page" (resumo da página inteira, no formato
das outras IAs: {"modality", "category", "score", "model_version"}).
"""
import hashlib
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

if not __package__:
    # executado como arquivo (python vision/pipeline.py): torna o pacote importável
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from pydantic import BaseModel

from vision.cache import CacheLRU
from vision.classificador import (CLASSES, GRAVIDADE, MODALIDADE, MODELO_VERSAO,
                                  Classificador, Pontuacoes)
from vision.download import abrir_imagem, baixar
from vision.filtro import motivo_rejeicao

# ---------- Configuração (ajuste aqui e reinicie o servidor) ----------

HOST, PORTA = "127.0.0.1", 8000

MAX_IMAGENS_POR_PAGINA = 15   # máximo de imagens NOVAS (fora do cache) por requisição
TAMANHO_CACHE = 2000
TRABALHADORES_DOWNLOAD = 8
REPETIR_ERRO_APOS_S = 60      # URL que falhou não é tentada de novo por este tempo
CASAS_DECIMAIS = 4            # arredondamento dos scores na resposta


# ---------- Entrada (o que a extensão manda) ----------

class ImagemEntrada(BaseModel):
    src: str
    alt: Optional[str] = None
    width: int
    height: int


class ConteudoEntrada(BaseModel):
    url: str
    title: str = ""
    timestamp: str = ""
    images: List[ImagemEntrada]
    # "text" fica de fora de propósito: o pydantic ignora campos extras


# ---------- Pipeline ----------

@dataclass
class Candidata:
    chave: str                    # sha1 da URL
    src: str
    largura: int
    altura: int
    indices: List[int] = field(default_factory=list)  # posições dessa URL no POST


def _sha1(dados) -> str:
    if isinstance(dados, str):
        dados = dados.encode("utf-8")
    return hashlib.sha1(dados).hexdigest()


def _encurtar(src: str) -> str:
    return src if len(src) <= 100 else src[:100] + "…"


def resultado_da_pontuacao(pontuacoes: Pontuacoes) -> dict:
    """Pontuações -> entrada da resposta (e do cache)."""
    return {
        "status": "classified",
        "label": pontuacoes.categoria,
        "scores": {c: round(v, CASAS_DECIMAIS) for c, v in pontuacoes.como_dict().items()},
    }


def agrupar_candidatas(imagens: List[ImagemEntrada], puladas: Dict[int, str]) -> List[Candidata]:
    """Tira o que não vale classificar (motivo em 'puladas') e agrupa URLs repetidas."""
    por_chave: Dict[str, Candidata] = {}
    for i, imagem in enumerate(imagens):
        motivo = motivo_rejeicao(imagem.src, imagem.width, imagem.height)
        if motivo:
            puladas[i] = motivo
            continue
        chave = _sha1(imagem.src)
        if chave in por_chave:
            por_chave[chave].indices.append(i)
        else:
            por_chave[chave] = Candidata(chave, imagem.src, imagem.width, imagem.height, [i])
    return list(por_chave.values())


def resumir_pagina(resultados: List[dict]) -> dict:
    """Resume a página no formato das outras IAs, pronto para app/decisao.py.

    Vale a imagem mais grave: se alguma não é SFW, a página recebe a classe e a
    probabilidade da pior delas; se todas são SFW, recebe SFW com a probabilidade
    da imagem MENOS segura de si (mesma ideia do classificar_longo do NLP).
    Sem nenhuma imagem classificada, score é None e a IA fica de fora da decisão."""
    classificadas = [r for r in resultados if r["status"] == "classified"]
    base = {"modality": MODALIDADE, "model_version": MODELO_VERSAO}
    if not classificadas:
        return {**base, "category": "indefinido", "score": None}
    inseguras = [r for r in classificadas if r["label"] != "SFW"]
    if inseguras:
        pior = max(inseguras, key=lambda r: (r["scores"][r["label"]], GRAVIDADE[r["label"]]))
        return {**base, "category": pior["label"], "score": pior["scores"][pior["label"]]}
    return {**base, "category": "SFW", "score": min(r["scores"]["SFW"] for r in classificadas)}


class PipelineImagens:
    """Filtra, baixa, classifica e guarda em cache. Uma instância por servidor."""

    def __init__(self, classificador, tamanho_cache: int = TAMANHO_CACHE,
                 max_imagens_por_pagina: int = MAX_IMAGENS_POR_PAGINA,
                 trabalhadores: int = TRABALHADORES_DOWNLOAD):
        self.classificador = classificador            # qualquer objeto com preparar() e pontuar()
        self.max_imagens_por_pagina = max_imagens_por_pagina
        self.cache_url = CacheLRU(tamanho_cache)       # sha1(url)   -> resultado
        self.cache_conteudo = CacheLRU(tamanho_cache)  # sha1(bytes) -> resultado
        self.cache_erros = CacheLRU(tamanho_cache)     # sha1(url)   -> falha recente
        self._executor = ThreadPoolExecutor(max_workers=trabalhadores)

    def processar(self, conteudo: ConteudoEntrada) -> dict:
        inicio = time.perf_counter()
        imagens = conteudo.images
        puladas: Dict[int, str] = {}
        resultados: Dict[str, dict] = {}          # sha1(url) -> resultado
        contagem = {"acertos_cache": 0, "baixadas": 0}

        candidatas = agrupar_candidatas(imagens, puladas)
        novas = self._separar_cache(candidatas, resultados, contagem)
        novas = self._limitar_por_pagina(novas, resultados)
        self._baixar_e_classificar(novas, conteudo.url, resultados, contagem)
        self._lembrar_erros(novas, resultados)
        return self._montar_resposta(conteudo.url, imagens, candidatas, puladas,
                                     resultados, contagem, inicio)

    # --- etapas ---

    def _separar_cache(self, candidatas, resultados, contagem) -> List[Candidata]:
        """Preenche o que já está em cache e devolve só as candidatas realmente novas."""
        novas: List[Candidata] = []
        for cand in candidatas:
            acerto = self.cache_url.obter(cand.chave)
            if acerto:
                resultados[cand.chave] = {**acerto, "cached": True}
                contagem["acertos_cache"] += 1
                continue
            erro = self.cache_erros.obter(cand.chave)
            if erro and time.monotonic() - erro["t"] < REPETIR_ERRO_APOS_S:
                resultados[cand.chave] = {"status": "error", "reason": erro["reason"], "cached": True}
            else:
                novas.append(cand)
        return novas

    def _limitar_por_pagina(self, novas, resultados) -> List[Candidata]:
        """Mantém as MAIORES imagens novas; as demais são puladas."""
        novas = sorted(novas, key=lambda c: c.largura * c.altura, reverse=True)
        for cand in novas[self.max_imagens_por_pagina:]:
            resultados[cand.chave] = {"status": "skipped", "reason": "limite_por_pagina"}
        return novas[:self.max_imagens_por_pagina]

    def _baixar_e_classificar(self, novas, url_da_pagina, resultados, contagem) -> None:
        if not novas:
            return
        baixadas = list(self._executor.map(lambda c: (c, *baixar(c.src, url_da_pagina)), novas))

        aguardando: Dict[str, List[Candidata]] = {}   # sha1(bytes) -> URLs com esse conteúdo
        ordem: List[str] = []
        tensores: list = []
        for cand, dados, erro in baixadas:
            if erro:
                resultados[cand.chave] = {"status": "error", "reason": erro}
                continue
            contagem["baixadas"] += 1
            chave_conteudo = _sha1(dados)
            acerto = self.cache_conteudo.obter(chave_conteudo)
            if acerto:
                self.cache_url.guardar(cand.chave, acerto)
                resultados[cand.chave] = {**acerto, "cached": True}
                contagem["acertos_cache"] += 1
            elif chave_conteudo in aguardando:
                aguardando[chave_conteudo].append(cand)
            else:
                try:
                    tensores.append(self.classificador.preparar(abrir_imagem(dados)))
                except Exception:
                    resultados[cand.chave] = {"status": "error", "reason": "imagem_invalida"}
                    continue
                aguardando[chave_conteudo] = [cand]
                ordem.append(chave_conteudo)

        if not tensores:
            return
        try:
            pontuacoes = self.classificador.pontuar(tensores)        # UMA chamada, em lote
        except Exception as erro:
            for chave_conteudo in ordem:
                for cand in aguardando[chave_conteudo]:
                    resultados[cand.chave] = {"status": "error",
                                              "reason": f"falha_no_modelo:{type(erro).__name__}"}
            return
        for chave_conteudo, pontuacao in zip(ordem, pontuacoes):
            resultado = resultado_da_pontuacao(pontuacao)
            self.cache_conteudo.guardar(chave_conteudo, resultado)
            for cand in aguardando[chave_conteudo]:
                self.cache_url.guardar(cand.chave, resultado)
                resultados[cand.chave] = {**resultado, "cached": False}

    def _lembrar_erros(self, novas, resultados) -> None:
        """Guarda as falhas por um tempo (menos erro do modelo, que não é culpa da imagem)."""
        for cand in novas:
            resultado = resultados.get(cand.chave)
            if (resultado and resultado["status"] == "error"
                    and not resultado["reason"].startswith("falha_no_modelo")):
                self.cache_erros.guardar(cand.chave, {"reason": resultado["reason"], "t": time.monotonic()})

    @staticmethod
    def _montar_resposta(url, imagens, candidatas, puladas, resultados, contagem, inicio) -> dict:
        """Uma entrada por imagem recebida, na ordem original."""
        por_indice: Dict[int, dict] = {}
        for cand in candidatas:
            base = resultados.get(cand.chave, {"status": "error", "reason": "sem_resultado"})
            for posicao, indice in enumerate(cand.indices):
                entrada = {"index": indice, "src": _encurtar(cand.src), **base}
                if posicao:
                    entrada["duplicate_of"] = cand.indices[0]
                por_indice[indice] = entrada
        for indice, motivo in puladas.items():
            por_indice[indice] = {"index": indice, "src": _encurtar(imagens[indice].src),
                                  "status": "skipped", "reason": motivo}

        lista = [por_indice[i] for i in sorted(por_indice)]
        quantas = lambda status: sum(1 for r in lista if r["status"] == status)
        return {
            "ok": True,
            "url": url,
            "summary": {
                "received": len(imagens),
                "classified": quantas("classified"),
                "skipped": quantas("skipped"),
                "errors": quantas("error"),
                "cache_hits": contagem["acertos_cache"],
                "downloaded": contagem["baixadas"],
                "elapsed_ms": round((time.perf_counter() - inicio) * 1000),
            },
            "page": resumir_pagina(lista),
            "images": lista,
        }


# ---------- Servidor ----------

def registrar(url: str, resposta: dict) -> None:
    """Uma linha de resumo no terminal por página."""
    s = resposta["summary"]
    votos = Counter(i["label"] for i in resposta["images"] if i["status"] == "classified")
    maioria = max(votos, key=lambda k: (votos[k], GRAVIDADE[k])) if votos else "—"   # empate: o pior ganha
    print(
        f"[ORCA] {url[:80]} | recebidas: {s['received']} | classificadas: {s['classified']} "
        f"(cache: {s['cache_hits']}) | puladas: {s['skipped']} | erros: {s['errors']} | {s['elapsed_ms']} ms\n"
        f"       -> maioria: {maioria} | " + " | ".join(f"{c}: {votos.get(c, 0)}" for c in CLASSES)
    )


def criar_app(pipeline: Optional[PipelineImagens] = None) -> FastAPI:
    """Monta o app. Sem 'pipeline', o modelo é carregado na subida do servidor."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        if app.state.pipeline is None:
            app.state.pipeline = PipelineImagens(Classificador())   # baixa/carrega o modelo uma vez só
        yield

    app = FastAPI(title="ORCA — imagens", lifespan=ciclo_de_vida)
    app.state.pipeline = pipeline

    @app.post("/content")
    def receber(conteudo: ConteudoEntrada):
        resposta = app.state.pipeline.processar(conteudo)
        registrar(conteudo.url, resposta)
        return resposta

    return app


app = criar_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORTA)
