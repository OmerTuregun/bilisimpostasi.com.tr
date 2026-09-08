#!/usr/bin/env python3
"""Shorter, less wall-of-text articles: lower word target + one bullet list."""
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

UZUNLUK (kısa tut):
- İÇERİK hedef 280–360 kelime. 400’ü geçme. 250’nin altına inme.
- Doldurma cümlesi, tekrar, “bu gelişme önemlidir” klişesi YASAK.

OKUNAKLILIK (tekdüze paragraf duvarı YASAK):
- Yapı: (1) 1 kısa giriş paragrafı (2–4 cümle) (2) TAM BİR madde listesi
  (3–5 madde, `- ` markdown) (3) 1–2 gövde paragrafı (4) 1 kısa kapanış paragrafı.
- Madde listesi somut olsun: kim/ne, sayı, ürün, ne değişti. Yorum cümlesi değil.
- İkinci liste yazma. Başlık (##) kullanma. Kalın (**) en fazla 2 kez.
- Paragraflar kısa kalsın (en fazla 4–5 cümle).

KALITE:
- Kaynağa sadık kal; uydurma özel isim/sayı yok.
- Kelime sayısı veya meta not yazma; sadece yazı.
- İÇERİK tam cümleyle bitsin. Yarım bırakma YASAK.
'''


def export_live() -> Path:
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    out = BACKUP / f'haber-yayinlama-{stamp}-pre-readable.json'
    subprocess.run(
        [
            'docker', 'exec', 'agent-n8n', 'n8n', 'export:workflow',
            f'--id={WF_ID}', '--output=/tmp/wf-readable-pre.json',
        ],
        check=True,
    )
    subprocess.run(['docker', 'cp', 'agent-n8n:/tmp/wf-readable-pre.json', str(out)], check=True)
    return out


def patch(src: Path) -> Path:
    data = json.loads(src.read_text())
    wf = deepcopy(data[0] if isinstance(data, list) else data)
    by = {n['name']: n for n in wf['nodes']}

    claude = by['Claude Toplu Yazi Uret']
    claude['parameters']['messages']['values'][0]['content'] = NEW_TR_PROMPT

    code = by['Yazilari Ayristir']['parameters']['jsCode']
    if 'words < 350' not in code:
        raise SystemExit('expected words < 350 in Yazilari Ayristir')
    by['Yazilari Ayristir']['parameters']['jsCode'] = code.replace(
        'words < 350', 'words < 250'
    ).replace(
        'word_lt_350', 'word_lt_250'
    )

    out = BACKUP / 'haber-yayinlama-article-readable-patched.json'
    out.write_text(json.dumps([wf], ensure_ascii=False), encoding='utf-8')
    print('wrote', out)
    return out


def import_publish(patched: Path) -> None:
    subprocess.run(['docker', 'cp', str(patched), 'agent-n8n:/tmp/wf-readable.json'], check=True)
    subprocess.run(
        ['docker', 'exec', 'agent-n8n', 'n8n', 'import:workflow', '--input=/tmp/wf-readable.json'],
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


def verify() -> None:
    raw = subprocess.check_output(
        [
            'docker', 'exec', 'agent-n8n-postgres', 'psql', '-U', 'n8n', '-d', 'n8n', '-t', '-A', '-c',
            f"SELECT nodes::text FROM workflow_entity WHERE id='{WF_ID}';",
        ],
        text=True,
    )
    nodes = json.loads(raw)
    by = {n['name']: n for n in nodes}
    prompt = by['Claude Toplu Yazi Uret']['parameters']['messages']['values'][0]['content']
    code = by['Yazilari Ayristir']['parameters']['jsCode']
    assert '280–360' in prompt or '280-360' in prompt or '280' in prompt
    assert 'madde listesi' in prompt
    assert '600–700' not in prompt
    assert 'words < 250' in code
    assert 'words < 350' not in code
    print('verify OK')


def main() -> None:
    pre = export_live()
    print('backup', pre)
    patched = patch(pre)
    import_publish(patched)
    verify()


if __name__ == '__main__':
    main()
