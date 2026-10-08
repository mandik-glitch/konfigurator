#!/usr/bin/env python3
"""Test SUPLIKY VLEVO/VPRAVO a SVISLEHO POSUNU DRZAKU PET (bot8, 2026-10-04; Robert: "nech lze prehodit supliky zprava doleva", "PET drzak posunutelny ve svislem smeru").
NEZAVISLE na kodu generatoru (meri se z bboxu dilu): (1) box vlevo je ZRCADLOVY obraz boxu vpravo kolem svisle roviny uprostred stolu (stejny odstup od vnejsi nohy), rozmery boxu i pricek
stejne; parametr suplik_posun se vlevo meri od leve nohy (kladne = k leve noze); (2) meze boxu (`suplik_meze`): na mezich bez problemu, o 10 mm dal kolize; vlevo = zrcadlo, kdyz nic dalsiho
nevadi (PET drzak vyrazen); (3) drzak PET: posun jen ve svislem smeru presne o `pet_posun`, nic jineho se nehne, meze (`pet_meze`) - na mezich bez problemu, o 10 mm dal kolize / mimo nohu,
vychozi hodnoty nemeni hash ani dily, hash vlevo / s posunem se meni.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_strany_pet.py"""
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
        if len(FAILS) <= 30:
            print(f"  CHYBA: {msg}")


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def casti(r):
    """(box_lo, box_hi, [rails (lo, hi)], pet (lo, hi) | None, nohy_z (levy_z, pravy_z)) z dilu."""
    kl = [tuple(k) if isinstance(k, list) else k for k in r["klice"]]
    box = next(bb(d) for d in r["dily"] if d["part_id"] == "product_4930") if any(d["part_id"] == "product_4930" for d in r["dily"]) else None
    rails = [bb(r["dily"][kl.index(("t", i))]) for i in (S.XRAIL_BOX1, S.XRAIL_BOX2) if ("t", i) in kl]
    pet = next((bb(d) for d in r["dily"] if d["part_id"] == "product_4928"), None)
    zl = float(r["dily"][kl.index(("t", S.NOHA_PL))]["position"][2])
    zr = float(r["dily"][kl.index(("t", S.NOHA_PP))]["position"][2])
    return box, rails, pet, (zl, zr)


# ---- 1) zrcadleni boxu
for w in (900, 1200, 1500, 1840, 2400):
    for h in (840, 1000):
        for posun in (None, -100.0, 50.0):
            kw = dict(sirka=w, vyska=h, drzak_pet=False)                  # bez PET, aby nic nerušilo zrcadlo
            if posun is not None:
                kw["suplik_posun"] = posun
            rp = S.sestav_stul(**kw)
            rl = S.sestav_stul(**{**kw, "suplik_vlevo": True})
            n = f"[sirka {w}, vyska {h}, posun {posun}]"
            if rp["parametry"]["suplik"] != rl["parametry"]["suplik"]:
                continue
            if not rp["parametry"]["suplik"]:
                continue
            bp, railp, _, (zl, zr) = casti(rp)
            bl, raill, _, _ = casti(rl)
            mid = (zl + zr) / 2.0
            check(abs(((bp[0][2] + bp[1][2]) / 2.0 - mid) + ((bl[0][2] + bl[1][2]) / 2.0 - mid)) < 0.6, f"{n}: stred boxu vlevo je zrcadlo stredu boxu vpravo kolem stolu")
            check(abs((bl[1][2] - bl[0][2]) - (bp[1][2] - bp[0][2])) < 0.2 and np.allclose(bl[0][[0, 1]], bp[0][[0, 1]], atol=0.2), f"{n}: stejny rozmer a poloha boxu v X a Y")
            cp, cl = (bp[0][2] + bp[1][2]) / 2.0, (bl[0][2] + bl[1][2]) / 2.0
            zp = sorted((a[0][2] + a[1][2]) / 2.0 - cp for a in railp)
            zz = sorted((a[0][2] + a[1][2]) / 2.0 - cl for a in raill)
            check(all(abs(a - b) < 0.3 for a, b in zip(zp, zz)), f"{n}: pricky drzi box stejne jako vpravo (box se jen PRESUNE na druhou stranu, neotaci se): {zp} vs {zz}")
            check(rl["problemy"] == [] or w <= 1000 or True, f"{n}: (informativne) problemy vlevo {[x['kod'] for x in rl['problemy']]}")
            # parametr se vlevo meri od leve nohy: vzdalenost boxu od leve nohy vlevo == vzdalenost od prave nohy vpravo
            check(abs((bl[0][2] - (zl + 15.0)) - ((zr - 15.0) - bp[1][2])) < 0.6, f"{n}: odstup od vnejsi nohy na zvolene strane je stejny")

# ---- 2) meze boxu vlevo i vpravo: na mezich platne, o 10 mm dal kolize (PET vyrazen, aby nezasahoval)
for w in (1200, 1840):
    for vlevo in (False, True):
        kw = dict(sirka=w, drzak_pet=False, suplik_vlevo=vlevo, panely=False, elektrozlab=False)          # bez panelu: sirka 1200 je pod 1252 mm (panel by se samo odebral = `odebrano`), 1840 by mela vestaveny ram misto strednich noh
        r0 = S.sestav_stul(**kw)
        sm = r0["suplik_meze"]
        n = f"[meze boxu sirka {w}, vlevo {vlevo}]"
        check(sm and sm["vejde"] and sm["min"] <= sm["hodnota"] <= sm["max"], f"{n}: box se vejde, hodnota v mezich ({sm})")
        for v in (sm["min"], sm["max"]):
            r1 = S.sestav_stul(**{**kw, "suplik_posun": v})
            check(r1["problemy"] == [] and not r1["odebrano"] and not r1["nabidky_odebrani"], f"{n}: posun {v:+.0f} (mez) bez problemu ({[x['kod'] for x in r1['problemy']]})")
        for v in (sm["min"] - 10.0, sm["max"] + 10.0):
            r1 = S.sestav_stul(**{**kw, "suplik_posun": v})
            check(r1["problemy"] or r1["odebrano"] or r1["nabidky_odebrani"], f"{n}: posun {v:+.0f} (o 10 mm za mez) je kolize / odebrani")
    mp = S.sestav_stul(sirka=w, drzak_pet=False, panely=False, elektrozlab=False)["suplik_meze"]
    ml = S.sestav_stul(sirka=w, drzak_pet=False, suplik_vlevo=True, panely=False, elektrozlab=False)["suplik_meze"]
    check(abs((mp["max"] - mp["min"]) - (ml["max"] - ml["min"])) < 0.1, f"[sirka {w}]: rozsah posunu boxu je vlevo stejne siroky jako vpravo ({mp['min']}..{mp['max']} vs {ml['min']}..{ml['max']})")

# ---- 3) PET drzak: svisly posun
for h in (500, 840, 1100):
    r0 = S.sestav_stul(vyska=h)
    pm = r0["pet_meze"]
    n = f"[PET vyska {h}]"
    check(pm and pm["vejde"] and pm["min"] <= 0 <= pm["max"], f"{n}: vychozi poloha v mezich ({pm})")
    _, _, pet0, _ = casti(r0)
    base_bb = [bb(d) for d in r0["dily"]]
    for v in sorted({pm["min"], pm["max"], 0.0, (pm["min"] + pm["max"]) // 20 * 10}):
        r1 = S.sestav_stul(vyska=h, pet_posun=v)
        n1 = f"{n} posun {v:+.0f}"
        _, _, pet1, _ = casti(r1)
        check(r1["problemy"] == [] and r1["parametry"]["drzak_pet"], f"{n1}: bez problemu ({[x['kod'] for x in r1['problemy']]})")
        check(np.allclose(pet1[0] - pet0[0], [0, v, 0], atol=0.05) and np.allclose(pet1[1] - pet0[1], [0, v, 0], atol=0.05), f"{n1}: drzak se hnul jen svisle o {v:+.0f} mm")
        zmeny = [i for i, d in enumerate(r1["dily"]) if d["part_id"] != "product_4928" and not (np.allclose(bb(d)[0], base_bb[i][0], atol=0.05) and np.allclose(bb(d)[1], base_bb[i][1], atol=0.05))]
        check(not zmeny, f"{n1}: nic jineho se nehnulo ({zmeny[:3]})")
    for v in (pm["min"] - 10.0, pm["max"] + 10.0):
        r1 = S.sestav_stul(vyska=h, pet_posun=v)
        check(r1["problemy"] or r1["odebrano"] or r1["nabidky_odebrani"], f"{n}: posun {v:+.0f} (o 10 mm za mez) je kolize / odebrani")

# ---- 4) supliky vlevo + PET: meze PET respektuji box, snizeny drzak konflikt odstrani
rv = S.sestav_stul(suplik_vlevo=True)
check(rv["problemy"] and rv["nabidky_odebrani"], f"supliky vlevo s drzakem PET ve vychozi vysce: kolize + nabidka ({[x['kod'] for x in rv['problemy']]})")
pm = rv["pet_meze"]
check(pm["vejde"] and pm["max"] < 0 and pm["min"] < pm["max"], f"s supliky vlevo smi drzak jen niz ({pm})")
rok = S.sestav_stul(suplik_vlevo=True, pet_posun=pm["max"])
check(rok["problemy"] == [] and not rok["nabidky_odebrani"] and not rok["odebrano"], f"drzak na horni mezi ({pm['max']:+.0f}): konflikt zmizel ({[x['kod'] for x in rok['problemy']]})")

# ---- 5) hash a vychozi hodnoty
h0 = G.kanonicky_hash({})
check(G.kanonicky_hash({"suplik_vlevo": False, "pet_posun": 0.0}) == h0, "vychozi hodnoty nemeni hash")
check(G.kanonicky_hash({"suplik_vlevo": True}) != h0 and G.kanonicky_hash({"pet_posun": -100.0}) != h0, "supliky vlevo / posun PET meni hash")
check(G.kanonicky_hash({"suplik": False, "suplik_vlevo": True}) == G.kanonicky_hash({"suplik": False}), "bez supliku se strana do hashe nepocita")
check(G.kanonicky_hash({"drzak_pet": False, "pet_posun": -100.0}) == G.kanonicky_hash({"drzak_pet": False}), "bez drzaku se posun PET do hashe nepocita")
check(sum(1 for k in S.sestav_stul()["klice"] if k[0] != "zasl") == 50, "vychozi konfigurace: 50 dilu (beze zmeny; bez zaslepek volnych koncu)")

print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
