#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3d_glb.py - serverova pojistka zakaznickeho GLB 3D nabidky (kontrakt v3d v1).

Jen standardni knihovna Pythonu (bezi i v /opt/konfigurator/api/venv/bin/python).

Zapojeni (api/scene_offers.py save_offer_model_bytes, OBE vetve - Vandr i nativni):

    import v3d_glb
    try:
        raw = v3d_glb.sanitize(raw, spec)      # spec = dict v3d v1, nebo None
    except ValueError as e:                    # V3DError je podtrida ValueError
        return "3D model neprosel kontrolou: %s" % e   # model NEVZNIKNE

CO POJISTKA NENI (cist pred zapojenim):
  Strazce vstupu (krok 5) je jen SIT na zbytky se starymi jmeny. Vyrazeni
  loga, obalu (pravidlo 60 %), karoserie, podlahy a pomucek je POVINNOST
  Blender kroku (Vandr vetev) a exportu (nativni vetev, bot8). Pojistka
  geometrii neposuzuje - prejmenovane logo nebo karoserie pod jinym jmenem
  projde. Jedina geometricka kontrola je hruba: kdyz existuje spec, model
  nesmi presahovat spec.box o vic nez 50 mm (jinak ValueError). Spec.box ale
  dodava ten samy build/export, takze to chyti jen nesoulad, ne chybu v obou.

Co sanitize() dela, v tomhle poradi:
  1. read_glb + check_structure vstupu (indexy, rozsahy bufferView/accessor,
     zarovnani, strom uzlu bez cyklu). Rozbity vstup = ValueError.
  2. Odmitne (ValueError), co kontrakt nepotrebuje nebo co nejde bezpecne
     vycistit: skiny, obrazky/textury/samplery (nativni ani Vandr vystupy
     zadne nemaji - viz _REJECT_ARRAYS), sparse accessory, morph targety,
     buffery pres uri (externi soubor i data:), vic nez jeden buffer,
     nepovolena POVINNA rozsireni (Draco/meshopt - r128 prohlizec bez
     dekoderu by spadl).
  3. Zahodi kamery, glTF animace (pohyby jsou parametricke kroky ve spec)
     a nepovolena NEpovinna rozsireni (KHR_lights_punctual ...).
  4. validate_spec(spec) + kontrola pivotu, na ktere spec odkazuje: jmeno je
     ve vstupu jednoznacne, uzel je prazdny (bez meshe), ma jednotkovou
     rotaci, je ve scene a pod nim je aspon jeden mesh.
  5. Strazce vstupu (guard=True, jen sit - viz vyse): uzel, mesh nebo
     material jmenem logo / podlaha / fixarea / LegsBox / legshoverbox /
     *Dimension / karoserie (presna shoda po odstraneni "(Clone)",
     "(Instance)" a koncovych cisel), pod kterym lezi geometrie ->
     ValueError. Nic se tise nemaze. (Kontejner 'colliders' ve Vandr GLB
     obsahuje CELY regal a 'Popruh...podlaha...' je skutecny dil, proto
     presna shoda jmen, ne podretezec.)
  6. Strom: jen vychozi scena. collapse=True slouci uzly bez meshe, ktere
     nejsou pivot ani rodic pivotu, do matic potomku (T*R*S podle glTF,
     sloucene jen kdyz vysledna matice jde rozlozit na TRS - jinak by
     three.js zkreslil geometrii). Prazdne listy pryc. Skupina kusovniku
     g se bere z extras.g nebo ze jmena bomgrp_N a pri slucovani se
     propisuje dolu (nejblizsi predek s g zustava stejny).
  7. GC: neodkazovane uzly, meshe, materialy, accessory a bufferViews pryc.
     Atributy primitiv jen POSITION/NORMAL/TANGENT/TEXCOORD_n/COLOR_n
     (ostatni, vc. JOINTS/WEIGHTS a vlastnich _XYZ, se zahodi i s daty).
  8. Prestavba z WHITELISTU (_SCHEMA): kazdy objekt vystupu se sklada znovu
     jen z povolenych klicu glTF 2.0 (material vc. pbrMetallicRoughness a
     povolenych rozsireni, mesh, primitiva, accessor, bufferView, buffer,
     uzel, scena, asset). Neznamy klic se zahodi; povoleny klic s
     nepovolenou hodnotou (napr. alphaMode s textem, accessor typu MAT4)
     = ValueError.
  9. BIN: bajty bufferView, ktere nepokryva zadny ponechany accessor
     (s ohledem na byteStride, componentType, type a count), se VYNULUJI.
     BIN se prebali JEN kdyz se neco odstranilo/vynulovalo nebo kdyz v nem
     mimo bufferViews lezi nenulove bajty. Jinak zustane bajt po bajtu stejny.
 10. Jmena: uzly n<i> (i = index ve vystupu), pivoty odkazovane ve spec si
     ponechaji sve p-jmeno ze vstupu (spec se tedy nemusi prepisovat),
     material si ponecha jmeno jen kdyz uz na vstupu bylo m<cislo>, vse
     ostatni bez jmena. extras jen {g:int} na uzlech a scenes[0].extras.v3d
     (= normalizovany spec). asset jen {"version":"2.0"}.
 11. Kontroly vystupu: check_structure, final_check (vrstva 1: pozitivni
     whitelist klicu a hodnot podle mista; vrstva 2: kazdy klic a retezec
     z globalniho whitelistu + zakazany regex FORBIDDEN_RE; vrstva 3:
     pivoty a spec), check_bin (kazdy bajt BIN mimo prvky accessoru je 0),
     spec.box vs. skutecne AABB z vrcholu (presah > 50 mm = ValueError),
     zpetne nacteni zapsaneho GLB.

Verejne funkce: read_glb, write_glb, sanitize, sanitize_report,
validate_spec, spec_pivot_refs, embedded_spec, final_check, check_structure,
check_bin.

Druh boxu (Robert 2026-10-02; nepovinne, spec bez nej je platny a vystup beze zmeny):
  motions[].g      volitelne, vycet "left" | "right" | "bulkhead" (strana ve spolecne nabidce)
  motions[].sub    vycet "klt" | "multibox" | "eurobox" | "kufrik", JEN u k=box
                   (u jineho druhu ValueError); jina hodnota ValueError. Do GLB se dostane
                   jen vycet - zadny nazev komponenty ani volny text.

Nativni vetev: spec prijde uvnitr GLB (GLTFExporter zapise scene.userData.v3d
do scenes[0].extras.v3d) -> sanitize(raw, embedded_spec(raw)). Vandr vetev:
spec z geom.json Blender kroku -> sanitize(clean_glb, geom["v3d"]).
CLI: python3 v3d_glb.py vstup.glb vystup.glb [spec.json] [--no-collapse] [--no-guard]
"""

import json
import math
import re
import struct
import sys

__all__ = [
    "V3DError", "read_glb", "write_glb", "sanitize", "sanitize_report",
    "validate_spec", "spec_pivot_refs", "embedded_spec", "final_check", "check_structure",
    "check_bin", "FORBIDDEN_RE", "NAME_OK_RE", "ALLOWED_EXTENSIONS",
]


class V3DError(ValueError):
    """Hlasita chyba pojistky - zakaznicky model nesmi vzniknout."""


# ---------------------------------------------------------------------------
# Konstanty
# ---------------------------------------------------------------------------

_MAGIC = b"glTF"
_CT_JSON = 0x4E4F534A
_CT_BIN = 0x004E4942

# Zaverecna kontrola, DRUHA vrstva: zadny retezec v JSON tohle nesmi obsahovat.
FORBIDDEN_RE = re.compile(
    r"\d+x\d+x\d+|Clone|Noha|Nohy|Suplik|Police|Vysuv|Zamek|Zapadka|Doraz|pant|Kluz|"
    r"logo|collider|fixarea|LegsBox|dimension|vandr|bomgrp|sse_|Solid_|Object_|world|geometry_",
    re.IGNORECASE,
)
# Povolene tvary jmen (fullmatch).
NAME_OK_RE = re.compile(r"(?:n\d+|p\d+|m\d+)?")
_NODE_NAME_RE = re.compile(r"n\d{1,6}|p\d{1,4}")
_MAT_NAME_RE = re.compile(r"m\d{1,4}")
_P_RE = re.compile(r"p\d{1,4}")
_MID_RE = re.compile(r"m\d{1,4}")
_T_RE = re.compile(r"[0-9 ]{1,7}(?: mm)?")
# stejny vzor jako nabidka-online.html:2358 / path-traced-preview.js:261
_BOMGRP_RE = re.compile(r"bomgrp_(\d{1,6})(?:_\d+)*")
# Atributy primitiv, ktere smi zustat (JOINTS/WEIGHTS bez skinu nemaji smysl).
_ATTR_RE = re.compile(r"POSITION|NORMAL|TANGENT|TEXCOORD_\d|COLOR_\d")

# Strazce vstupu - presna shoda normalizovaneho jmena (viz _guard_norm).
_GUARD_RE = re.compile(
    r"logo|podlaha|fixarea(?:_?red)?|legsbox|legshoverbox|karoserie|"
    r"(?:top|bottom|side|front|back|left|right)?(?:drilling)?dimensions?",
    re.IGNORECASE,
)

# Rozsireni, ktera smi zustat: jen ta, ktera three r128 GLTFLoader opravdu
# cte (GLTFLoader.js r128: clearcoat, transmission, unlit, mesh_quantization).
# Ostatni (emissive_strength, ior, specular, sheen, volume ...) r128 ignoruje,
# takze by jen nesla data navic - zahazuji se. Texturova rozsireni
# (KHR_texture_transform, EXT_texture_webp) nemaji smysl, textury se odmitaji.
ALLOWED_EXTENSIONS = frozenset({
    "KHR_materials_clearcoat", "KHR_materials_transmission", "KHR_materials_unlit",
    "KHR_mesh_quantization",
})

# Co ve VSTUPU znamena ValueError (kontrakt to nepotrebuje). Overeno
# 2026-10-01: zadna fixtura (nativni nabidky dc568f56.../e43bf378..., Vandr
# katalog 4910/4918, vystupy Blender kroku out/build, out/*.glb) nema
# images/textures/samplers; nativni export (path-traced-preview.js
# exportSceneAsGlb) bezi po setTechnicalDrawingMode(false) s
# MeshStandardMaterial bez map.
_REJECT_ARRAYS = ("skins", "images", "textures", "samplers")
_REJECT_MSG = {
    "skins": "skiny (kostry) nejsou v zakaznickem modelu povolene",
    "images": "obrazky nejsou v zakaznickem modelu povolene (kontrakt v3d textury nepouziva)",
    "textures": "textury nejsou v zakaznickem modelu povolene (kontrakt v3d textury nepouziva)",
    "samplers": "samplery nejsou v zakaznickem modelu povolene (kontrakt v3d textury nepouziva)",
}

_ALPHA_MODES = ("OPAQUE", "MASK", "BLEND")
_ACC_TYPES_OUT = ("SCALAR", "VEC2", "VEC3", "VEC4")
_BV_TARGETS = (34962, 34963)
_MAX_INT = 2 ** 53
_BOX_TOL_MM = 50.0          # presah modelu pres spec.box, nad ktery je chyba

_COMP_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_COMP_FMT = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_COMP_NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}
_TYPE_COMPS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}

_GLTF_ARRAYS = (
    "accessors", "animations", "buffers", "bufferViews", "cameras", "images", "materials",
    "meshes", "nodes", "samplers", "scenes", "skins", "textures",
)

# ---------------------------------------------------------------------------
# WHITELIST vystupu: pro kazdy druh objektu povolene klice a tvar hodnoty.
# Pouziva ho prestavba (_rebuild) i final_check (_schema_errors).
#   "int"  nezaporne cele cislo     "num"  konecne cislo     "bool"
#   "g"    skupina kusovniku        "ints" seznam indexu     "numlist" 1..16 cisel
#   ("nums", n) presne n cisel      ("enum", hodnoty)        ("re", regex)
#   ("obj", druh) vnoreny objekt    ("list", druh) seznam objektu
#   ("map", regex_klice) objekt {klic: index}    ("strs", mnozina) seznam retezcu
#   "v3d"  spec (validate_spec, kanonicky tvar)
# name/extras prestavba NIKDY nekopiruje (_REBUILD_SKIP) - nastavuje je
# sanitize sam; ve whitelistu jsou jen kvuli final_check.
# ---------------------------------------------------------------------------

_SCHEMA = {
    "gltf": {
        "asset": ("obj", "asset"), "scene": "int", "scenes": ("list", "scene"),
        "nodes": ("list", "node"), "meshes": ("list", "mesh"), "materials": ("list", "material"),
        "accessors": ("list", "accessor"), "bufferViews": ("list", "bufferView"),
        "buffers": ("list", "buffer"),
        "extensionsUsed": ("strs", ALLOWED_EXTENSIONS), "extensionsRequired": ("strs", ALLOWED_EXTENSIONS),
    },
    "asset": {"version": ("enum", ("2.0",))},
    "scene": {"nodes": "ints", "extras": ("obj", "scene_extras")},
    "scene_extras": {"v3d": "v3d"},
    "node": {
        "name": ("re", _NODE_NAME_RE), "children": "ints", "mesh": "int",
        "matrix": ("nums", 16), "translation": ("nums", 3), "rotation": ("nums", 4),
        "scale": ("nums", 3), "extras": ("obj", "node_extras"),
    },
    "node_extras": {"g": "g"},
    "mesh": {"primitives": ("list", "primitive")},
    "primitive": {
        "attributes": ("map", _ATTR_RE), "indices": "int", "material": "int",
        "mode": ("enum", (0, 1, 2, 3, 4, 5, 6)),
    },
    "material": {
        "name": ("re", _MAT_NAME_RE), "pbrMetallicRoughness": ("obj", "pbr"),
        "emissiveFactor": ("nums", 3), "alphaMode": ("enum", _ALPHA_MODES),
        "alphaCutoff": "num", "doubleSided": "bool", "extensions": ("obj", "material_ext"),
    },
    "pbr": {"baseColorFactor": ("nums", 4), "metallicFactor": "num", "roughnessFactor": "num"},
    "material_ext": {
        "KHR_materials_clearcoat": ("obj", "KHR_materials_clearcoat"),
        "KHR_materials_transmission": ("obj", "KHR_materials_transmission"),
        "KHR_materials_unlit": ("obj", "KHR_materials_unlit"),
    },
    "KHR_materials_clearcoat": {"clearcoatFactor": "num", "clearcoatRoughnessFactor": "num"},
    "KHR_materials_transmission": {"transmissionFactor": "num"},
    "KHR_materials_unlit": {},
    "accessor": {
        "bufferView": "int", "byteOffset": "int",
        "componentType": ("enum", tuple(sorted(_COMP_SIZE))), "normalized": "bool",
        "count": "int", "type": ("enum", _ACC_TYPES_OUT), "min": "numlist", "max": "numlist",
    },
    "bufferView": {
        "buffer": "int", "byteOffset": "int", "byteLength": "int", "byteStride": "int",
        "target": ("enum", _BV_TARGETS),
    },
    "buffer": {"byteLength": "int"},
}
_REQUIRED = {
    "gltf": ("asset",), "asset": ("version",), "scene_extras": ("v3d",), "node": ("name",),
    "node_extras": ("g",), "mesh": ("primitives",), "primitive": ("attributes",),
    "accessor": ("componentType", "count", "type"), "bufferView": ("buffer", "byteLength"),
    "buffer": ("byteLength",),
}
_REBUILD_SKIP = frozenset({"name", "extras"})
_TOP_KEYS_OUT = tuple(_SCHEMA["gltf"])

# Kontrakt v3d v1
_KINDS = ("drawer", "door", "floor_door", "box", "slide")
# motions[].sub (nepovinne, JEN u k=box; Robert 2026-10-02: Eurobox / KLT box / Multibox se ve
# spodni liste cipu nesmi jmenovat vsechny "Box N"): vycet, zadny volny text. kufrik = rezerva
# (ve Vandr datech je Kufrik zatim vysuv bez boxu).
_SUBS = ("klt", "multibox", "eurobox", "kufrik")
# strana ve spolecne nabidce (levá / pravá / přepážka; bot10 2026-10-06): volitelne motions[].g - jen vycet, viewer podle nej radi tlacitka
_SIDES = ("left", "right", "bulkhead")
_LOOKS = ("vd", "nat")
_OPS = ("T", "R")
_V3D_KEYS = frozenset({"v", "u", "up", "front", "box", "min", "max", "look", "dims", "motions",
                       "a", "b", "o", "t", "l", "p", "m", "id", "k", "n", "steps", "op", "ax", "ms", "pick", "sub", "g",
                       "mbx", "e", "s", "sk"})

# Globalni whitelist (druha vrstva final_check): kazdy klic a kazdy retezec
# kdekoli v JSON vystupu musi byt odsud.
_ALL_KEYS = frozenset(k for s in _SCHEMA.values() for k in s) | _V3D_KEYS
_STR_OK = frozenset({"2.0", "mm"} | set(_LOOKS) | set(_OPS) | set(_KINDS) | set(_SUBS) | set(_SIDES) | set(_ALPHA_MODES)
                    | set(_ACC_TYPES_OUT) | ALLOWED_EXTENSIONS)
_STR_OK_RE = re.compile(r"n\d{1,6}|p\d{1,4}|m\d{1,4}|b\d{1,4}|[0-9 ]{1,7}(?: mm)?")

_LIM_MM = 100000.0         # 100 m - cokoli vetsiho je chyba
_LIM_T_MM = 5000.0         # posun v jednom kroku
_LIM_R_DEG = 360.0
_MAX_MS = 10000
_MAX_DIMS = 500
_MAX_MOTIONS = 200
_MAX_MBX = 400
_LIM_MBX_MM = 3000.0       # nejvetsi rozmer jednoho multiboxu (skutecne 395,5 mm)
_BID_RE = re.compile(r"b\d{1,4}")
_MAX_STEPS = 8
_MAX_PICK = 32
_MAX_N = 999
_MAX_G = 1000000
_MAX_SPEC_BYTES = 200000
_UNIT_TOL = 1e-3
_MAX_DEPTH = 256
_DECOMP_TOL = 1e-6

_INV = bytes(255 - i for i in range(256))      # bytes.translate: maska 0x00 <-> 0xFF


# ---------------------------------------------------------------------------
# GLB cteni / zapis
# ---------------------------------------------------------------------------

def _reject_const(name):
    raise V3DError("GLB: JSON obsahuje %s (NaN/Infinity nejsou povolene)" % name)


def read_glb(data):
    """bytes -> (gltf_json: dict, bin: bytes|None).

    bin je obsah BIN chunku tak, jak je ulozen (vc. pripadneho zarovnani
    na 4 B). Nezname chunky se ignoruji (a write_glb je nezapise)."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise V3DError("GLB: ocekavam bajty")
    data = bytes(data)
    if len(data) < 20:
        raise V3DError("GLB: soubor je prilis kratky")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != _MAGIC:
        raise V3DError("GLB: chybi hlavicka glTF")
    if version != 2:
        raise V3DError("GLB: podporovana je jen verze 2 (je %d)" % version)
    if length != len(data):
        raise V3DError("GLB: delka v hlavicce (%d) nesedi se skutecnou (%d)" % (length, len(data)))
    off = 12
    idx = 0
    gltf = None
    bin_chunk = None
    while off < length:
        if off + 8 > length:
            raise V3DError("GLB: useknuta hlavicka chunku")
        clen, ctype = struct.unpack_from("<II", data, off)
        start = off + 8
        end = start + clen
        if end > length:
            raise V3DError("GLB: chunk presahuje konec souboru")
        chunk = data[start:end]
        if idx == 0:
            if ctype != _CT_JSON:
                raise V3DError("GLB: prvni chunk neni JSON")
            try:
                text = chunk.rstrip(b" \t\r\n\x00").decode("utf-8")
                gltf = json.loads(text, parse_constant=_reject_const)
            except V3DError:
                raise
            except (UnicodeDecodeError, ValueError) as e:
                raise V3DError("GLB: JSON chunk nejde precist (%s)" % e)
            if not isinstance(gltf, dict):
                raise V3DError("GLB: JSON chunk neni objekt")
        elif ctype == _CT_BIN:
            if idx != 1:
                raise V3DError("GLB: BIN chunk musi byt druhy a jen jeden")
            bin_chunk = chunk
        off = end
        idx += 1
    if gltf is None:
        raise V3DError("GLB: chybi JSON chunk")
    return gltf, bin_chunk


def write_glb(gltf, bin_data=None):
    """(gltf_json, bin|None) -> bytes. JSON doplnen mezerami a BIN nulami na
    nasobek 4 B, delky chunku i celkova delka odpovidaji."""
    try:
        js = json.dumps(gltf, separators=(",", ":"), ensure_ascii=True,
                        allow_nan=False).encode("ascii")
    except (TypeError, ValueError) as e:
        raise V3DError("GLB: JSON nejde zapsat (%s)" % e)
    js += b" " * (-len(js) % 4)
    parts = [struct.pack("<II", len(js), _CT_JSON), js]
    if bin_data is not None:
        b = bytes(bin_data)
        bufs = gltf.get("buffers") or []
        if bufs and isinstance(bufs[0], dict) and "uri" not in bufs[0]:
            bl = bufs[0].get("byteLength")
            if type(bl) is not int or bl > len(b):
                raise V3DError("GLB: buffers[0].byteLength nesedi s delkou BIN")
        b += b"\x00" * (-len(b) % 4)
        parts += [struct.pack("<II", len(b), _CT_BIN), b]
    body = b"".join(parts)
    return struct.pack("<4sII", _MAGIC, 2, 12 + len(body)) + body


# ---------------------------------------------------------------------------
# Matice 4x4 (glTF = column-major, 16 cisel)
# ---------------------------------------------------------------------------

_IDENT = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)


def _mat_mul(a, b):
    out = [0.0] * 16
    for c in range(4):
        b0, b1, b2, b3 = b[c * 4], b[c * 4 + 1], b[c * 4 + 2], b[c * 4 + 3]
        for r in range(4):
            out[c * 4 + r] = a[r] * b0 + a[4 + r] * b1 + a[8 + r] * b2 + a[12 + r] * b3
    return out


def _trs_matrix(t, q, s):
    x, y, z, w = (float(v) for v in q)
    sx, sy, sz = (float(v) for v in s)
    x2, y2, z2 = x + x, y + y, z + z
    xx, xy, xz = x * x2, x * y2, x * z2
    yy, yz, zz = y * y2, y * z2, z * z2
    wx, wy, wz = w * x2, w * y2, w * z2
    return [
        (1 - (yy + zz)) * sx, (xy + wz) * sx, (xz - wy) * sx, 0.0,
        (xy - wz) * sy, (1 - (xx + zz)) * sy, (yz + wx) * sy, 0.0,
        (xz + wy) * sz, (yz - wx) * sz, (1 - (xx + yy)) * sz, 0.0,
        float(t[0]), float(t[1]), float(t[2]), 1.0,
    ]


def _local_matrix(node):
    if "matrix" in node:
        return [float(v) for v in node["matrix"]]
    return _trs_matrix(node.get("translation", (0, 0, 0)),
                       node.get("rotation", (0, 0, 0, 1)),
                       node.get("scale", (1, 1, 1)))


def _is_identity(m, tol=1e-12):
    return all(abs(m[i] - _IDENT[i]) <= tol for i in range(16))


def _decomposable(m, tol=_DECOMP_TOL):
    """Afinni matice bez zkosu (sloupce 3x3 navzajem kolme) - jen takovou
    glTF dovoluje a jen takovou three.js (decompose na TRS) neprekrouti."""
    if abs(m[3]) > 1e-9 or abs(m[7]) > 1e-9 or abs(m[11]) > 1e-9 or abs(m[15] - 1.0) > 1e-9:
        return False
    cols = (m[0:3], m[4:7], m[8:11])
    lens = [math.sqrt(c[0] * c[0] + c[1] * c[1] + c[2] * c[2]) for c in cols]
    if min(lens) < 1e-12:
        return False
    for i, j in ((0, 1), (0, 2), (1, 2)):
        d = cols[i][0] * cols[j][0] + cols[i][1] * cols[j][1] + cols[i][2] * cols[j][2]
        if abs(d) > tol * lens[i] * lens[j]:
            return False
    return True


def _rotation_is_identity(node):
    """Pivot: jednotkova rotace (meritko kladne, posun libovolny)."""
    if "matrix" in node:
        m = [float(v) for v in node["matrix"]]
        if abs(m[3]) + abs(m[7]) + abs(m[11]) > 1e-9 or abs(m[15] - 1.0) > 1e-9:
            return False
        for k, c in enumerate((m[0:3], m[4:7], m[8:11])):
            ln = math.sqrt(c[0] * c[0] + c[1] * c[1] + c[2] * c[2])
            if ln < 1e-12:
                return False
            for r in range(3):
                if abs(c[r] / ln - (1.0 if r == k else 0.0)) > 1e-6:
                    return False
        return True
    q = node.get("rotation", (0, 0, 0, 1))
    if abs(q[0]) + abs(q[1]) + abs(q[2]) > 1e-6 or abs(abs(q[3]) - 1.0) > 1e-6:
        return False
    return all(v > 0 for v in node.get("scale", (1, 1, 1)))


def _clean_num(v):
    v = float(v)
    if v == 0.0:
        return 0.0          # i -0.0
    return v


# ---------------------------------------------------------------------------
# Kontrakt v3d v1
# ---------------------------------------------------------------------------

def _isnum(x):
    return type(x) in (int, float) and math.isfinite(x)


def _out_num(x, nd):
    r = round(float(x), nd)
    if r == 0.0:
        return 0
    if r.is_integer() and abs(r) < 2 ** 53:
        return int(r)
    return r


def _keys(d, req, opt, where):
    if not isinstance(d, dict):
        raise V3DError("%s: ocekavam objekt" % where)
    for k in d:
        if not isinstance(k, str):
            raise V3DError("%s: klic neni retezec" % where)
    extra = [k for k in d if k not in req and k not in opt]
    if extra:
        raise V3DError("%s: nepovolene klice %s" % (where, sorted(extra)[:5]))
    missing = [k for k in req if k not in d]
    if missing:
        raise V3DError("%s: chybi klice %s" % (where, missing))


def _vec3(v, where, lim=_LIM_MM):
    if not isinstance(v, list) or len(v) != 3 or not all(_isnum(x) for x in v):
        raise V3DError("%s: ocekavam [x,y,z] ze 3 konecnych cisel" % where)
    if any(abs(x) > lim for x in v):
        raise V3DError("%s: hodnota mimo rozsah +-%g" % (where, lim))
    return [float(x) for x in v]


def _unit3(v, where):
    v = _vec3(v, where, 1.0 + _UNIT_TOL)
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if abs(n - 1.0) > _UNIT_TOL:
        raise V3DError("%s: neni jednotkovy vektor (|v|=%.6f)" % (where, n))
    return v


def _int_in(x, lo, hi, where):
    if type(x) is not int or not (lo <= x <= hi):
        raise V3DError("%s: ocekavam cele cislo %d..%d" % (where, lo, hi))
    return x


def _pref(x, pivots, where):
    if not isinstance(x, str) or not _P_RE.fullmatch(x):
        raise V3DError("%s: odkaz na pivot musi byt p<cislo>" % where)
    if pivots is not None and x not in pivots:
        raise V3DError("%s: pivot %s v modelu neexistuje" % (where, x))
    return x


def validate_spec(spec, pivots=None):
    """Striktni kontrola kontraktu v3d v1. Vraci normalizovanou kopii (jen
    povolene klice, kanonicke poradi, cisla zaokrouhlena), jinak ValueError.

    pivots: mnozina p-jmen dostupnych v modelu (None = existenci neoverovat)."""
    if pivots is not None:
        pivots = set(pivots)
    _keys(spec, ("v", "u", "up", "front", "box", "look"), ("dims", "motions", "mbx"), "v3d")
    if type(spec["v"]) is not int or spec["v"] != 1:
        raise V3DError("v3d.v: podporovana je jen verze 1")
    if spec["u"] != "mm":
        raise V3DError("v3d.u: jednotky musi byt 'mm'")
    up = _vec3(spec["up"], "v3d.up")
    if up != [0.0, 1.0, 0.0]:
        raise V3DError("v3d.up: musi byt [0,1,0]")
    front = _unit3(spec["front"], "v3d.front")
    if abs(front[1]) > 1e-9:
        raise V3DError("v3d.front: slozka Y musi byt 0")
    _keys(spec["box"], ("min", "max"), (), "v3d.box")
    bmin = _vec3(spec["box"]["min"], "v3d.box.min")
    bmax = _vec3(spec["box"]["max"], "v3d.box.max")
    if any(bmin[i] > bmax[i] for i in range(3)):
        raise V3DError("v3d.box: min > max")
    if spec["look"] not in _LOOKS:
        raise V3DError("v3d.look: povoleno %s" % (_LOOKS,))

    dims_in = spec.get("dims", [])
    if not isinstance(dims_in, list) or len(dims_in) > _MAX_DIMS:
        raise V3DError("v3d.dims: ocekavam seznam (max %d)" % _MAX_DIMS)
    dims = []
    for i, d in enumerate(dims_in):
        w = "v3d.dims[%d]" % i
        _keys(d, ("a", "b", "o", "t", "l"), ("p", "m"), w)
        a = _vec3(d["a"], w + ".a")
        b = _vec3(d["b"], w + ".b")
        o = _vec3(d["o"], w + ".o")
        t = d["t"]
        if not isinstance(t, str) or not _T_RE.fullmatch(t) or not any(ch.isdigit() for ch in t):
            raise V3DError("%s.t: povolen jen tvar ^[0-9 ]{1,7}( mm)?$ s aspon jednou cislici" % w)
        lv = d["l"]
        if type(lv) is not int or lv not in (1, 2):
            raise V3DError("%s.l: povoleno 1 nebo 2" % w)
        p = d.get("p")
        if p is not None:
            p = _pref(p, pivots, w + ".p")
        dim = {"a": [_out_num(x, 3) for x in a], "b": [_out_num(x, 3) for x in b],
               "o": [_out_num(x, 3) for x in o], "t": t, "l": lv, "p": p}
        if "m" in d:          # poloha popisku na care koty (generator stolu, bot8): 0 = u bodu a, 1 = u bodu b, bez "m" = uprostred (viewer clampuje 0-1)
            if not (_isnum(d["m"]) and 0 <= d["m"] <= 1):
                raise V3DError("%s.m: povoleno konecne cislo 0-1 (poloha popisku na care koty)" % w)
            dim["m"] = _out_num(d["m"], 3)
        dims.append(dim)

    mot_in = spec.get("motions", [])
    if not isinstance(mot_in, list) or len(mot_in) > _MAX_MOTIONS:
        raise V3DError("v3d.motions: ocekavam seznam (max %d)" % _MAX_MOTIONS)
    motions = []
    seen_ids = set()
    for i, m in enumerate(mot_in):
        w = "v3d.motions[%d]" % i
        _keys(m, ("id", "k", "n", "steps"), ("pick", "sub", "g"), w)
        mid = m["id"]
        if not isinstance(mid, str) or not _MID_RE.fullmatch(mid):
            raise V3DError("%s.id: povolen jen tvar m<cislo>" % w)
        if mid in seen_ids:
            raise V3DError("%s.id: duplicitni %s" % (w, mid))
        seen_ids.add(mid)
        if m["k"] not in _KINDS:
            raise V3DError("%s.k: povoleno %s" % (w, _KINDS))
        sub = None
        if "sub" in m:
            sub = m["sub"]
            if type(sub) is not str or sub not in _SUBS:
                raise V3DError("%s.sub: povoleno %s" % (w, _SUBS))
            if m["k"] != "box":
                raise V3DError("%s.sub: povoleno jen u k=box" % w)
        g = None
        if "g" in m:
            g = m["g"]
            if type(g) is not str or g not in _SIDES:
                raise V3DError("%s.g: povoleno %s" % (w, _SIDES))
        n = _int_in(m["n"], 1, _MAX_N, w + ".n")
        steps_in = m["steps"]
        if not isinstance(steps_in, list) or not (1 <= len(steps_in) <= _MAX_STEPS):
            raise V3DError("%s.steps: 1..%d kroku" % (w, _MAX_STEPS))
        steps = []
        for j, s in enumerate(steps_in):
            ws = "%s.steps[%d]" % (w, j)
            _keys(s, ("p", "op", "ax", "v", "ms"), (), ws)
            p = _pref(s["p"], pivots, ws + ".p")
            if s["op"] not in _OPS:
                raise V3DError("%s.op: povoleno T nebo R" % ws)
            ax = _unit3(s["ax"], ws + ".ax")
            v = s["v"]
            lim = _LIM_T_MM if s["op"] == "T" else _LIM_R_DEG
            if not _isnum(v) or abs(v) > lim:
                raise V3DError("%s.v: cislo v rozsahu +-%g" % (ws, lim))
            ms = _int_in(s["ms"], 0, _MAX_MS, ws + ".ms")
            steps.append({"p": p, "op": s["op"], "ax": [_out_num(x, 6) for x in ax],
                          "v": _out_num(v, 3), "ms": ms})
        pick_in = m.get("pick", [])
        if not isinstance(pick_in, list) or len(pick_in) > _MAX_PICK:
            raise V3DError("%s.pick: seznam (max %d)" % (w, _MAX_PICK))
        pick = []
        for j, p in enumerate(pick_in):
            p = _pref(p, pivots, "%s.pick[%d]" % (w, j))
            if p not in pick:
                pick.append(p)
        mo = {"id": mid, "k": m["k"]}
        if sub is not None:
            mo["sub"] = sub
        if g is not None:
            mo["g"] = g
        mo.update({"n": n, "steps": steps, "pick": pick})
        motions.append(mo)

    # multiboxy (nepovinne; bot8, 2026-10-07; Robert: pricky do Multiboxu v nabidce): poloha boxu (svetovy AABB zavreneho stavu, mm), strana konce s vykrojem e = +1 / -1
    # (MIN / MAX strana delsiho vodorovneho rozmeru), pivot p (box jede s vysuvem) a poradi n; jen cisla, cele id b<cislo>, zadna jmena komponent
    mbx_in = spec.get("mbx", [])
    if not isinstance(mbx_in, list) or len(mbx_in) > _MAX_MBX:
        raise V3DError("v3d.mbx: ocekavam seznam (max %d)" % _MAX_MBX)
    mbx = []
    seen_b = set()
    for i, b in enumerate(mbx_in):
        w = "v3d.mbx[%d]" % i
        _keys(b, ("id", "min", "max", "e"), ("p", "g", "n", "s", "sk"), w)
        bid = b["id"]
        if not isinstance(bid, str) or not _BID_RE.fullmatch(bid):
            raise V3DError("%s.id: povolen jen tvar b<cislo>" % w)
        if bid in seen_b:
            raise V3DError("%s.id: duplicitni %s" % (w, bid))
        seen_b.add(bid)
        b_min = _vec3(b["min"], w + ".min")
        b_max = _vec3(b["max"], w + ".max")
        if any(b_min[j] > b_max[j] or b_max[j] - b_min[j] > _LIM_MBX_MM for j in range(3)):
            raise V3DError("%s: min > max nebo rozmer vetsi nez %g mm" % (w, _LIM_MBX_MM))
        e = b["e"]
        if type(e) is not int or e not in (-1, 1):
            raise V3DError("%s.e: povoleno -1 nebo 1" % w)
        bp = b.get("p")
        if bp is not None:
            bp = _pref(bp, pivots, w + ".p")
        bo = {"id": bid, "min": [_out_num(x, 1) for x in b_min], "max": [_out_num(x, 1) for x in b_max], "e": e, "p": bp}
        if "g" in b:
            bg = b["g"]
            if type(bg) is not str or bg not in _SIDES:
                raise V3DError("%s.g: povoleno %s" % (w, _SIDES))
            bo["g"] = bg
        if "n" in b:
            bo["n"] = _int_in(b["n"], 1, _MAX_N, w + ".n")
        if "s" in b:          # skupina = police / suplik s multiboxy (cislo skupiny; sety pricek se nabizeji pro celou skupinu)
            bo["s"] = _int_in(b["s"], 1, _MAX_N, w + ".s")
        if "sk" in b:         # druh skupiny jako cislo (jmena komponent do GLB nesmi): 1 = police, 2 = vysuv (suplik) s multiboxy, 3 = samostatne boxy, 4 = ocelove suplikove podnosy
            bo["sk"] = _int_in(b["sk"], 1, 4, w + ".sk")
        mbx.append(bo)

    out = {
        "v": 1, "u": "mm", "up": [0, 1, 0],
        "front": [_out_num(x, 6) for x in front],
        "box": {"min": [_out_num(x, 3) for x in bmin], "max": [_out_num(x, 3) for x in bmax]},
        "look": spec["look"], "dims": dims, "motions": motions,
    }
    if mbx:
        out["mbx"] = mbx
    if len(json.dumps(out, separators=(",", ":"))) > _MAX_SPEC_BYTES:
        raise V3DError("v3d: spec je prilis velky")
    return out


def embedded_spec(glb_bytes):
    """Spec, ktery uz lezi ve VSTUPNIM GLB v scenes[0].extras.v3d (nativni
    vetev: GLTFExporter zapise scene.userData.v3d). Vraci surovy dict nebo
    None - NEvaliduje, to udela az sanitize(glb, spec)."""
    g, _ = read_glb(glb_bytes)
    scenes = g.get("scenes")
    if not isinstance(scenes, list) or not scenes or not isinstance(scenes[0], dict):
        return None
    ex = scenes[0].get("extras")
    if isinstance(ex, dict) and "v3d" in ex:
        return ex["v3d"]
    return None


def spec_pivot_refs(spec):
    """Mnozina p-jmen, na ktera se (validovany) spec odkazuje."""
    refs = set()
    for d in spec.get("dims", []):
        if d.get("p"):
            refs.add(d["p"])
    for m in spec.get("motions", []):
        for s in m.get("steps", []):
            refs.add(s["p"])
        for p in m.get("pick", []):
            refs.add(p)
    for b in spec.get("mbx", []):
        if b.get("p"):
            refs.add(b["p"])
    return refs


# ---------------------------------------------------------------------------
# Kontrola struktury glTF (indexy, rozsahy, strom)
# ---------------------------------------------------------------------------

def _elem_size(acc_type, csize):
    if acc_type.startswith("MAT"):
        n = int(acc_type[3])
        col = n * csize
        col += -col % 4
        return n * col
    return _TYPE_COMPS[acc_type] * csize


def _tex_infos(obj):
    """Vsechny texture-info objekty (klic konci na 'Texture' a ma 'index')."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, dict) and isinstance(k, str) and k.endswith("Texture") and "index" in v:
                    out.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return out


def check_structure(g, bin_data, where="glTF"):
    """Zkontroluje platnost indexu a rozsahu (aby GLB slo nacist GLTFLoaderem).
    bin_data = obsah BIN chunku (nebo None). Vraci mapu rodicu {uzel: rodic}.
    Obrazky/textury/samplery tu neresi - sanitize je odmita cele."""

    def err(msg):
        raise V3DError("%s: %s" % (where, msg))

    def idx_ok(v, arr):
        return type(v) is int and 0 <= v < len(g.get(arr) or [])

    if not isinstance(g.get("asset"), dict) or g["asset"].get("version") != "2.0":
        err("asset.version musi byt '2.0'")
    for a in _GLTF_ARRAYS:
        if a in g:
            if not isinstance(g[a], list) or not all(isinstance(x, dict) for x in g[a]):
                err("%s musi byt seznam objektu" % a)

    def nums(v, n):
        return isinstance(v, list) and len(v) == n and all(_isnum(x) for x in v)

    # buffers
    bufs = g.get("buffers") or []
    for i, b in enumerate(bufs):
        if type(b.get("byteLength")) is not int or b["byteLength"] < 1:
            err("buffers[%d].byteLength" % i)
        if i == 0 and "uri" not in b:
            if bin_data is None or len(bin_data) < b["byteLength"]:
                err("buffers[0] je delsi nez BIN chunk")
    # bufferViews
    views = g.get("bufferViews") or []
    for i, v in enumerate(views):
        if not idx_ok(v.get("buffer"), "buffers"):
            err("bufferViews[%d].buffer" % i)
        off = v.get("byteOffset", 0)
        ln = v.get("byteLength")
        if type(off) is not int or off < 0 or type(ln) is not int or ln < 1:
            err("bufferViews[%d] offset/delka" % i)
        if off + ln > bufs[v["buffer"]]["byteLength"]:
            err("bufferViews[%d] presahuje buffer" % i)
        if "byteStride" in v:
            st = v["byteStride"]
            if type(st) is not int or not (4 <= st <= 252) or st % 4:
                err("bufferViews[%d].byteStride" % i)
    # accessors
    for i, a in enumerate(g.get("accessors") or []):
        ct = a.get("componentType")
        at = a.get("type")
        cnt = a.get("count")
        if ct not in _COMP_SIZE or at not in _TYPE_COMPS or type(cnt) is not int or cnt < 1:
            err("accessors[%d] typ/pocet" % i)
        csize = _COMP_SIZE[ct]
        esize = _elem_size(at, csize)
        for mm in ("min", "max"):
            if mm in a and not nums(a[mm], _TYPE_COMPS[at]):
                err("accessors[%d].%s" % (i, mm))
        boff = a.get("byteOffset", 0)
        if type(boff) is not int or boff < 0:
            err("accessors[%d].byteOffset" % i)
        if "bufferView" in a:
            if not idx_ok(a["bufferView"], "bufferViews"):
                err("accessors[%d].bufferView" % i)
            v = views[a["bufferView"]]
            stride = v.get("byteStride", esize)
            if stride < esize:
                err("accessors[%d] prvek je delsi nez byteStride" % i)
            if boff + stride * (cnt - 1) + esize > v["byteLength"]:
                err("accessors[%d] presahuje bufferView" % i)
            if boff % csize or (v.get("byteOffset", 0) + boff) % csize:
                err("accessors[%d] spatne zarovnani" % i)
        elif boff:
            err("accessors[%d].byteOffset bez bufferView" % i)
        sp = a.get("sparse")
        if sp is not None:
            if not isinstance(sp, dict) or type(sp.get("count")) is not int or not (1 <= sp["count"] <= cnt):
                err("accessors[%d].sparse.count" % i)
            si, sv = sp.get("indices"), sp.get("values")
            if not isinstance(si, dict) or not isinstance(sv, dict):
                err("accessors[%d].sparse" % i)
            if not idx_ok(si.get("bufferView"), "bufferViews") or si.get("componentType") not in (5121, 5123, 5125):
                err("accessors[%d].sparse.indices" % i)
            if not idx_ok(sv.get("bufferView"), "bufferViews"):
                err("accessors[%d].sparse.values" % i)
            if si.get("byteOffset", 0) + sp["count"] * _COMP_SIZE[si["componentType"]] > views[si["bufferView"]]["byteLength"]:
                err("accessors[%d].sparse.indices presahuje" % i)
            if sv.get("byteOffset", 0) + sp["count"] * esize > views[sv["bufferView"]]["byteLength"]:
                err("accessors[%d].sparse.values presahuje" % i)
    for i, m in enumerate(g.get("materials") or []):
        for ti in _tex_infos(m):
            if not idx_ok(ti.get("index"), "textures"):
                err("materials[%d] odkaz na texturu" % i)
    # meshes
    for i, m in enumerate(g.get("meshes") or []):
        prims = m.get("primitives")
        if not isinstance(prims, list) or not prims:
            err("meshes[%d] bez primitiv" % i)
        for j, p in enumerate(prims):
            if not isinstance(p, dict):
                err("meshes[%d].primitives[%d]" % (i, j))
            attrs = p.get("attributes")
            if not isinstance(attrs, dict) or not attrs or not all(idx_ok(v, "accessors") for v in attrs.values()):
                err("meshes[%d].primitives[%d].attributes" % (i, j))
            if "indices" in p and not idx_ok(p["indices"], "accessors"):
                err("meshes[%d].primitives[%d].indices" % (i, j))
            if "material" in p and not idx_ok(p["material"], "materials"):
                err("meshes[%d].primitives[%d].material" % (i, j))
            if "mode" in p and (type(p["mode"]) is not int or not 0 <= p["mode"] <= 6):
                err("meshes[%d].primitives[%d].mode" % (i, j))
            tgs = p.get("targets", []) or []
            if not isinstance(tgs, list):
                err("meshes[%d].primitives[%d].targets" % (i, j))
            for tg in tgs:
                if not isinstance(tg, dict) or not all(idx_ok(v, "accessors") for v in tg.values()):
                    err("meshes[%d].primitives[%d].targets" % (i, j))
    # nodes - strom
    nodes = g.get("nodes") or []
    parent = {}
    for i, n in enumerate(nodes):
        ch = n.get("children", [])
        if not isinstance(ch, list):
            err("nodes[%d].children" % i)
        for c in ch:
            if not idx_ok(c, "nodes") or c == i:
                err("nodes[%d].children obsahuje neplatny index" % i)
            if c in parent:
                err("uzel %d ma vic rodicu" % c)
            parent[c] = i
        for k, arr in (("mesh", "meshes"), ("camera", "cameras"), ("skin", "skins")):
            if k in n and not idx_ok(n[k], arr):
                err("nodes[%d].%s" % (i, k))
        if "matrix" in n:
            if not nums(n["matrix"], 16):
                err("nodes[%d].matrix" % i)
            if any(k in n for k in ("translation", "rotation", "scale")):
                err("nodes[%d] ma matrix i TRS" % i)
        for k, ln in (("translation", 3), ("rotation", 4), ("scale", 3)):
            if k in n and not nums(n[k], ln):
                err("nodes[%d].%s" % (i, k))
    # cykly + hloubka
    for i in range(len(nodes)):
        d, j = 0, i
        while j in parent:
            j = parent[j]
            d += 1
            if d > _MAX_DEPTH:
                err("strom uzlu je prilis hluboky nebo obsahuje cyklus")
    # scenes
    scenes = g.get("scenes") or []
    if "scene" in g and not idx_ok(g["scene"], "scenes"):
        err("scene")
    for i, s in enumerate(scenes):
        sn = s.get("nodes", [])
        if not isinstance(sn, list) or len(set(map(repr, sn))) != len(sn):
            err("scenes[%d].nodes" % i)
        for r in sn:
            if not idx_ok(r, "nodes") or r in parent:
                err("scenes[%d].nodes obsahuje neplatny koren" % i)
    # animace (jen zakladni platnost - stejne se zahodi)
    for i, an in enumerate(g.get("animations") or []):
        for ch in an.get("channels", []) or []:
            tgt = (ch or {}).get("target") or {}
            if "node" in tgt and not idx_ok(tgt["node"], "nodes"):
                err("animations[%d] cil" % i)
    return parent


# ---------------------------------------------------------------------------
# Whitelist - prestavba objektu a kontrola hodnot
# ---------------------------------------------------------------------------

def _tag(t):
    return t if isinstance(t, str) else t[0]


def _val_ok(v, t):
    """Listova hodnota odpovida typu t ze _SCHEMA (bez vnorenych objektu)."""
    tag = _tag(t)
    if tag == "int":
        return type(v) is int and 0 <= v <= _MAX_INT
    if tag == "num":
        return _isnum(v)
    if tag == "bool":
        return type(v) is bool
    if tag == "g":
        return type(v) is int and 0 <= v <= _MAX_G
    if tag == "ints":
        return isinstance(v, list) and all(type(x) is int and 0 <= x <= _MAX_INT for x in v)
    if tag == "numlist":
        return isinstance(v, list) and 1 <= len(v) <= 16 and all(_isnum(x) for x in v)
    if tag == "nums":
        return isinstance(v, list) and len(v) == t[1] and all(_isnum(x) for x in v)
    if tag == "enum":
        return any(type(v) is type(e) and v == e for e in t[1])
    if tag == "re":
        return isinstance(v, str) and t[1].fullmatch(v) is not None
    if tag == "strs":
        return isinstance(v, list) and all(isinstance(x, str) and x in t[1] for x in v)
    return False


def _rebuild(o, kind, where, rep=None):
    """Novy objekt jen z povolenych klicu _SCHEMA[kind] (bez name/extras -
    ty nastavuje sanitize sam). Neznamy klic se zahodi (rep['keys_dropped']),
    povoleny klic s nepovolenou hodnotou = ValueError."""
    sch = _SCHEMA[kind]
    if not isinstance(o, dict):
        raise V3DError("%s: ocekavam objekt" % where)
    out = {}
    for k, v in o.items():
        t = sch.get(k)
        if t is None or k in _REBUILD_SKIP:
            if t is None and rep is not None:
                rep["keys_dropped"] += 1
            continue
        w = "%s.%s" % (where, k)
        tag = _tag(t)
        if tag == "obj":
            out[k] = _rebuild(v, t[1], w, rep)
        elif tag == "list":
            if not isinstance(v, list):
                raise V3DError("%s: ocekavam seznam" % w)
            out[k] = [_rebuild(x, t[1], "%s[%d]" % (w, i), rep) for i, x in enumerate(v)]
        elif _val_ok(v, t):
            out[k] = list(v) if isinstance(v, list) else v
        else:
            raise V3DError("%s: nepovolena hodnota" % w)
    return out


def _schema_errors(o, kind, path, bad):
    """Vrstva 1 final_check: kazdy klic z _SCHEMA[kind], kazda hodnota
    odpovida tvaru pro sve misto, povinne klice jsou."""
    sch = _SCHEMA[kind]
    if not isinstance(o, dict):
        bad(path, "ocekavam objekt (%s)" % kind)
        return
    for k in _REQUIRED.get(kind, ()):
        if k not in o:
            bad(path, "chybi povinny klic %s" % k)
    for k, v in o.items():
        p = path + (k,)
        t = sch.get(k) if isinstance(k, str) else None
        if t is None:
            bad(p, "klic mimo whitelist (%s)" % kind)
            continue
        tag = _tag(t)
        if tag == "obj":
            _schema_errors(v, t[1], p, bad)
        elif tag == "list":
            if not isinstance(v, list):
                bad(p, "ocekavam seznam")
            else:
                for i, x in enumerate(v):
                    _schema_errors(x, t[1], p + (i,), bad)
        elif tag == "map":
            if not isinstance(v, dict) or not v:
                bad(p, "ocekavam neprazdny objekt")
            else:
                for ak, av in v.items():
                    if not (isinstance(ak, str) and t[1].fullmatch(ak)):
                        bad(p + (ak,), "nepovoleny atribut")
                    elif not _val_ok(av, "int"):
                        bad(p + (ak,), "ocekavam index")
        elif tag == "v3d":
            try:
                if validate_spec(v) != v:
                    bad(p, "spec neni v kanonickem tvaru")
            except V3DError as e:
                bad(p, str(e))
        elif not _val_ok(v, t):
            bad(p, "nepovolena hodnota")


def _str_ok(s):
    return s in _STR_OK or _STR_OK_RE.fullmatch(s) is not None


# ---------------------------------------------------------------------------
# BIN - pokryti accessory, nulovani, kontrola
# ---------------------------------------------------------------------------

def _mark(mask, start, esize, stride, count):
    """Oznaci (0xFF) bajty prvku accessoru v masce."""
    if stride == esize:
        mask[start:start + count * esize] = b"\xff" * (count * esize)
        return
    for b in range(esize):
        s = start + b
        mask[s:s + stride * (count - 1) + 1:stride] = b"\xff" * count


def _and_mask(data, mask):
    """data AND mask (maska 0x00/0xFF) - rychle pres velka cela cisla."""
    return (int.from_bytes(data, "little") & int.from_bytes(mask, "little")).to_bytes(len(data), "little")


def check_bin(gltf, bin_data):
    """Kazdy bajt BIN, ktery nepatri zadnemu prvku accessoru (s ohledem na
    byteStride), musi byt nula. Jinak ValueError (schovana data)."""
    if bin_data is None:
        return
    b = bytes(bin_data)
    if not b:
        return
    mask = bytearray(len(b))
    views = gltf.get("bufferViews") or []
    for a in gltf.get("accessors") or []:
        if "bufferView" not in a:
            continue
        v = views[a["bufferView"]]
        esize = _elem_size(a["type"], _COMP_SIZE[a["componentType"]])
        stride = v.get("byteStride", esize)
        _mark(mask, v.get("byteOffset", 0) + a.get("byteOffset", 0), esize, stride, a["count"])
    inv = bytes(mask).translate(_INV)
    if int.from_bytes(b, "little") & int.from_bytes(inv, "little"):
        n = sum(1 for x, m in zip(b, mask) if x and not m)
        raise V3DError("check_bin: v BIN lezi %d nenulovych bajtu mimo data accessoru" % n)


# ---------------------------------------------------------------------------
# Pomocne
# ---------------------------------------------------------------------------

def _ext_used(o, acc):
    if isinstance(o, dict):
        ext = o.get("extensions")
        if isinstance(ext, dict):
            acc.update(ext.keys())
        for v in o.values():
            _ext_used(v, acc)
    elif isinstance(o, list):
        for v in o:
            _ext_used(v, acc)


def _guard_norm(name):
    s = re.sub(r"\((?:clone|instance)\)", "", name, flags=re.IGNORECASE).strip()
    s = re.sub(r"(?:[._\- ]*\d+)+$", "", s)
    return s


def _node_g(n):
    """(g, zdroj) z extras.g (cele cislo) nebo ze jmena bomgrp_N; jinak None."""
    ex = n.get("extras")
    if isinstance(ex, dict) and type(ex.get("g")) is int and 0 <= ex["g"] <= _MAX_G:
        return ex["g"], "extras"
    nm = n.get("name")
    if isinstance(nm, str):
        mt = _BOMGRP_RE.fullmatch(nm)
        if mt and int(mt.group(1)) <= _MAX_G:
            return int(mt.group(1)), "bomgrp"
    return None


def _uncovered_nonzero(views, buf):
    """True, kdyz v bufferu mimo dane bufferViews lezi nenulove bajty."""
    iv = sorted((v.get("byteOffset", 0), v.get("byteOffset", 0) + v["byteLength"]) for v in views)
    pos = 0
    for s, e in iv:
        if s > pos and buf.count(0, pos, s) != s - pos:
            return True
        pos = max(pos, e)
    return buf.count(0, pos) != len(buf) - pos


def _positions(g, bin_data, acc_i, cache):
    """Vrcholy accessoru POSITION jako seznam (x, y, z) - i normalizovane
    cele typy (KHR_mesh_quantization)."""
    if acc_i in cache:
        return cache[acc_i]
    a = g["accessors"][acc_i]
    if "bufferView" not in a:
        pts = [(0.0, 0.0, 0.0)]                 # accessor bez dat = same nuly
    else:
        v = g["bufferViews"][a["bufferView"]]
        ct = a["componentType"]
        esize = 3 * _COMP_SIZE[ct]
        stride = v.get("byteStride", esize)
        base = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        fmt = "<3" + _COMP_FMT[ct]
        n = a["count"]
        if stride == esize:
            pts = list(struct.iter_unpack(fmt, bin_data[base:base + n * esize]))
        else:
            pts = [struct.unpack_from(fmt, bin_data, base + i * stride) for i in range(n)]
        if a.get("normalized") and ct in _COMP_NORM:
            d = _COMP_NORM[ct]
            pts = [tuple(max(c / d, -1.0) for c in p) for p in pts]
    cache[acc_i] = pts
    return pts


def _model_aabb(g, bin_data=None, exact=False):
    """AABB modelu ve svetovych souradnicich. exact=False: z min/max
    POSITION (rohy lokalniho boxu - u otocenych meshi muze byt vetsi nez
    skutecnost); exact=True nebo chybi-li min/max: ze vsech vrcholu."""
    nodes = g.get("nodes") or []
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    cache = {}

    def add_points(m, pts):
        for k in range(3):
            a, b, c, d = m[k], m[4 + k], m[8 + k], m[12 + k]
            vals = [a * x + b * y + c * z for x, y, z in pts]
            lo[k] = min(lo[k], min(vals) + d)
            hi[k] = max(hi[k], max(vals) + d)

    def walk(i, pm, depth):
        if depth > _MAX_DEPTH:
            raise V3DError("strom uzlu je prilis hluboky")
        n = nodes[i]
        m = _mat_mul(pm, _local_matrix(n))
        if "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                pi = p["attributes"].get("POSITION")
                if pi is None:
                    continue
                a = g["accessors"][pi]
                if not exact and "min" in a and "max" in a and len(a["min"]) == 3:
                    corners = [(x, y, z) for x in (a["min"][0], a["max"][0])
                               for y in (a["min"][1], a["max"][1]) for z in (a["min"][2], a["max"][2])]
                    add_points(m, corners)
                elif bin_data is not None or "bufferView" not in a:
                    add_points(m, _positions(g, bin_data, pi, cache))
        for c in n.get("children", []):
            walk(c, m, depth + 1)

    for r in (g.get("scenes") or [{}])[g.get("scene", 0)].get("nodes", []):
        walk(r, list(_IDENT), 0)
    if lo[0] == math.inf:
        return None
    return {"min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi]}


def _box_excess(bx, mx):
    """O kolik mm model (mx) presahuje box (bx) - kladne = presahuje."""
    return max(max(bx["min"][i] - mx["min"][i], mx["max"][i] - bx["max"][i]) for i in range(3))


def _box_slack(bx, mx):
    """O kolik mm je box (bx) vetsi nez model (mx) - kladne = box je vetsi."""
    return max(max(mx["min"][i] - bx["min"][i], bx["max"][i] - mx["max"][i]) for i in range(3))


# ---------------------------------------------------------------------------
# sanitize
# ---------------------------------------------------------------------------

def sanitize(glb_bytes, spec=None, *, collapse=True, guard=True):
    """Vraci vycisteny GLB (bytes). Pri jakemkoli problemu ValueError (V3DError)."""
    return sanitize_report(glb_bytes, spec, collapse=collapse, guard=guard)[0]


def sanitize_report(glb_bytes, spec=None, *, collapse=True, guard=True):
    """Jako sanitize(), navic vraci hlaseni (dict s pocty a mapami indexu).
    Hlaseni a texty chyb mohou obsahovat puvodni jmena ze vstupu - patri
    adminovi/logu, ne zakaznikovi. Vstupni JSON se nemeni (vystup se
    sklada znovu)."""
    g, raw_bin = read_glb(glb_bytes)
    rep = {
        "nodes_in": len(g.get("nodes") or []), "nodes_out": 0, "collapsed": 0, "pruned": 0,
        "unreachable": 0, "meshes_removed": 0, "materials_removed": 0, "accessors_removed": 0,
        "bufferviews_removed": 0, "attributes_dropped": 0, "keys_dropped": 0, "bytes_zeroed": 0,
        "cameras_removed": 0, "animations_removed": 0, "extensions_removed": [], "scenes_removed": 0,
        "g_from_bomgrp": 0, "pivots": [], "bin_changed": False, "bin_chunk_trimmed": False,
        "warnings": [], "mesh_map": {}, "node_map": {}, "model_aabb": None,
    }
    check_structure(g, raw_bin, "vstup")

    # -- 2. co kontrakt nepotrebuje / nejde vycistit -> chyba
    for k in _REJECT_ARRAYS:
        if g.get(k):
            raise V3DError("vstup: " + _REJECT_MSG[k])
    bufs = g.get("buffers") or []
    if len(bufs) > 1 or any("uri" in b for b in bufs):
        raise V3DError("vstup: model musi byt jeden GLB s jedinym vnitrnim BIN (bez uri)")
    for i, a in enumerate(g.get("accessors") or []):
        if "sparse" in a:
            raise V3DError("vstup: accessors[%d] je sparse - kontrakt ho nepovoluje" % i)
    meshes = g.get("meshes") or []
    for i, m in enumerate(meshes):
        for j, p in enumerate(m["primitives"]):
            if p.get("targets"):
                raise V3DError("vstup: meshes[%d].primitives[%d] ma morph targety - kontrakt je nepovoluje"
                               % (i, j))
    req = g.get("extensionsRequired") or []
    if not isinstance(req, list) or not all(isinstance(e, str) for e in req):
        raise V3DError("vstup: extensionsRequired musi byt seznam retezcu")
    bad_req = [e for e in req if e not in ALLOWED_EXTENSIONS]
    if bad_req:
        raise V3DError("vstup: nepovolena povinna rozsireni %s" % bad_req)
    used_in = g.get("extensionsUsed") or []
    used_in = set(e for e in used_in if isinstance(e, str)) if isinstance(used_in, list) else set()

    # -- 3. kamery, animace, nepovolena rozsireni (do vystupu se nedostanou)
    rep["animations_removed"] = len(g.get("animations") or [])
    rep["cameras_removed"] = len(g.get("cameras") or [])
    before = set()
    _ext_used(g, before)
    rep["extensions_removed"] = sorted(e for e in (before | used_in)
                                       if isinstance(e, str) and e not in ALLOWED_EXTENSIONS)

    # -- scena
    nodes = g.get("nodes") or []
    scenes = g.get("scenes") or []
    if not scenes:
        raise V3DError("vstup: chybi scena")
    scene_i = g.get("scene", 0)
    rep["scenes_removed"] = len(scenes) - 1
    roots = list(scenes[scene_i].get("nodes", []))
    reach = set()
    stack = list(roots)
    while stack:
        i = stack.pop()
        reach.add(i)
        stack.extend(nodes[i].get("children", []))
    rep["unreachable"] = len(nodes) - len(reach)
    parent = {}
    for i in reach:
        for c in nodes[i].get("children", []):
            parent[c] = i

    # -- 4. spec + pivoty
    pivot_idx = {}
    dup = set()
    for i, n in enumerate(nodes):
        nm = n.get("name")
        if isinstance(nm, str) and _P_RE.fullmatch(nm):
            if nm in pivot_idx:
                dup.add(nm)
            pivot_idx[nm] = i
    norm_spec = None
    pivot_name = {}                       # stary index uzlu -> p-jmeno
    if spec is not None:
        norm_spec = validate_spec(spec, pivots=set(pivot_idx))
        for nm in sorted(spec_pivot_refs(norm_spec)):
            if nm in dup:
                raise V3DError("vstup: pivot %s je v modelu vickrat" % nm)
            i = pivot_idx[nm]
            n = nodes[i]
            if i not in reach:
                raise V3DError("vstup: pivot %s neni ve scene" % nm)
            if "mesh" in n:
                raise V3DError("vstup: pivot %s neni prazdny uzel (ma mesh)" % nm)
            if not _rotation_is_identity(n):
                raise V3DError("vstup: pivot %s nema jednotkovou rotaci" % nm)
            pivot_name[i] = nm
        rep["pivots"] = sorted(pivot_name.values())

    # -- 5. strazce vstupu (jen sit - viz docstring modulu)
    materials = g.get("materials") or []
    has_mesh = {}

    def sub_has_mesh(i):
        if i not in has_mesh:
            n = nodes[i]
            has_mesh[i] = "mesh" in n or any(sub_has_mesh(c) for c in n.get("children", []))
        return has_mesh[i]

    if guard:
        hits = []
        for i in sorted(reach):
            n = nodes[i]
            nm = n.get("name")
            if isinstance(nm, str) and _GUARD_RE.fullmatch(_guard_norm(nm)) and sub_has_mesh(i):
                hits.append("uzel %r" % nm)
            if "mesh" in n:
                mesh = meshes[n["mesh"]]
                mn = mesh.get("name")
                if isinstance(mn, str) and _GUARD_RE.fullmatch(_guard_norm(mn)):
                    hits.append("mesh %r" % mn)
                for p in mesh["primitives"]:
                    if "material" in p:
                        matn = materials[p["material"]].get("name")
                        if isinstance(matn, str) and _GUARD_RE.fullmatch(_guard_norm(matn)):
                            hits.append("material %r" % matn)
        if hits:
            uniq = list(dict.fromkeys(hits))
            raise V3DError("vstup: model obsahuje geometrii, ktera nesmi k zakaznikovi "
                           "(logo/podlaha/pomucky/koty/karoserie): %s%s"
                           % (", ".join(uniq[:6]), " ..." if len(uniq) > 6 else ""))

    # -- 6. strom (slouceni, prazdne listy, g)
    no_collapse = set(pivot_name)
    for i in pivot_name:
        if i in parent:
            no_collapse.add(parent[i])
    for i in reach:
        if "mesh" in nodes[i]:
            no_collapse.add(i)

    def emit(i, acc, inh_g, depth):
        if depth > _MAX_DEPTH:
            raise V3DError("vstup: strom uzlu je prilis hluboky")
        n = nodes[i]
        own = _node_g(n)
        if own is not None and own[1] == "bomgrp":
            rep["g_from_bomgrp"] += 1
        geff = own[0] if own is not None else inh_g
        lm = _local_matrix(n)
        em = lm if acc is None else _mat_mul(acc, lm)
        kids_src = n.get("children", [])
        if collapse and i not in no_collapse and all(
                _decomposable(_mat_mul(em, _local_matrix(nodes[c]))) for c in kids_src):
            rep["collapsed"] += 1
            acc_c = None if _is_identity(em) else em
            res = []
            for c in kids_src:
                res.extend(emit(c, acc_c, geff, depth + 1))
            return res
        kids = []
        for c in kids_src:
            kids.extend(emit(c, None, None, depth + 1))
        if "mesh" not in n and not kids and i not in pivot_name:
            rep["pruned"] += 1
            return []
        return [{"src": i, "mat": None if acc is None else em, "g": geff, "kids": kids}]

    top = []
    for r in roots:
        top.extend(emit(r, None, None, 0))

    flat = []
    node_map = {}

    def assign(t):
        k = len(flat)
        flat.append(None)
        node_map[t["src"]] = k
        kid_idx = [assign(c) for c in t["kids"]]
        flat[k] = (t, kid_idx)
        return k

    root_idx = [assign(t) for t in top]
    if not flat:
        raise V3DError("vstup: model neobsahuje zadnou geometrii")

    # -- 7. GC + atributy z whitelistu
    mesh_old = sorted({nodes[t["src"]]["mesh"] for t, _ in flat if "mesh" in nodes[t["src"]]})
    if not mesh_old:
        raise V3DError("vstup: model neobsahuje zadnou geometrii")
    mesh_map = {o: k for k, o in enumerate(mesh_old)}
    acc_used, mat_used = set(), set()
    attrs_kept = {}
    for o in mesh_old:
        for j, p in enumerate(meshes[o]["primitives"]):
            at = {a: v for a, v in p["attributes"].items() if _ATTR_RE.fullmatch(a)}
            rep["attributes_dropped"] += len(p["attributes"]) - len(at)
            if "POSITION" not in at:
                raise V3DError("vstup: meshes[%d].primitives[%d] nema POSITION" % (o, j))
            attrs_kept[(o, j)] = at
            acc_used.update(at.values())
            if "indices" in p:
                acc_used.add(p["indices"])
            if "material" in p:
                mat_used.add(p["material"])
    mat_old = sorted(mat_used)
    mat_map = {o: k for k, o in enumerate(mat_old)}
    accessors = g.get("accessors") or []
    acc_old = sorted(acc_used)
    acc_map = {o: k for k, o in enumerate(acc_old)}
    # -- 8. prestavba z whitelistu (nepovolena hodnota = chyba hned, pred BIN)
    acc_new = {o: _rebuild(accessors[o], "accessor", "vstup: accessors[%d]" % o, rep) for o in acc_old}
    for o in mesh_old:
        for j in range(len(meshes[o]["primitives"])):
            pa = acc_new[attrs_kept[(o, j)]["POSITION"]]
            if pa["type"] != "VEC3" or pa["componentType"] == 5125:
                raise V3DError("vstup: meshes[%d].primitives[%d].POSITION musi byt VEC3" % (o, j))
    mat_new = [_rebuild(materials[o], "material", "vstup: materials[%d]" % o, rep) for o in mat_old]
    views = g.get("bufferViews") or []
    bv_old = sorted({a["bufferView"] for a in acc_new.values() if "bufferView" in a})
    bv_map = {o: k for k, o in enumerate(bv_old)}
    view_new = {o: _rebuild(views[o], "bufferView", "vstup: bufferViews[%d]" % o, rep) for o in bv_old}

    rep["meshes_removed"] = len(meshes) - len(mesh_old)
    rep["materials_removed"] = len(materials) - len(mat_old)
    rep["accessors_removed"] = len(accessors) - len(acc_old)
    rep["bufferviews_removed"] = len(views) - len(bv_old)

    # -- 9. BIN: nepokryte bajty bufferView vynulovat, pripadne prebalit
    bin_in = b""
    if bufs:
        bin_in = bytes(raw_bin[:bufs[0]["byteLength"]])
        if len(raw_bin) - len(bin_in) > 3 or raw_bin.count(0, len(bin_in)) != len(raw_bin) - len(bin_in):
            rep["bin_chunk_trimmed"] = True
    masks = {o: bytearray(views[o]["byteLength"]) for o in bv_old}
    for a in acc_new.values():
        if "bufferView" in a:
            v = views[a["bufferView"]]
            esize = _elem_size(a["type"], _COMP_SIZE[a["componentType"]])
            _mark(masks[a["bufferView"]], a.get("byteOffset", 0), esize, v.get("byteStride", esize), a["count"])
    replaced = {}
    for o in bv_old:
        if masks[o].count(0) == 0:
            continue
        off = views[o].get("byteOffset", 0)
        data = bin_in[off:off + views[o]["byteLength"]]
        z = _and_mask(data, masks[o])
        if z != data:
            replaced[o] = z
            rep["bytes_zeroed"] += sum(1 for x, y in zip(data, z) if x != y)
    identity = bv_old == list(range(len(views)))
    used_views = [views[o] for o in bv_old]
    hidden = bool(bin_in) and _uncovered_nonzero(used_views, bin_in)
    new_views = []
    if identity and not replaced and not hidden:
        new_bin = bin_in if bufs else None
        for o in bv_old:
            new_views.append(view_new[o])
    else:
        nb = bytearray()
        for o in bv_old:
            v = views[o]
            data = replaced.get(o)
            if data is None:
                off = v.get("byteOffset", 0)
                data = bin_in[off:off + v["byteLength"]]
            nb += b"\x00" * (-len(nb) % 4)
            nv = dict(view_new[o])
            nv.update(byteOffset=len(nb), byteLength=len(data))
            new_views.append(nv)
            nb += data
        new_bin = bytes(nb)
        rep["bin_changed"] = True
    if bufs and new_bin is not None and len(new_bin) == 0:
        raise V3DError("vstup: po vycisteni nezbyla zadna binarni data")

    # -- 10. vystupni JSON (sklada se znovu, jmena a extras jen povolene)
    out = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": root_idx}]}
    out_nodes = []
    for k, (t, kid_idx) in enumerate(flat):
        n = nodes[t["src"]]
        d = {"name": pivot_name.get(t["src"], "n%d" % k)}
        if kid_idx:
            d["children"] = kid_idx
        if "mesh" in n:
            d["mesh"] = mesh_map[n["mesh"]]
        if t["mat"] is None:
            for key in ("matrix", "translation", "rotation", "scale"):
                if key in n:
                    d[key] = list(n[key])
        elif not _is_identity(t["mat"]):
            d["matrix"] = [_clean_num(v) for v in t["mat"]]
        if t["g"] is not None:
            d["extras"] = {"g": t["g"]}
        out_nodes.append(d)
    out["nodes"] = out_nodes

    out_meshes = []
    for o in mesh_old:
        prims = []
        for j, p in enumerate(meshes[o]["primitives"]):
            q = {"attributes": {a: acc_map[v] for a, v in attrs_kept[(o, j)].items()}}
            if "indices" in p:
                q["indices"] = acc_map[p["indices"]]
            if "material" in p:
                q["material"] = mat_map[p["material"]]
            if "mode" in p:
                q["mode"] = p["mode"]
            prims.append(q)
        out_meshes.append({"primitives": prims})
    out["meshes"] = out_meshes

    for k, o in enumerate(mat_old):
        nm = materials[o].get("name")
        if isinstance(nm, str) and _MAT_NAME_RE.fullmatch(nm):
            mat_new[k]["name"] = nm
    if mat_new:
        out["materials"] = mat_new

    out_acc = []
    for o in acc_old:
        a = acc_new[o]
        if "bufferView" in a:
            a["bufferView"] = bv_map[a["bufferView"]]
        out_acc.append(a)
    out["accessors"] = out_acc
    if new_views:
        for v in new_views:
            v["buffer"] = 0
        out["bufferViews"] = new_views
    if new_bin is not None:
        out["buffers"] = [{"byteLength": len(new_bin)}]
    if norm_spec is not None:
        out["scenes"][0]["extras"] = {"v3d": norm_spec}

    used = set()
    _ext_used(out, used)
    if "KHR_mesh_quantization" in used_in or "KHR_mesh_quantization" in req:
        used.add("KHR_mesh_quantization")
    if used:
        out["extensionsUsed"] = sorted(used)
        req_out = sorted(e for e in req if e in used)
        if req_out:
            out["extensionsRequired"] = req_out
    out = {k: out[k] for k in _TOP_KEYS_OUT if k in out}

    # -- 11. kontroly vystupu
    rep["nodes_out"] = len(out_nodes)
    rep["node_map"] = node_map
    rep["mesh_map"] = mesh_map
    if norm_spec is not None:
        for nm in rep["pivots"]:
            k = node_map.get(pivot_idx[nm])
            if k is None or out_nodes[k]["name"] != nm:
                raise V3DError("vystup: pivot %s se ztratil" % nm)
            st = [k]
            found = False
            while st and not found:
                j = st.pop()
                found = "mesh" in out_nodes[j]
                st.extend(out_nodes[j].get("children", []))
            if not found:
                raise V3DError("vystup: pod pivotem %s neni zadna geometrie" % nm)
    check_structure(out, new_bin, "vystup")
    final_check(out)
    check_bin(out, new_bin)
    if norm_spec is not None:
        # skutecne AABB z vrcholu (min/max accessoru muze chybet nebo u
        # otocenych meshi prestrelit) - presah pres spec.box = chyba
        rep["model_aabb"] = _model_aabb(out, new_bin, exact=True)
        if rep["model_aabb"]:
            bx, mx = norm_spec["box"], rep["model_aabb"]
            over = _box_excess(bx, mx)
            if over > _BOX_TOL_MM:
                raise V3DError("vystup: model presahuje spec.box az o %.0f mm (povoleno %g mm) - ve "
                               "vystupu je nejspis geometrie navic (logo, obal, karoserie, pomucky) "
                               "nebo spec.box nesedi" % (over, _BOX_TOL_MM))
            slack = _box_slack(bx, mx)
            if slack > _BOX_TOL_MM:
                rep["warnings"].append("spec.box je vetsi nez model az o %.0f mm" % slack)
    else:
        rep["model_aabb"] = _model_aabb(out, new_bin)
    data = write_glb(out, new_bin)
    j2, b2 = read_glb(data)
    if j2 != out or (new_bin is not None and bytes(b2[:len(new_bin)]) != new_bin):
        raise V3DError("vystup: zapsany GLB se neshoduje po zpetnem nacteni")
    return data, rep


# ---------------------------------------------------------------------------
# final_check
# ---------------------------------------------------------------------------

def _fmt_path(path):
    s = ""
    for p in path:
        s += "[%d]" % p if isinstance(p, int) else ("." + str(p) if s else str(p))
    return s or "<koren>"


def final_check(gltf):
    """Zaverecna kontrola JSON casti zakaznickeho GLB. Pri jakemkoli nalezu
    ValueError (model nevznikne). Tri vrstvy:
      1. pozitivni whitelist podle mista (_SCHEMA): kazdy klic povoleny pro
         svuj druh objektu, kazda hodnota spravneho tvaru (vycty alphaMode/
         type/componentType/target/mode, jmena uzlu n<i>/p<i>, materialu
         m<i>, extras jen nodes[i]={g:int} a scenes[0]={v3d}, v3d v
         kanonickem tvaru validate_spec, rozsireni jen z ALLOWED_EXTENSIONS
         s vlastnim whitelistem klicu, atributy jen POSITION/NORMAL/...),
      2. globalne: kazdy klic z _ALL_KEYS (nebo jmeno atributu), kazdy
         retezec z whitelistu hodnot (_STR_OK / _STR_OK_RE) a nic proti
         FORBIDDEN_RE (klice i hodnoty), jen JSON typy a konecna cisla,
      3. jedna scena, p-jmena uzlu jednoznacna a odkazovana ze spec (a naopak)."""
    problems = []

    def bad(path, msg):
        problems.append("%s: %s" % (_fmt_path(path), msg))

    if not isinstance(gltf, dict):
        raise V3DError("final_check: glTF neni objekt")

    # vrstva 1
    _schema_errors(gltf, "gltf", (), bad)

    # vrstva 2
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                p = path + (k,)
                if not isinstance(k, str):
                    bad(path, "klic neni retezec")
                    continue
                if k not in _ALL_KEYS and not _ATTR_RE.fullmatch(k):
                    bad(p, "klic mimo globalni whitelist")
                if FORBIDDEN_RE.search(k):
                    bad(p, "zakazany retezec v klici")
                walk(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + (i,))
        elif isinstance(o, str):
            if not _str_ok(o):
                bad(path, "retezec mimo whitelist %r" % (o[:40],))
            if FORBIDDEN_RE.search(o):
                bad(path, "zakazany retezec %r" % (o[:40],))
        elif o is None or isinstance(o, bool):
            pass
        elif isinstance(o, (int, float)):
            if not math.isfinite(o):
                bad(path, "neplatne cislo")
        else:
            bad(path, "nepovoleny typ hodnoty")

    walk(gltf, ())

    # vrstva 3
    scenes = gltf.get("scenes") or []
    if not isinstance(scenes, list) or len(scenes) != 1:
        bad(("scenes",), "vystup musi mit prave jednu scenu")
    pnames = []
    for i, n in enumerate(gltf.get("nodes") or []):
        if isinstance(n, dict) and isinstance(n.get("name"), str) and _P_RE.fullmatch(n["name"]):
            pnames.append(n["name"])
    if len(set(pnames)) != len(pnames):
        bad(("nodes",), "duplicitni jmena pivotu")
    v3d = None
    if scenes and isinstance(scenes, list) and isinstance(scenes[0], dict) \
            and isinstance(scenes[0].get("extras"), dict):
        v3d = scenes[0]["extras"].get("v3d")
    if v3d is not None and not problems:
        try:
            validate_spec(v3d, pivots=set(pnames))
            refs = spec_pivot_refs(v3d)
        except V3DError as e:
            bad(("scenes", 0, "extras", "v3d"), str(e))
            refs = set()
        extra_p = set(pnames) - refs
        if extra_p:
            bad(("nodes",), "pivoty bez odkazu ze spec: %s" % sorted(extra_p)[:5])
    elif v3d is None and pnames:
        bad(("nodes",), "uzly p<i> bez spec v3d")

    if problems:
        more = " (+%d dalsich)" % (len(problems) - 12) if len(problems) > 12 else ""
        raise V3DError("final_check: " + "; ".join(problems[:12]) + more)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if len(args) not in (2, 3):
        print(__doc__.split("\n\n")[0])
        print("pouziti: v3d_glb.py vstup.glb vystup.glb [spec.json] [--no-collapse] [--no-guard]")
        return 2
    with open(args[0], "rb") as fh:
        data = fh.read()
    spec = None
    if len(args) == 3:
        with open(args[2], encoding="utf-8") as fh:
            spec = json.load(fh)
    try:
        out, rep = sanitize_report(data, spec, collapse="--no-collapse" not in flags,
                                   guard="--no-guard" not in flags)
    except ValueError as e:
        print("CHYBA: %s" % e, file=sys.stderr)
        return 1
    with open(args[1], "wb") as fh:
        fh.write(out)
    rep = {k: v for k, v in rep.items() if k not in ("mesh_map", "node_map")}
    rep["bytes_in"], rep["bytes_out"] = len(data), len(out)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
