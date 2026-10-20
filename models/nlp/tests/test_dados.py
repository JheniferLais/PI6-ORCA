import json
import unittest

import numpy as np
import pandas as pd

from nlp import dados as dd
from nlp import normalizacao as norm

CLASSES = dd.CLASSES


def df(textos, classe="seguro"):
    y = CLASSES.index(classe)
    return pd.DataFrame({"text": textos, "y": y, "indice": range(len(textos))})


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


@unittest.skipUnless((dd.PASTA_DATASETS / "treino.csv").exists(),
                     "datasets não gerados (rode python nlp/data/pipeline.py)")
class TestDadosReais(unittest.TestCase):
    """Roda sobre os CSVs reais, se existirem."""

    @classmethod
    def setUpClass(cls):
        cls.d = dd.preparar_dados()

    def test_formato_e_rotulos(self):
        self.assertEqual(CLASSES, ["seguro", "suicidio", "odio"])
        for nome in ("treino", "validacao", "teste"):
            onehot = self.d[nome][CLASSES]
            self.assertTrue((onehot.sum(axis=1) == 1).all())
            self.assertTrue((self.d[nome]["y"] == onehot.to_numpy().argmax(axis=1)).all())

    def test_sem_vazamento_efetivo(self):
        k = lambda d: set(d["text"].map(norm.chave_comparacao))
        self.assertFalse(k(self.d["treino"]) & k(self.d["validacao"]))
        self.assertFalse(k(self.d["treino"]) & k(self.d["teste"]))
        self.assertFalse(k(self.d["validacao"]) & k(self.d["teste"]))

    def test_hashes_e_relatorio(self):
        self.assertTrue(set(self.d["arquivos"]) >= {"treino.csv", "validacao.csv", "teste.csv"})
        rel = self.d["colisoes"]
        self.assertEqual(rel["linhas_originais"]["teste"], rel["linhas_efetivas"]["teste"])
        json.dumps(rel)  # serializável em orca_model.json

    def test_amostra_estratificada_tem_todas_as_classes(self):
        a = dd.amostra_estratificada(self.d["treino"], 192, 42)
        self.assertEqual(len(a), 192)
        self.assertEqual(set(a["y"]), {0, 1, 2})
        pd.testing.assert_frame_equal(a, dd.amostra_estratificada(self.d["treino"], 192, 42))


if __name__ == "__main__":
    unittest.main()
