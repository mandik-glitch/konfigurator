#!/opt/konfigurator/api/venv/bin/python
"""RAZITKA LOGA NA PROFILECH STOLU v modelu online nabidky (bot8, 2026-10-06; Robert pres bot5 / bot9: razitka i u stolu z generatoru, jen u modelu v nabidce - pravidlo 2026-09-06).

`api/stul_razitka.py` (pravidla razitkovace sestav: kazdy treti profil na kazde exponovane stene, nahodne po delce, min. rozestup 500 mm, vypln drazky pod logem) + `stul_glb.poskladej_glb(..., razitka)`:
logo = instance jednoho sdileneho meshe (uzel n<i>, vlastni material), vypln = kvadr ve skupine hlinik. Holy model (razitka=False; od 2026-10-08 - WORKFLOW pravidlo 61 - uz NENI vychozi) zustava BEZE ZMENY.

NEZAVISLE MERENI (z dat stolu, ne z kodu razitek): logo (mesh z katalogu) se prevede do sveta a porovna s AABB vsech ostatnich dilu a s rovinou steny hostitelskeho profilu.
  A  poloha: logo lezi cele NAD rovinou steny (prilehla strana presne na ni, vycnivani 3 mm), uvnitr profilu podel delky (40 mm od konce), vypln licuje se stenou (horni plocha v rovine steny)
  B  nic se nezanori: logo ani vypln se neprekryva s zadnym jinym dilem (krome hostitele - vypln je v jeho drazce) o vic nez 0,5 mm; logo je exponovano ven (paprsek podel normaly nic neprotne)
  C  pravidla: rozestup log na jednom profilu >= 222,2 + 500 mm, text se cte spravne (osa Y loga nahoru, kdyz je urcena gravitaci), na 4 a vice smerech stoly s dostatkem profilu, determinismus a rozdil mezi konfiguracemi
  D  GLB: verejny model se razitky NEMENI (stejne bytes, cache oddelene, vodici beze zmeny), model s razitky projde v3d_glb.sanitize + final_check, loga jsou instance jednoho meshe,
     soubor naroste o < 1 MB, spec.box stejny jako u verejneho modelu, uzly jmenem n<i>, nikde retezec "logo"
  E  vsechny systemy (30 / 35 / 40 / SSE 41) a mrizka konfiguraci bez vyjimky
Spusteni: api/venv/bin/python3 scripts/2026-10-06_razitka_stolu/test_razitka_stolu.py       Mutace: scripts/2026-10-06_razitka_stolu/mutace.py
"""
import itertools
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.environ.get("STUL_API_DIR") or os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)
import numpy as np  # noqa: E402
import stul_konfigurator as S  # noqa: E402
import stul_glb  # noqa: E402
import stul_razitka as RZ  # noqa: E402
import v3d_glb  # noqa: E402

R = RZ.R
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


def klic_t(k):
    return tuple(klic_t(x) for x in k) if isinstance(k, (list, tuple)) else k


LOGO_P = stul_glb.nacti_mesh(RZ.LOGO_PART)[0].astype(float)
LOGO_LO, LOGO_HI = LOGO_P.min(axis=0), LOGO_P.max(axis=0)
LOGO_ROHY = np.array([[x, y, z] for x in (LOGO_LO[0], LOGO_HI[0]) for y in (LOGO_LO[1], LOGO_HI[1]) for z in (LOGO_LO[2], LOGO_HI[2])])


def konfigurace():
    out = []
    for sy in (30, 35, 40):
        out.append({"system": sy})
        out.append({"system": sy, "sirka": 2400, "hloubka": 1100})
        out.append({"system": sy, "sirka": 3000, "hloubka": 1500})
        out.append({"system": sy, "led": False, "stojky": False, "police": 3})
        out.append({"system": sy, "sirka": 2800, "vyska": 760, "stredni_opora": "noha"})
        out.append({"system": sy, "kolecka": False, "patky": True, "vzpery": True})
        out.append({"system": sy, "sirka": 1600, "stredni_opora": "ram", "led_rameno": 400})
    out.append({"system": 41})
    out.append({"system": 41, "sirka": 2400})
    return out


def hodnoty_razitek(vstup):
    r = S.sestav_stul(**vstup)
    h = stul_glb.kanonicky_hash(r["parametry"])
    return r, h, RZ.razitka(r, h)


KONF = konfigurace()
chyby = {k: [] for k in "ABCE"}
pocty = []
smery = []
for vstup in KONF:
    try:
        r, h, st = hodnoty_razitek(vstup)
    except Exception as e:                   # noqa: BLE001
        chyby["E"].append((vstup, type(e).__name__ + ": " + str(e)[:80]))
        continue
    sy = r["parametry"]["system"]
    sd = S.SYSTEMY[sy]
    hh = sd["profil_mm"] / 2.0
    dily = r["dily"]
    klice = [klic_t(k) for k in r["klice"]]
    boxy = np.array([S._aabb(d) for d in dily], float)
    pocty.append(len(st))
    by_profil = {}
    for x in st:
        i = klice.index(x["klic"])
        d = dily[i]
        Rm = S.kvat_na_matici(d["quaternion"])
        osa = Rm[:, 1]
        stred = np.array(d["position"], float)
        L = 1000.0 * d["scale"][1]
        Rl = S.kvat_na_matici(x["logo"]["q"])
        normala = Rl[:, 2]
        smery.append(tuple(normala.round(1)))
        # ---- A: poloha
        rohy = LOGO_ROHY @ Rl.T + np.array(x["logo"]["pos"], float)
        w = (rohy - stred) @ normala                                      # vzdalenost rohu loga od osy profilu podel normaly steny
        u = (rohy - stred) @ osa
        if abs(w.min() - hh) > 0.01 or abs(w.max() - (hh + R.LOGO_RELIEF_MM)) > 0.01:
            chyby["A"].append((vstup, x["klic"], "logo neni na rovine steny", round(float(w.min()), 3), round(float(w.max()), 3)))
        if u.min() < -L / 2.0 + R.OKRAJ_MM - 0.01 or u.max() > L / 2.0 - R.OKRAJ_MM + 0.01:
            chyby["A"].append((vstup, x["klic"], "logo blize ke konci profilu nez 40 mm", round(float(u.min()), 1), round(float(u.max()), 1), L))
        if abs(np.dot(normala, osa)) > 1e-4:
            chyby["A"].append((vstup, x["klic"], "normala neni kolma na osu"))
        dw, dd_ = sd["profil"], RZ.DRAZKA[sd["profil"]]
        v = x["vypln"]
        Rv = S.kvat_na_matici(v["q"])
        pv = (np.array(v["pos"], float) - stred) @ normala
        if abs((pv + v["rozmer"][2] / 2.0) - hh) > 0.01 or v["rozmer"][1] != dd_[0] or v["rozmer"][2] != dd_[1] or abs(v["rozmer"][0] - R.LOGO_DELKA_MM) > 1e-6:
            chyby["A"].append((vstup, x["klic"], "vypln nelicuje se stenou / spatny rozmer", round(float(pv), 3), v["rozmer"]))
        if np.linalg.norm(Rv @ np.array([0, 0, 1.0]) - normala) > 1e-6:
            chyby["A"].append((vstup, x["klic"], "vypln otocena jinak nez logo"))
        # ---- B: nezanoreni a exponovani
        stred_loga = np.array(x["logo"]["pos"], float)
        lo_l, hi_l = rohy.min(axis=0), rohy.max(axis=0)
        for j in range(len(dily)):
            if j == i or (isinstance(klice[j], tuple) and klice[j] and klice[j][0] == "vz"):          # AABB sikme vzpery nic neříká (jako v kontrolách generátoru)
                continue
            pr = np.minimum(hi_l, boxy[j][1]) - np.maximum(lo_l, boxy[j][0])
            if (pr > 0.5).all():
                chyby["B"].append((vstup, x["klic"], "logo se zanorilo do dilu", klice[j], np.round(pr, 2).tolist()))
        # vypln: oriented box -> AABB; muze se prekryvat jen s hostitelem
        vrohy = np.array([[a, b, c] for a in (-v["rozmer"][0] / 2, v["rozmer"][0] / 2) for b in (-v["rozmer"][1] / 2, v["rozmer"][1] / 2) for c in (-v["rozmer"][2] / 2, v["rozmer"][2] / 2)]) @ Rv.T + np.array(v["pos"], float)
        lo_v, hi_v = vrohy.min(axis=0), vrohy.max(axis=0)
        for j in range(len(dily)):
            if j == i or (isinstance(klice[j], tuple) and klice[j] and klice[j][0] == "vz"):
                continue
            pr = np.minimum(hi_v, boxy[j][1]) - np.maximum(lo_v, boxy[j][0])
            if (pr > 0.5).all():
                chyby["B"].append((vstup, x["klic"], "vypln se zanorila do jineho dilu", klice[j]))
        # exponovani: pul-metr po normale od stredu loga nic nesmi protnout
        for dt in np.linspace(-R.LOGO_DELKA_MM / 2, R.LOGO_DELKA_MM / 2, 5):
            o = stred_loga + osa * dt + normala * 1.0
            zasah = [j for j in range(len(dily)) if j != i and not (isinstance(klice[j], tuple) and klice[j] and klice[j][0] == "vz") and RZ._paprsek_zasahne(o, normala, boxy[:, 0, :], boxy[:, 1, :], np.array([j]))]
            if zasah:
                chyby["B"].append((vstup, x["klic"], "logo je zakryte", [klice[j] for j in zasah][:3]))
                break
        by_profil.setdefault(i, []).append(x)
        # ---- C: text se cte spravne
        nahoru = Rl[:, 1]
        if abs(nahoru[1]) > 0.5 and nahoru[1] < 0:
            chyby["C"].append((vstup, x["klic"], "text vzhuru nohama", nahoru.round(2).tolist()))
    for i, lst in by_profil.items():
        for a, b in itertools.combinations(lst, 2):
            if abs(a["t"] - b["t"]) < R.LOGO_DELKA_MM + R.MIN_ROZESTUP_LOG_MM - 0.01:
                chyby["C"].append((vstup, a["klic"], "logo blize nez 500 mm od jineho na temz profilu", round(a["t"], 1), round(b["t"], 1)))
    # determinismus
    st2 = RZ.razitka(r, h)
    if json.dumps(st2, sort_keys=True, default=str) != json.dumps(st, sort_keys=True, default=str):
        chyby["C"].append((vstup, "neni deterministicke"))

over(f"A poloha: logo cele nad rovinou steny (vycnivani 3 mm), 40 mm od konce profilu, vypln licuje se stenou a ma rozmer drazky ({len(KONF)} konfiguraci)", not chyby["A"], chyby["A"][:3])
over("B nic se nezanori (logo ani vypln, max 0,5 mm) a logo je exponovano ven (paprsek ze 5 bodu podel loga nic neprotne)", not chyby["B"], chyby["B"][:3])
over("C pravidla: rozestup log na profilu >= 500 mm volne mezery, text se cte spravne, deterministicke", not chyby["C"], chyby["C"][:3])
over("E zadna konfigurace nespadla (30 / 35 / 40 / SSE 41)", not chyby["E"], chyby["E"][:3])
over("C2 stoly maji razitka na vice stranach: vychozi stoly 30 / 35 / 40 aspon 6 razitek a aspon 4 ruzne smery normaly", all(len(RZ.razitka(S.sestav_stul(system=sy), "x")) >= 6 for sy in (30, 35, 40)) and len(set(smery)) >= 4, (pocty[:6], len(set(smery))))
r30 = S.sestav_stul(system=30)
over("C3 ruzna konfigurace = jina razitka (hash vstupem nahody), stejna = stejna", RZ.razitka(r30, "a") != RZ.razitka(r30, "b") and RZ.razitka(r30, "a") == RZ.razitka(r30, "a"), None)

# C4: "kazdy treti" - vybrane = kazdy treti z kandidatu KAZDE steny (posun z hash); skutecny pocet muze byt nizsi jen kdyz se razitko nevejde kvuli rozestupu na profilu
chyby_C4 = []
for sy in (30, 35, 40):
    r = S.sestav_stul(system=sy)
    h = stul_glb.kanonicky_hash(r["parametry"])
    lad = {}
    st = RZ.razitka(r, h, ladeni=lad)
    for lok in range(4):
        n_kand = lad["kandidati"][lok]
        posun = int(R._nahodne_0_1("posun", h, lok) * R.KAZDY_NTY)
        ocek = len(range(posun, n_kand, R.KAZDY_NTY))
        if lad["vybrane"][lok] != ocek:
            chyby_C4.append((sy, lok, "vybrano", lad["vybrane"][lok], "ocekavano", ocek, "z", n_kand))
    if sum(lad["vybrane"].values()) < len(st) or len(st) < sum(lad["vybrane"].values()) - 3:
        chyby_C4.append((sy, "pocet razitek", len(st), "vybrano", sum(lad["vybrane"].values())))
over("C4 kazdy treti: z kandidatu kazde steny je vybrany kazdy treti od posunu daneho hash (pocet razitek = vybrane minus nejvys 3 vynechana pro rozestup)", not chyby_C4, chyby_C4)

# C5: rozmery drazky (sirka otvoru, hloubka k dnu hrdla) NEZAVISLE zmerene z GLB profilu (prurez) a porovnane s tabulkou RZ.DRAZKA
def drazka_z_meshe(part_id):
    P = stul_glb.nacti_mesh(part_id)[0].astype(float)
    povrch = float(P[:, 0].max())
    z_na_povrchu = np.unique(np.round(P[np.isclose(P[:, 0], povrch, atol=1e-3)][:, 2], 3))
    z0, z1 = float(z_na_povrchu[z_na_povrchu <= 0].max()), float(z_na_povrchu[z_na_povrchu >= 0].min())
    uvnitr = P[(P[:, 0] > 0) & (P[:, 0] < povrch - 1e-3) & (np.abs(P[:, 2]) <= (z1 - z0) / 2.0 + 0.02)]
    return round(z1 - z0, 2), round(povrch - float(uvnitr[:, 0].min()), 2)


chyby_C5 = []
for part_id, (w_, d_) in RZ.DRAZKA.items():
    w_m, d_m = drazka_z_meshe(part_id)
    if abs(w_m - w_) > 0.05 or abs(d_m - d_) > 0.05:
        chyby_C5.append((part_id, "zmereno", (w_m, d_m), "tabulka", (w_, d_)))
over("C5 drazka profilu (sirka otvoru, hloubka k dnu hrdla) zmerena z GLB profilu = tabulka v modulu razitek (30: 8,2 x 10; 35: 8,2 x 11,667; 40: 10,2 x 13,332)", not chyby_C5, chyby_C5)

# ---------------------------------------------------------------------------------------------- D) GLB
chyby_D = []
for vstup in ({"system": 30}, {"system": 35}, {"system": 40, "sirka": 2400, "hloubka": 1100}, {"system": 41}):
    r = S.sestav_stul(**vstup)
    h = stul_glb.kanonicky_hash(r["parametry"])
    stul_glb._GLB_CACHE.clear()
    stul_glb._GLB_RAZITKA_CACHE.clear()
    _, verejny = stul_glb.model_pro_parametry(r["parametry"], razitka=False)          # HOLY model: od WORKFLOW pravidla 61 (2026-10-08) je vychozi model S razitky, holy se vyzaduje vyslovne
    posun = stul_glb._META_CACHE[h].copy()
    rozs = stul_glb._ROZSAHY_CACHE[h]
    _, s_razitky = stul_glb.model_pro_parametry(r["parametry"], razitka=True)
    _, verejny2 = stul_glb.model_pro_parametry(r["parametry"], razitka=False)
    if verejny2 != verejny or not (stul_glb._META_CACHE[h] == posun).all() or stul_glb._ROZSAHY_CACHE[h] != rozs or h in stul_glb._GLB_RAZITKA_CACHE and stul_glb._GLB_CACHE[h] is stul_glb._GLB_RAZITKA_CACHE[h]:
        chyby_D.append((vstup, "verejny model se zmenil / cache zamichane"))
    n_st = len(RZ.razitka(r, h))
    if n_st and len(s_razitky) - len(verejny) > 1024 * 1024:
        chyby_D.append((vstup, "soubor narostl vic nez o 1 MB", len(s_razitky) - len(verejny)))

    def js(glb):
        n = struct.unpack("<I", glb[12:16])[0]
        return json.loads(glb[20:20 + n])
    jv, jr = js(verejny), js(s_razitky)
    if n_st:
        sdilene = [m for m in set(n.get("mesh") for n in jr["nodes"] if n.get("mesh") is not None) if sum(1 for n in jr["nodes"] if n.get("mesh") == m) == n_st and any("rotation" in n and n.get("mesh") == m for n in jr["nodes"])]
        if len(sdilene) != 1:
            chyby_D.append((vstup, "loga nejsou instance jednoho meshe", n_st, sdilene))
        if len(jr["nodes"]) != len(jv["nodes"]) + n_st or len(jr["materials"]) != len(jv["materials"]) + 1:
            chyby_D.append((vstup, "pocet uzlu / materialu", len(jr["nodes"]), len(jv["nodes"]), n_st))
        if jr["scenes"][0]["extras"]["v3d"]["box"] != jv["scenes"][0]["extras"]["v3d"]["box"]:
            chyby_D.append((vstup, "spec.box se zmenil"))
    if re.search(rb"logo", json.dumps(jr).encode().lower()):
        chyby_D.append((vstup, "v JSON modelu je retezec logo"))
    spec = v3d_glb.embedded_spec(s_razitky)
    try:
        out = v3d_glb.sanitize(s_razitky, spec)
        v3d_glb.final_check(v3d_glb.read_glb(out)[0])
    except ValueError as e:
        chyby_D.append((vstup, "sanitize / final_check", str(e)[:120]))
# D3 / D4: polohy a otoceni log v GLB = razitka + posun modelu; vypln drazek ve skupine hlinik (24 vrcholu na kvadr)
chyby_D3 = []
for vstup in ({"system": 30}, {"system": 40, "sirka": 2400, "hloubka": 1100}):
    r = S.sestav_stul(**vstup)
    h = stul_glb.kanonicky_hash(r["parametry"])
    stul_glb._GLB_CACHE.clear()
    stul_glb._GLB_RAZITKA_CACHE.clear()
    _, verejny = stul_glb.model_pro_parametry(r["parametry"], razitka=False)          # HOLY model: od WORKFLOW pravidla 61 (2026-10-08) je vychozi model S razitky, holy se vyzaduje vyslovne
    posun = np.array(stul_glb._META_CACHE[h], float)
    _, s_razitky = stul_glb.model_pro_parametry(r["parametry"], razitka=True)
    st = RZ.razitka(r, h)

    def js(glb):
        n = struct.unpack("<I", glb[12:16])[0]
        return json.loads(glb[20:20 + n])
    jv, jr = js(verejny), js(s_razitky)
    uzly = jr["nodes"][len(jv["nodes"]):]
    if len(uzly) != len(st):
        chyby_D3.append((vstup, "pocet uzlu loga", len(uzly), len(st)))
    for u, x in zip(uzly, st):
        if np.abs(np.array(u["translation"]) - (np.array(x["logo"]["pos"]) + posun)).max() > 0.001 or np.abs(np.array(u["rotation"]) - np.array(x["logo"]["q"])).max() > 1e-5:
            chyby_D3.append((vstup, "poloha / otoceni loga v GLB", x["klic"]))
    pv = jv["accessors"][jv["meshes"][jv["nodes"][0]["mesh"]]["primitives"][0]["attributes"]["POSITION"]]["count"]
    pr_ = jr["accessors"][jr["meshes"][jr["nodes"][0]["mesh"]]["primitives"][0]["attributes"]["POSITION"]]["count"]
    if pr_ - pv != len(stul_glb._mesh_kvadr((0, 0, 0), (1, 1, 1))[0]) * len(st):
        chyby_D3.append((vstup, "vypln drazek ve skupine hlinik", pr_ - pv, len(st)))
    mat = jr["materials"][-1]["pbrMetallicRoughness"]
    if mat["baseColorFactor"] != RZ.LOGO_BARVA or not (0.0 <= mat["metallicFactor"] <= 1.0):
        chyby_D3.append((vstup, "material loga", mat))
over("D3 GLB: kazde logo ma uzel s polohou (razitko + posun modelu) a otocenim z razitek; vypln drazek pribyla do skupiny hlinik (24 vrcholu na kvadr); material loga je oranzovy", not chyby_D3, chyby_D3[:3])

over("D GLB: verejny model beze zmeny (bytes, posun, rozsahy, cache oddelene); model s razitky = verejny + n instanci jednoho meshe + 1 material, < 1 MB navic, spec.box stejny, bez retezce logo, projde sanitize + final_check", not chyby_D, chyby_D[:3])

# glb_bytes: razitka=False je vychozi (verejny model) - pres falesny zdroj jen kontrola signatury
import inspect  # noqa: E402
over("D2 stul_shop.glb_bytes / model_pro_parametry: parametr razitka ma vychozi None = nastaveni generatoru, `RAZITKA_VYCHOZI` je True (WORKFLOW pravidlo 61, Robert 2026-10-08)", inspect.signature(stul_glb.model_pro_parametry).parameters["razitka"].default is None and stul_glb.RAZITKA_VYCHOZI is True and "razitka=None" in open(os.path.join(API, "stul_shop.py"), encoding="utf-8").read(), None)

ok = sum(vysl)
print(f"\nVYSLEDEK razitka loga na stolech: {ok}/{len(vysl)} OK  (konfiguraci: {len(KONF)}, razitek celkem {sum(pocty)})")
sys.exit(0 if ok == len(vysl) else 1)
