import unittest

from nlp import normalizacao as norm


class TestNormalizacao(unittest.TestCase):
    def test_remove_user_e_links(self):
        t = "  @user @USER olha https://t.co/abc123 e www.x.com/a   fim\n\n"
        self.assertEqual(norm.normalizar(t), "olha e fim")

    def test_preserva_caixa_e_acentos(self):
        self.assertEqual(norm.normalizar("Não ODEIO você"), "Não ODEIO você")

    def test_nfc(self):
        self.assertEqual(norm.normalizar("é"), "é")

    def test_outras_mencoes_nao_sao_alteradas(self):
        self.assertEqual(norm.normalizar("oi @maria"), "oi @maria")

    def test_none_e_vazio(self):
        self.assertEqual(norm.normalizar(None), "")
        self.assertEqual(norm.normalizar("@user https://t.co/x"), "")

    def test_chave_ignora_caixa(self):
        self.assertEqual(norm.chave_comparacao("Olá  MUNDO @user"), "olá mundo")


if __name__ == "__main__":
    unittest.main()
