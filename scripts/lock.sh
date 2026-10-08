#!/bin/bash
# Atomicky obal nad DEPLOY_LOCK.json (viz WORKFLOW.md - "Deploy zamek").
#
# DUVOD (bot3, 2026-08-06, po realne kolizi v teze session): puvodni
# rucni postup "precti DEPLOY_LOCK.json, uvidis-li held_by:null, zapis
# tam sam sebe" NENI atomicky - mezi cist a zapsat muze jiny bot udelat
# totez, oba uvidi "volno" a oba si mysli, ze zamek drzi. Presne tohle
# se stalo: bot3 precetl held_by:null, nez stihl zapsat, bot4 uz zamek
# mezitim zabral - bot3 to sice zachytil (nahodou, diky "soubor se zmenil"
# hlasce sveho edit nastroje), ale zadny takovy bezpecnostni pojistka NENI
# zarucena pro kazdy zpusob zapisu (napr. holy `echo > DEPLOY_LOCK.json`
# by race tise prohral).
#
# Tenhle skript nahrazuje rucni cti+pis jednim atomickym prikazem: uvnitr
# je kazdy pokus o acquire/release chranen `flock` na lokalnim mutex
# souboru (ne v gitu, nezavisi na obsahu DEPLOY_LOCK.json), takze dva
# soubezne spustene `lock.sh acquire` nemuzou nikdy oba uspet. Navic
# acquire/release rovnou i commituje (BOT_ID nastaveny spravne pro
# pre-commit hook) - odpada scenar, kdy bot zapise zamek na disk, ale
# ZAPOMENE ho hned commitnout a mezitim zacne editovat hlidane soubory
# (presne to udelal bot3 dnes: napsal DEPLOY_LOCK.json, ale pokracoval
# v editaci pred commitem).
#
# Pouziti:
#   scripts/lock.sh acquire <bot_id> "<poznamka co delas>" [--wait[=SEKUNDY]]
#   scripts/lock.sh release <bot_id>
#   scripts/lock.sh status
#   scripts/lock.sh require <bot_id>   # exit 1 (bez zmeny), pokud zamek
#                                       # prave nedrzi <bot_id> - pouzit
#                                       # jako pojistka PRED sftp/restart/
#                                       # cimkoli, co by nemelo bezet bez
#                                       # drzeneho zamku.
#
# --wait (bot4 navrh, 2026-08-06): misto vlastni cekaci smycky (kazdy
# bot by si jinak psal vlastni "cti po X sekundach, dokud neni volno" -
# presne to udelal bot3 rucne pred timhle skriptem) proste pockej uvnitr
# lock.sh. Bez --wait/--wait=N ceka implicitne 1800s (30 min), pak selze
# jasnou hlaskou - ne nekonecne, aby zamek "zaseknuty" omylem netocil
# bota do nekonecna bez povsimnuti. --wait=0 = cekej bez limitu.
#
# Puvodni rucni postup (Read/Write DEPLOY_LOCK.json primo) dal FUNGUJE -
# hook overuje jen VYSLEDNY commitnuty obsah, ne to, jak vznikl. Tenhle
# skript je ale ZASADNE DOPORUCENY zpusob acquire/release, viz WORKFLOW.md.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
LOCK_JSON="$REPO_ROOT/DEPLOY_LOCK.json"
MUTEX="$REPO_ROOT/.deploy_lock.mutex"
POLL_INTERVAL=15
DEFAULT_WAIT_SECONDS=1800

usage() {
  echo "Pouziti:" >&2
  echo "  scripts/lock.sh acquire <bot_id> \"<poznamka>\" [--wait[=SEKUNDY]]" >&2
  echo "  scripts/lock.sh release <bot_id>" >&2
  echo "  scripts/lock.sh status" >&2
  echo "  scripts/lock.sh require <bot_id>" >&2
  exit 2
}

CMD="${1:-}"
[ -n "$CMD" ] || usage
shift || true

BOT=""
NOTE=""
WAIT_MODE=0
WAIT_SECONDS="$DEFAULT_WAIT_SECONDS"

case "$CMD" in
  status)
    cat "$LOCK_JSON" 2>/dev/null || echo '{"held_by": null}'
    exit 0
    ;;
  require)
    BOT="${1:-}"
    [ -n "$BOT" ] || usage
    ;;
  acquire)
    BOT="${1:-}"
    NOTE="${2:-}"
    [ -n "$BOT" ] || usage
    shift 2 || true
    for arg in "$@"; do
      case "$arg" in
        --wait)
          WAIT_MODE=1
          ;;
        --wait=*)
          WAIT_MODE=1
          WAIT_SECONDS="${arg#--wait=}"
          ;;
        *)
          echo "Neznamy argument: $arg" >&2
          usage
          ;;
      esac
    done
    ;;
  release)
    BOT="${1:-}"
    [ -n "$BOT" ] || usage
    ;;
  *)
    usage
    ;;
esac

read_held_by() {
  python3 - "$LOCK_JSON" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        raw = f.read()
    if not raw.strip():
        print("")
    else:
        data = json.loads(raw)
        print(data.get("held_by") or "")
except Exception:
    print("__PARSE_ERROR__")
PYEOF
}

if [ "$CMD" = "require" ]; then
  CURRENT=$(read_held_by)
  if [ "$CURRENT" != "$BOT" ]; then
    echo "ODMITNUTO: zamek nedrzis ty ('$BOT') - aktualni drzitel: '${CURRENT:-<nikdo, zamek je volny>}'." >&2
    exit 1
  fi
  exit 0
fi

# Jeden atomicky pokus o acquire/release. flock drzeny JEN na dobu
# tehohle jednoho pokusu (subshell + fd otevreny tady) - "acquire --wait"
# nize mezi pokusy spi, ne ze by po celou dobu blokoval treba
# "scripts/lock.sh status" jineho bota.
try_once() {
  (
    flock -w 30 9 || { echo "MUTEX_BUSY"; exit 3; }
    CURRENT=$(read_held_by)
    if [ "$CURRENT" = "__PARSE_ERROR__" ]; then
      echo "PARSE_ERROR"
      exit 2
    fi
    if [ "$CMD" = "acquire" ]; then
      if [ -n "$CURRENT" ] && [ "$CURRENT" != "$BOT" ]; then
        echo "$CURRENT"
        exit 1
      fi
      python3 - "$LOCK_JSON" "$BOT" "$NOTE" <<'PYEOF'
import json, sys, datetime
path, bot, note = sys.argv[1], sys.argv[2], sys.argv[3]
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
with open(path, "w") as f:
    json.dump({"held_by": bot, "since": now, "note": note}, f, ensure_ascii=False, indent=2)
    f.write("\n")
PYEOF
      cd "$REPO_ROOT"
      git add DEPLOY_LOCK.json
      # bot3 2026-08-06: git commit muze selhat (pre-commit hook odmitne,
      # pokud HEAD mezitim - mimo tenhle flock, napr. bezny feature commit
      # jineho bota, ktery DEPLOY_LOCK.json vubec nemeni - poodejde a
      # PRIOR_HELD_BY uz neodpovida tomu, co jsme cetli v CURRENT o par
      # radku vys). Puvodne se navratovy kod NEKONTROLOVAL -> skript
      # tise ohlasil "OK: zamek acquired", i kdyz commit ve skutecnosti
      # neprosel a DEPLOY_LOCK.json na disku pak lhal (jiny bot uz nemel
      # skutecne odemceno) - realne se to stalo 2x behem jedne session,
      # viz AGENTS_LOG.md. Pri selhani vratime soubor na disku zpet na
      # HEAD (at nezanechame nekonzistentni stopu) a ohlasime jako
      # "busy" - volajici (wait smycka nize) to zkusi znovu.
      #
      # bot9 2026-08-21: `git checkout -- file` PO predchozim `git add`
      # je no-op (kopiruje z INDEXU, ktery uz ma nas novy/spatny obsah
      # staged - nekopiruje z HEAD). Realny dusledek: pri COMMIT_RACE
      # zustaval DEPLOY_LOCK.json na disku (i staged) ukazovat NAS
      # pokus o acquire/release, presestoze commit selhal - ostatni boti
      # ctouci "cat DEPLOY_LOCK.json"/"lock.sh status" tak videli
      # phantom drzitele, ktery ve skutecnosti nikdy nebyl commitnuty
      # (zjisteno naživo: 3 ruzne boty behem ~70 min ohlasovaly ruzne
      # "drzitele", zadny z toho se ale neobjevil v `git log --
      # DEPLOY_LOCK.json`). Oprava: `checkout HEAD --` resetuje SOUCASNE
      # index i pracovni strom na skutecny posledni commit.
      # bot16 2026-08-30 (naživo zjištěno: holý `git commit` tady sebral i
      # cizí jiz stagovany soubor volajiciho bota do stejneho commitu -
      # presne anti-vzor, ktery WORKFLOW.md bod 5 zakazuje, jen uvnitr
      # tohohle skriptu samotneho): commit VZDY jen explicitni cestou
      # k DEPLOY_LOCK.json, nikdy cely index.
      if ! BOT_ID="$BOT" git commit -q -m "lock: $BOT acquire - $NOTE" -- "$LOCK_JSON"; then
        git checkout HEAD -- "$LOCK_JSON" 2>/dev/null
        echo "COMMIT_RACE"
        exit 4
      fi
      exit 0
    else
      if [ -n "$CURRENT" ] && [ "$CURRENT" != "$BOT" ]; then
        echo "$CURRENT"
        exit 1
      fi
      printf '{\n  "held_by": null\n}\n' > "$LOCK_JSON"
      cd "$REPO_ROOT"
      git add DEPLOY_LOCK.json
      # bot16 2026-08-30: stejna oprava jako u acquire vyse - explicitni
      # cesta, nikdy cely index.
      if ! BOT_ID="$BOT" git commit -q -m "lock: $BOT release" -- "$LOCK_JSON"; then
        git checkout HEAD -- "$LOCK_JSON" 2>/dev/null
        echo "COMMIT_RACE"
        exit 4
      fi
      exit 0
    fi
  ) 9>"$MUTEX"
}

if [ "$CMD" = "release" ]; then
  OUT=$(try_once) && { echo "OK: zamek uvolnen."; exit 0; }
  RC=$?
  if [ "$RC" = 2 ]; then
    echo "ODMITNUTO: DEPLOY_LOCK.json je poskozeny/neparsovatelny JSON - oprav rucne, pak zkus znovu." >&2
  elif [ "$RC" = 3 ]; then
    echo "ODMITNUTO: nepodarilo se ziskat interni mutex lock.sh do 30s - zkus to znovu." >&2
  elif [ "$RC" = 4 ]; then
    echo "ODMITNUTO: git commit odmitnul (jiny commit prave zmenil HEAD) - prechodna kolize, zkus to znovu." >&2
  else
    echo "ODMITNUTO: zamek drzi '$OUT', ne '$BOT' - nemuzes uvolnit cizi zamek." >&2
  fi
  exit 1
fi

# acquire
if [ "$WAIT_MODE" = "0" ]; then
  OUT=$(try_once) && { echo "OK: zamek acquired pro '$BOT'."; exit 0; }
  RC=$?
  if [ "$RC" = 2 ]; then
    echo "ODMITNUTO: DEPLOY_LOCK.json je poskozeny/neparsovatelny JSON - oprav rucne, pak zkus znovu." >&2
  elif [ "$RC" = 3 ]; then
    echo "ODMITNUTO: nepodarilo se ziskat interni mutex lock.sh do 30s - zkus to znovu." >&2
  elif [ "$RC" = 4 ]; then
    echo "ODMITNUTO: git commit odmitnul (jiny commit prave zmenil HEAD) - prechodna kolize, zkus to znovu (nebo pouzij --wait)." >&2
  else
    echo "ODMITNUTO: zamek uz drzi '$OUT' (ne '$BOT'). Pockej, az bude volny (scripts/lock.sh status), nebo pouzij --wait." >&2
  fi
  exit 1
fi

START=$(date +%s)
NO_LIMIT=0
[ "$WAIT_SECONDS" = "0" ] && NO_LIMIT=1
DEADLINE=$((START + WAIT_SECONDS))
LAST_PRINT=$START
echo "Cekam na zamek pro '$BOT' (aktualne drzi: $(read_held_by))..."
while true; do
  if OUT=$(try_once); then
    echo "OK: zamek acquired pro '$BOT' (po $(( $(date +%s) - START ))s cekani)."
    exit 0
  fi
  RC=$?
  if [ "$RC" = 2 ]; then
    echo "ODMITNUTO: DEPLOY_LOCK.json je poskozeny/neparsovatelny JSON - oprav rucne, pak zkus znovu." >&2
    exit 1
  fi
  NOW=$(date +%s)
  if [ "$NO_LIMIT" = "0" ] && [ "$NOW" -ge "$DEADLINE" ]; then
    echo "ODMITNUTO: timeout po ${WAIT_SECONDS}s cekani - zamek porad drzi '$OUT'. Zkus scripts/lock.sh acquire ... --wait znovu, nebo napis do AGENTS_LOG.md/zeptej se Roberta." >&2
    exit 1
  fi
  if [ $((NOW - LAST_PRINT)) -ge 120 ]; then
    if [ "$RC" = 4 ]; then
      echo "...prechodna kolize commitu, zkousim znovu ($(( NOW - START ))s)"
    else
      echo "...porad ceka, drzi '$OUT' ($(( NOW - START ))s)"
    fi
    LAST_PRINT=$NOW
  fi
  SLEEP_FOR=$POLL_INTERVAL
  if [ "$NO_LIMIT" = "0" ]; then
    REMAINING=$((DEADLINE - NOW))
    [ "$REMAINING" -lt "$SLEEP_FOR" ] && SLEEP_FOR=$REMAINING
    [ "$SLEEP_FOR" -lt 1 ] && SLEEP_FOR=1
  fi
  sleep "$SLEEP_FOR"
done
