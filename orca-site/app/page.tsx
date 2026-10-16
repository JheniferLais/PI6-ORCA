import Image from 'next/image';
import Link from 'next/link';

export default function WelcomePage() {
  return (
      <main className="min-h-screen bg-[#F4F4F4] text-neutral-900 flex flex-col items-center justify-between p-8 md:p-24 selection:bg-black selection:text-white">
        {/* Cabeçalho simples */}
        <header className="w-full max-w-5xl flex items-center justify-between">
            <span className="text-xs font-mono uppercase tracking-widest text-neutral-500">Logo | ID Visual</span>
            <span className="text-sm font-semibold tracking-wider">ORCA</span>
        </header>

        {/* Conteúdo Central */}
        <div className="flex flex-col items-center text-center max-w-xl my-auto space-y-6">
          {/* Logotipo em Pixel Art */}
          <div className="p-6 bg-neutral-200 rounded-2xl shadow-sm border border-neutral-300 flex items-center justify-center">
            <Image
                src="/LOGO.svg"
                alt="Logo Orca Pixel Art"
                width={96}
                height={96}
                className="pixelated object-contain"
                priority
            />
          </div>

          {/* Títulos e Boas-vindas */}
          <div className="space-y-2">
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
              Bem-vindo ao Orca.
            </h1>
            <p className="text-neutral-600 text-sm md:text-base">
              ISSO É SÓ UM EXEMPLO FAZ AI CARAI KKKKK.
            </p>
          </div>

          {/* Botão de Ação */}
          <div className="pt-4">
            <Link
                href="/dashboard" // TODO: colocar a rota da pagina
                className="inline-flex items-center justify-center px-6 py-3 rounded-full bg-black text-white text-sm font-medium transition-all hover:bg-neutral-800 hover:scale-105 active:scale-95 shadow-md"
            >
              Começar
            </Link>
          </div>
        </div>

        {/* Rodapé */}
        <footer className="w-full max-w-5xl text-center text-xs text-neutral-400 font-mono">
          2026 Orca. Todos os direitos reservados.
        </footer>
      </main>
  );
}
