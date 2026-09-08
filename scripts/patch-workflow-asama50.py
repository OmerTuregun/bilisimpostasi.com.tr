#!/usr/bin/env python3
"""Aşama 50: ATLA kuyruk temizliği + taze/kaynak öncelikli sıralama."""
from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'zVyc6gzToDe5mhc2'

# Sort queue newest-first + RSS before arXiv (BATCH_LIMIT unchanged at 5).
HABER_LISTESI_SORT_SNIPPET = r'''
function sourcePriority(kaynak) {
  const k = String(kaynak || '').trim().toLowerCase();
  const map = {
    'hacker news': 1,
    'techcrunch': 2,
    'the verge': 3,
    'engadget': 4,
    'ars technica': 5,
    'diğer': 20,
    'diger': 20,
    'arxiv': 100,
  };
  return map[k] ?? 50;
}

function addedAtMs(m) {
  const t = Date.parse(String(m.eklenme_zamani || ''));
  return Number.isFinite(t) ? t : 0;
}

makaleler.sort((a, b) => {
  const byTime = addedAtMs(b) - addedAtMs(a);
  if (byTime !== 0) return byTime;
  return sourcePriority(a.kaynak) - sourcePriority(b.kaynak);
});
'''

AYRISTIR_CODE = r'''const listItems = (() => {
  try { return $('Haber Listesini Hazirla').all(); } catch (e) { return []; }
})();

const WORD_INFO_THRESHOLD = 250;

function normalizeLink(link) {
  return String(link || '').trim().replace(/\/+$/, '');
}

const stats = {
  event: 'ayristir_filter_stats',
  ts: new Date().toISOString(),
  input_items: 0,
  atla: 0,
  stop_reject: 0,
  parse_empty: 0,
  word_lt_250_info: 0,
  punct_reject: 0,
  passed_posts: 0,
  word_counts_info_under: [],
  word_counts_passed: [],
};

const atlaDroppedLinks = [];

function parseBlock(b, fallbackLink) {
  const baslikMatch = b.match(/BAŞLIK:\s*(.+)/);
  const ozetMatch = b.match(/ÖZET:\s*(.+)/);
  const kategoriMatch = b.match(/KATEGORİ:\s*(.+)/);
  const linkMatch =
    b.match(/Link:\s*(https?:\/\/\S+)/i) ||
    b.match(/LINK:\s*(https?:\/\/\S+)/i);
  const icerikMatch = b.match(/İÇERİK:\s*([\s\S]*)/i) || b.match(/ICERIK:\s*([\s\S]*)/i);
  const baslik = baslikMatch ? baslikMatch[1].trim() : '';
  const ozet = ozetMatch ? ozetMatch[1].trim() : '';
  const kategori = kategoriMatch ? kategoriMatch[1].trim() : 'Teknoloji';
  const link = (linkMatch ? linkMatch[1].trim() : '') || fallbackLink || '';
  let icerik = icerikMatch ? icerikMatch[1].trim() : '';
  icerik = icerik.replace(/\nATLA\s*$/i, '').trim();
  icerik = icerik.replace(/\n---+\s*$/g, '').trim();
  icerik = icerik.replace(/\n+[*_]*\s*(?:İÇERİK\s+)?(?:KELIME\s+)?SAYISI\s*:?\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n+[*_*]*\s*(?:Kelime\s*)?Say[ıiİI]s[ıiİI]\s*:?\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n+[*_]*\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n---+\s*$/g, '').trim();
  icerik = icerik.replace(/\*+\s*$/g, '').trim();
  return { baslik, ozet, kategori, link, icerik };
}

const out = [];

for (const [idx, item] of $input.all().entries()) {
  stats.input_items += 1;
  const j = item.json || {};
  const raw = (j.content?.[0]?.text || j.text || '').trim();
  const stopReason = String(
    j.stop_reason || j.stopReason || j.response?.stop_reason || j.meta?.stop_reason || ''
  ).toLowerCase();

  const itemLink = normalizeLink(
    (listItems[idx] && listItems[idx].json && listItems[idx].json.link) || j.link || ''
  );

  if (stopReason && stopReason !== 'end_turn' && stopReason !== 'stop') {
    stats.stop_reject += 1;
    continue;
  }
  if (!raw || raw === 'ATLA') {
    stats.atla += 1;
    if (itemLink) atlaDroppedLinks.push(itemLink);
    continue;
  }

  let posts = [];
  if (raw.includes('===YAZI===')) {
    const blocks = raw.split('===YAZI===').map((b) => b.trim()).filter(Boolean);
    posts = blocks.map((b) => parseBlock(b, itemLink));
  } else if (/BAŞLIK:/i.test(raw) && /İÇERİK:/i.test(raw)) {
    posts = [parseBlock(raw, itemLink)];
  }

  posts = posts
    .map((p) => ({ ...p, link: p.link || itemLink }))
    .filter((p) => p.baslik && p.icerik);

  if (!posts.length) {
    stats.parse_empty += 1;
    continue;
  }

  const kept = [];
  for (const p of posts) {
    const t = String(p.icerik || '').trim();
    const words = t.split(/\s+/).filter(Boolean).length;
    if (words < WORD_INFO_THRESHOLD) {
      stats.word_lt_250_info += 1;
      stats.word_counts_info_under.push(words);
      console.log(
        '[ayristir_word_info] under threshold words=' +
          words +
          ' baslik=' +
          String(p.baslik || '').slice(0, 80)
      );
    }
    const listEndOk = /(?:^|\n)-\s+\S[\s\S]*$/.test(t);
    if (!/[.!?…]"?$/.test(t) && !listEndOk) {
      stats.punct_reject += 1;
      continue;
    }
    stats.passed_posts += 1;
    stats.word_counts_passed.push(words);
    kept.push(p);
  }

  if (kept.length) {
    out.push({ json: { posts: kept, count: kept.length } });
  }
}

if (!out.length) {
  out.push({ json: { posts: [], count: 0 } });
}
out[0].json.atla_dropped_links = atlaDroppedLinks;

console.log(
  '[ayristir_filter_stats] ' +
    JSON.stringify({ ...stats, atla_dropped: atlaDroppedLinks.length })
);
return out;
'''

QUEUE_CLEAR_CODE = r'''// Remove published, prefilter-dropped, and Claude ATLA rows from pending queue.
function normalizeLink(link) {
  return String(link || '').trim().replace(/\/+$/, '');
}

const published = new Set();
try {
  for (const it of $('Frontmatter Olustur').all()) {
    const link = normalizeLink((it.json && it.json.link) || '');
    if (link) published.add(link);
  }
} catch (e) {}

const prefilterDrop = new Set();
try {
  const drops =
    ($('Haber Listesini Hazirla').first().json.prefilter_dropped_links || []);
  for (const l of drops) {
    const t = normalizeLink(l);
    if (t) prefilterDrop.add(t);
  }
} catch (e) {}

const atlaDrop = new Set();
try {
  for (const it of $('Yazilari Ayristir').all()) {
    const links = it.json.atla_dropped_links || [];
    for (const l of links) {
      const t = normalizeLink(l);
      if (t) atlaDrop.add(t);
    }
  }
} catch (e) {}

const fs = require('fs');
const atlandiPath = '/home/node/site/src/content/_queue/atlandi.jsonl';

let raw = '';
try {
  raw = String($('Kuyruk Metnini Cikar').first().json.data || '');
} catch (e) {
  raw = '';
}

const kept = [];
const removed = [];
for (const line of raw.split('\n')) {
  const t = line.trim();
  if (!t) continue;
  try {
    const o = JSON.parse(t);
    const link = normalizeLink(o.link || '');
    let why = '';
    if (link && published.has(link)) why = 'published';
    else if (link && prefilterDrop.has(link)) why = 'prefilter';
    else if (link && atlaDrop.has(link)) why = 'claude_atla';

    if (why) {
      removed.push({ link, why });
      if (why === 'claude_atla') {
        try {
          fs.appendFileSync(
            atlandiPath,
            JSON.stringify({
              link,
              reason: 'claude_atla',
              at: new Date().toISOString(),
              baslik: o.baslik || '',
              kaynak: o.kaynak || '',
              eklenme_zamani: o.eklenme_zamani || '',
            }) + '\n'
          );
        } catch (e) {
          console.log('[kuyruk_atla_archive] append failed: ' + e.message);
        }
      }
      continue;
    }
    kept.push(t);
  } catch (e) {
    kept.push(t);
  }
}

const kalan_icerik = kept.length ? kept.join('\n') + '\n' : '';
console.log(
  '[kuyruk_selective_clear] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      published: [...published],
      prefilter_dropped: [...prefilterDrop],
      atla_dropped: [...atlaDrop],
      removed_count: removed.length,
      removed_reasons: removed.reduce((acc, x) => {
        acc[x.why] = (acc[x.why] || 0) + 1;
        return acc;
      }, {}),
      kept_count: kept.length,
    })
);

return [{ json: { kalan_icerik, removed_count: removed.length, kept_count: kept.length } }];
'''


def export_workflow() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-asama50.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={WF_ID}', '--output=/tmp/wf-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-pre.json', str(out)], check=True)
    return out


def patch_workflow(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    hl = by['Haber Listesini Hazirla']['parameters']['jsCode']
    if 'sourcePriority' not in hl:
        marker = 'const seenInQueue = new Set();'
        if marker not in hl:
            raise SystemExit('Haber Listesini Hazirla: seenInQueue marker not found')
        hl = hl.replace(marker, HABER_LISTESI_SORT_SNIPPET + '\n' + marker)
    by['Haber Listesini Hazirla']['parameters']['jsCode'] = hl

    by['Yazilari Ayristir']['parameters']['jsCode'] = AYRISTIR_CODE
    by['Kuyruk Temizle Bos Icerik']['parameters']['jsCode'] = QUEUE_CLEAR_CODE

    out = BACKUP / 'haber-yayinlama-asama50-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_workflow(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-asama50.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-asama50.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'], check=False)


def verify() -> None:
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    hl = by['Haber Listesini Hazirla']['parameters']['jsCode']
    ay = by['Yazilari Ayristir']['parameters']['jsCode']
    qc = by['Kuyruk Temizle Bos Icerik']['parameters']['jsCode']
    assert 'sourcePriority' in hl, 'missing queue sort'
    assert 'BATCH_LIMIT = 5' in hl, 'BATCH_LIMIT changed unexpectedly'
    assert 'atla_dropped_links' in ay, 'missing atla tracking'
    assert 'claude_atla' in qc and 'atlandi.jsonl' in qc, 'missing atla queue clear'
    print('VERIFY OK')


def main() -> None:
    src = export_workflow()
    patched = patch_workflow(src)
    import_workflow(patched)
    for _ in range(30):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(2)
    verify()


if __name__ == '__main__':
    main()
