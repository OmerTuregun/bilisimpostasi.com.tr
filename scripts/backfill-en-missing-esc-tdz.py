#!/usr/bin/env python3
"""Backfill missing EN posts from TR via LibreTranslate (esc-TDZ recovery)."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
LT = 'http://127.0.0.1:5000/translate'
REPORT = ROOT / 'n8n/backups/en-backfill-esc-tdz-report.json'
LOG = ROOT / 'n8n/backups/en-backfill-esc-tdz.log'

CATEGORY_MAP = {
    'Yapay Zeka': 'AI',
    'Teknoloji': 'Technology',
    'Güvenlik': 'Security',
    'AI': 'AI',
    'Technology': 'Technology',
    'Security': 'Security',
}


def log(msg: str) -> None:
    line = f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(line, flush=True)
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def translate(text: str, retries: int = 4) -> str:
    text = (text or '').strip()
    if not text:
        return ''
    payload = json.dumps({'q': text, 'source': 'tr', 'target': 'en', 'format': 'text'}).encode()
    last: Exception | None = None
    for i in range(retries):
        try:
            req = urllib.request.Request(LT, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())['translatedText'].strip()
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(str(last))


def parse_post(raw: str) -> tuple[dict, list[str], dict, str]:
    m = re.match(r'^---\n([\s\S]*?)\n---\n([\s\S]*)$', raw)
    if not m:
        return {}, [], {}, raw
    fm_raw, body = m.group(1), m.group(2)
    meta: dict[str, str] = {}
    tags: list[str] = []
    tag_labels: dict[str, dict[str, str]] = {}
    in_tags = False
    in_labels = False
    cur = ''
    for line in fm_raw.splitlines():
        if line.startswith('tags:'):
            in_tags, in_labels = True, False
            continue
        if line.startswith('tagLabels:'):
            in_tags, in_labels = False, True
            continue
        if in_tags and re.match(r'^\s+-\s+', line):
            tags.append(line.split('-', 1)[1].strip())
            continue
        if in_labels:
            ms = re.match(r'^\s{2}([a-z0-9-]+):\s*$', line)
            if ms:
                cur = ms.group(1)
                tag_labels[cur] = {'tr': '', 'en': ''}
                continue
            mtr = re.match(r'^\s{4}tr:\s*"?(.*?)"?\s*$', line)
            men = re.match(r'^\s{4}en:\s*"?(.*?)"?\s*$', line)
            if cur and mtr:
                tag_labels[cur]['tr'] = mtr.group(1)
                continue
            if cur and men:
                tag_labels[cur]['en'] = men.group(1)
                continue
        in_tags = False
        in_labels = False
        if ':' in line and not line.startswith(' '):
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, tags, tag_labels, body.strip()


def esc(s: str) -> str:
    return str(s or '').replace('"', "'")


def build_en(meta: dict, tags: list[str], tag_labels: dict, en_title: str, en_desc: str, en_body: str) -> str:
    kat = CATEGORY_MAP.get(meta.get('kategori', ''), 'Technology')
    lines = [
        '---',
        f'title: "{esc(en_title)}"',
        f'pubDate: {meta.get("pubDate", "")}',
        f'kategori: "{kat}"',
    ]
    if tags:
        lines.append('tags:')
        for t in tags:
            lines.append(f'  - {t}')
    if tag_labels:
        lines.append('tagLabels:')
        for slug in tags:
            lb = tag_labels.get(slug) or {'tr': slug, 'en': slug}
            lines.append(f'  {slug}:')
            lines.append(f'    tr: "{esc(lb.get("tr", slug))}"')
            lines.append(f'    en: "{esc(lb.get("en", slug))}"')
    lines += [
        f'description: "{esc(en_desc[:150])}"',
        f'kaynak: "{esc(meta.get("kaynak", ""))}"',
        f'coverImage: "{esc(meta.get("coverImage", ""))}"',
        f'gorselFotografci: "{esc(meta.get("gorselFotografci", ""))}"',
        f'gorselFotografciLink: "{esc(meta.get("gorselFotografciLink", ""))}"',
    ]
    if meta.get('gorselQuery'):
        lines.append(f'gorselQuery: "{esc(meta.get("gorselQuery", ""))}"')
    lines.append('---')
    lines.append(en_body)
    lines.append('')
    return '\n'.join(lines)


def main() -> None:
    EN_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for tr in sorted(TR_DIR.glob('*.md')):
        en = EN_DIR / tr.name
        if not en.exists() or en.stat().st_size < 50:
            missing.append(tr)
    log(f'missing EN: {len(missing)}')
    ok, fail = [], []
    for i, tr in enumerate(missing, 1):
        try:
            meta, tags, tag_labels, body = parse_post(tr.read_text(encoding='utf-8'))
            log(f'[{i}/{len(missing)}] {tr.name}')
            en_title = translate(meta.get('title', ''))
            en_desc = translate(meta.get('description', '')) if meta.get('description') else ''
            en_body = translate(body)
            if not en_title or not en_body:
                raise RuntimeError('empty translation')
            (EN_DIR / tr.name).write_text(
                build_en(meta, tags, tag_labels, en_title, en_desc, en_body),
                encoding='utf-8',
            )
            ok.append({'file': tr.name, 'en_title': en_title})
            time.sleep(0.25)
        except Exception as e:
            fail.append({'file': tr.name, 'error': str(e)})
            log(f'  FAIL {e}')
    REPORT.write_text(json.dumps({'ok': ok, 'fail': fail}, ensure_ascii=False, indent=2), encoding='utf-8')
    log(f'done ok={len(ok)} fail={len(fail)} -> {REPORT}')


if __name__ == '__main__':
    main()
