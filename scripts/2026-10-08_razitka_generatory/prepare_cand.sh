#!/usr/bin/env bash
# Postavi KANDIDATNI strom ($1, vychozi $SP/razitka/cand): api/* = symlinky na zive soubory, jen upravovane soubory jsou kopie vzniklé aplikaci zaplat (patches/*.py) na ZIVY soubor;
# `webapp` a `scripts` = symlinky na zive (testy z kandidatniho korene tak pouziji kandidatni api/). Symlink webapp se vytvari PRED jakymkoli importem (import app bez nej vyrobi skutecny adresar webapp/).
# Pouziti: prepare_cand.sh [adresar]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CAND="${1:-${SP:?nastav SP nebo zadej adresar}/razitka/cand}"
rm -rf "$CAND"; mkdir -p "$CAND/api"
ln -sfn "$REPO/webapp" "$CAND/webapp"
ln -sfn "$REPO/scripts" "$CAND/scripts"
mkdir -p "$CAND/api/__pycache__"          # LOKALNI bajtkod: symlink na zivy api/__pycache__ by do nej zapisoval pyc kandidatnich souboru
for f in "$REPO"/api/*; do b="$(basename "$f")"; case "$b" in __pycache__|tmp_*) continue;; esac; ln -sfn "$f" "$CAND/api/$b"; done
P="$REPO/scripts/2026-10-08_razitka_generatory/patches"
for par in "patch_glb.py stul_glb.py" "patch_razitka_doc.py stul_razitka.py"; do
  set -- $par
  python3 "$P/$1" "$REPO/api/$2" "$CAND/api/$2.new"          # atomicky: nejdriv do .new, pak mv (nahradi i symlink)
  python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$CAND/api/$2.new"
  mv -f "$CAND/api/$2.new" "$CAND/api/$2"
done
echo "kandidat pripraven: $CAND/api"
