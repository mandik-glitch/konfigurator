"""Spolecne pomucky testu 'LED 600 v generatoru stolu' (bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru"; karta #5359 LED600, GLB product_5359.glb = LED 1200 zkracena o 600 mm).

  * import generatoru z adresare `STUL_API_OVERRIDE` (kandidatni / zakladni strom ve scratchpadu), jinak z api/ v repu; DB se v generatorovych testech NEPOUZIVA (pymysql.connect zakazano, falesne
    prostredi); shop vrstva ma vlastni test (test_led_delka_shop.py, DB jen cte);
  * mrizka konfiguraci a otisk vysledku (zlaty otisk PRED zavedenim volby `led_delka`: golden_head.py -> golden_head.json).
"""
import hashlib
import itertools
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden_head.json")


def nacti_generator(hermeticky=True):
    """Importuje app + generator (S) a GLB (G). hermeticky=True: falesne prostredi a zakazane pripojeni k DB (testy bez DB); False: prostredi z EnvironmentFile (systemd-run)."""
    if hermeticky:
        import pymysql
        for k, v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306", "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
            os.environ[k] = v
        pymysql.connect = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("test: pripojeni k DB zakazano"))
    os.chdir(REPO)
    orig = threading.Thread.start
    threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else orig(self, *a, **k)
    try:
        sys.path.insert(0, API)
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        import app  # noqa: F401
        import stul_glb as G
        import stul_konfigurator as S
    finally:
        threading.Thread.start = orig
    S.nastav_pravidla({})                                   # ziva pravidla stolu (DB) test neovlivni
    return S, G


def otisk(r):
    """Otisk dilu (part_id, poloha, otoceni, meritko zaokrouhlene) - STEJNY vzorec jako golden_head prvnich generatorovych zmen."""
    pol = [(d["part_id"], [round(float(x), 3) for x in d["position"]], [round(float(x), 4) for x in d["quaternion"]], [round(float(x), 5) for x in d["scale"]]) for d in r["dily"]]
    return hashlib.sha256(json.dumps(pol, sort_keys=True).encode()).hexdigest()[:20]


def mrizka():
    """Konfigurace, na kterych se overuje, ze s vychozi delkou LED (1200) je VSE beze zmeny: system x sirka x led x svitidlo x rameno (+ vzpery, stojky, panely, stredni opora, police)."""
    for system, sirka, led, svetlo, rameno in itertools.product((30, 35, 40, 45), (500, 640, 900, 1100, 1199, 1200, 1280, 1500, 2000, 2446, 2447, 2600, 3000), (True, False), (True, False), (400, 560, 900)):
        if not led and (not svetlo or rameno != 560):
            continue
        yield dict(system=system, sirka=sirka, led=led, led_svetlo=svetlo, led_rameno=rameno)
    for system, sirka, vzpery, panely, opora, police in itertools.product((30, 40), (1280, 1700, 2300), (False, True), (True, False), ("auto", "ram"), (0, 1)):
        yield dict(system=system, sirka=sirka, vzpery=vzpery, panely=panely, stredni_opora=opora, police=police)
    yield dict(system=30, stojky=False)
    yield dict(system=35, stojky=False, led=True)
    yield dict(system=40, sirka=3000, hloubka=1200, police=2, led_rameno=1500)
    yield dict(system=41)
    yield dict(system=41, sirka=2400)


def vypocti(S, G, vstupy, **navic):
    out = {}
    for p in vstupy:
        klic = json.dumps(p, sort_keys=True)
        r = S.sestav_stul(**{**p, **navic})
        out[klic] = {"hash": G.kanonicky_hash(r["parametry"]), "otisk": otisk(r), "problemy": sorted(x.get("kod") for x in r["problemy"]), "odebrano": sorted(o["volba"] for o in r["odebrano"]),
                     "spoju": int(r["pocet_spoju"]), "led": int(sum(1 for d in r["dily"] if d["part_id"] == "product_4929"))}
    return out
