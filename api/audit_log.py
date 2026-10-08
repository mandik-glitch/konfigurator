"""Audit log (Robert 2026-07-25: "audit log a správa uživatelů" -
čtecí endpoint nad audit_log tabulkou zapisovanou z log_audit()).

log_audit() sama a jeji volani zustavaji v api/app.py (pouziva ji
temer kazdy modul v projektu) - tady jen cteni/mazani nad tabulkou.

Vycleneno z api/app.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 5) - cisty presun, zadna zmena chovani/URL.
"""
from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit,
    parse_bulk_ids, bulk_delete, get_pagination_args, paginated_query,
)


@app.get("/api/admin/audit-log")
@require_permission("audit_log", "zobrazit")
def admin_audit_log():
    entity_type = request.args.get("entity_type")
    user_id = request.args.get("user_id", type=int)
    where, params = [], []
    if entity_type:
        where.append("a.entity_type=%s")
        params.append(entity_type)
    if user_id:
        where.append("a.user_id=%s")
        params.append(user_id)
    # Stránkování (task #78/85) - nahrazuje puvodni jednoduchy ?limit=
    # (default 200/max 500 bez celkoveho poctu a bez stranky 2+).
    page, page_size = get_pagination_args(default_page_size=50)
    base_sql = """
        SELECT a.id, a.action, a.entity_type, a.entity_id, a.detail, a.created_at,
               u.name AS user_name, u.email AS user_email
        FROM audit_log a LEFT JOIN app_users u ON u.id = a.user_id
    """
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           " ORDER BY a.created_at DESC, a.id DESC", page, page_size)
    finally:
        conn.close()
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    resp = {"entries": rows}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.post("/api/admin/audit-log/bulk-delete")
@require_permission("audit_log", "smazat")
def admin_audit_log_bulk_delete():
    """Hromadne smazani zaznamu auditniho logu (Robert: "mazat musí být
    všude !!!" - 2026-07-26). POZOR: mazani auditniho logu odstranuje
    zaznam odpovednosti za minule akce - implementovano presne a vyhradne
    na vyslovnou, opakovanou zadost majitele appky, ne jako vychozi/
    doporucene chovani."""
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "audit_log", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_delete", "audit_log", None, f"{deleted} záznamů auditního logu smazáno")
    return jsonify({"status": "ok", "deleted": deleted})
