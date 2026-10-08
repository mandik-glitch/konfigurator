#!/usr/bin/env python3
"""Hermeticky test: lic_peers pri importu FBX = DEFINICE SPOJE (bot8, 2026-10-02).

Nalez bot10: stul #577 po nacteni hlasi 32 spoju, geometrie 26 (stejne #572;
"Regal 40A01 Doblo" #524 53 vs 35). Pricina: dimension_match_fbx._profiles_
touch() bral za dotyk uz prekryv >= -0,5 mm na zbylych osach, tedy i dotyk
HRANOU; scena kazdy par z lic_peers po nacteni zapocita. Definice (Robert
2026-08-31, PRAVIDLA_SPOJU.md): spoj jen kdyz se CELA plocha cela jednoho
profilu dotyka cela/steny druheho = prekryv na obou zbylych osach >= mensi
rozmer - 0,5 mm (stejny test jako scene.html autoRegisterTouchedProfileJoints).

Test: (1) rucne sestavene pripady se znamym vysledkem, (2) skutecne polohy
profilu stolu #572/#577 a #524 (scripts/2026-10-02_lic_peers_definice_fixtures
.json, vytazeno z DB jen ctenim): compute_lic_peers == definice (26/26), puvodni
kriterium by dalo 32/32.

Spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-02_lic_peers_definice_test.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1. Zadna DB (pymysql.connect zablokovan).
"""
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("UIMP_API_OVERRIDE") or os.path.join(REPO, "api")

import numpy as np  # noqa: E402
import pymysql  # noqa: E402

for _k, _v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306",
               "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
    os.environ[_k] = _v
ATTEMPTS = []


def _no_connect(*a, **kw):
    ATTEMPTS.append(1)
    raise RuntimeError("test: pripojeni k DB zakazano")


pymysql.connect = _no_connect
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    sys.path.insert(0, API)
    import app  # noqa: F401,E402 - jako v ostrem behu (app importuje dimension_match_fbx az na konci; opacne poradi = kruhovy import)
    import dimension_match_fbx as dmf  # noqa: E402
finally:
    threading.Thread.start = _orig

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


def box(x, y, z, sx, sy, sz):
    """Kvadr se stredem (x,y,z) a rozmery."""
    c, s = np.array([x, y, z], dtype=float), np.array([sx, sy, sz], dtype=float)
    return c - s / 2, c + s / 2


def touch(a, b):
    return dmf._profiles_touch(a[0], a[1], b[0], b[1])


# 1) rucni pripady -----------------------------------------------------------------
print("1) rucni pripady se znamym vysledkem")
leg = box(0, 570, 0, 30, 1140, 30)                       # noha 30x30x1140 (svisle, osa Y), x v [-15, 15]
check(touch(leg, box(0, 1155, 0, 30, 30, 30)), "konec na konec (kolinearni) = spoj")
check(touch(leg, box(385, 1155, 0, 740, 30, 30)) is False,
      "pricka 740 mm NAD nohou, dotyk jen hranou (prekryv 0 z 30 mm) = NENI spoj (puvodni kriterium: spoj)")
check(touch(leg, box(-385, 1155, 0, 740, 30, 30)) is False, "totez z druhe strany = NENI spoj")
check(touch(leg, box(385, 600, 0, 740, 30, 30)), "T-spoj: konec pricky celou plochou na steni nohy = spoj")
check(touch(leg, box(30, 570, 0, 30, 1140, 30)), "bok k boku (cela strana na celou stranu) = dotyk (scena ho pak vyradi jako bok-k-boku)")
check(touch(leg, box(0, 1158, 0, 30, 30, 30)) is False, "mezera 3 mm (nad toleranci 1,5 mm) = NENI spoj")
check(touch(leg, box(0, 1156, 0, 30, 30, 30)), "mezera 1 mm (v toleranci) = spoj")
check(touch(leg, box(7, 1155, 0, 30, 30, 30)) is False,
      "krytka posunuta o 7 mm (cela plocha kryta jen z 77 %) = NENI spoj (zadne castecne kryte celo)")
check(touch(leg, box(0, 1150, 0, 20, 20, 20)), "mensi profil (20x20) celem celou plochou na cele vetsiho = spoj")

# 2) skutecne polohy z DB ----------------------------------------------------------
print("2) skutecne polohy profilu stolu a regalu (fixture z DB)")
fx_path = os.path.join(REPO, "scripts", "2026-10-02_lic_peers_definice_fixtures.json")
with open(fx_path, encoding="utf-8") as fh:
    fx = json.load(fh)
for key, data in fx.items():
    boxes = [(np.array(b[0]), np.array(b[1])) for b in data["boxes"]]
    idx = data["idx"]
    meshes = [{"bb_min": b[0], "bb_max": b[1]} for b in boxes]
    peers = dmf.compute_lic_peers(meshes)
    got = sorted({(idx[i], idx[j]) for i, js in peers.items() for j in js if i < j})
    want = sorted(tuple(x) for x in data["definice_pary"])
    check(got == want, f"{key} ({data['nazev']}): compute_lic_peers = definice ({len(got)} vs {len(want)} paru)")
    check(len(data["lic_peers_ulozene"]) >= len(want), f"{key}: ulozene lic_peers ({len(data['lic_peers_ulozene'])}) nejsou mene nez definice")
for key, expect in (("tvar572", 26), ("tvar577", 26)):
    check(len(fx[key]["definice_pary"]) == expect, f"{key}: definice dava {expect} spoju (bot10: geometrie 26)")
    check(len(fx[key]["lic_peers_ulozene"]) == 32, f"{key}: v dobe nalezu (fixture z DB 2026-10-02) bylo ulozeno 32 paru (6 navic)")

check(not ATTEMPTS, f"zadny pokus o spojeni s DB ({len(ATTEMPTS)})")
if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
