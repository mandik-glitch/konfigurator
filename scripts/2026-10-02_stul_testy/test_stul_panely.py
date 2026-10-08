#!/usr/bin/env python3
"""Test PANELU VSAZENYCH DO PROFILU, VESTAVENEHO RAMU, VYSKY STOJEK a ELEKTROZLABU (bot8, 2026-10-05; Robert: "U generatoru 30/40 doplnit moznosti: ...").

NEZAVISLE na kodu generatoru (vse se meri z AABB dilu, ocekavane hodnoty z rozmeru profilu a panelu 1190 x 460 x 15):
  A) vychozi stul (sirka 1280, 1 panel): panel sedi MEZI zadnimi stojkami v jejich rovine, nad a pod nim podelny profil, mezera 1 mm, zadny profil podel kratkych stran, profily se
     opiraji o stojky, spodni profil 2 mm nad zadni prickou rámu desky, zadny dil nezasahuje do panelu, spoje == definice spoje z dimension_match_fbx.
  B) nejmensi sirka stolu z delky panelu (1190 + 2 x 1 + 2 x profil): na hranici mezera presne 1 mm, o kousek uzsi stul = panel se samo odebere.
  C) vyska zadnich stojek (zkracovani / natahovani): vrch stojky nad zadni prickou = zadana vyska, rameno LED jede se stojkou, nejnizsi vyska podle panelu.
  D) posun panelu po stojkach (panely_posun): spodni profil o presne tolik vys, nejvyssi poloha = vrch profilu u vrchu stojky, elektrozlab jede s panelem.
  E) pocet panelu po jednom kuse: rady nad sebou (profil mezi radami), vedle sebe ve dvou useccich mezi stredni nohou, prazdny usek nema zadny profil, orez nad kapacitu.
  F) vestaveny ram misto strednich noh: 4 vodorovne podelniky zustavaji CELE, prícky a svisle profily podle skici (horni prícka od predniho po zadni pracovni podelnik, dolni od predniho po
     zadni podelnik police), deska police s vyrezem pro ram (kusy bez prekryvu), rám jen s policí, rezim `auto`.
  G) elektrozlab: vzdy se dotyka panelu nebo profilu (zadnim licem), meze posunu presne (na mezi opora, o 10 mm dal ne), jede s panelem.
  H) cena (polozky) a vyrobni vypis, hash (kod konfigurace) a 3D ovladani nových tahu.
Spusteni z korene repa (bez DB):  api/venv/bin/python3 scripts/2026-10-02_stul_testy/test_stul_panely.py
V systemu 40:  api/venv/bin/python3 scripts/2026-10-04_system40/spust_v_systemu.py 40 scripts/2026-10-02_stul_testy/test_stul_panely.py
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1."""
import itertools
import math
import os
import sys
import threading

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
    sys.path.insert(0, API)
    import app  # noqa: F401,E402 - jako v ostrem behu
    import dimension_match_fbx as dmf  # noqa: E402
    import qa_checks  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
finally:
    threading.Thread.start = _orig

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        if len(FAILS) <= 60:
            print(f"  CHYBA: {msg}")


SYS = S.VYCHOZI["system"]
P = float(S.SYSTEMY[SYS]["profil_mm"])               # sirka profilu: 30 / 40
H = P / 2.0
PANEL_S, PANEL_V, PANEL_T = 1190.0, 460.0, 15.0     # panel: sirka (Z), vyska (Y), tloustka (X) - katalog 4931
MEZERA = 1.0                                        # mezera panel - profil (Robert)
ODSTUP_PRICKA = 2.0                                 # spodni profil v nejnizsi poloze 2 mm nad zadni prickou ramu desky (aby se nepocital jako spoj)
USEK = PANEL_S + 2 * MEZERA                         # nejmensi volna sirka mezi stojkami = 1192
MIN_SIRKA = math.ceil(USEK + 2 * P)                 # 1252 / 1272
MIN_SIRKA_NOHY = math.ceil(2 * USEK + 3 * P)        # nejuzsi stul, kdy se panel vejde do useku mezi stredni nohou uprostred: 2474 / 2504
MIN_STOJKY = math.ceil(ODSTUP_PRICKA + PANEL_V + 2 * MEZERA + 2 * P)       # nejnizsi zadni stojky nad deskou pro jednu radu: 524 / 544
NOHA = dict(stredni_opora="noha")
PROFIL_GLB = {p_: p_ + ".glb" for p_ in S.PROFIL_PARTS}


def kl(r):
    return [tuple(k) if isinstance(k, list) else k for k in r["klice"]]


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def casti(r, pred):
    """[(index, klic, dil)] dilu, jejichz klic splnuje `pred`."""
    return [(i, k, r["dily"][i]) for i, k in enumerate(kl(r)) if pred(k)]


def panely(r):
    return sorted([(i, k, d) for i, k, d in casti(r, lambda k: isinstance(k, tuple) and k[0] == "pan")], key=lambda x: (x[1][1], x[1][2]))


def listy(r):
    return sorted([(i, k, d) for i, k, d in casti(r, lambda k: isinstance(k, tuple) and k[0] == "panrail")], key=lambda x: (x[1][1], x[1][2]))


def dil(r, klic):
    return r["dily"][kl(r).index(klic)]


NOHA_ZL, NOHA_ZP = ("t", S.NOHA_ZL), ("t", S.NOHA_ZP)


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


def over_napojeni(r, nazev):
    """Napojeni: spoje generatoru == definice z dimension_match_fbx, QA kontrola lic_peers, zadny profil bez spoje, kazda spojka ma 2 vlastniky, zadna spojka v desce ani v panelu."""
    dily = r["dily"]
    gen = {tuple(x) for x in r["spoje"]}
    ref = profil_pary_dmf(dily)
    check(gen == ref, f"{nazev}: spoje generatoru == dimension_match_fbx ({len(gen)} vs {len(ref)}; navic {sorted(gen - ref)[:3]}, chybi {sorted(ref - gen)[:3]})")
    pairs, bad = qa_checks.lic_peers_bad_pairs(dily, PROFIL_GLB, {})
    check(not bad, f"{nazev}: QA lic_peers_neni_spoj hlasi {len(bad)} spatnych paru {bad[:3]}")
    spojene = {i for p in r["spoje"] for i in p}
    sam = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS and i not in spojene]
    check(not sam, f"{nazev}: profily bez jakehokoli spoje {sam}")
    prekazky = [S._aabb(d) for d in dily if d["part_id"] in ("product_4933", S.PANEL_PART)]
    for i, d in enumerate(dily):
        if d["part_id"] not in S.SPOJKY_PARTS:
            continue
        vl = [j for j, e in enumerate(dily) if e["part_id"] in S.PROFIL_PARTS and i in (e.get("lic_peers") or [])]
        check(len(vl) == 2, f"{nazev}: spojka #{i} ma {len(vl)} vlastniku (ma mit 2)")
        b = S._aabb(d)
        for lo_d, hi_d in prekazky:
            pres = np.minimum(b[1], hi_d) - np.maximum(b[0], lo_d)
            check(not (np.all(pres > 0) and float(pres.min()) > S.TOL_PRUNIK_MM), f"{nazev}: spojka #{i} se zanorila do desky/panelu o {float(pres.min()):.1f} mm")


def bez_problemu(r, nazev):
    check(not r["problemy"], f"{nazev}: bez problemu ({[(p['kod'], p['text'][:70]) for p in r['problemy'][:2]]})")


# ---------------------------------------------------------------------------------------------------------------------
print(f"A) vychozi stul (system {SYS}, profil {P:g}): 1 panel vsazeny mezi zadni stojky")
r = S.sestav_stul()
bez_problemu(r, "vychozi")
W = r["parametry"]["sirka"]
check(W == 1280 and r["parametry"]["panely_pocet"] == 1 and r["parametry"]["stredni_opora"] == "auto" and r["parametry"]["stojky_vyska"] == 1073.0, f"vychozi: sirka 1280, 1 panel, opora auto, stojky 1073 ({r['parametry']['sirka']})")
pan, lis = panely(r), listy(r)
check(len(pan) == 1 and len(lis) == 2, f"vychozi: 1 panel a 2 profily nad/pod nim ({len(pan)}, {len(lis)})")
if len(pan) == 1 and len(lis) == 2:
    plo, phi = bb(pan[0][2])
    check(np.allclose(phi - plo, [PANEL_T, PANEL_V, PANEL_S], atol=0.05), f"panel ma rozmer {PANEL_T:g} x {PANEL_V:g} x {PANEL_S:g} ({np.round(phi - plo, 3).tolist()})")
    zl, zp = bb(dil(r, NOHA_ZL)), bb(dil(r, NOHA_ZP))
    in_l, in_p = float(zl[1][2]), float(zp[0][2])                  # vnitrni lica zadnich stojek (z)
    check(abs((in_p - in_l) - (W - 2 * P)) < 0.05, f"volna sirka mezi zadnimi stojkami = sirka - 2 x profil ({in_p - in_l:.2f})")
    g1, g2 = float(plo[2] - in_l), float(in_p - phi[2])
    check(g1 >= MEZERA - 1e-6 and g2 >= MEZERA - 1e-6 and abs(g1 - g2) < 0.01, f"panel je mezi stojkami vystredeny, mezera od stojek {g1:.3f} / {g2:.3f} mm (aspon {MEZERA:g})")
    nizsi, vyssi = sorted([lis[0], lis[1]], key=lambda x: bb(x[2])[0][1])
    lo_n, hi_n = bb(nizsi[2])
    lo_v, hi_v = bb(vyssi[2])
    check(abs((plo[1] - hi_n[1]) - MEZERA) < 0.01 and abs((lo_v[1] - phi[1]) - MEZERA) < 0.01, f"mezera panel - profil nad/pod presne {MEZERA:g} mm ({plo[1] - hi_n[1]:.3f} / {lo_v[1] - phi[1]:.3f})")
    for nm, (lo_, hi_) in (("spodni", (lo_n, hi_n)), ("horni", (lo_v, hi_v))):
        check(abs((hi_[0] - lo_[0]) - P) < 0.05 and abs((hi_[1] - lo_[1]) - P) < 0.05, f"{nm} profil panelu je {P:g} x {P:g}")
        check(abs(lo_[2] - in_l) < 0.05 and abs(hi_[2] - in_p) < 0.05, f"{nm} profil panelu dosedá na obe stojky (konce v z {lo_[2]:.2f} / {hi_[2]:.2f} vs {in_l:.2f} / {in_p:.2f})")
        check(abs(lo_[0] - zl[0][0]) < 0.05 and abs(hi_[0] - zl[1][0]) < 0.05, f"{nm} profil panelu lezi v rovine stojek (x)")
    check(abs((plo[0] + phi[0]) / 2 - (zl[0][0] + zl[1][0]) / 2) < 0.05, "panel je vystredeny v hloubce stojek (rovina stojek)")
    zad = bb(dil(r, ("t", S.ZRAIL_PRAC_ZAD)))
    check(abs((lo_n[1] - zad[1][1]) - ODSTUP_PRICKA) < 0.01, f"spodni profil v nejnizsi poloze {ODSTUP_PRICKA:g} mm nad zadni prickou ramu desky ({lo_n[1] - zad[1][1]:.3f})")
    # zadny profil podel kratkych stran panelu: v prostoru mezi stojkami a v y-rozsahu panelu nic neni (krome panelu, jeho dvou profilu a elektrozlabu pred nim)
    for i, k, d in casti(r, lambda k: True):
        if k in (NOHA_ZL, NOHA_ZP) or (isinstance(k, tuple) and k[0] in ("pan", "panrail")) or d["part_id"] in ("product_4932", S.PANEL_PART):
            continue
        lo_, hi_ = bb(d)
        v_rovine = min(hi_[0], zl[1][0]) - max(lo_[0], zl[0][0]) > 0.5
        v_y = min(hi_[1], phi[1]) - max(lo_[1], plo[1]) > 0.5
        v_z = min(hi_[2], in_p) - max(lo_[2], in_l) > 0.5
        check(not (v_rovine and v_y and v_z), f"v rovine stojek mezi nimi u panelu nic neni (dil #{i} {k} {d['part_id']})")
    # nic nezasahuje do panelu (spojky max TOL_PRUNIK_MM, ostatni jen dotyk/mezera)
    for i, k, d in casti(r, lambda k: True):
        if i == pan[0][0]:
            continue
        lo_, hi_ = bb(d)
        pres = np.minimum(phi, hi_) - np.maximum(plo, lo_)
        if np.all(pres > 0):
            check(float(pres.min()) <= (S.TOL_PRUNIK_MM if d["part_id"] in S.SPOJKY_PARTS else 0.011), f"dil #{i} {k} {d['part_id']} zasahuje do panelu o {float(pres.min()):.2f} mm")
    # spojky horniho profilu jsou (na tomto stole nad nim, mimo panel); spodni profil ma na tomto uzkem stole spojky vynechane (kolidovaly by s panelem)
    sp = [d for d in r["dily"] if d["part_id"] in S.SPOJKY_PARTS and bb(d)[0][1] > phi[1]]
    check(len(sp) >= 2, f"u horniho profilu panelu jsou spojky ({len(sp)})")
over_napojeni(r, "vychozi")
check(r["pocet_spoju"] == 28 and sum(1 for k in r["klice"] if k[0] != "zasl") == 50, f"vychozi stul: 28 spoju, 50 dilu bez zaslepek volnych koncu ({r['pocet_spoju']}, {len(r['dily'])})")

# profily panelu a stojky: nic neplave (kazdy profil ma spoj), pro sirsi stoly s volnou mezerou u stojek (>= 28 mm) ma spodni profil u obou stojek spojky
r_s = S.sestav_stul(sirka=1500)
check(len([d for d in r_s["dily"] if d["part_id"] in S.SPOJKY_PARTS]) == len([d for d in r["dily"] if d["part_id"] in S.SPOJKY_PARTS]) + 2, "sirka 1500: u spodniho profilu panelu pribyly 2 spojky (panel je dost daleko od stojek)")
over_napojeni(r_s, "1500")

# panely vypnute: zadny panel ani profily, elektrozlab se odebere
r_np = S.sestav_stul(panely=False)
check(not panely(r_np) and not listy(r_np) and [o["volba"] for o in r_np["odebrano"]] == ["elektrozlab"], f"panely vypnute: zadny panel ani profil, elektrozlab se odebere ({[o['volba'] for o in r_np['odebrano']]})")
r_0 = S.sestav_stul(panely_pocet=0)
check(r_0["parametry"]["panely"] is False and not panely(r_0), "panely_pocet=0 = panely vypnute")
over_napojeni(r_np, "bez panelu")

# ---------------------------------------------------------------------------------------------------------------------
print("B) nejmensi sirka stolu z delky panelu")
rm = S.sestav_stul(sirka=MIN_SIRKA)
check(not rm["problemy"] and len(panely(rm)) == 1 and rm["panely_info"]["min_sirka"] == MIN_SIRKA, f"sirka {MIN_SIRKA}: panel se vejde, min_sirka v odpovedi ({rm['panely_info']['min_sirka']})")
if panely(rm):
    plo, phi = bb(panely(rm)[0][2])
    zl, zp = bb(dil(rm, NOHA_ZL)), bb(dil(rm, NOHA_ZP))
    check(abs((plo[2] - zl[1][2]) - 1.0) < 0.01 and abs((zp[0][2] - phi[2]) - 1.0) < 0.01, f"na nejmensi sirce je mezera panel - stojka presne 1 mm ({plo[2] - zl[1][2]:.3f} / {zp[0][2] - phi[2]:.3f})")
over_napojeni(rm, f"sirka {MIN_SIRKA}")
ru = S.sestav_stul(sirka=MIN_SIRKA - 0.5)
check(not panely(ru) and {"panely", "elektrozlab"} <= {o["volba"] for o in ru["odebrano"]} and not ru["problemy"], f"sirka {MIN_SIRKA - 0.5}: panel se nevejde = automaticky odebran, bez chyby ({[o['volba'] for o in ru['odebrano']]})")
check(S.nabidky_roztazeni(sirka=MIN_SIRKA - 52)["panely"] == {"sirka": math.ceil((MIN_SIRKA - 52 + 60) / 10.0) * 10 if False else int(math.ceil(MIN_SIRKA / 10.0) * 10)}, f"nabidka roztazeni pro panel = nejmensi sirka zaokrouhlena na 10 mm ({S.nabidky_roztazeni(sirka=MIN_SIRKA - 52)['panely']})")
check(S.panel_limity()["min_sirka"] == MIN_SIRKA and S.panel_limity()["min_stojky"] == MIN_STOJKY and S.panel_limity()["min_sirka_nohy"] == MIN_SIRKA_NOHY and S.panel_limity()["usek"] == int(USEK),
      f"panel_limity() == nezavisly vypocet ({S.panel_limity()} vs {MIN_SIRKA}, {MIN_STOJKY}, {MIN_SIRKA_NOHY})")
dp = S.dostupnost(sirka=MIN_SIRKA - 10)
check(dp["panely"] and str(MIN_SIRKA) in dp["panely"], f"dostupnost: duvod u uzkeho stolu nese nejmensi sirku ({dp['panely']})")
check(S.dostupnost(sirka=MIN_SIRKA)["panely"] is None, "dostupnost: panel na nejmensi sirce jde zapnout")

# ---------------------------------------------------------------------------------------------------------------------
print("C) vyska zadnich stojek (zkracovat i natahovat)")
vrch = lambda d: float(bb(d)[1][1])
base = S.sestav_stul()
nad = vrch(dil(base, NOHA_ZL)) - vrch(dil(base, ("t", S.ZRAIL_PRAC_ZAD)))
check(abs(nad - 1073.0) < 0.05, f"vychozi stojky: vrch stojky {nad:.2f} mm nad zadni prickou (1073)")
arm_dy = float(bb(dil(base, ("t", S.XRAIL_TOP_L)))[0][1] - vrch(dil(base, NOHA_ZL)))
for h in (MIN_STOJKY, 700, 1073, 1300, 1500):
    rh = S.sestav_stul(stojky_vyska=h)
    bez_problemu(rh, f"stojky {h}")
    zl_, zp_ = dil(rh, NOHA_ZL), dil(rh, NOHA_ZP)
    nad_ = vrch(zl_) - vrch(dil(rh, ("t", S.ZRAIL_PRAC_ZAD)))
    check(abs(nad_ - h) < 0.05 and abs(vrch(zp_) - vrch(zl_)) < 0.01, f"stojky {h}: vrch stojek {nad_:.2f} mm nad zadni prickou, obe stejne")
    check(abs(float(bb(dil(rh, ("t", S.XRAIL_TOP_L)))[0][1] - vrch(zl_)) - arm_dy) < 0.01 and abs(float(bb(dil(rh, ("t", S.XRAIL_TOP_P)))[0][1] - vrch(zp_)) - arm_dy) < 0.01, f"stojky {h}: ramena LED jedou se stojkami")
    check(len(panely(rh)) == 1 and rh["stojky_meze"]["hodnota"] == float(h) and rh["stojky_meze"]["min"] == float(MIN_STOJKY) and rh["stojky_meze"]["max"] == 1500.0, f"stojky {h}: panel je, meze stojek {rh['stojky_meze']}")
    over_napojeni(rh, f"stojky {h}")
    if len(panely(rh)) == 1 and len(listy(rh)) == 2:
        top = max(bb(x[2])[1][1] for x in listy(rh))
        check(top <= vrch(zl_) + 0.01, f"stojky {h}: horni profil panelu nepresahuje stojky ({top:.2f} <= {vrch(zl_):.2f})")
check(abs(vrch(dil(S.sestav_stul(stojky_vyska=MIN_STOJKY), ("t", S.ZRAIL_PRAC_ZAD))) + MIN_STOJKY - vrch(dil(S.sestav_stul(stojky_vyska=MIN_STOJKY), NOHA_ZL))) < 0.05, "nejnizsi stojky s panelem")
rn = S.sestav_stul(stojky_vyska=MIN_STOJKY - 1)
check(not panely(rn) and {"panely", "elektrozlab"} <= {o["volba"] for o in rn["odebrano"]} and not rn["problemy"], f"o 1 mm nizsi stojky nez {MIN_STOJKY}: panel se nevejde = automaticky odebran ({[o['volba'] for o in rn['odebrano']]})")
check(S.nabidky_roztazeni(stojky_vyska=500)["panely"] == {"stojky_vyska": int(math.ceil(MIN_STOJKY / 10.0) * 10)}, f"nabidka pro panel na nizkych stojkach: zvysit na {math.ceil(MIN_STOJKY / 10.0) * 10} mm ({S.nabidky_roztazeni(stojky_vyska=500)['panely']})")
rl = S.sestav_stul(stojky_vyska=200, panely=False, elektrozlab=False)
check(not rl["problemy"] and rl["stojky_meze"]["min"] == 200.0, f"stojky 200 bez panelu: bez problemu, min {rl['stojky_meze']['min']}")
over_napojeni(rl, "stojky 200 bez panelu")
for chyba in (199, 1501, float("nan")):
    try:
        S.sestav_stul(stojky_vyska=chyba)
        check(False, f"stojky_vyska {chyba} ma byt odmitnuta")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"stojky_vyska {chyba}: kod {e.kod}")
a1 = S.sestav_stul(stojky=False, panely=False, led=False, elektrozlab=False, stojky_vyska=600)
a2 = S.sestav_stul(stojky=False, panely=False, led=False, elektrozlab=False, stojky_vyska=1400)
check([d["position"] for d in a1["dily"]] == [d["position"] for d in a2["dily"]] and [d["scale"] for d in a1["dily"]] == [d["scale"] for d in a2["dily"]], "bez zadnich stojek se vyska stojek nepouzije")
for kw in (dict(sirka=2000), dict(sirka=MIN_SIRKA_NOHY + 6, panely_pocet=2, **NOHA), dict(hloubka=1000, vyska=700)):
    for h in (MIN_STOJKY + 6, 900, 1500):
        over_napojeni(S.sestav_stul(stojky_vyska=h, **kw), f"stojky {h} {kw}")

# ---------------------------------------------------------------------------------------------------------------------
print("D) posun panelu po zadnich stojkach")
r0 = S.sestav_stul()
pmax = r0["panely_info"]["posun_max"]
check(pmax > 100, f"posun_max v odpovedi ({pmax:.1f})")
n0 = bb(listy(r0)[0][2])[0][1]
z0 = bb(dil(r0, ("t", S.ELZLAB)))[0][1]
for p in (0.0, 10.0, 100.0, 333.0, pmax):
    rp = S.sestav_stul(panely_pocet=1, panely_posun=p)
    bez_problemu(rp, f"posun {p:.0f}")
    nizsi = min(listy(rp), key=lambda x: bb(x[2])[0][1])
    check(abs(bb(nizsi[2])[0][1] - (n0 + p)) < 0.01, f"posun {p:.1f}: spodni profil o presne tolik vys ({bb(nizsi[2])[0][1] - n0:.3f})")
    check(abs(bb(panely(rp)[0][2])[0][1] - bb(panely(r0)[0][2])[0][1] - p) < 0.01, f"posun {p:.1f}: panel o presne tolik vys")
    check(abs(bb(dil(rp, ("t", S.ELZLAB)))[0][1] - z0 - p) < 0.01, f"posun {p:.1f}: elektrozlab jede s panelem")
    over_napojeni(rp, f"posun {p:.0f}")
rmx = S.sestav_stul(panely_posun=pmax)
vyssi = max(listy(rmx), key=lambda x: bb(x[2])[1][1])
check(abs(float(bb(vyssi[2])[1][1]) - vrch(dil(rmx, NOHA_ZL))) < 0.01, f"nejvyssi poloha: horni profil panelu lici s vrchem stojky ({bb(vyssi[2])[1][1]:.3f} vs {vrch(dil(rmx, NOHA_ZL)):.3f})")
rpr = S.sestav_stul(panely_posun=pmax + 500.0)
check(rpr["parametry"]["panely_posun"] == rmx["parametry"]["panely_posun"] and [d["position"] for d in rpr["dily"]] == [d["position"] for d in rmx["dily"]], "posun nad mez se orizne na nejvyssi polohu")
rneg = S.sestav_stul(panely_posun=-50.0)
check(rneg["parametry"]["panely_posun"] == 0.0, "zaporny posun se orizne na 0")
rv = S.sestav_stul(panely_posun=200.0, stojky_vyska=MIN_STOJKY + 200)
check(len(panely(rv)) == 1 and not rv["problemy"] and abs(rv["panely_info"]["posun_max"] - 200.0) < 0.01, f"stojky {MIN_STOJKY + 200} umozni posun do 200 mm ({rv['panely_info']['posun_max']:.2f})")
rvn = S.sestav_stul(panely_posun=201.0, stojky_vyska=MIN_STOJKY + 200)
check(abs(rvn["parametry"]["panely_posun"] - 200.0) < 0.01, "posun nad mez dana vyskou stojek se orizne")
# posun a spoje: spodni profil se po zvednuti nedotyka zadni pricky; stale drzi na obou stojkach
r_z = S.sestav_stul(panely_posun=300.0)
over_napojeni(r_z, "posun 300")
check(r_z["pocet_spoju"] == r0["pocet_spoju"], f"posun nemeni pocet spoju ({r_z['pocet_spoju']} vs {r0['pocet_spoju']})")

# ---------------------------------------------------------------------------------------------------------------------
print("E) pocet panelu: rady nad sebou, useky vedle sebe")
for n in (1, 2):
    rn = S.sestav_stul(panely_pocet=n)
    bez_problemu(rn, f"{n} panelu v rade")
    pn, ln = panely(rn), listy(rn)
    check(len(pn) == n and len(ln) == n + 1 and rn["panely_info"]["pocet"] == n and rn["panely_info"]["radu"] == n, f"{n} panelu nad sebou: {n} panelu, {n + 1} profilu ({len(pn)}, {len(ln)})")
    ys = sorted([(bb(x[2])[0][1], bb(x[2])[1][1], "p") for x in pn] + [(bb(x[2])[0][1], bb(x[2])[1][1], "l") for x in ln])
    check([t_[2] for t_ in ys] == ["l", "p"] * n + ["l"], f"{n} panelu: profil, panel, profil, ... nad sebou ({[t_[2] for t_ in ys]})")
    check(all(abs((ys[i + 1][0] - ys[i][1]) - MEZERA) < 0.01 for i in range(len(ys) - 1) if ys[i][2] != ys[i + 1][2]), f"{n} panelu: vsude mezera {MEZERA:g} mm mezi panelem a profilem")
    over_napojeni(rn, f"{n} panelu")
r3 = S.sestav_stul(panely_pocet=3)
check(r3["panely_info"]["pozadovano"] == 3 and r3["panely_info"]["pocet"] == 2 and r3["parametry"]["panely_pocet"] == 2 and len(panely(r3)) == 2 and r3["panely_info"]["max"] == 2, "3 panely na jednom useku: orez na kapacitu 2 (max 2 rady)")
r3h = S.sestav_stul(panely_pocet=3, stojky_vyska=1500)
check(len(panely(r3h)) == 2, "vyssi stojky nezvysi pocet rad nad 2")
# lisky jen u pouzitych useku
r2k = S.sestav_stul(sirka=MIN_SIRKA_NOHY + 120, panely_pocet=1, **NOHA)
check(len(panely(r2k)) == 1 and len(listy(r2k)) == 2 and r2k["panely_info"]["sloupcu"] == 2, f"2 useky, 1 panel: profily jen v useku s panelem ({len(listy(r2k))} profilu, {r2k['panely_info']['sloupcu']} useky)")
over_napojeni(r2k, "2 useky, 1 panel")
# dva useky vedle sebe: plna stredni noha mezi panely
for n, ocek_p, ocek_l in ((2, 2, 4), (3, 3, 5), (4, 4, 6)):
    r2 = S.sestav_stul(sirka=MIN_SIRKA_NOHY + 6, panely_pocet=n, **NOHA)
    bez_problemu(r2, f"2 useky, {n} panelu")
    pn = panely(r2)
    check(len(pn) == ocek_p and len(listy(r2)) == ocek_l and r2["panely_info"]["sloupcu"] == 2, f"2 useky, {n} panelu: {ocek_p} panelu, {ocek_l} profilu ({len(pn)}, {len(listy(r2))})")
    rm_ = [bb(d) for i, k, d in casti(r2, lambda k: k == "RM")]
    if rm_ and len(pn) >= 2:
        mlo, mhi = rm_[0]
        radu0 = [x for x in pn if x[1][1] == 0]
        check(len(radu0) == 2 and bb(radu0[0][2])[1][2] <= mlo[2] - MEZERA + 1e-6 and bb(radu0[1][2])[0][2] >= mhi[2] + MEZERA - 1e-6, f"2 useky, {n} panelu: spodni rada ma panel na kazde strane plne stredni nohy s mezerou aspon 1 mm")
        check(float(mhi[1] - mlo[1]) > 1000, "stredni noha je plna (vysoka)")
        for x in radu0:
            lo_, hi_ = bb(x[2])
            check(abs(lo_[2] - hi_[2]) > 1000 and bb(x[2])[0][1] == bb(radu0[0][2])[0][1], "panely vedle sebe jsou ve stejne vysce")
    over_napojeni(r2, f"2 useky {n} panelu")
r2n = S.sestav_stul(sirka=MIN_SIRKA_NOHY - 10, panely_pocet=2, **NOHA)
check(not panely(r2n) and not r2n["problemy"] and "panely" in [o["volba"] for o in r2n["odebrano"]], f"o 10 mm uzsi stul se strednimi nohami: panel se nevejde do zadneho useku = odebran ({[o['volba'] for o in r2n['odebrano']]})")
# stredni noha mimo stred: panel se vejde jen do sirsiho useku
r_off = S.sestav_stul(sirka=2400, stredni_noha=700.0, **NOHA)
check(len(panely(r_off)) == 1 and r_off["panely_info"]["sloupcu"] == 1, f"sirka 2400, stredni noha na 700: panel jen v sirsim (pravem) useku ({len(panely(r_off))}, {r_off['panely_info']['sloupcu']})")
if panely(r_off):
    rm_ = bb(dil(r_off, "RM"))
    check(bb(panely(r_off)[0][2])[0][2] >= rm_[1][2] + MEZERA - 1e-6, "panel je vpravo od stredni nohy")
over_napojeni(r_off, "2400 stredni noha 700")
# kapacita podle stojek: na nizkych stojkach (jedna rada) se druhy panel nevejde
r_nz = S.sestav_stul(panely_pocet=2, stojky_vyska=MIN_STOJKY + 10)
check(len(panely(r_nz)) == 1 and r_nz["panely_info"]["max"] == 1, f"nizke stojky: jen 1 rada (max {r_nz['panely_info']['max']})")

# ---------------------------------------------------------------------------------------------------------------------
print("F) vestaveny ram misto strednich noh")
SIR_RAM = (1600, 2000, 2400)                     # u 2474 a vic (30) by se panel vesel mezi stredni nohy, `auto` by zvolilo nohy
for W_, kw in itertools.product(SIR_RAM, (dict(), dict(hloubka=1000), dict(police=2, vyska=1000), dict(police=3, vyska=1200, hloubka=1000))):
    rr = S.sestav_stul(sirka=W_, **kw)                                          # panel (vychozi) se mezi stredni nohy nevejde -> auto zvoli ram
    n_ = f"ram {W_} {kw}"
    check(rr["panely_info"]["rezim"] == "ram" and "RM" not in kl(rr) and "FM" not in kl(rr), f"{n_}: auto zvolilo vestaveny ram, zadne stredni nohy ({rr['panely_info']['rezim']})")
    bez_problemu(rr, n_)
    over_napojeni(rr, n_)
    check(len(panely(rr)) == 1, f"{n_}: panel zustal")
    # 4 vodorovne podelniky CELE: predni/zadni pracovni a predni/zadni podelnik police, kazdy jeden dil o delce sirka - 2 x profil
    n_pol = rr["parametry"]["police"]
    for klic_, nazev in ((("t", S.ZRAIL_PRAC_PRED), "predni pracovni"), (("t", S.ZRAIL_PRAC_ZAD), "zadni pracovni"), (("t", S.ZRAIL_POL_PRED), "predni police"), (("t", S.ZRAIL_POL_ZAD), "zadni police")):
        lo_, hi_ = bb(dil(rr, klic_))
        check(abs((hi_[2] - lo_[2]) - (W_ - 2 * P)) < 0.05, f"{n_}: {nazev} podelnik je cely ({hi_[2] - lo_[2]:.2f} mm)")
    check(not any(isinstance(k, tuple) and k[0] == "seg" for k in kl(rr)), f"{n_}: zadne rozdelene podelniky")
    # prícky ramu: horni (osa X) od predniho po zadni pracovni podelnik, dolni od predniho po zadni podelnik police
    xp = bb(dil(rr, ("t", S.ZRAIL_PRAC_PRED)))
    xz = bb(dil(rr, ("t", S.ZRAIL_PRAC_ZAD)))
    top = bb(dil(rr, "XM_prac"))
    check(abs(top[0][0] - xp[1][0]) < 0.05 and abs(top[1][0] - xz[0][0]) < 0.05, f"{n_}: horni prícka ramu vede od predniho po zadni pracovni podelnik (x {top[0][0]:.2f}..{top[1][0]:.2f} vs {xp[1][0]:.2f}..{xz[0][0]:.2f})")
    pp, pz = bb(dil(rr, ("t", S.ZRAIL_POL_PRED))), bb(dil(rr, ("t", S.ZRAIL_POL_ZAD)))
    dol = bb(dil(rr, "XM_pol"))
    check(abs(dol[0][0] - pp[1][0]) < 0.05 and abs(dol[1][0] - pz[0][0]) < 0.05, f"{n_}: dolni prícka ramu vede od predniho po zadni podelnik police")
    check(abs(dol[0][2] - top[0][2]) < 0.05 and abs(dol[1][2] - top[1][2]) < 0.05, f"{n_}: prícky ramu ve stejne svisle rovine")
    # svisle profily ramu (osa Y), vsechny stejne tlusty profil, lezi mezi prickami a podelniky
    posty = [bb(d) for i, k, d in casti(rr, lambda k: isinstance(k, tuple) and k[0] == "ram")]
    check(len(posty) == 2 * n_pol, f"{n_}: 2 svisle profily ramu na kazdou uroven ({len(posty)} pro {n_pol} polic)")
    for lo_, hi_ in posty:
        check(abs((hi_[0] - lo_[0]) - P) < 0.05 and abs((hi_[2] - lo_[2]) - P) < 0.05 and (hi_[1] - lo_[1]) > 100, f"{n_}: svisly profil ramu {P:g} x {P:g}, vysoky")
        alk = [bb(d) for d in rr["dily"] if d["part_id"] in S.PROFIL_PARTS]
        spodek = [b[1][1] for b in alk if b[0][1] < lo_[1] + 0.5 and b[1][1] > lo_[1] - 0.05 and min(b[1][0], hi_[0]) - max(b[0][0], lo_[0]) > 0.5 and min(b[1][2], hi_[2]) - max(b[0][2], lo_[2]) > 0.5 and (hi_[1] - lo_[1]) != (b[1][1] - b[0][1])]
        vrch_ = [b[0][1] for b in alk if b[1][1] > hi_[1] - 0.5 and b[0][1] < hi_[1] + 0.05 and min(b[1][0], hi_[0]) - max(b[0][0], lo_[0]) > 0.5 and min(b[1][2], hi_[2]) - max(b[0][2], lo_[2]) > 0.5]
        check(any(abs(lo_[1] - y) < 0.05 for y in spodek) or any(abs(b[1][1] - lo_[1]) < 0.05 and min(b[1][0], hi_[0]) - max(b[0][0], lo_[0]) > 0.5 and min(b[1][2], hi_[2]) - max(b[0][2], lo_[2]) > 0.5 for b in alk), f"{n_}: svisly profil ramu stoji na profilu")
        check(any(abs(hi_[1] - b[0][1]) < 0.05 and min(b[1][0], hi_[0]) - max(b[0][0], lo_[0]) > 0.5 and min(b[1][2], hi_[2]) - max(b[0][2], lo_[2]) > 0.5 for b in alk), f"{n_}: svisly profil ramu se hornim koncem dotyka profilu nad nim")
    # kolecka: 4 (ram nema stredni nohy) a stul stoji na 4 nohach
    check(sum(1 for d in rr["dily"] if d["part_id"] == "product_4916") == 4, f"{n_}: 4 kolecka (zadne stredni nohy)")
# DESKY u vestaveneho ramu (Robert 2026-10-05, formaty tabuli lamino): pracovni deska i spodni police se u ramu DELI na dve desky (kazda se vejde do tabule); pracovni deska navazuje bez mezery,
# spodni police (svisly profil ramu prochazi rovinou police) jsou obe o pulku mezery KRATSI: mezera = profil + 1 mm vule z kazde strany, vycentrovana na osu ramu; zadne vyrezy ani kusy.
for W_, kw in ((2000, dict()), (2400, dict(hloubka=1000)), (1600, dict(police=2, vyska=1000))):
    rr = S.sestav_stul(sirka=W_, **kw)
    n_ = f"desky u ramu {W_} {kw}"
    n_pol_ = rr["parametry"]["police"]
    desky_p = [(i, d, bb(d)) for i, d in enumerate(rr["dily"]) if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("pol") and not str(d.get("deska_id")).startswith("polvyr")]
    check(len(desky_p) == 2 * n_pol_ and all(not d.get("deska_celek") and not d.get("deska_kus") for i, d, b in desky_p),
          f"{n_}: kazda z {n_pol_} polic jsou dve cele desky bez kusu a vyrezu ({len(desky_p)} desek)")
    posty_z = [(b[0][2] + b[1][2]) / 2 for i, k, d in casti(rr, lambda k: isinstance(k, tuple) and k[0] == "ram") for b in [bb(d)]]
    zm_r = float(np.mean(posty_z))
    mez = P / 2.0 + S.RAM_VULE_VYREZU                                      # od osy ramu k hrane desky
    patra = {}
    for i, d, b in desky_p:
        patra.setdefault(d["deska_id"].split("_")[0], []).append((d["deska_id"].endswith("_0"), b))
    check(len(patra) == n_pol_, f"{n_}: {n_pol_} pater polic ({len(patra)})")
    for pat, lst in patra.items():
        lev = [b for jl, b in lst if jl]
        pra = [b for jl, b in lst if not jl]
        check(len(lev) == 1 and len(pra) == 1, f"{n_}: patro {pat} ma levou a pravou desku")
        if len(lev) == 1 and len(pra) == 1:
            check(abs(lev[0][1][2] - (zm_r - mez)) < 0.05 and abs(pra[0][0][2] - (zm_r + mez)) < 0.05, f"{n_}: patro {pat}: hrany desek {lev[0][1][2] - zm_r:.2f} / {pra[0][0][2] - zm_r:.2f} mm od osy ramu (ma byt +-{mez:g})")
            check(abs((pra[0][0][2] - lev[0][1][2]) - (P + 2 * S.RAM_VULE_VYREZU)) < 0.05, f"{n_}: patro {pat}: mezera mezi deskami {pra[0][0][2] - lev[0][1][2]:.2f} mm = profil + 2 x vule")
    # svisle profily ramu neprochazi zadnou deskou
    for i, k, d in casti(rr, lambda k: isinstance(k, tuple) and k[0] == "ram"):
        lo_, hi_ = bb(d)
        for i1, d1, b1 in desky_p:
            pres = np.minimum(b1[1], hi_) - np.maximum(b1[0], lo_)
            check(not (np.all(pres > 0) and float(pres.min()) > S.TOL_PRUNIK_MM), f"{n_}: svisly profil ramu #{i} neprochazi deskou #{i1}")
    # pokryti: kazdy bod roviny police (nejnizsi police) uvnitr obalky desek lezi v nejake desce, nebo v mezere kolem ramu (+-mez od osy)
    nizsi = [(i, d, b) for i, d, b in desky_p if d["deska_id"].startswith("pol0_")]
    lo_all = np.min([b[0] for i, d, b in nizsi], axis=0)
    hi_all = np.max([b[1] for i, d, b in nizsi], axis=0)
    chyby_pokryti = 0
    for z in np.linspace(lo_all[2] + 1, hi_all[2] - 1, 200):
        v_desce = any(b[0][2] - 1e-6 <= z <= b[1][2] + 1e-6 for i, d, b in nizsi)
        v_mezere = abs(z - zm_r) <= mez + 1e-6
        if not v_desce and not v_mezere:
            chyby_pokryti += 1
    check(chyby_pokryti == 0, f"{n_}: desky pokryvaji polici mimo mezeru u ramu ({chyby_pokryti} nepokrytych rezu)")
    # pracovni deska: dve casti navazujici bez mezery, soucet = sirka stolu
    pr_ = sorted((bb(d) for d in rr["dily"] if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("prac_") and not d.get("deska_kus")), key=lambda b: b[0][2])
    check(len(pr_) == 2 and abs(pr_[0][1][2] - pr_[1][0][2]) < 0.05 and abs((pr_[1][1][2] - pr_[0][0][2]) - W_) < 0.05, f"{n_}: pracovni deska ve dvou castech bez mezery, celkem {W_} mm")
    check(all(S.deska_se_vejde_do_tabule(b[1][0] - b[0][0], b[1][2] - b[0][2]) for i, d, b in desky_p) and all(S.deska_se_vejde_do_tabule(b[1][0] - b[0][0], b[1][2] - b[0][2]) for b in pr_), f"{n_}: kazda deska se vejde do tabule")
# ram potrebuje spodni polici; bez police stredni nohy (a panel se mezi ne nevejde)
rb = S.sestav_stul(sirka=2000, police=0, stredni_opora="ram")
check(rb["panely_info"]["rezim"] == "noha" and "RM" in kl(rb) and not casti(rb, lambda k: isinstance(k, tuple) and k[0] == "ram") and not rb["problemy"], "ram bez spodni police: stredni nohy (ram potrebuje polici)")
# explicitne nohy / auto
check(S.sestav_stul(sirka=2000, **NOHA)["panely_info"]["rezim"] == "noha" and len(panely(S.sestav_stul(sirka=2000, **NOHA))) == 0, "explicitne stredni nohy: panel se mezi ne nevejde a odebere se")
r_au = S.sestav_stul(sirka=MIN_SIRKA_NOHY + 6, panely_pocet=2)
check(r_au["panely_info"]["rezim"] == "noha" and len(panely(r_au)) == 2 and "RM" in kl(r_au), "auto: 2 panely vedle sebe se vejdou se strednimi nohami = nohy")
r_au3 = S.sestav_stul(sirka=MIN_SIRKA_NOHY + 100, panely_pocet=1)
check(r_au3["panely_info"]["rezim"] == "noha" and len(panely(r_au3)) == 1, "auto: 1 panel se vejde do useku = nohy")
r_pet = S.sestav_stul(sirka=2000, pet_noha="FM")
check(r_pet["panely_info"]["rezim"] == "noha", "auto: drzak PET na stredni noze vynuti stredni nohy")
# polohu ramu lze menit (stredni_noha), pricky a svisle profily jdou s nim
for zrel in (300.0, 700.0, 1000.0):
    rr = S.sestav_stul(sirka=2000, stredni_noha=zrel)
    posty = [bb(d) for i, k, d in casti(rr, lambda k: isinstance(k, tuple) and k[0] == "ram")]
    zl_os = float((bb(dil(rr, NOHA_ZL))[0][2] + bb(dil(rr, NOHA_ZL))[1][2]) / 2)
    check(all(abs((b[0][2] + b[1][2]) / 2 - (zl_os + zrel)) < 0.05 for b in posty) and abs((bb(dil(rr, "XM_prac"))[0][2] + bb(dil(rr, "XM_prac"))[1][2]) / 2 - (zl_os + zrel)) < 0.05, f"ram na {zrel:g} mm od leve nohy: svisle profily i prícka tam")
    check(not rr["problemy"], f"ram na {zrel:g} mm: bez problemu ({[p['kod'] for p in rr['problemy']]})")
    over_napojeni(rr, f"ram na {zrel:g} mm")
# velka mrizka: napojeni a zadne problemy
n_mrizka = 0
for W_, D_, pol, pn, opora in itertools.product((1600, 2000, 2800), (500, 800, 1000, 1400), (1, 2, 3), (0, 1, 2), ("auto", "ram")):
    rr = S.sestav_stul(sirka=W_, hloubka=D_, vyska=1200, police=pol, panely_pocet=pn, panely=pn > 0, stredni_opora=opora)
    n_mrizka += 1
    check(not rr["problemy"], f"mrizka {W_}x{D_} police {pol} panelu {pn} opora {opora}: bez problemu ({[(p['kod'], p['text'][:60]) for p in rr['problemy'][:1]]})")
    if not rr["problemy"]:
        over_napojeni(rr, f"mrizka {W_}x{D_} police {pol} panelu {pn} opora {opora}")
print(f"   mrizka ram/auto: {n_mrizka} konfiguraci")

# ---------------------------------------------------------------------------------------------------------------------
print("G) elektrozlab: dotyk panelu nebo profilu, meze posunu")
rz = S.sestav_stul()
mz = S.elzlab_meze(rz)
check(mz["vejde"] and mz["y"]["min"] <= 0 <= mz["y"]["max"] and mz["z"]["min"] <= 0 <= mz["z"]["max"], f"elzlab_meze vychozi: vejde se, hodnota 0 v mezich ({mz})")


def opora_zlabu(r):
    """Nezavisle: zadni lico elektrozlabu lezi na predni plose dilu, ktery je pred nim (panel, profil panelu, stojka) - vraci (opora existuje, nejvetsi zanoreni)."""
    zlab = dil(r, ("t", S.ELZLAB))
    zlo, zhi = bb(zlab)
    dotyk, max_pres = False, 0.0
    for i, k, d in casti(r, lambda k: True):
        if d is zlab:
            continue
        lo_, hi_ = bb(d)
        py, pz = min(hi_[1], zhi[1]) - max(lo_[1], zlo[1]), min(hi_[2], zhi[2]) - max(lo_[2], zlo[2])
        px = min(hi_[0], zhi[0]) - max(lo_[0], zlo[0])
        if py > 0.5 and pz > 0.5:
            if abs(zhi[0] - lo_[0]) < 0.011 and d["part_id"] in S.PROFIL_PARTS + (S.PANEL_PART,):
                dotyk = True
            if px > 0 and d["part_id"] not in S.SPOJKY_PARTS:
                max_pres = max(max_pres, px)
    return dotyk, max_pres


for y, z in ((0, 0), (mz["y"]["min"], 0), (mz["y"]["max"], 0), (0, mz["z"]["min"]), (0, mz["z"]["max"]), (mz["y"]["max"], mz["z"]["max"]), (mz["y"]["min"], mz["z"]["min"]), (150, 300)):
    re = S.sestav_stul(elzlab_y=y, elzlab_z=z)
    bez_problemu(re, f"elektrozlab ({y}, {z})")
    dotyk, pres = opora_zlabu(re)
    check(dotyk and pres <= 0.011, f"elektrozlab ({y:g}, {z:g}): zadnim licem se dotyka panelu/profilu/stojky, nezasahuje do nich (dotyk {dotyk}, zanoreni {pres:.3f})")
    over_napojeni(re, f"elektrozlab ({y:g}, {z:g})")
for kw, kod in ((dict(elzlab_y=mz["y"]["max"] + 10), "elzlab_bez_opory"), (dict(elzlab_y=mz["y"]["min"] - 10), "zanoreni"), (dict(elzlab_z=mz["z"]["max"] + 10), "mimo_obrys"), (dict(elzlab_z=mz["z"]["min"] - 10), "mimo_obrys")):
    re = S.sestav_stul(**kw)
    check(re["problemy"], f"elektrozlab {kw}: o 10 mm za mez = problem ({[p['kod'] for p in re['problemy']]})")
# jede s panelem
for p in (0.0, 120.0):
    rr = S.sestav_stul(panely_posun=p, elzlab_y=50.0, elzlab_z=40.0)
    zb, pb = bb(dil(rr, ("t", S.ELZLAB))), bb(panely(rr)[0][2])
    check(abs((zb[0][1] - pb[0][1]) - (S.elzlab_meze(S.sestav_stul())["y"]["hodnota"] + 50.0 + (bb(dil(S.sestav_stul(), ("t", S.ELZLAB)))[0][1] - bb(panely(S.sestav_stul())[0][2])[0][1]))) < 0.01, f"posun panelu {p:g}: elektrozlab drzi stejnou polohu vuci panelu")
    bez_problemu(rr, f"posun {p:g} + elektrozlab")
# elektrozlab na nizkem panelu: meze se meni s posunem a stojkami, na hranicich opora
for kw in (dict(panely_posun=300.0), dict(stojky_vyska=700), dict(sirka=MIN_SIRKA_NOHY + 6, panely_pocet=2, **NOHA), dict(sirka=2000)):
    rr = S.sestav_stul(**kw)
    mm = S.elzlab_meze(rr)
    for y_ in (mm["y"]["min"], mm["y"]["max"]):
        for z_ in (mm["z"]["min"], mm["z"]["max"]):
            rx = S.sestav_stul(**kw, elzlab_y=y_, elzlab_z=z_)
            dotyk, pres = opora_zlabu(rx)
            check(not rx["problemy"] and dotyk and pres <= 0.011, f"{kw}: elektrozlab na hranicich mezi ({y_:g}, {z_:g}) ma oporu a bez problemu ({[p['kod'] for p in rx['problemy']]})")
# elektrozlab zmizi s panelem; je ve vychozim stolu 1x
check(sum(1 for d in S.sestav_stul()["dily"] if d["part_id"] == "product_4932") == 1 and sum(1 for d in S.sestav_stul(panely=False)["dily"] if d["part_id"] == "product_4932") == 0, "elektrozlab: 1x s panelem, bez panelu 0")

# ---------------------------------------------------------------------------------------------------------------------
print("H) cena, vyrobni vypis, hash, 3D ovladani")
e1 = S.entries_pro_cenu(S.sestav_stul()["dily"])
e0 = S.entries_pro_cenu(S.sestav_stul(panely=False)["dily"])
check(sum(1 for q in e1 if q["part_id"] == S.PANEL_PART) == 1 and sum(1 for q in e0 if q["part_id"] == S.PANEL_PART) == 0, "cena: panel je polozka ceny")
prof_d1 = sorted(q["length_mm"] for q in e1 if q["part_id"] in S.PROFIL_PARTS)
prof_d0 = sorted(q["length_mm"] for q in e0 if q["part_id"] in S.PROFIL_PARTS)
check(len(prof_d1) == len(prof_d0) + 2 and prof_d1.count(1280 - 2 * P) == prof_d0.count(1280 - 2 * P) + 2, f"cena: dva profily panelu delky {1280 - 2 * P:g} mm pribyly")
check(sum(q.get("joint_count", 0) for q in e1) > sum(q.get("joint_count", 0) for q in e0), "cena: spoje profilu panelu")
e2 = S.entries_pro_cenu(S.sestav_stul(panely_pocet=2)["dily"])
check(sum(1 for q in e2 if q["part_id"] == S.PANEL_PART) == 2 and len([q for q in e2 if q["part_id"] in S.PROFIL_PARTS]) == len(prof_d1) + 1, "cena: druhy panel + treti profil")
# vyrobni vypis: panel, profily panelu, svisle profily ramu (delka), deska police s vyrezem
vv = S.vyrobni_vypis(S.sestav_stul(sirka=2000))
text_vv = str(vv)
check("product_4931" in text_vv or "panel" in text_vv.lower(), "vyrobni vypis: perforovany panel")
desky_vv = [q for q in vv["desky"] if q["role"].startswith("spodní police")]
check("výřez pro přední svislý profil vestavěného rámu" not in text_vv and len(desky_vv) == 2 and all(not q["vyrezy"] for q in desky_vv)
      and [q["role"] for q in desky_vv] == ["spodní police – levá část", "spodní police – pravá část"], f"vyrobni vypis: u ramu je spodni police ve dvou castech BEZ vyrezu ({[q['role'] for q in desky_vv]})")
# hash
H0 = G.kanonicky_hash({})
check(G.kanonicky_hash(dict(panely=False, panely_pocet=3, panely_posun=100.0)) == G.kanonicky_hash(dict(panely=False)), "hash: pocet a posun panelu se bez panelu nepocitaji")
check(G.kanonicky_hash(dict(elektrozlab=False, elzlab_y=50.0, elzlab_z=20.0)) == G.kanonicky_hash(dict(elektrozlab=False)), "hash: posun elektrozlabu se bez elektrozlabu nepocita")
check(G.kanonicky_hash(dict(sirka=1400, stredni_opora="ram")) == G.kanonicky_hash(dict(sirka=1400)), "hash: stredni opora se u uzkeho stolu (bez strednich noh) nepocita")
check(G.kanonicky_hash(dict(stojky=False, panely=False, led=False, elektrozlab=False, stojky_vyska=500)) == G.kanonicky_hash(dict(stojky=False, panely=False, led=False, elektrozlab=False)), "hash: vyska stojek se bez stojek nepocita")
for kw in (dict(panely_pocet=2), dict(panely_posun=100.0), dict(stojky_vyska=900.0), dict(elzlab_y=10.0), dict(elzlab_z=10.0), dict(sirka=2000, stredni_opora="noha"), dict(sirka=2000, stredni_opora="ram")):
    check(G.kanonicky_hash(kw) != G.kanonicky_hash({k_: v_ for k_, v_ in kw.items() if k_ in ("sirka",)}), f"hash: {kw} meni kod konfigurace")
check(G.kanonicky_hash(dict(sirka=2000, stredni_opora="noha")) != G.kanonicky_hash(dict(sirka=2000, stredni_opora="ram")), "hash: nohy a ram jsou ruzne konfigurace")
check(G.RULES_VERSION >= "2026-10-05.1", f"verze pravidel zvysena ({G.RULES_VERSION})")
# 3D ovladani: nove tahy a polozky nabidky
ov = S.ovladani_3d(S.sestav_stul())
tahy = {t["id"]: t for t in ov["tahy"]}
check({"panely_posun", "stojky_vyska", "elzlab_y", "elzlab_z"} <= set(tahy), f"3D tahy: panely_posun, stojky_vyska, elzlab_y, elzlab_z ({sorted(tahy)})")
rp0 = S.sestav_stul()
if {"panely_posun", "stojky_vyska", "elzlab_y", "elzlab_z"} <= set(tahy):
    check(tahy["panely_posun"]["min"] == 0 and tahy["panely_posun"]["max"] == math.floor(rp0["panely_info"]["posun_max"] / 10.0) * 10 and tahy["panely_posun"]["hodnota"] == 0.0 and tahy["panely_posun"]["krok"] == 10.0,
          f"tah panelu: meze 0..{math.floor(rp0['panely_info']['posun_max'] / 10.0) * 10} po 10 mm ({tahy['panely_posun']['min']}..{tahy['panely_posun']['max']})")
    check(tahy["stojky_vyska"]["hodnota"] == 1073.0 and tahy["stojky_vyska"]["max"] == 1500.0 and tahy["stojky_vyska"]["min"] >= MIN_STOJKY - 1e-6 and tahy["stojky_vyska"]["min"] <= MIN_STOJKY + 10, f"tah stojek: 1073, meze ({tahy['stojky_vyska']['min']}..{tahy['stojky_vyska']['max']})")
    check(tahy["elzlab_y"]["min"] == mz["y"]["min"] and tahy["elzlab_y"]["max"] == mz["y"]["max"] and tahy["elzlab_z"]["min"] == mz["z"]["min"] and tahy["elzlab_z"]["max"] == mz["z"]["max"], "tahy elektrozlabu: meze z elzlab_meze")
cm = {c["id"]: c for c in ov["casti"]}
pm = cm.get("panely")
check(pm is not None, "3D cast panely")
if pm:
    def pol_(text_):
        return next((m for m in pm["menu"] if m["text"] == text_), None)
    pridat, posl, dolu = pol_("Přidat panel"), pol_("Odebrat panel (i elektrožlab)"), pol_("Panely vrátit do spodní polohy")
    zakladni = [m for m in pm["menu"] if not m["text"].startswith("Zvolit panel ")]          # + "Zvolit panel N mm" pro ostatni delky panelu (2026-10-07; viz test_panely_delky.py)
    check(pridat and posl and dolu and len(zakladni) == 4 and zakladni[3]["nastav"] == {"panely_z": 0.0} and len(pm["menu"]) == 4 + len(S.PANEL_DELKY) - 1, f"menu 1 panelu: pridat / odebrat posledni (i elektrozlab) / dolu / doprostred mezi nohy + volby delky ({[m['text'] for m in pm['menu']]})")
    if pridat and posl and dolu:
        check(not pridat["zakazano"] and pridat["nastav"]["panely_pocet"] == 2 and S.sestav_stul(**pridat["nastav"])["panely_info"]["pocet"] == 2, "menu: pridat panel -> 2 panely")
        check(S.sestav_stul(**posl["nastav"])["parametry"]["panely"] is False and not panely(S.sestav_stul(**posl["nastav"])), "menu: odebrat posledni panel = panely i elektrozlab pryc")
        check(dolu["zakazano"], "menu: panely uz jsou dole = zakazano")
        r2p = S.sestav_stul(panely_pocet=2)
        o2 = {c["id"]: c for c in S.ovladani_3d(r2p)["casti"]}["panely"]
        p2 = next(m for m in o2["menu"] if m["text"] == "Přidat panel")
        check(p2["zakazano"] and p2["duvod"], "menu: pri plne kapacite je pridat panel zakazano s duvodem")
        check(S.sestav_stul(**{"panely_pocet": 2, **next(m for m in o2["menu"] if m["text"] == "Odebrat panel")["nastav"]})["panely_info"]["pocet"] == 1, "menu: odebrat panel -> o jeden mene")
        vsechny = next((m for m in o2["menu"] if m["text"] == "Odebrat všechny panely (i elektrožlab)"), None)
        check(vsechny and S.sestav_stul(**vsechny["nastav"])["parametry"]["panely"] is False, "menu 2 panelu: odebrat vsechny panely (i elektrozlab)")
        o3 = {c["id"]: c for c in S.ovladani_3d(S.sestav_stul(panely_posun=100.0))["casti"]}["panely"]
        d3 = next(m for m in o3["menu"] if m["text"] == "Panely vrátit do spodní polohy")
        check(not d3["zakazano"] and S.sestav_stul(**{"panely_posun": 100.0, **d3["nastav"]})["parametry"]["panely_posun"] == 0.0, "menu: panely vratit dolu")

# ---------------------------------------------------------------------------------------------------------------------
print("I) mutace (test musi chytit zamerne poskozeni pravidel)")


def meridla_panelu(**kw):
    """Zmerene hodnoty vychoziho stolu s panelem (nezavisle na generatoru) -> seznam poruseni; prazdny seznam = vse sedi."""
    rr = S.sestav_stul(**kw)
    chyby = []
    pn, ls = panely(rr), listy(rr)
    if len(pn) != 1 or len(ls) != 2:
        return ["pocet panelu/profilu"]
    plo, phi = bb(pn[0][2])
    zl_, zp_ = bb(dil(rr, NOHA_ZL)), bb(dil(rr, NOHA_ZP))
    nz, vy = sorted(ls, key=lambda x: bb(x[2])[0][1])
    if abs((plo[1] - bb(nz[2])[1][1]) - 1.0) > 0.01 or abs((bb(vy[2])[0][1] - phi[1]) - 1.0) > 0.01:
        chyby.append("mezera panel - profil neni 1 mm")
    if abs((phi[2] - plo[2]) - PANEL_S) > 0.05 or abs((phi[1] - plo[1]) - PANEL_V) > 0.05:
        chyby.append("rozmer panelu")
    if abs((plo[2] - zl_[1][2]) - (zp_[0][2] - phi[2])) > 0.01:
        chyby.append("panel neni vystredeny")
    if abs((bb(nz[2])[0][1] - bb(dil(rr, ("t", S.ZRAIL_PRAC_ZAD)))[1][1]) - 2.0) > 0.01:
        chyby.append("spodni profil neni 2 mm nad pricku")
    if abs(bb(nz[2])[0][2] - zl_[1][2]) > 0.05 or abs(bb(nz[2])[1][2] - zp_[0][2]) > 0.05:
        chyby.append("profil nedosedá na stojky")
    return chyby


def meridla_ramu():
    rr = S.sestav_stul(sirka=2000)
    chyby = []
    if rr["panely_info"]["rezim"] != "ram" or "RM" in kl(rr):
        chyby.append("rezim ram")
    zad, pred = bb(dil(rr, ("t", S.ZRAIL_PRAC_ZAD))), bb(dil(rr, ("t", S.ZRAIL_PRAC_PRED)))
    if abs((zad[1][2] - zad[0][2]) - (2000 - 2 * P)) > 0.05 or abs((pred[1][2] - pred[0][2]) - (2000 - 2 * P)) > 0.05:
        chyby.append("podelniky nejsou cele")
    top = bb(dil(rr, "XM_prac"))
    if abs(top[0][0] - pred[1][0]) > 0.05 or abs(top[1][0] - zad[0][0]) > 0.05:
        chyby.append("horni pricka ramu")
    return chyby


_PG_ORIG = S._panel_geometrie
check(meridla_panelu() == [] and meridla_ramu() == [], "mutace: bez poskozeni merici funkce nic nenajdou")
MUTACE = (("PANEL_MEZERA = 2 mm", lambda: setattr(S, "PANEL_MEZERA", 2.0), lambda: setattr(S, "PANEL_MEZERA", 1.0), meridla_panelu),
          ("PANEL_ODSTUP_OD_PRICKY = 8 mm", lambda: setattr(S, "PANEL_ODSTUP_OD_PRICKY", 8.0), lambda: setattr(S, "PANEL_ODSTUP_OD_PRICKY", 2.0), meridla_panelu),
          ("RAM_ZAPNUT = False (ram se nikdy nezvoli)", lambda: setattr(S, "RAM_ZAPNUT", False), lambda: setattr(S, "RAM_ZAPNUT", True), meridla_ramu),
          ("panel (pro vypocet useku) o 10 mm uzsi", lambda: setattr(S, "_panel_geometrie", lambda _o=S._panel_geometrie: {**_o(), "s": _o()["s"] - 10.0}), lambda: setattr(S, "_panel_geometrie", _PG_ORIG),
           lambda: ([] if S.panel_limity()["min_sirka"] == MIN_SIRKA and len(panely(S.sestav_stul(sirka=MIN_SIRKA - 5))) == 0 else ["min sirka"])))
for nazev, zapni, vrat, mer in MUTACE:
    try:
        zapni()
        poruseni = mer()
    except Exception as e:                           # noqa: BLE001 - vyjimka z poskozene konstrukce je take zachyceni
        poruseni = [f"vyjimka {type(e).__name__}"]
    finally:
        vrat()
    check(bool(poruseni), f"mutace '{nazev}' musi byt zachycena ({poruseni[:2]})")
check(meridla_panelu() == [] and meridla_ramu() == [], "po mutacich je vse zase v poradku")

print()
print(f"{OK} kontrol OK" if not FAILS else f"{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
