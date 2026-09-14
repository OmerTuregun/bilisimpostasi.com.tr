#!/usr/bin/env python3
"""Enqueue missed Telegram/email/Twitter notifies for exec 5726 (2026-09-03 09:00 TR)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
SITE_BASE = 'https://bilisimpostasi.com.tr/posts'
OWNER_CHAT = '6675249884'
SUBSCRIBERS = ROOT / 'n8n/data/telegram-subscribers.jsonl'
REPORT = ROOT / 'n8n/backups/exec5726-notify-recovery.json'

POSTS = [
    {
        'dosya_adi': 'ready-cercevesi-kurumsal-ai-ajanlarinin-guvenilir-dagitimi-icin-yeni-standart-20260903-060000',
        'baslik': 'READY Çerçevesi: Kurumsal AI Ajanlarının Güvenilir Dağıtımı için Yeni Standart',
        'ozet': 'Araştırmacılar, benchmark testlerinde başarılı olan AI ajanlarının gerçek kurumsal ortamlarda kullanıma hazır olup olmadığını belirlemek için READY çerçevesini geliştirdi.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'maskills-cok-aracili-llm-sistemlerinde-surekli-beceri-optimizasyonu-20260903-060001',
        'baslik': 'MASkills: Çok Aracılı LLM Sistemlerinde Sürekli Beceri Optimizasyonu',
        'ozet': 'Yeni bir araştırma, yapay zeka ajanlarının deneyimlerinden daha etkili öğrenmesi için yapılandırılmış beceri bilgisini nasıl kullanabileceğini gösteriyor.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'llm-tabanli-i-se-alim-sistemlerinde-gizli-onyargilari-ortaya-cikarmak-20260903-060002',
        'baslik': 'LLM Tabanlı İşe Alım Sistemlerinde Gizli Önyargıları Ortaya Çıkarmak',
        'ozet': 'Araştırmacılar, yapay zeka destekli işe alım kararlarındaki adil olmayan davranışları tespit etmek için süreç odaklı bir tanılama yöntemi geliştirdi.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'chime-yapay-zeka-ajanlarinin-uzun-donem-planlama-yeteneklerini-gelistiren-yeni-yontem-20260903-060003',
        'baslik': 'CHIME: Yapay Zeka Ajanlarının Uzun Dönem Planlama Yeteneklerini Geliştiren Yeni Yöntem',
        'ozet': 'Araştırmacılar, eğitim maliyetleri olmadan çıkarım sırasında öğrenen CHIME adlı kredi-farkında bellek sistemini geliştirdi ve ajanların karmaşık görevleri daha verimli çözmesini sağlıyor.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'toolgate-yapay-zeka-ile-bilimsel-benchmark-testleri-otomatiklestirme-20260903-060004',
        'baslik': 'ToolGate: Yapay Zeka ile Bilimsel Benchmark Testleri Otomatikleştirme',
        'ozet': 'Yeni araştırma, dil modellerini kullanarak bilimsel benchmark sorularının hızla üretilmesini ve doğrulanmasını sağlayan ToolGate sistemini sunuyor.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'dochop-yapay-zeka-modellerinin-karmasik-belge-analizi-yetenegini-test-ediyor-20260903-060005',
        'baslik': 'DocHop: Yapay Zeka Modellerinin Karmaşık Belge Analizi Yeteneğini Test Ediyor',
        'ozet': 'Yeni bir benchmark, çok modaliteli dil modellerinin metin ve görselleri birlikte kullanarak karmaşık mantıksal çıkarımlar yapabilme becerisini ölçüyor.',
        'kategori': 'Yapay Zeka',
    },
    {
        'dosya_adi': 'minetrace-yapay-zeka-ile-maden-kesfinde-seffaflik-ve-etkilesim-20260903-060006',
        'baslik': 'MineTRACE: Yapay Zeka ile Maden Keşfinde Şeffaflık ve Etkileşim',
        'ozet': 'Yeni web sistemi, maden prospektliliği analizinde yapay zekayı kullanarak sekiz değerli metal için kanıta dayalı keşif imkanı sunuyor.',
        'kategori': 'Yapay Zeka',
    },
]


def dq(s: str) -> str:
    return (s or '').replace("'", "''")


def psql(sql: str) -> str:
    return subprocess.check_output(
        ['docker', 'exec', '-i', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c', sql],
        text=True,
    ).strip()


def load_subscribers() -> list[str]:
    ids: list[str] = []
    if SUBSCRIBERS.exists():
        for line in SUBSCRIBERS.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ids.append(str(json.loads(line)['chat_id']))
            except Exception:
                continue
    if OWNER_CHAT not in ids:
        ids.append(OWNER_CHAT)
    return ids


def insert_notify(channel: str, payload: dict) -> str:
    body = json.dumps(payload, ensure_ascii=False)
    sql = (
        "INSERT INTO notify_queue (channel, payload, status, scheduled_at) "
        f"VALUES ('{dq(channel)}', '{dq(body)}'::jsonb, 'pending', now()) "
        "RETURNING id;"
    )
    return psql(sql)


def main() -> None:
    now = datetime.now(timezone.utc)
    owner_lines = []
    sub_lines = ['🆕 Yeni yazılar:', '']
    email_lines = []
    for i, p in enumerate(POSTS, 1):
        slug = p['dosya_adi']
        url = f'{SITE_BASE}/{slug}/'
        owner_lines.append(f"{i}. {p['baslik']}\n{url}")
        sub_lines.append(f"{i}. {p['baslik']} - {url}")
        email_lines.append(f"{i}. {p['baslik']} - {url}")

    owner_text = '📰 Yeni yazı yayınlandı!\n\n' + '\n\n'.join(owner_lines)
    sub_text = '\n'.join(sub_lines)
    email_text = '\n'.join(email_lines)

    inserted = {'notify': [], 'twitter': []}

    oid = insert_notify('telegram_owner', {'chat_id': OWNER_CHAT, 'text': owner_text})
    inserted['notify'].append({'channel': 'telegram_owner', 'id': oid})

    for chat_id in load_subscribers():
        sid = insert_notify('telegram_subscriber', {'chat_id': chat_id, 'text': sub_text})
        inserted['notify'].append({'channel': 'telegram_subscriber', 'id': sid, 'chat_id': chat_id})

    eid = insert_notify('email_digest', {'text': email_text, 'post_count': len(POSTS)})
    inserted['notify'].append({'channel': 'email_digest', 'id': eid})

    step_min = 180 / len(POSTS)
    for i, p in enumerate(POSTS):
        slug = p['dosya_adi']
        summary = (p['ozet'] or '').split('. ')[0][:280]
        scheduled = (now + timedelta(minutes=i * step_min)).isoformat()
        sql = (
            "INSERT INTO twitter_queue (post_slug, post_title, post_summary, post_link, kategori, status, scheduled_at) "
            "SELECT "
            f"'{dq(slug)}', '{dq(p['baslik'])}', '{dq(summary)}', "
            f"'{dq(SITE_BASE)}/{dq(slug)}/', '{dq(p['kategori'])}', 'pending', "
            f"'{dq(scheduled)}'::timestamptz "
            "WHERE NOT EXISTS ("
            f"SELECT 1 FROM twitter_queue t WHERE t.post_slug = '{dq(slug)}' "
            f"OR t.post_link = '{dq(SITE_BASE)}/{dq(slug)}/'"
            ") RETURNING id;"
        )
        tid = psql(sql)
        inserted['twitter'].append({'slug': slug, 'id': tid or None, 'scheduled_at': scheduled})

    REPORT.write_text(json.dumps({
        'execution': 5726,
        'slot': '2026-09-03 09:00 Europe/Istanbul',
        'posts': len(POSTS),
        'inserted': inserted,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(inserted, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
