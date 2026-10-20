# Dataset multiclasse: seguro, suicídio e ódio

Dataset de textos curtos em português para classificação em três classes, criado a partir da união de dois datasets binários: **Boamente** (ideação suicida) e **TuPyE** (discurso de ódio).

| Classe | Significado | De onde vem |
|---|---|---|
| `seguro` | Texto sem ideação suicida e sem ódio | Boamente (`label` = 0) e TuPyE (`aggressive` = 0 e `hate` = 0) |
| `suicidio` | Texto com ideação suicida | Boamente (`label` = 1) |
| `odio` | Texto com discurso de ódio | TuPyE (`hate` = 1) |

## Estrutura

```
pipeline.py
README.md
datasets/
├── boamente.csv              original
├── tupye_binary_vote.csv     original
├── dataset_multiclasse.csv   os dois unidos, com rótulos em one-hot
├── treino.csv                70%
├── validacao.csv             15%
└── teste.csv                 15%
```

Todos os CSVs ficam na pasta `datasets`. `pipeline.py` cria a pasta, baixa os dois datasets originais e gera os outros quatro arquivos a partir deles.

| Arquivo | Textos | % | seguro | suicidio | odio |
|---|---|---|---|---|---|
| `dataset_multiclasse.csv` | 40.178 | 100% | 34.231 | 747 | 5.200 |
| `treino.csv` | 28.124 | 70% | 23.961 | 523 | 3.640 |
| `validacao.csv` | 6.027 | 15% | 5.135 | 112 | 780 |
| `teste.csv` | 6.027 | 15% | 5.135 | 112 | 780 |

## Colunas

| Coluna | Tipo | Descrição |
|---|---|---|
| `text` | texto | O texto da postagem |
| `seguro` | 0 ou 1 | 1 se o texto é da classe seguro |
| `suicidio` | 0 ou 1 | 1 se o texto é da classe suicídio |
| `odio` | 0 ou 1 | 1 se o texto é da classe ódio |
| `origem` | texto | Dataset de onde o texto veio: `boamente` ou `tupye` |

Os rótulos estão em one-hot encoding: cada linha tem exatamente um 1 entre as três colunas de classe. A coluna `origem` não é rótulo e não deve entrar como entrada do modelo.

## Como o dataset foi montado

1. **Mapeamento dos rótulos**, conforme a tabela do início.
2. **Descarte dos agressivos sem ódio.** O TuPyE tem 6.020 textos com `aggressive` = 1 e `hate` = 0 (xingamentos e ofensas que não chegam a ser discurso de ódio). Eles não entram em nenhuma classe, porque rotulá-los como seguro contaminaria essa classe.
3. **Remoção de rótulos conflitantes.** 30 textos apareciam com rótulos diferentes (63 linhas) e foram descartados.
4. **Remoção de duplicados.** 1.184 textos repetidos foram removidos, mantendo a primeira ocorrência. A maioria era do Boamente, por isso a classe suicídio caiu de 1.090 para 747. A comparação ignora maiúsculas e espaços extras.
5. **One-hot encoding** das três classes.
6. **Embaralhamento** das linhas com semente 42.

O texto em si não foi alterado, só teve os espaços do início e do fim removidos.

## Divisão em treino, validação e teste

A divisão é 70/15/15, com semente 42, e é estratificada por classe e por dataset de origem. Assim, os três arquivos mantêm a mesma proporção de classes do dataset completo (85,2% seguro, 1,9% suicídio, 12,9% ódio) e a mesma mistura de fontes. Como os duplicados foram removidos antes, nenhum texto aparece em mais de um arquivo.

## Como reproduzir

Requer Python 3 com `pandas` e `scikit-learn` (rode a partir de `models/`):

```bash
pip install pandas scikit-learn
python nlp/data/pipeline.py
```

O script baixa `boamente.csv` e `tupye_binary_vote.csv` das fontes originais para a pasta `datasets`, confere as colunas e o número de linhas e depois gera o dataset e as divisões na mesma pasta. Se os dois CSVs já estiverem lá, o download é pulado.

A pasta `datasets` é criada ao lado do script, não importa de onde ele seja executado. Para usar outra pasta:

```bash
python nlp/data/pipeline.py --pasta caminho/da/pasta
```

| Opção | Padrão | Descrição |
|---|---|---|
| `--pasta` | `datasets`, ao lado do script | Pasta onde ficam os seis CSVs |
| `--seed` | 42 | Semente do embaralhamento e da divisão |
| `--forcar` | desligado | Baixa os dois CSVs de novo, mesmo que já existam |
| `--url-boamente`, `--url-tupye` | endereços das fontes | Endereços de download, caso as fontes mudem de lugar |

Com a semente padrão, o script gera arquivos idênticos aos descritos aqui (testado com pandas 3.0.5 e scikit-learn 1.9.1). Outras versões podem embaralhar em ordem diferente.

## Como carregar

```python
import pandas as pd

CLASSES = ["seguro", "suicidio", "odio"]

treino = pd.read_csv("datasets/treino.csv")
X = treino["text"]
y = treino[CLASSES].values          # one-hot, formato (n, 3)
y_indice = y.argmax(axis=1)         # 0 = seguro, 1 = suicidio, 2 = odio
```

## Pontos de atenção

- **Desbalanceamento forte.** Suicídio é 1,9% dos textos. Vale usar pesos de classe ou reamostragem no treino e avaliar por F1 de cada classe, não por acurácia: um modelo que responde sempre "seguro" acerta 85%.
- **Poucos exemplos de suicídio na avaliação.** São 112 na validação e 112 no teste, então as métricas dessa classe oscilam bastante entre experimentos.
- **Classe e fonte se confundem.** Toda a classe suicídio vem do Boamente e toda a classe ódio vem do TuPyE. Os dois têm estilos diferentes: o TuPyE tem `@user` em cerca de 39% dos textos e o Boamente não tem menções. O modelo pode aprender a reconhecer a fonte em vez do conteúdo. Normalizar o texto (minúsculas, remover `@user` e links) reduz esse risco.
- **O "seguro" do Boamente é difícil de propósito.** São textos que usam expressões como "acabar com a minha vida" em sentido figurado, o que ajuda o modelo a não se apoiar só em palavras-chave.
- **Conteúdo sensível.** O dataset contém ofensas, discurso de ódio e relatos de ideação suicida.

## Fontes

- **Boamente**: tweets em português coletados em maio de 2021 e rotulados por três psicólogos quanto à ideação suicida (3.777 textos: 2.687 negativos e 1.090 positivos). Publicado no Zenodo como "Dataset of suicidal ideation texts in Brazilian Portuguese - Boamente System", versão 3, de janeiro de 2026, DOI [10.5281/zenodo.18343886](https://zenodo.org/records/18343886), licença CC BY 4.0. O arquivo original se chama `Boamente_Atualizado_Janeiro_2026.csv` e é salvo aqui como `boamente.csv`.
- **TuPyE**: 43.668 postagens do Twitter e do Instagram rotuladas quanto a agressividade e ódio, reunindo os conjuntos de Fortuna et al. (2019), Leite et al. (2020), Vargas et al. (2021) e Oliveira et al. (2023). Publicado no Hugging Face como [Silly-Machine/TuPyE-Dataset](https://huggingface.co/datasets/Silly-Machine/TuPyE-Dataset), licença CC BY 4.0. O arquivo usado é o `binary/tupye_binary_vote.csv`.

As duas licenças exigem atribuição: ao publicar ou redistribuir este dataset, cite as duas fontes e os artigos indicados nas páginas delas.