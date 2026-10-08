#!/usr/bin/env python3
"""Test ZIVEHO tazeni (bot8, 2026-10-03): operace `zive` u tahu (api/stul_konfigurator._zive_operace) + `zive_rozsahy` (api/stul_glb) tak, jak je pouzije
prohlizec - hybe vrcholy dilu primo v nactenem modelu bez dotazu na server. Docs: docs/OVLADANI_3D.md.

Nezavisle na kodu operaci: z GLB stolu v puvodnim stavu se operace APLIKUJI (stejna pravidla jako v prohlizeci: posun / natahni / roztahni) o zmenu parametru
a vysledek se porovna s GLB, ktery server poskladal pro NOVY parametr. Stredni noha, rameno LED a suplik musi sedet PRESNE (<= 0.05 mm, po odecteni
globalniho vycentrovani modelu); rozmery (sirka, hloubka, vyska) jsou NAHLED - tam se hlida, ze obalka modelu sedi (<= 25 mm), ze vetsina dilu je u cile a ze PRISLUSENSTVI SE NENATAHUJE.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_zive.py"""
import json
import os
import struct
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


def pozice_uzlu(glb):
    """[ndarray Nx3 (float32 -> float64)] pro kazdy uzel GLB (POSITION prvniho primitiva jeho meshe)."""
    delka_json = struct.unpack_from("<I", glb, 12)[0]
    js = json.loads(glb[20:20 + delka_json])
    bin0 = 20 + delka_json + 8
    out = []
    for n in js["nodes"]:
        if "mesh" not in n:                                            # prazdny pivot (spodni suplik boxu: p1) - bez vrcholu, indexy uzlu zustavaji
            out.append(None)
            continue
        prim = js["meshes"][n["mesh"]]["primitives"][0]
        acc = js["accessors"][prim["attributes"]["POSITION"]]
        bv = js["bufferViews"][acc["bufferView"]]
        a = np.frombuffer(glb, dtype="<f4", count=acc["count"] * 3, offset=bin0 + bv["byteOffset"]).reshape(-1, 3).astype(float)
        out.append(a.copy())
    return out


def aplikuj(poz, rozsahy, tah, delta, extra=None):
    """Stejna pravidla jako v prohlizeci (webapp/js/v3d-ovladani.js): delta = posun uchytu podel osy (mm); osa = tah["osa"]. `extra` = zive_rozsahy_extra (dil rozdeleny do vice uzlu:
    spodni suplik boxu; dalsi rozsahy se hybou spolu s dilem, klic = index dilu jako text)."""
    osa = np.array(tah["osa"], float)
    for op in tah["zive"]:
        d = op["k"] * delta * osa
        for i in op["ix"]:
            for r in ([rozsahy[i]] + list((extra or {}).get(str(i), []))):
                if r is None:
                    continue
                v = poz[r[0]][r[1]:r[1] + r[2]]
                if op["op"] == "posun":
                    v += d
                    continue
                u = v @ osa
                stred = (u.min() + u.max()) / 2.0
                strana = np.where(u > stred + 0.05, 1, np.where(u < stred - 0.05, -1, 0))        # 0 = vrchol PRESNE uprostred dilu (mesh desky ma stredovy vrchol plochy)
                if op["op"] == "natahni":
                    f = np.where(strana == 0, 0.5, np.where(strana == (1 if op["strana"] > 0 else -1), 1.0, 0.0))
                    v += f[:, None] * d
                elif op["op"] == "roztahni":
                    v += strana[:, None] * d
    return poz


def stav(par):
    r = S.odpoved(par)
    v = G.vodici(par, r)
    h, glb = G.model_pro_parametry(par, razitka=False)
    return r, v["ovladani"], h, glb


def porovnej(par, tid, zmena, tolerance, jmeno):
    """GLB po zmene parametru `tid` o `zmena` (v jednotkach parametru) vs. operace aplikovane na puvodni GLB."""
    r0, ov0, h0, glb0 = stav(par)
    tah = next((t for t in ov0["tahy"] if t["id"] == tid), None)
    check(tah is not None and tah.get("zive"), f"{jmeno}: tah {tid} ma zive operace")
    if not tah or not tah.get("zive"):
        return None
    par1 = dict(r0["parametry"])
    par1[tah["param"]] = tah["hodnota"] + zmena
    r1, ov1, h1, glb1 = stav(par1)
    delta = zmena / tah["faktor"]
    poz0 = pozice_uzlu(glb0)
    poz1 = pozice_uzlu(glb1)
    roz = ov0["zive_rozsahy"]
    check(len(roz) == len(r0["dily"]), f"{jmeno}: rozsahy jsou pro kazdy dil ({len(roz)} / {len(r0['dily'])})")
    check(len(r1["dily"]) == len(r0["dily"]), f"{jmeno}: zmena parametru nezmenila pocet dilu ({len(r0['dily'])} -> {len(r1['dily'])})")
    if len(r1["dily"]) != len(r0["dily"]):
        return None                                                    # zmena odebrala priblizne prislusenstvi - jina sada dilu, nejde porovnat po dilech
    extra = ov0.get("zive_rozsahy_extra") or {}
    pred = aplikuj([None if a is None else a.copy() for a in poz0], roz, tah, delta, extra)
    shift = np.array(G._META_CACHE[h1]) - np.array(G._META_CACHE[h0])          # globalni vycentrovani modelu (klient ho nedela)
    if tid in ("sirka", "hloubka", "vyska"):
        shift = shift * 0.0                                            # operace rozmeru uz vycentrovani emuluji (levy/pravy okraj +-delta)
    chyby = []
    for i, r in enumerate(roz):
        if r is None:
            continue
        a = pred[r[0]][r[1]:r[1] + r[2]] + shift
        b = poz1[r[0]][r[1]:r[1] + r[2]]
        chyby.append((float(np.abs(a - b).max()), i))
    for i_, lst in extra.items():                                      # dalsi rozsahy dilu (spodni suplik boxu): taky musi sedet na model ze serveru
        for r in lst:
            a = pred[r[0]][r[1]:r[1] + r[2]] + shift
            b = poz1[r[0]][r[1]:r[1] + r[2]]
            chyby.append((float(np.abs(a - b).max()), int(i_)))
    return chyby, pred, poz1, shift, roz, r0


def main():
    # ---- PRESNE: stredni noha, rameno LED, suplik
    pres = (("stredni_noha", dict(sirka=2000, stredni_noha=900.0), (+60.0, -80.0)),
            ("stredni_noha", dict(sirka=2400, stredni_noha=700.0), (+120.0,)),
            ("led_rameno", dict(sirka=1600), (+80.0, -100.0)),
            ("suplik_posun", dict(sirka=1600), (-120.0, +40.0)),
            ("stredni_noha", dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, stredni_noha=900.0), (+60.0, -80.0)),    # stredni vzpera jede se stredni nohou
            ("led_rameno", dict(sirka=1600, vzpery=True), (-60.0, +60.0)),
            ("suplik_posun", dict(sirka=1600, suplik_vlevo=True, drzak_pet=False), (-120.0, +40.0)),       # supliky vlevo: osa tahu miri k leve strane, posun se meri od leve nohy
            ("suplik_posun", dict(sirka=2400, suplik_vlevo=True, pet_posun=-150.0), (+60.0, -90.0)),
            ("pet_posun", dict(), (+60.0, -80.0)),                                                          # drzak PET lahve: svisly posun
            ("pet_posun", dict(vyska=1100, pet_posun=-200.0, suplik_vlevo=True), (-50.0, +40.0)),
            ("police_h1", dict(), (+40.0, -30.0)),                                                          # vyska polic: tazeni police dolu / nahoru (sonda)
            ("police_h1", dict(police=3, vyska=1200), (+60.0, -40.0)),
            ("police_h2", dict(police=3, vyska=1200), (+30.0, -20.0)),
            ("police_h3", dict(police=3, vyska=1200, police_h1=450.0), (+20.0, -30.0)),
            ("police_h2", dict(police=2, vyska=1000, suplik=False, sirka=2000, hloubka=1000), (+20.0, -20.0)))
    for tid, par, zmeny in pres:
        for z in zmeny:
            j = f"{tid} {par} {z:+.0f} mm"
            res = porovnej(par, tid, z, 0.05, j)
            if not res:
                continue
            chyby, r0_ = res[0], res[5]
            # desky: mesh ma zaoblene hrany (prstenec vrcholu <= 2,4 mm od konce), ktery server meri spolu s deskou (zmena delky o x % = az x % z 2,4 mm); zive operace ho posouvaji pevne s koncem
            # -> u desek povolena odchylka 0,3 mm (rozmer a poloha desky sedi presne), jinde 0,05 mm
            lim = lambda i: 0.3 if r0_["dily"][i]["part_id"] == "product_4933" else 0.05          # noqa: E731
            nejhorsi = max(chyby, key=lambda ci: ci[0] / lim(ci[1])) if chyby else (0, -1)
            check(chyby and all(c <= lim(i) for c, i in chyby), f"{j}: zive tazeni = model ze serveru (nejvetsi odchylka {nejhorsi[0]:.3f} mm u dilu {nejhorsi[1]})")
    # ---- NAHLED: rozmery
    NOHA = dict(stredni_opora="noha")          # NAHLED vzdy se strednimi nohami: deska police s vyrezem pro vestaveny ram je z kusu bez rozsahu vrcholu (stejne jako deska s otvory) a zustava do pusteni uchytu
    for tid, par, zmeny in (("sirka", dict(sirka=1800, **NOHA), (+200.0, -100.0)), ("sirka", dict(sirka=2000, stredni_noha=900.0, **NOHA), (+200.0,)), ("hloubka", dict(sirka=1800, **NOHA), (+100.0, -100.0)), ("vyska", dict(sirka=1800, **NOHA), (+100.0, -100.0))):
        for z in zmeny:
            j = f"{tid} {par} {z:+.0f} mm (nahled)"
            res = porovnej(par, tid, z, 3.0, j)
            if not res:
                continue
            chyby, pred, poz1, shift, roz, r0 = res
            ch = np.array([c for c, _ in chyby])
            check(len(ch) > 0 and (ch <= 3.0).mean() >= 0.5, f"{j}: aspon polovina dilu je u cile (<=3 mm): {(ch <= 3.0).mean() * 100:.0f} %")
            # obalka modelu (vsechny vrcholy)
            a = np.vstack([q for q in pred if q is not None]) + shift
            b = np.vstack([q for q in poz1 if q is not None])
            ob = np.abs((a.max(axis=0) - a.min(axis=0)) - (b.max(axis=0) - b.min(axis=0)))
            check(float(ob.max()) <= 25.0, f"{j}: obalka modelu sedi na ~2 cm - je to jen nahled (rozdil {ob.round(1).tolist()} mm)")
            print(f"    info {j}: dily u cile {(ch <= 3.0).sum()}/{len(ch)}, median odchylky {np.median(ch):.2f} mm, max {ch.max():.1f} mm")
    # ---- cache se drzi spolecne: horky model po mnoha jinych stavbach nesmi ztratit vodici (dřive META vypadla driv nez GLB)
    horky = dict(sirka=2000, stredni_noha=900.0)
    G.model_pro_parametry(horky, razitka=False)
    for k_ in range(G.CACHE_MAX + 4):
        G.model_pro_parametry(dict(sirka=2000, stredni_noha=300.0 + 10 * k_), razitka=False)
        G.model_pro_parametry(horky, razitka=False)                                    # horky model se porad pouziva
    check(G.vodici(horky, S.odpoved(horky)) is not None, "horky model po mnoha jinych stavbach stale ma vodici (cache drzi spolecne)")
    # ---- Robert 2026-10-03: "roztahuje se derovany panel, aniz by se to roztahovani tykalo" - prislusenstvi s fixni velikosti se NIKDY nenatahuje ani neroztahuje
    for par_ in (dict(), dict(sirka=1800), dict(sirka=2000, stredni_noha=900.0), dict(sirka=2400, hloubka=1000, vyrez1=True, loz=True), dict(sirka=1600, led_rameno=900.0)):
        r_ = S.odpoved(par_)
        v_ = G.vodici(par_, r_)["ovladani"]
        # nezavisle na kodu: dily podle part_id z vysledku generatoru
        pid = {i: d["part_id"] for i, d in enumerate(r_["dily"])}
        for t_ in v_["tahy"]:
            for op in t_.get("zive", []):
                if op["op"] in ("natahni", "roztahni"):
                    spatne = sorted({pid[i] for i in op["ix"] if pid[i] not in S.PROFIL_PARTS + ("product_4933",)})
                    check(not spatne, f"{par_} / tah {t_['id']}: {op['op']} natahuje jen profily a desky, ne {spatne}")
        # vodorovne tahy rozmeru: dily s fixni velikosti (panely, LED, elektrozlab, boxy, kolecka) maji po operacich STEJNE rozmery
        for tid, zm in (("sirka", 300.0), ("hloubka", 200.0), ("vyska", 100.0)):
            t_ = next(x_ for x_ in v_["tahy"] if x_["id"] == tid)
            poz = pozice_uzlu(G.model_pro_parametry(par_, razitka=False)[1])
            roz_ = v_["zive_rozsahy"]
            pred = aplikuj([None if a is None else a.copy() for a in poz], roz_, t_, zm / t_["faktor"], v_.get("zive_rozsahy_extra"))
            for i, d in enumerate(r_["dily"]):
                if roz_[i] is None or d["part_id"] in S.PROFIL_PARTS + ("product_4933",):
                    continue
                a0 = poz[roz_[i][0]][roz_[i][1]:roz_[i][1] + roz_[i][2]]
                a1 = pred[roz_[i][0]][roz_[i][1]:roz_[i][1] + roz_[i][2]]
                check(np.allclose(a1.max(axis=0) - a1.min(axis=0), a0.max(axis=0) - a0.min(axis=0), atol=1e-6),
                      f"{par_} / {tid}: dil {i} ({d['part_id']}) po nahledu ma STEJNY rozmer jako predtim")
    # ---- sikme vzpery ramen LED: nikdy se nenatahuji ani neroztahuji (jsou pevne na stojkach a rameni, jedou s nimi) - rozmery dilu vzper se pri nahledu nemeni
    if S.SYSTEMY[S.VYCHOZI["system"]]["vzpery"]:                        # system 40 sikme vzpery nema (zapnuty parametr se odebere), blok se v nem preskoci
        PVZ = dict(sirka=2000, panely=False, elektrozlab=False, vzpery=True, stredni_noha=900.0)
        r_vz = S.sestav_stul(**PVZ)
        vz_i = [i for i, k in enumerate(r_vz["klice"]) if isinstance(k, list) and k and k[0] == "vz"]
        check(len(vz_i) == 9, f"vzpery: 9 dilu (3 vzpery) ({len(vz_i)})")
        v_vz = G.vodici(PVZ, S.odpoved(PVZ))["ovladani"]
        poz_vz = pozice_uzlu(G.model_pro_parametry(PVZ, razitka=False)[1])
        roz_vz = v_vz["zive_rozsahy"]
        for tid, zm in (("sirka", 300.0), ("hloubka", 200.0), ("vyska", 100.0), ("led_rameno", 100.0), ("stredni_noha", 100.0)):
            t_ = next(x_ for x_ in v_vz["tahy"] if x_["id"] == tid)
            pred = aplikuj([None if a is None else a.copy() for a in poz_vz], roz_vz, t_, zm / t_["faktor"], v_vz.get("zive_rozsahy_extra"))
            for i in vz_i:
                a0 = poz_vz[roz_vz[i][0]][roz_vz[i][1]:roz_vz[i][1] + roz_vz[i][2]]
                a1 = pred[roz_vz[i][0]][roz_vz[i][1]:roz_vz[i][1] + roz_vz[i][2]]
                check(np.allclose(a1.max(axis=0) - a1.min(axis=0), a0.max(axis=0) - a0.min(axis=0), atol=1e-6), f"vzpery / {tid}: dil vzpery {i} se nenatahuje")
    # operace nesmi odkazovat na neexistujici dily a rozsahy musi byt platne
    r, ov, h, glb = stav(dict(sirka=2000, stredni_noha=900.0))
    poz = pozice_uzlu(glb)
    check(all(r_ is None or (0 <= r_[0] < len(poz) and 0 <= r_[1] and r_[1] + r_[2] <= len(poz[r_[0]])) for r_ in ov["zive_rozsahy"]), "rozsahy ukazuji do existujicich uzlu a vrcholu")
    check(all(0 <= i < len(ov["zive_rozsahy"]) for t in ov["tahy"] for op in t.get("zive", []) for i in op["ix"]), "operace odkazuji na existujici dily")
    check(all(r_ is not None or r["dily"][i_]["part_id"] == "product_4933" for i_, r_ in enumerate(ov["zive_rozsahy"])) and sum(1 for r_ in ov["zive_rozsahy"] if r_ is None) <= 5,
          "bez rozsahu jsou jen desky (deska s otvory / kusy desky police s vyrezem pro vestaveny ram)")
    check(all("zive" not in t for t in ov["tahy"] if t["typ"] == "rovina"), "vyrezy (rovina) nemaji zive operace (deska je jeden povrch)")
    # bez nastaveni nic navic v odpovedi: kdyz neni zadny tah se zive, nejsou ani rozsahy
    # (jen kontrola, ze pole existuje u vychoziho stolu)
    check("zive_rozsahy" in G.vodici({}, S.odpoved({}))["ovladani"], "vychozi stul ma zive_rozsahy")
    if FAILS:
        print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
        return 1
    print(f"\n{OK} kontrol OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
