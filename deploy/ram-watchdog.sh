#!/bin/bash
# ram-watchdog.sh - VPS-wide hlidac RAM (zadani: SERVER_RAM_WATCHDOG.md).
#
# Kazdych INTERVAL s cte /proc/meminfo (= to, co ukazuje `free -m`):
#   SOFT     dostupna RAM < SOFT_MB            -> zapise ALERT_FILE (boti si ho
#            ctou PRED spustenim narocne paralelni prace).
#   HARD     dostupna RAM < HARD_MB NEBO swap vyuzity >= SWAP_PCT %
#            -> navic SIGSTOP (ne kill, jde vratit) procesum z BEZPECNEHO
#            SEZNAMU - vyhradne podle presneho jmena binarky (/proc/PID/comm)
#            nebo cesty binarky (/proc/PID/exe), NIKDY podle textu prikazove
#            radky (2026-08-18: volny vzor chytil i `grep ffmpeg soubor.md`).
#   ESCALATE HARD trva >= ESCALATE_AFTER s i po pozastaveni seznamu -> zprava
#            do tmux session koordinatora (COORDINATOR_TMUX_SESSION, vychozi
#            bot3 - incident 2026-08-23: spatny vychozi nazev session = 18 h
#            tichy HARD alert; proto se selhani eskalace NAVIC hlasi pres
#            `logger -p user.crit`, do ESCALATE_FAIL_FILE a opakuje se kazdych
#            ESCALATE_REPEAT s, dokud HARD trva).
#   RECOVER  dostupna RAM >= SOFT_MB -> SIGCONT vsem, ktere jsme pozastavili,
#            smaze ALERT_FILE. Mezi HARD a SOFT (hystereze) zustavaji stat.
#
# Zamerne se NEDOTYKA zivych sluzeb (gunicorn/nginx/mysql/redis/sshd/systemd)
# ani `claude` procesu botu - pozastaveni vlastniho claude by session jen
# zamrazilo. Server bez swapu: SwapTotal 0 -> swap 0 %, zadne deleni nulou.
#
# INSTALACE (z repa /opt/konfigurator, jako root):
#   install -m 755 deploy/ram-watchdog.sh        /usr/local/sbin/ram-watchdog.sh
#   install -m 644 deploy/ram-watchdog.service   /etc/systemd/system/ram-watchdog.service
#   install -m 644 deploy/ram-watchdog.logrotate /etc/logrotate.d/ram-watchdog
#   systemctl daemon-reload && systemctl enable --now ram-watchdog.service
#   systemctl status ram-watchdog.service; tail -f /var/log/ram-watchdog.log
# Zmena koordinatora: /etc/default/ram-watchdog -> COORDINATOR_TMUX_SESSION=...
# a `systemctl restart ram-watchdog` (viz incident vyse).
#
# TEST BEZ DOTYKU ZIVYCH PROCESU: deploy/ram-watchdog-selftest.sh (dry-run +
# simulovane hodnoty pameti), rucne napr.:
#   RAM_WATCHDOG_DRY_RUN=1 RAM_WATCHDOG_FAKE_MEM="400 0 0" STATE_DIR=/tmp/rw \
#   LOG_FILE=/tmp/rw/log ALERT_FILE=/tmp/rw/alert ram-watchdog.sh --once
#   (FAKE_MEM = "dostupne_MB swap_total_MB swap_pouzity_MB"; RAM_WATCHDOG_FAKE_MEM_FILE
#   = soubor se stejnym obsahem cteny kazdou iteraci; SAFE_COMM/SAFE_EXE_DIRS lze
#   pro test zuzit na vlastni atrapu procesu, aby se nesahlo na nic ziveho)
set -u

# --- konfigurace (prepsatelna pres /etc/default/ram-watchdog nebo prostredi) ---
[ -r /etc/default/ram-watchdog ] && . /etc/default/ram-watchdog
INTERVAL=${INTERVAL:-10}
SOFT_MB=${SOFT_MB:-1500}
HARD_MB=${HARD_MB:-500}
SWAP_PCT=${SWAP_PCT:-90}
ESCALATE_AFTER=${ESCALATE_AFTER:-30}
ESCALATE_REPEAT=${ESCALATE_REPEAT:-600}
HEARTBEAT_EVERY=${HEARTBEAT_EVERY:-3600}
COORDINATOR_TMUX_SESSION=${COORDINATOR_TMUX_SESSION:-bot3}
ALERT_FILE=${ALERT_FILE:-/run/ram-watchdog-alert}
ESCALATE_FAIL_FILE=${ESCALATE_FAIL_FILE:-/run/ram-watchdog-escalate-failed}
STATE_DIR=${STATE_DIR:-/run/ram-watchdog}
LOG_FILE=${LOG_FILE:-/var/log/ram-watchdog.log}
DRY_RUN=${RAM_WATCHDOG_DRY_RUN:-0}
FAKE_MEM=${RAM_WATCHDOG_FAKE_MEM:-}
FAKE_MEM_FILE=${RAM_WATCHDOG_FAKE_MEM_FILE:-}   # totez, ale cte se kazdou iteraci (selftest meni hodnoty za behu)
# bezpecny seznam: presna jmena binarek (comm / basename exe) ...
SAFE_COMM=${SAFE_COMM:-"yt-dlp ffmpeg ffmpeg-linux"}
# ... a adresare, pod kterymi lezi binarka (Playwright prohlizece)
SAFE_EXE_DIRS=${SAFE_EXE_DIRS:-"/ms-playwright/"}

STOPPED_FILE="$STATE_DIR/stopped"   # PIDy, ktere jsme pozastavili MY (prezije restart watchdogu)
ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1

mkdir -p "$STATE_DIR" "$(dirname "$LOG_FILE")" 2>/dev/null
touch "$STOPPED_FILE" 2>/dev/null

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

# --- pamet: "avail_mb swap_total_mb swap_used_mb" ---
read_mem() {
    if [ -n "$FAKE_MEM_FILE" ] && [ -r "$FAKE_MEM_FILE" ]; then
        cat "$FAKE_MEM_FILE"
        return
    fi
    if [ -n "$FAKE_MEM" ]; then
        echo "$FAKE_MEM"
        return
    fi
    awk '
        /^MemAvailable:/ {a=$2}
        /^SwapTotal:/    {st=$2}
        /^SwapFree:/     {sf=$2}
        END {printf "%d %d %d\n", a/1024, st/1024, (st-sf)/1024}
    ' /proc/meminfo
}

swap_pct() {  # $1 total $2 used -> cele procento, 0 kdyz neni swap
    if [ "${1:-0}" -le 0 ]; then echo 0; else echo $(( ${2:-0} * 100 / $1 )); fi
}

# --- procesy ---
proc_state() {  # stav procesu (R/S/D/T/Z...) ze /proc/PID/stat, prazdne kdyz neexistuje
    local stat
    stat=$(cat "/proc/$1/stat" 2>/dev/null) || return 1
    stat=${stat##*) }
    printf '%s' "${stat%% *}"
}

is_safe_pid() {  # 0 = proces smi byt pozastaven (presne jmeno/cesta binarky)
    local pid=$1 comm exe base d
    [ "$pid" = "$$" ] && return 1
    [ "$pid" -le 1 ] && return 1
    comm=$(cat "/proc/$pid/comm" 2>/dev/null) || return 1
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null || true)
    base=${exe##*/}; base=${base% (deleted)}
    for d in $SAFE_COMM; do
        [ "$comm" = "$d" ] && return 0
        [ -n "$base" ] && [ "$base" = "$d" ] && return 0
    done
    for d in $SAFE_EXE_DIRS; do
        case "$exe" in *"$d"*) return 0 ;; esac
    done
    return 1
}

list_safe_running() {  # PIDy z bezpecneho seznamu, ktere prave NEJSOU zastavene
    local p pid st
    for p in /proc/[0-9]*; do
        pid=${p#/proc/}
        is_safe_pid "$pid" || continue
        st=$(proc_state "$pid") || continue
        [ "$st" = "T" ] || [ "$st" = "t" ] && continue
        echo "$pid"
    done
}

describe_pid() {
    local comm exe
    comm=$(cat "/proc/$1/comm" 2>/dev/null || echo '?')
    exe=$(readlink "/proc/$1/exe" 2>/dev/null || echo '?')
    printf 'pid %s (%s, %s)' "$1" "$comm" "$exe"
}

stop_safe_procs() {
    local pid n=0
    while read -r pid; do
        [ -n "$pid" ] || continue
        grep -qx "$pid" "$STOPPED_FILE" 2>/dev/null && continue   # uz evidovan (dry-run ho fyzicky nezastavi)
        if [ "$DRY_RUN" = 1 ]; then
            log "DRY-RUN: SIGSTOP by dostal $(describe_pid "$pid")"
        elif kill -STOP "$pid" 2>/dev/null; then
            log "SIGSTOP $(describe_pid "$pid")"
        else
            log "SIGSTOP selhal: $(describe_pid "$pid")"
            continue
        fi
        echo "$pid" >> "$STOPPED_FILE"
        n=$((n + 1))
    done < <(list_safe_running)
    echo "$n"
}

resume_stopped_procs() {
    local pid n=0
    [ -s "$STOPPED_FILE" ] || return 0
    while read -r pid; do
        [ -n "$pid" ] || continue
        if [ ! -d "/proc/$pid" ]; then
            log "pozastaveny pid $pid uz neexistuje (skoncil sam)"
        elif [ "$DRY_RUN" = 1 ]; then
            log "DRY-RUN: SIGCONT by dostal $(describe_pid "$pid")"
        elif is_safe_pid "$pid" && kill -CONT "$pid" 2>/dev/null; then
            log "SIGCONT $(describe_pid "$pid")"
        else
            log "SIGCONT preskocen (pid $pid uz neni z bezpecneho seznamu - recyklovany PID?)"
        fi
        n=$((n + 1))
    done < "$STOPPED_FILE"
    : > "$STOPPED_FILE"
    return 0
}

# --- eskalace na koordinatora ---
escalate() {  # $1 = text zpravy
    local msg="$1"
    if [ "$DRY_RUN" = 1 ]; then
        log "DRY-RUN: ESCALATE do tmux '$COORDINATOR_TMUX_SESSION': $msg"
        return 0
    fi
    if tmux has-session -t "=$COORDINATOR_TMUX_SESSION" 2>/dev/null \
        && tmux send-keys -t "=$COORDINATOR_TMUX_SESSION:" -l "$msg" 2>/dev/null \
        && tmux send-keys -t "=$COORDINATOR_TMUX_SESSION:" Enter 2>/dev/null; then
        log "ESCALATE odeslano do tmux '$COORDINATOR_TMUX_SESSION'"
        rm -f "$ESCALATE_FAIL_FILE"
        return 0
    fi
    # incident 2026-08-23: tohle NESMI zustat potichu jen v logu
    log "ESCALATE SELHAL: tmux session '$COORDINATOR_TMUX_SESSION' neexistuje/nedostupna - oprav COORDINATOR_TMUX_SESSION v /etc/default/ram-watchdog"
    logger -p user.crit -t ram-watchdog "ESCALATE selhal: tmux session '$COORDINATOR_TMUX_SESSION' nedostupna; $msg" 2>/dev/null
    printf '%s tmux session %s nedostupna\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$COORDINATOR_TMUX_SESSION" > "$ESCALATE_FAIL_FILE" 2>/dev/null
    return 1
}

# --- ukonceni: nikdy nenechat procesy viset v SIGSTOP ---
cleanup() {
    log "watchdog konci (signal) - probouzim pozastavene procesy"
    resume_stopped_procs
    rm -f "$ALERT_FILE"
    exit 0
}
trap cleanup TERM INT HUP

# --- hlavni smycka ---
level=normal          # normal | soft | hard
hard_since=0
last_escalate=0
last_heartbeat=$(date +%s)
log "start: INTERVAL=${INTERVAL}s SOFT<${SOFT_MB}MB HARD<${HARD_MB}MB|swap>=${SWAP_PCT}% ESCALATE>=${ESCALATE_AFTER}s -> tmux '${COORDINATOR_TMUX_SESSION}' dry_run=${DRY_RUN}${FAKE_MEM:+ FAKE_MEM='$FAKE_MEM'}"
# po restartu watchdogu: kdyz je RAM v poradku, pusť, co zustalo stat z minula
if [ -s "$STOPPED_FILE" ]; then
    log "po startu nalezeny drive pozastavene PIDy - kontrola pameti rozhodne"
fi

while :; do
    read -r avail swap_total swap_used <<< "$(read_mem)"
    avail=${avail:-0}; swap_total=${swap_total:-0}; swap_used=${swap_used:-0}
    spct=$(swap_pct "$swap_total" "$swap_used")
    now=$(date +%s)

    if [ "$avail" -lt "$HARD_MB" ] || [ "$spct" -ge "$SWAP_PCT" ]; then
        new=hard
    elif [ "$avail" -lt "$SOFT_MB" ]; then
        new=soft
    else
        new=normal
    fi

    case "$new" in
        hard)
            if [ "$level" != hard ]; then
                log "HARD alert: dostupne ${avail} MB, swap ${spct} % - pozastavuji bezpecny seznam"
                hard_since=$now
                last_escalate=0
            fi
            printf '%s HARD avail=%sMB swap=%s%%\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$avail" "$spct" > "$ALERT_FILE"
            n=$(stop_safe_procs)
            [ "$n" -gt 0 ] && log "pozastaveno procesu: $n"
            if [ $((now - hard_since)) -ge "$ESCALATE_AFTER" ] \
                && { [ "$last_escalate" -eq 0 ] || [ $((now - last_escalate)) -ge "$ESCALATE_REPEAT" ]; }; then
                n_stopped=$(grep -c . "$STOPPED_FILE" 2>/dev/null) || n_stopped=0   # grep -c vraci 1 pri 0 radcich, ale cislo vypise
                escalate "[ram-watchdog $(date '+%H:%M:%S')] HARD RAM alert trva $((now - hard_since)) s: dostupne ${avail} MB, swap ${spct} %, pozastaveno ${n_stopped:-0} procesu z bezpecneho seznamu - zastav/omez paralelni praci botu (log /var/log/ram-watchdog.log)"
                last_escalate=$now
            fi
            ;;
        soft)
            if [ "$level" = hard ]; then
                log "HARD skoncil, SOFT trva: dostupne ${avail} MB - pozastavene procesy zatim necham (hystereze do >= ${SOFT_MB} MB)"
            elif [ "$level" != soft ]; then
                log "SOFT alert: dostupne ${avail} MB (< ${SOFT_MB} MB)"
            fi
            printf '%s SOFT avail=%sMB swap=%s%%\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$avail" "$spct" > "$ALERT_FILE"
            ;;
        normal)
            if [ "$level" != normal ]; then
                log "RECOVER: dostupne ${avail} MB - probouzim pozastavene procesy, mazu alert"
            fi
            resume_stopped_procs
            rm -f "$ALERT_FILE"
            ;;
    esac
    level=$new

    if [ $((now - last_heartbeat)) -ge "$HEARTBEAT_EVERY" ]; then
        log "heartbeat: stav=${level} dostupne ${avail} MB swap ${spct} %"
        last_heartbeat=$now
    fi

    [ "$ONCE" = 1 ] && exit 0
    sleep "$INTERVAL" &
    wait $!   # sleep na pozadi + wait, aby trap TERM zabral okamzite
done
