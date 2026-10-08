#!/bin/bash
# Testy vzhledu online nabidek (HDRI, hlinik, AO; bot10, 2026-10-06; docs/KONTRAKT_NABIDKA_3D.md 5f). Nic nenasazuje, nepise do repa ani do DB (DB je atrapa).
#   scripts/2026-10-06_v3d_vzhled_testy/run_all.sh [--rychle]      --rychle = jen API (bez prohlizece a mutaci)
# Kandidati pred nasazenim: KONTROLA_HTML=<kontrola.html> V3D_PAGE_HTML=<nabidka-online.html> V3D_VZHLED_MODUL=<v3d_vzhled.py>
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-/opt/konfigurator/api/venv/bin/python}"
RYCHLE=0; [ "$1" = "--rychle" ] && RYCHLE=1
declare -a JMENA RC
beh() { local nazev="$1"; shift; echo; echo "=== $nazev"; "$@"; local rc=$?; JMENA+=("$nazev"); RC+=("$rc"); }
cd "$HERE" || exit 2
beh "test_vzhled_api (20)" "$PY" -B test_vzhled_api.py
if [ "$RYCHLE" = 0 ]; then
  beh "_mutace_vzhled (12 mutaci)" "$PY" -B _mutace_vzhled.py
  beh "test_kontrola_vzhled.js (24, prohlizec)" node test_kontrola_vzhled.js
  beh "harness_page.js scenar 9 (stranka nabidky)" env H_ONLY=9 node ../2026-10-02_v3d_testy/harness_page.js
fi
echo; echo "=================== SOUHRN"
SELHALO=0
for i in "${!JMENA[@]}"; do
  if [ "${RC[$i]}" = 0 ]; then s=OK; else s="SELHALO (rc=${RC[$i]})"; SELHALO=1; fi
  printf '%-48s %s\n' "${JMENA[$i]}" "$s"
done
exit $SELHALO
