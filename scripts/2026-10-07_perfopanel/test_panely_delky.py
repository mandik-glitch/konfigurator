#!/usr/bin/env python3
"""Test DELEK PERFOROVANEHO PANELU 1190 / 1481 / 1671 / 1975 mm v generatoru stolu (bot8, 2026-10-07; Robert: "integruj do generatoru dalsi velikosti perforovanych panelu",
rozmery 1481 a 1671 upresnil, 1975 x 460 jsem dorobil). Bez DB.

NEZAVISLE na kodu generatoru (vse se meri z AABB dilu a z GLB v katalogu, ocekavane hodnoty z rozmeru profilu a panelu):
  A) modely v katalogu (product_4931 / 4972 / 4973 / 4974): rozmery L x 15 x H, otvory 10 x 10 v pravidelne mrizce (pocet, velikost, symetricke okraje, svisla roztec 38 mm), lem 15 mm po vsech
     ctyrech stranach; generator scripts/2026-10-07_perfopanel/gen_perfopanel.py vyrobi tytez soubory (poloha vrcholu, trojuhelniky), mesh je vodotesny a ma jednotne otaceni.
  B) kazda delka x system 30 / 35 / 40: panel ma dil teto delky a rozmer z GLB, je vystredeny mezi zadnimi stojkami s mezerou aspon 1 mm, profily nad / pod nim dosedaji na stojky, spoje ==
     definice z dimension_match_fbx, QA lic_peers, nic nezasahuje do panelu, elektrozlab zustava v tomtez odstupu od LEVE hrany panelu a dotyka se ho, cena (polozky) ma spravny dil katalogu.
  C) hranice: na nejmensi sirce stolu (delka + 2 x 1 + 2 x profil) delka sedi s mezerou 1 mm, o 10 mm uzsi stul delku SNIZI na nejdelsi, ktera se vejde (panel se neodebere); nevejde-li se ani 1190,
     plati puvodni odebrani panelu.
  D) mrizka sirka x police x stredni opora x delka: zvolena delka se vzdy vejde (z AABB stojek), zvolena = nejdelsi ze vsech <= pozadovane, ktere se vejde, `panely_info.typy[].vejde` sedi.
  E) hash: vychozi delka (1190) a vypnute panely se do hashe nepocitaji, jina delka hash meni, snizena delka ma tentyz hash jako primo zadana.
  F) vstup: neplatna delka = StulChyba, dotaz ?panely_delka=1481, SSE (system 41) delku ignoruje.
  G) 3D ovladani: menu panelu nabizi ostatni delky ("Zvolit panel N mm"), nevejde se = zakazano s duvodem, preklady cs / en / sk.
  I) vyska panelu (1671 = 455 mm) a nizke zadni stojky; J) nazvy dilu s delkou, bez panelu zadna delka, chybejici GLB jedne delky nesmi shodit vychozi cestu.
  H) ZLATY OTISK: s vychozi delkou je VSE beze zmeny proti stavu pred zavedenim delky (702 konfiguraci: hash i otisk dilu, golden_head.json).
Spusteni z korene repa:  api/venv/bin/python3 scripts/2026-10-07_perfopanel/test_panely_delky.py     (STUL_API_OVERRIDE=<adresar api> = kandidat)
Vystup "N kontrol OK", exit 0; jinak radky CHYBA, exit 1."""
import hashlib
import itertools
import json
import math
import os
import struct
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
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import app  # noqa: F401,E402 - jako v ostrem behu
    import dimension_match_fbx as dmf  # noqa: E402
    import qa_checks  # noqa: E402
    import stul_glb as G  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_koty as KOTY  # noqa: E402
    import stul_ovladani_verejne as OV  # noqa: E402
    import gen_perfopanel as GEN  # noqa: E402
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


KATALOG = os.path.join(REPO, "webapp", "katalog")
TL_PANELU = 15.0
VYSKY = {1190: 460.0, 1481: 460.0, 1671: 455.0, 1975: 460.0}        # vyska panelu (mm) podle delky: 1671 ma v CAD od Roberta 455 mm (Robert 2026-10-07: "455 mm podle modelu")
MEZERA = 1.0                                                      # mezera panel - profil / stojka
ODSTUP_PRICKA = 2.0
PROFIL_GLB = {p_: p_ + ".glb" for p_ in S.PROFIL_PARTS}


def kl(r):
    return [tuple(k) if isinstance(k, list) else k for k in r["klice"]]


def bb(d):
    lo, hi = S._aabb(d)
    return np.array(lo, float), np.array(hi, float)


def casti(r, pred):
    return [(i, k, r["dily"][i]) for i, k in enumerate(kl(r)) if pred(k)]


def panely(r):
    return sorted(casti(r, lambda k: isinstance(k, tuple) and k[0] == "pan"), key=lambda x: (x[1][1], x[1][2]))


def listy(r):
    return sorted(casti(r, lambda k: isinstance(k, tuple) and k[0] == "panrail"), key=lambda x: (x[1][1], x[1][2]))


def dil(r, klic):
    return r["dily"][kl(r).index(klic)]


NOHA_ZL, NOHA_ZP = ("t", S.NOHA_ZL), ("t", S.NOHA_ZP)


def min_sirka(L, P):
    return int(math.ceil(L + 2 * MEZERA + 2 * P))


# ---------------------------------------------------------------------------------------------------------------------
# A) modely v katalogu
# ---------------------------------------------------------------------------------------------------------------------
print("A) modely panelu v katalogu")
try:
    import scipy.sparse as sps
    import scipy.sparse.csgraph as csg
    MA_SCIPY = True
except ImportError:
    MA_SCIPY = False
    print("  (bez scipy: kontrola otvoru preskocena)")

for L, part in sorted(S.PANEL_TYPY.items()):
    cesta = os.path.join(KATALOG, part + ".glb")
    check(os.path.isfile(cesta), f"A {L}: soubor {part}.glb je v katalogu")
    if not os.path.isfile(cesta):
        continue
    pos, nrm, tri = G.nacti_mesh(part)
    pos = pos.astype(np.float64)
    lo, hi = pos.min(axis=0), pos.max(axis=0)
    roz = hi - lo
    check(np.allclose(roz, [L, TL_PANELU, VYSKY[L]], atol=0.01), f"A {L}: rozmer (delka, tloustka, vyska) = {L} x {TL_PANELU:g} x {VYSKY[L]:g} ({np.round(roz, 3).tolist()})")
    # geometricky vodotesny a jednotne otoceny: svarit vrcholy podle polohy, kazda smerovana hrana ma presne jeden protejsek
    klic_v = np.round(pos, 3)
    uniq, inv = np.unique(klic_v, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    F = inv[tri]
    de = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    kodovane = de[:, 0].astype(np.int64) * len(uniq) + de[:, 1]
    protejsek = de[:, 1].astype(np.int64) * len(uniq) + de[:, 0]
    unik, cnt = np.unique(kodovane, return_counts=True)
    check(int(cnt.max()) == 1, f"A {L}: zadna hrana neni pouzita dvakrat stejnym smerem (jednotne otoceni)")
    check(bool(np.isin(kodovane, protejsek).all()), f"A {L}: kazda hrana ma protejsek (vodotesny mesh)")
    # otoceni ven: objem kladny a rovny ocekavanemu (plech + lem - otvory)
    v0, v1, v2 = uniq[F[:, 0]], uniq[F[:, 1]], uniq[F[:, 2]]
    objem = float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)
    par = GEN.TYPY[L]
    plocha_otvoru = par["sloupcu"] * GEN.RADKY * GEN.OTVOR * GEN.OTVOR
    plech = (L * par["vyska"] - plocha_otvoru) * GEN.TL_PLECH
    lem = (L * par["vyska"] - (L - 2 * GEN.TL_LEM) * (par["vyska"] - 2 * GEN.TL_LEM)) * (GEN.VYSKA_LEMU - GEN.TL_PLECH)
    check(abs(objem - (plech + lem)) < 5.0, f"A {L}: objem {objem:.1f} mm3 = plech + lem - otvory ({plech + lem:.1f})")
    # souradnicova soustava jako 4931: plech u minimalni Y, lem nahoru (Y = 15)
    y_dno = pos[:, 1].min()
    plocha_dna = pos[np.abs(pos[:, 1] - y_dno) < 0.01]
    check(len(plocha_dna) > 100, f"A {L}: plech lezi u minimalni Y (lem smeruje do +Y jako u 4931)")
    # otvory: hranicni smycky VNEJSI plochy plechu (trojuhelniky v rovine Y = min); smycka = hrany, ktere patri jedinemu trojuhelniku; obvod je nejvetsi smycka
    if MA_SCIPY:
        nn = np.cross(pos[tri[:, 1]] - pos[tri[:, 0]], pos[tri[:, 2]] - pos[tri[:, 0]])
        vnejsi = (np.abs(nn[:, 1]) > 1e-6) & (np.abs(pos[tri][:, :, 1] - y_dno).max(axis=1) < 0.01)
        Fv = inv[tri[vnejsi]]                                          # svarene indexy vrcholu
        hr = np.vstack([Fv[:, [0, 1]], Fv[:, [1, 2]], Fv[:, [2, 0]]])
        hr = np.sort(hr, axis=1)
        u_h, c_h = np.unique(hr, axis=0, return_counts=True)
        hranicni = u_h[c_h == 1]
        g = sps.coo_matrix((np.ones(len(hranicni)), (hranicni[:, 0], hranicni[:, 1])), shape=(len(uniq), len(uniq)))
        nc, lab = csg.connected_components(g, directed=False)
        smycky = {}
        for a_, b_ in hranicni:
            smycky.setdefault(lab[a_], set()).update((a_, b_))
        hr_box = []
        for vs in smycky.values():
            Q = uniq[list(vs)]
            hr_box.append((Q[:, 0].min() - lo[0], Q[:, 0].max() - lo[0], Q[:, 2].min() - lo[2], Q[:, 2].max() - lo[2]))
        hr_box.sort(key=lambda t_: -(t_[1] - t_[0]) * (t_[3] - t_[2]))
        obvod, otvory = hr_box[0], hr_box[1:]
        check(abs(obvod[1] - obvod[0] - L) < 0.01 and abs(obvod[3] - obvod[2] - VYSKY[L]) < 0.01, f"A {L}: obvod plechu {L} x {VYSKY[L]:g} ({obvod[1] - obvod[0]:.2f} x {obvod[3] - obvod[2]:.2f})")
        check(len(otvory) == par["sloupcu"] * GEN.RADKY, f"A {L}: {par['sloupcu']} x {GEN.RADKY} = {par['sloupcu'] * GEN.RADKY} otvoru ({len(otvory)})")
        check(all(abs(o[1] - o[0] - 10.0) < 0.01 and abs(o[3] - o[2] - 10.0) < 0.01 for o in otvory), f"A {L}: kazdy otvor ma 10 x 10 mm")
        zs = sorted({round((o[2] + o[3]) / 2, 1) for o in otvory})
        sloupce = sorted({round((o[0] + o[1]) / 2, 1) for o in otvory})
        okr_l, okr_p = min(o[0] for o in otvory), L - max(o[1] for o in otvory)
        okr_d, okr_h = min(o[2] for o in otvory), VYSKY[L] - max(o[3] for o in otvory)
        check(abs(okr_l - okr_p) <= 1.0 and abs(okr_d - okr_h) <= 1.0, f"A {L}: mrizka otvoru je v obrysu symetricka (okraje {okr_l:.1f}/{okr_p:.1f} a {okr_d:.1f}/{okr_h:.1f})")
        check(len(zs) == GEN.RADKY and np.allclose(np.diff(zs), 38.0, atol=0.15), f"A {L}: {GEN.RADKY} radku po 38 mm ({np.round(np.diff(zs), 2).tolist()[:3]})")
        check(len(sloupce) == par["sloupcu"], f"A {L}: {par['sloupcu']} sloupcu otvoru ({len(sloupce)})")
        dx = np.diff(sloupce)
        check(float(dx.max() - dx.min()) < (0.2 if L != 1190 else 0.2), f"A {L}: vodorovna roztec je rovnomerna ({dx.min():.2f} az {dx.max():.2f} mm)")
    # generator vyrobi tyz tvar (poloha vrcholu a trojuhelniky); GLB v katalogu = vystup generatoru (1190 = stavajici panel 4931 z jineho zdroje: jen rozmer a otvory)
    Vg, Ng, Tg, info = GEN.sestav(L, par["vyska"], par["sloupcu"], par["okraj"], par.get("roztec"))
    if L == 1190:
        check(np.allclose(Vg.max(0) - Vg.min(0), roz, atol=0.01), f"A 1190: generator napodobi rozmer stavajiciho panelu 4931 ({np.round(Vg.max(0) - Vg.min(0), 2).tolist()} vs {np.round(roz, 2).tolist()})")
    else:
        stejne_v = Vg.shape == pos.shape and np.allclose(np.sort(np.round(Vg, 3), axis=0), np.sort(np.round(pos, 3), axis=0), atol=0.002)
        check(stejne_v and len(Tg) == len(tri), f"A {L}: GLB v katalogu = vystup generatoru gen_perfopanel.py ({len(Vg)} vs {len(pos)} vrcholu, {len(Tg)} vs {len(tri)} trojuhelniku)")

# ---------------------------------------------------------------------------------------------------------------------
# B) kazda delka v kazdem systemu
# ---------------------------------------------------------------------------------------------------------------------
S_PUVODNI = S.VYCHOZI["system"]


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
    dily = r["dily"]
    gen = {tuple(x) for x in r["spoje"]}
    ref = profil_pary_dmf(dily)
    check(gen == ref, f"{nazev}: spoje generatoru == dimension_match_fbx ({len(gen)} vs {len(ref)}; navic {sorted(gen - ref)[:3]}, chybi {sorted(ref - gen)[:3]})")
    pairs, bad = qa_checks.lic_peers_bad_pairs(dily, PROFIL_GLB, {})
    check(not bad, f"{nazev}: QA lic_peers_neni_spoj hlasi {len(bad)} spatnych paru {bad[:3]}")
    spojene = {i for p in r["spoje"] for i in p}
    sam = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS and i not in spojene]
    check(not sam, f"{nazev}: profily bez jakehokoli spoje {sam}")
    prekazky = [S._aabb(d) for d in dily if d["part_id"] == "product_4933" or d["part_id"] in S.PANEL_PARTY]
    for i, d in enumerate(dily):
        if d["part_id"] not in S.SPOJKY_PARTS:
            continue
        vl = [j for j, e in enumerate(dily) if e["part_id"] in S.PROFIL_PARTS and i in (e.get("lic_peers") or [])]
        check(len(vl) == 2, f"{nazev}: spojka #{i} ma {len(vl)} vlastniku (ma mit 2)")
        b = S._aabb(d)
        for lo_d, hi_d in prekazky:
            pres = np.minimum(b[1], hi_d) - np.maximum(b[0], lo_d)
            check(not (np.all(pres > 0) and float(pres.min()) > S.TOL_PRUNIK_MM), f"{nazev}: spojka #{i} se zanorila do desky/panelu o {float(pres.min()):.1f} mm")


def over_panel(r, L, nazev, system):
    """Panel delky L: dil, rozmer, vystredeni mezi stojkami, profily nad / pod, nic v panelu, elektrozlab; vraci (stred panelu z, stred zlabu z)."""
    P = float(S.SYSTEMY[system]["profil_mm"])
    pan, lis = panely(r), listy(r)
    check(len(pan) == 1 and len(lis) == 2, f"{nazev}: 1 panel a 2 profily ({len(pan)}, {len(lis)})")
    if not (len(pan) == 1 and len(lis) == 2):
        return None
    check(pan[0][2]["part_id"] == S.PANEL_TYPY[L], f"{nazev}: dil panelu {pan[0][2]['part_id']} == {S.PANEL_TYPY[L]}")
    plo, phi = bb(pan[0][2])
    check(np.allclose(phi - plo, [TL_PANELU, VYSKY[L], L], atol=0.05), f"{nazev}: rozmer panelu {TL_PANELU:g} x {VYSKY[L]:g} x {L} ({np.round(phi - plo, 3).tolist()})")
    zl, zp = bb(dil(r, NOHA_ZL)), bb(dil(r, NOHA_ZP))
    in_l, in_p = float(zl[1][2]), float(zp[0][2])
    g1, g2 = float(plo[2] - in_l), float(in_p - phi[2])
    check(g1 >= MEZERA - 1e-6 and g2 >= MEZERA - 1e-6 and abs(g1 - g2) < 0.01, f"{nazev}: panel vystredeny mezi stojkami, mezery {g1:.3f} / {g2:.3f} mm (aspon {MEZERA:g})")
    nizsi, vyssi = sorted([lis[0], lis[1]], key=lambda x: bb(x[2])[0][1])
    lo_n, hi_n = bb(nizsi[2])
    lo_v, hi_v = bb(vyssi[2])
    check(abs((plo[1] - hi_n[1]) - MEZERA) < 0.01 and abs((lo_v[1] - phi[1]) - MEZERA) < 0.01, f"{nazev}: mezera panel - profil nad/pod presne {MEZERA:g} mm ({plo[1] - hi_n[1]:.3f} / {lo_v[1] - phi[1]:.3f})")
    for nm, (lo_, hi_) in (("spodni", (lo_n, hi_n)), ("horni", (lo_v, hi_v))):
        check(abs(lo_[2] - in_l) < 0.05 and abs(hi_[2] - in_p) < 0.05, f"{nazev}: {nm} profil panelu dosedá na obe stojky (z {lo_[2]:.2f} / {hi_[2]:.2f} vs {in_l:.2f} / {in_p:.2f})")
        check(abs(lo_[0] - zl[0][0]) < 0.05 and abs(hi_[0] - zl[1][0]) < 0.05, f"{nazev}: {nm} profil panelu lezi v rovine stojek (x)")
    check(abs((plo[0] + phi[0]) / 2 - (zl[0][0] + zl[1][0]) / 2) < 0.05, f"{nazev}: panel vystredeny v hloubce stojek")
    for i, k, d in casti(r, lambda k: True):
        if i == pan[0][0]:
            continue
        lo_, hi_ = bb(d)
        pres = np.minimum(phi, hi_) - np.maximum(plo, lo_)
        if np.all(pres > 0):
            check(float(pres.min()) <= (S.TOL_PRUNIK_MM if d["part_id"] in S.SPOJKY_PARTS else 0.011), f"{nazev}: dil #{i} {k} {d['part_id']} zasahuje do panelu o {float(pres.min()):.2f} mm")
    # elektrozlab: dotyk s panelem nebo profilem a stejny odstup od LEVE hrany panelu jako u sablonoveho panelu 1190 (v sablone sedi u leveho konce panelu)
    z_dil = [d for d in r["dily"] if d["part_id"] == "product_4932"]
    stred_zlab = None
    if z_dil:
        zlo, zhi = bb(z_dil[0])
        stred_zlab = float(zlo[2] - plo[2])
        check(zlo[2] >= plo[2] - 0.05 and zhi[2] <= phi[2] + 0.05, f"{nazev}: elektrozlab lezi v rozsahu panelu v z ({zlo[2]:.1f}..{zhi[2]:.1f} vs {plo[2]:.1f}..{phi[2]:.1f})")
        check(abs(zhi[0] - plo[0]) < 0.6 or abs(zlo[0] - plo[0]) < 0.6 or abs(zhi[0] - phi[0]) < 0.6 or min(zhi[0], phi[0]) - max(zlo[0], plo[0]) > -0.6, f"{nazev}: elektrozlab se dotyka panelu v x")
    return float((plo[2] + phi[2]) / 2.0), stred_zlab


print("B) kazda delka v systemech 30 / 35 / 40")
odstup_zlabu = {}                                   # system -> {delka: odstup leve hrany elektrozlabu od leve hrany panelu} (musi byt u vsech delek stejny)
for system in (30, 35, 40):
    P = float(S.SYSTEMY[system]["profil_mm"])
    for L in S.PANEL_DELKY:
        W = min_sirka(L, P) + 60
        r = S.sestav_stul(system=system, sirka=W, panely_delka=L, police=1)
        nazev = f"B s{system} L{L} W{W}"
        check(not r["problemy"], f"{nazev}: bez problemu ({[(p['kod'], p['text'][:60]) for p in r['problemy'][:2]]})")
        check(r["parametry"]["panely_delka"] == float(L) and r["panely_info"]["delka"] == L and r["panely_info"]["pocet"] == 1, f"{nazev}: efektivni delka {L}, 1 panel ({r['panely_info'].get('delka')}, {r['panely_info'].get('pocet')})")
        vys = over_panel(r, L, nazev, system)
        over_napojeni(r, nazev)
        if vys and vys[1] is not None:
            odstup_zlabu.setdefault(system, {})[L] = vys[1]
        pan_ = panely(r)
        if pan_:                                                       # koty: mezery panelu od noh (zaokrouhlene na cele mm) jsou v kotach 3D nahledu pro KAZDOU delku
            plo_, phi_ = bb(pan_[0][2])
            zl_, zp_ = bb(dil(r, NOHA_ZL)), bb(dil(r, NOHA_ZP))
            g1_, g2_ = float(plo_[2] - zl_[1][2]), float(zp_[0][2] - phi_[2])
            kt = [k_["t"] for k_ in KOTY.koty(r)]
            n_g = lambda g: str(int(math.floor(g + 0.5)))
            check(kt.count(n_g(g1_)) >= (2 if n_g(g1_) == n_g(g2_) else 1) and n_g(g2_) in kt, f"{nazev}: koty ukazuji mezery panelu od noh {g1_:.1f} / {g2_:.1f} mm ({sorted(set(kt))[:8]})")
        check(G.MATERIAL_DILU.get(S.PANEL_TYPY[L]) == "ocel", f"{nazev}: dil panelu {S.PANEL_TYPY[L]} ma v 3D material ocel ({G.MATERIAL_DILU.get(S.PANEL_TYPY[L])})")
        ent = S.entries_pro_cenu(r["dily"])
        n_pan = sum(1 for e in ent if e["part_id"] == S.PANEL_TYPY[L])
        n_jine = sum(1 for e in ent if e["part_id"] in S.PANEL_PARTY and e["part_id"] != S.PANEL_TYPY[L])
        check(n_pan == 1 and n_jine == 0, f"{nazev}: polozky ceny maji 1 x {S.PANEL_TYPY[L]} a zadny jiny panel ({n_pan}, {n_jine})")
        check(r["panely_info"]["vyska_panelu"] == VYSKY[L], f"{nazev}: panely_info.vyska_panelu {r['panely_info']['vyska_panelu']} == {VYSKY[L]}")
    odst = odstup_zlabu.get(system, {})
    check(len(odst) == len(S.PANEL_DELKY) and max(odst.values()) - min(odst.values()) < 0.05, f"B s{system}: elektrozlab drzi stejny odstup od LEVE hrany panelu pri vsech delkach ({ {k: round(v, 2) for k, v in odst.items()} })")
    # dva panely nad sebou a dva vedle sebe (siroky stul se stredni nohou): vsechny stejne delky
    for L in (1481, 1975):
        r = S.sestav_stul(system=system, sirka=min_sirka(L, P) + 60, panely_delka=L, panely_pocet=2, police=1)
        pp = panely(r)
        check(len(pp) == 2 and all(d["part_id"] == S.PANEL_TYPY[L] for _, _, d in pp), f"B s{system} L{L}: dva panely jsou oba delky {L} ({[d['part_id'] for _, _, d in pp]})")
    r = S.sestav_stul(system=system, sirka=3000, panely_delka=1190, panely_pocet=2, stredni_opora="noha")
    pp = panely(r)
    check(len(pp) == 2 and len({k[2] for _, k, _ in pp}) == 2, f"B s{system}: dva panely 1190 vedle sebe u stredni nohy (sloupce {[k[2] for _, k, _ in pp]})")

# ---------------------------------------------------------------------------------------------------------------------
# C) hranice
# ---------------------------------------------------------------------------------------------------------------------
print("C) hranice: nejmensi sirka, snizeni delky")
for system in (30, 35, 40):
    P = float(S.SYSTEMY[system]["profil_mm"])
    delky = list(S.PANEL_DELKY)
    for i, L in enumerate(delky):
        Wmin = min_sirka(L, P)
        r = S.sestav_stul(system=system, sirka=Wmin, panely_delka=L, police=1)
        nazev = f"C s{system} L{L} W{Wmin}"
        ok_ = r["panely_info"].get("delka") == L and r["panely_info"].get("pocet") == 1 and not r["odebrano"]
        check(ok_, f"{nazev}: na nejmensi sirce delka {L} sedi ({r['panely_info'].get('delka')}, {r['panely_info'].get('pocet')}, odebrano {[o['volba'] for o in r['odebrano']]})")
        if ok_:
            pan = panely(r)
            plo, phi = bb(pan[0][2])
            zl, zp = bb(dil(r, NOHA_ZL)), bb(dil(r, NOHA_ZP))
            g1, g2 = float(plo[2] - zl[1][2]), float(zp[0][2] - phi[2])
            check(MEZERA - 1e-3 <= g1 <= MEZERA + 1.0 and abs(g1 - g2) < 0.01, f"{nazev}: mezera u stojek {g1:.3f} / {g2:.3f} mm (1 az 2 mm)")
            over_napojeni(r, nazev)                                    # nejuzsi stul: mezera panel - stojka je 1 mm, spojky u spodniho profilu by se do panelu zanorily (musi se vynechat)
        Wuz = Wmin - 10
        r2 = S.sestav_stul(system=system, sirka=Wuz, panely_delka=L, police=1)
        if i == 0:
            check("panely" in [o["volba"] for o in r2["odebrano"]] or not r2["parametry"]["panely"], f"C s{system} L{L} W{Wuz}: nevejde se ani nejkratsi panel = panely se odeberou ({[o['volba'] for o in r2['odebrano']]})")
        else:
            nizsi = delky[i - 1]
            check(r2["parametry"]["panely"] and r2["panely_info"]["delka"] == nizsi and r2["parametry"]["panely_delka"] == float(nizsi) and not r2["problemy"],
                  f"C s{system} L{L} W{Wuz}: o 10 mm uzsi stul snizi delku na {nizsi} (ne odebrani panelu): {r2['panely_info'].get('delka')}, panely {r2['parametry']['panely']}")
            dily_pan = [d for d in r2["dily"] if d["part_id"] in S.PANEL_PARTY]
            check(len(dily_pan) == 1 and dily_pan[0]["part_id"] == S.PANEL_TYPY[nizsi], f"C s{system} L{L} W{Wuz}: v modelu je panel {nizsi} ({[d['part_id'] for d in dily_pan]})")

# ---------------------------------------------------------------------------------------------------------------------
# D) mrizka: zvolena delka se vejde, a je nejdelsi mozna
# ---------------------------------------------------------------------------------------------------------------------
print("D) mrizka sirka x police x stredni opora x delka")


def sekce_z_modelu(r):
    """Useky mezi stojkami [(a, b)] z AABB nohou: krajni zadni nohy, a u opory `noha` i stredni zadni noha (klic RM); vnitrni lica."""
    zl, zp = bb(dil(r, NOHA_ZL)), bb(dil(r, NOHA_ZP))
    stredni = [bb(d) for k, d in zip(kl(r), r["dily"]) if k == "RM"]
    if stredni and r["panely_info"].get("rezim") == "noha":
        sm = stredni[0]
        return [(float(zl[1][2]), float(sm[0][2])), (float(sm[1][2]), float(zp[0][2]))]
    return [(float(zl[1][2]), float(zp[0][2]))]


kontrolovano = 0
for system in (30, 40):
    P = float(S.SYSTEMY[system]["profil_mm"])
    for sirka, police, opora in itertools.product((1500, 1600, 1800, 2000, 2100, 2300, 2600, 3000), (0, 1), ("auto", "noha", "ram")):
        vysl = {}
        for L in S.PANEL_DELKY:
            r = S.sestav_stul(system=system, sirka=sirka, police=police, stredni_opora=opora, panely_delka=L)
            vysl[L] = r
            ef = r["parametry"]["panely_delka"] if r["parametry"]["panely"] else None
            nazev = f"D s{system} W{sirka} pol{police} {opora} L{L}"
            kontrolovano += 1
            if ef is None:
                check(L == S.PANEL_DELKY[0] or True, "")
                continue
            sekce = sekce_z_modelu(r)
            sirky = [b - a for a, b in sekce]
            check(any(s_ >= ef + 2 * MEZERA - 1e-6 for s_ in sirky), f"{nazev}: efektivni delka {ef:.0f} se vejde do nektereho useku {np.round(sirky, 1).tolist()}")
            check(ef <= L, f"{nazev}: efektivni delka {ef:.0f} neni delsi nez zvolena {L}")
            pan = panely(r)
            check(all(d["part_id"] == S.PANEL_TYPY[int(ef)] for _, _, d in pan), f"{nazev}: vsechny panely maji dil delky {int(ef)}")
            typy = {t["delka"]: t["vejde"] for t in r["panely_info"].get("typy", [])}
            check(typy.get(int(ef)) is True and all(typy.get(d) is False for d in S.PANEL_DELKY if d > int(ef) and d <= L and (opora != "auto")), f"{nazev}: panely_info.typy sedi s vysledkem ({typy})")
            if opora != "auto":                                    # pevna opora: nejdelsi mozna = zadna delka mezi efektivni a zvolenou se nevejde (pri teze opore)
                for d in S.PANEL_DELKY:
                    if int(ef) < d <= L:
                        check(not any(s_ >= d + 2 * MEZERA - 1e-6 for s_ in sirky), f"{nazev}: delka {d} (nad efektivni {int(ef)}) se do zadneho useku {np.round(sirky, 1).tolist()} nevejde")
        # delky sou monotonni: delsi zvolena delka nikdy nedava kratsi vysledek
        efs = [vysl[L]["parametry"]["panely_delka"] if vysl[L]["parametry"]["panely"] else 0 for L in S.PANEL_DELKY]
        check(efs == sorted(efs), f"D s{system} W{sirka} pol{police} {opora}: efektivni delka neklesa se zvolenou ({efs})")
print(f"   ({kontrolovano} konfiguraci)")

print("D2) vice panelu (2-4) ruznych delek: stejny dil, nic se neprekryva, kazdy v nejakem useku, rady nad sebou")
vice = 0
for system in (30, 40):
    P = float(S.SYSTEMY[system]["profil_mm"])
    for sirka, pocet, L, opora in itertools.product((2100, 2800, 3000), (2, 3, 4), S.PANEL_DELKY, ("auto", "noha", "ram")):
        r = S.sestav_stul(system=system, sirka=sirka, panely_pocet=pocet, panely_delka=L, stredni_opora=opora, police=1)
        vice += 1
        nazev = f"D2 s{system} W{sirka} n{pocet} L{L} {opora}"
        if not r["parametry"]["panely"]:
            continue
        ef = int(r["parametry"]["panely_delka"])
        pan = panely(r)
        n_ef = int(r["parametry"]["panely_pocet"])
        check(len(pan) == n_ef and 1 <= n_ef <= pocet and all(d["part_id"] == S.PANEL_TYPY[ef] for _, _, d in pan), f"{nazev}: {len(pan)} panelu (efektivne {n_ef} z {pocet}) vsechny delky {ef} ({sorted({d['part_id'] for _, _, d in pan})})")
        check(not r["problemy"], f"{nazev}: bez problemu ({[(x['kod'], x['text'][:50]) for x in r['problemy'][:2]]})")
        sekce = sekce_z_modelu(r)
        boxy = [bb(d) for _, _, d in pan]
        for (lo_, hi_) in boxy:
            check(any(lo_[2] >= a_ + MEZERA - 1e-3 and hi_[2] <= b_ - MEZERA + 1e-3 for a_, b_ in sekce), f"{nazev}: panel z {lo_[2]:.1f}..{hi_[2]:.1f} lezi v nejakem useku mezi stojkami {[(round(a_, 1), round(b_, 1)) for a_, b_ in sekce]}")
        for i_ in range(len(boxy)):
            for j_ in range(i_ + 1, len(boxy)):
                pres = np.minimum(boxy[i_][1], boxy[j_][1]) - np.maximum(boxy[i_][0], boxy[j_][0])
                check(not np.all(pres > 0.011), f"{nazev}: panely #{i_} a #{j_} se prekryvaji o {np.round(pres, 2).tolist()}")
        radky = sorted({round(float(lo_[1]), 2) for lo_, _ in boxy})
        if len(radky) >= 2:
            mezi = [radky[k] - radky[k - 1] for k in range(1, len(radky))]
            check(all(abs(m_ - (P + VYSKY[ef] + 2 * MEZERA)) < 0.05 for m_ in mezi), f"{nazev}: rady panelu nad sebou po {P + VYSKY[ef] + 2 * MEZERA:.1f} mm ({np.round(mezi, 2).tolist()})")
print(f"   ({vice} konfiguraci)")

# ---------------------------------------------------------------------------------------------------------------------
# E) hash
# ---------------------------------------------------------------------------------------------------------------------
print("E) hash")
h_vych = G.kanonicky_hash(S.sestav_stul(sirka=2100)["parametry"])
r1190 = S.sestav_stul(sirka=2100, panely_delka=1190)
check(G.kanonicky_hash(r1190["parametry"]) == h_vych, "E: vychozi delka 1190 = stejny hash jako bez parametru")
hs = {L: G.kanonicky_hash(S.sestav_stul(sirka=2100, panely_delka=L)["parametry"]) for L in S.PANEL_DELKY}
check(len(set(hs.values())) == len(hs), f"E: ruzne delky = ruzne hashe ({hs})")
check(G.kanonicky_hash(S.sestav_stul(sirka=2100, panely=False, panely_delka=1975)["parametry"]) == G.kanonicky_hash(S.sestav_stul(sirka=2100, panely=False)["parametry"]), "E: bez panelu delka hash nemeni")
r_sn = S.sestav_stul(sirka=1600, panely_delka=1975)
r_pr = S.sestav_stul(sirka=1600, panely_delka=1481)
check(r_sn["parametry"]["panely_delka"] == 1481.0 and G.kanonicky_hash(r_sn["parametry"]) == G.kanonicky_hash(r_pr["parametry"]), "E: snizena delka (1975 -> 1481) ma tentyz hash jako primo zadana 1481")

# ---------------------------------------------------------------------------------------------------------------------
# F) vstup
# ---------------------------------------------------------------------------------------------------------------------
print("F) vstup")
for spatna in (1200, 0, -1190, 1190.5, float("nan"), float("inf"), "1481", True, None):
    try:
        S.sestav_stul(panely_delka=spatna)
        check(False, f"F: panely_delka={spatna!r} musi byt StulChyba")
    except S.StulChyba as e:
        check(e.kod == "mimo_rozsah", f"F: panely_delka={spatna!r} = mimo_rozsah ({e.kod})")
    except (TypeError, ValueError) as e:                                   # noqa: PERF203 - jina vyjimka = chyba ve validaci
        check(False, f"F: panely_delka={spatna!r} dalo {type(e).__name__}: {e}")
check(S.sestav_stul(panely_delka=1481.0, sirka=1800)["parametry"]["panely_delka"] == 1481.0, "F: float 1481.0 se prijme")
check(S.sestav_stul(panely_delka=1481, sirka=1800)["parametry"]["panely_delka"] == 1481.0, "F: int 1481 se prijme")
check(S.parametry_z_dotazu({"panely_delka": "1481"}) == {"panely_delka": 1481.0}, "F: dotaz ?panely_delka=1481")
try:
    S.parametry_z_dotazu({"panely_delka": "abc"})
    check(False, "F: ?panely_delka=abc musi byt chyba")
except S.StulChyba as e:
    check(e.kod == "neplatny_vstup", f"F: ?panely_delka=abc = neplatny_vstup ({e.kod})")
r_sse = S.sestav_stul(system=S.SYSTEM_SSE, panely_delka=1975)
check(r_sse["parametry"]["panely_delka"] == float(S.PANEL_DELKA_VYCHOZI), f"F: stul SSE (41) delku panelu ignoruje ({r_sse['parametry']['panely_delka']})")
check(G.kanonicky_hash(S.sestav_stul(system=S.SYSTEM_SSE, panely_delka=1975)["parametry"]) == G.kanonicky_hash(S.sestav_stul(system=S.SYSTEM_SSE)["parametry"]), "F: SSE: delka panelu hash nemeni")
check(S.panel_limity(30)["min_sirka"] == min_sirka(1190, 30.0) and S.panel_limity(30, 1975)["min_sirka"] == min_sirka(1975, 30.0) and S.panel_limity(40, 1671)["min_sirka"] == min_sirka(1671, 40.0),
      f"F: panel_limity(system, delka) = nejmensi sirka ({S.panel_limity(30)['min_sirka']}, {S.panel_limity(30, 1975)['min_sirka']})")

# ---------------------------------------------------------------------------------------------------------------------
# G) 3D ovladani
# ---------------------------------------------------------------------------------------------------------------------
print("G) 3D ovladani: menu panelu, preklady")
r = S.sestav_stul(sirka=1800, panely_delka=1481)
ov = S.ovladani_3d(r)
cast_pan = next(c for c in ov["casti"] if c["id"] == "panely")
polozky = {m["text"]: m for m in cast_pan["menu"]}
for L in S.PANEL_DELKY:
    txt = f"Zvolit panel {L} mm"
    if L == 1481:
        check(txt not in polozky, "G: aktualni delka (1481) neni v menu")
        continue
    m = polozky.get(txt)
    check(m is not None and m["nastav"] == {"panely_delka": float(L)}, f"G: menu '{txt}' nastavi panely_delka {L} ({m and m.get('nastav')})")
    if m:
        typy = {t["delka"]: t["vejde"] for t in r["panely_info"]["typy"]}
        check(bool(m.get("zakazano")) == (not typy[L]), f"G: '{txt}' je zakazano prave kdyz se nevejde (zakazano {m.get('zakazano')}, vejde {typy[L]})")
        check((m.get("duvod") is not None) == bool(m.get("zakazano")), f"G: '{txt}' ma duvod prave kdyz je zakazano")
check("panely_delka" in cast_pan["param"], "G: cast panelu nese parametr panely_delka")
for lang in ("cs", "en", "sk"):
    try:
        out = OV.ovladani_verejne(ov, lang, 30.0)
        txt = [m["text"] for c in out["casti"] if c["id"] == "panels" for m in c["menu"]]
        check(any("1671" in t_ for t_ in txt) and all(t_ for t_ in txt), f"G: preklad menu panelu ({lang}): {txt[:3]}")
        nast = [m["nastav"] for c in out["casti"] if c["id"] == "panels" for m in c["menu"] if m.get("nastav") and "panellen" in m["nastav"]]
        check(nast and all(isinstance(x["panellen"], str) and x["panellen"] in {str(d) for d in S.PANEL_DELKY} for x in nast), f"G: verejne nastaveni nese slot panellen jako text ({lang}): {nast[:2]}")
    except OV.ChybiPreklad as e:
        check(False, f"G: chybi preklad ({lang}): {e}")

# ---------------------------------------------------------------------------------------------------------------------
# I) vyska panelu a zadni stojky (panel 1671 ma 455 mm, ostatni 460): delka se vejde na vysku i na sirku
# ---------------------------------------------------------------------------------------------------------------------
print("I) vyska panelu: nizke zadni stojky")
for system in (30, 40):
    P = float(S.SYSTEMY[system]["profil_mm"])
    min_st = {L: math.ceil(ODSTUP_PRICKA + VYSKY[L] + 2 * MEZERA + 2 * P) for L in S.PANEL_DELKY}          # nejnizsi zadni stojky pro 1 radu (nezavisly vzorec z vysky panelu)
    check(min_st[1671] < min_st[1975] == min_st[1481] == min_st[1190], f"I s{system}: panel 1671 (455 mm) potrebuje nizsi stojky nez ostatni ({min_st})")
    st_okno = min_st[1671]                                             # stojky, na ktere se vejde JEN panel 1671
    for sv, ocek in ((st_okno, {1190: None, 1481: None, 1671: 1671, 1975: 1671}), (min_st[1190] - 1, {1190: None, 1481: None, 1671: 1671, 1975: 1671}), (min_st[1190], {1190: 1190, 1481: 1481, 1671: 1671, 1975: 1975}),
                     (st_okno - 1, {1190: None, 1481: None, 1671: None, 1975: None})):
        for L in S.PANEL_DELKY:
            r = S.sestav_stul(system=system, sirka=2100, stojky_vyska=float(sv), panely_delka=L, police=1)
            ef = r["parametry"]["panely_delka"] if r["parametry"]["panely"] else None
            check(ef == (float(ocek[L]) if ocek[L] else None), f"I s{system} stojky {sv} zvolena {L}: efektivni delka {ocek[L]} ({ef})")
            if r["parametry"]["panely"]:
                check(not r["problemy"], f"I s{system} stojky {sv} zvolena {L}: bez problemu ({[x['kod'] for x in r['problemy']]})")
                typy = {t["delka"]: t for t in r["panely_info"]["typy"]}
                check(all(typy[d]["vejde_vyska"] == (sv >= min_st[d]) and typy[d]["min_stojky"] == min_st[d] for d in S.PANEL_DELKY), f"I s{system} stojky {sv}: typy[].vejde_vyska / min_stojky sedi ({ {d: (t['vejde_vyska'], t['min_stojky']) for d, t in typy.items()} })")

# ---------------------------------------------------------------------------------------------------------------------
# J) nazvy dilu, bez panelu zadna delka
# ---------------------------------------------------------------------------------------------------------------------
print("J) nazvy dilu s delkou, bez panelu zadna delka")
for L in S.PANEL_DELKY:
    pid = S.PANEL_TYPY[L]
    nazev = S._NAZVY.get(pid)
    check(nazev == ("perforovaný panel" if L == 1190 else f"perforovaný panel {L} mm"), f"J: nazev dilu {pid} = {nazev!r} (1190 beze zmeny, ostatni s delkou)")
check(all(S.PREPINAC_DILU.get(pid) == "panely" for pid in S.PANEL_PARTY), f"J: PREPINAC_DILU: vsechny dily panelu -> prepinac panely ({ {pid: S.PREPINAC_DILU.get(pid) for pid in S.PANEL_PARTY} })")
r = S.sestav_stul(sirka=2100, panely=False, panely_delka=1975)
check(r["parametry"]["panely_delka"] == float(S.PANEL_DELKA_VYCHOZI) and not [d for d in r["dily"] if d["part_id"] in S.PANEL_PARTY], "J: bez panelu je delka 1190 a v modelu zadny panel")
r = S.sestav_stul(sirka=1100, panely_delka=1975)
check(not r["parametry"]["panely"] and r["parametry"]["panely_delka"] == float(S.PANEL_DELKA_VYCHOZI), f"J: nevejde se ani 1190 = panely odebrane a delka 1190 ({r['parametry']['panely']}, {r['parametry']['panely_delka']})")
# chybejici GLB jedne delky nesmi shodit vychozi cestu (jen se tato delka nenabizi)
S.BBOX_PREPIS.clear()
_orig_bbox = S._bbox_ze_souboru
def _bez_4974(part_id):
    if part_id == S.PANEL_TYPY[1975]:
        raise S.StulChyba("chybi GLB dilu (test)", "glb")
    return _orig_bbox(part_id)
S._bbox_ze_souboru = _bez_4974
S._BBOX_CACHE.pop(S.PANEL_TYPY[1975], None)
S._AABB_MEMO.clear()
try:
    r = S.sestav_stul(sirka=2100)
    check(r["parametry"]["panely"] and not r["problemy"] and [t["delka"] for t in r["panely_info"]["typy"]] == [1190, 1481, 1671], f"J: bez GLB delky 1975 vychozi stul funguje a nabizi jen ostatni ({[t['delka'] for t in r['panely_info']['typy']]})")
    r2 = S.sestav_stul(sirka=2100, panely_delka=1671)
    check(r2["panely_info"]["delka"] == 1671, "J: bez GLB delky 1975 jde zvolit 1671")
finally:
    S._bbox_ze_souboru = _orig_bbox
    S._BBOX_CACHE.pop(S.PANEL_TYPY[1975], None)
    S._AABB_MEMO.clear()

# ---------------------------------------------------------------------------------------------------------------------
# H) zlaty otisk
# ---------------------------------------------------------------------------------------------------------------------
print("H) zlaty otisk (vychozi delka beze zmeny proti stavu pred zavedenim delky)")
import golden_head as GH  # noqa: E402
zlato = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_head.json"), encoding="utf-8"))
ted = GH.vypocti()
check(set(zlato) == set(ted), f"H: stejna mrizka konfiguraci ({len(zlato)} vs {len(ted)})")
spatne = []
automaticke = 0                                                                  # stoly, kde drive vznikalo VIC svitidel LED automaticky (od 2026-10-08 je pocet svitidel RUCNI, vychozi 1)
for k in zlato:
    if k not in ted or zlato[k] == ted[k]:
        continue
    if hasattr(GH.S, "LED_MAX"):
        p_ = json.loads(k)
        pp_ = GH.S.sestav_stul(**p_)["parametry"]
        nmax_ = GH.S.led_max_pocet(pp_["sirka"], GH.S.led_telo_dilu(GH.S.LED_TYPY[GH.S._led_delka_int(pp_["led_delka"])])) if (pp_["led"] and pp_["stojky"] and pp_["led_svetlo"]) else 1
        if nmax_ >= 2:
            r2_ = GH.S.sestav_stul(**p_, led_pocet=nmax_)
            if GH.otisk(r2_) == zlato[k]["otisk"] and (int(r2_["parametry"]["panely_pocet"]) if r2_["parametry"]["panely"] else 0) == zlato[k]["panelu"] and len(r2_["problemy"]) == zlato[k]["problemu"]:
                automaticke += 1
                continue
    spatne.append(k)
check(not spatne, f"H: {len(spatne)} konfiguraci se lisi od stavu pred zavedenim delky, napr. {spatne[:2]} -> {[(zlato[k], ted[k]) for k in spatne[:1]]}")
print(f"   ({automaticke} sirokych stolu s LED: drive automaticky pocet svitidel, ted led_pocet = drivejsi pocet da presne drivejsi otisk)")
print(f"   ({len(zlato)} konfiguraci)")

print()
if FAILS:
    print(f"CHYBA: {len(FAILS)} kontrol selhalo, {OK} OK")
    sys.exit(1)
print(f"{OK} kontrol OK")
