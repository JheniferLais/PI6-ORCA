/** Ajuste aqui e rode `npm run build` de novo. */
export const CONFIG = {
  /** Imagens menores que isso (tamanho natural, em px) são descartadas. */
  minImageWidth: 100,
  minImageHeight: 100,
  minImageArea: 10_000,

  /** Espera (ms) sem novas mudanças na página antes de extrair de novo. */
  debounceMs: 1000,

  /** Para onde o service worker envia cada conteúdo extraído. */
  serverUrl: 'http://localhost:8000/content',
};
