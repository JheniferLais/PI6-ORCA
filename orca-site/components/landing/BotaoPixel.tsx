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
  "inline-flex h-10 items-stretch border-2 border-white text-sm text-white transition-colors hover:bg-white/10";

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
      <span className="flex items-center pr-4 pl-3">
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
