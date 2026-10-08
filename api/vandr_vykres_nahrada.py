"""Nahradni obrazky online nabidky z karty Vandr (bot10, 2026-10-02, Robert: "oprav si to").

DUVOD: Vandr obrazky (kotovany 2D vykres + 2 3D pohledy) generuje jen Unity klient pri ulozeni sestavy; u asi poloviny karet
(napr. #4053, #4482) existuje jen FBX export a sloupce image_2D_with_dim/image_3D_primary/image_3D_secondary jsou prazdne.
Endpoint POST /api/admin/vandr-vyroba/<id>/nabidka (api/vandr_scene_offers.py) proto pro chybejici obrazek pouzije NAHRADU,
kdyz Vandr obrazek existuje, ma PREDNOST Vandr (kombinace je povolena).

SAMOSTATNY modul (CLAUDE.md bod 6: vanDrawee logika a nase vlastni logika se nemicha): tady je jen NASE vlastni logika.
Jen numpy + PIL, zadny Blender, zadny Cycles/GPU render, zadna sit, zadna DB (vyber snimku je cista funkce nad radky,
cteni DB a souboru dela volajici).

VEREJNE FUNKCE
  vykres_nares(glb_bytes, front_az_deg=None) -> (png_bytes, info)
      KOTOVANY 2D VYKRES vyrobeny z cisteho GLB: vlevo NARYS (ortogonalne ve smeru predni strany, kota celkove sirky a vysky),
      vpravo BOKORYS (kota hloubky a vysky). Jednotky mm; cisla = skutecne rozmery modelu (AABB vsech vrcholu), tj. stejna cisla
      jako `rozmer_mm` v odpovedi endpointu. Plocha svetle seda, hrany dilu stredne seda, obrys tmavy, bile pozadi, 1600 x 1000 px,
      deterministicky (stejny vstup = stejne bajty PNG), ~2-4 s. Texty jen pevne ceske popisky a cisla - zadne jmeno dilu,
      SKU ani unity_id (v GLB zakaznicke ani nejsou).
  pohled_z_modelu(glb_bytes, az_deg, el_deg, sirka=1280, vyska=960) -> png_bytes
      posledni zaloha 3D pohledu (kdyz karta nema ani snimky otocky, ani fotky v galerii): ortogonalni stinovany pohled z daneho
      azimutu/elevace (kamera = azimut ve smyslu kontrola.html vdCameraDir: (sin az, 0, cos az)).
  vyber_snimky_otocky(radky, front_az_deg, existuje=None) -> {"a": radek, "b": radek} | None
      cista funkce: ze snimku otocky karty (product_turntable_frames, is_active=1) vybere dva 3D pohledy: zepredu doprava a zepredu
      doleva (azimut prednich stran +-35 st.), elevace nejblizsi 17,5 st., nejvetsi tier >= 1024 px s rozumnou velikosti souboru.

Souradnice: GLB je Y-up v mm (v3d spec u == "mm"; staticky GLB z scripts/2026-09-28_vandr_offer_geometry.py totez).
Predni strana: smer k zakaznikovi (fx, 0, fz) = scenes[0].extras.v3d.front, jinak z azimutu (sin a, 0, cos a) jako vandr_offer_build /
kontrola.html (vandr_predni_azimut_deg), jinak odhad z geometrie. Vpravo z pohledu zakaznika: r = (-f) x up.
"""
import io
import math
import os
import re
import struct
import time

# ---------------------------------------------------------------------------
# Konstanty
# ---------------------------------------------------------------------------
PLATNO_SIRKA, PLATNO_VYSKA = 1600, 1000
SS = 2                                   # nadvzorkovani (anti-aliasing)
MAX_TROJUHELNIKU = 450000                # vic = rovnomerne rediti (rychlost)
CILOVA_ELEVACE_DEG = 17.5                # pohledy z otocky: nejblizsi elevace
ODCHYLKA_PRED_DEG = 35.0                 # pohledy z otocky: az_predni +- tolik
NEJVETSI_SNIMEK_B = 1500 * 1024          # strop velikosti jednoho snimku z otocky (JPG tier 2048 bywa ~0,3-1 MB)
MIN_TIER_PX = 1024
FONTY = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSans.ttf")
BARVA_PLOCHA_MIN, BARVA_PLOCHA_MAX = 196, 234     # svetle sede (stinovani podle normaly)
BARVA_HRANA = 120                        # hrany mezi dily (stredne seda)
BARVA_OBRYS = 28                         # obrys (tmava)
BARVA_KOTA = (22, 60, 110)               # kotovaci cary a texty


class VykresChyba(ValueError):
    """GLB nejde precist/vykreslit - volajici pouzije jinou nahradu (nebo hlasi, ze nahrada nevznikla)."""


# ---------------------------------------------------------------------------
# GLB -> svetove trojuhelniky
# ---------------------------------------------------------------------------

def _np():
    import numpy as np
    return np


def _read_glb(data):
    if len(data) < 20 or data[:4] != b"glTF":
        raise VykresChyba("neni GLB")
    import json
    off, js, bn = 12, None, None
    total = struct.unpack_from("<I", data, 8)[0]
    total = min(total, len(data))
    while off + 8 <= total:
        ln, ct = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + ln]
        if ct == 0x4E4F534A and js is None:
            js = json.loads(chunk.decode("utf-8"))
        elif ct == 0x004E4942 and bn is None:
            bn = chunk
        off += 8 + ((ln + 3) & ~3)
    if js is None or bn is None:
        raise VykresChyba("GLB bez JSON nebo BIN casti")
    return js, bn


_CT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2), 5125: ("I", 4), 5126: ("f", 4)}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _accessor(g, bn, idx):
    np = _np()
    a = g["accessors"][idx]
    if a.get("sparse"):
        raise VykresChyba("sparse accessor")
    fmt, size = _CT[a["componentType"]]
    n = _NC[a["type"]]
    bv = g["bufferViews"][a["bufferView"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or size * n
    cnt = a["count"]
    dt = np.dtype({"b": "i1", "B": "u1", "h": "<i2", "H": "<u2", "I": "<u4", "f": "<f4"}[fmt])
    if stride == size * n:
        arr = np.frombuffer(bn, dtype=dt, count=cnt * n, offset=off).reshape(cnt, n)
    else:
        raw = np.frombuffer(bn, dtype=np.uint8, count=stride * (cnt - 1) + size * n, offset=off)
        arr = np.lib.stride_tricks.as_strided(raw, shape=(cnt, size * n), strides=(stride, 1)).copy().view(dt).reshape(cnt, n)
    if a.get("normalized") and fmt != "f":
        arr = arr.astype("f4") / float(np.iinfo(dt).max)
    return arr


def _mat_uzlu(node):
    np = _np()
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    t = node.get("translation", (0, 0, 0))
    q = node.get("rotation", (0, 0, 0, 1))
    s = node.get("scale", (1, 1, 1))
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M = np.eye(4)
    M[:3, :3] = R * np.array(s, dtype=np.float64)[None, :]
    M[:3, 3] = t
    return M


# Pomucky, ktere k zakaznikovi nepatri (stejny seznam a stejna normalizace jmen jako strazce api/v3d_glb.py): logo, podlaha,
# fixarea, LegsBox, kotovaci pomucky, karoserie. Zakaznicky v3d model je nema vubec; DOSAVADNI staticky model (Blender
# geometrie bez v3d) je jeste obsahuje, a nahradni vykres je nesmi ukazat ani zapocitat do rozmeru.
_POMUCKY_RE = re.compile(
    r"logo|podlaha|fixarea(?:_?red)?|legsbox|legshoverbox|karoserie|"
    r"(?:top|bottom|side|front|back|left|right)?(?:drilling)?dimensions?", re.IGNORECASE)


def _pomucka(name):
    if not isinstance(name, str):
        return False
    s = re.sub(r"\((?:clone|instance)\)", "", name, flags=re.IGNORECASE).strip()
    s = re.sub(r"(?:[._\- ]*\d+)+$", "", s)
    return bool(_POMUCKY_RE.fullmatch(s))


def trojuhelniky_ze_glb(glb_bytes):
    """-> (T [N,3,3] float64 svetove souradnice (mm), id_uzlu [N] int, spec | None).
    Jen vychozi scena, jen mode TRIANGLES, bez pomucek (logo, podlaha, ... viz _POMUCKY_RE). VykresChyba pri necitelnem GLB."""
    np = _np()
    g, bn = _read_glb(glb_bytes)
    scenes = g.get("scenes") or []
    sc = scenes[g.get("scene", 0)] if scenes else None
    if not sc:
        raise VykresChyba("GLB bez sceny")
    spec = None
    ex = sc.get("extras") if isinstance(sc, dict) else None
    if isinstance(ex, dict) and isinstance(ex.get("v3d"), dict):
        spec = ex["v3d"]
    nodes = g.get("nodes") or []
    tris, ids = [], []
    stack = [(i, np.eye(4)) for i in sc.get("nodes", [])]
    videno = 0
    while stack:
        i, par = stack.pop()
        videno += 1
        if videno > 100000:
            raise VykresChyba("prilis mnoho uzlu / cyklus")
        n = nodes[i]
        if _pomucka(n.get("name")):
            continue                                  # vc. celeho podstromu
        M = par @ _mat_uzlu(n)
        for c in n.get("children", []):
            stack.append((c, M))
        if "mesh" not in n:
            continue
        mesh = g["meshes"][n["mesh"]]
        if _pomucka(mesh.get("name")):
            continue
        for prim in mesh.get("primitives", []):
            if prim.get("mode", 4) != 4 or "POSITION" not in prim.get("attributes", {}):
                continue
            if "material" in prim and _pomucka((g.get("materials") or [{}] * (prim["material"] + 1))[prim["material"]].get("name")):
                continue
            P = _accessor(g, bn, prim["attributes"]["POSITION"]).astype(np.float64)
            if P.shape[1] != 3 or len(P) == 0:
                continue
            if "indices" in prim:
                ix = _accessor(g, bn, prim["indices"]).reshape(-1).astype(np.int64)
            else:
                ix = np.arange(len(P), dtype=np.int64)
            ix = ix[: (len(ix) // 3) * 3].reshape(-1, 3)
            if len(ix) == 0:
                continue
            W = P @ M[:3, :3].T + M[:3, 3]
            tris.append(W[ix])
            ids.append(np.full(len(ix), i, dtype=np.int64))
    if not tris:
        raise VykresChyba("GLB nema zadne trojuhelniky")
    return np.concatenate(tris), np.concatenate(ids), spec


# ---------------------------------------------------------------------------
# Smer pohledu
# ---------------------------------------------------------------------------

def smer_z_azimutu(az_deg):
    a = math.radians(float(az_deg))
    return (math.sin(a), 0.0, math.cos(a))


def _predni_smer(T, spec, front_az_deg):
    """-> ((fx, 0, fz), zdroj)"""
    if isinstance(spec, dict) and isinstance(spec.get("front"), (list, tuple)) and len(spec["front"]) == 3:
        fx, fz = float(spec["front"][0]), float(spec["front"][2])
        h = math.hypot(fx, fz)
        if h > 1e-6:
            return (fx / h, 0.0, fz / h), "spec"
    if front_az_deg is not None:
        return smer_z_azimutu(front_az_deg), "azimut"
    ext = T.reshape(-1, 3).max(axis=0) - T.reshape(-1, 3).min(axis=0)
    return ((1.0, 0.0, 0.0), "odhad") if ext[0] <= ext[2] else ((0.0, 0.0, 1.0), "odhad")


def _osy(f):
    np = _np()
    f = np.array(f, dtype=np.float64)
    up = np.array((0.0, 1.0, 0.0))
    r = np.cross(-f, up)
    return f, up, r / (np.linalg.norm(r) or 1.0)


# ---------------------------------------------------------------------------
# Rasterizace (painter + PIL): stinovani + id uzlu (hrany dilu)
# ---------------------------------------------------------------------------

def _font(px):
    from PIL import ImageFont
    for p in FONTY:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, px)
            except OSError:
                continue
    return ImageFont.load_default()


def _ridit(T, ids, osa_u, osa_v, osa_h, svetlo, ramecek, mm_na_px, ss=SS):
    """Orthogonalni vykresleni do ramecku (x0, y0, x1, y1) v px KONCOVEHO platna, dolni levy roh modelu v (x0, y1).
    -> (stin L [ss*w, ss*h], id RGB-int pole numpy [ss*h, ss*w] (0 = pozadi)), plus sourad. okraje modelu v px.
    osa_u = vpravo, osa_v = nahoru, osa_h = smer ke kamere (vetsi = blize); svetlo = jednotkovy vektor."""
    np = _np()
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = ramecek
    W, H = (x1 - x0) * ss, (y1 - y0) * ss
    U = T @ osa_u
    V = T @ osa_v
    D = T @ osa_h
    umin, vmin = U.min(), V.min()
    sc = ss / mm_na_px
    X = (U - umin) * sc
    Y = H - (V - vmin) * sc
    # normaly (oboustranne stinovani)
    e1, e2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    nrm = np.cross(e1, e2)
    ln = np.linalg.norm(nrm, axis=1)
    ln[ln == 0] = 1.0
    nrm = nrm / ln[:, None]
    lam = np.abs(nrm @ svetlo)
    sede = (BARVA_PLOCHA_MIN + (BARVA_PLOCHA_MAX - BARVA_PLOCHA_MIN) * lam).astype(np.int64)
    poradi = np.argsort(D.mean(axis=1), kind="stable")          # vzdalene prvni (deterministicke)
    img_stin = Image.new("L", (W, H), 255)
    img_id = Image.new("RGB", (W, H), (0, 0, 0))
    d1, d2 = ImageDraw.Draw(img_stin), ImageDraw.Draw(img_id)
    Xl, Yl = X.tolist(), Y.tolist()
    idl, sl = ids.tolist(), sede.tolist()
    for t in poradi.tolist():
        pts = [(Xl[t][0], Yl[t][0]), (Xl[t][1], Yl[t][1]), (Xl[t][2], Yl[t][2])]
        d1.polygon(pts, fill=sl[t])
        k = idl[t] + 1
        d2.polygon(pts, fill=((k >> 16) & 255, (k >> 8) & 255, k & 255))
    a = np.asarray(img_id, dtype=np.int64)
    idpole = (a[:, :, 0] << 16) | (a[:, :, 1] << 8) | a[:, :, 2]
    # okraje modelu v px KONCOVEHO platna
    ox0, oy1 = x0, y1
    okraj = (x0, y1 - float(V.max() - vmin) / mm_na_px, x0 + float(U.max() - umin) / mm_na_px, y1)
    return img_stin, idpole, okraj


def _slozit(img_stin, idpole):
    """stin + hrany dilu + obrys -> L obrazek (jeste v nadvzorkovani)"""
    np = _np()
    from PIL import Image
    s = np.asarray(img_stin, dtype=np.uint8).copy()
    mask = idpole > 0
    hr = np.zeros(mask.shape, dtype=bool)
    ob = np.zeros(mask.shape, dtype=bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = idpole[dy:, dx:]
        b = idpole[: idpole.shape[0] - dy, : idpole.shape[1] - dx]
        zmena = a != b
        hr[dy:, dx:] |= zmena
        hr[: idpole.shape[0] - dy, : idpole.shape[1] - dx] |= zmena
        ma, mb = a > 0, b > 0
        pr = ma != mb
        ob[dy:, dx:] |= pr
        ob[: idpole.shape[0] - dy, : idpole.shape[1] - dx] |= pr
    hr &= mask
    s[hr] = np.minimum(s[hr], BARVA_HRANA).astype(np.uint8)
    s[ob] = BARVA_OBRYS
    return Image.fromarray(s, "L")


# ---------------------------------------------------------------------------
# Kotovani
# ---------------------------------------------------------------------------

def _text_cislo(mm):
    return "%d mm" % int(round(mm))


def _sipka(draw, x, y, dx, dy, barva, d=16, sirka=6):
    """sipka s hrotem v (x, y) ve smeru (dx, dy)"""
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    bx, by = x - ux * d, y - uy * d
    draw.polygon([(x, y), (bx - uy * sirka, by + ux * sirka), (bx + uy * sirka, by - ux * sirka)], fill=BARVA_KOTA)


def _kota_vodorovna(draw, font, x_a, x_b, y_cara, y_telo, text, texty):
    """vodorovna kota mezi x_a < x_b; cara v y_cara; vytahovaci cary od y_telo k y_cara"""
    for x in (x_a, x_b):
        draw.line([(x, y_telo), (x, y_cara + 10)], fill=BARVA_KOTA, width=2)
    draw.line([(x_a, y_cara), (x_b, y_cara)], fill=BARVA_KOTA, width=3)
    _sipka(draw, x_a, y_cara, 1, 0, BARVA_KOTA)
    _sipka(draw, x_b, y_cara, -1, 0, BARVA_KOTA)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    cx = (x_a + x_b) / 2.0
    draw.rectangle([cx - tw / 2 - 8, y_cara - th / 2 - 8, cx + tw / 2 + 8, y_cara + th / 2 + 8], fill=(255, 255, 255))
    draw.text((cx - tw / 2 - tb[0], y_cara - th / 2 - tb[1]), text, font=font, fill=BARVA_KOTA)
    texty.append(text)


def _kota_svisla(draw, font, y_a, y_b, x_cara, x_telo, text, texty):
    """svisla kota mezi y_a < y_b (px shora dolu); text otoceny o 90 st."""
    from PIL import Image, ImageDraw
    for y in (y_a, y_b):
        draw.line([(x_telo, y), (x_cara + 10, y)], fill=BARVA_KOTA, width=2)
    draw.line([(x_cara, y_a), (x_cara, y_b)], fill=BARVA_KOTA, width=3)
    _sipka(draw, x_cara, y_a, 0, 1, BARVA_KOTA)
    _sipka(draw, x_cara, y_b, 0, -1, BARVA_KOTA)
    tb = draw.textbbox((0, 0), text, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pl = Image.new("L", (tw + 16, th + 16), 0)
    ImageDraw.Draw(pl).text((8 - tb[0], 8 - tb[1]), text, font=font, fill=255)
    pl = pl.rotate(90, expand=True)
    cy = (y_a + y_b) / 2.0
    px, py = int(x_cara - pl.size[0] / 2), int(cy - pl.size[1] / 2)
    draw._image.paste((255, 255, 255), (px, py, px + pl.size[0], py + pl.size[1]))
    draw._image.paste(BARVA_KOTA, (px, py), pl)
    texty.append(text)


# ---------------------------------------------------------------------------
# Verejne funkce
# ---------------------------------------------------------------------------

def vykres_nares(glb_bytes, front_az_deg=None):
    """Kotovany 2D vykres (nares + bokorys) z cisteho GLB. -> (png_bytes, info). VykresChyba pri necitelnem GLB."""
    np = _np()
    from PIL import Image, ImageDraw
    t0 = time.time()
    T, ids, spec = trojuhelniky_ze_glb(glb_bytes)
    pocet = len(T)
    if pocet > MAX_TROJUHELNIKU:
        krok = int(math.ceil(pocet / float(MAX_TROJUHELNIKU)))
        T, ids = T[::krok], ids[::krok]
    mn, mx = T.reshape(-1, 3).min(axis=0), T.reshape(-1, 3).max(axis=0)
    (fx, _fy, fz), zdroj = _predni_smer(T, spec, front_az_deg)
    f, up, r = _osy((fx, 0.0, fz))
    P = T.reshape(-1, 3)
    # rozmery: v ose rovnobezne s osami modelu = AABB (stejne cislo jako rozmer_mm); jinak skutecny rozsah ve smeru pohledu
    sirka = float((P @ r).max() - (P @ r).min())
    vyska = float(mx[1] - mn[1])
    hloubka = float((P @ f).max() - (P @ f).min())
    if abs(fx) > 0.9999 or abs(fz) > 0.9999:
        osy_ext = mx - mn
        sirka, hloubka = (float(osy_ext[2]), float(osy_ext[0])) if abs(fx) > abs(fz) else (float(osy_ext[0]), float(osy_ext[2]))
    if min(sirka, vyska, hloubka) <= 0:
        raise VykresChyba("model ma nulovy rozmer")

    Wc, Hc = PLATNO_SIRKA, PLATNO_VYSKA
    levy, pravy_okraj = 150, 70            # mista pro svislou kotu vlevo / okraj vpravo
    dolni = 150                            # misto pro vodorovnou kotu dole
    horni = 120                            # titulek
    sirka_panelu1 = int(Wc * 0.66)
    mezera = 120                           # misto mezi nares a bokorys (svisla kota bokorysu)
    plocha1_w = sirka_panelu1 - levy - 30
    plocha2_w = Wc - sirka_panelu1 - mezera - pravy_okraj
    plocha_h = Hc - horni - dolni
    mm_na_px = max(sirka / plocha1_w, hloubka / plocha2_w, vyska / plocha_h)       # spolecne meritko
    pw1, ph = sirka / mm_na_px, vyska / mm_na_px
    pw2 = hloubka / mm_na_px
    y_pod = horni + plocha_h               # spodek (podlaha) obou pohledu
    x1_0 = levy + (plocha1_w - pw1) / 2.0
    x2_0 = sirka_panelu1 + mezera + (plocha2_w - pw2) / 2.0
    svetlo = np.array(f) * 0.75 + np.array(up) * 0.55 + r * 0.35
    svetlo = svetlo / np.linalg.norm(svetlo)

    platno = Image.new("RGB", (Wc, Hc), (255, 255, 255))
    # NARYS: pohled zepredu (kamera na +f)
    ramec1 = (int(round(x1_0)), int(round(y_pod - ph)), int(round(x1_0 + pw1)) + 1, int(round(y_pod)) + 1)
    s1, id1, ok1 = _ridit(T, ids, r, up, f, svetlo, ramec1, mm_na_px)
    # BOKORYS: pohled zprava (kamera na +r; vpravo na obrazovce je -f, tj. predni strana vlevo)
    r2 = -f
    svetlo2 = np.array(r) * 0.75 + np.array(up) * 0.55 + r2 * 0.35
    svetlo2 = svetlo2 / np.linalg.norm(svetlo2)
    ramec2 = (int(round(x2_0)), int(round(y_pod - ph)), int(round(x2_0 + pw2)) + 1, int(round(y_pod)) + 1)
    s2, id2, ok2 = _ridit(T, ids, r2, up, r, svetlo2, ramec2, mm_na_px)
    for img, idp, ram in ((s1, id1, ramec1), (s2, id2, ramec2)):
        sl = _slozit(img, idp).resize((img.size[0] // SS, img.size[1] // SS), Image.BOX)
        platno.paste(sl.convert("RGB"), (ram[0], ram[1]))
    d = ImageDraw.Draw(platno)
    font, font_n = _font(30), _font(26)
    texty = []
    # titulky
    d.text((levy, 40), "Nárys", font=_font(34), fill=(40, 40, 40))
    d.text((sirka_panelu1 + mezera, 40), "Bokorys", font=_font(34), fill=(40, 40, 40))
    texty += ["Nárys", "Bokorys"]
    # koty: nares - sirka (dole), vyska (vlevo); bokorys - hloubka (dole), vyska (vlevo)
    n1l, n1t, n1r, n1b = ok1
    n2l, n2t, n2r, n2b = ok2
    _kota_vodorovna(d, font, n1l, n1r, y_pod + 70, y_pod, _text_cislo(sirka), texty)
    _kota_svisla(d, font, n1t, n1b, n1l - 70, n1l, _text_cislo(vyska), texty)
    _kota_vodorovna(d, font, n2l, n2r, y_pod + 70, y_pod, _text_cislo(hloubka), texty)
    _kota_svisla(d, font, n2t, n2b, n2l - 70, n2l, _text_cislo(vyska), texty)
    pozn = "Rozměry sestavy v mm"
    d.text((levy, Hc - 52), pozn, font=font_n, fill=(90, 90, 90))
    texty.append(pozn)
    buf = io.BytesIO()
    platno.save(buf, "PNG", optimize=False, compress_level=6)
    info = {"sirka_mm": int(round(sirka)), "vyska_mm": int(round(vyska)), "hloubka_mm": int(round(hloubka)), "pocet_kot": 4,
            "texty": texty, "front": [round(fx, 6), round(fz, 6)], "front_zdroj": zdroj, "trojuhelniku": int(pocet),
            "mm_na_px": round(mm_na_px, 4), "platno": [Wc, Hc], "sekundy": round(time.time() - t0, 2)}
    return buf.getvalue(), info


def predni_azimut_deg(glb_bytes, front_az_deg=None):
    """azimut predni strany modelu ve stupnich (0-360, jako vandr_predni_azimut_deg): z spec.front GLB, jinak z parametru, jinak odhad"""
    T, _ids, spec = trojuhelniky_ze_glb(glb_bytes)
    (fx, _fy, fz), _zdroj = _predni_smer(T, spec, front_az_deg)
    return math.degrees(math.atan2(fx, fz)) % 360.0


def pohled_z_modelu(glb_bytes, az_deg, el_deg, sirka=1280, vyska=960):
    """Posledni zaloha 3D pohledu: ortogonalni stinovany pohled na model z azimutu/elevace (jako kontrola.html vdCameraDir)."""
    np = _np()
    from PIL import Image
    T, ids, _spec = trojuhelniky_ze_glb(glb_bytes)
    if len(T) > MAX_TROJUHELNIKU:
        krok = int(math.ceil(len(T) / float(MAX_TROJUHELNIKU)))
        T, ids = T[::krok], ids[::krok]
    el, az = math.radians(float(el_deg)), math.radians(float(az_deg))
    cd = np.array((math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az)))       # smer ke kamere
    up0 = np.array((0.0, 1.0, 0.0))
    r = np.cross(-cd, up0)
    r = r / (np.linalg.norm(r) or 1.0)
    u = np.cross(r, -cd)
    P = T.reshape(-1, 3)
    pu, pv = P @ r, P @ u
    sw, sh = float(pu.max() - pu.min()), float(pv.max() - pv.min())
    okraj = 60
    mm_na_px = max(sw / (sirka - 2 * okraj), sh / (vyska - 2 * okraj))
    px_w, px_h = sw / mm_na_px, sh / mm_na_px
    ramec = (int(round((sirka - px_w) / 2)), int(round((vyska - px_h) / 2)), int(round((sirka + px_w) / 2)) + 1,
             int(round((vyska + px_h) / 2)) + 1)
    svetlo = cd * 0.7 + u * 0.55 + r * 0.45
    svetlo = svetlo / np.linalg.norm(svetlo)
    s, idp, _ok = _ridit(T, ids, r, u, cd, svetlo, ramec, mm_na_px)
    sl = _slozit(s, idp).resize((s.size[0] // SS, s.size[1] // SS), Image.BOX)
    platno = Image.new("RGB", (sirka, vyska), (255, 255, 255))
    platno.paste(sl.convert("RGB"), (ramec[0], ramec[1]))
    buf = io.BytesIO()
    platno.save(buf, "PNG", optimize=False, compress_level=6)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Snimky otocky: vyber dvou 3D pohledu (cista funkce)
# ---------------------------------------------------------------------------

def _kruh(a, b):
    d = abs((float(a) - float(b)) % 360.0)
    return min(d, 360.0 - d)


def vyber_snimky_otocky(radky, front_az_deg, existuje=None):
    """radky = [{"elevation_deg", "azimuth_deg", "tier_px", "filename", "bytes"}] (product_turntable_frames, is_active=1).
    front_az_deg = shop_products.vandr_predni_azimut_deg. existuje(filename) -> bool (kontrola souboru; None = nekontroluje).
    -> {"a": radek (zepredu doprava: az_predni + 35), "b": radek (zepredu doleva: az_predni - 35)} nebo None.
    Pravidla: elevace nejblizsi 17,5 st. (pri shode vyssi); na kazdou pozici (elevace, azimut) nejvetsi tier >= 1024 px, jehoz soubor
    neni vetsi nez NEJVETSI_SNIMEK_B (jinak mensi tier >= 1024; az nakonec nejvetsi mensi); azimuty nejblizsi cilovym
    (kruhova vzdalenost), a != b; soubory musi existovat (jinak dalsi kandidat)."""
    if front_az_deg is None or not radky:
        return None
    pozice = {}
    for r in radky:
        try:
            klic = (int(r["elevation_deg"]), int(r["azimuth_deg"]))
            tier = int(r["tier_px"])
        except (KeyError, TypeError, ValueError):
            continue
        pozice.setdefault(klic, []).append(r)

    def poradi_tieru(rs):
        ok = [x for x in rs if int(x["tier_px"]) >= MIN_TIER_PX and int(x.get("bytes") or 0) <= NEJVETSI_SNIMEK_B]
        ok.sort(key=lambda x: -int(x["tier_px"]))
        velke = sorted([x for x in rs if int(x["tier_px"]) >= MIN_TIER_PX and x not in ok], key=lambda x: int(x["tier_px"]))
        mensi = sorted([x for x in rs if int(x["tier_px"]) < MIN_TIER_PX], key=lambda x: -int(x["tier_px"]))
        return ok + velke + mensi

    def snimek(klic):
        for x in poradi_tieru(pozice[klic]):
            if existuje is None or existuje(x["filename"]):
                return x
        return None

    elevace = sorted({k[0] for k in pozice}, key=lambda e: (abs(e - CILOVA_ELEVACE_DEG), -e))
    cile = {"a": (float(front_az_deg) + ODCHYLKA_PRED_DEG) % 360.0, "b": (float(front_az_deg) - ODCHYLKA_PRED_DEG) % 360.0}
    for el in elevace:
        azy = sorted({k[1] for k in pozice if k[0] == el})
        pouzite = set()
        vyber = {}
        for slot in ("a", "b"):
            for az in sorted(azy, key=lambda x: (_kruh(x, cile[slot]), x)):
                if az in pouzite:
                    continue
                x = snimek((el, az))
                if x is not None:
                    vyber[slot] = x
                    pouzite.add(az)
                    break
        if len(vyber) == 2:
            return vyber
    return None
