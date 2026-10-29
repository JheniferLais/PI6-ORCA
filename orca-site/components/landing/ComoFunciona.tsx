import Image from "next/image";
import TituloSecao from "./TituloSecao";

type Item = { rotulo: string; texto: string };

type Etapa = {
  titulo: string;
  icone: string;
  itens: Item[];
  mascote: {
    src: string;
    largura: number; // tamanho original do arquivo
    altura: number;
    exibir: number; // largura (px) no design de 1920px
    sobra: number; // quanto passa da borda de baixo do card (fração da largura)
  };
};

const etapas: Etapa[] = [
  {
    titulo: "Captura",
    icone: "/icones/tesoura.svg",
    itens: [
      { rotulo: "Orca Extractor", texto: "Extensão de navegador" },
      {
        rotulo: "Captura de DOM",
        texto: "Imagens e Texto de todas as páginas acessadas",
      },
    ],
    mascote: { src: "/mascotes/captura.png", largura: 391, altura: 372, exibir: 360, sobra: 0.5 },
  },
  {
    titulo: "Análise",
    icone: "/icones/olho.svg",
    itens: [
      { rotulo: "Análise Textual (NLP)", texto: "Conteúdo de ódio/impróprio" },
      { rotulo: "Análise de Imagens (CV)", texto: "SFW, NSFW e NSFL" },
    ],
    mascote: { src: "/mascotes/analise.png", largura: 280, altura: 325, exibir: 300, sobra: 0.565 },
  },
  {
    titulo: "Decisão",
    icone: "/icones/varinha.svg",
    itens: [
      {
        rotulo: "Políticas e viés",
        texto: "Políticas de bloqueio, e mínimo score aceitável das IAs",
      },
    ],
    mascote: { src: "/mascotes/decisao.png", largura: 328, altura: 347, exibir: 345, sobra: 0.465 },
  },
];

function Seta() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 8 12"
      className="hidden shrink-0 self-center xl:block xl:h-[calc(16*var(--u))] xl:w-[calc(12*var(--u))]"
    >
      <path d="M0 0L8 6L0 12Z" />
    </svg>
  );
}

export default function ComoFunciona() {
  return (
    <section
      id="como-funciona"
      className="bg-white px-6 pt-16 pb-40 xl:px-[calc(110*var(--u))] xl:pt-[calc(86*var(--u))] xl:pb-[calc(200*var(--u))]"
    >
      <TituloSecao>Como funciona...</TituloSecao>

      <div className="mt-14 flex w-full flex-col gap-24 xl:mt-[calc(56*var(--u))] xl:mx-auto xl:max-w-[calc(1555*var(--u))] xl:flex-row xl:gap-[calc(38*var(--u))]">
        {etapas.map((etapa, i) => (
          <div key={etapa.titulo} className="contents">
            {i > 0 && <Seta />}

            <article className="sombra-dura relative mx-auto flex w-full max-w-[460px] flex-1 flex-col items-center border-2 border-black bg-white px-4 pt-9 pb-[150px] text-center xl:max-w-none xl:px-[calc(24*var(--u))] xl:pt-[calc(36*var(--u))] xl:pb-[calc(150*var(--u))]">
              <Image
                src={etapa.icone}
                alt=""
                width={24}
                height={24}
                unoptimized
                className="absolute top-3 left-3 h-6 w-6 xl:top-[calc(12*var(--u))] xl:left-[calc(12*var(--u))] xl:h-[calc(24*var(--u))] xl:w-[calc(24*var(--u))]"
              />

              <h3 className="font-pixel text-[26px] leading-[0.963] xl:text-[length:calc(43.65*var(--u))]">
                {etapa.titulo}
              </h3>

              <div className="mt-6 flex w-full flex-col gap-4 xl:mt-[calc(24*var(--u))] xl:gap-[calc(16*var(--u))]">
                {etapa.itens.map((item) => (
                  <div key={item.rotulo}>
                    <p className="mx-2 bg-black py-[5px] text-[14px] leading-none font-bold whitespace-nowrap text-white xl:mx-[calc(32*var(--u))] xl:py-[calc(5*var(--u))] xl:text-[length:calc(23*var(--u))]">
                      {item.rotulo}
                    </p>
                    <p className="mx-auto mt-2 max-w-[26ch] text-[13px] leading-[1.25] text-balance xl:mt-[calc(8*var(--u))] xl:text-[length:calc(23*var(--u))]">
                      {item.texto}
                    </p>
                  </div>
                ))}
              </div>

              <Image
                src={etapa.mascote.src}
                alt=""
                width={etapa.mascote.largura}
                height={etapa.mascote.altura}
                unoptimized
                style={
                  {
                    imageRendering: "pixelated",
                    "--w-xl": `calc(${etapa.mascote.exibir} * var(--u))`,
                    "--b-mobile": `calc(180px * -${etapa.mascote.sobra})`,
                    "--b-xl": `calc(${etapa.mascote.exibir} * var(--u) * -${etapa.mascote.sobra})`,
                  } as React.CSSProperties
                }
                className="absolute left-1/2 h-auto w-[180px] -translate-x-1/2 bottom-[var(--b-mobile)] xl:w-[var(--w-xl)] xl:bottom-[var(--b-xl)]"
              />
            </article>
          </div>
        ))}
      </div>
    </section>
  );
}
