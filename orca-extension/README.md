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

## Servidor (Python)

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Deixe rodando. A cada página aberta o terminal mostra `[ORCA] url | texto: … | imagens: …`.
O endereço fica em `src/config.ts` (`serverUrl`) e a permissão em `public/manifest.json` (`host_permissions`);
se mudar a porta, mude nos dois e rode `npm run build`.

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
