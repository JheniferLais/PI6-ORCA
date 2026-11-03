import Image from "next/image";
import TituloSecao from "./TituloSecao";

type Alvo = {
  titulo: string;
  texto: string;
  /** Quando o time tiver a imagem, coloque o caminho aqui (ex.: "/objetivos/odio.png"). */
  imagem?: string;
};

// PROVISÓRIO: categorias deduzidas da seção "Análise". Troque pelas do projeto.
const alvos: Alvo[] = [
  { titulo: "Discurso de ódio", texto: "Texto ofensivo e discriminatório" },
  { titulo: "Linguagem imprópria", texto: "Palavrões e conteúdo inadequado" },
  { titulo: "Conteúdo sexual", texto: "Imagens de cunho sexual" },
  { titulo: "Violência extrema", texto: "Cenas violentas e perturbadoras" },
];

export default function Objetivos() {
  return (
    <section id="objetivos" className="bg-white">
      <div className="w-full px-6 pt-8 pb-20 sm:px-10 md:pt-12 md:pb-24 lg:px-16">
        <TituloSecao>Objetivos</TituloSecao>

        <p className="mt-10 flex items-center gap-2 text-lg font-bold">
          Mais segurança para explorar a internet.
          <Image
            src="/icones/brilho.svg"
            alt=""
            width={27}
            height={27}
            unoptimized
            className="h-5 w-5"
          />
        </p>

        <div className="mt-4 flex items-center gap-2 md:ml-4">
          <svg
            aria-hidden
            viewBox="0 0 8 12"
            className="hidden h-4 w-3 shrink-0 md:block"
          >
            <path d="M0 0L8 6L0 12Z" />
          </svg>
          <p className="max-w-3xl border-l-2 border-black pl-3 text-base leading-relaxed">
            O ORCA busca ampliar as ferramentas de controle parental por meio de
            inteligência artificial, ajudando responsáveis a monitorar e
            controlar o acesso de crianças a conteúdos digitais.
          </p>
        </div>

        <div className="mt-12 grid gap-10 md:grid-cols-2 md:gap-x-12 lg:gap-x-16 lg:px-8">
          {alvos.map((alvo) => (
            <div key={alvo.titulo} className="relative">
              {/* contorno deslocado, atrás da caixa preta */}
              <span
                aria-hidden
                className="absolute inset-0 -translate-x-1.5 translate-y-1.5 border-2 border-black bg-white"
              />
              <div className="relative flex h-44 flex-col items-center justify-center gap-2 overflow-hidden bg-black px-4 text-center text-white md:h-52">
                {alvo.imagem && (
                  <Image
                    src={alvo.imagem}
                    alt=""
                    fill
                    unoptimized
                    className="object-cover"
                  />
                )}
                <h3 className="relative font-pixel text-2xl md:text-3xl">
                  {alvo.titulo}
                </h3>
                <p className="relative text-sm text-white/80">{alvo.texto}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
