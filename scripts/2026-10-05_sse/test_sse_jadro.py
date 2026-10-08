#!/opt/konfigurator/api/venv/bin/python
"""Jadro SSE stolu (system 41; bot8, 2026-10-05) - Robert: „postav novy generator ... v podstate jde o system 40, jen nohy pouziva pouze tyto jeklove s vnitrnim profilem 35x35 pro vyskovou
stavitelnost"; „delku stolu urcuje podelnik tzn deska max 3000 mm, podelnik ma o 10 mm mene aby vesly zaslepky"; „jeklova spojnice nohy SSE muze mit libovolnou delku, od 400 do 1100 mm coz
urcuje hloubku stolu"; „mezera mezi nohama v zakladu: 1570 mm". Bez DB.

  api/venv/bin/python3 scripts/2026-10-05_sse/test_sse_jadro.py

NEZAVISLE MERENI: vsechno se meri z AABB dilu (S._aabb) a z klicu dilu, ne z konstant, ktere pouziva generator; cisla ze zadani (40, 675, 175, 10, 1570 ...) jsou v testu znovu zapsana.
Rozsah: vychozi stul (deska 2000 x 900 -> mezera mezi nohami 1570), mrizka rozmeru / police / supliku, stredni noha a deleni desek, supliky (poloha, strany, hloubka), rozsahy a odmitnute volby,
hash, GLB, koty, nezavislost na systemech 30 / 35 / 40, MUTACE (testovane chyby se musi chytit - viz mutuj_sse.sh)."""
import itertools
import json
import os
import re
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api"))          # izolovana kopie api/ s mutaci (viz mutuj_sse.sh)
import stul_glb as G  # noqa: E402
import stul_koty as K  # noqa: E402
import stul_konfigurator as S  # noqa: E402

fails, total = [], 0


def check(ok, nazev, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(nazev)
        print(f"FAIL {nazev} {detail}")


EPS = 0.02
JEKL, STOJKA, PLECH, ODSAZ, PRIREZ = 40.0, 675.0, 6.0, 175.0, 10.0
SYS = 41


def tup(k):
    return tuple(tup(x) for x in k) if isinstance(k, (list, tuple)) else k


class M:
    """Namerena data stolu SSE z vysledku sestav_stul."""

    def __init__(self, **kw):
        self.r = S.sestav_stul(system=SYS, **kw)
        self.p = self.r["parametry"]
        self.dily, self.klice = self.r["dily"], [tup(k) for k in self.r["klice"]]
        self.bb = [S._aabb(d) for d in self.dily]

    def idx(self, *predikat):
        return [i for i, k in enumerate(self.klice) if k[:len(predikat)] == predikat]

    def lo(self, i):
        return [float(v) for v in self.bb[i][0]]

    def hi(self, i):
        return [float(v) for v in self.bb[i][1]]

    def sj(self, ids):
        return (min(self.lo(i)[0] for i in ids), min(self.lo(i)[1] for i in ids), min(self.lo(i)[2] for i in ids),
                max(self.hi(i)[0] for i in ids), max(self.hi(i)[1] for i in ids), max(self.hi(i)[2] for i in ids))


def blizko(a, b, tol=EPS):
    return abs(float(a) - float(b)) <= tol


def box_zahrnuje(m):
    return bool(m.idx("sse", "box"))


# ---------------------------------------------------------------------------------------------------------------------
print("A) vychozi stul: deska 2000 x 900, mezera mezi nohami 1570 mm")
m = M()
p = m.p
check(p["system"] == 41 and p["sirka"] == 2000.0 and p["hloubka"] == 900.0 and p["vyska"] == 830.0 and p["police"] == 1 and p["suplik"] is True and p["suplik_pocet"] == 2, "vychozi parametry SSE", p)
check(not m.r["problemy"] and not m.r["odebrano"], "vychozi stul bez problemu a bez odebrani", (m.r["problemy"], m.r["odebrano"]))
desky = m.idx("sse", "deska")
x0, y0_, z0, x1, y1, z1 = m.sj(desky)
H, W, D = 830.0, 2000.0, 900.0
check(len(desky) == 1 and blizko(x0, 0, .01) and blizko(x1, D) and blizko(z0, 0, .01) and blizko(z1, W) and blizko(y1, H), "pracovni deska: jeden kus 2000 x 900, horni plocha 830", (x0, x1, z0, z1, y1))
tl = y1 - y0_
check(blizko(tl, 18.0), "deska je 18 mm silna (laminodeska)", tl)
T = y1 - tl                                                     # spodek desky
pod = {k[2]: i for k in m.klice for i in [m.klice.index(k)] if k[:2] == ("sse", "podelnik")}
check(set(pod) == {"pred", "zad"}, "dva podelniky")
for jm, i in pod.items():
    lo, hi = m.lo(i), m.hi(i)
    check(blizko(hi[1], T) and blizko(hi[1] - lo[1], 40) and blizko(hi[0] - lo[0], 40) and blizko(lo[2], 5) and blizko(hi[2], 1995), f"podelnik {jm}: 40x40, horni plocha = spodek desky, z 5 az 1995 (o 10 mm kratsi nez deska)", (lo, hi))
    check(m.dily[i]["part_id"] == "Object_11" and blizko(1000 * m.dily[i]["scale"][1], 1990.0, .01), f"podelnik {jm}: profil 40x40 (Object_11) delky 1990", m.dily[i]["scale"])
check(blizko(m.lo(pod["pred"])[0], 46) and blizko(m.hi(pod["zad"])[0], D - 46), "podelniky: vnejsi lice 46 mm od hrany desky (jekl 40 + plech 6)")
konce = {k: i for i, k in enumerate(m.klice) if k[:2] == ("sse", "konec")}
check(len(konce) == 4 and all(m.dily[i]["part_id"] == "product_3091" for i in konce.values()), "ctyri zaslepky podelniku (product_3091)")
for k, i in konce.items():
    lo, hi = m.lo(i), m.hi(i)
    levy = k[3] == "L"
    celo = 5.0 if levy else 1995.0                          # konec profilu
    check(blizko(lo[2] if levy else hi[2], celo - 3.3 if levy else celo + 3.3, 0.06) and (hi[2] - celo > 5.9 if levy else celo - lo[2] > 5.9), f"zaslepka {k[2:]}: priruba venku (3,3 mm), zatka sedi v profilu", (lo, hi))
nohy = {}
for i, k in enumerate(m.klice):
    if k[:2] == ("sse", "noha"):
        nohy.setdefault(k[2], {})[k[3:]] = i
check(sorted(nohy) == [0, 1], "dve nohy SSE (deska 2000 <= prah 2000)")
for n, d in nohy.items():
    check(set(d) == {("stojka", "pred"), ("stojka", "zad"), ("spojnice",), ("plech", "pred"), ("plech", "zad"), ("profil", "pred"), ("profil", "zad"), ("patka", "pred"), ("patka", "zad")}, f"noha {n}: 9 dilu (2 jekly, spojnice, 2 plechy, 2 profily, 2 zaslepky)", sorted(d))
sp = [m.sj([nohy[n][("stojka", "pred")], nohy[n][("stojka", "zad")]]) for n in (0, 1)]
zl_vnejsi = m.lo(nohy[0][("stojka", "pred")])[2]
zr_vnejsi = m.hi(nohy[1][("stojka", "pred")])[2]
check(blizko(zl_vnejsi, ODSAZ) and blizko(W - zr_vnejsi, ODSAZ), "vnejsi lice noh 175 mm od konce desky", (zl_vnejsi, W - zr_vnejsi))
mezera = m.lo(nohy[1][("stojka", "pred")])[2] - m.hi(nohy[0][("stojka", "pred")])[2]
check(blizko(mezera, 1570.0), "MEZERA MEZI NOHAMI 1570 mm (Robert)", mezera)
check(blizko(m.r["sse"]["mezera_mezi_nohami"], 1570.0), "odpoved nese mezeru mezi nohami")
for n in (0, 1):
    d = nohy[n]
    for jm, xl, xh in (("pred", 0.0, 40.0), ("zad", D - 40, D)):
        i = d[("stojka", jm)]
        lo, hi = m.lo(i), m.hi(i)
        check(m.dily[i]["part_id"] == "sse_jekl_40" and blizko(lo[0], xl) and blizko(hi[0], xh) and blizko(hi[2] - lo[2], 40) and blizko(hi[1] - lo[1], STOJKA) and blizko(hi[1], T),
              f"noha {n} jekl {jm}: 40x40x675, horni konec = spodek desky, vnejsi lice v rovine hrany desky", (lo, hi))
        i = d[("profil", jm)]
        plo, phi = m.lo(i), m.hi(i)
        check(blizko(plo[1], 3.0) and blizko(phi[1], 428.0) and blizko(phi[0] - plo[0], 35) and blizko(phi[2] - plo[2], 35) and blizko((plo[0] + phi[0]) / 2, (xl + xh) / 2) and blizko((plo[2] + phi[2]) / 2, (m.lo(d[("stojka", jm)])[2] + m.hi(d[("stojka", jm)])[2]) / 2),
              f"noha {n} vnitrni profil {jm}: 35x35, od zaslepky (3 mm) do 428 mm, soustredny s jeklem", (plo, phi))
        i = d[("patka", jm)]
        plo, phi = m.lo(i), m.hi(i)
        check(blizko(plo[1], 0.0) and blizko(phi[1], 3.0) and blizko(phi[0] - plo[0], 35), f"noha {n} zaslepka profilu {jm}: 35x35x3 na podlaze")
        i = d[("plech", jm)]
        plo, phi = m.lo(i), m.hi(i)
        zc = (m.lo(d[("stojka", jm)])[2] + m.hi(d[("stojka", jm)])[2]) / 2
        check(blizko(phi[2] - plo[2], 150) and blizko(phi[1] - plo[1], 40) and blizko(phi[0] - plo[0], PLECH) and blizko(phi[1], T) and blizko((plo[2] + phi[2]) / 2, zc)
              and (blizko(plo[0], 40) if jm == "pred" else blizko(phi[0], D - 40)), f"noha {n} plech {jm}: 150x40x6 u horniho konce jeklu, na vnitrni strane", (plo, phi))
        check(blizko(plo[0] + PLECH, m.lo(pod[jm])[0]) if jm == "pred" else blizko(phi[0] - PLECH, m.hi(pod[jm])[0]), f"noha {n}: podelnik {jm} lezi primo na plechu (dotyk celou plochou)")
    i = d[("spojnice",)]
    lo, hi = m.lo(i), m.hi(i)
    check(blizko(hi[0] - lo[0], D - 80) and blizko(lo[0], 40) and blizko(hi[1] - lo[1], 40) and blizko(lo[1] - m.lo(d[("stojka", "pred")])[1], 90.0), f"noha {n} spojnice: 40x40, delka hloubka - 80 = 820, 90 mm nad spodkem jeklu", (lo, hi))
    check(blizko(1000 * m.dily[i]["scale"][1], 820.0, .01), f"noha {n}: delka spojnice 820 (meritko)")
check(blizko(m.r["sse"]["spojnice"], 820.0), "odpoved nese delku spojnice")
y_jeklu = m.lo(nohy[0][("stojka", "pred")])[1]
check(blizko(y_jeklu, H - 18 - 675) and 128.7 - 130 < y_jeklu, "spodek jeklu = vyska desky - 18 - 675")
prekryti = 428.0 - y_jeklu
check(prekryti >= 100 and blizko(m.r["sse"]["preklad_profilu"], prekryti), "vnitrni profil zasahuje do jeklu aspon 100 mm", prekryti)
# police
pol = m.idx("sse", "polic")
px0, py0, pz0, px1, py1, pz1 = m.sj(pol)
check(len(pol) == 1 and blizko(px0, 40) and blizko(px1, D - 60) and blizko(pz0, ODSAZ - 7.5) and blizko(pz1, W - ODSAZ + 7.5) and blizko(py1 - py0, 18), "police: 1665 x 800 x 18 (jako vzor SSE), od predniho jeklu", (px0, px1, pz0, pz1))
check(blizko(py0, m.hi(nohy[0][("spojnice",)])[1]), "police lezi na spojnicich (spodek police = horni hrana spojnice)")
check(blizko(pz1 - pz0, 1665.0) and blizko(px1 - px0, 800.0), "police 1665 x 800 (vzor SSE)")
check(m.dily[pol[0]].get("deska_id") == "pol0_0" and m.dily[desky[0]].get("deska_id") == "prac_0", "deska_id desek")
# box
bx = m.idx("sse", "box")
check(len(bx) == 1 and m.dily[bx[0]]["part_id"] == "product_4930", "dvojsuplikovy box (vychozi)")
bx0, by0, bz0, bx1, by1, bz1 = m.sj(bx)
check(blizko(by1, T - 40, 0.3), "box visi vrchem pod podelniky", (by1, T - 40))
check(blizko(bx0, 46 - 1.2, 0.05) and bx1 < D - 86 + 0.01, "box: predni hrana u predniho podelniku, nesahne za zadni podelnik", (bx0, bx1))
check(blizko(bz1, 1805 - 20 - 40) and blizko(bz1 - bz0, 565.0, 0.2), "vychozi poloha boxu u prave nohy (od lice nohy 40 mm), sirka 565", (bz0, bz1))
check(by0 > py1 + 100, "box nesedi na police", (by0, py1))
pr = m.idx("sse", "box_pricka")
check(len(pr) == 2 and all(m.dily[i]["part_id"] == "Object_11" for i in pr), "dve pricky boxu (profil 40)")
for i in pr:
    lo, hi = m.lo(i), m.hi(i)
    check(blizko(lo[0], m.hi(pod["pred"])[0]) and blizko(hi[0], m.lo(pod["zad"])[0]) and blizko(hi[1], T) and blizko(hi[2] - lo[2], 40), "pricka boxu: mezi vnitrnimi lici podelniku, v rovine podelniku", (lo, hi))
    check(bz0 - 1 <= lo[2] and hi[2] <= bz1 + 1, "pricka je nad boxem (v jeho sirce)")
sps = m.idx("sse", "box_spojka")
check(len(sps) == 4 and all(m.dily[i]["part_id"] == "product_3176" for i in sps), "ctyri rohove spojky 3176 u predniho podelniku")
check(all(m.dily[i]["attached_to"]["prof"] == pod["pred"] for i in sps), "spojky jsou pripojene k predni podelnik")
check(m.r["pocet_spoju"] == 4 and sorted(map(tuple, m.r["spoje"])) == sorted([(pod["pred"], pr[0]), (pod["pred"], pr[1]), (pod["zad"], pr[0]), (pod["zad"], pr[1])]), "4 spoje profil-profil (2 pricky x 2 podelniky)", m.r["spoje"])
check(m.dily[pod["pred"]]["lic_peers"] == sorted(pr + sps) and m.dily[pod["zad"]]["lic_peers"] == sorted(pr), "lic_peers: podelniky drzi pricky a spojky")
check(m.r["suplik_meze"] and m.r["suplik_meze"]["hodnota"] == 0.0 and m.r["suplik_meze"]["vejde"] is True and m.r["suplik_meze"]["max"] > 0 > m.r["suplik_meze"]["min"], "suplik_meze: hodnota 0, rozpeti")
check(m.r["police_meze"] is None and m.r["panely_info"] is None and m.r["stojky_meze"] is None and m.r["vyrezy"] == [] and m.r["max_polic"] == 1, "SSE nema meze polic / panely / stojky / vyrezy")
rz = m.r["rozmery"]
check(blizko(rz["sirka_mm"], 2000, .01) and blizko(rz["hloubka_mm"], 900, .01) and blizko(rz["vyska_mm"], 830, .01) and blizko(rz["y_min"], 0.0, .01), "rozmery stolu 2000 x 900 x 830, podlaha 0", rz)
# zadne nespravne prunikly: jen povolene dvojice
ID_POVOLENE = {("konec", "podelnik"), ("profil", "stojka"), ("spojka", "podelnik"), ("spojka", "pricka"), ("pricka", "podelnik")}


def druh(k):
    if k[1] in ("konec", "podelnik", "box_pricka", "box_spojka", "box", "deska", "polic"):
        return {"konec": "konec", "podelnik": "podelnik", "box_pricka": "pricka", "box_spojka": "spojka", "box": "box", "deska": "deska", "polic": "polic"}[k[1]]
    return k[3]                                      # stojka / spojnice / plech / profil / patka


def pruniky(m):
    out = []
    n = len(m.dily)
    for i in range(n):
        for j in range(i + 1, n):
            ov = [min(m.hi(i)[a], m.hi(j)[a]) - max(m.lo(i)[a], m.lo(j)[a]) for a in range(3)]
            if all(v > 1.0 for v in ov):
                out.append((tup(m.klice[i]), tup(m.klice[j]), [round(v, 1) for v in ov]))
    return out


def povoleno(a, b):
    da, db = druh(a), druh(b)
    return {da, db} in ({"konec", "podelnik"}, {"profil", "stojka"}, {"spojka", "podelnik"}, {"spojka", "pricka"}, {"patka", "stojka"})


for a, b, ov in pruniky(m):
    check(povoleno(a, b), f"nedovoleny prunik {a} x {b}", ov)

# ---------------------------------------------------------------------------------------------------------------------
print("B) mrizka rozmeru, police, supliku: invarianty z AABB")
Ws = (800, 1280, 1500, 2000)
Ds = (480, 600, 720, 900, 1100, 1180)
Hs = (700, 830, 1000)
n_grid = 0
for W, D, H in itertools.product(Ws, Ds, Hs):
    for police, suplik in ((1, True), (0, False), (1, False)):
        kw = dict(sirka=W, hloubka=D, vyska=H, police=police, suplik=suplik)
        m = M(**kw)
        n_grid += 1
        T = H - 18
        d_ = m.idx("sse", "deska")
        a = m.sj(d_)
        check(blizko(a[3] - a[0], D) and blizko(a[5] - a[2], W) and blizko(a[4], H), f"{kw}: deska {W}x{D}, horni plocha {H}", a)
        po = {k[2]: i for i, k in enumerate(m.klice) if k[:2] == ("sse", "podelnik")}
        check(all(blizko(1000 * m.dily[i]["scale"][1], W - 10, .01) and blizko(m.hi(i)[1], T) for i in po.values()), f"{kw}: podelniky W - 10, horni plocha = spodek desky")
        nn = {}
        for i, k in enumerate(m.klice):
            if k[:2] == ("sse", "noha"):
                nn.setdefault(k[2], {})[k[3:]] = i
        check(len(nn) == 2, f"{kw}: dve nohy (W <= 2000)")
        sp_ = m.dily[nn[0][("spojnice",)]]
        check(blizko(1000 * sp_["scale"][1], D - 80, .01) and 400 <= D - 80 <= 1100, f"{kw}: spojnice D - 80 v rozsahu 400-1100")
        y0 = T - 675
        for jm in ("pred", "zad"):
            check(blizko(m.lo(nn[0][("stojka", jm)])[1], y0) and blizko(m.hi(nn[0][("plech", jm)])[1], T) and blizko(m.hi(nn[0][("profil", jm)])[1], 428.0), f"{kw}: vyska jeklu / plechu / profilu")
        check(428.0 - y0 >= 100 - 1e-9 and y0 >= 3.0, f"{kw}: prekryti profilu v jeklu >= 100 mm a jekl nad zaslepkou", y0)
        gap = m.lo(nn[1][("stojka", "pred")])[2] - m.hi(nn[0][("stojka", "pred")])[2]
        check(blizko(gap, W - 430), f"{kw}: mezera mezi nohami W - 430", gap)
        pol_ = m.idx("sse", "polic")
        check(bool(pol_) == bool(police), f"{kw}: police podle parametru")
        if pol_:
            q = m.sj(pol_)
            check(blizko(q[1], y0 + 130) and blizko(q[4] - q[1], 18) and blizko(q[5] - q[2], W - 335) and blizko(q[3] - q[0], D - 100), f"{kw}: police na spojnicich {W - 335} x {D - 100}", q)
        if suplik and D >= 720:
            check(box_zahrnuje(m) and not m.r["odebrano"], f"{kw}: box je a nic se neodebralo", m.r["odebrano"])
        if suplik and D < 714:
            check(not box_zahrnuje(m) and [o["volba"] for o in m.r["odebrano"]] == ["suplik"] and not m.r["problemy"], f"{kw}: box se nevejde (hluboky aspon 714) -> odebran jako suplik", (m.r["odebrano"], m.r["problemy"]))
        if not suplik:
            check(not box_zahrnuje(m) and not m.idx("sse", "box_pricka") and not m.idx("sse", "box_spojka"), f"{kw}: bez supliku zadny box ani pricky ani spojky")
        bad = [(a_, b_) for a_, b_, ov in pruniky(m) if not povoleno(a_, b_)]
        check(not bad, f"{kw}: zadne nedovolene pruniky", bad[:3])
check(n_grid == len(Ws) * len(Ds) * len(Hs) * 3, "mrizka B odebehla cela")

# ---------------------------------------------------------------------------------------------------------------------
print("C) stredni noha (sirka nad pravidlem sirka_stredni_noha SSE = 2000) a deleni desek")
for W in (2010, 2400, 2800, 3000):
    m = M(sirka=W)
    nn = sorted({k[2] for k in m.klice if k[:2] == ("sse", "noha")})
    check(nn == [0, 1, 2], f"W={W}: tri nohy (krajni + stredni)")
    zs = [(m.lo(i)[2] + m.hi(i)[2]) / 2 for i, k in enumerate(m.klice) if k[:2] == ("sse", "noha") and k[3:] == ("spojnice",)]
    zs.sort()
    check(blizko(zs[0], 195) and blizko(zs[2], W - 195) and blizko(zs[1], W / 2), f"W={W}: stredni noha uprostred", zs)
    d_ = sorted(m.idx("sse", "deska"), key=lambda i: m.lo(i)[2])
    check(len(d_) == 2 and blizko(m.hi(d_[0])[2], W / 2) and blizko(m.lo(d_[1])[2], W / 2) and blizko(m.lo(d_[0])[2], 0, .01) and blizko(m.hi(d_[1])[2], W), f"W={W}: pracovni deska deli v ose stredni nohy")
    check([m.dily[i]["deska_id"] for i in d_] == ["prac_0", "prac_1"], f"W={W}: deska_id prac_0 / prac_1")
    check(all(S.deska_se_vejde_do_tabule(m.hi(i)[0] - m.lo(i)[0], m.hi(i)[2] - m.lo(i)[2]) for i in d_), f"W={W}: obe desky se vejdou do tabule 2070 x 2800")
    p_ = sorted(m.idx("sse", "polic"), key=lambda i: m.lo(i)[2])
    check(len(p_) == 2 and blizko(m.hi(p_[0])[2], W / 2) and blizko(m.lo(p_[1])[2], W / 2) and [m.dily[i]["deska_id"] for i in p_] == ["pol0_0", "pol0_1"], f"W={W}: police se deli v ose stredni nohy")
    rails = m.idx("sse", "podelnik")
    check(len(rails) == 2 and all(blizko(1000 * m.dily[i]["scale"][1], W - 10, .01) for i in rails), f"W={W}: podelniky zustavaji cele (W - 10)")
    check(m.r["sse"]["stredni"] is not None and blizko(m.r["sse"]["stredni"], W / 2), f"W={W}: odpoved nese polohu stredni nohy")
    bad = [(a_, b_) for a_, b_, ov in pruniky(m) if not povoleno(a_, b_)]
    check(not bad, f"W={W}: zadne nedovolene pruniky", bad[:3])
m = M(sirka=2000)
check(len({k[2] for k in m.klice if k[:2] == ("sse", "noha")}) == 2, "W=2000: prah je 'nad' 2000 (dve nohy)")
m = M(sirka=2400, stredni_noha=900)
zs = sorted((m.lo(i)[2] + m.hi(i)[2]) / 2 for i, k in enumerate(m.klice) if k[:2] == ("sse", "noha") and k[3:] == ("spojnice",))
check(blizko(zs[1], 195 + 900), "stredni_noha = 900 mm od osy leve nohy", zs)
d_ = sorted(m.idx("sse", "deska"), key=lambda i: m.lo(i)[2])
check(blizko(m.hi(d_[0])[2], 1095) and blizko(m.lo(d_[1])[2], 1095), "deska se deli v ose posunute stredni nohy")
for spatne in (100, 149, 2000):
    try:
        M(sirka=2400, stredni_noha=spatne)
        check(False, f"stredni_noha {spatne} mimo meze musi vyhodit chybu")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"stredni_noha {spatne}: StulChyba mimo_rozsah", e.kod)
m = M(sirka=2400, stredni_noha=150)
check(m.r["sse"]["stredni"] is not None, "stredni_noha 150 (nejmensi odstup) je v poradku")
m = M(sirka=2000, stredni_noha=999)
check(len({k[2] for k in m.klice if k[:2] == ("sse", "noha")}) == 2, "stredni_noha u uzsiho stolu se ignoruje (zadna stredni noha)")
# vlastni prah pravidla
S.nastav_pravidla({"sirka_stredni_noha": 1500}, system=41)
m = M(sirka=2000)
check(len({k[2] for k in m.klice if k[:2] == ("sse", "noha")}) == 3, "pravidlo sirka_stredni_noha = 1500 v SSE: u 2000 mm je stredni noha")
m30 = S.sestav_stul(system=30, sirka=1600, panely=False, led=False, stojky=False, suplik=False)
check(any(k in ("FM", "RM") for k in m30["klice"]), "pravidlo SSE nemeni system 30 (prah 1500)")
S.nastav_pravidla({}, system=41)
check(S.prah_sirky(41) == 2000.0 and S.prah_sirky(30) == 1500.0, "vychozi prah SSE 2000, system 30 1500")

# ---------------------------------------------------------------------------------------------------------------------
print("D) supliky: posun, strana, pocet, meze")
m0 = M()
bz = lambda m: m.sj(m.idx("sse", "box"))
d0 = bz(m0)
mm = m0.r["suplik_meze"]
for posun in (-300.0, -50.0, 0.0, 120.0):
    m = M(suplik_posun=posun)
    b = bz(m)
    check(blizko(b[5] - d0[5], max(mm["min"], min(mm["max"], posun)), 0.15), f"suplik_posun {posun}: box se posunul o {posun} (v mezich)", (b[5], d0[5]))
for posun in (-5000.0, 5000.0):
    m = M(suplik_posun=posun)
    b = bz(m)
    check(blizko(m.r["suplik_meze"]["hodnota"], mm["min"] if posun < 0 else mm["max"], 0.15) and 14.9 <= b[2] and b[5] <= 2000 - 14.9, f"suplik_posun {posun}: orizne se na meze rozpeti podelniku, od konce >= 15 mm", (b, mm))
    check(not m.r["problemy"] and not m.r["odebrano"], f"suplik_posun {posun}: bez problemu (jen se orizne)")
mv = M(suplik_vlevo=True)
b = bz(mv)
check(blizko(b[2], 195 + 20 + 40) and blizko(b[5] - b[2], 565.0, .2), "suplik_vlevo: box u leve nohy (od lice nohy 40 mm)", b)
mv = M(suplik_vlevo=True, suplik_posun=100.0)
check(blizko(bz(mv)[2], 195 + 20 + 40 - 100.0), "suplik_vlevo: kladny posun = k levemu konci")
for pocet, vyska in ((1, 180), (2, 280), (3, 450)):
    m = M(suplik_pocet=pocet)
    b = bz(m)
    check(m.dily[m.idx("sse", "box")[0]]["part_id"] == S.SUPLIK_PARTY[pocet] and blizko(b[4] - b[1], vyska, 0.3) and blizko(b[4], 830 - 18 - 40, 0.3), f"suplik_pocet {pocet}: box vysoky {vyska}, vrch pod podelniky", b)
    check(b[1] > M().sj(M().idx("sse", "polic"))[4] + 20, f"suplik_pocet {pocet}: nad policí je volno")
m = M(hloubka=700)
check(not box_zahrnuje(m) and [o["volba"] for o in m.r["odebrano"]] == ["suplik"] and "nevejde" in m.r["odebrano"][0]["text"], "hloubka 700: box se nevejde mezi podelniky a odebere se", m.r["odebrano"])
m = M(hloubka=720)
check(box_zahrnuje(m) and blizko(bz(m)[3], 46 - 1.2 + 583.1, 0.2) and bz(m)[3] <= 720 - 86 + 0.01, "hloubka 720: box se jeste vejde")
dv = S.dostupnost(system=41, hloubka=700)
check(dv["suplik"] and "nevejde" in dv["suplik"] and all(dv[k] and "SSE" in dv[k] for k in ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "navlek", "vzpery")), "dostupnost: supliky se u hloubky 700 nevejdou, ostatni volby SSE nema", dv)
check(S.dostupnost(system=41)["suplik"] is None, "dostupnost: supliky lze (vychozi)")
check(S.nabidky_roztazeni(system=41) == {} and S.nabidky_police(system=41) is None, "nabidky roztazeni / police: SSE nema")

# ---------------------------------------------------------------------------------------------------------------------
print("E) rozsahy a nepodporovane volby")
for kw, kod in (({"sirka": 799}, "mimo_rozsah"), ({"sirka": 3001}, "mimo_rozsah"), ({"hloubka": 479}, "mimo_rozsah"), ({"hloubka": 1181}, "mimo_rozsah"), ({"vyska": 699}, "mimo_rozsah"), ({"vyska": 1001}, "mimo_rozsah"),
                ({"police": 2}, "mimo_rozsah"), ({"stojky": True}, "nepodporovano"), ({"kolecka": True}, "nepodporovano"), ({"panely": True}, "nepodporovano"), ({"led": True}, "nepodporovano"),
                ({"elektrozlab": True}, "nepodporovano"), ({"drzak_pet": True}, "nepodporovano"), ({"patky": True}, "nepodporovano"), ({"navlek": True}, "nepodporovano"), ({"vzpery": True}, "nepodporovano"),
                ({"loz": True}, "nepodporovano"), ({"vyrez1": True}, "nepodporovano"), ({"vyrez2_police": True}, "nepodporovano"), ({"stredni_opora": "ram"}, "nepodporovano")):
    try:
        S.sestav_stul(system=41, **kw)
        check(False, f"{kw}: musi vyhodit StulChyba")
    except S.StulChyba as e:
        check(e.kod == kod, f"{kw}: StulChyba {kod}", e.kod)
for kw in ({"sirka": 800}, {"sirka": 3000}, {"hloubka": 480}, {"hloubka": 1180}, {"vyska": 700}, {"vyska": 1000}, {"police": 0}, {"stojky": False, "panely": False, "led": False}, {"presah": 77, "led_rameno": 400}):
    S.sestav_stul(system=41, **kw)
    check(True, f"{kw}: platne meze")
a = S._norm_parametry({"system": 41, "presah": 77, "led_rameno": 400, "pet_noha": "ZP", "panely_pocet": 3, "stojky_vyska": 800})
b = S._norm_parametry({"system": 41})
check(a == b, "nepouzivane cisla se normalizuji na vychozi (jeden stav = jeden hash)", {k: (a[k], b[k]) for k in a if a[k] != b[k]})
check(all(b[k] is False for k in ("stojky", "kolecka", "panely", "led", "elektrozlab", "drzak_pet", "patky", "navlek", "vzpery", "loz", "vyrez1", "vyrez2", "vyrez3")), "nepodporovane prepinace jsou ve vychozim stavu vypnute")
try:
    S.sestav_stul(system=41, neznamy=1)
    check(False, "neznamy parametr")
except S.StulChyba as e:
    check(e.kod == "neznamy_parametr", "neznamy parametr -> StulChyba")

# ---------------------------------------------------------------------------------------------------------------------
print("F) hash, GLB, koty")
h0 = G.kanonicky_hash({"system": 41})
check(h0 == G.kanonicky_hash({"system": 41, "sirka": 2000, "hloubka": 900, "vyska": 830}) and h0 == G.kanonicky_hash({"system": "41"}), "vychozi hash je stabilni (vychozi hodnoty = zadane)")
for kw in ({"sirka": 2010}, {"hloubka": 910}, {"vyska": 840}, {"police": 0}, {"suplik": False}, {"suplik_pocet": 3}, {"suplik_posun": 10.0}, {"suplik_vlevo": True}):
    check(G.kanonicky_hash({"system": 41, **kw}) != h0, f"{kw}: jiny hash")
check(len({G.kanonicky_hash({"system": s_}) for s_ in (30, 35, 40, 41)}) == 4, "ctyri systemy = ctyri ruzne hashe")
check(G.kanonicky_hash({}) == "87a80526a7ae21aa", "hash vychoziho stolu systemu 30 beze zmeny")
S.nastav_pravidla({"sirka_stredni_noha": 1500}, system=41)
h1 = G.kanonicky_hash({"system": 41, "sirka": 1800})
S.nastav_pravidla({}, system=41)
check(h1 != G.kanonicky_hash({"system": 41, "sirka": 1800}), "prah stredni nohy SSE zmeni hash SSE")
check(G.kanonicky_hash({"system": 41, "sirka": 1800}) == G.kanonicky_hash({"system": 41, "sirka": 1800}) and G.kanonicky_hash({"system": 40}) == G.kanonicky_hash({"system": 40}), "hash je deterministicky")
hh, data = G.model_pro_parametry({"system": 41})
check(hh == h0 and data[:4] == b"glTF", "model_pro_parametry: GLB a hash", hh)
n_, t_ = struct.unpack("<II", data[12:20])
js = json.loads(data[20:20 + n_])
v3d = js["scenes"][0]["extras"]["v3d"]
check(v3d["box"]["max"][1] > 829.9 and abs(v3d["box"]["max"][2] - v3d["box"]["min"][2] - 2000) < 0.05 and abs(v3d["box"]["max"][0] - v3d["box"]["min"][0] - 900) < 0.05, "GLB: obalka 2000 x 900 x 830", v3d["box"])
mats = [mt["pbrMetallicRoughness"]["baseColorFactor"][:3] for mt in js["materials"]]
check(G.MATERIALY["ral7016"]["baseColorFactor"][:3] in mats, "GLB: jekly a plechy jsou v RAL 7016")
koty = {k["t"]: k for k in K.koty(S.sestav_stul(system=41))}
check(set(koty) >= {"830", "2 000", "900", "772", "285", "1 570"}, "koty: vyska, delka, hloubka, vnitrni vyska, police, mezera mezi nohami 1 570", sorted(koty))
mk = M()
nz = {n: m_i for n in (0, 1) for m_i in [mk.idx("sse", "noha", n, "stojka", "pred")[0]]}
kg = [k for k in K.koty(S.sestav_stul(system=41)) if k["t"] == "1 570"]
check(len(kg) == 1 and blizko(kg[0]["a"][2], mk.hi(nz[0])[2]) and blizko(kg[0]["b"][2], mk.lo(nz[1])[2]) and blizko(kg[0]["a"][1], 0.0) and blizko(kg[0]["b"][1], 0.0)
      and blizko(kg[0]["a"][0], mk.lo(nz[0])[0]) and kg[0]["o"][0] < 0, "kota mezery mezi nohami: konce meri od vnitrniho lice leve nohy k vnitrnimu lici prave, na podlaze pred stolem", kg)
kk = K.koty(S.sestav_stul(system=41, sirka=3000))
check(sorted(k["t"] for k in kk).count("1 265") == 2, "koty: u 3 noh dve mezery 1 265", [k["t"] for k in kk])
kk = K.koty(S.sestav_stul(system=41, police=0))
check("285" not in [k["t"] for k in kk], "koty: bez police zadna kota police")
hs = {}
for W_, D_, H_ in ((800, 480, 700), (3000, 1180, 1000), (2000, 900, 830)):
    hh, data = G.model_pro_parametry({"system": 41, "sirka": W_, "hloubka": D_, "vyska": H_})
    n_, t_ = struct.unpack("<II", data[12:20])
    bx_ = json.loads(data[20:20 + n_])["scenes"][0]["extras"]["v3d"]["box"]
    check(abs((bx_["max"][2] - bx_["min"][2]) - W_) < 0.05 and abs((bx_["max"][0] - bx_["min"][0]) - D_) < 0.05 and abs(bx_["max"][1] - H_) < 0.05, f"GLB {W_}x{D_}x{H_}: obalka odpovida", bx_)

# ---------------------------------------------------------------------------------------------------------------------
print("G) ostatni systemy beze zmeny (30 / 35 / 40 nezavisi na SSE)")
for sy in (30, 35, 40):
    r = S.sestav_stul(system=sy)
    check(not any(k and k[0] == "sse" for k in r["klice"] if isinstance(k, list)) and S.system_z_dilu(r["dily"]) == sy, f"system {sy}: zadne dily SSE, system_z_dilu = {sy}")
    check("sse" not in r, f"system {sy}: odpoved nema klic sse")
check(S.system_z_dilu(S.sestav_stul(system=41)["dily"]) == 41, "system_z_dilu pozna SSE (profil Object_11 je i v systemu 40)")
check(S.PROFIL_PARTS == ("Object_7", "profil_35x35", "Object_11"), "PROFIL_PARTS bez duplicit", S.PROFIL_PARTS)
for e in S.entries_pro_cenu(S.sestav_stul(system=41)["dily"]):
    check(e["part_id"] not in S.SSE_PARTS, "cenikove polozky nemaji dily nohy SSE (cena je pravidlo)")
ep = S.entries_pro_cenu(S.sestav_stul(system=41)["dily"])
check(sorted(e["part_id"] for e in ep if e["part_id"].startswith("Object")) == ["Object_11"] * 4 and sum(1 for e in ep if e["part_id"] == "product_4933") == 2, "cenikove polozky: 4 profily 40 (2 podelniky + 2 pricky), 2 desky", ep)
rails = [e for e in ep if e["part_id"] == "Object_11"]
check(sorted(round(e["length_mm"]) for e in rails) == [728, 728, 1990, 1990] and sum(e["joint_count"] for e in rails) == 4, "delky profilu 1990 x 2, 728 x 2 (D - 172), 4 spoje", [(e["length_mm"], e["joint_count"]) for e in rails])

# ---------------------------------------------------------------------------------------------------------------------
print("H) ovladani ve 3D (casti, tahy, zive tazeni supliku, verejne preklady cs / en / sk)")
import stul_ovladani_verejne as OV  # noqa: E402
for kw in ({}, {"sirka": 2600}, {"sirka": 3000, "suplik_vlevo": True}, {"police": 0, "suplik": False}, {"suplik_pocet": 3, "suplik_posun": 100.0}, {"hloubka": 700}, {"sirka": 2400, "stredni_noha": 900}):
    m = M(**kw)
    r = m.r
    ov = S.ovladani_3d(r)
    ids = [c["id"] for c in ov["casti"]]
    nn = len(r["sse"]["nohy"])
    check(ids[0] == "deska" and [i for i in ids if i.startswith("noha_")] == [f"noha_{n}" for n in range(nn)], f"{kw}: casti: deska + {nn} nohy", ids)
    check(("police_1" in ids) == bool(r["parametry"]["police"]) and ("suplik" in ids) == box_zahrnuje(m), f"{kw}: cast police / suplik jen kdyz existuji", ids)
    tahy = {t["id"]: t for t in ov["tahy"]}
    check(set(tahy) == {"vyska", "sirka", "hloubka"} | ({"suplik_posun"} if box_zahrnuje(m) else set()), f"{kw}: tahy", sorted(tahy))
    for tid, par in (("vyska", "vyska"), ("sirka", "sirka"), ("hloubka", "hloubka")):
        t = tahy[tid]
        lo_, hi_ = S.SYSTEMY[41]["rozsah"][par]
        check(t["param"] == par and t["min"] == lo_ and t["max"] == hi_ and t["hodnota"] == r["parametry"][par] and lo_ <= t["hodnota"] <= hi_ and t["mereni"][0]["param"] == par, f"{kw}: tah {tid}: meze a hodnota")
    dsk = m.sj(m.idx("sse", "deska"))
    check(tahy["sirka"]["bod"] == [round((dsk[0] + dsk[3]) / 2, 1), round(dsk[4], 1), round(dsk[5], 1)] and tahy["sirka"]["faktor"] == 2.0 and tahy["hloubka"]["bod"][0] == round(dsk[0], 1) and tahy["hloubka"]["faktor"] == 2.0,
          f"{kw}: uchyt sirky na prave hrane desky, hloubky na predni hrane (faktor 2: model je vystredeny)")
    j0 = m.idx("sse", "noha", 0, "stojka", "pred")[0]
    check(blizko(tahy["vyska"]["bod"][1], m.hi(j0)[1], 0.06) and blizko(tahy["vyska"]["bod"][2], (m.lo(j0)[2] + m.hi(j0)[2]) / 2, 0.06), f"{kw}: uchyt vysky na hornim konci jeklu leve nohy")
    check(ov["deska"]["sirka"] == r["parametry"]["sirka"] and ov["deska"]["hloubka"] == r["parametry"]["hloubka"], f"{kw}: deska v ovladani")
    c_ = {c["id"]: c for c in ov["casti"]}
    check(all(bool(c["menu"]) and c["aabb"][0][0] < c["aabb"][1][0] for c in ov["casti"]), f"{kw}: kazda cast ma nabidku a obalku")
    for n in range(nn):
        pts = m.idx("sse", "noha", n)
        a_ = c_[f"noha_{n}"]["aabb"]
        check(a_[0][2] <= min(m.lo(i)[2] for i in pts) + 0.1 and a_[1][2] >= max(m.hi(i)[2] for i in pts) - 0.1, f"{kw}: obalka nohy {n} zahrnuje vsechny jeji dily")
    check(("Střední nohu vrátit doprostřed" in [x["text"] for x in c_["noha_1"]["menu"]]) == (nn == 3), f"{kw}: nabidka 'Stredni nohu vratit doprostred' jen u stredni nohy")
    check(all(("Přidat spodní polici" in [x["text"] for x in c_[f"noha_{n}"]["menu"]]) == (not r["parametry"]["police"]) for n in range(nn)), f"{kw}: nabidka 'Pridat spodni polici' u noh jen bez police")
    if "suplik_posun" in tahy:
        t = tahy["suplik_posun"]
        sm = r["suplik_meze"]
        check(t["min"] == sm["min"] and t["max"] == sm["max"] and t["hodnota"] == sm["hodnota"] and t["osa"] == ([0.0, 0.0, -1.0] if r["parametry"]["suplik_vlevo"] else [0.0, 0.0, 1.0]), f"{kw}: tah supliku: meze, hodnota, osa")
        ix = t["zive"][0]["ix"]
        check(t["zive"][0]["op"] == "posun" and t["zive"][0]["k"] == 1.0 and sorted(ix) == sorted(m.idx("sse", "box") + m.idx("sse", "box_pricka") + m.idx("sse", "box_spojka")), f"{kw}: zive tazeni hybe box, pricky a spojky")
        d_ = 50.0 if sm["hodnota"] + 50.0 <= sm["max"] else -50.0
        m2 = M(**{**kw, "suplik_posun": sm["hodnota"] + d_})
        os_ = t["osa"][2]
        ok = all(blizko(m2.lo(i)[2] - m.lo(i)[2], d_ * os_, 0.15) and blizko(m2.hi(i)[2] - m.hi(i)[2], d_ * os_, 0.15) and blizko(m2.lo(i)[0], m.lo(i)[0]) and blizko(m2.lo(i)[1], m.lo(i)[1]) for i in ix)
        check(ok and m2.r["suplik_meze"]["hodnota"] == round(sm["hodnota"] + d_, 1), f"{kw}: zive tazeni o {d_:g} mm = model s posunem {sm['hodnota'] + d_:g} (kazdy dil sedi)")
    vod = G.vodici(r["parametry"], {**r, "ovladani_scena": ov})
    for lang in ("cs", "en", "sk"):
        try:
            o = OV.ovladani_verejne(vod["ovladani"], lang, 40)
            check(len(o["casti"]) == len(ov["casti"]) and {t["id"] for t in o["tahy"]} <= {"h", "w", "d", "boxpos"} and all(x["label"] for x in o["casti"]), f"{kw} [{lang}]: verejne ovladani")
        except OV.ChybiPreklad as e:
            check(False, f"{kw} [{lang}]: chybi preklad", str(e))
    en = OV.ovladani_verejne(vod["ovladani"], "en", 40)
    check(not any(re.search(r"laminodesk|spojk|katalog|SKU|profil 30", json.dumps(en, ensure_ascii=False), re.I) for _ in (0,)), f"{kw}: v anglickem ovladani zadne zakazane vyrazy")
    cs_txt = json.dumps(OV.ovladani_verejne(vod["ovladani"], "cs", 40), ensure_ascii=False)
    check(not re.search(r"laminodesk|spojk|katalog|SKU|profil 30", cs_txt, re.I), f"{kw}: v ceskem ovladani zadne zakazane vyrazy")
    check(OV.ovladani_verejne(vod["ovladani"], "cs", 40)["deska"]["sirka"] == r["parametry"]["sirka"], f"{kw}: verejne ovladani nese rozmery desky")
    check("noha_0" not in json.dumps(OV.ovladani_verejne(vod["ovladani"], "cs", 40)) and "leg1" in [c["id"] for c in OV.ovladani_verejne(vod["ovladani"], "cs", 40)["casti"]], f"{kw}: verejna id casti bez indexu dilu (leg1...)")

print(f"\n{total - len(fails)}/{total} kontrol OK" if not fails else f"\n{len(fails)} CHYB z {total}")
sys.exit(1 if fails else 0)
