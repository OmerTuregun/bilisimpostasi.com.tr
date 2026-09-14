#!/usr/bin/env python3
"""Aşama 55: Claude çıktısına etiket alanı + frontmatter tags."""
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

TAG_PROMPT_BLOCK = """
ETİKETLER: [etiket1, etiket2, etiket3]
Link: {{ $json.link }}
İÇERİK:
[markdown]

ETİKET KURALLARI:
- Yazıyla birlikte 2–4 ilgili etiket üret (ör. nvidia, openai, robotik, kripto).
- Slug formatı: küçük harf, Türkçe karakter yok, boşluk yerine tire.
- Sadece a-z, 0-9 ve tire kullan; her etiket 2–28 karakter.
"""

TAG_PROMPT_REPLACE_OLD = """KATEGORİ: [Yapay Zeka | Teknoloji | Güvenlik]
Link: {{ $json.link }}
İÇERİK:
[markdown]"""

TAG_PROMPT_REPLACE_NEW = """KATEGORİ: [Yapay Zeka | Teknoloji | Güvenlik]
ETİKETLER: [etiket1, etiket2, etiket3]
Link: {{ $json.link }}
İÇERİK:
[markdown]

ETİKET KURALLARI:
- Yazıyla birlikte 2–4 ilgili etiket üret (ör. nvidia, openai, robotik, kripto).
- Slug formatı: küçük harf, Türkçe karakter yok, boşluk yerine tire.
- Sadece a-z, 0-9 ve tire kullan; her etiket 2–28 karakter."""

PARSE_TAGS_HELPER = """
function slugifyTag(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/ğ/g, 'g')
    .replace(/ü/g, 'u')
    .replace(/ş/g, 's')
    .replace(/ı/g, 'i')
    .replace(/ö/g, 'o')
    .replace(/ç/g, 'c')
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

function parseTagsLine(line) {
  if (!line) return [];
  const raw = String(line).trim();
  const inner = raw.replace(/^\\[/, '').replace(/\\]$/, '').trim();
  if (!inner) return [];
  return inner
    .split(',')
    .map((t) => slugifyTag(t.trim()))
    .filter((t) => t.length >= 2)
    .slice(0, 4);
}
"""

FRONTMATTER_TAGS_SNIPPET = """
  const etiketler = Array.isArray(j.etiketler) ? j.etiketler : [];
  const tagsYaml = etiketler.length
    ? `tags:\\n${etiketler.map((t) => `  - ${t}`).join('\\n')}\\n`
    : '';
"""


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-asama55-tags.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-asama55-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-asama55-pre.json', str(out)], check=True)
    return out


def patch_prompt(content: str) -> str:
    if 'ETİKETLER:' in content:
        return content
    if TAG_PROMPT_REPLACE_OLD not in content:
        raise SystemExit('Claude prompt: expected KATEGORİ/Link/İÇERİK block')
    return content.replace(TAG_PROMPT_REPLACE_OLD, TAG_PROMPT_REPLACE_NEW)


def patch_ayristir(code: str) -> str:
    if 'parseTagsLine' in code:
        return code
    if 'function parseBlock(b, fallbackLink)' not in code:
        raise SystemExit('Yazilari Ayristir: parseBlock not found')
    code = code.replace(
        'function parseBlock(b, fallbackLink) {',
        PARSE_TAGS_HELPER + '\nfunction parseBlock(b, fallbackLink) {',
    )
    code = code.replace(
        "  const kategoriMatch = b.match(/KATEGORİ:\\s*(.+)/);",
        "  const kategoriMatch = b.match(/KATEGORİ:\\s*(.+)/);\n"
        "  const etiketlerMatch = b.match(/ETİKETLER:\\s*(\\[[^\\]\\n]+\\]|[^\\n]+)/i);",
    )
    code = code.replace(
        "  const kategori = kategoriMatch ? kategoriMatch[1].trim() : 'Teknoloji';",
        "  const kategori = kategoriMatch ? kategoriMatch[1].trim() : 'Teknoloji';\n"
        "  const etiketler = etiketlerMatch ? parseTagsLine(etiketlerMatch[1]) : [];",
    )
    code = code.replace(
        "  return { baslik, ozet, kategori, link, icerik };",
        "  return { baslik, ozet, kategori, etiketler, link, icerik };",
    )
    return code


def patch_frontmatter(code: str) -> str:
    if 'tagsYaml' in code:
        return code
    needle = "  const kategori = String(j.kategori || 'Teknoloji');"
    if needle not in code:
        raise SystemExit('Frontmatter Olustur: kategori line not found')
    code = code.replace(
        needle,
        needle + FRONTMATTER_TAGS_SNIPPET,
    )
    code = code.replace(
        '    `kategori: "${esc(kategori)}"\\n` +',
        '    `kategori: "${esc(kategori)}"\\n` +\n    tagsYaml +',
    )
    code = code.replace(
        "      kategori,\n      link,",
        "      kategori,\n      etiketler,\n      link,",
    )
    return code


def patch_en_markdown(code: str) -> str:
    if 'tagsYaml' in code and 'en_markdown_icerik' in code:
        # may already be patched partially
        if 'tags:\\n' in code.split('en_markdown_icerik')[1][:800]:
            return code
    insert_after = "  const category = categoryMap[src.tr_kategori] || 'Technology';"
    if insert_after not in code:
        raise SystemExit('EN Markdown Olustur: category line not found')
    en_tags = """
  const etiketler = Array.isArray(src.etiketler)
    ? src.etiketler
    : (fmAll[idx] && fmAll[idx].json && fmAll[idx].json.etiketler) || [];
  const tagsYaml = etiketler.length
    ? `tags:\\n${etiketler.map((t) => `  - ${t}`).join('\\n')}\\n`
    : '';
"""
    code = code.replace(insert_after, insert_after + en_tags)
    code = code.replace(
        '    `kategori: "${category}"\\n` +',
        '    `kategori: "${category}"\\n` +\n    tagsYaml +',
    )
    return code


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    claude = by['Claude Toplu Yazi Uret']
    claude['parameters']['messages']['values'][0]['content'] = patch_prompt(
        claude['parameters']['messages']['values'][0]['content']
    )

    by['Yazilari Ayristir']['parameters']['jsCode'] = patch_ayristir(
        by['Yazilari Ayristir']['parameters']['jsCode']
    )
    by['Frontmatter Olustur']['parameters']['jsCode'] = patch_frontmatter(
        by['Frontmatter Olustur']['parameters']['jsCode']
    )
    by['EN Markdown Olustur']['parameters']['jsCode'] = patch_en_markdown(
        by['EN Markdown Olustur']['parameters']['jsCode']
    )

    out = BACKUP / 'haber-yayinlama-asama55-tags-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-asama55.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-asama55.json'],
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
    prompt = by['Claude Toplu Yazi Uret']['parameters']['messages']['values'][0]['content']
    ay = by['Yazilari Ayristir']['parameters']['jsCode']
    fm = by['Frontmatter Olustur']['parameters']['jsCode']
    en = by['EN Markdown Olustur']['parameters']['jsCode']
    assert 'ETİKETLER:' in prompt
    assert 'parseTagsLine' in ay
    assert 'tagsYaml' in fm
    assert 'tagsYaml' in en
    print('verify OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify()


if __name__ == '__main__':
    main()
