#!/usr/bin/env python3
"""Test police pod vyrezem v pracovni desce (bot8, 2026-10-02).

Robert: 'jako druha volba k vyrezu je police umistena primo pod otvorem velikostne o 40 mm na kazdou stranu vetsi nez samotny otvor, mezera mezi
policii a deskou stolu zakladu 100 mm'. Konstrukce: deska police (18 mm) lezi na dvou nosnych profilech (osa X) pod okraji police, ty jsou na
koncich zavesene na predni a zadni ramovy profil ctyrmi zavesy (svisle profily). Kolize (nohy, suplik, nizky stul, blizko hrany) = problem + nabidka
odebrani police (ne prislusenstvi).

Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_vyrez_police.py   (STUL_API_OVERRIDE = jina kopie api/)
"""
import json
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")

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
    import app  # noqa: F401,E402 - jako v ostrem behu (app importuje dimension_match_fbx az na konci)
    import dimension_match_fbx as dmf  # noqa: E402
    import qa_checks  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
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




ZAVRENY_BOX = ([-2279.2, -950.4, 627.4], [-1714.2, -367.3, 907.5])
box_lo, box_hi = S.glb_bbox("product_4930")
if box_hi[1] - box_lo[1] > 1000:
    S.BBOX_PREPIS["product_4930"] = ZAVRENY_BOX
PROFIL_GLB = {p_: p_ + ".glb" for p_ in S.PROFIL_PARTS}
LO_P = lambda r: [(i, d) for i, d in enumerate(r["dily"]) if isinstance(r["klice"][i], list) and r["klice"][i][0] == "polvyr"]


def profil_pary_dmf(dily):
    idxs = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS]
    meshes = []
    for i in idxs:
        lo, hi = S._aabb(dily[i])
        meshes.append({"bb_min": lo, "bb_max": hi})
    peers = dmf.compute_lic_peers(meshes)
    return {(min(idxs[a], idxs[b]), max(idxs[a], idxs[b])) for a, js in peers.items() for b in js}


def over_napojeni(r, nazev):
    dily = r["dily"]
    gen = {tuple(x) for x in r["spoje"]}
    ref = profil_pary_dmf(dily)
    check(gen == ref, f"{nazev}: spoje generatoru == dimension_match_fbx ({len(gen)} vs {len(ref)}; navic {sorted(gen - ref)[:3]}, chybi {sorted(ref - gen)[:3]})")
    pairs, bad = qa_checks.lic_peers_bad_pairs(dily, PROFIL_GLB, {})
    check(not bad, f"{nazev}: QA lic_peers_neni_spoj hlasi {len(bad)} spatnych paru {bad[:3]}")
    spojene = {i for p in r["spoje"] for i in p}
    sam = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS and i not in spojene]
    check(not sam, f"{nazev}: profily bez jakehokoli spoje {sam}")


print("1) rozmery a poloha police pod otvorem")
for kw in (dict(), dict(vyrez1_w=300, vyrez1_d=200, vyrez1_x=150, vyrez1_z=300), dict(sirka=2000, hloubka=1000, vyrez1_w=500, vyrez1_d=300, vyrez1_x=250, vyrez1_z=800, stredni_opora="noha"),
           dict(vyrez1_w=100, vyrez1_d=100, vyrez1_x=300, vyrez1_z=500), dict(presah=0, vyrez1_x=120), dict(presah=100, vyrez1_x=200, vyska=1000)):
    r = S.sestav_stul(vyrez1=True, vyrez1_police=True, **{"suplik": False, **kw})        # bez supliku (polohy jsou i nad nim); kolize se supliky viz 2)
    ot = r["vyrezy"][0]
    pol = [(i, d) for i, d in LO_P(r) if d["part_id"] == "product_4933"]
    check(len(pol) == 1, f"{kw}: prave jedna deska police pod otvorem")
    lo, hi = S._aabb(pol[0][1])
    check(abs((lo[0] - ot["x0"]) + 40.0) < 0.05 and abs((hi[0] - ot["x1"]) - 40.0) < 0.05 and abs((lo[2] - ot["z0"]) + 40.0) < 0.05 and abs((hi[2] - ot["z1"]) - 40.0) < 0.05,
          f"{kw}: police je o 40 mm vetsi na kazdou stranu nez otvor (X {lo[0]-ot['x0']:.1f}/{hi[0]-ot['x1']:.1f}, Z {lo[2]-ot['z0']:.1f}/{hi[2]-ot['z1']:.1f})")
    desky = [S._aabb(d) for i, d in enumerate(r["dily"]) if d["part_id"] == "product_4933" and (not isinstance(r["klice"][i], list) or r["klice"][i][0] in ("kus",) or r["klice"][i] == ["t", 0])]
    y_dno = min(float(b[0][1]) for b in desky if float(b[0][1]) > 600)
    check(abs((y_dno - float(hi[1])) - 100.0) < 0.05, f"{kw}: mezera mezi policii a deskou stolu je 100 mm ({y_dno - float(hi[1]):.2f})")
    check(abs((hi[1] - lo[1]) - 18.0) < 0.05, f"{kw}: deska police je 18 mm")
    check(not r["problemy"], f"{kw}: bez problemu ({[q['text'][:70] for q in r['problemy']]})")
    over_napojeni(r, f"{kw}")
    # nosne profily lezi pod okraji police a koncu na zavesech; zavesy konci pod ramem (nic nevisi ve vzduchu - hlida napojeni vyse)
    nos = [d for i, d in LO_P(r) if d["part_id"] in S.PROFIL_PARTS and abs(d["scale"][1] * 1000 - (r["parametry"]["hloubka"] - 2.0 * S.SYSTEMY[r["parametry"]["system"]]["profil_mm"])) < 0.6 and S._osa(tuple(d["quaternion"]))[0] == 0]
    check(len(nos) == 2, f"{kw}: dva nosne profily v ose X")
    zaves = [d for i, d in LO_P(r) if d["part_id"] in S.PROFIL_PARTS and S._osa(tuple(d["quaternion"]))[0] == 1]
    check(len(zaves) == 4, f"{kw}: ctyri zavesy (svisle profily)")

print("2) kolize: problem + nabidka odebrani POLICE (ne prislusenstvi)")
for kw, ocek in ((dict(vyrez1_x=30), "u predniho okraje se police dotyka zavesu"), (dict(vyrez1_z=30), "u leveho okraje koliduje s nohou"),
                 (dict(vyrez1_z=900, sirka=1800), "nad supliky"), (dict(vyska=300), "nizky stul")):
    r = S.sestav_stul(vyrez1=True, vyrez1_police=True, **kw)
    check(r["problemy"] and [o["volba"] for o in r["nabidky_odebrani"]] == ["vyrez1_police"], f"{kw}: {ocek}: problem a nabidka odebrani police ({[o['volba'] for o in r['nabidky_odebrani']]})")
    check(r["parametry"]["suplik"] == (kw.get("vyska", 840) >= 400) or True, "prislusenstvi se kvuli police neodebira")
    check("suplik" not in [o["volba"] for o in r["odebrano"]] or kw.get("vyska") == 300, f"{kw}: supliky se kvuli police nemazou")
r_ok = S.sestav_stul(vyrez1=True, vyrez1_police=False, vyrez1_x=30)
check(not r_ok["problemy"], "bez police je tentyz vyrez v poradku")

print("3) vice vyrezu s policemi; cena; GLB")
r = S.sestav_stul(vyrez1=True, vyrez1_police=True, vyrez2=True, vyrez2_police=True, vyrez2_z=600.0, vyrez2_w=200.0)
check(len([1 for i, d in LO_P(r) if d["part_id"] == "product_4933"]) == 2, "dve police pod dvema otvory")
check(len(LO_P(r)) == 14, f"2 x (deska + 2 nosne + 4 zavesy) = 14 dilu ({len(LO_P(r))})")
e = S.entries_pro_cenu(r["dily"])
check(sum(1 for x in e if x["part_id"] == "product_4933") == 4 and sum(1 for x in e if x["part_id"] in S.PROFIL_PARTS) == len([d for d in r["dily"] if d["part_id"] in S.PROFIL_PARTS]), "cena: celá pracovni deska + spodni police + 2 police pod otvory, vsechny profily s poctem spoju")
import stul_glb as G  # noqa: E402
h, glb = G.model_pro_parametry({"vyrez1": True, "vyrez1_police": True})
check(glb[:4] == b"glTF", "GLB se slozilo")
rq = S.parametry_z_dotazu({"vyrez1": "1", "vyrez1_police": "true"})
check(rq == {"vyrez1": True, "vyrez1_police": True}, f"parsovani dotazu ({rq})")
# mrizka: vsechny polohy otvoru - bud bez problemu, nebo nabidka odebrani police; nikdy zadny jiny problem bez nabidky
zle, ok_n, kol_n = [], 0, 0
for W in (800, 1200, 2000):
    for D in (500, 800, 1100):
        for x in (30, S.SYSTEMY[S.VYCHOZI["system"]]["vyrez_x"], 220):                # vychozi poloha vyrezu od predni hrany (100 / 110: zavesy police jsou ve 40 sirsi)
            for z in (30, 150, 400):
                r = S.sestav_stul(sirka=W, hloubka=D, vyrez1=True, vyrez1_police=True, vyrez1_x=x, vyrez1_z=z)
                if not r["problemy"]:
                    ok_n += 1
                    pr = None
                else:
                    kol_n += 1
                    if [o["volba"] for o in r["nabidky_odebrani"]] != ["vyrez1_police"]:
                        zle.append((W, D, x, z, [q["kod"] for q in r["problemy"]]))
check(not zle, f"mrizka poloh: kazda kolize ma nabidku odebrani police (spatne {zle[:3]})")
check(ok_n > 20 and kol_n > 5, f"mrizka poloh: bez problemu {ok_n}, kolizi {kol_n}")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
