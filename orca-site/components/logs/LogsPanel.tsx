"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "@/components/auth/AuthProvider";
import {
  CATEGORIAS,
  carregarEventos,
  type Evento,
  type TipoOcorrencia,
} from "@/lib/logs";
import PixelIcon, { ICONES, Triangulo } from "./PixelIcon";
import "./logs.css";

// s.numero -> "logs-numero" (o projeto usa o plugin do Tailwind, que não suporta CSS Modules)
const s = new Proxy({} as Record<string, string>, {
  get: (_, nome) => `logs-${String(nome)}`,
});

// Em telas pequenas a página rola normalmente e mostra 5 por vez; no desktop
// a tela não rola e cabe na lista quantas ocorrências couberem na altura.
const POR_PAGINA_MOBILE = 5;
const ALTURA_ITEM_PADRAO = 70;
const MINIMO_POR_PAGINA = 4;
const MAXIMO_POR_PAGINA = 5;
// borda (2+2) + espaço acima (6) e abaixo (52, rodapé e paginação) da lista
const MOLDURA_DA_LISTA = 62;
const ATUALIZA_A_CADA_MS = 5000;

type FiltroTipo = "todos" | TipoOcorrencia;

const PERIODOS = [
  { valor: "24h", rotulo: "Últimas 24 horas", horas: 24 },
  { valor: "7d", rotulo: "Últimos 7 dias", horas: 24 * 7 },
  { valor: "30d", rotulo: "Últimos 30 dias", horas: 24 * 30 },
  { valor: "tudo", rotulo: "Todo o período", horas: Infinity },
] as const;

// 1234 -> "1.234"
function formatarNumero(n: number) {
  return n.toLocaleString("pt-BR");
}

function formatarData(iso: string) {
  const d = new Date(iso);
  return {
    dia: d.toLocaleDateString("pt-BR"),
    hora: d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
  };
}

export default function LogsPanel() {
  const { sessao, sairDaConta } = useAuth();
  // últimos logs recebidos do servidor (null = ainda não chegou nenhum)
  const [dados, setDados] = useState<{ eventos: Evento[]; limitado: boolean; em: number } | null>(
    null,
  );
  // mensagem da última falha (some quando uma busca der certo)
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [tipo, setTipo] = useState<FiltroTipo>("todos");
  const [categoria, setCategoria] = useState("");
  const [periodo, setPeriodo] = useState<(typeof PERIODOS)[number]["valor"]>("7d");
  const [pagina, setPagina] = useState(1);
  const [aberto, setAberto] = useState<string | null>(null);
  const [porPagina, setPorPagina] = useState(POR_PAGINA_MOBILE);
  const itensRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);
  const carregado = dados !== null;

  // Calcula quantas ocorrências cabem na lista sem rolar a página.
  useEffect(() => {
    // a lista tem a altura do conteúdo; "area" é o espaço máximo que ela pode ocupar
    const area = areaRef.current;
    const el = itensRef.current;
    if (!area || !el) return;
    const mobile = window.matchMedia("(max-width: 900px)");
    function medir() {
      if (!area || !el) return;
      if (mobile.matches) {
        setPorPagina(POR_PAGINA_MOBILE);
        return;
      }
      const linha = el.querySelector<HTMLElement>(".logs-linha");
      const alturaItem = linha ? linha.offsetHeight + 2 : ALTURA_ITEM_PADRAO;
      const cabem = Math.floor((area.clientHeight - MOLDURA_DA_LISTA) / alturaItem);
      setPorPagina(Math.min(MAXIMO_POR_PAGINA, Math.max(MINIMO_POR_PAGINA, cabem)));
    }
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(area);
    mobile.addEventListener("change", medir);
    return () => {
      observador.disconnect();
      mobile.removeEventListener("change", medir);
    };
  }, [carregado]);

  // Busca os eventos ao abrir a tela e de novo a cada 5 segundos.
  useEffect(() => {
    let ativo = true;
    async function atualizar() {
      const resultado = await carregarEventos();
      if (!ativo) return;
      if (resultado.ok) {
        setDados({ eventos: resultado.eventos, limitado: resultado.limitado, em: Date.now() });
        setErro(null);
      } else {
        // 401 já encerrou a sessão (a página volta para o login); nos demais
        // casos avisa e mantém só o que já veio do servidor, sem dados de exemplo
        setErro(resultado.mensagem);
      }
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

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / porPagina));
  const paginaAtual = Math.min(pagina, totalPaginas);
  const visiveis = filtrados.slice(
    (paginaAtual - 1) * porPagina,
    paginaAtual * porPagina,
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
            src="/orca_black_svg.svg"
            alt=""
            width={43}
            height={37}
            unoptimized
            className={s.logo}
          />
          <div className={s.acoes}>
            {sessao && (
              <span className={s.usuario} title={sessao.usuario.email}>
                {sessao.usuario.name || sessao.usuario.email}
              </span>
            )}
            <Link href="/" className={s.sair}>
              Início
            </Link>
            <button type="button" className={s.sair} onClick={sairDaConta}>
              Sair
            </button>
            <button type="button" className={s.config} aria-label="Configurações">
              <Image src="/icones/ic/settings_svg.svg" alt="" width={24} height={24} unoptimized />
            </button>
          </div>
        </header>

        <p className={s.periodoResumo}>
          Período: {PERIODOS.find((p) => p.valor === periodo)!.rotulo.toLowerCase()}
        </p>
        <section className={s.numeros} aria-label="Resumo">
          <div className={s.numero}>
            <div>
              <strong>{formatarNumero(base.length)}</strong>
              <span>Ocorrências</span>
            </div>
            <PixelIcon desenho={ICONES.funil} />
          </div>
          <div className={`${s.numero} ${s.numeroBloqueio}`}>
            <div>
              <strong>{formatarNumero(bloqueios)}</strong>
              <span>Bloqueios</span>
            </div>
            <Image src="/icones/ic/block_svg.svg" alt="" width={44} height={44} unoptimized />
          </div>
          <div className={`${s.numero} ${s.numeroAlerta}`}>
            <div>
              <strong>{formatarNumero(alertas)}</strong>
              <span>Alertas</span>
            </div>
            <Image src="/icones/ic/alert_svg.svg" alt="" width={44} height={44} unoptimized />
          </div>
        </section>

        <div className={s.filtros}>
          <div className={s.campoBusca}>
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
          </div>

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
              <Image
                src="/icones/ic/calendar_svg.svg"
                alt=""
                width={24}
                height={24}
                unoptimized
                className={s.iconeEsq}
              />
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

        <div className={s.area} ref={areaRef}>
          <section className={s.lista} aria-label="Ocorrências">
            <div className={s.itens} ref={itensRef}>
              {dados === null && erro && (
                <p className={s.vazio} role="alert">
                  Não foi possível carregar os logs.
                </p>
              )}
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
            </div>

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

      <StatusConexao
        estado={erro ? "erro" : dados === null ? "carregando" : "conectado"}
        detalhe={
          erro ??
          (dados?.limitado
            ? `Exibindo os ${formatarNumero(dados.eventos.length)} registros mais recentes.`
            : undefined)
        }
      />
    </div>
  );
}

/** Bolinha no canto inferior direito: verde = conectado, vermelha = falhou. */
function StatusConexao({
  estado,
  detalhe,
}: {
  estado: "carregando" | "conectado" | "erro";
  detalhe?: string;
}) {
  const texto = {
    carregando: "Conectando ao servidor...",
    conectado: "Conectado ao servidor",
    erro: "Sem conexão com o servidor",
  }[estado];
  const completo = detalhe ? `${texto}. ${detalhe}` : texto;
  const cor = { carregando: s.statusCarregando, conectado: s.statusOk, erro: s.statusErro }[
    estado
  ];
  return (
    <span className={`${s.status} ${cor}`} role="status" title={completo} aria-label={completo} />
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
          <Image
            src={bloqueio ? "/icones/ic/block_svg.svg" : "/icones/ic/alert_svg.svg"}
            alt=""
            width={44}
            height={44}
            unoptimized
          />
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
            <dt>Motivo</dt>
            <dd>{e.categoria}</dd>
          </div>
          <div>
            <dt>Nível</dt>
            <dd>{e.nivel || "—"}</dd>
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
