import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from nlp.inferencia import Classificador

# CONFIG DE NLP
MODELO_NLP_VERSION = "nlp-v1"
MODELO_NLP_PASTA = Path(__file__).resolve().parent / "artifacts" / MODELO_NLP_VERSION
MODALIDADE_NLP = "text"
MIN_PALAVRAS = 10
TEXTO_PEQUENO = f"Texto pequeno demais, pelo menos {MIN_PALAVRAS} palavras"


class TextoClassificacaoRequest(BaseModel):
    url: str
    timestamp: str
    text: str = ""

class ClassificacaoResponse(BaseModel):
    modality: str
    category: str
    score: Optional[float]
    model_version: str


clf = Classificador(MODELO_NLP_PASTA)


router = APIRouter(tags=["nlp"])


# a extensão reenvia a página a cada mudança no DOM: o mesmo texto não roda o modelo de novo
@lru_cache(maxsize=256)
def _classificar_com_cache(texto: str) -> tuple:
    # texto curto demais (ou vazio após normalizar) não é classificado
    resultado = clf.classificar_longo(texto) if len(texto.split()) >= MIN_PALAVRAS else None
    if resultado is None:
        return TEXTO_PEQUENO, None
    return resultado["category"], resultado["score"]


def classificar_texto(texto: str) -> dict:
    """Resultado da IA de texto no formato comum às duas IAs (usado também por /analyze)."""
    category, score = _classificar_com_cache(texto)
    return {
        "modality": MODALIDADE_NLP,
        "category": category,
        "score": score,
        "model_version": MODELO_NLP_VERSION,
    }


@router.post("/classify/text", response_model=ClassificacaoResponse)
def classify_text(req: TextoClassificacaoRequest):
    # recebe o mesmo JSON que a extensão manda ao vision (title e images são ignorados)
    t0 = time.perf_counter()
    acertos = _classificar_com_cache.cache_info().hits
    resposta = classificar_texto(req.text)
    cache = " (cache)" if _classificar_com_cache.cache_info().hits > acertos else ""
    score = "-" if resposta["score"] is None else f"{resposta['score']:.2f}"
    print(f"[ORCA texto] {req.url[:80]} | {len(req.text.split())} palavras | "
          f"{resposta['category']} {score}{cache} | {round((time.perf_counter() - t0) * 1000)} ms")
    return resposta
