#!/usr/bin/env python3
"""Revert TR to Haiku + one Claude call per news item + truncation guards.

Cost-safe: stays on Haiku (no Sonnet). Preferred approach (a): per-item calls.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
SRC = BACKUP / 'haber-yayinlama-live-current.json'
if not SRC.exists():
    SRC = BACKUP / 'haber-yayinlama-live-pre-haiku-peritem.json'

HAIKU = 'claude-haiku-4-5-20251001'
TR_MAX = 4096  # one article: ~600-700 Turkish words ≈ 900-1400 tokens; 4096 is enough headroom
EN_MAX = 8192

LIST_CODE = r'''const satirlar = $json.data.trim().split('\n').filter(s => s.trim().length > 0);
const makaleler = satirlar.map(s => JSON.parse(s));
// One item per news → one Haiku call each (no shared maxTokens budget).
return makaleler.map((m) => ({
  json: {
    baslik: m.baslik || '',
    ozet: m.ozet || '',
    link: m.link || '',
    kaynak: m.kaynak || '',
  },
}));
'''

TR_PROMPT = """=Aşağıdaki TEK teknoloji/AI haberinden BİR blog yazısı üret.

Kaynak haber:
Başlık: {{ $json.baslik }}
Özet: {{ $json.ozet }}
Link: {{ $json.link }}
Kaynak: {{ $json.kaynak }}

SADECE teknoloji ve yapay zeka konulu haberleri işle. Siyaset, göçmenlik,
iç güvenlik, spor, magazin, şirket içi rutin atama gibi düşük değerli
içerikleri KESİNLİKLE atla. Uymuyorsa başka hiçbir şey yazma, SADECE
tek kelime olarak "ATLA" yaz.

Uygunsa çıktı formatı (başka hiçbir şey yazma):

===YAZI===
BAŞLIK: [tek satır, çekici başlık, ** veya tırnak kullanma]
ÖZET: [tek satır kısa özet, ** veya tırnak kullanma]
KATEGORİ: [Yapay Zeka | Teknoloji | Güvenlik]
Link: {{ $json.link }}
İÇERİK:
[markdown]

MUTLAK UZUNLUK VE BİTİŞ:
- İÇERİK minimum 550 kelime, hedef 600–700 kelime.
- En az 6 paragraf yaz. Her paragraf en az 80–100 kelime olsun.
- 400 kelimenin altında yazmak YASAK.
- Yapı: (1) giriş (2–3 paragraf) (2) teknik gövde (ürün/model/şirket/yöntem/
  sayılar/isimler eksiksiz, 2–3 paragraf) (3) bağlam/etki/sonuç (1–2 paragraf).
- Bitirmeden önce İÇERİK kelime sayısını say; 500’ün altındaysa ek teknik
  paragraf ekle (karşılaştırma, sınırlılık, uygulama senaryosu veya risk).
- Kelime sayısını veya “SAYISI/kelime” meta notunu çıktıya YAZMA; sadece yazı.
- Kaynağa sadık kal; uydurma özel isim/sayı yok.
- İÇERİK mutlaka tam cümleyle bitsin (nokta/ünlem/soru). Yarım bırakma YASAK.
"""

AYRISTIR_CODE = r'''const raw = ($json.content?.[0]?.text || $json.text || '').trim();
const stopReason = String(
  $json.stop_reason
  || $json.stopReason
  || $json.response?.stop_reason
  || $json.meta?.stop_reason
  || ''
).toLowerCase();

// Truncation / incomplete model stop → drop silently (do not publish).
if (stopReason && stopReason !== 'end_turn' && stopReason !== 'stop') {
  return [];
}
if (!raw || raw === 'ATLA') {
  return [];
}

function parseBlock(b) {
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
  const link = (linkMatch ? linkMatch[1].trim() : '') || ($json.link || '');
  let icerik = icerikMatch ? icerikMatch[1].trim() : '';
  // Strip accidental trailing ATLA / category lines
  icerik = icerik.replace(/\nATLA\s*$/i, '').trim();
  // Drop accidental self-reported word-count trailers (break punctuation check)
  icerik = icerik.replace(/\n---+\s*$/g, '').trim();
  icerik = icerik.replace(/\n+[*_]*\s*(?:İÇERİK\s+)?(?:KELIME\s+)?SAYISI\s*:?\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n+[*_*]*\s*(?:Kelime\s*)?Say[ıiİI]s[ıiİI]\s*:?\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n+[*_]*\s*\d+\s*kelime[*_]*\s*$/i, '').trim();
  icerik = icerik.replace(/\n---+\s*$/g, '').trim();
  icerik = icerik.replace(/\*+\s*$/g, '').trim();
  return { baslik, ozet, kategori, link, icerik };
}

let posts = [];
if (raw.includes('===YAZI===')) {
  const blocks = raw.split('===YAZI===').map((b) => b.trim()).filter(Boolean);
  posts = blocks.map(parseBlock);
} else if (/BAŞLIK:/i.test(raw) && /İÇERİK:/i.test(raw)) {
  posts = [parseBlock(raw)];
}

// Prefer item link from split news item
const itemLink = $('Haber Listesini Hazirla').item?.json?.link || $json.link || '';
posts = posts.map((p) => ({
  ...p,
  link: p.link || itemLink,
})).filter((p) => p.baslik && p.icerik);

posts = posts.filter((p) => {
  const t = String(p.icerik || '').trim();
  const words = t.split(/\s+/).filter(Boolean).length;
  if (words < 350) return false;
  if (!/[.!?…]"?$/.test(t)) return false; // mid-sentence cut
  return true;
});

if (!posts.length) return [];
return [{ json: { posts, count: posts.length } }];
'''

EN_MARKDOWN_GUARD_SNIPPET = r'''
const enStop = String($json.stop_reason || $json.stopReason || $json.response?.stop_reason || '').toLowerCase();
if (enStop && enStop !== 'end_turn' && enStop !== 'stop') {
  return [{ json: { ...src, en_skip: true, en_error: 'Claude EN truncated: ' + enStop } }];
}
'''


def load_wf(path: Path) -> dict:
    data = json.loads(path.read_text())
    return data[0] if isinstance(data, list) else data


def set_model(node: dict, model: str) -> None:
    mid = node.setdefault('parameters', {}).setdefault('modelId', {})
    if isinstance(mid, dict):
        mid['__rl'] = True
        mid['value'] = model
        mid['mode'] = mid.get('mode') or 'list'
        mid['cachedResultName'] = model
    else:
        node['parameters']['modelId'] = {
            '__rl': True,
            'value': model,
            'mode': 'list',
            'cachedResultName': model,
        }


def set_max_tokens(node: dict, value: int) -> None:
    node.setdefault('parameters', {}).setdefault('options', {})['maxTokens'] = value


def set_content(node: dict, content: str) -> None:
    vals = node.setdefault('parameters', {}).setdefault('messages', {}).setdefault('values', [{}])
    if not vals:
        vals.append({})
    vals[0]['content'] = content


def patch_en_markdown(js: str) -> str:
    if 'enStop' in js or 'Claude EN truncated' in js:
        return js
    # Insert after src / raw extraction
    needle = "const raw = ($json.content?.[0]?.text || $json.text || '').trim();"
    if needle in js:
        return js.replace(
            needle,
            needle
            + "\n"
            + "const enStop = String($json.stop_reason || $json.stopReason || $json.response?.stop_reason || '').toLowerCase();\n"
            + "if (enStop && enStop !== 'end_turn' && enStop !== 'stop') {\n"
            + "  return [{ json: { ...($('EN Cevir Prompt').item.json), en_skip: true, en_error: 'Claude EN truncated: ' + enStop } }];\n"
            + "}\n",
        )
    return js


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f'missing {SRC}')
    wf = load_wf(SRC)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    pre = BACKUP / f'haber-yayinlama-toplu-{ts}-pre-haiku-peritem-patch.json'
    pre.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding='utf-8')

    by = {n['name']: n for n in wf['nodes']}

    # 1) Haber Listesini Hazirla → emit N items
    by['Haber Listesini Hazirla']['parameters']['jsCode'] = LIST_CODE

    # 2) Claude → Haiku + single-article prompt + 4096 tokens
    tr = by['Claude Toplu Yazi Uret']
    set_model(tr, HAIKU)
    set_max_tokens(tr, TR_MAX)
    set_content(tr, TR_PROMPT)
    # Rename for clarity (optional — keep name to avoid breaking refs)
    # tr['name'] stays 'Claude Toplu Yazi Uret'

    # 3) Ayristir → per-item parse + stop_reason + length guard
    by['Yazilari Ayristir']['parameters']['jsCode'] = AYRISTIR_CODE

    # 4) EN stays Haiku; ensure maxTokens; add truncate guard in EN Markdown Olustur
    en = by['Claude EN Cevir']
    set_model(en, HAIKU)
    set_max_tokens(en, EN_MAX)

    if 'EN Markdown Olustur' in by:
        code = by['EN Markdown Olustur']['parameters'].get('jsCode', '')
        by['EN Markdown Olustur']['parameters']['jsCode'] = patch_en_markdown(code)

    # Connections unchanged: List → Claude → Ayristir → Yazilara Bol → ...
    # (List now emits multiple items; n8n runs Claude once per item)

    wf['active'] = True
    out = BACKUP / f'haber-yayinlama-toplu-{ts}-haiku-peritem-patched.json'
    out.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding='utf-8')
    print('pre', pre)
    print('out', out)
    print('TR model', tr['parameters']['modelId']['value'], 'maxTokens', tr['parameters']['options']['maxTokens'])
    print('EN model', en['parameters']['modelId']['value'], 'maxTokens', en['parameters']['options']['maxTokens'])


if __name__ == '__main__':
    main()
