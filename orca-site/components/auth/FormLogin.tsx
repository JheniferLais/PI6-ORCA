"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { emailValido, entrar, ErroApi, normalizarEmail } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Campo, classeBotao, classeBotaoContorno, MensagemErro } from "./CamposAuth";
import { IconeCadeado, IconeEntrar, IconeMais, IconeUsuario } from "./Icones";

export default function FormLogin() {
  const router = useRouter();
  const params = useSearchParams();
  const recemCadastrado = params.get("cadastrado") === "1";
  const { estado } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // TODO: "Lembrar de mim" ainda não é enviado para o backend (entrar() não recebe esse dado).
  const [lembrar, setLembrar] = useState(false);
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
      <>
        <form onSubmit={enviar} noValidate className="flex flex-col gap-[14px]">
          {recemCadastrado && !erro && (
              <p role="status" className="border-2 border-(color:--auth-fg) px-3 py-2 text-[11px] leading-snug">
                Cadastro realizado. Entre com seu e-mail e senha.
              </p>
          )}
          <Campo
              id="email"
              rotulo="Email ou usuário"
              icone={<IconeUsuario className="size-full" />}
              inputMode="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
          />
          <Campo
              id="password"
              rotulo="Senha"
              type="password"
              icone={<IconeCadeado className="size-full" />}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
          />

          <div className="flex items-center justify-between text-[9.5px]">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                  type="checkbox"
                  checked={lembrar}
                  onChange={(e) => setLembrar(e.target.checked)}
                  className="peer sr-only"
              />
              <span
                  aria-hidden
                  className="grid size-4 place-items-center border-2 border-(color:--auth-fg) after:size-2 after:bg-(--auth-fg) after:opacity-0 peer-checked:after:opacity-100 peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-(color:--auth-fg)"
              />
              Lembrar de mim
            </label>
            {/* TODO: trocar "#" pela rota de recuperação de senha quando existir */}
            <Link href="#" className="underline">
              Esqueceu sua senha?
            </Link>
          </div>

          {erro && <MensagemErro>{erro}</MensagemErro>}

          <button type="submit" className={`${classeBotao} mt-[13px]`} disabled={enviando}>
            {enviando ? "Entrando..." : "Entrar"}
            <IconeEntrar className="absolute top-1/2 right-4 size-4 -translate-y-1/2" />
          </button>
        </form>

        <div className="-mx-3 mt-[10px] border-t border-(color:--auth-fg) pt-3 sm:-mx-[43px]">
          <p className="text-center text-[10px]">Ainda não possui uma conta?</p>
          <div className="mt-[7px] sm:mx-[43px]">
            <Link href="/cadastro" className={classeBotaoContorno}>
              Criar Conta
              <IconeMais className="absolute top-1/2 right-4 size-4 -translate-y-1/2" />
            </Link>
          </div>
        </div>
      </>
  );
}