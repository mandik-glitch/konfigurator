#!/usr/bin/env python3
"""Test DELKY LED SVITIDLA v generatoru stolu (bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru"; karta #5359 LED600, GLB product_5359.glb = LED 1200 zkracena o 600 mm).
Hermeticky (DB se nepouziva): generator + GLB + data pro pocitadlo luxu. Verejne API ma vlastni test (test_led_delka_shop.py).

Hlida: model v katalogu (delka 647,001 vs 1247,001, STEJNY stred a prurez, souradnice), konstanty a vstup (`led_delka` 1200 | 600, jine = StulChyba), ZLATY OTISK 465 konfiguraci proti stavu PRED
zavedenim volby (vychozi delka = VSE beze zmeny: hash, dily, problemy, odebrane prepinace), geometrii nezavisle meranou z VRCHOLU meshe (pocet svitidel max(1, floor((sirka + 47) / telo)), roztec
telesa, stred skupiny = stred pricneho profilu nad LED, stejna hloubka a vyska jako u 1200, prusah <= 48 mm, svitidla se neprekryvaji ani nezanoruji do jinych dilu), hranice pri kterych se LED
odebere (1200 od sirky 1200, 600 od sirky 600), hash (`led_delka` jen u svitidla jine nez 1200), `led_info.typy` proti skutecnemu chovani, 3D menu "Zvolit LED N mm" (a ze se nastaveni da pouzit),
model GLB (material led, rozmer svitidel), data pro pocitadlo luxu (typ led_600, svitici cara 600 mm vystredena v telese 647 mm), degradaci pri chybejicim GLB, SSE (led_delka ignorovana).
Spusteni:  api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka.py     (STUL_API_OVERRIDE=<adresar api> = kandidat; golden_head.json = stav pred zmenou)"""
import itertools
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_osvetleni  # noqa: E402

# Od 2026-10-08 je pocet svitidel LED RUCNI (`led_pocet`, vychozi 1; svitidla se uz nepridavaji sama podle sirky stolu). Tento test overuje rozlozeni svitidel podle sirky stolu (DRIVEJSI automaticky
# pocet = nejvic svitidel, co se vejde), proto jim zadava `led_pocet` na nejvic (generator ho orizne na pocet, ktery se vejde). Hash sirokych stolu se zmenil (nese klic poctu) - viz sekce C.
if hasattr(S, "LED_MAX"):
    _sestav_orig = S.sestav_stul
    S.sestav_stul = lambda **kw: _sestav_orig(**{"led_pocet": S.LED_MAX, **kw})
import trimesh  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if os.environ.get("TEST_STOP_PRVNI"):                  # rychly beh pro mutace: prvni selhani konci (mutace.py)
            sys.exit(1)


L1200, L600 = "product_4929", "product_5359"
TELO = {1200: 1247.0, 600: 647.0}                    # delka tělesa svitidla vc. koncovek (mm) - NEZAVISLE zadano z GLB (1247,001 / 647,001)
PREVIS = 47.0
KAT = os.path.join(C.REPO, "webapp", "katalog")


def led_dily(r):
    return [d for d in r["dily"] if d["part_id"] in (L1200, L600)]


def z_rozsah(d):
    """Rozsah svitidla v Z (osa sirky stolu) z VRCHOLU meshe (ne z accessoru) - nezavisle na generatoru."""
    P, _, _ = G._transformuj(d["part_id"], d)
    return float(P[:, 2].min()), float(P[:, 2].max()), P


def stred_pricne(r):
    """Stred v Z pricneho profilu nad LED (klic ("t", ZRAIL_TOP)): skupina svitidel je na nej vystredena."""
    for d, k in zip(r["dily"], r["klice"]):
        if tuple(k) == ("t", S.ZRAIL_TOP):
            lo, hi = S._aabb(d)
            return float((lo[2] + hi[2]) / 2.0), float(hi[2] - lo[2])
    return None, None


def pocet_pri(sirka, d):
    return max(1, int((sirka + PREVIS) // TELO[d]))


# ---------------------------------------------------------------------------------------------------------------------
print("A) model LED 600 v katalogu (GLB)")
for pid, delka in ((L1200, 1247.001), (L600, 647.001)):
    cesta = os.path.join(KAT, pid + ".glb")
    check(os.path.isfile(cesta), f"{pid}: GLB v katalogu existuje")
lo1, hi1 = S.glb_bbox(L1200)
lo6, hi6 = S.glb_bbox(L600)
check(abs((hi1[0] - lo1[0]) - 1247.001) < 0.01 and abs((hi6[0] - lo6[0]) - 647.001) < 0.01, f"delky z GLB: {hi1[0] - lo1[0]:.3f} / {hi6[0] - lo6[0]:.3f} (cekano 1247,001 / 647,001)")
check(np.allclose((lo1 + hi1) / 2, (lo6 + hi6) / 2, atol=0.01), f"STEJNY stred bboxu: {(lo1 + hi1) / 2} vs {(lo6 + hi6) / 2}")
check(np.allclose((hi1 - lo1)[1:], (hi6 - lo6)[1:], atol=0.01), "stejny prurez (Y, Z)")
m1 = trimesh.load(os.path.join(KAT, L1200 + ".glb"), force="scene")
m6 = trimesh.load(os.path.join(KAT, L600 + ".glb"), force="scene")
g1, g6 = list(m1.geometry.values())[0], list(m6.geometry.values())[0]
check(len(m6.geometry) == 1 and abs((g1.bounds[1][0] - g1.bounds[0][0]) - (g6.bounds[1][0] - g6.bounds[0][0]) - 600.0) < 0.01, "mesh LED 600 je o PRESNE 600 mm kratsi nez LED 1200 (z vrcholu)")
check(np.isfinite(g6.vertices).all() and np.isfinite(g6.vertex_normals).all() and len(g6.faces) > 1000, "mesh LED 600: konecne souradnice, normaly, dost trojuhelniku")
check(S.led_telo_dilu(L1200) == S.LED_SIRKA == 1247.0 and S.led_telo_dilu(L600) == 647.0, f"led_telo_dilu: 1247 / 647 ({S.led_telo_dilu(L1200)}, {S.led_telo_dilu(L600)})")
for system in (30, 35, 40, 45):
    with S._v_systemu(system):
        sab = S.sablona()
        q = sab[S.LED]["quaternion"]
        zr = S._aabb({"part_id": L1200, "quaternion": q, "scale": [1, 1, 1], "position": [0, 0, 0]})
        check(abs((zr[1][2] - zr[0][2]) - (hi1[0] - lo1[0])) < 0.01, f"system {system}: delka svitidla ve svete (osa Z) = lokalni X z GLB (otoceni sablony)")

print("B) konstanty a vstup")
check(S.LED_TYPY == {1200: L1200, 600: L600} and S.LED_DELKY == (600, 1200) and S.LED_DELKA_VYCHOZI == 1200 and S.LED_PARTY == frozenset({L1200, L600}), "LED_TYPY / LED_DELKY / vychozi 1200 / LED_PARTY")
check(S.VYCHOZI["led_delka"] == 1200.0 and S._norm_parametry({})["led_delka"] == 1200.0 and S._norm_parametry({"led_delka": 600})["led_delka"] == 600.0, "vychozi hodnota parametru led_delka = 1200")
for spatna in (0, 900, 599, 601, 1201, 600.5, True, False, "600", None, float("nan"), float("inf"), -600, 1e9):
    for extra in ({}, {"led": False}, {"led_svetlo": False}, {"stojky": False}, {"sirka": 500}):              # vstup se kontroluje i tam, kde svitidlo na stole neni
        try:
            S.sestav_stul(led_delka=spatna, **extra)
            check(False, f"led_delka={spatna!r} {extra} musi byt odmitnuta")
        except S.StulChyba as e:
            check(e.kod == "mimo_rozsah", f"led_delka={spatna!r} {extra}: StulChyba mimo_rozsah ({e.kod})")
check(S.sestav_stul(led_delka=600.0)["parametry"]["led_delka"] == 600.0 and S.sestav_stul(led_delka=1200)["parametry"]["led_delka"] == 1200.0, "led_delka 600.0 / 1200 projdou")
check(S._NAZVY[L600] == "LED osvětlení 600 mm" and S._NAZVY[L1200] == "LED osvětlení", "nazvy dilu: 4929 beze zmeny, 5359 s delkou")
check(S.PREPINAC_DILU[L1200] == "led" and S.PREPINAC_DILU[L600] == "led", "PREPINAC_DILU: oba dily = prepinac led")

print("C) vychozi delka = VSE BEZE ZMENY (zlaty otisk konfiguraci pred zavedenim volby)")
g0 = json.load(open(C.GOLDEN, encoding="utf-8"))
g1_ = C.vypocti(S, G, C.mrizka())
bez_hashe = lambda k, z: {x: y for x, y in z.items() if not (x == "hash" and g0[k]["led"] >= 2)}          # noqa: E731 - hash stolu, kde drive vznikalo vic svitidel automaticky, se zmenil (nese klic poctu)
rozdil = [k for k in g0 if bez_hashe(k, g0[k]) != bez_hashe(k, g1_.get(k, {}))]
check(len(g0) >= 400 and not rozdil and set(g0) == set(g1_), f"zlaty otisk {len(g0)} konfiguraci: rozdilnych {len(rozdil)} {rozdil[:2]}")
g1200 = C.vypocti(S, G, C.mrizka(), led_delka=1200)
check(g1200 == g1_, "vypocet s explicitni led_delka=1200 = vypocet bez ni (vsech 465 konfiguraci)")
g_led_off = C.vypocti(S, G, [{"led": False, "sirka": 1500}, {"sirka": 1500, "led_svetlo": False}, {"sirka": 1500, "stojky": False}, {"system": 41}])
g_led_off6 = C.vypocti(S, G, [{"led": False, "sirka": 1500}, {"sirka": 1500, "led_svetlo": False}, {"sirka": 1500, "stojky": False}, {"system": 41}], led_delka=600)
check(g_led_off == g_led_off6, "bez svitidla (led vypnuto / svitidlo odebrano / bez stojek / SSE) je led_delka=600 bez vlivu: stejny hash i dily")

print("D) geometrie nezavisle z vrcholu meshe: pocet, roztec, vystredeni, prusah, prekryvy")
SIRKY = [500, 599, 600, 610, 640, 647, 700, 900, 1000, 1199, 1200, 1280, 1293, 1294, 1500, 1940, 1941, 1999, 2000, 2446, 2447, 2600, 2940, 3000]
ref, ofset = {}, {}
for system in (30, 35, 40, 45):
    r = S.sestav_stul(system=system, sirka=1500)
    d0 = led_dily(r)[0]
    ref[system] = (float(d0["position"][0]), float(d0["position"][1]), tuple(d0["quaternion"]), tuple(d0["scale"]))
    a_, b_ = min(z_rozsah(d)[0] for d in led_dily(r)), max(z_rozsah(d)[1] for d in led_dily(r))
    ofset[system] = (a_ + b_) / 2.0 - stred_pricne(r)[0]                  # stred skupiny 1200 vuci pricnemu profilu nad LED (30 / 35 / 40: 0; system 45 ma v sablone ofset)
check(max(ofset.values()) - min(ofset.values()) < 0.05 and abs(ofset[30]) > 1.0, f"u 1200 je skupina vuci pricnemu profilu posunuta stejne ve vsech systemech (sablona; presah tělesa na jednu stranu): {ofset}")
nevejde1200, nevejde600, zkontrolovano = 0, 0, 0
for system, sirka, rameno in itertools.product((30, 35, 40, 45), SIRKY, (300, 560, 1000)):
    zakl = dict(system=system, sirka=sirka, led_rameno=rameno)
    r12, r6 = S.sestav_stul(**zakl), S.sestav_stul(**zakl, led_delka=600)
    l12, l6 = led_dily(r12), led_dily(r6)
    check(bool(l12) == (sirka >= 1200) and r12["parametry"]["led"] == bool(l12), f"{system}/{sirka}/{rameno}: LED 1200 je na stole prave od sirky 1200 (je: {len(l12)} ks)")
    check(bool(l6) == (sirka >= 600) and r6["parametry"]["led"] == bool(l6), f"{system}/{sirka}/{rameno}: LED 600 je na stole prave od sirky 600 (je: {len(l6)} ks)")
    nevejde1200 += not l12
    nevejde600 += not l6
    if not l6:
        check("led" in [o["volba"] for o in r6["odebrano"]] and r6["parametry"]["led_delka"] == 1200.0, f"{system}/{sirka}/{rameno}: nevejde-li se LED 600, prepinac led se automaticky odebere a delka se vrati na 1200")
        continue
    zkontrolovano += 1
    n = pocet_pri(sirka, 600)
    check(len(l6) == n and all(d["part_id"] == L600 for d in l6), f"{system}/{sirka}/{rameno}: pocet svitidel 600 = {n} (je {len(l6)}), vsechna dil product_5359")
    rozsahy = sorted((z_rozsah(d)[:2] for d in l6))
    delky = [b - a for a, b in rozsahy]
    check(all(abs(x - 647.001) < 0.02 for x in delky), f"{system}/{sirka}/{rameno}: kazde svitidlo je z vrcholu meshe dlouhe 647,001 mm ({[round(x, 3) for x in delky]})")
    mezery = [rozsahy[i + 1][0] - rozsahy[i][1] for i in range(len(rozsahy) - 1)]
    check(all(-0.01 <= m <= 0.01 for m in mezery), f"{system}/{sirka}/{rameno}: svitidla na sebe navazuji (koncovka na koncovku): mezery {[round(m, 4) for m in mezery]}")
    z0, z1 = rozsahy[0][0], rozsahy[-1][1]
    zs, delka_pr = stred_pricne(r6)
    check(zs is not None and abs((z0 + z1) / 2.0 - zs - ofset[system]) < 0.01, f"{system}/{sirka}/{rameno}: skupina svitidel 600 je vuci pricnemu profilu nad LED vystredena stejne jako u 1200 ({(z0 + z1) / 2.0 - zs:.3f} vs {ofset[system]:.3f})")
    check(abs(delka_pr - sirka) < 0.01, f"{system}/{sirka}/{rameno}: pricny profil nad LED ma delku sirky stolu ({delka_pr})")
    presah = (z1 - z0) - sirka
    check(presah <= PREVIS + 1.0 + 1e-6, f"{system}/{sirka}/{rameno}: prusah svitidel pres stul {presah:.3f} mm <= 48")
    check(not r6["problemy"] or [p["kod"] for p in r6["problemy"]] == [p["kod"] for p in r12["problemy"]], f"{system}/{sirka}/{rameno}: LED 600 nezpusobi zadny novy problem ({[p['kod'] for p in r6['problemy']]})")
    # hloubka (X) a vyska (Y) svitidla: stejne jako u 1200 (stejna polohova sablona, jen jiny dil se stejnym stredem); u 1200 na teze sirce, jinak porovnani s referenci 1280 stejneho systemu a ramene
    ref_r = r12 if l12 else S.sestav_stul(system=system, sirka=1280, led_rameno=rameno)
    ref_d = led_dily(ref_r)[0]
    for d in l6:
        check(abs(d["position"][0] - ref_d["position"][0]) < 1e-6 and abs(d["position"][1] - ref_d["position"][1]) < 1e-6 and tuple(d["quaternion"]) == tuple(ref_d["quaternion"]) and tuple(d["scale"]) == tuple(ref_d["scale"]),
              f"{system}/{sirka}/{rameno}: svitidlo 600 ma stejnou hloubku, vysku, otoceni a meritko jako svitidlo 1200 ({d['position'][:2]} vs {ref_d['position'][:2]})")
        break
    # srovnani s 1200 na teze sirce: stejny STRED skupiny
    if l12:
        a, b = min(z_rozsah(d)[0] for d in l12), max(z_rozsah(d)[1] for d in l12)
        check(abs((a + b) / 2.0 - (z0 + z1) / 2.0) < 0.01, f"{system}/{sirka}/{rameno}: stred skupiny 600 = stred skupiny 1200 ({(a + b) / 2.0:.3f} vs {(z0 + z1) / 2.0:.3f})")
        check(len(l12) == pocet_pri(sirka, 1200), f"{system}/{sirka}/{rameno}: pocet svitidel 1200 = {pocet_pri(sirka, 1200)} (je {len(l12)})")
check(nevejde1200 > 0 and nevejde600 > 0 and zkontrolovano > 200, f"mrizka pokryla obe hranice a dost konfiguraci ({zkontrolovano})")

print("D2) svitidla se nezanoruji do jinych dilu (AABB prunik nad toleranci) - totez co u 1200")
def prunik(r):
    lo_hi = [S._aabb(d) for d in r["dily"]]
    led = [i for i, d in enumerate(r["dily"]) if d["part_id"] in (L1200, L600)]
    out = []
    for i in led:
        for j, (lo, hi) in enumerate(lo_hi):
            if j == i:
                continue
            pr = np.minimum(lo_hi[i][1], hi) - np.maximum(lo_hi[i][0], lo)
            if np.all(pr > S.TOL_PRUNIK_MM):
                out.append((i, j, round(float(pr.min()), 2)))
    return out
for system, sirka, vzpery, panely in itertools.product((30, 40, 45), (1294, 2000, 3000), (False, True), (True, False)):
    r6 = S.sestav_stul(system=system, sirka=sirka, vzpery=vzpery, panely=panely, led_delka=600)
    check(not prunik(r6), f"{system}/{sirka}/vzpery={vzpery}/panely={panely}: svitidla 600 se nikam nezanoruji ({prunik(r6)[:2]})")
    check(not r6["problemy"], f"{system}/{sirka}/vzpery={vzpery}/panely={panely}: zadne problemy ({[p['kod'] for p in r6['problemy']]})")

print("E) hash: led_delka se promita jen u svitidla jine nez 1200")
r_def = S.sestav_stul(sirka=1500)
h_def = G.kanonicky_hash(r_def["parametry"])
h_12 = G.kanonicky_hash(S.sestav_stul(sirka=1500, led_delka=1200)["parametry"])
h_6 = G.kanonicky_hash(S.sestav_stul(sirka=1500, led_delka=600)["parametry"])
check(h_def == h_12 and h_def != h_6, f"hash: vychozi = 1200, 600 je jiny ({h_def} / {h_12} / {h_6})")
check(h_6 == G.kanonicky_hash(S.sestav_stul(sirka=1500, led_delka=600)["parametry"]), "hash je stabilni")
for p_off in ({"led": False}, {"led_svetlo": False}, {"stojky": False}):
    a = G.kanonicky_hash(S.sestav_stul(sirka=1500, **p_off)["parametry"])
    b = G.kanonicky_hash(S.sestav_stul(sirka=1500, led_delka=600, **p_off)["parametry"])
    check(a == b, f"bez svitidla {p_off}: led_delka 600 hash nemeni")
check(G.kanonicky_hash({"sirka": 1500, "led_delka": 600, "led_pocet": 2}) == h_6 and G.kanonicky_hash({"led_delka": 1200}) == G.kanonicky_hash({}), "kanonicky_hash i z nenormalizovanych parametru (vstup bez efektivnich)")
for p_off in ({"led": False}, {"led_svetlo": False}, {"stojky": False}):                       # hash i ze SUROVYCH parametru (staff API: kanonicky_hash(parametry) z dotazu, ne z efektivnich)
    check(G.kanonicky_hash({"sirka": 1500, "led_delka": 600, **p_off}) == G.kanonicky_hash({"sirka": 1500, **p_off}), f"surove parametry {p_off}: led_delka 600 bez svitidla hash nemeni")
check(G.kanonicky_hash({"sirka": 1500, "led_delka": 600}) != G.kanonicky_hash({"sirka": 1500}) and G.kanonicky_hash({"sirka": 1500, "led_delka": 1200}) == G.kanonicky_hash({"sirka": 1500}), "surove parametry: 600 se svitidlem hash meni, 1200 ne")
h_uzky = G.kanonicky_hash(S.sestav_stul(sirka=500, led_delka=600)["parametry"])
check(h_uzky == G.kanonicky_hash(S.sestav_stul(sirka=500)["parametry"]), "stul 500 (LED 600 se odebere): efektivni parametry bez delky = stejny hash jako bez volby")

print("F) led_info.typy proti skutecnemu chovani")
spatne = 0
for system, sirka in itertools.product((30, 40, 45), [x for x in range(560, 1400, 7)] + [599, 600, 1199, 1200]):
    r6 = S.sestav_stul(system=system, sirka=sirka, led_delka=600)
    if not led_dily(r6):
        continue
    typy = {t["delka"]: t for t in r6["led_info"]["typy"]}
    r12 = S.sestav_stul(system=system, sirka=sirka, led_delka=1200)
    ok12 = bool(led_dily(r12))
    if typy[1200]["vejde"] != ok12 or not typy[600]["vejde"]:
        spatne += 1
        print("   NESOUHLAS", system, sirka, typy, ok12)
    n12 = len(led_dily(r12))
    if ok12 and typy[1200]["pocet"] != n12:
        spatne += 1
        print("   POCET", system, sirka, typy[1200]["pocet"], n12)
    if typy[600]["pocet"] != len(led_dily(r6)) or typy[600]["pocet"] != pocet_pri(sirka, 600) or typy[1200]["pocet"] != pocet_pri(sirka, 1200):
        spatne += 1
        print("   POCET (600 / vzorec)", system, sirka, typy, len(led_dily(r6)))
check(spatne == 0, f"led_info.typy[].vejde a pocet souhlasi se skutecnym chovanim (rozdilu {spatne})")
li = S.sestav_stul(sirka=1500)["led_info"]
check(li["delka"] == 1200 and [t["delka"] for t in li["typy"]] == [600, 1200] and all(t["vejde"] for t in li["typy"]) and [t["min_sirka"] for t in li["typy"]] == [600, 1200]
      and [t["telo"] for t in li["typy"]] == [647.0, 1247.0], f"led_info u vychoziho stolu: {li}")
check(S.sestav_stul(sirka=1500, led=False)["led_info"]["typy"] == [] and S.sestav_stul(sirka=1500, led=False)["led_info"]["delka"] == 1200, "bez LED: led_info.typy prazdne, delka 1200")

print("G) 3D ovladani: menu 'Zvolit LED N mm'")
def cast_led(r):
    o = S.ovladani_3d(r)
    c = [x for x in o["casti"] if x["id"] == "led"]
    return c[0] if c else None
r = S.sestav_stul(sirka=1500)
c = cast_led(r)
tx = [m["text"] for m in c["menu"]]
check("Zvolit LED 600 mm" in tx and "Zvolit LED 1200 mm" not in tx, f"u 1200: menu nabizi 600, ne 1200 ({tx})")
check("led_delka" in c["param"], f"cast led nese parametr led_delka ({c['param']})")
pol600 = [m for m in c["menu"] if m["text"] == "Zvolit LED 600 mm"][0]
check(pol600["nastav"] == {"led_delka": 600.0} and not pol600["zakazano"], f"polozka 'Zvolit LED 600 mm': nastaveni {pol600['nastav']}")
r_zpet = S.sestav_stul(**{**r["parametry"], **pol600["nastav"]})
check(G.kanonicky_hash(r_zpet["parametry"]) == G.kanonicky_hash(S.sestav_stul(sirka=1500, led_delka=600, led_pocet=1)["parametry"]) and len(led_dily(r_zpet)) == 1, "pouziti nastaveni z menu dava konfiguraci s LED 600 (pocet svitidel se prepnutim delky nemeni: 1)")
c6 = cast_led(r_zpet)
tx6 = [m["text"] for m in c6["menu"]]
check("Zvolit LED 1200 mm" in tx6 and "Zvolit LED 600 mm" not in tx6, f"u 600: menu nabizi 1200, ne 600 ({tx6})")
rz = S.sestav_stul(sirka=900, led_delka=600)
cz = cast_led(rz)
pz = [m for m in cz["menu"] if m["text"] == "Zvolit LED 1200 mm"][0]
check(pz["zakazano"] and pz["duvod"] and "nevejde" in pz["duvod"], f"na stole 900 je 'Zvolit LED 1200 mm' zakazano s duvodem ({pz['duvod']})")
r_bez = S.sestav_stul(sirka=1500, led_svetlo=False)
check(not [m for m in cast_led(r_bez)["menu"] if m["text"].startswith("Zvolit LED")], "bez svitidla (jen ramena) menu delek neni")
check(len({id(x) for x in []}) == 0 and cast_led(S.sestav_stul(sirka=1500, led_delka=600)) is not None, "cast led s vice svitidly 600 je ve 3D ovladani")
# aabb casti led obsahuje vsechna svitidla
r6 = S.sestav_stul(sirka=2000, led_delka=600)
c6 = cast_led(r6)
zs6 = [z_rozsah(d)[:2] for d in led_dily(r6)]
check(c6["aabb"][0][2] <= min(a for a, b in zs6) + 3.5 and c6["aabb"][1][2] >= max(b for a, b in zs6) - 3.5, "AABB casti led pokryva vsechna svitidla 600 (osa Z)")
bbl = [S._aabb(d) for d in led_dily(r6)]
check(all(c6["aabb"][0][i] <= min(b_[0][i] for b_ in bbl) + 3.5 and c6["aabb"][1][i] >= max(b_[1][i] for b_ in bbl) - 3.5 for i in range(3)), f"AABB casti led obsahuje svitidla 600 ve vsech osach ({c6['aabb']} vs {[(b_[0].round(1).tolist(), b_[1].round(1).tolist()) for b_ in bbl[:1]]})")

print("H) model GLB (material led) a data pro pocitadlo luxu")
for sirka, d in ((1500, 600), (2000, 600), (1500, 1200), (2600, 1200)):
    r = S.sestav_stul(sirka=sirka, led_delka=d)
    hh, data = G.model_pro_parametry(r["parametry"])
    with tempfile.NamedTemporaryFile(suffix=".glb") as f:
        f.write(data)
        f.flush()
        sc = trimesh.load(f.name, force="scene")
    js = json.loads(data[20:20 + int.from_bytes(data[12:16], "little")])
    mat = [m_.get("pbrMetallicRoughness", {}).get("baseColorFactor") for m_ in js.get("materials", [])]
    led_bf = G.MATERIALY["led"]["baseColorFactor"] if hasattr(G, "MATERIALY") else [0.93, 0.93, 0.9, 1.0]
    check([float(x) for x in led_bf] in [[float(x) for x in m_] for m_ in mat if m_], f"{sirka}/{d}: GLB ma material led (baseColorFactor {led_bf}; je {mat})")
    iled = [i_ for i_, m_ in enumerate(mat) if m_ and [float(x) for x in m_] == [float(x) for x in led_bf]][0]
    prim = [pr for me in js["meshes"] for pr in me["primitives"] if pr.get("material") == iled]
    acc = [js["accessors"][pr["attributes"]["POSITION"]] for pr in prim]
    zl = min(a["min"][2] for a in acc), max(a["max"][2] for a in acc)
    n = pocet_pri(sirka, d)
    ocek = (n - 1) * TELO[d] + (1247.001 if d == 1200 else 647.001)
    check(abs((zl[1] - zl[0]) - ocek) < 0.05, f"{sirka}/{d}: v GLB maji svitidla spolecnou delku {zl[1] - zl[0]:.3f} (cekano {ocek:.3f})")
    for tp in ("product_4929", "product_5359"):
        pass
    osv = stul_osvetleni.osvetleni(r, G._transformuj)
    check(osv is not None and len(osv["lights"]) == n, f"{sirka}/{d}: payload luxu ma {n} svitidel")
    for lt in osv["lights"]:
        typ = "led_1200" if d == 1200 else "led_600"
        check(lt["typ"] == typ and lt["nominalLengthMm"] == float(d) and abs(lt["housingLengthMm"] - TELO[d]) < 1e-9 and lt["type"] == "linear" and lt["direction"] == [0, -1, 0], f"{sirka}/{d}: svitidlo {lt['id']}: typ {lt['typ']}, nominal {lt['nominalLengthMm']}, teleso {lt['housingLengthMm']}")
        sl = lt["endMm"][2] - lt["startMm"][2]
        c_tel = (lt["housingBoundsMm"][0][2] + lt["housingBoundsMm"][1][2]) / 2.0
        check(abs(sl - d) < 0.01 and abs((lt["startMm"][2] + lt["endMm"][2]) / 2.0 - c_tel) < 0.01, f"{sirka}/{d}: svitici cara {sl:.2f} mm vystredena v telese")
        check(abs((lt["housingBoundsMm"][1][2] - lt["housingBoundsMm"][0][2]) - (1247.001 if d == 1200 else 647.001)) < 0.02, f"{sirka}/{d}: teleso z vrcholu meshe = {lt['housingBoundsMm'][1][2] - lt['housingBoundsMm'][0][2]:.3f} mm")
    check(all("sku" not in json.dumps(lt).lower() and "4929" not in json.dumps(lt) and "5359" not in json.dumps(lt) for lt in osv["lights"]), f"{sirka}/{d}: verejny payload svitidel nenese SKU ani cislo produktu")
    ids = [lt["id"] for lt in osv["lights"]]
    zc = [(lt["housingBoundsMm"][0][2] + lt["housingBoundsMm"][1][2]) for lt in osv["lights"]]
    check(ids == [f"led-{k}" for k in range(1, n + 1)] and zc == sorted(zc), f"{sirka}/{d}: id svitidel led-1.. zleva doprava")
# vodici: pocitadlo luxu dostane stejny payload i pres verejne vodici (posun GLB)
r6 = S.sestav_stul(sirka=1500, led_delka=600)
r6["ovladani_scena"] = S.ovladani_3d(r6)                                    # jako stul_shop.resolve
vod = G.vodici(r6["parametry"], r6)
check(vod and vod.get("osvetleni") and [l_["typ"] for l_ in vod["osvetleni"]["lights"]] == ["led_600"] * pocet_pri(1500, 600), f"vodici: osvetleni nese svitidla typu led_600 ({vod and list((vod.get('osvetleni') or {}))})")

print("I) degradace pri chybejicim GLB 600 (vychozi cesta nespadne)")
orig_dir = S.KATALOG_DIR
orig_cache = (dict(S._BBOX_CACHE), dict(S._LED_TELO))
tmp = tempfile.mkdtemp(prefix="katalog_bez_5359_")
for f in os.listdir(KAT):
    if f.startswith("product_") and f.endswith(".glb") and f != "product_5359.glb":
        os.symlink(os.path.join(KAT, f), os.path.join(tmp, f))
try:
    S.KATALOG_DIR = tmp
    S._BBOX_CACHE.pop(L600, None)
    S._LED_TELO.pop(L600, None)
    r = S.sestav_stul(sirka=1500)
    check(len(led_dily(r)) == 1 and [t["delka"] for t in r["led_info"]["typy"]] == [1200], f"bez GLB 600: vychozi stul funguje, led_info nabizi jen 1200 ({r['led_info']['typy']})")
    try:
        S.sestav_stul(sirka=1500, led_delka=600)
        check(False, "bez GLB 600: led_delka=600 musi vyhodit StulChyba")
    except S.StulChyba as e:
        check("5359" in str(e), f"bez GLB 600: StulChyba nese chybejici dil ({str(e)[:80]})")
finally:
    S.KATALOG_DIR = orig_dir
    S._BBOX_CACHE.clear()
    S._BBOX_CACHE.update(orig_cache[0])
    S._LED_TELO.clear()
    S._LED_TELO.update(orig_cache[1])
check(len(S.sestav_stul(sirka=1500, led_delka=600)["dily"]) > 0, "po obnoveni katalogu LED 600 zase funguje")

print("J) SSE (system 41): led_delka se ignoruje")
a = S.sestav_stul(system=41, led_delka=600)
b = S.sestav_stul(system=41)
check(G.kanonicky_hash(a["parametry"]) == G.kanonicky_hash(b["parametry"]) and a["parametry"]["led_delka"] == 1200.0 and C.otisk(a) == C.otisk(b), "SSE: led_delka=600 = vychozi (hash, dily)")

print("K) rozsahy: nejuzsi (500) a nejsirsi (3000) stul")
r = S.sestav_stul(sirka=3000, led_delka=600)
check(len(led_dily(r)) == 4 and not r["problemy"], f"sirka 3000: 4 svitidla 600 ({len(led_dily(r))})")
r = S.sestav_stul(sirka=3000)
check(len(led_dily(r)) == 2, f"sirka 3000: 2 svitidla 1200 ({len(led_dily(r))})")
r = S.sestav_stul(sirka=500, led_delka=600)
check(not led_dily(r) and "led" in [o["volba"] for o in r["odebrano"]], "sirka 500: LED 600 se nevejde, odebere se")

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:6]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
