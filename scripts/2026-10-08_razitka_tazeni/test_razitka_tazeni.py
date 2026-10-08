#!/usr/bin/env python3
"""RAZITKA PRI ZIVEM TAZENI (bot8, 2026-10-08; Robert: „razitka na generatoru pri tazeni zustavaji na miste“). Hermeticky (bez DB, bez prohlizece).

Server (`stul_glb.vodici` -> `vodici.ovladani.razitka`, `stul_ovladani_verejne`) popisuje kazde razitko: {dil = index dilu, na kterem sedi, uzel = uzel n<i> loga, vypln = [uzel hlinik, od, pocet] vrcholu vyplne drazky}.
Prohlizec (webapp/js/v3d-ovladani.js, liveBegin / liveApply) pri tazeni hybe razitka s dilem: posun = jako dil; natahni / roztahni = podle polohy STREDU razitka vuci STREDU dilu podel osy (stejne pravidlo jako pro vrcholy
dilu), razitko se nedeformuje. Test provadi totez NEZAVISLE v Pythonu nad skutecnym GLB a skutecnymi operacemi `zive` (kopie pravidel z v3d-ovladani.js / test_stul_zive.py):
  A  popis razitek: pocet = pocet razitek modelu, `dil` je platny dil s rozsahem vrcholu, uzel n<i> existuje a je logo, vypln lezi uvnitr uzlu hlinik, pole je ve verejnem popisu, bez razitek (RAZITKA_VYCHOZI = False) neni
  B  VSECHNY tahy se zivymi operacemi x kladny / zaporny posun: razitko hostene na hybanem dile zustane u nej (stred loga i vyplne ve vzdalenosti <= 5 mm od AABB dilu po operaci); u operace `posun` se logo i vypln pohnou
     PRESNE o stejne delta jako dil; razitka na dilech, ktere se nehybou, zustanou beze zmeny
  C  kontrola citlivosti: bez pohybu razitek (puvodni chovani) by invariant B u nejake konfigurace selhal
Spusteni: api/venv/bin/python3 scripts/2026-10-08_razitka_tazeni/test_razitka_tazeni.py     (STUL_API_OVERRIDE=<adresar api> = kandidat)"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import numpy as np  # noqa: E402
import stul_ovladani_verejne as OV  # noqa: E402
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
    for c in (G._GLB_CACHE, G._META_CACHE, G._ROZSAHY_CACHE, G._EXTRA_CACHE, G._GLB_RAZITKA_CACHE, getattr(G, "_RAZITKA_CACHE", {}), G._GLB_KOMPR):
        c.clear()


def gltf_a_uzly(glb):
    """(json, [pole vrcholu kazdeho uzlu s meshem | None])"""
    dj = struct.unpack("<I", glb[12:16])[0]
    js = json.loads(glb[20:20 + dj])
    bin0 = 20 + dj + 8
    out = []
    for n in js["nodes"]:
        if "mesh" not in n:
            out.append(None)
            continue
        acc = js["accessors"][js["meshes"][n["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
        bv = js["bufferViews"][acc["bufferView"]]
        out.append(np.frombuffer(glb, dtype="<f4", count=acc["count"] * 3, offset=bin0 + bv["byteOffset"]).reshape(-1, 3).astype(float).copy())
    return js, out


def klient_tazeni(poz, logo, rozsahy, extra, tah, delta, razitka, pohybuj_razitka=True):
    """Totez co v3d-ovladani.js (liveApply): operace `zive` na kopii vrcholu; razitka (logo = bod, vypln = rozsah vrcholu) se hybou jako tuha telesa podle stredu dilu. Vraci (poz, logo)."""
    poz = [None if a is None else a.copy() for a in poz]
    logo = {k: v.copy() for k, v in logo.items()}
    osa = np.array(tah["osa"], float)
    rig = {}
    for z in razitka or []:
        rig.setdefault(z["dil"], []).append({"uzel": z["uzel"], "vypln": z["vypln"]})
    for op in tah["zive"]:
        d = op["k"] * delta * osa
        for i in op["ix"]:
            r = rozsahy[i]
            if r is None:
                continue
            v = poz[r[0]][r[1]:r[1] + r[2]]
            if op["op"] == "posun":
                v += d
                if pohybuj_razitka:
                    for z in rig.get(i, []):
                        logo[z["uzel"]] = logo[z["uzel"]] + d
                        a, b = z["vypln"][1], z["vypln"][1] + z["vypln"][2]
                        poz[z["vypln"][0]][a:b] += d
            else:
                u = v @ osa
                stred = (u.min() + u.max()) / 2.0
                strana = np.where(u > stred + 0.05, 1, np.where(u < stred - 0.05, -1, 0))
                if pohybuj_razitka:
                    for z in rig.get(i, []):
                        us = float(logo[z["uzel"]] @ osa)
                        sd = 1 if us > stred + 0.05 else (-1 if us < stred - 0.05 else 0)
                        f = (0.5 if sd == 0 else (1.0 if sd == (1 if op["strana"] > 0 else -1) else 0.0)) if op["op"] == "natahni" else float(sd)
                        if f:
                            logo[z["uzel"]] = logo[z["uzel"]] + f * d
                            a, b = z["vypln"][1], z["vypln"][1] + z["vypln"][2]
                            poz[z["vypln"][0]][a:b] += f * d
                if op["op"] == "natahni":
                    f = np.where(strana == 0, 0.5, np.where(strana == (1 if op["strana"] > 0 else -1), 1.0, 0.0))
                    v += f[:, None] * d
                else:
                    v += strana[:, None] * d
            for r2 in (extra or {}).get(str(i), []):                       # dalsi rozsahy dilu (suplik): jako v prohlizeci, vlastni stred rozsahu
                w = poz[r2[0]][r2[1]:r2[1] + r2[2]]
                if op["op"] == "posun":
                    w += d
                else:
                    u2 = w @ osa
                    st2 = (u2.min() + u2.max()) / 2.0
                    sd2 = np.where(u2 > st2 + 0.05, 1, np.where(u2 < st2 - 0.05, -1, 0))
                    ff = np.where(sd2 == 0, 0.5, np.where(sd2 == (1 if op["strana"] > 0 else -1), 1.0, 0.0)) if op["op"] == "natahni" else sd2
                    w += ff[:, None] * d
    return poz, logo


def konfigurace():
    return [dict(system=30), dict(system=30, sirka=2400, police=3), dict(system=40, sirka=2400), dict(system=35, hloubka=1000, vyska=1000), dict(system=45, hloubka=1800), dict(system=45, sirka=3000, hloubka=1400, police=2)]


# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("A) popis razitek v `vodici.ovladani.razitka`")
celkem_stamps = 0
bez_pohybu_chyba = 0
chyb_hostu_s_funkci = 0
for p in konfigurace():
    popis = json.dumps(p, sort_keys=True)
    vycisti()
    r = S.sestav_stul(**p)
    r["ovladani_scena"] = S.ovladani_3d(r)
    par = r["parametry"]
    h = G.kanonicky_hash(par)
    v = G.vodici(par, r)
    ov = v["ovladani"]
    stamps = RZ.razitka(r, h)
    rz = ov.get("razitka")
    check(rz is not None and len(rz) == len(stamps) and len(stamps) >= 1, f"{popis}: popis razitek ma {len(stamps)} polozek ({None if rz is None else len(rz)})")
    glb = G.model_pro_parametry(par)[1]
    js, poz = gltf_a_uzly(glb)
    rozsahy, extra = ov["zive_rozsahy"], ov.get("zive_rozsahy_extra")
    ok_popis = True
    for z, s0 in zip(rz or [], stamps):
        n = js["nodes"][z["uzel"]]
        ok_popis &= z["dil"] == s0["dil"] and rozsahy[z["dil"]] is not None and "mesh" in n and "translation" in n and n["name"] == f"n{z['uzel']}"
        uz, od, pocet = z["vypln"]
        ok_popis &= poz[uz] is not None and od + pocet <= len(poz[uz]) and pocet == 24 and js["nodes"][uz]["name"] == f"n{uz}"
        ok_popis &= bool(np.allclose(np.array(n["translation"]), np.array(s0["logo"]["pos"]) + np.array(G._META_CACHE[h]), atol=1e-3))
    check(ok_popis, f"{popis}: kazde razitko ma platny dil, uzel loga (poloha = razitko + posun modelu) a rozsah vyplne (24 vrcholu) v uzlu hlinik")
    check(len({z["uzel"] for z in rz or []}) == len(rz or []), f"{popis}: uzly loga jsou ruzne")
    verejny = OV.ovladani_verejne(ov, "cs", S.SYSTEMY[par["system"]]["profil_mm"])
    check(verejny is not None and verejny.get("razitka") == rz, f"{popis}: popis razitek je i ve verejnem popisu ovladani (stul_ovladani_verejne)")
    vycisti()
    G.model_pro_parametry(par)                                                    # model S razitky (a info o nich) je v cache
    G.RAZITKA_VYCHOZI = False
    try:
        v0 = G.vodici(par, r)                                                     # vychozi je holy model: stara info o razitkach z cache se NESMI pripojit
    finally:
        G.RAZITKA_VYCHOZI = True
    check("razitka" not in v0["ovladani"], f"{popis}: bez razitek (RAZITKA_VYCHOZI = False) neni v popisu ovladani zadne razitko, ani kdyz je stara info v cache")
    vycisti()
    G.model_pro_parametry(par)
    check(getattr(G, "_RAZITKA_CACHE", {}).get(h) == rz, f"{popis}: cache razitek odpovida popisu")
    G._RAZITKA_CACHE.pop(h, None)                                                 # cache razitek vytlacena (ostatni cache drzi): model se prestavi a popis je znovu
    v1 = G.vodici(par, r)
    check(v1["ovladani"].get("razitka") == rz, f"{popis}: po vytlaceni cache razitek se model prestavi a popis razitek je znovu")

    # ---- B) tazeni
    vycisti()
    glb = G.model_pro_parametry(par)[1]
    js, poz = gltf_a_uzly(glb)
    logo0 = {z["uzel"]: np.array(js["nodes"][z["uzel"]]["translation"], float) for z in rz}
    host_dily = {z["dil"] for z in rz}
    pocet_tahu = 0
    for tah in ov["tahy"]:
        if not tah.get("zive"):
            continue
        for zmena in (+60.0, -60.0):
            delta = zmena / tah["faktor"]
            pocet_tahu += 1
            poz1, logo1 = klient_tazeni(poz, logo0, rozsahy, extra, tah, delta, rz, True)
            poz_bez, logo_bez = klient_tazeni(poz, logo0, rozsahy, extra, tah, delta, rz, False)
            hybane = set()
            for op in tah["zive"]:
                hybane |= set(op["ix"])
            popis_t = f"{popis} tah {tah['id']} {zmena:+.0f}"
            chyby_blizko, chyby_posun, chyby_stoji, chyby_bez = [], [], [], []
            for z in rz:
                dil, uzel = z["dil"], z["uzel"]
                r_dil = rozsahy[dil]
                host1 = poz1[r_dil[0]][r_dil[1]:r_dil[1] + r_dil[2]]
                host0 = poz[r_dil[0]][r_dil[1]:r_dil[1] + r_dil[2]]
                lo1, hi1 = host1.min(axis=0) - 5.0, host1.max(axis=0) + 5.0
                uz, od, pocet = z["vypln"]
                fill1 = poz1[uz][od:od + pocet]
                if dil in hybane:
                    for nazev, bod in (("logo", logo1[uzel]), ("vypln", fill1.mean(axis=0))):
                        if not (np.all(bod >= lo1) and np.all(bod <= hi1)):
                            chyby_blizko.append((nazev, dil, uzel))
                    # kontrola citlivosti: stary prohlizec (razitka stoji) - je razitko od dilu dal nez 5 mm?
                    host_bez = poz_bez[r_dil[0]][r_dil[1]:r_dil[1] + r_dil[2]]
                    if not (np.all(logo_bez[uzel] >= host_bez.min(axis=0) - 5.0) and np.all(logo_bez[uzel] <= host_bez.max(axis=0) + 5.0)):
                        chyby_bez.append(uzel)
                    if all(o["op"] == "posun" for o in tah["zive"] if dil in o["ix"]):
                        dh = host1.mean(axis=0) - host0.mean(axis=0)
                        if not (np.allclose(logo1[uzel] - logo0[uzel], dh, atol=1e-4) and np.allclose(fill1.mean(axis=0) - poz[uz][od:od + pocet].mean(axis=0), dh, atol=1e-4)):
                            chyby_posun.append((dil, uzel))
                else:
                    if not (np.allclose(logo1[uzel], logo0[uzel]) and np.allclose(fill1, poz[uz][od:od + pocet])):
                        chyby_stoji.append((dil, uzel))
            check(not chyby_blizko, f"{popis_t}: razitka na hybanych dilech zustanou u nich ({chyby_blizko[:3]})")
            check(not chyby_posun, f"{popis_t}: u samotneho posunu se razitko pohne PRESNE jako dil ({chyby_posun[:3]})")
            check(not chyby_stoji, f"{popis_t}: razitka na dilech, ktere se nehybou, stoji ({chyby_stoji[:3]})")
            bez_pohybu_chyba += len(chyby_bez)
            chyb_hostu_s_funkci += len(chyby_blizko)
    check(pocet_tahu >= 10, f"{popis}: vyzkouseno {pocet_tahu} tahu")
    celkem_stamps += len(rz)

print("C) citlivost testu")
check(bez_pohybu_chyba >= 5, f"bez pohybu razitek (puvodni chovani) invariant selhal u {bez_pohybu_chyba} razitek (musi byt aspon 5, jinak test nic nehlida)")
check(celkem_stamps >= 40, f"vyzkouseno {celkem_stamps} razitek")

print(f"\nvysledek: {OK} OK, {len(FAILS)} chyb")
sys.exit(1 if FAILS else 0)
