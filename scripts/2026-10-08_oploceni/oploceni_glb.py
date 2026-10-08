"""GLB SKLADAC generatoru OCHRANNY KRYT A OPLOCENI (bot8, 2026-10-08; faze 1, viz oploceni_konfigurator.py a README.md).

Z vysledku `sestav_oploceni()` vyrobi GLB pro viewer3d.js stejnym zpusobem jako stul_glb.poskladej_glb: neprusvitne dily (profily, spojky, panty, zaslepky, patky, zamky) jsou slite po MATERIALECH
do jednoho meshe (katalogove GLB dilu: `stul_glb.nacti_mesh`), kazde POLE VYPLNE je samostatny uzel s vlastnim meshem a prusvitnym materialem (alphaMode BLEND, dvoustranny) - viewer (three.js)
radi prusvitne objekty po objektech, takze se tabule radi spravne (jeden slity mesh by se radil jako celek). Vyplne maji vyrezy v rozich (3 kvadry), jsou tedy slozene z vice kvadru v jednom uzlu.

`spec` (scenes[0].extras.v3d) jako u stolu: jednotky mm, nahoru +Y, celo = smer +Z (celo je v rovine z = D), obalka (box), look "nat", kóty - zadne (viewer udela 3 obalkove), bez pohybu.
Model je vycentrovany (x, z do stredu, podlaha y = 0). `otevrit_dvere` (stupne, jen pro OBRAZKY / nahled, do hash konfigurace nevstupuje) otoci kridlo kolem osy zavesu ven.
"""
import json
import os
import struct
import sys
import zlib
from collections import OrderedDict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oploceni_konfigurator as O  # noqa: E402

GLB_MAGIC, GLB_VERSION = 0x46546C67, 2
MATERIALY = OrderedDict([
    ("alu", {"baseColorFactor": [0.5841, 0.6105, 0.6376, 1.0], "metallicFactor": 0.6, "roughnessFactor": 0.35}),
    ("ocel", {"baseColorFactor": [0.3231, 0.3515, 0.3813, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}),
    ("cerna", {"baseColorFactor": [0.0742, 0.0742, 0.0742, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}),
])
# prusvitne vyplne: {pbrMetallicRoughness, alphaMode, doubleSided}; baseColorFactor je LINEARNI (glTF), alfa = zakaleni
PRUSVITNE = OrderedDict([
    ("pc_cira", {"pbr": {"baseColorFactor": [0.62, 0.74, 0.80, 0.24], "metallicFactor": 0.0, "roughnessFactor": 0.08}, "blend": True}),
    ("pc_koura", {"pbr": {"baseColorFactor": [0.03, 0.03, 0.035, 0.64], "metallicFactor": 0.0, "roughnessFactor": 0.1}, "blend": True}),
    ("plexi", {"pbr": {"baseColorFactor": [0.70, 0.80, 0.85, 0.17], "metallicFactor": 0.0, "roughnessFactor": 0.05}, "blend": True}),
    ("sit", {"pbr": {"baseColorFactor": [0.55, 0.57, 0.60, 1.0], "metallicFactor": 0.6, "roughnessFactor": 0.45}, "blend": True, "tex": "sit"}),
    ("plna", {"pbr": {"baseColorFactor": [0.62, 0.64, 0.66, 1.0], "metallicFactor": 0.35, "roughnessFactor": 0.4}, "blend": False}),
])
MATERIAL_DILU = {O.PROFIL_PART: "alu", O.SPOJKA: "ocel", O.ZASLEPKA: "cerna", O.PANT_PRAVY: "cerna", O.PANT_LEVY: "cerna", O.PATKA: "ocel", O.ZAPADKA: "ocel", O.ZAMEK: "ocel"}
POREDI = ["alu", "ocel", "cerna"]


def _G():
    import stul_glb
    return stul_glb


SIT_ROZTEC = 25.0                  # mm: oko svarovane site (jedna bunka textury)


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


def _transformuj(dil, G):
    pos, nrm, tri = G.nacti_mesh(dil["part_id"])
    Rm = O.kvat_na_matici(dil["quaternion"])
    s = np.array(dil["scale"], float)
    p = (pos.astype(np.float64) * s) @ Rm.T + np.array(dil["position"], float)
    n = (nrm.astype(np.float64) / s) @ Rm.T
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return p, n / ln, tri


def sestav_glb(r, otevrit_dvere=0.0):
    """GLB (bytes) z vysledku sestav_oploceni; `otevrit_dvere` = uhel otevreni krídla (stupne, jen nahled)."""
    G = _G()
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

    for dil in r["dily"]:
        p, n, tri = _transformuj(dil, G)
        if _je_kridlo(dil) and dil.get("strana") in osy:
            rt = rot_dveri(dil["strana"])
            if rt is not None:
                R, P0 = rt
                p = (p - P0) @ R.T + P0
                n = n @ R.T
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
        uv = np.stack([P @ e1, P @ e2], axis=1) / SIT_ROZTEC if PRUSVITNE[info["material"]].get("tex") else None           # souradnice textury z polohy PRED otocenim kridla
        if v["role"].startswith("výplň křídla") and v["strana"] in osy:
            rt = rot_dveri(v["strana"])
            if rt is not None:
                R, P0 = rt
                P = (P - P0) @ R.T + P0
                N = N @ R.T
        panely.append((v["typ"], P, N, T, uv))
    vse = [np.vstack(g["P"]) for g in skupiny.values() if g["P"]] + [x[1] for x in panely]
    vsechny = np.vstack(vse)
    lo, hi = vsechny.min(axis=0), vsechny.max(axis=0)
    posun = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -(lo[2] + hi[2]) / 2.0])
    blob = bytearray()
    views, accessors, meshes, nodes, materials = [], [], [], [], []
    textury = {}

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
            m = {"pbrMetallicRoughness": dict(pr["pbr"]), "doubleSided": True}
            if pr.get("tex"):
                if not textury:
                    textury["image"] = pridej(_png_sit())
                m["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
            if pr["blend"]:
                m["alphaMode"] = "BLEND"
            materials.append(m)
            mat_prus[typ] = len(materials) - 1
        mesh(P, N, T, mat_prus[typ], uv)
    box_lo, box_hi = lo + posun, hi + posun
    spec = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0, 0, 1], "box": {"min": [round(float(x), 3) for x in box_lo], "max": [round(float(x), 3) for x in box_hi]}, "look": "nat", "dims": [],
            "motions": []}
    js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes))), "extras": {"v3d": spec}}], "nodes": nodes, "meshes": meshes, "materials": materials,
          "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    if textury:
        js["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        js["images"] = [{"bufferView": textury["image"], "mimeType": "image/png"}]
        js["textures"] = [{"sampler": 0, "source": 0}]
    jb = json.dumps(js, separators=(",", ":")).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    while len(blob) % 4:
        blob.append(0)
    celkem = 12 + 8 + len(jb) + 8 + len(blob)
    return struct.pack("<III", GLB_MAGIC, GLB_VERSION, celkem) + struct.pack("<II", len(jb), 0x4E4F534A) + jb + struct.pack("<II", len(blob), 0x004E4942) + bytes(blob)


_CACHE = OrderedDict()


def model_pro_parametry(parametry, razitka=False):
    """(hash, GLB bytes) pro parametry konfigurace (jako stul_glb / dopravnik_glb); LRU cache podle hashe normalizovanych parametru. `razitka` zatim bez vlivu (faze 2: loga v nabidce)."""
    r = O.sestav_oploceni(**parametry)
    h = r["hash"]
    if h in _CACHE:
        _CACHE.move_to_end(h)
        return h, _CACHE[h]
    glb = sestav_glb(r)
    _CACHE[h] = glb
    while len(_CACHE) > 32:
        _CACHE.popitem(last=False)
    return h, glb
