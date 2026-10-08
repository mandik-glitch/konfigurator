"""Auta: strom Znacka -> Model -> karoserie (Robert 2026-08-05, format
zdrojovych souboru potvrzen jako FBX) - sprava jen admin, stejny princip
jako u custom_shape_categories (jen admin zaklada/maze/prejmenovava,
prohlizeni/vkladani do sceny smi kazdy prihlaseny). + samostatny
karoserie-model-reference (Robert 2026-08-22): plocha mapa vendor kodu
na oficialni rozmerove specifikace pro hover kartu v panelu Vlastni
tvary.

Vycleneno z api/app.py (bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 10) - cisty presun, zadna zmena chovani/URL.
"""
import glob
import os

from flask import request, jsonify
from werkzeug.utils import secure_filename

from app import (
    app,
    get_conn,
    login_required,
    staff_required,
    admin_required,
    current_user,
    log_audit,
    CAR_GLB_DIR,
    CAR_FBX_UPLOAD_DIR,
    convert_uploaded_model_to_glb,
)


@app.get("/api/karoserie-model-reference")
@login_required
def karoserie_model_reference_list():
    # Robert 2026-08-22: hover karta s rozmery karoserie v panelu Vlastni
    # tvary (webapp/scene.html buildShapeButtons) - plocha mapa kod->
    # specifikace, puvodne naparovana na nase tvary pres "[XXNN]" vendor kod
    # v nazvu. bot8 2026-09-06 (URGENTNI, Robert "nesmime pouzivat puvodni
    # oznaceni karoserii"): tenhle vendor kod uz neni stabilni identifikator
    # (prejmenovavame ho na vlastni schema) - klic zmenen z `legacy_vendor_code`
    # na `car_models_id` (sloupec pridany a dobackfillovany PRED samotnym
    # prejmenovanim car_models.name, viz AGENTS_LOG.md), tvary v custom_shapes
    # maji odpovidajici vlastni sloupec `car_model_id` (viz api/custom_shapes.py).
    # Radky bez sparovaneho car_models_id (starsi karoserie referencni data bez
    # vlastniho 3D tvaru, ~15 z 319) se preskoci - nemely pouzitelny klic ani
    # drive (zadny tvar na ne stejne neodkazoval).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT car_models_id, real_name, manufacturer, model_range, "
                "overall_text, wheelbase_mm, cargo_text, cargo_volume_m3, "
                "official_door_opening_height_mm, official_door_opening_source, "
                "official_side_door_height_mm, official_side_door_source, "
                "official_side_door_width_mm, official_side_door_width_source, "
                "official_wheel_arch_width_mm, official_wheel_arch_width_source "
                "FROM karoserie_model_reference WHERE car_models_id IS NOT NULL"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    result = {}
    for r in rows:
        result[str(r["car_models_id"])] = {
            "name": r["real_name"],
            "manufacturer": r["manufacturer"],
            "model_range": r["model_range"],
            "overall": r["overall_text"],
            "wheelbase_mm": r["wheelbase_mm"],
            "cargo": r["cargo_text"],
            "volume_m3": float(r["cargo_volume_m3"]) if r["cargo_volume_m3"] is not None else None,
            # Robert 2026-08-22 ("oficialni vysky dveri od vyrobcu uvadejme
            # jako druhou 3D kotu"): rucne dohledana/zkrizovana data
            # (bot10, backups/2026-08-22_door_height_reconciliation_*) -
            # NEZAVISLA na nasi vlastni zmerene geometrii (viz
            # computeCarBodyDoorDimensionSegments ve scene.html).
            "official_door_height_mm": r["official_door_opening_height_mm"],
            "official_door_height_source": r["official_door_opening_source"],
            # Robert 2026-08-22 ("stejnym zpusobem... rozmery otvoru bocnich
            # dveri"): jen vyrobcova hodnota, bez vlastni zmerene (geometrie
            # bocnich dveri nema spolehlivy signal, viz AGENTS_LOG).
            "official_side_door_height_mm": r["official_side_door_height_mm"],
            "official_side_door_source": r["official_side_door_source"],
            # Robert 2026-08-22 ("u bočních dveří potřebujeme 2 koty, výšku
            # a šířku otvoru dveří"): druhy rozmer bocnich dveri, stejny
            # zdroj/princip jako vyska.
            "official_side_door_width_mm": r["official_side_door_width_mm"],
            "official_side_door_width_source": r["official_side_door_width_source"],
            # Robert 2026-08-22 ("přidej kotu: rozměr mezi podběhy"): sirka
            # nakladoveho prostoru mezi podbehy kol - jen vyrobcova hodnota
            # (Robert: "koty pro karoserie ve scene budeme tahat pouze z
            # oficialnich zdroju"), zadna vlastni geometricka - L/R_D/B
            # dily nemaji modelovanou podlahu s podbehy vubec (overeno).
            "official_wheel_arch_width_mm": r["official_wheel_arch_width_mm"],
            "official_wheel_arch_width_source": r["official_wheel_arch_width_source"],
        }
    return jsonify({"models": result})


# --- Auta: strom Znacka -> Model -> karoserie (Robert 2026-08-05,
# format zdrojovych souboru potvrzen jako FBX) - sprava jen admin,
# stejny princip jako u custom_shape_categories (jen admin zaklada/
# maze/prejmenovava, prohlizeni/vkladani do sceny smi kazdy prihlaseny). ---

def _build_car_tree(cur):
    cur.execute("SELECT id, name, sort_order FROM car_makes ORDER BY sort_order, name")
    makes = cur.fetchall()
    cur.execute("SELECT id, make_id, name, sort_order FROM car_models ORDER BY sort_order, name")
    models_by_make = {}
    for m in cur.fetchall():
        models_by_make.setdefault(m["make_id"], []).append(m)
    cur.execute(
        "SELECT id, model_id, name, sort_order, glb_file, original_filename, conversion_error, uploaded_at "
        "FROM car_bodies ORDER BY sort_order, name"
    )
    bodies_by_model = {}
    for b in cur.fetchall():
        bodies_by_model.setdefault(b["model_id"], []).append({
            "id": b["id"], "name": b["name"], "sort_order": b["sort_order"],
            "glb_file": ("auta/" + b["glb_file"]) if b["glb_file"] else None,
            "original_filename": b["original_filename"],
            "conversion_error": b["conversion_error"],
            "uploaded_at": b["uploaded_at"].isoformat() if b["uploaded_at"] else None,
        })
    return [
        {
            "id": mk["id"], "name": mk["name"], "sort_order": mk["sort_order"],
            "models": [
                {
                    "id": md["id"], "name": md["name"], "sort_order": md["sort_order"],
                    "bodies": bodies_by_model.get(md["id"], []),
                }
                for md in models_by_make.get(mk["id"], [])
            ],
        }
        for mk in makes
    ]


@app.get("/api/car-makes-tree")
@login_required
def car_makes_tree():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            tree = _build_car_tree(cur)
    finally:
        conn.close()
    return jsonify({"tree": tree})


@app.post("/api/car-makes")
@admin_required
def car_makes_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název značky."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_makes WHERE name=%s", (name,))
            if cur.fetchone():
                return jsonify({"error": "Značka se stejným názvem už existuje."}), 400
            cur.execute("INSERT INTO car_makes (name) VALUES (%s)", (name,))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "car_make", new_id, name)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/car-makes/<int:make_id>")
@admin_required
def car_makes_update(make_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Vyplň název značky."}), 400
        fields.append("name=%s"); params.append(name)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_makes WHERE id=%s", (make_id,))
            if not cur.fetchone():
                return jsonify({"error": "Značka neexistuje."}), 404
            params.append(make_id)
            cur.execute(f"UPDATE car_makes SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "car_make", make_id, ", ".join(fields))
    return jsonify({"status": "ok"})


def _delete_car_body_files(body_id, glb_file):
    """Fyzicky smaze GLB VYSTUP i zdrojovy FBX/STEP soubor karoserie.
    Zdrojovy soubor nema priponu ulozenou v DB (jen v nazvu na disku,
    <id>.<ext>) - proto glob misto primeho os.remove."""
    if glb_file:
        try:
            os.remove(os.path.join(CAR_GLB_DIR, glb_file))
        except OSError:
            pass
    for src in glob.glob(os.path.join(CAR_FBX_UPLOAD_DIR, f"{body_id}.*")):
        try:
            os.remove(src)
        except OSError:
            pass


def _delete_car_glb_files(cur, model_ids=None, make_ids=None):
    """Fyzicky smaze soubory VSECH karoserii v danych modelech/znackach
    PRED DB DELETE (kaskada by jinak radky smazala, ale soubory na
    disku by osirely) - stejny vzor jako drive_admin_folder_delete v
    api/drive.py."""
    where, params = [], []
    if model_ids:
        where.append(f"model_id IN ({','.join(['%s']*len(model_ids))})"); params += model_ids
    if make_ids:
        cur.execute(f"SELECT id FROM car_models WHERE make_id IN ({','.join(['%s']*len(make_ids))})", make_ids)
        ids = [r["id"] for r in cur.fetchall()]
        if not ids:
            return
        where = [f"model_id IN ({','.join(['%s']*len(ids))})"]; params = ids
    if not where:
        return
    cur.execute(f"SELECT id, glb_file FROM car_bodies WHERE {' AND '.join(where)}", params)
    for r in cur.fetchall():
        _delete_car_body_files(r["id"], r["glb_file"])


@app.delete("/api/car-makes/<int:make_id>")
@admin_required
def car_makes_delete(make_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_makes WHERE id=%s", (make_id,))
            if not cur.fetchone():
                return jsonify({"error": "Značka neexistuje."}), 404
            _delete_car_glb_files(cur, make_ids=[make_id])
            cur.execute("DELETE FROM car_makes WHERE id=%s", (make_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_make", make_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/car-makes/<int:make_id>/models")
@admin_required
def car_models_create(make_id):
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název modelu."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_makes WHERE id=%s", (make_id,))
            if not cur.fetchone():
                return jsonify({"error": "Značka neexistuje."}), 404
            cur.execute("SELECT id FROM car_models WHERE make_id=%s AND name=%s", (make_id, name))
            if cur.fetchone():
                return jsonify({"error": "Model se stejným názvem u téhle značky už existuje."}), 400
            cur.execute("INSERT INTO car_models (make_id, name) VALUES (%s,%s)", (make_id, name))
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "car_model", new_id, name)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/car-models/<int:model_id>")
@admin_required
def car_models_update(model_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Vyplň název modelu."}), 400
        fields.append("name=%s"); params.append(name)
    if "make_id" in body:
        new_make = body.get("make_id")
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM car_makes WHERE id=%s", (new_make,))
                if not cur.fetchone():
                    return jsonify({"error": "Cílová značka neexistuje."}), 400
        finally:
            conn.close()
        fields.append("make_id=%s"); params.append(new_make)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_models WHERE id=%s", (model_id,))
            if not cur.fetchone():
                return jsonify({"error": "Model neexistuje."}), 404
            params.append(model_id)
            cur.execute(f"UPDATE car_models SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "car_model", model_id, ", ".join(fields))
    return jsonify({"status": "ok"})


@app.delete("/api/car-models/<int:model_id>")
@admin_required
def car_models_delete(model_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_models WHERE id=%s", (model_id,))
            if not cur.fetchone():
                return jsonify({"error": "Model neexistuje."}), 404
            _delete_car_glb_files(cur, model_ids=[model_id])
            cur.execute("DELETE FROM car_models WHERE id=%s", (model_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_model", model_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/car-models/<int:model_id>/bodies")
@admin_required
def car_bodies_upload(model_id):
    """Upload jedne karoserie (Robert: "postupně" nahraje vic souboru -
    admin UI tohle vola opakovane, jeden request na soubor, at castecne
    selhani neshodi zbytek davky). FBX/STEP -> GLB stejnou pipeline jako
    profily katalogu (convert_uploaded_model_to_glb) - selhani prevodu
    NEshodi upload, jen se karoserie ulozi bez glb_file a s
    conversion_error (stejny failure-safe vzor jako admin_profily_fbx_upload)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_models WHERE id=%s", (model_id,))
            if not cur.fetchone():
                return jsonify({"error": "Model neexistuje."}), 404
    finally:
        conn.close()

    name = (request.form.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název karoserie/velikosti."}), 400
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    src_ext = os.path.splitext(safe_name)[1].lower()
    if src_ext not in (".fbx", ".stp", ".step"):
        return jsonify({"error": "Očekávám soubor .fbx, .stp nebo .step."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO car_bodies (model_id, name, original_filename, uploaded_by, uploaded_at) "
                "VALUES (%s,%s,%s,%s,NOW())",
                (model_id, name, safe_name, admin["id"]),
            )
            body_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    src_path = os.path.join(CAR_FBX_UPLOAD_DIR, f"{body_id}{src_ext}")
    f.save(src_path)
    glb_name = f"{body_id}.glb"
    glb_dest = os.path.join(CAR_GLB_DIR, glb_name)
    ok, info = convert_uploaded_model_to_glb(src_path, glb_dest)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if ok:
                cur.execute("UPDATE car_bodies SET glb_file=%s, conversion_error=NULL WHERE id=%s", (glb_name, body_id))
            else:
                cur.execute("UPDATE car_bodies SET conversion_error=%s WHERE id=%s", (info.get("error"), body_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(
        admin["id"], "upload" if ok else "upload_convert_failed", "car_body", body_id,
        f"{name} ({safe_name}): {'OK' if ok else info.get('error')}",
    )
    return jsonify({
        "status": "ok", "id": body_id, "name": name,
        "conversion": {"success": ok, "error": info.get("error")},
    }), 201


@app.put("/api/car-bodies/<int:body_id>")
@admin_required
def car_bodies_update(body_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Vyplň název karoserie."}), 400
        fields.append("name=%s"); params.append(name)
    if "model_id" in body:
        new_model = body.get("model_id")
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM car_models WHERE id=%s", (new_model,))
                if not cur.fetchone():
                    return jsonify({"error": "Cílový model neexistuje."}), 400
        finally:
            conn.close()
        fields.append("model_id=%s"); params.append(new_model)
    if "sort_order" in body:
        try:
            fields.append("sort_order=%s"); params.append(int(body.get("sort_order") or 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné pořadí."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM car_bodies WHERE id=%s", (body_id,))
            if not cur.fetchone():
                return jsonify({"error": "Karoserie neexistuje."}), 404
            params.append(body_id)
            cur.execute(f"UPDATE car_bodies SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "car_body", body_id, ", ".join(fields))
    return jsonify({"status": "ok"})


@app.delete("/api/car-bodies/<int:body_id>")
@admin_required
def car_bodies_delete(body_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT glb_file FROM car_bodies WHERE id=%s", (body_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Karoserie neexistuje."}), 404
            _delete_car_body_files(body_id, row["glb_file"])
            cur.execute("DELETE FROM car_bodies WHERE id=%s", (body_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "car_body", body_id, None)
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Karoserie GLB jen pro prihlasene (bot8, 2026-09-05)
#
# Robert: "Zaridit at to neni dostupne nejoptimalnejsi cestou" - po zjisteni,
# ze cela knihovna karoserii (912 souboru / 259 MB, 304 vozidel) sla stahnout
# z verejne adresy BEZ prihlaseni.
#
# PRICINA byla v tom, ze soubory vubec neprochazely aplikaci: nginx je
# servíroval statickym aliasem `location /katalog/`, ktery o Flasku ani
# o session nic nevi. Chraneny byl jen SEZNAM (`/api/katalog` -> 401), ne
# samotne soubory - a to vypada jako hotova vec, dokud nezkusis stahnout
# konkretni soubor.
#
# RESENI je X-Accel-Redirect: autorizuje Flask, ale prenos bytu delá dal
# nginx, takze rychlost zustava stejna jako u statickeho souboru (Flask
# neposila zadna data, jen hlavicku s cestou). Alternativa `auth_request`
# by znamenala dotaz navic u KAZDEHO ze 123 dilu sestavy.
#
# Zbytek katalogu (profily, spojky, euroboxy, desky) zustava verejny - jsou
# to modely zbozi, ktere se prodava, neni co chranit.
#
# PROC @staff_required A NE @login_required: registrace je samoobsluzna
# (/api/auth/register), takze @login_required by pustil kohokoli, kdo si
# zalozi ucet. Presne pred tim varuje docstring u staff_required (bezpecnostni
# nalez bot3, 2026-09-02: "plain @login_required pousti i role='user'").
# Katalog sceny (/api/katalog) je taky @staff_required - tohle je jen
# srovnani souboru se seznamem, ktery uz chraneny byl.
CAR_BODIES_DIR = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "katalog", "car_bodies")
)
# Interni nginx location, kterou umi vyvolat jen X-Accel-Redirect (ma `internal;`),
# nikdy ne prohlizec primo.
CAR_BODIES_XACCEL_PREFIX = "/_car_bodies_internal/"


@app.get("/api/car-body-file/<path:fname>")
@staff_required
def car_body_file(fname):
    from urllib.parse import quote
    from flask import make_response

    # Cesta musi zustat UVNITR car_bodies/ - realpath az po spojeni, aby
    # neprosly ani "..", ani symlink ven, ani absolutni cesta.
    cesta = os.path.realpath(os.path.join(CAR_BODIES_DIR, fname))
    if not cesta.startswith(CAR_BODIES_DIR + os.sep):
        return jsonify({"error": "neplatna cesta"}), 400
    if not fname.lower().endswith(".glb") or not os.path.isfile(cesta):
        return jsonify({"error": "nenalezeno"}), 404

    # X-Accel-Redirect musi byt URL-zakodovany: nazvy obsahuji diakritiku
    # ("Citroën_Jumpy_...") a Flask nam je predal uz dekodovane. Bez quote()
    # by nginx cestu nenasel.
    rel = os.path.relpath(cesta, CAR_BODIES_DIR)
    resp = make_response("")
    resp.headers["X-Accel-Redirect"] = CAR_BODIES_XACCEL_PREFIX + quote(rel)
    resp.headers["Content-Type"] = "model/gltf-binary"
    # Privatni cache: soubor smi drzet jen prohlizec prihlaseneho uzivatele,
    # ne sdilena proxy (puvodni staticky blok mel "public", coz dovolovalo
    # ulozeni i cizim cache).
    resp.headers["Cache-Control"] = "private, max-age=3600"
    return resp
