"""NAVRH knihoven pro materialy cub_seda a bila (bot10, 2026-10-01) - na Sdilenem disku zatim NEEXISTUJI.

Vyrobi dva male .blend soubory s jednim materialem (Principled BSDF, fake user), stejne konvence jako ostatni Vandr
materialy (jeden material v souboru, soubor pojmenovany podle klice):
  cub_seda.blend -> material "CUB seda"   (laminodesky, plastove vypln; nativni 'CUB seda' z Vandr GLB: rough 0.25, metal 0)
  bila.blend     -> material "Bila"       (elektrozlab, lakovany plech; bily lak, rough 0.28)
Hodnoty = three_json z sql/2026-10-01_render_materialy.sql (nahled v adminu). Je to PLACEHOLDER jednoduchy Principled,
ne textura jako Alumi2/grey - kdyz ma Robert vlastni material, nahraje svuj soubor pod stejnym jmenem (a nazev_blender v
render_materialy upravi). Soubory se NEnahravaji na Sdileny disk samy - nahraje je Robert (Sdileny disk -> slozka
Vandr materialy), jinak admin u materialu ukazuje "knihovna chybi".

Spusteni (jen vytvori soubory, nic nerenderuje, nic nemeni v repu ani DB):
  /opt/blender-5.2/blender --background --factory-startup --python scripts/2026-10-01_render_materialy_knihovny_blend.py -- <vystupni_slozka>
"""
import os
import sys

import bpy

SPEC = {
    # soubor: (nazev materialu, sRGB hex, metalness, roughness, coat)
    "cub_seda.blend": ("CUB seda", "#D5D5D5", 0.0, 0.25, 0.0),
    "bila.blend": ("Bila", "#F4F4F1", 0.0, 0.28, 0.0),
}


def srgb_na_linear(hexc):
    n = int(hexc.lstrip("#"), 16)
    kanaly = [(n >> 16) & 255, (n >> 8) & 255, n & 255]
    return [((c / 255.0) / 12.92) if c / 255.0 <= 0.04045 else (((c / 255.0) + 0.055) / 1.055) ** 2.4 for c in kanaly] + [1.0]


def main():
    if "--" not in sys.argv or len(sys.argv) <= sys.argv.index("--") + 1:
        raise SystemExit("pouziti: blender --background --python <skript> -- <vystupni_slozka>")
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    for soubor, (nazev, hexc, kov, drs, coat) in SPEC.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        m = bpy.data.materials.new(nazev)
        m.use_nodes = True
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        p.inputs["Base Color"].default_value = srgb_na_linear(hexc)
        p.inputs["Metallic"].default_value = kov
        p.inputs["Roughness"].default_value = drs
        if "Coat Weight" in p.inputs:
            p.inputs["Coat Weight"].default_value = coat
        m.use_fake_user = True
        cesta = os.path.join(out, soubor)
        bpy.ops.wm.save_as_mainfile(filepath=cesta)
        print("ZAPSANO %s (material '%s')" % (cesta, nazev))


main()
