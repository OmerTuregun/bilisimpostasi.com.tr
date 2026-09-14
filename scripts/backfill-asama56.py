#!/usr/bin/env python3
"""Aşama 56: Eski yazılara kapak görseli + etiket backfill."""
from __future__ import annotations

import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
POSTS = ROOT / 'site/src/content/posts'
TR_DIR = POSTS / 'tr'
EN_DIR = POSTS / 'en'
ENV_PATH = ROOT / 'n8n/.env'
REPORT_PATH = ROOT / 'n8n/backups/asama56-backfill-report.json'
STATE_PATH = ROOT / 'n8n/backups/asama56-backfill-state.json'
LOG_PATH = ROOT / 'n8n/backups/asama56-backfill.log'

HAIKU = 'claude-haiku-4-5-20251001'
COVER_BATCH = 8
TAG_BATCH = 18
COVER_BATCH_SLEEP = 20
TAG_BATCH_SLEEP = 8
TAG_CALL_SLEEP = 1.2
COVER_CALL_SLEEP = 3.0

CAT_MAP = {
    'Yapay Zeka': 'artificial intelligence semiconductor',
    'AI': 'artificial intelligence semiconductor',
    'Teknoloji': 'technology innovation',
    'Technology': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
    'Security': 'cybersecurity digital security',
    'Siber Güvenlik': 'cybersecurity digital security',
    'Donanım': 'computer hardware chip',
    'Yazılım': 'software development coding',
}

TOPIC_PHRASES = [
    (re.compile(r'cerebras|yarıiletken|yariiletken|semiconductor|chip\b|mikroişlem|mikroislem', re.I), 'semiconductor chip artificial intelligence'),
    (re.compile(r'nvidia|gpu|cuda', re.I), 'nvidia gpu technology'),
    (re.compile(r'openai|chatgpt', re.I), 'openai artificial intelligence'),
    (re.compile(r'claude|anthropic', re.I), 'artificial intelligence chatbot'),
    (re.compile(r'google|gemini|deepmind', re.I), 'google technology artificial intelligence'),
    (re.compile(r'meta\b|llama|facebook', re.I), 'meta artificial intelligence'),
    (re.compile(r'apple|iphone|ipad|mac\b', re.I), 'apple technology product'),
    (re.compile(r'tesla|robotaxi|waymo|otonom', re.I), 'autonomous vehicle technology'),
    (re.compile(r'yatırım|yatirim|venture|investor|startup|fonu|mayfield', re.I), 'venture capital technology office'),
    (re.compile(r'siber|güvenlik|guvenlik|hack|malware|phishing', re.I), 'cybersecurity digital security'),
    (re.compile(r'drone|teslimat', re.I), 'delivery drone technology'),
    (re.compile(r'veri merkezi|datacenter|data center', re.I), 'data center server room'),
    (re.compile(r'yapay\s+zeka|\bai\b', re.I), 'artificial intelligence technology'),
    (re.compile(r'robot|robotik', re.I), 'robotics technology'),
    (re.compile(r'bulut|cloud|aws|azure', re.I), 'cloud computing servers'),
    (re.compile(r'kripto|bitcoin|blockchain', re.I), 'cryptocurrency technology'),
]

JUNK_RE = re.compile(
    r'\b(sign|plaque|street|restaurant|cafe|mosque|church|wedding|portrait|selfie|dog|cat|food|meal|beach vacation|derneği|dernegi)\b',
    re.I,
)
TECH_RE = re.compile(
    r'\b(chip|circuit|computer|server|robot|ai|artificial|intelligence|technology|code|software|hardware|data|network|digital)\b',
    re.I,
)


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(line + '\n')


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in ENV_PATH.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env


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


def split_post(text: str) -> tuple[str, str]:
    m = re.match(r'^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$', text)
    if not m:
        raise ValueError('frontmatter missing')
    return m.group(1), m.group(2)


def parse_scalar(line: str) -> str:
    m = re.match(r'^[^:]+:\s*(.*)$', line)
    if not m:
        return ''
    val = m.group(1).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1].replace('\\"', '"')
    return val


def parse_post(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    fm_raw, body = split_post(text)
    fm: dict[str, str] = {}
    tags: list[str] = []
    tag_labels: dict[str, dict[str, str]] = {}
    in_tags = False
    in_tag_labels = False
    current_label_slug = ''

    for line in fm_raw.splitlines():
        if line.startswith('tags:'):
            in_tags = True
            in_tag_labels = False
            if re.match(r'^tags:\s*\[\s*\]\s*$', line) or re.match(r'^tags:\s*\[\]', line):
                in_tags = False
            continue
        if line.startswith('tagLabels:'):
            in_tags = False
            in_tag_labels = True
            continue
        if in_tags and re.match(r'^\s+-\s+', line):
            tags.append(line.split('-', 1)[1].strip())
            continue
        if in_tag_labels:
            m_slug = re.match(r'^\s{2}([a-z0-9-]+):\s*$', line)
            if m_slug:
                current_label_slug = m_slug.group(1)
                tag_labels[current_label_slug] = {'tr': '', 'en': ''}
                continue
            m_tr = re.match(r'^\s{4}tr:\s*"?([^"]*)"?', line)
            m_en = re.match(r'^\s{4}en:\s*"?([^"]*)"?', line)
            if current_label_slug and m_tr:
                tag_labels[current_label_slug]['tr'] = m_tr.group(1)
                continue
            if current_label_slug and m_en:
                tag_labels[current_label_slug]['en'] = m_en.group(1)
                continue
        in_tags = False
        in_tag_labels = False
        kv = re.match(r'^([A-Za-z0-9_]+):\s*(.*)$', line)
        if kv:
            fm[kv.group(1)] = parse_scalar(line)

    cover = (fm.get('coverImage') or '').strip()
    return {
        'path': path,
        'file': path.name,
        'fm': fm,
        'fm_raw': fm_raw,
        'body': body,
        'title': fm.get('title', ''),
        'description': fm.get('description', ''),
        'kategori': fm.get('kategori', 'Teknoloji'),
        'cover': cover,
        'tags': [t for t in tags if t],
        'tag_labels': tag_labels,
    }


def esc_yaml(s: str) -> str:
    return str(s or '').replace('"', "'")


def rebuild_frontmatter(fm: dict[str, str], tags: list[str], tag_labels: dict[str, dict[str, str]]) -> str:
    # Preserve common order; rebuild from fm dict minus cover/tag fields handled separately
    skip = {'coverImage', 'gorselFotografci', 'gorselFotografciLink', 'gorselQuery'}
    order = ['title', 'pubDate', 'kategori', 'description', 'kaynak']
    lines: list[str] = []
    for key in order:
        if key not in fm:
            continue
        val = fm[key]
        if key == 'pubDate':
            lines.append(f'{key}: {val}')
        else:
            lines.append(f'{key}: "{esc_yaml(val)}"')
    if tags:
        lines.append('tags:')
        for t in tags:
            lines.append(f'  - {t}')
    if tag_labels:
        lines.append('tagLabels:')
        for slug in tags:
            lb = tag_labels.get(slug) or {'tr': slug, 'en': slug}
            lines.append(f'  {slug}:')
            lines.append(f'    tr: "{esc_yaml(lb.get("tr", slug))}"')
            lines.append(f'    en: "{esc_yaml(lb.get("en", slug))}"')
    cover_keys = ['coverImage', 'gorselFotografci', 'gorselFotografciLink', 'gorselQuery']
    for key in cover_keys:
        if key in fm and fm[key]:
            lines.append(f'{key}: "{esc_yaml(fm[key])}"')
    for key, val in fm.items():
        if key in order or key in skip or key in cover_keys:
            continue
        if key in ('tags', 'tagLabels'):
            continue
        lines.append(f'{key}: "{esc_yaml(val)}"')
    return '\n'.join(lines)


def write_post(path: Path, fm: dict[str, str], tags: list[str], tag_labels: dict[str, dict[str, str]], body: str) -> None:
    fm_text = rebuild_frontmatter(fm, tags, tag_labels)
    body = body if body.endswith('\n') else body + '\n'
    path.write_text(f'---\n{fm_text}\n---\n{body}', encoding='utf-8')


def build_query(title: str, kategori: str, summary: str = '') -> str:
    haystack = f'{title} {summary}'.lower()
    cat_parts = [p.strip() for p in re.split(r'[|/·,]', kategori or '') if p.strip()]
    for part in cat_parts:
        if part in CAT_MAP:
            return CAT_MAP[part]
    for pat, q in TOPIC_PHRASES:
        if pat.search(haystack):
            return q
    for part in cat_parts:
        if part in CAT_MAP:
            return CAT_MAP[part]
    return 'technology innovation abstract'


def score_relevance(photo: dict, query: str) -> float:
    q_tokens = [t for t in query.lower().split() if len(t) > 2]
    text = ' '.join([
        str(photo.get('alt_description') or ''),
        str(photo.get('description') or ''),
        str(photo.get('slug') or ''),
        ' '.join((t.get('title') if isinstance(t, dict) else str(t)) for t in (photo.get('tags') or [])),
    ]).lower()
    if JUNK_RE.search(text):
        return -100
    score = 0.0
    for t in q_tokens:
        if t in text:
            score += 3
    if TECH_RE.search(query) and TECH_RE.search(text):
        score += 4
    if TECH_RE.search(query) and not TECH_RE.search(text) and len(text) > 10:
        score -= 2
    return score


def cdn_photo_key(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r'images\.unsplash\.com/(photo-[0-9]+-[a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'images\.unsplash\.com/([^?]+)', url)
    return m.group(1) if m else None


def unsplash_search(access_key: str, query: str, per_page: int = 20) -> list[dict]:
    qs = urllib.parse.urlencode({'query': query, 'per_page': per_page, 'orientation': 'landscape'})
    req = urllib.request.Request(
        f'https://api.unsplash.com/search/photos?{qs}',
        headers={
            'Authorization': f'Client-ID {access_key}',
            'Accept-Version': 'v1',
            'User-Agent': 'bilisimpostasi-asama56/1.0',
        },
    )
    last_err: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            return data.get('results') or []
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429, 503) and attempt < 5:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < 5:
                time.sleep(3 * (attempt + 1))
                continue
            raise
    raise last_err or RuntimeError('unsplash_search failed')


def pick_photo(results: list[dict], blocked: set[str], query: str) -> tuple[dict | None, int]:
    best_score = float('-inf')
    chosen = None
    chosen_rank = -1
    for rank, cand in enumerate(results):
        api_id = str(cand.get('id') or '')
        if not api_id or api_id in blocked:
            continue
        sc = score_relevance(cand, query)
        if sc < 0:
            continue
        if sc > best_score:
            best_score = sc
            chosen = cand
            chosen_rank = rank
    if chosen:
        return chosen, chosen_rank
    for rank, cand in enumerate(results):
        api_id = str(cand.get('id') or '')
        if api_id and api_id not in blocked:
            return cand, rank
    return (results[0] if results else None), 0


def unsplash_cover_url(photo: dict, access_key: str) -> str:
    regular = ((photo.get('urls') or {}).get('regular') or '')
    if not regular:
        return ''
    if 'images.unsplash.com' in regular:
        regular += ('&' if '?' in regular else '?') + 'w=1200&q=80&fm=jpg&fit=max'
    return regular


def slugify_tag(s: str) -> str:
    tr = str.maketrans({
        'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
        'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'İ': 'i', 'Ö': 'o', 'Ç': 'c',
    })
    s = s.translate(tr).lower()
    s = re.sub(r'[^a-z0-9-]+', '-', s).strip('-')
    return s


def parse_tags_line(line: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    slugs: list[str] = []
    labels: dict[str, dict[str, str]] = {}
    raw = str(line or '').strip()
    inner = raw.replace('[', '').replace(']', '').strip()
    if not inner:
        return slugs, labels
    for part in inner.split(','):
        bits = [b.strip() for b in part.split('|')]
        slug = slugify_tag(bits[0] if bits else '')
        if len(slug) < 2:
            continue
        slugs.append(slug)
        tr = (bits[1] if len(bits) > 1 else slug).strip()
        en = (bits[2] if len(bits) > 2 else (bits[1] if len(bits) > 1 else slug)).strip()
        labels[slug] = {'tr': tr, 'en': en}
        if len(slugs) >= 4:
            break
    return slugs, labels


def haiku_tags(api_key: str, title: str, summary: str, kategori: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    prompt = f"""Aşağıdaki teknoloji haberi için 2-4 etiket üret.

Başlık: {title}
Özet: {summary}
Kategori: {kategori}

KURALLAR:
- Yanıtında SADECE tek satır ver: ETİKETLER: [slug|TR ad|EN ad, slug2|TR ad2|EN ad2]
- Slug: küçük harf, Türkçe karakter yok, tire ile; 2-28 karakter; sadece a-z, 0-9, tire
- TR ve EN görünen adlar kısa ve doğal olsun (1-4 kelime)
"""
    payload = {
        'model': HAIKU,
        'max_tokens': 256,
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
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            text = data['content'][0]['text']
            m = re.search(r'ETİKETLER:\s*(\[[^\]]+\]|.+)$', text, re.M | re.I)
            if not m:
                raise ValueError(f'no ETİKETLER line: {text[:200]}')
            return parse_tags_line(m.group(1))
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
    raise RuntimeError('haiku_tags failed')


@dataclass
class Article:
    file: str
    tr_path: Path | None
    en_path: Path | None
    title: str = ''
    description: str = ''
    kategori: str = 'Teknoloji'
    needs_cover: bool = False
    needs_tags: bool = False


@dataclass
class Report:
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cover_updated_articles: int = 0
    cover_updated_files: int = 0
    cover_failed: list[dict] = field(default_factory=list)
    tag_updated_articles: int = 0
    tag_updated_files: int = 0
    tag_failed: list[dict] = field(default_factory=list)
    cover_examples: list[dict] = field(default_factory=list)
    tag_examples: list[dict] = field(default_factory=list)


def collect_articles() -> list[Article]:
    tr_files = {p.name: p for p in TR_DIR.glob('*.md')}
    en_files = {p.name: p for p in EN_DIR.glob('*.md')}
    all_names = sorted(set(tr_files) | set(en_files))
    articles: list[Article] = []
    for name in all_names:
        trp = tr_files.get(name)
        enp = en_files.get(name)
        src = parse_post(trp) if trp else parse_post(enp)
        tr_cover = parse_post(trp)['cover'] if trp else ''
        en_cover = parse_post(enp)['cover'] if enp else ''
        tr_tags = parse_post(trp)['tags'] if trp else []
        needs_cover = bool((trp and not tr_cover) or (enp and not en_cover))
        needs_tags = bool(trp and not tr_tags) if trp else bool(enp and not parse_post(enp)['tags'])
        articles.append(Article(
            file=name,
            tr_path=trp,
            en_path=enp,
            title=src['title'],
            description=src['description'],
            kategori=src['kategori'],
            needs_cover=needs_cover,
            needs_tags=needs_tags,
        ))
    return articles


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def backfill_covers(articles: list[Article], env: dict[str, str], report: Report, state: dict) -> None:
    access = env['UNSPLASH_ACCESS_KEY']
    blocked = load_cooldown_ids()
    todo = [
        a for a in articles
        if a.needs_cover and state.get('covers_done', {}).get(a.file, {}).get('ok') is not True
    ]
    log(f'cover backfill: {len(todo)} articles')
    for bi in range(0, len(todo), COVER_BATCH):
        batch = todo[bi: bi + COVER_BATCH]
        log(f'cover batch {bi // COVER_BATCH + 1}/{(len(todo) + COVER_BATCH - 1) // COVER_BATCH} size={len(batch)}')
        for art in batch:
            try:
                query = build_query(art.title, art.kategori, art.description)
                results = unsplash_search(access, query)
                photo, rank = pick_photo(results, blocked, query)
                if not photo:
                    raise RuntimeError('no unsplash result')
                api_id = str(photo.get('id') or '')
                cover_url = unsplash_cover_url(photo, access)
                photographer = (photo.get('user') or {}).get('name') or ''
                user_html = ((photo.get('user') or {}).get('links') or {}).get('html') or ''
                photog_link = f'{user_html}?utm_source=bilisimpostasi&utm_medium=referral' if user_html else ''
                before = {'cover': None}
                updated_files = 0
                for path in [art.tr_path, art.en_path]:
                    if not path:
                        continue
                    post = parse_post(path)
                    if post['cover']:
                        continue
                    before['cover'] = post['cover'] or '(yok)'
                    fm = dict(post['fm'])
                    fm['coverImage'] = cover_url
                    fm['gorselFotografci'] = photographer
                    fm['gorselFotografciLink'] = photog_link
                    fm['gorselQuery'] = query
                    write_post(path, fm, post['tags'], post['tag_labels'], post['body'])
                    updated_files += 1
                if api_id:
                    blocked.add(api_id)
                    record_cover(api_id, cover_url, art.file.replace('.md', ''))
                report.cover_updated_articles += 1
                report.cover_updated_files += updated_files
                if len(report.cover_examples) < 5:
                    report.cover_examples.append({
                        'file': art.file,
                        'title': art.title[:80],
                        'before': before.get('cover'),
                        'after': cover_url[:100] + '...',
                        'query': query,
                    })
                state.setdefault('covers_done', {})[art.file] = {'ok': True, 'query': query}
                log(f'  cover OK {art.file[:55]} query={query!r} rank={rank}')
                time.sleep(COVER_CALL_SLEEP)
            except Exception as e:
                report.cover_failed.append({'file': art.file, 'error': str(e)})
                state.setdefault('covers_done', {})[art.file] = {'ok': False, 'error': str(e)}
                log(f'  cover FAIL {art.file}: {e}')
        save_state(state)
        if bi + COVER_BATCH < len(todo):
            time.sleep(COVER_BATCH_SLEEP)


def backfill_tags(articles: list[Article], api_key: str, report: Report, state: dict) -> None:
    todo = [
        a for a in articles
        if a.needs_tags and state.get('tags_done', {}).get(a.file, {}).get('ok') is not True
    ]
    log(f'tag backfill: {len(todo)} articles')
    for bi in range(0, len(todo), TAG_BATCH):
        batch = todo[bi: bi + TAG_BATCH]
        log(f'tag batch {bi // TAG_BATCH + 1}/{(len(todo) + TAG_BATCH - 1) // TAG_BATCH} size={len(batch)}')
        for art in batch:
            try:
                slugs, labels = haiku_tags(api_key, art.title, art.description, art.kategori)
                if not slugs:
                    raise RuntimeError('empty tags from haiku')
                before_tags: list[str] = []
                updated_files = 0
                for path in [art.tr_path, art.en_path]:
                    if not path:
                        continue
                    post = parse_post(path)
                    if post['tags']:
                        continue
                    before_tags = post['tags']
                    fm = dict(post['fm'])
                    write_post(path, fm, slugs, labels, post['body'])
                    updated_files += 1
                report.tag_updated_articles += 1
                report.tag_updated_files += updated_files
                if len(report.tag_examples) < 5:
                    report.tag_examples.append({
                        'file': art.file,
                        'title': art.title[:80],
                        'before_tags': before_tags,
                        'after_tags': slugs,
                        'tag_labels': labels,
                    })
                state.setdefault('tags_done', {})[art.file] = {'ok': True, 'tags': slugs}
                log(f'  tag OK {art.file[:55]} tags={slugs}')
                time.sleep(TAG_CALL_SLEEP)
            except Exception as e:
                report.tag_failed.append({'file': art.file, 'error': str(e)})
                state.setdefault('tags_done', {})[art.file] = {'ok': False, 'error': str(e)}
                log(f'  tag FAIL {art.file}: {e}')
        save_state(state)
        if bi + TAG_BATCH < len(todo):
            time.sleep(TAG_BATCH_SLEEP)


def main() -> None:
    env = load_env()
    api_key = env.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise SystemExit('ANTHROPIC_API_KEY missing')
    if not env.get('UNSPLASH_ACCESS_KEY'):
        raise SystemExit('UNSPLASH_ACCESS_KEY missing')

    state = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding='utf-8'))

    articles = collect_articles()
    report = Report()
    log(f'start asama56: cover_needed={sum(1 for a in articles if a.needs_cover)} tag_needed={sum(1 for a in articles if a.needs_tags)}')

    backfill_covers(articles, env, report, state)
    backfill_tags(articles, api_key, report, state)

    report.finished_at = datetime.now(timezone.utc).isoformat()
    REPORT_PATH.write_text(json.dumps(report.__dict__, ensure_ascii=False, indent=2), encoding='utf-8')
    log('report written ' + str(REPORT_PATH))
    log(
        f'done covers: articles={report.cover_updated_articles} files={report.cover_updated_files} '
        f'failed={len(report.cover_failed)} | tags: articles={report.tag_updated_articles} '
        f'files={report.tag_updated_files} failed={len(report.tag_failed)}'
    )


if __name__ == '__main__':
    main()
