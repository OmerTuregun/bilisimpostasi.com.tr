#!/usr/bin/env python3
"""Filter Email/Telegram/Twitter notifies to truly-new posts only (no republish spam)."""
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

FILTER_CODE = r'''const fs = require('fs');
const postsDir = '/home/node/site/src/content/posts/tr';

function normalizeLink(link) {
  let u = String(link || '').trim();
  if (!u) return '';
  try {
    const url = new URL(u);
    let host = url.hostname.toLowerCase();
    if (host.startsWith('www.')) host = host.slice(4);
    return url.protocol.replace(':', '') + '://' + host + url.pathname.replace(/\/+$/, '');
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

// Map kaynak -> list of filenames on disk
const byLink = new Map();
const titlesOnDisk = [];
try {
  for (const f of fs.readdirSync(postsDir)) {
    if (!f.endsWith('.md')) continue;
    const text = fs.readFileSync(postsDir + '/' + f, 'utf8');
    const km = text.match(/^kaynak:\s*"(.*)"\s*$/m);
    const tm = text.match(/^title:\s*"(.*)"\s*$/m);
    const link = normalizeLink(km && km[1]);
    if (link) {
      if (!byLink.has(link)) byLink.set(link, []);
      byLink.get(link).push(f.replace(/\.md$/, ''));
    }
    if (tm && tm[1]) titlesOnDisk.push({ title: normTitle(tm[1]), slug: f.replace(/\.md$/, '') });
  }
} catch (e) {
  console.log('[notify_filter] disk scan failed: ' + e.message);
}

function titleSimilar(a, b) {
  if (!a || !b) return false;
  if (a === b) return true;
  if (a.length < 16 || b.length < 16) return false;
  if (a.includes(b) || b.includes(a)) return true;
  const ta = new Set(a.split(' ').filter((w) => w.length > 2));
  const tb = new Set(b.split(' ').filter((w) => w.length > 2));
  if (!ta.size || !tb.size) return false;
  let inter = 0;
  for (const w of ta) if (tb.has(w)) inter += 1;
  return inter / Math.min(ta.size, tb.size) >= 0.78;
}

let posts = [];
try {
  posts = $('Frontmatter Olustur').all().map((i) => i.json).filter((p) => p && p.baslik && p.dosya_adi);
} catch (e) {
  posts = [];
}

const kept = [];
const dropped = [];

for (const p of posts) {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const link = normalizeLink(p.link || p.kaynak || '');
  const titleN = normTitle(p.baslik || '');

  // Same kaynak already has another older/other slug on disk → republish, skip notify
  const siblings = link ? (byLink.get(link) || []) : [];
  const otherSlugs = siblings.filter((s) => s !== slug);
  if (otherSlugs.length > 0) {
    dropped.push({ slug, reason: 'kaynak_already_published', others: otherSlugs.slice(0, 3) });
    continue;
  }

  // Near-identical title already exists under a different slug
  const titleHit = titlesOnDisk.find((t) => t.slug !== slug && titleSimilar(titleN, t.title));
  if (titleHit) {
    dropped.push({ slug, reason: 'title_already_published', other: titleHit.slug });
    continue;
  }

  kept.push(p);
}

console.log(
  '[notify_filter] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      input: posts.length,
      kept: kept.length,
      dropped: dropped.length,
      reasons: dropped,
    })
);

if (!kept.length) {
  return [{ json: { posts: [], post_count: 0, notify_skip_all: true } }];
}

return [{ json: { posts: kept, post_count: kept.length, notify_skip_all: false } }];
'''

ABONE_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
const lines = posts.map((p, i) => `${i + 1}. ${p.baslik} - https://bilisimpostasi.com.tr/posts/${p.dosya_adi}/`);
const text = posts.length ? `🆕 Yeni yazılar:\n\n${lines.join('\n')}` : '';
return [{ json: { text, post_count: posts.length } }];
'''

EMAIL_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
const lines = posts.map((p, i) => {
  const title = (p.baslik || p.title || '').replace(/\n/g, ' ');
  const slug = p.dosya_adi || '';
  const link = slug ? `https://bilisimpostasi.com.tr/posts/${slug}/` : (p.link || '');
  return `${i + 1}. ${title} - ${link}`;
});
return [{ json: { text: lines.join('\n'), post_count: posts.length } }];
'''

TWITTER_CODE = r'''const CYCLE_MINUTES = 180;
const MIN_GAP_MINUTES = 18;
const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);

function normalizeLink(link) {
  let u = String(link || '').trim();
  if (!u) return '';
  try {
    const url = new URL(u);
    let host = url.hostname.toLowerCase();
    if (host.startsWith('www.')) host = host.slice(4);
    return url.protocol.replace(':', '') + '://' + host + url.pathname.replace(/\/+$/, '');
  } catch (e) {
    return u.replace(/\/+$/, '');
  }
}

/** Random offsets in [0, window] with pairwise min gap. Sorted ascending. */
function randomOffsets(n, windowMin, minGap) {
  if (n <= 0) return [];
  if (n === 1) return [Math.random() * Math.min(12, windowMin * 0.15)];
  const reserved = (n - 1) * minGap;
  if (reserved >= windowMin) {
    const step = windowMin / n;
    return Array.from({ length: n }, (_, i) => i * step);
  }
  const slack = windowMin - reserved;
  const pts = Array.from({ length: n }, () => Math.random() * slack).sort((a, b) => a - b);
  return pts.map((p, i) => p + i * minGap);
}

const n = posts.length;
if (n === 0) {
  return [{ json: { twitter_queue_skip: true, message: 'No new posts to enqueue' } }];
}

const offsets = randomOffsets(n, CYCLE_MINUTES, MIN_GAP_MINUTES);
const now = Date.now();

return posts.map((p, i) => {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const summary = String(p.ozet || p.description || '').trim();
  const firstSentence = summary.split(/(?<=[.!?…])\s+/)[0] || summary;
  const kaynak = normalizeLink(p.link || p.kaynak || '');
  const offsetMin = offsets[i];
  return {
    json: {
      post_slug: slug,
      post_title: p.baslik,
      post_summary: firstSentence.slice(0, 280),
      post_link: `https://bilisimpostasi.com.tr/posts/${slug}/`,
      kategori: p.kategori || 'Teknoloji',
      kaynak_url: kaynak,
      scheduled_at: new Date(now + offsetMin * 60 * 1000).toISOString(),
      schedule_index: i,
      schedule_offset_min: Math.round(offsetMin * 10) / 10,
      schedule_min_gap_min: MIN_GAP_MINUTES,
      schedule_window_min: CYCLE_MINUTES,
    },
  };
});
'''

OWNER_TG_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
const lines = posts.map((p, i) => {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  return `${i + 1}. ${p.baslik || slug}\nhttps://bilisimpostasi.com.tr/posts/${slug}/`;
});
if (!lines.length) {
  return [{ json: { notify_skip: true, channel: 'telegram_owner' } }];
}
const text = '📰 Yeni yazı yayınlandı!\n\n' + lines.join('\n\n');
return [{
  json: {
    channel: 'telegram_owner',
    payload: { chat_id: '6675249884', text },
    scheduled_at: new Date().toISOString(),
    dosya_adi: posts[0].dosya_adi,
    baslik: posts[0].baslik,
  },
}];
'''

# Twitter insert: skip if slug already exists OR same kaynak already queued/notified
TWITTER_INSERT_QUERY = r"""={{
(() => {
  const slug = String($json.post_slug || '').replace(/'/g, "''");
  const title = String($json.post_title || '').replace(/'/g, "''");
  const summary = String($json.post_summary || '').replace(/'/g, "''");
  const link = String($json.post_link || '').replace(/'/g, "''");
  const kat = String($json.kategori || '').replace(/'/g, "''");
  const scheduled = String($json.scheduled_at || '');
  if ($json.twitter_queue_skip) return 'SELECT 1 WHERE false;';
  return `INSERT INTO twitter_queue (post_slug, post_title, post_summary, post_link, kategori, status, scheduled_at)
SELECT '${slug}', '${title}', '${summary}', '${link}', '${kat}', 'pending', '${scheduled}'::timestamptz
WHERE NOT EXISTS (
  SELECT 1 FROM twitter_queue t
  WHERE t.post_slug = '${slug}'
     OR t.post_link = '${link}'
     OR lower(t.post_title) = lower('${title}')
);`;
})()
}}"""


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-notify-dedupe.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-nd-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-nd-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    conn = wf['connections']
    names = {n['name'] for n in wf['nodes']}

    # Replace Telegram Icin Yazilari Topla with filter node (keep downstream TG path)
    # Add Yeni Postlari Filtrele; rewire Deploy success branch

    filter_node = {
        'parameters': {'jsCode': FILTER_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [2000, 200],
        'id': 'notify-filter-new-posts-0001',
        'name': 'Yeni Postlari Filtrele',
    }
    if 'Yeni Postlari Filtrele' in names:
        wf['nodes'] = [n for n in wf['nodes'] if n['name'] != 'Yeni Postlari Filtrele']
    wf['nodes'].append(filter_node)

    by['Abone Mesajini Hazirla']['parameters']['jsCode'] = ABONE_CODE
    by['Email Bildirim Hazirla']['parameters']['jsCode'] = EMAIL_CODE
    by['Twitter Kuyruk Hazirla']['parameters']['jsCode'] = TWITTER_CODE
    by['Owner TG Kuyruk Hazirla']['parameters']['jsCode'] = OWNER_TG_CODE
    by['Twitter Kuyruga Yaz']['parameters']['query'] = TWITTER_INSERT_QUERY

    # Deploy Basarili Mi true -> filter, then fan-out
    # Current: Deploy Basarili Mi -> [Telegram Icin Yazilari Topla, Abone, Email, Twitter]
    true_branch = [
        {'node': 'Yeni Postlari Filtrele', 'type': 'main', 'index': 0},
    ]
    # Keep false branch as-is
    existing = conn.get('Deploy Basarili Mi', {}).get('main', [[], []])
    false_branch = existing[1] if len(existing) > 1 else []
    conn['Deploy Basarili Mi'] = {'main': [true_branch, false_branch]}

    conn['Yeni Postlari Filtrele'] = {
        'main': [[
            {'node': 'Owner TG Kuyruk Hazirla', 'type': 'main', 'index': 0},
            {'node': 'Abone Mesajini Hazirla', 'type': 'main', 'index': 0},
            {'node': 'Email Bildirim Hazirla', 'type': 'main', 'index': 0},
            {'node': 'Twitter Kuyruk Hazirla', 'type': 'main', 'index': 0},
        ]]
    }

    # Owner TG path: was Telegram Icin -> Owner TG. Now filter -> Owner TG -> SQL -> Kuyruk Temizle
    # Ensure Owner TG still leads to queue clear (critical path)
    # Previously: Owner TG Kuyruga Yaz -> Kuyruk Temizle
    # Abone/Email/Twitter are side paths — OK
    # Remove old Telegram Icin Yazilari Topla from critical path if still connected
    conn.pop('Telegram Icin Yazilari Topla', None)

    # If Owner TG Kuyruga Yaz doesn't connect to Kuyruk Temizle, fix it
    if 'Owner TG Kuyruga Yaz' in by:
        conn['Owner TG Kuyruk Hazirla'] = {
            'main': [[{'node': 'Owner TG Kuyruk SQL', 'type': 'main', 'index': 0}]]
        }
        # keep existing Owner TG SQL -> Yaz -> Temizle if present

    out = BACKUP / 'haber-yayinlama-notify-dedupe-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-nd.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-nd.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(2)
    for wid in [WF_ID, 'bsqTiPswUyJSDCsC', 'notifyKuyrukIsleyici01', 'contactFormWebhook01', 'twKuyrukIsleyici01']:
        subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={wid}', '--active=true'],
            check=False,
            capture_output=True,
        )
    print('n8n restarted + activated')


def cleanup_twitter_orphans() -> None:
    # Remove test row + any slug without a TR file
    tr = {p.stem for p in (ROOT / 'site/src/content/posts/tr').glob('*.md')}
    rows = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         'SELECT id, post_slug FROM twitter_queue;'],
        text=True,
    ).strip().splitlines()
    del_ids = []
    for line in rows:
        if not line.strip():
            continue
        id_, slug = line.split('|', 1)
        if slug not in tr or slug.startswith('ntfy-test'):
            del_ids.append(id_)
    if del_ids:
        ids = ','.join(del_ids)
        out = subprocess.check_output(
            ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-c',
             f'DELETE FROM twitter_queue WHERE id IN ({ids}) RETURNING id, post_slug;'],
            text=True,
        )
        print(out)
    else:
        print('no twitter orphans')


def main() -> None:
    cleanup_twitter_orphans()
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    by = {n['name']: n for n in json.loads(raw)}
    assert 'Yeni Postlari Filtrele' in by
    assert 'Yeni Postlari Filtrele' in by['Twitter Kuyruk Hazirla']['parameters']['jsCode']
    assert 'NOT EXISTS' in by['Twitter Kuyruga Yaz']['parameters']['query']
    print('VERIFY OK')


if __name__ == '__main__':
    main()
