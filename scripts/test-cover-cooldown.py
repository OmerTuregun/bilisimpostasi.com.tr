#!/usr/bin/env python3
"""Isolated tests for 7-day cover photo cooldown."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
KEY = None


def load_unsplash_key() -> str:
    global KEY
    if KEY:
        return KEY
    env = (ROOT / 'n8n/.env').read_text()
    for line in env.splitlines():
        if line.startswith('UNSPLASH_ACCESS_KEY='):
            KEY = line.split('=', 1)[1].strip()
            return KEY
    raise SystemExit('UNSPLASH_ACCESS_KEY missing')


def psql(sql: str) -> str:
    return subprocess.check_output(
        ['docker', 'exec', '-i', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c', sql],
        text=True,
    ).strip()


def unsplash_search(query: str, per_page: int = 20) -> list[dict]:
    key = load_unsplash_key()
    qs = urllib.parse.urlencode({'query': query, 'per_page': per_page, 'orientation': 'landscape'})
    req = urllib.request.Request(
        f'https://api.unsplash.com/search/photos?{qs}',
        headers={'Authorization': f'Client-ID {key}', 'Accept-Version': 'v1'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data.get('results') or []


def select_photo(results: list[dict], used_at_by_id: dict[str, datetime], batch_used: set[str]):
    """Port of Gorsel Bilgi Hazirla selection."""
    now = datetime.now(timezone.utc)
    cooldown = timedelta(days=7)

    def blocked(pid: str) -> bool:
        if not pid or pid in batch_used:
            return True
        if pid not in used_at_by_id:
            return False
        return (now - used_at_by_id[pid]) < cooldown

    for rank, cand in enumerate(results):
        pid = str(cand.get('id') or '')
        if not blocked(pid):
            return cand, rank, False

    # pool exhausted
    best, best_rank, best_used = None, -1, datetime.max.replace(tzinfo=timezone.utc)
    for rank, cand in enumerate(results):
        pid = str(cand.get('id') or '')
        if not pid or pid in batch_used:
            continue
        t = used_at_by_id.get(pid) or datetime.min.replace(tzinfo=timezone.utc)
        if t < best_used:
            best, best_rank, best_used = cand, rank, t
    chosen = best or (results[0] if results else None)
    return chosen, (best_rank if best else 0), True


def load_used_from_db() -> dict[str, datetime]:
    rows = psql(
        "SELECT unsplash_photo_id||'|'||EXTRACT(EPOCH FROM MAX(used_at))::text "
        "FROM used_cover_photos "
        "WHERE used_at >= now() - interval '7 days' "
        "GROUP BY unsplash_photo_id"
    )
    out: dict[str, datetime] = {}
    if not rows:
        return out
    for line in rows.splitlines():
        pid, epoch = line.split('|', 1)
        out[pid] = datetime.fromtimestamp(float(epoch), tz=timezone.utc)
    return out


def record(pid: str, url: str, slug: str) -> None:
    pid_e = pid.replace("'", "''")
    url_e = url.replace("'", "''")
    slug_e = slug.replace("'", "''")
    psql(
        f"INSERT INTO used_cover_photos (unsplash_photo_id, photo_url, post_slug) "
        f"VALUES ('{pid_e}', '{url_e}', '{slug_e}');"
    )


def test_table_exists():
    assert psql("SELECT to_regclass('public.used_cover_photos')") == 'used_cover_photos'
    print('PASS table exists')


def test_sequential_diversity():
    """Same query 6 times → 6 different photo IDs (within 7d cooldown)."""
    # isolate with test prefix cleanup of our test rows only
    psql("DELETE FROM used_cover_photos WHERE post_slug LIKE 'test-cover-%';")
    query = 'artificial intelligence technology'
    results = unsplash_search(query, 20)
    assert len(results) >= 6, f'need ≥6 unsplash results, got {len(results)}'

    picked = []
    batch_used: set[str] = set()
    for i in range(6):
        used = load_used_from_db()
        # merge batch from previous iterations already in DB; batch_used cleared each call
        # but previous records are in DB now
        photo, rank, exhausted = select_photo(results, used, set())
        assert photo and photo.get('id'), i
        assert not exhausted, f'unexpected exhaust on iter {i}'
        pid = photo['id']
        assert pid not in picked, f'repeat on iter {i}: {pid} in {picked}'
        picked.append(pid)
        url = (photo.get('urls') or {}).get('regular') or ''
        record(pid, url, f'test-cover-{i}-{pid}')
        print(f'  pick[{i}] rank={rank} id={pid}')

    assert len(set(picked)) == 6
    n = psql("SELECT COUNT(*)::text FROM used_cover_photos WHERE post_slug LIKE 'test-cover-%'")
    assert n == '6', n
    print('PASS sequential 6 picks all distinct + table filled')


def test_pool_exhaustion():
    psql("DELETE FROM used_cover_photos WHERE post_slug LIKE 'test-pool-%'")
    # Tiny synthetic pool of 2 photos, both recently used
    results = [
        {'id': 'poolA', 'urls': {'regular': 'https://example.com/a.jpg'}},
        {'id': 'poolB', 'urls': {'regular': 'https://example.com/b.jpg'}},
    ]
    now = datetime.now(timezone.utc)
    # A used 6 days ago, B used 1 day ago → A is oldest → should reuse A
    psql(
        "INSERT INTO used_cover_photos (unsplash_photo_id, photo_url, post_slug, used_at) VALUES "
        f"('poolA', 'https://example.com/a.jpg', 'test-pool-a', now() - interval '6 days'),"
        f"('poolB', 'https://example.com/b.jpg', 'test-pool-b', now() - interval '1 day');"
    )
    used = load_used_from_db()
    photo, rank, exhausted = select_photo(results, used, set())
    assert exhausted is True
    assert photo['id'] == 'poolA', photo['id']
    assert rank == 0
    print('PASS pool exhaustion reuses oldest (poolA)')
    psql("DELETE FROM used_cover_photos WHERE post_slug LIKE 'test-pool-%'")


def test_workflow_live_config():
    nodes = json.loads(subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            "SELECT nodes::text FROM workflow_entity WHERE id='zVyc6gzToDe5mhc2';",
        ],
        text=True,
    ).strip())
    by = {n['name']: n for n in nodes}
    per = next(
        p['value']
        for p in by['Unsplash Arama']['parameters']['queryParameters']['parameters']
        if p['name'] == 'per_page'
    )
    assert str(per) == '20', per
    assert 'Kapak Cooldown Oku' in by
    assert 'Kapak Kaydet' in by
    assert 'isBlocked' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    assert 'cover_pool_exhausted' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    print('PASS live workflow cover-cooldown config')


def main():
    test_table_exists()
    test_sequential_diversity()
    test_pool_exhaustion()
    print('logic+API tests OK (run live config after patch)')


if __name__ == '__main__':
    main()
