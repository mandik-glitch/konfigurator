#!/bin/bash
# Vsechny testy PRICEK DO MULTIBOXU v online nabidce (bot8, 2026-10-07). Nic nenasazuje, nepise do repa ani do ostre DB (DB testy jen nad docasnymi tabulkami).
#   scripts/2026-10-07_multibox_pricky/run_all.sh [--rychle] [--mutace] [--kandidat <slozka api>]
#   --rychle    bez stavby 3 karet v Blenderu (pouzije se uz hotovy <OUT>/out, out2), bez prohlizecovych testu
#   --mutace    navic mutacni kontroly (mutace_pricky.py, ~10 min; plugin a stranka maji vlastni mutace v mutace_*.py)
#   --kandidat  slozka s kandidaty nabidka_pricky.py, scene_offers.py, orders.py, v3d_glb.py, v3d_merge.py (vychozi: zive api/)
# Prostredi: PY (vychozi /opt/konfigurator/api/venv/bin/python), V3D_TEST_OUT (vystupy mimo repo, vychozi <tmp>/v3d_testy), V3D_TEST_REPO (kandidatni strom pro build).
# Potrebuje: Blender /opt/blender-5.2/blender (jen -b, CPU), node + Playwright (/opt/konfigurator/node_modules).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PY="${PY:-/opt/konfigurator/api/venv/bin/python}"
export V3D_TEST_OUT="${V3D_TEST_OUT:-${TMPDIR:-/tmp}/v3d_testy}"
export PYTHONDONTWRITEBYTECODE=1
RYCHLE=0; MUTACE=0; API="$REPO/api"
while [ $# -gt 0 ]; do case "$1" in --rychle) RYCHLE=1;; --mutace) MUTACE=1;; --kandidat) shift; API="$1";; esac; shift; done
mkdir -p "$V3D_TEST_OUT"
declare -a JMENA RC
beh() { local nazev="$1"; shift; echo; echo "=== $nazev"; "$@"; local rc=$?; JMENA+=("$nazev"); RC+=("$rc"); }
DBRUN() { systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRICKY_CAND="$API" --setenv=PRICKY_FIX="$V3D_TEST_OUT/out2" \
          --setenv=V3D_TEST_OUT="$V3D_TEST_OUT" --working-directory=/opt/konfigurator "$PY" "$@"; }
cd "$HERE" || exit 2
if [ "$RYCHLE" = 0 ]; then beh "build karet 4453 4474 4594 4910 4917 4918 4921 4968 (Blender, CPU)" env FORCE=1 "$PY" "$REPO/scripts/2026-10-02_v3d_testy/build_karty.py" 4453 4474 4594 4910 4917 4918 4921 4968; fi
beh "test_pricky (cista logika: typ boxu, sloty 4/6/8, sety, ceny, vyber)" "$PY" test_pricky.py "$API"
beh "test_spec_mbx (validace mbx ve spec, sanitize, final_check)" "$PY" test_spec_mbx.py "$API" "$V3D_TEST_OUT/out2"
beh "test_merge_mbx (slouceni vice karet)" "$PY" test_merge_mbx.py "$API" "$V3D_TEST_OUT/out2"
beh "test_build_mbx (Blender build: skupiny, konec s vykrojem, pivoty)" env PRICKY_API="$API" "$PY" test_build_mbx.py
beh "test_pricky_backend (verejny JSON, QR, prijeti, objednavka; docasne tabulky)" DBRUN "$HERE/test_pricky_backend.py"
if [ "$RYCHLE" = 0 ]; then
  [ -f test_plugin.js ] && beh "test_plugin (prohlizec: 3D priccky, pohyb, wire, dispose)" env PRICKY_API="$API" V3D_TEST_OUT="$V3D_TEST_OUT" node test_plugin.js
  [ -f test_page.js ] && beh "test_page (prohlizec: nabidka-online.html, sety, ceny, QR, objednani)" env PRICKY_API="$API" V3D_TEST_OUT="$V3D_TEST_OUT" node test_page.js
  [ -f test_page_real.js ] && beh "test_page_real (skutecny viewer + plugin: vysunuti boxu, zvyrazneni)" env PRICKY_API="$API" V3D_TEST_OUT="$V3D_TEST_OUT" node test_page_real.js
fi
if [ "$MUTACE" = 1 ]; then beh "mutace_pricky (backend, spec, merge, modul)" env KANDIDAT="$API" FIX="$V3D_TEST_OUT/out2" "$PY" mutace_pricky.py; fi
echo; echo "=================== SOUHRN"
SELHALO=0
for i in "${!JMENA[@]}"; do
  if [ "${RC[$i]}" = 0 ]; then s=OK; else s="SELHALO (rc=${RC[$i]})"; SELHALO=1; fi
  printf '%-70s %s\n' "${JMENA[$i]}" "$s"
done
exit $SELHALO
