#!/usr/bin/env bash
# FAZE 2 generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): aplikuje na ZIVY strom (volat uvnitr zamku: scripts/lock.sh acquire; webapp/* je guardovane). Nejdriv se VSE spocita do docasneho
# adresare a overi (kotvy zaplat, preklad, JS syntaxe, dokumentace, piny ?v=, hermeticke testy nad vypocitanym api); teprve potom se zapisuje. Selze-li cokoli pred zapisem, v repu se nezmeni NIC.
# Zapisuje: 4x api/*.py zaplata (konfigurator_registr, stul_shop, konfigurace_kosik, nabidka_z_konfigurace) + 4x NOVY api/oploceni_{konfigurator,glb,cena,shop}.py, webapp/oploceni-konfigurator.html
# a webapp/js/oploceni-host.js (s vypocitanymi ?v=), docs/KONTRAKT_OPLOCENI.md (novy), upravy MAPA_3D_A_GENERATORU.md a docs/KONTRAKT_KONFIGURATOR_UI.md, soubory slozky scripts/2026-10-08_oploceni/
# (testy, mutace, skripty karet, README_FAZE2.md ...; stare kopie jadra z faze 1 v teto slozce se SMAZOU - ted jsou v api/). DB se nedotyka, nic nerestartuje (api/*.py nasadi planovana sluzba 0:00 / 12:30).
# Pouziti: bash apply_f2.sh [--jen-vypocet] [koren_repa]      (spoustet ze slozky se zdroji = scratchpad/oploceni/f2/skripty; vychozi koren /opt/konfigurator)
#   --jen-vypocet = spocita a overi vse, ale nezapise nic (nahled; vypise, co by se zapsalo)
set -euo pipefail
JEN_VYPOCET=0
if [ "${1:-}" = "--jen-vypocet" ]; then JEN_VYPOCET=1; shift; fi
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-/opt/konfigurator}"
HERE="$REPO/scripts/2026-10-08_oploceni"
PY="$REPO/api/venv/bin/python3"
[ -x "$PY" ] || PY=/opt/konfigurator/api/venv/bin/python3
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
NOVE_API="oploceni_konfigurator.py oploceni_glb.py oploceni_cena.py oploceni_shop.py"
ZAPLATY_API="konfigurator_registr.py stul_shop.py konfigurace_kosik.py nabidka_z_konfigurace.py"
SOUBORY_SCRIPTU="README.md README_FAZE2.md commit_f2.txt apply_f2.sh apply_patches_f2.py patch_docs_f2.py oploceni_verze.py run_regrese.py test_oploceni.py test_oploceni_shop.py test_oploceni_karty.py test_oploceni_stranka.js _most_oploceni.py mutace_oploceni.py render_oploceni.py render_glb.js overeni_ve_vieweru.js zaloz_kartu_oploceni.py zaloz_karty_vyplni.py"
STARE_Z_FAZE1="oploceni_konfigurator.py oploceni_glb.py oploceni_cena.py"

# 0) predpoklady
[ -d "$REPO/api" ] && [ -d "$REPO/webapp" ] && [ -d "$HERE" ] || { echo "CHYBA: $REPO nevypada jako koren repa s fazi 1 ($HERE chybi)"; exit 2; }
if [ -e "$REPO/api/oploceni_shop.py" ] || grep -q "modul_pro" "$REPO/api/konfigurator_registr.py"; then echo "CHYBA: faze 2 uz je v $REPO aplikovana (api/oploceni_shop.py nebo modul_pro existuje) - nic se nedela"; exit 3; fi
for f in $ZAPLATY_API; do [ -f "$REPO/api/$f" ] || { echo "CHYBA: chybi $REPO/api/$f"; exit 2; }; done
for f in $SOUBORY_SCRIPTU; do [ -f "$SRC/$f" ] || { echo "CHYBA: ve zdrojich chybi $f"; exit 2; }; done

# 1) vypocet + overeni (nic se nezapisuje do repa)
mkdir -p "$TMP/api" "$TMP/webapp/js" "$TMP/docroot/docs"
"$PY" "$SRC/apply_patches_f2.py" "$REPO/api" "$TMP/api"
for f in $ZAPLATY_API $NOVE_API; do "$PY" -m py_compile "$TMP/api/$f"; done
for t in test_oploceni test_oploceni_shop test_oploceni_karty mutace_oploceni zaloz_kartu_oploceni zaloz_karty_vyplni run_regrese render_oploceni _most_oploceni oploceni_verze patch_docs_f2 apply_patches_f2; do "$PY" -m py_compile "$SRC/$t.py"; done
cp "$REPO/MAPA_3D_A_GENERATORU.md" "$TMP/docroot/"; cp "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md" "$TMP/docroot/docs/"; cp "$SRC/novy_docs/KONTRAKT_OPLOCENI.md" "$TMP/docroot/docs/"
"$PY" "$SRC/patch_docs_f2.py" "$TMP/docroot"
cp "$SRC/novy_webapp/oploceni-konfigurator.html" "$TMP/webapp/"; cp "$SRC/novy_webapp/js/oploceni-host.js" "$TMP/webapp/js/"
"$PY" "$SRC/oploceni_verze.py" "$REPO" "$TMP/webapp"
if command -v node >/dev/null 2>&1; then node --check "$TMP/webapp/js/oploceni-host.js"; fi
# hermeticke testy nad VYPOCITANYM api: docasny koren (symlinky na zive polozky repa, api = zive soubory + vypocitanych 8, scripts/2026-10-08_oploceni = zdroje z teto slozky)
R="$TMP/root"; mkdir -p "$R/scripts/2026-10-08_oploceni" "$TMP/apitree"
for f in "$REPO"/api/*; do [ "$(basename "$f")" = "__pycache__" ] && continue; ln -s "$f" "$TMP/apitree/$(basename "$f")"; done
for f in $ZAPLATY_API $NOVE_API; do rm -f "$TMP/apitree/$f"; cp "$TMP/api/$f" "$TMP/apitree/$f"; done
for f in "$REPO"/* "$REPO"/.[!.]*; do b="$(basename "$f")"; [ -e "$f" ] || continue; case "$b" in api|scripts) continue;; esac; ln -s "$f" "$R/$b"; done
ln -s "$TMP/apitree" "$R/api"
for f in "$REPO"/scripts/*; do b="$(basename "$f")"; [ "$b" = "2026-10-08_oploceni" ] && continue; ln -s "$f" "$R/scripts/$b"; done
for f in $SOUBORY_SCRIPTU; do cp "$SRC/$f" "$R/scripts/2026-10-08_oploceni/$f"; done
(cd "$R" && PYTHONDONTWRITEBYTECODE=1 "$PY" "$R/scripts/2026-10-08_oploceni/test_oploceni.py" | tail -1 && PYTHONDONTWRITEBYTECODE=1 "$PY" "$R/scripts/2026-10-08_oploceni/test_oploceni_karty.py" | tail -1)
echo "VYPOCET A OVERENI V PORADKU (zadna zmena repa)."
echo "  api:     $ZAPLATY_API (zaplaty) + $NOVE_API (nove)"
echo "  webapp:  oploceni-konfigurator.html, js/oploceni-host.js"
echo "  docs:    docs/KONTRAKT_OPLOCENI.md (novy), docs/KONTRAKT_KONFIGURATOR_UI.md, MAPA_3D_A_GENERATORU.md"
echo "  scripts: $HERE (+ smazat stare kopie jadra z faze 1: $STARE_Z_FAZE1)"
if [ "$JEN_VYPOCET" = 1 ]; then exit 0; fi

# 2) zapis (az po uspesnem overeni vseho; cp --remove-destination = nikdy nezapisuje PRES symlink)
for f in $ZAPLATY_API $NOVE_API; do cp --remove-destination "$TMP/api/$f" "$REPO/api/$f"; done
cp --remove-destination "$TMP/webapp/oploceni-konfigurator.html" "$REPO/webapp/oploceni-konfigurator.html"
cp --remove-destination "$TMP/webapp/js/oploceni-host.js" "$REPO/webapp/js/oploceni-host.js"
cp --remove-destination "$TMP/docroot/MAPA_3D_A_GENERATORU.md" "$REPO/MAPA_3D_A_GENERATORU.md"
cp --remove-destination "$TMP/docroot/docs/KONTRAKT_KONFIGURATOR_UI.md" "$REPO/docs/KONTRAKT_KONFIGURATOR_UI.md"
cp --remove-destination "$TMP/docroot/docs/KONTRAKT_OPLOCENI.md" "$REPO/docs/KONTRAKT_OPLOCENI.md"
for f in $SOUBORY_SCRIPTU; do [ "$SRC/$f" -ef "$HERE/$f" ] || cp --remove-destination "$SRC/$f" "$HERE/$f"; done
for f in $STARE_Z_FAZE1; do rm -f "$HERE/$f"; done
echo "HOTOVO. Dale (viz README_FAZE2.md):"
echo "  1) PYTHONDONTWRITEBYTECODE=1 $PY $HERE/test_oploceni.py  a  test_oploceni_karty.py   (hermeticke)"
echo "  2) systemd-run --pipe --wait --quiet --property=EnvironmentFile=$REPO/api/.env --setenv=HOME=/root --working-directory=$REPO $PY $HERE/test_oploceni_shop.py   (DB jen cte)"
echo "  3) git add <pathspec z commit_f2.txt>, commit; API nasadi planovana sluzba (0:00 / 12:30), staticke soubory jsou zive hned"
echo "  4) AZ PO nasazeni API: zaloz_kartu_oploceni.py --apply, pak (po Robertovi) zaloz_karty_vyplni.py --apply"
