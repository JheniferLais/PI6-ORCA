import Image from "next/image";

// PROVISÓRIO: layout do rodapé deduzido (o Figma ainda não tem). As três cores
// vêm da paleta do projeto: fundo #273441, texto #E3E0D8 e linha #585651.
export default function Rodape() {
  return (
    <footer className="bg-orca-azul px-6 py-10 text-orca-areia xl:px-[calc(110*var(--u))] xl:py-[calc(64*var(--u))]">
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <Image
            src="/orca-icone.svg"
            alt=""
            width={83}
            height={67}
            unoptimized
            className="h-auto w-12 xl:w-[calc(83*var(--u))]"
          />
          <p className="text-[13px] xl:text-[length:calc(20*var(--u))]">
            Organization of Requests &amp; Communication Analysis
          </p>
        </div>

        <a
          href="https://github.com/JheniferLais/PI6-ORCA"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[13px] underline underline-offset-4 xl:text-[length:calc(20*var(--u))]"
        >
          Ver no Github
        </a>
      </div>

      <p className="mt-8 border-t border-orca-cinza pt-5 text-[12px] text-orca-areia/70 xl:mt-[calc(40*var(--u))] xl:pt-[calc(24*var(--u))] xl:text-[length:calc(16*var(--u))]">
        2026 Orca. Todos os direitos reservados.
      </p>
    </footer>
  );
}
