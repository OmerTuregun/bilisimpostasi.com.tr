/// <reference types="astro/client" />
/// <reference types="vite-plugin-pwa/info" />
/// <reference types="vite-plugin-pwa/vanillajs" />

declare module '@pagefind/default-ui' {
  export class PagefindUI {
    constructor(opts: Record<string, unknown>);
    triggerSearch(query: string): void;
  }
}
