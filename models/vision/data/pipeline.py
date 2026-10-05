"""
ORCA — Pipeline completo: recebe o conteúdo da extensão, limpa/normaliza
(pré-processamento) e expõe a rota do servidor local.

Contexto no backlog: a extensão captura texto/imagens da página (INF-002/003/004)
e envia para cá via POST /content. Antes desse conteúdo alimentar os futuros
classificadores de PLN (TXT-019) e Visão Computacional (IMG-021), ele passa por
esta limpeza — que só normaliza e filtra ruído, não faz nenhuma classificação
nem decisão de política (isso é o POL-00X, mais pra frente).

Mantido deliberadamente leve (sem dependências pesadas / download de modelo),
já que este agente roda na máquina do usuário (ver INF-007: consumo de CPU/memória).

Como rodar:
    uvicorn pipeline:app --reload --port 8765
"""
import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

try:
    from langdetect import DetectorFactory, LangDetectException, detect

    DetectorFactory.seed = 0  # torna a detecção determinística
except ImportError:  # langdetect é opcional — se faltar, só pulamos a detecção de idioma
    detect = None

    class LangDetectException(Exception):
        pass


# ---------- Configuração (ajuste aqui e reinicie o servidor) ----------

MIN_TEXT_LENGTH = 40           # textos menores que isso não valem a pena classificar
MAX_TEXT_LENGTH = 20_000       # trunca textos gigantes (limite de entrada do classificador)
BOILERPLATE_MAX_LINE_LEN = 40  # só considera "boilerplate" linhas curtas (menu, cookies, etc.)
BOILERPLATE_MIN_REPEATS = 3    # nº mínimo de repetições da mesma linha pra descartar
MAX_IMAGES_PER_PAGE = 15       # limite de imagens (já deduplicadas) enviadas pro classificador de visão


# ---------- Resultado da limpeza ----------

@dataclass
class CleanedText:
    text: str
    language: Optional[str]
    discarded: bool
    discard_reason: Optional[str] = None


@dataclass
class CleanedImage:
    src: str
    alt: Optional[str]
    width: int
    height: int
    content_hash: str


# ---------- Texto ----------

def _collapse_whitespace(text: str) -> str:
    """Mesma ideia do normalizeText() do TS — mantido aqui como segunda camada
    de segurança, já que este servidor pode um dia receber conteúdo de outras
    fontes além desta extensão."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _remove_repeated_short_lines(text: str) -> str:
    """Remove linhas curtas que se repetem muitas vezes no mesmo texto —
    tipicamente itens de menu, links de rodapé, avisos de cookie. Esse tipo
    de ruído sobrevive ao innerText porque ele é texto "de verdade" da página,
    só que não é o conteúdo que interessa classificar."""
    lines = text.split("\n")
    counts: Dict[str, int] = {}
    for line in lines:
        key = line.strip().lower()
        if key and len(key) <= BOILERPLATE_MAX_LINE_LEN:
            counts[key] = counts.get(key, 0) + 1

    boilerplate = {key for key, count in counts.items() if count >= BOILERPLATE_MIN_REPEATS}
    kept = [line for line in lines if line.strip().lower() not in boilerplate]
    return "\n".join(kept)


def _detect_language(text: str) -> Optional[str]:
    if detect is None or len(text) < 20:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def clean_text(raw_text: str) -> CleanedText:
    text = _collapse_whitespace(raw_text)
    text = _remove_repeated_short_lines(text)
    text = _collapse_whitespace(text)  # limpa linhas em branco deixadas pela remoção acima

    if len(text) < MIN_TEXT_LENGTH:
        return CleanedText(text=text, language=None, discarded=True, discard_reason="texto_curto_demais")

    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    return CleanedText(text=text, language=_detect_language(text), discarded=False)


# ---------- Imagens ----------

def clean_images(images: List[dict]) -> List[CleanedImage]:
    """Deduplica imagens repetidas (mesmo src, ex.: logo/ícones que aparecem
    em várias partes da página), mantendo a de maior resolução de cada grupo,
    e depois limita a quantidade total às MAX_IMAGES_PER_PAGE maiores — páginas
    com dezenas de imagens não devem mandar todas pro classificador de visão."""
    best_by_hash: Dict[str, CleanedImage] = {}

    for img in images:
        src = img["src"]
        content_hash = hashlib.sha1(src.encode("utf-8")).hexdigest()
        candidate = CleanedImage(
            src=src,
            alt=img.get("alt"),
            width=img["width"],
            height=img["height"],
            content_hash=content_hash,
        )
        current = best_by_hash.get(content_hash)
        if current is None or (candidate.width * candidate.height) > (current.width * current.height):
            best_by_hash[content_hash] = candidate

    deduplicated = list(best_by_hash.values())
    deduplicated.sort(key=lambda img: img.width * img.height, reverse=True)
    return deduplicated[:MAX_IMAGES_PER_PAGE]


# ---------- Servidor / rota ----------

app = FastAPI()


class Image(BaseModel):
    src: str
    alt: Optional[str] = None
    width: int
    height: int


class Content(BaseModel):
    url: str
    title: str
    timestamp: str
    text: str
    images: List[Image]


@app.post("/content")
def receive(content: Content):
    cleaned_text = clean_text(content.text)
    cleaned_images = clean_images([img.model_dump() for img in content.images])

    print(
        f"[ORCA] {content.url} | "
        f"texto: {len(content.text)} → {len(cleaned_text.text)} chars "
        f"(idioma: {cleaned_text.language}, descartado: {cleaned_text.discarded}) | "
        f"imagens: {len(content.images)} → {len(cleaned_images)} após deduplicação"
    )

    # ⬇ aqui entra a classificação (TXT-019 / IMG-021) + mecanismo de políticas (POL-00X):
    # usar cleaned_text.text (se not discarded) e cleaned_images como entrada dos modelos.
    return {
        "ok": True,
        "discarded": cleaned_text.discarded,
        "language": cleaned_text.language,
        "images_after_dedup": len(cleaned_images),
    }
