/**
 * Estado público da extensão (sem tokens) em chrome.storage.local, chave "estado".
 * Toda mudança atualiza o ícone (badge): ON = analisando, ! = precisa de atenção.
 */
import { ESTADO_INICIAL, monitoramentoAtivo, type EstadoExtensao } from '../models/content';

const CHAVE = 'estado';

export async function lerEstado(): Promise<EstadoExtensao> {
  const dados = await chrome.storage.local.get(CHAVE);
  return { ...ESTADO_INICIAL, ...(dados[CHAVE] as Partial<EstadoExtensao> | undefined) };
}

/** Aplica as mudanças e devolve o estado novo. */
export async function mudarEstado(mudancas: Partial<EstadoExtensao>): Promise<EstadoExtensao> {
  const novo = { ...(await lerEstado()), ...mudancas };
  await chrome.storage.local.set({ [CHAVE]: novo });
  await atualizarIcone(novo);
  return novo;
}

async function atualizarIcone(e: EstadoExtensao): Promise<void> {
  let texto = '';
  let cor = '#3fae5a';
  let titulo = 'ORCA: monitoramento desligado';

  if (e.sessao === 'expirada') {
    texto = '!';
    cor = '#cb5959';
    titulo = 'ORCA: sessão expirada. Entre no site do ORCA.';
  } else if (e.sessao === 'ausente') {
    titulo = 'ORCA: entre no site do ORCA para ativar';
  } else if (monitoramentoAtivo(e) && e.backend === 'indisponivel') {
    texto = '!';
    cor = '#dfca5a';
    titulo = 'ORCA: servidor indisponível, análises pausadas';
  } else if (monitoramentoAtivo(e)) {
    texto = 'ON';
    titulo = 'ORCA: analisando as páginas';
  }

  try {
    await chrome.action.setBadgeText({ text: texto });
    await chrome.action.setBadgeBackgroundColor({ color: cor });
    await chrome.action.setTitle({ title: titulo });
  } catch {
    // ícone é só informativo
  }
}
