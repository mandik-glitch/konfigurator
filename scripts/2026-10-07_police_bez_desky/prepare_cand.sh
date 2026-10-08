#!/usr/bin/env bash
# Postavi KANDIDATNI strom ($1, vychozi $SP/police/cand): api/* = symlinky na zive soubory, jen upravovane soubory jsou kopie vzniklé aplikaci zaplat (patches/*.py) na ZIVY soubor.
# Symlink webapp se vytvari PRED jakymkoli importem (import app bez nej vyrobi skutecny adresar webapp/).  Pouziti: prepare_cand.sh [adresar]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CAND="${1:-${SP:?nastav SP nebo zadej adresar}/police/cand}"
mkdir -p "$CAND/api"
ln -sfn "$REPO/webapp" "$CAND/webapp"
mkdir -p "$CAND/api/__pycache__"          # LOKALNI bajtkod: symlink na zivy api/__pycache__ by do nej zapisoval pyc kandidatnich souboru
for f in "$REPO"/api/*; do b="$(basename "$f")"; case "$b" in __pycache__|tmp_*) continue;; esac; ln -sfn "$f" "$CAND/api/$b"; done
P="$REPO/scripts/2026-10-07_police_bez_desky/patches"
for par in "patch_konfigurator.py stul_konfigurator.py" "patch_glb.py stul_glb.py" "patch_sse.py stul_sse.py" "patch_koty.py stul_koty.py" "patch_vyrobni_list.py stul_vyrobni_list.py" \
           "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py"; do
  set -- $par
  python3 "$P/$1" "$REPO/api/$2" "$CAND/api/$2.new"          # atomicky: nejdriv do .new, preklad do /dev/null (bez bajtkodu), pak mv (nahradi i symlink)
  python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$CAND/api/$2.new"
  mv -f "$CAND/api/$2.new" "$CAND/api/$2"
done
echo "kandidat pripraven: $CAND/api"
