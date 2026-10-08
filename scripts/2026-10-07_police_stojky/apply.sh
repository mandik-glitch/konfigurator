#!/usr/bin/env bash
# Aplikuje horni polici mezi zadni stojky na ZIVY strom (volat uvnitr zamku bot8!). Nejdriv se VSE spocita do docasneho adresare a overi (kotvy, preklad, test, dokumentace) - teprve potom se zapisuje:
# api/stul_hpolice.py (novy), 5x api/*.py (zaplaty), 1x existujici test (scripts/2026-10-02_stul_testy/test_stul_shop.py), 1x docs, 1x webapp/katalog/product_<LAM12_ID>.glb (novy).
# Selze-li kotva (nekdo mezitim upravil stejne misto), nezapise se NIC. PORADI: 1) zaloz_kartu_lam12.py --apply (vytiskne ID karty), 2) tenhle skript s tim ID, 3) test_hpolice*.py, 4) commit, 5) reload API planovanou sluzbou.
# Pouziti: apply.sh [koren_repa] [lam12_id]   (vychozi: repo, ve kterem lezi tento skript; lam12_id vychozi 5360 = DALSI VOLNE ID V DOBE PSANI - overit zaloz_kartu_lam12.py!)
set -euo pipefail
REPO="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
LAM12="${2:-5360}"
HERE="$REPO/scripts/2026-10-07_police_stojky"
PY="$REPO/api/venv/bin/python3"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/api" "$TMP/docroot/docs"
# 1) vypocet + overeni (nic se nezapisuje do repa)
"$PY" "$HERE/apply_patches.py" "$REPO/api" "$TMP/api" --lam12-id "$LAM12"
for f in stul_konfigurator stul_glb stul_sse stul_ovladani_verejne stul_shop stul_hpolice; do "$PY" -m py_compile "$TMP/api/$f.py"; done
"$PY" "$HERE/patch_testy.py" "$REPO/scripts/2026-10-02_stul_testy/test_stul_shop.py" "$TMP/test_stul_shop.py"
"$PY" -m py_compile "$TMP/test_stul_shop.py"
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/docroot/docs/"
"$PY" "$HERE/patch_docs.py" "$TMP/docroot"
# 2) zapis (az po uspesnem overeni vseho)
"$PY" "$HERE/apply_patches.py" "$REPO/api" "$REPO/api" --lam12-id "$LAM12"
cp "$TMP/test_stul_shop.py" "$REPO/scripts/2026-10-02_stul_testy/test_stul_shop.py"
cp "$TMP/docroot/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md"
[ -f "$REPO/webapp/katalog/product_${LAM12}.glb" ] || "$PY" "$HERE/glb_lam12.py" "$REPO/webapp/katalog/product_${LAM12}.glb"
echo "HOTOVO. Dale: test_hpolice.py, test_hpolice_shop.py (systemd-run), commit (pathspec viz README.md), reload API planovanou sluzbou."
