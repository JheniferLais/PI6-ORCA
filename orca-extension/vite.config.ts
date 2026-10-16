/**
 * O build roda duas vezes (uma por "mode"), porque cada arquivo precisa de um formato:
 *   --mode content     → dist/content.js     (IIFE: content scripts não aceitam `import`)
 *   --mode background  → dist/background.js  (ES module, como declarado no manifest)
 * Use `npm run build`, que já faz as duas.
 */
import { defineConfig } from 'vite';

export default defineConfig(({ mode }) => {
  const isContent = mode === 'content';

  return {
    publicDir: isContent ? 'public' : false, // copia public/manifest.json para dist/ (só na 1ª passada)
    build: {
      outDir: 'dist',
      emptyOutDir: isContent, // limpa dist/ só na 1ª passada
      target: 'es2022',
      minify: false,
      lib: {
        entry: isContent ? 'src/content/index.ts' : 'src/background/service-worker.ts',
        formats: [isContent ? 'iife' : 'es'],
        name: 'OrcaContent', // usado só no formato IIFE
        fileName: () => (isContent ? 'content.js' : 'background.js'),
      },
    },
  };
});
