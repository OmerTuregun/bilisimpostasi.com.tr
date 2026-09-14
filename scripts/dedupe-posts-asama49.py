#!/usr/bin/env python3
"""Deduplicate published posts by kaynak URL (+ near-identical titles); rebuild published-links index."""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

ROOT = Path('/root/agent-icerik-sistemi')
TR = ROOT / 'site/src/content/posts/tr'
EN = ROOT / 'site/src/content/posts/en'
QUEUE = ROOT / 'site/src/content/_queue'
BACKUP = ROOT / 'n8n/backups' / 'dedupe-20260826'
PUBLISHED_LINKS = QUEUE / 'published-links.jsonl'


def normalize_link(url: str) -> str:
    u = str(url or '').strip()
    if not u:
        return ''
    try:
        p = urlparse(u)
        host = (p.netloc or '').lower()
        if host.startswith('www.'):
            host = host[4:]
        path = (p.path or '').rstrip('/')
        # drop tracking query params
        q = parse_qs(p.query, keep_blank_values=False)
        keep = {
            k: v
            for k, v in q.items()
            if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid', 'ref', 'source'}
        }
        query = urlencode(keep, doseq=True)
        return urlunparse((p.scheme.lower() or 'https', host, path, '', query, ''))
    except Exception:
        return u.rstrip('/')


def norm_title(t: str) -> str:
    t = (t or '').lower()
    t = re.sub(r'[^\w\sçğıöşü]', '', t, flags=re.I)
    return re.sub(r'\s+', ' ', t).strip()


def parse_post(path: Path) -> dict:
    raw = path.read_text(encoding='utf-8')
    meta: dict[str, str] = {}
    m = re.match(r'^---\n([\s\S]*?)\n---\n', raw)
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip().strip('"')
    return {
        'path': path,
        'name': path.name,
        'title': meta.get('title', ''),
        'kaynak': meta.get('kaynak', ''),
        'kaynak_n': normalize_link(meta.get('kaynak', '')),
        'pubDate': meta.get('pubDate', ''),
        'cover': meta.get('coverImage', ''),
        'title_n': norm_title(meta.get('title', '')),
    }


def score(p: dict) -> tuple:
    # Prefer: has cover, earliest pubDate, stable name
    return (
        1 if p['cover'] else 0,
        p['pubDate'] or '9999',
        p['name'],
    )


def main() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    posts = [parse_post(p) for p in sorted(TR.glob('*.md'))]

    # 1) Groups by normalized kaynak
    by_link: dict[str, list] = defaultdict(list)
    for p in posts:
        if p['kaynak_n']:
            by_link[p['kaynak_n']].append(p)

    to_delete: dict[str, str] = {}  # name -> reason
    keep_report = []

    for link, group in by_link.items():
        if len(group) < 2:
            continue
        # Only treat as content-dup if titles are similar OR majority share similar titles
        titles = [g['title_n'] for g in group if g['title_n']]
        similar = True
        if len(titles) >= 2:
            # if any pair is very dissimilar AND group is large with mixed topics, skip mixed
            ratios = []
            for i, a in enumerate(titles):
                for b in titles[i + 1 :]:
                    ratios.append(SequenceMatcher(None, a, b).ratio())
            avg = sum(ratios) / len(ratios) if ratios else 1.0
            # Mixed wrong-kaynak clusters (old bug): low avg similarity -> don't mass-delete
            if avg < 0.45 and len(group) > 3:
                continue
            # For small groups, require at least one pair reasonably similar
            if avg < 0.45 and max(ratios) < 0.55:
                continue

        ranked = sorted(group, key=score)
        # Prefer with cover among earliest: re-rank
        ranked = sorted(group, key=lambda p: (-(1 if p['cover'] else 0), p['pubDate'] or '9999', p['name']))
        keeper = ranked[0]
        keep_report.append({'keep': keeper['name'], 'link': link, 'removed': [x['name'] for x in ranked[1:]]})
        for x in ranked[1:]:
            to_delete[x['name']] = f'dup_kaynak:{link[:80]}'

    # 2) Exact / near-exact title dups without shared link (or missed)
    by_title: dict[str, list] = defaultdict(list)
    for p in posts:
        if p['name'] in to_delete:
            continue
        if p['title_n'] and len(p['title_n']) > 20:
            by_title[p['title_n']].append(p)
    for title, group in by_title.items():
        if len(group) < 2:
            continue
        ranked = sorted(group, key=lambda p: (-(1 if p['cover'] else 0), p['pubDate'] or '9999', p['name']))
        keeper = ranked[0]
        keep_report.append({'keep': keeper['name'], 'title': title, 'removed': [x['name'] for x in ranked[1:]]})
        for x in ranked[1:]:
            to_delete[x['name']] = f'dup_title:{title[:60]}'

    # Fuzzy title among recent (Aug 24+) remaining
    recent = [p for p in posts if p['name'] not in to_delete and re.search(r'202608(2[4-9]|3)', p['name'])]
    used = set()
    for i, a in enumerate(recent):
        if a['name'] in used or a['name'] in to_delete:
            continue
        cluster = [a]
        for b in recent[i + 1 :]:
            if b['name'] in used or b['name'] in to_delete:
                continue
            r = SequenceMatcher(None, a['title_n'], b['title_n']).ratio()
            if r >= 0.82:
                cluster.append(b)
        if len(cluster) < 2:
            continue
        ranked = sorted(cluster, key=lambda p: (-(1 if p['cover'] else 0), p['pubDate'] or '9999', p['name']))
        keeper = ranked[0]
        used.add(keeper['name'])
        keep_report.append({
            'keep': keeper['name'],
            'fuzzy': keeper['title_n'][:70],
            'removed': [x['name'] for x in ranked[1:]],
        })
        for x in ranked[1:]:
            used.add(x['name'])
            to_delete[x['name']] = f'dup_fuzzy:{keeper["title_n"][:50]}'

    deleted = []
    for name, reason in sorted(to_delete.items()):
        src = TR / name
        if not src.exists():
            continue
        shutil.copy2(src, BACKUP / name)
        en = EN / name
        if en.exists():
            shutil.copy2(en, BACKUP / f'en-{name}')
            en.unlink()
        src.unlink()
        deleted.append({'file': name, 'reason': reason})

    # Rebuild published-links.jsonl from remaining TR posts
    remaining = [parse_post(p) for p in sorted(TR.glob('*.md'))]
    links = sorted({p['kaynak_n'] for p in remaining if p['kaynak_n']})
    PUBLISHED_LINKS.write_text(
        '\n'.join(json.dumps({'link': l}, ensure_ascii=False) for l in links) + ('\n' if links else ''),
        encoding='utf-8',
    )

    report = {
        'deleted_count': len(deleted),
        'deleted': deleted,
        'kept_groups': keep_report,
        'published_links_count': len(links),
        'remaining_tr': len(remaining),
    }
    out = BACKUP / 'report.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'deleted_count': len(deleted), 'published_links': len(links), 'remaining_tr': len(remaining)}, indent=2))
    print('backup/report ->', BACKUP)


if __name__ == '__main__':
    main()
