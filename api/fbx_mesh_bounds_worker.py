#!/usr/bin/env python3
"""fbx_mesh_bounds_worker.py - bot16, 2026-09-03 (revize bot3, bod 2).

Precte FBX pres assimp a vypise JSON se jmenem a bounding boxem KAZDEHO
meshe (uz ve scene souradnicich: scene_x=fbx_y, scene_y=fbx_z,
scene_z=fbx_x - stejny prevod jako dosud v dimension_match_fbx.match_meshes).

PROC SUBPROCESS: assimp je C knihovna a driv bezela primo uvnitr gunicorn
workeru - podvrzeny/obri FBX = pad nebo vycerpani pameti CELEHO workera
(a `--timeout 60` gunicornu pak zabije i ostatni rozdelane requesty).
Stejny vzor jako step_convert.py -> step_convert_worker.py: rodic ma
timeout a pad potomka je jen chybova hlaska.

Pouziti: venv/bin/python fbx_mesh_bounds_worker.py vstup.fbx
Vystup: jeden radek JSON {"ok": true, "meshes": [{"name", "bb_min", "bb_max"}]}
nebo {"ok": false, "error": "..."}; exit 0/1.
"""
import json
import sys


def read_bounds(fbx_path):
    import numpy as np
    import assimp_py as ai

    scene = ai.import_file(fbx_path, ai.Process_Triangulate)
    meshes = []
    for m in scene.meshes:
        verts = np.frombuffer(m.vertices, dtype=np.float32).reshape(-1, 3)
        if not len(verts):
            continue
        scene_pts = verts[:, [1, 2, 0]].astype(np.float64)
        meshes.append({
            "name": m.name,
            "bb_min": scene_pts.min(axis=0).tolist(),
            "bb_max": scene_pts.max(axis=0).tolist(),
        })
    return {"ok": True, "meshes": meshes, "total": len(scene.meshes)}


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "Pouziti: fbx_mesh_bounds_worker.py <soubor.fbx>"}))
        sys.exit(1)
    try:
        result = read_bounds(sys.argv[1])
    except Exception as e:  # noqa: BLE001 - vsechno hlasit rodici jako JSON
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
