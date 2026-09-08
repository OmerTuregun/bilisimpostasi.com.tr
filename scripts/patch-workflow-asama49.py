#!/usr/bin/env python3
"""Aşama 49: LibreTranslate data-loss fix + word-count log-only (no drop)."""
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

LT_TITLE_BODY = (
    '={{ { q: $(\'EN Cevir Prompt\').item.json.tr_title, '
    'source: "tr", target: "en", format: "text" } }}'
)
LT_SUMMARY_BODY = (
    '={{ { q: $(\'EN Cevir Prompt\').item.json.tr_summary, '
    'source: "tr", target: "en", format: "text" } }}'
)
LT_GOVDE_BODY = (
    '={{ { q: $(\'EN Cevir Prompt\').item.json.tr_body, '
    'source: "tr", target: "en", format: "text" } }}'
)

AYRISTIR_CODE = r'''const listItems = (() => {
  try { return $('Haber Listesini Hazirla').all(); } catch (e) { return []; }
})();

const WORD_INFO_THRESHOLD = 250;

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

  if (stopReason && stopReason !== 'end_turn' && stopReason !== 'stop') {
    stats.stop_reject += 1;
    continue;
  }
  if (!raw || raw === 'ATLA') {
    stats.atla += 1;
    continue;
  }

  const itemLink =
    (listItems[idx] && listItems[idx].json && listItems[idx].json.link) ||
    j.link ||
    '';

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
    // Word count is informational only — never drop solely for being short.
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

console.log('[ayristir_filter_stats] ' + JSON.stringify(stats));
return out;
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-asama49.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-asama49-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-asama49-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    by['Yazilari Ayristir']['parameters']['jsCode'] = AYRISTIR_CODE

    by['LT Baslik']['parameters']['jsonBody'] = LT_TITLE_BODY
    by['LT Ozet']['parameters']['jsonBody'] = LT_SUMMARY_BODY
    by['LT Govde']['parameters']['jsonBody'] = LT_GOVDE_BODY
    # Longer timeout for body; keep continue on error
    by['LT Govde']['parameters'].setdefault('options', {})['timeout'] = 180000
    for name in ('LT Baslik', 'LT Ozet', 'LT Govde'):
        by[name]['onError'] = 'continueRegularOutput'

    out = BACKUP / 'haber-yayinlama-asama49-lt-word-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-asama49.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-asama49.json'],
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
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';",
        ],
        text=True,
    )
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    assert "EN Cevir Prompt').item.json.tr_body" in by['LT Govde']['parameters']['jsonBody']
    assert "EN Cevir Prompt').item.json.tr_summary" in by['LT Ozet']['parameters']['jsonBody']
    assert 'WORD_INFO_THRESHOLD' in by['Yazilari Ayristir']['parameters']['jsCode']
    assert 'words < 140' not in by['Yazilari Ayristir']['parameters']['jsCode']
    assert 'continue' not in by['Yazilari Ayristir']['parameters']['jsCode'].split('words < WORD_INFO_THRESHOLD')[1].split('listEndOk')[0] or True
    # Ensure short-word path does not `continue`
    code = by['Yazilari Ayristir']['parameters']['jsCode']
    block = code.split('if (words < WORD_INFO_THRESHOLD)')[1].split('const listEndOk')[0]
    assert 'continue;' not in block
    print('VERIFY OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify()


if __name__ == '__main__':
    main()
