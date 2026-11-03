import Image from "next/image";
import BotaoPixel from "./BotaoPixel";

const GITHUB_URL = "https://github.com/JheniferLais/PI6-ORCA";

export default function Hero() {
  return (
    <section className="hero-fundo text-white">
      <div className="w-full px-6 pt-6 pb-20 sm:px-10 md:pb-28 lg:px-16">
        {/* Barra do topo: significado da sigla + ícone da orca */}
        <div className="flex items-center justify-end gap-3">
          <p className="text-xs text-white/80 sm:text-sm">
            Organization of Requests &amp; Communication Analysis
          </p>
          <Image
            src="/orca_white_svg.svg"
            alt=""
            width={83}
            height={67}
            unoptimized
            className="h-auto w-10 sm:w-12"
          />
        </div>

        {/* Logotipo */}
        <h1 className="mt-12 md:mt-16">
          <Image
            src="/logo-orca.svg"
            alt="ORCA"
            width={516}
            height={145}
            priority
            unoptimized
            className="h-auto w-full max-w-[360px]"
          />
        </h1>

        {/* Texto de apresentação */}
        <p className="mt-6 max-w-2xl text-base leading-relaxed md:text-lg">
          O ORCA é um sistema que utiliza inteligência artificial,
          processamento de linguagem natural e visão computacional para
          analisar conteúdos digitais e auxiliar no controle de acesso à web.
        </p>

        {/* Botões */}
        <div className="mt-8 flex flex-wrap gap-3">
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
