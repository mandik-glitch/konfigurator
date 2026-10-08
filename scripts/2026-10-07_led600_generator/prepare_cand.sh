#!/usr/bin/env bash
# Postavi KANDIDATNI strom ($1, vychozi $SP/led/cand): api/* = symlinky na zive soubory, jen upravovane soubory jsou kopie vzniklé aplikaci zaplat (patches/*.py) na ZIVY soubor.
# Symlink webapp se vytvari PRED jakymkoli importem (import app bez nej vyrobi skutecny adresar webapp/).  Pouziti: prepare_cand.sh [adresar]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CAND="${1:-${SP:?nastav SP nebo zadej adresar}/led/cand}"
mkdir -p "$CAND/api"
ln -sfn "$REPO/webapp" "$CAND/webapp"
for f in "$REPO"/api/*; do ln -sfn "$f" "$CAND/api/$(basename "$f")"; done
P="$REPO/scripts/2026-10-07_led600_generator/patches"
for par in "patch_konfigurator.py stul_konfigurator.py" "patch_glb.py stul_glb.py" "patch_sse.py stul_sse.py" "patch_osvetleni.py stul_osvetleni.py" \
           "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py"; do
  set -- $par
  rm -f "$CAND/api/$2"
  python3 "$P/$1" "$REPO/api/$2" "$CAND/api/$2"
  python3 -m py_compile "$CAND/api/$2"
done
echo "kandidat pripraven: $CAND/api"
