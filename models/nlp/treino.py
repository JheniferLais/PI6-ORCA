"""
Fine-tuning do classificador de texto do ORCA (S2-03, versão nlp-v1).

Subcomandos (rode dentro do venv models/nlp/.venv-treino):

  python treino.py dados             valida os CSVs de S2-02, mostra colisões e pesos (sem torch)
  python treino.py baixar            baixa o BERTimbau Base e fixa o hash exato da revisão
  python treino.py treinar --teste-rapido   valida o pipeline com amostra pequena (NÃO é o treino oficial)
  python treino.py treinar           treino oficial, salvo em artifacts/nlp-v1
  python treino.py verificar-modelo  recarrega o modelo salvo e classifica alguns textos de validação

Todos os hiperparâmetros ficam em config/nlp-v1.json.
"""
import argparse
import json
import math
import platform
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

import dados as dd
import normalizacao as norm

PASTA = dd.PASTA_NLP
CLASSES = dd.CLASSES
CONFIG_PADRAO = PASTA / "config" / "nlp-v1.json"
ARQ_METADATA = "orca_model.json"
ARQ_MODELO_BASE = "modelo-base.json"
IGNORAR_NO_DOWNLOAD = ["*.h5", "*.msgpack", "*.ot", "*.onnx"]  # só os pesos PyTorch
HASH_COMMIT = re.compile(r"[0-9a-f]{40}")
HP_OBRIGATORIOS = ["learning_rate", "num_train_epochs", "per_device_train_batch_size",
                   "per_device_eval_batch_size", "weight_decay", "warmup_ratio",
                   "lr_scheduler_type", "max_grad_norm", "seed", "optim", "fp16", "bf16"]


# ---------------------------------------------------------------- configuração

def carregar_config(caminho=CONFIG_PADRAO, epocas=None, teste_rapido=False):
    """Lê e valida a configuração. 'epocas' (opcional) substitui num_train_epochs;
    no teste rápido vale teste_rapido.num_train_epochs."""
    config = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if config["classes"] != CLASSES:
        raise ValueError(f"classes da configuração {config['classes']} diferem das de "
                         f"data/pipeline.py {CLASSES}")
    if config["normalizacao"] != norm.VERSAO:
        raise ValueError(f"configuração pede a normalização {config['normalizacao']}, "
                         f"mas normalizacao.py está em {norm.VERSAO}")
    faltando = [k for k in HP_OBRIGATORIOS if k not in config["hiperparametros"]]
    if faltando:
        raise ValueError(f"hiperparâmetros ausentes na configuração: {faltando}")
    if config["pesos_classe"]["metodo"] not in dd.METODOS_PESO:
        raise ValueError(f"método de peso inválido: {config['pesos_classe']['metodo']}")
    if config["selecao"] != {"metrica": "macro_f1", "conjunto": "validacao"}:
        raise ValueError("a seleção do melhor modelo deve ser macro_f1 na validação")
    if teste_rapido:
        config["hiperparametros"]["num_train_epochs"] = config["teste_rapido"]["num_train_epochs"]
    elif epocas is not None:
        if epocas < 1:
            raise ValueError("--epocas deve ser >= 1")
        config["hiperparametros"]["num_train_epochs"] = epocas
    return config


def resolver_destino(config, teste_rapido):
    """Pasta de saída e se a execução é oficial. O teste rápido NUNCA aponta para
    a pasta oficial: usa teste_rapido.id, que precisa terminar em '-teste'."""
    base = (PASTA / config["saida"]["pasta"]).resolve()
    oficial = base / config["versao"]
    if not teste_rapido:
        return oficial, True
    destino = (base / config["teste_rapido"]["id"]).resolve()
    if destino == oficial or destino.parent != base or not destino.name.endswith("-teste"):
        raise ValueError(f"id de teste rápido inválido ({destino.name}): deve ser diferente "
                         f"de {oficial.name}, terminar em '-teste' e ficar em {base}")
    return destino, False


def preparar_destino(destino, oficial, forcar):
    """Oficial: recusa sobrescrever; com --forcar, ARQUIVA a pasta anterior (renomeia).
    Teste rápido: só recria a própria pasta '-teste'. Devolve a pasta arquivada ou None."""
    if destino.exists() and any(destino.iterdir()):
        if oficial:
            if not forcar:
                raise FileExistsError(
                    f"{destino} já existe. O treino oficial não sobrescreve artefatos; "
                    f"use --forcar para arquivar a versão anterior e treinar de novo.")
            agora = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            arquivada = destino.with_name(f"{destino.name}.anterior-{agora}")
            destino.rename(arquivada)
            destino.mkdir(parents=True)
            return arquivada
        assert destino.name.endswith("-teste")
        shutil.rmtree(destino)
    destino.mkdir(parents=True, exist_ok=True)
    return None


# ---------------------------------------------------------------- métricas

def calcular_metricas(y_true, y_pred):
    """macro F1 (média simples do F1 das 3 classes), acurácia e precisão/recall/F1 por classe."""
    rotulos = list(range(len(CLASSES)))
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=rotulos, zero_division=0)
    m = {"macro_f1": float(f.mean()), "accuracy": float(accuracy_score(y_true, y_pred))}
    for i, c in enumerate(CLASSES):
        m[f"precision_{c}"], m[f"recall_{c}"], m[f"f1_{c}"] = float(p[i]), float(r[i]), float(f[i])
    return m


def compute_metrics(eval_pred):
    logits, rotulos = (eval_pred.predictions, eval_pred.label_ids) \
        if hasattr(eval_pred, "predictions") else eval_pred
    return calcular_metricas(np.asarray(rotulos), np.asarray(logits).argmax(axis=-1))


def _softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def resumo_avaliacao(y_true, y_pred, probs=None):
    """Matriz de confusão (linhas = classe real, colunas = classe prevista),
    contagem de previsões por classe e métricas por classe. 'probs' (n x K,
    opcional) acrescenta a probabilidade média por classe."""
    y_true, y_pred = np.asarray(y_true, dtype=int), np.asarray(y_pred, dtype=int)
    k = len(CLASSES)
    matriz = np.zeros((k, k), dtype=int)
    for real, prev in zip(y_true, y_pred):
        matriz[real, prev] += 1
    r = {"classes": CLASSES, "linhas": "classe real", "colunas": "classe prevista",
         "matriz_confusao": matriz.tolist(),
         "reais_por_classe": {c: int(n) for c, n in zip(CLASSES, np.bincount(y_true, minlength=k))},
         "previstas_por_classe": {c: int(n) for c, n in zip(CLASSES, np.bincount(y_pred, minlength=k))},
         "metricas": calcular_metricas(y_true, y_pred)}
    if probs is not None:
        probs = np.asarray(probs, dtype=float)
        r["probabilidade_media_por_classe"] = {c: float(probs[:, i].mean()) for i, c in enumerate(CLASSES)}
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


def escolher_melhor_epoca(log_history):
    """Entrada de avaliação com maior macro F1 na validação; em empate, a mais
    antiga (mesmo critério do Trainer: só troca se for estritamente melhor)."""
    melhor = None
    for entrada in log_history:
        if "eval_macro_f1" in entrada and (
                melhor is None or entrada["eval_macro_f1"] > melhor["eval_macro_f1"]):
            melhor = entrada
    return melhor


def _valor(v):
    return getattr(v, "value", v)  # enums do transformers -> texto


def comparar_hiperparametros(configurados, efetivos):
    """Lista de diferenças entre o configurado e o que o Trainer realmente usou."""
    dif = []
    for chave, esperado in configurados.items():
        real = _valor(efetivos.get(chave))
        if isinstance(esperado, float) and isinstance(real, (int, float)):
            igual = math.isclose(esperado, real, rel_tol=1e-9, abs_tol=1e-12)
        else:
            igual = esperado == real
        if not igual:
            dif.append({"hiperparametro": chave, "configurado": esperado, "efetivo": real})
    return dif


def versoes_bibliotecas():
    versoes = {"python": platform.python_version()}
    for nome in ["torch", "transformers", "accelerate", "huggingface_hub", "safetensors",
                 "tokenizers", "scikit-learn", "numpy", "pandas"]:
        try:
            versoes[nome] = metadata.version(nome)
        except metadata.PackageNotFoundError:
            versoes[nome] = None
    return versoes


def agora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- modelo base

def _arquivo_modelo_base(config):
    return PASTA / config["saida"]["pasta"] / ARQ_MODELO_BASE


def resolver_revisao(config):
    """Hash exato (40 caracteres) da revisão do modelo base. Vem de
    modelo_base.revision (se fixado na configuração) ou de modelo-base.json,
    gerado por 'treino.py baixar'. Sem nenhum dos dois, o treino não começa."""
    mb, arq = config["modelo_base"], _arquivo_modelo_base(config)
    gravada = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None
    if gravada and gravada["id"] != mb["id"]:
        raise RuntimeError(f"{arq.name} é de outro modelo ({gravada['id']}); rode 'baixar' de novo")
    fixa = mb.get("revision")
    if fixa:
        if not HASH_COMMIT.fullmatch(fixa):
            raise ValueError("modelo_base.revision deve ser o hash de 40 caracteres do commit")
        if gravada and gravada["revision"] != fixa:
            raise RuntimeError(f"revision fixada ({fixa}) difere da baixada ({gravada['revision']})")
        return fixa
    if gravada:
        return gravada["revision"]
    raise RuntimeError("revisão do modelo base desconhecida: rode 'python treino.py baixar' antes")


def baixar_modelo(config):
    from huggingface_hub import snapshot_download
    mb = config["modelo_base"]
    print(f"Baixando {mb['id']} (somente pesos PyTorch)...")
    caminho = snapshot_download(repo_id=mb["id"], revision=mb.get("revision") or None,
                                ignore_patterns=IGNORAR_NO_DOWNLOAD)
    revisao = Path(caminho).name
    if not HASH_COMMIT.fullmatch(revisao):
        raise RuntimeError(f"não consegui identificar o hash da revisão em {caminho}")
    arq = _arquivo_modelo_base(config)
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps({"id": mb["id"], "revision": revisao, "baixado_em_utc": agora_utc()},
                              indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Revisão fixada: {revisao}\nRegistrada em {arq}")


# ---------------------------------------------------------------- dados

def mostrar_dados(config):
    d = dd.preparar_dados(PASTA / config["dados"]["pasta"])
    c = d["colisoes"]
    print("Arquivos:")
    for nome, info in d["arquivos"].items():
        print(f"  {nome}: {info.get('linhas', '-')} linhas, sha256_lf={info['sha256_lf'][:16]}...")
    print("\nColisões após a normalização (norm-v1):")
    print(f"  chaves em mais de uma divisão: {c['chaves_em_mais_de_uma_divisao']} "
          f"(com rótulo divergente: {c['chaves_com_rotulo_divergente']})")
    print(f"  duplicados internos: {c['duplicados_internos_apos_normalizacao']}")
    print(f"  vazios após normalizar: {c['vazios_apos_normalizacao']}")
    for div in ("treino", "validacao", "teste"):
        print(f"  removidos de {div}: {c['removidos'][div]['total']} "
              f"{c['removidos'][div]['por_motivo']} por classe {c['removidos'][div]['por_classe']}")
    print(f"  linhas efetivas: {c['linhas_efetivas']}")
    pesos = dd.calcular_pesos(d["treino"]["y"], config["pesos_classe"]["metodo"])
    print(f"\nPesos de classe ({pesos['formula']}, N={pesos['N']}):")
    for cl in CLASSES:
        print(f"  {cl}: n={pesos['contagens'][cl]}  peso={pesos['pesos'][cl]:.6f}")


# ---------------------------------------------------------------- treino

def _importar_ml():
    try:
        import torch
        import transformers
    except ImportError:
        sys.exit("torch/transformers não estão instalados. Ative o venv de treino "
                 "(models/nlp/.venv-treino) e instale requirements-treino.txt.")
    return torch, transformers


def _criar_trainer_ponderado(torch, Trainer):
    class TrainerPonderado(Trainer):
        """Trainer com entropia cruzada ponderada por classe."""

        def __init__(self, *args, pesos_classe=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._pesos_classe = pesos_classe
            self.chamadas_treino = 0   # evidência de que a perda ponderada foi usada em cada passo

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            rotulos = inputs.pop("labels")
            if model.training:
                self.chamadas_treino += 1
            saidas = model(**inputs)
            pesos = self._pesos_classe.to(saidas.logits.device, saidas.logits.dtype)
            perda = torch.nn.functional.cross_entropy(saidas.logits, rotulos, weight=pesos)
            return (perda, saidas) if return_outputs else perda

    return TrainerPonderado


def _dataset(torch, tokenizer, textos, rotulos, max_length):
    codificado = tokenizer(textos, truncation=True, max_length=max_length)

    class Conjunto(torch.utils.data.Dataset):
        def __len__(self):
            return len(rotulos)

        def __getitem__(self, i):
            item = {k: codificado[k][i] for k in codificado.keys()}
            item["labels"] = int(rotulos[i])
            return item

    return Conjunto()


def _pct_truncados(tokenizer, textos, max_length):
    tamanhos = [len(x) for x in tokenizer(textos, truncation=False)["input_ids"]]
    return round(100 * sum(t > max_length for t in tamanhos) / len(tamanhos), 3)


def treinar(args):
    if args.teste_rapido and args.epocas is not None:
        sys.exit("--epocas não se aplica ao --teste-rapido (use teste_rapido.num_train_epochs)")
    config = carregar_config(args.config, args.epocas, args.teste_rapido)
    hp = config["hiperparametros"]
    destino, oficial = resolver_destino(config, args.teste_rapido)
    revisao = resolver_revisao(config)          # antes de tocar em qualquer pasta
    torch, transformers = _importar_ml()
    from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                              DataCollatorWithPadding, Trainer, TrainingArguments, set_seed)

    d = dd.preparar_dados(PASTA / config["dados"]["pasta"])
    tr_oficial_n, treino, validacao = len(d["treino"]), d["treino"], d["validacao"]
    amostra = None
    if args.teste_rapido:
        tr_cfg = config["teste_rapido"]
        treino = dd.amostra_estratificada(treino, tr_cfg["amostra_treino"], hp["seed"])
        validacao = dd.amostra_estratificada(validacao, tr_cfg["amostra_validacao"], hp["seed"])
        amostra = {"treino": len(treino), "validacao": len(validacao)}
    pesos = dd.calcular_pesos(treino["y"], config["pesos_classe"]["metodo"])

    arquivada = preparar_destino(destino, oficial, args.forcar)
    if arquivada:
        print(f"Versão anterior arquivada em {arquivada}")
    d["removidos"].to_csv(destino / "colisoes_removidas.csv", index=False)

    set_seed(hp["seed"])
    mb, max_length = config["modelo_base"], config["max_length"]
    tokenizer = AutoTokenizer.from_pretrained(mb["id"], revision=revisao, local_files_only=True)
    modelo = AutoModelForSequenceClassification.from_pretrained(
        mb["id"], revision=revisao, local_files_only=True, num_labels=len(CLASSES),
        id2label=dict(enumerate(CLASSES)), label2id={c: i for i, c in enumerate(CLASSES)})
    revisao_confirmada = getattr(modelo.config, "_commit_hash", None)
    if {int(i): c for i, c in modelo.config.id2label.items()} != dict(enumerate(CLASSES)):
        sys.exit(f"mapa de rótulos do modelo ({modelo.config.id2label}) difere de {dict(enumerate(CLASSES))}")

    x_tr = [norm.normalizar(t) for t in treino["text"]]
    x_va = [norm.normalizar(t) for t in validacao["text"]]
    truncados = {"max_length": max_length,
                 "treino_pct": _pct_truncados(tokenizer, x_tr, max_length),
                 "validacao_pct": _pct_truncados(tokenizer, x_va, max_length)}
    ds_tr = _dataset(torch, tokenizer, x_tr, treino["y"].to_numpy(), max_length)
    ds_va = _dataset(torch, tokenizer, x_va, validacao["y"].to_numpy(), max_length)

    argumentos = TrainingArguments(
        output_dir=str(destino / "checkpoints"),
        **{k: hp[k] for k in HP_OBRIGATORIOS},
        data_seed=hp["seed"],
        eval_strategy="epoch", save_strategy="epoch", save_total_limit=1,
        load_best_model_at_end=True, metric_for_best_model="macro_f1", greater_is_better=True,
        logging_strategy="steps", logging_steps=2 if args.teste_rapido else 50,
        report_to="none", dataloader_num_workers=0)
    efetivos = {k: _valor(getattr(argumentos, k)) for k in HP_OBRIGATORIOS}
    diferencas = comparar_hiperparametros(hp, efetivos)
    if diferencas:
        sys.exit(f"o Trainer não aplicou os hiperparâmetros configurados: {diferencas}")

    TrainerPonderado = _criar_trainer_ponderado(torch, Trainer)
    trainer = TrainerPonderado(
        model=modelo, args=argumentos, train_dataset=ds_tr, eval_dataset=ds_va,
        data_collator=DataCollatorWithPadding(tokenizer), compute_metrics=compute_metrics,
        pesos_classe=torch.tensor([pesos["pesos"][c] for c in CLASSES], dtype=torch.float32))

    print(f"{'TESTE RÁPIDO (não é o treino oficial)' if args.teste_rapido else 'TREINO OFICIAL'}: "
          f"{config['versao'] if oficial else config['teste_rapido']['id']} | "
          f"treino={len(ds_tr)} validação={len(ds_va)} | dispositivo={argumentos.device}")
    inicio = time.perf_counter()
    trainer.train()
    duracao = time.perf_counter() - inicio
    estado = trainer.state
    melhor = escolher_melhor_epoca(estado.log_history)   # antes de predict(), que reavalia o modelo carregado
    saida = trainer.predict(ds_va, metric_key_prefix="eval")   # modelo carregado = melhor checkpoint
    final, logits_va = saida.metrics, np.asarray(saida.predictions)
    avaliacao = resumo_avaliacao(saida.label_ids, logits_va.argmax(axis=-1), _softmax(logits_va))
    perda_ok = trainer.chamadas_treino == estado.global_step
    if not perda_ok:
        print(f"AVISO: perda ponderada chamada {trainer.chamadas_treino}x em {estado.global_step} passos.")
    consistente = bool(melhor) and estado.best_metric is not None and math.isclose(
        final["eval_macro_f1"], melhor["eval_macro_f1"], abs_tol=1e-4) and math.isclose(
        estado.best_metric, melhor["eval_macro_f1"], abs_tol=1e-9)
    if not consistente:
        print("AVISO: o modelo final não corresponde ao melhor macro F1 de validação registrado.")

    trainer.save_model(str(destino))
    tokenizer.save_pretrained(str(destino))

    s_passo = duracao / max(estado.global_step, 1)
    passos_oficiais = math.ceil(tr_oficial_n / hp["per_device_train_batch_size"]) * \
        carregar_config(args.config)["hiperparametros"]["num_train_epochs"]
    meta = {
        "id": config["versao"] if oficial else config["teste_rapido"]["id"],
        "oficial": oficial,
        "criado_em_utc": agora_utc(),
        "classes": CLASSES,
        "id2label": dict(enumerate(CLASSES)),
        "modelo_base": {"id": mb["id"], "revision": revisao,
                        "revision_confirmada_pelo_modelo": revisao_confirmada,
                        "finalidade": mb["finalidade"], "justificativa": mb["justificativa"]},
        "normalizacao": {"versao": norm.VERSAO, "regras": norm.REGRAS},
        "max_length": max_length,
        "hiperparametros_configurados": hp,
        "hiperparametros_efetivos": efetivos,
        "diferencas_configurado_vs_efetivo": diferencas,
        "pesos_classe": pesos,
        "perda_ponderada": {"pesos_aplicados": dict(zip(CLASSES, trainer._pesos_classe.tolist())),
                            "chamadas_em_treino": trainer.chamadas_treino,
                            "passos": estado.global_step, "consistente": perda_ok},
        "selecao": {"metrica": "macro_f1", "conjunto": "validacao",
                    "melhor_epoca": melhor["epoch"] if melhor else None,
                    "melhor_passo": melhor["step"] if melhor else None,
                    "melhor_macro_f1": melhor["eval_macro_f1"] if melhor else None,
                    "melhor_checkpoint": Path(estado.best_model_checkpoint).name
                    if estado.best_model_checkpoint else None,
                    "reavaliacao_do_modelo_salvo": {k: v for k, v in final.items()
                                                    if k.startswith("eval_")},
                    "consistente": consistente},
        "dados": {"pasta": config["dados"]["pasta"], "origem": config["dados"]["origem"],
                  "arquivos": d["arquivos"], "colisoes": d["colisoes"],
                  "amostra_teste_rapido": amostra,
                  "linhas_usadas": {"treino": len(ds_tr), "validacao": len(ds_va)}},
        "avaliacao_validacao_modelo_salvo": avaliacao,
        "truncamento": truncados,
        "execucao": {"dispositivo": str(argumentos.device), "tempo_treino_s": round(duracao, 1),
                     "passos": estado.global_step, "segundos_por_passo": round(s_passo, 4),
                     "epocas_executadas": estado.epoch},
        "bibliotecas": versoes_bibliotecas(),
        "metricas_validacao_por_epoca": [e for e in estado.log_history if "eval_macro_f1" in e],
        "perda_treino": [{"passo": e["step"], "epoca": e["epoch"], "loss": e["loss"]}
                         for e in estado.log_history if "loss" in e],
    }
    if oficial and args.epocas is not None:
        meta["aviso"] = "número de épocas diferente do padrão da configuração (--epocas)"
    (destino / ARQ_METADATA).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    print(f"\nModelo salvo em {destino}")
    print(formatar_avaliacao(avaliacao))
    if melhor:
        print(f"Melhor época {melhor['epoch']}: macro F1 de validação = {melhor['eval_macro_f1']:.4f}")
    if args.teste_rapido:
        est = s_passo * passos_oficiais
        print(f"\nMedido no teste rápido: {s_passo:.2f} s/passo (amostra pequena, sem a avaliação).")
        print(f"ESTIMATIVA NÃO MEDIDA para o treino oficial: {passos_oficiais} passos "
              f"x {s_passo:.2f} s = {est / 3600:.1f} h, mais o tempo das avaliações por época.")


# ---------------------------------------------------------------- verificação

def verificar_modelo(args):
    from inferencia import Classificador
    config = carregar_config(args.config)
    destino, _ = resolver_destino(config, args.teste_rapido)
    pasta = Path(args.pasta) if args.pasta else destino
    clf = Classificador(pasta)
    if args.matriz:
        return avaliar_modelo_salvo(clf, config, args.limite, args.json)
    amostra = dd.carregar_split(PASTA / config["dados"]["pasta"] / "validacao.csv").head(args.n)
    previsoes = clf.classificar(amostra["text"].tolist())
    print(f"Modelo {clf.model_version} carregado de {pasta} | classes: {clf.classes}")
    for (_, linha), p in zip(amostra.iterrows(), previsoes):
        print(f"  real={CLASSES[linha['y']]:<9} previsto={p['category']:<9} score={p['score']:.3f}")


def avaliar_modelo_salvo(clf, config, limite, destino_json):
    """Avalia o modelo salvo na validação efetiva (ou numa amostra estratificada de
    'limite' textos) e mostra a matriz de confusão. Só lê; não treina nem grava
    dentro de artifacts, a menos que --json aponte para lá."""
    va = dd.preparar_dados(PASTA / config["dados"]["pasta"])["validacao"]
    if limite:
        va = dd.amostra_estratificada(va, limite, config["hiperparametros"]["seed"])
    textos, probs = va["text"].tolist(), []
    for i in range(0, len(textos), 32):
        lote = clf.classificar(textos[i:i + 32])
        probs.extend([[p["probabilidades"][c] for c in CLASSES] for p in lote])
        if (i // 32) % 50 == 49:
            print(f"  {i + len(lote)}/{len(textos)} textos...")
    probs = np.asarray(probs)
    r = resumo_avaliacao(va["y"], probs.argmax(axis=1), probs)
    print(f"Modelo {clf.model_version} em {len(textos)} textos de validação:")
    print(formatar_avaliacao(r))
    print("Probabilidade média atribuída à classe real:", r["probabilidade_media_na_classe_real"])
    if destino_json:
        Path(destino_json).write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(CONFIG_PADRAO), help="arquivo de configuração JSON")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dados")
    sub.add_parser("baixar")
    t = sub.add_parser("treinar")
    t.add_argument("--teste-rapido", action="store_true",
                   help="amostra pequena em artifacts/nlp-v1-teste; não é o treino oficial")
    t.add_argument("--epocas", type=int, help="substitui num_train_epochs (padrão: da configuração)")
    t.add_argument("--forcar", action="store_true",
                   help="treino oficial: arquiva artifacts/nlp-v1 existente em vez de recusar")
    v = sub.add_parser("verificar-modelo")
    v.add_argument("--teste-rapido", action="store_true", help="verifica artifacts/nlp-v1-teste")
    v.add_argument("--pasta", help="outra pasta de modelo salvo")
    v.add_argument("-n", type=int, default=5, help="quantos textos de validação mostrar (modo simples)")
    v.add_argument("--matriz", action="store_true",
                   help="avalia o modelo salvo na validação e mostra matriz de confusão e métricas por classe")
    v.add_argument("--limite", type=int, help="com --matriz: usa só uma amostra estratificada deste tamanho")
    v.add_argument("--json", help="com --matriz: grava o resultado neste arquivo JSON")
    args = p.parse_args()

    try:
        if args.cmd == "dados":
            mostrar_dados(carregar_config(args.config))
        elif args.cmd == "baixar":
            baixar_modelo(carregar_config(args.config))
        elif args.cmd == "treinar":
            treinar(args)
        else:
            verificar_modelo(args)
    except (RuntimeError, ValueError, FileNotFoundError, FileExistsError) as erro:
        sys.exit(f"ERRO: {erro}")


if __name__ == "__main__":
    main()
