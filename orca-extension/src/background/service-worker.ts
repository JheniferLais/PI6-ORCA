/**
 * Service Worker: recebe o conteúdo extraído de cada aba e envia ao POST /analyze
 * do backend, com o token de login do site do ORCA (Authorization: Bearer).
 *
 * O token chega pelo content script que roda no site (SESSION_SYNC) e fica em
 * chrome.storage.session (some ao fechar o navegador, e content scripts não leem).
 * Sem token válido, nada é enviado: é preciso entrar no site do ORCA.
 */
import { CONFIG } from '../config';
import type { ContentExtractedMessage, ExtractedContent, SessionSyncMessage } from '../models/content';

const CHAVE_TOKEN = 'token';

/** Última assinatura enviada por aba: o mesmo conteúdo não é reanalisado (nem vira log de novo). */
const ultimaPorAba = new Map<number, string>();

/**
 * URLs cujo log já é definitivo (o backend respondeu "final": true): nenhuma
 * análise nova mudaria nada, então a página não é mais enviada, mesmo que mude.
 * Fica em chrome.storage.session para sobreviver ao service worker ser encerrado.
 */
const CHAVE_FINAIS = 'urlsFinais';

async function lerFinais(): Promise<string[]> {
    const dados = await chrome.storage.session.get(CHAVE_FINAIS);
    return (dados[CHAVE_FINAIS] as string[] | undefined) ?? [];
}

async function marcarFinal(url: string): Promise<void> {
    const finais = await lerFinais();
    if (!finais.includes(url)) await chrome.storage.session.set({ [CHAVE_FINAIS]: [...finais, url].slice(-500) });
}

/** Análise em andamento por URL: a próxima da mesma URL espera ela terminar (e pode nem ser enviada). */
const emAndamento = new Map<string, Promise<void>>();

async function lerToken(): Promise<string | null> {
    const dados = await chrome.storage.session.get(CHAVE_TOKEN);
    return (dados[CHAVE_TOKEN] as string | undefined) ?? null;
}

async function salvarToken(token: string | null): Promise<void> {
    if (token) await chrome.storage.session.set({ [CHAVE_TOKEN]: token });
    else await chrome.storage.session.remove(CHAVE_TOKEN);
}

/** Lê o "exp" do JWT (sem validar a assinatura: isso é papel do backend). */
function tokenExpirado(token: string): boolean {
    try {
        const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const { exp } = JSON.parse(atob(base64)) as { exp?: number };
        return typeof exp !== 'number' || exp * 1000 <= Date.now();
    } catch {
        return true;
    }
}

function assinatura(c: ExtractedContent): string {
    return `${c.url}\n${c.images.map((i) => i.src).sort().join('\n')}\n${c.text}`;
}

function handleContent(content: ExtractedContent, tabId?: number): Promise<void> {
    const anterior = emAndamento.get(content.url) ?? Promise.resolve();
    const atual = anterior.then(() => analisar(content, tabId));
    emAndamento.set(content.url, atual);
    void atual.finally(() => {
        if (emAndamento.get(content.url) === atual) emAndamento.delete(content.url);
    });
    return atual;
}

async function analisar(content: ExtractedContent, tabId?: number): Promise<void> {
    if ((await lerFinais()).includes(content.url)) return; // essa página já tem log definitivo

    const token = await lerToken();
    if (!token || tokenExpirado(token)) {
        console.warn('[ORCA] sem login válido: entre no site do ORCA para ativar a análise');
        return;
    }

    const minha = assinatura(content);
    if (tabId !== undefined && ultimaPorAba.get(tabId) === minha) return;

    console.log(`[ORCA] ${content.url} | texto: ${content.text.length} chars | imagens: ${content.images.length}`);
    try {
        const response = await fetch(CONFIG.analyzeUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify(content),
        });
        if (response.status === 401) {
            await salvarToken(null);
            console.warn('[ORCA] login expirado ou inválido: entre no site do ORCA de novo');
            return;
        }
        if (!response.ok) {
            console.warn(`[ORCA] /analyze respondeu ${response.status}`);
            return;
        }
        if (tabId !== undefined) ultimaPorAba.set(tabId, minha); // falhou = tenta de novo na próxima mudança
        const resultado = (await response.json()) as { final?: boolean };
        if (resultado.final) await marcarFinal(content.url);
        console.log('[ORCA] análise:', resultado);
    } catch (error) {
        console.warn('[ORCA] backend indisponível:', error);
    }
}

chrome.runtime.onMessage.addListener((message: ContentExtractedMessage | SessionSyncMessage, sender) => {
    if (message?.type === 'CONTENT_EXTRACTED') void handleContent(message.payload, sender.tab?.id);
    else if (message?.type === 'SESSION_SYNC') {
        // trocou de conta (ou saiu): as URLs "finais" eram da sessão anterior
        void lerToken().then(async (antes) => {
            if (antes !== message.token) await chrome.storage.session.remove(CHAVE_FINAIS);
            await salvarToken(message.token);
        });
    }
});

chrome.tabs.onRemoved.addListener((tabId) => ultimaPorAba.delete(tabId));

/** Clique no ícone da extensão: abre o site do ORCA em uma aba nova. */
chrome.action.onClicked.addListener(() => {
    void chrome.tabs.create({ url: CONFIG.dashboardUrl });
});
