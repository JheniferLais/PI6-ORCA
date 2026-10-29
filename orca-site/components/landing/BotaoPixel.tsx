import Image from "next/image";
import Link from "next/link";

type Props = {
  href: string;
  /** Imagem do quadradinho com o ícone (ex.: /icones/info.svg). */
  icone: string;
  /** Abre em outra aba (use para links externos, como o GitHub). */
  externo?: boolean;
  children: React.ReactNode;
};

const classes =
  "inline-flex h-11 items-stretch border-2 border-white text-[15px] text-white transition-colors hover:bg-white/10 xl:h-[calc(56*var(--u))] xl:text-[length:calc(24*var(--u))]";

/** Botão do design: contorno branco, quadrado branco com ícone e o texto. */
export default function BotaoPixel({ href, icone, externo, children }: Props) {
  const conteudo = (
    <>
      <Image
        src={icone}
        alt=""
        width={54}
        height={53}
        unoptimized
        className="h-full w-auto"
      />
      <span className="flex items-center pr-3 pl-2 xl:pr-[calc(16*var(--u))] xl:pl-[calc(12*var(--u))]">
        {children}
      </span>
    </>
  );

  // Páginas do próprio site usam <Link> (troca de página sem recarregar tudo).
  if (href.startsWith("/")) {
    return (
      <Link href={href} className={classes}>
        {conteudo}
      </Link>
    );
  }

  return (
    <a
      href={href}
      {...(externo && { target: "_blank", rel: "noopener noreferrer" })}
      className={classes}
    >
      {conteudo}
    </a>
  );
}
