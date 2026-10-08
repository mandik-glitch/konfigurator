"""GLB SKLADAC generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08; viz oploceni_konfigurator.py a docs/KONTRAKT_OPLOCENI.md).

Z vysledku `sestav_oploceni()` vyrobi GLB pro viewer3d.js stejnym zpusobem jako stul_glb.poskladej_glb: neprusvitne dily (profily, spojky, panty, zaslepky, patky, zamky) jsou slite po MATERIALECH
do jednoho meshe (katalogove GLB dilu: `stul_glb.nacti_mesh`), kazde POLE VYPLNE je samostatny uzel s vlastnim meshem a prusvitnym materialem (alphaMode BLEND, dvoustranny) - viewer (three.js)
radi prusvitne objekty po objektech, takze se tabule radi spravne (jeden slity mesh by se radil jako celek). Vyplne maji vyrezy v rozich (3 kvadry), jsou tedy slozene z vice kvadru v jednom uzlu.

DVA REZIMY (parametr `razitka` u model_pro_parametry, stejny smysl jako u stolu):
  * razitka=False (VEREJNY / STAFF model, routa /api/shop/configurator/glb/<token>, karta, nahled): dva nejtezsi katalogove dily - stavitelna patka (3 418 vrcholu) a bezpecnostni zamek (36 076
    vrcholu) - jsou ZJEDNODUSENE (shlukovani vrcholu v mrizce `ZJEDNODUSIT`, mm; vzhled zustava, soubor je o 5-10 MB mensi u nejvetsich konfiguraci), svarovana sit ma TEXTURU (PNG, UV);
  * razitka=True (model do ONLINE NABIDKY, nabidka_z_konfigurace -> v3d_glb.sanitize + v3d_mark): plne dily a BEZ textury (v3d kontrakt zakaznickeho modelu obrazky nepovoluje; sit je prusvitna sedá).

`spec` (scenes[0].extras.v3d) jako u stolu: jednotky mm, nahoru +Y, celo = smer +Z (celo je v rovine z = D), obalka (box), look "nat", kóty `dims` (celkova sirka, hloubka - jen kdyz ma smysl -
a vyska; uroven 1), bez pohybu. Model je vycentrovany (x, z do stredu, podlaha y = 0). `otevrit_dvere` (stupne, jen pro OBRAZKY / nahled, do hash konfigurace nevstupuje) otoci kridlo kolem osy
zavesu ven.
"""
import json
import struct
import zlib
from collections import OrderedDict

import numpy as np

import oploceni_konfigurator as O

GLB_MAGIC, GLB_VERSION = 0x46546C67, 2
MATERIALY = OrderedDict([
    ("alu", {"baseColorFactor": [0.5841, 0.6105, 0.6376, 1.0], "metallicFactor": 0.6, "roughnessFactor": 0.35}),
    ("ocel", {"baseColorFactor": [0.3231, 0.3515, 0.3813, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}),
    ("cerna", {"baseColorFactor": [0.0742, 0.0742, 0.0742, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}),
])
# prusvitne vyplne: {pbrMetallicRoughness, alphaMode, doubleSided}; baseColorFactor je LINEARNI (glTF), alfa = zakaleni; `tex` = svarovana sit s texturou (bez textury `pbr_bez`)
PRUSVITNE = OrderedDict([
    ("pc_cira", {"pbr": {"baseColorFactor": [0.62, 0.74, 0.80, 0.24], "metallicFactor": 0.0, "roughnessFactor": 0.08}, "blend": True}),
    ("pc_koura", {"pbr": {"baseColorFactor": [0.03, 0.03, 0.035, 0.64], "metallicFactor": 0.0, "roughnessFactor": 0.1}, "blend": True}),
    ("plexi", {"pbr": {"baseColorFactor": [0.70, 0.80, 0.85, 0.17], "metallicFactor": 0.0, "roughnessFactor": 0.05}, "blend": True}),
    ("sit", {"pbr": {"baseColorFactor": [0.55, 0.57, 0.60, 1.0], "metallicFactor": 0.6, "roughnessFactor": 0.45}, "blend": True, "tex": "sit",
             "pbr_bez": {"baseColorFactor": [0.40, 0.42, 0.45, 0.50], "metallicFactor": 0.6, "roughnessFactor": 0.45}}),
    ("plna", {"pbr": {"baseColorFactor": [0.62, 0.64, 0.66, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}, "blend": False}),
])
MATERIAL_DILU = {O.PROFIL_PART: "alu", O.SPOJKA: "ocel", O.ZASLEPKA: "cerna", O.PANT_PRAVY: "cerna", O.PANT_LEVY: "cerna", O.PATKA: "ocel", O.ZAPADKA: "ocel", O.ZAMEK: "ocel"}
POREDI = ["alu", "ocel", "cerna"]
ZJEDNODUSIT = {O.PATKA: 0.8, O.ZAMEK: 1.6}                # verejny model: dil -> hrana mrizky shlukovani vrcholu (mm)
SIT_ROZTEC = 25.0                  # mm: oko svarovane site (jedna bunka textury)
KOTY_ODSTUP = 120.0                # mm: o kolik lezi cary celkovych kot od konstrukce


def _G():
    import stul_glb
    return stul_glb


def _png_sit():
    """PNG 32 x 32 (RGBA): jedna bunka svarovane site (draty 3 px nahore a vlevo = 2,3 mm pri roztecy 25 mm, oko pruhledne); deterministicke bajty."""
    n, drat = 32, 3
    raw = bytearray()
    for y in range(n):
        raw.append(0)
        for x in range(n):
            raw.extend((205, 208, 212, 255) if (x < drat or y < drat) else (205, 208, 212, 0))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


def _je_kridlo(d):
    return bool(d.get("kridlo")) or "křídl" in d.get("role", "")


def _rot_kolem_osy(bod, uhel_rad):
    c, s = np.cos(uhel_rad), np.sin(uhel_rad)
    R = np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])           # kolem +Y (UP)
    return R, np.asarray(bod, float)


def _kvadr_svet(lo, hi):
    G = _G()
    return G._mesh_kvadr(lo, hi)


def zjednodus_mesh(pos, tri, tol):
    """Zjednoduseny mesh shlukovanim vrcholu v mrizce o hrane `tol` mm (vrcholy v jedne bunce se slouci do prumeru, zdegenerovane a duplicitni trojuhelniky pryc, normaly se dopocitaji z ploch
    vazene plochou). -> (pozice float32 Nx3, normaly float32 Nx3, trojuhelniky int64 Mx3). Vysledek je deterministicky."""
    pos = np.asarray(pos, np.float64)
    tri = np.asarray(tri, np.int64)
    q = np.floor(pos / float(tol)).astype(np.int64)
    uniq, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(uniq)
    cnt = np.bincount(inv, minlength=n).astype(np.float64)
    npos = np.zeros((n, 3))
    np.add.at(npos, inv, pos)
    npos /= cnt[:, None]
    t = inv[tri]
    t = t[(t[:, 0] != t[:, 1]) & (t[:, 1] != t[:, 2]) & (t[:, 0] != t[:, 2])]
    _, prvni = np.unique(np.sort(t, axis=1), axis=0, return_index=True)             # stejny trojuhelnik 2x (obe strany) nechat jednou
    t = t[np.sort(prvni)]
    pouzite = np.unique(t)
    mapa = np.full(n, -1, np.int64)
    mapa[pouzite] = np.arange(len(pouzite))
    t = mapa[t]
    npos = npos[pouzite]
    fn = np.cross(npos[t[:, 1]] - npos[t[:, 0]], npos[t[:, 2]] - npos[t[:, 0]])
    nn = np.zeros_like(npos)
    for k in range(3):
        np.add.at(nn, t[:, k], fn)
    ln = np.linalg.norm(nn, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return npos.astype(np.float32), (nn / ln).astype(np.float32), t.astype(np.int64)


_JEDNODUCHE = {}


def mesh_dilu(part_id, jednoduche):
    """(pozice, normaly, trojuhelniky) katalogoveho dilu; `jednoduche` = zjednoduseny mesh dilu z ZJEDNODUSIT (cache)."""
    G = _G()
    pos, nrm, tri = G.nacti_mesh(part_id)
    if jednoduche and part_id in ZJEDNODUSIT:
        klic = (part_id, ZJEDNODUSIT[part_id])
        if klic not in _JEDNODUCHE:
            _JEDNODUCHE[klic] = zjednodus_mesh(pos, tri, ZJEDNODUSIT[part_id])
        return _JEDNODUCHE[klic]
    return pos, nrm, tri


def _transformuj(dil, jednoduche):
    pos, nrm, tri = mesh_dilu(dil["part_id"], jednoduche)
    Rm = O.kvat_na_matici(dil["quaternion"])
    s = np.array(dil["scale"], float)
    p = (pos.astype(np.float64) * s) @ Rm.T + np.array(dil["position"], float)
    n = (nrm.astype(np.float64) / s) @ Rm.T
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return p, n / ln, tri


def _cislo_kota(v):
    n = int(np.floor(float(v) + 0.5))
    return f"{n:,}".replace(",", " ")


def _koty(r, plo, phi, posun):
    """Celkove koty (uroven 1) v souradnicich GLB: sirka (jen kdyz ma vliv), hloubka (jen kdyz ma vliv a konstrukce ma hloubku) a celkova vyska od podlahy (vcetne patek)."""
    p = r["parametry"]
    rel = O.rozmery_relevantni(p)
    out = []
    z1 = float(phi[2] + posun[2])

    def kota(a, b, o, v):
        return {"a": [round(float(x), 3) for x in a], "b": [round(float(x), 3) for x in b], "o": [round(float(x), 3) for x in o], "t": _cislo_kota(v), "l": 1}
    x0, x1 = float(plo[0] + posun[0]), float(phi[0] + posun[0])
    y_dol = float(plo[1] + posun[1])
    if rel["sirka"]:
        out.append(kota((x0, y_dol, z1), (x1, y_dol, z1), (0.0, 0.0, KOTY_ODSTUP), r["rozmery"]["sirka_mm"]))
    z0 = float(plo[2] + posun[2])
    if rel["hloubka"] and z1 - z0 > 100.0:
        out.append(kota((x1, y_dol, z0), (x1, y_dol, z1), (KOTY_ODSTUP, 0.0, 0.0), r["rozmery"]["hloubka_mm"]))
    out.append(kota((x0, 0.0, z1), (x0, float(r["rozmery"]["vyska_mm"]), z1), (-KOTY_ODSTUP, 0.0, 0.0), r["rozmery"]["vyska_mm"]))
    return out


def sestav_glb(r, otevrit_dvere=0.0, jednoduche=False, textury=True):
    """GLB (bytes) z vysledku sestav_oploceni; `otevrit_dvere` = uhel otevreni kridla (stupne, jen nahled); `jednoduche` = zjednodusene patky a zamky (verejny model); `textury` = textura site."""
    skupiny = {m: {"P": [], "N": [], "T": [], "base": 0} for m in POREDI}
    osy = {d["strana"]: d for d in r.get("dvere", [])}
    uhel = np.radians(float(otevrit_dvere))

    def rot_dveri(strana):
        d = osy.get(strana)
        if not d or not uhel:
            return None
        znam = 1.0 if d["zavesy"] == "vpravo" else -1.0
        R, P0 = _rot_kolem_osy(d["osa_bod"], znam * uhel)
        return R, P0

    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    plo = np.full(3, np.inf)                                                         # obalka PROFILU (kóty)
    phi = np.full(3, -np.inf)
    for dil in r["dily"]:
        p, n, tri = _transformuj(dil, jednoduche)
        rotace = rot_dveri(dil["strana"]) if (_je_kridlo(dil) and dil.get("strana") in osy) else None
        if rotace is not None:
            R, P0 = rotace
            p = (p - P0) @ R.T + P0
            n = n @ R.T
            blo, bhi = O.aabb(dil)                                                   # obalka natoceneho dilu: z rohu puvodni obalky (konzervativne)
            rohy = np.array([[x, y, z] for x in (blo[0], bhi[0]) for y in (blo[1], bhi[1]) for z in (blo[2], bhi[2])])
            rohy = (rohy - P0) @ R.T + P0
            blo, bhi = rohy.min(axis=0), rohy.max(axis=0)
        else:
            blo, bhi = O.aabb(dil)
        lo, hi = np.minimum(lo, blo), np.maximum(hi, bhi)
        if dil["druh"] == "profil" and rotace is None:
            plo, phi = np.minimum(plo, blo), np.maximum(phi, bhi)
        g = skupiny[MATERIAL_DILU.get(dil["part_id"], "ocel")]
        g["P"].append(p)
        g["N"].append(n)
        g["T"].append(tri + g["base"])
        g["base"] += len(p)
    panely = []                                               # (typ, P, N, T, UV nebo None) po polich vyplne
    for v in r["vyplne"]:
        info = O.VYPLNE[v["typ"]]
        t = info["tloustka"]
        e1, e2, nn = np.array(v["e1"]), np.array(v["e2"]), np.array(v["n"])
        Ps, Ns, Ts, base = [], [], [], 0
        for kus in v["kusy"]:
            pol = np.abs(e1) * kus["e1"] / 2.0 + np.abs(e2) * kus["e2"] / 2.0 + np.abs(nn) * t / 2.0
            c = np.array(kus["stred"], float)
            P, N, T = _kvadr_svet(c - pol, c + pol)
            Ps.append(P.astype(np.float64))
            Ns.append(N.astype(np.float64))
            Ts.append(T + base)
            base += len(P)
        P, N, T = np.vstack(Ps), np.vstack(Ns), np.vstack(Ts)
        uv = np.stack([P @ e1, P @ e2], axis=1) / SIT_ROZTEC if (textury and PRUSVITNE[info["material"]].get("tex")) else None          # souradnice textury z polohy PRED otocenim kridla
        if v["role"].startswith("výplň křídla") and v["strana"] in osy:
            rt = rot_dveri(v["strana"])
            if rt is not None:
                R, P0 = rt
                P = (P - P0) @ R.T + P0
                N = N @ R.T
        lo, hi = np.minimum(lo, P.min(axis=0)), np.maximum(hi, P.max(axis=0))
        panely.append((v["typ"], P, N, T, uv))
    posun = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -(lo[2] + hi[2]) / 2.0])
    blob = bytearray()
    views, accessors, meshes, nodes, materials = [], [], [], [], []
    textury_js = {}

    def pridej(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        v_ = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target:
            v_["target"] = target
        views.append(v_)
        blob.extend(data)
        return len(views) - 1

    def mesh(P, N, T, material_index, uv=None):
        P = (P + posun).astype("<f4")
        N = N.astype("<f4")
        T = T.astype("<u4").ravel()
        vp, vn, vi = pridej(P.tobytes(), 34962), pridej(N.tobytes(), 34962), pridej(T.tobytes(), 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(P), "type": "VEC3", "min": [float(x) for x in P.min(axis=0)], "max": [float(x) for x in P.max(axis=0)]})
        a_pos = len(accessors) - 1
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(N), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(T), "type": "SCALAR"})
        atr = {"POSITION": a_pos, "NORMAL": a_pos + 1}
        if uv is not None:
            uv = uv.astype("<f4")
            accessors.append({"bufferView": pridej(uv.tobytes(), 34962), "componentType": 5126, "count": len(uv), "type": "VEC2"})
            atr["TEXCOORD_0"] = len(accessors) - 1
        meshes.append({"primitives": [{"attributes": atr, "indices": a_pos + 2, "material": material_index, "mode": 4}]})
        nodes.append({"name": f"n{len(nodes)}", "mesh": len(meshes) - 1})

    for m in POREDI:
        g = skupiny[m]
        if not g["P"]:
            continue
        materials.append({"pbrMetallicRoughness": dict(MATERIALY[m])})
        mesh(np.vstack(g["P"]), np.vstack(g["N"]), np.vstack(g["T"]), len(materials) - 1)
    mat_prus = {}
    for typ, P, N, T, uv in panely:
        if typ not in mat_prus:
            pr = PRUSVITNE[O.VYPLNE[typ]["material"]]
            tex = bool(textury and pr.get("tex"))
            m = {"pbrMetallicRoughness": dict(pr["pbr"] if (tex or not pr.get("pbr_bez")) else pr["pbr_bez"]), "doubleSided": True}
            if tex:
                if not textury_js:
                    textury_js["image"] = pridej(_png_sit())
                m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
            if pr["blend"]:
                m["alphaMode"] = "BLEND"
            materials.append(m)
            mat_prus[typ] = len(materials) - 1
        mesh(P, N, T, mat_prus[typ], uv)
    box_lo, box_hi = lo + posun, hi + posun
    spec = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0, 0, 1], "box": {"min": [round(float(x), 3) for x in box_lo], "max": [round(float(x), 3) for x in box_hi]}, "look": "nat",
            "dims": _koty(r, plo, phi, posun), "motions": []}
    js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes))), "extras": {"v3d": spec}}], "nodes": nodes, "meshes": meshes, "materials": materials,
          "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    if textury_js:
        js["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        js["images"] = [{"bufferView": textury_js["image"], "mimeType": "image/png"}]
        js["textures"] = [{"sampler": 0, "source": 0}]
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    while len(blob) % 4:
        blob.append(0)
    celkem = 12 + 8 + len(jb) + 8 + len(blob)
    return struct.pack("<III", GLB_MAGIC, GLB_VERSION, celkem) + struct.pack("<II", len(jb), 0x4E4F534A) + jb + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)


_CACHE = OrderedDict()
CACHE_MAX = 16


def model_pro_parametry(parametry, razitka=False, max_dilu=None):
    """(hash, GLB bytes) pro parametry konfigurace jadra (jako stul_glb.model_pro_parametry); LRU cache podle (hash normalizovanych parametru, razitka). razitka=False = verejny / staff model
    (zjednodusene patky a zamky, textura site), razitka=True = model do ONLINE NABIDKY (plne dily, bez textur). `max_dilu` = strop poctu dilu modelu (vic = O.OploceniChyba "prilis_velky").
    Vyhodi O.OploceniChyba pri neplatnych parametrech."""
    r = O.sestav_oploceni(**parametry)
    if max_dilu is not None and len(r["dily"]) > max_dilu:
        raise O.OploceniChyba(f"Konfigurace má {len(r['dily'])} dílů, model se staví nejvýš z {max_dilu}.", "prilis_velky", {"dilu": len(r["dily"]), "max": max_dilu})
    h = r["hash"]
    klic = (h, bool(razitka))
    if klic in _CACHE:
        _CACHE.move_to_end(klic)
        return h, _CACHE[klic]
    glb = sestav_glb(r, jednoduche=not razitka, textury=not razitka)
    _CACHE[klic] = glb
    while len(_CACHE) > CACHE_MAX:
        _CACHE.popitem(last=False)
    return h, glb
