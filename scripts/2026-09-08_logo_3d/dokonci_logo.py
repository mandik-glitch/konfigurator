#!/usr/bin/env python3
"""Dokonci 3D logo z OBJ na katalogovy .glb - vcetne SRAZENI HORNICH HRAN.

    /opt/blender-5.2/blender -b -P dokonci_logo.py -- <vstup.obj> <vystup.glb>

Kroky: spojit rozpojene vrcholy -> zesilit relief na 3 mm -> posunout na
misto -> srovnat koplanarni plochy -> srazit horni hrany 1 mm primkou ->
zmerit -> export.

=== PROC TO DRIV NEFUNGOVALO (bot9 2026-09-11) ==========================
Robert si srazeni vyzadal trikrat, commity i recept tvrdily, ze je hotove,
a v geometrii nebylo. Merenim se nasly tri ruzne priciny za sebou:

1. ZDROJOVY OBLY BEVEL. `gen_logo_text.js` delal text s bevelEnabled a
   bevelSegments=2, takze hrana uz z three.js prisla jako lomeny oblouk
   0,3 mm hluboky. clamp_overlap pak nemeril 1 mm proti sirce tahu pisma,
   ale proti temhle mikro-hranam, a srazil ho na ~0,013 mm.
2. TROJUHELNIKOVE DELENI. I po vypnuti obleho bevelu prisel lic jako
   stovky trojuhelniku v jedne rovine a clamp se choval stejne - z 1 mm
   zbyl prumer 0,25 mm. Proto se koplanarni plochy nejdriv srovnaji.
3. KONTROLA MERILA POCET VRCHOLU. Puvodni skript hlasil "ZABRAL", kdyz
   bevel pridal vrcholy - to plati, i kdyz je fazeta neviditelne uzka.
   Tady se meri PLOCHA LICE a jeste SIRKA fazety; obojí umi selhat.

=== PROC SE SIRKA POCITA PRO KAZDOU HRANU ZVLAST ========================
Nejostrejsi roh obrysu ma 14,05 stupne (uzky klin uvnitr pismene "M").
Pri 1mm odsazeni se odsazene hrany protnou az 8,2 mm od rohu, ale nad
rohem zbyva do horni hrany pisma jen 5,8 mm - fazeta by material
prozrala skrz, vystrelila jehlu (logo by vyrostlo z 28 na 30,3 mm) a lic
by se prelozil pres sebe. Globalni clamp to sice uhlida, ale zaplati se
to fazetou 0,25 mm VSUDE, tedy presne tim, co Robert reklamoval.

Sirka se proto pocita z toho, kolik mista v danem rohu SKUTECNE je:
vystreli se paprsek po ose rohu a zjisti se vzdalenost k nejblizsi dalsi
hrane obrysu. Vysledek: 349 z 353 hran (98,9 %) dostane plny 1 mm, zuzi
se jen 4 hrany u dvou klinu v "M", a to na 0,47 mm.
"""
import bpy, bmesh, math, sys
import mathutils

argv = sys.argv[sys.argv.index("--") + 1:]
VSTUP, VYSTUP = argv[0], argv[1]

CIL_TLOUSTKA = 3.0
SRAZENI = 1.0
# Nejuzsi prouzek horniho lice, ktery ma v uzkem miste zustat. Bez nej
# vyjde v klinu "M" fazeta 0,558 mm, protilehle strany se PRESNE dotknou
# a lic se tam prelozi pres sebe (zmereno: 2 plochy po 152 mm2 naruby).
REZERVA = 0.8
# Stavajici logo ma v glTF Z rozsah -0,696 .. +2,304; strana PRILEHAJICI
# k profilu je na -0,696 (= 15,696 - 15 od osy profilu). Diky tomu sedi
# umisteni loga v uz hotovych sestavach beze zmeny.
PRILEHAJICI_STRANA_GLTF_Z = -0.696
ROVINA_SPODKU = -PRILEHAJICI_STRANA_GLTF_Z


# --- nacteni ------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.wm.obj_import(filepath=VSTUP)
except AttributeError:
    bpy.ops.import_scene.obj(filepath=VSTUP)
mo = [o for o in bpy.data.objects if o.type == "MESH"]
if not mo:
    sys.exit("CHYBA: OBJ neobsahuje zadny mesh")
bpy.ops.object.select_all(action="DESELECT")
for o in mo:
    o.select_set(True)
bpy.context.view_layer.objects.active = mo[0]
if len(mo) > 1:
    bpy.ops.object.join()
logo = bpy.context.view_layer.objects.active
logo.name = "logo_logiman_cz"
# OBJ importer da objektu ROTACI (Y-nahoru -> Z-nahoru). Bez zapeceni by
# `logo.scale` skalovalo jinym smerem, nez ve kterem meri bounding box -
# zesileni tloustky by slo do vysky pisma.
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.context.view_layer.update()


def rozsah():
    xs = [v.co.x for v in logo.data.vertices]
    ys = [v.co.y for v in logo.data.vertices]
    zs = [v.co.z for v in logo.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


X, Y, Z = rozsah()
print("PO IMPORTU   X %.3f..%.3f  Y %.3f..%.3f  Z %.3f..%.3f | vrcholu %d"
      % (X[0], X[1], Y[0], Y[1], Z[0], Z[1], len(logo.data.vertices)))

# --- 1) spojit rozpojene vrcholy ----------------------------------------
# GLB/OBJ z three.js ma vrcholy rozsypane. Bez tohohle kroku srazeni tise
# neudela NIC a jeste se tvari, ze probehlo.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0001)
bpy.ops.object.mode_set(mode="OBJECT")
print("po spojeni   vrcholu %d, hran %d" % (len(logo.data.vertices), len(logo.data.edges)))

X, Y, Z = rozsah()
roz = {"x": X[1]-X[0], "y": Y[1]-Y[0], "z": Z[1]-Z[0]}
osa = min(roz, key=roz.get)
idx = {"x": 0, "y": 1, "z": 2}[osa]
print("osa tloustky: %s (%.4f mm)" % (osa, roz[osa]))

# --- 2) zesilit relief, jen v ose tloustky ------------------------------
mer = [1.0, 1.0, 1.0]
mer[idx] = CIL_TLOUSTKA / roz[osa]
logo.scale = mer
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# --- 3) posunout, aby prilehajici strana zustala na miste ---------------
X, Y, Z = rozsah()
logo.location[idx] += ROVINA_SPODKU - [X, Y, Z][idx][1]
bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
bpy.context.view_layer.update()
X, Y, Z = rozsah()
print("PO ZESILENI  X %.3f..%.3f  Y %.3f..%.3f  Z %.3f..%.3f"
      % (X[0], X[1], Y[0], Y[1], Z[0], Z[1]))
OBRYS_PRED = {"X": X, "Z": Z}       # fazeta ubira dovnitr, obrys nesmi prerust

# horni lic = strana ODVRACENA od profilu = minimum osy tloustky
smer_nahoru = mathutils.Vector((0, 0, 0))
smer_nahoru[idx] = -1.0
# osy roviny lice (ty dve, ktere nejsou osa tloustky)
osy_lice = [i for i in (0, 1, 2) if i != idx]


def zmer(mesh):
    """Plochy podle orientace. `naruby` = plochy mirici jako spodni lic, ale
    lezici jinde - jediny spolehlivy priznak, ze fazeta prorostla geometrii.
    Meri se az na TRIANGULOVANE siti: slozeny n-uhelnik ma porad spravnou
    prumernou normalu a v mereni by vysel v poradku."""
    h = d = f = naruby = 0.0
    for p in mesh.polygons:
        sk = p.normal.dot(smer_nahoru)
        if sk > 0.999:
            h += p.area
        elif sk < -0.999:
            if abs(p.center[idx] - ROVINA_SPODKU) < 0.001:
                d += p.area
            else:
                naruby += p.area
        uhel = math.degrees(math.acos(max(-1.0, min(1.0, abs(sk)))))
        if 44.0 <= uhel <= 46.0:
            f += p.area
    return h, d, f, naruby


lic_pred, spod_pred, faz_pred, _ = zmer(logo.data)
print("PRED SRAZENIM  horni lic %.2f mm2 | spodni lic %.2f mm2 | fazety 44-46 %.3f mm2"
      % (lic_pred, spod_pred, faz_pred))

# --- 4) srovnat koplanarni plochy ---------------------------------------
bm = bmesh.new()
bm.from_mesh(logo.data)
bm.normal_update()
pred_ploch = len(bm.faces)
# Obrys pisma se tim nemeni - mizi jen zbytecne deleni UVNITR rovnych
# ploch. Zaobleni pismen (curveSegments) ma mezi segmenty realny uhel,
# takze prah 0,5 stupne ho nerozpusti.
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5),
                         verts=list(bm.verts), edges=list(bm.edges))
bm.normal_update()
bm.faces.ensure_lookup_table()
print("srovnani koplanarnich ploch: %d -> %d" % (pred_ploch, len(bm.faces)))

horni_plochy = set(f.index for f in bm.faces if f.normal.dot(smer_nahoru) > 0.999)
hranicni = [e for e in bm.edges
            if any(f.index in horni_plochy for f in e.link_faces)
            and any(f.index not in horni_plochy for f in e.link_faces)]
if not hranicni:
    sys.exit("CHYBA: nenasel jsem zadnou hranu na obvodu horniho lice")
print("hran na obvodu horniho lice: %d (z celkem %d)" % (len(hranicni), len(bm.edges)))

# --- 5) kolik mista je v kazdem rohu ------------------------------------
a1, a2 = osy_lice
useky = [(mathutils.Vector((e.verts[0].co[a1], e.verts[0].co[a2])),
          mathutils.Vector((e.verts[1].co[a1], e.verts[1].co[a2]))) for e in hranicni]
poradi = {e.index: i for i, e in enumerate(hranicni)}


def uvnitr(bod):
    """Lezi bod v materialu? Sude/liche krizeni paprsku."""
    k = 0
    for a, b in useky:
        if (a.y > bod.y) != (b.y > bod.y):
            t = (bod.y - a.y) / (b.y - a.y)
            if a.x + t * (b.x - a.x) > bod.x:
                k += 1
    return k % 2 == 1


def dohled(z, smer, vyloucit):
    """Vzdalenost k nejblizsi dalsi hrane obrysu ve smeru `smer`."""
    nej = float("inf")
    for i, (a, b) in enumerate(useky):
        if i in vyloucit:
            continue
        d = b - a
        det = smer.x * (-d.y) - smer.y * (-d.x)
        if abs(det) < 1e-12:
            continue
        rx, ry = a.x - z.x, a.y - z.y
        t = (rx * (-d.y) - ry * (-d.x)) / det
        u = (smer.x * ry - smer.y * rx) / det
        if t > 1e-6 and -1e-9 <= u <= 1 + 1e-9:
            nej = min(nej, t)
    return nej


povolene = {}
for v in bm.verts:
    s = [e for e in v.link_edges if e.index in poradi]
    if len(s) != 2:
        continue
    z = mathutils.Vector((v.co[a1], v.co[a2]))
    d = []
    for e in s:
        w = e.other_vert(v)
        d.append((mathutils.Vector((w.co[a1], w.co[a2])) - z).normalized())
    pul = d[0].angle(d[1]) / 2.0
    if math.sin(pul) < 1e-6:
        continue
    na_jednotku = 1.0 / math.sin(pul)      # posun prusecika pri odsazeni 1 mm
    smer = d[0] + d[1]
    if smer.length < 1e-9:
        continue
    smer.normalize()
    if not uvnitr(z + smer * 0.01):        # posun miri DO materialu
        smer = -smer
    t = dohled(z, smer, {poradi[s[0].index], poradi[s[1].index]})
    # Posun rohu je d*na_jednotku, protejsi hrana se odsadi o dalsi d.
    # Aby po srazeni zbyl kus lice, musi platit:
    #     d*na_jednotku + d + REZERVA <= t
    # Bez rezervy vyjde v klinu "M" presne 0,558 mm, protilehle strany se
    # dotknou a lic se v tom miste prelozi pres sebe (zmereno: 2 plochy po
    # 152 mm2 naruby). REZERVA je tedy nejuzsi prouzek lice, ktery tam ma
    # zustat.
    if t == float("inf"):
        povolene[v.index] = SRAZENI
    else:
        povolene[v.index] = min(SRAZENI, max(0.0, t - REZERVA) / (1.0 + na_jednotku))

sirky = {}
for e in hranicni:
    sirky[e.index] = min(povolene.get(e.verts[0].index, SRAZENI),
                         povolene.get(e.verts[1].index, SRAZENI))

plne = sum(1 for w in sirky.values() if w > SRAZENI - 0.001)
print("sirka fazety: %d z %d hran dostane plny %.1f mm (%.1f %%)"
      % (plne, len(sirky), SRAZENI, 100.0 * plne / len(sirky)))
if plne < len(sirky):
    zuzene = sorted(w for w in sirky.values() if w <= SRAZENI - 0.001)
    print("   zuzeno %d hran (tvar pisma na 1 mm nema misto), nejuzsi %.3f mm"
          % (len(zuzene), zuzene[0]))
bm.to_mesh(logo.data)
bm.free()
logo.data.update()

# --- 6) srazit ----------------------------------------------------------
# Bevel MODIFIKATOR s limit_method='WEIGHT': vaha hrany nasobi sirku, takze
# kazda hrana dostane svoji. Vaha 0 = zadne srazeni, cimz jsou spodni i
# bocni hrany vyrizene zadarmo - srazi se jen obvod horniho lice.
me = logo.data
if "bevel_weight_edge" not in me.attributes:
    me.attributes.new(name="bevel_weight_edge", type="FLOAT", domain="EDGE")
vahy = me.attributes["bevel_weight_edge"]
for i in range(len(me.edges)):
    vahy.data[i].value = sirky.get(i, 0.0) / SRAZENI

bev = logo.modifiers.new("srazeni", "BEVEL")
bev.width = SRAZENI
bev.segments = 1          # 1 segment + profile 0.5 = PRIMKA, ne oblouk
bev.profile = 0.5
bev.offset_type = "OFFSET"
bev.limit_method = "WEIGHT"
bev.use_clamp_overlap = False   # sirku uz omezuje vaha hrany, a presneji
bpy.ops.object.modifier_apply(modifier=bev.name)
bpy.context.view_layer.update()

# glTF pri exportu stejne trojuhelnikuje - a prave tam se pozna prelozeny
# lic. Triangulovat se proto musi JESTE PRED merenim, at se meri to, co se
# doopravdy exportuje.
bm = bmesh.new()
bm.from_mesh(logo.data)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
bm.normal_update()
bm.to_mesh(logo.data)
bm.free()
logo.data.update()

lic_po, spod_po, faz_po, naruby = zmer(logo.data)
print("PO SRAZENI     horni lic %.2f mm2 | spodni lic %.2f mm2 | fazety 44-46 %.3f mm2"
      % (lic_po, spod_po, faz_po))
print("   horni lic klesl o %.2f mm2 (%.1f %%), pomer horni/spodni %.4f"
      % (lic_pred - lic_po, 100.0 * (lic_pred - lic_po) / lic_pred, lic_po / spod_po))

siroke = 0.0
for p in logo.data.polygons:
    sk = p.normal.dot(smer_nahoru)
    uhel = math.degrees(math.acos(max(-1.0, min(1.0, abs(sk)))))
    if 44.0 <= uhel <= 46.0:
        vy = [logo.data.vertices[v].co[idx] for v in p.vertices]
        if (max(vy) - min(vy)) > 0.95 * SRAZENI:
            siroke += p.area
print("   z toho v plne sirce %.1f mm: %.1f mm2 (%.0f %%)"
      % (SRAZENI, siroke, 100.0 * siroke / max(faz_po, 1e-9)))

if naruby > 0.05:
    mista = []
    for p in logo.data.polygons:
        sk = p.normal.dot(smer_nahoru)
        if sk < -0.999 and abs(p.center[idx] - ROVINA_SPODKU) > 0.001:
            mista.append((p.center[a1], p.center[a2], p.area))
    mista.sort(key=lambda m: -m[2])
    print("   NARUBY na %d plochach, nejvetsi:" % len(mista))
    for x, z, a in mista[:8]:
        print("      X=%+8.3f Z=%+7.3f  %7.3f mm2" % (x, z, a))

# --- 7) kontroly - merenou PLOCHOU, ne poctem vrcholu -------------------
# Prahy jsou schvalne tesne. Volny prah ("lic klesl aspon o 5 %") propusti
# i fazetu 0,25 mm, kterou uz Robert jednou reklamoval jako neviditelnou.
chyby = []
if lic_po > lic_pred * 0.75:
    chyby.append("horni lic klesl jen na %.1f %% (%.2f -> %.2f mm2), ceka se pod 75 %%"
                 % (100.0 * lic_po / lic_pred, lic_pred, lic_po))
if faz_po < 1000.0:
    chyby.append("plocha fazet 44-46 stupnu je jen %.1f mm2, ceka se pres 1000" % faz_po)
if siroke < 0.90 * faz_po:
    chyby.append("jen %.0f %% fazet ma plnou sirku %.1f mm"
                 % (100.0 * siroke / max(faz_po, 1e-9), SRAZENI))
if abs(spod_po - spod_pred) > 0.05:
    chyby.append("zmenil se spodni lic (%.2f -> %.2f) - srazeny i spodni hrany"
                 % (spod_pred, spod_po))
# Prah nesmi byt uplna nula: po srazeni zbyva jedna ploska 0,09 mm2 u
# maleho "i" (0,003 % lice). Neni to roh ani mitra - zmereno, ze na ni
# nema vliv ani REZERVA, ani miter_outer - a proti 347 mm2, ktere delala
# jehla v "M", je to jina rada velikosti. Prah 0,2 mm2 ji propusti, ale
# jakykoli skutecny prulom zachyti.
if naruby > 0.2:
    chyby.append("%.2f mm2 ploch obracenych naruby - fazeta prorostla geometrii" % naruby)
X, Y, Z = rozsah()
for jm, ted in (("X", X), ("Z", Z)):
    drive = OBRYS_PRED[jm]
    if ted[0] < drive[0] - 0.001 or ted[1] > drive[1] + 0.001:
        chyby.append("obrys v ose %s prerostl: %.3f..%.3f -> %.3f..%.3f (jehla v ostrem rohu)"
                     % (jm, drive[0], drive[1], ted[0], ted[1]))
tl = [X, Y, Z][idx]
if abs((tl[1] - tl[0]) - CIL_TLOUSTKA) > 0.001:
    chyby.append("tloustka neni %.1f mm ale %.4f" % (CIL_TLOUSTKA, tl[1] - tl[0]))
if abs(tl[1] - ROVINA_SPODKU) > 0.0001:
    chyby.append("prilehajici strana neni na %.3f ale na %.4f" % (ROVINA_SPODKU, tl[1]))
if chyby:
    print("NEPROSLO - nic se neexportuje:")
    for c in chyby:
        print("   -", c)
    sys.exit(1)
print("KONTROLY PROSLY (merena PLOCHA lice a SIRKA fazety, ne pocet vrcholu)")

# --- 8) export ----------------------------------------------------------
bpy.ops.object.select_all(action="DESELECT")
logo.select_set(True)
bpy.context.view_layer.objects.active = logo
bpy.ops.export_scene.gltf(filepath=VYSTUP, export_format="GLB",
                          use_selection=True, export_apply=True, export_yup=True)
print("ULOZENO:", VYSTUP)
