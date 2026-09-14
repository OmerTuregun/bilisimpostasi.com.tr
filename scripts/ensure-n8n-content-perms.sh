#!/bin/bash
# Ensure n8n (uid 1000) can read/write content posts + publish queue.
# Safe to run from cron and from build-and-deploy-site.sh.
set -euo pipefail

CONTENT="/root/agent-icerik-sistemi/site/src/content"
POSTS="${CONTENT}/posts"
QUEUE="${CONTENT}/_queue"
PENDING="${QUEUE}/pending.jsonl"
OWNER_UID=1000
OWNER_GID=1000

mkdir -p "${POSTS}/tr" "${POSTS}/en" "${QUEUE}"

if [[ ! -e "${PENDING}" ]]; then
  : > "${PENDING}"
fi

chown -R "${OWNER_UID}:${OWNER_GID}" "${POSTS}" "${QUEUE}"
chmod -R u+rwX,g+rX "${POSTS}" "${QUEUE}"

# Explicit file ownership (in case pending was recreated by root)
chown "${OWNER_UID}:${OWNER_GID}" "${PENDING}"
chmod u+rw,g+r "${PENDING}"

echo "$(date -Is) ensure-n8n-content-perms: ok posts+queue -> ${OWNER_UID}:${OWNER_GID} pending=$(wc -c < "${PENDING}")B"
