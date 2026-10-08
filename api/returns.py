"""Reklamace a vratky (bot18, 2026-09-05, Robert pres bot3, navazuje na
OFBiz srovnani "Za hranice objednavky" + navrh "Reklamace a vratky").
Schema: sql/2026-09-05_shop_returns.sql.

Samostatna entita navazana na shop_orders pres order_id - shop_orders
(status/delivery_state/billing_state) se timhle NEMENI, stejny princip
jako Party model / delivery_state-billing_state (bod 2/5 z drivejsiho
Dolibarr/ERPNext rozboru).

Robertova rozhodnuti (2026-09-05, pres bot3):
1. Dobropis - zaporna hodnota (viz documents.py::create_credit_note).
2. Poskozene/vadne zbozi se NEVRACI do prodejniho skladu.
3. Self-service - zakaznik muze zalozit sam ke SVE objednavce (ownership
   pres shop_orders.user_id, stejny vzor jako customer_documents_list
   v documents.py).
4. Vymena kus za kus - ZADNY automaticky flow. shop_returns.
   replacement_order_id je jen VOLITELNY odkaz, admin ho pripoji rucne
   az sam rucne zalozi jakoukoli novou objednavku (stejny produkt
   zdarma, jiny produkt s doplatkem, cokoli) - zadny novy samostatny
   typ, viz PUT .../replacement-order nize.

Endpointy:
  Admin (require_permission("reklamace", ...)):
    GET  /api/admin/returns                          - seznam (zobrazit)
    GET  /api/admin/returns/<id>                      - detail vc. polozek+historie (zobrazit)
    POST /api/admin/orders/<order_id>/returns          - zalozeni (vytvorit)
    PUT  /api/admin/returns/<id>/status                - prechod stavu, viz RETURN_ALLOWED_TRANSITIONS (upravit)
    POST /api/admin/returns/<id>/credit-note           - vystaveni dobropisu + prechod na "vyrizeno" (upravit)
    PUT  /api/admin/returns/<id>/replacement-order      - pripojeni/odpojeni nahradni objednavky (upravit)

  Zakaznik (login_required, vlastnictvi pres shop_orders.user_id):
    GET  /api/customer/orders/<order_id>/returns        - seznam vlastnich k objednavce
    POST /api/customer/orders/<order_id>/returns        - zalozeni pozadavku (status vzdy 'pozadovano')
    GET  /api/customer/returns/<id>                      - detail vlastni reklamace
"""

from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, log_audit, login_required
import documents

RETURN_TYPES = ("reklamace", "odstoupeni")
RETURN_STATUSES = ("pozadovano", "posuzovano", "schvaleno", "prijato", "vyrizeno", "zamitnuto", "zruseno")
RETURN_RESOLUTIONS = ("refund", "repair", "rejected")
ITEM_CONDITIONS = ("nepouzite", "poskozene", "vadne")

# Stavovy graf - stejny vzor jako ALLOWED_TRANSITIONS v orders.py. Zadny
# prechod odsud dal z terminalnich stavu (vyrizeno/zamitnuto/zruseno).
RETURN_ALLOWED_TRANSITIONS = {
    "pozadovano": {"posuzovano", "zruseno"},
    "posuzovano": {"schvaleno", "zamitnuto", "zruseno"},
    "schvaleno": {"prijato", "zruseno"},
    "prijato": {"vyrizeno"},
    "vyrizeno": set(),
    "zamitnuto": set(),
    "zruseno": set(),
}

STATUS_LABELS_CZ = {
    "pozadovano": "Požadováno", "posuzovano": "Posuzováno", "schvaleno": "Schváleno",
    "prijato": "Přijato zpět", "vyrizeno": "Vyřízeno", "zamitnuto": "Zamítnuto", "zruseno": "Zrušeno",
}

# Objednavka musi byt aspon expedovana, aby davalo smysl neco vracet -
# nejde vratit, co jeste fyzicky neopustilo sklad.
RETURNABLE_ORDER_STATUSES = ("expedovana", "fakturovana")


def _serialize_return(row):
    return {
        "id": row["id"], "order_id": row["order_id"],
        "order_number": row.get("order_number"), "customer_name": row.get("customer_name"),
        "return_number": row["return_number"], "return_type": row["return_type"],
        "status": row["status"], "status_label": STATUS_LABELS_CZ.get(row["status"], row["status"]),
        "reason": row["reason"], "resolution": row["resolution"], "admin_note": row["admin_note"],
        "credit_note_document_id": row["credit_note_document_id"],
        "replacement_order_id": row["replacement_order_id"],
        "created_by_user_id": row["created_by_user_id"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def _serialize_return_item(row):
    return {
        "id": row["id"], "order_item_id": row["order_item_id"],
        "product_name_snapshot": row.get("product_name_snapshot"),
        "qty": row["qty"], "unit_price_czk": float(row["unit_price_czk"]),
        "item_condition": row["item_condition"],
    }


def _fetch_return(cur, return_id):
    cur.execute(
        "SELECT r.*, o.order_number, o.customer_name "
        "FROM shop_returns r JOIN shop_orders o ON o.id = r.order_id WHERE r.id=%s",
        (return_id,),
    )
    return cur.fetchone()


def _fetch_return_items(cur, return_id):
    cur.execute(
        "SELECT ri.*, oi.product_name_snapshot, oi.product_id "
        "FROM shop_return_items ri JOIN shop_order_items oi ON oi.id = ri.order_item_id "
        "WHERE ri.return_id=%s ORDER BY ri.id",
        (return_id,),
    )
    return cur.fetchall()


def _fetch_return_history(cur, return_id):
    cur.execute(
        "SELECT status, changed_by, changed_at, note FROM shop_return_status_history "
        "WHERE return_id=%s ORDER BY changed_at ASC, id ASC",
        (return_id,),
    )
    return [
        {"status": r["status"], "status_label": STATUS_LABELS_CZ.get(r["status"], r["status"]),
         "changed_by": r["changed_by"], "changed_at": r["changed_at"].isoformat() if r["changed_at"] else None,
         "note": r["note"]}
        for r in cur.fetchall()
    ]


def _return_detail_payload(cur, return_id):
    row = _fetch_return(cur, return_id)
    if not row:
        return None
    return {
        **_serialize_return(row),
        "items": [_serialize_return_item(i) for i in _fetch_return_items(cur, return_id)],
        "history": _fetch_return_history(cur, return_id),
    }


def _remaining_returnable_qty(cur, order_item_id, exclude_return_id=None):
    """Puvodni qty na radku objednavky MINUS uz vracene mnozstvi (napric
    VSEMI vratkami krome zrusenych/zamitnutych - ty se nepocitaji, zadne
    zbozi fakticky neopustilo/nevratilo se). `exclude_return_id` - pri
    UPRAVE existujici vratky se jeji vlastni polozky do souctu nezapocitavaji
    (jinak by si sama sobe blokovala mnozstvi)."""
    cur.execute("SELECT qty FROM shop_order_items WHERE id=%s", (order_item_id,))
    oi = cur.fetchone()
    if not oi:
        return None
    q = (
        "SELECT COALESCE(SUM(ri.qty), 0) AS n FROM shop_return_items ri "
        "JOIN shop_returns r ON r.id = ri.return_id "
        "WHERE ri.order_item_id=%s AND r.status NOT IN ('zamitnuto','zruseno')"
    )
    params = [order_item_id]
    if exclude_return_id is not None:
        q += " AND r.id != %s"
        params.append(exclude_return_id)
    cur.execute(q, params)
    already = cur.fetchone()["n"]
    return oi["qty"] - already


def _create_return(cur, order, items_body, return_type, reason, created_by_user_id):
    """Sdilene jadro zalozeni vratky - pouziva admin i zakaznicka cesta.
    Vraci (return_id, error_response_tuple_or_None)."""
    if return_type not in RETURN_TYPES:
        return None, (jsonify({"error": "Neplatný return_type."}), 400)
    if order["status"] not in RETURNABLE_ORDER_STATUSES:
        return None, (jsonify({"error": "Objednávku v tomto stavu nelze reklamovat/vrátit."}), 400)
    if not items_body:
        return None, (jsonify({"error": "Musí být vybraná aspoň 1 položka."}), 400)

    clean_items = []
    for it in items_body:
        order_item_id = it.get("order_item_id")
        qty = it.get("qty")
        condition = it.get("item_condition") or "nepouzite"
        if condition not in ITEM_CONDITIONS:
            return None, (jsonify({"error": f"Neplatný stav položky '{condition}'."}), 400)
        if not isinstance(qty, int) or qty <= 0:
            return None, (jsonify({"error": "Množství musí být kladné celé číslo."}), 400)
        cur.execute(
            "SELECT id, order_id, unit_price_czk FROM shop_order_items WHERE id=%s",
            (order_item_id,),
        )
        oi = cur.fetchone()
        if not oi or oi["order_id"] != order["id"]:
            return None, (jsonify({"error": "Položka nepatří k této objednávce."}), 400)
        remaining = _remaining_returnable_qty(cur, order_item_id)
        if remaining is None or qty > remaining:
            return None, (jsonify({"error": f"Lze vrátit nejvýš {max(remaining or 0, 0)} ks u položky #{order_item_id}."}), 400)
        clean_items.append({"order_item_id": order_item_id, "qty": qty,
                             "unit_price_czk": oi["unit_price_czk"], "item_condition": condition})

    cur.execute(
        "INSERT INTO shop_returns (order_id, return_number, return_type, status, reason, created_by_user_id) "
        "VALUES (%s, '', %s, 'pozadovano', %s, %s)",
        (order["id"], return_type, reason, created_by_user_id),
    )
    return_id = cur.lastrowid
    # return_number generovan AZ PO insertu z auto-increment id (stejny
    # princip jako orders.py::_generate_order_number) - zadna samostatna
    # ciselna rada/zamek potreba, id uz je atomicky unikatni.
    return_number = f"RMA-{order['order_number']}-{return_id}"
    cur.execute("UPDATE shop_returns SET return_number=%s WHERE id=%s", (return_number, return_id))

    for it in clean_items:
        cur.execute(
            "INSERT INTO shop_return_items (return_id, order_item_id, qty, unit_price_czk, item_condition) "
            "VALUES (%s,%s,%s,%s,%s)",
            (return_id, it["order_item_id"], it["qty"], it["unit_price_czk"], it["item_condition"]),
        )
    cur.execute(
        "INSERT INTO shop_return_status_history (return_id, status, changed_by, note) VALUES (%s,'pozadovano',%s,%s)",
        (return_id, created_by_user_id, "Založeno."),
    )
    return return_id, None


# ---------------------------------------------------------------------------
# Admin endpointy
# ---------------------------------------------------------------------------

@app.get("/api/admin/returns")
@require_permission("reklamace", "zobrazit")
def admin_returns_list():
    status_filter = request.args.get("status") or None
    type_filter = request.args.get("return_type") or None
    order_id_filter = request.args.get("order_id", type=int)
    where, params = [], []
    if status_filter:
        where.append("r.status=%s")
        params.append(status_filter)
    if type_filter:
        where.append("r.return_type=%s")
        params.append(type_filter)
    if order_id_filter:
        where.append("r.order_id=%s")
        params.append(order_id_filter)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.*, o.order_number, o.customer_name "
                "FROM shop_returns r JOIN shop_orders o ON o.id = r.order_id "
                f"{where_sql} ORDER BY r.created_at DESC",
                params,
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"returns": [_serialize_return(r) for r in rows]})


@app.get("/api/admin/returns/<int:return_id>")
@require_permission("reklamace", "zobrazit")
def admin_return_detail(return_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            payload = _return_detail_payload(cur, return_id)
    finally:
        conn.close()
    if not payload:
        return jsonify({"error": "Reklamace/vratka neexistuje."}), 404
    return jsonify(payload)


@app.post("/api/admin/orders/<int:order_id>/returns")
@require_permission("reklamace", "vytvorit")
def admin_return_create(order_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            return_id, err = _create_return(
                cur, order, body.get("items") or [], body.get("return_type"),
                body.get("reason"), admin["id"],
            )
            if err:
                conn.rollback()
                return err
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "return", return_id, f"Založeno k objednávce #{order_id}")
    return jsonify({"status": "ok", "id": return_id})


@app.put("/api/admin/returns/<int:return_id>/status")
@require_permission("reklamace", "upravit")
def admin_return_update_status(return_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")
    note = body.get("note")
    resolution = body.get("resolution")
    item_conditions = body.get("item_conditions") or {}  # {order_return_item_id: condition}

    if new_status not in RETURN_STATUSES:
        return jsonify({"error": "Neplatný status."}), 400
    if resolution is not None and resolution not in RETURN_RESOLUTIONS:
        return jsonify({"error": "Neplatné řešení."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_returns WHERE id=%s FOR UPDATE", (return_id,))
            ret = cur.fetchone()
            if not ret:
                conn.rollback()
                return jsonify({"error": "Reklamace/vratka neexistuje."}), 404
            old_status = ret["status"]
            if new_status != old_status:
                allowed = RETURN_ALLOWED_TRANSITIONS.get(old_status, set())
                if new_status not in allowed:
                    conn.rollback()
                    return jsonify({"error": (
                        f"Přechod ze stavu „{STATUS_LABELS_CZ.get(old_status)}“ "
                        f"do „{STATUS_LABELS_CZ.get(new_status)}“ není povolen."
                    )}), 400

            # Zamitnuto vzdy nese resolution='rejected' - zadna nejasnost
            # co bylo "reseni" u zamitnute reklamace.
            if new_status == "zamitnuto":
                resolution = "rejected"

            if item_conditions:
                for item_id_str, cond in item_conditions.items():
                    if cond not in ITEM_CONDITIONS:
                        conn.rollback()
                        return jsonify({"error": f"Neplatný stav položky '{cond}'."}), 400
                    cur.execute(
                        "UPDATE shop_return_items SET item_condition=%s WHERE id=%s AND return_id=%s",
                        (cond, int(item_id_str), return_id),
                    )

            # Prechod NA "prijato" - fyzicky navrat zbozi. Jen NEPOUZITE
            # polozky se vraci do prodejniho skladu (Robertovo rozhodnuti
            # 2026-09-05: poskozene/vadne se NEVRACI) - stejny vzor jako
            # navrat skladu pri zruseni objednavky v orders.py.
            if new_status == "prijato" and old_status != "prijato":
                items = _fetch_return_items(cur, return_id)
                for ri in items:
                    if ri["item_condition"] != "nepouzite" or not ri["product_id"]:
                        continue
                    cur.execute(
                        "UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                        (ri["qty"], ri["product_id"]),
                    )
                    cur.execute(
                        "INSERT INTO shop_stock_movements "
                        "(product_id, movement_type, qty, unit_price_czk, note, document_number, user_id) "
                        "VALUES (%s, 'receipt', %s, %s, %s, %s, %s)",
                        (ri["product_id"], ri["qty"], ri["unit_price_czk"],
                         f"Vratka {ret['return_number']}", ret["return_number"], admin["id"]),
                    )

            set_sql = "status=%s"
            params = [new_status]
            if resolution is not None:
                set_sql += ", resolution=%s"
                params.append(resolution)
            params.append(return_id)
            cur.execute(f"UPDATE shop_returns SET {set_sql} WHERE id=%s", params)
            cur.execute(
                "INSERT INTO shop_return_status_history (return_id, status, changed_by, note) VALUES (%s,%s,%s,%s)",
                (return_id, new_status, admin["id"], note),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "return", return_id, f"status -> {new_status}")
    return jsonify({"status": "ok"})


@app.post("/api/admin/returns/<int:return_id>/credit-note")
@require_permission("reklamace", "upravit")
def admin_return_credit_note(return_id):
    """Vystavi dobropis (documents.py::create_credit_note) a rovnou
    prevede vratku do 'vyrizeno' - jedna admin akce = "vyresit vracenim
    penez", stejne jako jina 'vystavit doklad' tlacitka jinde v adminu
    delaji jeden ucetni krok najednou."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_returns WHERE id=%s FOR UPDATE", (return_id,))
            ret = cur.fetchone()
            if not ret:
                conn.rollback()
                return jsonify({"error": "Reklamace/vratka neexistuje."}), 404
            if ret["credit_note_document_id"]:
                conn.rollback()
                return jsonify({"error": "Dobropis k této vratce už existuje."}), 400
            if ret["status"] not in ("prijato", "schvaleno"):
                conn.rollback()
                return jsonify({"error": "Dobropis lze vystavit až po schválení/přijetí vratky."}), 400

            cur.execute("SELECT * FROM shop_orders WHERE id=%s", (ret["order_id"],))
            order = cur.fetchone()
            items = _fetch_return_items(cur, return_id)
            cur.execute(
                "SELECT * FROM shop_documents WHERE order_id=%s AND document_type='invoice' "
                "ORDER BY created_at DESC LIMIT 1",
                (ret["order_id"],),
            )
            original_invoice = cur.fetchone()

            result = documents.create_credit_note(
                cur, order, ret, items, original_invoice, documents._issued_by_label(admin),
            )
            cur.execute(
                "UPDATE shop_returns SET credit_note_document_id=%s, status='vyrizeno', resolution='refund' WHERE id=%s",
                (result["id"], return_id),
            )
            cur.execute(
                "INSERT INTO shop_return_status_history (return_id, status, changed_by, note) VALUES (%s,'vyrizeno',%s,%s)",
                (return_id, admin["id"], f"Vystaven dobropis {result['document_number']}."),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "document_credit_note", result["id"], result["document_number"])
    return jsonify({"status": "ok", **result})


@app.put("/api/admin/returns/<int:return_id>/replacement-order")
@require_permission("reklamace", "upravit")
def admin_return_replacement_order(return_id):
    """Pripoji/odpojí odkaz na nahradni objednavku - ZADNA automatika
    (Robertovo rozhodnuti 2026-09-05: vymena muze byt stejny produkt
    zdarma, jiny produkt s doplatkem, cokoli - admin novou objednavku
    zalozi RUCNE beznym zpusobem, tenhle endpoint jen propojuje uz
    existujici objednavku, stejny vzor jako crm_quotes.order_id)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")  # None = odpojit
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_returns WHERE id=%s", (return_id,))
            if not cur.fetchone():
                return jsonify({"error": "Reklamace/vratka neexistuje."}), 404
            if order_id is not None:
                cur.execute("SELECT id FROM shop_orders WHERE id=%s", (order_id,))
                if not cur.fetchone():
                    return jsonify({"error": "Objednávka neexistuje."}), 400
            cur.execute("UPDATE shop_returns SET replacement_order_id=%s WHERE id=%s", (order_id, return_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "return", return_id, f"replacement_order_id -> {order_id}")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Zakaznik: vlastni reklamace/vratky (Robertovo rozhodnuti 2026-09-05: self-service rovnou)
# ---------------------------------------------------------------------------

def _owns_order(cur, order_id, user):
    cur.execute("SELECT * FROM shop_orders WHERE id=%s", (order_id,))
    order = cur.fetchone()
    if not order:
        return None, (jsonify({"error": "Objednávka neexistuje."}), 404)
    if order["user_id"] != user["id"] and user["role"] != "admin":
        return None, (jsonify({"error": "Nemáte oprávnění k této objednávce.", "code": "forbidden"}), 403)
    return order, None


@app.get("/api/customer/orders/<int:order_id>/returns")
@login_required
def customer_returns_list(order_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order, err = _owns_order(cur, order_id, user)
            if err:
                return err
            cur.execute(
                "SELECT r.*, o.order_number, o.customer_name "
                "FROM shop_returns r JOIN shop_orders o ON o.id = r.order_id "
                "WHERE r.order_id=%s ORDER BY r.created_at DESC",
                (order_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"returns": [_serialize_return(r) for r in rows]})


@app.post("/api/customer/orders/<int:order_id>/returns")
@login_required
def customer_return_create(order_id):
    user = current_user()
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_orders WHERE id=%s FOR UPDATE", (order_id,))
            order = cur.fetchone()
            if not order:
                conn.rollback()
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if order["user_id"] != user["id"]:
                conn.rollback()
                return jsonify({"error": "Nemáte oprávnění k této objednávce.", "code": "forbidden"}), 403
            # Zakaznik sam nemuze urcit stav polozky "poskozene/vadne" na
            # sklade dopredu (to zjisti az admin pri fyzickem prevzeti) -
            # kazda zakaznikem zalozena polozka zacina jako "nepouzite",
            # admin ji pripadne zmeni pri prijeti (viz admin_return_
            # update_status item_conditions).
            items_in = body.get("items") or []
            for it in items_in:
                it["item_condition"] = "nepouzite"
            return_id, err = _create_return(
                cur, order, items_in, body.get("return_type"), body.get("reason"), user["id"],
            )
            if err:
                conn.rollback()
                return err
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": return_id})


@app.get("/api/customer/returns/<int:return_id>")
@login_required
def customer_return_detail(return_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            row = _fetch_return(cur, return_id)
            if not row:
                return jsonify({"error": "Reklamace/vratka neexistuje."}), 404
            cur.execute("SELECT user_id FROM shop_orders WHERE id=%s", (row["order_id"],))
            owner = cur.fetchone()
            if not owner or (owner["user_id"] != user["id"] and user["role"] != "admin"):
                return jsonify({"error": "Nemáte oprávnění k této reklamaci.", "code": "forbidden"}), 403
            payload = _return_detail_payload(cur, return_id)
    finally:
        conn.close()
    return jsonify(payload)
