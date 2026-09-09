#!/usr/bin/env python3
"""Staggered site publish synced to Twitter queue scheduled_at.

- Haber Yayınlama writes MD to _queue/scheduled/{tr,en}/ (not live posts/)
- Skips immediate site deploy
- Shared random schedule (irregular minutes/seconds) on each post
- notify_queue (TG/email) uses same scheduled_at (per-post / digest at last)
- Twitter Kuyruk Isleyici promotes scheduled → posts/, deploys, then ntfy
"""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
PUB_ID = 'zVyc6gzToDe5mhc2'
TW_ID = 'twKuyrukIsleyici01'

SCHEDULED_TR = '/home/node/site/src/content/_queue/scheduled/tr'
SCHEDULED_EN = '/home/node/site/src/content/_queue/scheduled/en'
HOST_SCHED_TR = ROOT / 'site/src/content/_queue/scheduled/tr'
HOST_SCHED_EN = ROOT / 'site/src/content/_queue/scheduled/en'

DEPLOY_TOKEN = 'b90d2b8f03be758d3b58c5fed9432bd77f58f102ffdae3ec85fbbf9b21d0d2b6'

YENI_FILTER_CODE = r'''const fs = require('fs');
const postsDir = '/home/node/site/src/content/posts/tr';
const CYCLE_MINUTES = 180;
const MIN_GAP_MINUTES = 18;

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

function randomOffsets(n, windowMin, minGap) {
  if (n <= 0) return [];
  if (n === 1) return [5 + Math.random() * 25];
  const reserved = (n - 1) * minGap;
  if (reserved >= windowMin) {
    const step = windowMin / n;
    return Array.from({ length: n }, (_, i) => i * step + Math.random() * Math.min(4, step * 0.3));
  }
  const slack = windowMin - reserved;
  const pts = Array.from({ length: n }, () => Math.random() * slack).sort((a, b) => a - b);
  return pts.map((p, i) => p + i * minGap);
}

/** Avoid round-looking clock times (:00, :10, :30…). */
function stampFromOffset(nowMs, offsetMin) {
  let ms = nowMs + offsetMin * 60 * 1000;
  let d = new Date(ms);
  let sec = 7 + Math.floor(Math.random() * 50); // 7..56
  let min = d.getUTCMinutes();
  if (min % 5 === 0) {
    min = (min + 1 + Math.floor(Math.random() * 3)) % 60;
  }
  d.setUTCMinutes(min, sec, Math.floor(Math.random() * 900));
  return d.toISOString();
}

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
  const siblings = link ? (byLink.get(link) || []) : [];
  const otherSlugs = siblings.filter((s) => s !== slug);
  if (otherSlugs.length > 0) {
    dropped.push({ slug, reason: 'kaynak_already_published', others: otherSlugs.slice(0, 3) });
    continue;
  }
  const titleHit = titlesOnDisk.find((t) => t.slug !== slug && titleSimilar(titleN, t.title));
  if (titleHit) {
    dropped.push({ slug, reason: 'title_already_published', other: titleHit.slug });
    continue;
  }
  kept.push(p);
}

const offsets = randomOffsets(kept.length, CYCLE_MINUTES, MIN_GAP_MINUTES);
const now = Date.now();
kept.forEach((p, i) => {
  p.scheduled_at = stampFromOffset(now, offsets[i]);
  p.schedule_offset_min = Math.round(offsets[i] * 10) / 10;
});

console.log(
  '[notify_filter] ' +
    JSON.stringify({
      ts: new Date().toISOString(),
      input: posts.length,
      kept: kept.length,
      dropped: dropped.length,
      schedule: kept.map((p) => ({ slug: p.dosya_adi, at: p.scheduled_at, off: p.schedule_offset_min })),
      reasons: dropped,
    })
);

if (!kept.length) {
  return [{ json: { posts: [], post_count: 0, notify_skip_all: true } }];
}

return [{ json: { posts: kept, post_count: kept.length, notify_skip_all: false } }];
'''

TWITTER_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
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

const n = posts.length;
if (n === 0) {
  return [{ json: { twitter_queue_skip: true, message: 'No new posts to enqueue' } }];
}

return posts.map((p, i) => {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const summary = String(p.ozet || p.description || '').trim();
  const firstSentence = summary.split(/(?<=[.!?…])\s+/)[0] || summary;
  const kaynak = normalizeLink(p.link || p.kaynak || '');
  return {
    json: {
      post_slug: slug,
      post_title: p.baslik,
      post_summary: firstSentence.slice(0, 280),
      post_link: `https://bilisimpostasi.com.tr/posts/${slug}/`,
      kategori: p.kategori || 'Donanım & Çipler',
      kaynak_url: kaynak,
      scheduled_at: p.scheduled_at || new Date().toISOString(),
      schedule_index: i,
      schedule_offset_min: p.schedule_offset_min,
      schedule_window_min: 180,
      schedule_min_gap_min: 18,
    },
  };
});
'''

OWNER_TG_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
if (!posts.length) {
  return [{ json: { notify_skip: true, channel: 'telegram_owner' } }];
}
return posts.map((p) => {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const text = `📰 Yeni yazı yayınlandı!\n\n${p.baslik || slug}\nhttps://bilisimpostasi.com.tr/posts/${slug}/`;
  return {
    json: {
      channel: 'telegram_owner',
      payload: { chat_id: '6675249884', text },
      scheduled_at: p.scheduled_at || new Date().toISOString(),
      dosya_adi: p.dosya_adi,
      baslik: p.baslik,
    },
  };
});
'''

EMAIL_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
if (!posts.length) {
  return [{ json: { notify_skip: true, channel: 'email_digest' } }];
}
const lines = posts.map((p, i) => {
  const title = (p.baslik || p.title || '').replace(/\n/g, ' ');
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  return `${i + 1}. ${title} - https://bilisimpostasi.com.tr/posts/${slug}/`;
});
const times = posts.map((p) => Date.parse(p.scheduled_at || '') || Date.now());
const lastAt = new Date(Math.max(...times)).toISOString();
return [{
  json: {
    channel: 'email_digest',
    payload: { text: lines.join('\n'), post_count: posts.length },
    scheduled_at: lastAt,
  },
}];
'''

ABONE_MSG_CODE = r'''const meta = $('Yeni Postlari Filtrele').first().json || {};
const posts = (meta.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
return [{ json: { posts, post_count: posts.length } }];
'''

ABONE_TG_CODE = r'''const msg = $('Abone Mesajini Hazirla').first().json || {};
const posts = (msg.posts || []).filter((p) => p && p.baslik && p.dosya_adi);
if (!posts.length) {
  return [{ json: { notify_skip: true, channel: 'telegram_subscriber' } }];
}
let rows = [];
try {
  rows = $input.all().map((i) => i.json).filter((j) => j && j.chat_id);
} catch (e) {
  rows = [];
}
if (!rows.length) {
  return [{ json: { notify_skip: true, channel: 'telegram_subscriber', reason: 'no_subscribers' } }];
}
const out = [];
for (const p of posts) {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const text = `🆕 Yeni yazı:\n\n${p.baslik}\nhttps://bilisimpostasi.com.tr/posts/${slug}/`;
  const at = p.scheduled_at || new Date().toISOString();
  for (const r of rows) {
    out.push({
      json: {
        channel: 'telegram_subscriber',
        payload: { chat_id: String(r.chat_id), text },
        scheduled_at: at,
      },
    });
  }
}
return out;
'''

DEPLOY_SKIP_CODE = r'''// Posts stay in _queue/scheduled until Twitter due-time promote + deploy.
return [{
  json: {
    statusCode: 200,
    deferred_publish: true,
    message: 'Site go-live deferred to Twitter/notify scheduled_at',
  },
}];
'''

SITE_PROMOTE_CODE = r'''const fs = require('fs');

const SCHED_TR = '/home/node/site/src/content/_queue/scheduled/tr';
const SCHED_EN = '/home/node/site/src/content/_queue/scheduled/en';
const POSTS_TR = '/home/node/site/src/content/posts/tr';
const POSTS_EN = '/home/node/site/src/content/posts/en';

function join(dir, name) {
  return String(dir).replace(/\/+$/, '') + '/' + String(name).replace(/^\/+/, '');
}

function setPubDate(text, iso) {
  const stamp = new Date(iso).toISOString();
  if (/^pubDate:\s*/m.test(text)) {
    return text.replace(/^pubDate:\s*.*$/m, 'pubDate: ' + stamp);
  }
  return text.replace(/^---\n/, '---\npubDate: ' + stamp + '\n');
}

function promoteOne(slug, scheduledAt) {
  const result = { slug, scheduled_at: scheduledAt, tr: false, en: false, already: false };
  const trSrc = join(SCHED_TR, slug + '.md');
  const enSrc = join(SCHED_EN, slug + '.md');
  const trDst = join(POSTS_TR, slug + '.md');
  const enDst = join(POSTS_EN, slug + '.md');

  if (!fs.existsSync(trSrc) && fs.existsSync(trDst)) {
    result.already = true;
    return result;
  }
  if (fs.existsSync(trSrc)) {
    let t = fs.readFileSync(trSrc, 'utf8');
    t = setPubDate(t, scheduledAt);
    fs.mkdirSync(POSTS_TR, { recursive: true });
    fs.writeFileSync(trDst, t);
    fs.unlinkSync(trSrc);
    result.tr = true;
  }
  if (fs.existsSync(enSrc)) {
    let t = fs.readFileSync(enSrc, 'utf8');
    t = setPubDate(t, scheduledAt);
    fs.mkdirSync(POSTS_EN, { recursive: true });
    fs.writeFileSync(enDst, t);
    fs.unlinkSync(enSrc);
    result.en = true;
  }
  return result;
}

return $input.all().map((item) => {
  const j = item.json || {};
  const slug = String(j.post_slug || '').replace(/\.md$/, '');
  const at = j.scheduled_at || new Date().toISOString();
  let promo = { slug, error: 'empty_slug' };
  if (slug) {
    try {
      promo = promoteOne(slug, at);
    } catch (e) {
      promo = { slug, error: String(e && e.message ? e.message : e) };
    }
  }
  return {
    json: {
      ...j,
      site_promote: promo,
      needs_deploy: !!(promo.tr || promo.en),
    },
  };
});
'''


def export_wf(wf_id: str, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'{label}-{stamp}.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={wf_id}', f'--output=/tmp/{label}.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', f'agent-n8n:/tmp/{label}.json', str(out)], check=True)
    return out


def import_publish(path: Path, wf_id: str) -> None:
    subprocess.run(['docker', 'cp', str(path), f'agent-n8n:/tmp/imp-{wf_id}.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', f'--input=/tmp/imp-{wf_id}.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={wf_id}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={wf_id}', '--active=true'],
        check=False,
    )


def patch_publish(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    conn = wf.setdefault('connections', {})

    # 1) write to scheduled/
    by['Yaziyi Diske Yaz']['parameters']['fileName'] = \
        f'=/{SCHEDULED_TR}/{{{{ $binary.data.fileName }}}}'
    by['EN Dosyayi Yaz']['parameters']['fileName'] = \
        f'=/{SCHEDULED_EN}/{{{{ $binary.data.fileName }}}}'

    # 2) shared schedule + notify/twitter codes
    by['Yeni Postlari Filtrele']['parameters']['jsCode'] = YENI_FILTER_CODE
    by['Twitter Kuyruk Hazirla']['parameters']['jsCode'] = TWITTER_CODE
    by['Owner TG Kuyruk Hazirla']['parameters']['jsCode'] = OWNER_TG_CODE
    by['Email Kuyruk Hazirla']['parameters']['jsCode'] = EMAIL_CODE
    by['Email Bildirim Hazirla']['parameters']['jsCode'] = (
        "const meta = $('Yeni Postlari Filtrele').first().json || {};\n"
        "return [{ json: { post_count: Number(meta.post_count || 0), text: 'deferred' } }];\n"
    )
    by['Abone Mesajini Hazirla']['parameters']['jsCode'] = ABONE_MSG_CODE
    by['Abone TG Kuyruk Hazirla']['parameters']['jsCode'] = ABONE_TG_CODE

    # 3) skip immediate deploy
    skip_id = str(uuid.uuid4())
    skip_node = {
        'id': skip_id,
        'name': 'Yayin Ertele Deploy Atla',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [912, 48],
        'parameters': {'jsCode': DEPLOY_SKIP_CODE},
        'executeOnce': True,
    }
    # remove old deploy from graph connections; keep node for reference but disconnect
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] != 'Yayin Ertele Deploy Atla']
    wf['nodes'].append(skip_node)
    by = {n['name']: n for n in wf['nodes']}

    # EN Sonrasi Birlestir → Yayin Ertele → Deploy Basarili Mi
    conn['EN Sonrasi Birlestir'] = {
        'main': [[{'node': 'Yayin Ertele Deploy Atla', 'type': 'main', 'index': 0}]]
    }
    conn['Yayin Ertele Deploy Atla'] = {
        'main': [[{'node': 'Deploy Basarili Mi', 'type': 'main', 'index': 0}]]
    }
    # Drop inbound to Site Deploy Tetikle if any leftover
    for src, c in list(conn.items()):
        if not c or 'main' not in c:
            continue
        new_main = []
        for branch in c['main']:
            new_main.append([
                x for x in (branch or [])
                if x.get('node') != 'Site Deploy Tetikle'
            ])
        c['main'] = new_main

    out = BACKUP / 'haber-yayinlama-staggered-publish.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def patch_twitter_processor(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    conn = wf.setdefault('connections', {})

    # Poll every 5 minutes for tighter sync with scheduled_at
    cron = by.get('Her 10 Dakika') or by.get('Her 5 Dakika')
    if not cron:
        raise SystemExit('Twitter processor cron node not found')
    old_name = cron['name']
    cron['name'] = 'Her 5 Dakika'
    cron['parameters'] = {
        'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 5}]}
    }
    if old_name in conn and old_name != 'Her 5 Dakika':
        conn['Her 5 Dakika'] = conn.pop(old_name)

    promote_id = str(uuid.uuid4())
    deploy_id = str(uuid.uuid4())
    promote = {
        'id': promote_id,
        'name': 'Site Yayina Al',
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [700, 300],
        'parameters': {'jsCode': SITE_PROMOTE_CODE},
    }
    deploy = {
        'id': deploy_id,
        'name': 'Site Deploy Due',
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [920, 300],
        'parameters': {
            'method': 'POST',
            'url': 'http://172.18.0.1:9876/deploy',
            'sendHeaders': True,
            'headerParameters': {
                'parameters': [
                    {'name': 'Authorization', 'value': f'Bearer {DEPLOY_TOKEN}'},
                ]
            },
            'options': {
                'timeout': 300000,
                'response': {'response': {'fullResponse': True}},
            },
        },
        'onError': 'continueRegularOutput',
        'continueOnFail': True,
    }

    # Insert between Kayit Var Mi (true) → Tweet Metni Olustur
    # Find who feeds Tweet Metni Olustur
    # Current: Kayit Var Mi true → Tweet Metni OR Postgres Sonucu Normalize → ...
    # From earlier: Bekleyen → ... → Tweet Metni → Tek Tek → ntfy...
    # Insert: ... → Site Yayina Al → Site Deploy Due → Tweet Metni

    # Remove existing promote/deploy if re-run
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] not in ('Site Yayina Al', 'Site Deploy Due')]
    wf['nodes'].extend([promote, deploy])

    # Rewire: anything pointing to Tweet Metni Olustur → Site Yayina Al
    for src, c in list(conn.items()):
        if not c or 'main' not in c:
            continue
        for bi, branch in enumerate(c['main']):
            for i, link in enumerate(branch or []):
                if link.get('node') == 'Tweet Metni Olustur':
                    branch[i] = {'node': 'Site Yayina Al', 'type': 'main', 'index': 0}

    conn['Site Yayina Al'] = {
        'main': [[{'node': 'Site Deploy Due', 'type': 'main', 'index': 0}]]
    }
    conn['Site Deploy Due'] = {
        'main': [[{'node': 'Tweet Metni Olustur', 'type': 'main', 'index': 0}]]
    }

    out = BACKUP / 'twitter-kuyruk-isleyici-staggered.json'
    # Keep workflow id/name
    wf['id'] = TW_ID
    wf['name'] = 'Twitter Kuyruk Isleyici'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def check_deploy_auth_header() -> None:
    """Ensure Site Deploy Due uses whatever header the listener expects."""
    src = Path('/usr/local/lib/agent-icerik/deploy-listener.py').read_text()
    print('deploy auth snippet:')
    for line in src.splitlines():
        if 'token' in line.lower() or 'Authorization' in line or 'X-' in line or 'header' in line.lower():
            if line.strip().startswith('#') or len(line.strip()) < 5:
                continue
            print(' ', line.strip()[:120])


def main() -> None:
    HOST_SCHED_TR.mkdir(parents=True, exist_ok=True)
    HOST_SCHED_EN.mkdir(parents=True, exist_ok=True)
    (HOST_SCHED_TR / '.gitkeep').touch()
    (HOST_SCHED_EN / '.gitkeep').touch()

    check_deploy_auth_header()

    pub_pre = export_wf(PUB_ID, 'haber-yayinlama-pre-stagger')
    tw_pre = export_wf(TW_ID, 'twitter-isleyici-pre-stagger')
    print('backups', pub_pre, tw_pre)

    pub_out = patch_publish(pub_pre)
    tw_out = patch_twitter_processor(tw_pre)

    import_publish(pub_out, PUB_ID)
    import_publish(tw_out, TW_ID)

    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            print('n8n healthy')
            break
        time.sleep(2)

    # verify
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{PUB_ID}';"],
        text=True,
    )
    by = {n['name']: n for n in json.loads(raw)}
    assert 'scheduled/tr' in by['Yaziyi Diske Yaz']['parameters']['fileName']
    assert 'Yayin Ertele Deploy Atla' in by
    assert 'stampFromOffset' in by['Yeni Postlari Filtrele']['parameters']['jsCode']
    assert 'p.scheduled_at' in by['Twitter Kuyruk Hazirla']['parameters']['jsCode']

    raw2 = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{TW_ID}';"],
        text=True,
    )
    by2 = {n['name']: n for n in json.loads(raw2)}
    assert 'Site Yayina Al' in by2
    assert 'Site Deploy Due' in by2
    assert by2.get('Her 5 Dakika') or by2.get('Her 10 Dakika')
    print('verify OK')


if __name__ == '__main__':
    main()
