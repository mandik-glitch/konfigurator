#!/usr/bin/env python3
"""Test JADRA generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08): normalizace a meze, vychozi konfigurace (pocty dilu odvozene RUCNE nezavisle na kodu), pravidlo polohy rohove spojky proti SABLONE STOLU,
geometricke invarianty na mrizce konfiguraci (zadne zanoreni profilu, bloky spojek mimo profily a vyplne, vyplne ve stredove rovine a zasunuta max do drazky, kusy vyplne = obdelnik minus vyrezy), dvere
(vule, zavesy na strane zavesu, zamek na protejsi), symetrie, kusovnik a entries, hash, GLB (nacitatelne, obalka, prusvitne uzly), cena s virtualnimi deskami.
Hermeticky (bez DB, GLB cast pres fake prostredi), spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-08_oploceni/test_oploceni.py
(moduly jsou v api/: OPLOCENI_API / STUL_API_OVERRIDE = jiny adresar api/, napr. kandidatni strom faze 2)"""
import itertools
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
API = os.environ.get("OPLOCENI_API") or os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")           # api/: zivy, kandidatni strom, nebo kopie s mutaci (mutace_oploceni.py)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-07_police_bez_desky"))
import oploceni_konfigurator as O  # noqa: E402
assert os.path.abspath(O.__file__).startswith(os.path.abspath(API)), O.__file__

OK, FAILS = 0, []


def check(cond, msg, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg} {detail}")
        if os.environ.get("OPLOCENI_STOP_PRVNI"):                       # mutacni beh: staci prvni selhani (mutace je chycena), neztraci se cas zbytkem testu
            sys.exit(1)


def prekryv(a, b):
    return np.minimum(a[1], b[1]) - np.maximum(a[0], b[0])


def profily(r):
    return [d for d in r["dily"] if d["druh"] == "profil"]


def blok_spojky(d):
    """Svetova obalka BLOKU spojky (lokalni x 0..37, y -37..0, z 0..37) a cele spojky vcetne nozek (obalka dilu)."""
    R = O.kvat_na_matici(d["quaternion"])
    pos = np.array(d["position"], float)
    rohy = np.array([pos + R @ np.array([lx, ly, lz]) for lx in (0.0, O.BLOK) for ly in (-O.BLOK, 0.0) for lz in (0.0, O.BLOK)])
    return rohy.min(axis=0), rohy.max(axis=0)


def kusy_aabb(v):
    e1, e2, n = np.array(v["e1"]), np.array(v["e2"]), np.array(v["n"])
    t = O.VYPLNE[v["typ"]]["tloustka"]
    out = []
    for k in v["kusy"]:
        pol = np.abs(e1) * k["e1"] / 2.0 + np.abs(e2) * k["e2"] / 2.0 + np.abs(n) * t / 2.0
        c = np.array(k["stred"], float)
        out.append((c - pol, c + pol))
    return out


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("A) normalizace, meze, chyby")
p = O.normalizuj()
check(p == dict(O.VYCHOZI) or all(p[k] == O.VYCHOZI[k] for k in O.VYCHOZI), "vychozi parametry")
check(O.normalizuj(**p) == p, "normalizace je idempotentni")
check(p["dvere_vyska"] is None and p["celo"] == "dvere" and p["strecha"] == "vyplne" and p["vyplne"] == "pc_cira", "vychozi: dvere vpredu, strecha s vyplni, cira vyplne")
for popis, kw, kod in [("sirka pod mezi", dict(sirka=599), "mimo_rozsah"), ("sirka nad mezi", dict(sirka=6001), "mimo_rozsah"), ("hloubka pod mezi", dict(hloubka=599.9), "mimo_rozsah"),
                       ("vyska pod mezi", dict(vyska=999), "mimo_rozsah"), ("vyska nad mezi", dict(vyska=3001), "mimo_rozsah"), ("sirka text", dict(sirka="abc"), "neplatny_vstup"),
                       ("sirka NaN", dict(sirka=float("nan")), "neplatny_vstup"), ("sirka bool", dict(sirka=True), "neplatny_vstup"), ("neznamy parametr", dict(neco=1), "neznamy_parametr"),
                       ("strana neznama hodnota", dict(celo="okno"), "mimo_rozsah"), ("strecha neznama", dict(strecha="sedlova"), "mimo_rozsah"), ("vyplne neznama", dict(vyplne="sklo"), "mimo_rozsah"),
                       ("vyplne strany neznama", dict(vyplne_leva="x"), "mimo_rozsah"), ("poloha dveri", dict(dvere_poloha="nahoru"), "mimo_rozsah"), ("zavesy", dict(dvere_zavesy="stred"), "mimo_rozsah"),
                       ("zamek", dict(zamek="klika"), "mimo_rozsah"), ("patky ne bool", dict(patky="ano"), "neplatny_vstup"), ("dvere uzke", dict(dvere_sirka=599), "mimo_rozsah"),
                       ("dvere siroke", dict(dvere_sirka=1201), "mimo_rozsah"), ("dvere nizke", dict(dvere_vyska=1499), "mimo_rozsah"),
                       ("vse otevrene bez strechy", dict(celo="otevreno", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna"), "prazdne")]:
    try:
        O.sestav_oploceni(**kw)
        check(False, f"{popis}: musi byt OploceniChyba")
    except O.OploceniChyba as e:
        check(e.kod == kod, f"{popis}: kod {kod}", f"(je {e.kod}: {e})")
for popis, kw in [("minimum", dict(sirka=600, hloubka=600, vyska=1000, celo="stena")), ("maximum", dict(sirka=6000, hloubka=6000, vyska=3000))]:
    r = O.sestav_oploceni(**kw)
    check(len(r["dily"]) > 10, f"mezni rozmer {popis} projde")
for popis, kw, kod in [("dvere v nizke stene", dict(vyska=1700), "dvere_nevejdou"), ("dvere sirsi nez stena", dict(sirka=900, dvere_sirka=1000), "dvere_nevejdou"),
                       ("uzke pole u dveri", dict(sirka=1050, dvere_sirka=800), "stena_uzka"), ("dvere_vyska nad mezi nadprazi", dict(dvere_vyska=2300), "dvere_nevejdou")]:
    try:
        O.sestav_oploceni(**kw)
        check(False, f"{popis}: musi byt chyba")
    except O.OploceniChyba as e:
        check(e.kod == kod, f"{popis}: kod {kod}", f"(je {e.kod}: {e})")
nd = O.normalizuj(celo="stena", dvere_sirka=1000, dvere_vyska=1800, dvere_poloha="vlevo", dvere_zavesy="vlevo", zamek="zamek")
check((nd["dvere_sirka"], nd["dvere_vyska"], nd["dvere_poloha"], nd["dvere_zavesy"], nd["zamek"]) == (800.0, None, "vpravo", "vpravo", "zapadka"), "bez dveri se VSECHNY parametry dveri vraci na vychozi (jedna kanonicka podoba)", nd)
check(O.normalizuj(sirka=1500.04)["sirka"] == 1500.0 and O.normalizuj(sirka=1500.26)["sirka"] == 1500.3 and O.normalizuj(sirka="1500,0".replace(",", "."))["sirka"] == 1500.0, "rozmery se zaokrouhluji na 0,1 mm (jeden rozmer = jeden hash)")
try:
    O.sestav_oploceni(vyska=1050, patky=True, celo="stena")
    check(False, "vyska 1050 s patkami (konstrukce 971 mm) musi byt chyba")
except O.OploceniChyba as e:
    check(e.kod == "mimo_rozsah", "vyska 1050 s patkami: konstrukce jen 971 mm < 1000 = chyba mimo_rozsah", f"(je {e.kod})")
check(len(O.sestav_oploceni(vyska=1079, patky=True, celo="stena")["dily"]) > 10, "vyska 1079 s patkami: konstrukce presne 1000 mm projde")
check(O.normalizuj(prava="otevreno", vyplne_prava="plexi")["vyplne_prava"] is None, "volba vyplne strany bez steny se zahodi")
check(O.normalizuj(strecha="ram", vyplne_strecha="sit")["vyplne_strecha"] is None, "volba vyplne strechy bez vyplne strechy se zahodi")
for popis, kw, klic in [("jen celo", dict(celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna"), "hloubka"),
                        ("jen zadni", dict(celo="otevreno", prava="otevreno", zadni="stena", leva="otevreno", strecha="zadna"), "hloubka"),
                        ("jen prava", dict(celo="otevreno", prava="stena", zadni="otevreno", leva="otevreno", strecha="zadna"), "sirka"),
                        ("jen leva", dict(celo="otevreno", prava="otevreno", zadni="otevreno", leva="stena", strecha="zadna"), "sirka")]:
    a_, b_ = O.normalizuj(**kw, **{klic: 1000}), O.normalizuj(**kw, **{klic: 2000})
    check(a_ == b_ and a_[klic] == O.VYCHOZI[klic], f"{popis} bez strechy: rozmer kolmy na stenu ({klic}) nema vliv - jedna kanonicka podoba")
    check(O.sestav_oploceni(**kw, **{klic: 1000})["hash"] == O.sestav_oploceni(**kw, **{klic: 2000})["hash"], f"{popis}: stejny hash")
for popis, kw in [("celo + zadni (dve rovnobezne)", dict(celo="stena", prava="otevreno", zadni="stena", leva="otevreno", strecha="zadna")), ("celo + prava (L)", dict(celo="stena", prava="stena", zadni="otevreno", leva="otevreno", strecha="zadna")),
                  ("jen celo, ale se strechou", dict(celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="ram"))]:
    check(O.normalizuj(**kw, hloubka=1000, sirka=3000)["hloubka"] == 1000.0 and O.normalizuj(**kw, hloubka=1000, sirka=3000)["sirka"] == 3000.0, f"{popis}: oba rozmery se zachovaji")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("B) vychozi konfigurace (1500 x 1500 x 2200, dvere vpredu vpravo 800, strecha s vyplni): pocty odvozene rucne")
r = O.sestav_oploceni()
pr = profily(r)
role_n = lambda t: sum(1 for d in pr if d["role"].startswith(t))
dh = 2200 - 40 - 43 - 150 - 5                                    # = 1962: nadpraz zustane aspon 150 mm
check(abs(r["dvere"][0]["vyska_kridla"] - dh) < 1e-6, f"vyska kridla = {dh} mm (nadpraz aspon 150 mm; menší než 2000)")
check(role_n("rohový sloupek") == 4 and role_n("mezilehlý sloupek") == 4, "4 rohove + 4 mezilehle sloupky (po jednom na zadni / leve / prave strane a u dveri)")
check(all(abs(d["delka"] - 2200) < 1e-6 for d in pr if d["role"].startswith("rohový")) and all(abs(d["delka"] - 2160) < 1e-6 for d in pr if d["role"].startswith("mezilehlý")),
      "rohove sloupky maji celou vysku 2200, mezilehle koncí pod hornipricku (2200 - 40 = 2160)")
check(role_n("stojka křídla") == 2 and all(abs(d["delka"] - dh) < 1e-6 for d in pr if d["role"].startswith("stojka křídla")), "2 stojky kridla delky vyska dveri")
check(role_n("horní příčka (") == 4 and all(abs(d["delka"] - 1420) < 1e-6 for d in pr if d["role"].startswith("horní příčka (")), "4 souvisle horni pricky (po jedne na stranu, pres pole i dvere) delky 1420")
check(role_n("dolní příčka (") == 7 and role_n("mezipříčka (") == 7, "7 dolnich pricek a 7 mezipricek v polich (dvere nemaji dolni prícku)")
check(role_n("nadpraží") == 1 and role_n("horní příčka křídla") == 1 and role_n("dolní příčka křídla") == 1 and role_n("mezipříčka křídla") == 1, "nadpraží + horní, dolní a mezipříčka křídla (vyska krídla 1962 > 1100 + 80)")
check(role_n("střešní příčka") == 3 and sorted(round(d["delka"]) for d in pr if d["role"].startswith("střešní")) == [690, 690, 1420], "strecha: 1 pricka 1420 a 2 x 690 (mrizka 2 x 2)")
check(len(pr) == 35, "celkem 35 profilu", len(pr))
spojky = [d for d in r["dily"] if d["druh"] == "spojka"]
check(len(spojky) == 80 and r["pocet_spoju"] == 54, "80 spojek (L-roh 1, T-spoj 2) a 54 spoju (8 + 4 u hornich pricek, 14 + 14 u dolnich a mezipricek, 2 nadpraz, 6 kridlo, 6 strecha)", (len(spojky), r["pocet_spoju"]))
check(sum(1 for d in r["dily"] if d["druh"] == "zaslepka") == 16, "16 zaslepek (4 rohove sloupky nahore i dole = 8, 4 mezilehle dole, 2 stojky kridla x 2 = 4)")
check(sum(1 for d in r["dily"] if d["druh"] == "pant") == 3 and all(d["part_id"] == O.PANT_PRAVY for d in r["dily"] if d["druh"] == "pant"), "3 zavesy 'pravy' (zavesy vpravo)")
check(sum(1 for d in r["dily"] if d["druh"] == "zamek") == 1 and sum(1 for d in r["dily"] if d["druh"] == "patka") == 0, "1 zapadka, bez patek")
check(len(r["vyplne"]) == 21, "21 poli vyplne (4 steny po 2-5, nadpraz, 2 pole kridla, strecha 4)", len(r["vyplne"]))
roz = sorted((v["rozmer_tabule"], v["vyrezy"]) for v in r["vyplne"])
check(((592.0, 1058.0), 4) in roz and ((708.0, 1058.0), 4) in roz and ((708.0, 708.0), 3) in roz and ((824.0, 168.0), 4) in roz and ((738.0, 939.0), 4) in roz, "rozmery tabuli (otvor + 2 x 9 mm) a pocty vyrezu v rozich")
check(r["hash"] == "860d0d3df313be62", "hash vychozi konfigurace (golden)", r["hash"])
check(len(r["dily"]) == 135, "vychozi konfigurace ma 135 dilu (35 profilu + 80 spojek + 16 zaslepek + 3 zavesy + 1 zapadka)", len(r["dily"]))
check(abs(r["kusovnik"]["profily_celkem_mm"] - sum(d["delka"] for d in pr)) < 0.1 and r["kusovnik"]["profily_ks"] == 35, "kusovnik: soucet delek a pocet profilu")
check(abs(r["kusovnik"]["profily_celkem_mm"] - (4 * 2200 + 4 * 2160 + 2 * 1962 + 4 * 1420 + 1420 + 2 * 690 + 806 + 3 * 720 + 6 * 690 + 6 * 690 + 574 + 574)) < 0.1, "kusovnik: soucet delek profilu rucne (hodnoty z navrhu steny)", r["kusovnik"]["profily_celkem_mm"])
check(abs(sum(t["mnozstvi"] for t in r["kusovnik"]["tesneni"]) - sum(2 * (v["w"] + v["h"]) / 1000 for v in r["vyplne"])) < 0.01, "tesneni = obvod vsech otvoru")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("C) pravidlo polohy rohove spojky proti SABLONE STOLU (system 40: spojky 30, 31, 32 - poloha a kvaternion z api/stul_sablona_system40.json)")
S0 = O._Sestava(O.normalizuj())
d31 = S0.spojka(np.array([-101.48, 325.2, -402.4]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), "sablona 31")
check(np.allclose(d31["position"], [-101.48, 382.2, -420.9], atol=0.05) and np.allclose(d31["quaternion"], [0, 0, 0, 1], atol=1e-6), "spojka 31 (nad pricku, roh nahoru): poloha i kvaternion", (d31["position"], d31["quaternion"]))
d32 = S0.spojka(np.array([-101.48, 801.5, -402.4]), np.array([1.0, 0, 0]), np.array([0, -1.0, 0]), "sablona 32")
check(np.allclose(d32["position"], [-101.48, 744.5, -383.9], atol=0.05) and np.allclose(np.abs(d32["quaternion"]), [1, 0, 0, 0], atol=1e-6), "spojka 32 (pod pricku): poloha i kvaternion", (d32["position"], d32["quaternion"]))
d30 = S0.spojka(np.array([-121.48, 801.5, -382.4]), np.array([0, 0, 1.0]), np.array([0, -1.0, 0]), "sablona 30")
q30 = np.array(d30["quaternion"])
check(np.allclose(d30["position"], [-140.0, 744.5, -382.4], atol=0.05) and np.allclose(np.abs(q30), [0.7071068, 0, 0.7071068, 0], atol=1e-5), "spojka 30 (pricka ve smeru +Z): poloha i kvaternion", (d30["position"], d30["quaternion"]))
for d in (d31, d32, d30):
    R = O.kvat_na_matici(d["quaternion"])
    check(abs(np.linalg.det(R) - 1) < 1e-6 and np.allclose(R @ R.T, np.eye(3), atol=1e-6), "rotace spojky je vlastni (det +1, ortonormalni)", float(np.linalg.det(R)))

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("D) geometricke invarianty na mrizce konfiguraci")
MRIZKA = []
for (sx, hl, vy), strany in itertools.product([(600, 600, 1000), (900, 900, 1800), (1200, 1200, 1600), (1500, 1500, 2200), (2000, 2000, 2400), (2400, 1200, 2000), (3000, 3000, 2500), (3600, 2400, 2800),
                                               (6000, 1800, 3000), (1000, 4000, 2100), (1250, 1250, 1750)],
                                              [dict(), dict(celo="stena"), dict(celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno"), dict(celo="stena", prava="otevreno", zadni="otevreno"),
                                               dict(celo="dvere", prava="dvere", dvere_poloha="stred"), dict(celo="dvere", zadni="dvere", dvere_poloha="vlevo", dvere_zavesy="vlevo", zamek="zamek"),
                                               dict(celo="stena", prava="stena", zadni="stena", leva="stena", strecha="ram"), dict(strecha="zadna", patky=True),
                                               dict(celo="dvere", dvere_poloha="vlevo", dvere_sirka=1000, vyplne="plexi", vyplne_leva="sit", patky=True), dict(celo="dvere", dvere_vyska=1500, dvere_sirka=700, dvere_poloha="stred")]):
    kw = dict(sirka=sx, hloubka=hl, vyska=vy, **strany)
    try:
        O.normalizuj(**kw)
        O.sestav_oploceni(**kw)
    except O.OploceniChyba:
        continue                                                    # neproveditelne kombinace (dvere ve strane / vysce, ktere se nevejdou) sem nepatri - testuji se v A
    MRIZKA.append(kw)
check(len(MRIZKA) >= 60, f"mrizka ma dost proveditelnych konfiguraci ({len(MRIZKA)})")
chyby = {"prunik_profilu": [], "blok_v_profilu": [], "bloky": [], "spojka_nedotyka": [], "vyplna_v_bloku": [], "vyplna_rovina": [], "vyplna_hloubka": [], "profil_rozmer": [], "kusy_plocha": [], "kusy_prekryv": [],
         "mimo_obrys": [], "rozpeti": [], "rohy_bez_spojky": []}


def pole_boxu(boxy):
    if not boxy:
        return np.zeros((0, 3)), np.zeros((0, 3))
    return np.array([b[0] for b in boxy]), np.array([b[1] for b in boxy])


def ovm(A, B):
    """Prekryv (m x n x 3) vsech dvojic obalek A (lo, hi pole) a B."""
    return np.minimum(A[1][:, None, :], B[1][None, :, :]) - np.maximum(A[0][:, None, :], B[0][None, :, :])


for kw in MRIZKA:
    r = O.sestav_oploceni(**kw)
    pr = profily(r)
    P = pole_boxu([O.aabb(d) for d in pr])
    M = np.triu(np.all(ovm(P, P) > 1.0, axis=2), 1)
    for i, j in np.argwhere(M):
        chyby["prunik_profilu"].append((kw, pr[i]["role"], pr[j]["role"]))
    ext = np.sort(P[1] - P[0], axis=1)
    dl = np.array([d["delka"] for d in pr])
    for i in np.argwhere(~((np.abs(ext[:, 0] - 40) < 0.01) & (np.abs(ext[:, 1] - 40) < 0.01) & (np.abs(ext[:, 2] - dl) < 0.01))).ravel():
        chyby["profil_rozmer"].append((kw, pr[i]["role"], ext[i].tolist()))
    sp = [d for d in r["dily"] if d["druh"] == "spojka"]
    BL = pole_boxu([blok_spojky(d) for d in sp])
    CA = pole_boxu([O.aabb(d) for d in sp])
    for k in np.argwhere(np.all(ovm(BL, P) > 0.5, axis=2).any(axis=1)).ravel():
        chyby["blok_v_profilu"].append((kw, sp[k]["role"]))
    dotyk = np.all(ovm((CA[0] - 0.5, CA[1] + 0.5), P) > 0, axis=2).sum(axis=1)
    for k in np.argwhere(dotyk < 2).ravel():
        chyby["spojka_nedotyka"].append((kw, sp[k]["role"], int(dotyk[k])))
    for k, l in np.argwhere(np.triu(np.all(ovm(BL, BL) > 0.5, axis=2), 1)):
        chyby["bloky"].append((kw, sp[k]["role"], sp[l]["role"]))
    kusy, kn, pid = [], [], []                                                       # vsechny kusy vyplni: obalka, osa normaly pole, cislo pole
    for n_pole, v in enumerate(r["vyplne"]):
        for a in kusy_aabb(v):
            kusy.append(a)
            kn.append(int(np.argmax(np.abs(np.array(v["n"])))))
            pid.append(n_pole)
        dv = r["parametry"]["dvere_sirka"]
        if v["strana"] == "strecha":
            ok_rozpeti = v["w"] <= 1200.0001 and v["h"] <= 1200.0001
        elif v["role"].startswith("výplň nadpraží"):
            ok_rozpeti = abs(v["w"] - (dv + 6.0)) < 0.01 and v["h"] <= 1100.0001                 # pole nad dvermi = sirka dveri + 2 x 3 mm vule
        elif v["role"].startswith("výplň křídla"):
            ok_rozpeti = abs(v["w"] - (dv - 80.0)) < 0.01 and v["h"] <= 1100.0001                # vyplne krídla = sirka krídla - 2 stojky
        else:
            ok_rozpeti = v["w"] <= 1200.0001 and v["h"] <= 1100.0001 and v["w"] >= 150.0 and v["h"] >= 150.0
        if not ok_rozpeti:
            chyby["rozpeti"].append((kw, v["role"], v["w"], v["h"]))
        # kazdy roh pole vyplne je bud u rohoveho sloupku (jen strecha: maly vyrez), nebo v nem lezi blok spojky (velky vyrez): stena = 4 velke vyrezy, strecha = velke + male = 4
        if v["vyrezy_vsechny"] != 4 or v["vyrezy"] + len(v["male_rohy"]) != 4:
            chyby["rohy_bez_spojky"].append((kw, v["role"], v["vyrezy"], len(v["male_rohy"])))
        w2, h2 = v["w"] + 2 * O.INS, v["h"] + 2 * O.INS
        # plocha = obdelnik - vyrezy (kazdy roh jeho strana): rohy s blokem VYREZ x VYREZ, rohy u sloupku (strecha) (INS + 0,5)^2
        ocek = w2 * h2 - v["vyrezy"] * O.VYREZ ** 2 - (v["vyrezy_vsechny"] - v["vyrezy"]) * (O.INS + 0.5) ** 2
        plocha = sum(k["e1"] * k["e2"] for k in v["kusy"])
        if abs(plocha - ocek) > 0.5:
            chyby["kusy_plocha"].append((kw, v["role"], plocha, ocek))
    K = pole_boxu(kusy)
    kn, pid = np.array(kn), np.array(pid)
    for k in np.argwhere(np.all(ovm(K, BL) > 0.5, axis=2).any(axis=1)).ravel():
        chyby["vyplna_v_bloku"].append((kw, r["vyplne"][pid[k]]["role"]))
    OV = ovm(K, P)
    uvnitr = np.all(OV > 0.01, axis=2)
    Kc, Pc = (K[0] + K[1]) / 2.0, (P[0] + P[1]) / 2.0
    dc = np.abs(Kc[np.arange(len(K[0])), kn][:, None] - Pc[:, kn].T)                 # vzdalenost stredovych rovin kusu a profilu podel normaly pole
    for k, i in np.argwhere(uvnitr & (dc > 0.01)):
        chyby["vyplna_rovina"].append((kw, r["vyplne"][pid[k]]["role"], pr[i]["role"]))
    osa_ne = np.arange(3)[None, :] != kn[:, None]                                      # (kusu, 3): osy rovnobezne s polem
    hl = np.where(osa_ne[:, None, :], OV, np.inf).min(axis=2)
    for k, i in np.argwhere(uvnitr & (hl > O.INS + 0.01)):
        chyby["vyplna_hloubka"].append((kw, r["vyplne"][pid[k]]["role"], pr[i]["role"], np.round(OV[k, i], 2).tolist()))
    stejne = pid[:, None] == pid[None, :]
    for k, l in np.argwhere(np.triu(np.all(ovm(K, K) > 0.001, axis=2) & stejne, 1)):
        chyby["kusy_prekryv"].append((kw, r["vyplne"][pid[k]]["role"]))
    lo_o, hi_o = P[0].min(axis=0), P[1].max(axis=0)
    if not (abs(lo_o[0]) < 0.01 and abs(lo_o[2]) < 0.01 and abs(hi_o[0] - kw["sirka"]) < 0.01 and abs(hi_o[2] - kw["hloubka"]) < 0.01 and abs(hi_o[1] - kw["vyska"]) < 0.01):
        chyby["mimo_obrys"].append((kw, lo_o.tolist(), hi_o.tolist()))
for k, v in chyby.items():
    check(not v, f"{k}: bez poruseni na {len(MRIZKA)} konfiguracich", str(v[:2]))

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("E) dvere: vule, zavesy na strane zavesu, zamek na protejsi strane, rozlozeni steny")


def zamek_na_plose(r, dil, stojky, info, popis, rozmery, osy):
    """Zamek / zapadka lezi PLOSNE na vnejsi plose stojky: dosedaci plocha = plocha profilu, tloustka (osa `osy[1]` dilu), svisly rozmer (osa `osy[0]`), vodorovny (`osy[2]`), vystredeno na stojce
    a na vysce min(1000, vyska kridla / 2) nad spodkem kridla. `rozmery` = (svisly, tloustka, vodorovny) podle katalogoveho GLB (zapadka 42 x 10,5 x 8, zamek 100,1 x 31,7 x 83)."""
    n = np.array(info["n"])
    eu = np.array(info["eu"])
    kn = int(np.argmax(np.abs(n)))
    sg = 1.0 if n[kn] > 0 else -1.0
    lo_, hi_ = O.aabb(dil)
    face = max(sg * (O.aabb(st)[1][kn] if sg > 0 else O.aabb(st)[0][kn]) for st in stojky)
    vnitrni = sg * (lo_[kn] if sg > 0 else hi_[kn])
    vnejsi = sg * (hi_[kn] if sg > 0 else lo_[kn])
    check(abs(vnitrni - face) < 0.01, f"dvere {popis}: dil lezi na vnejsi plose stojky (dosedaci plocha = plocha profilu)", (vnitrni, face))
    check(abs((vnejsi - vnitrni) - rozmery[1]) < 0.05, f"dvere {popis}: tloustka dilu nad plochou {rozmery[1]} mm", vnejsi - vnitrni)
    check(abs((hi_[1] - lo_[1]) - rozmery[0]) < 0.05, f"dvere {popis}: svisly rozmer dilu {rozmery[0]} mm", hi_[1] - lo_[1])
    vod = float(np.dot(hi_ - lo_, np.abs(eu)))
    check(abs(vod - rozmery[2]) < 0.05, f"dvere {popis}: vodorovny rozmer dilu {rozmery[2]} mm", vod)
    check(abs((lo_[1] + hi_[1]) / 2.0 - (info["spodek"] + min(1000.0, info["vyska_kridla"] / 2.0))) < 0.01, f"dvere {popis}: vyska stredu dilu = spodek kridla + min(1000, vyska / 2)")

for poloha, zav in itertools.product(("vlevo", "stred", "vpravo"), ("vlevo", "vpravo")):
    for strana, vel in (("celo", (2400, 1500)), ("prava", (1500, 2400)), ("zadni", (2400, 1500)), ("leva", (1500, 2400))):
        kw = dict(sirka=vel[0], hloubka=vel[1], vyska=2300, celo="stena", prava="stena", zadni="stena", leva="stena", dvere_poloha=poloha, dvere_zavesy=zav, dvere_sirka=900)
        kw[strana] = "dvere"
        r = O.sestav_oploceni(**kw)
        info = r["dvere"][0]
        eu = np.array(info["eu"])
        k = int(np.argmax(np.abs(eu)))
        pr = profily(r)
        stojky = [d for d in pr if d["role"].startswith("stojka křídla")]
        ostatni = [d for d in pr if not d.get("kridlo") and d["role"].startswith(("rohový", "mezilehlý"))]
        mezery = []
        for st in stojky:
            bs = O.aabb(st)
            for o in ostatni:
                bo = O.aabb(o)
                ov = prekryv(bs, bo)
                if all(ov[a] > 1 for a in range(3) if a != k):
                    g = max(bo[0][k] - bs[1][k], bs[0][k] - bo[1][k])
                    if g > -1e-6:
                        mezery.append(round(float(g), 2))
        check(sorted(mezery)[:2] == [3.0, 3.0], f"dvere {strana}/{poloha}/zavesy {zav}: vule 3 mm ke sloupkum na obou stranach", str(sorted(mezery)))
        # zavesy na strane zavesu: vzdalenost od stredu stojky na strane zavesu < vzdalenosti od protejsi stojky
        pant = [d for d in r["dily"] if d["druh"] == "pant"]
        check(len(pant) == 3 and all(d["part_id"] == (O.PANT_PRAVY if zav == "vpravo" else O.PANT_LEVY) for d in pant), f"dvere {strana}/{poloha}/zavesy {zav}: 3 zavesy spravneho typu")
        u_osa = float(np.dot(np.array(info["osa_bod"]), eu))
        u_st = sorted(float(np.dot(np.array(O.aabb(st)[0]) + np.array(O.aabb(st)[1]), eu)) / 2.0 for st in stojky)
        ocek_strana = max(u_st) if zav == "vpravo" else min(u_st)
        check(abs(abs(u_osa - ocek_strana) - 21.5) < 0.2, f"dvere {strana}/{poloha}/zavesy {zav}: osa zavesu je u spravne stojky (21,5 mm od jejiho stredu)", (u_osa, ocek_strana))
        for d in pant:                                                   # osa otaceni krídla (info pro nahled otevreni) = osa cepu zavesu (stred obalky zavesu ve vodorovne rovine)
            lo_p, hi_p = O.aabb(d)
            stred_p = (lo_p + hi_p) / 2.0 - np.array(info["osa_bod"])
            check(abs(float(np.dot(stred_p, eu))) < 0.01 and abs(float(np.dot(stred_p, np.array(info["n"])))) < 0.01, f"dvere {strana}/{poloha}/zavesy {zav}: osa otaceni krídla lezi v ose cepu zavesu", stred_p.tolist())
        pz = [float(np.dot(np.array(d["position"]), eu)) for d in pant]
        check(all(abs(x - pz[0]) < 0.01 for x in pz), f"dvere {strana}/{poloha}/zavesy {zav}: zavesy nad sebou ve stejne poloze podel steny")
        zam = [d for d in r["dily"] if d["druh"] == "zamek"]
        check(len(zam) == 1, f"dvere {strana}: 1 zamek")
        lo_z, hi_z = O.aabb(zam[0])
        uz = float(np.dot((lo_z + hi_z) / 2.0, eu))
        u_volna = min(u_st) if zav == "vpravo" else max(u_st)
        check(abs(uz - u_volna) < 0.01 and abs(uz - float(np.dot(np.array(info["osa_bod"]), eu))) > 600, f"dvere {strana}/{poloha}/zavesy {zav}: zapadka je vystredena na volne stojce (protejsi nez zavesy)", (uz, u_volna))
        zamek_na_plose(r, zam[0], stojky, info, f"{strana}/{poloha}/{zav}", (42.0, 10.5, 8.0), (0, 1, 2))
r = O.sestav_oploceni(zamek="zadny")
check(not [d for d in r["dily"] if d["druh"] == "zamek"], "zamek 'zadny' = bez zamku")
r = O.sestav_oploceni(zamek="zamek")
check([d["part_id"] for d in r["dily"] if d["druh"] == "zamek"] == [O.ZAMEK], "zamek 'zamek' = bezpecnostni zamek (#3423)")
for strana, vel in (("celo", (2400, 1500)), ("prava", (1500, 2400)), ("zadni", (2400, 1500)), ("leva", (1500, 2400))):
    kw = dict(sirka=vel[0], hloubka=vel[1], vyska=2300, celo="stena", prava="stena", zadni="stena", leva="stena", zamek="zamek", dvere_zavesy="vlevo")
    kw[strana] = "dvere"
    r = O.sestav_oploceni(**kw)
    stojky = [d for d in profily(r) if d["role"].startswith("stojka křídla")]
    zamek_na_plose(r, [d for d in r["dily"] if d["druh"] == "zamek"][0], stojky, r["dvere"][0], f"{strana}/zamek", (100.09, 31.71, 83.0), (2, 1, 0))
# dvere vyplnuji celou stenu
r = O.sestav_oploceni(sirka=886, dvere_sirka=800, celo="dvere", hloubka=800)
check(sum(1 for d in profily(r) if d["role"].startswith("mezilehlý")) == 0 and len(r["dvere"]) == 1, "dvere vypln celou stranu (svetlost 806 = 800 + 2 x 3): bez mezilehleho sloupku")
# dolni pricky: u dveri zadna, u poli ano
r = O.sestav_oploceni()
dolni = [d for d in profily(r) if d["role"].startswith("dolní příčka (celo)")]
check(len(dolni) == 1 and abs(dolni[0]["delka"] - 574) < 0.01, "celo: dolni pricka jen u pole (574), u dveri zadny prah")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("F) symetrie: dvere vlevo / zavesy vlevo je zrcadlem dveri vpravo / zavesy vpravo (profily a vyplne)")
a = O.sestav_oploceni(sirka=2100, hloubka=1500, dvere_poloha="vlevo", dvere_zavesy="vlevo")
b = O.sestav_oploceni(sirka=2100, hloubka=1500, dvere_poloha="vpravo", dvere_zavesy="vpravo")


def zrcadlo(bb, W):
    lo, hi = bb
    return (np.array([W - hi[0], lo[1], lo[2]]), np.array([W - lo[0], hi[1], hi[2]]))


def mnozina(r_, zrcadlit):
    out = set()
    for d in profily(r_):
        bb_ = O.aabb(d)
        if zrcadlit:
            bb_ = zrcadlo(bb_, 2100.0)
        out.add(tuple(np.round(np.concatenate([bb_[0], bb_[1]]), 1)))
    for v in r_["vyplne"]:
        for bb_ in kusy_aabb(v):
            if zrcadlit:
                bb_ = zrcadlo(bb_, 2100.0)
            out.add(tuple(np.round(np.concatenate([bb_[0], bb_[1]]), 1)))
    return out


check(mnozina(a, True) == mnozina(b, False), "zrcadlo (x -> W - x): shodne profily i kusy vyplni")
check(len(a["dily"]) == len(b["dily"]) and a["pocet_spoju"] == b["pocet_spoju"] and a["kusovnik"]["profily_celkem_mm"] == b["kusovnik"]["profily_celkem_mm"], "stejne pocty dilu, spoju a delka profilu")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("G) pravidla: pole, mezipricky, strecha, patky, vyplne po stranach")
for sirka, ocek_poli in ((600, 1), (1280, 1), (1281, 2), (2500, 2), (2520, 2), (2521, 3), (6000, 5)):          # svetla sirka - 80; pole <= 1200, mezi poli sloupky po 40
    r = O.sestav_oploceni(sirka=sirka, hloubka=600, vyska=1000, celo="stena", prava="stena", zadni="stena", leva="stena", strecha="zadna")
    celo = [v for v in r["vyplne"] if v["strana"] == "celo"]
    check(len({round(v["w"], 1) for v in celo}) == 1 and max(v["w"] for v in celo) <= 1200.0001 and len(celo) == ocek_poli, f"sirka {sirka}: {ocek_poli} poli na celo, kazde <= 1200 mm", (len(celo), [v['w'] for v in celo]))
    check(sum(1 for d in profily(r) if d["role"].startswith("mezilehlý sloupek") and d["strana"] == "celo") == ocek_poli - 1, f"sirka {sirka}: {ocek_poli - 1} mezilehlych sloupku na celo")
for vyska, ocek_radku in ((1000, 1), (1180, 1), (1181, 2), (1280, 2), (2300, 2), (2500, 3), (3000, 3)):          # svetla vyska otvoru = vyska - 80; max 1100 mezi pricky
    r = O.sestav_oploceni(sirka=900, hloubka=900, vyska=vyska, celo="stena", strecha="zadna")
    pole = [v for v in r["vyplne"] if v["strana"] == "celo"]
    check(len(pole) == ocek_radku and all(v["h"] <= 1100.0001 for v in pole), f"vyska {vyska}: {ocek_radku} radku vyplne, kazdy <= 1100 mm", (len(pole), [v["h"] for v in pole]))
r = O.sestav_oploceni(strecha="zadna")
check(not [v for v in r["vyplne"] if v["strana"] == "strecha"] and not [d for d in profily(r) if d["role"].startswith("střešní")], "strecha 'zadna': bez vyplne a strešních pricek")
r = O.sestav_oploceni(strecha="ram")
check(not [v for v in r["vyplne"] if v["strana"] == "strecha"] and not [d for d in profily(r) if d["role"].startswith("střešní")] and len([d for d in profily(r) if d["role"].startswith("horní příčka (")]) == 4, "strecha 'ram': jen horni ram (4 horni pricky, bez vyplne a strednich pricek)")
r = O.sestav_oploceni(sirka=1000, hloubka=1000, celo="stena", strecha="vyplne")
check(len([v for v in r["vyplne"] if v["strana"] == "strecha"]) == 1 and not [d for d in profily(r) if d["role"].startswith("střešní")], "strecha 1000 x 1000: jedna tabule, zadne strešní pricky")
r = O.sestav_oploceni(patky=True)
sl = [d for d in profily(r) if "sloupek" in d["role"]]
check(all(abs(d["delka"] - (2200 - O.PATKA_VYSKA)) < 1e-6 for d in sl if d["role"].startswith("rohový")) and all(abs(d["delka"] - (2160 - O.PATKA_VYSKA)) < 1e-6 for d in sl if d["role"].startswith("mezilehlý"))
      and sum(1 for d in r["dily"] if d["druh"] == "patka") == 8, "patky: sloupky o 79 mm kratsi, patka pod kazdym sloupkem (8)")
check(sum(1 for d in r["dily"] if d["druh"] == "zaslepka") == 8, "patky: zaslepky jen nahore rohovych sloupku (4) a u stojek kridla (4)")
r = O.sestav_oploceni(vyplne="plexi", vyplne_leva="pc_koura")
typy = {}
for v in r["vyplne"]:
    typy.setdefault(v["strana"], set()).add(v["typ"])
check(typy["leva"] == {"pc_koura"} and typy["celo"] == {"plexi"} and typy["prava"] == {"plexi"} and typy["zadni"] == {"plexi"} and typy["strecha"] == {"plexi"}, "vyplne po stranach: leva kourova, ostatni plexi; strecha bez vlastni volby = celkova")
r = O.sestav_oploceni(vyplne="plexi", strecha="vyplne", vyplne_strecha="plexi")
check({v["typ"] for v in r["vyplne"] if v["strana"] == "strecha"} == {"plexi"}, "vyplne strechy podle volby")
r = O.sestav_oploceni(vyplne="pc_cira", vyplne_strecha="sit")
check({v["typ"] for v in r["vyplne"] if v["strana"] == "strecha"} == {"sit"}, "vyplne strechy: vlastni volba (sit)")
# oploceni: jedna strana, ctyri pole, bez strechy: bez rohovych sloupku u otevrenych stran
r = O.sestav_oploceni(sirka=4800, hloubka=700, vyska=1800, celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna", vyplne="sit")
check(len([d for d in profily(r) if d["role"].startswith("rohový")]) == 2 and len([d for d in profily(r) if d["role"].startswith("mezilehlý")]) == 3, "oploceni 4 pole: 2 rohove + 3 mezilehle sloupky (otevrene strany bez sloupku)")
check(not [v for v in r["vyplne"] if v["strana"] != "celo"] and len([v for v in r["vyplne"]]) == 8, "oploceni 4 pole x 2 radky = 8 poli vyplne (vyska 1800: mezipricka)")
# nizke dvere ve vysoke stene: pole nad dvermi se deli mezipricky jako kazde jine (max svetla vyska 1100)
r = O.sestav_oploceni(vyska=3000, dvere_vyska=1500)
nad = [v for v in r["vyplne"] if v["role"].startswith("výplň nadpraží")]
mezi = [d for d in profily(r) if d["role"].startswith("mezipříčka nadpraží")]
check(len(nad) == 2 and len(mezi) == 1 and all(abs(v["h"] - 686.0) < 0.01 for v in nad) and abs(mezi[0]["delka"] - 806.0) < 0.01, "dvere 1500 ve vysce 3000: pole nad nimi (1412 mm) se deli 1 mezipricku na 2 x 686 mm", (len(nad), [v["h"] for v in nad], len(mezi)))
check(all(v["h"] <= 1100.0001 for v in r["vyplne"] if v["strana"] != "strecha"), "dvere 1500 ve vysce 3000: zadna vyplna steny neni vyssi nez 1100 mm", max(v["h"] for v in r["vyplne"]))
r = O.sestav_oploceni()
check(len([v for v in r["vyplne"] if v["role"].startswith("výplň nadpraží")]) == 1 and not [d for d in profily(r) if d["role"].startswith("mezipříčka nadpraží")], "vychozi dvere: pole nad dvermi (150 mm) bez mezipricky")
# otevrena strana se strechou: horni pricka + rohove sloupky
r = O.sestav_oploceni(celo="stena", prava="otevreno", zadni="stena", leva="stena", strecha="vyplne")
check(any(d["role"].startswith("horní příčka (prava, otevřená strana)") for d in profily(r)) and len([d for d in profily(r) if d["role"].startswith("rohový")]) == 4, "otevrena strana se strechou: horni pricka a vsechny rohove sloupky")
# T-spoj 2 spojky, L-roh 1: sedi na rozdilu poctu spojek a spoju
r = O.sestav_oploceni(celo="stena", prava="stena", zadni="stena", leva="stena", strecha="zadna", vyska=1000, sirka=600, hloubka=600)
check(len([d for d in r["dily"] if d["druh"] == "spojka"]) == 16 and r["pocet_spoju"] == 16 and len(profily(r)) == 12, "nejmensi kryt 600 x 600 x 1000 bez strechy: 4 rohove sloupky + 4 horni + 4 dolni pricky = 12 profilu, 16 konců pricek = 16 spojek a 16 spoju")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("H) entries, kusovnik, hash")
r = O.sestav_oploceni()
e = r["entries"]
check(sum(1 for x in e if x["product_id"] == O.PROFIL_PART) == 35 and sum(x.get("joint_count", 0) for x in e) == 54, "entries: 35 profilu s delkou, soucet joint_count = 54")
check(sum(1 for x in e if x["product_id"].startswith("navrh:")) == 21 and all("width_mm" in x and "height_mm" in x for x in e if x["product_id"].startswith("navrh:")), "entries: 21 desek vyplne s rozmerem tabule")
check(sum(1 for x in e if x["product_id"] == O.SPOJKA) == 80, "entries: 80 spojek")
hw = {m["sku"]: m["mnozstvi"] for m in r["kusovnik"]["spojovaci_material"]}
check(hw == {"2.1.21.0616": 160, "2.1.001.10.06": 160}, "spojovaci material: 2 sroubky + 2 matice na spojku (160 + 160)", str(hw))
check(r["extra_prace"] and r["extra_prace"][0]["unit_czk"] == 32.0, "extra prace: tesneni na sklo za metr")
h = {}
for kw in [dict(), dict(sirka=1600), dict(vyska=2300), dict(celo="stena"), dict(strecha="ram"), dict(vyplne="plexi"), dict(vyplne_leva="pc_koura"), dict(dvere_sirka=900), dict(dvere_poloha="stred"),
           dict(dvere_zavesy="vlevo"), dict(zamek="zamek"), dict(patky=True), dict(hloubka=1600)]:
    hh = O.sestav_oploceni(**kw)["hash"]
    check(hh not in h, f"hash je ruzny pro ruznou konfiguraci {kw}")
    h[hh] = kw
check(O.sestav_oploceni(sirka=1500.0)["hash"] == O.sestav_oploceni()["hash"] == O.sestav_oploceni(**{"sirka": "1500"})["hash"], "hash stabilni (cislo / text / vychozi)")
check(all(0 < len(x["product_id"]) for x in e), "entries maji product_id")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("I) GLB (hermeticky, fake prostredi)")
import _spolecne as C  # noqa: E402

C.nacti_generator(hermeticky=True)
import json  # noqa: E402
import struct  # noqa: E402

import trimesh  # noqa: E402
import oploceni_glb as OG  # noqa: E402

for nazev, kw in (("vychozi", dict()), ("oploceni", dict(sirka=4800, hloubka=700, vyska=1800, celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna", vyplne="sit")),
                  ("patky_dve_dvere", dict(sirka=2600, hloubka=1800, vyska=2300, celo="dvere", prava="dvere", dvere_poloha="stred", patky=True))):
    r = O.sestav_oploceni(**kw)
    glb = OG.sestav_glb(r)
    check(glb == OG.sestav_glb(r), f"GLB {nazev}: deterministicke bajty")
    sc = trimesh.load(__import__("io").BytesIO(glb), file_type="glb", force="scene")
    lo, hi = sc.bounds
    ext = hi - lo
    prof = [O.aabb(d) for d in profily(r)]
    env = np.max([b[1] for b in prof], axis=0) - np.min([b[0] for b in prof], axis=0)
    check(abs(ext[1] - r["parametry"]["vyska"]) < 1.0 and all(env[k] - 1.0 <= ext[k] <= env[k] + 45.0 for k in (0, 2)), f"GLB {nazev}: vyska = parametr vyska (vcetne patek), sirka a hloubka = obalka profilu (+ vystouple zavesy / zamek do 45 mm)",
          (np.round(ext, 1).tolist(), np.round(env, 1).tolist()))
    check(abs(r["rozmery"]["sirka_mm"] - env[0]) < 0.05 and abs(r["rozmery"]["hloubka_mm"] - env[2]) < 0.05 and r["rozmery"]["vyska_mm"] == r["parametry"]["vyska"], f"rozmery ve vysledku = obalka profilu ({nazev})", r["rozmery"])
    check(abs(lo[1]) < 0.01 and abs(lo[0] + hi[0]) < 40 and abs(lo[2] + hi[2]) < 40, f"GLB {nazev}: vycentrovano, podlaha y = 0", (np.round(lo, 1).tolist(), np.round(hi, 1).tolist()))
    off = 12
    js = None
    while off < len(glb):
        ln, typ = struct.unpack("<II", glb[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(glb[off + 8:off + 8 + ln])
        off += 8 + ln
    spec = js["scenes"][0]["extras"]["v3d"]
    check(spec["up"] == [0, 1, 0] and spec["front"] == [0, 0, 1] and spec["u"] == "mm" and len(spec["box"]["min"]) == 3, f"GLB {nazev}: spec v3d")
    check(np.allclose(spec["box"]["min"], lo, atol=0.01) and np.allclose(spec["box"]["max"], hi, atol=0.01), f"GLB {nazev}: spec.box = obalka")
    prus = [m for m in js["materials"] if m.get("alphaMode") == "BLEND"]
    skupin = len({OG.MATERIAL_DILU.get(d["part_id"], "ocel") for d in r["dily"]})
    check(len(js["nodes"]) == skupin + len(r["vyplne"]), f"GLB {nazev}: uzel na kazdou skupinu materialu ({skupin}) a na kazde pole vyplne ({len(r['vyplne'])})", len(js["nodes"]))
    check(all(m.get("doubleSided") for m in js["materials"] if m.get("alphaMode") == "BLEND"), f"GLB {nazev}: prusvitne materialy dvoustranne")
    typu = {v["typ"] for v in r["vyplne"]}
    check(len(prus) == len(typu) and len([m for m in js["materials"] if m.get("doubleSided")]) == len(typu), f"GLB {nazev}: pro kazdy typ vyplne ({len(typu)}) jeden prusvitny dvoustranny material (alphaMode BLEND)", (len(prus), len(typu)))
    tex = [m for m in js["materials"] if "baseColorTexture" in m["pbrMetallicRoughness"]]
    uzly_sit = [n for n in js["nodes"] if "TEXCOORD_0" in js["meshes"][n["mesh"]]["primitives"][0]["attributes"]]
    check(bool(tex) == ("sit" in typu) and (len(uzly_sit) == sum(1 for v in r["vyplne"] if v["typ"] == "sit")) and (not tex or (js.get("images") and js.get("textures") and js.get("samplers"))),
          f"GLB {nazev}: textura s UV jen u site (uzlu s UV {len(uzly_sit)})")
check(OG.MATERIAL_DILU == {"Object_11": "alu", "product_3176": "ocel", "product_3091": "cerna", "product_3644": "cerna", "product_3645": "cerna", "product_3283": "ocel", "product_3298": "ocel", "product_3423": "ocel"}, "material dilu v GLB (profil hlinik, spojka ocel, zaslepka a pant cerne)")
glb0 = OG.sestav_glb(O.sestav_oploceni())
glb1 = OG.sestav_glb(O.sestav_oploceni(), otevrit_dvere=70.0)
def bin_delka(g):
    off = 12
    while off < len(g):
        ln, typ = struct.unpack("<II", g[off:off + 8])
        if typ == 0x004E4942:
            return ln
        off += 8 + ln


check(glb0 != glb1 and bin_delka(glb0) == bin_delka(glb1), "otevrene dvere (jen nahled): jina poloha dilu, stejny objem dat")
def obalky_uzlu(g):
    """Obalky (min, max) POSITION kazdeho uzlu GLB v poradi uzlu (nejdriv skupiny materialu alu / ocel / cerna, potom pole vyplne v poradi r['vyplne'])."""
    off, js_ = 12, None
    while off < len(g):
        ln, typ = struct.unpack("<II", g[off:off + 8])
        if typ == 0x4E4F534A:
            js_ = json.loads(g[off + 8:off + 8 + ln])
        off += 8 + ln
    out = []
    for n in js_["nodes"]:
        ac = js_["accessors"][js_["meshes"][n["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
        out.append((np.array(ac["min"]), np.array(ac["max"])))
    return out


# tloustka vyplne v GLB = tloustka z tabulky (plexi 5, sit 3, PC 4, plna 3): nejmensi rozmer obalky uzlu pole
for kw_, tl in ((dict(vyplne="plexi", vyplne_leva="sit", strecha="zadna"), {"plexi": 5.0, "sit": 3.0}), (dict(vyplne="pc_koura", vyplne_strecha="plna"), {"pc_koura": 4.0, "plna": 3.0}), (dict(), {"pc_cira": 4.0})):
    r_ = O.sestav_oploceni(**kw_)
    ob_ = obalky_uzlu(OG.sestav_glb(r_))
    n_op_ = len({OG.MATERIAL_DILU.get(d["part_id"], "ocel") for d in r_["dily"]})
    zle_ = [(v["role"], v["typ"], float(min(ob_[n_op_ + i][1] - ob_[n_op_ + i][0]))) for i, v in enumerate(r_["vyplne"]) if abs(float(min(ob_[n_op_ + i][1] - ob_[n_op_ + i][0])) - tl[v["typ"]]) > 0.01]
    check(not zle_ and len(ob_) == n_op_ + len(r_["vyplne"]), f"GLB: tloustka kazdeho pole vyplne = tloustka materialu {tl}", zle_[:2])

# otevreni dveri (nahled): kridlo = jeho profily, spojky, zamek a jeho vyplne se otoci, vse ostatni (pevna pole, zavesy) zustane; srovnani vuci pevnemu poli ve stejne stene (nezavisle na vycentrovani)
r_ = O.sestav_oploceni()
ob0, ob1 = obalky_uzlu(OG.sestav_glb(r_)), obalky_uzlu(OG.sestav_glb(r_, otevrit_dvere=70.0))
n_op_ = len({OG.MATERIAL_DILU.get(d["part_id"], "ocel") for d in r_["dily"]})
ref_ = next(i for i, v in enumerate(r_["vyplne"]) if v["role"].startswith("výplň pole (celo)"))
dz = lambda ob, i: float(ob[i][1][2] - ob[n_op_ + ref_][1][2])
for i, v in enumerate(r_["vyplne"]):
    zmena = dz(ob1, n_op_ + i) - dz(ob0, n_op_ + i)
    if v["role"].startswith("výplň křídla"):
        check(zmena > 400, f"otevreni dveri: pole vyplne kridla se vyklopi ven (o {zmena:.0f} mm)", v["role"])
    else:
        check(abs(zmena) < 0.01, f"otevreni dveri: pevne pole vyplne se nehybe ({v['role']})", zmena)
check(dz(ob1, 0) - dz(ob0, 0) > 500, "otevreni dveri: hlinikove profily kridla (skupina alu) se vyklopi ven", dz(ob1, 0) - dz(ob0, 0))

for zav in ("vpravo", "vlevo"):                                   # otevrene dvere se vyklopi VEN (do smeru +Z u cela), ne dovnitr, a to na obe strany zavesu
    rz = O.sestav_oploceni(dvere_zavesy=zav, strecha="zadna")
    b_zav = trimesh.load(__import__("io").BytesIO(OG.sestav_glb(rz)), file_type="glb", force="scene").bounds
    b_otev = trimesh.load(__import__("io").BytesIO(OG.sestav_glb(rz, otevrit_dvere=70.0)), file_type="glb", force="scene").bounds
    rust = (b_otev[1][2] - b_otev[0][2]) - (b_zav[1][2] - b_zav[0][2])
    check(rust > 600, f"dvere se zavesy {zav} se otevrou ven (hloubka obalky vzroste o {rust:.0f} mm; sirka kridla 800, sin 70 = 0,94), ne dovnitr")
h1, g1 = OG.model_pro_parametry({})
h2, g2 = OG.model_pro_parametry({"sirka": 1500})
check(h1 == h2 == O.sestav_oploceni()["hash"] and g1 == g2 and g1 == glb0, "model_pro_parametry: hash a bajty = sestav_glb, cache")
h3, g3 = OG.model_pro_parametry({"sirka": 1600})
check(h3 != h1 and g3 != g1 and h3 == O.sestav_oploceni(sirka=1600)["hash"], "model_pro_parametry: jina konfigurace = jiny hash a jine bajty (cache nezamenuje)")
for typ in O.VYPLNE:                                                                     # kazdy typ vyplne se sestavi do GLB
    gl = OG.sestav_glb(O.sestav_oploceni(vyplne=typ, sirka=900, hloubka=900, vyska=1200, celo="stena"))
    check(gl[:4] == b"glTF" and len(gl) > 1000, f"GLB s vyplni {typ} se sestavi")

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("J) pripnute konstanty navrhu, tabulky a otisky geometrie (zlaty stav: zmena = vedomy zasah do navrhu, aktualizovat po schvaleni)")
check((O.PROFIL, O.INS, O.BLOK, O.VYREZ, O.POLE_MAX, O.MID_MAX, O.POLE_MIN, O.MEZERA_DVERE, O.DVERE_NAD_PODLAHOU, O.NADPRAZ_MIN, O.PATKA_VYSKA, O.ZAVESY_Y)
      == (40.0, 9.0, 37.0, 47.0, 1200.0, 1100.0, 150.0, 3.0, 5.0, 150.0, 79.0, 150.0), "konstanty navrhu (profil, zasunuti 9, blok spojky 37, vyrez 47, pole 1200 / 1100, vule dveri 3, nadpraz 150, patka 79, zavesy 150)")
check(O.ROZSAH == {"sirka": (600.0, 6000.0), "hloubka": (600.0, 6000.0), "vyska": (1000.0, 3000.0), "dvere_sirka": (600.0, 1200.0), "dvere_vyska": (1500.0, 2400.0)}, "meze rozmeru")
check({k: (v["tloustka"], v["sku"], v["cena_m2"], v["tesneni"]) for k, v in O.VYPLNE.items()}
      == {"pc_cira": (4.0, "OPL-PC-CIRY-04", 1150.0, "product_3218"), "pc_koura": (4.0, "OPL-PC-KOURA-04", 1350.0, "product_3218"), "plexi": (5.0, "OPL-PLEXI-CIRE-05", 1550.0, "product_3218"),
          "sit": (3.0, "OPL-SIT-03", 900.0, "product_3199"), "plna": (3.0, "OPL-AL-KOMPOZIT-03", 1400.0, "product_3199")}, "tabulka vyplni (tloustka, navrh SKU, orientacni cena za m2, tesneni)")
check({k: (v["sku"], v["cena_m"]) for k, v in O.TESNENI_KARTY.items()} == {"product_3218": ("2.3.006.10.02", 32.0), "product_3199": ("2.3.005.10.01.01", 25.0)}, "karty tesneni (SKU, cena za metr)")
check((O.PROFIL_PART, O.SPOJKA, O.ZASLEPKA, O.PANT_PRAVY, O.PANT_LEVY, O.PATKA, O.ZAPADKA, O.ZAMEK) == ("Object_11", "product_3176", "product_3091", "product_3644", "product_3645", "product_3283", "product_3298", "product_3423"),
      "dily katalogu")
check(O.SPOJOVACI_MATERIAL == {"product_3176": [("2.1.21.0616", 2, "Šroub imbus s válcovou hlavou M6×16"), ("2.1.001.10.06", 2, "Otočná matice M6 (drážka 10)")]}, "spojovaci material ke spojce")
import hashlib  # noqa: E402


def otisk(r_):
    d = [(x["part_id"], list(map(float, x["quaternion"])), list(map(float, x["scale"])), list(map(float, x["position"])), x["druh"], x["role"]) for x in r_["dily"]]
    v = [(x["typ"], x["w"], x["h"], x["role"], x["vyrezy"], x["vyrezy_vsechny"], [(list(map(float, k["stred"])), k["e1"], k["e2"]) for k in x["kusy"]]) for x in r_["vyplne"]]
    return hashlib.sha1(json.dumps([d, v, r_["pocet_spoju"], r_["kusovnik"]], sort_keys=True, default=str).encode()).hexdigest()[:16]


OTISKY = [(dict(), "fb3bc73298fef141"), (dict(vyplne_leva="pc_koura"), "cb2c0cf72bb7eb82"),
          (dict(sirka=4800, hloubka=700, vyska=1800, celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna", vyplne="sit"), "187b1b5703d837a7"),
          (dict(sirka=2600, hloubka=1800, vyska=2300, celo="dvere", prava="dvere", zadni="stena", leva="stena", strecha="vyplne", dvere_sirka=900, dvere_poloha="stred", zamek="zamek", patky=True), "8d9c812f55b97133"),
          (dict(sirka=6000, hloubka=6000, vyska=3000, celo="stena", strecha="vyplne"), "a14e3c68f1b46ff0"),
          (dict(sirka=3600, hloubka=2400, vyska=2800, celo="dvere", dvere_poloha="vlevo", dvere_zavesy="vlevo", strecha="vyplne"), "3767881a412bc3d5"),
          (dict(sirka=2400, hloubka=2000, vyska=2000, celo="stena", prava="otevreno", zadni="otevreno", strecha="ram"), "92c758e8be2c897c")]
for kw, ocek in OTISKY:
    got = otisk(O.sestav_oploceni(**kw))
    check(got == ocek, f"otisk geometrie {kw or 'vychozi'}", got)
r = O.sestav_oploceni()
check(r["rozmery"]["svetla_sirka_mm"] == 1420.0 and r["rozmery"]["svetla_hloubka_mm"] == 1420.0 and r["rozmery"]["svetla_vyska_mm"] == 2160.0 and r["rozmery"]["pudorys_m2"] == 2.25, "rozmery uzavreneho krytu: svetlost 1420 x 1420 x 2160, pudorys 2,25 m2", r["rozmery"])
r = O.sestav_oploceni(celo="stena", prava="otevreno", zadni="otevreno", leva="otevreno", strecha="zadna")
check(r["rozmery"]["svetla_sirka_mm"] is None and r["rozmery"]["pudorys_m2"] is None and r["rozmery"]["svetla_vyska_mm"] == 2200.0, "oploceni (neuzavreny pudorys): bez svetlosti a pudorysu, svetla vyska 2200", r["rozmery"])

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("K) cena s virtualnimi deskami (fake ctx, nezavisly vypocet)")
import oploceni_cena as OC  # noqa: E402

CP = OC.CP
parts = {"Object_11": {"id": "Object_11", "name": "Profil 40x40mm", "layer": "profil", "sku": None, "length_mm": 1000.0, "cross_section_mm": [40.0, 40.0], "weight_kg": 1.04, "price_czk": 430.0,
                       "price_per_cut_czk": 50.0, "is_board_material": False, "scene_coef": True}}
for pid, cena in ((O.SPOJKA, 19.0), (O.ZASLEPKA, 5.0), (O.PANT_PRAVY, 72.0), (O.PANT_LEVY, 72.0), (O.PATKA, 47.0), (O.ZAPADKA, 57.0), (O.ZAMEK, 384.0)):
    parts[pid] = {"id": pid, "name": pid, "layer": "produkt", "sku": None, "length_mm": None, "cross_section_mm": [None, None], "weight_kg": None, "price_czk": cena, "price_per_cut_czk": None,
                  "is_board_material": False, "scene_coef": False}
for sku, pid, cena in (("2.1.21.0616", "product_4945", 2.0), ("2.1.001.10.06", "product_3582", 1.5)):
    parts[pid] = {"id": pid, "name": sku, "layer": "produkt", "sku": sku, "length_mm": None, "cross_section_mm": [None, None], "weight_kg": None, "price_czk": cena, "price_per_cut_czk": None,
                  "is_board_material": False, "scene_coef": False}
ctx = {"parts": parts, "pricing": {"joint_price_czk": 110.0, "profile_flat_fee_czk": 5.0, "packaging_pct": 3.0, "montaz_pct": 8.0, "accessories": [], "scene_price_coefficient": 1.0}, "joint_rule_version": 3}
r = O.sestav_oploceni()
c = OC.cena(r, ctx)
ps = c["price_summary"]
mat = sum(d["delka"] / 1000.0 * 430.0 for d in profily(r)) + sum(v["rozmer_tabule"][0] * v["rozmer_tabule"][1] / 1e6 * O.VYPLNE[v["typ"]]["cena_m2"] for v in r["vyplne"])
check(abs(ps["material_czk"] - round(mat)) <= 1, "cena: material = soucet profilu (delka x cena/m) a desek (m2 x cena/m2)", (ps["material_czk"], round(mat)))
check(ps["cut_czk"] == 35 * 50 and ps["profile_flat_fee_czk"] == 35 * 5 and ps["joint_count"] == 54 and ps["joint_czk"] == 54 * 110, "cena: rezy, pausal za profil a spoje podle poctu", ps)
acc = 80 * 19.0 + 16 * 5.0 + 3 * 72.0 + 57.0 + 160 * 2.0 + 160 * 1.5
check(abs(ps["accessory_czk"] - round(acc)) <= 1, "cena: prislusenstvi (spojky, zaslepky, zavesy, zapadka, spojovaci material)", (ps["accessory_czk"], acc))
tes = sum(t["mnozstvi"] * t["cena_m"] for t in r["kusovnik"]["tesneni"])
check(abs(ps["extra_work_czk"] - round(tes)) <= 1 and not c["chybejici"], "cena: tesneni jako extra prace za metr; spojovaci material nalezen", (ps["extra_work_czk"], tes, c["chybejici"]))
ctx_bez = {**ctx, "parts": {k: v for k, v in parts.items() if k not in ("product_4945",)}}
c2 = OC.cena(r, ctx_bez)
check([m["sku"] for m in c2["chybejici"]] == ["2.1.21.0616"], "chybejici spojovaci material (bez karty) je v 'chybejici'")

# upozorneni (ID a hranice)
ids = lambda **kw: [u["id"] for u in O.sestav_oploceni(**kw)["upozorneni"]]
check(ids() == ["norma"], "upozorneni: vychozi konfigurace jen 'norma'", ids())
check("14120" in O.sestav_oploceni()["upozorneni"][0]["text"] and "13857" in O.sestav_oploceni()["upozorneni"][0]["text"], "upozorneni 'norma' zmiňuje ISO 14120 a 13857")
check(ids(vyska=2500) == ["norma"] and ids(vyska=2501) == ["norma", "kotveni"], "upozorneni: ukotveni od vysky nad 2500 mm (2500 ne, 2501 ano)")
check(ids(sirka=4000, hloubka=4000) == ["norma"] and ids(sirka=4001, hloubka=1500, celo="stena") == ["norma", "kotveni"] and ids(sirka=1500, hloubka=4001) == ["norma", "kotveni"], "upozorneni: ukotveni od delky strany nad 4000 mm (4000 ne, 4001 ano; sirka i hloubka)")
check(ids(dvere_sirka=1000) == ["norma"] and ids(dvere_sirka=1100) == ["norma", "dvere_siroke"], "upozorneni: tezke kridlo nad 1000 mm (1000 ne, 1100 ano)")
check(ids(celo="stena", dvere_sirka=1100) == ["norma"], "upozorneni: sirka dveri se bez dveri neuplatni")
check(ids(vyplne="sit") == ["norma", "sit"] and ids(vyplne_leva="sit") == ["norma", "sit"] and ids(vyplne_strecha="sit") == ["norma", "sit"] and ids(vyplne="sit", vyplne_leva="plexi", vyplne_prava="plexi", vyplne_zadni="plexi", vyplne_celo="plexi", vyplne_strecha="plexi") == ["norma"],
      "upozorneni: sit kdekoli (celek, strana, strecha) = 'sit'; prebita vsude jinde = ne")
check(ids(vyska=2600, dvere_sirka=1100, vyplne="sit") == ["norma", "kotveni", "dvere_siroke", "sit"], "upozorneni: poradi norma, kotveni, dvere_siroke, sit")

# doplnky_ctx s falesnym kurzorem: karty dilu mimo scenu (panty, zapadka, patka, tesneni, spojovaci material) se doplni do ctx s cenou z karty a koeficientem sceny jen u dilu z Dogusu / profilovych
class FalesnyKurzor:
    def __init__(self, radky):
        self.radky, self.dotaz = radky, None

    def execute(self, sql, params=()):
        self.dotaz = (sql, params)

    def fetchall(self):
        return self.radky


radky = [{"id": 3644, "name": "Pant 40x40 (pravy)", "sku": "2.2.003.4040.05", "weight_g": 80.0, "price_czk_placeholder": 72.0, "unit": "ks", "dogus_url": "https://dogus.example/x", "is_profile_material": 0},
         {"id": 3283, "name": "Patka", "sku": "2.3.002.1050", "weight_g": None, "price_czk_placeholder": 47.0, "unit": "KS ", "dogus_url": None, "is_profile_material": 0},
         {"id": 3176, "name": "Spojka", "sku": "2.2.001.10.4040.33", "weight_g": 43.0, "price_czk_placeholder": 19.0, "unit": "ks", "dogus_url": None, "is_profile_material": 1},
         {"id": 3091, "name": "Zaslepka", "sku": "2.3.001.4040.01", "weight_g": 5.5, "price_czk_placeholder": None, "unit": "ks", "dogus_url": "x", "is_profile_material": 0}]
ctx3 = {"parts": {"product_3091": {"id": "product_3091", "price_czk": 5.0}}, "pricing": {"scene_price_coefficient": 1.15}}
kur = FalesnyKurzor(radky)
OC.doplnky_ctx(kur, ctx3)
P = ctx3["parts"]
check(set(P) == {"product_3091", "product_3644", "product_3283", "product_3176"} and P["product_3091"] == {"id": "product_3091", "price_czk": 5.0}, "doplnky_ctx: existujici dil ve scene se nepřepisuje, ostatni se doplni")
check(P["product_3644"]["price_czk"] == 82.8 and P["product_3176"]["price_czk"] == 21.85 and P["product_3283"]["price_czk"] == 47.0, "doplnky_ctx: koeficient sceny 1,15 jen u dilu z Dogusu (72 -> 82,80) a profilovych (19 -> 21,85), ne u ostatnich (47)", {k: v["price_czk"] for k, v in P.items()})
check(P["product_3283"]["unit"] == "ks" and P["product_3644"]["weight_kg"] == 0.08 and P["product_3283"]["weight_kg"] is None and P["product_3644"]["is_board_material"] is False and P["product_3644"]["sku"] == "2.2.003.4040.05",
      "doplnky_ctx: jednotka malymi pismeny, hmotnost v kg, SKU, neni deska")
dotaz, parametry = kur.dotaz
check(set(parametry) >= {3176, 3091, 3644, 3645, 3283, 3298, 3423, 3218, 3199, "2.1.21.0616", "2.1.001.10.06"} and "shop_products" in dotaz and "UPDATE" not in dotaz.upper() and "INSERT" not in dotaz.upper(),
      "doplnky_ctx: dotaz jen cte a ptá se na vsechny dily oploceni a spojovaci material", parametry)

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
print("L) karty vyplni: prepnuti ceny z virtualnich desek `navrh:<typ>` na karty `product_<id>` (fake kurzor a ctx, nezavisly vypocet)")


class KurzorNastaveni:
    """Fake kurzor: SELECT setting_value ... (fetchone) a SELECT z shop_products (fetchall = zadne dalsi karty)."""
    def __init__(self, hodnota=None, vyjimka=False):
        self.hodnota, self.vyjimka, self.dotazy = hodnota, vyjimka, []

    def execute(self, sql, params=()):
        if self.vyjimka:
            raise RuntimeError("DB nedostupna")
        self.dotazy.append((sql, params))

    def fetchone(self):
        return None if self.hodnota is None else {"setting_value": self.hodnota}

    def fetchall(self):
        return []


kv = lambda h, **kw: OC.karty_vyplni(KurzorNastaveni(h, **kw))
check(kv(json.dumps({"pc_cira": 5400, "sit": 5401})) == {"pc_cira": 5400, "sit": 5401}, "karty_vyplni: platne mapovani typ -> id karty")
check(kv(None) == {} and kv("") == {} and kv("nesmysl") == {} and kv("[1, 2]") == {} and kv("null") == {} and kv("5") == {}, "karty_vyplni: chybejici / prazdne / rozbite / ne-objektove nastaveni = {}")
check(kv(json.dumps({"pc_cira": 5400}), vyjimka=True) == {}, "karty_vyplni: vyjimka DB = {} (cena se vzdy spocita)")
check(kv(json.dumps({"neznamy": 5, "pc_cira": 5400})) == {"pc_cira": 5400}, "karty_vyplni: neznamy typ vyplne se ignoruje")
check(kv(json.dumps({"pc_cira": True, "sit": 5401.0, "plexi": "5402", "plna": 0, "pc_koura": -3})) == {}, "karty_vyplni: bool, desetinne cislo, retezec, nula a zaporne cislo se ignoruji")
k_ = KurzorNastaveni(json.dumps({"pc_cira": 5400}))
OC.karty_vyplni(k_)
check(len(k_.dotazy) == 1 and k_.dotazy[0][0].lstrip().upper().startswith("SELECT") and k_.dotazy[0][1] == ("oploceni_karty_vyplni",) and OC.KARTY_VYPLNI_KLIC == "oploceni_karty_vyplni",
      "karty_vyplni: jediny dotaz, SELECT z app_settings `oploceni_karty_vyplni`", k_.dotazy)


def deska(pid, cena, je_deska=True):
    return {"id": pid, "name": f"{pid} KARTA", "layer": "produkt", "sku": "X-" + pid, "length_mm": None, "cross_section_mm": [None, None], "weight_kg": None, "price_czk": cena, "price_per_cut_czk": None,
            "is_board_material": je_deska, "source": "product", "scene_coef": False, "unit": "m2", "price_basis": None}


base = {"parts": dict(parts, product_5400=deska("product_5400", 1000.0), product_5401=deska("product_5401", 700.0, False)), "pricing": ctx["pricing"], "joint_rule_version": 3}
casti_pred = dict(base["parts"])
kd = OC.odvozeny_kontext(KurzorNastaveni(json.dumps({"pc_cira": 5400, "sit": 5401, "plexi": 5999})), base)
check(kd["karty_vyplni"] == {"pc_cira": 5400}, "odvozeny_kontext: projde jen karta, ktera v kontextu je a je deska (sit = karta neni deska, plexi = karta v kontextu neni)", kd["karty_vyplni"])
check(kd is not base and kd["parts"] is not base["parts"] and base["parts"] == casti_pred and "karty_vyplni" not in base, "odvozeny_kontext: kontext stolu (sdileny) se nemeni")
kd_bez = OC.odvozeny_kontext(KurzorNastaveni(None), base)
check(kd_bez["karty_vyplni"] == {}, "odvozeny_kontext: bez nastaveni zadne karty")

r = O.sestav_oploceni(vyplne_leva="sit")                                    # pc_cira (ma kartu) + sit (jen virtualni deska)
c_v = OC.cena(r, kd_bez)
c_k = OC.cena(r, kd)
ps_v, ps_k = c_v["price_summary"], c_k["price_summary"]
plocha = sum(v["rozmer_tabule"][0] * v["rozmer_tabule"][1] / 1e6 for v in r["vyplne"] if v["typ"] == "pc_cira")
check(abs((ps_k["material_czk"] - ps_v["material_czk"]) - round(plocha * (1000.0 - 1150.0))) <= 1, "cena s kartou: material se zmeni o plochu pc_cira x (cena karty - orientacni cena)", (ps_k["material_czk"] - ps_v["material_czk"], round(plocha * -150.0)))
check(all(ps_k[k] == ps_v[k] for k in ("cut_czk", "joint_czk", "accessory_czk", "extra_work_czk", "joint_count")) and ps_k["total_czk"] < ps_v["total_czk"], "cena s kartou: rezy, spoje, prislusenstvi a tesneni se nemeni")
nazvy_k = [b["name"] for b in c_k["bom"]]
nazvy_v = [b["name"] for b in c_v["bom"]]
check(any("product_5400 KARTA" in n for n in nazvy_k) and not any("OPL-PC-CIRY-04" in n for n in nazvy_k) and any("OPL-SIT-03" in n for n in nazvy_k),
      "cena s kartou: pc_cira se cení z karty (nazev karty v kusovniku), sit bez karty zustava virtualni deska")
check(not any("5400" in n for n in nazvy_v) and any("OPL-PC-CIRY-04" in n for n in nazvy_v) and not c_k["warnings"] and not c_v["warnings"], "cena bez karet: virtualni desky (ceny nechybi)")
check(all(e["product_id"].startswith("navrh:") for e in r["entries"][-len(r["vyplne"]):]), "cena() nemeni vysledek jadra (entries zustavaji virtualni)")
kd_drazsi = OC.odvozeny_kontext(KurzorNastaveni(json.dumps({"pc_cira": 5400})), dict(base, parts=dict(base["parts"], product_5400=deska("product_5400", 2000.0))))
check(OC.cena(r, kd_drazsi)["price_summary"]["total_czk"] > ps_v["total_czk"], "cena s kartou: karta drazsi nez orientacni cena = cena vyroste (cena se bere z karty, ne z navrhu)")

r2 = O.sestav_oploceni()                                                   # vse pc_cira
t_ref = OC.cena(r2, kd)["price_summary"]["total_czk"]
check(OC.cena(r2, kd, vyplne_typy=["pc_cira"] * len(r2["vyplne"]))["price_summary"]["total_czk"] == t_ref, "vyplne_typy: stejny typ = stejna cena")
for typ in ("sit", "plexi", "pc_koura", "plna"):
    alt = OC.cena(r2, kd, vyplne_typy=[typ] * len(r2["vyplne"]))["price_summary"]["total_czk"]
    ref = OC.cena(O.sestav_oploceni(vyplne=typ), kd)["price_summary"]["total_czk"]
    check(alt == ref, f"vyplne_typy: preceneni na {typ} (u puvodniho typu karta) = cena znovu sestavene konfigurace", (alt, ref))

te = OC.tesneni_extra([{"w": 500.0, "h": 300.0}, {"w": 1000.0, "h": 200.0}, {"w": 100.0, "h": 100.0}], ["pc_cira", "sit", "plexi"])
check([(t["unit_czk"], t["qty"]) for t in te] == [(32.0, 2.0), (25.0, 2.4)] and te[0]["name"] == "Těsnění na sklo – drážka 10, průhledná [2.3.006.10.02]" and te[1]["name"] == "Měkké těsnění drážky – drážka 10, černá [2.3.005.10.01.01]",
      "tesneni_extra: obvod otvoru v metrech, typy se sklem (pc, plexi) sdili tesneni, sit a plna mekke", te)
rr = O.sestav_oploceni(vyplne_leva="sit", vyplne_strecha="plexi")
check(OC.tesneni_extra(rr["vyplne"], [v["typ"] for v in rr["vyplne"]]) == rr["extra_prace"], "tesneni_extra: pro puvodni typy = extra_prace jadra (stejny tvar, poradi i metry)")

print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:6]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
