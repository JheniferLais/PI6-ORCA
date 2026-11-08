function payload(token: string): { exp?: number; sub?: string } | null {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64)) as { exp?: number; sub?: string };
  } catch {
    return null;
  }
}

/** O JWT vence em menos de `margemMs`? (sem validar a assinatura: isso é papel do backend) */
export function tokenExpirado(token: string, margemMs = 0): boolean {
  const exp = payload(token)?.exp;
  return typeof exp !== 'number' || exp * 1000 - margemMs <= Date.now();
}

/** id_user ("sub") do JWT, sem validar (só para comparar com a sessão atual). */
export function usuarioDoToken(token: string): string | null {
  const sub = payload(token)?.sub;
  return typeof sub === 'string' ? sub : null;
}
