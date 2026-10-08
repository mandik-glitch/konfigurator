#!/usr/bin/env python3
"""
scripts/lock_watchdog.py (bot15, 2026-09-03, Robert pres bot3: "disciplina
zamku je porad slabina, tak na to nekdo vymysli reseni").

DETEKCE, ne prevence - nejde technicky zabranit jine Claude Code session
editovat guarded soubor bez zamku (zadny hook na to nema pristup), takze
misto toho tenhle skript kazdych ~90s (viz deploy/konfigurator-lock-
watchdog.timer) kontroluje 2 konkretni, dnes REALNE pozorovane vzory
selhani a hlasite na ne upozorni (AGENTS_LOG.md + bot_handover), aby si
toho vsimnul bot3 (koordinator DEPLOY_LOCK.json) co nejdriv:

(c) Zamek drzeny podezrele dlouho (`since` stary > LONG_HOLD_MINUTES) -
    typicky bot spadl/zapomnel uvolnit.
(e) Guarded soubory (webapp/, api/*.py) maji NECOMMITNUTE zmeny (jen
    SLEDOVANE soubory, ne chronicky velka hromada untracked assetu jako
    webapp/katalog/*.glb) a ZAROVEN zamek nikdo nedrzi, dlouhodobe
    (> DIRTY_SUSTAINED_MINUTES).

    DULEZITE (Robert/bot3 pripominka, 2026-09-03): kratke "spinave +
    zamek volny" okno je BEZNY a ZADOUCI stav behem pripravy prace
    (WORKFLOW.md: "priprav si vse PRED acquire, zamek ber jen kratce
    tesne pred commitem" - viz i pamet feedback_lock_hold_duration.md).
    Kontrola proto NENI "spinave + volny = alarm" (to by hlasilo
    poplach pri kazde normalni solo editaci), ale vyzaduje, aby tenhle
    stav TRVAL dlouho (DIRTY_SUSTAINED_MINUTES, vyrazne vic nez normalni
    priprava+commit cyklus) - cili chyta konkretne pripad "bot ma
    hotovy diff, ale zapomnel/nikdy neresil zamek" (dnesni incident:
    "bot14 mel hotovy diff v app.py bez zamku"), ne normalni pracovni
    rytmus.

Stav (prvni-videno cas, uz-alarmovano flag) se drzi v
qa-reports/lock_watchdog_state.json (gitignored, jako zbytek qa-reports/)
- bez nej by kazdy beh nemel pamet, jak dlouho podminka trva.

Pouziti: api/venv/bin/python3 scripts/lock_watchdog.py
"""
import datetime
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "qa-reports", "lock_watchdog_state.json")
LOCK_PATH = os.path.join(REPO_ROOT, "DEPLOY_LOCK.json")

LONG_HOLD_MINUTES = 25  # (c) drzeny zamek
DIRTY_SUSTAINED_MINUTES = 20  # (e) spinave guarded soubory bez zamku


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_iso(s):
    if not s:
        return None
    try:
        # "since" v DEPLOY_LOCK.json je z `date` / lock.sh, ISO 8601 s offsetem
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return None


def _load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def _read_lock():
    try:
        with open(LOCK_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None, None
    return data.get("held_by") or None, data.get("since") or None


def _guarded_dirty_files():
    """Jen SLEDOVANE (tracked) zmeny v guarded cestach - stejna logika
    jako scripts/restart_konfigurator.sh (viz jeho komentar k webapp/
    katalog/*.glb)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "webapp/", "api/*.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception as e:
        print(f"[lock_watchdog] git status selhalo: {e}", file=sys.stderr)
        return []
    return [line for line in out.splitlines() if line and not line.startswith("??")]


def _alarm(topic, body):
    print(f"[lock_watchdog] ALARM: {topic}")
    ts = _now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## lock-watchdog (automaticky, scripts/lock_watchdog.py) — {ts} — {topic}\n\n"
        f"{body}\n"
    )
    try:
        agents_log = os.path.join(REPO_ROOT, "AGENTS_LOG.md")
        with open(agents_log, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[lock_watchdog] zapis do AGENTS_LOG.md selhal: {e}", file=sys.stderr)

    try:
        subprocess.run(
            [
                os.path.join(REPO_ROOT, "api", "venv", "bin", "python"),
                os.path.join(REPO_ROOT, "scripts", "handover.py"),
                "add", "--bot", "system-watchdog", "--project", "konfigurator",
                "--topic", f"ZAMEK-ALARM: {topic}", "--status", "blocked",
                "--body", body,
            ],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        print(f"[lock_watchdog] zapis do bot_handover selhal: {e}", file=sys.stderr)


def check_long_held_lock(state):
    held_by, since = _read_lock()
    key = f"{held_by}|{since}"

    if not held_by:
        state["long_hold_alarmed_key"] = None
        return state

    since_dt = _parse_iso(since)
    if since_dt is None:
        return state

    age_minutes = (_now() - since_dt).total_seconds() / 60.0
    if age_minutes >= LONG_HOLD_MINUTES and state.get("long_hold_alarmed_key") != key:
        _alarm(
            f"zamek drzi '{held_by}' už {age_minutes:.0f} min (od {since})",
            f"DEPLOY_LOCK.json.held_by='{held_by}' je nezmeneno od {since} "
            f"(>{LONG_HOLD_MINUTES} min) - bezne drzeni je radove minuty, "
            f"tohle vypada na zapomenuty/spadly bot. Zkontroluj, jestli "
            f"'{held_by}' jeste realne pracuje; pokud ne, viz WORKFLOW.md "
            f"\"Co delat, kdyz najdes zamek drzeny dlouho/podezrele\".",
        )
        state["long_hold_alarmed_key"] = key
    return state


def check_dirty_without_lock(state):
    held_by, _since = _read_lock()
    dirty = _guarded_dirty_files()

    if held_by or not dirty:
        state["dirty_since"] = None
        state["dirty_alarmed"] = False
        return state

    if not state.get("dirty_since"):
        state["dirty_since"] = _now().isoformat()
        state["dirty_alarmed"] = False
        return state

    started = _parse_iso(state["dirty_since"])
    if started is None:
        state["dirty_since"] = _now().isoformat()
        return state

    age_minutes = (_now() - started).total_seconds() / 60.0
    if age_minutes >= DIRTY_SUSTAINED_MINUTES and not state.get("dirty_alarmed"):
        _alarm(
            f"necommitnute zmeny v guarded souborech bez zamku, trva {age_minutes:.0f} min",
            "Guarded soubory (webapp/, api/*.py) maji necommitnute zmeny "
            f"a DEPLOY_LOCK.json.held_by je null uz aspon {DIRTY_SUSTAINED_MINUTES} "
            "min souvisle - normalni priprava+commit cyklus by se do tohohle "
            "okna vesel, tohle vypada na zapomenuty/opusteny rozdelany diff "
            "(nebo skutecnou kolizi, kterou nikdo nedokoncil zamkem).\n"
            "Zmenene soubory:\n" + "\n".join(dirty),
        )
        state["dirty_alarmed"] = True
    return state


def main():
    state = _load_state()
    state = check_long_held_lock(state)
    state = check_dirty_without_lock(state)
    _save_state(state)


if __name__ == "__main__":
    main()
