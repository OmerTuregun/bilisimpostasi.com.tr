#!/usr/bin/env python3
"""LibreTranslate quality samples + chain smoke test."""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
LT_URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5000/translate'

SAMPLES = [
    {
        'label': 'ChatGPT iMessages',
        'file': 'chatgpt-mac-te-apple-imessages-i-okuyup-yanitlayabiliyor-yapay-zeka-ve-mesajlasma-entegrasyonu-20260821-120000.md',
    },
    {
        'label': 'DeepSeek Vision',
        'file': 'deepseek-vision-api-ile-yapay-zeka-goruntu-analizi-yeni-boyuta-cikiyor-20260821-120001.md',
    },
    {
        'label': 'Patreon algorithm',
        'file': 'patreon-kucuk-i-cerik-ureticilerinin-kesfedilmesini-saglamak-i-cin-algoritmasini-yeniliyor-20260821-120002.md',
    },
]


def parse_fm(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$', text)
    if not m:
        raise ValueError('no frontmatter')
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'^(\w+):\s*"(.*)"\s*$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2)
            continue
        mm = re.match(r'^(\w+):\s*(.+)\s*$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"')
    return fm, m.group(2).strip()


def translate(text: str, timeout: int = 120) -> str:
    payload = json.dumps({'q': text, 'source': 'tr', 'target': 'en', 'format': 'text'}).encode()
    req = urllib.request.Request(
        LT_URL,
        data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'bilisimpostasi-lt-test/1.0'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return str(data.get('translatedText') or '').strip()


def category_map(tr_kategori: str) -> str:
    return {'Yapay Zeka': 'AI', 'Teknoloji': 'Technology', 'Güvenlik': 'Security'}.get(tr_kategori, 'Technology')


def build_en_markdown(fm: dict[str, str], en_title: str, en_summary: str, en_body: str) -> str:
    esc = lambda s: str(s or '').replace('"', "'")
    cat = category_map(fm.get('kategori', ''))
    return (
        f'---\n'
        f'title: "{esc(en_title)}"\n'
        f'pubDate: {fm.get("pubDate", "")}\n'
        f'kategori: "{cat}"\n'
        f'description: "{esc(en_summary[:150])}"\n'
        f'kaynak: "{esc(fm.get("kaynak", ""))}"\n'
        f'coverImage: "{esc(fm.get("coverImage", ""))}"\n'
        f'---\n'
        f'{en_body}\n'
    )


def main() -> None:
    report = {'url': LT_URL, 'samples': [], 'chain_ok': True}

    # health
    base = LT_URL.rsplit('/', 1)[0]
    try:
        req = urllib.request.Request(f'{base}/languages', headers={'User-Agent': 'test'})
        with urllib.request.urlopen(req, timeout=15) as r:
            langs = json.loads(r.read().decode())
        codes = {x.get('code') for x in langs}
        print('languages:', sorted(codes))
        assert 'tr' in codes and 'en' in codes
    except Exception as e:
        print('FAIL languages:', e)
        sys.exit(1)

    for s in SAMPLES:
        path = TR_DIR / s['file']
        text = path.read_text(encoding='utf-8')
        fm, body = parse_fm(text)
        title = fm.get('title', '')
        summary = fm.get('description', '')
        print(f"\n=== {s['label']} ===")
        print('TR title:', title[:100])
        en_title = translate(title, 30)
        en_summary = translate(summary, 30)
        # body excerpt only for quality report (full body is slow)
        body_excerpt = body[:800]
        en_body_excerpt = translate(body_excerpt, 120)
        md = build_en_markdown(fm, en_title, en_summary, en_body_excerpt)
        ok = bool(en_title and en_body_excerpt and md.startswith('---'))
        print('EN title:', en_title[:120])
        print('EN summary:', en_summary[:120])
        print('EN body excerpt:', en_body_excerpt[:300], '...')
        print('markdown ok:', ok)
        report['samples'].append({
            'label': s['label'],
            'tr_title': title,
            'en_title': en_title,
            'tr_summary': summary,
            'en_summary': en_summary,
            'en_body_excerpt': en_body_excerpt,
            'markdown_ok': ok,
        })
        if not ok:
            report['chain_ok'] = False

    out = ROOT / 'n8n/backups/libretranslate-quality-report.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\nreport ->', out)
    if not report['chain_ok']:
        sys.exit(1)
    print('ALL LT TESTS PASSED')


if __name__ == '__main__':
    main()
