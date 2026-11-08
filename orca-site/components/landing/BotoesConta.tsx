"use client";

import { useAuth } from "@/components/auth/AuthProvider";
import BotaoPixel from "./BotaoPixel";

/**
 * Botões do topo que dependem do login:
 *  visitante   -> Cadastrar e Entrar
 *  autenticado -> Logs e Sair
 * Enquanto a sessão é lida/confirmada no backend não mostra nada, para não
 * piscar o botão errado.
 */
export default function BotoesConta() {
  const { estado, sairDaConta } = useAuth();

  if (estado === "visitante") {
    return (
      <>
        <BotaoPixel href="/cadastro" icone="/icones/cadastro.svg">
          Cadastrar
        </BotaoPixel>
        <BotaoPixel href="/login" icone="/icones/entrar.svg">
          Entrar
        </BotaoPixel>
      </>
    );
  }

  if (estado === "autenticado") {
    return (
      <>
        <BotaoPixel href="/logs" icone="/icones/log.svg">
          Logs
        </BotaoPixel>
        <BotaoPixel onClick={sairDaConta} icone="/icones/sair.svg">
          Sair
        </BotaoPixel>
      </>
    );
  }

  return null;
}
