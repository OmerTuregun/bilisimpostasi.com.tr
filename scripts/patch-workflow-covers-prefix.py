#!/usr/bin/env python3
"""Fix Gorsel Bilgi Hazirla so R2 key and public URL both use covers/ prefix."""
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
R2_BASE = 'https://pub-880c98af22074b02b5f5237e1b3a0bad.r2.dev'


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    pre = BACKUP / f'haber-yayinlama-{stamp}-pre-covers-prefix.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-covers-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-covers-pre.json', str(pre)], check=True)
    data = json.loads(pre.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    code = by['Gorsel Bilgi Hazirla']['parameters']['jsCode']

    # Ensure dosya_adi is covers/{slug}-{ts}.jpg
    if "const dosya_adi = 'covers/' +" in code or 'const dosya_adi = "covers/" +' in code:
        print('dosya_adi already has covers/ prefix')
    else:
        old = "const dosya_adi = slug.slice(0, 50) + '-' + ts + '.jpg';"
        new = "const dosya_adi = 'covers/' + slug.slice(0, 50) + '-' + ts + '.jpg';"
        if old not in code:
            raise SystemExit('dosya_adi line not found')
        code = code.replace(old, new, 1)

    # Ensure URL uses R2_BASE + '/' + dosya_adi (dosya_adi already includes covers/)
    # Replace any bare base+dosya without covers awareness
    code2 = re.sub(
        r"gorsel_r2_url:\s*'https://pub-[a-z0-9]+\.r2\.dev/' \+ dosya_adi",
        f"gorsel_r2_url: '{R2_BASE}/' + dosya_adi",
        code,
    )
    if "gorsel_r2_url: '" not in code2 and 'gorsel_r2_url:' not in code2:
        raise SystemExit('gorsel_r2_url not found after patch')

    # Guard: if somehow dosya_adi lacks covers/, URL builder still ok since dosya_adi has it
    by['Gorsel Bilgi Hazirla']['parameters']['jsCode'] = code2

    # R2 Yukle already uses gorsel_dosya_adi as fileName — will now be covers/...
    out = BACKUP / 'haber-yayinlama-covers-prefix-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)

    subprocess.run(['docker', 'cp', str(out), 'agent-n8n:/tmp/wf-covers.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-covers.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )

    # Don't restart if publish waiting
    running = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT count(*) FROM execution_entity WHERE \"workflowId\"='{WF_ID}' AND status IN ('running','waiting');"],
        text=True,
    ).strip()
    print('running/waiting', running)
    if running == '0':
        subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
        for _ in range(40):
            r = subprocess.run(
                ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
                capture_output=True,
            )
            if r.returncode == 0:
                print('healthy')
                break
            time.sleep(2)
    else:
        print('SKIP restart — active execution')

    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    code = {n['name']: n for n in json.loads(raw)}['Gorsel Bilgi Hazirla']['parameters']['jsCode']
    assert "const dosya_adi = 'covers/' +" in code
    assert f"{R2_BASE}/' + dosya_adi" in code or f'{R2_BASE}/" + dosya_adi' in code
    print('verify OK')


if __name__ == '__main__':
    main()
