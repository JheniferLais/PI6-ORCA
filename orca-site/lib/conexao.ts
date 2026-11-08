/**
 * Estado da conexão com o backend, compartilhado pelo site inteiro.
 * apiFetch() informa o resultado de cada chamada e a bolinha de status
 * (components/StatusServidor.tsx) também testa o servidor de tempos em tempos.
 */

export type EstadoConexao = "verificando" | "conectado" | "erro";

let atual: EstadoConexao = "verificando";
const ouvintes = new Set<() => void>();

export function lerConexao(): EstadoConexao {
  return atual;
}

/** true = o servidor respondeu (qualquer status HTTP); false = não respondeu. */
export function informarConexao(respondeu: boolean) {
  const novo: EstadoConexao = respondeu ? "conectado" : "erro";
  if (novo === atual) return;
  atual = novo;
  ouvintes.forEach((f) => f());
}

export function observarConexao(aoMudar: () => void): () => void {
  ouvintes.add(aoMudar);
  return () => {
    ouvintes.delete(aoMudar);
  };
}
