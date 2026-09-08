#!/usr/bin/env python3
"""Aşama 49: queue Telegram + Email notifications like Twitter."""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
PUBLISH_ID = 'zVyc6gzToDe5mhc2'
PROCESSOR_ID = 'notifyKuyrukIsleyici01'
PG_CRED = {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'}
TG_CRED = {'id': 'IPdDDgKVO9y4kgxN', 'name': 'Telegram account'}
OWNER_CHAT = '6675249884'


def export_publish() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-notify-queue.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={PUBLISH_ID}', '--output=/tmp/wf-notify-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-notify-pre.json', str(out)], check=True)
    return out


EMAIL_QUEUE_CODE = r'''const text = String($json.text || '');
const post_count = Number($json.post_count || 0);
if (!post_count || !text.trim()) {
  return [{ json: { notify_skip: true, channel: 'email_digest' } }];
}
return [{
  json: {
    channel: 'email_digest',
    payload: { text, post_count },
    scheduled_at: new Date().toISOString(),
  },
}];
'''

OWNER_TG_QUEUE_CODE = f'''const items = $input.all();
const lines = items.map((it, i) => {{
  const slug = String(it.json.dosya_adi || '').replace(/\\.md$/, '');
  const title = it.json.baslik || slug;
  return `${{i + 1}}. ${{title}}\\nhttps://bilisimpostasi.com.tr/posts/${{slug}}/`;
}}).filter(Boolean);
if (!lines.length) {{
  return [{{ json: {{ notify_skip: true, channel: 'telegram_owner' }} }}];
}}
const text = '📰 Yeni yazı yayınlandı!\\n\\n' + lines.join('\\n\\n');
return [{{
  json: {{
    channel: 'telegram_owner',
    payload: {{ chat_id: '{OWNER_CHAT}', text }},
    scheduled_at: new Date().toISOString(),
    dosya_adi: items[0].json.dosya_adi,
    baslik: items[0].json.baslik,
  }},
}}];
'''

ABONE_TG_QUEUE_CODE = r'''const msg = $('Abone Mesajini Hazirla').first().json || {};
const text = String(msg.text || '');
const post_count = Number(msg.post_count || 0);
if (!post_count || !text.trim()) {
  return [{ json: { notify_skip: true, channel: 'telegram_subscriber' } }];
}

let rows = [];
try {
  rows = $input.all().map((i) => i.json).filter((j) => j && j.chat_id);
} catch (e) {
  rows = [];
}
if (!rows.length) {
  return [{ json: { notify_skip: true, channel: 'telegram_subscriber', reason: 'no_subscribers' } }];
}

return rows.map((r) => ({
  json: {
    channel: 'telegram_subscriber',
    payload: { chat_id: String(r.chat_id), text },
    scheduled_at: new Date().toISOString(),
  },
}));
'''

INSERT_QUERY = (
    "INSERT INTO notify_queue (channel, payload, status, scheduled_at)\n"
    "SELECT\n"
    "  '{{ $json.channel }}',\n"
    "  '{{ JSON.stringify($json.payload).replace(/'/g, \"''\") }}'::jsonb,\n"
    "  'pending',\n"
    "  '{{ $json.scheduled_at }}'::timestamptz\n"
    "WHERE '{{ $json.notify_skip || false }}' <> 'true';"
)

# Safer insert via query with dollar quoting is hard in n8n template.
# Use executeQuery with expression-built SQL in Code node instead.

INSERT_PREP_CODE = r'''return $input.all().map((item) => {
  const j = item.json || {};
  if (j.notify_skip) {
    return { json: { ...j, sql_skip: true, query: 'SELECT 1 WHERE false;' } };
  }
  const channel = String(j.channel || '').replace(/'/g, "''");
  const payload = JSON.stringify(j.payload || {}).replace(/'/g, "''");
  const scheduled = String(j.scheduled_at || new Date().toISOString()).replace(/'/g, "''");
  const query =
    "INSERT INTO notify_queue (channel, payload, status, scheduled_at) VALUES (" +
    "'" + channel + "', " +
    "'" + payload + "'::jsonb, " +
    "'pending', " +
    "'" + scheduled + "'::timestamptz);";
  return { json: { ...j, sql_skip: false, query } };
});
'''


def patch_publish(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    conn = wf['connections']
    names = {n['name'] for n in wf['nodes']}

    # --- Email: prepare queue + insert instead of direct webhook ---
    by['Email Bildirim Hazirla']['parameters']['jsCode'] = (
        by['Email Bildirim Hazirla']['parameters']['jsCode'].rstrip()
        + "\n"
    )
    # Replace Email Bildirim Gonder with queue prep + postgres
    # Keep node name for fewer connection churn: change type/params of Email Bildirim Gonder
    # Actually insert new nodes and rewire.

    def add_node(node):
        if node['name'] in names:
            # replace existing
            wf['nodes'] = [n for n in wf['nodes'] if n['name'] != node['name']]
        wf['nodes'].append(node)
        names.add(node['name'])

    add_node({
        'parameters': {'jsCode': EMAIL_QUEUE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [2200, 400],
        'id': 'notify-email-prep-0001',
        'name': 'Email Kuyruk Hazirla',
    })
    add_node({
        'parameters': {'jsCode': INSERT_PREP_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [2420, 400],
        'id': 'notify-email-sql-0002',
        'name': 'Email Kuyruk SQL',
    })
    add_node({
        'parameters': {
            'operation': 'executeQuery',
            'query': '={{ $json.query }}',
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [2640, 400],
        'id': 'notify-email-ins-0003',
        'name': 'Email Kuyruga Yaz',
        'onError': 'continueRegularOutput',
        'credentials': {'postgres': PG_CRED},
    })

    # Owner telegram queue
    add_node({
        'parameters': {'jsCode': OWNER_TG_QUEUE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1760, 48],
        'id': 'notify-owner-prep-0004',
        'name': 'Owner TG Kuyruk Hazirla',
    })
    add_node({
        'parameters': {'jsCode': INSERT_PREP_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [1980, 48],
        'id': 'notify-owner-sql-0005',
        'name': 'Owner TG Kuyruk SQL',
    })
    add_node({
        'parameters': {
            'operation': 'executeQuery',
            'query': '={{ $json.query }}',
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [2200, 48],
        'id': 'notify-owner-ins-0006',
        'name': 'Owner TG Kuyruga Yaz',
        'onError': 'continueRegularOutput',
        'credentials': {'postgres': PG_CRED},
    })

    # Subscriber telegram queue (replaces send loop)
    add_node({
        'parameters': {'jsCode': ABONE_TG_QUEUE_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [2420, 200],
        'id': 'notify-sub-prep-0007',
        'name': 'Abone TG Kuyruk Hazirla',
    })
    add_node({
        'parameters': {'jsCode': INSERT_PREP_CODE},
        'type': 'n8n-nodes-base.code',
        'typeVersion': 2,
        'position': [2640, 200],
        'id': 'notify-sub-sql-0008',
        'name': 'Abone TG Kuyruk SQL',
    })
    add_node({
        'parameters': {
            'operation': 'executeQuery',
            'query': '={{ $json.query }}',
            'options': {},
        },
        'type': 'n8n-nodes-base.postgres',
        'typeVersion': 2.7,
        'position': [2860, 200],
        'id': 'notify-sub-ins-0009',
        'name': 'Abone TG Kuyruga Yaz',
        'onError': 'continueRegularOutput',
        'credentials': {'postgres': PG_CRED},
    })

    # Rewire Email
    conn['Email Bildirim Hazirla'] = {
        'main': [[{'node': 'Email Kuyruk Hazirla', 'type': 'main', 'index': 0}]]
    }
    conn['Email Kuyruk Hazirla'] = {
        'main': [[{'node': 'Email Kuyruk SQL', 'type': 'main', 'index': 0}]]
    }
    conn['Email Kuyruk SQL'] = {
        'main': [[{'node': 'Email Kuyruga Yaz', 'type': 'main', 'index': 0}]]
    }
    conn.pop('Email Bildirim Gonder', None)

    # Rewire owner telegram: Telegram Icin Yazilari Topla -> Owner TG queue -> Kuyruk Temizle
    # (bypass direct Telegram Bildirimi Gonder for send; keep node unused or disconnect)
    conn['Telegram Icin Yazilari Topla'] = {
        'main': [[{'node': 'Owner TG Kuyruk Hazirla', 'type': 'main', 'index': 0}]]
    }
    conn['Owner TG Kuyruk Hazirla'] = {
        'main': [[{'node': 'Owner TG Kuyruk SQL', 'type': 'main', 'index': 0}]]
    }
    conn['Owner TG Kuyruk SQL'] = {
        'main': [[{'node': 'Owner TG Kuyruga Yaz', 'type': 'main', 'index': 0}]]
    }
    conn['Owner TG Kuyruga Yaz'] = {
        'main': [[{'node': 'Kuyruk Temizle Bos Icerik', 'type': 'main', 'index': 0}]]
    }
    conn.pop('Telegram Bildirimi Gonder', None)

    # Rewire subscriber telegram: Aktif Aboneleri Cikar -> Abone TG queue (skip Bol/Send/Wait)
    conn['Aktif Aboneleri Cikar'] = {
        'main': [[{'node': 'Abone TG Kuyruk Hazirla', 'type': 'main', 'index': 0}]]
    }
    conn['Abone TG Kuyruk Hazirla'] = {
        'main': [[{'node': 'Abone TG Kuyruk SQL', 'type': 'main', 'index': 0}]]
    }
    conn['Abone TG Kuyruk SQL'] = {
        'main': [[{'node': 'Abone TG Kuyruga Yaz', 'type': 'main', 'index': 0}]]
    }
    # Disconnect old send path
    for dead in ('Abonelere Bol', 'Telegram Abone Mesaji Gonder', 'Abone Gonderim Bekle'):
        conn.pop(dead, None)

    out = BACKUP / 'haber-yayinlama-asama49-notify-queue-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('publish patched', out)
    return out


def build_processor() -> Path:
    wf = {
        'id': PROCESSOR_ID,
        'name': 'Bildirim Kuyruk Isleyici',
        'active': True,
        'nodes': [
            {
                'parameters': {
                    'rule': {'interval': [{'field': 'minutes', 'minutesInterval': 5}]}
                },
                'type': 'n8n-nodes-base.scheduleTrigger',
                'typeVersion': 1.2,
                'position': [-480, 0],
                'id': 'nq-sched-0001',
                'name': 'Her 5 Dakika',
            },
            {
                'parameters': {
                    'operation': 'executeQuery',
                    'query': (
                        "SELECT id, channel, payload, attempts\n"
                        "FROM notify_queue\n"
                        "WHERE status = 'pending'\n"
                        "  AND scheduled_at <= now()\n"
                        "ORDER BY scheduled_at ASC, id ASC\n"
                        "LIMIT 30;"
                    ),
                    'options': {'queryBatching': 'single'},
                },
                'type': 'n8n-nodes-base.postgres',
                'typeVersion': 2.7,
                'position': [-256, 0],
                'id': 'nq-select-0002',
                'name': 'Bekleyen Bildirimleri Cek',
                'credentials': {'postgres': PG_CRED},
            },
            {
                'parameters': {
                    'jsCode': (
                        "const rows = $input.all().map(i => i.json).filter(j => j && j.id);\n"
                        "if (!rows.length) return [{ json: { empty: true } }];\n"
                        "return rows.map(r => {\n"
                        "  let payload = r.payload;\n"
                        "  if (typeof payload === 'string') {\n"
                        "    try { payload = JSON.parse(payload); } catch (e) { payload = {}; }\n"
                        "  }\n"
                        "  return { json: { ...r, payload, empty: false } };\n"
                        "});"
                    )
                },
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [-40, 0],
                'id': 'nq-norm-0003',
                'name': 'Normalize',
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
                        'conditions': [{
                            'id': 'not-empty',
                            'leftValue': '={{ $json.empty }}',
                            'rightValue': True,
                            'operator': {'type': 'boolean', 'operation': 'notEquals'},
                        }],
                        'combinator': 'and',
                    },
                    'options': {},
                },
                'type': 'n8n-nodes-base.if',
                'typeVersion': 2.2,
                'position': [180, 0],
                'id': 'nq-if-0004',
                'name': 'Kayit Var Mi',
            },
            {
                'parameters': {},
                'type': 'n8n-nodes-base.noOp',
                'typeVersion': 1,
                'position': [400, 120],
                'id': 'nq-empty-0005',
                'name': 'Bos Kuyruk',
            },
            {
                'parameters': {
                    'rules': {
                        'values': [
                            {
                                'conditions': {
                                    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                                    'conditions': [{
                                        'leftValue': '={{ $json.channel }}',
                                        'rightValue': 'email_digest',
                                        'operator': {'type': 'string', 'operation': 'equals'},
                                    }],
                                    'combinator': 'and',
                                },
                                'renameOutput': True,
                                'outputKey': 'email',
                            },
                            {
                                'conditions': {
                                    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                                    'conditions': [{
                                        'leftValue': '={{ $json.channel }}',
                                        'rightValue': 'telegram_owner',
                                        'operator': {'type': 'string', 'operation': 'equals'},
                                    }],
                                    'combinator': 'and',
                                },
                                'renameOutput': True,
                                'outputKey': 'tg_owner',
                            },
                            {
                                'conditions': {
                                    'options': {'caseSensitive': True, 'leftValue': '', 'typeValidation': 'strict', 'version': 2},
                                    'conditions': [{
                                        'leftValue': '={{ $json.channel }}',
                                        'rightValue': 'telegram_subscriber',
                                        'operator': {'type': 'string', 'operation': 'equals'},
                                    }],
                                    'combinator': 'and',
                                },
                                'renameOutput': True,
                                'outputKey': 'tg_sub',
                            },
                        ]
                    },
                    'options': {'fallbackOutput': 'extra'},
                },
                'type': 'n8n-nodes-base.switch',
                'typeVersion': 3.2,
                'position': [400, -40],
                'id': 'nq-switch-0006',
                'name': 'Kanal Sec',
            },
            {
                'parameters': {
                    'method': 'POST',
                    'url': 'https://n8n.omerfarukturegun.com.tr/webhook/haber-email-notify',
                    'sendBody': True,
                    'specifyBody': 'json',
                    'jsonBody': '={{ { text: $json.payload.text, post_count: $json.payload.post_count } }}',
                    'options': {'timeout': 60000},
                },
                'type': 'n8n-nodes-base.httpRequest',
                'typeVersion': 4.2,
                'position': [640, -160],
                'id': 'nq-email-0007',
                'name': 'Email Webhook Gonder',
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'chatId': '={{ $json.payload.chat_id }}',
                    'text': '={{ $json.payload.text }}',
                    'additionalFields': {},
                },
                'type': 'n8n-nodes-base.telegram',
                'typeVersion': 1.2,
                'position': [640, -40],
                'id': 'nq-tg-owner-0008',
                'name': 'Owner Telegram Gonder',
                'credentials': {'telegramApi': TG_CRED},
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'chatId': '={{ $json.payload.chat_id }}',
                    'text': '={{ $json.payload.text }}',
                    'additionalFields': {},
                },
                'type': 'n8n-nodes-base.telegram',
                'typeVersion': 1.2,
                'position': [640, 80],
                'id': 'nq-tg-sub-0009',
                'name': 'Abone Telegram Gonder',
                'credentials': {'telegramApi': TG_CRED},
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'jsCode': (
                        "const item = $input.first().json || {};\n"
                        "const id = item.id;\n"
                        "// Detect failure: telegram/http errors often set error message\n"
                        "const err = item.error || item.message || '';\n"
                        "const failed = !!(item.error || (typeof err === 'string' && /ECONN|timeout|error|fail/i.test(String(err)) && !item.message_id && !item.ok));\n"
                        "// Heuristic: success if telegram message_id present OR http status < 400 OR body ok\n"
                        "const tgOk = !!(item.message_id || (item.result && item.result.message_id));\n"
                        "const httpOk = (item.statusCode && Number(item.statusCode) < 400) || item.status === 'success' || item.ok === true;\n"
                        "const channel = item.channel || ($('Kanal Sec').item.json.channel);\n"
                        "const queueId = item.id || $('Kanal Sec').item.json.id;\n"
                        "const attempts = Number(($('Kanal Sec').item.json.attempts || 0)) + 1;\n"
                        "let ok = tgOk || httpOk;\n"
                        "if (channel === 'email_digest') {\n"
                        "  // webhook onReceived returns quickly; treat no error as ok\n"
                        "  ok = !item.error;\n"
                        "}\n"
                        "if (channel && String(channel).startsWith('telegram')) {\n"
                        "  ok = tgOk;\n"
                        "}\n"
                        "if (ok) {\n"
                        "  return [{ json: { queue_id: queueId, ok: true, query: `UPDATE notify_queue SET status='sent', sent_at=now(), attempts=${attempts}, last_error=NULL WHERE id=${Number(queueId)};` } }];\n"
                        "}\n"
                        "const status = attempts >= 8 ? 'failed' : 'pending';\n"
                        "const last = String(item.error || item.message || 'send_failed').replace(/'/g, \"''\").slice(0, 500);\n"
                        "const delayMin = Math.min(60, attempts * 5);\n"
                        "return [{ json: { queue_id: queueId, ok: false, query: `UPDATE notify_queue SET status='${status}', attempts=${attempts}, last_error='${last}', scheduled_at=now() + interval '${delayMin} minutes' WHERE id=${Number(queueId)};` } }];\n"
                    )
                },
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [880, -40],
                'id': 'nq-result-0010',
                'name': 'Sonuc SQL Hazirla',
            },
            {
                'parameters': {
                    'operation': 'executeQuery',
                    'query': '={{ $json.query }}',
                    'options': {},
                },
                'type': 'n8n-nodes-base.postgres',
                'typeVersion': 2.7,
                'position': [1100, -40],
                'id': 'nq-update-0011',
                'name': 'Durum Guncelle',
                'credentials': {'postgres': PG_CRED},
                'onError': 'continueRegularOutput',
            },
        ],
        'connections': {
            'Her 5 Dakika': {'main': [[{'node': 'Bekleyen Bildirimleri Cek', 'type': 'main', 'index': 0}]]},
            'Bekleyen Bildirimleri Cek': {'main': [[{'node': 'Normalize', 'type': 'main', 'index': 0}]]},
            'Normalize': {'main': [[{'node': 'Kayit Var Mi', 'type': 'main', 'index': 0}]]},
            'Kayit Var Mi': {
                'main': [
                    [{'node': 'Kanal Sec', 'type': 'main', 'index': 0}],
                    [{'node': 'Bos Kuyruk', 'type': 'main', 'index': 0}],
                ]
            },
            'Kanal Sec': {
                'main': [
                    [{'node': 'Email Webhook Gonder', 'type': 'main', 'index': 0}],
                    [{'node': 'Owner Telegram Gonder', 'type': 'main', 'index': 0}],
                    [{'node': 'Abone Telegram Gonder', 'type': 'main', 'index': 0}],
                ]
            },
            'Email Webhook Gonder': {'main': [[{'node': 'Sonuc SQL Hazirla', 'type': 'main', 'index': 0}]]},
            'Owner Telegram Gonder': {'main': [[{'node': 'Sonuc SQL Hazirla', 'type': 'main', 'index': 0}]]},
            'Abone Telegram Gonder': {'main': [[{'node': 'Sonuc SQL Hazirla', 'type': 'main', 'index': 0}]]},
            'Sonuc SQL Hazirla': {'main': [[{'node': 'Durum Guncelle', 'type': 'main', 'index': 0}]]},
        },
        'settings': {'executionOrder': 'v1'},
    }
    out = BACKUP / 'bildirim-kuyruk-isleyici.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('processor', out)
    return out


def build_contact_workflow() -> Path:
    # destek@ not active yet — send tests to owner's known inbox until switched.
    to_email = 'trkuraf@gmail.com'
    validate_code = f'''
const body = $json.body ?? $json;
const name = String(body.name || '').trim().slice(0, 120);
const email = String(body.email || '').trim().slice(0, 200);
const message = String(body.message || '').trim().slice(0, 5000);
const honeypot = String(body.website || body.company || '').trim();

if (honeypot) {{
  return [{{ json: {{ ok: true, spam: true, status: 200, response: {{ ok: true }} }} }}];
}}
if (!name || !email || !message || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {{
  return [{{ json: {{ ok: false, status: 400, response: {{ ok: false, error: 'invalid' }} }} }}];
}}
if (message.length < 10) {{
  return [{{ json: {{ ok: false, status: 400, response: {{ ok: false, error: 'short' }} }} }}];
}}

const esc = (s) => String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');
const subject = ('[İletişim] ' + name).slice(0, 120);
const html =
  '<p><b>Ad:</b> ' + esc(name) + '</p>' +
  '<p><b>E-posta:</b> ' + esc(email) + '</p>' +
  '<p><b>Mesaj:</b></p>' +
  '<pre style="white-space:pre-wrap;font-family:inherit">' + esc(message) + '</pre>';

return [{{
  json: {{
    ok: true,
    spam: false,
    status: 200,
    to: '{to_email}',
    reply_to: email,
    subject,
    html,
    response: {{ ok: true }},
  }},
}}];
'''
    wf = {
        'id': 'contactFormWebhook01',
        'name': 'Iletisim Formu',
        'active': True,
        'nodes': [
            {
                'parameters': {
                    'path': 'contact-form',
                    'httpMethod': 'POST',
                    'responseMode': 'responseNode',
                    'options': {},
                },
                'type': 'n8n-nodes-base.webhook',
                'typeVersion': 2.1,
                'position': [0, 0],
                'id': 'cf-hook-0001',
                'name': 'Iletisim Webhook',
                'webhookId': 'contact-form-hook',
            },
            {
                'parameters': {'jsCode': validate_code},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [240, 0],
                'id': 'cf-validate-0002',
                'name': 'Dogrula',
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
                        'conditions': [{
                            'id': 'should-send',
                            'leftValue': '={{ $json.ok === true && $json.spam !== true }}',
                            'rightValue': True,
                            'operator': {'type': 'boolean', 'operation': 'equals'},
                        }],
                        'combinator': 'and',
                    },
                    'options': {},
                },
                'type': 'n8n-nodes-base.if',
                'typeVersion': 2.2,
                'position': [460, 0],
                'id': 'cf-if-0003',
                'name': 'Gonderilecek Mi',
            },
            {
                'parameters': {
                    'method': 'POST',
                    'url': 'https://api.resend.com/emails',
                    'authentication': 'genericCredentialType',
                    'genericAuthType': 'httpHeaderAuth',
                    'sendBody': True,
                    'specifyBody': 'json',
                    'jsonBody': (
                        "={{ { from: 'Bilişim Postası <no-reply@bilisimpostasi.com.tr>', "
                        "to: [$json.to], reply_to: $json.reply_to, "
                        "subject: $json.subject, html: $json.html } }}"
                    ),
                    'options': {'timeout': 30000},
                },
                'type': 'n8n-nodes-base.httpRequest',
                'typeVersion': 4.2,
                'position': [700, -80],
                'id': 'cf-resend-0004',
                'name': 'Resend Gonder',
                'credentials': {
                    'httpHeaderAuth': {'id': 'ReSendAPIKey0002', 'name': 'Resend API Key'}
                },
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'respondWith': 'json',
                    'responseBody': '={{ $json.response || { ok: !!$json.id || true } }}',
                    'options': {},
                },
                'type': 'n8n-nodes-base.respondToWebhook',
                'typeVersion': 1.1,
                'position': [940, 0],
                'id': 'cf-respond-0005',
                'name': 'Yanit',
            },
        ],
        'connections': {
            'Iletisim Webhook': {'main': [[{'node': 'Dogrula', 'type': 'main', 'index': 0}]]},
            'Dogrula': {'main': [[{'node': 'Gonderilecek Mi', 'type': 'main', 'index': 0}]]},
            'Gonderilecek Mi': {
                'main': [
                    [{'node': 'Resend Gonder', 'type': 'main', 'index': 0}],
                    [{'node': 'Yanit', 'type': 'main', 'index': 0}],
                ]
            },
            'Resend Gonder': {'main': [[{'node': 'Yanit', 'type': 'main', 'index': 0}]]},
        },
        'settings': {'executionOrder': 'v1'},
    }
    out = BACKUP / 'iletisim-formu-workflow.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('contact wf', out)
    return out


def import_wf(path: Path, wf_id: str | None = None) -> None:
    dest = f'/tmp/{path.name}'
    subprocess.run(['docker', 'cp', str(path), f'agent-n8n:{dest}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', f'--input={dest}'],
        check=True,
    )
    if wf_id:
        subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={wf_id}'],
            check=False,
        )
        subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={wf_id}', '--active=true'],
            check=False,
        )


def main() -> None:
    pre = export_publish()
    pub = patch_publish(pre)
    proc = build_processor()
    contact = build_contact_workflow()
    import_wf(pub, PUBLISH_ID)
    import_wf(proc, PROCESSOR_ID)
    import_wf(contact, 'contactFormWebhook01')
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
    print('DONE')


if __name__ == '__main__':
    main()
