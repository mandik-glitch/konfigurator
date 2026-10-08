#!/bin/bash
# Postavi KANDIDATNI strom pro horni police (nic nezapisuje do zivého stromu): cand/api = symlinky na zive soubory, krome souboru upravenych zaplatami (apply_patches.py) a noveho modulu;
# cand/webapp = symlinky na zive polozky + vlastni katalog (symlinky + GLB desky 12 mm pro testy: nova karta zatim neexistuje).
# Pouziti: bash scripts/2026-10-07_police_stojky/prepare_cand.sh <slozka kandidata> [lam12_id]
set -euo pipefail
CAND="${1:?slozka kandidata}"; LAM12_ID="${2:-5360}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$REPO/scripts/2026-10-07_police_stojky"
rm -rf "$CAND/api" "$CAND/webapp" 2>/dev/null || true
mkdir -p "$CAND/api" "$CAND/webapp/katalog"
for f in "$REPO"/api/*; do ln -s "$f" "$CAND/api/$(basename "$f")"; done
for f in "$REPO"/webapp/*; do b="$(basename "$f")"; [ "$b" = "katalog" ] && continue; ln -s "$f" "$CAND/webapp/$b"; done
for f in "$REPO"/webapp/katalog/*; do ln -s "$f" "$CAND/webapp/katalog/$(basename "$f")"; done
"$REPO/api/venv/bin/python3" "$HERE/apply_patches.py" "$REPO/api" "$CAND/api" --lam12-id "$LAM12_ID"
"$REPO/api/venv/bin/python3" "$HERE/glb_lam12.py" "$CAND/webapp/katalog/product_${LAM12_ID}.glb"
# "repo" kandidata: symlinky na vsechny polozky korene repa krome api a webapp (ty jsou kandidatni) - testy pouzivaji REPO z cesty sveho souboru, takze bezi nad kandidatem
mkdir -p "$CAND/repo"
for f in "$REPO"/* "$REPO"/.[!.]*; do b="$(basename "$f")"; [ -e "$f" ] || continue; case "$b" in api|webapp) continue;; esac; ln -sfn "$f" "$CAND/repo/$b"; done
ln -sfn "$CAND/api" "$CAND/repo/api"; ln -sfn "$CAND/webapp" "$CAND/repo/webapp"
for f in stul_konfigurator stul_glb stul_sse stul_ovladani_verejne stul_hpolice stul_shop; do "$REPO/api/venv/bin/python3" -m py_compile "$CAND/api/$f.py"; done
echo "kandidat pripraven: $CAND (deska 12 mm = product_${LAM12_ID})"
