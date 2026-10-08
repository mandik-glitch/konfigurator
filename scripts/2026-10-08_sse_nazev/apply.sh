#!/usr/bin/env bash
# Aplikuje zaplatu SSE nazvu (patches/patch_sse_nazev.py) na ZIVE soubory: webapp/* a api/stul_vyrobni_list.py jsou guardovane -> vyzaduje zamek bot8 (scripts/lock.sh require bot8).
# Nejdriv se VSE spocita do docasneho korene a zkontroluje (kotvy sedi prave jednou, JS projde `node --check`, Python se prelozi), teprve potom se zive soubory prepisou.
# Pouziti: apply.sh [--jen-vypocet]      (--jen-vypocet = nic nezapise a zamek nevyzaduje)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SOUBORY="webapp/stul-konfigurator-41.html webapp/js/stul-host.js webapp/js/stul-karta.js webapp/js/stul-nabidka.js webapp/js/scene/stul-konfigurator.js api/stul_vyrobni_list.py MAPA_3D_A_GENERATORU.md docs/KONTRAKT_KONFIGURATOR_UI.md docs/OVLADANI_3D.md"
JEN=0; [ "${1:-}" = "--jen-vypocet" ] && JEN=1
if [ "$JEN" -eq 0 ]; then
  "$REPO/scripts/lock.sh" require bot8 >/dev/null 2>&1 || { echo "ZAMEK bot8 nemas (scripts/lock.sh acquire bot8 ...)"; exit 3; }
fi
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
for f in $SOUBORY; do mkdir -p "$T/$(dirname "$f")"; cp "$REPO/$f" "$T/$f"; done
python3 "$REPO/scripts/2026-10-08_sse_nazev/patches/patch_sse_nazev.py" "$T"
for f in webapp/js/stul-host.js webapp/js/stul-karta.js webapp/js/stul-nabidka.js webapp/js/scene/stul-konfigurator.js; do node --check "$T/$f"; done
python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$T/api/stul_vyrobni_list.py"
echo "vypocet OK (kotvy sedi, JS projde node --check, Python se prelozi)"
[ "$JEN" -eq 1 ] && exit 0
for f in $SOUBORY; do cp "$T/$f" "$REPO/$f.new" && mv -f "$REPO/$f.new" "$REPO/$f"; done
echo "aplikovano: $SOUBORY"
