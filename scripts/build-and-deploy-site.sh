#!/bin/bash
set -euo pipefail

SITE_DIR="/root/agent-icerik-sistemi/site"
DEPLOY_DIR="/var/www/blog"

export NVM_DIR="/root/.nvm"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
fi
if ! command -v npm >/dev/null 2>&1; then
  export PATH="/root/.nvm/versions/node/v22.19.0/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
fi

cd "$SITE_DIR"
npm run build

mkdir -p "$DEPLOY_DIR"
rsync -a --delete "$SITE_DIR/dist/" "$DEPLOY_DIR/"
echo "Site güncellendi: $(date) -> $DEPLOY_DIR"

# Warm Cloudflare/R2 edge cache for homepage covers (first paint, no visitor wait).
python3 - <<'PY' || true
import re, concurrent.futures, urllib.request
from pathlib import Path
html = Path("/var/www/blog/index.html").read_text(encoding="utf-8", errors="ignore")
urls = list(dict.fromkeys(re.findall(r'https://pub-[a-z0-9]+\.r2\.dev/[^"\s>]+\.(?:jpg|jpeg|png|webp)', html)))[:16]
def hit(u: str) -> str:
    try:
        req = urllib.request.Request(u, method="GET", headers={"User-Agent": "bilisimpostasi-cover-warmup/1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read(64)
            return f"{r.status} {u}"
    except Exception as e:
        return f"ERR {u} ({e})"
if urls:
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for line in ex.map(hit, urls):
            print("cover-warmup:", line)
else:
    print("cover-warmup: no r2 cover urls on homepage")
PY
