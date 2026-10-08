"""Admin: firemní údaje (název/adresa/IČO/DIČ/telefon/e-mail) zobrazené na
veřejné kontaktní stránce (kontakt.html) - DB-backed misto natvrdo v HTML
(Robert 2026-09-06, přes bot3: "chci aby to bylo editovatelné z adminu").

Uloženo v app_settings pod klíčem "company_info" (stejný vzor jako
og_site_defaults/theme_colors_*/smtp_config - jeden JSON řádek, ne vlastní
tabulka - viz AGENTS_LOG.md 2026-09-06 pro zdůvodnění volby oproti nové
tabulce, kterou zadání taky připouštělo).

Registruje:
- GET/PUT /api/admin/company-info - admin formulář (tab "Nastavení").
- GET /api/contact-email-image - veřejný, generuje PNG s e-mailem za běhu
  (nahrazuje dřívější statické webapp/contact-email-{dark,light}.png -
  ty byly guarded soubory v gitu, přepisovat je při každé změně e-mailu
  za běhu appky by nechávalo neustále "špinavý" guarded diff bez zámku/
  commitu; cesta pod /api/ je navíc proxovaná na backend na VŠECH
  vhostech sdílejících webapp/, takže funguje všude bez zásahu do nginx).
- GET /kontakt.html - SSR, JEN na vhostech co mají `location =
  /kontakt.html` proxy na backend (aktuálně `logiman-autovestavby` a
  `konfigurator`, mimo git - viz AGENTS_LOG.md). Na ostatních vhostech
  sdílejících webapp/ (Fiat storefronty, remeslnik-pro) se kontakt.html
  dál servíruje staticky beze změny (obsah v gitu zůstává reálnými
  aktuálními hodnotami jako rozumný fallback), vědomě neřešeno pro
  tuhle session - jiné brandy/produkty, mimo rozsah zadání.
"""
import io
import json
import os
import re

from flask import request, jsonify, Response

from app import (
    app, get_conn, get_setting, require_permission, current_user, log_audit,
    _og_escape, _ld_json_script,
)

# Výchozí hodnoty = přesně to, co bylo dřív natvrdo v kontakt.html (fallback
# pro chybějící řádek v app_settings, např. čerstvá DB).
COMPANY_INFO_DEFAULTS = {
    "name": "LOGIMAN s.r.o.",
    "address": "Husinecká 903/10, 13000 Praha, Česká republika",
    "ico": "28337638",
    "dic": "CZ28337638",
    "phone": "+420 603 230 059",
    "email": "mandik@logiman.cz",
}
COMPANY_INFO_FIELDS = tuple(COMPANY_INFO_DEFAULTS)


def _get_company_info(cur):
    raw = get_setting(cur, "company_info", None)
    info = dict(COMPANY_INFO_DEFAULTS)
    if raw:
        try:
            saved = json.loads(raw)
        except (ValueError, TypeError):
            saved = {}
        for k in COMPANY_INFO_FIELDS:
            if saved.get(k):
                info[k] = saved[k]
    return info


@app.get("/api/admin/company-info")
@require_permission("nastaveni", "zobrazit")
def company_info_get():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            return jsonify(_get_company_info(cur))
    finally:
        conn.close()


@app.put("/api/admin/company-info")
@require_permission("nastaveni", "upravit")
def company_info_set():
    body = request.get_json(silent=True) or {}
    info = {k: (body.get(k) or "").strip() for k in COMPANY_INFO_FIELDS}
    required = ("name", "address", "ico", "phone", "email")
    missing = [k for k in required if not info[k]]
    if missing:
        return jsonify({"error": "Vyplň všechny povinné údaje (název, adresa, IČO, telefon, e-mail)."}), 400
    if "@" not in info["email"]:
        return jsonify({"error": "E-mail nevypadá platně."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            val = json.dumps(info, ensure_ascii=False)
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES ('company_info',%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (val, val),
            )
        conn.commit()
    finally:
        conn.close()
    user = current_user()
    log_audit(user["id"] if user else None, "update", "company_info", None,
              "Firemní údaje aktualizovány (název/adresa/IČO/DIČ/telefon/e-mail).")
    return jsonify({"status": "ok"})


# --- Dynamický e-mailový obrázek (viz docstring nahoře) -------------------
_EMAIL_IMG_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_EMAIL_IMG_COLORS = {"dark": "#c7ccd4", "light": "#3a3f4a"}  # = --text2 v obou motivech kontakt.html


@app.get("/api/contact-email-image")
def contact_email_image():
    from PIL import Image, ImageDraw, ImageFont
    mode = request.args.get("theme") if request.args.get("theme") in _EMAIL_IMG_COLORS else "dark"
    color = _EMAIL_IMG_COLORS[mode]
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            email = _get_company_info(cur)["email"]
    finally:
        conn.close()
    scale = 4
    font_size = 16 * scale
    pad = 6 * scale
    font = ImageFont.truetype(_EMAIL_IMG_FONT_PATH, font_size)
    tmp_draw = ImageDraw.Draw(Image.new("RGBA", (10, 10), (0, 0, 0, 0)))
    bbox = tmp_draw.textbbox((0, 0), email, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((pad - bbox[0], pad - bbox[1]), email, font=font, fill=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    resp = Response(buf.getvalue(), mimetype="image/png")
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# --- SSR kontakt.html (viz docstring nahoře - jen na vybraných vhostech) --
_KONTAKT_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "webapp", "kontakt.html")
_KONTAKT_FIELD_IDS = {"name": "kiName", "address": "kiAddress", "ico": "kiIco", "dic": "kiDic"}


@app.get("/kontakt.html")
def kontakt_html_page():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            info = _get_company_info(cur)
    finally:
        conn.close()
    with open(_KONTAKT_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    desc = f'Kontaktní údaje {info["name"]} – {info["address"]}. IČO {info["ico"]}, telefon {info["phone"]}.'
    for attr in ('name="description"', 'property="og:description"', 'name="twitter:description"'):
        html = re.sub(
            rf'(<meta {re.escape(attr)} content=")[^"]*(")',
            lambda m: m.group(1) + _og_escape(desc) + m.group(2),
            html, count=1,
        )
    for field, elem_id in _KONTAKT_FIELD_IDS.items():
        html = re.sub(
            rf'(id="{elem_id}">)[^<]*(</div>)',
            lambda m, v=info[field]: m.group(1) + _og_escape(v) + m.group(2),
            html, count=1,
        )
    phone_digits = re.sub(r"[^+0-9]", "", info["phone"])
    # [^"]* nahrazuje celý href včetně "tel:" - prefix se musí vrátit, jinak je z odkazu
    # relativní URL (/+420...) a vede na 404 (QA SEO_INTERNAL_LINK_BROKEN).
    html = re.sub(
        r'(id="kiPhoneLink" href=")[^"]*(">)[^<]*(</a>)',
        lambda m: m.group(1) + "tel:" + phone_digits + m.group(2) + _og_escape(info["phone"]) + m.group(3),
        html, count=1,
    )
    ld_json = _ld_json_script({
        "@context": "https://schema.org", "@type": "Organization",
        "name": "Hliníkový konstrukční stavebnicový systém s drážkami",
        "legalName": info["name"],
        "telephone": info["phone"],
        # Adresa zůstává jedno volné pole (shoduje se s jediným editovatelným
        # "Adresa" řádkem v adminu) - schema.org Organization.address přijímá
        # Text i strukturovaný PostalAddress, Text je tu záměrně jednodušší
        # varianta odpovídající rozsahu zadání (bot9, 2026-09-06).
        "address": info["address"],
    })
    html = re.sub(r'<script type="application/ld\+json">.*?</script>', ld_json.strip(), html, count=1, flags=re.S)
    return Response(html, mimetype="text/html; charset=utf-8")
