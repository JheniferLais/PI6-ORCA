"""Configuração e pasta de saída do treino (não precisam de torch)."""
import tempfile
import unittest
from pathlib import Path

from nlp import treino as tr


class TestConfig(unittest.TestCase):
    def test_config_padrao(self):
        c = tr.carregar_config()
        self.assertEqual(c["versao"], "nlp-v1")
        self.assertRegex(c["modelo_base"]["revision"], r"^[0-9a-f]{40}$")  # hash exato, não "main"
        self.assertEqual(c["hiperparametros"]["num_train_epochs"], 3)

    def test_teste_rapido_reduz_epocas(self):
        self.assertEqual(tr.carregar_config(teste_rapido=True)["hiperparametros"]["num_train_epochs"], 1)


class TestDestino(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.config = {"versao": "nlp-v1"}
        for nome in ("nlp-v1", "nlp-v1-teste"):
            (self.base / nome).mkdir()
            (self.base / nome / "x.txt").write_text("x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_oficial_recusa_sobrescrever(self):
        with self.assertRaises(FileExistsError):
            tr.preparar_destino(self.config, teste_rapido=False, base=self.base)
        self.assertTrue((self.base / "nlp-v1" / "x.txt").exists())

    def test_forcar_arquiva_e_nao_apaga(self):
        destino = tr.preparar_destino(self.config, teste_rapido=False, forcar=True, base=self.base)
        self.assertFalse(any(destino.iterdir()))
        arquivadas = list(self.base.glob("nlp-v1.anterior-*"))
        self.assertEqual(len(arquivadas), 1)
        self.assertTrue((arquivadas[0] / "x.txt").exists())

    def test_teste_rapido_so_recria_a_propria_pasta(self):
        destino = tr.preparar_destino(self.config, teste_rapido=True, base=self.base)
        self.assertEqual(destino.name, "nlp-v1-teste")
        self.assertFalse((destino / "x.txt").exists())
        self.assertTrue((self.base / "nlp-v1" / "x.txt").exists())


if __name__ == "__main__":
    unittest.main()
