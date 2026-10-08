#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testy serverove pojistky api/v3d_glb.py (kontrakt v3d v1).

Spusteni:  /opt/konfigurator/api/venv/bin/python scripts/2026-10-02_v3d_testy/test_sanitize.py   (nebo run_all.sh)

Fixtury: fixtures/native_offer.glb = KOPIE nativniho modelu nabidky 103 (private-files/scene-offer-models/);
  katalogove GLB karet 4910 a 4918 se CTOU primo z webapp/katalog/vandr/ (kdyz chybi, testy se preskoci).
Synteticke GLB se skladaji tady v kodu.

Vystupy Blender kroku <OUT>/out/<karta>.glb + .json (v3d) vyrobi build_karty.py (run_all.sh);
bez nich se test TestVandrOut preskoci. <OUT> = $V3D_TEST_OUT nebo <tmp>/v3d_testy (mimo repo).

Svetove matice a AABB pocita test VLASTNIM kodem (radkove matice, rotace
z kvaternionu zvlast), ne funkcemi modulu - aby chyba v modulu nemohla
"potvrdit sama sebe". Kontrola v three r128 GLTFLoaderu bezi pres node
(tests/three_check.js), bez site.

TestAttacks = utoky nezavisle kontroly (tmp/kontrola/adv_sanitize.py):
kazdy ma predepsany vysledek - "cisti" (vystup projde vsemi kontrolami a
tajny text v nem neni) nebo "odmitne" (ValueError). Predepsany vysledek
(ne "kterykoli z obou") je zamerny: kdyby prestavba z whitelistu prestala
fungovat, utoky by misto vycisteni koncily chybou ve final_check a
mutacni kontrola (tests/_mutace.py) by to jinak nepoznala.
"""

import copy
import glob
import json
import math
import os
import re
import struct
import subprocess
import sys
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _cesty as CE  # noqa: E402
ROOT = CE.REPO
sys.path.insert(0, os.path.join(ROOT, "api"))

import v3d_glb  # noqa: E402
from v3d_glb import V3DError, FORBIDDEN_RE  # noqa: E402

FIX = CE.FIX
NATIVE = os.path.join(FIX, "native_offer.glb")
VANDR = os.path.join(CE.KATALOG, "vandr", "vd_export_ford_transit_l3h3_fwd_4155e003.glb")      # karta 4910 (jen cteni)
VANDR2 = os.path.join(CE.KATALOG, "vandr", "vd_export_vw_crafter_l3h3_fwd_1958c629.glb")     # karta 4918 (jen cteni)
THREE_JS = os.path.join(HERE, "three_check.js")
NODE = "/usr/bin/node" if os.path.exists("/usr/bin/node") else None
TOL = 0.01      # mm

NAME_RE = re.compile(r"(?:n\d+|p\d+|m\d+)?")


def read(path):
    if not os.path.exists(path):
        raise unittest.SkipTest("chybi vstup %s" % path)
    with open(path, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Nezavisla geometrie (radkove 4x4, list listu)
# ---------------------------------------------------------------------------

def m_ident():
    return [[1.0 if r == c else 0.0 for c in range(4)] for r in range(4)]


def m_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def m_node(n):
    if "matrix" in n:
        e = n["matrix"]               # column-major
        return [[float(e[c * 4 + r]) for c in range(4)] for r in range(4)]
    tx, ty, tz = n.get("translation", [0, 0, 0])
    qx, qy, qz, qw = n.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = n.get("scale", [1, 1, 1])
    r = [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]
    s = (sx, sy, sz)
    return [
        [r[0][0] * s[0], r[0][1] * s[1], r[0][2] * s[2], tx],
        [r[1][0] * s[0], r[1][1] * s[1], r[1][2] * s[2], ty],
        [r[2][0] * s[0], r[2][1] * s[1], r[2][2] * s[2], tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def xform(m, p):
    return [m[k][0] * p[0] + m[k][1] * p[1] + m[k][2] * p[2] + m[k][3] for k in range(3)]


def positions(g, b, acc_i):
    a = g["accessors"][acc_i]
    assert a["componentType"] == 5126 and a["type"] == "VEC3"
    v = g["bufferViews"][a["bufferView"]]
    stride = v.get("byteStride", 12)
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    return [struct.unpack_from("<3f", b, base + i * stride) for i in range(a["count"])]


def accessor_bytes(g, b, acc_i):
    a = g["accessors"][acc_i]
    v = g["bufferViews"][a["bufferView"]]
    csize = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[a["componentType"]]
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
    esize = csize * ncomp
    stride = v.get("byteStride", esize)
    base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    return b"".join(b[base + i * stride: base + i * stride + esize] for i in range(a["count"]))


def mesh_instances(glb_bytes):
    """[(mesh_idx, prim_idx, vertex_world_aabb, corner_world_aabb, attr_bytes)]."""
    g, raw = v3d_glb.read_glb(glb_bytes)
    b = raw or b""
    out = []
    scene = g["scenes"][g.get("scene", 0)]

    def walk(i, pm):
        n = g["nodes"][i]
        m = m_mul(pm, m_node(n))
        if "mesh" in n:
            for j, p in enumerate(g["meshes"][n["mesh"]]["primitives"]):
                pi = p["attributes"]["POSITION"]
                pts = [xform(m, q) for q in positions(g, b, pi)]
                va = [min(q[k] for q in pts) for k in range(3)] + [max(q[k] for q in pts) for k in range(3)]
                a = g["accessors"][pi]
                corners = [xform(m, (x, y, z)) for x in (a["min"][0], a["max"][0])
                           for y in (a["min"][1], a["max"][1]) for z in (a["min"][2], a["max"][2])]
                ca = [min(q[k] for q in corners) for k in range(3)] + [max(q[k] for q in corners) for k in range(3)]
                ab = tuple(accessor_bytes(g, b, v) for _k, v in sorted(p["attributes"].items()))
                if "indices" in p:
                    ab += (accessor_bytes(g, b, p["indices"]),)
                out.append((n["mesh"], j, va, ca, ab))
        for c in n.get("children", []):
            walk(c, m)

    for r in scene.get("nodes", []):
        walk(r, m_ident())
    return out


def match_boxes(test, want, got, tol=TOL, what="AABB"):
    """Parovani dvou multimnozin boxu (kazdy box = 6 cisel) s toleranci."""
    test.assertEqual(len(want), len(got), "%s: pocet %d vs %d" % (what, len(want), len(got)))
    free = list(got)
    for w in want:
        for k, f in enumerate(free):
            if max(abs(w[i] - f[i]) for i in range(6)) <= tol:
                del free[k]
                break
        else:
            test.fail("%s: box %s nema protejsek" % (what, [round(x, 3) for x in w]))


def compare_instances(test, before, after, mesh_map):
    """Svetove AABB (z vrcholu) + bajty atributu kazde instance meshe pred/po."""
    exp = {}
    for mi, j, va, _ca, ab in before:
        if mi in mesh_map:
            exp.setdefault((mesh_map[mi], j), []).append((va, ab))
    got = {}
    for mi, j, va, _ca, ab in after:
        got.setdefault((mi, j), []).append((va, ab))
    test.assertEqual(sorted(exp), sorted(got), "sada meshu/primitiv pred/po nesedi")
    for key in exp:
        e, o = exp[key], got[key]
        test.assertEqual(len(e), len(o), "pocet instanci %s" % (key,))
        for _va, ab in e:
            test.assertIn(ab, [x[1] for x in o], "data atributu meshe %s se zmenila" % (key,))
        match_boxes(test, [x[0] for x in e], [x[0] for x in o], what="mesh %s" % (key,))


def three_load(glb_bytes, tmpname):
    path = os.path.join(CE.OUT, "sanitize_test", tmpname)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(glb_bytes)
    r = subprocess.run([NODE, THREE_JS, path], capture_output=True, text=True, timeout=120)
    try:
        res = json.loads(r.stdout)
    except ValueError:
        raise AssertionError("three_check.js nevratil JSON: %s %s" % (r.stdout[:300], r.stderr[:300]))
    return res


def walk_json(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + (k,), k, v
            yield from walk_json(v, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk_json(v, path + (i,))


# ---------------------------------------------------------------------------
# Synteticky GLB
# ---------------------------------------------------------------------------

def quat_axis(ax, deg):
    s = math.sin(math.radians(deg) / 2)
    return [ax[0] * s, ax[1] * s, ax[2] * s, math.cos(math.radians(deg) / 2)]


class GB:
    def __init__(self):
        self.j = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": []}], "nodes": [],
                  "meshes": [], "accessors": [], "bufferViews": [], "buffers": []}
        self.bin = bytearray()

    def view(self, data, **kw):
        self.bin += b"\x00" * (-len(self.bin) % 4)
        self.j["bufferViews"].append(dict(buffer=0, byteOffset=len(self.bin), byteLength=len(data), **kw))
        self.bin += data
        return len(self.j["bufferViews"]) - 1

    def material(self, name=None, **kw):
        m = {"pbrMetallicRoughness": {"baseColorFactor": [0.7, 0.7, 0.7, 1], "metallicFactor": 1}}
        if name is not None:
            m["name"] = name
        m.update(kw)
        self.j.setdefault("materials", []).append(m)
        return len(self.j["materials"]) - 1

    def box(self, size=(10, 20, 30), center=(0, 0, 0), material=None, name=None, acc_name=None):
        hx, hy, hz = (s / 2 for s in size)
        cx, cy, cz = center
        pts = [(cx + sx * hx, cy + sy * hy, cz + sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        pos = b"".join(struct.pack("<3f", *p) for p in pts)
        idx = [0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3]
        ib = struct.pack("<%dH" % len(idx), *idx)
        pv = self.view(pos, target=34962)
        iv = self.view(ib, target=34963)
        f32 = [struct.unpack("<f", struct.pack("<f", v))[0] for p in pts for v in p]
        mn = [min(f32[k::3]) for k in range(3)]
        mx = [max(f32[k::3]) for k in range(3)]
        acc = self.j["accessors"]
        a_pos = dict(bufferView=pv, componentType=5126, count=8, type="VEC3", min=mn, max=mx)
        if acc_name:
            a_pos["name"] = acc_name
        acc.append(a_pos)
        acc.append(dict(bufferView=iv, componentType=5123, count=len(idx), type="SCALAR"))
        prim = {"attributes": {"POSITION": len(acc) - 2}, "indices": len(acc) - 1}
        if material is not None:
            prim["material"] = material
        mesh = {"primitives": [prim]}
        if name:
            mesh["name"] = name
        self.j["meshes"].append(mesh)
        return len(self.j["meshes"]) - 1

    def node(self, parent=None, **kw):
        self.j["nodes"].append(dict(kw))
        i = len(self.j["nodes"]) - 1
        if parent is None:
            self.j["scenes"][0]["nodes"].append(i)
        else:
            self.j["nodes"][parent].setdefault("children", []).append(i)
        return i

    def glb(self):
        self.j["buffers"] = [{"byteLength": len(self.bin)}]
        return v3d_glb.write_glb(self.j, bytes(self.bin))


def png_1x1(text_chunks=()):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    for t, d in text_chunks:
        out += chunk(t, d)
    return out + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def build_synthetic(extra=None):
    """Synteticky 'Vandr-like' GLB s pivoty, retezy, smetim v extras/jmenech."""
    gb = GB()
    alu = gb.material("ALU (Instance)", extras={"unity": "Suplik.ocel"},
                      extensions={"KHR_materials_clearcoat": {"clearcoatFactor": 0.1}})
    klt = gb.material("m03")
    chrome = gb.material("chrome (Instance)")
    root = gb.node(name="Nohy2CrafterH21700459(Clone)", translation=[100, 0, 0],
                   rotation=quat_axis((0, 1, 0), 90), scale=[1, 1, 1],
                   extras={"transformData": {"eulerOrder": "YXZ"}})
    sup = gb.node(root, name="Suplikocel1301057459(Clone)",
                  matrix=[2, 0, 0, 0, 0, 2, 0, 0, 0, 0, 2, 0, 5, 300, -10, 1])
    p01 = gb.node(sup, name="p01", translation=[0, 20, -115])
    gb.node(p01, name="Object_22", mesh=gb.box((440, 130, 400), (0, 0, -200), alu, name="Suplik.ocel.130"),
            extras={"g": 5})
    p02 = gb.node(p01, name="p02", translation=[0, 70, -100])
    gb.node(p02, name="box6417", mesh=gb.box((300, 133, 400), (0, 66, 0), klt))
    grp = gb.node(sup, name="sroub", rotation=quat_axis((0, 0, 1), 30))
    gb.node(grp, name="Object_23", mesh=gb.box((12, 53, 450), (220, 0, -225), chrome, acc_name="Object_23_pos"))
    bg = gb.node(None, name="bomgrp_7", extras={"basePos": {"x": 1, "y": 2, "z": 3}})
    w = gb.node(bg, name="world", extras={"name": "world"}, translation=[0, 10, 0])
    gb.node(w, name="geometry_0", mesh=gb.box((40, 1000, 40)), matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 500, 0, 1],
            extras={"origMeshColor": 123})
    gb.node(None, name="colliders")
    gb.node(None, name="p05", translation=[1, 2, 3], children=[])
    gb.j["nodes"][-1].pop("children")
    gb.j["cameras"] = [{"type": "perspective", "name": "Camera vandr",
                        "perspective": {"yfov": 0.8, "znear": 0.1}}]
    gb.node(None, name="Camera", camera=0)
    gb.j["extensions"] = {"KHR_lights_punctual": {"lights": [{"type": "point", "name": "Svetlo Suplik"}]}}
    gb.node(None, name="Light", extensions={"KHR_lights_punctual": {"light": 0}})
    gb.box((5, 5, 5), name="logo")       # osirely mesh (zadny uzel) -> GC
    gb.j["asset"].update(generator="vanDrawee exporter 1.0", copyright="Logiman s.r.o.",
                         extras={"source": "Suplik"})
    gb.j["extras"] = {"author": "bot10"}
    gb.j["extensionsUsed"] = ["KHR_lights_punctual", "KHR_materials_clearcoat"]
    if extra:
        extra(gb)
    return gb


# box = AABB syntetickeho modelu z vrcholu (spocitano mesh_instances, ne modulem)
SPEC = {
    "v": 1, "u": "mm", "up": [0, 1, 0], "front": [-1, 0, 0],
    "box": {"min": [-940, 10, -445], "max": [90, 1010, 435]}, "look": "vd",
    "dims": [{"a": [0, 0, 0], "b": [1685, 0, 0], "o": [0, -40, 0], "t": "1 685", "l": 1, "p": None},
             {"a": [0, 0, 0], "b": [0, 130, 0], "o": [20, 0, 0], "t": "130 mm", "l": 2, "p": "p01"}],
    "motions": [
        {"id": "m1", "k": "drawer", "n": 1,
         "steps": [{"p": "p01", "op": "T", "ax": [0, 0, -1], "v": 450, "ms": 600}], "pick": ["p01"]},
        {"id": "m2", "k": "box", "n": 1,
         "steps": [{"p": "p02", "op": "T", "ax": [0, 1, 0], "v": 17, "ms": 300},
                   {"p": "p02", "op": "T", "ax": [0, 0, -1], "v": 430, "ms": 600}], "pick": ["p02"]},
    ],
}


_SPEC_MIN = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0, 0, 1],
             "box": {"min": [0, 0, 0], "max": [1, 1, 1]}, "look": "nat"}


def _two_scenes(j):
    j["scenes"].append({"nodes": []})


def _spec_extra_key(j):
    s = v3d_glb.validate_spec(_SPEC_MIN)
    s["nazev"] = "x"
    j["scenes"][0]["extras"] = {"v3d": s}


# Upravy JSON vystupu BEZ zakazanych slov (FORBIDDEN_RE je nechyti) - musi
# je chytit whitelist final_check (vrstva 1 a/nebo 2).
FC_WHITELIST_ONLY = [
    lambda j: j.update(materials=[{"poznamka": "Ford Transit"}]),
    lambda j: j.update(materials=[{"alphaMode": "Ford Transit"}]),
    lambda j: j.update(materials=[{"pbrMetallicRoughness": {"x": 1}}]),
    lambda j: j.update(materials=[{"extensions": {"KHR_materials_clearcoat": {"pozn": 1}}}]),
    lambda j: j.update(materials=[{"extensions": {"KHR_materials_clearcoat": {"clearcoatFactor": "Ford"}}}]),
    lambda j: j.update(materials=[{"extensions": {"KHR_materials_ior": {"ior": 1.5}}}]),
    lambda j: j.update(materials=[{"Ѕuplik": 1}]),                    # homoglyf
    lambda j: j.update(materials=[{"name": "m1", "doubleSided": "ano"}]),
    lambda j: j["nodes"][0].update(popis=1),
    lambda j: j["nodes"][0].update(name="Ford"),
    lambda j: j["nodes"][0].update(extras={}),
    lambda j: j["asset"].update(version="2.1"),
    lambda j: j.update(scene="0"),                                        # retezec z whitelistu, spatny typ
    lambda j: j.update(accessors=[{"componentType": 5126, "count": 1, "type": "VEC3", "name": "a1"}]),
    lambda j: j.update(accessors=[{"componentType": 5126, "count": 1, "type": "MAT4"}]),
    lambda j: j.update(meshes=[{"primitives": [{"attributes": {"_Ford": 0}}]}]),
    lambda j: j.update(bufferViews=[{"buffer": 0, "byteLength": 4, "target": 1}]),
    lambda j: j.update(buffers=[{"byteLength": 4, "uri": "x.bin"}]),
    lambda j: j.update(textures=[{}]),
    lambda j: j.update(extensionsUsed=["KHR_texture_transform"]),
    lambda j: j.update(extensionsRequired=["X_tajne"]),
    lambda j: j["scenes"][0].update(extras={"v3d": dict(_SPEC_MIN)}),     # ne kanonicky tvar
    _spec_extra_key,
    _two_scenes,
]


def strip_nodes_from_parent(glb_bytes, names):
    """Simulace Blender kroku: odpoji uzly daneho jmena od rodice (meshe zustanou osirele v BIN)."""
    g, b = v3d_glb.read_glb(glb_bytes)
    kill = {i for i, n in enumerate(g["nodes"]) if n.get("name") in names}
    for n in g["nodes"]:
        if "children" in n:
            n["children"] = [c for c in n["children"] if c not in kill]
            if not n["children"]:
                del n["children"]
    for s in g["scenes"]:
        s["nodes"] = [r for r in s["nodes"] if r not in kill]
    return v3d_glb.write_glb(g, b), len(kill)


# ---------------------------------------------------------------------------
# Spolecne kontroly vystupu
# ---------------------------------------------------------------------------

class Base(unittest.TestCase):
    def assert_clean(self, out, spec=None):
        g, b = v3d_glb.read_glb(out)
        # 1) GLB obalka: zarovnani a delky
        self.assertEqual(struct.unpack_from("<I", out, 8)[0], len(out))
        jl = struct.unpack_from("<I", out, 12)[0]
        self.assertEqual(jl % 4, 0)
        if b is not None:
            self.assertEqual(len(b) % 4, 0)
            self.assertEqual(20 + jl + 8 + len(b), len(out))
        # 2) zadny zakazany retezec kdekoli v JSON (vc. klicu)
        text = out[20:20 + jl].decode("ascii")
        self.assertIsNone(FORBIDDEN_RE.search(text), "zakazany retezec v JSON: %r"
                          % (FORBIDDEN_RE.search(text) and text[max(0, FORBIDDEN_RE.search(text).start() - 40):][:100]))
        # 3) jmena a extras
        for path, k, v in walk_json(g):
            if k == "name":
                self.assertTrue(isinstance(v, str) and NAME_RE.fullmatch(v), "jmeno %r na %s" % (v, path))
                self.assertIn(path[0], ("nodes", "materials"), "jmeno mimo uzly/materialy: %s" % (path,))
            if k == "extras":
                if path[0] == "nodes" and len(path) == 3:
                    self.assertEqual(set(v), {"g"})
                    self.assertIs(type(v["g"]), int)
                else:
                    self.assertEqual(path, ("scenes", 0, "extras"))
                    self.assertEqual(set(v), {"v3d"})
            self.assertNotEqual(k, "uri")
        self.assertEqual(g["asset"], {"version": "2.0"})
        for i, n in enumerate(g["nodes"]):
            self.assertRegex(n["name"], r"^(n\d+|p\d+)$")
            if n["name"].startswith("n"):
                self.assertEqual(n["name"], "n%d" % i)
        if spec is None:
            self.assertNotIn("extras", g["scenes"][0])
        else:
            self.assertEqual(g["scenes"][0]["extras"]["v3d"], v3d_glb.validate_spec(spec))
        # 4) final_check projde a struktura je platna
        v3d_glb.final_check(g)
        v3d_glb.check_structure(g, b, "test")
        return g, b

    def assert_three(self, out, before_instances, mesh_map, name, spec=None):
        if not NODE:
            self.skipTest("node neni k dispozici")
        res = three_load(out, name)
        self.assertTrue(res.get("ok"), res.get("error"))
        self.assertEqual(res["revision"], "128")
        for nm in res["names"]:
            # mesh_<index>[_k]: jmeno, ktere si r128 GLTFLoader VYROBI sam pro
            # dilci meshe meshe s vice primitivami (GLTFLoader.js:2863), ne z GLB
            self.assertRegex(nm, r"^(n\d+|p\d+|m\d+|mesh_\d+(?:_\d+)?)?$")
        for ud in res["userData"]:
            # r128 GLTFLoader kopiruje jmeno uzlu do userData.name (GLTFLoader.js:3218)
            self.assertLessEqual(set(ud), {"g", "name"})
            if "name" in ud:
                self.assertRegex(ud["name"], r"^(n\d+|p\d+)$")
            if "g" in ud:
                self.assertIs(type(ud["g"]), int)
        if spec is not None:
            self.assertEqual(res["sceneUserData"], {"v3d": v3d_glb.validate_spec(spec)})
        else:
            self.assertEqual(res["sceneUserData"], {})
        want = [ca for mi, _j, _va, ca, _ab in before_instances if mi in mesh_map]
        match_boxes(self, want, res["prims"], what="three r128 vs vstup")


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------

class TestGlbIO(Base):
    def test_roundtrip_native(self):
        data = read(NATIVE)
        g, b = v3d_glb.read_glb(data)
        again = v3d_glb.write_glb(g, b)
        g2, b2 = v3d_glb.read_glb(again)
        self.assertEqual(g, g2)
        self.assertEqual(b, b2)
        self.assertEqual(len(again) % 4, 0)

    def test_padding(self):
        g = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 5}]}
        out = v3d_glb.write_glb(g, b"12345")
        jl = struct.unpack_from("<I", out, 12)[0]
        bl = struct.unpack_from("<I", out, 20 + jl)[0]
        self.assertEqual((jl % 4, bl), (0, 8))
        self.assertEqual(out[20 + jl + 8:], b"12345\x00\x00\x00")
        self.assertEqual(struct.unpack_from("<I", out, 8)[0], len(out))

    def test_bad_glb(self):
        for bad in (b"", b"glTF" + b"\x00" * 4, b"xxxx" + b"\x00" * 30):
            with self.assertRaises(ValueError):
                v3d_glb.read_glb(bad)
        data = bytearray(read(NATIVE))
        struct.pack_into("<I", data, 8, len(data) + 4)
        with self.assertRaises(ValueError):
            v3d_glb.read_glb(bytes(data))


class TestNative(Base):
    def setUp(self):
        self.data = read(NATIVE)
        self.before = mesh_instances(self.data)

    def _nearest_bomgrp(self):
        """mesh index -> N z nejblizsiho predka bomgrp_N ve VSTUPU."""
        g, _ = v3d_glb.read_glb(self.data)
        res = {}

        def walk(i, cur):
            n = g["nodes"][i]
            m = re.fullmatch(r"bomgrp_(\d+)", n.get("name", ""))
            cur = int(m.group(1)) if m else cur
            if "mesh" in n:
                res.setdefault(n["mesh"], set()).add(cur)
            for c in n.get("children", []):
                walk(c, cur)
        for r in g["scenes"][0]["nodes"]:
            walk(r, None)
        return res

    def test_collapse(self):
        out, rep = v3d_glb.sanitize_report(self.data)
        g, b = self.assert_clean(out)
        _, bin_in = v3d_glb.read_glb(self.data)
        self.assertFalse(rep["bin_changed"])
        self.assertEqual(b, bin_in, "BIN se nesmi zmenit")
        self.assertEqual(rep["nodes_out"], 11)        # bomgrp->world->geometry = 1 uzel
        compare_instances(self, self.before, mesh_instances(out), rep["mesh_map"])
        # g = cislo bomgrp nejblizsiho predka (zvyrazneni kusovniku zustane)
        want = self._nearest_bomgrp()
        for n in g["nodes"]:
            if "mesh" in n:
                self.assertEqual({n["extras"]["g"]}, want[n["mesh"]])
        self.assert_three(out, self.before, rep["mesh_map"], "native_collapse.glb")

    def test_no_collapse(self):
        out, rep = v3d_glb.sanitize_report(self.data, collapse=False)
        g, b = self.assert_clean(out)
        _, bin_in = v3d_glb.read_glb(self.data)
        self.assertEqual(b, bin_in)
        self.assertEqual(rep["nodes_out"], 33)
        compare_instances(self, self.before, mesh_instances(out), rep["mesh_map"])
        self.assertEqual(sum(1 for n in g["nodes"] if "extras" in n), 11)   # g na byvalych bomgrp
        self.assert_three(out, self.before, rep["mesh_map"], "native_nocollapse.glb")

    def test_idempotent(self):
        out = v3d_glb.sanitize(self.data)
        self.assertEqual(v3d_glb.sanitize(out), out)


class TestVandr(Base):
    def test_raw_catalog_guard(self):
        with self.assertRaises(ValueError) as cm:
            v3d_glb.sanitize(read(VANDR))
        self.assertIn("logo", str(cm.exception))

    def _guard_off(self, path, collapse):
        data = read(path)
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data, guard=False, collapse=collapse)
        g, b = self.assert_clean(out)
        _, bin_in = v3d_glb.read_glb(data)
        self.assertFalse(rep["bin_changed"])
        self.assertEqual(b[:len(bin_in)], bin_in)
        self.assertEqual(rep["meshes_removed"], 0)
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
        self.assert_three(out, before, rep["mesh_map"],
                          "%s_%s.glb" % (os.path.basename(path)[:-4], "c" if collapse else "nc"))
        return rep

    def test_4910_guard_off_collapse(self):
        rep = self._guard_off(VANDR, True)
        self.assertEqual(rep["nodes_out"], 256)

    def test_4910_guard_off_no_collapse(self):
        self._guard_off(VANDR, False)

    def test_4918_guard_off_collapse(self):
        self._guard_off(VANDR2, True)

    def test_precleaned(self):
        """Simulace Blender kroku (logo a podlaha odpojene) -> strazce projde,
        osirele meshe zmizi i z BIN, zbytek geometrie bajt po bajtu stejny."""
        for path in (VANDR, VANDR2):
            with self.subTest(path=os.path.basename(path)):
                data, killed = strip_nodes_from_parent(read(path), {"logo", "podlaha"})
                self.assertGreaterEqual(killed, 2)
                before = mesh_instances(data)
                out, rep = v3d_glb.sanitize_report(data)
                g, b = self.assert_clean(out)
                self.assertEqual(rep["meshes_removed"], 10)        # 9 pismen loga + podlaha
                self.assertTrue(rep["bin_changed"])
                _, bin_in = v3d_glb.read_glb(data)
                self.assertLess(len(b), len(bin_in))
                used = sum(v["byteLength"] + (-v["byteLength"] % 4) for v in g["bufferViews"])
                self.assertLessEqual(g["buffers"][0]["byteLength"], used)
                compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
                # rozmer modelu bez loga se zmensi (logo zvetsovalo koty)
                self.assertIsNotNone(rep["model_aabb"])
                self.assert_three(out, before, rep["mesh_map"], "pre_" + os.path.basename(path))


class TestSynthetic(Base):
    def test_full(self):
        data = build_synthetic().glb()
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data, SPEC)
        g, b = self.assert_clean(out, SPEC)
        names = [n["name"] for n in g["nodes"]]
        self.assertIn("p01", names)
        self.assertIn("p02", names)
        self.assertNotIn("p05", names)                     # neodkazovany pivot -> n<i>
        self.assertEqual(rep["meshes_removed"], 1)         # osirely 'logo'
        self.assertTrue(rep["bin_changed"])
        self.assertEqual(rep["cameras_removed"], 1)
        self.assertEqual(rep["extensions_removed"], ["KHR_lights_punctual"])
        self.assertEqual(g["extensionsUsed"], ["KHR_materials_clearcoat"])
        self.assertNotIn("cameras", g)
        self.assertEqual([m.get("name") for m in g["materials"]], [None, "m03", None])
        # pivoty: prazdne, jednotkova rotace, p02 je potomek p01
        by = {n["name"]: i for i, n in enumerate(g["nodes"])}
        for p in ("p01", "p02"):
            n = g["nodes"][by[p]]
            self.assertNotIn("mesh", n)
            self.assertNotIn("rotation", n)
            self.assertNotIn("matrix", n)
        self.assertIn(by["p02"], g["nodes"][by["p01"]]["children"])
        # g: explicitni g=5 na meshi, bomgrp_7 -> mesh pod nim
        gs = sorted(n["extras"]["g"] for n in g["nodes"] if "extras" in n)
        self.assertEqual(gs, [5, 7])
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
        self.assert_three(out, before, rep["mesh_map"], "synthetic.glb", SPEC)
        # znovu stejnym spec -> stejne bajty (p-jmena zustala)
        self.assertEqual(v3d_glb.sanitize(out, SPEC), out)

    def test_shear_not_collapsed(self):
        gb = GB()
        par = gb.node(None, name="scaled", scale=[1, 3, 1])
        gb.node(par, name="rot", rotation=quat_axis((0, 0, 1), 45), mesh=gb.box((100, 10, 10)))
        par2 = gb.node(None, name="uniform", scale=[2, 2, 2], translation=[5, 0, 0])
        gb.node(par2, name="rot2", rotation=quat_axis((0, 0, 1), 45), mesh=gb.box((100, 10, 10)))
        data = gb.glb()
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data)
        g, _ = self.assert_clean(out)
        self.assertEqual(rep["nodes_out"], 3)           # 'scaled' zustal, 'uniform' se sloucil
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
        self.assert_three(out, before, rep["mesh_map"], "shear.glb")

    def test_textures_rejected(self):
        """Kontrakt textury nepouziva -> images/textures/samplers ve vstupu
        (i ciste PNG bez metadat, i neodkazovane) = ValueError."""
        def full(gb):
            bv = gb.view(png_1x1())
            gb.j["images"] = [{"bufferView": bv, "mimeType": "image/png"}]
            gb.j["samplers"] = [{"magFilter": 9729}]
            gb.j["textures"] = [{"source": 0, "sampler": 0}]
            gb.j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}

        def only(key):
            def f(gb):
                if key == "images":
                    gb.j["images"] = [{"bufferView": gb.view(png_1x1()), "mimeType": "image/png"}]
                elif key == "samplers":
                    gb.j["samplers"] = [{"magFilter": 9729}]
                else:
                    gb.j["textures"] = [{}]
            return f
        for name, f in (("vse", full), ("jen images", only("images")),
                        ("jen samplers", only("samplers")), ("jen textures", only("textures"))):
            with self.subTest(case=name):
                with self.assertRaises(ValueError) as cm:
                    v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)
                self.assertIn("povolene", str(cm.exception))


class TestNativeExportLike(Base):
    """Vstup ve tvaru budouciho offer-export.js + GLTFExporter r128: pivoty jako
    matice (jen posun), userData {g} -> extras, spec v scenes[0].extras.v3d."""

    def _build(self, pivot_matrix):
        gb = GB()
        gb.j["scenes"][0]["name"] = "AuxScene"
        piv = gb.node(None, name="p01", matrix=pivot_matrix)
        gb.node(piv, name="", mesh=gb.box((400, 20, 300), (0, 0, 150)), extras={"g": 2},
                matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 10, 0, 0, 1])
        bg = gb.node(None, name="bomgrp_4_1")
        gb.node(bg, name="geometry_0", mesh=gb.box((40, 40, 900)))
        spec = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0, 0, 1],
                "box": {"min": [-190, -20, -450], "max": [210, 247.3, 450]}, "look": "nat",
                "motions": [{"id": "m1", "k": "door", "n": 1, "pick": ["p01"],
                             "steps": [{"p": "p01", "op": "R", "ax": [1, 0, 0], "v": -90, "ms": 650}]}]}
        gb.j["scenes"][0]["extras"] = {"v3d": spec}
        return gb.glb(), spec

    def test_embedded_spec(self):
        data, spec = self._build([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 237.3, 25.5, 1])
        emb = v3d_glb.embedded_spec(data)
        self.assertEqual(emb, spec)
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data, emb)
        g, _ = self.assert_clean(out, spec)
        self.assertEqual(rep["pivots"], ["p01"])
        self.assertEqual(sorted(n["extras"]["g"] for n in g["nodes"] if "extras" in n), [2, 4])
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
        self.assert_three(out, before, rep["mesh_map"], "native_like.glb", spec)
        self.assertIsNone(v3d_glb.embedded_spec(read(NATIVE)))

    def test_pivot_matrix_with_rotation(self):
        c, s = math.cos(0.3), math.sin(0.3)
        data, spec = self._build([1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 237.3, 25.5, 1])
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(data, v3d_glb.embedded_spec(data))

    def test_spec_dropped_when_not_passed(self):
        data, _spec = self._build([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 237.3, 25.5, 1])
        out = v3d_glb.sanitize(data)                    # bez spec -> zadne v3d ani p-jmena
        g, _ = self.assert_clean(out)
        self.assertFalse(any(n["name"].startswith("p") for n in g["nodes"]))


class TestForbidden(Base):
    """Synteticky GLB se zakazanym obsahem -> ValueError (model nevznikne)."""

    def test_guard_logo_subtree(self):
        def logo(gb):
            lg = gb.node(None, name="logo")
            gb.node(lg, name="Object_3", mesh=gb.box((5, 1, 5)))
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(build_synthetic(logo).glb(), SPEC)

    def test_guard_mesh_and_material_names(self):
        for mk in ("mesh", "mat"):
            with self.subTest(mk=mk):
                def f(gb, mk=mk):
                    if mk == "mesh":
                        gb.node(None, name="x", mesh=gb.box((5, 5, 5), name="podlaha.001"))
                    else:
                        gb.node(None, name="x", mesh=gb.box((5, 5, 5), material=gb.material("podlaha_2")))
                with self.assertRaises(ValueError):
                    v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)

    def test_guard_no_false_positive(self):
        def f(gb):
            c = gb.node(None, name="colliders")              # kontejner s regalem - smi
            gb.node(c, name="PopruhkufrypodlahaA459(Clone)", mesh=gb.box((5, 5, 5)))
            gb.node(None, name="LegsBox(Clone)")             # prazdny - jen se zahodi
        out = v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)
        self.assert_clean(out, SPEC)

    def test_image_uri(self):
        def f(gb):
            gb.j["images"] = [{"uri": "vandr_logo.png"}]
            gb.j["textures"] = [{"source": 0}]
            gb.j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)

    def test_required_unknown_extension(self):
        def f(gb):
            gb.j["extensionsUsed"].append("KHR_draco_mesh_compression")
            gb.j["extensionsRequired"] = ["KHR_draco_mesh_compression"]
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)

    def test_text_hidden_in_allowed_extension(self):
        """Vlastni klic v povolenem rozsireni: prestavba ho zahodi (whitelist
        klicu clearcoat), povolene hodnoty zustanou."""
        def f(gb):
            gb.j["materials"][0]["extensions"]["KHR_materials_clearcoat"]["poznamka"] = "45x45x369_Zx2"
        out, rep = v3d_glb.sanitize_report(build_synthetic(f).glb(), SPEC)
        g, _ = self.assert_clean(out, SPEC)
        self.assertNotIn(b"45x45", out)
        self.assertNotIn(b"poznamka", out)
        self.assertEqual(g["materials"][0]["extensions"], {"KHR_materials_clearcoat": {"clearcoatFactor": 0.1}})
        self.assertGreaterEqual(rep["keys_dropped"], 1)
        # kdyby se to az do final_check dostalo, odmitne to (obe vrstvy)
        j = json.loads(json.dumps(g))
        j["materials"][0]["extensions"]["KHR_materials_clearcoat"]["poznamka"] = "45x45x369_Zx2"
        with self.assertRaises(ValueError) as cm:
            v3d_glb.final_check(j)
        self.assertIn("final_check", str(cm.exception))

    def test_skin_rejected(self):
        def f(gb):
            gb.j["skins"] = [{"joints": [0]}]
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(build_synthetic(f).glb(), SPEC)

    def test_final_check_direct(self):
        ok = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
              "nodes": [{"name": "n0", "extras": {"g": 3}}]}
        v3d_glb.final_check(ok)
        bads = [
            lambda j: j["nodes"][0].update(name="Suplikocel1301057459(Clone)"),
            lambda j: j["nodes"][0].update(name="geometry_0"),
            lambda j: j["nodes"][0].update(name="45x45x1330_noha"),
            lambda j: j["nodes"][0].update(name="kolo"),                     # nepovoleny tvar
            lambda j: j["nodes"][0].update(name="m1"),                       # uzel nesmi m
            lambda j: j["nodes"][0].update(extras={"g": 3, "basePos": 1}),
            lambda j: j["nodes"][0].update(extras={"g": True}),
            lambda j: j["asset"].update(generator="THREE.GLTFExporter"),
            lambda j: j.update(extras={"a": 1}),
            lambda j: j["scenes"][0].update(name="AuxScene"),
            lambda j: j.update(materials=[{"name": "ALU"}]),
            lambda j: j.update(images=[{"uri": "x.png"}]),
            lambda j: j["nodes"][0].update(name="p01"),                      # pivot bez spec
            lambda j: j["nodes"][0].update(extensions={"KHR_lights_punctual": {"light": 0}}),
            lambda j: j.update(animations=[{"channels": [], "samplers": []}]),
        ] + [lambda j, f=f: f(j) for f in FC_WHITELIST_ONLY]
        for i, f in enumerate(bads):
            with self.subTest(i=i):
                j = json.loads(json.dumps(ok))
                f(j)
                with self.assertRaises(ValueError):
                    v3d_glb.final_check(j)

    def test_final_check_layers_independent(self):
        """Vrstva 1+2 (whitelist) chyti volny text i BEZ zakazaneho regexu;
        vrstva FORBIDDEN_RE chyti zakazany text i BEZ whitelistu."""
        ok = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
              "nodes": [{"name": "n0", "extras": {"g": 3}}]}
        saved = (v3d_glb.FORBIDDEN_RE, v3d_glb._schema_errors, v3d_glb._str_ok, v3d_glb._ALL_KEYS)
        try:
            v3d_glb.FORBIDDEN_RE = re.compile(r"(?!)")
            for i, f in enumerate(FC_WHITELIST_ONLY):
                with self.subTest(vrstva="whitelist", i=i):
                    j = json.loads(json.dumps(ok))
                    f(j)
                    with self.assertRaises(ValueError):
                        v3d_glb.final_check(j)
            v3d_glb.FORBIDDEN_RE = saved[0]

            class Vse:
                def __contains__(self, _x):
                    return True
            v3d_glb._schema_errors = lambda *a, **k: None
            v3d_glb._str_ok = lambda s: True
            v3d_glb._ALL_KEYS = Vse()
            for i, (k, v) in enumerate((("materials", [{"x": "Suplikocel1301057459(Clone)"}]),
                                        ("materials", [{"Object_3": 1}]),
                                        ("nodes", [{"name": "45x45x1330"}]))):
                with self.subTest(vrstva="FORBIDDEN_RE", i=i):
                    j = json.loads(json.dumps(ok))
                    j[k] = v
                    with self.assertRaises(ValueError):
                        v3d_glb.final_check(j)
        finally:
            (v3d_glb.FORBIDDEN_RE, v3d_glb._schema_errors, v3d_glb._str_ok, v3d_glb._ALL_KEYS) = saved


class TestSpec(Base):
    def test_valid_normalized(self):
        s = v3d_glb.validate_spec(SPEC, pivots={"p01", "p02"})
        self.assertEqual(s["motions"][0]["steps"][0]["v"], 450)
        self.assertEqual(list(s), ["v", "u", "up", "front", "box", "look", "dims", "motions"])
        minimal = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0.6, 0, 0.8],
                   "box": {"min": [0, 0, 0], "max": [1, 2, 3]}, "look": "nat"}
        self.assertEqual(v3d_glb.validate_spec(minimal)["dims"], [])

    def test_dims_m_poloha_popisku(self):
        """dims[].m (poloha popisku na care koty, generator stolu): volitelne cislo 0-1, vystup bez m beze zmeny tvaru (bot5, 2026-10-06)."""
        def s_m(*hodnoty):
            s = json.loads(json.dumps(SPEC))
            for i, m in enumerate(hodnoty):
                if m is not None:
                    s["dims"][i]["m"] = m
            return s
        bez = v3d_glb.validate_spec(SPEC, pivots={"p01", "p02"})
        self.assertTrue(all("m" not in d for d in bez["dims"]), "bez m se v nic nepridava (stejny tvar jako dosud)")
        for hodnota, ocekavano in ((0, 0), (1, 1), (0.5, 0.5), (0.25, 0.25), (1 / 3, 0.333), (0.9996, 1), (0.9994, 0.999), (0.00049, 0), (0.0005, 0.001)):
            with self.subTest(m=hodnota):
                out = v3d_glb.validate_spec(s_m(hodnota), pivots={"p01", "p02"})
                self.assertEqual(out["dims"][0]["m"], ocekavano)
                self.assertNotIn("m", out["dims"][1], "m jen tam, kde bylo zadano")
        out = v3d_glb.validate_spec(s_m(0.2, 0.8), pivots={"p01", "p02"})
        self.assertEqual([d["m"] for d in out["dims"]], [0.2, 0.8])
        # cela cesta: sanitize + final_check na syntetickem GLB s pivoty, m prezije do vystupniho specu
        spec = s_m(0.25, 1)
        glb = v3d_glb.sanitize(build_synthetic(lambda gb: None).glb(), spec)
        vystup = v3d_glb.embedded_spec(glb)
        self.assertEqual([d.get("m") for d in vystup["dims"]], [0.25, 1])
        gltf, _b = v3d_glb.read_glb(glb)
        v3d_glb.final_check(gltf)                                  # druha vrstva (globalni whitelist klicu) m pusti
        # m jinde nez ve specu dal zakazano: nahodny objekt s klicem m (hodnota jakakoli) mimo v3d.dims neprojde druhou vrstvou, pokud neni v schematu
        self.assertEqual(v3d_glb.validate_spec(s_m(0.5, 0.5), pivots={"p01", "p02"})["dims"][1]["m"], 0.5)

    def test_invalid(self):
        def mod(f):
            s = json.loads(json.dumps(SPEC))
            f(s)
            return s
        cases = {
            "neznamy klic": mod(lambda s: s.update(nazev="Suplik 1")),
            "v bool": mod(lambda s: s.update(v=True)),
            "v=2": mod(lambda s: s.update(v=2)),
            "u": mod(lambda s: s.update(u="m")),
            "up": mod(lambda s: s.update(up=[0, 0, 1])),
            "front y": mod(lambda s: s.update(front=[0.8, 0.6, 0])),
            "front delka": mod(lambda s: s.update(front=[2, 0, 0])),
            "box min>max": mod(lambda s: s.update(box={"min": [5, 0, 0], "max": [1, 1, 1]})),
            "box klic": mod(lambda s: s["box"].update(stred=[0, 0, 0])),
            "look": mod(lambda s: s.update(look="pbr")),
            "t text": mod(lambda s: s["dims"][0].update(t="Suplik")),
            "t newline": mod(lambda s: s["dims"][0].update(t="1685\n")),
            "t mezery": mod(lambda s: s["dims"][0].update(t="   ")),
            "t dlouhe": mod(lambda s: s["dims"][0].update(t="12345678")),
            "t cm": mod(lambda s: s["dims"][0].update(t="168 cm")),
            "l=3": mod(lambda s: s["dims"][0].update(l=3)),
            "a 2D": mod(lambda s: s["dims"][0].update(a=[0, 0])),
            "a NaN": mod(lambda s: s["dims"][0].update(a=[0, float("nan"), 0])),
            "a inf": mod(lambda s: s["dims"][0].update(a=[0, float("inf"), 0])),
            "a string": mod(lambda s: s["dims"][0].update(a=[0, "1", 0])),
            "a obri": mod(lambda s: s["dims"][0].update(a=[0, 1e9, 0])),
            "dim p chybi v modelu": mod(lambda s: s["dims"][1].update(p="p09")),
            "dim p tvar": mod(lambda s: s["dims"][1].update(p="Suplik")),
            "dim bez o": mod(lambda s: s["dims"][0].pop("o")),
            "dim m zaporne": mod(lambda s: s["dims"][0].update(m=-0.1)),
            "dim m > 1": mod(lambda s: s["dims"][0].update(m=1.0001)),
            "dim m text": mod(lambda s: s["dims"][0].update(m="0.5")),
            "dim m null": mod(lambda s: s["dims"][0].update(m=None)),
            "dim m bool": mod(lambda s: s["dims"][0].update(m=True)),
            "dim m NaN": mod(lambda s: s["dims"][0].update(m=float("nan"))),
            "dim m inf": mod(lambda s: s["dims"][0].update(m=float("inf"))),
            "dim m seznam": mod(lambda s: s["dims"][0].update(m=[0.5])),
            "dim jiny klic vedle m": mod(lambda s: s["dims"][0].update(m=0.5, x=1)),
            "id tvar": mod(lambda s: s["motions"][0].update(id="suplik1")),
            "id duplicita": mod(lambda s: s["motions"][1].update(id="m1")),
            "k": mod(lambda s: s["motions"][0].update(k="rotate")),
            "n 0": mod(lambda s: s["motions"][0].update(n=0)),
            "n float": mod(lambda s: s["motions"][0].update(n=1.0)),
            "steps prazdne": mod(lambda s: s["motions"][0].update(steps=[])),
            "step klic": mod(lambda s: s["motions"][0]["steps"][0].update(label="Suplik")),
            "op": mod(lambda s: s["motions"][0]["steps"][0].update(op="S")),
            "ax neni jednotkovy": mod(lambda s: s["motions"][0]["steps"][0].update(ax=[0, 0, -2])),
            "v moc": mod(lambda s: s["motions"][0]["steps"][0].update(v=99999)),
            "R uhel": mod(lambda s: s["motions"][0]["steps"][0].update(op="R", v=720)),
            "ms zaporne": mod(lambda s: s["motions"][0]["steps"][0].update(ms=-1)),
            "ms float": mod(lambda s: s["motions"][0]["steps"][0].update(ms=300.5)),
            "step p chybi": mod(lambda s: s["motions"][0]["steps"][0].update(p="p07")),
            "pick chybi": mod(lambda s: s["motions"][0].update(pick=["p08"])),
            "pick text": mod(lambda s: s["motions"][0].update(pick="p01")),
            "spec neni dict": [1, 2],
        }
        for name, spec in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    v3d_glb.validate_spec(spec, pivots={"p01", "p02"})

    def test_pivot_rules_in_glb(self):
        def rotated(gb):
            gb.j["nodes"][2]["rotation"] = quat_axis((0, 1, 0), 10)   # p01
        def with_mesh(gb):
            gb.j["nodes"][2]["mesh"] = 0
        def duplicate(gb):
            gb.node(None, name="p01", mesh=gb.box((1, 1, 1)))
        def unreachable(gb):
            gb.j["nodes"].append({"name": "p03"})
        def empty_pivot(gb):
            gb.node(None, name="p03")
        spec3 = json.loads(json.dumps(SPEC))
        spec3["motions"].append({"id": "m3", "k": "door", "n": 1,
                                 "steps": [{"p": "p03", "op": "R", "ax": [1, 0, 0], "v": -90, "ms": 600}]})
        for name, f, spec in (("rotace", rotated, SPEC), ("mesh", with_mesh, SPEC),
                              ("duplicita", duplicate, SPEC), ("mimo scenu", unreachable, spec3),
                              ("prazdny pivot", empty_pivot, spec3)):
            with self.subTest(case=name):
                with self.assertRaises(ValueError):
                    v3d_glb.sanitize(build_synthetic(f).glb(), spec)

    def test_spec_on_native_without_pivots(self):
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(read(NATIVE), SPEC)          # p01 v modelu neni
        spec = {k: v for k, v in SPEC.items() if k not in ("motions", "dims")}
        # box = AABB nativni fixtury z vrcholu (mesh_instances)
        spec["box"] = {"min": [-100, -40, -850], "max": [508.6, 490.001, 1146.03]}
        out, rep = v3d_glb.sanitize_report(read(NATIVE), spec)
        self.assert_clean(out, spec)
        self.assertEqual(rep["warnings"], [])


class TestSideG(Base):
    """motions[].g (left | right | bulkhead, volitelne) - bot10 2026-10-06 (spolecna nabidka). Bez g beze zmeny."""

    @staticmethod
    def _spec(**kw):
        s = json.loads(json.dumps(SPEC))
        s["motions"][1].update(kw)
        return s

    def test_valid_and_kept(self):
        for g in v3d_glb._SIDES:
            with self.subTest(g=g):
                spec = self._spec(g=g)
                v = v3d_glb.validate_spec(spec, pivots={"p01", "p02"})
                self.assertEqual(v["motions"][1]["g"], g)
                self.assertNotIn("g", v["motions"][0])
                out = v3d_glb.sanitize(build_synthetic().glb(), spec)
                gl, _ = self.assert_clean(out, spec)
                self.assertEqual(gl["scenes"][0]["extras"]["v3d"]["motions"][1]["g"], g)
                self.assertEqual(v3d_glb.sanitize(out, spec), out)

    def test_without_g_unchanged(self):
        v = v3d_glb.validate_spec(SPEC, pivots={"p01", "p02"})
        for m in v["motions"]:
            self.assertNotIn("g", m)
        self.assertNotIn(b'"left"', v3d_glb.sanitize(build_synthetic().glb(), SPEC))

    def test_invalid(self):
        for g in ["Left", "LEFT", "left ", "", "bulkhead\n", "side", "levá", "p01", None, 1, True, ["left"], {"a": 1}]:
            with self.subTest(g=g):
                with self.assertRaises(ValueError):
                    v3d_glb.validate_spec(self._spec(g=g), pivots={"p01", "p02"})
                with self.assertRaises(ValueError):
                    v3d_glb.sanitize(build_synthetic().glb(), self._spec(g=g))


class TestSub(Base):
    """motions[].sub (vycet klt | multibox | eurobox | kufrik, jen u k=box) - Robert 2026-10-02.
    Spec bez sub zustava platny a vystup beze zmeny; do GLB se dostane jen vycet."""

    @staticmethod
    def _spec(**kw):
        s = json.loads(json.dumps(SPEC))
        s["motions"][1].update(kw)                    # m2 = box
        return s

    @staticmethod
    def _spec_k(k, **kw):
        s = json.loads(json.dumps(SPEC))
        s["motions"][0]["k"] = k                      # m1 = puvodne drawer
        s["motions"][0].update(kw)
        return s

    def test_backward_compat_no_sub(self):
        v = v3d_glb.validate_spec(SPEC, pivots={"p01", "p02"})
        for m in v["motions"]:
            self.assertEqual(list(m), ["id", "k", "n", "steps", "pick"])       # beze zmeny proti v1 bez sub
        out = v3d_glb.sanitize(build_synthetic().glb(), SPEC)
        self.assert_clean(out, SPEC)
        self.assertNotIn(b'"sub"', out)

    def test_sub_valid(self):
        for sub in v3d_glb._SUBS:
            with self.subTest(sub=sub):
                spec = self._spec(sub=sub)
                v = v3d_glb.validate_spec(spec, pivots={"p01", "p02"})
                self.assertEqual(list(v["motions"][1]), ["id", "k", "sub", "n", "steps", "pick"])
                self.assertEqual(v["motions"][1]["sub"], sub)
                self.assertNotIn("sub", v["motions"][0])
                out = v3d_glb.sanitize(build_synthetic().glb(), spec)
                g, _ = self.assert_clean(out, spec)
                self.assertEqual(g["scenes"][0]["extras"]["v3d"]["motions"][1]["sub"], sub)
                self.assertEqual(out.count(sub.encode()), 1)                   # jen jednou, jen jako hodnota sub
                self.assertEqual(v3d_glb.sanitize(out, spec), out)             # idempotence

    def test_sub_invalid(self):
        bad = ["KLT", "Klt", "klt ", " klt", "klt\n", "klt box", "box", "", "Eurobox", "euro", "drawer", "p01", "Multibox",
               "multibox\x00", "kлlt", "Vysuv.KLT3.147.1357.459", "<b>klt</b>", None, 1, 0, True, False, 1.5,
               ["klt"], {"klt": 1}, ("klt",)]
        for sub in bad:
            with self.subTest(sub=sub):
                with self.assertRaises(ValueError):
                    v3d_glb.validate_spec(self._spec(sub=sub), pivots={"p01", "p02"})
                with self.assertRaises(ValueError):
                    v3d_glb.sanitize(build_synthetic().glb(), self._spec(sub=sub))
        # sub jen u k=box
        for k in ("drawer", "door", "floor_door", "slide"):
            for sub in v3d_glb._SUBS:
                with self.subTest(k=k, sub=sub):
                    with self.assertRaises(ValueError) as cm:
                        v3d_glb.validate_spec(self._spec_k(k, sub=sub), pivots={"p01", "p02"})
                    self.assertIn("k=box", str(cm.exception))

    def test_sub_in_final_check(self):
        """final_check: sub mimo vycet / u jineho druhu / na jinem miste je odmitnuto (vrstva 1 i 2)."""
        spec = v3d_glb.validate_spec(self._spec(sub="klt"), pivots={"p01", "p02"})
        base = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0, 1, 2], "extras": {"v3d": spec}}],
                "nodes": [{"name": "p01"}, {"name": "p02"}, {"name": "n2", "extras": {"g": 3}}]}
        v3d_glb.final_check(json.loads(json.dumps(base)))
        bads = {
            "sub mimo vycet": lambda j: j["scenes"][0]["extras"]["v3d"]["motions"][1].update(sub="Suplik"),
            "sub volny text": lambda j: j["scenes"][0]["extras"]["v3d"]["motions"][1].update(sub="Vysuv.KLT3.147"),
            "sub na drawer": lambda j: j["scenes"][0]["extras"]["v3d"]["motions"][0].update(sub="klt"),
            "sub neni retezec": lambda j: j["scenes"][0]["extras"]["v3d"]["motions"][1].update(sub=["klt"]),
            "jmeno uzlu klt": lambda j: j["nodes"][2].update(name="klt"),
            "extras uzlu": lambda j: j["nodes"][2].update(extras={"g": 3, "sub": "klt"}),
            "klic sub na scene": lambda j: j["scenes"][0]["extras"].update(sub="klt"),
        }
        for name, f in bads.items():
            with self.subTest(case=name):
                j = json.loads(json.dumps(base))
                f(j)
                with self.assertRaises(ValueError):
                    v3d_glb.final_check(j)

    def test_sub_in_native_branch(self):
        """Nativni vetev: spec se sub uvnitr GLB (scenes[0].extras.v3d) -> embedded_spec -> sanitize."""
        spec = self._spec(sub="eurobox")
        g, b = v3d_glb.read_glb(build_synthetic().glb())
        g["scenes"][0]["extras"] = {"v3d": spec}
        emb = v3d_glb.write_glb(g, b)
        self.assertEqual(v3d_glb.embedded_spec(emb), spec)
        self.assert_clean(v3d_glb.sanitize(emb, v3d_glb.embedded_spec(emb)), spec)
        spec["motions"][1]["sub"] = "Eurobox"
        g["scenes"][0]["extras"] = {"v3d": spec}
        emb = v3d_glb.write_glb(g, b)
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(emb, v3d_glb.embedded_spec(emb))


class TestStructure(Base):
    def test_broken_indices(self):
        g, b = v3d_glb.read_glb(read(NATIVE))
        breakers = [
            lambda j: j["nodes"][0].update(mesh=999),
            lambda j: j["nodes"][1].update(children=[1]),
            lambda j: j["accessors"][0].update(count=10 ** 7),
            lambda j: j["bufferViews"][0].update(byteOffset=10 ** 8),
            lambda j: j["meshes"][0]["primitives"][0]["attributes"].update(POSITION=999),
            lambda j: j["scenes"][0]["nodes"].append(0),     # potomek jako koren
            lambda j: j["nodes"][0].update(matrix=[1, 0, 0]),
        ]
        for i, f in enumerate(breakers):
            with self.subTest(i=i):
                j = json.loads(json.dumps(g))
                f(j)
                with self.assertRaises(ValueError):
                    v3d_glb.sanitize(v3d_glb.write_glb(j, b))

    def test_cycle(self):
        gb = GB()
        a = gb.node(None, name="a", mesh=gb.box())
        bb = gb.node(a, name="b")
        gb.j["nodes"][bb]["children"] = [a]
        gb.j["scenes"][0]["nodes"] = []
        gb.node(None, name="c", mesh=gb.box())
        with self.assertRaises(ValueError):
            v3d_glb.sanitize(gb.glb())


# ---------------------------------------------------------------------------
# Utoky nezavisle kontroly (prevzato z tmp/kontrola/adv_sanitize.py)
# ---------------------------------------------------------------------------

SECRET = "Ford Transit L3H3 SKU DIL-777"      # zamerne NEchyceny FORBIDDEN_RE
SECRET_B = SECRET.encode()
NEEDLES = [SECRET_B, b"Ford", b"DIL-777", b"tajne", "Ѕ".encode("utf-8"), b"\\u0405"]

SPEC_ADV = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [-1, 0, 0],
            "box": {"min": [-50, -50, -50], "max": [325, 50, 50]}, "look": "vd", "dims": [],
            "motions": [{"id": "m1", "k": "drawer", "n": 1,
                         "steps": [{"p": "p01", "op": "T", "ax": [-1, 0, 0], "v": 100, "ms": 300}],
                         "pick": ["p01"]}]}


def adv_base():
    gb = GB()
    m = gb.material("m01")
    p = gb.node(None, name="p01", translation=[0, 0, 0])
    gb.node(p, mesh=gb.box((100, 100, 100), (0, 0, 0), m))
    gb.node(None, mesh=gb.box((50, 50, 50), (300, 0, 0), m))
    return gb


def png_with(chunks_before_idat=(), after_iend=b""):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
    for t, d in chunks_before_idat:
        out += chunk(t, d)
    return out + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b"") + after_iend


def jpeg_min(trailing=b"", com_after_sos=False):
    soi = b"\xff\xd8"
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    sos = b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
    tail = b""
    if com_after_sos:
        tail = b"\xff\xfe" + struct.pack(">H", 2 + len(SECRET_B)) + SECRET_B
    return soi + app0 + sos + b"\x12\x34\x56" + tail + b"\xff\xd9" + trailing


def with_texture(gb, img_bytes, mime, tex_extra=None, smp_extra=None):
    bv = gb.view(img_bytes)
    gb.j["images"] = [{"bufferView": bv, "mimeType": mime}]
    gb.j["samplers"] = [dict({"magFilter": 9729}, **(smp_extra or {}))]
    gb.j["textures"] = [dict({"source": 0, "sampler": 0}, **(tex_extra or {}))]
    gb.j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0}


def _webp_text(gb):
    body = (b"WEBP" + b"VP8L" + struct.pack("<I", 5) + b"\x2f\x00\x00\x00\x00" + b"\x00"
            + b"TEXT" + struct.pack("<I", len(SECRET_B)) + SECRET_B + (b"\x00" if len(SECRET_B) & 1 else b""))
    with_texture(gb, b"RIFF" + struct.pack("<I", len(body)) + body, "image/webp")


def _bin_in_used_view(gb):
    # POSITION view prodlouzime o text (accessor ho nepokryje)
    v = gb.j["bufferViews"][gb.j["accessors"][0]["bufferView"]]
    data = bytes(gb.bin[v["byteOffset"]:v["byteOffset"] + v["byteLength"]]) + SECRET_B
    gb.bin += b"\x00" * (-len(gb.bin) % 4)
    v["byteOffset"] = len(gb.bin)
    v["byteLength"] = len(data)
    gb.bin += data


def _attr_key(gb):
    p = gb.j["meshes"][0]["primitives"][0]
    p["attributes"]["_Ford_Transit_L3H3_DIL777"] = p["attributes"]["POSITION"]


def _camera(gb):
    gb.j["cameras"] = [{"type": "perspective", "name": SECRET, "perspective": {"yfov": 1, "znear": 0.1}}]
    gb.node(None, camera=0, name=SECRET)


def _texinfo_key(gb):
    with_texture(gb, png_1x1(), "image/png")
    gb.j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["popis"] = SECRET


def _tex_transform(gb):
    with_texture(gb, png_1x1(), "image/png")
    gb.j["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["extensions"] = {
        "KHR_texture_transform": {"offset": [0, 0], "pozn": SECRET}}


def _ext_required(gb):
    gb.j["extensionsUsed"] = ["X_tajne"]
    gb.j["extensionsRequired"] = ["X_tajne"]


def _image_named(gb):
    with_texture(gb, png_1x1(), "image/png")
    gb.j["images"][0].update(name=SECRET, popis=SECRET)


CISTI, ODMITNE = "cisti", "odmitne"
ATTACKS = [
    ("material: neznamy klic s volnym textem", CISTI, lambda gb: gb.j["materials"][0].update(poznamka=SECRET)),
    ("material: alphaMode = volny text", ODMITNE, lambda gb: gb.j["materials"][0].update(alphaMode=SECRET)),
    ("pbrMetallicRoughness: neznamy klic", CISTI,
     lambda gb: gb.j["materials"][0]["pbrMetallicRoughness"].update(x=SECRET)),
    ("material: extras", CISTI, lambda gb: gb.j["materials"][0].update(extras={"sku": SECRET})),
    ("material: povolene rozsireni s vlastnim klicem", CISTI, lambda gb: gb.j["materials"][0].update(
        extensions={"KHR_materials_clearcoat": {"clearcoatFactor": 1, "pozn": SECRET}})),
    ("material: vnorene extensions s vlastnim jmenem", CISTI, lambda gb: gb.j["materials"][0].update(
        extensions={"KHR_materials_clearcoat": {"extensions": {"X_vlastni": {"t": SECRET}}}})),
    ("mesh: neznamy klic", CISTI, lambda gb: gb.j["meshes"][0].update(popis=SECRET)),
    ("mesh: extras.targetNames", CISTI, lambda gb: gb.j["meshes"][0].update(extras={"targetNames": [SECRET]})),
    ("primitive: neznamy klic", CISTI, lambda gb: gb.j["meshes"][0]["primitives"][0].update(popis=SECRET)),
    ("primitive: vlastni atribut _<text> (jmeno klice)", CISTI, _attr_key),
    ("accessor: name", CISTI, lambda gb: gb.j["accessors"][0].update(name=SECRET)),
    ("accessor: neznamy klic", CISTI, lambda gb: gb.j["accessors"][0].update(popis=SECRET)),
    ("bufferView: name + neznamy klic", CISTI, lambda gb: gb.j["bufferViews"][0].update(name=SECRET, popis=SECRET)),
    ("buffers[0]: name", CISTI, lambda gb: gb.j.setdefault("_post", []).append(
        lambda j: j["buffers"][0].update(name=SECRET))),
    ("node: neznamy klic", CISTI, lambda gb: gb.j["nodes"][1].update(popis=SECRET)),
    ("scene: name + neznamy klic", CISTI, lambda gb: gb.j["scenes"][0].update(name=SECRET, popis=SECRET)),
    ("asset: generator/copyright/extras", CISTI,
     lambda gb: gb.j["asset"].update(generator=SECRET, copyright=SECRET, extras={"a": SECRET})),
    ("top-level: extras + vlastni klic + extensions", CISTI,
     lambda gb: gb.j.update(extras={"a": SECRET}, popis=SECRET, extensions={"X_vlastni": {"t": SECRET}})),
    ("extensionsUsed: vlastni jmeno (nepovinne)", CISTI,
     lambda gb: gb.j.update(extensionsUsed=["X_" + SECRET.replace(" ", "_")])),
    ("extensionsRequired: vlastni jmeno", ODMITNE, _ext_required),
    ("cameras: jmeno", CISTI, _camera),
    ("animations: jmeno + kanaly", CISTI,
     lambda gb: gb.j.update(animations=[{"name": SECRET, "channels": [], "samplers": []}])),
    ("skins: jmeno", ODMITNE, lambda gb: gb.j.update(skins=[{"joints": [1], "name": SECRET}])),
    ("images.uri (data:)", ODMITNE,
     lambda gb: gb.j.update(images=[{"uri": "data:text/plain;base64,Rm9yZA==", "name": SECRET}])),
    ("images: name + neznamy klic (bufferView)", ODMITNE, _image_named),
    ("samplers: name + neznamy klic", ODMITNE,
     lambda gb: with_texture(gb, png_1x1(), "image/png", smp_extra={"name": SECRET, "popis": SECRET})),
    ("textures: name + neznamy klic", ODMITNE,
     lambda gb: with_texture(gb, png_1x1(), "image/png", tex_extra={"name": SECRET, "popis": SECRET})),
    ("textureInfo: neznamy klic", ODMITNE, _texinfo_key),
    ("PNG: tEXt chunk", ODMITNE,
     lambda gb: with_texture(gb, png_with([(b"tEXt", b"Comment\x00" + SECRET_B)]), "image/png")),
    ("PNG: vlastni KRITICKY chunk", ODMITNE,
     lambda gb: with_texture(gb, png_with([(b"ZzZz", SECRET_B)]), "image/png")),
    ("PNG: data za IEND", ODMITNE, lambda gb: with_texture(gb, png_with(after_iend=SECRET_B), "image/png")),
    ("JPEG: data za EOI", ODMITNE, lambda gb: with_texture(gb, jpeg_min(trailing=SECRET_B), "image/jpeg")),
    ("JPEG: COM za SOS", ODMITNE, lambda gb: with_texture(gb, jpeg_min(com_after_sos=True), "image/jpeg")),
    ("WebP: vlastni chunk", ODMITNE, _webp_text),
    ("BIN: text uvnitr pouziteho bufferView za koncem accessoru", CISTI, _bin_in_used_view),
    ("BIN: text v neodkazovanem bufferView", CISTI, lambda gb: gb.view(SECRET_B)),
    ("BIN: text za koncem buffers[0].byteLength", CISTI, lambda gb: gb.j.setdefault("_tail", SECRET_B)),
    ("GLB: treti neznamy chunk s textem", CISTI, lambda gb: gb.j.setdefault("_chunk3", SECRET_B)),
    ("KHR_texture_transform s vlastnim klicem", ODMITNE, _tex_transform),
    ("homoglyf v neznamem klici materialu", CISTI,
     lambda gb: gb.j["materials"][0].update(x="Ѕuplik 45Х5Х369")),
]


def build_attack(f):
    gb = adv_base()
    f(gb)
    tail = gb.j.pop("_tail", b"")
    ch3 = gb.j.pop("_chunk3", None)
    posts = gb.j.pop("_post", [])
    gb.j["buffers"] = [{"byteLength": len(gb.bin)}]
    for p in posts:
        p(gb.j)
    data = v3d_glb.write_glb(gb.j, bytes(gb.bin) + tail)
    if ch3 is not None:
        c = ch3 + b" " * (-len(ch3) % 4)
        data = data + struct.pack("<II", len(c), 0x12345678) + c
        data = data[:8] + struct.pack("<I", len(data)) + data[12:]
    return data


class TestAttacks(Base):
    def test_attacks(self):
        self.assertEqual(len(ATTACKS), 40)
        for name, want, f in ATTACKS:
            for spec in (None, SPEC_ADV):
                with self.subTest(utok=name, spec=spec is not None):
                    data = build_attack(f)
                    self.assertTrue(any(n in data for n in NEEDLES), "utok nic nevlozil")
                    if want == ODMITNE:
                        with self.assertRaises(ValueError):
                            v3d_glb.sanitize(data, copy.deepcopy(spec))
                        continue
                    try:
                        out = v3d_glb.sanitize(data, copy.deepcopy(spec))
                    except ValueError as e:
                        self.fail("utok %r mel byt vycisten, skoncil chybou: %s" % (name, e))
                    self.assertEqual([n for n in NEEDLES if n in out], [], "tajny text prosakuje")
                    self.assert_clean(out, spec)


# ---------------------------------------------------------------------------
# Whitelist objektu, BIN, spec.box, vystupy Blender kroku
# ---------------------------------------------------------------------------

class TestWhitelist(Base):
    def _one(self, f, spec=SPEC_ADV):
        gb = adv_base()
        f(gb)
        return gb.glb()

    def test_rejected_values(self):
        cases = {
            "alphaMode": lambda gb: gb.j["materials"][0].update(alphaMode="opaque"),
            "doubleSided text": lambda gb: gb.j["materials"][0].update(doubleSided="true"),
            "baseColorFactor 3": lambda gb: gb.j["materials"][0]["pbrMetallicRoughness"].update(
                baseColorFactor=[1, 1, 1]),
            "clearcoat text": lambda gb: gb.j["materials"][0].update(
                extensions={"KHR_materials_clearcoat": {"clearcoatFactor": "1"}}),
            "bufferView target": lambda gb: gb.j["bufferViews"][0].update(target=34000),
            "POSITION MAT4": lambda gb: gb.j["accessors"].__setitem__(0, dict(
                gb.j["accessors"][0], type="MAT4", count=1, min=[0] * 16, max=[0] * 16)),
            "TEXCOORD_0 MAT4": lambda gb: (
                gb.j["accessors"].append({"bufferView": gb.view(b"\x00" * 64), "componentType": 5126,
                                          "count": 1, "type": "MAT4"}),
                gb.j["meshes"][0]["primitives"][0]["attributes"].update(TEXCOORD_0=len(gb.j["accessors"]) - 1)),
            "sparse": lambda gb: gb.j["accessors"][0].update(sparse={
                "count": 1, "indices": {"bufferView": 1, "componentType": 5123},
                "values": {"bufferView": 0}}),
            "morph targets": lambda gb: gb.j["meshes"][0]["primitives"][0].update(targets=[{"POSITION": 0}]),
            "bez POSITION": lambda gb: gb.j["meshes"][0]["primitives"][0]["attributes"].update(
                NORMAL=gb.j["meshes"][0]["primitives"][0]["attributes"].pop("POSITION")),
        }
        for name, f in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(ValueError) as cm:
                    v3d_glb.sanitize(self._one(f), SPEC_ADV)
                # odmitnout uz pri prestavbe vstupu, ne az druhou vrstvou ve final_check
                self.assertTrue(str(cm.exception).startswith("vstup"), str(cm.exception))

    def test_attributes_and_extensions_filtered(self):
        def f(gb):
            p = gb.j["meshes"][0]["primitives"][0]
            pos = p["attributes"]["POSITION"]
            acc = gb.j["accessors"]
            # JOINTS_0 / WEIGHTS_0 / _CUSTOM: vlastni data, ktera musi zmizet i z BIN
            for nm, typ, comp, size in (("JOINTS_0", "VEC4", 5121, 4), ("WEIGHTS_0", "VEC4", 5126, 16),
                                        ("_CUSTOM", "SCALAR", 5126, 4)):
                bv = gb.view(b"\x07" * (8 * size))
                acc.append({"bufferView": bv, "componentType": comp, "count": 8, "type": typ})
                p["attributes"][nm] = len(acc) - 1
            p["attributes"]["TEXCOORD_0"] = len(acc)
            acc.append({"bufferView": gb.view(b"\x00\x00\x80\x3f" * 16), "componentType": 5126,
                        "count": 8, "type": "VEC2"})
            self.assertIn(pos, p["attributes"].values())
            gb.j["materials"][0].update(alphaMode="MASK", alphaCutoff=0.4, emissiveFactor=[0, 0, 0],
                                        extensions={"KHR_materials_unlit": {"x": 1},
                                                    "KHR_materials_ior": {"ior": 1.4},
                                                    "KHR_materials_emissive_strength": {"emissiveStrength": 2}})
            gb.j["extensionsUsed"] = ["KHR_materials_unlit", "KHR_materials_ior", "KHR_materials_emissive_strength"]
        data = self._one(f)
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data, SPEC_ADV)
        g, b = self.assert_clean(out, SPEC_ADV)
        self.assertEqual(rep["attributes_dropped"], 3)
        self.assertEqual(sorted(g["meshes"][0]["primitives"][0]["attributes"]), ["POSITION", "TEXCOORD_0"])
        self.assertNotIn(b"\x07\x07\x07\x07", b)
        self.assertEqual(rep["extensions_removed"], ["KHR_materials_emissive_strength", "KHR_materials_ior"])
        m = g["materials"][0]
        self.assertEqual((m["alphaMode"], m["alphaCutoff"], m["extensions"]),
                         ("MASK", 0.4, {"KHR_materials_unlit": {}}))
        self.assertEqual(g["extensionsUsed"], ["KHR_materials_unlit"])
        # atributy se zmenily (3 zahozene) -> porovnat svetove AABB a bajty POSITION
        after = mesh_instances(out)
        match_boxes(self, [x[2] for x in before], [x[2] for x in after])
        gi, bi = v3d_glb.read_glb(data)
        self.assertEqual(accessor_bytes(gi, bi, 0), accessor_bytes(g, b, g["meshes"][0]["primitives"][0]
                                                                   ["attributes"]["POSITION"]))
        self.assertEqual(v3d_glb.sanitize(out, SPEC_ADV), out)          # idempotence

    def test_output_keys_only_from_whitelist(self):
        """Vsechny vystupy testu: kazdy objekt jen s klici z _SCHEMA."""
        for data, spec in ((read(NATIVE), None), (build_synthetic().glb(), SPEC)):
            g, _ = v3d_glb.read_glb(v3d_glb.sanitize(data, spec))
            for kind, arr in (("node", "nodes"), ("mesh", "meshes"), ("material", "materials"),
                              ("accessor", "accessors"), ("bufferView", "bufferViews"), ("buffer", "buffers")):
                for o in g.get(arr, []):
                    self.assertLessEqual(set(o), set(v3d_glb._SCHEMA[kind]), arr)
            self.assertLessEqual(set(g), set(v3d_glb._SCHEMA["gltf"]))


def interleaved_glb(gap_bytes=b"\x00\x00\x00\x00", orphan=False):
    """POSITION + NORMAL prokladane v jednom bufferView (stride 28 = 12+12+4
    mezera). orphan=True: druhy accessor POSITION ve stejnem view patri
    osirelemu meshi (zadny uzel)."""
    gb = GB()
    pts = [(x, y, z) for x in (-50, 50) for y in (0, 100) for z in (-20, 20)]
    nrm = [(0.0, 1.0, 0.0)] * 8
    blob = b"".join(struct.pack("<3f", *p) + struct.pack("<3f", *n) + gap_bytes for p, n in zip(pts, nrm))
    if orphan:
        blob += b"".join(struct.pack("<3f", p[0] + 1000, p[1], p[2]) + b"\x00" * 16 for p in pts)
    bv = gb.view(blob, byteStride=28, target=34962)
    idx = [0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3]
    iv = gb.view(struct.pack("<%dH" % len(idx), *idx), target=34963)
    acc = gb.j["accessors"]
    acc.append({"bufferView": bv, "componentType": 5126, "count": 8, "type": "VEC3",
                "min": [-50, 0, -20], "max": [50, 100, 20]})
    acc.append({"bufferView": bv, "byteOffset": 12, "componentType": 5126, "count": 8, "type": "VEC3"})
    acc.append({"bufferView": iv, "componentType": 5123, "count": len(idx), "type": "SCALAR"})
    gb.j["meshes"].append({"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2}]})
    gb.node(None, name="a", mesh=0)
    if orphan:
        acc.append({"bufferView": bv, "byteOffset": 8 * 28, "componentType": 5126, "count": 8, "type": "VEC3",
                    "min": [950, 0, -20], "max": [1050, 100, 20]})
        gb.j["meshes"].append({"primitives": [{"attributes": {"POSITION": 3}, "indices": 2}]})
    return gb.glb()


class TestBinCoverage(Base):
    def test_interleaved_gap_zeroed(self):
        data = interleaved_glb(gap_bytes=b"Ford")
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data)
        g, b = self.assert_clean(out)
        self.assertNotIn(b"Ford", out)
        self.assertEqual(rep["bytes_zeroed"], 32)
        self.assertTrue(rep["bin_changed"])
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
        self.assert_three(out, before, rep["mesh_map"], "interleaved.glb")
        # cista mezera -> BIN beze zmeny, bajt po bajtu
        clean = interleaved_glb()
        out2, rep2 = v3d_glb.sanitize_report(clean)
        self.assertFalse(rep2["bin_changed"])
        self.assertEqual(v3d_glb.read_glb(out2)[1], v3d_glb.read_glb(clean)[1])

    def test_orphan_accessor_in_shared_view_zeroed(self):
        data = interleaved_glb(orphan=True)
        before = mesh_instances(data)
        out, rep = v3d_glb.sanitize_report(data)
        g, b = self.assert_clean(out)
        self.assertEqual(rep["meshes_removed"], 1)
        self.assertEqual(rep["accessors_removed"], 1)
        self.assertGreater(rep["bytes_zeroed"], 0)
        v = g["bufferViews"][g["accessors"][0]["bufferView"]]
        tail = b[v["byteOffset"] + 8 * 28: v["byteOffset"] + v["byteLength"]]
        self.assertEqual(tail, b"\x00" * len(tail))           # vrcholy osireleho meshe pryc
        compare_instances(self, before, mesh_instances(out), rep["mesh_map"])

    def test_check_bin_direct(self):
        out = v3d_glb.sanitize(interleaved_glb())
        g, b = v3d_glb.read_glb(out)
        b = b[:g["buffers"][0]["byteLength"]]
        v3d_glb.check_bin(g, b)
        for pos, hidden in ((24, True), (27, True), (52, True), (220, True),   # mezery v prokladanych prvcich
                            (0, False), (12, False), (230, False)):           # data accessoru - smi
            bb = bytearray(b)
            bb[pos] ^= 0x41
            with self.subTest(pos=pos):
                if hidden:
                    with self.assertRaises(ValueError):
                        v3d_glb.check_bin(g, bytes(bb))
                else:
                    v3d_glb.check_bin(g, bytes(bb))
        # padding za koncem posledniho view (bufferView kratsi nez buffer)
        g2 = json.loads(json.dumps(g))
        g2["bufferViews"][1]["byteLength"] -= 2
        g2["accessors"][2]["count"] -= 1
        with self.assertRaises(ValueError):
            v3d_glb.check_bin(g2, b)


def octa_glb(r=500.0, deg=45.0, far_box=False, drop_minmax=False):
    """Osmisten (6 vrcholu na osach) otoceny o deg kolem Y: rohy lokalniho
    boxu po otoceni sahaji na r*sqrt(2), skutecne vrcholy jen na r*cos(45)."""
    gb = GB()
    pts = [(r, 0, 0), (-r, 0, 0), (0, r, 0), (0, -r, 0), (0, 0, r), (0, 0, -r)]
    pv = gb.view(b"".join(struct.pack("<3f", *p) for p in pts), target=34962)
    idx = [0, 2, 4, 4, 2, 1, 1, 2, 5, 5, 2, 0, 0, 4, 3, 4, 1, 3, 1, 5, 3, 5, 0, 3]
    iv = gb.view(struct.pack("<%dH" % len(idx), *idx), target=34963)
    gb.j["accessors"] += [{"bufferView": pv, "componentType": 5126, "count": 6, "type": "VEC3",
                           "min": [-r, -r, -r], "max": [r, r, r]},
                          {"bufferView": iv, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]
    gb.j["meshes"].append({"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]})
    gb.node(None, name="o", mesh=0, rotation=quat_axis((0, 1, 0), deg))
    if far_box:
        m = gb.box((100, 100, 100), (2000, 0, 0), name="kryt")
        if drop_minmax:
            a = gb.j["accessors"][gb.j["meshes"][m]["primitives"][0]["attributes"]["POSITION"]]
            del a["min"], a["max"]
        gb.node(None, name="x", mesh=m)
    return gb.glb()


def box_spec(lo, hi):
    return {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [0, 0, 1],
            "box": {"min": lo, "max": hi}, "look": "nat"}


class TestSpecBox(Base):
    def test_model_bigger_than_box_rejected(self):
        data = build_synthetic().glb()
        small = copy.deepcopy(SPEC)
        small["box"]["max"][1] -= 51                       # model presahuje o 51 mm
        with self.assertRaises(ValueError) as cm:
            v3d_glb.sanitize(data, small)
        self.assertIn("spec.box", str(cm.exception))
        ok = copy.deepcopy(SPEC)
        ok["box"]["max"][1] -= 49                          # 49 mm je jeste v toleranci
        v3d_glb.sanitize(data, ok)

    def test_box_bigger_than_model_only_warns(self):
        big = copy.deepcopy(SPEC)
        big["box"]["min"] = [v - 300 for v in big["box"]["min"]]
        out, rep = v3d_glb.sanitize_report(build_synthetic().glb(), big)
        self.assert_clean(out, big)
        self.assertEqual(len(rep["warnings"]), 1)
        self.assertIn("vetsi nez model", rep["warnings"][0])

    def test_exact_aabb_from_vertices(self):
        """Rohy min/max otoceneho meshe prestreli box o ~200 mm, skutecne
        vrcholy ne -> projde (AABB z vrcholu, ne z rohu)."""
        c = 500 * math.cos(math.radians(45))
        out, rep = v3d_glb.sanitize_report(octa_glb(), box_spec([-c, -500, -c], [c, 500, c]))
        self.assertLessEqual(max(abs(rep["model_aabb"]["max"][0] - c), abs(rep["model_aabb"]["min"][2] + c)), 0.01)
        self.assert_clean(out, box_spec([-c, -500, -c], [c, 500, c]))

    def test_quantized_positions(self):
        """KHR_mesh_quantization: POSITION jako normalizovany int16 (32767 = 1.0)
        a meritko uzlu 500 -> AABB z vrcholu musi dekvantovat."""
        gb = GB()
        q = 32767
        pts = [(q, 0, 0), (-q, 0, 0), (0, q, 0), (0, -q, 0), (0, 0, q), (0, 0, -q)]
        pv = gb.view(b"".join(struct.pack("<3h", *p) + b"\x00\x00" for p in pts), byteStride=8, target=34962)
        idx = [0, 2, 4, 4, 2, 1, 1, 2, 5, 5, 2, 0, 0, 4, 3, 4, 1, 3, 1, 5, 3, 5, 0, 3]
        iv = gb.view(struct.pack("<%dH" % len(idx), *idx), target=34963)
        gb.j["accessors"] += [{"bufferView": pv, "componentType": 5122, "normalized": True, "count": 6,
                               "type": "VEC3", "min": [-q, -q, -q], "max": [q, q, q]},
                              {"bufferView": iv, "componentType": 5123, "count": len(idx), "type": "SCALAR"}]
        gb.j["meshes"].append({"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]})
        gb.node(None, name="o", mesh=0, rotation=quat_axis((0, 1, 0), 45), scale=[500, 500, 500])
        gb.j["extensionsUsed"] = gb.j["extensionsRequired"] = ["KHR_mesh_quantization"]
        c = 500 * math.cos(math.radians(45))
        spec = box_spec([-c, -500, -c], [c, 500, c])
        out, rep = v3d_glb.sanitize_report(gb.glb(), spec)
        g, _ = self.assert_clean(out, spec)
        self.assertEqual(g["extensionsRequired"], ["KHR_mesh_quantization"])
        self.assertEqual(rep["bytes_zeroed"], 0)                 # 2 B vyplne na vrchol jsou nuly
        for k in (0, 2):
            self.assertAlmostEqual(rep["model_aabb"]["max"][k], c, delta=0.01)
            self.assertAlmostEqual(rep["model_aabb"]["min"][k], -c, delta=0.01)
        self.assertAlmostEqual(rep["model_aabb"]["max"][1], 500, delta=0.01)

    def test_extra_geometry_without_minmax_detected(self):
        """Vzdaleny mesh (obal/karoserie pod jinym jmenem) bez min/max se
        do AABB pocita taky -> presah = chyba."""
        c = 500 * math.cos(math.radians(45))
        for drop in (False, True):
            with self.subTest(bez_minmax=drop):
                with self.assertRaises(ValueError) as cm:
                    v3d_glb.sanitize(octa_glb(far_box=True, drop_minmax=drop), box_spec([-c, -500, -c], [c, 500, c]))
                self.assertIn("spec.box", str(cm.exception))


OUT_DIR = os.path.join(CE.OUT, "out")


class TestVandrOut(Base):
    """Vystupy Blender kroku out/<karta>.glb + spec z out/<karta>.json."""

    def test_out_cards(self):
        cards = sorted(p for p in glob.glob(os.path.join(OUT_DIR, "*.glb"))
                       if re.fullmatch(r"\d+\.glb", os.path.basename(p))
                       and os.path.exists(p[:-4] + ".json"))
        if not cards:
            self.skipTest("out/<karta>.glb neni k dispozici")
        for path in cards:
            name = os.path.basename(path)[:-4]
            with self.subTest(karta=name):
                data = read(path)
                with open(path[:-4] + ".json", encoding="utf-8") as fh:
                    spec = json.load(fh)["v3d"]
                before = mesh_instances(data)
                out, rep = v3d_glb.sanitize_report(data, spec)
                g, b = self.assert_clean(out, spec)
                compare_instances(self, before, mesh_instances(out), rep["mesh_map"])
                self.assertEqual(rep["bytes_zeroed"], 0)
                self.assertEqual(rep["warnings"], [])
                # AABB vsech instanci (vlastnim kodem) vs spec.box
                inst = mesh_instances(out)
                lo = [min(i[2][k] for i in inst) for k in range(3)]
                hi = [max(i[2][k + 3] for i in inst) for k in range(3)]
                bx = v3d_glb.validate_spec(spec)["box"]
                dev = max(max(abs(bx["min"][k] - lo[k]), abs(bx["max"][k] - hi[k])) for k in range(3))
                self.assertLessEqual(dev, 0.1, "spec.box vs model")
                self.assertEqual(v3d_glb.sanitize(out, spec), out)        # idempotence
                if name in ("4910", "4917"):
                    self.assert_three(out, before, rep["mesh_map"], "out_%s.glb" % name, spec)


if __name__ == "__main__":
    unittest.main(verbosity=2)
