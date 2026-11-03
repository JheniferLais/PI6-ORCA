# Dataset de imagens: SFW, NSFW e NSFL

Pipeline, sem servidor e sem modelo, que reúne imagens de fontes públicas, rotula cada uma como `SFW`, `NSFW` ou `NSFL`, descarta as inválidas e repetidas e divide em treino, validação e teste. Serve para **avaliar** o classificador (`python -m vision avaliar`). O modelo `image-safety-classifier-s` já vem pré-treinado, então aqui ele não é treinado: o dataset é a régua para medir o quanto ele acerta no nosso universo.

| Classe | Significado | De onde vem (padrão) |
|---|---|---|
| `SFW` | Seguro para qualquer público | deepghs: pastas `neutral` e `drawing` |
| `NSFW` | Conteúdo sexual explícito | deepghs: pastas `porn` e `hentai` |
| `NSFL` | Conteúdo violento ou chocante (gore) | **só a pasta `manual/NSFL`** (veja "O problema do NSFL") |

## Estrutura

```
fontes.json                 o que baixar e como ligar cada pasta a uma classe
pipeline.py                 o pipeline
README.md
datasets/                   (fora do git) criada ao rodar
├── _downloads/             arquivos baixados das fontes (ficam, para não baixar de novo)
├── manual/                 imagens que o grupo coleta: SFW/  NSFW/  NSFL/   (você cria)
├── imagens/<classe>/<sha1>.<ext>    uma cópia de cada imagem aceita, nomeada pelo conteúdo
├── treino.csv      70%
├── validacao.csv   15%
├── teste.csv       15%
└── resumo.json     contagens por fonte e por divisão, hashes dos CSVs
```

`imagens/` e os CSVs são **refeitos a cada execução** (são dados derivados). `_downloads/` e `manual/` nunca são apagados.

## Colunas dos CSVs

| Coluna | Descrição |
|---|---|
| `arquivo` | Caminho relativo a `imagens/`, ex.: `NSFW/3f2a….jpg` |
| `rotulo` | `SFW`, `NSFW` ou `NSFL` |
| `origem` | Nome da fonte em `fontes.json` |
| `sha1` | Hash do conteúdo (também é o nome do arquivo) |
| `largura`, `altura` | Em pixels |

```python
import csv
with open("datasets/teste.csv", encoding="utf-8", newline="") as f:
    for linha in csv.DictReader(f):
        caminho = f"datasets/imagens/{linha['arquivo']}"
        rotulo = linha["rotulo"]
```

## Como reproduzir

Requer só Python 3 com `pillow`. A partir de `models/`:

```bash
pip install pillow
python -m vision dados                    # ou: python vision/data/pipeline.py
python -m vision dados --inspecionar      # só lista as pastas de cada fonte, sem montar
```

| Opção | Padrão | Descrição |
|---|---|---|
| `--pasta` | `datasets`, ao lado do script | Onde ficam imagens, CSVs e downloads |
| `--fontes` | `fontes.json`, ao lado do script | Arquivo de fontes |
| `--seed` | 42 | Semente do sorteio e da divisão |
| `--max-por-classe` | sem limite | Sorteia no máximo N imagens por classe. Avaliar leva tempo (o modelo faz cerca de 2 s por imagem em CPU, segundo o grupo), então algo como `2000` ajuda |
| `--forcar` | desligado | Baixa de novo, mesmo que o download já exista |
| `--inspecionar` | desligado | Não monta nada: mostra quantas imagens há em cada pasta de cada fonte e a que classe cada uma seria ligada |

Com a mesma semente e as mesmas fontes, os CSVs saem idênticos (os hashes SHA-256 deles ficam em `resumo.json`).

## Como o dataset é montado

1. **Leitura de cada fonte ativa** de `fontes.json`: arquivo `.zip`/`.tar.gz` baixado por URL, repositório do Hugging Face ou pasta local. Só arquivos de imagem (`jpg`, `png`, `webp`, `bmp`, `gif`; `svg` fica de fora) de até 10 MB. Nada é extraído para o disco usando o nome de dentro do arquivo, o que protege contra caminhos como `../../`.
2. **Rótulo pela pasta**: vale a pasta mais próxima do arquivo que estiver no `mapeamento` da fonte. Pastas fora do mapeamento são **ignoradas** (e contadas em `resumo.json`).
3. **Validação**: a imagem precisa abrir, ter formato suportado e passar o mesmo filtro de tamanho do servidor (lado mínimo 100 px, área mínima 10.000 px², proporção até 8:1). Assim o dataset só tem o que o classificador de fato receberia.
4. **Repetidas**: imagens com os mesmos bytes valem uma só.
5. **Conflitos**: a mesma imagem com **classes diferentes** (em fontes diferentes, por exemplo) é descartada por inteiro, porque o rótulo é duvidoso.
6. **Limite por classe** (opcional, `--max-por-classe`), por sorteio reprodutível.
7. **Divisão 70/15/15**, estratificada por classe **e por fonte**, para cada fonte aparecer nas três divisões. Grupos com menos de 3 imagens vão inteiros para o treino (e o pipeline avisa). Como as repetidas saíram antes, nenhuma imagem aparece em mais de uma divisão.

## Dataset gerado

Comando: `python -m vision dados --max-por-classe 500` (seed 42).

| Divisão | SFW | NSFW | NSFL | Total |
|---|---|---|---|---|
| Treino | 350 | 350 | 36 | 736 |
| Validação | 75 | 75 | 8 | 158 |
| Teste | 75 | 75 | 8 | 158 |
| **Total** | **500** | **500** | **52** | **1052** |

Por fonte:
- `deepghs-nsfw-detect`: 16.800 imagens lidas, 16.715 aceitas (84 repetidas e 1 de proporção extrema descartadas). Sorteamos 500 de SFW e 500 de NSFW. A pasta `sexy` (11.200 imagens) ficou de fora de propósito.
- `manual`: 52 imagens de NSFL coletadas e revisadas pelo grupo. [Descreva aqui a origem: de onde vieram e como foram revisadas.]

O modelo é pré-treinado e não é treinado por nós, então o conjunto de teste é o que importa; treino e validação existem por compatibilidade com o pipeline do NLP.

## Relação com `categorias.md`

O modelo de imagem só distingue SFW, NSFW e NSFL:
- **Conteúdo sexual** → `NSFW`.
- **Violência/conteúdo chocante** → `NSFL` (categoria que não está em `categorias.md`).
- **Automutilação, jogos de azar e drogas em imagem não são cobertas** por este modelo.

## Fontes

Todas ficam em `fontes.json`; para trocar o mapeamento ou ligar/desligar uma fonte, edite só esse arquivo.

| Fonte | Estado | O que é | Licença declarada |
|---|---|---|---|
| [`deepghs/nsfw_detect`](https://huggingface.co/datasets/deepghs/nsfw_detect) | **ligada** | Um zip com as pastas `drawing`, `hentai`, `neutral`, `porn` e `sexy`. Entre 10 mil e 100 mil imagens (a página não dá o número exato) | MIT |
| `manual` | **ligada** | Sua pasta `datasets/manual/{SFW,NSFW,NSFL}/` | a de cada imagem |
| [`NeuralShell/Gore-Blood-Dataset-v1.0`](https://huggingface.co/datasets/NeuralShell/Gore-Blood-Dataset-v1.0) | desligada | Menos de 1 mil imagens, marcadas `art`, `blood`, `death` | MIT |
| [Imagenette](https://github.com/fastai/imagenette) (fastai) | desligada | Fotos comuns de 10 classes de objetos, para ter SFW fora do universo de arte | não verificada |

Decisões de mapeamento do deepghs (mude em `fontes.json` se o grupo discordar):

- `sexy` fica **de fora**: é conteúdo sugestivo sem ser explícito, a fronteira entre SFW e NSFW. Rotulá-lo de qualquer jeito contaminaria a avaliação justamente onde o modelo mais erra.
- `hentai` vira NSFW (ilustração explícita), e `drawing` vira SFW (ilustração comum). O card do modelo diz que ele classifica desenhos também.

## O problema do NSFL

É o ponto frágil do dataset, e vale falar claro:

- **Não existe fonte pública confiável de gore pronta para usar.** Uma tese da Universidade de Ottawa sobre censura de gore afirma que precisou criar o dataset por conta própria porque nenhum estava disponível publicamente ([Gore Classification and Censoring in Images](https://ruor.uottawa.ca/handle/10393/42984)).
- O único candidato achado no Hugging Face, `NeuralShell/Gore-Blood-Dataset-v1.0`, **não documenta classes, origem nem contagem**. Rotular tudo como NSFL sem revisar pode misturar ilustração, sangue de filme e outros conteúdos, e o resultado seria um número de "recall NSFL" que parece científico e não é. Por isso ele vem **desligado**.
- O próprio autor do modelo admite que NSFL é a classe **sub-representada** no treino dele.

O que fazer: **curar à mão**. Coloque imagens revisadas em `datasets/manual/NSFL/` (e, se quiser, `manual/SFW/` com screenshots, memes e fotos comuns, e `manual/NSFW/`). A fonte `manual` já vem ligada. Para testar o repositório do NeuralShell: `pip install huggingface_hub`, ligue a fonte em `fontes.json`, rode `python -m vision dados --inspecionar` e **revise as imagens** antes de montar o dataset.

Enquanto não houver exemplos de NSFL, o pipeline avisa e a avaliação mostra a classe como "sem imagens reais", sem inventar número.

## Cuidados

- **Conteúdo explícito e violento.** Não é preciso abrir as imagens para usar o pipeline. Se for revisar, faça com cuidado.
- **Nunca commite as imagens**: `datasets/` está no `.gitignore` de `vision/`.
- **Direitos autorais.** As imagens vêm de coletas na web. A licença da página do dataset vale para a compilação, não necessariamente para cada imagem. Use para avaliação interna e não redistribua.
- **Se encontrar qualquer imagem que envolva menores, apague e não redistribua.** Datasets raspados da web podem ter conteúdo ilegal que o rótulo não revela.

## Pontos de atenção

- **O universo do deepghs é de arte e anime.** O `neutral` é foto comum, mas boa parte do conjunto é ilustração. As páginas que a criança realmente visita têm screenshots, memes e fotos de redes sociais. Resultado bom aqui não garante resultado bom lá, e a pasta `manual` e a fonte Imagenette ajudam a reduzir esse viés.
- **Rótulo pela pasta não é revisão humana.** A pasta `neutral` do deepghs, por exemplo, vem de coleta automática e pode ter ruído.
- **Desbalanceamento.** `porn` tem muito mais imagens que `NSFL`. Leia as métricas por classe (precisão, recall, F1) e não só a acurácia: um modelo que responde sempre `SFW` pode ter acurácia alta.
- **Não foi testado com o download real.** O ambiente em que este pipeline foi escrito não alcançava o Hugging Face, então o download do zip do deepghs e o nome exato das pastas dentro dele (`porn`, `neutral` etc.) vêm da página do dataset e não foram conferidos. Os testes cobrem o pipeline inteiro com imagens sintéticas e arquivos `.zip`/`.tar.gz` locais. Na primeira execução, rode `python -m vision dados --inspecionar` e confirme que cada pasta aparece ligada à classe esperada.
