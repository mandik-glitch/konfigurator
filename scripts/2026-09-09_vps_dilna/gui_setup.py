"""gui_setup.py - DILNA: GUI Blender na VPS (bot8, 2026-09-09).

Robert: "moje dilna Blender je tam nato aby se to nastaveni renderu vzalo
odtud". Scena v tomhle Blenderu je ZDROJ vzhledu vsech produktovych
renderu.

Jak to funguje:
  * kazdych 10 s se ulozi snapshot do vps_dilna.blend
  * kazda renderovaci uloha ho bere jako sablonu automaticky
    (scripts/2026-09-09_turntable_render.py)
  * cokoli Robert ve scene zmeni, se projevi na dalsim renderu samo

DILNA JE TRVALA. Robert 2026-09-09: "ty menis nastaveni renderu v moji
dilne?" - drive se scena stavela ZNOVU pri kazdem restartu, takze kazda
oprava prepsala jeho praci. Nove: existuje-li vps_dilna.blend, jen se
OTEVRE. Od nuly se stavi jen poprve.

PRAVIDLO (Robert 2026-09-09): "zadny bot nemuze menit nastaveni na VPS
v Blenderu dokud to admin nepovoli". Tenhle skript proto na EXISTUJICI
dilnu NESAHA - nemeni engine, vzorky, svetla, world, materialy ani
viewport. Dela jen dve veci:
  * cte scenu a uklada snapshot (autosave)
  * ZABALUJE obrazky do souboru (img.pack())
Baleni je jedina vyjimka a je technicka, ne vzhledova: bez nej render na
Robertove Windows PC nenajde HDRi a vyjde fialovy. Vzhled nemeni.
Od nuly se scena stavi JEN kdyz vps_dilna.blend jeste neexistuje.

PASTI (kazda uz jednou stala cas):
 1. Obrazky se MUSI zabalit do souboru. Sablona jde na Robertuv Windows
    PC, kde cesty z VPS neexistuji - nezabalene HDRi = FIALOVY render.
 2. bpy.context.active_object pri startu pres --python neexistuje;
    mesh podlahy se stavi z dat, ne operatorem.
 3. Scena je v MILIMETRECH (regal pres 2000 jednotek) - bez zvednuti
    clip_end je za orezovou rovinou ve vsech layoutech.
 4. Skript nesmi zaviset na souboru v uklizenem adresari (drive nacital
    gui_doblo_a.glb, ten zmizel a Robert koukal 3 h na prazdnou scenu).
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Quaternion, Vector

OUT = "/opt/konfigurator/private-files/blender-renders"
JOB = os.path.join(OUT, "dilna_job.json")
SAVE_TO = os.path.join(OUT, "vps_dilna.blend")
HDRI = "/opt/konfigurator/private-files/shared-drive-named/Rendering/HDRi/studio_small_08_4k.exr"
INTERVAL_S = 10.0

C = Matrix.Rotation(math.radians(90.0), 4, "X")
C_INV = C.inverted()

# POZOR: dilna se NESMI otvirat pres bpy.ops.wm.open_mainfile() TADY.
# Nacteni souboru za behu skriptu v Blenderu UKONCI zbytek skriptu -
# casovace se pak nezaregistruji, autosave nebezi a Robertovy zmeny se
# do renderu nikdy nedostanou (chyceno 2026-09-09: sablona stala
# 10 minut na stejnem case, i kdyz Blender bezel).
# Soubor se proto predava Blenderu uz na prikazove radce
# (start_dilna.sh) a tady se jen pozna, jestli uz je nacteny.
JE_NOVA = not bpy.data.filepath
if JE_NOVA:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print("DILNA: prvni spusteni - stavim od nuly")
else:
    print("DILNA: nactena ulozena dilna (%s), nesaham na ni" % bpy.data.filepath)
sc = bpy.context.scene
if JE_NOVA:
    sc.render.engine = "CYCLES"


def _import_sestavy():
    """Sestava z job JSONu - stejny prevod souradnic jako
    api/blender_render_turntable.py (prohlizec Y-nahoru -> Blender
    Z-nahoru, konjugace C @ M @ C^-1)."""
    try:
        with open(JOB, encoding="utf-8") as fh:
            job = json.load(fh)
    except (OSError, ValueError):
        print("DILNA: job JSON nenalezen, scena zustane prazdna")
        return []
    out = []
    for part in job.get("parts") or []:
        if not os.path.exists(part.get("glb") or ""):
            continue
        before = set(sc.objects)
        try:
            bpy.ops.import_scene.gltf(filepath=part["glb"])
        except Exception as e:
            print("DILNA: import %s selhal: %r" % (part.get("part_id"), e))
            continue
        new = [o for o in sc.objects if o not in before]
        q, p, s = part["quaternion"], part["position"], part["scale"]
        quat = Quaternion((float(q[3]), float(q[0]), float(q[1]), float(q[2])))
        M = (C @ (Matrix.Translation(Vector((float(p[0]), float(p[1]), float(p[2]))))
                  @ quat.to_matrix().to_4x4()
                  @ Matrix.Diagonal(Vector((float(s[0]), float(s[1]), float(s[2]), 1.0)))) @ C_INV)
        for r in [o for o in new if o.parent is None]:
            r.matrix_world = M @ r.matrix_world
        for o in new:
            if o.type == "MESH":
                for poly in o.data.polygons:
                    poly.use_smooth = False   # ostre hrany profilu
                out.append(o)
    return out


def _bbox(objs):
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for o in objs:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for i in range(3):
                mn[i] = min(mn[i], w[i])
                mx[i] = max(mx[i], w[i])
    if not objs:
        return Vector((0, 0, 0)), Vector((1000, 1000, 1000))
    return mn, mx


def _postav_studio(objs):
    """Studiovy zaklad PRIMO VE SCENE, ne schovany v kodu rendereru -
    Robert to musi videt a moci prepsat."""
    mn, mx = _bbox(objs)
    center = (mn + mx) / 2.0
    size = mx - mn
    r = max(size.x, size.y, size.z) or 1000.0

    # WORLD: HDRi jako osvetleni, ale NE jako pozadi. Light Path
    # "Is Camera Ray" prepina - kamera vidi cistou plochu, odrazy na
    # hliniku berou plne HDRi.
    world = bpy.data.worlds.new("DILNA_World")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (600, 0)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.location = (400, 0)
    lp = nt.nodes.new("ShaderNodeLightPath"); lp.location = (200, 250)
    bg_env = nt.nodes.new("ShaderNodeBackground"); bg_env.location = (200, 60)
    bg_cam = nt.nodes.new("ShaderNodeBackground"); bg_cam.location = (200, -150)
    bg_cam.inputs["Color"].default_value = (0.88, 0.89, 0.90, 1.0)
    if os.path.exists(HDRI):
        env = nt.nodes.new("ShaderNodeTexEnvironment"); env.location = (-100, 60)
        env.image = bpy.data.images.load(HDRI, check_existing=True)
        env.image.pack()          # past c. 1
        nt.links.new(env.outputs["Color"], bg_env.inputs["Color"])
        print("DILNA: HDRi %s (zabaleno)" % os.path.basename(HDRI))
    else:
        bg_env.inputs["Color"].default_value = (0.6, 0.62, 0.65, 1.0)
        print("DILNA: HDRi nenalezeno, pouzita plocha obloha")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_env.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

    # SVETLA: plosna, ne bodova - hlinik potrebuje SIROKY zdroj, aby se
    # v nem melo co odrazet.
    for name, sx, sy, en, pos in (
            ("DILNA_Key", 1.6, 1.0, 0.020, (-0.8, -0.9, 1.1)),
            ("DILNA_Fill", 1.4, 0.9, 0.006, (1.1, -0.7, 0.4))):
        li = bpy.data.lights.new(name, type="AREA")
        li.shape = "RECTANGLE"
        li.size = r * sx
        li.size_y = r * sy
        li.energy = r * r * en
        ob = bpy.data.objects.new(name, li)
        sc.collection.objects.link(ob)
        ob.location = center + Vector((r * pos[0], r * pos[1], r * pos[2]))
        ob.rotation_euler = (center - ob.location).to_track_quat("-Z", "Y").to_euler()

    # PODLAHA: nativni Cycles shadow catcher. Jmeno TT_FLOOR je KONTRAKT -
    # renderer ji pozna a jen posune pod sestavu. Stavi se z dat, ne
    # operatorem (past c. 2).
    h = r * 3.0
    me = bpy.data.meshes.new("TT_FLOOR")
    me.from_pydata([(-h, -h, 0.0), (h, -h, 0.0), (h, h, 0.0), (-h, h, 0.0)], [], [(0, 1, 2, 3)])
    me.update()
    floor = bpy.data.objects.new("TT_FLOOR", me)
    sc.collection.objects.link(floor)
    floor.location = (center.x, center.y, mn.z)
    floor.is_shadow_catcher = True

    sc.cycles.samples = 256          # 4096 z vyroby = 300 s na snimek
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    print("DILNA: studio postaveno (r=%.0f mm, 256 vzorku, AgX)" % r)


if JE_NOVA:
    imported = _import_sestavy()
    print("DILNA: naimportovano %d mesh objektu" % len(imported))
    _postav_studio(imported)
else:
    print("DILNA: %d mesh objektu, studio uz ve scene je"
          % len([o for o in sc.objects if o.type == "MESH"]))


def _zabal_obrazky():
    """Kazdy obrazek musi byt ZABALENY, ne odkaz na cestu - sablona jde na
    Windows PC, kde cesty z VPS neexistuji (past c. 1). Bezi pri kazdem
    autosave, takze se zabali i to, co si Robert nacte sam."""
    for img in bpy.data.images:
        if img.packed_file or img.source not in {"FILE", "SEQUENCE"} or not img.filepath:
            continue
        try:
            img.pack()
            print("DILNA: zabalen obrazek %s" % img.name)
        except Exception as e:
            print("DILNA: %s nelze zabalit (%r) - render s nim zfialovi" % (img.name, e))


def _autosave():
    _zabal_obrazky()
    try:
        tmp = SAVE_TO + ".tmp.blend"
        bpy.ops.wm.save_as_mainfile(filepath=tmp, copy=True, compress=True)
        os.replace(tmp, SAVE_TO)
        try:
            os.chmod(SAVE_TO, 0o644)
        except OSError:
            pass
    except Exception as e:
        print("DILNA: autosave selhal: %r" % e)
    return INTERVAL_S


def _nastav_pohled():
    """Scena je v MILIMETRECH - bez zvednuti clip_end je regal za orezovou
    rovinou (past c. 3). Ve VSECH layoutech, jinak by po prepnuti zalozky
    zmizel."""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.clip_start = 10.0
                    space.clip_end = 1000000.0
                    space.shading.type = "MATERIAL"
    done = False
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "WINDOW":
                    try:
                        with bpy.context.temp_override(window=win, area=area, region=region):
                            bpy.ops.view3d.view_all(center=True)
                        done = True
                    except Exception as e:
                        print("DILNA: zabrat pohled se nepovedlo: %r" % e)
    if done:
        print("DILNA: pohled zabran, orez 10..1000000")
        return None
    return 1.0


# Robert 2026-09-09 ("proc se nerendovalo to co mam ve scene v dilne?" -
# podruhe, po diagnoze bot8): Blender pri KAZDEM otevreni souboru
# (File > Open, tedy i kdyz si Robert v dilne otevre svuj vlastni .blend)
# ZAHODI vsechny registrovane casovace, ktere nejsou persistent. Autosave
# tim tise umrel presne ve chvili, kdy Robert otevrel X30-1.blend
# (14:50:24) - posledni zapis do sablony byl 14:50:06 a dalsich 16 minut
# jeho prace uz do sablony nesla. Navenek to vypada, ze render ignoruje
# jeho nastaveni; ve skutecnosti render dostaval stary otisk scény.
#
# Reseni ma DVE casti, obe nutne:
#   1) persistent=True   - casovac prezije nacteni jineho souboru
#   2) load_post handler - pojistka: po kazdem nacteni ho radeji
#      zaregistrujeme znovu (persistent sam o sobe casovac po load_post
#      nenahazuje, pokud uz mezitim vypadl)
# AUTOSAVE VYPNUT (Robert 2026-09-09: "nepotrebujeme tam autosave, je to
# k nicemu" + "autosave vypni"). Duvod je vecny, ne technicky: v Blenderu
# se nic netvori - jen se do nej vkladaji hotove sestavy kvuli renderu
# (Robertovo upresneni tyz den). Periodicke prepisovani .blend souboru
# tim, co je zrovna v GUI, tedy nema co zachytavat a jen Robertovi
# prepisovalo scenu pod rukama.
#
# Funkce _autosave()/_zabal_obrazky() zustavaji v souboru zamerne
# NEZAREGISTROVANE - zabaleni obrazku se muze hodit volat jednorazove
# (soberstacnost sablony pro vzdalene GPU), ale uz NIKDY periodicky.
# Soubor uklada vyhradne Robert sam (File > Save).
if JE_NOVA:
    bpy.app.timers.register(_nastav_pohled, first_interval=2.0)
else:
    print("DILNA: existujici dilna - NESAHAM na nic (pravidlo Roberta 2026-09-09)")
print("DILNA: autosave VYPNUT (Robert 2026-09-09) - soubor uklada jen Robert sam pres File > Save")
