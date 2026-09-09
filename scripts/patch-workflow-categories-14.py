#!/usr/bin/env python3
"""Update Haber Yayınlama Claude kategori list + EN categoryMap to 14 categories."""
from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'zVyc6gzToDe5mhc2'

OLD_KAT = 'KATEGORİ: [Yapay Zeka | Teknoloji | Güvenlik]'
NEW_KAT = (
    'KATEGORİ: [şu listeden TAM OLARAK birini seç — genel/şemsiye kategori yok: '
    'Büyük Dil Modelleri | AI Ajanları & Otomasyon | Siber Güvenlik | Açık Kaynak | '
    'Yazılım & Geliştirici Araçları | Donanım & Çipler | Mobil & Giyilebilir | '
    'Akıllı Ev & IoT | Ses & Kulaklık | Otonom & Elektrikli Araçlar | Bulut & Altyapı | '
    'Uzay & Drone | Sosyal Medya & Platformlar | Oyun & Eğlence]'
)

NEW_CATEGORY_MAP = """const categoryMap = {
  'Büyük Dil Modelleri': 'Large Language Models',
  'AI Ajanları & Otomasyon': 'AI Agents & Automation',
  'Siber Güvenlik': 'Cybersecurity',
  'Açık Kaynak': 'Open Source',
  'Yazılım & Geliştirici Araçları': 'Software & Dev Tools',
  'Donanım & Çipler': 'Hardware & Chips',
  'Mobil & Giyilebilir': 'Mobile & Wearables',
  'Akıllı Ev & IoT': 'Smart Home & IoT',
  'Ses & Kulaklık': 'Audio & Headphones',
  'Otonom & Elektrikli Araçlar': 'Autonomous & Electric Vehicles',
  'Bulut & Altyapı': 'Cloud & Infrastructure',
  'Uzay & Drone': 'Space & Drones',
  'Sosyal Medya & Platformlar': 'Social Media & Platforms',
  'Oyun & Eğlence': 'Gaming & Entertainment',
  'Yapay Zeka': 'Large Language Models',
  'Teknoloji': 'Hardware & Chips',
  'Güvenlik': 'Cybersecurity',
  'Large Language Models': 'Large Language Models',
  'AI Agents & Automation': 'AI Agents & Automation',
  Cybersecurity: 'Cybersecurity',
  'Open Source': 'Open Source',
  'Software & Dev Tools': 'Software & Dev Tools',
  'Hardware & Chips': 'Hardware & Chips',
  'Mobile & Wearables': 'Mobile & Wearables',
  'Smart Home & IoT': 'Smart Home & IoT',
  'Audio & Headphones': 'Audio & Headphones',
  'Autonomous & Electric Vehicles': 'Autonomous & Electric Vehicles',
  'Cloud & Infrastructure': 'Cloud & Infrastructure',
  'Space & Drones': 'Space & Drones',
  'Social Media & Platforms': 'Social Media & Platforms',
  'Gaming & Entertainment': 'Gaming & Entertainment',
  AI: 'Large Language Models',
  Technology: 'Hardware & Chips',
  Security: 'Cybersecurity',
};"""


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-cat14.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-cat14-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-cat14-pre.json', str(out)], check=True)
    return out


def patch_claude(text: str) -> str:
    if OLD_KAT in text:
        return text.replace(OLD_KAT, NEW_KAT, 1)
    if 'Büyük Dil Modelleri | AI Ajanları' in text:
        return text
    # fallback: any short 3-cat line
    import re
    m = re.search(r'KATEGORİ:\s*\[[^\]]+\]', text)
    if not m:
        raise SystemExit('Claude prompt: KATEGORİ line not found')
    return text[: m.start()] + NEW_KAT + text[m.end() :]


def patch_en_map(code: str) -> str:
    import re
    m = re.search(r'const categoryMap = \{[\s\S]*?\};', code)
    if not m:
        raise SystemExit('EN Markdown: categoryMap not found')
    return code[: m.start()] + NEW_CATEGORY_MAP + code[m.end() :]


def patch_defaults(code: str, old: str, new: str) -> str:
    return code.replace(old, new)


def main() -> None:
    pre = export_live()
    print('backup', pre)
    data = json.loads(pre.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    # Claude prompt — may be in text / messages / options depending on node version
    claude = by['Claude Toplu Yazi Uret']
    params = claude['parameters']
    blob = json.dumps(params, ensure_ascii=False)
    if OLD_KAT not in blob and 'Büyük Dil Modelleri' not in blob:
        # try nested
        pass
    # Prefer messages / text / prompt fields
    replaced = False
    for key in list(params.keys()):
        val = params[key]
        if isinstance(val, str) and 'KATEGORİ' in val:
            params[key] = patch_claude(val)
            replaced = True
        elif isinstance(val, dict):
            s = json.dumps(val, ensure_ascii=False)
            if 'KATEGORİ' in s:
                params[key] = json.loads(patch_claude(s))
                replaced = True
        elif isinstance(val, list):
            s = json.dumps(val, ensure_ascii=False)
            if 'KATEGORİ' in s:
                params[key] = json.loads(patch_claude(s))
                replaced = True
    if not replaced:
        raise SystemExit('Could not find KATEGORİ in Claude node params')

    en = by['EN Markdown Olustur']['parameters']['jsCode']
    by['EN Markdown Olustur']['parameters']['jsCode'] = patch_en_map(en)

    # Defaults in parser / frontmatter if present
    for name in ('Yazilari Ayristir', 'Frontmatter Olustur', 'Post Verisini Geri Yukle'):
        if name not in by:
            continue
        code = by[name]['parameters'].get('jsCode') or ''
        if "|| 'Teknoloji'" in code or '|| "Teknoloji"' in code:
            code = code.replace("|| 'Teknoloji'", "|| 'Donanım & Çipler'")
            code = code.replace('|| "Teknoloji"', '|| "Donanım & Çipler"')
            by[name]['parameters']['jsCode'] = code
        if "kategori || 'Teknoloji'" in code:
            by[name]['parameters']['jsCode'] = code.replace(
                "kategori || 'Teknoloji'", "kategori || 'Donanım & Çipler'"
            )

    out = BACKUP / 'haber-yayinlama-cat14-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)

    subprocess.run(['docker', 'cp', str(out), 'agent-n8n:/tmp/wf-cat14.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-cat14.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )
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

    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    live = {n['name']: n for n in json.loads(raw)}
    assert 'Büyük Dil Modelleri' in json.dumps(live['Claude Toplu Yazi Uret']['parameters'], ensure_ascii=False)
    assert 'Software & Dev Tools' in live['EN Markdown Olustur']['parameters']['jsCode']
    print('verify OK')


if __name__ == '__main__':
    main()
