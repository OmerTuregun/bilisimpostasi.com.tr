#!/usr/bin/env python3
"""Migrate TR/EN posts to 14 fine-grained categories (rule-based). Write unmatched list."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
TR_DIR = ROOT / 'site/src/content/posts/tr'
EN_DIR = ROOT / 'site/src/content/posts/en'
REPORT_DIR = ROOT / 'n8n/backups'
UNMATCHED_PATH = REPORT_DIR / 'category-unmatched-20260908.json'
SUMMARY_PATH = REPORT_DIR / 'category-migrate-20260908-summary.json'

# TR label → EN label (must match site/src/i18n/config.ts)
TR_TO_EN = {
    'Büyük Dil Modelleri': 'Large Language Models',
    'Siber Güvenlik': 'Cybersecurity',
    'Donanım & Çipler': 'Hardware & Chips',
    'Açık Kaynak': 'Open Source',
    'Yazılım & Geliştirici Araçları': 'Software & Dev Tools',
    'AI Ajanları & Otomasyon': 'AI Agents & Automation',
    'Otonom & Elektrikli Araçlar': 'Autonomous & Electric Vehicles',
    'Mobil & Giyilebilir': 'Mobile & Wearables',
    'Ses & Kulaklık': 'Audio & Headphones',
    'Uzay & Drone': 'Space & Drones',
    'Bulut & Altyapı': 'Cloud & Infrastructure',
    'Akıllı Ev & IoT': 'Smart Home & IoT',
    'Sosyal Medya & Platformlar': 'Social Media & Platforms',
    'Oyun & Eğlence': 'Gaming & Entertainment',
}

# first-match rules (AI security → Siber, Enerji → Bulut within the approved 14)
RULES: list[tuple[str, str]] = [
    ('Siber Güvenlik', r'siber|guvenlik-acig|zafiyet|malware|ransomware|phishing|parola|hack|breach|cve|kimlik-av|sifirinci|zero-day|saldiri|sertifika|rsa|veri-sizinti|siber-tehdit|siber-saldiri|guvenlik|ai-guven|yapay-zeka-guven|ai-etik|alignment|deepfake|jailbreak|prompt-injection|model-guven|ai-guvenlik|homomorphic|kriptografi|gizlilik'),
    ('AI Ajanları & Otomasyon', r'ai-ajan|ajan-|agentic|otonom-ajan|rpa|keenable|chime|ajanlar|multi-agent|multi-ajan'),
    ('Büyük Dil Modelleri', r'\b(llm|gpt|claude|gemini|llama|mistral|openai|anthropic|deepseek|qwen|grok|chatgpt|dil-model|language-model|copilot|chatbot|benchmark)\b|dil modeli|dil-modelleri|hallupeer'),
    ('Açık Kaynak', r'acik-kaynak|open-source|github|linux|foss|netbsd|git-hosting|pushin'),
    ('Yazılım & Geliştirici Araçları', r'yazilim|developer|programlama|api-|sdk|framework|devops|kod-|coding|javascript|python|rust|web-gelistirme|gelistirici|adobe|sql|codepen'),
    ('Akıllı Ev & IoT', r'akilli-ev|iot|hue|smart-home|akilli-isik|thermostat|matter|philips-hue|robot-supurge|ev-otomasyon|google-home|ev-akilli'),
    ('Ses & Kulaklık', r'kulaklik|airpods|ses-teknoloji|audio|hoparlor|speaker|mikrofon|piyano|muzik'),
    ('Otonom & Elektrikli Araçlar', r'elektrikli|otomobil|otonom-arac|tesla|batarya|robotaksi|self-driving|otonom|arac-|sarj|carplay|dacia'),
    ('Donanım & Çipler', r'islemci|gpu|nvidia|amd|intel|chip|donanim|laptop|pc-|macbook|ssd|ram-|anakart|chipset|windows|depolama|nadir-toprak|raspberry|router'),
    ('Bulut & Altyapı', r'bulut|cloud|aws|azure|gcp|veri-merkezi|data-center|kubernetes|serverless|hosting|cdn|cloudflare|enerji|gunes|nukleer|yenilenebilir|grid|maden|minetrace|jeotermal'),
    ('Sosyal Medya & Platformlar', r'twitter|tiktok|instagram|facebook|meta-|youtube|sosyal-medya|reddit|platform'),
    ('Mobil & Giyilebilir', r'iphone|android|smartphone|telefon|wearable|saat-|watch|pixel-|samsung|giyilebilir|vive|gozluk|fairphone|xiaomi|fold'),
    ('Uzay & Drone', r'uzay|spacex|nasa|uydu|drone|roket|mars|orbit|stoke'),
    ('Oyun & Eğlence', r'oyun|gaming|playstation|xbox|nintendo|konsol|steam|gta|anbernic'),
]


def norm(s: str) -> str:
    return (
        s.lower()
        .replace('ç', 'c')
        .replace('ğ', 'g')
        .replace('ı', 'i')
        .replace('ö', 'o')
        .replace('ş', 's')
        .replace('ü', 'u')
    )


def parse_fm_block(text: str) -> tuple[str, str, str] | None:
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    if not m:
        return None
    return m.group(1), m.group(2), text


def get_field(block: str, key: str) -> str:
    mm = re.search(rf'^{key}:\s*"(.*)"\s*$', block, re.M)
    if mm:
        return mm.group(1)
    mm = re.search(rf'^{key}:\s*(.+)\s*$', block, re.M)
    return mm.group(1).strip().strip('"') if mm else ''


def get_tags(block: str) -> list[str]:
    tags: list[str] = []
    in_tags = False
    for line in block.splitlines():
        if line.startswith('tags:'):
            in_tags = True
            continue
        if in_tags:
            if line.startswith('  - '):
                tags.append(line[4:].strip().strip('"\''))
            elif line.startswith('tagLabels') or (line and not line.startswith(' ')):
                break
    return tags


def set_kategori(block: str, value: str) -> str:
    if re.search(r'^kategori:\s*', block, re.M):
        return re.sub(r'^kategori:\s*.*$', f'kategori: "{value}"', block, count=1, flags=re.M)
    # insert after pubDate
    if re.search(r'^pubDate:\s*', block, re.M):
        return re.sub(
            r'^(pubDate:\s*.*)$',
            rf'\1\nkategori: "{value}"',
            block,
            count=1,
            flags=re.M,
        )
    return f'kategori: "{value}"\n' + block


def classify(title: str, tags: list[str]) -> str | None:
    blob = norm(' '.join(tags) + ' ' + title)
    for name, pat in RULES:
        if re.search(pat, blob, re.I):
            return name
    if 'yapay-zeka' in tags or 'ai' in tags:
        return 'Büyük Dil Modelleri'
    return None


def find_en(tr_stem: str) -> Path | None:
    p = EN_DIR / f'{tr_stem}.md'
    if p.exists():
        return p
    m = re.search(r'(20\d{6}-\d{6})$', tr_stem)
    if not m:
        return None
    hits = list(EN_DIR.glob(f'*-{m.group(1)}.md'))
    return hits[0] if len(hits) == 1 else None


def main() -> None:
    assigned = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    unmatched: list[dict] = []
    migrated = 0
    en_migrated = 0

    for path in sorted(TR_DIR.glob('*.md')):
        text = path.read_text(encoding='utf-8')
        parsed = parse_fm_block(text)
        if not parsed:
            unmatched.append({'slug': path.stem, 'title': '?', 'reason': 'no-frontmatter'})
            continue
        block, body, _ = parsed
        title = get_field(block, 'title')
        old_cat = get_field(block, 'kategori')
        tags = get_tags(block)
        new_cat = classify(title, tags)
        if not new_cat:
            unmatched.append({
                'slug': path.stem,
                'title': title,
                'old_kategori': old_cat,
                'tags': tags[:8],
            })
            continue

        new_block = set_kategori(block, new_cat)
        path.write_text(f'---\n{new_block}\n---\n{body}', encoding='utf-8')
        migrated += 1
        assigned[new_cat] += 1
        if len(examples[new_cat]) < 5:
            examples[new_cat].append(title)

        en_path = find_en(path.stem)
        if en_path and en_path.exists():
            et = en_path.read_text(encoding='utf-8')
            ep = parse_fm_block(et)
            if ep:
                eb, ebody, _ = ep
                en_label = TR_TO_EN[new_cat]
                eb2 = set_kategori(eb, en_label)
                en_path.write_text(f'---\n{eb2}\n---\n{ebody}', encoding='utf-8')
                en_migrated += 1

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    UNMATCHED_PATH.write_text(
        json.dumps(unmatched, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    summary = {
        'migrated_tr': migrated,
        'migrated_en': en_migrated,
        'unmatched': len(unmatched),
        'counts': dict(assigned.most_common()),
        'examples': {k: examples[k] for k in assigned},
        'unmatched_path': str(UNMATCHED_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('\n=== UNMATCHED (for manual review) ===')
    for i, u in enumerate(unmatched, 1):
        print(f"{i:2d}. {u.get('title','?')}")
        print(f"    slug: {u.get('slug')} | eski: {u.get('old_kategori')} | tags: {u.get('tags')}")


if __name__ == '__main__':
    main()
