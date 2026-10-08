"""
fbx_convert.py - prevod jednoho FBX souboru (jeden profil) na jeden GLB
soubor pouzitelny primo ve 3D scene (webapp/katalog/<id>.glb).

bot1, 2026-07-27. Robert: "jakmile se fbx modely nahrajou supni je do
sceny do katalogu" - navazuje na admin FBX upload pole (viz
admin_profily_fbx_upload() v app.py). Na rozdil od puvodniho
convert_fbx_catalog.py (ktery zpracovaval JEDEN velky FBX se stovkami
pojmenovanych objektu jako cely katalog) tohle ocekava, ze Robert
nahraje FBX vzdy jen s JEDNIM profilem (jeden mesh, nebo par mesh
kousku tvoricich dohromady jeden dil - napr. hlavni telo + pripadne
oddelene sub-meshe stejneho profilu). Vsechny nedegenerovane meshe v
souboru se sloucí do jedne GLB geometrie (stejny pristup jako u
puvodniho SSE baked-world importu).

Pouziti:
    from fbx_convert import convert_single_fbx
    ok, info = convert_single_fbx("/cesta/k/profil.fbx", "/cesta/vystup.glb")
    # ok: bool, info: dict s detaily (dims_mm, vertices, faces, watertight, error)
"""
import numpy as np
import trimesh
import assimp_py as ai

MIN_DIM_MM = 0.5  # stejny prah jako v convert_fbx_catalog.py - objekty s
                   # 2+ rozmery temer nulovymi jsou povazovany za
                   # referencni krivky/body, ne skutecnou geometrii dilu.


def _mesh_to_trimesh(m):
    verts = np.frombuffer(m.vertices, dtype=np.float32).reshape(-1, 3).astype(np.float64)
    faces = np.frombuffer(m.indices, dtype=np.uint32).reshape(-1, 3).astype(np.int64)
    tm = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    # DULEZITE (stejna poznamka jako v convert_fbx_catalog.py): bez tohoto
    # radku GLB export neobsahuje NORMAL atribut a dil se ve Three.js
    # zobrazuje temer cerny bez ohledu na barvu materialu.
    _ = tm.vertex_normals
    return tm


def _is_degenerate(dims_mm):
    near_zero = sum(1 for d in dims_mm if d < MIN_DIM_MM)
    return near_zero >= 2


def convert_single_fbx(fbx_path, glb_path):
    """Vrati (True, info) pri uspechu, (False, info) pri selhani. info vzdy
    obsahuje aspon 'error' (None pri uspechu) - volajici kod (viz
    admin_profily_fbx_upload) rozhoduje, jak s vysledkem nalozit (aktualizace
    cfg_dily.glb_file/visible_in_scene jen pri uspechu)."""
    info = {
        "error": None, "dims_mm": None, "vertices": None,
        "faces": None, "watertight": None, "mesh_count": 0,
    }
    try:
        scene = ai.import_file(fbx_path, ai.Process_Triangulate)
    except Exception as e:
        info["error"] = f"Nepodařilo se načíst FBX (poškozený soubor nebo nepodporovaný formát): {e}"
        return False, info

    if not scene.meshes:
        info["error"] = "FBX soubor neobsahuje žádnou geometrii (mesh)."
        return False, info

    valid_meshes = []
    for m in scene.meshes:
        try:
            tm = _mesh_to_trimesh(m)
        except Exception:
            continue
        bbox = tm.bounds
        dims_mm = [round(float(x), 2) for x in (bbox[1] - bbox[0])]
        if _is_degenerate(dims_mm):
            continue  # referencni krivka/bod, ne skutecna geometrie
        valid_meshes.append(tm)

    if not valid_meshes:
        info["error"] = "Ve FBX souboru nebyla nalezena žádná použitelná geometrie (jen degenerované/referenční objekty)."
        return False, info

    try:
        combined = trimesh.util.concatenate(valid_meshes) if len(valid_meshes) > 1 else valid_meshes[0]
        _ = combined.vertex_normals  # zajisti normaly i po concatenate
        combined.export(glb_path)
    except Exception as e:
        info["error"] = f"Převod/export do GLB selhal: {e}"
        return False, info

    bbox = combined.bounds
    dims_mm = [round(float(x), 2) for x in (bbox[1] - bbox[0])]
    info.update({
        "dims_mm": dims_mm,
        "vertices": int(len(combined.vertices)),
        "faces": int(len(combined.faces)),
        "watertight": bool(combined.is_watertight),
        "mesh_count": len(valid_meshes),
    })
    return True, info
