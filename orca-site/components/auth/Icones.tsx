/**
 * Ícones de linha usados nas telas de login e cadastro (traço de 1.75px,
 * mesmo desenho dos ícones "lucide" do protótipo). A cor vem do `color` do CSS.
 */

type Props = { className?: string };

function Svg({ className, children }: Props & { children: React.ReactNode }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {children}
    </svg>
  );
}

export const IconeUsuario = (p: Props) => (
  <Svg {...p}>
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </Svg>
);

export const IconeCadeado = (p: Props) => (
  <Svg {...p}>
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </Svg>
);

export const IconeEmail = (p: Props) => (
  <Svg {...p}>
    <rect width="20" height="16" x="2" y="4" rx="2" />
    <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
  </Svg>
);

export const IconeOlho = (p: Props) => (
  <Svg {...p}>
    <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
    <circle cx="12" cy="12" r="3" />
  </Svg>
);

export const IconeOlhoRiscado = (p: Props) => (
  <Svg {...p}>
    <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />
    <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />
    <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />
    <path d="m2 2 20 20" />
  </Svg>
);

export const IconeVoltar = (p: Props) => (
  <Svg {...p}>
    <polyline points="9 14 4 9 9 4" />
    <path d="M20 20v-7a4 4 0 0 0-4-4H4" />
  </Svg>
);

export const IconePower = (p: Props) => (
  <Svg {...p}>
    <path d="M12 2v10" />
    <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
  </Svg>
);

/** Seta "↳" dos botões de enviar. */
export const IconeEntrar = (p: Props) => (
  <Svg {...p}>
    <polyline points="15 10 20 15 15 20" />
    <path d="M4 4v7a4 4 0 0 0 4 4h12" />
  </Svg>
);

export const IconeMais = (p: Props) => (
  <Svg {...p}>
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </Svg>
);
