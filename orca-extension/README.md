# ORCA — Extração de Conteúdo

Extensão Chrome (Manifest V3) que extrai o **texto** e as **imagens (`<img>`)** de cada página e envia o
resultado ao servidor (`server/`), que por enquanto só recebe.

## Rodar

```bash
npm install
npm run build
```

`chrome://extensions` → **Modo do desenvolvedor** → **Carregar sem compactação** → pasta `dist/`.
Para ver o resultado: no card da extensão, clique em **service worker** e abra qualquer site.

Depois de mudar o código: `npm run build`, recarregue a extensão e **recarregue a aba**.

## Servidores (Python)

O mesmo conteúdo é enviado para os dois servidores, cada um independente do outro
(se um estiver fora do ar, o outro continua recebendo):

| IA | Endereço | Como subir (a partir de `models/`, com o `.venv` ativo) |
|---|---|---|
| imagem | `http://localhost:8000/content` | `python vision/pipeline.py` |
| texto | `http://localhost:8001/classify/text` | `python server.py` |

Deixe rodando. A cada página aberta o terminal de cada servidor mostra um resumo
(`[ORCA] …` no de imagem, `[ORCA texto] …` no de texto), e o console do service worker
mostra a resposta de cada um.
Os endereços ficam em `src/config.ts` (`serverUrls`) e as permissões em `public/manifest.json`
(`host_permissions`); se mudar uma porta, mude nos dois e rode `npm run build`.

## Arquivos

```
public/manifest.json           permissões: só content_scripts (http/https), sem "permissions"
src/config.ts                  tamanho mínimo das imagens (100 / 100 / 10.000 px²) e debounce
src/models/content.ts          tipos: ExtractedContent, ExtractedImage, mensagem
src/content/index.ts           extrai, envia ao service worker, repete quando a página muda
src/content/extractor.ts       extractText / extractImages / extractMetadata / normalizeContent
src/content/observer.ts        MutationObserver + debounce (+ evento load das <img>)
src/utils/normalization.ts     limpeza básica do texto
src/background/service-worker.ts   recebe o conteúdo e faz POST para o servidor
```

## Formato do resultado

```ts
{
  url, title, timestamp,        // strings
  text,                         // string
  images: [{ src, alt?, width, height }]
}
```

## Limitações

- Só `<img>` (não pega CSS background, `<svg>` inline, `<canvas>`, `<video>`).
- `images[].src` é a URL, não os bytes da imagem.
- Só o frame principal da página (iframes não são lidos).
