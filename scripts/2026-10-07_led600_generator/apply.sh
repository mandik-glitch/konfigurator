#!/usr/bin/env bash
# Aplikuje API cast + dokumentaci + upravu existujiciho testu 'LED 600 do generatoru' na ZIVY strom (volat uvnitr zamku bot8!). Nejdriv se vsechno vyrobi do docasneho adresare (kotvy se overi, preklad,
# docs se vyzkousi na kopiich), teprve pak se zive soubory vymeni (zadna zaplata se neaplikuje napul). STATICKE JS (pocitadlo luxu) se aplikuje SAMOSTATNE: apply_js.sh (zapisuje se okamzite zive + piny ?v=).
# Pouziti: apply.sh [koren_repa]   (vychozi: repo, ve kterem lezi tento skript)
set -euo pipefail
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
D="$REPO/scripts/2026-10-07_led600_generator"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SOUBORY=("patch_konfigurator.py stul_konfigurator.py" "patch_glb.py stul_glb.py" "patch_sse.py stul_sse.py" "patch_osvetleni.py stul_osvetleni.py"
         "patch_shop.py stul_shop.py" "patch_ovladani_verejne.py stul_ovladani_verejne.py")
for par in "${SOUBORY[@]}"; do
  set -- $par
  python3 "$D/patches/$1" "$REPO/api/$2" "$TMP/$2"
  python3 -m py_compile "$TMP/$2"
done
python3 "$D/patches_test/patch_test_shop.py" "$REPO/scripts/2026-10-02_stul_testy/test_stul_shop.py" "$TMP/test_stul_shop.py"
python3 -m py_compile "$TMP/test_stul_shop.py"
python3 "$D/patches_test/patch_run_all.py" "$REPO/scripts/2026-10-02_stul_testy/run_all.sh" "$TMP/run_all.sh"
bash -n "$TMP/run_all.sh"
mkdir -p "$TMP/kopie/docs"
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/kopie/docs/"
cp "$REPO/MAPA_3D_A_GENERATORU.md" "$TMP/kopie/"
python3 "$D/patches/patch_docs.py" "$TMP/kopie"
for par in "${SOUBORY[@]}"; do
  set -- $par
  cp "$TMP/$2" "$REPO/api/$2"
done
cp "$TMP/test_stul_shop.py" "$REPO/scripts/2026-10-02_stul_testy/test_stul_shop.py"
cp "$TMP/run_all.sh" "$REPO/scripts/2026-10-02_stul_testy/run_all.sh"
cp "$TMP/kopie/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md"
cp "$TMP/kopie/MAPA_3D_A_GENERATORU.md" "$REPO/MAPA_3D_A_GENERATORU.md"
python3 -m py_compile "$REPO"/api/stul_konfigurator.py "$REPO"/api/stul_glb.py "$REPO"/api/stul_sse.py "$REPO"/api/stul_osvetleni.py "$REPO"/api/stul_shop.py "$REPO"/api/stul_ovladani_verejne.py
echo "aplikovano: api/{stul_konfigurator,stul_glb,stul_sse,stul_osvetleni,stul_shop,stul_ovladani_verejne}.py, scripts/2026-10-02_stul_testy/{test_stul_shop.py,run_all.sh}, docs/KONTRAKT_KONFIGURATOR_UI.md, MAPA_3D_A_GENERATORU.md"
