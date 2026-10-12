"""Řady euroboxů (400x300, 600x400) s válečkovými dráhami pro Generátor Dynamic.

Čistý Python + numpy, žádná DB / síť / soubory za běhu. Deterministické, výstup JSON-serializovatelný.
Rozměry dílů a euroboxů jsou odvozené z GLB (skript odvod_konstant.py) a ze zadání; co není ověřeno
na GLB, je označené `neoverene` (viz ODVOZENI.md).

SOUŘADNICE (mm): X = hloubka (0 = předek), Y = nahoru (0 = podlaha), Z = šířka.

VSTUP `spec` (vše kromě `rady` je volitelné):
  rady: [{id, typ: "400x300"|"600x400", vyska, smer: "delka"|"sirka", pocet, x, y, z,
          patro?, sklon_deg?}]
      smer "delka": delší strana boxu (400 / 600) leží PODÉL řady; "sirka": kratší strana podél řady.
      x, y, z = dolní přední roh obálky prvního boxu na NIŽŠÍM konci řady (spodek nožky boxu):
        souřadnice podél osy řady = nižší konec řady (u nizsi_konec="zadek" je to hrana s větší
        souřadnicí a řada se rozbíhá do menších), souřadnice napříč = menší (min) strana řady.
  sklon_deg: výchozí sklon všech řad (stupně, 0 = vodorovně)
  patra: {id_patra: {sklon_deg}}   přepis sklonu po patrech (přepis řady má přednost před patrem)
  mezera_boxu_mm: 1.0               čistá mezera mezi obálkami sousedních boxů v řadě
  draha: "5276" (výchozí) | "5275"  karta dráhy
  osa_rady: "x" (výchozí) | "z"     osa, podél které jdou boxy za sebou
  nizsi_konec: "predek" (výchozí) | "zadek"   nižší konec skloněné řady = menší | větší souřadnice
  zasun_draha_mm: 54.5              kolik mm dráhy je zasunuto do kapsy koncovky (neověřeno)
  kapsa_hloubka_mm: 54.5            hloubka kapsy koncovky (neověřeno)
  zarazka_u: "kapsa" | "hak"        kde na plechu 5282 je svislá zarážka (neověřeno, výchozí kapsa)
  roztec_drah_mm: null              osová rozteč 2 drah (null = výchozí podle typu dráhy a boxu)
  odstup_nozka_mm: 10               u 5275: odstup vnější hrany dráhy od hrany nožky boxu
  presah_nosniku_mm: 0              o kolik trubka přesahuje krajní koncovku (nohy dodá rám)
  hrubka_zarazky_mm: 1.5            tloušťka svislé zarážky (odhad)
  sklon_doporuceny_deg: [2, 15]     mimo => varování (neověřeno); <0 nebo >=45 => chyba
  min_mezera_pater_mm: 10           menší výšková mezera pater => varování
  deska_mm: 0                       tloušťka desky pod vodorovnou řadou (jen pro mezeru pater)
  max_rozpeti_mm: null              nad touto vzdáleností trubek na řadě varování
  mrizka_mezery_mm: 2.0             krok vzorkování při výpočtu výškové mezery pater
  tolerance_kolize_mm: 0.05         hloubka průniku, od které je to kolize

VÝSTUP `postav(spec)`: viz klíče na konci funkce `postav` a ODVOZENI.md.
Kvůli kopírování řad: `kopie_rady(spec, id_rady, kam, mezera_mm, pocet=1)` a
`min_vyska_patra(spec, patro_dole, patro_nahore, mezera_mm=0)`.
"""
from __future__ import annotations

import copy
import itertools
import math

import numpy as np

VERZE = "2026-10-12.1"
R_TRUBKY = 14.0          # trubka Ø28 (karta 3673)
HR_ZARAZKY = 1.5

# ---------------------------------------------------------------------------------------------
# EUROBOXY
# ---------------------------------------------------------------------------------------------
# GLB 400x300 (karty 3788..3796): rozměr GLB 299 x 399 (jmenovitě 300 x 400 minus 1 mm); počítá se
# s JMENOVITOU obálkou 300 x 400, model leží uvnitř, vystředěný. Střed obálky GLB v lokálních
# souřadnicích je odvozen skriptem odvod_konstant.py (lokální X = kratší strana, Y = delší, Z = výška,
# nožka u min Z).
# Nožka: dole 266 x 366 mm (odvozeno), nahoře se rozšiřuje na ~274,2 x 375,0 mm, výška 12 mm.
BOXY = {
    "400x300": {
        "dlouha": 400.0, "kratka": 300.0,
        "vysky": {
            120: {"karta": 3788, "stred_glb": (142.9867, -392.5566, -521.0865)},
            170: {"karta": 3793, "stred_glb": (0.0199, -0.0002, 109.2674)},
            220: {"karta": 3794, "stred_glb": (142.9867, -392.5566, -583.5673)},
            270: {"karta": 3795, "stred_glb": (142.9867, -392.5566, -847.134)},
            320: {"karta": 3796, "stred_glb": (142.9867, -392.5566, -532.0674)},
        },
        "nozka_h": 12.0,
        "nozka_dole": (266.0, 366.0),      # (kratka, dlouha) u spodní plochy nožky
        "nozka_hore": (274.2, 375.0),      # (kratka, dlouha) u horní hrany nožky
        "model": True,
    },
    # 600x400: modely nemáme (jen neaktivní karty dodavatele 2999-3003) => kvádr bez nožky.
    "600x400": {
        "dlouha": 600.0, "kratka": 400.0,
        "vysky": {
            120: {"karta": None, "karta_dodavatele_kandidat": 2999},
            170: {"karta": None, "karta_dodavatele_kandidat": 3000},
            220: {"karta": None, "karta_dodavatele_kandidat": 3001},
            320: {"karta": None, "karta_dodavatele_kandidat": 3002},
            420: {"karta": None, "karta_dodavatele_kandidat": 3003},
        },
        "nozka_h": 0.0,
        "nozka_dole": (400.0, 600.0),
        "nozka_hore": (400.0, 600.0),
        "model": False,
    },
}

# ---------------------------------------------------------------------------------------------
# DÍLY (rozměry ze zadání; GLB zatím nejsou => procedurální náhrady o stejných rozměrech)
# Osy lokální: viz `osy` (index lokální osy podél / napříč / nahoru). Neověřené orientace: `neoverene`.
# ---------------------------------------------------------------------------------------------
DILY = {
    5275: {"sku": "2.2.016.027.037.01", "role": "draha", "rozmer_glb": (271.66, 37.24, 38.86),
           "delka": 271.66, "sirka": 37.24, "pod": 38.86, "nad": 0.0, "doraz": False,
           "osy": {"podel": 0, "napric": 1, "nahoru": 2}, "stred_glb": (0.0, 0.0, 0.0)},
    5276: {"sku": "2.2.016.027.037.03", "role": "draha", "rozmer_glb": (41.0, 61.67, 255.04),
           "delka": 255.04, "sirka": 41.0, "pod": 33.67, "nad": 28.0, "doraz": True,
           "osy": {"podel": 2, "napric": 0, "nahoru": 1}, "stred_glb": (0.0, 0.0, 0.0)},
    5281: {"sku": "2.2.017.000.055.01", "role": "horni", "rozmer_glb": (38.47, 27.75, 86.29),
           "delka": 86.29, "sirka": 38.47, "pod": 27.75, "nad": 0.0,
           "osy": {"podel": 2, "napric": 0, "nahoru": 1}, "stred_glb": (0.0, 0.0, 0.0)},
    5282: {"sku": "2.2.017.035.055.01", "role": "dolni", "rozmer_glb": (38.47, 55.75, 86.29),
           "delka": 86.29, "sirka": 38.47, "pod": 27.75, "nad": 28.0,
           "osy": {"podel": 2, "napric": 0, "nahoru": 1}, "stred_glb": (0.0, 0.0, 0.0)},
}
HRANA_BOCNIHO_DORAZU = 3.0   # tloušťka bočního dorazu dráhy 5276 (odhad, jen pro náhradu)

DEFAULTY = {
    "sklon_deg": 0.0,
    "mezera_boxu_mm": 1.0,
    "draha": "5276",
    "osa_rady": "x",
    "nizsi_konec": "predek",
    "zasun_draha_mm": 54.5,
    "kapsa_hloubka_mm": 54.5,
    "zarazka_u": "kapsa",
    "roztec_drah_mm": None,
    "odstup_nozka_mm": 10.0,
    "presah_nosniku_mm": 0.0,
    "hrubka_zarazky_mm": HR_ZARAZKY,
    "sklon_doporuceny_deg": [2.0, 15.0],
    "min_mezera_pater_mm": 10.0,
    "deska_mm": 0.0,
    "max_rozpeti_mm": None,
    "mrizka_mezery_mm": 2.0,
    "tolerance_kolize_mm": 0.05,
}

NEOVERENO = (
    "GLB dílů 5275-5282 zatím nejsou v repu: tvar, orientace, poloha háku a kapsy jsou odvozené z rozměrů "
    "(viz ODVOZENI.md)."
)


# ---------------------------------------------------------------------------------------------
# pomocné
# ---------------------------------------------------------------------------------------------
def _v(*a):
    return np.array(a, dtype=float)


def _unit(x):
    x = np.asarray(x, dtype=float)
    return x / np.linalg.norm(x)


def _quat(M):
    """Kvaternion [x,y,z,w] z rotační matice (sloupce = lokální osy ve světě), w >= 0."""
    m = np.asarray(M, dtype=float)
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([x, y, z, w])
    q /= np.linalg.norm(q)
    if q[3] < 0 or (q[3] == 0 and q[:3][np.nonzero(q[:3])[0][0]] < 0):
        q = -q
    return q


_PRESNE = {"quaternion", "vektor_podel", "vektor_kolmo", "vektor_napric", "osy"}


def _zaokr(o, des=3):
    """Zaokrouhlení výstupu: mm na 3 desetinná místa, směrové vektory a kvaterniony na 7."""
    if isinstance(o, dict):
        return {k: _zaokr(v, 7 if k in _PRESNE else des) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_zaokr(v, des) for v in o]
    if isinstance(o, np.ndarray):
        return _zaokr(o.tolist(), des)
    if isinstance(o, (np.floating, float)):
        r = round(float(o), des)
        return 0.0 if r == 0 else r
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


class _Rama:
    """Souřadnicový rám řady: bod = P0 + s*d + t*c + h*n  (s podél sklonu nahoru, t napříč, h kolmo)."""

    def __init__(self, P0, os_idx, znam_u, theta):
        e_al = np.zeros(3)
        e_al[os_idx] = 1.0
        e_ac = np.zeros(3)
        e_ac[2 if os_idx == 0 else 0] = 1.0
        up = _v(0, 1, 0)
        th = math.radians(theta)
        self.P0 = np.asarray(P0, float)
        self.d = math.cos(th) * znam_u * e_al + math.sin(th) * up
        self.n = -math.sin(th) * znam_u * e_al + math.cos(th) * up
        self.c = e_ac
        self.U = np.array([self.d, self.c, self.n])   # řádky = osy
        self.th = theta
        self.os_idx = os_idx
        self.os_napric = 2 if os_idx == 0 else 0

    def bod(self, s, t, h):
        return self.P0 + s * self.d + t * self.c + h * self.n

    def obb(self, s0, s1, t0, t1, h0, h1, **extra):
        c = self.bod((s0 + s1) / 2, (t0 + t1) / 2, (h0 + h1) / 2)
        o = {"typ": "obb", "c": c, "u": self.U.copy(), "h": _v((s1 - s0) / 2, (t1 - t0) / 2, (h1 - h0) / 2)}
        o.update(extra)
        return o


def _verts_obb(o):
    sg = np.array(list(itertools.product((-1, 1), repeat=3)), float)
    return o["c"] + (sg * o["h"]) @ o["u"]


_N = 16


def _cyl_geom(cy):
    a = _unit(cy["a"])
    p = np.cross(a, _v(0, 1, 0))
    if np.linalg.norm(p) < 1e-6:
        p = np.cross(a, _v(1, 0, 0))
    p = _unit(p)
    q = np.cross(a, p)
    rc = cy["r"] / math.cos(math.pi / _N)
    ang = np.arange(_N) * 2 * math.pi / _N
    ring = rc * (np.outer(np.cos(ang), p) + np.outer(np.sin(ang), q))
    v = np.concatenate([cy["c"] + cy["hl"] * a + ring, cy["c"] - cy["hl"] * a + ring])
    nang = (np.arange(_N // 2) * 2 + 1) * math.pi / _N
    nor = [a] + [math.cos(x) * p + math.sin(x) * q for x in nang]
    edg = [a] + [-math.sin(x) * p + math.cos(x) * q for x in nang]
    return v, nor, edg


def _poly(o):
    if o["typ"] == "obb":
        return _verts_obb(o), [x for x in o["u"]], [x for x in o["u"]]
    return _cyl_geom(o)


def _aabb(o):
    v = _poly(o)[0]
    return v.min(0), v.max(0)


def _sat_hloubka(A, B):
    """Hloubka průniku dvou konvexních těles (0 = oddělená / jen dotyk)."""
    va, na, ea = _poly(A)
    vb, nb, eb = _poly(B)
    osy = list(na) + list(nb)
    for x in ea:
        for y in eb:
            cr = np.cross(x, y)
            ln = np.linalg.norm(cr)
            if ln > 1e-9:
                osy.append(cr / ln)
    best = np.inf
    for ax in osy:
        pa = va @ ax
        pb = vb @ ax
        ov = min(pa.max(), pb.max()) - max(pa.min(), pb.min())
        if ov <= 0:
            return 0.0
        best = min(best, ov)
    return float(best)


# ---------------------------------------------------------------------------------------------
# NORMALIZACE VSTUPU
# ---------------------------------------------------------------------------------------------
def _parametry(spec):
    p = copy.deepcopy(DEFAULTY)
    for k in DEFAULTY:
        if k in spec and spec[k] is not None:
            p[k] = spec[k]
    if p["draha"] not in ("5275", "5276", 5275, 5276):
        raise ValueError("draha musí být 5275 nebo 5276")
    p["draha"] = str(p["draha"])
    if p["osa_rady"] not in ("x", "z"):
        raise ValueError("osa_rady musí být x nebo z")
    if p["nizsi_konec"] not in ("predek", "zadek"):
        raise ValueError("nizsi_konec musí být predek nebo zadek")
    if p["zarazka_u"] not in ("kapsa", "hak"):
        raise ValueError("zarazka_u musí být kapsa nebo hak")
    return p


def _patro_id(r):
    if r.get("patro") not in (None, ""):
        return str(r["patro"])
    return "auto@%.1f" % float(r["y"])


def _sklon_rady(r, spec, p):
    if r.get("sklon_deg") is not None:
        return float(r["sklon_deg"])
    pid = _patro_id(r)
    pt = (spec.get("patra") or {}).get(pid)
    if pt and pt.get("sklon_deg") is not None:
        return float(pt["sklon_deg"])
    return float(p["sklon_deg"])


# ---------------------------------------------------------------------------------------------
# STAVBA JEDNÉ ŘADY
# ---------------------------------------------------------------------------------------------
def _roztec_vychozi(draha, typ, smer, p):
    b = BOXY[typ]["kratka"] if smer == "delka" else BOXY[typ]["dlouha"]   # rozměr napříč
    dl = DILY[int(draha)]
    w = dl["sirka"]
    if draha == "5276":
        # boční doraz (strana ven, odhad tloušťky HRANA_BOCNIHO_DORAZU) 1 mm za bokem boxu
        return b + 2.0 * (1.0 + HRANA_BOCNIHO_DORAZU) - w
    nozka = BOXY[typ]["nozka_dole"]
    nz = nozka[0] if smer == "delka" else nozka[1]
    return nz - w - 2.0 * p["odstup_nozka_mm"]


def _pose_dil(M_cols_podel, nahoru, napric_vec, cfg, stred_svet):
    """Pozice+kvaternion dílu: lokální osy podle cfg['osy'], podel -> M_cols_podel, nahoru -> nahoru."""
    i_al, i_ac, i_up = cfg["osy"]["podel"], cfg["osy"]["napric"], cfg["osy"]["nahoru"]
    M = np.zeros((3, 3))
    M[:, i_al] = M_cols_podel
    M[:, i_up] = nahoru
    M[:, i_ac] = np.cross(nahoru, M_cols_podel)
    if np.linalg.det(M) < 0:
        M[:, i_ac] *= -1
    sg = _v(*cfg["stred_glb"])
    pos = np.asarray(stred_svet, float) - M @ sg
    return pos, _quat(M), M


def _stavba_rady(r, spec, p, soupis):
    """Vrátí slovník s geometrií řady: boxy, dráhy, koncovky, tvary pro kolize a podobně."""
    typ = r["typ"]
    if typ not in BOXY:
        raise ValueError("neznámý typ boxu: %r" % typ)
    bx = BOXY[typ]
    smer = r.get("smer", "delka")
    if smer not in ("delka", "sirka"):
        raise ValueError("smer musí být delka nebo sirka")
    n = int(r["pocet"])
    if n < 1:
        raise ValueError("pocet >= 1")
    vyska = int(r["vyska"])
    a = bx["dlouha"] if smer == "delka" else bx["kratka"]       # podél řady
    b = bx["kratka"] if smer == "delka" else bx["dlouha"]       # napříč
    gap = float(p["mezera_boxu_mm"])
    L = n * a + (n - 1) * gap
    theta = _sklon_rady(r, spec, p)
    os_idx = 0 if p["osa_rady"] == "x" else 2
    znam_u = 1.0 if p["nizsi_konec"] == "predek" else -1.0
    P0 = _v(r["x"], r["y"], r["z"])
    fr = _Rama(P0, os_idx, znam_u, theta)
    rid = str(r["id"])
    pid = _patro_id(r)
    res = {"id": rid, "patro": pid, "theta": theta, "fr": fr, "a": a, "b": b, "L": L, "n": n,
           "typ": typ, "smer": smer, "vyska": vyska, "znam_u": znam_u, "os_idx": os_idx,
           "boxy": [], "draha": None, "koncovky": [], "tvary": [], "opory": [], "problemy": []}
    if vyska not in bx["vysky"]:
        res["problemy"].append({"kod": "NEZNAMA_VYSKA", "uroven": "chyba", "id": [rid],
                                "text": "Výška %d mm není pro %s v nabídce (%s)." % (
                                    vyska, typ, "/".join(str(x) for x in sorted(bx["vysky"])))})
    info = bx["vysky"].get(vyska, {"karta": None})
    fh = bx["nozka_h"]
    nd, nh = bx["nozka_dole"], bx["nozka_hore"]
    # nožka: (kratka, dlouha) -> (napříč, podél) podle směru
    if smer == "delka":
        nz_ac_d, nz_al_d, nz_ac_h, nz_al_h = nd[0], nd[1], nh[0], nh[1]
    else:
        nz_ac_d, nz_al_d, nz_ac_h, nz_al_h = nd[1], nd[0], nh[1], nh[0]
    res["nozka_napric_dole"] = nz_ac_d
    res["nozka_napric_hore"] = nz_ac_h

    # --- boxy ----------------------------------------------------------------------------------
    for i in range(n):
        s0 = i * (a + gap)
        s1 = s0 + a
        sc, tc, hc = (s0 + s1) / 2, b / 2, vyska / 2
        centrum = fr.bod(sc, tc, hc)
        d, n_ = fr.d, fr.n
        if smer == "delka":
            # lokální Y (delší) podél řady, X (kratší) napříč, Z nahoru
            Y, Z = d, n_
            X = np.cross(Y, Z)
        else:
            X, Z = d, n_
            Y = np.cross(Z, X)
        M = np.column_stack([X, Y, Z])
        if "stred_glb" in info:
            pos = centrum - M @ _v(*info["stred_glb"])
        else:
            pos = centrum
        # tvary pro kolize: tělo + nožka
        tv = []
        if fh > 0:
            tv.append(fr.obb(s0 + (a - nz_al_h) / 2, s0 + (a + nz_al_h) / 2, (b - nz_ac_h) / 2, (b + nz_ac_h) / 2,
                             0, fh, rodic="box", nazev="nozka"))
        tv.append(fr.obb(s0, s1, 0, b, fh, vyska, rodic="box", nazev="telo"))
        box = {
            "id": "%s#%d" % (rid, i + 1), "rada": rid, "patro": pid, "index": i + 1, "typ": typ,
            "vyska": vyska, "smer": smer,
            "part_id": info.get("karta"),
            "kvadr": not bx["model"],
            "position": pos, "quaternion": _quat(M), "scale": [1.0, 1.0, 1.0],
            "stred": centrum,
            "rozmer_obalky": [a, b, float(vyska)],
        }
        if info.get("karta_dodavatele_kandidat"):
            box["karta_dodavatele_kandidat"] = info["karta_dodavatele_kandidat"]
        ver = np.concatenate([_poly(t)[0] for t in tv])
        box["obalka"] = {"min": ver.min(0), "max": ver.max(0)}
        res["boxy"].append(box)
        for t in tv:
            t["vlastnik"] = box["id"]
            res["tvary"].append(t)

    # --- vodorovná řada: jen opora --------------------------------------------------------------
    if theta == 0.0:
        vs = np.concatenate([_verts_obb(t) for t in res["tvary"]])
        res["opory"].append({
            "rada": rid, "patro": pid, "typ": "deska",
            "min": [float(vs[:, 0].min()), float(vs[:, 2].min())],
            "max": [float(vs[:, 0].max()), float(vs[:, 2].max())],
            "y": float(r["y"]),
            "poznamka": "Vodorovná řada leží na desce rámu (řeší rám); horní plocha desky = y.",
        })
        if p["deska_mm"] > 0:
            res["tvary"].append(fr.obb(0, L, 0, b, -p["deska_mm"], 0, rodic="deska", vlastnik=rid + "#deska"))
        return res

    # --- skloněná řada: dráhy + koncovky ---------------------------------------------------------
    dr = int(p["draha"])
    dcfg = DILY[dr]
    M_mod = dcfg["delka"]
    zasun = float(p["zasun_draha_mm"])
    kapsa = float(p["kapsa_hloubka_mm"])
    ts = float(p["hrubka_zarazky_mm"])
    cd, cu = DILY[5282], DILY[5281]
    Lp = cd["delka"]
    hak_pul = (Lp - kapsa) / 2.0          # osa trubky od vnějšího konce plechu
    if zasun > kapsa + 1e-9:
        res["problemy"].append({"kod": "ZASUN_VETSI_NEZ_KAPSA", "uroven": "chyba", "id": [rid],
                                "text": "Zasunutí dráhy %.2f mm je větší než hloubka kapsy %.2f mm." % (zasun, kapsa)})
    # dolní plech: otvor kapsy (vnitřní konec) v s = 0 (zarazka_u = kapsa), nebo zarážka u háku
    if p["zarazka_u"] == "kapsa":
        sp0_d = -Lp                       # vnější (hákový) konec
    else:
        sp0_d = -ts
    sp_in_d = sp0_d + Lp                 # otvor kapsy
    s_rs = sp_in_d - zasun               # začátek soustavy modulů
    # počet modulů: viditelná část dráhy (mezi otvory kapes) musí pokrýt řadu
    # dráha musí sahat od s_rs do s_re, otvor horní kapsy sp_in_u = s_re - zasun >= L
    m = max(1, math.ceil((L + zasun - s_rs - 1e-9) / M_mod))
    s_re = s_rs + m * M_mod
    sp_in_u = s_re - zasun
    sp1_u = sp_in_u + Lp                 # vnější (hákový) konec horního plechu
    s_tl = sp0_d + hak_pul
    s_tu = sp1_u - hak_pul
    h_t = -hak_pul
    res["geom_draha"] = {"moduly": m, "s_zacatek": s_rs, "s_konec": s_re, "delka_celkem": m * M_mod,
                         "sp0_d": sp0_d, "sp_in_d": sp_in_d, "sp_in_u": sp_in_u, "sp1_u": sp1_u,
                         "s_trubka_dole": s_tl, "s_trubka_nahore": s_tu, "h_trubky": h_t,
                         "vzdalenost_trubek": s_tu - s_tl, "viditelna_delka": sp_in_u - sp_in_d}
    roztec = p["roztec_drah_mm"]
    roztec_auto = roztec is None
    if roztec_auto:
        roztec = _roztec_vychozi(p["draha"], typ, smer, p)
    roztec = float(roztec)
    res["roztec"] = roztec
    res["roztec_auto"] = roztec_auto
    tc = b / 2
    w = dcfg["sirka"]
    wp = cd["sirka"]
    pasy = []
    for k, tk in enumerate((tc - roztec / 2, tc + roztec / 2)):
        vnejsi = -1.0 if k == 0 else 1.0        # směr "ven" (po ose c)
        moduly = []
        for j in range(m):
            sa, sb = s_rs + j * M_mod, s_rs + (j + 1) * M_mod
            tv = [fr.obb(sa, sb, tk - w / 2, tk + w / 2, -dcfg["pod"], 0.0, rodic="draha", nazev="telo")]
            if dcfg["doraz"]:
                if vnejsi < 0:
                    t0, t1 = tk - w / 2, tk - w / 2 + HRANA_BOCNIHO_DORAZU
                else:
                    t0, t1 = tk + w / 2 - HRANA_BOCNIHO_DORAZU, tk + w / 2
                tv.append(fr.obb(sa, sb, t0, t1, 0.0, dcfg["nad"], rodic="draha", nazev="boc_doraz"))
            # orientace: stran dorazu = lokální +napříč (neověřeno); volba směru podél pro vnější doraz
            d_part = fr.d
            if dcfg["doraz"]:
                # lokální +napříč = nahoru x podél => chceme, aby mířil "ven"
                if np.dot(np.cross(fr.n, d_part), vnejsi * fr.c) < 0:
                    d_part = -fr.d
            stred = fr.bod((sa + sb) / 2, tk, (dcfg["nad"] - dcfg["pod"]) / 2)
            pos, q, Mx = _pose_dil(d_part, fr.n, None, dcfg, stred)
            mod = {"part_id": dr, "sku": dcfg["sku"], "index": j + 1, "s_od": sa, "s_do": sb,
                   "position": pos, "quaternion": q, "scale": [1.0, 1.0, 1.0],
                   "tvary_nahrady": [{"stred": t["c"], "osy": t["u"], "pul": t["h"]} for t in tv],
                   "neoverene": True}
            moduly.append(mod)
            for t in tv:
                t["vlastnik"] = "%s/draha%d/m%d" % (rid, k + 1, j + 1)
                t["pas"] = k
                t["modul"] = j
                res["tvary"].append(t)
        pasy.append({"index": k + 1, "t": tk, "moduly": moduly})
        # koncovky
        for role, cfg, sp_in, smer_ven in (("dolni", cd, sp_in_d, -1.0), ("horni", cu, sp_in_u, 1.0)):
            sp_out = sp_in + smer_ven * Lp          # vnější (hákový) konec
            sa, sb = min(sp_in, sp_out), max(sp_in, sp_out)
            tv = [fr.obb(sa, sb, tk - wp / 2, tk + wp / 2, -cfg["pod"], 0.0, rodic="koncovka", nazev="zaklad")]
            if role == "dolni":
                if p["zarazka_u"] == "kapsa":
                    z0, z1 = sp_in - ts, sp_in
                else:
                    z0, z1 = sp_out, sp_out + ts
                tv.append(fr.obb(z0, z1, tk - wp / 2, tk + wp / 2, 0.0, cfg["nad"], rodic="koncovka", nazev="zarazka"))
            # lokální +podél směřuje od háku ke kapse
            d_part = fr.d if role == "dolni" else -fr.d
            vys_c = (cfg["nad"] - cfg["pod"]) / 2
            stred = fr.bod((sa + sb) / 2, tk, vys_c)
            pos, q, Mx = _pose_dil(d_part, fr.n, None, cfg, stred)
            idk = "%s/koncovka_%s%d" % (rid, role, k + 1)
            ko = {"id": idk, "rada": rid, "patro": pid, "pas": k + 1, "role": role,
                  "part_id": 5282 if role == "dolni" else 5281,
                  "sku": cfg["sku"], "position": pos, "quaternion": q, "scale": [1.0, 1.0, 1.0],
                  "tvary_nahrady": [{"stred": t["c"], "osy": t["u"], "pul": t["h"]} for t in tv],
                  "s_otvor_kapsy": sp_in, "s_hak": sp_out, "neoverene": True}
            res["koncovky"].append(ko)
            for t in tv:
                t["vlastnik"] = idk
                t["koncovka_role"] = role
                t["pas"] = k
                res["tvary"].append(t)
    res["draha"] = {
        "rada": rid, "patro": pid, "part_id": dr, "sku": dcfg["sku"], "moduly_na_pas": m, "pasy": pasy,
        "delka_celku_mm": m * M_mod, "viditelna_delka_mm": sp_in_u - sp_in_d,
        "zasun_draha_mm": zasun, "roztec_mm": roztec, "roztec_vychozi": roztec_auto,
        "vzdalenost_trubek_mm": s_tu - s_tl,
        "spoj_modulu": "na sraz, bez spojky (neověřeno)",
    }
    # kotvení pro nosníky: osa trubky v rámu řady
    res["trubka_dole"] = (s_tl, h_t)
    res["trubka_nahore"] = (s_tu, h_t)
    res["plech_t_rozsah"] = (tc - roztec / 2 - wp / 2, tc + roztec / 2 + wp / 2)
    res["draha_t_rozsah"] = (tc - roztec / 2 - w / 2, tc + roztec / 2 + w / 2)
    # kontrola opory: dráha musí ležet pod nožkou
    nz = nz_ac_d
    for k, tk in enumerate((tc - roztec / 2, tc + roztec / 2)):
        prekryv = min(tk + w / 2, tc + nz / 2) - max(tk - w / 2, tc - nz / 2)
        if prekryv < 10.0:
            res["problemy"].append({"kod": "DRAHA_MIMO_OPORU", "uroven": "chyba", "id": [rid],
                                    "text": "Dráha %d leží pod nožkou boxu jen %.1f mm (box není podepřen)." % (k + 1, max(prekryv, 0))})
    if roztec < w:
        res["problemy"].append({"kod": "DRAHY_SE_PROLINAJI", "uroven": "chyba", "id": [rid],
                                "text": "Rozteč drah %.1f mm je menší než šířka dráhy %.1f mm." % (roztec, w)})
    return res


# ---------------------------------------------------------------------------------------------
# NOSNÍKY
# ---------------------------------------------------------------------------------------------
def _nosniky(rady, p):
    skupiny = {}
    for r in rady:
        if r["draha"] is None:
            continue
        fr = r["fr"]
        for role, klic in (("dolni", "trubka_dole"), ("horni", "trubka_nahore")):
            s_t, h_t = r[klic]
            # poloha osy trubky: bod v rámu řady při t = 0 => vezmeme jen složku podél a výšku
            bod = fr.bod(s_t, 0.0, h_t)
            klic_s = (r["patro"], role, round(float(bod[fr.os_idx]), 2), round(float(bod[1]), 2))
            skupiny.setdefault(klic_s, []).append((r, bod))
    out = []
    for (patro, role, _, _), cl in sorted(skupiny.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        r0, bod = cl[0]
        fr = r0["fr"]
        lo, hi = np.inf, -np.inf
        for r, b_ in cl:
            t0, t1 = r["plech_t_rozsah"]
            ac0 = r["fr"].P0[fr.os_napric]
            lo = min(lo, ac0 + t0)
            hi = max(hi, ac0 + t1)
        lo -= p["presah_nosniku_mm"]
        hi += p["presah_nosniku_mm"]
        a_ = bod.copy()
        b_ = bod.copy()
        a_[fr.os_napric] = lo
        b_[fr.os_napric] = hi
        out.append({
            "id": "nosnik_%s_%s_%d" % (role, patro, len(out) + 1), "role": role, "patro": patro,
            "a": a_, "b": b_, "polomer": R_TRUBKY, "prumer": 2 * R_TRUBKY, "part_id": 3673,
            "rady": [r["id"] for r, _ in cl], "osa_napric": "x" if fr.os_napric == 0 else "z",
        })
    return out


def _tvar_nosniku(nz):
    a = np.asarray(nz["a"], float)
    b = np.asarray(nz["b"], float)
    return {"typ": "cyl", "c": (a + b) / 2, "a": b - a, "r": nz["polomer"], "hl": float(np.linalg.norm(b - a)) / 2,
            "vlastnik": nz["id"], "rodic": "nosnik", "rady": nz["rady"]}


# ---------------------------------------------------------------------------------------------
# VÝŠKOVÁ MEZERA
# ---------------------------------------------------------------------------------------------
def _interval_y(o, X, Z):
    """Svislá přímka (x, z): interval y uvnitř tělesa (nan pokud mimo). X, Z jsou 1D pole."""
    if o["typ"] == "obb":
        lo = np.full(X.shape, -np.inf)
        hi = np.full(X.shape, np.inf)
        for u, h in zip(o["u"], o["h"]):
            base = (X - o["c"][0]) * u[0] + (Z - o["c"][2]) * u[2] - o["c"][1] * u[1]
            # |base + y*u1| <= h
            if abs(u[1]) < 1e-12:
                bad = np.abs(base) > h
                lo = np.where(bad, np.inf, lo)
                hi = np.where(bad, -np.inf, hi)
            else:
                y1 = (-h - base) / u[1]
                y2 = (h - base) / u[1]
                lo = np.maximum(lo, np.minimum(y1, y2))
                hi = np.minimum(hi, np.maximum(y1, y2))
        bad = lo > hi
        return np.where(bad, np.nan, lo), np.where(bad, np.nan, hi)
    a = _unit(o["a"])
    cx, cy, cz = o["c"]
    # q(y) = (X-cx, y-cy, Z-cz); radiální složka: q - (q.a) a
    ex = np.array([1.0, 0, 0])
    ey = np.array([0, 1.0, 0])
    ez = np.array([0, 0, 1.0])
    q0 = np.stack([X - cx, np.full(X.shape, -cy), Z - cz], -1)
    # r(y) = P (q0 + y ey) kde P = I - a a^T
    P = np.eye(3) - np.outer(a, a)
    r0 = q0 @ P.T
    r1 = P @ ey
    A = float(r1 @ r1)
    B = 2 * (r0 @ r1)
    C = (r0 * r0).sum(-1) - o["r"] ** 2
    if A < 1e-12:
        ok = C <= 0
        lo = np.full(X.shape, -np.inf)
        hi = np.full(X.shape, np.inf)
    else:
        disc = B * B - 4 * A * C
        ok = disc >= 0
        sq = np.sqrt(np.where(ok, disc, 0))
        lo = (-B - sq) / (2 * A)
        hi = (-B + sq) / (2 * A)
    # axiální omezení |q.a| <= hl
    qa0 = q0 @ a
    if abs(a[1]) < 1e-12:
        ok &= np.abs(qa0) <= o["hl"]
    else:
        y1 = (-o["hl"] - qa0) / a[1]
        y2 = (o["hl"] - qa0) / a[1]
        lo = np.maximum(lo, np.minimum(y1, y2))
        hi = np.minimum(hi, np.maximum(y1, y2))
        ok &= lo <= hi
    return np.where(ok, lo, np.nan), np.where(ok, hi, np.nan)


def _mezera_vyska(horni_tvary, dolni_tvary, krok):
    """Nejmenší výšková vzdálenost: nejnižší bod `horni_tvary` nad nejvyšším bodem `dolni_tvary`
    na stejné svislici (x, z). inf = žádný společný půdorys."""
    if not horni_tvary or not dolni_tvary:
        return math.inf
    bh = [_aabb(t) for t in horni_tvary]
    bd = [_aabb(t) for t in dolni_tvary]
    xmin = max(min(b[0][0] for b in bh), min(b[0][0] for b in bd))
    xmax = min(max(b[1][0] for b in bh), max(b[1][0] for b in bd))
    zmin = max(min(b[0][2] for b in bh), min(b[0][2] for b in bd))
    zmax = min(max(b[1][2] for b in bh), max(b[1][2] for b in bd))
    if xmin >= xmax or zmin >= zmax:
        return math.inf
    xs = np.arange(xmin, xmax + krok / 2, krok)
    zs = np.arange(zmin, zmax + krok / 2, krok)
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    X, Z = XX.ravel(), ZZ.ravel()
    nizky = np.full(X.shape, np.inf)
    vysoky = np.full(X.shape, -np.inf)
    for (lo_, hi_), t in zip(bh, horni_tvary):
        m = (X >= lo_[0]) & (X <= hi_[0]) & (Z >= lo_[2]) & (Z <= hi_[2])
        if m.any():
            y0, _ = _interval_y(t, X[m], Z[m])
            cur = nizky[m]
            nizky[m] = np.where(np.isnan(y0), cur, np.minimum(cur, np.where(np.isnan(y0), np.inf, y0)))
    for (lo_, hi_), t in zip(bd, dolni_tvary):
        m = (X >= lo_[0]) & (X <= hi_[0]) & (Z >= lo_[2]) & (Z <= hi_[2])
        if m.any():
            _, y1 = _interval_y(t, X[m], Z[m])
            cur = vysoky[m]
            vysoky[m] = np.where(np.isnan(y1), cur, np.maximum(cur, np.where(np.isnan(y1), -np.inf, y1)))
    ok = np.isfinite(nizky) & np.isfinite(vysoky)
    if not ok.any():
        return math.inf
    return float((nizky[ok] - vysoky[ok]).min())


# ---------------------------------------------------------------------------------------------
# HLAVNÍ FUNKCE
# ---------------------------------------------------------------------------------------------
def _sestav(spec):
    p = _parametry(spec)
    rady = []
    ids = set()
    for r in spec.get("rady", []):
        if str(r["id"]) in ids:
            raise ValueError("duplicitní id řady: %s" % r["id"])
        ids.add(str(r["id"]))
        rady.append(_stavba_rady(r, spec, p, None))
    nos = _nosniky(rady, p)
    return p, rady, nos


def _tvary_patra(rady, nosniky, patro, jen_boxy=False):
    out = []
    for r in rady:
        if r["patro"] != patro:
            continue
        for t in r["tvary"]:
            if jen_boxy and t.get("rodic") != "box":
                continue
            out.append(t)
    if not jen_boxy:
        for nz in nosniky:
            if nz["patro"] == patro:
                out.append(_tvar_nosniku(nz))
    return out


def _vyska_patra_a_mezera(spec, patro_dole, patro_nahore):
    p, rady, nos = _sestav(spec)
    h = _tvary_patra(rady, nos, patro_nahore)
    d = _tvary_patra(rady, nos, patro_dole, jen_boxy=True)
    return _mezera_vyska(h, d, float(p["mrizka_mezery_mm"])), rady


def min_vyska_patra(spec, patro_dole, patro_nahore, mezera_mm=0.0):
    """Nejmenší `y` řad patra `patro_nahore`, aby výšková vzdálenost mezi horním okrajem boxů patra
    `patro_dole` a nejnižším dílem patra `patro_nahore` (dráha, plech, nosník, u vodorovné řady spodek
    boxu / desky) byla alespoň `mezera_mm`. Vrací slovník:
      mezera_ted_mm  aktuální (nejmenší přes celý půdorys; inf = patra se nepřekrývají v půdoryse)
      posun_y_mm     o kolik je třeba horní patro posunout nahoru (záporné = dolů lze)
      y_min          {id_rady: minimální y}
    Přesnost: vzorkování půdorysu po `mrizka_mezery_mm` (skloněné plochy: chyba <= krok*tan(sklon))."""
    g, rady = _vyska_patra_a_mezera(spec, patro_dole, patro_nahore)
    y_min = {}
    if math.isinf(g):
        for r in rady:
            if r["patro"] == patro_nahore:
                y_min[r["id"]] = float(r["fr"].P0[1])
        return {"mezera_ted_mm": None, "posun_y_mm": 0.0, "y_min": y_min,
                "poznamka": "Patra se v půdoryse nepřekrývají, výška není omezena."}
    delta = float(mezera_mm) - g
    for r in rady:
        if r["patro"] == patro_nahore:
            y_min[r["id"]] = float(r["fr"].P0[1]) + delta
    return {"mezera_ted_mm": g, "posun_y_mm": delta, "y_min": y_min}


def postav(spec):
    p, rady, nos = _sestav(spec)
    tol = float(p["tolerance_kolize_mm"])
    problemy = []
    for r in rady:
        problemy.extend(r["problemy"])

    # --- sklony -------------------------------------------------------------------------------
    smin, smax = p["sklon_doporuceny_deg"]
    for r in rady:
        th = r["theta"]
        if th < 0 or th >= 45:
            problemy.append({"kod": "SKLON_NEPLATNY", "uroven": "chyba", "id": [r["id"]],
                             "text": "Sklon %.2f° je mimo 0 až 45° (nižší konec se volí parametrem nizsi_konec)." % th})
        elif 0 < th and (th < smin or th > smax):
            problemy.append({"kod": "SKLON_MIMO_ROZSAH", "uroven": "varovani", "id": [r["id"]],
                             "text": "Sklon %.2f° je mimo doporučených %.1f až %.1f° (neověřeno)." % (th, smin, smax)})
        if th == 0:
            problemy.append({"kod": "VODOROVNA_RADA_NA_DESCE", "uroven": "info", "id": [r["id"]],
                             "text": "Vodorovná řada: bez drah, box leží na desce rámu (viz `opory`)."})
    # --- patra: stejná výška a sklon ------------------------------------------------------------
    pat = {}
    for r in rady:
        pat.setdefault(r["patro"], []).append(r)
    for pid, rr in sorted(pat.items()):
        ys = {round(float(r["fr"].P0[1]), 2) for r in rr}
        ths = {round(r["theta"], 4) for r in rr}
        if len(ys) > 1 or len(ths) > 1:
            problemy.append({"kod": "PATRO_NESEDI", "uroven": "varovani", "id": [r["id"] for r in rr],
                             "text": "Řady patra %s nemají stejnou výšku (%s) nebo sklon (%s); společný dolní nosník "
                                     "se pak nesdílí." % (pid, sorted(ys), sorted(ths))})
    # --- mezery pater ----------------------------------------------------------------------------
    pids = sorted(pat)
    mezery = []
    for i, pa in enumerate(pids):
        for pb in pids[i + 1:]:
            ya = min(r["fr"].P0[1] for r in pat[pa])
            yb = min(r["fr"].P0[1] for r in pat[pb])
            if abs(ya - yb) < 1e-9:
                continue
            dole, nahore = (pa, pb) if ya < yb else (pb, pa)
            g = _mezera_vyska(_tvary_patra(rady, nos, nahore), _tvary_patra(rady, nos, dole, jen_boxy=True),
                              float(p["mrizka_mezery_mm"]))
            if math.isinf(g):
                continue
            mezery.append({"dole": dole, "nahore": nahore, "mezera_mm": g})
            if g < p["min_mezera_pater_mm"]:
                problemy.append({"kod": "MALA_MEZERA_PATER", "uroven": "varovani" if g >= 0 else "chyba",
                                 "id": [dole, nahore],
                                 "text": "Výšková mezera mezi patrem %s (horní okraj boxů) a patrem %s (nejnižší díl) "
                                         "je %.1f mm (minimum %.1f)." % (dole, nahore, g, p["min_mezera_pater_mm"])})
    # --- kolize -----------------------------------------------------------------------------------
    tvary = []
    for r in rady:
        tvary.extend(r["tvary"])
    for nz in nos:
        tvary.append(_tvar_nosniku(nz))
    aabbs = [_aabb(t) for t in tvary]

    def vyjimka(A, B):
        # záměrné styky: koncovka s vlastní dráhou (zasunutí do kapsy) a s vlastním nosníkem (hák)
        for X, Y in ((A, B), (B, A)):
            if X.get("rodic") == "koncovka":
                if Y.get("rodic") == "draha" and Y["vlastnik"].split("/")[0] == X["vlastnik"].split("/")[0] \
                        and Y.get("pas") == X.get("pas"):
                    return True
                if Y.get("rodic") == "nosnik" and X["vlastnik"].split("/")[0] in Y["rady"]:
                    return True
        return False

    kolize = {}
    for i in range(len(tvary)):
        lo1, hi1 = aabbs[i]
        for j in range(i + 1, len(tvary)):
            lo2, hi2 = aabbs[j]
            if np.any(lo1 > hi2 - tol) or np.any(lo2 > hi1 - tol):
                continue
            A, B = tvary[i], tvary[j]
            if A["vlastnik"] == B["vlastnik"]:
                continue
            if vyjimka(A, B):
                continue
            hl = _sat_hloubka(A, B)
            if hl > tol:
                kolize[(A["vlastnik"], B["vlastnik"])] = max(hl, kolize.get((A["vlastnik"], B["vlastnik"]), 0))
    for (a_, b_), hl in sorted(kolize.items()):
        problemy.append({"kod": "KOLIZE", "uroven": "chyba", "id": [a_, b_],
                         "text": "Průnik %s a %s (hloubka %.2f mm)." % (a_, b_, hl)})
    # --- různé -------------------------------------------------------------------------------------
    vsechny = [v for t in tvary for v in [_poly(t)[0]]]
    if vsechny:
        V = np.concatenate(vsechny)
        mn, mx = V.min(0), V.max(0)
    else:
        mn = mx = np.zeros(3)
    if mn[1] < -1e-6:
        problemy.append({"kod": "POD_PODLAHOU", "uroven": "varovani", "id": [],
                         "text": "Nejnižší bod konstrukce je %.1f mm pod podlahou (y=0)." % mn[1]})
    if p["max_rozpeti_mm"] is not None:
        for r in rady:
            if r["draha"] and r["draha"]["vzdalenost_trubek_mm"] > p["max_rozpeti_mm"]:
                problemy.append({"kod": "ROZPETI_DRAHY", "uroven": "varovani", "id": [r["id"]],
                                 "text": "Dráha je mezi trubkami %.0f mm, limit %.0f mm." % (
                                     r["draha"]["vzdalenost_trubek_mm"], p["max_rozpeti_mm"])})
    if any(r["draha"] for r in rady):
        problemy.append({"kod": "DILY_NEOVERENO", "uroven": "info", "id": [], "text": NEOVERENO})
        if any(r["draha"]["moduly_na_pas"] > 1 for r in rady if r["draha"]):
            problemy.append({"kod": "SPOJ_MODULU_NEOVERENO", "uroven": "info", "id": [],
                             "text": "Moduly dráhy jsou na sraz; způsob spojení modulů není z podkladů známý."})

    vysl = {
        "verze": VERZE,
        "jednotky": "mm",
        "parametry": p,
        "rady": [{"id": r["id"], "patro": r["patro"], "typ": r["typ"], "smer": r["smer"], "vyska": r["vyska"],
                  "pocet": r["n"], "sklon_deg": r["theta"], "delka_rady_mm": r["L"],
                  "nizsi_konec": p["nizsi_konec"], "osa_rady": p["osa_rady"],
                  "vektor_podel": r["fr"].d, "vektor_kolmo": r["fr"].n, "vektor_napric": r["fr"].c,
                  "roztec_drah_mm": r.get("roztec"), "zacatek": r["fr"].P0}
                 for r in rady],
        "boxy": [b for r in rady for b in r["boxy"]],
        "draha": [r["draha"] for r in rady if r["draha"]],
        "koncovky": [k for r in rady for k in r["koncovky"]],
        "nosniky": nos,
        "opory": [o for r in rady for o in r["opory"]],
        "mezery_pater": mezery,
        "rozmery": {"min": mn, "max": mx, "velikost": mx - mn},
        "problemy": problemy,
    }
    return _zaokr(vysl)


# ---------------------------------------------------------------------------------------------
# KOPÍROVÁNÍ ŘAD
# ---------------------------------------------------------------------------------------------
def _rozsah_napric(spec, id_rady):
    """(min, max) souřadnice napříč přes všechny díly řady (boxy, dráhy, koncovky; bez nosníků)."""
    s1 = copy.deepcopy(spec)
    s1["rady"] = [r for r in s1["rady"] if str(r["id"]) == str(id_rady)]
    if not s1["rady"]:
        raise ValueError("řada %r neexistuje" % id_rady)
    s1["patra"] = spec.get("patra")
    p, rady, _ = _sestav(s1)
    r = rady[0]
    ax = r["fr"].os_napric
    V = np.concatenate([_poly(t)[0] for t in r["tvary"]])
    return float(V[:, ax].min()), float(V[:, ax].max()), ax


def kopie_rady(spec, id_rady, kam, mezera_mm, pocet=1, sklon_deg=None, patro=None):
    """Vrátí NOVÝ spec s `pocet` kopiemi řady `id_rady`.
    kam="vedle": kopie ve stejném patře, posun napříč tak, aby čistá vzdálenost mezi konstrukcí
        (box, dráha, koncovka) sousedních řad byla `mezera_mm` (nosník je společný, nepočítá se).
    kam="nad": kopie v novém patře (stejný půdorys a sklon); výšková mezera mezi horním okrajem boxů
        spodního patra a nejnižším dílem horního patra (nejmenší přes celý půdorys) je `mezera_mm`.
    Kopie se řetězí (druhá se měří od první).
    sklon_deg (jen kam="nad"): sklon nového patra (jinak stejný jako u zdroje).
    patro (jen kam="nad", pocet=1): jméno nového patra (jinak "<patro zdroje>+k"). Další řady téhož
        patra se pak přidají kopií kam="vedle".
    Mezera "nad" závisí na dráze zadané ve `spec` (klíč draha) a na jejím sklonu."""
    if sklon_deg is not None and kam != "nad":
        raise ValueError("sklon_deg lze zadat jen pro kam=\"nad\" (řady jednoho patra mají stejnou výšku a sklon)")
    if kam not in ("vedle", "nad"):
        raise ValueError('kam musí být "vedle" nebo "nad"')
    if patro is not None and (kam != "nad" or int(pocet) != 1):
        raise ValueError('patro lze zadat jen pro kam="nad" a pocet=1')
    novy = copy.deepcopy(spec)
    zdroj = next((r for r in novy["rady"] if str(r["id"]) == str(id_rady)), None)
    if zdroj is None:
        raise ValueError("řada %r neexistuje" % id_rady)
    p = _parametry(spec)
    existujici = {str(r["id"]) for r in novy["rady"]}
    pred = copy.deepcopy(zdroj)
    for k in range(1, int(pocet) + 1):
        nova = copy.deepcopy(pred)
        i = k
        while "%s-%d" % (id_rady, i) in existujici:
            i += 1
        nova["id"] = "%s-%d" % (id_rady, i)
        existujici.add(nova["id"])
        if kam == "vedle":
            mn, mx, ax = _rozsah_napric(novy, pred["id"])
            nova["x" if ax == 0 else "z"] = float(pred["x" if ax == 0 else "z"]) + (mx - mn) + float(mezera_mm)
        else:
            patro_dole = _patro_id(pred)
            theta = _sklon_rady(pred, novy, p) if sklon_deg is None else float(sklon_deg)
            nove_patro = str(patro) if patro is not None else "%s+%d" % (_patro_id(zdroj), k)
            if patro is not None and nove_patro in {_patro_id(r) for r in novy["rady"]}:
                raise ValueError("patro %r už existuje" % nove_patro)
            while nove_patro in {_patro_id(r) for r in novy["rady"]}:
                nove_patro += "'"
            nova["patro"] = nove_patro
            novy.setdefault("patra", {})
            novy["patra"] = dict(novy["patra"] or {})
            novy["patra"][nove_patro] = {"sklon_deg": theta}
            nova.pop("sklon_deg", None)
            nova["y"] = float(pred["y"]) + 1000.0       # provizorně nad, pak se přesně dopočte
            novy["rady"].append(nova)
            vys = min_vyska_patra(novy, patro_dole, nove_patro, mezera_mm)
            novy["rady"].remove(nova)
            nova["y"] = vys["y_min"][nova["id"]] if vys["mezera_ted_mm"] is not None else float(pred["y"]) + 1000.0
        novy["rady"].append(nova)
        pred = nova
    return novy
