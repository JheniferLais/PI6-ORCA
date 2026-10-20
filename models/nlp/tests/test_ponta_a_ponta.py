"""
Testes de ponta a ponta com um BERT MINÚSCULO de pesos aleatórios e um
vocabulário de 3 palavras. Não baixam nada (nem os pesos do BERTimbau) e rodam
em CPU em poucos segundos. Exigem torch e transformers; sem eles, são pulados.

Usam o código real de treino.py (TrainerPonderado, criar_dataset), de
avaliacao.py (compute_metrics, resumo_avaliacao) e de inferencia.py
(Classificador). Os hiperparâmetros daqui
(taxa 3e-3, 30 épocas) são só do teste e não têm relação com os do nlp-v1.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from nlp import avaliacao as av
from nlp import dados as dd
from nlp import normalizacao as norm
from nlp import treino as tr

try:
    import torch
    import transformers  # noqa: F401
    TEM_ML = True
except ImportError:
    TEM_ML = False

CLASSES = dd.CLASSES
PALAVRA = {"seguro": "aaa", "suicidio": "bbb", "odio": "ccc"}   # cada classe = uma palavra
PESOS = {"seguro": 0.5, "suicidio": 4.0, "odio": 1.0}


@unittest.skipUnless(TEM_ML, "torch/transformers não instalados neste ambiente")
class TestPipelineMinusculo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import (BertConfig, BertForSequenceClassification, BertTokenizerFast,
                                  DataCollatorWithPadding, Trainer, TrainingArguments, set_seed)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.raiz = Path(cls.tmp.name)
        vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "aaa", "bbb", "ccc"]
        (cls.raiz / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
        cls.tok = BertTokenizerFast(vocab_file=str(cls.raiz / "vocab.txt"), do_lower_case=False)
        set_seed(42)
        config = BertConfig(
            vocab_size=len(vocab), hidden_size=32, num_hidden_layers=2, num_attention_heads=2,
            intermediate_size=64, max_position_embeddings=32, num_labels=3,
            id2label=dict(enumerate(CLASSES)), label2id={c: i for i, c in enumerate(CLASSES)})
        cls.modelo = BertForSequenceClassification(config)

        # o nº de repetições (1 a 3) é independente da classe, para o modelo não
        # poder usar o comprimento do texto como atalho para a classe
        textos = [" ".join([PALAVRA[CLASSES[i % 3]]] * (1 + (i // 3) % 3)) for i in range(60)]
        cls.y = np.array([i % 3 for i in range(60)])
        cls.ds = tr.criar_dataset(torch, cls.tok, textos, cls.y, 16)
        cls.colador = DataCollatorWithPadding(cls.tok)
        cls.pesos = torch.tensor([PESOS[c] for c in CLASSES], dtype=torch.float32)

        TrainerPonderado = tr.criar_trainer_ponderado(torch, Trainer)
        argumentos = TrainingArguments(
            output_dir=str(cls.raiz / "ck"), learning_rate=3e-3, num_train_epochs=30,
            per_device_train_batch_size=8, per_device_eval_batch_size=16, seed=42,
            report_to="none", save_strategy="no", eval_strategy="no", logging_strategy="no",
            disable_tqdm=True, use_cpu=True)
        cls.trainer = TrainerPonderado(
            model=cls.modelo, args=argumentos, train_dataset=cls.ds, data_collator=cls.colador,
            compute_metrics=av.compute_metrics, pesos_classe=cls.pesos)

        cls.pesos_vistos = []
        original = torch.nn.functional.cross_entropy

        def espiao(*args, **kwargs):
            cls.pesos_vistos.append(kwargs.get("weight"))
            return original(*args, **kwargs)

        with mock.patch("torch.nn.functional.cross_entropy", espiao):
            cls.trainer.train()
        cls.modelo.eval()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pesos_sao_passados_a_perda_em_todo_passo(self):
        passos = self.trainer.state.global_step
        self.assertGreater(passos, 0)
        self.assertEqual(len(self.pesos_vistos), passos)
        for w in self.pesos_vistos:
            self.assertIsNotNone(w)
            self.assertTrue(torch.allclose(w.cpu(), self.pesos))

    def test_valor_da_perda_e_o_ponderado_e_nao_o_simples(self):
        lote = self.colador([self.ds[i] for i in range(9)])
        y = lote["labels"]
        with torch.no_grad():
            logits = self.modelo(**{k: v for k, v in lote.items() if k != "labels"}).logits
            perda = float(self.trainer.compute_loss(self.modelo, dict(lote)))
        logp = torch.log_softmax(logits, dim=-1)
        w = self.pesos[y]
        manual = float(-(w * logp[torch.arange(len(y)), y]).sum() / w.sum())
        simples = float(torch.nn.functional.cross_entropy(logits, y))
        self.assertAlmostEqual(perda, manual, places=5)
        self.assertNotAlmostEqual(perda, simples, places=3)

    def test_rotulos_dataset_modelo_metricas(self):
        saida = self.trainer.predict(self.ds, metric_key_prefix="eval")
        self.assertTrue(np.array_equal(saida.label_ids, self.y))   # rótulos chegam intactos
        r = av.resumo_avaliacao(saida.label_ids, saida.predictions.argmax(-1))
        for i in range(3):                                          # diagonal dominante
            self.assertGreaterEqual(r["matriz_confusao"][i][i], 18)
        self.assertGreater(r["metricas"]["f1_suicidio"], 0.9)       # classe 1 = 'bbb'
        self.assertEqual({int(i): c for i, c in self.modelo.config.id2label.items()},
                         dict(enumerate(CLASSES)))

    @classmethod
    def _classificador_recarregado(cls):
        """Salva o modelo treinado e o recarrega com a Classificador (uma vez)."""
        if getattr(cls, "_clf", None) is None:
            from nlp.inferencia import Classificador
            pasta = cls.raiz / "modelo-salvo"
            cls.trainer.save_model(str(pasta))
            cls.tok.save_pretrained(str(pasta))
            (pasta / "orca_model.json").write_text(json.dumps(
                {"id": "toy", "classes": CLASSES, "max_length": 16,
                 "normalizacao": {"versao": norm.VERSAO}}), encoding="utf-8")
            cls._clf = Classificador(pasta)
        return cls._clf

    SONDAS = ["aaa", "bbb", "ccc", "aaa aaa aaa", "bbb bbb", "ccc ccc ccc"]

    def test_reload_e_fiel_ao_modelo_em_memoria(self):
        """Isola o recarregamento: mesmos token ids e mesmos logits que o modelo treinado."""
        clf = self._classificador_recarregado()
        orig = self.tok(self.SONDAS, padding=True, return_tensors="pt")
        rec = clf.tokenizer(self.SONDAS, padding=True, return_tensors="pt")
        self.assertTrue(torch.equal(orig["input_ids"], rec["input_ids"]),
                        f"tokenizador recarregado difere: {orig['input_ids']} x {rec['input_ids']}")
        with torch.no_grad():
            a = self.modelo(**orig).logits
            b = clf.modelo(**rec).logits
        self.assertTrue(torch.allclose(a, b, atol=1e-5), f"logits diferem:\n{a}\n{b}")
        self.assertEqual(clf.classes, CLASSES)

    def test_inferencia_aplica_a_mesma_normalizacao(self):
        clf = self._classificador_recarregado()
        suja = clf.classificar("@user ccc https://t.co/xyz")[0]["probabilidades"]
        limpa = clf.classificar("ccc")[0]["probabilidades"]
        for c in CLASSES:
            self.assertAlmostEqual(suja[c], limpa[c], places=6)

    def test_categorias_do_modelo_recarregado(self):
        clf = self._classificador_recarregado()
        esperado = ["seguro", "suicidio", "odio", "seguro", "suicidio", "odio"]
        previsto = [r["category"] for r in clf.classificar(self.SONDAS)]
        self.assertEqual(previsto, esperado)

    def test_classificar_longo_texto_curto_igual_a_classificar(self):
        clf = self._classificador_recarregado()
        for t in ("aaa aaa", "ccc ccc"):
            curto, longo = clf.classificar(t)[0], clf.classificar_longo(t)
            self.assertEqual(longo["category"], curto["category"])
            self.assertAlmostEqual(longo["score"], curto["score"], places=5)
        self.assertIsNone(clf.classificar_longo("@user https://t.co/x"))

    def test_classificar_longo_analisa_alem_de_max_length(self):
        """Texto de várias janelas: o trecho de risco no fim seria cortado por
        classificar() (max_length=16), mas classificar_longo() o encontra."""
        clf = self._classificador_recarregado()
        texto = " ".join(["aaa"] * 40 + ["bbb"] * 10)
        self.assertEqual(clf.classificar(texto)[0]["category"], "seguro")
        self.assertEqual(clf.classificar_longo(texto)["category"], "suicidio")

if __name__ == "__main__":
    unittest.main()
