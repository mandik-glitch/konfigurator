# Blender (na pozadi, CPU, bez renderu) - prevody GLB -> OBJ / FBX / GLB / STL pro test odolnosti znacky.
# Spusteni: /opt/blender-5.2/blender -b --factory-startup --python tests/_blender_mark_convert.py -- vstup.glb vystupni_adresar
# Vystupy v adresari: glb_rt.glb, glb_zup.glb, obj.obj, fbx.fbx, fbx_rt.glb, stl.stl,
# join_glb.glb, merge01_glb.glb, merge_big_glb.glb, origin_geom_glb.glb, decimate_glb.glb
# Na konci radek "CONVERT_DONE <seznam>" (a "CONVERT_ERR <krok> <chyba>" pri selhani kroku).
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = argv[0], argv[1]
os.makedirs(OUT, exist_ok=True)
done = []


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def imp_glb():
    fresh()
    bpy.ops.import_scene.gltf(filepath=SRC)


def step(name, fn):
    try:
        fn()
        done.append(name)
    except Exception as e:                      # noqa: BLE001
        print("CONVERT_ERR", name, repr(e)[:300])


def sel_meshes():
    bpy.ops.object.select_all(action="DESELECT")
    ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in ms:
        o.select_set(True)
    if ms:
        bpy.context.view_layer.objects.active = ms[0]
    return ms


def exp_glb(name, **kw):
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, name), export_format="GLB", **kw)


def s_glb_rt():
    imp_glb()
    exp_glb("glb_rt.glb")


def s_glb_zup():
    imp_glb()
    exp_glb("glb_zup.glb", export_yup=False)


def s_obj():
    imp_glb()
    bpy.ops.wm.obj_export(filepath=os.path.join(OUT, "obj.obj"), export_materials=False,
                          export_normals=False, export_uv=False)


def s_fbx():
    imp_glb()
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "fbx.fbx"))
    fresh()
    bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, "fbx.fbx"))
    exp_glb("fbx_rt.glb")


def s_stl():
    imp_glb()
    bpy.ops.wm.stl_export(filepath=os.path.join(OUT, "stl.stl"))


def s_join():
    imp_glb()
    ms = sel_meshes()
    bpy.ops.object.join()
    exp_glb("join_glb.glb")


def s_merge01():
    imp_glb()
    ms = sel_meshes()
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode="OBJECT")
    exp_glb("merge01_glb.glb")


def s_merge_big():
    imp_glb()
    ms = sel_meshes()
    bpy.ops.object.join()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.1)
    bpy.ops.object.mode_set(mode="OBJECT")
    exp_glb("merge_big_glb.glb")


def s_origin_geom():
    imp_glb()
    ms = sel_meshes()
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    exp_glb("origin_geom_glb.glb")


def s_decimate():
    imp_glb()
    ms = sel_meshes()
    for o in ms:
        bpy.context.view_layer.objects.active = o
        m = o.modifiers.new("d", "DECIMATE")
        m.ratio = 0.5
        bpy.ops.object.modifier_apply(modifier=m.name)
    exp_glb("decimate_glb.glb")


for nm, fn in (("glb_rt", s_glb_rt), ("glb_zup", s_glb_zup), ("obj", s_obj), ("fbx", s_fbx), ("stl", s_stl),
               ("join", s_join), ("merge01", s_merge01), ("merge_big", s_merge_big),
               ("origin_geom", s_origin_geom), ("decimate", s_decimate)):
    step(nm, fn)
print("CONVERT_DONE", " ".join(done))
