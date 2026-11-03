"""
Filtro barato das imagens: decide, sem rede e sem modelo, o que não vale classificar.

Cada função devolve o MOTIVO da rejeição (texto curto, que a API devolve em
"reason") ou None quando a imagem pode seguir para o modelo.
"""
from typing import Optional
from urllib.parse import urlparse

LADO_MINIMO = 100         # px; a extensão já filtra, aqui é a segunda camada
AREA_MINIMA = 10_000      # px²
PROPORCAO_MAXIMA = 8.0    # banners/divisórias (ex.: 1600x100) não vão pro modelo


def rejeitar_por_tamanho(largura: int, altura: int) -> Optional[str]:
    """Pequena demais ou com proporção de banner. Também usada pelo pipeline de dados."""
    if min(largura, altura) < LADO_MINIMO or largura * altura < AREA_MINIMA:
        return "pequena_demais"
    if max(largura, altura) / max(1, min(largura, altura)) > PROPORCAO_MAXIMA:
        return "proporcao_extrema"
    return None


def motivo_rejeicao(src: str, largura: int, altura: int) -> Optional[str]:
    """Motivo para não classificar a imagem de endereço 'src', ou None se vale classificar."""
    if src.startswith("data:"):
        if not src.startswith("data:image/"):
            return "data_uri_nao_e_imagem"
        if src.startswith("data:image/svg"):
            return "svg"
    else:
        analisada = urlparse(src)
        if analisada.scheme not in ("http", "https"):
            return "esquema_nao_suportado"  # blob:, file:, etc. — o servidor não alcança
        if analisada.path.lower().endswith(".svg"):
            return "svg"                    # vetor/ícone; o PIL nem abre
    return rejeitar_por_tamanho(largura, altura)
