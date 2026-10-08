#!/usr/bin/env python3
"""Test SIKME POLICE NA BOXY (typ `sikma`) horni police generatoru stolu (bot8, fork 3, 2. kolo, 2026-10-08; zadani: ram se sklonem dopredu dolu, vychozi 15 st., drzi ho 2 naklapeci konzole
#3323 / #3324 na zadnich stojkach, vpredu lem z PR10 s uhelniky, deska laminodeska 18 / 12 mm, vyska = vyska zadniho okraje desky). Bez DB.

NEZAVISLE na kodu modulu (mereni z OBB dilu ve svete: poloha + kvaternion + meritko + bbox z GLB; ocekavane hodnoty jsou ZADANI tady v testu):
  S0) konzoly #3323 / #3324: tvar z GLB (zadni rovina listu, rovina desky kloubu, osa otvoru kloubu, delka) odpovida konstantam modulu;
  S1) mrizka system x sirka x panely x sklon x hloubka x LED: osa zadni pricky v rovine stojek, bocni profily skloneny o presne sklon, predni pricka nize o (hloubka - P) x sin(sklon),
      deska lezi na rame (spodni plocha na hornim lici, horni zadni roh ve vysce `hv`), lem kolmo k desce vpredu, konzoly (zadni plocha na predním licu stojky, rovina desky kloubu na vnejsim licu
      bocniho profilu, osa kloubu na ose profilu), nejnizsi bod >= 50 mm nad deskou stolu, nejvyssi bod >= 15 mm pod ramenem LED, zadna kolize (vlastni SAT OBB x AABB), spoje (lic_peers) a pocty
      spojek / zaslepek / uhelniku, automaticka vyska je nejmensi mozna (po 10 mm), ostatni dily stolu beze zmeny;
  S2) nevejde se: stul se strednimi zadnimi nohami (dva useky), nizke stojky, hloubka; automaticke odebrani s oznamenim; `typy[].duvod`;
  S3) vstup, hash, token-stav: sklon se mimo sikmou polici do hashe nepocita, jina hodnota meni hash, rozsah, dotaz ?hpolice_sklon;
  S4) cena a vyroba: konzoly v polozkach ceny, spojovaci material, vyrobni vypis (konzoly a uhelniky v kroku 7, profily a desky v kroku 1), GLB;
  S5) 3D menu: polozky sklonu, prepnuti typu, preklady cs / en / sk.
Spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-07_police_stojky/test_hpolice_sikma.py     (STUL_API_OVERRIDE=<adresar api> = kandidat)
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1."""
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
    sys.path.insert(0, API)
    import app  # noqa: F401,E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_ovladani_verejne as OV  # noqa: E402
finally:
    threading.Thread.start = _orig
try:
    import stul_hpolice as HP  # noqa: E402
    HP.KONZOLE_GEO
except (ImportError, AttributeError):
    print("CHYBA: modul api/stul_hpolice.py (verze se sikmou polici) neni nasazen (test patri ke kandidatu 2. kola, STUL_API_OVERRIDE)")
    sys.exit(1)

OK, FAILS = 0, []
PRVNI_CHYBA = bool(os.environ.get("HPOL_PRVNI_CHYBA"))


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
    out = [(i, k, r["dily"][i]) for i, k in enumerate(kl(r)) if isinstance(k, tuple) and k and k[0] == "hpol" and (role is None or k[2] == role) and (s is None or k[1] == s)]
    return sorted(out, key=lambda t: t[1])


def sestav(**cfg):
    return S.sestav_stul(**cfg)


# ---------------------------------------------------------------------------------------------------------------------
# ZADANI
# ---------------------------------------------------------------------------------------------------------------------
TL = {"lam18": 18.0, "lam12": 12.0}
KONZ_PART = {30: "product_3323", 35: "product_3323", 40: "product_3324", 45: "product_3324"}
UHELNIK = {30: "product_3045", 35: "product_3045", 40: "product_3207", 45: "product_3207"}
DESKA_PART = {"lam18": "product_4933", "lam12": HP.LAM12_PART}
PREPAZKA_PART, PREPAZKA_TL, LEM_VYSKA = "product_3539", 10.0, 40.0
MEZERA_NAD_PANELY, VYSKA_BEZ_PANELU, MEZERA_POD_RAMENEM, MIN_NAD_DESKOU = 60.0, 150.0, 15.0, 50.0
SIRKA_MIN_PLUS = 120.0
ROZPON = {"lam18": 800.0, "lam12": 600.0}
TOL = 0.06
SKLONY = (5.0, 15.0, 30.0)
NOHA_ZL, NOHA_ZP = ("t", S.NOHA_ZL), ("t", S.NOHA_ZP)
# konzoly (mereno z GLB v sekci S0; zde jako zadani): zadni plocha listu, rovina desky kloubu, osa kloubu (x = 0), polomer otvoru, polovina delky
KONZ_GEO = {"product_3323": {"y_zad": -3.0, "z_b": 20.02, "pivot_y": 20.98, "r_otvor": 3.25, "pul_x": 60.0},
            "product_3324": {"y_zad": -19.0, "z_b": -3.0, "pivot_y": 0.0, "r_otvor": 4.0, "pul_x": 60.0}}


tl_dilu = HP.tloustka_dilu


def profil_mm(system):
    return float(S.SYSTEMY[system]["profil_mm"])


def obb(d):
    """(stred, osy po sloupcich, polorozmery) dilu: poloha + kvaternion + meritko + bbox z GLB."""
    lo, hi = S.glb_bbox(d["part_id"])
    R = S.kvat_na_matici(d["quaternion"])
    s = np.array(d["scale"], float)
    c_l = (np.array(lo, float) + np.array(hi, float)) / 2.0
    return np.array(d["position"], float) + R @ (s * c_l), R, np.abs(s) * (np.array(hi, float) - np.array(lo, float)) / 2.0


def rohy(d):
    c, R, h = obb(d)
    return np.array([c + R @ (h * np.array([sx, sy, sz])) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])


def sat(c1, R1, h1, c2, R2, h2):
    """Oddeleni dvou OBB (mm): > 0 mezera, < 0 prunik (nejvetsi oddeleni pres 15 deliciich os)."""
    osy = [R1[:, i] for i in range(3)] + [R2[:, i] for i in range(3)]
    for i in range(3):
        for j in range(3):
            a = np.cross(R1[:, i], R2[:, j])
            n = np.linalg.norm(a)
            if n > 1e-9:
                osy.append(a / n)
    best = -1e18
    for a in osy:
        r1 = sum(abs(a @ R1[:, i]) * h1[i] for i in range(3))
        r2 = sum(abs(a @ R2[:, i]) * h2[i] for i in range(3))
        best = max(best, abs(a @ (c2 - c1)) - r1 - r2)
    return best


def uhel_z(v):
    return math.degrees(math.atan2(v[1], v[0]))


def r0_mereni(r0):
    dily, klice = r0["dily"], kl(r0)
    prac = [bb(d)[1][1] for d, k in zip(dily, klice) if k == ("t", S.DESKA_PRAC) or (d.get("deska_id") or "").startswith("prac_")]
    y_desky = float(max(prac))
    listy = [bb(d)[1][1] for d, k in zip(dily, klice) if isinstance(k, tuple) and k[0] == "panrail"]
    y_pan = float(max(listy)) if listy else None
    ramena = [bb(dil(r0, k))[0][1] for k in (("t", S.XRAIL_TOP_L), ("t", S.XRAIL_TOP_P)) if k in klice]
    y_strop = float(min(ramena)) if ramena else float(max(bb(dil(r0, NOHA_ZL))[1][1], bb(dil(r0, NOHA_ZP))[1][1]))
    return {"y_desky": y_desky, "y_pan": y_pan, "y_strop": y_strop}


def useky_mezi_stojkami(r, y_desky):
    klice = kl(r)
    posty = []
    for k in (NOHA_ZL, "RM", NOHA_ZP):
        if k in klice:
            lo, hi = bb(dil(r, k))
            if hi[1] > y_desky + 50.0:
                posty.append((float(lo[2]), float(hi[2]), (lo, hi)))
    posty.sort()
    return [(posty[i][1], posty[i + 1][0]) for i in range(len(posty) - 1)], posty


# ---------------------------------------------------------------------------------------------------------------------
print("S0) naklapeci konzole: tvar z GLB")
try:
    import trimesh
except ImportError:
    trimesh = None
    print("   (trimesh neni k dispozici: kontrola tvaru GLB se preskakuje)")
for pid, g in KONZ_GEO.items():
    lo, hi = S.glb_bbox(pid)
    check(abs(lo[1] - g["y_zad"]) < 0.01 and abs(lo[2] - g["z_b"]) < 0.05 and abs(hi[0] - lo[0] - 2 * g["pul_x"]) < 0.01, f"S0 {pid}: bbox GLB (zadni plocha y {lo[1]:.3f}, rovina desky z {lo[2]:.3f}, delka {hi[0] - lo[0]:.2f})")
    ge = HP.KONZOLE_GEO[pid]
    check(all(abs(ge[k] - g[k]) < 0.01 for k in ("y_zad", "z_b", "pivot_y", "pul_x")), f"S0 {pid}: konstanty modulu {ge} == zadani {g}")
    if trimesh is not None:
        m = list(trimesh.load(os.path.join(S.KATALOG_DIR, f"{pid}.glb"), force="scene").geometry.values())[0]
        V = np.asarray(m.vertices, float)
        kruh = V[(V[:, 2] < g["z_b"] + 3.1) & (np.hypot(V[:, 0], V[:, 1] - g["pivot_y"]) < g["r_otvor"] + 1.5)]            # vrcholy desky kloubu kolem osy kloubu
        rr = np.hypot(kruh[:, 0], kruh[:, 1] - g["pivot_y"])
        check(len(kruh) >= 20 and abs(rr.min() - g["r_otvor"]) < 0.06, f"S0 {pid}: otvor kloubu je kolem (0, {g['pivot_y']}) o polomeru {g['r_otvor']} ({len(kruh)} vrcholu, min polomer {rr.min() if len(rr) else None})")

# ---------------------------------------------------------------------------------------------------------------------
print("S1) mrizka: geometrie sikme police nezavisle z OBB")


def over_sikmou(cfg, nazev, deska, sklon, hv_zad=None, hl_zad=None):
    system = int(cfg.get("system", 30))
    P, H = profil_mm(system), profil_mm(system) / 2.0
    kw = dict(cfg, hpolice=True, hpolice_typ="sikma", hpolice_deska=deska, hpolice_sklon=sklon)
    if hv_zad is not None:
        kw["hpolice_vyska"] = hv_zad
    if hl_zad is not None:
        kw["hpolice_hloubka"] = hl_zad
    r = sestav(**kw)
    r0 = sestav(**cfg)
    m0 = r0_mereni(r0)
    useky, posty = useky_mezi_stojkami(r0, m0["y_desky"])
    odebrano = [o["volba"] for o in r["odebrano"]]
    jeden = len(useky) == 1 and useky[0][1] - useky[0][0] >= 2 * P + SIRKA_MIN_PLUS - 1e-6
    th = math.radians(sklon)
    c_, s_ = math.cos(th), math.sin(th)
    tl = TL[deska]
    x_post = (posty[0][2][0][0] + posty[0][2][1][0]) / 2.0
    x_pred = (bb(dil(r0, ("t", S.NOHA_PL)))[0][0] + bb(dil(r0, ("t", S.NOHA_PL)))[1][0]) / 2.0
    h_max_t = min(600.0, (x_post - x_pred) + P)
    dout = min(max(300.0 if hl_zad is None else float(hl_zad), 150.0), max(h_max_t, 150.0))
    kg = KONZ_GEO[KONZ_PART[system]]
    dpiv = kg["pivot_y"] - kg["y_zad"]
    y_c_rel = -(H + dpiv) * math.tan(th)
    rear_top = H * s_ + (H + tl) * c_
    rear_low = -H * (c_ + s_)
    front_low = -(dout - P) * s_ - H * (c_ + s_)
    lip_top = (-(dout - P) - H + PREPAZKA_TL) * s_ + (H + LEM_VYSKA) * c_
    low = min(front_low, y_c_rel - kg["pul_x"], rear_low)
    lo_cg, hi_cg = S.glb_bbox(S.SYSTEMY[system]["spojka"])
    L_g = float(max(hi_cg - lo_cg))                                      # rameno rohove spojky ramene LED u stojky (konzola musi byt pod ni + 5 mm)
    high = max(rear_top, lip_top, y_c_rel + kg["pul_x"] + max(0.0, L_g + 5.0 - MEZERA_POD_RAMENEM), H * (s_ + c_))
    hv_max = m0["y_strop"] - MEZERA_POD_RAMENEM - m0["y_desky"] + rear_top - high
    min_raw = max(100.0, MIN_NAD_DESKOU - low + rear_top)
    if m0["y_pan"] is not None:
        hv_pan = m0["y_pan"] + MEZERA_NAD_PANELY - m0["y_desky"] + rear_top - rear_low
        min_raw = max(min_raw, hv_pan)
        auto_raw = hv_pan
    else:
        auto_raw = VYSKA_BEZ_PANELU - low + rear_top
    hv_min = math.ceil(min_raw / 10.0 - 1e-9) * 10.0
    hv_auto = math.ceil(max(auto_raw, min_raw) / 10.0 - 1e-9) * 10.0
    vejde = jeden and hv_min <= hv_max + 1e-6 and hv_auto <= hv_max + 1e-6
    if not vejde:
        check(not r["parametry"]["hpolice"] and "hpolice" in odebrano, f"{nazev}: nevejde se (usekum {len(useky)}, auto {hv_auto:g}, min {hv_min:g}, max {hv_max:g}) -> police odebrana ({r['parametry']['hpolice']}, {odebrano})")
        return None
    check(r["parametry"]["hpolice"] and "hpolice" not in odebrano and not r["problemy"], f"{nazev}: vejde se a je bez problemu (auto {hv_auto:g}, max {hv_max:g}; odebrano {odebrano}, problemy {[(x['kod'], x['text'][:80]) for x in r['problemy']]})")
    hp = r["hpolice_info"]
    if not (r["parametry"]["hpolice"] and hp):
        return None
    hv = hv_auto if hv_zad is None else min(max(float(hv_zad), hv_min), max(hv_max, hv_min))
    check(abs(hp["vyska"]["hodnota"] - hv) < TOL and abs(hp["vyska"]["min"] - hv_min) < TOL and abs(hp["vyska"]["max"] - hv_max) < TOL and hp["vyska"]["auto"] == (hv_zad is None),
          f"{nazev}: hpolice_info.vyska {hp['vyska']} == hodnota {hv:g} / min {hv_min:g} / max {hv_max:g}")
    check(abs(hp["sklon"]["hodnota"] - sklon) < TOL and abs(hp["hloubka"]["hodnota"] - dout) < TOL, f"{nazev}: sklon {hp['sklon']} a hloubka {hp['hloubka']['hodnota']} == {sklon:g} / {dout:g}")
    a, b = useky[0]
    G_ = b - a
    y_s = m0["y_desky"] + hv - rear_top                                   # osa zadni pricky (stred otaceni) podle zadani: horni zadni roh desky ve vysce hv nad deskou stolu
    O = np.array([x_post, y_s, 0.0])
    d = np.array([-c_, -s_, 0.0])                                         # smer sklonu (dopredu dolu)
    n = np.array([-s_, c_, 0.0])                                          # normala desky (nahoru a dopredu)
    # --- zadni pricka
    zad, pred = dil(r, ("hpol", 0, "zad")), dil(r, ("hpol", 0, "pred"))
    cz, Rz, hz = obb(zad)
    cp, Rp, hpp = obb(pred)
    check(np.allclose(cz, O + np.array([0, 0, (a + b) / 2.0]), atol=TOL), f"{nazev}: stred zadni pricky v rovine stojek ve vysce osy {cz.round(2).tolist()} vs {(O + np.array([0, 0, (a + b) / 2.0])).round(2).tolist()}")
    dl_os = int(np.argmax(hz))
    check(abs(abs(Rz[2, dl_os]) - 1.0) < 1e-4 and abs(2 * hz[dl_os] - G_) < TOL, f"{nazev}: zadni pricka je rovnobezna s osou Z a dlouha {G_:.1f} (osa {Rz[:, dl_os].round(3).tolist()}, delka {2 * hz[dl_os]:.2f})")
    kratke = [i for i in range(3) if i != dl_os]
    check(all(abs(((uhel_z(Rz[:, i]) - sklon + 45.0) % 90.0) - 45.0) < 0.02 for i in kratke), f"{nazev}: prurez zadni pricky je otoceny o sklon {sklon:g} st. kolem sve osy ({[round(uhel_z(Rz[:, i]), 2) for i in kratke]})")
    check(abs(2 * hz[kratke[0]] - P) < TOL and abs(2 * hz[kratke[1]] - P) < TOL, f"{nazev}: prurez zadni pricky {P:g}")
    # --- predni pricka: o (dout - P) dopredu po sklonu
    check(np.allclose(cp, O + (dout - P) * d + np.array([0, 0, (a + b) / 2.0]), atol=TOL), f"{nazev}: predni pricka je o {dout - P:g} mm dal po sklonu ({cp.round(2).tolist()} vs {(O + (dout - P) * d + np.array([0, 0, (a + b) / 2.0])).round(2).tolist()})")
    check(abs(2 * hpp[int(np.argmax(hpp))] - G_) < TOL and abs(abs(Rp[2, int(np.argmax(hpp))]) - 1.0) < 1e-4, f"{nazev}: predni pricka rovnobezna s Z, delka {G_:.1f}")
    # --- boky a mezilisty
    boky = hpol(r, "bok", 0)
    mezi = hpol(r, "mezi", 0)
    n_ocek = 0
    while ((G_ - 2 * P) - n_ocek * P) / (n_ocek + 1) > ROZPON[deska] + 1e-9:
        n_ocek += 1
    check(len(boky) == 2 and len(mezi) == n_ocek, f"{nazev}: 2 boky a {n_ocek} mezilist pro rozpon {ROZPON[deska]:g} ({len(boky)}, {len(mezi)})")
    for _, kk, dd in boky + mezi:
        cs, Rs, hs = obb(dd)
        os_ = int(np.argmax(hs))
        osa = Rs[:, os_] * (1 if Rs[:, os_] @ d >= 0 else -1)
        L = dout - 2 * P
        check(np.allclose(osa, d, atol=1e-4) and abs(2 * hs[os_] - L) < TOL, f"{nazev} {kk}: osa sikme (-cos, -sin) a delka {L:g} ({osa.round(4).tolist()}, {2 * hs[os_]:.2f})")
        zc = cs[2]
        check(np.allclose(cs, O + (H + L / 2.0) * d + np.array([0, 0, zc]), atol=TOL), f"{nazev} {kk}: stred bocniho profilu: zadni konec dosedá na predni lico zadni pricky ({cs.round(2).tolist()})")
        if kk[2] == "bok":
            z_oc = (a + H) if kk[3] == 0 else (b - H)
            check(abs(zc - z_oc) < TOL, f"{nazev} {kk}: bocni profil lezi na vnitrnim lici stojky (z {zc:.2f} vs {z_oc:.2f})")
    if mezi:
        zs = sorted(float(obb(dd)[0][2]) for _, _, dd in mezi)
        pole = [(zs[0] - H) - (a + P)] + [(zs[j + 1] - H) - (zs[j] + H) for j in range(len(zs) - 1)] + [(b - P) - (zs[-1] + H)]
        check(max(pole) - min(pole) < TOL and max(pole) <= ROZPON[deska] + TOL, f"{nazev}: volna pole mezi profily stejna a nejvyse {ROZPON[deska]:g} ({np.round(pole, 1).tolist()})")
    # --- deska
    dk = hpol(r, "deska", 0)
    check(len(dk) >= 1 and all(dd["part_id"] == DESKA_PART[deska] for _, _, dd in dk), f"{nazev}: deska {deska} ({len(dk)} kusu)")
    for _, kk, dd in dk:
        c, R, h = obb(dd)
        k_n = int(np.argmin(h))
        nn = R[:, k_n] * (1 if R[:, k_n] @ n >= 0 else -1)
        check(np.allclose(nn, n, atol=1e-4) and abs(2 * h[k_n] - tl) < TOL, f"{nazev} {kk}: deska tlusta {tl:g} s normalou ({-s_:.3f}, {c_:.3f}) ({nn.round(4).tolist()})")
        check(abs((c - O) @ n - (H + tl / 2.0)) < TOL, f"{nazev} {kk}: spodni plocha desky lezi na hornim lici ramu (vzdalenost stredu {(c - O) @ n:.3f} vs {H + tl / 2.0:g})")
        t_zad = float(((rohy(dd) - O) @ (-d)).max())
        check(abs(t_zad - H) < TOL, f"{nazev} {kk}: deska konci na zadnim lici zadni pricky (t {t_zad:.3f} vs {H:g})")
    horni = max(float(rohy(dd)[:, 1].max()) for _, _, dd in dk)
    check(abs((horni - m0["y_desky"]) - hv) < TOL, f"{nazev}: horni zadni roh desky {horni - m0['y_desky']:.3f} mm nad deskou stolu == vyska {hv:g}")
    # --- lem
    lem = hpol(r, "lem", 0)
    check(len(lem) == max(1, math.ceil(G_ / 2500.0 - 1e-9)) and all(dd["part_id"] == PREPAZKA_PART for _, _, dd in lem), f"{nazev}: lem PR10 ({len(lem)} kusu)")
    for _, kk, dd in lem:
        c, R, h = obb(dd)
        tenka = int(np.argmin(h))
        osa_t = R[:, tenka] * (1 if R[:, tenka] @ d >= 0 else -1)
        check(abs(2 * h[tenka] - PREPAZKA_TL) < TOL and np.allclose(osa_t, d, atol=1e-4), f"{nazev} {kk}: lem tlusty {PREPAZKA_TL:g} je kolmy k desce (tloustka ve smeru sklonu)")
        t_c = (c - O) @ d
        n_c = (c - O) @ n
        check(abs(t_c - ((dout - P) + H - PREPAZKA_TL / 2.0)) < TOL and abs(n_c - (H + LEM_VYSKA / 2.0)) < TOL, f"{nazev} {kk}: lem stoji na predni pricce u jejiho predniho lice (t {t_c:.2f}, n {n_c:.2f})")
    uh = hpol(r, "uhel", 0)
    n_b = max(2, math.ceil(G_ / 450.0))
    check(len(uh) == n_b and all(dd["part_id"] == UHELNIK[system] for _, _, dd in uh), f"{nazev}: {n_b} uhelniku lemu {UHELNIK[system]} ({len(uh)})")
    for _, kk, dd in uh:
        c, R, h = obb(dd)
        lem0 = lem[0][2]
        sep = sat(c, R, h, *obb(lem0))
        check(sep < 1.5, f"{nazev} {kk}: uhelnik dosedá na lem (oddeleni {sep:.2f} mm)")
        nmin = float(((rohy(dd) - O) @ n).min())
        check(abs(nmin - H) < 0.1, f"{nazev} {kk}: uhelnik lemu lezi na hornim lici ramu (nejnizsi bod {nmin:.3f} nad osou, ocekavano {H:g})")
    # --- konzoly
    kz = {(kk[3]): dd for _, kk, dd in hpol(r, "konz", 0)}
    check(set(kz) == {0, 1} and all(dd["part_id"] == KONZ_PART[system] for dd in kz.values()), f"{nazev}: 2 konzoly {KONZ_PART[system]} ({sorted(kz)})")
    for j, dd in kz.items():
        c, R, h = obb(dd)
        lokalni = lambda p_: np.array(dd["position"], float) + R @ (np.array(dd["scale"], float) * np.array(p_, float))
        lo_l, hi_l = S.glb_bbox(dd["part_id"])
        zad_rohy = np.array([lokalni([x, kg["y_zad"], z]) for x in (-kg["pul_x"], kg["pul_x"]) for z in (lo_l[2], hi_l[2])])
        check(np.allclose(zad_rohy[:, 0], x_post - H, atol=TOL), f"{nazev} konzola {j}: zadni plocha listu lezi na predním licu stojky (x {zad_rohy[:, 0].round(3).tolist()} vs {x_post - H:.3f})")
        z_lico = a if j == 0 else b
        deskove = np.array([lokalni([x, y, kg["z_b"]]) for x in (-kg["pul_x"], kg["pul_x"]) for y in (kg["y_zad"], kg["pivot_y"] + 40)])
        check(np.allclose(deskove[:, 2], z_lico, atol=TOL), f"{nazev} konzola {j}: rovina desky kloubu lezi na vnejsim licu bocniho profilu (z {deskove[:, 2].round(3).tolist()} vs {z_lico:.3f})")
        list_z = [lokalni([0, kg["y_zad"], z])[2] for z in (kg["z_b"] + 1.0, kg["z_b"] + 20.0)]
        check((list_z[1] - list_z[0]) * (-1 if j == 0 else 1) > 0, f"{nazev} konzola {j}: list zasahuje do stojky (smerem od bocniho profilu)")
        horni_konz = float(max(lokalni([x, y, z])[1] for x in (-kg["pul_x"], kg["pul_x"]) for y in (kg["y_zad"], kg["pivot_y"] + 64) for z in (lo_l[2], hi_l[2])))
        check(horni_konz <= m0["y_strop"] - (L_g + 5.0) + TOL, f"{nazev} konzola {j}: horni okraj konzoly {m0['y_strop'] - horni_konz:.1f} mm pod ramenem LED (aspon {L_g + 5.0:.1f}: pod rohovou spojkou ramene)")
        piv = lokalni([0, kg["pivot_y"], kg["z_b"]])
        # vzdalenost osy kloubu od osy bocniho profilu (v rovine xy): osa prochazi O smerem d
        v_ = piv[:2] - O[:2]
        vzd = abs(v_[0] * d[1] - v_[1] * d[0])
        check(vzd < 0.1, f"{nazev} konzola {j}: osa kloubu lezi na ose bocniho profilu (vzdalenost {vzd:.3f} mm)")
        check(abs(piv[0] - (x_post - H - dpiv)) < TOL and abs(piv[1] - (y_s + y_c_rel)) < TOL, f"{nazev} konzola {j}: kloub {dpiv:.2f} mm pred licem stojky ve vysce {y_s + y_c_rel:.2f} ({piv.round(2).tolist()})")
    # --- nejnizsi / nejvyssi bod, kolize
    skup = [d_ for _, _, d_ in hpol(r)]
    sk_rohy = np.vstack([rohy(d_) for d_ in skup])
    check(sk_rohy[:, 1].min() >= m0["y_desky"] + MIN_NAD_DESKOU - TOL, f"{nazev}: nejnizsi bod police {sk_rohy[:, 1].min() - m0['y_desky']:.1f} mm nad deskou stolu >= {MIN_NAD_DESKOU:g}")
    check(sk_rohy[:, 1].max() <= m0["y_strop"] - MEZERA_POD_RAMENEM + TOL, f"{nazev}: nejvyssi bod police je aspon {MEZERA_POD_RAMENEM:g} mm pod stropem ({m0['y_strop'] - sk_rohy[:, 1].max():.1f})")
    if m0["y_pan"] is not None:
        zadni_nej = float(rohy(zad)[:, 1].min())
        check(zadni_nej >= m0["y_pan"] + MEZERA_NAD_PANELY - TOL, f"{nazev}: spodni roh zadni pricky je aspon {MEZERA_NAD_PANELY:g} mm nad hornim profilem panelu ({zadni_nej - m0['y_pan']:.1f})")
    if hv_zad is None:                                                 # automaticka vyska je NEJMENSI mozna (po 10 mm): o 10 mm nizsi by porusila nektere pravidlo
        marze_dolni = float(sk_rohy[:, 1].min()) - (m0["y_desky"] + (MIN_NAD_DESKOU if m0["y_pan"] is None else MIN_NAD_DESKOU))
        marze_pan = (float(rohy(zad)[:, 1].min()) - (m0["y_pan"] + MEZERA_NAD_PANELY)) if m0["y_pan"] is not None else 1e9
        marze_auto = (float(sk_rohy[:, 1].min()) - (m0["y_desky"] + VYSKA_BEZ_PANELU)) if m0["y_pan"] is None else 1e9
        check(min(marze_pan, marze_auto) < 10.0 + TOL or marze_dolni < 10.0 + TOL or hv <= hv_min + 1e-6, f"{nazev}: automaticka vyska {hv:g} je nejmensi mozna (rezervy {marze_pan:.1f} / {marze_auto:.1f} / {marze_dolni:.1f})")
    # vlastni SAT: dily skupiny proti vsem ostatnim dilum stolu
    klice = kl(r)
    skup_idx = {i for i, k in enumerate(klice) if isinstance(k, tuple) and k and k[0] == "hpol"}
    vlastnici = {}
    for j, d_ in enumerate(r["dily"]):
        for i2 in (d_.get("lic_peers") or []):
            if i2 < len(r["dily"]) and r["dily"][i2]["part_id"] in S.SPOJKY_PARTS:
                vlastnici.setdefault(i2, set()).add(j)
    spojky_skup = {i2 for i2, vl in vlastnici.items() if vl & skup_idx}
    zasl_skup = {i for i, k in enumerate(klice) if isinstance(k, tuple) and k and k[0] == "zasl" and isinstance(k[1], tuple) and k[1][0] == "hpol"}
    vsechny_skup = skup_idx | spojky_skup | zasl_skup
    ostatni = [i for i in range(len(r["dily"])) if i not in vsechny_skup]
    nejhorsi = (-1e9, None, None)
    for i in vsechny_skup:
        c1, R1, h1 = obb(r["dily"][i])
        ob = np.abs(R1).dot(h1)
        for j in ostatni:
            lo_j, hi_j = bb(r["dily"][j])
            if np.any(lo_j > c1 + ob + 1) or np.any(hi_j < c1 - ob - 1):
                continue                                                  # AABB obalky se nedotykaji: SAT netreba
            sep = sat(c1, R1, h1, (lo_j + hi_j) / 2.0, np.eye(3), (hi_j - lo_j) / 2.0)
            if -sep > nejhorsi[0]:
                nejhorsi = (-sep, i, j)
    check(nejhorsi[0] <= S.TOL_PRUNIK_MM + 1e-6, f"{nazev}: prunik dilu police s ostatnimi dily stolu {nejhorsi[0]:.2f} mm ({klice[nejhorsi[1]] if nejhorsi[1] is not None else ''} x {klice[nejhorsi[2]] if nejhorsi[2] is not None else ''})")
    # --- spoje, spojky, zaslepky
    n_spojek = sum(1 for d_ in r["dily"] if d_["part_id"] in S.SPOJKY_PARTS) - sum(1 for d_ in r0["dily"] if d_["part_id"] in S.SPOJKY_PARTS)
    check(n_spojek == 4 + 4 * n_ocek, f"{nazev}: spojek police {n_spojek} == {4 + 4 * n_ocek} (4 rohy + 4 na mezilistu; zadne spoje se stojkami)")
    zasl = S.SYSTEMY[system]["zaslepka"]
    check(sum(1 for d_ in r["dily"] if d_["part_id"] == zasl) - sum(1 for d_ in r0["dily"] if d_["part_id"] == zasl) == 2, f"{nazev}: 2 zaslepky na volnych koncich predni pricky")
    for i in spojky_skup:
        c1, R1, h1 = obb(r["dily"][i])
        for j in vlastnici[i] & skup_idx:
            sep = sat(c1, R1, h1, *obb(r["dily"][j]))
            check(sep < S.TOL_SPOJ_MM + 1e-6, f"{nazev}: spojka #{i} dosedá na vlastnika {klice[j]} (oddeleni {sep:.2f} mm)")
        check(len(vlastnici[i]) == 2, f"{nazev}: spojka #{i} ma 2 vlastniky ({len(vlastnici[i])})")
    prof = [i for _, k, _ in hpol(r) if k[2] in ("zad", "pred", "bok", "mezi") for i in [klice.index(k)]]
    posty_s = [klice.index(k_) for k_ in (NOHA_ZL, NOHA_ZP)]
    pary = {(min(i, j), max(i, j)) for i in prof + posty_s for j in (r["dily"][i].get("lic_peers") or []) if j in prof}
    oc = set()
    for kb in [k for _, k, _ in boky + mezi]:
        for kp_ in (("hpol", 0, "zad"), ("hpol", 0, "pred")):
            oc.add((min(klice.index(kb), klice.index(kp_)), max(klice.index(kb), klice.index(kp_))))
    for _i, _k, _d in boky:                                          # konzola drzi bocni profil na nejblizsi zadni stojce: spoj stojka - bok (prace za spoj v cene; jako sikma vzpera)
        z_b = float((bb(_d)[0][2] + bb(_d)[1][2]) / 2.0)
        i_p = min(posty_s, key=lambda ip: abs(float((bb(r["dily"][ip])[0][2] + bb(r["dily"][ip])[1][2]) / 2.0) - z_b))
        oc.add((min(i_p, _i), max(i_p, _i)))
    check(pary == oc, f"{nazev}: spoje profil - profil police: boky / mezilisty x pricky + 2 x stojka - bok (konzola) ({len(pary)} vs {len(oc)})")
    # --- ostatni dily stolu beze zmeny (poloha, meritko)
    zmeneno = []
    for i0, k in enumerate(kl(r0)):
        if k in klice:
            d0, d1 = r0["dily"][i0], dil(r, k)
            if d0["part_id"] != d1["part_id"] or not np.allclose(d0["position"], d1["position"], atol=1e-6) or not np.allclose(d0["scale"], d1["scale"], atol=1e-9):
                zmeneno.append(k)
    check(not zmeneno, f"{nazev}: ostatni dily stolu se police nezmenily ({zmeneno[:3]})")
    return r


n_cfg = n_odeb = 0
t0 = time.time()
for system, (sirka, opora), panely, led in itertools.product((30, 35, 40, 45), ((1280, "auto"), (2100, "ram"), (2100, "auto")), (0, 1, 2), (True, False)):
    cfg = dict(system=system, sirka=sirka, police=1, stredni_opora=opora)
    if panely == 0:
        cfg.update(panely=False, elektrozlab=False)
    else:
        cfg.update(panely_pocet=panely)
    if not led:
        cfg.update(led=False)
    for sklon in SKLONY:
        for deska in (("lam18", "lam12") if system in (30, 35) else ("lam18",)):
            if deska == "lam12" and (sklon != 15.0 or sirka != 1280):
                continue
            for hloubka in (None, 450.0) if sklon != 5.0 else (None,):
                nazev = f"S1 s{system} W{sirka}/{opora} pan{panely} led{int(led)} {deska} sklon {sklon:g}" + (f" h{int(hloubka)}" if hloubka else "")
                r = over_sikmou(cfg, nazev, deska, sklon, None, hloubka)
                n_cfg += 1
                n_odeb += 1 if r is None else 0
print(f"   ({n_cfg} konfiguraci, {n_odeb} bez police (nevesla se / dve sekce), {time.time() - t0:.0f} s)")
check(n_cfg > 250 and n_odeb < n_cfg, f"S1: dost konfiguraci se sikmou policí ({n_cfg}, odebrano {n_odeb})")
print("S1b) zadana vyska: nejnizsi, stred, nejvyssi, mimo meze")
for system, sklon, panely in itertools.product((30, 40), (5.0, 15.0, 30.0), (0, 1)):
    cfg = dict(system=system, sirka=1500, police=1)
    if panely == 0:
        cfg.update(panely=False, elektrozlab=False)
    r_ = sestav(**dict(cfg, hpolice=True, hpolice_typ="sikma", hpolice_sklon=sklon))
    if not r_["parametry"]["hpolice"]:
        check(False, f"S1b s{system} sklon {sklon:g} pan{panely}: police se na vychozi stul nevesla")
        continue
    v = r_["hpolice_info"]["vyska"]
    for hv in (v["min"], (v["min"] + v["max"]) / 2.0, v["max"], v["max"] + 80.0, 100.0):
        over_sikmou(cfg, f"S1b s{system} sklon {sklon:g} pan{panely} vyska {hv:g}", "lam18", sklon, float(hv), None)
    if sklon == 5.0:                                                      # mala hloubka a maly sklon: horni okraj LEMU je vyssi nez zadni okraj desky (strop urcuje lem)
        r_h = sestav(**dict(cfg, hpolice=True, hpolice_typ="sikma", hpolice_sklon=sklon, hpolice_hloubka=150.0))
        if r_h["parametry"]["hpolice"]:
            over_sikmou(cfg, f"S1b s{system} sklon 5 pan{panely} hloubka 150 nejvyssi vyska", "lam18", sklon, float(r_h["hpolice_info"]["vyska"]["max"]), 150.0)

# ---------------------------------------------------------------------------------------------------------------------
print("S2) nevejde se: dva useky (stredni zadni noha), nizke stojky, uzky stul")
r = sestav(system=30, sirka=2100, stredni_opora="noha", panely=False, elektrozlab=False, hpolice=True, hpolice_typ="sikma")
check(not r["parametry"]["hpolice"] and "hpolice" in [o["volba"] for o in r["odebrano"]], f"S2: stul se strednimi zadnimi nohami (2 useky): sikma police odebrana ({r['parametry']['hpolice']})")
jadro = S._sestav_jadro(dict(S._norm_parametry(dict(S.VYCHOZI, system=30, sirka=2100, stredni_opora="noha", panely=False, elektrozlab=False, hpolice=True, hpolice_typ="sikma"))))
check("hpolice_nevejde" in [x["kod"] for x in jadro["problemy"]] and jadro["hpolice_info"]["problem"] == "sekce" and "střední zadní nohou" in " ".join(x["text"] for x in jadro["problemy"] if x["kod"] == "hpolice_nevejde"),
      f"S2: jadro hlasi hpolice_nevejde / sekce s textem o stredni zadni noze ({[x['kod'] for x in jadro['problemy']]})")
r = sestav(system=30, sirka=2100, stredni_opora="noha", panely=False, elektrozlab=False, hpolice=True, hpolice_typ="rovna")
tp = {x["typ"]: x for x in r["hpolice_info"]["typy"]}
check(tp["sikma"]["vejde"] is False and tp["sikma"]["duvod"] == "sekce" and tp["rovna"]["vejde"], f"S2: typy[] u dvou useku: sikma nevejde (duvod sekce), rovna vejde ({tp['sikma']})")
r = sestav(system=30, sirka=2100, stredni_opora="ram", hpolice=True, hpolice_typ="sikma", panely=False, elektrozlab=False)
check(r["parametry"]["hpolice"] and not r["problemy"], "S2: vestaveny ram = jeden dlouhy usek: sikma police se postavi")
for system, sv in itertools.product((30, 40), (300.0, 400.0, 500.0)):
    cfg = dict(system=system, stojky_vyska=sv, panely=False, elektrozlab=False)
    over_sikmou(cfg, f"S2 nizke stojky s{system} {sv:g}", "lam18", 15.0, None, None)
r = sestav(system=30, hpolice=True, hpolice_typ="sikma", stojky=False, panely=False, led=False, elektrozlab=False)
check(not r["parametry"]["hpolice"] and not r["problemy"] and "hpolice" in [o["volba"] for o in r["odebrano"]], f"S2: bez zadnich stojek se sikma police odebere ({r['parametry']['hpolice']}, {[x['kod'] for x in r['problemy']]})")
nab = S.nabidky_roztazeni(system=30, stojky_vyska=300.0, panely=False, elektrozlab=False)
check(True, f"S2: nabidka roztazeni pro polici pri nizkych stojkach: {nab.get('hpolice')}")

# ---------------------------------------------------------------------------------------------------------------------
print("S3) vstup, hash, dotaz")
for kw, popis in ((dict(hpolice_sklon=4.9), "sklon pod 5"), (dict(hpolice_sklon=30.1), "sklon nad 30"), (dict(hpolice_sklon=True), "sklon bool"), (dict(hpolice_sklon="15"), "sklon text"),
                  (dict(hpolice_sklon=float("nan")), "sklon NaN"), (dict(hpolice_sklon=None), "sklon None")):
    try:
        sestav(hpolice=True, hpolice_typ="sikma", **kw)
        dobre = False
    except S.StulChyba as e:
        dobre = getattr(e, "kod", "mimo_rozsah") == "mimo_rozsah"
    check(dobre, f"S3: neplatny sklon ({popis}) = StulChyba mimo_rozsah")
for system in (30, 40):
    zakl = sestav(system=system)
    h0 = G.kanonicky_hash(zakl["parametry"])
    hs = {}
    for sk in SKLONY:
        rr = sestav(system=system, hpolice=True, hpolice_typ="sikma", hpolice_sklon=sk)
        hs[sk] = G.kanonicky_hash(rr["parametry"])
    check(len(set(hs.values())) == 3 and h0 not in hs.values(), f"S3 s{system}: kazdy sklon sikme police ma jiny hash a jiny nez stul bez police ({hs})")
    r1 = sestav(system=system, hpolice=True, hpolice_typ="rovna", hpolice_sklon=30.0)
    r2 = sestav(system=system, hpolice=True, hpolice_typ="rovna", hpolice_sklon=5.0)
    r3 = sestav(system=system, hpolice=True, hpolice_typ="rovna")
    check(G.kanonicky_hash(r1["parametry"]) == G.kanonicky_hash(r2["parametry"]) == G.kanonicky_hash(r3["parametry"]) and r1["parametry"]["hpolice_sklon"] == 15.0, f"S3 s{system}: sklon se mimo sikmou polici do hashe nepocita a je kanonicky 15 ({r1['parametry']['hpolice_sklon']})")
    for typ_h in ("rovna", "ram", "drazka", "lem", "prepazky"):                  # u jineho typu nez sikma klic `hpolice_sklon` v kanonickem otisku vubec neni (hashe polic v1 beze zmeny)
        pp_h = dict(sestav(system=system, hpolice=True, hpolice_typ=typ_h)["parametry"])
        check("hpolice_sklon" in pp_h and "hpolice_sklon" not in HP.kanon_hash(dict(pp_h)), f"S3 s{system} {typ_h}: klic hpolice_sklon se z kanonickeho otisku vyhodi (do hashe nevstupuje)")
    pp_s = dict(sestav(system=system, hpolice=True, hpolice_typ="sikma", hpolice_sklon=25.0)["parametry"])
    check(HP.kanon_hash(dict(pp_s)).get("hpolice_sklon") == 25.0, f"S3 s{system} sikma: klic hpolice_sklon zustava v kanonickem otisku (vstupuje do hashe)")
    r4 = sestav(system=system, hpolice=False, hpolice_typ="sikma", hpolice_sklon=25.0)
    check(G.kanonicky_hash(r4["parametry"]) == h0 and "hpolice_sklon" not in S.parametry_z_dotazu({}), f"S3 s{system}: vypnuta police + sklon = stul beze zmeny")
q = S.parametry_z_dotazu({"hpolice": "1", "hpolice_typ": "sikma", "hpolice_sklon": "20"})
check(q.get("hpolice_sklon") == 20.0 and q.get("hpolice_typ") == "sikma", f"S3: dotaz ?hpolice_sklon=20 ({ {k: v for k, v in q.items() if k.startswith('hpolice')} })")
rs = sestav(system=41, hpolice_sklon=25.0, hpolice_typ="sikma")
check(rs["parametry"].get("hpolice_typ") == "rovna" and rs["parametry"].get("hpolice_sklon") == 15.0 and G.kanonicky_hash(rs["parametry"]) == G.kanonicky_hash(sestav(system=41)["parametry"]), "S3: SSE ignoruje klice police vcetne sklonu (stejny hash)")

# ---------------------------------------------------------------------------------------------------------------------
print("S4) cena, vyroba, GLB")
for system, sklon in itertools.product((30, 35, 40, 45), (5.0, 15.0, 30.0)):
    nazev = f"S4 s{system} sklon {sklon:g}"
    r = sestav(system=system, sirka=1500, hpolice=True, hpolice_typ="sikma", hpolice_sklon=sklon, police=1)
    r0 = sestav(system=system, sirka=1500, police=1)
    if not r["parametry"]["hpolice"]:
        check(False, f"{nazev}: nevesla se")
        continue
    ent = S.entries_pro_cenu(r["dily"])
    n_konz = sum(1 for e in ent if e["part_id"] == KONZ_PART[system])
    n_konz0 = sum(1 for e in S.entries_pro_cenu(r0["dily"]) if e["part_id"] == KONZ_PART[system])
    check(n_konz - n_konz0 == 2, f"{nazev}: v polozkach ceny 2 konzoly {KONZ_PART[system]} ({n_konz - n_konz0})")
    n_uh = len(hpol(r, "uhel"))
    jc = sum(e.get("joint_count", 0) for e in ent) - sum(e.get("joint_count", 0) for e in S.entries_pro_cenu(r0["dily"]))
    n_pr = 2 * (len(hpol(r, "bok")) + len(hpol(r, "mezi")))
    check(jc == n_pr + 2, f"{nazev}: spoje profilu v cene: {n_pr} (boky / mezilisty x pricky) + 2 (konzola = spoj stojka - bok) = {n_pr + 2} (je {jc})")
    sm = S.spojovaci_material([d for d in r["dily"] if d["part_id"] == KONZ_PART[system]], {})
    sku_ocek = {"product_3323": ("2.1.21.0612", "2.1.001.08.06"), "product_3324": ("2.1.21.0616", "2.1.001.10.06")}[KONZ_PART[system]]
    check({x["sku"]: x["mnozstvi"] for x in sm} == {sku_ocek[0]: 8, sku_ocek[1]: 8}, f"{nazev}: spojovaci material ke 2 konzolam: 8 sroubu + 8 matic ({[(x['sku'], x['mnozstvi']) for x in sm]})")
    sm_u = S.spojovaci_material([d for d in r["dily"] if d["part_id"] == UHELNIK[system]], {})
    check(sum(x["mnozstvi"] for x in sm_u) == 2 * n_uh and n_uh > 0, f"{nazev}: spojovaci material k {n_uh} uhelnikum lemu = {2 * n_uh} ks ({[(x['sku'], x['mnozstvi']) for x in sm_u]})")
    vv = S.vyrobni_vypis(r, {})
    kroky = {m["krok"]: m for m in vv["montazni_postup"]}
    kz_idx = {i for i, k, d in hpol(r, "konz")}
    uh_idx = {i for i, k, d in hpol(r, "uhel")}
    check(kz_idx | uh_idx <= set(kroky[7]["dily"]), f"{nazev}: konzoly a uhelniky police jsou v kroku 7 ({sorted((kz_idx | uh_idx) - set(kroky[7]['dily']))})")
    prof_i = {i for i, k, d in hpol(r) if k[2] in ("zad", "pred", "bok", "mezi")}
    check(prof_i <= set(kroky[1]["dily"]), f"{nazev}: profily police jsou v kroku 1 ({sorted(prof_i - set(kroky[1]['dily']))})")
    vsechny_h = {i for i, k, d in hpol(r)}
    cizi_kroky = {n_: sorted(vsechny_h & set(m_["dily"])) for n_, m_ in kroky.items() if n_ not in (1, 7) and vsechny_h & set(m_["dily"])}
    check(vsechny_h <= set(kroky[7]["dily"]) and not cizi_kroky, f"{nazev}: VSECHNY dily police (profily, deska, lem, uhelniky, konzoly) jsou v montaznim kroku 7 a v zadnem jinem (chybi v 7: {sorted(vsechny_h - set(kroky[7]['dily']))}, jinde: {cizi_kroky})")
    check("horní police" in kroky[7]["text"].lower(), f"{nazev}: krok 7 zmiňuje horní polici")
    pris = [x for x in vv["prislusenstvi"] if x["karta_id"] == int(KONZ_PART[system].split("_")[1])]
    check(len(pris) == 1 and pris[0]["pocet"] == 2, f"{nazev}: vyrobni vypis: 2 konzoly v prislusenstvi ({[(x['karta_id'], x['pocet']) for x in pris]})")
    desk_v = [x for x in vv["desky"] if x.get("deska_id", "").startswith("hpol")]
    for x in desk_v:                                                 # rozmery desek ve vypisu z meritka (skutecne rozmery desky), ne z obalky naklonene desky
        d_ = r["dily"][x["id_dilu"][0]]
        check(abs(x["tloustka_mm"] - tl_dilu(d_["part_id"])) < 0.01 and abs(x["sirka_mm"] - 1000.0 * d_["scale"][1]) < 0.06 and abs(x["hloubka_mm"] - 1000.0 * d_["scale"][0]) < 0.06,
              f"{nazev}: rozmery desky '{x['role']}' ve vypisu {x['sirka_mm']} x {x['hloubka_mm']} z meritka")
    popisy = [S.role_dilu(k)[1] for _, k, _ in hpol(r, "konz")]
    check(all("naklápěcí konzola horní police" in p_ for p_ in popisy) and popisy[0] != popisy[1], f"{nazev}: role konzol ve vypisu ({popisy})")
    glb = G.poskladej_glb(r["dily"])
    check(glb[:4] == b"glTF" and len(glb) > 10000, f"{nazev}: GLB se poskladalo ({len(glb)} B)")
    check(S._NAZVY.get(KONZ_PART[system]) in ("úhlová naklápěcí konzola (drážka 8)", "úhlová naklápěcí konzola (drážka 10)"), f"{nazev}: nazev konzoly v kusovniku ({S._NAZVY.get(KONZ_PART[system])})")


# ---------------------------------------------------------------------------------------------------------------------
print("S5) 3D menu a preklady")
for system in (30, 40):
    r = sestav(system=system, hpolice=True, hpolice_typ="sikma", hpolice_sklon=15.0)
    ov = S.ovladani_3d(r)
    cast = next((c for c in ov["casti"] if c["id"] == "hpolice"), None)
    check(cast is not None, f"S5 s{system}: cast 'hpolice' ve 3D ovladani")
    if not cast:
        continue
    texty = {m["text"]: m for m in cast["menu"]}
    check("Sklon police o 5° větší" in texty and "Sklon police o 5° menší" in texty and "Police: šikmá na boxy" not in texty, f"S5 s{system}: u sikme police polozky sklonu, typ sikma se nenabizi ({list(texty)[:4]})")
    for t_txt, nov in (("Sklon police o 5° větší", 20.0), ("Sklon police o 5° menší", 10.0)):
        m = texty[t_txt]
        check(m["nastav"] == {"hpolice_sklon": nov} and not m.get("zakazano"), f"S5 s{system}: '{t_txt}' nastavi sklon {nov:g} ({m['nastav']})")
        r2 = sestav(**dict(r["parametry"], **m["nastav"]))
        check(r2["parametry"]["hpolice_sklon"] == nov and r2["parametry"]["hpolice"] and not r2["problemy"], f"S5 s{system}: po '{t_txt}' je sklon {nov:g} a police bez problemu")
    r30 = sestav(system=system, hpolice=True, hpolice_typ="sikma", hpolice_sklon=30.0)
    r5 = sestav(system=system, hpolice=True, hpolice_typ="sikma", hpolice_sklon=5.0)
    for rr, txt in ((r30, "Sklon police o 5° větší"), (r5, "Sklon police o 5° menší")):
        m = {x["text"]: x for x in next(c for c in S.ovladani_3d(rr)["casti"] if c["id"] == "hpolice")["menu"]}[txt]
        check(m.get("zakazano") and m.get("duvod"), f"S5 s{system}: '{txt}' je na mezi zakazano s duvodem")
    for lang in ("cs", "en", "sk"):
        try:
            out = OV.ovladani_verejne(ov, lang, profil_mm(system))
            c = next(c for c in out["casti"] if c["id"] == "upshelf")
            nast = [m["nastav"] for m in c["menu"] if m.get("nastav")]
            check(any("upshelftilt" in n for n in nast) and all(set(n) <= {"upshelf", "upshelftype", "upshelfboard", "upshelfpos", "upshelfdepth", "upshelftilt"} for n in nast), f"S5 s{system} ({lang}): verejne nastaveni sklonu ({nast[-2:]})")
            check(all(m["text"] and "{" not in m["text"] for m in c["menu"]), f"S5 s{system} ({lang}): texty menu prelozeny")
        except OV.ChybiPreklad as e:
            check(False, f"S5 s{system} ({lang}): chybi preklad: {e}")
# prepnuti typu na sikmou: u dvou useku zakazano s duvodem o stredni noze
r = sestav(system=30, sirka=2100, stredni_opora="noha", panely=False, elektrozlab=False, hpolice=True, hpolice_typ="rovna")
m = {x["text"]: x for x in next(c for c in S.ovladani_3d(r)["casti"] if c["id"] == "hpolice")["menu"]}["Police: šikmá na boxy"]
check(m.get("zakazano") and "střední zadní nohou" in (m.get("duvod") or ""), f"S5: u stolu se strednimi zadnimi nohami je prepnuti na sikmou zakazano s duvodem ({m.get('duvod')})")
r = sestav(system=30, hpolice=True, hpolice_typ="rovna")
m = {x["text"]: x for x in next(c for c in S.ovladani_3d(r)["casti"] if c["id"] == "hpolice")["menu"]}["Police: šikmá na boxy"]
r2 = sestav(**dict(r["parametry"], **m["nastav"]))
check(not m.get("zakazano") and r2["parametry"]["hpolice_typ"] == "sikma" and r2["parametry"]["hpolice"] and not r2["problemy"], "S5: z rovne police jde prepnout na sikmou")

print("S6) presna kontrola kolizi (stul_hpolice.zkontroluj): citlivost a zapojeni do generatoru")
r = sestav(system=30, hpolice=True, hpolice_typ="sikma", panely=False, elektrozlab=False)
klice = kl(r)
clenove_s6, spojky_s6 = {}, {}
for i, k in enumerate(klice):
    if isinstance(k, tuple) and k and k[0] == "hpol":
        clenove_s6[k] = {"hp_skup": True} if k[2] == "konz" else {"hp_rot": True}
    if isinstance(k, tuple) and len(k) == 3 and k[0] == "zasl":
        clenove_s6[k] = {}
for j, d_ in enumerate(r["dily"]):
    for i2 in (d_.get("lic_peers") or []):
        if r["dily"][i2]["part_id"] in S.SPOJKY_PARTS and klice[j] in clenove_s6:
            spojky_s6.setdefault(klice[i2], {"vlastnici": []})["vlastnici"].append(klice[j])
for k_ in spojky_s6:
    spojky_s6[k_]["vlastnici"] = tuple(spojky_s6[k_]["vlastnici"])
idx_s6 = {k: i for i, k in enumerate(klice)}
bb_s6 = [bb(d) for d in r["dily"]]
check(HP.zkontroluj(r["hpolice_info"], r["dily"], bb_s6, idx_s6, clenove_s6, spojky_s6) == [], "S6: sikma police bez cizich dilu = zadny problem presne kontroly")
sk_c = np.mean([obb(d)[0] for _, _, d in hpol(r)], axis=0)
lo_pan, hi_pan = S.glb_bbox("product_4931")
for popis, posun, ocek_problem in (("panel uprostred police", np.zeros(3), True), ("panel 2 m od police", np.array([0.0, 0.0, 2000.0]), False), ("panel pri kraji desky (dotyk)", None, None)):
    if posun is None:
        continue
    dum = {"part_id": "product_4931", "position": (sk_c - (np.array(lo_pan) + np.array(hi_pan)) / 2.0 + posun).tolist(), "quaternion": [0.0, 0.0, 0.0, 1.0], "scale": [1.0, 1.0, 1.0]}
    dily2 = list(r["dily"]) + [dum]
    bb2 = bb_s6 + [bb(dum)]
    idx2 = dict(idx_s6)
    idx2[("dum", 0)] = len(dily2) - 1
    pr = HP.zkontroluj(r["hpolice_info"], dily2, bb2, idx2, clenove_s6, spojky_s6)
    check(bool(pr) == ocek_problem and (not pr or (pr[0]["kod"] == "hpolice_nevejde" and len(dily2) - 1 in pr[0]["dily"] and "narazila" in pr[0]["text"])), f"S6: {popis}: presna kontrola {'hlasi' if ocek_problem else 'nehlasi'} kolizi ({[(x['kod'], x['text'][:60]) for x in pr]})")
orig_zk = HP.zkontroluj
HP.zkontroluj = lambda *a_, **k_: [{"kod": "hpolice_nevejde", "dily": [], "text": "test: presna kontrola hlasi kolizi"}]
try:
    r_m = sestav(system=30, hpolice=True, hpolice_typ="sikma", panely=False, elektrozlab=False)
finally:
    HP.zkontroluj = orig_zk
check(not r_m["parametry"]["hpolice"] and "hpolice" in [o["volba"] for o in r_m["odebrano"]], f"S6: problem z presne kontroly generator zpracuje (police se odebere) ({r_m['parametry']['hpolice']}, {[o['volba'] for o in r_m['odebrano']]})")

print("S7) vzpery ramen LED: sikma police se vzperami (vzpera se prizpusobi, nic se nezanori)")
n_vz = 0
for system, sklon, panely, rel in itertools.product((30, 35, 40, 45), SKLONY, (0, 1), (0.0, 0.5, 1.0)):
    cfg = dict(system=system, sirka=1280, hpolice=True, hpolice_typ="sikma", hpolice_sklon=sklon, led=True, vzpery=True, panely=bool(panely), elektrozlab=bool(panely), police=1)
    v = sestav(**cfg)["hpolice_info"]
    if not v:
        continue
    hv = round(v["vyska"]["min"] + rel * (v["vyska"]["max"] - v["vyska"]["min"]), 1)
    r = sestav(**dict(cfg, hpolice_vyska=hv))
    nazev = f"S7 s{system} sklon {sklon:g} pan{panely} vyska {hv:g} ({rel:g})"
    check(r["parametry"]["hpolice"] and not r["problemy"] and not r["odebrano"], f"{nazev}: police se vzperami bez problemu a bez odebrani ({r['parametry']['hpolice']}, {[(x['kod'], x['text'][:80]) for x in r['problemy']]}, {[o['volba'] for o in r['odebrano']]})")
    klice = kl(r)
    vz_prof = [(i, k) for i, k in enumerate(klice) if isinstance(k, tuple) and k[0] == "vz" and k[2] == "prof"]
    check(len(vz_prof) == 2 and r["parametry"]["vzpery"], f"{nazev}: obe vzpery existuji ({len(vz_prof)})")
    skup_h = [i for i, k in enumerate(klice) if isinstance(k, tuple) and k and k[0] == "hpol"]
    vz_vse = [i for i, k in enumerate(klice) if isinstance(k, tuple) and k and k[0] == "vz"]
    nejhorsi = min((sat(*obb(r["dily"][i]), *obb(r["dily"][j])) for i in vz_vse for j in skup_h), default=1e9)
    check(nejhorsi >= -S.TOL_PRUNIK_MM - 1e-6, f"{nazev}: vzpery (profil i spojky) se nezanori do dilu police (nejhorsi oddeleni {nejhorsi:.2f} mm)")
    n_vz += 1
check(n_vz >= 40, f"S7: otestovano dost konfigurací se vzperami ({n_vz})")

if FAILS:
    import re
    kat = {}
    for f_ in FAILS:
        klic = re.sub(r"[0-9.\-]+", "#", f_.split(": ", 1)[1] if ": " in f_ else f_)[:110]
        kat.setdefault(klic, [0, f_])[0] += 1
    print("\nSOUHRN CHYB (typ: pocet, priklad):")
    for k_, (n_, ex) in sorted(kat.items(), key=lambda t: -t[1][0])[:25]:
        print(f"  {n_:5d} x  {ex[:230]}")
print(f"\n{OK} kontrol OK" if not FAILS else f"\n{len(FAILS)} CHYB, {OK} kontrol OK")
sys.exit(1 if FAILS else 0)
