# Classificador de texto (NLP)

Classifica textos em português em três classes: `seguro`, `suicidio` e `odio`.
Modelo: BERTimbau Base (`neuralmind/bert-base-portuguese-cased`) com fine-tuning.
Resultado do `nlp-v1` na validação: **macro F1 0,7995**, acurácia 0,8956
(detalhes, decisões e limitações em [`docs/nlp-v1-treinamento.md`](../../docs/nlp-v1-treinamento.md)).

## Estrutura

```
nlp/
├── data/
│   ├── pipeline.py        baixa Boamente e TuPyE e gera treino/validação/teste (70/15/15)
│   ├── README.md          origem, rótulos e montagem do dataset
│   └── datasets/          CSVs gerados (fora do git)
├── config/nlp-v1.json     um experimento: modelo base (revisão fixa), hiperparâmetros, pesos
├── normalizacao.py        limpeza do texto, idêntica no treino e na inferência
├── dados.py               leitura dos CSVs, colisões entre divisões, pesos de classe
├── treino.py              fine-tuning (Trainer com perda ponderada por classe)
├── avaliacao.py           métricas, matriz de confusão, avaliação do modelo salvo
├── inferencia.py          Classificador: carrega o modelo e classifica (usado pelo server.py)
├── __main__.py            linha de comando: python -m nlp ...
├── artifacts/nlp-v1/      modelo treinado + orca_model.json (registro do experimento)
└── tests/                 testes unitários e de ponta a ponta (BERT minúsculo, sem download)
```

O fluxo é linear: `data/pipeline.py` → `dados.py` → `treino.py` → `avaliacao.py`;
`inferencia.py` e `normalizacao.py` são tudo o que o servidor precisa.

## Como usar

Tudo roda a partir de `models/`, com o ambiente de `models/requirements.txt` ativo.

```bash
python nlp/data/pipeline.py                # 1. gera os datasets (baixa as fontes)
python -m nlp dados                        # 2. confere CSVs, colisões e pesos de classe
python -m nlp treinar --teste-rapido       # 3. valida o fluxo em minutos (não é resultado)
python -m nlp treinar                      # 4. treino completo (~8 h em CPU)
python -m nlp avaliar                      # 5. avalia o modelo salvo na validação
python -m nlp avaliar --divisao teste      # 6. avaliação final, uma única vez, no teste
python -m unittest discover -s nlp/tests -t .   # testes
```

- Para um novo experimento, copie `config/nlp-v1.json` para `config/nlp-v2.json`, mude
  `versao` e o que for testar, e passe `--config nlp/config/nlp-v2.json`.
- O treino nunca sobrescreve um modelo: `--forcar` arquiva a pasta anterior.
- `avaliar` grava o resultado em `artifacts/<versao>/avaliacao-<divisao>.json`.

## Modelo treinado

Os pesos (`artifacts/nlp-v1/model.safetensors`, ~436 MB) não vão para o git. Coloque o
arquivo nessa pasta (ou treine de novo). Para confirmar que é o modelo certo, rode
`python -m nlp avaliar`: a matriz de confusão deve ser igual à de `orca_model.json`.

Os datasets também não vão para o git: `data/pipeline.py` os regenera, e os hashes
SHA-256 em `orca_model.json` confirmam que são os mesmos usados no treino.

## Uso no servidor

```python
from nlp.inferencia import Classificador
clf = Classificador("nlp/artifacts/nlp-v1")
clf.classificar_longo("texto de uma página")   # {'category': 'odio', 'score': 0.97}
```

`classificar_longo` divide textos longos em janelas de 128 tokens e devolve a janela mais
grave, então conteúdo no fim de uma página também é analisado.
