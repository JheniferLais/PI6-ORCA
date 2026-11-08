"use client";

import { useEffect, useSyncExternalStore } from "react";
import { API_URL } from "@/lib/api";
import {
  informarConexao,
  lerConexao,
  observarConexao,
  type EstadoConexao,
} from "@/lib/conexao";

const VERIFICA_A_CADA_MS = 10_000;

/** Testa se o servidor responde (qualquer resposta HTTP serve). */
async function testarServidor() {
  const controle = new AbortController();
  const limite = setTimeout(() => controle.abort(), 3000);
  try {
    await fetch(`${API_URL}/docs`, { cache: "no-store", signal: controle.signal });
    informarConexao(true);
  } catch {
    informarConexao(false);
  } finally {
    clearTimeout(limite);
  }
}

const TEXTOS: Record<EstadoConexao, string> = {
  verificando: "Conectando ao servidor...",
  conectado: "Conectado ao servidor",
  erro: "Sem conexão com o servidor",
};

const CORES: Record<EstadoConexao, string> = {
  verificando: "bg-[#bbb]",
  conectado: "bg-[#3fae5a]",
  erro: "bg-orca-vermelho",
};

/**
 * Bolinha no canto inferior direito: verde = conectado, vermelha = sem conexão.
 * Sem props, usa o estado global da conexão; a tela de logs passa o próprio
 * estado (que também considera erros como 403 ao buscar os registros).
 */
export default function StatusServidor({
  estado: estadoProprio,
  detalhe,
}: {
  estado?: EstadoConexao;
  detalhe?: string;
}) {
  const global = useSyncExternalStore(observarConexao, lerConexao, () => "verificando" as const);
  const controlado = estadoProprio !== undefined;

  useEffect(() => {
    if (controlado) return;
    void testarServidor();
    const relogio = setInterval(() => void testarServidor(), VERIFICA_A_CADA_MS);
    return () => clearInterval(relogio);
  }, [controlado]);

  const estado = estadoProprio ?? global;
  const texto = detalhe ? `${TEXTOS[estado]}. ${detalhe}` : TEXTOS[estado];

  return (
    <span
      role="status"
      title={texto}
      aria-label={texto}
      className={`fixed right-[14px] bottom-[14px] z-50 size-3 rounded-full ${CORES[estado]}`}
    />
  );
}
