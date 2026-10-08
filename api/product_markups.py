"""
"Zakreslena pripominka" na strance produktu (bot14, 2026-09-02).

Robert (pres bot3/toscanaccio-0b): zakaznik si prohlizi obrazek produktu/
sestavy na e-shopu a chce do nej mysi/prstem zakrouzkovat, dokreslit nebo
skrtnout, co chce jinak, pridat text a odeslat jako dotaz. Kreslici modul
`webapp/js/image-markup.js` (bot5) resi vykreslovani + skladani vysledneho
obrazku (composite) na strane klienta - tenhle soubor je jen backend:
ulozeni, CRM lead, e-mailova fronta, admin sprava.

Vzor endpointu: `car_storefronts.py::storefront_lead_create` (verejny
lead bez loginu, zadny primy e-mail - WORKFLOW.md bod 16) +
`inquiries.py::inquiry_custom_table` (multipart formular s prilohou pres
`quotes.save_lead_attachment`).

Composite obrazek se uklada DVAKRAT, ze dvou ruznych duvodu:
  1) `PRIVATE_FILES_DIR/product-markups/<token>.<ext>` - "zdroj pravdy"
     pro `product_markups.composite_filename`, servirovany jen
     autentizovanym adminum (GET /api/admin/product-markups/<id>/file,
     vzor `gallery_items.py::gallery_items_file`).
  2) kopie jako priloha CRM leadu/zpravy pres `quotes.save_lead_attachment`
     (stejne jako u ostatnich verejnych formularu s prilohou) - at je
     videt primo v existujici CRM/Nabidky pipeline, ne jen v novem
     samostatnem miste.

Aktivace: `import product_markups` na konec app.py, AZ PO `import quotes`
(pouziva `quotes.save_lead_attachment`) a AZ PO `import products` (FK na
shop_products, i kdyz primo import products.py netreba).
"""
import json
import os
import re
import subprocess
import uuid
from io import BytesIO

from flask import request, jsonify, send_from_directory, abort
from PIL import Image, UnidentifiedImageError

from app import (
    app, get_conn, require_permission, current_user, log_audit, get_setting,
    get_pagination_args, APP_BASE_URL, _client_ip, _rate_limited,
)
import quotes

# Znovupouziti stavajiciho nastaveni ("koho upozornit na neco novyho,
# co potrebuje reakci admina" - viz support.py SUPPORT_NOTIFY_EMAIL_
# SETTING_KEY), misto vymyslet vlastni nastaveni jen pro tenhle jeden
# modul - mimo rozsah dnesniho zadani, admin uz jednu spolecnou adresu ma.
NOTIFY_EMAIL_SETTING_KEY = "support_notify_email"

PRIVATE_FILES_DIR = os.environ.get("PRIVATE_FILES_DIR", "/opt/konfigurator/private-files")
MARKUPS_DIR = os.path.join(PRIVATE_FILES_DIR, "product-markups")
os.makedirs(MARKUPS_DIR, exist_ok=True)

MAX_COMPOSITE_BYTES = 3 * 1024 * 1024
MAX_MARKS = 500
MAX_NOTE_LEN = 2000
MIN_NOTE_LEN = 3
MAX_VIEWS = 6
MAX_VIEW_JSON_BYTES = 4 * 1024
ALLOWED_MARK_KINDS = {"pen", "ellipse", "cross", "arrow", "text"}
STATUSES = ("new", "in_progress", "done")
STATUS_LABELS = {"new": "Nové", "in_progress": "Řeší se", "done": "Vyřízeno"}
_PHONE_DIGITS_RE = re.compile(r"\d")
# Zjevne vymyslena/testovaci cisla (Robert 2026-09-13: "kontrola realneho
# cisla telefonu pokud lze") - vsechny cislice stejne ("999999999") nebo
# jednoduchá rostouci/klesajici rada ("123456789"/"987654321"). Neresi to
# realnou existenci cisla (na to by bylo treba placena SMS-overovaci
# sluzba - mimo rozsah), jen odfiltruje nejocividnejsi bot/testovaci vstup.
_FAKE_PHONE_PATTERNS = {"123456789", "987654321", "012345678"}


def _telefon_vypada_falesne(cislice):
    if len(set(cislice)) == 1:
        return True
    if cislice in _FAKE_PHONE_PATTERNS or cislice[:9] in _FAKE_PHONE_PATTERNS:
        return True
    return False


def _domena_ma_mailserver(domain, timeout=2.0):
    """Overi, ze domena z e-mailu ma DNS MX (nebo aspon A) zaznam - odhali
    ocividne vymyslene/preklepove domeny (napr. "firma.cz" -> "firma.cz.cz",
    "gnail.com") bez plneho overeni schranky (zadny confirm-link/OTP - to
    by vyzadovalo odeslani e-mailu a cekani na klik, mimo rozsah teto
    verejne formulare). POUZE existence mailserveru, ne ze e-mail
    skutecne existuje.

    FAIL-OPEN: kdyz `dig` selze/timeoutuje (vypadek DNS na nasi strane,
    chybejici binarka), vraci True (nechceme odmitnout platny e-mail
    kvuli nasi infrastruktuře) - odmitne se JEN prokazatelne chybejici
    zaznam u domeny, kterou se podarilo dotazat.
    """
    try:
        for typ in ("MX", "A"):
            r = subprocess.run(
                ["dig", "+short", "+time=1", "+tries=1", typ, domain],
                capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode != 0:
                return True  # dig samotny selhal (ne NXDOMAIN) - fail open
            if r.stdout.strip():
                return True
        return False  # oba dotazy uspesne probehly, ani jeden zaznam
    except (subprocess.TimeoutExpired, OSError):
        return True


def _view_label(view, index):
    """Kratky popisek pohledu pro e-mail/admin (Robert: "v e-mailu
    vyjmenuj pohledy s uhly") - kind od bot16 (turntable)/bot5 (3d,
    snapshot GLB nahledu produktu)/fotky z galerie."""
    kind = view.get("kind") if isinstance(view, dict) else None
    if kind == "turntable":
        az, el = view.get("azimuth_deg"), view.get("elevation_deg")
        if az is not None and el is not None:
            return f"Pohled {index + 1}: otočný náhled {az}°/{el}°"
        return f"Pohled {index + 1}: otočný náhled"
    if kind == "3d":
        return f"Pohled {index + 1}: 3D náhled"
    if kind == "photo":
        return f"Pohled {index + 1}: fotka"
    return f"Pohled {index + 1}"


def _validate_composite(file_storage):
    """Overi OBSAH (ne jen priponu/Content-Type z hlavicky, ktere si
    klient muze vymyslet) - PIL musi soubor skutecne dekodovat jako
    JPEG nebo PNG. Vraci (data_bytes, ext) nebo (None, chybova_hlaska)."""
    if not file_storage or not file_storage.filename:
        return None, "Chybí obrázek (composite)."
    raw = file_storage.read(MAX_COMPOSITE_BYTES + 1)
    if len(raw) > MAX_COMPOSITE_BYTES:
        return None, "Obrázek je příliš velký (max 3 MB)."
    if not raw:
        return None, "Prázdný obrázek."
    try:
        img = Image.open(BytesIO(raw))
        img.verify()
        fmt = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "Soubor není platný obrázek (JPEG/PNG)."
    if fmt not in ("JPEG", "PNG"):
        return None, "Obrázek musí být JPEG nebo PNG."
    ext = "jpg" if fmt == "JPEG" else "png"
    return raw, ext


def _validate_marks(raw_json):
    """Struktura: pole objektu {kind, color, width, points[{x,y} 0..1],
    text?}, max MAX_MARKS znacek. Nevaliduje umelecky obsah (barvy/
    souradnice necha projit sirsi), jen tvar dat - marks_json se dal
    nikdy nevykrresluje jako HTML (viz admin.html - jen JSON dump /
    znovu-vykresleni do <canvas>), takze XSS riziko tady neni jako u
    volneho textu."""
    try:
        marks = json.loads(raw_json)
    except (TypeError, ValueError):
        return None, "Neplatný formát značek (marks)."
    if not isinstance(marks, list):
        return None, "marks musí být pole."
    if len(marks) > MAX_MARKS:
        return None, f"Příliš mnoho značek (max {MAX_MARKS})."
    for m in marks:
        if not isinstance(m, dict):
            return None, "Neplatná značka."
        if m.get("kind") not in ALLOWED_MARK_KINDS:
            return None, f"Neplatný typ značky: {m.get('kind')!r}."
        points = m.get("points")
        if not isinstance(points, list) or not points:
            return None, "Značka bez bodů."
        for p in points:
            if not isinstance(p, dict) or "x" not in p or "y" not in p:
                return None, "Neplatný bod značky."
            try:
                x, y = float(p["x"]), float(p["y"])
            except (TypeError, ValueError):
                return None, "Neplatný bod značky."
            if not (0 <= x <= 1 and 0 <= y <= 1):
                return None, "Bod značky mimo rozsah 0..1."
    return marks, None


def _safe_ext_filename(ext):
    token = os.urandom(16).hex()
    return f"{token}.{ext}"


def composite_filenames_for_products(cur, product_ids):
    """Nazvy kompozitu pripominek danych produktu. Volat PRED DELETE
    shop_products - FK product_markups -> shop_products je ON DELETE
    CASCADE, po smazani produktu uz se nazvy z DB nedozvime (products.py,
    bot3 2026-09-02)."""
    ids = [int(i) for i in product_ids]
    if not ids:
        return []
    ph = ",".join(["%s"] * len(ids))
    cur.execute(f"SELECT composite_filename FROM product_markups WHERE product_id IN ({ph})", ids)
    return [r["composite_filename"] for r in cur.fetchall() if r.get("composite_filename")]


def purge_composites(filenames):
    """Best-effort smazani kompozitu z MARKUPS_DIR PO uspesnem commitu
    (smazani produktu). Nazvy jsou nase (os.urandom hex + pripona), presto
    se bere jen basename - nikdy nesahat mimo MARKUPS_DIR. Chyby jen do
    logu."""
    removed, errors = 0, []
    for name in filenames:
        base = os.path.basename(name or "")
        if not base:
            continue
        try:
            os.remove(os.path.join(MARKUPS_DIR, base))
            removed += 1
        except FileNotFoundError:
            pass
        except OSError as e:
            errors.append(f"{base}: {e}")
    if errors:
        app.logger.warning("markups purge: smazano %d kompozitu, CHYBY: %s", removed, "; ".join(errors[:5]))
    elif removed:
        app.logger.info("markups purge: smazano %d kompozitu", removed)


@app.post("/api/shop/products/<int:product_id>/markups")
def product_markup_create(product_id):
    # VEREJNE, bez loginu - stejny duvod jako storefront_lead_create.
    # v2 (Robert pres bot3, 2026-09-02): "Zajemce muze zakreslit, co
    # zamysli, ve vice pohledech a pokazde to bude jinak, protoze natoci
    # pohled jinak" - jedna pripominka = 1..N pohledu (views), sdileji
    # lead/note/kontakt, kazdy ma vlastni composite/marks/view_json
    # (product_markups radek, sdileny submission_id).
    if _rate_limited(f"product_markup:{_client_ip()}", max_requests=5, window_seconds=3600):
        return jsonify({"error": "Příliš mnoho odeslaných připomínek, zkuste to prosím za chvíli."}), 429

    # Honeypot - skryte pole ve formulari, clovek ho nikdy nevyplni.
    # Vyplnene = bot -> tvarime se, ze vse probehlo v poradku, ale nic
    # neukladame (stejny vzor jako u jinych verejnych formularu v repu).
    if (request.form.get("website") or "").strip():
        return jsonify({"status": "ok"}), 200

    email = (request.form.get("email") or "").strip().lower()[:255]
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Zadejte platný e-mail.", "field": "email"}), 400
    # Robert 2026-09-13: "kontrola realneho cisla telefonu pokud lze a
    # emailu" - format uz kontrolovan vyse, tohle overuje, ze DOMENA
    # e-mailu vubec ma mailserver (viz _domena_ma_mailserver - fail-open
    # pri DNS vypadku, odmitne jen prokazatelne neexistujici domenu).
    email_domain = email.rsplit("@", 1)[-1]
    if not _domena_ma_mailserver(email_domain):
        return jsonify({"error": "Zadejte platný e-mail (doména neexistuje).", "field": "email"}), 400
    phone_raw = (request.form.get("phone") or "").strip()
    phone_digits = "".join(_PHONE_DIGITS_RE.findall(phone_raw))
    if not (9 <= len(phone_digits) <= 15):
        return jsonify({"error": "Zadejte platný telefon (9 až 15 číslic).", "field": "phone"}), 400
    if _telefon_vypada_falesne(phone_digits):
        return jsonify({"error": "Zadejte prosím skutečné telefonní číslo.", "field": "phone"}), 400
    phone = phone_raw[:50]
    note = (request.form.get("note") or "").strip()
    if not (MIN_NOTE_LEN <= len(note) <= MAX_NOTE_LEN):
        return jsonify({"error": f"Popis připomínky musí mít {MIN_NOTE_LEN}–{MAX_NOTE_LEN} znaků.", "field": "note"}), 400

    try:
        views_raw = json.loads(request.form.get("views") or "[]")
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatný formát views.", "field": "views"}), 400
    if not isinstance(views_raw, list) or not (1 <= len(views_raw) <= MAX_VIEWS):
        return jsonify({"error": f"Musí být zadán 1 až {MAX_VIEWS} pohled(ů).", "field": "views"}), 400

    parsed_views = []  # [{marks, view_obj, view_json_str, image_url, gallery_item_id}]
    for i, v in enumerate(views_raw):
        if not isinstance(v, dict):
            return jsonify({"error": f"Pohled {i + 1}: neplatná data.", "field": "views"}), 400
        image_url = str(v.get("image_url") or "").strip()[:500]
        if not image_url:
            return jsonify({"error": f"Pohled {i + 1}: chybí podkladový obrázek.", "field": "views"}), 400
        # Hodnota od klienta se uklada a pak zobrazuje v administraci -
        # bez tehle kontroly by slo ulozit `javascript:`/`data:` URL
        # (bot6, revize 17). Povolene je jen relativni `/...` nebo http(s).
        if not (image_url.startswith("/")
                or image_url.startswith("http://") or image_url.startswith("https://")):
            return jsonify({"error": f"Pohled {i + 1}: nepovolená adresa obrázku.", "field": "views"}), 400
        marks, marks_err = _validate_marks(json.dumps(v.get("marks") or []))
        if marks_err:
            return jsonify({"error": f"Pohled {i + 1}: {marks_err}", "field": "views"}), 400
        view_obj = v.get("view")
        if not isinstance(view_obj, dict):
            return jsonify({"error": f"Pohled {i + 1}: chybí view.", "field": "views"}), 400
        view_json_str = json.dumps(view_obj, ensure_ascii=False)
        if len(view_json_str.encode("utf-8")) > MAX_VIEW_JSON_BYTES:
            return jsonify({"error": f"Pohled {i + 1}: view je příliš velké.", "field": "views"}), 400
        gallery_item_id = None
        if view_obj.get("kind") == "photo":
            try:
                gallery_item_id = int(view_obj.get("gallery_item_id")) if view_obj.get("gallery_item_id") is not None else None
            except (TypeError, ValueError):
                gallery_item_id = None
        parsed_views.append({
            "marks": marks, "view_json": view_json_str, "image_url": image_url, "gallery_item_id": gallery_item_id,
        })

    composites = []  # [(data_bytes, ext)]
    for i in range(len(parsed_views)):
        data, ext_or_err = _validate_composite(request.files.get(f"composite_{i}"))
        if data is None:
            return jsonify({"error": f"Pohled {i + 1}: {ext_or_err}", "field": "views"}), 400
        composites.append((data, ext_or_err))

    written = []  # kompozity zapsane na disk v teto transakci - pri chybe smazat
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, slug, sku FROM shop_products WHERE id=%s", (product_id,))
            product = cur.fetchone()
            if not product:
                return jsonify({"error": "Produkt nenalezen."}), 404

            # Gating (Robert pres bot3: "tento rezim zobrazovat POUZE u
            # produktovych sestav") - i na backendu, ne jen skryte
            # tlacitko na strance (obrana proti primemu POSTu na
            # neplatny produkt). Rozsireno 2026-09-25 (Robert primo: Vandr
            # sestavy chce bez ohledu na product_assemblies, viz stejna
            # podminka u `allow_markup` v api/products.py::shop_products_get) -
            # VD-* SKU je samo o sobe dukaz, ze je to export sestavy.
            cur.execute("SELECT id FROM product_assemblies WHERE shop_product_id=%s LIMIT 1", (product_id,))
            has_assembly = bool(cur.fetchone())
            is_vandr = (product.get("sku") or "").startswith("VD-")
            if not has_assembly and not is_vandr:
                return jsonify({"error": "Tento produkt nepodporuje zakreslenou připomínku."}), 400

            submission_id = uuid.uuid4().hex

            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
            cust = cur.fetchone()
            subject = f"Zakreslená připomínka – {product['name']}"
            cur.execute(
                "INSERT INTO crm_leads (customer_id, contact_email, contact_phone, subject, source, unread_by_admin) "
                "VALUES (%s,%s,%s,%s,'product_markup',1)",
                (cust["id"] if cust else None, email, phone, subject),
            )
            lead_id = cur.lastrowid
            product_url = f"{APP_BASE_URL}/produkt/{product['slug']}" if product.get("slug") else f"{APP_BASE_URL}/product.html?id={product_id}"
            view_labels = [_view_label(json.loads(pv["view_json"]), i) for i, pv in enumerate(parsed_views)]
            message_body = (
                f"{note}\n\nProdukt: {product['name']}\n{product_url}\n\n"
                f"Přiložené pohledy ({len(parsed_views)}):\n" + "\n".join(f"- {lbl}" for lbl in view_labels)
            )
            cur.execute(
                "INSERT INTO crm_lead_messages (lead_id, sender_type, body) VALUES (%s,'contact',%s)",
                (lead_id, message_body),
            )
            message_id = cur.lastrowid

            client_ip = _client_ip()
            markup_ids = []
            for i, (pv, (data, ext)) in enumerate(zip(parsed_views, composites)):
                stored_filename = _safe_ext_filename(ext)
                # kompozit na disk uvnitr transakce (radek potrebuje nazev);
                # kdyz cokoli dal selze, `written` se v except smaze - zadne
                # sirotci soubory po rollbacku (bot3 d, 2026-09-02). Opacne
                # poradi (zapis az po commitu) by pri chybe disku nechalo
                # radek bez souboru = 404 v administraci, proto ne.
                with open(os.path.join(MARKUPS_DIR, stored_filename), "wb") as fh:
                    fh.write(data)
                written.append(os.path.join(MARKUPS_DIR, stored_filename))
                quotes.save_lead_attachment(cur, message_id, lead_id, f"pripominka-{i + 1}.{ext}",
                                             "image/jpeg" if ext == "jpg" else "image/png", data)
                # bot5, 2026-09-26 (Robert nasel panel "Fotky" u poptavky
                # prazdny, i kdyz zprava rikala "Přiložené pohledy (1)") -
                # bot3 zjistil, ze ten panel (admin.html #crmModalGallery,
                # renderGalleryModule("lead", leadId)) cte TRETI, uplne
                # jiny system (content_gallery_items, ne shared_drive_files
                # ani MARKUPS_DIR) - kopie composite obrazku sem, stejny
                # vzor jako gallery_items.py::gallery_items_upload()
                # (verejny /content-files/gallery-items/ adresar, proto
                # kopie - MARKUPS_DIR je privatni). is_public=0 (admin-only
                # pohled, ne verejna galerie).
                import gallery_items
                gallery_stored_name = f"lead-{lead_id}_zakres-{i + 1}-{os.urandom(4).hex()}.{ext}"
                with open(os.path.join(gallery_items.GALLERY_ITEMS_DIR, gallery_stored_name), "wb") as fh:
                    fh.write(data)
                written.append(os.path.join(gallery_items.GALLERY_ITEMS_DIR, gallery_stored_name))
                cur.execute(
                    "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM content_gallery_items "
                    "WHERE owner_type='lead' AND owner_id=%s",
                    (lead_id,),
                )
                gallery_sort = cur.fetchone()["n"]
                cur.execute(
                    "INSERT INTO content_gallery_items (owner_type, owner_id, filename, sort_order, is_public) "
                    "VALUES ('lead',%s,%s,%s,0)",
                    (lead_id, gallery_stored_name, gallery_sort),
                )
                cur.execute(
                    "INSERT INTO product_markups (product_id, submission_id, view_index, gallery_item_id, image_url, "
                    "view_json, marks_json, composite_filename, note, contact_email, contact_phone, lead_id, client_ip) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (product_id, submission_id, i, pv["gallery_item_id"], pv["image_url"], pv["view_json"],
                     json.dumps(pv["marks"], ensure_ascii=False), stored_filename, note, email, phone, lead_id, client_ip),
                )
                markup_ids.append(cur.lastrowid)

            notify_email = get_setting(cur, NOTIFY_EMAIL_SETTING_KEY, "")
            if notify_email:
                admin_link = f"{APP_BASE_URL}/admin.html#productmarkups"
                admin_subject = f"Nová zakreslená připomínka – {product['name']}"
                admin_body = (
                    f"Zákazník ({email}, {phone}) zakreslil připomínku k produktu „{product['name']}“ "
                    f"({len(parsed_views)} pohled(ů)).\n\n" + "\n".join(f"- {lbl}" for lbl in view_labels) +
                    f"\n\nPopis:\n{note}\n\nOtevřít v administraci: {admin_link}"
                )
                cur.execute(
                    "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                    "VALUES (NULL,'product_markup',%s,%s,%s,'pending','auto')",
                    (notify_email, admin_subject, admin_body),
                )

            confirm_subject = "Připomínku jsme přijali"
            confirm_body = (
                f"Dobrý den,\n\ndíky za zakreslenou připomínku k produktu „{product['name']}“ "
                f"({len(parsed_views)} pohled(ů)) - ozveme se vám co nejdřív s dalšími informacemi.\n\nS pozdravem"
            )
            cur.execute(
                "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) "
                "VALUES (NULL,'product_markup',%s,%s,%s,'pending','auto')",
                (email, confirm_subject, confirm_body),
            )
        conn.commit()
    except Exception:
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    finally:
        conn.close()
    return jsonify({"status": "ok", "submission_id": submission_id, "ids": markup_ids}), 201


@app.get("/api/admin/product-markups")
@require_permission("zakreslene_pripominky", "zobrazit")
def admin_product_markups_list():
    # v2 (bot3): "seskupit podle submission_id - jedna karta = kontakt +
    # text + N nahledu s labelem uhlu". Strankuje se na urovni SUBMISSION
    # (ne jednotlivych radku/pohledu), proto vlastni SQL misto sdileneho
    # paginated_query (ten nepocita s GROUP BY).
    status_filter = request.args.get("status")
    page, page_size = get_pagination_args(default_page_size=30)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where_sql = ""
            count_params = []
            if status_filter in STATUSES:
                where_sql = " WHERE pm.status=%s"
                count_params.append(status_filter)

            cur.execute(f"SELECT COUNT(DISTINCT pm.submission_id) AS c FROM product_markups pm{where_sql}", count_params)
            total = cur.fetchone()["c"]

            sub_sql = (
                f"SELECT pm.submission_id, MAX(pm.created_at) AS created_at "
                f"FROM product_markups pm{where_sql} GROUP BY pm.submission_id ORDER BY MAX(pm.created_at) DESC"
            )
            sub_params = list(count_params)
            if page_size:
                sub_sql += " LIMIT %s OFFSET %s"
                sub_params += [page_size, (page - 1) * page_size]
            cur.execute(sub_sql, sub_params)
            submission_ids = [r["submission_id"] for r in cur.fetchall()]

            rows = []
            if submission_ids:
                placeholders = ",".join(["%s"] * len(submission_ids))
                cur.execute(
                    f"SELECT pm.id, pm.submission_id, pm.view_index, pm.product_id, p.name AS product_name, "
                    f"p.slug AS product_slug, pm.note, pm.contact_email, pm.contact_phone, pm.status, "
                    f"pm.lead_id, pm.created_at, pm.view_json "
                    f"FROM product_markups pm JOIN shop_products p ON p.id = pm.product_id "
                    f"WHERE pm.submission_id IN ({placeholders}) ORDER BY pm.submission_id, pm.view_index",
                    submission_ids,
                )
                rows = cur.fetchall()
    finally:
        conn.close()

    grouped = {}
    order = []
    for r in rows:
        sid = r["submission_id"]
        if sid not in grouped:
            grouped[sid] = {
                "submission_id": sid, "product_id": r["product_id"], "product_name": r["product_name"],
                "product_slug": r["product_slug"], "note": r["note"], "contact_email": r["contact_email"],
                "contact_phone": r["contact_phone"], "lead_id": r["lead_id"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "views": [],
            }
            order.append(sid)
        view_json = r["view_json"]
        if isinstance(view_json, str):
            try:
                view_json = json.loads(view_json)
            except (TypeError, ValueError):
                view_json = None
        grouped[sid]["views"].append({
            "id": r["id"], "view_index": r["view_index"], "status": r["status"],
            "view_json": view_json, "view_label": _view_label(view_json or {}, r["view_index"]),
        })
    for sid in order:
        statuses = {v["status"] for v in grouped[sid]["views"]}
        overall = "new" if "new" in statuses else ("in_progress" if "in_progress" in statuses else "done")
        grouped[sid]["status"] = overall
        grouped[sid]["status_label"] = STATUS_LABELS.get(overall, overall)

    items = [grouped[sid] for sid in order]
    resp = {"items": items, "count": len(items)}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.put("/api/admin/product-markups/submission/<submission_id>")
@require_permission("zakreslene_pripominky", "upravit")
def admin_product_markup_submission_update(submission_id):
    # Meni stav VSECH pohledu jedne pripominky najednou (admin karta
    # = 1 submission, ne 1 radek) - viz admin_product_markups_list().
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in STATUSES:
        return jsonify({"error": f"status musí být jedno z: {', '.join(STATUSES)}."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM product_markups WHERE submission_id=%s LIMIT 1", (submission_id,))
            if not cur.fetchone():
                return jsonify({"error": "Nenalezeno."}), 404
            cur.execute("UPDATE product_markups SET status=%s WHERE submission_id=%s", (status, submission_id))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "product_markup_submission", None, f"{submission_id}: status={status}")
    return jsonify({"status": "ok"})


@app.get("/api/admin/product-markups/<int:markup_id>/file")
@require_permission("zakreslene_pripominky", "zobrazit")
def admin_product_markup_file(markup_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT composite_filename FROM product_markups WHERE id=%s", (markup_id,))
            row = cur.fetchone()
    finally:
        conn.close()
    # `composite_filename` je NOT NULL az od zavedeni v2, ale radek muze
    # existovat s prazdnou hodnotou - send_from_directory(None) by spadlo
    # na TypeError = 500 misto cisteho 404 (bot6, revize 17).
    if not row or not row["composite_filename"]:
        abort(404)
    return send_from_directory(MARKUPS_DIR, row["composite_filename"])
