#!/usr/bin/env python3
"""Send Telegram + email notifications for exec #537 recovery posts."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
MANIFEST = ROOT / 'n8n/backups/exec537-recovery-manifest.json'
ENV_PATH = ROOT / 'n8n/.env'
SUBSCRIBERS_PATH = ROOT / 'n8n/data/telegram-subscribers.jsonl'
RESULTS_PATH = ROOT / 'n8n/backups/exec537-notify-results.json'
EMAIL_WEBHOOK = 'https://n8n.omerfarukturegun.com.tr/webhook/haber-email-notify'
SITE_BASE = 'https://bilisimpostasi.com.tr/posts'
ADMIN_CHAT_ID = '6675249884'
DELAY_SEC = 2.5


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def truncate_desc(desc: str, limit: int = 150) -> str:
    desc = (desc or '').strip()
    if len(desc) <= limit:
        return desc
    cut = desc[: limit - 1].rsplit(' ', 1)[0]
    return cut.rstrip('.,;:') + '…'


def telegram_send(token: str, chat_id: str | int, text: str) -> dict:
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({
        'chat_id': int(chat_id) if str(chat_id).lstrip('-').isdigit() else chat_id,
        'text': text,
        'disable_web_page_preview': True,
    }).encode('utf-8')
    req = urllib.request.Request(
        url, data=payload, headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {'ok': True, 'http_status': resp.status, 'body': resp.read().decode()[:500]}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'http_status': e.code, 'body': e.read().decode(errors='replace')[:500]}
    except Exception as e:
        return {'ok': False, 'http_status': None, 'body': str(e)[:500]}


def email_send(text: str, post_count: int) -> dict:
    payload = json.dumps({'text': text, 'post_count': post_count}).encode('utf-8')
    req = urllib.request.Request(
        EMAIL_WEBHOOK, data=payload, headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return {'ok': True, 'http_status': resp.status, 'body': resp.read().decode()[:800]}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'http_status': e.code, 'body': e.read().decode(errors='replace')[:800]}
    except Exception as e:
        return {'ok': False, 'http_status': None, 'body': str(e)[:800]}


def load_subscribers(path: Path) -> list[int]:
    ids: list[int] = []
    if not path.exists():
        return ids
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ids.append(int(json.loads(line)['chat_id']))
        except Exception:
            continue
    return ids


def admin_message(title: str, description: str, slug: str) -> str:
    return (
        '📰 Yeni yazı yayınlandı!\n\n'
        f'{title}\n\n'
        f'{truncate_desc(description, 150)}\n\n'
        f'Habere gitmek için: {SITE_BASE}/{slug}/'
    )


def main() -> int:
    t0 = time.time()
    env = load_env(ENV_PATH)
    token = env.get('TELEGRAM_BOT_TOKEN', '')
    admin_id = env.get('TELEGRAM_CHAT_ID', ADMIN_CHAT_ID) or ADMIN_CHAT_ID
    if not token:
        print('ERROR: TELEGRAM_BOT_TOKEN missing', file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    posts = sorted(manifest.get('recovered') or [], key=lambda p: p.get('dosya_adi', ''))
    if not posts:
        print('ERROR: no recovered posts in manifest', file=sys.stderr)
        return 1

    results: dict = {
        'execution': 537,
        'posts_used': len(posts),
        'admin_messages': [],
        'subscriber_digests': [],
        'email': None,
        'sample_admin_message': None,
        'digest_text': None,
        'counts': {},
        'verifications': {},
        'elapsed_seconds': None,
    }

    for i, post in enumerate(posts):
        text = admin_message(post['baslik'], post.get('ozet') or '', post['dosya_adi'])
        if results['sample_admin_message'] is None:
            results['sample_admin_message'] = text
        r = telegram_send(token, admin_id, text)
        results['admin_messages'].append({
            'slug': post['dosya_adi'],
            'ok': r['ok'],
            'http_status': r['http_status'],
            'error_sample': None if r['ok'] else r['body'],
        })
        time.sleep(DELAY_SEC)

    digest_lines = ['🆕 Yeni yazılar:', '']
    for idx, post in enumerate(posts, 1):
        digest_lines.append(f"{idx}. {post['baslik']} - {SITE_BASE}/{post['dosya_adi']}/")
    digest_text = '\n'.join(digest_lines)
    results['digest_text'] = digest_text

    subscribers = load_subscribers(SUBSCRIBERS_PATH) or [int(admin_id)]
    for chat_id in subscribers:
        r = telegram_send(token, chat_id, digest_text)
        results['subscriber_digests'].append({
            'chat_id': chat_id,
            'ok': r['ok'],
            'http_status': r['http_status'],
            'error_sample': None if r['ok'] else r['body'],
        })
        time.sleep(DELAY_SEC)

    email_text = '\n'.join(
        f"{idx}. {post['baslik']} - {SITE_BASE}/{post['dosya_adi']}/"
        for idx, post in enumerate(posts, 1)
    )
    email_r = email_send(email_text, len(posts))
    results['email'] = {
        'ok': email_r['ok'],
        'http_status': email_r['http_status'],
        'response_sample': email_r['body'],
        'post_count': len(posts),
    }

    admin_ok = sum(1 for m in results['admin_messages'] if m['ok'])
    sub_ok = sum(1 for m in results['subscriber_digests'] if m['ok'])
    sample = results['sample_admin_message'] or ''
    results['counts'] = {
        'admin_ok': admin_ok,
        'admin_total': len(results['admin_messages']),
        'subscriber_ok': sub_ok,
        'subscriber_total': len(results['subscriber_digests']),
        'email_ok': 1 if email_r['ok'] else 0,
        'post_count': len(posts),
    }
    results['verifications'] = {
        'sample_admin_is_short_format': '📰 Yeni yazı yayınlandı!' in sample and 'Habere gitmek için:' in sample,
        'sample_link_correct': 'https://bilisimpostasi.com.tr/posts/' in sample,
        'digest_links_correct': all(
            f"https://bilisimpostasi.com.tr/posts/{p['dosya_adi']}/" in digest_text for p in posts
        ),
    }
    results['elapsed_seconds'] = round(time.time() - t0, 2)
    RESULTS_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'results_path': str(RESULTS_PATH),
        'counts': results['counts'],
        'verifications': results['verifications'],
        'elapsed_seconds': results['elapsed_seconds'],
    }, ensure_ascii=False, indent=2))
    tg_total = results['counts']['admin_total'] + results['counts']['subscriber_total']
    tg_ok = admin_ok + sub_ok
    return 0 if tg_ok == tg_total and email_r['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
