/** Ajuste aqui e rode `npm run build` de novo. */
export const CONFIG = {
    /** Imagens menores que isso (tamanho natural, em px) são descartadas. */
    minImageWidth: 100,
    minImageHeight: 100,
    minImageArea: 10_000,

    /** Espera (ms) sem novas mudanças na página antes de extrair de novo. */
    debounceMs: 1000,

    /**
     * Para onde o service worker envia cada conteúdo extraído (o mesmo JSON vai para todos).
     * Se mudar uma porta, mude também host_permissions em public/manifest.json.
     */
    serverUrls: {
        imagem: 'http://localhost:8000/content',      // models/vision/pipeline.py
        texto: 'http://localhost:8001/classify/text', // models/server.py (nlp)
    },

    /** Site aberto quando o usuário clica no ícone da extensão. */
    dashboardUrl: 'https://pi-orca.vercel.app/',
};