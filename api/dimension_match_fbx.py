"""
dimension_match_fbx.py - rozklad SUROVEHO FBX na katalogove profily podle
ROZMERU (ne podle nazvu meshe) - bot6, 2026-08-09.

Puvod: scripts/dimension_match_fbx_to_custom_shape.py (bot4, 2026-08-09,
"když nahraju fbx model k produktu... potřebuju aby rozeznal jednotlivé
díly, tuto proceduru jsme v minulosti zapsali, najdi to"). Robert pak
chtel totez primo z tlacitka na skladove karte ("tak tento script uloz
pod tlacitkem Prevod... jak budou pribyvat polozky v katalogu ve scene,
bude script rozpoznavat vice a vice polozek") - jadro logiky (match_meshes/
build_parts) presunuto sem, aby ho sdilel jak puvodni CLI skript (viz
scripts/dimension_match_fbx_to_custom_shape.py, ted uz jen tenky wrapper),
tak novy endpoint POST /api/shop/products/<id>/decompose-fbx.

"Bude script rozpoznavat vice a vice polozek" - ANO automaticky: katalog
se cte pokazde znovu z DB (_catalog_profiles_by_cross_section, viz
leg_fbx_import.py), zadne hardcodovane/cachovane seznamy profilu. Jakmile
pribude novy profil s GLB do katalogu, dalsi spusteni ho uz bere v uvahu
bez jakekoli zmeny kodu.

Souradnicova konvence a zbytek principu - viz puvodni docstring skriptu
(FBX Z-up -> scene Y-up, shoda prurezu v tolerance, jen hlinikova kostra
bez sroubu/desek/plastu).

OPRAVA 2026-08-10 (bot6, Robertovo podezreni "chybne nastavene spoje maji
objekty importovane pres tenhle script"): potvrzeno - build_parts() dosud
NEUKLADALA zadnou informaci o spojich (lic_peers) mezi rozpoznanymi
profily, takze kazdy takto vlozeny tvar mel ve scene VZDY 0 spoju, i kdyz
jde o realne sestavenou konstrukci (viditelne dotykajici se dily). Az
nasledna rucni interakce ve scene (tazeni, Pripoj2) spoje nekonzistentne
dopocitavala - presne zdroj chybnych/neuplnych poctu spoju u takhle
importovanych sestav. Opraveno: compute_lic_peers() spocita skutecne
geometricke doteky MEZI rozpoznanymi profily (stejny princip "dotyk
plochy" jako drivejsi 'Najdi spoje' ve scene.html) primo z CISTYCH FBX
souradnic (pred jakymkoli pozdejsim pripojovacim odsazenim), a
build_parts() vysledek ulozi do parts[i]["lic_peers"] - insertCustomShape()
ve scene.html pak jointCount rekonstruuje presne z techto dat hned pri
vlozeni tvaru do sceny, misto aby zustaval na 0.

OPRAVA 2026-10-02 (bot8, nalez bot10: stul #577 hlasil po nacteni 32 spoju,
geometrie 26; stejne #572, #524 53 vs 35): _profiles_touch() pozadoval na
zbylych 2 osach jen prekryv >= -0,5 mm, takze STACILO, ze se dva profily
dotykaji HRANOU (u noh a pricek stolu 6 paru) - a scena (insertCustomShape)
kazdy par z lic_peers po nacteni zapocita do spoju. Robertova definice
(2026-08-31, PRAVIDLA_SPOJU.md): spoj existuje jen kdyz se CELA plocha cela
jednoho profilu dotyka cela/steny druheho - stejny test uz od 2026-08-31 pouziva
scene.html autoRegisterTouchedProfileJoints (prekryv na obou zbylych osach
>= mensi rozmer - 0,5 mm). Nyni stejne kriterium i tady (EPS_FACE_MM zustava
1,5 mm - cista CAD data). Kontrola: QA check lic_peers_neni_spoj (qa_checks.py).
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter

import numpy as np
from flask import jsonify, request
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, current_user, require_permission, CUSTOM_SHAPE_MAX_PARTS, PRODUCT_FBX_UPLOAD_DIR,
    fetch_katalog_parts, _validate_custom_shape_parts, _validate_custom_shape_relations,
)
from leg_fbx_import import _catalog_profiles_by_cross_section, _S2

MIN_LENGTH_MM = 100.0  # kratsi kusy nemaji smysl jako "rezany profil"

# Robert 2026-08-09 ("stejnou formou, vlozim soubor stisknu prevod") -
# primy upload FBX (bez vazby na existujici produkt).
# bot16 2026-09-03 (revize bot3): drive se nahrany FBX ukladal natrvalo do
# webapp/content-files/dimension_match_fbx/ - tu slozku ale nginx servíruje
# VEREJNE (/content-files/), takze sly cizi 3D modely stahnout bez loginu.
# Soubor se po rozboru uz nikdy nepouzije (vysledek jde rovnou do
# custom_shapes), proto ted jen docasny adresar smazany hned po analyze.
# Cteni FBX bezi v SUBPROCESU s timeoutem (assimp = C knihovna, podvrzeny
# soubor nesmi shodit gunicorn worker) - viz fbx_mesh_bounds_worker.py.
FBX_BOUNDS_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fbx_mesh_bounds_worker.py")
FBX_READ_TIMEOUT_SEC = 60  # FBX profilu jsou male, realne jednotky sekund


def _read_fbx_mesh_bounds(fbx_path):
    """Vrati (meshes, total) z workeru; ValueError s citelnou hlaskou pri selhani."""
    cmd = [sys.executable, FBX_BOUNDS_WORKER, fbx_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=FBX_READ_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise ValueError(f"Čtení FBX trvalo déle než {FBX_READ_TIMEOUT_SEC} s a bylo zastaveno.")
    except OSError as e:
        raise ValueError(f"Nepodařilo se spustit čtení FBX: {e}")
    try:
        result = json.loads((proc.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise ValueError(f"Čtení FBX selhalo (exit={proc.returncode}). {(proc.stderr or '')[-300:]}")
    if not result.get("ok"):
        raise ValueError(result.get("error") or "Neznámá chyba čtení FBX.")
    return result.get("meshes") or [], int(result.get("total") or 0)


def match_meshes(fbx_path, catalog, tolerance):
    """Vrati (profile_meshes, total_count). profile_meshes ma bb_min/bb_max
    uz PREVEDENE do scene souradnic (scene_x=fbx_y, scene_y=fbx_z,
    scene_z=fbx_x)."""
    meshes, total = _read_fbx_mesh_bounds(fbx_path)
    if not total:
        raise ValueError("FBX neobsahuje žádnou geometrii.")

    profile_meshes = []
    for m in meshes:
        bb_min = np.array(m["bb_min"], dtype=np.float64)
        bb_max = np.array(m["bb_max"], dtype=np.float64)
        size = bb_max - bb_min
        dims_sorted = sorted(size.tolist())
        a, b, c = dims_sorted
        if c < MIN_LENGTH_MM:
            continue
        for cross in catalog.keys():
            w_, h_ = cross
            if abs(a - w_) <= tolerance and abs(b - h_) <= tolerance:
                profile_meshes.append({"name": m["name"], "cross": cross, "bb_min": bb_min, "bb_max": bb_max})
                break
    return profile_meshes, total


EPS_FACE_MM = 1.5  # tolerance "blizkosti plochy" na dotykove ose
EPS_OVERLAP_MM = 0.5  # tolerance pozadovaneho prekryvu na zbylych 2 osach (od mensiho rozmeru)


def _profiles_touch(bb_min_a, bb_max_a, bb_min_b, bb_max_b):
    """Test 'dotyk plochy' mezi 2 bounding boxy (stejny princip, jaky drive
    pouzivalo 'Najdi spoje' ve scene.html - viz AGENTS_LOG 2026-08-10,
    bot6): na JEDNE ose se plochy priblizi na EPS_FACE_MM, na ZBYLYCH 2
    osach se REALNE prekryvaji (ne jen jsou nablizku). Na rozdil od tehdejsi
    runtime heuristiky (ktera resila uz OFSETOVANE/pripojene dily v ruzne
    pozici behem tazeni) tady jde o PRIME nezkreslene FBX souradnice z CAD
    modelu - zadne dodatecne odsazeni pri "pripojovani" se jeste
    neaplikovalo, takze bezny dotyk bounding-boxu spolehlive odpovida
    SKUTECNE navrzene sestave."""
    for axis in range(3):
        face_close = (abs(bb_max_a[axis] - bb_min_b[axis]) < EPS_FACE_MM
                      or abs(bb_min_a[axis] - bb_max_b[axis]) < EPS_FACE_MM)
        if not face_close:
            continue
        overlaps = True
        for other in range(3):
            if other == axis:
                continue
            lo = max(bb_min_a[other], bb_min_b[other])
            hi = min(bb_max_a[other], bb_max_b[other])
            # definice spoje (Robert 2026-08-31): prekryv musi pokryt CELOU mensi
            # plochu - dotyk jen hranou/rohem (prekryv ~0) spoj NENI
            min_size = min(bb_max_a[other] - bb_min_a[other], bb_max_b[other] - bb_min_b[other])
            if hi - lo < min_size - EPS_OVERLAP_MM:
                overlaps = False
                break
        if overlaps:
            return True
    return False


def compute_lic_peers(profile_meshes):
    """Vrati {index: sorted[indexy dotykajicich se sousedu]} pro vsechny
    rozpoznane profily (viz _profiles_touch) - pouziva se k predvyplneni
    lic_peers ulozeneho tvaru, aby vlozeny tvar mel spoje spravne
    SPOCITANE HNED (insertCustomShape() ve scene.html jointCount
    rekonstruuje presne z techto dat), misto aby zustaly na 0 a doufaly v
    nahodne pozdejsi rucni/auto-dotykove doplneni ve scene."""
    n = len(profile_meshes)
    peers = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if _profiles_touch(profile_meshes[i]["bb_min"], profile_meshes[i]["bb_max"],
                                profile_meshes[j]["bb_min"], profile_meshes[j]["bb_max"]):
                peers[i].add(j)
                peers[j].add(i)
    return {i: sorted(s) for i, s in peers.items()}


def count_lic_peer_pairs(parts):
    """Pocet UNIKATNICH dvojic spoju v ulozenych parts (kazda dvojice je v
    lic_peers zapsana symetricky na obou stranach, proto /2) - pouziva se
    jen pro informativni hlasku po prevodu (kolik spoju se naslo), ne pro
    ukladana data samotna."""
    return sum(len(p.get("lic_peers") or []) for p in parts) // 2


def build_parts(profile_meshes, catalog):
    """Stejna logika jako leg_fbx_import.parse_leg_fbx (normalizace na
    global_min, kvaternion podle delkove osy, scale = actual_len/L0) -
    jen mesh selection je podle rozmeru, ne podle nazvu."""
    global_min = np.min([p["bb_min"] for p in profile_meshes], axis=0)
    lic_peers = compute_lic_peers(profile_meshes)
    parts = []
    for idx, p in enumerate(profile_meshes):
        lo = p["bb_min"] - global_min
        hi = p["bb_max"] - global_min
        size = hi - lo
        length_axis = int(np.argmax(size))
        actual_len = float(size[length_axis])
        cat = catalog[p["cross"]]
        if length_axis == 1:
            quat = [0.0, 0.0, 0.0, 1.0]
        elif length_axis == 0:
            quat = [0.0, 0.0, -_S2, _S2]
        else:
            quat = [_S2, 0.0, 0.0, _S2]
        center = (lo + hi) / 2.0
        part = {
            "part_id": cat["id"],
            "position": [round(float(v), 2) for v in center],
            "quaternion": [round(float(v), 6) for v in quat],
            "scale": [1.0, round(actual_len / cat["L0"], 6), 1.0],
        }
        if lic_peers[idx]:
            part["lic_peers"] = lic_peers[idx]
        parts.append(part)
    global_max = np.max([p["bb_max"] for p in profile_meshes], axis=0) - global_min
    dims = {"width_x": round(float(global_max[0]), 1), "height_y": round(float(global_max[1]), 1), "depth_z": round(float(global_max[2]), 1)}
    return parts, dims


@app.post("/api/shop/products/<int:product_id>/decompose-fbx")
@require_permission("rozklad_fbx", "upravit")
def shop_products_decompose_fbx(product_id):
    # Robert: "tak tento script uloz pod tlacitkem Prevod do skladovych
    # karet" - stejny zdrojovy soubor jako /convert-to-glb (surovy FBX/STP
    # v PRODUCT_FBX_UPLOAD_DIR, {product_id}.<pripona>), zadny novy upload.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, fbx_original_name FROM shop_products WHERE id=%s", (product_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Neznámý produkt."}), 404
    if not row["fbx_original_name"]:
        return jsonify({"error": "Produkt zatím nemá nahraný žádný 3D model (STP/FBX)."}), 400

    matches = glob.glob(os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{product_id}.*"))
    if not matches:
        return jsonify({"error": "Zdrojový soubor na disku chybí (byl smazán mimo aplikaci?) - nahraj model znovu."}), 404
    src_path = matches[0]
    if not src_path.lower().endswith((".fbx",)):
        return jsonify({"error": "Rozklad na profily podporuje jen FBX zdroj (ne STP) - tenhle produkt má nahraný jiný formát."}), 400

    body = request.get_json(silent=True) or {}
    tolerance = body.get("tolerance")
    try:
        tolerance = float(tolerance) if tolerance is not None else 2.0
    except (TypeError, ValueError):
        tolerance = 2.0
    name = (body.get("name") or "").strip() or f"{row['name']} - hliníková kostra"

    catalog = _catalog_profiles_by_cross_section()
    if not catalog:
        return jsonify({"error": "V katalogu není žádný použitelný profil (GLB, centrovaný počátek)."}), 400

    try:
        profile_meshes, total = match_meshes(src_path, catalog, tolerance)
    except Exception as e:
        return jsonify({"error": f"Rozbor FBX selhal: {e}"}), 400

    if not profile_meshes:
        return jsonify({"error": "Žádný kus se neshoduje s katalogovým profilem - nic k uložení.",
                         "total_meshes": total, "recognized": 0}), 400
    if len(profile_meshes) > CUSTOM_SHAPE_MAX_PARTS:
        return jsonify({
            "error": f"Rozpoznáno {len(profile_meshes)} dílů, limit vlastního tvaru je {CUSTOM_SHAPE_MAX_PARTS} - "
                     f"zkus tolerance snížit, nebo rozděl na víc tvarů (mimo rozsah tohoto nástroje).",
            "total_meshes": total, "recognized": len(profile_meshes),
        }), 400

    parts, dims = build_parts(profile_meshes, catalog)
    from collections import Counter
    breakdown = [{"cross": f"{c[0]:.0f}x{c[1]:.0f}", "count": n}
                 for c, n in Counter(p["cross"] for p in profile_meshes).most_common()]

    data = {"parts": parts, "join_groups": [], "frame_groups": []}
    admin = current_user()
    conn2 = get_conn()
    try:
        with conn2.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_shapes (name, data, created_by, is_public) VALUES (%s,%s,%s,1)",
                (name, json.dumps(data, ensure_ascii=False), admin["id"] if admin else None),
            )
            new_id = cur.lastrowid
        conn2.commit()
    finally:
        conn2.close()

    return jsonify({
        "custom_shape_id": new_id,
        "name": name,
        "total_meshes": total,
        "recognized": len(profile_meshes),
        "breakdown": breakdown,
        "dims_mm": dims,
        "joints_found": count_lic_peer_pairs(parts),
    })


@app.post("/api/admin/decompose-fbx-upload")
@require_permission("rozklad_fbx", "upravit")
def decompose_fbx_upload():
    # Robert 2026-08-09 ("nova sekce Importy" -> "stejnou formou, vlozim
    # soubor stisknu prevod") - primy upload FBX, stejny princip jako
    # /api/admin/legs/import-fbx (leg_fbx_import.py), jen rozpoznavani
    # podle rozmeru mist nazvu meshe (viz match_meshes vyse).
    admin = current_user()
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    stem, ext = os.path.splitext(safe_name)
    if ext.lower() != ".fbx":
        return jsonify({"error": "Očekávám soubor .fbx."}), 400
    name = (request.form.get("name") or "").strip() or stem

    tol_raw = request.form.get("tolerance")
    try:
        tolerance = float(tol_raw) if tol_raw else 2.0
    except (TypeError, ValueError):
        tolerance = 2.0

    catalog = _catalog_profiles_by_cross_section()
    if not catalog:
        return jsonify({"error": "V katalogu není žádný použitelný profil (GLB, centrovaný počátek)."}), 400

    # Jen docasne - po rozboru se soubor smaze (viz komentar u
    # FBX_BOUNDS_WORKER), nic nezustava ve verejne servirovane slozce.
    with tempfile.TemporaryDirectory(prefix="dimension_match_fbx_") as td:
        dest_path = os.path.join(td, "upload.fbx")
        f.save(dest_path)
        try:
            profile_meshes, total = match_meshes(dest_path, catalog, tolerance)
        except Exception as e:
            return jsonify({"error": f"Rozbor FBX selhal: {e}"}), 400

    if not profile_meshes:
        return jsonify({"error": "Žádný kus se neshoduje s katalogovým profilem - nic k uložení.",
                         "total_meshes": total, "recognized": 0}), 400

    parts, dims = build_parts(profile_meshes, catalog)

    # Stejna validace jako u rucne ukladanych tvaru (Ctrl+S ve scene) a u
    # importu noh - kontroluje mj. i CUSTOM_SHAPE_MAX_PARTS limit.
    valid_part_ids = {p["id"] for p in fetch_katalog_parts()}
    clean_parts, err = _validate_custom_shape_parts(parts, valid_part_ids)
    if err:
        return jsonify({"error": err, "total_meshes": total, "recognized": len(profile_meshes)}), 400
    clean_jg, clean_fg, err = _validate_custom_shape_relations(None, None, len(clean_parts), clean_parts)
    if err:
        return jsonify({"error": f"Interní chyba rozkladu: {err}"}), 500

    breakdown = [{"cross": f"{c[0]:.0f}x{c[1]:.0f}", "count": n}
                 for c, n in Counter(p["cross"] for p in profile_meshes).most_common()]

    data = {"parts": clean_parts, "join_groups": clean_jg, "frame_groups": clean_fg}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_shapes (name, data, created_by, is_public) VALUES (%s,%s,%s,1)",
                (name, json.dumps(data, ensure_ascii=False), admin["id"] if admin else None),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return jsonify({
        "custom_shape_id": new_id,
        "name": name,
        "total_meshes": total,
        "recognized": len(profile_meshes),
        "breakdown": breakdown,
        "dims_mm": dims,
        "joints_found": count_lic_peer_pairs(clean_parts),
    })
