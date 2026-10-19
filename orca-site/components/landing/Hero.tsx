import Image from "next/image";
import BotaoPixel from "./BotaoPixel";

const GITHUB_URL = "https://github.com/JheniferLais/PI6-ORCA";

export default function Hero() {
  return (
    <section className="hero-fundo text-white">
      <div className="px-6 pt-8 pb-24 xl:pt-[calc(48*var(--u))] xl:pr-[calc(86*var(--u))] xl:pb-[calc(210*var(--u))] xl:pl-[calc(120*var(--u))]">
        {/* Barra do topo: significado da sigla + ícone da orca */}
        <div className="flex items-center justify-end gap-3">
          <p className="text-[11px] text-white/80 xl:text-[length:calc(20*var(--u))]">
            Organization of Requests &amp; Communication Analysis
          </p>
          <Image
            src="/orca-icone.svg"
            alt=""
            width={83}
            height={67}
            unoptimized
            className="h-auto w-11 xl:w-[calc(83*var(--u))]"
          />
        </div>

        {/* Logotipo */}
        <h1 className="mt-10 xl:mt-[calc(110*var(--u))]">
          <Image
            src="/logo-orca.svg"
            alt="ORCA"
            width={516}
            height={145}
            priority
            unoptimized
            className="h-auto w-full max-w-[342px] xl:w-[calc(516*var(--u))] xl:max-w-none"
          />
        </h1>

        {/* Texto de apresentação */}
        <p className="mt-6 max-w-[68ch] text-[15px] leading-[1.25] xl:mt-[calc(24*var(--u))] xl:text-[length:calc(26*var(--u))]">
          O ORCA é um sistema que utiliza inteligência artificial,
          processamento de linguagem natural e visão computacional para
          analisar conteúdos digitais e auxiliar no controle de acesso à web.
        </p>

        {/* Botões */}
        <div className="mt-8 flex flex-wrap gap-4 xl:mt-[calc(32*var(--u))] xl:gap-[calc(16*var(--u))]">
          <BotaoPixel href="#como-funciona" icone="/icones/info.svg">
            Conheça o Projeto
          </BotaoPixel>
          <BotaoPixel href={GITHUB_URL} icone="/icones/github.svg" externo>
            Ver no Github
          </BotaoPixel>
          <BotaoPixel href="/logs" icone="/icones/log.svg">
            Log
          </BotaoPixel>
        </div>
      </div>
    </section>
  );
}
