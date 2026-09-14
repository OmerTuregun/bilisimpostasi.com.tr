# Bilişim Postası (Astro)

https://bilisimpostasi.com.tr — teknoloji ve yapay zeka haber sitesi. Bu klasör **Agent İçerik Sistemi** monoreposunun statik site kısmıdır. Haberler n8n workflow'ları ile üretilir; site Astro ile build edilip `/var/www/blog` altına rsync edilir.

Üst seviye mimari, n8n ve Umami: [`../README.md`](../README.md).

## Teknoloji

- Astro 7, `@astrojs/rss`, `@astrojs/sitemap`
- TR/EN i18n, PWA (`@vite-pwa/astro`), Pagefind arama
- Umami tracker (`script.js`)
- Node `>=22.12.0`

`site` config: `https://bilisimpostasi.com.tr`.

## Komutlar

Proje kökü: `/root/agent-icerik-sistemi/site`

| Komut | Açıklama |
|-------|----------|
| `npm install` | Bağımlılıklar |
| `npm run dev` | Yerel sunucu (`localhost:4321`) |
| `npm run build` | Production build + Pagefind (`dist/`) |
| `npm run preview` | Build önizleme |
| `npm run icons` | PWA ikon üretimi (`prebuild` ile de çalışır) |

Production deploy: `../scripts/build-and-deploy-site.sh` (n8n `deploy-listener` da tetikler).

## Ortam değişkenleri (`site/.env.example`)

`UMAMI_API_URL`, `UMAMI_WEBSITE_ID`, `UMAMI_API_TOKEN`, `UMAMI_USERNAME`, `UMAMI_PASSWORD`

## Yapı (özet)

```
site/
├── src/pages/          # TR/EN sayfalar, posts, kategoriler, abonelik, iletişim
├── src/content/        # markdown haberler
├── public/
└── package.json
```

İçerik kuyruğu: `_queue/` (pending / scheduled). Medya: site `/media` ve Cloudflare R2.
