import ComoFunciona from "@/components/landing/ComoFunciona";
import Hero from "@/components/landing/Hero";
import Objetivos from "@/components/landing/Objetivos";
import Rodape from "@/components/landing/Rodape";

export default function Home() {
  return (
    <>
      <main>
        <Hero />
        <ComoFunciona />
        <Objetivos />
      </main>
      <Rodape />
    </>
  );
}
