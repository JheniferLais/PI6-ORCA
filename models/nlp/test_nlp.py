"""
Testes do S2-03 que NÃO precisam de torch/transformers nem dos pesos do modelo.

Rodar (dentro de models/nlp):
    python -m unittest test_nlp -v        # ou: pytest test_nlp.py -v

O laço de treino e o recarregamento do modelo só são exercitados pelo
'treino.py treinar --teste-rapido' e 'treino.py verificar-modelo'.
"""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import dados as dd
import normalizacao as norm
import treino as tr

CLASSES = dd.CLASSES
PASTA_DATASETS = Path(__file__).resolve().parent / "data" / "datasets"


def df(textos, classe="seguro"):
    y = CLASSES.index(classe)
    return pd.DataFrame({"text": textos, "y": y, "indice": range(len(textos))})


class TestNormalizacao(unittest.TestCase):
    def test_remove_user_e_links(self):
        t = "  @user @USER olha https://t.co/abc123 e www.x.com/a   fim\n\n"
        self.assertEqual(norm.normalizar(t), "olha e fim")

    def test_preserva_caixa_e_acentos(self):
        self.assertEqual(norm.normalizar("Não ODEIO você"), "Não ODEIO você")

    def test_nfc(self):
        self.assertEqual(norm.normalizar("e\u0301"), "\u00e9")

    def test_outras_mencoes_nao_sao_alteradas(self):
        self.assertEqual(norm.normalizar("oi @maria"), "oi @maria")

    def test_none_e_vazio(self):
        self.assertEqual(norm.normalizar(None), "")
        self.assertEqual(norm.normalizar("@user https://t.co/x"), "")

    def test_chave_ignora_caixa(self):
        self.assertEqual(norm.chave_comparacao("Olá  MUNDO @user"), "olá mundo")


class TestColisoes(unittest.TestCase):
    def setUp(self):
        self.tr = df(["a b", "c d", "novo treino", "@user so no treino", "   ", "dup", "dup"])
        self.va = df(["A  B @user", "val unico", "x teste"])
        self.te = df(["x TESTE", "teste unico", "c d https://t.co/1"])

    def test_politica(self):
        t, v, rel, rem = dd.tratar_colisoes(self.tr, self.va, self.te)
        # treino: "a b" (colide c/ validação), "c d" (colide c/ teste), vazio -> removidos
        self.assertEqual(sorted(t["text"]), sorted(["novo treino", "@user so no treino", "dup", "dup"]))
        # validação perde só "x teste" (colide com o teste)
        self.assertEqual(sorted(v["text"]), sorted(["A  B @user", "val unico"]))
        self.assertEqual(rel["removidos"]["treino"]["por_motivo"],
                         {"colide_com_teste": 1, "colide_com_validacao": 1,
                          "vazio_apos_normalizacao": 1})
        self.assertEqual(rel["removidos"]["validacao"]["por_motivo"], {"colide_com_teste": 1})
        self.assertEqual(rel["removidos"]["teste"]["total"], 0)
        self.assertEqual(rel["linhas_efetivas"], {"treino": 4, "validacao": 2, "teste": 3})
        self.assertEqual(rel["duplicados_internos_apos_normalizacao"]["treino"], 1)  # "dup"
        self.assertEqual(rel["vazios_apos_normalizacao"]["treino"], 1)

    def test_nada_e_silencioso(self):
        _, _, rel, rem = dd.tratar_colisoes(self.tr, self.va, self.te)
        total = rel["removidos"]["treino"]["total"] + rel["removidos"]["validacao"]["total"]
        self.assertEqual(len(rem), total)
        self.assertEqual(set(rem.columns), {"divisao", "indice", "classe", "motivo"})

    def test_entradas_nao_sao_alteradas(self):
        antes = (self.tr.copy(), self.va.copy(), self.te.copy())
        dd.tratar_colisoes(self.tr, self.va, self.te)
        for original, depois in zip(antes, (self.tr, self.va, self.te)):
            pd.testing.assert_frame_equal(original, depois)

    def test_sem_vazamento_depois_do_tratamento(self):
        t, v, _, _ = dd.tratar_colisoes(self.tr, self.va, self.te)
        k = lambda d: set(d["text"].map(norm.chave_comparacao))
        self.assertFalse(k(t) & k(v))
        self.assertFalse(k(t) & k(self.te))
        self.assertFalse(k(v) & k(self.te))

    def test_rotulo_divergente_e_contado(self):
        t = pd.DataFrame({"text": ["mesmo"], "y": 0, "indice": [0]})
        v = pd.DataFrame({"text": ["Mesmo"], "y": 2, "indice": [0]})
        te = pd.DataFrame({"text": ["outro"], "y": 1, "indice": [0]})
        _, _, rel, _ = dd.tratar_colisoes(t, v, te)
        self.assertEqual(rel["chaves_em_mais_de_uma_divisao"], 1)
        self.assertEqual(rel["chaves_com_rotulo_divergente"], 1)


class TestPesos(unittest.TestCase):
    def test_formula(self):
        y = np.array([0] * 80 + [1] * 5 + [2] * 15)  # N=100, K=3
        p = dd.calcular_pesos(y)
        self.assertAlmostEqual(p["pesos"]["seguro"], 100 / (3 * 80))
        self.assertAlmostEqual(p["pesos"]["suicidio"], 100 / (3 * 5))
        self.assertAlmostEqual(p["pesos"]["odio"], 100 / (3 * 15))
        self.assertEqual(p["contagens"], {"seguro": 80, "suicidio": 5, "odio": 15})

    def test_classe_balanceada_tem_peso_1(self):
        p = dd.calcular_pesos(np.array([0, 1, 2] * 10))
        self.assertTrue(all(abs(v - 1) < 1e-12 for v in p["pesos"].values()))

    def test_nenhum_e_classe_ausente(self):
        self.assertEqual(set(dd.calcular_pesos(np.array([0, 1, 2]), "nenhum")["pesos"].values()), {1.0})
        with self.assertRaises(ValueError):
            dd.calcular_pesos(np.array([0, 0, 1]))
        with self.assertRaises(ValueError):
            dd.calcular_pesos(np.array([0, 1, 2]), "outro")


class TestMetricasESelecao(unittest.TestCase):
    def test_macro_f1(self):
        y = np.array([0, 0, 1, 1, 2, 2])
        self.assertAlmostEqual(tr.calcular_metricas(y, y)["macro_f1"], 1.0)
        m = tr.calcular_metricas(y, np.zeros(6, dtype=int))  # sempre "seguro"
        self.assertAlmostEqual(m["recall_suicidio"], 0.0)
        self.assertAlmostEqual(m["macro_f1"], (0.5 + 0 + 0) / 3)

    def test_compute_metrics_aceita_tupla(self):
        logits = np.array([[2, 0, 0], [0, 2, 0], [0, 0, 2]])
        m = tr.compute_metrics((logits, np.array([0, 1, 2])))
        self.assertAlmostEqual(m["macro_f1"], 1.0)

    def test_melhor_epoca_por_macro_f1_e_nao_pela_ultima_nem_pela_perda(self):
        log = [
            {"loss": 0.9, "step": 10},
            {"eval_macro_f1": 0.60, "eval_loss": 0.50, "epoch": 1.0, "step": 100},
            {"eval_macro_f1": 0.72, "eval_loss": 0.55, "epoch": 2.0, "step": 200},
            {"eval_macro_f1": 0.70, "eval_loss": 0.40, "epoch": 3.0, "step": 300},
        ]
        self.assertEqual(tr.escolher_melhor_epoca(log)["epoch"], 2.0)

    def test_empate_fica_com_a_mais_antiga_e_sem_avaliacao(self):
        log = [{"eval_macro_f1": 0.7, "epoch": 1.0}, {"eval_macro_f1": 0.7, "epoch": 2.0}]
        self.assertEqual(tr.escolher_melhor_epoca(log)["epoch"], 1.0)
        self.assertIsNone(tr.escolher_melhor_epoca([{"loss": 1.0}]))


class TestResumoAvaliacao(unittest.TestCase):
    def test_matriz_e_contagens(self):
        y_true = np.array([0, 0, 0, 1, 1, 2])
        y_pred = np.array([0, 0, 2, 0, 1, 2])
        r = tr.resumo_avaliacao(y_true, y_pred)
        self.assertEqual(r["matriz_confusao"], [[2, 0, 1], [1, 1, 0], [0, 0, 1]])
        self.assertEqual(r["reais_por_classe"], {"seguro": 3, "suicidio": 2, "odio": 1})
        self.assertEqual(r["previstas_por_classe"], {"seguro": 3, "suicidio": 1, "odio": 2})
        self.assertAlmostEqual(r["metricas"]["recall_suicidio"], 0.5)
        self.assertAlmostEqual(r["metricas"]["precision_suicidio"], 1.0)

    def test_precisao_zero_sem_previsao_x_com_previsao_errada(self):
        """P=R=F1=0 em 'suicidio' vale tanto se o modelo nunca previu a classe
        quanto se previu e errou: só a matriz distingue os dois casos."""
        y_true = np.array([1, 1, 0, 0])
        nunca = tr.resumo_avaliacao(y_true, np.array([0, 0, 0, 0]))
        errou = tr.resumo_avaliacao(y_true, np.array([0, 0, 1, 0]))
        for r in (nunca, errou):
            self.assertEqual(r["metricas"]["precision_suicidio"], 0.0)
            self.assertEqual(r["metricas"]["recall_suicidio"], 0.0)
        self.assertEqual(nunca["previstas_por_classe"]["suicidio"], 0)
        self.assertEqual(errou["previstas_por_classe"]["suicidio"], 1)

    def test_probabilidades_e_formatacao(self):
        logits = np.array([[3.0, 0, 0], [0, 3.0, 0], [0, 0, 3.0]])
        p = tr._softmax(logits)
        self.assertTrue(np.allclose(p.sum(axis=1), 1))
        r = tr.resumo_avaliacao([0, 1, 2], logits.argmax(axis=1), p)
        self.assertGreater(r["probabilidade_media_na_classe_real"]["suicidio"], 0.9)
        texto = tr.formatar_avaliacao(r)
        self.assertIn("Matriz de confusão", texto)
        self.assertIn("macro F1 = 1.0000", texto)
        json.dumps(r)


class TestConfigEDestino(unittest.TestCase):
    def test_config_padrao_valida_e_valores_aprovados(self):
        c = tr.carregar_config()
        hp = c["hiperparametros"]
        self.assertEqual(c["modelo_base"]["id"], "neuralmind/bert-base-portuguese-cased")
        self.assertEqual((hp["learning_rate"], hp["num_train_epochs"], hp["per_device_train_batch_size"]),
                         (2e-5, 3, 16))
        self.assertEqual((hp["weight_decay"], hp["warmup_ratio"], hp["lr_scheduler_type"],
                          hp["max_grad_norm"], hp["seed"], hp["fp16"], hp["bf16"]),
                         (0.01, 0.1, "linear", 1.0, 42, False, False))
        self.assertEqual(c["max_length"], 128)
        self.assertEqual(c["selecao"], {"metrica": "macro_f1", "conjunto": "validacao"})

    def test_epocas_configuravel(self):
        self.assertEqual(tr.carregar_config(epocas=5)["hiperparametros"]["num_train_epochs"], 5)
        self.assertEqual(tr.carregar_config(teste_rapido=True)["hiperparametros"]["num_train_epochs"], 1)
        with self.assertRaises(ValueError):
            tr.carregar_config(epocas=0)

    def test_teste_rapido_nunca_aponta_para_nlp_v1(self):
        c = tr.carregar_config()
        oficial, flag_o = tr.resolver_destino(c, teste_rapido=False)
        teste, flag_t = tr.resolver_destino(c, teste_rapido=True)
        self.assertEqual((oficial.name, flag_o), ("nlp-v1", True))
        self.assertEqual((teste.name, flag_t), ("nlp-v1-teste", False))
        self.assertNotEqual(oficial, teste)
        for id_ruim in ("nlp-v1", "outro", "../nlp-v1-teste"):
            c["teste_rapido"]["id"] = id_ruim
            with self.assertRaises(ValueError):
                tr.resolver_destino(c, teste_rapido=True)

    def test_oficial_recusa_sobrescrever_e_forcar_arquiva(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "nlp-v1"
            destino.mkdir()
            (destino / "orca_model.json").write_text("{}")
            with self.assertRaises(FileExistsError):
                tr.preparar_destino(destino, oficial=True, forcar=False)
            self.assertTrue((destino / "orca_model.json").exists())   # intacto
            arquivada = tr.preparar_destino(destino, oficial=True, forcar=True)
            self.assertTrue((arquivada / "orca_model.json").exists())  # preservado, não apagado
            self.assertTrue(destino.exists() and not any(destino.iterdir()))

    def test_teste_rapido_so_recria_a_propria_pasta(self):
        with tempfile.TemporaryDirectory() as tmp:
            oficial, teste = Path(tmp) / "nlp-v1", Path(tmp) / "nlp-v1-teste"
            for p in (oficial, teste):
                p.mkdir()
                (p / "x.txt").write_text("x")
            tr.preparar_destino(teste, oficial=False, forcar=False)
            self.assertTrue((oficial / "x.txt").exists())
            self.assertFalse((teste / "x.txt").exists())
            with self.assertRaises(AssertionError):  # defesa extra: nunca limpa pasta sem '-teste'
                tr.preparar_destino(oficial, oficial=False, forcar=False)
            self.assertTrue((oficial / "x.txt").exists())

    def test_hiperparametros_efetivos(self):
        hp = tr.carregar_config()["hiperparametros"]
        class Enum:  # imita enums do transformers
            value = "linear"
        efetivos = dict(hp, lr_scheduler_type=Enum())
        self.assertEqual(tr.comparar_hiperparametros(hp, efetivos), [])
        efetivos["learning_rate"] = 5e-5
        dif = tr.comparar_hiperparametros(hp, efetivos)
        self.assertEqual([d["hiperparametro"] for d in dif], ["learning_rate"])


class TestRevisaoDoModeloBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = tr.carregar_config()
        self.config["saida"]["pasta"] = str(Path(self.tmp.name))
        self.config["modelo_base"]["revision"] = None

    def tearDown(self):
        self.tmp.cleanup()

    def test_sem_download_nao_inicia(self):
        with self.assertRaises(RuntimeError):
            tr.resolver_revisao(self.config)

    def test_usa_hash_gravado_pelo_baixar(self):
        h = "a" * 40
        (Path(self.tmp.name) / "modelo-base.json").write_text(json.dumps(
            {"id": self.config["modelo_base"]["id"], "revision": h}))
        self.assertEqual(tr.resolver_revisao(self.config), h)

    def test_revision_fixada_precisa_ser_hash(self):
        self.config["modelo_base"]["revision"] = "main"
        with self.assertRaises(ValueError):
            tr.resolver_revisao(self.config)


@unittest.skipUnless((PASTA_DATASETS / "treino.csv").exists(),
                     "datasets não gerados (rode data/pipeline.py)")
class TestDadosReais(unittest.TestCase):
    """Roda sobre os CSVs reais de S2-02, se existirem."""

    @classmethod
    def setUpClass(cls):
        cls.d = dd.preparar_dados(PASTA_DATASETS)

    def test_formato_e_rotulos(self):
        self.assertEqual(CLASSES, ["seguro", "suicidio", "odio"])
        for nome in ("treino", "validacao"):
            onehot = self.d[nome][CLASSES]
            self.assertTrue((onehot.sum(axis=1) == 1).all())
            self.assertTrue((self.d[nome]["y"] == onehot.to_numpy().argmax(axis=1)).all())

    def test_sem_vazamento_efetivo(self):
        teste = dd.carregar_split(PASTA_DATASETS / "teste.csv")
        k = lambda d: set(d["text"].map(norm.chave_comparacao))
        self.assertFalse(k(self.d["treino"]) & k(self.d["validacao"]))
        self.assertFalse(k(self.d["treino"]) & k(teste))
        self.assertFalse(k(self.d["validacao"]) & k(teste))

    def test_hashes_e_relatorio(self):
        self.assertEqual(set(self.d["arquivos"]) >= {"treino.csv", "validacao.csv", "teste.csv"}, True)
        rel = self.d["colisoes"]
        self.assertEqual(rel["linhas_originais"]["teste"], rel["linhas_efetivas"]["teste"])
        json.dumps(rel)  # serializável em orca_model.json

    def test_pesos_do_treino_real(self):
        orig = dd.carregar_split(PASTA_DATASETS / "treino.csv")
        p = dd.calcular_pesos(orig["y"])["pesos"]
        n = len(orig)
        for i, c in enumerate(CLASSES):
            self.assertAlmostEqual(p[c], n / (3 * (orig["y"] == i).sum()))

    def test_amostra_estratificada_tem_todas_as_classes(self):
        a = dd.amostra_estratificada(self.d["treino"], 192, 42)
        self.assertEqual(len(a), 192)
        self.assertEqual(set(a["y"]), {0, 1, 2})
        pd.testing.assert_frame_equal(a, dd.amostra_estratificada(self.d["treino"], 192, 42))


if __name__ == "__main__":
    unittest.main()
