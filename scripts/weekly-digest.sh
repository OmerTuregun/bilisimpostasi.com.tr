#!/bin/bash
# Build a compact weekly digest for Medium draft (titles + descriptions only).
set -euo pipefail
OUT="/root/agent-icerik-sistemi/site/src/content/weekly-digest.txt"
POSTS_TR="/root/agent-icerik-sistemi/site/src/content/posts/tr"
TMP="$(mktemp)"

# Last 7 days, TR only, newest first, hard cap 40 posts.
mapfile -t FILES < <(find "$POSTS_TR" -mtime -7 -name '*.md' -printf '%T@ %p\n' | sort -nr | awk 'NR<=40 {print $2}')

{
  echo "Haftalik ozet $(date -u +%Y-%m-%dT%H:%M:%SZ) — ${#FILES[@]} yazi"
  echo
  for f in "${FILES[@]}"; do
    [ -f "$f" ] || continue
    title=$(awk '/^title:/{sub(/^title:[[:space:]]*/,""); gsub(/^"|"$/,""); print; exit}' "$f")
    desc=$(awk '/^description:/{sub(/^description:[[:space:]]*/,""); gsub(/^"|"$/,""); print; exit}' "$f")
    kat=$(awk '/^kategori:/{sub(/^kategori:[[:space:]]*/,""); gsub(/^"|"$/,""); print; exit}' "$f")
    date=$(awk '/^pubDate:/{sub(/^pubDate:[[:space:]]*/,""); print; exit}' "$f")
    echo "- [$kat] $title"
    echo "  tarih: $date"
    echo "  ozet: $desc"
    echo
  done
} > "$TMP"

mv "$TMP" "$OUT"
chmod 644 "$OUT"
echo "Weekly digest guncellendi: $(date) bytes=$(wc -c < "$OUT") posts=${#FILES[@]}"
