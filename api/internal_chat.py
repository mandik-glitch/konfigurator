"""Interni tymovy chat na Dashboardu (Robert 2026-08-08: "na dashboard
pridej chatovaci okno pro vsechny prihlasene v systemu") - JEDNA
sdilena mistnost pro cely tym (ne soukrome zpravy), viz
sql/2026-08-08_internal_chat.sql.

@staff_required, ne @require_permission na specificky oddil - Dashboard
tab sam o sobe nema TAB_SECTION zaznam a je videt kazde STAFF roli (viz
applyTabPermissions() v admin.html), chat ma stejny rozsah pristupu jako
zbytek Dashboardu. PUVODNE jen @login_required (bezpecnostni nalez,
bot3/revize kodu 2026-09-02: "kazde prihlasene roli" myslelo STAFF, ale
@login_required pousti i role='user' - bezny e-shop zakaznik ze
/api/auth/register sdili STEJNY login mechanismus - a mohl tak cist/psat
do interniho tymoveho chatu).

Vycleneno z api/app.py (bot5, 2026-09-03, PLAN_ROZDELENI_BACKENDU.md
skupina 4) - cisty presun, zadna zmena chovani/URL.
"""
from flask import request, jsonify

from app import app, get_conn, staff_required, current_user

INTERNAL_CHAT_HISTORY_LIMIT = 100


@app.get("/api/admin/internal-chat/messages")
@staff_required
def internal_chat_messages_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Robert 2026-08-08 ("kazda role nech ma svoji barvu textu v
            # chatu at se to hned pozna kdo pise") - role se cte ZIVA z
            # app_users (ne snapshot v okamziku odeslani) - u interniho
            # tymoveho chatu je "kdo to ted je" uzitecnejsi nez historicka
            # presnost, a role se meni vzacne. LEFT JOIN (ne INNER) at
            # zprava zustane viditelna, i kdyz byl mezitim ucet smazan.
            cur.execute(
                "SELECT m.id, m.sender_user_id, m.sender_name, m.body, m.created_at, u.role AS sender_role "
                "FROM internal_chat_messages m LEFT JOIN app_users u ON u.id = m.sender_user_id "
                "ORDER BY m.id DESC LIMIT %s",
                (INTERNAL_CHAT_HISTORY_LIMIT,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    # pymysql DictCursor.fetchall() vraci tuple (ne list) - .reverse() na
    # miste by spadlo s AttributeError, proto list()+reversed() misto in-place.
    rows = list(reversed(rows))  # nejstarsi prvni, at se da vykreslit shora dolu bez dalsiho razeni na klientovi
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
    return jsonify({"messages": rows})


@app.post("/api/admin/internal-chat/messages")
@staff_required
def internal_chat_messages_create():
    body = (request.get_json(silent=True) or {}).get("body", "")
    body = body.strip() if isinstance(body, str) else ""
    if not body:
        return jsonify({"error": "Prázdná zpráva."}), 400
    if len(body) > 4000:
        return jsonify({"error": "Zpráva je příliš dlouhá (max 4000 znaků)."}), 400
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO internal_chat_messages (sender_user_id, sender_name, body) VALUES (%s,%s,%s)",
                (user["id"], user.get("name") or user["email"], body),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"id": new_id}), 201
