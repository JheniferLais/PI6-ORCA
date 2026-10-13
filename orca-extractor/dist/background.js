const CONFIG = {
  /** Imagens menores que isso (tamanho natural, em px) são descartadas. */
  minImageWidth: 100,
  minImageHeight: 100,
  minImageArea: 1e4,
  /** Espera (ms) sem novas mudanças na página antes de extrair de novo. */
  debounceMs: 1e3,
  /** Para onde o service worker envia cada conteúdo extraído. */
  serverUrl: "http://localhost:8000/content",
  /** Site aberto quando o usuário clica no ícone da extensão. */
  dashboardUrl: "https://example.com"
};
async function handleContent(content) {
  console.log(`[ORCA] ${content.url} | texto: ${content.text.length} chars | imagens: ${content.images.length}`, content);
  try {
    const response = await fetch(CONFIG.serverUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(content)
    });
    if (!response.ok) console.warn(`[ORCA] servidor respondeu ${response.status}`);
  } catch (error) {
    console.warn("[ORCA] servidor indisponível:", error);
  }
}
chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "CONTENT_EXTRACTED") void handleContent(message.payload);
});
chrome.action.onClicked.addListener(() => {
  void chrome.tabs.create({ url: CONFIG.dashboardUrl });
});
