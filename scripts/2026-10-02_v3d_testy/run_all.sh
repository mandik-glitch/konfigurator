#!/bin/bash
# Vsechny testy 3D nabidky z Vandr karty (2026-10-02). Nic nenasazuje, nepise do repa ani do DB (DB je vzdy atrapa).
#   scripts/2026-10-02_v3d_testy/run_all.sh [--full] [--rychle]
#   --full    test_mark.py v plnem rozsahu (node + Blender + registrace s originalem; 6-10 min navic)
#   --rychle  bez stavby 7 karet, bez testu, ktere ji potrebuji (test_sanitize TestVandrOut, test_mark), a bez harness_page.js (prohlizec, ~3 min)
# Prostredi: PY (vychozi /opt/konfigurator/api/venv/bin/python), V3D_TEST_OUT (vystupy mimo repo, vychozi <tmp>/v3d_testy),
#            V3D_TEST_KATALOG (jen cteni, vychozi <repo>/webapp/katalog), V3D_ZAKAZANA_SLOVA (staticka kontrola).
# Potrebuje: Blender /opt/blender-5.2/blender (jen -b, CPU), node (three r128 z /opt/konfigurator/node_modules).
# Mimo run_all (potrebuje DB prihlaseni pres systemd, docasne tabulky): test_spolecna_nabidka_admin.py - systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root
#   --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_v3d_testy/test_spolecna_nabidka_admin.py
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-/opt/konfigurator/api/venv/bin/python}"
export V3D_TEST_OUT="${V3D_TEST_OUT:-${TMPDIR:-/tmp}/v3d_testy}"
export PYTHONDONTWRITEBYTECODE=1
FULL=0; RYCHLE=0
for a in "$@"; do case "$a" in --full) FULL=1;; --rychle) RYCHLE=1;; esac; done
mkdir -p "$V3D_TEST_OUT"
declare -a JMENA RC
beh() { local nazev="$1"; shift; echo; echo "=== $nazev"; "$@"; local rc=$?; JMENA+=("$nazev"); RC+=("$rc"); }
cd "$HERE" || exit 2
if [ "$RYCHLE" = 0 ]; then beh "build 7 karet (Blender, CPU)" "$PY" build_karty.py; fi
beh "test_sanitize" "$PY" test_sanitize.py
beh "test_motions_sub" "$PY" test_motions_sub.py
beh "_mutace (sanitizer)" "$PY" _mutace.py
if [ "$RYCHLE" = 0 ]; then
  if [ "$FULL" = 1 ]; then beh "test_mark (plny)" "$PY" test_mark.py; else beh "test_mark (MARK_FAST=1)" env MARK_FAST=1 "$PY" test_mark.py; fi
fi
beh "test_vykres (nahradni obrazky)" "$PY" test_vykres.py
beh "test_import" "$PY" test_import.py
beh "test_endpoint" "$PY" test_endpoint.py
beh "_mutace_endpoint" "$PY" _mutace_endpoint.py
beh "test_kontrola_route (kontrolni scena, 2026-10-06)" "$PY" test_kontrola_route.py
if [ "$RYCHLE" = 0 ]; then beh "test_spolecna_nabidka (leva+prava+prepazka v 1 nabidce, Blender, 2026-10-06)" "$PY" test_spolecna_nabidka.py; fi
if [ "$RYCHLE" = 0 ]; then beh "_mutace_kontrola_route" "$PY" _mutace_kontrola_route.py; fi
if [ "$RYCHLE" = 0 ]; then beh "test_kontrola_nabidka_auto (prohlizec, ~1 min)" node test_kontrola_nabidka_auto.js; fi
beh "kontrola_staticka" "$PY" kontrola_staticka.py
if [ "$RYCHLE" = 0 ]; then beh "harness_page (prohlizec, ~3 min)" node harness_page.js; fi
echo; echo "=================== SOUHRN"
SELHALO=0
for i in "${!JMENA[@]}"; do
  if [ "${RC[$i]}" = 0 ]; then s=OK; else s="SELHALO (rc=${RC[$i]})"; SELHALO=1; fi
  printf '%-32s %s\n' "${JMENA[$i]}" "$s"
done
exit $SELHALO
