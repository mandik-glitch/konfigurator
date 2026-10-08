#!/usr/bin/env bash
# Regresni sada generatoru stolu pro volbu 'spodni police bez desky' (bot8, 2026-10-07): nove testy + existujici sady, ktere se tykaji polic / desek / kusovniku / ceny / schematu / kot / 3D ovladani / hashe.
# Pouziti:  run_regrese.sh [koren] [vystupni_soubor] [cast]
#   koren   = koren repa NEBO pracovni strom se symlinky api / webapp / scripts (vychozi: repo, ve kterem lezi tento skript); testy z nej berou api/ (importuji podle umisteni skriptu)
#   cast    = 1 | 2 | 3 | 4 | 5 (vychozi vse): 1 = jadro stolu, 2 = police / desky / koty, 3 = tezke sady jen nad generatorem, 4 = shop a SSE, 5 = NOVE testy (nad zivym stromem nemaji smysl)
# BEZ_NOVYCH=1 v prostredi preskoci nove testy police_bez_desky (beh nad zivym stromem).
# Vsechno bezi pres systemd-run s prostredim z api/.env (DB se jen CTE); vystup: radek '== nazev', posledni tri radky testu a 'rc=<kod>'.
set -u
ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
OUT="${2:-/dev/stdout}"
CAST="${3:-0}"
PY=/opt/konfigurator/api/venv/bin/python3
SUITES=(
  "5|2026-10-07_police_bez_desky/test_police_bez_desky.py"
  "5|2026-10-07_police_bez_desky/test_police_bez_desky_shop.py"
  "5|2026-10-07_police_bez_desky/test_police_bez_desky_zlato.py"
  "1|2026-10-02_stul_testy/test_stul_konfigurator.py"
  "1|2026-10-02_stul_testy/test_stul_glb.py"
  "1|2026-10-02_stul_testy/test_stul_shop.py"
  "1|2026-10-02_stul_testy/test_stul_api.py"
  "1|2026-10-02_stul_testy/test_stul_vyrez_police.py"
  "1|2026-10-02_stul_testy/test_stul_vyroba.py"
  "1|2026-10-02_stul_testy/test_stul_ovladani.py"
  "1|2026-10-02_stul_testy/test_stul_zive.py"
  "1|2026-10-02_stul_testy/test_stul_zive_vyska.py"
  "2|2026-10-02_stul_testy/test_stul_podpery.py"
  "2|2026-10-02_stul_testy/test_stul_police_vysky.py"
  "2|2026-10-02_stul_testy/test_stul_koty.py"
  "2|2026-10-02_stul_testy/test_stul_desky_tabule.py"
  "2|2026-10-02_stul_testy/test_stul_suplik_meze.py"
  "2|2026-10-02_stul_testy/test_stul_supliky.py"
  "2|2026-10-02_stul_testy/test_stul_strany_pet.py"
  "2|2026-10-02_stul_testy/test_stul_pet_umisteni.py"
  "2|2026-10-02_stul_testy/test_stul_loz.py"
  "2|2026-10-02_stul_testy/test_stul_suplik_klik.py"
  "2|2026-10-02_stul_testy/test_stul_pravidla.py"
  "2|2026-10-02_stul_testy/test_stul_pravidla_systemy.py"
  "2|2026-10-02_stul_testy/test_stul_led_svetlo.py"
  "3|2026-10-02_stul_testy/test_stul_panely.py"
  "3|2026-10-02_stul_testy/test_stul_panely_z.py"
  "3|2026-10-05_system35/test_navlek.py"
  "4|2026-10-05_system35/test_shop_navlek.py"
  "4|2026-10-05_system35/test_shop_system35.py"
  "3|2026-10-04_system40/test_regrese_system30.py"
  "3|2026-10-04_system40/test_regrese_35_40_navlek.py"
  "4|2026-10-04_system40/test_shop_system40.py"
  "4|2026-10-05_sse/test_sse_jadro.py"
  "4|2026-10-05_sse/test_sse_shop.py"
  "3|2026-10-05_luxy/test_osvetleni.py"
  "3|2026-10-06_zaslepky_konce/test_zaslepky_konce.py"
  "3|2026-10-06_razitka_stolu/test_razitka_stolu.py"
  "3|2026-10-07_perfopanel/test_panely_delky.py"
  "4|2026-10-07_perfopanel/test_panely_delky_shop.py"
  "4|2026-10-05_vychozi_konfigurace/test_vychozi.py"
)
for zaznam in "${SUITES[@]}"; do
  c="${zaznam%%|*}"; t="${zaznam#*|}"
  if [ "$CAST" != "0" ] && [ "$c" != "$CAST" ]; then continue; fi
  if [ "${BEZ_NOVYCH:-0}" = "1" ] && [[ "$t" == *police_bez_desky* ]]; then continue; fi          # BEZ_NOVYCH=1: jen existujici sady (beh nad zivym stromem, kde volba jeste neni)
  echo "== $t" >> "$OUT"
  timeout 2400 systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PYTHONDONTWRITEBYTECODE=1 --working-directory="$ROOT" "$PY" "$ROOT/scripts/$t" 2>&1 | grep -v "^jazyky:\|WARNING" | tail -3 >> "$OUT"
  echo "rc=${PIPESTATUS[0]}" >> "$OUT"
done
echo "HOTOVO" >> "$OUT"
