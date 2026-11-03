"""
Monta o dataset de imagens (SFW, NSFW, NSFL) usado para AVALIAR o classificador.
Sem servidor e sem modelo: só baixa, rotula, valida, remove repetidas e divide.

    python vision/data/pipeline.py           (a partir de models/)
    python -m vision dados                   (mesma coisa)
    python -m vision dados --inspecionar     (só mostra as pastas de cada fonte, não grava nada)

Resultado, em vision/data/datasets/:
    imagens/<SFW|NSFW|NSFL>/<sha1>.<ext>    uma cópia de cada imagem, nomeada pelo conteúdo
    treino.csv  validacao.csv  teste.csv    70% / 15% / 15%, estratificados por classe e fonte
    resumo.json                             contagens por fonte e por divisão, hashes dos CSVs

As fontes e o mapeamento pasta -> classe ficam em fontes.json.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import random
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Dict, Iterator, List, Optional, Tuple

if not __package__:
    # executado como arquivo (python vision/data/pipeline.py): torna o pacote importável
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PIL import Image

from vision.classificador import CLASSES
from vision.download import MAX_BYTES
from vision.filtro import rejeitar_por_tamanho

PASTA_DATASETS = Path(__file__).resolve().parent / "datasets"
ARQUIVO_FONTES = Path(__file__).resolve().parent / "fontes.json"

EXTENSOES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}      # svg fica de fora
EXTENSAO_DO_FORMATO = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "GIF": ".gif"}
TIPOS_DE_FONTE = {"arquivo_url", "pasta_local", "hf_repo"}
FRACAO_VALIDACAO = FRACAO_TESTE = 0.15                               # o resto (70%) é treino
COLUNAS = ["arquivo", "rotulo", "origem", "sha1", "largura", "altura"]

DadoDeImagem = Tuple[str, bytes]   # (nome dentro da fonte, bytes)


# ---------------------------------------------------------------- fontes

def carregar_fontes(caminho: Path = ARQUIVO_FONTES) -> List[dict]:
    """Lê e valida o fontes.json. Os nomes de pasta do mapeamento ficam em minúsculas."""
    fontes = json.loads(Path(caminho).read_text(encoding="utf-8"))["fontes"]
    for fonte in fontes:
        nome = fonte.get("nome", "?")
        if fonte.get("tipo") not in TIPOS_DE_FONTE:
            raise ValueError(f"fonte {nome}: 'tipo' deve ser um de {sorted(TIPOS_DE_FONTE)}")
        mapeamento = fonte.get("mapeamento")
        if not mapeamento:
            raise ValueError(f"fonte {nome}: falta o 'mapeamento' pasta -> classe")
        invalidas = sorted(set(mapeamento.values()) - set(CLASSES))
        if invalidas:
            raise ValueError(f"fonte {nome}: classes inválidas {invalidas}; use {list(CLASSES)}")
        fonte["mapeamento"] = {pasta.lower(): classe for pasta, classe in mapeamento.items()}
    return fontes


def rotulo_da_pasta(nome: str, mapeamento: Dict[str, str]) -> Optional[str]:
    """Classe de uma imagem pelo nome do arquivo na fonte: vale a pasta mais próxima que
    estiver no mapeamento; senão '*' (se houver); senão None (a imagem é ignorada)."""
    pastas = [p.lower() for p in PurePosixPath(nome.replace("\\", "/")).parts[:-1]]
    for pasta in reversed(pastas):
        if pasta in mapeamento:
            return mapeamento[pasta]
    return mapeamento.get("*")


def baixar_arquivo(url: str, destino: Path, forcar: bool = False) -> Path:
    """Baixa 'url' para 'destino', a menos que ele já exista. Levanta RuntimeError se falhar."""
    destino = Path(destino)
    if destino.exists() and not forcar:
        print(f"  {destino.name}: já existe, download pulado")
        return destino
    print(f"  {destino.name}: baixando de {url}")
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (orca vision/data)"})
    try:
        with urllib.request.urlopen(pedido, timeout=120) as resposta, open(parcial, "wb") as f:
            shutil.copyfileobj(resposta, f)
    except Exception as erro:
        parcial.unlink(missing_ok=True)
        raise RuntimeError(f"não consegui baixar {url}: {erro}. Baixe à mão e salve como {destino.resolve()}") from erro
    parcial.replace(destino)
    print(f"  {destino.name}: salvo ({destino.stat().st_size / 1_048_576:.1f} MB)")
    return destino


def _e_imagem(nome: str) -> bool:
    return PurePosixPath(nome.replace("\\", "/")).suffix.lower() in EXTENSOES


def ler_arquivo_comprimido(caminho: Path) -> Iterator[DadoDeImagem]:
    """Imagens de um .zip ou .tar/.tar.gz/.tgz. O NOME do membro só serve para achar a
    pasta/classe: nada é extraído para o disco com ele (protege contra '../' malicioso)."""
    nome = Path(caminho).name.lower()
    if nome.endswith(".zip"):
        with zipfile.ZipFile(caminho) as arquivo:
            for info in arquivo.infolist():
                if info.is_dir() or not _e_imagem(info.filename):
                    continue
                with arquivo.open(info) as f:
                    dados = f.read(MAX_BYTES + 1)
                if len(dados) <= MAX_BYTES:
                    yield info.filename, dados
    elif nome.endswith((".tar", ".tar.gz", ".tgz")):
        with tarfile.open(caminho, "r:*") as arquivo:
            for membro in arquivo:
                if not membro.isfile() or not _e_imagem(membro.name):
                    continue
                dados = arquivo.extractfile(membro).read(MAX_BYTES + 1)
                if len(dados) <= MAX_BYTES:
                    yield membro.name, dados
    else:
        raise RuntimeError(f"formato de arquivo não suportado: {nome} (use .zip, .tar, .tar.gz ou .tgz)")


def ler_pasta(raiz: Path) -> Iterator[DadoDeImagem]:
    """Imagens de uma pasta (recursivo, sem seguir links simbólicos), em ordem estável."""
    raiz = Path(raiz)
    for atual, subpastas, arquivos in os.walk(raiz, followlinks=False):
        subpastas.sort()
        for arquivo in sorted(arquivos):
            caminho = Path(atual) / arquivo
            if caminho.is_symlink() or not _e_imagem(arquivo) or caminho.stat().st_size > MAX_BYTES:
                continue
            yield caminho.relative_to(raiz).as_posix(), caminho.read_bytes()


def iterar_fonte(fonte: dict, pasta: Path, forcar: bool = False) -> Iterator[DadoDeImagem]:
    """Imagens da fonte (baixando o que precisar para pasta/_downloads)."""
    tipo = fonte["tipo"]
    if tipo == "arquivo_url":
        arquivo = baixar_arquivo(fonte["url"], pasta / "_downloads" / fonte["arquivo"], forcar)
        yield from ler_arquivo_comprimido(arquivo)
    elif tipo == "hf_repo":
        try:
            from huggingface_hub import snapshot_download
        except ImportError as erro:
            raise RuntimeError("esta fonte precisa de 'pip install huggingface_hub'") from erro
        destino = pasta / "_downloads" / fonte["nome"]
        print(f"  {fonte['repo_id']}: baixando do Hugging Face para {destino}")
        snapshot_download(repo_id=fonte["repo_id"], repo_type="dataset", local_dir=str(destino))
        yield from ler_pasta(destino)
    else:  # pasta_local
        raiz = Path(fonte["caminho"])
        raiz = raiz if raiz.is_absolute() else pasta / raiz
        if not raiz.is_dir():
            print(f"  pasta {raiz} não existe: fonte pulada")
            return
        yield from ler_pasta(raiz)


# ---------------------------------------------------------------- validação e coleta

def inspecionar_imagem(dados: bytes) -> Tuple[int, int, str]:
    """(largura, altura, extensão) de uma imagem válida; ValueError se corrompida ou de formato não suportado."""
    try:
        with Image.open(io.BytesIO(dados)) as imagem:
            formato, (largura, altura) = imagem.format, imagem.size
            imagem.verify()
    except Exception as erro:
        raise ValueError(f"imagem inválida: {erro}") from erro
    if formato not in EXTENSAO_DO_FORMATO:
        raise ValueError(f"formato não suportado: {formato}")
    return largura, altura, EXTENSAO_DO_FORMATO[formato]


class Coletor:
    """Recebe imagens já rotuladas, valida, tira repetidas e grava em imagens/<classe>/<sha1>.<ext>.

    Duas imagens com os mesmos bytes valem uma só. Se aparecem com classes DIFERENTES
    (ex.: a mesma foto em duas fontes), as duas cópias são descartadas: o rótulo é duvidoso."""

    def __init__(self, pasta_imagens: Path):
        self.pasta_imagens = Path(pasta_imagens)
        self.registros: Dict[str, dict] = {}     # sha1 -> linha do CSV
        self.conflitos: set = set()

    def adicionar(self, rotulo: str, origem: str, dados: bytes, estatisticas: Counter) -> None:
        estatisticas["lidas"] += 1
        sha1 = hashlib.sha1(dados).hexdigest()
        if sha1 in self.conflitos:
            estatisticas["conflitos_de_rotulo"] += 1
            return
        existente = self.registros.get(sha1)
        if existente:
            if existente["rotulo"] == rotulo:
                estatisticas["repetidas"] += 1
            else:
                (self.pasta_imagens / existente["arquivo"]).unlink(missing_ok=True)
                del self.registros[sha1]
                self.conflitos.add(sha1)
                estatisticas["conflitos_de_rotulo"] += 1
            return
        try:
            largura, altura, extensao = inspecionar_imagem(dados)
        except ValueError:
            estatisticas["invalidas"] += 1
            return
        motivo = rejeitar_por_tamanho(largura, altura)
        if motivo:
            estatisticas[motivo] += 1
            return
        arquivo = f"{rotulo}/{sha1}{extensao}"
        destino = self.pasta_imagens / arquivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
        self.registros[sha1] = {"arquivo": arquivo, "rotulo": rotulo, "origem": origem,
                                "sha1": sha1, "largura": largura, "altura": altura}
        estatisticas["aceitas"] += 1

    def remover(self, sha1: str) -> None:
        linha = self.registros.pop(sha1)
        (self.pasta_imagens / linha["arquivo"]).unlink(missing_ok=True)


def limitar_por_classe(coletor: Coletor, maximo: int, seed: int) -> Dict[str, int]:
    """Mantém no máximo 'maximo' imagens por classe (sorteio reprodutível); devolve quantas removeu."""
    removidas: Dict[str, int] = {}
    for rotulo in CLASSES:
        shas = sorted(s for s, r in coletor.registros.items() if r["rotulo"] == rotulo)
        if len(shas) <= maximo:
            continue
        manter = set(random.Random(f"{seed}-{rotulo}").sample(shas, maximo))
        for sha1 in shas:
            if sha1 not in manter:
                coletor.remover(sha1)
        removidas[rotulo] = len(shas) - maximo
    return removidas


# ---------------------------------------------------------------- divisão

def dividir(registros: Dict[str, dict], seed: int) -> Dict[str, List[dict]]:
    """70/15/15, estratificado por (classe, fonte): cada fonte contribui em todas as divisões.

    Estratos com menos de 3 imagens vão inteiros para o treino (não dá para dividir)."""
    estratos: Dict[tuple, List[str]] = defaultdict(list)
    for sha1, linha in registros.items():
        estratos[(linha["rotulo"], linha["origem"])].append(sha1)

    divisoes: Dict[str, List[dict]] = {"treino": [], "validacao": [], "teste": []}
    for (rotulo, origem), shas in sorted(estratos.items()):
        shas.sort()
        random.Random(f"{seed}-{rotulo}-{origem}").shuffle(shas)
        n = len(shas)
        if n < 3:
            print(f"  AVISO: {rotulo}/{origem} tem só {n} imagem(ns): tudo vai para o treino")
            n_validacao = n_teste = 0
        else:
            n_validacao = max(1, round(n * FRACAO_VALIDACAO))
            n_teste = max(1, round(n * FRACAO_TESTE))
        n_treino = n - n_validacao - n_teste
        divisoes["treino"] += [registros[s] for s in shas[:n_treino]]
        divisoes["validacao"] += [registros[s] for s in shas[n_treino:n_treino + n_validacao]]
        divisoes["teste"] += [registros[s] for s in shas[n_treino + n_validacao:]]
    return divisoes


def gravar_csv(caminho: Path, linhas: List[dict]) -> str:
    """Grava o CSV (sempre com \\n, igual em Windows e Linux) e devolve o SHA-256 dele."""
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows({c: linha[c] for c in COLUNAS} for linha in linhas)
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


# ---------------------------------------------------------------- montagem

def montar_dataset(fontes: List[dict], pasta: Path, seed: int = 42,
                   max_por_classe: Optional[int] = None, forcar: bool = False) -> dict:
    """Roda tudo e devolve o resumo (o mesmo que vai para resumo.json).

    A pasta 'imagens' e os CSVs são REFEITOS a cada execução: são dados derivados.
    Já os downloads (pasta/_downloads) e a pasta/manual são preservados."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    pasta_imagens = pasta / "imagens"
    if pasta_imagens.exists():
        shutil.rmtree(pasta_imagens)

    coletor = Coletor(pasta_imagens)
    por_fonte: Dict[str, dict] = {}
    for fonte in fontes:
        if not fonte.get("ativa", True):
            print(f"[{fonte['nome']}] desligada em fontes.json")
            continue
        print(f"[{fonte['nome']}]")
        estatisticas: Counter = Counter()
        try:
            for nome, dados in iterar_fonte(fonte, pasta, forcar):
                rotulo = rotulo_da_pasta(nome, fonte["mapeamento"])
                if rotulo is None:
                    estatisticas["ignoradas_sem_classe"] += 1
                else:
                    coletor.adicionar(rotulo, fonte["nome"], dados, estatisticas)
        except (RuntimeError, OSError, zipfile.BadZipFile, tarfile.TarError) as erro:
            print(f"  AVISO: fonte pulada: {erro}")
            estatisticas["fonte_com_erro"] = 1
        por_fonte[fonte["nome"]] = dict(estatisticas)
        print("  " + (", ".join(f"{k}={v}" for k, v in sorted(estatisticas.items())) or "nada lido"))

    removidas = limitar_por_classe(coletor, max_por_classe, seed) if max_por_classe else {}
    if not coletor.registros:
        raise RuntimeError("nenhuma imagem foi coletada: confira as fontes em fontes.json "
                           "ou coloque imagens em datasets/manual/<SFW|NSFW|NSFL>/")

    divisoes = dividir(coletor.registros, seed)
    hashes = {nome: gravar_csv(pasta / f"{nome}.csv", linhas) for nome, linhas in divisoes.items()}

    contagem = {nome: dict(Counter(linha["rotulo"] for linha in linhas)) for nome, linhas in divisoes.items()}
    resumo = {
        "seed": seed,
        "max_por_classe": max_por_classe,
        "classes": list(CLASSES),
        "total": len(coletor.registros),
        "por_divisao": {nome: {"total": len(linhas), **contagem[nome]} for nome, linhas in divisoes.items()},
        "por_fonte": por_fonte,
        "conflitos_de_rotulo_descartados": len(coletor.conflitos),
        "removidas_pelo_limite_por_classe": removidas,
        "sha256_dos_csvs": hashes,
    }
    (pasta / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return resumo


def inspecionar(fontes: List[dict], pasta: Path, forcar: bool = False) -> None:
    """Mostra, por fonte, quantas imagens há em cada pasta e a que classe cada uma seria
    ligada. Não grava nada além dos downloads. Serve para conferir o mapeamento."""
    for fonte in fontes:
        if not fonte.get("ativa", True):
            print(f"[{fonte['nome']}] desligada em fontes.json (ligue para inspecionar)")
            continue
        print(f"[{fonte['nome']}]")
        por_pasta: Counter = Counter()
        try:
            for nome, _ in iterar_fonte(fonte, pasta, forcar):
                partes = PurePosixPath(nome.replace("\\", "/")).parts[:-1]
                por_pasta[partes[-1] if partes else "(raiz)"] += 1
        except (RuntimeError, OSError, zipfile.BadZipFile, tarfile.TarError) as erro:
            print(f"  AVISO: fonte pulada: {erro}")
            continue
        for nome_pasta, n in sorted(por_pasta.items()):
            rotulo = rotulo_da_pasta(f"{nome_pasta}/x.jpg", fonte["mapeamento"])
            print(f"  {nome_pasta:<30}{n:>8} imagens  ->  {rotulo or 'IGNORADA'}")


def imprimir_resumo(resumo: dict) -> None:
    print(f"\nDataset pronto: {resumo['total']} imagens (seed {resumo['seed']})")
    print(f"{'':<12}" + "".join(f"{c:>10}" for c in (*CLASSES, "total")))
    for nome, linha in resumo["por_divisao"].items():
        print(f"{nome:<12}" + "".join(f"{linha.get(c, 0):>10}" for c in CLASSES) + f"{linha['total']:>10}")
    sem_exemplos = [c for c in CLASSES if not any(l.get(c) for l in resumo["por_divisao"].values())]
    for classe in sem_exemplos:
        print(f"AVISO: nenhuma imagem de {classe}. A avaliação dessa classe ficará vazia: "
              f"coloque imagens revisadas em datasets/manual/{classe}/ ou ligue uma fonte em fontes.json.")


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--pasta", default=PASTA_DATASETS,
                   help='onde ficam imagens, CSVs e downloads; padrão: "datasets" ao lado do script')
    p.add_argument("--fontes", default=ARQUIVO_FONTES, help="arquivo de fontes; padrão: fontes.json ao lado do script")
    p.add_argument("--seed", type=int, default=42, help="semente do sorteio e da divisão")
    p.add_argument("--max-por-classe", type=int, default=None,
                   help="sorteia no máximo N imagens por classe (avaliar leva tempo; ex.: 2000)")
    p.add_argument("--forcar", action="store_true", help="baixa de novo, mesmo que o download já exista")
    p.add_argument("--inspecionar", action="store_true",
                   help="só lista as pastas de cada fonte e o mapeamento; não monta o dataset")
    args = p.parse_args(argv)

    try:
        fontes = carregar_fontes(args.fontes)
        if args.inspecionar:
            inspecionar(fontes, Path(args.pasta), args.forcar)
        else:
            imprimir_resumo(montar_dataset(fontes, Path(args.pasta), args.seed, args.max_por_classe, args.forcar))
    except (ValueError, RuntimeError, FileNotFoundError, KeyError) as erro:
        sys.exit(f"ERRO: {erro}")


if __name__ == "__main__":
    main()
