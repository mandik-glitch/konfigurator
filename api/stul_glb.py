"""Skladani GLB konfigurovaneho stolu na serveru (bot8, 2026-10-02).

Verejny prohlizec (viewer3d.js, e-shop) NESMI nacitat katalog/*.glb ani scene.html (ochrana 3D modelu, Robert 2026-09-06):
model prichazi jako JEDEN GLB poskladany tady z dilu, ktere vraci api/stul_konfigurator.py. Vystup:
  * jednotky mm, osa Y nahoru (jako scena a viewer3d - viz demo stul_demo_a.glb), stul vycentrovany v ose X/Z, podlaha y = 0
  * dily slite do nekolika siti PODLE MATERIALU (zadna jmena dilu, zadna hierarchie): uzly "n0", "n1", ...
  * scenes[0].extras.v3d = popis pro viewer3d (jednotky, nahoru, predek, obalka, kóty sirka/hloubka/vyska, bez pohybu)
  * normaly se transformuji (nerovnomerne meritko profilu), chybi-li v dilu, dopocitaji se
Pure funkce nad soubory katalogu (jen cteni); vysledek se drzi v malem LRU cache podle kanonickeho hashe parametru.
"""
import gzip
import hashlib
import json
import logging
import os
import struct
from collections import OrderedDict

try:
    import brotli as _brotli
except ImportError:                                           # bez brotli se komprimuje jen gzipem
    _brotli = None

import numpy as np

import stul_konfigurator as S
import stul_koty
import stul_osvetleni

RULES_VERSION = "2026-10-06.1"      # 2026-10-06.1: zaslepky (3071 / 3090 / 3091) se automaticky davaji na VOLNE KONCE profilu (konce ramen LED a pricky nad LED, horni konce zadnich noh bez LED...): pribyvaji dily, cena, kusovnik a vyrobni vypis; vnejsi rozmery stolu se nemeni. 2026-10-05.2: formaty tabuli laminodesky jako kriterium - pracovni deska i spodni police se u stredni nohy / vestaveneho ramu DELI na dve desky (kazda se vejde do tabule 2070 x 2800 mm; pracovni deska a police u stredni nohy navazuji bez mezery, spodni police u ramu jsou o mezeru kratsi), horni mez prahu sirky = delka tabule, meze polohy stredni nohy z delky desky; vyrobni vypis po deskach. 2026-10-05.1: panely vsazene do profilu mezi zadni stojky (1 panel, vychozi sirka 1280), pocet panelu, vyska stojek, vestaveny ram, pohyb elektrozlabu. 2026-10-04.2: kusovnik/cena nese spojovaci material ke spojkam (2 sroubu + 2 matice na spojku). 2026-10-04.1: hloubka > 900 - podperne profily i pod pracovni deskou (pricky supliku se pocitaji jako podpera). 2026-10-03.1: hloubka > 900 - deska spodni police uzsi o 62 mm + podperne profily pod ni, spojky svislych profilu bocnic i dole
GLB_MAGIC, GLB_VERSION = 0x46546C67, 2
CACHE_MAX = 16
KOMPR_MIN = 20000                                             # mensi odpovedi se nekomprimuji
KOMPR_CACHE_MAX = 3 * CACHE_MAX                               # komprimovane bytes (br / gzip) hotovych modelu, LRU podle (hash, kodovani)
_GLB_KOMPR = OrderedDict()

# material podle dilu (barvy podle demo stolu bot10: stul_demo_a.glb - baseColorFactor v "gamma" hodnotach jako Vandr)
MATERIALY = {
    "alu": {"baseColorFactor": [0.5841, 0.6105, 0.6376, 1.0], "metallicFactor": 0.6, "roughnessFactor": 0.35},
    "ocel": {"baseColorFactor": [0.3231, 0.3515, 0.3813, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4},
    "seda": {"baseColorFactor": [0.3763, 0.3763, 0.3763, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4},
    "cerna": {"baseColorFactor": [0.0742, 0.0742, 0.0742, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4},
    "lamino": {"baseColorFactor": [0.74, 0.74, 0.74, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.55},   # svetle seda (Robert)
    "led": {"baseColorFactor": [0.93, 0.93, 0.9, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.3},
}
MATERIALY["chrom"] = {"baseColorFactor": [0.78, 0.8, 0.82, 1.0], "metallicFactor": 1.0, "roughnessFactor": 0.22}      # kulicka a prirube lozisk. jednotky
# RAL 7016 (antracitova seda, sRGB 41 / 49 / 51), LESK (Robert 2026-10-05: "barva navleku tmava sedocerna RAL 7016, lesk"): lak, ne kov - kovovost 0, nizka drsnost.
# POZOR: baseColorFactor je pro viewer3d.js (GLB se spec v3d) LINEARNI (glTF), ne "gamma" jako u starsich materialu vyse; sRGB 41 / 49 / 51 = linearne 0,0222 / 0,0307 / 0,0331
# (s 0,161 / 0,192 / 0,200 vychazel jekl stredne sedy ~ #707880 misto tmaveho)
MATERIALY["ral7016"] = {"baseColorFactor": [0.0222, 0.0307, 0.0331, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.18}
MATERIAL_DILU = {
    "Object_7": "alu", "product_3158": "seda", "product_4933": "lamino", "product_4916": "cerna", "product_4931": "ocel",
    "product_4930": "ocel", "product_4929": "led", "product_4932": "seda", "product_4928": "cerna", "product_3025": "chrom", "product_3071": "cerna", "product_3251": "ocel",
    "product_3254": "seda",           # sikma spojka 45 st. (vzpery ramen LED) - stejny material jako rohove spojky 3158
    # SYSTEM 40 (bot10, 2026-10-04): profil SuperLight 40x40, rohova spojka 3176, zaslepka 40x40 S10 (3091), patka M10 (3283) - stejne materialy jako v systemu 30
    "Object_11": "alu", "product_3176": "seda", "product_3091": "cerna", "product_3283": "ocel", "product_3220": "seda",          # 3220 = sikma spojka 45 st. pro 40 (vzpery)
    # SYSTEM 35 (bot10, 2026-10-05): profil 35x35 (cfg_dily profil_35x35), zaslepka 35x35 (3090); rohove spojky 3158, patky 3251 a sikme spojky 3254 jsou ze systemu 30 (Robert), materialy uz jsou vyse
    "profil_35x35": "alu", "product_3090": "cerna",
    # NAVLEK NOHOU (bot10, 2026-10-05; Robert): jekl 40x40x2 (ocel) a jeho plastova zaslepka - procedural, viz _mesh_jekl / _mesh_jekl_zaslepka
    S.NAVLEK_PART: "ral7016", S.NAVLEK_ZASLEPKA: "cerna",
    # NOHA SSE (bot8, 2026-10-05; system 41): jekly a plechove patky v RAL 7016 jako jekl navleku, vnitrni profil ocel, zaslepka vnitrniho profilu cerny plast - procedural, viz _mesh_kvadr
    S.SSE_JEKL_PART: "ral7016", S.SSE_PLECH_PART: "ral7016", S.SSE_PROFIL_PART: "ocel", S.SSE_PATKA_PART: "cerna",
}
MATERIAL_DILU.update({pid_: "ocel" for pid_ in S.SUPLIK_PARTY_VSE})            # box s 1 a 3 supliky (karty #4956, #4957): stejny material jako dvojsuplik 4930
MATERIALY["mdf"] = {"baseColorFactor": [0.34, 0.36, 0.39, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.6}                 # MDF Steel Grey 8 mm (police): tmave seda
MATERIALY["preklizka"] = {"baseColorFactor": [0.72, 0.56, 0.36, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.65}          # topolova foliovana prekliska PR10 (police): svetle drevo
MATERIAL_DILU.update(S._hpol().MATERIAL_DILU)                                                                                    # dily horni police (desky, uhelniky)
MATERIAL_DILU.update({pid_: "ocel" for pid_ in S.PANEL_PARTY})                 # perforovane panely vsech delek (karty #4931, #4972-4974): ocel jako 4931
MATERIAL_DILU.update({pid_: "led" for pid_ in S.LED_PARTY})                   # svitidla LED vsech delek (karty #4929 LED1200, #5359 LED600): material "led" jako 4929
POREDI_MATERIALU = ["alu", "lamino", "ocel", "seda", "cerna", "led", "chrom", "mdf", "preklizka", "ral7016"]          # ral7016 (jekl navleku) az na konci: poradi uzlu stolu bez navleku se nemeni

_MESH_CACHE = {}
_GLB_CACHE = OrderedDict()
_META_CACHE = OrderedDict()
_POSLEDNI_POSUN = [None]       # posun, ktery pouzilo posledni poskladej_glb (stul se vycentruje v X/Z, podlaha y = 0)
_POSLEDNI_ROZSAHY = [None]     # [[uzel, od, pocet] | None] pro kazdy dil (index jako v dily): kde jsou vrcholy dilu ve slepenych uzlech GLB (zive tazeni v prohlizeci)
_ROZSAHY_CACHE = OrderedDict()
_POSLEDNI_EXTRA = [None]       # {index dilu: [[uzel, od, pocet], ...]}: DALSI rozsahy vrcholu dilu rozdeleneho do vice uzlu (box s supliky: SPODNI suplik s delicimi pricky je vlastni uzel kvuli pohybu na klik); zive tazeni je pricte k rozsahu dilu
_EXTRA_CACHE = OrderedDict()
_POSLEDNI_RAZITKA = [None]     # [{dil, uzel, vypln: [uzel, od, pocet]}] razitek posledniho modelu S razitky (None = model bez razitek): kde je logo (uzel n<uzel>) a jeho vypln drazky (vrcholy v uzlu hlinik) a na kterem dilu sedi; prohlizec je pri zivem tazeni hybe s dilem
_RAZITKA_CACHE = OrderedDict()   # hash -> info o razitkach modelu S razitky (jen k modelu v _GLB_RAZITKA_CACHE)
SUPLIK_OTEVRENI_PODIL = 0.8    # spodni suplik boxu (s delicimi pricky) se na klik vysune o tento podil hloubky svoji korby (nejvic SUPLIK_OTEVRENI_MAX_MM)
SUPLIK_OTEVRENI_MAX_MM = 360.0
SUPLIK_OTEVRENI_MS = 700       # delka pohybu otevreni / zavreni (ms)


class GlbChyba(ValueError):
    pass


# ---------------------------------------------------------------------------------------------------------------------
# cteni GLB dilu
# ---------------------------------------------------------------------------------------------------------------------
_TYPY = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_POCET = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _accessor(js, binc, idx):
    a = js["accessors"][idx]
    if a.get("sparse"):
        raise GlbChyba("sparse accessor neumim cist")
    bv = js["bufferViews"][a["bufferView"]]
    fmt, size = _TYPY[a["componentType"]]
    n = _POCET[a["type"]]
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or size * n
    if stride == size * n:
        arr = np.frombuffer(binc, dtype=np.dtype("<" + fmt), count=a["count"] * n, offset=base)
        return arr.reshape(a["count"], n) if n > 1 else arr
    out = np.empty((a["count"], n), dtype=np.dtype("<" + fmt))
    for i in range(a["count"]):
        out[i] = np.frombuffer(binc, dtype=np.dtype("<" + fmt), count=n, offset=base + i * stride)
    return out if n > 1 else out[:, 0]


def _mesh_loziskove_jednotky(n=28):
    """Procedurální tvar ložiskové (kuličkové) jednotky, karta 3025 (katalog nemá GLB): příruba Ø34 x 3 mm na desce, nad ní prstenec Ø21 x 1,5 mm
    a kulička Ø15 vyčnívající 6 mm nad přírubu (kulový vrchlík). Počátek = střed spodku příruby, Y nahoru (mm). Rozměry jsou odhad podle fotky karty."""
    R_P, H_P, R_K, H_K, R_B, Y_TOP = S.LOZ_PRUMER / 2.0, 3.0, 10.5, 1.5, 7.5, S.LOZ_VYSKA
    P, N, T = [], [], []

    def kruh(y, r, ny):
        base = len(P)
        P.append([0.0, y, 0.0]); N.append([0.0, ny, 0.0])
        for i in range(n):
            a = 2 * np.pi * i / n
            P.append([r * np.cos(a), y, r * np.sin(a)]); N.append([0.0, ny, 0.0])
        for i in range(n):
            a_, b_ = base + 1 + i, base + 1 + (i + 1) % n
            T.append([base, b_, a_] if ny > 0 else [base, a_, b_])

    def plast(y0, y1, r):
        base = len(P)
        for y in (y0, y1):
            for i in range(n):
                a = 2 * np.pi * i / n
                P.append([r * np.cos(a), y, r * np.sin(a)]); N.append([np.cos(a), 0.0, np.sin(a)])
        for i in range(n):
            a_, b_ = i, (i + 1) % n
            T.append([base + a_, base + b_, base + n + b_]); T.append([base + a_, base + n + b_, base + n + a_])

    kruh(0.0, R_P, -1.0); plast(0.0, H_P, R_P); kruh(H_P, R_P, 1.0)
    kruh(H_P, R_K, 1.0); plast(H_P, H_P + H_K, R_K); kruh(H_P + H_K, R_K, 1.0)
    y_stred = Y_TOP - R_B                                   # stred kulicky
    y_zacatek = H_P + H_K                                   # vrchlik zacina na horni plose prstence
    uhly = [np.arccos(np.clip((y_zacatek - y_stred) / R_B, -1, 1)) * k / 7.0 for k in range(8)]    # od vrcholu (0) k okraji
    uhly = sorted({float(u) for u in uhly})
    base = len(P)
    for u in uhly:
        for i in range(n):
            a = 2 * np.pi * i / n
            d = np.array([np.sin(u) * np.cos(a), np.cos(u), np.sin(u) * np.sin(a)])
            P.append((np.array([0.0, y_stred, 0.0]) + R_B * d).tolist()); N.append(d.tolist())
    for j in range(len(uhly) - 1):
        for i in range(n):
            a_, b_ = base + j * n + i, base + j * n + (i + 1) % n
            c_, d_ = base + (j + 1) * n + i, base + (j + 1) * n + (i + 1) % n
            T.append([a_, c_, d_]); T.append([a_, d_, b_])
    return np.array(P, np.float32), np.array(N, np.float32), np.array(T, np.int64)


def _plocha(P, N, T, a, b, c, d, n):
    """Ctyruhelnik a-b-c-d (vrcholy po obvodu) s normalou n: vlastni vrcholy (ploche stinovani), poradi se opravi tak, aby trojuhelniky mirily ke n (CCW zvenku)."""
    a, b, c, d = (np.array(v, float) for v in (a, b, c, d))
    if float(np.dot(np.cross(b - a, c - a), np.array(n, float))) < 0:
        b, d = d, b
    base = len(P)
    for v in (a, b, c, d):
        P.append(v.tolist())
        N.append(list(n))
    T.append([base, base + 1, base + 2])
    T.append([base, base + 2, base + 3])


def _kvadr(P, N, T, lo, hi):
    """Plny kvadr lo..hi (6 ploch s normalami ven)."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    _plocha(P, N, T, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (1, 0, 0))
    _plocha(P, N, T, (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (-1, 0, 0))
    _plocha(P, N, T, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (0, 1, 0))
    _plocha(P, N, T, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0))
    _plocha(P, N, T, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1))
    _plocha(P, N, T, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (0, 0, -1))


def _plocha3(P, N, T, a, b, c, n):
    """Trojuhelnik a-b-c s normalou n: vlastni vrcholy (ploche stinovani), poradi se opravi tak, aby trojuhelnik mirilo ke n."""
    a, b, c = (np.array(v, float) for v in (a, b, c))
    if float(np.dot(np.cross(b - a, c - a), np.array(n, float))) < 0:
        b, c = c, b
    base = len(P)
    for v in (a, b, c):
        P.append(v.tolist())
        N.append(list(n))
    T.append([base, base + 1, base + 2])


def _obrys_sraz(h, c):
    """Ctverec 2h x 2h se srazenymi (45 st.) rohy o c mm: osm vrcholu (u, v) po obvodu proti smeru hodinovych rucicek; hrany 0-1, 2-3, 4-5, 6-7 jsou rovne strany, 1-2, 3-4, 5-6, 7-0 srazeni."""
    return [(h, -(h - c)), (h, h - c), (h - c, h), (-(h - c), h), (-h, h - c), (-h, -(h - c)), (-(h - c), -h), (h - c, -h)]


def _bod(osa, u, v, w):
    """Bod (u, v) obrysu v rovine kolme na osu `osa` ('y': x = u, z = v; 'z': x = u, y = v) ve vzdalenosti w podel osy."""
    return (u, w, v) if osa == "y" else (u, v, w)


def _smer(osa, nu, nv, nw):
    return _bod(osa, nu, nv, nw)


def _prizma_boky(P, N, T, obrys, osa, w0, w1, dovnitr=False):
    """Boky prizmatu nad obrysem (jedna plocha na kazdou stranu, vlastni vrcholy): normaly ven z obrysu (dovnitr=True: do dutiny)."""
    n_ = len(obrys)
    for i in range(n_):
        (ua, va), (ub, vb) = obrys[i], obrys[(i + 1) % n_]
        du, dv = ub - ua, vb - va
        d = (du * du + dv * dv) ** 0.5
        nu, nv = dv / d, -du / d                                              # obrys proti smeru hodinovych rucicek: tohle je normala ven
        if dovnitr:
            nu, nv = -nu, -nv
        _plocha(P, N, T, _bod(osa, ua, va, w0), _bod(osa, ua, va, w1), _bod(osa, ub, vb, w1), _bod(osa, ub, vb, w0), _smer(osa, nu, nv, 0.0))


def _mesh_jekl():
    """NAVLEK NOHOU (bot10, 2026-10-05): jekl 40x40, stena 2 mm (vnitrni 36x36), 1000 mm podel Y, vystredeny v pocatku jako profil (delku dava meritko y). VNEJSI ROHY SRAZENE 45 st. o
    NAVLEK_SRAZENI (2 mm) jako jekl nohy stolu SSE (Robert: \"sraseni jako je na jeklu stolu SSE\"): osmiuhelnikovy vnejsi obrys, vnitrni obrys ctverec. Dutý: 8 vnejsich ploch, 4 vnitrni (normaly
    dovnitr dutiny) a 2 cela (mezikruzi: 4 lichobezniky + 4 trojuhelniky). Katalog GLB nema - tvar se vyrabi tady."""
    h, c = S.NAVLEK_JEKL / 2.0, S.NAVLEK_SRAZENI
    hi_ = h - S.NAVLEK_STENA
    y0, y1 = -500.0, 500.0
    P, N, T = [], [], []
    vnejsi = _obrys_sraz(h, c)
    vnitrni = [(hi_, -hi_), (hi_, hi_), (-hi_, hi_), (-hi_, -hi_)]
    _prizma_boky(P, N, T, vnejsi, "y", y0, y1)
    _prizma_boky(P, N, T, vnitrni, "y", y0, y1, dovnitr=True)
    O, I = vnejsi, {"pm": (hi_, -hi_), "pp": (hi_, hi_), "mp": (-hi_, hi_), "mm": (-hi_, -hi_)}
    for y, ny in ((y1, 1.0), (y0, -1.0)):                                            # cela: mezikruzi mezi osmiuhelnikem a ctvercem
        n = (0.0, ny, 0.0)
        def B(q):
            return _bod("y", q[0], q[1], y)
        for (a_, b_, c_, d_) in ((O[0], O[1], I["pp"], I["pm"]), (O[2], O[3], I["mp"], I["pp"]), (O[4], O[5], I["mm"], I["mp"]), (O[6], O[7], I["pm"], I["mm"])):
            _plocha(P, N, T, B(a_), B(b_), B(c_), B(d_), n)
        for (a_, b_, c_) in ((O[1], O[2], I["pp"]), (O[3], O[4], I["mp"]), (O[5], O[6], I["mm"]), (O[7], O[0], I["pm"])):
            _plocha3(P, N, T, B(a_), B(b_), B(c_), n)
    return np.array(P, np.float32), np.array(N, np.float32), np.array(T, np.int64)


def _mesh_kvadr(lo, hi):
    """Plny kvadr lo..hi jako mesh (pozice, normaly, trojuhelniky); dily nohy SSE (vnitrni profil, plechova patka, zaslepka)."""
    P, N, T = [], [], []
    _kvadr(P, N, T, tuple(float(v) for v in lo), tuple(float(v) for v in hi))
    return np.array(P, np.float32), np.array(N, np.float32), np.array(T, np.int64)


def _mesh_jekl_zaslepka():
    """Zaslepka jeklu 40x40 (plast): priruba 3 mm (z 0..3, vnejsi plocha z = 0 lezi na podlaze) se STEJNYM osmiuhelnikovym obrysem jako jekl (srazene rohy) a zatka 35,6x35,6 mm dlouha 12 mm
    (z 3..15) do jeklu; lokalni +Z = do jeklu (jako zaslepka profilu)."""
    h = S.NAVLEK_JEKL / 2.0
    z = S.NAVLEK_PRIRUBA
    zt = 0.5 * (S.NAVLEK_JEKL - 2 * S.NAVLEK_STENA) - 0.2                            # zatka s vuli 0,2 mm na stranu v dutine 36 mm
    P, N, T = [], [], []
    obrys = _obrys_sraz(h, S.NAVLEK_SRAZENI)
    _prizma_boky(P, N, T, obrys, "z", 0.0, z)
    for w, nw in ((z, 1.0), (0.0, -1.0)):                                            # vika priruby: vějíř od středu
        for i in range(len(obrys)):
            a_, b_ = obrys[i], obrys[(i + 1) % len(obrys)]
            _plocha3(P, N, T, _bod("z", 0.0, 0.0, w), _bod("z", a_[0], a_[1], w), _bod("z", b_[0], b_[1], w), (0.0, 0.0, nw))
    _kvadr(P, N, T, (-zt, -zt, z), (zt, zt, z + S.NAVLEK_ZATKA))
    return np.array(P, np.float32), np.array(N, np.float32), np.array(T, np.int64)


def nacti_mesh(part_id):
    """(pozice Nx3 float32, normaly Nx3 float32, indexy Mx3 int64) vsech meshu/primitiv dilu slite do jednoho."""
    if part_id in _MESH_CACHE:
        return _MESH_CACHE[part_id]
    if part_id == S.LOZ_PART:                      # karta 3025 nema GLB: tvar se vyrabi tady (katalog se nemeni)
        _MESH_CACHE[part_id] = _mesh_loziskove_jednotky()
        return _MESH_CACHE[part_id]
    if part_id == S.NAVLEK_PART:                   # navlek nohou (jekl 40x40x2) a jeho zaslepka: tvar se vyrabi tady
        _MESH_CACHE[part_id] = _mesh_jekl()
        return _MESH_CACHE[part_id]
    if part_id == S.NAVLEK_ZASLEPKA:
        _MESH_CACHE[part_id] = _mesh_jekl_zaslepka()
        return _MESH_CACHE[part_id]
    if part_id == S.SSE_JEKL_PART:                 # jekl nohy SSE: stejny tvar jako jekl navleku (40x40, stena 2 mm, srazene rohy)
        _MESH_CACHE[part_id] = _mesh_jekl()
        return _MESH_CACHE[part_id]
    if part_id in S.SSE_PARTS:                     # vnitrni profil 35x35, plechova patka 150x40x6, zaslepka 35x35x3: plne kvadry (obalka = S.PROCEDURALNI_BBOX)
        lo, hi = S.PROCEDURALNI_BBOX[part_id]
        _MESH_CACHE[part_id] = _mesh_kvadr(lo, hi)
        return _MESH_CACHE[part_id]
    path = S.glb_cesta(part_id)
    if not os.path.isfile(path):
        raise GlbChyba(f"chybi GLB dilu {part_id}")
    with open(path, "rb") as f:
        buf = f.read()
    if struct.unpack("<I", buf[:4])[0] != GLB_MAGIC:
        raise GlbChyba(f"{part_id}: neni GLB")
    off, js, binc = 12, None, None
    while off < len(buf):
        ln, typ = struct.unpack("<II", buf[off:off + 8])
        if typ == 0x4E4F534A:
            js = json.loads(buf[off + 8:off + 8 + ln].decode("utf-8"))
        elif typ == 0x004E4942:
            binc = buf[off + 8:off + 8 + ln]
        off += 8 + ln
    for n in js.get("nodes", []):
        if any(k in n for k in ("matrix", "translation", "rotation", "scale")):
            ident = (n.get("matrix") in (None, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]) and
                     not any(abs(v) > 1e-6 for v in n.get("translation", [0, 0, 0])) and
                     not any(abs(a - b) > 1e-6 for a, b in zip(n.get("rotation", [0, 0, 0, 1]), [0, 0, 0, 1])) and
                     not any(abs(v - 1) > 1e-6 for v in n.get("scale", [1, 1, 1])))
            if not ident:
                raise GlbChyba(f"{part_id}: uzel s transformaci - neumim (kontrola glbRizikaParseru)")
    P, N, T, base = [], [], [], 0
    for mesh in js.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4:
                raise GlbChyba(f"{part_id}: mod != TRIANGLES")
            pos = np.array(_accessor(js, binc, prim["attributes"]["POSITION"]), dtype=np.float32)
            if "NORMAL" in prim["attributes"]:
                nrm = np.array(_accessor(js, binc, prim["attributes"]["NORMAL"]), dtype=np.float32)
            else:
                nrm = None
            if prim.get("indices") is not None:
                idx = np.array(_accessor(js, binc, prim["indices"]), dtype=np.int64)
            else:
                idx = np.arange(len(pos), dtype=np.int64)
            tri = idx.reshape(-1, 3) + base
            if nrm is None:
                nrm = _hladke_normaly(pos, tri - base)
            P.append(pos); N.append(nrm); T.append(tri)
            base += len(pos)
    if not P:
        raise GlbChyba(f"{part_id}: zadna geometrie")
    out = (np.vstack(P), np.vstack(N), np.vstack(T))
    if part_id == "product_4930":
        out = (_zavri_suplik(out[0], out[2]), out[1], out[2])
    _MESH_CACHE[part_id] = out
    return out


def _souvisle_komponenty(pos, tri):
    """Cislo souvisle komponenty pro kazdy TROJUHELNIK (vrcholy se stejnou pozici na 0,01 mm se pokladaji za jeden)."""
    _, inv = np.unique(np.round(pos, 2), axis=0, return_inverse=True)
    inv = inv.ravel()
    t = inv[tri]
    n = int(inv.max()) + 1
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in t:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(c)] = find(a)
    root = np.array([find(i) for i in range(n)])
    return root[t[:, 0]]


def _zavri_suplik(pos, tri):
    """Model `product_4930` (ocelove supliky) ma v katalogu JEDEN SUPLIK VYSUNUTY (~50 cm pred skrin). Pro zakaznicky model se
    zavre: vsechny komponenty vysunuteho supliku (deska + korba + drobne dily, 98 samostatnych komponent) se posunou dovnitr tak,
    aby jeho celo leželo v rovine cela druheho (zavreneho) supliku. Katalogovy soubor se NEMENI. Pri jine strukture modelu (po
    nahrazeni zavrenym souborem, jiny pocet komponent) se NIC nedela. Overeno na skutecnem modelu: posun 513 mm, 0 pruniku s telem."""
    y = pos[:, 1]
    if float(y.max() - y.min()) < 1000.0:
        return pos                              # uz zavreny (nebo jiny) model
    rel = pos.astype(np.float64).copy()
    rel[:, 1] -= rel[:, 1].min()
    komp = _souvisle_komponenty(pos, tri)
    sup1 = np.zeros(len(tri), bool)
    ncomp = 0
    celo2 = None
    for r in np.unique(komp):
        m = komp == r
        vs = np.unique(tri[m].ravel())
        lo, hi = rel[vs].min(axis=0), rel[vs].max(axis=0)
        if lo[2] >= 686.5 and hi[2] <= 779.0 and hi[1] <= 545.0:
            sup1 |= m
            ncomp += 1
        elif int(m.sum()) == 250 and lo[2] > 840.0:
            celo2 = float(lo[1])                # celo druheho (zavreneho) supliku
    dv = np.unique(tri[sup1].ravel())
    if ncomp < 20 or celo2 is None or not len(dv):
        return pos                              # neznama struktura - nic nemenit
    delta = celo2 - float(rel[dv][:, 1].min())
    if not 450.0 < delta < 560.0:
        return pos
    out = pos.copy()
    out[dv, 1] += np.float32(round(delta, 1))
    return out


_SUPLIK_SPODNI = {}


def _najdi_spodni_suplik(pos, tri):
    """Maska trojuhelniku SPODNIHO supliku (s delicimi pricky) v lokalnim meshi ocelove skrine (product_4956 / 4930 / 4957) + hloubka jeho korby (mm, lokalne podel y), nebo None
    (neznama struktura). Mesh ma samostatne souvisle komponenty: telo skrine (jedna velka), korby supliku (spodni hluboka 1148 trojuhelniku, y 19-549, s 87 dily delicich pricek
    po 28 trojuhelnicich; horni mensi 602 trojuhelniku bez pricek; x > 400, y > 300, vyska < 150 mm), jejich rukojeti (x > 400), drobne dily (kolejnice) a zamek (u celni hrany
    y < 12, mimo supliky). Spodni suplik = korba s NEJNIZSIM z + vse, co lezi v jejim pasmu (z od jejiho spodku do +30 mm nad horni okraj) a neni zamek; u skrine s jednim
    suplikem je to ten jediny. Overeno na vsech trech modelech (viz scripts/2026-10-02_stul_testy/test_stul_suplik_klik.py). Lokalni predek skrine je -y (cela supliku maji nizke y)."""
    komp = _souvisle_komponenty(pos, tri)
    p64 = pos.astype(np.float64)
    rel = p64 - p64.min(axis=0)
    info = []
    for r in np.unique(komp):
        m = komp == r
        vs = np.unique(tri[m].ravel())
        info.append((int(r), int(m.sum()), rel[vs].min(axis=0), rel[vs].max(axis=0)))
    korby = [i for i in info if i[1] >= 500 and (i[3][0] - i[2][0]) > 400 and (i[3][1] - i[2][1]) > 300 and (i[3][2] - i[2][2]) < 150]
    if not korby:
        return None
    spodni = min(korby, key=lambda i: i[2][2])
    cleni = [spodni[0]]
    rukojet = False
    for r, n, lo, hi in info:
        if r == spodni[0] or n >= 500:
            continue
        if lo[2] < spodni[2][2] - 1.0 or hi[2] > spodni[3][2] + 30.0:
            continue
        if (hi[1] - lo[1]) < 12.0 and lo[1] < 3.0:
            continue                                                  # zamek skrine u celni hrany
        cleni.append(r)
        if n >= 60 and (hi[0] - lo[0]) > 400:
            rukojet = True
    maska = np.isin(komp, cleni)
    if not rukojet or not 600 <= int(maska.sum()) <= 5000:
        return None
    return maska, float(spodni[3][1] - spodni[2][1])


def _suplik_spodni(part_id):
    """(maska trojuhelniku, hloubka korby) spodniho supliku skrine `part_id`, nebo None (viz _najdi_spodni_suplik); vysledek se pocita jednou."""
    if part_id not in _SUPLIK_SPODNI:
        try:
            pos, _n, tri = nacti_mesh(part_id)
            _SUPLIK_SPODNI[part_id] = _najdi_spodni_suplik(pos, tri)
        except Exception:                                             # neznama / poskozena struktura = bez pohybu, model se postavi jako dosud
            _SUPLIK_SPODNI[part_id] = None
    return _SUPLIK_SPODNI[part_id]


def _rozdel_podle_masky(p, n, tri, maska):
    """((P, N, T) trojuhelniku mimo masku, (P, N, T) trojuhelniku v masce): kazda cast jen s vlastnimi vrcholy (v puvodnim poradi), indexy prepocitane."""
    def cast(m):
        t = tri[m]
        pouzite = np.unique(t.ravel())
        nove = np.full(len(p), -1, np.int64)
        nove[pouzite] = np.arange(len(pouzite))
        return p[pouzite], n[pouzite], nove[t]
    return cast(~maska), cast(maska)


# PLASTOVY KUZEL STAVITELNE PATKY (Robert 2026-10-08: "stavitelne patky se skladaji ze dvou casti: sroub s maticí a plastovy kuzel - dat do cerne barvy"): katalogovy GLB patky (3251 = M8, 3283 = M10) je
# JEDEN svareny mesh bez materialu (souvisla komponenta, nejde rozdelit podle spojitosti), proto se kuzel pozna GEOMETRICKY: je to cast pod rovinou horni plochy kuzele (plocha mezikruzi s trojuhelniky
# presne v y = rovina, pod ni zaobleny okraj a kuzel az po disk na podlaze; nad ni sroub M8 / M10 a sestihranna matice). Rovina v LOKALNICH souradnicich dilu (puvod = horni stred zavitu, patka roste do -y),
# zjistena z profilu polomeru: 3251 -> y = -50 (kuzel -75..-50, polomer 20,5), 3283 -> y = -48 (kuzel -79..-48, polomer 30). Trojuhelnik patri kuzeli, kdyz jeho TEZISTE je v y <= rovina + 0,001.
KUZEL_PATKY = {"product_3251": -50.0, "product_3283": -48.0}
MATERIAL_KUZELE = "cerna"                                  # cerny plast (stejny material jako zaslepky): v GLB uz je i v renderech, zadny novy klic materialu
_KUZEL_MASKA = {}


def _kuzel_patky(part_id):
    """Maska trojuhelniku (np.bool_, delka = pocet trojuhelniku dilu) plastoveho kuzele patky `part_id`, nebo None (dil kuzel nema / struktura nesedi = bez rozdeleni, model se postavi jako dosud)."""
    y0 = KUZEL_PATKY.get(part_id)
    if y0 is None:
        return None
    if part_id not in _KUZEL_MASKA:
        try:
            pos, _n, tri = nacti_mesh(part_id)
            maska = pos[tri][:, :, 1].mean(axis=1) <= y0 + 1e-3
            _KUZEL_MASKA[part_id] = maska if (maska.any() and not maska.all()) else None
        except Exception:                                             # noqa: BLE001 - chybejici / poskozeny GLB patky: bez rozdeleni
            _KUZEL_MASKA[part_id] = None
    return _KUZEL_MASKA[part_id]


def _hladke_normaly(pos, tri):
    n = np.zeros_like(pos)
    v0, v1, v2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    fn = np.cross(v1 - v0, v2 - v0)
    for k in range(3):
        np.add.at(n, tri[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return (n / ln).astype(np.float32)


# ---------------------------------------------------------------------------------------------------------------------
# skladani
# ---------------------------------------------------------------------------------------------------------------------
def kanonicky_hash(parametry):
    """Hash konfigurace: normalizovane parametry + verze pravidel (zaokrouhleno, razene) - stejna konfigurace = stejny hash."""
    p = S._norm_parametry(parametry)
    sys_ = p["system"]                                     # pravidla stolu (prahy) jsou PO SYSTEMECH: hash bere prahy systemu konfigurace
    if p["system"] == S.SYSTEM_VYCHOZI:                    # system 30: klic se do hashe nepocita (hashe stolu systemu 30 zustavaji jako pred zavedenim systemu); 40 ma vlastni hashe
        p.pop("system", None)
    for n in range(1, S.MAX_VYREZU + 1):               # vypnuty vyrez nema na model vliv: jeho rozmery se do hashe nepocitaji
        if not p[f"vyrez{n}"]:
            for sfx in ("w", "d", "x", "z"):
                p[f"vyrez{n}_{sfx}"] = S.VYCHOZI[f"vyrez{n}_{sfx}"]
            p[f"vyrez{n}_police"] = False                  # police pod vypnutym vyrezem neexistuje
    if not p["loz"]:                                       # vypnute loziskove jednotky: rozteč a okraj se do hashe nepocitaji
        p["loz_rozteca"], p["loz_okraj"] = S.VYCHOZI["loz_rozteca"], S.VYCHOZI["loz_okraj"]
    if not p["vzpery"]:                                    # vypnute vzpery: klice se do hashe nepocitaji vubec (hash konfigurace bez vzper zustava jako pred jejich pridanim)
        p.pop("vzpery", None)
        p.pop("vzpera_delka", None)
    if not p["navlek"]:                                    # bez navleku nohou (jekl, jen system 35) se klice do hashe nepocitaji (hashe stolu bez navleku zustavaji jako pred jeho pridanim)
        p.pop("navlek", None)
        p.pop("navlek_delka", None)
    if not (p["suplik"] and p["suplik_vlevo"]):                # suplikovy box na leve strane: bez supliku nebo vpravo se klic do hashe nepocita (hashe stolu bez nej zustavaji)
        p.pop("suplik_vlevo", None)
    if not p["suplik"] or p["suplik_pocet"] == S.SUPLIK_POCET_VYCHOZI:      # pocet supliku (Robert 2026-10-05): bez supliku nebo vychozi dvojsuplik se klic do hashe nepocita (hashe stolu s dvojsuplikem zustavaji)
        p.pop("suplik_pocet", None)
    if p["led_svetlo"] or not (p["led"] and p["stojky"]):          # svitidlo LED pryc (ramena zustavaji): do hashe jen kdyz je to opravdu vypnute (hashe stolu s svitidlem beze zmeny)
        p.pop("led_svetlo", None)
    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)):          # RUCNI svitidla LED (Robert 2026-10-08): bez svitidla se pocet ani polohy do hashe nepocitaji
        p.pop("led_pocet", None)
        for k_led in S.LED_PARAMETRY_Z:
            p.pop(k_led, None)
    else:
        n_led = int(p["led_pocet"])
        if n_led == 1 and S.led_max_pocet(p["sirka"], S.led_telo_dilu(S.LED_TYPY[S._led_delka_int(p["led_delka"])])) == 1:          # vejde se jen jedno svitidlo: pocet nic nemeni (hashe uzkych stolu zustavaji jako pred rucnimi svitidly); u sirsiho stolu se klic nese - drive tam byl pocet automaticky
            p.pop("led_pocet", None)
        for j, k_led in enumerate(S.LED_PARAMETRY_Z, 1):                      # poloha svitidla: automaticka (None) / pro neexistujici svitidlo se do hashe nepocita
            if p.get(k_led) is None or j > n_led:
                p.pop(k_led, None)
    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)) or int(round(p["led_delka"])) == S.LED_DELKA_VYCHOZI:          # delka svitidla LED (Robert 2026-10-07): vychozi 1200 / bez svitidla se do hashe nepocita (hashe stolu s LED 1200 zustavaji)
        p.pop("led_delka", None)
    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:           # police BEZ DESKY (Robert 2026-10-07): do hashe jen kdyz opravdu bez desky (hashe stolu s deskou zustavaji); bez polic a v SSE volba nic nedela
        p.pop("police_deska", None)
    for j in range(1, 11):                                     # vyska polic: nezadana (None) / pro neexistujici polici se do hashe nepocita (hashe stolu bez teto volby zustavaji)
        if p.get(f"police_h{j}") is None or j > p["police"]:
            p.pop(f"police_h{j}", None)
    if not p["drzak_pet"] or (p["pet_noha"] == "PL" and p["pet_strana"] == "vpravo"):          # umisteni drzaku PET: vychozi (predni leva noha, strana vpravo) nebo bez drzaku se do hashe nepocita
        p.pop("pet_noha", None)
        p.pop("pet_strana", None)
    if not (p["drzak_pet"] and p["pet_posun"]):                # svisly posun drzaku PET: nulovy / bez drzaku se do hashe nepocita
        p.pop("pet_posun", None)
    if not (p["panely"] and p["stojky"]):                      # panely: pocet, posun a elektrozlab (jeho posun) se bez panelu / stojek do hashe nepocitaji
        p.pop("panely_pocet", None)
        p.pop("panely_posun", None)
        p["elzlab_y"], p["elzlab_z"] = 0.0, 0.0
    if not (p["panely"] and p["stojky"]) or int(round(p["panely_delka"])) == S.PANEL_DELKA_VYCHOZI:          # delka panelu (Robert 2026-10-07): vychozi 1190 / bez panelu se do hashe nepocita (hashe stolu s panely 1190 zustavaji)
        p.pop("panely_delka", None)
    if not (p["panely"] and p["stojky"] and p["panely_z"]):    # vodorovny posun panelu (Robert 2026-10-05): nulovy / bez panelu se klic do hashe nepocita (hashe stolu s vystredenymi panely zustavaji)
        p.pop("panely_z", None)
    if not p["elektrozlab"]:
        p["elzlab_y"], p["elzlab_z"] = 0.0, 0.0
    if p["sirka"] <= S.prah_sirky(sys_):                       # stredni opora (noha / ram / auto) existuje jen u sirokeho stolu
        p["stredni_opora"] = "auto"
    if not p["stojky"]:
        p["stojky_vyska"] = S.VYCHOZI["stojky_vyska"]          # bez zadnich stojek vyska stojek nic nedela
    p = S._hpol().kanon_hash(p)                            # horni police (Robert 2026-10-07): klice se do hashe nepocitaji, dokud neni zapnuta (hashe stolu bez police zustavaji)
    kanon = {k: (round(v, 1) if isinstance(v, float) else v) for k, v in sorted(p.items())}
    kanon["_v"] = RULES_VERSION
    if not p["stojky"] and sys_ != S.SYSTEM_SSE:                                    # BEZ zadnich stojek deska pokracuje dozadu o tloustku profilu (Robert 2026-10-08): jiny model / cena -> jiny hash a kod; hashe stolu SE stojkami beze zmeny
        kanon["_deska_zad"] = int(S.SYSTEMY[sys_]["profil_mm"])
    if S.prah_sirky(sys_) != min(S.pravidla_vychozi(sys_)["sirka_stredni_noha"], S.max_delka_desky()):              # nastavitelny prah sirky pro stredni nohu (v systemu konfigurace) meni vysledek -> jiny hash (vuci vychozi hodnote SYSTEMU: SSE ma 2000)
        kanon["_prah_s"] = int(S.prah_sirky(sys_))
    if S.tabule() != S.TABULE_VYCHOZI:                                              # format tabule laminodesky (karta 4933) meni, co se vejde a kde se desky deli -> jiny hash
        kanon["_tab"] = [int(v) for v in S.tabule()]
    if sys_ != S.SYSTEM_SSE and S.prah_hloubky(sys_) != S.PRAVIDLA_VYCHOZI["hloubka_stredni_profil"]:      # nastavitelny prah hloubky (Robert) meni vysledek -> jiny hash/kod; vychozi hodnota hash nemeni (SSE ho nepouziva)
        kanon["_prah_h"] = int(S.prah_hloubky(sys_))
    if S.SYSTEMY[sys_].get("hluboky") and S.prah_hloubky_noha(sys_) != S.pravidla_vychozi(sys_)["hloubka_stredni_noha"]:          # system 45: nastavitelny prah stredni rady noh meni vysledek -> jiny hash/kod
        kanon["_prah_hn"] = int(S.prah_hloubky_noha(sys_))
    if sys_ != S.SYSTEM_SSE and S.podpera_max_rozpon(sys_) != S.pravidla_vychozi(sys_)["podpera_max_rozpon"]:                      # nejvetsi nepodepreny usek meni pocet podper -> jiny hash/kod
        kanon["_podp"] = int(S.podpera_max_rozpon(sys_))
    return hashlib.sha256(json.dumps(kanon, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _transformuj(part_id, cast):
    pos, nrm, tri = nacti_mesh(part_id)
    Rm = S.kvat_na_matici(cast["quaternion"])
    s = np.array(cast["scale"], float)
    p = (pos.astype(np.float64) * s) @ Rm.T + np.array(cast["position"], float)
    # normaly: R * (n / s) (inverzne transponovana matice pro nerovnomerne meritko)
    n = (nrm.astype(np.float64) / s) @ Rm.T
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return p, n / ln, tri


def _deska_s_otvory(kusy):
    """JEDEN souvisly povrch pracovni desky s vyrezy z kusu desky (obdelniky): horni/spodni plocha po bunkach spolecne site (bez prechodu mezi kusy =
    zadne svy), steny jen tam, kde souseda neni (obvod desky a okraje otvoru). Hrany jsou ostre (kusy z katalogoveho meshe maji zkoseni, ktere by se u
    dotykajicich kusu zobrazilo jako svy). Vraci (pozice Nx3, normaly Nx3, trojuhelniky Mx3) ve svetovych souradnicich (mm)."""
    boxy = [S._aabb(c) for c in kusy]
    xs = sorted({round(float(v), 2) for lo, hi in boxy for v in (lo[0], hi[0])})
    zs = sorted({round(float(v), 2) for lo, hi in boxy for v in (lo[2], hi[2])})
    y0 = float(min(lo[1] for lo, hi in boxy))
    y1 = float(max(hi[1] for lo, hi in boxy))

    def kryta(i, j):
        if not (0 <= i < len(xs) - 1 and 0 <= j < len(zs) - 1):
            return False
        cx, cz = (xs[i] + xs[i + 1]) / 2.0, (zs[j] + zs[j + 1]) / 2.0
        return any(lo[0] < cx < hi[0] and lo[2] < cz < hi[2] for lo, hi in boxy)

    P, N, T = [], [], []

    def ctyruhelnik(v, n):
        v = np.array(v, float)
        hrana1, hrana2 = v[1] - v[0], v[2] - v[0]
        if np.dot(np.cross(hrana1, hrana2), n) < 0:
            v = v[::-1]
        b = len(P)
        P.extend(v.tolist()); N.extend([n] * 4)
        T.extend([[b, b + 1, b + 2], [b, b + 2, b + 3]])

    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            if not kryta(i, j):
                continue
            xa, xb, za, zb = xs[i], xs[i + 1], zs[j], zs[j + 1]
            ctyruhelnik([(xa, y1, za), (xb, y1, za), (xb, y1, zb), (xa, y1, zb)], (0.0, 1.0, 0.0))
            ctyruhelnik([(xa, y0, za), (xb, y0, za), (xb, y0, zb), (xa, y0, zb)], (0.0, -1.0, 0.0))
            for (di, dj, n, q) in ((1, 0, (1.0, 0.0, 0.0), [(xb, y0, za), (xb, y1, za), (xb, y1, zb), (xb, y0, zb)]),
                                   (-1, 0, (-1.0, 0.0, 0.0), [(xa, y0, za), (xa, y1, za), (xa, y1, zb), (xa, y0, zb)]),
                                   (0, 1, (0.0, 0.0, 1.0), [(xa, y0, zb), (xa, y1, zb), (xb, y1, zb), (xb, y0, zb)]),
                                   (0, -1, (0.0, 0.0, -1.0), [(xa, y0, za), (xa, y1, za), (xb, y1, za), (xb, y0, za)])):
                if not kryta(i + di, j + dj):
                    ctyruhelnik(q, n)
    return np.array(P, float), np.array(N, float), np.array(T, np.int64)


def _koty_v_glb(koty, posun):
    """Koty generatoru (souradnice generatoru) -> `dims` ve spec v3d: konce mereni se posunou o `posun` (stejne jako model), `o` (posun cary) a `t` zustavaji."""
    out = []
    for k in koty or []:
        d = {"a": [round(float(k["a"][i]) + float(posun[i]), 3) for i in range(3)], "b": [round(float(k["b"][i]) + float(posun[i]), 3) for i in range(3)],
             "o": [round(float(x), 3) for x in k["o"]], "t": k["t"], "l": int(k["l"])}
        if "m" in k:
            d["m"] = float(k["m"])
        out.append(d)
    return out


def poskladej_glb(dily, rozmery=None, koty=None, razitka=None):
    """GLB (bytes) z dilu ve formatu custom_shapes.data.parts (viz modul). `koty` = koty ve spec v3d (stul_koty.koty: souradnice generatoru, tady se posunou stejne jako model);
    bez nich viewer3d.js kresli jen 3 obalkove koty (sirka, hloubka, vyska). `razitka` = seznam razitek z stul_razitka.razitka (jen model v online nabidce, Robert 2026-10-06): vypln drazky
    pod logem jako kvadr ve skupine hlinik, logo jako instance JEDNOHO sdileneho meshe (vlastni material, uzel n<i>) - soubor nenaroste o desitky MB."""
    skupiny = {m: {"P": [], "N": [], "T": [], "base": 0} for m in POREDI_MATERIALU}
    kusy_desky = {}                                  # hladina (spodni plocha desky, mm) -> kusy rozrezanych desek; kazda hladina = jeden souvisly povrch (pracovni deska s vyrezy, police s vyrezem pro ram...)
    rozsahy = []                                     # (material, od, pocet) pro kazdy dil; deska s otvory = None (jeden souvisly povrch, nejde posouvat po dilech)
    kuzele = []                                      # (index dilu, material, od, pocet): plastovy kuzel patky = DALSI rozsah dilu v materialu "cerna" (viz _kuzel_patky); jde do extra rozsahu (zive tazeni ho hybe s dilem)
    suplik_otev = None                               # spodni suplik boxu (s delicimi pricky) jako vlastni uzel s pohybem na klik (viz _suplik_spodni); jen jeden box
    for cast in dily:
        if cast.get("deska_celek") or cast.get("deska_kus"):
            kusy_desky.setdefault(round(float(S._aabb(cast)[0][1]), 1), []).append(cast)       # deska rozrezana na kusy: jeden souvisly povrch PO HLADINACH (viz _deska_s_otvory; ruzne vysky nesmi splynout v jeden blok)
            rozsahy.append(None)
            continue
        mat = MATERIAL_DILU.get(cast["part_id"], "ocel")
        p, n, tri = _transformuj(cast["part_id"], cast)
        g = skupiny[mat]
        hs_ = _suplik_spodni(cast["part_id"]) if (suplik_otev is None and cast["part_id"] in S.SUPLIK_PARTY_VSE) else None
        if hs_ is not None:
            (p_b, n_b, t_b), (p_d, n_d, t_d) = _rozdel_podle_masky(p, n, tri, hs_[0])
            rozsahy.append((mat, g["base"], len(p_b)))                 # rozsah dilu = jen telo skrine; suplik ma vlastni uzel (DALSI rozsah v _POSLEDNI_EXTRA)
            g["P"].append(p_b); g["N"].append(n_b); g["T"].append(t_b + g["base"])
            g["base"] += len(p_b)
            Rm = S.kvat_na_matici(cast["quaternion"])
            sc_ = np.array(cast["scale"], float)
            osa = (np.array([0.0, -1.0, 0.0]) * sc_) @ Rm.T                # lokalni predek skrine (-y) ve svete
            suplik_otev = {"idx": len(rozsahy) - 1, "mat": mat, "P": p_d, "N": n_d, "T": t_d, "osa": osa / np.linalg.norm(osa),
                           "v": round(min(SUPLIK_OTEVRENI_MAX_MM, SUPLIK_OTEVRENI_PODIL * hs_[1] * abs(float(sc_[1]))), 1)}
            continue
        km_ = _kuzel_patky(cast["part_id"])
        if km_ is not None:                                            # stavitelna patka: sroub s maticí zustava v materialu dilu, plastovy kuzel jde do "cerna" (rozsah dilu = jen sroub, kuzel = extra rozsah)
            (p_s, n_s, t_s), (p_k, n_k, t_k) = _rozdel_podle_masky(p, n, tri, km_)
            gk = skupiny[MATERIAL_KUZELE]
            rozsahy.append((mat, g["base"], len(p_s)))
            g["P"].append(p_s); g["N"].append(n_s); g["T"].append(t_s + g["base"])
            g["base"] += len(p_s)
            kuzele.append((len(rozsahy) - 1, MATERIAL_KUZELE, gk["base"], len(p_k)))
            gk["P"].append(p_k); gk["N"].append(n_k); gk["T"].append(t_k + gk["base"])
            gk["base"] += len(p_k)
            continue
        rozsahy.append((mat, g["base"], len(p)))
        g["P"].append(p); g["N"].append(n); g["T"].append(tri + g["base"])
        g["base"] += len(p)
    for hladina in sorted(kusy_desky):
        p, n, tri = _deska_s_otvory(kusy_desky[hladina])
        g = skupiny[MATERIAL_DILU["product_4933"]]
        g["P"].append(p); g["N"].append(n); g["T"].append(tri + g["base"])
        g["base"] += len(p)
    vyplne_rozsahy = []                              # (od, pocet) vrcholu vyplne kazdeho razitka v uzlu hlinik (zive tazeni je hybe s dilem)
    for rz in (razitka or []):                       # vypln drazky pod logem (kvadr: x podel profilu = delka loga, y = otvor drazky, z = hloubka k dnu hrdla), souvisla se stenou profilu
        L_, W_, D_ = rz["vypln"]["rozmer"]
        Pm, Nm, Tm = _mesh_kvadr((-L_ / 2.0, -W_ / 2.0, -D_ / 2.0), (L_ / 2.0, W_ / 2.0, D_ / 2.0))
        Rv = S.kvat_na_matici(rz["vypln"]["q"])
        g = skupiny["alu"]
        g["P"].append(Pm.astype(np.float64) @ Rv.T + np.array(rz["vypln"]["pos"], float))
        g["N"].append(Nm.astype(np.float64) @ Rv.T)
        g["T"].append(Tm + g["base"])
        vyplne_rozsahy.append((g["base"], len(Pm)))
        g["base"] += len(Pm)
    vsechny = np.vstack([np.vstack(g["P"]) for g in skupiny.values() if g["P"]])
    lo, hi = vsechny.min(axis=0), vsechny.max(axis=0)
    posun = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -(lo[2] + hi[2]) / 2.0])
    box_lo, box_hi = lo + posun, hi + posun
    _POSLEDNI_POSUN[0] = posun.copy()
    uzel_materialu = {}
    for mat in POREDI_MATERIALU:
        if skupiny[mat]["P"]:
            uzel_materialu[mat] = len(uzel_materialu)                       # poradi uzlu v GLB = poradi neprazdnych materialu (viz nodes nize)
    _POSLEDNI_ROZSAHY[0] = [None if r_ is None else [uzel_materialu[r_[0]], r_[1], r_[2]] for r_ in rozsahy]

    blob = bytearray()
    views, accessors, meshes, nodes, materials = [], [], [], [], []
    mat_index = {}                                   # material (jmeno) -> index v `materials`

    def pridej(data, target):
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        return len(views) - 1

    for mat in POREDI_MATERIALU:
        g = skupiny[mat]
        if not g["P"]:
            continue
        P = (np.vstack(g["P"]) + posun).astype("<f4")
        N = np.vstack(g["N"]).astype("<f4")
        T = np.vstack(g["T"]).astype("<u4").ravel()
        vp = pridej(P.tobytes(), 34962)
        vn = pridej(N.tobytes(), 34962)
        vi = pridej(T.tobytes(), 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(P), "type": "VEC3",
                          "min": [float(x) for x in P.min(axis=0)], "max": [float(x) for x in P.max(axis=0)]})
        a_pos = len(accessors) - 1
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(N), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(T), "type": "SCALAR"})
        materials.append({"pbrMetallicRoughness": dict(MATERIALY[mat])})
        mat_index[mat] = len(materials) - 1
        meshes.append({"primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_pos + 1}, "indices": a_pos + 2,
                                       "material": len(materials) - 1, "mode": 4}]})
        nodes.append({"name": f"n{len(nodes)}", "mesh": len(meshes) - 1})

    # spodni suplik boxu (s delicimi pricky): vlastni uzel pod prazdnym pivotem p1 + pohyb k=drawer (T podel predku skrine): v prohlizeci se na klik vysune a dalsim klikem zasune (viewer3d.js: motions[].pick)
    motions, potomci, extra = [], set(), {}
    for idx_, mat_, od_, n_ in kuzele:                               # plastovy kuzel patky: dalsi rozsah dilu v uzlu materialu "cerna" (zive tazeni: hybe se spolu s patkou)
        extra[idx_] = [[uzel_materialu[mat_], od_, n_]]
    if suplik_otev is not None:
        sg = suplik_otev
        Pd = (sg["P"] + posun).astype("<f4")
        Nd = sg["N"].astype("<f4")
        Td = sg["T"].astype("<u4").ravel()
        vp = pridej(Pd.tobytes(), 34962)
        vn = pridej(Nd.tobytes(), 34962)
        vi = pridej(Td.tobytes(), 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(Pd), "type": "VEC3",
                          "min": [float(x) for x in Pd.min(axis=0)], "max": [float(x) for x in Pd.max(axis=0)]})
        a_pos = len(accessors) - 1
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(Nd), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(Td), "type": "SCALAR"})
        meshes.append({"primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_pos + 1}, "indices": a_pos + 2, "material": mat_index[sg["mat"]], "mode": 4}]})
        nodes.append({"name": f"n{len(nodes)}", "mesh": len(meshes) - 1})
        uzel_s = len(nodes) - 1
        nodes.append({"name": "p1", "children": [uzel_s]})
        potomci.add(uzel_s)
        extra[sg["idx"]] = [[uzel_s, 0, len(Pd)]]
        motions.append({"id": "m1", "k": "drawer", "n": 1, "pick": ["p1"],
                        "steps": [{"p": "p1", "op": "T", "ax": [round(float(x), 6) for x in sg["osa"]], "v": sg["v"], "ms": SUPLIK_OTEVRENI_MS}]})
    _POSLEDNI_EXTRA[0] = extra or None
    _POSLEDNI_RAZITKA[0] = None

    if razitka:                                      # loga: JEDEN mesh (katalogove GLB loga) + instance uzlu s polohou a otocenim; material oranzovy elox. hlinik, uzly jmenem n<i> (sanitizer / final_check)
        import stul_razitka as RZ
        Pl, Nl, Tl = nacti_mesh(RZ.LOGO_PART)
        Pl, Nl, Tl = Pl.astype("<f4"), Nl.astype("<f4"), Tl.astype("<u4").ravel()
        vp = pridej(Pl.tobytes(), 34962)
        vn = pridej(Nl.tobytes(), 34962)
        vi = pridej(Tl.tobytes(), 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(Pl), "type": "VEC3",
                          "min": [float(x) for x in Pl.min(axis=0)], "max": [float(x) for x in Pl.max(axis=0)]})
        a_pos = len(accessors) - 1
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(Nl), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(Tl), "type": "SCALAR"})
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": RZ.LOGO_BARVA, "metallicFactor": RZ.LOGO_KOVOVOST, "roughnessFactor": RZ.LOGO_DRSNOST}})
        meshes.append({"primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_pos + 1}, "indices": a_pos + 2, "material": len(materials) - 1, "mode": 4}]})
        mesh_loga = len(meshes) - 1
        info_razitek = []
        for k_, rz in enumerate(razitka):
            info_razitek.append({"dil": rz.get("dil"), "uzel": len(nodes), "vypln": [uzel_materialu["alu"], int(vyplne_rozsahy[k_][0]), int(vyplne_rozsahy[k_][1])]})
            nodes.append({"name": f"n{len(nodes)}", "mesh": mesh_loga, "rotation": [round(float(v), 7) for v in rz["logo"]["q"]],
                          "translation": [round(float(v), 4) for v in (np.array(rz["logo"]["pos"], float) + posun)]})
        _POSLEDNI_RAZITKA[0] = info_razitek

    sirka = float(box_hi[2] - box_lo[2])
    hloubka = float(box_hi[0] - box_lo[0])
    vyska = float(box_hi[1])
    spec = {
        "v": 1, "u": "mm", "up": [0, 1, 0], "front": [-1, 0, 0],
        "box": {"min": [round(float(x), 3) for x in box_lo], "max": [round(float(x), 3) for x in box_hi]},
        "look": "nat",
        "dims": _koty_v_glb(koty, posun),      # bez kot viewer3d vytvori 3 obalkove (sirka/hloubka/vyska) sam z obalky v ramu cela; viz stul_koty
        "motions": motions,
    }
    js = {"asset": {"version": "2.0"}, "scene": 0,
          "scenes": [{"nodes": [i for i in range(len(nodes)) if i not in potomci], "extras": {"v3d": spec}}],
          "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors, "bufferViews": views,
          "buffers": [{"byteLength": len(blob)}]}
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    while len(blob) % 4:
        blob.append(0)
    celkem = 12 + 8 + len(jb) + 8 + len(blob)
    return (struct.pack("<III", GLB_MAGIC, GLB_VERSION, celkem) + struct.pack("<II", len(jb), 0x4E4F534A) + jb +
            struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


RAZITKA_VYCHOZI = True                                        # WORKFLOW pravidlo 61 (Robert 2026-10-08: "razitka budou na vsech 3D modelech ve vsech generatorech"): logo LOGIMAN.CZ na profilech u ziveho modelu, kosiku, nabidky i karet; False jen na Robertuv pokyn
_GLB_RAZITKA_CACHE = OrderedDict()                            # hash -> GLB S razitky; oddelene od cache modelu bez razitek (_GLB_CACHE). Vedlejsi cache (posun, rozsahy, extra) jsou SPOLECNE pro oba modely (razitka je nemeni, overuje regrese)


def model_pro_parametry(parametry, razitka=None):
    """(hash, bytes GLB) pro parametry konfigurace; LRU cache podle kanonickeho hashe. `razitka=None` = VYCHOZI NASTAVENI GENERATORU (RAZITKA_VYCHOZI = True: logo LOGIMAN.CZ na profilech - zivy model, kosik, nabidka,
    karta; WORKFLOW pravidlo 61, Robert 2026-10-08, pravidla umisteni stul_razitka beze zmeny), True / False se predava vyslovne (False = holy model bez razitek: testy geometrie, srovnani). Model s razitky a bez nich
    ma kazdy SVOU cache (razitka nejsou soucasti hashe konfigurace, jsou z nej odvozena); `vodici`, uchyty a zive tazeni ctou posun / rozsahy / extra z cache SPOLECNYCH - razitka zadny dil neposouvaji (jsou jen pripojena
    na konec materialu hlinik a jako dalsi uzly), takze model s razitky je plnohodnotny verejny model. Vyhodi StulChyba/GlbChyba."""
    if razitka is None:
        razitka = RAZITKA_VYCHOZI
    h = kanonicky_hash(parametry)
    if razitka:
        if h in _GLB_RAZITKA_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE and h in _RAZITKA_CACHE:
            for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE, _RAZITKA_CACHE):
                c_.move_to_end(h)                              # vsechny ctyri cache se drzi spolecne (jinak by `vodici` pro horky model ztratilo posun a vratilo None)
            return h, _GLB_RAZITKA_CACHE[h]
        import stul_razitka
        r = S.sestav_stul(**parametry)
        data = poskladej_glb(r["dily"], r["rozmery"], stul_koty.koty(r), razitka=stul_razitka.razitka(r, h))
        _GLB_RAZITKA_CACHE[h] = data
        _META_CACHE[h] = _POSLEDNI_POSUN[0]
        _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]
        _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}
        _RAZITKA_CACHE[h] = _POSLEDNI_RAZITKA[0] or []
        for c_ in (_GLB_RAZITKA_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE, _RAZITKA_CACHE):
            while len(c_) > CACHE_MAX:
                c_.popitem(last=False)
        return h, data
    if h in _GLB_CACHE and h in _META_CACHE and h in _ROZSAHY_CACHE and h in _EXTRA_CACHE:
        for c_ in (_GLB_CACHE, _META_CACHE, _ROZSAHY_CACHE, _EXTRA_CACHE):
            c_.move_to_end(h)                              # vsechny tri cache se drzi spolecne (jinak by `vodici` pro horky model ztratilo posun a vratilo None)
        return h, _GLB_CACHE[h]
    r = S.sestav_stul(**parametry)
    data = poskladej_glb(r["dily"], r["rozmery"], stul_koty.koty(r))
    _GLB_CACHE[h] = data
    _META_CACHE[h] = _POSLEDNI_POSUN[0]
    _ROZSAHY_CACHE[h] = _POSLEDNI_ROZSAHY[0]
    _EXTRA_CACHE[h] = _POSLEDNI_EXTRA[0] or {}
    while len(_EXTRA_CACHE) > CACHE_MAX:
        _EXTRA_CACHE.popitem(last=False)
    while len(_GLB_CACHE) > CACHE_MAX:
        _GLB_CACHE.popitem(last=False)
    while len(_META_CACHE) > CACHE_MAX:
        _META_CACHE.popitem(last=False)
    while len(_ROZSAHY_CACHE) > CACHE_MAX:
        _ROZSAHY_CACHE.popitem(last=False)
    return h, data


def vyber_kodovani(accept_encoding):
    """Kodovani odpovedi podle hlavicky Accept-Encoding: 'br' (kdyz je brotli a klient ho umi), jinak 'gzip', jinak None (q=0 = zakazano; '*' = cokoli).
    GLB stolu je z velke casti opakovana geometrie (profily, spojky): gzip ho zmensi na ~20 %, brotli na ~14 % (4,7 MB -> 0,7 MB) - prenos modelu, ne vypocet, byl to, co
    zakaznika zdrzovalo (Robert 2026-10-04: \"model stolu se tam nacita dlouho\")."""
    q = {}
    for cast in str(accept_encoding or "").split(","):
        jmeno, _, parametry = cast.strip().partition(";")
        jmeno = jmeno.strip().lower()
        if not jmeno:
            continue
        hodnota = 1.0
        for par in parametry.split(";"):
            k, _, v = par.strip().partition("=")
            if k.strip().lower() == "q":
                try:
                    hodnota = float(v)
                except ValueError:
                    hodnota = 0.0
        q[jmeno] = hodnota
    def ok(jmeno):
        return q.get(jmeno, q.get("*", 0.0)) > 0.0
    if _brotli is not None and ok("br"):
        return "br"
    if ok("gzip") or ok("x-gzip"):
        return "gzip"
    return None


def zakoduj_pro_klienta(h, data, accept_encoding):
    """(bytes, kodovani | None): GLB zkomprimovany podle Accept-Encoding (viz vyber_kodovani); bytes se drzi v LRU podle (hash, kodovani, delka dat), takze se stejny model nekomprimuje dvakrat a model s razitky se nezamění s modelem bez nich.
    Vysledek je deterministicky (gzip bez casu), dekomprimovany == `data`."""
    kod = vyber_kodovani(accept_encoding)
    if kod is None or len(data) < KOMPR_MIN:
        return data, None
    klic = (h, kod, len(data))                                       # model S razitky a BEZ nich maji stejny hash, ale jina data: klic nese i delku dat
    z = _GLB_KOMPR.get(klic)
    if z is None:
        z = _brotli.compress(data, quality=5, lgwin=24) if kod == "br" else gzip.compress(data, 4, mtime=0)
        _GLB_KOMPR[klic] = z
        while len(_GLB_KOMPR) > KOMPR_CACHE_MAX:
            try:
                _GLB_KOMPR.popitem(last=False)
            except KeyError:
                break
    else:
        try:
            _GLB_KOMPR.move_to_end(klic)
        except KeyError:
            pass
    return z, kod


def _posun_ovladani(o, posun):
    """Prepocet popisu ovladani 3D (api/stul_konfigurator.ovladani_3d) z souradnic generatoru do souradnic GLB (vycentrovano, podlaha y = 0)."""
    def b(v):
        return [round(float(v[0] + posun[0]), 2), round(float(v[1] + posun[1]), 2), round(float(v[2] + posun[2]), 2)]
    out = dict(o)
    if "deska" in o:
        out["deska"] = dict(o["deska"], pocatek=b(o["deska"]["pocatek"]))
    out["casti"] = [dict(c, aabb=[b(c["aabb"][0]), b(c["aabb"][1])]) for c in o.get("casti", [])]
    out["tahy"] = [dict(t, bod=b(t["bod"])) for t in o.get("tahy", [])]
    return out


def vodici(parametry, vysledek):
    """Uchopovaci znacky a popis ovladani pro 3D (tazeni mysi, nabidka pravym tlacitkem), uz v souradnicich GLB (mm, vycentrovano, podlaha 0): `stredni_noha`
    (starsi tvar, jen kdyz stredni nohy jsou) a `ovladani` (casti + tahy, viz docs/OVLADANI_3D.md; jen kdyz je ve vysledku `ovladani_scena`). Vraci None,
    kdyz neni nic z toho. Volani sklada GLB (je v cache, pozdeji ho stejne prohlizec stahne)."""
    v = (vysledek or {}).get("vodici_scena")
    ov = (vysledek or {}).get("ovladani_scena")
    if not v and not ov:
        return None
    h, _ = model_pro_parametry(parametry)
    posun = _META_CACHE.get(h)
    if posun is None:
        return None
    out = {}
    if v:
        m = v["stredni_noha"]
        out["stredni_noha"] = {"x": round(m["x"] + posun[0], 2), "y": round(m["y"] + posun[1], 2), "z": round(m["z"] + posun[2], 2),
                               "z_levy": round(m["z_levy"] + posun[2], 2), "z_pravy": round(m["z_pravy"] + posun[2], 2), "rezim": m.get("rezim"),
                               "min": round(m["min"] + posun[2], 2), "max": round(m["max"] + posun[2], 2),
                               "zakazano": [[round(a + posun[2], 2), round(b + posun[2], 2)] for a, b in m.get("zakazano", [])]}
    if ov:
        out["ovladani"] = _posun_ovladani(ov, posun)
        roz = _ROZSAHY_CACHE.get(h)
        if roz is not None and any(t_.get("zive") for t_ in ov.get("tahy", [])):
            out["ovladani"]["zive_rozsahy"] = roz            # kde jsou vrcholy kazdeho dilu v GLB: prohlizec z toho pri tazeni hybe dily primo (docs/OVLADANI_3D.md)
            ex_ = _EXTRA_CACHE.get(h)
            if ex_:
                out["ovladani"]["zive_rozsahy_extra"] = {str(k_): v_ for k_, v_ in ex_.items()}      # dil rozdeleny do vice uzlu (spodni suplik boxu): dalsi rozsahy, hybou se spolu s dilem
            rz_ = _RAZITKA_CACHE.get(h) if RAZITKA_VYCHOZI else None
            if rz_:
                out["ovladani"]["razitka"] = rz_            # razitka (logo + vypln drazky) a dil, na kterem sedi: prohlizec je pri zivem tazeni hybe s dilem (docs/OVLADANI_3D.md; Robert 2026-10-08); jen kdyz je vychozi model S razitky
    try:                                                  # pracovni rovina a LED pro pocitadlo luxu (stul_osvetleni; stejny posun jako model); pomocna vec nesmi shodit verejnou odpoved
        osv = stul_osvetleni.osvetleni(vysledek, _transformuj)
        if osv:
            out["osvetleni"] = stul_osvetleni.v_glb(osv, posun)
    except Exception:
        logging.getLogger(__name__).exception("stul_glb.vodici: data pro pocitadlo luxu se nepodarilo sestavit")
    return out
