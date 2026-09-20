/** Service Worker: recebe o conteúdo extraído de cada aba e envia ao servidor. */
import { CONFIG } from '../config';
import type { ContentExtractedMessage, ExtractedContent } from '../models/content';

async function handleContent(content: ExtractedContent): Promise<void> {
  console.log(`[ORCA] ${content.url} | texto: ${content.text.length} chars | imagens: ${content.images.length}`, content);

  try {
    const response = await fetch(CONFIG.serverUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(content),
    });
    if (!response.ok) console.warn(`[ORCA] servidor respondeu ${response.status}`);
  } catch (error) {
    console.warn('[ORCA] servidor indisponível:', error);
  }
}

chrome.runtime.onMessage.addListener((message: ContentExtractedMessage) => {
  if (message?.type === 'CONTENT_EXTRACTED') void handleContent(message.payload);
});
