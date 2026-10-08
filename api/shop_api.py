"""Shop API (/api/shop/*): FBX/STEP upload + převod na GLB a stažení STP
u produktů, dashboard skladu, sestava k objednání (reorder-items),
manuální refresh ceny z logiman.cz.

Vyčleněno z api/app.py (PLAN_ROZDELENI_BACKENDU.md skupina 15) - čistý
přesun, žádná změna chování/URL. `convert_uploaded_model_to_glb`,
`_reorder_sync_from_stock` a `refresh_price_for_product`/
`scrape_logiman_product_price` zůstávají v app.py, protože je používá i
kód mimo tuhle skupinu (approvals.py přímo importuje
_reorder_sync_from_stock, price-scraping - plán skupina 6 - jeste
nevyčleněno) - modul si je jen importuje. `logiman_price_check`/
`shop_products_refresh_price` NEJSOU tady - už existují (byte-identicky)
v price_scraping.py (skupina 6, vyčleněno dřív), přesun sem by způsobil
duplicitní registraci route (bot15, revize mergu). `PRODUCT_FBX_UPLOAD_DIR`
zůstává v app.py taky - používá ji i dimension_match_fbx.py mimo tuhle
skupinu (nalezeno až při live restartu po mergu, bot15).
"""
import glob
import os
import re
from urllib.parse import quote

from flask import request, jsonify, Response
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    parse_bulk_ids, bulk_delete, get_pagination_args, paginated_query,
    KATALOG_GLB_DIR, convert_uploaded_model_to_glb,
    _reorder_sync_from_stock,
    PRODUCT_FBX_UPLOAD_DIR,
)


@app.post("/api/shop/products/<int:product_id>/fbx-upload")
@require_permission("sklad_karty", "upravit")
def shop_products_fbx_upload(product_id):
    """Nahrani FBX 3D modelu k produktu (shop_products) - bot2, 2026-07-28.
    Presny mirror admin_profily_fbx_upload() (viz vyse) pro cfg_dily, jen
    cilova tabulka je shop_products. Po uspesnem prevodu na GLB
    (fbx_convert.convert_single_fbx) se nastavi jen glb_file.

    Robert 2026-08-08 ("do 3Dsceny nebudou vsechny produkty z eshopu, ani
    vsechny ktere maji stp, ale pouze produkty s priznakem: ProScenu") -
    PUVODNE (viz git historie) se tu zaroven natvrdo nastavovalo i
    visible_in_scene=1, takze KAZDY produkt s uspesne prevedenym STP/FBX
    se OKAMZITE a automaticky objevil v katalogu dilu ve 3D scene
    (fetch_katalog_parts() nize) - presne to uz Robert nechce. Mit 3D
    model (pro nahled na skladove karte, budouci pouziti) uz neznamena
    automaticky "ukaz to ve scene" - to ted rika samostatny prepinac
    "Pro scénu" (visible_in_scene, editovatelny primo v adminu pres
    PUT /api/shop/products/<id>, viz products.py::shop_products_update).
    Pri selhani prevodu zustane surovy FBX ulozeny, visible_in_scene se
    nikdy nemeni odsud."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                return jsonify({"error": "Neznámý produkt."}), 404
    finally:
        conn.close()

    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    src_ext = os.path.splitext(safe_name)[1].lower()
    if src_ext not in (".fbx", ".stp", ".step"):
        return jsonify({"error": "Očekávám soubor .fbx, .stp nebo .step."}), 400

    quality = request.form.get("quality") or None
    if quality not in (None, "low", "medium", "high"):
        quality = None

    dest_path = os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{product_id}{src_ext}")
    f.save(dest_path)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shop_products SET fbx_original_name=%s, fbx_uploaded_at=NOW() WHERE id=%s",
                (safe_name, product_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "upload", "product_fbx", product_id, safe_name + (f" (kvalita: {quality})" if quality else ""))

    conversion = {"attempted": True, "success": False, "error": None}
    glb_name = f"product_{product_id}.glb"
    glb_dest = os.path.join(KATALOG_GLB_DIR, glb_name)
    ok, info = convert_uploaded_model_to_glb(dest_path, glb_dest, quality=quality)
    conversion["success"] = ok
    conversion["error"] = info.get("error")
    if ok:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute(
                    "UPDATE shop_products SET glb_file=%s WHERE id=%s",
                    (glb_name, product_id),
                )
            conn2.commit()
        finally:
            conn2.close()
        log_audit(admin["id"], "convert", "product_model_to_glb", product_id, f"OK ({src_ext}, {info.get('vertices')}v/{info.get('faces', info.get('triangles_after_simplify'))}f)")
    else:
        log_audit(admin["id"], "convert", "product_model_to_glb", product_id, f"SELHALO ({src_ext}) - {info.get('error')}")

    return jsonify({
        "status": "ok",
        "id": product_id,
        "fbx_original_name": safe_name,
        "conversion": conversion,
    })

@app.post("/api/shop/products/<int:product_id>/convert-to-glb")
@require_permission("sklad_karty", "upravit")
def shop_products_convert_to_glb(product_id):
    """Rucni (opakovany) prevod jiz ULOZENEHO STP/FBX na GLB - Robert
    2026-08-09: "prevedene glb nech zustane jakoby viditelny jako druhy
    soubor" - na rozdil od /fbx-upload vyse ZADNY novy soubor nenahrava,
    jen znovu spusti convert_uploaded_model_to_glb nad souborem, ktery uz
    lezi v PRODUCT_FBX_UPLOAD_DIR ({product_id}.<puvodni pripona>).
    Zdrojovy STP/FBX (fbx_original_name, soubor na disku) zustava zcela
    beze zmeny - jen se doplni/prepise glb_file, oba soubory (zdroj i
    prevod) tak koexistuji vedle sebe, presne jak Robert chtel ("stp
    soubory nesmi zmizet, musi zustat pro dalsi pouziti").

    Robert: "dej k tem tlacitkum i volbu kvality, protoze nemusí být
    vzdy u vsech stejná" - stejny quality parametr (low/medium/high)
    jako u /fbx-upload, jen bez preview kroku (soubor uz je ulozeny,
    zvolena kvalita se rovnou pouzije)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fbx_original_name FROM shop_products WHERE id=%s",
                (product_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Neznámý produkt."}), 404
    if not row["fbx_original_name"]:
        return jsonify({"error": "Produkt zatím nemá nahraný žádný 3D model (STP/FBX)."}), 400

    body = request.get_json(silent=True) or {}
    quality = body.get("quality") or None
    if quality not in (None, "low", "medium", "high"):
        quality = None

    matches = glob.glob(os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{product_id}.*"))
    if not matches:
        return jsonify({"error": "Zdrojový soubor na disku chybí (byl smazán mimo aplikaci?) - nahraj model znovu."}), 404
    src_path = matches[0]

    glb_name = f"product_{product_id}.glb"
    glb_dest = os.path.join(KATALOG_GLB_DIR, glb_name)
    ok, info = convert_uploaded_model_to_glb(src_path, glb_dest, quality=quality)
    if ok:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("UPDATE shop_products SET glb_file=%s WHERE id=%s", (glb_name, product_id))
            conn2.commit()
        finally:
            conn2.close()
        log_audit(admin["id"], "convert", "product_model_to_glb", product_id,
                   f"rucni prevod OK ({os.path.basename(src_path)}, kvalita: {quality or 'auto'})")
    else:
        log_audit(admin["id"], "convert", "product_model_to_glb", product_id,
                   f"rucni prevod SELHAL ({os.path.basename(src_path)}) - {info.get('error')}")

    return jsonify({
        "status": "ok" if ok else "error",
        "id": product_id,
        "glb_file": glb_name if ok else None,
        "conversion": {"attempted": True, "success": ok, "error": info.get("error")},
    })

# Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): STP/STEP hlavicka
# (ISO-10303-21 FILE_NAME, prosty text na zacatku souboru) casto
# obsahuje PUVODNI nazev souboru od dodavatele vc. jeho INTERNIHO
# kodovani dilu (napr. '2.3.005.10.01_kanal fitili 45x45 k10.STEP') -
# konkurence by tak mohla dohledat velkoobchodni cenik primo u
# dodavatele. Jmeno dodavatele samo (Dogus) je jinde na webu uz verejne
# (product.html "Dodavatel"), takze anonymizace resi JEN tenhle interni
# kod - nahrazuje se prvni retezec v FILE_NAME(...) (a stejny retezec,
# pokud se objevi i ve FILE_DESCRIPTION) za "<SKU>.step". Soubory NA
# DISKU se nemeni, jen se upravi bajty pri streamovani.
_STEP_WS_OR_COMMENT = rb"(?:\s|/\*.*?\*/)*"

_STEP_FILE_NAME_RE = re.compile(
    rb"FILE_NAME" + _STEP_WS_OR_COMMENT + rb"\(" + _STEP_WS_OR_COMMENT + rb"'((?:[^']|'')*)'",
    re.DOTALL,
)

def _sanitize_step_header(data, sku):
    endsec_idx = data.find(b"ENDSEC;")
    if endsec_idx == -1:
        return data
    header, rest = data[:endsec_idx], data[endsec_idx:]
    m = _STEP_FILE_NAME_RE.search(header)
    if not m:
        app.logger.warning("_sanitize_step_header: FILE_NAME nenalezeno, streamuji beze zmeny")
        return data
    original_name = m.group(1)
    new_name = f"{sku}.step".encode("ascii", "replace")
    new_header = header[:m.start(1)] + new_name + header[m.end(1):]
    if original_name and original_name in new_header:
        new_header = new_header.replace(original_name, new_name)
    return new_header + rest

@app.get("/api/shop/products/<int:product_id>/stp-download")
def shop_products_stp_download(product_id):
    """VEREJNE stazeni originalniho STP/FBX souboru produktu (detail
    produktu na e-shopu, Robert 2026-08-10: "stp vetsinou mame stazene,
    zacni na tom delat" - zakaznici maji mit moznost stahnout si CAD
    soubor primo z produktu, ne jen admin). Soubor je fyzicky ulozeny v
    PRODUCT_FBX_UPLOAD_DIR/{id}.<pripona> (viz fbx-upload vyse), zde se
    jen stream-uje pod puvodnim jmenem (fbx_original_name)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT fbx_original_name, sku FROM shop_products WHERE id=%s AND active=1 AND is_archived=0",
                (product_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not row["fbx_original_name"]:
        return jsonify({"error": "Produkt nemá k dispozici 3D model ke stažení."}), 404

    matches = glob.glob(os.path.join(PRODUCT_FBX_UPLOAD_DIR, f"{product_id}.*"))
    if not matches:
        return jsonify({"error": "Soubor na disku chybí."}), 404

    with open(matches[0], "rb") as f:
        data = f.read()
    src_ext = os.path.splitext(matches[0])[1].lower()
    if src_ext in (".stp", ".step"):
        data = _sanitize_step_header(data, row["sku"])
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, follow-up k
    # _sanitize_step_header): puvodni kod tady pouzival fbx_original_name
    # (vc. tureckeho nazvu/interniho kodu dodavatele) jako STAZENY nazev
    # souboru - i po anonymizaci FILE_NAME hlavicky nahore tak stejny
    # udaj unikal pres Content-Disposition. Sjednoceno na stejnou hodnotu
    # jako v hlavicce (SKU, fallback product_id kdyz SKU chybi), spravna
    # pripona podle skutecneho souboru na disku (ne vzdy .step - endpoint
    # servíruje i FBX). RFC 5987 filename* jen kdyz ascii fallback neni
    # bajt-presne totozny (SKU/id je typicky cistě ASCII, tak se v praxi
    # obvykle vubec nepouzije).
    download_name = f"{row['sku']}{src_ext}" if row.get("sku") else f"{product_id}{src_ext}"
    ascii_fallback = download_name.encode("ascii", "replace").decode("ascii")
    content_disposition = f'attachment; filename="{ascii_fallback}"'
    if ascii_fallback != download_name:
        content_disposition += f"; filename*=UTF-8''{quote(download_name)}"
    return Response(data, mimetype="application/octet-stream", headers={
        "Content-Disposition": content_disposition,
    })

# --- Dashboard (Robert 2026-07-25: "rozšířená evidence položek" -
# souhrnny prehled stavu skladu pro admina). ---
@app.get("/api/shop/dashboard")
@require_permission("sklad_karty", "zobrazit")
def shop_dashboard():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM shop_products WHERE is_archived=0")
            active_count = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM shop_products WHERE is_archived=1")
            archived_count = cur.fetchone()["c"]
            cur.execute("""
                SELECT COALESCE(SUM(stock_qty * price_czk_placeholder), 0) AS v
                FROM shop_products WHERE is_archived=0 AND price_czk_placeholder IS NOT NULL
            """)
            stock_value = cur.fetchone()["v"]
            cur.execute("""
                SELECT id, sku, name, stock_qty, min_stock, unit FROM shop_products
                WHERE is_archived=0 AND min_stock IS NOT NULL AND stock_qty < min_stock
                ORDER BY (min_stock - stock_qty) DESC LIMIT 20
            """)
            low_stock = cur.fetchall()
            cur.execute("""
                SELECT COUNT(*) AS c FROM shop_products
                WHERE is_archived=0 AND min_stock IS NOT NULL AND stock_qty < min_stock
            """)
            low_stock_count = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM content_categories")
            category_count = cur.fetchone()["c"]
            cur.execute("""
                SELECT m.id, m.movement_type, m.qty, m.created_at, p.name AS product_name, p.sku AS product_sku,
                       u.name AS user_name, u.email AS user_email
                FROM shop_stock_movements m
                JOIN shop_products p ON p.id = m.product_id
                LEFT JOIN app_users u ON u.id = m.user_id
                ORDER BY m.created_at DESC, m.id DESC LIMIT 10
            """)
            recent_movements = cur.fetchall()
    finally:
        conn.close()
    for m in recent_movements:
        if m.get("created_at"):
            m["created_at"] = m["created_at"].isoformat()
    return jsonify({
        "active_products": active_count,
        "archived_products": archived_count,
        "stock_value_czk": float(stock_value),
        "low_stock_count": low_stock_count,
        "low_stock_items": low_stock,
        "category_count": category_count,
        "recent_movements": recent_movements,
    })

@app.get("/api/shop/reorder-items")
@require_permission("sklad_doobjednavky", "zobrazit")
def shop_reorder_items_list():
    status_filter = request.args.get("status")
    # Stránkování (task #78/85)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            _reorder_sync_from_stock(cur)
        conn.commit()
        with conn.cursor() as cur:
            base_sql = """
                SELECT r.id, r.product_id, p.sku, p.name, p.unit, p.stock_qty, p.min_stock,
                       r.qty_needed, r.status, r.source, r.note, r.created_at, r.updated_at
                FROM shop_reorder_items r
                JOIN shop_products p ON p.id = r.product_id
            """
            params = []
            where_sql = ""
            if status_filter in ("needed", "selected"):
                where_sql = " WHERE r.status=%s"
                params.append(status_filter)
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           " ORDER BY (r.status='selected') ASC, r.qty_needed DESC, r.updated_at DESC",
                                           page, page_size)
    finally:
        conn.close()
    for r in rows:
        for k in ("created_at", "updated_at"):
            if r.get(k):
                r[k] = r[k].isoformat()
    resp = {"items": rows, "count": len(rows)}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)

@app.post("/api/shop/reorder-items")
@require_permission("sklad_doobjednavky", "vytvorit")
def shop_reorder_items_create():
    # rucni pridani polozky do sestavy (napr. chce navysit zasobu, i kdyz
    # produkt zatim neni pod min. zasobou)
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    try:
        qty_needed = int(body.get("qty_needed"))
    except (TypeError, ValueError):
        qty_needed = 0
    if not product_id or qty_needed <= 0:
        return jsonify({"error": "Vyber produkt a zadej kladné množství."}), 400
    note = (body.get("note") or "").strip() or None
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Produkt neexistuje."}), 404
            cur.execute("SELECT id FROM shop_reorder_items WHERE product_id=%s", (product_id,))
            if cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Tento produkt už v sestavě k objednání je."}), 400
            cur.execute(
                "INSERT INTO shop_reorder_items (product_id, qty_needed, status, source, note) "
                "VALUES (%s,%s,'needed','manual',%s)",
                (product_id, qty_needed, note),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "reorder_item", new_id,
              f"Ručně přidáno do sestavy k objednání (product_id={product_id}, množství={qty_needed})")
    return jsonify({"status": "ok", "id": new_id}), 201

@app.put("/api/shop/reorder-items/<int:item_id>")
@require_permission("sklad_doobjednavky", "upravit")
def shop_reorder_items_update(item_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "qty_needed" in body:
        try:
            qv = int(body["qty_needed"])
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné množství."}), 400
        if qv <= 0:
            return jsonify({"error": "Množství musí být kladné."}), 400
        fields.append("qty_needed=%s"); params.append(qv)
    if "status" in body:
        if body["status"] not in ("needed", "selected"):
            return jsonify({"error": "Neplatný stav."}), 400
        fields.append("status=%s"); params.append(body["status"])
    if "note" in body:
        fields.append("note=%s"); params.append((body["note"] or "").strip() or None)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(item_id)
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE shop_reorder_items SET {', '.join(fields)} WHERE id=%s", params)
            changed = cur.rowcount
            if changed == 0:
                cur.execute("SELECT id FROM shop_reorder_items WHERE id=%s", (item_id,))
                if not cur.fetchone():
                    conn.rollback()
                    return jsonify({"error": "Položka neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "reorder_item", item_id,
              ", ".join(f.split("=")[0] for f in fields))
    return jsonify({"status": "ok"})

@app.post("/api/shop/reorder-items/select")
@require_permission("sklad_doobjednavky", "upravit")
def shop_reorder_items_bulk_select():
    # hromadne oznaceni vybranych polozek pracovnikem ("nas pracovnik si
    # rucne vybere ktere polozky z toho chce objednat")
    body = request.get_json(silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Vyber alespoň jednu položku."}), 400
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatná id."}), 400
    new_status = body.get("status", "selected")
    if new_status not in ("needed", "selected"):
        return jsonify({"error": "Neplatný stav."}), 400
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"UPDATE shop_reorder_items SET status=%s WHERE id IN ({placeholders})",
                        [new_status] + ids)
            updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "reorder_item", None,
              f"hromadně označeno {updated} položek jako '{new_status}'")
    return jsonify({"status": "ok", "updated": updated})

@app.post("/api/shop/reorder-items/bulk-delete")
@require_permission("sklad_doobjednavky", "smazat")
def shop_reorder_items_bulk_delete():
    # Robert 2026-07-26: "smazat, dalsi navrhni podle kontextu" - polozky
    # sestavy k objednani uz maji radkove Smazat, hromadne jen zrcadli
    # tutez akci (zadne vedlejsi ucinky na sklad, staci bulk_delete()).
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "shop_reorder_items", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "bulk_delete", "reorder_item", None, f"{deleted} položek smazáno ze sestavy")
    return jsonify({"status": "ok", "deleted": deleted})

@app.delete("/api/shop/reorder-items/<int:item_id>")
@require_permission("sklad_doobjednavky", "smazat")
def shop_reorder_items_delete(item_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_reorder_items WHERE id=%s", (item_id,))
            deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    if not deleted:
        return jsonify({"error": "Položka neexistuje."}), 404
    log_audit(user["id"], "delete", "reorder_item", item_id, None)
    return jsonify({"status": "ok"})

