#!/usr/bin/env python3
"""Test skladani GLB konfigurovaneho stolu (api/stul_glb.py) - bot8, 2026-10-02. Bez DB.
Hlida: platny GLB (hlavicka, chunky, delky), obalka stolu vycentrovana (X/Z) s podlahou y=0, jednotky mm, zploštele uzly (zadne
jmeno dilu ani odkaz na katalog), pocet trojuhelniku = soucet dilu, materialy, spec pro viewer3d (kóty si viewer dela sam),
zavreny suplik (Y rozpeti modelu < 1000), kanonicky hash (poradi parametru nehraje roli), cache, dalsi rozmery meni obalku.
Spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_glb.py"""
import json
import os
import struct
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
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


def rozbal(data):
    magic, ver, celkem = struct.unpack("<III", data[:12])
    off, js, binc = 12, None, None
    while off < len(data):
        ln, typ = struct.unpack("<II", data[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(data[off + 8:off + 8 + ln])
        elif typ == 0x004E4942:
            binc = data[off + 8:off + 8 + ln]
        off += 8 + ln
    return magic, ver, celkem, js, binc


h0, glb0 = G.model_pro_parametry({}, razitka=False)
magic, ver, celkem, js, binc = rozbal(glb0)
check(magic == 0x46546C67 and ver == 2 and celkem == len(glb0), "platna GLB hlavicka a celkova delka")
check(len(glb0) % 4 == 0 and js["buffers"][0]["byteLength"] == len(binc), "zarovnani a delka bufferu")
check(len(js["materials"]) == 6 and len(js["meshes"]) == 7 and len(js["nodes"]) == 8, f"6 siti podle materialu + spodni suplik boxu jako vlastni sit (bot10, pohyb na klik) a jeho pivot ({len(js['meshes'])} siti, {len(js['nodes'])} uzlu)")
check(all(n["name"] == f"n{i}" for i, n in enumerate(js["nodes"]) if "mesh" in n) and [n["name"] for n in js["nodes"] if "mesh" not in n] == ["p1"] and js["nodes"][-1].get("children") == [6],
      "uzly s meshem maji zploštela jmena n0..n6, jediny dalsi uzel je prazdny pivot p1 se supliku pod sebou")
check(js["scenes"][0]["nodes"] == [0, 1, 2, 3, 4, 5, 7], "koren sceny: uzly materialu a pivot (suplik je jeho potomek)")
txt = json.dumps(js).lower()
check(not any(k in txt for k in ("product_", "object_", "katalog", "profil", "scene.html")), "v GLB neni jmeno dilu ani odkaz na katalog")
spec = js["scenes"][0]["extras"]["v3d"]
check(spec["u"] == "mm" and spec["up"] == [0, 1, 0] and [m["k"] for m in spec["motions"]] == ["drawer"] and spec["motions"][0]["pick"] == ["p1"] and spec["motions"][0]["steps"][0]["p"] == "p1",
      "spec: mm, nahoru Y, jediny pohyb = spodni suplik boxu (k=drawer, pivot p1, klik)")
check(isinstance(spec["dims"], list) and len(spec["dims"]) >= 9 and all(set(d) <= {"a", "b", "o", "t", "l", "m"} and {"a", "b", "o", "t", "l"} <= set(d) for d in spec["dims"]),
      f"spec: vlastni kóty generatoru (api/stul_koty.py; podrobne je zkousi test_stul_koty.py), pole a b o t l [m]: {len(spec['dims'])} kot")
mn = np.min([a["min"] for a in js["accessors"] if "min" in a], axis=0)
mx = np.max([a["max"] for a in js["accessors"] if "max" in a], axis=0)
check(abs(mn[1]) < 0.05 and abs(mn[0] + mx[0]) < 0.05 and abs(mn[2] + mx[2]) < 0.05, f"vycentrovano v X/Z, podlaha y=0 ({np.round(mn, 2)} {np.round(mx, 2)})")
check(abs(mx[1] - 1924.54) < 0.05 and abs(mx[2] - 682.5) < 0.1 and 800 < (mx[0] - mn[0]) < 850,
      f"obalka vychoziho stolu se zavrenym supliku: vyska 1924,5, sirka 1365 (vychozi 1280 + 85), hloubka ~840 ({np.round(mx - mn, 1)}; demo bot10 mela hloubku 1316 kvuli vysunutemu supliku)")
# pocet trojuhelniku = soucet trojuhelniku dilu
r0 = S.sestav_stul()
soucet = sum(len(G.nacti_mesh(d["part_id"])[2]) for d in r0["dily"])
tris = sum(a["count"] // 3 for a in js["accessors"] if a["type"] == "SCALAR")
check(soucet == tris, f"pocet trojuhelniku = soucet dilu ({tris} vs {soucet})")
# zavreny suplik
pos, _, _ = G.nacti_mesh("product_4930")
check(float(pos[:, 1].max() - pos[:, 1].min()) < 1000, "suplik v modelu je zavreny (Y rozpeti < 1000 mm)")
# normaly jednotkove
vn = [a for a in js["accessors"] if a["type"] == "VEC3" and "min" not in a]
vv = js["bufferViews"][vn[0]["bufferView"]]
nrm = np.frombuffer(binc, "<f4", vn[0]["count"] * 3, vv["byteOffset"]).reshape(-1, 3)
check(float(np.abs(np.linalg.norm(nrm, axis=1) - 1).max()) < 1e-3, "normaly jsou jednotkove")
# hash
a = G.kanonicky_hash({"sirka": 1500, "hloubka": 900})
b = G.kanonicky_hash({"hloubka": 900.0, "sirka": 1500.0})
c = G.kanonicky_hash({"sirka": 1510, "hloubka": 900})
check(a == b and a != c and len(a) == 16, "kanonicky hash: poradi/typ nehraje roli, jina konfigurace = jiny hash")
h1, g1 = G.model_pro_parametry({"sirka": 1500}, razitka=False)
h2, g2 = G.model_pro_parametry({"sirka": 1500}, razitka=False)
check(g1 is g2 and h1 == h2, "druhe volani stejne konfigurace jde z cache")
# rozmery se promitnou do obalky
_, g3 = G.model_pro_parametry({"sirka": 2400, "hloubka": 1000, "vyska": 900}, razitka=False)
js3 = rozbal(g3)[3]
mx3 = np.max([a["max"] for a in js3["accessors"] if "max" in a], axis=0)
mn3 = np.min([a["min"] for a in js3["accessors"] if "min" in a], axis=0)
check(mx3[2] - mn3[2] > 2400 and mx3[0] - mn3[0] > 1000 and abs(mx3[1] - (900 + 1084.5)) < 0.1, f"obalka 2400x1000x900 ({np.round(mx3 - mn3, 0)})")
# neplatny vstup
try:
    G.model_pro_parametry({"sirka": 100}, razitka=False); check(False, "mimo rozsah ma vyhodit chybu")
except S.StulChyba:
    check(True, "")
# deska s vyrezy = jeden souvisly povrch bez svu: horni plocha ma presne plochu desky minus otvory, steny jen na obvodu a u otvoru
def lamino_geometrie(parametry):
    _, glb = G.model_pro_parametry(parametry, razitka=False)
    _, _, _, jj, bb = rozbal(glb)
    pr = [p for m, p in zip(jj["meshes"], jj["materials"]) if p["pbrMetallicRoughness"]["roughnessFactor"] == 0.55 and p["pbrMetallicRoughness"]["metallicFactor"] == 0.0]
    idx = [i for i, m in enumerate(jj["materials"]) if m["pbrMetallicRoughness"].get("roughnessFactor") == 0.55 and m["pbrMetallicRoughness"].get("metallicFactor") == 0.0][0]
    prim = jj["meshes"][idx]["primitives"][0]
    acc = jj["accessors"]
    def citaj(i, ncomp, dtype):
        a = acc[i]; v = jj["bufferViews"][a["bufferView"]]
        return np.frombuffer(bb, dtype=dtype, count=a["count"] * ncomp, offset=v["byteOffset"]).reshape(-1, ncomp) if ncomp > 1 else np.frombuffer(bb, dtype=dtype, count=a["count"], offset=v["byteOffset"])
    P = citaj(prim["attributes"]["POSITION"], 3, "<f4").astype(float)
    T = citaj(prim["indices"], 1, "<u4").reshape(-1, 3)
    return P, T


def plocha_nahore(P, T):
    """Soucet plochy trojuhelniku s normalou +Y (horni plochy desek) - po vycentrovani modelu."""
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n = np.cross(b - a, c - a)
    return float(np.sum(0.5 * np.linalg.norm(n, axis=1)[n[:, 1] > 0.5 * np.linalg.norm(n, axis=1)]))


# (bez spodni police, aby se merila jen pracovni deska; katalogovy mesh bez vyrezu ma zkosene hrany, proto se plocha porovnava s presnym vzorcem)
P1, T1 = lamino_geometrie({"sirka": 1200, "police": 0, "vyrez1": True, "vyrez1_w": 300, "vyrez1_d": 200})
check(abs(plocha_nahore(P1, T1) - (800.0 * 1200.0 - 300.0 * 200.0)) < 5.0, f"deska s vyrezem: horni plocha = plocha desky minus otvor ({plocha_nahore(P1, T1):.0f} mm2)")


def plocha_svisla(P, T):
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n = np.cross(b - a, c - a); ln = np.linalg.norm(n, axis=1)
    return float(np.sum(0.5 * ln[np.abs(n[:, 1]) < 0.1 * ln]))


# zadne vnitrni svisle steny mezi kusy: svisle steny jen na obvodu desky a u otvoru (obvod x tloustka 18 mm)
P2, T2 = lamino_geometrie({"sirka": 1200, "police": 0, "vyrez1": True, "vyrez1_w": 300, "vyrez1_d": 200, "vyrez2": True, "vyrez2_w": 100, "vyrez2_d": 100, "vyrez2_z": 600.0})
steny_ocek = (2 * (800.0 + 1200.0) + 2 * (300 + 200) + 2 * (100 + 100)) * 18.0
check(abs(plocha_svisla(P2, T2) - steny_ocek) / steny_ocek < 0.005, f"svisle steny desky jen na obvodu a u otvoru ({plocha_svisla(P2, T2):.0f} vs {steny_ocek:.0f} mm2)")
check(abs(plocha_nahore(P2, T2) - (800.0 * 1200.0 - 300 * 200 - 100 * 100)) < 5.0, "dva vyrezy: horni plocha o oba otvory mensi")
# ---- sikme vzpery ramen LED: model je platny, spojky 3254 maji material "seda" (jako rohove spojky), obalka stolu se nemeni, trojuhelniky sedi, rozsahy vrcholu (zive tazeni) pokryvaji vzpery
PV = {"sirka": 1400, "vzpery": True, "vzpera_delka": 400}
rv = S.sestav_stul(**PV)
check(rv["parametry"]["vzpery"] and not rv["problemy"], "vzpery 1400/400: sestava bez problemu")
hv, gv = G.model_pro_parametry(PV, razitka=False)
jv = rozbal(gv)[3]
r_bez = S.sestav_stul(sirka=1400)
soucet_v = sum(len(G.nacti_mesh(d["part_id"])[2]) for d in rv["dily"])
check(soucet_v == sum(a["count"] // 3 for a in jv["accessors"] if a["type"] == "SCALAR"), "model se vzperami: pocet trojuhelniku = soucet dilu")
check(len(rv["dily"]) == len(r_bez["dily"]) + 6 and G.MATERIAL_DILU["product_3254"] == G.MATERIAL_DILU["product_3158"], "spojky 3254 maji stejny material jako rohove spojky 3158")
mnv = np.min([a["min"] for a in jv["accessors"] if "min" in a], axis=0)
mxv = np.max([a["max"] for a in jv["accessors"] if "max" in a], axis=0)
_, gb = G.model_pro_parametry({"sirka": 1400}, razitka=False)
jb = rozbal(gb)[3]
mnb = np.min([a["min"] for a in jb["accessors"] if "min" in a], axis=0)
mxb = np.max([a["max"] for a in jb["accessors"] if "max" in a], axis=0)
check(np.allclose(mxv - mnv, mxb - mnb, atol=0.05), f"vzpery se vejdou do obalky stolu (obalka stejna: {np.round(mxv - mnv, 1)} vs {np.round(mxb - mnb, 1)})")
check(all(n["name"] == f"n{i}" for i, n in enumerate(jv["nodes"]) if "mesh" in n) and not any(k in json.dumps(jv).lower() for k in ("product_", "object_", "katalog")), "GLB se vzperami: zadna jmena dilu")
# rozsahy vrcholu: vzpery maji rozsah (jsou to normalni dily), spojky 3254 v uzlu materialu "seda"; vodici vraci zive_rozsahy pro tahy
vod = G.vodici(PV, S.odpoved(PV))["ovladani"]
roz = vod["zive_rozsahy"]
check(len(roz) == len(rv["dily"]) and all(r is not None for r in roz[-6:]), "zive_rozsahy: i vzpery maji rozsah vrcholu v modelu")
kl_v = [tuple(k) if isinstance(k, list) else k for k in rv["klice"]]
check(all(any(c["id"] == "vzpery" for c in vod["casti"]) for _ in (0,)), "ovladani: cast 'vzpery' pro pravé tlacitko")
# neaktivni vzpery nemeni model ani hash
check(G.model_pro_parametry({"sirka": 1400, "vzpery": False, "vzpera_delka": 600}, razitka=False)[0] == G.model_pro_parametry({"sirka": 1400}, razitka=False)[0], "vypnute vzpery: stejny model a hash")
# LRU omezeni
for i in range(G.CACHE_MAX + 3):
    G.model_pro_parametry({"sirka": 600 + 10 * i}, razitka=False)
check(len(G._GLB_CACHE) <= G.CACHE_MAX, f"cache nepreroste {G.CACHE_MAX} polozek ({len(G._GLB_CACHE)})")
# ---- desky rozrezane na kusy se skladaji PO HLADINACH (2026-10-05, opraveno): vyrez pro ram v policich a vyrezy v pracovni desce lezi v ruznych vyskach a drive splynuly v jeden blok od police po desku;
#      kazdy vrchol lamino meshe musi lezet v nejake desce (y mezi spodkem a vrchem nejake desky v sestave)
for par_ in (dict(sirka=2000, police=2, vyska=1000), dict(sirka=2000, police=3, vyska=1200), dict(sirka=2000, police=1, vyrez1=True), dict(sirka=2400, police=2, vyska=1000, vyrez1=True, vyrez1_police=True, stredni_opora="ram")):
    P_, T_ = lamino_geometrie(par_)
    r_ = S.sestav_stul(**par_)
    hlad = sorted({(float(S._aabb(d)[0][1]), float(S._aabb(d)[1][1])) for d in r_["dily"] if d["part_id"] == "product_4933"})
    mimo = [float(y) for y in np.unique(np.round(P_[:, 1], 1)) if not any(lo - 0.6 <= y <= hi + 0.6 for lo, hi in hlad)]
    check(not mimo, f"{par_}: lamino mesh jen v hladinach desek (mimo: {mimo[:4]}; hladiny {[(round(a, 1), round(b, 1)) for a, b in hlad]})")
    ys_t = P_[T_][:, :, 1]
    check(len(P_) > 0 and float((ys_t.max(axis=1) - ys_t.min(axis=1)).max()) <= 20.0, f"{par_}: zadny trojuhelnik lamino desky neni vyssi nez deska (18 mm) = nejsou tam bloky od police po desku ({float((ys_t.max(axis=1) - ys_t.min(axis=1)).max()):.1f} mm)")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
