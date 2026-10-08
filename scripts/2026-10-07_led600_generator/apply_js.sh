#!/usr/bin/env bash
# Aplikuje STATICKOU (JS) cast 'LED 600 do generatoru' na ZIVY strom - volat uvnitr zamku bot8; STATIKA SE ZAPISUJE OKAMZITE ZIVE (pred nasazenim API, ktere zacne posilat typ led_600, to nevadi:
# stary payload typu led_1200 funguje stejne; nove JS umi oba typy). Pri zapisu: 1) vystupy patch_luxdata.py / patch_luxy.py do docasnych souboru + node --check, 2) teprve pak vymena zivych souboru,
# 3) piny ?v= (idempotentni nastroje projektu): scripts/stul_verze.py (stul-luxy.js, piny lux-data uvnitr, stranky generatoru 01-05) a scripts/miniweb_verze.py (embed/stul.html, mini-shopy).
# Pouziti: apply_js.sh [koren_repa]
set -euo pipefail
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
P="$REPO/scripts/2026-10-07_led600_generator/patches_js"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 "$P/patch_luxdata.py" "$REPO/webapp/js/lux/lux-data.js" "$TMP/lux-data.js"
python3 "$P/patch_luxy.py" "$REPO/webapp/js/stul-luxy.js" "$TMP/stul-luxy.js"
node --check "$TMP/lux-data.js"
node --check "$TMP/stul-luxy.js"
cp "$TMP/lux-data.js" "$REPO/webapp/js/lux/lux-data.js"
cp "$TMP/stul-luxy.js" "$REPO/webapp/js/stul-luxy.js"
(cd "$REPO" && api/venv/bin/python3 scripts/stul_verze.py && api/venv/bin/python3 scripts/miniweb_verze.py)
echo "JS aplikovano: webapp/js/stul-luxy.js, webapp/js/lux/lux-data.js + piny (viz git status: stranky generatoru 01-05, embed/stul.html, pripadne miniweb)"
