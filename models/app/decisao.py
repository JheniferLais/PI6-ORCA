"""
Junta o resultado das duas IAs (texto e imagem) numa decisão única e diz se a
página vira log.

Cada IA devolve {"modality", "category", "score", "model_version"}.

1. RISCO de cada IA (0 a 1):
     categoria perigosa (odio, NSFW...) -> risco = score
     categoria segura   (seguro, SFW)   -> risco = 1 - score  (certeza de seguro = risco baixo)
     sem score (ex.: texto pequeno)     -> a IA fica de fora da conta
2. SCORE FINAL = média ponderada dos riscos pelos PESOS.
     ex.: imagem NSFW 0.92 e texto odio 0.60, pesos 0.5/0.5 -> 0.5*0.92 + 0.5*0.60 = 0.76
3. A IA de MAIOR risco é a que prevalece: a categoria dela vira a causa (reason) do log.
     no ex.: imagem 0.92 > texto 0.60 -> causa "Conteúdo sexual"
4. NÍVEL pelo score final:
     >= LIMIAR_BLOQUEIO -> "bloqueio"   (no ex.: 0.76 -> bloqueio)
     >= LIMIAR_ALERTA   -> "alerta"
     abaixo, ou se a IA que prevaleceu disse "seguro" -> não gera log
"""
from typing import Optional

# quanto cada IA conta na média (não precisam somar 1)
PESOS = {"text": 0.5, "img": 0.5}  # chaves = "modality" de cada IA

LIMIAR_BLOQUEIO = 0.75
LIMIAR_ALERTA = 0.50

CATEGORIAS_SEGURAS = {"seguro", "SFW"}

# nomes que o site mostra (docs/categorias.md, orca-site/lib/logs.ts)
NOME_CATEGORIA = {
    "suicidio": "Automutilação/Suicídio",
    "odio": "Discurso de ódio/Discriminação",
    "NSFW": "Conteúdo sexual",
    "NSFL": "Conteúdo violento/chocante",  # não está em docs/categorias.md
}


def risco(resultado: dict) -> Optional[float]:
    """Risco de 0 a 1 de um resultado de IA, ou None se a IA não classificou."""
    if resultado is None or resultado.get("score") is None:
        return None
    if resultado["category"] in CATEGORIAS_SEGURAS:
        return 1 - resultado["score"]
    return resultado["score"]


def combinar(*resultados: dict) -> dict:
    """Combina os resultados das IAs (em qualquer quantidade) numa decisão.

    Devolve {"score", "level", "reason", "prevaleceu", "riscos"}; level e
    reason são None quando a página não deve virar log."""
    avaliados = [(r, risco(r)) for r in resultados]
    avaliados = [(r, x) for r, x in avaliados if x is not None]
    riscos = {r["modality"]: round(x, 4) for r, x in avaliados}

    if not avaliados:
        return {"score": None, "level": None, "reason": None, "prevaleceu": None, "riscos": riscos}

    soma_pesos = sum(PESOS.get(r["modality"], 1.0) for r, _ in avaliados)
    score = sum(PESOS.get(r["modality"], 1.0) * x for r, x in avaliados) / soma_pesos

    principal, _ = max(avaliados, key=lambda par: par[1])

    if principal["category"] in CATEGORIAS_SEGURAS or score < LIMIAR_ALERTA:
        level = None
    elif score >= LIMIAR_BLOQUEIO:
        level = "bloqueio"
    else:
        level = "alerta"

    return {
        "score": round(score, 4),
        "level": level,
        "reason": NOME_CATEGORIA.get(principal["category"], principal["category"]) if level else None,
        "prevaleceu": principal,
        "riscos": riscos,
    }
