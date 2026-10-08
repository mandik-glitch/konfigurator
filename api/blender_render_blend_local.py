"""blender_render_blend_local.py - server-side (bez GPU) render syroveho
.blend souboru presne tak, jak byl ulozen (vlastni kamera/material/
engine/vzorky uvnitr) - zadna sestava se nestavi z GLB, na rozdil od
blender_render_scene.py.

Pouziva se JEN pro lokalni (server) fallback, kdyz Robertuv GPU worker
neni online - viz api/blender_render.py::_run_render_job, job_type
"blend". Vzdaleny worker (scripts/render_worker_agent.py) .blend
soubor renderuje PRIMO (blender -b <file> -f 1), bez tohodle skriptu -
jeho vlastni Cycles preference uz GPU zarizeni maji zapnute a
read_factory_settings() se tam nikdy nevola (na rozdil od
blender_render_scene.py), takze soubor si ponecha presne to, co ma
ulozene.

Server GPU nema (paravirtualni QXL) - kdyz scena chce "GPU" a zadne
zarizeni neni k dispozici, prepneme na CPU (jinak by render vubec
neprobehl), vse ostatni (vzorky, kamera, material, world, rozliseni)
zustava presne take, jak je v souboru ulozeno.
"""
import bpy
import sys

sc = bpy.context.scene

if sc.render.engine == "CYCLES" and sc.cycles.device == "GPU":
    try:
        cprefs = bpy.context.preferences.addons["cycles"].preferences
        cprefs.get_devices()
        any_gpu = any(d.use and d.type != "CPU" for d in cprefs.devices)
    except Exception:
        any_gpu = False
    if not any_gpu:
        print("Zadne GPU zarizeni na tomto stroji - prepnuto na CPU.")
        sc.cycles.device = "CPU"

# Robert 2026-09-09: "nechceme to samotne pozadi hdri videt, slouzi pouze
# pro odlesky". film_transparent nemeni osvetleni ani odrazy (HDRI dal
# sviti i se zrcadli v hliniku) - jen kamerove paprsky, ktere proleti
# kolem sestavy do prazdna, konci pruhlednou alfou misto fotky mapy.
# Zapina se TADY, na uz nactenem souboru; .blend na Sdilenem disku se
# nikdy neprepisuje. Stejny prepinac ma vzdaleny worker
# (scripts/render_worker_agent.py::run_blend_job).
sc.render.film_transparent = True

out_path = sys.argv[sys.argv.index("--") + 1]
sc.render.filepath = out_path
sc.render.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
print("RENDER_OK", out_path)
