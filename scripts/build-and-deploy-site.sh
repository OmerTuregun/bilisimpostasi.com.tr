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
