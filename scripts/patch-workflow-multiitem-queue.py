#!/usr/bin/env python3
"""Fix silent multi-item drops + selective pending.jsonl cleanup.

1) Yazilari Ayristir / Post Verisini Geri Yukle / Frontmatter / Dosya Adi Dogrula /
   EN Cevir Prompt / EN Markdown Olustur → process ALL items via $input.all()
   (same pattern as Anahtar Kelime Cikar / asama30).
2) Kuyruk Temizle: remove only successfully published links; keep the rest.
3) 350-word filter: DO NOT change threshold; add structured console.log monitoring.
"""
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

AYRISTIR_CODE = r'''const listItems = (() => {
  try { return $('Haber Listesini Hazirla').all(); } catch (e) { return []; }
})();

const stats = {
  event: 'ayristir_filter_stats',
  ts: new Date().toISOString(),
  input_items: 0,
  atla: 0,
  stop_reject: 0,
  parse_empty: 0,
  word_lt_350: 0,
  punct_reject: 0,
  passed_posts: 0,
  word_counts_rejected: [],
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
    if (words < 350) {
      stats.word_lt_350 += 1;
      stats.word_counts_rejected.push(words);
      continue;
    }
    if (!/[.!?…]"?$/.test(t)) {
      stats.punct_reject += 1;
      stats.word_counts_rejected.push(words);
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

RESTORE_CODE = r'''function allJson(name) {
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

  if (cur.url) {
    merged.coverImage = cur.url;
  } else {
    merged.coverImage =
      merged.coverImage ||
      merged.cover_image ||
      merged.gorsel_r2_url ||
      merged.gorsel_url ||
      '';
  }

  if (!merged.gorsel_r2_url) {
    merged.gorsel_r2_url =
      src.gorsel_r2_url ||
      cur.gorsel_r2_url ||
      (cur.url && String(cur.url).includes('r2.dev') ? cur.url : '') ||
      merged.gorsel_url ||
      '';
  }

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

FRONTMATTER_CODE = r'''const baseNow = new Date();
const pad = (n) => String(n).padStart(2, '0');

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

const esc = (s) => String(s || '').replace(/"/g, "'");

return $input.all().map((item, idx) => {
  const j = item.json || {};
  const baslik = String(j.baslik || j.title || '').trim();
  if (!baslik) {
    throw new Error('Frontmatter Olustur: baslik bos (idx=' + idx + ')');
  }

  const slug = slugify(baslik);
  if (!slug) {
    throw new Error('Frontmatter Olustur: slug bos: ' + JSON.stringify(baslik));
  }

  // Unique timestamp per item (same-second collision guard)
  const now = new Date(baseNow.getTime() + idx * 1000);
  const ts =
    now.getFullYear() +
    pad(now.getMonth() + 1) +
    pad(now.getDate()) +
    '-' +
    pad(now.getHours()) +
    pad(now.getMinutes()) +
    pad(now.getSeconds());

  const dosya_adi = `${slug}-${ts}`;
  if (!dosya_adi || dosya_adi.startsWith('-') || /^-\d{8}/.test(dosya_adi)) {
    throw new Error('Frontmatter Olustur: gecersiz dosya_adi: ' + JSON.stringify(dosya_adi));
  }

  const ozet = String(j.ozet || j.description || '');
  const kategori = String(j.kategori || 'Teknoloji');
  const link = String(j.link || j.kaynak || '');
  const cover = String(j.gorsel_r2_url || j.coverImage || j.cover_image || '');
  const gorselQuery = String(j.gorsel_query || '').trim();
  const fotografci = String(j.gorsel_fotografci || '');
  const fotografciLink = String(j.gorsel_fotografci_link || '');
  const icerik = String(j.icerik || j.body || '');
  const pubDate = now.toISOString();

  const markdown_icerik =
    `---\n` +
    `title: "${esc(baslik)}"\n` +
    `pubDate: ${pubDate}\n` +
    `kategori: "${esc(kategori)}"\n` +
    `description: "${esc(ozet.slice(0, 150))}"\n` +
    `kaynak: "${esc(link)}"\n` +
    `coverImage: "${esc(cover)}"\n` +
    `gorselFotografci: "${esc(fotografci)}"\n` +
    `gorselFotografciLink: "${esc(fotografciLink)}"\n` +
    `gorselQuery: "${esc(gorselQuery)}"\n` +
    `---\n` +
    `${icerik}`;

  return {
    json: {
      ...j,
      baslik,
      ozet,
      icerik,
      kategori,
      link,
      gorsel_r2_url: cover,
      coverImage: j.coverImage || cover,
      gorsel_query: gorselQuery,
      gorselQuery,
      pubDate,
      markdown_icerik,
      dosya_adi,
    },
  };
});
'''

VALIDATE_CODE = r'''return $input.all().map((item, idx) => {
  const j = item.json || {};
  const dosya = String(j.dosya_adi || '').trim();
  const md = String(j.markdown_icerik || '');
  const baslik = String(j.baslik || '').trim();

  if (!baslik) {
    throw new Error('Dosya Adi Dogrula: baslik bos (idx=' + idx + ')');
  }
  if (!dosya || dosya.startsWith('-') || /^-\d{8}/.test(dosya) || dosya === '.md') {
    throw new Error(
      'Dosya Adi Dogrula: gecersiz dosya_adi (idx=' + idx + '): ' + JSON.stringify(dosya)
    );
  }
  if (!md || !md.includes('title:')) {
    throw new Error('Dosya Adi Dogrula: markdown_icerik eksik (idx=' + idx + ')');
  }

  return { json: j };
});
'''

EN_PROMPT_CODE = r'''const fmAll = (() => {
  try { return $('Frontmatter Olustur').all(); } catch (e) { return []; }
})();

return $input.all().map((item, idx) => {
  const src = (fmAll[idx] && fmAll[idx].json) || item.json || {};
  return {
    json: {
      ...src,
      tr_title: src.baslik || '',
      tr_summary: src.ozet || '',
      tr_kategori: src.kategori || 'Teknoloji',
      tr_body: src.icerik || '',
      tr_slug: String(src.dosya_adi || '').replace(/\.md$/, ''),
    },
  };
});
'''

EN_MARKDOWN_CODE = r'''const promptAll = (() => {
  try { return $('EN Cevir Prompt').all(); } catch (e) { return []; }
})();
const fmAll = (() => {
  try { return $('Frontmatter Olustur').all(); } catch (e) { return []; }
})();

return $input.all().map((item, idx) => {
  const j = item.json || {};
  const src = (promptAll[idx] && promptAll[idx].json) || {};
  const raw = (j.content?.[0]?.text || j.text || '').trim();
  const enStop = String(j.stop_reason || j.stopReason || j.response?.stop_reason || '').toLowerCase();

  if (enStop && enStop !== 'end_turn' && enStop !== 'stop') {
    return {
      json: {
        ...src,
        en_skip: true,
        en_error: 'Claude EN truncated: ' + enStop,
      },
    };
  }

  function pick(label) {
    const re = new RegExp('^' + label + ':\\s*(.+)$', 'im');
    const m = raw.match(re);
    return m ? m[1].trim() : '';
  }

  const title = pick('TITLE');
  const summary = pick('SUMMARY');
  let category = pick('CATEGORY');
  const bodyMatch = raw.match(/^BODY:\\s*\\n([\\s\\S]*)$/im);
  const body = bodyMatch ? bodyMatch[1].trim() : '';

  const map = {
    AI: 'AI', Technology: 'Technology', Security: 'Security',
    'Yapay Zeka': 'AI', Teknoloji: 'Technology', Güvenlik: 'Security',
  };
  category = map[category] || map[src.tr_kategori] || 'Technology';

  if (!title || !body) {
    return {
      json: {
        ...src,
        en_skip: true,
        en_error: 'Claude EN parse failed',
        en_raw: raw.slice(0, 500),
      },
    };
  }

  const esc = (s) => (s || '').replace(/"/g, "'");
  const pubDate =
    src.pubDate ||
    (fmAll[idx] && fmAll[idx].json && fmAll[idx].json.pubDate) ||
    new Date().toISOString();
  const markdown =
    `---\\n` +
    `title: "${esc(title)}"\\n` +
    `pubDate: ${pubDate}\\n` +
    `kategori: "${category}"\\n` +
    `description: "${esc(summary.slice(0, 150))}"\\n` +
    `kaynak: "${esc(src.link || '')}"\\n` +
    `coverImage: "${esc(src.gorsel_r2_url || '')}"\\n` +
    `gorselFotografci: "${esc(src.gorsel_fotografci || '')}"\\n` +
    `gorselFotografciLink: "${esc(src.gorsel_fotografci_link || '')}"\\n` +
    `---\\n` +
    `${body}\\n`;

  return {
    json: {
      ...src,
      en_skip: false,
      en_title: title,
      en_markdown_icerik: markdown,
      en_fileName: `${src.tr_slug || src.dosya_adi}.md`.replace(/\\.md\\.md$/, '.md'),
    },
  };
});
'''

# Fix accidental double-escaping in EN_MARKDOWN_CODE — write clean version below
EN_MARKDOWN_CODE = r'''const promptAll = (() => {
  try { return $('EN Cevir Prompt').all(); } catch (e) { return []; }
})();
const fmAll = (() => {
  try { return $('Frontmatter Olustur').all(); } catch (e) { return []; }
})();

return $input.all().map((item, idx) => {
  const j = item.json || {};
  const src = (promptAll[idx] && promptAll[idx].json) || {};
  const raw = (j.content?.[0]?.text || j.text || '').trim();
  const enStop = String(j.stop_reason || j.stopReason || j.response?.stop_reason || '').toLowerCase();

  if (enStop && enStop !== 'end_turn' && enStop !== 'stop') {
    return {
      json: {
        ...src,
        en_skip: true,
        en_error: 'Claude EN truncated: ' + enStop,
      },
    };
  }

  function pick(label) {
    const re = new RegExp('^' + label + ':\\s*(.+)$', 'im');
    const m = raw.match(re);
    return m ? m[1].trim() : '';
  }

  const title = pick('TITLE');
  const summary = pick('SUMMARY');
  let category = pick('CATEGORY');
  const bodyMatch = raw.match(/^BODY:\s*\n([\s\S]*)$/im);
  const body = bodyMatch ? bodyMatch[1].trim() : '';

  const map = {
    AI: 'AI', Technology: 'Technology', Security: 'Security',
    'Yapay Zeka': 'AI', Teknoloji: 'Technology', Güvenlik: 'Security',
  };
  category = map[category] || map[src.tr_kategori] || 'Technology';

  if (!title || !body) {
    return {
      json: {
        ...src,
        en_skip: true,
        en_error: 'Claude EN parse failed',
        en_raw: raw.slice(0, 500),
      },
    };
  }

  const esc = (s) => (s || '').replace(/"/g, "'");
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

QUEUE_KEEP_CODE = r'''// Keep unpublished queue rows; remove only links that were written this cycle.
const published = new Set();
try {
  for (const it of $('Frontmatter Olustur').all()) {
    const link = String((it.json && it.json.link) || '').trim();
    if (link) published.add(link);
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
    if (link && published.has(link)) {
      removed.push(link);
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
      removed_count: removed.length,
      kept_count: kept.length,
    })
);

return [{ json: { kalan_icerik, removed_count: removed.length, kept_count: kept.length } }];
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-toplu-{stamp}-pre-multiitem-queue-fix.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-multiitem-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-multiitem-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = data[0] if isinstance(data, list) else data
    wf = deepcopy(wf)
    by = {n['name']: n for n in wf['nodes']}

    code_map = {
        'Yazilari Ayristir': AYRISTIR_CODE,
        'Post Verisini Geri Yukle': RESTORE_CODE,
        'Frontmatter Olustur': FRONTMATTER_CODE,
        'Dosya Adi Dogrula': VALIDATE_CODE,
        'EN Cevir Prompt': EN_PROMPT_CODE,
        'EN Markdown Olustur': EN_MARKDOWN_CODE,
    }
    for name, code in code_map.items():
        if name not in by:
            raise SystemExit(f'missing node: {name}')
        by[name]['parameters']['jsCode'] = code
        # Keep default runOnceForAllItems; $input.all() handles multi-item (asama30 pattern)
        by[name]['parameters'].pop('mode', None)

    # Replace Set "Kuyruk Temizle Bos Icerik" with Code selective keep
    qnode = by['Kuyruk Temizle Bos Icerik']
    qnode['type'] = 'n8n-nodes-base.code'
    qnode['typeVersion'] = 2
    qnode['parameters'] = {'jsCode': QUEUE_KEEP_CODE}
    qnode.pop('notesInFlow', None)

    # Convert-to-file must read kalan_icerik
    conv = by['Kuyruk Temizle Dosyaya Cevir']
    conv['parameters']['sourceProperty'] = 'kalan_icerik'
    # ensure toText
    conv['parameters']['operation'] = 'toText'

    out = BACKUP / 'haber-yayinlama-toplu-multiitem-queue-fixed.json'
    # n8n import expects array or single object — match unsplash patch ([wf])
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('patched nodes:', sorted(code_map))
    print('queue node → Code selective keep; convert sourceProperty=kalan_icerik')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(
        ['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-multiitem-fixed.json'],
        check=True,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-multiitem-fixed.json'],
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
    print('import+publish+restart done')


def verify_live() -> None:
    # wait for n8n up
    for _ in range(30):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            break
        time.sleep(2)
    raw = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';",
        ],
        text=True,
    ).strip()
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    checks = {
        'Yazilari Ayristir': '$input.all()',
        'Post Verisini Geri Yukle': '$input.all()',
        'Frontmatter Olustur': '$input.all()',
        'Dosya Adi Dogrula': '$input.all()',
        'EN Cevir Prompt': '$input.all()',
        'EN Markdown Olustur': '$input.all()',
        'Kuyruk Temizle Bos Icerik': 'kalan_icerik',
    }
    for name, needle in checks.items():
        code = by[name]['parameters'].get('jsCode') or ''
        src = by[name]['parameters'].get('sourceProperty') or ''
        blob = code + src
        ok = needle in blob or needle in code
        if name == 'Kuyruk Temizle Dosyaya Cevir':
            continue
        print(f'verify {name}: {"OK" if ok else "FAIL"} ({needle})')
        if not ok:
            raise SystemExit(f'verify failed: {name}')
    conv_src = by['Kuyruk Temizle Dosyaya Cevir']['parameters'].get('sourceProperty')
    print('verify convert sourceProperty:', conv_src)
    assert conv_src == 'kalan_icerik'
    assert by['Kuyruk Temizle Bos Icerik']['type'] == 'n8n-nodes-base.code'
    # threshold unchanged
    assert 'words < 350' in by['Yazilari Ayristir']['parameters']['jsCode']
    print('verify word filter threshold still 350: OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify_live()


if __name__ == '__main__':
    main()
