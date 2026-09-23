# Contrato de API — Extensão ↔ Backend Local

Este documento define o formato das mensagens trocadas entre a extensão do
navegador (módulo de captura) e o backend local (motores de IA e motor de
políticas), servindo de base para o desenvolvimento das Duplas A (NLP) e B
(Visão) na Sprint 2.

## Visão geral do fluxo

1. A extensão captura URL, texto e imagens da página (RF001) e faz o
   pré-processamento (RF002, RF005).
2. A extensão envia o conteúdo pré-processado para o backend.
3. O backend classifica o texto (`POST /classify/text`) e as imagens
   (`POST /classify/image`), cada um retornando categoria, score e versão
   do modelo.
4. O motor de políticas consolida as duas respostas e decide a ação.

## Endpoints previstos

| Método | Endpoint | Responsabilidade |
|---|---|---|
| `POST` | `/classify/text` | Classificar o texto pré-processado de uma página (RF003, RF004) |
| `POST` | `/classify/image` | Classificar as imagens pré-processadas de uma página (RF006, RF007) |

## Formato de envio de imagens

As imagens são enviadas como **base64**, já redimensionadas e normalizadas
pela extensão (RF005), evitando que o backend precise acessar a URL original
da imagem (o que poderia falhar em páginas HTTPS ou com conteúdo dinâmico).

---

## `POST /classify/text`

### Requisição

```json
{
  "url": "https://exemplo.com/pagina",
  "timestamp": "2026-09-20T14:30:00Z",
  "text": "texto limpo da página..."
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `url` | string | URL completa da página acessada |
| `timestamp` | string (ISO 8601) | Data/hora da captura |
| `text` | string | Texto já limpo e normalizado pela extensão (RF002). Pode vir vazio ou ausente se o texto for insuficiente |

### Resposta

```json
{
  "modality": "text",
  "category": "seguro",
  "score": 0.93,
  "model_version": "nlp-v1"
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `modality` | string | Sempre `"text"` |
| `category` | string | Categoria atribuída (ver `docs/categorias.md`) |
| `score` | number [0, 1] | Nível de confiança da classificação (RF004) |
| `model_version` | string | Identificador da versão do modelo usado (ex.: `nlp-v1`) |

---

## `POST /classify/image`

### Requisição

```json
{
  "url": "https://exemplo.com/pagina",
  "timestamp": "2026-09-20T14:30:00Z",
  "images": [
    { "src": "https://exemplo.com/img1.jpg", "width": 800, "height": 600, "data": "base64..." }
  ]
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `url` | string | URL completa da página acessada |
| `timestamp` | string (ISO 8601) | Data/hora da captura |
| `images` | array | Lista de imagens já pré-processadas (RF005). Pode vir vazia se não houver imagens relevantes |
| `images[].src` | string | URL de origem da imagem |
| `images[].width` / `height` | number | Dimensões originais da imagem |
| `images[].data` | string (base64) | Imagem já redimensionada/normalizada para o formato de entrada do modelo |

### Resposta

```json
{
  "modality": "image",
  "results": [
    {
      "src": "https://exemplo.com/img1.jpg",
      "category": "seguro",
      "score": 0.88,
      "model_version": "vision-v1"
    }
  ]
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `modality` | string | Sempre `"image"` |
| `results` | array | Uma entrada por imagem enviada |
| `results[].src` | string | URL de origem, para rastrear qual imagem recebeu qual categoria |
| `results[].category` | string | Categoria atribuída (RF006) |
| `results[].score` | number [0, 1] | Nível de confiança da classificação (RF007) |
| `results[].model_version` | string | Identificador da versão do modelo usado (ex.: `vision-v1`) |

---

## Casos de borda

- **Texto insuficiente** (menos que o mínimo de palavras definido em RF002): o
  campo `text` pode vir vazio; o backend deve responder com `category: "indefinido"`
  e `score: null`, sem travar o fluxo.
- **Página sem imagens relevantes**: `images` pode ser uma lista vazia (`[]`);
  a resposta deve trazer `results: []`.
- **Falha em um dos módulos**: seguir o modo degradado definido em RNF005 — o
  motor de políticas aplica uma política padrão em vez de travar a navegação.

## Histórico de revisão

| Versão | Data | Alteração |
|---|---|---|
| 0.1 | a definir | Versão inicial, revisada com o time |
