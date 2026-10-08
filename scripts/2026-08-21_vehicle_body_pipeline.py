import bpy, bmesh, math, sys, json

# Parametrizovana verze overene pipeline (FO30) - vezme libovolny zdrojovy
# GLB + jmena uzlu pro L/R_D/B a vyrobi 3 samostatne zpracovane soubory
# (shell-separation na L/R_D, B beze zmeny krome scale/rotace).
#
# Pouziti: blender --background --python process_vehicle_body.py -- \
#   <src.glb> <out_dir> <prefix> <L_node> <RD_node> <B_node>

argv = sys.argv[sys.argv.index("--")+1:]
src, out_dir, prefix, l_name, rd_name, b_name = argv

def dominant_axis_is_x(o):
    me = o.data
    me.calc_loop_triangles()
    area_x, area_z = 0.0, 0.0
    for poly in me.polygons:
        n = poly.normal
        if abs(n.x) > 0.8: area_x += poly.area
        elif abs(n.z) > 0.8: area_z += poly.area
    return area_x > area_z

def process_shell_layered(name, out_suffix):
    obj = bpy.data.objects.get(name)
    if obj is None:
        return {"error": f"{name} nenalezen"}
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0005)
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')
    pieces = [o for o in bpy.data.objects if o.name == name or o.name.startswith(name + ".")]
    pieces = [o for o in pieces if len(o.data.vertices) >= 20]

    if len(pieces) == 1:
        # jen 1 vrstva (jako FO30_B) - neni co oddelovat
        inner = pieces
    else:
        inner = [o for o in pieces if dominant_axis_is_x(o)]
        if len(inner) != 1:
            return {"error": f"{name}: ocekavana 1 vnitrni vrstva, nalezeno {len(inner)} (celkem vrstev {len(pieces)})"}

    all_pieces_this_obj = [o for o in bpy.data.objects if o.name == name or o.name.startswith(name + ".")]
    bpy.ops.object.select_all(action='DESELECT')
    for o in all_pieces_this_obj:
        if o.name != inner[0].name:
            o.select_set(True)
    bpy.ops.object.delete()

    inner_obj = bpy.data.objects[inner[0].name]
    inner_obj.name = name
    # NEprepisovat scale absolutne na 1000 - ruzne zdrojove soubory v
    # knihovne maji ruznou vlastni jednotkovou konvenci (FO30: raw mesh
    # uz v metrech, scale=1.0; jine soubory: raw mesh uz v mm-like
    # cislech, kompenzovano scale=0.001 na uzlu, aby souhlasila world-
    # space velikost v "metrech"). NASOBIT existujici scale 1000x -
    # respektuje uz spravnou world-space velikost (tu, kterou vidi
    # kazdy standardni glTF prohlizec), misto aby ji ignorovalo.
    # Overeno 2026-08-21 na BYD/NI11: scale=1000 (absolutni) dal
    # 735147mm misto spravnych 735mm - presne 1000x moc, protoze
    # puvodni scale byl 0.001, ne 1.0 jako u FO30.
    inner_obj.scale = tuple(s * 1000.0 for s in inner_obj.scale)
    inner_obj.rotation_mode = 'XYZ'
    inner_obj.rotation_euler[0] += math.radians(-90)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    inner_obj.select_set(True)
    bpy.context.view_layer.objects.active = inner_obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    out_path = f"{out_dir}{prefix}_{out_suffix}.glb"
    bpy.ops.export_scene.gltf(filepath=out_path, export_format='GLB', use_selection=True, export_apply=True)
    return {"ok": True, "path": out_path, "layers_found": len(pieces)}


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
names_found = [o.name for o in bpy.data.objects]

result = {"source": src, "nodes_in_file": names_found}
result["L"] = process_shell_layered(l_name, "L")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
result["R_D"] = process_shell_layered(rd_name, "R_D")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
result["B"] = process_shell_layered(b_name, "B")

print("RESULT_JSON_START")
print(json.dumps(result))
print("RESULT_JSON_END")
