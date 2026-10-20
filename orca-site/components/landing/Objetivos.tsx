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
  { titulo: "Conteúdo NSFW", texto: "Imagens de cunho sexual" },
  { titulo: "Conteúdo NSFL", texto: "Violência e cenas perturbadoras" },
];

export default function Objetivos() {
  return (
    <section
      id="objetivos"
      className="bg-white px-6 pt-8 pb-24 xl:px-[calc(110*var(--u))] xl:pt-[calc(95*var(--u))] xl:pb-[calc(150*var(--u))]"
    >
      <TituloSecao>Objetivos</TituloSecao>

      <p className="mt-10 flex items-center gap-3 text-[16px] font-bold xl:mt-[calc(60*var(--u))] xl:gap-[calc(12*var(--u))] xl:text-[length:calc(26*var(--u))]">
        Mais segurança para explorar a internet.
        <Image
          src="/icones/brilho.svg"
          alt=""
          width={27}
          height={27}
          unoptimized
          className="h-5 w-5 xl:h-[calc(27*var(--u))] xl:w-[calc(27*var(--u))]"
        />
      </p>

      <div className="mt-4 flex items-center gap-2 xl:mt-[calc(18*var(--u))] xl:ml-[calc(20*var(--u))] xl:gap-[calc(10*var(--u))]">
        <svg
          aria-hidden
          viewBox="0 0 8 12"
          className="hidden shrink-0 xl:block xl:h-[calc(16*var(--u))] xl:w-[calc(12*var(--u))]"
        >
          <path d="M0 0L8 6L0 12Z" />
        </svg>
        <p className="border-l-2 border-black pl-3 text-[15px] leading-snug xl:max-w-[calc(1355*var(--u))] xl:pl-[calc(18*var(--u))] xl:text-[length:calc(26*var(--u))] xl:leading-[0.963]">
          O ORCA busca ampliar as ferramentas de controle parental por meio de
          inteligência artificial, ajudando responsáveis a monitorar e
          controlar o acesso de crianças a conteúdos digitais.
        </p>
      </div>

      <div className="mt-12 grid gap-14 xl:mt-[calc(52*var(--u))] xl:mx-auto xl:max-w-[calc(1519*var(--u))] xl:grid-cols-2 xl:gap-x-[calc(76*var(--u))] xl:gap-y-[calc(67*var(--u))]">
        {alvos.map((alvo) => (
          <div key={alvo.titulo} className="relative">
            {/* contorno deslocado, atrás da caixa preta */}
            <span
              aria-hidden
              className="absolute inset-0 -translate-x-[6px] translate-y-[6px] border-2 border-black bg-white xl:-translate-x-[calc(9*var(--u))] xl:translate-y-[calc(9*var(--u))]"
            />
            <div className="relative flex h-44 flex-col items-center justify-center gap-2 overflow-hidden bg-black px-4 text-center text-white xl:h-[calc(331*var(--u))]">
              {alvo.imagem && (
                <Image
                  src={alvo.imagem}
                  alt=""
                  fill
                  unoptimized
                  className="object-cover"
                />
              )}
              <h3 className="relative font-pixel text-[24px] xl:text-[length:calc(40*var(--u))]">
                {alvo.titulo}
              </h3>
              <p className="relative text-[13px] text-white/80 xl:text-[length:calc(20*var(--u))]">
                {alvo.texto}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
