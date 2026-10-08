#!/usr/bin/env bash
# Postavi KANDIDATNI strom pro BROWSER testy ($1, vychozi $SP/led/mirror2): api/ = kandidat (prepare_cand.sh musi bezet drive), webapp/ = PREKRYV: symlinky na zive soubory kromě 2 upravenych JS
# (js/stul-luxy.js, js/lux/lux-data.js = vystup patches_js/*.py proti zivym souborum), scripts/ = zive. Zive webapp se NEMENI (nikdy nespoustet scripts/stul_verze.py ani miniweb_verze.py v prekryvu: zapisuji pres symlinky).
# Browser test se pak pousti z korene prekryvu (REPO = koren, odkud je skript spusten): viz hlavicka test_led_delka_stranka.js.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT="${1:-${SP:?nastav SP nebo zadej adresar}/led/mirror2}"
CAND="${2:-${SP:?}/led/cand}"
rm -rf "$ROOT"; mkdir -p "$ROOT/webapp/js/lux"
ln -sfn "$CAND/api" "$ROOT/api"
# scripts/ = PREKRYV: symlinky na zive soubory, jen testy dotcene novou volbou (patches_test/*.py) jsou upravene kopie (zive testy se NEMENI; apply.sh je zaplatuje zive)
mkdir -p "$ROOT/scripts"
for e in "$REPO"/scripts/*; do ln -sfn "$e" "$ROOT/scripts/$(basename "$e")"; done
PT="$REPO/scripts/2026-10-07_led600_generator/patches_test"
for par in "patch_test_shop.py 2026-10-02_stul_testy/test_stul_shop.py"; do
  set -- $par
  d="$(dirname "$ROOT/scripts/$2")"; rm -f "$d"; mkdir -p "$d"
  for f in "$REPO/scripts/$(dirname "$2")"/*; do ln -sfn "$f" "$d/$(basename "$f")"; done
  rm -f "$ROOT/scripts/$2"
  python3 "$PT/$1" "$REPO/scripts/$2" "$ROOT/scripts/$2"
done
for e in "$REPO"/webapp/*; do b="$(basename "$e")"; [ "$b" = js ] && continue; ln -sfn "$e" "$ROOT/webapp/$b"; done
for e in "$REPO"/webapp/js/*; do b="$(basename "$e")"; [ "$b" = lux ] || [ "$b" = stul-luxy.js ] && continue; ln -sfn "$e" "$ROOT/webapp/js/$b"; done
for e in "$REPO"/webapp/js/lux/*; do b="$(basename "$e")"; [ "$b" = lux-data.js ] && continue; ln -sfn "$e" "$ROOT/webapp/js/lux/$b"; done
P="$REPO/scripts/2026-10-07_led600_generator/patches_js"
python3 "$P/patch_luxy.py" "$REPO/webapp/js/stul-luxy.js" "$ROOT/webapp/js/stul-luxy.js"
python3 "$P/patch_luxdata.py" "$REPO/webapp/js/lux/lux-data.js" "$ROOT/webapp/js/lux/lux-data.js"
node --check "$ROOT/webapp/js/stul-luxy.js"; node --check "$ROOT/webapp/js/lux/lux-data.js"
echo "kandidatni koren pro browser testy: $ROOT"
