#!/usr/bin/env python3
"""Sync twitter + notify queues behind one site go-live gate.

- Twitter: always deploy when due item is in posts/ (incl. already); skip tweet if not ready.
- Notify: promote from scheduled/ → deploy if needed → send only if posts/ has slug(s).
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
TW_ID = 'twKuyrukIsleyici01'
NF_ID = 'notifyKuyrukIsleyici01'

PROMOTE_CORE = r'''
const fs = require('fs');

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

function liveInPosts(slug) {
  return fs.existsSync(join(POSTS_TR, slug + '.md'));
}
'''

TW_PROMOTE = PROMOTE_CORE + r'''
return $input.all().map((item) => {
  const j = item.json || {};
  const slug = String(j.post_slug || '').replace(/\.md$/, '');
  const at = j.scheduled_at || new Date().toISOString();
  let promo = { slug, error: 'empty_slug' };
  if (slug) {
    try {
      promo = promoteOne(slug, at);
      if (!promo.tr && !promo.en && !promo.already) {
        promo.error = 'not_in_scheduled_or_posts';
      }
    } catch (e) {
      promo = { slug, error: String(e && e.message ? e.message : e) };
    }
  }
  const ready = !!(slug && (promo.tr || promo.en || promo.already) && !promo.error);
  return {
    json: {
      ...j,
      site_promote: promo,
      // already=true olsa bile deploy: www ile posts/ senkron kalsın
      needs_deploy: ready,
      site_ready: ready,
    },
  };
});
'''

NF_PROMOTE = PROMOTE_CORE + r'''
function slugsFromPayload(payload) {
  const text = String((payload && payload.text) || '');
  const out = [];
  const re = /bilisimpostasi\.com\.tr\/(?:en\/)?posts\/([a-z0-9-]+)/gi;
  let m;
  while ((m = re.exec(text))) {
    out.push(String(m[1]).replace(/\/+$/, ''));
  }
  return [...new Set(out)];
}

return $input.all().map((item) => {
  const j = item.json || {};
  const at = j.scheduled_at || new Date().toISOString();
  const slugs = slugsFromPayload(j.payload);
  const promos = [];
  let moved = false;
  let already = false;
  let err = '';
  for (const slug of slugs) {
    try {
      const promo = promoteOne(slug, at);
      promos.push(promo);
      if (promo.tr || promo.en) moved = true;
      if (promo.already) already = true;
    } catch (e) {
      err = String(e && e.message ? e.message : e);
      promos.push({ slug, error: err });
    }
  }
  const missing = slugs.filter((s) => !liveInPosts(s));
  // slug parse edilemezse (beklenmedik payload) gönderme — ertele
  const site_ready = slugs.length > 0 && missing.length === 0 && !err;
  return {
    json: {
      ...j,
      site_slugs: slugs,
      site_missing: missing,
      site_promote: promos,
      needs_deploy: !!(moved || (already && site_ready) || (site_ready && missing.length === 0 && moved === false && already)),
      // deploy when we moved files OR when all live but we want refresh after promote path;
      // simplify: deploy if moved OR (ready and at least one slug)
      site_ready,
    },
  };
}).map((row) => {
  const j = row.json;
  const moved = (j.site_promote || []).some((p) => p && (p.tr || p.en));
  const already = (j.site_promote || []).some((p) => p && p.already);
  j.needs_deploy = !!(j.site_ready && (moved || already));
  return { json: j };
});
'''

# Fix needs_deploy logic - the double map is messy. Rewrite NF_PROMOTE cleaner.
NF_PROMOTE = PROMOTE_CORE + r'''
function slugsFromPayload(payload) {
  const text = String((payload && payload.text) || '');
  const out = [];
  const re = /bilisimpostasi\.com\.tr\/(?:en\/)?posts\/([a-z0-9-]+)/gi;
  let m;
  while ((m = re.exec(text))) {
    out.push(String(m[1]).replace(/\/+$/, ''));
  }
  return [...new Set(out)];
}

return $input.all().map((item) => {
  const j = item.json || {};
  const at = j.scheduled_at || new Date().toISOString();
  const slugs = slugsFromPayload(j.payload);
  const promos = [];
  let moved = false;
  let already = false;
  let err = '';
  for (const slug of slugs) {
    try {
      const promo = promoteOne(slug, at);
      promos.push(promo);
      if (promo.tr || promo.en) moved = true;
      if (promo.already) already = true;
    } catch (e) {
      err = String(e && e.message ? e.message : e);
      promos.push({ slug, error: err });
    }
  }
  const missing = slugs.filter((s) => !liveInPosts(s));
  const site_ready = slugs.length > 0 && missing.length === 0 && !err;
  const needs_deploy = site_ready && (moved || already);
  return {
    json: {
      ...j,
      site_slugs: slugs,
      site_missing: missing,
      site_promote: promos,
      needs_deploy,
      site_ready,
    },
  };
});
'''


def export_wf(wid: str, dest: Path) -> dict:
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={wid}', '--output=/tmp/wf-sync.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-sync.json', str(dest)], check=True)
    data = json.loads(dest.read_text())
    return data[0] if isinstance(data, list) else data


def import_wf(path: Path, wid: str) -> None:
    subprocess.run(['docker', 'cp', str(path), 'agent-n8n:/tmp/wf-sync-in.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-sync-in.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={wid}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={wid}', '--active=true'],
        check=False,
    )


def bool_if(name: str, field: str, position: list[int], nid: str) -> dict:
    return {
        'parameters': {
            'conditions': {
                'options': {
                    'caseSensitive': True,
                    'leftValue': '',
                    'typeValidation': 'loose',
                    'version': 2,
                },
                'conditions': [
                    {
                        'id': nid + '-cond',
                        'leftValue': f'={{{{ $json.{field} }}}}',
                        'rightValue': True,
                        'operator': {
                            'type': 'boolean',
                            'operation': 'true',
                            'singleValue': True,
                        },
                    }
                ],
                'combinator': 'and',
            },
            'options': {},
        },
        'id': nid,
        'name': name,
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': position,
    }


DEPLOY_MERGE = r'''
const prev = $('Site Yayina Al').item.json;
const dep = $input.first().json || {};
return [{
  json: {
    ...prev,
    deploy_http: {
      statusCode: dep.statusCode || dep.status || null,
      ok: Number(dep.statusCode || dep.status || 0) < 400,
    },
  },
}];
'''


def patch_twitter(wf: dict) -> None:
    by = {n['name']: n for n in wf['nodes']}
    by['Site Yayina Al']['parameters']['jsCode'] = TW_PROMOTE

    names = {n['name'] for n in wf['nodes']}
    if 'Deploy Sonrasi Koru' not in names:
        wf['nodes'].append(
            {
                'parameters': {'jsCode': DEPLOY_MERGE},
                'id': 'tw-deploy-merge',
                'name': 'Deploy Sonrasi Koru',
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [680, -80],
            }
        )

    # Site Hazir Mi IF before tweet (after deploy branches merge into Tweet Metni)
    if 'Site Hazir Mi' not in by and 'Site Hazir Mi' not in names:
        wf['nodes'].append(bool_if('Site Hazir Mi', 'site_ready', [900, 0], 'tw-site-ready-if'))
        wf['nodes'].append(
            {
                'parameters': {},
                'id': 'tw-site-wait-noop',
                'name': 'Site Bekleniyor',
                'type': 'n8n-nodes-base.noOp',
                'typeVersion': 1,
                'position': [1120, 120],
            }
        )

    # Rewire: Deploy → merge → Site Hazir Mi; skip-deploy → Site Hazir Mi
    conn = wf['connections']
    conn['Deploy Gerekli Mi'] = {
        'main': [
            [{'node': 'Site Deploy Due', 'type': 'main', 'index': 0}],
            [{'node': 'Site Hazir Mi', 'type': 'main', 'index': 0}],
        ]
    }
    conn['Site Deploy Due'] = {
        'main': [[{'node': 'Deploy Sonrasi Koru', 'type': 'main', 'index': 0}]]
    }
    conn['Deploy Sonrasi Koru'] = {
        'main': [[{'node': 'Site Hazir Mi', 'type': 'main', 'index': 0}]]
    }
    conn['Site Hazir Mi'] = {
        'main': [
            [{'node': 'Tweet Metni Olustur', 'type': 'main', 'index': 0}],
            [{'node': 'Site Bekleniyor', 'type': 'main', 'index': 0}],
        ]
    }


def patch_notify(wf: dict) -> None:
    by = {n['name']: n for n in wf['nodes']}
    names = {n['name'] for n in wf['nodes']}

    if 'Site Yayina Al' not in names:
        wf['nodes'].append(
            {
                'parameters': {'jsCode': NF_PROMOTE},
                'id': 'nf-site-promote',
                'name': 'Site Yayina Al',
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [300, -40],
            }
        )
    else:
        by['Site Yayina Al']['parameters']['jsCode'] = NF_PROMOTE

    if 'Deploy Gerekli Mi' not in names:
        wf['nodes'].append(bool_if('Deploy Gerekli Mi', 'needs_deploy', [520, -40], 'nf-needs-deploy-if'))

    if 'Site Deploy Due' not in names:
        wf['nodes'].append(
            {
                'parameters': {
                    'method': 'POST',
                    'url': 'http://172.18.0.1:9876/deploy',
                    'sendHeaders': True,
                    'headerParameters': {
                        'parameters': [
                            {
                                'name': 'Authorization',
                                'value': 'Bearer ***REMOVED***',
                            }
                        ]
                    },
                    'options': {
                        'timeout': 300000,
                        'response': {'response': {'fullResponse': True}},
                    },
                },
                'id': 'nf-site-deploy',
                'name': 'Site Deploy Due',
                'type': 'n8n-nodes-base.httpRequest',
                'typeVersion': 4.2,
                'position': [740, -160],
            }
        )

    if 'Deploy Sonrasi Koru' not in names:
        wf['nodes'].append(
            {
                'parameters': {'jsCode': DEPLOY_MERGE},
                'id': 'nf-deploy-merge',
                'name': 'Deploy Sonrasi Koru',
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [900, -160],
            }
        )

    if 'Site Hazir Mi' not in names:
        wf['nodes'].append(bool_if('Site Hazir Mi', 'site_ready', [1080, -40], 'nf-site-ready-if'))

    if 'Site Bekliyor SQL' not in names:
        wf['nodes'].append(
            {
                'parameters': {
                    'jsCode': r'''
const j = $input.first().json || {};
const id = Number(j.id);
const miss = (j.site_missing || []).join(',').replace(/'/g, "''").slice(0, 180);
if (!id) {
  return [{ json: { query: 'SELECT 1;', skip: true } }];
}
return [{
  json: {
    query:
      "UPDATE notify_queue SET scheduled_at = now() + interval '5 minutes', " +
      "last_error = 'waiting_site:" + miss + "' " +
      "WHERE id = " + id + " AND status = 'pending';",
  },
}];
'''
                },
                'id': 'nf-site-wait-sql',
                'name': 'Site Bekliyor SQL',
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [1300, 80],
            }
        )

    # Reposition Kanal Sec further right
    for n in wf['nodes']:
        if n['name'] == 'Kanal Sec':
            n['position'] = [1300, -40]
        if n['name'] in ('Email Webhook Gonder', 'Owner Telegram Gonder', 'Abone Telegram Gonder'):
            n['position'][0] = max(n['position'][0], 1520)
        if n['name'] == 'Sonuc SQL Hazirla':
            n['position'] = [1760, -40]
        if n['name'] == 'Durum Guncelle':
            n['position'] = [1980, -40]

    conn = wf['connections']
    # Kayit Var Mi true → Site Yayina Al (was Kanal Sec)
    conn['Kayit Var Mi'] = {
        'main': [
            [{'node': 'Site Yayina Al', 'type': 'main', 'index': 0}],
            [{'node': 'Bos Kuyruk', 'type': 'main', 'index': 0}],
        ]
    }
    conn['Site Yayina Al'] = {
        'main': [[{'node': 'Deploy Gerekli Mi', 'type': 'main', 'index': 0}]]
    }
    conn['Deploy Gerekli Mi'] = {
        'main': [
            [{'node': 'Site Deploy Due', 'type': 'main', 'index': 0}],
            [{'node': 'Site Hazir Mi', 'type': 'main', 'index': 0}],
        ]
    }
    conn['Site Deploy Due'] = {
        'main': [[{'node': 'Deploy Sonrasi Koru', 'type': 'main', 'index': 0}]]
    }
    conn['Deploy Sonrasi Koru'] = {
        'main': [[{'node': 'Site Hazir Mi', 'type': 'main', 'index': 0}]]
    }
    conn['Site Hazir Mi'] = {
        'main': [
            [{'node': 'Kanal Sec', 'type': 'main', 'index': 0}],
            [{'node': 'Site Bekliyor SQL', 'type': 'main', 'index': 0}],
        ]
    }
    conn['Site Bekliyor SQL'] = {
        'main': [[{'node': 'Durum Guncelle', 'type': 'main', 'index': 0}]]
    }


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    BACKUP.mkdir(parents=True, exist_ok=True)

    tw_pre = BACKUP / f'tw-kuyruk-{stamp}-pre-sync.json'
    nf_pre = BACKUP / f'notify-kuyruk-{stamp}-pre-sync.json'
    tw = export_wf(TW_ID, tw_pre)
    nf = export_wf(NF_ID, nf_pre)

    tw2 = deepcopy(tw)
    nf2 = deepcopy(nf)
    patch_twitter(tw2)
    patch_notify(nf2)

    tw_out = BACKUP / f'tw-kuyruk-{stamp}-sync-patched.json'
    nf_out = BACKUP / f'notify-kuyruk-{stamp}-sync-patched.json'
    tw_out.write_text(json.dumps([tw2], ensure_ascii=False), encoding='utf-8')
    nf_out.write_text(json.dumps([nf2], ensure_ascii=False), encoding='utf-8')

    import_wf(tw_out, TW_ID)
    import_wf(nf_out, NF_ID)

    # verify from DB
    for wid, label, needle in [
        (TW_ID, 'twitter', 'needs_deploy: ready'),
        (NF_ID, 'notify', 'waiting_site:'),
    ]:
        raw = subprocess.check_output(
            [
                'docker',
                'exec',
                'agent-n8n-postgres',
                'psql',
                '-U',
                'n8n',
                '-d',
                'n8n',
                '-t',
                '-A',
                '-c',
                f"SELECT nodes::text FROM workflow_entity WHERE id='{wid}';",
            ],
            text=True,
        )
        assert needle in raw or 'site_ready' in raw, (label, 'missing gate')
        names = [n['name'] for n in json.loads(raw)]
        print(label, 'nodes:', ', '.join(names))

    print('OK patched', TW_ID, NF_ID)


if __name__ == '__main__':
    main()
