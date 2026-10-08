"""blender_render_scene.py - headless Blender render sestavy ze sceny.

Robert 2026-08-10 ("zapoj to do sceny, ale chci tam mit plne nastavovani
jako v blenderu") - navazuje na jeho vlastni navrh architektury
(aplikace -> subprocess -> Blender headless -> PNG na disk -> zpet do
aplikace).

Spousti se VYHRADNE pres api/blender_render.py (endpoint
POST /api/admin/blender-render), ktery pripravi vstupni JSON:

    blender -b -noaudio -P api/blender_render_scene.py -- <settings.json>

Cely stav renderu je v tom JSONu (zadne dalsi CLI argumenty) - je jich
moc a JSON jde snadno rozsirovat, aniz by se menilo poradi parametru.

DULEZITE (dve pasti overene v praxi, viz AGENTS_LOG 2026-08-10):
1. Scena je v MILIMETRECH - Blender ma vychozi clip_end kamery 100, coz
   je u sestavy velke 1000+ jednotek "za obzorem" a render vyjde
   PRAZDNY. Clip roviny se proto pocitaji z velikosti sestavy.
2. Katalogove GLB modely NEMAJI UV souradnice - proto se PBR textury
   mapuji BOX projekci primo v Image Texture uzlu (projection='BOX'),
   ktera UV nepotrebuje. Presne tohle v prohlizecovem rendereru
   nefungovalo a muselo se resit rucnim dopoctem UV.
"""
import bpy
import json
import math
import os
import re
import sys
from mathutils import Vector


def load_settings():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not args:
        raise SystemExit("Chybi cesta k settings JSON")
    with open(args[0], "r", encoding="utf-8") as f:
        return json.load(f)


S = load_settings()


def g(key, default=None):
    v = S.get(key)
    return default if v is None else v


# Robert 2026-09-09 ("dej tam jen 2 možnosti blender/cycles a ten
# Luxcore") - viz sekce "render" nize pro plne zduvodneni; potreba uz
# tady, aby ho mohla pouzit i sekce "prostredi" (LuxCore nezna trik s
# ShaderNodeMixShader/LightPath, ktery Cyclesu skryva HDRi z kamery).
_renderer = g("renderer", "cycles")

# ---------------------------------------------------------------- scena
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

bpy.ops.import_scene.gltf(filepath=S["glb_path"])
meshes = [o for o in sc.objects if o.type == "MESH"]
if not meshes:
    raise SystemExit("GLB neobsahuje zadny mesh")

# Robert 2026-08-11 ("rendery by se meli pripojit v online nabidkach
# jako zvlast obrazky ke konkretnimu radku nabidky"): kdyz volajici
# posle only_groups, vyrenderuje se JEN ten jeden radek kusovniku.
# Uzly v GLB se jmenuji bomgrp_<idx> podle skupiny v kusovniku; pri
# duplicitach k nim exporter/importer lepi pripony (_1, .001), proto
# se jmeno parsuje regularnim vyrazem, ne presnou shodou.
only_groups = g("only_groups")
if isinstance(only_groups, (list, tuple)) and only_groups:
    wanted = set()
    for v in only_groups:
        try:
            wanted.add(int(v))
        except (TypeError, ValueError):
            pass
    keep, drop = [], []
    for o in meshes:
        m = re.match(r"^bomgrp_(\d+)", o.name)
        (keep if (m and int(m.group(1)) in wanted) else drop).append(o)
    if keep:  # kdyby jmena nesedela, radeji nechame celou scenu nez prazdny obraz
        for o in drop:
            bpy.data.objects.remove(o, do_unlink=True)
        meshes = keep
        print("Renderuji jen skupiny %s (%d dilu)" % (sorted(wanted), len(keep)))
    else:
        print("VAROVANI: skupiny %s v modelu nenalezeny, renderuji celou scenu" % sorted(wanted))

mins = Vector((1e18, 1e18, 1e18))
maxs = Vector((-1e18, -1e18, -1e18))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        for i in range(3):
            mins[i] = min(mins[i], w[i])
            maxs[i] = max(maxs[i], w[i])
center = (mins + maxs) / 2.0
size = maxs - mins
max_dim = max(size.x, size.y, size.z) or 1.0

# ------------------------------------------------------------- material
tex = g("textures", {})  # {"baseColor": "/cesta", "normal": ..., ...}
mat = bpy.data.materials.new("AluPBR")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")

tile_mm = float(g("texture_tile_mm", 40)) or 40
texcoord = nt.nodes.new("ShaderNodeTexCoord")
mapping = nt.nodes.new("ShaderNodeMapping")
mapping.inputs["Scale"].default_value = (1.0 / tile_mm,) * 3
nt.links.new(mapping.inputs["Vector"], texcoord.outputs["Object"])


def img_node(path, non_color=False):
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(path)
    node.projection = "BOX"  # funguje i BEZ UV souradnic (viz docstring)
    node.projection_blend = float(g("texture_box_blend", 0.3))
    node.extension = "REPEAT"
    if non_color:
        node.image.colorspace_settings.name = "Non-Color"
    nt.links.new(node.inputs["Vector"], mapping.outputs["Vector"])
    return node


if tex.get("baseColor"):
    nt.links.new(bsdf.inputs["Base Color"], img_node(tex["baseColor"]).outputs["Color"])
else:
    _bc = g("base_color", [0.91, 0.92, 0.92])  # zmereny F0 hliniku, viz api/blender_render.py
    bsdf.inputs["Base Color"].default_value = (_bc[0], _bc[1], _bc[2], 1)

if tex.get("roughness"):
    nt.links.new(bsdf.inputs["Roughness"], img_node(tex["roughness"], True).outputs["Color"])
else:
    bsdf.inputs["Roughness"].default_value = float(g("material_roughness", 0.28))

if tex.get("metallic"):
    nt.links.new(bsdf.inputs["Metallic"], img_node(tex["metallic"], True).outputs["Color"])
else:
    bsdf.inputs["Metallic"].default_value = float(g("material_metallic", 1.0))

# Anizotropie (Robert 2026-09-08 "na tohle musí být spousta podkladů na
# internetu" - broušený hliník bez ní vypada matne/mrtve i na cele
# ploche rovne plochy z jakehokoli uhlu: izotropni drsny odraz roztahne
# svetlo rovnomerne do kruhu, takze ve smeru kamery casto neni zadny
# zdroj svetla - ANIZOTROPNI odraz ho natahne do PRUHU podel jedne osy
# (imituje smer broušeni), takze zachyti svetlo z mnohem sirsiho rozsahu
# uhlu a hrany/plochy ziskaji charakteristicke svetle "pruhy" i pri
# celnim pohledu. Tangent RADIAL (osa Z) - profily nemaji UV, takze
# UV_MAP rezim nejde use; RADIAL nepotrebuje UV, jen objektovy prostor.
if "Anisotropic" in bsdf.inputs:
    tan = nt.nodes.new("ShaderNodeTangent")
    tan.direction_type = "RADIAL"
    tan.axis = "Z"
    if "Tangent" in bsdf.inputs:
        nt.links.new(bsdf.inputs["Tangent"], tan.outputs["Tangent"])
    bsdf.inputs["Anisotropic"].default_value = float(g("material_anisotropic", 0.7))
    if "Anisotropic Rotation" in bsdf.inputs:
        bsdf.inputs["Anisotropic Rotation"].default_value = 0.0

# Coat (lak) - plati VZDY, i pri PBR texturach (Robert 2026-08-11:
# "chci mit moznost zmenit texturu a shading nodes").
_coat = float(g("coat_weight", 0.0))
if _coat > 0:
    for _name in ("Coat Weight", "Clearcoat"):  # 4.x vs starsi nazev vstupu
        if _name in bsdf.inputs:
            bsdf.inputs[_name].default_value = _coat
            break

_normal_out = None
if tex.get("normal") and g("use_normal_map", True):
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = float(g("normal_strength", 1.0))
    nt.links.new(nmap.inputs["Color"], img_node(tex["normal"], True).outputs["Color"])
    _normal_out = nmap.outputs["Normal"]

# Robert 2026-08-11 ("chci docilit maximalni realisticke podoby
# renderu"): zaoblene hrany. Skutecny profil nema dokonale ostre hrany -
# ostra CG hrana bez odlesku je nejcitelnejsi znak "pocitacoveho
# obrazku". Bevel shader hrany zaobli JEN pri vypoctu odrazu (geometrie
# se nemeni, zadny dalsi polygon), takze na hranach vzniknou tenke
# svetle odlesky jako na fotce. Scena je v mm => radius primo v mm.
bevel_mm = float(g("bevel_mm", 0.4))
if bevel_mm > 0:
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 6
    bev.inputs["Radius"].default_value = bevel_mm
    if _normal_out is not None:
        nt.links.new(bev.inputs["Normal"], _normal_out)
    nt.links.new(bsdf.inputs["Normal"], bev.outputs["Normal"])
elif _normal_out is not None:
    nt.links.new(bsdf.inputs["Normal"], _normal_out)

# Robert 2026-08-11 ("obarvene predmety budou barevne i v png?"): ANO.
# Driv se VSEM dilum natahl jeden hlinikovy material a barvy z GLB se
# zahodily. Ted se z importovaneho materialu precte puvodni Base Color a
# kdyz je to skutecna barva (saturace) nebo tmavy dil (cerny plast,
# gumove nozky...), dil si ji podrzi - dostane variantu materialu se
# svou barvou (stejna drsnost/kovovost/normal mapa, jen bez hlinikove
# baseColor textury). Neutralne svetle-sede dily = hlinik jako dosud.


def _imported_material_info(o):
    """Vraci (barva, metalness, roughness) z importovaneho materialu, nebo
    (None, None, None) kdyz dil zadny material nema (GLB z katalogu bez
    UV/barvy - viz nize)."""
    for slot_mat in o.data.materials:
        if not slot_mat:
            continue
        if slot_mat.use_nodes:
            b = slot_mat.node_tree.nodes.get("Principled BSDF")
            if b:
                c = b.inputs["Base Color"].default_value
                m = b.inputs["Metallic"].default_value
                r = b.inputs["Roughness"].default_value
                return (float(c[0]), float(c[1]), float(c[2])), float(m), float(r)
        c = slot_mat.diffuse_color
        return (float(c[0]), float(c[1]), float(c[2])), None, None
    return None, None, None


def _keeps_own_color(c, metallic):
    # Robert 2026-09-08 ("pridat realne rozliseni podle layer/produktu"):
    # zivá scéna barvi KAZDY dil pri umisteni (applyPartMaterial ve
    # scene-panels), s metalness 0.6 pro vrstvu "alu" a 0.35 pro vse
    # ostatni (viz webapp/js/scene/hdri-panels-ui.js::materialForLayer) -
    # a exportSceneAsGlb() posle tyhle materialy 1:1 do GLB. Metalness je
    # proto SPOLEHLIVY, primy signal "je to hlinikovy dil?" - puvodni
    # odhad jen z barvy (sytost/tma) eurobox kontejnery a spojky (svetle
    # NEUTRALNI seda, ani syta, ani tmava) mylne priradil hliniku, takze
    # vypadaly jako plech misto plastu. Odhad z barvy zustava JEN
    # zaloha pro dily bez metalness informace (napr. rucne sestavene GLB
    # bez materialu vubec - viz _imported_material_info -> (None, None)).
    if metallic is not None:
        return metallic < 0.5
    if c is None:
        return False
    mx, mn = max(c), min(c)
    saturation = 0.0 if mx <= 0.0 else (mx - mn) / mx
    return saturation > 0.12 or mx < 0.35  # barevny NEBO tmavy dil


_color_variants = {}


def _material_for_color(c, metallic, roughness):
    key = (round(c[0], 2), round(c[1], 2), round(c[2], 2),
           round(metallic, 2) if metallic is not None else -1,
           round(roughness, 2) if roughness is not None else -1)
    if key not in _color_variants:
        vm = mat.copy()
        vm.name = "AluPBR_barva_%s" % (len(_color_variants) + 1)
        vb = vm.node_tree.nodes.get("Principled BSDF")
        for lk in list(vb.inputs["Base Color"].links):
            vm.node_tree.links.remove(lk)  # odpojit hlinikovou baseColor texturu
        vb.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
        if metallic is not None:
            vb.inputs["Metallic"].default_value = metallic  # napr. plast = 0.15, ne 1.0 hliniku
        if roughness is not None:
            for lk in list(vb.inputs["Roughness"].links):
                vm.node_tree.links.remove(lk)  # odpojit hlinikovou roughness texturu
            vb.inputs["Roughness"].default_value = roughness  # ostry plast vs matna guma, ne hlinikova drsnost
        _color_variants[key] = vm
    return _color_variants[key]


_zinc_variants = {}
ZINC_METALLIC_BAND = (0.35, 0.55)  # viz partMaterialMetalness.zinc (webapp/js/scene/catalog-panels.js) = 0.45


def _zinc_cast_material(c, metallic):
    # Robert 2026-09-08 ("tohle stavění GUI nemusíme delat kdyz to umi z
    # blenderu"): zinkovy odlitek (rohove spojky/konzole/patky) nema svou
    # fotografovanou PBR sadu jako hlinik (AluPBR) - misto aby si Robert
    # musel fotit/nahravat texturu na Sdileny disk, postavime "odlitkovy"
    # povrch procedurálně primo v Blender shader nodes (sum -> zrnita
    # variace drsnosti + drobny bump), zadna textura/GUI navic.
    key = (round(c[0], 2), round(c[1], 2), round(c[2], 2))
    if key not in _zinc_variants:
        zm = bpy.data.materials.new("ZincCast_%s" % (len(_zinc_variants) + 1))
        zm.use_nodes = True
        znt = zm.node_tree
        zb = znt.nodes.get("Principled BSDF")
        zb.inputs["Base Color"].default_value = (c[0], c[1], c[2], 1)
        # Zinkovy odlitek je vizualne dost kovovy (i kdyz vstupni signal
        # ze zive sceny je jen 0.45 - schvalne pod hranici "alu" pasma,
        # jen aby sel rozeznat od hliniku pri vyberu materialu vyse).
        zb.inputs["Metallic"].default_value = 0.7
        noise = znt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 60.0
        noise.inputs["Detail"].default_value = 4.0
        ramp = znt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[0].color = (0.28, 0.28, 0.28, 1)
        ramp.color_ramp.elements[1].position = 0.65
        ramp.color_ramp.elements[1].color = (0.5, 0.5, 0.5, 1)
        znt.links.new(ramp.inputs["Fac"], noise.outputs["Fac"])
        znt.links.new(zb.inputs["Roughness"], ramp.outputs["Color"])
        bump = znt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.15
        bump.inputs["Distance"].default_value = 0.15
        znt.links.new(bump.inputs["Height"], noise.outputs["Fac"])
        znt.links.new(zb.inputs["Normal"], bump.outputs["Normal"])
        _zinc_variants[key] = zm
    return _zinc_variants[key]


shade_smooth = bool(g("shade_smooth", False))
for o in meshes:
    own, own_metallic, own_roughness = _imported_material_info(o)
    o.data.materials.clear()
    if own_metallic is not None and ZINC_METALLIC_BAND[0] <= own_metallic < ZINC_METALLIC_BAND[1]:
        chosen = _zinc_cast_material(own or (0.72, 0.74, 0.76), own_metallic)
    elif _keeps_own_color(own, own_metallic):
        chosen = _material_for_color(own, own_metallic, own_roughness)
    else:
        chosen = mat
    o.data.materials.append(chosen)
    for p in o.data.polygons:
        p.use_smooth = shade_smooth

# --------------------------------------------------------------- podlaha
if g("floor_enabled", True):
    bpy.ops.mesh.primitive_plane_add(size=max_dim * 8,
                                     location=(center.x, center.y, mins.z))
    floor = bpy.context.active_object
    fmat = bpy.data.materials.new("Floor")
    fmat.use_nodes = True
    fb = fmat.node_tree.nodes.get("Principled BSDF")
    fc = g("floor_color", [0.35, 0.35, 0.36])
    fb.inputs["Base Color"].default_value = (fc[0], fc[1], fc[2], 1)
    fb.inputs["Roughness"].default_value = float(g("floor_roughness", 0.6))

    # Robert 2026-08-11 ("chci do renderu umistit podlahu jako velkou sit
    # bodu, jen naznakem, v nasem HUD stylu, aby byl obrazek vzdy
    # rozpoznatelny"): procedualni mrizka tecek primo v shaderu podlahy -
    # zadna zmena sceny ani textura, tecky jsou v perspektive a jemne
    # sviti (HUD zelena #2fe07a jako nadpis novinek na webu). Vzor:
    # object souradnice podlahy (mm) -> modulo roztec -> vzdalenost od
    # stredu bunky -> tecka o polomeru floor_dot_radius_mm.
    # Robert 2026-08-11 ("chci vice navrhu, toto je moc huste, zkus neco
    # ve stylu co mame na webu v pozadi"): podlaha muze mit naznakovy
    # vzor v HUD stylu. floor_pattern:
    #   dots  - ridka sit tecek
    #   lines - sikme linky po vzoru pozadi webu (index.html: 45 stupnu,
    #           roztec 126 px, kazda pata v akcentni barve)
    #   grid  - jemna ctvercova mrizka
    #   cross - male krizky v uzlech mrizky
    #   none  - ciste podlaha
    # Vse procedualne v shaderu - zadny objekt navic, zadna textura,
    # vzor drzi perspektivu i stiny.
    _pattern = str(g("floor_pattern", "lines")).lower()
    if _pattern not in ("dots", "lines", "grid", "cross", "none"):
        _pattern = "lines"
    if _pattern != "none":
        fnt = fmat.node_tree
        # 0 = auto podle velikosti sestavy (mala konzole i velky ram)
        spacing = float(g("floor_pattern_spacing_mm", 0) or 0) or max_dim / 5.0
        thick = float(g("floor_pattern_thickness_mm", 0) or 0) or spacing * 0.012
        hud = g("floor_dot_color", [0.18, 0.88, 0.48])          # HUD zelena
        accent = g("floor_accent_color", [1.0, 0.62, 0.20])     # oranzova jako na webu
        every = max(0, int(g("floor_accent_every", 5)))         # kazda N-ta linka; 0 = bez akcentu

        def _new(t, **kw):
            n = fnt.nodes.new(t)
            for k, v in kw.items():
                setattr(n, k, v)
            return n

        def _math(op, a_node=None, a_out=None, b=None, a_val=None):
            n = _new("ShaderNodeMath", operation=op)
            if a_node is not None:
                fnt.links.new(n.inputs[0], a_node.outputs[a_out or "Value"])
            elif a_val is not None:
                n.inputs[0].default_value = a_val
            if b is not None:
                n.inputs[1].default_value = b
            return n

        ftc = _new("ShaderNodeTexCoord")
        fsep = _new("ShaderNodeSeparateXYZ")
        fnt.links.new(fsep.inputs["Vector"], ftc.outputs["Object"])

        def _stripes(axis_nodes):
            """Vrati (maska_linky, maska_akcentu) pro dany smer.
            axis_nodes = uzel s hodnotou souradnice podel normaly pruhu."""
            # posun do kladnych hodnot - modulo na zapornych vraci zaporny zbytek
            u = _math("ADD", a_node=axis_nodes[0], a_out=axis_nodes[1], b=1e6)
            idx_f = _math("DIVIDE", a_node=u, b=spacing)
            idx = _math("FLOOR", a_node=idx_f)
            frac = _new("ShaderNodeMath", operation="SUBTRACT")
            fnt.links.new(frac.inputs[0], idx_f.outputs["Value"])
            fnt.links.new(frac.inputs[1], idx.outputs["Value"])
            line = _math("LESS_THAN", a_node=frac, b=max(0.001, thick / spacing))
            if not every:
                return line, None
            mod = _math("MODULO", a_node=idx, b=float(every))
            is_acc = _math("LESS_THAN", a_node=mod, b=0.5)
            acc = _new("ShaderNodeMath", operation="MULTIPLY")
            fnt.links.new(acc.inputs[0], line.outputs["Value"])
            fnt.links.new(acc.inputs[1], is_acc.outputs["Value"])
            return line, acc

        def _combine(a, b, op="MAXIMUM"):
            if a is None:
                return b
            if b is None:
                return a
            n = _new("ShaderNodeMath", operation=op)
            fnt.links.new(n.inputs[0], a.outputs["Value"])
            fnt.links.new(n.inputs[1], b.outputs["Value"])
            return n

        if _pattern == "dots":
            # vzdalenost od stredu bunky < polomer
            foff = _new("ShaderNodeVectorMath", operation="ADD")
            foff.inputs[1].default_value = (1e6 + spacing / 2.0, 1e6 + spacing / 2.0, 0.0)
            fnt.links.new(foff.inputs[0], ftc.outputs["Object"])
            fmod = _new("ShaderNodeVectorMath", operation="MODULO")
            fmod.inputs[1].default_value = (spacing, spacing, 1e9)
            fnt.links.new(fmod.inputs[0], foff.outputs["Vector"])
            fsub = _new("ShaderNodeVectorMath", operation="SUBTRACT")
            fsub.inputs[1].default_value = (spacing / 2.0, spacing / 2.0, 0.0)
            fnt.links.new(fsub.inputs[0], fmod.outputs["Vector"])
            flen = _new("ShaderNodeVectorMath", operation="LENGTH")
            fnt.links.new(flen.inputs[0], fsub.outputs["Vector"])
            mask = _math("LESS_THAN", a_node=flen, a_out="Value",
                         b=float(g("floor_dot_radius_mm", 0) or 0) or spacing * 0.05)
            acc_mask = None
        elif _pattern == "lines":
            # sikme pruhy 45 stupnu - (x+y)/sqrt(2), presne jako pozadi webu
            xy = _new("ShaderNodeMath", operation="ADD")
            fnt.links.new(xy.inputs[0], fsep.outputs["X"])
            fnt.links.new(xy.inputs[1], fsep.outputs["Y"])
            diag = _math("MULTIPLY", a_node=xy, b=0.70710678)
            mask, acc_mask = _stripes((diag, "Value"))
        else:  # grid / cross
            mx, ax = _stripes((fsep, "X"))
            my, ay = _stripes((fsep, "Y"))
            if _pattern == "grid":
                mask = _combine(mx, my)
                acc_mask = _combine(ax, ay)
            else:  # cross - jen prusecik obou smeru = male krizky v uzlech
                mask = _combine(mx, my, "MULTIPLY")
                acc_mask = _combine(ax, ay, "MULTIPLY")

        mix1 = _new("ShaderNodeMix", data_type="RGBA")
        mix1.inputs["A"].default_value = (fc[0], fc[1], fc[2], 1)
        mix1.inputs["B"].default_value = (hud[0], hud[1], hud[2], 1)
        fnt.links.new(mix1.inputs["Factor"], mask.outputs["Value"])
        if acc_mask is not None:
            mix2 = _new("ShaderNodeMix", data_type="RGBA")
            mix2.inputs["B"].default_value = (accent[0], accent[1], accent[2], 1)
            fnt.links.new(mix2.inputs["A"], mix1.outputs["Result"])
            fnt.links.new(mix2.inputs["Factor"], acc_mask.outputs["Value"])
            col_out = mix2.outputs["Result"]
        else:
            col_out = mix1.outputs["Result"]
        fnt.links.new(fb.inputs["Base Color"], col_out)
        glow = float(g("floor_dot_glow", 0.35))

        # Robert 2026-08-11 ("toto je dobre, ale bez toho sedeho podkladu,
        # nech je to pruchozi a je videt pod rovinu car, s malym
        # zaclonenim toho co je pod rovinou"): rovina podlahy zmizi a
        # zustanou VISET jen samotne cary vzoru. Misto Principled se
        # material prepne na Mix Shader: kde neni cara -> Transparent
        # BSDF (paprsek proleti dal, takze je videt, co je pod rovinou),
        # kde je cara -> svitici Emission. Zacloneni = barva Transparent
        # BSDF pod 1.0, coz vse pod rovinou jemne ztlumi (jako tenka
        # mlha), ale nic neschova.
        if bool(g("floor_see_through", True)):
            dim = max(0.0, min(0.95, float(g("floor_dim", 0.15))))
            transp = _new("ShaderNodeBsdfTransparent")
            transp.inputs["Color"].default_value = (1 - dim, 1 - dim, 1 - dim, 1)
            emis = _new("ShaderNodeEmission")
            emis.inputs["Strength"].default_value = max(0.8, 1.4 + glow)
            fnt.links.new(emis.inputs["Color"], col_out)
            mixsh = _new("ShaderNodeMixShader")
            fnt.links.new(mixsh.inputs[0], mask.outputs["Value"])
            fnt.links.new(mixsh.inputs[1], transp.outputs["BSDF"])
            fnt.links.new(mixsh.inputs[2], emis.outputs["Emission"])
            fout = fnt.nodes.get("Material Output") or _new("ShaderNodeOutputMaterial")
            for lk in list(fout.inputs["Surface"].links):
                fnt.links.remove(lk)
            fnt.links.new(fout.inputs["Surface"], mixsh.outputs["Shader"])
            # cary jsou znacky, ne fyzicky objekt - nesmi vrhat stin
            floor.visible_shadow = False
            # Kov (Metallic 1.0) se dosud "svetlil" odrazem sede podlahy;
            # po jejim zprusvitneni by odrazel jen tmavou spodni pulku
            # HDRI a dily by zcernaly. Neviditelna odrazova rovina pod
            # mrizkou svetlo vraci - kamera ji nevidi (visible_camera =
            # False), takze pozadi zustava ciste a je videt "pod rovinu".
            bpy.ops.mesh.primitive_plane_add(size=max_dim * 12,
                                             location=(center.x, center.y, mins.z - max_dim * 0.002))
            bounce = bpy.context.active_object
            bmat = bpy.data.materials.new("FloorBounce")
            bmat.use_nodes = True
            bb = bmat.node_tree.nodes.get("Principled BSDF")
            _bcol = float(g("floor_bounce", 0.8))
            bb.inputs["Base Color"].default_value = (_bcol, _bcol, _bcol, 1)
            bb.inputs["Roughness"].default_value = 0.65
            bounce.data.materials.append(bmat)
            bounce.visible_camera = False   # kamera vidi pozadi, ne tuhle rovinu
            bounce.visible_shadow = False
        # jemne "sviceni" vzoru, at drzi HUD charakter i ve stinu
        elif glow > 0 and "Emission Strength" in fb.inputs:
            for _emc in ("Emission Color", "Emission"):
                if _emc in fb.inputs:
                    fnt.links.new(fb.inputs[_emc], col_out)
                    break
            fem = _math("MULTIPLY", a_node=mask, b=glow)
            fnt.links.new(fb.inputs["Emission Strength"], fem.outputs["Value"])
    floor.data.materials.append(fmat)

# ------------------------------------------------------------- prostredi
world = bpy.data.worlds.new("W")
sc.world = world
world.use_nodes = True
wnt = world.node_tree
wout = wnt.nodes["World Output"]
bgc = g("background_color", [0.85, 0.86, 0.87])
bgc_top = g("background_color_top", None)


def _make_flat_background_node():
    # Robert 2026-09-09 ("Jde o tu hloubku v pozadí" - ziva scena ma
    # tmave modre pozadi, ktere sviteli k horizontu, ne plochou barvu) -
    # kdyz je zadana i "background_color_top", pozadi neni jedna plocha
    # barva, ale svisly prechod (Gradient Texture ve svetovem prostoru,
    # Z-osa) - stejny vizualni efekt jako fog/atmosfericka hloubka bez
    # skutecne volumetriky. Bez "background_color_top" (nebo kdyz je
    # stejna jako spodni) se chova presne jako drive - jedna plocha barva.
    bg = wnt.nodes.new("ShaderNodeBackground")
    if bgc_top and list(bgc_top) != list(bgc):
        tex_coord = wnt.nodes.new("ShaderNodeTexCoord")
        grad = wnt.nodes.new("ShaderNodeTexGradient")
        grad.gradient_type = "LINEAR"
        wnt.links.new(grad.inputs["Vector"], tex_coord.outputs["Generated"])
        ramp = wnt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (bgc[0], bgc[1], bgc[2], 1)
        ramp.color_ramp.elements[1].color = (bgc_top[0], bgc_top[1], bgc_top[2], 1)
        wnt.links.new(ramp.inputs["Fac"], grad.outputs["Fac"])
        wnt.links.new(bg.inputs["Color"], ramp.outputs["Color"])
    else:
        bg.inputs["Color"].default_value = (bgc[0], bgc[1], bgc[2], 1)
    return bg

hdri_path = g("hdri_path")
if hdri_path:
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri_path)
    # Rotace HDRI kolem svisle osy - LuxCore (BlendLuxCore) neumi prevest
    # Mapping uzel na vstupu Environment Texture (NotImplementedError,
    # overeno 2026-09-09) - HDRi rotace se tam zatim proto nepodporuje,
    # nechame vychozi (nepripojeny Vector = generated souradnice).
    if _renderer != "luxcore":
        env_map = wnt.nodes.new("ShaderNodeMapping")
        env_coord = wnt.nodes.new("ShaderNodeTexCoord")
        env_map.inputs["Rotation"].default_value = (0, 0, math.radians(float(g("hdri_rotation_deg", 0))))
        wnt.links.new(env_map.inputs["Vector"], env_coord.outputs["Generated"])
        wnt.links.new(env.inputs["Vector"], env_map.outputs["Vector"])

    bg_env = wnt.nodes.new("ShaderNodeBackground")
    bg_env.inputs["Strength"].default_value = float(g("hdri_strength", 1.0))
    wnt.links.new(bg_env.inputs["Color"], env.outputs["Color"])

    if g("hdri_as_background", False) or _renderer == "luxcore":
        # LuxCore: BlendLuxCore ("use_cycles_settings") neumi prevest
        # ShaderNodeMixShader/LightPath trik nize (Exception "Unsupported
        # node type" - overeno 2026-09-09) - pouzij proto vzdy primy
        # Background bez skryvani pred kamerou, HDRi tak bude videt i
        # jako pozadi (LuxCore nema jiny zpusob, jak dat kovum odlesky).
        wnt.links.new(wout.inputs["Surface"], bg_env.outputs["Background"])
    else:
        # Light Path trik: kamera vidi jednolite pozadi, ale odrazy a
        # osvetleni berou skutecnou HDRI mapu (Robert: "pozadi nesmi byt
        # aktivni, hdri mapa skryta").
        bg_plain = _make_flat_background_node()
        lp = wnt.nodes.new("ShaderNodeLightPath")
        mix = wnt.nodes.new("ShaderNodeMixShader")
        wnt.links.new(mix.inputs[0], lp.outputs["Is Camera Ray"])
        wnt.links.new(mix.inputs[1], bg_env.outputs["Background"])
        wnt.links.new(mix.inputs[2], bg_plain.outputs["Background"])
        wnt.links.new(wout.inputs["Surface"], mix.outputs["Shader"])
else:
    bg_plain = _make_flat_background_node()
    wnt.links.new(wout.inputs["Surface"], bg_plain.outputs["Background"])

# ---------------------------------------------------------------- svetlo
if g("sun_enabled", True):
    az = math.radians(float(g("sun_azimuth_deg", 45)))
    el = math.radians(float(g("sun_elevation_deg", 50)))
    d = max_dim * 3
    sun_loc = (center.x + d * math.cos(el) * math.cos(az),
               center.y + d * math.cos(el) * math.sin(az),
               center.z + d * math.sin(el))
    bpy.ops.object.light_add(type="SUN", location=sun_loc)
    sun = bpy.context.active_object
    sun.data.energy = float(g("sun_energy", 3.0))
    sun.data.angle = math.radians(float(g("sun_softness_deg", 7.0)))
    look = center - Vector(sun_loc)
    sun.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- kamera
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = float(g("camera_lens_mm", 50))
# Viz docstring, past c. 1 - bez tohohle je model za clip rovinou.
cam_data.clip_start = max(0.001, max_dim * 0.001)
cam_data.clip_end = max_dim * 100
cam = bpy.data.objects.new("Cam", cam_data)
sc.collection.objects.link(cam)
sc.camera = cam

# Robert 2026-08-11 ("ted potrebujeme nas Render cycle dostat do
# nabidky"): kdyz volajici posle KONKRETNI kameru (camera_position +
# camera_target), pouzije se presne ona misto azimut/elevace posuvniku.
# Tim umi Cycles vyrenderovat presne ty dva zabery, ktere uz nabidka
# pouziva pro rastrove nahledy - jinak by fotorealisticky render koukal
# na sestavu odjinud nez zbytek nabidky.
#
# SOURADNICE: prohlizec (three.js) je Y-nahoru, Blender Z-nahoru.
# Importer glTF prevadi (x, y, z) -> (x, -z, y), takze stejny prevod
# musi projit i kamera, jinak by mirila mimo model.
def _gltf_to_blender(v):
    return Vector((float(v[0]), -float(v[2]), float(v[1])))


cam_pos_in = g("camera_position")
cam_tgt_in = g("camera_target")
if (isinstance(cam_pos_in, (list, tuple)) and len(cam_pos_in) == 3
        and isinstance(cam_tgt_in, (list, tuple)) and len(cam_tgt_in) == 3):
    cam.location = _gltf_to_blender(cam_pos_in)
    cam_target = _gltf_to_blender(cam_tgt_in)
    # Zorny uhel z prohlizece (svisly FOV) prebiji ohnisko v mm - jinak
    # by render mel jiny vyrez nez to, co uzivatel videl ve scene.
    fov_deg = float(g("camera_fov_deg", 0) or 0)
    if fov_deg > 0:
        cam_data.sensor_fit = "VERTICAL"
        cam_data.lens = (cam_data.sensor_height / 2.0) / math.tan(math.radians(fov_deg) / 2.0)
else:
    cam_az = math.radians(float(g("camera_azimuth_deg", -50)))
    cam_el = math.radians(float(g("camera_elevation_deg", 25)))
    dist = max_dim * float(g("camera_distance_factor", 2.2))
    cam.location = center + Vector((
        dist * math.cos(cam_el) * math.cos(cam_az),
        dist * math.cos(cam_el) * math.sin(cam_az),
        dist * math.sin(cam_el),
    ))
    cam_target = center
cam.rotation_euler = (cam_target - cam.location).to_track_quat("-Z", "Y").to_euler()

if g("dof_enabled", False):
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = (cam_target - cam.location).length
    cam_data.dof.aperture_fstop = float(g("dof_fstop", 2.8))

# ---------------------------------------------------------------- render
sc.render.resolution_x = int(g("resolution_x", 1100))
sc.render.resolution_y = int(g("resolution_y", 825))
sc.render.resolution_percentage = 100
sc.render.film_transparent = bool(g("transparent_background", False))
sc.render.image_settings.file_format = "PNG"

# Alternativni vypocetni engine vedle Cyclesu (_renderer nastaven uz na
# zacatku souboru, viz komentar tam) - api/blender_render.py "renderer",
# whitelist cycles/luxcore. Zatim jen zkusebni/porovnavaci - vyzaduje
# nainstalovany BlendLuxCore extension (viz AGENTS_LOG.md 2026-09-08/09
# pro postup instalace + zname mezery: GPU vyber jeste neni propojeny
# jako u Cyclesu [KONF_GPU_BACKEND nize], rozliseni materialu kov/plast
# jeste neni overene spravne).
if _renderer == "luxcore":
    try:
        bpy.ops.preferences.addon_enable(module="bl_ext.user_default.blendluxcore")
    except Exception as e:
        raise SystemExit("LuxCore (BlendLuxCore) neni na serveru dostupny: %r" % (e,))
    # "use_cycles_settings" = LuxCore cte STEJNY World node-graph (Background/
    # Environment Texture), ktery uz stavi kod vyse pro Cycles - bez tohohle
    # by HDRi/pozadi zustalo prazdne (LuxCore ma jinak vlastni IBL koncept).
    world.luxcore.use_cycles_settings = True
    sc.render.engine = "LUXCORE"
    sc.luxcore.config.engine = "PATH"
    sc.luxcore.config.device = "CPU"  # GPU vyber zatim nereseno, viz komentar vyse
    sc.luxcore.halt.enable = True
    sc.luxcore.halt.use_time = True
    sc.luxcore.halt.time = int(float(g("time_limit_s", 0)) or 60)
    # Autolinear = automaticka expozice podle jasu sceny - bez tohodle
    # vysel render bud uplne prepaleny, nebo uplne tmavy podle HDRi.
    cam_data.luxcore.imagepipeline.tonemapper.use_autolinear = True
    sc.render.filepath = S["output_path"]
    bpy.ops.render.render(write_still=True)
    print("RENDER_OK", S["output_path"])
    raise SystemExit(0)

sc.render.engine = "CYCLES"

# --- Vypocetni zarizeni (CPU / GPU) -------------------------------------
# Server GPU nema (paravirtualni QXL), takze vychozi je CPU. Notebook s
# RTX 4080 si o GPU rekne promennou prostredi KONF_GPU_BACKEND
# (OPTIX / CUDA / HIP / ONEAPI), kterou nastavuje renderovaci agent.
#
# POZOR - nastaveni MUSI byt az tady, ne na zacatku skriptu:
# bpy.ops.wm.read_factory_settings() vyse resetuje i UZIVATELSKE
# PREDVOLBY, tedy vcetne vyberu vypocetniho zarizeni v Cycles. Robert
# 2026-08-11: presne tohle bylo duvodem, proc render na jeho notebooku
# bezel na CPU (49 s) a nebyl rychlejsi nez server - agent GPU zapnul,
# ale tenhle radek ji o par set radku pozdeji zase vypnul.
_gpu_backend = (os.environ.get("KONF_GPU_BACKEND") or "NONE").upper()
sc.cycles.device = "CPU"
if _gpu_backend != "NONE":
    _cprefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        _cprefs.compute_device_type = _gpu_backend
    except TypeError:
        print("GPU backend", _gpu_backend, "neni k dispozici, renderuji na CPU")
    else:
        _cprefs.get_devices()
        _on = []
        for _d in _cprefs.devices:
            # Jen zarizeni zvoleneho backendu. Kdyz se pusti i CPU nebo se
            # tataz karta zapne dvakrat (CUDA + OptiX), Cycles scenu mezi
            # ne rozdeli a render je POMALEJSI, ne rychlejsi.
            _d.use = (_d.type == _gpu_backend)
            if _d.use:
                _on.append(_d.name)
        if _on:
            sc.cycles.device = "GPU"
        print("GPU backend %s, zarizeni: %s" % (_gpu_backend, ", ".join(_on) or "zadne"))

# --- Sampling (odpovida panelu Render Properties > Sampling > Render,
# viz Robertuv screenshot z Blenderu 2026-08-10) ---
sc.cycles.samples = int(g("samples", 48))                      # Max Samples
sc.cycles.use_adaptive_sampling = bool(g("adaptive_sampling", True))
sc.cycles.adaptive_threshold = float(g("noise_threshold", 0.05))  # Noise Threshold
sc.cycles.adaptive_min_samples = int(g("min_samples", 0))      # Min Samples
sc.cycles.time_limit = float(g("time_limit_s", 0))             # Time Limit (0 = bez limitu)

# Robert 2026-08-11 ("ten server je slaby dlouho to trva"): denoising
# JE ted k dispozici - server pouziva oficialni Blender 4.2.9 LTS z
# blender.org (viz BLENDER_BIN v blender_render.py), ktery OpenImageDenoise
# obsahuje (drivejsi ubuntu balicek byl "without OpenImageDenoiser" a
# zapnuty denoising render rovnou shodil). Diky nemu staci vyrazne mene
# vzorku pri stejne cistote obrazu.
try:
    sc.cycles.use_denoising = bool(g("use_denoising", True))
    if sc.cycles.use_denoising:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
        sc.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
except (AttributeError, TypeError) as e:
    print("Denoising nedostupny, pokracuji bez nej:", e)
    sc.cycles.use_denoising = False
# --- Light Paths (Render Properties > Light Paths, viz Robertuv
# screenshot 2026-08-10 - vychozi hodnoty prevzaty z nej) ---
sc.cycles.max_bounces = int(g("max_bounces", 6))               # Max Bounces > Total
sc.cycles.diffuse_bounces = int(g("diffuse_bounces", 3))
sc.cycles.glossy_bounces = int(g("glossy_bounces", 3))
sc.cycles.transmission_bounces = int(g("transmission_bounces", 4))
sc.cycles.volume_bounces = int(g("volume_bounces", 0))
sc.cycles.transparent_max_bounces = int(g("transparent_bounces", 6))
sc.cycles.sample_clamp_direct = float(g("clamp_direct", 0.0))   # Clamping > Direct Light
sc.cycles.sample_clamp_indirect = float(g("clamp_indirect", 10.0))

sc.view_settings.view_transform = g("view_transform", "AgX")
sc.view_settings.look = g("look", "None")
sc.view_settings.exposure = float(g("exposure", 0.0))
sc.view_settings.gamma = float(g("gamma", 1.0))

# Robert 2026-08-10 ("chci to videt prubezne obraz kazdych 5 sec"):
# Cycles v headless rezimu neumi vydat rozdelany obraz ven behem
# jednoho renderu. Progresivni nahled se proto dela ROZDELENIM na
# nekolik pruchodu s rostoucim poctem vzorku (4, 8, 16... az cil) -
# kazdy pruchod prepise soubor nahledu, ktery si server pri dotazu na
# stav precte a posle do okna. Cena: celkovy cas ~2x delsi nez jeden
# pruchod (soucet geometricke rady), protoze kazdy pruchod pocita od
# nuly. Proto je to volitelne (posuvnik/zatrzitko v panelu) - kdo chce
# nejrychlejsi vysledek, prubezny nahled si vypne.
preview_path = S.get("preview_path")
target_samples = int(g("samples", 48))
progressive = bool(g("progressive_preview", True)) and bool(preview_path)

if progressive:
    passes = []
    s = max(4, target_samples // 8)
    while s < target_samples:
        passes.append(s)
        s *= 2
    passes.append(target_samples)
else:
    passes = [target_samples]

# Robert 2026-08-11: nahledove pruchody se renderuji ve ZMENSENEM
# rozliseni (vychozi 50 % = ctvrtina pixelu), finalni pruchod v plnem.
# Nahled slouzi k tomu, aby bylo videt "jde to spravnym smerem" - na to
# staci mensi obrazek a cena prubezneho nahledu klesne z ~2x celkoveho
# casu na ~1,2x. Navic je mensi PNG, coz se hodi pri prenosu z notebooku.
preview_pct = max(10, min(100, int(g("preview_scale", 50))))

preview_tmp = (preview_path + ".tmp.png") if preview_path else None
for idx, pass_samples in enumerate(passes):
    is_last = (idx == len(passes) - 1)
    sc.cycles.samples = pass_samples
    sc.render.resolution_percentage = 100 if is_last else preview_pct
    sc.render.filepath = S["output_path"] if is_last else preview_tmp
    bpy.ops.render.render(write_still=True)
    if not is_last:
        # os.replace je atomicky - server nikdy neprecte pulku souboru
        try:
            os.replace(preview_tmp, preview_path)
        except OSError:
            pass
        print(f"PASS_DONE {idx + 1}/{len(passes)} samples={pass_samples}", flush=True)

print("RENDER_OK", S["output_path"])
