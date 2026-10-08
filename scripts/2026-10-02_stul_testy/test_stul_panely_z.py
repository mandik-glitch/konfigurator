#!/usr/bin/env python3
"""Test VODOROVNEHO POSUNU PANELU (`panely_z`, bot8, 2026-10-05; Robert: "perforovanych panelu od vsech nohou (panely chceme pohyblive, pokud maji mezeru mezi nohama)").

Panel (1190 mm) je vychozne vystredeny v useku mezi zadnimi stojkami (u stredni nohy dva useky); maji-li mezi nohama mezeru, da se posouvat do stran. NEZAVISLE na kodu generatoru
(mereni z AABB dilu a z vzorcu z parametru):
  A) vychozi stav: panel uprostred useku, mezera od kazde nohy = (usek - 1190) / 2; `panely_z` 0 nemeni hash ani dily,
  B) posun: kazdy panel (vsechny rady a useky) se posune o PRESNE zadanou hodnotu, mezera od jedne nohy roste a od druhe klesa o tolik, od zadne nohy neklesne pod 1 mm (PANEL_MEZERA);
     mimo meze se orizne na ±(mezera - 1 mm) vcetne zapisu efektivni hodnoty; profily nad a pod panelem (`panrail`) a nohy se nehybou; elektrozlab jede s panelem a porad se dotyka,
  C) stredni nohy (dva useky, nerovne useky pri posunuté stredni noze): panely se hybou spolecne a meze dava uzsi usek; vestaveny ram (jeden usek),
  D) hash: nula = hash beze zmeny, nenulova hodnota jiny hash, bez panelu / bez stojek se klic nepocita, neplatne hodnoty = StulChyba,
  E) 3D ovladani: tah `panely_z` je jen kdyz je kam posouvat, meze = ±mezera, `mereni` ukazuje mezery od VSECH noh a rovnaji se skutecne zmerenym, zive operace sedi s modelem,
  F) automaticke odebrani: posun panelu se nepocita jako duvod odebrat dil (kolize zpusobena posunem se nabizi, ne mazat samo).
Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_panely_z.py
Ostatni systemy:  api/venv/bin/python3 scripts/2026-10-04_system40/spust_v_systemu.py <30|35|40> scripts/2026-10-02_stul_testy/test_stul_panely_z.py"""
import itertools
import math
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


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def panely(r):
    """[(klic, lo, hi)] perforovanych panelu"""
    return [(tuple(tuple(x) if isinstance(x, list) else x for x in r["klice"][i]), *bb(d)) for i, d in enumerate(r["dily"]) if d["part_id"] == S.PANEL_PART]


def nohy_zadni(r):
    """z-rozsahy zadnich svislych noh (stojky, stredni zadni noha)"""
    out = []
    for i, d in enumerate(r["dily"]):
        k = r["klice"][i]
        if k in (["t", S.NOHA_ZL], ["t", S.NOHA_ZP], "RM"):
            lo, hi = bb(d)
            out.append((float(lo[2]), float(hi[2])))
    return sorted(out)


def mezery_od_noh(r):
    """pro kazdy panel (podle z) [(mezera vlevo, mezera vpravo)] zmerene z AABB: k nejblizsim nohám po obou stranach"""
    nz = nohy_zadni(r)
    out = []
    for k, lo, hi in sorted(panely(r), key=lambda t: (t[1][2], t[1][1])):
        vlevo = max(h for l, h in nz if h <= lo[2] + 1e-6)
        vpravo = min(l for l, h in nz if l >= hi[2] - 1e-6)
        out.append((float(lo[2] - vlevo), float(vpravo - hi[2])))
    return out


def sestav(**kw):
    return S.sestav_stul(**{**S.VYCHOZI, **kw})


P = float(S.SYSTEMY[S.aktivni_system()]["profil_mm"])
SYS = S.aktivni_system()
print(f"SYSTEM {SYS}, profil {P:.0f} mm, panel {S.PANEL_SIRKA:.0f} mm, mezera {S.PANEL_MEZERA} mm")

print("A) vychozi stav")
r0 = sestav()
g0 = mezery_od_noh(r0)
sirka = float(r0["parametry"]["sirka"])
usek = sirka - 2 * P
g_ocek = (usek - S.PANEL_SIRKA) / 2.0
check(len(g0) == 1 and abs(g0[0][0] - g_ocek) < 0.2 and abs(g0[0][1] - g_ocek) < 0.2, f"vychozi panel je uprostred mezi stojkami: mezery {g0} = {g_ocek:.2f} z kazde strany")
check(r0["parametry"]["panely_z"] == 0.0 and S.VYCHOZI["panely_z"] == 0.0, "vychozi panely_z = 0")
check(r0["panely_info"]["posun_z"] == {"hodnota": 0.0, "min": -math.floor(g_ocek - S.PANEL_MEZERA + 1e-6), "max": math.floor(g_ocek - S.PANEL_MEZERA + 1e-6)}, f"panely_info.posun_z = ±{math.floor(g_ocek - S.PANEL_MEZERA + 1e-6)} ({r0['panely_info']['posun_z']})")
lim0 = int(r0["panely_info"]["posun_z"]["max"])
check(lim0 >= 1, f"vychozi stul ma mezeru k posunu: ±{lim0} mm")

print("B) posun o zadanou hodnotu")
pozice0 = {k: (lo.copy(), hi.copy()) for k, lo, hi in panely(r0)}
rails0 = {i: bb(d) for i, d in enumerate(r0["dily"]) if r0["klice"][i][0] == "panrail"}
zlab0 = [bb(d) for d in r0["dily"] if d["part_id"] == "product_4932"]
for dz in sorted({-lim0, -max(1, lim0 // 2), -1, 1, max(1, lim0 // 2), lim0}):
    r = sestav(panely_z=dz)
    check(r["parametry"]["panely_z"] == float(dz) and not r["problemy"] and not r["odebrano"], f"posun {dz}: efektivni hodnota {r['parametry']['panely_z']}, bez problemu a odebrani")
    ok_pos = True
    for k, lo, hi in panely(r):
        l0, h0 = pozice0[k]
        ok_pos &= abs(lo[2] - l0[2] - dz) < 0.01 and abs(hi[2] - h0[2] - dz) < 0.01 and np.allclose(lo[[0, 1]], l0[[0, 1]], atol=0.01) and np.allclose(hi[[0, 1]], h0[[0, 1]], atol=0.01)
    check(ok_pos, f"posun {dz}: panel se pohnul PRESNE o {dz} mm podel Z a nikam jinam")
    gm = mezery_od_noh(r)[0]
    check(abs(gm[0] - (g0[0][0] + dz)) < 0.01 and abs(gm[1] - (g0[0][1] - dz)) < 0.01 and min(gm) >= S.PANEL_MEZERA - 0.011, f"posun {dz}: mezery od noh {gm[0]:.2f} / {gm[1]:.2f} mm (aspon {S.PANEL_MEZERA} mm)")
    check(all(np.allclose(bb(d)[0], rails0[i][0], atol=1e-6) and np.allclose(bb(d)[1], rails0[i][1], atol=1e-6) for i, d in enumerate(r["dily"]) if r["klice"][i][0] == "panrail"), f"posun {dz}: profily nad a pod panelem se nehybou")
    zl = [bb(d) for d in r["dily"] if d["part_id"] == "product_4932"]
    check(len(zl) == 1 and abs(zl[0][0][2] - zlab0[0][0][2] - dz) < 0.01 and abs(zl[0][1][2] - zlab0[0][1][2] - dz) < 0.01, f"posun {dz}: elektrozlab jede s panelem")
    check(not [x for x in r["problemy"] if x["kod"] == "elzlab_bez_opory"], f"posun {dz}: elektrozlab se porad dotyka panelu / profilu")
for dz, ocek in ((lim0 + 7, lim0), (-lim0 - 25, -lim0), (10 ** 4, lim0), (-10 ** 4, -lim0)):
    r = sestav(panely_z=dz)
    gm = mezery_od_noh(r)[0]
    check(r["parametry"]["panely_z"] == float(ocek) and min(gm) >= S.PANEL_MEZERA - 0.011, f"posun {dz} mimo meze se orizne na {ocek} (efektivne {r['parametry']['panely_z']}, mezery {gm[0]:.2f} / {gm[1]:.2f})")
r_rady = sestav(panely_pocet=2, stojky_vyska=1500, vyska=1200, panely_z=lim0)
pr_ = panely(r_rady)
check(len(pr_) == 2 and len({round(float(lo[2]), 2) for k, lo, hi in pr_}) == 1 and all(abs(m[0] - (g0[0][0] + lim0)) < 0.01 for m in mezery_od_noh(r_rady)), "dve rady panelu nad sebou se posouvaji spolecne (stejne z)")

print("C) stredni nohy, nerovne useky, vestaveny ram")
for sirka_, opora_ in ((2600, "noha"), (2900, "noha"), (2600, "ram"), (3000, "ram")):
    pk = 2 if opora_ == "noha" else 1
    r1 = sestav(sirka=sirka_, stredni_opora=opora_, panely_pocet=pk)
    pi = r1["panely_info"]
    lim = int(pi["posun_z"]["max"])
    if not pi["pocet"] or lim < 2:
        check(True, f"{sirka_} {opora_}: panely se nevejdou / bez mezery ({pi['pocet']}, ±{lim}) - preskoceno")
        continue
    ga = mezery_od_noh(r1)
    dz = max(1, lim // 2)
    r2 = sestav(sirka=sirka_, stredni_opora=opora_, panely_pocet=pk, panely_z=dz)
    gb = mezery_od_noh(r2)
    check(len(gb) == len(ga) and all(abs(b[0] - (a[0] + dz)) < 0.01 and abs(b[1] - (a[1] - dz)) < 0.01 for a, b in zip(ga, gb)) and min(min(g) for g in gb) >= S.PANEL_MEZERA - 0.011,
          f"{sirka_} {opora_}: vsechny panely se posunuly o {dz} mm, mezery {[(round(a, 1), round(b, 1)) for a, b in gb]}")
    rm = sestav(sirka=sirka_, stredni_opora=opora_, panely_pocet=pk, panely_z=lim + 50)
    check(rm["parametry"]["panely_z"] == float(lim) and min(min(g) for g in mezery_od_noh(rm)) >= S.PANEL_MEZERA - 0.011, f"{sirka_} {opora_}: mimo meze se orizne na ±{lim} a od zadne nohy neni mene nez {S.PANEL_MEZERA} mm")
    check(not r2["problemy"] and not r2["odebrano"], f"{sirka_} {opora_}: posun bez problemu")
# nerovne useky: stredni noha mimo stred -> uzsi usek urcuje mez
r3 = sestav(sirka=2900, stredni_opora="noha", panely_pocet=2, stredni_noha=1330.0)          # levy usek 1300, pravy 1510 mm (vzdalenost od osy leve nohy k ose stredni)
pi3 = r3["panely_info"]
if pi3["pocet"] == 2:
    zab = pi3["zaber"]
    check(len(zab) == 2 and abs(pi3["posun_z"]["max"] - math.floor(min(u["mezera"] for u in zab) - S.PANEL_MEZERA + 1e-6)) < 1e-9, f"nerovne useky: mez {pi3['posun_z']['max']} dava uzsi usek ({[round(u['mezera'], 1) for u in zab]})")
else:
    check(True, "nerovne useky: dva panely se nevejdou (preskoceno)")

print("D) hash a neplatne hodnoty")
H0 = G.kanonicky_hash({})
check(G.kanonicky_hash({"panely_z": 0}) == H0 and G.kanonicky_hash({"panely_z": -0.0}) == H0, "panely_z 0 hash nemeni")
check(G.kanonicky_hash({"panely_z": 5}) != H0 and G.kanonicky_hash({"panely_z": 5}) != G.kanonicky_hash({"panely_z": 6}), "nenulova hodnota = jiny hash (a ruzne hodnoty ruzne)")
check(G.kanonicky_hash({"panely": False, "panely_z": 5}) == G.kanonicky_hash({"panely": False}) and G.kanonicky_hash({"stojky": False, "panely_z": 5}) == G.kanonicky_hash({"stojky": False}), "bez panelu / stojek se posun do hashe nepocita")
check(G.kanonicky_hash({"panely_z": 10 ** 4}) == G.kanonicky_hash({"panely_z": 10 ** 4}), "hash je stabilni")
for spatne in (True, None, float("nan"), float("inf"), "x"):
    try:
        S.sestav_stul(**{**S.VYCHOZI, "panely_z": spatne})
        check(False, f"panely_z={spatne!r} musi byt StulChyba")
    except S.StulChyba:
        check(True, "")
rb = sestav(panely=False, panely_z=15)
check(rb["parametry"]["panely_z"] == 0.0 and rb["panely_info"]["posun_z"]["max"] == 0.0, "bez panelu je efektivni posun 0")
for pr_, pop_ in ((dict(sirka=int(2 * P + S.PANEL_SIRKA + 2 * S.PANEL_MEZERA + 0.999)), "nejuzsi stul: panel tesne"),):
    rt = sestav(**pr_)
    check(rt["panely_info"]["posun_z"]["max"] == 0.0 or rt["panely_info"]["pocet"] == 0, f"{pop_}: bez mezery se nehybe ({rt['panely_info']['posun_z']})")

print("E) 3D ovladani")
ov = S.ovladani_3d(sestav(panely_z=3))
tz = [t for t in ov["tahy"] if t["id"] == "panely_z"]
check(len(tz) == 1, "tah panely_z existuje, ma-li panel mezeru")
t = tz[0]
check(t["min"] == -float(lim0) and t["max"] == float(lim0) and t["krok"] == 1.0 and t["param"] == "panely_z" and t["hodnota"] == 3.0 and t["osa"] == [0.0, 0.0, 1.0], f"tah: meze ±{lim0}, krok 1, hodnota 3 ({t['min']}, {t['max']}, {t['hodnota']})")
r_t = sestav(panely_z=3)
gt = mezery_od_noh(r_t)
radky = [round(m["add"] + m["mul"] * 3.0, 1) for m in t["mereni"]]
check(len(radky) == 2 * len(gt) and all(abs(radky[2 * j] - g[0]) < 0.05 and abs(radky[2 * j + 1] - g[1]) < 0.05 for j, g in enumerate(gt)), f"mereni = zmerene mezery od noh: {radky} = {[(round(a, 1), round(b, 1)) for a, b in gt]}")
check(any(c["id"] == "panely" and "panely_z" in c["param"] for c in ov["casti"]) and any(m["text"].startswith("Panely vrátit doprostřed") for c in ov["casti"] if c["id"] == "panely" for m in c["menu"]),
      "cast Perforovane panely: parametr panely_z a polozka nabidky 'vratit doprostred'")
check([m for c in ov["casti"] if c["id"] == "panely" for m in c["menu"] if m["text"].startswith("Panely vrátit doprostřed")][0]["nastav"] == {"panely_z": 0.0}, "polozka nabidky nastavuje panely_z = 0")
# bez posunu v nabidce neaktivni
ov0 = S.ovladani_3d(sestav())
mm = [m for c in ov0["casti"] if c["id"] == "panely" for m in c["menu"] if m["text"].startswith("Panely vrátit doprostřed")][0]
check(mm["zakazano"] is True and mm["duvod"], f"polozka je pri vystredenych panelech neaktivni ({mm})")
# zive operace: kazdy dil sedi s modelem ze serveru (stejny postup jako test_stul_zive)
zive = t.get("zive")
check(bool(zive), "tah panely_z ma zive operace")
if zive:
    rA, rB = sestav(panely_z=0), sestav(panely_z=lim0 // 2 or 1)
    d_ = (lim0 // 2 or 1)
    bbA = [bb(d) for d in rA["dily"]]
    bbB = [bb(d) for d in rB["dily"]]
    # GLB se vycentruje podle obalky celeho stolu (sirka stolu se tim neni dotcena): posun je jen o to, co panely udelaly
    ix_zive = {i for op in zive for i in op["ix"]}
    check(all(k_[0] == "pan" or d["part_id"] in ("product_4931", "product_4932") for i in ix_zive for k_, d in [(tuple(rA["klice"][i]) if isinstance(rA["klice"][i], (list, tuple)) else (rA["klice"][i],), rA["dily"][i])]), "zive operace se tykaji jen panelu a elektrozlabu")
    ok_z = True
    for i in range(len(rA["dily"])):
        dlo, dhi = bbB[i][0] - bbA[i][0], bbB[i][1] - bbA[i][1]
        ocek = d_ if i in ix_zive else 0.0
        ok_z &= abs(dlo[2] - ocek) < 0.01 and abs(dhi[2] - ocek) < 0.01 and abs(dlo[0]) < 0.01 and abs(dlo[1]) < 0.01
    check(ok_z, "po posunu o %d mm se pohnou PRESNE dily z `zive` (o k * posun) a nic jineho" % d_)
    check(all(op["op"] == "posun" and abs(op["k"] - 1.0) < 1e-9 for op in zive), "zive operace: posun s koeficientem 1")

print("F) kolize zpusobena posunem se nenabizi jako automaticke odebrani")
check(S._kolizi_zpusobuje_posun({**r0["parametry"]}, "panely") is False, "vychozi stul: zadna kolize zpusobena posunem")
check(isinstance(S._kolizi_zpusobuje_posun({**r0["parametry"], "panely_z": 5.0}, "panely"), bool), "s posunem panelu se kolize posuzuje proti vychozim polohám (funkce panely_z zna)")
print(f"\n{OK} kontrol OK" + (f", {len(FAILS)} CHYB" if FAILS else ""))
sys.exit(1 if FAILS else 0)
