#!/usr/bin/env python3
"""Unit tests: P0 batch limit, prefilter, arXiv cap, queue keep."""
from __future__ import annotations

import json
import re
from pathlib import Path

BATCH_LIMIT = 5
MIN_TITLE_LEN = 12
MIN_SUMMARY_LEN = 20
ARXIV_MAX = 25

BLOCK_PATTERNS = [
    re.compile(r'\b(sponsored|advertorial|giveaway|coupon)\b', re.I),
    re.compile(r'indirim\s+kodu|magazin\s+haber', re.I),
]


def prefilter_reason(m: dict) -> str:
    title = str(m.get('baslik') or '').strip()
    ozet = str(m.get('ozet') or '').strip()
    link = str(m.get('link') or '').strip()
    if not link.startswith('http'):
        return 'bad_link'
    if len(title) < MIN_TITLE_LEN:
        return 'short_title'
    if ozet and len(ozet) < MIN_SUMMARY_LEN:
        return 'short_summary'
    for pat in BLOCK_PATTERNS:
        if pat.search(title) or pat.search(ozet):
            return 'blocked_keyword'
    return ''


def prepare_batch(queue: list[dict], published: set[str]) -> tuple[list[dict], list[str]]:
    seen: set[str] = set()
    dropped: list[str] = []
    candidates: list[dict] = []
    for m in queue:
        link = str(m.get('link') or '').strip().rstrip('/')
        if not link or link in seen:
            if link:
                dropped.append(link)
            continue
        seen.add(link)
        if link in published:
            dropped.append(link)
            continue
        reason = prefilter_reason(m)
        if reason:
            dropped.append(link)
            continue
        candidates.append(m)
    return candidates[:BATCH_LIMIT], dropped


def selective_clear(raw: str, published: set[str], prefilter_drop: set[str]) -> tuple[list[str], int]:
    kept = []
    removed = 0
    for line in raw.splitlines():
        t = line.strip()
        if not t:
            continue
        o = json.loads(t)
        link = str(o.get('link') or '').strip()
        if link and (link in published or link in prefilter_drop):
            removed += 1
            continue
        kept.append(t)
    return kept, removed


def arxiv_append(rows: list[dict], existing: set[str]) -> tuple[list[str], int, int]:
    additions = []
    arxiv_added = 0
    arxiv_skipped = 0
    for m in rows:
        link = str(m.get('link') or '').strip()
        if not link or link in existing:
            continue
        kaynak = str(m.get('kaynak') or '')
        is_arxiv = kaynak == 'arXiv' or 'arxiv.org' in link
        if is_arxiv:
            if arxiv_added >= ARXIV_MAX:
                arxiv_skipped += 1
                continue
            arxiv_added += 1
        existing.add(link)
        additions.append(json.dumps(m, ensure_ascii=False))
    return additions, arxiv_added, arxiv_skipped


def main() -> None:
    # 1) batch limit
    queue = [
        {'baslik': f'Valid tech headline number {i}', 'ozet': 'A long enough summary for tech news item.', 'link': f'https://example.com/{i}', 'kaynak': 'TechCrunch'}
        for i in range(12)
    ]
    batch, dropped = prepare_batch(queue, set())
    assert len(batch) == 5, len(batch)
    assert batch[0]['link'] == 'https://example.com/0'
    print('PASS batch limit 5/12')

    # 2) prefilter
    bad = [
        {'baslik': 'Short', 'ozet': 'ok summary here', 'link': 'https://x.com/1'},
        {'baslik': 'Magazin haber skandal', 'ozet': 'celebrity gossip', 'link': 'https://x.com/2'},
        {'baslik': 'Good AI headline here', 'ozet': 'Detailed summary about artificial intelligence.', 'link': 'https://x.com/3'},
    ]
    b2, d2 = prepare_batch(bad, set())
    assert len(b2) == 1 and b2[0]['link'] == 'https://x.com/3'
    assert len(d2) == 2
    print('PASS prefilter drops 2/3')

    # 3) queue keep + prefilter drop removal
    raw = '\n'.join(json.dumps(x) for x in queue[:8])
    prefilter_drop = {queue[1]['link'], queue[3]['link']}
    kept, rem = selective_clear(raw, set(), prefilter_drop)
    assert rem == 2 and len(kept) == 6
    print('PASS selective clear removes prefilter drops')

    # 4) arxiv cap
    rows = [
        {'baslik': f'Paper {i}', 'link': f'https://arxiv.org/abs/2401.{i:04d}', 'kaynak': 'arXiv', 'ozet': 'abstract'}
        for i in range(40)
    ]
    adds, arx, skip = arxiv_append(rows, set())
    assert arx == 25 and skip == 15 and len(adds) == 25
    print('PASS arxiv cap 25/40')

    print('\nALL P0 LOGIC TESTS PASSED')


if __name__ == '__main__':
    main()
