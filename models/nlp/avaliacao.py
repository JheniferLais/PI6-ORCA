"""
Métricas do classificador e avaliação de um modelo salvo.

A seleção do modelo usa o macro F1 na validação. O teste só deve ser usado
uma vez, na avaliação final do modelo escolhido: é o único número que não foi
influenciado por nenhuma decisão de treino.
"""
import json

import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from . import dados as dd

CLASSES = dd.CLASSES
LOTE = 32


def calcular_metricas(y_true, y_pred):
    """macro F1 (média simples do F1 das classes), acurácia e precisão/recall/F1 por classe."""
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(CLASSES))), zero_division=0)
    m = {"macro_f1": float(f.mean()), "accuracy": float(accuracy_score(y_true, y_pred))}
    for i, c in enumerate(CLASSES):
        m[f"precision_{c}"], m[f"recall_{c}"], m[f"f1_{c}"] = float(p[i]), float(r[i]), float(f[i])
    return m


def compute_metrics(eval_pred):
    """Adaptador para o Trainer do transformers."""
    logits, rotulos = eval_pred
    return calcular_metricas(np.asarray(rotulos), np.asarray(logits).argmax(axis=-1))


def softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def resumo_avaliacao(y_true, y_pred, probs=None):
    """Matriz de confusão (linhas = classe real, colunas = classe prevista),
    contagens por classe e métricas. 'probs' (n x K, opcional) acrescenta a
    probabilidade média atribuída à classe real.

    A matriz é necessária porque precisão/recall/F1 iguais a zero valem tanto
    para uma classe nunca prevista quanto para uma prevista só errada."""
    y_true, y_pred = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    k = len(CLASSES)
    matriz = np.zeros((k, k), dtype=int)
    np.add.at(matriz, (y_true, y_pred), 1)
    r = {"classes": CLASSES,
         "matriz_confusao": matriz.tolist(),
         "reais_por_classe": dict(zip(CLASSES, matriz.sum(axis=1).tolist())),
         "previstas_por_classe": dict(zip(CLASSES, matriz.sum(axis=0).tolist())),
         "metricas": calcular_metricas(y_true, y_pred)}
    if probs is not None:
        probs = np.asarray(probs, dtype=float)
        r["probabilidade_media_na_classe_real"] = {
            c: float(probs[y_true == i, i].mean()) if (y_true == i).any() else None
            for i, c in enumerate(CLASSES)}
    return r


def formatar_avaliacao(r):
    larg = max(len(c) for c in CLASSES) + 2
    linhas = ["Matriz de confusão (linhas = real, colunas = previsto):",
              " " * larg + "".join(f"{c:>{larg}}" for c in CLASSES)]
    for c, linha in zip(CLASSES, r["matriz_confusao"]):
        linhas.append(f"{c:<{larg}}" + "".join(f"{n:>{larg}}" for n in linha))
    m = r["metricas"]
    linhas.append("Por classe (precisão / recall / F1):")
    for c in CLASSES:
        linhas.append(f"  {c:<{larg}}{m['precision_' + c]:.4f} / {m['recall_' + c]:.4f} / {m['f1_' + c]:.4f}"
                      f"   (reais={r['reais_por_classe'][c]}, previstas={r['previstas_por_classe'][c]})")
    linhas.append(f"macro F1 = {m['macro_f1']:.4f} | acurácia = {m['accuracy']:.4f}")
    return "\n".join(linhas)


def avaliar_modelo(clf, textos, y):
    """Classifica os textos com um Classificador carregado e resume o resultado."""
    probs = []
    for i in range(0, len(textos), LOTE):
        lote = clf.classificar(textos[i:i + LOTE])
        probs.extend([[p["probabilidades"][c] for c in CLASSES] for p in lote])
        if (i // LOTE) % 50 == 49:
            print(f"  {i + len(lote)}/{len(textos)} textos...")
    probs = np.asarray(probs)
    return resumo_avaliacao(y, probs.argmax(axis=1), probs)


def avaliar(pasta_modelo, divisao="validacao", limite=None, seed=42):
    """Avalia o modelo salvo em 'pasta_modelo' na validação efetiva ou no teste
    e grava o resultado em <pasta_modelo>/avaliacao-<divisao>.json (exceto
    quando 'limite' pede só uma amostra, que serve apenas para conferência)."""
    from .inferencia import Classificador
    clf = Classificador(pasta_modelo)
    df = dd.preparar_dados()[divisao]
    if limite:
        df = dd.amostra_estratificada(df, limite, seed)
    r = avaliar_modelo(clf, df["text"].tolist(), df["y"].to_numpy())
    r = {"modelo": clf.model_version, "divisao": divisao, "textos": len(df), **r}
    print(f"Modelo {clf.model_version} em {len(df)} textos de {divisao}:")
    print(formatar_avaliacao(r))
    if not limite:
        destino = clf.pasta / f"avaliacao-{divisao}.json"
        destino.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Resultado gravado em {destino}")
    return r
