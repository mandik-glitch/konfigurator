#!/usr/bin/env python3
"""Test HORNI POLICE MEZI ZADNIMI STOJKAMI generatoru stolu (bot8, fork 3, 2026-10-07; Robert: „pridat do generatoru ruzne typy polic mezi zadni stojky“ + rovna z laminodesky, ramova bez
desky, s lemem, ram s prekliskou / MDF v drazce, ram s prepazkami z prekliky 10 mm na uhelnicich podle stolu SSE). Bez DB (pripojeni je zakazano).

NEZAVISLE na kodu police (vse se meri z AABB dilu ve svete a z GLB v katalogu; ocekavane hodnoty jsou tady v testu jako ZADANI - viz konstanty nize):
  A) ZLATY OTISK: bez horni police je VSE beze zmeny (661 konfiguraci: hash, otisk dilu, pocet problemu, cenovy vstup) a vypnuta police s ostatnimi klici police = tentyz stul.
  B) modely v katalogu: desky 1000 x 1000 x tloustka (18 / 12 / 8 / 10 mm), uhelniky; vstup (neplatny typ / deska / vyska / hloubka = StulChyba, kombinace desky a typu, SSE police nema).
  C) MRIZKA typ x system x sirka x panely x hloubka x LED: rozmer a poloha kazdeho profilu (zadni / predni pricka mezi stojkami, boky, mezilisty podle rozponu), deska (rovna / lem
     na rame, v drazce mezi spojkami), prepazky (pocet, rozteč, vyska, uhelniky stridave), lem (poloha, uhelniky), vyska (automaticka = 60 mm nad panely, 150 mm bez nich, zaokrouhlena na 10 mm;
     zadana se ořízne), hloubka, strop (rameno LED / vrch stojek - 15 mm), pocty spojek a zaslepek, spoje == dimension_match_fbx, QA lic_peers, vlastni kontrola pruniku.
  D) nevejde se: mala vyska stojek, uzky stul, malo hluboky stul -> problem hpolice_nevejde (a pri sestav_stul automaticke odebrani), meze vysky.
  E) cena a vyroba: polozky ceny (deska = plocha, uhelniky = kusy), spojovaci material k uhelnikum, vyrobni vypis (role, popisy, montazni krok), materialy ve 3D (GLB).
  F) hash: vypnuta / nezadana vyska / ramova nema desku se do hashe nepocitaji, jinak se meni.
  G) 3D ovladani: skupina Police mezi stojkami, polozky menu a jejich dopad, verejna podoba (preklady cs / en / sk).
  H) deleni desky na vice kusu podle tabule laminodesky.
Spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-07_police_stojky/test_hpolice.py     (STUL_API_OVERRIDE=<adresar api> = kandidat)
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1."""
import hashlib
import itertools
import json
import math
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
API = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")

import numpy as np  # noqa: E402
import pymysql  # noqa: E402

for _k, _v in {"FLASK_SECRET_KEY": "selftest-secret", "DB_HOST": "selftest.invalid", "DB_PORT": "3306",
               "DB_USER": "selftest", "DB_PASSWORD": "selftest", "DB_NAME": "selftest"}.items():
    os.environ[_k] = _v


def _no_connect(*a, **kw):
    raise RuntimeError("test: pripojeni k DB zakazano")


pymysql.connect = _no_connect
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
try:
    sys.path.insert(0, API)                                              # (HERE zamerne NENI v sys.path: modul stul_hpolice musi byt ten nasazeny v API, ne zdroj ve skriptech)
    import app  # noqa: F401,E402 - jako v ostrem behu
    import dimension_match_fbx as dmf  # noqa: E402
    import qa_checks  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_ovladani_verejne as OV  # noqa: E402
finally:
    threading.Thread.start = _orig
try:
    import stul_hpolice as HP  # noqa: E402
except ImportError:
    print("CHYBA: modul api/stul_hpolice.py neexistuje (horni police neni nasazena; test patri ke kandidatu, STUL_API_OVERRIDE)")
    sys.exit(1)

OK, FAILS = 0, []


PRVNI_CHYBA = bool(os.environ.get("HPOL_PRVNI_CHYBA"))                   # mutacni testy: skonci na prvni chybe (zivy beh vypisuje vsechny)


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        if len(FAILS) <= 80:
            print(f"  CHYBA: {msg}")
        if PRVNI_CHYBA:
            sys.exit(1)


def kl(r):
    return [tuple(k) if isinstance(k, list) else k for k in r["klice"]]


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def dil(r, klic):
    return r["dily"][kl(r).index(klic)]


def hpol(r, role=None, s=None):
    """[(index, klic, dil)] dilu horni police (klic ("hpol", usek, role, ...)), volitelne jen dane role / useku, serazene podle klice."""
    out = [(i, k, r["dily"][i]) for i, k in enumerate(kl(r)) if isinstance(k, tuple) and k and k[0] == "hpol" and (role is None or k[2] == role) and (s is None or k[1] == s)]
    return sorted(out, key=lambda t: t[1])


def sestav(**cfg):
    return S.sestav_stul(**cfg)


# ---------------------------------------------------------------------------------------------------------------------
# ZADANI (ocekavane hodnoty; NEJSOU opsane z modulu - kdyz je nekdo zmeni, test to musi poznat)
# ---------------------------------------------------------------------------------------------------------------------
TL = {"lam18": 18.0, "lam12": 12.0, "mdf8": 8.0, "pr10": 10.0}                  # tloustka desky (mm) = osa Z GLB
DESKA_PART = {"lam18": "product_4933", "lam12": HP.LAM12_PART, "mdf8": "product_3939", "pr10": "product_3539"}
DRAZKA_DESKA = {30: "mdf8", 35: "mdf8", 40: "pr10", 45: "pr10"}                 # deska do drazky 8 / 10 mm
DESKY_SYSTEMU = {30: ("lam18", "lam12", "mdf8"), 35: ("lam18", "lam12", "mdf8"), 40: ("lam18", "pr10"), 45: ("lam18", "pr10")}
ZASAH = {30: 8.0, 35: 8.0, 40: 10.0, 45: 10.0}                                  # deska v drazce zasahuje do drazky o jeji sirku (SSE vzor: deska 10 mm zasahuje 10 mm)
ROZPON = {"lam18": 800.0, "lam12": 600.0, "mdf8": 400.0, "pr10": 500.0, None: 800.0}      # nejvetsi volne pole desky mezi profily (PREDPOKLAD, Robert upresni)
UHELNIK = {30: "product_3045", 35: "product_3045", 40: "product_3207", 45: "product_3207"}
PREPAZKA_PART, PREPAZKA_TL, PREPAZKA_VYSKA, ROZTEC = "product_3539", 10.0, 240.0, 260.0
LEM_VYSKA = 40.0
MEZERA_NAD_PANELY, VYSKA_BEZ_PANELU, MEZERA_POD_RAMENEM = 60.0, 150.0, 15.0     # automaticka vyska (spodek ramu) a vule pod ramenem LED
SIRKA_MIN_PLUS = 120.0                                                          # nejuzsi usek: 2 x profil + 120 mm
HLOUBKA_MIN, HLOUBKA_MAX, HLOUBKA_VYCHOZI, VYSKA_MIN = 150.0, 600.0, 300.0, 100.0
TOL = 0.06                                                                      # tolerance polohy (mm; hodnoty v hlaseni jsou zaokrouhlene na 0,1)
TYPY_VSE = ("rovna", "ram", "drazka", "lem", "prepazky")
ROLE_TYPU = {"rovna": {"zad", "pred", "bok", "mezi", "deska"}, "ram": {"zad", "pred", "bok", "mezi"}, "drazka": {"zad", "pred", "bok", "mezi", "deska"},
             "lem": {"zad", "pred", "bok", "mezi", "deska", "lem", "uhel"}, "prepazky": {"zad", "pred", "bok", "mezi", "deska", "prep", "uhel"}}
NOHA_ZL, NOHA_ZP = ("t", S.NOHA_ZL), ("t", S.NOHA_ZP)


def profil_mm(system):
    return float(S.SYSTEMY[system]["profil_mm"])


def deska_typu(typ, system, deska):
    """Deska, ktera se u typu police pouzije: ramova zadna, drazkove = deska do drazky systemu, jinak zvolena."""
    return None if typ == "ram" else (DRAZKA_DESKA[system] if typ in ("drazka", "prepazky") else deska)


# ---------------------------------------------------------------------------------------------------------------------
# A) zlaty otisk
# ---------------------------------------------------------------------------------------------------------------------
print("A) ZLATY OTISK: bez horni police je vse beze zmeny")
t0 = time.time()
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("golden_head", os.path.join(HERE, "golden_head.py"))
GH = importlib.util.module_from_spec(_spec)                              # stejne API (STUL_API_OVERRIDE), modul ze skriptu bez zasahu do sys.path
_spec.loader.exec_module(GH)
gold = json.load(open(os.path.join(HERE, "golden_head.json"), encoding="utf-8"))
nyni = GH.vypocti()
check(set(nyni) == set(gold) and len(gold) >= 600, f"A: stejna mnozina konfiguraci ({len(nyni)} vs {len(gold)})")
rozdily = [k for k in gold if nyni.get(k) != gold[k]]
if rozdily and hasattr(S, "LED_MAX"):                                   # od 2026-10-08 je pocet svitidel LED RUCNI (vychozi 1): siroke stoly maji ted jedno svitidlo; led_pocet = nejvic da PRESNE drivejsi model (hash se lisi - nese klic poctu)
    stary_pocet = GH.vypocti(navic={"led_pocet": S.LED_MAX}, jen=set(rozdily))
    rozdily = [k for k in rozdily if {x: y for x, y in stary_pocet[k].items() if x != "hash"} != {x: y for x, y in gold[k].items() if x != "hash"}]
check(not rozdily, f"A: {len(rozdily)} z {len(gold)} konfiguraci se ZMENILO oproti stavu pred horni policí (napr. {rozdily[:2]} {[(gold[k], nyni.get(k)) for k in rozdily[:1]]})")
for system in (30, 35, 40, 45):
    zakl = sestav(system=system, police=1)
    kr7 = [m["text"] for m in S.vyrobni_vypis(zakl, {})["montazni_postup"] if m["krok"] == 7]
    check(kr7 and "horní police" not in kr7[0].lower(), f"A s{system}: vychozi vypis (bez police) nezmiňuje horní polici v kroku 7")
    h0, o0 = G.kanonicky_hash(zakl["parametry"]), GH.otisk(zakl)
    for extra in ({}, dict(hpolice_typ="lem"), dict(hpolice_typ="prepazky", hpolice_vyska=500.0), dict(hpolice_hloubka=450.0), dict(hpolice_typ="ram", hpolice_deska="lam12" if system < 40 else "pr10")):
        r2 = sestav(system=system, police=1, hpolice=False, **extra)
        check(G.kanonicky_hash(r2["parametry"]) == h0 and GH.otisk(r2) == o0 and r2["hpolice_info"] is None, f"A s{system}: vypnuta police + {extra} = stul beze zmeny")
    check(not [k for k in kl(zakl) if isinstance(k, tuple) and k[0] == "hpol"], f"A s{system}: bez police zadny dil 'hpol'")
print(f"   ({time.time() - t0:.0f} s)")

# ---------------------------------------------------------------------------------------------------------------------
# B) modely v katalogu, vstup
# ---------------------------------------------------------------------------------------------------------------------
print("B) modely desek a uhelniku v katalogu, vstup")
for d, tl in TL.items():
    lo, hi = S.glb_bbox(DESKA_PART[d])
    check(np.allclose(hi - lo, [1000.0, 1000.0, tl], atol=0.02), f"B: GLB desky {d} ({DESKA_PART[d]}) je 1000 x 1000 x {tl:g} mm ({np.round(hi - lo, 3).tolist()})")
for system in (30, 35, 40, 45):
    lo, hi = S.glb_bbox(UHELNIK[system])
    ro = sorted((hi - lo).tolist())
    check(all(20.0 <= v <= 45.0 for v in ro), f"B s{system}: uhelnik {UHELNIK[system]} je maly L profil do 45 mm ({np.round(ro, 2).tolist()})")
    P = profil_mm(system)
    check(max(ro) <= P + 1e-6, f"B s{system}: sirka uhelniku {max(ro):.1f} se vejde na profil {P:g} mm")
for typ, deska, system, ok in (("rovna", "lam18", 30, True), ("rovna", "lam12", 30, True), ("rovna", "lam12", 40, False), ("rovna", "mdf8", 30, False), ("rovna", "pr10", 40, False),
                               ("lem", "lam12", 35, True), ("lem", "pr10", 40, False), ("ram", "lam12", 40, True), ("drazka", "lam18", 30, True), ("drazka", "pr10", 30, True),
                               ("prepazky", "lam12", 45, True)):
    try:
        r = sestav(system=system, hpolice=True, hpolice_typ=typ, hpolice_deska=deska)
        dobre = True
    except S.StulChyba:
        dobre = False
    check(dobre == ok, f"B: typ {typ} + deska {deska} v systemu {system}: {'prijato' if ok else 'odmitnuto'} ({'prijato' if dobre else 'StulChyba'})")
    if dobre and ok:
        ef = r["parametry"]["hpolice_deska"]
        ocek = deska_typu(typ, system, deska) or "lam18"
        check(ef == ocek, f"B: typ {typ} + deska {deska} v s{system}: ucinna deska {ef} == {ocek}")
for kw, popis in ((dict(hpolice_typ="sikma2"), "neznamy typ"), (dict(hpolice_typ=None), "typ None"), (dict(hpolice_deska="dub"), "neznama deska"), (dict(hpolice_vyska=50.0), "vyska pod 100"),
                  (dict(hpolice_vyska=1501.0), "vyska nad 1500"), (dict(hpolice_vyska=True), "vyska bool"), (dict(hpolice_vyska=float("nan")), "vyska NaN"), (dict(hpolice_vyska="500"), "vyska text"),
                  (dict(hpolice_hloubka=100.0), "hloubka pod 150"), (dict(hpolice_hloubka=601.0), "hloubka nad 600"), (dict(hpolice_hloubka=None), "hloubka None"), (dict(hpolice_hloubka=float("inf")), "hloubka inf")):
    try:
        sestav(hpolice=True, **kw)
        dobre = False
    except S.StulChyba as e:
        dobre = e.kod == "mimo_rozsah" if hasattr(e, "kod") else True
    check(dobre, f"B: neplatny vstup ({popis}) = StulChyba mimo_rozsah")
try:
    sestav(system=41, hpolice=True)
    dobre = False
except S.StulChyba:
    dobre = True
check(dobre, "B: SSE (system 41) polici nema: explicitni zapnuti = StulChyba")
r = sestav(system=41, hpolice_typ="lem", hpolice_vyska=500.0)
check(r["parametry"].get("hpolice_typ") == "rovna" and r["parametry"].get("hpolice_vyska") is None and G.kanonicky_hash(r["parametry"]) == G.kanonicky_hash(sestav(system=41)["parametry"]), "B: SSE: klice police se ignoruji i v parametrech a v hashi")
check(not [k for k in kl(r) if isinstance(k, tuple) and k[0] == "hpol"] and not r["parametry"].get("hpolice"), "B: SSE ignoruje klice police")
r = sestav(hpolice=True, hpolice_vyska=None, hpolice_hloubka=300)
check(r["parametry"]["hpolice_vyska"] is None and r["parametry"]["hpolice_hloubka"] == 300.0 and r["hpolice_info"]["vyska"]["auto"], "B: vyska None = automaticka, cele cislo hloubky se prijme")
# dotaz (staff API)
q = S.parametry_z_dotazu({"hpolice": "1", "hpolice_typ": "lem", "hpolice_deska": "lam12", "hpolice_vyska": "600", "hpolice_hloubka": "250"})
check(q.get("hpolice") is True and q.get("hpolice_typ") == "lem" and q.get("hpolice_deska") == "lam12" and q.get("hpolice_vyska") == 600.0 and q.get("hpolice_hloubka") == 250.0, f"B: dotaz ?hpolice=1&... ({ {k: v for k, v in q.items() if k.startswith('hpolice')} })")
q = S.parametry_z_dotazu({"hpolice": "1", "hpolice_vyska": ""})
check(q.get("hpolice_vyska") is None, f"B: prazdna vyska v dotazu = automaticka ({q.get('hpolice_vyska')!r})")


# ---------------------------------------------------------------------------------------------------------------------
# C) mrizka: geometrie nezavisle z AABB
# ---------------------------------------------------------------------------------------------------------------------
def profil_pary_dmf(dily):
    idxs = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS]
    meshes = []
    for i in idxs:
        lo, hi = S._aabb(dily[i])
        meshes.append({"bb_min": lo, "bb_max": hi})
    peers = dmf.compute_lic_peers(meshes)
    out = set()
    for a, js in peers.items():
        for b in js:
            out.add((min(idxs[a], idxs[b]), max(idxs[a], idxs[b])))
    return out


PROFIL_GLB = {p_: p_ + ".glb" for p_ in S.PROFIL_PARTS}


def vlastni_prunik(r, nazev, system):
    """Vlastni kontrola pruniku (nezavisle na S._zkontroluj): nic krome spojek / zaslepek se nesmi prekryvat vic nez 1 mm; deska v drazce smi zasahovat jen do bocnich / strednich profilu sve
    sekce o sirku drazky; spojky se nesmi zanorit do desek, prepazek, uhelniku ani jinych komponent."""
    dily, klice = r["dily"], kl(r)
    boxes = [bb(d) for d in dily]
    lo, hi = np.array([b[0] for b in boxes]), np.array([b[1] for b in boxes])
    pres = np.minimum(hi[:, None, :], hi[None, :, :]) - np.maximum(lo[:, None, :], lo[None, :, :])
    vnitrek = np.all(pres > 0, axis=2)
    nejm = pres.min(axis=2)
    je_spojka = np.array([d["part_id"] in S.SPOJKY_PARTS for d in dily])
    je_konec = np.array([d["part_id"] in S.KONCE_PARTS for d in dily])
    ok = True
    for a, b in zip(*np.nonzero(np.triu(vnitrek & (nejm > S.TOL_PRUNIK_MM), 1))):
        ka, kb = klice[a], klice[b]
        if (je_spojka[a] or je_konec[a]) and (je_spojka[b] or je_konec[b]):
            continue                                                   # spojky a zaslepky mezi sebou a s profily se ridi generatorem (viz napojeni nize)
        if je_spojka[a] or je_spojka[b] or je_konec[a] or je_konec[b]:
            j, c = (a, b) if (je_spojka[a] or je_konec[a]) else (b, a)
            if dily[c]["part_id"] in S.PROFIL_PARTS or str(dily[c]["part_id"]) in S.KONCE_PARTS:
                continue                                               # spojka v profilu (zasouva se) - kontroluje se u spojek nize
        # deska v drazce zasahuje do profilu sve sekce o sirku drazky
        if isinstance(ka, tuple) and ka[0] == "hpol" and ka[2] == "deska" and dily[a].get("zasazeno_do") is not None and isinstance(kb, tuple) and kb[0] == "hpol" and kb[1] == ka[1] and kb[2] in ("bok", "mezi"):
            if nejm[a, b] <= ZASAH[system] + 0.1:
                continue
        if isinstance(kb, tuple) and kb[0] == "hpol" and kb[2] == "deska" and isinstance(ka, tuple) and ka[0] == "hpol" and ka[1] == kb[1] and ka[2] in ("bok", "mezi"):
            if nejm[a, b] <= ZASAH[system] + 0.1:
                continue
        check(False, f"{nazev}: prunik {ka} x {kb} o {nejm[a, b]:.2f} mm")
        ok = False
    # spojky se nezanori do desek, prepazek, uhelniku, panelu ani jinych komponent (nic mimo profily a jine spojky)
    komp = [i for i, d in enumerate(dily) if d["part_id"] not in S.PROFIL_PARTS and not je_spojka[i] and not je_konec[i]]
    for i in np.nonzero(je_spojka)[0]:
        for c in komp:
            if vnitrek[i, c] and nejm[i, c] > S.TOL_PRUNIK_MM:
                check(False, f"{nazev}: spojka {klice[i]} se zanorila do {klice[c]} o {nejm[i, c]:.2f} mm")
                ok = False
    return ok


def over_napojeni(r, nazev):
    dily = r["dily"]
    gen = {tuple(x) for x in r["spoje"]}
    ref = profil_pary_dmf(dily)
    check(gen == ref, f"{nazev}: spoje generatoru == dimension_match_fbx ({len(gen)} vs {len(ref)}; navic {sorted(gen - ref)[:3]}, chybi {sorted(ref - gen)[:3]})")
    pairs, bad = qa_checks.lic_peers_bad_pairs(dily, PROFIL_GLB, {})
    check(not bad, f"{nazev}: QA lic_peers_neni_spoj hlasi {len(bad)} spatnych paru {bad[:3]}")
    spojene = {i for p in r["spoje"] for i in p}
    sam = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS and i not in spojene]
    check(not sam, f"{nazev}: profily bez jakehokoli spoje {sam}")
    for i, d in enumerate(dily):
        if d["part_id"] not in S.SPOJKY_PARTS:
            continue
        vl = [j for j, e in enumerate(dily) if e["part_id"] in S.PROFIL_PARTS and i in (e.get("lic_peers") or [])]
        check(len(vl) == 2, f"{nazev}: spojka #{i} ma {len(vl)} vlastniku (ma mit 2)")
        b = bb(d)
        for j in vl:
            pres = np.minimum(b[1], bb(dily[j])[1]) - np.maximum(b[0], bb(dily[j])[0])
            check(np.all(pres > 0), f"{nazev}: spojka #{i} nesedi na vlastnikovi #{j}")


def r0_mereni(r0):
    """Mereni stolu BEZ police (r0): vrch pracovni desky, vrch nejvyssi listy panelu (nebo None), strop (spodek ramene LED, jinak vrch zadnich stojek), stojky nad deskou."""
    dily, klice = r0["dily"], kl(r0)
    prac = [bb(d)[1][1] for d, k in zip(dily, klice) if k == ("t", S.DESKA_PRAC) or (d.get("deska_id") or "").startswith("prac_")]
    y_desky = float(max(prac))
    listy = [bb(d)[1][1] for d, k in zip(dily, klice) if isinstance(k, tuple) and k[0] == "panrail"]
    y_pan = float(max(listy)) if listy else None
    ramena = [bb(dil(r0, k))[0][1] for k in (("t", S.XRAIL_TOP_L), ("t", S.XRAIL_TOP_P)) if k in klice]
    if ramena:
        y_strop = float(min(ramena))
    else:
        y_strop = float(max(bb(dil(r0, NOHA_ZL))[1][1], bb(dil(r0, NOHA_ZP))[1][1]))
    return {"y_desky": y_desky, "y_pan": y_pan, "y_strop": y_strop}


def useky_mezi_stojkami(r, y_desky):
    """[(a, b)] volne useky (z) mezi zadnimi stojkami, ktere jsou stojkami nad deskou (vnitrni lica); serazene zleva doprava."""
    klice = kl(r)
    posty = []
    for k in (NOHA_ZL, "RM", NOHA_ZP):
        if k in klice:
            lo, hi = bb(dil(r, k))
            if hi[1] > y_desky + 50.0:
                posty.append((float(lo[2]), float(hi[2]), (lo, hi)))
    posty.sort()
    return [(posty[i][1], posty[i + 1][0]) for i in range(len(posty) - 1)], posty


def ocekavane_meze(typ, deska, m0, system, led_ramena=None):
    """(hv_auto, hv_min, hv_max, tl_vrch, extra) z mereni stolu bez police podle ZADANI."""
    P = profil_mm(system)
    tl_vrch = TL[deska] if (deska and typ in ("rovna", "lem")) else 0.0
    extra = PREPAZKA_VYSKA if typ == "prepazky" else (LEM_VYSKA if typ == "lem" else 0.0)
    dolni = (m0["y_pan"] + MEZERA_NAD_PANELY) if m0["y_pan"] is not None else (m0["y_desky"] + VYSKA_BEZ_PANELU)
    hv_auto = math.ceil((dolni + P + tl_vrch - m0["y_desky"]) / 10.0 - 1e-9) * 10.0
    hv_max = m0["y_strop"] - MEZERA_POD_RAMENEM - extra - m0["y_desky"]
    hv_min = max(VYSKA_MIN, hv_auto) if m0["y_pan"] is not None else VYSKA_MIN
    return hv_auto, hv_min, hv_max, tl_vrch, extra


def over_police(cfg, nazev, typ, deska_zad, hv_zad=None, hl_zad=None):
    """Postavi stul s policí (cfg + typ / deska / vyska / hloubka) a bez ni, zmeri a overi vse; vraci vysledek (nebo None, kdyz se police nevesla a byla automaticky odebrana)."""
    system = int(cfg.get("system", 30))
    P, H = profil_mm(system), profil_mm(system) / 2.0
    kw = dict(cfg, hpolice=True, hpolice_typ=typ, hpolice_deska=deska_zad)
    if hv_zad is not None:
        kw["hpolice_vyska"] = hv_zad
    if hl_zad is not None:
        kw["hpolice_hloubka"] = hl_zad
    r = sestav(**kw)
    r0 = sestav(**cfg)
    m0 = r0_mereni(r0)
    deska = deska_typu(typ, system, deska_zad)
    hv_auto, hv_min, hv_max, tl_vrch, extra = ocekavane_meze(typ, deska, m0, system)
    useky, posty = useky_mezi_stojkami(r0, m0["y_desky"])
    siroke = [i for i, (a, b) in enumerate(useky) if b - a >= 2 * P + SIRKA_MIN_PLUS - 1e-6]
    drazka = typ in ("drazka", "prepazky")
    lo_c, hi_c = S.glb_bbox(S.SYSTEMY[system]["spojka"])
    gap_c = float(max(hi_c - lo_c)) + 1.0 if drazka else 0.0
    h_min = HLOUBKA_MIN if not drazka else max(HLOUBKA_MIN, math.ceil((2 * P + 2 * gap_c + 100.0) / 10.0) * 10.0)
    x_zad = (posty[0][2][0][0] + posty[0][2][1][0]) / 2.0                        # osa zadnich stojek (x)
    x_pred = (bb(dil(r0, ("t", S.NOHA_PL)))[0][0] + bb(dil(r0, ("t", S.NOHA_PL)))[1][0]) / 2.0     # osa predni nohy
    h_max = min(HLOUBKA_MAX, (x_zad - x_pred) + P)
    odebrano = [o["volba"] for o in r["odebrano"]]
    # --- nevejde se: pak ji generator sam odebere (a v r0 mereni to potvrdi)
    fit = bool(siroke) and hv_min <= hv_max + 1e-6 and hv_auto <= hv_max + 1e-6 and h_min <= h_max + 1e-6
    if not fit:
        check(not r["parametry"]["hpolice"] and "hpolice" in odebrano, f"{nazev}: nevejde se (auto {hv_auto:g}, min {hv_min:g}, max {hv_max:g}, sirokych useku {len(siroke)}, hloubka {h_min:g}..{h_max:g}) -> police odebrana ({r['parametry']['hpolice']}, {odebrano})")
        return None
    check(r["parametry"]["hpolice"] and "hpolice" not in odebrano, f"{nazev}: vejde se -> zustane zapnuta (auto {hv_auto:g}, max {hv_max:g}; odebrano {odebrano}, problemy {[(x['kod']) for x in r['problemy']]})")
    if not r["parametry"]["hpolice"]:
        return None
    check(not r["problemy"], f"{nazev}: bez problemu ({[(x['kod'], x['text'][:70]) for x in r['problemy'][:2]]})")
    hp = r["hpolice_info"]
    check(hp and not hp["problem"] and hp["typ"] == typ, f"{nazev}: hpolice_info ({hp and (hp['typ'], hp['problem'])})")
    if not hp:
        return None
    # --- vyska
    hv_ocek = hv_auto if hv_zad is None else min(max(float(hv_zad), hv_min), max(hv_max, hv_min))
    klice = kl(r)
    frame = [d for _, k, d in hpol(r) if k[2] in ("zad", "pred", "bok", "mezi")]
    desky = hpol(r, "deska")
    y_rt = max(bb(d)[1][1] for d in frame)
    vrch = max([bb(d)[1][1] for _, _, d in desky]) if (typ in ("rovna", "lem") and desky) else y_rt
    check(abs((vrch - m0["y_desky"]) - hv_ocek) < TOL, f"{nazev}: horni plocha police {vrch - m0['y_desky']:.2f} mm nad deskou == {hv_ocek:g} (auto {hv_auto:g}, zadano {hv_zad})")
    check(abs(hp["vyska"]["hodnota"] - hv_ocek) < TOL and abs(hp["vyska"]["max"] - hv_max) < TOL and abs(hp["vyska"]["min"] - hv_min) < TOL and hp["vyska"]["auto"] == (hv_zad is None),
          f"{nazev}: hpolice_info.vyska {hp['vyska']} == hodnota {hv_ocek:g} / min {hv_min:g} / max {hv_max:g}")
    if hv_zad is None and m0["y_pan"] is not None:
        spodek = min(bb(d)[0][1] for d in frame)
        check(spodek - m0["y_pan"] >= MEZERA_NAD_PANELY - TOL, f"{nazev}: spodek ramu je aspon {MEZERA_NAD_PANELY:g} mm nad hornim profilem panelu ({spodek - m0['y_pan']:.2f})")
    if hv_zad is None and m0["y_pan"] is None:
        spodek = min(bb(d)[0][1] for d in frame)
        check(spodek - m0["y_desky"] >= VYSKA_BEZ_PANELU - TOL and spodek - m0["y_desky"] < VYSKA_BEZ_PANELU + 10.0 + TOL, f"{nazev}: bez panelu je spodek ramu 150 az 160 mm nad deskou ({spodek - m0['y_desky']:.2f})")
    nejvyssi = max(bb(d)[1][1] for _, _, d in hpol(r))
    check(nejvyssi + MEZERA_POD_RAMENEM <= m0["y_strop"] + TOL, f"{nazev}: nejvyssi dil police {nejvyssi:.1f} je aspon {MEZERA_POD_RAMENEM:g} mm pod stropem {m0['y_strop']:.1f}")
    # --- hloubka
    hl_ocek = min(max(HLOUBKA_VYCHOZI if hl_zad is None else float(hl_zad), h_min), max(h_max, h_min))
    ys = sorted({round(float((bb(d)[0][1] + bb(d)[1][1]) / 2.0), 2) for d in frame})
    check(len(ys) == 1, f"{nazev}: vsechny profily police ve stejne vysce osy ({ys})")
    check(abs(hp["hloubka"]["hodnota"] - hl_ocek) < TOL and abs(hp["hloubka"]["min"] - h_min) < TOL and abs(hp["hloubka"]["max"] - h_max) < TOL, f"{nazev}: hpolice_info.hloubka {hp['hloubka']} == {hl_ocek:g} ({h_min:g}..{h_max:g})")
    # --- sekce
    expected_s = len(siroke)
    sekce = sorted({k[1] for _, k, _ in hpol(r)})
    check(sekce == siroke and hp["sekci"] == expected_s, f"{nazev}: sekce police {sekce} == siroke useky {siroke} (info {hp['sekci']})")
    n_spojek_oc = 0
    n_zasl_oc = 0
    for s in siroke:
        a, b = useky[s]
        G_ = b - a
        zad, pred = hpol(r, "zad", s), hpol(r, "pred", s)
        check(len(zad) == 1 and len(pred) == 1, f"{nazev} s{s}: jedna zadni a jedna predni pricka")
        if not (zad and pred):
            continue
        lz, hz = bb(zad[0][2])
        lp, hp_ = bb(pred[0][2])
        post_lo, post_hi = posty[s][2][0], posty[s][2][1]
        check(abs(lz[2] - a) < TOL and abs(hz[2] - b) < TOL and abs(lp[2] - a) < TOL and abs(hp_[2] - b) < TOL, f"{nazev} s{s}: pricky leží mezi vnitrnimi lici stojek ({lz[2]:.2f}..{hz[2]:.2f} vs {a:.2f}..{b:.2f})")
        check(abs((lz[0] + hz[0]) / 2 - x_zad) < TOL and abs((hz[0] - lz[0]) - P) < TOL and abs((hz[1] - lz[1]) - P) < TOL, f"{nazev} s{s}: zadni pricka v rovine stojek, prurez {P:g}")
        check(abs((hz[0] - lp[0]) - hl_ocek) < TOL, f"{nazev} s{s}: vnejsi hloubka ramu {hz[0] - lp[0]:.2f} == {hl_ocek:g}")
        check(abs((hp_[0] - lp[0]) - P) < TOL and abs((hp_[1] - lp[1]) - P) < TOL, f"{nazev} s{s}: predni pricka ma prurez {P:g}")
        boky = hpol(r, "bok", s)
        mezi = hpol(r, "mezi", s)
        check(len(boky) == 2, f"{nazev} s{s}: dva bocni profily")
        if len(boky) == 2:
            for j, (_, k, d) in enumerate(boky):
                lo, hi = bb(d)
                zlo, zhi = (a, a + P) if j == 0 else (b - P, b)
                check(abs(lo[2] - zlo) < TOL and abs(hi[2] - zhi) < TOL, f"{nazev} s{s}: bocni profil {j} lezi na vnitrnim lici stojky ({lo[2]:.2f}..{hi[2]:.2f} vs {zlo:.2f}..{zhi:.2f})")
                check(abs(lo[0] - hp_[0]) < TOL and abs(hi[0] - lz[0]) < TOL, f"{nazev} s{s}: bocni profil {j} dosedá celem na obe pricky (x {lo[0]:.2f}..{hi[0]:.2f} vs {hp_[0]:.2f}..{lz[0]:.2f})")
                check(abs((hi[1] - lo[1]) - P) < TOL, f"{nazev} s{s}: bocni profil {j} ma vysku {P:g}")
        # mezilisty: rovnomerne, nejmensi mozny pocet podle rozponu
        roz = ROZPON[deska]
        span = (b - P) - (a + P)
        n_ocek = 0
        while (span - n_ocek * P) / (n_ocek + 1) > roz + 1e-9:                    # nejmensi pocet mezilist, pri kterem je volne pole (po odecteni profilu) nejvyse `roz`
            n_ocek += 1
        check(len(mezi) == n_ocek, f"{nazev} s{s}: {n_ocek} mezilist pro rozpon {roz:g} a volne pole {span:.1f} ({len(mezi)})")
        if mezi:
            zs = [float((bb(d)[0][2] + bb(d)[1][2]) / 2.0) for _, _, d in mezi]
            hr = [a + P] + [z - H for z in zs] + [b - P]
            hr2 = [z + H for z in zs]
            pole = [(zs[0] - H) - (a + P)] + [(zs[j + 1] - H) - (zs[j] + H) for j in range(len(zs) - 1)] + [(b - P) - (zs[-1] + H)]
            check(max(pole) - min(pole) < TOL and max(pole) <= roz + TOL, f"{nazev} s{s}: volna pole mezi profily jsou stejna a nejvyse {roz:g} ({np.round(pole, 1).tolist()})")
            check(all(abs((bb(d)[1][2] - bb(d)[0][2]) - P) < TOL and abs(bb(d)[0][0] - hp_[0]) < TOL and abs(bb(d)[1][0] - lz[0]) < TOL for _, _, d in mezi), f"{nazev} s{s}: mezilisty maji prurez {P:g} a dosedaji na pricky")
        n_mezi = len(mezi)
        # --- desky
        dk = hpol(r, "deska", s)
        if typ == "ram":
            check(not dk, f"{nazev} s{s}: ramova police nema desku")
        else:
            check(len(dk) >= 1, f"{nazev} s{s}: police ma desku")
        if typ in ("rovna", "lem") and dk:
            x_od = lp[0] if typ == "rovna" else None
            tl = TL[deska]
            dl_tab = float(S.max_delka_desky())
            kusy = sorted(dk, key=lambda t: bb(t[2])[0][2])
            check(abs(bb(kusy[0][2])[0][2] - a) < TOL and abs(bb(kusy[-1][2])[1][2] - b) < TOL, f"{nazev} s{s}: deska(y) pokryvaji useku mezi stojkami ({bb(kusy[0][2])[0][2]:.2f}..{bb(kusy[-1][2])[1][2]:.2f} vs {a:.2f}..{b:.2f})")
            check(len(kusy) == (1 if G_ <= dl_tab else math.ceil(G_ / dl_tab - 1e-9)), f"{nazev} s{s}: pocet kusu desky {len(kusy)} (usek {G_:.0f}, tabule {dl_tab:g})")
            for q, (_, kk, d) in enumerate(kusy):
                lo, hi = bb(d)
                check(d["part_id"] == DESKA_PART[deska], f"{nazev} s{s}: dil desky {d['part_id']} == {DESKA_PART[deska]}")
                check(abs((hi[1] - lo[1]) - tl) < TOL and abs(lo[1] - y_rt) < TOL, f"{nazev} s{s}: deska {tl:g} mm lezi na horním lici ramu (y {lo[1]:.2f}..{hi[1]:.2f}, rám {y_rt:.2f})")
                check(abs(hi[0] - hz[0]) < TOL, f"{nazev} s{s}: deska konci na zadnim lici ramu")
                if typ == "rovna":
                    check(abs(lo[0] - lp[0]) < TOL, f"{nazev} s{s}: rovna deska zacina na predním lici ramu")
        if typ == "lem":
            lem = sorted(hpol(r, "lem", s), key=lambda t: bb(t[2])[0][2])
            n_lem = max(1, math.ceil(G_ / 2500.0 - 1e-9))
            check(len(lem) == n_lem, f"{nazev} s{s}: {n_lem} kus(u) lemu (PR10 tabule 2500) ({len(lem)})")
            if lem:
                ll, lh = bb(lem[0][2])
                ll_all, lh_all = np.min([bb(d)[0] for _, _, d in lem], axis=0), np.max([bb(d)[1] for _, _, d in lem], axis=0)
                check(all(d["part_id"] == PREPAZKA_PART and abs((bb(d)[1][0] - bb(d)[0][0]) - PREPAZKA_TL) < TOL and abs((bb(d)[1][1] - bb(d)[0][1]) - LEM_VYSKA) < TOL and (bb(d)[1][2] - bb(d)[0][2]) <= 2500.0 + TOL for _, _, d in lem),
                      f"{nazev} s{s}: lem PR10 {PREPAZKA_TL:g} x {LEM_VYSKA:g}, kazdy kus nejvyse 2500 mm")
                check(abs((lh_all[2] - ll_all[2]) - G_) < TOL and abs(ll_all[2] - a) < TOL, f"{nazev} s{s}: kusy lemu pokryvaji celou predni hranu ({ll_all[2]:.2f}..{lh_all[2]:.2f})")
                check(abs(ll[0] - lp[0]) < TOL and abs(ll[1] - y_rt) < TOL, f"{nazev} s{s}: lem stoji na predni pricce u jejiho predniho lice")
                uh = hpol(r, "uhel", s)
                n_b = max(2, math.ceil(G_ / 450.0))
                check(len(uh) == n_b, f"{nazev} s{s}: {n_b} uhelniku lemu ({len(uh)})")
                for _, kk, d in uh:
                    ul, uhh = bb(d)
                    check(d["part_id"] == UHELNIK[system], f"{nazev} s{s}: uhelnik lemu {d['part_id']} == {UHELNIK[system]}")
                    check(abs(ul[1] - y_rt) < TOL and abs(ul[0] - lh[0]) < TOL, f"{nazev} s{s}: uhelnik lemu lezi na pricce a dosedá na zadni plochu lemu (x {ul[0]:.2f} vs {lh[0]:.2f}, y {ul[1]:.2f} vs {y_rt:.2f})")
                    check(ul[0] - lp[0] >= -TOL and ul[2] >= a - TOL and uhh[2] <= b + TOL and abs((ul[2] + uhh[2]) / 2 - (ul[2] + uhh[2]) / 2) < TOL, f"{nazev} s{s}: uhelnik lemu v rozsahu useku")
                zs = sorted(float((bb(d)[0][2] + bb(d)[1][2]) / 2.0) for _, _, d in uh)
                oc = [a + 60.0 + j * (G_ - 120.0) / (n_b - 1) for j in range(n_b)]
                check(np.allclose(zs, oc, atol=0.2), f"{nazev} s{s}: uhelniky lemu rovnomerne od 60 mm od stojek ({np.round(zs, 1).tolist()} vs {np.round(oc, 1).tolist()})")
                if dk:
                    ul_max = max(bb(d)[1][0] for _, _, d in uh)
                    check(abs(bb(dk[0][2])[0][0] - (ul_max + 1.0)) < 0.15, f"{nazev} s{s}: deska lemu zacina presne 1 mm za rameny uhelniku: {bb(dk[0][2])[0][0]:.2f} vs {ul_max:.2f}")
        if drazka and dk:
            tl = TL[deska]
            zas = ZASAH[system]
            check(len(dk) == n_mezi + 1, f"{nazev} s{s}: {n_mezi + 1} poli desky v drazce ({len(dk)})")
            hrany = [a] + [float((bb(d)[0][2] + bb(d)[1][2]) / 2.0) for _, _, d in mezi] + [b]
            dk_s = sorted(dk, key=lambda t: bb(t[2])[0][2])
            for q, (_, kk, d) in enumerate(dk_s):
                lo, hi = bb(d)
                z_l = (a + P) if q == 0 else hrany[q] + H
                z_p = (b - P) if q == len(dk_s) - 1 else hrany[q + 1] - H
                check(d["part_id"] == DESKA_PART[deska], f"{nazev} s{s}: deska v drazce {d['part_id']} == {DESKA_PART[deska]}")
                check(abs((hi[1] - lo[1]) - tl) < TOL and abs((lo[1] + hi[1]) / 2.0 - ys[0]) < TOL, f"{nazev} s{s}/{q}: deska {tl:g} mm v ose profilu (y {lo[1]:.2f}..{hi[1]:.2f}, osa {ys[0]:.2f})")
                check(abs(lo[2] - (z_l - zas)) < TOL and abs(hi[2] - (z_p + zas)) < TOL, f"{nazev} s{s}/{q}: deska zasahuje do drazek o {zas:g} mm (z {lo[2]:.2f}..{hi[2]:.2f} vs {z_l - zas:.2f}..{z_p + zas:.2f})")
                check(abs(lo[0] - (lp[0] + P + gap_c)) < TOL + 0.01 and abs(hi[0] - (lz[0] - gap_c)) < TOL + 0.01, f"{nazev} s{s}/{q}: deska konci o rameno spojky + 1 mm pred pricnymi profily (x {lo[0]:.2f}..{hi[0]:.2f} vs {lp[0] + P + gap_c:.2f}..{lz[0] - gap_c:.2f})")
        if typ == "prepazky":
            pre = hpol(r, "prep", s)
            n_p = max(0, int(round(G_ / ROZTEC)) - 1)
            check(len(pre) == n_p, f"{nazev} s{s}: {n_p} prepazek pri rozteci {ROZTEC:g} (usek {G_:.0f}) ({len(pre)})")
            uh = hpol(r, "uhel", s)
            check(len(uh) == 2 * n_p, f"{nazev} s{s}: 2 uhelniky na prepazku ({len(uh)})")
            pre_s = sorted(pre, key=lambda t: bb(t[2])[0][2])
            predni_strany = []                                                         # strana predniho uhelniku u kazde prepazky (zleva doprava): musi se STRIDAT (vzor SSE.vzor.01)
            zc = []
            for q, (_, kk, d) in enumerate(pre_s):
                lo, hi = bb(d)
                zc.append(float((lo[2] + hi[2]) / 2.0))
                check(d["part_id"] == PREPAZKA_PART and abs((hi[2] - lo[2]) - PREPAZKA_TL) < TOL and abs((hi[1] - lo[1]) - PREPAZKA_VYSKA) < TOL, f"{nazev} s{s}/{q}: prepazka PR10 {PREPAZKA_TL:g} x {PREPAZKA_VYSKA:g} ({np.round(hi - lo, 2).tolist()})")
                check(abs(lo[1] - y_rt) < TOL, f"{nazev} s{s}/{q}: prepazka stoji na hornim lici ramu")
                check(abs((hi[0] - lo[0]) - (hl_ocek - 8.0)) < TOL and abs((lo[0] + hi[0]) / 2.0 - (lp[0] + hz[0]) / 2.0) < TOL, f"{nazev} s{s}/{q}: prepazka je o 4 mm kratsi nez hloubka ramu z kazde strany a vystredena ({hi[0] - lo[0]:.2f})")
            oc = [a + (j + 1) * G_ / (n_p + 1) for j in range(n_p)]
            check(np.allclose(zc, oc, atol=0.2), f"{nazev} s{s}: prepazky rovnomerne ({np.round(zc, 1).tolist()} vs {np.round(oc, 1).tolist()})")
            for q, (_, kk, dp) in enumerate(pre_s):
                lo_p, hi_p = bb(dp)
                sousedi = [t for t in uh if abs(((bb(t[2])[0][2] + bb(t[2])[1][2]) / 2.0) - zc[q]) < 40.0]
                check(len(sousedi) == 2, f"{nazev} s{s}/{q}: 2 uhelniky u prepazky ({len(sousedi)})")
                strany = {}
                for _, ku, du in sousedi:
                    ul, uhh = bb(du)
                    check(du["part_id"] == UHELNIK[system], f"{nazev} s{s}/{q}: uhelnik {du['part_id']} == {UHELNIK[system]}")
                    check(abs(ul[1] - y_rt) < TOL, f"{nazev} s{s}/{q}: uhelnik lezi na hornim lici pricky")
                    vpred = abs(((ul[0] + uhh[0]) / 2.0) - (lp[0] + hp_[0]) / 2.0) < 1.0
                    vzad = abs(((ul[0] + uhh[0]) / 2.0) - (lz[0] + hz[0]) / 2.0) < 1.0
                    check(vpred != vzad, f"{nazev} s{s}/{q}: uhelnik je na predni nebo zadni pricce (stred x {(ul[0] + uhh[0]) / 2.0:.1f})")
                    znak = 1 if ((ul[2] + uhh[2]) / 2.0) > zc[q] else -1
                    if znak > 0:
                        check(abs(ul[2] - hi_p[2]) < TOL, f"{nazev} s{s}/{q}: uhelnik na +z strane dosedá na stenu prepazky ({ul[2]:.2f} vs {hi_p[2]:.2f})")
                    else:
                        check(abs(uhh[2] - lo_p[2]) < TOL, f"{nazev} s{s}/{q}: uhelnik na -z strane dosedá na stenu prepazky ({uhh[2]:.2f} vs {lo_p[2]:.2f})")
                    strany["pred" if vpred else "zad"] = znak
                check(set(strany) == {"pred", "zad"} and strany.get("pred") == -strany.get("zad", 0), f"{nazev} s{s}/{q}: uhelniky na protilehlych stranach prepazky u predni a zadni pricky ({strany})")
                predni_strany.append(strany.get("pred"))
                if q > 0 and q - 1 < len(pre_s):
                    pass
            check(all(predni_strany[i] == -predni_strany[i - 1] for i in range(1, len(predni_strany))), f"{nazev} s{s}: uhelniky se u dalsi prepazky stridaji ({predni_strany})")
        # --- pocty spojek a zaslepek v sekci (nic se nesmi ztratit): zadni pricka 2, bocni 2 x 2 x 1, mezilisty 2 x 2 x n
        n_spojek_oc += 2 + 2 * 2 + 4 * n_mezi
        n_zasl_oc += 2
    spojek = sum(1 for d in r["dily"] if d["part_id"] in S.SPOJKY_PARTS) - sum(1 for d in r0["dily"] if d["part_id"] in S.SPOJKY_PARTS)
    check(spojek == n_spojek_oc, f"{nazev}: spojek pribylo {spojek}, ocekavano {n_spojek_oc} (zadna se neztratila)")
    zasl = S.SYSTEMY[system]["zaslepka"]
    zaslepek = sum(1 for d in r["dily"] if d["part_id"] == zasl) - sum(1 for d in r0["dily"] if d["part_id"] == zasl)
    check(zaslepek == n_zasl_oc, f"{nazev}: zaslepek pribylo {zaslepek}, ocekavano {n_zasl_oc} (volne konce predni pricky)")
    role = {k[2] for _, k, _ in hpol(r)}
    check(role == ROLE_TYPU[typ] or (typ in ("prepazky",) and role >= ROLE_TYPU[typ] - {"prep", "uhel"}), f"{nazev}: role dilu police {sorted(role)} == {sorted(ROLE_TYPU[typ])}")
    # --- ostatni dily stolu beze zmeny proti stolu bez police (polohy, otoceni, meritko)
    kl0 = kl(r0)
    zmeneno = []
    for i0, k in enumerate(kl0):
        if k in klice:
            d0, d1 = r0["dily"][i0], dil(r, k)
            if d0["part_id"] != d1["part_id"] or not np.allclose(d0["position"], d1["position"], atol=1e-6) or not np.allclose(d0["scale"], d1["scale"], atol=1e-9):
                zmeneno.append(k)
    check(not zmeneno, f"{nazev}: ostatni dily stolu se police nezmenily ({zmeneno[:3]})")
    return r


print("C) mrizka: typ x system x sirka x panely x hloubka x LED")
t0 = time.time()
n_cfg = 0
n_odebrano = 0
for system, sirka, panely, led in itertools.product((30, 35, 40, 45), (1280, 2100, 2800), (0, 1, 2), (True, False)):
    cfg = dict(system=system, sirka=sirka, police=1)
    if panely == 0:
        cfg.update(panely=False, elektrozlab=False)
    else:
        cfg.update(panely_pocet=panely)
    if not led:
        cfg.update(led=False)
    for typ in TYPY_VSE:
        desky = [d for d in DESKY_SYSTEMU[system] if d in ("lam18", "lam12")] if typ in ("rovna", "lem") else ["lam18"]
        for deska in desky:
            for hloubka in (None, 450.0):
                if led is False and hloubka == 450.0 and typ not in ("rovna", "prepazky"):
                    continue
                nazev = f"C s{system} W{sirka} pan{panely} led{int(led)} {typ}/{deska}" + (f" h{int(hloubka)}" if hloubka else "")
                r = over_police(cfg, nazev, typ, deska, None, hloubka)
                n_cfg += 1
                if r is None:
                    n_odebrano += 1
                else:
                    over_napojeni(r, nazev)
                    vlastni_prunik(r, nazev, system)
print(f"   ({n_cfg} konfiguraci, z toho {n_odebrano} se policí odebranou protoze se nevesla, {time.time() - t0:.0f} s)")
check(n_cfg > 600 and n_odebrano < n_cfg // 2, f"C: dost konfiguraci se policí ({n_cfg}, odebrano {n_odebrano})")

print("C2) zadana vyska: stred, nejnizsi, nejvyssi, mimo meze (orizne se)")
for system, typ, panely in itertools.product((30, 40), TYPY_VSE, (0, 1)):
    cfg = dict(system=system, sirka=1500, police=1)
    if panely == 0:
        cfg.update(panely=False, elektrozlab=False)
    deska = "lam18"
    r_ = sestav(**dict(cfg, hpolice=True, hpolice_typ=typ, hpolice_deska=deska))
    if not r_["parametry"]["hpolice"]:
        check(False, f"C2 s{system} {typ} pan{panely}: police se na vychozi stul nevesla")
        continue
    v = r_["hpolice_info"]["vyska"]
    for hv in (v["min"], (v["min"] + v["max"]) / 2.0, v["max"], v["max"] + 80.0, VYSKA_MIN):
        nazev = f"C2 s{system} {typ} pan{panely} vyska {hv:g}"
        r2 = over_police(cfg, nazev, typ, deska, float(hv), None)
        if r2 is not None:
            over_napojeni(r2, nazev)
            vlastni_prunik(r2, nazev, system)

print("C3) hloubka police: nejmensi, nejvetsi, mimo meze")
for system, typ in itertools.product((30, 40), TYPY_VSE):
    cfg = dict(system=system, sirka=1500, police=1)
    for hl in (HLOUBKA_MIN, 200.0, 300.0, 400.0, HLOUBKA_MAX):
        nazev = f"C3 s{system} {typ} hloubka {hl:g}"
        r2 = over_police(cfg, nazev, typ, "lam18", None, float(hl))
        if r2 is not None:
            over_napojeni(r2, nazev)
            vlastni_prunik(r2, nazev, system)

# ---------------------------------------------------------------------------------------------------------------------
# D) nevejde se
# ---------------------------------------------------------------------------------------------------------------------
print("D) nevejde se: nizke stojky, uzky stul, maly stul; meze a automaticke odebrani")
for system, typ in itertools.product((30, 40), TYPY_VSE):
    P = profil_mm(system)
    for sv in (300.0, 500.0):
        r = sestav(system=system, stojky_vyska=sv, panely=False, elektrozlab=False, hpolice=True, hpolice_typ=typ)
        r0 = sestav(system=system, stojky_vyska=sv, panely=False, elektrozlab=False)
        m0 = r0_mereni(r0)
        hv_auto, hv_min, hv_max, _, _ = ocekavane_meze(typ, deska_typu(typ, system, "lam18"), m0, system)
        vejde = hv_auto <= hv_max + 1e-6
        check(r["parametry"]["hpolice"] == vejde, f"D s{system} {typ} stojky {sv:g}: {'zustane' if vejde else 'odebrana'} (auto {hv_auto:g} max {hv_max:g}; je zapnuta {r['parametry']['hpolice']})")
        if not vejde:
            check("hpolice" in [o["volba"] for o in r["odebrano"]] and not r["problemy"], f"D s{system} {typ} stojky {sv:g}: odebrani je v odebrano a stul je bez problemu ({[o['volba'] for o in r['odebrano']]}, {[x['kod'] for x in r['problemy']]})")
            # jadro (bez automatiky) hlasi problem
            nepouzito = S._sestav_jadro(dict(S._norm_parametry(dict(S.VYCHOZI, system=system, stojky_vyska=sv, panely=False, elektrozlab=False, hpolice=True, hpolice_typ=typ))))
            check("hpolice_nevejde" in [x["kod"] for x in nepouzito["problemy"]] and nepouzito["hpolice_info"]["problem"] == "misto", f"D s{system} {typ} stojky {sv:g}: jadro hlasi hpolice_nevejde / misto")
        # nabidka: roztazeni stojek zachrani polici
        if not vejde:
            nab = S.nabidky_roztazeni(system=system, stojky_vyska=sv, panely=False, elektrozlab=False)
            n_ = nab.get("hpolice")
            check(n_ is None or "stojky_vyska" in n_ or "sirka" in n_ or "hloubka" in n_, f"D s{system} {typ} stojky {sv:g}: nabidka roztazeni pro polici ({n_})")
            if n_ and "stojky_vyska" in n_:
                r3 = sestav(system=system, stojky_vyska=float(n_["stojky_vyska"]), panely=False, elektrozlab=False, hpolice=True, hpolice_typ=typ)
                check(r3["parametry"]["hpolice"], f"D s{system} {typ}: po nabidnutem zvyseni stojek ({n_['stojky_vyska']}) se police vejde")
    # uzky stul: usek mezi stojkami < 2P + 120
    for sirka in (500, 520, 540):
        r = sestav(system=system, sirka=sirka, panely=False, elektrozlab=False, hpolice=True, hpolice_typ=typ)
        r0 = sestav(system=system, sirka=sirka, panely=False, elektrozlab=False)
        useky, posty = useky_mezi_stojkami(r0, r0_mereni(r0)["y_desky"])
        siroke = [1 for a, b in useky if b - a >= 2 * P + SIRKA_MIN_PLUS - 1e-6]
        check(r["parametry"]["hpolice"] == bool(siroke), f"D s{system} {typ} sirka {sirka}: usek {[round(b - a, 1) for a, b in useky]} -> police {'zustane' if siroke else 'odebrana'} ({r['parametry']['hpolice']})")
# uzky usek vedle krajni nohy (stredni noha 150-350 mm od krajni): usek mezi stojkami uzsi nez 2P + 120 se preskoci, siroky usek dostane polici
for system, typ in itertools.product((30, 40), ("rovna", "lem")):
    P = profil_mm(system)
    n_uzkych = 0
    for sn in (150.0, 200.0, 250.0, 300.0, 350.0):
        cfg = dict(system=system, sirka=2100, stredni_opora="noha", stredni_noha=sn, panely=False, elektrozlab=False)
        r = sestav(**dict(cfg, hpolice=True, hpolice_typ=typ))
        r0 = sestav(**cfg)
        useky, posty = useky_mezi_stojkami(r0, r0_mereni(r0)["y_desky"])
        siroke = [(a_, b_) for a_, b_ in useky if b_ - a_ >= 2 * P + SIRKA_MIN_PLUS - 1e-6]
        n_uzkych += len(useky) - len(siroke)
        zad = sorted((bb(d_) for _, k_, d_ in hpol(r, "zad")), key=lambda t_: t_[0][2])
        check(r["parametry"]["hpolice"] == bool(siroke) and len(zad) == len(siroke), f"D3 s{system} {typ} stredni noha {sn:g}: useky {[round(b_ - a_, 1) for a_, b_ in useky]} -> police ve {len(zad)} z {len(siroke)} dost sirokych useku")
        check(all(abs(float(z_[0][2]) - a_) < 0.2 and abs(float(z_[1][2]) - b_) < 0.2 for z_, (a_, b_) in zip(zad, siroke)), f"D3 s{system} {typ} stredni noha {sn:g}: zadni pricka police presne mezi stojkami sirokeho useku")
        if r["hpolice_info"]:
            check(r["hpolice_info"]["preskoceno"] == len(useky) - len(siroke), f"D3 s{system} {typ} stredni noha {sn:g}: hpolice_info.preskoceno = {len(useky) - len(siroke)} ({r['hpolice_info']['preskoceno']})")
    check(n_uzkych >= 2, f"D3 s{system} {typ}: v testu jsou aspon 2 uzke useky ({n_uzkych})")
# malo hluboky stul pro drazkovy typ (hloubka police < nejmensi hloubka typu)
for system in (30, 40):
    r = sestav(system=system, hloubka=400.0, hpolice=True, hpolice_typ="drazka")
    P = profil_mm(system)
    inf = r["hpolice_info"]
    check(r["parametry"]["hpolice"] and inf and inf["hloubka"]["min"] > HLOUBKA_MIN, f"D s{system}: u drazkove police je nejmensi hloubka vetsi nez {HLOUBKA_MIN:g} ({inf and inf['hloubka']})")
    inf2 = sestav(system=system, hpolice=True, hpolice_typ="rovna")["hpolice_info"]
    check(inf2["hloubka"]["min"] == HLOUBKA_MIN, f"D s{system}: u rovne police je nejmensi hloubka {HLOUBKA_MIN:g} ({inf2['hloubka']['min']})")
# typy[]: vejde se / nevejde se (nezavisle na zvolenem typu)
for system in (30, 40):
    cfg = dict(system=system, stojky_vyska=500.0, panely=False, elektrozlab=False)
    r = sestav(**dict(cfg, hpolice=True, hpolice_typ="ram"))
    r0 = sestav(**cfg)
    m0 = r0_mereni(r0)
    if r["hpolice_info"] and not r["hpolice_info"]["problem"]:
        ty = {x["typ"]: x for x in r["hpolice_info"]["typy"]}
        for t in TYPY_VSE:
            hv_auto, hv_min, hv_max, _, _ = ocekavane_meze(t, deska_typu(t, system, "lam18"), m0, system)
            check(ty[t]["vejde"] == (hv_auto <= hv_max + 1e-6), f"D s{system}: typy[{t}].vejde == {hv_auto <= hv_max + 1e-6} (auto {hv_auto:g}, max {hv_max:g}; info {ty[t]})")
    check(True, "")

print("D4) _kolizi_zpusobuje_posun: RUCNE zadana vyska police je posun (kolizi zpusobenou vyskou se police sama neodebere, jen se nabidne odebrani)")
for system, typ in itertools.product((30, 40), TYPY_VSE + ("sikma",)):
    p_ruc = S._norm_parametry(dict(S.VYCHOZI, system=system, hpolice=True, hpolice_typ=typ, hpolice_vyska=500.0))
    p_aut = S._norm_parametry(dict(S.VYCHOZI, system=system, hpolice=True, hpolice_typ=typ))
    check(S._kolizi_zpusobuje_posun(p_ruc, "hpolice") is True, f"D4 s{system} {typ}: rucne zadana vyska police je posun -> kolize se nabidne odebrat (True)")
    check(S._kolizi_zpusobuje_posun(p_aut, "hpolice") is False, f"D4 s{system} {typ}: automaticka vyska + vychozi polohy = kolize neni zpusobena posunem (False)")

# ---------------------------------------------------------------------------------------------------------------------
# E) cena a vyroba
# ---------------------------------------------------------------------------------------------------------------------
print("E) cena a vyroba")
for system, typ in itertools.product((30, 35, 40, 45), TYPY_VSE):
    desky = [d for d in DESKY_SYSTEMU[system] if d in ("lam18", "lam12")] if typ in ("rovna", "lem") else ["lam18"]
    for deska in desky:
        nazev = f"E s{system} {typ}/{deska}"
        r = sestav(system=system, sirka=1500, hpolice=True, hpolice_typ=typ, hpolice_deska=deska, police=1)
        r0 = sestav(system=system, sirka=1500, police=1)
        if not r["parametry"]["hpolice"]:
            check(False, f"{nazev}: nevesla se")
            continue
        ent = S.entries_pro_cenu(r["dily"])
        ent0 = S.entries_pro_cenu(r0["dily"])
        # polozky navic = polozky police
        def pocty(e):
            c = {}
            for x in e:
                c[x["part_id"]] = c.get(x["part_id"], 0) + 1
            return c
        p1, p0 = pocty(ent), pocty(ent0)
        navic = {k: p1[k] - p0.get(k, 0) for k in p1 if p1[k] != p0.get(k, 0)}
        hp = r["hpolice_info"]
        ocek = {}
        ef = deska_typu(typ, system, deska)
        n_desek = len(hpol(r, "deska"))
        if ef:
            ocek[DESKA_PART[ef]] = ocek.get(DESKA_PART[ef], 0) + n_desek
        if typ == "prepazky":
            ocek[PREPAZKA_PART] = ocek.get(PREPAZKA_PART, 0) + hp["prepazek"]
        if typ == "lem":
            ocek[PREPAZKA_PART] = ocek.get(PREPAZKA_PART, 0) + len(hpol(r, "lem"))
        n_uh = len(hpol(r, "uhel"))
        if n_uh:
            ocek[UHELNIK[system]] = n_uh
        n_prof = sum(1 for _, k, _ in hpol(r) if k[2] in ("zad", "pred", "bok", "mezi"))
        n_spoj = sum(1 for d in r["dily"] if d["part_id"] in S.SPOJKY_PARTS) - sum(1 for d in r0["dily"] if d["part_id"] in S.SPOJKY_PARTS)
        n_zasl = sum(1 for d in r["dily"] if d["part_id"] == S.SYSTEMY[system]["zaslepka"]) - sum(1 for d in r0["dily"] if d["part_id"] == S.SYSTEMY[system]["zaslepka"])
        prof = S.SYSTEMY[system]["profil"]
        ocek[prof] = n_prof
        ocek[S.SYSTEMY[system]["spojka"]] = n_spoj
        ocek[S.SYSTEMY[system]["zaslepka"]] = n_zasl
        # polozky ceny: spojky a zaslepky maji kus = jedna polozka, profily maji delku
        check(navic == {k: v for k, v in ocek.items() if v}, f"{nazev}: polozky ceny navic {navic} == {ocek}")
        # desky: rozmer polozky = rozmer dilu v AABB (plocha), profil: delka
        for e in ent:
            if e["part_id"] in DESKA_PART.values() and "width_mm" in e and e["part_id"] != "product_4933":
                check(e["width_mm"] > 0 and e["height_mm"] > 0, f"{nazev}: polozka desky {e['part_id']} ma rozmer")
        for i, k, d in hpol(r, "deska") + hpol(r, "prep") + hpol(r, "lem"):
            lo, hi = bb(d)
            e_roz = sorted(((d["scale"][0] * 1000.0), (d["scale"][1] * 1000.0)))
            a_roz = sorted(float(v) for v in (hi - lo))[1:]                       # dva vetsi rozmery AABB (tloustka je nejmensi)
            check(np.allclose(e_roz, a_roz, atol=0.1), f"{nazev}: rozmer desky {k} z meritka {np.round(e_roz, 1).tolist()} == z AABB {np.round(a_roz, 1).tolist()}")
        # spojovaci material k uhelnikum
        sm = S.spojovaci_material(r["dily"], {})
        sm0 = S.spojovaci_material(r0["dily"], {})
        mn = lambda lst: sum(x["mnozstvi"] for x in lst)
        check(mn(sm) - mn(sm0) >= 2 * n_uh and (n_uh > 0 or mn(sm) >= mn(sm0)), f"{nazev}: spojovaci material pribyl o aspon 2 kusy na uhelnik ({mn(sm) - mn(sm0)} pro {n_uh} uhelniku)")
        sm_uh = S.spojovaci_material([d_ for d_ in r["dily"] if d_["part_id"] == UHELNIK[system]], {})
        check(n_uh == 0 or sum(x_["mnozstvi"] for x_ in sm_uh) == 2 * n_uh, f"{nazev}: spojovaci material k {n_uh} uhelnikum = {2 * n_uh} ks (1 sroub + 1 matice na uhelnik) ({[(x_['sku'], x_['mnozstvi']) for x_ in sm_uh]})")
        # vyrobni vypis: role dilu police, popisy, montazni krok
        vv = S.vyrobni_vypis(r, {})
        txt = json.dumps(vv, ensure_ascii=False)
        check("horní police" in txt, f"{nazev}: vyrobni vypis nese 'horní police'")
        prof_v = [x for x in vv["profily"] if "horní police" in x["role"]]
        check(len(prof_v) == n_prof, f"{nazev}: vyrobni vypis: {n_prof} profilu police ({len(prof_v)})")
        for x in prof_v:
            d_ = r["dily"][x["id"]]
            check(abs(x["delka_mm"] - 1000.0 * d_["scale"][1]) < 0.06, f"{nazev}: delka profilu '{x['role']}' ve vypisu {x['delka_mm']} == {1000.0 * d_['scale'][1]:.1f}")
        desk_v = [x for x in vv["desky"] if x.get("deska_id", "").startswith("hpol")]
        check(len(desk_v) == len(hpol(r, "deska")) + len(hpol(r, "prep")) + len(hpol(r, "lem")), f"{nazev}: vyrobni vypis: vsechny desky / prepazky / lem police ({len(desk_v)})")
        for x in desk_v:
            d_ = r["dily"][x["id_dilu"][0]]
            lo_, hi_ = bb(d_)
            roz_ = sorted((float(v) for v in (hi_ - lo_)))
            check(abs(x["tloustka_mm"] - roz_[0]) < 0.06 and abs(sorted((x["sirka_mm"], x["hloubka_mm"]))[0] - roz_[1]) < 0.15 and abs(sorted((x["sirka_mm"], x["hloubka_mm"]))[1] - roz_[2]) < 0.15,
                  f"{nazev}: rozmery desky '{x['role']}' ve vypisu {x['tloustka_mm']} x {x['sirka_mm']} x {x['hloubka_mm']} == AABB {np.round(roz_, 1).tolist()}")
        kroky_7 = [m["text"] for m in vv["montazni_postup"] if m["krok"] == 7]
        check(kroky_7 and "horní police" in kroky_7[0].lower(), f"{nazev}: montazni krok 7 zmiňuje horní polici ({kroky_7[0][-120:] if kroky_7 else None})")
        kroky_m = {m_["krok"]: m_ for m_ in vv["montazni_postup"]}
        prisl_i = {i_ for i_, kk_, d_ in hpol(r) if kk_[2] == "uhel"}
        prof_i = {i_ for i_, kk_, d_ in hpol(r) if kk_[2] in ("zad", "pred", "bok", "mezi")}
        check(prisl_i <= set(kroky_m[7]["dily"]) and prof_i <= set(kroky_m[1]["dily"]), f"{nazev}: uhelniky police jsou v montaznim kroku 7 a profily v kroku 1 ({sorted(prisl_i - set(kroky_m[7]['dily']))}, {sorted(prof_i - set(kroky_m[1]['dily']))})")
        vsechny_h = {i_ for i_, kk_, d_ in hpol(r)}
        cizi_kroky = {n_: sorted(vsechny_h & set(m_["dily"])) for n_, m_ in kroky_m.items() if n_ not in (1, 7) and vsechny_h & set(m_["dily"])}
        check(vsechny_h <= set(kroky_m[7]["dily"]) and not cizi_kroky, f"{nazev}: VSECHNY dily police (profily, desky, lem, prepazky, uhelniky) jsou v montaznim kroku 7 a v zadnem jinem (krok 1 = rezani) (chybi v 7: {sorted(vsechny_h - set(kroky_m[7]['dily']))}, v jinych krocich: {cizi_kroky})")
        if n_uh:
            uh_v = [x for x in vv["prislusenstvi"] if x["karta_id"] == int(UHELNIK[system].split("_")[1])]
            check(len(uh_v) == 1 and uh_v[0]["pocet"] == n_uh, f"{nazev}: prislusenstvi ve vypisu: {n_uh} x uhelnik karty {UHELNIK[system]} ({[(x['karta_id'], x['pocet']) for x in uh_v]})")
        roles = {kk: S.role_dilu(kk) for _, kk, _ in hpol(r)}
        check(all(isinstance(v, tuple) and len(v) == 2 and "horní police" in v[1] for v in roles.values()), f"{nazev}: role_dilu vsech dilu police ('horní police' v popisu)")
        for _, kk, d in hpol(r, "deska"):
            check(d.get("deska_id", "").startswith("hpol") and "horní police" in S._popis_desky(d["deska_id"]), f"{nazev}: popis desky {d.get('deska_id')} = {S._popis_desky(d.get('deska_id', ''))!r}")
        # 3D material
        ocek_mat = {DESKA_PART["lam18"]: "lamino", DESKA_PART["lam12"]: "lamino", "product_3939": "mdf", "product_3539": "preklizka", "product_3045": "seda", "product_3207": "seda"}
        for pid_ in {d["part_id"] for _, kk, d in hpol(r) if d["part_id"] not in S.PROFIL_PARTS}:
            check(G.MATERIAL_DILU.get(pid_) == ocek_mat[pid_], f"{nazev}: material dilu {pid_} v GLB = {ocek_mat[pid_]} ({G.MATERIAL_DILU.get(pid_)})")
        glb = G.poskladej_glb(r["dily"])
        check(isinstance(glb, (bytes, bytearray)) and glb[:4] == b"glTF" and len(glb) > 10000, f"{nazev}: GLB se poskladalo ({len(glb)} B)")
# dily police v neutralnim bom (verejny kusovnik) - jen nazvy, bez cisel dilu
r = sestav(system=30, hpolice=True, hpolice_typ="prepazky")
nazvy = {S._NAZVY.get(d["part_id"], "díl") for d in r["dily"]}
check(all("product_" not in n for n in nazvy), f"E: nazvy dilu bez cisel karet ({[n for n in nazvy if 'product_' in n]})")
check({"MDF deska 8 mm (police)", "překližka PR10 10 mm (police)", "úhelníková spojka 30×30"} <= nazvy, f"E: nazvy novych dilu v kusovniku ({sorted(nazvy)})")
# hmotnost lamino: vcetne police (lam18) - plocha vsech product_4933
r1 = sestav(system=30, hpolice=True, hpolice_typ="rovna")
r0 = sestav(system=30)
dp = S.plocha_lamino_m2(r1["dily"]) - S.plocha_lamino_m2(r0["dily"])
a_deska = sum(float((bb(d)[1][0] - bb(d)[0][0]) * (bb(d)[1][2] - bb(d)[0][2])) for _, _, d in hpol(r1, "deska")) / 1.0e6
check(abs(dp - a_deska) < 0.001, f"E: plocha lamino m2 vcetne police: +{dp:.4f} == plocha desky z AABB {a_deska:.4f}")

# ---------------------------------------------------------------------------------------------------------------------
# F) hash
# ---------------------------------------------------------------------------------------------------------------------
print("F) hash")
for system in (30, 40):
    zak = sestav(system=system)
    h0 = G.kanonicky_hash(zak["parametry"])
    hs = {}
    for typ in TYPY_VSE:
        r = sestav(system=system, hpolice=True, hpolice_typ=typ)
        hs[typ] = G.kanonicky_hash(r["parametry"])
        check(hs[typ] != h0, f"F s{system}: hash s policí ({typ}) se lisi od stolu bez police")
    check(len(set(hs.values())) == len(hs), f"F s{system}: kazdy typ ma jiny hash ({hs})")
    ra = sestav(system=system, hpolice=True, hpolice_typ="rovna")
    rb = sestav(system=system, hpolice=True, hpolice_typ="rovna", hpolice_vyska=ra["hpolice_info"]["vyska"]["hodnota"])
    check(G.kanonicky_hash(ra["parametry"]) != G.kanonicky_hash(rb["parametry"]), f"F s{system}: zadana vyska (i stejna jako automaticka) hash meni")
    check(G.kanonicky_hash(sestav(system=system, hpolice=True, hpolice_typ="rovna")["parametry"]) == hs["rovna"], f"F s{system}: stejny vstup = stejny hash")
    rc = sestav(system=system, hpolice=True, hpolice_typ="rovna", hpolice_hloubka=400.0)
    check(G.kanonicky_hash(rc["parametry"]) != hs["rovna"], f"F s{system}: jina hloubka police meni hash")
    d1 = sestav(system=system, hpolice=True, hpolice_typ="ram", hpolice_deska="lam18")
    d2 = sestav(system=system, hpolice=True, hpolice_typ="ram", hpolice_deska="lam12" if system < 40 else "pr10")
    check(G.kanonicky_hash(d1["parametry"]) == G.kanonicky_hash(d2["parametry"]), f"F s{system}: ramova police nema desku -> deska hash nemeni")
    d3 = sestav(system=system, hpolice=True, hpolice_typ="drazka", hpolice_deska="lam18")
    check(G.kanonicky_hash(d3["parametry"]) == hs["drazka"], f"F s{system}: drazkova police: pozadovana deska se ignoruje, hash je stejny")
    if system < 40:
        l12 = sestav(system=system, hpolice=True, hpolice_typ="rovna", hpolice_deska="lam12")
        check(G.kanonicky_hash(l12["parametry"]) != hs["rovna"], f"F s{system}: jina deska (12 mm) meni hash")
    # bez stojek / odebrana: klice policejni se nepocitaji
    rs = sestav(system=system, stojky=False, panely=False, led=False, elektrozlab=False, hpolice=True, hpolice_typ="lem")
    check(not rs["parametry"]["hpolice"] and not rs["problemy"] and "hpolice" in [o_["volba"] for o_ in rs["odebrano"]], f"F s{system}: bez zadnich stojek se police odebere a stul je bez problemu ({rs['parametry']['hpolice']}, {[x_['kod'] for x_ in rs['problemy']]})")
    check(G.kanonicky_hash(rs["parametry"]) == G.kanonicky_hash(sestav(system=system, stojky=False, panely=False, led=False, elektrozlab=False)["parametry"]), f"F s{system}: bez stojek (police odebrana) = stul bez police")

# ---------------------------------------------------------------------------------------------------------------------
# G) 3D ovladani
# ---------------------------------------------------------------------------------------------------------------------
print("G) 3D ovladani: skupina Police mezi stojkami, polozky menu, verejna podoba")
for system, typ in itertools.product((30, 40), TYPY_VSE):
    r = sestav(system=system, hpolice=True, hpolice_typ=typ)
    ov = S.ovladani_3d(r)
    cast = next((c for c in ov["casti"] if c["id"] == "hpolice"), None)
    check(cast is not None, f"G s{system} {typ}: cast 'hpolice' v 3D ovladani")
    if not cast:
        continue
    check(set(cast["param"]) >= {"hpolice", "hpolice_typ", "hpolice_deska", "hpolice_vyska", "hpolice_hloubka"} and cast["label"] == "Police mezi stojkami", f"G s{system} {typ}: parametry a popisek casti ({cast['param']}, {cast['label']})")
    # AABB casti obsahuje vsechny dily police
    lo = np.min([bb(d)[0] for _, _, d in hpol(r)], axis=0)
    hi = np.max([bb(d)[1] for _, _, d in hpol(r)], axis=0)
    check(np.all(np.array(cast["aabb"][0]) <= lo + 0.2) and np.all(np.array(cast["aabb"][1]) >= hi - 0.2), f"G s{system} {typ}: AABB casti obsahuje cele police")
    texty = [m["text"] for m in cast["menu"]]
    check(texty[0] == "Odebrat polici mezi stojkami", f"G s{system} {typ}: prvni polozka = odebrat ({texty[0]})")
    for t in TYPY_VSE:
        s_ = f"Police: {HP.NAZVY_MENU[t]}"
        check((s_ in texty) == (t != typ), f"G s{system} {typ}: nabidka typu '{s_}' {'je' if t != typ else 'neni'}")
    # kazda polozka s nastavenim se da pouzit (vysledek bez problemu a v ocekavanem stavu)
    for m in cast["menu"]:
        if m.get("zakazano") or not m.get("nastav"):
            continue
        r2 = sestav(**dict(r["parametry"], **m["nastav"]))
        if "Odebrat" in m["text"]:
            check(not r2["parametry"]["hpolice"] and not hpol(r2), f"G s{system} {typ}: '{m['text']}' odebere polici")
            continue
        check(r2["parametry"]["hpolice"] and not r2["problemy"], f"G s{system} {typ}: '{m['text']}' -> stul s policí bez problemu ({[x['kod'] for x in r2['problemy']]})")
        n = m["nastav"]
        if "hpolice_typ" in n:
            check(r2["parametry"]["hpolice_typ"] == n["hpolice_typ"], f"G s{system} {typ}: '{m['text']}' prepne typ")
        if "hpolice_deska" in n:
            check(r2["parametry"]["hpolice_deska"] == n["hpolice_deska"], f"G s{system} {typ}: '{m['text']}' prepne desku")
        if "hpolice_vyska" in n:
            v1, v0 = r2["hpolice_info"]["vyska"]["hodnota"], r["hpolice_info"]["vyska"]["hodnota"]
            check(abs(v1 - n["hpolice_vyska"]) < TOL and (v1 > v0) == ("výš" in m["text"]), f"G s{system} {typ}: '{m['text']}' posune vysku o 50 mm ({v0} -> {v1})")
        if "hpolice_hloubka" in n:
            h1, h0 = r2["hpolice_info"]["hloubka"]["hodnota"], r["hpolice_info"]["hloubka"]["hodnota"]
            check(abs(h1 - n["hpolice_hloubka"]) < TOL and (h1 > h0) == ("hlouběji" in m["text"]), f"G s{system} {typ}: '{m['text']}' zmeni hloubku o 50 mm ({h0} -> {h1})")
    # zakazane polozky maji duvod
    for m in cast["menu"]:
        check(bool(m.get("zakazano")) == (m.get("duvod") is not None), f"G s{system} {typ}: '{m['text']}' je zakazano prave kdyz ma duvod")
    # meze: nejvyssi / nejnizsi / nejmensi hloubka
    rm = sestav(system=system, hpolice=True, hpolice_typ=typ, hpolice_vyska=r["hpolice_info"]["vyska"]["max"], hpolice_hloubka=HLOUBKA_MAX)
    if rm["parametry"]["hpolice"]:
        ms = {m["text"]: m for m in next(c for c in S.ovladani_3d(rm)["casti"] if c["id"] == "hpolice")["menu"]}
        check(ms["Police o 50 mm výš"]["zakazano"] and ms["Police hlouběji (+50 mm)"]["zakazano"], f"G s{system} {typ}: na nejvyssi vysce a nejvetsi hloubce jsou 'vyš' / 'hlouběji' zakazane")
    # verejna podoba
    for lang in ("cs", "en", "sk"):
        try:
            out = OV.ovladani_verejne(ov, lang, profil_mm(system))
            c = next((c for c in out["casti"] if c["id"] == "upshelf"), None)
            check(c is not None and all(m["text"] for m in c["menu"]), f"G s{system} {typ} ({lang}): verejna cast 'upshelf' s preklady")
            if c:
                nast = [m["nastav"] for m in c["menu"] if m.get("nastav")]
                check(all(set(n) <= {"upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth"} for n in nast), f"G s{system} {typ} ({lang}): verejne nastaveni jen sloty upshelf* ({nast[:2]})")
                typy_pub = [n["upshelftype"] for n in nast if "upshelftype" in n]
                check(all(isinstance(t_, str) and t_ in HP.TYP_IDS for t_ in typy_pub), f"G s{system} {typ} ({lang}): verejna id typu ({typy_pub})")
                if lang == "en":
                    check(not [m["text"] for m in c["menu"] if any(ch in m["text"] for ch in "ěščřžýáíéúůťďň")], f"G s{system} {typ} ({lang}): anglicky preklad bez diakritiky ({[m['text'] for m in c['menu']][:2]})")
                if lang == "sk":
                    check(not [m["text"] for m in c["menu"] if any(ch in m["text"] for ch in "ěřů")], f"G s{system} {typ} ({lang}): slovensky preklad bez ceskych znaku ě ř ů ({[m['text'] for m in c['menu']][:2]})")
        except OV.ChybiPreklad as e:
            check(False, f"G s{system} {typ} ({lang}): chybi preklad: {e}")

print("G2) 3D menu: typ, ktery se nevejde, je zakazan (stojky, na ktere se vejde rovna police, ale ne prepazky / lem)")
for system in (30, 40):
    nej = next(sv for sv in range(200, 900, 10) if S.sestav_stul(system=system, stojky_vyska=float(sv), panely=False, elektrozlab=False, hpolice=True, hpolice_typ="rovna")["parametry"]["hpolice"])
    r = sestav(system=system, stojky_vyska=float(nej), panely=False, elektrozlab=False, hpolice=True, hpolice_typ="rovna")
    menu_g2 = {m_["text"]: m_ for m_ in next(c_ for c_ in S.ovladani_3d(r)["casti"] if c_["id"] == "hpolice")["menu"]}
    typy_g2 = {x_["typ"]: x_ for x_ in r["hpolice_info"]["typy"]}
    check(r["parametry"]["hpolice"] and not typy_g2["prepazky"]["vejde"], f"G2 s{system} stojky {nej}: rovna se vejde, prepazky ne ({[(t_, x_['vejde']) for t_, x_ in typy_g2.items()]})")
    for t_ in TYPY_VSE:
        if t_ != "rovna":
            m_ = menu_g2[f"Police: {HP.NAZVY_MENU[t_]}"]
            check(bool(m_.get("zakazano")) == (not typy_g2[t_]["vejde"]) and (m_.get("duvod") is not None) == (not typy_g2[t_]["vejde"]), f"G2 s{system} stojky {nej}: menu 'Police: {HP.NAZVY_MENU[t_]}' zakazano prave kdyz se nevejde ({m_.get('zakazano')}, {typy_g2[t_]['vejde']})")

# ---------------------------------------------------------------------------------------------------------------------
# H) deleni desky podle tabule
# ---------------------------------------------------------------------------------------------------------------------
print("H) tabule laminodesky: siroka deska police se deli v osach mezilist")
for system, deska in ((30, "lam18"), (30, "lam12"), (40, "lam18")):
    P = profil_mm(system)
    cfg = dict(system=system, sirka=2100, stredni_opora="ram", panely=False, elektrozlab=False, police=1)
    for tabule in ((1000.0, 1200.0), (1200.0, 1500.0)):
        S.nastav_tabuli(*tabule)
        try:
            nazev = f"H s{system} {deska} tabule {tabule[0]:g}x{tabule[1]:g}"
            r = sestav(**dict(cfg, hpolice=True, hpolice_typ="rovna", hpolice_deska=deska))
            r0 = sestav(**cfg)
            if not r["parametry"]["hpolice"]:
                check(False, f"{nazev}: police se odebrala ({[o['volba'] for o in r['odebrano']]}, {[x['kod'] for x in r['problemy']]})")
                continue
            dk = sorted(hpol(r, "deska"), key=lambda t: bb(t[2])[0][2])
            useky, _ = useky_mezi_stojkami(r0, r0_mereni(r0)["y_desky"])
            a, b = useky[0]
            dl = max(tabule)
            check(len(useky) == 1, f"{nazev}: vestaveny ram = jeden usek mezi stojkami ({len(useky)})")
            check(len(dk) >= math.ceil((b - a) / dl - 1e-9) and len(dk) <= math.ceil((b - a) / dl - 1e-9) + 1, f"{nazev}: usek {b - a:.0f} mm se deli na {len(dk)} kusu")
            check(all(float(bb(d)[1][2] - bb(d)[0][2]) <= dl + 0.2 for _, _, d in dk), f"{nazev}: kazdy kus se vejde do tabule ({[round(float(bb(d)[1][2] - bb(d)[0][2])) for _, _, d in dk]})")
            mezi = [float((bb(d)[0][2] + bb(d)[1][2]) / 2.0) for _, _, d in hpol(r, "mezi")]
            vnitrni = sorted({round(float(bb(d)[1][2]), 2) for _, _, d in dk})[:-1]
            check(all(any(abs(v - m) < 0.2 for m in mezi) for v in vnitrni), f"{nazev}: spary mezi kusy lezi v osach mezilist ({vnitrni} vs {np.round(mezi, 1).tolist()})")
            check(abs(float(bb(dk[0][2])[0][2]) - a) < TOL and abs(float(bb(dk[-1][2])[1][2]) - b) < TOL, f"{nazev}: kusy pokryvaji cely usek")
            check(not [x for x in r["problemy"] if x["kod"] == "deska_mimo_tabuli"], f"{nazev}: zadna 'deska_mimo_tabuli' ({[x['text'][:80] for x in r['problemy'] if x['kod'] == 'deska_mimo_tabuli']})")
            over_napojeni(r, nazev)
            vlastni_prunik(r, nazev, system)
            ent = [e for e in S.entries_pro_cenu(r["dily"]) if e["part_id"] == DESKA_PART[deska] and e.get("width_mm")]
            check(len(ent) >= len(dk), f"{nazev}: kazdy kus desky je polozka ceny ({len(ent)} >= {len(dk)})")
        finally:
            S.nastav_tabuli(*S.TABULE_VYCHOZI)

print("H2) nejsirsi stul (3000 mm, vestaveny ram = jeden dlouhy usek): lem se deli na kusy do 2500 mm, laminodeska na tabule 2800 mm")
for system in (30, 40):
    cfg = dict(system=system, sirka=3000, stredni_opora="ram", panely=False, elektrozlab=False, police=1)
    for typ, deska in (("lem", "lam18"), ("rovna", "lam18"), ("ram", "lam18"), ("drazka", "lam18"), ("prepazky", "lam18")):
        nazev = f"H2 s{system} W3000 {typ}"
        r = over_police(cfg, nazev, typ, deska, None, None)
        check(r is not None, f"{nazev}: police se na nejsirsi stul vejde")
        if r is not None:
            over_napojeni(r, nazev)
            vlastni_prunik(r, nazev, system)
            useky, _ = useky_mezi_stojkami(sestav(**cfg), r0_mereni(sestav(**cfg))["y_desky"])
            check(len(useky) == 1 and useky[0][1] - useky[0][0] > 2800.0, f"{nazev}: jeden usek delsi nez tabule ({[round(b - a) for a, b in useky]})")
            if typ == "lem":
                check(len(hpol(r, "lem")) == 2, f"{nazev}: lem ze dvou kusu ({len(hpol(r, 'lem'))})")
                check(len({round(float(bb(d)[1][2] - bb(d)[0][2]), 1) for _, _, d in hpol(r, "lem")}) == 1, f"{nazev}: oba kusy lemu jsou stejne dlouhe")
                check([S._popis_desky(d["deska_id"]) for _, _, d in hpol(r, "lem")] == ["lem horní police", "lem horní police (kus 2)"], f"{nazev}: popisy kusu lemu ({[S._popis_desky(d['deska_id']) for _, _, d in hpol(r, 'lem')]})")
            if typ == "rovna":
                check(len(hpol(r, "deska")) == 2, f"{nazev}: laminodeska police ze dvou kusu (tabule 2800) ({len(hpol(r, 'deska'))})")
                kusy_h2 = sorted(hpol(r, "deska"), key=lambda t: bb(t[2])[0][2])
                useky_h2, _p2 = useky_mezi_stojkami(sestav(**cfg), r0_mereni(sestav(**cfg))["y_desky"])
                mids_h2 = sorted(float((bb(d_)[0][2] + bb(d_)[1][2]) / 2.0) for _, _, d_ in hpol(r, "mezi"))
                ocek_rez = max(z_ for z_ in mids_h2 if z_ - useky_h2[0][0] <= float(S.max_delka_desky()) + 1e-6)
                check(abs(float(bb(kusy_h2[0][2])[1][2]) - ocek_rez) < 0.2, f"{nazev}: prvni kus desky konci v NEJVZDALENEJSIM strednim profilu, do ktereho se jeste vejde (tabule {S.max_delka_desky():g}): {float(bb(kusy_h2[0][2])[1][2]):.1f} vs {ocek_rez:.1f}")

if FAILS:
    import re
    kat = {}
    for f_ in FAILS:                                   # souhrn: stejny typ chyby (bez cisel a konfigurace) jednou s poctem a prikladem
        klic = re.sub(r"[0-9.\-]+", "#", f_.split(": ", 1)[1] if ": " in f_ else f_)[:110]
        kat.setdefault(klic, [0, f_])[0] += 1
    print("\nSOUHRN CHYB (typ: pocet, priklad):")
    for k_, (n_, ex) in sorted(kat.items(), key=lambda t: -t[1][0])[:25]:
        print(f"  {n_:5d} x  {ex[:230]}")
print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
