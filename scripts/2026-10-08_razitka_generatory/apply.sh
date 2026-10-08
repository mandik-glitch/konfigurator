#!/usr/bin/env bash
# Aplikuje zaplaty razitek (WORKFLOW pravidlo 61) na ZIVE soubory: api/stul_glb.py, api/stul_razitka.py (guardovane - vyzaduje zamek bot8) + 3 dokumenty (patches/patch_docs.py).
# Nejdriv se VSE spocita do docasneho adresare a zkontroluje (kotvy sedi prave jednou, soubory se prelozi), teprve potom se zive soubory atomicky prepisou (.new -> mv).
# Pouziti: apply.sh [--jen-vypocet]      (--jen-vypocet = nic nezapise a zamek nevyzaduje)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
P="$REPO/scripts/2026-10-08_razitka_generatory/patches"
JEN=0; [ "${1:-}" = "--jen-vypocet" ] && JEN=1
if [ "$JEN" -eq 0 ]; then
  "$REPO/scripts/lock.sh" require bot8 >/dev/null 2>&1 || { echo "ZAMEK bot8 nemas (scripts/lock.sh acquire bot8 ...)"; exit 3; }
fi
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
python3 "$P/patch_glb.py" "$REPO/api/stul_glb.py" "$T/stul_glb.py"
python3 "$P/patch_razitka_doc.py" "$REPO/api/stul_razitka.py" "$T/stul_razitka.py"
for f in "$T/stul_glb.py" "$T/stul_razitka.py"; do
  python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$f"
done
mkdir -p "$T/koren/docs"
cp "$REPO/MAPA_3D_A_GENERATORU.md" "$T/koren/"
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/STUL_ZASLEPKY_A_RAZITKA.md" "$T/koren/docs/"
python3 "$P/patch_docs.py" "$T/koren"
echo "vypocet OK (kotvy sedi, soubory se prelozi)"
[ "$JEN" -eq 1 ] && exit 0
cp "$T/stul_glb.py" "$REPO/api/stul_glb.py.new" && mv -f "$REPO/api/stul_glb.py.new" "$REPO/api/stul_glb.py"
cp "$T/stul_razitka.py" "$REPO/api/stul_razitka.py.new" && mv -f "$REPO/api/stul_razitka.py.new" "$REPO/api/stul_razitka.py"
cp "$T/koren/MAPA_3D_A_GENERATORU.md" "$REPO/MAPA_3D_A_GENERATORU.md"
cp "$T/koren/docs/KONTRAKT_KONFIGURATOR_UI.md" "$T/koren/docs/STUL_ZASLEPKY_A_RAZITKA.md" "$REPO/docs/"
echo "aplikovano: api/stul_glb.py, api/stul_razitka.py, MAPA_3D_A_GENERATORU.md, docs/KONTRAKT_KONFIGURATOR_UI.md, docs/STUL_ZASLEPKY_A_RAZITKA.md"
