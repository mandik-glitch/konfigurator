import bpy, bmesh, math, json, os, glob, re, traceback, sys
import mathutils

sys.path.insert(0, "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad")
from detect_orientation import detect_axis_mapping, build_correction_matrix

OUT_DIR = "/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/batch_v2_out/"
os.makedirs(OUT_DIR, exist_ok=True)

# vsech 20: (soubor, prefix_uzlu_bez_L/R_D/B_suffixu se detekuje automaticky)
FILES = [
    ("/root/.claude/uploads/b336267e-a1f5-4ea8-b332-89232804d6ac/469f4849-FO30.glb", "Ford_FO30"),
    ("/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/drive_download_test/BYD__ETP3_BY01_2020-.glb", "BYD_ETP3"),
] + [
    (f, os.path.splitext(os.path.basename(f))[0])
    for f in sorted(glob.glob("/tmp/claude-0/-opt-konfigurator/b336267e-a1f5-4ea8-b332-89232804d6ac/scratchpad/batch20/*.glb"))
]

def detect_lrb_nodes(names):
    # 2026-08-21 (Citroen Jumpy CI18/CI19, interne "PE20/PE21"): nektere
    # soubory nemaji zadnou "_R_D" (s dvermi) variantu, jen hole "_R" -
    # ne kazdy model ma dverni variantu na prave strane. Preferuj _R_D
    # (zavedeny vzor), spadni na plain _R kdyz neexistuje.
    def suffix_tokens(n):
        return n.split("_")
    l_cands = [n for n in names if suffix_tokens(n)[-1] == "L"]
    rd_cands = [n for n in names if suffix_tokens(n)[-2:] == ["R", "D"]]
    if not rd_cands:
        rd_cands = [n for n in names if suffix_tokens(n)[-1] == "R"]
    b_cands = [n for n in names if suffix_tokens(n)[-1] == "B"]
    return (l_cands[0] if len(l_cands) == 1 else None,
            rd_cands[0] if len(rd_cands) == 1 else None,
            b_cands[0] if len(b_cands) == 1 else None)

def dominant_axis_is_x(o):
    me = o.data
    me.calc_loop_triangles()
    area_x, area_z = 0.0, 0.0
    for poly in me.polygons:
        n = poly.normal
        if abs(n.x) > 0.8: area_x += poly.area
        elif abs(n.z) > 0.8: area_z += poly.area
    return area_x > area_z

def shell_separate(name):
    """Robert 2026-08-21 ("ford je bez podlahy"): odstraneni vnejsi
    vrstvy stahlo s sebou i podlahu (fyzicky srostla s vnejsi/plochou
    slupkou v puvodni mesh - "inner"/"outer" klasifikace podle
    dominantni roviny normal si vsimala jen stenovych ploch, ne
    podlahy). Dokud neni bezpecny zpusob jak podlahu zachovat i pri
    odstraneni vnejsi slupky, NEODDELOVAT vrstvy vubec - vratit CELou
    puvodni geometrii (obe vrstvy pokud existuji), jen zmereno kolik
    jich je pro informaci."""
    obj = bpy.data.objects.get(name)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    visited = set(); islands = []
    for sv in bm.verts:
        if sv.index in visited: continue
        stack=[sv]; comp=[]; visited.add(sv.index)
        while stack:
            v = stack.pop(); comp.append(v)
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.index not in visited:
                    visited.add(o.index); stack.append(o)
        islands.append(comp)
    layers_found = len([c for c in islands if len(c) >= 20])
    bm.free()
    return obj, layers_found


results = []
for fpath, prefix in FILES:
    entry = {"file": fpath, "prefix": prefix}
    try:
        # 1) import jen pro detekci mapovani os (na CISTYCH, jeste nerozdelenych L/R_D/B)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=fpath)
        names = [o.name for o in bpy.data.objects if o.type == 'MESH']
        l_n, rd_n, b_n = detect_lrb_nodes(names)
        entry["nodes_found"] = names
        entry["detected"] = {"L": l_n, "R_D": rd_n, "B": b_n}
        if not (l_n and rd_n and b_n):
            entry["error"] = "nejednoznacna detekce L/R_D/B"
            results.append(entry)
            continue

        l_obj = bpy.data.objects[l_n]; rd_obj = bpy.data.objects[rd_n]; b_obj = bpy.data.objects[b_n]
        mapping, l_r, rd_r, b_r = detect_axis_mapping(l_obj, rd_obj, b_obj)
        entry["axis_mapping"] = mapping
        M_corr = build_correction_matrix(mapping).to_4x4()
        M_scale = mathutils.Matrix.Scale(1000.0, 4)
        M_total = M_scale @ M_corr

        # 2) pro kazdy ze 3 uzlu: cerstvy import (kvuli shell-separate bezpecnosti),
        # aplikuj STEJNOU M_total (spocitanou z puvodni, nerozdelene geometrie).
        for role, node_name in [("L", l_n), ("R_D", rd_n), ("B", b_n)]:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=fpath)
            obj, layers = shell_separate(node_name)
            bpy.context.view_layer.update()
            obj.matrix_world = M_total @ obj.matrix_world
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            out_path = f"{OUT_DIR}{prefix}_{role}.glb"
            bpy.ops.export_scene.gltf(filepath=out_path, export_format='GLB', use_selection=True, export_apply=True)
            entry[role] = {"ok": True, "path": out_path, "layers_found": layers}
    except Exception as e:
        entry["exception"] = f"{e}\n{traceback.format_exc()}"
    results.append(entry)
    print(f"HOTOVO: {prefix}")

with open(OUT_DIR + "batch_v2_results.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)
print("VSECHNY SOUBORY ZPRACOVANY (v2, obecny algoritmus orientace)")
