#!/bin/bash
set -e
OUT="/root/agent-icerik-sistemi/site/src/content/weekly-digest.txt"
> "$OUT"
find /root/agent-icerik-sistemi/site/src/content/posts -mtime -7 -name "*.md" | while read -r f; do
  echo "=== DOSYA: $(basename "$f") ===" >> "$OUT"
  cat "$f" >> "$OUT"
  echo "" >> "$OUT"
done
echo "Weekly digest güncellendi: $(date)"
