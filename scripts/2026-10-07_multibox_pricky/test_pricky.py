#!/usr/bin/env python3
"""Testy cisteho modulu api/nabidka_pricky.py (bot8, 2026-10-07): typ boxu z AABB, sloty a geometrie pricek (uvnitr studny, bez kolize), sety pro celou skupinu (polici/suplik),
vyber a rozpis, verejny payload. Jen PRICNE pricky (Robert: podelne pricky a mrizky neexistuji); max pricek 4 / 6 / 8 podle delky boxu 288 / 395 / 500.
Spusteni: python3 test_pricky.py [cesta_k_api]   (bez DB, bez Flasku)"""
import json
import os
import re
import sys

API = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api")
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import nabidka_pricky as P  # noqa: E402

bad = 0
total = 0


def t(name, cond, detail=None):
    global bad, total
    total += 1
    if not cond:
        bad += 1
    print("[%s] %s%s" % ("OK   " if cond else "CHYBA", name, "" if cond or detail is None else " | %r" % (detail,)))


CENY = {"p186": {"id": 11, "cena": 39.0, "nazev": "P186", "aktivni": True}, "p91": {"id": 12, "cena": 29.0, "nazev": "P91", "aktivni": True}}


def aabb(L, W, osa=0, x=0.0, y=1000.0, z=0.0):
    if osa == 0:
        return [x, y, z], [x + L, y + P.MB_VYSKA, z + W]
    return [x, y, z], [x + W, y + P.MB_VYSKA, z + L]


# --- dily a SKU: dve karty multiboxu (186, 91) a pet karet supliku (hloubka x vyska)
t("dily: 2 multiboxove (186, 91) a 5 suplikovych (hloubka x vyska)", list(P.DILY) == ["p186", "p91", "ps332v137", "ps332v210", "ps384v101", "ps384v137", "ps384v210"], list(P.DILY))
t("SKU stabilni", P.SKU_NA_KLIC == {"MBX-PRICKA-PRICNA-186": "p186", "MBX-PRICKA-PRICNA-91": "p91", "SUP-PRICKA-PRICNA-332x137": "ps332v137", "SUP-PRICKA-PRICNA-332x210": "ps332v210",
                                    "SUP-PRICKA-PRICNA-384x101": "ps384v101", "SUP-PRICKA-PRICNA-384x137": "ps384v137", "SUP-PRICKA-PRICNA-384x210": "ps384v210"})

# --- tridy delek a sloty: 300 -> 4, 400 -> 6, 500 -> 8 (Robert 2026-10-07)
t("sloty podle delky: 288 -> 4, 395 -> 6, 500 -> 8", [P.max_pricek(k) for k in ("288x186", "395x186", "500x186")] == [4, 6, 8])
t("6 typu boxu (3 delky x 2 sirky)", sorted(P.TYPY) == ["288x186", "288x91", "395x186", "395x91", "500x186", "500x91"], sorted(P.TYPY))

# --- typ boxu z AABB
for k, (L, W, _) in P.TYPY.items():
    for osa in (0, 2):
        mn, mx = aabb(L, W, osa)
        t("typ_boxu %s osa %d" % (k, osa), P.typ_boxu(mn, mx) == k, P.typ_boxu(mn, mx))
t("typ_boxu: sirka 92 = typ 91", P.typ_boxu(*aabb(395.5, 92.0)) == "395x91")
t("typ_boxu: skutecne rozmery z modelu (395,4 x 185,9; 288,0 x 91,0)", P.typ_boxu(*aabb(395.4, 185.9)) == "395x186" and P.typ_boxu(*aabb(288.0, 91.0)) == "288x91")
t("typ_boxu: delka 496 mm patri do tridy 500", P.typ_boxu(*aabb(496.0, 186.0)) == "500x186")
t("typ_boxu: jina vyska = None", P.typ_boxu([0, 0, 0], [395.5, 60.0, 186.0]) is None)
t("typ_boxu: neznama delka = None", P.typ_boxu(*aabb(350.0, 186.0)) is None and P.typ_boxu(*aabb(600.0, 186.0)) is None)
t("typ_boxu: neznama sirka = None", P.typ_boxu(*aabb(395.5, 140.0)) is None)
t("typ_boxu: smeti = None", P.typ_boxu(None, None) is None and P.typ_boxu([0, 0], [1, 1]) is None)
t("osa_delky", P.osa_delky(*aabb(395.5, 186.0, 0)) == 0 and P.osa_delky(*aabb(395.5, 186.0, 2)) == 2)

# --- vyber slotu
for S in (4, 6, 8):
    for n in range(0, S + 1):
        v = P.vyber_slotu(S, n)
        t("vyber_slotu S=%d n=%d: %d ruznych slotu 1..S vzestupne" % (S, n, n), len(v) == n and v == sorted(set(v)) and all(1 <= j <= S for j in v), v)
    t("vyber_slotu S=%d: n = S = vsechny sloty" % S, P.vyber_slotu(S, S) == list(range(1, S + 1)))
ESL = {4: {0: [], 1: [3], 2: [2, 3], 3: [1, 3, 4], 4: [1, 2, 3, 4]}, 6: {0: [], 1: [4], 2: [2, 5], 3: [2, 4, 5], 4: [1, 3, 4, 6], 5: [1, 2, 4, 5, 6], 6: [1, 2, 3, 4, 5, 6]},
       8: {0: [], 1: [5], 2: [3, 6], 3: [2, 5, 7], 4: [2, 4, 5, 7], 5: [2, 3, 5, 6, 8], 6: [1, 3, 4, 5, 6, 8], 7: [1, 2, 3, 5, 6, 7, 8], 8: [1, 2, 3, 4, 5, 6, 7, 8]}}
t("vyber_slotu: pevna tabulka rozlozeni (symetricke tam, kde to jde)", all(P.vyber_slotu(S, n) == ESL[S][n] for S in ESL for n in ESL[S]), [(S, n, P.vyber_slotu(S, n)) for S in ESL for n in ESL[S] if P.vyber_slotu(S, n) != ESL[S][n]][:3])
t("vyber_slotu: n nad max se oreze", P.vyber_slotu(4, 9) == [1, 2, 3, 4] and P.vyber_slotu(4, -1) == [])

# --- sety = MIXY (Robert: "hotove varianty mix"): vzor hustoty podle poradi boxu ve skupine; uroven 1 = 1 pricka, 2 = polovina slotu (2 / 3 / 4), 3 = vsechny sloty (4 / 6 / 8)
t("sety: bez, mix1 .. mix4, pln (zadne uniformni zak / str)", P.SET_IDS == ("bez", "mix1", "mix2", "mix3", "mix4", "pln"), P.SET_IDS)
# nezavisla ocekavani (pevne tabulky) - skupiny stejne jako nize ve spec_boxy: s1 police 5 x 395x186 + 2 x 395x91 (6 slotu), s2 3 x 288x186 (4), s3 2 x 288x91 (4), s4 4 x 395x186 (6)
POC = {"s1": {"bez": [0] * 7, "mix1": [6, 1, 6, 1, 6, 1, 6], "mix2": [6, 3, 6, 3, 6, 3, 6], "mix3": [6, 6, 1, 6, 6, 1, 6], "mix4": [1, 1, 3, 3, 3, 6, 6], "pln": [6] * 7},
       "s2": {"bez": [0] * 3, "mix1": [4, 1, 4], "mix2": [4, 2, 4], "mix3": [4, 4, 1], "mix4": [1, 2, 4], "pln": [4] * 3},
       "s3": {"bez": [0, 0], "mix1": [4, 1], "mix2": [4, 2], "mix4": [1, 4], "pln": [4, 4]},                     # mix3 = pln (u 2 boxu) -> nenabizi se dvakrat
       "s4": {"bez": [0] * 4, "mix1": [6, 1, 6, 1], "mix2": [6, 3, 6, 3], "mix3": [6, 6, 1, 6], "mix4": [1, 3, 3, 6], "pln": [6] * 4}}
CENA_BOXU = {"s1": [39] * 5 + [29] * 2, "s2": [39] * 3, "s3": [29] * 2, "s4": [39] * 4}
t("pocty_setu: 8 boxu 395 mm", {x: P.pocty_setu(x, ["395x186"] * 8) for x in P.SET_IDS} == {"bez": [0] * 8, "mix1": [6, 1, 6, 1, 6, 1, 6, 1], "mix2": [6, 3, 6, 3, 6, 3, 6, 3],
  "mix3": [6, 6, 1, 6, 6, 1, 6, 6], "mix4": [1, 1, 3, 3, 3, 3, 6, 6], "pln": [6] * 8})
t("pocty_setu: boxy ruzne delky v jedne skupine (288 = 4 slotu, 395 = 6, 500 = 8): pln", P.pocty_setu("pln", ["288x91", "395x91", "500x186"]) == [4, 6, 8])
t("pocty_setu: uroven 2 = polovina slotu 2 / 3 / 4", P.pocty_setu("mix2", ["288x91", "395x91", "500x91"]) == [4, 3, 8] and P.pocty_setu("mix2", ["288x91", "395x91", "500x91", "288x91"]) == [4, 3, 8, 2])
t("pocty_setu: jediny box = vsude plny (mixy se shoduji s plnym setem)", all(P.pocty_setu(x, ["395x186"]) == [6] for x in P.SET_IDS if x != "bez"))
t("pocty_setu: vsechny sety nikdy nepresahnou pocet slotu a nejsou zaporne", all(0 <= n <= P.max_pricek(k) for x in P.SET_IDS for k in P.TYPY for n in P.pocty_setu(x, [k] * 9)))

# --- geometrie: kazda pricka uvnitr studny, na dne, pod okrajem, ve slotu; zadna se nepretina; vykroj zustava volny
for k in P.TYPY:
    x0, x1, z0, z1 = P.studna(k)
    S = P.max_pricek(k)
    pitch = (x1 - x0) / (S + 1)
    for pt in P.pocty_typu(k):
        sid, ds = "n=%d" % pt["n"], pt["desky"]
        for i, d in enumerate(ds):
            (sx, sy, sz), (rx, ry, rz) = d["s"], d["r"]
            ok = (x0 - 1e-6 <= sx - rx / 2 and sx + rx / 2 <= x1 + 1e-6 and z0 - 1e-6 <= sz - rz / 2 and sz + rz / 2 <= z1 + 1e-6
                  and abs((sy - ry / 2) - P.DNO) < 1e-6 and sy + ry / 2 <= P.MB_VYSKA - 1.0)
            t("%s/%s pricka %d uvnitr studny (stoji na dne, pod okrajem)" % (k, sid, i), ok, d)
            t("%s/%s pricka %d: vykroj (X < 28,4 mm od konce) zustava volny" % (k, sid, i), sx - rx / 2 >= 28.4 - 1e-6)
            t("%s/%s pricka %d je pricna: tloustka 2 mm v ose delky, pres celou sirku studny" % (k, sid, i), d["r"][0] == 2.0 and d["r"][1] == 75.0 and d["r"][2] > (z1 - z0) - 2.0)
            j = (sx - x0) / pitch
            t("%s/%s pricka %d lezi presne ve slotu (X = %.1f)" % (k, sid, i, sx), abs(j - round(j)) < 0.02 and 1 <= round(j) <= S, j)
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                a, b = ds[i], ds[j]
                prekryv = all(abs(a["s"][c] - b["s"][c]) < (a["r"][c] + b["r"][c]) / 2 - 1e-6 for c in range(3))
                t("%s/%s pricky %d a %d se neprotinaji" % (k, sid, i, j), not prekryv)
        t("%s/%s pocet pricek odpovida n" % (k, sid), len(ds) == pt["n"])
    L0 = {"288": 288.0, "395": 395.5, "500": 500.0}[k.split("x")[0]]
    t("%s: sloty lezi na pevnych polohach 28,4 + j x (L - 2 - 28,4) / (S + 1)" % k, [d["s"][0] for d in P.desky(k, S)] == [round(28.4 + (L0 - 2.0 - 28.4) * j / (S + 1), 1) for j in range(1, S + 1)],
      ([d["s"][0] for d in P.desky(k, S)], [round(28.4 + (L0 - 2.0 - 28.4) * j / (S + 1), 1) for j in range(1, S + 1)]))

# --- boxy a skupiny: police 395x186 x5 + 395x91 x2, vysuv 288x186 x3, samostatne 288x91 x2 (strana left)
def spec_boxy():
    mb, i = [], 0
    for (s, sk, k, pocet, g) in ((1, 1, "395x186", 5, "left"), (1, 1, "395x91", 2, "left"), (2, 2, "288x186", 3, "left"), (3, 3, "288x91", 2, "left"), (4, 2, "395x186", 4, "right")):
        for _ in range(pocet):
            i += 1
            L, W, _ = P.TYPY[k]
            mn, mx = aabb(L, W, 0, x=0, z=i * 200.0)
            mb.append({"id": "b%02d" % i, "min": mn, "max": mx, "e": 1, "p": "p%d" % i, "n": i, "s": s, "sk": sk, "g": g})
    return {"v": 1, "mbx": mb}


spec = spec_boxy()
boxy = P.boxy_ze_spec(spec)
t("boxy_ze_spec: vsech 16 boxu, skupina jako s<N>, druh jako klic", len(boxy) == 16 and boxy[0]["s"] == "s1" and boxy[0]["sk"] == "police" and boxy[14]["sk"] == "vysuv", boxy[0])
sks = P.skupiny_z_boxu(boxy, CENY)
t("4 skupiny podle cisla", [s["id"] for s in sks] == ["s1", "s2", "s3", "s4"], [s["id"] for s in sks])
t("popisy skupin", [s["popis"] for s in sks] == ["Police s multiboxy 1 · levá strana", "Výsuv s multiboxy 1 · levá strana", "Samostatné multiboxy · levá strana", "Výsuv s multiboxy 2 · levá strana"][:3] + [sks[3]["popis"]], [s["popis"] for s in sks])
t("pocty boxu ve skupinach", [s["boxu"] for s in sks] == [7, 3, 2, 4], [s["boxu"] for s in sks])
for sk_ in sks:
    sid_ = sk_["id"]
    if sid_ not in POC:
        continue
    t("%s: nabizene sety bez duplicit" % sid_, list(sk_["sety"]) == [x for x in P.SET_IDS if x in POC[sid_]], list(sk_["sety"]))
    t("%s: pocty pricek po boxech jednotlivych setu (nezavisla tabulka)" % sid_, all(sk_["sety"][x]["po_boxech"] == POC[sid_][x] for x in sk_["sety"]), {x: sk_["sety"][x]["po_boxech"] for x in sk_["sety"]})
    t("%s: priccek a cena setu = soucet po boxech (186 mm 39 Kc, 91 mm 29 Kc)" % sid_, all(sk_["sety"][x]["priccek"] == sum(POC[sid_][x]) and sk_["sety"][x]["cena"] == sum(n * c for n, c in zip(POC[sid_][x], CENA_BOXU[sid_])) for x in sk_["sety"]))
    t("%s: dily setu souhlasi s widths (p186 / p91)" % sid_, all(sk_["sety"][x]["dily"] == {k_: v_ for k_, v_ in (("p186", sum(n for n, c in zip(POC[sid_][x], CENA_BOXU[sid_]) if c == 39)), ("p91", sum(n for n, c in zip(POC[sid_][x], CENA_BOXU[sid_]) if c == 29))) if v_} for x in sk_["sety"]))
t("bez ceny z DB: orientacni ceny z DILY", P.skupiny_z_boxu(boxy, None)[0]["sety"]["mix1"]["cena"] == sum(n * c for n, c in zip(POC["s1"]["mix1"], CENA_BOXU["s1"])))
b0 = P.boxy_ze_spec({"mbx": [{"id": "b01", "min": [0, 0, 0], "max": [395.5, 81, 186], "e": 1}]})
t("spec bez s a sk: jedna skupina s0 druhu box", len(b0) == 1 and b0[0]["s"] == "s0" and b0[0]["sk"] == "box" and P.skupiny_z_boxu(b0)[0]["id"] == "s0" and P.skupiny_z_boxu(b0)[0]["popis"] == "Samostatné multiboxy")

# --- vyber PO BOXECH: {id boxu: pocet pricek 0..sloty}; sety jsou jen zkratka
BY = {b["id"]: b for b in boxy}
t("parse_vyber retezec", P.parse_vyber("b01:6, b02:2") == {"b01": 6, "b02": 2})
t("parse_vyber dict", P.parse_vyber({"b01": 6, "b02": 0}) == {"b01": 6, "b02": 0})
t("parse_vyber prazdne", P.parse_vyber("") == {} and P.parse_vyber(None) == {})
for spatny in ("b01", "b01:6:x", "s1:pln", "b01:x", "b01:", ":6", "b01:100", "b01:-1", "b01:6,b01:2", {"b01": "6"}, {"B01": 6}, {"b01": 6.0}, {"b01": True}, {"b01": -1}, {"b01": 100}, 5, ["b01:6"]):
    try:
        P.parse_vyber(spatny)
        t("parse_vyber odmitne %r" % (spatny,), False)
    except ValueError:
        t("parse_vyber odmitne %r" % (spatny,), True)
t("over_vyber: nuly se zahodi", P.over_vyber({"b01": 0, "b02": 3}, boxy) == {"b02": 3})
t("over_vyber: presne maximum slotu projde (395 mm = 6, 288 mm = 4)", P.over_vyber({"b01": 6, "b08": 4, "b11": 4}, boxy) == {"b01": 6, "b08": 4, "b11": 4})
for spatny in ({"b99": 1}, {"b01": 7}, {"b08": 5}, {"b16": 7}, {"b11": 5}):
    try:
        P.over_vyber(spatny, boxy)
        t("over_vyber odmitne %r" % (spatny,), False)
    except ValueError:
        t("over_vyber odmitne %r" % (spatny,), True)
t("vyber_retezec razeny podle cisla boxu, bez nul", P.vyber_retezec({"b10": 2, "b02": 6, "b01": 0, "b1": 1}) == "b1:1,b02:6,b10:2")
def ids_pocty(sid, pocty):
    return {b: n for b, n in zip(sks[int(sid[1:]) - 1]["boxy"], pocty) if n}


vs = P.vyber_ze_setu(boxy, sks, {"s1": "mix2", "s2": "pln", "s9": "pln", "s3": "mix3", "s4": "bez", "s5": "xx"})
t("vyber_ze_setu: mix2 ve s1, pln ve s2; neznama skupina, set, ktery skupina nenabizi (mix3 u 2 boxu) a 'bez' se preskoci", vs == {**ids_pocty("s1", POC["s1"]["mix2"]), **ids_pocty("s2", POC["s2"]["pln"])}, vs)
t("vyber_ze_setu: ruzne pocty v jedne skupine (mix4 u s1 = 1,1,3,3,3,6,6)", P.vyber_ze_setu(boxy, sks, {"s1": "mix4"}) == ids_pocty("s1", [1, 1, 3, 3, 3, 6, 6]))
# rozpoznani setu
t("rozpoznej_set: zadne pricky = bez", P.rozpoznej_set(sks[0], BY, {}) == "bez")
t("rozpoznej_set: kazdy nabizeny set se pozna (vsechny skupiny)", all(P.rozpoznej_set(sk_, BY, P.vyber_ze_setu(boxy, sks, {sk_["id"]: x})) == x for sk_ in sks for x in sk_["sety"] if x != "bez"))
v1 = P.vyber_ze_setu(boxy, sks, {"s1": "mix1"})
mixed = dict(v1)
mixed[sks[0]["boxy"][1]] = 2
t("rozpoznej_set: jeden box jinak = vlastni kombinace", P.rozpoznej_set(sks[0], BY, mixed) == "vlastni")
t("rozpoznej_set: jediny box s pricky = vlastni", P.rozpoznej_set(sks[0], BY, {sks[0]["boxy"][0]: 1}) == "vlastni")
t("rozpoznej_set: pocty z jine skupiny nevadi", P.rozpoznej_set(sks[1], BY, v1) == "bez")
t("rozpoznej_set: u 2 boxu je plny set pozname jako pln (mix3 se nenabizi)", P.rozpoznej_set(sks[2], BY, P.vyber_ze_setu(boxy, sks, {"s3": "pln"})) == "pln")

# spocti: s1 mix2 + s2 pln + 2 boxy ze s4 vlastni (3 a 5)
vyb = dict(P.vyber_ze_setu(boxy, sks, {"s1": "mix2", "s2": "pln"}))
vyb[sks[3]["boxy"][0]] = 3
vyb[sks[3]["boxy"][1]] = 5
r = P.spocti(boxy, sks, vyb, CENY)
n186 = sum(n for n, c in zip(POC["s1"]["mix2"], CENA_BOXU["s1"]) if c == 39) + 12 + 8          # s1 mix2: 6+3+6+3+6 = 24 v 186 boxech; s2 pln: 12; s4: 8
n91 = sum(n for n, c in zip(POC["s1"]["mix2"], CENA_BOXU["s1"]) if c == 29)                    # 3 + 6 = 9
t("spocti: agregace po dilech", {x["klic"]: x["qty"] for x in r["radky"]} == {"p186": n186, "p91": n91} and n186 == 44 and n91 == 9, r["radky"])
t("spocti: soucet", r["net"] == round(n186 * 39 + n91 * 29, 2), r["net"])
t("spocti: pocty (skupin, boxu, kusu)", r["skupin"] == 3 and r["boxu"] == 7 + 3 + 2 and r["kusu"] == 53, (r["skupin"], r["boxu"], r["kusu"]))
t("spocti: product_id a poradi", [x["product_id"] for x in r["radky"]] == [11, 12])
t("spocti: popis po skupinach: set / vlastni, pocty", [(p["id"], p["set"], p["boxu_s_pricky"], p["priccek"]) for p in r["popis"]] == [("s1", "mix2", 7, 33), ("s2", "pln", 3, 12), ("s4", "vlastni", 2, 8)], r["popis"])
t("spocti: rozpis (histogram poctu v boxech)", [p["rozpis"] for p in r["popis"]] == ["6× v 4 boxech, 3× v 3 boxech", "4× v 3 boxech", "5× v 1 boxu, 3× v 1 boxu"], [p["rozpis"] for p in r["popis"]])
t("spocti: souhlasi se souctem cen skupin", abs(r["net"] - sum(p["cena"] for p in r["popis"])) < 0.01)
t("spocti: po_boxech = pocty ve vsech boxech skupiny v poradi skupiny (vcetne nul)", [x["po_boxech"] for x in r["popis"]] == [POC["s1"]["mix2"], [4, 4, 4], [3, 5, 0, 0]], [x["po_boxech"] for x in r["popis"]])
t("spocti: nazev setu a vlastni kombinace", [p["set_popis"] for p in r["popis"]] == ["Mix 2", "Plný set", "Vlastní kombinace"], [p["set_popis"] for p in r["popis"]])
t("spocti: prazdny vyber", P.spocti(boxy, sks, {}, CENY) == {"radky": [], "net": 0.0, "skupin": 0, "boxu": 0, "kusu": 0, "popis": []})
t("spocti: ceny maji 2 desetinna", all(round(x["total"], 2) == x["total"] for x in r["radky"]))
r1 = P.spocti(boxy, sks, {sks[0]["boxy"][0]: 2}, CENY)
t("spocti: jediny box s 2 prickami: cena 78 (186 mm) a vlastni kombinace, 1 box z 7", r1["net"] == 78.0 and r1["popis"][0]["set"] == "vlastni" and r1["popis"][0]["boxu_s_pricky"] == 1 and r1["popis"][0]["boxu"] == 7, r1)

# --- payload
pl = P.payload(spec, CENY)
t("payload: zapnuto, sety, skupiny, typy, dily (jen pouzite)", pl and pl["enabled"] and not pl["nahled_admin"] and [s["id"] for s in pl["sety"]] == list(P.SET_IDS) and len(pl["skupiny"]) == 4
  and sorted(pl["typy"]) == ["288x186", "288x91", "395x186", "395x91"] and [d["klic"] for d in pl["dily"]] == ["p186", "p91"])
t("payload: typ nese max (a uz ne sety po typech)", pl["typy"]["395x186"]["max"] == 6 and pl["typy"]["288x91"]["max"] == 4 and all("sety" not in t_ for t_ in pl["typy"].values()))
t("payload: skupiny nesou sety s po_boxech (pro miniatury a plugin) bez duplicit", all(sk_["sety"][x]["po_boxech"] == POC[sk_["id"]][x] for sk_ in pl["skupiny"] for x in sk_["sety"] if sk_["id"] in POC) and "mix3" not in pl["skupiny"][2]["sety"], [list(s_["sety"]) for s_ in pl["skupiny"]])
t("payload: typ nese dil (186 -> p186, 91 -> p91) a pocty 0..max s deskami pro LIBOVOLNY pocet", pl["typy"]["395x186"]["dil"] == "p186" and pl["typy"]["395x91"]["dil"] == "p91"
  and [x["n"] for x in pl["typy"]["395x186"]["pocty"]] == list(range(7)) and [x["n"] for x in pl["typy"]["288x91"]["pocty"]] == list(range(5))
  and all(len(x["desky"]) == x["n"] for t_ in pl["typy"].values() for x in t_["pocty"]) and [d["s"][0] for d in pl["typy"]["395x186"]["pocty"][6]["desky"]] == [round(28.4 + (395.5 - 2.0 - 28.4) * j / 7, 1) for j in range(1, 7)])
t("payload: boxy maji skupinu", all(b["s"] in {s["id"] for s in pl["skupiny"]} for b in pl["boxy"]))
t("payload: je serializovatelny do JSON", bool(json.dumps(pl)))
CENY_NEAKT = {k: dict(v, aktivni=False) for k, v in CENY.items()}
t("payload: neaktivni karty = None (verejnost)", P.payload(spec, CENY_NEAKT) is None)
pa = P.payload(spec, CENY_NEAKT, nahled_admin=True)
t("payload: nahled admina pri neaktivnich kartach (vsechny 4 skupiny skryto)", pa is not None and pa["nahled_admin"] is True and len(pa["skupiny"]) == 4 and all(s_["skryto"] for s_ in pa["skupiny"]))
t("payload: admin pri aktivnich kartach = bez bannerem (skryto = False)", P.payload(spec, CENY, nahled_admin=True)["nahled_admin"] is False and not any(s_["skryto"] for s_ in P.payload(spec, CENY, nahled_admin=True)["skupiny"]))
t("payload: verejny pohled nema pole skryto = true", all(s_["skryto"] is False for s_ in pl["skupiny"]))
pc = P.payload(spec, {k: v for k, v in CENY.items() if k != "p91"})
t("payload: chybi cena dilu p91 = skupiny s boxy 91 mm se nenabizeji (zustanou s2 a s4 jen s 186 mm)", pc is not None and [s_["id"] for s_ in pc["skupiny"]] == ["s2", "s4"] and [d["klic"] for d in pc["dily"]] == ["p186"], pc and [s_["id"] for s_ in pc["skupiny"]])
t("payload: chybi obe ceny = None", P.payload(spec, {}) is None)
t("payload: bez boxu = None", P.payload({"v": 1}, CENY) is None)
t("payload: jen nezname boxy = None", P.payload({"mbx": [{"id": "b01", "min": [0, 0, 0], "max": [300, 81, 100], "e": 1}]}, CENY) is None)


# ======================================================================= v5: podnosy ocelovych supliku (Robert 2026-10-07: "v suplíku jsou sloty po 100 mm, smer jen zepredu dozadu"; jen ocelove s modrym celem)
# skutecne typy (zmereno na vsech Vandr modelech): klic -> (nejvyssi pocet pricek, dil)
REAL = {"S443x332x137": (4, "ps332v137"), "S443x332x210": (4, "ps332v210"), "S695x332x137": (6, "ps332v137"), "S443x384x137": (4, "ps384v137"), "S443x384x210": (4, "ps384v210"),
        "S695x384x137": (6, "ps384v137"), "S695x384x210": (6, "ps384v210"), "S950x384x101": (9, "ps384v101"), "S950x384x137": (9, "ps384v137"), "S950x384x210": (9, "ps384v210")}
t("suplik: 10 skutecnych typu podnosu je znamo, sloty 4 (443) / 6 (695) / 9 (950) a dil podle hloubky x vysky", all(k in P.TYPY_SUP and P.max_pricek(k) == m and P.dil_boxu(k) == d for k, (m, d) in REAL.items()), [k for k in REAL if k not in P.TYPY_SUP])
t("suplik: typy maji jen znamy tvar klice S<sirka>x<hloubka>x<vyska>", all(re.fullmatch(r"S(443|695|950)x(332|384)x(101|137|210)", k) for k in P.TYPY_SUP), list(P.TYPY_SUP))
t("suplik: dily maji nazev, SKU a rozmer pricky (tloustka 2, vyska = vyska podnosu - 8, delka 313 / 362)",
  {k: (d["rozmer"], d["sku"]) for k, d in P.DILY.items() if k.startswith("ps")} == {
      "ps332v137": ((2.0, 129.0, 313.0), "SUP-PRICKA-PRICNA-332x137"), "ps332v210": ((2.0, 202.0, 313.0), "SUP-PRICKA-PRICNA-332x210"), "ps384v101": ((2.0, 93.0, 362.0), "SUP-PRICKA-PRICNA-384x101"),
      "ps384v137": ((2.0, 129.0, 362.0), "SUP-PRICKA-PRICNA-384x137"), "ps384v210": ((2.0, 202.0, 362.0), "SUP-PRICKA-PRICNA-384x210")}, {k: d["rozmer"] for k, d in P.DILY.items() if k.startswith("ps")})
t("suplik: popis typu pro zakaznika", P.TYP_POPIS["S950x384x101"] == "Šuplík 950 × 384 mm, výška 101 mm" and P.TYP_POPIS["S443x332x137"] == "Šuplík 443 × 332 mm, výška 137 mm")
t("suplik: nazvy dilu pro zakaznika", P.DILY["ps384v101"]["nazev"] == "Příčka do ocelového šuplíku, hloubka 384 mm, výška 101 mm")


def aabb_sup(W, D, H, osa=0, x=100.0, y=500.0, z=-50.0):
    """podnos: sirka W (delsi), hloubka D (kratsi, zepredu dozadu), vyska H; osa 0 = hloubka podel X, osa 2 = hloubka podel Z"""
    if osa == 0:
        return [x, y, z], [x + D, y + H, z + W]
    return [x, y, z], [x + W, y + H, z + D]


for k in REAL:
    W_, D_, H_ = (float(v) for v in re.fullmatch(r"S(\d+)x(\d+)x(\d+)", k).groups())
    for osa in (0, 2):
        t("typ_boxu %s osa %d" % (k, osa), P.typ_boxu(*aabb_sup(W_, D_, H_, osa)) == k, P.typ_boxu(*aabb_sup(W_, D_, H_, osa)))
t("typ_boxu supliku: tolerance (949,5 x 383,3 x 100,8)", P.typ_boxu(*aabb_sup(949.5, 383.3, 100.8)) == "S950x384x101")
t("typ_boxu supliku: kombinace hloubka 332 x vyska 101 se nenabizi (dil neexistuje)", P.typ_boxu(*aabb_sup(443.0, 332.0, 101.0)) is None)
t("typ_boxu supliku: neznama vyska / hloubka / sirka = None", P.typ_boxu(*aabb_sup(950.0, 384.0, 120.0)) is None and P.typ_boxu(*aabb_sup(950.0, 350.0, 101.0)) is None and P.typ_boxu(*aabb_sup(700.0, 384.0, 101.0)) is None)
t("typ_boxu: multibox se dal pozna jako multibox (vyska 81) a podnos jako podnos", P.typ_boxu(*aabb(395.5, 186.0)) == "395x186" and P.typ_boxu(*aabb_sup(950.0, 384.0, 101.0)) == "S950x384x101")

# --- geometrie pricek v podnosu (nezavisle vzorce: dutina podnosu zmerena z podlahy, sloty po 100 mm souměrne kolem stredu sirky)
CELA_ZAD = {"332": (0.4, 17.8), "384": (0.5, 20.6)}
BOK = {"443": 12.5, "695": 11.4, "950": 11.7}
PODL = {"101": 1.0, "137": 1.4, "210": 2.1}
PRL = {"332": 313.0, "384": 362.0}
PRV = {"101": 93.0, "137": 129.0, "210": 202.0}
ESL9 = {0: [], 1: [5], 4: [2, 4, 6, 8], 9: [1, 2, 3, 4, 5, 6, 7, 8, 9]}
t("vyber_slotu S=9: pevne hodnoty pro 0, 1, 4 (kazdy druhy slot), 9", all(P.vyber_slotu(9, n) == v for n, v in ESL9.items()), [(n, P.vyber_slotu(9, n)) for n in ESL9 if P.vyber_slotu(9, n) != ESL9[n]])
t("vyber_slotu S=9: ostatni n = n ruznych slotu 1..9 vzestupne", all(len(P.vyber_slotu(9, n)) == n and P.vyber_slotu(9, n) == sorted(set(P.vyber_slotu(9, n))) and all(1 <= j <= 9 for j in P.vyber_slotu(9, n)) for n in range(10)))
for k, (maxn, dil) in REAL.items():
    Wk, Dk, Hk = re.fullmatch(r"S(\d+)x(\d+)x(\d+)", k).groups()
    W_, D_, H_ = float(Wk), float(Dk), float(Hk)
    cela, zad = CELA_ZAD[Dk]
    bok, podl = BOK[Wk], PODL[Hk]
    S = int((W_ - 2 * bok) // 100)
    t("%s: pocet slotu = floor((sirka - 2 x bok) / 100) = %d" % (k, S), P.max_pricek(k) == S == maxn, (P.max_pricek(k), S))
    t("%s: pocty 0..%d, kazdy pocet ma tolik desek" % (k, S), [x["n"] for x in P.pocty_typu(k)] == list(range(S + 1)) and all(len(x["desky"]) == x["n"] for x in P.pocty_typu(k)))
    plne = P.desky(k, S)
    t("%s: vsechny sloty = po 100 mm souměrně kolem stredu sirky (%.1f ... %.1f)" % (k, W_ / 2 - (S - 1) * 50, W_ / 2 + (S - 1) * 50), [d["s"][0] for d in plne] == [round(W_ / 2 + (j - (S + 1) / 2.0) * 100.0, 1) for j in range(1, S + 1)], [d["s"][0] for d in plne])
    for n in range(S + 1):
        ds = P.desky(k, n)
        for i, d in enumerate(ds):
            (sx, sy, sz), (rx, ry, rz) = d["s"], d["r"]
            t("%s/n=%d pricka %d: uvnitr dutiny (od boku, od cela a zadniho lemu, na podlaze, pod okrajem)" % (k, n, i),
              sx - rx / 2 >= bok - 0.06 and sx + rx / 2 <= W_ - bok + 0.06 and sz - rz / 2 >= cela - 0.06 and sz + rz / 2 <= D_ - zad + 0.06
              and abs((sy - ry / 2) - podl) < 0.06 and sy + ry / 2 <= H_ - 5.0, d)
            t("%s/n=%d pricka %d: rozmer 2 x %g x %g mm, dil %s, jde zepredu dozadu (dlouha v ose z)" % (k, n, i, PRV[Hk], PRL[Dk], dil), d["r"] == [2.0, PRV[Hk], PRL[Dk]] and d["d"] == dil and d["r"][2] > 300.0)
            j = (sx - (W_ / 2 - (S + 1) / 2.0 * 100.0)) / 100.0
            t("%s/n=%d pricka %d lezi presne ve slotu %d (x = %.1f)" % (k, n, i, round(j), sx), abs(j - round(j)) < 0.001 and 1 <= round(j) <= S, j)
        t("%s/n=%d: jde o sloty %s" % (k, n, P.vyber_slotu(S, n)), [round((d["s"][0] - (W_ / 2 - (S + 1) / 2.0 * 100.0)) / 100.0) for d in ds] == P.vyber_slotu(S, n))
        for i in range(len(ds)):
            for j2 in range(i + 1, len(ds)):
                a, b = ds[i], ds[j2]
                t("%s/n=%d pricky %d a %d se neprotinaji" % (k, n, i, j2), not all(abs(a["s"][c] - b["s"][c]) < (a["r"][c] + b["r"][c]) / 2 - 1e-6 for c in range(3)))
    z0 = round(cela + (D_ - cela - zad) / 2.0, 1)
    t("%s: stred pricky pres hloubku = stred dutiny %.1f od cela, vyska stredu %.1f" % (k, z0, round(podl + PRV[Hk] / 2, 1)), all(d["s"][1] == round(podl + PRV[Hk] / 2, 1) and d["s"][2] == z0 for d in plne), plne[0])

# --- skupiny supliku: sloupec 4 podnosu 950 x 384 x 101 (sk 4), sety = MIXY podle poradi podnosu; sloupec 6 podnosu 443 / 695 stridave (jako dve rady u 2suplikyocel)
def spec_sup():
    mb, i = [], 0
    def pridej(typ, s, osa=0):
        nonlocal i
        i += 1
        W_, D_, H_ = (float(v) for v in re.fullmatch(r"S(\d+)x(\d+)x(\d+)", typ).groups())
        mn, mx = aabb_sup(W_, D_, H_, osa, y=3000.0 - i * 150.0, z=i * 10.0)
        mb.append({"id": "b%02d" % i, "min": mn, "max": mx, "e": 1, "p": "p%d" % i, "n": i, "s": s, "sk": 4})
    for _ in range(4):
        pridej("S950x384x101", 1)
    for typ in ("S443x384x137", "S695x384x137") * 3:
        pridej(typ, 2)
    pridej("S950x384x101", 3)                                   # jediny podnos ve skupine
    for typ in ("S950x384x101", "S950x384x101"):
        pridej(typ, 4, osa=2)                                   # dva podnosy, hloubka podel Z
    return {"v": 1, "mbx": mb}


CENY5 = dict(CENY, ps384v101={"id": 21, "cena": 59.0, "nazev": "S101", "aktivni": True}, ps384v137={"id": 22, "cena": 69.0, "nazev": "S137", "aktivni": True})
spec_s = spec_sup()
boxy_s = P.boxy_ze_spec(spec_s)
t("boxy_ze_spec: 13 podnosu, druh suplik, typ podle rozmeru (obe osy hloubky)", len(boxy_s) == 13 and all(b["sk"] == "suplik" for b in boxy_s)
  and [b["k"] for b in boxy_s] == ["S950x384x101"] * 4 + ["S443x384x137", "S695x384x137"] * 3 + ["S950x384x101"] * 3, [b["k"] for b in boxy_s])
sks_s = P.skupiny_z_boxu(boxy_s, CENY5)
t("suplik: 4 skupiny, popisy 'Suplíky N', pocty podnosu", [s_["id"] for s_ in sks_s] == ["s1", "s2", "s3", "s4"] and [s_["popis"] for s_ in sks_s] == ["Šuplíky 1", "Šuplíky 2", "Šuplíky 3", "Šuplíky 4"]
  and [s_["boxu"] for s_ in sks_s] == [4, 6, 1, 2] and all(s_["k"] == "suplik" for s_ in sks_s), [(s_["id"], s_["popis"], s_["boxu"]) for s_ in sks_s])
POC_S = {"s1": {"bez": [0] * 4, "mix1": [9, 1, 9, 1], "mix2": [9, 4, 9, 4], "mix3": [9, 9, 1, 9], "mix4": [1, 4, 4, 9], "pln": [9] * 4},
         "s2": {"bez": [0] * 6, "mix1": [4, 1, 4, 1, 4, 1], "mix2": [4, 3, 4, 3, 4, 3], "mix3": [4, 6, 1, 6, 4, 1], "mix4": [1, 1, 2, 3, 4, 6], "pln": [4, 6, 4, 6, 4, 6]},
         "s3": {"bez": [0], "pln": [9]},                                                  # jediny podnos: vsechny mixy = pln -> nabizi se jen bez a pln
         "s4": {"bez": [0, 0], "mix1": [9, 1], "mix2": [9, 4], "mix4": [1, 9], "pln": [9, 9]}}       # mix3 = pln (u 2 podnosu)
CENA_S = {"s1": [59.0] * 4, "s2": [69.0] * 6, "s3": [59.0], "s4": [59.0] * 2}
for sk_ in sks_s:
    sid_ = sk_["id"]
    t("suplik %s: nabizene sety bez duplicit" % sid_, list(sk_["sety"]) == [x for x in P.SET_IDS if x in POC_S[sid_]], list(sk_["sety"]))
    t("suplik %s: pocty pricek po podnosech (nezavisla tabulka: 1 / polovina slotu / vsechny sloty)" % sid_, all(sk_["sety"][x]["po_boxech"] == POC_S[sid_][x] for x in sk_["sety"]), {x: sk_["sety"][x]["po_boxech"] for x in sk_["sety"]})
    t("suplik %s: priccek a cena setu = soucet po podnosech" % sid_, all(sk_["sety"][x]["priccek"] == sum(POC_S[sid_][x]) and sk_["sety"][x]["cena"] == sum(n * c for n, c in zip(POC_S[sid_][x], CENA_S[sid_])) for x in sk_["sety"]))
t("suplik s1: cena mixu 1 = 20 pricek x 59 = 1180, plny set 36 x 59 = 2124; s2: mix1 = 15 x 69 = 1035", sks_s[0]["sety"]["mix1"]["cena"] == 1180.0 and sks_s[0]["sety"]["pln"]["cena"] == 2124.0 and sks_s[1]["sety"]["mix1"]["cena"] == 1035.0)
t("suplik: dily setu (s1 jen ps384v101, s2 jen ps384v137)", sks_s[0]["sety"]["mix1"]["dily"] == {"ps384v101": 20} and sks_s[1]["sety"]["pln"]["dily"] == {"ps384v137": 30})
t("suplik: vyber_ze_setu + rozpoznej_set funguji i pro podnosy", P.rozpoznej_set(sks_s[0], {b["id"]: b for b in boxy_s}, P.vyber_ze_setu(boxy_s, sks_s, {"s1": "mix3"})) == "mix3")
vyb_s = {"b01": 9, "b02": 4, "b05": 4, "b06": 1}
t("over_vyber supliku: presne maximum slotu projde (950 -> 9, 443 -> 4, 695 -> 6)", P.over_vyber({"b01": 9, "b05": 4, "b06": 6}, boxy_s) == {"b01": 9, "b05": 4, "b06": 6})
for spatny in ({"b01": 10}, {"b05": 5}, {"b06": 7}):
    try:
        P.over_vyber(spatny, boxy_s)
        t("over_vyber supliku odmitne %r" % (spatny,), False)
    except ValueError:
        t("over_vyber supliku odmitne %r" % (spatny,), True)
rs = P.spocti(boxy_s, sks_s, vyb_s, CENY5)
t("spocti supliku: radky po dilech (ps384v101: 9 + 4 = 13 x 59; ps384v137: 4 + 1 = 5 x 69)", {x["klic"]: (x["qty"], x["unit_price"]) for x in rs["radky"]} == {"ps384v101": (13, 59.0), "ps384v137": (5, 69.0)}
  and [x["klic"] for x in rs["radky"]] == ["ps384v101", "ps384v137"] and rs["net"] == 13 * 59.0 + 5 * 69.0, rs["radky"])
t("spocti supliku: slova podle druhu (suplik / suplicich), jednotka a oznaceni", [(p["rozpis"], p["jednotka"], p["jednotkaL"], p["oznaceni"]) for p in rs["popis"]] == [("9× v 1 šuplíku, 4× v 1 šuplíku", "šuplíků", "šuplících", "Šuplík"), ("4× v 1 šuplíku, 1× v 1 šuplíku", "šuplíků", "šuplících", "Šuplík")], [p["rozpis"] for p in rs["popis"]])
t("spocti supliku: jeden pocet ve vice podnosech = mnozne cislo 'v 2 suplicich'", P.spocti(boxy_s, sks_s, {"b01": 4, "b02": 4}, CENY5)["popis"][0]["rozpis"] == "4× v 2 šuplících")
t("spocti multiboxu: slova beze zmeny (boxu / boxech, Multibox)", [(p["rozpis"], p["jednotka"], p["jednotkaL"], p["oznaceni"]) for p in P.spocti(boxy, sks, {"b01": 6}, CENY)["popis"]] == [("6× v 1 boxu", "boxů", "boxech", "Multibox")])

# --- smisena nabidka: multibox + podnosy, gating po skupinach (karta dilu s cenou a aktivni)
def spec_mix():
    mb = []
    for i in range(2):
        mn, mx = aabb(395.5, 186.0, 0, x=0, z=i * 200.0)
        mb.append({"id": "b%02d" % (i + 1), "min": mn, "max": mx, "e": 1, "p": "p%d" % (i + 1), "n": i + 1, "s": 1, "sk": 1})
    for i in range(2):
        mn, mx = aabb_sup(950.0, 384.0, 101.0, 0, y=2000.0 - i * 150.0, z=1000.0)
        mb.append({"id": "b%02d" % (i + 3), "min": mn, "max": mx, "e": 1, "p": "p%d" % (i + 3), "n": i + 3, "s": 2, "sk": 4})
    mn, mx = aabb_sup(443.0, 332.0, 137.0, 2, y=500.0, z=3000.0)
    mb.append({"id": "b05", "min": mn, "max": mx, "e": -1, "p": "p5", "n": 5, "s": 3, "sk": 4})
    return {"v": 1, "mbx": mb}


spec_m = spec_mix()
bm = P.boxy_ze_spec(spec_m)
def cm(**zmeny):
    c = {"p186": {"id": 11, "cena": 39.0, "nazev": "P186", "aktivni": True}, "p91": {"id": 12, "cena": 29.0, "nazev": "P91", "aktivni": True},
         "ps384v101": {"id": 21, "cena": 59.0, "nazev": "S101", "aktivni": True}, "ps332v137": {"id": 23, "cena": 59.0, "nazev": "S332", "aktivni": False}}
    for k, v in zmeny.items():
        if v is None:
            c.pop(k, None)
        else:
            c[k] = dict(c[k], **v)
    return c


t("dostupne_boxy: verejnost = jen skupiny, jejichz dily maji aktivni kartu (s3 ma neaktivni ps332v137)", [b["id"] for b in P.dostupne_boxy(bm, cm())] == ["b01", "b02", "b03", "b04"], [b["id"] for b in P.dostupne_boxy(bm, cm())])
t("dostupne_boxy: admin vidi i skupiny s neaktivni kartou, ktera ma cenu", [b["id"] for b in P.dostupne_boxy(bm, cm(), True)] == ["b01", "b02", "b03", "b04", "b05"])
t("dostupne_boxy: skupina bez ceny dilu se nenabizi ani adminovi", [b["id"] for b in P.dostupne_boxy(bm, cm(ps332v137={"cena": None}), True)] == ["b01", "b02", "b03", "b04"] and [b["id"] for b in P.dostupne_boxy(bm, cm(ps384v101=None), True)] == ["b01", "b02", "b05"])
t("dostupne_boxy: skupiny jsou nezavisle (multibox karty neaktivni -> verejnost vidi jen supliky)", [b["id"] for b in P.dostupne_boxy(bm, cm(p186={"aktivni": False}))] == ["b03", "b04"])
t("dostupne_boxy: poradi boxu zustava (jako ve spec)", [b["id"] for b in P.dostupne_boxy(bm, cm(), True)] == [b["id"] for b in bm])
pv = P.payload(spec_m, cm())
t("payload: verejnost - skupiny s1 (police) a s2 (suplik), dily jen p186 a ps384v101, bez banneru", [s_["id"] for s_ in pv["skupiny"]] == ["s1", "s2"] and [d["klic"] for d in pv["dily"]] == ["p186", "ps384v101"] and pv["nahled_admin"] is False
  and not any(s_["skryto"] for s_ in pv["skupiny"]) and sorted(pv["typy"]) == ["395x186", "S950x384x101"] and [b["id"] for b in pv["boxy"]] == ["b01", "b02", "b03", "b04"], pv and [s_["id"] for s_ in pv["skupiny"]])
pad = P.payload(spec_m, cm(), nahled_admin=True)
t("payload: admin - vsechny 3 skupiny, s3 skryto = true a banner, dily vcetne ps332v137", [s_["id"] for s_ in pad["skupiny"]] == ["s1", "s2", "s3"] and [s_["skryto"] for s_ in pad["skupiny"]] == [False, False, True] and pad["nahled_admin"] is True
  and [d["klic"] for d in pad["dily"]] == ["p186", "ps332v137", "ps384v101"] and sorted(pad["typy"]) == ["395x186", "S443x332x137", "S950x384x101"], [d["klic"] for d in pad["dily"]])
t("payload: typ nese druh / os / L / W / H / lem (multibox: box, a, 395,5 x 186 x 81, lem 28,4; podnos: suplik, b, 950 x 384 x 101, lem 0)",
  {k_: {x: v_[x] for x in ("druh", "os", "L", "W", "H", "lem")} for k_, v_ in pad["typy"].items()} == {
      "395x186": {"druh": "box", "os": "a", "L": 395.5, "W": 186.0, "H": 81.0, "lem": 28.4}, "S443x332x137": {"druh": "suplik", "os": "b", "L": 443.0, "W": 332.0, "H": 137.0, "lem": 0.0},
      "S950x384x101": {"druh": "suplik", "os": "b", "L": 950.0, "W": 384.0, "H": 101.0, "lem": 0.0}}, pad["typy"]["S950x384x101"])
t("payload: typ supliku nese max a pocty 0..max s deskami (4 / 6 / 9)", pad["typy"]["S950x384x101"]["max"] == 9 and [x["n"] for x in pad["typy"]["S950x384x101"]["pocty"]] == list(range(10)) and pad["typy"]["S443x332x137"]["max"] == 4
  and len(pad["typy"]["S950x384x101"]["pocty"][9]["desky"]) == 9 and pad["typy"]["S950x384x101"]["dil"] == "ps384v101")
t("payload se supliky je serializovatelny do JSON", bool(json.dumps(pad)))
t("payload: jen podnosy s neznamym typem = None", P.payload({"mbx": [{"id": "b01", "min": [0, 0, 0], "max": [384, 101, 700], "e": 1}]}, cm()) is None)
t("druh podle typu: podnos se sk = 1 je suplik, multibox se sk = 4 je box", [b["sk"] for b in P.boxy_ze_spec({"mbx": [dict(spec_m["mbx"][2], sk=1), dict(spec_m["mbx"][0], sk=4, id="b09")]})] == ["suplik", "box"])

# --- ceny z karet (kurzor atrapa)
class Cur:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params

    def fetchall(self):
        return self.rows


rows = [{"id": 1, "sku": "MBX-PRICKA-PRICNA-186", "name": "A", "price_czk_placeholder": "39.00", "active": 1, "is_archived": 0},
        {"id": 2, "sku": "MBX-PRICKA-PRICNA-91", "name": "B", "price_czk_placeholder": None, "active": 1, "is_archived": 0},
        {"id": 4, "sku": "JINE", "name": "D", "price_czk_placeholder": "1", "active": 1, "is_archived": 0}]
c = P.nacti_ceny(Cur(rows))
t("nacti_ceny: podle SKU, cizi sku ignoruje", set(c) == {"p186", "p91"}, set(c))
t("nacti_ceny: cena a aktivni", c["p186"]["cena"] == 39.0 and c["p186"]["aktivni"] and c["p91"]["cena"] is None)
t("ceny_pouzitelne: chybi cena", not P.ceny_pouzitelne(c))
rows2 = [dict(rows[0]), dict(rows[1], price_czk_placeholder="29", active=0)]
c2 = P.nacti_ceny(Cur(rows2))
MB = ("p186", "p91")
t("vsechny_aktivni: neaktivni karta (pro dily multiboxu)", P.ceny_pouzitelne(c2, MB) and not P.vsechny_aktivni(c2, MB) and P.vsechny_aktivni(CENY, MB))
t("vsechny_aktivni bez seznamu dilu = vsech 7 dilu (chybi karty supliku)", not P.ceny_pouzitelne(c2) and not P.vsechny_aktivni(CENY))
rows3 = [dict(rows[0]), dict(rows[1], price_czk_placeholder="29", is_archived=1)]
t("archivovana karta neni aktivni (a stejna neinvolvovana karta aktivni je)", not P.vsechny_aktivni(P.nacti_ceny(Cur(rows3)), MB) and P.vsechny_aktivni(P.nacti_ceny(Cur([dict(rows[0]), dict(rows[1], price_czk_placeholder="29")])), MB))
rows4 = [dict(rows[0]), dict(rows[1], price_czk_placeholder="29"), {"id": 5, "sku": "SUP-PRICKA-PRICNA-384x101", "name": "S", "price_czk_placeholder": "59.00", "active": 1, "is_archived": 0}]
c4 = P.nacti_ceny(Cur(rows4))
t("nacti_ceny: i karty supliku podle SKU (ps384v101) a dotaz na vsechny SKU", set(c4) == {"p186", "p91", "ps384v101"} and c4["ps384v101"]["cena"] == 59.0)
cur4 = Cur(rows4)
P.nacti_ceny(cur4)
t("nacti_ceny: dotaz ma 7 SKU (2 multibox + 5 suplik)", len(cur4.params) == 7 and "SUP-PRICKA-PRICNA-332x137" in cur4.params and "MBX-PRICKA-PRICNA-91" in cur4.params, cur4.params)

print("\n%d/%d OK" % (total - bad, total))
sys.exit(1 if bad else 0)
