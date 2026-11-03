"""
Avaliação offline do classificador de imagens, sem servidor.

Roda o modelo em uma divisão do dataset de vision/data (por padrão, a de teste) e
mede o quanto ele acerta: matriz de confusão, precisão/recall/F1 por classe e,
porque o ORCA é controle parental, as métricas "seguro x inseguro" (NSFW ou NSFL
contra SFW).

O modelo é pré-treinado e NÃO é treinado aqui, então não há risco de "vazar" o
teste para o treino. Mesmo assim, as imagens do dataset vêm de fontes diferentes
das que o autor do modelo usou (ele tem um conjunto próprio), e a classe NSFL é
pequena: leia os números por classe, não só a acurácia.
"""
import csv
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from vision.classificador import CLASSES, MODELO_ID, MODELO_VERSAO, Pontuacoes
from vision.download import abrir_imagem

PASTA_DATASETS = Path(__file__).resolve().parent / "data" / "datasets"
DIVISOES = ("treino", "validacao", "teste")
LOTE = 16
INSEGURAS = ("NSFW", "NSFL")


# ---------------------------------------------------------------- leitura

def ler_divisao(pasta: Path, divisao: str) -> List[dict]:
    """Linhas do CSV da divisão (arquivo, rotulo, origem, sha1, largura, altura)."""
    caminho = Path(pasta) / f"{divisao}.csv"
    if not caminho.exists():
        raise FileNotFoundError(f"{caminho} não existe: rode 'python -m vision dados' antes")
    with open(caminho, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    invalidos = sorted({l["rotulo"] for l in linhas} - set(CLASSES))
    if invalidos:
        raise ValueError(f"{caminho.name} tem rótulos desconhecidos: {invalidos}")
    return linhas


def amostra_estratificada(linhas: Sequence[dict], limite: int, seed: int = 42) -> List[dict]:
    """No máximo 'limite' linhas, mantendo a proporção de cada classe (e pelo menos 1 de cada)."""
    por_classe: Dict[str, List[dict]] = {c: [] for c in CLASSES}
    for linha in linhas:
        por_classe[linha["rotulo"]].append(linha)
    total = len(linhas)
    if total <= limite:
        return list(linhas)
    escolhidas: List[dict] = []
    for classe in CLASSES:
        grupo = por_classe[classe]
        if not grupo:
            continue
        n = max(1, round(limite * len(grupo) / total))
        escolhidas += random.Random(f"{seed}-{classe}").sample(grupo, min(n, len(grupo)))
    return escolhidas


# ---------------------------------------------------------------- métricas

def _divisao(a: float, b: float) -> Optional[float]:
    return a / b if b else None


def resumo_avaliacao(reais: Sequence[str], previstos: Sequence[str],
                     pontuacoes: Optional[Sequence[Pontuacoes]] = None) -> dict:
    """Métricas a partir dos rótulos reais e previstos (nomes de classe).

    Matriz de confusão: linhas = classe real, colunas = classe prevista, na ordem de CLASSES.
    Classe sem nenhuma imagem real (ex.: NSFL quando faltam exemplos): recall e F1 ficam
    None e ela não entra no macro F1, que é a média do F1 das classes COM exemplos.
    'inseguro' junta NSFW e NSFL: recall = quantas imagens inseguras o modelo pegou;
    taxa de falso alarme = quantas SFW ele marcou como inseguras."""
    indice = {c: i for i, c in enumerate(CLASSES)}
    k = len(CLASSES)
    matriz = [[0] * k for _ in range(k)]
    for real, previsto in zip(reais, previstos):
        matriz[indice[real]][indice[previsto]] += 1

    por_classe: Dict[str, dict] = {}
    for classe, i in indice.items():
        acertos = matriz[i][i]
        n_reais = sum(matriz[i])
        n_previstas = sum(matriz[j][i] for j in range(k))
        precisao = _divisao(acertos, n_previstas)
        recall = _divisao(acertos, n_reais)
        if n_reais == 0:
            f1, precisao = None, (0.0 if n_previstas else None)
        else:
            p, r = precisao or 0.0, recall or 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
        por_classe[classe] = {"precisao": precisao, "recall": recall, "f1": f1,
                              "reais": n_reais, "previstas": n_previstas}

    total = len(reais)
    f1s = [m["f1"] for m in por_classe.values() if m["f1"] is not None]
    inseguras_reais = [(r, p) for r, p in zip(reais, previstos) if r in INSEGURAS]
    sfw_reais = [(r, p) for r, p in zip(reais, previstos) if r == "SFW"]
    pegas = sum(1 for _, p in inseguras_reais if p != "SFW")
    marcadas = sum(1 for p in previstos if p != "SFW")
    marcadas_certo = sum(1 for r, p in zip(reais, previstos) if r != "SFW" and p != "SFW")

    resultado = {
        "classes": list(CLASSES),
        "imagens": total,
        "matriz_confusao": matriz,
        "por_classe": por_classe,
        "acuracia": _divisao(sum(matriz[i][i] for i in range(k)), total),
        "macro_f1": sum(f1s) / len(f1s) if f1s else None,
        "seguro_x_inseguro": {
            "recall_inseguro": _divisao(pegas, len(inseguras_reais)),
            "precisao_inseguro": _divisao(marcadas_certo, marcadas),
            "taxa_falso_alarme": _divisao(sum(1 for _, p in sfw_reais if p != "SFW"), len(sfw_reais)),
            "inseguras_reais": len(inseguras_reais),
            "inseguras_pegas": pegas,
            "sfw_reais": len(sfw_reais),
        },
    }
    if pontuacoes is not None:
        medias: Dict[str, Optional[float]] = {}
        for classe in CLASSES:
            valores = [p.como_dict()[classe] for r, p in zip(reais, pontuacoes) if r == classe]
            medias[classe] = sum(valores) / len(valores) if valores else None
        resultado["probabilidade_media_na_classe_real"] = medias
    return resultado


def _fmt(valor: Optional[float]) -> str:
    return "   -  " if valor is None else f"{valor:.4f}"


def formatar_avaliacao(r: dict) -> str:
    larg = max(len(c) for c in CLASSES) + 2
    linhas = ["Matriz de confusão (linhas = real, colunas = previsto):",
              " " * larg + "".join(f"{c:>{larg}}" for c in CLASSES)]
    for classe, linha in zip(CLASSES, r["matriz_confusao"]):
        linhas.append(f"{classe:<{larg}}" + "".join(f"{n:>{larg}}" for n in linha))
    linhas.append("Por classe (precisão / recall / F1):")
    for classe in CLASSES:
        m = r["por_classe"][classe]
        sufixo = "   (sem imagens reais desta classe)" if m["reais"] == 0 else ""
        linhas.append(f"  {classe:<{larg}}{_fmt(m['precisao'])} / {_fmt(m['recall'])} / {_fmt(m['f1'])}"
                      f"   (reais={m['reais']}, previstas={m['previstas']}){sufixo}")
    s = r["seguro_x_inseguro"]
    linhas.append(f"Seguro x inseguro: recall = {_fmt(s['recall_inseguro'])} "
                  f"({s['inseguras_pegas']}/{s['inseguras_reais']} inseguras pegas), "
                  f"precisão = {_fmt(s['precisao_inseguro'])}, "
                  f"falso alarme em SFW = {_fmt(s['taxa_falso_alarme'])}")
    linhas.append(f"macro F1 = {_fmt(r['macro_f1'])} | acurácia = {_fmt(r['acuracia'])}")
    return "\n".join(linhas)


# ---------------------------------------------------------------- avaliação

def avaliar(divisao: str = "teste", pasta: Optional[Path] = None, limite: Optional[int] = None,
            seed: int = 42, classificador=None) -> dict:
    """Classifica a divisão e resume. Grava <pasta>/avaliacao-<divisao>.json, exceto com 'limite'
    (que serve só para uma conferência rápida). 'classificador' é opcional (os testes passam um falso)."""
    if divisao not in DIVISOES:
        raise ValueError(f"divisão deve ser uma de {DIVISOES}")
    pasta = Path(pasta or PASTA_DATASETS)
    linhas = ler_divisao(pasta, divisao)
    if limite:
        linhas = amostra_estratificada(linhas, limite, seed)
    if not linhas:
        raise ValueError(f"a divisão {divisao} está vazia")
    if classificador is None:
        from vision.classificador import Classificador
        classificador = Classificador()

    reais: List[str] = []
    previstos: List[str] = []
    pontuacoes: List[Pontuacoes] = []
    ilegiveis = 0
    for i in range(0, len(linhas), LOTE):
        lote, tensores = [], []
        for linha in linhas[i:i + LOTE]:
            try:
                tensores.append(classificador.preparar(abrir_imagem((pasta / "imagens" / linha["arquivo"]).read_bytes())))
                lote.append(linha)
            except Exception:
                ilegiveis += 1
        for linha, pontuacao in zip(lote, classificador.pontuar(tensores) if tensores else []):
            reais.append(linha["rotulo"])
            previstos.append(pontuacao.categoria)
            pontuacoes.append(pontuacao)
        if (i // LOTE) % 25 == 24:
            print(f"  {min(i + LOTE, len(linhas))}/{len(linhas)} imagens...")

    resultado = {"modelo": MODELO_ID, "versao": MODELO_VERSAO, "divisao": divisao,
                 "ilegiveis": ilegiveis, **resumo_avaliacao(reais, previstos, pontuacoes)}
    print(f"Modelo {MODELO_VERSAO} em {len(reais)} imagens de {divisao}"
          + (f" ({ilegiveis} ilegíveis ignoradas)" if ilegiveis else "") + ":")
    print(formatar_avaliacao(resultado))
    if not limite:
        destino = pasta / f"avaliacao-{divisao}.json"
        destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Resultado gravado em {destino}")
    return resultado
