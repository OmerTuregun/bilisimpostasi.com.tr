#!/usr/bin/env python3
"""Aşama 55: Haftalık özet e-postası workflow (test webhook + Pazartesi 09:00 İstanbul)."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'haftalikOzetEmail01'
TEST_EMAIL = 'trkuraf@gmail.com'

READ_POSTS_CODE = r"""
const fs = require('fs');
const path = '/home/node/site/src/content/posts/tr';
const MAX_POSTS = 15;
const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
const test_mode = !!($json.test_mode);

function pick(key, block) {
  const prefix = key + ':';
  const lines = String(block || '').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith(prefix)) continue;
    return trimmed.slice(prefix.length).trim().replace(/^"|"$/g, '');
  }
  return '';
}

const posts = [];
for (const file of fs.readdirSync(path)) {
  if (!file.endsWith('.md')) continue;
  const text = fs.readFileSync(path + '/' + file, 'utf8');
  const fm = text.match(/^---\n([\s\S]*?)\n---/);
  if (!fm) continue;
  const block = fm[1];
  const pubRaw = pick('pubDate', block);
  const pub = Date.parse(pubRaw);
  if (!Number.isFinite(pub) || pub < cutoff) continue;
  const slug = file.replace(/\.md$/, '');
  posts.push({
    title: pick('title', block),
    summary: pick('description', block),
    link: 'https://bilisimpostasi.com.tr/posts/' + slug + '/',
    pubDate: pub,
  });
}

posts.sort((a, b) => b.pubDate - a.pubDate);
const selected = posts.slice(0, MAX_POSTS);

return [{
  json: {
    test_mode,
    posts: selected,
    post_count: selected.length,
    week_label: new Date().toLocaleDateString('tr-TR', { timeZone: 'Europe/Istanbul' }),
  },
}];
"""

HTML_CODE = r"""
const j = $json;
const posts = j.posts || [];
const count = Number(j.post_count || posts.length || 0);
if (!count) {
  return [{ json: { should_send: 0, post_count: 0, test_mode: !!j.test_mode } }];
}

const esc = (s) => String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let rows = '';
for (const p of posts) {
  const title = esc(p.title);
  const summary = esc(p.summary || '');
  const link = esc(p.link);
  rows += `<tr><td style="padding:16px 0;border-bottom:1px solid #f0ece4;">
    <a href="${link}" style="font-size:16px;font-weight:700;color:#1a1a1a;text-decoration:none;line-height:1.35;">${title}</a>
    <p style="margin:8px 0 0;font-size:14px;color:#555;line-height:1.5;">${summary}</p>
    <a href="${link}" style="font-size:13px;color:#0b5fff;text-decoration:none;">Yazıyı oku →</a>
  </td></tr>`;
}

const subject = `Haftalık Özet (${count} yazı) — Bilişim Postası`;
const html = `<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
</head>
<body style="margin:0;padding:0;background:#f6f4ef;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f6f4ef;padding:24px 12px;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #e8e4dc;">
  <tr><td style="padding:24px 24px 16px;text-align:center;border-bottom:1px solid #f0ece4;">
    <img src="https://bilisimpostasi.com.tr/navbar-logo.png" alt="Bilişim Postası" height="52" style="height:52px;width:auto;"/>
  </td></tr>
  <tr><td style="padding:24px 24px 8px;">
    <h1 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#1a1a1a;">Bu Haftanın Yazıları</h1>
    <p style="margin:0 0 18px;font-size:14px;color:#666;">Son 7 günde yayınlanan ${count} yazı:</p>
    <table width="100%" cellpadding="0" cellspacing="0">${rows}</table>
  </td></tr>
  <tr><td style="padding:8px 24px 24px;text-align:center;">
    <a href="https://bilisimpostasi.com.tr" style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:600;color:#ffffff;background:#0b5fff;text-decoration:none;border-radius:6px;">Siteye Git</a>
  </td></tr>
  {{FOOTER_PLACEHOLDER}}
</table>
</td></tr>
</table>
</body>
</html>`;

return [{
  json: {
    should_send: 1,
    subject,
    html,
    post_count: count,
    test_mode: !!j.test_mode,
  },
}];
"""

RESEND_PAYLOAD_CODE = r"""
const baseHtml = $('HTML Hazirla').first().json.html || '';
const subject = $('HTML Hazirla').first().json.subject || '';
const test_mode = !!($('HTML Hazirla').first().json.test_mode);
const toEmail = ($json.email_address || $json.email || '').toString();
const token = ($json.unsubscribe_token || '').toString();
const unsubscribeUrl = token
  ? 'https://bilisimpostasi.com.tr/abone-cik?token=' + token
  : 'https://bilisimpostasi.com.tr/abone-cik';

const footer = `<tr><td style="padding:18px 24px 26px;border-top:1px solid #f0ece4;text-align:center;background:#faf9f7;">
  <p style="margin:0 0 10px;font-size:13px;color:#666;">Bu e-postayı Bilişim Postası haftalık özet listesinden alıyorsunuz.</p>
  <p style="margin:0 0 8px;font-size:14px;"><a href="${unsubscribeUrl}" style="color:#c0392b;text-decoration:underline;font-weight:600;">Abonelikten çık</a></p>
  <p style="margin:0;font-size:11px;color:#aaa;">Bilişim Postası · <a href="https://bilisimpostasi.com.tr" style="color:#999;text-decoration:none;">bilisimpostasi.com.tr</a></p>
</td></tr>`;

const html = baseHtml.replace('{{FOOTER_PLACEHOLDER}}', footer);
const prefix = test_mode ? '[TEST] ' : '';

return { json: { to: toEmail, subject: prefix + subject, html } };
"""

TEST_RECIPIENT_CODE = f"""
const row = $input.first().json || {{}};
const token = row.unsubscribe_token || '';
return [{{
  json: {{
    email_address: '{TEST_EMAIL}',
    unsubscribe_token: token,
  }},
}}];
"""


def build_workflow() -> dict:
    return {
        'id': WF_ID,
        'name': 'Haftalik Ozet E-postasi',
        'active': True,
        'nodes': [
            {
                'parameters': {
                    'rule': {
                        'interval': [
                            {
                                'field': 'cronExpression',
                                'expression': '0 9 * * 1',
                            }
                        ]
                    },
                    'timezone': 'Europe/Istanbul',
                },
                'type': 'n8n-nodes-base.scheduleTrigger',
                'typeVersion': 1.2,
                'position': [-700, -120],
                'id': 'wk-sched-001',
                'name': 'Pazartesi 0900',
            },
            {
                'parameters': {
                    'path': 'weekly-digest-test',
                    'httpMethod': 'POST',
                    'authentication': 'none',
                    'responseMode': 'onReceived',
                    'responseCode': 200,
                    'options': {},
                },
                'type': 'n8n-nodes-base.webhook',
                'typeVersion': 2.1,
                'position': [-700, 120],
                'id': 'wk-test-hook-002',
                'name': 'Test Webhook',
                'webhookId': 'weekly-digest-test-hook',
            },
            {
                'parameters': {'jsCode': 'return [{ json: { test_mode: false } }];'},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [-460, -120],
                'id': 'wk-live-flag-003',
                'name': 'Canli Mod',
            },
            {
                'parameters': {'jsCode': 'return [{ json: { test_mode: true } }];'},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [-460, 120],
                'id': 'wk-test-flag-004',
                'name': 'Test Modu',
            },
            {
                'parameters': {'jsCode': READ_POSTS_CODE},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [-220, 0],
                'id': 'wk-read-005',
                'name': 'Son 7 Gun Yazilari',
            },
            {
                'parameters': {
                    'conditions': {
                        'options': {
                            'caseSensitive': True,
                            'leftValue': '',
                            'typeValidation': 'strict',
                            'version': 3,
                        },
                        'conditions': [{
                            'id': 'has-posts',
                            'leftValue': '={{ $json.post_count }}',
                            'rightValue': 0,
                            'operator': {'type': 'number', 'operation': 'gt'},
                        }],
                        'combinator': 'and',
                    },
                    'options': {},
                },
                'type': 'n8n-nodes-base.if',
                'typeVersion': 2.3,
                'position': [20, 0],
                'id': 'wk-if-posts-006',
                'name': 'Yazi Var Mi',
            },
            {
                'parameters': {'jsCode': HTML_CODE},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [260, -40],
                'id': 'wk-html-007',
                'name': 'HTML Hazirla',
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
                            'id': 'is-test',
                            'leftValue': '={{ $json.test_mode }}',
                            'rightValue': True,
                            'operator': {'type': 'boolean', 'operation': 'equals'},
                        }],
                        'combinator': 'and',
                    },
                    'options': {'looseTypeValidation': True},
                },
                'type': 'n8n-nodes-base.if',
                'typeVersion': 2.2,
                'position': [500, -40],
                'id': 'wk-if-test-008',
                'name': 'Test Modu Mu',
            },
            {
                'parameters': {
                    'operation': 'executeQuery',
                    'query': f"SELECT unsubscribe_token FROM email_subscribers WHERE email='{TEST_EMAIL}' AND status='confirmed' AND unsubscribed_at IS NULL LIMIT 1;",
                    'options': {},
                },
                'type': 'n8n-nodes-base.postgres',
                'typeVersion': 2.7,
                'position': [740, -160],
                'id': 'wk-test-token-009',
                'name': 'Test Token Cek',
                'credentials': {'postgres': {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'}},
                'continueOnFail': True,
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {'jsCode': TEST_RECIPIENT_CODE},
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [980, -160],
                'id': 'wk-test-recip-010',
                'name': 'Test Alici',
            },
            {
                'parameters': {
                    'operation': 'executeQuery',
                    'query': "SELECT email AS email_address, unsubscribe_token FROM email_subscribers WHERE status='confirmed' AND unsubscribed_at IS NULL;",
                    'options': {},
                },
                'type': 'n8n-nodes-base.postgres',
                'typeVersion': 2.7,
                'position': [740, 80],
                'id': 'wk-subs-011',
                'name': 'Onayli Aboneleri Cek',
                'credentials': {'postgres': {'id': 'PgN8nCred0000002', 'name': 'Postgres (n8n)'}},
                'continueOnFail': True,
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'jsCode': RESEND_PAYLOAD_CODE,
                    'mode': 'runOnceForEachItem',
                },
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [1220, -40],
                'id': 'wk-payload-012',
                'name': 'Resend Payload',
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
                        "to: [$json.to], subject: $json.subject, html: $json.html } }}"
                    ),
                    'options': {'timeout': 30000},
                },
                'type': 'n8n-nodes-base.httpRequest',
                'typeVersion': 4.5,
                'position': [1460, -40],
                'id': 'wk-resend-013',
                'name': 'Resend Gonder',
                'credentials': {
                    'httpHeaderAuth': {'id': 'ReSendAPIKey0002', 'name': 'Resend API Key'}
                },
                'continueOnFail': True,
                'onError': 'continueRegularOutput',
            },
            {
                'parameters': {
                    'amount': 0.2,
                    'unit': 'seconds',
                    'resume': 'timeInterval',
                },
                'type': 'n8n-nodes-base.wait',
                'typeVersion': 1.1,
                'position': [1700, -40],
                'id': 'wk-wait-015b',
                'name': 'Mail Bekle',
            },
            {
                'parameters': {},
                'type': 'n8n-nodes-base.noOp',
                'typeVersion': 1,
                'position': [260, 160],
                'id': 'wk-skip-015',
                'name': 'Bos Hafta Atla',
            },
        ],
        'connections': {
            'Pazartesi 0900': {'main': [[{'node': 'Canli Mod', 'type': 'main', 'index': 0}]]},
            'Test Webhook': {'main': [[{'node': 'Test Modu', 'type': 'main', 'index': 0}]]},
            'Canli Mod': {'main': [[{'node': 'Son 7 Gun Yazilari', 'type': 'main', 'index': 0}]]},
            'Test Modu': {'main': [[{'node': 'Son 7 Gun Yazilari', 'type': 'main', 'index': 0}]]},
            'Son 7 Gun Yazilari': {'main': [[{'node': 'Yazi Var Mi', 'type': 'main', 'index': 0}]]},
            'Yazi Var Mi': {
                'main': [
                    [{'node': 'HTML Hazirla', 'type': 'main', 'index': 0}],
                    [{'node': 'Bos Hafta Atla', 'type': 'main', 'index': 0}],
                ]
            },
            'HTML Hazirla': {'main': [[{'node': 'Test Modu Mu', 'type': 'main', 'index': 0}]]},
            'Test Modu Mu': {
                'main': [
                    [{'node': 'Test Token Cek', 'type': 'main', 'index': 0}],
                    [{'node': 'Onayli Aboneleri Cek', 'type': 'main', 'index': 0}],
                ]
            },
            'Test Token Cek': {'main': [[{'node': 'Test Alici', 'type': 'main', 'index': 0}]]},
            'Test Alici': {'main': [[{'node': 'Resend Payload', 'type': 'main', 'index': 0}]]},
            'Onayli Aboneleri Cek': {'main': [[{'node': 'Resend Payload', 'type': 'main', 'index': 0}]]},
            'Resend Payload': {'main': [[{'node': 'Resend Gonder', 'type': 'main', 'index': 0}]]},
            'Resend Gonder': {'main': [[{'node': 'Mail Bekle', 'type': 'main', 'index': 0}]]},
        },
        'settings': {'executionOrder': 'v1'},
    }


def import_workflow(path: Path) -> None:
    dest = f'/tmp/{path.name}'
    subprocess.run(['docker', 'cp', str(path), f'agent-n8n:{dest}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', f'--input={dest}'],
        check=True,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'],
        check=False,
    )
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )


def restart_n8n() -> None:
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            print('n8n healthy')
            return
        time.sleep(2)


def main() -> None:
    wf = build_workflow()
    out = BACKUP / 'haftalik-ozet-eposta.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    import_workflow(out)
    restart_n8n()
    print('weekly digest workflow imported (schedule active Mon 09:00 Europe/Istanbul)')


if __name__ == '__main__':
    main()
