/** Tipos e acesso aos dados da tela de logs (GET /logs, autenticado). */

import { apiFetch, ErroApi } from "./api";

export type TipoOcorrencia = "bloqueio" | "alerta";

export type Evento = {
  id: string;
  /** ISO 8601 */
  timestamp: string;
  url: string;
  /** causa da ocorrência (coluna "reason", ex.: "Conteúdo sexual") */
  categoria: string;
  /** "bloqueio" ou "alerta" (coluna "level") */
  tipo: TipoOcorrencia;
  /** valor original de "level", exibido nos detalhes */
  nivel: string;
};

/** Categorias de docs/categorias.md (aparecem no filtro mesmo sem ocorrências). */
export const CATEGORIAS = [
  "Automutilação/Suicídio",
  "Discurso de ódio/Discriminação",
  "Conteúdo sexual",
];

/** Linha da tabela "logs" do Supabase, como o backend devolve. */
type LogDoServidor = {
  id_log: string;
  timestamp: string;
  url: string;
  level: string;
  reason: string | null;
  id_user: string;
};

type PaginaDeLogs = {
  logs: LogDoServidor[];
  limit: number;
  offset: number;
};

/**
 * level -> tipo da interface. O backend grava "bloqueio" ou "alerta"
 * (models/app/decisao.py); qualquer outro valor é tratado como alerta e o
 * texto original continua visível nos detalhes.
 */
function converter(l: LogDoServidor): Evento {
  const nivel = (l.level ?? "").trim();
  return {
    id: l.id_log,
    timestamp: l.timestamp,
    url: l.url,
    categoria: l.reason?.trim() || "Sem motivo informado",
    tipo: nivel.toLowerCase() === "bloqueio" ? "bloqueio" : "alerta",
    nivel,
  };
}

// o backend aceita no máximo 100 por página
const POR_REQUISICAO = 100;
const MAXIMO_DE_LOGS = 1000;

export type Resultado =
  | { ok: true; eventos: Evento[]; limitado: boolean }
  | {
      ok: false;
      /** 401 = sessão inválida, 403 = sem permissão, 0 = servidor fora do ar */
      status: number;
      mensagem: string;
    };

/** Busca os logs do usuário logado (o backend filtra pelo id do token). */
export async function carregarEventos(): Promise<Resultado> {
  try {
    const eventos: Evento[] = [];
    for (let offset = 0; offset < MAXIMO_DE_LOGS; offset += POR_REQUISICAO) {
      const pagina = await apiFetch<PaginaDeLogs>(
        `/logs?limit=${POR_REQUISICAO}&offset=${offset}`,
        { autenticado: true },
      );
      if (!Array.isArray(pagina?.logs)) {
        throw new ErroApi(500, "Resposta inesperada do servidor.");
      }
      eventos.push(...pagina.logs.map(converter));
      if (pagina.logs.length < POR_REQUISICAO) {
        return { ok: true, eventos, limitado: false };
      }
    }
    return { ok: true, eventos, limitado: true };
  } catch (e) {
    const status = e instanceof ErroApi ? e.status : -1;
    const mensagens: Record<number, string> = {
      0: "Não foi possível carregar os logs: o servidor não respondeu.",
      401: "Sua sessão expirou. Entre novamente para ver os logs.",
      403: "Você não tem permissão para ver estes logs.",
    };
    return {
      ok: false,
      status,
      mensagem:
        mensagens[status] ??
        `Não foi possível carregar os logs${e instanceof Error ? ` (${e.message})` : ""}.`,
    };
  }
}
