"""Planovane prispevky na socialni site (jen struktura, viz komentar u
puvodniho bloku v app.py - odesilani na Facebook API az bude Page
Access Token).

Vycleneno z api/app.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 1) - cisty presun, zadna zmena chovani/URL.
"""
from flask import request, jsonify

from app import app, get_conn, require_permission, current_user, parse_bulk_ids, bulk_delete

SOCIAL_POST_STATUSES = ("planned", "sent", "failed", "cancelled")


def _serialize_social_post(row):
    row = dict(row)
    if row.get("scheduled_at"):
        row["scheduled_at"] = row["scheduled_at"].isoformat()
    if row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    if row.get("sent_at"):
        row["sent_at"] = row["sent_at"].isoformat()
    return row


@app.get("/api/admin/social-posts")
@require_permission("nastaveni", "zobrazit")
def social_posts_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM social_scheduled_posts ORDER BY scheduled_at DESC")
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"posts": [_serialize_social_post(r) for r in rows]})


@app.post("/api/admin/social-posts")
@require_permission("nastaveni", "vytvorit")
def social_posts_create():
    body = request.get_json(silent=True) or {}
    platform = (body.get("platform") or "facebook").strip()
    message = (body.get("message") or "").strip()
    image_filename = (body.get("image_filename") or "").strip() or None
    scheduled_at = (body.get("scheduled_at") or "").strip()
    if not message:
        return jsonify({"error": "Vyplň text příspěvku."}), 400
    if not scheduled_at:
        return jsonify({"error": "Vyplň datum a čas naplánování."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO social_scheduled_posts (platform, message, image_filename, scheduled_at, status, created_by) "
                "VALUES (%s,%s,%s,%s,'planned',%s)",
                (platform, message, image_filename, scheduled_at, current_user()["id"]),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/social-posts/<int:post_id>")
@require_permission("nastaveni", "upravit")
def social_posts_update(post_id):
    body = request.get_json(silent=True) or {}
    fields = []
    params = []
    if "platform" in body:
        fields.append("platform=%s"); params.append((body.get("platform") or "facebook").strip())
    if "message" in body:
        msg = (body.get("message") or "").strip()
        if not msg:
            return jsonify({"error": "Text příspěvku nesmí být prázdný."}), 400
        fields.append("message=%s"); params.append(msg)
    if "image_filename" in body:
        fields.append("image_filename=%s"); params.append((body.get("image_filename") or "").strip() or None)
    if "scheduled_at" in body:
        sched = (body.get("scheduled_at") or "").strip()
        if not sched:
            return jsonify({"error": "Datum naplánování nesmí být prázdné."}), 400
        fields.append("scheduled_at=%s"); params.append(sched)
    if "status" in body:
        status = body.get("status")
        if status not in SOCIAL_POST_STATUSES:
            return jsonify({"error": "Neplatný stav."}), 400
        fields.append("status=%s"); params.append(status)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE social_scheduled_posts SET {', '.join(fields)} WHERE id=%s", params + [post_id])
            if cur.rowcount == 0:
                return jsonify({"error": "Příspěvek neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/social-posts/<int:post_id>")
@require_permission("nastaveni", "smazat")
def social_posts_delete(post_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM social_scheduled_posts WHERE id=%s", (post_id,))
            if cur.rowcount == 0:
                return jsonify({"error": "Příspěvek neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/admin/social-posts/bulk-delete")
@require_permission("nastaveni", "smazat")
def social_posts_bulk_delete():
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "social_scheduled_posts", ids)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "deleted": deleted})
