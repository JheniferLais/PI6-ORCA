import type { Metadata } from "next";
import { Suspense } from "react";
import FormCadastro from "@/components/auth/FormCadastro";
import TelaAuth from "@/components/auth/TelaAuth";

export const metadata: Metadata = {
    title: "Cadastro | ORCA",
};

export default function CadastroPage() {
    return (
        <TelaAuth titulo="Novo por aqui?" tema="claro">
            <Suspense>
                <FormCadastro />
            </Suspense>
        </TelaAuth>
    );
}