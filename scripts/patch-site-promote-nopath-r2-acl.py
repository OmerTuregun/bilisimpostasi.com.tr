#!/usr/bin/env python3
"""Fix Site Yayina Al (no path require) + remove R2 ACL that can Forbidden."""
from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
TW_ID = 'twKuyrukIsleyici01'
PUB_ID = 'zVyc6gzToDe5mhc2'

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


def export_wf(wf_id: str, out: Path) -> dict:
    tmp = f'/tmp/wf-{wf_id}.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={wf_id}', f'--output={tmp}'],
        check=True,
    )
    subprocess.run(['docker', 'cp', f'agent-n8n:{tmp}', str(out)], check=True)
    data = json.loads(out.read_text())
    return data[0] if isinstance(data, list) else data


def import_wf(path: Path) -> None:
    tmp = f'/tmp/import-{path.name}'
    subprocess.run(['docker', 'cp', str(path), f'agent-n8n:{tmp}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', f'--input={tmp}'],
        check=True,
    )


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')

    # --- Twitter processor: Site Yayina Al ---
    pre_tw = BACKUP / f'twitter-isleyici-{stamp}-pre-pathfix.json'
    wf = export_wf(TW_ID, pre_tw)
    by = {n['name']: n for n in wf['nodes']}
    by['Site Yayina Al']['parameters']['jsCode'] = SITE_PROMOTE_CODE
    out_tw = BACKUP / 'twitter-kuyruk-isleyici-site-promote-nopath.json'
    out_tw.write_text(json.dumps(wf, ensure_ascii=False, indent=2))
    import_wf(out_tw)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={TW_ID}'],
        check=False,
    )

    # --- Publish workflow: drop ACL on R2 Yukle ---
    pre_pub = BACKUP / f'haber-yayinlama-{stamp}-pre-r2-acl.json'
    pub = export_wf(PUB_ID, pre_pub)
    byp = {n['name']: n for n in pub['nodes']}
    r2 = byp['R2 Yukle']
    af = r2['parameters'].setdefault('additionalFields', {})
    if 'acl' in af:
        del af['acl']
        print('removed R2 ACL')
    else:
        print('R2 ACL already absent')
    # keep contentType
    af['contentType'] = 'image/jpeg'
    out_pub = BACKUP / 'haber-yayinlama-r2-no-acl.json'
    out_pub.write_text(json.dumps(pub, ensure_ascii=False, indent=2))
    import_wf(out_pub)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={PUB_ID}'],
        check=False,
    )

    # Also update patch source for future re-applies
    src = ROOT / 'scripts/patch-staggered-site-publish.py'
    text = src.read_text()
    if "const path = require('path');" in text:
        # replace SITE_PROMOTE_CODE block start markers carefully
        start = text.find("SITE_PROMOTE_CODE = r'''")
        end = text.find("'''", start + len("SITE_PROMOTE_CODE = r'''")) + 3
        if start > 0 and end > start:
            text = text[:start] + "SITE_PROMOTE_CODE = r'''" + SITE_PROMOTE_CODE + "'''" + text[end:]
            src.write_text(text)
            print('updated patch-staggered-site-publish.py')

    print('done')


if __name__ == '__main__':
    main()
