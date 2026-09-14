#!/usr/bin/env python3
"""TR Sonnet + raise maxTokens; lengthen TR/EN prompts; drop short/truncated splits."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'zVyc6gzToDe5mhc2'

TR_MAX = 32000
EN_MAX = 8192
TR_MODEL = 'claude-sonnet-4-5-20250929'
EN_MODEL = 'claude-haiku-4-5-20251001'

# Prefer newest live export (v2 pre-patch, then original pre-length).
PREFERRED_SRCS = [
    BACKUP / 'haber-yayinlama-live-post-sonnet.json',
    BACKUP / 'haber-yayinlama-live-post-length-v3.json',
    BACKUP / 'haber-yayinlama-live-post-length-v2.json',
    BACKUP / 'haber-yayinlama-live-pre-length-v2.json',
    BACKUP / 'haber-yayinlama-live-pre-length.json',
    BACKUP / 'haber-yayinlama-live-post-length.json',
]

NEW_TR_PROMPT = """=Sana verilen {{ $json.makale_sayisi }} teknoloji/AI haberini değerlendir.
Konu olarak birbirine YAKIN olanları aynı grupta topla; aralarında
gerçek bir konu bağlantısı yoksa AYRI gruplara ayır. Her grup için
AYRI bir blog yazısı üreteceksin.

MUTLAK UZUNLUK KURALI (en önemli kural — diğer her şeyden önce):
- Her İÇERİK en az 550 kelime olsun; hedef 600–700 kelime.
- 300 kelimenin altında yazı üretmek YASAKTIR.
- 500 kelimenin altında yazı da YETERSİZ sayılır; yazmayı SÜRDÜR.
- Token bütçesi yetmezse ÇOK SAYIDA kısa yazı yerine AZ SAYIDA (1–2)
  tamamlanmış, 600+ kelimelik yazı üret. Kısa yazı bırakmak başarısızlıktır.
- Bitirmeden önce her İÇERİK için kelime sayını zihnen kontrol et; 550’nin
  altındaysa ek paragraf ekle (teknik bağlam, yöntem, risk, sektör etkisi).

Not: SADECE teknoloji ve yapay zeka konulu haberleri işle. Siyaset,
göçmenlik, iç güvenlik, spor, magazin gibi teknoloji/AI ile ilgisi
olmayan haberleri KESİNLİKLE dahil etme. Şirket içi personel/yönetici
atama haberleri, rutin organizasyonel değişiklikler gibi düşük haber
değeri taşıyan içerikleri de atla. Eğer hiçbir haber kritere uymuyorsa,
başka hiçbir şey yazma, SADECE tek kelime olarak "ATLA" yaz.

Her yazıyı şu formatta yaz. Yazılar arasına (ilk yazıdan önce de dahil)
tam olarak "===YAZI===" satırını koy:

===YAZI===
BAŞLIK: [tek satır, çekici bir başlık, ** veya tırnak kullanma]
ÖZET: [tek satır kısa özet, ** veya tırnak kullanma]
KATEGORİ: [şu seçeneklerden biri: Yapay Zeka, Teknoloji, Güvenlik. Haber doğrudan yapay zeka/makine öğrenmesi/LLM ile ilgiliyse "Yapay Zeka"; güvenlik/bilgi güvenliğiyle ilgili (siber saldırı, veri ihlali, zafiyet/exploit, hack/ihlaller, güvenlik güncellemeleri) ise "Güvenlik"; değilse (donanım, yazılım, girişim ve genel teknoloji) "Teknoloji" seç.]
Link: [bu yazının dayandığı haberin Link URL'si — Haberler listesinden aynen kopyala, değiştirme]
İÇERİK:
[markdown — aşağıdaki yapıya UY; toplam 600–700 kelime]

İÇERİK YAPISI (zorunlu, üç bölüm; toplam ≥550 kelime):
  1) Giriş (1 uzun paragraf, ~100–130 kelime): olay/bulgu + neden önemli.
  2) Genişletilmiş gövde (EN AZ 4 uzun paragraf, toplam ~380–480 kelime):
     kaynak detayları EKSİKSİZ (sayı, isim, ürün/model, şirket, yöntem,
     tarih, alıntı). Kaynak kısa olsa bile her paragrafı teknik açıklama,
     karşılaştırma, risk/fayda ve uygulama örneği ile genişlet; uydurma
     özel isim/sayı UYDURMA.
  3) Bağlam/etki (1–2 paragraf, ~120–160 kelime): sektör, okur, düzenleme
     veya iş etkisi; abartısız, kaynağa sadık.

Ek zorunluluklar:
- Toplam İÇERİK: MINIMUM 550, hedef 600–700 kelime.
- Her İÇERİK en az 550 kelime olsun; 300 kelimenin altında yazı üretmek YASAKTIR.
- Her İÇERİK tam cümleyle bitsin; cümle ortasında kesme YASAK.
- "Kısa tut / özetle / 2-3 cümle" YOK — uzun form editöryel haber yaz.

Haberler:
{{ $json.makale_listesi }}

ÇOK ÖNEMLİ ÇIKTI KURALI:
- Yazı ürettiysen sonuna "ATLA" yazma. "ATLA" yalnız hiçbir haber uymuyorsa.
- İÇERİK sonuna kategori / format açıklaması ekleme.
- Önce uzunluk: az ama ≥550 kelimelik tamam yazılar; yarım/kısa yazı yok.
"""

NEW_EN_PROMPT = """=You are a professional translator for a technology news website.
Translate the following Turkish article into natural, fluent English news style.
Translate by meaning, not word-for-word.
Preserve the FULL length and structure of the Turkish body (do not shorten).
Target roughly the same word count as the Turkish article (~600–700 words when the source is that long).
End BODY with complete sentences only — never truncate mid-sentence.

Return ONLY this exact format:
TITLE: [one line]
SUMMARY: [one line, max 150 chars]
CATEGORY: [AI, Technology, or Security]
BODY:
[translated markdown body only — full length]

Category mapping:
- Yapay Zeka -> AI
- Teknoloji -> Technology
- Güvenlik -> Security

Turkish title: {{ $json.tr_title }}
Turkish summary: {{ $json.tr_summary }}
Turkish category: {{ $json.tr_kategori }}
Turkish body:
{{ $json.tr_body }}
"""

# Injected after posts array is fully built (link matching included).
POSTS_LENGTH_FILTER = """
posts = posts.filter(p => {
  const t = String(p.icerik || '').trim();
  const words = t.split(/\\s+/).filter(Boolean).length;
  if (words < 400) return false;
  if (!/[.!?…]"?$/.test(t)) return false;
  return true;
});
""".strip()


def load_wf(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    return data[0] if isinstance(data, list) else data


def dump_wf(path: Path, wf: dict, as_list: bool = True) -> None:
    payload = [wf] if as_list else wf
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')



def set_model(node: dict, model_id: str) -> None:
    mid = node.setdefault('parameters', {}).get('modelId')
    if isinstance(mid, dict):
        mid['value'] = model_id
        mid['cachedResultName'] = model_id
        mid.setdefault('__rl', True)
        mid.setdefault('mode', 'list')
    else:
        node['parameters']['modelId'] = {
            '__rl': True,
            'value': model_id,
            'mode': 'list',
            'cachedResultName': model_id,
        }

def set_max_tokens(node: dict, value: int) -> None:
    opts = node.setdefault('parameters', {}).setdefault('options', {})
    opts['maxTokens'] = value


def set_message_content(node: dict, content: str) -> None:
    params = node.setdefault('parameters', {})
    if 'messages' in params:
        msgs = params['messages']
        if isinstance(msgs, dict) and 'values' in msgs and msgs['values']:
            msgs['values'][0]['content'] = content
            return
        if isinstance(msgs, list) and msgs:
            if isinstance(msgs[0], dict):
                msgs[0]['content'] = content
                return
    if 'text' in params:
        params['text'] = content
        return
    raise RuntimeError(f'Cannot find message content field on node {node.get("name")}')


def patch_ayristir(js: str) -> str:
    """After posts are built, filter short / mid-sentence-truncated bodies (icerik)."""
    js = re.sub(
        r'\nfunction looksTruncated\(body\) \{[\s\S]*?\n\}\n?',
        '\n',
        js,
    )
    js = re.sub(
        r'\nposts\s*=\s*posts\.filter\(p\s*=>\s*!looksTruncated\(p\.icerik\)\);\n?',
        '\n',
        js,
    )
    # Replace any prior length filter block (250 or other) with current version.
    js = re.sub(
        r"\nposts = posts\.filter\(p => \{\n  const t = String\(p\.icerik \|\| ''\)\.trim\(\);\n  const words = t\.split\(/\\s\+/\)\.filter\(Boolean\)\.length;\n  if \(words < \d+\) return false;\n  if \(!/\[\.!\?…\]\"\?\$/\.test\(t\)\) return false;\n  return true;\n\}\);\n?",
        '\n',
        js,
    )

    needle = 'return [{ json: { posts, count: posts.length } }];'
    if needle not in js:
        m = re.search(r'return\s*\[\s*\{\s*json:\s*\{\s*posts,\s*count:\s*posts\.length\s*\}\s*\}\s*\];', js)
        if not m:
            raise RuntimeError('Yazilari Ayristir: cannot find return posts statement')
        needle = m.group(0)

    injection = POSTS_LENGTH_FILTER + '\n\n' + needle
    if 'words < 400' in js and needle in js and POSTS_LENGTH_FILTER.split('\n')[0] in js:
        return js
    return js.replace(needle, injection, 1)


def resolve_src() -> Path:
    for pref in PREFERRED_SRCS:
        if pref.is_file():
            w = load_wf(pref)
            names = {n['name'] for n in w.get('nodes', [])}
            if 'Claude Toplu Yazi Uret' in names and 'Yazilari Ayristir' in names:
                return pref

    candidates = sorted(BACKUP.glob('wf-live-zVyc6gz*.json')) + sorted(
        BACKUP.glob('haber-yayinlama-toplu*.json')
    ) + sorted(BACKUP.glob('haber-yayinlama-live*.json'))
    if not candidates:
        raise SystemExit('no workflow backup found')
    src = candidates[-1]
    for c in reversed(candidates):
        try:
            w = load_wf(c)
            names = {n['name'] for n in w.get('nodes', [])}
            if 'Claude Toplu Yazi Uret' in names and 'Claude EN Cevir' in names:
                src = c
                break
        except Exception:
            continue
    return src


def main() -> None:
    src = resolve_src()
    wf = load_wf(src)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')

    pre = BACKUP / f'haber-yayinlama-toplu-{ts}-pre-length-v2.json'
    dump_wf(pre, wf, as_list=True)

    by_name = {n['name']: n for n in wf['nodes']}
    tr = by_name['Claude Toplu Yazi Uret']
    en = by_name['Claude EN Cevir']

    set_model(tr, TR_MODEL)
    set_model(en, EN_MODEL)
    set_max_tokens(tr, TR_MAX)
    set_max_tokens(en, EN_MAX)
    set_message_content(tr, NEW_TR_PROMPT)
    set_message_content(en, NEW_EN_PROMPT)

    node = by_name['Yazilari Ayristir']
    code = node.get('parameters', {}).get('jsCode', '')
    node['parameters']['jsCode'] = patch_ayristir(code)

    wf['active'] = True
    wf['id'] = WF_ID
    out = BACKUP / f'haber-yayinlama-toplu-{ts}-length-v2-patched.json'
    dump_wf(out, wf, as_list=True)

    patched_js = node['parameters']['jsCode']
    print('src', src)
    print('pre', pre)
    print('out', out)
    print('TR model', tr['parameters']['modelId']['value'])
    print('EN model', en['parameters']['modelId']['value'])
    print('TR maxTokens', tr['parameters']['options']['maxTokens'])
    print('EN maxTokens', en['parameters']['options']['maxTokens'])
    print('TR prompt has 550', '550' in NEW_TR_PROMPT)
    print('TR prompt has 600–700', '600–700' in NEW_TR_PROMPT)
    print('filter words < 400', 'words < 400' in patched_js)
    print('filter no 250', 'words < 250' not in patched_js)


if __name__ == '__main__':
    main()
