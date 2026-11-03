# Classificador de imagens (visão)

Classifica imagens em três classes: `SFW`, `NSFW` e `NSFL`, e para cada imagem devolve **três números de 0 a 1** (as probabilidades de cada classe, que somam 1).
Modelo: [`OwenElliott/image-safety-classifier-s`](https://huggingface.co/OwenElliott/image-safety-classifier-s), um SwiftFormer pequeno (cerca de 5,7 milhões de parâmetros, licença MIT), usado **como veio**, sem treino nosso.

```json
{ "label": "NSFW", "scores": { "SFW": 0.0312, "NSFW": 0.9487, "NSFL": 0.0201 } }
```

A ordem é sempre `SFW`, `NSFW`, `NSFL`. O card do modelo mostra duas ordens diferentes de rótulos (uma no texto, outra no exemplo ONNX), então o código mapeia pelo **nome** do rótulo e levanta erro se vier algo diferente de `SFW`, `NSFW` e `NSFL`, em vez de devolver números trocados em silêncio.

## Estrutura

```
vision/
├── data/
│   ├── pipeline.py        monta o dataset (sem servidor, sem modelo)
│   ├── fontes.json        fontes e mapeamento pasta -> classe
│   └── README.md          origem, rótulos, limitações do dataset
├── classificador.py       carrega o modelo e devolve as 3 pontuações (Pontuacoes)
├── filtro.py              o que não vale classificar (svg, pequena, banner...)
├── download.py            bytes da imagem (data: URI ou http/https) e decodificação
├── cache.py               cache LRU
├── pipeline.py            servidor FastAPI: POST /content (porta 8000)
├── avaliacao.py           métricas do modelo no dataset
├── simulado.py            IA SIMULADA usada hoje por /analyze (veja "Integração")
├── __main__.py            linha de comando: python -m vision ...
├── requirements.txt
└── tests/                 testes sem torch e sem rede
```

O fluxo é linear: `data/pipeline.py` → `avaliacao.py`; `pipeline.py` usa `filtro` → `download` → `cache` → `classificador`.

## Como usar

Tudo roda a partir de `models/`, com o ambiente de `vision/requirements.txt` (ou o `models/requirements.txt`) ativo.

```bash
python -m vision dados                      # 1. monta o dataset (veja data/README.md)
python -m vision avaliar                    # 2. avalia o modelo no teste (grava avaliacao-teste.json)
python -m vision                            # 3. sobe o servidor para a extensão (localhost:8000)
python -m unittest discover -s vision/tests -t .    # testes
```

Na primeira subida o `timm` baixa os pesos do Hugging Face (alguns MB) para o cache do usuário. Os testes **não** precisam de torch nem de internet.

## O servidor: `POST /content`

É o endereço que a extensão já chama (`orca-extension/src/config.ts`). Recebe o JSON de sempre (`url`, `title`, `timestamp`, `images[]`; o campo `text` é ignorado) e devolve **uma entrada por imagem, na ordem original**:

```json
{
  "ok": true,
  "url": "https://exemplo.com/",
  "summary": { "received": 3, "classified": 1, "skipped": 1, "errors": 1,
               "cache_hits": 0, "downloaded": 2, "elapsed_ms": 412 },
  "page": { "modality": "img", "category": "NSFW", "score": 0.9487, "model_version": "vision-v1" },
  "images": [
    { "index": 0, "src": "https://…/a.jpg", "status": "classified", "label": "NSFW",
      "scores": { "SFW": 0.0312, "NSFW": 0.9487, "NSFL": 0.0201 }, "cached": false },
    { "index": 1, "src": "https://…/logo.svg", "status": "skipped", "reason": "svg" },
    { "index": 2, "src": "https://…/b.jpg", "status": "error", "reason": "download_falhou:http_403" }
  ]
}
```

| `status` | Significado | Campos |
|---|---|---|
| `classified` | O modelo classificou | `label`, `scores` (3 floats), `cached`, e `duplicate_of` se a URL repete outra da página |
| `skipped` | Nem chegou ao modelo | `reason`: `svg`, `pequena_demais`, `proporcao_extrema`, `esquema_nao_suportado`, `data_uri_nao_e_imagem`, `limite_por_pagina` |
| `error` | Não deu para baixar/abrir | `reason`: `download_falhou:…`, `imagem_invalida`, `falha_no_modelo:…` |

**Imagem com erro NUNCA volta como `SFW`.** Quem decide o que fazer com ela é a camada de política.

### O campo `page`

Resume a página inteira **no mesmo formato das outras IAs** (`modality`, `category`, `score`, `model_version`), pronto para o `app/decisao.py`:

- se alguma imagem não é SFW, vale a pior delas (maior probabilidade; em empate, NSFL > NSFW);
- se todas são SFW, vale SFW com a probabilidade da imagem **menos** segura de si;
- se nenhuma foi classificada, `category` é `"indefinido"` e `score` é `null`, e a IA fica de fora da decisão (igual ao texto pequeno demais).

### Do mais barato ao mais caro

1. Descarta o que não vale classificar (sem rede e sem modelo).
2. Agrupa URLs repetidas (o mesmo ícone 8 vezes vale 1).
3. Cache por URL: a extensão reenvia a página a cada mudança no DOM.
4. Limita as imagens novas às 15 maiores (`MAX_IMAGENS_POR_PAGINA`).
5. Baixa em paralelo (`data:` URI é decodificado direto).
6. Cache por conteúdo (hash dos bytes): URL diferente, mesma imagem, 1 inferência.
7. **Uma** chamada do modelo, em lote, com tudo que sobrou.

Os parâmetros (tamanhos mínimos, limite por página, tamanho do cache, tempo de espera de erro) ficam no topo de `pipeline.py`, `filtro.py` e `download.py`.

## Avaliação

`python -m vision avaliar` roda o modelo no conjunto de **teste** de `data/datasets` e grava `avaliacao-teste.json` com:

- a matriz de confusão (linhas = classe real, colunas = prevista), necessária porque precisão/recall/F1 iguais a zero valem tanto para "nunca prevista" quanto para "prevista só errada";
- precisão, recall e F1 por classe, o macro F1 e a acurácia;
- **seguro x inseguro** (NSFW ou NSFL contra SFW): recall (quantas inseguras o modelo pegou), precisão e taxa de falso alarme em SFW. Para controle parental, é o número que mais importa;
- a probabilidade média dada à classe real.

Classe sem nenhuma imagem real (NSFL, enquanto não houver exemplos revisados) aparece como "sem imagens reais" e fica **fora** do macro F1, em vez de virar um 0 ou um número inventado. `--divisao validacao` e `--limite N` (amostra estratificada, não grava arquivo) servem para conferência rápida.

O número que o autor do modelo reporta (97,99% de acurácia) vem de um conjunto próprio e privado, **não** do nosso. A nossa avaliação é a que vale para o ORCA.

## Resultados (vision-v1, conjunto de teste)

Modelo pré-treinado `OwenElliott/image-safety-classifier-s`, **sem treino nosso**, avaliado em 158 imagens do nosso dataset (`python -m vision dados --max-por-classe 500` e `python -m vision avaliar`, seed 42).

| Divisão | SFW | NSFW | NSFL | Total |
|---|---|---|---|---|
| Treino | 350 | 350 | 36 | 736 |
| Validação | 75 | 75 | 8 | 158 |
| Teste | 75 | 75 | 8 | 158 |

(O modelo não é treinado aqui, então só o teste importa; treino e validação existem por compatibilidade com o pipeline do NLP.)

Matriz de confusão (linhas = real, colunas = previsto):

|  | SFW | NSFW | NSFL |
|---|---|---|---|
| **SFW** | 73 | 2 | 0 |
| **NSFW** | 2 | 73 | 0 |
| **NSFL** | 1 | 0 | 7 |

| Classe | Precisão | Recall | F1 | Reais |
|---|---|---|---|---|
| SFW | 0,9605 | 0,9733 | 0,9669 | 75 |
| NSFW | 0,9733 | 0,9733 | 0,9733 | 75 |
| NSFL | 1,0000 | 0,8750 | 0,9333 | 8 |

**macro F1 = 0,9579 | acurácia = 0,9684**

Seguro × inseguro (NSFW ou NSFL contra SFW), a métrica que mais importa para controle parental: **recall 0,9639** (80 de 83 inseguras pegas; as 3 que passaram foram classificadas como SFW), precisão 0,9756 e **falso alarme de 0,0267** (2 de 75 imagens SFW marcadas como inseguras).

Probabilidade média dada à classe real: SFW 0,89, NSFW 0,90, NSFL 0,81. O score não foi calibrado.

### Leitura, com as ressalvas

- **NSFL tem só 8 imagens no teste.** Cada imagem vale 12,5 pontos de recall, então 0,875 (7 de 8) tem margem de erro enorme. Os números dessa classe mostram que o modelo funciona, mas não permitem comparar com precisão.
- **As imagens de NSFL foram coletadas e revisadas por nós** (52 no total), sem fonte pública de referência. [Descreva aqui como foram coletadas.]
- **SFW e NSFW vêm do dataset `deepghs/nsfw_detect`**, rotuladas pela pasta de origem, sem revisão humana. Sorteamos 500 de cada classe entre as 16.715 aceitas.
- **A pasta `sexy` (conteúdo sugestivo, não explícito) ficou de fora de propósito.** É a fronteira entre SFW e NSFW, onde o modelo mais erra, então os números de SFW e NSFW são **mais otimistas do que seriam em conteúdo ambíguo**.
- **Não dá para descartar sobreposição** entre as imagens do deepghs e o conjunto privado de treino do autor do modelo, o que também favoreceria o resultado.
- O dataset é majoritariamente arte e anime. Em páginas reais (screenshots, memes, fotos de rede social), o desempenho pode ser pior.
- O autor reporta 97,99% de acurácia, mas em um conjunto privado dele. O nosso 96,84% é do mesmo patamar, mas os números **não são comparáveis**.
- Latência e comportamento do servidor em páginas reais não foram medidos nesta avaliação.

## Integração com o backend

Hoje o `POST /analyze` (`app/routes/analise.py`) usa `vision/simulado.py`, que **sorteia** o resultado a partir da URL, enquanto a extensão chama este servidor (porta 8000) e o backend (porta 8001) separadamente. Os dois não se falam. O `page` foi feito para o caso de ligar os dois: a troca em `analise.py` é fornecer uma função que devolva o `page` do `PipelineImagens`, com a mesma assinatura da simulada. Isso **não foi alterado** nesta etapa.

## Limitações

- **NSFL é o ponto fraco**, no modelo (o autor admite que a classe é sub-representada no treino dele) e no nosso dataset (não há fonte pública confiável; veja `data/README.md`).
- Os rótulos do modelo são subjetivos: o card avisa que "NSFW" depende de contexto e que ele erra.
- Só `<img>`: `background-image` do CSS, `<svg>`, `<canvas>` e `<video>` não chegam (limitação da extensão).
- O servidor **baixa a imagem pela URL**, então imagem atrás de login/cookies falha com `download_falhou` (por isso o `Referer` é enviado, mas cookie não). Não está pronto para sair de `localhost`: baixa qualquer URL que receber (risco de SSRF).
- Uma inferência por vez (trava no modelo); POSTs simultâneos esperam na fila.
- A avaliação mede o modelo no nosso dataset, que é majoritariamente arte/anime; o desempenho em páginas reais (screenshots, memes, fotos de rede social) pode ser pior.
