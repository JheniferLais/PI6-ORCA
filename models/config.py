from typing import List, Optional
from pydantic import BaseModel

CATEGORIA_NAO_DEFINIDA="indefinido"

# CONFIG DE NLP
MODALIDADE_NLP="text"
MODELO_NLP_VERSION="nlp-v1"
MIN_PALAVRAS=10

class TextoClassificacaoRequest(BaseModel):
    url: str
    timestamp: str
    text: str = ""

 # TODO: trocar pelo modelo de verdade KAKSKSKASKKSA
def classificar_texto(texto):
    return "seguro", 0.5 # SÓ EXEMPLO :(


# CONFIG DE VISION
MODALIDADE_VISION="image"
MODELO_VISION_VERSION="vision-v1"
