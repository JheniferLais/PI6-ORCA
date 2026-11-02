from pathlib import Path
from typing import Optional

from pydantic import BaseModel

PASTA_MODELS = Path(__file__).resolve().parent

CATEGORIA_NAO_DEFINIDA = "indefinido"

# CONFIG DE NLP
MODALIDADE_NLP = "text"
MODELO_NLP_PASTA = PASTA_MODELS / "nlp" / "artifacts" / "nlp-v1"
MIN_PALAVRAS = 10
MODELO_NLP_VERSION = "nlp-v1"
TEXTO_PEQUENO=f"Texto pequeno demais, pelo menos {MIN_PALAVRAS} palavras"

class TextoClassificacaoRequest(BaseModel):
    url: str
    timestamp: str
    text: str = ""

class ClassificacaoResponse(BaseModel):
    modality: str
    category: str
    score: Optional[float]
    model_version: str


# CONFIG DE VISION
MODALIDADE_VISION="image"
MODELO_VISION_VERSION="vision-v1"
