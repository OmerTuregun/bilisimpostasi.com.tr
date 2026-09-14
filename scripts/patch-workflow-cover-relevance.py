#!/usr/bin/env python3
"""Fix Unsplash keyword + relevance scoring; stop junk covers like random street signs."""
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

ANAHTAR_CODE = r'''function buildQuery(baslik, kategori, ozet) {
  const title = String(baslik || '').trim();
  const summary = String(ozet || '').trim();
  const haystack = (title + ' ' + summary).toLowerCase();

  // Category may be "Yapay Zeka | Teknoloji" — take first known token
  const catRaw = String(kategori || '').trim();
  const catParts = catRaw.split(/[|/·,]/).map((s) => s.trim()).filter(Boolean);
  const catMap = {
    'Yapay Zeka': 'artificial intelligence semiconductor',
    'AI': 'artificial intelligence semiconductor',
    'Teknoloji': 'technology innovation',
    'Technology': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
    'Security': 'cybersecurity digital security',
    'Siber Güvenlik': 'cybersecurity digital security',
    'Donanım': 'computer hardware chip',
    'Yazılım': 'software development coding',
  };
  let catQuery = '';
  for (const p of catParts) {
    if (catMap[p]) { catQuery = catMap[p]; break; }
  }

  const TOPIC_PHRASES = [
    [/cerebras|yarıiletken|yariiletken|semiconductor|chip\b|mikroişlem|mikroislem/i, 'semiconductor chip artificial intelligence'],
    [/nvidia|gpu|cuda/i, 'nvidia gpu technology'],
    [/openai|chatgpt/i, 'openai artificial intelligence'],
    [/claude|anthropic/i, 'artificial intelligence chatbot'],
    [/google|gemini|deepmind/i, 'google technology artificial intelligence'],
    [/meta\b|llama|facebook/i, 'meta artificial intelligence'],
    [/apple|iphone|ipad|mac\b/i, 'apple technology product'],
    [/tesla|robotaxi|waymo|otonom/i, 'autonomous vehicle technology'],
    [/yatırım|yatirim|venture|investor|startup|fonu|mayfield/i, 'venture capital technology office'],
    [/siber|güvenlik|guvenlik|hack|malware|phishing/i, 'cybersecurity digital security'],
    [/drone|teslimat/i, 'delivery drone technology'],
    [/veri merkezi|datacenter|data center/i, 'data center server room'],
    [/yapay\s+zeka|\bai\b/i, 'artificial intelligence technology'],
    [/robot|robotik/i, 'robotics technology'],
    [/bulut|cloud|aws|azure/i, 'cloud computing servers'],
    [/kripto|bitcoin|blockchain/i, 'cryptocurrency technology'],
  ];

  for (const [re, q] of TOPIC_PHRASES) {
    if (re.test(haystack)) return q;
  }

  if (catQuery) return catQuery;

  // Never search bare person names — Unsplash returns random portraits/signs.
  // Prefer category / generic tech fallback.
  return catQuery || 'technology innovation abstract';
}

return $input.all().map((item) => {
  const j = item.json || {};
  const query = buildQuery(j.baslik || j.title || '', j.kategori || '', j.ozet || j.description || '');
  console.log('[gorsel_query] ' + JSON.stringify({ baslik: (j.baslik || '').slice(0, 60), query }));
  return {
    json: {
      ...j,
      gorsel_query: query,
    },
  };
});
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-cover-relevance.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-cover-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-cover-pre.json', str(out)], check=True)
    return out


def patch_gorsel_select(code: str) -> str:
    """Inject relevance scoring into candidate loop in Gorsel Bilgi Hazirla."""
    if 'scoreRelevance' in code:
        return code

    helper = r'''
function scoreRelevance(photo, query) {
  const q = String(query || '').toLowerCase();
  const qTokens = q.split(/\s+/).filter((t) => t.length > 2);
  const text = [
    photo.alt_description,
    photo.description,
    photo.slug,
    ...((photo.tags || []).map((t) => (t && t.title) || t || '')),
  ]
    .join(' ')
    .toLowerCase();

  // Hard reject obvious junk for tech articles
  const JUNK = /\b(sign|plaque|street|restaurant|cafe|mosque|church|wedding|portrait|selfie|dog|cat|food|meal|beach vacation|derneği|dernegi)\b/i;
  if (JUNK.test(text)) return -100;

  if (!qTokens.length) return 0;
  let score = 0;
  for (const t of qTokens) {
    if (text.includes(t)) score += 3;
  }
  // Prefer photos that at least mention tech-ish words when query is tech
  const TECH = /\b(chip|circuit|computer|server|robot|ai|artificial|intelligence|technology|code|software|hardware|data|network|digital)\b/i;
  if (TECH.test(q) && TECH.test(text)) score += 4;
  if (TECH.test(q) && !TECH.test(text) && text.length > 10) score -= 2;
  return score;
}

'''
    # Insert helper before `const out = [];`
    if 'const out = [];' not in code:
        raise SystemExit('Gorsel Bilgi Hazirla: const out marker missing')
    code = code.replace('const out = [];', helper + '\nconst out = [];', 1)

    # Replace naive first-available pick with scored pick
    old_loop = '''  for (let r = 0; r < results.length; r++) {
    const cand = results[r] || {};
    const id = String(cand.id || '').trim();
    if (!id) continue;
    if (isBlocked(id)) continue;
    chosen = cand;
    chosenRank = r;
    break;
  }'''
    new_loop = '''  let bestScore = -Infinity;
  const queryHint = String(src.gorsel_query || '');
  for (let r = 0; r < results.length; r++) {
    const cand = results[r] || {};
    const id = String(cand.id || '').trim();
    if (!id) continue;
    if (isBlocked(id)) continue;
    const sc = scoreRelevance(cand, queryHint);
    if (sc < 0) continue; // junk
    // Prefer higher relevance; tie-break earlier Unsplash rank
    if (sc > bestScore || (sc === bestScore && chosenRank < 0)) {
      bestScore = sc;
      chosen = cand;
      chosenRank = r;
    }
  }
  // If all scored negative, fall back to first unblocked (last resort)
  if (!chosen) {
    for (let r = 0; r < results.length; r++) {
      const cand = results[r] || {};
      const id = String(cand.id || '').trim();
      if (!id || isBlocked(id)) continue;
      chosen = cand;
      chosenRank = r;
      console.log('[cover_relevance_fallback] ' + JSON.stringify({ query: queryHint, id }));
      break;
    }
  } else {
    console.log('[cover_relevance] ' + JSON.stringify({ query: queryHint, id: chosen.id, score: bestScore, rank: chosenRank }));
  }'''
    if old_loop not in code:
        raise SystemExit('Gorsel Bilgi Hazirla: pick loop not found')
    code = code.replace(old_loop, new_loop, 1)
    return code


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    by['Anahtar Kelime Cikar']['parameters']['jsCode'] = ANAHTAR_CODE
    by['Gorsel Bilgi Hazirla']['parameters']['jsCode'] = patch_gorsel_select(
        by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    )

    out = BACKUP / 'haber-yayinlama-cover-relevance-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-cover.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-cover.json'],
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
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )


def fix_cerebras_cover() -> None:
    """Replace junk cover on the live Cerebras post with a chip/AI photo."""
    import re
    import urllib.request

    key = (ROOT / 'n8n/.env').read_text()
    m = re.search(r'^UNSPLASH_ACCESS_KEY=(.+)$', key, re.M)
    if not m:
        raise SystemExit('no unsplash key')
    api_key = m.group(1).strip()
    req = urllib.request.Request(
        'https://api.unsplash.com/search/photos?query=semiconductor%20chip%20circuit%20board&per_page=5&orientation=landscape',
        headers={'Authorization': f'Client-ID {api_key}'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    # Prefer a real circuit/chip photo
    photo = None
    for p in data.get('results') or []:
        alt = (p.get('alt_description') or '') + ' ' + (p.get('description') or '')
        if re.search(r'circuit|chip|board|semiconductor|computer', alt, re.I):
            photo = p
            break
    if not photo:
        photo = (data.get('results') or [None])[0]
    if not photo:
        raise SystemExit('no photo')

    raw_url = (photo.get('urls') or {}).get('regular') or ''
    image_url = raw_url + ('&' if '?' in raw_url else '?') + 'w=1200&q=80&fm=jpg&fit=max'
    user = photo.get('user') or {}
    name = user.get('name') or ''
    link = ((user.get('links') or {}).get('html') or '') + '?utm_source=bilisimpostasi&utm_medium=referral'

    paths = list((ROOT / 'site/src/content/posts/tr').glob('*cerebras*'))
    paths += list((ROOT / 'site/src/content/posts/en').glob('*cerebras*'))
    for path in paths:
        text = path.read_text(encoding='utf-8')
        text2 = re.sub(r'^coverImage: ".*"$', f'coverImage: "{image_url}"', text, count=1, flags=re.M)
        text2 = re.sub(r'^gorselFotografci: ".*"$', f'gorselFotografci: "{name}"', text2, count=1, flags=re.M)
        text2 = re.sub(
            r'^gorselFotografciLink: ".*"$',
            f'gorselFotografciLink: "{link}"',
            text2,
            count=1,
            flags=re.M,
        )
        if 'gorselQuery:' in text2:
            text2 = re.sub(
                r'^gorselQuery: ".*"$',
                'gorselQuery: "semiconductor chip artificial intelligence"',
                text2,
                count=1,
                flags=re.M,
            )
        path.write_text(text2, encoding='utf-8')
        print('updated', path.name, '->', name, photo.get('id'))

    # Trigger download tracking (best-effort)
    dl = (photo.get('links') or {}).get('download_location')
    if dl:
        try:
            urllib.request.urlopen(
                urllib.request.Request(dl, headers={'Authorization': f'Client-ID {api_key}'}),
                timeout=15,
            ).read(64)
        except Exception:
            pass


def main() -> None:
    fix_cerebras_cover()
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    # verify
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    by = {n['name']: n for n in json.loads(raw)}
    assert 'semiconductor chip' in by['Anahtar Kelime Cikar']['parameters']['jsCode']
    assert 'scoreRelevance' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    assert 'JUNK' in by['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    print('VERIFY OK')


if __name__ == '__main__':
    main()
