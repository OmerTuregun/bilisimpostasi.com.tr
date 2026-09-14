#!/usr/bin/env python3
"""Fix republish: durable published-links index + enable fs + harden prefilter."""
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
COMPOSE = ROOT / 'n8n/docker-compose.yml'

HABER_LISTESI_CODE = r'''const BATCH_LIMIT = 5;
const MIN_TITLE_LEN = 12;
const MIN_SUMMARY_LEN = 20;

const BLOCK_PATTERNS = [
  /\b(sponsored|advertorial|affiliate|giveaway|coupon|deals?\s+roundup)\b/i,
  /\b(celebrity|kardashian|royal\s+family|dating\s+rumor)\b/i,
  /\b(nfl|nba|premier\s+league|match\s+result|transfer\s+rumor)\b/i,
  /indirim\s+kodu|kupon\s+kodu|reklam\s+ilan|magazin\s+haber|skandal\s+foto/i,
  /clickbait|you\s+won't\s+believe|shocking\s+truth/i,
  /^\s*(watch|video|gallery|photos)\s*:/i,
];

function normalizeLink(link) {
  let u = String(link || '').trim();
  if (!u) return '';
  try {
    const url = new URL(u);
    let host = url.hostname.toLowerCase();
    if (host.startsWith('www.')) host = host.slice(4);
    let path = url.pathname.replace(/\/+$/, '');
    const drop = new Set(['utm_source','utm_medium','utm_campaign','utm_term','utm_content','fbclid','gclid','ref','source']);
    const kept = [];
    url.searchParams.forEach((v, k) => {
      if (!drop.has(k.toLowerCase()) && !k.toLowerCase().startsWith('utm_')) {
        kept.push([k, v]);
      }
    });
    kept.sort((a, b) => a[0].localeCompare(b[0]));
    const q = kept.map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(v)).join('&');
    return url.protocol.replace(':','') + '://' + host + path + (q ? '?' + q : '');
  } catch (e) {
    return u.replace(/\/+$/, '');
  }
}

function normTitle(t) {
  return String(t || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function titleSimilar(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  if (a.length < 16 || b.length < 16) return false;
  if (a.includes(b) || b.includes(a)) return true;
  // token overlap
  const ta = new Set(a.split(' ').filter((w) => w.length > 2));
  const tb = new Set(b.split(' ').filter((w) => w.length > 2));
  if (!ta.size || !tb.size) return false;
  let inter = 0;
  for (const w of ta) if (tb.has(w)) inter += 1;
  const overlap = inter / Math.min(ta.size, tb.size);
  return overlap >= 0.78;
}

function prefilterReason(m) {
  const title = String(m.baslik || '').trim();
  const ozet = String(m.ozet || '').trim();
  const link = normalizeLink(m.link);
  if (!link || !/^https?:\/\//i.test(link)) return 'bad_link';
  if (title.length < MIN_TITLE_LEN) return 'short_title';
  if (ozet.length > 0 && ozet.length < MIN_SUMMARY_LEN) return 'short_summary';
  for (const re of BLOCK_PATTERNS) {
    if (re.test(title) || re.test(ozet)) return 'blocked_keyword';
  }
  return '';
}

const publishedLinks = new Set();
const publishedTitles = [];
const fs = require('fs');
const postsDir = '/home/node/site/src/content/posts/tr';
const publishedIndex = '/home/node/site/src/content/_queue/published-links.jsonl';

try {
  if (fs.existsSync(publishedIndex)) {
    for (const line of fs.readFileSync(publishedIndex, 'utf8').split('\n')) {
      const t = line.trim();
      if (!t) continue;
      try {
        const o = JSON.parse(t);
        const n = normalizeLink(o.link || o);
        if (n) publishedLinks.add(n);
      } catch (e) {
        const n = normalizeLink(t.replace(/^"|"$/g, ''));
        if (n) publishedLinks.add(n);
      }
    }
  }
} catch (e) {
  console.log('[haber_listesi] published-links index read failed: ' + e.message);
}

try {
  if (fs.existsSync(postsDir)) {
    for (const f of fs.readdirSync(postsDir)) {
      if (!f.endsWith('.md')) continue;
      const text = fs.readFileSync(`${postsDir}/${f}`, 'utf8');
      const km = text.match(/^kaynak:\s*"(.*)"\s*$/m);
      if (km && km[1]) publishedLinks.add(normalizeLink(km[1]));
      const tm = text.match(/^title:\s*"(.*)"\s*$/m);
      if (tm && tm[1]) publishedTitles.push(normTitle(tm[1]));
    }
  }
} catch (e) {
  console.log('[haber_listesi] published posts scan failed: ' + e.message);
}

console.log(
  '[haber_listesi_dedupe] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      published_links: publishedLinks.size,
      published_titles: publishedTitles.length,
      fs_ok: publishedLinks.size > 0,
    })
);

const satirlar = String($json.data || '')
  .trim()
  .split('\n')
  .filter((s) => s.trim().length > 0);

const makaleler = [];
for (const s of satirlar) {
  try {
    makaleler.push(JSON.parse(s));
  } catch (e) {}
}

const seenInQueue = new Set();
const prefilterDropped = [];
const candidates = [];

for (const m of makaleler) {
  const link = normalizeLink(m.link);
  if (!link) continue;
  if (seenInQueue.has(link)) {
    prefilterDropped.push({ link, reason: 'queue_dup' });
    continue;
  }
  seenInQueue.add(link);

  if (publishedLinks.has(link)) {
    prefilterDropped.push({ link, reason: 'already_published' });
    continue;
  }

  const tnorm = normTitle(m.baslik || '');
  if (tnorm && publishedTitles.some((pt) => titleSimilar(tnorm, pt))) {
    prefilterDropped.push({ link, reason: 'title_dup' });
    continue;
  }

  const reason = prefilterReason(m);
  if (reason) {
    prefilterDropped.push({ link, reason });
    continue;
  }
  candidates.push(m);
}

const batch = candidates.slice(0, BATCH_LIMIT);

console.log(
  '[haber_listesi_p0] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      queue_total: makaleler.length,
      prefilter_dropped: prefilterDropped.length,
      prefilter_reasons: prefilterDropped.reduce((acc, x) => {
        acc[x.reason] = (acc[x.reason] || 0) + 1;
        return acc;
      }, {}),
      candidates: candidates.length,
      batch_to_claude: batch.length,
      batch_limit: BATCH_LIMIT,
    })
);

const prefilter_dropped_links = prefilterDropped.map((x) => x.link);

return batch.map((m, idx) => ({
  json: {
    baslik: m.baslik || '',
    ozet: m.ozet || '',
    link: m.link || '',
    kaynak: m.kaynak || '',
    prefilter_dropped_links: idx === 0 ? prefilter_dropped_links : undefined,
    batch_meta:
      idx === 0
        ? {
            queue_total: makaleler.length,
            batch_limit: BATCH_LIMIT,
            sent_to_claude: batch.length,
            prefilter_dropped: prefilterDropped.length,
            published_links: publishedLinks.size,
          }
        : undefined,
  },
}));
'''

# Append published links after frontmatter (runs once per post item via executeCommand or code)
PUBLISHED_APPEND_CODE = r'''const fs = require('fs');
const path = '/home/node/site/src/content/_queue/published-links.jsonl';

function normalizeLink(link) {
  let u = String(link || '').trim();
  if (!u) return '';
  try {
    const url = new URL(u);
    let host = url.hostname.toLowerCase();
    if (host.startsWith('www.')) host = host.slice(4);
    const p = url.pathname.replace(/\/+$/, '');
    return url.protocol.replace(':','') + '://' + host + p;
  } catch (e) {
    return u.replace(/\/+$/, '');
  }
}

const existing = new Set();
try {
  if (fs.existsSync(path)) {
    for (const line of fs.readFileSync(path, 'utf8').split('\n')) {
      const t = line.trim();
      if (!t) continue;
      try {
        const o = JSON.parse(t);
        existing.add(normalizeLink(o.link || ''));
      } catch (e) {}
    }
  }
} catch (e) {}

const out = [];
for (const item of $input.all()) {
  const j = item.json || {};
  const link = normalizeLink(j.link || j.kaynak || '');
  if (link && !existing.has(link)) {
    existing.add(link);
    try {
      fs.appendFileSync(path, JSON.stringify({ link, ts: new Date().toISOString() }) + '\n', 'utf8');
    } catch (e) {
      console.log('[published_links_append] fail: ' + e.message);
    }
  }
  out.push({ json: j });
}
return out;
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-dedupe.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-dedupe-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-dedupe-pre.json', str(out)], check=True)
    return out


def patch_compose_fs() -> None:
    text = COMPOSE.read_text(encoding='utf-8')
    if 'NODE_FUNCTION_ALLOW_BUILTIN' in text:
        print('compose already has NODE_FUNCTION_ALLOW_BUILTIN')
        return
    needle = "      N8N_RESTRICT_FILE_ACCESS_TO: /home/node/site;/home/node/.n8n-files;/home/node/data\n"
    insert = (
        needle
        + "      # Allow Code nodes to read posts for already_published dedupe\n"
        + "      NODE_FUNCTION_ALLOW_BUILTIN: fs\n"
    )
    if needle not in text:
        raise SystemExit('compose needle not found')
    COMPOSE.write_text(text.replace(needle, insert), encoding='utf-8')
    print('compose patched for fs')


def patch_workflow(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    conn = wf['connections']
    names = {n['name'] for n in wf['nodes']}

    by['Haber Listesini Hazirla']['parameters']['jsCode'] = HABER_LISTESI_CODE

    # Insert Published Links Append between Dosya Adi Dogrula and Markdown Dosyasina Cevir
    # Current: Dosya Adi Dogrula -> Markdown Dosyasina Cevir
    pos = by['Dosya Adi Dogrula']['position']
    node = {
        'parameters': {'jsCode': PUBLISHED_APPEND_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [pos[0] + 220, pos[1]],
        'id': 'published-links-append-0001',
        'name': 'Published Links Append',
    }
    if 'Published Links Append' in names:
        wf['nodes'] = [n for n in wf['nodes'] if n['name'] != 'Published Links Append']
    wf['nodes'].append(node)

    # Rewire: whoever pointed to Markdown Dosyasina Cevir from Dosya Adi Dogrula
    # Find inbound to Markdown
    for src_name, outs in list(conn.items()):
        main = outs.get('main') or []
        for bi, branch in enumerate(main):
            for ei, edge in enumerate(branch or []):
                if edge.get('node') == 'Markdown Dosyasina Cevir' and src_name == 'Dosya Adi Dogrula':
                    conn[src_name]['main'][bi][ei] = {
                        'node': 'Published Links Append',
                        'type': 'main',
                        'index': 0,
                    }
    conn['Published Links Append'] = {
        'main': [[{'node': 'Markdown Dosyasina Cevir', 'type': 'main', 'index': 0}]]
    }

    # Also normalize links in queue clear
    clear = by['Kuyruk Temizle Bos Icerik']['parameters']['jsCode']
    if 'function normalizeLink' not in clear:
        clear = clear.replace(
            'const published = new Set();\ntry {\n  for (const it of $(\'Frontmatter Olustur\').all()) {\n    const link = String((it.json && it.json.link) || \'\').trim();\n    if (link) published.add(link);\n  }\n} catch (e) {}',
            '''function normalizeLink(link) {
  return String(link || '').trim().replace(/\/+$/, '');
}
const published = new Set();
try {
  for (const it of $('Frontmatter Olustur').all()) {
    const link = normalizeLink((it.json && it.json.link) || '');
    if (link) published.add(link);
  }
} catch (e) {}'''
        )
        clear = clear.replace(
            "const link = String(o.link || '').trim();\n    if (link && (published.has(link) || prefilterDrop.has(link))) {",
            "const link = normalizeLink(o.link || '');\n    if (link && (published.has(link) || prefilterDrop.has(normalizeLink(link)))) {",
        )
        by['Kuyruk Temizle Bos Icerik']['parameters']['jsCode'] = clear

    out = BACKUP / 'haber-yayinlama-dedupe-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_and_restart(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-dedupe.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-dedupe.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )
    # recreate n8n with new env
    subprocess.run(
        ['docker', 'compose', '-f', str(COMPOSE), 'up', '-d', 'n8n'],
        cwd=str(ROOT / 'n8n'),
        check=True,
    )
    for _ in range(45):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            print('n8n healthy')
            break
        time.sleep(2)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )


def verify_fs() -> None:
    env = subprocess.check_output(['docker', 'exec', 'agent-n8n', 'printenv', 'NODE_FUNCTION_ALLOW_BUILTIN'], text=True).strip()
    print('NODE_FUNCTION_ALLOW_BUILTIN=', env)
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    assert 'published-links.jsonl' in by['Haber Listesini Hazirla']['parameters']['jsCode']
    assert 'title_dup' in by['Haber Listesini Hazirla']['parameters']['jsCode']
    assert 'Published Links Append' in by
    print('VERIFY OK')


def main() -> None:
    patch_compose_fs()
    pre = export_live()
    print('backup', pre)
    patched = patch_workflow(pre)
    import_and_restart(patched)
    verify_fs()


if __name__ == '__main__':
    main()
