"""
Junta o resultado das duas IAs (texto e imagem) numa decisão única e diz se a
página vira log.

Cada IA devolve {"modality", "category", "score", "model_version"}.

1. RISCO de cada IA (0 a 1):
     categoria perigosa (odio, NSFW...) -> risco = score
     categoria segura   (seguro, SFW)   -> risco = 1 - score  (certeza de seguro = risco baixo)
     sem score (ex.: texto pequeno)     -> a IA fica de fora
2. ACUSAÇÕES: as IAs com categoria perigosa e risco >= LIMIAR_ALERTA.
     nenhuma -> não gera log.
3. SCORE FINAL = o MAIOR risco entre as acusações (não a média: uma IA dizendo
   "seguro" não pode anular a outra; o texto de uma página de gore costuma ser normal).
4. NÍVEL pelo score final: >= LIMIAR_BLOQUEIO -> "bloqueio", senão "alerta".
5. CAUSA (reason): a acusação de maior PRIORIDADE da modalidade; empate, a de maior risco.
     A imagem tem prioridade porque só ela conhece "Conteúdo sexual" e "violento":
     o modelo de texto só tem seguro/suicidio/odio, e numa página sexual ele chuta
     "odio". Assim, se a imagem acusou algo, a causa é a dela.

ex.: imagem NSFW 0.90 e texto odio 0.95 -> score 0.95, bloqueio, causa "Conteúdo sexual"
ex.: imagem NSFL 0.90 e texto seguro 0.95 -> score 0.90, bloqueio, causa "Conteúdo violento/chocante"
"""
from typing import Optional

LIMIAR_BLOQUEIO = 0.75
LIMIAR_ALERTA = 0.50

# quem define a causa quando mais de uma IA acusa (chaves = "modality" de cada IA)
PRIORIDADE = {"img": 1, "text": 0}

CATEGORIAS_SEGURAS = {"seguro", "SFW"}

# nomes que o site mostra (docs/categorias.md, orca-site/lib/logs.ts)
NOME_CATEGORIA = {
    "suicidio": "Automutilação/Suicídio",
    "odio": "Discurso de ódio/Discriminação",
    "NSFW": "Conteúdo sexual",
    "NSFL": "Conteúdo violento/chocante",  # não está em docs/categorias.md
}


NIVEL = {"alerta": 1, "bloqueio": 2}
# causa (como gravada no log) -> modalidade que a gerou
MODALIDADE_DA_CAUSA = {NOME_CATEGORIA["NSFW"]: "img", NOME_CATEGORIA["NSFL"]: "img"}


def _peso_do_log(level: str, reason: str) -> tuple:
    return (NIVEL.get(level, 0), PRIORIDADE.get(MODALIDADE_DA_CAUSA.get(reason, "text"), 0))


def substitui_log(novo_level: str, novo_reason: str, antigo: dict) -> bool:
    """A decisão nova deve substituir o log já gravado da mesma URL?

    Sim se for mais grave (alerta -> bloqueio) ou, no mesmo nível, se a causa vier
    de uma IA de maior PRIORIDADE (ex.: a página carregou as imagens depois e a
    causa "ódio" chutada pelo texto vira "Conteúdo sexual")."""
    return _peso_do_log(novo_level, novo_reason) > _peso_do_log(antigo["level"], antigo["reason"])


def log_no_maximo(log: dict) -> bool:
    """Nenhuma análise nova consegue substituir este log (bloqueio com a causa de maior prioridade)?"""
    return _peso_do_log(log["level"], log["reason"]) >= (max(NIVEL.values()), max(PRIORIDADE.values()))


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

    acusacoes = [(r, x) for r, x in avaliados
                 if r["category"] not in CATEGORIAS_SEGURAS and x >= LIMIAR_ALERTA]
    if not acusacoes:
        score = max(riscos.values()) if riscos else None
        return {"score": score, "level": None, "reason": None, "prevaleceu": None, "riscos": riscos}

    score = max(x for _, x in acusacoes)
    principal, _ = max(acusacoes, key=lambda par: (PRIORIDADE.get(par[0]["modality"], 0), par[1]))

    return {
        "score": round(score, 4),
        "level": "bloqueio" if score >= LIMIAR_BLOQUEIO else "alerta",
        "reason": NOME_CATEGORIA.get(principal["category"], principal["category"]),
        "prevaleceu": principal,
        "riscos": riscos,
    }
