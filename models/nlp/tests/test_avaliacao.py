import json
import unittest

import numpy as np

from nlp import avaliacao as av


class TestMetricas(unittest.TestCase):
    def test_macro_f1(self):
        y = np.array([0, 0, 1, 1, 2, 2])
        self.assertAlmostEqual(av.calcular_metricas(y, y)["macro_f1"], 1.0)
        m = av.calcular_metricas(y, np.zeros(6, dtype=int))  # sempre "seguro"
        self.assertAlmostEqual(m["recall_suicidio"], 0.0)
        self.assertAlmostEqual(m["macro_f1"], (0.5 + 0 + 0) / 3)

    def test_compute_metrics_aceita_tupla(self):
        logits = np.array([[2, 0, 0], [0, 2, 0], [0, 0, 2]])
        self.assertAlmostEqual(av.compute_metrics((logits, np.array([0, 1, 2])))["macro_f1"], 1.0)


class TestResumoAvaliacao(unittest.TestCase):
    def test_matriz_e_contagens(self):
        y_true = np.array([0, 0, 0, 1, 1, 2])
        y_pred = np.array([0, 0, 2, 0, 1, 2])
        r = av.resumo_avaliacao(y_true, y_pred)
        self.assertEqual(r["matriz_confusao"], [[2, 0, 1], [1, 1, 0], [0, 0, 1]])
        self.assertEqual(r["reais_por_classe"], {"seguro": 3, "suicidio": 2, "odio": 1})
        self.assertEqual(r["previstas_por_classe"], {"seguro": 3, "suicidio": 1, "odio": 2})
        self.assertAlmostEqual(r["metricas"]["recall_suicidio"], 0.5)
        self.assertAlmostEqual(r["metricas"]["precision_suicidio"], 1.0)

    def test_precisao_zero_sem_previsao_x_com_previsao_errada(self):
        """P=R=F1=0 em 'suicidio' vale tanto se o modelo nunca previu a classe
        quanto se previu e errou: só a matriz distingue os dois casos."""
        y_true = np.array([1, 1, 0, 0])
        nunca = av.resumo_avaliacao(y_true, np.array([0, 0, 0, 0]))
        errou = av.resumo_avaliacao(y_true, np.array([0, 0, 1, 0]))
        for r in (nunca, errou):
            self.assertEqual(r["metricas"]["precision_suicidio"], 0.0)
            self.assertEqual(r["metricas"]["recall_suicidio"], 0.0)
        self.assertEqual(nunca["previstas_por_classe"]["suicidio"], 0)
        self.assertEqual(errou["previstas_por_classe"]["suicidio"], 1)

    def test_probabilidades_e_formatacao(self):
        logits = np.array([[3.0, 0, 0], [0, 3.0, 0], [0, 0, 3.0]])
        p = av.softmax(logits)
        self.assertTrue(np.allclose(p.sum(axis=1), 1))
        r = av.resumo_avaliacao([0, 1, 2], logits.argmax(axis=1), p)
        self.assertGreater(r["probabilidade_media_na_classe_real"]["suicidio"], 0.9)
        texto = av.formatar_avaliacao(r)
        self.assertIn("Matriz de confusão", texto)
        self.assertIn("macro F1 = 1.0000", texto)
        json.dumps(r)


if __name__ == "__main__":
    unittest.main()
