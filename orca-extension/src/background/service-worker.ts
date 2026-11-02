/** Service Worker: recebe o conteúdo extraído de cada aba e envia ao servidor. */
import { CONFIG } from '../config';
import type { ContentExtractedMessage, ExtractedContent } from '../models/content';

/** Envia para um servidor; uma falha (servidor fora do ar) não afeta o outro. */
async function send(name: string, url: string, body: string): Promise<void> {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body,
        });
        if (!response.ok) {
            console.warn(`[ORCA] servidor de ${name} respondeu ${response.status}`);
            return;
        }
        console.log(`[ORCA] resposta de ${name}:`, await response.json());
    } catch (error) {
        console.warn(`[ORCA] servidor de ${name} indisponível:`, error);
    }
}

async function handleContent(content: ExtractedContent): Promise<void> {
    console.log(`[ORCA] ${content.url} | texto: ${content.text.length} chars | imagens: ${content.images.length}`, content);

    const body = JSON.stringify(content);
    await Promise.all(
        Object.entries(CONFIG.serverUrls).map(([name, url]) => send(name, url, body)),
    );
}

chrome.runtime.onMessage.addListener((message: ContentExtractedMessage) => {
    if (message?.type === 'CONTENT_EXTRACTED') void handleContent(message.payload);
});

/** Clique no ícone da extensão: abre o site do ORCA em uma aba nova. */
chrome.action.onClicked.addListener(() => {
    void chrome.tabs.create({ url: CONFIG.dashboardUrl });
});