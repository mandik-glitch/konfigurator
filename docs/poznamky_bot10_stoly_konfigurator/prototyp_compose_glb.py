#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""
PROTOTYP (bot10, 2026-10-02, fáze průzkum + kandidát; NIC se nezapisuje do /opt ani do DB, jen SELECT):
server-side složení GLB z uložené sestavy čistě v Pythonu (numpy) + ověření.

  python prototyp_compose_glb.py [--shape 577 | --assembly N] [--out DIR] [--repeat N]

Co to dělá:
  1. SELECT custom_shapes.data (nebo product_assemblies.data) -> parts[] (part_id, position, quaternion, scale ...)
  2. part_id -> katalogový GLB (cfg_dily.glb_file / shop_products.glb_file, stejně jako fetch_katalog_parts + resolve_parts)
  3. čte katalogové GLB (v3d_glb.read_glb + numpy akcesory), aplikuje TRS jako scéna (T*R*S na kořen dílu),
     normály přes inv(M3), obrací vinutí při det<0, slepí do primitiv podle materiálu (barva/kovovost/drsnost jako
     resolve_material z turntable_job), uzly = slot g (celé číslo), bez jmen, bez extras kromě {g}
  4. v3d_glb.sanitize() výsledek projde a znovu se zkontroluje (AABB, počty, žádná jména)
  5. referenční výpočet v Node/three r128 (node_ref.js) na STEJNÝCH datech: Box3 každého dílu i celku a počet spojů
     přesně kódem vyříznutým ze scene.html -> porovnání
  6. Pythonový port počtu spojů (profil-profil, plná krycí plocha menšího čela, JOINT_RULE_VERSION 3) -> porovnání

Co to NENÍ: hotový modul. Materiály jsou zjednodušené (viz MATERIAL_*), sloty jsou demonstrační, žádné parametrické varianty.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
V3D_API = "/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d/api"
sys.path.insert(0, V3D_API)
sys.path.insert(0, HERE)

import numpy as np  # noqa: E402
import v3d_glb  # noqa: E402
import db  # noqa: E402

KAT = "/opt/konfigurator/webapp/katalog/"
THREE_CHECK = "/tmp/claude-0/-opt-konfigurator/3a4f3da8-6534-422d-a853-fe8654c9f7d6/scratchpad/v3d/tests/three_check.js"

# --------------------------------------------------------------------------------------------------
# materiály (KOPIE z scripts/2026-09-09_turntable_job.py:70-86,140-160 - v ostrém modulu import, ne kopie)
# --------------------------------------------------------------------------------------------------
PART_MATERIAL_COLOR = {"alu": "#c9cdd1", "black": "#242424", "zinc": "#b7bcc0", "guma": "#1c1c1e",
                       "plast_svetly": "#666c73", "mdf": "#5c626a"}
PART_MATERIAL_METALNESS = {"alu": 0.6, "zinc": 0.45, "black": 0.1, "guma": 0.05, "plast_svetly": 0.0, "mdf": 0.1}
PART_MATERIAL_ROUGHNESS = {"alu": 0.35, "zinc": 0.55, "black": 0.15, "guma": 0.75, "plast_svetly": 0.38, "mdf": 0.4}
DEFAULT_PART_COLOR = "#9aa0a6"
HEX_TO_METALNESS = {v.lower(): PART_MATERIAL_METALNESS[k] for k, v in PART_MATERIAL_COLOR.items()}
HEX_TO_ROUGHNESS = {v.lower(): PART_MATERIAL_ROUGHNESS[k] for k, v in PART_MATERIAL_COLOR.items()}


def resolve_material(layer, color_hex, defaults=None):
    for k, v in (defaults or {}).items():           # app_settings.scene_material_defaults (jen čtení)
        if k in PART_MATERIAL_COLOR and isinstance(v, dict):
            pass
    color = (color_hex or PART_MATERIAL_COLOR.get(layer) or DEFAULT_PART_COLOR).lower()
    metal = HEX_TO_METALNESS.get(color)
    if metal is None:
        metal = PART_MATERIAL_METALNESS.get(layer, 0.35)
    rough = HEX_TO_ROUGHNESS.get(color)
    if rough is None:
        rough = PART_MATERIAL_ROUGHNESS.get(layer, 0.4)
    return color, float(metal), float(rough)


def hex_to_linear(h):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


# --------------------------------------------------------------------------------------------------
# čtení katalogových GLB (numpy)
# --------------------------------------------------------------------------------------------------
_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def _accessor(g, b, i):
    a = g["accessors"][i]
    bv = g["bufferViews"][a["bufferView"]]
    dt = np.dtype(_CT[a["componentType"]])
    nc = _NC[a["type"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride") or dt.itemsize * nc
    if stride == dt.itemsize * nc:
        return np.frombuffer(b, dtype=dt, count=a["count"] * nc, offset=off).reshape(a["count"], nc)
    raw = np.frombuffer(b, dtype=np.uint8, count=stride * a["count"], offset=off).reshape(a["count"], stride)
    return np.ascontiguousarray(raw[:, :dt.itemsize * nc]).view(dt).reshape(a["count"], nc)


class CatGlb:
    """Jedna katalogová geometrie: pos[N,3] f64, nrm[N,3] f64 | None, tri[M,3] i64 (všechna primitiva slepená)."""
    __slots__ = ("pos", "nrm", "tri", "bmin", "bmax", "n_prims", "has_mat")

    def __init__(self, file):
        g, b = v3d_glb.read_glb(open(KAT + file, "rb").read())
        for n in g.get("nodes", []):
            if any(k in n for k in ("matrix", "translation", "rotation", "scale")):
                raise ValueError("%s: uzel s transformací (katalog dnes žádný nemá, přidat podporu)" % file)
        P, N, T, off = [], [], [], 0
        has_n = None
        self.n_prims = 0
        self.has_mat = bool(g.get("materials"))
        for m in g.get("meshes", []):
            for p in m["primitives"]:
                if p.get("mode", 4) != 4:
                    raise ValueError("%s: jen trojúhelníky" % file)
                pos = _accessor(g, b, p["attributes"]["POSITION"]).astype(np.float64)
                tri = (_accessor(g, b, p["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in p
                       else np.arange(len(pos), dtype=np.int64).reshape(-1, 3))
                nrm = (_accessor(g, b, p["attributes"]["NORMAL"]).astype(np.float64)
                       if "NORMAL" in p["attributes"] else None)
                if has_n is None:
                    has_n = nrm is not None
                elif has_n != (nrm is not None):
                    nrm = None          # smíšené (nevyskytuje se ověřeně) -> počítat ploché normály pro celý díl
                    has_n = False
                P.append(pos); N.append(nrm); T.append(tri + off); off += len(pos); self.n_prims += 1
        if not P:
            raise ValueError("%s: bez geometrie" % file)
        self.pos = np.concatenate(P)
        self.nrm = np.concatenate(N) if has_n and all(x is not None for x in N) else None
        self.tri = np.concatenate(T)
        self.bmin = self.pos.min(0)
        self.bmax = self.pos.max(0)


_GEO = {}


def catglb(file):
    if file not in _GEO:
        _GEO[file] = CatGlb(file)
    return _GEO[file]


# --------------------------------------------------------------------------------------------------
# TRS jako three.js Object3D (matrix = T * R * S)
# --------------------------------------------------------------------------------------------------
def quat_to_mat3(q):
    x, y, z, w = [float(v) for v in q]
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0   # three: quaternion se nenormalizuje při compose, ale ukládáme jednotkové
    # POZOR: three Matrix4.compose používá q tak, jak je (neprovádí normalizaci). Uložené kvaterniony jsou zaokrouhlené
    # na 6 míst (0.707107) - norma 1.0000003, rozdíl pod 1e-6 relativně, ignorujeme, ale NEnormalizujeme, abychom měli shodu.
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    return np.array([[1 - (yy + zz), xy - wz, xz + wy],
                     [xy + wz, 1 - (xx + zz), yz - wx],
                     [xz - wy, yz + wx, 1 - (xx + yy)]])


def trs4(position, quaternion, scale):
    R = quat_to_mat3(quaternion)
    M = np.eye(4)
    M[:3, :3] = R * np.asarray(scale, dtype=float)[None, :]      # R @ diag(s)
    M[:3, 3] = position
    return M


def aabb_of_box_corners(M, bmin, bmax):
    """Box3.setFromObject() v r128 = AABB z 8 rohů lokální obálky geometrie transformovaných maticí (ne z vrcholů)."""
    c = np.array([[x, y, z, 1.0] for x in (bmin[0], bmax[0]) for y in (bmin[1], bmax[1]) for z in (bmin[2], bmax[2])])
    w = c @ M.T
    return w[:, :3].min(0), w[:, :3].max(0)


# --------------------------------------------------------------------------------------------------
# katalog: part_id -> {glb, layer, color_hex, is_profile, length_mm, cross, is_board}
# --------------------------------------------------------------------------------------------------
def resolve_catalog(cur, part_ids):
    out = {}
    cfg_ids = sorted({p for p in part_ids if not p.startswith("product_") and not p.startswith("car_body_")})
    prod_ids = sorted({int(p.split("_", 1)[1]) for p in part_ids if p.startswith("product_")})
    if cfg_ids:
        cur.execute("SELECT id,name,layer,glb_file,color_hex,dim_x_mm,dim_y_mm,dim_z_mm FROM cfg_dily WHERE id IN (%s)"
                    % ",".join(["%s"] * len(cfg_ids)), cfg_ids)
        for r in cur.fetchall():
            dims = [None if r[k] is None else float(r[k]) for k in ("dim_x_mm", "dim_y_mm", "dim_z_mm")]
            prof = all(d is not None for d in dims)       # isProfilePart: length_mm && cross_section_mm[0] != null
            ds = sorted(dims) if prof else None
            out[r["id"]] = dict(glb=r["glb_file"], layer=r["layer"], color_hex=r["color_hex"], name=r["name"],
                                is_profile=prof, length_mm=ds[2] if prof else None,
                                cross=[ds[0], ds[1]] if prof else [None, None], is_board=False)
    if prod_ids:
        cur.execute("SELECT id,name,sku,glb_file,color_hex,is_board_material,nativni_material FROM shop_products "
                    "WHERE id IN (%s)" % ",".join(["%s"] * len(prod_ids)), prod_ids)
        for r in cur.fetchall():
            out["product_%d" % r["id"]] = dict(glb=r["glb_file"], layer=None, color_hex=r["color_hex"], name=r["name"],
                                               is_profile=False, length_mm=None, cross=[None, None],
                                               is_board=bool(r["is_board_material"]),
                                               nativni=bool(r["nativni_material"]), sku=r["sku"])
    return out


# --------------------------------------------------------------------------------------------------
# složení GLB
# --------------------------------------------------------------------------------------------------
def flat_normals(P, T):
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1.0
    return n / ln


def compose(parts, cat, slot_of=None, normals=True, recenter=False):
    """parts: seznam dílů (jako v custom_shapes.data), cat: výstup resolve_catalog.
    Vrací (gltf_dict, bin_bytes, info). Jeden uzel + jedno primitivum na (slot, materiál).
    normals=False: bez NORMAL (viewer3d.js vynucuje flatShading, normály se nepoužijí; GLB je ~2x menší, katalogové indexování zůstane).
    recenter=True: posun modelu tak, aby střed půdorysu byl v 0 a spodek na y=0 (nenese souřadnice zdrojové sestavy)."""
    shift = np.zeros(3)
    if recenter:
        mn_all = np.full(3, np.inf); mx_all = np.full(3, -np.inf)
        for p in parts:
            g_ = catglb(cat[p["part_id"]]["glb"]); M_ = trs4(p["position"], p["quaternion"], p["scale"])
            lo, hi = aabb_of_box_corners(M_, g_.bmin, g_.bmax)
            mn_all = np.minimum(mn_all, lo); mx_all = np.maximum(mx_all, hi)
        shift = -np.array([(mn_all[0] + mx_all[0]) / 2, mn_all[1], (mn_all[2] + mx_all[2]) / 2])
    groups = {}            # (slot, color, metal, rough) -> list of (P, N, T)
    per_part = []
    for i, p in enumerate(parts):
        c = cat.get(p["part_id"])
        if c is None or not c["glb"]:
            raise ValueError("díl %s nemá GLB v katalogu" % p["part_id"])
        geo = catglb(c["glb"])
        M = trs4(p["position"], p["quaternion"], p["scale"])
        M3 = M[:3, :3]
        P = geo.pos @ M3.T + M[:3, 3] + shift
        tri = geo.tri
        if np.linalg.det(M3) < 0:
            tri = tri[:, [0, 2, 1]]
        if not normals:
            N = None
        elif geo.nrm is not None:
            N = geo.nrm @ np.linalg.inv(M3)             # (M3^-T n)^T = n^T M3^-1
            ln = np.linalg.norm(N, axis=1, keepdims=True); ln[ln == 0] = 1.0
            N = N / ln
            if np.linalg.det(M3) < 0:
                pass                                    # inv-transpose už zrcadlení řeší, vinutí jsme obrátili výše
        else:
            # three GLTFLoader u primitiva bez NORMAL nastaví material.flatShading -> ploché normály, rozpletené vrcholy
            fn = flat_normals(P, tri)
            P = P[tri.reshape(-1)]
            N = np.repeat(fn, 3, axis=0)
            tri = np.arange(len(P), dtype=np.int64).reshape(-1, 3)
        color, metal, rough = resolve_material(c["layer"], c["color_hex"])
        key = (slot_of(p, c, i) if slot_of else 0, color, round(metal, 4), round(rough, 4))
        groups.setdefault(key, []).append((P, N, tri))
        per_part.append((P.min(0), P.max(0)))

    bin_parts, bviews, accessors, meshes, nodes, materials = [], [], [], [], [], []
    mat_index = {}
    off = 0

    def add_view(arr, target):
        nonlocal off
        raw = np.ascontiguousarray(arr).tobytes()
        pad = (-len(raw)) % 4
        bviews.append({"buffer": 0, "byteOffset": off, "byteLength": len(raw), "target": target})
        bin_parts.append(raw + b"\x00" * pad)
        off += len(raw) + pad
        return len(bviews) - 1

    gmin = np.full(3, np.inf); gmax = np.full(3, -np.inf)
    tot_v = tot_t = 0
    for key in sorted(groups):
        slot, color, metal, rough = key
        Ps, Ns, Ts = [], [], []
        base = 0
        for P, N, T in groups[key]:
            Ps.append(P); Ns.append(N); Ts.append(T + base); base += len(P)
        P = np.concatenate(Ps).astype(np.float32)
        N = np.concatenate(Ns).astype(np.float32) if normals else None
        T = np.concatenate(Ts)
        idx_dt = np.uint16 if len(P) < 65535 else np.uint32
        T = T.reshape(-1).astype(idx_dt)
        mk = (color, metal, rough)
        if mk not in mat_index:
            rgb = hex_to_linear(color)
            materials.append({"pbrMetallicRoughness": {"baseColorFactor": [rgb[0], rgb[1], rgb[2], 1.0],
                                                       "metallicFactor": metal, "roughnessFactor": rough}})
            mat_index[mk] = len(materials) - 1
        # POZOR: baseColorFactor v glTF je LINEÁRNÍ; three GLTFLoader ho převádí na sRGB working space (r128: ColorManagement ne,
        # outputEncoding=sRGB v nabidka-online) - shoda s barvou ve scéně (hex přes materiál) je TŘEBA OVĚŘIT vizuálně (hypotéza).
        vp = add_view(P, 34962)
        vn = add_view(N, 34962) if normals else None
        vi = add_view(T, 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(P), "type": "VEC3",
                          "min": [float(x) for x in P.min(0)], "max": [float(x) for x in P.max(0)]})
        if normals:
            accessors.append({"bufferView": vn, "componentType": 5126, "count": len(N), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5123 if idx_dt == np.uint16 else 5125,
                          "count": len(T), "type": "SCALAR"})
        a = len(accessors) - (3 if normals else 2)
        attrs = {"POSITION": a, "NORMAL": a + 1} if normals else {"POSITION": a}
        meshes.append({"primitives": [{"attributes": attrs, "indices": a + (2 if normals else 1),
                                       "material": mat_index[mk]}]})
        nodes.append({"mesh": len(meshes) - 1, "extras": {"g": int(slot)}})
        gmin = np.minimum(gmin, P.min(0)); gmax = np.maximum(gmax, P.max(0))
        tot_v += len(P); tot_t += len(T) // 3
    binb = b"".join(bin_parts)
    gltf = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}],
            "nodes": nodes, "meshes": meshes, "materials": materials, "accessors": accessors,
            "bufferViews": bviews, "buffers": [{"byteLength": len(binb)}]}
    info = dict(aabb_min=gmin.tolist(), aabb_max=gmax.tolist(), per_part=per_part, verts=tot_v, tris=tot_t,
                nodes=len(nodes), materials=len(materials))
    return gltf, binb, info


# --------------------------------------------------------------------------------------------------
# počet spojů - Pythonový port (scene.html: autoRegisterTouchedProfileJoints + classifyJointPair)
# --------------------------------------------------------------------------------------------------
EPS_FACE, EPS_OVERLAP = 0.75, 0.5


class ProfEntry:
    __slots__ = ("i", "bmin", "bmax", "axis_w", "end0", "end1", "ends")

    def __init__(self, i, part, geo):
        M = trs4(part["position"], part["quaternion"], part["scale"])
        self.i = i
        self.bmin, self.bmax = aabb_of_box_corners(M, geo.bmin, geo.bmax)
        c = (geo.bmin + geo.bmax) / 2
        dims = geo.bmax - geo.bmin
        ax = 0
        if dims[1] > dims[ax]: ax = 1                    # shodně s computeConnectorsLocal (remíza -> nižší osa)
        if dims[2] > dims[ax]: ax = 2
        half = dims[ax] / 2
        av = np.zeros(3); av[ax] = 1.0
        e0 = M @ np.append(c + av * half, 1.0)            # connectors[0] = +osa, [1] = -osa
        e1 = M @ np.append(c - av * half, 1.0)
        self.end0, self.end1 = e0[:3], e1[:3]
        d = self.end1 - self.end0
        self.axis_w = d / (np.linalg.norm(d) or 1.0)


def touching(a, b):
    for ax in range(3):
        face_close = abs(a.bmax[ax] - b.bmin[ax]) < EPS_FACE or abs(a.bmin[ax] - b.bmax[ax]) < EPS_FACE
        if not face_close:
            continue
        ok = True
        for j in range(3):
            if j == ax:
                continue
            lo = max(a.bmin[j], b.bmin[j]); hi = min(a.bmax[j], b.bmax[j])
            min_size = min(a.bmax[j] - a.bmin[j], b.bmax[j] - b.bmin[j])
            if (hi - lo) < (min_size - EPS_OVERLAP):
                ok = False
                break
        if ok:
            return True
    return False


def axial_overlap(entry, prof):
    A, B = prof.end0, prof.end1
    ax = B - A
    L = np.linalg.norm(ax)
    if L < 1e-6:
        return math.inf
    ax = ax / L
    cs = np.array([[x, y, z] for x in (entry.bmin[0], entry.bmax[0]) for y in (entry.bmin[1], entry.bmax[1])
                   for z in (entry.bmin[2], entry.bmax[2])])
    t = (cs - A) @ ax
    return min(t.max(), L) - max(t.min(), 0.0)


def is_real_joint(a, b):
    """classifyJointPair: aspoň jedna strana 'end' (kolmé osy -> vždy; souosé bez překryvu -> end-end; souosé s překryvem
    = bok-k-boku NENÍ spoj; šikmé = není)."""
    d = abs(float(a.axis_w @ b.axis_w))
    if d < 0.1:
        return True
    if d > 0.9:
        return axial_overlap(a, b) <= 5
    return False


def count_joints(parts, cat, with_lic_peers=False):
    """Vrací (počet spojů, seznam párů indexů). Jen profil-profil dvojice (isProfilePart na obou stranách)."""
    ents = []
    for i, p in enumerate(parts):
        c = cat.get(p["part_id"])
        if c and c["is_profile"] and c["glb"]:
            role = p.get("role") or ""
            if role.startswith("logo-ochrana") or role.startswith("kontrolni-pomucka"):
                continue
            ents.append(ProfEntry(i, p, catglb(c["glb"])))
    pairs = set()
    for x in range(len(ents)):
        for y in range(x + 1, len(ents)):
            a, b = ents[x], ents[y]
            if touching(a, b) and is_real_joint(a, b):
                pairs.add((a.i, b.i))
    if with_lic_peers:
        idx = {e.i: e for e in ents}
        for i, p in enumerate(parts):
            for j in p.get("lic_peers") or []:
                lo, hi = min(i, j), max(i, j)
                if lo in idx and hi in idx and lo != hi and is_real_joint(idx[lo], idx[hi]):
                    pairs.add((lo, hi))
    return len(pairs), sorted(pairs)


# --------------------------------------------------------------------------------------------------
def make_spec(amin, amax, front=(0, 0, 1)):
    """Minimální spec v3d v1 pro statický model s hlavními kótami (šířka/hloubka/výška); look 'nat' (nativní díly)."""
    (x0, y0, z0), (x1, y1, z1) = [float(v) for v in amin], [float(v) for v in amax]
    def t(v): return "%d mm" % round(v)
    dims = [
        {"a": [x0, y0, z1], "b": [x1, y0, z1], "o": [0, 0, 150], "t": t(x1 - x0), "l": 1},
        {"a": [x1, y0, z0], "b": [x1, y0, z1], "o": [150, 0, 0], "t": t(z1 - z0), "l": 1},
        {"a": [x0, y0, z1], "b": [x0, y1, z1], "o": [-150, 0, 150], "t": t(y1 - y0), "l": 1},
    ]
    return {"v": 1, "u": "mm", "up": [0, 1, 0], "front": list(front),
            "box": {"min": [x0, y0, z0], "max": [x1, y1, z1]}, "look": "nat", "dims": dims, "motions": []}


def export_variant(parts, cat, slot_of, out_path):
    """Zákaznický export: bez NORMAL, přecentrováno, se spec -> sanitize. Vrací (bytes, timing dict)."""
    import gzip
    t0 = time.perf_counter()
    gltf, binb, info = compose(parts, cat, slot_of, normals=False, recenter=True)
    raw = v3d_glb.write_glb(gltf, binb)
    t1 = time.perf_counter()
    spec = make_spec(info["aabb_min"], info["aabb_max"])
    san = v3d_glb.sanitize(raw, spec)
    t2 = time.perf_counter()
    open(out_path, "wb").write(san)
    return san, dict(compose_ms=1000 * (t1 - t0), sanitize_ms=1000 * (t2 - t1), bytes=len(san),
                     gzip_bytes=len(gzip.compress(san, 6)), verts=info["verts"], tris=info["tris"],
                     aabb_min=info["aabb_min"], aabb_max=info["aabb_max"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shape", type=int, default=577)
    ap.add_argument("--assembly", type=int, default=None)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--repeat", type=int, default=5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    c, cur = db.ro()
    if a.assembly:
        cur.execute("SELECT id,name,data FROM product_assemblies WHERE id=%s", (a.assembly,))
        tag = "asm%d" % a.assembly
    else:
        cur.execute("SELECT id,name,data FROM custom_shapes WHERE id=%s", (a.shape,))
        tag = "shape%d" % a.shape
    row = cur.fetchone()
    data = json.loads(row["data"])
    parts = [p for p in data["parts"] if not p["part_id"].startswith("car_body_")
             and not (p.get("role") or "").startswith(("logo-ochrana", "kontrolni-pomucka"))]
    print("== %s '%s': %d dílů (po filtru razítek/karoserie)" % (tag, row["name"], len(parts)))
    cat = resolve_catalog(cur, {p["part_id"] for p in parts})
    miss = [p["part_id"] for p in parts if p["part_id"] not in cat or not cat[p["part_id"]]["glb"]]
    if miss:
        sys.exit("v katalogu chybí: %s" % sorted(set(miss)))

    # ---- demonstrační sloty: deska / profil / kolečka / spojky / ostatní komponenty ----
    def slot_of(p, c, i):
        if c["is_board"]: return 1
        if c["is_profile"]: return 2
        if c.get("sku", "").startswith("Pojedove.kolo"): return 3
        if "spojka" in (c.get("name") or "").lower(): return 4
        return 5

    # ---- složení + čas ----
    t = []
    for _ in range(a.repeat):
        _GEO.clear()                  # studený běh (čtení všech GLB ze souborů); teplý je viz níže
        t0 = time.perf_counter()
        gltf, binb, info = compose(parts, cat, slot_of)
        raw = v3d_glb.write_glb(gltf, binb)
        t.append(time.perf_counter() - t0)
    t_warm = []
    for _ in range(a.repeat):
        t0 = time.perf_counter()
        gltf, binb, info = compose(parts, cat, slot_of)
        raw = v3d_glb.write_glb(gltf, binb)
        t_warm.append(time.perf_counter() - t0)
    print("složení GLB (%d dílů): studené (čtení GLB z disku) %.0f ms (min %.0f), teplé (cache geometrií) %.0f ms (min %.0f); "
          "výstup %d B, %d vrcholů, %d trojúhelníků, %d uzlů, %d materiálů" % (
              len(parts), 1000 * float(np.median(t)), 1000 * min(t), 1000 * float(np.median(t_warm)), 1000 * min(t_warm),
              len(raw), info["verts"], info["tris"], info["nodes"], info["materials"]))
    open(os.path.join(a.out, tag + "_surove.glb"), "wb").write(raw)

    # ---- sanitizer ----
    t0 = time.perf_counter()
    rep = v3d_glb.sanitize_report(raw)
    san = rep[0]
    t_san = time.perf_counter() - t0
    open(os.path.join(a.out, tag + "_sanitized.glb"), "wb").write(san)
    g2, b2 = v3d_glb.read_glb(san)
    js = json.dumps(g2)
    names = [n.get("name") for n in g2["nodes"]] + [m.get("name") for m in g2.get("materials", [])]
    print("sanitize: OK za %.0f ms; %d B -> %d B; jména uzlů %s; jména materiálů %s; extras uzlů %s; klíče kořene %s" % (
        1000 * t_san, len(raw), len(san), names[:len(g2['nodes'])], names[len(g2['nodes']):],
        [n.get("extras") for n in g2["nodes"]], sorted(g2.keys())))
    v3d_glb.final_check(g2)
    print("final_check: OK; zakázaný regex v JSON:", bool(v3d_glb.FORBIDDEN_RE.search(js)))

    # ---- referenční výpočet v Node/three ----
    ref_in = {
        "parts": parts,
        "glb_map": {pid: cat[pid]["glb"] for pid in cat},
        "is_profile": {pid: cat[pid]["is_profile"] for pid in cat},
        "length_mm": {pid: cat[pid]["length_mm"] for pid in cat},
        "cross": {pid: cat[pid]["cross"] for pid in cat},
    }
    pin = os.path.join(a.out, tag + "_ref_in.json"); pout = os.path.join(a.out, tag + "_ref_out.json")
    json.dump(ref_in, open(pin, "w"))
    t0 = time.perf_counter()
    r = subprocess.run(["node", os.path.join(HERE, "node_ref.js"), pin, pout], capture_output=True, text=True,
                       cwd="/opt/konfigurator")
    print(r.stdout.strip() or r.stderr.strip()[:2000])
    if r.returncode != 0:
        sys.exit("node_ref selhal")
    ref = json.load(open(pout))

    # ---- porovnání AABB: celek ----
    gmin, gmax = np.array(info["aabb_min"]), np.array(info["aabb_max"])
    rmin, rmax = np.array(ref["boxes"]["union"]["min"]), np.array(ref["boxes"]["union"]["max"])
    d_all = float(max(np.abs(gmin - rmin).max(), np.abs(gmax - rmax).max()))
    print("AABB celku: python-GLB min %s max %s | three(scéna) min %s max %s | max odchylka %.5f mm" % (
        np.round(gmin, 2).tolist(), np.round(gmax, 2).tolist(), np.round(rmin, 2).tolist(), np.round(rmax, 2).tolist(), d_all))
    # ---- po dílech (Python = přesné vrcholy; three = obálka geometrie, shodné pro násobky 90 st) ----
    worst = 0.0
    worst_i = None
    for i, (pm, px) in enumerate(info["per_part"]):
        rb = ref["boxes"]["per_part"][i]
        d = float(max(np.abs(np.array(pm) - np.array(rb["min"])).max(), np.abs(np.array(px) - np.array(rb["max"])).max()))
        if d > worst:
            worst, worst_i = d, i
    print("AABB po dílech: %d dílů, nejhorší odchylka %.5f mm (díl %s)" % (len(parts), worst, worst_i))

    # ---- AABB sanitizovaného GLB načteného přes three GLTFLoader (nezávislá cesta) ----
    rr = subprocess.run(["node", THREE_CHECK, os.path.join(a.out, tag + "_sanitized.glb")], capture_output=True,
                        text=True, cwd="/opt/konfigurator")
    if rr.returncode == 0:
        tc = json.loads(rr.stdout)
        pr = np.array(tc["prims"])
        tmin, tmax = pr[:, :3].min(0), pr[:, 3:].max(0)
        d_three = float(max(np.abs(tmin - rmin).max(), np.abs(tmax - rmax).max()))
        print("three GLTFLoader(sanitized): uzly %s, userData %s, AABB min %s max %s, odchylka vs scéna %.5f mm" % (
            tc["names"], tc["userData"], np.round(tmin, 2).tolist(), np.round(tmax, 2).tolist(), d_three))
    else:
        print("three_check selhal:", rr.stdout[:500], rr.stderr[:500])

    # ---- spoje ----
    nj_geo, pairs_geo = count_joints(parts, cat, False)
    nj_lic, pairs_lic = count_joints(parts, cat, True)
    ns = ref["joints_scena_po_nacteni"]["total"]; ng = ref["joints_jen_geometrie"]["total"]
    stored = ref["stored_joint_count_sum"]
    pr_geo_node = ref["joints_jen_geometrie"]["pairs"]
    print("SPOJE: python jen geometrie %d | python +lic_peers %d | node(kód scene.html) jen geometrie %d | "
          "node scéna po načtení (lic_peers+geometrie) %d | uložený součet parts[].joint_count %s" % (
              nj_geo, nj_lic, ng, ns, stored if stored else "(chybí)"))
    print("  páry geometrické shodné s Node:", [tuple(x) for x in pr_geo_node] == [tuple(x) for x in pairs_geo],
          "(python %d párů, node %d párů)" % (len(pairs_geo), len(pr_geo_node)))
    if [tuple(x) for x in pr_geo_node] != [tuple(x) for x in pairs_geo]:
        print("  jen v python:", sorted(set(pairs_geo) - set(map(tuple, pr_geo_node))),
              "jen v node:", sorted(set(map(tuple, pr_geo_node)) - set(pairs_geo)))
    # ---- zákaznický export (bez NORMAL, přecentrováno, se spec) ----
    exp, ex = export_variant(parts, cat, slot_of, os.path.join(a.out, tag + "_export.glb"))
    g3, _ = v3d_glb.read_glb(exp)
    sp = g3["scenes"][0].get("extras", {}).get("v3d")
    print("EXPORT (bez NORMAL, přecentrováno, se spec): složení %.0f ms + sanitize %.0f ms, %d B (gzip %d B), %d vrcholů, %d trojúhelníků; "
          "AABB %s .. %s; spec dims %s" % (ex["compose_ms"], ex["sanitize_ms"], ex["bytes"], ex["gzip_bytes"], ex["verts"], ex["tris"],
                                          np.round(ex["aabb_min"], 1).tolist(), np.round(ex["aabb_max"], 1).tolist(),
                                          [d["t"] for d in (sp or {}).get("dims", [])]))
    v3d_glb.final_check(g3)
    json.dump(dict(tag=tag, name=row["name"], parts=len(parts), glb_bytes=len(raw), san_bytes=len(san),
                   t_cold_ms=1000 * float(np.median(t)), t_warm_ms=1000 * float(np.median(t_warm)),
                   aabb_diff_union=d_all, aabb_diff_parts=worst, joints=dict(py_geo=nj_geo, py_lic=nj_lic, node_geo=ng,
                   node_scene=ns, stored=stored)), open(os.path.join(a.out, tag + "_vysledek.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
