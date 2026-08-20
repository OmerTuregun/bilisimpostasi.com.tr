#!/usr/bin/env python3
"""Recover 10 posts from execution #537: TR + covers (R2) + EN + twitter + pending cleanup.

Does NOT call Claude for TR bodies. Calls Claude only for EN translation.
Does NOT send Telegram/email (use notify-exec537-recovery.py).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
SRC = ROOT / 'n8n/backups/exec537-posts.json'
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
QUEUE = ROOT / 'site/src/content/_queue/pending.jsonl'
ENV_PATH = ROOT / 'n8n/.env'
MANIFEST = ROOT / 'n8n/backups/exec537-recovery-manifest.json'
COVER_REPORT = ROOT / 'n8n/backups/exec537-cover-report.json'

IST = timezone(timedelta(hours=3))
# 15:00 TR cycle — avoid colliding with noon recovery (*-12000x.md)
PUB = datetime(2026, 8, 20, 15, 0, 0, tzinfo=IST)
MIN_BODY = 200
CYCLE_MINUTES = 180

TR_MAP = str.maketrans({
    'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
    'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'İ': 'i', 'Ö': 'o', 'Ç': 'c',
})

METAPHOR = {
    'soguyor', 'soğuyor', 'isiniyor', 'ısınıyor', 'patliyor', 'patlıyor',
    'cokuyor', 'çöküyor', 'dusuyor', 'düşüyor', 'yukseliyor', 'yükseliyor',
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
    (re.compile(r'prime\s*air|drone|teslimat', re.I), 'amazon delivery drone sky'),
    (re.compile(r'terrapower|n[uü]kleer|reakt[oö]r|veri\s+merkezi', re.I), 'nuclear power plant data center'),
    (re.compile(r'alexa|fire\s*tv', re.I), 'smart tv living room amazon'),
    (re.compile(r'kontrail|contrail|istiklal|blue\s*skies', re.I), 'airplane contrail sky'),
    (re.compile(r'[oö][gğ]renci|ai\s+pro|universite|üniversite', re.I), 'university students laptop studying'),
    (re.compile(r'rillet|unicorn', re.I), 'startup office finance growth'),
    (re.compile(r'binance|ticaret\s+ajan', re.I), 'cryptocurrency trading chart'),
    (re.compile(r'cognition|spacex|kod\s+yazma', re.I), 'software developer coding screen'),
    (re.compile(r'pixel\s*11|telefon', re.I), 'smartphone android mobile phone'),
    (re.compile(r'ajan\s+g[uü]venli[gğ]i|gizli\s+anla[sş]ma|pazar', re.I), 'cybersecurity lock digital'),
    (re.compile(r'yapay\s+zeka', re.I), 'artificial intelligence'),
    (re.compile(r'\bai\b', re.I), 'artificial intelligence'),
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def slugify(s: str, max_len: int = 80) -> str:
    s = s.translate(TR_MAP).lower()
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:max_len].rstrip('-')


def esc(s: str) -> str:
    return str(s or '').replace('"', "'")


def first_sentence(summary: str) -> str:
    summary = (summary or '').strip()
    parts = re.split(r'(?<=[.!?…])\s+', summary)
    return (parts[0] if parts else summary)[:280]


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
    return CAT_MAP.get(cat) or cat or 'technology'


def optimize_jpeg(data: bytes, max_side: int = 1200, quality: int = 80) -> bytes:
    try:
        from PIL import Image
    except ImportError:
        return data
    im = Image.open(BytesIO(data))
    im = im.convert('RGB')
    w, h = im.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    out = BytesIO()
    im.save(out, format='JPEG', quality=quality, optimize=True)
    return out.getvalue()


def unsplash_search(access_key: str, query: str, page: int = 1) -> dict:
    qs = urllib.parse.urlencode({
        'query': query,
        'per_page': 5,
        'orientation': 'landscape',
        'page': page,
    })
    req = urllib.request.Request(
        f'https://api.unsplash.com/search/photos?{qs}',
        headers={
            'Authorization': f'Client-ID {access_key}',
            'Accept-Version': 'v1',
            'User-Agent': 'bilisimpostasi-exec537-recovery/1.0',
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def trigger_download(access_key: str, download_location: str) -> str:
    if not download_location:
        return ''
    sep = '&' if '?' in download_location else '?'
    url = f'{download_location}{sep}client_id={urllib.parse.quote(access_key)}'
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-exec537-recovery/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        return data.get('url') or ''


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': 'bilisimpostasi-exec537-recovery/1.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
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


def fetch_cover(env: dict, title: str, kategori: str, used_ids: set[str], index: int) -> dict:
    key = env['UNSPLASH_ACCESS_KEY']
    query = build_query(title, kategori)
    photo = None
    for page in (1, 2, 3):
        data = unsplash_search(key, query, page=page)
        for cand in data.get('results') or []:
            pid = cand.get('id') or ''
            if pid and pid not in used_ids:
                photo = cand
                break
        if photo:
            break
    if not photo:
        raise RuntimeError(f'no unique Unsplash result for {query!r}')

    used_ids.add(photo.get('id') or '')
    photographer = (photo.get('user') or {}).get('name') or ''
    user_html = ((photo.get('user') or {}).get('links') or {}).get('html') or ''
    dl_loc = ((photo.get('links') or {}).get('download_location') or '')
    final_url = trigger_download(key, dl_loc)
    if not final_url:
        final_url = ((photo.get('urls') or {}).get('regular')
                     or (photo.get('urls') or {}).get('small') or '')
    img = optimize_jpeg(download_bytes(final_url))
    ts = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    obj_key = f'{slugify(title, 50)}-cover-opt-{ts}.jpg'
    public_url = upload_r2(env, obj_key, img)
    return {
        'coverImage': public_url,
        'gorselFotografci': photographer,
        'gorselFotografciLink': (
            f'{user_html}?utm_source=bilisimpostasi&utm_medium=referral' if user_html else ''
        ),
        'gorselQuery': query,
        'unsplash_id': photo.get('id'),
        'unsplash_alt': photo.get('alt_description') or photo.get('description') or '',
        'bytes': len(img),
    }


def write_tr_md(path: Path, fm: dict, body: str) -> None:
    lines = [
        '---',
        f'title: "{esc(fm["title"])}"',
        f'pubDate: {fm["pubDate"]}',
        f'kategori: "{esc(fm["kategori"])}"',
        f'description: "{esc(fm["description"][:150])}"',
        f'kaynak: "{esc(fm["kaynak"])}"',
        f'coverImage: "{esc(fm["coverImage"])}"',
        f'gorselFotografci: "{esc(fm.get("gorselFotografci", ""))}"',
        f'gorselFotografciLink: "{esc(fm.get("gorselFotografciLink", ""))}"',
        f'gorselQuery: "{esc(fm.get("gorselQuery", ""))}"',
        '---',
        body.strip(),
        '',
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')


def claude_translate(api_key: str, fm: dict, body: str) -> str:
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
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = json.load(resp)
            return data['content'][0]['text']
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 503) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except Exception:
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError('Claude EN failed')


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


EN_CAT = {
    'AI': 'AI', 'Technology': 'Technology', 'Security': 'Security',
    'Yapay Zeka': 'AI', 'Teknoloji': 'Technology', 'Güvenlik': 'Security',
}


def write_en_md(path: Path, tr_fm: dict, en: dict) -> None:
    cat = EN_CAT.get(en['category'], EN_CAT.get(tr_fm.get('kategori', ''), 'Technology'))
    lines = [
        '---',
        f'title: "{esc(en["title"])}"',
        f'pubDate: {tr_fm["pubDate"]}',
        f'kategori: "{cat}"',
        f'description: "{esc(en["summary"][:150])}"',
        f'kaynak: "{esc(tr_fm["kaynak"])}"',
        f'coverImage: "{esc(tr_fm["coverImage"])}"',
        f'gorselFotografci: "{esc(tr_fm.get("gorselFotografci", ""))}"',
        f'gorselFotografciLink: "{esc(tr_fm.get("gorselFotografciLink", ""))}"',
        '---',
        en['body'].strip(),
        '',
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')


def chown_posts() -> None:
    subprocess.run(
        ['chown', '-R', '1000:1000', str(TR_DIR), str(EN_DIR), str(QUEUE.parent)],
        check=False,
    )


def insert_twitter(rows: list[dict]) -> list[dict]:
    results = []
    for r in rows:
        sql = (
            "INSERT INTO twitter_queue "
            "(post_slug, post_title, post_summary, post_link, kategori, status, scheduled_at) "
            "VALUES ("
            f"$$${r['post_slug']}$$$, "
            f"$$${r['post_title']}$$$, "
            f"$$${r['post_summary']}$$$, "
            f"$$${r['post_link']}$$$, "
            f"$$${r['kategori']}$$$, "
            "'pending', "
            f"'$${r['scheduled_at']}$$'::timestamptz"
            ");"
        )
        # Use dollar quoting carefully — titles may contain $$. Escape by replacing.
        def dq(s: str) -> str:
            return (s or '').replace("'", "''")

        sql = (
            "INSERT INTO twitter_queue "
            "(post_slug, post_title, post_summary, post_link, kategori, status, scheduled_at) "
            "VALUES ("
            f"'{dq(r['post_slug'])}', "
            f"'{dq(r['post_title'])}', "
            f"'{dq(r['post_summary'])}', "
            f"'{dq(r['post_link'])}', "
            f"'{dq(r['kategori'])}', "
            "'pending', "
            f"'{dq(r['scheduled_at'])}'::timestamptz"
            ");"
        )
        cmd = [
            'docker', 'exec', '-i', 'agent-n8n-postgres',
            'psql', '-U', 'n8n', '-d', 'n8n', '-v', 'ON_ERROR_STOP=1', '-c', sql,
        ]
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
            results.append({'slug': r['post_slug'], 'ok': True, 'out': out.strip()[:80]})
        except subprocess.CalledProcessError as e:
            results.append({'slug': r['post_slug'], 'ok': False, 'out': (e.output or str(e))[:300]})
    return results


def strip_pending(links: set[str]) -> dict:
    used = set()
    for link in links:
        link = (link or '').strip()
        if not link:
            continue
        used.add(link)
        used.add(link.rstrip('/'))
        used.add(link.rstrip('/') + '/')
    backup = QUEUE.with_suffix('.jsonl.bak-exec537-recovery')
    raw = QUEUE.read_text(encoding='utf-8') if QUEUE.exists() else ''
    backup.write_text(raw, encoding='utf-8')
    kept, removed = [], 0
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
    chown_posts()
    return {'removed': removed, 'remaining': len(kept), 'backup': str(backup)}


def main() -> int:
    env = load_env()
    posts = json.loads(SRC.read_text(encoding='utf-8'))
    if len(posts) != 10:
        print(f'WARNING expected 10 posts, got {len(posts)}')

    TR_DIR.mkdir(parents=True, exist_ok=True)
    EN_DIR.mkdir(parents=True, exist_ok=True)
    chown_posts()

    used_photo_ids: set[str] = set()
    recovered: list[dict] = []
    cover_rows: list[dict] = []
    skipped: list[dict] = []

    print('=== TR write + covers ===')
    for i, p in enumerate(posts):
        baslik = (p.get('baslik') or '').strip()
        icerik = (p.get('icerik') or '').strip()
        if len(icerik) < MIN_BODY:
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': f'short body {len(icerik)}'})
            continue
        slug_part = slugify(baslik)
        if not slug_part:
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': 'empty slug'})
            continue
        ts = PUB + timedelta(seconds=i)
        dosya_adi = f'{slug_part}-{ts.strftime("%Y%m%d-%H%M%S")}'
        if re.match(r'^-\d{8}', dosya_adi) or dosya_adi.startswith('-'):
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': 'bad slug'})
            continue
        tr_path = TR_DIR / f'{dosya_adi}.md'
        if tr_path.exists():
            skipped.append({'index': i + 1, 'baslik': baslik, 'reason': f'exists {tr_path.name}'})
            continue

        kategori = (p.get('kategori') or 'Teknoloji').strip()
        ozet = (p.get('ozet') or '').strip()
        link = (p.get('link') or p.get('kaynak') or '').strip()

        try:
            cover = fetch_cover(env, baslik, kategori, used_photo_ids, i)
            print(f'COVER ok [{i+1}/10] {baslik[:50]} -> {cover["gorselQuery"]} id={cover["unsplash_id"]} {cover["bytes"]}B')
        except Exception as e:
            print(f'COVER fail [{i+1}/10] {baslik[:50]}: {e}')
            # fallback to unsplash URL from exec if present (not ideal but better than empty)
            cover = {
                'coverImage': (p.get('gorsel_url') or '').strip(),
                'gorselFotografci': p.get('gorsel_fotografci') or '',
                'gorselFotografciLink': p.get('gorsel_fotografci_link') or '',
                'gorselQuery': p.get('gorsel_query') or p.get('gorselQuery') or '',
                'unsplash_id': p.get('gorsel_unsplash_id'),
                'unsplash_alt': p.get('gorsel_unsplash_alt') or '',
                'bytes': 0,
                'fallback': True,
                'error': str(e),
            }

        fm = {
            'title': baslik,
            'pubDate': ts.isoformat(),
            'kategori': kategori,
            'description': ozet,
            'kaynak': link,
            'coverImage': cover['coverImage'],
            'gorselFotografci': cover.get('gorselFotografci', ''),
            'gorselFotografciLink': cover.get('gorselFotografciLink', ''),
            'gorselQuery': cover.get('gorselQuery', ''),
        }
        write_tr_md(tr_path, fm, icerik)
        cover_rows.append({'file': tr_path.name, 'title': baslik, **cover, 'ok': bool(cover.get('coverImage'))})
        recovered.append({
            'index': i + 1,
            'baslik': baslik,
            'dosya_adi': dosya_adi,
            'tr_path': str(tr_path),
            'kategori': kategori,
            'ozet': ozet,
            'link': link,
            'post_link': f'https://bilisimpostasi.com.tr/posts/{dosya_adi}/',
            'post_summary': first_sentence(ozet),
            'coverImage': cover['coverImage'],
            'gorselQuery': cover.get('gorselQuery'),
            'fm': fm,
            'body': icerik,
        })
        time.sleep(1.1)

    chown_posts()
    print(f'TR written: {len(recovered)} skipped={len(skipped)}')

    print('=== EN translate ===')
    api_key = env.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise SystemExit('ANTHROPIC_API_KEY missing')
    en_ok = 0
    for i, rec in enumerate(recovered):
        if i:
            time.sleep(1.5)
        raw = claude_translate(api_key, rec['fm'], rec['body'])
        en = parse_en(raw)
        if not en['title'] or not en['body']:
            print(f'EN FAIL {rec["dosya_adi"]}: incomplete')
            rec['en_ok'] = False
            continue
        en_path = EN_DIR / f'{rec["dosya_adi"]}.md'
        write_en_md(en_path, rec['fm'], en)
        rec['en_ok'] = True
        rec['en_title'] = en['title']
        rec['en_path'] = str(en_path)
        en_ok += 1
        print(f'EN ok [{i+1}/{len(recovered)}] {en["title"][:60]}')

    chown_posts()

    n = len(recovered)
    step = CYCLE_MINUTES / n if n else 0
    now = datetime.now(timezone.utc)
    tw_rows = []
    for i, rec in enumerate(recovered):
        sched = (now + timedelta(minutes=i * step)).isoformat()
        rec['scheduled_at'] = sched
        rec['schedule_step_min'] = step
        tw_rows.append({
            'post_slug': rec['dosya_adi'],
            'post_title': rec['baslik'],
            'post_summary': rec['post_summary'],
            'post_link': rec['post_link'],
            'kategori': rec['kategori'],
            'scheduled_at': sched,
        })

    print('=== Twitter queue ===')
    tw_results = insert_twitter(tw_rows)
    tw_ok = sum(1 for r in tw_results if r['ok'])
    print(f'twitter insert {tw_ok}/{len(tw_results)}')

    print('=== pending cleanup ===')
    pending_info = strip_pending({r['link'] for r in recovered})
    print(pending_info)

    # Drop heavy body from manifest
    manifest_posts = []
    for r in recovered:
        manifest_posts.append({k: v for k, v in r.items() if k not in ('body', 'fm')})

    MANIFEST.write_text(json.dumps({
        'execution': 537,
        'recovered': manifest_posts,
        'skipped': skipped,
        'covers': cover_rows,
        'twitter': tw_results,
        'pending': pending_info,
        'en_ok': en_ok,
        'tr_ok': len(recovered),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    COVER_REPORT.write_text(json.dumps(cover_rows, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'Done tr={len(recovered)} en={en_ok} tw={tw_ok} manifest={MANIFEST}')
    return 0 if len(recovered) == 10 and en_ok == 10 and tw_ok == 10 else 1


if __name__ == '__main__':
    sys.exit(main())
