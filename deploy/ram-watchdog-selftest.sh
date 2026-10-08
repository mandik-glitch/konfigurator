#!/bin/bash
# ram-watchdog-selftest.sh - test logiky deploy/ram-watchdog.sh BEZ dotyku
# zivych procesu a bez zapisu mimo docasny adresar.
#
#   bash deploy/ram-watchdog-selftest.sh          -> "SELFTEST OK" / exit 1 + log
#
# Co se testuje:
#   A) dry-run, simulovana pamet pres RAM_WATCHDOG_FAKE_MEM_FILE:
#      normal -> SOFT -> HARD -> ESCALATE (jen log, tmux se nevola)
#      -> SOFT (hystereze: nic se neprobouzi) -> RECOVER (alert smazan)
#   B) swap "0 0" (server bez swapu) i swap 90 % -> HARD bez deleni nulou
#   C) skutecny SIGSTOP/SIGCONT, ale POUZE na vlastnim dummy procesu:
#      kopie /bin/sleep s unikatnim jmenem + SAFE_COMM zuzeny jen na ni,
#      SAFE_EXE_DIRS=/nonexistent/ -> nic jineho v systemu nemuze byt zasazeno.
#   D) hlidac se sam nikdy nezastavi, pid 1 nikdy.
#   E) realna eskalace (send-keys) do vlastni docasne tmux session + hlaseni
#      selhani pri neexistujici session (soubor ESCALATE_FAIL_FILE).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
WD=$HERE/ram-watchdog.sh
T=$(mktemp -d "${TMPDIR:-/tmp}/ram-watchdog-selftest.XXXXXX")
trap 'kill $WPID $DUMMY 2>/dev/null; kill -CONT $DUMMY 2>/dev/null; [ -n "${TS:-}" ] && tmux kill-session -t "=$TS" 2>/dev/null; rm -rf "$T"' EXIT
FAIL=0
fail() { echo "FAIL: $*"; FAIL=1; }
LOG=$T/log; ALERT=$T/alert; FAILF=$T/escfail; MEM=$T/mem
common=(STATE_DIR="$T/state" LOG_FILE="$LOG" ALERT_FILE="$ALERT" ESCALATE_FAIL_FILE="$FAILF"
        RAM_WATCHDOG_FAKE_MEM_FILE="$MEM" INTERVAL=1 ESCALATE_AFTER=2 ESCALATE_REPEAT=3 HEARTBEAT_EVERY=100000
        COORDINATOR_TMUX_SESSION=ram-watchdog-selftest-neexistuje)
wait_log() {  # wait_log <regex> [timeout_s]
    local i=0; while ! grep -Eq "$1" "$LOG" 2>/dev/null; do i=$((i+1)); [ $i -ge $((${2:-8}*10)) ] && return 1; sleep 0.1; done
}
mem() { echo "$*" > "$MEM"; }

echo "== A/B: dry-run, simulovana pamet =="
mem 20000 0 0
env "${common[@]}" RAM_WATCHDOG_DRY_RUN=1 SAFE_COMM=none SAFE_EXE_DIRS=/nonexistent/ bash "$WD" & WPID=$!
wait_log '^.* start: ' || fail "start nezalogovan"
sleep 1.2; [ -e "$ALERT" ] && fail "alert existuje pri 20000 MB"
mem 1200 0 0;  wait_log 'SOFT alert: dostupne 1200 MB' || fail "SOFT nenastal"
sleep 0.3; grep -q ' SOFT avail=1200MB swap=0%' "$ALERT" || fail "alert soubor po SOFT: $(cat "$ALERT" 2>/dev/null)"
mem 400 0 0;   wait_log 'HARD alert: dostupne 400 MB, swap 0 %' || fail "HARD (bez swapu) nenastal"
wait_log 'DRY-RUN: ESCALATE do tmux .*HARD RAM alert trva [0-9]+ s: dostupne 400 MB, swap 0 %, pozastaveno 0 procesu z bezpecneho seznamu - .*ram-watchdog.log\)$' 6 || fail "ESCALATE po ESCALATE_AFTER nenastal / zprava neni jednoradkova: $(grep -A1 'DRY-RUN: ESCALATE' "$LOG")"
i=0; while [ "$(grep -c 'DRY-RUN: ESCALATE' "$LOG")" -lt 2 ] && [ $i -lt 80 ]; do i=$((i+1)); sleep 0.1; done
[ "$(grep -c 'DRY-RUN: ESCALATE' "$LOG")" -ge 2 ] || fail "ESCALATE se neopakuje po ESCALATE_REPEAT (${ESCALATE_REPEAT:-3} s)"
grep -q 'SIGSTOP by dostal' "$LOG" && fail "dry-run chtel zastavit proces i pri SAFE_COMM=none: $(grep 'SIGSTOP' "$LOG")"
mem 1000 0 0;  wait_log 'HARD skoncil, SOFT trva: dostupne 1000 MB' || fail "hystereze HARD->SOFT nezalogovana"
grep -q 'RECOVER' "$LOG" && fail "RECOVER predcasne (uz pri SOFT)"
mem 5000 0 0;  wait_log 'RECOVER: dostupne 5000 MB' || fail "RECOVER nenastal"
sleep 0.5; [ -e "$ALERT" ] && fail "alert nesmazan po RECOVER"
# swap vetev: 8192 MB swapu, 7500 pouzito = 91 % -> HARD i pri dostatku RAM
mem 20000 8192 7500; wait_log 'HARD alert: dostupne 20000 MB, swap 91 %' || fail "HARD podle swapu nenastal"
mem 20000 8192 100;  wait_log 'RECOVER: dostupne 20000 MB' 4 || fail "RECOVER po swapu nenastal"
grep -Eqi 'division by zero|deleni nulou|syntax error' "$LOG" && fail "chyba v logu: $(grep -Ei 'division|syntax' "$LOG")"
kill -TERM $WPID; wait $WPID 2>/dev/null
wait_log 'watchdog konci' 3 || fail "cleanup trap po TERM nezalogovan"
[ -e "$ALERT" ] && fail "alert prezil TERM"
[ -e "$FAILF" ] && fail "escalate-fail soubor vznikl v dry-run"
kill -0 $WPID 2>/dev/null && fail "watchdog po TERM stale bezi"

echo "== C: realny STOP/CONT jen na vlastnim dummy =="
DN=rwselftest$$; cp /bin/sleep "$T/$DN"; "$T/$DN" 600 & DUMMY=$!
sleep 0.2; [ "$(cat /proc/$DUMMY/comm)" = "${DN:0:15}" ] || fail "dummy comm=$(cat /proc/$DUMMY/comm)"
: > "$LOG"; mem 20000 0 0; rm -rf "$T/state"
env "${common[@]}" RAM_WATCHDOG_DRY_RUN=0 SAFE_COMM="${DN:0:15}" SAFE_EXE_DIRS=/nonexistent/ bash "$WD" & WPID=$!
wait_log ' start: ' || fail "start C"
mem 300 0 0; wait_log "SIGSTOP pid $DUMMY \\(" 4 || fail "dummy nedostal SIGSTOP: $(tail -3 "$LOG")"
sleep 0.3; st=$(awk '{print $3}' /proc/$DUMMY/stat); [ "$st" = T ] || fail "dummy neni ve stavu T (je $st)"
grep -qx "$DUMMY" "$T/state/stopped" || fail "pid dummy neni ve state souboru"
n=$(grep -c 'SIGSTOP pid' "$LOG"); [ "$n" -eq 1 ] || fail "SIGSTOP zalogovan ${n}x (ocekavano 1)"
grep -v "pid $DUMMY " "$LOG" | grep -q 'SIGSTOP pid' && fail "zastaven cizi proces! $(grep 'SIGSTOP pid' "$LOG")"
mem 1000 0 0; sleep 1.5; st=$(awk '{print $3}' /proc/$DUMMY/stat); [ "$st" = T ] || fail "hystereze: dummy probuzen uz pri SOFT"
mem 9000 0 0; wait_log "SIGCONT pid $DUMMY \\(" 4 || fail "dummy nedostal SIGCONT"
sleep 0.3; st=$(awk '{print $3}' /proc/$DUMMY/stat); [ "$st" = S ] || fail "dummy po CONT neni S (je $st)"
[ -s "$T/state/stopped" ] && fail "state soubor po RECOVER neprazdny"
# cleanup trap: zastav znovu, pak TERM watchdogu -> dummy musi byt probuzen
mem 300 0 0; wait_log "SIGSTOP pid $DUMMY \\(.*\n.*SIGSTOP pid $DUMMY" 1 >/dev/null 2>&1
sleep 2; st=$(awk '{print $3}' /proc/$DUMMY/stat); [ "$st" = T ] || fail "2. SIGSTOP neprobehl (stav $st)"
kill -TERM $WPID; wait $WPID 2>/dev/null; sleep 0.3
st=$(awk '{print $3}' /proc/$DUMMY/stat); [ "$st" = S ] || fail "cleanup trap neprobudil dummy (stav $st)"
kill $DUMMY 2>/dev/null

echo "== D: hlidac sam sebe / pid 1 =="
: > "$LOG"; mem 300 0 0; rm -rf "$T/state"
# SAFE_COMM=bash by chytil i sam watchdog (bash) - overit, ze $$ je vyloucen: dry-run, jen log
env "${common[@]}" RAM_WATCHDOG_DRY_RUN=1 SAFE_COMM="systemd init" SAFE_EXE_DIRS=/nonexistent/ bash "$WD" --once
grep -q 'SIGSTOP by dostal pid 1 ' "$LOG" && fail "pid 1 by byl zastaven"
grep -q 'HARD alert' "$LOG" || fail "--once nezalogoval HARD"

echo "== E: realna eskalace do vlastni docasne tmux session =="
# chyba 2026-09-02: `send-keys -t =nazev` (bez dvojtecky) hlasi "can't find pane" -> test bez dry-run
if command -v tmux >/dev/null; then
    TS=rwst$$; tmux new-session -d -s "$TS" -x 200 -y 20 'cat' && sleep 0.3
    : > "$LOG"; mem 300 0 0; rm -rf "$T/state" "$FAILF"
    env "${common[@]}" RAM_WATCHDOG_DRY_RUN=0 ESCALATE_AFTER=0 COORDINATOR_TMUX_SESSION="$TS" SAFE_COMM=none SAFE_EXE_DIRS=/nonexistent/ bash "$WD" --once
    grep -q "ESCALATE odeslano do tmux '$TS'" "$LOG" || fail "eskalace do tmux '$TS' selhala: $(grep ESCALATE "$LOG")"
    sleep 0.3; tmux capture-pane -p -t "=$TS:" | grep -q 'HARD RAM alert trva 0 s: dostupne 300 MB' || fail "zprava nedorazila do tmux pane: $(tmux capture-pane -p -t "=$TS:" | grep -v '^$' | head -3)"
    [ -e "$FAILF" ] && fail "escalate-fail soubor po uspesne eskalaci"
    tmux kill-session -t "=$TS"
    # neexistujici session -> fail soubor + log, zadny pad
    : > "$LOG"; rm -rf "$T/state"
    env "${common[@]}" RAM_WATCHDOG_DRY_RUN=0 ESCALATE_AFTER=0 SAFE_COMM=none SAFE_EXE_DIRS=/nonexistent/ bash "$WD" --once
    grep -q 'ESCALATE SELHAL' "$LOG" && [ -s "$FAILF" ] || fail "neuspesna eskalace neni hlasena (log/fail soubor)"
else
    echo "(tmux neni, E preskoceno)"
fi

[ $FAIL -eq 0 ] && { echo "SELFTEST OK ($T bude smazan)"; exit 0; }
echo "--- log ---"; cat "$LOG"; exit 1
