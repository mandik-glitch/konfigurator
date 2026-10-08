"""extrahuj_svetla.py - vypise svetla z .blend souboru jako JSON (bezi UVNITR
Blenderu, soubor jen cte, nic neuklada). Robert 2026-09-29: "v renderovaci
tabulce chci pridat nastaveni svetel, podle nejakeho souboru" (X1_SCENA.blend).

    blender -b --factory-startup <soubor.blend> -P extrahuj_svetla.py

Vystup: jediny radek `SVETLA_JSON|{...}` na stdout. Barva a vykon jsou to,
co Blender skutecne vyzari (Light.color x energy x 2^exposure x Emission uzel);
svetla s nulovym vykonem jdou do "preskoceno". Poloha a natoceni jsou
ve SVETOVYCH souradnicich souboru (matrix_world - funguje i pro svetla
s rodicem), kamera souboru slouzi jen jako smer pohledu (azimut), podle
ktereho se svetla pri renderu otaci spolu s kamerou.
"""
import json
import math

import bpy

sc = bpy.context.scene
ve_view_layer = set(bpy.context.view_layer.objects.keys())

# kolekce vypnuta pro render (i nadrazenou) svetlo nerenderuje
skryte_kolekce = set()


def _projdi(lc, skryto):
    skryto = skryto or lc.collection.hide_render
    if skryto:
        skryte_kolekce.add(lc.collection.name)
    for dite in lc.children:
        _projdi(dite, skryto)


_projdi(bpy.context.view_layer.layer_collection, False)


def vyzareni(ld):
    """(barva rgb, sila nasobek, stav) - to, co Blender opravdu vyzari:
    Light.color x energy x 2^exposure x Emission uzel ve svetelnem node stromu
    (barva a sila Emission se nasobi). Stav: 'zadne' (bez uzlu), 'emission',
    'slozite' (uzel neni Emission nebo ma napojeny vstup - vezmou se jen
    vychozi hodnoty, vysledek nemusi sedet)."""
    barva = [c for c in ld.color]
    sila = ld.energy * (2.0 ** getattr(ld, "exposure", 0.0))
    stav = "zadne"
    nt = getattr(ld, "node_tree", None)
    if getattr(ld, "use_nodes", False) and nt is not None:
        vystup = None
        for n in nt.nodes:
            if n.bl_idname == "ShaderNodeOutputLight":
                if vystup is None or n.is_active_output:
                    vystup = n
        zdroj = None
        if vystup is not None and vystup.inputs[0].is_linked:
            zdroj = vystup.inputs[0].links[0].from_node
        if zdroj is not None and zdroj.bl_idname == "ShaderNodeEmission":
            stav = "emission"
            if zdroj.inputs["Color"].is_linked or zdroj.inputs["Strength"].is_linked:
                stav = "slozite"
            ec = zdroj.inputs["Color"].default_value
            barva = [barva[i] * ec[i] for i in range(3)]
            sila *= zdroj.inputs["Strength"].default_value
        elif zdroj is not None:
            stav = "slozite"
    return barva, sila, stav


svetla = []
preskoceno = []
for o in sc.objects:
    if o.type != "LIGHT" or o.hide_render or o.name not in ve_view_layer:
        continue
    if o.users_collection and all(c.name in skryte_kolekce for c in o.users_collection):
        continue
    ld = o.data
    barva, sila, stav = vyzareni(ld)
    if sila <= 0.0 or max(barva) <= 0.0:
        preskoceno.append({"jmeno": o.name, "duvod": "nulovy vykon nebo cerna barva"})
        continue
    mw = o.matrix_world
    sc3 = mw.to_scale()
    d = {
        "jmeno": o.name,
        "typ": ld.type,
        "barva": [round(c, 5) for c in barva],
        "vykon": sila,
        "uzly": stav,
        "poloha": [round(c, 6) for c in mw.translation],
        "rot": [[round(c, 6) for c in radek] for radek in mw.to_3x3().normalized()],
        "meritko": (abs(sc3.x) + abs(sc3.y) + abs(sc3.z)) / 3.0,
        "diffuse": ld.diffuse_factor,
        "specular": ld.specular_factor,
        "stiny": bool(ld.use_shadow),
    }
    if getattr(ld, "use_temperature", False):
        d["teplota"] = ld.temperature
    if ld.type in {"POINT", "SPOT"}:
        d["polomer"] = ld.shadow_soft_size
    if ld.type == "SPOT":
        d["spot_uhel"] = ld.spot_size
        d["spot_blend"] = ld.spot_blend
    if ld.type == "AREA":
        d["tvar"] = ld.shape
        d["velikost"] = ld.size
        d["velikost_y"] = ld.size_y
    if ld.type == "SUN":
        d["uhel"] = ld.angle
    svetla.append(d)

kamera_az = None
if sc.camera is not None:
    t = sc.camera.matrix_world.translation
    if abs(t.x) + abs(t.y) > 1e-6:
        kamera_az = math.degrees(math.atan2(t.y, t.x))

print("SVETLA_JSON|" + json.dumps({"verze": 2, "svetla": svetla, "preskoceno": preskoceno,
                                   "kamera_azimut_deg": kamera_az}))
