"""
Verejny poptavkovy formular "Poptavam stul" (bot6, 2026-08-08).

Robert dal odkaz https://www.logiman.cz/poptavam-stul/ a chtel
"podobny formular" u nas. Ten je postaveny na externim nastroji
Fillout.com (3 kroky: typ stolu + rozmery, kontakt, specifikace
material/prislusenstvi/balici material/pocet stolu) - rozklicovano
z jeho verejneho JSON (`__NEXT_DATA__` na forms.fillout.com/t/<id>),
obrazky stazeny a ulozeny lokalne (webapp/content-files/inquiry-forms/
stul/), zadna zavislost na externim Fillout uctu.

Upresneno pres AskUserQuestion: 1) odpovedi maji koncit primo v CRM
Poptavky (crm_leads/crm_lead_messages, ne jen e-mailem) - admin je
uvidi ve stejnem workflow jako poptavky z e-mailu; 2) plna kopie (3
kroky, obrazkove vybery), ne zjednodusena verze.

Endpoint je VEREJNY (zadny @require_permission) - vyplnuje ho
nepřihlášený zákazník na e-shopu.
"""
import random

from flask import request, jsonify, session

from app import app, get_conn, _rate_limited, _client_ip
import quotes

MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_FIELD_LEN = 2000

TABLE_TYPES = {
    "Stůl a police spolu",
    "Stůl a police odděleně",
    "Stůl s neměnnou výškou",
    "Elektricky nastavitelná výška stolu",
}
MATERIALS = {
    "Laminovaná dřevotříska síly 18 / 25mm",
    "Březová nebo buková překližka 30 / 40 mm",
    "Oděruodolná vrstva HPL 0,8mm",
}


def _clean(value, max_len=MAX_FIELD_LEN):
    if value is None:
        return ""
    value = str(value).strip()
    return value[:max_len]


def _find_or_create_web_lead(cur, contact_email, contact_name, subject):
    """Zrcadli crm.find_or_create_lead(), ale se source='web' (odliseni
    od e-mailovych/rucnich poptavek v adminu) - existujici funkci
    nemenim, at nezasahuji do e-mailove synchronizace, ktera na ni
    primo vola."""
    cur.execute(
        "SELECT id FROM crm_leads WHERE contact_email=%s AND status NOT IN ('vyhrano','prohrano') "
        "AND archived=0 ORDER BY last_message_at DESC LIMIT 1",
        (contact_email,),
    )
    row = cur.fetchone()
    if row:
        return row["id"], False
    cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (contact_email,))
    cust = cur.fetchone()
    cur.execute(
        "INSERT INTO crm_leads (customer_id, contact_name, contact_email, subject, source) "
        "VALUES (%s,%s,%s,%s,'web')",
        (cust["id"] if cust else None, contact_name, contact_email, subject),
    )
    return cur.lastrowid, True


def _format_message(fields):
    lines = ["Poptávka stolu (webový formulář e-shopu)", ""]
    lines.append(f"Typ stolu: {fields['table_type']}")
    lines.append(
        f"Rozměry pracovní desky: {fields['length_mm']} × {fields['width_mm']} mm"
    )
    lines.append(f"Rozsah výškové stavitelnosti: {fields['height_range_mm']} mm")
    lines.append(f"Materiál desky: {fields['material']}")
    if fields["accessories"]:
        lines.append(f"Příslušenství: {', '.join(fields['accessories'])}")
    if fields["packaging_material"]:
        lines.append(f"Balicí materiál pro řezačku: {', '.join(fields['packaging_material'])}")
    if fields["table_count"]:
        lines.append(f"Počet stolů: {fields['table_count']}")
    if fields["note"]:
        lines.append("")
        lines.append("Doplňující informace:")
        lines.append(fields["note"])
    return "\n".join(lines)


@app.post("/api/inquiries/custom-table")
def inquiry_custom_table():
    # QA bezpecnostni nalez (2026-09-05): verejny formular bez rate-limitu
    # (analogicky storefront_lead v car_storefronts.py, stejne hodnoty).
    if _rate_limited(f"inquiry_custom_table:{_client_ip()}", max_requests=5, window_seconds=600):
        return jsonify({"error": "Příliš mnoho pokusů, zkuste to prosím za chvíli."}), 429
    body = request.form
    errors = {}

    table_type = _clean(body.get("table_type"), 255)
    if table_type not in TABLE_TYPES:
        errors["table_type"] = "Vyberte typ stolu."

    def _positive_int(key, label):
        raw = _clean(body.get(key), 20)
        try:
            n = int(raw)
        except (TypeError, ValueError):
            errors[key] = f"{label}: zadejte celé číslo v mm."
            return None
        if n <= 0 or n > 20000:
            errors[key] = f"{label}: neplatná hodnota."
            return None
        return n

    length_mm = _positive_int("length_mm", "Délka pracovní desky")
    width_mm = _positive_int("width_mm", "Šířka pracovní desky")
    height_range_mm = _positive_int("height_range_mm", "Rozsah výškové stavitelnosti")

    material = _clean(body.get("material"), 255)
    if material not in MATERIALS:
        errors["material"] = "Vyberte materiál pracovní desky."

    name = _clean(body.get("name"), 255)
    if not name:
        errors["name"] = "Zadejte jméno."
    email = _clean(body.get("email"), 255).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        errors["email"] = "Zadejte platný e-mail."
    phone = _clean(body.get("phone"), 50)
    if not phone:
        errors["phone"] = "Zadejte telefon."

    if errors:
        return jsonify({"error": "Formulář obsahuje chyby.", "fields": errors}), 400

    accessories = [a for a in request.form.getlist("accessories") if a][:20]
    packaging_material = [p for p in request.form.getlist("packaging_material") if p][:10]
    table_count = _clean(body.get("table_count"), 50)
    note = _clean(body.get("note"), MAX_FIELD_LEN)

    fields = {
        "table_type": table_type, "length_mm": length_mm, "width_mm": width_mm,
        "height_range_mm": height_range_mm, "material": material,
        "accessories": accessories, "packaging_material": packaging_material,
        "table_count": table_count, "note": note,
    }
    message_body = _format_message(fields)
    subject = f"Poptávka stolu - {table_type}"

    upload = request.files.get("file")
    attachment_data = None
    if upload and upload.filename:
        raw = upload.read(MAX_ATTACHMENT_BYTES + 1)
        if len(raw) > MAX_ATTACHMENT_BYTES:
            return jsonify({"error": "Příloha je příliš velká (max 15 MB)."}), 400
        attachment_data = (upload.filename, upload.content_type, raw)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            lead_id, created = _find_or_create_web_lead(cur, email, name, subject)
            if not created:
                cur.execute(
                    "UPDATE crm_leads SET contact_name=COALESCE(contact_name, %s), "
                    "contact_phone=COALESCE(contact_phone, %s), unread_by_admin=1, last_message_at=NOW() "
                    "WHERE id=%s",
                    (name, phone, lead_id),
                )
            else:
                cur.execute(
                    "UPDATE crm_leads SET contact_phone=%s WHERE id=%s",
                    (phone, lead_id),
                )
            cur.execute(
                "INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) "
                "VALUES (%s,'contact',%s,%s)",
                (lead_id, name, message_body),
            )
            message_id = cur.lastrowid
            if attachment_data:
                quotes.save_lead_attachment(cur, message_id, lead_id, *attachment_data)
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 201


# Robert pres bot3, 2026-09-26 - "v každé kategorii bude okno pro dotaz po
# zadání platného emailu a kontrolního výpočtu proti spamu". Overeno: jen
# category.html vubec renderuje obsah kategorie (index.html/blok.html
# nerenderuji content_pages vubec, grep na bottom_body_html/intro_html
# tam vraci 0) - widget tedy jen tam, zadna dalsi kopie.
#
# Anti-spam kontrolni priklad: dve mala nahodna cisla, ocekavany soucet
# ulozeny server-side v podepsanem Flask session cookie (session[...],
# stejny mechanismus jako support.py/scene_offers.py uz pouzivaji pro
# guest ID) - NE v localStorage (klient by si mohl odpoved sam upravit)
# a NE jen v JS (to obejde kazdy bot/curl). Jednorazovy - .pop() ho
# smaze pri KAZDEM overovacim pokusu (uspesnem i neuspesnem), takze
# uhodnuti vyzaduje novou vyzvu pro kazdy pokus, ne opakovane zkouseni
# proti jedne staticke otazce.
CAPTCHA_SESSION_KEY = "cat_inquiry_captcha_sum"


@app.get("/api/category-inquiry/captcha")
def category_inquiry_captcha():
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    session[CAPTCHA_SESSION_KEY] = a + b
    return jsonify({"a": a, "b": b})


@app.post("/api/category-inquiry")
def category_inquiry_submit():
    if _rate_limited(f"category_inquiry:{_client_ip()}", max_requests=5, window_seconds=600):
        return jsonify({"error": "Příliš mnoho pokusů, zkuste to prosím za chvíli."}), 429

    body = request.get_json(silent=True) or request.form
    errors = {}

    message = _clean(body.get("message"), MAX_FIELD_LEN)
    if not message:
        errors["message"] = "Zadejte dotaz."

    email = _clean(body.get("email"), 255).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        errors["email"] = "Zadejte platný e-mail."

    # Jednorazove overeni - session hodnota se smaze HNED, at uz je
    # odpoved spravne nebo ne (viz komentar u CAPTCHA_SESSION_KEY vyse).
    expected_sum = session.pop(CAPTCHA_SESSION_KEY, None)
    submitted_raw = _clean(body.get("captcha_answer"), 10)
    try:
        submitted_sum = int(submitted_raw)
    except (TypeError, ValueError):
        submitted_sum = None
    if expected_sum is None:
        errors["captcha_answer"] = "Kontrolní příklad vypršel, načtěte prosím stránku znovu."
    elif submitted_sum != expected_sum:
        errors["captcha_answer"] = "Výsledek příkladu nesouhlasí."

    if errors:
        return jsonify({"error": "Formulář obsahuje chyby.", "fields": errors}), 400

    try:
        category_id = int(body.get("category_id"))
    except (TypeError, ValueError):
        category_id = None

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            category_name = None
            if category_id:
                cur.execute("SELECT name FROM content_categories WHERE id=%s", (category_id,))
                cat_row = cur.fetchone()
                category_name = cat_row["name"] if cat_row else None
            subject = f"Dotaz ke kategorii - {category_name}" if category_name else "Dotaz ke kategorii"
            # bot5 (konzultace k formatu subjectu, 2026-09-26): doporucil
            # pridat id kategorie do zpravy pro zpetnou dohledatelnost,
            # kdyby se nazev kategorie casem prejmenoval/zdvojil.
            message_body = message
            if category_id:
                message_body += f"\n\n(Dotaz odeslán z kategorie č. {category_id}"
                message_body += f" – {category_name})" if category_name else ")"

            # bot5, 2026-09-27 (Robert 3x zmateny "žádný dotaz sem
            # nespadl" - bot3 zjistil, ze dotaz se spravne ULOZIL, ale
            # slouceny do STAREHO vlakna (_find_or_create_web_lead paruje
            # jen podle e-mailu, bez ohledu na temat) je vizualne
            # neviditelny - pocet radku v seznamu se nezmeni, tema
            # zustava puvodni). VYSLOVNE JEN TADY (ne v _find_or_create_
            # web_lead samotne, ta zustava sdilena s e-mailovou synchronizaci
            # a ostatnimi formulari beze zmeny) - kazdy dotaz z kategorie
            # dostava VLASTNI novy radek, VZDY, i kdyz uz pro ten e-mail
            # existuje jiny lead. Zadne parovani/hledani ve vlakne.
            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
            cust = cur.fetchone()
            cur.execute(
                "INSERT INTO crm_leads (customer_id, contact_name, contact_email, subject, source, unread_by_admin) "
                "VALUES (%s,%s,%s,%s,'web',1)",
                (cust["id"] if cust else None, None, email, subject),
            )
            lead_id = cur.lastrowid
            cur.execute(
                "INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) "
                "VALUES (%s,'contact',%s,%s)",
                (lead_id, None, message_body),
            )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"status": "ok"}), 201
