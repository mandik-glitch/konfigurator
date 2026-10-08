#!/usr/bin/env python3
"""fbx_mesh_extract_worker.py - bot8, 2026-09-29 (univerzalni import objektu,
viz universal_import.py).

Sourozenec fbx_mesh_bounds_worker.py (bot16, 2026-09-03): STEJNE cteni
(assimp, jen Process_Triangulate, vrcholy meshu tak, jak je assimp vrati,
BEZ aplikace transformaci uzlu), stejny prevod os FBX -> scena
(scene_x=fbx_y, scene_y=fbx_z, scene_z=fbx_x), stejny subprocess vzor
(pad/timeout potomka = jen chybova hlaska, ne pad gunicorn workeru).
Bboxy jsou bit-shodne s fbx_mesh_bounds_worker (overeno na profil_fbx/
noha_*.fbx i na Unity SSE.2020.Ram40.6P.fbx).

Navic uklada SAMOTNE VRCHOLY/INDEXY kazdeho meshe (numpy .npz do
workdir) - z nich se pak skladaji jednotlive GLB dilu. Na stdout jde jen
JSON s metadaty (u stolu jsou statisice vrcholu, to do JSONu nepatri).
K meshi se doplni i nazev uzlu, ktery ho odkazuje (assimp mesh name byva
"Object_29.002", uzel "Object_29" - pro clovek citelnejsi popisek).

PROC SE TRANSFORMACE UZLU NEAPLIKUJI (vyzkouseno 2026-09-29, obe cesty
zamitnuty):
  * Process_PreTransformVertices: zapece transformace, ale zaroven SLOUCI
    meshe se stejnym materialem do jednoho (noha 8 -> 4, ram 43 -> 4) =
    presny opak rozkladu na dily.
  * rucni nasobeni matic uzlu (rodic @ uzel): u SolidWorks exportu jsou
    vsechny uzly identita (bez zmeny), ale u Unity exportu maji uzly
    vrstev uniform scale 0.1 a vysledek byl 10x MENSI nez skutecnost
    (profil "45x45x100_3" = 4x4x157 misto spravnych 40x40x1569 mm) -
    assimp vraci vrcholy uz ve finalnich jednotkach, ten scale je
    importni artefakt, ne skutecna transformace. Proto stejne chovani
    jako fbx_mesh_bounds_worker, na kterem stoji dimension_match_fbx/
    leg_fbx_import v produkci.

Pouziti: venv/bin/python fbx_mesh_extract_worker.py vstup.fbx workdir
Vystup (posledni radek stdout): {"ok": true, "total": N, "meshes": [
  {"i", "name", "node", "bb_min", "bb_max", "n_verts", "n_tris", "npz"}]}
nebo {"ok": false, "error": "..."}; exit 0/1.
"""
import json
import os
import sys


def extract(fbx_path, workdir):
    import numpy as np
    import assimp_py as ai

    os.makedirs(workdir, exist_ok=True)
    scene = ai.import_file(fbx_path, ai.Process_Triangulate)

    node_of_mesh = {}

    def walk(node):
        for mi in node.mesh_indices:
            node_of_mesh.setdefault(int(mi), node.name)
        for ch in node.children:
            walk(ch)

    walk(scene.root_node)

    meshes = []
    for i, m in enumerate(scene.meshes):
        verts = np.frombuffer(m.vertices, dtype=np.float32).reshape(-1, 3)
        if not len(verts):
            continue
        scene_pts = verts[:, [1, 2, 0]].astype(np.float32)
        idx = np.frombuffer(m.indices, dtype=np.uint32).copy()
        npz_name = f"mesh_{i}.npz"
        np.savez(os.path.join(workdir, npz_name), pos=scene_pts, idx=idx)
        meshes.append({
            "i": i,
            "name": m.name or node_of_mesh.get(i, f"mesh_{i}"),
            "node": node_of_mesh.get(i, ""),
            "bb_min": scene_pts.min(axis=0).astype(float).tolist(),
            "bb_max": scene_pts.max(axis=0).astype(float).tolist(),
            "n_verts": int(len(scene_pts)),
            "n_tris": int(len(idx) // 3),
            "npz": npz_name,
        })
    return {"ok": True, "meshes": meshes, "total": len(scene.meshes)}


def main():
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "Pouziti: fbx_mesh_extract_worker.py <soubor.fbx> <workdir>"}))
        sys.exit(1)
    try:
        result = extract(sys.argv[1], sys.argv[2])
    except Exception as e:  # noqa: BLE001 - vsechno hlasit rodici jako JSON
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
