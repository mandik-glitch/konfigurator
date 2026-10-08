#!/bin/bash
# Postavi KANDIDATNI strom pro mutace / testy z ZIVEHO stromu PO commitu 2. kola (sikma police uz je v zivych souborech - zadne zaplaty se neaplikuji):
#   cand/api = symlinky na VSECHNY zive soubory api (vcetne dotfiles, napr. .env), cand/webapp = symlinky, cand/repo = koren pro testy (scripts/2026-10-07_police_stojky = TATO slozka,
#   ostatni scripts = symlinky na zive). Nic se nezapisuje do zivého stromu.
# Pouziti: bash prepare_cand_live.sh <slozka kandidata>     (pak: STUL_KANDIDAT=<slozka> api/venv/bin/python3 <slozka>/repo/scripts/2026-10-07_police_stojky/mutace_hpolice.py [id ...] [-j 3])
set -euo pipefail
CAND="${1:?slozka kandidata}"
REPO=/opt/konfigurator
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rm -rf "$CAND/api" "$CAND/webapp" "$CAND/repo" 2>/dev/null || true
mkdir -p "$CAND/api" "$CAND/webapp/katalog" "$CAND/repo/scripts"
for f in "$REPO"/api/* "$REPO"/api/.[!.]*; do [ -e "$f" ] || continue; ln -s "$f" "$CAND/api/$(basename "$f")"; done
for f in "$REPO"/webapp/*; do b="$(basename "$f")"; [ "$b" = "katalog" ] && continue; ln -s "$f" "$CAND/webapp/$b"; done
for f in "$REPO"/webapp/katalog/*; do ln -s "$f" "$CAND/webapp/katalog/$(basename "$f")"; done
for f in "$REPO"/* "$REPO"/.[!.]*; do b="$(basename "$f")"; [ -e "$f" ] || continue; case "$b" in api|webapp|scripts) continue;; esac; ln -sfn "$f" "$CAND/repo/$b"; done
ln -sfn "$CAND/api" "$CAND/repo/api"; ln -sfn "$CAND/webapp" "$CAND/repo/webapp"
for f in "$REPO"/scripts/*; do b="$(basename "$f")"; [ "$b" = "2026-10-07_police_stojky" ] && continue; ln -sfn "$f" "$CAND/repo/scripts/$b"; done
ln -sfn "$HERE" "$CAND/repo/scripts/2026-10-07_police_stojky"
for f in stul_konfigurator stul_sse stul_ovladani_verejne stul_shop stul_hpolice; do "$REPO/api/venv/bin/python3" -m py_compile "$CAND/api/$f.py"; done
echo "kandidat (zivy strom po v2) pripraven: $CAND"
