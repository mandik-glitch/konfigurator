#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3d_mark.py - neviditelna forenzni znacka v zakaznickem GLB 3D nabidky
(bot10, 2026-10-02; Robert: stupen 2 ochrany 3D modelu sestav = "razitko
s unikatni znackou vazanou na nabidku"). Znacka nese cislo nabidky
(scene_offers.id) a umi se z uniklého GLB precist. NENI to ochrana rozmeru
(ta je v tom, ze se geometrie nedava ven) - je to stopa puvodu.

Zavislosti: numpy (api/venv/bin/python ho ma - overeno numpy 2.5.1), jinak
standardni knihovna + api/v3d_glb.py. Rezim "s originalem" navic pouziva
scipy.spatial.cKDTree (venv ma scipy 1.18; importuje se az tam).

VEREJNE FUNKCE
  mark(glb, offer_id, secret, *, verify=True) -> bytes
  mark_report(...)                            -> (bytes, report)
  mark_offer_model(glb, offer_id, flask_secret_key=None, env=None)   (vstup pro api/scene_offers.py)
  detect(glb, secret, kandidati=None, original=None) -> (offer_id|None, jistota)
  detect_report(...)                          -> dict (podrobnosti)
  detect_points(P, secret, kandidati, original_points, frames=True)  (body [N,3], napr. z OBJ/STL)
  world_points(glb) / points_from_obj(text) / points_from_stl(bytes) -> ndarray [N,3]
  derive_secret(flask_secret_key) / get_secret(env, flask_secret_key)
Chyby jsou ValueError (v3d_glb.V3DError je podtrida) - znacka se nikdy tise nevynecha.

JEDNOTKY (overeno): spec.u == "mm" (v3d_glb.validate_spec to vynucuje), model sestavy je
~480 x 1700 x 2400 mm, souradnice v GLB jsou tedy MILIMETRY (ne metry jako v glTF specifikaci).

SCHEMA (verze 1) - kvantizacni index modulace (QIM) na klicovane mrizce
  Znacka = 72 bitu: 32 b cislo nabidky + 40 b HMAC-SHA256(K_tag, id)[:5]. Z `secret` se HMAC-em
  odvodi K_grid, K_tag a posun mrizky (kazdy podklic zvlast, jmeno nese "v3d-mark/v1").
  1. Pracuje se v SVETOVYCH souradnicich (soucin matic uzlu, mm). Posun se zapise zpet do
     lokalnich souradnic meshe pres inverzni matici uzlu (testovano i s rotaci, nerovnomernym
     meritkem a zrcadlenim). Mesh pouzity vic uzly s ruznou polohou se neznaci (neslo by to).
  2. Prostor je rozdelen na kostky (bunky) o hrane CELL = 2 mm s klicovanou pocatecni polohou.
     Vrchol se znaci JEN kdyz lezi >= M_EMB (0.07 mm) od steny sve bunky na vsech osach - pak se
     bunka nezmeni ani po posunu (<= 0.045 mm) a po sumu. Zbytek vrcholu (u skutecnych karet
     14-32 %) zustane BEZE ZMENY.
  3. Z bunky vypocte BLAKE2b(K_grid) osu a (0..2), index bitu j (0..71) a dither d. Souradnice
     vrcholu na ose a se pritahne k nejblizsimu bodu mrizky d + DELTA*(k + b/2), b = j-ty bit kodu.
     DELTA = 0.09 mm -> posun <= 0.045 mm (< 0.05 mm), druha mrizka je o 0.045 mm vedle. Meni se
     JEN POSITION (float32) a min/max jeho accessoru; indexy, topologie, normaly, JSON a vsechny
     ostatni bajty zustavaji. Vrcholy o stejne poloze (kopie u plocheho stinovani) dostanou stejny
     posun, takze se netrhaji hrany ani kontakty mezi dily.
  4. Cteni BEZ originalu: bunka kazdeho vrcholu je dana jeho vlastni polohou -> zmeri se, ke ktere
     ze dvou mrizek je souradnice blize -> hlas (-1..+1) pro bit j; hlasy se prumeruji po bunkach
     (jedna bunka = jeden hlas), scitaji po bitech; kod overi HMAC (pripadne oprava az 12 nejmene
     spolehlivych bitu). Jistota = 1 - (pocet zkousek * 2^-40). Bez platneho HMAC: pokud jsou
     kandidati, matched filter na kod kazdeho kandidata (z-skore, p <= 1e-6 po korekci).
  5. Pri nezdaru: (a) hledani soustavy = jednotky (mm/cm/m/palce/stopy) a 24 otoceni o nasobky
     90 st. BEZ posunu (Z-up exporty, STL, scena zmensena na metry); (b) s `original`
     (nemarkovany GLB teze karty): registrace na original (podobnost: posun + libovolne otoceni +
     jednotne meritko, PCA + ICP) a cteni skutecneho posunu vrcholu oproti originalu.

OMEZENI (vse overeno testy v tests/test_mark.py, tabulka odolnosti)
  - BEZ originalu se cte jen v soustave souboru (az na jednotky a otoceni o 90 st., bez posunu).
    Posun, libovolne otoceni, meritko kolem jineho bodu nez pocatek: bez originalu znacku NEPRECTE.
    S originalem ano (cely model).
  - Orez + transformace zaroven: registrace (PCA) predpoklada cely model; pri orezu ~50 % selhava
    (zalezi na karte); orez bez transformace staci (>= ~100-200 bunek = jeden vetsi dil).
  - Sum: bez originalu do cca sigma 0.03 mm (gauss), s kandidaty o malo vic, s originalem do cca
    0.04-0.06 mm. Zaokrouhleni souradnic: bez originalu do 0.05 mm, s originalem prezije i 0.1-0.2 mm
    (host je z vetsiny mimo mrizku; kdyby sestava lezela cela na mrizce 0.1 mm, zmizi).
  - Znacku zničí: svar vrcholu s prahem > ~0.05 mm, remesh, hrubsi decimace, sum >= 0.04 mm,
    novy export z jineho CAD s prepoctem sit. Decimace 0.5 a svar 0.1 mm v Blenderu ji NEznici
    (zbyle puvodni vrcholy drzi polohu).
  - Kolize: kdo dostane DVE kopie teze karty (ruzne nabidky) vidi, ve kterych vrcholech se lisi
    (zmereno cca 28 %). Prumer obou kopii (zmereno na karte 4918) se da stale precist matched
    filtrem: obe nabidky maji stejne z-skore 6.85 (cizi id 4.23), detect_report vsak vraci jen jednu
    z nich (nejlepsi) - u podezreni na kolizi projit kandidaty rucne. Jine utoky vice kopiemi
    (nahodne michani dilu z obou kopii apod.) nejsou testovany.
  - jistota znamena "pravdepodobnost, ze to neni nahoda"; neni to dukaz proti cilene padelane
    znacce bez znalosti klice (klic ma jen server). K_grid je pro vsechny nabidky stejny, kod se
    lisi jen v hodnote bitu (aby slo cist BEZ znalosti cisla nabidky); pokud by unikl klic, lze
    znacku podvrhnout i odstranit.
  - Klic musi zustat zachovan po celou dobu zivota modelu (na Sdilenem disku se model pri smazani
    nabidky nemaze). Zmena FLASK_SECRET_KEY zmeni odvozeny klic a stare znacky se prestanou cist ->
    nastavit V3D_MARK_SECRET (viz get_secret) a zalohovat.
"""

import hashlib
import hmac
import math
import os
import re
import struct
import sys

try:
    import numpy as np
except ImportError as _e:                                   # pragma: no cover
    raise ImportError("v3d_mark.py potrebuje numpy (api/venv/bin/python ho ma)") from _e

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v3d_glb  # noqa: E402
from v3d_glb import V3DError  # noqa: E402

__all__ = [
    "mark", "mark_report", "mark_offer_model", "detect", "detect_report", "detect_points", "world_points",
    "points_from_obj", "points_from_stl", "derive_secret", "get_secret", "V3DError",
    "VERZE", "DELTA", "CELL", "MAX_SHIFT_MM", "ID_BITS", "TAG_BITS", "CODE_BITS",
]

# ---------------------------------------------------------------------------
# Parametry schematu (zmena = nova VERZE; detect je k nim pevne vazan)
# ---------------------------------------------------------------------------
VERZE = 1
DELTA = 0.09            # mm, perioda QIM mrizky; max posun = DELTA / 2
MAX_SHIFT_MM = 0.05     # tvrda horni mez posunu vrcholu (zadani: < 0.05 mm)
CELL = 2.0              # mm, hrana bunky identity
M_EMB = 0.07            # mm, nejmensi vzdalenost od steny bunky pri znaceni
M_DET = 0.02            # mm, totez pri cteni (bez originalu)
ID_BITS = 32
TAG_BITS = 40
CODE_BITS = ID_BITS + TAG_BITS      # 72
_SEC_MIN = 16
_MAX_FLIP = 12          # oprava kodu: zkousi se vsechny podmnoziny z tolika nejmene spolehlivych bitu
MIN_CELLS_MARK = 400   # mene unikatnich bunek (viz _votes_blind) nema na 72 bitu dost hlasu -> mark() odmitne
_P_MIN = 1e-6           # nejvyssi povolena pravdepodobnost falesne shody pro platnou detekci
_ICP_ACCEPT_MM = 0.25   # registrace: median vzdalenosti NN po sesouhlaseni
_MATCH_MM = 0.30        # s originalem: nejvetsi vzdalenost vrchol -> nejblizsi bod uniku

_ATOL_M = 1e-9
# slepe hledani soustavy (bez originalu): nasobek jednotek (soubor -> mm) a 24 otoceni o nasobky 90 st.,
# posun je nulovy (neznamy posun bez originalu cist nejde)
_SCALES = (1.0, 1000.0, 0.001, 100.0, 0.01, 10.0, 0.1, 25.4, 1.0 / 25.4, 304.8, 1.0 / 304.8)
_SCREEN_N = 3000        # kolik vrcholu se pouzije k rychlemu situ hypotezy
_SCREEN_T = 0.112       # prah sita (nahodna data ~0.125, znacka ~0.0-0.1)


# ---------------------------------------------------------------------------
# Klice a kod
# ---------------------------------------------------------------------------

def derive_secret(flask_secret_key):
    """Odvozeny klic z FLASK_SECRET_KEY (stejny vzor jako api/tracking.py
    _ip_hash: zadny novy secret ke sprave). Pouzit jen jako zaloha, kdyz
    neni nastaveno V3D_MARK_SECRET - viz get_secret()."""
    if isinstance(flask_secret_key, str):
        flask_secret_key = flask_secret_key.encode("utf-8")
    if not flask_secret_key:
        raise ValueError("prazdny FLASK_SECRET_KEY")
    return hmac.new(bytes(flask_secret_key), b"v3d-mark/v1/derived-from-flask-secret", hashlib.sha256).digest()


def get_secret(env=None, flask_secret_key=None):
    """secret pro mark()/detect(): 1) env V3D_MARK_SECRET (retezec; 64 hex znaku
    = bajty z hex, jinak UTF-8), 2) derive_secret(flask_secret_key). Jinak
    ValueError (znacka se nevklada tise)."""
    env = os.environ if env is None else env
    v = (env.get("V3D_MARK_SECRET") or "").strip()
    if v:
        if re.fullmatch(r"[0-9a-fA-F]{64}", v):
            return bytes.fromhex(v)
        b = v.encode("utf-8")
        if len(b) < _SEC_MIN:
            raise ValueError("V3D_MARK_SECRET je kratky (min %d znaku)" % _SEC_MIN)
        return b
    if flask_secret_key:
        return derive_secret(flask_secret_key)
    raise ValueError("neni V3D_MARK_SECRET ani FLASK_SECRET_KEY - znacku nelze vlozit/precist")


class _Keys:
    def __init__(self, secret):
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < _SEC_MIN:
            raise ValueError("secret musi byt bajty (min %d)" % _SEC_MIN)
        secret = bytes(secret)
        self.grid = hmac.new(secret, b"v3d-mark/v1/grid", hashlib.sha256).digest()
        self.tag = hmac.new(secret, b"v3d-mark/v1/tag", hashlib.sha256).digest()
        o = hmac.new(secret, b"v3d-mark/v1/origin", hashlib.sha256).digest()
        self.origin = np.array([int.from_bytes(o[4 * i:4 * i + 4], "big") / 4294967296.0 * CELL
                                for i in range(3)])

    def tag_of(self, offer_id):
        return int.from_bytes(hmac.new(self.tag, struct.pack(">I", offer_id), hashlib.sha256).digest()[:5], "big")

    def code_int(self, offer_id):
        """72bitove cislo: horni 32 b id, dolnich 40 b tag."""
        return (offer_id << TAG_BITS) | self.tag_of(offer_id)

    def code_bits(self, offer_id):
        c = self.code_int(offer_id)
        return np.array([(c >> (CODE_BITS - 1 - j)) & 1 for j in range(CODE_BITS)], dtype=np.int64)

    def prf_cells(self, cells):
        """cells: int64 [M,3] -> (osa[M], j[M], dither[M] v mm; vsechno pro UNIKATNI bunky) + inv.
        Vrati pole pro kazdy vstupni radek (po rozbaleni pres inv)."""
        u, inv = np.unique(cells, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        m = len(u)
        axis = np.empty(m, dtype=np.int64)
        j = np.empty(m, dtype=np.int64)
        d = np.empty(m, dtype=np.float64)
        key = self.grid
        pack = struct.pack
        b2 = hashlib.blake2b
        for i in range(m):
            h = b2(pack("<3q", int(u[i, 0]), int(u[i, 1]), int(u[i, 2])), digest_size=9, key=key).digest()
            axis[i] = int.from_bytes(h[0:4], "big") % 3
            j[i] = int.from_bytes(h[4:6], "big") % CODE_BITS
            d[i] = int.from_bytes(h[6:9], "big") / 16777216.0 * DELTA
        return axis[inv], j[inv], d[inv]


# ---------------------------------------------------------------------------
# Geometrie GLB: svetove matice, POSITION accessory
# ---------------------------------------------------------------------------

def _mat4(m):
    """glTF column-major seznam 16 cisel -> numpy 4x4 (radky)."""
    return np.array(m, dtype=np.float64).reshape(4, 4).T


def _scene_nodes(g):
    """[(node_index, world_matrix 4x4)] pro vsechny uzly dosazitelne z vychozi sceny."""
    nodes = g.get("nodes") or []
    scenes = g.get("scenes") or []
    if scenes:
        si = g.get("scene", 0)
        roots = list(scenes[si if isinstance(si, int) and 0 <= si < len(scenes) else 0].get("nodes", []))
    else:
        child = {c for n in nodes for c in n.get("children", [])}
        roots = [i for i in range(len(nodes)) if i not in child]
    out = []
    stack = [(r, np.eye(4)) for r in reversed(roots)]
    seen = 0
    while stack:
        i, pm = stack.pop()
        seen += 1
        if seen > 10 * len(nodes) + 10:
            raise V3DError("strom uzlu obsahuje cyklus")
        n = nodes[i]
        lm = _mat4(v3d_glb._local_matrix(n))
        wm = pm @ lm
        out.append((i, wm))
        for c in reversed(n.get("children", [])):
            stack.append((c, wm))
    return out


def _acc_view(g, buf, ai, writable=False):
    """ndarray [count,3] float32 nad accessorem POSITION (stride-aware) nebo None."""
    a = g["accessors"][ai]
    if a.get("componentType") != 5126 or a.get("type") != "VEC3" or "bufferView" not in a or "sparse" in a:
        return None
    v = g["bufferViews"][a["bufferView"]]
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride", 12)
    n = a["count"]
    if base + stride * (n - 1) + 12 > len(buf):
        raise V3DError("POSITION accessor presahuje BIN")
    return np.ndarray((n, 3), dtype="<f4", buffer=buf, offset=base, strides=(stride, 4))


def _acc_points_any(g, buf, ai):
    """Vrcholy libovehoho (i normalizovaneho celociselneho) POSITION jako float64 [n,3]; None kdyz nejde."""
    a = g["accessors"][ai]
    if "bufferView" not in a or "sparse" in a or a.get("type") != "VEC3":
        return None
    if a.get("componentType") == 5126:
        return np.array(_acc_view(g, buf, ai), dtype=np.float64)
    if a.get("componentType") in (5120, 5121, 5122, 5123):
        pts = v3d_glb._positions(g, buf, ai, {})
        return np.array(pts, dtype=np.float64)
    return None


def _buf0(g, b):
    bufs = g.get("buffers") or []
    if not bufs or "uri" in bufs[0] or b is None:
        raise V3DError("GLB musi mit jeden vnitrni BIN chunk (bez uri)")
    return b


def world_points(glb_bytes, with_info=False):
    """Vsechny vrcholy POSITION v SVETOVYCH souradnicich (jednotky souboru) jako
    ndarray float64 [N,3]. Tolerantni ke GLB z jinych nastroju (Blender, three,
    vice primitiv, matice i TRS, int/normalized POSITION); Draco a sparse se
    preskoci (info['skipped'])."""
    g, b = v3d_glb.read_glb(glb_bytes)
    buf = _buf0(g, b)
    chunks = []
    skipped = 0
    meshes = g.get("meshes") or []
    cache = {}
    for i, wm in _scene_nodes(g):
        n = g["nodes"][i]
        if "mesh" not in n:
            continue
        R, t = wm[:3, :3], wm[:3, 3]
        for pr in meshes[n["mesh"]].get("primitives", []):
            pa = (pr.get("attributes") or {}).get("POSITION")
            if pa is None or "KHR_draco_mesh_compression" in (pr.get("extensions") or {}):
                skipped += 1
                continue
            if pa not in cache:
                cache[pa] = _acc_points_any(g, buf, pa)
            P = cache[pa]
            if P is None:
                skipped += 1
                continue
            chunks.append(P @ R.T + t)
    if not chunks:
        raise V3DError("v GLB nejsou zadne vrcholy POSITION (preskoceno %d)" % skipped)
    P = np.concatenate(chunks)
    return (P, {"skipped": skipped, "primitives": len(chunks)}) if with_info else P


def points_from_obj(text):
    """Vrcholy z textoveho OBJ ("v x y z") - OBJ nema hierarchii, souradnice jsou svetove."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8", "replace")
    pts = []
    for line in text.splitlines():
        if line.startswith("v "):
            p = line.split()
            pts.append((float(p[1]), float(p[2]), float(p[3])))
    if not pts:
        raise V3DError("OBJ nema zadne vrcholy")
    return np.array(pts, dtype=np.float64)


def points_from_stl(data):
    """Vrcholy z binarniho STL (3 vrcholy na trojuhelnik, svetove souradnice)."""
    data = bytes(data)
    if len(data) < 84:
        raise V3DError("STL je prilis kratky")
    n = struct.unpack_from("<I", data, 80)[0]
    if 84 + 50 * n != len(data):
        raise V3DError("STL: neocekavana delka (ASCII STL se nepodporuje)")
    rec = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    arr = np.frombuffer(data, dtype=rec, count=n, offset=84)
    return arr["v"].reshape(-1, 3).astype(np.float64)


class _Seg:
    __slots__ = ("acc", "R", "t", "Rinv", "count")


def _position_segments(g):
    """POSITION accessory k oznaceni: [(_Seg)], + pocet preskocenych accessoru.
    Kazdy accessor musi byt pouzit jednou transformaci (mesh ve scene prave jednou
    - tak vznika sanitizer; vic ruznych matic = accessor se preskoci)."""
    meshes = g.get("meshes") or []
    mats = {}
    for i, wm in _scene_nodes(g):
        n = g["nodes"][i]
        if "mesh" not in n:
            continue
        for pr in meshes[n["mesh"]].get("primitives", []):
            pa = (pr.get("attributes") or {}).get("POSITION")
            if pa is not None:
                mats.setdefault(pa, []).append(wm)
    segs, skipped = [], 0
    for pa, ml in sorted(mats.items()):
        a = g["accessors"][pa]
        if a.get("componentType") != 5126 or a.get("type") != "VEC3" or "bufferView" not in a or "sparse" in a:
            skipped += 1
            continue
        if any(not np.allclose(m, ml[0], rtol=0, atol=_ATOL_M) for m in ml[1:]):
            skipped += 1
            continue
        wm = ml[0]
        R = wm[:3, :3]
        if abs(np.linalg.det(R)) < 1e-12:
            skipped += 1
            continue
        s = _Seg()
        s.acc, s.R, s.t, s.Rinv, s.count = pa, R, wm[:3, 3].copy(), np.linalg.inv(R), a["count"]
        segs.append(s)
    return segs, skipped


# ---------------------------------------------------------------------------
# Dekodovani hlasu (bez originalu)
# ---------------------------------------------------------------------------

def _cells_of(P, keys):
    q = (P - keys.origin) / CELL
    c = np.floor(q)
    f = q - c
    margin = np.minimum(f, 1.0 - f).min(axis=1) * CELL
    return c.astype(np.int64), margin


def _votes_blind(P, keys):
    """Hlasy pro bity kodu z bodu P [N,3] (svetove souradnice). Vraci dict
    (sum[L], cnt[L], cells, vertices)."""
    cells, margin = _cells_of(P, keys)
    ok = np.nonzero(margin >= M_DET)[0]
    s = np.zeros(CODE_BITS)
    cnt = np.zeros(CODE_BITS, dtype=np.int64)
    if len(ok) == 0:
        return {"sum": s, "cnt": cnt, "cells": 0, "vertices": 0}
    axis, j, d = keys.prf_cells(cells[ok])
    x = P[ok, axis]
    r = ((x - d) / DELTA) % 1.0
    d0 = np.minimum(r, 1.0 - r)
    d1 = np.abs(r - 0.5)
    vote = np.clip(2.0 * (d0 - d1), -1.0, 1.0)             # +1 = blize mrizce b=1
    # jedna bunka = jeden hlas (souvisle kopie a vice vrcholu v bunce se nezapocitaji nasobne)
    u, inv = np.unique(cells[ok], axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    cv = np.bincount(inv, weights=vote) / np.bincount(inv)
    cj = np.zeros(len(u), dtype=np.int64)
    cj[inv] = j
    s = np.bincount(cj, weights=cv, minlength=CODE_BITS)
    cnt = np.bincount(cj, minlength=CODE_BITS)
    return {"sum": s, "cnt": cnt, "cells": int(len(u)), "vertices": int(len(ok))}


def _ncdf_tail(z):
    """P(Z >= z) pro standardni normalni rozdeleni."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _bits_to_int(bits):
    v = 0
    for b in bits:
        v = (v << 1) | int(b)
    return v


def _interpret(votes, keys, kandidati=None):
    """Z hlasu -> vysledek: platny kod (HMAC), pripadne nejlepsi kandidat."""
    s, cnt = votes["sum"], votes["cnt"]
    m = np.divide(s, np.maximum(cnt, 1))                     # -1..+1 na bit
    bits = (s > 0).astype(np.int64)
    order = np.argsort(np.abs(m))                            # nejmene spolehlive prvni
    res = {"offer_id": None, "jistota": 0.0, "mode": None, "p_false": None, "flips": None,
           "bits_min_cells": int(cnt.min()) if len(cnt) else 0,
           "mean_abs_vote": float(np.mean(np.abs(m))), "cells": votes.get("cells", 0),
           "vertices": votes.get("vertices", 0), "kandidat": None}
    if votes.get("cells", 0) < CODE_BITS:
        return res

    def try_bits(bv):
        v = _bits_to_int(bv)
        oid = v >> TAG_BITS
        return oid if (v & ((1 << TAG_BITS) - 1)) == keys.tag_of(oid) else None

    found, flips, tries = None, 0, 0
    oid = try_bits(bits)
    tries = 1
    if oid is not None:
        found = oid
    else:
        low = [int(i) for i in order[:_MAX_FLIP]]
        best = None
        for mask in range(1, 1 << _MAX_FLIP):
            tries += 1
            nb = bits.copy()
            k = 0
            for bi in range(_MAX_FLIP):
                if mask >> bi & 1:
                    nb[low[bi]] ^= 1
                    k += 1
            oid = try_bits(nb)
            if oid is not None and (best is None or k < best[1]):
                best = (oid, k)
        if best is not None:
            found, flips = best
    if found is not None:
        p = min(1.0, tries * 2.0 ** -TAG_BITS)
        res.update(offer_id=found, jistota=1.0 - p, mode="blind", p_false=p, flips=flips)
        return res
    # kandidati: matched filter na kod kandidata (jen kdyz hard-dekod selhal)
    if kandidati:
        denom = math.sqrt(float(np.sum(m * m)))
        best = None
        n = 0
        for cid in kandidati:
            n += 1
            cb = keys.code_bits(int(cid)) * 2 - 1
            z = float(np.dot(cb, m) / denom) if denom > 0 else 0.0
            if best is None or z > best[1]:
                best = (int(cid), z)
        if best is not None:
            p = min(1.0, _ncdf_tail(best[1]) * n)
            res["kandidat"] = {"id": best[0], "z": best[1], "p_false": p}
            if p <= _P_MIN:
                res.update(offer_id=best[0], jistota=1.0 - p, mode="kandidat", p_false=p)
    return res


# ---------------------------------------------------------------------------
# Registrace na original (podobnost: meritko + otoceni + posun)
# ---------------------------------------------------------------------------

def _umeyama(src, dst):
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    cov = xd.T @ xs / len(src)
    U, S, Vt = np.linalg.svd(cov)
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1.0
    R = U @ D @ Vt
    var_s = float((xs ** 2).sum() / len(src))
    s = float(np.sum(S * np.diag(D)) / var_s) if var_s > 0 else 1.0
    t = mu_d - s * R @ mu_s
    return s, R, t


def _signed_perms():
    import itertools
    out = []
    for p in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            M = np.zeros((3, 3))
            for i in range(3):
                M[i, p[i]] = sg[i]
            out.append(M)
    return out


def _icp(src, dst, tree, s, R, t, iters, trim):
    med = float("inf")
    for _ in range(iters):
        X = s * (src @ R.T) + t
        dist, idx = tree.query(X)
        k = max(10, int(trim * len(dist)))
        sel = np.argpartition(dist, k - 1)[:k]
        s, R, t = _umeyama(src[sel], dst[idx[sel]])
        med = float(np.median(dist))
    X = s * (src @ R.T) + t
    dist, _ = tree.query(X)
    return s, R, t, float(np.median(dist))


def _dedupe(P):
    """Unikatni body (v relativni presnosti 1e-6 rozmeru modelu - funguje i pro model v metrech)."""
    step = max(float(np.linalg.norm(P.max(0) - P.min(0))) * 1e-6, 1e-12)
    _, ui = np.unique(np.round(P / step), axis=0, return_index=True)
    return P[np.sort(ui)]


def register(P_leak, P_orig, rng_seed=1):
    """Najde podobnost (s, R, t) takovou, ze s*R@x+t prevede body uniku do souradnic
    originalu. Vraci (s, R, t, median_nn_mm) nebo None. Cela-model transformace
    (bez oriznuti): PCA + 24 otoceni + trimovany ICP. Vyzaduje scipy."""
    from scipy.spatial import cKDTree
    rng = np.random.RandomState(rng_seed)
    Lu = _dedupe(P_leak)
    Ou = _dedupe(P_orig)
    tree_o = cKDTree(Ou)
    sub = lambda A, n: A if len(A) <= n else A[rng.choice(len(A), n, replace=False)]   # noqa: E731
    Ls, Os = sub(Lu, 3000), sub(Ou, 3000)
    tree_os = cKDTree(Os)

    # 1) identita (nejcastejsi: jen sum/zaokrouhleni/oriznuti v tehoz souradnem systemu)
    s, R, t, med = _icp(Ls, Os, tree_os, 1.0, np.eye(3), np.zeros(3), 3, 0.7)
    if med < 0.2 and 0.5 < s < 2.0:
        s, R, t, med = _icp(Lu, Ou, tree_o, s, R, t, 6, 0.85)
        if med < _ICP_ACCEPT_MM and 0.5 < s < 2.0:
            return s, R, t, med
    # 2) PCA + signed permutace
    mu_l, mu_o = Lu.mean(0), Ou.mean(0)
    cl, co = np.cov((Lu - mu_l).T), np.cov((Ou - mu_o).T)
    wl, Vl = np.linalg.eigh(cl)
    wo, Vo = np.linalg.eigh(co)
    s0 = math.sqrt(float(wo.sum() / wl.sum()))
    best = None
    for Pm in _signed_perms():
        R0 = Vo @ Pm @ Vl.T
        if np.linalg.det(R0) < 0:
            continue
        t0 = mu_o - s0 * R0 @ mu_l
        r = _icp(Ls, Os, tree_os, s0, R0, t0, 12, 0.7)
        if best is None or r[3] < best[3]:
            best = r
    s, R, t, med = best
    s, R, t, med = _icp(Lu, Ou, tree_o, s, R, t, 25, 0.85)
    if med < _ICP_ACCEPT_MM and 0.5 * s0 < s < 2.0 * s0:
        return s, R, t, med
    return None


def _votes_with_original(P_leak, P_orig, keys, tf=None):
    """Hlasy z posunu vrcholu originalu: P_leak (uniklé body) se prevedou do soustavy
    originalu (tf = (s,R,t) nebo registrace) a pro kazdy znacitelny vrchol originalu se
    porovna jeho skutecny posun s ocekavanym pro b=0 a b=1."""
    from scipy.spatial import cKDTree
    if tf is None:
        tf = register(P_leak, P_orig)
        if tf is None:
            return None, None
    s, R, t = tf[0], tf[1], tf[2]
    X = s * (P_leak @ R.T) + t
    cells, margin = _cells_of(P_orig, keys)
    el = np.nonzero(margin >= M_EMB)[0]
    out = {"sum": np.zeros(CODE_BITS), "cnt": np.zeros(CODE_BITS, dtype=np.int64), "cells": 0, "vertices": 0}
    if len(el) == 0:
        return out, tf
    tree = cKDTree(X)
    dist, idx = tree.query(P_orig[el], distance_upper_bound=_MATCH_MM)
    good = np.isfinite(dist)
    el, idx = el[good], idx[good]
    if len(el) == 0:
        return out, tf
    axis, j, d = keys.prf_cells(cells[el])
    x0 = P_orig[el, axis]
    xo = X[idx, axis]
    # ocekavane posuny pro b=0 a b=1
    k0 = np.rint((x0 - d) / DELTA)
    d0 = d + DELTA * k0 - x0
    k1 = np.rint((x0 - d) / DELTA - 0.5)
    d1 = d + DELTA * (k1 + 0.5) - x0
    r = xo - x0
    mid = 0.5 * (d0 + d1)
    sgn = np.sign(d1 - d0)
    vote = np.clip(sgn * (r - mid) / (DELTA / 4.0), -1.0, 1.0)     # +1 = shoda s b=1
    u, inv = np.unique(cells[el], axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    cv = np.bincount(inv, weights=vote) / np.bincount(inv)
    cj = np.zeros(len(u), dtype=np.int64)
    cj[inv] = j
    out["sum"] = np.bincount(cj, weights=cv, minlength=CODE_BITS)
    out["cnt"] = np.bincount(cj, minlength=CODE_BITS)
    out["cells"] = int(len(u))
    out["vertices"] = int(len(el))
    return out, tf


def _rot24():
    return [Pm for Pm in _signed_perms() if np.linalg.det(Pm) > 0]


def _screen_stat(Q, keys):
    """Rychle sito hypotezy soustavy: strednihodnota vzdalenosti fazi od nejblizsi z obou mrizek
    (v perioda DELTA; nahodna data ~0.125, spravne ctena znacka << 0.125)."""
    cells, margin = _cells_of(Q, keys)
    ok = np.nonzero(margin >= M_DET)[0]
    if len(ok) < 200:
        return 0.125
    # pri zmensenem modelu body padnou do par bunek a faze jsou nahodou "hezke" -> sito by lhalo;
    # spravna hypoteza ma tolik bunek, kolik je vrcholu
    if len(np.unique(cells[ok], axis=0)) < 0.5 * len(ok):
        return 0.125
    axis, _, d = keys.prf_cells(cells[ok])
    r = ((Q[ok, axis] - d) / DELTA) % 1.0
    return float(np.mean(np.minimum(np.minimum(r, 1.0 - r), np.abs(r - 0.5))))


def _frame_search(P, keys, kand):
    """Zkusi znacku precist po zmene jednotek a otoceni o nasobky 90 st. (napr. Blender Z-up,
    STL, jednotky v metrech/cm/palcich) BEZ posunu. Vraci (vysledek, popis) nebo (None, None)."""
    rng = np.random.RandomState(7)
    sub = P if len(P) <= _SCREEN_N else P[rng.choice(len(P), _SCREEN_N, replace=False)]
    hyp = []
    for sc in _SCALES:
        for Rm in _rot24():
            if sc == 1.0 and np.allclose(Rm, np.eye(3)):
                continue
            T = _screen_stat(sc * (sub @ Rm.T), keys)
            if T < _SCREEN_T:
                hyp.append((T, sc, Rm))
    hyp.sort(key=lambda h: h[0])
    for T, sc, Rm in hyp[:6]:
        res = _interpret(_votes_blind(sc * (P @ Rm.T), keys), keys, kand)
        if res["offer_id"] is not None:
            tried = len(hyp[:6])
            res["p_false"] = min(1.0, res["p_false"] * tried)
            res["jistota"] = 1.0 - res["p_false"]
            return res, {"meritko": sc, "otoceni": Rm.astype(int).tolist(), "sito": T}
    return None, None


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------

def detect_points(P, secret, kandidati=None, original_points=None, frames=True):
    """Jako detect_report, ale na bodech [N,3] (napr. z OBJ). Poradi pokusu: (1) cteni v
    soustave souboru, (2) frames=True: slepe hledani jednotek/otoceni o 90 st. bez posunu,
    (3) original_points: registrace na original (posun, libovolne otoceni, meritko)."""
    keys = _Keys(secret)
    P = np.asarray(P, dtype=np.float64)
    if P.ndim != 2 or P.shape[1] != 3 or len(P) == 0:
        raise ValueError("body musi byt [N,3]")
    kand = list(kandidati) if kandidati is not None else None
    res = _interpret(_votes_blind(P, keys), keys, kand)
    res["rezim"] = "bez originalu" if res["offer_id"] is not None else None
    res["registrace"] = None
    res["soustava"] = None
    if res["offer_id"] is None and frames:
        r2, info = _frame_search(P, keys, kand)
        if r2 is not None:
            r2["rezim"] = "bez originalu (jine jednotky/otoceni)"
            r2["registrace"] = None
            r2["soustava"] = info
            return r2
    if res["offer_id"] is None and original_points is not None:
        votes, tf = _votes_with_original(P, np.asarray(original_points, dtype=np.float64), keys)
        if votes is None:
            res["registrace"] = "selhala"
        else:
            res["registrace"] = {"meritko": tf[0], "median_nn_mm": tf[3]}
            r2 = _interpret(votes, keys, kand)
            r2["rezim"] = "s originalem" if r2["offer_id"] is not None else None
            r2["registrace"] = res["registrace"]
            r2["soustava"] = None
            r2["slepa_cells"] = res["cells"]
            res = r2
    return res


def detect_report(glb_bytes, secret, kandidati=None, original=None):
    """Podrobny vysledek detekce: dict(offer_id, jistota, mode, p_false, flips, cells,
    vertices, registrace, kandidat ...). original = bajty nemarkovaneho GLB teze karty
    (nepovinne; umoznuje cist i po posunu/otoceni/zmene meritka)."""
    P = world_points(glb_bytes)
    Po = world_points(original) if original is not None else None
    return detect_points(P, secret, kandidati, Po)


def detect(glb_bytes, secret, kandidati=None, original=None):
    """(offer_id | None, jistota). jistota = 1 - pravdepodobnost, ze by nahodny (nemarkovany
    nebo cizim klicem markovany) model dal platny kod; 0.0 pri None.
    kandidati: iterable[int] (napr. id vsech scene_offers) - pouzije se jen kdyz kod
    nejde potvrdit HMAC (matched filter na kod kandidata); platny kod se cte i bez nich.
    original: bajty nemarkovaneho GLB (viz detect_report)."""
    r = detect_report(glb_bytes, secret, kandidati, original)
    return r["offer_id"], (r["jistota"] if r["offer_id"] is not None else 0.0)


# ---------------------------------------------------------------------------
# mark
# ---------------------------------------------------------------------------

def _embed(Pw, bits, keys):
    """Pw [N,3] svetove -> (Pw2, idx znacenych vrcholu). Nic jineho nemeni."""
    cells, margin = _cells_of(Pw, keys)
    idx = np.nonzero(margin >= M_EMB)[0]
    Pw2 = Pw.copy()
    if len(idx) == 0:
        return Pw2, idx
    axis, j, d = keys.prf_cells(cells[idx])
    b = bits[j].astype(np.float64)
    x = Pw[idx, axis]
    k = np.rint((x - d) / DELTA - 0.5 * b)
    Pw2[idx, axis] = d + DELTA * (k + 0.5 * b)
    return Pw2, idx


def _aabb_exact(g, buf):
    return v3d_glb._model_aabb(g, buf, exact=True)


def mark_report(glb_bytes, offer_id, secret, *, verify=True):
    """Jako mark(), navic vraci hlaseni (dict)."""
    if type(offer_id) is not int or not (0 <= offer_id < (1 << ID_BITS)):
        raise ValueError("offer_id musi byt cele cislo 0..2^32-1")
    keys = _Keys(secret)
    g, b = v3d_glb.read_glb(glb_bytes)
    buf = _buf0(g, b)
    v3d_glb.check_structure(g, buf, "mark vstup")
    segs, skipped = _position_segments(g)
    if not segs:
        raise V3DError("mark: v GLB neni zadny POSITION accessor typu float32 VEC3 k oznaceni")

    # uz oznaceny model? (dvojite znaceni by posunulo vrcholy az o 0.09 mm)
    pre = detect_points(world_points(glb_bytes), secret)
    if pre["offer_id"] is not None:
        if pre["offer_id"] == offer_id:
            return glb_bytes, {"already": True, "offer_id": offer_id}
        raise V3DError("mark: model uz nese znacku nabidky %d (nejde pridat dalsi)" % pre["offer_id"])

    bits = keys.code_bits(offer_id)
    out_bin = bytearray(buf)
    g2 = _deepcopy_json(g)
    n_all = n_mark = 0
    max_shift = 0.0
    ss = 0.0
    diff_ranges = []
    aabb0 = _aabb_exact(g, buf)
    for s in segs:
        ro = _acc_view(g, buf, s.acc)
        P32 = np.array(ro, dtype=np.float32)
        Pl = P32.astype(np.float64)
        Pw = Pl @ s.R.T + s.t
        Pw2, idx = _embed(Pw, bits, keys)
        n_all += len(Pw)
        if len(idx) == 0:
            continue
        Pl2 = ((Pw2[idx] - s.t) @ s.Rinv.T).astype(np.float32)
        # skutecny svetovy posun po zaokrouhleni na float32
        shift = np.linalg.norm((Pl2.astype(np.float64) @ s.R.T + s.t) - Pw[idx], axis=1)
        max_shift = max(max_shift, float(shift.max()))
        ss += float((shift ** 2).sum())
        n_mark += len(idx)
        wv = _acc_view(g, out_bin, s.acc)
        wv[idx] = Pl2
        P32[idx] = Pl2
        acc = g2["accessors"][s.acc]
        acc["min"] = [float(x) for x in P32.min(axis=0)]
        acc["max"] = [float(x) for x in P32.max(axis=0)]
        a = g["accessors"][s.acc]
        v = g["bufferViews"][a["bufferView"]]
        base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        diff_ranges.append((base, v.get("byteStride", 12), a["count"]))
    if n_mark == 0:
        raise V3DError("mark: zadny vrchol nesplnil podminky znaceni")
    cells_est = _count_cells(g, buf, segs, keys, bits)
    if cells_est < MIN_CELLS_MARK:
        raise V3DError("mark: model je na znacku prilis maly (%d unikatnich bunek, potreba >= %d)"
                       % (cells_est, MIN_CELLS_MARK))
    if max_shift >= MAX_SHIFT_MM:
        raise V3DError("mark: posun vrcholu %.4f mm prekrocil mez %.3f mm" % (max_shift, MAX_SHIFT_MM))
    out = v3d_glb.write_glb(g2, bytes(out_bin))
    rep = {"already": False, "offer_id": offer_id, "vertices": n_all, "marked": n_mark,
           "skipped_accessors": skipped, "max_shift_mm": max_shift, "rms_shift_mm": math.sqrt(ss / n_mark)}

    if verify:
        _verify(out, glb_bytes, g, buf, diff_ranges, offer_id, secret, aabb0, rep)
    return out, rep


def _count_cells(g, buf, segs, keys, bits):
    """Pocet unikatnich bunek, ve kterych je aspon jeden znaceny vrchol (zhruba kolik hlasu pri cteni)."""
    allc = []
    for s in segs:
        Pw = np.array(_acc_view(g, buf, s.acc), dtype=np.float64) @ s.R.T + s.t
        cells, margin = _cells_of(Pw, keys)
        allc.append(cells[margin >= M_EMB])
    c = np.concatenate(allc)
    return int(len(np.unique(c, axis=0))) if len(c) else 0


def mark_offer_model(sanitized_glb, offer_id, flask_secret_key=None, env=None, *, verify=True):
    """Vstup pro api/scene_offers.py: secret z get_secret(env, flask_secret_key) a mark().
    Vraci bajty GLB; pri jakemkoli problemu ValueError (volajici nabidku/model odmitne)."""
    return mark(sanitized_glb, int(offer_id), get_secret(env, flask_secret_key), verify=verify)


def mark(glb_bytes, offer_id, secret, *, verify=True):
    """GLB (uz po v3d_glb.sanitize) + cislo nabidky -> GLB s neviditelnou znackou.
    Poradi v integraci: sanitize -> mark (mark si vystup sam pusti pres sanitize a
    final_check, viz verify). verify=False jen pro mereni."""
    return mark_report(glb_bytes, offer_id, secret, verify=verify)[0]


def _deepcopy_json(o):
    import json
    return json.loads(json.dumps(o))


def _verify(out, orig, g_in, buf_in, diff_ranges, offer_id, secret, aabb0, rep):
    g2, b2 = v3d_glb.read_glb(out)
    v3d_glb.check_structure(g2, b2, "mark vystup")
    v3d_glb.final_check(g2)
    v3d_glb.check_bin(g2, b2)
    # zmenit se smely jen bajty POSITION elementu
    a = np.frombuffer(buf_in, dtype=np.uint8)
    c = np.frombuffer(b2[:len(buf_in)], dtype=np.uint8)
    if len(a) != len(c):
        raise V3DError("mark: zmenila se delka BIN")
    mask = np.zeros(len(a), dtype=bool)
    for base, stride, cnt in diff_ranges:
        for k in range(12):
            mask[base + k: base + stride * (cnt - 1) + k + 1: stride] = True
    changed = np.nonzero(a != c)[0]
    if len(changed) and not mask[changed].all():
        raise V3DError("mark: zmenily se bajty mimo data POSITION")
    # JSON se smi lisit jen v min/max POSITION accessoru
    gi = _deepcopy_json(g_in)
    g2c = _deepcopy_json(g2)
    for ac in gi["accessors"] + g2c["accessors"]:
        ac.pop("min", None)
        ac.pop("max", None)
    if gi != g2c:
        raise V3DError("mark: zmenil se JSON mimo min/max accessoru")
    aabb1 = _aabb_exact(g2, b2)
    sh = max(max(abs(aabb1["min"][k] - aabb0["min"][k]), abs(aabb1["max"][k] - aabb0["max"][k])) for k in range(3))
    rep["aabb_shift_mm"] = sh
    if sh > MAX_SHIFT_MM + 0.002:
        raise V3DError("mark: AABB modelu se posunul o %.4f mm" % sh)
    spec = v3d_glb.embedded_spec(out)
    # znacka musi jit precist a prezit dalsi pruchod pojistkou
    rd = detect_points(world_points(out), secret)
    if rd["offer_id"] != offer_id:
        raise V3DError("mark: znacka se po vlozeni nedala precist (kontrola)")
    again = v3d_glb.sanitize(out, spec)
    rep["sanitize_idempotent"] = again == out
    rd2 = detect_points(world_points(again), secret)
    if rd2["offer_id"] != offer_id:
        raise V3DError("mark: znacka neprezila dalsi v3d_glb.sanitize")
    rep["detect_cells"] = rd["cells"]
