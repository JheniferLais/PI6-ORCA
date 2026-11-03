import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from vision import avaliacao as av
from vision.classificador import Pontuacoes
from vision.data import pipeline as dados
from vision.tests.auxiliar import AZUL, VERDE, VERMELHO, ClassificadorFalso, imagem_png


class TestMetricas(unittest.TestCase):
    def test_classificador_perfeito(self):
        y = ["SFW", "SFW", "NSFW", "NSFW", "NSFL", "NSFL"]
        r = av.resumo_avaliacao(y, y)
        self.assertEqual(r["matriz_confusao"], [[2, 0, 0], [0, 2, 0], [0, 0, 2]])
        self.assertEqual((r["acuracia"], r["macro_f1"]), (1.0, 1.0))
        self.assertEqual(r["seguro_x_inseguro"]["recall_inseguro"], 1.0)
        self.assertEqual(r["seguro_x_inseguro"]["taxa_falso_alarme"], 0.0)

    def test_matriz_e_metricas_por_classe(self):
        reais = ["SFW", "SFW", "SFW", "NSFW", "NSFW", "NSFL"]
        previstos = ["SFW", "SFW", "NSFW", "SFW", "NSFW", "NSFL"]
        r = av.resumo_avaliacao(reais, previstos)
        self.assertEqual(r["matriz_confusao"], [[2, 1, 0], [1, 1, 0], [0, 0, 1]])
        sfw, nsfw = r["por_classe"]["SFW"], r["por_classe"]["NSFW"]
        self.assertAlmostEqual(sfw["precisao"], 2 / 3)
        self.assertAlmostEqual(sfw["recall"], 2 / 3)
        self.assertAlmostEqual(nsfw["precisao"], 1 / 2)
        self.assertEqual((nsfw["reais"], nsfw["previstas"]), (2, 2))
        self.assertAlmostEqual(r["acuracia"], 4 / 6)

    def test_seguro_x_inseguro(self):
        reais = ["SFW"] * 4 + ["NSFW", "NSFW", "NSFL", "NSFL"]
        previstos = ["SFW", "SFW", "SFW", "NSFW",      # 1 falso alarme em 4 SFW
                     "NSFW", "SFW", "NSFW", "NSFL"]    # 3 de 4 inseguras pegas (NSFL previsto NSFW conta como pega)
        s = av.resumo_avaliacao(reais, previstos)["seguro_x_inseguro"]
        self.assertAlmostEqual(s["recall_inseguro"], 3 / 4)
        self.assertAlmostEqual(s["taxa_falso_alarme"], 1 / 4)
        self.assertAlmostEqual(s["precisao_inseguro"], 3 / 4)       # 4 marcadas como inseguras, 3 de fato eram
        self.assertEqual((s["inseguras_reais"], s["inseguras_pegas"], s["sfw_reais"]), (4, 3, 4))

    def test_classe_sem_exemplos_nao_entra_no_macro_f1(self):
        reais = ["SFW", "SFW", "NSFW", "NSFW"]
        r = av.resumo_avaliacao(reais, reais)
        nsfl = r["por_classe"]["NSFL"]
        self.assertEqual((nsfl["reais"], nsfl["recall"], nsfl["f1"], nsfl["precisao"]), (0, None, None, None))
        self.assertEqual(r["macro_f1"], 1.0)                         # média só de SFW e NSFW

    def test_classe_sem_exemplos_mas_prevista_tem_precisao_zero(self):
        r = av.resumo_avaliacao(["SFW", "SFW"], ["SFW", "NSFL"])
        self.assertEqual(r["por_classe"]["NSFL"]["precisao"], 0.0)
        self.assertIsNone(r["por_classe"]["NSFL"]["f1"])

    def test_zero_na_classe_real_e_nao_previsto_difere_na_matriz(self):
        nunca = av.resumo_avaliacao(["NSFW", "NSFW", "SFW"], ["SFW", "SFW", "SFW"])
        errou = av.resumo_avaliacao(["NSFW", "NSFW", "SFW"], ["SFW", "SFW", "NSFW"])
        for r in (nunca, errou):
            self.assertEqual(r["por_classe"]["NSFW"]["f1"], 0.0)
        self.assertEqual(nunca["por_classe"]["NSFW"]["previstas"], 0)
        self.assertEqual(errou["por_classe"]["NSFW"]["previstas"], 1)

    def test_probabilidade_media_na_classe_real(self):
        pontuacoes = [Pontuacoes(0.9, 0.1, 0.0), Pontuacoes(0.7, 0.3, 0.0), Pontuacoes(0.2, 0.8, 0.0)]
        r = av.resumo_avaliacao(["SFW", "SFW", "NSFW"], ["SFW", "SFW", "NSFW"], pontuacoes)
        self.assertAlmostEqual(r["probabilidade_media_na_classe_real"]["SFW"], 0.8)
        self.assertAlmostEqual(r["probabilidade_media_na_classe_real"]["NSFW"], 0.8)
        self.assertIsNone(r["probabilidade_media_na_classe_real"]["NSFL"])

    def test_formatacao_e_json(self):
        r = av.resumo_avaliacao(["SFW", "NSFW"], ["SFW", "NSFW"])
        texto = av.formatar_avaliacao(r)
        self.assertIn("Matriz de confusão", texto)
        self.assertIn("sem imagens reais desta classe", texto)       # NSFL vazio
        self.assertIn("macro F1 = 1.0000", texto)
        json.dumps(r)


class TestAmostra(unittest.TestCase):
    LINHAS = ([{"rotulo": "SFW", "arquivo": f"SFW/{i}"} for i in range(80)]
              + [{"rotulo": "NSFW", "arquivo": f"NSFW/{i}"} for i in range(15)]
              + [{"rotulo": "NSFL", "arquivo": f"NSFL/{i}"} for i in range(5)])

    def test_respeita_o_limite_e_mantem_todas_as_classes(self):
        amostra = av.amostra_estratificada(self.LINHAS, 20)
        classes = {l["rotulo"] for l in amostra}
        self.assertEqual(classes, {"SFW", "NSFW", "NSFL"})
        self.assertLessEqual(len(amostra), 22)                        # arredondamento por classe

    def test_reprodutivel(self):
        self.assertEqual(av.amostra_estratificada(self.LINHAS, 20, 1), av.amostra_estratificada(self.LINHAS, 20, 1))

    def test_limite_maior_que_o_total_devolve_tudo(self):
        self.assertEqual(len(av.amostra_estratificada(self.LINHAS, 1000)), 100)


class TestAvaliarDeVerdade(unittest.TestCase):
    """Do dataset em disco até o JSON, com o classificador falso."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = Path(self._tmp.name) / "datasets"
        self.n = 0

    def criar(self, classe_da_pasta, cor, quantas):
        pasta = self.pasta / "manual" / classe_da_pasta
        pasta.mkdir(parents=True, exist_ok=True)
        for _ in range(quantas):
            self.n += 1
            (pasta / f"{self.n}.png").write_bytes(imagem_png(cor, semente=self.n))

    def montar(self):
        fonte = {"nome": "manual", "tipo": "pasta_local", "caminho": "manual",
                 "mapeamento": {"sfw": "SFW", "nsfw": "NSFW", "nsfl": "NSFL"}}
        with contextlib.redirect_stdout(io.StringIO()):
            dados.montar_dataset([fonte], self.pasta)

    def avaliar(self, **kw):
        with contextlib.redirect_stdout(io.StringIO()):
            return av.avaliar("teste", self.pasta, classificador=ClassificadorFalso(), **kw)

    def test_classificador_perfeito_de_ponta_a_ponta(self):
        self.criar("SFW", VERDE, 20), self.criar("NSFW", VERMELHO, 20), self.criar("NSFL", AZUL, 20)
        self.montar()
        r = self.avaliar()
        self.assertEqual(r["macro_f1"], 1.0)
        self.assertEqual(r["imagens"], 9)
        gravado = json.loads((self.pasta / "avaliacao-teste.json").read_text(encoding="utf-8"))
        self.assertEqual(gravado["matriz_confusao"], r["matriz_confusao"])
        self.assertEqual(gravado["versao"], "vision-v1")

    def test_erros_aparecem_na_matriz(self):
        self.criar("SFW", VERDE, 20)
        self.criar("NSFW", VERDE, 20)        # rotuladas NSFW, mas o modelo falso vê imagens verdes: SFW
        self.montar()
        r = self.avaliar()
        self.assertEqual(r["matriz_confusao"][1], [3, 0, 0])          # as 3 NSFW do teste caíram em SFW
        self.assertEqual(r["seguro_x_inseguro"]["recall_inseguro"], 0.0)
        self.assertEqual(r["por_classe"]["NSFW"]["f1"], 0.0)

    def test_classe_sem_exemplos_nao_quebra(self):
        self.criar("SFW", VERDE, 20), self.criar("NSFW", VERMELHO, 20)
        self.montar()
        r = self.avaliar()
        self.assertEqual(r["por_classe"]["NSFL"]["reais"], 0)
        self.assertEqual(r["macro_f1"], 1.0)

    def test_limite_nao_grava_arquivo(self):
        self.criar("SFW", VERDE, 40), self.criar("NSFW", VERMELHO, 40)
        self.montar()
        r = self.avaliar(limite=4)
        self.assertLessEqual(r["imagens"], 6)
        self.assertFalse((self.pasta / "avaliacao-teste.json").exists())

    def test_imagem_ilegivel_e_contada_e_ignorada(self):
        self.criar("SFW", VERDE, 20), self.criar("NSFW", VERMELHO, 20)
        self.montar()
        primeira = av.ler_divisao(self.pasta, "teste")[0]
        (self.pasta / "imagens" / primeira["arquivo"]).write_bytes(b"corrompida")
        r = self.avaliar()
        self.assertEqual(r["ilegiveis"], 1)
        self.assertEqual(r["imagens"], 5)

    def test_erros_de_uso(self):
        with self.assertRaises(FileNotFoundError):
            av.avaliar("teste", self.pasta, classificador=ClassificadorFalso())
        with self.assertRaises(ValueError):
            av.avaliar("outra", self.pasta, classificador=ClassificadorFalso())


if __name__ == "__main__":
    unittest.main()
