"""Admin sprava prislusenstvi spoju (cfg_accessories) - cena se pocita
za behu z aktualniho poctu spoju ve 3D scene, tabulka neni nikym FK
referencovana.

Vycleneno z api/app.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 3) - cisty presun, zadna zmena chovani/URL.
"""
from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, log_audit, parse_bulk_ids, bulk_delete, bulk_update_fields


@app.get("/api/admin/accessories")
@require_permission("prislusenstvi", "zobrazit")
def admin_accessories_list():
    # Robert 2026-08-01: "chceme ukazovat veškeré možné archivní věci
    # položky" - stejny vzor jako shop_suppliers (purchase_orders.py) -
    # vychozi jen active=1, ?archived=1 prohodi na jen neaktivni.
    show_archived = request.args.get("archived") == "1"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, price_czk, qty_per_joint, active, sort_order
                FROM cfg_accessories WHERE active=%s ORDER BY sort_order, name
            """, (0 if show_archived else 1,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"rows": [
        {
            "id": r["id"], "name": r["name"],
            "price_czk": float(r["price_czk"]), "qty_per_joint": float(r["qty_per_joint"]),
            "active": bool(r["active"]), "sort_order": r["sort_order"],
        } for r in rows
    ]})


@app.post("/api/admin/accessories")
@require_permission("prislusenstvi", "vytvorit")
def admin_accessories_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Chybi nazev prislusenstvi."}), 400
    price = float(body.get("price_czk") or 0)
    qty = float(body.get("qty_per_joint") or 0)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cfg_accessories (name, price_czk, qty_per_joint, active) VALUES (%s,%s,%s,1)",
                (name, price, qty),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/accessories/<int:aid>")
@require_permission("prislusenstvi", "upravit")
def admin_accessories_update(aid):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        fields.append("name=%s"); params.append((body.get("name") or "").strip())
    if "price_czk" in body:
        fields.append("price_czk=%s"); params.append(float(body.get("price_czk") or 0))
    if "qty_per_joint" in body:
        fields.append("qty_per_joint=%s"); params.append(float(body.get("qty_per_joint") or 0))
    if "active" in body:
        fields.append("active=%s"); params.append(1 if body.get("active") else 0)
    if not fields:
        return jsonify({"error": "Nic ke zmene."}), 400
    params.append(aid)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE cfg_accessories SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/accessories/<int:aid>")
@require_permission("prislusenstvi", "smazat")
def admin_accessories_delete(aid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cfg_accessories WHERE id=%s", (aid,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


# Hromadne akce nad prislusenstvim (Robert: "mazat musí být všude !!!").
# Zadna FK/vedlejsi ucinek - cfg_accessories neni nikym referencovano
# (cena se pocita za behu z aktualniho poctu spoju ve 3D scene) - staci
# sdileny bulk_delete()/bulk_update_fields().
@app.post("/api/admin/accessories/bulk-delete")
@require_permission("prislusenstvi", "smazat")
def admin_accessories_bulk_delete():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "cfg_accessories", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_delete", "accessory", None, f"{deleted} příslušenství smazáno")
    return jsonify({"status": "ok", "deleted": deleted})


@app.post("/api/admin/accessories/bulk-active")
@require_permission("prislusenstvi", "upravit")
def admin_accessories_bulk_active():
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
            updated = bulk_update_fields(cur, "cfg_accessories", ids, {"active": active})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_active", "accessory", None, f"{updated} příslušenství -> active={active}")
    return jsonify({"status": "ok", "updated": updated})
