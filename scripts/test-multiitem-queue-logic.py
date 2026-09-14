#!/usr/bin/env python3
"""Isolated logic tests for multi-item restore / ayristir / selective queue clear."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

# --- Port of Yazilari Ayristir filter (per item) ---

def parse_block(b: str, fallback_link: str = '') -> dict:
    baslik_m = re.search(r'BAŞLIK:\s*(.+)', b)
    ozet_m = re.search(r'ÖZET:\s*(.+)', b)
    kat_m = re.search(r'KATEGORİ:\s*(.+)', b)
    link_m = re.search(r'Link:\s*(https?://\S+)', b, re.I) or re.search(r'LINK:\s*(https?://\S+)', b, re.I)
    icerik_m = re.search(r'İÇERİK:\s*([\s\S]*)', b, re.I) or re.search(r'ICERIK:\s*([\s\S]*)', b, re.I)
    icerik = (icerik_m.group(1).strip() if icerik_m else '')
    icerik = re.sub(r'\nATLA\s*$', '', icerik, flags=re.I).strip()
    return {
        'baslik': baslik_m.group(1).strip() if baslik_m else '',
        'ozet': ozet_m.group(1).strip() if ozet_m else '',
        'kategori': kat_m.group(1).strip() if kat_m else 'Teknoloji',
        'link': (link_m.group(1).strip() if link_m else '') or fallback_link,
        'icerik': icerik,
    }


def ayristir_all(items: list[dict]) -> tuple[list[dict], dict]:
    """Simulate $input.all() flatMap Ayristir (new code)."""
    stats = {
        'input_items': 0, 'atla': 0, 'stop_reject': 0, 'parse_empty': 0,
        'word_lt_350': 0, 'punct_reject': 0, 'passed_posts': 0,
    }
    out = []
    for j in items:
        stats['input_items'] += 1
        content = j.get('content')
        raw = ''
        if isinstance(content, list) and content:
            raw = (content[0].get('text') or '') if isinstance(content[0], dict) else ''
        raw = (raw or j.get('text') or '').strip()
        stop = str(j.get('stop_reason') or '').lower()
        if stop and stop not in ('end_turn', 'stop', ''):
            stats['stop_reject'] += 1
            continue
        if not raw or raw == 'ATLA':
            stats['atla'] += 1
            continue
        posts = []
        if '===YAZI===' in raw:
            blocks = [b.strip() for b in raw.split('===YAZI===') if b.strip()]
            posts = [parse_block(b, j.get('link') or '') for b in blocks]
        elif re.search(r'BAŞLIK:', raw, re.I) and re.search(r'İÇERİK:', raw, re.I):
            posts = [parse_block(raw, j.get('link') or '')]
        posts = [p for p in posts if p['baslik'] and p['icerik']]
        if not posts:
            stats['parse_empty'] += 1
            continue
        kept = []
        for p in posts:
            t = p['icerik'].strip()
            words = len([w for w in re.split(r'\s+', t) if w])
            if words < 350:
                stats['word_lt_350'] += 1
                continue
            if not re.search(r'[.!?…]"?$', t):
                stats['punct_reject'] += 1
                continue
            stats['passed_posts'] += 1
            kept.append(p)
        if kept:
            out.append({'posts': kept, 'count': len(kept)})
    return out, stats


def restore_all(wait_items: list[dict], bol_items: list[dict], gorsel_items: list[dict]) -> list[dict]:
    """Simulate Post Verisini Geri Yukle $input.all() with index+link restore."""
    gorsel_by_link = {str(g.get('link') or '').strip(): g for g in gorsel_items if g.get('link')}
    out = []
    for idx, cur in enumerate(wait_items):
        bol = bol_items[idx] if idx < len(bol_items) else {}
        link = str(bol.get('link') or cur.get('link') or '').strip()
        gorsel = gorsel_by_link.get(link) or (gorsel_items[idx] if idx < len(gorsel_items) else {})
        merged = {**bol, **gorsel}
        if cur.get('url'):
            merged['coverImage'] = cur['url']
            merged['gorsel_r2_url'] = merged.get('gorsel_r2_url') or cur['url']
        merged['baslik'] = str(merged.get('baslik') or '').strip()
        if not merged['baslik']:
            raise AssertionError(f'restore failed idx={idx}')
        out.append(merged)
    return out


def selective_clear(queue_raw: str, published_links: list[str]) -> tuple[str, int, int]:
    published = set(published_links)
    kept, removed = [], []
    for line in queue_raw.split('\n'):
        t = line.strip()
        if not t:
            continue
        o = json.loads(t)
        link = str(o.get('link') or '').strip()
        if link and link in published:
            removed.append(link)
        else:
            kept.append(t)
    kalan = ('\n'.join(kept) + '\n') if kept else ''
    return kalan, len(removed), len(kept)


def make_article(title: str, words: int, link: str) -> str:
    body = ' '.join(['kelime'] * (words - 1)) + ' bitti.'
    return (
        f'===YAZI===\nBAŞLIK: {title}\nÖZET: ozet\nKATEGORİ: Teknoloji\n'
        f'Link: {link}\nİÇERİK:\n{body}\n'
    )


def test_ayristir_processes_all_not_just_first():
    items = [
        {'content': [{'text': make_article('Bir', 400, 'https://a.example/1')}]},
        {'content': [{'text': 'ATLA'}]},
        {'content': [{'text': make_article('Uc', 420, 'https://a.example/3')}]},
        {'content': [{'text': make_article('Dort', 200, 'https://a.example/4')}]},  # word filter
        {'content': [{'text': make_article('Bes', 450, 'https://a.example/5')}]},
    ]
    out, stats = ayristir_all(items)
    assert stats['input_items'] == 5
    assert stats['atla'] == 1
    assert stats['word_lt_350'] == 1
    assert stats['passed_posts'] == 3
    assert len(out) == 3
    titles = [o['posts'][0]['baslik'] for o in out]
    assert titles == ['Bir', 'Uc', 'Bes'], titles
    # OLD bug simulation: only first
    old_out, _ = ayristir_all(items[:1])
    assert len(old_out) == 1
    print('PASS ayristir processes all (3 passed, 1 ATLA, 1 word-reject)')


def test_restore_all_six_after_wait():
    bol = [{'baslik': f'Yazi {i}', 'icerik': f'body {i}', 'link': f'https://x/{i}', 'kategori': 'Teknoloji'} for i in range(6)]
    gorsel = [{**b, 'gorsel_r2_url': f'https://r2.dev/{i}.jpg'} for i, b in enumerate(bol)]
    wait = [{'url': f'https://r2.dev/{i}.jpg'} for i in range(6)]  # sparse Wait payload
    restored = restore_all(wait, bol, gorsel)
    assert len(restored) == 6
    assert [r['baslik'] for r in restored] == [f'Yazi {i}' for i in range(6)]
    assert all(r.get('gorsel_r2_url') for r in restored)
    # OLD bug: only first
    old = restore_all(wait[:1], bol, gorsel)
    assert len(old) == 1
    print('PASS restore recovers all 6 Wait items')


def test_selective_queue_clear():
    queue = '\n'.join([
        json.dumps({'baslik': 'A', 'link': 'https://a/1', 'kaynak': 'Engadget'}),
        json.dumps({'baslik': 'B', 'link': 'https://a/2', 'kaynak': 'HN'}),
        json.dumps({'baslik': 'C', 'link': 'https://a/3', 'kaynak': 'Verge'}),
        json.dumps({'baslik': 'D', 'link': 'https://a/4', 'kaynak': 'Ars'}),
    ]) + '\n'
    kalan, removed, kept = selective_clear(queue, ['https://a/1', 'https://a/3'])
    assert removed == 2
    assert kept == 2
    links = [json.loads(l)['link'] for l in kalan.strip().split('\n')]
    assert links == ['https://a/2', 'https://a/4']
    # full wipe would leave empty — we must NOT
    assert kalan.strip() != ''
    print('PASS selective queue clear keeps unpublished rows')


def test_live_workflow_codes():
    raw = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            "SELECT nodes::text FROM workflow_entity WHERE id='zVyc6gzToDe5mhc2';",
        ],
        text=True,
    ).strip()
    nodes = {n['name']: n for n in json.loads(raw)}
    for name in (
        'Yazilari Ayristir', 'Post Verisini Geri Yukle', 'Frontmatter Olustur',
        'Dosya Adi Dogrula', 'EN Cevir Prompt', 'EN Markdown Olustur',
    ):
        code = nodes[name]['parameters']['jsCode']
        assert '$input.all()' in code, name
    assert 'kalan_icerik' in nodes['Kuyruk Temizle Bos Icerik']['parameters']['jsCode']
    assert nodes['Kuyruk Temizle Dosyaya Cevir']['parameters']['sourceProperty'] == 'kalan_icerik'
    assert 'words < 350' in nodes['Yazilari Ayristir']['parameters']['jsCode']
    assert 'ayristir_filter_stats' in nodes['Yazilari Ayristir']['parameters']['jsCode']
    print('PASS live workflow codes contain $input.all() + selective queue + filter stats')


def main() -> None:
    test_ayristir_processes_all_not_just_first()
    test_restore_all_six_after_wait()
    test_selective_queue_clear()
    print('logic tests OK (live verify after import)')


if __name__ == '__main__':
    main()
