"""Blender-side geometrie pro "Vytvorit online nabidku" u Vandr karet
(bot10, 2026-09-28, Robert pres bot3: "integrace Vandr do online
nabidky"). Spousti api/vandr_scene_offers.py jako subprocess.

POZOR - ZUZENO 2026-09-28 (Robert primo: "ty 2D nakresy nemuzes rucne
kreslit, musi se natahnout jinak hotove z Vandru"): puvodne tenhle
skript navic renderoval 2 perspektivni 3D pohledy (Cycles) pro
view3d_a/view3d_b - TA CAST JE PRYC. 3D i 2D kotovane obrazky teď
prichazeji primo z vanDrawee DB (stored_model_parts.image_3D_primary/
image_3D_secondary/image_2D_with_dim, viz api/vandr_scene_offers.py a
novy artisan prikaz `vandr:offer-data`). Tenhle skript uz dela JEN dve
veci, ktere Vandr export sam neresi:

  1. Rozdeli mesh uzly GLB na "profily" (jmeno NNxNNxLLL, hlinikove
     tyce) a "obal" (karoserie/podlaha - >=60% sceny v aspon 2 ze 3 os,
     stejna heuristika jako razitkovaci generator) a napise JSON s
     celkovymi rozmery (pro "rozmer_mm" v odpovedi API, NE pro kresleni
     kotovani - to uz je hotove v obrazcich z Vandru).
     DULEZITE (2 chyby chycene pri prvnim pouziti, viz AGENTS_LOG
     2026-09-28): celkovy rozmer se pocita ze VSECH dilu KROME obalu
     (ne jen z profilu - plastove boxy/zasuvky/kovani nemaji NNxNNxLLL
     jmeno, ale patri do rozmeru produktu; a NIKDY z cele sceny vcetne
     obalu, to by ukazalo rozmer cele karoserie vozidla, ne sestavy).
  2. Exportuje OCISTENOU kopii GLB (bez obalu) pro interaktivni 3D
     prohlizec v nabidce - jinak by `buildOverallDimensions()` v
     nabidka-online.html spocital kotu z CELE sceny vcetne karoserie
     (presne tenhle nesoulad byl zjisten a opraven na karte #4910).

Pouziti:
    blender -b -P 2026-09-28_vandr_offer_geometry.py -- <glb_in> <geom_json_out> <clean_glb_out>
"""
import json
import re
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
GLB_IN, GEOM_JSON_OUT, CLEAN_GLB_OUT = argv[:3]

OBAL_POMER = 0.6
CAND_RE = re.compile(r"^[A-Za-z_]*(\d+)x(\d+)x(\d+)", re.IGNORECASE)
RAZITKO_RE = re.compile(r"^(logo_logiman_cz|vypln_placka|vypln_placka_30)", re.IGNORECASE)


def _world_aabb(o):
    mn = Vector((1e18, 1e18, 1e18))
    mx = Vector((-1e18, -1e18, -1e18))
    for c in o.bound_box:
        wc = o.matrix_world @ Vector(c)
        mn.x, mn.y, mn.z = min(mn.x, wc.x), min(mn.y, wc.y), min(mn.z, wc.z)
        mx.x, mx.y, mx.z = max(mx.x, wc.x), max(mx.y, wc.y), max(mx.z, wc.z)
    return mn, mx


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]

boxes = {}
scene_mn = Vector((1e18, 1e18, 1e18))
scene_mx = Vector((-1e18, -1e18, -1e18))
for o in meshes:
    mn, mx = _world_aabb(o)
    boxes[o.name] = (mn, mx)
    scene_mn.x, scene_mn.y, scene_mn.z = min(scene_mn.x, mn.x), min(scene_mn.y, mn.y), min(scene_mn.z, mn.z)
    scene_mx.x, scene_mx.y, scene_mx.z = max(scene_mx.x, mx.x), max(scene_mx.y, mx.y), max(scene_mx.z, mx.z)
scene_size = (scene_mx.x - scene_mn.x, scene_mx.y - scene_mn.y, scene_mx.z - scene_mn.z)

obal_names = set()
for name, (mn, mx) in boxes.items():
    span = (mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    velke = sum(1 for i in range(3) if scene_size[i] > 0 and span[i] >= OBAL_POMER * scene_size[i])
    if velke >= 2:
        obal_names.add(name)

profily = []
for o in meshes:
    if o.name in obal_names or RAZITKO_RE.match(o.name or ""):
        continue
    m = CAND_RE.match(o.name or "")
    if not m:
        continue
    mn, mx = boxes[o.name]
    dims = (mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)
    dom = max(range(3), key=lambda i: dims[i])
    prurez = tuple(sorted((int(m.group(1)), int(m.group(2)))))
    profily.append({
        "name": o.name, "prurez": list(prurez), "delka_mm": round(dims[dom], 1),
        "min": [mn.x, mn.y, mn.z], "max": [mx.x, mx.y, mx.z],
    })

# Celkovy rozmer = VSE KROME obalu (ne jen profily - viz komentar nahore).
prod_mn = Vector((1e18, 1e18, 1e18))
prod_mx = Vector((-1e18, -1e18, -1e18))
for o in meshes:
    if o.name in obal_names:
        continue
    mn, mx = boxes[o.name]
    prod_mn.x, prod_mn.y, prod_mn.z = min(prod_mn.x, mn.x), min(prod_mn.y, mn.y), min(prod_mn.z, mn.z)
    prod_mx.x, prod_mx.y, prod_mx.z = max(prod_mx.x, mx.x), max(prod_mx.y, mx.y), max(prod_mx.z, mx.z)

geom_out = {
    "overall_min": [prod_mn.x, prod_mn.y, prod_mn.z],
    "overall_max": [prod_mx.x, prod_mx.y, prod_mx.z],
    "overall_size": [prod_mx.x - prod_mn.x, prod_mx.y - prod_mn.y, prod_mx.z - prod_mn.z],
    "obal_names": sorted(obal_names),
    "total_mesh": len(meshes),
    "profily": profily,
}
with open(GEOM_JSON_OUT, "w", encoding="utf-8") as f:
    json.dump(geom_out, f, ensure_ascii=False)
print("GEOM_OK profilu=%d obal=%d" % (len(profily), len(obal_names)))

for name in list(obal_names):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.export_scene.gltf(filepath=CLEAN_GLB_OUT, export_format="GLB", use_selection=False)
print("CLEAN_GLB_OK", CLEAN_GLB_OUT)
