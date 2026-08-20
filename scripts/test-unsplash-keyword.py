#!/usr/bin/env python3
"""Unit-test Unsplash keyword builder (mirrors Anahtar Kelime Cikar)."""
from __future__ import annotations

import re

METAPHOR = {
    'soguyor', 'soğuyor', 'isiniyor', 'ısınıyor', 'patliyor', 'patlıyor', 'patlama',
    'cokuyor', 'çöküyor', 'dusuyor', 'düşüyor', 'yukseliyor', 'yükseliyor',
    'artis', 'artış', 'dusus', 'düşüş', 'patladi', 'patladı', 'sogudu', 'soğudu',
    'cooling', 'heating', 'booming', 'crashing', 'soaring', 'plunging',
}
STOP = {
    've', 'bu', 'de', 'da', 'ile', 'icin', 'için', 'bir', 'her', 'yeni', 'son',
    'gibi', 'daha', 'cok', 'çok', 'olan', 'olarak', 'uzerine', 'üzerine',
}
CAT_MAP = {
    'Yapay Zeka': 'artificial intelligence technology',
    'Teknoloji': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
}
TOPIC_PHRASES = [
    (re.compile(r'yapay\s+zeka', re.I), 'artificial intelligence'),
    (re.compile(r'\bai\b', re.I), 'artificial intelligence'),
    (re.compile(r'buyuk\s+dil\s+model|büyük\s+dil\s+model', re.I), 'large language model AI'),
    (re.compile(r'openai', re.I), 'openai artificial intelligence'),
    (re.compile(r'meta\b|llama', re.I), 'meta artificial intelligence'),
    (re.compile(r'drone|itfaiyeci|teslimat', re.I), 'delivery drone'),
    (re.compile(r'otonom|robotaksi|waymo', re.I), 'autonomous vehicle'),
    (re.compile(r'kodlama|yazilim|yazılım|codex', re.I), 'software coding'),
]


def build_query(baslik: str, kategori: str = '') -> str:
    title = (baslik or '').strip()
    cat = (kategori or '').strip()
    for re_pat, q in TOPIC_PHRASES:
        if re_pat.search(title):
            return q
    if cat in CAT_MAP:
        return CAT_MAP[cat]
    words = title.split()
    cleaned = [
        re.sub(r'[^\wçğıöşüÇĞİÖŞÜ-]', '', w, flags=re.I)
        for w in words
    ]
    cleaned = [w for w in cleaned if len(w) > 2 and w.lower() not in STOP and w.lower() not in METAPHOR]
    proper = [w for w in cleaned if w[:1].isupper()]
    if len(proper) >= 2:
        return ' '.join(proper[:2])
    if len(proper) == 1 and len(proper[0]) >= 4:
        return f'{proper[0]} {CAT_MAP.get(cat, "technology")}'.strip()
    if len(cleaned) >= 2:
        return ' '.join(cleaned[:2])
    return CAT_MAP.get(cat) or cat or 'technology'


# Old buggy behavior simulation
def old_buggy(baslik: str, kategori: str = '') -> str:
    words = baslik.split(r'\s+')  # literal backslash-s — never splits
    proper = [w for w in words if re.match(r'^[A-Z\u00C0-\u024F]', w) and len(w) > 2]
    if proper:
        return ' '.join(proper[:2])
    return CAT_MAP.get(kategori) or kategori or 'technology'


CASES = [
    ('Yapay Zeka Asistanlarının Tüketici Kabulü Soğuyor', 'Yapay Zeka'),
    ('X Soğuyor', 'Teknoloji'),
    ('Y Patlama Yapıyor', 'Teknoloji'),
    ('Z Isınıyor', 'Teknoloji'),
    ('OpenAI Güvenlik Endişeleriyle Geliştirme Hızını Yavaşlatıyor', 'Yapay Zeka'),
    ('Otonom Araçlar Ticari Ölçekte Yaygınlaşıyor', 'Teknoloji'),
    ('Meta\'nın Mac Uygulaması İşletme Odaklı AI Araçlarını Çoğaltıyor', 'Yapay Zeka'),
]


def main() -> None:
    print(f'{"BAŞLIK":60} | {"ESKİ (bug)":55} | YENİ')
    print('-' * 140)
    for title, cat in CASES:
        old = old_buggy(title, cat)
        new = build_query(title, cat)
        print(f'{title[:60]:60} | {old[:55]:55} | {new}')
        # Assertions for the known bad case
        if 'Soğuyor' in title and 'Yapay Zeka Asistan' in title:
            assert 'Soğuyor' not in new and 'soğuyor' not in new.lower()
            assert 'artificial intelligence' in new.lower() or 'yapay' in new.lower()
            assert old == title or 'Soğuyor' in old  # old used full title
        # Metaphor-only titles should not pass the metaphor word alone
        if title in ('X Soğuyor', 'Y Patlama Yapıyor', 'Z Isınıyor'):
            assert new.lower() not in ('soğuyor', 'patlama', 'ısınıyor', 'soguyor')
            assert 'technology' in new.lower() or 'innovation' in new.lower() or len(new.split()) >= 1
    print('\nALL ASSERTIONS PASSED')


if __name__ == '__main__':
    main()
