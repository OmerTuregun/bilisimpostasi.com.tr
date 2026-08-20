#!/usr/bin/env python3
"""Add Twitter queue enqueue step to Haber Yayınlama (Toplu)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

SRC = Path('/root/agent-icerik-sistemi/n8n/backups/haber-yayinlama-toplu-20260820-0747-pre-twitter.json')
OUT = Path('/root/agent-icerik-sistemi/n8n/backups/haber-yayinlama-toplu-twitter-queue-patched.json')

QUEUE_CODE = r"""const CYCLE_MINUTES = 180;
let posts = [];
try {
  posts = $('Frontmatter Olustur').all().map((i) => i.json).filter((p) => p && p.baslik && p.dosya_adi);
} catch (e) {
  posts = [];
}

const n = posts.length;
if (n === 0) {
  return [{ json: { twitter_queue_skip: true, message: 'No posts to enqueue' } }];
}

const step = CYCLE_MINUTES / n;
const now = Date.now();

return posts.map((p, i) => {
  const slug = String(p.dosya_adi || '').replace(/\.md$/, '');
  const summary = String(p.ozet || p.description || '').trim();
  const firstSentence = summary.split(/(?<=[.!?…])\s+/)[0] || summary;
  return {
    json: {
      post_slug: slug,
      post_title: p.baslik,
      post_summary: firstSentence.slice(0, 280),
      post_link: `https://bilisimpostasi.com.tr/posts/${slug}/`,
      kategori: p.kategori || 'Teknoloji',
      scheduled_at: new Date(now + i * step * 60 * 1000).toISOString(),
      schedule_index: i,
      schedule_step_min: step,
    },
  };
});
"""

NEW_NODES = [
    {
        'parameters': {'jsCode': QUEUE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1248, 320],
        'id': 'tw-queue-prep-0001',
        'name': 'Twitter Kuyruk Hazirla',
        'onError': 'continueRegularOutput',
    },
    {
        'parameters': {
            'operation': 'executeQuery',
            'query': (
                "INSERT INTO twitter_queue "
                "(post_slug, post_title, post_summary, post_link, kategori, status, scheduled_at)\n"
                "VALUES (\n"
                "  '{{ $json.post_slug.replace(/'/g, \"''\") }}',\n"
                "  '{{ $json.post_title.replace(/'/g, \"''\") }}',\n"
                "  '{{ ($json.post_summary || '').replace(/'/g, \"''\") }}',\n"
                "  '{{ $json.post_link.replace(/'/g, \"''\") }}',\n"
                "  '{{ ($json.kategori || '').replace(/'/g, \"''\") }}',\n"
                "  'pending',\n"
                "  '{{ $json.scheduled_at }}'::timestamptz\n"
                ");"
            ),
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [1472, 320],
        'id': 'tw-queue-insert-0002',
        'name': 'Twitter Kuyruga Yaz',
        'onError': 'continueRegularOutput',
        'credentials': {
            'postgres': {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'},
        },
    },
]


def main() -> None:
    data = json.loads(SRC.read_text())
    wf = data[0]
    names = {n['name'] for n in wf['nodes']}
    if 'Twitter Kuyruga Yaz' in names:
        print('Already patched')
        OUT.write_text(json.dumps(data, ensure_ascii=False))
        return

    wf['nodes'].extend(NEW_NODES)
    # Deploy success true branch: add parallel Twitter enqueue
    dep = wf['connections']['Deploy Basarili Mi']['main'][0]
    dep.append({'node': 'Twitter Kuyruk Hazirla', 'type': 'main', 'index': 0})
    wf['connections']['Twitter Kuyruk Hazirla'] = {
        'main': [[{'node': 'Twitter Kuyruga Yaz', 'type': 'main', 'index': 0}]]
    }
    OUT.write_text(json.dumps([wf], ensure_ascii=False))
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
