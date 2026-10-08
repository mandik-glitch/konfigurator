# Stavba knihoven cub_seda.blend a bila.blend (Blender 5.2, -b --factory-startup, jen CPU, BEZ renderu).
#
#   /opt/blender-5.2/blender -b --factory-startup --python stav_knihovny.py -- <cub_seda|bila|laminodeska|eurobox_seda> <vystup.blend> [hex_barvy]
#
# CUB seda = KOPIE materialu KLT1 (KLT1.blend, procedura: Object souradnice -> Noise/Voronoi -> drsnost + Bump),
#            prebarveno na seda, meritko prepocteno na mm scenu, drsnost ~0.28, jemny jas-sum.
# Laminodeska   (2026-10-03, Robert: lamino, plastova vypln CUB a plast euroboxu jsou TRI ruzne materialy) = KOPIE KLT1, ale MATNA
#               svetle seda laminovana deska: bez clearcoatu, vyssi drsnost, jemne zrno (mensi noise, slaby bump).
# Eurobox_seda  = KOPIE KLT1 prebarvena na seda plast euroboxu (Vandr 'box tmava' #A6A6A6), pul-lesk (formovany PP), slaby clearcoat.
# Bila     = KOPIE materialu Suplik_celo (Suplik_celo.blend = lakovane ocelove celo supliku, tatez kostra jako KLT1),
#            prebarveno na bilou, glossy lak (coat), orange-peel bump i na coat normale.
# Zadne obrazky/odkazy na cizi soubory (obe predlohy jsou ciste proceduralni).
import bpy, sys, os

args = sys.argv[sys.argv.index("--") + 1:]
KIND, OUT = args[0], args[1]
HEX = args[2] if len(args) > 2 else None

DRIVE = "/opt/konfigurator/private-files/shared-drive/"
SRC = {
    "cub_seda": (DRIVE + "5493bf984acff4326159df504b4cce18.blend", "KLT1", "CUB seda", "KLT1.blend / KLT1"),
    "bila": (DRIVE + "aa06531213d6619b998766acdb057e7a.blend", "Suplik_celo", "Bila", "Suplik_celo.blend / Suplik_celo"),
    "laminodeska": (DRIVE + "5493bf984acff4326159df504b4cce18.blend", "KLT1", "Laminodeska", "KLT1.blend / KLT1"),
    "eurobox_seda": (DRIVE + "5493bf984acff4326159df504b4cce18.blend", "KLT1", "Eurobox seda", "KLT1.blend / KLT1"),
}
src_path, src_name, new_name, odvozeno = SRC[KIND]


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(h):
    h = h.lstrip("#")
    return tuple(s2l(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (1.0,)


# ---- cista scena: bez default objektu/materialu, aby soubor nesl jen material
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)

with bpy.data.libraries.load(src_path, link=False) as (df, dt):
    dt.materials = [src_name]
mat = bpy.data.materials[src_name]
mat.name = new_name
assert mat.name == new_name, mat.name
mat.use_fake_user = True
nt = mat.node_tree
N = nt.nodes


def node(name):
    return N[name]


P = node("Principled BSDF")
MAP = node("Mapping")
RAMP = node("Color Ramp").color_ramp
BUMP = node("Bump")

# jednotky: predloha je navrzena v METRECH (Mapping 8 => Noise scale 4 = ~3 cm skvrny, 80 = ~1.6 mm zrno,
# Bump Distance 0.008 = 8 mm). Nase render scena je v MM (1 BU = 1 mm) => souradnice * 0.001, vyska bumpu * 1000.
MAP.inputs["Scale"].default_value = (0.008, 0.008, 0.008)
MAP.label = "Meritko: 0.008 = 8 (puvodni, metry) x 0.001 (scena v mm). Metrova scena: 8"
BUMP.inputs["Distance"].default_value = 8.0
BUMP.label = "Bump: vyska v mm (puvodne 0.008 m)"


def ramp_set(e0, e1, v0, v1):
    RAMP.elements[0].position = e0
    RAMP.elements[0].color = (v0, v0, v0, 1.0)
    RAMP.elements[1].position = e1
    RAMP.elements[1].color = (v1, v1, v1, 1.0)
    RAMP.interpolation = "LINEAR"


def set_in(name, val):
    P.inputs[name].default_value = val


# nezavisle nastaveni obou materialu
if KIND == "cub_seda":
    base = hex_lin(HEX or "#BCBCBC")          # Unity .mat 'CUB seda' _Color 0.735849 (gamma projekt) = #BCBCBC
    set_in("Metallic", 0.0)
    set_in("IOR", 1.5)
    set_in("Specular IOR Level", 0.5)
    set_in("Anisotropic", 0.0)
    set_in("Coat Weight", 0.08)               # jako KLT1
    set_in("Coat Roughness", 0.15)
    set_in("Sheen Weight", 0.0)
    # drsnost: pozice sumu 0.30 -> 0.36, 0.70 -> 0.20 (stred 0.5 = 0.28, typicky 0.25-0.32)
    ramp_set(0.30, 0.70, 0.36, 0.20)
    BUMP.inputs["Strength"].default_value = 0.05
    var = 0.035                                # +-3.5 % jas
    mat.roughness = 0.28
    popis = "svetle seda plastova vypln CUB / laminodesky"
elif KIND == "laminodeska":
    # matna laminovana deska (foto produktu 3671: svetle seda, matna, jemne zrno, bez lesku)
    base = hex_lin(HEX or "#C4C4C1")
    set_in("Metallic", 0.0)
    set_in("IOR", 1.5)
    set_in("Specular IOR Level", 0.30)
    set_in("Anisotropic", 0.0)
    set_in("Coat Weight", 0.0)
    set_in("Coat Roughness", 0.5)
    set_in("Sheen Weight", 0.0)
    ramp_set(0.30, 0.70, 0.64, 0.50)          # stred 0.57 (matne)
    BUMP.inputs["Strength"].default_value = 0.03
    BUMP.inputs["Distance"].default_value = 0.6   # jemne zrno desky (CUB 8 mm = hruby formovany plast)
    MAP.inputs["Scale"].default_value = (0.025, 0.025, 0.025)   # jemnejsi zrno nez CUB
    var = 0.015                                # +-1.5 % jas
    mat.roughness = 0.57
    popis = "matna svetle seda laminodeska (lamino)"
elif KIND == "eurobox_seda":
    # seda plastova vana euroboxu: Vandr 'box tmava' (Unity _Color 0.651 = #A6A6A6), formovany PP, pul-lesk
    base = hex_lin(HEX or "#A6A6A6")
    set_in("Metallic", 0.0)
    set_in("IOR", 1.5)
    set_in("Specular IOR Level", 0.5)
    set_in("Anisotropic", 0.0)
    set_in("Coat Weight", 0.05)
    set_in("Coat Roughness", 0.2)
    set_in("Sheen Weight", 0.0)
    ramp_set(0.30, 0.70, 0.46, 0.30)          # stred 0.38 (pul-lesk)
    BUMP.inputs["Strength"].default_value = 0.04
    var = 0.03                                 # +-3 % jas
    mat.roughness = 0.38
    popis = "seda plastova vana euroboxu (Vandr 'box tmava')"
else:
    base = hex_lin(HEX or "#F2F2EF")
    set_in("Metallic", 0.0)
    set_in("IOR", 1.5)
    set_in("Specular IOR Level", 0.5)
    set_in("Anisotropic", 0.0)
    set_in("Coat Weight", 0.22)               # lehky clearcoat (Suplik_celo mel 0.08)
    set_in("Coat Roughness", 0.10)
    set_in("Coat IOR", 1.5)
    set_in("Sheen Weight", 0.0)
    ramp_set(0.30, 0.70, 0.46, 0.34)          # stred 0.40 (satinovy podklad pod lakem)
    BUMP.inputs["Strength"].default_value = 0.05
    var = 0.02                                 # +-2 % jas (lak je rovnomerny)
    mat.roughness = 0.40
    popis = "bily lak / lakovany plech (ocelove supliky stolu, elektrozlab)"
    # orange-peel i na lakove (coat) normale - bez toho by coat zustal dokonale hladky
    nt.links.new(BUMP.outputs["Normal"], P.inputs["Coat Normal"])

# ---- barva: RGB uzel * jemny jas-sum z velkeho Noise (MixRGB Multiply) -> Base Color
rgb = N.new("ShaderNodeRGB")
rgb.label = "Zakladni barva"
rgb.outputs[0].default_value = base
rgb.location = (P.location.x - 700, P.location.y + 260)
mr = N.new("ShaderNodeMapRange")
mr.label = "Jas-sum +-%.1f %%" % (var * 100)
mr.inputs["To Min"].default_value = 1.0 - var
mr.inputs["To Max"].default_value = 1.0 + var
mr.location = (P.location.x - 700, P.location.y + 60)
mx = N.new("ShaderNodeMixRGB")
mx.blend_type = "MULTIPLY"
mx.inputs["Fac"].default_value = 1.0
mx.location = (P.location.x - 400, P.location.y + 200)
nt.links.new(node("Noise Texture").outputs["Fac"], mr.inputs["Value"])
nt.links.new(rgb.outputs["Color"], mx.inputs["Color1"])
nt.links.new(mr.outputs["Result"], mx.inputs["Color2"])
nt.links.new(mx.outputs["Color"], P.inputs["Base Color"])
P.inputs["Base Color"].default_value = base      # (je linkovan; hodnota je pro zalohu/viewport)

mat.diffuse_color = base
mat.metallic = 0.0
mat["odvozeno_z"] = odvozeno
mat["popis"] = popis
mat["zdroj_barvy"] = {"cub_seda": "Unity .mat 'CUB seda' _Color 0.735849 (gamma) = #BCBCBC",
                      "laminodeska": "svetle seda #C4C4C1 odhad z fotky produktu 3671 (matna laminovana deska)",
                      "eurobox_seda": "Vandr material 'box tmava' _Color 0.651 (gamma) = #A6A6A6"}.get(KIND, "bila #F2F2EF (CUB bila v Unity = 1,1,1, lakovany plech ~0.9)")

# ---- vycisteni a ulozeni
for im in list(bpy.data.images):
    if im.users == 0:
        bpy.data.images.remove(im)
for o in list(bpy.data.meshes) + list(bpy.data.lights) + list(bpy.data.cameras):
    try:
        bpy.data.batch_remove([o])
    except Exception:
        pass
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print("ULOZENO", OUT, os.path.getsize(OUT), "bytes; material:", mat.name, "fake:", mat.use_fake_user)
