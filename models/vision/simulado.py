"""
IA de imagem SIMULADA, enquanto o vision/pipeline.py (porta 8000) não está no
servidor 8001. Devolve o mesmo formato da IA de texto (nlp_router.classificar_texto):

    {"modality": "image", "category": "NSFW", "score": 0.92, "model_version": "vision-v1-simulado"}

O resultado é sorteado a partir da URL, então a mesma página sempre recebe o
mesmo resultado (dá para repetir um teste). Quando a IA real entrar, troque o
import em app/routes/analise.py por uma função com essa mesma assinatura.
"""
import hashlib
import random

MODALIDADE_VISION = "img"
MODELO_VISION_VERSION = "vision-v1-simulado"
CLASSES = ["SFW", "NSFW", "NSFL"]          # as mesmas do image-safety-classifier-s
CHANCES = [0.70, 0.22, 0.08]               # a maioria das páginas é segura


def classificar_imagens_simulado(url: str) -> dict:
    semente = int(hashlib.sha256(url.encode("utf-8")).hexdigest(), 16)
    sorteio = random.Random(semente)
    categoria = sorteio.choices(CLASSES, weights=CHANCES)[0]
    return {
        "modality": MODALIDADE_VISION,
        "category": categoria,
        "score": round(sorteio.uniform(0.55, 0.99), 4),
        "model_version": MODELO_VISION_VERSION,
    }
