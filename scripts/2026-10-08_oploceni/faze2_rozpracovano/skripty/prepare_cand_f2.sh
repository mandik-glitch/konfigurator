#!/bin/bash
# Postavi KANDIDATNI strom FAZE 2 generatoru oploceni z ZIVEHO stromu; nic nezapisuje do zivého stromu:
#   <cand>/api    = symlinky na zive soubory, krome 4 zaplatovanych (apply_patches_f2.py) a 4 novych modulu oploceni_*.py;
#   <cand>/webapp = symlinky na zive soubory + NOVE soubory stranky (novy_webapp/: oploceni-konfigurator.html, js/oploceni-host.js; slozky, do kterych pribyva soubor, jsou skutecne s symlinky uvnitr);
#   <cand>/repo   = koren pro testy (scripts/2026-10-08_oploceni = TATO slozka, ostatni scripts = symlinky na zive; api/webapp = kandidat).
# Pouziti: bash prepare_cand_f2.sh <slozka kandidata>        (testy se pousti z <cand>/repo; viz README_FAZE2.md)
set -euo pipefail
CAND="${1:?slozka kandidata}"
REPO=/opt/konfigurator
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$REPO/api/venv/bin/python3"
rm -rf "$CAND/api" "$CAND/webapp" "$CAND/repo" 2>/dev/null || true
mkdir -p "$CAND/api" "$CAND/webapp" "$CAND/repo/scripts"
for f in "$REPO"/api/*; do [ "$(basename "$f")" = "__pycache__" ] && continue; ln -s "$f" "$CAND/api/$(basename "$f")"; done      # NE __pycache__: py_compile by pres symlink psal bytecode do ZIVEHO api/__pycache__
for f in "$REPO"/webapp/*; do ln -s "$f" "$CAND/webapp/$(basename "$f")"; done
# nove soubory webapp: kazda slozka na ceste se zmeni na skutecnou (s symlinky na zive polozky) a soubor se zkopiruje
( cd "$HERE/novy_webapp" && find . -type f | sed 's#^\./##' ) | while read -r rel; do
  d="$(dirname "$rel")"; cur="$CAND/webapp"; zive="$REPO/webapp"
  if [ "$d" != "." ]; then
    IFS='/' read -ra casti <<< "$d"
    for c in "${casti[@]}"; do
      if [ -L "$cur/$c" ]; then rm "$cur/$c"; mkdir "$cur/$c"; for g in "$zive/$c"/*; do ln -s "$g" "$cur/$c/$(basename "$g")"; done; fi
      cur="$cur/$c"; zive="$zive/$c"
    done
  fi
  [ -L "$CAND/webapp/$rel" ] && rm "$CAND/webapp/$rel"
  cp "$HERE/novy_webapp/$rel" "$CAND/webapp/$rel"
done
"$PY" "$HERE/apply_patches_f2.py" "$REPO/api" "$CAND/api"
for f in "$REPO"/* "$REPO"/.[!.]*; do b="$(basename "$f")"; [ -e "$f" ] || continue; case "$b" in api|webapp|scripts) continue;; esac; ln -sfn "$f" "$CAND/repo/$b"; done
ln -sfn "$CAND/api" "$CAND/repo/api"; ln -sfn "$CAND/webapp" "$CAND/repo/webapp"
for f in "$REPO"/scripts/*; do b="$(basename "$f")"; [ "$b" = "2026-10-08_oploceni" ] && continue; ln -sfn "$f" "$CAND/repo/scripts/$b"; done
ln -sfn "$HERE" "$CAND/repo/scripts/2026-10-08_oploceni"
for f in konfigurator_registr stul_shop konfigurace_kosik nabidka_z_konfigurace oploceni_konfigurator oploceni_glb oploceni_cena oploceni_shop; do "$PY" -m py_compile "$CAND/api/$f.py"; done
echo "kandidat faze 2 pripraven: $CAND"
