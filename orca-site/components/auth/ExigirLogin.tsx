"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./AuthProvider";

/**
 * Protege uma área do site: só mostra o conteúdo depois que o backend
 * confirmou a sessão; sem sessão válida, manda para /login.
 */
export default function ExigirLogin({ children }: { children: React.ReactNode }) {
  const { estado, saindo } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // ao sair pelo botão, quem decide o destino ("/") é o sairDaConta()
    if (estado === "visitante" && !saindo) router.replace("/login");
  }, [estado, saindo, router]);

  if (estado !== "autenticado") {
    return (
      <p className="p-10 text-center text-sm text-orca-cinza" role="status">
        Verificando sessão...
      </p>
    );
  }
  return <>{children}</>;
}
