/**
 * Content Script.
 *  - No site do ORCA: só repassa o token de login do site ao service worker.
 *  - Nas demais páginas: extrai o conteúdo, envia ao service worker e repete quando o DOM muda.
 */
import { CONFIG } from '../config';
import type { ContentExtractedMessage, SessionSyncMessage } from '../models/content';
import { extractContent } from './extractor';
import { observeChanges } from './observer';

/** Evento que o site dispara no login/logout (orca-site/lib/api.ts). */
const EVENTO_SESSAO_DO_SITE = 'orca:sessao';
const VERIFICAR_SESSAO_A_CADA_MS = 2000;

function send(message: ContentExtractedMessage | SessionSyncMessage): void {
  try {
    chrome.runtime.sendMessage(message).catch(() => {});
  } catch {
    // extensão recarregada com a aba aberta — recarregue a aba
  }
}

function readSiteToken(): string | null {
  try {
    const raw = localStorage.getItem(CONFIG.siteSessionKey);
    const session = raw ? (JSON.parse(raw) as { token?: unknown }) : null;
    return typeof session?.token === 'string' && session.token ? session.token : null;
  } catch {
    return null;
  }
}

function syncSession(): void {
  let last: string | null | undefined; // undefined = ainda não enviou
  const check = () => {
    const token = readSiteToken();
    if (token === last) return;
    last = token;
    send({ type: 'SESSION_SYNC', token });
  };
  check();
  window.addEventListener(EVENTO_SESSAO_DO_SITE, check); // login/logout nesta aba
  window.addEventListener('storage', check);             // ... em outra aba
  setInterval(check, VERIFICAR_SESSAO_A_CADA_MS);        // garantia
}

function extractAndSend(): void {
  send({ type: 'CONTENT_EXTRACTED', payload: extractContent() });
}

if (CONFIG.siteOrigins.includes(location.origin)) {
  syncSession();
} else {
  extractAndSend();
  observeChanges(extractAndSend, CONFIG.debounceMs);
}
