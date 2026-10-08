"""
E-mailovy klient primo v systemu - bot3, 2026-07-25 (v9).

Robert: "nachystej emailoveho klienta pro odesilani emailu primo ze
systemu, vcetne vedeni historie, napric sekcemi jako objednavky, faktury,
vsechny tyto typy dokladu, přidej dodací listy, vse musi mit prehledy s
pořádným filtrováním."

Rozhodnuti Roberta (AskUserQuestion, 2026-07-25):
  - Odesilani: RUCNE z adminu (tlacitko, text lze pred odeslanim upravit)
    I AUTOMATICKY u klicovych udalosti (OBOJI zvoleno) - viz volani
    emails.send_and_log()/emails.send_document_email_auto() z orders.py
    (potvrzeni objednavky, zmena stavu, automaticka zalohova faktura) a z
    documents.py::_auto_email_after_issue() (proforma/VDD/faktura/dodaci
    list po rucnim vystaveni admin em).
  - Priloha: PDF souvisejiciho dokladu se AUTOMATICKY prednabizi (admin ji
    muze pri rucnim odesilani pres POST .../documents/<id>/email zmenit/
    odebrat pomoci vlastniho subject/body; u volneho e-mailu k objednavce
    jde priloha vybrat pres attach_document_id).
  - Dodaci listy: NOVY typ dokladu v UZ EXISTUJICIM systemu dokladu (viz
    documents.py DOCUMENT_TYPES + create_delivery_note) - NE samostatna
    tabulka/modul.

Kazdy odeslany e-mail (rucni i automaticky, uspesny i neuspesny) se
zaznamena do shop_emails (sql/2026-07-25_emails.sql) - "historie napric
sekcemi": kazdy zaznam ma order_id (VZDY) a volitelne document_id, takze
historie jde zobrazit podle objednavky (GET .../orders/<id>/emails),
podle konkretniho dokladu (GET .../documents/<id>/emails) i CELKOVE
(GET /api/admin/emails - filtrovani + counts, stejny vzor jako
GET /api/admin/documents z (13)).

Odesilani NIKDY nesmi shodit hlavni operaci (vytvoreni objednavky/dokladu) -
vyjimky ze `send_email()` (app.py) se VZDY chytaji uvnitr send_and_log(),
neuspech se jen zaloguje jako status='failed' s error_message, volajici
kod (orders.py/documents.py) navic sam obaluje cele auto-volani do
try/except (viz jejich komentare), takze SMTP vypadek nikdy neprojevi
navenek jako 500 na puvodni akci.

Aktivace: `import emails` na UPLNY KONEC app.py, AZ PO `import documents`
(viz konec app.py) - emails.py pouziva documents.render_document_pdf(),
documents._fetch_document()/_fetch_order()/_fetch_order_items(),
documents.DOCUMENT_TYPE_LABELS, documents._fmt_czk()/_fmt_date()/_money().
Naopak orders.py/documents.py NEIMPORTUJI emails.py na urovni modulu (to
by vedlo k cyklickemu importu - emails.py potrebuje documents.py plne
nacteny UZ PRI SVEM VLASTNIM importu) - misto toho volaji `import emails`
AZ UVNITR funkce, tesne pred samotnym odeslanim. To je bezpecne (na rozdil
od stejne-vypadajiciho puvodniho bugu s `import documents` uvnitr
_resolve_and_insert_order, viz komentar v orders.py): v okamziku PRVNIHO
HTTP requestu je emails.py uz davno plne nacteny (cely retez importu na
konci app.py probehne pri STARTU aplikace, ne az za behu) - lazy import
tedy jen sahne do jiz existujiciho sys.modules zaznamu, NEREGISTRUJE
zadnou novou route za behu (to byl skutecny problem puvodniho bugu).

Vyzaduje migraci sql/2026-07-25_emails.sql (nova tabulka shop_emails) -
MUSI byt spustena PRED restartem se zapnutym timhle modulem. Sloupec sent_at (skutecny cas odeslani) pridava sql/2026-10-08_shop_emails_sent_at.sql
(shop_emails i system_emails; MUSI byt spustena PRED nasazenim kodu, ktery ho zapisuje).
"""
from flask import request, jsonify

from app import (
    app, get_conn, require_permission, current_user, log_audit, send_email,
    get_pagination_args, paginated_query, parse_bulk_ids, bulk_delete,
)

import documents  # noqa: E402 - viz docstring vyse pro poradek importu

# ---------------------------------------------------------------------------
# Staticka konfigurace
# ---------------------------------------------------------------------------

EMAIL_KINDS = (
    "order_confirmation", "status_change",
    "proforma_invoice", "payment_tax_document", "invoice", "delivery_note",
    "purchase_order",
    "custom",
)

EMAIL_KIND_LABELS = {
    "order_confirmation": "Potvrzení objednávky",
    "status_change": "Změna stavu objednávky",
    "proforma_invoice": "Zálohová faktura",
    "payment_tax_document": "Daňový doklad k přijaté platbě",
    "purchase_order": "Objednávka dodavateli",
    "invoice": "Faktura",
    "delivery_note": "Dodací list",
    "custom": "Vlastní e-mail",
}


# ---------------------------------------------------------------------------
# Sablony - vychozi predmet/text (admin je pri rucnim odeslani muze prepsat)
# ---------------------------------------------------------------------------

def default_subject_body_for_document(doc_type, order_number, customer_name, document_number,
                                       amount_due_czk=None, due_date=None):
    label = documents.DOCUMENT_TYPE_LABELS.get(doc_type, doc_type)
    first = (customer_name or "").split(" ")[0] if customer_name else ""
    greeting = "Dobrý den," if not first else f"Dobrý den, {first},"
    subject = f"{label} č. {document_number} - objednávka {order_number}"
    lines = [
        greeting, "",
        f"v příloze Vám zasíláme {label.lower()} č. {document_number} k objednávce č. {order_number}.",
    ]
    if doc_type in ("proforma_invoice", "invoice") and amount_due_czk:
        due_str = documents._fmt_date(due_date) if due_date else ""
        lines.append(
            f"K úhradě: {documents._fmt_czk(amount_due_czk)}" + (f", splatnost do {due_str}." if due_str else ".")
        )
    if doc_type == "payment_tax_document":
        lines.append("Tento doklad slouží pouze jako potvrzení přijaté platby - prosím NEPLAŤTE jej.")
    if doc_type == "delivery_note":
        lines.append("Zásilka byla předána k expedici - v příloze najdete dodací list s přehledem dodaných položek.")
    lines += ["", "S pozdravem,", "LOGIMAN s.r.o."]
    return subject, "\n".join(lines)


def _default_subject_body_order_confirmation(cur, order):
    items = documents._fetch_order_items(cur, order["id"])
    name = order.get("customer_name") or order.get("billing_name") or ""
    first = name.split(" ")[0] if name else ""
    greeting = "Dobrý den," if not first else f"Dobrý den, {first},"
    lines = [greeting, "", f"děkujeme za Vaši objednávku č. {order['order_number']}.", "", "Položky objednávky:"]
    for it in items:
        # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks také 3m") -
        # sdilena podminka s doklady, viz documents._is_profile_order_item
        # (vyluci desky s cfg_dily_id i stinove radky rezneho planu).
        unit_note = " (3 m)" if documents._is_profile_order_item(it) else ""
        lines.append(f"  - {it['product_name_snapshot']} × {it['qty']} ks{unit_note} = {documents._fmt_czk(it['line_total_czk'])}")
    lines += [
        "", f"Celkem: {documents._fmt_czk(order.get('total_czk'))}", "",
        "Ozveme se Vám s dalšími kroky.", "", "S pozdravem,", "LOGIMAN s.r.o.",
    ]
    subject = f"Potvrzení objednávky č. {order['order_number']} - LOGIMAN s.r.o."
    return subject, "\n".join(lines)


# ---------------------------------------------------------------------------
# Odeslani + zalogovani (jadro modulu)
# ---------------------------------------------------------------------------

def neschvaleny_doklad(doc):
    """Robert 2026-10-08 ("nemuze se nabidnout odeslat e-mail o potvrzeni zaslani dokladu, ktery neni schvaleny"): e-mail s PDF dokladem se nesmi zaradit do fronty ani odeslat, dokud doklad
    neni `schvaleno` (shop_documents.approval_status, schvaluje se na Dashboardu: POST /api/admin/documents/<id>/approve). -> text hlasky pro uzivatele, nebo None (schvaleny / zadny doklad)."""
    if doc and doc.get("approval_status") != "schvaleno":
        return f"Doklad č. {doc.get('document_number') or doc.get('id')} ještě není schválený – e-mail s ním nejde odeslat. Nejdřív ho schval na Dashboardu."
    return None


def _log_email(cur, *, order_id, document_id, template_key, recipient_email, cc_email,
                subject, body_text, status, error_message, trigger, sent_by_label, sent_by_user_id,
                purchase_order_id=None):
    """Zapis radku historie. sent_at (skutecny cas odeslani, bot5 2026-10-08, Robert pres bot16: "schvaleni jsem udelal az ted") se plni JEN pri status='sent' (volano hned po send_email);
    created_at je cas zarazeni do fronty. Cekajici ('pending') a neuspesne radky maji sent_at NULL, doplni ho az approve_pending_email."""
    cur.execute(
        "INSERT INTO shop_emails "
        "(order_id, purchase_order_id, document_id, template_key, recipient_email, cc_email, subject, body_text, "
        " status, error_message, trigger_type, sent_by, sent_by_user_id, sent_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, IF(%s='sent', NOW(), NULL))",
        (order_id, purchase_order_id, document_id, template_key, recipient_email, cc_email, subject, body_text,
         status, error_message, trigger, sent_by_label, sent_by_user_id, status),
    )
    return cur.lastrowid


def _recent_duplicate_send(cur, *, order_id, document_id, template_key, window_seconds=60):
    """W1 (bezpecnostni nalez, bot3/revize kodu 2026-09-02): rucni odeslani
    (admin_order_send_email/admin_document_send_email) nemelo zadnou
    ochranu proti dvojkliku/retry - dva POSTy v rychlem sledu poslaly
    stejny e-mail 2x. Kontrola jen KRATKE okno (60s), ne trvala blokace -
    "znovu-odeslani" dokladu po case je zamerna funkce (viz docstring
    admin_document_send_email). Klic = order_id + template_key, zuzeny o
    document_id kdyz je znamy (konkretni doklad)."""
    where = ["order_id=%s", "template_key=%s", "status IN ('pending','sent')",
             "created_at >= NOW() - INTERVAL %s SECOND"]
    params = [order_id, template_key, window_seconds]
    if document_id:
        where.insert(2, "document_id=%s")
        params.insert(2, document_id)
    cur.execute(f"SELECT id FROM shop_emails WHERE {' AND '.join(where)} LIMIT 1", params)
    return cur.fetchone() is not None


def send_and_log(order_id, *, template_key, recipient, subject, body, cc=None,
                  document_id=None, admin=None, auto=False, purchase_order_id=None):
    """Spolecna nizkourovnova funkce - VZDY zaloguje vysledek do
    shop_emails, bez ohledu na uspech/neuspech odeslani. Pokud je zadane
    document_id, PDF prilohy se dogeneruje z existujiciho dokladu (viz
    documents.render_document_pdf - doklady jsou nemenne snapshoty, takze
    PDF jde kdykoli znovu vygenerovat identicke). Pouziva se jak primo z
    endpointu (rucni odeslani), tak z auto-trigger volani v orders.py/
    documents.py po commitu hlavni transakce.

    NOVE (Robert 2026-08-22, WORKFLOW.md bod 16 - "NELZE aby se emaily
    odesilali automaticky pri zmenach stavu (ani jindy), vsechny odchozi
    emaily musi schvalit admin"): kdyz auto=True A mame prijemce, e-mail
    se ZALOGUJE jako 'pending' a NEODESLE - ceka na rucni schvaleni
    (viz admin_email_review nize v tomhle souboru). Priloha (PDF) se
    negeneruje ted (dokument je nemenny snapshot, dogeneruje se znovu az
    pri schvaleni z document_id, viz admin_email_review). Bez prijemce
    (auto i manual) zustava puvodni chovani - okamzite 'failed', nema
    smysl "cekat na schvaleni" e-mailu, ktery nikdy nepujde poslat.
    RUCNI odeslani (auto=False, admin aktivne klikne) je uz samo o sobe
    schvaleni - NEMENI se, posila se rovnou jako drive."""
    if document_id:                                              # pojistka: e-mail s neschvalenym dokladem se nezarazuje ani neposila (nic se ani nelogguje)
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                chyba = neschvaleny_doklad(documents._fetch_document(cur, document_id))
        finally:
            conn.close()
        if chyba:
            return None, "not_approved", chyba
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if auto and recipient:
                log_id = _log_email(
                    cur, order_id=order_id, document_id=document_id, template_key=template_key,
                    recipient_email=recipient, cc_email=cc, subject=subject, body_text=body,
                    purchase_order_id=purchase_order_id,
                    status="pending", error_message=None, trigger="auto",
                    sent_by_label="Systém (automaticky)", sent_by_user_id=None,
                )
                conn.commit()
                return log_id, "pending", None

            attachment = None
            if document_id:
                doc = documents._fetch_document(cur, document_id)
                if doc:
                    pdf_bytes = documents.render_document_pdf(doc)
                    filename = f"{doc['document_type']}_{doc['document_number']}.pdf"
                    attachment = (filename, pdf_bytes, "pdf")

            if not recipient:
                status, err = "failed", "Chybí e-mail příjemce."
            else:
                try:
                    send_email(recipient, subject, body, cc_email=cc,
                               attachments=[attachment] if attachment else None)
                    status, err = "sent", None
                except Exception as e:
                    status, err = "failed", str(e)

            log_id = _log_email(
                cur, order_id=order_id, document_id=document_id, template_key=template_key,
                recipient_email=recipient or "", cc_email=cc, subject=subject, body_text=body,
                purchase_order_id=purchase_order_id,
                status=status, error_message=err, trigger=("auto" if auto else "manual"),
                sent_by_label=("Systém (automaticky)" if auto else documents._issued_by_label(admin)),
                sent_by_user_id=(admin["id"] if admin else None),
            )
        conn.commit()
    finally:
        conn.close()
    return log_id, status, err


def approve_pending_email(email_id, admin):
    """Schvaleni cekajiciho ('pending') automatickeho e-mailu - admin ho
    PRAVE TED aktivne schvaluje k odeslani (Robert 2026-08-22, viz
    send_and_log docstring vyse). Priloha (PDF) se dogeneruje cerstve z
    document_id (nemenny snapshot dokladu), presne jako u rucniho
    odeslani. Vraci (status, error) - 'sent'|'failed', nikdy nevyhodi
    vyjimku ven (stejny princip jako send_and_log)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shop_emails WHERE id=%s", (email_id,))
            row = cur.fetchone()
            if not row:
                return None, "not_found", None
            if row["document_id"]:                               # doklad mezitim neni schvaleny / jeste nebyl: e-mail zustava ve fronte, neodejde
                chyba = neschvaleny_doklad(documents._fetch_document(cur, row["document_id"]))
                if chyba:
                    return row, "doc_not_approved", chyba
            # Atomicky "claim" radek PRED odeslanim (ne jen SELECT+kontrola v
            # Pythonu - dva soubezne kliky na schvaleni by jinak oba prosly
            # kontrolou a e-mail se odeslal dvakrat). UPDATE...WHERE status=
            # 'pending' je pod row-lockem druheho souvisleho pripojeni
            # zablokovana, dokud tahle transakce nedokonci commit - rowcount
            # 1 = ja jsem prvni, kdo smi odeslat.
            cur.execute("UPDATE shop_emails SET status='sending' WHERE id=%s AND status='pending'", (email_id,))
            if cur.rowcount != 1:
                return row, "not_pending", None

            attachment = None
            if row["document_id"]:
                doc = documents._fetch_document(cur, row["document_id"])
                if doc:
                    pdf_bytes = documents.render_document_pdf(doc)
                    filename = f"{doc['document_type']}_{doc['document_number']}.pdf"
                    attachment = (filename, pdf_bytes, "pdf")
            elif (row["template_key"] or "").startswith("prijaty_doklad:"):
                # bot5, 2026-10-06: e-mail ucetni s PRIJATYM dokladem - soubor ze Sdileneho disku se nacte az ted (viz ucetni_hak.priloha_prijateho)
                try:
                    import ucetni_hak
                    attachment = ucetni_hak.priloha_prijateho(cur, int(row["template_key"].split(":", 1)[1]))
                except (ValueError, IndexError):
                    attachment = None
                if attachment is None:
                    cur.execute("UPDATE shop_emails SET status='pending' WHERE id=%s AND status='sending'", (email_id,))
                    conn.commit()
                    return row, "failed", "Příloha (přijatý doklad) nenalezena, e-mail se neodeslal."

            try:
                send_email(row["recipient_email"], row["subject"], row["body_text"], cc_email=row["cc_email"],
                           attachments=[attachment] if attachment else None)
                status, err = "sent", None
            except Exception as e:
                status, err = "failed", str(e)

            # sent_at = okamzik PO send_email (skutecne odeslani), ne created_at (zarazeni do fronty); jen u 'sent', u 'failed' zustava NULL
            cur.execute(
                "UPDATE shop_emails SET status=%s, error_message=%s, sent_by=%s, sent_by_user_id=%s, "
                "sent_at=IF(%s='sent', NOW(), NULL) WHERE id=%s",
                (status, err, documents._issued_by_label(admin), admin["id"] if admin else None, status, email_id),
            )
        conn.commit()
    finally:
        conn.close()

    # Pravidlo 1+2 (orders.py::auto_confirm_after_confirmation_email) -
    # objednavka se puvodne preklapela z "nova" na potvrzenou/cekajici
    # PRESNE ve chvili, kdy potvrzovaci e-mail skutecne odesel. Po
    # zavedeni schvalovani se ta chvile posunula sem (schvaleni + uspesny
    # odesel), ne uz na puvodni auto-trigger (ten ted jen zaloguje
    # 'pending'). Lazy import (stejny duvod jako jinde v tomhle souboru -
    # orders.py neimportuje emails.py na urovni modulu).
    if status == "sent" and row["template_key"] == "order_confirmation" and row["order_id"]:
        import orders
        orders.auto_confirm_after_confirmation_email(row["order_id"])

    return row, status, err


def reject_pending_email(email_id, admin):
    """Zamitnuti cekajiciho e-mailu - NATRVALO, nikdy neodejde (Robert
    2026-08-22). Jen zaznamena rozhodnuti, zadne odeslani se nezkousi.

    W2 (bezpecnostni nalez, bot3/revize kodu 2026-09-02): puvodne
    SELECT+UPDATE jako 2 kroky (na rozdil od approve_pending_email, ktera
    uz atomicky "claim" ma) - soubezny approve+reject na stejnem radku
    mohl zavist k nekonzistenci. Ted jeden atomicky UPDATE ... WHERE
    status='pending', rowcount==0 = uz vyrizeno (stejny "not_pending"
    navrat/400 jako approve_pending_email pro stejny pripad - schvalne
    NEzavadim jiny stavovy kod jen pro reject, at je chovani symetricke)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status FROM shop_emails WHERE id=%s", (email_id,))
            row = cur.fetchone()
            if not row:
                return None, "not_found"
            cur.execute(
                "UPDATE shop_emails SET status='rejected', sent_by=%s, sent_by_user_id=%s "
                "WHERE id=%s AND status='pending'",
                (documents._issued_by_label(admin), admin["id"] if admin else None, email_id),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return row, "not_pending"
        conn.commit()
    finally:
        conn.close()
    return row, "rejected"


def send_document_email_auto(order_id, document_id):
    """Auto-trigger po vystaveni dokladu (zalohova faktura/VDD/faktura/
    dodaci list) - najde objednavku+doklad, sestavi vychozi predmet/text
    podle typu dokladu a odesle+zaloguje. Volano z
    documents.py::_auto_email_after_issue() (lazy import, viz jeho
    komentar)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order = documents._fetch_order(cur, order_id)
            doc = documents._fetch_document(cur, document_id)
    finally:
        conn.close()
    if not order or not doc:
        return None, "failed", "Objednávka nebo doklad neexistuje."
    chyba = neschvaleny_doklad(doc)
    if chyba:
        return None, "not_approved", chyba                       # neschvaleny doklad: e-mail se nezarazuje; zaradi se az po schvaleni (approvals.approve_document)
    conn = get_conn()
    try:
        with conn.cursor() as cur:                               # idempotence: zakaznicky e-mail k dokladu se zaradi nejvyse jednou (vystaveni i schvaleni dokladu ho zkousi)
            cur.execute("SELECT id FROM shop_emails WHERE document_id=%s AND template_key=%s AND trigger_type='auto' AND status IN ('pending','sending','sent') LIMIT 1",
                        (document_id, doc["document_type"]))
            existuje = cur.fetchone()
    finally:
        conn.close()
    if existuje:
        return existuje["id"], "already_queued", None
    subject, body = default_subject_body_for_document(
        doc["document_type"], order["order_number"], order.get("customer_name"),
        doc["document_number"], amount_due_czk=documents._money(doc["amount_due_czk"]), due_date=doc["due_date"],
    )
    return send_and_log(
        order_id, template_key=doc["document_type"], recipient=order.get("customer_email"),
        subject=subject, body=body, document_id=document_id, admin=None, auto=True,
    )


# ---------------------------------------------------------------------------
# Admin: rucni odeslani
# ---------------------------------------------------------------------------

@app.post("/api/admin/orders/<int:order_id>/emails")
@require_permission("emaily_odchozi", "vytvorit")
def admin_order_send_email(order_id):
    """
    Rucni odeslani e-mailu k objednavce - BEZ konkretniho dokladu (pro
    konkretni doklad viz POST /api/admin/documents/<id>/email nize).

    Body:
    {
      "kind": "order_confirmation" | "custom",   (default "custom")
      "recipient": "jina@adresa.cz",              (volitelne, jinak e-mail zakaznika z objednavky)
      "cc": "kopie@example.cz",                    (volitelne)
      "subject": "...",                             (volitelne u order_confirmation - jinak vychozi sablona; POVINNE u custom)
      "body": "...",                                  (stejne jako subject)
      "attach_document_id": 42                          (volitelne - prilozi PDF existujiciho dokladu teto objednavky)
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    kind = body.get("kind") or "custom"
    if kind not in ("order_confirmation", "custom"):
        return jsonify({
            "error": "Nepodporovaný 'kind' (order_confirmation nebo custom; pro konkrétní doklad "
                     "použij POST /api/admin/documents/<id>/email)."
        }), 400
    recipient_override = (body.get("recipient") or "").strip() or None
    cc = (body.get("cc") or "").strip() or None
    subject_override = (body.get("subject") or "").strip() or None
    body_override = body.get("body") or None
    attach_document_id = body.get("attach_document_id")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            order = documents._fetch_order(cur, order_id)
            if not order:
                return jsonify({"error": "Objednávka neexistuje."}), 404
            if attach_document_id:
                doc = documents._fetch_document(cur, attach_document_id)
                if not doc or doc["order_id"] != order_id:
                    return jsonify({"error": "Vybraný doklad nepatří k této objednávce."}), 400
                chyba = neschvaleny_doklad(doc)
                if chyba:
                    return jsonify({"error": chyba, "code": "document_not_approved"}), 409
            default_subject, default_body = (
                _default_subject_body_order_confirmation(cur, order) if kind == "order_confirmation" else (None, None)
            )
            if _recent_duplicate_send(cur, order_id=order_id, document_id=attach_document_id, template_key=kind):
                return jsonify({"error": "already_sent"}), 409
    finally:
        conn.close()

    if kind == "custom" and not (subject_override and body_override):
        return jsonify({"error": "U vlastního e-mailu (kind=custom) je nutné vyplnit subject i body."}), 400

    to_email = recipient_override or order.get("customer_email")
    subject = subject_override or default_subject
    msg_body = body_override or default_body

    log_id, status, err = send_and_log(
        order_id, template_key=kind, recipient=to_email, subject=subject, body=msg_body,
        cc=cc, document_id=attach_document_id, admin=admin, auto=False,
    )
    if status != "sent":
        return jsonify({"status": "failed", "id": log_id, "error": err}), 502
    log_audit(admin["id"], "send", "email", log_id, f"order {order_id}: {kind}")
    return jsonify({"status": "ok", "id": log_id})


@app.post("/api/admin/documents/<int:doc_id>/email")
@require_permission("emaily_odchozi", "vytvorit")
def admin_document_send_email(doc_id):
    """
    Rucni odeslani (nebo znovu-odeslani) e-mailu ke KONKRETNIMU dokladu -
    PDF dokladu se VZDY priloz (Robert, AskUserQuestion 2026-07-25: 'PDF
    souvisejícího dokladu se automaticky přednabízí').

    Body (vse volitelne - bez nich se pouzije vychozi sablona podle typu
    dokladu, viz default_subject_body_for_document):
    {
      "recipient": "jina@adresa.cz",
      "cc": "kopie@example.cz",
      "subject": "...",
      "body": "..."
    }
    """
    admin = current_user()
    body = request.get_json(silent=True) or {}
    recipient_override = (body.get("recipient") or "").strip() or None
    cc = (body.get("cc") or "").strip() or None
    subject_override = (body.get("subject") or "").strip() or None
    body_override = body.get("body") or None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            doc = documents._fetch_document(cur, doc_id)
            if not doc:
                return jsonify({"error": "Doklad neexistuje."}), 404
            chyba = neschvaleny_doklad(doc)
            if chyba:
                return jsonify({"error": chyba, "code": "document_not_approved"}), 409
            order = documents._fetch_order(cur, doc["order_id"])
            if _recent_duplicate_send(cur, order_id=doc["order_id"], document_id=doc_id, template_key=doc["document_type"]):
                return jsonify({"error": "already_sent"}), 409
    finally:
        conn.close()

    default_subject, default_body = default_subject_body_for_document(
        doc["document_type"], order["order_number"], order.get("customer_name"),
        doc["document_number"], amount_due_czk=documents._money(doc["amount_due_czk"]), due_date=doc["due_date"],
    )
    to_email = recipient_override or order.get("customer_email")
    subject = subject_override or default_subject
    msg_body = body_override or default_body

    log_id, status, err = send_and_log(
        doc["order_id"], template_key=doc["document_type"], recipient=to_email, subject=subject,
        body=msg_body, cc=cc, document_id=doc_id, admin=admin, auto=False,
    )
    if status != "sent":
        return jsonify({"status": "failed", "id": log_id, "error": err}), 502
    log_audit(admin["id"], "send", "email", log_id, f"document {doc_id}")
    return jsonify({"status": "ok", "id": log_id})


# ---------------------------------------------------------------------------
# Historie / prehledy
# ---------------------------------------------------------------------------

def _serialize_email(row):
    return {
        "id": row["id"],
        "order_id": row["order_id"],
        "document_id": row["document_id"],
        "purchase_order_id": row["purchase_order_id"],
        "order_number": row.get("order_number"),
        "customer_name": row.get("customer_name"),
        "document_number": row.get("document_number"),
        "po_number": row.get("po_number"),
        "po_supplier_name": row.get("po_supplier_name"),
        "template_key": row["template_key"],
        "template_label": EMAIL_KIND_LABELS.get(row["template_key"], row["template_key"]),
        "recipient_email": row["recipient_email"],
        "cc_email": row["cc_email"],
        "subject": row["subject"],
        "body_text": row["body_text"],
        "status": row["status"],
        "error_message": row["error_message"],
        "trigger_type": row["trigger_type"],
        "sent_by": row["sent_by"],
        "created_at": documents._dt(row["created_at"]),
        "sent_at": documents._dt(row.get("sent_at")),
    }


_EMAILS_BASE_SQL = (
    "SELECT e.*, o.order_number, o.customer_name, d.document_number, "
    "       po.po_number, po.supplier_name AS po_supplier_name "
    "FROM shop_emails e LEFT JOIN shop_orders o ON o.id=e.order_id "
    "LEFT JOIN shop_documents d ON d.id=e.document_id "
    "LEFT JOIN shop_purchase_orders po ON po.id=e.purchase_order_id"
)


@app.get("/api/admin/orders/<int:order_id>/emails")
@require_permission("emaily_odchozi", "zobrazit")
def admin_order_emails_list(order_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_EMAILS_BASE_SQL + " WHERE e.order_id=%s ORDER BY e.created_at DESC, e.id DESC", (order_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"emails": [_serialize_email(r) for r in rows]})


@app.get("/api/admin/documents/<int:doc_id>/emails")
@require_permission("emaily_odchozi", "zobrazit")
def admin_document_emails_list(doc_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_EMAILS_BASE_SQL + " WHERE e.document_id=%s ORDER BY e.created_at DESC, e.id DESC", (doc_id,))
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"emails": [_serialize_email(r) for r in rows]})


@app.get("/api/admin/emails")
@require_permission("emaily_odchozi", "zobrazit")
def admin_emails_overview():
    """
    Celkovy prehled VSECH odeslanych e-mailu napric objednavkami i doklady
    (Robert, 2026-07-25: 'vše musí mít přehledy s pořádným filtrováním') -
    stejny vzor jako GET /api/admin/documents (13).

    ?template_key=order_confirmation|status_change|proforma_invoice|payment_tax_document|invoice|delivery_note|custom
    ?status=sent|failed|pending|rejected
    ?trigger_type=manual|auto
    ?q=...  - hledani v prijemci, predmetu, cisle objednavky, jmenu zakaznika, cisle dokladu
    ?date_from=YYYY-MM-DD, ?date_to=YYYY-MM-DD  - filtr na datum odeslani (sent_at; u radku bez nej - cekajici/zamitnute/neuspesne - datum zarazeni created_at)

    Odpoved obsahuje "counts" (po typu sablony + "all") a "status_counts"
    (sent/failed/pending/rejected) - pro vykresleni tabu/badge v adminu
    bez nutnosti volat endpoint vicekrat. "pending" (Robert 2026-08-22) =
    automaticky e-mail cekajici na schvaleni admina, viz send_and_log.
    """
    template_key = request.args.get("template_key")
    status = request.args.get("status")
    trigger_type = request.args.get("trigger_type")
    q = (request.args.get("q") or "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if template_key and template_key not in EMAIL_KINDS:
        return jsonify({"error": "Neplatný template_key."}), 400
    if status and status not in ("sent", "failed", "pending", "rejected"):
        return jsonify({"error": "Neplatný status."}), 400
    if trigger_type and trigger_type not in ("manual", "auto"):
        return jsonify({"error": "Neplatný trigger_type."}), 400

    where, params = [], []
    if template_key:
        where.append("e.template_key=%s"); params.append(template_key)
    if status:
        where.append("e.status=%s"); params.append(status)
    if trigger_type:
        where.append("e.trigger_type=%s"); params.append(trigger_type)
    if q:
        where.append(
            "(e.recipient_email LIKE %s OR e.subject LIKE %s OR o.order_number LIKE %s "
            "OR o.customer_name LIKE %s OR d.document_number LIKE %s "
            "OR po.po_number LIKE %s OR po.supplier_name LIKE %s)"
        )
        like = f"%{q}%"
        params += [like, like, like, like, like, like, like]
    if date_from:
        where.append("DATE(COALESCE(e.sent_at, e.created_at)) >= %s"); params.append(date_from)
    if date_to:
        where.append("DATE(COALESCE(e.sent_at, e.created_at)) <= %s"); params.append(date_to)

    # Stránkování (task #78/83)
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, _EMAILS_BASE_SQL, where_sql, params,
                                           " ORDER BY e.created_at DESC, e.id DESC", page, page_size)

            cur.execute("SELECT template_key, COUNT(*) AS n FROM shop_emails GROUP BY template_key")
            kind_counts = {r["template_key"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT status, COUNT(*) AS n FROM shop_emails GROUP BY status")
            status_counts = {r["status"]: r["n"] for r in cur.fetchall()}
            cur.execute("SELECT COUNT(*) AS n FROM shop_emails")
            all_count = cur.fetchone()["n"]
    finally:
        conn.close()

    counts = {"all": all_count}
    for k in EMAIL_KINDS:
        counts[k] = kind_counts.get(k, 0)

    resp = {
        "emails": [_serialize_email(r) for r in rows],
        "counts": counts,
        "status_counts": {
            "sent": status_counts.get("sent", 0), "failed": status_counts.get("failed", 0),
            "pending": status_counts.get("pending", 0), "rejected": status_counts.get("rejected", 0),
        },
    }
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


# ---------------------------------------------------------------------------
# Schvalovani cekajicich automatickych e-mailu (Robert 2026-08-22)
# ---------------------------------------------------------------------------
# Stejny vzor jako support.py triage-proposals review - jeden radek,
# {"approved": true|false}, frontend bulk akce jen smycku volani tohoto
# endpointu (viz webapp/admin.html emailBulkApprove/emailBulkReject).

@app.put("/api/admin/emails/<int:email_id>")
@require_permission("emaily_odchozi", "upravit")
def admin_email_review(email_id):
    """
    Robert 2026-08-24: schvalovaci okno musi jit editovat, ne jen
    zobrazit - u cekajiciho e-mailu (typicky nakupni objednavka
    dodavateli) admin muze pred schvalenim opravit predmet/text.
    Volitelne "subject"/"body_text" v body se ulozi VZDY pred
    approve/reject (i pri zamitnuti, pro pripad ze se k tomu bude
    vracet) - jen u zaznamu, ktery je jeste 'pending' (jinak by to
    prepsalo uz odeslany/zamitnuty text, ktery ma zustat historickym
    snapshotem toho, co se skutecne stalo).
    """
    body = request.get_json(silent=True) or {}
    approved = body.get("approved")
    new_subject = body.get("subject")
    new_body_text = body.get("body_text")
    if approved not in (True, False) and approved is not None:
        return jsonify({"error": "Chybí approved (true/false)."}), 400
    if new_subject is not None or new_body_text is not None:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM shop_emails WHERE id=%s", (email_id,))
                row = cur.fetchone()
                if not row:
                    return jsonify({"error": "Záznam e-mailu neexistuje."}), 404
                if row["status"] == "pending":
                    fields, params = [], []
                    if new_subject is not None:
                        fields.append("subject=%s")
                        params.append(new_subject)
                    if new_body_text is not None:
                        fields.append("body_text=%s")
                        params.append(new_body_text)
                    params.append(email_id)
                    cur.execute(f"UPDATE shop_emails SET {', '.join(fields)} WHERE id=%s", params)
            conn.commit()
        finally:
            conn.close()
    if approved is None:
        # Jen ulozeni upraveneho textu, bez rozhodnuti schvalit/zamitnout.
        admin = current_user()
        log_audit(admin["id"], "update", "email", email_id, "Upraven text čekajícího e-mailu.")
        return jsonify({"status": "ok"})
    admin = current_user()
    if approved:
        row, status, err = approve_pending_email(email_id, admin)
    else:
        row, status = reject_pending_email(email_id, admin)
        err = None
    if row is None:
        return jsonify({"error": "Záznam e-mailu neexistuje."}), 404
    if status == "not_pending":
        return jsonify({"error": "Tenhle e-mail už není ve stavu čeká na schválení (byl už vyřízen)."}), 400
    if status == "doc_not_approved":
        return jsonify({"error": err, "code": "document_not_approved"}), 409
    log_audit(admin["id"], "update", "email", email_id,
               f"{'Schváleno' if approved else 'Zamítnuto'}: {row['subject']} ({row['recipient_email']}).")
    return jsonify({"status": "ok", "email_status": status, "error_message": err})


# ---------------------------------------------------------------------------
# Mazani zaznamu historie (Robert 2026-07-26: "mazat musí být všude !!!")
# ---------------------------------------------------------------------------
# Na rozdil od shop_documents na shop_emails NEODKAZUJE zadna FK (je to
# "list", ne "rodic" zadne dalsi tabulky), takze jde o prosty DELETE bez
# potreby cokoli jinde odpojovat. Smazani zaznamu odeslani NIJAK
# necouvne/neovlivni objednavku ani doklad, ke kteremu se e-mail vazal -
# maze se jen samotny log o tom, ze e-mail byl odeslan.

@app.delete("/api/admin/emails/<int:email_id>")
@require_permission("emaily_odchozi", "smazat")
def admin_email_delete_one(email_id):
    """Smazani JEDNOHO zaznamu z historie e-mailu."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, recipient_email, subject FROM shop_emails WHERE id=%s", (email_id,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return jsonify({"error": "Záznam e-mailu neexistuje."}), 404
            cur.execute("DELETE FROM shop_emails WHERE id=%s", (email_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "delete", "email", email_id,
              f"Smazán záznam e-mailu: {row['subject']} ({row['recipient_email']}).")
    return jsonify({"status": "ok"})


@app.post("/api/admin/emails/bulk-delete")
@require_permission("emaily_odchozi", "smazat")
def admin_emails_bulk_delete():
    """Hromadne smazani zaznamu historie e-mailu."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(ids))
            cur.execute(f"SELECT id FROM shop_emails WHERE id IN ({placeholders})", ids)
            found_ids = {r["id"] for r in cur.fetchall()}
            deleted = bulk_delete(cur, "shop_emails", ids)
        conn.commit()
    finally:
        conn.close()
    missing = [i for i in ids if i not in found_ids]
    log_audit(admin["id"], "bulk_delete", "email", None,
              f"{deleted} záznamů e-mailů smazáno" + (f", {len(missing)} nenalezeno" if missing else ""))
    return jsonify({"status": "ok", "deleted": deleted,
                     "failed": [{"id": i, "error": "Záznam neexistuje."} for i in missing]})
