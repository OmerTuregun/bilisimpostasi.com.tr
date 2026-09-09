#!/usr/bin/env python3
"""Harden Unsplash nodes so 403/rate-limit does not kill the whole publish run."""
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
    pre = BACKUP / f'haber-yayinlama-{stamp}-pre-unsplash-harden.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-ush.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-ush.json', str(pre)], check=True)
    data = json.loads(pre.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    for name in ('Unsplash Arama', 'Unsplash Download Trigger', 'Gorseli Indir'):
        n = by[name]
        # Prefer modern onError; also set continueOnFail for older n8n
        n['onError'] = 'continueRegularOutput'
        n['continueOnFail'] = True
        print('hardened', name)

    out = BACKUP / 'haber-yayinlama-unsplash-harden.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    subprocess.run(['docker', 'cp', str(out), 'agent-n8n:/tmp/wf-ush2.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-ush2.json'],
        check=True,
    )
    subprocess.run(['docker', 'exec', 'agent-n8n', 'n8n', 'publish:workflow', f'--id={WF_ID}'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'update:workflow', f'--id={WF_ID}', '--active=true'],
        check=False,
    )
    # Do NOT restart n8n while execution 8801 may still be running — only restart if idle
    running = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT count(*) FROM execution_entity WHERE \"workflowId\"='{WF_ID}' AND status IN ('running','waiting');"],
        text=True,
    ).strip()
    print('running/waiting execs', running)
    if running == '0':
        subprocess.run(['docker', 'restart', 'agent-n8n'], check=True)
        for _ in range(40):
            r = subprocess.run(
                ['docker', 'exec', 'agent-n8n', 'wget', '-q', '-O-', 'http://127.0.0.1:5678/healthz'],
                capture_output=True,
            )
            if r.returncode == 0:
                print('n8n healthy after restart')
                break
            time.sleep(2)
    else:
        print('SKIP restart — active execution; harden will apply on next publish/restart')
    print('wrote', out)


if __name__ == '__main__':
    main()
