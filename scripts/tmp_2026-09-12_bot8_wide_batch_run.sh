#!/usr/bin/env bash
# Projede vsechny sestavy ze models.json pres wide_process.js, jedna po druhe
# (jeden Node proces na sestavu -> pamet se uvolni mezi behy). Vysledky uklada
# do OUT_DIR/<id>.json, souhrn tiskne na stdout.
set -euo pipefail
cd /opt/konfigurator
MODELS_JSON="${1:?models.json cesta}"
OUT_DIR="${2:?vystupni adresar}"
mkdir -p "$OUT_DIR"

node -e "
const models = require('$MODELS_JSON');
for (const m of models) {
  for (const id of m.ids) {
    console.log(m.kod + ' ' + id + ' ' + m.base);
  }
}
" > "$OUT_DIR/_worklist.txt"

while read -r kod id base; do
  echo "=== $kod id=$id ==="
  if node scripts/tmp_2026-09-12_bot8_wide_process.js "$id" "$base" "$OUT_DIR/${id}.json" 2>"$OUT_DIR/${id}.stderr"; then
    echo "  OK"
  else
    echo "  FAIL (viz $OUT_DIR/${id}.json a ${id}.stderr)"
    tail -c 2000 "$OUT_DIR/${id}.stderr" | sed 's/^/    /'
  fi
done < "$OUT_DIR/_worklist.txt"
