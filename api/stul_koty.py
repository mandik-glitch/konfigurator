"""Koty (rozmerove cary) do 3D nahledu generatoru stolu (bot8, 2026-10-05).

Robert 2026-10-05: ve 3D nahledu generatoru ma byt (i v dratenem vzhledu) tohle:
  * celkova vyska od podlahy po posledni konec profilu,
  * rozmery pracovni desky (delka, hloubka),
  * vyska horni roviny pracovni desky od podlahy,
  * vzdalenosti perforovanych panelu od vsech nohou (panely chce pohyblive, kdyz maji mezi nohama mezeru - viz `panely_posun_z` v generatoru),
  * vnitrni vyska od podlahy ke spodni hrane podelniku, ktery nese pracovni desku,
  * mezery mezi spodnimi policemi,
  * vyska od podlahy po horni rovinu kazde spodni police.

Cista funkce nad vysledkem generatoru: `koty(r)` -> seznam kot ve formatu `scenes[0].extras.v3d.dims` (viewer3d.js: a, b = konce mereni, o = posun cary od mereni, t = cislo,
l = uroven 1 "Rozmery" / 2 "Detail", m = poloha popisku na care 0-1; viz docs/VIEWER3D_SETMODEL.md). SOURADNICE JSOU V SOURADNICICH GENERATORU (mm; x = hloubka, predek v mensim x,
y = nahoru, z = sirka zleva doprava) - `stul_glb.poskladej_glb` je posune stejne jako model. Text kot je jen cislo (viewer jiny text nezobrazi), proto je poloha cary vzdy u
mereneho dilu: kdo kotu cte, vidi, co meri. Mereni vyska "od podlahy" se kresli jako sloupec u praveho (police, vnitrni vyska) a leveho (pracovni deska, celek) boku stolu s popiskem
u horniho konce cary (m = 1).
"""
import math
import re

import stul_konfigurator as S

OFF = 130.0                      # mm: o kolik je svisly sloupec kot vedle boku stolu
OFF_PANEL = 70.0                 # mm: o kolik pred panelem lezi cary vzdalenosti od nohou
PRAHY_MEZERY = 0.5               # mm: mezera mensi nez tolik se nekotuje (panel se dotyka nohy)
M_RAZ_DESKY = 0.3                # poloha popisku delky a hloubky desky na care: mimo stred (tam jsou uchyty 3D ovladani Sirka / Hloubka desky) a mimo konec u popisku vysky
ODSTUP_VYSKY = 45.0               # mm: svisly odstup leve / prave kóty vzdalenosti panelu od nohy od stredu panelu
_RE_POLICE = re.compile(r"^pol(\d+)_\d+$")


def _cislo(v):
    """Hodnota v mm -> text pro viewer ("1 925"): zaokrouhleno NA CELE mm, pulky nahoru (sablona stolu je o setiny mm vedle: 839,537 -> 840 = stul, jak ho zakaznik zvolil)."""
    n = int(math.floor(float(v) + 0.5))
    return f"{n:,}".replace(",", " ")


def _kota(a, b, o, v, uroven=1, m=None):
    k = {"a": [round(float(x), 3) for x in a], "b": [round(float(x), 3) for x in b], "o": [round(float(x), 3) for x in o], "t": _cislo(v), "l": int(uroven)}
    if m is not None:
        k["m"] = round(float(m), 3)
    return k


def _sloupec(x_zdroj, z_zdroj, x_sl, z_sl):
    """Posun cary `o` (vodorovny), kterym se dim z miste mereni (x_zdroj, z_zdroj) dostane do sloupce kot (x_sl, z_sl)."""
    return (x_sl - x_zdroj, 0.0, z_sl - z_zdroj)


def koty(r):
    """Koty stolu z vysledku generatoru `r` (sestav_stul): seznam slovniku {a, b, o, t, l[, m]} v souradnicich generatoru. Bez pracovni desky (nemuze nastat) prazdny seznam."""
    dily, klice, p = r["dily"], r["klice"], r["parametry"]
    bb = [S._aabb(d) for d in dily]
    P = float(S.SYSTEMY[int(p["system"])]["profil_mm"])

    def klic(i):
        k = klice[i]
        return tuple(tuple(x) if isinstance(x, list) else x for x in k) if isinstance(k, (list, tuple)) else k

    def ids_desky(re_nebo_predpona):
        out = {}
        for i, d in enumerate(dily):
            did = str(d.get("deska_id") or "")
            if callable(getattr(re_nebo_predpona, "match", None)):
                m = re_nebo_predpona.match(did)
                if m:
                    out.setdefault(int(m.group(1)), []).append(i)
            elif did.startswith(re_nebo_predpona):
                out.setdefault(0, []).append(i)
        return out

    prac = ids_desky("prac").get(0, [])
    if not prac:
        return []

    def sjednoceni(ids):
        return (min(float(bb[i][0][0]) for i in ids), min(float(bb[i][0][1]) for i in ids), min(float(bb[i][0][2]) for i in ids),
                max(float(bb[i][1][0]) for i in ids), max(float(bb[i][1][1]) for i in ids), max(float(bb[i][1][2]) for i in ids))

    xf, _yd0, zl, xb, yt, zr = sjednoceni(prac)                     # pracovni deska: predni a zadni hrana, leva a prava hrana, horni rovina
    podlaha = float(r["rozmery"]["y_min"])
    # ---- profily: nejvyssi konec (celkova vyska) a podelniky nesouci pracovni desku (vnitrni vyska)
    profily = [i for i, d in enumerate(dily) if d["part_id"] in S.PROFIL_PARTS]
    y_celek = max([float(bb[i][1][1]) for i in profily] + [yt])
    nosne = [i for i in range(len(dily)) if klic(i) in (("t", S.ZRAIL_PRAC_PRED), ("t", S.ZRAIL_PRAC_ZAD), ("t", S.XRAIL_PRAC_L), ("t", S.XRAIL_PRAC_P))]
    y_nosny = min([float(bb[i][0][1]) for i in nosne]) if nosne else float(yt - S.DESKA_TLOUSTKA - P)          # spodni hrana podelniku nesouciho pracovni desku
    x_celek = min([float(bb[i][0][0]) for i in profily if bb[i][1][1] >= y_celek - 0.5] or [xf])             # nejpredni lico nejvyssiho profilu (kota stoji v jeho rovine)
    x_nohy = min([float(bb[i][0][0]) for i in range(len(dily)) if klic(i) in (("t", S.NOHA_PL), ("t", S.NOHA_PP))] or [xf])      # predni lico predni nohy

    out = []
    # ---- LEVY SLOUPEC (-z): vyska horni roviny pracovni desky, celkova vyska; popisek u horniho konce
    zc_l = zl - OFF
    out.append(_kota((xf, podlaha, zl), (xf, yt, zl), (0.0, 0.0, -OFF), yt - podlaha, 1, 1.0))
    if y_celek - yt > 1.0:
        out.append(_kota((x_celek, podlaha, zl), (x_celek, y_celek, zl), _sloupec(x_celek, zl, xf, zc_l), y_celek - podlaha, 1, 1.0))
    # ---- pracovni deska: delka podel predni hrany, hloubka podel leve hrany (v rovine horni plochy)
    out.append(_kota((xf, yt, zl), (xf, yt, zr), (-OFF, 0.0, 0.0), zr - zl, 1, M_RAZ_DESKY))
    out.append(_kota((xf, yt, zl), (xb, yt, zl), (0.0, 0.0, -OFF), xb - xf, 1, 1.0 - M_RAZ_DESKY))
    # ---- PRAVY SLOUPEC (+z): vnitrni vyska (k spodni hrane podelniku), vyska horni roviny kazde spodni police; popisky u horniho konce
    zc_r = zr + OFF
    out.append(_kota((x_nohy, podlaha, zr), (x_nohy, y_nosny, zr), (0.0, 0.0, OFF), y_nosny - podlaha, 1, 1.0))
    police = {}
    for k, ids in ids_desky(_RE_POLICE).items():
        x0, y0, z0, x1, y1, z1 = sjednoceni(ids)
        police[k] = {"x": x0, "x_zad": x1, "z": z1, "dno": y0, "vrch": y1}
    if not police and not p.get("police_deska", True) and p.get("police"):          # police BEZ DESKY (Robert 2026-10-07): deska uz neni, kota patri hornimu lici ramu police (horni hrana bocnich pricek)
        patra = {}
        for i in range(len(dily)):
            k_ = S._patro_ramu_police(klic(i))
            if k_ is not None:
                patra.setdefault(k_, []).append(i)
        for k, ids in patra.items():
            x0, y0, z0, x1, y1, z1 = sjednoceni(ids)
            police[k] = {"x": x0, "x_zad": x1, "z": z1, "dno": y1, "vrch": y1}
    seznam = [police[k] for k in sorted(police, key=lambda k: police[k]["vrch"])]
    for pol in seznam:
        out.append(_kota((pol["x"], podlaha, pol["z"]), (pol["x"], pol["vrch"], pol["z"]), _sloupec(pol["x"], pol["z"], x_nohy, zc_r), pol["vrch"] - podlaha, 1, 1.0))
    # ---- mezery mezi policemi: od horni plochy spodni police ke spodku RAMU police nad ni (deska lezi na rame silnem profil), nad nejvyssi policí k podelniku; popisek uprostred mezery
    for j, pol in enumerate(seznam):
        horni_hrana = (seznam[j + 1]["dno"] - P) if j + 1 < len(seznam) else y_nosny
        mezera = horni_hrana - pol["vrch"]
        if mezera > PRAHY_MEZERY:
            xm = pol["x_zad"]                                        # zadni pravy roh police: sloupec mezer je na druhem konci boku nez sloupec vysek (popisky se v zadnem pohledu nepřekryvají)
            out.append(_kota((xm, pol["vrch"], pol["z"]), (xm, horni_hrana, pol["z"]), (0.0, 0.0, 2.5 * OFF), mezera, 1))
    # ---- perforovane panely: vzdalenost bocnich hran od nejblizsich noh (zadni stojky, stredni zadni noha)
    nohy = [(float(bb[i][0][2]), float(bb[i][1][2]), float(bb[i][0][1]), float(bb[i][1][1])) for i in range(len(dily))
            if klic(i) in (("t", S.NOHA_ZL), ("t", S.NOHA_ZP), "RM")]
    sloupce = {}
    for i, d in enumerate(dily):
        if d["part_id"] in S.PANEL_PARTY:
            kl = klic(i)
            sloupce.setdefault(kl[2] if isinstance(kl, tuple) and len(kl) >= 3 else i, []).append(i)
    for c in sorted(sloupce):
        ids = sloupce[c]
        px0, py0, pz0, px1, py1, pz1 = sjednoceni(ids)
        y_stred = (py0 + py1) / 2.0
        vlevo = [n for n in nohy if n[1] <= pz0 + PRAHY_MEZERY and n[2] <= y_stred <= n[3]]
        vpravo = [n for n in nohy if n[0] >= pz1 - PRAHY_MEZERY and n[2] <= y_stred <= n[3]]
        if vlevo:                                                    # mezera vlevo o kus vys, vpravo o kus niz: u spolecne (stredni) nohy by se jinak oba popisky prekryly
            z_n = max(n[1] for n in vlevo)
            if pz0 - z_n > PRAHY_MEZERY:
                out.append(_kota((px0, y_stred + ODSTUP_VYSKY, z_n), (px0, y_stred + ODSTUP_VYSKY, pz0), (-OFF_PANEL, 0.0, 0.0), pz0 - z_n, 1))
        if vpravo:
            z_n = min(n[0] for n in vpravo)
            if z_n - pz1 > PRAHY_MEZERY:
                out.append(_kota((px0, y_stred - ODSTUP_VYSKY, pz1), (px0, y_stred - ODSTUP_VYSKY, z_n), (-OFF_PANEL, 0.0, 0.0), z_n - pz1, 1))
    # ---- stul SSE (system 41): mezera mezi nohami (svetla vzdalenost vnitrnich lic sousednich noh; u desky 2000 mm 1570 mm - Robert), kota na podlaze pred stolem
    sse = r.get("sse")
    if sse and len(sse["nohy"]) >= 2:
        pul = S.SSE_JEKL / 2.0
        for a_, b_ in zip(sse["nohy"], sse["nohy"][1:]):
            out.append(_kota((xf, podlaha, a_ + pul), (xf, podlaha, b_ - pul), (-OFF, 0.0, 0.0), b_ - a_ - S.SSE_JEKL, 1, 0.5))
    return out
