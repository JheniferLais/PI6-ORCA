/** Ícones em pixel art: cada "X" do desenho vira um quadradinho. */

export const ICONES = {
  funil: [
    "XXXXXXXXXXXX",
    "X..........X",
    "XX........XX",
    ".X........X.",
    "..XX....XX..",
    "...X....X...",
    "...XX..XX...",
    "....X..X....",
    "....X..X....",
    "....X..X....",
    "....XXXX....",
  ],
  bloqueio: [
    "XXXXXXXXXXXX",
    "X..........X",
    "X.XX....XX.X",
    "X..XX..XX..X",
    "X...XXXX...X",
    "X....XX....X",
    "X...XXXX...X",
    "X..XX..XX..X",
    "X.XX....XX.X",
    "X..........X",
    "XXXXXXXXXXXX",
  ],
  alerta: [
    "XXXXXXXXXXXX",
    "X..........X",
    "X....XX....X",
    "X....XX....X",
    "X....XX....X",
    "X....XX....X",
    "X....XX....X",
    "X..........X",
    "X....XX....X",
    "X....XX....X",
    "X..........X",
    "XXXXXXXXXXXX",
  ],
  engrenagem: [
    "....XXXX....",
    ".XX.XXXX.XX.",
    ".XXXXXXXXXX.",
    "..XXX..XXX..",
    "XXXX....XXXX",
    "XXX......XXX",
    "XXX......XXX",
    "XXXX....XXXX",
    "..XXX..XXX..",
    ".XXXXXXXXXX.",
    ".XX.XXXX.XX.",
    "....XXXX....",
  ],
  calendario: [
    "..X......X..",
    "XXXXXXXXXXXX",
    "X..........X",
    "XXXXXXXXXXXX",
    "X.X.X.X.X.XX",
    "X..........X",
    "X.X.X.X.X.XX",
    "X..........X",
    "XXXXXXXXXXXX",
  ],
} as const;

type Props = {
  desenho: readonly string[];
  className?: string;
};

/** A cor vem do `color` do CSS (fill="currentColor"). */
export default function PixelIcon({ desenho, className }: Props) {
  const largura = Math.max(...desenho.map((l) => l.length));
  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${largura} ${desenho.length}`}
      shapeRendering="crispEdges"
      fill="currentColor"
      className={className}
    >
      {desenho.flatMap((linha, y) =>
        Array.from(linha).map((c, x) =>
          c === "X" ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null,
        ),
      )}
    </svg>
  );
}

/** Triângulo (setas da lista, da paginação e dos menus). */
export function Triangulo({
  direcao,
  className,
}: {
  direcao: "direita" | "esquerda" | "baixo";
  className?: string;
}) {
  const pontos = {
    direita: "0,0 8,6 0,12",
    esquerda: "8,0 0,6 8,12",
    baixo: "0,0 12,0 6,8",
  }[direcao];
  const caixa = direcao === "baixo" ? "0 0 12 8" : "0 0 8 12";
  return (
    <svg aria-hidden viewBox={caixa} fill="currentColor" className={className}>
      <polygon points={pontos} />
    </svg>
  );
}
