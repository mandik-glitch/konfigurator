"""
Schvalovani - agregovany prehled "Ke schvaleni" pro dashboard (bot6, 2026-08-01).

Robert: "veskere doklady ktere maji byt schvaleny nejakou roli, jakmile
vzniknou musi se ihned objevit na dashboardu dane role ktera to ma
schvalovat" - potvrzeny rozsah (AskUserQuestion, "vsechno co te napadne"):

  1. Nakupni objednavky ve stavu 'navrh'      (schvaluje nakupni_objednavky/upravit)
  2. Prijate objednavky ve stavu 'nova'       (schvaluje objednavky/upravit)
  3. Nabidky s approval_status='ceka_schvaleni' (schvaluje nabidky/upravit)
  4. Doklady s approval_status='ceka_schvaleni' (schvaluje doklady/upravit)

Body 1+2 pouzivaji EXISTUJICI stavy (schvaleni = prechod stavu, ktery uz
v aplikaci je - potvrzeni objednavky/odeslani PO), body 3+4 dostaly novy
sloupec approval_status (sql/2026-08-01_approvals.sql) + POST approve
endpointy zde.

GET /api/admin/approvals vraci jen sekce, na ktere ma PRIHLASENA role
pravo 'upravit' (has_permission) - kazda role tak na dashboardu vidi
presne to, co ma schvalovat, nic vic. Dashboard panel se navic
periodicky obnovuje (viz admin.html), takze nove vznikle polozky se
objevi "ihned" bez nutnosti reloadu.

Aktivace: `import approvals` na konci app.py (stejny vzor jako ostatni
moduly).
"""

from flask import jsonify

from app import (
    app, get_conn, require_permission, current_user, has_permission, log_audit,
    _reorder_sync_from_stock, staff_required,
)


@app.get("/api/admin/approvals")
@staff_required
def approvals_overview():
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): drivejsi rucni
    # kontrola tu overovala jen "je prihlasen", ne "je to admin panel role" -
    # bezny e-shop zakaznik (role='user' z /api/auth/register) tak prosel a
    # videl sekci "reorder" (viz nize), ktera NEMA has_permission filtr
    # (zamerne, "kazdy prihlaseny uzivatel ADMIN PANELU" - myslen staff,
    # ne zakaznik). @staff_required dela presne tuhle dvojici kontrol
    # (prihlaseni + role in PERMISSION_ROLES) - QA nalez (2026-09-05)
    # doporucil dekorator misto rucni kopie stejne logiky. current_user()
    # tu ale porad potreba je - has_permission(user, ...) nize overuje
    # jemnejsi opravneni per-sekce, ne jen "je to staff".
    user = current_user()
    sections = {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Robert 2026-08: "nevyrizene polozky k objednani (sestava k
            # objednani) nech se ukaze kazdemu na dashboardu" - ZADNY
            # permission filtr (na rozdil od ostatnich sekci), vidi to
            # kazdy prihlaseny uzivatel admin panelu. Sync ze skladu
            # stejne jako v GET /api/shop/reorder-items, at je prehled
            # aktualni i kdyz nikdo neotevrel zalozku Sestava k objednani.
            _reorder_sync_from_stock(cur)
            conn.commit()
            cur.execute(
                "SELECT r.id, r.product_id, p.sku, p.name, p.unit, r.qty_needed, r.status, r.created_at "
                "FROM shop_reorder_items r JOIN shop_products p ON p.id = r.product_id "
                "ORDER BY r.qty_needed DESC LIMIT 50"
            )
            rows = cur.fetchall()
            if rows:
                sections["reorder"] = {
                    "label": "Nevyřízené položky k objednání (sestava k objednání)",
                    "tab": "reorder",
                    "items": [
                        # product_id navic k id: sestava k objednani nema
                        # detail RADKU, klik na polozku otevira skladovou
                        # kartu PRODUKTU (openStockCardModalById), stejne
                        # jako klik na radek primo v te zalozce.
                        {"id": r["id"], "product_id": r["product_id"],
                         "title": f'{r["sku"]} – {r["name"]} ({r["qty_needed"]} {r["unit"] or "ks"})',
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows
                    ],
                }
            if has_permission(user, "nakupni_objednavky", "upravit"):
                cur.execute(
                    "SELECT id, po_number, supplier_name, total_czk, created_at "
                    "FROM shop_purchase_orders WHERE status='navrh' ORDER BY id DESC LIMIT 50"
                )
                rows = cur.fetchall()
                sections["purchase_orders"] = {
                    "label": "Nákupní objednávky ke schválení (návrh)",
                    "tab": "purchaseorders",
                    "items": [
                        {"id": r["id"], "title": f'{r["po_number"]} – {r["supplier_name"] or "bez dodavatele"}',
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows
                    ],
                }
            if has_permission(user, "objednavky", "upravit"):
                cur.execute(
                    "SELECT id, order_number, customer_name, created_at "
                    "FROM shop_orders WHERE status='nova' ORDER BY id DESC LIMIT 50"
                )
                rows = cur.fetchall()
                sections["orders"] = {
                    "label": "Nové objednávky k potvrzení",
                    "tab": "orders",
                    "items": [
                        {"id": r["id"], "title": f'{r["order_number"]} – {r["customer_name"] or ""}',
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows
                    ],
                }
            if has_permission(user, "nabidky", "upravit"):
                cur.execute(
                    "SELECT id, quote_number, client_label, title, created_at "
                    "FROM crm_quotes WHERE approval_status='ceka_schvaleni' ORDER BY id DESC LIMIT 50"
                )
                rows = cur.fetchall()
                sections["quotes"] = {
                    "label": "Nabídky ke schválení",
                    # Nabidky jsou od 2026-08-05 opet vlastni polozka hlavniho leveho panelu
                    "tab": "quotes",
                    "approve_url": "/api/admin/crm/quotes/{id}/approve",
                    "items": [
                        {"id": r["id"], "title": f'RM{r["quote_number"]} – {r["client_label"] or r["title"] or ""}',
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows
                    ],
                }
            if has_permission(user, "doklady", "upravit"):
                cur.execute(
                    "SELECT d.id, d.document_number, d.document_type, d.total_with_vat_czk, d.created_at "
                    "FROM shop_documents d WHERE d.approval_status='ceka_schvaleni' ORDER BY d.id DESC LIMIT 50"
                )
                rows = cur.fetchall()
                sections["documents"] = {
                    "label": "Doklady ke schválení",
                    "tab": "documents",
                    "approve_url": "/api/admin/documents/{id}/approve",
                    "items": [
                        {"id": r["id"],
                         "title": f'{r["document_number"]} ({r["document_type"]}) – {r["total_with_vat_czk"]} Kč',
                         "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                        for r in rows
                    ],
                }
            # Robert 2026-08-17 (pres bot3): prijate doklady/faktury z
            # e-mailu (viz api/incoming_documents.py) - ZAMERNE
            # samostatna sekce/permission od "doklady" vyse (ty jsou
            # VYSTAVENE eshopem, tohle jsou PRIJATE od dodavatelu).
            if has_permission(user, "prijate_doklady", "upravit"):
                cur.execute(
                    "SELECT id, source_email, source_name, subject, filename, received_at "
                    "FROM incoming_documents WHERE approval_status='ceka_schvaleni' ORDER BY id DESC LIMIT 50"
                )
                rows = cur.fetchall()
                sections["incoming_documents"] = {
                    "label": "Přijaté doklady ke schválení",
                    # POZOR na presny tvar klice: skutecny atribut v
                    # admin.html je data-tab="incomingdocuments" BEZ
                    # pomlcky. Drive tu bylo "incoming-documents", takze
                    # querySelector('.tab-btn[data-tab=...]') vracel null
                    # a odkaz na nadpis teto sekce tise nedelal nic
                    # (nalezeno bot18 2026-09-03; hlida to nove
                    # check_dangling_admin_tab_key v api/qa_checks.py).
                    "tab": "incomingdocuments",
                    "approve_url": "/api/admin/incoming-documents/{id}/approve",
                    "items": [
                        {"id": r["id"],
                         "title": f'{r["source_name"] or r["source_email"]} – {r["filename"] or (r["subject"] or "bez předmětu")}',
                         "created_at": r["received_at"].isoformat() if r["received_at"] else None}
                        for r in rows
                    ],
                }
    finally:
        conn.close()

    total = sum(len(s["items"]) for s in sections.values())
    return jsonify({"sections": sections, "total": total})


@app.post("/api/admin/documents/<int:doc_id>/approve")
@require_permission("doklady", "upravit")
def approve_document(doc_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE shop_documents SET approval_status='schvaleno', approved_by=%s, approved_at=NOW() "
                "WHERE id=%s AND approval_status='ceka_schvaleni'",
                (admin["id"], doc_id),
            )
            if cur.rowcount == 0:
                return jsonify({"error": "Doklad neexistuje nebo už je schválený."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "approve", "document", doc_id, "Doklad schválen")
    # bot5, 2026-10-08 (Robert: e-mail s dokladem jen po schvaleni dokladu): zakaznicky e-mail s PDF se zarazuje AZ TED (pri vystaveni se pro neschvaleny doklad nezaradil), idempotentne, best-effort
    try:
        import documents
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                doc = documents._fetch_document(cur, doc_id)
        finally:
            conn.close()
        if doc and doc["document_type"] in documents.AUTO_EMAIL_DOCUMENT_TYPES:
            documents._auto_email_after_issue(doc["order_id"], doc_id)
    except Exception:
        app.logger.exception("doklad %s je schvaleny, ale e-mail zakaznikovi se nezaradil do fronty", doc_id)
    # bot5, 2026-10-06 (Robert): schvaleny doklad -> e-mail ucetni do FRONTY ke schvaleni (pravidlo 16 beze zmeny), best-effort az po commitu
    try:
        import ucetni_hak
        ucetni_hak.zaradit_vydany(doc_id)
    except Exception:
        app.logger.exception("ucetni hak: doklad %s je schvaleny, ale e-mail ucetni se nezaradil do fronty", doc_id)
    return jsonify({"status": "ok"})


@app.post("/api/admin/crm/quotes/<int:quote_id>/approve")
@require_permission("nabidky", "upravit")
def approve_quote(quote_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE crm_quotes SET approval_status='schvaleno', approved_by=%s, approved_at=NOW() "
                "WHERE id=%s AND approval_status='ceka_schvaleni'",
                (admin["id"], quote_id),
            )
            if cur.rowcount == 0:
                return jsonify({"error": "Nabídka neexistuje nebo už je schválená."}), 404
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "approve", "quote", quote_id, "Nabídka schválena")
    return jsonify({"status": "ok"})
