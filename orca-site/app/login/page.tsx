import type { Metadata } from "next";
import { Suspense } from "react";
import FormLogin from "@/components/auth/FormLogin";
import TelaAuth from "@/components/auth/TelaAuth";

export const metadata: Metadata = {
  title: "Entrar | ORCA",
};

export default function LoginPage() {
  return (
    <TelaAuth titulo="Entrar">
      <Suspense>
        <FormLogin />
      </Suspense>
    </TelaAuth>
  );
}
