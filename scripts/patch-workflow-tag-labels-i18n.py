#!/usr/bin/env python3
"""Etiketler: slug + TR/EN görünen ad (otomatik i18n, frontmatter tagLabels)."""
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

TAG_RULES_OLD = """ETİKET KURALLARI:
- Yazıyla birlikte 2–4 ilgili etiket üret (ör. nvidia, openai, robotik, kripto).
- Slug formatı: küçük harf, Türkçe karakter yok, boşluk yerine tire.
- Sadece a-z, 0-9 ve tire kullan; her etiket 2–28 karakter."""

TAG_RULES_NEW = """ETİKET KURALLARI:
- Yazıyla birlikte 2–4 ilgili etiket üret.
- Format: slug|TR görünen ad|EN görünen ad (ör. guvenlik|Güvenlik|Security, llama|Llama|Llama).
- Slug: küçük harf, Türkçe karakter yok, boşluk yerine tire; sadece a-z, 0-9 ve tire; 2–28 karakter.
- TR ve EN görünen adlar kısa ve doğal olsun (1–4 kelime)."""

TAG_PROMPT_LINE_OLD = 'ETİKETLER: [etiket1, etiket2, etiket3]'
TAG_PROMPT_LINE_NEW = 'ETİKETLER: [slug|TR ad|EN ad, slug2|TR ad2|EN ad2]'

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

function titleCaseSlug(slug) {
  return String(slug || '')
    .split('-')
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ');
}

function parseTagsLine(line) {
  const empty = { slugs: [], labels: {} };
  if (!line) return empty;
  const raw = String(line).trim();
  const inner = raw.replace(/^\\[/, '').replace(/\\]$/, '').trim();
  if (!inner) return empty;
  const slugs = [];
  const labels = {};
  for (const part of inner.split(',').map((t) => t.trim()).filter(Boolean).slice(0, 4)) {
    const bits = part.split('|').map((t) => t.trim());
    const slug = slugifyTag(bits[0] || '');
    if (slug.length < 2) continue;
    slugs.push(slug);
    const tr = (bits[1] || titleCaseSlug(slug)).trim();
    const en = (bits[2] || bits[1] || titleCaseSlug(slug)).trim();
    labels[slug] = { tr, en };
  }
  return { slugs, labels };
}
"""

FRONTMATTER_TAG_LABELS_SNIPPET = """
  const tagLabels = (j.tagLabels && typeof j.tagLabels === 'object') ? j.tagLabels : {};
  const tagLabelsYaml = (() => {
    const keys = Object.keys(tagLabels);
    if (!keys.length) return '';
    const lines = keys.map((k) => {
      const lb = tagLabels[k] || {};
      return `  ${k}:\\n    tr: "${esc(lb.tr || k)}"\\n    en: "${esc(lb.en || k)}"`;
    });
    return `tagLabels:\\n${lines.join('\\n')}\\n`;
  })();
"""


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-tag-labels-i18n.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-tag-labels-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-tag-labels-pre.json', str(out)], check=True)
    return out


def patch_prompt(content: str) -> str:
    content = content.replace(TAG_PROMPT_LINE_OLD, TAG_PROMPT_LINE_NEW)
    content = content.replace(TAG_RULES_OLD, TAG_RULES_NEW)
    if 'slug|TR ad|EN ad' not in content:
        raise SystemExit('Claude prompt: ETİKETLER format not updated')
    return content


def patch_ayristir(code: str) -> str:
    if 'titleCaseSlug' in code and 'tagLabels' in code and 'parseTagsLine' in code:
        # Re-patch parseTagsLine body if old version
        if 'const slugs = []' in code and 'labels[slug]' in code:
            return code

    # Replace old parseTags helper block
    start = code.find('function slugifyTag(s)')
    end = code.find('function parseBlock(b, fallbackLink)')
    if start == -1 or end == -1:
        raise SystemExit('Yazilari Ayristir: slugifyTag/parseBlock not found')
    code = code[:start] + PARSE_TAGS_HELPER.strip() + '\n\n' + code[end:]

    code = code.replace(
        '  const etiketler = etiketlerMatch ? parseTagsLine(etiketlerMatch[1]) : [];',
        '  const tagParsed = etiketlerMatch ? parseTagsLine(etiketlerMatch[1]) : { slugs: [], labels: {} };\n'
        '  const etiketler = tagParsed.slugs;\n'
        '  const tagLabels = tagParsed.labels;',
    )
    code = code.replace(
        '  return { baslik, ozet, kategori, etiketler, link, icerik };',
        '  return { baslik, ozet, kategori, etiketler, tagLabels, link, icerik };',
    )
    return code


def patch_frontmatter(code: str) -> str:
    if 'tagLabelsYaml' in code:
        return code
    needle = '  const tagsYaml = etiketler.length'
    if needle not in code:
        raise SystemExit('Frontmatter Olustur: tagsYaml block not found')
    insert_at = code.find(needle)
    line_end = code.find('\n', insert_at)
    while line_end != -1 and code[line_end + 1 : line_end + 5] == '    ':
        line_end = code.find('\n', line_end + 1)
    code = code[: line_end + 1] + FRONTMATTER_TAG_LABELS_SNIPPET + code[line_end + 1 :]
    code = code.replace(
        '    tagsYaml +\n',
        '    tagsYaml +\n    tagLabelsYaml +\n',
        1,
    )
    code = code.replace(
        '      etiketler,\n      link,',
        '      etiketler,\n      tagLabels,\n      link,',
    )
    if 'const tagLabels = (j.tagLabels' not in code:
        code = code.replace(
            '  const etiketler = Array.isArray(j.etiketler) ? j.etiketler : [];',
            '  const etiketler = Array.isArray(j.etiketler) ? j.etiketler : [];\n'
            '  const tagLabels = (j.tagLabels && typeof j.tagLabels === \'object\') ? j.tagLabels : {};',
        )
    return code


def patch_en_markdown(code: str) -> str:
    # Repair TDZ if a previous patch left esc() after tagLabelsYaml usage.
    if 'tagLabelsYaml' in code and "const esc = (s) => String(s || '').replace(/\"/g, \"'\");" in code:
        esc_line = "  const esc = (s) => String(s || '').replace(/\"/g, \"'\");\n"
        if code.find(esc_line.strip()) > code.find('tagLabelsYaml'):
            code = code.replace(esc_line, '', 1)
            insert_at = code.find('  const etiketler = Array.isArray(src.etiketler)')
            if insert_at < 0:
                raise SystemExit('EN Markdown Olustur: etiketler line not found for esc move')
            code = code[:insert_at] + esc_line + code[insert_at:]
        return code
    if 'tagLabelsYaml' in code:
        return code
    insert_after = '  const tagsYaml = etiketler.length\n    ? `tags:\\n${etiketler.map((t) => `  - ${t}`).join(\'\\n\')}\\n`\n    : \'\';'
    if insert_after not in code:
        raise SystemExit('EN Markdown Olustur: tagsYaml block not found')
    # Declare esc BEFORE tagLabelsYaml (temporal dead zone otherwise).
    en_labels = """
  const esc = (s) => String(s || '').replace(/"/g, "'");
  const tagLabels = (src.tagLabels && typeof src.tagLabels === 'object')
    ? src.tagLabels
    : ((fmAll[idx] && fmAll[idx].json && fmAll[idx].json.tagLabels) || {});
  const tagLabelsYaml = (() => {
    const keys = Object.keys(tagLabels);
    if (!keys.length) return '';
    const lines = keys.map((k) => {
      const lb = tagLabels[k] || {};
      return `  ${k}:\\n    tr: "${esc(lb.tr || k)}"\\n    en: "${esc(lb.en || k)}"`;
    });
    return `tagLabels:\\n${lines.join('\\n')}\\n`;
  })();
"""
    code = code.replace(insert_after, insert_after + en_labels)
    # Remove the later duplicate esc declaration if present.
    code = code.replace(
        "\n  const esc = (s) => String(s || '').replace(/\"/g, \"'\");\n  const pubDate =",
        "\n  const pubDate =",
        1,
    )
    code = code.replace(
        '    tagsYaml +\n',
        '    tagsYaml +\n    tagLabelsYaml +\n',
        1,
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

    out = BACKUP / 'haber-yayinlama-tag-labels-i18n-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-tag-labels.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-tag-labels.json'],
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
    assert 'slug|TR ad|EN ad' in prompt
    assert 'tagLabels' in ay and 'labels[slug]' in ay
    assert 'tagLabelsYaml' in fm
    assert 'tagLabelsYaml' in en
    print('verify OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify()


if __name__ == '__main__':
    main()
