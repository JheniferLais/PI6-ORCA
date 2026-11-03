import contextlib
import csv
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from vision.data import pipeline as pd_
from vision.tests.auxiliar import AZUL, VERDE, VERMELHO, imagem_png

COR = {"SFW": VERDE, "NSFW": VERMELHO, "NSFL": AZUL}


def ler_csv(caminho):
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        self.pasta = self.raiz / "datasets"
        self.contador = 0

    def nova(self, cor, **kw):
        """Bytes de uma imagem inédita (a semente muda a cada chamada)."""
        self.contador += 1
        return imagem_png(cor, semente=self.contador, **kw)

    def manual(self, por_classe, pasta=None):
        """Cria <pasta>/manual/<CLASSE>/<n>.png com 'n' imagens inéditas por classe."""
        base = Path(pasta or self.pasta) / "manual"
        for classe, n in por_classe.items():
            (base / classe).mkdir(parents=True, exist_ok=True)
            for i in range(n):
                (base / classe / f"{i}.png").write_bytes(self.nova(COR[classe]))

    @staticmethod
    def fonte_manual():
        return {"nome": "manual", "tipo": "pasta_local", "caminho": "manual",
                "mapeamento": {"sfw": "SFW", "nsfw": "NSFW", "nsfl": "NSFL"}}

    def montar(self, fontes=None, **kw):
        with contextlib.redirect_stdout(io.StringIO()):          # silencia o relatório do pipeline
            return pd_.montar_dataset(fontes or [self.fonte_manual()], self.pasta, **kw)


class TestRotulos(unittest.TestCase):
    MAPA = {"porn": "NSFW", "neutral": "SFW"}

    def test_pasta_mais_proxima_vale(self):
        self.assertEqual(pd_.rotulo_da_pasta("ds/porn/a.jpg", self.MAPA), "NSFW")
        self.assertEqual(pd_.rotulo_da_pasta("neutral/sub/porn/a.jpg", self.MAPA), "NSFW")
        self.assertEqual(pd_.rotulo_da_pasta("porn/sub/neutral/a.jpg", self.MAPA), "SFW")

    def test_ignora_caixa_e_barras_do_windows(self):
        self.assertEqual(pd_.rotulo_da_pasta("DS\\Neutral\\a.jpg", self.MAPA), "SFW")

    def test_sem_pasta_conhecida(self):
        self.assertIsNone(pd_.rotulo_da_pasta("ds/sexy/a.jpg", self.MAPA))
        self.assertIsNone(pd_.rotulo_da_pasta("a.jpg", self.MAPA))

    def test_curinga(self):
        mapa = {"*": "SFW", "porn": "NSFW"}
        self.assertEqual(pd_.rotulo_da_pasta("qualquer/coisa/a.jpg", mapa), "SFW")
        self.assertEqual(pd_.rotulo_da_pasta("x/porn/a.jpg", mapa), "NSFW")

    def test_a_pasta_nao_inclui_o_nome_do_arquivo(self):
        self.assertIsNone(pd_.rotulo_da_pasta("ds/porn.jpg", self.MAPA))


class TestFontes(Base):
    def _carregar(self, fonte):
        caminho = self.raiz / "fontes.json"
        caminho.write_text(json.dumps({"fontes": [fonte]}), encoding="utf-8")
        return pd_.carregar_fontes(caminho)

    def test_fontes_json_do_repositorio_e_valido(self):
        fontes = pd_.carregar_fontes()
        self.assertTrue(any(f["ativa"] for f in fontes))
        for f in fontes:
            self.assertTrue(set(f["mapeamento"].values()) <= {"SFW", "NSFW", "NSFL"})

    def test_normaliza_pastas_para_minusculas(self):
        f = self._carregar({"nome": "x", "tipo": "pasta_local", "mapeamento": {"Porn": "NSFW"}})
        self.assertEqual(f[0]["mapeamento"], {"porn": "NSFW"})

    def test_rejeita_tipo_e_classe_invalidos(self):
        with self.assertRaises(ValueError):
            self._carregar({"nome": "x", "tipo": "ftp", "mapeamento": {"a": "SFW"}})
        with self.assertRaises(ValueError):
            self._carregar({"nome": "x", "tipo": "pasta_local", "mapeamento": {"a": "GORE"}})
        with self.assertRaises(ValueError):
            self._carregar({"nome": "x", "tipo": "pasta_local"})


class TestMontagem(Base):
    def test_estrutura_gerada(self):
        self.manual({"SFW": 20, "NSFW": 20, "NSFL": 20})
        resumo = self.montar()
        self.assertEqual(resumo["total"], 60)
        for nome in ("treino", "validacao", "teste"):
            linhas = ler_csv(self.pasta / f"{nome}.csv")
            self.assertEqual(list(linhas[0]), pd_.COLUNAS)
            for linha in linhas:
                arquivo = self.pasta / "imagens" / linha["arquivo"]
                self.assertTrue(arquivo.is_file())
                self.assertTrue(linha["arquivo"].startswith(linha["rotulo"] + "/"))
                self.assertEqual(hashlib.sha1(arquivo.read_bytes()).hexdigest(), linha["sha1"])
        self.assertEqual(json.loads((self.pasta / "resumo.json").read_text())["total"], 60)

    def test_divisao_70_15_15_estratificada_e_sem_vazamento(self):
        self.manual({"SFW": 100, "NSFW": 40, "NSFL": 20})
        resumo = self.montar()
        self.assertEqual(resumo["por_divisao"]["treino"], {"total": 112, "SFW": 70, "NSFW": 28, "NSFL": 14})
        self.assertEqual(resumo["por_divisao"]["validacao"], {"total": 24, "SFW": 15, "NSFW": 6, "NSFL": 3})
        self.assertEqual(resumo["por_divisao"]["teste"], {"total": 24, "SFW": 15, "NSFW": 6, "NSFL": 3})
        shas = [{l["sha1"] for l in ler_csv(self.pasta / f"{n}.csv")} for n in ("treino", "validacao", "teste")]
        self.assertFalse(shas[0] & shas[1] or shas[0] & shas[2] or shas[1] & shas[2])
        self.assertEqual(sum(len(s) for s in shas), 160)

    def test_reprodutivel_com_a_mesma_seed(self):
        self.manual({"SFW": 30, "NSFW": 30})
        a = self.montar(seed=7)
        segunda = Path(self._tmp.name) / "segunda"
        for classe in ("SFW", "NSFW"):
            (segunda / "manual" / classe).mkdir(parents=True)
            for arquivo in (self.pasta / "manual" / classe).iterdir():
                (segunda / "manual" / classe / arquivo.name).write_bytes(arquivo.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()):
            b = pd_.montar_dataset([self.fonte_manual()], segunda, seed=7)
        self.assertEqual(a["sha256_dos_csvs"], b["sha256_dos_csvs"])

    def test_refaz_a_pasta_de_imagens(self):
        self.manual({"SFW": 5})
        velho = self.pasta / "imagens" / "SFW" / "velho.png"
        velho.parent.mkdir(parents=True)
        velho.write_bytes(b"x")
        self.montar()
        self.assertFalse(velho.exists())

    def test_estrato_pequeno_vai_inteiro_para_o_treino(self):
        self.manual({"SFW": 20, "NSFL": 2})
        resumo = self.montar()
        self.assertEqual(resumo["por_divisao"]["treino"]["NSFL"], 2)
        self.assertNotIn("NSFL", resumo["por_divisao"]["teste"])

    def test_limite_por_classe(self):
        self.manual({"SFW": 30, "NSFW": 30, "NSFL": 3})
        resumo = self.montar(max_por_classe=10)
        self.assertEqual(resumo["removidas_pelo_limite_por_classe"], {"SFW": 20, "NSFW": 20})
        linhas = sum((ler_csv(self.pasta / f"{n}.csv") for n in ("treino", "validacao", "teste")), [])
        self.assertEqual(len(linhas), 23)
        self.assertEqual(len(list((self.pasta / "imagens").rglob("*.png"))), 23)   # sem sobras no disco

    def test_sem_imagens_levanta_erro_claro(self):
        with self.assertRaisesRegex(RuntimeError, "nenhuma imagem"):
            self.montar()

    def test_fonte_desligada_e_pasta_ausente_sao_puladas(self):
        self.manual({"SFW": 5})
        desligada = {**self.fonte_manual(), "nome": "off", "ativa": False}
        sem_pasta = {**self.fonte_manual(), "nome": "sem-pasta", "caminho": "nao-existe"}
        resumo = self.montar([self.fonte_manual(), desligada, sem_pasta])
        self.assertEqual(resumo["total"], 5)
        self.assertNotIn("off", resumo["por_fonte"])
        self.assertEqual(resumo["por_fonte"]["sem-pasta"], {})


class TestValidacaoDasImagens(Base):
    def test_invalidas_pequenas_e_repetidas(self):
        base = self.pasta / "manual" / "SFW"
        base.mkdir(parents=True)
        boa = self.nova(VERDE)
        (base / "boa.png").write_bytes(boa)
        (base / "copia.png").write_bytes(boa)                                   # mesmos bytes
        (base / "quebrada.png").write_bytes(b"nao sou uma imagem")
        (base / "pequena.png").write_bytes(self.nova(VERDE, tamanho=(50, 50)))
        (base / "banner.png").write_bytes(self.nova(VERDE, tamanho=(1600, 100)))
        (base / "icone.svg").write_text("<svg/>")                                # extensão não suportada
        (base / "notas.txt").write_text("oi")
        resumo = self.montar()
        est = resumo["por_fonte"]["manual"]
        self.assertEqual(resumo["total"], 1)
        self.assertEqual((est["aceitas"], est["repetidas"], est["invalidas"]), (1, 1, 1))
        self.assertEqual((est["pequena_demais"], est["proporcao_extrema"]), (1, 1))
        self.assertEqual(est["lidas"], 5)                                        # svg e txt nem foram lidos

    def test_mesma_imagem_com_classes_diferentes_e_descartada(self):
        (self.pasta / "manual" / "SFW").mkdir(parents=True)
        (self.pasta / "manual" / "NSFW").mkdir(parents=True)
        duvidosa = self.nova(VERDE)
        (self.pasta / "manual" / "SFW" / "a.png").write_bytes(duvidosa)
        (self.pasta / "manual" / "NSFW" / "a.png").write_bytes(duvidosa)
        (self.pasta / "manual" / "SFW" / "ok.png").write_bytes(self.nova(VERDE))
        resumo = self.montar()
        self.assertEqual(resumo["total"], 1)
        self.assertEqual(resumo["conflitos_de_rotulo_descartados"], 1)
        self.assertEqual(len(list((self.pasta / "imagens").rglob("*.png"))), 1)  # a primeira cópia saiu do disco


class TestArquivosComprimidos(Base):
    def _zip(self, membros, nome="fonte.zip"):
        caminho = self.raiz / nome
        with zipfile.ZipFile(caminho, "w") as z:
            for membro, dados in membros.items():
                z.writestr(membro, dados)
        return caminho

    def _fonte(self, caminho, mapeamento, nome="remota"):
        return {"nome": nome, "tipo": "arquivo_url", "url": caminho.as_uri(), "arquivo": caminho.name,
                "mapeamento": mapeamento}

    def test_zip_com_pastas_e_pasta_ignorada(self):
        caminho = self._zip({
            "ds/porn/1.png": self.nova(VERMELHO), "ds/porn/2.png": self.nova(VERMELHO),
            "ds/neutral/3.png": self.nova(VERDE), "ds/sexy/4.png": self.nova(VERMELHO),
            "ds/LEIAME.txt": b"oi",
        })
        resumo = self.montar([self._fonte(caminho, {"porn": "NSFW", "neutral": "SFW"})])
        est = resumo["por_fonte"]["remota"]
        self.assertEqual((est["aceitas"], est["ignoradas_sem_classe"]), (3, 1))
        self.assertTrue((self.pasta / "_downloads" / "fonte.zip").exists())

    def test_zip_com_caminho_malicioso_nao_escreve_fora_da_pasta(self):
        caminho = self._zip({"../../fora/porn/evil.png": self.nova(VERMELHO)})
        resumo = self.montar([self._fonte(caminho, {"porn": "NSFW"})])
        self.assertEqual(resumo["total"], 1)
        self.assertFalse((self.raiz / "fora").exists())
        self.assertFalse((self.pasta.parent / "fora").exists())
        arquivo = next((self.pasta / "imagens").rglob("*.png"))
        self.assertTrue(str(arquivo.resolve()).startswith(str(self.pasta.resolve())))

    def test_tar_gz_com_curinga(self):
        caminho = self.raiz / "fonte.tgz"
        with tarfile.open(caminho, "w:gz") as t:
            for i in range(3):
                dados = self.nova(VERDE)
                info = tarfile.TarInfo(f"fotos/classe{i}/{i}.png")
                info.size = len(dados)
                t.addfile(info, io.BytesIO(dados))
        resumo = self.montar([self._fonte(caminho, {"*": "SFW"})])
        self.assertEqual(resumo["por_divisao"]["treino"]["total"] + resumo["por_divisao"]["validacao"]["total"]
                         + resumo["por_divisao"]["teste"]["total"], 3)

    def test_fonte_com_erro_nao_derruba_as_outras(self):
        self.manual({"SFW": 5})
        quebrada = {"nome": "quebrada", "tipo": "arquivo_url", "url": (self.raiz / "nao-existe.zip").as_uri(),
                    "arquivo": "nao-existe.zip", "mapeamento": {"*": "SFW"}}
        corrompida = self.raiz / "ruim.zip"
        corrompida.write_bytes(b"isso nao e um zip")
        resumo = self.montar([quebrada, self._fonte(corrompida, {"*": "SFW"}, "corrompida"), self.fonte_manual()])
        self.assertEqual(resumo["total"], 5)
        self.assertEqual(resumo["por_fonte"]["quebrada"]["fonte_com_erro"], 1)
        self.assertEqual(resumo["por_fonte"]["corrompida"]["fonte_com_erro"], 1)

    def test_formato_de_arquivo_nao_suportado(self):
        self.manual({"SFW": 3})
        rar = self.raiz / "fonte.rar"
        rar.write_bytes(b"x")
        resumo = self.montar([self._fonte(rar, {"*": "SFW"}), self.fonte_manual()])
        self.assertEqual(resumo["por_fonte"]["remota"]["fonte_com_erro"], 1)
        self.assertEqual(resumo["total"], 3)


class TestCLI(Base):
    def test_inspecionar_lista_pastas_e_mapeamento(self):
        caminho = self.raiz / "f.zip"
        with zipfile.ZipFile(caminho, "w") as z:
            z.writestr("ds/porn/1.png", self.nova(VERMELHO))
            z.writestr("ds/sexy/2.png", self.nova(VERMELHO))
        fonte = {"nome": "f", "tipo": "arquivo_url", "url": caminho.as_uri(), "arquivo": "f.zip",
                 "mapeamento": {"porn": "NSFW"}}
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            pd_.inspecionar([fonte], self.pasta)
        texto = saida.getvalue()
        self.assertIn("porn", texto)
        self.assertIn("NSFW", texto)
        self.assertIn("IGNORADA", texto)
        self.assertFalse((self.pasta / "imagens").exists())          # não monta nada


if __name__ == "__main__":
    unittest.main()
