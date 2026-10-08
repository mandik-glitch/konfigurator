#!/usr/bin/env python3
"""Test VYSKOVE STAVITELNOSTI SPODNICH POLIC (bot8, 2026-10-04; Robert: "pridat vyskove stavitelnosti spodnich polic", mereni: "horni plocha desky od spodni hrany podelniku podepirajicich
pracovni plochu, a kazda dalsi spodni police jako mezera mezi policemi"; cisluje se SHORA).
NEZAVISLE na kodu generatoru (meri se z bboxu dilu): (1) vychozi (None) = dnesni rozlozeni, hash a pocet dilu beze zmeny; (2) police_h1 = presne odstup horni plochy desky 1. police pod spodni
hranou podelniku pracovni plochy, police_h<k> = mezera mezi horni plochou desky k-te police a spodkem ramu police nad ni; (3) meze: na nich bez problemu, o 0,1 mm dal problem `police_vyska`;
(4) zadane hodnoty meni hash; vyska polic bez police se do hashe nepocita.
Spusteni: api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_police_vysky.py"""
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


def klic(k):
    return tuple(klic(x) for x in k) if isinstance(k, list) else k


def mereni(r):
    """(y0 = spodni hrana podelniku pracovni plochy, [(horni plocha desky, spodek ramu police)] SHORA DOLU) z bboxu dilu."""
    kl = [klic(k) for k in r["klice"]]
    y0 = float(S._aabb(r["dily"][kl.index(("t", S.XRAIL_PRAC_L))])[0][1])
    desky = []
    for i, k in enumerate(kl):
        if r["dily"][i]["part_id"] == "product_4933" and (k == ("t", S.DESKA_POLICE) or (isinstance(k, tuple) and k[0] == "polic" and k[2] == ("t", S.DESKA_POLICE))):
            vrch = float(S._aabb(r["dily"][i])[1][1])
            ram = ("t", S.XRAIL_POL_L) if k == ("t", S.DESKA_POLICE) else ("polic", k[1], ("t", S.XRAIL_POL_L))
            desky.append((vrch, float(S._aabb(r["dily"][kl.index(ram)])[0][1])))
    return y0, sorted(desky, reverse=True)


def hodnoty(y0, desky):
    """efektivni (h1, h2, ...) z bboxu: h1 = y0 - horni plocha 1. desky, h_k = spodek ramu police nad ni - horni plocha desky k-te police."""
    h = [y0 - desky[0][0]]
    for k in range(1, len(desky)):
        h.append(desky[k - 1][1] - desky[k][0])
    return h


KONF = (dict(vyska=840), dict(vyska=1000), dict(vyska=1200), dict(vyska=1000, suplik=False), dict(vyska=1200, suplik=False, sirka=2000, hloubka=1000), dict(vyska=900, kolecka=False))
for base in KONF:
    for n in (1, 2, 3):
        kw = {**base, "police": n}
        r0 = S.sestav_stul(**kw)
        nn = r0["parametry"]["police"]
        if nn != n:
            continue
        pm = r0["police_meze"]
        nm = f"[{kw}]"
        # (1) vychozi: automaticky rozlozeno, efektivni hodnoty = z bboxu
        y0, desky = mereni(r0)
        h = hodnoty(y0, desky)
        check(len(desky) == n and all(abs(a - b) < 0.05 for a, b in zip(h, pm["hodnoty"])), f"{nm}: efektivni vysky polic z modelu {np.round(h, 2).tolist()} == police_meze {np.round(pm['hodnoty'], 2).tolist()}")
        check(all(pm["auto"]) and r0["problemy"] == [], f"{nm}: vychozi = automaticky, bez problemu")
        # (2)+(3) kazda police zvlast: stred rozsahu presne, meze bez problemu, o 0,1 mm dal problem
        for k in range(n):
            lo, hi = pm["min"][k], pm["max"][k]
            if hi <= lo:
                continue
            for v in sorted({lo, hi, round((lo + hi) / 2.0, 1)}):
                r1 = S.sestav_stul(**{**kw, f"police_h{k + 1}": v})
                y1, d1 = mereni(r1)
                h1 = hodnoty(y1, d1)
                check(r1["problemy"] == [] and abs(h1[k] - v) < 0.06, f"{nm}: police {k + 1} = {v}: bez problemu a z modelu {h1[k]:.2f}")
                # ostatni mezery zustavaji (automaticky odvozene od puvodniho rozlozeni): mezera pod zmenenou policí se nemeni, kdyz se meni jen odstup / mezera nad ni
                check(len(d1) == n, f"{nm}: police {k + 1} = {v}: pocet polic {len(d1)}")
            r_min = S.sestav_stul(**{**kw, f"police_h{k + 1}": round(lo - 0.2, 1)})
            r_max = S.sestav_stul(**{**kw, f"police_h{k + 1}": round(hi + 0.2, 1)})
            check(any(x["kod"] == "police_vyska" for x in r_min["problemy"]) and any(x["kod"] == "police_vyska" for x in r_max["problemy"]), f"{nm}: police {k + 1}: o 0,2 mm za mez je problem police_vyska")

# (4) hash a vychozi beze zmeny
h0 = G.kanonicky_hash({})
check(G.kanonicky_hash({"police_h1": None}) == h0 and sum(1 for k in S.sestav_stul()["klice"] if k[0] != "zasl") == 50, "vychozi (None): hash i pocet dilu beze zmeny")
check(G.kanonicky_hash({"police_h1": 400.0}) != h0, "zadana vyska police meni hash")
check(G.kanonicky_hash({"police": 0, "police_h1": 400.0}) == G.kanonicky_hash({"police": 0}), "bez police se vyska do hashe nepocita")
check(G.kanonicky_hash({"police": 1, "police_h2": 120.0}) == G.kanonicky_hash({"police": 1}), "vyska neexistujici (2.) police se do hashe nepocita")
# zadana hodnota == automaticka hodnota -> stejny MODEL (ne nutne stejny hash)
a = S.sestav_stul(vyska=1000, police=2)
b = S.sestav_stul(vyska=1000, police=2, police_h1=a["police_meze"]["hodnoty"][0], police_h2=a["police_meze"]["hodnoty"][1])
check([d["position"] for d in a["dily"]] == [d["position"] for d in b["dily"]], "zadane hodnoty rovne automatickym davaji stejny model")
print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
