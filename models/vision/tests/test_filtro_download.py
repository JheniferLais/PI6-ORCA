import unittest
from unittest import mock

from PIL import Image

from vision import download
from vision.filtro import motivo_rejeicao, rejeitar_por_tamanho
from vision.tests.auxiliar import data_uri, imagem_png


class TestFiltro(unittest.TestCase):
    def test_aceita_imagem_normal(self):
        self.assertIsNone(motivo_rejeicao("https://site.com/foto.jpg", 800, 600))
        self.assertIsNone(motivo_rejeicao("data:image/png;base64,AAAA", 300, 300))

    def test_motivos(self):
        casos = [
            ("https://site.com/icone.svg", 800, 600, "svg"),
            ("https://site.com/icone.SVG?v=2", 800, 600, "svg"),
            ("data:image/svg+xml;base64,AAAA", 800, 600, "svg"),
            ("data:text/plain;base64,AAAA", 800, 600, "data_uri_nao_e_imagem"),
            ("blob:https://site.com/123", 800, 600, "esquema_nao_suportado"),
            ("file:///etc/passwd", 800, 600, "esquema_nao_suportado"),
            ("https://site.com/p.png", 99, 800, "pequena_demais"),
            ("https://site.com/p.png", 120, 80, "pequena_demais"),      # lado < 100
            ("https://site.com/b.png", 1600, 100, "proporcao_extrema"),
        ]
        for src, largura, altura, esperado in casos:
            with self.subTest(src=src, tamanho=(largura, altura)):
                self.assertEqual(motivo_rejeicao(src, largura, altura), esperado)

    def test_limites_exatos(self):
        self.assertIsNone(rejeitar_por_tamanho(100, 100))              # 100 px e 10.000 px²: passa
        self.assertEqual(rejeitar_por_tamanho(100, 99), "pequena_demais")
        self.assertIsNone(rejeitar_por_tamanho(800, 100))              # proporção 8: passa
        self.assertEqual(rejeitar_por_tamanho(801, 100), "proporcao_extrema")


class TestDownload(unittest.TestCase):
    def test_data_uri_base64(self):
        dados = imagem_png()
        self.assertEqual(download.baixar(data_uri(dados)), (dados, None))

    def test_data_uri_sem_base64(self):
        dados, erro = download.baixar("data:image/svg+xml,%3Csvg%3E%3C/svg%3E")
        self.assertEqual((dados, erro), (b"<svg></svg>", None))

    def test_arquivo_grande_demais_vira_erro_e_nao_excecao(self):
        with mock.patch.object(download, "MAX_BYTES", 10):
            dados, erro = download.baixar(data_uri(b"x" * 50))
        self.assertIsNone(dados)
        self.assertEqual(erro, "download_falhou:ValueError")

    def test_falha_de_rede_vira_erro(self):
        with mock.patch.object(download, "urlopen", side_effect=OSError("sem rede")):
            self.assertEqual(download.baixar("https://site.com/a.png"), (None, "download_falhou:OSError"))

    def test_abrir_imagem_devolve_rgb(self):
        imagem = download.abrir_imagem(imagem_png())
        self.assertEqual(imagem.mode, "RGB")

    def test_transparencia_vira_fundo_branco(self):
        import io
        transparente = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        saida = io.BytesIO()
        transparente.save(saida, format="PNG")
        self.assertEqual(download.abrir_imagem(saida.getvalue()).getpixel((5, 5)), (255, 255, 255))

    def test_bytes_que_nao_sao_imagem(self):
        with self.assertRaises(Exception):
            download.abrir_imagem(b"isso nao e uma imagem")


if __name__ == "__main__":
    unittest.main()
