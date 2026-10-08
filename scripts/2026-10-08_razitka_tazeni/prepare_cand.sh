#!/usr/bin/env bash
# Postavi KANDIDATNI strom ($1, vychozi $SP/tazeni/cand): api/* = symlinky na zive soubory, jen 3 soubory (stul_razitka.py, stul_glb.py, stul_ovladani_verejne.py) jsou kopie s aplikovanou zaplatou patches/patch_api.py;
# webapp/ = adresar symlinku na zive polozky, js/ taky adresar symlinku a jen js/v3d-ovladani.js je kopie se zaplatou patches/patch_js.py; scripts = symlink na zive. Prohlizecove testy (_most_stul.py spusteny z
# $CAND/scripts/...) tak obslouzi kandidatni JS a API bez zamku a bez zasahu do zive stranky.   Pouziti: prepare_cand.sh [adresar]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CAND="${1:-${SP:?nastav SP nebo zadej adresar}/tazeni/cand}"
rm -rf "$CAND"; mkdir -p "$CAND/api" "$CAND/webapp/js"
ln -sfn "$REPO/scripts" "$CAND/scripts"
for f in "$REPO"/webapp/*; do b="$(basename "$f")"; [ "$b" = "js" ] && continue; ln -sfn "$f" "$CAND/webapp/$b"; done
for f in "$REPO"/webapp/js/*; do b="$(basename "$f")"; [ "$b" = "v3d-ovladani.js" ] && continue; ln -sfn "$f" "$CAND/webapp/js/$b"; done
cp "$REPO/webapp/js/v3d-ovladani.js" "$CAND/webapp/js/v3d-ovladani.js"
mkdir -p "$CAND/api/__pycache__"          # LOKALNI bajtkod: symlink na zivy api/__pycache__ by do nej zapisoval pyc kandidatnich souboru
for f in "$REPO"/api/*; do b="$(basename "$f")"; case "$b" in __pycache__|tmp_*) continue;; esac; ln -sfn "$f" "$CAND/api/$b"; done
for b in stul_razitka.py stul_glb.py stul_ovladani_verejne.py; do rm -f "$CAND/api/$b"; cp "$REPO/api/$b" "$CAND/api/$b"; done
python3 "$REPO/scripts/2026-10-08_razitka_tazeni/patches/patch_api.py" "$CAND"
python3 "$REPO/scripts/2026-10-08_razitka_tazeni/patches/patch_js.py" "$CAND"
for b in stul_razitka.py stul_glb.py stul_ovladani_verejne.py; do python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$CAND/api/$b"; done
node --check "$CAND/webapp/js/v3d-ovladani.js"
echo "kandidat pripraven: $CAND (api + webapp/js/v3d-ovladani.js)"
