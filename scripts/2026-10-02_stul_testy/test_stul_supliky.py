#!/usr/bin/env python3
"""Test POCTU SUPLIKU v ocelovem boxu 1 / 2 / 3 (bot8, 2026-10-05; Robert: vnejsi vysky 180 / 280 / 450 mm, SKU Suplik.ocel.440136 / Dvojsuplik.ocel.440137 / Trojsuplik.ocel.440138,
ceny 3 900 / 5 800 / 5 900 Kc bez DPH; karty #4956 (1 ks), #4930 (2 ks), #4957 (3 ks)).

NEZAVISLE na kodu generatoru (mereni z AABB a z accessoru GLB):
  A) modely v katalogu: stejny pudorys 565 x 583,1 mm, vyska 180 / 280,1 / 450 mm, HORNI plocha ve stejne lokalni vysce (box visi vrchem na pricich),
  B) stul: kazdy box ma v svetovych souradnicich stejny pudorys a stejnou polohu, vrch boxu pod pricemi (dotyk), spodek o prislusnou vysku niz; zadne problemy,
  C) parametr `suplik_pocet`: vychozi 2 (hash beze zmeny), 1 / 3 jiny hash, bez supliku se nepocita, neplatne hodnoty = StulChyba,
  D) kdyz se vyssi box nevejde (police, nizky stul), pocet se SNIZI (3 -> 2 -> 1) misto odebrani celeho boxu (`suplik_orez`); az kdyz nevejde ani 1, box se odebere,
  E) mapovani dilu (automaticke odebrani, 3D cast s menu poctu, zive tazeni posunu supliku, vyrobni vypis, cena),
  F) mrizka vysek stolu x poctu polic x poctu supliku: bez problemu, police nikdy neprunika boxem.
Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_supliky.py
V systemu 40:  api/venv/bin/python3 scripts/2026-10-04_system40/spust_v_systemu.py 40 scripts/2026-10-02_stul_testy/test_stul_supliky.py"""
import itertools
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


PARTY = {1: "product_4956", 2: "product_4930", 3: "product_4957"}
VYSKY = {1: 180.0, 2: 280.1, 3: 450.0}


def box(r):
    return [(i, d) for i, d in enumerate(r["dily"]) if d["part_id"] in S.SUPLIK_PARTY_VSE]


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


print("A) modely v katalogu")
check(S.SUPLIK_PARTY == PARTY and S.SUPLIK_POCTY == (1, 2, 3) and S.SUPLIK_POCET_VYCHOZI == 2 and S.VYCHOZI["suplik_pocet"] == 2, f"konstanty ({S.SUPLIK_PARTY})")
loks = {}
for n, pid in PARTY.items():
    lo, hi = S.glb_bbox(pid)
    loks[n] = (np.array(lo), np.array(hi))
    check(os.path.isfile(os.path.join(S.KATALOG_DIR, pid + ".glb")), f"{n} supliku: GLB {pid} je v katalogu")
    check(abs((hi[2] - lo[2]) - VYSKY[n]) < 0.15, f"{n} supliku: vyska modelu {hi[2] - lo[2]:.2f} mm (ma byt {VYSKY[n]})")
    check(abs((hi[0] - lo[0]) - 565.0) < 0.1 and abs((hi[1] - lo[1]) - 583.1) < 0.1, f"{n} supliku: pudorys {hi[0] - lo[0]:.1f} x {hi[1] - lo[1]:.1f} mm = 565 x 583,1")
    check(abs(hi[2] - 907.5) < 0.1 and abs(lo[0] + 2279.2) < 0.1 and abs(lo[1] + 950.4) < 0.1, f"{n} supliku: horni plocha a pudorys ve stejne lokalni poloze jako zavreny 4930 (z {hi[2]:.1f})")
check(loks[1][1][2] - loks[1][0][2] < loks[2][1][2] - loks[2][0][2] < loks[3][1][2] - loks[3][0][2], "vysky rostou 1 < 2 < 3")

print("B) stul: poloha a rozmery boxu")
ref = None
for v, pocet in itertools.product((1000, 1200), (1, 2, 3)):
    r = S.sestav_stul(vyska=v, police=0, suplik_pocet=pocet)
    b = box(r)
    check(len(b) == 1 and b[0][1]["part_id"] == PARTY[pocet] and not r["problemy"] and not r["odebrano"] and r["parametry"]["suplik_pocet"] == pocet and r["suplik_orez"] is None,
          f"vyska {v}, {pocet} supliku: jeden box {PARTY[pocet]}, bez problemu, bez orezu")
    lo, hi = bb(b[0][1])
    check(abs((hi[1] - lo[1]) - VYSKY[pocet]) < 0.15, f"vyska {v}, {pocet} supliku: vyska boxu ve svete {hi[1] - lo[1]:.2f} mm")
    pricky = [bb(d) for i, d in enumerate(r["dily"]) if r["klice"][i] in (["t", S.XRAIL_BOX1], ["t", S.XRAIL_BOX2])]
    check(len(pricky) == 2 and all(abs(hi[1] - p_[0][1]) < 0.2 for p_ in pricky), f"vyska {v}, {pocet} supliku: box visi VRCHEM na pricich (vrch {hi[1]:.1f} = spodek pricek {[round(float(p_[0][1]), 1) for p_ in pricky]})")
    if v == 1000:
        if ref is None:
            ref = (lo[[0, 2]], hi[[0, 2]], hi[1])
        check(np.allclose(lo[[0, 2]], ref[0], atol=0.05) and np.allclose(hi[[0, 2]], ref[1], atol=0.05) and abs(hi[1] - ref[2]) < 0.05, f"{pocet} supliku: pudorys a vrch boxu stejne jako u ostatnich poctu")
    # tri varianty: stejna sablonova pozice dilu (index 20), jen jiny dil
    check(r["klice"][b[0][0]] == ["t", S.BOX], f"{pocet} supliku: box je sablonovy dil {S.BOX}")

print("C) parametr, hash, neplatne hodnoty")
H0 = G.kanonicky_hash({})
check(G.kanonicky_hash(dict(suplik_pocet=2)) == H0, "vychozi 2 supliky: hash beze zmeny")
check(len({G.kanonicky_hash(dict(suplik_pocet=n)) for n in (1, 2, 3)}) == 3, "1 / 2 / 3 supliky: tri ruzne hashe")
check(G.kanonicky_hash(dict(suplik=False, suplik_pocet=3)) == G.kanonicky_hash(dict(suplik=False)), "bez supliku se pocet nepocita do hashe")
for spatne in (0, 4, -1, 2.5, "x", True, None):
    try:
        S.sestav_stul(suplik_pocet=spatne)
        check(False, f"suplik_pocet={spatne!r} se mel odmitnout")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"suplik_pocet={spatne!r}: StulChyba mimo_rozsah ({e})")
check(S.parametry_z_dotazu({"suplik_pocet": "3"}) == {"suplik_pocet": 3.0} and S.sestav_stul(**S.parametry_z_dotazu({"suplik_pocet": "3", "vyska": "1000"}))["parametry"]["suplik_pocet"] == 3, "dotaz ?suplik_pocet=3")
check(S.sestav_stul(suplik_pocet=3.0, vyska=1000)["parametry"]["suplik_pocet"] == 3, "cele cislo jako float je platne")

print("D) kdyz se vyssi box nevejde: pocet se snizi")
NIZKY = 0 if S.VYCHOZI["system"] == 40 else 1                       # stul 600 mm s polici: profil 30 / 35 pojme jeden suplik, profil 40 (silnejsi ram a police) uz zadny (box se odebere)
for v, pol, pozad, ocek in ((840, 1, 3, 2), (840, 1, 2, 2), (800, 1, 3, 2), (900, 1, 3, 3), (600, 1, 3, NIZKY), (600, 1, 2, NIZKY), (1000, 1, 3, 3), (1200, 2, 3, 3)):
    r = S.sestav_stul(vyska=v, police=pol, suplik_pocet=pozad)
    b = box(r)
    if ocek:
        check(len(b) == 1 and b[0][1]["part_id"] == PARTY[ocek] and r["parametry"]["suplik_pocet"] == ocek and not r["odebrano"] and not r["problemy"],
              f"vyska {v}, police {pol}, pozadovano {pozad} -> {ocek} supliku (ma {[d['part_id'] for i, d in b]}, odebrano {[o['volba'] for o in r['odebrano']]})")
        check(r["suplik_orez"] == ({"pozadovano": pozad, "pocet": ocek} if ocek < pozad else None), f"vyska {v}, pozadovano {pozad}: suplik_orez {r['suplik_orez']}")
    else:
        check(not b and [o["volba"] for o in r["odebrano"]] == ["suplik"] and r["suplik_orez"] is None and not r["problemy"], f"vyska {v}, police {pol}, pozadovano {pozad}: ani 1 suplik se nevejde -> box odebran")
r_ne = S.sestav_stul(vyska=140, police=0, suplik_pocet=3)
check(not box(r_ne) and any(o["volba"] == "suplik" for o in r_ne["odebrano"]) and r_ne["suplik_orez"] is None, "nevejde se ani 1 suplik: box odebran (bez orezu)")
# max_polic neroste s poctem supliku
for v in (840, 1000, 1200):
    mp = [S.sestav_stul(vyska=v, police=1, suplik_pocet=n)["max_polic"] for n in (1, 2, 3)]
    check(mp[0] >= mp[1] >= mp[2], f"vyska {v}: max polic klesa s poctem supliku {mp}")

print("E) mapovani dilu, 3D, vyrobni vypis, cena")
check(all(S.PREPINAC_DILU[pid] == "suplik" for pid in S.SUPLIK_PARTY_VSE) and all(pid in G.MATERIAL_DILU and G.MATERIAL_DILU[pid] == "ocel" for pid in S.SUPLIK_PARTY_VSE), "dily boxu: prepinac `suplik` a material ocel")
for pocet in (1, 2, 3):
    r = S.sestav_stul(vyska=1200, police=0, suplik_pocet=pocet)
    ov = S.ovladani_3d(r)
    cast = next((c for c in ov["casti"] if c["id"] == "suplik"), None)
    check(cast is not None and "suplik_pocet" in cast["param"], f"{pocet} supliku: 3D cast `suplik` ma parametr suplik_pocet")
    if cast:
        menu = [m["text"] for m in cast["menu"]]
        ostatni = [c for c in (1, 2, 3) if c != pocet]
        check(all(any(f"Box s {c} " in t for t in menu) for c in ostatni) and not any(f"Box s {pocet} " in t for t in menu), f"{pocet} supliku: nabidka nabizi ostatni pocty ({menu})")
        nast = {m["text"]: m["nastav"] for m in cast["menu"]}
        check(all(m.get("nastav") == {"suplik_pocet": c} for c in ostatni for m in cast["menu"] if f"Box s {c} " in m["text"]), f"{pocet} supliku: polozky menu nastavuji suplik_pocet")
    tah = next((t for t in ov["tahy"] if t["id"] == "suplik_posun"), None)
    check(tah is not None and any(o["op"] == "posun" and any(r["dily"][i]["part_id"] == PARTY[pocet] for i in o["ix"]) for o in tah.get("zive", [])), f"{pocet} supliku: zive tazeni posunu supliku hybe boxem")
    v = S.vyrobni_vypis(r)
    pris = [q for q in v["prislusenstvi"] if q["karta_id"] == int(PARTY[pocet].split("_")[1])]
    check(len(pris) == 1 and pris[0]["pocet"] == 1, f"{pocet} supliku: vyrobni vypis nese kartu {PARTY[pocet]} jednou")
    check(not [q for q in v["prislusenstvi"] if q["karta_id"] in (4930, 4956, 4957) and q["karta_id"] != int(PARTY[pocet].split("_")[1])], f"{pocet} supliku: v prislusenstvi jen jeden druh boxu")
    ent = [e for e in S.entries_pro_cenu(r["dily"]) if e["part_id"] in S.SUPLIK_PARTY_VSE]
    check(ent == [{"part_id": PARTY[pocet]}], f"{pocet} supliku: polozka ceny {ent}")
    glb = G.model_pro_parametry(r["parametry"])[1]
    check(len(glb) > 100000, f"{pocet} supliku: GLB stolu se postavi ({len(glb)} B)")
# automaticke odebrani podle dilu (kolize s jinym dilem tez najde box s libovolnym poctem): zuzeny stul
for pocet in (1, 2, 3):
    r = S.sestav_stul(sirka=700, hloubka=500, vyska=1000, police=0, suplik_pocet=pocet)
    check((not box(r) and any(o["volba"] == "suplik" for o in r["odebrano"])) or box(r), f"zuzeny stul, {pocet} supliku: box zustane, nebo se odebere pres prepinac `suplik`")
# kolize zpusobena POSUNEM se neresi snizenim poctu (nabidka odebrani zustava)
rp = S.sestav_stul(sirka=1500, vyska=1000, police=0, suplik_pocet=3, suplik_posun=-900.0)
check(all(d["part_id"] == PARTY[3] for i, d in box(rp)) and rp["suplik_orez"] is None, "kolize posunem: pocet supliku se nesnizuje")

print("F) mrizka: vyska x police x pocet supliku")
n_mr = 0
for v, pol, pocet in itertools.product((500, 600, 700, 840, 900, 1000, 1100, 1200), (0, 1, 2, 3), (1, 2, 3)):
    r = S.sestav_stul(vyska=v, police=pol, suplik_pocet=pocet)
    n_mr += 1
    n = f"vyska {v}, police {pol}, {pocet} supliku"
    check(not r["problemy"], f"{n}: bez problemu ({[p['kod'] for p in r['problemy']][:3]})")
    b = box(r)
    if b:
        lo, hi = bb(b[0][1])
        ef = r["parametry"]["suplik_pocet"]
        check(b[0][1]["part_id"] == PARTY[ef] and ef <= pocet, f"{n}: dil boxu odpovida efektivnimu poctu {ef}")
        for i, d in enumerate(r["dily"]):
            if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("pol"):          # police pod boxem: horni plocha desky police neprunika boxem
                dlo, dhi = bb(d)
                if min(hi[0], dhi[0]) - max(lo[0], dlo[0]) > 1.0 and min(hi[2], dhi[2]) - max(lo[2], dlo[2]) > 1.0:
                    check(dhi[1] <= lo[1] + 0.5, f"{n}: police (horni plocha {dhi[1]:.1f}) je pod boxem (spodek {lo[1]:.1f})")
    else:
        check(r["suplik_orez"] is None, f"{n}: bez boxu neni orez")
print(f"   mrizka: {n_mr} konfiguraci")

if FAILS:
    print(f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
    sys.exit(1)
print(f"\n{OK} kontrol OK")
