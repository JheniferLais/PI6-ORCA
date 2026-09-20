"""Servidor mínimo do ORCA: só recebe o conteúdo enviado pela extensão."""
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

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
    print(f"[ORCA] {content.url} | texto: {len(content.text)} chars | imagens: {len(content.images)}")
    # ⬇ aqui entra a sua pipeline: content.text, content.images[i].src, ...
    return {"ok": True}
