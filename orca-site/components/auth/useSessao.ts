"use client";

import { useSyncExternalStore } from "react";
import { lerSessao, observarSessao, type Sessao } from "@/lib/api";

/**
 * Sessão atual, atualizada quando o usuário entra, sai ou o token expira
 * (inclusive em outra aba). "undefined" = ainda no servidor / hidratando.
 */
export function useSessao(): Sessao | null | undefined {
  return useSyncExternalStore(
    observarSessao,
    () => lerSessao(),
    () => undefined,
  );
}
