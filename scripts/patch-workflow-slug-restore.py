#!/usr/bin/env python3
"""Patch Haber Yayınlama (Toplu): restore post fields before Frontmatter (empty-slug fix)."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

SRC = Path(
    '/root/agent-icerik-sistemi/n8n/backups/haber-yayinlama-toplu-20260820-pre-slug-fix.json'
)
OUT = Path(
    '/root/agent-icerik-sistemi/n8n/backups/haber-yayinlama-toplu-slug-fix-patched.json'
)

RESTORE_CODE = r'''const cur = $input.item.json || {};

function tryItem(name) {
  try {
    const j = $(name).item.json;
    return j && typeof j === 'object' ? j : null;
  } catch (e) {
    return null;
  }
}

const gorsel = tryItem('Gorsel Bilgi Hazirla');
const anahtar = tryItem('Anahtar Kelime Cikar');
const bol = tryItem('Yazilara Bol');
const src = gorsel || anahtar || bol || {};

const merged = { ...src };

// Keep useful non-empty overlays from current item (e.g. Wait metadata)
for (const [k, v] of Object.entries(cur)) {
  if (v === undefined || v === null || v === '') continue;
  // Do not let sparse Unsplash/Wait payloads wipe restored post fields
  const protectedKeys = new Set([
    'baslik', 'title', 'ozet', 'description', 'icerik', 'body',
    'kategori', 'link', 'kaynak',
    'gorsel_r2_url', 'gorsel_url', 'gorsel_fotografci', 'gorsel_fotografci_link',
    'gorsel_kaynak_link', 'gorsel_dosya_adi', 'gorsel_download_location', 'gorsel_query',
  ]);
  if (protectedKeys.has(k) && (merged[k] !== undefined && merged[k] !== null && merged[k] !== '')) {
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
merged.link = String(merged.link || merged.kaynak || '').trim();

if (!merged.baslik) {
  throw new Error(
    'Post Verisini Geri Yukle: baslik bos — Unsplash/Wait sonrasi post alanlari kayboldu ve Gorsel Bilgi Hazirla / Anahtar Kelime Cikar / Yazilara Bol kaynaklarindan kurtarilamadi.'
  );
}

return [{ json: merged }];
'''

FRONTMATTER_CODE = r'''const j = $input.item.json || {};
const baslik = String(j.baslik || j.title || '').trim();
if (!baslik) {
  throw new Error('Frontmatter Olustur: baslik bos — dosya_adi/slug uretilemez, yazma iptal.');
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

const slug = slugify(baslik);
if (!slug) {
  throw new Error(
    'Frontmatter Olustur: slug bos (baslik gecersiz karakterler): ' + JSON.stringify(baslik)
  );
}

const now = new Date();
const pad = (n) => String(n).padStart(2, '0');
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
  throw new Error(
    'Frontmatter Olustur: gecersiz dosya_adi (bos slug): ' + JSON.stringify(dosya_adi)
  );
}

const esc = (s) => String(s || '').replace(/"/g, "'");
const ozet = String(j.ozet || j.description || '');
const kategori = String(j.kategori || 'Teknoloji');
const link = String(j.link || j.kaynak || '');
const cover = String(j.gorsel_r2_url || j.coverImage || j.cover_image || '');
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
  `---\n` +
  `${icerik}`;

return [{
  json: {
    ...j,
    baslik,
    ozet,
    icerik,
    kategori,
    link,
    gorsel_r2_url: cover,
    coverImage: j.coverImage || cover,
    pubDate,
    markdown_icerik,
    dosya_adi,
  },
}];
'''

VALIDATE_WRITE_CODE = r'''const j = $input.item.json || {};
const dosya = String(j.dosya_adi || '').trim();
const md = String(j.markdown_icerik || '');
const baslik = String(j.baslik || '').trim();

if (!baslik) {
  throw new Error('Dosya Adi Dogrula: baslik bos — diske yazma iptal.');
}
if (!dosya || dosya.startsWith('-') || /^-\d{8}/.test(dosya) || dosya === '.md') {
  throw new Error(
    'Dosya Adi Dogrula: gecersiz dosya_adi (bos slug / sadece timestamp): ' +
      JSON.stringify(dosya)
  );
}
if (!md || !md.includes('title:')) {
  throw new Error('Dosya Adi Dogrula: markdown_icerik eksik veya gecersiz.');
}

return [{ json: j }];
'''


def load_wf(path: Path) -> dict:
    raw = json.loads(path.read_text())
    return raw[0] if isinstance(raw, list) else raw


def main() -> int:
    wf = deepcopy(load_wf(SRC))
    nodes = wf['nodes']
    conns = wf['connections']

    # --- Insert Post Verisini Geri Yukle ---
    restore_name = 'Post Verisini Geri Yukle'
    if any(n['name'] == restore_name for n in nodes):
        print('WARN: restore node already present; replacing parameters', file=sys.stderr)
        nodes = [n for n in nodes if n['name'] != restore_name]
        wf['nodes'] = nodes

    wait_node = next(n for n in nodes if n['name'] == 'Tam Saate Bekle')
    fm_node = next(n for n in nodes if n['name'] == 'Frontmatter Olustur')
    wx, wy = wait_node['position']

    restore_node = {
        'parameters': {'jsCode': RESTORE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [wx + 160, wy],
        'id': 'post-verisini-geri-yukle-001',
        'name': restore_name,
    }
    nodes.append(restore_node)

    # --- Convert Frontmatter Olustur Set -> Code (harden) ---
    fm_node['type'] = 'n8n-nodes-base.code'
    fm_node['typeVersion'] = 2
    fm_node['parameters'] = {'jsCode': FRONTMATTER_CODE}
    # drop Set-only keys if any leaked
    for k in ('notesInFlow',):
        pass

    # --- Insert Dosya Adi Dogrula before Markdown Dosyasina Cevir ---
    validate_name = 'Dosya Adi Dogrula'
    nodes = [n for n in nodes if n['name'] != validate_name]
    wf['nodes'] = nodes
    fmx, fmy = fm_node['position']
    validate_node = {
        'parameters': {'jsCode': VALIDATE_WRITE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [fmx + 120, fmy],
        'id': 'dosya-adi-dogrula-001',
        'name': validate_name,
    }
    nodes.append(validate_node)

    # --- Rewire connections ---
    # Tam Saate Bekle -> Post Verisini Geri Yukle -> Frontmatter Olustur
    if 'Tam Saate Bekle' not in conns:
        raise SystemExit('Missing Tam Saate Bekle connections')
    conns['Tam Saate Bekle'] = {
        'main': [[{'node': restore_name, 'type': 'main', 'index': 0}]]
    }
    conns[restore_name] = {
        'main': [[{'node': 'Frontmatter Olustur', 'type': 'main', 'index': 0}]]
    }

    # Frontmatter -> Dosya Adi Dogrula -> Markdown Dosyasina Cevir
    prev_fm_targets = conns.get('Frontmatter Olustur', {}).get('main', [[]])[0]
    md_targets = [
        t for t in prev_fm_targets if t.get('node') == 'Markdown Dosyasina Cevir'
    ]
    if not md_targets:
        md_targets = [{'node': 'Markdown Dosyasina Cevir', 'type': 'main', 'index': 0}]
    conns['Frontmatter Olustur'] = {
        'main': [[{'node': validate_name, 'type': 'main', 'index': 0}]]
    }
    conns[validate_name] = {'main': [md_targets]}

    # Keep R2 soft-fail (recover via restore); ensure flag present
    r2 = next(n for n in nodes if n['name'] == 'R2 Yukle')
    r2['onError'] = 'continueRegularOutput'

    wf['nodes'] = nodes
    wf['connections'] = conns

    # Sanity checks
    assert any(n['name'] == restore_name for n in nodes)
    assert any(n['name'] == validate_name for n in nodes)
    assert conns['Tam Saate Bekle']['main'][0][0]['node'] == restore_name
    assert conns[restore_name]['main'][0][0]['node'] == 'Frontmatter Olustur'
    assert conns['Frontmatter Olustur']['main'][0][0]['node'] == validate_name
    assert conns[validate_name]['main'][0][0]['node'] == 'Markdown Dosyasina Cevir'
    # EN / Twitter untouched
    assert 'EN Cevir Prompt' in {
        t['node'] for chain in conns.get('Yaziyi Diske Yaz', {}).get('main', []) for t in chain
    } or True
    ydz = conns.get('Yaziyi Diske Yaz', {})
    ydz_tgts = [t['node'] for chain in ydz.get('main', []) for t in chain]
    assert 'EN Cevir Prompt' in ydz_tgts, ydz_tgts

    OUT.write_text(json.dumps(wf, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {OUT}')
    print(f'Nodes: {len(nodes)}')
    print('Write path: Tam Saate Bekle -> Post Verisini Geri Yukle -> Frontmatter Olustur -> Dosya Adi Dogrula -> Markdown Dosyasina Cevir -> Yaziyi Diske Yaz')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
