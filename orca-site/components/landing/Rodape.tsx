import Image from "next/image";

// PROVISÓRIO: layout do rodapé deduzido (o Figma ainda não tem). As três cores
// vêm da paleta do projeto: fundo #273441, texto #E3E0D8 e linha #585651.
export default function Rodape() {
  return (
    <footer className="bg-orca-azul text-orca-areia">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            <Image
              src="/orca-icone.svg"
              alt=""
              width={83}
              height={67}
              unoptimized
              className="h-auto w-12"
            />
            <p className="text-sm">
              Organization of Requests &amp; Communication Analysis
            </p>
          </div>

          <a
            href="https://github.com/JheniferLais/PI6-ORCA"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm underline underline-offset-4"
          >
            Ver no Github
          </a>
        </div>

        <p className="mt-8 border-t border-orca-cinza pt-5 text-xs text-orca-areia/70">
          2026 Orca. Todos os direitos reservados.
        </p>
      </div>
    </footer>
  );
}
