#!/usr/bin/env python3
"""Zlaty otisk stolu s panely PRED zavedenim delky panelu (bot8, 2026-10-07): pro mrizku konfiguraci (system x sirka x police x pocet panelu x stredni opora) ulozi hash a otisk dilu
(sha256 z part_id, polohy, otoceni, meritka zaokrouhlenych na 0,001 mm) do golden_head.json. Test_panely_delky.py pak overi, ze s vychozi delkou panelu (1190) je VSE beze zmeny.
Pouziti: api/venv/bin/python3 scripts/2026-10-07_perfopanel/golden_head.py  (nad API VE STAVU PRED zmenou; STUL_API_OVERRIDE = adresar api)"""
import hashlib
import itertools
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
import pymysql  # noqa: E402
for _k, _v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306", "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
    os.environ[_k] = _v
pymysql.connect = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test: pripojeni k DB zakazano"))
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    sys.path.insert(0, API)
    import app  # noqa: F401,E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
finally:
    threading.Thread.start = _orig


def otisk(r):
    pol = [(d["part_id"], [round(float(x), 3) for x in d["position"]], [round(float(x), 4) for x in d["quaternion"]], [round(float(x), 5) for x in d["scale"]]) for d in r["dily"]]
    return hashlib.sha256(json.dumps(pol, sort_keys=True).encode()).hexdigest()[:20]


def mrizka():
    for system, sirka, police, pocet, opora in itertools.product((30, 35, 40), (1280, 1500, 1600, 2100, 2800), (0, 1, 2), (0, 1, 2, 3, 4), ("auto", "noha", "ram")):
        yield dict(system=system, sirka=sirka, police=police, panely_pocet=pocet, stredni_opora=opora)
    for system, sirka, posun, z in itertools.product((30, 40), (1400, 1700, 2600), (0, 200), (0, 7)):
        yield dict(system=system, sirka=sirka, panely_posun=posun, panely_z=z, police=1)
    yield dict(system=30, stojky=False)
    yield dict(system=35, panely=False)
    yield dict(system=40, sirka=3000, hloubka=1200, police=2, panely_pocet=4)


def vypocti():
    out = {}
    for p in mrizka():
        klic = json.dumps(p, sort_keys=True)
        r = S.sestav_stul(**p)
        out[klic] = {"hash": G.kanonicky_hash(r["parametry"]), "otisk": otisk(r), "panelu": int(r["parametry"]["panely_pocet"]) if r["parametry"]["panely"] else 0, "problemu": len(r["problemy"])}
    return out


if __name__ == "__main__":
    g = vypocti()
    cil = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_head.json")
    json.dump(g, open(cil, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("zapsano", len(g), "konfiguraci do", cil)
