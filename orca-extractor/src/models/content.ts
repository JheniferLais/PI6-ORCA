export interface ExtractedImage {
  /** URL efetiva do recurso (currentSrc quando disponível). */
  src: string;
  alt?: string;
  /** Tamanho natural, em px. */
  width: number;
  height: number;
}

export interface ExtractedContent {
  url: string;
  title: string;
  /** ISO 8601 */
  timestamp: string;
  text: string;
  images: ExtractedImage[];
}

/** Mensagem enviada do Content Script para o Service Worker. */
export interface ContentExtractedMessage {
  type: 'CONTENT_EXTRACTED';
  payload: ExtractedContent;
}
