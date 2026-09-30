"""Servidor do ORCA: recebe o conteúdo da extensão e aplica a limpeza (INF)
antes de repassar aos futuros classificadores de PLN/Visão (TXT-019 / IMG-021)."""

from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from cleaning import clean_images, clean_text

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