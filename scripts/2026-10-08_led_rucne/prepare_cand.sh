#!/usr/bin/env bash
# Postavi KANDIDATNI strom ($1, vychozi $SP/led_rucne/cand): api/* = symlinky na zive soubory, jen upravovane soubory jsou kopie vzniklé aplikaci zaplat (patches/*.py) na ZIVY soubor.
# Symlink webapp se vytvari PRED jakymkoli importem (import app bez nej vyrobi skutecny adresar webapp/); symlink scripts, aby testy z kandidata nasly sve skripty.
# Pouziti: prepare_cand.sh [adresar]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CAND="${1:-${SP:?nastav SP nebo zadej adresar}/led_rucne/cand}"
mkdir -p "$CAND/api"
ln -sfn "$REPO/webapp" "$CAND/webapp"
# scripts: kandidatni strom ma vlastni adresare testu (symlinky na soubory repa); upravene existujici testy jsou KOPIE s aplikovanou zaplatou patches_test/*.diff (cesty ve zaplatach: a/<adresar>/<soubor> vuci scripts/)
rm -rf "$CAND/scripts"
mkdir -p "$CAND/scripts"
for d in "$REPO"/scripts/*; do ln -sfn "$d" "$CAND/scripts/$(basename "$d")"; done
DIFFY=("$REPO"/scripts/2026-10-08_led_rucne/patches_test/*.diff)
if [ -e "${DIFFY[0]}" ]; then
  for z in "${DIFFY[@]}"; do
    for f in $(grep -E '^\+\+\+ b/' "$z" | sed 's#^+++ b/##; s#\t.*##'); do
      dir="${f%%/*}"
      if [ -L "$CAND/scripts/$dir" ]; then
        rm "$CAND/scripts/$dir"
        mkdir "$CAND/scripts/$dir"
        for g in "$REPO/scripts/$dir"/*; do ln -sfn "$g" "$CAND/scripts/$dir/$(basename "$g")"; done
      fi
      if [ -L "$CAND/scripts/$f" ]; then
        cp --remove-destination "$(readlink -f "$CAND/scripts/$f")" "$CAND/scripts/$f"
      fi
    done
    patch -s -p1 -d "$CAND/scripts" < "$z"
  done
fi
for f in "$REPO"/api/*; do ln -sfn "$f" "$CAND/api/$(basename "$f")"; done
P="$REPO/scripts/2026-10-08_led_rucne/patches"
for par in "patch_konfigurator.py stul_konfigurator.py" "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py"; do
  set -- $par
  rm -f "$CAND/api/$2"
  python3 "$P/$1" "$REPO/api/$2" "$CAND/api/$2"
  python3 -m py_compile "$CAND/api/$2"
done
rm -f "$CAND/api/stul_sse.py" "$CAND/api/stul_glb.py"
python3 "$P/patch_sse_glb.py" "$REPO/api/stul_sse.py" "$CAND/api/stul_sse.py" "$REPO/api/stul_glb.py" "$CAND/api/stul_glb.py"
python3 -m py_compile "$CAND/api/stul_sse.py" "$CAND/api/stul_glb.py"
echo "kandidat pripraven: $CAND/api"
