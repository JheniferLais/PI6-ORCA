"""Obtenção e decodificação dos bytes de uma imagem (data: URI ou http/https)."""
import base64
import io
from typing import Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import unquote_to_bytes
from urllib.request import Request, urlopen

from PIL import Image

TIMEOUT_S = 5
MAX_BYTES = 10 * 1024 * 1024
LADO_RASCUNHO = 448          # JPEG grande é decodificado já reduzido (bem mais rápido)
USER_AGENT = "Mozilla/5.0"

Image.MAX_IMAGE_PIXELS = 50_000_000  # proteção contra "decompression bomb"


def obter_bytes(src: str, referer: str = "") -> bytes:
    """Bytes da imagem. data: URI é decodificado direto, sem rede."""
    if src.startswith("data:"):
        cabecalho, _, conteudo = src.partition(",")
        dados = base64.b64decode(conteudo) if ";base64" in cabecalho else unquote_to_bytes(conteudo)
    else:
        cabecalhos = {"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.5"}
        if referer:
            cabecalhos["Referer"] = referer[:2000]  # alguns CDNs bloqueiam hotlink sem isso
        with urlopen(Request(src, headers=cabecalhos), timeout=TIMEOUT_S) as resposta:
            dados = resposta.read(MAX_BYTES + 1)
    if len(dados) > MAX_BYTES:
        raise ValueError("arquivo_grande_demais")
    return dados


def baixar(src: str, referer: str = "") -> Tuple[Optional[bytes], Optional[str]]:
    """(bytes, None) se deu certo; (None, motivo_do_erro) se não."""
    try:
        return obter_bytes(src, referer), None
    except HTTPError as erro:
        return None, f"download_falhou:http_{erro.code}"
    except Exception as erro:
        return None, f"download_falhou:{type(erro).__name__}"


def abrir_imagem(dados: bytes) -> Image.Image:
    """Decodifica para RGB; transparência vira fundo branco (e não preto)."""
    imagem = Image.open(io.BytesIO(dados))
    imagem.draft("RGB", (LADO_RASCUNHO, LADO_RASCUNHO))  # só afeta JPEG; ignora o resto
    if imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info):
        rgba = imagem.convert("RGBA")
        fundo = Image.new("RGB", rgba.size, (255, 255, 255))
        fundo.paste(rgba, mask=rgba.split()[-1])
        return fundo
    return imagem.convert("RGB")
