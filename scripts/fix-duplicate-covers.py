#!/usr/bin/env python3
"""Fix duplicate cover images on already-published posts (asama46).

Keeps oldest pubDate owner per duplicate group; refetches Unsplash covers
for newer siblings using keyword logic + 7-day used_cover_photos cooldown.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
ENV_PATH = ROOT / 'n8n/.env'
REPORT = ROOT / 'n8n/backups/cover-dedupe-fix-20260821-report.json'
BEFORE_SHOT = ROOT / 'n8n/backups/homepage-before-cover-dedupe.png'
AFTER_SHOT = ROOT / 'n8n/backups/homepage-after-cover-dedupe.png'

METAPHOR = {
    'soguyor', 'soğuyor', 'isiniyor', 'ısınıyor', 'patliyor', 'patlıyor', 'patlama',
    'cokuyor', 'çöküyor', 'dusuyor', 'düşüyor', 'yukseliyor', 'yükseliyor',
    'artis', 'artış', 'dusus', 'düşüş', 'patladi', 'patladı', 'sogudu', 'soğudu',
    'cooling', 'heating', 'booming', 'crashing', 'soaring', 'plunging',
}
STOP = {
    've', 'bu', 'de', 'da', 'ile', 'icin', 'için', 'bir', 'her', 'yeni', 'son',
    'gibi', 'daha', 'cok', 'çok', 'olan', 'olarak', 'uzerine', 'üzerine',
    'the', 'a', 'an', 'of', 'for', 'to', 'in', 'on', 'with',
}
CAT_MAP = {
    'Yapay Zeka': 'artificial intelligence technology',
    'Teknoloji': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
}
TOPIC_PHRASES = [
    (re.compile(r'imessage|mesajlasma|mesajlaşma|messages', re.I), 'smartphone messaging app'),
    (re.compile(r'vision|goruntu|görüntü|image analysis', re.I), 'computer vision AI'),
    (re.compile(r'patreon|algoritma|algorithm|creator', re.I), 'creator platform social media'),
    (re.compile(r'yapay\s+zeka', re.I), 'artificial intelligence'),
    (re.compile(r'\bai\b', re.I), 'artificial intelligence'),
    (re.compile(r'openai|chatgpt', re.I), 'openai chatgpt artificial intelligence'),
    (re.compile(r'deepseek', re.I), 'artificial intelligence neural network'),
    (re.compile(r'kodlama|yazilim|yazılım|codex', re.I), 'software coding'),
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


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


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$', text)
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


def cdn_photo_key(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r'images\.unsplash\.com/(photo-[0-9]+-[a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'images\.unsplash\.com/([^?]+)', url)
    return m.group(1) if m else None


def psql(sql: str) -> str:
    return subprocess.check_output(
        ['docker', 'exec', '-i', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c', sql],
        text=True,
    ).strip()


def load_cooldown_ids() -> set[str]:
    rows = psql(
        "SELECT unsplash_photo_id FROM used_cover_photos "
        "WHERE used_at >= now() - interval '7 days'"
    )
    return {l.strip() for l in rows.splitlines() if l.strip()} if rows else set()


def record_cover(photo_id: str, url: str, slug: str) -> None:
    pid = photo_id.replace("'", "''")
    u = url.replace("'", "''")
    s = slug.replace("'", "''")
    psql(
        "INSERT INTO used_cover_photos (unsplash_photo_id, photo_url, post_slug) "
        f"VALUES ('{pid}', '{u}', '{s}');"
    )


def unsplash_search(access_key: str, query: str, per_page: int = 20) -> list[dict]:
    qs = urllib.parse.urlencode({'query': query, 'per_page': per_page, 'orientation': 'landscape'})
    req = urllib.request.Request(
        f'https://api.unsplash.com/search/photos?{qs}',
        headers={
            'Authorization': f'Client-ID {access_key}',
            'Accept-Version': 'v1',
            'User-Agent': 'bilisimpostasi-cover-dedupe/1.0',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get('results') or []


def trigger_download(access_key: str, download_location: str) -> str:
    if not download_location:
        return ''
    sep = '&' if '?' in download_location else '?'
    url = f'{download_location}{sep}client_id={urllib.parse.quote(access_key)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-cover-dedupe/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        return data.get('url') or ''


def download_bytes(url: str) -> bytes:
    # Prefer ~1200px jpeg
    if 'images.unsplash.com' in url and 'w=1200' not in url:
        url = url + ('&' if '?' in url else '?') + 'w=1200&q=80&fm=jpg&fit=max'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-cover-dedupe/1.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def upload_r2(env: dict[str, str], key: str, data: bytes) -> str:
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
        ContentType='image/jpeg',
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


def find_en_path(tr_slug: str) -> Path | None:
    # EN files use same slug stem
    p = EN_DIR / f'{tr_slug}.md'
    if p.exists():
        return p
    # fallback: match by timestamp suffix
    m = re.search(r'(20\d{6}-\d{6})$', tr_slug)
    if not m:
        return None
    hits = list(EN_DIR.glob(f'*-{m.group(1)}.md'))
    return hits[0] if len(hits) == 1 else None


def collect_posts() -> list[dict]:
    out = []
    for p in TR_DIR.glob('*.md'):
        fm, _ = parse_frontmatter(p.read_text(encoding='utf-8'))
        cover = fm.get('coverImage') or ''
        out.append({
            'path': p,
            'slug': p.stem,
            'title': fm.get('title', ''),
            'pubDate': fm.get('pubDate', ''),
            'kategori': fm.get('kategori', ''),
            'cover': cover,
            'cdn_key': cdn_photo_key(cover),
            'photog': fm.get('gorselFotografci', ''),
            'query': fm.get('gorselQuery', ''),
        })
    return out


def find_dup_groups(posts: list[dict]) -> list[list[dict]]:
    # Prefer CDN photo key; also content-hash posts with covers for safety
    by_key: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        if post['cdn_key']:
            by_key[post['cdn_key']].append(post)

    # content hash for any remaining same-bytes under different URLs
    hash_groups: dict[str, list[dict]] = defaultdict(list)
    for post in posts:
        if not post['cover'] or post['cdn_key']:
            # still hash cdn ones for confirmation — skip network if already grouped
            continue
        try:
            data = download_bytes(post['cover'])
            h = hashlib.sha256(data).hexdigest()[:16]
            hash_groups[h].append(post)
        except Exception:
            pass

    groups = [v for v in by_key.values() if len(v) >= 2]
    # merge hash groups not already covered
    covered = {p['slug'] for g in groups for p in g}
    for v in hash_groups.values():
        if len(v) >= 2 and not all(p['slug'] in covered for p in v):
            groups.append(v)
    return groups


def pick_photo(
    results: list[dict],
    blocked_api: set[str],
    blocked_cdn: set[str],
) -> tuple[dict | None, int, bool]:
    for rank, cand in enumerate(results):
        api_id = str(cand.get('id') or '')
        regular = ((cand.get('urls') or {}).get('regular') or '')
        cdn = cdn_photo_key(regular) or ''
        if api_id in blocked_api:
            continue
        if cdn and cdn in blocked_cdn:
            continue
        return cand, rank, False
    # pool exhausted — oldest not applicable without used_at map; take first not in batch
    for rank, cand in enumerate(results):
        api_id = str(cand.get('id') or '')
        if api_id and api_id not in blocked_api:
            # allow cdn collision only if forced
            return cand, rank, True
    return (results[0] if results else None), 0, True


def update_post_cover(path: Path, public_url: str, photographer: str, photog_link: str, query: str) -> None:
    text = path.read_text(encoding='utf-8')
    fm, body = parse_frontmatter(text)
    fm['coverImage'] = public_url
    fm['gorselFotografci'] = photographer
    fm['gorselFotografciLink'] = photog_link
    fm['gorselQuery'] = query
    path.write_text(write_frontmatter(fm, body), encoding='utf-8')


def screenshot_homepage(out: Path) -> None:
    # Prefer playwright/chromium if available; else skip
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print('screenshot skip (no playwright):', e)
        return
    url = 'https://bilisimpostasi.com.tr/'
    # local deploy may be on /var/www/blog — try public first
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        try:
            page.goto(url, wait_until='networkidle', timeout=60000)
        except Exception:
            page.goto('http://127.0.0.1:9080/', wait_until='networkidle', timeout=60000)
        page.screenshot(path=str(out), full_page=False)
        browser.close()
    print('screenshot', out)


def main() -> None:
    env = load_env()
    access = env.get('UNSPLASH_ACCESS_KEY')
    if not access:
        raise SystemExit('UNSPLASH_ACCESS_KEY missing')

    posts = collect_posts()
    groups = find_dup_groups(posts)
    print(f'Found {len(groups)} duplicate cover groups')

    # Seed blocked sets from all existing covers + DB cooldown
    blocked_api = load_cooldown_ids()
    blocked_cdn: set[str] = set()
    for post in posts:
        if post['cdn_key']:
            blocked_cdn.add(post['cdn_key'])
        # also seed DB with CDN keys so future workflow avoids them
        if post['cdn_key'] and post['cover']:
            # only insert if not present recently
            exists = psql(
                "SELECT 1 FROM used_cover_photos WHERE unsplash_photo_id="
                f"'{post['cdn_key'].replace(chr(39), chr(39)+chr(39))}' "
                "AND used_at >= now() - interval '7 days' LIMIT 1"
            )
            if not exists:
                record_cover(post['cdn_key'], post['cover'], post['slug'])
                print(f"seeded cooldown {post['cdn_key']} <- {post['slug'][:40]}")

    blocked_api |= load_cooldown_ids()

    # Before shot (current live site still old covers until deploy)
    try:
        screenshot_homepage(BEFORE_SHOT)
    except Exception as e:
        print('before screenshot failed:', e)

    changes = []
    for gi, group in enumerate(groups, 1):
        ordered = sorted(group, key=lambda x: x['pubDate'])
        keeper = ordered[0]
        to_fix = ordered[1:]
        print(f'\n=== GROUP {gi} key={keeper.get("cdn_key")} keeper={keeper["slug"][:50]} keep_cover')
        print(f'    will fix {len(to_fix)} posts')

        for post in to_fix:
            query = build_query(post['title'], post['kategori'])
            # diversify queries slightly per post to avoid same top results
            print(f'\n--- fix {post["slug"][:55]}')
            print(f'    title={post["title"][:70]}')
            print(f'    query={query!r}')

            results = unsplash_search(access, query, 20)
            photo, rank, exhausted = pick_photo(results, blocked_api, blocked_cdn)
            if not photo:
                raise RuntimeError(f'no photo for {post["slug"]}')
            if exhausted:
                print('    WARN pool exhausted, forced pick')

            api_id = str(photo.get('id') or '')
            photographer = (photo.get('user') or {}).get('name') or ''
            user_html = ((photo.get('user') or {}).get('links') or {}).get('html') or ''
            dl_loc = ((photo.get('links') or {}).get('download_location') or '')
            regular = ((photo.get('urls') or {}).get('regular') or '')
            cdn = cdn_photo_key(regular) or ''

            final_url = trigger_download(access, dl_loc) or regular
            img = download_bytes(final_url)
            ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            obj_key = f'{slugify_key(post["title"])}-cover-{ts}.jpg'
            public_url = upload_r2(env, obj_key, img)
            photog_link = (
                f'{user_html}?utm_source=bilisimpostasi&utm_medium=referral' if user_html else ''
            )

            update_post_cover(post['path'], public_url, photographer, photog_link, query)
            en_path = find_en_path(post['slug'])
            en_updated = False
            if en_path:
                update_post_cover(en_path, public_url, photographer, photog_link, query)
                en_updated = True

            if api_id:
                blocked_api.add(api_id)
                record_cover(api_id, public_url, post['slug'])
            if cdn:
                blocked_cdn.add(cdn)
                if cdn != api_id:
                    record_cover(cdn, public_url, post['slug'])

            row = {
                'group': gi,
                'slug': post['slug'],
                'title': post['title'],
                'kept_owner_slug': keeper['slug'],
                'old_cover': post['cover'],
                'new_cover': public_url,
                'query': query,
                'unsplash_id': api_id,
                'cdn_key': cdn,
                'rank': rank,
                'photographer': photographer,
                'en_updated': en_updated,
                'pool_exhausted': exhausted,
            }
            changes.append(row)
            print(f'    OK rank={rank} id={api_id} -> {public_url}')
            time.sleep(1.0)

    REPORT.write_text(json.dumps({
        'groups': len(groups),
        'posts_changed': len(changes),
        'changes': changes,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nReport {REPORT} changed={len(changes)}')

    # Build + deploy
    print('\nBuilding and deploying...')
    subprocess.run(['bash', str(ROOT / 'scripts/build-and-deploy-site.sh')], check=True)

    # Verify URLs and no slug change
    for ch in changes:
        slug = ch['slug']
        url = f'https://bilisimpostasi.com.tr/posts/{slug}/'
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'dedupe-check'})
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f'HTTP {r.status} {url}')
        except Exception as e:
            # some servers block HEAD
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'dedupe-check'})
                with urllib.request.urlopen(req, timeout=20) as r:
                    print(f'HTTP {r.status} GET {url}')
            except Exception as e2:
                print(f'URL check fail {url}: {e2}')

    # Re-scan duplicates on TR source
    posts2 = collect_posts()
    groups2 = find_dup_groups(posts2)
    print(f'After fix duplicate groups in source: {len(groups2)}')

    try:
        screenshot_homepage(AFTER_SHOT)
    except Exception as e:
        print('after screenshot failed:', e)

    print('DONE')


if __name__ == '__main__':
    main()
