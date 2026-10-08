"""
Nakupni objednavky - bot3, 2026-07-25 (v7).

Kontext: Robert "pridejme jeste Nákupní objednávky" - NA ROZDIL od
orders.py (shop_orders = objednavky OD zakazniku), tohle jsou objednavky,
ktere LOGIMAN zadava SVYM DODAVATELUM (nakup materialu/zbozi na sklad).
Zamena s objednavkami od zakazniku by byla nebezpecna (jina strana
transakce, jina auditni stopa) - proto samostatny modul, samostatne
tabulky (shop_suppliers, shop_purchase_orders, shop_purchase_order_items,
shop_purchase_order_status_history), samostatna URL prefix
/api/admin/purchase-orders a /api/admin/suppliers.

Rozsah potvrzen Robertem pres AskUserQuestion (2026-07-25, vsechny 3
zvoleny):
  1. Evidence dodavatelu (shop_suppliers - zakladni karta).
  2. Polozky napojene na sklad (shop_products) - prijem zbozi AUTOMATICKY
     zvysi stock_qty + zapise se do shop_stock_movements (stejny princip
     jako u prijmu/vraceni skladu v orders.py::admin_orders_update).
  3. Stavy/schvalovani - navrh -> odeslano -> (castecne) prijato, s
     auditni historii (stejny vzor jako shop_order_status_history).

Vyzaduje migraci sql/2026-07-25_purchase_orders.sql. Aktivace: `import
purchase_orders` na konec app.py (poradi vuci ostatnim modulum
nepodstatne - na rozdil od orders.py/documents.py spolu tyhle dva moduly
NEKOMUNIKUJI, zadny cross-import).

Zname omezeni v1 (vedome, kvuli rozsahu):
  - Polozky nakupni objednavky NELZE upravit po vytvoreni (jen cely PO
    zrusit a zalozit novy) - stejna konzervativni filozofie jako u
    koncovych stavu shop_orders ("pripadnou opravu chyby resi admin
    rucne v DB, ne pres API").
  - Nakupni cena se zadava rucne pri vytvoreni PO, NENAPOJENA na
    price_source_url/automaticke nocni nacitani cen (to je zdroj prodejni
    ceny zakaznikum, ne nakupni ceny od dodavatele - jiny ucel).
  - Zadne DPH/danove doklady u nakupnich objednavek (na rozdil od v6
    zalohova faktura/faktura) - nakupni objednavka je interni/dodavatelsky
    doklad, ne danovy doklad vuci zakaznikovi.

v8 (bot3, 2026-07-26) - hromadne akce (viz NAVRH_HROMADNE_AKCE.md, bot4):
  - POST /api/admin/suppliers/bulk-activate - hromadna aktivace/deaktivace
    vybranych dodavatelu (zadne vedlejsi ucinky, primy bulk_update_fields()).
  - POST /api/admin/purchase-orders/bulk-status - hromadna zmena stavu
    vybranych nakupnich objednavek. Sdili _apply_po_status_change() se
    stavajicim PUT /api/admin/purchase-orders/<id> (refaktorovano z
    puvodniho admin_po_update tela) - NE holy UPDATE, kvuli vedlejsimu
    ucinku (zapis do shop_purchase_order_status_history) a stejne
    validaci ALLOWED_PO_TRANSITIONS. Kazde id se commituje/rollbackuje
    samostatne, selhani jedne objednavky (napr. nepovoleny prechod) se
    zaznamena do "failed" a nezastavi zbytek davky.
  - Vyzaduje z app.py: parse_bulk_ids(), bulk_update_fields() (sdilene
    helpery, viz NAVRH_HROMADNE_AKCE.md sekce 2).
"""
import csv
import io
import math
from datetime import datetime

from flask import request, jsonify, Response

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    parse_bulk_ids, bulk_update_fields, bulk_delete, get_pagination_args, paginated_query,
)
from products import reverse_and_delete_stock_movements
from cart import _fetch_cart_rows, _serialize_cart, _cart_owner_id

PO_STATUSES = ("navrh", "odeslano", "castecne_prijato", "prijato", "zruseno")

PO_STATUS_LABELS_CZ = {
    "navrh": "Návrh",
    "odeslano": "Odesláno dodavateli",
    "castecne_prijato": "Částečně přijato",
    "prijato": "Přijato",
    "zruseno": "Zrušeno",
}

# Rucni prechody pres PUT /api/admin/purchase-orders/<id> (na rozdil od
# castecne_prijato/prijato, ktere se dopocitavaji AUTOMATICKY z prijmu
# zbozi - viz _recompute_status_after_receive - a NEJDOU nastavit rucne).
ALLOWED_PO_TRANSITIONS = {
    "navrh": {"odeslano", "zruseno"},
    "odeslano": {"zruseno"},
    "castecne_prijato": {"zruseno"},
    "prijato": set(),
    "zruseno": set(),
}


def _money(v):
    return float(v) if v is not None else None


def _dt(v):
    return v.isoformat() if v else None


# ---------------------------------------------------------------------------
# Dodavatele - admin CRUD
# ---------------------------------------------------------------------------

def _serialize_supplier(row):
    return {
        "id": row["id"], "name": row["name"], "ico": row["ico"], "dic": row["dic"],
        "address": row["address"], "contact_name": row["contact_name"],
        "email": row["email"], "phone": row["phone"], "note": row["note"],
        "active": bool(row["active"]), "created_at": _dt(row["created_at"]),
    }


@app.get("/api/admin/suppliers")
@require_permission("nakupni_objednavky", "zobrazit")
def admin_suppliers_list():
    """?archived=1 prohodi vychozi filtr aktivni<->archivovani (stejny
    vzor jako u produktu - shop_products.is_archived, viz app.py
    shop_products_list) - dodavatele nemaji samostatny is_archived
    sloupec, "archivovany" == active=0 (Robert 2026-08-01: "přidej
    tlačítka, ukázat archivované položky")."""
    q = (request.args.get("q") or "").strip()
    show_archived = request.args.get("archived") == "1"
    where, params = ["active=%s"], [0 if show_archived else 1]
    if q:
        where.append("(name LIKE %s OR ico LIKE %s)")
        like = f"%{q}%"
        params += [like, like]
    # Stránkování (task #78/82)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM shop_suppliers"
            where_sql = " WHERE " + " AND ".join(where)
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY name", page, page_size)
    finally:
        conn.close()
    resp = {"suppliers": [_serialize_supplier(r) for r in rows]}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/admin/suppliers/<int:supplier_id>")
@require_permission("nakupni_objednavky", "zobrazit")
def admin_suppliers_get(supplier_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_suppliers WHERE id=%s", (supplier_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Dodavatel neexistuje."}), 404
    return jsonify({"supplier": _serialize_supplier(row)})


@app.post("/api/admin/suppliers")
@require_permission("nakupni_objednavky", "vytvorit")
def admin_suppliers_create():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Chybí název dodavatele."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shop_suppliers (name, ico, dic, address, contact_name, email, phone, note, active) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1)",
                (name, (body.get("ico") or "").strip() or None, (body.get("dic") or "").strip() or None,
                 (body.get("address") or "").strip() or None, (body.get("contact_name") or "").strip() or None,
                 (body.get("email") or "").strip() or None, (body.get("phone") or "").strip() or None,
                 (body.get("note") or "").strip() or None),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "supplier", new_id, name)
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/admin/suppliers/<int:supplier_id>")
@require_permission("nakupni_objednavky", "upravit")
def admin_suppliers_update(supplier_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    for key in ("name", "ico", "dic", "address", "contact_name", "email", "phone", "note"):
        if key in body:
            fields.append(f"{key}=%s")
            params.append((body.get(key) or "").strip() or None)
    if "active" in body:
        fields.append("active=%s")
        params.append(1 if body.get("active") else 0)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(supplier_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_suppliers WHERE id=%s", (supplier_id,))
            if not cur.fetchone():
                conn.rollback()
                return jsonify({"error": "Dodavatel neexistuje."}), 404
            cur.execute(f"UPDATE shop_suppliers SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "supplier", supplier_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/admin/suppliers/<int:supplier_id>")
@require_permission("nakupni_objednavky", "smazat")
def admin_suppliers_delete(supplier_id):
    """Robert 2026-08-02 (AskUserQuestion): smazani dodavatele KASKADOVE
    smaze i jeho nakupni objednavky (_delete_one_purchase_order nize -
    i s vracenim skladoveho dopadu a smazanim navazanych e-mailu).
    Produkty (shop_products.supplier_id) se NEMAZOU, jen odpoji -
    ON DELETE SET NULL primo v DB, zadny kod netreba ("smazat i PO a
    odpojit produkty")."""
    admin = current_user()
    conn = get_conn()
    po_stock_movement_ids, po_stock_failed, po_item_ids = [], [], []
    deleted_po_count = 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_purchase_orders WHERE supplier_id=%s", (supplier_id,))
            for po_id in [r["id"] for r in cur.fetchall()]:
                result = _delete_one_purchase_order(cur, po_id)
                if result:
                    deleted_po_count += 1
                    po_stock_movement_ids.extend(result["stock_movement_ids"])
                    po_stock_failed.extend(result["stock_failed"])
                    po_item_ids.extend(result["item_ids"])
            cur.execute("DELETE FROM shop_suppliers WHERE id=%s", (supplier_id,))
        conn.commit()
    finally:
        conn.close()
    import gallery_items
    for iid in po_item_ids:
        gallery_items.delete_items_for_owner("po_item", iid)
    for mv_id in po_stock_movement_ids:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)
    note = f" ({deleted_po_count} nákupních objednávek smazáno kaskádově)" if deleted_po_count else ""
    log_audit(admin["id"], "delete", "supplier", supplier_id, f"smazán{note}")
    return jsonify({
        "status": "ok",
        "cascaded_purchase_orders": deleted_po_count,
        "stock_failed": po_stock_failed,
    })


@app.post("/api/admin/suppliers/bulk-activate")
@require_permission("nakupni_objednavky", "upravit")
def admin_suppliers_bulk_activate():
    """
    Hromadna aktivace/deaktivace vybranych dodavatelu. Zadne vedlejsi
    ucinky (na rozdil od zmeny stavu nakupni objednavky) - jednoduchy
    pripad, staci primy `bulk_update_fields()` (viz NAVRH_HROMADNE_AKCE.md
    sekce 2 - "pravidlo pro entity s vedlejsimi ucinky" se sem nevztahuje).

    Body: {"ids": [1,2,3], "active": true|false}
    Odpoved: {"status": "ok", "updated": N}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    if "active" not in body:
        return jsonify({"error": "Chybí pole active."}), 400
    active = 1 if body.get("active") else 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "shop_suppliers", ids, {"active": active})
        conn.commit()
    finally:
        conn.close()

    log_audit(
        admin["id"], "bulk_update", "supplier", None,
        f"{updated} dodavatelů → {'aktivní' if active else 'neaktivní'}",
    )
    return jsonify({"status": "ok", "updated": updated})


@app.post("/api/admin/suppliers/bulk-delete")
@require_permission("nakupni_objednavky", "smazat")
def admin_suppliers_bulk_delete():
    """Hromadne smazani dodavatelu (Robert 2026-08-01: "přidat bulk
    mazání"). shop_products.supplier_id je ON DELETE SET NULL - produkty
    jen ztrati vazbu, beze zmeny. shop_purchase_orders.supplier_id je
    take ON DELETE SET NULL, ale Robert 2026-08-02 (AskUserQuestion)
    potvrdil, ze nakupni objednavky dotcenych dodavatelu se maji smazat
    KASKADOVE (ne jen odpojit) - viz _delete_one_purchase_order."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    po_stock_movement_ids, po_stock_failed, po_item_ids = [], [], []
    deleted_po_count = 0
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_purchase_orders WHERE supplier_id IN ({placeholders})", ids)
            for po_id in [r["id"] for r in cur.fetchall()]:
                result = _delete_one_purchase_order(cur, po_id)
                if result:
                    deleted_po_count += 1
                    po_stock_movement_ids.extend(result["stock_movement_ids"])
                    po_stock_failed.extend(result["stock_failed"])
                    po_item_ids.extend(result["item_ids"])
            deleted = bulk_delete(cur, "shop_suppliers", ids)
        conn.commit()
    finally:
        conn.close()
    import gallery_items
    for iid in po_item_ids:
        gallery_items.delete_items_for_owner("po_item", iid)
    for mv_id in po_stock_movement_ids:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)
    po_note = f", {deleted_po_count} nákupních objednávek kaskádově" if deleted_po_count else ""
    log_audit(admin["id"], "bulk_delete", "supplier", None, f"{deleted} dodavatelů smazáno{po_note}")
    return jsonify({
        "status": "ok", "deleted": deleted,
        "cascaded_purchase_orders": deleted_po_count, "stock_failed": po_stock_failed,
    })


# ---------------------------------------------------------------------------
# Nakupni objednavky
# ---------------------------------------------------------------------------

def _generate_po_number(po_id, created_at):
    year = created_at.year if created_at else datetime.utcnow().year
    return f"NO-{year}-{po_id:05d}"


def _serialize_po(row):
    return {
        "id": row["id"], "po_number": row["po_number"], "status": row["status"],
        "status_label": PO_STATUS_LABELS_CZ.get(row["status"], row["status"]),
        "supplier_id": row["supplier_id"], "supplier_name": row["supplier_name"],
        "supplier_ico": row["supplier_ico"], "supplier_dic": row["supplier_dic"],
        "supplier_address": row["supplier_address"],
        "supplier_contact_name": row["supplier_contact_name"],
        "supplier_email": row["supplier_email"], "supplier_phone": row["supplier_phone"],
        "note": row["note"], "admin_note": row["admin_note"],
        "total_czk": _money(row["total_czk"]), "created_by": row["created_by"],
        "created_at": _dt(row["created_at"]), "updated_at": _dt(row["updated_at"]),
    }


def _serialize_po_item(row):
    return {
        "id": row["id"], "product_id": row["product_id"],
        "product_name": row["product_name_snapshot"], "sku": row["sku_snapshot"],
        "unit_price_czk": _money(row["unit_price_czk"]),
        "qty_ordered": row["qty_ordered"], "qty_received": row["qty_received"],
        "line_total_czk": _money(row["line_total_czk"]),
    }


def _fetch_po_with_items(conn, po_id):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM shop_purchase_orders WHERE id=%s", (po_id,))
        po = cur.fetchone()
        if not po:
            return None, []
        cur.execute(
            "SELECT * FROM shop_purchase_order_items WHERE purchase_order_id=%s ORDER BY id",
            (po_id,),
        )
        items = cur.fetchall()
    return po, items


@app.post("/api/admin/purchase-orders")
@require_permission("nakupni_objednavky", "vytvorit")
def admin_po_create():
    """
    Vytvoreni nakupni objednavky (stav vzdy zacina jako 'navrh').

    Ocekavany JSON payload:
    {
      "supplier_id": 3,                    (volitelne - napojeni na kartu dodavatele,
                                              predvyplni supplier_* snapshot)
      "supplier_name": "...",              (povinne, pokud neni supplier_id NEBO
                                              chcete jiny nazev nez ma karta)
      "supplier_ico": "...", "supplier_dic": "...", "supplier_address": "...",
      "supplier_contact_name": "...", "supplier_email": "...", "supplier_phone": "...",
      "note": "...",
      "items": [{"product_id": 12, "qty": 100, "unit_price_czk": 45.50}, ...]
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}

    items_in = body.get("items")
    if not isinstance(items_in, list) or not items_in:
        return jsonify({"error": "Nákupní objednávka musí obsahovat alespoň jednu položku."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            supplier = None
            supplier_id = body.get("supplier_id")
            if supplier_id is not None:
                cur.execute("SELECT * FROM shop_suppliers WHERE id=%s", (supplier_id,))
                supplier = cur.fetchone()
                if not supplier:
                    conn.rollback()
                    return jsonify({"error": "Zvolený dodavatel neexistuje."}), 400

            supplier_name = (body.get("supplier_name") or "").strip() or (supplier["name"] if supplier else "")
            if not supplier_name:
                conn.rollback()
                return jsonify({"error": "Chybí název dodavatele (supplier_id nebo supplier_name)."}), 400
            supplier_ico = (body.get("supplier_ico") or "").strip() or (supplier["ico"] if supplier else None)
            supplier_dic = (body.get("supplier_dic") or "").strip() or (supplier["dic"] if supplier else None)
            supplier_address = (body.get("supplier_address") or "").strip() or (supplier["address"] if supplier else None)
            supplier_contact_name = (body.get("supplier_contact_name") or "").strip() or (supplier["contact_name"] if supplier else None)
            supplier_email = (body.get("supplier_email") or "").strip() or (supplier["email"] if supplier else None)
            supplier_phone = (body.get("supplier_phone") or "").strip() or (supplier["phone"] if supplier else None)
            note = (body.get("note") or "").strip() or None

            clean_items = []
            total = 0.0
            for raw in items_in:
                if not isinstance(raw, dict):
                    conn.rollback()
                    return jsonify({"error": "Neplatná položka."}), 400
                try:
                    product_id = int(raw.get("product_id"))
                    qty = int(raw.get("qty"))
                    unit_price = float(raw.get("unit_price_czk"))
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatné product_id, množství nebo cena."}), 400
                if qty <= 0:
                    conn.rollback()
                    return jsonify({"error": "Množství musí být kladné celé číslo."}), 400
                # math.isfinite (bezpecnostni nalez, bot3/revize kodu
                # 2026-09-02, stejna oprava jako orders.py ~ř. 1510/1524) -
                # float() prijme "nan"/"inf" bez vyjimky, "< 0" je u obou
                # vzdy False.
                if not math.isfinite(unit_price) or unit_price < 0:
                    conn.rollback()
                    return jsonify({"error": "Cena nemůže být záporná."}), 400
                cur.execute("SELECT id, name, sku FROM shop_products WHERE id=%s", (product_id,))
                product = cur.fetchone()
                if not product:
                    conn.rollback()
                    return jsonify({"error": f"Produkt {product_id} neexistuje."}), 400
                line_total = round(unit_price * qty, 2)
                total += line_total
                clean_items.append({
                    "product_id": product["id"], "product_name_snapshot": product["name"],
                    "sku_snapshot": product["sku"], "unit_price_czk": unit_price,
                    "qty_ordered": qty, "line_total_czk": line_total,
                })
            total = round(total, 2)

            cur.execute(
                "INSERT INTO shop_purchase_orders "
                "(po_number, status, supplier_id, supplier_name, supplier_ico, supplier_dic, "
                " supplier_address, supplier_contact_name, supplier_email, supplier_phone, "
                " note, total_czk, created_by) "
                "VALUES ('', 'navrh', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (supplier_id, supplier_name, supplier_ico, supplier_dic, supplier_address,
                 supplier_contact_name, supplier_email, supplier_phone, note, total, admin["id"]),
            )
            po_id = cur.lastrowid
            cur.execute("SELECT created_at FROM shop_purchase_orders WHERE id=%s", (po_id,))
            created_at = cur.fetchone()["created_at"]
            po_number = _generate_po_number(po_id, created_at)
            cur.execute("UPDATE shop_purchase_orders SET po_number=%s WHERE id=%s", (po_number, po_id))

            for it in clean_items:
                cur.execute(
                    "INSERT INTO shop_purchase_order_items "
                    "(purchase_order_id, product_id, product_name_snapshot, sku_snapshot, "
                    " unit_price_czk, qty_ordered, line_total_czk) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (po_id, it["product_id"], it["product_name_snapshot"], it["sku_snapshot"],
                     it["unit_price_czk"], it["qty_ordered"], it["line_total_czk"]),
                )

            cur.execute(
                "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
                "VALUES (%s, 'navrh', %s, 'Nákupní objednávka vytvořena.')",
                (po_id, admin["id"]),
            )
        conn.commit()
    finally:
        conn.close()

    log_audit(admin["id"], "create", "purchase_order", po_id, po_number)
    return jsonify({"status": "ok", "id": po_id, "po_number": po_number, "total_czk": total}), 201


@app.post("/api/admin/purchase-orders/from-cart")
@require_permission("nakupni_objednavky", "vytvorit")
def admin_po_create_from_cart():
    """Nakupni objednavka primo z REALNEHO eshopoveho kosiku prihlaseneho
    stafera (Robert primo, 2026-09-28: "chci klikat položky do
    objednávky pro odeslání dodavateli přímo v našem eshopu, jen se to
    neuloží jako objednávka přijatá, nýbrž jako objednávka nákupní").

    Staff prochazi ZIVY e-shop (product.html) a pridava polozky do SVEHO
    kosiku UPLNE STEJNYM tlacitkem "Přidat do košíku" jako zakaznik -
    zadna paralelni/duplikovana logika pro prirezy/varianty sestav/
    montaz, ta uz existuje v /api/cart/items a tady se jen ZNOVU POUZIJE
    (_fetch_cart_rows/_serialize_cart z cart.py). Rozdil je AZ TADY, na
    konci: misto normalniho checkoutu (ktery by z toho udelal PRODEJNI
    objednavku - viz modulovy docstring, "zamena s objednavkami od
    zakazniku by byla nebezpecna") se aktualni obsah kosiku prevede na
    NAKUPNI objednavku danemu dodavateli. Kosik se po uspechu vyprazdni
    (polozky "presly" do PO, nemaji zustat viset a hrozit, ze se omylem
    znovu objednaji/smichaji s pristim nakupem).

    Cena/ks se preberou z kosiku (unit_price_czk - PRODEJNI cena
    zakaznikum, ne skutecna nakupni/dodavatelska cena!) jen jako VYCHOZI
    navrh, presne jako u rucne zadanych polozek v admin_po_create - admin
    ji v adminu (Upravit nakupni objednavku) porad muze prepsat na
    skutecnou fakturovanou cenu od dodavatele. Cena montaze/rezu (viz
    cut_service_total_czk/montaz_czk v cart.py) se VYNECHAVA - to jsou
    Logiman-interni sluzby, ne neco, co plati dodavatel.
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    supplier_id = body.get("supplier_id")
    supplier_name_in = (body.get("supplier_name") or "").strip()
    note = (body.get("note") or "").strip() or None
    if not supplier_id and not supplier_name_in:
        return jsonify({"error": "Vyber dodavatele nebo zadej název ručně."}), 400

    cart_owner_id = _cart_owner_id(admin)
    conn = get_conn()
    try:
        rows = _fetch_cart_rows(conn, cart_owner_id)
        cart = _serialize_cart(rows)
        if not cart["items"]:
            conn.rollback()
            return jsonify({"error": "Košík je prázdný - nejprve přidej položky přes „Přidat do košíku” na detailu produktu."}), 400
        with conn.cursor() as cur:
            supplier = None
            if supplier_id is not None:
                cur.execute("SELECT * FROM shop_suppliers WHERE id=%s", (supplier_id,))
                supplier = cur.fetchone()
                if not supplier:
                    conn.rollback()
                    return jsonify({"error": "Zvolený dodavatel neexistuje."}), 400
            supplier_name = supplier_name_in or (supplier["name"] if supplier else "")
            if not supplier_name:
                conn.rollback()
                return jsonify({"error": "Chybí název dodavatele."}), 400

            clean_items = []
            total = 0.0
            for it in cart["items"]:
                line_total = round(it["unit_price_czk"] * it["qty"], 2)
                total += line_total
                clean_items.append({
                    "product_id": it["product_id"], "product_name_snapshot": it["name"],
                    "sku_snapshot": it["sku"], "unit_price_czk": it["unit_price_czk"],
                    "qty_ordered": it["qty"], "line_total_czk": line_total,
                })
            total = round(total, 2)

            cur.execute(
                "INSERT INTO shop_purchase_orders "
                "(po_number, status, supplier_id, supplier_name, supplier_ico, supplier_dic, "
                " supplier_address, supplier_contact_name, supplier_email, supplier_phone, "
                " note, total_czk, created_by) "
                "VALUES ('', 'navrh', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (supplier_id, supplier_name,
                 supplier["ico"] if supplier else None, supplier["dic"] if supplier else None,
                 supplier["address"] if supplier else None, supplier["contact_name"] if supplier else None,
                 supplier["email"] if supplier else None, supplier["phone"] if supplier else None,
                 note, total, admin["id"]),
            )
            po_id = cur.lastrowid
            cur.execute("SELECT created_at FROM shop_purchase_orders WHERE id=%s", (po_id,))
            created_at = cur.fetchone()["created_at"]
            po_number = _generate_po_number(po_id, created_at)
            cur.execute("UPDATE shop_purchase_orders SET po_number=%s WHERE id=%s", (po_number, po_id))

            for it in clean_items:
                cur.execute(
                    "INSERT INTO shop_purchase_order_items "
                    "(purchase_order_id, product_id, product_name_snapshot, sku_snapshot, "
                    " unit_price_czk, qty_ordered, line_total_czk) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (po_id, it["product_id"], it["product_name_snapshot"], it["sku_snapshot"],
                     it["unit_price_czk"], it["qty_ordered"], it["line_total_czk"]),
                )

            cur.execute(
                "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
                "VALUES (%s, 'navrh', %s, 'Nákupní objednávka vytvořena z eshopového košíku.')",
                (po_id, admin["id"]),
            )
            cur.execute("DELETE FROM shop_cart_items WHERE user_id=%s", (cart_owner_id,))
        conn.commit()
    finally:
        conn.close()

    log_audit(admin["id"], "create", "purchase_order", po_id, po_number)
    return jsonify({"status": "ok", "id": po_id, "po_number": po_number, "total_czk": total}), 201


@app.get("/api/admin/purchase-orders")
@require_permission("nakupni_objednavky", "zobrazit")
def admin_po_list():
    """Seznam nakupnich objednavek, ?status=... filtr, counts pro taby (stejny vzor jako admin_orders_list)."""
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()
    if status and status not in PO_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400

    where, params = [], []
    if status:
        where.append("status=%s")
        params.append(status)
    if q:
        where.append("(po_number LIKE %s OR supplier_name LIKE %s)")
        like = f"%{q}%"
        params += [like, like]

    # Stránkování (task #78/82)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM shop_purchase_orders"
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY created_at DESC", page, page_size)

            cur.execute("SELECT status, COUNT(*) AS n FROM shop_purchase_orders GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM shop_purchase_orders")
            all_count = cur.fetchone()["n"]
    finally:
        conn.close()

    counts = {"all": all_count}
    for s in PO_STATUSES:
        counts[s] = status_counts.get(s, 0)
    resp = {"purchase_orders": [_serialize_po(r) for r in rows], "counts": counts}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/admin/purchase-orders/<int:po_id>")
@require_permission("nakupni_objednavky", "zobrazit")
def admin_po_get(po_id):
    conn = get_conn()
    try:
        po, items = _fetch_po_with_items(conn, po_id)
        history = []
        if po:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT h.*, u.name AS changed_by_name FROM shop_purchase_order_status_history h "
                    "LEFT JOIN app_users u ON u.id = h.changed_by "
                    "WHERE h.purchase_order_id=%s ORDER BY h.changed_at ASC, h.id ASC",
                    (po_id,),
                )
                history = cur.fetchall()
    finally:
        conn.close()
    if not po:
        return jsonify({"error": "Nákupní objednávka neexistuje."}), 404

    result = _serialize_po(po)
    result["items"] = [_serialize_po_item(i) for i in items]
    result["history"] = [
        {"status": h["status"], "status_label": PO_STATUS_LABELS_CZ.get(h["status"], h["status"]),
         "changed_by": h["changed_by"], "changed_by_name": h["changed_by_name"],
         "changed_at": _dt(h["changed_at"]), "note": h["note"]}
        for h in history
    ]
    return jsonify({"purchase_order": result})


@app.get("/api/admin/purchase-orders/<int:po_id>/export-csv")
@require_permission("nakupni_objednavky", "zobrazit")
def admin_po_export_csv(po_id):
    """
    Export polozek objednavky do CSV BEZ cen (Robert 2026-09-30: "u
    nakupni objednavky pridat moznost export do csv, bez cen") - urceno
    k predani mimo admin (napr. skladu/dopravci pri prijmu), kde nakupni
    cena od dodavatele nema co delat. Stejny vzor jako products.py/
    categories.py export (io.StringIO + csv.writer, zadny BOM/strednik -
    konzistentne s existujicimi export endpointy).
    """
    conn = get_conn()
    try:
        po, items = _fetch_po_with_items(conn, po_id)
    finally:
        conn.close()
    if not po:
        return jsonify({"error": "Nákupní objednávka neexistuje."}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "nazev", "objednano_ks", "prijato_ks"])
    for it in items:
        writer.writerow([
            it["sku_snapshot"] or "", it["product_name_snapshot"],
            it["qty_ordered"], it["qty_received"],
        ])
    log_audit(current_user()["id"], "export", "purchase_order", po_id, po["po_number"])
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{po["po_number"]}.csv"'},
    )


def _apply_po_status_change(conn, po_id, admin_id, new_status=None, admin_note=None, history_note=None):
    """
    Jadro rucni zmeny stavu/admin_note JEDNE nakupni objednavky - sdilene
    mezi PUT /api/admin/purchase-orders/<id> (jednotliva zmena) a
    POST /api/admin/purchase-orders/bulk-status (hromadna zmena), aby
    obe cesty prosly STEJNOU validaci ALLOWED_PO_TRANSITIONS a stejne
    zapisovaly do shop_purchase_order_status_history (vedlejsi ucinek,
    kvuli kteremu hromadna akce NESMI byt holy UPDATE - viz
    NAVRH_HROMADNE_AKCE.md sekce 2/4).

    Pracuje na JIZ OTEVRENE `conn` - commit/rollback/close resi volajici
    (bulk varianta potrebuje commitovat/rollbackovat po kazde polozce
    zvlast, aby selhani jedne objednavky nezhatilo zbytek davky).

    Vraci (ok: bool, error: str|None, status_changed: bool) - status_changed
    je True jen kdyz se stav SKUTECNE zmenil (bot16, 2026-09-02, revize
    bot3): volajici podle nej posilaji e-mail dodavateli, takze PUT
    {status:"odeslano", admin_note} na uz odeslanou NO je idempotentni a
    nezaradi e-mail do fronty podruhe.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM shop_purchase_orders WHERE id=%s FOR UPDATE", (po_id,))
        po = cur.fetchone()
        if not po:
            return False, "Nákupní objednávka neexistuje.", False

        fields, params = [], []
        status_changed = False
        if new_status is not None and new_status != po["status"]:
            allowed = ALLOWED_PO_TRANSITIONS.get(po["status"], set())
            if new_status not in allowed:
                return False, (
                    f"Přechod ze stavu „{PO_STATUS_LABELS_CZ.get(po['status'])}“ "
                    f"do „{PO_STATUS_LABELS_CZ.get(new_status)}“ není povolen."
                ), False
            fields.append("status=%s")
            params.append(new_status)
            status_changed = True
            cur.execute(
                "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
                "VALUES (%s,%s,%s,%s)",
                (po_id, new_status, admin_id, history_note),
            )
        if admin_note is not None:
            fields.append("admin_note=%s")
            params.append(admin_note)
        if not fields:
            return False, "Nebyla zadána žádná změna.", False
        params.append(po_id)
        cur.execute(f"UPDATE shop_purchase_orders SET {', '.join(fields)} WHERE id=%s", params)
    return True, None, status_changed


def _po_email_body(po, items):
    lines = [
        "Dobrý den,",
        "",
        f"zasíláme objednávku {po['po_number']}.",
        "",
        "Objednáváme:",
    ]
    for it in items:
        lines.append(f"  - {it['product_name_snapshot']}: {it['qty_ordered']} ks"
                     + (f" à {_money(it['unit_price_czk']):.2f} Kč" if it["unit_price_czk"] else ""))
    total = _money(po["total_czk"]) or 0
    lines += ["", f"Celkem: {total:,.2f} Kč".replace(",", " "), ""]
    if po.get("note"):
        lines += [po["note"], ""]
    lines += ["Děkujeme za potvrzení a sdělení termínu dodání.", "", "S pozdravem", "LOGiMAN"]
    return "\n".join(lines)


def send_po_to_supplier(po_id):
    """Robert 2026-07-31: potvrzenim nakupni objednavky adminem
    (navrh -> odeslano) "se automaticky odesle dodavateli". Volano AZ PO
    commitu zmeny stavu - selhani SMTP nesmi shodit samotny prechod
    (stejny vzor jako u zakaznickych e-mailu v orders.py).

    Vraci (status, error): status 'sent' | 'failed' | 'skipped'.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_purchase_orders WHERE id=%s", (po_id,))
            po = cur.fetchone()
            if not po:
                return "failed", "Nákupní objednávka neexistuje."
            cur.execute(
                "SELECT product_name_snapshot, unit_price_czk, qty_ordered "
                "FROM shop_purchase_order_items WHERE purchase_order_id=%s ORDER BY id",
                (po_id,),
            )
            items = cur.fetchall()
    finally:
        conn.close()

    recipient = (po.get("supplier_email") or "").strip()
    if not recipient:
        # Typicky automaticky zalozena NO s "Neznamy dodavatel" - admin
        # nejdriv musi doplnit dodavatele/e-mail. Neni to chyba prechodu.
        return "skipped", "Dodavatel nemá vyplněný e-mail – objednávku odešli ručně."

    try:
        import emails
        _log_id, status, err = emails.send_and_log(
            None, template_key="purchase_order", recipient=recipient,
            subject=f"Objednávka {po['po_number']}",
            body=_po_email_body(po, items), admin=None, auto=True,
            purchase_order_id=po_id,
        )
        return status, err
    except Exception as e:
        return "failed", str(e)


@app.put("/api/admin/purchase-orders/<int:po_id>")
@require_permission("nakupni_objednavky", "upravit")
def admin_po_update(po_id):
    """
    Rucni stavovy prechod (jen navrh->odeslano, nebo ->zruseno z
    aktivniho stavu - viz ALLOWED_PO_TRANSITIONS) + admin_note.
    castecne_prijato/prijato NEJDOU nastavit rucne - dopocitavaji se
    automaticky z POST .../receive.

    Body: {"status": "odeslano", "admin_note": "...", "history_note": "..."}
    """
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    admin_note = body.get("admin_note")
    history_note = (body.get("history_note") or "").strip() or None
    admin = current_user()

    if new_status is not None and new_status not in PO_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400
    if new_status in ("castecne_prijato", "prijato"):
        return jsonify({"error": "Tento stav se nastavuje automaticky při příjmu zboží (viz POST .../receive)."}), 400

    conn = get_conn()
    try:
        ok, err, status_changed = _apply_po_status_change(conn, po_id, admin["id"], new_status, admin_note, history_note)
        if not ok:
            conn.rollback()
            code = 404 if err == "Nákupní objednávka neexistuje." else 400
            return jsonify({"error": err}), code
        conn.commit()
    finally:
        conn.close()
    # Robert 2026-07-31: potvrzeni adminem (navrh -> odeslano) = "automaticky
    # se odesle dodavateli". Az PO commitu - selhani SMTP nesmi shodit
    # samotny prechod stavu.
    # Jen pri SKUTECNEM prechodu do "odeslano" - opakovany PUT se stejnym
    # stavem (napr. jen zmena admin_note) e-mail znovu nezaradi.
    email_status = email_error = None
    if status_changed and new_status == "odeslano":
        email_status, email_error = send_po_to_supplier(po_id)
    return jsonify({"status": "ok", "email_status": email_status, "email_error": email_error})


@app.post("/api/admin/purchase-orders/bulk-status")
@require_permission("nakupni_objednavky", "upravit")
def admin_po_bulk_status():
    """
    Hromadna zmena stavu vybranych nakupnich objednavek. KRITICKE: nákupní
    objednávky maji vedlejsi ucinky (zapis do stavove historie, a v
    budoucnu pripadne navazane sklad. pohyby pri prijmu) - proto tohle
    NENI holy UPDATE, ale smycka volajici sdilenou `_apply_po_status_change()`
    (stejnou funkci jako PUT /api/admin/purchase-orders/<id>) pro kazde id
    zvlast, s vlastnim commit/rollback per polozka - selhani jedne
    objednavky (napr. nepovoleny prechod stavu) nezastavi zbytek davky.

    castecne_prijato/prijato nejdou nastavit rucne (stejne jako u
    jednopolozkove varianty - dopocitavaji se z POST .../receive).

    Body: {"ids": [1,2,3], "status": "odeslano", "history_note": "..."}
    Odpoved: {"status": "ok", "updated": N, "failed": [{"id": X, "error": "..."}]}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err

    new_status = body.get("status")
    history_note = (body.get("history_note") or "").strip() or None
    if not new_status or new_status not in PO_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400
    if new_status in ("castecne_prijato", "prijato"):
        return jsonify({"error": "Tento stav se nastavuje automaticky při příjmu zboží (viz POST .../receive)."}), 400

    updated = 0
    failed = []
    sent_ids = []
    conn = get_conn()
    try:
        for po_id in ids:
            try:
                ok, item_err, status_changed = _apply_po_status_change(conn, po_id, admin["id"], new_status, None, history_note)
                if ok:
                    conn.commit()
                    updated += 1
                    if status_changed and new_status == "odeslano":
                        sent_ids.append(po_id)
                else:
                    conn.rollback()
                    failed.append({"id": po_id, "error": item_err})
            except Exception as exc:
                conn.rollback()
                failed.append({"id": po_id, "error": str(exc)})
    finally:
        conn.close()

    # Stejny vzor jako u jednopolozkoveho PUT vyse (send_po_to_supplier
    # AZ PO commitu, selhani SMTP/logovani nesmi shodit prechod stavu) -
    # bug nahlaseny Robertem 2026-08-24: hromadna akce menila stav na
    # "odeslano", ale e-mail se vubec nezalogoval/nezaslal ke schvaleni
    # (na rozdil od jednopolozkove varianty), protoze tohle volani tu
    # chybelo.
    for po_id in sent_ids:
        send_po_to_supplier(po_id)

    log_audit(
        admin["id"], "bulk_status", "purchase_order", None,
        f"{updated} objednávek → {PO_STATUS_LABELS_CZ.get(new_status, new_status)}"
        + (f", {len(failed)} selhalo" if failed else ""),
    )
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


def _delete_one_purchase_order(cur, po_id):
    """
    Smaze JEDNU nakupni objednavku i s vracenim skladoveho dopadu a
    smazanim navazanych e-mailu. Sdilena logika pro admin_po_bulk_delete
    NIZE i pro kaskadove mazani PO pri smazani dodavatele
    (admin_suppliers_delete/_bulk_delete) - Robert 2026-08-02: "smaže-li
    se jakýkolikoli doklad, prvek, tzn i nák.obj, musí se smazat i každý
    návazný doklad pohyb cokoli co navazuje v DB".

    KRITICKE: PO ve stavu castecne_prijato/prijato uz VYVOLALY vedlejsi
    ucinek (POST .../receive zvysil stock_qty + zapsal
    shop_stock_movements) - pred smazanim samotne PO se tenhle skladovy
    dopad musi vratit, jinak by sklad zustal neopravitelne nekonzistentni
    (viz reverse_and_delete_stock_movements - presny opak delty pri
    vytvoreni, pripadny prusak do zaporu pohyb jen preskoci).

    shop_emails.purchase_order_id NEMA v DB zadnou FK (na rozdil od
    order_id/document_id) - bez tohohle rucniho smazani by e-maily
    dodavateli zustaly osirele s odkazem do prazdna po smazane PO
    (presne tenhle bug Robert nahlasil).

    shop_purchase_order_items / shop_purchase_order_status_history
    NEMAJI ON DELETE CASCADE (viz sql/2026-07-25_purchase_orders.sql) -
    proto se mazou explicitne v ramci stejne transakce, pred smazanim
    radku shop_purchase_orders.

    Vraci None, pokud PO neexistuje, jinak dict {"item_ids": [...] (pro
    gallery cleanup u volajiciho), "stock_movement_ids": [...],
    "stock_failed": [...]}.
    """
    cur.execute("SELECT po_number FROM shop_purchase_orders WHERE id=%s", (po_id,))
    row = cur.fetchone()
    if not row:
        return None
    cur.execute(
        "SELECT id FROM shop_stock_movements WHERE document_number=%s",
        (row["po_number"],),
    )
    movement_ids = [r["id"] for r in cur.fetchall()]
    stock_movement_ids, stock_failed = [], []
    if movement_ids:
        stock_movement_ids, stock_failed = reverse_and_delete_stock_movements(cur, movement_ids)
    cur.execute("SELECT id FROM shop_purchase_order_items WHERE purchase_order_id=%s", (po_id,))
    item_ids = [r["id"] for r in cur.fetchall()]
    cur.execute("DELETE FROM shop_emails WHERE purchase_order_id=%s", (po_id,))
    cur.execute("DELETE FROM shop_purchase_order_status_history WHERE purchase_order_id=%s", (po_id,))
    cur.execute("DELETE FROM shop_purchase_order_items WHERE purchase_order_id=%s", (po_id,))
    cur.execute("DELETE FROM shop_purchase_orders WHERE id=%s", (po_id,))
    return {"item_ids": item_ids, "stock_movement_ids": stock_movement_ids, "stock_failed": stock_failed}


@app.post("/api/admin/purchase-orders/bulk-delete")
@require_permission("nakupni_objednavky", "smazat")
def admin_po_bulk_delete():
    """
    Hromadne smazani nakupnich objednavek pres _delete_one_purchase_order()
    vyse - viz jeji docstring pro detaily (vraceni skladu, smazani
    navazanych e-mailu). KRITICKE: na rozdil od bulk-status tohle je
    skutecne mazani radku (ne zmena stavu na "zruseno").

    Body: {"ids": [1,2,3]}
    Odpoved: {"status": "ok", "deleted": N, "failed": [{"id": X, "error": "..."}],
              "stock_reversed": N, "stock_failed": [...]}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err

    deleted = 0
    failed = []
    stock_movement_ids = []
    stock_failed = []
    all_item_ids = []
    conn = get_conn()
    try:
        for po_id in ids:
            try:
                with conn.cursor() as cur:
                    result = _delete_one_purchase_order(cur, po_id)
                    if result is None:
                        conn.rollback()
                        failed.append({"id": po_id, "error": "Nákupní objednávka neexistuje."})
                        continue
                conn.commit()
                deleted += 1
                stock_movement_ids.extend(result["stock_movement_ids"])
                stock_failed.extend(result["stock_failed"])
                all_item_ids.extend(result["item_ids"])
            except Exception as exc:
                conn.rollback()
                failed.append({"id": po_id, "error": str(exc)})
    finally:
        conn.close()
    import gallery_items
    for iid in all_item_ids:
        gallery_items.delete_items_for_owner("po_item", iid)
    for mv_id in stock_movement_ids:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)

    stock_note = f", {len(stock_movement_ids)} skladových pohybů vráceno" if stock_movement_ids else ""
    log_audit(
        admin["id"], "bulk_delete", "purchase_order", None,
        f"{deleted} nákupních objednávek smazáno" + (f", {len(failed)} selhalo" if failed else "") + stock_note,
    )
    return jsonify({
        "status": "ok", "deleted": deleted, "failed": failed,
        "stock_reversed": len(stock_movement_ids), "stock_failed": stock_failed,
    })


def _recompute_status(cur, po_id):
    cur.execute(
        "SELECT qty_ordered, qty_received FROM shop_purchase_order_items WHERE purchase_order_id=%s",
        (po_id,),
    )
    items = cur.fetchall()
    if all(i["qty_received"] >= i["qty_ordered"] for i in items):
        return "prijato"
    if any(i["qty_received"] > 0 for i in items):
        return "castecne_prijato"
    return None  # zadna zmena (nic jeste neprislo)


@app.post("/api/admin/purchase-orders/<int:po_id>/receive")
@require_permission("nakupni_objednavky", "upravit")
def admin_po_receive(po_id):
    """
    Prijem zbozi na sklad - navysi shop_products.stock_qty a zapise
    shop_stock_movements (movement_type='receipt', document_number=po_number),
    presne jako rucni prijem na sklad. Podporuje castecne dodavky (lze
    volat vicekrat, dokud qty_received < qty_ordered u nejake polozky).

    Body: {"items": [{"item_id": 5, "qty": 20}, ...], "note": "..."}
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    items_in = body.get("items")
    if not isinstance(items_in, list) or not items_in:
        return jsonify({"error": "Musíte zadat alespoň jednu přijímanou položku."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_purchase_orders WHERE id=%s FOR UPDATE", (po_id,))
            po = cur.fetchone()
            if not po:
                conn.rollback()
                return jsonify({"error": "Nákupní objednávka neexistuje."}), 404
            if po["status"] not in ("odeslano", "castecne_prijato"):
                conn.rollback()
                return jsonify({
                    "error": f"Příjem zboží lze provést jen u objednávky ve stavu "
                             f"„{PO_STATUS_LABELS_CZ['odeslano']}“ nebo „{PO_STATUS_LABELS_CZ['castecne_prijato']}“ "
                             f"(aktuální stav: „{PO_STATUS_LABELS_CZ.get(po['status'])}“)."
                }), 400

            for raw in items_in:
                if not isinstance(raw, dict):
                    conn.rollback()
                    return jsonify({"error": "Neplatná položka příjmu."}), 400
                try:
                    item_id = int(raw.get("item_id"))
                    qty = int(raw.get("qty"))
                except (TypeError, ValueError):
                    conn.rollback()
                    return jsonify({"error": "Neplatné item_id nebo množství."}), 400
                if qty <= 0:
                    conn.rollback()
                    return jsonify({"error": "Množství musí být kladné celé číslo."}), 400

                cur.execute(
                    "SELECT * FROM shop_purchase_order_items WHERE id=%s AND purchase_order_id=%s FOR UPDATE",
                    (item_id, po_id),
                )
                item = cur.fetchone()
                if not item:
                    conn.rollback()
                    return jsonify({"error": f"Položka {item_id} nepatří k této objednávce."}), 400
                remaining = item["qty_ordered"] - item["qty_received"]
                if qty > remaining:
                    conn.rollback()
                    return jsonify({
                        "error": f"Nelze přijmout {qty} ks „{item['product_name_snapshot']}“ - "
                                 f"zbývá jen {remaining} ks z objednaných {item['qty_ordered']} ks."
                    }), 400

                cur.execute(
                    "UPDATE shop_purchase_order_items SET qty_received = qty_received + %s WHERE id=%s",
                    (qty, item_id),
                )
                cur.execute(
                    "UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                    (qty, item["product_id"]),
                )
                cur.execute(
                    "INSERT INTO shop_stock_movements "
                    "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                    "VALUES (%s,'receipt',%s,%s,%s,%s,%s)",
                    (item["product_id"], qty, item["unit_price_czk"],
                     f"Příjem z nákupní objednávky {po['po_number']}", po["po_number"], admin["id"]),
                )

            new_status = _recompute_status(cur, po_id)
            if new_status:
                cur.execute("UPDATE shop_purchase_orders SET status=%s WHERE id=%s", (new_status, po_id))
                note = (body.get("note") or "").strip() or "Zboží přijato na sklad."
                cur.execute(
                    "INSERT INTO shop_purchase_order_status_history (purchase_order_id, status, changed_by, note) "
                    "VALUES (%s,%s,%s,%s)",
                    (po_id, new_status, admin["id"], note),
                )
        conn.commit()
    finally:
        conn.close()

    # Robert 2026-07-31: "automaticky pri naskladneni" - prijem zbozi z
    # nakupni objednavky muze odblokovat objednavky cekajici ve stavu
    # "ceka_na_zbozi" (stejny hook jako u rucni prijemky v app.py).
    import orders as _orders
    released, needs_review = _orders.try_release_waiting_orders()

    return jsonify({"status": "ok", "released_orders": released, "needs_manual_review_orders": needs_review})
