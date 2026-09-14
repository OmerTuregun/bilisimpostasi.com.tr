#!/usr/bin/env python3
"""Aşama 50: one-time pending.jsonl cleanup for stale arXiv + blocked junk."""
from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
QUEUE = ROOT / 'site/src/content/_queue/pending.jsonl'
ARCHIVE = ROOT / 'site/src/content/_queue/atlandi.jsonl'
BACKUP = ROOT / 'n8n/backups'

# Items on/before this date that are arXiv or blocked_keyword are archived.
CUTOFF_DAY = '2026-08-24'

BLOCK_PATTERNS = [
    re.compile(r'\b(sponsored|advertorial|affiliate|giveaway|coupon|deals?\s+roundup)\b', re.I),
    re.compile(r'\b(celebrity|kardashian|royal\s+family|dating\s+rumor)\b', re.I),
    re.compile(r'\b(nfl|nba|premier\s+league|match\s+result|transfer\s+rumor|football)\b', re.I),
    re.compile(r'indirim\s+kodu|kupon\s+kodu|reklam\s+ilan|magazin\s+haber|skandal\s+foto', re.I),
    re.compile(r'clickbait|you\s+won\'t\s+believe|shocking\s+truth', re.I),
    re.compile(r'^\s*(watch|video|gallery|photos)\s*:', re.I),
    re.compile(r'\b(survived\s+9/11|buys a castle|steroid extravaganza)\b', re.I),
    re.compile(r'\b(usda|recall).*(beef|pounds)\b', re.I),
]


def blocked_reason(m: dict) -> str:
    blob = f"{m.get('baslik', '')} {m.get('ozet', '')}"
    for pat in BLOCK_PATTERNS:
        if pat.search(blob):
            return 'blocked_keyword'
    return ''


def day_of(m: dict) -> str:
    return str(m.get('eklenme_zamani', ''))[:10]


def should_archive(m: dict) -> str | None:
    d = day_of(m)
    if not d or d > CUTOFF_DAY:
        return None
    kaynak = str(m.get('kaynak', '')).lower()
    if kaynak == 'arxiv':
        return 'old_arxiv_backlog'
    reason = blocked_reason(m)
    if reason:
        return f'old_{reason}'
    return None


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(QUEUE, BACKUP / f'pending-pre-asama50-cleanup-{stamp}.jsonl')

    rows: list[dict] = []
    bad_lines = 0
    for line in QUEUE.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1

    kept: list[dict] = []
    archived: list[dict] = []
    reasons = Counter()

    for m in rows:
        why = should_archive(m)
        if why:
            reasons[why] += 1
            archived.append({
                **m,
                'archived_at': datetime.now(timezone.utc).isoformat(),
                'archive_reason': why,
            })
        else:
            kept.append(m)

    # Sort kept like workflow: newest first, RSS before arXiv
    priority = {
        'hacker news': 1,
        'techcrunch': 2,
        'the verge': 3,
        'engadget': 4,
        'ars technica': 5,
        'diğer': 20,
        'diger': 20,
        'arxiv': 100,
    }

    def added_at_ms(m: dict) -> float:
        try:
            return datetime.fromisoformat(
                str(m.get('eklenme_zamani', '')).replace('Z', '+00:00')
            ).timestamp()
        except ValueError:
            return 0.0

    kept.sort(
        key=lambda m: (
            -added_at_ms(m),
            priority.get(str(m.get('kaynak', '')).lower(), 50),
        )
    )

    with ARCHIVE.open('a', encoding='utf-8') as af:
        for m in archived:
            af.write(json.dumps(m, ensure_ascii=False) + '\n')

    with QUEUE.open('w', encoding='utf-8') as qf:
        for m in kept:
            qf.write(json.dumps(m, ensure_ascii=False) + '\n')

    print('cleanup_summary', json.dumps({
        'before': len(rows),
        'bad_lines_skipped': bad_lines,
        'archived': len(archived),
        'kept': len(kept),
        'reasons': dict(reasons),
        'cutoff_day': CUTOFF_DAY,
        'archive_file': str(ARCHIVE),
    }, ensure_ascii=False))

    print('first_5_kept:')
    for m in kept[:5]:
        print(f"  {str(m.get('eklenme_zamani',''))[:16]} | {m.get('kaynak')} | {(m.get('baslik') or '')[:70]}")


if __name__ == '__main__':
    main()
