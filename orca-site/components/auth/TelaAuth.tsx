import Image from "next/image";
import Link from "next/link";
import StatusServidor from "@/components/StatusServidor";
import { IconePower, IconeVoltar } from "./Icones";

export type TemaAuth = "escuro" | "claro";

/* ------------------------------------------------------------------
   IMAGENS (coloque os arquivos em /public/auth/, veja a lista no final)
   Posições e tamanhos em px, medidos no protótipo (frame de 1440x810).
   `esq`/`topo` são relativos ao canto superior direito do card.
   ------------------------------------------------------------------ */
type Figura = { src: string; w: number; h: number; esq: number; topo: number };

const CENAS: Record<TemaAuth, { mascote: Figura; icones: Figura[] }> = {
    // Login (escuro): orca acenando + ícones "[...]" e "arquivo"
    escuro: {
        mascote: { src: "/auth/orca-login.png", w: 300, h: 320, esq: 52, topo: 157 },
        icones: [
            { src: "/auth/icone-codigo.png", w: 58, h: 43, esq: 204, topo: 94 },
            { src: "/auth/icone-arquivo.png", w: 54, h: 58, esq: 316, topo: 160 },
        ],
    },
    // Cadastro (claro): orca de óculos escrevendo + ícones "disquete" e "banco"
    claro: {
        mascote: { src: "/auth/orca-cadastro.png", w: 310, h: 334, esq: 40, topo: 144 },
        icones: [
            { src: "/auth/icone-disquete.png", w: 54, h: 55, esq: 154, topo: 92 },
            { src: "/auth/icone-banco.png", w: 52, h: 48, esq: 314, topo: 182 },
        ],
    },
};

const pixelado = "[image-rendering:pixelated]";

function Figura({ f, className = "" }: { f: Figura; className?: string }) {
    return (
        <Image
            src={f.src}
            alt=""
            width={f.w}
            height={f.h}
            unoptimized
            className={`${pixelado} size-full ${className}`}
        />
    );
}

/** Faixa de "xadrez" em pixel (quadradinhos de 6px) das pontas da linha do rodapé. */
function Xadrez({
                    colunas,
                    linhas,
                    rampa,
                }: {
    colunas: number;
    linhas: number;
    /** Quanto cada linha "recua" (cria o degrau do desenho). */
    rampa: (linha: number) => { de: number; ate: number };
}) {
    const c = 6;
    const quadrados = [];
    for (let y = 0; y < linhas; y++) {
        const { de, ate } = rampa(y);
        for (let x = de; x <= ate; x++) {
            if ((x + y) % 2 === 0) quadrados.push(<rect key={`${x}-${y}`} x={x * c} y={y * c} width={c} height={c} />);
        }
    }
    return (
        <svg
            aria-hidden
            width={colunas * c}
            height={linhas * c}
            viewBox={`0 0 ${colunas * c} ${linhas * c}`}
            shapeRendering="crispEdges"
            fill="currentColor"
            className="shrink-0"
        >
            {quadrados}
        </svg>
    );
}

/**
 * Moldura das telas de login (tema "escuro") e cadastro (tema "claro"):
 * fundo com gradiente e grade de "+", logo no canto, card com sombra
 * deslocada, mascote ao lado e a linha xadrez no rodapé.
 */
export default function TelaAuth({
                                     titulo,
                                     tema,
                                     children,
                                 }: {
    titulo: string;
    tema: TemaAuth;
    children: React.ReactNode;
}) {
    const cena = CENAS[tema];

    return (
        <main
            className={`auth-${tema} relative isolate min-h-screen overflow-hidden text-(color:--auth-fg) xl:min-h-[max(100vh,760px)]`}
        >
            <div aria-hidden className="auth-fundo absolute inset-0 -z-20" />
            <div aria-hidden className="auth-grade absolute inset-0 -z-10" />

            {/* Abaixo de 1280px tudo empilha; no desktop cada peça é posicionada. */}
            <div className="flex flex-col items-center gap-8 px-5 pt-8 pb-24 xl:block xl:p-0">
                {/* Logo */}
                <Link
                    href="/"
                    className="self-start xl:absolute xl:top-[121px] xl:left-[6vw]"
                    aria-label="ORCA, ir para o início"
                >
                    <Image
                        src="/logo-orca.svg"
                        alt="ORCA"
                        width={275}
                        height={77}
                        priority
                        unoptimized
                        className={`h-auto w-[180px] sm:w-[220px] xl:w-[275px] ${tema === "claro" ? "invert" : ""}`}
                    />
                    <span className="mt-4 block h-[7px] w-[72px] bg-(--auth-fg) sm:w-[88px] xl:mt-5 xl:w-[110px]" />
                </Link>

                {/* Card */}
                <div className="relative w-full max-w-[480px] xl:absolute xl:top-[53%] xl:left-1/2 xl:-translate-x-1/2 xl:-translate-y-1/2">
                    {/* "sombra dura": segundo card deslocado atrás */}
                    <div
                        aria-hidden
                        className="absolute inset-0 translate-x-2 translate-y-2 border border-(color:--auth-sombra-borda) bg-(--auth-sombra-bg)"
                    />
                    <section className="relative min-h-[402px] border-2 border-(color:--auth-fg) bg-(--auth-bg) px-6 pt-[38px] pb-9 text-(color:--auth-fg) sm:px-[72px]">
                        {/* Controles no topo, à direita */}
                        <div className="absolute top-[6px] right-[7px] flex">
                            <Link
                                href="/"
                                aria-label="Voltar para o início"
                                className="grid size-6 place-items-center focus-visible:outline-2 focus-visible:outline-(color:--auth-fg)"
                            >
                                <IconeVoltar className="size-[14px]" />
                            </Link>
                            <Link
                                href="/"
                                aria-label="Sair para o início"
                                className="grid size-6 place-items-center focus-visible:outline-2 focus-visible:outline-(color:--auth-fg)"
                            >
                                <IconePower className="size-[14px]" />
                            </Link>
                        </div>

                        <h1 className="font-pixel text-center text-[25px] leading-9">{titulo}</h1>
                        <div className="mx-auto mt-1 h-1 w-[55px] bg-(--auth-fg)" />

                        <div className="mt-[25px]">{children}</div>
                    </section>

                    {/* Mascote e ícones flutuantes (só no desktop), posicionados a partir do canto direito do card */}
                    {[cena.mascote, ...cena.icones].map((f) => (
                        <div
                            key={f.src}
                            aria-hidden
                            className="pointer-events-none absolute hidden xl:block"
                            style={{ left: `calc(100% + ${f.esq}px)`, top: f.topo, width: f.w, height: f.h }}
                        >
                            <Figura f={f} />
                        </div>
                    ))}
                </div>

                {/* Mascote menor, abaixo do card, quando não cabe ao lado */}
                <Image
                    src={cena.mascote.src}
                    alt=""
                    width={cena.mascote.w}
                    height={cena.mascote.h}
                    unoptimized
                    className={`${pixelado} h-auto w-[170px] sm:w-[200px] xl:hidden`}
                />
            </div>

            {/* Linha xadrez do rodapé */}
            <div
                aria-hidden
                className="absolute right-[6vw] bottom-10 left-[6vw] hidden items-start md:flex xl:right-[10vw] xl:bottom-[60px] xl:left-[9.5vw]"
            >
                <Xadrez colunas={12} linhas={4} rampa={(l) => ({ de: (3 - l) * 2, ate: 11 })} />
                <div className="h-px flex-1 bg-(--auth-fg)" />
                <Xadrez colunas={11} linhas={2} rampa={(l) => ({ de: 0, ate: 10 - l * 3 })} />
            </div>

            <StatusServidor />
        </main>
    );
}