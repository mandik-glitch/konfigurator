"""
leg_fbx_import.py - hromadny import FBX modelu noh (van-racking legs) s
automatickym ROZKLADEM na jednotlive katalogove profily (bot5, 2026-08-06).

Kontext (Robert): nahrani cele nohy jako JEDNOHO slitého katalogoveho dilu
(POST /api/admin/profily/new, bot3) se ukazalo jako slepa ulicka - "scena
nezvladla pojmout jako kompatibilni se systemem z hlediska ceny, nejde
natahovat apod." Cenovy/protahovaci system pocita s jednotlivymi
hlinikovymi profily, ne s opaque blobem.

Reseni: FBX soubory z Robertova CAD exportu NEJSOU slite - obsahuji
samostatne pojmenovane meshe (overeno na noha_1_citroen_berlingo_h1_
1100_459.fbx: 8 meshu ve skupinach alu/black/plast/sroub). Hlinikove
profily maji jednoznacny nazvovy vzor `<W>x<D>x<delka>[_pripona]` (napr.
"45x45x1100_noha") a souradnice PRIMO ve world-space (transformace uzlu
jsou identity - overeno). Tenhle modul je vytahne, prevede na
custom_shapes multi-part format (stejny jako rucne skladane nohy, viz
TVARY_VLASTNI.md 2an) a zaradi do spravne kategorie podle vysky.

Osova konvence (overena empiricky, viz AGENTS_LOG 2026-08-06):
  - FBX: vyska podel Z, sirka podel Y, hloubka podel X
  - scene.html/three.js: vyska podel Y
  - trimesh GLB export osy NEKONVERTUJE (vertexy 1:1), takze mapovani
    poloh je ciste nase vec: scene_x = fbx_y, scene_y = fbx_z,
    scene_z = fbx_x (cyklicka permutace - zachovava pravotocivost).

Koncovky/deska/srouby (meshe bez nazvu ve tvaru WxDxL) se preskakuji -
Robertovo rozhodnuti "staci jen hlinikova kostra".

lic_peers/joint_count se zamerne NEpocitaji (heuristika dotyku bboxu by
byla nespolehliva) - zname zjednoduseni, jde jen o bookkeeping poctu
spoju pro cenu, ne o geometrii.
"""
import json
import os
import re
import struct

import numpy as np
import assimp_py as ai
from flask import request, jsonify
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    UPLOAD_DIR, KATALOG_GLB_DIR,
    _validate_custom_shape_parts, _validate_custom_shape_relations,
    fetch_katalog_parts,
)

LEG_FBX_UPLOAD_DIR = os.path.join(UPLOAD_DIR, "leg_fbx")
os.makedirs(LEG_FBX_UPLOAD_DIR, exist_ok=True)

# Nazvovy vzor hlinikoveho profilu uvnitr FBX: "<W>x<D>x<delka>[_cokoli]",
# volitelne s kratkou pismennou predponou rady profilu ("SL40x40x1259" =
# Super Light 40x40 - Robert 2026-08-06: stejny prurez, stejny katalogovy
# profil, jen jina rada; bez predpony to nerozpoznavalo "totozne" profily).
# Max 4 pismena predpony - delsi slova ("zaslepka_40x40", "Zaslepka_20x80")
# projit nesmi.
PROFILE_MESH_RE = re.compile(r"^[A-Za-z]{0,4}(\d+)x(\d+)x(\d+)(?:_.*)?$")

# Tolerance mezi delkou z nazvu meshe a skutecnym rozpetim bboxu - FBX
# geometrie miva zaslepky/zkoseni, ktere delku o par mm meni.
LENGTH_TOLERANCE_MM = 25.0

# Prah kategorii (Robert 2026-08-05): do 1300 mm vcetne = male, nad = velke.
HEIGHT_THRESHOLD_MM = 1300.0
CATEGORY_ROOT_NAME = "Auta dodávky"
CATEGORY_SMALL_NAME = "Nohy malé dodávky"
CATEGORY_LARGE_NAME = "Nohy velké dodávky"

_S2 = 0.7071067811865476


def _glb_axis_spans(glb_path):
    """Vrati [(min,max), (min,max), (min,max)] pro X/Y/Z z POSITION
    accessoru GLB souboru (glTF JSON chunk) - stejny postup jako ve
    TVARY_VLASTNI.md 2an."""
    with open(glb_path, "rb") as f:
        data = f.read()
    _, _, length = struct.unpack("<4sII", data[0:12])
    offset = 12
    gltf = None
    while offset < length:
        clen, ctype = struct.unpack("<II", data[offset:offset + 8])
        if ctype == 0x4E4F534A:  # "JSON"
            gltf = json.loads(data[offset + 8:offset + 8 + clen])
        offset += 8 + clen
    acc = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    return list(zip(acc["min"], acc["max"]))


def _catalog_profiles_by_cross_section():
    """Mapa {(mensi, vetsi prurez): {id, L0}} ze VSECH katalogovych
    profilu s pouzitelnym GLB. L0 = delka (nejvetsi rozmer). Zaroven
    overi, ze GLB je centrovane na vsech osach (jina konvence puvodu
    neni podporovana - radsi chybu nez tise spatne pozice)."""
    parts = fetch_katalog_parts()
    result = {}
    for p in parts:
        if p.get("source") != "profil" or not p.get("visible_in_scene"):
            continue
        dims = p.get("dims_mm") or []
        if len(dims) != 3 or any(d is None for d in dims):
            continue
        dims_sorted = sorted(float(d) for d in dims)
        cross = (dims_sorted[0], dims_sorted[1])
        length = dims_sorted[2]
        if cross in result:
            continue  # prvni vyhrava (duplicity prurezu = mesh instance z exportu)
        glb_path = os.path.join(KATALOG_GLB_DIR, (p.get("file") or "").split("?")[0].replace("katalog/", ""))
        if not os.path.exists(glb_path):
            continue
        spans = _glb_axis_spans(glb_path)
        centered = all(abs(lo + hi) < 2.0 for lo, hi in spans)
        if not centered:
            continue  # necentrovany GLB - nepodporujeme, viz docstring
        result[cross] = {"id": p["id"], "L0": length}
    return result


def parse_leg_fbx(fbx_path):
    """Rozlozi FBX na profily. Vrati (parts, meta):
    parts = custom_shapes "parts" pole (part_id/position/quaternion/scale),
    meta = {skipped: [nazvy preskocenych meshu], warnings: [...],
            total_height_mm, total_width_mm}.
    Vyhazuje ValueError s ceskou zpravou pri nepouzitelnem souboru."""
    try:
        scene = ai.import_file(fbx_path, ai.Process_Triangulate)
    except Exception as e:
        raise ValueError(f"Nepodařilo se načíst FBX: {e}")

    if not scene.meshes:
        raise ValueError("FBX neobsahuje žádnou geometrii.")

    catalog = _catalog_profiles_by_cross_section()
    if not catalog:
        raise ValueError("V katalogu není žádný použitelný profil (GLB).")

    profile_meshes = []
    skipped = []
    for m in scene.meshes:
        name = m.name or ""
        match = PROFILE_MESH_RE.match(name)
        if not match:
            skipped.append(name or "(nepojmenovaný)")
            continue
        w, d, declared_len = (float(match.group(i)) for i in (1, 2, 3))
        verts = np.frombuffer(m.vertices, dtype=np.float32).reshape(-1, 3)
        # FBX -> scene: scene_x = fbx_y, scene_y = fbx_z, scene_z = fbx_x
        scene_pts = verts[:, [1, 2, 0]].astype(np.float64)
        bb_min = scene_pts.min(axis=0)
        bb_max = scene_pts.max(axis=0)
        profile_meshes.append({
            "name": name, "cross": tuple(sorted((w, d))),
            "declared_len": declared_len, "bb_min": bb_min, "bb_max": bb_max,
        })

    if not profile_meshes:
        raise ValueError(
            "FBX neobsahuje žádný mesh s názvem ve tvaru <šířka>x<hloubka>x<délka> "
            "(např. 45x45x1100_noha) - nelze rozpoznat hliníkové profily."
        )

    # Normalizace: cela sestava zacina na 0 ve vsech osach (podlaha y=0,
    # levy okraj x=0, predni hrana z=0) - stejna konvence jako rucne
    # skladane nohy.
    # Vsechny chybejici prurezy nahlasit NAJEDNOU - at Robert vidi cely
    # seznam profilu, kterym musi nahrat 3D model, ne jen prvni.
    missing_crosses = sorted({
        f"{p['cross'][0]:.0f}x{p['cross'][1]:.0f}"
        for p in profile_meshes if p["cross"] not in catalog
    })
    if missing_crosses:
        raise ValueError(
            f"Průřez(y) {', '.join(missing_crosses)} nemají v katalogu profil "
            f"s nahraným 3D modelem - nahraj jim model v Ceníku a spusť import znovu."
        )

    global_min = np.min([p["bb_min"] for p in profile_meshes], axis=0)
    warnings = []
    parts = []
    for p in profile_meshes:
        lo = p["bb_min"] - global_min
        hi = p["bb_max"] - global_min
        size = hi - lo
        length_axis = int(np.argmax(size))
        actual_len = float(size[length_axis])
        if abs(actual_len - p["declared_len"]) > LENGTH_TOLERANCE_MM:
            warnings.append(
                f"{p['name']}: délka z názvu {p['declared_len']:.0f}mm vs. "
                f"geometrie {actual_len:.0f}mm - použita geometrie."
            )
        cat = catalog[p["cross"]]
        # Kvaternion podle toho, ktera svetova osa nese delku (katalogovy
        # profil ma delku podel lokalni +Y):
        if length_axis == 1:      # delka podel scene Y (svisly sloup)
            quat = [0.0, 0.0, 0.0, 1.0]
        elif length_axis == 0:    # delka podel scene X (vodorovna pricka)
            quat = [0.0, 0.0, -_S2, _S2]
        else:                     # delka podel scene Z (do hloubky)
            quat = [_S2, 0.0, 0.0, _S2]
        center = (lo + hi) / 2.0
        parts.append({
            "part_id": cat["id"],
            "position": [round(float(v), 2) for v in center],
            "quaternion": quat,
            "scale": [1.0, round(actual_len / cat["L0"], 6), 1.0],
        })

    global_max = np.max([p["bb_max"] for p in profile_meshes], axis=0) - global_min
    meta = {
        "skipped": skipped,
        "warnings": warnings,
        "total_height_mm": round(float(global_max[1]), 1),
        "total_width_mm": round(float(global_max[0]), 1),
        "profile_count": len(parts),
    }
    return parts, meta


def _find_or_create_shape_category(cur, name, parent_id):
    """Najde/zalozi kategorii custom_shape_categories podle jmena pod danym
    rodicem (NULL-safe pres <=>). Stejny vzor jako find_or_create_lead
    (crm.py) / _find_or_create_conversation (support_email_sync.py)."""
    cur.execute(
        "SELECT id FROM custom_shape_categories WHERE parent_id <=> %s AND name=%s",
        (parent_id, name),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO custom_shape_categories (parent_id, name, created_by) VALUES (%s,%s,NULL)",
        (parent_id, name),
    )
    return cur.lastrowid


@app.post("/api/admin/legs/import-fbx")
@require_permission("ceny_profilu", "vytvorit")
def admin_legs_import_fbx():
    """Jeden FBX = jedna noha = jeden novy custom_shapes zaznam slozeny z
    KATALOGOVYCH profilu (part_id/position/quaternion/scale) - plne
    kompatibilni s cenou/natahovanim, na rozdil od slite varianty.
    Frontend vola opakovane, jeden request na soubor (izolace chyb +
    gunicorn timeout 60s na request)."""
    admin = current_user()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    stem, src_ext = os.path.splitext(safe_name)
    if src_ext.lower() != ".fbx":
        return jsonify({"error": "Očekávám soubor .fbx."}), 400
    name = (request.form.get("name") or "").strip() or stem

    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or "noha"
    dest_path = os.path.join(LEG_FBX_UPLOAD_DIR, f"{slug}.fbx")
    f.save(dest_path)

    try:
        parts, meta = parse_leg_fbx(dest_path)
    except ValueError as e:
        log_audit(admin["id"], "import_failed", "leg_fbx", None, f"{safe_name}: {e}")
        return jsonify({"error": str(e)}), 400

    # Stejna validace jako u rucne ukladanych tvaru (Ctrl+S ve scene) -
    # at nove zaznamy prochazi identickou kontrolou.
    valid_part_ids = {p["id"] for p in fetch_katalog_parts()}
    clean_parts, err = _validate_custom_shape_parts(parts, valid_part_ids)
    if err:
        return jsonify({"error": f"Interní chyba rozkladu: {err}"}), 500
    clean_jg, clean_fg, err = _validate_custom_shape_relations(None, None, len(clean_parts), clean_parts)
    if err:
        return jsonify({"error": f"Interní chyba rozkladu: {err}"}), 500

    # Robert 2026-08-06 ("uprav tak, abych mohl nahrat strom - adresare se
    # soubory"): kdyz frontend posle category_path (relativni cesta slozek
    # z vybraneho adresare, "/" oddelovac), strom adresaru se zrcadli do
    # stromu kategorii a PREBIJI automaticke pravidlo podle vysky. Bez
    # category_path (rucni vyber jednotlivych souboru) plati vyskove
    # pravidlo jako dosud.
    category_path_raw = (request.form.get("category_path") or "").strip()
    path_segments = [s.strip() for s in category_path_raw.split("/") if s.strip()]

    size_cat_name = (
        CATEGORY_SMALL_NAME if meta["total_height_mm"] <= HEIGHT_THRESHOLD_MM
        else CATEGORY_LARGE_NAME
    )
    payload = {"parts": clean_parts, "join_groups": clean_jg, "frame_groups": clean_fg}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if path_segments:
                category_id = None
                for seg in path_segments:
                    category_id = _find_or_create_shape_category(cur, seg, category_id)
                size_cat_name = "/".join(path_segments)
            else:
                root_id = _find_or_create_shape_category(cur, CATEGORY_ROOT_NAME, None)
                category_id = _find_or_create_shape_category(cur, size_cat_name, root_id)
            cur.execute(
                "INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) "
                "VALUES (%s,%s,%s,%s,1)",
                (name, category_id, json.dumps(payload), admin["id"]),
            )
            shape_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    log_audit(
        admin["id"], "import", "leg_fbx", shape_id,
        f"{safe_name}: {meta['profile_count']} profilů, výška {meta['total_height_mm']}mm -> {size_cat_name}",
    )
    return jsonify({
        "status": "ok",
        "custom_shape_id": shape_id,
        "name": name,
        "category": size_cat_name,
        "profile_count": meta["profile_count"],
        "total_height_mm": meta["total_height_mm"],
        "total_width_mm": meta["total_width_mm"],
        "skipped_meshes": meta["skipped"],
        "warnings": meta["warnings"],
    }), 201
