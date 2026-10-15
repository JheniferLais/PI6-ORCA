# Treinamento do classificador de texto — nlp-v1 (S2-03, RF003)

Issue #26: escolher o modelo base e treinar a primeira versão do classificador de texto.

> **Status:** pipeline implementado, testado e executado. O download do modelo base e o treino oficial
> foram feitos em 15/10/2026 (resultados na seção 6). A avaliação no conjunto de teste não faz parte do S2-03.

## 1. Modelo base

| Item | Valor |
|---|---|
| Modelo | BERTimbau Base, `neuralmind/bert-base-portuguese-cased` |
| Finalidade | Encoder BERT em português do Brasil, usado aqui com cabeça de classificação de sequência (3 classes) |
| Revisão | Hash exato do commit (40 caracteres), gravado em `artifacts/modelo-base.json` por `treino.py baixar` e repetido em `orca_model.json` |

Justificativa: textos em português; textos curtos (p99 de cerca de 54 palavras no treino, medido);
cerca de 110 milhões de parâmetros, viável em CPU; compatível com `transformers`. O BERTimbau Large
foi descartado por ser lento demais para CPU. A normalização preserva maiúsculas e minúsculas
porque o modelo é *cased*.

## 2. Dados (origem: S2-02)

Arquivos de `models/nlp/data/datasets/`, gerados por `models/nlp/data/pipeline.py`
(ver `models/nlp/data/README.md`): `treino.csv`, `validacao.csv` e `teste.csv`.

- Colunas usadas: `text` e as três colunas one-hot `seguro`, `suicidio`, `odio`. A coluna `origem` não é usada.
- Rótulos (ordem de `CLASSES` em `pipeline.py`): 0 = `seguro`, 1 = `suicidio`, 2 = `odio`.
  `seguro` significa apenas "sem ideação suicida e sem ódio"; o dataset não cobre as demais
  categorias de `categorias.md` (apostas, conteúdo sexual, drogas).
- Os CSVs nunca são alterados pelo treino. O teste só é lido para detectar colisões e **não
  participa do treino nem da seleção do modelo**.
- O hash SHA-256 de cada arquivo é gravado em `orca_model.json`. `sha256_lf` ignora a diferença
  CRLF/LF entre Windows e Linux.

### Normalização (`normalizacao.py`, versão `norm-v1`)

Unicode NFC; remove links (`http://`, `https://`, `www.`); remove `@user`; colapsa espaços e quebras
de linha. Maiúsculas e minúsculas são preservadas (diferença em relação à sugestão do README de
S2-02, que menciona minúsculas). Outras menções (`@fulano`) não são alteradas: no dataset só existe
`@user`. A mesma função deve ser usada na inferência. Não se reutiliza `cleaning.py`, que é feito
para páginas inteiras (descarta textos com menos de 40 caracteres, remove linhas repetidas e trunca
em 20.000 caracteres).

### Colisões entre divisões após a normalização

Depois da normalização, textos que eram diferentes nos CSVs (por exemplo, só por `@user` ou por um
link) podem ficar iguais em divisões diferentes. Tratamento aplicado, sempre em memória:

1. Chave de comparação: texto normalizado, sem diferenciar maiúsculas.
2. **Teste:** nunca é alterado.
3. **Validação:** perde as linhas que colidem com o teste.
4. **Treino:** perde as linhas que colidem com a validação ou com o teste, e as que ficam vazias.
5. Duplicados dentro de uma mesma divisão são só contados, não removidos.
6. Toda linha removida é listada em `colisoes_removidas.csv` (divisão, índice da linha, classe,
   motivo) e as contagens vão para `orca_model.json`.

Medido com os CSVs enviados (`python treino.py dados`; treino 28.124, validação 6.027, teste 6.027 linhas):

| Item | Resultado |
|---|---|
| Textos presentes em mais de uma divisão | 33 (1 com rótulo divergente) |
| Removidos do treino | 34 (31 `seguro`, 3 `odio`, 0 `suicidio`): 19 colidem com o teste, 13 com a validação, 2 com ambos |
| Removidos da validação | 2 (`seguro`), por colidirem com o teste |
| Removidos do teste | 0 |
| Linhas efetivas | treino 28.090, validação 6.025, teste 6.027 |
| Duplicados internos (apenas contados) | treino 50, validação 2, teste 2 |
| Vazios após normalizar | 0 |

Se os seus CSVs forem diferentes (outra versão de pandas ou das fontes), confira os hashes e rode
`python treino.py dados` para obter as contagens da sua máquina.

## 3. Hiperparâmetros (configurados)

Fonte única: `models/nlp/config/nlp-v1.json`. O treino confere se o `Trainer` aplicou exatamente
esses valores e grava os valores efetivos em `orca_model.json`.

| Hiperparâmetro | Valor configurado |
|---|---|
| Taxa de aprendizado | 2e-5 |
| Épocas | 3 (padrão; `--epocas N` altera) |
| Batch de treino / avaliação | 16 / 32 |
| Otimizador | `adamw_torch`, weight decay 0,01 |
| Warmup / scheduler | 10% dos passos / decaimento linear |
| Corte de gradiente | 1,0 |
| Seed | 42 |
| Precisão | FP32 (`fp16` e `bf16` desligados) |
| Comprimento máximo | 128 tokens (truncamento) |
| Seleção do melhor modelo | maior **macro F1 na validação**, avaliada ao fim de cada época |

Os valores são os usuais para fine-tuning de BERT-base e foram escolhidos como ponto de partida; não
foram ajustados nem comparados com alternativas.

### Pesos de classe

Entropia cruzada ponderada, `w_c = N / (K * n_c)` (N = exemplos do treino efetivo, K = 3, n_c =
exemplos da classe), calculada a partir dos rótulos do treino efetivo e gravada em `orca_model.json`.
Com os CSVs enviados e após o tratamento de colisões: `seguro` 0,3913 (n=23.930), `suicidio` 17,9031
(n=523), `odio` 2,5745 (n=3.637). Esses números são só o cálculo; **o peso alto de `suicidio` não
garante melhor desempenho**: pode aumentar o recall e reduzir a precisão da classe, e isso só se
sabe depois do treino e da avaliação. Para comparar, `pesos_classe.metodo = "nenhum"` desliga os pesos.

## 4. Como executar

Pré-requisito: Python 3.12 instalado ao lado do 3.14. Os comandos são em PowerShell e **dependem da
pasta atual**: o bloco 1 roda na **raiz do repositório** (`PI6-ORCA`) e o bloco 2 roda dentro de
`models\nlp`. Não cole os dois seguidos em outra pasta: criar o venv de dentro de `models\nlp` com o
caminho `models\nlp\.venv-treino` cria um venv duplicado em `models\nlp\models\nlp`.

Bloco 1: ambiente (uma vez só, na raiz do repositório):

```powershell
cd <raiz-do-repositório>
py -3.12 -m venv models\nlp\.venv-treino
models\nlp\.venv-treino\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r models\nlp\requirements-treino.txt
```

Bloco 2: uso (venv ativo, dentro de `models\nlp`):

```powershell
cd <raiz-do-repositório>\models\nlp
python -m unittest test_nlp test_torch -v    # testes (test_torch usa um BERT minúsculo, sem download)
python data\pipeline.py                      # só se data\datasets ainda não existir
python treino.py dados                       # valida CSVs, colisões e pesos (não usa torch)
python treino.py baixar                      # baixa o BERTimbau Base (~420 MB) e fixa a revisão
python treino.py treinar --teste-rapido      # valida o pipeline; NÃO é o treino oficial
python treino.py verificar-modelo --teste-rapido --matriz   # matriz de confusão do modelo do teste rápido
```

Treino oficial (leva horas; **não faz parte da sequência acima, execute só quando decidir**). A
pasta `artifacts\nlp-v1` precisa não existir; se existir só com restos de uma execução interrompida,
acrescente `--forcar` (ela é arquivada, não apagada). `Tee-Object` guarda o log em arquivo:

```powershell
python treino.py treinar 2>&1 | Tee-Object -FilePath treino-oficial.log
```

Depois do treino oficial:

```powershell
python treino.py verificar-modelo            # recarrega nlp-v1 e classifica 5 textos de validação
python treino.py verificar-modelo --matriz   # matriz de confusão e métricas por classe de nlp-v1 (só leitura)
```

- `--teste-rapido` usa uma amostra estratificada (192 de treino e 96 de validação) por 1 época, grava
  só em `artifacts/nlp-v1-teste` (com `"oficial": false`) e **nunca** escreve em `artifacts/nlp-v1`. No
  fim, imprime os segundos por passo medidos e a extrapolação para o treino oficial, que continua
  sendo uma estimativa não medida.
- O treino oficial recusa sobrescrever `artifacts/nlp-v1`. Com `--forcar`, a pasta anterior é
  arquivada (renomeada para `nlp-v1.anterior-<data>`), nunca apagada.
- Os pesos baixados ficam no cache do Hugging Face do usuário, fora do repositório.

### Avaliação por classe

Ao fim do treino, o `orca_model.json` traz `avaliacao_validacao_modelo_salvo`: matriz de confusão (linhas = classe real, colunas = classe prevista), previsões por classe, precisão, recall e F1 por classe, e a probabilidade média por classe. Também traz `perda_ponderada`, com os pesos efetivamente passados à perda e o número de passos em que foram usados. A matriz é necessária porque precisão, recall e F1 iguais a zero em uma classe valem tanto para "nunca prevista" quanto para "prevista só errada".

O teste rápido (192 textos de treino, 96 de validação, 12 passos) serve para validar o fluxo e medir tempo. Suas métricas **não são resultado do modelo**: a validação do teste rápido tem apenas 2 exemplos de `suicidio`.

## 5. Artefatos

`models/nlp/artifacts/nlp-v1/` (pesos e checkpoints ignorados pelo Git; o resto pode ser versionado):

| Arquivo | Conteúdo |
|---|---|
| `model.safetensors`, `config.json` | Pesos treinados e configuração, com `id2label` / `label2id` |
| arquivos do tokenizador | `vocab.txt`, `tokenizer_config.json` etc. |
| `orca_model.json` | Versão, modelo base e revisão exata, normalização, hiperparâmetros configurados e efetivos, pesos de classe, hashes dos CSVs, colisões, truncamento, versões das bibliotecas, métricas de validação por época, melhor época, perda de treino |
| `colisoes_removidas.csv` | Linhas removidas em memória e o motivo |
| `training_args.bin` | Argumentos do `Trainer` (formato binário do transformers) |
| `checkpoints/` | Checkpoints do treino (ignorados pelo Git; podem ser apagados depois) |

`artifacts/modelo-base.json` guarda o hash da revisão baixada e é versionado.

### Como carregar `nlp-v1`

```python
from inferencia import Classificador   # dentro de models/nlp
clf = Classificador("artifacts/nlp-v1")
clf.classificar("texto de exemplo")    # category, score (softmax da classe prevista), model_version
```

O `Classificador` aplica a mesma normalização do treino e confere o mapa de rótulos. A integração
com `POST /classify/text` está **fora do escopo do S2-03**.

## 6. Valores efetivos e resultados (treino oficial de 15/10/2026)

Fonte: `artifacts/nlp-v1/orca_model.json`, gerado pela execução oficial (`python treino.py treinar --forcar`;
a pasta `nlp-v1` anterior era só o resto de uma execução interrompida e foi arquivada). As métricas
abaixo são de **validação**, o mesmo conjunto que escolheu a época; o conjunto de teste não foi usado.

### Valores efetivos

| Item | Valor |
|---|---|
| Modelo base e revisão | `neuralmind/bert-base-portuguese-cased`, revisão `94d69c95f98f7d5b2a8700c420230ae10def0baa` (confirmada pelo modelo carregado) |
| Hiperparâmetros efetivos | Iguais aos configurados (diferenças: nenhuma): taxa 2e-5, 3 épocas, batch 16/32, weight decay 0,01, warmup 0,1, scheduler linear, corte de gradiente 1,0, seed 42, `adamw_torch`, FP32 |
| Bibliotecas | Python 3.12.10, torch 2.14.1+cpu, transformers 4.57.6, accelerate 1.15.0, huggingface_hub 0.36.2, tokenizers 0.22.2, safetensors 0.8.0, scikit-learn 1.9.1, numpy 2.5.4, pandas 3.0.6 |
| Linhas usadas | treino 28.090 e validação 6.025 (CSV: 28.124 e 6.027) |
| SHA-256 (sem diferença CRLF/LF) | `treino.csv` `5878a676ff202a4ea3e038547876b69a9726f0d6f09846dc9fb1ff8d4bf692da`; `validacao.csv` `6c6f203d82216b3059d108d7f4da58a92fe242241bf9783c3ecd166e7dd95156`; `teste.csv` `c1eb3a6047d56ca08b2e2fc6b067102ce7b1d7ac464fc47a49c339fcf31ca6c7` |
| Pesos de classe aplicados | `seguro` 0,3913, `suicidio` 17,9031, `odio` 2,5745; perda ponderada usada em 5.268 de 5.268 passos |
| Execução | CPU; 5.268 passos em 29.753 s (8 h 16 min), 5,65 s/passo; a avaliação de cada época levou de 8 a 11 min (log do console) |
| Truncamento em 128 tokens | 0,16% do treino e 0,10% da validação |
| Seleção | Melhor época 3 (`checkpoint-5268`), macro F1 0,7995; a reavaliação do modelo salvo deu o mesmo valor (`consistente: true`) |

`verificar-modelo --matriz` recarregou o modelo salvo e reproduziu exatamente a matriz de confusão abaixo.
Os hashes acima permitem conferir que os CSVs usados são os mesmos de S2-02; conforme o README de S2-02,
outras versões de pandas ou scikit-learn podem gerar arquivos diferentes.

### Resultados na validação (efetiva, 6.025 textos)

| Época | Perda de validação | macro F1 | Acurácia | F1 `suicidio` | Recall `suicidio` | F1 `odio` |
|---|---|---|---|---|---|---|
| 1 | 0,4090 | 0,7622 | 0,8584 | 0,7605 | 0,8929 | 0,6136 |
| 2 | 0,4686 | 0,7840 | 0,8822 | 0,7909 | 0,9286 | 0,6319 |
| 3 (selecionada) | 0,7297 | 0,7995 | 0,8956 | 0,8211 | 0,9018 | 0,6392 |

Matriz de confusão do modelo salvo (linhas = classe real, colunas = classe prevista):

| Real \ Previsto | seguro | suicidio | odio |
|---|---|---|---|
| seguro (5.133) | 4.776 | 33 | 324 |
| suicidio (112) | 10 | 101 | 1 |
| odio (780) | 261 | 0 | 519 |

| Classe | Precisão | Recall | F1 | Reais | Previstas |
|---|---|---|---|---|---|
| seguro | 0,9463 | 0,9305 | 0,9383 | 5.133 | 5.047 |
| suicidio | 0,7537 | 0,9018 | 0,8211 | 112 | 134 |
| odio | 0,6149 | 0,6654 | 0,6392 | 780 | 844 |

macro F1 = 0,7995; acurácia = 0,8956.

Leitura, com as ressalvas:

- `suicidio`: o modelo detectou 101 de 112 casos, com 33 falsos positivos vindos de `seguro`. Com 112 exemplos, o recall tem margem de erro de aproximadamente ±5 pontos.
- `odio` é a classe mais fraca: 261 dos 780 casos foram classificados como `seguro`.
- A perda de validação subiu a cada época enquanto o macro F1 melhorou. A seleção usa macro F1, como configurado, mas a probabilidade média dada à classe real é alta (`seguro` 0,92, `suicidio` 0,90, `odio` 0,66), o que indica previsões confiantes; o `score` não foi calibrado nem avaliado como probabilidade.
- A seleção da época e as métricas usam o mesmo conjunto (validação), então os valores são um pouco otimistas. A avaliação no conjunto de teste, as metas de F1/recall (RIA01 a RIA03, ainda "a definir" no relatório) e a latência (RIA05) ficam para a etapa de avaliação.
- Toda a classe `suicidio` vem de uma única fonte (Boamente); parte do desempenho pode refletir o estilo dessa fonte e não o conteúdo. Isso não foi testado.

## 7. Limitações conhecidas

- O dataset é de tweets curtos; a extensão enviará páginas inteiras. Há mudança de domínio, e textos
  acima de 128 tokens são truncados (sem divisão em trechos). No dataset isso afeta só 0,16% do treino e 0,10% da validação, mas o efeito em páginas reais não foi avaliado.
- Só 3 classes; `seguro` não significa conteúdo adequado para as demais categorias do projeto. Os
  nomes `suicidio` e `odio` ainda precisam ser mapeados para os de `categorias.md`.
- Toda a classe `suicidio` vem do Boamente e toda `odio` do TuPyE: o modelo pode aprender a fonte em
  vez do conteúdo. A remoção de `@user` e links reduz, mas não elimina, esse risco.
- Há poucos exemplos de `suicidio` na validação (112, o mesmo número depois do tratamento de colisões), então
  o macro F1 oscila entre execuções.
- Execuções em CPU com a mesma seed tendem a repetir os resultados, mas não há garantia de igualdade
  bit a bit entre máquinas ou versões de bibliotecas.
- Os pesos (`model.safetensors`, cerca de 436 MB) não são versionados no Git. O local de compartilhamento com a equipe ainda precisa ser definido (a definir pela equipe).
- Compatibilidade: o treino rodou com as versões registradas na seção 6. Outras versões dentro das faixas de
  `requirements-treino.txt` não foram testadas.
