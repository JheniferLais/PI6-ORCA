"""
Normalização de texto do classificador de NLP (versão norm-v1).

Função pura, sem dependências externas, usada de forma idêntica no treino
(treino.py) e na inferência (inferencia.py).
Qualquer mudança de regra deve incrementar VERSAO, porque um modelo só é
coerente com a normalização com que foi treinado.

Regras:
  1. Unicode em forma NFC (acentos compostos).
  2. Remove links (http://, https:// e www.).
  3. Remove o marcador "@user" do TuPyE (anonimização das menções; sem
     isso o modelo pode aprender a fonte em vez do conteúdo). Outras
     menções não existem no dataset e não são alteradas.
  4. Colapsa qualquer sequência de espaços/quebras de linha em um espaço e
     remove espaços nas pontas.

A caixa (maiúsculas/minúsculas) é preservada de propósito: o BERTimbau Base
(bert-base-portuguese-cased) é um modelo "cased".
"""
import re
import unicodedata

VERSAO = "norm-v1"

REGRAS = [
    "Unicode NFC",
    "remove links (http://, https://, www.)",
    "remove o marcador @user (sem diferenciar maiúsculas)",
    "colapsa espaços e quebras de linha; remove espaços nas pontas",
    "preserva maiúsculas/minúsculas (modelo cased)",
]

_LINK = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_ARROBA_USER = re.compile(r"@user\b", re.IGNORECASE)
_ESPACOS = re.compile(r"\s+")


def normalizar(texto) -> str:
    """Normaliza um texto. None vira string vazia."""
    if texto is None:
        return ""
    t = unicodedata.normalize("NFC", str(texto))
    t = _LINK.sub(" ", t)
    t = _ARROBA_USER.sub(" ", t)
    return _ESPACOS.sub(" ", t).strip()


def chave_comparacao(texto) -> str:
    """Chave usada para detectar textos repetidos entre divisões (texto
    normalizado, sem diferenciar maiúsculas). Só para comparação; o modelo
    recebe normalizar(texto), com a caixa original."""
    return normalizar(texto).casefold()
