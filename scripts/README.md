# scripts/ — ne var, hangisi hâlâ gerekli?

Bu klasör zamanla doldu: n8n workflow yamaları (`patch-workflow-*`), backfill’ler, recovery
script’leri, deploy yardımcıları ve bir kerelik testler bir arada duruyor. Hangisinin
cron/n8n/deploy akışında **hâlâ çağrıldığı**, hangisinin **bir kez çalıştırılıp bittiği**
veya **acil durum referansı** olduğu belirsizleşti.

Bu README yalnızca envanterdir. Tipler:

| Tip | Anlamı |
|-----|--------|
| **Sürekli/aktif** | Cron, systemd, n8n veya deploy zincirinde hâlâ çalışıyor |
| **Aktif yardımcı** | Periyodik değil; eksik EN vb. durumlarda hâlâ doğru araç |
| **Tek seferlik migration/backfill** | Bir kez çalıştırılmış yama/veri taşıma; yeniden koşmak genelde anlamsız veya riskli |
| **Recovery/acil durum** | Belirli bir execution/arıza sonrası kurtarma; benzer arızada referans |
| **Test/doğrulama** | Elle smoke/unit yardımcıları |
| **Arşiv** | `scripts/archive/` — tarihsel, workflow eskidi veya Claude yolu terk edildi |

Tarihler: `git log --follow` ile dosyanın **ilk görüldüğü** commit tarihi (+ docstring’teki aşama notu varsa).

---

## Envanter

### Sürekli / aktif

| Dosya | Tip | Ne işe yarıyor | Hâlâ kullanımda mı |
|-------|-----|----------------|--------------------|
| `build-and-deploy-site.sh` | Sürekli/aktif | Astro `npm run build` + `rsync` → `/var/www/blog`; perms script’ini de çağırır. | **Evet** — cron `*/30`; `deploy-listener` da tetikler (2026-08-17) |
| `deploy-listener.py` | Sürekli/aktif | Docker bridge üzerinden HTTP dinler; n8n yayın sonrası build/deploy (ve R2) tetikler. | **Evet** — `scripts/deploy-listener.py` **symlink** → `/usr/local/lib/agent-icerik/deploy-listener.py` (systemd canonical; 2026-08-20) |
| `ensure-n8n-content-perms.sh` | Sürekli/aktif | `posts/` + `_queue/` sahipliğini n8n uid 1000 yapar; pending dosyasını garantiler. | **Evet** — cron `*/15` + build script içinden (2026-09-08) |
| `weekly-digest.sh` | Sürekli/aktif | Son 7 gün TR yazılarından `weekly-digest.txt` üretir (Medium taslağı için). | **Evet** — cron Perşembe 09:55; n8n “Haftalık Medium Taslağı” dosyayı okur (2026-08-17) |
| `telegram-subscribers.js` | Sürekli/aktif | n8n Execute Command ile `telegram-subscribers.jsonl` subscribe/unsubscribe. | **Evet** — “Telegram Abonelik Yakala” workflow (2026-08-20) |

### Aktif yardımcı (elle, ihtiyaç oldukça)

| Dosya | Tip | Ne işe yarıyor | Hâlâ kullanımda mı |
|-------|-----|----------------|--------------------|
| `backfill-en-libretranslate.py` | Aktif yardımcı | Eksik EN post’ları TR’den LibreTranslate ile backfill (asama49). | **Evet** — Claude yolu terk edildi; EN açığı için tercih edilen araç (2026-09-08 / asama49) |
| `backfill-en-missing-esc-tdz.py` | Aktif yardımcı | Eksik EN backfill (esc-TDZ recovery varyantı). | **Evet** — aynı aile; spesifik TDZ/kaçış hatası sonrası (2026-09-08) |

### Tek seferlik migration / backfill / workflow yaması

Bunlar n8n JSON’unu veya disk içeriğini bir kez değiştirmek için yazıldı; canlıda periyodik çağrı yok.
Yeniden çalıştırmadan önce workflow/DB durumunu kontrol et.

| Dosya | Tip | Ne işe yarıyor | Hâlâ kullanımda mı |
|-------|-----|----------------|--------------------|
| `patch-workflow-slug-restore.py` | Tek seferlik | Empty-slug: Frontmatter öncesi post alanlarını geri yükle. | Hayır (2026-08-20) |
| `patch-workflow-twitter-queue.py` | Tek seferlik | Haber Yayınlama’ya Twitter kuyruk enqueue adımı ekler. | Hayır (2026-08-20) |
| `patch-workflow-twitter-ntfy.py` | Tek seferlik | Twitter işleyicide X API yerine ntfy push. | Hayır (2026-08-20) |
| `patch-workflow-unsplash-keyword.py` | Tek seferlik | Anahtar Kelime Cikar: whitespace / metafor filtresi / multi-item. | Hayır (2026-08-20) |
| `patch-workflow-asama49.py` | Tek seferlik | Aşama 49: LibreTranslate veri kaybı düzeltmesi + kelime sayısı log. | Hayır (2026-09-08 / asama49) |
| `patch-workflow-asama49-notify.py` | Tek seferlik | Aşama 49: Telegram+Email’i Twitter tarzı kuyruğa alır. | Hayır (2026-09-08 / asama49) |
| `patch-workflow-dedupe-asama49.py` | Tek seferlik | Yeniden yayın: published-links indeksi + prefilter sertleştirme. | Hayır (2026-09-08 / asama49) |
| `dedupe-posts-asama49.py` | Tek seferlik | Yayındaki yazıları kaynak URL (+ benzer başlık) ile dedupe; indeks rebuild. | Hayır (2026-09-08 / asama49) |
| `patch-workflow-asama50.py` | Tek seferlik | Aşama 50: ATLA kuyruk temizliği + taze/kaynak öncelikli sıra. | Hayır (2026-09-08 / asama50) |
| `cleanup-pending-asama50.py` | Tek seferlik | pending.jsonl’den bayat arXiv + junk temizliği. | Hayır (2026-09-08 / asama50) |
| `patch-workflow-asama55-tags.py` | Tek seferlik | Aşama 55: Claude çıktısına etiket + frontmatter `tags`. | Hayır (2026-09-08 / asama55) |
| `patch-workflow-tag-labels-i18n.py` | Tek seferlik | Etiketlere slug + TR/EN görünen ad (`tagLabels`). | Hayır (2026-09-08) |
| `build-weekly-digest-workflow.py` | Tek seferlik | Aşama 55: Haftalık özet e-posta n8n workflow’unu üretir/yükler. | Hayır — workflow artık canlı; script bir kerelik kurulum (2026-09-08 / asama55) |
| `backfill-asama56.py` | Tek seferlik | Aşama 56: Eski yazılara kapak + etiket backfill. | Hayır (2026-09-08 / asama56) |
| `patch-workflow-article-length.py` | Tek seferlik | TR prompt uzunluğu / maxTokens; kısa/kesik split’leri kaldır. | Hayır (2026-09-08) |
| `patch-workflow-article-readable.py` | Tek seferlik | Daha kısa, madde işaretli okunabilir yazı hedefi. | Hayır (2026-09-08) |
| `patch-workflow-ayristir-140-webhook.py` | Tek seferlik | 14:50 sessiz düşüş: kelime filtresi + webhook tetik. | Hayır (2026-09-08) |
| `patch-workflow-batch-limit-7.py` | Tek seferlik | BATCH_LIMIT 5 → 7. | Hayır (2026-09-08) |
| `patch-workflow-cover-cooldown.py` | Tek seferlik | 7 gün Unsplash cover cooldown (`used_cover_photos`). | Hayır (2026-09-08) |
| `patch-workflow-cover-relevance.py` | Tek seferlik | Unsplash keyword + relevance; junk kapakları azalt. | Hayır (2026-09-08) |
| `patch-workflow-haiku-peritem.py` | Tek seferlik | TR Haiku + haber başına Claude çağrısı + truncation guard. | Hayır (2026-09-08) |
| `patch-workflow-multiitem-queue.py` | Tek seferlik | Multi-item sessiz drop + seçici pending temizliği. | Hayır (2026-09-08) |
| `patch-workflow-notify-dedupe.py` | Tek seferlik | Email/TG/Twitter notify’yi yalnızca gerçekten yeni post’lara kısıtla. | Hayır (2026-09-08) |
| `patch-workflow-p0-libretranslate.py` | Tek seferlik | P0 kuyruk limiti/prefilter/arXiv cap; Claude EN → LibreTranslate. | Hayır (2026-09-08) |
| `patch-workflow-pending-ensure.py` | Tek seferlik | İlk kuyruk okumasından önce pending.jsonl ensure (executeCommand). | Hayır (2026-09-08) |
| `patch-workflow-toplama-multitem-recover.py` | Tek seferlik | Toplama multi-item append + lastItemDate skip sonrası feed recover. | Hayır (2026-09-08) |
| `patch-workflow-twitter-random-r2.py` | Tek seferlik | Twitter aralığı rastgele + R2 cover URL restore. | Hayır (2026-09-08) |
| `fix-duplicate-covers.py` | Tek seferlik | Yayındaki tekrarlayan kapakları düzelt (asama46); Unsplash refetch. | Hayır (2026-09-08 / asama46) |
| `migrate-categories-14.py` | Tek seferlik | TR/EN post’ları 14 kategoriye kural tabanlı taşı; unmatched listesi yaz. | Hayır (2026-09-09) |
| `patch-workflow-categories-14.py` | Tek seferlik | Claude kategori listesi + EN categoryMap → 14 kategori. | Hayır (2026-09-09) |
| `patch-workflow-catmap-14.py` | Tek seferlik | Unsplash catMap’i 14 kategoriye genişlet. | Hayır (2026-09-09) |
| `patch-workflow-covers-prefix.py` | Tek seferlik | R2 key + public URL’de `covers/` prefix. | Hayır (2026-09-09) |
| `patch-workflow-unsplash-harden.py` | Tek seferlik | Unsplash 403/rate-limit tüm yayın run’ını öldürmesin. | Hayır (2026-09-09) |
| `patch-staggered-site-publish.py` | Tek seferlik | Staggered yayın: MD → `_queue/scheduled`, Twitter zamanına senkron promote/deploy. | Hayır (2026-09-09) |
| `patch-site-promote-nopath-r2-acl.py` | Tek seferlik | Site Yayina Al path zorunluluğu + R2 ACL Forbidden düzeltmesi. | Hayır (2026-09-09) |
| `backfill-unsplash-to-r2-cdn.py` | Tek seferlik | Unsplash hotlink → R2 **API’siz** (CDN indir); API banned/limited sonrası bitirme aracı. Aynı state dosyasını kullanır. | Hayır (2026-09-09) — kalan Unsplash hotlink için tercih edilen araç |
| `patch-queue-site-sync.py` | Tek seferlik | Twitter + notify kuyruklarını tek “site go-live” kapısına bağlar. | Hayır (2026-09-11) |
| `refetch-covers-20260820.py` | Tek seferlik | 20260820-12* recovery post’larının kapaklarını yeni keyword mantığıyla yenile. | Hayır (2026-08-20) |

### Recovery / acil durum

| Dosya | Tip | Ne işe yarıyor | Hâlâ kullanımda mı |
|-------|-----|----------------|--------------------|
| `recover-exec509-posts.py` | Recovery | Exec #509 Claude çıktısından TR post kurtarma (Claude/R2/Unsplash yok). | Hayır — referans (2026-08-20) |
| `notify-exec509-recovery.py` | Recovery | Exec #509 için bildirim; `twitter_queue`’ya dokunmaz. | Hayır — referans (2026-08-20) |
| `recover-exec537.py` | Recovery | Exec #537: TR + kapak (R2) + EN + twitter + pending cleanup. | Hayır — referans (2026-08-20) |
| `notify-exec537-recovery.py` | Recovery | Exec #537 recovery post’ları için TG + e-posta. | Hayır — referans (2026-08-20) |
| `recover-notify-exec5726.py` | Recovery | Exec 5726 (2026-09-03) kaçan TG/email/Twitter notify enqueue. | Hayır — referans (2026-09-08) |

### Test / doğrulama yardımcıları

| Dosya | Tip | Ne işe yarıyor | Hâlâ kullanımda mı |
|-------|-----|----------------|--------------------|
| `test-cover-cooldown.py` | Test | 7 günlük cover cooldown mantığı (izolasyon). | Hayır — elle (2026-09-08) |
| `test-libretranslate-quality.py` | Test | LibreTranslate kalite örnekleri + zincir smoke. | Hayır — elle (2026-09-08) |
| `test-multiitem-queue-logic.py` | Test | Multi-item restore / ayristir / seçici kuyruk clear. | Hayır — elle (2026-09-08) |
| `test-p0-queue-prefilter.py` | Test | P0 batch limit, prefilter, arXiv cap, queue keep. | Hayır — elle (2026-09-08) |
| `test-twitter-queue-logic.py` | Test | Twitter kuyruk zamanlama + tweet karakter bütçesi. | Hayır — elle (2026-08-20) |
| `test-unsplash-keyword.py` | Test | Unsplash keyword builder (Anahtar Kelime Cikar aynası). | Hayır — elle (2026-08-20) |
| `verify_18_10_post_deploy.py` | Test | 18:10 yayın/deploy sonrası post+cover+kuyruk doğrulama raporu (2026-08-19 odaklı). | Hayır — elle / tarihsel (2026-08-20) |

### Arşiv (`scripts/archive/`)

| Dosya | Tip | Ne işe yarıyordu | Not |
|-------|-----|------------------|-----|
| `archive/translate-remaining-posts.py` | Arşiv | EN’siz TR post’ları **Claude** ile toplu çevir. | LibreTranslate’e geçildi; n8n de LT kullanıyor — arşivlendi (2026-09-14) |
| `archive/patch-workflow-bolum3.py` | Arşiv | Haber Yayınlama: TR sonrası otomatik EN (Claude) + deploy öncesi. | Tarihsel; staggered + LibreTranslate yamalarıyla eskidi — arşivlendi (2026-09-14) |
| `archive/update-publish-workflow-deploy.py` | Arşiv | Deploy-before-telegram akışı. | Tarihsel; staggered publish ile eskidi — arşivlendi (2026-09-14) |
| `archive/backfill-unsplash-to-r2.py` | Arşiv | Unsplash hotlink → R2 **API’li** (attribution + download trigger). | CDN-only varyant (`backfill-unsplash-to-r2-cdn.py`) yerini aldı — arşivlendi (2026-09-14) |

---

## Hızlı referans — canlı çağrı noktaları

| Tetikleyici | Ne çağrılır |
|-------------|-------------|
| cron `*/30` | `scripts/build-and-deploy-site.sh` |
| cron `*/15` | `scripts/ensure-n8n-content-perms.sh` |
| cron Perşembe 09:55 | `scripts/weekly-digest.sh` |
| systemd `agent-icerik-deploy-listener` | **`/usr/local/lib/agent-icerik/deploy-listener.py`** (canonical; `scripts/deploy-listener.py` buna symlink) |
| n8n Haber Yayınlama / Twitter Kuyruk | HTTP `http://172.18.0.1:9876/deploy` (script path değil) |
| n8n “Telegram Abonelik Yakala” | `telegram-subscribers.js` (`/home/node/scripts/` mount) |
