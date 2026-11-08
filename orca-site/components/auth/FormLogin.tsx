"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { emailValido, entrar, ErroApi, normalizarEmail } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Campo, classeBotao, MensagemErro } from "./TelaAuth";

export default function FormLogin() {
  const router = useRouter();
  const params = useSearchParams();
  const recemCadastrado = params.get("cadastrado") === "1";
  const { estado } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // já está logado: não precisa da tela de login
  useEffect(() => {
    if (estado === "autenticado") router.replace("/");
  }, [estado, router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim() || !password) {
      setErro("Preencha o e-mail e a senha.");
      return;
    }
    if (!emailValido(normalizarEmail(email))) {
      setErro("Informe um e-mail válido.");
      return;
    }
    setErro(null);
    setEnviando(true);
    try {
      await entrar(email, password);
      router.replace("/");
    } catch (err) {
      setErro(
        err instanceof ErroApi && err.status === 401
          ? "E-mail ou senha inválidos."
          : err instanceof Error
            ? err.message
            : "Não foi possível entrar.",
      );
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      {recemCadastrado && !erro && (
        <p role="status" className="border-2 border-black px-3 py-2 text-sm">
          Cadastro realizado. Entre com seu e-mail e senha.
        </p>
      )}
      <Campo
        id="email"
        rotulo="E-mail"
        type="email"
        inputMode="email"
        autoComplete="email"
        placeholder="voce@exemplo.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <Campo
        id="password"
        rotulo="Senha"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {erro && <MensagemErro>{erro}</MensagemErro>}
      <button type="submit" className={`${classeBotao} mt-2`} disabled={enviando}>
        {enviando ? "Entrando..." : "Entrar"}
      </button>
      <p className="text-center text-sm">
        Não tem conta?{" "}
        <Link href="/cadastro" className="font-bold underline">
          Cadastre-se
        </Link>
      </p>
    </form>
  );
}
