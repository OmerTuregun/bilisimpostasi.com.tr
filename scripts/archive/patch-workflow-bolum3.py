#!/usr/bin/env python3
"""Patch Haber Yayınlama (Toplu): auto EN translation after TR write, before deploy."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

WORKFLOW_ID = 'zVyc6gzToDe5mhc2'
ROOT = Path('/root/agent-icerik-sistemi/n8n/backups')

EN_PROMPT_CODE = r"""const src = $('Frontmatter Olustur').item.json;
return [{
  json: {
    ...src,
    tr_title: src.baslik || '',
    tr_summary: src.ozet || '',
    tr_kategori: src.kategori || 'Teknoloji',
    tr_body: src.icerik || '',
    tr_slug: (src.dosya_adi || '').replace(/\.md$/, ''),
  },
}];"""

EN_BUILD_CODE = r"""const src = $('EN Cevir Prompt').item.json;
const raw = ($json.content?.[0]?.text || $json.text || '').trim();

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
  return [{ json: { ...src, en_skip: true, en_error: 'Claude EN parse failed', en_raw: raw.slice(0, 500) } }];
}

const esc = (s) => (s || '').replace(/"/g, "'");
const pubDate = src.pubDate || $('Frontmatter Olustur').item.json.pubDate || new Date().toISOString();
const markdown = `---\ntitle: "${esc(title)}"\npubDate: ${pubDate}\nkategori: "${category}"\ndescription: "${esc(summary.slice(0, 150))}"\nkaynak: "${esc(src.link || '')}"\ncoverImage: "${esc(src.gorsel_r2_url || '')}"\ngorselFotografci: "${esc(src.gorsel_fotografci || '')}"\ngorselFotografciLink: "${esc(src.gorsel_fotografci_link || '')}"\n---\n${body}\n`;

return [{
  json: {
    ...src,
    en_skip: false,
    en_title: title,
    en_markdown_icerik: markdown,
    en_fileName: `${src.tr_slug || src.dosya_adi}.md`.replace(/\.md\.md$/, '.md'),
  },
}];"""

CLAUDE_PROMPT = """=You are a professional translator for a technology news website.
Translate the following Turkish article into natural, fluent English news style.
Translate by meaning, not word-for-word.

Return ONLY this exact format:
TITLE: [one line]
SUMMARY: [one line, max 150 chars]
CATEGORY: [AI, Technology, or Security]
BODY:
[translated markdown body only]

Category mapping:
- Yapay Zeka -> AI
- Teknoloji -> Technology
- Güvenlik -> Security

Turkish title: {{ $json.tr_title }}
Turkish summary: {{ $json.tr_summary }}
Turkish category: {{ $json.tr_kategori }}
Turkish body:
{{ $json.tr_body }}"""

ON_ERROR = 'continueRegularOutput'

NEW_NODES = [
    {
        'parameters': {'jsCode': EN_PROMPT_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1024, 48],
        'id': 'b3-en-prompt-0001',
        'name': 'EN Cevir Prompt',
        'onError': ON_ERROR,
    },
    {
        'parameters': {
            'modelId': {
                '__rl': True,
                'value': 'claude-haiku-4-5-20251001',
                'mode': 'list',
                'cachedResultName': 'claude-haiku-4-5-20251001',
            },
            'messages': {'values': [{'content': CLAUDE_PROMPT}]},
            'options': {'maxTokens': 4096},
        },
        'type': '@n8n/n8n-nodes-langchain.anthropic',
        'typeVersion': 1,
        'position': [1248, 48],
        'id': 'b3-claude-en-0002',
        'name': 'Claude EN Cevir',
        'onError': ON_ERROR,
        'credentials': {'anthropicApi': {'id': 'PwbVP4NCV8ZK1PDe', 'name': 'Anthropic account'}},
    },
    {
        'parameters': {'jsCode': EN_BUILD_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1472, 48],
        'id': 'b3-en-build-0003',
        'name': 'EN Markdown Olustur',
        'onError': ON_ERROR,
    },
    {
        'parameters': {
            'conditions': {
                'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                'conditions': [
                    {
                        'id': 'en-skip-check',
                        'leftValue': '={{ $json.en_skip }}',
                        'rightValue': True,
                        'operator': {'type': 'boolean', 'operation': 'notEquals'},
                    }
                ],
                'combinator': 'and',
            },
            'options': {},
        },
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': [1696, 48],
        'id': 'b3-en-if-0004',
        'name': 'EN Yazilacak mi',
    },
    {
        'parameters': {
            'operation': 'toText',
            'sourceProperty': 'en_markdown_icerik',
            'binaryPropertyName': '=data',
            'options': {'fileName': '={{ $json.en_fileName }}'},
        },
        'type': 'n8n-nodes-base.convertToFile',
        'typeVersion': 1.1,
        'position': [1920, -16],
        'id': 'b3-en-file-0005',
        'name': 'EN Markdown Dosyaya Cevir',
        'onError': ON_ERROR,
    },
    {
        'parameters': {
            'operation': 'write',
            'fileName': '=/home/node/site/src/content/posts/en/{{ $binary.data.fileName }}',
            'options': {},
        },
        'type': 'n8n-nodes-base.readWriteFile',
        'typeVersion': 1.1,
        'position': [2144, -16],
        'id': 'b3-en-write-0006',
        'name': 'EN Dosyayi Yaz',
        'onError': ON_ERROR,
    },
    {
        'parameters': {},
        'type': 'n8n-nodes-base.noOp',
        'typeVersion': 1,
        'position': [1920, 112],
        'id': 'b3-en-skip-0007',
        'name': 'EN Atla Devam',
    },
    {
        'parameters': {},
        'type': 'n8n-nodes-base.merge',
        'typeVersion': 3.2,
        'position': [2368, 48],
        'id': 'b3-en-merge-0008',
        'name': 'EN Sonrasi Birlestir',
    },
]


def patch_workflow(wf: dict) -> dict:
    out = deepcopy(wf)
    names = {n['name'] for n in out['nodes']}

    # Fix R2 region: use Cloudflare R2 (us-east-1) instead of auto region S3 cred
    for n in out['nodes']:
        if n['name'] == 'R2 Yukle':
            n['credentials'] = {'aws': {'id': '62kpyPA4lvaLXyMB', 'name': 'Cloudflare R2'}}
            n['onError'] = ON_ERROR

    if 'Claude EN Cevir' in names:
        print('Already patched — skipping EN node insert')
        return out

    out['nodes'].extend(NEW_NODES)
    conn = out.setdefault('connections', {})

    # Yaziyi Diske Yaz -> EN chain (was -> Site Deploy)
    conn['Yaziyi Diske Yaz'] = {'main': [[{'node': 'EN Cevir Prompt', 'type': 'main', 'index': 0}]]}
    conn['EN Cevir Prompt'] = {'main': [[{'node': 'Claude EN Cevir', 'type': 'main', 'index': 0}]]}
    conn['Claude EN Cevir'] = {'main': [[{'node': 'EN Markdown Olustur', 'type': 'main', 'index': 0}]]}
    conn['EN Markdown Olustur'] = {'main': [[{'node': 'EN Yazilacak mi', 'type': 'main', 'index': 0}]]}
    conn['EN Yazilacak mi'] = {
        'main': [
            [{'node': 'EN Markdown Dosyaya Cevir', 'type': 'main', 'index': 0}],
            [{'node': 'EN Atla Devam', 'type': 'main', 'index': 0}],
        ]
    }
    conn['EN Markdown Dosyaya Cevir'] = {'main': [[{'node': 'EN Dosyayi Yaz', 'type': 'main', 'index': 0}]]}
    conn['EN Dosyayi Yaz'] = {'main': [[{'node': 'EN Sonrasi Birlestir', 'type': 'main', 'index': 0}]]}
    conn['EN Atla Devam'] = {'main': [[{'node': 'EN Sonrasi Birlestir', 'type': 'main', 'index': 1}]]}
    conn['EN Sonrasi Birlestir'] = {'main': [[{'node': 'Site Deploy Tetikle', 'type': 'main', 'index': 0}]]}
    return out


def main() -> int:
    src = sorted(ROOT.glob('haber-yayinlama-toplu-*-pre-bolum3.json'))[-1]
    data = json.loads(src.read_text())
    wf = data[0] if isinstance(data, list) else data
    patched = patch_workflow(wf)
    out = ROOT / f"haber-yayinlama-toplu-bolum3-patched.json"
    json.dump([patched], out.open('w'), ensure_ascii=False)
    print(f'Wrote {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
