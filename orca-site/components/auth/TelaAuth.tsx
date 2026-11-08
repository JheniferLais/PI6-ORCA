import Image from "next/image";
import Link from "next/link";
import StatusServidor from "@/components/StatusServidor";

/**
 * Moldura das telas de login e cadastro: mesmo fundo do topo da página
 * inicial (preto com grade de pontinhos) e um cartão branco no centro.
 */
export default function TelaAuth({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <main className="hero-fundo flex min-h-screen flex-col px-4 py-6 text-white sm:px-10">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="font-pixel text-xl">
          ORCA
        </Link>
        <Image
          src="/orca_white_svg.svg"
          alt=""
          width={83}
          height={67}
          unoptimized
          className="h-auto w-10"
        />
      </div>

      <div className="flex flex-1 items-center justify-center py-10">
        <section className="w-full max-w-md border-2 border-black bg-white p-6 text-black sm:p-8">
          <h1 className="font-pixel text-3xl leading-none">{titulo}</h1>
          <div className="mt-3 mb-6 h-1.5 w-16 bg-black" />
          {children}
          <p className="mt-4 text-center text-sm">
            <Link href="/" className="underline">
              Voltar para o início
            </Link>
          </p>
        </section>
      </div>

      <StatusServidor />
    </main>
  );
}

/** Campo com rótulo no estilo dos filtros da tela de logs. */
export function Campo({
  id,
  rotulo,
  ...props
}: { id: string; rotulo: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-bold">
        {rotulo}
      </label>
      <input
        id={id}
        name={id}
        className="h-10 w-full border-2 border-black bg-white px-3 text-sm placeholder:text-[#777] aria-[invalid=true]:border-orca-vermelho"
        {...props}
      />
    </div>
  );
}

export function MensagemErro({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="border-2 border-orca-vermelho px-3 py-2 text-sm text-black"
    >
      {children}
    </p>
  );
}

export const classeBotao =
  "h-10 w-full border-2 border-black bg-black px-4 text-sm font-bold text-white transition-colors hover:bg-white hover:text-black disabled:cursor-default disabled:opacity-50 disabled:hover:bg-black disabled:hover:text-white";
