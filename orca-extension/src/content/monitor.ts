/**
 * Monitor das páginas comuns (todas menos o site do ORCA).
 *
 * Só captura enquanto o monitoramento está ativo (estado em chrome.storage.local,
 * mantido pelo service worker). Liga e desliga na hora quando o estado muda:
 * desligado, nem o MutationObserver fica rodando.
 *
 * Mudanças irrelevantes no DOM não geram nova análise: o conteúdo vira uma
 * assinatura (URL + imagens + texto sem números) e só é reenviado se ela mudar.
 */
import { CONFIG } from '../config';
import {
  monitoramentoAtivo,
  type ContentExtractedMessage,
  type EstadoExtensao,
  type ExtractedContent,
  type RespostaAnalise,
} from '../models/content';
import { extractContent } from './extractor';
import { observeChanges } from './observer';

/** FNV-1a 32 bits: rápido e suficiente para "mudou ou não". */
function hash(texto: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16);
}

/** Números (horários, contadores, "há 2 min") não contam como mudança de conteúdo. */
export function assinatura(c: ExtractedContent): string {
  const texto = c.text.replace(/\d+/g, '#').replace(/\s+/g, ' ').slice(0, 20_000);
  const imagens = c.images.map((i) => i.src).sort().join('\n');
  return hash(`${c.url}\n${imagens}\n${texto}`);
}

export function iniciarMonitor(): void {
  let ativo = false;
  let pararObservador: (() => void) | null = null;
  let ultimaEnviada: string | null = null;
  let enviando = false;
  let repetir = false;

  async function extrairEEnviar(): Promise<void> {
    if (!ativo) return;
    if (enviando) {
      repetir = true; // já tem uma em andamento: manda a versão mais nova depois
      return;
    }
    const conteudo = extractContent();
    conteudo.text = conteudo.text.slice(0, CONFIG.maxTextChars);
    const minha = assinatura(conteudo);
    if (minha === ultimaEnviada) return; // nada de relevante mudou

    enviando = true;
    try {
      const mensagem: ContentExtractedMessage = { type: 'CONTENT_EXTRACTED', payload: conteudo, assinatura: minha };
      const resposta = (await chrome.runtime.sendMessage(mensagem)) as RespostaAnalise | undefined;
      // só marca como enviada se foi analisada: falhou (backend fora) = tenta na próxima mudança
      if (resposta?.ok) ultimaEnviada = minha;
    } catch {
      // extensão recarregada com a aba aberta: recarregue a aba
    } finally {
      enviando = false;
      if (repetir) {
        repetir = false;
        void extrairEEnviar();
      }
    }
  }

  function aplicar(estado: EstadoExtensao | undefined): void {
    const novo = monitoramentoAtivo(estado);
    if (novo === ativo) return;
    ativo = novo;
    if (ativo) {
      ultimaEnviada = null;
      pararObservador = observeChanges(() => void extrairEEnviar(), CONFIG.debounceMs, CONFIG.maxWaitMs);
      void extrairEEnviar();
    } else {
      pararObservador?.();
      pararObservador = null;
    }
  }

  chrome.storage.local.get('estado').then((d) => aplicar(d.estado as EstadoExtensao | undefined));
  chrome.storage.onChanged.addListener((mudancas, area) => {
    if (area === 'local' && mudancas.estado) aplicar(mudancas.estado.newValue as EstadoExtensao | undefined);
  });
}
