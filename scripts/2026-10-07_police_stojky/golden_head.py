#!/usr/bin/env python3
"""Zlaty otisk stolu PRED zavedenim horni police mezi zadnimi stojkami (bot8, 2026-10-07): pro mrizku konfiguraci (system x sirka x hloubka x police x panely x LED x vzpery x stredni opora)
ulozi kanonicky hash a otisk dilu (sha256 z part_id, polohy, otoceni, meritka zaokrouhlenych na 0,001 mm) + pocet problemu + cenovy vstup (entries_pro_cenu) do golden_head.json.
test_hpolice.py pak overi, ze s VYCHOZI volbou (bez horni police) je VSE beze zmeny (hash i otisk i cenove polozky).
Pouziti (nad API VE STAVU PRED zmenou; STUL_API_OVERRIDE = adresar api):  api/venv/bin/python3 scripts/2026-10-07_police_stojky/golden_head.py"""
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
    for system, sirka, police, pocet, opora in itertools.product((30, 35, 40, 45), (1280, 1500, 1600, 2100, 2800), (0, 1, 2), (0, 1, 2), ("auto", "noha", "ram")):
        yield dict(system=system, sirka=sirka, police=police, panely_pocet=pocet, stredni_opora=opora)
    for system, sirka, led, vzpery, rameno in itertools.product((30, 35, 40), (1400, 2000, 2600), (True, False), (False, True), (560, 900)):
        yield dict(system=system, sirka=sirka, led=led, vzpery=vzpery, led_rameno=rameno, police=1)
    for system, sirka, posun, vyska in itertools.product((30, 40), (1400, 1700, 2600), (0, 200), (800, 1073, 1400)):
        yield dict(system=system, sirka=sirka, panely_posun=posun, stojky_vyska=vyska, police=1)
    for system, hloubka in itertools.product((40, 45), (600, 1000, 1600, 2200)):
        yield dict(system=system, hloubka=hloubka, sirka=1500)
    yield dict(system=30, stojky=False)
    yield dict(system=35, panely=False, elektrozlab=False)
    yield dict(system=40, sirka=3000, hloubka=1200, police=2, panely_pocet=4)
    yield dict(system=41)
    yield dict(system=41, sirka=2600, hloubka=700)


def vypocti(navic=None, jen=None):
    """Otisky mrizky; `navic` = dalsi parametry generatoru pro vsechny konfigurace (napr. led_pocet), `jen` = mnozina klicu, ktere se maji pocitat."""
    out = {}
    for p in mrizka():
        klic = json.dumps(p, sort_keys=True)
        if jen is not None and klic not in jen:
            continue
        try:
            r = S.sestav_stul(**{**p, **(navic or {})})
        except S.StulChyba as e:
            out[klic] = {"chyba": str(e)}
            continue
        out[klic] = {"hash": G.kanonicky_hash(r["parametry"]), "otisk": otisk(r), "problemu": len(r["problemy"]), "dilu": len(r["dily"]),
                     "vypis": hashlib.sha256(json.dumps(S.vyrobni_vypis(r, {}), sort_keys=True, default=str).encode()).hexdigest()[:16],
                     "entries": hashlib.sha256(json.dumps(S.entries_pro_cenu(r["dily"]), sort_keys=True).encode()).hexdigest()[:16]}
    return out


if __name__ == "__main__":
    g = vypocti()
    cil = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_head.json")
    json.dump(g, open(cil, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("zapsano", len(g), "konfiguraci do", cil, "| chyb:", sum(1 for v in g.values() if "chyba" in v))
