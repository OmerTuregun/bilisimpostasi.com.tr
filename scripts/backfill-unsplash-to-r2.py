#!/usr/bin/env python3
"""Backfill Unsplash hotlink covers → R2 (dedupe by CDN photo key).

Rate-limit style mirrors asama56: CALL_SLEEP + batch pauses, 403/429 retries.
Updates all TR+EN files that share the same images.unsplash.com photo.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
ENV_PATH = ROOT / 'n8n/.env'
STATE_PATH = ROOT / 'n8n/backups/unsplash-r2-backfill-state.json'
REPORT_PATH = ROOT / 'n8n/backups/unsplash-r2-backfill-report.json'

CALL_SLEEP = 3.0
BATCH_SIZE = 8
BATCH_SLEEP = 20.0
MAX_RETRIES = 6


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


def cdn_photo_key(url: str) -> str | None:
    if not url or 'images.unsplash.com' not in url:
        return None
    m = re.search(r'images\.unsplash\.com/(photo-[0-9]+-[a-zA-Z0-9_-]+)', url)
    return m.group(1) if m else None


def parse_simple_fm(text: str) -> dict[str, str]:
    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---', text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'^(\w+):\s*"(.*)"\s*$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2)
            continue
        mm = re.match(r'^(\w+):\s*(.+)\s*$', line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip().strip('"')
    return fm


def replace_cover(path: Path, new_url: str) -> bool:
    text = path.read_text(encoding='utf-8')
    if 'coverImage:' not in text:
        return False
    new_text, n = re.subn(
        r'^(coverImage:\s*)".*"\s*$',
        rf'\1"{new_url}"',
        text,
        count=1,
        flags=re.M,
    )
    if n:
        path.write_text(new_text, encoding='utf-8')
        return True
    return False


def api_get(url: str, access_key: str) -> dict | list:
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'Authorization': f'Client-ID {access_key}',
                    'Accept-Version': 'v1',
                    'User-Agent': 'bilisimpostasi-r2-backfill/1.0',
                },
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'api_get failed: {url} err={last_err}')


def trigger_download(access_key: str, download_location: str) -> str:
    if not download_location:
        return ''
    sep = '&' if '?' in download_location else '?'
    url = f'{download_location}{sep}client_id={urllib.parse.quote(access_key)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-r2-backfill/1.0'})
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
                return data.get('url') or ''
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                time.sleep(5 * (attempt + 1))
                continue
            raise
    return ''


def download_bytes(url: str) -> bytes:
    if 'images.unsplash.com' in url and 'w=1200' not in url:
        url = url + ('&' if '?' in url else '?') + 'w=1200&q=80&fm=jpg&fit=max'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-r2-backfill/1.0'})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def upload_r2(env: dict[str, str], key: str, data: bytes) -> str:
    import boto3
    from botocore.config import Config

    account = env['R2_ACCOUNT_ID']
    client = boto3.client(
        's3',
        endpoint_url=f'https://{account}.r2.cloudflarestorage.com',
        aws_access_key_id=env['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=env['R2_SECRET_ACCESS_KEY'],
        region_name='auto',
        config=Config(signature_version='s3v4'),
    )
    client.put_object(
        Bucket=env['R2_BUCKET_NAME'],
        Key=key,
        Body=data,
        ContentType='image/jpeg',
    )
    return f"{env['R2_PUBLIC_URL_BASE'].rstrip('/')}/{key}"


def username_from_link(link: str) -> str:
    m = re.search(r'unsplash\.com/@([^?/\s]+)', link or '')
    return m.group(1) if m else ''


def resolve_photo(access_key: str, cdn_key: str, username: str, query: str) -> dict | None:
    """Find Unsplash API photo object matching CDN key."""
    # 1) photographer's recent photos (paginate)
    if username:
        for page in range(1, 6):
            qs = urllib.parse.urlencode({'per_page': 30, 'page': page, 'order_by': 'latest'})
            data = api_get(f'https://api.unsplash.com/users/{urllib.parse.quote(username)}/photos?{qs}', access_key)
            time.sleep(CALL_SLEEP)
            photos = data if isinstance(data, list) else []
            if not photos:
                break
            for p in photos:
                urls = p.get('urls') or {}
                blob = ' '.join(str(v) for v in urls.values())
                if cdn_key in blob:
                    return p
    # 2) search by query
    if query:
        qs = urllib.parse.urlencode({'query': query, 'per_page': 30})
        data = api_get(f'https://api.unsplash.com/search/photos?{qs}', access_key)
        time.sleep(CALL_SLEEP)
        for p in (data.get('results') if isinstance(data, dict) else []) or []:
            urls = p.get('urls') or {}
            blob = ' '.join(str(v) for v in urls.values())
            if cdn_key in blob:
                return p
    return None


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {'done_cdn_keys': [], 'errors': [], 'updated_files': 0, 'uploaded': 0}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def collect_groups() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for loc, d in [('tr', TR_DIR), ('en', EN_DIR)]:
        for path in d.glob('*.md'):
            fm = parse_simple_fm(path.read_text(encoding='utf-8'))
            cover = fm.get('coverImage') or ''
            key = cdn_photo_key(cover)
            if not key:
                continue
            groups[key].append({
                'path': path,
                'loc': loc,
                'cover': cover,
                'title': fm.get('title', ''),
                'photog_link': fm.get('gorselFotografciLink', ''),
                'query': fm.get('gorselQuery', ''),
                'slug': path.stem,
            })
    return groups


def main() -> None:
    env = load_env()
    access = env['UNSPLASH_ACCESS_KEY']
    state = load_state()
    done = set(state.get('done_cdn_keys') or [])
    groups = collect_groups()
    keys = sorted(groups.keys(), key=lambda k: -len(groups[k]))
    pending = [k for k in keys if k not in done]
    print(f'unique unsplash photos={len(keys)} pending={len(pending)} already_done={len(done)}')

    batch_i = 0
    for i, cdn_key in enumerate(pending, 1):
        refs = groups[cdn_key]
        sample = refs[0]
        username = username_from_link(sample['photog_link'])
        # prefer a ref that has username / query
        for r in refs:
            if username_from_link(r['photog_link']):
                username = username_from_link(r['photog_link'])
                sample = r
                break
        query = sample.get('query') or ''
        print(f'[{i}/{len(pending)}] {cdn_key} refs={len(refs)} user=@{username or "-"}')

        try:
            photo = resolve_photo(access, cdn_key, username, query)
            download_url = sample['cover']
            if photo:
                dl_loc = (photo.get('links') or {}).get('download_location') or ''
                triggered = trigger_download(access, dl_loc) if dl_loc else ''
                time.sleep(CALL_SLEEP)
                if triggered:
                    download_url = triggered
                print(f'  resolved api_id={photo.get("id")} download_trigger={"yes" if triggered else "no"}')
            else:
                print('  WARN: could not resolve API photo; downloading CDN URL directly')
                state.setdefault('errors', []).append({
                    'cdn_key': cdn_key,
                    'error': 'unresolved-api-id',
                    'refs': len(refs),
                })

            data = download_bytes(download_url)
            r2_key = f'covers/{cdn_key}.jpg'
            public = upload_r2(env, r2_key, data)
            updated = 0
            for r in refs:
                if replace_cover(r['path'], public):
                    updated += 1
            state['uploaded'] = int(state.get('uploaded') or 0) + 1
            state['updated_files'] = int(state.get('updated_files') or 0) + updated
            done.add(cdn_key)
            state['done_cdn_keys'] = sorted(done)
            save_state(state)
            print(f'  OK r2={public} files={updated}')
        except Exception as e:
            print(f'  FAIL {e}')
            state.setdefault('errors', []).append({
                'cdn_key': cdn_key,
                'error': str(e),
                'at': datetime.now(timezone.utc).isoformat(),
            })
            save_state(state)

        batch_i += 1
        time.sleep(CALL_SLEEP)
        if batch_i >= BATCH_SIZE:
            print(f'  batch pause {BATCH_SLEEP}s…')
            time.sleep(BATCH_SLEEP)
            batch_i = 0

    # final counts
    left = sum(1 for p in list(TR_DIR.glob('*.md')) + list(EN_DIR.glob('*.md'))
               if 'images.unsplash.com' in p.read_text(encoding='utf-8', errors='ignore'))
    report = {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'unique_uploaded': state.get('uploaded'),
        'files_updated': state.get('updated_files'),
        'done_cdn_keys': len(done),
        'remaining_unsplash_files': left,
        'errors': state.get('errors') or [],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
