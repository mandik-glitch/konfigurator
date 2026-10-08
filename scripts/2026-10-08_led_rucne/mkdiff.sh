#!/usr/bin/env bash
# Z pracovnich kopii upravenych testu ($TW/<adresar>/<soubor>, vychozi $SP/led_rucne/tw) udela unified diffy proti ZIVYM souborum do patches_test/ (cesty a/<adresar>/<soubor>).
# Poradi a nazvy diffu: NN_<popis>.diff podle seznamu ZAZNAMY nize. Pouziti: mkdiff.sh
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
TW="${TW:-${SP:?nastav SP nebo TW}/led_rucne/tw}"
OUT="$REPO/scripts/2026-10-08_led_rucne/patches_test"
ZAZNAMY=(
  "03_led600_test_led_delka|2026-10-07_led600_generator/test_led_delka.py"
  "04_led600_test_led_delka_shop|2026-10-07_led600_generator/test_led_delka_shop.py"
  "05_led600_test_led_delka_lux|2026-10-07_led600_generator/test_led_delka_lux.py"
  "06_led600_test_led_delka_stranka|2026-10-07_led600_generator/test_led_delka_stranka.js"
  "07_police_bez_desky_spolecne|2026-10-07_police_bez_desky/_spolecne.py"
  "08_police_bez_desky_test|2026-10-07_police_bez_desky/test_police_bez_desky.py"
  "09_police_bez_desky_zlato|2026-10-07_police_bez_desky/test_police_bez_desky_zlato.py"
  "10_police_stojky_golden_head|2026-10-07_police_stojky/golden_head.py"
  "11_police_stojky_test_hpolice|2026-10-07_police_stojky/test_hpolice.py"
)
cd "$REPO/scripts"
for z in "${ZAZNAMY[@]}"; do
  nazev="${z%%|*}"; rel="${z#*|}"
  if [ -f "$TW/$rel" ]; then
    if diff -u --label "a/$rel" --label "b/$rel" "$rel" "$TW/$rel" > "$OUT/$nazev.diff"; then
      rm -f "$OUT/$nazev.diff"; echo "$nazev: bez zmeny"
    else
      echo "$nazev: $(grep -c '^[-+][^-+]' "$OUT/$nazev.diff") zmenenych radku"
    fi
  fi
done
