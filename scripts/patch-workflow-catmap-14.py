#!/usr/bin/env python3
"""Expand Unsplash catMap in Anahtar Kelime Cikar for 14 categories."""
from __future__ import annotations

import json
import re
import subprocess
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/root/agent-icerik-sistemi')
BACKUP = ROOT / 'n8n/backups'
WF_ID = 'zVyc6gzToDe5mhc2'

NEW_MAP = """const catMap = {
    'Büyük Dil Modelleri': 'large language model AI',
    'Large Language Models': 'large language model AI',
    'AI Ajanları & Otomasyon': 'AI agent automation robot',
    'AI Agents & Automation': 'AI agent automation robot',
    'Siber Güvenlik': 'cybersecurity digital security',
    'Cybersecurity': 'cybersecurity digital security',
    'Açık Kaynak': 'open source software linux',
    'Open Source': 'open source software linux',
    'Yazılım & Geliştirici Araçları': 'software development coding',
    'Software & Dev Tools': 'software development coding',
    'Donanım & Çipler': 'computer hardware chip processor',
    'Hardware & Chips': 'computer hardware chip processor',
    'Mobil & Giyilebilir': 'smartphone wearable mobile',
    'Mobile & Wearables': 'smartphone wearable mobile',
    'Akıllı Ev & IoT': 'smart home IoT devices',
    'Smart Home & IoT': 'smart home IoT devices',
    'Ses & Kulaklık': 'headphones audio speaker',
    'Audio & Headphones': 'headphones audio speaker',
    'Otonom & Elektrikli Araçlar': 'electric vehicle autonomous car',
    'Autonomous & Electric Vehicles': 'electric vehicle autonomous car',
    'Bulut & Altyapı': 'cloud computing data center',
    'Cloud & Infrastructure': 'cloud computing data center',
    'Uzay & Drone': 'space rocket satellite drone',
    'Space & Drones': 'space rocket satellite drone',
    'Sosyal Medya & Platformlar': 'social media network platform',
    'Social Media & Platforms': 'social media network platform',
    'Oyun & Eğlence': 'gaming console esports',
    'Gaming & Entertainment': 'gaming console esports',
    'Yapay Zeka': 'artificial intelligence semiconductor',
    'AI': 'artificial intelligence semiconductor',
    'Teknoloji': 'technology innovation',
    'Technology': 'technology innovation',
    'Güvenlik': 'cybersecurity digital security',
    'Security': 'cybersecurity digital security',
  };"""


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    pre = BACKUP / f'haber-yayinlama-{stamp}-pre-catmap.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-catmap-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-catmap-pre.json', str(pre)], check=True)
    data = json.loads(pre.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    code = by['Anahtar Kelime Cikar']['parameters']['jsCode']
    m = re.search(r'const catMap = \{[\s\S]*?\};', code)
    if not m:
        raise SystemExit('catMap not found')
    code = code[: m.start()] + NEW_MAP + code[m.end() :]
    by['Anahtar Kelime Cikar']['parameters']['jsCode'] = code
    out = BACKUP / 'haber-yayinlama-catmap14-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    subprocess.run(['docker', 'cp', str(out), 'agent-n8n:/tmp/wf-catmap.json'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-catmap.json'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'], check=False)
    subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
    for _ in range(40):
        r = subprocess.run(
            ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
            capture_output=True,
        )
        if r.returncode == 0:
            print('OK')
            break
        time.sleep(2)


if __name__ == '__main__':
    main()
