/**
 * Chama `onChange` (uma vez) depois que a página para de mudar por `delayMs`.
 * Assim, 500 mutações seguidas geram uma única extração.
 */
export function observeChanges(onChange: () => void, delayMs: number): void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(onChange, delayMs);
  };

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['src', 'srcset'],
  });

  // O tamanho de uma <img> só existe depois que ela carrega. O evento "load" não
  // borbulha, então escutamos na fase de captura para pegar todas as imagens.
  document.addEventListener(
    'load',
    (event) => {
      if (event.target instanceof HTMLImageElement) schedule();
    },
    true,
  );
}
