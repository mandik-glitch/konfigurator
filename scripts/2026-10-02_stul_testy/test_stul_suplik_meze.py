#!/usr/bin/env python3
"""Test PRESNYCH MEZI posunu suplikoveho boxu (bot8, 2026-10-03; Robert: "suplik v noze je neakceptovatelny, zapomnels na limity").

Generator vraci `suplik_meze` {hodnota, min, max, vejde} = hodnoty parametru `suplik_posun`, pri kterych ma box (a jeho pricky) od KAZDE nohy (krajni i stredni) aspon
30 mm. Test to proveri NEZAVISLE na vypoctu mezi: z SKUTECNE site dilu (stul_glb._transformuj) zmeri svetlou vzdalenost boxu od kazde svisle nohy, ktera se s nim
prekryva v X a Y. Pro param = min a = max: generator NEhlasi problem, supliky zustavaji a vzdalenost je >= 30 mm - 0.01; pro min-10 a max+10: problem (nebo odebrani),
nebo vzdalenost < 30 mm (meze nejsou zbytecne prisne ani prilis volne). `vejde` False = ani pri `hodnota` nic neplati.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_suplik_meze.py  (STUL_API_OVERRIDE = jina kopie api/)
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import numpy as np  # noqa: E402
import stul_glb as G  # noqa: E402
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


def mesh(d):
    P, _, _ = G._transformuj(d["part_id"], d)
    return P.min(axis=0), P.max(axis=0)


def mezery_od_noh(r):
    """[(index nohy, svetla vzdalenost v ose Z)] boxu od kazde svisle nohy (profil Object_7 podel Y, delka > 100 mm), ktera se s nim prekryva v X a Y (po mesh, ne AABB generatoru)."""
    dily = r["dily"]
    box = next(d for d in dily if d["part_id"] in S.SUPLIK_PARTY_VSE)               # box s 1 / 2 / 3 supliky (stejny pudorys, jiny dil katalogu)
    lo_b, hi_b = mesh(box)
    out = []
    for i, d in enumerate(dily):
        if d["part_id"] not in S.PROFIL_PARTS or S._osa(d["quaternion"])[0] != 1 or 1000.0 * d["scale"][1] <= 100.0:
            continue
        lo, hi = mesh(d)
        if min(hi[0], hi_b[0]) - max(lo[0], lo_b[0]) > 1.0 and min(hi[1], hi_b[1]) - max(lo[1], lo_b[1]) > 1.0:
            out.append((i, float(max(lo[2] - hi_b[2], lo_b[2] - hi[2]))))
    return out


def stav(kw, v):
    r = S.sestav_stul(**{**kw, "suplik_posun": v})
    return r, r["parametry"]["suplik"], r["problemy"]


KONF = []
for sirka in (1200, 1840, 2400, 3000):
    for hloubka in (600, 800, 1100):
        KONF.append(dict(sirka=sirka, hloubka=hloubka))
        if sirka > S.SIRKA_STREDNI_NOHY:
            KONF.append(dict(sirka=sirka, hloubka=hloubka, stredni_noha=round((sirka - 30.0) * 0.25, 1)))
            KONF.append(dict(sirka=sirka, hloubka=hloubka, stredni_noha=round((sirka - 30.0) * 0.75, 1)))
KONF += [dict(sirka=1840, kolecka=False, patky=True), dict(sirka=2400, vyska=500, police=0), dict(sirka=1000), dict(sirka=900, hloubka=700)]
for pocet in (1, 3):                                      # box s 1 a 3 supliky (Robert 2026-10-05): stejny pudorys, meze posunu musi platit stejne (stul 1100 mm, aby se i 3 supliky vesly)
    for kw0 in (dict(sirka=1200), dict(sirka=1840), dict(sirka=2400, stredni_noha=round((2400 - 30.0) * 0.25, 1)), dict(sirka=900, hloubka=700), dict(sirka=2400, hloubka=1100, suplik_vlevo=True)):
        KONF.append({**kw0, "vyska": 1100, "suplik_pocet": pocet})
zkouseno = 0
for kw in KONF:
    n = str(kw)
    r0 = S.sestav_stul(**kw)
    m = r0.get("suplik_meze")
    if not r0["parametry"]["suplik"]:
        check(m is None, f"{n}: supliky odebrany -> zadne meze")
        continue
    check(m is not None and set(m) == {"hodnota", "min", "max", "vejde"}, f"{n}: odpoved nese suplik_meze")
    if not m["vejde"]:
        check(m["min"] == m["max"] == m["hodnota"], f"{n}: nevejde se -> min = max = hodnota")
        continue
    check(m["min"] <= m["max"] and m["min"] % 10 == 0 and m["max"] % 10 == 0, f"{n}: meze po 10 mm a min <= max ({m})")
    # meze se meri od AKTUALNIHO (vychoziho, parametr 0) stavu: hodnota = skutecny posun (u uzkeho stolu automaticky)
    for v, nazev in ((m["min"], "min"), (m["max"], "max")):
        r, suplik, problemy = stav(kw, v)
        zkouseno += 1
        check(suplik and not problemy, f"{n}: suplik_posun = {nazev} ({v:+.0f}) bez problemu a supliky zustavaji ({[x['text'][:60] for x in problemy][:1]})")
        if suplik:
            mz = mezery_od_noh(r)
            check(mz and all(g >= S.ODSTUP_KOMPONENTU_OD_NOHOU - 0.01 for _, g in mz), f"{n}: suplik_posun = {nazev} ({v:+.0f}): svetla vzdalenost od vsech {len(mz)} nohou >= 30 mm ({[round(g, 1) for _, g in mz]})")
    for v, nazev in ((m["min"] - 10, "min-10"), (m["max"] + 10, "max+10")):
        r, suplik, problemy = stav(kw, v)
        if not suplik or problemy:
            check(True, "")
            continue
        mz = mezery_od_noh(r)
        check(any(g < S.ODSTUP_KOMPONENTU_OD_NOHOU - 0.01 for _, g in mz) or not mz, f"{n}: suplik_posun = {nazev} ({v:+.0f}) je bez problemu, ale vzdalenost od nohy uz neni < 30 mm - meze jsou zbytecne prisne ({[round(g, 1) for _, g in mz]})")
    # `hodnota` je skutecna poloha boxu: parametr 0 a parametr = hodnota davaji stejne dily boxu (u uzkeho stolu ma parametr 0 automaticky posun)
    if m["hodnota"] != 0.0:
        ra, rb = r0, S.sestav_stul(**{**kw, "suplik_posun": m["hodnota"]})
        za = next(d["position"][2] for d in ra["dily"] if d["part_id"] in S.SUPLIK_PARTY_VSE)
        zb = next(d["position"][2] for d in rb["dily"] if d["part_id"] in S.SUPLIK_PARTY_VSE)
        check(abs(za - zb) < 0.5, f"{n}: hodnota ({m['hodnota']}) = skutecny automaticky posun boxu (rozdil poloh {abs(za - zb):.2f} mm)")

# zakrivene pripady: ucelove uzky stul s RUCNIM posunem (nevejde se / vejde se jen jedna poloha)
vejde = 0
for sirka in range(640, 760, 10):
    r = S.sestav_stul(sirka=sirka, suplik_posun=10.0)
    m = r["suplik_meze"]
    if not r["parametry"]["suplik"]:
        check(m is None, f"sirka {sirka}: box odebran -> bez mezi")
        continue
    if m["vejde"]:
        vejde += 1
        rr, suplik, problemy = stav(dict(sirka=sirka), m["min"])
        check(suplik and not problemy, f"sirka {sirka}: jedina/nejlevejsi pripustna poloha ({m['min']:+.0f}) bez problemu")
    else:
        check(r["problemy"] or not r["parametry"]["suplik"], f"sirka {sirka}: vejde False -> generator hlasi problem")
check(vejde >= 1, "uzky stul: aspon jedna sirka, kde se box vejde jen do uzke mezery")
# ovladani ve 3D bere meze z popisu (ne hruby vzorec)
r = S.odpoved(dict(sirka=1840))
t = next(x for x in r["ovladani_scena"]["tahy"] if x["id"] == "suplik_posun")
check(t["min"] == r["suplik_meze"]["min"] and t["max"] == r["suplik_meze"]["max"] and t["hodnota"] == r["suplik_meze"]["hodnota"], f"3D tah suplik_posun: min/max/hodnota z suplik_meze ({t['min']}, {t['max']}, {t['hodnota']})")
check(r["suplik_meze"]["min"] > -(1840 - 700) and r["suplik_meze"]["max"] < 80, "meze jsou UZSI nez dosavadni hruby vzorec -(sirka-700)..80")
check(not S.odpoved(dict(suplik=False))["suplik_meze"], "bez supliku zadne meze")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK ({zkouseno} poloh zkouseno)")
    sys.exit(1)
print(f"\n{OK} kontrol OK ({zkouseno} poloh zkouseno)")
