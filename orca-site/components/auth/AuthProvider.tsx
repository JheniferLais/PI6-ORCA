"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { confirmarSessao, ErroApi, sair, type Sessao } from "@/lib/api";
import { useSessao } from "./useSessao";

/**
 * Estado de autenticação de todo o site.
 *
 *  - "carregando":  ainda lendo a sessão salva (primeira renderização)
 *  - "visitante":   sem sessão, ou o backend recusou o token
 *  - "verificando": há token salvo, aguardando GET /auth/me confirmar
 *  - "autenticado": o backend aceitou o token
 *
 * Ter um token salvo não basta: ele só vale depois que o backend confirma.
 * Se o backend responder 401, apiFetch() apaga a sessão e o estado vira
 * "visitante" em todas as páginas (e em outras abas) na hora.
 */
export type EstadoAuth = "carregando" | "visitante" | "verificando" | "autenticado";

type ContextoAuth = {
  estado: EstadoAuth;
  sessao: Sessao | null;
  /** Encerra a sessão local e volta para a página inicial. */
  sairDaConta: () => void;
  /** true entre o clique em "Sair" e a chegada em "/" (as telas protegidas
   *  não devem mandar para /login nesse meio-tempo). */
  saindo: boolean;
};

const Contexto = createContext<ContextoAuth | null>(null);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const sessao = useSessao();
  const router = useRouter();
  const caminho = usePathname();
  // página em que o usuário clicou em "Sair"; zera ao trocar de página
  const [saindoDe, setSaindoDe] = useState<string | null>(null);
  const [caminhoAnterior, setCaminhoAnterior] = useState(caminho);
  if (caminho !== caminhoAnterior) {
    setCaminhoAnterior(caminho);
    setSaindoDe(null);
  }
  // token que o backend já confirmou
  const [confirmado, setConfirmado] = useState<string | null>(null);
  const token = sessao?.token ?? null;

  useEffect(() => {
    if (!token || confirmado === token) return;
    let ativo = true;
    confirmarSessao()
      .then(() => ativo && setConfirmado(token))
      .catch((e: unknown) => {
        // 401: a sessão já foi apagada por apiFetch(). Servidor fora do ar
        // (status 0) não é uma recusa do token: mantém a sessão e as telas
        // protegidas mostram o erro de conexão ao buscar os dados.
        if (ativo && e instanceof ErroApi && e.status !== 401) setConfirmado(token);
      });
    return () => {
      ativo = false;
    };
  }, [token, confirmado]);

  const estado: EstadoAuth =
    sessao === undefined
      ? "carregando"
      : sessao === null
        ? "visitante"
        : confirmado === sessao.token
          ? "autenticado"
          : "verificando";

  const sairDaConta = useCallback(() => {
    setSaindoDe(caminho);
    sair();
    router.replace("/");
  }, [router, caminho]);

  return (
    <Contexto.Provider
      value={{ estado, sessao: sessao ?? null, sairDaConta, saindo: saindoDe === caminho }}
    >
      {children}
    </Contexto.Provider>
  );
}

export function useAuth(): ContextoAuth {
  const ctx = useContext(Contexto);
  if (!ctx) throw new Error("useAuth precisa estar dentro de <AuthProvider>");
  return ctx;
}
