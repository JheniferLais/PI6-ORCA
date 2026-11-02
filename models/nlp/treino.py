"""
Fine-tuning do BERTimbau para classificar textos em seguro, suicidio e odio.

Um experimento = um arquivo em config/ (ex.: config/nlp-v1.json). O modelo,
o tokenizador e o registro do experimento (orca_model.json) são salvos em
artifacts/<versao>. O teste rápido usa uma amostra pequena, 1 época, e salva
em artifacts/<versao>-teste: serve para validar o fluxo e medir tempo, não é
resultado do modelo.
"""
import json
import math
import platform
import shutil
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np

from . import avaliacao as av
from . import dados as dd
from . import normalizacao as norm

PASTA_NLP = Path(__file__).resolve().parent
PASTA_ARTIFACTS = PASTA_NLP / "artifacts"
CONFIG_PADRAO = PASTA_NLP / "config" / "nlp-v1.json"
CLASSES = dd.CLASSES


def agora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def carregar_config(caminho=CONFIG_PADRAO, teste_rapido=False):
    config = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if config["normalizacao"] != norm.VERSAO:
        raise ValueError(f"a configuração pede a normalização {config['normalizacao']}, "
                         f"mas normalizacao.py está em {norm.VERSAO}")
    if teste_rapido:
        config["hiperparametros"]["num_train_epochs"] = config["teste_rapido"]["num_train_epochs"]
    return config


def preparar_destino(config, teste_rapido, forcar=False, base=PASTA_ARTIFACTS):
    """Pasta de saída do experimento. O treino oficial nunca sobrescreve um
    modelo: sem 'forcar' recusa; com 'forcar' renomeia a pasta antiga para
    <versao>.anterior-<data>. A pasta do teste rápido é sempre recriada."""
    destino = Path(base) / (config["versao"] + ("-teste" if teste_rapido else ""))
    if destino.exists() and any(destino.iterdir()):
        if teste_rapido:
            shutil.rmtree(destino)
        elif not forcar:
            raise FileExistsError(f"{destino} já existe; use --forcar para arquivá-la e treinar de novo")
        else:
            agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            arquivada = destino.rename(destino.with_name(f"{destino.name}.anterior-{agora}"))
            print(f"Versão anterior arquivada em {arquivada}")
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def versoes_bibliotecas():
    versoes = {"python": platform.python_version()}
    for nome in ["torch", "transformers", "accelerate", "tokenizers", "scikit-learn", "numpy", "pandas"]:
        try:
            versoes[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versoes[nome] = None
    return versoes


# ---------------------------------------------------------------- peças do treino

def criar_trainer_ponderado(torch, Trainer):
    class TrainerPonderado(Trainer):
        """Trainer com entropia cruzada ponderada por classe (compensa o desbalanceamento)."""

        def __init__(self, *args, pesos_classe=None, **kwargs):
            super().__init__(*args, **kwargs)
            self.pesos_classe = pesos_classe

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            rotulos = inputs.pop("labels")
            saidas = model(**inputs)
            pesos = self.pesos_classe.to(saidas.logits.device, saidas.logits.dtype)
            perda = torch.nn.functional.cross_entropy(saidas.logits, rotulos, weight=pesos)
            return (perda, saidas) if return_outputs else perda

    return TrainerPonderado


def criar_dataset(torch, tokenizer, textos, rotulos, max_length):
    codificado = tokenizer(textos, truncation=True, max_length=max_length)

    class Conjunto(torch.utils.data.Dataset):
        def __len__(self):
            return len(rotulos)

        def __getitem__(self, i):
            item = {k: codificado[k][i] for k in codificado.keys()}
            item["labels"] = int(rotulos[i])
            return item

    return Conjunto()


def pct_truncados(tokenizer, textos, max_length):
    tamanhos = [len(x) for x in tokenizer(textos, truncation=False)["input_ids"]]
    return round(100 * sum(t > max_length for t in tamanhos) / len(tamanhos), 3)


# ---------------------------------------------------------------- treino

def treinar(caminho_config=CONFIG_PADRAO, teste_rapido=False, forcar=False):
    import torch
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              DataCollatorWithPadding, Trainer, TrainingArguments, set_seed)

    config = carregar_config(caminho_config, teste_rapido)
    hp, mb, max_length = config["hiperparametros"], config["modelo_base"], config["max_length"]

    d = dd.preparar_dados()
    treino, validacao = d["treino"], d["validacao"]
    if teste_rapido:
        treino = dd.amostra_estratificada(treino, config["teste_rapido"]["amostra_treino"], hp["seed"])
        validacao = dd.amostra_estratificada(validacao, config["teste_rapido"]["amostra_validacao"], hp["seed"])
    pesos = dd.calcular_pesos(treino["y"], config["pesos_classe"])

    destino = preparar_destino(config, teste_rapido, forcar)
    d["removidos"].to_csv(destino / "colisoes_removidas.csv", index=False)

    # O hash da revisão fixa exatamente os pesos do modelo base baixados do Hugging Face.
    set_seed(hp["seed"])
    tokenizer = AutoTokenizer.from_pretrained(mb["id"], revision=mb["revision"])
    modelo = AutoModelForSequenceClassification.from_pretrained(
        mb["id"], revision=mb["revision"], num_labels=len(CLASSES),
        id2label=dict(enumerate(CLASSES)), label2id={c: i for i, c in enumerate(CLASSES)})

    x_tr = [norm.normalizar(t) for t in treino["text"]]
    x_va = [norm.normalizar(t) for t in validacao["text"]]
    ds_tr = criar_dataset(torch, tokenizer, x_tr, treino["y"].to_numpy(), max_length)
    ds_va = criar_dataset(torch, tokenizer, x_va, validacao["y"].to_numpy(), max_length)

    argumentos = TrainingArguments(
        output_dir=str(destino / "checkpoints"), **hp, data_seed=hp["seed"],
        eval_strategy="epoch", save_strategy="epoch", save_total_limit=1,
        load_best_model_at_end=True, metric_for_best_model="macro_f1", greater_is_better=True,
        logging_strategy="steps", logging_steps=2 if teste_rapido else 50,
        report_to="none", dataloader_num_workers=0)
    trainer = criar_trainer_ponderado(torch, Trainer)(
        model=modelo, args=argumentos, train_dataset=ds_tr, eval_dataset=ds_va,
        data_collator=DataCollatorWithPadding(tokenizer), compute_metrics=av.compute_metrics,
        pesos_classe=torch.tensor([pesos["pesos"][c] for c in CLASSES], dtype=torch.float32))

    print(f"{'TESTE RÁPIDO (não é resultado do modelo)' if teste_rapido else 'TREINO'}: {destino.name} | "
          f"treino={len(ds_tr)} validação={len(ds_va)} | dispositivo={argumentos.device}")
    inicio = time.perf_counter()
    trainer.train()
    duracao = time.perf_counter() - inicio

    # Ao fim do train(), o trainer já carregou o melhor checkpoint (maior macro F1 na validação).
    saida = trainer.predict(ds_va)
    logits = np.asarray(saida.predictions)
    avaliacao = av.resumo_avaliacao(saida.label_ids, logits.argmax(axis=-1), av.softmax(logits))
    trainer.save_model(str(destino))
    tokenizer.save_pretrained(str(destino))
    shutil.rmtree(destino / "checkpoints", ignore_errors=True)

    estado = trainer.state
    meta = {
        "id": destino.name,
        "oficial": not teste_rapido,
        "criado_em_utc": agora_utc(),
        "classes": CLASSES,
        "modelo_base": mb,
        "normalizacao": {"versao": norm.VERSAO, "regras": norm.REGRAS},
        "max_length": max_length,
        "hiperparametros": hp,
        "pesos_classe": pesos,
        "selecao": {"metrica": "macro_f1", "conjunto": "validacao",
                    "melhor_macro_f1": estado.best_metric,
                    "melhor_checkpoint": Path(estado.best_model_checkpoint).name
                    if estado.best_model_checkpoint else None},
        "dados": {"arquivos": d["arquivos"], "colisoes": d["colisoes"],
                  "linhas_usadas": {"treino": len(ds_tr), "validacao": len(ds_va)}},
        "truncamento": {"max_length": max_length,
                        "treino_pct": pct_truncados(tokenizer, x_tr, max_length),
                        "validacao_pct": pct_truncados(tokenizer, x_va, max_length)},
        "avaliacao_validacao": avaliacao,
        "metricas_validacao_por_epoca": [e for e in estado.log_history if "eval_macro_f1" in e],
        "perda_treino": [{"passo": e["step"], "epoca": e["epoch"], "loss": e["loss"]}
                         for e in estado.log_history if "loss" in e],
        "execucao": {"dispositivo": str(argumentos.device), "tempo_treino_s": round(duracao, 1),
                     "passos": estado.global_step},
        "bibliotecas": versoes_bibliotecas(),
    }
    (destino / "orca_model.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    print(f"\nModelo salvo em {destino}")
    print(av.formatar_avaliacao(avaliacao))

    if teste_rapido:
        s_passo = duracao / max(estado.global_step, 1)
        epocas = carregar_config(caminho_config)["hiperparametros"]["num_train_epochs"]
        passos = math.ceil(len(d["treino"]) / hp["per_device_train_batch_size"]) * epocas
        print(f"\nMedido: {s_passo:.2f} s/passo. Estimativa (não medida) do treino completo: "
              f"{passos} passos = {s_passo * passos / 3600:.1f} h, mais as avaliações por época.")
    return destino
