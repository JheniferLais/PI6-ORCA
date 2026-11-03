/** Tipos e acesso aos dados da tela de logs. */

export type TipoOcorrencia = "bloqueio" | "alerta";

export type Evento = {
  id: string;
  /** ISO 8601 */
  timestamp: string;
  url: string;
  categoria: string;
  tipo: TipoOcorrencia;
  /** confiança do modelo, de 0 a 1 (pode não existir) */
  score: number | null;
  modalidade: string;
  modelo: string;
};

/** Endereço do servidor local (models/server.py). Troque com NEXT_PUBLIC_API_URL. */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

/** Categorias de docs/categorias.md (aparecem no filtro mesmo sem ocorrências). */
export const CATEGORIAS = [
  "Automutilação/Suicídio",
  "Discurso de ódio/Discriminação",
  "Conteúdo sexual",
];

type EventoDoServidor = {
  id: string;
  timestamp: string;
  url: string;
  category: string;
  action: TipoOcorrencia;
  score: number | null;
  modality?: string;
  model_version?: string;
};

function converter(e: EventoDoServidor): Evento {
  return {
    id: e.id,
    timestamp: e.timestamp,
    url: e.url,
    categoria: e.category,
    tipo: e.action,
    score: e.score,
    modalidade: e.modality ?? "text",
    modelo: e.model_version ?? "—",
  };
}

export type Resultado = {
  eventos: Evento[];
  /** "servidor" = dados reais; "exemplo" = servidor fora do ar, dados de mentira */
  origem: "servidor" | "exemplo";
};

export async function carregarEventos(): Promise<Resultado> {
  try {
    const controle = new AbortController();
    const limite = setTimeout(() => controle.abort(), 3000);
    const resposta = await fetch(`${API_URL}/logs`, {
      signal: controle.signal,
      cache: "no-store",
    });
    clearTimeout(limite);
    if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`);
    const dados = (await resposta.json()) as EventoDoServidor[];
    return { eventos: dados.map(converter), origem: "servidor" };
  } catch {
    return { eventos: exemplos(), origem: "exemplo" };
  }
}

/** Dados de mentira, só para a tela não ficar vazia sem o servidor. */
function exemplos(): Evento[] {
  const agora = Date.now();
  const h = 3_600_000;
  const base: [number, string, TipoOcorrencia, string, number][] = [
    [5, "Discurso de ódio/Discriminação", "alerta", "forum-exemplo.com/topico/48213/comentarios", 0.71],
    [20, "Conteúdo sexual", "bloqueio", "exemplo-adulto.com/galeria/destaques", 0.93],
    [30, "Automutilação/Suicídio", "alerta", "blog-exemplo.com.br/posts/como-lidar-com-a-tristeza", 0.64],
    [75, "Discurso de ódio/Discriminação", "bloqueio", "rede-exemplo.com/post/9981273", 0.88],
    [190, "Conteúdo sexual", "alerta", "exemplo-video.com/assistir/canal-71", 0.62],
    [75, "Discurso de ódio/Discriminação", "bloqueio", "rede-exemplo.com/post/9981273", 0.88],
    [75, "Discurso de ódio/Discriminação", "bloqueio", "rede-exemplo.com/post/9981273", 0.88],

  ];
  return base.map(([horasAtras, categoria, tipo, url, score], i) => ({
    id: `exemplo-${i}`,
    timestamp: new Date(agora - horasAtras * h).toISOString(),
    url,
    categoria,
    tipo,
    score,
    modalidade: i % 3 === 2 ? "image" : "text",
    modelo: i % 3 === 2 ? "vision-v1" : "nlp-v1",
  }));
}
