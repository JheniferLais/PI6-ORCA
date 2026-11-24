"use client";

import { useState } from "react";
import { IconeOlho, IconeOlhoRiscado } from "./Icones";

/**
 * Peças dos formulários de login e cadastro. As cores vêm das variáveis
 * --auth-* definidas em globals.css (.auth-escuro / .auth-claro), então as
 * mesmas peças servem para a tela escura e para a clara.
 */

type CampoProps = {
  id: string;
  /** Texto do campo (placeholder visível e rótulo para leitores de tela). */
  rotulo: string;
  /** Ícone à esquerda (ex.: <IconeUsuario className="size-full" />). */
  icone: React.ReactNode;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "placeholder">;

export function Campo({ id, rotulo, icone, type = "text", className, ...props }: CampoProps) {
  const ehSenha = type === "password";
  const [visivel, setVisivel] = useState(false);

  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">
        {rotulo}
      </label>
      <span
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3 size-[14px] -translate-y-1/2"
      >
        {icone}
      </span>
      <input
        id={id}
        name={id}
        type={ehSenha && visivel ? "text" : type}
        placeholder={rotulo}
        className={`h-9 w-full border-2 border-(color:--auth-fg) bg-transparent pl-[34px] text-[12px] text-(color:--auth-fg) placeholder:text-(color:--auth-placeholder) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(color:--auth-fg) aria-[invalid=true]:border-orca-vermelho ${ehSenha ? "pr-10" : "pr-3"} ${className ?? ""}`}
        {...props}
      />
      {ehSenha && (
        <button
          type="button"
          onClick={() => setVisivel((v) => !v)}
          aria-label={visivel ? "Ocultar senha" : "Mostrar senha"}
          aria-pressed={visivel}
          className="absolute top-1/2 right-2 grid size-6 -translate-y-1/2 cursor-pointer place-items-center text-(color:--auth-fg) focus-visible:outline-2 focus-visible:outline-(color:--auth-fg)"
        >
          {visivel ? (
            <IconeOlho className="size-[14px]" />
          ) : (
            <IconeOlhoRiscado className="size-[14px]" />
          )}
        </button>
      )}
    </div>
  );
}

export function MensagemErro({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="border-2 border-orca-vermelho px-3 py-2 text-[11px] leading-snug text-(color:--auth-fg)"
    >
      {children}
    </p>
  );
}

const baseBotao =
  "relative flex h-9 w-full cursor-pointer items-center justify-center border-2 border-(color:--auth-fg) text-[16px] transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(color:--auth-fg) disabled:cursor-default disabled:opacity-50";

/** Botão principal: preenchido com a cor do texto (branco no escuro, preto no claro). */
export const classeBotao = `${baseBotao} bg-(--auth-fg) text-(color:--auth-bg) hover:bg-(--auth-bg) hover:text-(color:--auth-fg) disabled:hover:bg-(--auth-fg) disabled:hover:text-(color:--auth-bg)`;

/** Botão secundário: só contorno ("Criar Conta"). */
export const classeBotaoContorno = `${baseBotao} bg-transparent text-(color:--auth-fg) hover:bg-(--auth-fg) hover:text-(color:--auth-bg)`;
