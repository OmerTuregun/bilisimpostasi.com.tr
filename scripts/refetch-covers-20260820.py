#!/usr/bin/env python3
"""Re-fetch Unsplash covers for recovered 20260820-12* TR posts using fixed keyword logic."""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
ENV_PATH = ROOT / 'n8n/.env'
REPORT = ROOT / 'n8n/backups/cover-refetch-20260820-report.json'

GLOB = '*-20260820-12*.md'

# --- fixed keyword builder (mirrors Anahtar Kelime Cikar / test-unsplash-keyword.py) ---
METAPHOR = {
    'soguyor', 'soğuyor', 'isiniyor', 'ısınıyor', 'patliyor', 'patlıyor', 'patlama',
    'cokuyor', 'çöküyor', 'dusuyor', 'düşüyor', 'yukseliyor', 'yükseliyor',
    'artis', 'artış', 'dusus', 'düşüş', 'patladi', 'patladı', 'sogudu', 'soğudu',
    'cooling', 'heating', 'booming', 'crashing', 'soaring', 'plunging',
}
STOP = {
    've', 'bu', 'de', 'da', 'ile', 'icin', 'için', 'bir', 'her', 'yeni', 'son',
    'gibi', 'daha', 'cok', 'çok', 'olan', 'olarak', 'uzerine', 'üzerine',
}
CAT_MAP = {
    'Yapay Zeka': 'artificial intelligence technology',
    'Teknoloji': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
}
TOPIC_PHRASES = [
    (re.compile(r'yapay\s+zeka', re.I), 'artificial intelligence'),
    (re.compile(r'\bai\b', re.I), 'artificial intelligence'),
    (re.compile(r'buyuk\s+dil\s+model|büyük\s+dil\s+model', re.I), 'large language model AI'),
    (re.compile(r'openai', re.I), 'openai artificial intelligence'),
    (re.compile(r'meta\b|llama', re.I), 'meta artificial intelligence'),
    (re.compile(r'drone|itfaiyeci|teslimat', re.I), 'delivery drone'),
    (re.compile(r'otonom|robotaksi|waymo', re.I), 'autonomous vehicle'),
    (re.compile(r'kodlama|yazilim|yazılım|codex', re.I), 'software coding'),
    (re.compile(r'ogrenci|öğrenci|egitim|eğitim|study', re.I), 'students learning technology'),
    (re.compile(r'yonetim|yönetim|ajan|agent', re.I), 'AI agent software office'),
]


def build_query(baslik: str, kategori: str = '') -> str:
    title = (baslik or '').strip()
    cat = (kategori or '').strip()
    for re_pat, q in TOPIC_PHRASES:
        if re_pat.search(title):
            return q
    if cat in CAT_MAP:
        return CAT_MAP[cat]
    words = title.split()
    cleaned = [re.sub(r'[^\wçğıöşüÇĞİÖŞÜ-]', '', w, flags=re.I) for w in words]
    cleaned = [w for w in cleaned if len(w) > 2 and w.lower() not in STOP and w.lower() not in METAPHOR]
    proper = [w for w in cleaned if w[:1].isupper()]
    if len(proper) >= 2:
        return ' '.join(proper[:2])
    if len(proper) == 1 and len(proper[0]) >= 4:
        return f'{proper[0]} {CAT_MAP.get(cat, "technology")}'.strip()
    if len(cleaned) >= 2:
        return ' '.join(cleaned[:2])
    return CAT_MAP.get(cat) or cat or 'technology'


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
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
    return fm, m.group(2)


def esc(s: str) -> str:
    return str(s or '').replace('"', "'")


def write_frontmatter(fm: dict[str, str], body: str) -> str:
    order = [
        'title', 'pubDate', 'kategori', 'description', 'kaynak',
        'coverImage', 'gorselFotografci', 'gorselFotografciLink', 'gorselQuery',
    ]
    lines = ['---']
    for k in order:
        if k not in fm:
            continue
        v = fm[k]
        if k == 'pubDate':
            lines.append(f'{k}: {v}')
        else:
            lines.append(f'{k}: "{esc(v)}"')
    for k, v in fm.items():
        if k in order:
            continue
        lines.append(f'{k}: "{esc(v)}"')
    lines.append('---')
    body = body if body.endswith('\n') else body + '\n'
    return '\n'.join(lines) + '\n' + body.lstrip('\n')


def unsplash_search(access_key: str, query: str) -> dict:
    qs = urllib.parse.urlencode({
        'query': query,
        'per_page': 1,
        'orientation': 'landscape',
    })
    req = urllib.request.Request(
        f'https://api.unsplash.com/search/photos?{qs}',
        headers={
            'Authorization': f'Client-ID {access_key}',
            'Accept-Version': 'v1',
            'User-Agent': 'bilisimpostasi-cover-refetch/1.0',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def trigger_download(access_key: str, download_location: str) -> str:
    """Hit Unsplash download endpoint (required by API guidelines); return final image URL."""
    if not download_location:
        return ''
    sep = '&' if '?' in download_location else '?'
    url = f'{download_location}{sep}client_id={urllib.parse.quote(access_key)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-cover-refetch/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        return data.get('url') or ''


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-cover-refetch/1.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def upload_r2(env: dict[str, str], key: str, data: bytes, content_type: str = 'image/jpeg') -> str:
    import boto3
    from botocore.config import Config

    account = env['R2_ACCOUNT_ID']
    endpoint = f'https://{account}.r2.cloudflarestorage.com'
    client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=env['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=env['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        config=Config(signature_version='s3v4'),
    )
    client.put_object(
        Bucket=env['R2_BUCKET_NAME'],
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{env['R2_PUBLIC_URL_BASE'].rstrip('/')}/{key}"


def slugify_key(title: str) -> str:
    tr = str.maketrans({
        'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
        'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'İ': 'i', 'Ö': 'o', 'Ç': 'c',
    })
    s = title.translate(tr).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:50]


def main() -> None:
    env = load_env()
    key = env.get('UNSPLASH_ACCESS_KEY')
    if not key:
        raise SystemExit('UNSPLASH_ACCESS_KEY missing')

    files = sorted(TR_DIR.glob(GLOB))
    if len(files) != 8:
        print(f'WARNING expected 8 files, found {len(files)}')

    rows = []
    for path in files:
        text = path.read_text(encoding='utf-8')
        fm, body = parse_frontmatter(text)
        title = fm.get('title', '')
        kategori = fm.get('kategori', 'Teknoloji')
        old_cover = fm.get('coverImage', '')
        old_query = fm.get('gorselQuery', '')
        # Old wrong query for the snow case was full title
        if not old_query and 'Soğuyor' in title:
            old_query = title

        new_query = build_query(title, kategori)
        print(f'\n=== {path.name}')
        print(f'title: {title}')
        print(f'old_query: {old_query or "(empty)"}')
        print(f'new_query: {new_query}')

        try:
            data = unsplash_search(key, new_query)
            results = data.get('results') or []
            if not results:
                raise RuntimeError(f'no Unsplash results for {new_query!r}')
            photo = results[0]
            photographer = (photo.get('user') or {}).get('name') or ''
            user_html = ((photo.get('user') or {}).get('links') or {}).get('html') or ''
            dl_loc = ((photo.get('links') or {}).get('download_location') or '')
            alt = photo.get('alt_description') or photo.get('description') or ''

            final_url = trigger_download(key, dl_loc)
            if not final_url:
                final_url = ((photo.get('urls') or {}).get('regular')
                             or (photo.get('urls') or {}).get('small') or '')
            img = download_bytes(final_url)

            ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            obj_key = f'{slugify_key(title)}-cover-{ts}.jpg'
            public_url = upload_r2(env, obj_key, img)

            fm['coverImage'] = public_url
            fm['gorselFotografci'] = photographer
            fm['gorselFotografciLink'] = (
                f'{user_html}?utm_source=bilisimpostasi&utm_medium=referral' if user_html else ''
            )
            fm['gorselQuery'] = new_query
            path.write_text(write_frontmatter(fm, body), encoding='utf-8')

            row = {
                'file': path.name,
                'title': title,
                'old_query': old_query or '(empty/full-title)',
                'new_query': new_query,
                'old_cover': old_cover or '(empty)',
                'new_cover': public_url,
                'photographer': photographer,
                'unsplash_alt': alt,
                'unsplash_id': photo.get('id'),
                'ok': True,
            }
            print(f'OK -> {public_url} ({photographer}) alt={alt[:80]!r}')
        except Exception as e:
            row = {
                'file': path.name,
                'title': title,
                'old_query': old_query or '(empty)',
                'new_query': new_query,
                'old_cover': old_cover or '(empty)',
                'new_cover': None,
                'error': str(e),
                'ok': False,
            }
            print(f'FAIL: {e}')
        rows.append(row)
        time.sleep(1.2)  # be kind to Unsplash rate limits

    REPORT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(1 for r in rows if r.get('ok'))
    print(f'\nDone {ok}/{len(rows)} -> {REPORT}')
    if ok < len(rows):
        sys.exit(1)


if __name__ == '__main__':
    main()
