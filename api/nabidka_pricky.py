# -*- coding: utf-8 -*-
"""Pricky do Multiboxu v online nabidce (bot8, 2026-10-07; Robert: "multiboxy maji moznost delicich pricek, navrhni zjednodusene tvary a v online nabidce pro multiboxy
nejaky system pro priobjednani pricek jako prislusenstvi, v nejakych par variantach i vizualne primo v multiboxech, at jsou videt ceny aby si uzivatel vybral";
"jde o to nabidnout vzdy nejake varianty SETU, vzdy pro CELOU POLICI / SUPLIK s multiboxy").

JEDNO MISTO PRAVDY pro tvar pricek, sety, ceny a vypocet vyberu - stejny kod pouziva verejny JSON nabidky, QR platba, objednavka, test i nahled.
Cista logika: bez Flasku a bez DB (DB cte jen nacti_ceny(cur) z predaneho kurzoru); geometrii pricek pocita SERVER a viewer ji jen vykresli (zadna duplicita).

Co se nabizi: pro kazdou SKUPINU (police / suplik / samostatne boxy; = jedna instance komponenty ve Vandr modelu) hotove SETY, ktere se pouziji na VSECHNY multiboxy skupiny naraz:
  bez = Bez pricek · mix1 .. mix4 = ctyri MIXY (v jedne polici ruzne pocty pricek v ruznych boxech, napr. strídave husté a rídke) · pln = Plny set (vsechny sloty ve vsech boxech).
  Mix = VZOR hustoty podle poradi boxu ve skupine (uroven 1 = 1 pricka, 2 = polovina slotu, 3 = vsechny sloty; pocet pricek z poctu slotu boxu 4 / 6 / 8).
  Robert 2026-10-07: "nemyslim kazdy zvlast, ale chci hotove varianty mix, v jedne polici napr. 4 moznosti ruznych kombinaci"; "je zdlouhave klikat kazdy box zvlast".
VYBER se na server prenasi PO BOXECH: {id boxu: pocet pricek 0..sloty} (set je jen zkratka, ktera nastavi pocty ve vsech boxech skupiny; server ho nezna, zna jen pocty a plati je presne);
skupina, jejiz boxy se shoduji s nejakym setem, se pozna jako ten set, jinak je to "vlastni kombinace".
Pocet slotu (= nejvetsi mozny pocet pricek v boxu) podle delky boxu (Robert 2026-10-07): "300" (= nase 288 mm) 4 ks, "400" (= nase 395,5 mm) 6 ks, "500" (zatim se nepouziva) 8 ks.
POZOR (Robert 2026-10-07: "toto neexistuje"): podelne pricky ani mrizky NEEXISTUJI - Multibox ma jen PRICNE pricky (kolme na delku boxu).

Spec v3d (scenes[0].extras.v3d.mbx, viz docs/KONTRAKT_NABIDKA_PRICKY.md): [{id: "b01", min: [x,y,z], max: [x,y,z], e: +1|-1, p: "p22"|null, g?, n?, s?, sk?}] = poloha kazdeho
Multiboxu v zavrenem stavu (svetovy AABB, glTF mm, Y nahoru). Delsi vodorovny rozmer = delka boxu (osa a), e = +1: konec s vykrojem je na MIN strane delky, e = -1: na MAX strane.
s = cislo skupiny (police / suplik), sk = druh skupiny jako cislo (1 police, 2 vysuv = suplik, 3 samostatne boxy; jmena komponent do GLB nesmi).

Tvar Multiboxu (zjednoduseny Vandr model, vlastni mereni 2026-10-07): 395,5 | 288 x 186 | 91 x 81 mm, steny a dno 2 mm; na jednom konci (X = 0..28,4) je lem a spodek konce je vykrojeny
do vysky ~33 mm (za vykroj se box da zavesit sikmo za podelnik nad nim, Robert 2026-10-07). Pricky se vkladaji jen do "studny" boxu za lemem, do rovnomerne rozlozenych slotu.
Osy MISTNIHO systemu boxu (jednotky mm): X = delka od konce s vykrojem, Y = vyska od spodku boxu, Z = sirka.

v5 (2026-10-07; Robert: "potom i pricky v suplíku, v suplíku jsou sloty po 100 mm, smer jen zepredu dozadu"; "pro deleni prickou se jedna pouze o typy suplíku s modrym celem ocelove"):
druhy "box" je i PODNOS OCELOVEHO SUPLIKU (komponenty Suplikocel* / 2suplikyocel* ve Vandr modelech, skupina = instance komponenty, sk = 4). Klic typu "S<sirka>x<hloubka>x<vyska>"
(napr. "S950x384x101"), sloty po 100 mm napric sirkou (4 / 6 / 9 podle sirky 443 / 695 / 950), pricky jdou zepredu dozadu; geometrie a dily viz SUP_* a docs/KONTRAKT_NABIDKA_PRICKY.md.
Skupina se nabizi verejnosti, kdyz maji VSECHNY jeji dily kartu s cenou a aktivni kartu (dostupne_boxy); jinak ji vidi jen admin (skryto).
"""
import math
import re

# ------------------------------------------------------------------ tvar boxu
MB_VYSKA = 81.0
STENA = 2.0
DNO = 2.0
STUDNA_OD = 28.4                              # konec lemu / vykroje: odtud je plna studna boxu
TYP_TOL = 3.0                                 # tolerance rozmeru pri urceni typu z AABB (92 mm kusy = typ 91)
# tridy delek: (klic, od, do, nominalni delka mm, pocet slotu = nejvetsi pocet pricek); 500 zatim neexistuje (delka je predpoklad, upravit az bude skutecny model)
TRIDY_DELKY = (("288", 270.0, 310.0, 288.0, 4), ("395", 380.0, 410.0, 395.5, 6), ("500", 480.0, 520.0, 500.0, 8))
TRIDY_SIRKY = (("186", 183.0, 189.0, 186.0), ("91", 88.0, 95.0, 91.0))
# typ -> (delka, sirka, sloty); klic = "<trida delky>x<trida sirky>"
TYPY = {"%sx%s" % (d[0], w[0]): (d[3], w[3], d[4]) for d in TRIDY_DELKY for w in TRIDY_SIRKY}
TYP_POPIS = {k: "Multibox %s × %s mm" % (k.split("x")[0], k.split("x")[1]) for k in TYPY}

# ------------------------------------------------------------------ pricka
PRICKA_T = 2.0                                # tloustka
PRICKA_V = 75.0                               # vyska (dno 2 mm + 75 = 77, okraj boxu 79-81 mm)

# klic dilu -> {sku (stabilni, karty se hledaji podle SKU), nazev, rozmer (X, Y, Z v systemu pricky: tloustka, vyska, delka), orientacni cena Kc bez DPH (jen pri zalozeni karty)}
DILY = {
    "p186": {"sku": "MBX-PRICKA-PRICNA-186", "nazev": "Příčka do Multiboxu šířky 186 mm", "rozmer": (PRICKA_T, PRICKA_V, 181.0), "cena0": 39.0},
    "p91": {"sku": "MBX-PRICKA-PRICNA-91", "nazev": "Příčka do Multiboxu šířky 91 mm", "rozmer": (PRICKA_T, PRICKA_V, 86.0), "cena0": 29.0},
}

# ------------------------------------------------------------------ ocelove suplikove podnosy (v5)
# Podnos = mesh "Default" pod komponentou Suplikocel* / 2suplikyocel* (Vandr export). AABB zavreneho stavu: vyska 101 | 137 | 210, hloubka (zepredu dozadu) 332 | 384, sirka 443 | 695 | 950 mm.
# Dutina podnosu (zmereno z podlahy na vsech 10 typech ve vsech Vandr modelech): mezera od cela 0,4 | 0,5 mm, od zadniho lemu 17,8 | 20,6 mm, od boku 12,5 | 11,4 | 11,7 mm; podlaha ve vysce 1,0 | 1,4 | 2,1 mm.
SUP_HLOUBKY = (("332", 330.0, 335.0, 332.0, 0.4, 17.8), ("384", 382.0, 386.0, 384.0, 0.5, 20.6))                   # klic, od, do, nominalni hloubka, mezera u cela, mezera vzadu (lem)
SUP_SIRKY = (("443", 441.0, 445.0, 443.0, 12.5), ("695", 693.0, 697.0, 695.0, 11.4), ("950", 948.0, 952.0, 950.0, 11.7))   # klic, od, do, nominalni sirka, mezera u boku
SUP_VYSKY = (("101", 99.5, 102.5, 101.0, 1.0), ("137", 135.5, 138.5, 137.0, 1.4), ("210", 208.5, 211.5, 210.0, 2.1))       # klic, od, do, nominalni vyska, vyska podlahy
SUP_KOMBINACE = (("332", "137"), ("332", "210"), ("384", "101"), ("384", "137"), ("384", "210"))                    # (hloubka, vyska), pro ktere existuje dil (karta); jina kombinace se nenabizi
SUP_ROZTEC = 100.0                                                                                                   # sloty po 100 mm napric sirkou podnosu
SUP_PRICKA_T = 2.0                                                                                                   # tloustka pricky
SUP_PRICKA_MINUS = 8.0                                                                                               # vyska pricky = vyska podnosu - 8 mm (stoji na podlaze, kousek pod okrajem)
SUP_CENA0 = {("332", "137"): 59.0, ("332", "210"): 79.0, ("384", "101"): 59.0, ("384", "137"): 69.0, ("384", "210"): 89.0}   # orientacni cena Kc bez DPH (jen pri zalozeni karty)


def _sup_dil(hloubka, vyska):
    return "ps%sv%s" % (hloubka, vyska)


# typ -> parametry; klic "S<sirka>x<hloubka>x<vyska>" (sirka = delsi vodorovna strana, hloubka = kratsi = zepredu dozadu)
TYPY_SUP = {}
for _h in SUP_HLOUBKY:
    for _s in SUP_SIRKY:
        for _v in SUP_VYSKY:
            if (_h[0], _v[0]) not in SUP_KOMBINACE:
                continue
            TYPY_SUP["S%sx%sx%s" % (_s[0], _h[0], _v[0])] = {
                "L": _s[3], "W": _h[3], "H": _v[3], "cela": _h[4], "zad": _h[5], "bok": _s[4], "podlaha": _v[4],
                "sloty": int((_s[3] - 2 * _s[4]) // SUP_ROZTEC), "dil": _sup_dil(_h[0], _v[0]),
                "pricka_v": _v[3] - SUP_PRICKA_MINUS, "pricka_l": float(int(_h[3] - _h[4] - _h[5])),
            }
for _hv in SUP_KOMBINACE:
    _t = next(t for t in TYPY_SUP.values() if t["dil"] == _sup_dil(*_hv))
    DILY[_t["dil"]] = {"sku": "SUP-PRICKA-PRICNA-%sx%s" % _hv, "nazev": "Příčka do ocelového šuplíku, hloubka %s mm, výška %s mm" % _hv,
                       "rozmer": (SUP_PRICKA_T, _t["pricka_v"], _t["pricka_l"]), "cena0": SUP_CENA0[_hv]}
TYP_POPIS.update({k: "Šuplík %d × %d mm, výška %d mm" % (t["L"], t["W"], t["H"]) for k, t in TYPY_SUP.items()})
SKU_NA_KLIC = {d["sku"]: k for k, d in DILY.items()}

# sety pro celou skupinu: (id, popis, poznamka); pocty pricek v boxech urcuje VZOR (VZORY) podle poradi boxu ve skupine (index i z N) a UROVEN hustoty -> pocet z poctu slotu boxu m
SETY = (
    ("bez", "Bez příček", ""),
    ("mix1", "Mix 1", "střídavě husté a řídké dělení"),
    ("mix2", "Mix 2", "střídavě husté a středně husté dělení"),
    ("mix3", "Mix 3", "husté dělení, každý třetí box řidčeji"),
    ("mix4", "Mix 4", "postupně od řídkého dělení k hustému"),
    ("pln", "Plný set", "všechny sloty ve všech boxech"),
)
SET_IDS = tuple(x[0] for x in SETY)
UROVNE = {0: lambda m: 0, 1: lambda m: 1, 2: lambda m: m // 2, 3: lambda m: m}          # uroven hustoty -> pocet pricek v boxu o m slotech (1 pricka | polovina slotu (kazdy druhy) | vsechny sloty); m = 4 / 6 / 8 u multiboxu, 4 / 6 / 9 u suplikoveho podnosu
VZORY = {
    "bez": lambda i, n: 0,
    "mix1": lambda i, n: 3 if i % 2 == 0 else 1,
    "mix2": lambda i, n: 3 if i % 2 == 0 else 2,
    "mix3": lambda i, n: 1 if i % 3 == 2 else 3,
    "mix4": lambda i, n: 3 if n <= 1 else 1 + int(2.0 * i / (n - 1) + 0.5),
    "pln": lambda i, n: 3,
}

# druhy skupin (cislo ve spec -> klic) a popisy pro zakaznika; popisy jsou jen ve verejnem JSON, ne v GLB
DRUHY = {1: "police", 2: "vysuv", 3: "box", 4: "suplik"}
DRUH_POPIS = {"police": "Police s multiboxy", "vysuv": "Výsuv s multiboxy", "box": "Samostatné multiboxy", "suplik": "Šuplíky"}
# slova podle druhu skupiny (rozpis "6x v 5 boxech", poznamka objednavky "Multibox 1...N" / "Suplik 1...N")
SLOVA = {"box": {"jedn": "boxů", "jedn1": "boxu", "jednL": "boxech", "oznaceni": "Multibox"},
         "suplik": {"jedn": "šuplíků", "jedn1": "šuplíku", "jednL": "šuplících", "oznaceni": "Šuplík"}}
STRANA_POPIS = {"left": "levá strana", "right": "pravá strana", "bulkhead": "přepážka"}
MAX_BOXU = 400
_BID_RE = re.compile(r"b\d{1,4}")
_SID_RE = re.compile(r"s\d{1,4}")


# ------------------------------------------------------------------ typ a studna
def typ_boxu(mn, mx):
    """Klic typu ("395x186" ...) z AABB boxu (mm) nebo None (nezname rozmery / jina vyska)."""
    try:
        dx, dy, dz = (float(mx[i]) - float(mn[i]) for i in range(3))
    except (TypeError, ValueError, IndexError):
        return None
    L, W = max(dx, dz), min(dx, dz)
    if abs(dy - MB_VYSKA) > 2.0:                                  # jina vyska nez multibox: ocelovy suplikovy podnos (vyska 101 | 137 | 210)
        vt = next((v[0] for v in SUP_VYSKY if v[1] <= dy <= v[2]), None)
        ht = next((h[0] for h in SUP_HLOUBKY if h[1] <= W <= h[2]), None)
        st = next((x[0] for x in SUP_SIRKY if x[1] <= L <= x[2]), None)
        k = "S%sx%sx%s" % (st, ht, vt) if vt and ht and st else None
        return k if k in TYPY_SUP else None
    dt = next((d[0] for d in TRIDY_DELKY if d[1] <= L <= d[2]), None)
    wt = next((w[0] for w in TRIDY_SIRKY if w[1] <= W <= w[2]), None)
    return "%sx%s" % (dt, wt) if dt and wt else None


def osa_delky(mn, mx):
    """0 (X) nebo 2 (Z): delsi vodorovny rozmer AABB."""
    return 0 if (mx[0] - mn[0]) >= (mx[2] - mn[2]) else 2


def studna(k):
    L, W, _ = TYPY[k]
    return (STUDNA_OD, L - STENA, STENA, W - STENA)


def sirka_klic(k):
    return 186 if TYPY[k][1] > 140 else 91


def max_pricek(k):
    """Pocet slotu = nejvetsi mozny pocet pricek v boxu typu k."""
    if k in TYPY_SUP:
        return TYPY_SUP[k]["sloty"]
    return TYPY[k][2]


def dil_boxu(k):
    if k in TYPY_SUP:
        return TYPY_SUP[k]["dil"]
    return "p186" if sirka_klic(k) == 186 else "p91"


def geom_typu(k):
    """Geometricke udaje typu pro verejny JSON (plugin a miniatura): druh, osa prevracena orientaci e ("a" = delsi, "b" = kratsi), L (delsi vodorovna strana), W (kratsi), H (vyska), lem (tmavy konec v miniature)."""
    if k in TYPY_SUP:
        t = TYPY_SUP[k]
        return {"druh": "suplik", "os": "b", "L": t["L"], "W": t["W"], "H": t["H"], "lem": 0.0}
    L, W, _ = TYPY[k]
    return {"druh": "box", "os": "a", "L": L, "W": W, "H": MB_VYSKA, "lem": STUDNA_OD}


# ------------------------------------------------------------------ sloty, pricky, sety
def vyber_slotu(S, n):
    """Cisla slotu (1..S) pro n pricek rozlozenych co nejrovnomerneji (n = S: vsechny)."""
    n = max(0, min(int(n), S))
    return [int(math.floor(i * (S + 1) / (n + 1) + 0.5)) for i in range(1, n + 1)]


def desky_suplik(k, n):
    """Pricky v podnosu suplíku: MISTNI system x = podel sirky od min[a] (souměrne, bez prevraceni), y = nahoru od dna podnosu, z = podel hloubky OD CELA (prevraceni dela plugin podle e);
    sloty po 100 mm souměrně kolem stredu sirky, pricka jde zepredu dozadu (pres celou vnitrni hloubku)."""
    t = TYPY_SUP[k]
    S = t["sloty"]
    rz = DILY[t["dil"]]["rozmer"]
    y = round(t["podlaha"] + t["pricka_v"] / 2.0, 1)
    z = round(t["cela"] + (t["W"] - t["cela"] - t["zad"]) / 2.0, 1)
    return [{"s": [round(t["L"] / 2.0 + (j - (S + 1) / 2.0) * SUP_ROZTEC, 1), y, z], "r": [rz[0], rz[1], rz[2]], "d": t["dil"]} for j in vyber_slotu(S, n)]


def desky(k, n):
    """Fyzicke pricky pro n pricek v boxu typu k, v MISTNIM systemu boxu: [{"s": [x,y,z] stred, "r": [dx,dy,dz] rozmer, "d": klic dilu}]. Vsechny lezi uvnitr studny boxu a ve slotech."""
    if k in TYPY_SUP:
        return desky_suplik(k, n)
    x0, x1, z0, z1 = studna(k)
    S = max_pricek(k)
    pitch = (x1 - x0) / (S + 1)
    y = DNO + PRICKA_V / 2
    zc = (z0 + z1) / 2
    d = dil_boxu(k)
    rz = DILY[d]["rozmer"]
    return [{"s": [round(x0 + pitch * j, 1), round(y, 1), round(zc, 1)], "r": [rz[0], rz[1], rz[2]], "d": d} for j in vyber_slotu(S, n)]


def pocty_setu(set_id, typy_boxu):
    """[pocet pricek v kazdem boxu] pro set set_id a boxy skupiny (typy_boxu = klice typu v poradi boxu ve skupine)."""
    vzor = VZORY[set_id]
    n = len(typy_boxu)
    return [int(UROVNE[vzor(i, n)](max_pricek(k))) for i, k in enumerate(typy_boxu)]


def pocty_typu(k):
    """[{"n": n, "desky": [...]}] pro n = 0..sloty: geometrie pricek pro LIBOVOLNY pocet (vyber po boxech)."""
    return [{"n": n, "desky": desky(k, n)} for n in range(0, max_pricek(k) + 1)]


def _cena_dilu(ceny, klic):
    if ceny is None:
        return DILY[klic]["cena0"]
    return float(ceny[klic]["cena"])


# ------------------------------------------------------------------ boxy a skupiny ze spec
def boxy_ze_spec(spec):
    """[{id, k, n, g, s (id skupiny "s<N>"), sk (druh)}] jen boxy znameho typu; spec = validovany v3d spec (nebo None)."""
    out = []
    if not isinstance(spec, dict):
        return out
    for b in spec.get("mbx") or []:
        try:
            k = typ_boxu(b["min"], b["max"])
        except (KeyError, TypeError):
            k = None
        if k is None or not isinstance(b.get("id"), str) or not _BID_RE.fullmatch(b["id"]):
            continue
        s = b.get("s") if type(b.get("s")) is int and b.get("s") >= 0 else 0
        sk = "suplik" if k in TYPY_SUP else (DRUHY.get(b.get("sk"), "box") if DRUHY.get(b.get("sk")) != "suplik" else "box")          # druh podle typu (podnos suplíku = suplik, multibox nikdy suplik)
        out.append({"id": b["id"], "k": k, "n": b.get("n"), "g": b.get("g"), "s": "s%d" % s, "sk": sk})
    return out[:MAX_BOXU]


def skupiny_z_boxu(boxy, ceny=None):
    """[{id "s<N>", k druh, n poradi v ramci (strana, druh), g, popis, boxu, boxy [ids], sety {set_id: {priccek, cena, dily}}}] podle cisla skupiny."""
    by_s = {}
    for b in boxy:
        by_s.setdefault(b["s"], []).append(b)
    by_id = {b["id"]: b for b in boxy}
    out = []
    cnt = {}
    for sid in sorted(by_s, key=lambda x: int(x[1:])):
        bs = by_s[sid]
        druh = bs[0]["sk"]
        g = next((b["g"] for b in bs if b.get("g")), None)
        cnt[(g, druh)] = cnt.get((g, druh), 0) + 1
        n = cnt[(g, druh)]
        popis = DRUH_POPIS[druh] + ("" if druh == "box" else " %d" % n) + (" · %s" % STRANA_POPIS[g] if g in STRANA_POPIS else "")
        sk = {"id": sid, "k": druh, "n": n, "g": g, "popis": popis, "boxu": len(bs), "boxy": [b["id"] for b in bs]}
        sk["sety"] = sety_skupiny(sk, by_id, ceny)
        out.append(sk)
    return out


def sety_skupiny(sk, by_id, ceny):
    """{set_id: {"priccek", "cena" (Kc bez DPH za celou skupinu), "dily" {klic: pocet}, "po_boxech" [pocet v kazdem boxu skupiny v jejim poradi]}} v poradi SETY.
    Set, ktery by v dane skupine dal STEJNE pocty jako jiny (u 1-2 boxu: mixy se shoduji s plnym setem), se nenabizi dvakrat: prednost maji bez, pln, potom mixy v poradi."""
    out = {}
    typy = [by_id[bid]["k"] for bid in sk["boxy"]]
    videne = []
    for set_id in ("bez", "pln") + tuple(x for x in SET_IDS if x not in ("bez", "pln")):
        pocty = pocty_setu(set_id, typy)
        if pocty in videne:
            continue
        videne.append(pocty)
        dily = {}
        for k, n in zip(typy, pocty):
            if n:
                d = dil_boxu(k)
                dily[d] = dily.get(d, 0) + n
        out[set_id] = {"priccek": sum(dily.values()), "cena": round(sum(_cena_dilu(ceny, kd) * n for kd, n in dily.items()), 2), "dily": dily, "po_boxech": pocty}
    return {set_id: out[set_id] for set_id in SET_IDS if set_id in out}


# ------------------------------------------------------------------ ceny z karet
def nacti_ceny(cur):
    """{klic dilu: {"id", "cena", "nazev", "aktivni"}} podle SKU karet (jen cteni). Chybejici karta = klic chybi."""
    skus = list(SKU_NA_KLIC)
    cur.execute("SELECT id, sku, name, price_czk_placeholder, active, is_archived FROM shop_products WHERE sku IN (%s)" % ",".join(["%s"] * len(skus)), tuple(skus))
    out = {}
    for r in cur.fetchall():
        klic = SKU_NA_KLIC.get(r["sku"])
        if klic is None:
            continue
        try:
            cena = float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None
        except (TypeError, ValueError):
            cena = None
        out[klic] = {"id": r["id"], "cena": cena, "nazev": r["name"] or DILY[klic]["nazev"], "aktivni": bool(r["active"]) and not r["is_archived"]}
    return out


def ceny_pouzitelne(ceny, potrebne=None):
    """True, kdyz maji vsechny potrebne dily kartu s cenou."""
    return all(k in ceny and ceny[k]["cena"] is not None for k in (potrebne or DILY))


def vsechny_aktivni(ceny, potrebne=None):
    return ceny_pouzitelne(ceny, potrebne) and all(ceny[k]["aktivni"] for k in (potrebne or DILY))


# ------------------------------------------------------------------ vyber
def parse_vyber(raw):
    """Vyber zakaznika PO BOXECH -> {id boxu: pocet pricek}. Bere retezec "b01:6,b02:2" nebo dict {"b01": 6}. Neplatny tvar = ValueError."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, str):
        out = {}
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if part.count(":") != 1:
                raise ValueError("neplatny vyber pricek")
            a, b = part.split(":")
            a, b = a.strip(), b.strip()
            if a in out or not re.fullmatch(r"\d{1,2}", b):
                raise ValueError("neplatny vyber pricek")
            out[a] = int(b)
        raw = out
    if not isinstance(raw, dict) or len(raw) > MAX_BOXU:
        raise ValueError("neplatny vyber pricek")
    out = {}
    for a, b in raw.items():
        if not isinstance(a, str) or not _BID_RE.fullmatch(a) or type(b) is not int or not (0 <= b <= 99):
            raise ValueError("neplatny vyber pricek")
        out[a] = b
    return out


def over_vyber(vyber, boxy):
    """Vyber proti boxum nabidky: cisty dict bez nul (= beze zmeny); neznamy box nebo pocet nad pocet slotu boxu = ValueError."""
    by_id = {b["id"]: b for b in boxy}
    out = {}
    for bid, n in vyber.items():
        b = by_id.get(bid)
        if b is None:
            raise ValueError("neznamy box %s" % bid)
        if not (0 <= n <= max_pricek(b["k"])):
            raise ValueError("box %s: pocet pricek %d mimo 0..%d" % (bid, n, max_pricek(b["k"])))
        if n:
            out[bid] = n
    return out


def vyber_retezec(vyber):
    return ",".join("%s:%d" % (a, b) for a, b in sorted(vyber.items(), key=lambda kv: int(kv[0][1:])) if b)


def vyber_ze_setu(boxy, skupiny, sety):
    """{id boxu: pocet} z {id skupiny: id setu} (zkratka pro sety; nezname skupiny a sety, ktere skupina nenabizi, se preskoci)."""
    sk_by = {s["id"]: s for s in skupiny}
    out = {}
    for sid, set_id in sety.items():
        sk = sk_by.get(sid)
        if sk is None or set_id not in sk["sety"]:
            continue
        for bid, n in zip(sk["boxy"], sk["sety"][set_id]["po_boxech"]):
            if n:
                out[bid] = n
    return out


def rozpoznej_set(sk, by_id, vyber):
    """'bez' (v boxech skupiny nejsou zadne pricky), id setu nabizeneho skupine (pocty ve vsech boxech presne odpovidaji setu) nebo 'vlastni' (vlastni kombinace)."""
    pocty = [vyber.get(bid, 0) for bid in sk["boxy"]]
    if not any(pocty):
        return "bez"
    for set_id, info in sk["sety"].items():
        if set_id != "bez" and pocty == info["po_boxech"]:
            return set_id
    return "vlastni"


def spocti(boxy, skupiny, vyber, ceny):
    """Rozpis (jiz overeneho) vyberu po boxech pro JEDEN kus sestavy (qty nasobi volajici).

    vraci {"radky": [{"klic", "product_id", "name", "qty", "unit_price", "total"}], "net": soucet bez DPH, "skupin": pocet skupin s pricky, "boxu": pocet boxu s pricky, "kusu": pocet pricek,
           "popis": [{"id", "popis" skupiny, "set" (id setu / vlastni), "set_popis", "boxu" ve skupine, "boxu_s_pricky", "priccek", "cena", "rozpis": "6× v 5 boxech, 2× v 1 boxu",
                      "po_boxech": [pocet pricek v kazdem boxu skupiny v poradi boxu skupiny (shodne s poradim v nabidce)]}]}."""
    by_id = {b["id"]: b for b in boxy}
    celkem = {}
    popis = []
    boxu = 0
    for sk in sorted(skupiny, key=lambda x: int(x["id"][1:])):
        v = {bid: vyber[bid] for bid in sk["boxy"] if vyber.get(bid)}
        if not v:
            continue
        dily = {}
        hist = {}
        for bid, n in v.items():
            d = dil_boxu(by_id[bid]["k"])
            dily[d] = dily.get(d, 0) + n
            celkem[d] = celkem.get(d, 0) + n
            hist[n] = hist.get(n, 0) + 1
        boxu += len(v)
        set_id = rozpoznej_set(sk, by_id, vyber)
        set_popis = "Vlastní kombinace" if set_id == "vlastni" else next(x[1] for x in SETY if x[0] == set_id)
        sl = SLOVA["suplik" if sk["k"] == "suplik" else "box"]
        rozpis = ", ".join("%d× v %d %s" % (n, c, sl["jedn1"] if c == 1 else sl["jednL"]) for n, c in sorted(hist.items(), reverse=True))
        popis.append({"id": sk["id"], "popis": sk["popis"], "set": set_id, "set_popis": set_popis, "boxu": sk["boxu"], "boxu_s_pricky": len(v), "priccek": sum(v.values()),
                      "jednotka": sl["jedn"], "jednotkaL": sl["jednL"], "oznaceni": sl["oznaceni"],
                      "cena": round(sum(_cena_dilu(ceny, kd) * n for kd, n in dily.items()), 2), "rozpis": rozpis, "po_boxech": [vyber.get(bid, 0) for bid in sk["boxy"]]})
    radky = []
    for kd in DILY:                                                     # stabilni poradi
        n = celkem.get(kd)
        if not n:
            continue
        c = ceny[kd]
        jedn = round(float(c["cena"]), 2)
        radky.append({"klic": kd, "product_id": c["id"], "name": c["nazev"] or DILY[kd]["nazev"], "qty": n, "unit_price": jedn, "total": round(jedn * n, 2)})
    return {"radky": radky, "net": round(sum(r["total"] for r in radky), 2), "skupin": len(popis), "boxu": boxu, "kusu": sum(celkem.values()), "popis": popis}


# ------------------------------------------------------------------ dostupnost po skupinach
def dostupne_boxy(boxy, ceny, admin=False):
    """Boxy skupin, ktere se smi nabidnout: vsechny dily skupiny maji kartu s cenou a (verejnosti) AKTIVNI kartu; admin (nahled pred aktivaci) vidi i skupiny s dosud neaktivnimi kartami.
    Skupiny jsou nezavisle (multiboxy se nabizeji, i kdyz dily suplikovych pricek karty nemaji, a naopak)."""
    by_s = {}
    for b in boxy:
        by_s.setdefault(b["s"], []).append(b)
    ok = set()
    for sid, bs in by_s.items():
        potrebne = {dil_boxu(b["k"]) for b in bs}
        if ceny_pouzitelne(ceny, potrebne) and (admin or vsechny_aktivni(ceny, potrebne)):
            ok.add(sid)
    return [b for b in boxy if b["s"] in ok]


# ------------------------------------------------------------------ verejny JSON
def payload(spec, ceny, nahled_admin=False):
    """Blok offer.pricky pro verejny JSON nabidky; None, kdyz nabidka nema boxy znameho typu nebo zadna skupina neni dostupna.

    Verejnosti jen skupiny, jejichz vsechny dily maji aktivni kartu s cenou; nahled_admin = divak je admin (odkaz "Zobrazit online"): vidi i skupiny s dosud neaktivnimi kartami
    (skupina.skryto = true, banner nahled_admin)."""
    boxy_vse = boxy_ze_spec(spec)
    verejne = dostupne_boxy(boxy_vse, ceny, False)
    boxy = dostupne_boxy(boxy_vse, ceny, True) if nahled_admin else verejne
    if not boxy:
        return None
    ids_verejne = {b["id"] for b in verejne}
    skupiny = skupiny_z_boxu(boxy, ceny)
    for sk in skupiny:
        sk["skryto"] = any(bid not in ids_verejne for bid in sk["boxy"])
    typy = {}
    for k in sorted({b["k"] for b in boxy}):
        typy[k] = dict({"popis": TYP_POPIS[k], "max": max_pricek(k), "dil": dil_boxu(k), "pocty": pocty_typu(k)}, **geom_typu(k))
    pouzite = {dil_boxu(b["k"]) for b in boxy}
    return {
        "enabled": True, "nahled_admin": any(sk["skryto"] for sk in skupiny),
        "sety": [{"id": x[0], "popis": x[1], "pozn": x[2]} for x in SETY],
        "skupiny": skupiny, "boxy": boxy, "typy": typy,
        "dily": [{"klic": k, "nazev": ceny[k]["nazev"], "cena": round(float(ceny[k]["cena"]), 2), "product_id": ceny[k]["id"]} for k in DILY if k in pouzite],
        "geom": {"vyska_boxu": MB_VYSKA, "studna_od": STUDNA_OD},
    }
