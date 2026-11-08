/**
 * Só roda nas páginas do site do ORCA (CONFIG.siteOrigins). É a ponte entre o
 * site e a extensão, que NÃO compartilham localStorage:
 *
 *   site -> extensão
 *     - lê a sessão que o site salva no localStorage e repassa o access token
 *       ao service worker (que cria uma sessão própria); null = o usuário saiu;
 *     - evento "orca:monitoramento" (botão do painel) -> o SW confere o backend.
 *   extensão -> site
 *     - publica o estado da extensão (sem tokens) no atributo data-orca-extensao
 *       do <html>, que o painel de logs mostra;
 *     - logout pelo popup: apaga a sessão do site e avisa a página.
 */
import { CONFIG } from '../config';
import type {
  EstadoExtensao,
  SessionSyncMessage,
  SiteLogoutMessage,
  SiteStateChangedMessage,
} from '../models/content';

/** Eventos disparados pelo site (orca-site/lib/api.ts). */
const EVENTO_SESSAO_DO_SITE = 'orca:sessao';
const EVENTO_MONITORAMENTO_DO_SITE = 'orca:monitoramento';
const ATRIBUTO = 'data-orca-extensao';
const VERIFICAR_A_CADA_MS = 2000;

export function isOrcaSite(origin = location.origin): boolean {
  return CONFIG.siteOrigins.includes(origin);
}

function lerToken(): string | null {
  try {
    const bruto = localStorage.getItem(CONFIG.siteSessionKey);
    const sessao = bruto ? (JSON.parse(bruto) as { token?: unknown }) : null;
    return typeof sessao?.token === 'string' && sessao.token ? sessao.token : null;
  } catch {
    return null;
  }
}

function enviar(mensagem: SessionSyncMessage | SiteStateChangedMessage): void {
  try {
    chrome.runtime.sendMessage(mensagem).catch(() => {});
  } catch {
    // extensão recarregada com a aba aberta — recarregue a aba
  }
}

function publicarEstado(e: EstadoExtensao | undefined): void {
  const publico = {
    versao: chrome.runtime.getManifest().version,
    email: e?.usuario?.email ?? null,
    sessao: e?.sessao ?? 'ausente',
    monitorando: !!e?.monitorando,
    backend: e?.backend ?? 'desconhecido',
  };
  document.documentElement.setAttribute(ATRIBUTO, JSON.stringify(publico));
}

export function syncSession(): void {
  // ---- sessão do site -> extensão
  let ultimo: string | null | undefined; // undefined = ainda não enviou
  const conferirSessao = () => {
    const token = lerToken();
    if (token === ultimo) return;
    ultimo = token;
    enviar({ type: 'SESSION_SYNC', token });
  };
  conferirSessao();
  window.addEventListener(EVENTO_SESSAO_DO_SITE, conferirSessao); // login/logout/renovação nesta aba
  window.addEventListener('storage', conferirSessao);             // ... em outra aba
  setInterval(conferirSessao, VERIFICAR_A_CADA_MS);               // garantia

  // ---- botão de monitoramento do painel -> extensão
  window.addEventListener(EVENTO_MONITORAMENTO_DO_SITE, () => enviar({ type: 'SITE_STATE_CHANGED' }));

  // ---- estado da extensão -> painel
  chrome.storage.local.get('estado').then((d) => publicarEstado(d.estado as EstadoExtensao | undefined));
  chrome.storage.onChanged.addListener((mudancas, area) => {
    if (area === 'local' && mudancas.estado) publicarEstado(mudancas.estado.newValue as EstadoExtensao | undefined);
  });

  // ---- logout pelo popup -> site sai também
  chrome.runtime.onMessage.addListener((mensagem: SiteLogoutMessage) => {
    if (mensagem?.type !== 'SITE_LOGOUT') return;
    try {
      localStorage.removeItem(CONFIG.siteSessionKey);
    } catch {
      // armazenamento bloqueado
    }
    ultimo = null; // já sabemos que saiu: não reenvia null ao SW
    window.dispatchEvent(new Event(EVENTO_SESSAO_DO_SITE)); // a página atualiza na hora
  });
}
