"""priprav_sablonu.py - dopln do .blend sablony CHYBEJICI obrazky
(bezi UVNITR Blenderu). bot8, Robert 2026-09-09: "proc ho tam nedas?"

Blender obrazky do .blend neuklada, uklada jen CESTU. Robertuv X30-1.blend
proto odkazuje na C:\\Users\\rober\\Downloads\\... - na GPU stanici ta
cesta neexistuje, Blender obrazek nenajde a render vyjde FIALOVY.

Tenhle skript chybejici obrazky najde podle NAZVU SOUBORU ve sdilenych
slozkach, prepoji je a VSECHNY zabali dovnitr. Vysledek uklada jako
KOPII - Robertuv original se nikdy nemeni (jeho vyslovne pravidlo).

    blender -b <sablona.blend> -P priprav_sablonu.py -- <vystup.blend>
"""
import os
import sys

import bpy

HLEDAT_V = [
    "/opt/konfigurator/private-files/shared-drive-named/Rendering/HDRi",
    "/opt/konfigurator/private-files/shared-drive-named/Rendering",
]

_args_all = sys.argv[sys.argv.index("--") + 1:]
out_path = _args_all[0]

# Mapa nazev souboru -> plna cesta. PORADI JE ZAMERNE:
#
# 1. seznam z TABULKY shared_drive_files, ktery predava volajici tretim
#    argumentem (JSON). Tabulka je zdroj pravdy - odvozeny strom
#    shared-drive-named/ nespolehlivy JE: 2026-09-10 v nem lezel rozbity
#    symlink canary_wharf_4k.exr na blob, ktery uz neexistoval, a dva
#    soubory (docklands_01_4k.hdr, crossfit_gym_2k.exr) tam jsou jen jako
#    rucni kopie, ktere v tabulce nejsou vubec - pri pregenerovani stromu
#    by zmizely.
# 2. teprve pak prohledani adresare, jako zaloha (a jedina cesta k tem
#    rucnim kopiim, dokud je nekdo poradne nenahraje).
#
# Rozbite symlinky se preskakuji - os.path.isfile() je na nich False,
# jinak by se dosadila cesta, kterou Blender stejne neotevre.
k_dispozici = {}
if len(_args_all) > 2 and _args_all[2]:
    try:
        import json as _json
        with open(_args_all[2], "r", encoding="utf-8") as _fh:
            for _jmeno, _cesta in (_json.load(_fh) or {}).items():
                if os.path.isfile(_cesta):
                    k_dispozici.setdefault(_jmeno.lower(), _cesta)
        print("Z TABULKY: %d souboru k dispozici" % len(k_dispozici))
    except Exception as _e:
        print("VAROVANI: seznam z tabulky nelze precist (%r), jedu podle adresare" % _e)
for base in HLEDAT_V:
    for root, _dirs, files in os.walk(base):
        for f in files:
            cesta = os.path.join(root, f)
            if os.path.isfile(cesta):
                k_dispozici.setdefault(f.lower(), cesta)

chybelo, doplneno, nenalezeno = 0, 0, []
for img in bpy.data.images:
    if img.packed_file or img.source not in {"FILE", "SEQUENCE"} or not img.filepath:
        continue
    if tuple(img.size) != (0, 0):
        continue          # nacetl se, je v poradku
    chybelo += 1
    jmeno = os.path.basename(img.filepath.replace("\\", "/")).lower()
    nahrada = k_dispozici.get(jmeno)
    if not nahrada:
        nenalezeno.append(jmeno)
        continue
    img.filepath = nahrada
    try:
        img.reload()
        img.pack()
        doplneno += 1
        print("DOPLNENO: %s <- %s" % (img.name, nahrada))
    except Exception as e:
        nenalezeno.append("%s (%r)" % (jmeno, e))

# zabalit i vse ostatni, at je sablona sobestacna na cizim pocitaci
for img in bpy.data.images:
    if not img.packed_file and img.source in {"FILE", "SEQUENCE"} and img.filepath:
        try:
            img.pack()
        except Exception:
            pass

print("SOUHRN chybelo=%d doplneno=%d nenalezeno=%s" % (chybelo, doplneno, nenalezeno or "-"))

# --- volitelna vymena HDRI (Robert 2026-09-09) -------------------------
# "chci mit moznost podle vyslednych renderu preklikavat ktery hdri se
# pouzije priste" + "kdyz bude v adresari 20 hdri souborů musi se mi
# nabidnout vsechny".
#
# Vymena se deje TADY, tedy az v KOPII sablony - Robertuv .blend zustava
# nedotceny (jeho pravidlo). Kdyz se HDRI nepreda, world se nechava presne
# tak, jak si ho Robert ulozil.
hdri_path = None
_args = sys.argv[sys.argv.index("--") + 1:]
if len(_args) > 1 and _args[1]:
    hdri_path = _args[1]

# --- volitelna rotace HDRI kolem svisle osy (Robert pres bot3, 2026-09-12:
# "zkusit natocit HDRI mapu kolem svisle osy po 30°, 12 pozic 0-330° a pro
# kazdou udelat test render") -------------------------------------------
# Nezavisle na vymene souboru vyse - rotuje se i STAVAJICI mapa sablony,
# kdyz se hdri_path nepreda.
hdri_rotace_deg = 0.0
if len(_args) > 3 and _args[3]:
    try:
        hdri_rotace_deg = float(_args[3])
    except ValueError:
        print("HDRI ROTACE: neplatny uhel %r (ma byt cislo ve stupnich), pouzivam 0" % _args[3])

if hdri_path and not os.path.isfile(hdri_path):
    print("HDRI: soubor neexistuje, nechavam world beze zmeny: %s" % hdri_path)
    hdri_path = None

if hdri_path or hdri_rotace_deg:
    sc = bpy.context.scene
    world = sc.world
    if world is None:
        world = bpy.data.worlds.new("Render_World")
        sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    # Vybrat ten TEX_ENVIRONMENT, ktery opravdu krmi pozadi/osvetleni.
    # X30-1.blend ma uzly DVA a "prvni v seznamu" je ten SPATNY:
    #   Environment Texture     (docklands) -> Ambient Occlusion  <- prvni
    #   Environment Texture.001 (canary)    -> Background         <- tenhle
    # Puvodni next(...) proto vybranou mapu dosazoval do AO vetve, kde
    # se na osvetleni ani odlescich vubec neprojevi. Jdeme tedy po
    # skutecnem zapojeni: World Output -> Background -> Color.
    def _env_za_pozadim():
        out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None)
        na_rade, videno = [], set()
        if out:
            na_rade = [l.from_node for l in out.inputs["Surface"].links]
        while na_rade:
            uzel = na_rade.pop(0)
            if uzel is None or uzel.name in videno:
                continue
            videno.add(uzel.name)
            if uzel.type == "TEX_ENVIRONMENT":
                return uzel
            for vst in uzel.inputs:
                for l in vst.links:
                    na_rade.append(l.from_node)
        return None

    env = _env_za_pozadim() or next((n for n in nt.nodes if n.type == "TEX_ENVIRONMENT"), None)
    if env is not None:
        print("HDRI: cilovy uzel '%s'" % env.name)
    if env is None and hdri_path:
        # World bez environment textury (jen barva) - dopojime uzel na
        # Background, at ma HDRI kam vstoupit.
        bg = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
        if bg is None:
            bg = nt.nodes.new("ShaderNodeBackground")
            out = next((n for n in nt.nodes if n.type == "OUTPUT_WORLD"), None) \
                or nt.nodes.new("ShaderNodeOutputWorld")
            nt.links.new(out.inputs["Surface"], bg.outputs["Background"])
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        nt.links.new(bg.inputs["Color"], env.outputs["Color"])
    elif env is None:
        print("HDRI ROTACE: sablona nema zadny Environment Texture uzel, neni co otocit")

    if env is not None and hdri_path:
        img = bpy.data.images.load(hdri_path, check_existing=True)
        env.image = img
        try:
            img.pack()          # bez zabaleni by na GPU stanici chybela
        except Exception as e:
            print("HDRI: nelze zabalit (%r) - render muze vyjit tmavy" % e)
        print("HDRI VYMENENO: %s (world '%s')" % (os.path.basename(hdri_path), world.name))

    if env is not None and hdri_rotace_deg:
        import math
        # Mapping napojeny primo na env.Vector uz muze existovat (napr.
        # sablona uz jednou rotaci mela) - pouzit ho znovu misto hromadeni
        # dalsich uzlu pri opakovanem behu na stejnem zdrojovem souboru.
        _navazany = env.inputs["Vector"].links[0].from_node if env.inputs["Vector"].links else None
        if _navazany is not None and _navazany.type == "MAPPING":
            mp = _navazany
        else:
            tc = nt.nodes.new("ShaderNodeTexCoord")
            mp = nt.nodes.new("ShaderNodeMapping")
            nt.links.new(mp.inputs["Vector"], tc.outputs["Generated"])
            nt.links.new(env.inputs["Vector"], mp.outputs["Vector"])
        mp.inputs["Rotation"].default_value[2] = math.radians(hdri_rotace_deg)
        print("HDRI ROTACE: %.1f stupnu (Z, uzel '%s' -> '%s')" % (hdri_rotace_deg, mp.name, env.name))

bpy.ops.wm.save_as_mainfile(filepath=out_path, compress=True)
print("PRIPRAVENO", out_path)
