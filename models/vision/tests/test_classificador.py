import unittest

from vision.classificador import CLASSES, Pontuacoes, pontuacoes_a_partir_de


class TestOrdemDasClasses(unittest.TestCase):
    """O requisito central: sempre 3 floats, na ordem SFW, NSFW, NSFL, qualquer que seja a ordem do modelo."""

    def test_ordem_do_card_do_modelo(self):
        p = pontuacoes_a_partir_de(["NSFW", "NSFL", "SFW"], [0.2, 0.1, 0.7])
        self.assertEqual(p.como_tupla(), (0.7, 0.2, 0.1))

    def test_ordem_do_exemplo_onnx(self):
        p = pontuacoes_a_partir_de(["NSFL", "NSFW", "SFW"], [0.1, 0.2, 0.7])
        self.assertEqual(p.como_tupla(), (0.7, 0.2, 0.1))

    def test_ignora_caixa_e_espacos(self):
        p = pontuacoes_a_partir_de([" sfw", "Nsfw", "nsfl "], [0.5, 0.3, 0.2])
        self.assertEqual(p.como_tupla(), (0.5, 0.3, 0.2))

    def test_dict_tem_as_tres_chaves_na_ordem(self):
        p = Pontuacoes(0.1, 0.2, 0.7)
        self.assertEqual(list(p.como_dict()), list(CLASSES))
        self.assertEqual(p.como_dict(), {"SFW": 0.1, "NSFW": 0.2, "NSFL": 0.7})


class TestValidacao(unittest.TestCase):
    def test_rotulo_faltando(self):
        with self.assertRaises(ValueError):
            pontuacoes_a_partir_de(["SFW", "NSFW"], [0.5, 0.5])

    def test_rotulo_desconhecido(self):
        with self.assertRaises(ValueError):
            pontuacoes_a_partir_de(["SFW", "NSFW", "GORE"], [0.5, 0.3, 0.2])

    def test_rotulo_repetido(self):
        with self.assertRaises(ValueError):
            pontuacoes_a_partir_de(["SFW", "sfw", "NSFL"], [0.5, 0.3, 0.2])

    def test_tamanhos_diferentes(self):
        with self.assertRaises(ValueError):
            pontuacoes_a_partir_de(["SFW", "NSFW", "NSFL"], [0.5, 0.5])

    def test_soma_diferente_de_um(self):
        with self.assertRaises(ValueError):
            pontuacoes_a_partir_de(["SFW", "NSFW", "NSFL"], [0.5, 0.5, 0.5])

    def test_fora_de_zero_a_um_e_nan(self):
        for ruim in ([1.5, -0.3, -0.2], [float("nan"), 0.5, 0.5]):
            with self.assertRaises(ValueError):
                pontuacoes_a_partir_de(["SFW", "NSFW", "NSFL"], ruim)

    def test_erro_de_arredondamento_do_float32_e_corrigido(self):
        p = pontuacoes_a_partir_de(["SFW", "NSFW", "NSFL"], [1.0000001, -0.0000001, 0.0])
        self.assertEqual(p.como_tupla(), (1.0, 0.0, 0.0))


class TestCategoria(unittest.TestCase):
    def test_maior_probabilidade(self):
        self.assertEqual(Pontuacoes(0.1, 0.8, 0.1).categoria, "NSFW")
        self.assertEqual(Pontuacoes(0.9, 0.05, 0.05).categoria, "SFW")
        self.assertEqual(Pontuacoes(0.1, 0.1, 0.8).categoria, "NSFL")

    def test_empate_vence_a_classe_mais_grave(self):
        self.assertEqual(Pontuacoes(0.5, 0.5, 0.0).categoria, "NSFW")
        self.assertEqual(Pontuacoes(0.0, 0.5, 0.5).categoria, "NSFL")
        self.assertEqual(Pontuacoes(1 / 3, 1 / 3, 1 / 3).categoria, "NSFL")


if __name__ == "__main__":
    unittest.main()
