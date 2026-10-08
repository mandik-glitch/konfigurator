#!/bin/bash
# Postavi KANDIDATNI strom 2. kola (sikma police) z ZIVEHO stromu (v1 uz aplikovana); nic nezapisuje do zivého stromu:
#   cand/api = symlinky na zive soubory, krome 4 zaplatovanych (apply_patches_v2.py) a modulu stul_hpolice.py (v2); cand/webapp = symlinky (vcetne katalogu);
#   cand/repo = koren pro testy (scripts/2026-10-07_police_stojky = TATO slozka, ostatni scripts = symlinky na zive).
# Pouziti: bash prepare_cand_v2.sh <slozka kandidata>
set -euo pipefail
CAND="${1:?slozka kandidata}"
REPO=/opt/konfigurator
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rm -rf "$CAND/api" "$CAND/webapp" "$CAND/repo" 2>/dev/null || true
mkdir -p "$CAND/api" "$CAND/webapp/katalog" "$CAND/repo/scripts"
for f in "$REPO"/api/*; do ln -s "$f" "$CAND/api/$(basename "$f")"; done
for f in "$REPO"/webapp/*; do b="$(basename "$f")"; [ "$b" = "katalog" ] && continue; ln -s "$f" "$CAND/webapp/$b"; done
for f in "$REPO"/webapp/katalog/*; do ln -s "$f" "$CAND/webapp/katalog/$(basename "$f")"; done
"$REPO/api/venv/bin/python3" "$HERE/apply_patches_v2.py" "$REPO/api" "$CAND/api"
for f in "$REPO"/* "$REPO"/.[!.]*; do b="$(basename "$f")"; [ -e "$f" ] || continue; case "$b" in api|webapp|scripts) continue;; esac; ln -sfn "$f" "$CAND/repo/$b"; done
ln -sfn "$CAND/api" "$CAND/repo/api"; ln -sfn "$CAND/webapp" "$CAND/repo/webapp"
for f in "$REPO"/scripts/*; do b="$(basename "$f")"; [ "$b" = "2026-10-07_police_stojky" ] && continue; ln -sfn "$f" "$CAND/repo/scripts/$b"; done
ln -sfn "$HERE" "$CAND/repo/scripts/2026-10-07_police_stojky"
for f in stul_konfigurator stul_sse stul_ovladani_verejne stul_shop stul_hpolice; do "$REPO/api/venv/bin/python3" -m py_compile "$CAND/api/$f.py"; done
echo "kandidat v2 pripraven: $CAND"
