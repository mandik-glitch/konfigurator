#!/usr/bin/env bash
# Aplikuje VSECHNY zaplaty 'spodni police bez desky' na ZIVY strom (volat uvnitr zamku bot8!). Nejdriv se VSE spocita do docasneho adresare a overi (kotvy, preklad) - teprve potom se zapisuje:
# 7x api/*.py, 1x existujici test (scripts/2026-10-02_stul_testy/test_stul_shop.py) a 2x docs. Selze-li kotva (nekdo mezitim upravil stejne misto), nezapise se NIC.
# Pouziti: apply.sh [koren_repa]   (vychozi: repo, ve kterem lezi tento skript)
set -euo pipefail
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
P="$REPO/scripts/2026-10-07_police_bez_desky/patches"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SOUBORY=("patch_konfigurator.py stul_konfigurator.py" "patch_glb.py stul_glb.py" "patch_sse.py stul_sse.py" "patch_koty.py stul_koty.py" "patch_vyrobni_list.py stul_vyrobni_list.py"
         "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py")
TEST="scripts/2026-10-02_stul_testy/test_stul_shop.py"
# 1) vypocet + overeni (nic se nezapisuje do repa)
for par in "${SOUBORY[@]}"; do
  set -- $par
  python3 "$P/$1" "$REPO/api/$2" "$TMP/$2"
  python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$TMP/$2"
done
python3 "$P/patch_test_stul_shop.py" "$REPO/$TEST" "$TMP/test_stul_shop.py"          # existujici test: volba shelfboard bez polic cenu nemeni
python3 -c "import sys; compile(open(sys.argv[1], encoding='utf-8').read(), sys.argv[1], 'exec')" "$TMP/test_stul_shop.py"
mkdir -p "$TMP/docroot/docs"
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/OVLADANI_3D.md" "$TMP/docroot/docs/"
python3 "$P/patch_docs.py" "$TMP/docroot"                                           # overeni kotev dokumentace na kopii
# 2) zapis (az po uspesnem overeni vseho)
for par in "${SOUBORY[@]}"; do
  set -- $par
  cp "$TMP/$2" "$REPO/api/$2"
done
cp "$TMP/test_stul_shop.py" "$REPO/$TEST"
cp "$TMP/docroot/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/docroot/docs/OVLADANI_3D.md" "$REPO/docs/"
python3 -m py_compile "$REPO"/api/stul_konfigurator.py "$REPO"/api/stul_glb.py "$REPO"/api/stul_sse.py "$REPO"/api/stul_koty.py "$REPO"/api/stul_vyrobni_list.py "$REPO"/api/stul_shop.py "$REPO"/api/stul_ovladani_verejne.py
echo "zaplaty aplikovany: 7x api/*.py (stul_konfigurator stul_glb stul_sse stul_koty stul_vyrobni_list stul_shop stul_ovladani_verejne), $TEST, docs/KONTRAKT_KONFIGURATOR_UI.md, docs/OVLADANI_3D.md"
