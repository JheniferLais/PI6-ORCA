"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cadastrar, emailValido, ErroApi, normalizarEmail } from "@/lib/api";
import { useAuth } from "./AuthProvider";
import { Campo, classeBotao, MensagemErro } from "./TelaAuth";

type Erros = Partial<Record<"name" | "email" | "password" | "confirmacao", string>>;

/**
 * Mesmas regras do backend (models/app/schemas.py, UserCreate); o e-mail vai
 * no campo "email" (o site limita a 100 caracteres; o backend aceita até 254).
 */
function validar(name: string, email: string, password: string, confirmacao: string): Erros {
  const erros: Erros = {};
  if (!name.trim()) erros.name = "Informe seu nome.";
  else if (name.trim().length > 120) erros.name = "O nome pode ter no máximo 120 caracteres.";
  const e = normalizarEmail(email);
  if (!e) erros.email = "Informe seu e-mail.";
  else if (!emailValido(e)) erros.email = "Informe um e-mail válido.";
  else if (e.length > 100) erros.email = "O e-mail pode ter no máximo 100 caracteres.";
  if (password.length < 8) erros.password = "A senha precisa de ao menos 8 caracteres.";
  else if (password.length > 128) erros.password = "A senha pode ter no máximo 128 caracteres.";
  if (confirmacao !== password) erros.confirmacao = "As senhas não conferem.";
  return erros;
}

export default function FormCadastro() {
  const router = useRouter();
  const { estado } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erros, setErros] = useState<Erros>({});
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  // já está logado: não precisa se cadastrar
  useEffect(() => {
    if (estado === "autenticado") router.replace("/");
  }, [estado, router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const encontrados = validar(name, email, password, confirmacao);
    setErros(encontrados);
    setErro(null);
    if (Object.keys(encontrados).length > 0) return;

    setEnviando(true);
    try {
      await cadastrar(name.trim(), email, password);
    } catch (err) {
      setErro(
        err instanceof ErroApi && err.status === 409
          ? "Este e-mail já está cadastrado."
          : err instanceof Error
            ? err.message
            : "Não foi possível cadastrar.",
      );
      setEnviando(false);
      return;
    }

    // cadastro feito: o usuário entra pela tela de login
    router.replace("/login?cadastrado=1");
  }

  const ajuda = (campo: keyof Erros) =>
    erros[campo] && (
      <span id={`${campo}-erro`} className="mt-1 block text-xs text-orca-vermelho">
        {erros[campo]}
      </span>
    );

  return (
    <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
      <div>
        <Campo
          id="name"
          rotulo="Nome"
          autoComplete="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={!!erros.name}
          aria-describedby={erros.name ? "name-erro" : undefined}
        />
        {ajuda("name")}
      </div>
      <div>
        <Campo
          id="email"
          rotulo="E-mail"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="voce@exemplo.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={!!erros.email}
          aria-describedby={erros.email ? "email-erro" : undefined}
        />
        {ajuda("email")}
      </div>
      <div>
        <Campo
          id="password"
          rotulo="Senha"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={!!erros.password}
          aria-describedby={erros.password ? "password-erro" : undefined}
        />
        {ajuda("password")}
      </div>
      <div>
        <Campo
          id="confirmacao"
          rotulo="Confirmar senha"
          type="password"
          autoComplete="new-password"
          value={confirmacao}
          onChange={(e) => setConfirmacao(e.target.value)}
          aria-invalid={!!erros.confirmacao}
          aria-describedby={erros.confirmacao ? "confirmacao-erro" : undefined}
        />
        {ajuda("confirmacao")}
      </div>
      {erro && <MensagemErro>{erro}</MensagemErro>}
      <button type="submit" className={`${classeBotao} mt-2`} disabled={enviando}>
        {enviando ? "Cadastrando..." : "Cadastrar"}
      </button>
      <p className="text-center text-sm">
        Já tem conta?{" "}
        <Link href="/login" className="font-bold underline">
          Entrar
        </Link>
      </p>
    </form>
  );
}
