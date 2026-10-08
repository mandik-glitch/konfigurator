#!/usr/bin/env python3
"""Zmeri 3D logo v .glb - hlavne SRAZENI HORNICH HRAN.

    /opt/blender-5.2/blender -b -P zmer_logo.py -- webapp/katalog/logo_logiman_cz.glb

Proc to existuje (bot9 2026-09-11): srazeni hran loga se tri kola "opravovalo"
a pokazde se ohlasilo jako hotove, aniz v geometrii bylo. Duvod byl vzdycky
stejny - kontrolovalo se, jestli bevel PRIDAL VRCHOLY. To plati i tehdy, kdyz
je fazeta 0,013 mm siroka, tedy neviditelna.

Jediny dukaz, ze srazeni existuje, je PLOCHA. Bez srazeni jsou oba lice
stejne velke (pomer 1,000); s 1mm fazetou je viditelny lic vyrazne mensi a
objevi se plochy se sklonem 44-46 stupnu, ktere pred tim nebyly.

POZOR na to, ktery lic je ktery. Logo lezi na profilu: strana PRILEHAJICI
k profilu je v glTF na Z=-0,696 (po importu do Blenderu Y=+0,696) a zustava
ostra. VIDITELNY lic je ten odvraceny, na opacne strane - a srazi se prave
on. Zamena obou je snadna, protoze bez srazeni jsou k nerozeznani.
"""
import bpy, math, sys
from collections import Counter
import mathutils

VSTUP = sys.argv[sys.argv.index("--") + 1:][0]
PRILEHAJICI_STRANA_GLTF_Z = -0.696

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=VSTUP)
mo = [o for o in bpy.data.objects if o.type == "MESH"]
if not mo:
    sys.exit("CHYBA: v souboru neni zadny mesh")
bpy.ops.object.select_all(action="DESELECT")
for o in mo:
    o.select_set(True)
bpy.context.view_layer.objects.active = mo[0]
if len(mo) > 1:
    bpy.ops.object.join()
ob = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
me = ob.data

xs = [v.co.x for v in me.vertices]
ys = [v.co.y for v in me.vertices]
zs = [v.co.z for v in me.vertices]
roz = {"x": max(xs)-min(xs), "y": max(ys)-min(ys), "z": max(zs)-min(zs)}
osa = min(roz, key=roz.get)
idx = {"x": 0, "y": 1, "z": 2}[osa]
mez = [(min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))]

print("SOUBOR:", VSTUP)
print("rozmery  X %.3f  Y %.3f  Z %.3f   (osa tloustky: %s = %.4f mm)"
      % (roz["x"], roz["y"], roz["z"], osa, roz[osa]))
print("vrcholu %d, ploch %d" % (len(me.vertices), len(me.polygons)))

# prilehajici strana = ta na +osa (po importu glTF), viditelny lic naproti
rovina_prilehajici = -PRILEHAJICI_STRANA_GLTF_Z
k_profilu = mathutils.Vector((0, 0, 0))
k_profilu[idx] = 1.0

viditelny = prilehajici = fazety = naruby = 0.0
sklony = Counter()
for p in me.polygons:
    sk = p.normal.dot(k_profilu)
    if sk < -0.999:
        viditelny += p.area
    elif sk > 0.999:
        if abs(p.center[idx] - rovina_prilehajici) < 0.001:
            prilehajici += p.area
        else:
            naruby += p.area
    uhel = math.degrees(math.acos(max(-1.0, min(1.0, abs(sk)))))
    if 44.0 <= uhel <= 46.0:
        fazety += p.area
    sklony[round(uhel / 5) * 5] += p.area

print()
print("VIDITELNY LIC (odvraceny od profilu) : %9.2f mm2   <- tenhle se srazi"
      % viditelny)
print("PRILEHAJICI LIC (na profilu)         : %9.2f mm2   <- zustava ostry"
      % prilehajici)
if prilehajici:
    print("pomer viditelny/prilehajici          : %9.4f      (1,000 = zadne srazeni)"
          % (viditelny / prilehajici))
print("plochy se sklonem 44-46 (fazeta 45)  : %9.3f mm2  <- bez srazeni ~0"
      % fazety)
if naruby > 0.001:
    print("plochy obracene naruby               : %9.3f mm2  <- fazeta prorostla!"
          % naruby)

# jak siroka fazeta je - uzka fazeta je totez jako zadna
plne = 0.0
for p in me.polygons:
    sk = p.normal.dot(k_profilu)
    uhel = math.degrees(math.acos(max(-1.0, min(1.0, abs(sk)))))
    if 44.0 <= uhel <= 46.0:
        h = [me.vertices[v].co[idx] for v in p.vertices]
        if (max(h) - min(h)) > 0.95:
            plne += p.area
print("z toho fazety siroke aspon 0,95 mm   : %9.3f mm2 (%.0f %%)"
      % (plne, 100.0 * plne / max(fazety, 1e-9)))

print()
print("rozlozeni plochy podle sklonu od roviny lice:")
for k in sorted(sklony):
    if sklony[k] > 0.05:
        print("   %3d-%3d stupnu : %9.3f mm2" % (k - 2, k + 2, sklony[k]))
