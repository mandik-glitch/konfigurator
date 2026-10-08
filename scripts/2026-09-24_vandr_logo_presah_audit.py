#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nezavisle overeni bot3 obavy (4565 "logo presahuje do vzduchu"):
pro KAZDE logo v aktualnich datech karty zmer vzdalenost OBOU koncu jeho
DELKOVE osy (222.204 mm, pulka na kazdou stranu od pozice) od nejblizsi
skutecne mesh plochy v cele scene (BVHTree.find_nearest). Velka vzdalenost
(desitky mm) = konec loga je v prazdnu = presne to, co Robert videl.

Pozice/quaternion jsou v THREE.JS prostoru (jak je zapsany v DB) - prevod
do Blender prostoru pro raycast/BVH je INVERZE toho, co dela generator
(tam C_INV: Blender->three.js), tady tedy C: three.js->Blender - STEJNA
matice jako v generatoru (Matrix.Rotation(90, 4, 'X')), ne vlastni odhad.

POUZITI: /opt/blender-5.2/blender -b -noaudio -P overeni_logo_na_profilu.py -- <glb> <razitka.json> <karta>
"""
import bpy, sys, json, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
GLB_PATH, RAZITKA_JSON_PATH, KARTA = argv[0], argv[1], argv[2]

C = Matrix.Rotation(math.radians(90.0), 4, "X")  # three.js -> Blender (stejna jako generator, jen NEinvertovana)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
bpy.context.view_layer.update()

# BVH ze VSECH mesh trojuhelniku (vc. karoserie/podlahy - Robert vidi
# CELOU scenu ve viewru, ne jen orazitkovatelne profily).
verts, tris = [], []
for o in bpy.context.scene.objects:
    if o.type != 'MESH':
        continue
    mesh = o.data
    o_mat = o.matrix_world
    base = len(verts)
    for v in mesh.vertices:
        verts.append(o_mat @ v.co)
    for poly in mesh.polygons:
        idx = [base + i for i in poly.vertices]
        for k in range(1, len(idx) - 1):
            tris.append((idx[0], idx[k], idx[k + 1]))
bvh = BVHTree.FromPolygons(verts, tris)
print("BVH: %d vertexu, %d trojuhelniku z cele sceny" % (len(verts), len(tris)))

def osa_x_z_quaternionu(q):
    x, y, z, w = q
    return Vector((1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)))

razitka = json.load(open(RAZITKA_JSON_PATH, encoding="utf-8"))
logos = [r for r in razitka if r["part_id"] == "logo_logiman_cz"]
LOGO_PUL_MM = 222.204 / 2.0
print("KARTA %s: %d log v datech" % (KARTA, len(logos)))

nejhorsi = 0.0
for r in logos:
    pos_three = Vector(r["position"])
    osa_three = osa_x_z_quaternionu(r["quaternion"]).normalized()
    for znam, label in ((1, "konec+"), (-1, "konec-")):
        konec_three = pos_three + osa_three * (znam * LOGO_PUL_MM)
        konec_blender = C.to_3x3() @ konec_three
        # BVH.find_nearest hleda i skrz povrch (neni to raycast) - presne to,
        # co chceme: "je nejakA plocha nablizku", ne "je vidět shora".
        loc, normal, idx, dist = bvh.find_nearest(konec_blender, 60.0)  # strop hledani 60mm
        if dist is None:
            print("  %-30s %-7s VZDALENOST > 60mm OD JAKEKOLI PLOCHY <-- PRESAHUJE DO PRAZDNA"
                  % (r["role"], label))
            nejhorsi = max(nejhorsi, 999.0)
        else:
            znacka = "  " if dist < 8.0 else (" <-- PODEZRELE (>8mm od nejblizsi plochy)" if dist < 20.0
                     else " <-- PRESAHUJE DO PRAZDNA (>20mm)")
            print("  %-30s %-7s vzdalenost od nejblizsi plochy: %5.1f mm%s"
                  % (r["role"], label, dist, znacka))
            nejhorsi = max(nejhorsi, dist)

print("NEJHORSI (max pres vsechny konce vsech log): %.1f mm" % nejhorsi)
print("VERDIKT: %s" % ("OK (vsechny konce <8mm od plochy)" if nejhorsi < 8.0 else "NALEZEN PROBLEM"))
