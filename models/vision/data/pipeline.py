"""
ORCA — pipeline de imagens: recebe o POST da extensão, filtra as imagens e
classifica cada uma como SFW / NSFW / NSFL com o image-safety-classifier-s.

Só imagens: o campo "text" que a extensão manda é ignorado.

Como rodar (porta que a extensão espera: localhost:8000):
    pip install fastapi uvicorn pillow timm torch
    python pipeline.py
    # ou: uvicorn pipeline:app --port 8000

Fluxo de cada POST /content (do mais barato pro mais caro, pra gastar o mínimo
de tempo de modelo):
    1. descarta o que não vale classificar (svg, esquema estranho, muito pequena,
       proporção de banner)                                  -> sem rede, sem modelo
    2. agrupa URLs repetidas (o mesmo ícone 8x na página vira 1)
    3. cache por URL: a extensão reenvia a página a cada mudança no DOM, então
       o que já foi classificado volta na hora
    4. limita as imagens novas às MAX_IMAGES_PER_PAGE maiores
    5. baixa em paralelo (data: URI é decodificado direto, sem rede)
    6. cache por conteúdo (hash dos bytes): URL diferente, mesma imagem -> 1 só
    7. UMA chamada do modelo em lote com tudo que sobrou

Imagem que não deu pra baixar/abrir volta com status "error", NUNCA como SFW:
quem decide o que fazer com isso é a camada de política, mais pra frente.
"""
import base64
import hashlib
import io
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import unquote_to_bytes, urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI
from PIL import Image
from pydantic import BaseModel

# ---------- Configuração (ajuste aqui e reinicie o servidor) ----------

HOST, PORT = "127.0.0.1", 8000

MODEL_ID = "hf-hub:OwenElliott/image-safety-classifier-s"

MIN_SIDE = 100              # lado mínimo (px); a extensão já filtra, aqui é segunda camada
MIN_AREA = 10_000
MAX_ASPECT_RATIO = 8.0      # banners/divisórias (ex.: 1600x100) não vão pro modelo
MAX_IMAGES_PER_PAGE = 15    # máximo de imagens NOVAS (fora do cache) por requisição

DOWNLOAD_TIMEOUT_S = 5
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
DOWNLOAD_WORKERS = 8
BATCH_SIZE = 8              # imagens por chamada do modelo
DRAFT_SIZE = 448            # JPEG grande é decodificado já reduzido (bem mais rápido)
CACHE_SIZE = 2000
ERROR_RETRY_S = 60          # URL que falhou não é tentada de novo por este tempo
USER_AGENT = "Mozilla/5.0"

Image.MAX_IMAGE_PIXELS = 50_000_000  # proteção contra "decompression bomb"


# ---------- Modelo ----------

class Classifier:
    """Carrega o modelo UMA vez (no startup) e classifica em lote."""

    def __init__(self, model_id: str = MODEL_ID):
        import timm
        import torch

        self.torch = torch
        self.model = timm.create_model(model_id, pretrained=True).eval()
        config = timm.data.resolve_model_data_config(self.model)
        self.transform = timm.data.create_transform(**config, is_training=False)
        self.labels: List[str] = list(self.model.pretrained_cfg["label_names"])
        self.lock = threading.Lock()  # 1 inferência por vez, mesmo com POSTs simultâneos
        self.predict([self.preprocess(Image.new("RGB", (224, 224)))])  # aquecimento

    def preprocess(self, img: Image.Image):
        return self.transform(img)

    def predict(self, tensors: list) -> List[List[float]]:
        out: List[List[float]] = []
        with self.lock, self.torch.inference_mode():
            for i in range(0, len(tensors), BATCH_SIZE):
                batch = self.torch.stack(tensors[i:i + BATCH_SIZE])
                out.extend(self.model(batch).softmax(dim=-1).cpu().tolist())
        return out


CLASSIFIER: Optional[Classifier] = None


# ---------- Cache (LRU simples) ----------

class LRU:
    def __init__(self, size: int):
        self.size = size
        self.data: "OrderedDict[str, dict]" = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[dict]:
        with self.lock:
            value = self.data.get(key)
            if value is not None:
                self.data.move_to_end(key)
            return value

    def set(self, key: str, value: dict) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)


URL_CACHE = LRU(CACHE_SIZE)      # sha1(url)   -> resultado
CONTENT_CACHE = LRU(CACHE_SIZE)  # sha1(bytes) -> resultado
ERROR_CACHE = LRU(CACHE_SIZE)    # sha1(url)   -> falha recente (evita re-tentar a cada repost)
EXECUTOR = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS)


# ---------- Filtro (sem rede, sem modelo) ----------

@dataclass
class Candidate:
    key: str                      # sha1 da URL
    src: str
    width: int
    height: int
    indices: List[int] = field(default_factory=list)  # posições dessa URL no POST


def _sha1(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def reject_reason(src: str, width: int, height: int) -> Optional[str]:
    if src.startswith("data:"):
        if not src.startswith("data:image/"):
            return "data_uri_nao_e_imagem"
        if src.startswith("data:image/svg"):
            return "svg"
    else:
        parsed = urlparse(src)
        if parsed.scheme not in ("http", "https"):
            return "esquema_nao_suportado"  # blob:, file:, etc. — o servidor não alcança
        if parsed.path.lower().endswith(".svg"):
            return "svg"                    # vetor/ícone; o PIL nem abre

    if min(width, height) < MIN_SIDE or width * height < MIN_AREA:
        return "pequena_demais"
    if max(width, height) / max(1, min(width, height)) > MAX_ASPECT_RATIO:
        return "proporcao_extrema"
    return None


def select_images(images: List["ImageIn"], skipped: Dict[int, str]) -> List[Candidate]:
    """Remove o que não vale classificar e agrupa URLs repetidas."""
    by_key: Dict[str, Candidate] = {}
    for i, img in enumerate(images):
        reason = reject_reason(img.src, img.width, img.height)
        if reason:
            skipped[i] = reason
            continue
        key = _sha1(img.src)
        if key in by_key:
            by_key[key].indices.append(i)
        else:
            by_key[key] = Candidate(key, img.src, img.width, img.height, [i])
    return list(by_key.values())


# ---------- Download / decodificação ----------

def fetch_bytes(src: str, referer: str) -> bytes:
    if src.startswith("data:"):
        header, _, payload = src.partition(",")
        data = base64.b64decode(payload) if ";base64" in header else unquote_to_bytes(payload)
    else:
        headers = {"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.5"}
        if referer:
            headers["Referer"] = referer[:2000]  # alguns CDNs bloqueiam hotlink sem isso
        with urlopen(Request(src, headers=headers), timeout=DOWNLOAD_TIMEOUT_S) as resp:
            data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("arquivo_grande_demais")
    return data


def fetch(cand: Candidate, referer: str):
    try:
        return cand, fetch_bytes(cand.src, referer), None
    except HTTPError as e:
        return cand, None, f"download_falhou:http_{e.code}"
    except Exception as e:
        return cand, None, f"download_falhou:{type(e).__name__}"


def decode_image(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.draft("RGB", (DRAFT_SIZE, DRAFT_SIZE))  # só afeta JPEG; ignora o resto
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")              # fundo branco em vez de preto nas transparências
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def to_result(labels: List[str], probs: List[float]) -> dict:
    best = max(range(len(probs)), key=probs.__getitem__)
    return {
        "status": "classified",
        "label": labels[best],
        "scores": {name: round(p, 4) for name, p in zip(labels, probs)},
    }


def _short(src: str) -> str:
    return src if len(src) <= 100 else src[:100] + "…"


# ---------- Pipeline ----------

def process(content: "ContentIn") -> dict:
    t0 = time.perf_counter()
    classifier = CLASSIFIER
    images = content.images
    skipped: Dict[int, str] = {}
    outcome: Dict[str, dict] = {}   # sha1(url) -> resultado
    cache_hits = downloaded = 0

    cands = select_images(images, skipped)

    # cache por URL
    misses: List[Candidate] = []
    for c in cands:
        hit = URL_CACHE.get(c.key)
        if hit:
            outcome[c.key] = {**hit, "cached": True}
            cache_hits += 1
        else:
            err = ERROR_CACHE.get(c.key)
            if err and time.monotonic() - err["t"] < ERROR_RETRY_S:
                outcome[c.key] = {"status": "error", "reason": err["reason"], "cached": True}
            else:
                misses.append(c)

    # limite de imagens novas: as maiores primeiro
    misses.sort(key=lambda c: c.width * c.height, reverse=True)
    for c in misses[MAX_IMAGES_PER_PAGE:]:
        outcome[c.key] = {"status": "skipped", "reason": "limite_por_pagina"}
    misses = misses[:MAX_IMAGES_PER_PAGE]

    # download em paralelo + cache por conteúdo + decodificação
    pending: Dict[str, List[Candidate]] = {}  # sha1(bytes) -> URLs com esse conteúdo
    order: List[str] = []
    tensors: list = []
    fetched = list(EXECUTOR.map(lambda c: fetch(c, content.url), misses)) if misses else []
    for c, data, err in fetched:
        if err:
            outcome[c.key] = {"status": "error", "reason": err}
            continue
        downloaded += 1
        ck = _sha1(data)
        hit = CONTENT_CACHE.get(ck)
        if hit:
            URL_CACHE.set(c.key, hit)
            outcome[c.key] = {**hit, "cached": True}
            cache_hits += 1
        elif ck in pending:
            pending[ck].append(c)
        else:
            try:
                tensors.append(classifier.preprocess(decode_image(data)))
            except Exception:
                outcome[c.key] = {"status": "error", "reason": "imagem_invalida"}
                continue
            pending[ck] = [c]
            order.append(ck)

    # uma chamada do modelo, em lote, com tudo que sobrou
    if tensors:
        try:
            probs = classifier.predict(tensors)
        except Exception as e:
            for ck in order:
                for c in pending[ck]:
                    outcome[c.key] = {"status": "error", "reason": f"falha_no_modelo:{type(e).__name__}"}
        else:
            for ck, p in zip(order, probs):
                result = to_result(classifier.labels, p)
                CONTENT_CACHE.set(ck, result)
                for c in pending[ck]:
                    URL_CACHE.set(c.key, result)
                    outcome[c.key] = {**result, "cached": False}

    # lembra as falhas por um tempo (menos erro do modelo, que não é culpa da imagem)
    for c in misses:
        o = outcome.get(c.key)
        if o and o["status"] == "error" and not o["reason"].startswith("falha_no_modelo"):
            ERROR_CACHE.set(c.key, {"reason": o["reason"], "t": time.monotonic()})

    # monta a resposta, uma entrada por imagem recebida, na ordem original
    by_index: Dict[int, dict] = {}
    for c in cands:
        base = outcome.get(c.key, {"status": "error", "reason": "sem_resultado"})
        for j, idx in enumerate(c.indices):
            entry = {"index": idx, "src": _short(c.src), **base}
            if j:
                entry["duplicate_of"] = c.indices[0]
            by_index[idx] = entry
    for idx, reason in skipped.items():
        by_index[idx] = {"index": idx, "src": _short(images[idx].src), "status": "skipped", "reason": reason}

    results = [by_index[i] for i in sorted(by_index)]
    count = lambda s: sum(1 for r in results if r["status"] == s)
    return {
        "ok": True,
        "url": content.url,
        "summary": {
            "received": len(images),
            "classified": count("classified"),
            "skipped": count("skipped"),
            "errors": count("error"),
            "cache_hits": cache_hits,
            "downloaded": downloaded,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000),
        },
        "images": results,
    }


# ---------- Servidor / rota ----------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    global CLASSIFIER
    if CLASSIFIER is None:
        CLASSIFIER = Classifier()  # baixa/carrega o modelo uma vez só
    yield


app = FastAPI(lifespan=lifespan)


class ImageIn(BaseModel):
    src: str
    alt: Optional[str] = None
    width: int
    height: int


class ContentIn(BaseModel):
    url: str
    title: str = ""
    timestamp: str = ""
    images: List[ImageIn]
    # "text" fica de fora de propósito: o pydantic ignora campos extras


@app.post("/content")
def receive(content: ContentIn):
    response = process(content)
    s = response["summary"]
    print(
        f"[ORCA] {content.url[:80]} | recebidas: {s['received']} | classificadas: {s['classified']} "
        f"(cache: {s['cache_hits']}) | puladas: {s['skipped']} | erros: {s['errors']} | {s['elapsed_ms']} ms"
    )
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)