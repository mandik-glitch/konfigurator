"""Dashboard panel "Nasazeni serveru" (bot16, 2026-10-01, Robert pres bot3: "uz me nebavi delat restart").

GET /api/admin/deploy-runs ("dash_nasazeni"/"zobrazit") vraci jen ke CTENI:
  * kdy pujde kod ven: dalsi termin planovaneho nasazeni (0:00 a 12:30 Europe/Prague) a jestli je casovac zapnuty,
  * co ceka: commity do api/*.py mladsi nez start NEJSTARSIHIHO workeru (= kod bezi nejmene od ...). Pocita se
    z casu, ne ze zaznamu, takze to sedi i po rucnim restartu nebo padu workeru,
  * necommitnute zmeny v api/*.py (ty planovane nasazeni zablokuji),
  * posledni nasazeni a historie z tabulky deploy_runs (zapisuje ji scripts/nasazeni.py): vysledek, mereni
    (pauza obsluhy, selhane pozadavky, smoke), dukaz co se nasadilo,
  * upozorneni, ktera maji byt VIDET: posledni beh selhal/varoval, nasazeni se opakovane preskakuje, casovac neni
    zapnuty nebo dlouho nebezel. Zadny e-mail (WORKFLOW.md pravidlo 16) - jen tenhle panel.

Nezamenovat s GET /api/deploy-status v app.py ('deploy majak' ve scene - kdo prave drzi DEPLOY_LOCK).
Nic nespousti ani nerestartuje. Rucni nasazeni (vyjimka pro nalehavou opravu) je
`scripts/restart_konfigurator.sh --reload`; stejna data pro boty vypise `--stav`.

Podprocesy (git, ps, systemctl) dostavaji MINIMALNI prostredi: sdileny proces ma DB_PASSWORD z EnvironmentFile
a explicitni `env=` zabrani, aby ho zdedily (viz poznamka o subprocess env u api/vandr_scene_offers.py).
`git -c safe.directory=...`: repo patri rootovi a gunicorn bezi jako www-data.
"""
import datetime
import json
import os
import subprocess
import time
from zoneinfo import ZoneInfo

import pymysql
from flask import jsonify

from app import app, get_conn, require_permission

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUZBA = "konfigurator.service"
TIMER = "konfigurator-nasazeni.timer"
# Terminy musi sedet s deploy/konfigurator-nasazeni.timer a OKNA v scripts/nasazeni.py.
OKNA = ("00:00", "12:30")
TZ = ZoneInfo("Europe/Prague")
PATHSPEC_API = ":(glob)api/*.py"
PATHSPEC_JAZYKY = ":(glob)api/jazyky/*.json"   # jako v scripts/nasazeni.py: datove sady jazyku se nasazuji restartem
PATHSPECY_API = (PATHSPEC_API, PATHSPEC_JAZYKY)
_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
_CACHE_S = 15
_cache = {"t": 0.0, "data": None}


def _run(cmd, timeout=8):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=_ENV).stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _git(*args):
    # --no-optional-locks: `git status` jako www-data nesmi zkouset prepisovat index (patri rootovi)
    return _run(["git", "--no-optional-locks", "-c", "safe.directory=" + REPO, "-C", REPO] + list(args), 10)


def _kod_bezi_od():
    """(epoch startu nejstarsiho workeru | None, pocet workeru)."""
    try:
        master = int(_run(["systemctl", "show", SLUZBA, "-p", "MainPID", "--value"]).strip())
    except ValueError:
        master = 0
    master = master or os.getppid()          # tenhle proces je gunicorn worker, rodic = master
    et = [int(x) for x in _run(["ps", "-o", "etimes=", "--ppid", str(master)]).split() if x.isdigit()]
    return (time.time() - max(et), len(et)) if et else (None, 0)


def _iso(ts):
    return datetime.datetime.fromtimestamp(ts, TZ).isoformat()


def _ceka(od):
    res = []
    if od is None:
        return res
    for r in _git("log", "-n", "400", "--format=%h%x1f%ct%x1f%s", "--", *PATHSPECY_API).splitlines():
        p = r.split("\x1f", 2)
        if len(p) == 3 and p[1].isdigit() and int(p[1]) > od:
            res.append({"hash": p[0], "cas": _iso(int(p[1])), "predmet": p[2][:160]})
    return res


def _necommitnute():
    res = []
    for r in _git("status", "--porcelain", "--", *PATHSPECY_API).splitlines():
        if len(r) >= 4:
            res.append({"stav": r[:2].strip() or "?", "soubor": r[3:].strip().strip('"')})
    return res


def _casovac():
    v = dict(l.split("=", 1) for l in _run(["systemctl", "show", TIMER, "-p", "LoadState", "-p", "ActiveState",
                                             "-p", "UnitFileState"]).splitlines() if "=" in l)
    if v.get("LoadState") in (None, "not-found"):
        return "neni"
    return "zapnuty" if v.get("ActiveState") == "active" and v.get("UnitFileState") == "enabled" else "vypnuty"


def _dalsi_okno():
    n = datetime.datetime.now(TZ)
    kand = []
    for den in (0, 1):
        for hhmm in OKNA:
            h, m = map(int, hhmm.split(":"))
            d = (n + datetime.timedelta(days=den)).replace(hour=h, minute=m, second=0, microsecond=0)
            if d > n:
                kand.append(d)
    return min(kand).isoformat()


def _jak_json(text, vychozi):
    try:
        return json.loads(text) if text else vychozi
    except ValueError:
        return vychozi


def _behy(n=12):
    """None = tabulka jeste neexistuje (vznikne pri prvnim behu / migraci sql/2026-10-01_deploy_runs.sql)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, started_at, finished_at, trigger_type, status, reason, head_before, head_after, "
                        "commits_count, commits_json, detail_json, duration_s, requested_by "
                        "FROM deploy_runs ORDER BY id DESC LIMIT %s", (n,))
            rows = cur.fetchall()
    except pymysql.err.ProgrammingError as e:
        if e.args and e.args[0] == 1146:
            return None
        raise
    finally:
        conn.close()
    res = []
    for i, r in enumerate(rows):
        zaz = {
            "id": r["id"], "status": r["status"], "trigger": r["trigger_type"], "kdo": r["requested_by"],
            "zacatek": r["started_at"].replace(tzinfo=TZ).isoformat() if r["started_at"] else None,
            "konec": r["finished_at"].replace(tzinfo=TZ).isoformat() if r["finished_at"] else None,
            "commitu": r["commits_count"], "trvani_s": float(r["duration_s"]) if r["duration_s"] is not None else None,
            "duvod": (r["reason"] or "")[:600],
        }
        if i == 0:                       # podrobnosti jen u posledniho behu
            d = _jak_json(r["detail_json"], {})
            zaz["commity"] = _jak_json(r["commits_json"], [])[:40]
            zaz["detail"] = {k: d.get(k) for k in ("sonda", "smoke", "workery_pred", "workery_po", "workery_vznik_s",
                                                    "preflight_import_s", "cekani_s", "journal", "nginx_5xx",
                                                    "blokatory", "necommitnute_po") if k in d}
        res.append(zaz)
    return res


def _upozorneni(casovac, behy, ceka, necommitnute):
    u = []
    now = time.time()

    def stari_h(iso):
        return (now - datetime.datetime.fromisoformat(iso).timestamp()) / 3600 if iso else None

    if casovac != "zapnuty":
        u.append({"uroven": "varovani", "text": "Plánované nasazení ještě není zapnuté - kód se sám nenasazuje a "
                  "po každé změně je potřeba ruční reload. Zapnutí je jednorázový příkaz (viz TASKS.md)."
                  if casovac == "neni" else "Časovač plánovaného nasazení je nainstalovaný, ale vypnutý."})
    posledni = behy[0] if behy else None
    if posledni:
        if posledni["status"] == "selhalo":
            u.append({"uroven": "chyba", "text": "Poslední nasazení SELHALO: " + posledni["duvod"][:300]})
        elif posledni["status"] == "varovani":
            u.append({"uroven": "varovani", "text": "Poslední nasazení proběhlo s varováním: " + posledni["duvod"][:300]})
        elif posledni["status"] == "prerusen":
            u.append({"uroven": "chyba", "text": "Poslední nasazení bylo přerušeno (proces zanikl, aniž zapsal výsledek)."})
        elif posledni["status"] == "bezi" and (stari_h(posledni["zacatek"]) or 0) > 1:
            u.append({"uroven": "chyba", "text": "Nasazení běží (nebo visí) už přes hodinu."})
    plan = [b for b in (behy or []) if b["trigger"] == "plan" and b["status"] != "bezi"]
    preskoceno = 0
    for b in plan:
        if b["status"] != "preskoceno":
            break
        preskoceno += 1
    if preskoceno and ceka:
        u.append({"uroven": "varovani", "text": "Nasazení se přeskakuje už %d termínů za sebou, čeká %d commitů. Důvod: %s"
                  % (preskoceno, len(ceka), plan[0]["duvod"].splitlines()[0][:200])})
    if necommitnute and casovac == "zapnuty":
        u.append({"uroven": "info", "text": "V api/*.py leží necommitnuté změny (%s) - plánované nasazení je zablokuje, "
                  "dokud je jejich autor necommitne." % ", ".join(x["soubor"] for x in necommitnute[:4])})
    if casovac == "zapnuty" and plan:
        h = stari_h(plan[0]["zacatek"])
        if h is not None and h > 14:
            u.append({"uroven": "chyba", "text": "Časovač neběží? Poslední plánovaný běh byl před %.0f hodinami "
                      "(mají být 2 denně)." % h})
    return u


def _sestav_stav():
    od, workeru = _kod_bezi_od()
    casovac = _casovac()
    ceka = _ceka(od)
    necommitnute = _necommitnute()
    behy = _behy()
    return {
        "table_missing": behy is None,
        "ted": datetime.datetime.now(TZ).isoformat(),
        "kod_bezi_od": _iso(od) if od else None,
        "workeru": workeru,
        "okna": list(OKNA),
        "dalsi_okno": _dalsi_okno(),
        "casovac": casovac,
        "ceka": ceka[:60],
        "ceka_celkem": len(ceka),
        "necommitnute": necommitnute,
        "posledni": (behy or [None])[0],
        "behy": behy or [],
        "upozorneni": _upozorneni(casovac, behy or [], ceka, necommitnute),
    }


@app.get("/api/admin/deploy-runs")
@require_permission("dash_nasazeni", "zobrazit")
def admin_deploy_runs():
    now = time.time()
    if _cache["data"] is None or now - _cache["t"] > _CACHE_S:
        _cache["data"] = _sestav_stav()
        _cache["t"] = now
    return jsonify(_cache["data"])
