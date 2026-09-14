#!/usr/bin/env python3
"""Fix 14:50 silent drop: word filter too high vs Haiku short output + webhook trigger."""
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

NEW_TR_PROMPT = '''=Aşağıdaki TEK teknoloji/AI haberinden BİR blog yazısı üret.

Kaynak haber:
Başlık: {{ $json.baslik }}
Özet: {{ $json.ozet }}
Link: {{ $json.link }}
Kaynak: {{ $json.kaynak }}

SADECE teknoloji ve yapay zeka konulu haberleri işle. Siyaset, göçmenlik,
iç güvenlik, spor, magazin, şirket içi rutin atama gibi düşük değerli
içerikleri KESİNLİKLE atla. Uymuyorsa başka hiçbir şey yazma, SADECE
tek kelime olarak "ATLA" yaz.

Uygunsa çıktı formatı (başka hiçbir şey yazma):

===YAZI===
BAŞLIK: [tek satır, çekici başlık, ** veya tırnak kullanma]
ÖZET: [tek satır kısa özet, ** veya tırnak kullanma]
KATEGORİ: [Yapay Zeka | Teknoloji | Güvenlik]
Link: {{ $json.link }}
İÇERİK:
[markdown]

UZUNLUK:
- İÇERİK hedef 280–340 kelime. 220’nin altına inmek YASAK. 400’ü geçme.
- Kısa tut ama iskelet yazı (150 kelime) yazma.

OKUNAKLILIK:
- Yapı: (1) 1 giriş paragrafı (2–4 cümle) (2) TAM BİR madde listesi
  (3–5 madde, `- ` markdown) (3) 1–2 gövde paragrafı (4) 1 kısa kapanış.
- Madde listesi somut olsun: kim/ne, sayı, ürün, ne değişti.
- İkinci liste yazma. Başlık (##) kullanma. Kalın (**) en fazla 2 kez.
- Paragraflar en fazla 4–5 cümle.

KALITE:
- Kaynağa sadık kal; uydurma özel isim/sayı yok.
- Kelime sayısı veya meta not yazma; sadece yazı.
- İÇERİK tam cümleyle bitsin. Yarım bırakma YASAK.
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-ayristir-140.json'
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
         f'--id={WF_ID}', '--output=/tmp/wf-ayr-pre.json'],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-ayr-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    by['Claude Toplu Yazi Uret']['parameters']['messages']['values'][0]['content'] = NEW_TR_PROMPT

    code = by['Yazilari Ayristir']['parameters']['jsCode']
    old = 'if (words < 250)'
    if old not in code and 'if (words < 350)' in code:
        old = 'if (words < 350)'
    if old not in code:
        raise SystemExit('word threshold not found')
    code = code.replace(old, 'if (words < 140)')
    code = code.replace('word_lt_250', 'word_lt_140').replace('word_lt_350', 'word_lt_140')
    # lists often end without a period on the last bullet
    if 'punct_reject' in code and 'listEndOk' not in code:
        code = code.replace(
            "if (!/[.!?…]\"?$/.test(t)) {",
            "const listEndOk = /(?:^|\\n)-\\s+\\S[\\s\\S]*$/.test(t);\n    if (!/[.!?…]\"?$/.test(t) && !listEndOk) {",
        )
    by['Yazilari Ayristir']['parameters']['jsCode'] = code

    names = {n['name'] for n in wf['nodes']}
    if 'Manuel Tetik' not in names:
        wf['nodes'].append({
            'parameters': {
                'path': 'haber-yayinlama-manuel',
                'httpMethod': 'POST',
                'authentication': 'none',
                'responseMode': 'onReceived',
                'options': {},
            },
            'type': 'n8n-nodes-base.webhook',
            'typeVersion': 2.1,
            'position': [-480, 160],
            'id': 'pub-manual-webhook-0001',
            'name': 'Manuel Tetik',
            'webhookId': 'haber-yayinlama-manuel-hook',
        })
        conn = wf['connections']
        conn['Manuel Tetik'] = {
            'main': [[{'node': 'Kuyruk Dosyasini Garantile', 'type': 'main', 'index': 0}]]
        }

    out = BACKUP / 'haber-yayinlama-ayristir-140-webhook-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-ayr.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-ayr.json'],
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


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    raw = subprocess.check_output(
        ['docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
         f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';"],
        text=True,
    )
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    assert 'words < 140' in by['Yazilari Ayristir']['parameters']['jsCode']
    assert 'Manuel Tetik' in by
    print('verify OK')


if __name__ == '__main__':
    main()
