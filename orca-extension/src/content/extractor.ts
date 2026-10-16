import { CONFIG } from '../config';
import type { ExtractedContent, ExtractedImage } from '../models/content';
import { normalizeText } from '../utils/normalization';

/** Texto visível da página, direto do DOM. */
export function extractText(): string {
  return document.body?.innerText ?? '';
}

/** Imagens <img> da página, já sem as muito pequenas (pixels de rastreio, ícones). */
export function extractImages(): ExtractedImage[] {
  const images: ExtractedImage[] = [];

  for (const img of Array.from(document.images)) {
    const width = img.naturalWidth;
    const height = img.naturalHeight;

    // Imagem ainda não carregada tem tamanho 0 e cai aqui também.
    if (
      width < CONFIG.minImageWidth ||
      height < CONFIG.minImageHeight ||
      width * height < CONFIG.minImageArea
    ) {
      continue;
    }

    const src = img.currentSrc || img.src;
    if (!src) continue;

    const image: ExtractedImage = { src, width, height };
    const alt = img.alt.trim();
    if (alt) image.alt = alt;
    images.push(image);
  }

  return images;
}

export function extractMetadata() {
  return {
    url: location.href,
    title: document.title,
    timestamp: new Date().toISOString(),
  };
}

/** Junta tudo na estrutura final. */
export function normalizeContent(
  metadata: ReturnType<typeof extractMetadata>,
  text: string,
  images: ExtractedImage[],
): ExtractedContent {
  return {
    url: metadata.url,
    title: metadata.title.replace(/\s+/g, ' ').trim(),
    timestamp: metadata.timestamp,
    text: normalizeText(text),
    images,
  };
}

export function extractContent(): ExtractedContent {
  return normalizeContent(extractMetadata(), extractText(), extractImages());
}
