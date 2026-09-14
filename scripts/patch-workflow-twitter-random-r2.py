#!/usr/bin/env python3
"""Patch Haber Yayınlama: random Twitter spacing + restore R2 cover URLs."""
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
R2_BASE = 'https://pub-880c98af22074b02b5f5237e1b3a0bad.r2.dev'

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

POST_RESTORE_CODE = r'''function allJson(name) {
  try {
    return $(name).all().map((i) => i.json).filter((j) => j && typeof j === 'object');
  } catch (e) {
    return [];
  }
}

const bolItems = allJson('Yazilara Bol');
const anahtarItems = allJson('Anahtar Kelime Cikar');
const gorselItems = allJson('Gorsel Bilgi Hazirla');
const yokItems = allJson('Gorsel Yok Gecis');

const gorselByLink = new Map();
for (const j of [...gorselItems, ...yokItems]) {
  const link = String(j.link || '').trim();
  if (link && !gorselByLink.has(link)) gorselByLink.set(link, j);
}

const protectedKeys = new Set([
  'baslik', 'title', 'ozet', 'description', 'icerik', 'body',
  'kategori', 'link', 'kaynak',
  'gorsel_r2_url', 'gorsel_url', 'gorsel_fotografci', 'gorsel_fotografci_link',
  'gorsel_kaynak_link', 'gorsel_dosya_adi', 'gorsel_download_location', 'gorsel_query',
]);

function isR2Url(u) {
  const s = String(u || '');
  return s.includes('r2.dev') || s.includes('r2.cloudflarestorage.com');
}

return $input.all().map((item, idx) => {
  const cur = item.json || {};
  const bol = bolItems[idx] || {};
  const anahtar = anahtarItems[idx] || {};
  const linkHint = String(bol.link || anahtar.link || cur.link || '').trim();
  const gorsel = (linkHint && gorselByLink.get(linkHint)) || gorselItems[idx] || yokItems[idx] || {};
  const src = { ...anahtar, ...bol, ...gorsel };

  const merged = { ...src };
  for (const [k, v] of Object.entries(cur)) {
    if (v === undefined || v === null || v === '') continue;
    if (protectedKeys.has(k) && merged[k] !== undefined && merged[k] !== null && merged[k] !== '') {
      continue;
    }
    merged[k] = v;
  }

  // Prefer precomputed R2 public URL; only trust upload response if it is R2.
  const r2FromUpload = isR2Url(cur.url) ? cur.url : '';
  merged.gorsel_r2_url =
    src.gorsel_r2_url ||
    merged.gorsel_r2_url ||
    r2FromUpload ||
    '';

  merged.coverImage =
    merged.gorsel_r2_url ||
    (isR2Url(cur.url) ? cur.url : '') ||
    merged.coverImage ||
    merged.gorsel_url ||
    '';

  merged.baslik = String(merged.baslik || merged.title || '').trim();
  merged.ozet = String(merged.ozet || merged.description || '').trim();
  merged.icerik = String(merged.icerik || merged.body || '').trim();
  merged.kategori = String(merged.kategori || 'Teknoloji').trim();
  merged.link = String(merged.link || merged.kaynak || linkHint || '').trim();

  if (!merged.baslik) {
    throw new Error(
      'Post Verisini Geri Yukle: baslik bos (idx=' + idx + ') — Wait sonrasi post alanlari kurtarilamadi.'
    );
  }

  return { json: merged };
});
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-twitter-r2.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-tw-r2-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-tw-r2-pre.json', str(out)], check=True)
    return out


def patch_gorsel(code: str) -> str:
    if "gorsel_r2_url: '" in code or 'gorsel_r2_url: "' in code or 'gorsel_r2_url:' in code and 'r2.dev' in code:
        if R2_BASE in code:
            return code
    needle = "      gorsel_url: imageUrl,"
    if needle not in code:
        raise SystemExit('Gorsel Bilgi Hazirla: gorsel_url line not found')
    insert = (
        "      gorsel_url: imageUrl,\n"
        f"      gorsel_r2_url: '{R2_BASE}/' + dosya_adi,"
    )
    return code.replace(needle, insert, 1)


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    by['Twitter Kuyruk Hazirla']['parameters']['jsCode'] = TWITTER_CODE
    by['Gorsel Bilgi Hazirla']['parameters']['jsCode'] = patch_gorsel(
        by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    )
    by['Post Verisini Geri Yukle']['parameters']['jsCode'] = POST_RESTORE_CODE

    out = BACKUP / 'haber-yayinlama-twitter-random-r2-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-tw-r2.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-tw-r2.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
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
            print('n8n healthy')
            break
        time.sleep(2)


def verify() -> None:
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    by = {n['name']: n for n in json.loads(raw)}
    tw = by['Twitter Kuyruk Hazirla']['parameters']['jsCode']
    gorsel = by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    restore = by['Post Verisini Geri Yukle']['parameters']['jsCode']
    assert 'randomOffsets' in tw and 'MIN_GAP_MINUTES' in tw
    assert R2_BASE in gorsel and 'gorsel_r2_url' in gorsel
    assert 'isR2Url' in restore and 'Prefer precomputed R2' in restore
    # download trigger still present
    assert by['Unsplash Download Trigger']['parameters'].get('url')
    print('verify OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify()


if __name__ == '__main__':
    main()
