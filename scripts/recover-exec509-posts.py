#!/usr/bin/env python3
"""Recover TR posts from execution #509 Claude output. No Claude/R2/Unsplash."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path('/root/agent-icerik-sistemi')
SRC = ROOT / 'n8n/backups/exec509-posts.json'
TR_DIR = ROOT / 'site/src/content/posts/tr'
QUEUE = ROOT / 'site/src/content/_queue/pending.jsonl'
MANIFEST = ROOT / 'n8n/backups/exec509-recovery-manifest.json'
MIN_BODY = 200

IST = timezone(timedelta(hours=3))
PUB = datetime(2026, 8, 20, 12, 0, 0, tzinfo=IST)

TR_MAP = str.maketrans(
    {
        'ğ': 'g',
        'ü': 'u',
        'ş': 's',
        'ı': 'i',
        'ö': 'o',
        'ç': 'c',
        'Ğ': 'g',
        'Ü': 'u',
        'Ş': 's',
        'İ': 'i',
        'Ö': 'o',
        'Ç': 'c',
    }
)


def slugify(s: str) -> str:
    s = s.translate(TR_MAP).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def esc(s: str) -> str:
    return str(s or '').replace('"', "'")


def first_sentence(summary: str) -> str:
    summary = (summary or '').strip()
    parts = re.split(r'(?<=[.!?…])\s+', summary)
    return (parts[0] if parts else summary)[:280]


def main() -> None:
    posts = json.loads(SRC.read_text())
    recovered = []
    skipped = []

    for i, p in enumerate(posts):
        baslik = (p.get('baslik') or '').strip()
        icerik = (p.get('icerik') or '').strip()
        if len(icerik) < MIN_BODY:
            skipped.append(
                {
                    'index': i + 1,
                    'baslik': baslik,
                    'reason': f'truncated icerik ({len(icerik)} chars)',
                    'icerik': icerik,
                }
            )
            continue

        slug_part = slugify(baslik)
        if not slug_part:
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': 'empty slug'})
            continue

        ts = PUB + timedelta(seconds=i)
        ts_token = ts.strftime('%Y%m%d-%H%M%S')
        dosya_adi = f'{slug_part}-{ts_token}'
        if dosya_adi.startswith('-') or re.match(r'^-\d{8}', dosya_adi):
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': 'timestamp-only slug'})
            continue

        dest = TR_DIR / f'{dosya_adi}.md'
        if dest.exists():
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': f'file exists {dest.name}'})
            continue

        cover = (p.get('gorsel_url') or p.get('gorsel_r2_url') or '').strip()
        ozet = (p.get('ozet') or '').strip()
        kategori = (p.get('kategori') or 'Teknoloji').strip()
        link = (p.get('link') or '').strip()
        pub_iso = ts.isoformat()

        md = (
            '---\n'
            f'title: "{esc(baslik)}"\n'
            f'pubDate: {pub_iso}\n'
            f'kategori: "{esc(kategori)}"\n'
            f'description: "{esc(ozet[:150])}"\n'
            f'kaynak: "{esc(link)}"\n'
            f'coverImage: "{esc(cover)}"\n'
            f'gorselFotografci: "{esc(p.get("gorsel_fotografci") or "")}"\n'
            f'gorselFotografciLink: "{esc(p.get("gorsel_fotografci_link") or "")}"\n'
            '---\n'
            f'{icerik}\n'
        )
        dest.write_text(md, encoding='utf-8')
        recovered.append(
            {
                'index': i + 1,
                'baslik': baslik,
                'dosya_adi': dosya_adi,
                'path': str(dest),
                'kategori': kategori,
                'ozet': ozet,
                'link': link,
                'post_link': f'https://bilisimpostasi.com.tr/posts/{dosya_adi}/',
                'post_summary': first_sentence(ozet),
            }
        )
        print(f'WROTE {dest.name}  slug_ok={bool(slug_part)}')

    n = len(recovered)
    step = 180 / n if n else 0
    now = datetime.now(timezone.utc)
    for i, rec in enumerate(recovered):
        rec['scheduled_at'] = (now + timedelta(minutes=i * step)).isoformat()
        rec['schedule_step_min'] = step

    MANIFEST.write_text(json.dumps({'recovered': recovered, 'skipped': skipped}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'recovered={n} skipped={len(skipped)} manifest={MANIFEST}')

    # Strip recovered source URLs from pending.jsonl so next cycle does not duplicate.
    used = set()
    for rec in recovered:
        link = rec['link'].rstrip('/')
        used.add(link)
        used.add(link + '/')
        # also without trailing path variants
        used.add(rec['link'])

    q_backup = QUEUE.with_suffix('.jsonl.bak-exec509-recovery')
    raw = QUEUE.read_text(encoding='utf-8')
    q_backup.write_text(raw, encoding='utf-8')
    kept = []
    removed = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        link = str(row.get('link') or '').strip()
        variants = {link, link.rstrip('/'), link.rstrip('/') + '/'}
        if variants & used:
            removed += 1
            continue
        kept.append(line)
    QUEUE.write_text(('\n'.join(kept) + ('\n' if kept else '')), encoding='utf-8')
    print(f'pending.jsonl removed={removed} remaining={len(kept)} backup={q_backup}')


if __name__ == '__main__':
    main()
