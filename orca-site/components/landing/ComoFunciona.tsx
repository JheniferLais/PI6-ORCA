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
    exibir: number; // largura (px) na tela
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
    mascote: { src: "/mascotes/captura.png", largura: 391, altura: 372, exibir: 180, sobra: 0.5 },
  },
  {
    titulo: "Análise",
    icone: "/icones/olho.svg",
    itens: [
      { rotulo: "Análise Textual (NLP)", texto: "Conteúdo de ódio/impróprio" },
      { rotulo: "Análise de Imagens (CV)", texto: "SFW, NSFW e NSFL" },
    ],
    mascote: { src: "/mascotes/analise.png", largura: 280, altura: 325, exibir: 150, sobra: 0.565 },
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
    mascote: { src: "/mascotes/decisao.png", largura: 328, altura: 347, exibir: 172, sobra: 0.465 },
  },
];

function Seta() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 8 12"
      className="hidden h-4 w-3 shrink-0 self-center lg:block"
    >
      <path d="M0 0L8 6L0 12Z" />
    </svg>
  );
}

export default function ComoFunciona() {
  return (
    <section id="como-funciona" className="bg-white">
      <div className="mx-auto max-w-6xl px-4 pt-16 pb-32 sm:px-6 md:pt-24 md:pb-40 lg:px-8">
        <TituloSecao>Como funciona...</TituloSecao>

        <div className="mt-12 flex w-full flex-col gap-28 lg:flex-row lg:gap-6">
          {etapas.map((etapa, i) => (
            <div key={etapa.titulo} className="contents">
              {i > 0 && <Seta />}

              <article className="sombra-dura relative mx-auto flex w-full max-w-md flex-1 flex-col items-center border-2 border-black bg-white px-4 pt-8 pb-28 text-center lg:max-w-none">
                <Image
                  src={etapa.icone}
                  alt=""
                  width={24}
                  height={24}
                  unoptimized
                  className="absolute top-3 left-3 h-6 w-6"
                />

                <h3 className="font-pixel text-2xl leading-none md:text-3xl">
                  {etapa.titulo}
                </h3>

                <div className="mt-6 flex w-full flex-col gap-4">
                  {etapa.itens.map((item) => (
                    <div key={item.rotulo}>
                      <p className="mx-4 bg-black py-1 text-sm leading-tight font-bold whitespace-nowrap text-white">
                        {item.rotulo}
                      </p>
                      <p className="mx-auto mt-2 max-w-[26ch] text-sm leading-snug text-balance">
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
                  style={{
                    imageRendering: "pixelated",
                    width: etapa.mascote.exibir,
                    bottom: -etapa.mascote.exibir * etapa.mascote.sobra,
                  }}
                  className="absolute left-1/2 h-auto -translate-x-1/2"
                />
              </article>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
