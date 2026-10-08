"""Mini-shop (Packstations a dalsi tema mini-shopy): serverove API /api/miniweb/* (bot5, 2026-10-02; navrh schvalil bot3, kostru shopu a TVARY ODPOVEDI dodal bot16 - webapp/miniweb/demo-api.js).

FAZE 1 = CTECI API, FAZE 2 = POPTAVKA (POST). Objednavky (faze 3: mena, DPH, doprava, doklady v cizi mene) jsou ZAVRENE do rozhodnuti Roberta a tu nejsou.

Mini-shop = storefront (car_storefronts: host a jazyk podle DOMENY, aliasy hostu v storefront_hosts) + radek v miniweb_shops. Katalog je language-neutral (miniweb_categories, miniweb_products) a patri RODINE shopu
(family: shopy se stejnou rodinou = jazykove verze sdili katalog, shop jine rodiny vidi jen svuj),
TEXTY jsou po jazycich v miniweb_*_texts se stavem draft/approved: verejnosti se servi jen approved, staff v nahledu (shop ve stavu draft, nebo ?drafts=1) i draft (u produktu text_status 'draft').

Endpointy (JSON, shop ve stavu live je verejny, shop ve stavu draft jen pro staff - brana je NA SERVERU):
  GET  /api/miniweb/config             nastaveni shopu (nahrazuje staticky config.json): jazyk, mena, barva, zeme, neutralni kontakt (telefon, doba, NIKDY e-mail), price_mode, alternates (jazykove verze se stejnou rodinou)
  GET  /api/miniweb/categories         [{id, parent_id, slug, name, count}] (count = viditelne produkty vcetne podkategorii)
  GET  /api/miniweb/products           ?category=<slug> &limit &offset -> {products, total}
  GET  /api/miniweb/products/<id>      {product}
  GET  /api/miniweb/legal              {seller, contact, documents} - JEDINE misto, kde se objevi nazev spolecnosti (zakonna identifikace prodejce, Robert: prodejce zustava Logiman s.r.o.)
  POST /api/miniweb/inquiry            poptavka/kontaktni formular: {name, email, phone?, company?, country?, message?, consent: true, items?: [{product_id, qty, kod?, configuration?, summary?}], website: "" (honeypot)}
                                       -> 201 {status: ok, inquiry_id}. Zaklada CRM poptavku (source miniweb, osobni udaje JEN tam) a nepersonalni snimek (miniweb_inquiries, polozky). Potvrzeni zakaznikovi je
                                       ZATIM VYPNUTE (CONFIRMATION_ENABLED, rozhodnuti Roberta pres bot3: odpovi zamestnanec osobne), po zapnuti jde jen do schvalovaci fronty (system_emails pending,
                                       pravidlo 16). Shop, ktery neni live (nahled pro staff), poptavku jen zvaliduje a NEULOZI (201 s preview true) - zadna testovaci data v produkci.

Pravidla (nemenit bez Roberta/bot3):
  * ZADNY ZIVY E-MAIL na webu (Robert 2026-09-06): API nevydava zadnou e-mailovou adresu (kontakt je telefon a doba, jinak formular /inquiry).
  * BEZ ZNACKY: kazdy text (nazvy, popisy, parametry, kontakt, adresy jazykovych verzi, e-mail zakaznikovi) projde filtrem dealers._BRAND_RE, FAIL CLOSED: pole se znackou se nevyda, produkt/kategorie se znackou se skryje.
    Vyjimka je jen legal.seller (zakonny udaj, ne marketingovy text),
  * ceny se NEVYDAVAJI (price_from vzdy null, price_mode 'hidden') ani NEPRIJIMAJI, dokud Robert nerozhodne o mene a DPH; dodavatel, interni SKU a interni id karet (krome configurator.product_id, ktere konfigurator potrebuje) neodchazeji,
  * texty jsou cisty text (HTML se odstrani), delky omezene, specs jen {name, value}; klient nikdy nerozhoduje o nazvu, kodu a existenci produktu v poptavce (server bere z databaze),
  * odpovedi nesou X-Robots-Tag noindex a Cache-Control (live verejne 60 s, staff/koncept/chyby no-store), limit 240 cteni za minutu na IP, poptavky 5 za 10 minut na IP a 3 za den na e-mail.
"""
import html
import json
import re

from flask import request, jsonify

import car_storefronts
import dealers
import documents
from app import app, get_conn, current_user, _client_ip, _rate_limited, PERMISSION_ROLES

READ_LIMIT_PER_MIN = 240
INQUIRY_LIMIT_PER_IP = (5, 600)
INQUIRY_LIMIT_PER_EMAIL_DAY = 3
INQUIRY_MAX_BODY = 65536
INQUIRY_MAX_ITEMS = 20
INQUIRY_MAX_DEPTH = 32
INQUIRY_MAX_MESSAGE = 12000
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
_LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-z]{2,4})?\Z")
_LOCALE_RE = re.compile(r"^[a-z]{2,3}([-_][A-Za-z0-9]{2,8})*\Z")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}\Z")
_ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}\Z")
_COUNTRY_RE = re.compile(r"^[A-Z]{2}\Z")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}\Z")
_HASH_RE = re.compile(r"^[A-Za-z0-9_.:-]{6,128}\Z")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]+@([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}\Z")
_BLOCK_RE = re.compile(r"<(script|style)\b[^>]{0,300}>.{0,5000}?</\1\s*>", re.I | re.S)
_TAG_RE = re.compile(r"<!--.{0,2000}?-->|</?[A-Za-z][^>]{0,300}>", re.S)
_BREAK_RE = re.compile(r"<\s*br\s*/?\s*>|</\s*(?:p|div|li|h[1-6]|tr)\s*>", re.I)
_CTRL_RE = re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f" + chr(0x2028) + chr(0x2029) + "]")                  # ridici znaky a oddelovace radku Unicode

# POTVRZENI ZAKAZNIKOVI JE ZATIM VYPNUTE (rozhodnuti Roberta pres bot3 2026-10-02: mini-shop nepotvrzuje e-mailem, poptavka jde jen do CRM a zamestnanec odpovi osobne, protoze spolecny odesilatel
# SMTP nese znacku "Logiman s.r.o." a Robertovu adresu). Zapnout az bude neutralni odesilatel (domena a schranka shopu), pak patri prepinac do DB per shop. Sablony zustavaji pripravene a otestovane.
# Kdyz je zapnuto: potvrzeni jde jen do schvalovaci fronty (system_emails pending, pravidlo 16), sablona existuje jen pro jazyky se schvalenym textem, pro ostatni se nezaklada.
CONFIRMATION_ENABLED = False
CONFIRMATION = {
    "en": ("Inquiry received", "Dear {name},\n\nthank you for your inquiry via {site}.\n\nWe will get back to you shortly with further information.\n\nKind regards"),
}


class ShopError(Exception):
    def __init__(self, status, code, field=None):
        super().__init__(code)
        self.status, self.code, self.field = status, code, field


def _clean_lang(value):
    s = str(value or "").strip().lower().replace("_", "-")
    return s if _LANG_RE.match(s) else None


def _no_surrogates(s):
    """Osamocene surrogaty (z JSON escape jako \\ud800) nejdou ulozit do databaze (UnicodeEncodeError), proto pryc."""
    return s.encode("utf-8", "ignore").decode("utf-8")


def _too_deep(obj, limit=INQUIRY_MAX_DEPTH):
    """True, kdyz je JSON struktura hlubsi nez limit (iterativne, bez rekurze). MySQL odmita JSON hlubsi nez 100 urovni a Python ho rad nacte i vypise mnohem hloubeji."""
    stack = [(obj, 1)]
    while stack:
        o, d = stack.pop()
        if d > limit:
            return True
        if isinstance(o, dict):
            stack.extend((v, d + 1) for v in o.values())
        elif isinstance(o, list):
            stack.extend((v, d + 1) for v in o)
    return False


def _plain(value, limit, multiline=False):
    """Cisty text z dat: entity rozbalene, bloky script/style a HTML znacky pryc (konce odstavcu a <br> u multiline jako novy radek), ridici znaky pryc, mezery sjednocene, orez na limit.
    Samotne znaky < a > (napr. 'load > 150 kg') zustavaji, strip bere jen to, co vypada jako znacka."""
    s = _no_surrogates(("" if value is None else str(value))[:limit * 4 + 64])      # predorez: praci s anonymnim vstupem omezuje delka, ne obsah
    s = html.unescape(s)
    s = _BLOCK_RE.sub(" ", s)
    if multiline:
        s = _BREAK_RE.sub("\n", s)
    s = _CTRL_RE.sub("", _TAG_RE.sub(" ", s))
    if multiline:
        s = re.sub(r"[ \t\f\v]+", " ", s.replace("\r", ""))
        s = re.sub(r" ?\n ?", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
    else:
        s = re.sub(r"\s+", " ", s)
    return s.strip()[:limit]


def _as_int(value):
    """Cele cislo z JSON hodnoty: int (ne bool) nebo retezec cislic, jinak None (true, 1.9, null, 'abc' nejsou cisla)."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,9}", value.strip()):
        return int(value.strip())
    return None


def _is_staff(user):
    return bool(user) and bool(user.get("active")) and user.get("role") in PERMISSION_ROLES


def _storefront_by_host(cur, host):
    cur.execute("SELECT * FROM car_storefronts WHERE primary_domain=%s", (host,))
    row = cur.fetchone()
    if row:
        return row
    cur.execute("SELECT s.* FROM storefront_hosts h JOIN car_storefronts s ON s.id = h.storefront_id WHERE h.host=%s", (host,))
    return cur.fetchone()


def _shop_context(cur):
    """Mini-shop pro tenhle pozadavek: storefront podle HOSTA (hlavni nebo alias), na spolecne domene ?shop=<slug> jen pro staff. Shop, ktery neni live, vidi jen staff, ostatni dostanou 404.
    Jazyk = lang storefrontu (urcuje domena), ?lang= jen pro staff. -> dict kontextu, nebo ShopError."""
    user = current_user()
    staff = _is_staff(user)
    host = car_storefronts._normalize_host(request.host)
    sf = _storefront_by_host(cur, host) if host else None
    if sf is None and staff and request.args.get("shop"):
        cur.execute("SELECT * FROM car_storefronts WHERE slug=%s", (request.args.get("shop"),))
        sf = cur.fetchone()
        host = car_storefronts._normalize_host(sf["primary_domain"]) if sf else host
    if sf is None:
        raise ShopError(404, "shop_not_found")
    live = sf["status"] == "live"
    if not live and not staff:
        raise ShopError(404, "shop_not_found")
    cur.execute("SELECT * FROM miniweb_shops WHERE storefront_id=%s", (sf["id"],))
    shop = cur.fetchone()
    if not shop:
        raise ShopError(404, "shop_not_found")
    lang = _clean_lang(sf.get("lang")) or "cs"
    if staff and request.args.get("lang"):
        lang = _clean_lang(request.args.get("lang")) or lang
    langs = [lang] + ([lang.split("-")[0]] if "-" in lang else [])
    include_draft = staff and (not live or request.args.get("drafts") == "1")
    return {"sf": sf, "shop": shop, "lang": lang, "langs": langs, "staff": staff, "live": live, "include_draft": include_draft, "host": host,
            "statuses": ["approved", "draft"] if include_draft else ["approved"]}


def _respond(payload, ctx=None, status=200):
    resp = jsonify(payload)
    resp.status_code = status
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Cache-Control"] = "public, max-age=60" if (ctx and ctx["live"] and not ctx["staff"] and status == 200 and request.method == "GET") else "no-store"
    return resp


def _guard(fn):
    def wrapped(*a, **k):
        if _rate_limited(f"miniweb:{_client_ip()}", READ_LIMIT_PER_MIN, 60):
            return _respond({"error": "rate_limited"}, None, 429)
        try:
            return fn(*a, **k)
        except ShopError as e:
            return _respond({"error": e.code, **({"field": e.field} if e.field else {})}, None, e.status)
        except Exception:
            app.logger.exception("miniweb: neocekavana chyba v %s", fn.__name__)
            return _respond({"error": "internal_error"}, None, 500)
    wrapped.__name__ = fn.__name__
    return wrapped


def _shop_slug(sf):
    return sf["slug"] if not dealers._brand_hit(sf["slug"]) else "shop"


def _currency(shop):
    return shop["currency"] if shop["currency"] and _CURRENCY_RE.match(shop["currency"]) else None


# ---------------------------------------------------------------------------------------------------------------- data
def _texts(cur, table, idcol, ids, ctx):
    """Texty vybranych polozek v jazyce shopu (presny jazyk ma prednost pred zakladnim, napr. en-ie pred en) ve stavech povolenych kontextem. -> {id: radek}.
    SQL porovnava jazyk bez ohledu na velikost pismen, proto se poradi ve slozce pocita z normalizovane hodnoty."""
    if not ids:
        return {}
    ph = ",".join(["%s"] * len(ids))
    lph = ",".join(["%s"] * len(ctx["langs"]))
    sph = ",".join(["%s"] * len(ctx["statuses"]))
    cur.execute(f"SELECT * FROM {table} WHERE {idcol} IN ({ph}) AND lang IN ({lph}) AND status IN ({sph})", list(ids) + ctx["langs"] + ctx["statuses"])
    best = {}
    for r in cur.fetchall():
        lang = _clean_lang(r["lang"])
        if lang not in ctx["langs"]:
            continue
        rank = ctx["langs"].index(lang)
        if r[idcol] not in best or rank < best[r[idcol]][0]:
            best[r[idcol]] = (rank, r)
    return {k: v[1] for k, v in best.items()}


def _visible_categories(cur, ctx):
    """{id: {id, parent_id, slug, name, sort_order, text_status}} jen pro viditelne kategorie: z RODINY shopu, aktivni, s textem v jazyce shopu, bez znacky, a CELY retezec rodicu viditelny
    (rodic z jine rodiny se nenacte, takze potomek zustane skryty)."""
    cur.execute("SELECT id, parent_id, slug, sort_order FROM miniweb_categories WHERE is_active=1 AND family=%s ORDER BY sort_order, id", (ctx["shop"]["family"],))
    rows = {r["id"]: r for r in cur.fetchall()}
    texts = _texts(cur, "miniweb_category_texts", "miniweb_category_id", list(rows), ctx)
    memo = {}

    def visible(cid, seen=()):
        if cid in memo:
            return memo[cid]
        r, ok = rows.get(cid), False
        if r is not None and cid not in seen:
            t = texts.get(cid)
            name = _plain(t["name"], 200) if t else ""
            if name and not dealers._brand_hit(name, r["slug"]):
                ok = r["parent_id"] is None or visible(r["parent_id"], seen + (cid,))
        memo[cid] = ok
        return ok

    out = {}
    for cid, r in rows.items():
        if visible(cid):
            out[cid] = {"id": cid, "parent_id": r["parent_id"], "slug": r["slug"], "name": _plain(texts[cid]["name"], 200), "sort_order": r["sort_order"], "text_status": texts[cid]["status"]}
    return out


def _specs(raw):
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    out = []
    for s in (raw if isinstance(raw, list) else [])[:40]:
        if isinstance(s, dict):
            n, v = _plain(s.get("name"), 120), _plain(s.get("value"), 300)
            if n and v:
                out.append({"name": n, "value": v})
    return out


def _product_json(p, t, ctx, shop):
    """Produkt v tvaru z demo-api.js, nebo None (bez nazvu / se znackou v kterekoli z vydavanych hodnot = skryt, fail closed)."""
    name, summary = _plain(t["name"], 200), _plain(t["summary"], 500)
    description, delivery = _plain(t["description"], 4000, multiline=True), _plain(t["delivery"], 255)
    specs = _specs(t["specs_json"])
    if not name or dealers._brand_hit(name, summary, description, delivery, p["slug"], p["public_sku"], *[x for s in specs for x in (s["name"], s["value"])]):
        return None
    available = bool(p["configurator_available"])
    item = {"id": p["id"], "slug": p["slug"], "sku": p["public_sku"], "category_id": p["category_id"], "name": name, "summary": summary, "description": description,
            "price_from": None, "currency": _currency(shop), "delivery": delivery,
            "configurator": {"available": available, "default_view": p["default_view"], "product_id": p["shop_product_id"] if available else None}, "specs": specs}
    if ctx["include_draft"] and t["status"] == "draft":
        item["text_status"] = "draft"
    return item


def _visible_products(cur, ctx):
    """-> (seznam produktu ve tvaru API serazeny podle sort_order a id, slovnik viditelnych kategorii)."""
    cats = _visible_categories(cur, ctx)
    cur.execute("SELECT * FROM miniweb_products WHERE is_active=1 ORDER BY sort_order, id")
    prods = [p for p in cur.fetchall() if p["category_id"] in cats]
    texts = _texts(cur, "miniweb_product_texts", "miniweb_product_id", [p["id"] for p in prods], ctx)
    out = []
    for p in prods:
        t = texts.get(p["id"])
        item = _product_json(p, t, ctx, ctx["shop"]) if t else None
        if item is not None:
            out.append(item)
    return out, cats


def _contact(shop):
    raw = shop.get("contact_json")
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for k in ("phone", "hours"):                          # e-mail se NEVYDAVA nikdy (Robertovo trvale pravidlo 2026-09-06: na zadnem webu zadny zivy e-mail, kontakt je formular), ani kdyz je v contact_json
        v = _plain(raw.get(k), 200)
        out[k] = "" if (not v or dealers._brand_hit(v)) else v
    return out


# ---------------------------------------------------------------------------------------------------------------- endpointy: cteni
@app.get("/api/miniweb/config")
@_guard
def miniweb_config():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            sf, shop = ctx["sf"], ctx["shop"]
            cur.execute("SELECT s.lang, s.primary_domain, s.status FROM miniweb_shops m JOIN car_storefronts s ON s.id = m.storefront_id WHERE m.family=%s AND m.storefront_id<>%s ORDER BY s.lang, s.id",
                        (shop["family"], sf["id"]))
            alternates, seen = [], {ctx["lang"]}
            for r in cur.fetchall():
                lang = _clean_lang(r["lang"])
                if lang and lang not in seen and (r["status"] == "live" or ctx["staff"]) and not dealers._brand_hit(r["primary_domain"]):
                    seen.add(lang)
                    alternates.append({"lang": lang, "href": f"https://{r['primary_domain']}/"})
    finally:
        conn.close()
    accent = shop["accent"] if shop["accent"] and _ACCENT_RE.match(shop["accent"]) else None
    countries = [c for c in (x.strip().upper() for x in (shop["countries"] or "").split(",")) if _COUNTRY_RE.match(c)]
    locale = shop["locale"] if shop["locale"] and _LOCALE_RE.match(shop["locale"]) else ctx["lang"]
    return _respond({"shop": _shop_slug(sf), "lang": ctx["lang"], "locale": locale, "currency": _currency(shop), "accent": accent, "countries": countries,
                     "contact": _contact(shop), "price_mode": shop["price_mode"], "inquiry_only": True, "inquiry_enabled": bool(shop["inquiry_enabled"]), "alternates": alternates,
                     "preview": not ctx["live"]}, ctx)


@app.get("/api/miniweb/categories")
@_guard
def miniweb_categories():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            products, cats = _visible_products(cur, ctx)
    finally:
        conn.close()
    counts = {cid: 0 for cid in cats}
    for p in products:
        cid, seen = p["category_id"], set()
        while cid in cats and cid not in seen:            # produkt se pocita do sve kategorie i vsech nadrazenych
            counts[cid] += 1
            seen.add(cid)
            cid = cats[cid]["parent_id"]
    ordered = sorted(cats.values(), key=lambda c: (c["sort_order"], c["id"]))
    return _respond({"categories": [{"id": c["id"], "parent_id": c["parent_id"], "slug": c["slug"], "name": c["name"], "count": counts[c["id"]]} for c in ordered]}, ctx)


@app.get("/api/miniweb/products")
@_guard
def miniweb_products():
    try:
        limit = min(MAX_LIMIT, max(1, int(request.args.get("limit", DEFAULT_LIMIT))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return _respond({"error": "bad_request"}, None, 400)
    cat_slug = request.args.get("category")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            products, cats = _visible_products(cur, ctx)
    finally:
        conn.close()
    if cat_slug:
        target = next((c for c in cats.values() if c["slug"] == cat_slug), None) if _SLUG_RE.match(cat_slug) else None
        wanted = set()
        if target:
            wanted = {target["id"]}
            changed = True
            while changed:                                  # podkategorie (i neprime)
                changed = False
                for c in cats.values():
                    if c["parent_id"] in wanted and c["id"] not in wanted:
                        wanted.add(c["id"])
                        changed = True
        products = [p for p in products if p["category_id"] in wanted]
    total = len(products)
    return _respond({"products": products[offset:offset + limit], "total": total}, ctx)


@app.get("/api/miniweb/products/<int:product_id>")
@_guard
def miniweb_product(product_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            products, _cats = _visible_products(cur, ctx)
    finally:
        conn.close()
    item = next((p for p in products if p["id"] == product_id), None)
    if item is None:
        return _respond({"error": "not_found"}, None, 404)
    return _respond({"product": item}, ctx)


@app.get("/api/miniweb/legal")
@_guard
def miniweb_legal():
    """Pravni udaje prodejce: JEDINE misto s nazvem spolecnosti (zakonna identifikace prodejce, ne marketingovy text). Jen to, co patri na verejnou stranku: nazev, adresa, ICO, DIC, zeme jako kod
    (stranka si ji lokalizuje), BEZ osobniho e-mailu, telefonu, webu a uctu. Kontakt je neutralni kontakt shopu. Texty podminek, soukromi a vraceni dodava Robert (zatim prazdny seznam documents)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
    finally:
        conn.close()
    s = documents.SUPPLIER
    seller = {"name": s["name"], "address": ", ".join(x for x in (s.get("street"), s.get("city")) if x), "country_code": "CZ", "id": s.get("ico"), "vat_id": s.get("dic")}
    return _respond({"seller": seller, "contact": _contact(ctx["shop"]), "documents": []}, ctx)


# ---------------------------------------------------------------------------------------------------------------- endpoint: poptavka
def _inquiry_items(raw, visible_by_id):
    """Polozky poptavky z prohlizece -> overene polozky se SNIMKEM z databaze. Klient rozhoduje jen o poctu a konfiguraci, nikdy o nazvu, kodu a existenci produktu (neviditelny produkt = chyba).
    Cenu (unit_net apod.) server ignoruje - cenu urci nabidka."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > INQUIRY_MAX_ITEMS:
        raise ShopError(400, "items_invalid", "items")
    out = []
    for i, it in enumerate(raw):
        if not isinstance(it, dict):
            raise ShopError(400, "items_invalid", f"items[{i}]")
        pid, qty = _as_int(it.get("product_id")), _as_int(it.get("qty", 1))
        p = visible_by_id.get(pid)
        if p is None or qty is None or not 1 <= qty <= 99:
            raise ShopError(400, "items_invalid", f"items[{i}]")
        conf = it.get("configuration")
        config_json, config_hash = None, None
        if conf is not None:
            if not isinstance(conf, dict) or _too_deep(conf):
                raise ShopError(400, "items_invalid", f"items[{i}].configuration")
            try:
                dumped = _no_surrogates(json.dumps(conf, ensure_ascii=False, separators=(",", ":")))
            except (TypeError, ValueError, RecursionError):
                raise ShopError(400, "items_invalid", f"items[{i}].configuration")
            if len(dumped) > 6000:
                raise ShopError(400, "items_invalid", f"items[{i}].configuration")
            config_json = dumped
            h = conf.get("hash")
            config_hash = h if isinstance(h, str) and _HASH_RE.match(h) else None
        summary = []
        for s in (it.get("summary") if isinstance(it.get("summary"), list) else [])[:40]:
            if isinstance(s, dict):
                label, value = _plain(s.get("label"), 120), _plain(s.get("value"), 300)
                if label and value:
                    summary.append({"label": label, "value": value})
        out.append({"miniweb_product_id": pid, "public_sku": p["sku"], "product_name": p["name"], "qty": qty, "config_code": _plain(it.get("kod"), 60) or None,
                    "config_hash": config_hash, "config_json": config_json, "summary_json": json.dumps(summary, ensure_ascii=False) if summary else None})
    return out


def _staff_message(ctx, message, country, items, company):
    """Text prvni zpravy v CRM (pro zamestnance, cesky): zprava zakaznika a vycet polozek s konfiguraci."""
    lines = [message] if message else []
    meta = [x for x in (f"Firma: {company}" if company else "", f"Země: {country}" if country else "") if x]
    if meta:
        lines += ["", " | ".join(meta)]
    if items:
        lines += ["", f"--- Položky poptávky (mini-shop {ctx['host']}, jazyk {ctx['lang']}) ---"]
        for n, it in enumerate(items, 1):
            lines.append(f"{n}. {it['qty']}× {it['product_name']} ({it['public_sku']})" + (f", kód konfigurace {it['config_code']}" if it["config_code"] else ""))
            for s in json.loads(it["summary_json"]) if it["summary_json"] else []:
                lines.append(f"    - {s['label']}: {s['value']}")
    text = "\n".join(lines).strip()
    if len(text) > INQUIRY_MAX_MESSAGE:
        text = text[:INQUIRY_MAX_MESSAGE].rstrip() + "\n[…zkráceno, úplné položky jsou v tabulce miniweb_inquiry_items]"
    return text


def _confirmation(ctx, name):
    """(predmet, text) potvrzeni zakaznikovi do schvalovaci fronty, nebo None (pro jazyk shopu neni sablona). Bez znacky: misto domeny se znackou se pise 'our website'."""
    tpl = CONFIRMATION.get(ctx["lang"]) or CONFIRMATION.get(ctx["lang"].split("-")[0])
    if not tpl:
        return None
    site = ctx["host"] if ctx["host"] and not dealers._brand_hit(ctx["host"]) else "our website"
    return tpl[0], tpl[1].format(name=name, site=site)


@app.post("/api/miniweb/inquiry")
@_guard
def miniweb_inquiry():
    if _rate_limited(f"miniweb_inquiry:{_client_ip()}", *INQUIRY_LIMIT_PER_IP):
        return _respond({"error": "rate_limited"}, None, 429)
    if request.mimetype != "application/json":               # bariera proti cross-site formularum (ty nemohou poslat application/json bez preflightu)
        raise ShopError(400, "invalid_json")
    if (request.content_length or 0) > INQUIRY_MAX_BODY:
        return _respond({"error": "payload_too_large"}, None, 413)
    raw = request.stream.read(INQUIRY_MAX_BODY + 1)           # omezene cteni, nezavisle na Content-Length (chunked)
    if len(raw) > INQUIRY_MAX_BODY:
        return _respond({"error": "payload_too_large"}, None, 413)
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, RecursionError):                      # neplatny JSON, neplatne UTF-8, hluboce vnoreny JSON
        body = None
    if not isinstance(body, dict):
        raise ShopError(400, "invalid_json")
    if body.get("website"):                                   # honeypot: clovek ho nevidi, bot ano. Tvarime se, ze se povedlo, a nic neukladame
        return _respond({"status": "ok", "inquiry_id": 0}, None, 201)

    name = _plain(body.get("name"), 120)
    email = str(body.get("email") or "").strip().lower()
    phone = re.sub(r"[^0-9+()./ \-]", "", _plain(body.get("phone"), 40)).strip() or None
    company = _plain(body.get("company"), 160) or None
    country = str(body.get("country") or "").strip().upper() or None
    message = _plain(body.get("message"), 4000, multiline=True)
    if not name:
        raise ShopError(400, "name_required", "name")
    if len(email) > 254 or not _EMAIL_RE.match(email) or ".." in email:
        raise ShopError(400, "email_invalid", "email")
    if country is not None and not _COUNTRY_RE.match(country):
        raise ShopError(400, "country_invalid", "country")
    if body.get("consent") is not True:
        raise ShopError(400, "consent_required", "consent")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            if not ctx["shop"]["inquiry_enabled"]:
                raise ShopError(403, "inquiry_disabled")
            products, _cats = _visible_products(cur, ctx)
            items = _inquiry_items(body.get("items"), {p["id"]: p for p in products})
            if not message and not items:
                raise ShopError(400, "message_or_items_required", "message")
            if not ctx["live"]:                                # nahled pro staff: jen validace, nic se neuklada (zadna testovaci data v produkci)
                return _respond({"status": "ok", "inquiry_id": 0, "preview": True}, ctx, 201)
            cur.execute("SELECT COUNT(*) AS n FROM crm_leads WHERE source='miniweb' AND contact_email=%s AND created_at > NOW() - INTERVAL 1 DAY", (email,))
            if cur.fetchone()["n"] >= INQUIRY_LIMIT_PER_EMAIL_DAY:
                raise ShopError(429, "too_many_inquiries")

            cur.execute("SELECT id FROM shop_customers WHERE email=%s LIMIT 1", (email,))
            cust = cur.fetchone()
            subject = f"Poptávka z mini-shopu {ctx['host']}"[:500]
            cur.execute("INSERT INTO crm_leads (customer_id, contact_name, contact_email, contact_phone, company_name, subject, source, unread_by_admin) VALUES (%s,%s,%s,%s,%s,%s,'miniweb',1)",
                        (cust["id"] if cust else None, name, email, phone, company, subject))
            lead_id = cur.lastrowid
            cur.execute("INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) VALUES (%s,'contact',%s,%s)", (lead_id, name, _staff_message(ctx, message, country, items, company)))
            cur.execute("INSERT INTO miniweb_inquiries (storefront_id, shop_host, lang, crm_lead_id, country, consent_at) VALUES (%s,%s,%s,%s,%s,NOW())",
                        (ctx["sf"]["id"], ctx["host"][:255], ctx["lang"], lead_id, country))
            inquiry_id = cur.lastrowid
            for it in items:
                cur.execute("INSERT INTO miniweb_inquiry_items (inquiry_id, miniweb_product_id, public_sku, product_name, qty, config_code, config_hash, config_json, summary_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (inquiry_id, it["miniweb_product_id"], it["public_sku"], it["product_name"], it["qty"], it["config_code"], it["config_hash"], it["config_json"], it["summary_json"]))
            conf = _confirmation(ctx, name) if CONFIRMATION_ENABLED else None
            if conf:
                cur.execute("INSERT INTO system_emails (user_id, kind, recipient_email, subject, body_text, status, trigger_type) VALUES (NULL,'storefront_lead',%s,%s,%s,'pending','auto')", (email, conf[0], conf[1]))
                cur.execute("UPDATE miniweb_inquiries SET system_email_id=%s WHERE id=%s", (cur.lastrowid, inquiry_id))
        conn.commit()
    finally:
        conn.close()
    return _respond({"status": "ok", "inquiry_id": inquiry_id}, ctx, 201)
