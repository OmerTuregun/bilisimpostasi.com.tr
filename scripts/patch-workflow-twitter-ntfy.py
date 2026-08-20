#!/usr/bin/env python3
"""Replace X API tweet node with ntfy push in Twitter Kuyruk Isleyici."""
from __future__ import annotations

import json
from pathlib import Path

SRC = sorted(Path('/root/agent-icerik-sistemi/n8n/backups').glob('twitter-kuyruk-isleyici-*-pre-ntfy.json'))[-1]
OUT = Path('/root/agent-icerik-sistemi/n8n/backups/twitter-kuyruk-isleyici-ntfy-patched.json')

INTENT_CODE = r"""const row = $json;
const tweetText = String(row.tweet_text || '').trim();
if (!tweetText) {
  throw new Error('tweet_text missing for queue id ' + row.id);
}

const encoded = encodeURIComponent(tweetText);
const clickUrl = `https://x.com/intent/post?text=${encoded}`;
const title = String(row.post_title || 'Yeni yazı').trim();
const body = `${title}\n\nGöndermek için dokun`;

return [{
  json: {
    ...row,
    ntfy_topic: 'bilisimpostasi-tw-x7k2m9qz',
    ntfy_url: 'https://ntfy.sh/bilisimpostasi-tw-x7k2m9qz',
    ntfy_title: 'Bilişim Postası — Yeni Tweet Hazır',
    ntfy_click: clickUrl,
    ntfy_icon: 'https://bilisimpostasi.com.tr/navbar-logo.png',
    ntfy_body: body,
  },
}];"""

REMOVE = {
    'X Tweet Gonder',
    'Tweet Basarili Mi',
    'Durum Posted',
    'Durum Failed',
}

NEW_NODES = [
    {
        'parameters': {'jsCode': INTENT_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [640, -80],
        'id': 'tw-ntfy-intent-001',
        'name': 'ntfy Intent Hazirla',
        'onError': 'continueRegularOutput',
    },
    {
        'parameters': {
            'method': 'POST',
            'url': '={{ $json.ntfy_url }}',
            'sendHeaders': True,
            'headerParameters': {
                'parameters': [
                    {'name': 'Title', 'value': '={{ $json.ntfy_title }}'},
                    {'name': 'Click', 'value': '={{ $json.ntfy_click }}'},
                    {'name': 'Icon', 'value': '={{ $json.ntfy_icon }}'},
                ]
            },
            'sendBody': True,
            'contentType': 'raw',
            'rawContentType': 'text/plain',
            'body': '={{ $json.ntfy_body }}',
            'options': {'response': {'response': {'fullResponse': True}}},
        },
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [864, -80],
        'id': 'tw-ntfy-send-002',
        'name': 'ntfy Push Gonder',
        'onError': 'continueRegularOutput',
    },
    {
        'parameters': {
            'conditions': {
                'options': {
                    'caseSensitive': True,
                    'leftValue': '',
                    'typeValidation': 'loose',
                    'version': 2,
                },
                'conditions': [
                    {
                        'id': 'ntfy-ok',
                        'leftValue': '={{ $json.statusCode }}',
                        'rightValue': 200,
                        'operator': {
                            'type': 'number',
                            'operation': 'equals',
                        },
                    }
                ],
                'combinator': 'and',
            },
            'options': {},
        },
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': [1088, -80],
        'id': 'tw-ntfy-ok-003',
        'name': 'ntfy Basarili Mi',
    },
    {
        'parameters': {
            'operation': 'executeQuery',
            'query': (
                "UPDATE twitter_queue\n"
                "SET status = 'notified', posted_at = now()\n"
                "WHERE id = {{ $('Tek Tek Tweetle').item.json.id }};"
            ),
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [1312, -160],
        'id': 'tw-notified-004',
        'name': 'Durum Notified',
        'credentials': {
            'postgres': {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'},
        },
    },
    {
        'parameters': {
            'operation': 'executeQuery',
            'query': (
                "UPDATE twitter_queue\n"
                "SET status = 'failed'\n"
                "WHERE id = {{ $('Tek Tek Tweetle').item.json.id }};"
            ),
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [1312, 0],
        'id': 'tw-notify-fail-005',
        'name': 'Durum Notify Failed',
        'onError': 'continueRegularOutput',
        'credentials': {
            'postgres': {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'},
        },
    },
]


def main() -> None:
    wf = json.loads(SRC.read_text())[0]
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] not in REMOVE]
    names = {n['name'] for n in wf['nodes']}
    for node in NEW_NODES:
        if node['name'] not in names:
            wf['nodes'].append(node)

    conn = wf['connections']
    for key in list(conn.keys()):
        if key in REMOVE:
            del conn[key]

    conn['Tek Tek Tweetle'] = {
        'main': [
            [],
            [{'node': 'ntfy Intent Hazirla', 'type': 'main', 'index': 0}],
        ]
    }
    conn['ntfy Intent Hazirla'] = {
        'main': [[{'node': 'ntfy Push Gonder', 'type': 'main', 'index': 0}]]
    }
    conn['ntfy Push Gonder'] = {
        'main': [[{'node': 'ntfy Basarili Mi', 'type': 'main', 'index': 0}]]
    }
    conn['ntfy Basarili Mi'] = {
        'main': [
            [{'node': 'Durum Notified', 'type': 'main', 'index': 0}],
            [{'node': 'Durum Notify Failed', 'type': 'main', 'index': 0}],
        ]
    }
    conn['Durum Notified'] = {
        'main': [[{'node': 'Tek Tek Tweetle', 'type': 'main', 'index': 0}]]
    }
    conn['Durum Notify Failed'] = {
        'main': [[{'node': 'Tek Tek Tweetle', 'type': 'main', 'index': 0}]]
    }

    OUT.write_text(json.dumps([wf], ensure_ascii=False))
    print(f'Wrote {OUT}')
    print('nodes:', [n['name'] for n in wf['nodes']])


if __name__ == '__main__':
    main()
