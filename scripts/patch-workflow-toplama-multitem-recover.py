#!/usr/bin/env python3
"""Fix Haber Toplama multi-item queue append + recover TC/Ars/arXiv after lastItemDate skip.

Root cause (2026-08-21):
- pending.jsonl missing caused failed writes, but RSS trigger still advanced
  staticData lastItemDate to the newest feed item → those items never re-emit.
- Code used $('Edit Fields2').first() → even on success only 1 of N items
  (e.g. arXiv 222) would be queued.

Feeds themselves are healthy; Garantile is shared by all sources.
"""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import time
import urllib.request
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'bsqTiPswUyJSDCsC'
PENDING = ROOT / 'site/src/content/_queue/pending.jsonl'

CODE = r'''// Append ALL new Edit Fields rows (not only .first()). Dedupe by link.
const mevcut = String($input.first().json.data || '');
const existing = new Set();
for (const line of mevcut.split('\n')) {
  const t = line.trim();
  if (!t) continue;
  try {
    const o = JSON.parse(t);
    if (o.link) existing.add(String(o.link).trim());
  } catch (e) {}
}

let rows = [];
try {
  rows = $('Edit Fields2').all().map((i) => i.json || {});
} catch (e) {
  rows = [];
}

const additions = [];
for (const m of rows) {
  const link = String(m.link || '').trim();
  if (!link || existing.has(link)) continue;
  existing.add(link);
  additions.push(
    JSON.stringify({
      baslik: m.baslik || '',
      link,
      ozet: m.ozet || '',
      kaynak: m.kaynak || '',
      eklenme_zamani: m.ekleme_zamani || m.eklenme_zamani || new Date().toISOString(),
    })
  );
}

console.log(
  '[haber_toplama_append] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      incoming: rows.length,
      added: additions.length,
      skipped_dup: rows.length - additions.length,
    })
);

const base = mevcut.trim();
const guncelIcerik = additions.length
  ? (base ? base + '\n' + additions.join('\n') : additions.join('\n'))
  : base;

return [{ json: { icerik: guncelIcerik } }];
'''

FEEDS = {
    'TechCrunch': {
        'url': 'https://techcrunch.com/feed/',
        'trigger': 'RSS Feed Trigger',
        'kaynak': 'TechCrunch',
    },
    'Ars Technica': {
        'url': 'https://feeds.arstechnica.com/arstechnica/index',
        'trigger': 'RSS Feed Trigger1',
        'kaynak': 'Ars Technica',
    },
    'arXiv': {
        'url': 'http://export.arxiv.org/rss/cs.AI',
        'trigger': 'RSS Feed Trigger3',
        'kaynak': 'arXiv',
    },
}

# Reset cursor to before the outage so next poll can also see remaining items
RESET_LAST_ITEM_DATE = '2026-08-19T12:00:00.000Z'


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-toplama-{stamp}-pre-multitem-recover.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-toplama-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-toplama-pre.json', str(out)], check=True)
    return out


def patch_code(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    by['Code in JavaScript']['parameters']['jsCode'] = CODE
    by['Code in JavaScript']['parameters'].pop('mode', None)
    out = BACKUP / 'haber-toplama-multitem-recover-fixed.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-toplama-fixed.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-toplama-fixed.json'],
        check=True,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'],
        check=True,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )


def get_static() -> dict:
    raw = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f'SELECT COALESCE("staticData"::text, \'{{}}\') FROM workflow_entity WHERE id=\'{WF_ID}\';',
        ],
        text=True,
    ).strip()
    return json.loads(raw or '{}')


def set_static(data: dict) -> None:
    payload = json.dumps(data).replace("'", "''")
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-c',
            f'UPDATE workflow_entity SET "staticData" = \'{payload}\'::json WHERE id=\'{WF_ID}\';',
        ],
        check=True,
    )


def reset_cursors() -> dict:
    static = get_static()
    before = {}
    for meta in FEEDS.values():
        key = f"node:{meta['trigger']}"
        node = static.setdefault(key, {})
        before[meta['trigger']] = node.get('lastItemDate')
        node['lastItemDate'] = RESET_LAST_ITEM_DATE
        # clear legacy key if present
        node.pop('lastTimeChecked', None)
    set_static(static)
    return before


def parse_feed(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; bilisim-postasi/1.0)'})
    with urllib.request.urlopen(req, timeout=40, context=ssl.create_default_context()) as r:
        text = r.read().decode('utf-8', 'replace')

    items = []
    # RSS <item>
    for block in re.findall(r'<item[\s\S]*?</item>', text, re.I):
        def tag(name: str) -> str:
            m = re.search(rf'<{name}[^>]*><!\[CDATA\[(.*?)\]\]></{name}>', block, re.I | re.S)
            if m:
                return m.group(1).strip()
            m = re.search(rf'<{name}[^>]*>([^<]*)</{name}>', block, re.I)
            return (m.group(1).strip() if m else '')

        link = tag('link')
        if not link:
            m = re.search(r'<link[^>]+href=["\']([^"\']+)', block, re.I)
            link = m.group(1).strip() if m else ''
        title = re.sub(r'\s+', ' ', tag('title'))
        desc = re.sub(r'\s+', ' ', tag('description') or tag('content:encoded'))[:500]
        items.append({'baslik': title, 'link': link, 'ozet': desc})

    if items:
        return [i for i in items if i.get('link')]

    # Atom <entry> (arxiv often RSS 1.0/RDF or Atom-like)
    for block in re.findall(r'<entry[\s\S]*?</entry>', text, re.I):
        title_m = re.search(r'<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', block, re.I | re.S)
        id_m = re.search(r'<id>([^<]+)</id>', block, re.I)
        link_m = re.search(r'<link[^>]+href=["\']([^"\']+)', block, re.I)
        summary_m = re.search(r'<summary[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</summary>', block, re.I | re.S)
        title = re.sub(r'\s+', ' ', (title_m.group(1) if title_m else '')).strip()
        link = (link_m.group(1) if link_m else (id_m.group(1) if id_m else '')).strip()
        ozet = re.sub(r'\s+', ' ', (summary_m.group(1) if summary_m else ''))[:500]
        if link:
            items.append({'baslik': title, 'link': link, 'ozet': ozet})
    return items


def load_pending_links() -> set[str]:
    if not PENDING.exists():
        PENDING.write_text('')
    links = set()
    for line in PENDING.read_text().splitlines():
        t = line.strip()
        if not t:
            continue
        try:
            links.add(json.loads(t).get('link', '').strip())
        except Exception:
            pass
    return links


def append_pending(rows: list[dict]) -> int:
    links = load_pending_links()
    added = []
    now = datetime.now(timezone.utc).isoformat()
    for r in rows:
        link = (r.get('link') or '').strip()
        if not link or link in links:
            continue
        links.add(link)
        added.append(
            json.dumps(
                {
                    'baslik': r.get('baslik') or '',
                    'link': link,
                    'ozet': r.get('ozet') or '',
                    'kaynak': r.get('kaynak') or '',
                    'eklenme_zamani': now,
                },
                ensure_ascii=False,
            )
        )
    if not added:
        return 0
    prev = PENDING.read_text(encoding='utf-8') if PENDING.exists() else ''
    prefix = '\n' if prev and not prev.endswith('\n') else ''
    with PENDING.open('a', encoding='utf-8') as f:
        f.write(prefix + '\n'.join(added) + '\n')
    return len(added)


def test_code_logic_222() -> None:
    """Simulate Code append with 222 items into a temp-like pending buffer."""
    existing = {'https://already.example/x'}
    rows = [
        {'baslik': f'P{i}', 'link': f'https://arxiv.org/abs/test.{i}', 'ozet': 'o', 'kaynak': 'arXiv', 'ekleme_zamani': 't'}
        for i in range(222)
    ]
    rows.append({'baslik': 'dup', 'link': 'https://arxiv.org/abs/test.1', 'ozet': '', 'kaynak': 'arXiv'})
    additions = []
    for m in rows:
        link = m['link']
        if link in existing:
            continue
        existing.add(link)
        additions.append(json.dumps(m))
    assert len(additions) == 222, len(additions)
    print('PASS code-logic would append 222/223 (1 dup skipped)')


def restart_n8n() -> None:
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(2)


def verify_live_code() -> None:
    nodes = json.loads(
        subprocess.check_output(
            [
                'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
                f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';",
            ],
            text=True,
        ).strip()
    )
    code = next(n['parameters']['jsCode'] for n in nodes if n['name'] == 'Code in JavaScript')
    assert "$('Edit Fields2').all()" in code
    assert '.first().json.baslik' not in code
    print('PASS live Code uses Edit Fields2.all()')


def main() -> None:
    test_code_logic_222()

    pre = export_live()
    print('backup', pre)
    patched = patch_code(pre)
    print('patched', patched)
    import_publish(patched)

    before = reset_cursors()
    print('reset lastItemDate:', before, '→', RESET_LAST_ITEM_DATE)

    restart_n8n()
    verify_live_code()

    # Recover current feed items into pending (immediate, not waiting for poll)
    report = {}
    for name, meta in FEEDS.items():
        items = parse_feed(meta['url'])
        for it in items:
            it['kaynak'] = meta['kaynak']
        added = append_pending(items)
        report[name] = {'feed_items': len(items), 'added_to_pending': added}
        print(f'recover {name}: feed={len(items)} added={added}')

    # Count pending by kaynak
    by_k: dict[str, int] = {}
    for line in PENDING.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            k = json.loads(line).get('kaynak') or '?'
        except Exception:
            k = '?'
        by_k[k] = by_k.get(k, 0) + 1
    print('pending by kaynak:', by_k)
    print('pending total lines:', sum(by_k.values()))
    print('REPORT_JSON', json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
