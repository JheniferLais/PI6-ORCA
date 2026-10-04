
import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

CLASSES = ["seguro", "suicidio", "odio"]
PASTA_DATASETS = Path(__file__).resolve().parent / "datasets"

URL_BOAMENTE = ("https://zenodo.org/records/18343886/files/"
                "Boamente_Atualizado_Janeiro_2026.csv?download=1")
URL_TUPYE = ("https://huggingface.co/datasets/Silly-Machine/TuPyE-Dataset/"
             "resolve/main/binary/tupye_binary_vote.csv")

"""
Fontes:
    Boamente: https://zenodo.org/records/18343886 (CC BY 4.0)
    TuPyE:    https://huggingface.co/datasets/Silly-Machine/TuPyE-Dataset (CC BY 4.0)
"""

# ---------------------------------------------------------------- download

def baixar(url, destino, forcar):
    """Baixa o arquivo, a menos que ele já exista."""
    destino = Path(destino)
    if destino.exists() and not forcar:
        print(f"{destino.name}: já existe, download pulado")
        return destino
    print(f"{destino.name}: baixando de {url}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (preparar_dataset.py)"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resposta, open(parcial, "wb") as f:
            shutil.copyfileobj(resposta, f)
    except Exception as erro:
        parcial.unlink(missing_ok=True)
        sys.exit(f"ERRO ao baixar {destino.name}: {erro}\n"
                 f"Baixe manualmente em {url}\ne salve como {destino.resolve()}")
    parcial.replace(destino)
    print(f"{destino.name}: salvo ({destino.stat().st_size / 1024:.0f} KB)")
    return destino


def ler_csv(caminho, colunas, linhas_esperadas):
    """Lê o CSV e confere se tem as colunas necessárias."""
    df = pd.read_csv(caminho)
    df.columns = [c.strip().lower() for c in df.columns]
    faltando = [c for c in colunas if c not in df.columns]
    if faltando:
        sys.exit(f"ERRO: {Path(caminho).name} não tem as colunas {faltando}. "
                 f"Colunas encontradas: {list(df.columns)}")
    aviso = "" if len(df) == linhas_esperadas else \
        f"  (AVISO: esperado {linhas_esperadas}; a fonte pode ter sido atualizada)"
    print(f"{Path(caminho).name}: {len(df)} linhas{aviso}")
    return df


# ---------------------------------------------------------------- rótulos

def carregar_boamente(caminho):
    """Boamente: label 1 -> suicidio, label 0 -> seguro."""
    df = ler_csv(caminho, ["text", "label"], 3777)
    return pd.DataFrame({
        "text": df["text"].str.strip(),
        "label": df["label"].map({0: "seguro", 1: "suicidio"}),
        "origem": "boamente",
    })


def carregar_tupye(caminho):
    """TuPyE: hate 1 -> odio; aggressive 0 e hate 0 -> seguro.

    Textos agressivos sem ódio (aggressive 1, hate 0) são descartados,
    porque não se encaixam bem em nenhuma das três classes.
    """
    df = ler_csv(caminho, ["text", "aggressive", "hate"], 43668)
    ambiguo = (df["aggressive"] == 1) & (df["hate"] == 0)
    print(f"TuPyE: {ambiguo.sum()} textos agressivos sem ódio descartados")
    df = df[~ambiguo]
    return pd.DataFrame({
        "text": df["text"].str.strip(),
        "label": df["hate"].map({0: "seguro", 1: "odio"}),
        "origem": "tupye",
    })


# ---------------------------------------------------------------- união

def unir_e_limpar(boamente, tupye, seed):
    df = pd.concat([boamente, tupye], ignore_index=True)

    # Chave de comparação: minúsculas e espaços normalizados
    df["chave"] = df["text"].str.lower().str.replace(r"\s+", " ", regex=True)
    df = df[df["chave"].str.len() > 0]

    # Remove textos que aparecem com rótulos diferentes
    n_rotulos = df.groupby("chave")["label"].nunique()
    conflitos = set(n_rotulos[n_rotulos > 1].index)
    em_conflito = df["chave"].isin(conflitos)
    print(f"Conflitos de rótulo: {len(conflitos)} textos ({em_conflito.sum()} linhas) removidos")
    df = df[~em_conflito]

    # Remove duplicados, mantendo a primeira ocorrência
    antes = len(df)
    df = df.drop_duplicates("chave")
    print(f"Duplicados removidos: {antes - len(df)}")

    # One-hot encoding
    for classe in CLASSES:
        df[classe] = (df["label"] == classe).astype(int)

    df = df[["text", *CLASSES, "origem"]]
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)


# ---------------------------------------------------------------- divisão

def dividir(df, seed):
    """70/15/15 estratificado por classe e por dataset de origem."""
    estrato = df[CLASSES].idxmax(axis=1) + "_" + df["origem"]
    treino, resto = train_test_split(
        df, test_size=0.30, random_state=seed, stratify=estrato)
    validacao, teste = train_test_split(
        resto, test_size=0.50, random_state=seed, stratify=estrato.loc[resto.index])
    return {"treino": treino, "validacao": validacao, "teste": teste}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--pasta", default=PASTA_DATASETS,
                   help='pasta onde ficam todos os CSVs; padrão: "datasets" ao lado do script')
    p.add_argument("--seed", type=int, default=42, help="semente aleatória")
    p.add_argument("--forcar", action="store_true",
                   help="baixa os dois CSVs de novo, mesmo que já existam")
    p.add_argument("--url-boamente", default=URL_BOAMENTE, help="endereço do CSV do Boamente")
    p.add_argument("--url-tupye", default=URL_TUPYE, help="endereço do CSV do TuPyE")
    args = p.parse_args()

    # 1. Download (pulado para arquivos que já existem)
    pasta = Path(args.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    boamente = baixar(args.url_boamente, pasta / "boamente.csv", args.forcar)
    tupye = baixar(args.url_tupye, pasta / "tupye_binary_vote.csv", args.forcar)

    # 2. Rótulos, união, limpeza e one-hot
    df = unir_e_limpar(carregar_boamente(boamente), carregar_tupye(tupye), args.seed)
    assert (df[CLASSES].sum(axis=1) == 1).all(), "cada linha deve ter exatamente uma classe"

    df.to_csv(pasta / "dataset_multiclasse.csv", index=False, encoding="utf-8")

    # 3. Divisão 70/15/15
    partes = dividir(df, args.seed)
    print(f"\n{'arquivo':<26}{'textos':>8}{'%':>7}" + "".join(f"{c:>10}" for c in CLASSES))
    for nome, parte in [("dataset_multiclasse", df), *partes.items()]:
        if nome != "dataset_multiclasse":
            parte.to_csv(pasta / f"{nome}.csv", index=False, encoding="utf-8")
        print(f"{nome + '.csv':<26}{len(parte):>8}{len(parte) / len(df) * 100:>7.1f}"
              + "".join(f"{parte[c].sum():>10}" for c in CLASSES))
    print(f"\nArquivos salvos em: {pasta.resolve()}")


if __name__ == "__main__":
    main()