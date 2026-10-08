#!/usr/bin/env bash
# DRUHE KOLO horni police (sikma police na boxy; bot8 fork 3, 2026-10-08): aplikuje NAD v1 (commit 110b03d3) na ZIVY strom (volat uvnitr zamku!). Nejdriv se VSE spocita do docasneho adresare
# a overi (kotvy, preklad, dokumentace, testy); teprve potom se zapisuje: 5x api/*.py (stul_hpolice.py = cely novy soubor, 4x zaplata), docs/KONTRAKT_KONFIGURATOR_UI.md a soubory
# slozky scripts/2026-10-07_police_stojky/ (testy, mutace, skripty). Selze-li kotva, nezapise se NIC. Zadna nova karta ani GLB (konzoly #3323 / #3324 uz v katalogu jsou).
# Pouziti: bash apply_v2.sh [koren_repa]   (spoustet z teto slozky = scratchpad/police_stojky/v2/skripty; vychozi koren /opt/konfigurator)
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-/opt/konfigurator}"
HERE="$REPO/scripts/2026-10-07_police_stojky"
PY="$REPO/api/venv/bin/python3"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/api" "$TMP/docroot/docs"
# 1) vypocet + overeni (nic se nezapisuje do repa)
"$PY" "$SRC/apply_patches_v2.py" "$REPO/api" "$TMP/api"
for f in stul_konfigurator stul_sse stul_ovladani_verejne stul_shop stul_hpolice; do "$PY" -m py_compile "$TMP/api/$f.py"; done
cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/docroot/docs/"
"$PY" "$SRC/patch_docs_v2.py" "$TMP/docroot"
for t in test_hpolice test_hpolice_shop test_hpolice_sikma mutace_hpolice apply_patches_v2 patch_docs_v2; do "$PY" -m py_compile "$SRC/$t.py"; done
# 2) zapis (az po uspesnem overeni vseho)
"$PY" "$SRC/apply_patches_v2.py" "$REPO/api" "$REPO/api"
cp "$TMP/docroot/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md"
for f in stul_hpolice.py apply_patches_v2.py patch_docs_v2.py DOKUMENTACE_SIKMA.md test_hpolice.py test_hpolice_shop.py test_hpolice_sikma.py mutace_hpolice.py prepare_cand_v2.sh README.md commit_api_v2.txt apply_v2.sh; do
  [ "$SRC/$f" -ef "$HERE/$f" ] || cp "$SRC/$f" "$HERE/$f"
done
echo "HOTOVO. Dale: test_hpolice_sikma.py + test_hpolice.py (hermeticke), test_hpolice_shop.py (systemd-run, DB jen cte), existujici sada scripts/2026-10-02_stul_testy/run_all.sh, commit (pathspec viz README.md), reload API planovanou sluzbou."
