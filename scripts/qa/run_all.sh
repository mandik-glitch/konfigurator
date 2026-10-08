#!/usr/bin/env bash
# scripts/qa/run_all.sh - agregator QA suit (bot14, 2026-09-02, bod H
# "kontrolni mechanismy na cely system konfiguratoru").
#
# Spousti VSECHNY suity SEKVENCNE (Robert/bot3: RAM na sdilenem VPS,
# zadny paralelni beh navic), kazdou s timeoutem 10 min, sbira jejich
# --json vystup a slouci pres merge_reports.py do
# qa-reports/<YYYY-MM-DD_HHMM>.json + .md (+ symlink latest.json/.md).
#
# Suity:
#   - scripts/qa_product_audit.py (existujici, qa_checks.py) jako "data_code"
#   - kazdy scripts/qa/*.py (krome _common.py/merge_reports.py/tohohle
#     souboru) jako suite = jmeno souboru bez pripony - health.py ->
#     "health", logs.py -> "logs", atd. NECEKA se na suity ostatnich
#     botu (bot5/bot13/bot15/bot6) - kdyz jejich soubor jeste
#     neexistuje, proste se v teto iteraci vynecha.
#   - kazdy scripts/qa/*.sh (krome tohohle) - stejny vzor
#   - scripts/qa/e2e/run.cjs (pokud existuje - bot5 Playwright)
#
# Pouziti:
#   scripts/qa/run_all.sh
# Exit kod: 0 ok, 1 warn, 2 fail (podle merge_reports.py vysledku),
# 3 pri internim selhani agregatoru samotneho.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QA_DIR="$REPO_ROOT/scripts/qa"
PY="$REPO_ROOT/api/venv/bin/python3"
# Nektere suity (napr. bot15 seo.py - BeautifulSoup) potrebuji baliky,
# ktere jsou jen v samostatnem scripts/qa/.venv (bot3: "QA nastroje
# treti strany do scripts/qa/.venv, ne do produkcniho venv"). Tenhle
# venv ma navic i pymysql (overeno zive), takze je bezpecny univerzalni
# fallback interpret pro .py suity BEZ vlastniho .sh wrapperu (ktery by
# jinak spravny interpret volil sam - viz static.sh vzor).
QA_PY="$PY"
if [ -x "$QA_DIR/.venv/bin/python3" ]; then
  QA_PY="$QA_DIR/.venv/bin/python3"
fi
TMP_DIR="$(mktemp -d /tmp/qa-run-all.XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -e /run/ram-watchdog-alert ]; then
  echo "RAM watchdog alert aktivni (/run/ram-watchdog-alert) - QA beh preskocen, at nepridava dalsi zatez." >&2
  exit 3
fi

declare -a MERGE_ARGS=()

run_one() {
  local suite_name="$1"; shift
  local out_file="$TMP_DIR/${suite_name}.json"
  echo "=== spoustim suitu: $suite_name ===" >&2
  if timeout 600 "$@" --json > "$out_file" 2>"$TMP_DIR/${suite_name}.stderr"; then
    :
  fi
  # exit kod suity muze byt 0/1/2 (ok/warn/fail, viz kontrakt) - to NENI
  # duvod k MISSING, jen kdyz je vystup skutecne prazdny/chybi (crash
  # pred prvnim printem, timeout zabil proces drive, atd.).
  if [ ! -s "$out_file" ]; then
    local reason
    reason="$(tail -c 500 "$TMP_DIR/${suite_name}.stderr" 2>/dev/null || echo 'žádný výstup')"
    MERGE_ARGS+=("$suite_name" "MISSING:${reason}")
  else
    MERGE_ARGS+=("$suite_name" "$out_file")
  fi
}

# --- existujici qa_product_audit.py jako suite "data_code" ---
run_one "data_code" "$PY" "$REPO_ROOT/scripts/qa_product_audit.py"
declare -A HANDLED=([data_code]=1)

# --- scripts/qa/*.sh NEJDRIV (kromě tohohle) - .sh je "oficialni"
# spousteci obal, ktery si sam vybira spravny interpret (viz
# static.sh: produkcni venv pro hlavni beh, vlastni .venv jen pro
# pyflakes uvnitr) - kdyz existuje, MA prednost pred stejnojmennym .py. ---
for f in "$QA_DIR"/*.sh; do
  [ -e "$f" ] || continue
  base="$(basename "$f" .sh)"
  [ "$base" = "run_all" ] && continue
  chmod +x "$f" 2>/dev/null || true
  run_one "$base" "$f"
  HANDLED[$base]=1
done

# --- scripts/qa/*.py (kromě infrastrukturnich souboru a suit uz
# pokrytych vlastnim .sh wrapperem vyse) - beh pod scripts/qa/.venv,
# pokud existuje (fallback pro baliky mimo produkcni api/venv, napr.
# BeautifulSoup u seo.py - zivy test 2026-09-02 to odhalil jako
# ModuleNotFoundError pri pokusu spustit pod api/venv). ---
for f in "$QA_DIR"/*.py; do
  [ -e "$f" ] || continue
  base="$(basename "$f" .py)"
  case "$base" in
    _common|merge_reports|send_alert) continue ;;
  esac
  [ -n "${HANDLED[$base]:-}" ] && continue
  run_one "$base" "$QA_PY" "$f"
  HANDLED[$base]=1
done

# --- e2e (Playwright, bot5) - jiny vzor spousteni (node, ne python) ---
if [ -f "$QA_DIR/e2e/run.cjs" ]; then
  run_one "e2e" node "$QA_DIR/e2e/run.cjs"
fi

echo "=== slucuji vysledky ===" >&2
merge_argv=()
for ((i=0; i<${#MERGE_ARGS[@]}; i+=2)); do
  merge_argv+=(--input "${MERGE_ARGS[i]}" "${MERGE_ARGS[i+1]}")
done
"$PY" "$QA_DIR/merge_reports.py" "${merge_argv[@]}"
merge_status=$?

# Alert (Robert/bot3: critical nalez -> pending e-mail do system_emails
# fronty, NIKDY primo odeslani) - az PO uspesnem slouceni, potrebuje
# hotovy qa-reports/latest.json.
"$PY" "$QA_DIR/send_alert.py" || echo "send_alert.py selhal (nekriticke, report uz je ulozeny)" >&2

exit $merge_status
