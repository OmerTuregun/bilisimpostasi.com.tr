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

## Yedekleme & Restore

Sunucu kaybı veya veri bozulması durumunda referans. Komutlar **15 Eylül 2026**'da izole ortamda test edildi (içerik SHA256, n8n/Umami satır sayıları); **canlı veritabanına yazarak restore test edilmedi**.

Script: `/root/apps/ops-backup/scripts/backup-all.sh` (Ofelia `ops-backup-runner` içinde `/scripts/backup-all.sh`).

### Ne yedekleniyor

| Artefakt | Dosya adı (örnek) | Kaynak |
|----------|-------------------|--------|
| n8n Postgres (full dump) | `YYYYMMDD-HHMMSS.n8n-postgres.dump` | `agent-n8n-postgres` — tüm şema (`email_subscribers`, `twitter_queue`, `notify_queue`, `used_cover_photos`, `workflow_entity`, n8n workflow/credential tabloları, …) |
| Umami Postgres (full dump) | `YYYYMMDD-HHMMSS.umami-postgres.dump` | `agent-umami-db` |
| Site içeriği | `YYYYMMDD-HHMMSS.content-posts-queue.tar.gz` | `site/src/content/posts/` + `site/src/content/_queue/` |
| n8n dosya depolama | `YYYYMMDD-HHMMSS.n8n_n8n_data.tar.gz` | Docker volume `n8n_n8n_data` (config, `storage/workflows/…/binary_data`, event log’lar) |

### Sıklık ve retention

- **Zamanlama:** Ofelia, her gece **03:00** (`Europe/Istanbul`), `agent-icerik` dahil tam yedek (`backup-all.sh` argsız).
- **Retention:** `daily/` **30 gün**; Pazar günü kopya `weekly/` (**180 gün**).

Elle tetikleme (sadece bu proje):

```bash
docker exec ops-backup-runner /scripts/backup-all.sh agent-icerik
```

Tüm projeler (Ofelia ile aynı):

```bash
docker exec ops-backup-runner /scripts/backup-all.sh
```

### Yedekler nerede

| Konum | Yol | Not |
|-------|-----|-----|
| Yerel (VDS) | `/root/backups/agent-icerik/daily/` ve `weekly/` | Restore için birincil kaynak |
| MinIO | `opsbackup/db-backups/agent-icerik/...` | Aynı VDS — **offsite sayılmaz** |
| Google Drive | `gdrive:backups/agent-icerik/` | **Gerçek offsite** (`rclone sync`, script sonunda) |

Offsite listeleme (host’ta rclone config):

```bash
docker run --rm \
  -v /root/.config/rclone:/config/rclone:ro \
  rclone/rclone lsl gdrive:backups/agent-icerik/daily/
```

> **Uyarı:** rclone şu an paylaşımlı Google Drive `client_id` kullanıyor; 2026’da kesilme riski var. İleride kendi Google Cloud OAuth `client_id` / `client_secret` ile rclone config güncellenmeli.

GDrive’dan yerel kopya (felaket / yeni sunucu):

```bash
mkdir -p /root/backups/agent-icerik
docker run --rm \
  -v /root/.config/rclone:/config/rclone:ro \
  -v /root/backups/agent-icerik:/data \
  rclone/rclone sync gdrive:backups/agent-icerik/ /data/
```

### Restore — içerik (posts + _queue)

Yedekte arşiv kökünde `posts/` ve `_queue/` vardır. En güncel stamp’i seçin (örnek: `20260915-055908`).

```bash
STAMP=20260915-055908
BACKUP="/root/backups/agent-icerik/daily/${STAMP}.content-posts-queue.tar.gz"
WORK="/root/restore-work-content"
SITE="/root/agent-icerik-sistemi/site/src/content"

rm -rf "$WORK"
mkdir -p "$WORK"
tar -xzf "$BACKUP" -C "$WORK"

# Canlıya yazmadan önce sayım kontrolü (testte: 992 posts + 6 _queue = 998 .md)
find "$WORK/posts" -name '*.md' | wc -l
find "$WORK/_queue" -name '*.md' | wc -l

# Felaket anında: mevcut içeriğin üzerine (önce yedek alın)
rsync -a "$WORK/posts/" "$SITE/posts/"
rsync -a "$WORK/_queue/" "$SITE/_queue/"

# Siteyi yeniden yayınla
/root/agent-icerik-sistemi/scripts/build-and-deploy-site.sh
```

### Restore — n8n Postgres (doğrulama, test edildi)

Boş geçici DB’ye yükleme — **production’a yazmaz**:

```bash
STAMP=20260915-055908
DUMP="/root/backups/agent-icerik/daily/${STAMP}.n8n-postgres.dump"

docker run -d --name restore-test-n8n-pg \
  -e POSTGRES_PASSWORD=test postgres:16-alpine
# hazır olana kadar bekleyin: docker exec restore-test-n8n-pg pg_isready -U postgres

docker exec restore-test-n8n-pg psql -U postgres -c "CREATE ROLE n8n LOGIN PASSWORD 'test';"
docker exec restore-test-n8n-pg psql -U postgres -c "CREATE DATABASE n8n OWNER n8n;"
docker exec restore-test-n8n-pg psql -U postgres -d n8n -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

docker cp "$DUMP" restore-test-n8n-pg:/tmp/n8n.dump
docker exec restore-test-n8n-pg pg_restore -U postgres -d n8n --no-owner --role=n8n /tmp/n8n.dump
# exit code 1 gelebilir: yalnızca extension ownership uyarısı (testte veri eksiksiz geldi)

docker exec restore-test-n8n-pg psql -U n8n -d n8n -c "
SELECT 'email_subscribers', count(*) FROM email_subscribers
UNION ALL SELECT 'twitter_queue', count(*) FROM twitter_queue
UNION ALL SELECT 'notify_queue', count(*) FROM notify_queue
UNION ALL SELECT 'used_cover_photos', count(*) FROM used_cover_photos
UNION ALL SELECT 'workflow_entity', count(*) FROM workflow_entity;"

docker rm -f restore-test-n8n-pg
```

**Canlı n8n veritabanına restore (felaket senaryosu — test edilmedi, dikkatli ilerle):**

Compose servisi `n8n` → konteyner `agent-n8n`; DB servisi `n8n-postgres` → `agent-n8n-postgres`.

1. Yedekten önce mevcut dump alın.
2. n8n uygulamasını durdurun (`agent-n8n`; Postgres’e yazmayı keser):

```bash
cd /root/agent-icerik-sistemi
docker compose -f n8n/docker-compose.yml stop n8n
```

3. Dump’ı `agent-n8n-postgres` içine yükleyin. Testte kullanılan bayraklar: `--no-owner --role=n8n`. Mevcut dolu DB’nin üzerine yazmak için strateji (drop/recreate, `pg_restore --clean`, vb.) **production’da denenmedi** — adım adım planlayın, tek seferde uygulayın.

```bash
STAMP=20260915-055908
DUMP="/root/backups/agent-icerik/daily/${STAMP}.n8n-postgres.dump"

docker cp "$DUMP" agent-n8n-postgres:/tmp/n8n.restore.dump
docker exec agent-n8n-postgres pg_restore -U n8n -d n8n --no-owner --role=n8n /tmp/n8n.restore.dump
```

4. n8n’i tekrar başlatın:

```bash
cd /root/agent-icerik-sistemi
docker compose -f n8n/docker-compose.yml start n8n
```

### Restore — Umami Postgres (doğrulama, test edildi)

```bash
STAMP=20260915-055908
DUMP="/root/backups/agent-icerik/daily/${STAMP}.umami-postgres.dump"

docker run -d --name restore-test-umami-pg \
  -e POSTGRES_PASSWORD=test postgres:15-alpine

docker exec restore-test-umami-pg psql -U postgres -c "CREATE ROLE umami LOGIN PASSWORD 'test';"
docker exec restore-test-umami-pg psql -U postgres -c "CREATE DATABASE umami OWNER umami;"
docker exec restore-test-umami-pg psql -U postgres -d umami -c 'CREATE EXTENSION IF NOT EXISTS pgcrypto;'

docker cp "$DUMP" restore-test-umami-pg:/tmp/umami.dump
docker exec restore-test-umami-pg pg_restore -U postgres -d umami --no-owner --role=umami /tmp/umami.dump

docker exec restore-test-umami-pg psql -U umami -d umami -c "
SELECT 'website', count(*) FROM website
UNION ALL SELECT 'session', count(*) FROM session
UNION ALL SELECT 'website_event', count(*) FROM website_event
UNION ALL SELECT 'user', count(*) FROM \"user\";"

docker rm -f restore-test-umami-pg
```

**Canlı Umami DB (felaket senaryosu — test edilmedi, dikkatli ilerle):**

Compose servisi `umami` → konteyner `agent-umami`; DB servisi `umami-db` → `agent-umami-db`.

1. Yedekten önce mevcut dump alın.
2. Umami uygulamasını durdurun (`agent-umami`):

```bash
cd /root/agent-icerik-sistemi
docker compose -f analytics/docker-compose.yml stop umami
```

3. Dump’ı `agent-umami-db` içine yükleyin (testteki bayraklar: `--no-owner --role=umami`). Dolu DB’nin üzerine yazma stratejisi **production’da denenmedi**.

```bash
STAMP=20260915-055908
DUMP="/root/backups/agent-icerik/daily/${STAMP}.umami-postgres.dump"

docker cp "$DUMP" agent-umami-db:/tmp/umami.restore.dump
docker exec agent-umami-db pg_restore -U umami -d umami --no-owner --role=umami /tmp/umami.restore.dump
```

4. Umami’yi tekrar başlatın:

```bash
cd /root/agent-icerik-sistemi
docker compose -f analytics/docker-compose.yml start umami
```

### Restore — n8n_n8n_data volume

Volume adı: `n8n_n8n_data` (`n8n/docker-compose.yml`).

```bash
STAMP=20260915-055908
TAR="/root/backups/agent-icerik/daily/${STAMP}.n8n_n8n_data.tar.gz"

cd /root/agent-icerik-sistemi
docker compose -f n8n/docker-compose.yml stop n8n

docker run --rm \
  -v n8n_n8n_data:/data \
  -v "$(dirname "$TAR"):/in:ro" \
  alpine:3.20 \
  sh -c "cd /data && tar -xzf /in/$(basename "$TAR")"

docker compose -f n8n/docker-compose.yml start n8n
```

### Test özeti (15 Eylül 2026)

- **Content:** 998 `.md`; rastgele post’larda frontmatter + dosya SHA256 canlı ile birebir eşleşti.
- **n8n Postgres:** Tablo satırları canlı ile eşleşti; yedekten sonra canlıda biriken küçük farklar normal (ör. `twitter_queue` +6).
- **Umami:** `website` 1, `session` 137, `website_event` 1030, `user` 1 — canlı ile aynı.
- **n8n_n8n_data:** `config`, `storage/workflows/…/binary_data`, event log’lar mevcut.
- **Sorun yok:** Postgres 16 / 15 uyumu, encoding sorunu yok. Tek uyarı: `uuid-ossp` / `pgcrypto` extension ownership (`pg_restore` exit 1, veri kaybı yok).
