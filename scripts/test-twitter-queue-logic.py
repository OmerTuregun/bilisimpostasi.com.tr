#!/usr/bin/env python3
"""Unit tests for Twitter queue scheduling + tweet char budget (emoji format)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

HASHTAG = {
    'Yapay Zeka': '#YapayZeka',
    'Teknoloji': '#Teknoloji',
    'Güvenlik': '#SiberGuvenlik',
    'AI': '#YapayZeka',
    'Technology': '#Teknoloji',
    'Security': '#SiberGuvenlik',
    'Siber': '#SiberGuvenlik',
}
EMOJI = {
    'Yapay Zeka': '🤖',
    'AI': '🤖',
    'Teknoloji': '💻',
    'Technology': '💻',
    'Güvenlik': '🔒',
    'Security': '🔒',
    'Siber': '🔒',
}
TCO_LEN = 23
LIMIT = 280
CTA = 'Devamı için ⬇️'
CTA_PREFIX = 'Devamı için '


def pick_emoji(kategori: str) -> str:
    if kategori in EMOJI:
        return EMOJI[kategori]
    lower = (kategori or '').lower()
    if 'yapay' in lower or lower == 'ai' or 'ai' in lower.split():
        return '🤖'
    if 'teknoloji' in lower or 'technology' in lower:
        return '💻'
    if 'güvenlik' in lower or 'guvenlik' in lower or 'security' in lower or 'siber' in lower:
        return '🔒'
    return '📰'


def schedule_slots(n: int, cycle_minutes: int = 180):
    step = cycle_minutes / n
    return [i * step for i in range(n)], step


def weighted_len(emoji: str, title: str, summary: str, tag: str) -> int:
    # emoji=2, ⬇️=2, link=23; other chars at JS string length 1
    return (
        2  # start emoji
        + 1  # space
        + len(title)
        + 2  # \n\n
        + len(summary)
        + 2  # \n\n
        + len(CTA_PREFIX)
        + 2  # ⬇️
        + 1  # \n
        + TCO_LEN
        + 2  # \n\n
        + len(tag)
    )


def build_tweet(title: str, summary: str, link: str, kategori: str) -> tuple[str, int, str, str]:
    emoji = pick_emoji(kategori)
    tag = HASHTAG.get(kategori, '#Teknoloji')
    t = title.strip()
    s = (summary or '').strip()

    fixed = weighted_len(emoji, '', '', tag)
    budget = max(20, LIMIT - fixed)

    if len(t) + len(s) > budget:
        left_for_summary = budget - len(t)
        if left_for_summary < 0:
            title_max = max(20, budget - 4)
            if len(t) > title_max:
                t = t[: max(1, title_max - 3)].rstrip() + '...'
            rem = budget - len(t)
            if rem <= 4:
                s = ''
            elif len(s) > rem:
                s = s[: max(1, rem - 3)].rstrip() + '...'
        elif len(s) > left_for_summary:
            if left_for_summary <= 4:
                s = ''
                if len(t) > budget:
                    t = t[: max(1, budget - 3)].rstrip() + '...'
            else:
                s = s[: max(1, left_for_summary - 3)].rstrip() + '...'

    w = weighted_len(emoji, t, s, tag)
    while w > LIMIT and len(t) > 4:
        t = t[: max(1, len(t) - 4)].rstrip() + '...'
        w = weighted_len(emoji, t, s, tag)
    while w > LIMIT and len(s) > 0:
        if len(s) <= 4:
            s = ''
        else:
            s = s[: max(1, len(s) - 4)].rstrip() + '...'
        w = weighted_len(emoji, t, s, tag)

    text = f'{emoji} {t}\n\n{s}\n\n{CTA}\n{link}\n\n{tag}'
    return text, weighted_len(emoji, t, s, tag), tag, emoji


def main() -> None:
    print('=== Schedule simulation (5 posts / 180 min) ===')
    slots, step = schedule_slots(5)
    print(f'step={step} min')
    base = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    for i, m in enumerate(slots):
        at = base + timedelta(minutes=m)
        print(f'  i={i} +{m:.0f}m -> {at.isoformat()}')
    assert slots == [0, 36, 72, 108, 144]

    print('\n=== Char limit: long title+summary ===')
    long_title = 'A' * 200
    long_summary = 'B' * 200
    text, w, tag, emoji = build_tweet(
        long_title,
        long_summary,
        'https://bilisimpostasi.com.tr/posts/ornek-cok-uzun-slug-test/',
        'Yapay Zeka',
    )
    print(f'weighted_len={w} (limit {LIMIT}) emoji={emoji} tag={tag}')
    print('--- tweet preview ---')
    print(text)
    print('---')
    assert w <= LIMIT, w
    assert 'Devamı için ⬇️' in text
    assert text.startswith('🤖 ')

    samples = []
    cases = [
        (
            'Yapay Zeka',
            'OpenAI yeni model duyurusu yaptı',
            'GPT ailesinde performans ve maliyet dengesi değişiyor.',
            'https://bilisimpostasi.com.tr/posts/openai-yeni-model/',
            '🤖',
            '#YapayZeka',
        ),
        (
            'Teknoloji',
            'ABD özel şirketlere siber saldırı yetkisi veriyor',
            'Politika değişikliği riskleri artırabilir.',
            'https://bilisimpostasi.com.tr/posts/ornek/',
            '💻',
            '#Teknoloji',
        ),
        (
            'Güvenlik',
            'Kritik sıfırıncı gün açığı yamalandı',
            'Kurumsal ağlarda acil güncelleme öneriliyor.',
            'https://bilisimpostasi.com.tr/posts/sifirinci-gun/',
            '🔒',
            '#SiberGuvenlik',
        ),
    ]

    print('\n=== Sample tweets (3 categories) ===')
    for kat, title, summary, link, expect_emoji, expect_tag in cases:
        t, ww, tg, em = build_tweet(title, summary, link, kat)
        print(f'\n--- {kat} weighted={ww} ---')
        print(t)
        assert ww <= LIMIT, ww
        assert 'Devamı için ⬇️' in t
        assert em == expect_emoji, (em, expect_emoji)
        assert tg == expect_tag
        assert t.startswith(expect_emoji + ' ')
        samples.append((kat, t, ww, em, tg))

    # else → 📰
    t_else, w_else, _, em_else = build_tweet('Genel başlık', 'Özet.', 'https://bilisimpostasi.com.tr/x/', 'Spor')
    assert em_else == '📰'
    assert w_else <= LIMIT
    assert 'Devamı için ⬇️' in t_else

    print('\n=== Intent URL encode smoke ===')
    sample_ai = samples[0][1]
    encoded = quote(sample_ai, safe='')
    intent = f'https://x.com/intent/post?text={encoded}'
    print(f'intent_len={len(intent)} encoded_prefix={encoded[:80]}...')
    assert 'Devam%C4%B1' in encoded or 'Devam' in encoded

    print('\nALL TESTS PASSED')
    return samples


if __name__ == '__main__':
    main()
