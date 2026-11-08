/**
 * Acesso ao backend (models/server.py) e sessão do usuário.
 *
 * O backend autentica com JWT próprio (POST /auth/login devolve access_token)
 * e as rotas protegidas exigem o cabeçalho "Authorization: Bearer <token>".
 * Como o backend roda em outra origem e não usa cookies, o token fica no
 * localStorage do navegador e é enviado por apiFetch() automaticamente.
 */

import { informarConexao } from "./conexao";

/** Endereço do servidor local. Troque com NEXT_PUBLIC_API_URL. */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

const CHAVE_SESSAO = "orca.sessao";
const EVENTO_SESSAO = "orca:sessao";

export type Usuario = {
  id_user: string;
  name: string | null;
  email: string;
};

export type Sessao = {
  token: string;
  usuario: Usuario;
};

/** Erro de uma chamada à API, com o status HTTP (0 = servidor fora do ar). */
export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

// ---------------------------------------------------------------- sessão

/** Lê o "exp" do JWT (sem validar a assinatura: isso é papel do backend). */
function expiraEm(token: string): number | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(base64)) as { exp?: number };
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function tokenExpirado(token: string): boolean {
  const exp = expiraEm(token);
  return exp === null || exp <= Date.now();
}

// cache para o useSyncExternalStore devolver sempre o mesmo objeto
let cacheBruto: string | null = null;
let cacheSessao: Sessao | null = null;

/** Sessão salva (ou null se não houver, estiver corrompida ou expirada). */
export function lerSessao(): Sessao | null {
  if (typeof window === "undefined") return null;
  let bruto: string | null = null;
  try {
    bruto = localStorage.getItem(CHAVE_SESSAO);
  } catch {
    return null;
  }
  if (bruto !== cacheBruto) {
    cacheBruto = bruto;
    try {
      const s = bruto ? (JSON.parse(bruto) as Sessao) : null;
      cacheSessao = s?.token && s.usuario ? s : null;
    } catch {
      cacheSessao = null;
    }
  }
  if (cacheSessao && tokenExpirado(cacheSessao.token)) return null;
  return cacheSessao;
}

function salvarSessao(sessao: Sessao | null) {
  try {
    if (sessao) localStorage.setItem(CHAVE_SESSAO, JSON.stringify(sessao));
    else localStorage.removeItem(CHAVE_SESSAO);
  } catch {
    // armazenamento bloqueado (ex.: modo privado): a sessão dura só esta aba
  }
  window.dispatchEvent(new Event(EVENTO_SESSAO));
}

/** Avisa quando a sessão muda (nesta aba ou em outra). */
export function observarSessao(aoMudar: () => void): () => void {
  const aoArmazenar = (e: StorageEvent) => {
    if (e.key === null || e.key === CHAVE_SESSAO) aoMudar();
  };
  window.addEventListener(EVENTO_SESSAO, aoMudar);
  window.addEventListener("storage", aoArmazenar);
  return () => {
    window.removeEventListener(EVENTO_SESSAO, aoMudar);
    window.removeEventListener("storage", aoArmazenar);
  };
}

export function sair() {
  salvarSessao(null);
}

// ---------------------------------------------------------------- requisições

/** Transforma o "detail" do FastAPI numa frase legível. */
function mensagemDoErro(corpo: unknown, status: number): string {
  const detail = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // erro de validação (422): [{loc: ["body", "password"], msg: "..."}]
    const campos: Record<string, string> = {
      name: "nome",
      email: "e-mail",
      password: "senha",
    };
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const campo = String(d.loc?.[d.loc.length - 1] ?? "");
        return `${campos[campo] ?? campo}: ${d.msg ?? "inválido"}`;
      })
      .join("; ");
  }
  return `Erro ${status} no servidor`;
}

type Opcoes = RequestInit & {
  /** Envia o token da sessão. Em 401 a sessão é encerrada. */
  autenticado?: boolean;
  /** Tempo máximo de espera em ms. */
  limite?: number;
};

export async function apiFetch<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const { autenticado, limite = 10_000, headers, ...resto } = opcoes;
  const cabecalhos = new Headers(headers);
  if (resto.body && !cabecalhos.has("Content-Type")) {
    cabecalhos.set("Content-Type", "application/json");
  }

  if (autenticado) {
    const sessao = lerSessao();
    if (!sessao) {
      sair();
      throw new ErroApi(401, "Sessão expirada. Entre novamente.");
    }
    cabecalhos.set("Authorization", `Bearer ${sessao.token}`);
  }

  const controle = new AbortController();
  const relogio = setTimeout(() => controle.abort(), limite);
  let resposta: Response;
  try {
    resposta = await fetch(`${API_URL}${caminho}`, {
      ...resto,
      headers: cabecalhos,
      signal: controle.signal,
      cache: "no-store",
    });
  } catch {
    informarConexao(false);
    throw new ErroApi(0, "Não foi possível conectar ao servidor.");
  } finally {
    clearTimeout(relogio);
  }
  informarConexao(true);

  const corpo: unknown = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    // token inválido/expirado: encerra a sessão para o site voltar ao login
    if (resposta.status === 401 && autenticado) sair();
    throw new ErroApi(resposta.status, mensagemDoErro(corpo, resposta.status));
  }
  return corpo as T;
}

// ---------------------------------------------------------------- autenticação

type RespostaLogin = {
  access_token: string;
  token_type: string;
  user: Usuario;
};

/**
 * O login é feito por e-mail (coluna "email" da tabela users). O backend também
 * normaliza, mas o site já envia o e-mail sem espaços e em minúsculas.
 */
export function normalizarEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Formato básico: algo@dominio.ext, sem espaços. */
export function emailValido(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/** POST /auth/login: guarda o token e o usuário na sessão. */
export async function entrar(email: string, password: string): Promise<Sessao> {
  const r = await apiFetch<RespostaLogin>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: normalizarEmail(email), password }),
  });
  const sessao = { token: r.access_token, usuario: r.user };
  salvarSessao(sessao);
  return sessao;
}

/** POST /auth/register (não devolve token; quem chama faz o login depois). */
export async function cadastrar(
  name: string,
  email: string,
  password: string,
): Promise<Usuario> {
  const r = await apiFetch<{ message: string; user: Usuario }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ name, email: normalizarEmail(email), password }),
  });
  return r.user;
}

/** GET /auth/me: confirma no backend que o token salvo ainda vale. */
export async function confirmarSessao(): Promise<Usuario> {
  const usuario = await apiFetch<Usuario>("/auth/me", { autenticado: true });
  const atual = lerSessao();
  if (atual) salvarSessao({ ...atual, usuario });
  return usuario;
}
