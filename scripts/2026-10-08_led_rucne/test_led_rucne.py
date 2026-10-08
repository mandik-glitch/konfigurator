#!/usr/bin/env python3
"""Test RUCNICH SVITIDEL LED v generatoru stolu (bot8, 2026-10-08).
Robert: "svitidla v generatoru se pridavaji automaticky za sebe podle delky, ale chceme aby se pridavali jen rucne a mohli se posouvat podel profilu".

Co se hlida (generator, GLB, lux data, hash, 3D ovladani; DB se NEPOUZIVA, pymysql.connect je zakazano):
  * vstup `led_pocet` (1..4, cele cislo) a `led_z1..led_z4` (poloha STREDU svitidla v mm od osy stolu, + doprava, None = automaticky): hranice, chybne hodnoty, `parametry_z_dotazu`;
  * vychozi = JEDNO svitidlo (u sirokych stolu uz se nepridavaji sama); pocet 1..max, kolik se vejde (soucet delek <= sirka + LED_PREVIS), vyssi se orizne; svitidla stoji tesne vedle sebe a skupina je
    vystredena jako dosud;
  * polohy MERENE z vrcholu meshe (nezavisle na generatoru): stred svitidla = osa stolu + led_z<k>; svitidla se neprekryvaji, zustava poradi, aspon 90 % delky kazdeho lezi nad pricnym profilem,
    rozpeti skupiny <= sirka + LED_PREVIS; nahodny pokus (fuzz) na invarianty a idempotenci (efektivni parametry zpet do generatoru = totez);
  * kanonicka podoba: poloha shodna s automatickou = None (stejny model i hash); bez svitidla (led / svetlo / stojky vypnuty, svitidlo se nevejde) se pocet a polohy zahodi; SSE je ignoruje;
  * `led_info` (pocet, max, polohy, auto, meze, pridat, odebrat) a jeho nabidky: pridat do prazdneho mista, odebrat libovolne svitidlo bez posunu ostatnich;
  * 3D ovladani: casti `led_<k>`, tah `led_z<k>` s mezemi (sousedi, okraj), cislovane vzorce `mereni` proti MERENI z vrcholu, nabidky (pridat / odebrat / vratit na vychozi misto), ZIVE tazeni proti modelu
    ze serveru (test_stul_zive.porovnej);
  * hash: pocet 1 se u stolu, kam se vejde jen jedno svitidlo, nenese (hashe uzkych stolu beze zmeny), u sirsiho ano; polohy None / pro neexistujici svitidlo se nenesou;
  * ZLATY OTISK (golden_head.json = stav PRED zmenou, 873 konfiguraci): vsechno beze zmeny, krome stolu, kde drive vznikalo vic svitidel automaticky - tam `led_pocet` = drivejsi pocet da PRESNE
    drivejsi model (otisk dilu, problemy, odebrane, spoje).
Spusteni: api/venv/bin/python3 scripts/2026-10-08_led_rucne/test_led_rucne.py        (STUL_API_OVERRIDE=<adresar api> = kandidat; TEST_STOP_PRVNI=1 = prvni selhani konci)"""
import importlib.util
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_osvetleni as O  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")
        if os.environ.get("TEST_STOP_PRVNI"):
            sys.exit(1)


def ocekavej_chybu(msg, kod="mimo_rozsah", **kw):
    try:
        S.sestav_stul(**kw)
    except S.StulChyba as e:
        check(getattr(e, "kod", None) == kod or kod is None, f"{msg}: chyba s kodem {kod} ({getattr(e, 'kod', None)})")
        return
    except Exception as e:  # noqa: BLE001
        check(False, f"{msg}: ocekavana StulChyba, prisla {type(e).__name__}: {e}")
        return
    check(False, f"{msg}: ocekavana StulChyba, vyslo bez chyby")


TOL = 0.06                                                               # mm: polohy jsou na mrizce 0,1 mm
LED_PREVIS = S.LED_PREVIS
Q90 = S.MIN_PODIL_PROFILU_LED


def lampy(r):
    return [d for d in r["dily"] if d["part_id"] in C.LED_PARTY]


def zrozsah(d):
    P, _, _ = G._transformuj(d["part_id"], d)                           # vrcholy meshe ve svete generatoru (nezavisle na S._aabb)
    return float(P[:, 2].min()), float(P[:, 2].max())


def osa_stolu(r):
    """(osa z, sirka) vnejsich okraju stolu z pracovni desky."""
    desky = [d for d in r["dily"] if d["part_id"] == O.DESKA_PART and str(d.get("deska_id") or "").startswith(O.PRACOVNI_PREFIX)]
    lo = min(float(S._aabb(d)[0][2]) for d in desky)
    hi = max(float(S._aabb(d)[1][2]) for d in desky)
    return (lo + hi) / 2.0, hi - lo


def meri(r):
    """Nezavisle mereni: (osa stolu, sirka stolu, [(stred vuci ose, levy konec vuci ose, pravy konec vuci ose) zleva doprava])."""
    zc, w = osa_stolu(r)
    out = []
    for lo, hi in sorted(zrozsah(d) for d in lampy(r)):
        out.append(((lo + hi) / 2.0 - zc, lo - zc, hi - zc))
    return zc, w, out


def sestav(**kw):
    return S.sestav_stul(**kw)


def stredy(r):
    return [round(c, 2) for c, _, _ in meri(r)[2]]


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== konstanty a vstup")
check(S.LED_MAX == 4 and S.LED_PARAMETRY_Z == ("led_z1", "led_z2", "led_z3", "led_z4"), f"LED_MAX 4, LED_PARAMETRY_Z ({S.LED_MAX}, {S.LED_PARAMETRY_Z})")
check(S.VYCHOZI["led_pocet"] == 1 and all(S.VYCHOZI[k] is None for k in S.LED_PARAMETRY_Z), "VYCHOZI: led_pocet 1, polohy None")
check(S.led_max_pocet(5000, 647.0) == S.LED_MAX and S.led_max_pocet(100, 647.0) == 1 and S.led_max_pocet(1246, 647.0) == 1 and S.led_max_pocet(1247, 647.0) == 2,
      "led_max_pocet: strop LED_MAX, nejmene 1, hranice 1247 mm (2 x 647 <= sirka + 47)")
r0 = sestav()
check(r0["parametry"]["led_pocet"] == 1 and all(r0["parametry"][k] is None for k in S.LED_PARAMETRY_Z), "vychozi stul: 1 svitidlo, polohy None")
for zle in (0, 5, -1, 1.5, "2", None, True, float("nan"), float("inf")):
    ocekavej_chybu(f"led_pocet={zle!r}", led_pocet=zle)
for zle in ("5", True, float("nan"), float("inf"), [1], {}):
    ocekavej_chybu(f"led_z1={zle!r}", led_z1=zle)
check(sestav(led_pocet=1.0)["parametry"]["led_pocet"] == 1 and isinstance(sestav(led_pocet=1.0)["parametry"]["led_pocet"], int), "led_pocet=1.0 (cislo s .0) se prijme jako int")
check(sestav(sirka=1500, led_delka=600, led_pocet=2, led_z1=-300)["parametry"]["led_z1"] == -300.0, "led_z1 se uklada jako cislo (mm)")
check(sestav(sirka=1500, led_delka=600, led_z1=-300.04)["parametry"]["led_z1"] == -300.0, "led_z1 se zaokrouhluje na 0,1 mm")
check(S._norm_parametry({"led_z1": 50.04})["led_z1"] == 50.0 and S._norm_parametry({"led_z1": 50.06})["led_z1"] == 50.1 and S._norm_parametry({"led_z2": None})["led_z2"] is None, "_norm_parametry: poloha na 0,1 mm uz ve vstupu, None zustava None")
pz = S.parametry_z_dotazu({"led_pocet": "2", "led_z1": "-120.5", "led_z2": "null", "led_z3": "", "led_z4": "auto", "sirka": "1500"})
check(pz == {"led_pocet": 2.0, "led_z1": -120.5, "led_z2": None, "led_z3": None, "led_z4": None, "sirka": 1500.0}, f"parametry_z_dotazu: cisla a None (null / prazdne / auto) ({pz})")
try:
    S.parametry_z_dotazu({"led_z1": "abc"})
    check(False, "parametry_z_dotazu: led_z1=abc ma selhat")
except S.StulChyba:
    check(True, "")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== vychozi = jedno svitidlo, pocet 1..max, tesne vedle sebe, vystredene")
KONF = ((1500, 600, 2), (2000, 600, 3), (2600, 600, 4), (3000, 600, 4), (2447, 1200, 2), (3000, 1200, 2), (2446, 1200, 1), (1280, 1200, 1), (1200, 600, 1), (700, 600, 1))
ref1 = {}
for sirka, delka, nmax in KONF:
    base = dict(sirka=sirka, led_delka=delka)
    r1 = sestav(**base)
    zc, w, m1 = meri(r1)
    check(len(m1) == 1 and not r1["problemy"] and "led" not in [o["volba"] for o in r1["odebrano"]], f"{base}: vychozi = 1 svitidlo bez problemu ({len(m1)}, {[x['kod'] for x in r1['problemy']]})")
    check(abs(w - sirka) < 0.5, f"{base}: sirka stolu z desky = {sirka} ({w:.1f})")
    ref1[(sirka, delka)] = (zc, m1[0][0], m1[0][2] - m1[0][1])
    li = r1["led_info"]
    check(li["pocet"] == 1 and li["max"] == nmax, f"{base}: led_info pocet 1, max {nmax} ({li['pocet']}, {li['max']})")
    check(abs(li["osa"] - zc) < 0.1, f"{base}: led_info.osa = osa stolu z desky ({li['osa']} vs {zc:.2f})")
    for n in range(1, nmax + 1):
        r = sestav(**base, led_pocet=n)
        zc, w, m = meri(r)
        dl = m[0][2] - m[0][1]
        check(len(m) == n and r["parametry"]["led_pocet"] == n and all(r["parametry"][k] is None for k in S.LED_PARAMETRY_Z), f"{base} led_pocet={n}: {n} svitidel, polohy None ({len(m)})")
        check(not r["problemy"] and "led" not in [o["volba"] for o in r["odebrano"]], f"{base} led_pocet={n}: bez problemu ({[x['kod'] for x in r['problemy']]})")
        check(all(abs((m[i + 1][1] - m[i][2])) < TOL for i in range(n - 1)), f"{base} led_pocet={n}: svitidla tesne vedle sebe ({[round(m[i + 1][1] - m[i][2], 3) for i in range(n - 1)]})")
        check(abs(sum(c for c, _, _ in m) / n - ref1[(sirka, delka)][1]) < TOL, f"{base} led_pocet={n}: skupina vystredena kolem vychozi polohy jednoho svitidla ({sum(c for c, _, _ in m) / n:.2f} vs {ref1[(sirka, delka)][1]:.2f})")
        check(all(abs(a - b) < TOL for a, b in zip(r["led_info"]["polohy"], [c for c, _, _ in m])), f"{base} led_pocet={n}: led_info.polohy = mereni z vrcholu ({r['led_info']['polohy']} vs {[round(c, 2) for c, _, _ in m]})")
        check(r["led_info"]["auto"] == r["led_info"]["polohy"] and r["led_info"]["pocet"] == n, f"{base} led_pocet={n}: automaticke polohy = polohy")
        check(abs(sum(1 for d in r['dily'] if d['part_id'] in C.LED_PARTY) - n) < 0.5, f"{base} led_pocet={n}: pocet dilu svitidel")
    if nmax < 4:
        r = sestav(**base, led_pocet=nmax + 1)
        check(r["parametry"]["led_pocet"] == nmax and len(lampy(r)) == nmax, f"{base} led_pocet={nmax + 1}: orizne se na {nmax} ({r['parametry']['led_pocet']})")
    r = sestav(**base, led_pocet=4)
    check(r["parametry"]["led_pocet"] == nmax and len(lampy(r)) == nmax, f"{base} led_pocet=4: orizne se na nejvic {nmax}")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== polohy: MERENE z vrcholu")
base = dict(sirka=1500, led_delka=600)
zc, w, _ = meri(sestav(**base))
for x in (-480.0, -300.0, -100.0, 0.0, 123.4, 300.0, 480.0):
    r = sestav(**base, led_z1=x)
    c = meri(r)[2][0][0]
    check(abs(c - x) < TOL and abs(r["parametry"]["led_z1"] - x) < 1e-9 and not r["problemy"], f"1 svitidlo: led_z1={x} -> stred {c:.2f} mm od osy, bez problemu")
auto1 = sestav(**base)["led_info"]["auto"][0]                      # poloha tesne vedle automaticke (0,2 / 2 / -3 mm) se za automatickou NEpovazuje: jde do parametru presne (prah splyvani je 0,05 mm)
for d_ in (0.2, 2.0, -3.0):
    r = sestav(**base, led_z1=round(auto1 + d_, 1))
    check(abs(meri(r)[2][0][0] - (auto1 + d_)) < TOL and r["parametry"]["led_z1"] is not None and abs(r["parametry"]["led_z1"] - (auto1 + d_)) < TOL,
          f"led_z1 = automaticka {d_:+.1f} mm: presne ({r['parametry']['led_z1']})")
li = sestav(**base)["led_info"]
lo_abs, hi_abs = li["stred"]
tel = meri(sestav(**base))[2][0][2] - meri(sestav(**base))[2][0][1]                      # delka telesa svitidla 600 z vrcholu meshe (647)
check(abs(tel - 647.0) < 1.0, f"telo svitidla 600 ma z vrcholu meshe ~647 mm ({tel:.2f})")
check(abs(lo_abs - (-w / 2 + Q90 * tel - tel / 2)) < 0.15 and abs(hi_abs + lo_abs) < 0.15, f"led_info.stred = rozsah stredu svitidla (aspon 90 % delky nad profilem): {li['stred']}")
for pozad, ocek_lo, ocek_hi in ((-5000.0, lo_abs, None), (5000.0, None, hi_abs), (lo_abs - 0.5, lo_abs, None), (hi_abs + 0.5, None, hi_abs)):
    r = sestav(**base, led_z1=pozad)
    c, lk, pk = meri(r)[2][0]
    ocek = ocek_lo if ocek_lo is not None else ocek_hi
    check(abs(c - ocek) < 0.1 and abs(r["parametry"]["led_z1"] - ocek) < 0.15, f"led_z1={pozad:g}: orizne se na mez {ocek:.1f} ({c:.2f}; parametr {r['parametry']['led_z1']})")
    prah = (1 - Q90) * (pk - lk) + 0.1
    check(lk >= -w / 2 - prah and pk <= w / 2 + prah, f"led_z1={pozad:g}: presah svitidla pres okraj stolu <= 10 % delky ({lk + w / 2:.1f}, {pk - w / 2:.1f})")
    check(not r["problemy"], f"led_z1={pozad:g}: bez problemu ({[x['kod'] for x in r['problemy']]})")
# rovna mez presne: svitidlo na mezi = presne 10 % presah
r = sestav(**base, led_z1=lo_abs)
c, lk, pk = meri(r)[2][0]
check(abs((lk + w / 2) + (1 - Q90) * (pk - lk)) < 0.2, f"svitidlo na mezi presahuje okraj o 10 % delky ({lk + w / 2:.2f} vs {-(1 - Q90) * (pk - lk):.2f})")

# dve svitidla: rucni scenare s vypoctem rukou (sirka 1500, svitidlo 600 -> telo 647, stred v rozsahu +-491,2)
base2 = dict(sirka=1500, led_delka=600, led_pocet=2)
r = sestav(**base2, led_z1=300.0)                                          # 1. se orizne na (max - telo) a 2. se odsune tesne vedle
c = stredy(r)
check(abs(c[0] - (hi_abs - tel)) < 0.1 and abs(c[1] - hi_abs) < 0.1, f"z1=300: [{c[0]}, {c[1]}] = [{hi_abs - tel:.1f}, {hi_abs:.1f}] (1. orezano, 2. odsunuto)")
check(abs(r["parametry"]["led_z1"] - c[0]) < 0.06 and abs(r["parametry"]["led_z2"] - c[1]) < 0.06, f"z1=300: efektivni parametry nesou skutecne polohy ({r['parametry']['led_z1']}, {r['parametry']['led_z2']})")
r = sestav(**base2, led_z1=-300.0, led_z2=-100.0)                           # 2. nesmi prekryt 1. -> odsunuto tesne vedle (-300 + telo)
c = stredy(r)
check(abs(c[0] + 300.0) < 0.06 and abs(c[1] - (-300.0 + tel)) < 0.1, f"z1=-300, z2=-100: [{c[0]}, {c[1]}] = [-300, {-300.0 + tel:.1f}] (2. odsunuto od 1.)")
r = sestav(**base2, led_z1=-400.0, led_z2=420.0)
c = stredy(r)
check(abs(c[0] + 400.0) < 0.06 and abs(c[1] - 420.0) < 0.06 and abs(r["parametry"]["led_z2"] - 420.0) < 0.06, f"z1=-400, z2=420: obe na zadanych mistech ({c})")
r = sestav(**base2, led_z1=0.0)                                            # 1. nemuze dal doprava nez (max - telo): jinak by se 2. nevesla
c = stredy(r)
check(abs(c[0] - (hi_abs - tel)) < 0.1 and abs(c[1] - hi_abs) < 0.1, f"z1=0: 1. se zastavi, aby se 2. vlezlo ({c})")
r = sestav(**base2, led_z2=-300.0)                                         # 2. nezaujme misto vlevo od 1. (poradi se nemeni): 1. auto -355,2 -> 2. tesne vpravo od 1.
c = stredy(r)
check(abs(c[0] - (-355.2)) < 0.1 and abs(c[1] - (-355.2 + tel)) < 0.1, f"z2=-300: poradi se nemeni, 2. tesne vedle 1. ({c})")

# rozpeti skupiny: 4 svitidla 600 na stolu 3000 (4 x 647 = 2588 <= 3000 + 47): lze je rozsunout, rozpeti <= sirka + LED_PREVIS
base4 = dict(sirka=3000, led_delka=600, led_pocet=4)
r = sestav(**base4, led_z1=-5000.0, led_z4=5000.0)
zc, w, m = meri(r)
check(len(m) == 4 and abs((m[3][2] - m[0][1]) - (w + LED_PREVIS)) < 0.3, f"4 svitidla roztazena na krajni mez: rozpeti {m[3][2] - m[0][1]:.1f} = sirka + LED_PREVIS ({w + LED_PREVIS:.0f})")
check(all(m[i + 1][1] - m[i][2] > -TOL for i in range(3)), "4 roztazena svitidla se neprekryvaji")
check(abs(m[0][1] - (-w / 2 - (1 - Q90) * tel)) < 0.3, f"1. svitidlo stoji na mezi (10 % presah pres levy okraj): {m[0][1] + w / 2:.1f}")
check(not r["problemy"], f"4 roztazena svitidla: bez problemu ({[x['kod'] for x in r['problemy']]})")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== nahodny pokus: invarianty a idempotence")
rnd = random.Random(20261008)
pocitadlo = 0
for i in range(260):
    sirka = rnd.choice((700, 900, 1100, 1280, 1500, 1800, 2000, 2447, 2600, 3000))
    delka = rnd.choice((600, 1200))
    nmax = S.led_max_pocet(sirka, S.led_telo_dilu(S.LED_TYPY[delka]))
    n = rnd.randint(1, 4)
    zad = {f"led_z{k}": (None if rnd.random() < 0.35 else round(rnd.uniform(-sirka / 2 - 100, sirka / 2 + 100), 1)) for k in range(1, 5)}
    kw = dict(sirka=sirka, led_delka=delka, led_pocet=n, **zad)
    r = sestav(**kw)
    p = r["parametry"]
    if not p["led"] or not p["led_svetlo"] or not p["stojky"]:
        check(p["led_pocet"] == 1 and all(p[k] is None for k in S.LED_PARAMETRY_Z), f"fuzz {i} {kw}: bez svitidla se pocet a polohy zahodi")
        continue
    pocitadlo += 1
    zc, w, m = meri(r)
    ne = min(n, nmax)
    dl = m[0][2] - m[0][1]
    check(len(m) == ne and p["led_pocet"] == ne, f"fuzz {i} {kw}: pocet {ne} ({len(m)}, {p['led_pocet']})")
    check(all(m[k + 1][1] - m[k][2] > -TOL for k in range(ne - 1)), f"fuzz {i} {kw}: svitidla se neprekryvaji ({[round(m[k + 1][1] - m[k][2], 2) for k in range(ne - 1)]})")
    check(all(m[k][0] < m[k + 1][0] for k in range(ne - 1)), f"fuzz {i} {kw}: poradi zleva doprava")
    check(all(lk >= -w / 2 - (1 - Q90) * dl - 0.15 and pk <= w / 2 + (1 - Q90) * dl + 0.15 for _, lk, pk in m), f"fuzz {i} {kw}: aspon 90 % delky kazdeho svitidla je nad profilem")
    check(m[-1][2] - m[0][1] <= w + LED_PREVIS + 0.2, f"fuzz {i} {kw}: rozpeti {m[-1][2] - m[0][1]:.1f} <= {w + LED_PREVIS:.0f}")
    check(not [x for x in r["problemy"] if x["kod"] in ("profil_led_kratky", "led_mimo_obrys")], f"fuzz {i} {kw}: bez problemu LED ({[x['kod'] for x in r['problemy']]})")
    auto = r["led_info"]["auto"]
    for k in range(ne):
        pk = p[f"led_z{k + 1}"]
        if pk is None:
            check(abs(m[k][0] - auto[k]) < 0.1, f"fuzz {i} {kw}: svitidlo {k + 1} je na automaticke poloze ({m[k][0]:.2f} vs {auto[k]})")
        else:
            check(abs(m[k][0] - pk) < TOL and abs(pk - auto[k]) >= 0.04, f"fuzz {i} {kw}: svitidlo {k + 1}: parametr = skutecna poloha ({pk} vs {m[k][0]:.2f}) a neni automaticky")
    check(all(p[f"led_z{k}"] is None for k in range(ne + 1, 5)), f"fuzz {i} {kw}: poloh nad poctem je None")
    r2 = sestav(**p)                                                         # idempotence: efektivni parametry zpet do generatoru = totez
    check(C.otisk(r2) == C.otisk(r) and r2["parametry"] == p and G.kanonicky_hash(r2["parametry"]) == G.kanonicky_hash(p), f"fuzz {i} {kw}: efektivni parametry znovu = stejny model a hash")
    li = r["led_info"]
    check(all(abs(a - b) < 0.1 for a, b in zip(li["polohy"], [c for c, _, _ in m])), f"fuzz {i} {kw}: led_info.polohy = mereni")
    for k in range(ne):
        lo, hi = li["meze"][k]
        check(lo - 0.06 <= li["polohy"][k] <= hi + 0.06, f"fuzz {i} {kw}: poloha {k + 1} lezi v mezich ({lo}, {li['polohy'][k]}, {hi})")
check(pocitadlo > 150, f"fuzz: dost konfiguraci se svitidlem ({pocitadlo})")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== kanonicka podoba: automaticka poloha = None")
for sirka, delka, nmax in KONF:
    for n in range(1, nmax + 1):
        base = dict(sirka=sirka, led_delka=delka, led_pocet=n)
        ra = sestav(**base)
        auto = ra["led_info"]["auto"]
        expl = {f"led_z{k + 1}": auto[k] for k in range(n)}
        re_ = sestav(**base, **expl)
        check(C.otisk(re_) == C.otisk(ra) and re_["parametry"] == ra["parametry"] and G.kanonicky_hash(re_["parametry"]) == G.kanonicky_hash(ra["parametry"]),
              f"{base}: polohy zadane presne jako automaticke = stejny model, parametry (None) i hash")
        if n >= 2:
            r1 = sestav(**base, led_z1=auto[0])
            check(C.otisk(r1) == C.otisk(ra), f"{base}: jen 1. svitidlo zadane jako automaticke = beze zmeny")

print("== bez svitidla se pocet a polohy zahodi")
for kw0 in (dict(led_svetlo=False), dict(led=False), dict(stojky=False), dict(sirka=900, led_delka=1200), dict(sirka=700, led_delka=1200)):
    kw = {**dict(sirka=1500, led_delka=600), **kw0}
    kw_zadane = dict(kw, led_pocet=3, led_z1=-100.0, led_z2=200.0)
    ra, rb = sestav(**kw), sestav(**kw_zadane)
    pb = rb["parametry"]
    check(pb["led_pocet"] == 1 and all(pb[k] is None for k in S.LED_PARAMETRY_Z), f"{kw0}: pocet a polohy se zahodi ({pb['led_pocet']}, {[pb[k] for k in S.LED_PARAMETRY_Z]})")
    check(C.otisk(ra) == C.otisk(rb) and G.kanonicky_hash(ra["parametry"]) == G.kanonicky_hash(rb["parametry"]), f"{kw0}: model i hash stejne jako bez pozadavku na svitidla")
    if "sirka" not in kw0:                                                   # (svitidlo, ktere se nevejde, se pozna az v generatoru: hash ze SUROVYCH parametru ho jeste nese)
        check(G.kanonicky_hash(S._norm_parametry(kw_zadane)) == G.kanonicky_hash(S._norm_parametry(kw)), f"{kw0}: hash i z pozadovanych parametru je stejny (bez svitidla se neni co nest)")
check(sestav(sirka=900, led_delka=1200, led_pocet=2)["odebrano"] and not lampy(sestav(sirka=900, led_delka=1200, led_pocet=2)), "sirka 900, svitidlo 1200: LED se odebere jako dosud (i s pozadovanym poctem)")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== led_info: pridat / odebrat")
for sirka, delka, nmax in ((3000, 600, 4), (2000, 600, 3), (1500, 600, 2), (3000, 1200, 2), (1280, 1200, 1)):
    base = dict(sirka=sirka, led_delka=delka)
    r = sestav(**base)
    for krok in range(nmax):
        li = r["led_info"]
        if krok == nmax - 1:
            check(li["pridat"] is None and li["pocet"] == nmax, f"{base}: na maximu ({nmax}) neni co pridat")
            break
        pat = li["pridat"]
        check(pat is not None and pat["led_pocet"] == li["pocet"] + 1, f"{base} krok {krok}: nabidka 'pridat' ma pocet {li['pocet'] + 1} ({pat})")
        m_pred = [c for c, _, _ in meri(r)[2]]
        pars = {k: v for k, v in r["parametry"].items()}
        pars.update(pat)
        r = sestav(**pars)
        m_po = [c for c, _, _ in meri(r)[2]]
        check(len(m_po) == li["pocet"] + 1 and not r["problemy"], f"{base} krok {krok}: po pridani {li['pocet'] + 1} svitidel bez problemu ({len(m_po)})")
        # puvodni svitidla zustala na svych mistech (nektera z nabidek je jen "tesne vedle"), jinak se vsechna znovu vystredila (automaticke polohy)
        zbytek = list(m_po)
        zachovano = True
        for c in m_pred:
            j = next((i for i, v in enumerate(zbytek) if abs(v - c) < TOL), None)
            if j is None:
                zachovano = False
                break
            zbytek.pop(j)
        auto_po = all(pat[f"led_z{k + 1}"] is None for k in range(len(m_po)))
        check(zachovano or auto_po, f"{base} krok {krok}: pridani zachova polohy ostatnich, nebo vsechny znovu vystredi ({m_pred} -> {m_po}, {pat})")
    # odebrani kazdeho svitidla: ostatni zustanou
    li = r["led_info"]
    n = li["pocet"]
    if n >= 2:
        pred = [c for c, _, _ in meri(r)[2]]
        for k in range(n):
            pars = dict(r["parametry"])
            pars.update(li["odebrat"][k])
            r2 = sestav(**pars)
            po = [c for c, _, _ in meri(r2)[2]]
            ocek = [c for i, c in enumerate(pred) if i != k]
            check(len(po) == n - 1 and all(abs(a - b) < TOL for a, b in zip(po, ocek)), f"{base}: odebrani svitidla {k + 1} ze {n} zanecha ostatni na miste ({po} vs {ocek})")
            check(not r2["problemy"], f"{base}: po odebrani svitidla {k + 1} bez problemu")
    else:
        check(li["odebrat"] == [], f"{base}: u jednoho svitidla zadne odebrani po indexu")

print("== led_info: tvar a meze")
r = sestav(sirka=3000, led_delka=600, led_pocet=3, led_z1=-1000.0, led_z2=0.0, led_z3=900.0)
li = r["led_info"]
check(set(li) >= {"delka", "typy", "pocet", "max", "polohy", "auto", "meze", "pridat", "odebrat", "osa", "okraj", "stred", "telo"}, f"led_info ma vsechny klice ({sorted(li)})")
check(li["pocet"] == 3 and len(li["polohy"]) == 3 and len(li["auto"]) == 3 and len(li["meze"]) == 3 and len(li["odebrat"]) == 3, "led_info: delky seznamu odpovidaji poctu")
tel = li["telo"]
for k in range(3):
    lo, hi = li["meze"][k]
    v = li["polohy"]
    exp_lo = li["stred"][0] if k == 0 else v[k - 1] + tel
    exp_hi = li["stred"][1] if k == 2 else v[k + 1] - tel
    check(abs(lo - exp_lo) < 0.15 and abs(hi - exp_hi) < 0.15, f"led_info.meze[{k}] = [{exp_lo:.1f}, {exp_hi:.1f}] ({lo}, {hi})")
check(li["okraj"][1] - li["okraj"][0] > 2990 and abs(li["okraj"][0] + li["okraj"][1]) < 0.2, f"led_info.okraj = vnejsi okraje stolu vuci ose ({li['okraj']})")
check(not r["problemy"], "3 svitidla s mezerami: bez problemu")
# rozpeti skupiny (<= sirka + 47) omezuje i krajni svitidla: 2. svitidlo na horni mezi pousti 1. jen na (v2 + telo - (sirka + 47)); 1. na dolni mezi pousti 2. jen na (v1 - telo + sirka + 47)
rS = sestav(sirka=3000, led_delka=600, led_pocet=2, led_z1=-1100.0, led_z2=1241.2)
liS = rS["led_info"]
check(abs(liS["polohy"][1] - liS["stred"][1]) < 0.15 and abs(liS["meze"][0][0] - (liS["polohy"][1] + liS["telo"] - (3000 + LED_PREVIS))) < 0.2 and liS["meze"][0][0] > liS["stred"][0] + 50,
      f"led_info.meze: 1. svitidlo pri 2. na mezi: dolni mez z rozpeti skupiny ({liS['meze'][0]}, {liS['polohy']})")
rT = sestav(sirka=3000, led_delka=600, led_pocet=2, led_z1=-1241.2, led_z2=1100.0)
liT = rT["led_info"]
check(abs(liT["polohy"][0] - liT["stred"][0]) < 0.15 and abs(liT["meze"][1][1] - (liT["polohy"][0] - liT["telo"] + (3000 + LED_PREVIS))) < 0.2 and liT["meze"][1][1] < liT["stred"][1] - 50,
      f"led_info.meze: 2. svitidlo pri 1. na mezi: horni mez z rozpeti skupiny ({liT['meze'][1]}, {liT['polohy']})")
# Pridat: konkretni scenare (vedle posledniho / vedle prvniho, kdyz vpravo neni misto / do mezery) - jinak by stacilo vzdy znovu vystredit
for kw_, ocek_ in ((dict(sirka=3000, led_delka=600), [-31.7, 615.3]),
                    (dict(sirka=3000, led_delka=600, led_z1=900.0), [253.0, 900.0]),
                    (dict(sirka=3000, led_delka=600, led_pocet=2, led_z1=-1000.0, led_z2=900.0), [-1000.0, -353.0, 900.0])):
    r_ = sestav(**kw_)
    r2_ = sestav(**{**r_["parametry"], **r_["led_info"]["pridat"]})
    check(len(lampy(r2_)) == len(ocek_) and all(abs(a - b) < 0.2 for a, b in zip(stredy(r2_), ocek_)), f"{kw_}: Pridat -> {ocek_} ({stredy(r2_)})")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== 3D ovladani: casti, tahy, mereni, nabidky")


def ov_pro(**kw):
    r = sestav(**kw)
    return r, S.ovladani_3d(r)


r, ov = ov_pro(sirka=3000, led_delka=600, led_pocet=3, led_z1=-1000.0, led_z2=0.0, led_z3=900.0)
ids_casti = [c["id"] for c in ov["casti"]]
check(all(x in ids_casti for x in ("led", "led_1", "led_2", "led_3")) and "led_4" not in ids_casti, f"casti: led + led_1..led_3 ({[x for x in ids_casti if x.startswith('led')]})")
tahy = {t["id"]: t for t in ov["tahy"]}
check(all(f"led_z{k}" in tahy for k in (1, 2, 3)) and "led_z4" not in tahy, f"tahy led_z1..led_z3 ({[x for x in tahy if x.startswith('led_z')]})")
zc, w, mm = meri(r)
for k in (1, 2, 3):
    t = tahy[f"led_z{k}"]
    c, lk, pk = mm[k - 1]
    check(t["param"] == f"led_z{k}" and t["casti"] == [f"led_{k}"] and t["typ"] == "osa" and t["osa"] == [0.0, 0.0, 1.0] and t["faktor"] == 1.0, f"tah led_z{k}: parametr, cast, osa Z, faktor 1")
    check(abs(t["hodnota"] - c) < TOL, f"tah led_z{k}: hodnota = skutecna poloha ({t['hodnota']} vs {c:.2f})")
    lo, hi = t["min"], t["max"]
    # mez zkouskou: na mezi se svitidlo (a sousedi) nehnou; za mezi zbytek (levy soused / okraj) svitidlo zastavi
    rl = sestav(**dict(r["parametry"], **{f"led_z{k}": lo}))
    check(abs(stredy(rl)[k - 1] - lo) < 0.1, f"tah led_z{k}: svitidlo lze dat na minimum {lo}")
    rl2 = sestav(**dict(r["parametry"], **{f"led_z{k}": lo - 5.0}))
    check(abs(stredy(rl2)[k - 1] - lo) < 0.1, f"tah led_z{k}: pod minimum se zastavi na {lo} ({stredy(rl2)[k - 1]})")
    rh = sestav(**dict(r["parametry"], **{f"led_z{k}": hi}))
    check(abs(stredy(rh)[k - 1] - hi) < 0.1, f"tah led_z{k}: svitidlo lze dat na maximum {hi}")
    if k == 3:
        rh2 = sestav(**dict(r["parametry"], **{f"led_z{k}": hi + 5.0}))
        check(abs(stredy(rh2)[k - 1] - hi) < 0.1, f"tah led_z{k}: nad maximum se zastavi na {hi}")
    # mereni: vzorec mul * hodnota + add = skutecna vzdalenost
    for mr in t["mereni"]:
        hod = mr["mul"] * t["hodnota"] + mr["add"]
        if mr["label"] == "od levého okraje stolu":
            ocek = lk + w / 2
        elif mr["label"] == "od pravého okraje stolu":
            ocek = w / 2 - pk
        elif mr["label"] == "od levého svítidla":
            ocek = lk - mm[k - 2][2]
        elif mr["label"] == "od pravého svítidla":
            ocek = mm[k][1] - pk
        else:
            ocek = None
        check(ocek is not None and abs(hod - ocek) < 0.2, f"tah led_z{k}: mereni '{mr['label']}' = {hod:.2f} mm (zmereno {ocek if ocek is None else round(ocek, 2)})")
        check(mr["param"] == f"led_z{k}", f"tah led_z{k}: mereni nese parametr tahu")
    stitky = [mr["label"] for mr in t["mereni"]]
    check(("od levého svítidla" in stitky) == (k > 1) and ("od pravého svítidla" in stitky) == (k < 3) and "od levého okraje stolu" in stitky and "od pravého okraje stolu" in stitky, f"tah led_z{k}: stitky mereni ({stitky})")
# vzdalenost se meni spolu s tahem (kontrola smeru mul): posun o +20 mm -> vzdalenost od praveho okraje se zmensi o 20
t2 = tahy["led_z2"]
for mr in t2["mereni"]:
    d0, d1 = mr["mul"] * t2["hodnota"] + mr["add"], mr["mul"] * (t2["hodnota"] + 20) + mr["add"]
    check((mr["label"].startswith("od levého") and abs(d1 - d0 - 20) < 1e-9) or (mr["label"].startswith("od pravého") and abs(d1 - d0 + 20) < 1e-9), f"tah led_z2: smer mereni '{mr['label']}'")

# nabidky skupin
cast = {c["id"]: c for c in ov["casti"]}
for k in (1, 2, 3):
    c = cast[f"led_{k}"]
    check(c["priorita"] > cast["led"]["priorita"] and c["param"] == ["led_pocet", f"led_z{k}"], f"cast led_{k}: vyssi priorita nez cele osvetleni, parametry")
    men = {m["text"]: m for m in c["menu"]}
    odeb = men["Odebrat toto svítidlo"]
    pars = dict(r["parametry"])
    pars.update(odeb["nastav"])
    r2 = sestav(**pars)
    pred = stredy(r)
    ocek = [x for i, x in enumerate(pred) if i != k - 1]
    check(not odeb["zakazano"] and len(lampy(r2)) == 2 and all(abs(a - b) < TOL for a, b in zip(stredy(r2), ocek)), f"nabidka led_{k}: Odebrat toto svitidlo -> 2 svitidla, ostatni na miste ({stredy(r2)} vs {ocek})")
    vr = men["Vrátit svítidlo na výchozí místo"]
    je_auto = r["parametry"][f"led_z{k}"] is None
    check(bool(vr["zakazano"]) == je_auto and vr["nastav"] == {f"led_z{k}": None}, f"nabidka led_{k}: Vratit na vychozi misto {'zakazano' if je_auto else 'povoleno'} ({vr['zakazano']})")
    if not je_auto:
        pars = dict(r["parametry"])
        pars.update(vr["nastav"])
        r3 = sestav(**pars)
        pol3, aut3 = r3["led_info"]["polohy"][k - 1], r3["led_info"]["auto"][k - 1]
        check(abs(pol3 - aut3) < 0.06 or pol3 > aut3, f"nabidka led_{k}: po vraceni je svitidlo na automaticke poloze, nebo (kdyz tam stoji soused) tesne vedle nej ({pol3} vs {aut3})")
men = {m["text"]: m for m in cast["led"]["menu"]}
check(men["Přidat svítidlo LED"]["nastav"] == r["led_info"]["pridat"] and not men["Přidat svítidlo LED"]["zakazano"], "nabidka led: Pridat svitidlo = led_info.pridat")
r4, ov4 = ov_pro(sirka=3000, led_delka=600, led_pocet=4)
men4 = {m["text"]: m for m in [c for c in ov4["casti"] if c["id"] == "led"][0]["menu"]}
check(men4["Přidat svítidlo LED"]["zakazano"] and men4["Přidat svítidlo LED"]["duvod"] and men4["Přidat svítidlo LED"]["nastav"] is None, "nabidka led: na maximu je Pridat zakazano s duvodem")
r5, ov5 = ov_pro(sirka=1280)
c5 = {c["id"]: c for c in ov5["casti"]}
check("led_1" in c5 and "led_2" not in c5, f"jedno svitidlo: cast led_1 (a zadna dalsi)")
m5 = {m["text"]: m for m in c5["led_1"]["menu"]}
check(m5["Odebrat toto svítidlo"]["nastav"] == {"led_svetlo": False}, "jedno svitidlo: Odebrat toto svitidlo = led_svetlo False")
check(c5["led_1"]["label"] == "Svítidlo LED" and [t["label"] for t in ov5["tahy"] if t["id"] == "led_z1"] == ["Posun svítidla LED"], "jedno svitidlo: popisky bez cisla")
check(c5["led_1"]["priorita"] > c5["led"]["priorita"], "jedno svitidlo: vetsi priorita nez cele osvetleni")
vr5 = m5["Vrátit svítidlo na výchozí místo"]
check(vr5["zakazano"] and vr5["duvod"] == "Už je na výchozím místě." and vr5["nastav"] == {"led_z1": None}, f"jedno svitidlo na vychozim miste: 'Vratit na vychozi misto' je zakazano s duvodem ({vr5})")
t5 = [t for t in ov5["tahy"] if t["id"] == "led_z1"][0]
check(t5["min"] < t5["hodnota"] < t5["max"] and abs(t5["hodnota"] - (-31.7)) < 0.1, f"jedno svitidlo na uzkem stole: tah ma rozsah ({t5['min']}, {t5['hodnota']}, {t5['max']})")
check(len([t for t in ov5["tahy"] if t["id"].startswith("led_z")]) == 1 and [t["id"] for t in ov5["tahy"]].count("led_rameno") == 1, "jedno svitidlo: tah led_z1 + dosavadni led_rameno")
for kw in (dict(led_svetlo=False), dict(led=False), dict(stojky=False)):
    rr, oo = ov_pro(**kw)
    check(not [c for c in oo["casti"] if c["id"].startswith("led_")] and not [t for t in oo["tahy"] if t["id"].startswith("led_z")], f"{kw}: zadna svitidla = zadne casti ani tahy led_<k>")
# ovladani_3d se uz neplete u stolu bez LED (beze zmeny)
check([c["id"] for c in ov_pro(led=False)[1]["casti"] if c["id"].startswith("led")] == [], "led=False: v ovladani zadna cast led")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== zive tazeni svitidel proti modelu ze serveru")
spec = importlib.util.spec_from_file_location("test_stul_zive", os.path.join(C.REPO, "scripts", "2026-10-02_stul_testy", "test_stul_zive.py"))
Z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(Z)
VOLNA = dict(sirka=3000, led_delka=600, led_pocet=3, led_z1=-1000.0, led_z2=0.0, led_z3=900.0)          # tri svitidla s mezerami (misto na posun obema smery)
ZIVE = ((dict(sirka=1500, led_delka=600, led_pocet=2), "led_z1", (-80.0, -20.0)),            # 2 svitidla 600 na stole 1500 stoji tesne (vpravo neni misto), vlevo je 136 mm
        (dict(sirka=1500, led_delka=600, led_pocet=2), "led_z2", (+40.0, +20.0)),
        (VOLNA, "led_z1", (+60.0, -40.0)),
        (VOLNA, "led_z2", (+60.0, -90.0)),
        (VOLNA, "led_z3", (+40.0, -50.0)),
        (dict(sirka=3000, led_delka=1200, led_pocet=2), "led_z2", (+25.0, +60.0)),
        (dict(sirka=1280), "led_z1", (+50.0, -60.0)),
        (dict(sirka=2000, led_delka=600, led_pocet=2, vzpery=True), "led_z1", (-50.0,)),
        (dict(sirka=1500, led_delka=600, led_pocet=2, led_rameno=900), "led_z2", (+20.0,)))
for par, tid, zmeny in ZIVE:
    for zm in zmeny:
        j = f"{tid} {par} {zm:+.0f} mm"
        res = Z.porovnej(par, tid, zm, 0.05, j)
        if not res:
            check(False, f"{j}: porovnani se nepovedlo (chybi tah / zmenil se pocet dilu)")
            continue
        chyby, r0_ = res[0], res[5]
        lamp = [i for i, d in enumerate(r0_["dily"]) if d["part_id"] in C.LED_PARTY]
        lim = lambda i: 0.3 if r0_["dily"][i]["part_id"] == "product_4933" else 0.05          # noqa: E731 - desky stejne jako v puvodnim testu
        nej = max(chyby, key=lambda ci: ci[0] / lim(ci[1])) if chyby else (0, -1)
        check(chyby and all(c <= lim(i) for c, i in chyby), f"{j}: zive tazeni = model ze serveru (nejvetsi odchylka {nej[0]:.3f} mm u dilu {nej[1]})")
        ch_led = [c for c, i in chyby if i in lamp]
        check(len(lamp) >= 1 and ch_led and max(ch_led) <= 0.05, f"{j}: svitidla ({len(lamp)} ks) sedi s modelem ({max(ch_led) if ch_led else None})")
check(not Z.FAILS, f"pomocna kontrola z test_stul_zive.py nehlasi chybu ({Z.FAILS[:2]})")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== hash")
H = lambda **kw: G.kanonicky_hash(S._norm_parametry(kw))                       # noqa: E731
check(H(sirka=1280) == H(sirka=1280, led_pocet=1) == H(sirka=1280, led_pocet=1, led_z2=100.0), "uzky stul (vejde se jedno svitidlo): pocet 1 a nesmyslna 2. poloha se do hashe nenesou")
h1 = H(sirka=1500, led_delka=600)
h2 = H(sirka=1500, led_delka=600, led_pocet=2)
check(h1 != h2, "sirsi stul: 1 svitidlo a 2 svitidla maji ruzny hash")
check(H(sirka=1500, led_delka=600, led_pocet=1) == h1, "sirsi stul: led_pocet=1 explicitne = vychozi")
check(H(sirka=1500, led_delka=600, led_z1=50.04) == H(sirka=1500, led_delka=600, led_z1=50.0) != H(sirka=1500, led_delka=600, led_z1=50.1), "hash: poloha se zaokrouhluje na 0,1 mm uz ve vstupu (50,04 = 50,0, 50,1 je jina)")
check(H(sirka=1500, led_delka=600, led_z2=100.0) == h1, "sirsi stul: poloha neexistujiciho 2. svitidla (pocet 1) se do hashe nenese")
check(H(sirka=1500, led_delka=600, led_z1=50.0) != h1 and H(sirka=1500, led_delka=600, led_z1=50.0) != H(sirka=1500, led_delka=600, led_z1=60.0), "poloha svitidla meni hash (ruzne polohy = ruzne hashe)")
check(H(sirka=1500, led_delka=600, led_pocet=2, led_z1=50.0) != H(sirka=1500, led_delka=600, led_pocet=2), "poloha 1. svitidla pri poctu 2 meni hash")
check(H(sirka=1500, led_delka=600, led_svetlo=False, led_pocet=2, led_z1=5.0) == H(sirka=1500, led_delka=600, led_svetlo=False) == H(sirka=1500, led_svetlo=False), "bez svitidla se pocet ani polohy do hashe nenesou")
check(H(sirka=1500, led=False, led_pocet=3) == H(sirka=1500, led=False), "bez LED se pocet nenese")
# SSE ignoruje
rs0, rs1 = sestav(system=41), sestav(system=41, led_pocet=3, led_z1=100.0)
check(rs1["parametry"]["led_pocet"] == 1 and rs1["parametry"]["led_z1"] is None and C.otisk(rs0) == C.otisk(rs1) and G.kanonicky_hash(rs0["parametry"]) == G.kanonicky_hash(rs1["parametry"]), "SSE (system 41): pocet a polohy svitidel se ignoruji")
check(all(k in __import__("stul_sse").IGNOROVANE for k in ("led_pocet",) + S.LED_PARAMETRY_Z), "SSE: IGNOROVANE nese led_pocet a led_z1..4")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== GLB, lux, kusovnik")
for kw in (dict(sirka=3000, led_delka=600, led_pocet=4), dict(sirka=3000, led_delka=600, led_pocet=3, led_z1=-1000.0, led_z2=0.0, led_z3=900.0), dict(sirka=1500, led_delka=600, led_pocet=2, led_z1=-480.0), dict(sirka=3000, led_delka=1200, led_pocet=2)):
    r = sestav(**kw)
    try:
        h, glb = G.model_pro_parametry(r["parametry"])
        check(len(glb) > 100000 and h == G.kanonicky_hash(r["parametry"]), f"{kw}: GLB se slozi ({len(glb)} B), hash = kanonicky hash")
    except Exception as e:  # noqa: BLE001
        check(False, f"{kw}: GLB se neslozilo ({type(e).__name__}: {e})")
    oc = O.osvetleni(r, G._transformuj)
    zc, w, mm = meri(r)
    check(oc is not None and len(oc["lights"]) == len(mm), f"{kw}: lux data: {len(mm)} svitidel ({oc and len(oc['lights'])})")
    if oc:
        sv = sorted(((l["startMm"][2] + l["endMm"][2]) / 2.0 - zc for l in oc["lights"]))
        check(all(abs(a - b) < 0.1 for a, b in zip(sv, [c for c, _, _ in mm])), f"{kw}: lux data: polohy svitidel = zmerene stredy ({[round(x, 1) for x in sv]} vs {[round(c, 1) for c, _, _ in mm]})")
    ks = [d for d in r["dily"] if d["part_id"] in C.LED_PARTY]
    check(len(ks) == r["parametry"]["led_pocet"], f"{kw}: pocet dilu svitidel = led_pocet")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("== ZLATY OTISK (stav PRED zmenou, 873 konfiguraci)")
zlaty = json.load(open(C.GOLDEN, encoding="utf-8"))
radky = [(json.loads(k), v) for k, v in zlaty.items()]
zmenene = beze_zmeny = 0
for p, st in radky:
    r = sestav(**p)
    nove = {"hash": G.kanonicky_hash(r["parametry"]), "otisk": C.otisk(r), "problemy": sorted(x.get("kod") for x in r["problemy"]), "odebrano": sorted(o["volba"] for o in r["odebrano"]),
            "spoju": int(r["pocet_spoju"]), "led": C.pocet_svitidel(r)}
    if st["led"] >= 2:
        zmenene += 1
        check(nove["led"] == 1, f"zlaty {p}: drive {st['led']} svitidla automaticky, ted vychozi jedno ({nove['led']})")
        r2 = sestav(**p, led_pocet=st["led"])                                                   # drivejsi chovani = rucne zadany drivejsi pocet
        n2 = {"otisk": C.otisk(r2), "problemy": sorted(x.get("kod") for x in r2["problemy"]), "odebrano": sorted(o["volba"] for o in r2["odebrano"]), "spoju": int(r2["pocet_spoju"]), "led": C.pocet_svitidel(r2)}
        check(all(n2[k] == st[k] for k in n2), f"zlaty {p}: led_pocet={st['led']} da PRESNE drivejsi model ({[k for k in n2 if n2[k] != st[k]]})")
        check(nove["hash"] != st["hash"] and G.kanonicky_hash(r2["parametry"]) != st["hash"], f"zlaty {p}: hash stolu s mnoha svitidly se zmenil (model se lisi od drivejsiho; novy hash neni zamenitelny se starym)")
    else:
        beze_zmeny += 1
        check(nove == {k: st[k] for k in nove}, f"zlaty {p}: beze zmeny ({[k for k in nove if nove[k] != st[k]]})")
check(zmenene == 217 and beze_zmeny == 873 - 217, f"zlaty otisk: 217 stolu s drive automatickym poctem >= 2, ostatnich {873 - 217} beze zmeny ({zmenene}, {beze_zmeny})")

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:8]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
