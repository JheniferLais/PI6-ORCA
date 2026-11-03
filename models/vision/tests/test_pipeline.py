import contextlib
import io
import unittest
from unittest import mock

from vision.classificador import CLASSES
from vision.pipeline import (ConteudoEntrada, ImagemEntrada, PipelineImagens, criar_app,
                             resumir_pagina)
from vision.tests.auxiliar import (AZUL, VERDE, VERMELHO, ClassificadorFalso, ClassificadorQueFalha,
                                   data_uri, imagem_png)

try:
    from fastapi.testclient import TestClient
except Exception:   # httpx não instalado
    TestClient = None


def img(cor=VERDE, semente=0, largura=128, altura=128, src=None):
    """Imagem de entrada com data: URI (sem rede). 'largura/altura' são as DECLARADAS pela extensão."""
    return ImagemEntrada(src=src or data_uri(imagem_png(cor, semente=semente)), width=largura, height=altura)


def pagina(*imagens, url="https://pagina.test/"):
    return ConteudoEntrada(url=url, images=list(imagens))


class TestClassificacao(unittest.TestCase):
    def setUp(self):
        self.modelo = ClassificadorFalso()
        self.pipeline = PipelineImagens(self.modelo)

    def test_cada_imagem_recebe_tres_floats_de_zero_a_um(self):
        r = self.pipeline.processar(pagina(img(VERMELHO, 1), img(AZUL, 2), img(VERDE, 3)))
        self.assertEqual([i["label"] for i in r["images"]], ["NSFW", "NSFL", "SFW"])
        for imagem in r["images"]:
            self.assertEqual(imagem["status"], "classified")
            self.assertEqual(list(imagem["scores"]), list(CLASSES))           # SFW, NSFW, NSFL
            for valor in imagem["scores"].values():
                self.assertIsInstance(valor, float)
                self.assertTrue(0.0 <= valor <= 1.0)
            self.assertAlmostEqual(sum(imagem["scores"].values()), 1.0, places=3)

    def test_uma_unica_chamada_do_modelo_por_pagina(self):
        self.pipeline.processar(pagina(img(VERMELHO, 1), img(AZUL, 2), img(VERDE, 3)))
        self.assertEqual((self.modelo.chamadas, self.modelo.imagens_pontuadas), (1, 3))

    def test_resumo_da_pagina(self):
        r = self.pipeline.processar(pagina(img(VERMELHO, 1), img(VERDE, 2), img(src="https://x.com/a.svg")))
        self.assertEqual(r["summary"]["received"], 3)
        self.assertEqual(r["summary"]["classified"], 2)
        self.assertEqual(r["summary"]["skipped"], 1)
        self.assertEqual(r["summary"]["errors"], 0)

    def test_urls_repetidas_viram_uma_classificacao(self):
        mesma = data_uri(imagem_png(VERMELHO))
        r = self.pipeline.processar(pagina(img(src=mesma), img(VERDE, 5), img(src=mesma)))
        self.assertEqual(self.modelo.imagens_pontuadas, 2)
        self.assertEqual(r["images"][2]["duplicate_of"], 0)
        self.assertEqual(r["images"][2]["label"], "NSFW")
        self.assertNotIn("duplicate_of", r["images"][0])


class TestCaches(unittest.TestCase):
    def setUp(self):
        self.modelo = ClassificadorFalso()
        self.pipeline = PipelineImagens(self.modelo)

    def test_cache_por_url(self):
        conteudo = pagina(img(VERMELHO, 1), img(VERDE, 2))
        primeira = self.pipeline.processar(conteudo)
        segunda = self.pipeline.processar(conteudo)
        self.assertTrue(all(not i["cached"] for i in primeira["images"]))
        self.assertTrue(all(i["cached"] for i in segunda["images"]))
        self.assertEqual(self.modelo.chamadas, 1)                    # a segunda não tocou no modelo
        self.assertEqual(segunda["summary"]["cache_hits"], 2)
        self.assertEqual([i["scores"] for i in segunda["images"]], [i["scores"] for i in primeira["images"]])

    def test_cache_por_conteudo(self):
        dados = imagem_png(AZUL, semente=7)
        self.pipeline.processar(pagina(img(src=data_uri(dados))))
        r = self.pipeline.processar(pagina(img(src=data_uri(dados, "image/x-png"))))   # mesmos bytes, outra URL
        self.assertEqual(self.modelo.imagens_pontuadas, 1)
        self.assertTrue(r["images"][0]["cached"])
        self.assertEqual(r["images"][0]["label"], "NSFL")

    def test_mesmo_conteudo_em_duas_urls_da_mesma_pagina(self):
        dados = imagem_png(VERMELHO, semente=3)
        r = self.pipeline.processar(pagina(img(src=data_uri(dados)), img(src=data_uri(dados, "image/x-png"))))
        self.assertEqual(self.modelo.imagens_pontuadas, 1)
        self.assertEqual([i["label"] for i in r["images"]], ["NSFW", "NSFW"])


class TestFiltrosEErros(unittest.TestCase):
    def setUp(self):
        self.modelo = ClassificadorFalso()
        self.pipeline = PipelineImagens(self.modelo)

    def test_puladas_com_motivo_e_sem_tocar_no_modelo(self):
        r = self.pipeline.processar(pagina(
            img(src="https://x.com/icone.svg"),
            img(largura=50, altura=50),
            img(largura=1600, altura=100),
            img(src="blob:https://x.com/1"),
            img(src="data:text/plain;base64,AAAA"),
        ))
        self.assertEqual([i["reason"] for i in r["images"]],
                         ["svg", "pequena_demais", "proporcao_extrema",
                          "esquema_nao_suportado", "data_uri_nao_e_imagem"])
        self.assertTrue(all(i["status"] == "skipped" for i in r["images"]))
        self.assertEqual(self.modelo.chamadas, 0)

    def test_imagem_invalida_vira_erro_e_nunca_sfw(self):
        lixo = data_uri(b"isso nao e imagem")
        r = self.pipeline.processar(pagina(img(src=lixo), img(VERDE, 1)))
        invalida = r["images"][0]
        self.assertEqual((invalida["status"], invalida["reason"]), ("error", "imagem_invalida"))
        self.assertNotIn("label", invalida)
        self.assertNotIn("scores", invalida)
        self.assertEqual(r["images"][1]["label"], "SFW")                # a outra segue normal

    def test_erro_fica_em_cache_por_um_tempo(self):
        lixo = img(src=data_uri(b"isso nao e imagem"))
        self.pipeline.processar(pagina(lixo))
        r = self.pipeline.processar(pagina(lixo))
        self.assertEqual((r["images"][0]["status"], r["images"][0]["cached"]), ("error", True))

    def test_falha_de_download_vira_erro(self):
        with mock.patch("vision.pipeline.baixar", return_value=(None, "download_falhou:URLError")):
            r = self.pipeline.processar(pagina(img(src="https://site.com/foto.jpg")))
        self.assertEqual((r["images"][0]["status"], r["images"][0]["reason"]), ("error", "download_falhou:URLError"))
        self.assertNotIn("label", r["images"][0])
        self.assertEqual(self.modelo.chamadas, 0)

    def test_limite_de_imagens_novas_por_pagina_fica_com_as_maiores(self):
        pipeline = PipelineImagens(self.modelo, max_imagens_por_pagina=2)
        r = pipeline.processar(pagina(
            img(VERDE, 1, 200, 200), img(VERMELHO, 2, 900, 900),
            img(AZUL, 3, 500, 500), img(VERDE, 4, 150, 150)))
        self.assertEqual([i["status"] for i in r["images"]], ["skipped", "classified", "classified", "skipped"])
        self.assertEqual(r["images"][0]["reason"], "limite_por_pagina")
        self.assertEqual(self.modelo.imagens_pontuadas, 2)

    def test_falha_do_modelo_vira_erro_e_nao_fica_em_cache_de_erro(self):
        modelo = ClassificadorQueFalha()
        pipeline = PipelineImagens(modelo)
        conteudo = pagina(img(VERMELHO, 1))
        for _ in range(2):
            r = pipeline.processar(conteudo)
            self.assertEqual(r["images"][0]["status"], "error")
            self.assertTrue(r["images"][0]["reason"].startswith("falha_no_modelo"))
        self.assertEqual(modelo.chamadas, 2)                            # tentou de novo: a culpa não é da imagem


class TestResumoDaPagina(unittest.TestCase):
    @staticmethod
    def c(label, sfw, nsfw, nsfl):
        return {"status": "classified", "label": label, "scores": {"SFW": sfw, "NSFW": nsfw, "NSFL": nsfl}}

    def test_sem_nada_classificado(self):
        r = resumir_pagina([{"status": "skipped", "reason": "svg"}, {"status": "error", "reason": "x"}])
        self.assertEqual((r["category"], r["score"]), ("indefinido", None))
        self.assertEqual(resumir_pagina([])["score"], None)

    def test_tudo_seguro_vale_a_imagem_menos_confiante(self):
        r = resumir_pagina([self.c("SFW", 0.99, 0.01, 0.0), self.c("SFW", 0.60, 0.40, 0.0)])
        self.assertEqual((r["category"], r["score"]), ("SFW", 0.60))

    def test_uma_imagem_insegura_decide_a_pagina(self):
        r = resumir_pagina([self.c("SFW", 0.99, 0.01, 0.0), self.c("NSFW", 0.05, 0.90, 0.05),
                            self.c("NSFW", 0.20, 0.70, 0.10)])
        self.assertEqual((r["category"], r["score"]), ("NSFW", 0.90))

    def test_entre_inseguras_vence_a_de_maior_probabilidade(self):
        r = resumir_pagina([self.c("NSFW", 0.05, 0.90, 0.05), self.c("NSFL", 0.05, 0.05, 0.95)])
        self.assertEqual((r["category"], r["score"]), ("NSFL", 0.95))

    def test_formato_igual_ao_das_outras_ias(self):
        r = resumir_pagina([self.c("SFW", 0.9, 0.1, 0.0)])
        self.assertEqual(set(r), {"modality", "category", "score", "model_version"})
        self.assertEqual(r["modality"], "img")                          # chave usada em app/decisao.py


class TestCompativelComODecisao(unittest.TestCase):
    """O campo "page" tem que ser aceito por app/decisao.py (motor de políticas) sem adaptador."""

    def test_pagina_insegura_gera_bloqueio_e_pagina_segura_nao_gera_log(self):
        try:
            from app.decisao import combinar
        except ImportError:
            self.skipTest("app/decisao.py não encontrado (rode a partir de models/)")
        insegura = resumir_pagina([TestResumoDaPagina.c("NSFW", 0.05, 0.92, 0.03)])
        segura = resumir_pagina([TestResumoDaPagina.c("SFW", 0.97, 0.02, 0.01)])
        self.assertEqual(combinar(insegura)["level"], "bloqueio")
        self.assertEqual(combinar(insegura)["reason"], "Conteúdo sexual")
        self.assertIsNone(combinar(segura)["level"])
        self.assertEqual(combinar(resumir_pagina([]))["riscos"], {})       # sem imagem: a IA fica de fora


@unittest.skipIf(TestClient is None, "precisa de 'pip install httpx' (TestClient do FastAPI)")
class TestEndpoint(unittest.TestCase):
    def setUp(self):
        self.cliente = TestClient(criar_app(PipelineImagens(ClassificadorFalso())))

    def test_post_content(self):
        corpo = {"url": "https://pagina.test/", "title": "t", "timestamp": "2026-11-02T12:00:00Z",
                 "text": "o texto é ignorado",
                 "images": [{"src": data_uri(imagem_png(VERMELHO)), "alt": "x", "width": 128, "height": 128}]}
        with contextlib.redirect_stdout(io.StringIO()):          # silencia a linha de log do servidor
            resposta = self.cliente.post("/content", json=corpo)
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json()
        self.assertTrue(dados["ok"])
        self.assertEqual(dados["images"][0]["label"], "NSFW")
        self.assertEqual(list(dados["images"][0]["scores"]), ["SFW", "NSFW", "NSFL"])
        self.assertEqual(dados["page"]["category"], "NSFW")

    def test_corpo_invalido(self):
        self.assertEqual(self.cliente.post("/content", json={"url": "https://x.com"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
