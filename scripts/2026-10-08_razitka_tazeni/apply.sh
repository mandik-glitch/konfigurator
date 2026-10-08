#!/usr/bin/env bash
# Aplikuje zaplaty "razitka pri tazeni se hybou s dilem" na ZIVE soubory: api/stul_razitka.py, api/stul_glb.py, api/stul_ovladani_verejne.py, webapp/js/v3d-ovladani.js (guardovane -> zamek bot8) + docs/OVLADANI_3D.md.
# Nejdriv se VSE spocita do docasneho korene a zkontroluje (kotvy sedi prave jednou, JS projde node --check, Python se prelozi), pak se zive soubory prepisou. POTOM je potreba pustit
#   api/venv/bin/python3 scripts/stul_verze.py && api/venv/bin/python3 scripts/miniweb_verze.py      (?v= hash v HTML a v stul-host.js / miniweb-pages.js / stul-embed.js)
# Pouziti: apply.sh [--jen-vypocet]      (--jen-vypocet = nic nezapise a zamek nevyzaduje)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SOUBORY="api/stul_razitka.py api/stul_glb.py api/stul_ovladani_verejne.py webapp/js/v3d-ovladani.js docs/OVLADANI_3D.md"
JEN=0; [ "${1:-}" = "--jen-vypocet" ] && JEN=1
if [ "$JEN" -eq 0 ]; then
  "$REPO/scripts/lock.sh" require bot8 >/dev/null 2>&1 || { echo "ZAMEK bot8 nemas (scripts/lock.sh acquire bot8 ...)"; exit 3; }
fi
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
for f in $SOUBORY; do mkdir -p "$T/$(dirname "$f")"; cp "$REPO/$f" "$T/$f"; done
P="$REPO/scripts/2026-10-08_razitka_tazeni/patches"
python3 "$P/patch_api.py" "$T"; python3 "$P/patch_js.py" "$T"; python3 "$P/patch_docs.py" "$T"
node --check "$T/webapp/js/v3d-ovladani.js"
for f in api/stul_razitka.py api/stul_glb.py api/stul_ovladani_verejne.py; do python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$T/$f"; done
echo "vypocet OK (kotvy sedi, JS projde node --check, Python se prelozi)"
[ "$JEN" -eq 1 ] && exit 0
for f in $SOUBORY; do cp "$T/$f" "$REPO/$f.new" && mv -f "$REPO/$f.new" "$REPO/$f"; done
echo "aplikovano: $SOUBORY (dal: scripts/stul_verze.py a scripts/miniweb_verze.py)"
