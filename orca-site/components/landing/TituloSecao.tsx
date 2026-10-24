/** Título pixelado com o traço preto embaixo (usado em cada seção). */
export default function TituloSecao({ children }: { children: React.ReactNode }) {
  return (
    <>
      <h2 className="font-pixel text-3xl leading-none md:text-4xl">
        {children}
      </h2>
      <div className="mt-3 h-1.5 w-16 bg-black" />
    </>
  );
}
