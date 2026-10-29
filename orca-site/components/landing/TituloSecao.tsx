/** Título pixelado com o traço preto embaixo (usado em cada seção). */
export default function TituloSecao({ children }: { children: React.ReactNode }) {
  return (
    <>
      <h2 className="font-pixel text-[28px] leading-[0.963] xl:text-[length:calc(43.65*var(--u))]">
        {children}
      </h2>
      <div className="mt-3 h-[6px] w-[70px] bg-black xl:mt-[calc(12*var(--u))] xl:h-[calc(9*var(--u))] xl:w-[calc(100*var(--u))]" />
    </>
  );
}
