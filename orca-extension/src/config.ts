/** Ajuste aqui e rode `npm run build` de novo. */
export const CONFIG = {
    /** Imagens menores que isso (tamanho natural, em px) são descartadas. */
    minImageWidth: 100,
    minImageHeight: 100,
    minImageArea: 10_000,

    /** Espera (ms) sem novas mudanças na página antes de extrair de novo. */
    debounceMs: 1000,

    /**
     * Para onde o service worker envia cada conteúdo extraído: o backend analisa
     * texto + imagens e grava o log do usuário logado (models/app/routes/analise.py).
     * Se mudar a porta, mude também host_permissions em public/manifest.json.
     */
    analyzeUrl: 'http://localhost:8001/analyze',

    /**
     * Páginas do site do ORCA. Nelas a extensão não analisa nada: só lê o token
     * de login que o site guarda no localStorage (orca-site/lib/api.ts).
     */
    siteOrigins: ['https://pi-orca.vercel.app', 'http://localhost:3000', 'http://127.0.0.1:3000'],
    siteSessionKey: 'orca.sessao',

    /** Site aberto quando o usuário clica no ícone da extensão. */
    dashboardUrl: 'https://pi-orca.vercel.app/',
};
