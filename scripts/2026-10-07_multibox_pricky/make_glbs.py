#!/usr/bin/env python3
"""Pomocnik testu pluginu pricek (bot8, 2026-10-07): pripravi vstupy pro test_plugin.js do DOCASNE slozky - zadny fixture v repu.
  payload_<karta>.json  verejny blok offer.pricky vyrobeny z `spec` zakaznickeho GLB karty (<OUT>/out2/<karta>.offer.glb) pres api/nabidka_pricky.payload s TESTOVACIMI cenami
                        (p186 = id 9001, 39 Kc; p91 = id 9002, 29 Kc; aktivni); karty bez multiboxu / bez GLB se preskoci s hlaskou
                        v5: ma-li karta podnosy supliku (mbx sk = 4), je payload_<karta>.json i GLB <karta>.offer.glb (v teto docasne slozce, test ji servíruje prednostne) pohled 'JEN MULTIBOXY':
                        podnosy odfiltrovane, id boxu b01.. / cisla skupin / n prectislovane od 1 = presne karta pred v5 (puvodni karetni kontroly bezi beze zmeny na starych I novych GLB);
                        karta jen z podnosu (napr. 4968) nema payload_<karta>.json. Karta VCETNE podnosu: <karta>.vse.glb + payload_<karta>.vse.json (sekce R testu)
  synt.glb              z 4921.offer.glb: syntetickeho mbx (osa X i Z, e = +1 / -1, staticke i pohyblive boxy, delky 288 / 395 / 500, neexistujici pivot) + synt.payload.json, synt.mbx.json
  nombx.glb             tentyz model BEZ mbx (box nenalezen)
  pohyby.glb            (v4.1) z 4921.offer.glb: mbx + motions (box / slide / drawer, vadne polozky) pro api.motionIds + pohyby.payload.json
  suplik.glb            (v5) 12 typu podnosu ocelovych SUPLIKU z kontraktu x 4 orientace (osa delky X i Z, e = +1 / -1), po skupine na typ, sk = 4 + suplik.payload.json, suplik.mbx.json
  smisena.glb           (v5) smisena scena multibox + suplik: podnosy a boxy staticke i pod pivoty vysuvu z modelu 4921 (pohyb s pivotem) + smisena.payload.json, smisena.mbx.json, smisena.piv.json
Geometrie boxu v syntetickem modelu neodpovida; u synt. boxu se overuje jen matematika umisteni vuci mbx AABB.
Payload supliku: kdyz ma API (kandidat) podporu supliku (api/nabidka_pricky.payload(spec, ceny, nahled_admin=True) vrati typy s druh 'suplik'), pouzije se SKUTECNY vystup; jinak se
payload sestavi RUCNE podle kontraktu (c5/KONTRAKT_SUPLIKY_v5.md); PRICKY_SUPLIKY=rucne|skutecny|auto (vychozi auto) to prepise. Test pak kontroluje geometrii proti cislum z kontraktu v JS (nezavisle na obou).
Spusteni:  python3 make_glbs.py <vystupni_slozka>
Prostredi: PRICKY_REPO (koren repa, vychozi ../..), PRICKY_API (slozka s v3d_glb.py a nabidka_pricky.py, vychozi <repo>/api; kandidat pred nasazenim),
           V3D_TEST_OUT (vychozi <tmp>/v3d_testy; GLB v <OUT>/out2 stavi scripts/2026-10-02_v3d_testy/build_karty.py 4917 4918 4921 4594), PRICKY_FIX (primo slozka s <karta>.offer.glb).
Povinne karty: 4921 a 4917 (jinak konci s kodem 2); na konci vypise radek `KARTY {...}` s tim, co pripravil."""
import json
import math
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("PRICKY_REPO") or os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.environ.get("PRICKY_API") or os.path.join(REPO, "api")
OUT = os.environ.get("V3D_TEST_OUT") or os.path.join(tempfile.gettempdir(), "v3d_testy")
FIX = os.environ.get("PRICKY_FIX") or os.path.join(OUT, "out2")
POVINNE = ("4921", "4917")
MOD_SUPLIKY = os.environ.get("PRICKY_SUPLIKY") or "auto"
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import v3d_glb  # noqa: E402
import nabidka_pricky as P  # noqa: E402

# testovaci ceny (id karet 9001+ jsou vymyslene, nic se nikam nezapisuje); ceny supliku = orientacni ceny z kontraktu v5 (bez DPH)
CENY = {"p186": {"id": 9001, "cena": 39.0, "nazev": P.DILY["p186"]["nazev"], "aktivni": True},
        "p91": {"id": 9002, "cena": 29.0, "nazev": P.DILY["p91"]["nazev"], "aktivni": True}}
SUP_DILY = (("ps332v137", 9003, 59.0), ("ps332v210", 9004, 79.0), ("ps384v101", 9005, 59.0), ("ps384v137", 9006, 69.0), ("ps384v210", 9007, 89.0))
for _k, _id, _c in SUP_DILY:
    CENY[_k] = {"id": _id, "cena": _c, "nazev": "Příčka do ocelového šuplíku, hloubka %s mm, výška %s mm" % (_k[2:5], _k[6:]), "aktivni": True}

# ---------------------------------------------------------------------- supliky (v5): tabulky z kontraktu c5/KONTRAKT_SUPLIKY_v5.md (rucni generator payloadu = nezavisly zdroj pravdy)
SUP_BOK = {443: 12.5, 695: 11.4, 950: 11.7}                  # mezera od boku dutiny podnosu (mm) podle sirky
SUP_CELO = {332: 0.4, 384: 0.5}                              # mezera od cela podle hloubky
SUP_LEM = {332: 17.8, 384: 20.6}                             # zadni lem podle hloubky
SUP_PODLAHA = {101: 1.0, 137: 1.4, 210: 2.1}                 # vyska podlahy podle vysky podnosu
SUP_SLOT = 100.0                                             # sloty po 100 mm napric sirkou, soumerne kolem stredu
SUP_TYPY = ((443, 332, 137), (695, 332, 137), (950, 332, 137), (443, 332, 210), (695, 332, 210), (443, 384, 137), (695, 384, 137), (950, 384, 137),
            (443, 384, 210), (695, 384, 210), (950, 384, 210), (950, 384, 101))
DRUH_SUPLIK = 4                                              # mbx[].sk u supliku


def suplik_klic(L, W, H):
    return "S%dx%dx%d" % (L, W, H)


def suplik_dil(W, H):
    return "ps%dv%d" % (W, H)


def suplik_max(L):
    return int((L - 2 * SUP_BOK[L]) // SUP_SLOT)             # 443: 4, 695: 6, 950: 9


def vyber_slotu(S, n):
    """Cisla slotu (1..S) pro n pricek rozlozenych co nejrovnomerneji (stejne pravidlo jako u multiboxu)."""
    n = max(0, min(int(n), S))
    return [int(math.floor(i * (S + 1) / (n + 1) + 0.5)) for i in range(1, n + 1)]


def desky_suplik(L, W, H, n):
    """Pricky n-teho poctu v MISTNIM systemu podnosu (kontrakt v5 oddil 4): x podel delsi osy od min (bez prevraceni), y od min nahoru, z od cela podel kratsi osy; r = [tloustka, vyska, delka zepredu dozadu]."""
    mx = suplik_max(L)
    vnitrni = W - SUP_CELO[W] - SUP_LEM[W]
    h = H - 8.0
    y = SUP_PODLAHA[H] + h / 2.0
    z = SUP_CELO[W] + vnitrni / 2.0
    return [{"s": [round(L / 2.0 + (j - (mx + 1) / 2.0) * SUP_SLOT, 1), round(y, 1), round(z, 1)], "r": [2.0, h, float(math.floor(vnitrni))], "d": suplik_dil(W, H)} for j in vyber_slotu(mx, n)]


def typ_suplik(L, W, H):
    mx = suplik_max(L)
    return {"popis": "Ocelový šuplík %d × %d × %d mm" % (L, W, H), "max": mx, "dil": suplik_dil(W, H), "pocty": [{"n": n, "desky": desky_suplik(L, W, H, n)} for n in range(mx + 1)],
            "druh": "suplik", "os": "b", "L": float(L), "W": float(W), "H": float(H), "lem": 0.0}


def klic_suplik_z_aabb(mn, mx):
    d = [mx[i] - mn[i] for i in range(3)]
    t = (int(round(max(d[0], d[2]))), int(round(min(d[0], d[2]))), int(round(d[1])))
    return t if t in SUP_TYPY else None


def payload_rucne(mbx):
    """offer.pricky podle kontraktu v5 pro syntetickou scenu (multiboxy i supliky); TESTOVACI ceny z CENY, vsechny dily aktivni (skryto false)."""
    VZORY = getattr(P, "VZORY", None) or {"bez": lambda i, n: 0, "mix1": lambda i, n: 3 if i % 2 == 0 else 1, "mix2": lambda i, n: 3 if i % 2 == 0 else 2,
                                           "mix3": lambda i, n: 1 if i % 3 == 2 else 3, "mix4": lambda i, n: 3 if n <= 1 else 1 + int(2.0 * i / (n - 1) + 0.5), "pln": lambda i, n: 3}
    UROVNE = getattr(P, "UROVNE", None) or {0: lambda m: 0, 1: lambda m: 1, 2: lambda m: (m + 1) // 2, 3: lambda m: m}
    SETY = getattr(P, "SETY", None) or (("bez", "Bez příček", ""), ("mix1", "Mix 1", "střídavě husté a řídké dělení"), ("mix2", "Mix 2", "střídavě husté a středně husté dělení"),
                                         ("mix3", "Mix 3", "husté dělení, každý třetí box řidčeji"), ("mix4", "Mix 4", "postupně od řídkého dělení k hustému"), ("pln", "Plný set", "všechny sloty ve všech boxech"))
    SET_IDS = tuple(x[0] for x in SETY)
    STRANA = getattr(P, "STRANA_POPIS", {"left": "levá strana", "right": "pravá strana", "bulkhead": "přepážka"})
    boxy, typy, max_typu = [], {}, {}
    for b in mbx:
        sk = b.get("sk")
        if sk == DRUH_SUPLIK:
            t = klic_suplik_z_aabb(b["min"], b["max"])
            if t is None:
                continue
            k = suplik_klic(*t)
            if k not in typy:
                typy[k] = typ_suplik(*t)
            druh, sk_txt = "suplik", "suplik"
        else:
            k = P.typ_boxu(b["min"], b["max"])
            if k is None:
                continue
            if k not in typy:
                typy[k] = {"popis": P.TYP_POPIS[k], "max": P.max_pricek(k), "dil": P.dil_boxu(k), "pocty": P.pocty_typu(k), "druh": "box", "os": "a",
                           "L": float(P.TYPY[k][0]), "W": float(P.TYPY[k][1]), "H": float(P.MB_VYSKA), "lem": float(P.STUDNA_OD)}
            druh, sk_txt = P.DRUHY.get(sk, "box"), P.DRUHY.get(sk, "box")
        max_typu[k] = typy[k]["max"]
        boxy.append({"id": b["id"], "k": k, "n": b.get("n"), "g": b.get("g"), "s": "s%d" % (b.get("s") if type(b.get("s")) is int and b.get("s") >= 0 else 0), "sk": sk_txt})
    by_id = {b["id"]: b for b in boxy}
    popis_druhu = {"police": "Police s multiboxy", "vysuv": "Výsuv s multiboxy", "box": "Samostatné multiboxy", "suplik": "Šuplíky"}
    by_s = {}
    for b in boxy:
        by_s.setdefault(b["s"], []).append(b)
    skupiny, cnt = [], {}
    for sid in sorted(by_s, key=lambda x: int(x[1:])):
        bs = by_s[sid]
        druh = bs[0]["sk"]
        g = next((b["g"] for b in bs if b.get("g")), None)
        cnt[(g, druh)] = cnt.get((g, druh), 0) + 1
        n = cnt[(g, druh)]
        popis = popis_druhu[druh] + ("" if druh == "box" else " %d" % n) + (" · %s" % STRANA[g] if g in STRANA else "")
        sk = {"id": sid, "k": druh, "n": n, "g": g, "popis": popis, "boxu": len(bs), "boxy": [b["id"] for b in bs]}
        typy_boxu = [b["k"] for b in bs]
        out, videne = {}, []
        for set_id in ("bez", "pln") + tuple(x for x in SET_IDS if x not in ("bez", "pln")):
            pocty = [int(UROVNE[VZORY[set_id](i, len(bs))](max_typu[k])) for i, k in enumerate(typy_boxu)]
            if pocty in videne:
                continue
            videne.append(pocty)
            dily = {}
            for k, c in zip(typy_boxu, pocty):
                if c:
                    d = typy[k]["dil"]
                    dily[d] = dily.get(d, 0) + c
            out[set_id] = {"priccek": sum(dily.values()), "cena": round(sum(CENY[kd]["cena"] * c for kd, c in dily.items()), 2), "dily": dily, "po_boxech": pocty}
        sk["sety"] = {x: out[x] for x in SET_IDS if x in out}
        sk["skryto"] = False
        skupiny.append(sk)
    pouzite = [d for d in CENY if any(t["dil"] == d for t in typy.values())]
    return {"enabled": True, "nahled_admin": False, "sety": [{"id": x[0], "popis": x[1], "pozn": x[2]} for x in SETY], "skupiny": skupiny, "boxy": boxy,
            "typy": {k: typy[k] for k in sorted(typy)}, "dily": [{"klic": d, "nazev": CENY[d]["nazev"], "cena": round(CENY[d]["cena"], 2), "product_id": CENY[d]["id"]} for d in pouzite],
            "geom": {"vyska_boxu": P.MB_VYSKA, "studna_od": P.STUDNA_OD}}


def payload_skutecny(mbx):
    """SKUTECNY vystup API (kandidat s podporou supliku: payload(spec, ceny, nahled_admin=True)) nebo None, kdyz API supliky (jeste) neumi."""
    try:
        pl = P.payload({"mbx": mbx}, CENY, nahled_admin=True)
    except TypeError:
        return None                                  # v4: payload(spec, ceny, zapnuto, nahled_admin=False) - supliky nezna
    if pl and any(t.get("druh") == "suplik" for t in pl.get("typy", {}).values()):
        return pl
    return None


def payload_supliku(mbx):
    """(payload, zdroj 'rucne' | 'skutecny') podle PRICKY_SUPLIKY."""
    if MOD_SUPLIKY != "rucne":
        pl = payload_skutecny(mbx)
        if pl is not None:
            return pl, "skutecny"
        if MOD_SUPLIKY == "skutecny":
            sys.exit("CHYBA: PRICKY_SUPLIKY=skutecny, ale API %s supliky nepodporuje" % API)
    return payload_rucne(mbx), "rucne"


def pl_karty(spec):
    """payload karty (multiboxy) s testovacimi cenami; v4: payload(spec, ceny, zapnuto), v5: payload(spec, ceny, nahled_admin=False)."""
    try:
        return P.payload(spec, CENY, nahled_admin=True)
    except TypeError:
        return P.payload(spec, CENY, True)


# ---------------------------------------------------------------------- syntetika
def box(bid, x, y, z, L, W, osa, e, p=None, n=None, s=None, sk=None, H=81.0):
    mn = [x, y, z]
    mx = [x + (L if osa == 0 else W), y + H, z + (W if osa == 0 else L)]
    d = {"id": bid, "min": mn, "max": mx, "e": e, "p": p}
    if n is not None:
        d["n"] = n
    if s is not None:
        d["s"] = s                       # cislo skupiny (police / suplik)
        d["sk"] = sk                     # druh skupiny: 1 police, 2 vysuv, 3 samostatne, 4 suplik
    return d


MBX = [
    box("b01", 100, 100, 100, 395.5, 186.0, 0, 1, n=1, s=1, sk=1),                  # police s1: staticky, osa X, vykroj na MIN strane
    box("b02", 100, 100, 400, 395.5, 186.0, 0, -1, n=2, s=1, sk=1),                 # police s1: staticky, osa X, vykroj na MAX strane
    box("b03", 700, 100, 100, 395.5, 186.0, 2, 1, n=3, s=2, sk=3),                  # samostatne s2: osa Z (otoceny o 90 stupnu), vykroj na MIN strane
    box("b04", 1000, 100, 100, 395.5, 186.0, 2, -1, n=4, s=2, sk=3),                # samostatne s2: osa Z, vykroj na MAX strane
    box("b05", 1300, 100, 100, 395.5, 91.0, 2, 1, p="p22", n=5, s=3, sk=2),         # vysuv s3: uzky, osa Z, v pivotu p22 (pohyblivy)
    box("b06", 1500, 100, 100, 288.0, 91.0, 0, -1, n=6, s=4, sk=3),                 # samostatne s4: kratky uzky, osa X
    box("b07", 1500, 300, 100, 288.0, 186.0, 0, 1, n=7, s=4, sk=3),                 # samostatne s4: kratky siroky
    box("b10", 1500, 500, 100, 395.5, 186.0, 0, -1, n=10, s=4, sk=3),               # samostatne s4: DLOUHY box ve skupine s kratkymi (ruzne delky = ruzne pocty pricek u stejneho setu)
    box("b08", 1800, 100, 100, 395.5, 186.0, 0, 1, p="p99", n=8, s=5, sk=2),        # vysuv s5: pivot p99 v modelu neni -> plugin box preskoci (skupina neni ready)
    box("b09", 2200, 100, 100, 500.0, 186.0, 0, 1, n=9, s=6, sk=3),                 # samostatne s6: delka 500 (8 slotu), zatim se nepouziva
]


def tray(bid, x, y, z, t, osa, e, p=None, n=None, s=None):
    """Podnos supliku typu t = (L, W, H): osa delky (sirka podnosu) X (0) nebo Z (2), e = strana cela na kratsi ose b (+1 min, -1 max)."""
    L, W, H = t
    return box(bid, x, y, z, float(L), float(W), osa, e, p=p, n=n, s=s, sk=DRUH_SUPLIK, H=float(H))


def suplik_mbx():
    """12 typu x 4 orientace (osa X / Z x e = +1 / -1), po skupine na typ."""
    out, bi = [], 0
    for ti, t in enumerate(SUP_TYPY):
        for oi, (osa, e) in enumerate(((0, 1), (0, -1), (2, 1), (2, -1))):
            bi += 1
            out.append(tray("b%02d" % bi, 4000 + 1300 * oi, 100 + 400 * ti, 100, t, osa, e, n=oi + 1, s=ti + 1))
    return out


def pivoty_modelu(raw):
    """id pivotu dvou pohybu typu vysuv / suplik v modelu (ty se pri otevreni opravdu pohnou) - pro 'podnos pod pivotem vysuvu'."""
    g, _ = v3d_glb.read_glb(raw)
    spec = g["scenes"][0]["extras"]["v3d"]
    piv = []
    for m in spec.get("motions", []):
        if m.get("k") in ("slide", "drawer"):
            p = m["steps"][0]["p"]
            if p not in piv:
                piv.append(p)
    return piv


def smisena_mbx(piv):
    """Smisena scena multibox + suplik: staticke i pod pivotem vysuvu (piv[0], piv[1] z modelu), oba smery e, osa X i Z; supliky ruznych typu v jedne skupine."""
    p1, p2 = piv[0], piv[1]
    return [
        box("b01", 100, 100, 100, 395.5, 186.0, 0, 1, n=1, s=1, sk=1),                                  # police s1: staticke multiboxy
        box("b02", 100, 100, 400, 395.5, 186.0, 0, -1, n=2, s=1, sk=1),
        box("b03", 700, 100, 100, 395.5, 91.0, 2, 1, p=p1, n=3, s=2, sk=2),                             # vysuv s2: multibox pod pivotem vysuvu p1
        box("b04", 1000, 100, 100, 395.5, 186.0, 2, -1, p=p1, n=4, s=2, sk=2),
        tray("b05", 3000, 100, 100, (950, 384, 101), 0, 1, p=p2, n=5, s=3),                             # suplik s3: tri podnosy ruznych typu pod pivotem vysuvu p2
        tray("b06", 3000, 100, 600, (695, 384, 137), 0, -1, p=p2, n=6, s=3),
        tray("b07", 4200, 100, 100, (443, 332, 210), 2, 1, p=p2, n=7, s=3),
        tray("b08", 3000, 500, 100, (950, 384, 137), 2, -1, n=8, s=4),                                  # suplik s4: dva staticke podnosy
        tray("b09", 4500, 500, 600, (695, 332, 137), 0, 1, n=9, s=4),
    ]


# ---- pohyby (v4.1, api.motionIds): syntetizovany spec - motions podle skutecneho modelu 4921 (box = 3 kroky na pivotu boxu, slide / drawer na pivotu vysuvu) + okrajove pripady pravidla box -> pohyb
def krok(p, ax=(0, 1, 0), v=20.0):
    return {"p": p, "op": "T", "ax": list(ax), "v": v, "ms": 1200}


POH_MOT = [
    {"id": "m1", "k": "drawer", "n": 1, "steps": [krok("p01", (-1, 0, 0), 450.0)], "pick": ["p01"]},
    {"id": "m2", "k": "slide", "n": 1, "steps": [krok("p02", (-1, 0, 0), 450.0)], "pick": ["p02"]},
    {"id": "m3", "k": "box", "sub": "multibox", "n": 1, "steps": [krok("p03", (0, 1, 0), 22.5), krok("p03", (-1, 0, 0), 444.1), krok("p03", (0, 1, 0), 37.5)], "pick": ["p03"]},
    {"id": "m4", "k": "box", "sub": "multibox", "n": 2, "steps": [krok("p04", (0, 1, 0), 22.5), krok("p04", (-1, 0, 0), 444.1), krok("p04", (0, 1, 0), 37.5)], "pick": ["p04"]},
    {"id": "m5", "k": "slide", "n": 2, "steps": [krok("p05", (-1, 0, 0), 450.0)], "pick": ["p05"]},                 # pivot p05: JEN pohyb typu slide (zadny box)
    {"id": "m6", "k": "slide", "n": 3, "steps": [krok("p06", (-1, 0, 0), 450.0)], "pick": ["p06"]},                 # pivot p06: pohyb typu slide je v seznamu PRED pohybem k box
    {"id": "m7", "k": "box", "sub": "multibox", "n": 3, "steps": [krok("p06"), krok("p06", (-1, 0, 0), 300.0)], "pick": ["p06"]},
    {"id": "m8", "k": "box", "sub": "multibox", "n": 4, "steps": [krok("p08"), krok("p07", (-1, 0, 0), 300.0)], "pick": ["p07"]},     # pivot boxu p07 je az ve 2. kroku
    {"id": "m9", "k": "box", "sub": "multibox", "n": 5, "steps": [krok("p09")], "pick": ["p09"]},
    {"id": "m10", "k": "box", "sub": "multibox", "n": 6, "steps": [krok("p10")], "pick": ["p10"]},
    {"id": "m11", "k": "slide", "n": 4, "steps": [krok("p12", (-1, 0, 0), 450.0)], "pick": ["p12"]},               # pivot p12: dva pohyby BEZ k box (slide, potom drawer) -> vezme se PRVNI (m11)
    {"id": "m12", "k": "drawer", "n": 2, "steps": [krok("p12", (-1, 0, 0), 450.0)], "pick": ["p12"]},
    {"id": "m13", "k": "box", "sub": "multibox", "n": 7, "steps": [krok("p10")], "pick": ["p10"]},                # druhy pohyb k box na pivotu p10 -> vezme se prvni (m10)
    None, {"id": 5}, {"id": "mx", "k": "box", "steps": "x"}, {"id": "my", "k": "box", "steps": [None, {"p": 5}, {}]},                      # vadne polozky: plugin je preskoci
]
POH_MBX = [
    box("b01", 100, 100, 100, 395.5, 186.0, 0, 1, p="p03", n=1, s=1, sk=1),            # s1: pivot p03 -> m3
    box("b02", 100, 100, 400, 395.5, 186.0, 0, 1, p="p03", n=2, s=1, sk=1),            # sdili pivot s b01 -> m3 jen jednou
    box("b03", 100, 100, 700, 395.5, 186.0, 0, 1, n=3, s=1, sk=1),                     # bez pivotu (staticky) -> preskoci
    box("b04", 100, 100, 1000, 395.5, 186.0, 0, 1, p="p04", n=4, s=1, sk=1),           # -> m4
    box("b05", 700, 100, 100, 395.5, 186.0, 0, 1, p="p05", n=5, s=2, sk=2),            # s2: jen pohyb slide m5 (zadny box) -> m5
    box("b06", 700, 100, 400, 395.5, 186.0, 0, 1, p="p06", n=6, s=2, sk=2),            # slide m6 pred box m7 -> prednost ma box: m7
    box("b07", 700, 100, 700, 395.5, 186.0, 0, 1, p="p11", n=7, s=2, sk=2),            # pivot p11 v modelu je, ale zadny pohyb -> preskoci
    box("b08", 1300, 100, 100, 395.5, 186.0, 0, 1, p="p07", n=8, s=3, sk=2),           # s3: pivot az ve 2. kroku m8 -> m8
    box("b09", 1300, 100, 400, 395.5, 186.0, 0, 1, p="p10", n=9, s=3, sk=2),           # -> m10
    box("b10", 1300, 100, 700, 395.5, 186.0, 0, 1, p="p09", n=10, s=3, sk=2),          # -> m9 (poradi boxu skupiny, ne id pohybu: m8, m10, m9)
    box("b11", 1900, 100, 100, 395.5, 186.0, 0, 1, p="p99", n=11, s=4, sk=2),          # s4: pivot p99 v modelu neni -> box neni v modelu -> preskoci
    box("b12", 1900, 100, 400, 395.5, 186.0, 0, 1, p="p03", n=12, s=4, sk=2),          # p03 sdili se s1 -> m3 (pres vsechny skupiny jen jednou)
    box("b13", 2500, 100, 100, 395.5, 186.0, 0, 1, n=13, s=5, sk=3),                   # s5: jen staticky box -> []
    box("b14", 700, 100, 1000, 395.5, 186.0, 0, 1, p="p12", n=14, s=2, sk=2),          # s2: pivot p12 ma jen pohyby bez k box (m11 slide, m12 drawer) -> prvni: m11
]


def pohyby(spec):
    spec["mbx"] = POH_MBX
    spec["motions"] = POH_MOT


def jen_multiboxy(mbx):
    """mbx karty bez podnosu supliku (sk 4): id b01.. v poradi, cisla skupin s a poradi n prectislovane od 1 = presne mbx karty pred v5 (podnosy se do nej nevkladaly)."""
    out, skup = [], {}
    for i, x in enumerate(m for m in mbx if isinstance(m, dict) and m.get("sk") != 4):
        x = dict(x)
        x["id"] = "b%02d" % (i + 1)
        if "n" in x:
            x["n"] = i + 1
        if "s" in x:
            skup.setdefault(x["s"], len(skup) + 1)
            x["s"] = skup[x["s"]]
        out.append(x)
    return out


def main(out):
    os.makedirs(out, exist_ok=True)
    for k in POVINNE:
        if not os.path.isfile(os.path.join(FIX, k + ".offer.glb")):
            sys.exit("CHYBA: chybi %s - postav zakaznicka GLB: python3 scripts/2026-10-02_v3d_testy/build_karty.py 4917 4918 4921 4594 (V3D_TEST_OUT=%s)" % (os.path.join(FIX, k + ".offer.glb"), OUT))
    hotovo, preskoceno, vse, filtrovano = [], {}, [], []
    for fn in sorted(os.listdir(FIX)):
        m = re.fullmatch(r"(\d+)\.offer\.glb", fn)
        if not m:
            continue
        karta = m.group(1)
        try:
            raw_karty = open(os.path.join(FIX, fn), "rb").read()
            spec = v3d_glb.embedded_spec(raw_karty)
            mb_vse = (spec or {}).get("mbx") or []
            if any(isinstance(x, dict) and x.get("sk") == 4 for x in mb_vse):
                # v5: karta se supliky. (1) <karta>.vse.glb + payload_<karta>.vse.json = karta VCETNE podnosu (sekce R); (2) <karta>.offer.glb + payload_<karta>.json = pohled 'jen multiboxy'
                # (podnosy pryc, id / skupiny / n prectislovane = presne karta jako pred v5), takze puvodni karetni kontroly bezi beze zmeny na starych I novych zakaznickych GLB
                json.dump(pl_karty(spec), open(os.path.join(out, "payload_%s.vse.json" % karta), "w", encoding="utf-8"), ensure_ascii=False)
                open(os.path.join(out, "%s.vse.glb" % karta), "wb").write(raw_karty)
                vse.append(karta)
                mb = jen_multiboxy(mb_vse)
                if mb:
                    g, b = v3d_glb.read_glb(raw_karty)
                    g["scenes"][0]["extras"]["v3d"]["mbx"] = mb
                    open(os.path.join(out, fn), "wb").write(v3d_glb.write_glb(g, b))
                    spec = dict(spec, mbx=mb)
                    filtrovano.append(karta)
                else:
                    spec = None                                        # karta jen z podnosu: puvodni kontroly ji nepouziji
            pl = pl_karty(spec) if spec else None
        except Exception as e:  # noqa: BLE001 - jedna vadna karta nesmi zastavit ostatni
            preskoceno[karta] = "chyba: %s" % str(e)[:80]
            continue
        if pl is None:
            preskoceno[karta] = "bez multiboxu"
            continue
        json.dump(pl, open(os.path.join(out, "payload_%s.json" % karta), "w", encoding="utf-8"), ensure_ascii=False)
        hotovo.append(karta)
    for k in POVINNE:
        if k not in hotovo:
            sys.exit("CHYBA: karta %s nema v zakaznickem GLB multiboxy (mbx ve spec) - stavba build_karty.py je ze stare verze buildu?" % k)

    raw = open(os.path.join(FIX, "4921.offer.glb"), "rb").read()

    def vyrob(upravit):
        g, b = v3d_glb.read_glb(raw)
        upravit(g["scenes"][0]["extras"]["v3d"])
        return v3d_glb.write_glb(g, b)

    def s_mbx(lst):
        def f(spec):
            spec["mbx"] = lst
        return f

    def nombx(spec):
        spec.pop("mbx", None)

    open(os.path.join(out, "synt.glb"), "wb").write(vyrob(s_mbx(MBX)))
    open(os.path.join(out, "nombx.glb"), "wb").write(vyrob(nombx))
    pl = pl_karty({"mbx": MBX})
    json.dump(pl, open(os.path.join(out, "synt.payload.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(MBX, open(os.path.join(out, "synt.mbx.json"), "w"))
    open(os.path.join(out, "pohyby.glb"), "wb").write(vyrob(pohyby))                        # v4.1: syntetika pro api.motionIds
    json.dump(pl_karty({"mbx": POH_MBX}), open(os.path.join(out, "pohyby.payload.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # ---- supliky (v5)
    sup = suplik_mbx()
    pl_sup, zdroj_sup = payload_supliku(sup)
    open(os.path.join(out, "suplik.glb"), "wb").write(vyrob(s_mbx(sup)))
    json.dump(pl_sup, open(os.path.join(out, "suplik.payload.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(sup, open(os.path.join(out, "suplik.mbx.json"), "w"))
    piv = pivoty_modelu(raw)
    if len(piv) < 2:
        sys.exit("CHYBA: v modelu 4921 nejsou aspon dva pivoty vysuvu / supliku (motions k = slide | drawer)")
    smis = smisena_mbx(piv)
    pl_smis, zdroj_smis = payload_supliku(smis)
    open(os.path.join(out, "smisena.glb"), "wb").write(vyrob(s_mbx(smis)))
    json.dump(pl_smis, open(os.path.join(out, "smisena.payload.json"), "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(smis, open(os.path.join(out, "smisena.mbx.json"), "w"))
    json.dump(piv[:2], open(os.path.join(out, "smisena.piv.json"), "w"))
    print("KARTY " + json.dumps({"payload": hotovo, "preskoceno": preskoceno, "vse": vse, "filtrovano": filtrovano, "synt_boxu": len(pl["boxy"]), "synt_skupin": len(pl["skupiny"]), "sety": [x["id"] for x in pl["sety"]],
                                  "suplik": {"zdroj": zdroj_sup, "typy": sum(1 for t in pl_sup["typy"].values() if t.get("druh") == "suplik"), "boxu": len(pl_sup["boxy"]), "skupin": len(pl_sup["skupiny"]),
                                             "smisena_zdroj": zdroj_smis, "smisena_boxu": len(pl_smis["boxy"]), "smisena_skupin": len(pl_smis["skupiny"])}}, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("pouziti: make_glbs.py <vystupni_slozka>")
    main(sys.argv[1])
