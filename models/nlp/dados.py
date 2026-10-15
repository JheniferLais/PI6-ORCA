"""
Dados do S2-03: leitura e validação dos CSVs de S2-02, tratamento de colisões
entre divisões após a normalização e cálculo dos pesos de classe.

Não depende de torch/transformers: tudo aqui roda só com pandas, numpy e
scikit-learn, e é coberto por test_nlp.py.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from normalizacao import chave_comparacao

PASTA_NLP = Path(__file__).resolve().parent


def _classes_do_pipeline():
    """Lê CLASSES de data/pipeline.py (S2-02), fonte única da ordem dos rótulos:
    índice 0 = seguro, 1 = suicidio, 2 = odio."""
    spec = importlib.util.spec_from_file_location(
        "orca_pipeline_s2_02", PASTA_NLP / "data" / "pipeline.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return list(modulo.CLASSES)


CLASSES = _classes_do_pipeline()

POLITICA_COLISOES = [
    "chave de comparação = texto normalizado (norm-v1) sem diferenciar maiúsculas",
    "os arquivos CSV nunca são alterados; as remoções ocorrem só em memória",
    "teste: nunca é alterado e só é lido para detectar colisões (texto e rótulo "
    "apenas para contar divergências; não entra em treino nem em seleção de modelo)",
    "validação: perde as linhas cujo texto colide com o teste",
    "treino: perde as linhas cujo texto colide com a validação ou com o teste, "
    "e as que ficam vazias após a normalização",
    "duplicados dentro de uma mesma divisão são apenas contados, não removidos",
    "toda linha removida é listada (divisão, índice, classe, motivo) em colisoes_removidas.csv",
]


# ---------------------------------------------------------------- leitura

def sha256_arquivo(caminho):
    """SHA-256 do arquivo. 'sha256_lf' ignora diferença CRLF/LF (Windows x Linux)."""
    dados = Path(caminho).read_bytes()
    return {
        "sha256": hashlib.sha256(dados).hexdigest(),
        "sha256_lf": hashlib.sha256(dados.replace(b"\r\n", b"\n")).hexdigest(),
        "bytes": len(dados),
    }


def carregar_split(caminho):
    """Lê um CSV de S2-02 e valida colunas e one-hot. Ignora a coluna 'origem'
    (não é rótulo nem entrada do modelo). Devolve text, as colunas de classe,
    'y' (índice da classe) e 'indice' (posição da linha de dados no CSV)."""
    df = pd.read_csv(caminho, keep_default_na=False)
    faltando = [c for c in ["text", *CLASSES] if c not in df.columns]
    if faltando:
        raise ValueError(f"{Path(caminho).name}: faltam as colunas {faltando} "
                         f"(encontradas: {list(df.columns)})")
    if not df["text"].map(lambda x: isinstance(x, str)).all():
        raise ValueError(f"{Path(caminho).name}: a coluna 'text' tem valores que não são texto")
    onehot = df[CLASSES]
    if not onehot.isin([0, 1]).all().all():
        raise ValueError(f"{Path(caminho).name}: colunas de classe com valores fora de 0/1")
    if not (onehot.sum(axis=1) == 1).all():
        raise ValueError(f"{Path(caminho).name}: cada linha deve ter exatamente uma classe")
    saida = df[["text", *CLASSES]].copy()
    saida["y"] = onehot.to_numpy().argmax(axis=1)
    saida["indice"] = np.arange(len(saida))
    return saida.reset_index(drop=True)


# ---------------------------------------------------------------- colisões

def _contagem_por_classe(y):
    cont = np.bincount(np.asarray(y, dtype=int), minlength=len(CLASSES))
    return {c: int(n) for c, n in zip(CLASSES, cont)}


def tratar_colisoes(treino, validacao, teste):
    """Detecta e trata textos repetidos entre treino, validação e teste depois
    da normalização (ver POLITICA_COLISOES). Devolve (treino_efetivo,
    validacao_efetiva, relatorio, removidos). O teste não é alterado."""
    k_tr = treino["text"].map(chave_comparacao)
    k_va = validacao["text"].map(chave_comparacao)
    k_te = teste["text"].map(chave_comparacao)
    nao_vazio = lambda k: k != ""

    set_va, set_te = set(k_va[nao_vazio(k_va)]), set(k_te[nao_vazio(k_te)])

    # Validação: remove o que colide com o teste.
    rem_va = k_va.isin(set_te) & nao_vazio(k_va)
    motivo_va = np.where(rem_va, "colide_com_teste", "")

    # Treino: remove vazios e o que colide com validação (original) ou teste.
    vazio_tr = ~nao_vazio(k_tr)
    c_va = k_tr.isin(set_va) & nao_vazio(k_tr)
    c_te = k_tr.isin(set_te) & nao_vazio(k_tr)
    rem_tr = vazio_tr | c_va | c_te
    motivo_tr = np.select(
        [vazio_tr, c_va & c_te, c_va, c_te],
        ["vazio_apos_normalizacao", "colide_com_validacao_e_teste",
         "colide_com_validacao", "colide_com_teste"],
        default="")

    removidos = pd.concat([
        pd.DataFrame({"divisao": "treino", "indice": treino.loc[rem_tr, "indice"],
                      "classe": treino.loc[rem_tr, "y"].map(dict(enumerate(CLASSES))),
                      "motivo": motivo_tr[rem_tr.to_numpy()]}),
        pd.DataFrame({"divisao": "validacao", "indice": validacao.loc[rem_va, "indice"],
                      "classe": validacao.loc[rem_va, "y"].map(dict(enumerate(CLASSES))),
                      "motivo": motivo_va[rem_va.to_numpy()]}),
    ], ignore_index=True)

    # Chaves presentes em mais de uma divisão e quantas têm rótulos divergentes.
    todos = pd.concat([
        pd.DataFrame({"chave": k, "divisao": nome, "y": d["y"]})
        for nome, k, d in (("treino", k_tr, treino), ("validacao", k_va, validacao),
                           ("teste", k_te, teste))
    ])
    todos = todos[nao_vazio(todos["chave"])]
    por_chave = todos.groupby("chave").agg(n_div=("divisao", "nunique"), n_rot=("y", "nunique"))
    multi = por_chave[por_chave["n_div"] > 1]

    def interno(k):
        k = k[nao_vazio(k)]
        return int(len(k) - k.nunique())

    def resumo(rem_mask, motivos, y):
        return {
            "total": int(rem_mask.sum()),
            "por_motivo": {str(m): int((motivos[rem_mask.to_numpy()] == m).sum())
                           for m in sorted(set(motivos[rem_mask.to_numpy()]))},
            "por_classe": _contagem_por_classe(y[rem_mask]),
        }

    tr_ef = treino[~rem_tr].reset_index(drop=True)
    va_ef = validacao[~rem_va].reset_index(drop=True)
    relatorio = {
        "chave": "texto normalizado (norm-v1), sem diferenciar maiúsculas",
        "politica": POLITICA_COLISOES,
        "chaves_em_mais_de_uma_divisao": int(len(multi)),
        "chaves_com_rotulo_divergente": int((multi["n_rot"] > 1).sum()),
        "vazios_apos_normalizacao": {
            "treino": int(vazio_tr.sum()),
            "validacao": int((~nao_vazio(k_va)).sum()),
            "teste": int((~nao_vazio(k_te)).sum()),
        },
        "duplicados_internos_apos_normalizacao": {
            "treino": interno(k_tr), "validacao": interno(k_va), "teste": interno(k_te)},
        "removidos": {
            "treino": resumo(rem_tr, motivo_tr, treino["y"]),
            "validacao": resumo(rem_va, motivo_va, validacao["y"]),
            "teste": {"total": 0, "por_motivo": {}, "por_classe": {c: 0 for c in CLASSES}},
        },
        "linhas_originais": {"treino": len(treino), "validacao": len(validacao), "teste": len(teste)},
        "linhas_efetivas": {"treino": len(tr_ef), "validacao": len(va_ef), "teste": len(teste)},
        "classes_originais": {"treino": _contagem_por_classe(treino["y"]),
                              "validacao": _contagem_por_classe(validacao["y"]),
                              "teste": _contagem_por_classe(teste["y"])},
        "classes_efetivas": {"treino": _contagem_por_classe(tr_ef["y"]),
                             "validacao": _contagem_por_classe(va_ef["y"]),
                             "teste": _contagem_por_classe(teste["y"])},
    }
    return tr_ef, va_ef, relatorio, removidos


# ---------------------------------------------------------------- pesos

METODOS_PESO = ("inversa_frequencia", "nenhum")


def calcular_pesos(y, metodo="inversa_frequencia"):
    """Pesos de classe calculados a partir dos rótulos do treino efetivo.

    inversa_frequencia: w_c = N / (K * n_c), com N = total de exemplos,
    K = número de classes e n_c = exemplos da classe c. Uma classe com
    frequência 1/K recebe peso 1. 'nenhum' usa peso 1 para todas as classes.
    O peso não garante melhor desempenho: o efeito em precisão e recall de
    cada classe só é conhecido depois do treino e da avaliação.
    """
    if metodo not in METODOS_PESO:
        raise ValueError(f"método de peso desconhecido: {metodo!r} (use {METODOS_PESO})")
    cont = np.bincount(np.asarray(y, dtype=int), minlength=len(CLASSES))
    if (cont == 0).any():
        raise ValueError(f"alguma classe não tem exemplos no treino: {dict(zip(CLASSES, cont))}")
    n, k = int(cont.sum()), len(CLASSES)
    pesos = np.ones(k) if metodo == "nenhum" else n / (k * cont)
    return {
        "metodo": metodo,
        "formula": "N / (K * n_c)" if metodo == "inversa_frequencia" else "1",
        "N": n,
        "K": k,
        "contagens": {c: int(x) for c, x in zip(CLASSES, cont)},
        "pesos": {c: float(p) for c, p in zip(CLASSES, pesos)},
    }


# ---------------------------------------------------------------- conjunto

def amostra_estratificada(df, n, seed):
    """Subconjunto estratificado por classe (usado só no teste rápido)."""
    if n >= len(df):
        return df.reset_index(drop=True)
    amostra, _ = train_test_split(df, train_size=n, stratify=df["y"], random_state=seed)
    return amostra.sort_values("indice").reset_index(drop=True)


def preparar_dados(pasta_datasets):
    """Carrega treino, validação e teste, registra hashes e trata colisões."""
    pasta = Path(pasta_datasets)
    arquivos, splits = {}, {}
    for nome in ("treino", "validacao", "teste"):
        caminho = pasta / f"{nome}.csv"
        if not caminho.exists():
            raise FileNotFoundError(
                f"{caminho} não existe. Gere os datasets com: python data/pipeline.py")
        splits[nome] = carregar_split(caminho)
        arquivos[caminho.name] = {**sha256_arquivo(caminho), "linhas": len(splits[nome])}
    completo = pasta / "dataset_multiclasse.csv"
    if completo.exists():
        arquivos[completo.name] = sha256_arquivo(completo)
    tr, va, relatorio, removidos = tratar_colisoes(
        splits["treino"], splits["validacao"], splits["teste"])
    return {"treino": tr, "validacao": va, "arquivos": arquivos,
            "colisoes": relatorio, "removidos": removidos}
