#!/usr/bin/env bash
# SVITIDLA LED RUCNE (bot8 fork 5, 2026-10-08; Robert: "svitidla se nepridavaji automaticky za sebe podle delky, jen rucne, a mohou se posouvat podel profilu"): aplikuje API cast + dokumentaci + upravy
# existujicich testu na ZIVY strom (volat uvnitr zamku bot8!). Nejdriv se VSE spocita do docasneho adresare a overi (kotvy, preklad, dokumentace, run_all.sh, zaplaty testu `patch --dry-run`);
# teprve potom se zapisuje: 6x api/*.py (stul_konfigurator, stul_shop, stul_ovladani_verejne, stul_sse, stul_glb), 3x dokumentace, run_all.sh a zaplaty existujicich testu (patches_test/*.diff).
# Selze-li kotva nebo zaplata, nezapise se NIC. Zadna nova karta ani GLB, STATICKY JS se nemeni (modul voleb a ovladani ve 3D uz umi vsechno z popisu ve schematu a odpovedi).
# Pouziti: bash apply.sh [koren_repa]   (vychozi: repo, ve kterem lezi tento skript)
set -euo pipefail
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
D="$REPO/scripts/2026-10-08_led_rucne"
P="$D/patches"
PY="$REPO/api/venv/bin/python3"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/api" "$TMP/doc/docs"
# 1) vypocet + overeni (nic se nezapisuje do repa)
for par in "patch_konfigurator.py stul_konfigurator.py" "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py"; do
  set -- $par
  "$PY" "$P/$1" "$REPO/api/$2" "$TMP/api/$2"
  "$PY" -m py_compile "$TMP/api/$2"
done
"$PY" "$P/patch_sse_glb.py" "$REPO/api/stul_sse.py" "$TMP/api/stul_sse.py" "$REPO/api/stul_glb.py" "$TMP/api/stul_glb.py"
"$PY" -m py_compile "$TMP/api/stul_sse.py" "$TMP/api/stul_glb.py"
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/OVLADANI_3D.md" "$TMP/doc/docs/"
cp "$REPO/MAPA_3D_A_GENERATORU.md" "$TMP/doc/"
"$PY" "$P/patch_docs.py" "$TMP/doc"
"$PY" "$D/patches_test/patch_run_all.py" "$REPO/scripts/2026-10-02_stul_testy/run_all.sh" "$TMP/run_all.sh"
bash -n "$TMP/run_all.sh"
for z in "$D"/patches_test/*.diff; do patch --dry-run -s -p1 -d "$REPO/scripts" < "$z"; done
for t in test_led_rucne test_led_rucne_shop test_regrese_bez_rucnich_led mutace golden_head _spolecne run_regrese; do "$PY" -m py_compile "$D/$t.py"; done
node --check "$D/test_led_rucne_stranka.js"
# 2) zapis (az po uspesnem overeni vseho)
for f in stul_konfigurator stul_shop stul_ovladani_verejne stul_sse stul_glb; do cp "$TMP/api/$f.py" "$REPO/api/$f.py"; done
cp "$TMP/doc/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/doc/docs/OVLADANI_3D.md" "$REPO/docs/"
cp "$TMP/doc/MAPA_3D_A_GENERATORU.md" "$REPO/MAPA_3D_A_GENERATORU.md"
cp "$TMP/run_all.sh" "$REPO/scripts/2026-10-02_stul_testy/run_all.sh"
for z in "$D"/patches_test/*.diff; do patch -s -p1 -d "$REPO/scripts" < "$z"; done
"$PY" -m py_compile "$REPO"/api/stul_konfigurator.py "$REPO"/api/stul_shop.py "$REPO"/api/stul_ovladani_verejne.py "$REPO"/api/stul_sse.py "$REPO"/api/stul_glb.py
echo "HOTOVO: api/{stul_konfigurator,stul_shop,stul_ovladani_verejne,stul_sse,stul_glb}.py, docs/{KONTRAKT_KONFIGURATOR_UI,OVLADANI_3D}.md, MAPA_3D_A_GENERATORU.md, scripts/2026-10-02_stul_testy/run_all.sh + upravene testy (patches_test/*.diff)."
echo "Dale: test_led_rucne.py (hermeticky), test_led_rucne_shop.py (systemd-run, DB jen cte), test_led_rucne_stranka.js (most), upravene testy (README.md), commit (pathspec viz README.md), reload API planovanou sluzbou / Robertovym prikazem."
