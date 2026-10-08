#!/usr/bin/env python3
"""JADRO generatoru stolu SYSTEM 45 = hluboky stul az 2500 mm (bot10, 2026-10-07).

Robert 2026-10-07: "postav generator stolu system 45, profil 1.1.10.040040.03, hloubka stolu az 2500 mm, mozna tam musime lehce zmenit konstrukci", "kompatibilita s predeslymi generatory".
System 45 = profil, spojky, sablona i vsechny dily jako SYSTEM 40 (SuperLight S10 40x40, Object_11), jen HLOUBKA 400-2500 mm; nad HLOUBKA_STREDNI_NOHA (1500 mm) pribyva uprostred hloubky na
kazde strane STREDNI NOHA (od podlahy po spodni bocni pricku) a pod podperami pracovni desky i kazde police PRICKA pres sirku mezi obema strednimi nohami.

Hlida:
  A) rozsah hloubky po systemech (45: 400-2500, ostatni 400-1500; mimo rozsah = StulChyba), pravidla 45 jsou vlastni sada se stejnymi vychozimi hodnotami jako 40;
  B) KOMPATIBILITA: do hloubky 1500 mm (vcetne) je stul systemu 45 BIT PO BITU stejny jako system 40 (dily, klice, problemy, info, rozmery, spoje) - mrizka ~1000 konfiguraci;
  C) hluboky stul (nad 1500): bez problemu, stredni nohy presne v pulce hloubky a v ose bocnich noh, pricky presne mezi nimi pod bocnimi pruvlaky, konce noh (kolecko / patka / zaslepka),
     pocty dilu proti systemu 40 stejne sirky, informace `stredni_rada_noh`;
  D) prah: 1500 mm jeste bez stredni rady, 1510 mm uz s ni; nastavitelny prah `hloubka_stredni_profil` (podpery) funguje v systemu 45 zvlast;
  E) nahodna sada voleb (pevne semeno): hluboky stul je platny vzdy, kdyz je platny stul 40 o hloubce 1500 se stejnymi volbami.
Spusteni (bez DB):  api/venv/bin/python3 -B scripts/2026-10-07_system45/test_s45_jadro.py [--rychle]"""
import itertools
import os
import random
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.dont_write_bytecode = True
import numpy as np  # noqa: E402
import stul_konfigurator as S  # noqa: E402

RYCHLE = "--rychle" in sys.argv
OK, FAILS = 0, []
PROFIL = 40.0                                   # sirka profilu SuperLight S10 40x40 (system 45 = profil systemu 40)


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print("  CHYBA:", msg)


def klice(r):
    return [tuple(k) if isinstance(k, list) else k for k in r["klice"]]


def podle_klice(r):
    return dict(zip(klice(r), r["dily"]))


def smer(d):
    """Jednotkovy vektor delky profilu (lokalni osa Y) po otoceni kvaternionem [x, y, z, w]."""
    x, y, z, w = d["quaternion"]
    return np.array([2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)])


def osa(d):
    v = np.abs(smer(d))
    return "XYZ"[int(v.argmax())]


def sestav(system, **kw):
    try:
        return S.sestav_stul(system=system, **kw), None
    except S.StulChyba as e:
        return None, str(e)


# ---------------------------------------------------------------- A) rozsah a pravidla
check(S.SYSTEM_45 == 45 and 45 in S.SYSTEMY, "system 45 je v tabulce SYSTEMY")
check(S.SYSTEMY[45]["profil"] == S.SYSTEMY[40]["profil"] == "Object_11", f"profil systemu 45 = profil systemu 40 (Object_11): {S.SYSTEMY[45]['profil']}")
check(tuple(S._rozsahy(45)["hloubka"]) == (400.0, 2500.0), f"rozsah hloubky systemu 45: {S._rozsahy(45)['hloubka']}")
for s_ in (30, 35, 40, 41):
    check(tuple(S._rozsahy(s_)["hloubka"]) == tuple(S.ROZSAH["hloubka"]) == (400, 1500), f"rozsah hloubky systemu {s_} beze zmeny: {S._rozsahy(s_)['hloubka']}")
for hl, system, ocekavano in ((2500.0, 45, True), (400.0, 45, True), (2510.0, 45, False), (399.0, 45, False), (2500.0, 40, False), (1500.0, 40, True)):
    r, err = sestav(system, hloubka=hl, sirka=1200.0)
    check((r is not None) == ocekavano, f"hloubka {hl:g} mm v systemu {system}: {'platna' if ocekavano else 'StulChyba'} ({err})")
    if r is not None:
        check(r["parametry"]["hloubka"] == hl and r["parametry"]["system"] == system, f"hloubka {hl:g} se zachova, system {system}")
check(S.pravidla_systemu(45) == S.pravidla_systemu(40) == S.PRAVIDLA_VYCHOZI, "pravidla systemu 45 maji stejne vychozi hodnoty jako 40")
check(S.PRAVIDLA_SYSTEMU[45] is not S.PRAVIDLA_SYSTEMU[40], "sada pravidel systemu 45 je vlastni slovnik (ne sdileny s 40)")

# ---------------------------------------------------------------- B) 45 == 40 do hloubky 1500 mm (bit po bitu)
t0 = time.time()
HL_B = (400.0, 900.0, 901.0, 1200.0, 1500.0) if not RYCHLE else (900.0, 1500.0)
SIR_B = (600.0, 1280.0, 1500.0, 1501.0, 2200.0, 3000.0) if not RYCHLE else (1280.0, 2200.0)
VYS_B = (300.0, 840.0, 1200.0) if not RYCHLE else (840.0,)
pocet_b = rozdil_b = 0
for hl, sr, vy, pol, kol, sup in itertools.product(HL_B, SIR_B, VYS_B, (0, 1, 2), (True, False), (True, False)):
    kw = dict(hloubka=hl, sirka=sr, vyska=vy, police=pol, kolecka=kol, suplik=sup)
    a, ea = sestav(45, **kw)
    b, eb = sestav(40, **kw)
    pocet_b += 1
    if (a is None) != (b is None) or ea != eb:
        rozdil_b += 1
        check(False, f"B) {kw}: 45 -> {ea}, 40 -> {eb}")
        continue
    if a is None:
        continue
    shodne = (a["dily"] == b["dily"] and a["klice"] == b["klice"] and a["problemy"] == b["problemy"] and a["info"] == b["info"] and a["rozmery"] == b["rozmery"]
              and a["spoje"] == b["spoje"] and a["pocet_spoju"] == b["pocet_spoju"] and {k: v for k, v in a["parametry"].items() if k != "system"} == {k: v for k, v in b["parametry"].items() if k != "system"})
    if not shodne:
        rozdil_b += 1
        check(False, f"B) {kw}: stul 45 se lisi od stolu 40")
check(rozdil_b == 0, f"B) 45 == 40 ve vsech {pocet_b} konfiguracich do hloubky 1500 mm (rozdilu {rozdil_b}; {time.time() - t0:.0f} s)")

# stejne s rozsirenymi volbami (panely, LED, vzpery, vyrezy, stredni noha) na hlubce 1500
for kw in (dict(sirka=2200.0, hloubka=1500.0, panely_pocet=2, led=True, vzpery=True), dict(sirka=1800.0, hloubka=1500.0, vyrez1=True, vyrez2=True, vyrez3=True, vyrez1_police=True),
           dict(sirka=2600.0, hloubka=1500.0, stredni_opora="noha", suplik=True, suplik_pocet=3), dict(sirka=1280.0, hloubka=1500.0, loz=True, police=0), dict(sirka=1600.0, hloubka=1500.0, patky=True, kolecka=False)):
    a, ea = sestav(45, **kw)
    b, eb = sestav(40, **kw)
    check(ea == eb and (a is None or (a["dily"] == b["dily"] and a["klice"] == b["klice"] and a["problemy"] == b["problemy"])), f"B2) {kw}: 45 == 40 ({ea} / {eb})")

# ---------------------------------------------------------------- C) hluboky stul: invarianty
def kontrola_hlubokeho(kw, popis):
    r, err = sestav(45, **kw)
    if r is None:
        check(False, f"C) {popis}: StulChyba {err}")
        return None
    check(not r["problemy"], f"C) {popis}: bez problemu ({[p['kod'] for p in r['problemy']]})")
    kl, pos = klice(r), podle_klice(r)
    inf = [i for i in r["info"] if i["kod"] == "stredni_rada_noh"]
    check(len(inf) == 1 and inf[0]["hloubka_mm"] == 1500, f"C) {popis}: informace stredni_rada_noh s prahem 1500 ({inf})")
    nohy_dno = [("bok", "L", "dno"), ("bok", "P", "dno")]
    if not all(k in pos for k in nohy_dno):
        check(False, f"C) {popis}: chybi stredni nohy ({[k for k in nohy_dno if k not in pos]})")
        return r
    xm = (pos[("t", 3)]["position"][0] + pos[("t", 12)]["position"][0]) / 2.0                  # stred hloubky mezi predni a zadni nohou
    for k, roh in ((("bok", "L", "dno"), ("t", 3)), (("bok", "P", "dno"), ("t", 4))):
        d, dr = pos[k], pos[roh]
        check(abs(d["position"][0] - xm) < 0.5, f"C) {popis}: {k} presne v pulce hloubky ({d['position'][0]:.2f} vs {xm:.2f})")
        check(abs(d["position"][2] - dr["position"][2]) < 0.5, f"C) {popis}: {k} v ose bocni nohy ({d['position'][2]:.2f} vs {dr['position'][2]:.2f})")
        check(osa(d) == "Y" and d["part_id"] == "Object_11", f"C) {popis}: {k} je svisly profil Object_11")
    zl, zr = pos[("t", 3)]["position"][2], pos[("t", 4)]["position"][2]
    pricky = [k for k in kl if isinstance(k, tuple) and k[0] == "zmid"]
    check(inf and inf[0]["pricek"] == len(pricky), f"C) {popis}: pocet pricek v informaci = pocet pricek v sestave ({inf[0]['pricek'] if inf else None} / {len(pricky)})")
    x_profily = [d for k, d in pos.items() if isinstance(d, dict) and d["part_id"] == "Object_11" and osa(d) == "X" and abs(d["position"][2] - zl) < 0.5]
    for k in pricky:
        d = pos[k]
        check(osa(d) == "Z" and d["part_id"] == "Object_11", f"C) {popis}: {k} je vodorovny profil pres sirku")
        check(abs(d["position"][0] - xm) < 0.5, f"C) {popis}: {k} v pulce hloubky")
        check(abs(d["position"][2] - (zl + zr) / 2.0) < 0.5, f"C) {popis}: {k} uprostred sirky")
        check(abs(1000.0 * d["scale"][1] - ((zr - zl) - PROFIL)) < 0.5, f"C) {popis}: {k} delka = svetla sirka mezi strednimi nohami ({1000.0 * d['scale'][1]:.1f} vs {(zr - zl) - PROFIL:.1f})")
        check(any(abs(x["position"][1] - d["position"][1] - PROFIL) < 0.5 and abs(x["position"][0] - xm) < 0.5 * 1000.0 * x["scale"][1] for x in x_profily),
              f"C) {popis}: {k} lezi primo pod bocnim pruvlakem (pod bocni pruvlak = o sirku profilu nize)")
        check(d["position"][1] > pos[("bok", "L", "dno")]["position"][1] - 0.5 * 1000.0 * pos[("bok", "L", "dno")]["scale"][1], f"C) {popis}: {k} vyse nez spodek stredni nohy")
    # konec stredni nohy: kolecko (stejneho typu jako u rohovych noh) / patka / zaslepka
    rohova = {pos[("t", i)]["part_id"] for i in (26, 27, 28, 29) if ("t", i) in pos}
    for strana in ("L", "P"):
        if r["parametry"]["kolecka"]:
            kk = ("bok_kolecko", strana)
            check(kk in pos and pos[kk]["part_id"] in rohova and bool(rohova), f"C) {popis}: stredni noha {strana} konci koleckem stejneho typu jako rohove ({pos.get(kk, {}).get('part_id')} / {rohova})")
        else:
            kk = ("konec", ("bok", strana, "dno"))
            check(kk in pos and pos[kk]["part_id"] == pos[("konec", ("t", 3))]["part_id"], f"C) {popis}: stredni noha {strana} konci patkou / zaslepkou stejneho typu jako rohove ({pos.get(kk, {}).get('part_id')} / {pos[('konec', ('t', 3))]['part_id']})")
    return r


t0 = time.time()
HL_C = (1501.0, 1510.0, 1800.0, 2000.0, 2500.0) if not RYCHLE else (1510.0, 2500.0)
SIR_C = (600.0, 1280.0, 2200.0, 3000.0) if not RYCHLE else (1280.0, 3000.0)
VYS_C = (300.0, 450.0, 840.0, 1200.0) if not RYCHLE else (450.0, 840.0)
pocet_c = 0
for hl, sr, vy, pol, kol, sup in itertools.product(HL_C, SIR_C, VYS_C, (0, 1, 2), (True, False), (True, False)):
    kw = dict(hloubka=hl, sirka=sr, vyska=vy, police=pol, kolecka=kol, suplik=sup)
    kontrola_hlubokeho(kw, f"D={hl:g} W={sr:g} H={vy:g} police={pol} kolecka={kol} suplik={sup}")
    pocet_c += 1
for hl, sr, pol, pat in itertools.product((1510.0, 2000.0, 2500.0), (1280.0, 2400.0), (0, 1, 2), (True, False)):          # konce noh bez koleček: patky / zaslepky
    kontrola_hlubokeho(dict(hloubka=hl, sirka=sr, vyska=840.0, police=pol, kolecka=False, patky=pat), f"D={hl:g} W={sr:g} police={pol} bez koleček patky={pat}")
    pocet_c += 1
print(f"  C) {pocet_c} hlubokych konfiguraci ({time.time() - t0:.0f} s)")

# pocty dilu proti systemu 40 stejne sirky (hloubka 1500 -> 2000): + 2 stredni nohy, + 2 kolecka (nebo koncove dily), + pricky, + jejich spojky
for kw in (dict(sirka=1800.0, police=1, kolecka=True, suplik=True), dict(sirka=1800.0, police=0, kolecka=False, suplik=False), dict(sirka=2400.0, police=2, kolecka=True, suplik=False)):
    a, _ = sestav(45, hloubka=2000.0, **kw)
    b, _ = sestav(40, hloubka=1500.0, **kw)
    ka, kb = klice(a), klice(b)
    nove = [k for k in ka if isinstance(k, tuple) and (k[0] == "zmid" or (k[0] == "bok" and k[2] == "dno") or k[0] == "bok_kolecko" or (k[0] == "konec" and k[1] in (("bok", "L", "dno"), ("bok", "P", "dno"))))]
    check(len(nove) >= 5, f"C2) {kw}: aspon 2 stredni nohy + 2 konce + 1 pricka ({len(nove)} novych klicu)")
    check(len(a["dily"]) > len(b["dily"]), f"C2) {kw}: hluboky stul ma vic dilu ({len(a['dily'])} vs {len(b['dily'])})")
    check(a["pocet_spoju"] > b["pocet_spoju"], f"C2) {kw}: hluboky stul ma vic spoju ({a['pocet_spoju']} vs {b['pocet_spoju']})")

# ---------------------------------------------------------------- D) prah 1500 mm a nastavitelny prah podper
a15, _ = sestav(45, hloubka=1500.0, sirka=1800.0)
a151, _ = sestav(45, hloubka=1510.0, sirka=1800.0)
check(not any(isinstance(k, tuple) and k[0] == "zmid" for k in klice(a15)) and not [i for i in a15["info"] if i["kod"] == "stredni_rada_noh"], "D) hloubka 1500: jeste bez stredni rady noh")
check(any(isinstance(k, tuple) and k[0] == "zmid" for k in klice(a151)) and [i for i in a151["info"] if i["kod"] == "stredni_rada_noh"], "D) hloubka 1510: stredni rada noh uz je")
puv = dict(S.PRAVIDLA_SYSTEMU[45]), dict(S.PRAVIDLA_SYSTEMU[40])
try:
    S.nastav_pravidla({"hloubka_stredni_profil": 1200}, system=45)
    check(S.prah_hloubky(45) == 1200.0 and S.prah_hloubky(40) == 900.0, f"D) prah podper nastaveny jen pro system 45 ({S.prah_hloubky(45)} / {S.prah_hloubky(40)})")
    r12, _ = sestav(45, hloubka=1100.0, sirka=1800.0)
    r12_40, _ = sestav(40, hloubka=1100.0, sirka=1800.0)
    check(not any(isinstance(k, tuple) and k[0] in ("podpera_d", "bok") for k in klice(r12)) and any(isinstance(k, tuple) and k[0] in ("podpera_d", "bok") for k in klice(r12_40)),
          "D) pri prahu 1200 ma stul 45 o hloubce 1100 bez podper a bocnich profilu, stul 40 je ma dal")
    r_hlubky, _ = sestav(45, hloubka=1600.0, sirka=1800.0)
    check(r_hlubky is not None and not r_hlubky["problemy"], "D) hluboky stul s prahem podper 1200 je platny")
finally:
    S.PRAVIDLA_SYSTEMU[45], S.PRAVIDLA_SYSTEMU[40] = puv

# ---------------------------------------------------------------- E) nahodne sady voleb (pevne semeno)
rnd = random.Random(20261007)
N_E = 150 if not RYCHLE else 30
stat = {"obe_ok": 0, "stul40_neplatny": 0, "rozdil": 0}
for n in range(N_E):
    b = lambda: rnd.random() < 0.5  # noqa: E731
    P = dict(sirka=float(rnd.randrange(500, 3001, 10)), vyska=float(rnd.randrange(140, 1201, 10)), presah=float(rnd.choice((0, 30, 50, 100))), led_rameno=float(rnd.randrange(200, 1501, 20)),
             stojky=b(), stojky_vyska=float(rnd.randrange(200, 1501, 20)), police=rnd.choice((0, 1, 2, 3)), kolecka=b(), patky=b(), panely=b(), led=b(), panely_pocet=rnd.choice((1, 2)),
             suplik=b(), suplik_pocet=rnd.choice((1, 2, 3)), elektrozlab=b(), drzak_pet=b(), led_svetlo=b(), suplik_vlevo=b(), vzpery=b(), loz=b(), vyrez1=b(), vyrez2=b(), vyrez3=b(), vyrez1_police=b())
    D = float(rnd.randrange(1510, 2501, 10))
    z40, e40 = sestav(40, hloubka=1500.0, **P)
    if z40 is None or z40["problemy"]:
        stat["stul40_neplatny"] += 1
        continue
    z45, e45 = sestav(45, hloubka=D, **P)
    if z45 is None or z45["problemy"]:
        stat["rozdil"] += 1
        check(False, f"E) volby {P}, D={D:g}: stul 40 (D=1500) je platny, hluboky stul 45 ne ({e45 or [p['text'][:100] for p in z45['problemy']]})")
    else:
        stat["obe_ok"] += 1
print(f"  E) nahodne sady: {stat}")
check(stat["obe_ok"] > 0, "E) aspon nektere nahodne sady byly platne v obou systemech")

# ---------------------------------------------------------------- F) ZLOMOVE MIRY PO SYSTEMECH (Robert 2026-10-07: "vsechny zlomove miry ma mit kazdy system svoje")
puv_vse = {s_: dict(S.PRAVIDLA_SYSTEMU[s_]) for s_ in S.SYSTEMY}
try:
    def ma(r, nazev):
        return any(isinstance(k, tuple) and k[0] == nazev or k == nazev for k in klice(r))
    for s_ in S.SYSTEMY:
        check(S.pravidla_vychozi(s_)["hloubka_stredni_noha"] == 1500.0 and S.pravidla_vychozi(s_)["podpera_max_rozpon"] == 800.0 and S.pravidla_vychozi(s_)["min_odstup_stredni_noha"] == 150.0,
              f"F0) system {s_}: vychozi zlomove miry = dosavadni konstanty (1500 / 800 / 150)")
    # F1) hloubka_stredni_noha: pravidlo systemu 45 posouva zlom (a nic jineho)
    S.nastav_pravidla({"hloubka_stredni_noha": 1800}, system=45)
    r17, _ = sestav(45, hloubka=1700.0, sirka=1800.0)
    r181, _ = sestav(45, hloubka=1810.0, sirka=1800.0)
    r15, _ = sestav(45, hloubka=1510.0, sirka=1800.0)
    check(r17 is not None and not ma(r17, "zmid") and ma(r181, "zmid") and not ma(r15, "zmid"), "F1) prah stredni rady noh 1800: 1700 a 1510 mm bez ni, 1810 mm s ni")
    inf = [i for i in r181["info"] if i["kod"] == "stredni_rada_noh"]
    check(inf and inf[0]["hloubka_mm"] == 1800, f"F1) informace nese prah systemu ({inf})")
    check(S.odpoved(dict(system=45, hloubka=1810.0, sirka=1800.0))["hloubka_stredni_noha"] == 1800, "F1) odpoved() nese prah systemu 45")
    S.nastav_pravidla({"hloubka_stredni_noha": 2500}, system=45)
    r25, _ = sestav(45, hloubka=2500.0, sirka=1800.0)
    check(not ma(r25, "zmid"), "F1) prah 2500 = stredni rada se nikdy nepridava")
    # F2) podpera_max_rozpon: mensi nepodepreny usek = vic podper; jen v systemu, kde je zmenena
    S.nastav_pravidla({}, system=45)
    p45a, _ = sestav(45, hloubka=1200.0, sirka=1400.0)
    p40a, _ = sestav(40, hloubka=1200.0, sirka=1400.0)
    n_pod = lambda r: sum(1 for k in klice(r) if isinstance(k, tuple) and k[0] in ("podpera", "podpera_d"))        # noqa: E731
    S.nastav_pravidla({"podpera_max_rozpon": 500}, system=45)
    p45b, _ = sestav(45, hloubka=1200.0, sirka=1400.0)
    p40b, _ = sestav(40, hloubka=1200.0, sirka=1400.0)
    check(n_pod(p45b) > n_pod(p45a) and n_pod(p40b) == n_pod(p40a) and p40b["dily"] == p40a["dily"], f"F2) nejvetsi nepodepreny usek 500 mm: ve 45 vic podper ({n_pod(p45a)} -> {n_pod(p45b)}), ve 40 beze zmeny ({n_pod(p40a)} -> {n_pod(p40b)})")
    # F3) min_odstup_stredni_noha: limit polohy stredni nohy po systemech
    S.nastav_pravidla({}, system=45)
    S.nastav_pravidla({"min_odstup_stredni_noha": 300}, system=40)
    lo40, hi40 = S.stredni_noha_meze(2600, 40)
    lo45, hi45 = S.stredni_noha_meze(2600, 45)
    check(lo40 == 300 and lo45 == 150 and hi40 < hi45, f"F3) meze polohy stredni nohy: system 40 od {lo40:g}, system 45 od {lo45:g}")
    r40_200, e40 = sestav(40, sirka=2600.0, stredni_noha=200.0)
    r45_200, e45 = sestav(45, sirka=2600.0, stredni_noha=200.0)
    check(r40_200 is None and "300" in (e40 or "") and r45_200 is not None and not r45_200["problemy"], f"F3) stredni noha 200 mm od krajni: ve 40 (limit 300) chyba, ve 45 (limit 150) platne ({e40})")
    check(S.odpoved(dict(system=40, sirka=2600.0))["min_odstup_stredni_noha"] == 300 and S.odpoved(dict(system=45, sirka=2600.0))["min_odstup_stredni_noha"] == 150, "F3) odpoved() nese limit systemu")
    # F4) sirka_stredni_noha po systemech (existuje od 2026-10-05): stejny stul ma ve 40 a 45 ruznou stavbu
    S.nastav_pravidla({}, system=40)
    S.nastav_pravidla({"sirka_stredni_noha": 1800}, system=40)
    s40, _ = sestav(40, sirka=1700.0)
    s45, _ = sestav(45, sirka=1700.0)
    ma_oporu = lambda r: any(k in ("FM", "RM") or (isinstance(k, tuple) and k[0] == "ram") for k in klice(r))        # noqa: E731  (stredni opora = stredni nohy FM / RM nebo vestaveny ram)
    check(not ma_oporu(s40) and ma_oporu(s45), "F4) sirka 1700: ve 40 (prah 1800) bez stredni opory, ve 45 (prah 1500) se stredni oporou")
    # F5) SSE: limit polohy stredni nohy je pravidlo systemu SSE (dosud konstanta)
    import stul_sse  # noqa: E402
    S.nastav_pravidla({"min_odstup_stredni_noha": 400}, system=41)
    lo41, _hi41 = stul_sse.stredni_meze(2600)
    check(lo41 - stul_sse.zeme_nohou(2600)[0] == 400, f"F5) SSE: limit polohy stredni nohy z pravidla systemu 41 ({lo41 - stul_sse.zeme_nohou(2600)[0]:g})")
finally:
    for s_, sada in puv_vse.items():
        S.PRAVIDLA_SYSTEMU[s_] = sada
check(all(S.PRAVIDLA_SYSTEMU[s_] == S.PRAVIDLA_VYCHOZI or s_ == 41 for s_ in (30, 35, 40, 45)), "F) po testu jsou pravidla vsech systemu vracena na vychozi")

print(f"\nOK {OK}, selhani {len(FAILS)}")
sys.exit(1 if FAILS else 0)
