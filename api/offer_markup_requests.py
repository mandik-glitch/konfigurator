"""
Zakreslene zmeny v online nabidce (bot16, 2026-10-07).

Robert 2026-10-07: "zakreslovani zmen komplet je na webu hotove, jen to prenest do online nabidky a to i pro stoly z generatoru" (+ nabidky z Vandr karet).
Zakaznik v online nabidce zakresli zmenu (kreslici modul webapp/js/image-markup.js: tuzka, krouzek, skrtnout, sipka, text) do vykresu / 3D pohledu /
renderu, pripise popis + kontakt a odesle; Logiman dostane poptavku s obrazky. Kresleni a skladani vysledneho obrazku (composite) dela prohlizec
(webapp/nabidka-online.html), tenhle soubor je jen BACKEND: validace, CRM poptavka, prilohy, poznamka u nabidky, e-maily do fronty.

Vzor: product_markups.py::product_markup_create (stejny postup a STEJNE validace - helpery se berou odtamtud). Rozdily: misto produktu je nabidka (scene_offers)
a misto samostatne tabulky product_markups jdou obrazky jako prilohy CRM poptavky (Drive slozka poptavky + panel Fotky) a poznamka je v scene_offer_notes
(viditelna ve statistikach nabidky). ZADNE nove tabulky ani DDL: crm_leads.source je varchar(20) ('offer_markup'), scene_offers.customer_email uz existuje.
Vektorove znacky (marks) se jen OVERUJI a neukladaji - jsou "vypalene" v obrazku; ukladat je dava smysl az s prohlizenim v adminu (product_markups je ma kvuli tomu).
Totez `page` u pohledu (jen overeni delky); `view.kind` se pouziva do popisku pohledu v CRM zprave a e-mailech, `view.camera`/`key` se jen overuji.

Endpoint (verejny, bez loginu - zakaznik ma jen odkaz s tokenem):
  POST /api/public/offers/<token>/markup-requests    multipart/form-data
    email, phone (povinne), note (3-2000 znaku), website (honeypot - vyplnene = tvarime se OK a nic neukladame),
    views = JSON pole 1-6 objektu [{label, page?, view:{kind:'drawing'|'3d'|'render', key?, camera?}, marks:[...], image_w, image_h}],
    composite_0 .. composite_{N-1} = obrazek kazdeho pohledu (JPEG/PNG, do 3 MB)
  -> 201 {"status":"ok","views":N}; 400 {"error","field"}; 403 admin "Zobrazit online" token; 404 nabidka; 429 rate limit.

PRIZNAK pro stranku: GET /api/public/offers/<token> vraci "markup_requests" = markup_requests_enabled(offer) (scene_offers.public_offer_get) - vlastnost NABIDKY,
bez ohledu na to, zda je token klientsky nebo admin (stranka podle nej schova stare znackovani a roli rozlisuje pres viewer_role); admin token odmita az POST (403).
Statika (nabidka-online.html) je zivá hned, API az pri nasazeni - stranka proto zakreslovani nabidne JEN kdyz backend priznak poslal.

Gating (markup_requests_enabled): nabidka z konfigurace stolu (offer_options.source == 'configurator') nebo z Vandr karty (offer_options.vandr_single_drawing);
nabidky ze sceny (1. vetev) maji vlastni starsi znackovani (znacky viditelne oboum stranam, PUT .../markups) a zatim zustavaji beze zmeny.

Aktivace: `import offer_markup_requests` na konec app.py AZ PO `import product_markups` (pouziva jeho helpery) a po scene_offers/quotes/crm/drive/gallery_items.
"""
import datetime
import hashlib
import json
import os
import re

from flask import request, jsonify

from app import app, get_conn, APP_BASE_URL
import crm
import drive
import gallery_items
import product_markups as pm
import quotes
import scene_offers

SOURCE = "offer_markup"                   # crm_leads.source (varchar(20))
EMAIL_KIND = "scene_offer_markup"         # system_emails.kind
NOTE_ITEM_NAME = "Zakreslená změna"       # scene_offer_notes.item_name
VIEW_KINDS = ("drawing", "3d", "render")  # view.kind: vykres / 3D pohled (snimek prohlizece) / render z galerie nabidky
MAX_LABEL_LEN = 120
MAX_PAGE_LEN = 30
MAX_KEY_LEN = 80
MAX_IMAGE_SIDE = 10000
ADMIN_OFFERS_URL = f"{APP_BASE_URL}/admin.html#onlineoffers"
_DRUH_POHLEDU = {"drawing": "výkres", "3d": "3D pohled", "render": "vizualizace"}
_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")        # jeden zavinac, zadne bile znaky (ani novy radek = ochrana pred vlozenim hlavicek do e-mailu), tecka v domene


def markup_requests_enabled(offer):
    """JEDINE misto rozhodnuti, zda nabidka umi zakreslene zmeny (pouziva ho POST nize i priznak ve verejne odpovedi scene_offers.public_offer_get).
    offer = radek scene_offers. True: nabidka z konfigurace stolu (source 'configurator') nebo z Vandr karty (vandr_single_drawing)."""
    try:
        opts = scene_offers._offer_options_from_row(offer)
    except Exception:
        return False
    if not isinstance(opts, dict):
        return False
    return opts.get("source") == "configurator" or opts.get("vandr_single_drawing") is True


def _chyba(zprava, pole=None):
    body = {"error": zprava}
    if pole:
        body["field"] = pole
    return jsonify(body), 400


def _popisek_pohledu(pohled, index):
    druh = _DRUH_POHLEDU.get((pohled.get("view") or {}).get("kind"), "pohled")
    label = pohled.get("label") or ""
    return f"Pohled {index + 1}: {label} ({druh})" if label else f"Pohled {index + 1}: {druh}"


def _cela_cislo(hodnota):
    return isinstance(hodnota, int) and not isinstance(hodnota, bool) and 1 <= hodnota <= MAX_IMAGE_SIDE


def _zkontroluj_pohledy(raw_json):
    """views z formulare -> (seznam {label,page,view,marks,image_w,image_h}, None) nebo (None, (zprava, pole)). Vsechny chyby se hlasi
    jako 'Pohled N: ...' (stejne jako u product_markups), at zakaznik vi, ktery pohled vadi."""
    try:
        views_raw = json.loads(raw_json or "[]")
    except (TypeError, ValueError):
        return None, ("Neplatný formát views.", "views")
    if not isinstance(views_raw, list) or not (1 <= len(views_raw) <= pm.MAX_VIEWS):
        return None, (f"Musí být zadán 1 až {pm.MAX_VIEWS} pohled(ů).", "views")
    out = []
    for i, v in enumerate(views_raw):
        n = i + 1
        if not isinstance(v, dict):
            return None, (f"Pohled {n}: neplatná data.", "views")
        label = v.get("label")
        if label is not None and (not isinstance(label, str) or len(label.strip()) > MAX_LABEL_LEN):
            return None, (f"Pohled {n}: neplatný popisek (max {MAX_LABEL_LEN} znaků).", "views")
        page = v.get("page")
        if page is not None and (not isinstance(page, str) or len(page) > MAX_PAGE_LEN):
            return None, (f"Pohled {n}: neplatná stránka.", "views")
        view_obj = v.get("view")
        if not isinstance(view_obj, dict):
            return None, (f"Pohled {n}: chybí view.", "views")
        if view_obj.get("kind") not in VIEW_KINDS:
            return None, (f"Pohled {n}: neplatný druh pohledu.", "views")
        key = view_obj.get("key")
        if key is not None and (not isinstance(key, str) or len(key) > MAX_KEY_LEN):
            return None, (f"Pohled {n}: neplatný klíč pohledu.", "views")
        camera = view_obj.get("camera")
        if camera is not None and not isinstance(camera, dict):
            return None, (f"Pohled {n}: neplatná kamera.", "views")
        if len(json.dumps(view_obj, ensure_ascii=False).encode("utf-8")) > pm.MAX_VIEW_JSON_BYTES:
            return None, (f"Pohled {n}: view je příliš velké.", "views")
        marks, marks_err = pm._validate_marks(json.dumps(v.get("marks") or []))
        if marks_err:
            return None, (f"Pohled {n}: {marks_err}", "views")
        for nazev in ("image_w", "image_h"):
            if v.get(nazev) is not None and not _cela_cislo(v.get(nazev)):
                return None, (f"Pohled {n}: neplatný rozměr obrázku ({nazev}).", "views")
        out.append({"label": " ".join((label or "").split()), "page": page, "view": view_obj, "marks": marks,
                    "image_w": v.get("image_w"), "image_h": v.get("image_h")})
    return out, None


def _priloha_poptavky(cur, lead_id, message_id, nazev, mime, data, written):
    """Priloha CRM poptavky (Drive slozka poptavky + panel Fotky) - quotes.save_lead_attachment zapise soubor na disk A radek do shared_drive_files.
    Nazev souboru na disku zna jen ta funkce, proto se po ulozeni dohleda posledni soubor v NASI slozce poptavky a zapamatuje se pro uklid pri chybe."""
    folder_id = crm.ensure_lead_drive_folder(cur, lead_id)          # idempotentni - save_lead_attachment pouzije tutez slozku
    quotes.save_lead_attachment(cur, message_id, lead_id, nazev, mime, data)
    if folder_id is not None:
        cur.execute("SELECT stored_filename FROM shared_drive_files WHERE folder_id=%s ORDER BY id DESC LIMIT 1", (folder_id,))
        row = cur.fetchone()
        if row and row.get("stored_filename"):
            written.append(os.path.join(drive.DRIVE_FILES_DIR, os.path.basename(row["stored_filename"])))


def _kopie_do_galerie(cur, lead_id, poradi, ext, data, written):
    """Kopie obrazku do galerie poptavky (content_gallery_items, owner_type 'lead', neverejna) - presne jako product_markups: panel "Fotky" u poptavky
    v adminu cte tenhle system, ne shared_drive_files. Verejny adresar gallery-items, proto samostatna kopie (privatni je jen Drive)."""
    jmeno = f"lead-{lead_id}_zakres-{poradi}-{os.urandom(4).hex()}.{ext}"
    cesta = os.path.join(gallery_items.GALLERY_ITEMS_DIR, jmeno)
    with open(cesta, "wb") as fh:
        fh.write(data)
    written.append(cesta)
    cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM content_gallery_items WHERE owner_type='lead' AND owner_id=%s", (lead_id,))
    razeni = cur.fetchone()["n"]
    cur.execute("INSERT INTO content_gallery_items (owner_type, owner_id, filename, sort_order, is_public) VALUES ('lead',%s,%s,%s,0)", (lead_id, jmeno, razeni))


def _zaradit_emaily(cur, offer, test_prefix, email, phone, note, popisky, lead_id, ip, now):
    """Dva e-maily JEN do fronty (pravidlo 16, nikdy primo): upozorneni dodavateli + potvrzeni zakaznikovi. Admin je schvaluje/odesila jako ostatni systemove e-maily."""
    cislo = offer["offer_number"]
    zakaznik = offer.get("customer_name") or "-"
    seznam = "\n".join(f"- {p}" for p in popisky)
    cur.execute(
        "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) VALUES (NULL,%s,%s,%s,%s,'pending','auto')",
        (EMAIL_KIND, scene_offers.SUPPLIER["email"], f"{test_prefix}Zakreslená změna k nabídce {cislo}",
         f"K nabídce {cislo} přišla zakreslená změna ({len(popisky)} pohled(ů)).\n\n"
         f"Zákazník: {zakaznik}\nKontakt: {email}, {phone}\n\nPopis změny:\n{note}\n\nPohledy:\n{seznam}\n\n"
         f"Obrázky jsou v CRM poptávce č. {lead_id} (záložka Fotky).\nNabídky v administraci: {ADMIN_OFFERS_URL}\n"
         f"Čas: {now.strftime('%d.%m.%Y %H:%M')}\nIP adresa: {ip}"),
    )
    cur.execute(
        "INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) VALUES (NULL,%s,%s,%s,%s,'pending','auto')",
        (EMAIL_KIND, email, f"{test_prefix}Zakreslenou změnu jsme přijali",
         f"Dobrý den,\n\ndíky za zakreslenou změnu k nabídce {cislo} ({len(popisky)} pohled(ů)) - ozveme se vám co nejdřív "
         f"s dalšími informacemi.\n\nS pozdravem\n{scene_offers.SUPPLIER.get('name', '')}"),
    )


@app.post("/api/public/offers/<token>/markup-requests")
def public_offer_markup_request(token):
    # VEREJNE, bez loginu (zakaznik ma jen odkaz s tokenem) - stejny duvod jako product_markup_create / public_offer_note.
    limited = scene_offers._public_offer_rate_limited(token, "markup", 3, 8)
    if limited:
        return limited

    # Honeypot - skryte pole ve formulari, clovek ho nikdy nevyplni. Vyplnene = bot: tvarime se, ze vse probehlo v poradku, ale nic neukladame.
    if (request.form.get("website") or "").strip():
        return jsonify({"status": "ok"}), 200

    # Nabidka PRED tezkou praci (dekodovani obrazku): neplatny/ciziny token nema stat nic.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            offer = scene_offers._resolve_offer_by_token(cur, token)
    finally:
        conn.close()
    if not offer or not offer["is_active"] or offer["expires_at"] < datetime.datetime.now():
        return jsonify({"error": "Nabídka nebyla nalezena."}), 404
    if hashlib.sha256(token.encode()).hexdigest() == offer["admin_view_token_hash"]:
        return jsonify({"error": "Administrátorský náhled neodesílá změny."}), 403
    if not markup_requests_enabled(offer):
        return jsonify({"error": "Tato nabídka zakreslení změn nepodporuje."}), 400

    email = (request.form.get("email") or "").strip().lower()[:255]
    if not _EMAIL_RE.fullmatch(email):
        return _chyba("Zadejte platný e-mail.", "email")
    phone_raw = (request.form.get("phone") or "").strip()
    phone_digits = "".join(pm._PHONE_DIGITS_RE.findall(phone_raw))
    if not (9 <= len(phone_digits) <= 15):
        return _chyba("Zadejte platný telefon (9 až 15 číslic).", "phone")
    if pm._telefon_vypada_falesne(phone_digits):
        return _chyba("Zadejte prosím skutečné telefonní číslo.", "phone")
    phone = " ".join(phone_raw.split())[:50]
    note = (request.form.get("note") or "").strip()
    if not (pm.MIN_NOTE_LEN <= len(note) <= pm.MAX_NOTE_LEN):
        return _chyba(f"Popis změny musí mít {pm.MIN_NOTE_LEN}–{pm.MAX_NOTE_LEN} znaků.", "note")

    pohledy, chyba = _zkontroluj_pohledy(request.form.get("views"))
    if chyba:
        return _chyba(*chyba)
    composites = []                      # [(data, ext)]
    for i in range(len(pohledy)):
        data, ext_nebo_chyba = pm._validate_composite(request.files.get(f"composite_{i}"))
        if data is None:
            return _chyba(f"Pohled {i + 1}: {ext_nebo_chyba}", "views")
        composites.append((data, ext_nebo_chyba))
    # DNS (MX) nakonec - je to nejpomalejsi kontrola (fail-open pri vypadku DNS, viz product_markups._domena_ma_mailserver)
    if not pm._domena_ma_mailserver(email.rsplit("@", 1)[-1]):
        return _chyba("Zadejte platný e-mail (doména neexistuje).", "email")

    popisky = [_popisek_pohledu(p, i) for i, p in enumerate(pohledy)]
    test_prefix = "[TESTOVACÍ NABÍDKA] " if offer["offer_number"] == scene_offers.TEST_OFFER_NUMBER else ""
    ip = scene_offers._client_ip()
    now = datetime.datetime.now()
    written = []                         # soubory zapsane na disk v teto transakci - pri chybe se smazou (zadni sirotci po rollbacku)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
            cust = cur.fetchone()
            cur.execute(
                "INSERT INTO crm_leads (customer_id, contact_name, contact_email, contact_phone, subject, source, unread_by_admin) VALUES (%s,%s,%s,%s,%s,%s,1)",
                (cust["id"] if cust else None, (offer.get("customer_name") or "").strip()[:255] or None, email, phone,
                 f"{test_prefix}Zakreslená změna k nabídce {offer['offer_number']}", SOURCE),
            )
            lead_id = cur.lastrowid
            zprava = (f"{note}\n\nNabídka: {offer['offer_number']}" + (f" (zákazník: {offer['customer_name']})" if offer.get("customer_name") else "")
                      + f"\nNabídky v administraci: {ADMIN_OFFERS_URL}\n\nPřiložené pohledy ({len(pohledy)}):\n" + "\n".join(f"- {p}" for p in popisky))
            cur.execute("INSERT INTO crm_lead_messages (lead_id, sender_type, body) VALUES (%s,'contact',%s)", (lead_id, zprava))
            message_id = cur.lastrowid
            for i, (data, ext) in enumerate(composites):
                _priloha_poptavky(cur, lead_id, message_id, f"zakreslena-zmena-{i + 1}.{ext}", "image/jpeg" if ext == "jpg" else "image/png", data, written)
                _kopie_do_galerie(cur, lead_id, i + 1, ext, data, written)
            cur.execute(
                "INSERT INTO scene_offer_notes (offer_id, guest_id, page_key, item_name, body, ip_address, created_at) VALUES (%s,%s,NULL,%s,%s,%s,%s)",
                (offer["id"], scene_offers._quote_guest_id(), NOTE_ITEM_NAME,
                 f"{note}\n\nKontakt: {email}, {phone}\nZakreslené pohledy: {len(pohledy)}\nCRM poptávka #{lead_id}", ip, now),
            )
            _zaradit_emaily(cur, offer, test_prefix, email, phone, note, popisky, lead_id, ip, now)
        conn.commit()
    except Exception:
        for cesta in written:
            try:
                os.remove(cesta)
            except OSError:
                pass
        app.logger.exception("zakreslena zmena k nabidce %s se neulozila", offer["offer_number"])
        return jsonify({"error": "Odeslání se nepodařilo, zkuste to prosím za chvíli znovu."}), 500
    finally:
        conn.close()
    return jsonify({"status": "ok", "views": len(pohledy)}), 201
