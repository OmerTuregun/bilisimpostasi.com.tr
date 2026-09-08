#!/usr/bin/env python3
"""P0 queue limit + prefilter + arXiv cap; replace Claude EN with LibreTranslate."""
from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
PUBLISH_ID = 'zVyc6gzToDe5mhc2'
COLLECT_ID = 'bsqTiPswUyJSDCsC'
LT_URL = 'http://libretranslate:5000/translate'

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
  return String(link || '').trim().replace(/\/+$/, '');
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

// Already published kaynak URLs from TR posts (no LLM).
const publishedLinks = new Set();
try {
  const fs = require('fs');
  const postsDir = '/home/node/site/src/content/posts/tr';
  if (fs.existsSync(postsDir)) {
    for (const f of fs.readdirSync(postsDir)) {
      if (!f.endsWith('.md')) continue;
      const text = fs.readFileSync(`${postsDir}/${f}`, 'utf8');
      const m = text.match(/^kaynak:\s*"(.*)"\s*$/m);
      if (m && m[1]) publishedLinks.add(normalizeLink(m[1]));
    }
  }
} catch (e) {
  console.log('[haber_listesi] published scan failed: ' + e.message);
}

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
          }
        : undefined,
  },
}));
'''

QUEUE_KEEP_CODE = r'''// Keep unpublished queue rows; remove published + prefilter-dropped junk.
const published = new Set();
try {
  for (const it of $('Frontmatter Olustur').all()) {
    const link = String((it.json && it.json.link) || '').trim();
    if (link) published.add(link);
  }
} catch (e) {}

const prefilterDrop = new Set();
try {
  const drops =
    ($('Haber Listesini Hazirla').first().json.prefilter_dropped_links || []);
  for (const l of drops) {
    const t = String(l || '').trim();
    if (t) prefilterDrop.add(t);
  }
} catch (e) {}

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
    const link = String(o.link || '').trim();
    if (link && (published.has(link) || prefilterDrop.has(link))) {
      removed.push({ link, why: published.has(link) ? 'published' : 'prefilter' });
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
      removed_count: removed.length,
      kept_count: kept.length,
    })
);

return [{ json: { kalan_icerik, removed_count: removed.length, kept_count: kept.length } }];
'''

COLLECT_CODE = r'''// Append new rows; dedupe; cap arXiv per run.
const ARXIV_MAX_PER_RUN = 25;

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
let arxivAdded = 0;
let arxivSkippedCap = 0;

for (const m of rows) {
  const link = String(m.link || '').trim();
  if (!link || existing.has(link)) continue;

  const kaynak = String(m.kaynak || '').trim();
  const isArxiv =
    kaynak === 'arXiv' ||
    /arxiv\.org/i.test(link) ||
    /export\.arxiv\.org/i.test(String(m.link || ''));

  if (isArxiv) {
    if (arxivAdded >= ARXIV_MAX_PER_RUN) {
      arxivSkippedCap += 1;
      continue;
    }
    arxivAdded += 1;
  }

  existing.add(link);
  additions.push(
    JSON.stringify({
      baslik: m.baslik || '',
      link,
      ozet: m.ozet || '',
      kaynak: kaynak || m.kaynak || '',
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
      skipped_dup: rows.length - additions.length - arxivSkippedCap,
      arxiv_added: arxivAdded,
      arxiv_skipped_cap: arxivSkippedCap,
      arxiv_max_per_run: ARXIV_MAX_PER_RUN,
    })
);

const base = mevcut.trim();
const guncelIcerik = additions.length
  ? (base ? base + '\n' + additions.join('\n') : additions.join('\n'))
  : base;

return [{ json: { icerik: guncelIcerik } }];
'''

EN_MARKDOWN_CODE = r'''const mergedAll = (() => {
  try { return $('EN Cevir Birlestir').all(); } catch (e) { return []; }
})();
const fmAll = (() => {
  try { return $('Frontmatter Olustur').all(); } catch (e) { return []; }
})();

const categoryMap = {
  'Yapay Zeka': 'AI',
  Teknoloji: 'Technology',
  Güvenlik: 'Security',
  AI: 'AI',
  Technology: 'Technology',
  Security: 'Security',
};

return $input.all().map((item, idx) => {
  const src = (mergedAll[idx] && mergedAll[idx].json) || item.json || {};
  const title = String(src.en_title || '').trim();
  const summary = String(src.en_summary || src.tr_summary || '').trim();
  const body = String(src.en_body || '').trim();
  const category = categoryMap[src.tr_kategori] || 'Technology';

  if (!title || !body || src.lt_ok === false) {
    return {
      json: {
        ...src,
        en_skip: true,
        en_error: src.lt_error || 'LibreTranslate EN failed',
      },
    };
  }

  const esc = (s) => String(s || '').replace(/"/g, "'");
  const pubDate =
    src.pubDate ||
    (fmAll[idx] && fmAll[idx].json && fmAll[idx].json.pubDate) ||
    new Date().toISOString();
  const markdown =
    `---\n` +
    `title: "${esc(title)}"\n` +
    `pubDate: ${pubDate}\n` +
    `kategori: "${category}"\n` +
    `description: "${esc(summary.slice(0, 150))}"\n` +
    `kaynak: "${esc(src.link || '')}"\n` +
    `coverImage: "${esc(src.gorsel_r2_url || '')}"\n` +
    `gorselFotografci: "${esc(src.gorsel_fotografci || '')}"\n` +
    `gorselFotografciLink: "${esc(src.gorsel_fotografci_link || '')}"\n` +
    `---\n` +
    `${body}\n`;

  return {
    json: {
      ...src,
      en_skip: false,
      en_title: title,
      en_markdown_icerik: markdown,
      en_fileName: `${src.tr_slug || src.dosya_adi}.md`.replace(/\.md\.md$/, '.md'),
    },
  };
});
'''

EN_BIRLESTIR_CODE = r'''const promptAll = $('EN Cevir Prompt').all();
const baslikAll = $('LT Baslik').all();
const ozetAll = $('LT Ozet').all();
const govdeAll = $('LT Govde').all();

return promptAll.map((item, idx) => {
  const src = item.json || {};
  const en_title = String(baslikAll[idx]?.json?.translatedText || '').trim();
  const en_summary = String(ozetAll[idx]?.json?.translatedText || '').trim();
  const en_body = String(govdeAll[idx]?.json?.translatedText || '').trim();
  const lt_ok = !!(en_title && en_body);

  if (!lt_ok) {
    console.log('[lt_en_merge] fail idx=' + idx + ' title=' + !!en_title + ' body=' + !!en_body);
  }

  return {
    json: {
      ...src,
      en_title,
      en_summary,
      en_body,
      lt_ok,
      lt_error: lt_ok ? '' : 'LibreTranslate returned empty title or body',
    },
  };
});
'''

HTTP_LT_BODY = {
    'method': 'POST',
    'url': LT_URL,
    'sendBody': True,
    'specifyBody': 'json',
    'jsonBody': '={{ { q: $json.tr_body, source: "tr", target: "en", format: "text" } }}',
    'options': {'timeout': 120000},
}

HTTP_LT_TITLE = {
    'method': 'POST',
    'url': LT_URL,
    'sendBody': True,
    'specifyBody': 'json',
    'jsonBody': '={{ { q: $json.tr_title, source: "tr", target: "en", format: "text" } }}',
    'options': {'timeout': 30000},
}

HTTP_LT_SUMMARY = {
    'method': 'POST',
    'url': LT_URL,
    'sendBody': True,
    'specifyBody': 'json',
    'jsonBody': '={{ { q: $json.tr_summary, source: "tr", target: "en", format: "text" } }}',
    'options': {'timeout': 30000},
}


def export_wf(wf_id: str, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'{label}-{stamp}-pre-p0-libre.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={wf_id}', f'--output=/tmp/wf-{label}.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', f'agent-n8n:/tmp/wf-{label}.json', str(out)], check=True)
    return out


def patch_publish(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    by['Haber Listesini Hazirla']['parameters']['jsCode'] = HABER_LISTESI_CODE
    by['Kuyruk Temizle Bos Icerik']['parameters']['jsCode'] = QUEUE_KEEP_CODE
    by['EN Markdown Olustur']['parameters']['jsCode'] = EN_MARKDOWN_CODE

    # Remove Claude EN Cevir
    claude_id = by['Claude EN Cevir']['id']
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] != 'Claude EN Cevir']

    # Add LibreTranslate HTTP nodes + merge
    lt_baslik = {
        'parameters': HTTP_LT_TITLE,
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [1248, 48],
        'id': 'lt-baslik-0001',
        'name': 'LT Baslik',
        'onError': 'continueRegularOutput',
    }
    lt_ozet = {
        'parameters': HTTP_LT_SUMMARY,
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [1472, 48],
        'id': 'lt-ozet-0002',
        'name': 'LT Ozet',
        'onError': 'continueRegularOutput',
    }
    lt_govde = {
        'parameters': HTTP_LT_BODY,
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [1696, 48],
        'id': 'lt-govde-0003',
        'name': 'LT Govde',
        'onError': 'continueRegularOutput',
    }
    en_birlestir = {
        'parameters': {'jsCode': EN_BIRLESTIR_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1920, 48],
        'id': 'lt-merge-0004',
        'name': 'EN Cevir Birlestir',
    }
    wf['nodes'].extend([lt_baslik, lt_ozet, lt_govde, en_birlestir])

    conn = wf['connections']
    conn['EN Cevir Prompt'] = {'main': [[{'node': 'LT Baslik', 'type': 'main', 'index': 0}]]}
    conn['LT Baslik'] = {'main': [[{'node': 'LT Ozet', 'type': 'main', 'index': 0}]]}
    conn['LT Ozet'] = {'main': [[{'node': 'LT Govde', 'type': 'main', 'index': 0}]]}
    conn['LT Govde'] = {'main': [[{'node': 'EN Cevir Birlestir', 'type': 'main', 'index': 0}]]}
    conn['EN Cevir Birlestir'] = {'main': [[{'node': 'EN Markdown Olustur', 'type': 'main', 'index': 0}]]}
    conn.pop('Claude EN Cevir', None)

    out = BACKUP / 'haber-yayinlama-p0-libretranslate-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('publish patched ->', out)
    return out


def patch_collect(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    by['Code in JavaScript']['parameters']['jsCode'] = COLLECT_CODE
    out = BACKUP / 'haber-toplama-p0-arxiv-cap-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('collect patched ->', out)
    return out


def import_publish(patched: Path, wf_id: str) -> None:
    remote = f'/tmp/wf-{wf_id}.json'
    subprocess.run(['docker', 'cp', str(patched), f'agent-n8n:{remote}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', f'--input={remote}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={wf_id}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={wf_id}', '--active=true'], check=False)


def main() -> None:
    pub_pre = export_wf(PUBLISH_ID, 'publish')
    col_pre = export_wf(COLLECT_ID, 'collect')
    pub = patch_publish(pub_pre)
    col = patch_collect(col_pre)
    import_publish(pub, PUBLISH_ID)
    import_publish(col, COLLECT_ID)
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


if __name__ == '__main__':
    main()
