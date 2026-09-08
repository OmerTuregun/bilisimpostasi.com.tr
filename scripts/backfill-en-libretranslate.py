#!/usr/bin/env python3
"""Backfill missing EN posts from TR via LibreTranslate (asama49)."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

TR_DIR = Path('/root/agent-icerik-sistemi/site/src/content/posts/tr')
EN_DIR = Path('/root/agent-icerik-sistemi/site/src/content/posts/en')
LT = 'http://127.0.0.1:5000/translate'

CATEGORY_MAP = {
    'Yapay Zeka': 'AI',
    'Teknoloji': 'Technology',
    'Güvenlik': 'Security',
    'AI': 'AI',
    'Technology': 'Technology',
    'Security': 'Security',
}


def translate(text: str, retries: int = 3) -> str:
    text = (text or '').strip()
    if not text:
        return ''
    payload = json.dumps(
        {'q': text, 'source': 'tr', 'target': 'en', 'format': 'text'}
    ).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                LT, data=payload, headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())['translatedText'].strip()
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise RuntimeError(last)


def parse_fm(raw: str) -> tuple[dict, str]:
    m = re.match(r'^---\n([\s\S]*?)\n---\n([\s\S]*)$', raw)
    if not m:
        return {}, raw
    meta = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2).strip()


def main() -> None:
    EN_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for tr in sorted(TR_DIR.glob('*.md')):
        # Only Aug 24+ where EN never arrived
        if not re.search(r'202608(2[4-9]|3\d)', tr.name):
            continue
        en = EN_DIR / tr.name
        if en.exists() and en.stat().st_size > 50:
            continue
        missing.append(tr)

    print(f'missing EN: {len(missing)}')
    samples = []
    for i, tr in enumerate(missing):
        raw = tr.read_text(encoding='utf-8')
        meta, body = parse_fm(raw)
        title = meta.get('title', '')
        desc = meta.get('description', '')
        print(f'[{i+1}/{len(missing)}] {tr.name} …', flush=True)
        en_title = translate(title)
        en_desc = translate(desc) if desc else ''
        en_body = translate(body)
        if not en_title or not en_body:
            print('  FAIL empty translation')
            continue
        kat = CATEGORY_MAP.get(meta.get('kategori', ''), 'Technology')
        esc = lambda s: str(s or '').replace('"', "'")
        md = (
            f'---\n'
            f'title: "{esc(en_title)}"\n'
            f'pubDate: {meta.get("pubDate", "")}\n'
            f'kategori: "{kat}"\n'
            f'description: "{esc(en_desc[:150])}"\n'
            f'kaynak: "{esc(meta.get("kaynak", ""))}"\n'
            f'coverImage: "{esc(meta.get("coverImage", ""))}"\n'
            f'gorselFotografci: "{esc(meta.get("gorselFotografci", ""))}"\n'
            f'gorselFotografciLink: "{esc(meta.get("gorselFotografciLink", ""))}"\n'
            f'---\n'
            f'{en_body}\n'
        )
        (EN_DIR / tr.name).write_text(md, encoding='utf-8')
        if len(samples) < 3:
            samples.append((title, en_title, body[:180], en_body[:180]))
        time.sleep(0.2)

    report = Path('/root/agent-icerik-sistemi/n8n/backups/asama49-en-backfill-samples.json')
    report.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding='utf-8')
    print('samples ->', report)
    print('done EN count Aug24+:', len(list(EN_DIR.glob('*2026082[4-9]*'))))


if __name__ == '__main__':
    main()
