"""Sprava uzivatelu admin panelu (/api/admin/users) - role, aktivace,
hromadne akce s pojistkou proti smazani posledniho aktivniho admina.

Vycleneno z api/app.py (bot13, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 7) - cisty presun, zadna zmena chovani/URL.
"""
import pymysql
from flask import request, jsonify
from werkzeug.security import generate_password_hash

from app import (
    app,
    get_conn,
    require_permission,
    current_user,
    log_audit,
    parse_bulk_ids,
    bulk_update_fields,
    create_party,
)


# --- Sprava uzivatelu (jen admin) ---
@app.get("/api/admin/users")
@require_permission("uzivatele", "zobrazit")
def admin_users_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, name, role, active, created_at FROM app_users ORDER BY created_at")
            rows = cur.fetchall()
    finally:
        conn.close()
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify({"users": rows})


@app.post("/api/admin/users")
@require_permission("uzivatele", "vytvorit")
def admin_users_create():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    name = (body.get("name") or "").strip()
    role = body.get("role") or "user"
    password = body.get("password") or ""
    if role not in ("admin", "manager", "user", "skladnik", "ucetni", "monter", "sklad"):
        return jsonify({"error": "Neplatná role."}), 400
    if not email or not password:
        return jsonify({"error": "Vyplň e-mail i heslo."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM app_users WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({"error": "Uživatel s tímto e-mailem už existuje."}), 400
            party_id = create_party(cur, full_name=name, primary_email=email)
            cur.execute(
                "INSERT INTO app_users (email, password_hash, name, role, active, party_id) "
                "VALUES (%s,%s,%s,%s,1,%s)",
                (email, generate_password_hash(password), name, role, party_id),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "user", new_id, f"{email} ({role})")
    return jsonify({"status": "ok", "id": new_id})


@app.put("/api/admin/users/<int:user_id>")
@require_permission("uzivatele", "upravit")
def admin_users_update(user_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        fields.append("name=%s"); params.append(body["name"])
    if "role" in body and body["role"] in ("admin", "manager", "user", "skladnik", "ucetni", "monter", "sklad"):
        fields.append("role=%s"); params.append(body["role"])
    if "active" in body:
        fields.append("active=%s"); params.append(1 if body["active"] else 0)
    if body.get("password"):
        fields.append("password_hash=%s"); params.append(generate_password_hash(body["password"]))
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(user_id)
    changed_fields = [f.split("=")[0] for f in fields]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE app_users SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "user", user_id, ", ".join(changed_fields))
    return jsonify({"status": "ok"})


def _protect_last_active_admin(cur, ids, found_users, would_lose_admin_status):
    """Spolecna pojistka pro bulk-role/bulk-active (V11, bot3, 2026-07-26).
    Pokud by akce (uplatnena na VSECHNY ids) shodila posledniho aktivniho
    admina, vybere jeden (nejnizsi id) z ohrozenych, vyjme ho z davky
    (zustane nezmeneny) a vrati pro nej failed-polozku."""
    if not would_lose_admin_status:
        return None, None
    losing_ids = [i for i in ids if i in found_users
                  and found_users[i]["role"] == "admin" and found_users[i]["active"]]
    if not losing_ids:
        return None, None
    cur.execute("SELECT COUNT(*) AS c FROM app_users WHERE role='admin' AND active=1")
    total_active_admins = cur.fetchone()["c"]
    if total_active_admins - len(losing_ids) >= 1:
        return None, None
    protected_id = min(losing_ids)
    return protected_id, {"id": protected_id,
        "error": "Nelze provést - jde o posledního aktivního administrátora v systému."}


@app.post("/api/admin/users/bulk-role")
@require_permission("uzivatele", "upravit")
def admin_users_bulk_role():
    # Hromadna zmena role vybranych uzivatelu (V11, bot3, 2026-07-26, viz
    # NAVRH_HROMADNE_AKCE.md). Pojistka: nesmi jit odebrat administratorska
    # prava POSLEDNIMU aktivnimu adminovi v systemu.
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    role = body.get("role")
    if role not in ("admin", "manager", "user", "skladnik", "ucetni", "monter", "sklad"):
        return jsonify({"error": "Neplatná role."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, role, active FROM app_users WHERE id IN ({placeholders})", ids)
            found = {r["id"]: r for r in cur.fetchall()}
            failed = [{"id": i, "error": "Uživatel neexistuje."} for i in ids if i not in found]
            protected_id, protect_failure = _protect_last_active_admin(
                cur, ids, found, would_lose_admin_status=(role != "admin"))
            if protect_failure:
                failed.append(protect_failure)
            update_ids = [i for i in ids if i in found and i != protected_id]
            updated = 0
            if update_ids:
                updated = bulk_update_fields(cur, "app_users", update_ids, {"role": role})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_role", "user", None,
              f"{updated} uživatelů -> role={role}" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


@app.post("/api/admin/users/bulk-active")
@require_permission("uzivatele", "upravit")
def admin_users_bulk_active():
    # Hromadna aktivace/deaktivace vybranych uzivatelu (V11, bot3,
    # 2026-07-26, viz NAVRH_HROMADNE_AKCE.md). Stejna pojistka posledniho
    # aktivniho admina jako u bulk-role.
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
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id, role, active FROM app_users WHERE id IN ({placeholders})", ids)
            found = {r["id"]: r for r in cur.fetchall()}
            failed = [{"id": i, "error": "Uživatel neexistuje."} for i in ids if i not in found]
            protected_id, protect_failure = _protect_last_active_admin(
                cur, ids, found, would_lose_admin_status=(not active))
            if protect_failure:
                failed.append(protect_failure)
            update_ids = [i for i in ids if i in found and i != protected_id]
            updated = 0
            if update_ids:
                updated = bulk_update_fields(cur, "app_users", update_ids, {"active": active})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_active", "user", None,
              f"{updated} uživatelů -> active={active}" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "updated": updated, "failed": failed})


@app.delete("/api/admin/users/<int:user_id>")
@require_permission("uzivatele", "smazat")
def admin_users_delete(user_id):
    user = current_user()
    if user["id"] == user_id:
        return jsonify({"error": "Nemůžeš smazat sám sebe."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM app_users WHERE id=%s", (user_id,))
            existing = cur.fetchone()
            try:
                cur.execute("DELETE FROM app_users WHERE id=%s", (user_id,))
            except pymysql.err.IntegrityError:
                # Robert 2026-08-09 ("nemuzu to smazat"): FK constraint bez
                # ON DELETE SET NULL (viz fleet_trips - opraveno, ale kdyby
                # nekdy pribyla dalsi tabulka se stejnou dirou) drive spadla
                # jako neosetrena vyjimka -> 500 bez uzitecne hlasky.
                conn.rollback()
                return jsonify({"error": "Uživatele nelze smazat - má navázané záznamy (např. jízdy, objednávky). Nejdřív je přeřaď/smaž, nebo požádej o úpravu vazby v DB."}), 409
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "delete", "user", user_id, existing["email"] if existing else None)
    return jsonify({"status": "ok"})
