/**
 * Chamadas ao backend com a sessão da extensão.
 *
 *  - O access token é renovado ANTES de vencer (POST /auth/refresh), e de novo
 *    se o backend recusar com 401. Só uma renovação por vez (o backend derruba a
 *    sessão se o mesmo refresh token for usado duas vezes).
 *  - Se a renovação for recusada, os tokens são apagados: a sessão acabou.
 */
import { CONFIG } from '../config';
import { tokenExpirado } from '../utils/token';
import { apagarCredenciais, lerCredenciais, salvarCredenciais } from './credenciais';

/** Falha numa chamada: status HTTP, ou 0 = backend fora do ar / sem resposta. */
export class ErroBackend extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

export interface UsuarioApi {
  id_user: string;
  name: string | null;
  email: string;
  monitoring_enabled: boolean;
}

interface RespostaTokens {
  access_token: string;
  refresh_token: string;
  user: UsuarioApi;
}

/** Renova quando falta menos que isso para o access token vencer. */
const RENOVAR_ANTES_MS = 2 * 60_000;

// muda a cada logout: uma renovação que termina depois do logout é descartada
let geracao = 0;
let renovacao: Promise<string> | null = null;

async function requisitar(caminho: string, init: RequestInit, limiteMs = 10_000): Promise<Response> {
  try {
    return await fetch(`${CONFIG.apiUrl}${caminho}`, {
      ...init,
      cache: 'no-store',
      signal: AbortSignal.timeout(limiteMs),
    });
  } catch {
    throw new ErroBackend(0, 'Servidor do ORCA indisponível');
  }
}

export async function guardarTokens(r: RespostaTokens): Promise<void> {
  await salvarCredenciais({ access: r.access_token, refresh: r.refresh_token });
}

/** Esquece a sessão local (sem falar com o backend). */
export async function esquecerSessao(): Promise<void> {
  geracao++;
  await apagarCredenciais();
}

/** POST /auth/refresh com rotação. Devolve o access token novo. */
export function renovar(): Promise<string> {
  if (!renovacao) {
    renovacao = (async () => {
      const minhaGeracao = geracao;
      const atual = await lerCredenciais();
      if (!atual) throw new ErroBackend(401, 'Sem sessão');
      const resposta = await requisitar('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: atual.refresh }),
      });
      if (resposta.status === 401) {
        await esquecerSessao();
        throw new ErroBackend(401, 'Sessão expirada');
      }
      if (!resposta.ok) throw new ErroBackend(resposta.status, `Erro ${resposta.status} ao renovar a sessão`);
      const r = (await resposta.json()) as RespostaTokens;
      if (minhaGeracao !== geracao) throw new ErroBackend(401, 'Sessão encerrada'); // logout no meio
      await guardarTokens(r);
      return r.access_token;
    })().finally(() => {
      renovacao = null;
    });
  }
  return renovacao;
}

async function tokenValido(): Promise<string> {
  const atual = await lerCredenciais();
  if (!atual) throw new ErroBackend(401, 'Sem sessão');
  if (!tokenExpirado(atual.access, RENOVAR_ANTES_MS)) return atual.access;
  return renovar();
}

/** Chamada autenticada. Em 401, renova uma vez e tenta de novo; se ainda falhar, a sessão acabou. */
export async function chamar(caminho: string, init: RequestInit = {}, limiteMs?: number): Promise<Response> {
  const comToken = (token: string) => {
    const cabecalhos = new Headers(init.headers);
    cabecalhos.set('Authorization', `Bearer ${token}`);
    if (init.body && !cabecalhos.has('Content-Type')) cabecalhos.set('Content-Type', 'application/json');
    return requisitar(caminho, { ...init, headers: cabecalhos }, limiteMs);
  };

  let resposta = await comToken(await tokenValido());
  if (resposta.status === 401) {
    resposta = await comToken(await renovar());
    if (resposta.status === 401) {
      await esquecerSessao();
      throw new ErroBackend(401, 'Sessão encerrada');
    }
  }
  return resposta;
}

/** Garante um access token válido (usado pela sincronização periódica). */
export async function manterSessao(): Promise<void> {
  await tokenValido();
}

export async function lerUsuario(): Promise<UsuarioApi> {
  const resposta = await chamar('/auth/me');
  if (!resposta.ok) throw new ErroBackend(resposta.status, `Erro ${resposta.status} em /auth/me`);
  return (await resposta.json()) as UsuarioApi;
}

/** Troca o access token do site por uma sessão própria da extensão. */
export async function criarSessaoDaExtensao(tokenDoSite: string): Promise<UsuarioApi> {
  const minhaGeracao = geracao;
  const resposta = await requisitar('/auth/extension-session', {
    method: 'POST',
    headers: { Authorization: `Bearer ${tokenDoSite}` },
  });
  if (!resposta.ok) throw new ErroBackend(resposta.status, `Erro ${resposta.status} ao vincular a extensão`);
  const r = (await resposta.json()) as RespostaTokens;
  if (minhaGeracao !== geracao) throw new ErroBackend(401, 'Sessão encerrada');
  await guardarTokens(r);
  return r.user;
}

/**
 * POST /auth/logout com o refresh token (funciona mesmo com o access vencido).
 * todas = true encerra também a sessão do site. Sempre apaga os tokens locais.
 */
export async function encerrarSessao(todas: boolean): Promise<void> {
  const atual = await lerCredenciais();
  await esquecerSessao();
  if (!atual) return;
  try {
    await requisitar('/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: atual.refresh, all: todas }),
    });
  } catch {
    // backend fora do ar: os tokens locais já foram apagados
  }
}

export async function definirMonitoramentoNoBackend(ligado: boolean): Promise<boolean> {
  const resposta = await chamar('/monitoring', { method: 'PUT', body: JSON.stringify({ enabled: ligado }) });
  if (!resposta.ok) throw new ErroBackend(resposta.status, `Erro ${resposta.status} ao alterar o monitoramento`);
  return ((await resposta.json()) as { enabled: boolean }).enabled;
}
