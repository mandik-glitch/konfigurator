"""
Fronta systemovych (ne-objednavkovych) e-mailu cekajicich na schvaleni
admina - bot13, 2026-08-23.

WORKFLOW.md bod 16 (Robert 2026-08-22: "NELZE aby se emaily odesilali
automaticky pri zmenach stavu (ani jindy), vsechny odchozi emaily musi
schvalit admin") plati bez vyjimky i pro e-maily, ktere nejsou navazane
na objednavku - typicky overovaci e-mail pri registraci (viz
app.py::issue_email_verification, pouzito z auth_register i
remeslo.py::remeslo_register, bezpecnostni review Modulu 11 bod 1,
AGENTS_LOG.md "BEZPECNOSTNI REVIEW verejne registrace Remesla").

Samostatna tabulka system_emails misto pretezovani shop_emails
(api/emails.py) - ta ma order_id NOT NULL s FK na shop_orders, systemovy
e-mail zadnou objednavku nema. Schvalovaci vzor (pending -> admin
schvali/zamitne v adminu -> teprve pak send_email()) je ale STEJNY jako
u shop_emails.approve_pending_email - viz api/emails.py pro puvodni
vzor.
"""
from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit, send_email,
    get_pagination_args, paginated_query, EMAIL_VERIFICATION_TTL_MIN,
)

SYSTEM_EMAIL_KINDS = (
    "email_verification",
    "remeslo_offer_accepted", "remeslo_offer_declined",
    "scene_offer_accepted", "scene_offer_declined", "scene_offer_note",
    "scene_offer_expiry_reminder",
    "storefront_lead",
    "product_markup",
    "qa_report_critical",
)
SYSTEM_EMAIL_KIND_LABELS = {
    "email_verification": "Ověření e-mailu (registrace)",
    "remeslo_offer_accepted": "Řemeslo - zákazník potvrdil nabídku",
    "remeslo_offer_declined": "Řemeslo - zákazník odmítl nabídku",
    "scene_offer_accepted": "Nabídka (scéna) - zákazník potvrdil",
    "scene_offer_declined": "Nabídka (scéna) - zákazník nemá zájem",
    "scene_offer_note": "Nabídka (scéna) - dotaz/poznámka",
    "scene_offer_expiry_reminder": "Nabídka (scéna) - upomínka na vypršení",
    "storefront_lead": "Mini-eshop (auto) - potvrzení poptávky",
    "product_markup": "Zakreslená připomínka na produktu",
    "scene_offer_markup": "Nabídka - zakreslená změna zákazníka",
    "qa_report_critical": "QA report - kritický nález (scripts/qa/run_all.sh)",
}


def _serialize(r):
    return {
        "id": r["id"],
        "user_id": r["user_id"],
        "kind": r["kind"],
        "kind_label": SYSTEM_EMAIL_KIND_LABELS.get(r["kind"], r["kind"]),
        "recipient_email": r["recipient_email"],
        "subject": r["subject"],
        "body_text": r["body_text"],
        "status": r["status"],
        "error_message": r["error_message"],
        "sent_by": r["sent_by"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "sent_at": r["sent_at"].isoformat() if r.get("sent_at") else None,
    }


# Sdili opravneni "emaily_odchozi" se shop_emails (api/emails.py) - jde
# koncepcne o STEJNOU adminovu odpovednost ("schvaluji odchozi e-maily
# z appky"), jen jina zdrojova tabulka - nema smysl vytvaret druhy
# permission klic jen kvuli tomu, odkud radek pochazi.
@app.get("/api/admin/system-emails")
@require_permission("emaily_odchozi", "zobrazit")
def admin_system_emails_list():
    status = request.args.get("status")
    if status and status not in ("pending", "sent", "failed", "rejected"):
        return jsonify({"error": "Neplatný status."}), 400

    where, params = [], []
    if status:
        where.append("status=%s")
        params.append(status)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            rows, total = paginated_query(
                cur, "SELECT * FROM system_emails", where_sql, params,
                " ORDER BY created_at DESC, id DESC", page, page_size,
            )
            cur.execute("SELECT status, COUNT(*) AS n FROM system_emails GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
    finally:
        conn.close()

    resp = {
        "emails": [_serialize(r) for r in rows],
        "status_counts": {k: status_counts.get(k, 0) for k in ("pending", "sent", "failed", "rejected")},
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.put("/api/admin/system-emails/<int:email_id>")
@require_permission("emaily_odchozi", "upravit")
def admin_system_email_review(email_id):
    body = request.get_json(silent=True) or {}
    approved = body.get("approved")
    if approved not in (True, False):
        return jsonify({"error": "Chybí approved (true/false)."}), 400

    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM system_emails WHERE id=%s", (email_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Záznam neexistuje."}), 404
            # Atomicky "claim" radek PRED odeslanim (ne jen SELECT+kontrola v
            # Pythonu - dva soubezne kliky na schvaleni by jinak oba prosly
            # kontrolou a e-mail se odeslal dvakrat, viz stejna oprava v
            # emails.py::approve_pending_email). rowcount 1 = ja jsem prvni.
            cur.execute("UPDATE system_emails SET status='sending' WHERE id=%s AND status='pending'", (email_id,))
            if cur.rowcount != 1:
                return jsonify({"error": "Tenhle e-mail už není ve stavu čeká na schválení (byl už vyřízen)."}), 400

            if approved:
                if row["kind"] == "email_verification" and row["user_id"]:
                    # Namet (bot3/revize kodu, 2026-09-02): overovaci token
                    # ma TTL od VYTVORENI (registrace/resend), ale e-mail
                    # cekal ve fronte na schvaleni - kdyz schvaleni trva
                    # dele nez TTL, je odkaz mrtvy driv, nez ho zakaznik
                    # vubec dostane. Tesne pred odeslanim se proto
                    # nejnovejsimu NEPOUZITEMU tokenu daneho uzivatele
                    # posune expirace o TTL OD TETO CHVILE (kdy e-mail
                    # skutecne odchazi). Bez schema zmeny - parovani jen
                    # pres user_id (system_emails a email_verification_tokens
                    # nemaji explicitni FK mezi sebou).
                    cur.execute(
                        "UPDATE email_verification_tokens SET expires_at = NOW() + INTERVAL %s MINUTE "
                        "WHERE user_id=%s AND used=0 ORDER BY id DESC LIMIT 1",
                        (EMAIL_VERIFICATION_TTL_MIN, row["user_id"]),
                    )
                    if cur.rowcount == 0:
                        app.logger.warning(
                            "admin_system_email_review: schvaluji email_verification pro user_id=%s, "
                            "ale nenasel jsem nepouzity token k obnoveni platnosti", row["user_id"],
                        )
                try:
                    send_email(row["recipient_email"], row["subject"], row["body_text"])
                    new_status, err = "sent", None
                except Exception as e:
                    new_status, err = "failed", str(e)
            else:
                new_status, err = "rejected", None

            # sent_at = okamzik PO send_email (skutecne odeslani); created_at je zarazeni do fronty. U zamitnuteho / neuspesneho zustava NULL.
            cur.execute(
                "UPDATE system_emails SET status=%s, error_message=%s, sent_by=%s, sent_by_user_id=%s, "
                "sent_at=IF(%s='sent', NOW(), NULL) WHERE id=%s",
                (new_status, err, admin["name"] if admin else None, admin["id"] if admin else None, new_status, email_id),
            )
        conn.commit()
    finally:
        conn.close()

    log_audit(admin["id"], "update", "system_email", email_id,
               f"{'Schváleno' if approved else 'Zamítnuto'}: {row['subject']} ({row['recipient_email']}).")
    return jsonify({"status": "ok", "email_status": new_status, "error_message": err})
