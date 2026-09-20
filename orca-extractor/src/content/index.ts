/** Content Script: extrai a página, envia ao service worker e repete quando o DOM muda. */
import { CONFIG } from '../config';
import type { ContentExtractedMessage } from '../models/content';
import { extractContent } from './extractor';
import { observeChanges } from './observer';

function extractAndSend(): void {
  const message: ContentExtractedMessage = {
    type: 'CONTENT_EXTRACTED',
    payload: extractContent(),
  };
  try {
    chrome.runtime.sendMessage(message).catch(() => {});
  } catch {
    // extensão recarregada com a aba aberta — recarregue a aba
  }
}

extractAndSend();
observeChanges(extractAndSend, CONFIG.debounceMs);
