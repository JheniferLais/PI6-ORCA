"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  CATEGORIAS,
  carregarEventos,
  type Evento,
  type Resultado,
  type TipoOcorrencia,
} from "@/lib/logs";
import PixelIcon, { ICONES, Triangulo } from "./PixelIcon";
import "./logs.css";

// s.numero -> "logs-numero" (o projeto usa o plugin do Tailwind, que não suporta CSS Modules)
const s = new Proxy({} as Record<string, string>, {
  get: (_, nome) => `logs-${String(nome)}`,
});

const POR_PAGINA = 5;
const ATUALIZA_A_CADA_MS = 5000;

type FiltroTipo = "todos" | TipoOcorrencia;

const PERIODOS = [
  { valor: "24h", rotulo: "Últimas 24 horas", horas: 24 },
  { valor: "7d", rotulo: "Últimos 7 dias", horas: 24 * 7 },
  { valor: "30d", rotulo: "Últimos 30 dias", horas: 24 * 30 },
  { valor: "tudo", rotulo: "Todo o período", horas: Infinity },
] as const;

function formatarData(iso: string) {
  const d = new Date(iso);
  return {
    dia: d.toLocaleDateString("pt-BR"),
    hora: d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
  };
}

export default function LogsPanel() {
  const [dados, setDados] = useState<(Resultado & { em: number }) | null>(null);
  const [busca, setBusca] = useState("");
  const [tipo, setTipo] = useState<FiltroTipo>("todos");
  const [categoria, setCategoria] = useState("");
  const [periodo, setPeriodo] = useState<(typeof PERIODOS)[number]["valor"]>("7d");
  const [pagina, setPagina] = useState(1);
  const [aberto, setAberto] = useState<string | null>(null);

  // Busca os eventos ao abrir a tela e de novo a cada 5 segundos.
  useEffect(() => {
    let ativo = true;
    async function atualizar() {
      const resultado = await carregarEventos();
      if (ativo) setDados({ ...resultado, em: Date.now() });
    }
    void atualizar();
    const relogio = setInterval(() => void atualizar(), ATUALIZA_A_CADA_MS);
    return () => {
      ativo = false;
      clearInterval(relogio);
    };
  }, []);

  // Filtros de busca, categoria e período (a contagem dos cartões usa estes).
  const base = useMemo(() => {
    if (!dados) return [];
    const horas = PERIODOS.find((p) => p.valor === periodo)!.horas;
    // "em" = momento da última busca (o período é contado a partir dele)
    const corte = dados.em - horas * 3_600_000;
    const termo = busca.trim().toLowerCase();
    return dados.eventos
      .filter((e) => new Date(e.timestamp).getTime() >= corte)
      .filter((e) => !categoria || e.categoria === categoria)
      .filter(
        (e) =>
          !termo ||
          e.url.toLowerCase().includes(termo) ||
          e.categoria.toLowerCase().includes(termo),
      )
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [dados, busca, categoria, periodo]);

  const bloqueios = base.filter((e) => e.tipo === "bloqueio").length;
  const alertas = base.length - bloqueios;
  const filtrados = tipo === "todos" ? base : base.filter((e) => e.tipo === tipo);

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / POR_PAGINA));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const visiveis = filtrados.slice(
    (paginaAtual - 1) * POR_PAGINA,
    paginaAtual * POR_PAGINA,
  );

  const categorias = useMemo(() => {
    const extras = (dados?.eventos ?? [])
      .map((e) => e.categoria)
      .filter((c) => !CATEGORIAS.includes(c));
    return [...CATEGORIAS, ...new Set(extras)];
  }, [dados]);

  // Mudar qualquer filtro volta para a página 1.
  function mudar<T>(definir: (v: T) => void) {
    return (valor: T) => {
      definir(valor);
      setPagina(1);
      setAberto(null);
    };
  }

  return (
    <div className={s.pagina}>
      <div className={s.conteudo}>
        <header className={s.topo}>
          <Link href="/" className={s.marca}>
            ORCA <Triangulo direcao="direita" /> histórico de alertas
          </Link>
          <Image
            src="/orca-icone.svg"
            alt=""
            width={83}
            height={67}
            unoptimized
            className={s.logo}
          />
          <button type="button" className={s.config} aria-label="Configurações">
            <PixelIcon desenho={ICONES.engrenagem} />
          </button>
        </header>

        <section className={s.numeros} aria-label="Resumo">
          <div className={s.numero}>
            <div>
              <strong>{base.length}</strong>
              <span>Ocorrências</span>
            </div>
            <PixelIcon desenho={ICONES.funil} />
          </div>
          <div className={`${s.numero} ${s.numeroBloqueio}`}>
            <div>
              <strong>{bloqueios}</strong>
              <span>Bloqueios</span>
            </div>
            <PixelIcon desenho={ICONES.bloqueio} />
          </div>
          <div className={`${s.numero} ${s.numeroAlerta}`}>
            <div>
              <strong>{alertas}</strong>
              <span>Alertas</span>
            </div>
            <PixelIcon desenho={ICONES.alerta} />
          </div>
        </section>

        <label className={s.rotulo} htmlFor="busca">
          Busca por ocorrência
        </label>
        <input
          id="busca"
          type="search"
          className={s.busca}
          placeholder="Buscar por URL ou categoria..."
          value={busca}
          onChange={(e) => mudar(setBusca)(e.target.value)}
        />

        <div className={s.filtros}>
          <div>
            <span className={s.rotulo}>Tipo de ocorrência</span>
            <div className={s.grupo} role="group" aria-label="Tipo de ocorrência">
              {(
                [
                  ["todos", "Todos"],
                  ["bloqueio", "Bloqueios"],
                  ["alerta", "Alertas"],
                ] as const
              ).map(([valor, rotulo]) => (
                <button
                  key={valor}
                  type="button"
                  aria-pressed={tipo === valor}
                  className={`${s.opcao} ${tipo === valor ? s.opcaoAtiva : ""}`}
                  onClick={() => mudar(setTipo)(valor)}
                >
                  {rotulo}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className={s.rotulo} htmlFor="categoria">
              Categoria
            </label>
            <div className={s.selecao}>
              <select
                id="categoria"
                value={categoria}
                onChange={(e) => mudar(setCategoria)(e.target.value)}
              >
                <option value="">Todas as categorias</option>
                {categorias.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
              <Triangulo direcao="baixo" className={s.seta} />
            </div>
          </div>

          <div>
            <label className={s.rotulo} htmlFor="periodo">
              Período
            </label>
            <div className={`${s.selecao} ${s.selecaoComIcone}`}>
              <PixelIcon desenho={ICONES.calendario} className={s.iconeEsq} />
              <select
                id="periodo"
                value={periodo}
                onChange={(e) =>
                  mudar(setPeriodo)(e.target.value as (typeof PERIODOS)[number]["valor"])
                }
              >
                {PERIODOS.map((p) => (
                  <option key={p.valor} value={p.valor}>
                    {p.rotulo}
                  </option>
                ))}
              </select>
              <Triangulo direcao="baixo" className={s.seta} />
            </div>
          </div>
        </div>

        <p className={s.estado} role="status">
          {dados === null
            ? "Carregando..."
            : dados.origem === "servidor"
              ? "● Conectado ao servidor local. A lista atualiza sozinha."
              : "○ Servidor local fora do ar: mostrando dados de exemplo."}
        </p>

        <section className={s.lista} aria-label="Ocorrências">
          {dados !== null && visiveis.length === 0 && (
            <p className={s.vazio}>Nenhuma ocorrência encontrada.</p>
          )}

          {visiveis.map((e) => (
            <ItemOcorrencia
              key={e.id}
              evento={e}
              aberto={aberto === e.id}
              alternar={() => setAberto(aberto === e.id ? null : e.id)}
            />
          ))}

          <p className={s.rodape}>
            Exibindo {visiveis.length} de {filtrados.length} ocorrências
          </p>

          <nav className={s.paginacao} aria-label="Páginas">
            <button
              type="button"
              aria-label="Página anterior"
              disabled={paginaAtual <= 1}
              onClick={() => setPagina(paginaAtual - 1)}
            >
              <Triangulo direcao="esquerda" />
            </button>
            <span aria-current="page">{paginaAtual}</span>
            <button
              type="button"
              aria-label="Próxima página"
              disabled={paginaAtual >= totalPaginas}
              onClick={() => setPagina(paginaAtual + 1)}
            >
              <Triangulo direcao="direita" />
            </button>
          </nav>
        </section>
      </div>
    </div>
  );
}

function ItemOcorrencia({
  evento: e,
  aberto,
  alternar,
}: {
  evento: Evento;
  aberto: boolean;
  alternar: () => void;
}) {
  const bloqueio = e.tipo === "bloqueio";
  const cor = bloqueio ? s.vermelho : s.amarelo;
  const { dia, hora } = formatarData(e.timestamp);

  return (
    <article className={`${s.item} ${aberto ? s.aberto : ""}`}>
      <button
        type="button"
        className={s.linha}
        aria-expanded={aberto}
        onClick={alternar}
      >
        <span className={`${s.selo} ${cor}`}>
          <PixelIcon desenho={bloqueio ? ICONES.bloqueio : ICONES.alerta} />
        </span>
        <span className={s.texto}>
          <span className={s.titulo}>
            {e.categoria}
            <span className={`${s.tag} ${cor}`}>{bloqueio ? "Bloqueado" : "Alerta"}</span>
          </span>
          <span className={s.url} style={{ display: "block" }}>
            {e.url}
          </span>
        </span>
        <span className={s.quando}>
          <strong>{dia}</strong>
          <span>{hora}</span>
        </span>
        <Triangulo direcao="direita" className={s.abrir} />
      </button>

      {aberto && (
        <dl className={s.detalhes}>
          <div>
            <dt>Confiança</dt>
            <dd>{e.score === null ? "—" : `${Math.round(e.score * 100)}%`}</dd>
          </div>
          <div>
            <dt>Tipo de análise</dt>
            <dd>{e.modalidade === "image" ? "Imagem" : "Texto"}</dd>
          </div>
          <div>
            <dt>Modelo</dt>
            <dd>{e.modelo}</dd>
          </div>
          <div>
            <dt>Ação</dt>
            <dd>{bloqueio ? "Página bloqueada" : "Responsável alertado"}</dd>
          </div>
        </dl>
      )}
    </article>
  );
}
