/**
 * Normalização básica: espaços repetidos → 1 espaço, linhas vazias repetidas → 1,
 * trim em cada linha e no texto todo. Não altera o conteúdo.
 */
export function normalizeText(input: string): string {
  return input
      .replace(/\r\n?/g, '\n')
      .replace(/[^\S\n]+/g, ' ')
      .split('\n')
      .map((line) => line.trim())
      .join('\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
}