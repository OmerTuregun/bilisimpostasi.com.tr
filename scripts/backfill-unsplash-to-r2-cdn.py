#!/usr/bin/env python3
"""Finish Unsplash→R2 backfill WITHOUT Unsplash API (CDN download only).

Avoids rate-limiting the live publish workflow. Still updates TR+EN covers.
Attribution fields are left as-is. Download-trigger is skipped (API banned/limited).
"""
from __future__ import annotations

import json
import re
import time
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

CALL_SLEEP = 1.2
BATCH_SIZE = 12
BATCH_SLEEP = 8.0


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


def parse_cover(text: str) -> str:
    m = re.search(r'^coverImage:\s*"(.*?)"\s*$', text, re.M)
    return m.group(1) if m else ''


def replace_cover(path: Path, new_url: str) -> bool:
    text = path.read_text(encoding='utf-8')
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


def download_bytes(url: str) -> bytes:
    if 'images.unsplash.com' in url and 'w=1200' not in url:
        url = url + ('&' if '?' in url else '?') + 'w=1200&q=80&fm=jpg&fit=max'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-r2-cdn-backfill/1.0'})
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


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    return {'done_cdn_keys': [], 'errors': [], 'updated_files': 0, 'uploaded': 0}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def collect_groups() -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in (TR_DIR, EN_DIR):
        for path in d.glob('*.md'):
            text = path.read_text(encoding='utf-8')
            cover = parse_cover(text)
            key = cdn_photo_key(cover)
            if not key:
                continue
            groups[key].append({'path': path, 'cover': cover})
    return groups


def main() -> None:
    env = load_env()
    state = load_state()
    done = set(state.get('done_cdn_keys') or [])
    groups = collect_groups()
    pending = [k for k in sorted(groups, key=lambda k: -len(groups[k])) if k not in done]
    print(f'cdn-only backfill pending={len(pending)} already_done={len(done)}')

    batch_i = 0
    for i, cdn_key in enumerate(pending, 1):
        refs = groups[cdn_key]
        cover = refs[0]['cover']
        print(f'[{i}/{len(pending)}] {cdn_key} refs={len(refs)}')
        try:
            data = download_bytes(cover)
            public = upload_r2(env, f'covers/{cdn_key}.jpg', data)
            updated = sum(1 for r in refs if replace_cover(r['path'], public))
            state['uploaded'] = int(state.get('uploaded') or 0) + 1
            state['updated_files'] = int(state.get('updated_files') or 0) + updated
            done.add(cdn_key)
            state['done_cdn_keys'] = sorted(done)
            save_state(state)
            print(f'  OK {public} files={updated}')
        except Exception as e:
            print(f'  FAIL {e}')
            state.setdefault('errors', []).append({
                'cdn_key': cdn_key, 'error': str(e),
                'at': datetime.now(timezone.utc).isoformat(),
            })
            save_state(state)
        batch_i += 1
        time.sleep(CALL_SLEEP)
        if batch_i >= BATCH_SIZE:
            print(f'  batch pause {BATCH_SLEEP}s')
            time.sleep(BATCH_SLEEP)
            batch_i = 0

    left = 0
    for d in (TR_DIR, EN_DIR):
        for p in d.glob('*.md'):
            if 'images.unsplash.com' in p.read_text(encoding='utf-8', errors='ignore'):
                left += 1
    report = {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'cdn-only',
        'unique_uploaded': state.get('uploaded'),
        'files_updated': state.get('updated_files'),
        'done_cdn_keys': len(done),
        'remaining_unsplash_files': left,
        'errors_tail': (state.get('errors') or [])[-20:],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
