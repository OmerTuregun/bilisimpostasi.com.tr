#!/usr/bin/env python3
"""Fix Anahtar Kelime Cikar: whitespace bug, metaphor filter, multi-item return."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUPS = ROOT / 'n8n/backups'
WF_ID = 'zVyc6gzToDe5mhc2'

# Fixed keyword extraction — process ALL items; prefer topic over metaphor.
ANAHTAR_CODE = r'''function buildQuery(baslik, kategori) {
  const title = String(baslik || '').trim();
  const cat = String(kategori || '').trim();

  const catMap = {
    'Yapay Zeka': 'artificial intelligence technology',
    'AI': 'artificial intelligence technology',
    'Teknoloji': 'technology innovation',
    'Technology': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
    'Security': 'cybersecurity digital security',
    'Siber Güvenlik': 'cybersecurity digital security',
    'Donanım': 'computer hardware',
    'Yazılım': 'software development',
  };

  // Metaphorical / sentiment verbs that produce literal Unsplash junk (snow, explosion, fire…)
  const METAPHOR = new Set([
    'soguyor', 'soğuyor', 'isiniyor', 'ısınıyor', 'patliyor', 'patlıyor', 'patlama',
    'cokuyor', 'çöküyor', 'dusuyor', 'düşüyor', 'yukseliyor', 'yükseliyor',
    'artis', 'artış', 'dusus', 'düşüş', 'patladi', 'patladı', 'sogudu', 'soğudu',
    'cooling', 'heating', 'booming', 'crashing', 'soaring', 'plunging',
  ]);

  const STOP = new Set([
    've', 'bu', 'de', 'da', 'ile', 'icin', 'için', 'bir', 'her', 'yeni', 'son',
    'gibi', 'daha', 'cok', 'çok', 'olan', 'olarak', 'uzerine', 'üzerine',
    'the', 'a', 'an', 'of', 'for', 'to', 'in', 'on', 'with',
  ]);

  // Topic phrase shortcuts (order matters — longer first)
  const TOPIC_PHRASES = [
    [/yapay\s+zeka/i, 'artificial intelligence'],
    [/\bai\b/i, 'artificial intelligence'],
    [/buyuk\s+dil\s+model/i, 'large language model AI'],
    [/b[uü]y[uü]k\s+dil\s+model/i, 'large language model AI'],
    [/openai/i, 'openai artificial intelligence'],
    [/claude|anthropic/i, 'artificial intelligence chatbot'],
    [/google|gemini/i, 'google technology'],
    [/meta\b|llama/i, 'meta artificial intelligence'],
    [/drone|i[tT]faiyeci|teslimat/i, 'delivery drone'],
    [/otonom|robotaksi|waymo/i, 'autonomous vehicle'],
    [/kodlama|yazilim|yazılım|codex/i, 'software coding'],
    [/siber|guvenlik|güvenlik|hack/i, 'cybersecurity'],
  ];

  for (const [re, q] of TOPIC_PHRASES) {
    if (re.test(title)) return q;
  }

  if (catMap[cat]) return catMap[cat];

  // Tokenize on real whitespace (NOT over-escaped)
  const words = title.split(/\s+/).filter(Boolean);
  const cleaned = words
    .map((w) => w.replace(/[^\wçğıöşüÇĞİÖŞÜ-]/gi, ''))
    .filter((w) => w.length > 2)
    .filter((w) => !STOP.has(w.toLowerCase()))
    .filter((w) => !METAPHOR.has(w.toLowerCase()));

  // Prefer multi-word known tech tokens / Capitalized runs without metaphor
  const proper = cleaned.filter((w) => /^[A-ZÇĞİÖŞÜ]/.test(w));
  if (proper.length >= 2) {
    return proper.slice(0, 2).join(' ');
  }
  if (proper.length === 1 && proper[0].length >= 4) {
    const fallback = catMap[cat] || 'technology';
    // Avoid single metaphor-adjacent leftover; pair with category
    return `${proper[0]} ${fallback}`.trim();
  }

  if (cleaned.length >= 2) {
    return cleaned.slice(0, 2).join(' ');
  }

  return catMap[cat] || cat || 'technology';
}

return $input.all().map((item) => {
  const j = item.json || {};
  const query = buildQuery(j.baslik || j.title || '', j.kategori || '');
  return {
    json: {
      ...j,
      gorsel_query: query,
    },
  };
});
'''

# Gorsel Bilgi Hazirla — process each Unsplash item, pair with Anahtar by index
GORSEL_BILGI_CODE = r'''const anahtarItems = $('Anahtar Kelime Cikar').all();

return $input.all().map((item, idx) => {
  const results = item.json.results || [];
  const photo = results[0] || {};
  const imageUrl = (photo.urls && (photo.urls.regular || photo.urls.small)) || '';
  const downloadLocation = (photo.links && photo.links.download_location) || '';
  const userName = (photo.user && photo.user.name) || '';
  const userLink = (photo.user && photo.user.links && photo.user.links.html) || '';

  const src = (anahtarItems[idx] && anahtarItems[idx].json) || $('Anahtar Kelime Cikar').item.json || {};
  const baslik = src.baslik || 'post';
  const slug = String(baslik)
    .toLowerCase()
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ı/g, 'i')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
  const ts = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14);
  const dosya_adi = slug.slice(0, 50) + '-' + ts + '.jpg';

  return {
    json: {
      ...src,
      gorsel_query: src.gorsel_query || '',
      gorsel_url: imageUrl,
      gorsel_download_location: downloadLocation,
      gorsel_fotografci: userName,
      gorsel_fotografci_link: userLink ? userLink + '?utm_source=bilisimpostasi&utm_medium=referral' : '',
      gorsel_kaynak_link: 'https://unsplash.com/?utm_source=bilisimpostasi&utm_medium=referral',
      gorsel_dosya_adi: dosya_adi,
      gorsel_unsplash_id: photo.id || '',
      gorsel_unsplash_alt: photo.alt_description || photo.description || '',
    },
  };
});
'''

GORSEL_YOK_CODE = r'''const anahtarItems = $('Anahtar Kelime Cikar').all();
return $input.all().map((item, idx) => {
  const src = (anahtarItems[idx] && anahtarItems[idx].json) || item.json || {};
  return {
    json: {
      ...src,
      gorsel_r2_url: '',
      gorsel_url: '',
      gorsel_fotografci: '',
      gorsel_fotografci_link: '',
      gorsel_kaynak_link: '',
      gorsel_query: src.gorsel_query || '',
    },
  };
});
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUPS / f'haber-yayinlama-toplu-{stamp}-pre-unsplash-keyword-fix.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={WF_ID}', '--output=/tmp/wf-unsplash-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-unsplash-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = data[0] if isinstance(data, list) else data

    renamed = {
        'Anahtar Kelime Cikar': ANAHTAR_CODE,
        'Gorsel Bilgi Hazirla': GORSEL_BILGI_CODE,
        'Gorsel Yok Gecis': GORSEL_YOK_CODE,
    }
    # also try alternate names
    found = set()
    for n in wf['nodes']:
        name = n['name']
        if name in renamed:
            n['parameters']['jsCode'] = renamed[name]
            found.add(name)
        # Frontmatter: persist gorsel_query into markdown as HTML comment is ugly;
        # add to returned json and into frontmatter as gorselQuery
        if name == 'Frontmatter Olustur':
            code = n['parameters'].get('jsCode', '')
            if 'gorselQuery' not in code:
                code = code.replace(
                    'const cover = String(j.gorsel_r2_url || j.coverImage || j.cover_image || \'\');',
                    "const cover = String(j.gorsel_r2_url || j.coverImage || j.cover_image || '');\n"
                    "const gorselQuery = String(j.gorsel_query || '').trim();",
                )
                code = code.replace(
                    '  `gorselFotografciLink: "${esc(fotografciLink)}"\\n` +\n'
                    '  `---\\n` +',
                    '  `gorselFotografciLink: "${esc(fotografciLink)}"\\n` +\n'
                    '  `gorselQuery: "${esc(gorselQuery)}"\\n` +\n'
                    '  `---\\n` +',
                )
                code = code.replace(
                    '    coverImage: j.coverImage || cover,\n',
                    '    coverImage: j.coverImage || cover,\n'
                    '    gorsel_query: gorselQuery,\n'
                    '    gorselQuery,\n',
                )
                n['parameters']['jsCode'] = code
                found.add('Frontmatter Olustur+gorselQuery')

    missing = set(renamed) - found
    if missing:
        # Gorsel Yok might have different name
        names = [n['name'] for n in wf['nodes']]
        print('WARNING missing nodes:', missing)
        print('available:', [x for x in names if 'Gorsel' in x or 'Anahtar' in x])

    out = BACKUPS / 'haber-yayinlama-toplu-unsplash-keyword-fixed.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('patched', out, 'found', sorted(found))
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-unsplash-fixed.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-unsplash-fixed.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    print('import+publish+restart done')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)


if __name__ == '__main__':
    main()
