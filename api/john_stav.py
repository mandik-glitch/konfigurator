"""Admin > Prehledy > John: ZIVE jednotky john-* (bot16, 2026-10-06, Robert pres bot9: "chci Johnovu praci videt primo v adminu v nejakem panelu").

OpenAI bot John bezi jako systemd jednotky `john-*` (spousti je `systemd-run --unit=john-...`). Panel (webapp/admin/js/prehledy-john.js) cte
verejny soubor /nahled-john/prace.json, ktery John sam udrzuje, a TENHLE endpoint mu k tomu dava jedno, co soubor nezjisti: bezi John opravdu?
(Presne tuhle mezeru mela pamet "John skoncil a nikdo to nevedel": uloha v souboru rika Bezi, jednotka uz dava.)

GET /api/admin/john/stav ("prehledy_john"/"zobrazit") vraci jen ke CTENI:
  {"zkontrolovano": ISO, "bezi": [{"jednotka", "od" (ISO | null), "bezi_s" (sekundy | null)}], "selhaly": [{"jednotka"}], "chyba": null | "text"}
Zdroj: `systemctl list-units 'john-*'` + `systemctl show -p ActiveEnterTimestamp --timestamp=unix` (cas startu). Nic nespousti ani nezastavuje.
NEVRACI popis jednotky ani prikazovou radku (obsahuje cesty a parametry modelu). Jmena jednotek prochazi regexem (jen `john-...service|scope`),
do podprocesu nejde zadny vstup od uzivatele. Podprocesy dostavaji MINIMALNI prostredi: sdileny proces ma DB_PASSWORD z EnvironmentFile a
explicitni `env=` zabrani, aby ho zdedily (stejne jako api/deploy_runs.py). Vysledek se drzi 5 s v pameti (panel se obnovuje kazdych 30 s,
oken muze byt vic).
"""
import datetime
import re
import subprocess
import time

from flask import jsonify

from app import app, require_permission

_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
_JEDNOTKA = re.compile(r"^john-[A-Za-z0-9_.@:-]{1,120}\.(?:service|scope)$")
_CACHE_S = 5
_cache = {"t": 0.0, "data": None}


def _run(cmd, timeout=6):
    """stdout (str) nebo None, kdyz se prikaz nepodarilo spustit / vyprsel cas."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_ENV).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None


def _cas_startu(jednotka):
    """epoch startu jednotky (systemctl show --timestamp=unix vraci '@1791301992') nebo None."""
    out = _run(["systemctl", "show", jednotka, "-p", "ActiveEnterTimestamp", "--value", "--timestamp=unix"])
    m = re.match(r"^@(\d{9,11})\s*$", out or "")
    return int(m.group(1)) if m else None


def _parsuj(vystup):
    """list-units radky: UNIT LOAD ACTIVE SUB DESCRIPTION... -> (bezi, selhaly) jmen jednotek."""
    bezi, selhaly = [], []
    for radek in (vystup or "").splitlines():
        cast = radek.split(None, 4)
        if len(cast) < 4 or not _JEDNOTKA.match(cast[0]):
            continue
        jednotka, aktivni = cast[0], cast[2]
        if aktivni in ("active", "activating", "reloading"):
            bezi.append(jednotka)
        elif aktivni == "failed":
            selhaly.append(jednotka)
    return sorted(set(bezi)), sorted(set(selhaly))


def _sestav_stav():
    ted = time.time()
    out = _run(["systemctl", "list-units", "john-*", "--all", "--no-legend", "--no-pager", "--plain", "--full"])
    odpoved = {"zkontrolovano": datetime.datetime.fromtimestamp(ted).astimezone().isoformat(timespec="seconds"), "bezi": [], "selhaly": [], "chyba": None}
    if out is None:
        odpoved["chyba"] = "systemctl se nepodarilo spustit"
        return odpoved
    bezi, selhaly = _parsuj(out)
    for j in bezi[:20]:
        od = _cas_startu(j)
        odpoved["bezi"].append({
            "jednotka": j,
            "od": datetime.datetime.fromtimestamp(od).astimezone().isoformat(timespec="seconds") if od else None,
            "bezi_s": max(0, int(ted - od)) if od else None,
        })
    odpoved["selhaly"] = [{"jednotka": j} for j in selhaly[:20]]
    return odpoved


@app.get("/api/admin/john/stav")
@require_permission("prehledy_john", "zobrazit")
def admin_john_stav():
    now = time.time()
    if _cache["data"] is None or now - _cache["t"] > _CACHE_S:
        _cache["data"] = _sestav_stav()
        _cache["t"] = now
    resp = jsonify(_cache["data"])
    resp.headers["Cache-Control"] = "no-store"
    return resp
