#!/usr/bin/env python3
"""RAZITKA LOGA NA VSECH 3D MODELECH GENERATORU STOLU (bot8, 2026-10-08; WORKFLOW pravidlo 61, Robert: "razitka budou na vsech 3D modelech ve vsech generatorech").

`stul_glb.model_pro_parametry(parametry, razitka=None)`: razitka jsou VYCHOZI (RAZITKA_VYCHOZI = True), pravidla umisteni (`stul_razitka`) beze zmeny. Hermeticky (bez DB); verejnou routu hlida test_razitka_shop.py.

  A  model: vychozi = model s razitky (bajt po bajte jako `razitka=True`), `razitka=False` = holy model; pro systemy 30 / 35 / 40 / 41 / 45 a 3-4 konfigurace: platne GLB (hlavicka, delky),
     uzlu o pocet razitek vic (nove uzly NA KONCI, drivejsi uzly beze zmeny), jedno logo = JEDEN sdileny mesh (+1 mesh, +1 material), spec (box, koty, celo, pohyby) stejna jako u holeho modelu
  B  vedlejsi cache (posun, rozsahy, extra) po vychozim modelu = presne cache po holem modelu -> `vodici` (uchyty ve 3D, payload luxu, zive tazeni) je stejne
  C  cache: vychozi model je jen v cache razitek (nestavi se dvakrat), holy model jen v `_GLB_CACHE`, obe se drzi v mezi CACHE_MAX, horky model po vytlaceni vedlejsi cache se prestavi bez chyby
  D  komprimovana cache GLB (`zakoduj_pro_klienta`): model s razitky a bez nich (STEJNY hash) se nezameni, obe se rozbali na vstup (br i gzip), v obou poradich
  E  vaha: razitka pridavaji ~0,5 MB surove (sdileny mesh loga) bez ohledu na pocet razitek, po brotli < 200 KB
  F  loga lezi nejvyse o 3,5 mm mimo `spec.box` (relief loga 3 mm): rozmery, kamera a koty modelu se razitky nemeni
Spusteni: api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/test_razitka_vychozi.py     (STUL_API_OVERRIDE=<adresar api> = kandidat)   Mutace: mutace.py"""
import gzip
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_razitka as RZ  # noqa: E402

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


def vycisti():
    for c in (G._GLB_CACHE, G._META_CACHE, G._ROZSAHY_CACHE, G._EXTRA_CACHE, G._GLB_RAZITKA_CACHE, G._GLB_KOMPR):
        c.clear()


def gltf(b):
    """(json, hlavicka-ok): GLB 2.0: magic, verze, delka souboru = len(b), prvni chunk JSON."""
    magic, ver, celkem = struct.unpack_from("<III", b, 0)
    dj, tj = struct.unpack_from("<II", b, 12)
    ok = magic == 0x46546C67 and ver == 2 and celkem == len(b) and tj == 0x4E4F534A and 20 + dj <= len(b)
    return json.loads(b[20:20 + dj].decode("utf-8")), ok


def spec(js):
    return js["scenes"][0]["extras"]["v3d"]


def sestav(p):
    r = S.sestav_stul(**p)
    return r, r["parametry"], G.kanonicky_hash(r["parametry"])


def konfigurace():
    out = []
    for sy in (30, 35, 40, 41, 45):
        if sy == 41:                                                          # SSE: jen sirka (hloubka a dalsi volby systemu 41 nema)
            out += [dict(system=sy), dict(system=sy, sirka=2400)]
            continue
        out += [dict(system=sy), dict(system=sy, sirka=2400, hloubka=1100), dict(system=sy, sirka=3000, hloubka=1400, police=2), dict(system=sy, led=False, stojky=False)]
    return out


def jako_json(o):
    return json.dumps(o, sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))


def vodici_pro(p, holy):
    """`vodici(parametry, vysledek)` jako ho vola resolve (vysledek generatoru + `ovladani_scena`), nad prazdnymi cache; holy=True = razitka vypnuta jako vychozi."""
    vycisti()
    r, par, h = sestav(p)
    r["ovladani_scena"] = S.ovladani_3d(r)
    G.RAZITKA_VYCHOZI = not holy
    try:
        return G.vodici(par, r)
    finally:
        G.RAZITKA_VYCHOZI = True


def kvat_matice(q):
    return S.kvat_na_matici(list(q))


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("A) vychozi model = model s razitky; razitka=False = holy model")
check(getattr(G, "RAZITKA_VYCHOZI", None) is True, f"RAZITKA_VYCHOZI je True ({getattr(G, 'RAZITKA_VYCHOZI', '(neni)')})")
VELIKOSTI = []
LOGO_MESHE = set()
for p in konfigurace():
    vycisti()
    r, par, h = sestav(p)
    popis = json.dumps(p, sort_keys=True)
    hd, d = G.model_pro_parametry(par)
    check(hd == h, f"{popis}: hash vychoziho modelu = kanonicky hash")
    s = G.model_pro_parametry(par, razitka=True)[1]
    b = G.model_pro_parametry(par, razitka=False)[1]
    check(d == s, f"{popis}: vychozi model = model s razitky (bajt po bajte)")
    check(d != b and len(d) > len(b), f"{popis}: vychozi model se lisi od holeho a je vetsi ({len(d)} vs {len(b)})")
    n = len(RZ.razitka(r, h))
    check(n >= 1, f"{popis}: stul ma aspon jedno razitko ({n})")
    jd, okd = gltf(d)
    jb, okb = gltf(b)
    check(okd and okb, f"{popis}: hlavicky GLB jsou platne (magic, verze 2, delka souboru, prvni chunk JSON)")
    check(len(jd["nodes"]) - len(jb["nodes"]) == n, f"{popis}: uzlu o pocet razitek vic ({len(jd['nodes'])} - {len(jb['nodes'])} = {n})")
    check(len(jd["meshes"]) - len(jb["meshes"]) == 1 and len(jd["materials"]) - len(jb["materials"]) == 1, f"{popis}: logo = JEDEN novy mesh a JEDEN novy material (instance uzlu)")
    nove = jd["nodes"][len(jb["nodes"]):]
    meshe = {x.get("mesh") for x in nove}
    check(len(meshe) == 1 and None not in meshe, f"{popis}: vsechna nova razitka sdili jeden mesh ({meshe})")
    LOGO_MESHE |= meshe
    check(jd["nodes"][:len(jb["nodes"])] == jb["nodes"], f"{popis}: drivejsi uzly beze zmeny a na stejnych mistech (razitka jsou pripojena na konec)")
    check(all(x["name"] == f"n{i}" for i, x in enumerate(jd["nodes"]) if "name" in x and x["name"].startswith("n") and x["name"][1:].isdigit()), f"{popis}: uzly se jmenuji n<index>")
    check("logo" not in json.dumps(jd).lower(), f"{popis}: v GLB nikde retezec 'logo'")
    sd, sb = spec(jd), spec(jb)
    check(sd == sb, f"{popis}: spec (box, koty, celo, pohyby, vzhled) se razitky nemeni")
    check(jd["scenes"][0]["nodes"][:len(jb["scenes"][0]["nodes"])] == jb["scenes"][0]["nodes"] and len(jd["scenes"][0]["nodes"]) == len(jb["scenes"][0]["nodes"]) + n, f"{popis}: korenove uzly sceny = drivejsi + razitka")
    VELIKOSTI.append((p.get("system"), n, len(d) - len(b)))

check(len(LOGO_MESHE) >= 1, "razitka pouzivaji mesh loga")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("B) vedlejsi cache po vychozim modelu = cache po holem modelu (uchyty ve 3D, luxy, zive tazeni)")
for p in (dict(system=30), dict(system=40, sirka=2400), dict(system=45, hloubka=1800), dict(system=35, police=3), dict(system=30, sirka=3000, led_pocet=2)):
    popis = json.dumps(p, sort_keys=True)
    r, par, h = sestav(p)
    vycisti()
    G.model_pro_parametry(par, razitka=False)
    holy = (np.array(G._META_CACHE[h], float).tolist(), jako_json(G._ROZSAHY_CACHE[h]), jako_json(G._EXTRA_CACHE[h]))
    vycisti()
    G.model_pro_parametry(par)
    check(h in G._META_CACHE and h in G._ROZSAHY_CACHE and h in G._EXTRA_CACHE, f"{popis}: vychozi model naplni vedlejsi cache")
    vychozi = (np.array(G._META_CACHE[h], float).tolist(), jako_json(G._ROZSAHY_CACHE[h]), jako_json(G._EXTRA_CACHE[h]))
    check(vychozi == holy, f"{popis}: posun, rozsahy dilu i extra rozsahy po vychozim modelu = po holem")
    # vodici (uchyty ve 3D + payload luxu) z modelu s razitky = z holeho modelu (kazde volani nad cerstvym vysledkem generatoru: `vodici` s nim pracuje jako resolve)
    v_holy = vodici_pro(p, holy=True)
    v_vych = vodici_pro(p, holy=False)
    check(v_holy is not None and v_vych is not None, f"{popis}: `vodici` vraci uchyty i nad modelem s razitky ({v_vych is not None}) a nad holym ({v_holy is not None})")
    rz_vych = ((v_vych or {}).get("ovladani") or {}).pop("razitka", None)           # od razitka-tazeni (2026-10-08) nese vodici.ovladani navic pole `razitka` (popis pro zive tazeni; hlida test_razitka_tazeni.py)
    check(rz_vych is None or (isinstance(rz_vych, list) and len(rz_vych) >= 1), f"{popis}: pole `razitka` ve vodicich znackach je seznam razitek ({rz_vych})")
    check(jako_json(v_vych) == jako_json(v_holy), f"{popis}: `vodici` (uchyty, stredni noha, ovladani, luxy) nad modelem s razitky = nad holym (az na pole `razitka`)")
    check((v_vych or {}).get("ovladani"), f"{popis}: ovladani ve 3D je v odpovedi")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("C) cache")
r, par, h = sestav(dict(system=30))
vycisti()
hd, d1 = G.model_pro_parametry(par)
check(h in G._GLB_RAZITKA_CACHE and h not in G._GLB_CACHE, "vychozi model je jen v cache razitek (holy se kvuli vedlejsim cache nestavi navic)")
d2 = G.model_pro_parametry(par)[1]
check(d2 is d1, "druhe volani vrati tytez bajty z cache (zadne nove skladani)")
G.model_pro_parametry(par, razitka=False)
check(h in G._GLB_CACHE and h in G._GLB_RAZITKA_CACHE, "holy model je v `_GLB_CACHE`, razitkovy zustava")
check(G.model_pro_parametry(par)[1] is d1, "po holem modelu vychozi dal vraci razitkovy z cache")
del G._META_CACHE[h]
hd, d3 = G.model_pro_parametry(par)
check(h in G._META_CACHE and d3 == d1, "vytlacena vedlejsi cache: model se prestavi (stejne bajty) a cache se doplni, bez chyby")
vycisti()
posledni = None
for i in range(G.CACHE_MAX + 6):
    r_i, par_i, h_i = sestav(dict(system=30, sirka=1000 + 10 * i))
    r_i["ovladani_scena"] = S.ovladani_3d(r_i)
    G.model_pro_parametry(par_i)
    posledni = (r_i, par_i, h_i)
check(len(G._GLB_RAZITKA_CACHE) <= G.CACHE_MAX and len(G._META_CACHE) <= G.CACHE_MAX and len(G._ROZSAHY_CACHE) <= G.CACHE_MAX and len(G._EXTRA_CACHE) <= G.CACHE_MAX,
      f"cache nepresahnou {G.CACHE_MAX} polozek ({len(G._GLB_RAZITKA_CACHE)}, {len(G._META_CACHE)}, {len(G._ROZSAHY_CACHE)}, {len(G._EXTRA_CACHE)})")
check(G.vodici(posledni[1], posledni[0]) is not None, "horky (posledni) model ma po preplneni cache vodici znacky")
for i in range(G.CACHE_MAX + 6):                                              # starsi modely jsou vytlacene: znovu volani je prestavi, zadna chyba
    r_i, par_i, h_i = sestav(dict(system=30, sirka=1000 + 10 * i))
    hh, dd = G.model_pro_parametry(par_i)
    if hh != h_i or h_i not in G._META_CACHE:
        check(False, f"model #{i} po vytlaceni se neprestavil")
        break
else:
    check(True, "vsech 22 modelu po vytlaceni cache se prestavi a vedlejsi cache je kompletni")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("D) komprimovana cache GLB (hash je stejny, data jina)")
r, par, h = sestav(dict(system=40, sirka=2000))
vycisti()
b = G.model_pro_parametry(par, razitka=False)[1]
s = G.model_pro_parametry(par, razitka=True)[1]
for poradi in ("holy-prvni", "razitka-prvni"):
    G._GLB_KOMPR.clear()
    prvni, druhy = (b, s) if poradi == "holy-prvni" else (s, b)
    zp, kp = G.zakoduj_pro_klienta(h, prvni, "br")
    zd, kd = G.zakoduj_pro_klienta(h, druhy, "br")
    rozbal_br = getattr(G._brotli, "decompress", None)
    check(kp == "br" and kd == "br" and zp != zd, f"{poradi}: brotli vrati pro model s razitky a bez nich RUZNA data (stejny hash)")
    if rozbal_br:
        check(rozbal_br(zp) == prvni and rozbal_br(zd) == druhy, f"{poradi}: obe brotli verze se rozbali na svuj vstup")
    G._GLB_KOMPR.clear()
    gp, kgp = G.zakoduj_pro_klienta(h, prvni, "gzip")
    gd, kgd = G.zakoduj_pro_klienta(h, druhy, "gzip")
    check(kgp == "gzip" and gp != gd and gzip.decompress(gp) == prvni and gzip.decompress(gd) == druhy, f"{poradi}: gzip: ruzna data a oba se rozbali na svuj vstup")
zz, _ = G.zakoduj_pro_klienta(h, s, "br")
zz2, _ = G.zakoduj_pro_klienta(h, s, "br")
check(zz is zz2, "opakovane komprimovani stejneho modelu bere z cache (stejny objekt)")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("E) vaha")
rozdily = [v[2] for v in VELIKOSTI]
check(400_000 <= min(rozdily) and max(rozdily) <= 700_000, f"razitka pridavaji 0,4-0,7 MB surove ({min(rozdily)}..{max(rozdily)} B)")
n_min, n_max = min(v[1] for v in VELIKOSTI), max(v[1] for v in VELIKOSTI)
check(n_max > n_min and max(rozdily) - min(rozdily) < 40_000, f"narust nezavisi na poctu razitek ({n_min}..{n_max} razitek, rozdil narustu {max(rozdily) - min(rozdily)} B): logo je sdileny mesh")
r, par, h = sestav(dict(system=30))
vycisti()
b = G.model_pro_parametry(par, razitka=False)[1]
s = G.model_pro_parametry(par)[1]
zb, zs = G.zakoduj_pro_klienta("e" + h, b, "br")[0], G.zakoduj_pro_klienta("e" + h + "s", s, "br")[0]
check(len(zs) - len(zb) < 200_000, f"po brotli pribude < 200 KB ({len(zs) - len(zb)} B; {len(zb)} -> {len(zs)})")
vycisti()
t0 = time.time()
G.model_pro_parametry(par, razitka=False)
t_b = time.time() - t0
vycisti()
t0 = time.time()
G.model_pro_parametry(par)
t_s = time.time() - t0
print(f"  cas skladani vychoziho stolu 30: bez razitek {t_b * 1000:.0f} ms, s razitky {t_s * 1000:.0f} ms")
check(t_s < t_b * 3 + 0.5, f"skladani s razitky neni radove pomalejsi ({t_s:.2f} s vs {t_b:.2f} s)")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("F) loga nevycnivaji z obalky modelu o vic nez relief")
for p in konfigurace():
    vycisti()
    r, par, h = sestav(p)
    d = G.model_pro_parametry(par)[1]
    jd, _ = gltf(d)
    sp = spec(jd)
    lo, hi = np.array(sp["box"]["min"], float), np.array(sp["box"]["max"], float)
    if "mesh" not in jd["nodes"][-1] or "translation" not in jd["nodes"][-1]:
        check(False, f"{json.dumps(p, sort_keys=True)}: posledni uzel modelu neni razitko (logo)")
        continue
    logo_idx = jd["nodes"][-1]["mesh"]
    acc = jd["accessors"][jd["meshes"][logo_idx]["primitives"][0]["attributes"]["POSITION"]]
    a, b2 = np.array(acc["min"], float), np.array(acc["max"], float)
    rohy = np.array([[x, y, z] for x in (a[0], b2[0]) for y in (a[1], b2[1]) for z in (a[2], b2[2])])
    n_roz = len(RZ.razitka(r, h))
    uzly = jd["nodes"][-n_roz:]
    pts = np.vstack([rohy @ kvat_matice(u["rotation"]).T + np.array(u["translation"], float) for u in uzly])
    ven = max(float((lo - pts.min(axis=0)).max()), float((pts.max(axis=0) - hi).max()), 0.0)
    check(ven <= 3.5 + 1e-6, f"{json.dumps(p, sort_keys=True)}: logo vycnivaji z `spec.box` nejvyse o {ven:.2f} mm (<= 3,5)")

print(f"\nvysledek: {OK} OK, {len(FAILS)} chyb")
sys.exit(1 if FAILS else 0)
