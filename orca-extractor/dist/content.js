(function() {
  "use strict";
  const CONFIG = {
    /** Imagens menores que isso (tamanho natural, em px) são descartadas. */
    minImageWidth: 100,
    minImageHeight: 100,
    minImageArea: 1e4,
    /** Espera (ms) sem novas mudanças na página antes de extrair de novo. */
    debounceMs: 1e3
  };
  function normalizeText(input) {
    return input.replace(/\r\n?/g, "\n").replace(/[^\S\n]+/g, " ").split("\n").map((line) => line.trim()).join("\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  function extractText() {
    return document.body?.innerText ?? "";
  }
  function extractImages() {
    const images = [];
    for (const img of Array.from(document.images)) {
      const width = img.naturalWidth;
      const height = img.naturalHeight;
      if (width < CONFIG.minImageWidth || height < CONFIG.minImageHeight || width * height < CONFIG.minImageArea) {
        continue;
      }
      const src = img.currentSrc || img.src;
      if (!src) continue;
      const image = { src, width, height };
      const alt = img.alt.trim();
      if (alt) image.alt = alt;
      images.push(image);
    }
    return images;
  }
  function extractMetadata() {
    return {
      url: location.href,
      title: document.title,
      timestamp: (/* @__PURE__ */ new Date()).toISOString()
    };
  }
  function normalizeContent(metadata, text, images) {
    return {
      url: metadata.url,
      title: metadata.title.replace(/\s+/g, " ").trim(),
      timestamp: metadata.timestamp,
      text: normalizeText(text),
      images
    };
  }
  function extractContent() {
    return normalizeContent(extractMetadata(), extractText(), extractImages());
  }
  function observeChanges(onChange, delayMs) {
    let timer;
    const schedule = () => {
      clearTimeout(timer);
      timer = setTimeout(onChange, delayMs);
    };
    new MutationObserver(schedule).observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["src", "srcset"]
    });
    document.addEventListener(
      "load",
      (event) => {
        if (event.target instanceof HTMLImageElement) schedule();
      },
      true
    );
  }
  function extractAndSend() {
    const message = {
      type: "CONTENT_EXTRACTED",
      payload: extractContent()
    };
    try {
      chrome.runtime.sendMessage(message).catch(() => {
      });
    } catch {
    }
  }
  extractAndSend();
  observeChanges(extractAndSend, CONFIG.debounceMs);
})();
