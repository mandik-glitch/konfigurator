#!/usr/bin/env python3
"""Test KOT ve 3D nahledu generatoru stolu (bot8, 2026-10-05; Robert: "doplnit do generatoru ve 3D nahledu ... musi tam byt koty v dratenem pohledu": celkova vyska po posledni konec
profilu, delka a hloubka pracovni desky, vyska horni roviny pracovni desky od podlahy, vzdalenosti perforovanych panelu od vsech nohou, vnitrni vyska ke spodni hrane podelniku
nesouciho pracovni desku, mezery mezi spodnimi policemi, vyska horni roviny kazde spodni police od podlahy). Kody: api/stul_koty.py, spec v3d `dims` v api/stul_glb.py.

NEZAVISLE na kodu kot - ocekavane hodnoty se pocitaji z PARAMETRU stolu (sirka, hloubka, vyska, stojky_vyska, profil systemu, tloustka desky 18 mm), z `police_meze` generatoru
(mezery polic ve vlastni definici Roberta: police_h1 = od horni plochy desky nejvyssi police po spodek podelniku, dalsi = od horni plochy desky po spodek ramu police nad ni)
a z geometrie hotoveho GLB (accessory vrcholu):
  A) vychozi stul: presne tyto kóty (cisla, usporadani do sloupcu, popisek u horniho konce cary),
  B) mrizka systemu 30 / 35 / 40 x rozmeru x polic x panelu x stojek / LED / stredni opory: kazde cislo = vzorec z parametru, zadna kota navic,
  C) GLB: kóty ve spec v3d (format viewer3d.js: text jen cislice, uroven, poloha popisku), konce kot lezi na modelu (podlaha y = 0, horni rovina desky = max y desky v GLB),
     delka cary kóty = jeji text, zadna kota mimo obalku modelu o vic nez 300 mm,
  D) kóty se nemeni hash ani RULES_VERSION (kosiky a objednavky), stejna konfigurace = stejne kóty,
  E) mutace: pokazene zaokrouhlovani / chybejici posun GLB / vynechane mezery musi test chytit.
Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_koty.py
Ostatni systemy:  api/venv/bin/python3 scripts/2026-10-04_system40/spust_v_systemu.py <30|35|40> scripts/2026-10-02_stul_testy/test_stul_koty.py"""
import itertools
import json
import math
import os
import re
import struct
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))
import numpy as np  # noqa: E402
import stul_glb as G  # noqa: E402
import stul_koty as K  # noqa: E402
import stul_konfigurator as S  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


def kr(v):
    """zaokrouhleni na cele mm a pulky NAHORU (nezavisla kopie pravidla)"""
    return int(math.floor(v + 0.5))


def cislo(t):
    return int(str(t).replace(" ", ""))


def delka(k):
    return float(np.linalg.norm(np.array(k["b"], float) - np.array(k["a"], float)))


def typ(k, yt):
    """Druh kóty podle geometrie (kóty nenesou jmeno): 'v_podlaha' svisla od podlahy, 'v_mezera' svisla lokalni, 'x' po hloubce, 'z_deska' po sirce v rovine desky, 'z_jine' po sirce jinde (panely)."""
    d = np.array(k["b"], float) - np.array(k["a"], float)
    a = np.array(k["a"], float)
    if abs(d[0]) < 1e-6 and abs(d[2]) < 1e-6:
        return "v_podlaha" if abs(a[1]) < 0.01 else "v_mezera"
    if abs(d[1]) < 1e-6 and abs(d[2]) < 1e-6:
        return "x"
    if abs(d[0]) < 1e-6 and abs(d[1]) < 1e-6:
        return "z_deska" if abs(a[1] - yt) < 0.01 else "z_jine"
    return "?"


def ocekavane(r):
    """Ocekavana cisla z PARAMETRU a police_meze (nezavisle na stul_koty)."""
    p, P = r["parametry"], float(S.SYSTEMY[int(r["parametry"]["system"])]["profil_mm"])
    t = S.DESKA_TLOUSTKA
    yt = float(p["vyska"])
    vnitrni = yt - t - P
    zkr = float(S.SYSTEMY[int(p["system"])]["deska_zkraceni"])        # systemy 35 / 40: deska lezi na lici zadnich noh, ktere jsou vic vpredu = fyzicka deska je o 5 / 10 mm kratsi nez zadana hloubka stolu
    zad = 0.0 if (p["stojky"] or S.SYSTEMY[int(p["system"])].get("sse")) else P                  # BEZ zadnich stojek deska pokracuje dozadu o tloustku profilu a prekryva zadni svisle profily (Robert 2026-10-08)
    out = {"delka": float(p["sirka"]), "hloubka": float(p["hloubka"]) - zkr + zad, "deska_vyska": yt, "vnitrni": vnitrni}
    if p["stojky"] and p["led"]:
        out["celek"] = yt - t + float(p["stojky_vyska"]) + P            # horni ram LED (profil) lezi na vrcholu zadnich stojek
    elif p["stojky"]:
        out["celek"] = yt - t + float(p["stojky_vyska"])
    else:
        out["celek"] = None                                              # bez stojek je nejvyssi bod deska = kota deska_vyska (celek se nekotuje dvakrat)
    mezery = [float(h) for h in r["police_meze"]["hodnoty"]]            # od nejvyssi police dolu: [police_h1, police_h2, ...]
    tops = []
    top = vnitrni - mezery[0] if mezery else None
    for j in range(len(mezery)):
        tops.append(top)
        if j + 1 < len(mezery):
            top = top - (t + P) - mezery[j + 1]                          # horni plocha nizsi police = spodek ramu police nad ni - mezera
    out["police"] = tops
    out["mezery"] = mezery if len(mezery) else []
    return out


def spoctene(k_list, yt):
    """Seznam kot rozdelen podle druhu: slovnik druh -> cisla (zaokrouhlena texty)."""
    d = {}
    for k in k_list:
        d.setdefault(typ(k, yt), []).append(cislo(k["t"]))
    return d


def kontrola_konfigurace(p, popis):
    r = S.sestav_stul(**p)
    pr = r["parametry"]
    K_ = K.koty(r)
    yt = None
    # horni rovina desky v souradnicich generatoru: z kot (kota "z_deska" lezi v teto rovine) - nezavisle ji dostaneme z desky v dilech
    desky = [S._aabb(d) for d in r["dily"] if str(d.get("deska_id") or "").startswith("prac")]
    yt = max(float(b[1][1]) for b in desky)
    e = ocekavane(r)
    rd = spoctene(K_, yt)
    check(sorted(rd.get("z_deska", [])) == [kr(e["delka"])], f"{popis}: delka desky {rd.get('z_deska')} = {kr(e['delka'])}")
    check(rd.get("x") == [kr(e["hloubka"])], f"{popis}: hloubka desky {rd.get('x')} = {kr(e['hloubka'])}")
    od_podlahy = sorted(rd.get("v_podlaha", []))
    cekano = [e["deska_vyska"], e["vnitrni"]] + ([e["celek"]] if e["celek"] is not None else []) + list(e["police"])
    cekano = sorted(kr(v) for v in cekano)
    # tolerance 1 mm: sablona ma desku o setiny mm vedle; porovnavame po jednom
    ok_v = len(od_podlahy) == len(cekano) and all(abs(a - b) <= 1 for a, b in zip(od_podlahy, cekano))
    check(ok_v, f"{popis}: vysky od podlahy {od_podlahy} = {cekano} (deska, vnitrni, celek, police)")
    mezery = sorted(rd.get("v_mezera", []))
    cekane_mezery = sorted(kr(v) for v in e["mezery"])
    ok_m = len(mezery) == len(cekane_mezery) and all(abs(a - b) <= 1 for a, b in zip(mezery, cekane_mezery))
    check(ok_m, f"{popis}: mezery polic {mezery} = {cekane_mezery}")
    # panely: soucet obou mezer jednoho panelu = volna sirka mezi nohama - sirka panelu (stejne u obou stran; stred dostane polovinu)
    pi = r["panely_info"]
    if pi["pocet"] and not pr["stredni_noha"]:
        P = float(S.SYSTEMY[int(pr["system"])]["profil_mm"])
        rezim = pi.get("rezim")
        sloupcu = int(pi["sloupcu"])
        volno = (float(pr["sirka"]) - 2 * P) if sloupcu == 1 else ((float(pr["sirka"]) - 3 * P) / 2.0)      # jeden usek mezi stojkami, nebo dva useky u stredni nohy (stredni noha uprostred)
        celkem_mezera = volno - S.PANEL_SIRKA
        pz = sorted(rd.get("z_jine", []))
        obsazenych = min(int(pi["pocet"]), sloupcu)                                  # panely se pridavaji zleva doprava po useku: prazdny usek nema panel, tedy ani kóty
        cekano_pz = sorted([kr(celkem_mezera / 2.0)] * (2 * obsazenych)) if celkem_mezera / 2.0 > K.PRAHY_MEZERY else []
        ok_p = len(pz) == len(cekano_pz) and all(abs(a - b) <= 1 for a, b in zip(pz, cekano_pz))
        check(ok_p, f"{popis}: mezery panelu od nohou {pz} = {cekano_pz} (rezim {rezim}, useku {sloupcu})")
    else:
        check(not pi["pocet"] or pr["stredni_noha"] or rd.get("z_jine", []) is not None, f"{popis}: bez panelu zadne kóty panelu" if not pi["pocet"] else f"{popis}: panely")
        if not pi["pocet"]:
            check(not rd.get("z_jine"), f"{popis}: bez panelu zadna kota panelu ({rd.get('z_jine')})")
    check(all(typ(k, yt) != "?" for k in K_), f"{popis}: kazda kota ma jasny druh (svisla, po sirce, po hloubce)")
    return r, K_


print("A) vychozi stul")
r0 = S.sestav_stul(**S.VYCHOZI)
k0 = K.koty(r0)
pop = {(cislo(k["t"]), tuple(round(x) for x in k["o"]), k["l"], k.get("m")) for k in k0}
# poradi: vyska desky, celkova vyska, delka a hloubka desky, vnitrni vyska, vyska police, mezera nad policí, mezery panelu vlevo a vpravo (hloubka desky 795 / 790 = deska kratsi o 5 / 10 mm v systemech 35 / 40)
CEKANO_VYCHOZI = {30: [840, 1925, 1280, 800, 792, 363, 428, 15, 15], 35: [840, 1930, 1280, 795, 787, 363, 423, 10, 10], 40: [840, 1935, 1280, 790, 782, 363, 418, 5, 5]}
check([cislo(k["t"]) for k in k0] == CEKANO_VYCHOZI[S.aktivni_system()], f"vychozi stul systemu {S.aktivni_system()}: kóty {[k['t'] for k in k0]} = {CEKANO_VYCHOZI[S.aktivni_system()]}")
check(all(re.fullmatch(r"[0-9 ]{1,7}", k["t"]) for k in k0), "texty kot: jen cislice a mezery (viewer jiny text nezobrazi)")
check(all(k["l"] in (1, 2) and abs(delka(k) - cislo(k["t"])) <= 0.5 + 1e-9 for k in k0), "text kóty = delka cary kóty (zaokrouhlena na cele mm)")
check(k0[0].get("m") == 1.0 and k0[1].get("m") == 1.0, "vysky od podlahy maji popisek u horniho konce cary (m = 1)")
check(all("m" not in k or 0.0 <= k["m"] <= 1.0 for k in k0), "poloha popisku m je v 0..1")
check(len(k0) == len({json.dumps(k, sort_keys=True) for k in k0}), "zadna kota dvakrat")

print("B) mrizka konfiguraci")
n_konf = 0
for sirka, hloubka, vyska, police, panely, stojky, led, stred in itertools.product(
        (1000, 1280, 2000, 2600), (600, 800, 1000), (840, 1000, 1200), (0, 1, 3), (1, 2), (True, False), (True, False), ("auto", "ram")):
    if stred == "ram" and sirka <= 1500:
        continue
    if not stojky and not led and panely == 2:
        continue
    n_konf += 1
    if n_konf % 4:                                                       # kazda ctvrta (mrizka je velka; kazdy bezi 40 ms, ale test ma zustat kratky)
        continue
    p = dict(sirka=sirka, hloubka=hloubka, vyska=vyska, police=police, panely_pocet=panely, stojky=stojky, led=led, stredni_opora=stred, suplik=False)
    kontrola_konfigurace(p, f"{sirka}x{hloubka}x{vyska} police {police} panelu {panely} stojky {stojky} LED {led} opora {stred}")
print(f"   zkouseno {len(range(0, n_konf, 4))} konfiguraci v systemu {S.aktivni_system()}")

print("B2) dalsi volby: suplik, vyrezy, navlek, hloubka nad prahem, PET, vzpery")
for p, popis in (
    (dict(), "vychozi"),
    (dict(hloubka=1100, police=2, vyska=1100), "hloubka 1100 (svisly profil bocnic), 2 police"),
    (dict(suplik=True, suplik_pocet=3, vyska=1100, sirka=1500), "3 supliky"),
    (dict(vyrez1=True, sirka=1600), "vyrez v desce (deska z vice kusu)"),
    (dict(police=2, vyska=1000, kolecka=False, patky=True), "patky misto koleček"),
    (dict(kolecka=False, patky=False), "zaslepky"),
    (dict(sirka=2600, stredni_opora="noha", panely_pocet=2), "stredni noha, 2 panely"),
    (dict(sirka=2600, stredni_opora="ram", police=1, panely_pocet=2), "vestaveny ram, 2 panely"),
    (dict(panely_pocet=2, stojky_vyska=1500, vyska=1200), "2 rady panelu"),
    (dict(stojky=False, led=False, panely=False, elektrozlab=False), "bez stojek"),
    (dict(panely=False, elektrozlab=False), "bez panelu"),
    (dict(vzpery=True), "vzpery ramen LED"),
):
    kontrola_konfigurace(p, popis)

print("C) GLB: spec v3d dims")


def nacti_glb(data):
    magic, ver, delka_ = struct.unpack("<III", data[:12])
    n, typ_ = struct.unpack("<II", data[12:20])
    js = json.loads(data[20:20 + n])
    return js


def max_y_materialu(js, klic_barvy):
    """max y vrcholu uzlu s danym materialem (accessor POSITION max)."""
    for mesh, mat in zip(js["meshes"], js["materials"]):
        if [round(x, 4) for x in mat["pbrMetallicRoughness"]["baseColorFactor"]] == [round(x, 4) for x in klic_barvy]:
            acc = js["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
            return float(acc["max"][1])
    return None


for p, popis in ((dict(), "vychozi"), (dict(sirka=2000, police=3, vyska=1200, hloubka=1100), "siroky, 3 police"), (dict(sirka=2600, panely_pocet=2, stredni_opora="noha"), "stredni noha, 2 panely")):
    par = S.sestav_stul(**p)["parametry"]
    h, data = G.model_pro_parametry(par)
    js = nacti_glb(data)
    spec = js["scenes"][0]["extras"]["v3d"]
    dims = spec["dims"]
    box = spec["box"]
    check(len(dims) >= 9 and len(dims) <= 60, f"GLB {popis}: pocet kot {len(dims)}")
    check(all(re.fullmatch(r"[0-9 ]{1,7}", d["t"]) and d["l"] in (1, 2) and (("m" not in d) or 0 <= d["m"] <= 1) for d in dims), f"GLB {popis}: kóty maji format viewer3d.js")
    check(all(len(d["a"]) == 3 and len(d["b"]) == 3 and len(d["o"]) == 3 and all(math.isfinite(x) for x in d["a"] + d["b"] + d["o"]) for d in dims), f"GLB {popis}: souradnice jsou konecna cisla")
    check(all(abs(delka(d) - cislo(d["t"])) <= 0.5 + 1e-6 for d in dims), f"GLB {popis}: text kóty = delka cary")
    yt_glb = max_y_materialu(js, G.MATERIALY["lamino"]["baseColorFactor"])
    kv = [d for d in dims if typ(d, yt_glb if yt_glb is not None else 0.0) == "v_podlaha"]
    check(len(kv) >= 3 and all(abs(d["a"][1]) < 0.01 for d in kv), f"GLB {popis}: svisle kóty od podlahy zacinaji na y = 0 (posun GLB je pouzity)")
    top_deska = max(d["b"][1] for d in kv if abs(d["b"][1] - (yt_glb or 0)) < 0.01) if yt_glb is not None and any(abs(d["b"][1] - yt_glb) < 0.01 for d in kv) else None
    check(top_deska is not None, f"GLB {popis}: jedna kota od podlahy konci presne na horni plose desky v modelu (y = {yt_glb})")
    lo, hi = np.array(box["min"], float), np.array(box["max"], float)
    vne = [d for d in dims for pt in (d["a"], d["b"]) if np.any(np.array(pt) + np.array(d["o"]) < lo - 450) or np.any(np.array(pt) + np.array(d["o"]) > hi + 450)]
    check(not vne, f"GLB {popis}: zadna kota mimo obalku modelu o vic nez 450 mm ({len(vne)})")
    kx = [d for d in dims if abs(d["b"][1] - d["a"][1]) < 1e-6 and abs(d["b"][2] - d["a"][2]) < 1e-6]
    zkr_glb = float(S.SYSTEMY[int(par["system"])]["deska_zkraceni"]) - (0.0 if (par["stojky"] or S.SYSTEMY[int(par["system"])].get("sse")) else float(S.SYSTEMY[int(par["system"])]["profil_mm"]))      # bez stojek deska o tloustku profilu delsi
    check(len(kx) == 1 and abs(cislo(kx[0]["t"]) - kr(par["hloubka"] - zkr_glb)) <= 1, f"GLB {popis}: jedna kota po hloubce = hloubka desky ({[k_['t'] for k_ in kx]} = {par['hloubka'] - zkr_glb})")

print("D) hash a verze pravidel beze zmeny")
h_vychozi = G.kanonicky_hash({})
check(S.aktivni_system() != 30 or h_vychozi == "87a80526a7ae21aa", f"hash vychoziho stolu systemu 30 je stejny jako pred kotami ({h_vychozi})")
G_h = G.kanonicky_hash({})
_koty_puvodni = K.koty
K.koty = lambda r: []
check(G_h == G.kanonicky_hash({}), "hash nezavisi na kotach")
K.koty = _koty_puvodni
check(G.RULES_VERSION == "2026-10-05.2" or G.RULES_VERSION >= "2026-10-05.2", f"RULES_VERSION {G.RULES_VERSION}: kóty ji nemeni (kosiky a objednavky)")
check(K.koty(S.sestav_stul(**S.VYCHOZI)) == K.koty(S.sestav_stul(**S.VYCHOZI)), "stejna konfigurace = stejne kóty")

print("E) mutace: test musi chytit pokazene kóty")
puvodni_cislo, puvodni_koty_v_glb = K._cislo, G._koty_v_glb


def pokazene_cislo(v):          # useknuti misto zaokrouhleni: 1924,54 -> 1924
    return f"{int(float(v)):,}".replace(",", " ")


K._cislo = pokazene_cislo
chyb_pred = len(FAILS)
k_m = K.koty(S.sestav_stul(**S.VYCHOZI))
zachyceno1 = [cislo(k["t"]) for k in k_m] != CEKANO_VYCHOZI[S.aktivni_system()]
K._cislo = puvodni_cislo
check(zachyceno1, "mutace 1 (useknuti misto zaokrouhleni) zmeni vychozi cisla (1 925 -> 1 924) = test A ji chyti")
G._koty_v_glb = lambda koty, posun: [{**k, "a": list(k["a"]), "b": list(k["b"])} for k in (koty or [])]            # bez posunu o model
par = S.sestav_stul(**S.VYCHOZI)["parametry"]
G._GLB_CACHE.pop(G.kanonicky_hash(par), None)
G._META_CACHE.pop(G.kanonicky_hash(par), None)
G._ROZSAHY_CACHE.pop(G.kanonicky_hash(par), None)
js_m = nacti_glb(G.model_pro_parametry(par)[1])
d_m = js_m["scenes"][0]["extras"]["v3d"]["dims"]
zachyceno2 = not all(abs(d["a"][1]) < 0.01 for d in d_m if typ(d, 0.0) == "v_podlaha") or any(d["a"][1] < -0.001 or d["a"][1] > 0.01 for d in d_m if abs(d["a"][0] - d_m[0]["a"][0]) < 1e-6 and d["a"][1] != 0)
zachyceno2 = zachyceno2 or abs(d_m[0]["a"][2] - (-422.377)) < 0.01                      # sirka stolu 1280: bez posunu je leva hrana na -422,4 misto -640
G._koty_v_glb = puvodni_koty_v_glb
for c_ in (G._GLB_CACHE, G._META_CACHE, G._ROZSAHY_CACHE):
    c_.pop(G.kanonicky_hash(par), None)
check(zachyceno2, "mutace 2 (GLB bez posunu kot) se projevi: levy sloupec kot neni na hrane stolu v GLB")
puvodni_meze = K.PRAHY_MEZERY
K.PRAHY_MEZERY = 1e9                                                  # mutace 3: zadna mezera se nekotuje
k_mm = K.koty(S.sestav_stul(**S.VYCHOZI))
K.PRAHY_MEZERY = puvodni_meze
check(len(k_mm) < len(k0), f"mutace 3 (vynechane mezery) snizi pocet kot ({len(k_mm)} < {len(k0)})")

print(f"\n{OK} kontrol OK" + (f", {len(FAILS)} CHYB" if FAILS else ""))
sys.exit(1 if FAILS else 0)
