#!/usr/bin/env python3
"""7-day Unsplash cover cooldown via used_cover_photos table.

Diagnosis: Unsplash Arama used per_page=1 and Gorsel Bilgi Hazirla always
took results[0] — same query → same top photo → homepage repeats.

Fix:
1) per_page=20
2) Before pick: load photo IDs used in last 7 days (+ purge >30d)
3) Pick first result not used in 7d (batch-aware); if pool exhausted,
   reuse oldest-in-window and log warning
4) INSERT selected id (once per TR cover; EN shares same asset)
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
MIGRATION = ROOT / 'n8n/migrations/20260821_create_used_cover_photos.sql'
WF_ID = 'zVyc6gzToDe5mhc2'
PG_CRED = {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'}

STASH_CODE = r'''// Stash Unsplash search payloads for after cooldown SELECT (which replaces items).
const staticData = $getWorkflowStaticData('global');
const anahtar = (() => {
  try { return $('Anahtar Kelime Cikar').all(); } catch (e) { return []; }
})();

staticData.coverUnsplashBatch = $input.all().map((item, idx) => ({
  results: item.json.results || [],
  src: (anahtar[idx] && anahtar[idx].json) || {},
}));

// Pass through so Postgres node still runs (input ignored by query).
return [{ json: { cover_stash_count: staticData.coverUnsplashBatch.length } }];
'''

SELECT_CODE = r'''const staticData = $getWorkflowStaticData('global');
const batch = staticData.coverUnsplashBatch || [];
// Clear early so a retry does not reuse stale stash mid-run accidentally
staticData.coverUnsplashBatch = null;

const usedAtById = new Map();
for (const row of $input.all()) {
  const j = row.json || {};
  const id = String(j.unsplash_photo_id || j.unsplash_photo_id || '').trim();
  // postgres may return lowercase keys
  const pid = String(j.unsplash_photo_id || '').trim();
  const photoId = pid || String(j.unsplash_photo_id || '').trim();
  const usedAt = j.used_at || j.usedAt || null;
  if (photoId) usedAtById.set(photoId, usedAt);
}

// Re-parse properly (n8n postgres column names)
usedAtById.clear();
for (const row of $input.all()) {
  const j = row.json || {};
  const photoId = String(j.unsplash_photo_id || '').trim();
  if (!photoId) continue;
  usedAtById.set(photoId, j.used_at || null);
}

const batchUsed = new Set();
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;
const now = Date.now();

function isBlocked(photoId) {
  if (!photoId) return true;
  if (batchUsed.has(photoId)) return true;
  if (!usedAtById.has(photoId)) return false;
  const raw = usedAtById.get(photoId);
  const t = raw ? new Date(raw).getTime() : NaN;
  if (!Number.isFinite(t)) return true; // treat unknown as blocked
  return (now - t) < COOLDOWN_MS;
}

function buildImageUrl(photo) {
  const rawUrl = (photo.urls && (photo.urls.regular || photo.urls.small)) || '';
  if (!rawUrl) return '';
  return (
    rawUrl.replace(/([?&])w=\d+/g, '').replace(/([?&])q=\d+/g, '') +
    (rawUrl.includes('?') ? '&' : '?') +
    'w=1200&q=80&fm=jpg&fit=max'
  );
}

function slugify(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ı/g, 'i')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

const out = [];

for (let idx = 0; idx < batch.length; idx++) {
  const entry = batch[idx] || {};
  const results = Array.isArray(entry.results) ? entry.results : [];
  const src = entry.src || {};

  let chosen = null;
  let chosenRank = -1;
  let poolExhausted = false;

  for (let r = 0; r < results.length; r++) {
    const cand = results[r] || {};
    const id = String(cand.id || '').trim();
    if (!id) continue;
    if (isBlocked(id)) continue;
    chosen = cand;
    chosenRank = r;
    break;
  }

  if (!chosen && results.length) {
    // Pool exhausted: reuse the candidate whose previous use is oldest (cooldown nearest to expiry)
    poolExhausted = true;
    let best = null;
    let bestRank = -1;
    let bestUsed = Infinity;
    for (let r = 0; r < results.length; r++) {
      const cand = results[r] || {};
      const id = String(cand.id || '').trim();
      if (!id || batchUsed.has(id)) continue;
      const raw = usedAtById.get(id);
      const t = raw ? new Date(raw).getTime() : 0;
      if (t < bestUsed) {
        bestUsed = t;
        best = cand;
        bestRank = r;
      }
    }
    // If all blocked by batchUsed only, fall back to results[0]
    chosen = best || results[0];
    chosenRank = best ? bestRank : 0;
    console.log(
      '[cover_pool_exhausted] ' +
        JSON.stringify({
          ts: new Date().toISOString(),
          query: src.gorsel_query || '',
          baslik: src.baslik || '',
          results: results.length,
          reused_id: chosen && chosen.id,
          reused_rank: chosenRank,
          message: 'havuz tükendi, en eski tekrar kullanıldı',
        })
    );
  }

  const photo = chosen || {};
  const photoId = String(photo.id || '').trim();
  if (photoId) batchUsed.add(photoId);

  const imageUrl = buildImageUrl(photo);
  const downloadLocation = (photo.links && photo.links.download_location) || '';
  const userName = (photo.user && photo.user.name) || '';
  const userLink = (photo.user && photo.user.links && photo.user.links.html) || '';
  const baslik = src.baslik || 'post';
  const slug = slugify(baslik);
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const dosya_adi = slug.slice(0, 50) + '-' + ts + '.jpg';
  const postSlug = `${slug}-${ts}`;

  console.log(
    '[cover_selected] ' +
      JSON.stringify({
        ts: new Date().toISOString(),
        photo_id: photoId,
        rank: chosenRank,
        pool_exhausted: poolExhausted,
        query: src.gorsel_query || '',
        post_slug: postSlug,
      })
  );

  out.push({
    json: {
      ...src,
      gorsel_query: src.gorsel_query || '',
      gorsel_url: imageUrl,
      gorsel_download_location: downloadLocation,
      gorsel_fotografci: userName,
      gorsel_fotografci_link: userLink
        ? userLink + '?utm_source=bilisimpostasi&utm_medium=referral'
        : '',
      gorsel_kaynak_link: 'https://unsplash.com/?utm_source=bilisimpostasi&utm_medium=referral',
      gorsel_dosya_adi: dosya_adi,
      gorsel_unsplash_id: photoId,
      gorsel_unsplash_alt: photo.alt_description || photo.description || '',
      gorsel_cover_rank: chosenRank,
      gorsel_pool_exhausted: poolExhausted,
      _cover_post_slug: postSlug,
    },
  });
}

return out;
'''

# Fix the buggy duplicate lines in SELECT_CODE - rewrite cleanly
SELECT_CODE = r'''const staticData = $getWorkflowStaticData('global');
const batch = staticData.coverUnsplashBatch || [];
staticData.coverUnsplashBatch = null;

const usedAtById = new Map();
for (const row of $input.all()) {
  const j = row.json || {};
  const photoId = String(j.unsplash_photo_id || '').trim();
  if (!photoId) continue;
  usedAtById.set(photoId, j.used_at || null);
}

const batchUsed = new Set();
const COOLDOWN_MS = 7 * 24 * 60 * 60 * 1000;
const now = Date.now();

function isBlocked(photoId) {
  if (!photoId) return true;
  if (batchUsed.has(photoId)) return true;
  if (!usedAtById.has(photoId)) return false;
  const raw = usedAtById.get(photoId);
  const t = raw ? new Date(raw).getTime() : NaN;
  if (!Number.isFinite(t)) return true;
  return (now - t) < COOLDOWN_MS;
}

function buildImageUrl(photo) {
  const rawUrl = (photo.urls && (photo.urls.regular || photo.urls.small)) || '';
  if (!rawUrl) return '';
  return (
    rawUrl.replace(/([?&])w=\d+/g, '').replace(/([?&])q=\d+/g, '') +
    (rawUrl.includes('?') ? '&' : '?') +
    'w=1200&q=80&fm=jpg&fit=max'
  );
}

function slugify(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ı/g, 'i')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

const out = [];

for (let idx = 0; idx < batch.length; idx++) {
  const entry = batch[idx] || {};
  const results = Array.isArray(entry.results) ? entry.results : [];
  const src = entry.src || {};

  let chosen = null;
  let chosenRank = -1;
  let poolExhausted = false;

  for (let r = 0; r < results.length; r++) {
    const cand = results[r] || {};
    const id = String(cand.id || '').trim();
    if (!id) continue;
    if (isBlocked(id)) continue;
    chosen = cand;
    chosenRank = r;
    break;
  }

  if (!chosen && results.length) {
    poolExhausted = true;
    let best = null;
    let bestRank = -1;
    let bestUsed = Infinity;
    for (let r = 0; r < results.length; r++) {
      const cand = results[r] || {};
      const id = String(cand.id || '').trim();
      if (!id || batchUsed.has(id)) continue;
      const raw = usedAtById.get(id);
      const t = raw ? new Date(raw).getTime() : 0;
      if (t < bestUsed) {
        bestUsed = t;
        best = cand;
        bestRank = r;
      }
    }
    chosen = best || results[0];
    chosenRank = best ? bestRank : 0;
    console.log(
      '[cover_pool_exhausted] ' +
        JSON.stringify({
          ts: new Date().toISOString(),
          query: src.gorsel_query || '',
          baslik: src.baslik || '',
          results: results.length,
          reused_id: chosen && chosen.id,
          reused_rank: chosenRank,
          message: 'havuz tükendi, en eski tekrar kullanıldı',
        })
    );
  }

  const photo = chosen || {};
  const photoId = String(photo.id || '').trim();
  if (photoId) batchUsed.add(photoId);

  const imageUrl = buildImageUrl(photo);
  const downloadLocation = (photo.links && photo.links.download_location) || '';
  const userName = (photo.user && photo.user.name) || '';
  const userLink = (photo.user && photo.user.links && photo.user.links.html) || '';
  const baslik = src.baslik || 'post';
  const slug = slugify(baslik);
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const dosya_adi = slug.slice(0, 50) + '-' + ts + '.jpg';
  const postSlug = `${slug}-${ts}`;

  console.log(
    '[cover_selected] ' +
      JSON.stringify({
        ts: new Date().toISOString(),
        photo_id: photoId,
        rank: chosenRank,
        pool_exhausted: poolExhausted,
        query: src.gorsel_query || '',
        post_slug: postSlug,
      })
  );

  out.push({
    json: {
      ...src,
      gorsel_query: src.gorsel_query || '',
      gorsel_url: imageUrl,
      gorsel_download_location: downloadLocation,
      gorsel_fotografci: userName,
      gorsel_fotografci_link: userLink
        ? userLink + '?utm_source=bilisimpostasi&utm_medium=referral'
        : '',
      gorsel_kaynak_link: 'https://unsplash.com/?utm_source=bilisimpostasi&utm_medium=referral',
      gorsel_dosya_adi: dosya_adi,
      gorsel_unsplash_id: photoId,
      gorsel_unsplash_alt: photo.alt_description || photo.description || '',
      gorsel_cover_rank: chosenRank,
      gorsel_pool_exhausted: poolExhausted,
      _cover_post_slug: postSlug,
    },
  });
}

return out;
'''

# Always return ≥1 row so the next Code node still runs on an empty table.
COOLDOWN_QUERY = """\
WITH cleaned AS (
  DELETE FROM used_cover_photos
  WHERE used_at < now() - interval '30 days'
  RETURNING 1
),
recent AS (
  SELECT unsplash_photo_id, MAX(used_at) AS used_at
  FROM used_cover_photos
  WHERE used_at >= now() - interval '7 days'
  GROUP BY unsplash_photo_id
)
SELECT unsplash_photo_id, used_at FROM recent
UNION ALL
SELECT NULL::text AS unsplash_photo_id, NULL::timestamptz AS used_at
WHERE NOT EXISTS (SELECT 1 FROM recent);
"""

# Fan-out leaf: must not sit in the download chain (empty INSERT output would stall it).
INSERT_QUERY = """\
INSERT INTO used_cover_photos (unsplash_photo_id, photo_url, post_slug)
SELECT
  '{{ $json.gorsel_unsplash_id }}',
  '{{ ($json.gorsel_url || "").replace(/'/g, "''") }}',
  '{{ ($json._cover_post_slug || "").replace(/'/g, "''") }}'
WHERE '{{ $json.gorsel_unsplash_id }}' <> '';
"""


def apply_migration() -> None:
    sql = MIGRATION.read_text(encoding='utf-8')
    subprocess.run(
        ['docker', 'exec', '-i', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n'],
        input=sql,
        text=True,
        check=True,
    )
    print('migration applied')


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-toplu-{stamp}-pre-cover-cooldown.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-cover-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-cover-pre.json', str(out)], check=True)
    return out


def _pos(nodes: list, name: str) -> list[int]:
    n = next(x for x in nodes if x['name'] == name)
    return list(n['position'])


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    nodes = wf['nodes']
    conn = wf['connections']
    by = {n['name']: n for n in nodes}

    # 1) Unsplash per_page = 20
    unsplash = by['Unsplash Arama']
    params = unsplash['parameters']['queryParameters']['parameters']
    found = False
    for p in params:
        if p.get('name') == 'per_page':
            p['value'] = '20'
            found = True
    if not found:
        params.append({'name': 'per_page', 'value': '20'})
    print('Unsplash per_page → 20')

    # Remove old Gorsel Bilgi Hazirla; replace with stash → cooldown → select → record → download
    old_gorsel = by['Gorsel Bilgi Hazirla']
    gx, gy = old_gorsel['position']

    # Rename/reuse Gorsel Bilgi Hazirla as the SELECT code (keep name for Post Verisini Geri Yukle refs)
    # Insert BEFORE it: Kapak Stash + Kapak Cooldown Oku
    # Insert AFTER it: Kapak Kaydet (postgres), then existing Gorseli Indir

    stash = {
        'parameters': {'jsCode': STASH_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [gx - 220, gy],
        'id': 'kapak-stash-' + uuid.uuid4().hex[:8],
        'name': 'Kapak Unsplash Stash',
    }

    cooldown = {
        'parameters': {
            'operation': 'executeQuery',
            'query': COOLDOWN_QUERY,
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [gx - 40, gy],
        'id': 'kapak-cooldown-' + uuid.uuid4().hex[:8],
        'name': 'Kapak Cooldown Oku',
        'credentials': {'postgres': PG_CRED},
        'onError': 'continueRegularOutput',
    }

    old_gorsel['parameters'] = {'jsCode': SELECT_CODE}
    old_gorsel['position'] = [gx + 140, gy]

    record = {
        'parameters': {
            'operation': 'executeQuery',
            'query': INSERT_QUERY,
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [gx + 320, gy],
        'id': 'kapak-kaydet-' + uuid.uuid4().hex[:8],
        'name': 'Kapak Kaydet',
        'credentials': {'postgres': PG_CRED},
        'onError': 'continueRegularOutput',
    }

    # Drop previous versions if re-run
    drop = {'Kapak Unsplash Stash', 'Kapak Cooldown Oku', 'Kapak Kaydet'}
    nodes = [n for n in nodes if n['name'] not in drop]
    nodes.extend([stash, cooldown, record])
    # ensure Gorsel Bilgi still present (already in nodes)
    wf['nodes'] = nodes

    # Rewire: Sonuc Var Mi true → Stash → Cooldown → Gorsel Bilgi → Kaydet → Gorseli Indir
    # false branch unchanged (Gorsel Yok Gecis)
    sv = conn['Sonuc Var Mi']['main']
    # main[0] = true, main[1] = false
    sv[0] = [{'node': 'Kapak Unsplash Stash', 'type': 'main', 'index': 0}]
    conn['Kapak Unsplash Stash'] = {
        'main': [[{'node': 'Kapak Cooldown Oku', 'type': 'main', 'index': 0}]]
    }
    conn['Kapak Cooldown Oku'] = {
        'main': [[{'node': 'Gorsel Bilgi Hazirla', 'type': 'main', 'index': 0}]]
    }
    # Fan-out: record in parallel; download chain keeps full post payload
    conn['Gorsel Bilgi Hazirla'] = {
        'main': [[
            {'node': 'Kapak Kaydet', 'type': 'main', 'index': 0},
            {'node': 'Gorseli Indir', 'type': 'main', 'index': 0},
        ]]
    }
    conn.pop('Kapak Kaydet', None)  # leaf

    out = BACKUP / 'haber-yayinlama-toplu-cover-cooldown-fixed.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(
        ['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-cover-fixed.json'],
        check=True,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-cover-fixed.json'],
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
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            break
        time.sleep(2)
    print('import+publish+restart done')


def verify_live() -> None:
    raw = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f"SELECT nodes::text, connections::text FROM workflow_entity WHERE id='{WF_ID}';",
        ],
        text=True,
    ).strip()
    # nodes|connections — connections may contain | so split once from left for nodes only via json query
    nodes = json.loads(subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';",
        ],
        text=True,
    ).strip())
    by = {n['name']: n for n in nodes}
    assert 'Kapak Unsplash Stash' in by
    assert 'Kapak Cooldown Oku' in by
    assert 'Kapak Kaydet' in by
    assert 'coverUnsplashBatch' in by['Kapak Unsplash Stash']['parameters']['jsCode']
    assert 'cover_pool_exhausted' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    assert 'isBlocked' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    per = None
    for p in by['Unsplash Arama']['parameters']['queryParameters']['parameters']:
        if p.get('name') == 'per_page':
            per = p.get('value')
    assert str(per) == '20', per
    # table exists
    exists = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            "SELECT to_regclass('public.used_cover_photos');",
        ],
        text=True,
    ).strip()
    assert exists == 'used_cover_photos', exists
    print('verify OK: nodes + per_page=20 + table')


def main() -> None:
    apply_migration()
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify_live()


if __name__ == '__main__':
    main()
