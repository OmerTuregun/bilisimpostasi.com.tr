#!/usr/bin/env python3
"""One-off batch: translate TR posts without EN counterpart."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
LOG_PATH = ROOT / 'n8n/translate-batch.log'
ENV_PATH = ROOT / 'n8n/.env'

CAT_MAP = {
    'Yapay Zeka': 'AI',
    'Teknoloji': 'Technology',
    'Güvenlik': 'Security',
    'AI': 'AI',
    'Technology': 'Technology',
    'Security': 'Security',
}


def load_api_key() -> str:
    for line in ENV_PATH.read_text().splitlines():
        if line.startswith('ANTHROPIC_API_KEY='):
            return line.split('=', 1)[1].strip()
    raise RuntimeError('ANTHROPIC_API_KEY missing')


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def parse_md(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$', text)
    if not match:
        raise ValueError('frontmatter parse failed')
    fm: dict[str, str] = {}
    for line in match.group(1).splitlines():
        m = re.match(r'^(\w+):\s*"?(.+?)"?\s*$', line)
        if m:
            fm[m.group(1)] = m.group(2).strip('"')
    return fm, match.group(2).strip()


def claude_translate(api_key: str, fm: dict[str, str], body: str, retries: int = 3) -> str:
    prompt = f"""You are a professional translator for a technology news website.
Translate the following Turkish article into natural, fluent English news style.
Translate by meaning, not word-for-word.

Return ONLY this exact format:
TITLE: [one line]
SUMMARY: [one line, max 150 chars]
CATEGORY: [AI, Technology, or Security]
BODY:
[translated markdown body only]

Category mapping:
- Yapay Zeka -> AI
- Teknoloji -> Technology
- Güvenlik -> Security

Turkish title: {fm.get('title', '')}
Turkish summary: {fm.get('description', '')}
Turkish category: {fm.get('kategori', 'Teknoloji')}
Turkish body:
{body}
"""
    payload = {
        'model': 'claude-haiku-4-5-20251001',
        'max_tokens': 4096,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=json.dumps(payload).encode(),
        headers={
            'content-type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
        },
        method='POST',
    )
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.load(resp)
            return data['content'][0]['text']
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 529, 503):
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise last_err or RuntimeError('Claude request failed')


def parse_en(raw: str) -> dict[str, str]:
    title = re.search(r'^TITLE:\s*(.+)$', raw, re.M)
    summary = re.search(r'^SUMMARY:\s*(.+)$', raw, re.M)
    category = re.search(r'^CATEGORY:\s*(.+)$', raw, re.M)
    body = re.search(r'^BODY:\s*\n([\s\S]*)$', raw, re.M)
    return {
        'title': title.group(1).strip() if title else '',
        'summary': summary.group(1).strip() if summary else '',
        'category': category.group(1).strip() if category else 'Technology',
        'body': body.group(1).strip() if body else '',
    }


def build_en_md(fm: dict[str, str], en: dict[str, str]) -> str:
    cat = CAT_MAP.get(en['category'], CAT_MAP.get(fm.get('kategori', 'Teknoloji'), 'Technology'))
    esc = lambda s: (s or '').replace('"', "'")
    return f"""---
title: "{esc(en['title'])}"
pubDate: {fm.get('pubDate')}
kategori: "{cat}"
description: "{esc(en['summary'][:150])}"
kaynak: "{esc(fm.get('kaynak', ''))}"
coverImage: "{esc(fm.get('coverImage', ''))}"
gorselFotografci: "{esc(fm.get('gorselFotografci', ''))}"
gorselFotografciLink: "{esc(fm.get('gorselFotografciLink', ''))}"
---
{en['body']}
"""


def main() -> int:
    import argparse
    import fnmatch
    parser = argparse.ArgumentParser(description='Translate TR posts missing EN counterparts')
    parser.add_argument('--only', help="fnmatch filter on TR filenames, e.g. '*-20260820-12000*.md'")
    parser.add_argument('--force', action='store_true', help='Translate even if EN already exists')
    args = parser.parse_args()

    EN_DIR.mkdir(parents=True, exist_ok=True)
    api_key = load_api_key()
    pending = sorted(
        f for f in os.listdir(TR_DIR)
        if f.endswith('.md')
        and (args.force or not (EN_DIR / f).exists())
        and (not args.only or fnmatch.fnmatch(f, args.only))
    )
    log(f'Starting batch: {len(pending)} posts pending' + (f' (only={args.only!r})' if args.only else ''))
    ok, fail = 0, 0
    for i, fname in enumerate(pending, 1):
        if i > 1:
            time.sleep(1.5)
        try:
            fm, body = parse_md((TR_DIR / fname).read_text(encoding='utf-8'))
            raw = claude_translate(api_key, fm, body)
            en = parse_en(raw)
            if not en['title'] or not en['body']:
                raise ValueError('incomplete Claude output')
            (EN_DIR / fname).write_text(build_en_md(fm, en), encoding='utf-8')
            ok += 1
            log(f'OK [{i}/{len(pending)}] {fname} -> {en["title"][:70]}')
        except Exception as e:
            fail += 1
            log(f'FAIL [{i}/{len(pending)}] {fname}: {e}')
    log(f'Done. success={ok} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
