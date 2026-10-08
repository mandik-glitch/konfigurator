"""Vlastni tvary (custom shapes) + jejich strom kategorii - Robert: "na
scene si nakreslim nejaky objekt, oznacim ho, CTRL+S ulozi tento vyber
jako novy prednastaveny tvar, system si vyzada jeho nazev a zalozi jej
jako nove tlacitko v panelu 'Vlastni tvary'; klik na tlacitko vlozi
ulozeny objekt do sceny" (2026-07-24). Kazdy dil vyberu se uklada jako
part_id + position/quaternion/scale (+ volitelne color/used_conn), viz
frontend serializace pri Ctrl+S. Tabulka custom_shapes: id, name, data
(JSON pole dilu), created_by, created_at. Kategorie: samostatny strom od
content_categories (jina domena), zrcadleny do Sdileneho disku.

Vycleneno z api/app.py (bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 8) - cisty presun, zadna zmena chovani/URL.

Pozn.: `_validate_custom_shape_parts`/`_validate_custom_shape_relations`
ZUSTAVAJI v app.py, protoze je pouziva i product_assemblies.py (skupina
9, endpointy sestav 1:1 kopiruji strukturu vlastnich tvaru a stejne
validatory ZNOVUPOUZIVAJI beze zmeny) - tenhle modul si je jen importuje.
`_validate_custom_shape_text_labels` (a CUSTOM_SHAPE_MAX_TEXT_LABELS)
naopak pouziva jen tenhle modul, takze presla sem cela i s konstantou.
"""
import json
import os
from datetime import datetime

from flask import request, jsonify

from app import (
    app,
    get_conn,
    admin_required,
    staff_required,
    current_user,
    log_audit,
    fetch_katalog_parts,
    DRIVE_FILES_DIR,
    CUSTOM_SHAPE_MAX_PARTS,
    _validate_custom_shape_parts,
    _validate_custom_shape_relations,
    _najdi_duplicitni_role,
)

CUSTOM_SHAPE_MAX_TEXT_LABELS = 50

# bot8 2026-09-18 (Robert: "jak mame funkci preulozit sestavu, potrebuji
# to tlacitko na preulozeni libovolneho tvaru" - po vzoru product_assemblies
# resave_scene, viz api/product_assemblies.py::_zaloha_pred_resave a
# komentar u RESAVE_BACKUP_DIR tam - stejny bezpecnostni duvod (zadny
# resave nesmi prepsat data bez zalohy PREDTIM), stejny vzor (kazdy
# resave = 1 NOVY soubor, nic se neprepisuje).
RESAVE_SHAPE_BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "backups", "resave_shape")


def _zaloha_pred_resave_shape(shape_id, name, stara_data_raw):
    """Ulozi PUVODNI `data` tvaru na disk TESNE PRED prepsanim - viz
    _zaloha_pred_resave v product_assemblies.py (stejny vzor, stejny
    duvod). Zamerne NEZACHYCUJE vyjimky - volajici ma selhani zalohy
    povazovat za duvod NEPOKRACOVAT."""
    stara_data = json.loads(stara_data_raw) if stara_data_raw else None
    os.makedirs(RESAVE_SHAPE_BACKUP_DIR, exist_ok=True)
    razitko = datetime.now().strftime("%Y-%m-%dT%H-%M-%S.%f")
    nazev = f"{shape_id}_{razitko}.json"
    with open(os.path.join(RESAVE_SHAPE_BACKUP_DIR, nazev), "w", encoding="utf-8") as fh:
        json.dump({"shape_id": shape_id, "name": name, "data": stara_data}, fh, ensure_ascii=False, indent=1)
    return nazev


# bot8, 2026-08-17 (Robert: "pripises k vytvořené sestavě" text pouziteho
# tlacitka/funkce) - plovouci 3D popisky pro srovnavaci galerie ruznych
# napojovacich funkci na stejnem dilu. Sam-o-sobe neni soucasti zadneho
# dilu (na rozdil od parts[]), proto vlastni validator - jen text + poloha
# v mm, zadne vazby na jine dily.
def _validate_custom_shape_text_labels(text_labels_in):
    if text_labels_in is None:
        return [], None
    if not isinstance(text_labels_in, list):
        return None, "Neplatný formát popisků."
    if len(text_labels_in) > CUSTOM_SHAPE_MAX_TEXT_LABELS:
        return None, f"Příliš mnoho popisků (max {CUSTOM_SHAPE_MAX_TEXT_LABELS})."
    clean = []
    for tl in text_labels_in:
        if not isinstance(tl, dict):
            return None, "Neplatný popisek."
        text = tl.get("text")
        position = tl.get("position")
        if not (isinstance(text, str) and text.strip()):
            return None, "Popisek bez textu."
        if not (isinstance(position, list) and len(position) == 3 and all(isinstance(v, (int, float)) for v in position)):
            return None, "Neplatná pozice popisku."
        clean.append({"text": text.strip()[:200], "position": [float(v) for v in position]})
    return clean, None


@app.get("/api/custom-shapes")
@staff_required
def custom_shapes_list():
    # Robert 2026-07-27: "kazdy uzivatel vidi jen svoje vlastni tvary, ja
    # admin kdyz udelam vlastni tvary uvidi je vsichni" - viditelnost: verejne
    # (is_public=1, ulozene adminem) + vlastni (created_by = ja), nikdy cizi
    # soukrome. is_public je snapshot role tvurce z okamziku ulozeni (viz
    # custom_shapes_create), ne live JOIN na aktualni roli.
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, category_id, car_model_id, data, created_by, is_public, created_at FROM custom_shapes "
                "WHERE is_public=1 OR created_by=%s ORDER BY created_at DESC",
                (user["id"],),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    result = []
    for r in rows:
        try:
            parsed = json.loads(r["data"])
        except (ValueError, TypeError):
            parsed = []
        if isinstance(parsed, dict):
            parts = parsed.get("parts") or []
            join_groups = parsed.get("join_groups") or []
            frame_groups = parsed.get("frame_groups") or []
            text_labels = parsed.get("text_labels") or []
        else:
            # stary format (pred 2026-07-25): `data` bylo primo pole dilu,
            # bez spoju/skupin - nacte se beze zmeny, jen bez relaci.
            parts = parsed if isinstance(parsed, list) else []
            join_groups = []
            frame_groups = []
            text_labels = []
        result.append({
            "id": r["id"],
            "name": r["name"],
            "category_id": r["category_id"],
            # bot8 2026-09-06 (URGENTNI, Robert "nesmime pouzivat puvodni
            # oznaceni karoserii"): stabilni odkaz na car_models pro karoserie
            # ulozene jako custom_shapes ("... - karoserie (L+R_D+B)") - scene.html
            # uz na nej hover bublinu s rozmery napojuje misto parsovani kodu
            # z r["name"] (ten uz navic neni "puvodni" vendor kod, viz
            # KOMPONENTY_EUROBOXY.md/AGENTS_LOG.md prejmenovani karoserii).
            "car_model_id": r["car_model_id"],
            "parts": parts,
            "join_groups": join_groups,
            "frame_groups": frame_groups,
            "text_labels": text_labels,
            "is_public": bool(r["is_public"]),
            "mine": r["created_by"] == user["id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return jsonify({"status": "ok", "shapes": result})


@app.post("/api/custom-shapes")
@staff_required
def custom_shapes_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název tvaru."}), 400
    if len(name) > 255:
        return jsonify({"error": "Název je příliš dlouhý."}), 400
    katalog_parts = fetch_katalog_parts()
    valid_part_ids = {p["id"] for p in katalog_parts}
    clean_parts, err = _validate_custom_shape_parts(body.get("parts"), valid_part_ids)
    if err:
        return jsonify({"error": err}), 400
    clean_join_groups, clean_frame_groups, err = _validate_custom_shape_relations(
        body.get("join_groups"), body.get("frame_groups"), len(clean_parts), clean_parts
    )
    if err:
        return jsonify({"error": err}), 400
    clean_text_labels, err = _validate_custom_shape_text_labels(body.get("text_labels"))
    if err:
        return jsonify({"error": err}), 400
    user = current_user()
    is_public = 1 if user and user["role"] == "admin" else 0
    # Robert 2026-08-05 ("stromeckove... jako leve menu"): category_id
    # volitelny - klient posila ID aktivni (rozklikle) kategorie ve
    # stromu, None = "Nezarazene" (beze zmeny pro klienty, kteri to
    # zatim neposilaji).
    category_id = body.get("category_id")
    if category_id is not None:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (category_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Kategorie neexistuje."}), 400
        finally:
            conn.close()
    payload = {
        "parts": clean_parts, "join_groups": clean_join_groups, "frame_groups": clean_frame_groups,
        "text_labels": clean_text_labels,
    }
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO custom_shapes (name, category_id, data, created_by, is_public) VALUES (%s,%s,%s,%s,%s)",
                (name, category_id, json.dumps(payload), user["id"] if user else None, is_public),
            )
            new_id = cur.lastrowid
            _mirror_shape_to_drive(cur, new_id, name, category_id, payload, user["id"] if user else None)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id, "is_public": bool(is_public)})


@app.delete("/api/custom-shapes/<int:shape_id>")
@staff_required
def custom_shapes_delete(shape_id):
    # Robert 2026-07-27: mazani smi jen vlastnik tvaru, admin smi smazat
    # cokoli (i verejne tvary jinych adminu) - stejna logika jako viditelnost
    # v custom_shapes_list vyse.
    user = current_user()
    conn = get_conn()
    stored_filename = None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT created_by, drive_file_id FROM custom_shapes WHERE id=%s", (shape_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Tvar neexistuje."}), 404
            if user["role"] != "admin" and row["created_by"] != user["id"]:
                return jsonify({"error": "Tento tvar nemůžeš smazat, není tvůj."}), 403
            drive_file_id = row["drive_file_id"]
            if drive_file_id:
                cur.execute("SELECT stored_filename FROM shared_drive_files WHERE id=%s", (drive_file_id,))
                frow = cur.fetchone()
                stored_filename = frow["stored_filename"] if frow else None
            cur.execute("DELETE FROM custom_shapes WHERE id=%s", (shape_id,))
            if drive_file_id:
                cur.execute("DELETE FROM shared_drive_files WHERE id=%s", (drive_file_id,))
        conn.commit()
    finally:
        conn.close()
    if stored_filename:
        try:
            os.remove(os.path.join(DRIVE_FILES_DIR, stored_filename))
        except OSError:
            pass
    return jsonify({"status": "ok"})


@app.put("/api/custom-shapes/<int:shape_id>")
@staff_required
def custom_shapes_update(shape_id):
    """Prerazeni do jine kategorie (Robert 2026-08-05) A/NEBO preulozeni
    (resave_scene) - Robert 2026-09-18: "jak mame funkci preulozit
    sestavu, potrebuji to tlacitko na preulozeni libovolneho tvaru...
    ktery muze obsahovat i casti jine nez profily, libovolne" - stejny
    ucel jako product_assemblies resave_scene (viz
    product_assemblies_update): admin/vlastnik si tvar rucne upravi
    primo ve scene (posun dilu, pridani noveho...) a prepise CELY
    existujici radek stejnym ID, misto zalozeni noveho. Na rozdil od
    sestav ZDE zustava opravneni vlastnik-nebo-admin (stejne jako
    zbytek teto funkce, ne pritvrzeno na cisteho admina) - vlastni tvary
    uz maji volnejsi model nez sestavy odjakziva.
    Stejna opravneni jako mazani - vlastnik, nebo admin."""
    user = current_user()
    body = request.get_json(silent=True) or {}
    if "category_id" not in body and "resave_scene" not in body:
        return jsonify({"error": "Nic ke změně."}), 400
    category_id = body.get("category_id")
    resave_parts_count = None
    early_error = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT created_by, name, data, category_id FROM custom_shapes WHERE id=%s", (shape_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Tvar neexistuje."}), 404
            if user["role"] != "admin" and row["created_by"] != user["id"]:
                return jsonify({"error": "Tento tvar nemůžeš upravit, není tvůj."}), 403
            if body.get("resave_scene"):
                katalog_parts = fetch_katalog_parts()
                valid_part_ids = {p["id"] for p in katalog_parts}
                clean_parts, err = _validate_custom_shape_parts(
                    body.get("parts"), valid_part_ids, max_parts=CUSTOM_SHAPE_MAX_PARTS)
                if err:
                    return jsonify({"error": err}), 400
                clean_join_groups, clean_frame_groups, err = _validate_custom_shape_relations(
                    body.get("join_groups"), body.get("frame_groups"), len(clean_parts), clean_parts)
                if err:
                    return jsonify({"error": err}), 400
                clean_text_labels, err = _validate_custom_shape_text_labels(body.get("text_labels"))
                if err:
                    return jsonify({"error": err}), 400
                dup = _najdi_duplicitni_role(clean_parts)
                if dup:
                    return jsonify({"error": "Přeuložení odmítnuto: duplicitní role - "
                                              + ", ".join(f"{r} ({n}×)" for r, n in dup.items())}), 400
                # Zaloha PUVODNICH dat PRED prepsanim - schvalne se
                # nezachytava vyjimka, selhani zalohy ma prepsani
                # zastavit, ne se tise preskocit (viz product_assemblies
                # resave_scene, stejny incident-driven duvod).
                try:
                    _zaloha_pred_resave_shape(shape_id, row["name"], row["data"])
                except Exception:  # noqa: BLE001
                    app.logger.exception("Tvar %s: zaloha pred prepsanim SELHALA, oprava NEPROVEDENA", shape_id)
                    early_error = ("Přeuložení zastaveno: nepodařilo se zálohovat původní data "
                                   "(bezpečnostní pojistka). Zkuste to prosím znovu.", 500)
                if not early_error:
                    payload = {
                        "parts": clean_parts, "join_groups": clean_join_groups, "frame_groups": clean_frame_groups,
                        "text_labels": clean_text_labels,
                    }
                    cur.execute("UPDATE custom_shapes SET data=%s WHERE id=%s", (json.dumps(payload), shape_id))
                    _mirror_shape_to_drive(cur, shape_id, row["name"], row["category_id"], payload, user["id"])
                    resave_parts_count = len(clean_parts)
            elif category_id is not None:
                cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (category_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Kategorie neexistuje."}), 400
            if not body.get("resave_scene"):
                cur.execute("UPDATE custom_shapes SET category_id=%s WHERE id=%s", (category_id, shape_id))
                try:
                    payload = json.loads(row["data"])
                except (ValueError, TypeError):
                    payload = {}
                _mirror_shape_to_drive(cur, shape_id, row["name"], category_id, payload, user["id"])
        if not early_error:
            conn.commit()
    finally:
        conn.close()
    if early_error:
        return jsonify({"error": early_error[0]}), early_error[1]
    if resave_parts_count is not None:
        log_audit(user["id"], "shape_resave", "custom_shape", shape_id, f"přeuloženo, {resave_parts_count} dílů")
        return jsonify({"status": "ok", "resave": {"parts": resave_parts_count}})
    return jsonify({"status": "ok"})


# --- Vlastni tvary: strom kategorii (Robert 2026-08-05: "stromeckove
# jako leve menu, vlastnich tvaru tam bude hodne stovky a desitky
# podkategorii"). Samostatny strom od content_categories (jina domena -
# sablony sestav pro 3D scenu, ne prodejni katalog). Spravu (zalozeni/
# prejmenovani/presun/smazani kategorie) smi jen admin - stejne jako
# jen admin muze ukladat VEREJNE tvary (is_public), prochazeni stromu
# (GET) smi kazdy prihlaseny stejne jako videt tvary samotne. ---
def _build_custom_shape_category_tree(cur):
    cur.execute(
        "SELECT id, parent_id, name, sort_order FROM custom_shape_categories "
        "ORDER BY parent_id IS NULL DESC, sort_order, name"
    )
    rows = cur.fetchall()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)

    def build(parent_id):
        return [
            {"id": r["id"], "name": r["name"], "sort_order": r["sort_order"], "children": build(r["id"])}
            for r in by_parent.get(parent_id, [])
        ]

    return build(None)


@app.get("/api/custom-shape-categories")
@staff_required
def custom_shape_categories_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            tree = _build_custom_shape_category_tree(cur)
    finally:
        conn.close()
    return jsonify({"tree": tree})


# Zrcadleni do Sdileneho disku (Robert 2026-08-06: "nech strom z tvaru
# ve scene zije zaroven ve sdilenym diskem" -> upresneno "kategorie
# tvaru = automaticky i slozka na disku") - JEDNOSMERNY sync (kategorie
# tvaru -> slozka disku, ne obracene - vytvoreni slozky rucne primo ve
# Sdilenem disku zadnou kategorii tvaru nezaklada). Vsechny zrcadlene
# slozky visi pod jednim spolecnym korenem "Vlastní tvary", at
# nezaplevuji koren Sdileneho disku desitkami nesouvisejicich polozek.
def _ensure_shapes_drive_root(cur, user_id):
    cur.execute("SELECT id FROM shared_drive_folders WHERE parent_folder_id IS NULL AND name=%s", ("Vlastní tvary",))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (NULL,%s,%s)",
        ("Vlastní tvary", user_id),
    )
    return cur.lastrowid


def _mirror_shape_category_to_drive(cur, cat_id, name, parent_id, user_id):
    """Vytvori parovou slozku ve Sdilenem disku pro NOVOU kategorii
    tvaru a ulozi jeji id do custom_shape_categories.drive_folder_id."""
    if parent_id is not None:
        cur.execute("SELECT drive_folder_id FROM custom_shape_categories WHERE id=%s", (parent_id,))
        prow = cur.fetchone()
        drive_parent_id = prow["drive_folder_id"] if prow else None
    else:
        drive_parent_id = None
    if drive_parent_id is None:
        drive_parent_id = _ensure_shapes_drive_root(cur, user_id)
    cur.execute(
        "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
        (drive_parent_id, name, user_id),
    )
    drive_folder_id = cur.lastrowid
    cur.execute("UPDATE custom_shape_categories SET drive_folder_id=%s WHERE id=%s", (drive_folder_id, cat_id))
    return drive_folder_id


def _mirror_shape_to_drive(cur, shape_id, name, category_id, payload, user_id):
    """Zapise/aktualizuje JSON export dat JEDNOHO tvaru jako soubor v jeho
    parove slozce na Sdilenem disku (Robert 2026-08-06, screenshot
    "Nohy FBX 349" prazdna: predchozi mirror resil jen slozky, ne obsah -
    tvary videl ve stromu ve scene, ale na Sdilenem disku "soubory nejsou
    videt"). Bez kategorie (Nezarazene) jde soubor do korenove slozky
    "Vlastni tvary". VOLAT VZDY v ramci uz otevrene transakce (stejny cur,
    zadny vlastni get_conn/close) - viz bug 2026-08-05 s tichym rollbackem
    pri volani pomocnych funkci s vlastnim connectionem uprostred zapisu."""
    if category_id is not None:
        cur.execute("SELECT drive_folder_id FROM custom_shape_categories WHERE id=%s", (category_id,))
        crow = cur.fetchone()
        drive_folder_id = crow["drive_folder_id"] if crow else None
    else:
        drive_folder_id = None
    if drive_folder_id is None:
        drive_folder_id = _ensure_shapes_drive_root(cur, user_id)

    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    display_name = f"{name}.json"[:255]

    cur.execute("SELECT drive_file_id FROM custom_shapes WHERE id=%s", (shape_id,))
    srow = cur.fetchone()
    existing_id = srow["drive_file_id"] if srow else None
    frow = None
    if existing_id:
        cur.execute("SELECT stored_filename FROM shared_drive_files WHERE id=%s", (existing_id,))
        frow = cur.fetchone()

    if frow:
        with open(os.path.join(DRIVE_FILES_DIR, frow["stored_filename"]), "wb") as fh:
            fh.write(content)
        cur.execute(
            "UPDATE shared_drive_files SET folder_id=%s, filename=%s, size_bytes=%s WHERE id=%s",
            (drive_folder_id, display_name, len(content), existing_id),
        )
        return existing_id

    stored_filename = f"{os.urandom(16).hex()}.json"
    with open(os.path.join(DRIVE_FILES_DIR, stored_filename), "wb") as fh:
        fh.write(content)
    cur.execute(
        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (drive_folder_id, display_name, stored_filename, "application/json", len(content), user_id),
    )
    new_file_id = cur.lastrowid
    cur.execute("UPDATE custom_shapes SET drive_file_id=%s WHERE id=%s", (new_file_id, shape_id))
    return new_file_id


@app.post("/api/custom-shape-categories")
@admin_required
def custom_shape_categories_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Vyplň název kategorie."}), 400
    parent_id = body.get("parent_id")
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if parent_id is not None:
                cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (parent_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
            cur.execute(
                "INSERT INTO custom_shape_categories (parent_id, name, created_by) VALUES (%s,%s,%s)",
                (parent_id, name, user["id"]),
            )
            new_id = cur.lastrowid
            _mirror_shape_category_to_drive(cur, new_id, name, parent_id, user["id"])
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "custom_shape_category", new_id, name)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/custom-shape-categories/<int:cat_id>")
@admin_required
def custom_shape_categories_update(cat_id):
    body = request.get_json(silent=True) or {}
    # POZOR: current_user() si interne otevira/zaviro VLASTNI get_conn() -
    # a .close() na pooled spojeni znamena ROLLBACK (viz _PooledConn
    # docstring), ne bezpecny navrat do fronty. Volat current_user() az
    # UVNITR nize otevrene transakce by tichem rollbacknulo predchozi
    # UPDATE v teto funkci (presne tenhle bug se stal a byl odhalen testem -
    # zjistit VZDY PRED otevrenim vlastni transakce, nikdy uvnitr).
    user_id = current_user()["id"]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (cat_id,))
            if not cur.fetchone():
                return jsonify({"error": "Kategorie neexistuje."}), 404
            fields, params = [], []
            if "name" in body:
                name = (body.get("name") or "").strip()
                if not name:
                    return jsonify({"error": "Vyplň název kategorie."}), 400
                fields.append("name=%s"); params.append(name)
            if "parent_id" in body:
                new_parent = body.get("parent_id")
                if new_parent is not None:
                    cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (new_parent,))
                    if not cur.fetchone():
                        return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
                    # Zabranit cyklu - novy rodic nesmi byt sam sobe ani
                    # vlastnimu potomkovi (stejny vzor jako
                    # drive_admin_folder_update v api/drive.py).
                    cur.execute("SELECT id, parent_id FROM custom_shape_categories")
                    parent_of = {r["id"]: r["parent_id"] for r in cur.fetchall()}
                    walker, seen = new_parent, set()
                    while walker is not None:
                        if walker == cat_id:
                            return jsonify({"error": "Nelze přesunout kategorii do sebe/vlastního podstromu."}), 400
                        if walker in seen:
                            break
                        seen.add(walker)
                        walker = parent_of.get(walker)
                fields.append("parent_id=%s"); params.append(new_parent)
            if "sort_order" in body:
                try:
                    sort_order = int(body.get("sort_order") or 0)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné pořadí."}), 400
                fields.append("sort_order=%s"); params.append(sort_order)
            if not fields:
                return jsonify({"error": "Nic ke změně."}), 400
            params.append(cat_id)
            cur.execute(f"UPDATE custom_shape_categories SET {', '.join(fields)} WHERE id=%s", params)

            # Zrcadleni prejmenovani/presunu do parove slozky Sdileneho
            # disku (Robert 2026-08-06). Legacy kategorie bez
            # drive_folder_id (zalozene pred touhle funkci) si slozku
            # domysli az pri prvni uprave, misto samostatneho backfillu.
            cur.execute("SELECT drive_folder_id, name, parent_id FROM custom_shape_categories WHERE id=%s", (cat_id,))
            row = cur.fetchone()
            drive_folder_id = row["drive_folder_id"]
            if drive_folder_id is None:
                drive_folder_id = _mirror_shape_category_to_drive(cur, cat_id, row["name"], row["parent_id"], user_id)
            else:
                if "name" in body:
                    cur.execute("UPDATE shared_drive_folders SET name=%s WHERE id=%s", (row["name"], drive_folder_id))
                if "parent_id" in body:
                    if row["parent_id"] is not None:
                        cur.execute("SELECT drive_folder_id FROM custom_shape_categories WHERE id=%s", (row["parent_id"],))
                        prow = cur.fetchone()
                        new_drive_parent = prow["drive_folder_id"] if prow else None
                        if new_drive_parent is None:
                            new_drive_parent = _ensure_shapes_drive_root(cur, user_id)
                    else:
                        new_drive_parent = _ensure_shapes_drive_root(cur, user_id)
                    cur.execute("UPDATE shared_drive_folders SET parent_folder_id=%s WHERE id=%s", (new_drive_parent, drive_folder_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(user_id, "update", "custom_shape_category", cat_id, ", ".join(fields))
    return jsonify({"status": "ok"})


@app.delete("/api/custom-shape-categories/<int:cat_id>")
@admin_required
def custom_shape_categories_delete(cat_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM custom_shape_categories WHERE id=%s", (cat_id,))
            if not cur.fetchone():
                return jsonify({"error": "Kategorie neexistuje."}), 404
            # ON DELETE CASCADE smaze cely podstrom kategorii, ON DELETE
            # SET NULL u custom_shapes.category_id presune jeji tvary do
            # "Nezarazene" - zadny tvar se mazanim kategorie neztrati.
            # Parova slozka ve Sdilenem disku (drive_folder_id) se
            # ZAMERNE NEMAZE - mohou v ni byt realne nahrane soubory,
            # mazani kategorie tvaru by je tise smazalo. Osireleho
            # zaznamu si admin vsimne pri prochazeni Sdileneho disku
            # a smaze ho tam rucne, pokud fakt uz neni potreba.
            cur.execute("DELETE FROM custom_shape_categories WHERE id=%s", (cat_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "custom_shape_category", cat_id, None)
    return jsonify({"status": "ok"})
