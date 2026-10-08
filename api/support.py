"""
Podpora (zivy chat) - bot1, 2026-07-25 (Faze 1 z SUPPORT_SYSTEM_NAVRH.md,
rozsireno pro anonymni navstevniky 2026-07-25 vecer). V UI od 2026-08
zobrazeno jako "Emaily prichozi" (Robert: kod/DB porad rikaji "podpora"/
"support", zmatecne vuci UI nazvu) - RBAC permission sekce prejmenovana
na "emaily_prichozi" (bot10, 2026-08-22), zbytek kodu (nazev souboru,
DB tabulky shop_support_*, JS identifikatory) zustava beze zmeny zamerne
(kosmeticke riziko/prinos nestoji za rozsah zasahu, viz TASKS.md).

Robert: "udelej stejny system jako je zde: https://supportbox.cz/funkce/
... bude potreba jej implementovat jak do dokladu tak do 3D sceny, abych
mohl uzivatelum nejak radit online, at se to vsechno sjednocuje do jednoho
prostredi" -> rozhodnuto (viz SUPPORT_SYSTEM_NAVRH.md): Robert/tym odpovida
jako zivy operator (zadny AI chatbot v teto fazi). "stav to hred".

Pozdeji doplneno: "[ma chat widget fungovat i mimo prihlaseny konfigurator,
napr. na realizace.html] ano" - realizace.html (verejna fotogalerie) NENI
za loginem (na rozdil od scene.html, rozhodnuti 2026-07-23), takze pisici
tam muze byt anonymni navstevnik. Identifikace tedy resena DVEMA zpusoby:
  - prihlaseny uzivatel (app_users, jako v puvodni Fazi 1) -> customer_user_id
  - anonymni navstevnik -> Flask session cookie (funguje i bez loginu,
    FLASK_SECRET_KEY uz je nastaveny v app.py) drzici nahodny
    guest_session_id, ulozeny do shop_support_conversations.guest_session_id
    (sloupec pridan migraci sql/2026-07-25_support_guest.sql, viz DB CHECK
    "customer_user_id IS NOT NULL OR guest_session_id IS NOT NULL").
  Anonymni navstevnik musi pri PRVNI zprave vyplnit e-mail (aby ho slo
  zpetne kontaktovat) - viz support_customer_send() kod "email_required".

Endpointy:
  Zakaznik (bez @login_required - funguje pro prihlasene i anonymni):
    GET  /api/support/conversation       - aktualni/posledni konverzace + zpravy, oznaci jako precteno zakaznikem
    POST /api/support/messages           - {body, source, name?, email?} - posle zpravu (zalozi konverzaci, pokud zadna otevrena neexistuje)
  Admin (admin_required):
    GET  /api/admin/support/conversations              - seznam konverzaci (nejnovejsi nahore)
    GET  /api/admin/support/conversations/<id>/messages - detail vlakna, oznaci jako precteno adminem
    POST /api/admin/support/conversations/<id>/reply    - {body} - odpoved operatora
    POST /api/admin/support/conversations/<id>/close    - uzavre konverzaci

Aktivace: `import support` na konec app.py (za ostatnimi moduly).
"""
import os
import re
import subprocess
import uuid

from flask import request, jsonify, session, Response

from app import (
    app, get_conn, require_permission, has_permission, current_user, log_audit,
    parse_bulk_ids, bulk_update_fields, bulk_delete, get_pagination_args,
    paginated_query, get_setting, _rate_limited, _client_ip,
)
from quotes import content_disposition

import support_ai
import crm
import incoming_documents
import orders

VALID_SOURCES = ("widget_scene", "widget_realizace", "widget_offer")  # widget_offer = chat v online nabidce (bot4, 2026-08-06)

# Robert 2026-08-07 ("jak docílíme aby zprávy s chatu podpory mi chodily
# na mobil" -> zvolil variantu "E-mail", mobil pak upozorni pres beznou
# push notifikaci e-mailove appky): editovatelna adresa v adminu, stejny
# vzor jako FLEET_FUEL_RECEIPT_EMAIL_SETTING_KEY v api/fleet.py (ulozena
# v app_settings, ne natvrdo zadratovana jako FLEET_CONTINUITY_ALERT_EMAIL).
SUPPORT_NOTIFY_EMAIL_SETTING_KEY = "support_notify_email"


def _support_identity():
    """Vrati (customer_user_id, guest_session_id, default_email, default_name)
    pro aktualniho navstevnika. Prihlaseny uzivatel ma prednost; jinak se
    pouzije/zalozi anonymni token ve Flask session (session.permanent=True,
    stejne jako u loginu v app.py, aby vydrzel i po zavreni prohlizece)."""
    user = current_user()
    if user:
        return user["id"], None, user["email"], user.get("name")
    gid = session.get("support_guest_id")
    if not gid:
        gid = uuid.uuid4().hex
        session["support_guest_id"] = gid
        session.permanent = True
    return None, gid, None, None


def _serialize_message(row):
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "sender_type": row["sender_type"],
        "sender_name": row["sender_name"],
        "body": row["body"],
        # body_html - jen u e-mailu s text/html castou (viz
        # api/support_email_sync.py), jinak None - admin.html ho pouzije
        # misto plain textu, pokud je k dispozici (sandboxovany iframe).
        "body_html": row.get("body_html"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_conversation(row):
    return {
        "id": row["id"],
        "customer_user_id": row["customer_user_id"],
        "customer_email": row["customer_email"],
        "customer_name": row["customer_name"],
        # Robert 2026-08-05 ("přidej sloupec předmět zprávy") - jen
        # e-mailove konverzace ho maji (viz support_email_sync.py),
        # chat widget zustane None.
        "email_subject": row["email_subject"],
        "source": row["source"],
        "status": row["status"],
        "archived": bool(row.get("archived")),
        # linked_order_id (Robert 2026-08-22) - viz _link_conversation_to_order,
        # zobrazuje se jako odznak/proklik u konverzace misto drivejsi
        # tiche archivace destinace "objednavka".
        "linked_order_id": row.get("linked_order_id"),
        # linked_lead_id (bot10, 2026-08-23, Robert pres bot3: "poptavka
        # jako stitek opticky uz v emailech") - vyplneno u konverzaci
        # zrcadlenych z crm_leads (viz support_email_sync.py "poptavka"
        # vetev, DUAL-WRITE - lead zustava plnohodnotny zaznam, tohle je
        # jen viditelny stitek+proklik v E-mailech prichozich navic).
        "linked_lead_id": row.get("linked_lead_id"),
        "unread_by_admin": bool(row["unread_by_admin"]),
        "unread_by_customer": bool(row["unread_by_customer"]),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "last_message_at": row["last_message_at"].isoformat() if row["last_message_at"] else None,
    }


# ---------------------------------------------------------------------------
# Zakaznik - chat widget (scene.html i realizace.html)
# ---------------------------------------------------------------------------

@app.get("/api/support/conversation")
def support_customer_conversation():
    user_id, guest_id, _, _ = _support_identity()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # bot10 2026-08-17 (Robert - konverzace #42 mixovala e-mailove
            # vlakno s widget chatem, viz AGENTS_LOG.md): tenhle dotaz drive
            # hledal konverzaci JEN podle customer_user_id, bez ohledu na
            # zdroj - prihlaseny uzivatel s existujici e-mailovou konverzaci
            # (source='email', napr. zalozenou synchronizaci z schranky) tak
            # v chat widgetu uvidel/psal do TE e-mailove konverzace, misto
            # aby si widget zalozil/nasel vlastni. `source IN VALID_SOURCES`
            # e-mailove vlakno vyslovne vyloucuje - widget chat (kteracoli
            # ze 3 stranek, co ho hosti) je jeden spolecny "kanal" oddeleny
            # od e-mailu, presne jak Robert zadal.
            if user_id:
                cur.execute(
                    "SELECT * FROM shop_support_conversations WHERE customer_user_id=%s "
                    "AND source IN %s "
                    "ORDER BY (status='open') DESC, last_message_at DESC LIMIT 1",
                    (user_id, VALID_SOURCES),
                )
            else:
                cur.execute(
                    "SELECT * FROM shop_support_conversations WHERE guest_session_id=%s "
                    "AND source IN %s "
                    "ORDER BY (status='open') DESC, last_message_at DESC LIMIT 1",
                    (guest_id, VALID_SOURCES),
                )
            conv = cur.fetchone()
            messages = []
            if conv:
                cur.execute(
                    "SELECT * FROM shop_support_messages WHERE conversation_id=%s ORDER BY created_at ASC, id ASC",
                    (conv["id"],),
                )
                messages = cur.fetchall()
                if conv["unread_by_customer"]:
                    cur.execute(
                        "UPDATE shop_support_conversations SET unread_by_customer=0 WHERE id=%s",
                        (conv["id"],),
                    )
                    conn.commit()
                    conv["unread_by_customer"] = 0
    finally:
        conn.close()
    return jsonify({
        "conversation": _serialize_conversation(conv) if conv else None,
        "messages": [_serialize_message(m) for m in messages],
        "requires_email": not user_id and not (conv and conv["customer_email"]),
    })


@app.post("/api/support/messages")
def support_customer_send():
    # Bezpecnost (bot11, 2026-08-18, audit AUDIT_SYSTEM_2026-08-18.md
    # nalez 1.5): endpoint bez limitu spoustel synchronne realne
    # Anthropic API volani + vzdy SMTP notifikaci Robertovi - kdokoli
    # bez prihlaseni mohl skriptem generovat neomezene API naklady a
    # zahltit schranku. 8 zprav / minutu na IP - dost pro bezny zivy
    # chat (clovek nedokaze psat rychleji), zastavi skriptovane
    # zahlcovani.
    if _rate_limited(f"support_msg:{_client_ip()}", max_requests=8, window_seconds=60):
        return jsonify({"error": "Příliš mnoho zpráv, zkuste to prosím za chvíli znovu."}), 429
    user_id, guest_id, def_email, def_name = _support_identity()
    body_json = request.get_json(silent=True) or {}
    body = (body_json.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Zpráva je prázdná."}), 400
    source = body_json.get("source") if body_json.get("source") in VALID_SOURCES else "widget_scene"
    guest_email = (body_json.get("email") or "").strip() or None
    guest_name = (body_json.get("name") or "").strip() or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # bot10 2026-08-17 - stejna oprava jako v support_customer_conversation()
            # vyse (viz komentar tam) - "otevrena konverzace pro tohoto
            # uzivatele" nesmi zahrnovat e-mailove vlakno, jinak se widget
            # zprava prilepi na cizi/nesouvisejici e-mailovou konverzaci.
            if user_id:
                cur.execute(
                    "SELECT id, customer_email FROM shop_support_conversations "
                    "WHERE customer_user_id=%s AND status='open' AND source IN %s "
                    "ORDER BY last_message_at DESC LIMIT 1",
                    (user_id, VALID_SOURCES),
                )
            else:
                cur.execute(
                    "SELECT id, customer_email FROM shop_support_conversations "
                    "WHERE guest_session_id=%s AND status='open' AND source IN %s "
                    "ORDER BY last_message_at DESC LIMIT 1",
                    (guest_id, VALID_SOURCES),
                )
            row = cur.fetchone()
            if row:
                conv_id = row["id"]
                if not user_id and (guest_email or guest_name) and not row["customer_email"]:
                    cur.execute(
                        "UPDATE shop_support_conversations SET customer_email=COALESCE(customer_email,%s), "
                        "customer_name=COALESCE(customer_name,%s) WHERE id=%s",
                        (guest_email, guest_name, conv_id),
                    )
            else:
                if not user_id and not guest_email:
                    # Anonymni navstevnik bez existujici konverzace MUSI zadat e-mail
                    # pri prvni zprave (jinak by ho nesel zpetne kontaktovat).
                    return jsonify({"error": "Pro odeslání zprávy vyplňte prosím e-mail.", "code": "email_required"}), 400
                # Chat v online nabidce (bot4, 2026-08-06) posila subject
                # ("Nabídka Logiman00xx") - ulozi se do email_subject, at
                # admin v Podpore hned vidi, ke ktere nabidce vlakno patri.
                subject = (body_json.get("subject") or "").strip()[:255] or None
                cur.execute(
                    "INSERT INTO shop_support_conversations "
                    "(customer_user_id, guest_session_id, customer_email, customer_name, source, email_subject, status, unread_by_admin) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'open',1)",
                    (user_id, guest_id, def_email or guest_email, def_name or guest_name, source, subject),
                )
                conv_id = cur.lastrowid
            sender_label = def_name or guest_name or def_email or guest_email or "Zákazník"
            cur.execute(
                "INSERT INTO shop_support_messages (conversation_id, sender_type, sender_user_id, sender_name, body) "
                "VALUES (%s,'customer',%s,%s,%s)",
                (conv_id, user_id, sender_label, body),
            )
            cur.execute(
                "UPDATE shop_support_conversations SET unread_by_admin=1, last_message_at=NOW() WHERE id=%s",
                (conv_id,),
            )
        conn.commit()
    finally:
        conn.close()

    _maybe_notify_new_message(conv_id, sender_label, body)

    if source == "widget_scene":
        _maybe_generate_ai_reply(conv_id)

    return jsonify({"status": "ok", "conversation_id": conv_id})


def _maybe_notify_new_message(conv_id, sender_label, body):
    """Robert 2026-08-07 ("jak docílíme aby zprávy s chatu podpory mi
    chodily na mobil"): pokud je v app_settings nastavena notifikacni
    adresa (viz SUPPORT_NOTIFY_EMAIL_SETTING_KEY, editovatelna v adminu
    - GET/PUT /api/admin/support/settings nize), posle se tam e-mail s
    obsahem nove zakaznicke zpravy. BEST-EFFORT, stejny vzor jako
    fleet.py continuity/fuel-receipt alerty - selhani se jen zaloguje,
    nikdy nerozbije uz uspesne odeslanou zpravu zakaznika (volano AZ PO
    commitu)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            notify_email = get_setting(cur, SUPPORT_NOTIFY_EMAIL_SETTING_KEY, "")
    finally:
        conn.close()
    if not notify_email:
        return
    # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - primy send_email()
    # obchazel schvalovaci frontu (WORKFLOW.md bod 16, ktery vyslovne
    # nedela vyjimku pro interni adresy).
    try:
        import emails
        preview = body if len(body) <= 500 else body[:500] + "…"
        emails.send_and_log(
            None, template_key="custom", recipient=notify_email,
            subject=f"Emaily příchozí – nová zpráva od {sender_label}",
            # bot10 2026-08-22: hash byl "#podpora", ale data-tab je "support"
            # (restoreTabFromHash() v admin.html hleda presne tenhle atribut) -
            # odkaz tak byl ticha nefunkcni, klik jen otevrel admin.html bez
            # prepnuti na spravnou zalozku. Opraveno na skutecnou hodnotu.
            body=f"Od: {sender_label}\n\n{preview}\n\nOtevřít v administraci: /admin.html#support",
            auto=True,
        )
    except Exception as e:
        print(f"[support._maybe_notify_new_message] zařazení e-mailu do fronty selhalo (konverzace {conv_id}): {e}")


def _maybe_generate_ai_reply(conv_id):
    """Robert 2026-07-26: "implementuj do okna podpory ve 3D scene naseho
    3D bota aby mohl reagovat uzivatelum na dotazy". Rozhodnuto: AUTOMATICKY
    a HNED, jen pro zdroj widget_scene, odpovedi VIDITELNE OZNACENE jako od
    AI (sender_type='ai', sender_name='3Dbot') - viz support_ai.py pro
    znalostni zdroje (zive z DB/VLASTNOSTI_PROFILU.md, zadna rucni kopie).
    Bezi v SAMOSTATNE transakci PO uspesnem ulozeni zakaznikovy zpravy -
    jakekoli selhani (chybejici API klic, vypadek Anthropic API) se jen
    zaloguje a konverzace proste zustane cekat na Roberta, nikdy nerozbije
    already-uspesne odeslani zakaznikovy zpravy (ktere uz probehlo pred
    timto volanim)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT sender_type, body FROM shop_support_messages "
                "WHERE conversation_id=%s ORDER BY created_at ASC, id ASC",
                (conv_id,),
            )
            history = cur.fetchall()
        reply_text = support_ai.generate_ai_reply(history)
        if not reply_text:
            return
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO shop_support_messages (conversation_id, sender_type, sender_user_id, sender_name, body) "
                "VALUES (%s,'ai',NULL,'3Dbot',%s)",
                (conv_id, reply_text),
            )
            cur.execute(
                "UPDATE shop_support_conversations SET unread_by_customer=1, last_message_at=NOW() WHERE id=%s",
                (conv_id,),
            )
        conn.commit()
    except Exception as e:
        print(f"[support._maybe_generate_ai_reply] selhalo (konverzace {conv_id}): {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Admin - operatorska konzole (admin.html, tab "Podpora")
# ---------------------------------------------------------------------------

@app.get("/api/admin/support/settings")
@require_permission("emaily_prichozi", "zobrazit")
def support_settings_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            email = get_setting(cur, SUPPORT_NOTIFY_EMAIL_SETTING_KEY, "")
    finally:
        conn.close()
    return jsonify({"notify_email": email or ""})


@app.put("/api/admin/support/settings")
@require_permission("emaily_prichozi", "upravit")
def support_settings_set():
    body = request.get_json(silent=True) or {}
    if "notify_email" not in body:
        return jsonify({"error": "Chybí notify_email."}), 400
    email = (body.get("notify_email") or "").strip()
    if email and ("@" not in email or not email.isascii()):
        return jsonify({"error": "Zadejte platnou e-mailovou adresu (bez diakritiky)."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SUPPORT_NOTIFY_EMAIL_SETTING_KEY, email, email),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "support_settings", None, f"notify_email={email or '(prazdne)'}")
    return jsonify({"ok": True})


@app.get("/api/admin/support/conversations")
@require_permission("emaily_prichozi", "zobrazit")
def support_admin_list():
    """Robert 2026-07-26: "chybi tlacitko smazat a filtry" -> pak jeste
    "toto neni plnohodnotny filtr system" -> upresneno (AskUserQuestion):
    zdroj, datum (od-do), jen neprectene, razeni (nejstarsi/nejnovejsi).
    Vsechny filtry se kombinuji (AND). status_counts/source_counts se
    pocitaji VZDY z CELE (nefiltrovane) sady, aby zalozky/vyber ukazovaly
    spravne celkove pocty bez ohledu na aktualne aplikovany filtr;
    unread_count (globalni odznak na zalozce) stejne tak."""
    status = request.args.get("status")
    q = (request.args.get("q") or "").strip()
    source = request.args.get("source")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    unread_only = request.args.get("unread_only") == "1"
    sort = "ASC" if request.args.get("sort") == "oldest" else "DESC"
    archived = request.args.get("archived") == "1"

    where, params = [], []
    # Archiv je vlastni zalozka (bot23, 2026-08-17, viz crm_leads.archived
    # pro stejny vzor) - bezne zalozky (Vse/Otevrene/Uzavrene) archivovane
    # konverzace nikdy neukazuji, nezavisle na status.
    where.append("archived=1" if archived else "archived=0")
    if status:
        where.append("status=%s"); params.append(status)
    if source:
        where.append("source=%s"); params.append(source)
    if q:
        where.append("(customer_name LIKE %s OR customer_email LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    if date_from:
        where.append("last_message_at >= %s"); params.append(f"{date_from} 00:00:00")
    if date_to:
        where.append("last_message_at <= %s"); params.append(f"{date_to} 23:59:59")
    if unread_only:
        where.append("unread_by_admin=1")

    # Stránkování (task #78/84)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM shop_support_conversations"
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           f" ORDER BY unread_by_admin DESC, last_message_at {sort}", page, page_size)

            cur.execute("SELECT status, COUNT(*) AS n FROM shop_support_conversations WHERE archived=0 GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT source, COUNT(*) AS n FROM shop_support_conversations WHERE archived=0 GROUP BY source")
            source_counts = {r["source"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM shop_support_conversations WHERE unread_by_admin=1 AND archived=0")
            unread_count = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM shop_support_conversations WHERE archived=1")
            archived_count = cur.fetchone()["n"]
    finally:
        conn.close()
    resp = {
        "conversations": [_serialize_conversation(r) for r in rows],
        "unread_count": unread_count,
        "archived_count": archived_count,
        "status_counts": status_counts,
        "source_counts": source_counts,
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


OUTCOME_LABELS_CZ = {
    "poptavka": "Poptávka",
    "doklad": "Doklad",
    "podpora": "Podpora",
    "objednavka_link": "Objednávka (propojeno)",
    "auto_archived": "Auto-archivováno",
    "ignored": "Ignorováno (pravidlo)",
    "self_copy_skipped": "Přeskočeno (vlastní kopie)",
    "duplicate": "Duplicitní (zahozeno)",
    "no_sender": "Bez odesílatele",
}


@app.get("/api/admin/support/mailbox-log")
@require_permission("emaily_prichozi", "zobrazit")
def support_admin_mailbox_log():
    """
    Robert 2026-08-24 ("chci vidět, co hromadíme v mailboxu u nás") -
    KOMPLETNÍ přehled toho, co support_email_sync.py kdy zpracoval,
    bez ohledu na výsledek (i ignorované/duplicitní/auto-archivované,
    které jinak nezanechají žádnou stopu v žádné z existujících front).
    Zápis viz _log_sync_outcome() v support_email_sync.py.

    ?outcome=poptavka|doklad|podpora|objednavka_link|auto_archived|
             ignored|self_copy_skipped|duplicate|no_sender
    ?q=... - hledání v odesílateli/předmětu
    """
    outcome = request.args.get("outcome")
    q = (request.args.get("q") or "").strip()
    where, params = [], []
    if outcome:
        if outcome not in OUTCOME_LABELS_CZ:
            return jsonify({"error": "Neplatný outcome."}), 400
        where.append("outcome=%s"); params.append(outcome)
    if q:
        where.append("(from_email LIKE %s OR from_name LIKE %s OR subject LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM email_sync_log"
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params,
                                           " ORDER BY processed_at DESC, id DESC", page, page_size)
            cur.execute("SELECT outcome, COUNT(*) AS n FROM email_sync_log GROUP BY outcome")
            outcome_counts = {r["outcome"]: r["n"] for r in cur.fetchall()}
    finally:
        conn.close()
    resp = {
        "entries": [
            {
                "id": r["id"], "imap_uid": r["imap_uid"], "message_id_header": r["message_id_header"],
                "from_email": r["from_email"], "from_name": r["from_name"], "subject": r["subject"],
                "outcome": r["outcome"], "outcome_label": OUTCOME_LABELS_CZ.get(r["outcome"], r["outcome"]),
                "lead_id": r["lead_id"], "conversation_id": r["conversation_id"], "document_id": r["document_id"],
                "note": r["note"],
                "processed_at": r["processed_at"].isoformat() if r["processed_at"] else None,
            } for r in rows
        ],
        "outcome_counts": {k: outcome_counts.get(k, 0) for k in OUTCOME_LABELS_CZ},
        "outcome_labels": OUTCOME_LABELS_CZ,
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.delete("/api/admin/support/conversations/<int:conv_id>")
@require_permission("emaily_prichozi", "smazat")
def support_admin_delete(conv_id):
    """Robert 2026-07-26: "chybi tlacitko smazat". shop_support_messages
    ma ON DELETE CASCADE na conversation_id, takze staci smazat radek
    konverzace - zpravy zmizi automaticky (viz sql/2026-07-25_support.sql)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_support_conversations WHERE id=%s", (conv_id,))
            if not cur.fetchone():
                return jsonify({"error": "Konverzace neexistuje."}), 404
            cur.execute("DELETE FROM shop_support_conversations WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "support_conversation", conv_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/admin/support/conversations/<int:conv_id>/blacklist-sender-domain")
@require_permission("emaily_prichozi", "smazat")
def support_admin_blacklist_sender_domain(conv_id):
    """Robert 2026-08-22 (pres bot3): tlacitko "Blacklistovat domenu" v
    trideni e-mailu - jednim klikem zaradi CELOU domenu odesilatele do
    `crm_classifier_sender_rules` (rule_type='ignore', vzor '@domena' -
    viz crm.match_sender_rule()), takze dalsi e-maily z ni se od te
    chvile VUBEC NEULOZI (support_email_sync.py). Zaroven rovnou smaze
    AKTUALNI konverzaci (stejne jako "spam") A VSECHNY DALSI zatim
    nevytridene (status='open') konverzace ze STEJNE domeny, pokud
    nejake existuji - ne jen tu jednu, na ktere se kliklo (rozhodnuti
    bot10, TASKS.md bod "Trideni e-mailu: tlacitko Blacklistovat
    domenu" rozsah (b) nechaval na rozhodnuti provadejicimu botovi)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, customer_email FROM shop_support_conversations WHERE id=%s", (conv_id,))
            conv = cur.fetchone()
            if not conv:
                return jsonify({"error": "Konverzace neexistuje."}), 404
            email = (conv["customer_email"] or "").strip().lower()
            if "@" not in email:
                return jsonify({"error": "Konverzace nemá e-mail odesílatele, doménu nelze určit."}), 400
            domain = email.rsplit("@", 1)[-1]
            pattern = "@" + domain

            cur.execute(
                "SELECT id FROM crm_classifier_sender_rules WHERE pattern=%s AND rule_type='ignore'",
                (pattern,),
            )
            existing_rule = cur.fetchone()
            if existing_rule:
                rule_id = existing_rule["id"]
            else:
                cur.execute(
                    "INSERT INTO crm_classifier_sender_rules (pattern, rule_type, note, created_by) VALUES (%s,%s,%s,%s)",
                    (pattern, "ignore", f"Blacklistováno z třídění e-mailů (konverzace #{conv_id})", admin["id"]),
                )
                rule_id = cur.lastrowid

            cur.execute(
                "SELECT id FROM shop_support_conversations WHERE status='open' AND customer_email LIKE %s",
                ("%@" + domain,),
            )
            to_delete = sorted({r["id"] for r in cur.fetchall()} | {conv_id})

            fmt = ",".join(["%s"] * len(to_delete))
            cur.execute(f"DELETE FROM shop_support_conversations WHERE id IN ({fmt})", tuple(to_delete))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "crm_classifier_sender_rule", rule_id, pattern)
    for cid in to_delete:
        log_audit(admin["id"], "delete", "support_conversation", cid, f"blacklist domain {domain}")
    return jsonify({"status": "ok", "domain": domain, "rule_id": rule_id, "deleted_conversation_ids": to_delete})


@app.get("/api/admin/support/conversations/<int:conv_id>/messages")
@require_permission("emaily_prichozi", "zobrazit")
def support_admin_messages(conv_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_support_conversations WHERE id=%s", (conv_id,))
            conv = cur.fetchone()
            if not conv:
                return jsonify({"error": "Konverzace neexistuje."}), 404
            cur.execute(
                "SELECT * FROM shop_support_messages WHERE conversation_id=%s ORDER BY created_at ASC, id ASC",
                (conv_id,),
            )
            messages = cur.fetchall()
            if conv["unread_by_admin"]:
                cur.execute(
                    "UPDATE shop_support_conversations SET unread_by_admin=0 WHERE id=%s",
                    (conv_id,),
                )
                conn.commit()
                conv["unread_by_admin"] = 0
    finally:
        conn.close()
    return jsonify({
        "conversation": _serialize_conversation(conv),
        "messages": [_serialize_message(m) for m in messages],
    })


@app.post("/api/admin/support/conversations/<int:conv_id>/reply")
@require_permission("emaily_prichozi", "vytvorit")
def support_admin_reply(conv_id):
    """Faze 2 (bot1, 2026-07-26): odpoved operatora se KROME zapisu do
    vlakna posle i jako skutecny e-mail na customer_email (pokud je znamy -
    coz je u vsech 3 zdroju konverzace: prihlaseny widget, anonymni widget
    (e-mail je povinny), i email-origin konverzace). Sjednocuje chat+email
    presne podle SUPPORT_SYSTEM_NAVRH.md 4.4 - zakaznik dostane odpoved i
    do sve bezne postovni schranky, ne jen do widgetu. Selhani odeslani
    NESMI shodit samotnou odpoved v konzoli (stejny princip jako
    emails.py::send_and_log) - jen se potichu zaloguje."""
    admin = current_user()
    body = (request.get_json(silent=True) or {}).get("body", "").strip()
    if not body:
        return jsonify({"error": "Zpráva je prázdná."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, customer_email, email_subject FROM shop_support_conversations WHERE id=%s", (conv_id,))
            conv = cur.fetchone()
            if not conv:
                return jsonify({"error": "Konverzace neexistuje."}), 404
            cur.execute(
                "INSERT INTO shop_support_messages (conversation_id, sender_type, sender_user_id, sender_name, body) "
                "VALUES (%s,'operator',%s,%s,%s)",
                (conv_id, admin["id"], admin.get("name") or admin["email"], body),
            )
            cur.execute(
                "UPDATE shop_support_conversations SET unread_by_customer=1, last_message_at=NOW(), status='open' WHERE id=%s",
                (conv_id,),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "reply", "support_conversation", conv_id, body[:200])
    # OPRAVA (bot10, 2026-08-26, schvaleno bot3) - primy send_email() bez
    # emails.send_and_log() obchazel schvalovaci frontu (WORKFLOW.md bod
    # 16) - stejna chyba jako crm.py::crm_admin_lead_reply mela pred
    # opravou 2026-08-24 ("odpoved odeslana z poptavky musi skoncit ve
    # schvalovaci fronte e-mailu k odeslani" - VZDY auto=True, i kdyz
    # pise admin). Zrcadleno 1:1.
    if conv.get("customer_email"):
        try:
            import emails
            subject = f"Re: {conv['email_subject']}" if conv.get("email_subject") else "Odpověď z podpory LOGIMAN"
            emails.send_and_log(
                None, template_key="custom", recipient=conv["customer_email"],
                subject=subject, body=body, admin=admin, auto=True,
            )
        except Exception as e:
            print(f"[support_admin_reply] zařazení e-mailu do fronty selhalo (konverzace {conv_id}): {e}")
    return jsonify({"status": "ok"})


@app.post("/api/admin/support/conversations/<int:conv_id>/close")
@require_permission("emaily_prichozi", "upravit")
def support_admin_close(conv_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # bot23 2026-08-18: existenci overit SELECTem, ne cur.rowcount
            # po UPDATE - bez CLIENT_FOUND_ROWS pymysql vraci pocet
            # SKUTECNE zmenenych radku, ne nalezenych (stejna past uz
            # opravena u /archive nize a v api/gallery.py) - opakovane
            # uzavreni uz uzavrene konverzace by rowcount==0 mylne
            # vyhodnotilo jako "neexistuje".
            cur.execute("SELECT id FROM shop_support_conversations WHERE id=%s", (conv_id,))
            if not cur.fetchone():
                return jsonify({"error": "Konverzace neexistuje."}), 404
            cur.execute("UPDATE shop_support_conversations SET status='closed' WHERE id=%s", (conv_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "close", "support_conversation", conv_id, None)
    return jsonify({"status": "ok"})


@app.post("/api/admin/support/conversations/<int:conv_id>/archive")
@require_permission("emaily_prichozi", "upravit")
def support_admin_archive(conv_id):
    """Archivace/obnova jedne konverzace (bot23, 2026-08-17, Robert pres
    bot3: "chybi moznost archivovat" vedle Uzavrit/Otevrit znovu/Smazat).
    Nezavisla na status - stejny vzor jako crm_leads.archived (viz
    sql/2026-08-17_support_conversation_archive.sql)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    archived = 1 if body.get("archived", True) else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # existenci overit SELECTem, ne cur.rowcount po UPDATE - bez
            # CLIENT_FOUND_ROWS pymysql vraci pocet SKUTECNE zmenenych
            # radku (MySQL default), takze opakovane archivovani uz
            # archivovane konverzace by rowcount==0 mylne vyhodnotilo
            # jako "neexistuje" (stejna past, ktere se vyhnout).
            cur.execute("SELECT id FROM shop_support_conversations WHERE id=%s", (conv_id,))
            if not cur.fetchone():
                return jsonify({"error": "Konverzace neexistuje."}), 404
            cur.execute("UPDATE shop_support_conversations SET archived=%s WHERE id=%s", (archived, conv_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "archive" if archived else "unarchive", "support_conversation", conv_id, None)
    return jsonify({"status": "ok"})


# shop_orders.order_number je vzdy presne 8 cislic (overeno zive,
# 2026-08-22). Cislo se hleda AZ PO klicovem slove "objedn..."
# (objednavka/objednavky/objednavku/objednavce...), ne jako holy
# \d{8} kdekoli v textu - jinak by se chytl nahodny 8mistny ICO nebo
# telefon v podpisu (stejne poucen jako _SIGNATURE_ICO_RE/_DIC_RE v
# api/crm.py, ktere z podobneho duvodu take vyzaduji klicove slovo
# tesne pred cislem, ne holy vzor).
_ORDER_NUMBER_RE = re.compile(r"objedn\w*\D{0,20}(\d{8})\b", re.IGNORECASE)


def _link_conversation_to_order(cur, conv_id):
    """Propoji konverzaci na objednavku (Robert, 2026-08-22, u diagramu
    pipeline, potvrzeno durazne: "objednavka se nearchivuje !!! jde do
    objednavek" - puvodni chovani destinace 'objednavka' jen
    archivovalo konverzaci beze stopy, viz TASKS.md pro puvodni
    zduvodneni z 2026-08-19, ktere se ukazalo jako spatny predpoklad).

    Nejdriv zkusi najit cislo objednavky v predmetu/tele e-mailu a
    propojit na EXISTUJICI shop_orders zaznam. Kdyz cislo nenajde nebo
    neodpovida zadne objednavce, ZALOZI NOVOU, holou objednavku (viz
    orders.create_bare_order_from_lead) - Robert 2026-08-22, PREKONAVA
    drivejsi vedome "nedela" u teto vetve ("zalozeni UPLNE NOVE
    objednavky... vyzaduje spolehliva strukturovana data, co e-mail
    nemusi obsahovat"): "kdyz to navrhne jako objednavku tak to musi
    pri schvaleni skoncit v objednavkach!" - hromadeni beze zmeny v
    Emaily prichozi uz neni prijatelne u zadne kategorie (stejny duvod
    jako zmena u kategorie 'podpora' ten samy den).

    Vraci (order_id, created_new) - created_new=True u nove zalozene
    objednavky (zadne polozky, admin je doplni rucne), False u napojeni
    na existujici. Vraci (None, False) jen kdyz konverzace nema ZADNY
    kontaktni e-mail (nelze zalozit shop_orders.customer_email NOT
    NULL) - tenhle jediny pripad zustava beze zmeny v Emaily prichozi,
    zadne tiche mizeni dat."""
    cur.execute(
        "SELECT email_subject, customer_name, customer_email FROM shop_support_conversations WHERE id=%s",
        (conv_id,),
    )
    conv = cur.fetchone()
    if not conv:
        return None, False
    cur.execute(
        "SELECT body FROM shop_support_messages WHERE conversation_id=%s ORDER BY created_at ASC, id ASC",
        (conv_id,),
    )
    combined = (conv.get("email_subject") or "") + "\n" + "\n".join((m["body"] or "") for m in cur.fetchall())
    match = _ORDER_NUMBER_RE.search(combined)
    order_id = None
    if match:
        cur.execute("SELECT id FROM shop_orders WHERE order_number=%s", (match.group(1),))
        existing = cur.fetchone()
        if existing:
            order_id = existing["id"]
    created_new = False
    if order_id is None:
        if not conv.get("customer_email"):
            return None, False
        admin_note = combined.strip()[:20000] or None
        order_id, _order_number = orders.create_bare_order_from_lead(
            cur, conv.get("customer_name"), conv["customer_email"], admin_note
        )
        created_new = True
    cur.execute("UPDATE shop_support_conversations SET linked_order_id=%s WHERE id=%s", (order_id, conv_id))
    return order_id, created_new


def _move_conversation_to_crm(cur, conv_id, lead_id_override=None):
    """Presune konverzaci z podpory do CRM (lead) - sdilena logika pro
    rucni tlacitko "oznacit jako poptavku" (viz endpoint nize) i pro
    automaticke provedeni pri schvaleni triage navrhu s destination=
    'crm' (viz support_triage_proposal_review). Vraci lead_id, nebo
    None pokud konverzace neexistuje. Vyhodi ValueError, pokud
    konverzace nema kontaktni e-mail (nutny pro CRM zaznam) - NETYKA se
    lead_id_override (viz nize), tam email netreba.

    lead_id_override (Robert 2026-08-22, WORKFLOW.md bod 17 - "bot to
    nemusi zvladnout rozeznat", admin musi mit vzdy moznost rucniho
    prepsani): kdyz je zadano, PRESKOCI se automaticke
    crm.find_or_create_lead() (rozpoznani pres Message-ID/predmet/
    e-mail) a zpravy/prilohy se napoji rovnou na TENHLE konkretni,
    uz overeny (existence + aktivni stav) lead. Volajici (support_
    triage_proposal_review) validuje existenci/stav PRED zavolanim -
    tahle funkce uz lead_id_override bere jako duveryhodne.

    Prilohy (shop_support_message_attachments) i message_id_header se
    MUSI prenest PRED DELETE FROM shop_support_conversations nize -
    shop_support_messages/_attachments kaskaduji (ON DELETE CASCADE,
    viz sql/2026-08-19_shop_support_message_attachments.sql), takze DB
    radek prilohy by zmizel s konverzaci, ale fyzicky soubor (stary
    staging, nebo cerstve stazeny primo z IMAPu) by nikdo neuklidil
    (osireleny bez DB reference navzdy). Bez message_id_header by se
    pozdejsi odpoved klienta na takhle presunutou zpravu nenapojila
    skrz skutecne vlakno, jen fallback na shodny predmet (viz
    crm.find_or_create_lead, bot10 2026-08-22, oprava bot3 audit).

    Prilohy jdou PRIMO do Drive slozky poptavky (crm.ensure_lead_drive_folder
    + shared_drive_files), NE do soukromeho LEAD_ATTACHMENTS_DIR/
    crm_lead_message_attachments (bot10 2026-08-22 dopoledne - Robert
    odpoledne upresnil "primo do slozek v Poptavka > nabidka", nahrazuje
    dopoledni mezikrok, viz TASKS.md/AGENTS_LOG.md)."""
    import quotes  # local import - support.py je nacten pred quotes.py (viz app.py), top-level import by byl circular
    import drive  # dtto (DRIVE_FILES_DIR)
    import support_email_sync  # dtto (SUPPORT_ATTACHMENTS_DIR)

    cur.execute("SELECT * FROM shop_support_conversations WHERE id=%s", (conv_id,))
    conv = cur.fetchone()
    if not conv:
        return None
    if not lead_id_override and not conv.get("customer_email"):
        raise ValueError("Konverzace nemá e-mail kontaktu, nelze převést na poptávku.")
    cur.execute(
        "SELECT * FROM shop_support_messages WHERE conversation_id=%s ORDER BY created_at ASC, id ASC",
        (conv_id,),
    )
    messages = cur.fetchall()

    customer_text = "\n".join(m["body"] for m in messages if m["sender_type"] == "customer")
    crm.train_words(cur, conv.get("email_subject"), customer_text, "poptavka")

    if lead_id_override:
        lead_id = lead_id_override
    else:
        lead_id = crm.find_or_create_lead(cur, conv["customer_email"], conv["customer_name"], conv.get("email_subject"))
    for m in messages:
        sender_type = "operator" if m["sender_type"] == "operator" else "contact"
        cur.execute(
            "INSERT INTO crm_lead_messages (lead_id, sender_type, sender_user_id, sender_name, body, "
            "created_at, message_id_header) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (lead_id, sender_type, m["sender_user_id"], m["sender_name"], m["body"], m["created_at"],
             m.get("message_id_header")),
        )
        cur.execute(
            "SELECT * FROM shop_support_message_attachments WHERE message_id=%s",
            (m["id"],),
        )
        attachments = cur.fetchall()
        if attachments:
            folder_id = crm.ensure_lead_drive_folder(cur, lead_id)
        for att in attachments:
            if att["stored_filename"]:
                # Legacy staged soubor (z pred zruseni plosneho stagingu,
                # bot11 2026-08-22) - presun beze zmeny.
                src = os.path.join(support_email_sync.SUPPORT_ATTACHMENTS_DIR, att["stored_filename"])
                dest_stored_filename = att["stored_filename"]
                dest = os.path.join(drive.DRIVE_FILES_DIR, dest_stored_filename)
                try:
                    os.rename(src, dest)
                except OSError as e:
                    print(f"[support] presun prilohy pri prevodu na poptavku selhal ({att['stored_filename']}): {e}")
                    continue
                content_type, size_bytes = att["content_type"], att["size_bytes"]
            else:
                # Novy postup - priloha jeste nikdy nebyla na disku
                # (jen metadata, viz TASKS.md zruseni plosneho
                # stagingu) - prevod na poptavku je trvaly presun do
                # CRM, takze se soubor musi stahnout TED primo z
                # IMAPu, ne az pozdeji.
                fetched = support_email_sync.fetch_attachment_from_imap(m.get("message_id_header"), att["filename"])
                if not fetched:
                    print(f"[support] priloha {att['filename']} uz neni dostupna v IMAPu, prevod na poptavku ji vynecha.")
                    continue
                content_type, data = fetched
                content_type = content_type or att["content_type"]
                dest_stored_filename = quotes.safe_stored_filename(att["filename"])
                with open(os.path.join(drive.DRIVE_FILES_DIR, dest_stored_filename), "wb") as fh:
                    fh.write(data)
                size_bytes = len(data)
            cur.execute(
                "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes) "
                "VALUES (%s,%s,%s,%s,%s)",
                (folder_id, att["filename"], dest_stored_filename, content_type, size_bytes),
            )
    cur.execute("UPDATE crm_leads SET unread_by_admin=1, last_message_at=NOW() WHERE id=%s", (lead_id,))
    cur.execute("DELETE FROM shop_support_conversations WHERE id=%s", (conv_id,))
    return lead_id


@app.post("/api/admin/support/conversations/<int:conv_id>/mark-lead")
@require_permission("emaily_prichozi", "upravit")
def support_admin_mark_lead(conv_id):
    """Opacny smer k crm.py::crm_admin_lead_reject (bot5, 2026-07-31,
    viz crm.py modulovy docstring pro cely kontext uceni klasifikatoru):
    admin oznaci konverzaci z Podpory jako skutecnou poptavku - presune
    ji do CRM (crm_leads/crm_lead_messages) a text se zauci jako
    pozitivni priklad pro crm.classify_incoming_email.

    Volitelne telo {"lead_id": <id>} (Robert 2026-08-22, WORKFLOW.md bod
    17 - obecny princip, ne jen triage review) - napoji na KONKRETNI
    existujici aktivni poptavku misto automatickeho find_or_create_lead."""
    body = request.get_json(silent=True) or {}
    lead_id_override = body.get("lead_id")
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if lead_id_override is not None:
                try:
                    lead_id_override = int(lead_id_override)
                except (TypeError, ValueError):
                    return jsonify({"error": "Neplatné lead_id."}), 400
                cur.execute("SELECT id, status FROM crm_leads WHERE id=%s", (lead_id_override,))
                target_lead = cur.fetchone()
                if not target_lead:
                    return jsonify({"error": "Vybraná poptávka neexistuje."}), 400
                if target_lead["status"] in crm.CRM_CLOSED_STATUSES:
                    return jsonify({"error": "Vybraná poptávka je uzavřená (vyhráno/prohráno) - vyberte aktivní."}), 400
            try:
                lead_id = _move_conversation_to_crm(cur, conv_id, lead_id_override=lead_id_override)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            if lead_id is None:
                return jsonify({"error": "Konverzace neexistuje."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "mark_lead", "support_conversation", conv_id, None)
    return jsonify({"status": "ok", "lead_id": lead_id})


@app.get("/api/admin/orders/<int:order_id>/support-conversations")
@require_permission("emaily_prichozi", "zobrazit")
def support_admin_order_conversations(order_id):
    """Konverzace z Emaily prichozi propojene na tuhle objednavku (Robert
    2026-08-22, viz _link_conversation_to_order) - zobrazuje se v detailu
    objednavky stejnym vzorem jako existujici sekce "Odeslane e-maily"
    (webapp/admin.html, api/emails.py)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, customer_name, customer_email, email_subject, status, unread_by_admin, "
                "created_at, last_message_at FROM shop_support_conversations "
                "WHERE linked_order_id=%s ORDER BY last_message_at DESC",
                (order_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"conversations": [
        {
            "id": r["id"], "customer_name": r["customer_name"], "customer_email": r["customer_email"],
            "email_subject": r["email_subject"], "status": r["status"],
            "unread_by_admin": bool(r["unread_by_admin"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
        }
        for r in rows
    ]})


# V11 (bot3, 2026-07-26, viz NAVRH_HROMADNE_AKCE.md) - hromadne
# uzavreni/znovuotevreni vybranych konverzaci. Stavy jsou jen 'open'/
# 'closed' (sql/2026-07-25_support.sql), uzavreni je holy UPDATE bez
# vedlejsich ucinku (na rozdil od "reply", ktera posila e-mail) -
# bezpecne pouzit bulk_update_fields() primo. Robert 2026-07-26: cely
# soubor prepojen z @admin_required na @require_permission("emaily_prichozi",...)
# - nova sekce v PERMISSION_SECTIONS (viz app.py).
VALID_STATUSES = ("open", "closed")


@app.post("/api/admin/support/conversations/bulk-close")
@require_permission("emaily_prichozi", "upravit")
def support_admin_bulk_close():
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    status = body.get("status", "closed")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Neplatný stav."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "shop_support_conversations", ids, {"status": status})
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_close", "support_conversation", None, f"{updated} konverzací -> {status}")
    return jsonify({"status": "ok", "updated": updated})


@app.post("/api/admin/support/conversations/bulk-archive")
@require_permission("emaily_prichozi", "upravit")
def support_admin_bulk_archive():
    """Hromadna archivace/obnova vybranych konverzaci (bot23, 2026-08-17,
    Robert pres bot3). Nezavisla na status - viz support_admin_archive
    (jednotliva konverzace) a sql/2026-08-17_support_conversation_archive.sql."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    archived = 1 if body.get("archived", True) else 0

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            updated = bulk_update_fields(cur, "shop_support_conversations", ids, {"archived": archived})
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_archive" if archived else "bulk_unarchive", "support_conversation", None,
              f"{updated} konverzací")
    return jsonify({"status": "ok", "updated": updated})


@app.delete("/api/admin/support/conversations/bulk")
@require_permission("emaily_prichozi", "smazat")
def support_admin_bulk_delete():
    """Hromadne smazani VYBRANYCH konverzaci (bot2, 2026-07-29, Robert:
    "přidej do podpory bulk mazání"). Stejny vzor jako support_admin_delete
    (single) - shop_support_messages ma ON DELETE CASCADE na
    conversation_id, takze bulk_delete() na shop_support_conversations
    stejne jako u jednotlive konverzace."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted = bulk_delete(cur, "shop_support_conversations", ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "bulk_delete", "support_conversation", None, f"{deleted} konverzací smazáno")
    return jsonify({"status": "ok", "deleted": deleted})


# ==================== TRIDENI PRICHOZICH E-MAILU (bot3, 2026-08-18) ====================
# Robert: tlacitko "Tridit" zada botovi ukol vytridit otevrene konverzace
# a navrhnout, kam kazda dal patri + co s prilohami - navrh se objevi v
# panelu, admin ho po radcich schvali/zamitne. Stejny princip jako
# email_review_queue/remeslo_photo_analyses - ANTHROPIC_API_KEY neni
# platny, zadne zive automaticke AI volani. POST vytvori "pending" beh,
# skutecne posouzeni dopisuje bot rucne (viz scripts/support_triage_
# submit.py), pak beh prejde na "ready_for_review".

TRIAGE_DESTINATION_LABELS = {
    "crm": "Poptávka (přesunout do CRM)",
    "doklad": "Přijatý doklad (faktura/účtenka)",
    "objednavka": "Objednávka (propojit)",
    "podpora": "Ponechat v Emaily příchozí",
    "spam": "Spam/nesouvisející (navrhuji smazat)",
    "jine": "Nejasné - potřeba ruční posouzení",
}


def _serialize_triage_run(run, proposals):
    return {
        "id": run["id"],
        "status": run["status"],
        "requested_at": run["requested_at"].isoformat() if run.get("requested_at") else None,
        "completed_at": run["completed_at"].isoformat() if run.get("completed_at") else None,
        "proposals": [
            {
                "id": p["id"],
                "conversation_id": p["conversation_id"],
                "customer_name": p.get("customer_name") or p.get("customer_email") or f"#{p['conversation_id']}",
                "customer_email": p.get("customer_email"),
                "email_subject": p.get("email_subject"),
                "proposed_destination": p["proposed_destination"],
                "destination_label": p["destination_label"],
                "reasoning": p.get("reasoning"),
                "attachment_note": p.get("attachment_note"),
                "invoice_attachment_filename": p.get("invoice_attachment_filename"),
                "review_status": p["review_status"],
            }
            for p in proposals
        ],
    }


@app.post("/api/admin/support/triage-runs")
@require_permission("emaily_prichozi", "zobrazit")
def support_triage_run_create():
    """Zalozi novy "beh trideni" - skutecny navrh dopisuje bot rucne
    mimo tenhle request (viz modulovy komentar vyse), tady se jen
    zapise pozadavek se stavem 'pending'."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO support_email_triage_runs (requested_by) VALUES (%s)",
                (admin["id"],),
            )
            run_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "support_email_triage_run", run_id, "Žádost o vytřídění e-mailů")
    return jsonify({"id": run_id, "status": "pending"}), 201


@app.get("/api/admin/support/triage-runs/<int:run_id>")
@require_permission("emaily_prichozi", "zobrazit")
def support_triage_run_get(run_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM support_email_triage_runs WHERE id=%s", (run_id,))
            run = cur.fetchone()
            if not run:
                return jsonify({"error": "Běh třídění nenalezen."}), 404
            cur.execute(
                "SELECT p.*, c.customer_name, c.customer_email, c.email_subject "
                "FROM support_email_triage_proposals p "
                "JOIN shop_support_conversations c ON c.id = p.conversation_id "
                "WHERE p.run_id=%s ORDER BY p.id",
                (run_id,),
            )
            proposals = cur.fetchall()
    finally:
        conn.close()
    return jsonify(_serialize_triage_run(run, proposals))


@app.get("/api/admin/support/triage-runs")
@require_permission("emaily_prichozi", "zobrazit")
def support_triage_runs_list():
    """Nejnovejsi beh (pending nebo ready_for_review) - frontend si po
    otevreni zalozky/refresh muze overit, jestli uz nejaky bezi, misto
    zakladani duplicitniho."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM support_email_triage_runs "
                "WHERE status != 'done' ORDER BY id DESC LIMIT 1"
            )
            run = cur.fetchone()
    finally:
        conn.close()
    return jsonify({"run": run})


def run_triage_auto_check_cli():
    """Periodicka automaticka kontrola "netridenych" konverzaci (Robert,
    2026-08-22, pres bot3 - navazuje na zaseknuty beh id=6, ktery nikdo
    rucne nedopsal): spousti konfigurator-triage-auto-check.timer kazdych
    30 minut. Pouziti: python3 app.py triage-auto-check

    NEZAKLADA navrhy sama (zadne zive AI volani, viz modulovy komentar
    vyse u support_triage_run_create) - jen ZAKLADA prazdny beh (stejne
    jako tlacitko "Tridit"), kdyz je "netridenych" konverzaci dost a
    zadny jiny beh prave nečeka na dokonceni. Skutecny navrh pak porad
    dopisuje bot rucne (scripts/2026-08-18_support_triage_submit.py),
    stejne jako po rucnim kliknuti na "Tridit".

    "Netridena" konverzace = otevrena (status='open', archived=0) A
    NEMA zadny 'pending' navrh z jakehokoli behu. Konverzace s pending
    navrhem uz na rozhodnuti CEKA (nezalezi, ve kterem behu) - nepocitat
    ji znovu by vedlo k opakovanemu navrhovani tehoz. Konverzace s
    approved/rejected/deferred navrhem (rozhodnuti uz padlo, i kdyz
    konverzace zustala otevrena - napr. rejected/deferred, nebo doklad
    uz byl vytazen) se POCITA znovu - potrebuje novy navrh v pristim
    behu (presne to se stalo mezi behem 5 a 6, viz AGENTS_LOG.md)."""
    TRIAGE_AUTO_THRESHOLD = 6
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status FROM support_email_triage_runs "
                "WHERE status != 'done' ORDER BY id DESC LIMIT 1"
            )
            existing = cur.fetchone()
            if existing:
                print(f"[triage-auto-check] beh id={existing['id']} (status={existing['status']}) "
                      f"jeste ceka na dokonceni - novy beh se nezaklada.")
                return
            cur.execute(
                "SELECT COUNT(*) AS n FROM shop_support_conversations c "
                "WHERE c.status='open' AND c.archived=0 "
                "AND NOT EXISTS (SELECT 1 FROM support_email_triage_proposals p "
                "WHERE p.conversation_id=c.id AND p.review_status='pending')"
            )
            untriaged = cur.fetchone()["n"]
            print(f"[triage-auto-check] {untriaged} netridenych konverzaci "
                  f"(prah pro zalozeni behu: {TRIAGE_AUTO_THRESHOLD}).")
            if untriaged < TRIAGE_AUTO_THRESHOLD:
                return
            cur.execute("INSERT INTO support_email_triage_runs (requested_by) VALUES (NULL)")
            run_id = cur.lastrowid
        conn.commit()
        print(f"[triage-auto-check] zalozen novy beh id={run_id} (automaticky, requested_by=NULL).")
    finally:
        conn.close()


def _systemd_last_run(unit):
    """Cas posledniho skutecneho spusteni sluzby (ne jen kdy mel timer
    spustit, ale kdy proces opravdu bezel) - `systemctl show` je jen
    dotaz (funguje i pod www-data, neni potreba sudo), zadna zmena
    stavu. Pouzito pro zivy diagram pipeline (bot9, 2026-08-22) - vlastni
    log tabulka pro sync/auto-check neexistuje, systemd uz presne tohle
    hlida sam."""
    try:
        proc = subprocess.run(
            ["systemctl", "show", unit, "-p", "ExecMainStartTimestamp", "--value"],
            capture_output=True, timeout=5, text=True,
        )
        raw = (proc.stdout or "").strip()
        if not raw:
            return None
        from datetime import datetime as _dt
        return _dt.strptime(raw, "%a %Y-%m-%d %H:%M:%S %Z").isoformat()
    except Exception:
        return None


@app.get("/api/admin/pipeline/overview")
@require_permission("emaily_prichozi", "zobrazit")
def admin_pipeline_overview():
    """Zivy prehled e-mailove pipeline pro novou zalozku "Pipeline"
    (Robert pres bot3, 2026-08-22: "postavime pipeline jako plnohodnotny
    prvek administrace... chci zviditelnit v adminu ten, co aktualne
    jedeme" - VYSLOVNE jen READ-ONLY cisla + prokliky, ZADNA konfigurace
    prahu/intervalu, ZADNY audit historie jednotlive konverzace/
    objednavky - obojí explicitne NEVYBRAL). Frontend z techto cisel
    kresli SVG diagram (boxy+sipky), ne dlazdice - viz webapp/admin.html
    renderPipelineDiagram().

    Sekce mimo "emaily_prichozi" (odchozi/prijate_doklady) se vraci jen
    pokud na ne ma prihlaseny uzivatel pravo 'zobrazit' - jinak null, at
    frontend dane uzly diagramu jen ztlumi/skryje cisla, bez uniku dat
    mimo pridelenou roli."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM shop_support_conversations c "
                "WHERE c.status='open' AND c.archived=0 "
                "AND NOT EXISTS (SELECT 1 FROM support_email_triage_proposals p "
                "WHERE p.conversation_id=c.id AND p.review_status='pending')"
            )
            untriaged = cur.fetchone()["n"]

            cur.execute(
                "SELECT id, status FROM support_email_triage_runs "
                "WHERE status != 'done' ORDER BY id DESC LIMIT 1"
            )
            active_run = cur.fetchone()

            cur.execute(
                "SELECT proposed_destination, COUNT(*) AS n FROM support_email_triage_proposals "
                "WHERE review_status='pending' GROUP BY proposed_destination"
            )
            pending_by_cat = {r["proposed_destination"]: r["n"] for r in cur.fetchall()}

            cur.execute("SELECT COUNT(*) AS n FROM crm_leads WHERE unread_by_admin=1")
            leads_unread = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM shop_support_conversations "
                "WHERE linked_order_id IS NOT NULL AND DATE(last_message_at)=CURDATE()"
            )
            objednavky_today = cur.fetchone()["n"]

            outgoing_pending = None
            if has_permission(user, "emaily_odchozi", "zobrazit"):
                cur.execute("SELECT COUNT(*) AS n FROM shop_emails WHERE status='pending'")
                outgoing_pending = cur.fetchone()["n"]

            docs_pending = None
            if has_permission(user, "prijate_doklady", "zobrazit"):
                cur.execute(
                    "SELECT COUNT(*) AS n FROM incoming_documents WHERE approval_status='ceka_schvaleni'"
                )
                docs_pending = cur.fetchone()["n"]

            # Platby (bot18, 2026-09-04, TASKS.md "Pipeline diagram: doplnit
            # dlaždici Platby" - vynecháno vědomě dokud nebylo hotové bankovní
            # párování bot10, ted uz je). Stejny gate-podle-opravneni vzor
            # jako outgoing/docs vyse.
            payments_matched_recent = None
            payments_unmatched_pending = None
            if has_permission(user, "bankovni_vypisy", "zobrazit"):
                cur.execute(
                    "SELECT COUNT(*) AS n FROM shop_orders WHERE bank_paid=1 "
                    "AND bank_paid_at >= (NOW() - INTERVAL 30 DAY)"
                )
                payments_matched_recent = cur.fetchone()["n"]
                # Nespárované = přijaté transakce za 30 dní, jejichž VS
                # nesedí na ŽÁDNÝ z obou platných zdrojů VS (viz
                # api/bank_statements.py::_order_vs_candidates - zálohová
                # faktura MÁ PŘEDNOST, order_number je fallback pro
                # historické/importované objednávky). COLLATE nutné -
                # bank_transactions.variable_symbol je utf8mb4_unicode_ci,
                # shop_documents/shop_orders utf8mb4_0900_ai_ci (zjištěno
                # živě, ne v _iter_order_payment_matches - ten porovnává
                # přes vázaný parametr per objednávka, ne SQL JOIN mezi
                # tabulkami, takže kolizi kolace nikdy nepotká).
                cur.execute(
                    "SELECT COUNT(*) AS n FROM bank_transactions bt "
                    "WHERE bt.direction='prijem' AND bt.transaction_date >= (CURDATE() - INTERVAL 30 DAY) "
                    "AND bt.variable_symbol NOT IN ("
                    "  SELECT variable_symbol COLLATE utf8mb4_unicode_ci FROM shop_documents "
                    "  WHERE document_type='proforma_invoice' AND variable_symbol IS NOT NULL AND variable_symbol != '' "
                    "  UNION "
                    "  SELECT order_number COLLATE utf8mb4_unicode_ci FROM shop_orders "
                    "  WHERE order_number IS NOT NULL AND order_number != ''"
                    ")"
                )
                payments_unmatched_pending = cur.fetchone()["n"]
    finally:
        conn.close()

    return jsonify({
        "sync": {
            "last_sync_at": _systemd_last_run("konfigurator-support-email-sync.service"),
            "last_auto_check_at": _systemd_last_run("konfigurator-triage-auto-check.service"),
        },
        "incoming": {
            "untriaged": untriaged,
            "leads_unread": leads_unread,
            "objednavky_linked_today": objednavky_today,
        },
        "triage": {
            "active_run": active_run,
            "pending_by_category": {
                k: pending_by_cat.get(k, 0) for k in
                ("crm", "doklad", "objednavka", "spam", "podpora", "jine")
            },
            "pending_total": sum(pending_by_cat.values()),
        },
        "outgoing": {"pending_approval": outgoing_pending},
        "documents": {"pending_second_approval": docs_pending},
        "payments": {
            "matched_recent": payments_matched_recent,
            "unmatched_pending": payments_unmatched_pending,
        },
    })


def _triage_proposal_attachments(cur, conversation_id):
    """Vsechny prilohy VSECH zprav dane konverzace (napric celym
    vlaknem, ne jen posledni zpravou) - admin musi videt VSECHNY
    kandidaty, ne jen ten, co bot navrhl (Robert, 2026-08-19: "Robert
    vizualne sam pozna, jestli je priloha skutecne faktura - appka/bot
    to spolehlive nepozna")."""
    cur.execute(
        "SELECT a.id, a.filename, a.content_type, a.size_bytes, a.message_id "
        "FROM shop_support_message_attachments a "
        "JOIN shop_support_messages m ON m.id = a.message_id "
        "WHERE m.conversation_id=%s ORDER BY m.created_at, a.id",
        (conversation_id,),
    )
    return cur.fetchall()


@app.get("/api/admin/support/triage-proposals/<int:proposal_id>/attachments")
@require_permission("emaily_prichozi", "zobrazit")
def support_triage_proposal_attachments_list(proposal_id):
    """Seznam vsech priloh konverzace k danemu navrhu - podklad pro
    admin UI vyber/nahled PRED schvalenim 'doklad' navrhu (zadne
    automaticke rozhodnuti, jen navrh k posouzeni)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT conversation_id FROM support_email_triage_proposals WHERE id=%s", (proposal_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Návrh nenalezen."}), 404
            attachments = _triage_proposal_attachments(cur, row["conversation_id"])
    finally:
        conn.close()
    return jsonify({"attachments": [
        {"id": a["id"], "filename": a["filename"], "content_type": a["content_type"], "size_bytes": a["size_bytes"]}
        for a in attachments
    ]})


def _support_attachment_response(data, filename):
    """Priloha z prichoziho e-mailu je NEDUVERYHODNY zdroj - content_type
    z hlavicky e-mailu si odesilatel urci sam (napr. text/html priloha
    servirovana inline = skript na originu adminu, stored/reflected XSS).
    Stejna logika jako drive.py::drive_admin_files_preview - inline jen
    kdyz OBSAH souboru sam (magic bytes, ne deklarovany content_type)
    odpovida znamemu obrazku nebo PDF, jinak vzdy attachment + nosniff."""
    if data.startswith(b"\xff\xd8\xff"):
        mimetype = "image/jpeg"
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        mimetype = "image/png"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mimetype = "image/gif"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mimetype = "image/webp"
    elif data.startswith(b"%PDF-"):
        mimetype = "application/pdf"
    else:
        mimetype = None
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c != '"' else "_" for c in (filename or "")) or "priloha"
    if mimetype:
        return Response(data, mimetype=mimetype, headers={
            "Content-Disposition": f'inline; filename="{safe_ascii}"',
            "X-Content-Type-Options": "nosniff",
        })
    return Response(data, mimetype="application/octet-stream", headers={
        "Content-Disposition": content_disposition(filename or "priloha"),
        "X-Content-Type-Options": "nosniff",
    })


@app.get("/api/admin/support/triage-proposals/<int:proposal_id>/attachment-preview/<path:filename>")
@require_permission("emaily_prichozi", "zobrazit")
def support_triage_proposal_attachment_preview(proposal_id, filename):
    """Nahled/stazeni JEDNE prilohy PRED schvalenim (obrazek/PDF primo v
    prohlizeci u radku navrhu). `filename` se overuje proti realne
    existujici priloze KONKRETNI konverzace (ne libovolny nazev
    souboru) - stejna bezpecnostni logika jako incoming_documents_download.

    ZMENENO 2026-08-22 (bot11, zruseni plosneho stagingu, viz TASKS.md):
    puvodne se vzdy cetlo ze support_email_sync.SUPPORT_ATTACHMENTS_DIR
    (staging). Nove prilohy uz na disku nejsou (jen metadata,
    stored_filename NULL) - kdyz chybi, stahne se az ted, na vyzadani,
    primo z IMAPu podle Message-ID puvodni zpravy
    (fetch_attachment_from_imap). Stary staged soubor (stored_filename
    vyplnene, z pred tehle zmeny) se cte z disku beze zmeny."""
    import support_email_sync
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT conversation_id FROM support_email_triage_proposals WHERE id=%s", (proposal_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Návrh nenalezen."}), 404
            cur.execute(
                "SELECT a.stored_filename, a.content_type, a.filename AS orig_filename, m.message_id_header "
                "FROM shop_support_message_attachments a "
                "JOIN shop_support_messages m ON m.id = a.message_id "
                "WHERE m.conversation_id=%s AND a.filename=%s ORDER BY a.id DESC LIMIT 1",
                (row["conversation_id"], filename),
            )
            att = cur.fetchone()
    finally:
        conn.close()
    if not att:
        return jsonify({"error": "Příloha nenalezena."}), 404
    if att["stored_filename"]:
        path = os.path.join(support_email_sync.SUPPORT_ATTACHMENTS_DIR, att["stored_filename"])
        if not os.path.isfile(path):
            return jsonify({"error": "Soubor přílohy chybí na disku."}), 404
        with open(path, "rb") as f:
            data = f.read()
        return _support_attachment_response(data, att["orig_filename"] or filename)
    fetched = support_email_sync.fetch_attachment_from_imap(att["message_id_header"], filename)
    if not fetched:
        return jsonify({"error": "Příloha už není dostupná (e-mail v IMAPu nenalezen)."}), 404
    _content_type, data = fetched
    return _support_attachment_response(data, att["orig_filename"] or filename)


def _import_triage_invoice(cur, conversation_id, invoice_attachment_filename):
    """Schvaleni 'doklad' navrhu (bot11, 2026-08-19) - PRESUNE (ne
    zkopiruje) OZNACENOU prilohu do incoming_documents fronty
    (approval_status='ceka_schvaleni' - DALSI samostatne schvaleni tam
    teprve posune soubor do Sdileneho disku). Bez oznacene prilohy se
    zapise jen text posledni zpravy (zadny soubor).

    ZMENENO 2026-08-22 (bot11, zruseni plosneho stagingu, viz TASKS.md):
    puvodne se soubor vzdy presouval ze stagingu (support_email_sync.
    SUPPORT_ATTACHMENTS_DIR). Nove prilohy uz staged nejsou
    (stored_filename NULL) - misto presunu se soubor prave TED stahne
    primo z IMAPu (fetch_attachment_from_imap), presne v okamziku
    schvaleni 'doklad' (jak zadal Robert - "skutečný soubor stáhnout
    AŽ při schvalování kategorie doklad"). Stary staged soubor
    (stored_filename vyplnene, z pred tehle zmeny) se presouva beze
    zmeny."""
    import support_email_sync

    cur.execute(
        "SELECT customer_email, customer_name, email_subject FROM shop_support_conversations WHERE id=%s",
        (conversation_id,),
    )
    conv = cur.fetchone()
    cur.execute(
        "SELECT id, body, created_at FROM shop_support_messages WHERE conversation_id=%s "
        "ORDER BY created_at DESC LIMIT 1",
        (conversation_id,),
    )
    last_msg = cur.fetchone()
    received_at = last_msg["created_at"] if last_msg else None

    if not invoice_attachment_filename:
        incoming_documents.save_incoming_document(
            cur, conv["customer_email"], conv["customer_name"], conv["email_subject"],
            (last_msg["body"] if last_msg else "") or "", received_at, [],
        )
        return "doklad_imported_no_file"

    cur.execute(
        "SELECT a.id, a.stored_filename, a.content_type, a.filename, m.message_id_header "
        "FROM shop_support_message_attachments a "
        "JOIN shop_support_messages m ON m.id = a.message_id "
        "WHERE m.conversation_id=%s AND a.filename=%s ORDER BY a.id DESC LIMIT 1",
        (conversation_id, invoice_attachment_filename),
    )
    att = cur.fetchone()
    if not att:
        # Oznaceny soubor uz neexistuje (napr. smazan/prejmenovan) -
        # nezpusobi chybu celeho schvaleni, zapise se aspon text.
        incoming_documents.save_incoming_document(
            cur, conv["customer_email"], conv["customer_name"], conv["email_subject"],
            (last_msg["body"] if last_msg else "") or "", received_at, [],
        )
        return "doklad_imported_attachment_missing"

    staged_path = None
    if att["stored_filename"]:
        # Legacy staged soubor (z pred zruseni plosneho stagingu) - beze zmeny.
        staged_path = os.path.join(support_email_sync.SUPPORT_ATTACHMENTS_DIR, att["stored_filename"])
        if not os.path.isfile(staged_path):
            incoming_documents.save_incoming_document(
                cur, conv["customer_email"], conv["customer_name"], conv["email_subject"],
                (last_msg["body"] if last_msg else "") or "", received_at, [],
            )
            return "doklad_imported_attachment_missing"
        with open(staged_path, "rb") as f:
            data = f.read()
        content_type = att["content_type"]
    else:
        # Novy postup - soubor jeste nikdy nebyl na disku, stahne se
        # az ted primo z IMAPu.
        fetched = support_email_sync.fetch_attachment_from_imap(att["message_id_header"], att["filename"])
        if not fetched:
            incoming_documents.save_incoming_document(
                cur, conv["customer_email"], conv["customer_name"], conv["email_subject"],
                (last_msg["body"] if last_msg else "") or "", received_at, [],
            )
            return "doklad_imported_attachment_missing"
        content_type, data = fetched
        content_type = content_type or att["content_type"]

    incoming_documents.save_incoming_document(
        cur, conv["customer_email"], conv["customer_name"], conv["email_subject"],
        (last_msg["body"] if last_msg else "") or "", received_at,
        [(att["filename"], content_type, data)],
    )
    # PRESUN, ne kopie - u legacy staged souboru mizi i fyzicky soubor
    # (soubor ted "vlastni" vyhradne incoming_documents, na disku nesmi
    # zustat druha kopie oznacena jako doklad mimo schvalovaci frontu) -
    # u noveho postupu zadny fyzicky staged soubor neexistoval, jen DB radek.
    if staged_path:
        os.remove(staged_path)
    cur.execute("DELETE FROM shop_support_message_attachments WHERE id=%s", (att["id"],))
    return "doklad_imported"


@app.put("/api/admin/support/triage-proposals/<int:proposal_id>")
@require_permission("emaily_prichozi", "upravit")
def support_triage_proposal_review(proposal_id):
    """Schvaleni/zamitnuti JEDNOHO navrhu. Zamitnuti jen zaznamena
    rozhodnuti (auditni stopa) - konverzace zustava beze zmeny, admin
    ji posoudi rucne. Schvaleni navic ROVNOU PROVEDE navrhovanou akci
    (Robert 2026-08-18: schvaleny navrh "spam" zustaval viditelny v
    Emaily prichozi - ocekaval, ze schvaleni uz samo neco udela, ne jen
    zapise rozhodnuti):
    - 'spam'       -> smaze konverzaci (shodne s DELETE /conversations/<id>)
    - 'crm'        -> presune do CRM (shodne s /mark-lead, viz _move_conversation_to_crm).
      Kdyz telo obsahuje `lead_id`, PRESKOCI automaticke rozpoznani
      (find_or_create_lead pres Message-ID/predmet/e-mail) a napoji
      konverzaci na TENHLE konkretni, adminem rucne vybrany lead
      (Robert 2026-08-22, WORKFLOW.md bod 17: "bot to nemusi zvladnout
      rozeznat" - admin musi mit vzdy moznost rucniho prepsani).
    - 'podpora'    -> PREPNE konverzaci na status='closed' (Robert
      2026-08-22: "nemůže existovat skupina, která bude hromadit
      e-maily" - schvaleni uz neni "bez akce", ale rovnou uzavreni,
      admin pripadnou odpoved musi napsat PRED schvalenim)
    - 'objednavka' -> NEARCHIVUJE (Robert 2026-08-22: "objednavka se
      nearchivuje !!! jde do objednavek" - zmena oproti puvodnimu
      chovani z 2026-08-19, viz TASKS.md pro puvodni/nyni prekonane
      zduvodneni). Pokusi se z predmetu/tela e-mailu vytahnout cislo
      objednavky a PROPOJIT konverzaci na odpovidajici shop_orders
      zaznam (_link_conversation_to_order). Kdyz se cislo nenajde nebo
      neodpovida zadne objednavce, ZALOZI NOVOU holou objednavku (Robert
      2026-08-22, PREKONAVA jeste ten samy den puvodni "nedela": "kdyz
      to navrhne jako objednavku tak to musi pri schvaleni skoncit v
      objednavkach!") - bez polozek (nespolehlivy parsing), admin je
      doplni rucne. Konverzace BEZE ZMENY v Emaily prichozi zustava uz
      jen kdyz nema ZADNY kontaktni e-mail (nelze zalozit objednavku
      bez povinneho customer_email) - zadne tiche mizeni dat.
    - 'doklad'     -> pokud bot pri psani navrhu oznacil
      invoice_attachment_filename, PRESUNE (ne zkopiruje) tenhle jeden
      soubor ze stagingu (support_email_sync.SUPPORT_ATTACHMENTS_DIR) do
      incoming_documents fronty (api/incoming_documents.py,
      approval_status='ceka_schvaleni' - DALSI, samostatne schvaleni tam
      teprve posune soubor do Sdileneho disku). Bez oznacene prilohy se
      zapise jen text e-mailu (zadny soubor) - stejne jako incoming_
      documents.save_incoming_document() dela pro attachments=[].
    - 'jine' -> zadna automatizovana cilova akce (zatim) neexistuje,
      zustava jen jako informace pro rucni posouzeni admina"""
    body = request.get_json(silent=True) or {}
    approved = body.get("approved")
    if approved not in (True, False):
        return jsonify({"error": "Chybí approved (true/false)."}), 400
    # Botuv navrh invoice_attachment_filename je jen PREDVYPLNENI, ne
    # automaticke rozhodnuti (Robert, 2026-08-19: "Robert vizualne sam
    # pozna, jestli je priloha skutecne faktura") - admin muze pri
    # schvaleni vybrat JINOU prilohu (nebo zadnou), nez bot navrhl.
    # Rozliseni "klic vubec neposlan" (fallback na botuv navrh z DB) vs.
    # "admin explicitne poslal null = zadna priloha" - proto `in body`,
    # ne jen `.get(...) is not None`.
    has_attachment_override = "invoice_attachment_filename" in body
    attachment_override = body.get("invoice_attachment_filename")
    # lead_id (Robert 2026-08-22, WORKFLOW.md bod 17) - rucni prepsani
    # automatickeho rozpoznani u destinace 'crm', viz docstring vyse a
    # _move_conversation_to_crm.
    lead_id_override = body.get("lead_id")
    if lead_id_override is not None:
        try:
            lead_id_override = int(lead_id_override)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatné lead_id."}), 400
    admin = current_user()
    conn = get_conn()
    action_taken = None
    spam_stored_filenames = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id, conversation_id, proposed_destination, invoice_attachment_filename "
                "FROM support_email_triage_proposals WHERE id=%s",
                (proposal_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Návrh nenalezen."}), 404
            # lead_id validace PRED jakymkoli zapisem (Robert 2026-08-22,
            # WORKFLOW.md bod 17) - spatny/uzavreny vyber se vrati jako
            # 400 hned, nic se mezitim nezapsalo (zadny rollback treba,
            # UPDATE review_status nize se u chybneho lead_id vubec
            # neprovede).
            if approved and lead_id_override is not None and row["proposed_destination"] == "crm":
                cur.execute("SELECT id, status FROM crm_leads WHERE id=%s", (lead_id_override,))
                target_lead = cur.fetchone()
                if not target_lead:
                    return jsonify({"error": "Vybraná poptávka neexistuje."}), 400
                if target_lead["status"] in crm.CRM_CLOSED_STATUSES:
                    return jsonify({"error": "Vybraná poptávka je uzavřená (vyhráno/prohráno) - vyberte aktivní."}), 400
            cur.execute(
                "UPDATE support_email_triage_proposals SET review_status=%s, reviewed_by=%s, reviewed_at=NOW() "
                "WHERE id=%s",
                ("approved" if approved else "rejected", admin["id"], proposal_id),
            )
            if approved:
                dest = row["proposed_destination"]
                conv_id = row["conversation_id"]
                if dest == "spam":
                    # Robert 2026-08-22 ("soubory spamů musíme deletovat
                    # hned"): DELETE nize kaskaduje na shop_support_messages/
                    # shop_support_message_attachments (DB radky), ale
                    # fyzicky soubor ve stagingu (SUPPORT_ATTACHMENTS_DIR)
                    # kaskada nesmaze - musi se uklidit rucne, PRED delete
                    # (po nem uz nejde dohledat, ktere soubory patrily
                    # k teto konverzaci). Filtr `stored_filename IS NOT
                    # NULL` (bot11, 2026-08-22, zruseni plosneho stagingu) -
                    # nove prilohy uz zadny fyzicky soubor nemaji (jen
                    # metadata), bez filtru by nasledny os.path.join s
                    # None spadl na TypeError misto tichého skipu.
                    cur.execute(
                        "SELECT a.stored_filename FROM shop_support_message_attachments a "
                        "JOIN shop_support_messages m ON m.id = a.message_id "
                        "WHERE m.conversation_id=%s AND a.stored_filename IS NOT NULL",
                        (conv_id,),
                    )
                    spam_stored_filenames = [r["stored_filename"] for r in cur.fetchall()]
                    cur.execute("DELETE FROM shop_support_conversations WHERE id=%s", (conv_id,))
                    action_taken = "deleted"
                elif dest == "crm":
                    try:
                        lead_id = _move_conversation_to_crm(cur, conv_id, lead_id_override=lead_id_override)
                        action_taken = "moved_to_crm" if lead_id is not None else None
                    except ValueError:
                        # Chybi kontaktni e-mail - nelze presunout automaticky,
                        # konverzace zustava v Podpore k rucnimu posouzeni.
                        # (lead_id_override se validuje driv, viz vyse -
                        # sem uz by se s neplatnym lead_id nemelo dostat.)
                        action_taken = "crm_move_skipped_no_email"
                elif dest == "objednavka":
                    order_id, created_new_order = _link_conversation_to_order(cur, conv_id)
                    if order_id and created_new_order:
                        action_taken = f"created_order_{order_id}"
                    elif order_id:
                        action_taken = f"linked_to_order_{order_id}"
                    else:
                        action_taken = "order_not_found_left_open"
                elif dest == "doklad":
                    chosen_filename = attachment_override if has_attachment_override \
                        else row.get("invoice_attachment_filename")
                    action_taken = _import_triage_invoice(cur, conv_id, chosen_filename)
                elif dest == "podpora":
                    # Robert 2026-08-22 ("Ponechat v Emaily příchozí...
                    # co je to za výmysl?" -> "nemůže existovat skupina,
                    # která bude hromadit e-maily") - schvaleni uz NENI
                    # "bez akce": konverzace se uzavre (status='closed',
                    # stejny sloupec/hodnota jako rucni tlacitko Uzavrit
                    # v Emaily prichozi, viz support_admin_close vyse) -
                    # zmizi z fronty k trideni i z pohledu "otevrene",
                    # zustane dohledatelna v historii. Kdyz konverzace
                    # potrebuje odpoved, admin ji musi napsat PRED
                    # schvalenim navrhu - schvaleni = "vyrizeno", ne
                    # "cekej dal". Plati stejne pro "Schvalit vse" (bulk
                    # jen opakuje tenhle endpoint po jednom navrhu).
                    cur.execute(
                        "UPDATE shop_support_conversations SET status='closed' WHERE id=%s",
                        (conv_id,),
                    )
                    action_taken = "closed"
            # Kdyz uz nezbyva zadny 'pending' navrh v tomhle behu, beh se
            # oznaci jako 'done' - cistě informativni stav pro frontend.
            # POZOR: schvaleny 'spam'/'crm' navrh vyse smaze konverzaci,
            # coz kaskadove smaze i tenhle radek (fk_setp_conv ON DELETE
            # CASCADE) - COUNT na run_id na tom nezavisi (pocita se podle
            # run_id, ne podle existence tohohle konkretniho radku).
            cur.execute(
                "SELECT COUNT(*) AS n FROM support_email_triage_proposals WHERE run_id=%s AND review_status='pending'",
                (row["run_id"],),
            )
            if cur.fetchone()["n"] == 0:
                cur.execute(
                    "UPDATE support_email_triage_runs SET status='done', completed_at=NOW() WHERE id=%s",
                    (row["run_id"],),
                )
        conn.commit()
    finally:
        conn.close()
    if spam_stored_filenames:
        import support_email_sync
        for stored_filename in spam_stored_filenames:
            try:
                os.remove(os.path.join(support_email_sync.SUPPORT_ATTACHMENTS_DIR, stored_filename))
            except OSError:
                pass
    log_audit(admin["id"], "update", "support_email_triage_proposal", proposal_id,
              "schváleno" if approved else "zamítnuto")
    return jsonify({"status": "ok", "action_taken": action_taken})


@app.post("/api/admin/support/triage-proposals/<int:proposal_id>/defer")
@require_permission("emaily_prichozi", "upravit")
def support_triage_proposal_defer(proposal_id):
    """Presun navrhu do "dalsi davky" (Robert, 2026-08-20, u polozek v
    "Nejasne" kde jeste nema dost informaci na schvalit/zamitnout).
    Konverzace zustava beze zmeny - stejne jako zamitnuti, ale
    VLASTNI stav 'deferred' (ne 'rejected'), at je v historii jasne
    videt rozdil mezi "bot navrhl spatne" a "nemel jsem cas/info ted".
    Zadna specialni "davkova" fronta netreba - konverzace zustava
    open+nearchivovana, takze ji dalsi --list pro NOVY beh proste
    znovu najde sam (viz cmd_list ve scripts/2026-08-18_support_
    triage_submit.py, filtruje jen status=open/archived=0)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM support_email_triage_proposals WHERE id=%s",
                (proposal_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Návrh nenalezen."}), 404
            cur.execute(
                "UPDATE support_email_triage_proposals SET review_status='deferred', reviewed_by=%s, reviewed_at=NOW() "
                "WHERE id=%s",
                (admin["id"], proposal_id),
            )
            cur.execute(
                "SELECT COUNT(*) AS n FROM support_email_triage_proposals WHERE run_id=%s AND review_status='pending'",
                (row["run_id"],),
            )
            if cur.fetchone()["n"] == 0:
                cur.execute(
                    "UPDATE support_email_triage_runs SET status='done', completed_at=NOW() WHERE id=%s",
                    (row["run_id"],),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "support_email_triage_proposal", proposal_id, "přesunuto do další dávky")
    return jsonify({"status": "ok"})


@app.post("/api/admin/support/triage-proposals/<int:proposal_id>/delete")
@require_permission("emaily_prichozi", "upravit")
def support_triage_proposal_delete(proposal_id):
    """Smazani konverzace VYHRADNE u kategorie 'jine' (Nejasne) - Robert,
    2026-08-22: "u nejasných emailů přidej tlačítko smazat", kdyz admin
    vidi, ze konverzace je jasne nepotrebna, ale zadna jina kategorie
    nesedi.

    ZAMERNE SAMOSTATNY endpoint, NE znovupouziti PUT .../review's
    `approved=true` vetve pro dest='jine' - ta zustava BEZE ZMENY
    (zadna akce, jen zaznam rozhodnuti), presne jak Robert zadal ("ne
    menit chovani Schvalit/Zamitnout tam"). Fail-closed kontrola
    `proposed_destination != 'jine'` odmitne pozadavek i kdyby si nekdo
    sestavil URL rucne mimo pripravene UI tlacitko.

    Stejna fyzicka akce jako schvaleny navrh 'spam' v PUT .../review
    (uklid stagovanych priloh + DELETE shop_support_conversations,
    ktery kaskaduje na shop_support_messages i na TENTO radek
    support_email_triage_proposals - fk_setp_conv ON DELETE CASCADE).
    Zadny novy `review_status` enum navic netreba (zvazeno, viz TASKS.md
    zadani) - smazany radek proste prestane existovat, nehrozi zamena s
    "schvaleno bez akce" v historii (na rozdil od toho by holé
    review_status='approved' bez smazani konverzace v historii vypadalo
    stejne jako normalni Schvalit). Auditni stopa jde pres log_audit()
    nize."""
    admin = current_user()
    conn = get_conn()
    spam_stored_filenames = []
    conv_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT conversation_id, proposed_destination, run_id "
                "FROM support_email_triage_proposals WHERE id=%s",
                (proposal_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Návrh nenalezen."}), 404
            if row["proposed_destination"] != "jine":
                return jsonify({"error": "Smazat lze jen návrhy v kategorii „Nejasné“."}), 400
            conv_id = row["conversation_id"]
            cur.execute(
                "SELECT a.stored_filename FROM shop_support_message_attachments a "
                "JOIN shop_support_messages m ON m.id = a.message_id "
                "WHERE m.conversation_id=%s AND a.stored_filename IS NOT NULL",
                (conv_id,),
            )
            spam_stored_filenames = [r["stored_filename"] for r in cur.fetchall()]
            cur.execute("DELETE FROM shop_support_conversations WHERE id=%s", (conv_id,))
            cur.execute(
                "SELECT COUNT(*) AS n FROM support_email_triage_proposals WHERE run_id=%s AND review_status='pending'",
                (row["run_id"],),
            )
            if cur.fetchone()["n"] == 0:
                cur.execute(
                    "UPDATE support_email_triage_runs SET status='done', completed_at=NOW() WHERE id=%s",
                    (row["run_id"],),
                )
        conn.commit()
    finally:
        conn.close()
    if spam_stored_filenames:
        import support_email_sync
        for stored_filename in spam_stored_filenames:
            try:
                os.remove(os.path.join(support_email_sync.SUPPORT_ATTACHMENTS_DIR, stored_filename))
            except OSError:
                pass
    log_audit(admin["id"], "delete", "shop_support_conversation", conv_id,
              "smazáno z třídění (kategorie „Nejasné“, tlačítko Smazat)")
    return jsonify({"status": "ok"})
