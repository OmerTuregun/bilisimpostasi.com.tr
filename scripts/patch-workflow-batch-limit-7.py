#!/usr/bin/env python3
"""Raise BATCH_LIMIT 5 → 7 (user-approved Sep 2026)."""
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


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    pre = BACKUP / f'haber-yayinlama-{stamp}-pre-batch7.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow', f'--id={WF_ID}', '--output=/tmp/wf-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-pre.json', str(pre)], check=True)

    data = json.loads(pre.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}
    code = by['Haber Listesini Hazirla']['parameters']['jsCode']
    if 'BATCH_LIMIT = 5' not in code:
        raise SystemExit('BATCH_LIMIT = 5 not found in live workflow')
    code = code.replace('BATCH_LIMIT = 5', 'BATCH_LIMIT = 7')
    by['Haber Listesini Hazirla']['parameters']['jsCode'] = code

    out = BACKUP / 'haber-yayinlama-batch7-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    subprocess.run(['docker', 'cp', str(out), 'agent-n8n:/tmp/wf-batch7.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-batch7.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'], check=False)

    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    assert 'BATCH_LIMIT = 7' in raw
    assert 'BATCH_LIMIT = 5' not in raw
    print('BATCH_LIMIT=7 live OK')


if __name__ == '__main__':
    main()
