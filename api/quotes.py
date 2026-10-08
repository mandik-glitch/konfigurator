"""
Nabidky (obchodni cenove nabidky) - bot5, 2026-08-01.

Robert: "priprav plan pro strukturu nabidek ... kazdou nabidku chci mit
vedenou jako adresar a ten muze mit dalsi slozky pod slozky protoze
jedne nabidky se muze tykat mnoho ruznych typu dokladu" + cislovani
"ctyriciferne cislo a zatim RM zatim nazev klienta" + "kdyz vznikne
adresar pro konkretni poptavku ulozi se do nej vsechny prilohy z toho
daneho e-mailu" + "zaroven ... i pripadne budouci prilohy jinych
e-mailu vlakno".

Nabidka (crm_quotes) je korenovy "adresar", ktery muze mit libovolne
vnorene podslozky (crm_quote_folders, self-referential jako
content_categories.parent_id) a v nich soubory LIBOVOLNEHO typu
(crm_quote_files - PDF/DOCX/XLSX/JPG/vykresy... NE jen obrazky jako
gallery_items.py).

Vznika AUTOMATICKY (viz crm.py::_apply_lead_update - prechod poptavky
do stavu 'nabidnuto' zavola get_or_create_quote_for_lead()) i RUCNE
(POST /api/admin/crm/quotes, i bez navazane poptavky, nebo POST
/api/admin/crm/leads/<id>/create-quote v crm.py). Cislovani:
QUOTE_PREFIX ("RM", Python konstanta - "zatim") + ctyrmistne cislo z
crm_quote_sequence (FOR UPDATE zamek, mirror
documents._next_document_number).

E-mailove prilohy (support_email_sync.py) se ukladaji DVOUUROVNOVE:
PRIMO do Drive slozky dane poptavky (shared_drive_files, viz
crm.py::ensure_lead_drive_folder - bot10 2026-08-22, Robert: "prilohy
schvalenych poptavek se ukladaji rovnou do slozek v Poptavka >
nabidka"; puvodne to bylo crm_lead_message_attachments/
LEAD_ATTACHMENTS_DIR - stare radky tam mohou jeste existovat z doby
PRED touhle zmenou, viz lead_attachment_filenames()/
remove_lead_attachment_files() nize, ktere se o ne poradi) VZDY pri
prijmu e-mailu patriciho k poptavce (bez ohledu na to, jestli uz
nabidka existuje), a KOPIE do crm_quote_files v okamziku, kdy nabidka
existuje/vznikne - viz save_lead_attachment()/
get_or_create_quote_for_lead() nize (kopiruje z OBOU moznych zdroju,
stary i novy). Duvod dvouurovnove struktury: crm_admin_lead_reject()
(v crm.py) dela fyzicke DELETE FROM crm_leads (kaskaduje na
crm_lead_messages), ale nabidka MA prezit (crm_quotes.lead_id je ON
DELETE SET NULL) i Drive slozka MA prezit (crm_leads.drive_folder_id
je take ON DELETE SET NULL) - proto Quote potrebuje VLASTNI
nezavislou kopii souboru, ne live odkaz na zpravu/slozku.

DULEZITE: soubory NEJSOU v UPLOAD_DIR (webapp/content-files) - cely
adresar webapp/ je nginxem servirovan STATICKY (viz
/etc/nginx/sites-enabled/konfigurator, "location / { root
/opt/konfigurator/webapp; ... }"). Pro obchodni doklady/e-mailove
prilohy se citlivymi udaji to neni dost (na rozdil od gallery_items.py,
kde je to "tajne" jen diky nahodnemu tokenu v nazvu). Uklada se do
PRIVATE_FILES_DIR (/opt/konfigurator/private-files/, MIMO nginx
root/alias) - stazeni jde jen pres autentizovany GET
.../files/<id>/download nize, VZDY Content-Disposition: attachment
(nikdy inline) - i kdyby nekdo nahral .html/.svg soubor, nesmi se
vykreslit v prohlizeci jako soucast aplikace (pojistka proti stored XSS).

Endpointy (admin, @require_permission("nabidky", ...)):
  GET/POST        /api/admin/crm/quotes                   - seznam + rucni zalozeni
  GET/PUT          /api/admin/crm/quotes/<id>              - detail (strom slozek) + editace
  POST/PUT/DELETE  /api/admin/crm/quotes/<id>/folders[/<fid>]
  POST/PUT/DELETE  /api/admin/crm/quotes/<id>/files[/<fid>]
  GET              /api/admin/crm/quotes/<id>/files/<fid>/download

("Vytvorit nabidku" rucni trigger z CRM detailu -
POST /api/admin/crm/leads/<lead_id>/create-quote - zije v crm.py,
protoze pracuje primarne s leadem; jen vola get_or_create_quote_for_lead
nize.)

Aktivace: `import quotes` na konec app.py, AZ PO `import crm` (crm.py
na tento modul primo vola).
"""
import os
import re
import shutil
import sys
import urllib.parse

from flask import request, jsonify, Response

from app import app, get_conn, current_user, require_permission, log_audit, get_pagination_args, paginated_query

QUOTE_PREFIX = "Logiman"  # Robert 2026-08-06: "Cislovani nabidek zmen na Logiman00xx" (drive "RM")

PRIVATE_FILES_DIR = os.environ.get("PRIVATE_FILES_DIR", "/opt/konfigurator/private-files")
QUOTE_FILES_DIR = os.path.join(PRIVATE_FILES_DIR, "crm-quotes")
LEAD_ATTACHMENTS_DIR = os.path.join(PRIVATE_FILES_DIR, "crm-lead-attachments")
os.makedirs(QUOTE_FILES_DIR, exist_ok=True)
os.makedirs(LEAD_ATTACHMENTS_DIR, exist_ok=True)


def safe_stored_filename(original_filename):
    """Nazev na disku je CISTE nahodny token (na rozdil od
    gallery_items._seo_slug, ktery do nazvu vklada slugifikovany
    original) - tyhle soubory nikdy nejsou verejna URL, takze SEO
    nema smysl, a cisty token vylucuje jakekoli problemy s
    neocekavanymi znaky v puvodnim nazvu (path traversal apod)."""
    _, ext = os.path.splitext(original_filename or "")
    ext = re.sub(r"[^a-zA-Z0-9]", "", ext)[:10].lower()
    token = os.urandom(16).hex()
    return f"{token}.{ext}" if ext else token


def content_disposition(filename):
    """attachment (nikdy inline, viz modulovy docstring) s podporou
    neascii nazvu (RFC 6266 filename* vedle ascii fallbacku filename)."""
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c != '"' else "_" for c in (filename or "")) or "soubor"
    encoded = urllib.parse.quote(filename or "soubor")
    return f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'


def _next_quote_number(cur):
    """Mirror documents._next_document_number() - FOR UPDATE zamek na
    jedinem radku pocitadla, atomicke v ramci volajici transakce."""
    cur.execute("SELECT next_number FROM crm_quote_sequence WHERE id=1 FOR UPDATE")
    n = cur.fetchone()["next_number"]
    cur.execute("UPDATE crm_quote_sequence SET next_number=next_number+1 WHERE id=1")
    return f"{n:04d}"


def lead_attachment_filenames(cur, lead_id):
    """Vraci stored_filename vsech priloh k danemu leadu - MUSI se
    zavolat PRED DELETE FROM crm_leads (crm.py::crm_admin_lead_reject),
    protoze ten kaskaduje na crm_lead_messages i
    crm_lead_message_attachments (DB radky zaniknou, ale fyzicke soubory
    na disku ne - bez tohohle by zustaly navzdy osirele)."""
    cur.execute(
        "SELECT a.stored_filename FROM crm_lead_message_attachments a "
        "JOIN crm_lead_messages m ON m.id = a.message_id WHERE m.lead_id=%s",
        (lead_id,),
    )
    return [r["stored_filename"] for r in cur.fetchall()]


def remove_lead_attachment_files(filenames):
    """Volat AZ PO commitu DELETE FROM crm_leads (mirror
    gallery_items.delete_items_for_owner) se seznamem z
    lead_attachment_filenames() vyse."""
    for fn in filenames:
        try:
            os.remove(os.path.join(LEAD_ATTACHMENTS_DIR, fn))
        except OSError:
            pass


def _copy_attachment_to_quote(cur, quote_id, attachment_row, folder_id=None,
                               source_dir=None, source_message_id=None):
    """Fyzicka kopie (ne presun) prilohy do QUOTE_FILES_DIR - original
    zustava na svem miste (bud crm_lead_message_attachments/
    LEAD_ATTACHMENTS_DIR - stary zpusob pred bot10 2026-08-22, nebo
    shared_drive_files/drive.DRIVE_FILES_DIR - novy zpusob, viz
    save_lead_attachment() nize), nabidka dostane vlastni nezavislou
    kopii (musi prezit i smazani leadu, viz modulovy docstring).
    `source_dir` umoznuje volajicimu urcit, odkud se kopiruje (bez toho
    default LEAD_ATTACHMENTS_DIR pro zpetnou kompatibilitu se starymi
    prilohami). `source_message_id` prebiji `attachment_row["message_id"]"
    (shared_drive_files tenhle sloupec vubec nema)."""
    src_dir = source_dir if source_dir is not None else LEAD_ATTACHMENTS_DIR
    src = os.path.join(src_dir, attachment_row["stored_filename"])
    dest_stored = safe_stored_filename(attachment_row["filename"])
    dest = os.path.join(QUOTE_FILES_DIR, dest_stored)
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        print(f"[quotes] kopie prilohy selhala ({attachment_row['stored_filename']}): {e}")
        return
    msg_id = source_message_id if source_message_id is not None else attachment_row.get("message_id")
    cur.execute(
        "INSERT INTO crm_quote_files (quote_id, folder_id, filename, stored_filename, content_type, size_bytes, "
        "source, source_message_id) VALUES (%s,%s,%s,%s,%s,%s,'email_attachment',%s)",
        (quote_id, folder_id, attachment_row["filename"], dest_stored, attachment_row["content_type"],
         attachment_row["size_bytes"], msg_id),
    )


def get_or_create_quote_for_lead(cur, lead, created_by=None):
    """Idempotentni - bezpecne volat opakovane (i pri opakovanem ulozeni
    stejneho stavu pres bulk-status). Prvni volani pro dany lead
    zalozi nabidku a rovnou zkopiruje VSECHNY dosavadni prilohy jeho
    e-mailu (viz "kdyz vznikne adresar ... ulozi se do nej vsechny
    prilohy z toho daneho e-mailu"). Kopiruje ze DVOU moznych zdroju
    (bot10 2026-08-22): stare crm_lead_message_attachments (pred
    zavedenim Drive slozky) i nove shared_drive_files v Drive slozce
    poptavky (po zavedeni) - lead muze mit prilohy z obou obdobi."""
    cur.execute(
        "SELECT id FROM crm_quotes WHERE lead_id=%s ORDER BY created_at DESC LIMIT 1",
        (lead["id"],),
    )
    row = cur.fetchone()
    if row:
        return row["id"]

    quote_number = _next_quote_number(cur)
    client_label = lead.get("company_name") or lead.get("contact_name") or lead.get("contact_email")
    cur.execute(
        "INSERT INTO crm_quotes (lead_id, customer_id, quote_number, client_label, contact_email, title, created_by) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (lead["id"], lead.get("customer_id"), quote_number, client_label,
         lead.get("contact_email"), lead.get("subject"), created_by),
    )
    quote_id = cur.lastrowid

    cur.execute(
        "SELECT a.* FROM crm_lead_message_attachments a "
        "JOIN crm_lead_messages m ON m.id = a.message_id "
        "WHERE m.lead_id=%s ORDER BY a.created_at ASC, a.id ASC",
        (lead["id"],),
    )
    for a in cur.fetchall():
        _copy_attachment_to_quote(cur, quote_id, a)

    if lead.get("drive_folder_id"):
        import drive
        cur.execute(
            "SELECT * FROM shared_drive_files WHERE folder_id=%s ORDER BY created_at ASC, id ASC",
            (lead["drive_folder_id"],),
        )
        for f in cur.fetchall():
            _copy_attachment_to_quote(cur, quote_id, f, source_dir=drive.DRIVE_FILES_DIR, source_message_id=None)
    return quote_id


def save_lead_attachment(cur, message_id, lead_id, filename, content_type, data):
    """Vola support_email_sync.py (a inquiries.py) pro KAZDOU prilohu
    KAZDEHO e-mailu/formulare klasifikovaneho jako 'poptavka', bez
    ohledu na to, jestli uz nabidka existuje. UPRAVENO bot10 2026-08-22
    (Robert: "prilohy schvalenych poptavek se ukladaji rovnou do slozek
    v Poptavka > nabidka") - priloha uz nejde do soukromeho
    LEAD_ATTACHMENTS_DIR/crm_lead_message_attachments (puvodni reseni
    BUG1 z rana tehoz dne), ale PRIMO do Drive slozky dane poptavky
    (crm.ensure_lead_drive_folder() + shared_drive_files). Pokud lead uz
    nabidku MA, priloha se rovnou zkopiruje i tam - reseni "zaroven ...
    i pripadne budouci prilohy jinych e-mailu vlakno"."""
    import crm
    import drive
    folder_id = crm.ensure_lead_drive_folder(cur, lead_id)
    if folder_id is None:
        # bot5, 2026-09-26 (incident lead 117 "kde je ten zakres?"): drive
        # z libovolneho duvodu vratil None (chybejici/prejmenovany koren -
        # viz crm.LEAD_DRIVE_ROOT_FOLDER_NAME), TOHLE misto ho drive
        # doposud TICHE polykalo a vlozilo osirely radek s folder_id=NULL,
        # ktery pak v adminu (panel Fotky u poptavky) nesel nikdy najit.
        # Priloha se porad ULOZI (nechceme ztratit zakaznikovu zpravu jen
        # kvuli chybe ve slozkach), ale hlasite - at je to videt v
        # journalctlu, ne aby si toho nekdo vsiml az za mesic ve WHERE
        # folder_id IS NULL.
        print(f"[quotes] save_lead_attachment: ensure_lead_drive_folder(lead_id={lead_id}) "
              f"vratilo None - priloha '{filename}' se ulozi BEZ Drive slozky (folder_id=NULL), "
              f"nebude videt v panelu Fotky.", file=sys.stderr)
    stored_filename = safe_stored_filename(filename)
    with open(os.path.join(drive.DRIVE_FILES_DIR, stored_filename), "wb") as fh:
        fh.write(data)
    cur.execute(
        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes) "
        "VALUES (%s,%s,%s,%s,%s)",
        (folder_id, filename, stored_filename, content_type, len(data)),
    )
    drive_file_id = cur.lastrowid

    cur.execute("SELECT id FROM crm_quotes WHERE lead_id=%s ORDER BY created_at DESC LIMIT 1", (lead_id,))
    quote = cur.fetchone()
    if quote:
        cur.execute("SELECT * FROM shared_drive_files WHERE id=%s", (drive_file_id,))
        _copy_attachment_to_quote(cur, quote["id"], cur.fetchone(), source_dir=drive.DRIVE_FILES_DIR, source_message_id=None)


def _serialize_quote(row):
    return {
        "id": row["id"], "lead_id": row["lead_id"], "customer_id": row["customer_id"],
        "order_id": row.get("order_id"),
        "quote_number": f"{QUOTE_PREFIX}{row['quote_number']}",
        "client_label": row["client_label"], "contact_email": row["contact_email"],
        "title": row["title"], "created_by": row["created_by"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_folder(row):
    return {
        "id": row["id"], "quote_id": row["quote_id"], "parent_folder_id": row["parent_folder_id"],
        "name": row["name"], "sort_order": row["sort_order"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _serialize_file(row):
    return {
        "id": row["id"], "quote_id": row["quote_id"], "folder_id": row["folder_id"],
        "filename": row["filename"], "content_type": row["content_type"], "size_bytes": row["size_bytes"],
        "source": row["source"], "uploaded_by": row["uploaded_by"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _get_quote(cur, quote_id):
    cur.execute("SELECT * FROM crm_quotes WHERE id=%s", (quote_id,))
    return cur.fetchone()


@app.get("/api/admin/crm/quotes")
@require_permission("nabidky", "zobrazit")
def quotes_admin_list():
    q = (request.args.get("q") or "").strip()
    where, params = [], []
    if q:
        where.append("(quote_number LIKE %s OR client_label LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])
    page, page_size = get_pagination_args(default_page_size=50)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            base_sql = "SELECT * FROM crm_quotes"
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            rows, total = paginated_query(cur, base_sql, where_sql, params, " ORDER BY created_at DESC", page, page_size)
    finally:
        conn.close()
    resp = {"quotes": [_serialize_quote(r) for r in rows]}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.post("/api/admin/crm/quotes")
@require_permission("nabidky", "vytvorit")
def quotes_admin_create():
    """Rucni zalozeni - S lead_id (idempotentni, mirror auto-trigger)
    nebo BEZ nej (samostatna nabidka, client_label povinny rucne)."""
    admin = current_user()
    body = request.get_json(silent=True) or {}
    lead_id = body.get("lead_id")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if lead_id:
                cur.execute("SELECT * FROM crm_leads WHERE id=%s", (lead_id,))
                lead = cur.fetchone()
                if not lead:
                    return jsonify({"error": "Poptávka neexistuje."}), 404
                quote_id = get_or_create_quote_for_lead(cur, lead, created_by=admin["id"])
            else:
                client_label = (body.get("client_label") or "").strip()
                if not client_label:
                    return jsonify({"error": "Název klienta je povinný."}), 400
                quote_number = _next_quote_number(cur)
                cur.execute(
                    "INSERT INTO crm_quotes (quote_number, client_label, title, created_by) VALUES (%s,%s,%s,%s)",
                    (quote_number, client_label, (body.get("title") or "").strip() or None, admin["id"]),
                )
                quote_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "create", "crm_quote", quote_id, body.get("client_label") or f"lead#{lead_id}")
    return jsonify({"status": "ok", "id": quote_id}), 201


@app.get("/api/admin/crm/quotes/<int:quote_id>")
@require_permission("nabidky", "zobrazit")
def quotes_admin_detail(quote_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            quote = _get_quote(cur, quote_id)
            if not quote:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            cur.execute("SELECT * FROM crm_quote_folders WHERE quote_id=%s ORDER BY sort_order, name", (quote_id,))
            folders = cur.fetchall()
            cur.execute("SELECT * FROM crm_quote_files WHERE quote_id=%s ORDER BY sort_order, filename", (quote_id,))
            files = cur.fetchall()
            order_info = None
            if quote.get("order_id"):
                cur.execute(
                    "SELECT id, order_number, customer_name, status, total_czk FROM shop_orders WHERE id=%s",
                    (quote["order_id"],),
                )
                order_info = cur.fetchone()
                if order_info and order_info.get("total_czk") is not None:
                    order_info["total_czk"] = float(order_info["total_czk"])
    finally:
        conn.close()

    by_parent = {}
    for f in folders:
        by_parent.setdefault(f["parent_folder_id"], []).append(f)
    files_by_folder = {}
    for fl in files:
        files_by_folder.setdefault(fl["folder_id"], []).append(fl)

    def build(parent_id):
        out = []
        for f in by_parent.get(parent_id, []):
            out.append({
                **_serialize_folder(f),
                "children": build(f["id"]),
                "files": [_serialize_file(x) for x in files_by_folder.get(f["id"], [])],
            })
        return out

    return jsonify({
        "quote": _serialize_quote(quote),
        "order_info": order_info,
        "folders": build(None),
        "root_files": [_serialize_file(x) for x in files_by_folder.get(None, [])],
    })


@app.put("/api/admin/crm/quotes/<int:quote_id>")
@require_permission("nabidky", "upravit")
def quotes_admin_update(quote_id):
    admin = current_user()
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "client_label" in body:
        label = (body.get("client_label") or "").strip()
        if not label:
            return jsonify({"error": "Název klienta nesmí být prázdný."}), 400
        fields.append("client_label=%s"); params.append(label)
    if "title" in body:
        fields.append("title=%s"); params.append((body.get("title") or "").strip() or None)
    # Robert (pres bot3, 2026-09-04, schvalene doporuceni z Dolibarr/ERPNext
    # rozboru) - rucni propojeni nabidky s objednavkou, stejny princip jako
    # WORKFLOW.md bod 17 (rucni prirazeni k existujici poptavce): admin
    # vybere KONKRETNI objednavku, zadne automaticke parovani. order_id=null
    # odpojuje vazbu (nemaze objednavku, jen ji odpoji od teto nabidky).
    order_id_value = "unset"
    if "order_id" in body:
        raw_order_id = body.get("order_id")
        if raw_order_id in (None, ""):
            order_id_value = None
        else:
            try:
                order_id_value = int(raw_order_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatné order_id."}), 400
        fields.append("order_id=%s"); params.append(order_id_value)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not _get_quote(cur, quote_id):
                return jsonify({"error": "Nabídka neexistuje."}), 404
            if order_id_value not in ("unset", None):
                cur.execute("SELECT id FROM shop_orders WHERE id=%s", (order_id_value,))
                if not cur.fetchone():
                    return jsonify({"error": "Zadaná objednávka neexistuje."}), 400
            params.append(quote_id)
            cur.execute(f"UPDATE crm_quotes SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "update", "crm_quote", quote_id, str(body))
    return jsonify({"status": "ok"})


@app.delete("/api/admin/crm/quotes/<int:quote_id>")
@require_permission("nabidky", "smazat")
def quotes_admin_delete(quote_id):
    """Smazani CELE nabidky vc. slozek a souboru (bot6, 2026-08-02,
    Robert: "pridej obema bulk mazani s fajkama" - UI maze vybrane
    nabidky paralelnimi DELETE na tenhle endpoint). DB radky slozek/
    souboru kaskaduji (fk_cqf_quote/fk_cqfiles_quote ON DELETE CASCADE),
    fyzicke soubory na disku se musi smazat rucne PRED delete (jinak by
    se ztratil seznam stored_filename)."""
    admin = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            quote = _get_quote(cur, quote_id)
            if not quote:
                return jsonify({"error": "Nabídka neexistuje."}), 404
            cur.execute("SELECT stored_filename FROM crm_quote_files WHERE quote_id=%s", (quote_id,))
            stored = [r["stored_filename"] for r in cur.fetchall()]
            cur.execute("DELETE FROM crm_quotes WHERE id=%s", (quote_id,))
        conn.commit()
    finally:
        conn.close()
    for fn in stored:
        try:
            os.remove(os.path.join(QUOTE_FILES_DIR, fn))
        except OSError:
            pass
    log_audit(admin["id"], "delete", "crm_quote", quote_id,
              f"{quote['quote_number']} – {quote.get('client_label') or ''} ({len(stored)} souborů)")
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Slozky
# ---------------------------------------------------------------------------

@app.post("/api/admin/crm/quotes/<int:quote_id>/folders")
@require_permission("nabidky", "vytvorit")
def quotes_admin_folder_create(quote_id):
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Název složky je povinný."}), 400
    parent_folder_id = body.get("parent_folder_id") or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not _get_quote(cur, quote_id):
                return jsonify({"error": "Nabídka neexistuje."}), 404
            if parent_folder_id:
                cur.execute(
                    "SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s",
                    (parent_folder_id, quote_id),
                )
                if not cur.fetchone():
                    return jsonify({"error": "Nadřazená složka neexistuje."}), 400
            cur.execute(
                "INSERT INTO crm_quote_folders (quote_id, parent_folder_id, name) VALUES (%s,%s,%s)",
                (quote_id, parent_folder_id, name),
            )
            folder_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": folder_id}), 201


@app.put("/api/admin/crm/quotes/<int:quote_id>/folders/<int:folder_id>")
@require_permission("nabidky", "upravit")
def quotes_admin_folder_update(quote_id, folder_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "name" in body:
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Název složky nesmí být prázdný."}), 400
        fields.append("name=%s"); params.append(name)
    new_parent = None
    if "parent_folder_id" in body:
        # bot16, 2026-09-02 (revize bot3): hodnotu prisne na int - kontrola
        # cyklu nize porovnava s int id, string "5" by ji obesel; null/0/""
        # = presun do korene.
        raw_parent = body.get("parent_folder_id")
        if raw_parent not in (None, "", 0, "0"):
            if isinstance(raw_parent, bool) or not isinstance(raw_parent, (int, str)):
                return jsonify({"error": "Neplatná nadřazená složka."}), 400
            try:
                new_parent = int(raw_parent)
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatná nadřazená složka."}), 400
            if new_parent <= 0:
                return jsonify({"error": "Neplatná nadřazená složka."}), 400
        fields.append("parent_folder_id=%s"); params.append(new_parent)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s", (folder_id, quote_id))
            if not cur.fetchone():
                return jsonify({"error": "Složka neexistuje."}), 404
            if new_parent:
                # Rodic musi patrit TEZE nabidce (stejne jako u create) - jinak
                # by slozka osirela pod cizi nabidkou a kontrola cyklu nize by
                # ho v mape teto nabidky vubec nenasla.
                cur.execute(
                    "SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s",
                    (new_parent, quote_id),
                )
                if not cur.fetchone():
                    return jsonify({"error": "Nadřazená složka neexistuje."}), 400
                # Zabranit cyklu - novy rodic nesmi byt sam sobe ani vlastnimu potomkovi.
                cur.execute("SELECT id, parent_folder_id FROM crm_quote_folders WHERE quote_id=%s", (quote_id,))
                parent_of = {r["id"]: r["parent_folder_id"] for r in cur.fetchall()}
                walker, seen = new_parent, set()
                while walker is not None:
                    if walker == folder_id:
                        return jsonify({"error": "Nelze přesunout složku do sebe/vlastního podstromu."}), 400
                    if walker in seen:
                        break
                    seen.add(walker)
                    walker = parent_of.get(walker)
            params.append(folder_id)
            cur.execute(f"UPDATE crm_quote_folders SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


def _collect_folder_subtree_ids(cur, quote_id, folder_id):
    cur.execute("SELECT id, parent_folder_id FROM crm_quote_folders WHERE quote_id=%s", (quote_id,))
    children_by_parent = {}
    for r in cur.fetchall():
        children_by_parent.setdefault(r["parent_folder_id"], []).append(r["id"])
    ids, stack = [folder_id], [folder_id]
    while stack:
        current = stack.pop()
        for child_id in children_by_parent.get(current, []):
            ids.append(child_id)
            stack.append(child_id)
    return ids


@app.delete("/api/admin/crm/quotes/<int:quote_id>/folders/<int:folder_id>")
@require_permission("nabidky", "smazat")
def quotes_admin_folder_delete(quote_id, folder_id):
    """Smaze slozku VCETNE cele podslozkove vetve a VSECH souboru v ni -
    DB FK (fk_cqfiles_folder) je jen ON DELETE SET NULL (bezpecnostni
    sit proti osirelym radkum), skutecne rekurzivni mazani obsahu resi
    tahle funkce explicitne (stejny princip jako
    gallery_items.delete_items_for_owner)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s", (folder_id, quote_id))
            if not cur.fetchone():
                return jsonify({"error": "Složka neexistuje."}), 404
            folder_ids = _collect_folder_subtree_ids(cur, quote_id, folder_id)
            placeholders = ",".join(["%s"] * len(folder_ids))
            cur.execute(f"SELECT stored_filename FROM crm_quote_files WHERE folder_id IN ({placeholders})", folder_ids)
            file_rows = cur.fetchall()
            cur.execute(f"DELETE FROM crm_quote_files WHERE folder_id IN ({placeholders})", folder_ids)
            cur.execute("DELETE FROM crm_quote_folders WHERE id=%s", (folder_id,))
        conn.commit()
    finally:
        conn.close()
    for r in file_rows:
        try:
            os.remove(os.path.join(QUOTE_FILES_DIR, r["stored_filename"]))
        except OSError:
            pass
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Soubory
# ---------------------------------------------------------------------------

@app.post("/api/admin/crm/quotes/<int:quote_id>/files")
@require_permission("nabidky", "vytvorit")
def quotes_admin_files_upload(quote_id):
    """Zadne omezeni pripony - "jedne nabidky se muze tykat mnoho
    ruznych typu dokladu" (na rozdil od gallery_items.ALLOWED_EXT)."""
    admin = current_user()
    folder_id = request.form.get("folder_id", type=int)
    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"error": "Chybí soubor."}), 400
    conn = get_conn()
    created = []
    try:
        with conn.cursor() as cur:
            if not _get_quote(cur, quote_id):
                return jsonify({"error": "Nabídka neexistuje."}), 404
            if folder_id:
                cur.execute("SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s", (folder_id, quote_id))
                if not cur.fetchone():
                    return jsonify({"error": "Složka neexistuje."}), 400
            for f in files:
                stored_filename = safe_stored_filename(f.filename)
                dest = os.path.join(QUOTE_FILES_DIR, stored_filename)
                f.save(dest)
                size_bytes = os.path.getsize(dest)
                cur.execute(
                    "INSERT INTO crm_quote_files (quote_id, folder_id, filename, stored_filename, content_type, "
                    "size_bytes, source, uploaded_by) VALUES (%s,%s,%s,%s,%s,%s,'upload',%s)",
                    (quote_id, folder_id, f.filename[:255], stored_filename, f.mimetype, size_bytes, admin["id"]),
                )
                created.append(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    log_audit(admin["id"], "upload", "crm_quote_file", quote_id, f"{len(created)} souborů")
    return jsonify({"status": "ok", "ids": created}), 201


@app.put("/api/admin/crm/quotes/<int:quote_id>/files/<int:file_id>")
@require_permission("nabidky", "upravit")
def quotes_admin_files_update(quote_id, file_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "filename" in body:
        fn = (body.get("filename") or "").strip()
        if not fn:
            return jsonify({"error": "Název souboru nesmí být prázdný."}), 400
        fields.append("filename=%s"); params.append(fn[:255])
    if "folder_id" in body:
        fields.append("folder_id=%s"); params.append(body.get("folder_id") or None)
    if not fields:
        return jsonify({"error": "Nebyla zadána žádná změna."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM crm_quote_files WHERE id=%s AND quote_id=%s", (file_id, quote_id))
            if not cur.fetchone():
                return jsonify({"error": "Soubor neexistuje."}), 404
            if body.get("folder_id"):
                cur.execute(
                    "SELECT id FROM crm_quote_folders WHERE id=%s AND quote_id=%s",
                    (body["folder_id"], quote_id),
                )
                if not cur.fetchone():
                    return jsonify({"error": "Složka neexistuje."}), 400
            params.append(file_id)
            cur.execute(f"UPDATE crm_quote_files SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.delete("/api/admin/crm/quotes/<int:quote_id>/files/<int:file_id>")
@require_permission("nabidky", "smazat")
def quotes_admin_files_delete(quote_id, file_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stored_filename FROM crm_quote_files WHERE id=%s AND quote_id=%s", (file_id, quote_id))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Soubor neexistuje."}), 404
            cur.execute("DELETE FROM crm_quote_files WHERE id=%s", (file_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        os.remove(os.path.join(QUOTE_FILES_DIR, row["stored_filename"]))
    except OSError:
        pass
    return jsonify({"status": "ok"})


@app.get("/api/admin/crm/quotes/<int:quote_id>/files/<int:file_id>/download")
@require_permission("nabidky", "zobrazit")
def quotes_admin_files_download(quote_id, file_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_quote_files WHERE id=%s AND quote_id=%s", (file_id, quote_id))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor neexistuje."}), 404
    try:
        with open(os.path.join(QUOTE_FILES_DIR, row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Soubor na disku chybí."}), 404
    return Response(data, mimetype=row["content_type"] or "application/octet-stream", headers={
        "Content-Disposition": content_disposition(row["filename"]),
    })


@app.get("/api/admin/crm/quotes/<int:quote_id>/files/<int:file_id>/preview")
@require_permission("nabidky", "zobrazit")
def quotes_admin_files_preview(quote_id, file_id):
    """Nahled PDF primo v adminu (Robert: "u nabidek PDF v disku, vytvor
    moznost zobrazit primo v adminu"). NA ROZDIL od /download vyse (vzdy
    attachment, viz modulovy docstring - pojistka proti stored XSS u
    libovolneho nahraneho typu) tenhle endpoint umoznuje inline jen pro
    SKUTECNE PDF - overeno magic bytes obsahu souboru (%PDF-), NE podle
    stored content_type/pripony nazvu (obojí je nedůveryhodné - content_type
    je pri uploadu udaj z prohlizece/e-mailu, filename je taky uzivatelsky
    vstup). Response mimetype je natvrdo "application/pdf" bez ohledu na to,
    co je ulozene v DB - takze i kdyby nekdo obesel kontrolu, prohlizec dostane
    spravnou hlavicku, ne to, co si mysli utocnik."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM crm_quote_files WHERE id=%s AND quote_id=%s", (file_id, quote_id))
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Soubor neexistuje."}), 404
    try:
        with open(os.path.join(QUOTE_FILES_DIR, row["stored_filename"]), "rb") as fh:
            data = fh.read()
    except OSError:
        return jsonify({"error": "Soubor na disku chybí."}), 404
    if not data.startswith(b"%PDF-"):
        return jsonify({"error": "Náhled je dostupný jen pro PDF soubory."}), 415
    safe_ascii = "".join(c if 32 <= ord(c) < 127 and c != '"' else "_" for c in (row["filename"] or "")) or "soubor"
    return Response(data, mimetype="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{safe_ascii}"',
        "X-Content-Type-Options": "nosniff",
    })
