# Agent İçerik Sistemi — Bilişim Postası

Haber/içerik hattı: n8n otomasyon + LibreTranslate + Umami analitik + Astro statik site. Teknoloji ve yapay zeka haberleri toplanır, özetlenir, çevrilir, kuyruğa alınır ve https://bilisimpostasi.com.tr üzerinde yayınlanır.

**Sunucu yolu:** `/root/agent-icerik-sistemi`  
Compose projeleri: **`n8n`**, **`agent-analytics`**  
Label: `com.omer.project=agent-icerik`

## Canlı adresler

| Servis | URL |
|--------|-----|
| Site | https://bilisimpostasi.com.tr |
| n8n | https://n8n.omerfarukturegun.com.tr |
| Umami | https://analytics.omerfarukturegun.com.tr |
| LibreTranslate | `127.0.0.1:5000` (internal; n8n `http://libretranslate:5000`) |

Kaynaklar (site hakkında): TechCrunch, Ars Technica, Hacker News, arXiv, The Verge, Engadget.

## Mimari

```
n8n workflow'ları
  → haber toplama / özet (Claude)
  → LibreTranslate (tr↔en)
  → kapak görseli (Unsplash → R2)
  → site/_queue + markdown post
  → deploy-listener (build + rsync /var/www/blog)
  → e-posta (Resend), Telegram, Twitter kuyruğu, ntfy

Umami ← site tracker (script.js)
host nginx → site dosyaları / n8n(Caddy) / analytics
```

```
İnternet
  bilisimpostasi.com.tr     → nginx → /var/www/blog (Astro dist)
  n8n.omerfarukturegun.com.tr
      → nginx → 127.0.0.1:9080 Caddy → agent-n8n:5678  (n8n kendi login)
  analytics.omerfarukturegun.com.tr
      → nginx → 127.0.0.1:3002 agent-umami
```

## Çalışan konteynerler

| Container | Rol | Host port |
|-----------|-----|-----------|
| `agent-n8n` | n8n | yok (Caddy üzerinden) |
| `agent-n8n-postgres` | n8n Postgres 16 | internal |
| `agent-libretranslate` | TR↔EN çeviri (`LT_LOAD_ONLY: tr,en`) | `127.0.0.1:5000` |
| `agent-umami` | Umami | `127.0.0.1:3002` → 3000 |
| `agent-umami-db` | Umami Postgres 15 | internal |

n8n host mount: `n8n/data`, `site/` (rw), `scripts/` (ro). Network: `n8n_agent_internal` + external `ops_net`.

Deploy listener: `scripts/deploy-listener.py` bir **symlink**; gerçek dosya `/usr/local/lib/agent-icerik/deploy-listener.py`. Systemd `agent-icerik-deploy-listener.service` canonical path’i çalıştırır; n8n HTTP ile `http://172.18.0.1:9876/deploy` çağırır (script path değil).

## Klasörler

```
agent-icerik-sistemi/
├── n8n/
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── data/
│   ├── migrations/          # email_subscribers, twitter_queue, used_cover_photos, notify_queue
│   └── backups/             # workflow JSON export'ları
├── analytics/
│   └── docker-compose.yml   # Umami + Postgres
├── site/                    # Astro 7, TR/EN, PWA, Pagefind, RSS
└── scripts/                 # build-and-deploy, deploy-listener, patch-workflow-*
```

## n8n

```bash
cd /root/agent-icerik-sistemi/n8n
docker compose up -d
```

Timezone: Europe/Istanbul. Execution prune: 336 saat.  
`N8N_HOST=n8n.${DOMAIN}`, `WEBHOOK_URL=https://n8n.${DOMAIN}/`.

### n8n `.env.example` değişken adları

`DOMAIN`, `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`, `RESEND_API_KEY`, `UNSPLASH_ACCESS_KEY`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL_BASE`, `TWITTER_CLIENT_ID`, `TWITTER_CLIENT_SECRET`, `DEPLOY_LISTENER_TOKEN`

### Başlıca workflow'lar

- Haber Toplama ve Özetleme
- Haber Yayınlama (Toplu / staggered / R2)
- E-posta Abonelik Yönetimi, Haber Email Bildirimi, Haftalık Özet
- Twitter / bildirim kuyruk işleyicileri
- İletişim Formu, Haftalık Medium Taslağı
- Geçmiş Yazıları İngilizceye Çevir

JSON kopyaları `n8n/backups/` ve kökteki bazı export dosyalarında.

## Analytics (Umami)

```bash
cd /root/agent-icerik-sistemi/analytics
docker compose up -d
```

Env adları: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `APP_SECRET`.  
Site tarafı: `UMAMI_API_URL`, `UMAMI_WEBSITE_ID`, `UMAMI_API_TOKEN` (`site/.env.example`).

## Site (Astro)

Statik site; Docker'da çalışmaz. Node >= 22.12.

```bash
cd /root/agent-icerik-sistemi/site
npm install
npm run check        # Astro type check
npm run test         # Vitest unit tests
npm run dev          # localhost:4321
npm run build        # dist + Pagefind
# prod: scripts/build-and-deploy-site.sh → rsync /var/www/blog
```

### CI (doğrulama — deploy yok)

GitHub Actions (`.github/workflows/ci.yml`, iş adı **Site CI** / `build-and-test`) `main` push ve her PR'da `site/` altında `npm ci` → `check` → `test` → fixture post seed → `build` çalıştırır. Amaç sadece kodun kırılmadığını doğrulamak; **CI sunucuya deploy etmez**. Canlı yayın hâlâ `scripts/build-and-deploy-site.sh` (ve n8n deploy-listener) ile yapılır.

Not: Gerçek haber markdown'ları `site/src/content/posts/` altında gitignore'lıdır (yalnızca VDS'te). CI bu yüzden build için minimal TR/EN fixture post üretir; Pagefind boş indekste patlamasın diye.

İçerik: TR + EN post'lar, `_queue/` (pending/scheduled). Sayfalar: abonelik, iletişim, kategoriler, etiket, en çok okunanlar, gizlilik/şartlar.

Deploy listener: `scripts/deploy-listener.py` → symlink → `/usr/local/lib/agent-icerik/deploy-listener.py` (systemd `agent-icerik-deploy-listener.service`; n8n yayın sonrası HTTP `:9876/deploy`).

## Yönetim

```bash
cd /root/agent-icerik-sistemi/n8n && docker compose ps
cd /root/agent-icerik-sistemi/analytics && docker compose ps
ops-manage status agent-icerik
```

Yedek (ops-backup beklenen): n8n Postgres dump + `n8n_n8n_data` volume tar.
