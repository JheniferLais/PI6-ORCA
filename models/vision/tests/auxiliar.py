"""Peças compartilhadas pelos testes: imagens sintéticas e um classificador falso (sem torch, sem rede)."""
import base64
import io
import random
from typing import List

from PIL import Image

from vision.classificador import Pontuacoes

VERMELHO = (220, 20, 20)   # o classificador falso diz NSFW
AZUL = (20, 20, 220)       # NSFL
VERDE = (20, 200, 20)      # SFW

PONTUACOES_FALSAS = {
    "NSFW": Pontuacoes(sfw=0.07, nsfw=0.90, nsfl=0.03),
    "NSFL": Pontuacoes(sfw=0.10, nsfw=0.10, nsfl=0.80),
    "SFW": Pontuacoes(sfw=0.95, nsfw=0.03, nsfl=0.02),
}


def imagem_png(cor=VERDE, tamanho=(128, 128), semente=0, formato="PNG") -> bytes:
    """Imagem de uma cor só, com uns pixels aleatórios (a 'semente' muda os bytes, mas não a cor dominante)."""
    imagem = Image.new("RGB", tamanho, cor)
    sorteio = random.Random(semente)
    for _ in range(8):
        x, y = sorteio.randrange(tamanho[0]), sorteio.randrange(tamanho[1])
        imagem.putpixel((x, y), tuple(min(255, c + sorteio.randrange(10)) for c in cor))
    saida = io.BytesIO()
    imagem.save(saida, format=formato)
    return saida.getvalue()


def data_uri(dados: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(dados).decode()}"


class ClassificadorFalso:
    """Classifica pela cor dominante: vermelho = NSFW, azul = NSFL, o resto = SFW. Conta as chamadas."""

    def __init__(self):
        self.chamadas = 0
        self.imagens_pontuadas = 0

    def preparar(self, imagem):
        return imagem.resize((1, 1)).getpixel((0, 0))     # (r, g, b) médio

    def pontuar(self, tensores: list) -> List[Pontuacoes]:
        self.chamadas += 1
        self.imagens_pontuadas += len(tensores)
        return [PONTUACOES_FALSAS[self._classe(rgb)] for rgb in tensores]

    @staticmethod
    def _classe(rgb) -> str:
        r, g, b = rgb
        if r > max(g, b) + 50:
            return "NSFW"
        if b > max(r, g) + 50:
            return "NSFL"
        return "SFW"


class ClassificadorQueFalha(ClassificadorFalso):
    def pontuar(self, tensores):
        self.chamadas += 1
        raise RuntimeError("modelo quebrou")
