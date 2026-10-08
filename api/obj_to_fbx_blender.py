"""obj_to_fbx_blender.py - pomocny skript spousteny "blender -b --python
obj_to_fbx_blender.py -- <vstup.obj> <vystup.fbx>" (viz export_fbx_scene()
v app.py). Bezi uvnitr Blenderu (embedded Python, ne venv appky - proto
numpy pro Blenderuv FBX exporter instalovano zvlast primo do systemoveho
python3.12 pres "python3.12 -m pip install numpy --break-system-packages",
Blender 4.0 na Ubuntu je sestaveny proti systemovemu pythonu, ne vlastnimu).

bot2, 2026-08-02. Robert: "export do fbx nefunguje, resp po otevreni je ve
scene prazdno (pouzivam Rhino)" - puvodni implementace (assimp export -ffbx,
viz git historie) produkovala FBX, ktery assimp sam bez problemu znovu
nacetl (info prikaz ukazal spravnou geometrii), ale Rhino (postavene na
oficialnim Autodesk FBX SDK, mnohem prisnejsim ctecim) v nem nevidelo nic -
znamy, dlouhodobe hlaseny nedostatek Assimp FBX EXPORTERU (na rozdil od
FBX IMPORTU, ktery je v Assimpu zralý a pouziva se jinde v teto appce pro
opacny smer - nahravani FBX profilu/produktu admin_profily_fbx_upload()).
Blenderuv FBX exporter je oborovy standard pro interoperabilitu s
Rhino/Unity/Unreal/Maya, proto nahrazuje assimp pro tento (export) smer.

DULEZITE (scale): Blenderuv OBJ import bere 1 OBJ jednotku jako 1 metr,
FBX exporter pak defaultne dela dalsi prevod metry->cm (x100) pri zapisu
- bez "global_scale=0.01" (rusi ten x100 prevod) by vysledny FBX mel
souradnice 100x vetsi, nez puvodni OBJ (overeno testem: 20mm kostka ->
2000 bez opravy, 20 spravne s opravou). Nas OBJ (buildObjFromEntries
v scene.html) pouziva syrova cisla v mm, chceme presne stejna cisla i
ve vystupnim FBX (1:1), zadny skryty prevod jednotek.
"""
import bpy
import sys

def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if len(argv) < 2:
        print("OBJ_TO_FBX_ERROR: chybi argumenty (obj_path, fbx_path)")
        sys.exit(1)
    obj_path, fbx_path = argv[0], argv[1]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=obj_path)

    if not bpy.context.scene.objects:
        print("OBJ_TO_FBX_ERROR: po importu OBJ nejsou ve scene zadne objekty")
        sys.exit(1)

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=False,
        global_scale=0.01,
        apply_unit_scale=False,
        apply_scale_options='FBX_SCALE_NONE',
        axis_forward='-Z',
        axis_up='Y',
    )
    print("OBJ_TO_FBX_OK")


try:
    main()
except Exception as e:
    print(f"OBJ_TO_FBX_ERROR: {e}")
    sys.exit(1)
