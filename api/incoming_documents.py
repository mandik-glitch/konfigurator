"""
Prijate ucetni doklady z e-mailu - bot8, 2026-08-17.

Kontext (Robert pres bot3, navazuje na ladeni support_email_sync.py):
"nastavte potrebne k tomu, aby se emaily analyzovali na spam a opravdu
doklady, ktere musime zavadet do ucetnictvi". Rozsireni existujiciho
e-mailoveho tridiciho bodu (viz support_email_sync.py) o TRETI
kategorii vedle "poptavka" (crm.py)/"jine": "doklad" - faktura/dokladovy
PDF prijaty od dodavatele na mandik@logiman.cz.

Zjisteni pri analyze puvodniho problemu ("proc chodi tak malo emailu"):
skutecna prekazka byla, ze Robert e-maily rucne stahuje ze schranky
(a tim je ze serveru odstranuje) rychleji, nez je stihne zachytit
2minutova synchronizace - to reseni je na strane jeho e-mailoveho
klienta (nastaveni "nechat kopii na serveru"), ne v tomhle kodu.
NEZAVISLE na tom ale platilo: i kdyz se doklad-email zachytit stihl,
predchozi (2026-07-31) seed dat klasifikatoru mel 'faktura'/'fakturu'
apod. SILNE svazane s "jine" (0 poptavka, 4-5 jine) - a protoze
odesilatel faktury temer nikdy neni "eshopovy zakaznik"
(_is_shop_related_email), takove e-maily tise mizely bez ulozeni
kamkoli. Tenhle modul tu druhou, nezavislou dernou opravuje.

SCHVALOVACI FRONTA (Robert, tyz den, doplneno pote, co jsem navrhl
primo ukladat do Sdileneho disku): "predpokladam, ze to ukladani
dokladu budeme jeste upresnovat, konkretne: nez se tam ulozi, musim je
odsouhlasit" - detekovany doklad NENI zapsan primo do Sdileneho disku
(shared_drive_files), ale nejdriv do TETO tabulky (incoming_documents,
approval_status='ceka_schvaleni', stejny vzor jako
shop_documents.approval_status/crm_quotes.approval_status - viz
api/approvals.py). Az po rucnim schvaleni (POST .../approve) se soubor
PRESUNE ze stagingu (INCOMING_DOCS_DIR, mimo Sdileny disk) do
Sdileneho disku, do slozky "Faktury a doklady prijate" / <rok> /
<cesky nazev mesice> - podle DATA PRIJETI e-mailu (ne data vystaveni na
fakture), podslozky se zakladaji za chodu (jen kdyz prijde prvni doklad
daneho mesice), ne predem vsechny.

Aktivace: `import incoming_documents` na konec app.py, AZ PO crm/
quotes/drive (pouziva helpery ze vsech tri - quotes.safe_stored_filename/
content_disposition, drive.DRIVE_FILES_DIR konvence, crm.train_words
pro budouci uceni z rucnich oprav).

Endpointy (admin, @require_permission("prijate_doklady", ...) - NOVA
sekce, odlisna od existujici "doklady" (ta patri VYSTAVENYM dokladum
eshopu v api/documents.py, tohle jsou PRIJATE doklady od dodavatelu):
  GET    /api/admin/incoming-documents              - seznam + filtr podle approval_status
  GET    /api/admin/incoming-documents/<id>          - detail (vc. body_text pro rucni posouzeni)
  PUT    /api/admin/incoming-documents/<id>          - rucni doplneni supplier_name/amount_czk/note
  POST   /api/admin/incoming-documents/<id>/approve   - presun do Sdileneho disku (rok/mesic)
  POST   /api/admin/incoming-documents/<id>/reject    - zamitnuti (soubor zustava ve stagingu pro pripadne obnoveni)
  GET    /api/admin/incoming-documents/<id>/download  - nahled/stazeni PRED schvalenim (ze stagingu)
  POST   /api/admin/incoming-documents/<id>/confirm-payment    - rucni potvrzeni shody s odchozi bank. platbou
  POST   /api/admin/incoming-documents/<id>/unconfirm-payment  - zruseni potvrzene shody

Volano i INTERNE ze support_email_sync.py (save_incoming_document) pri
klasifikaci "doklad" - 1 radek na kazdou prilohu e-mailu (0 priloh =
1 radek bez souboru, at se aspon text e-mailu neztrati).

PAROVANI S ODCHOZIMI BANKOVNIMI PLATBAMI (bot10, 2026-08-22, Robert
pres bot3: "z bankovnich vypisu je videt i odchozi platby, sparujme
je s evidovanymi prijatymi doklady, at admin vidi uhradu a nezaplati
omylem duplicitne"): na rozdil od parovani objednavek podle VS
(api/bank_statements.py::match_bank_payments_to_orders - VS je NASE
vlastni cislo, spolehlivy klic), tady VS neni k dispozici (je to
cislo DODAVATELE na jeho fakture, appka ho neextrahuje) - proto
find_payment_matches() nize hleda jen podle CASTKY (amount_czk,
±0,5 Kc toleranca zaokrouhleni) + CASOVEHO OKNA (±30 dni od
received_at). Vysledek je VZDY jen NAVRH k rucnimu potvrzeni
(POST .../confirm-payment) - ZADNE automaticke parovani, admin musi
vizualne porovnat protistranu (counter_account_name) se
supplier_name a rozhodnout sam."""
import os

from flask import request, jsonify, Response

from app import app, get_conn, require_permission, current_user, log_audit
from quotes import safe_stored_filename, content_disposition, PRIVATE_FILES_DIR
from drive import DRIVE_FILES_DIR

INCOMING_DOCS_DIR = os.path.join(PRIVATE_FILES_DIR, "incoming-documents")
os.makedirs(INCOMING_DOCS_DIR, exist_ok=True)

ROOT_FOLDER_NAME = "Faktury a doklady přijaté"
MONTH_NAMES_CZ = (
    "Leden", "Únor", "Březen", "Duben", "Květen", "Červen",
    "Červenec", "Srpen", "Září", "Říjen", "Listopad", "Prosinec",
)


def save_incoming_document(cur, source_email, source_name, subject, body_text, received_at, attachments):
    """Vola support_email_sync.py pro kazdy e-mail klasifikovany jako
    'doklad'. `attachments` je stejny format jako
    support_email_sync._extract_attachments() - seznam (filename,
    content_type, bytes). Prazdny seznam = 1 radek bez souboru (jen
    text e-mailu k rucnimu posouzeni). Vraci pocet vlozenych radku."""
    if not attachments:
        cur.execute(
            "INSERT INTO incoming_documents "
            "(source_email, source_name, subject, body_text, received_at) "
            "VALUES (%s,%s,%s,%s,%s)",
            (source_email, source_name, subject, body_text, received_at),
        )
        return 1
    for filename, content_type, data in attachments:
        stored_filename = safe_stored_filename(filename)
        with open(os.path.join(INCOMING_DOCS_DIR, stored_filename), "wb") as f:
            f.write(data)
        cur.execute(
            "INSERT INTO incoming_documents "
            "(source_email, source_name, subject, body_text, received_at, "
            "filename, stored_filename, content_type, size_bytes) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (source_email, source_name, subject, body_text, received_at,
             filename, stored_filename, content_type, len(data)),
        )
    return len(attachments)


def find_payment_matches(cur, doc):
    """Vraci kandidatni odchozi bankovni platby (bank_transactions,
    direction='vydaj') pro tenhle prijaty doklad - podle CASTKY
    (amount_czk, ±0,5 Kc tolerance) + CASOVEHO OKNA (±30 dni od
    received_at), serazeno podle blizkosti data. Jen NAVRH k rucnimu
    potvrzeni (bot10, 2026-08-22) - zadne automaticke parovani. Vraci
    [] pokud doklad nema vyplnenou castku (nejcastejsi pripad - viz
    modulovy docstring, amount_czk se dnes doplnuje jen rucne)."""
    if doc.get("amount_czk") is None:
        return []
    amount = float(doc["amount_czk"])
    received_at = doc["received_at"]
    cur.execute(
        "SELECT * FROM bank_transactions WHERE direction='vydaj' "
        "AND amount_czk BETWEEN %s AND %s "
        "AND transaction_date BETWEEN DATE_SUB(%s, INTERVAL 30 DAY) AND DATE_ADD(%s, INTERVAL 30 DAY) "
        "ORDER BY ABS(DATEDIFF(transaction_date, %s)) ASC LIMIT 5",
        (amount - 0.5, amount + 0.5, received_at, received_at, received_at),
    )
    return cur.fetchall()


def _serialize_bank_match(row):
    return {
        "id": row["id"],
        "transaction_date": row["transaction_date"].isoformat() if row["transaction_date"] else None,
        "amount_czk": float(row["amount_czk"]) if row["amount_czk"] is not None else None,
        "counter_account_name": row["counter_account_name"],
        "message_for_recipient": row["message_for_recipient"],
        "variable_symbol": row["variable_symbol"],
    }


def _serialize(row, cur=None):
    out = {
        "id": row["id"],
        "source_email": row["source_email"],
        "source_name": row["source_name"],
        "subject": row["subject"],
        "received_at": row["received_at"].isoformat() if row["received_at"] else None,
        "filename": row["filename"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "approval_status": row["approval_status"],
        "supplier_name": row["supplier_name"],
        "amount_czk": float(row["amount_czk"]) if row["amount_czk"] is not None else None,
        "note": row["note"],
        "drive_file_id": row["drive_file_id"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "paid_bank_transaction_id": row.get("paid_bank_transaction_id"),
        "paid_at": row["paid_at"].isoformat() if row.get("paid_at") else None,
    }
    # bot10, 2026-08-22: navrh shody jen kdyz jeste NENI potvrzena a mame
    # castku k porovnani - cur je volitelny (list endpoint ho preda kvuli
    # vykonu jen kdyz ma smysl, viz nize), detail ho preda vzdy.
    if cur is not None and row.get("paid_bank_transaction_id") is None and row.get("amount_czk") is not None:
        out["payment_matches"] = [_serialize_bank_match(m) for m in find_payment_matches(cur, row)]
    else:
        out["payment_matches"] = []
    return out


@app.get("/api/admin/incoming-documents")
@require_permission("prijate_doklady", "zobrazit")
def incoming_documents_list():
    # bot3, 2026-08-20 (Robert: "stejnou filtraci a stylizaci aplikuj na
    # prijate doklady" - vzor prevzaty z Emaily prichozi): pridano
    # hledani/obdobi/razeni vedle stavajicho filtru na stav. Pocty pod
    # zalozkami (status_counts) VEDOME pocitany bez q/date_from/date_to -
    # jinak by se cisla pod zalozkami meritelne menila psanim do
    # vyhledavani, coz je matouci (stejny vzor jako support conversations).
    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    sort = (request.args.get("sort") or "newest").strip()
    where = []
    params = []
    if status:
        where.append("approval_status=%s")
        params.append(status)
    if q:
        like = f"%{q}%"
        where.append("(source_name LIKE %s OR source_email LIKE %s OR subject LIKE %s OR supplier_name LIKE %s)")
        params.extend([like, like, like, like])
    if date_from:
        where.append("received_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("received_at < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(date_to)
    sql = "SELECT * FROM incoming_documents"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY received_at " + ("ASC" if sort == "oldest" else "DESC") + " LIMIT 200"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            cur.execute(
                "SELECT approval_status, COUNT(*) AS c FROM incoming_documents GROUP BY approval_status"
            )
            counts = {r["approval_status"]: r["c"] for r in cur.fetchall()}
            # _serialize s cur MUSI probehnout tady uvnitr (najde payment
            # matches dotazem na bank_transactions) - conn nize se zavira.
            documents = [_serialize(r, cur) for r in rows]
    finally:
        conn.close()
    return jsonify({"documents": documents, "status_counts": counts})


@app.post("/api/admin/incoming-documents/bulk-approve")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_bulk_approve():
    """Hromadne schvaleni (bot3, 2026-08-20) - stejna logika presunu do
    Sdileneho disku jako jednotlivy POST .../approve, jen ve smycce.
    Polozky, ktere uz nejsou 'ceka_schvaleni' (napr. mezitim schvalene/
    zamitnute v jine zalozce), se tise preskoci - vraceny v 'skipped'."""
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    admin = current_user()
    approved, skipped = [], []
    # Zivy nalez z revize kodu (bot3, 2026-09-02): kopie souboru +
    # os.remove(src) jsou NEVRATNE operace na souborovem systemu, ale
    # cely cyklus mel jen JEDEN commit az na konci - selhani u polozky N
    # by vratilo DB zpet, ale soubory 1..N-1 uz byly fyzicky presunute
    # (zdroj smazany, sirotci v cili bez DB zaznamu). Reseni: os.remove()
    # az PO uspesnem commitu (to_remove), a pri vyjimce rollback + uklid
    # jiz vytvorenych kopii v cili (created_dest_paths) - zdrojove
    # soubory se BEHEM cyklu nikdy nemazou, takze opakovane schvaleni po
    # chybe proste projde znovu od zacatku.
    to_remove = []
    created_dest_paths = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for doc_id in ids:
                cur.execute("SELECT * FROM incoming_documents WHERE id=%s", (doc_id,))
                row = cur.fetchone()
                if not row or row["approval_status"] != "ceka_schvaleni":
                    skipped.append(doc_id)
                    continue
                drive_file_id = None
                if row["stored_filename"]:
                    root_id = _get_or_create_folder(cur, ROOT_FOLDER_NAME, None, admin["id"])
                    year_name = str(row["received_at"].year)
                    year_id = _get_or_create_folder(cur, year_name, root_id, admin["id"])
                    month_name = MONTH_NAMES_CZ[row["received_at"].month - 1]
                    month_id = _get_or_create_folder(cur, month_name, year_id, admin["id"])
                    src_path = os.path.join(INCOMING_DOCS_DIR, row["stored_filename"])
                    dest_stored_filename = safe_stored_filename(row["filename"])
                    dest_path = os.path.join(DRIVE_FILES_DIR, dest_stored_filename)
                    with open(src_path, "rb") as f_in, open(dest_path, "wb") as f_out:
                        f_out.write(f_in.read())
                    created_dest_paths.append(dest_path)
                    cur.execute(
                        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (month_id, row["filename"], dest_stored_filename, row["content_type"], row["size_bytes"], admin["id"]),
                    )
                    drive_file_id = cur.lastrowid
                    to_remove.append(src_path)
                cur.execute(
                    "UPDATE incoming_documents SET approval_status='schvaleno', drive_file_id=%s, "
                    "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
                    (drive_file_id, admin["id"], doc_id),
                )
                approved.append(doc_id)
        conn.commit()
    except Exception:
        conn.rollback()
        for p in created_dest_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        return jsonify({
            "error": f"Schválení selhalo, žádná změna nebyla uložena ({len(approved)} z {len(ids)} rozpracováno) - "
                     "zdrojové soubory zůstávají, zkuste to prosím znovu.",
        }), 500
    finally:
        conn.close()
    for src_path in to_remove:
        try:
            os.remove(src_path)
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"[incoming_documents_bulk_approve] smazání zdrojového souboru selhalo ({src_path}): {e}")
    for doc_id in approved:
        log_audit(admin["id"], "approve", "incoming_document", doc_id, None)
        # bot5, 2026-10-06 (Robert): schvaleny doklad -> e-mail ucetni do FRONTY ke schvaleni (pravidlo 16 beze zmeny), best-effort az po commitu
        try:
            import ucetni_hak
            ucetni_hak.zaradit_prijaty(doc_id)
        except Exception:
            app.logger.exception("ucetni hak: prijaty doklad %s je schvaleny, ale e-mail ucetni se nezaradil do fronty", doc_id)
    return jsonify({"status": "ok", "approved": approved, "skipped": skipped})


@app.post("/api/admin/incoming-documents/bulk-reject")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_bulk_reject():
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    admin = current_user()
    rejected, skipped = [], []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for doc_id in ids:
                cur.execute("SELECT approval_status FROM incoming_documents WHERE id=%s", (doc_id,))
                row = cur.fetchone()
                if not row or row["approval_status"] != "ceka_schvaleni":
                    skipped.append(doc_id)
                    continue
                cur.execute(
                    "UPDATE incoming_documents SET approval_status='zamitnuto', "
                    "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
                    (admin["id"], doc_id),
                )
                rejected.append(doc_id)
        conn.commit()
    finally:
        conn.close()
    for doc_id in rejected:
        log_audit(admin["id"], "reject", "incoming_document", doc_id, None)
    return jsonify({"status": "ok", "rejected": rejected, "skipped": skipped})


@app.get("/api/admin/incoming-documents/<int:doc_id>")
@require_permission("prijate_doklady", "zobrazit")
def incoming_documents_detail(doc_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM incoming_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Doklad nenalezen."}), 404
            out = _serialize(row, cur)
    finally:
        conn.close()
    out["body_text"] = row["body_text"]
    return jsonify(out)


@app.put("/api/admin/incoming-documents/<int:doc_id>")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_update(doc_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "supplier_name" in body:
        fields.append("supplier_name=%s")
        params.append((body.get("supplier_name") or "").strip() or None)
    if "amount_czk" in body:
        try:
            params.append(float(body["amount_czk"]) if body["amount_czk"] not in (None, "") else None)
        except (TypeError, ValueError):
            return jsonify({"error": "Částka musí být číslo."}), 400
        fields.append("amount_czk=%s")
    if "note" in body:
        fields.append("note=%s")
        params.append((body.get("note") or "").strip() or None)
    if not fields:
        return jsonify({"error": "Nic k uložení."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM incoming_documents WHERE id=%s", (doc_id,))
            if not cur.fetchone():
                return jsonify({"error": "Doklad nenalezen."}), 404
            cur.execute(f"UPDATE incoming_documents SET {', '.join(fields)} WHERE id=%s", (*params, doc_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


def _get_or_create_folder(cur, name, parent_folder_id, admin_id):
    cur.execute(
        "SELECT id FROM shared_drive_folders WHERE name=%s AND "
        + ("parent_folder_id=%s" if parent_folder_id else "parent_folder_id IS NULL"),
        (name, parent_folder_id) if parent_folder_id else (name,),
    )
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
        (parent_folder_id, name, admin_id),
    )
    return cur.lastrowid


@app.post("/api/admin/incoming-documents/<int:doc_id>/approve")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_approve(doc_id):
    admin = current_user()
    # Zivy nalez z revize kodu (bot3, 2026-09-02) - stejny jako bulk-approve
    # vyse: os.remove(src_path) az PO uspesnem commitu, pri vyjimce
    # rollback + uklid uz vytvorene kopie v cili (sirotek bez DB zaznamu),
    # zdrojovy soubor se nikdy behem transakce nemaze -> opakovane
    # schvaleni po chybe projde znovu.
    src_path = None
    dest_path = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM incoming_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Doklad nenalezen."}), 404
            if row["approval_status"] != "ceka_schvaleni":
                return jsonify({"error": "Doklad už byl vyřízen."}), 400

            drive_file_id = None
            if row["stored_filename"]:
                # Robert 2026-08-17: "musi se ukladat podle mesicu a roku,
                # 2026/srpen atd." - podslozky <rok>/<cesky nazev mesice>
                # podle DATA PRIJETI (ne vystaveni), zalozene za chodu.
                root_id = _get_or_create_folder(cur, ROOT_FOLDER_NAME, None, admin["id"])
                year_name = str(row["received_at"].year)
                year_id = _get_or_create_folder(cur, year_name, root_id, admin["id"])
                month_name = MONTH_NAMES_CZ[row["received_at"].month - 1]
                month_id = _get_or_create_folder(cur, month_name, year_id, admin["id"])

                src_path = os.path.join(INCOMING_DOCS_DIR, row["stored_filename"])
                # Nova nahodna stored_filename na cilove strane (stejna
                # konvence jako drive.py/quotes.py - zadne sdileni tokenu
                # mezi staging a Sdilenym diskem, cisty prevod vlastnictvi).
                dest_stored_filename = safe_stored_filename(row["filename"])
                dest_path = os.path.join(DRIVE_FILES_DIR, dest_stored_filename)
                with open(src_path, "rb") as f_in, open(dest_path, "wb") as f_out:
                    f_out.write(f_in.read())
                cur.execute(
                    "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (month_id, row["filename"], dest_stored_filename, row["content_type"], row["size_bytes"], admin["id"]),
                )
                drive_file_id = cur.lastrowid

            cur.execute(
                "UPDATE incoming_documents SET approval_status='schvaleno', drive_file_id=%s, "
                "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
                (drive_file_id, admin["id"], doc_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        if dest_path:
            try:
                os.remove(dest_path)
            except OSError:
                pass
        return jsonify({"error": "Schválení selhalo, žádná změna nebyla uložena - zkuste to prosím znovu."}), 500
    finally:
        conn.close()
    if src_path:
        try:
            os.remove(src_path)
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"[incoming_documents_approve] smazání zdrojového souboru selhalo ({src_path}): {e}")
    log_audit(admin["id"], "approve", "incoming_document", doc_id, None)
    # bot5, 2026-10-06 (Robert): schvaleny doklad -> e-mail ucetni do FRONTY ke schvaleni (pravidlo 16 beze zmeny), best-effort az po commitu
    try:
        import ucetni_hak
        ucetni_hak.zaradit_prijaty(doc_id)
    except Exception:
        app.logger.exception("ucetni hak: prijaty doklad %s je schvaleny, ale e-mail ucetni se nezaradil do fronty", doc_id)
    return jsonify({"status": "ok", "drive_file_id": drive_file_id})


@app.post("/api/admin/incoming-documents/<int:doc_id>/reject")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_reject(doc_id):
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, approval_status FROM incoming_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Doklad nenalezen."}), 404
            if row["approval_status"] != "ceka_schvaleni":
                return jsonify({"error": "Doklad už byl vyřízen."}), 400
            # Soubor VEDOME zustava ve stagingu (ne mazan) - jednoduse
            # obnovitelne rucni prehodnoceni ("Toto je doklad" opacnym
            # smerem zatim neni endpoint, ale soubor na disku prezije,
            # aby to slo doresit rucne v DB, kdyby se admin spletl).
            cur.execute(
                "UPDATE incoming_documents SET approval_status='zamitnuto', "
                "reviewed_by=%s, reviewed_at=NOW() WHERE id=%s",
                (admin["id"], doc_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "reject", "incoming_document", doc_id, None)
    return jsonify({"status": "ok"})


@app.get("/api/admin/incoming-documents/<int:doc_id>/download")
@require_permission("prijate_doklady", "zobrazit")
def incoming_documents_download(doc_id):
    """Nahled/stazeni jen PRED schvalenim (ze stagingu) - po schvaleni
    uz soubor zije ve Sdilenem disku pod NOVYM stored_filename (viz
    approve() vyse, ktery stary staging soubor po presunu smaze), stare
    stored_filename v teto tabulce uz tedy nikam neukazuje. Po schvaleni
    pouzij existujici /api/admin/drive/files/<drive_file_id>/download."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename, stored_filename, content_type, approval_status, drive_file_id FROM incoming_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Doklad nenalezen."}), 404
    if row["approval_status"] == "schvaleno":
        return jsonify({"error": "Doklad už je ve Sdíleném disku.", "drive_file_id": row["drive_file_id"]}), 409
    if not row["stored_filename"]:
        return jsonify({"error": "Doklad nemá přiložený soubor."}), 404
    path = os.path.join(INCOMING_DOCS_DIR, row["stored_filename"])
    if not os.path.exists(path):
        return jsonify({"error": "Soubor na disku chybí."}), 404
    with open(path, "rb") as f:
        data = f.read()
    return Response(
        data,
        mimetype=row["content_type"] or "application/octet-stream",
        headers={"Content-Disposition": content_disposition(row["filename"] or "doklad")},
    )


@app.post("/api/admin/incoming-documents/<int:doc_id>/confirm-payment")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_confirm_payment(doc_id):
    """Rucni potvrzeni shody s odchozi bankovni platbou (bot10,
    2026-08-22) - VZDY explicitni akce admina, nikdy automaticky (VS
    tady neni spolehlivy klic, viz modulovy docstring). Body:
    {"bank_transaction_id": <id>} - musi byt jedna z hodnot vracenych
    v payment_matches (nebo jakykoli existujici direction='vydaj'
    zaznam - neomezujeme na presne navrhovane, admin muze najit shodu
    i mimo automaticky navrh napr. rucnim hledanim v Bankovnich
    vypisech)."""
    body = request.get_json(silent=True) or {}
    bank_transaction_id = body.get("bank_transaction_id")
    if not bank_transaction_id:
        return jsonify({"error": "Chybí bank_transaction_id."}), 400
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM incoming_documents WHERE id=%s", (doc_id,))
            if not cur.fetchone():
                return jsonify({"error": "Doklad nenalezen."}), 404
            cur.execute(
                "SELECT id, transaction_date FROM bank_transactions WHERE id=%s AND direction='vydaj'",
                (bank_transaction_id,),
            )
            tx = cur.fetchone()
            if not tx:
                return jsonify({"error": "Bankovní platba nenalezena (nebo není odchozí)."}), 404
            cur.execute(
                "UPDATE incoming_documents SET paid_bank_transaction_id=%s, paid_at=%s WHERE id=%s",
                (tx["id"], tx["transaction_date"], doc_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "confirm_payment", "incoming_document", doc_id, str(bank_transaction_id))
    return jsonify({"status": "ok"})


@app.post("/api/admin/incoming-documents/<int:doc_id>/unconfirm-payment")
@require_permission("prijate_doklady", "upravit")
def incoming_documents_unconfirm_payment(doc_id):
    """Zruseni drive potvrzene shody (oprava omylu) - bot10, 2026-08-22."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM incoming_documents WHERE id=%s", (doc_id,))
            if not cur.fetchone():
                return jsonify({"error": "Doklad nenalezen."}), 404
            cur.execute(
                "UPDATE incoming_documents SET paid_bank_transaction_id=NULL, paid_at=NULL WHERE id=%s",
                (doc_id,),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "unconfirm_payment", "incoming_document", doc_id, None)
    return jsonify({"status": "ok"})
