"""
Classificador de imagens do ORCA: image-safety-classifier-s -> três pontuações.

Para cada imagem, devolve as probabilidades das três classes, sempre nesta ordem
e com estes nomes, independentemente da ordem interna do modelo:

    Pontuacoes(sfw=0.03, nsfw=0.95, nsfl=0.02)     # 3 floats em [0, 1], somam 1

O card do modelo mostra duas ordens diferentes de rótulos (NSFW/NSFL/SFW no texto,
NSFL/NSFW/SFW no exemplo ONNX), então o mapeamento é feito pelo NOME do rótulo
(pretrained_cfg["label_names"]), nunca pela posição.

Quem usa só precisa de dois métodos:
    preparar(imagem_pil)  -> tensor    (redimensiona e normaliza)
    pontuar(tensores)     -> [Pontuacoes, ...]   (uma chamada do modelo, em lote)
"""
import threading
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

MODELO_ID = "hf-hub:OwenElliott/image-safety-classifier-s"
MODELO_VERSAO = "vision-v1"
MODALIDADE = "img"                       # mesma chave usada em app/decisao.py

CLASSES: Tuple[str, ...] = ("SFW", "NSFW", "NSFL")
GRAVIDADE: Dict[str, int] = {"SFW": 0, "NSFW": 1, "NSFL": 2}   # desempate: a mais grave vence

LOTE = 8                                 # imagens por chamada do modelo
_TOLERANCIA = 1e-3                       # erro aceito na soma das probabilidades


@dataclass(frozen=True)
class Pontuacoes:
    """Probabilidade de cada classe para UMA imagem (3 floats de 0 a 1, somando 1)."""

    sfw: float
    nsfw: float
    nsfl: float

    def como_dict(self) -> Dict[str, float]:
        return {"SFW": self.sfw, "NSFW": self.nsfw, "NSFL": self.nsfl}

    def como_tupla(self) -> Tuple[float, float, float]:
        return (self.sfw, self.nsfw, self.nsfl)

    @property
    def categoria(self) -> str:
        """Classe mais provável; em empate, a mais grave (NSFL > NSFW > SFW)."""
        valores = self.como_dict()
        return max(CLASSES, key=lambda c: (valores[c], GRAVIDADE[c]))


def pontuacoes_a_partir_de(rotulos: Sequence[str], probabilidades: Sequence[float]) -> Pontuacoes:
    """Reordena as probabilidades do modelo para (SFW, NSFW, NSFL), pelo nome do rótulo.

    Levanta ValueError se os rótulos não forem exatamente SFW, NSFW e NSFL, ou se as
    probabilidades não forem válidas (fora de [0, 1] ou soma diferente de 1): é
    melhor falhar alto do que devolver números trocados em silêncio."""
    if len(rotulos) != len(probabilidades):
        raise ValueError(f"{len(rotulos)} rótulos para {len(probabilidades)} probabilidades")
    por_nome: Dict[str, float] = {}
    for rotulo, p in zip(rotulos, probabilidades):
        nome = str(rotulo).strip().upper()
        if nome in por_nome:
            raise ValueError(f"rótulo repetido: {nome}")
        por_nome[nome] = float(p)
    if set(por_nome) != set(CLASSES):
        raise ValueError(f"o modelo deve ter exatamente os rótulos {list(CLASSES)}; veio {list(rotulos)}")
    for nome, p in por_nome.items():
        if not -_TOLERANCIA <= p <= 1 + _TOLERANCIA:     # também barra NaN
            raise ValueError(f"probabilidade fora de [0, 1] em {nome}: {p}")
        por_nome[nome] = min(1.0, max(0.0, p))
    if abs(sum(por_nome.values()) - 1.0) > _TOLERANCIA:
        raise ValueError(f"as probabilidades não somam 1: {por_nome}")
    return Pontuacoes(sfw=por_nome["SFW"], nsfw=por_nome["NSFW"], nsfl=por_nome["NSFL"])


class Classificador:
    """Carrega o modelo UMA vez e classifica em lote. Seguro para várias threads."""

    def __init__(self, modelo_id: str = MODELO_ID):
        import timm     # importados aqui para o resto do pacote funcionar sem torch/timm
        import torch
        from PIL import Image

        self._torch = torch
        self._modelo = timm.create_model(modelo_id, pretrained=True).eval()
        configuracao = timm.data.resolve_model_data_config(self._modelo)
        self._transformacao = timm.data.create_transform(**configuracao, is_training=False)
        self._rotulos: List[str] = list(self._modelo.pretrained_cfg["label_names"])
        self._trava = threading.Lock()        # 1 inferência por vez, mesmo com POSTs simultâneos
        # aquecimento; também confere os rótulos do modelo logo na subida
        self.pontuar([self.preparar(Image.new("RGB", (224, 224)))])

    def preparar(self, imagem):
        """Imagem PIL (RGB) -> tensor pronto para o modelo."""
        return self._transformacao(imagem)

    def pontuar(self, tensores: list) -> List[Pontuacoes]:
        """Uma Pontuacoes por tensor, na mesma ordem."""
        saida: List[Pontuacoes] = []
        with self._trava, self._torch.inference_mode():
            for i in range(0, len(tensores), LOTE):
                lote = self._torch.stack(tensores[i:i + LOTE])
                probabilidades = self._modelo(lote).softmax(dim=-1).cpu().tolist()
                saida.extend(pontuacoes_a_partir_de(self._rotulos, p) for p in probabilidades)
        return saida

    def classificar(self, imagens: list) -> List[Pontuacoes]:
        """Atalho: imagens PIL -> Pontuacoes."""
        return self.pontuar([self.preparar(imagem) for imagem in imagens])
