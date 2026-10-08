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
  GET  /api/miniweb/legal              {seller, contact, documents[{kind, title, body, updated}]} - JEDINE misto, kde se objevi nazev spolecnosti (zakonna identifikace prodejce, Robert: prodejce zustava Logiman s.r.o.)
  POST /api/miniweb/inquiry            poptavka (JEN FIRMAM, Robert 2026-10-02: "vzdy jen firmam"): {name, email, phone?, company, company_id (ICO), vat_id? (DIC / IC DPH, nepovinne, kdyz je, kontroluje se syntaxe), country (u shopu s jedinou zemi dodani vychozi), message?, consent: true, b2b_confirm: true (potvrzeni, ze dopyt posila podnikatel), items?: [{product_id, qty, kod?, configuration?, summary?}], website: "" (honeypot)}
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
import jazyky
import miniweb_cena
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
# Pravni dokumenty shopu (podminky, soukromi, vraceni ...): po jazycich jako ostatni texty (import jako draft, schvaluje Robert), verejne jen schvalene, BEZ ZNACKY (prodejce je jen v legal.seller).
DOC_KINDS = ("terms", "privacy", "returns", "shipping", "cookies")           # povolene druhy, poradi = poradi ve vydani
DOC_MAX_TITLE = 200
DOC_MAX_BODY = 60000
# Zastupne znacky v navrzich dokumentu ([DOPLNIT: ...], [OVERIT: ...], "NAVRH k pravni kontrole"): dokument s nimi se NIKDY nevydava a nejde schvalit, dokud je nenahradi finalni verze po pravni kontrole.
_DOC_PLACEHOLDER_RE = re.compile(r"\[\s*(?:DOPLNI[TŤ]|OVERI[TŤ]|TODO)\b[^\]]{0,200}\]|n[aá]vrh\s+k\s+pr[aá]v(?:nej|n[ií])\s+kontrole", re.I)
CONFIRMATION = {
    "en": ("Inquiry received", "Dear {name},\n\nthank you for your inquiry via {site}.\n\nWe will get back to you shortly with further information.\n\nKind regards"),
}
jazyky.pripoj_potvrzeni(CONFIRMATION)                          # dalsi jazyky (sekce `potvrzeni` v api/jazyky/<jazyk>.json), jen kdyz ji sada ma


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


def _country_in(value):
    """Zeme z tela: nezadana (None, '') = None; retezec = velka pismena; cokoli jineho (objekt, cislo) = neplatna hodnota '?' (country_invalid), ne tise ignorovano."""
    if value is None or value == "":
        return None
    return value.strip().upper() or None if isinstance(value, str) else "?"


def _str_only(value):
    """Vstup z prohlizece smi byt jen retezec; objekt, pole, cislo a bool se berou jako nezadane (jinak by str() udelalo z objektu 'text')."""
    return value if isinstance(value, str) else ""


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
        # vnitrni cteni server-side SEO stranky (miniweb_seo.py, in-process test_client s WSGI klicem miniweb.interni - z HTTP ho nastavit nejde) nesdili limit navstevniku
        if not request.environ.get("miniweb.interni") and _rate_limited(f"miniweb:{_client_ip()}", READ_LIMIT_PER_MIN, 60):
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


def _doc_brand_hit(*texts):
    """Filtr znacky pro pravni dokumenty: jako jinde (dealers._brand_hit), JEN zakonny nazev prodejce (documents.SUPPLIER['name'], bez ohledu na velikost pismen a mezer) je povolen - zakonna identifikace
    prodejce v podminkach a zasadach, stejna vyjimka jako legal.seller. Kazdy jiny vyskyt znacky (samotne jmeno, konfigurator, dodavatel) dokument zablokuje."""
    name = (documents.SUPPLIER.get("name") or "").split()
    rest = list(texts)
    if name:
        rx = re.compile(r"\s+".join(re.escape(w) for w in name), re.I)
        rest = [rx.sub(" ", str(t or "")) for t in texts]
    return dealers._brand_hit(*rest)


def _doc_placeholder(*texts):
    return any(_DOC_PLACEHOLDER_RE.search(str(t or "")) for t in texts)


def _documents(cur, ctx):
    """Pravni dokumenty shopu v jazyce shopu ve stavech povolenych kontextem (verejnost jen schvalene, staff v nahledu i koncepty): presny jazyk ma prednost pred zakladnim, dokument se znackou
    se NEVYDAVA (fail closed), prazdny nazev ci text taky ne. -> [{kind, title, body, updated}] v poradi DOC_KINDS."""
    lph = ",".join(["%s"] * len(ctx["langs"]))
    sph = ",".join(["%s"] * len(ctx["statuses"]))
    cur.execute(f"SELECT * FROM miniweb_documents WHERE family=%s AND lang IN ({lph}) AND status IN ({sph})", [ctx["shop"]["family"]] + ctx["langs"] + ctx["statuses"])
    best = {}
    for r in cur.fetchall():
        lang = _clean_lang(r["lang"])
        if lang not in ctx["langs"] or r["kind"] not in DOC_KINDS:
            continue
        rank = ctx["langs"].index(lang)
        if r["kind"] not in best or rank < best[r["kind"]][0]:
            best[r["kind"]] = (rank, r)
    out = []
    for kind in DOC_KINDS:
        if kind not in best:
            continue
        r = best[kind][1]
        title, body = _plain(r["title"], DOC_MAX_TITLE), _plain(r["body"], DOC_MAX_BODY, multiline=True)
        if title and body and not _doc_brand_hit(title, body) and not _doc_placeholder(title, body):
            when = r["approved_at"] if r["status"] == "approved" and r["approved_at"] else r["updated_at"]
            out.append({"kind": kind, "title": title, "body": body, "updated": when.date().isoformat() if when else None})
    return out


def _url_slug(t, base):
    """Slug v jazyce shopu (bot5, 2026-10-03; SEO adresy po jazycich): url_slug z textu (schvaluje se spolu s textem), kdyz je platny a bez znacky, jinak zakladni slug (jazykove neutralni identita)."""
    v = (t or {}).get("url_slug")
    return v if isinstance(v, str) and _SLUG_RE.match(v) and not dealers._brand_hit(v) else base


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
            if name and not dealers._brand_hit(name, r["slug"], _url_slug(t, r["slug"])):
                ok = r["parent_id"] is None or visible(r["parent_id"], seen + (cid,))
        memo[cid] = ok
        return ok

    out = {}
    for cid, r in rows.items():
        if visible(cid):
            out[cid] = {"id": cid, "parent_id": r["parent_id"], "slug": _url_slug(texts[cid], r["slug"]), "base_slug": r["slug"], "name": _plain(texts[cid]["name"], 200), "sort_order": r["sort_order"], "text_status": texts[cid]["status"]}
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


def _system_karty(p):
    """System profilu (30 | 40) konfigurovatelneho stolu podle karty produktu (stul_shop.system_pro_produkt, bot10 2026-10-04); pri chybe 30."""
    try:
        import stul_shop
        return stul_shop.system_pro_produkt(p["shop_product_id"])
    except Exception:
        return 30


def _price_from(p, shop):
    """Cena konfigurace pro produkt v EUR bez DPH (celé EUR) pro shop s price_mode 'shown', jinak None (kurz, marže a zaokrouhlení v miniweb_cena, nic natvrdo)."""
    if shop["price_mode"] != "shown" or not p["configurator_available"]:
        return None
    cfg = miniweb_cena.nastaveni(shop)
    if cfg is None:
        return None
    try:
        import stul_shop
        czk = ((stul_shop.pro_objednavku({}, None, "cs", p["shop_product_id"]) or {}).get("price") or {}).get("net")
    except Exception:
        return None
    return miniweb_cena.cena_eur(czk, cfg)


STUL_PROFIL_GROOVE_FAMILY = "8"           # drazka profilu konfigurovatelneho stolu (system 30): Robert 2026-10-03 (klik: 8 mm); v konfiguratoru ani na karte zapsana neni, prurez 30x30 se bere z konfiguratoru
STUL_PROFIL_GROOVE_FAMILY_40 = "10"       # system 40 (SuperLight S10) a system 41 (stul SSE, podelniky Object_11 = tentyz profil): drazka 10 mm; systemy 30 a 35 (profil 35x35) maji drazku 8 mm


def _profil_info(p):
    """Stitky profilu pro konfigurovatelny stul (bot3 2026-10-03: groove_family, cross_section_label, profil_mm; nic jineho): prurez z konfiguratoru stolu (cfg_dily Object_7 = profil; 35: profil_35x35), drazka z konstanty.
    Jen u produktu s konfiguratorem a jen kdyz je prurez ctvercovy a znamy; jinak nic."""
    if not p["configurator_available"]:
        return {}
    try:
        import stul_api
        import stul_konfigurator
        system = _system_karty(p)
        a, b = stul_api._ctx_ceny()["parts"][stul_konfigurator.SYSTEMY[system]["profil"]]["cross_section_mm"]       # system 30: Object_7, system 40: Object_11
        if a is None or b is None or float(a) != float(b) or float(a) <= 0:
            return {}
        mm = int(round(float(a)))
    except Exception:
        return {}
    return {"groove_family": STUL_PROFIL_GROOVE_FAMILY_40 if system in (40, stul_konfigurator.SYSTEM_45, stul_konfigurator.SYSTEM_SSE) else STUL_PROFIL_GROOVE_FAMILY, "cross_section_label": f"{mm}\u00d7{mm}", "profil_mm": mm}


def _product_json(p, t, ctx, shop):
    """Produkt v tvaru z demo-api.js, nebo None (bez nazvu / se znackou v kterekoli z vydavanych hodnot = skryt, fail closed)."""
    name, summary = _plain(t["name"], 200), _plain(t["summary"], 500)
    description, delivery = _plain(t["description"], 4000, multiline=True), _plain(t["delivery"], 255)
    specs = _specs(t["specs_json"])
    slug = _url_slug(t, p["slug"])
    if not name or dealers._brand_hit(name, summary, description, delivery, p["slug"], slug, p["public_sku"], *[x for s in specs for x in (s["name"], s["value"])]):
        return None
    available = bool(p["configurator_available"])
    item = {"id": p["id"], "slug": slug, "slug_alt": [p["slug"]] if p["slug"] != slug else [], "sku": p["public_sku"], "category_id": p["category_id"], "name": name, "summary": summary, "description": description,
            "price_from": _price_from(p, shop), "currency": _currency(shop), "delivery": delivery,
            "configurator": {"available": available, "default_view": p["default_view"], "product_id": p["shop_product_id"] if available else None}, "specs": specs, **_profil_info(p)}
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


def _seller(info, supplier):
    """Zakonna identifikace prodejce z nastaveni spolecnosti (app_settings company_info, JEDEN zdroj jako kontakt; externi revize 2026-10-03, #4), chybejici pole doplni documents.SUPPLIER.
    Adresa bez koncove zeme (zeme je v country_code). Nazev se dal prochazi stejnymi filtry jako dosud (filtr znacky se nemeni)."""
    addr = _plain(info.get("address"), 200)
    country = (supplier.get("country") or "").strip()
    if country and addr.endswith(", " + country):
        addr = addr[: -len(country) - 2]
    return {"name": _plain(info.get("name"), 200) or supplier["name"], "address": addr or ", ".join(x for x in (supplier.get("street"), supplier.get("city")) if x),
            "country_code": "CZ", "id": _plain(info.get("ico"), 40) or supplier.get("ico"), "vat_id": _plain(info.get("dic"), 40) or supplier.get("dic")}


def _company_contact(cur):
    """Jmeno, adresa a telefon spolecnosti z JEDNOHO zdroje na serveru: nastaveni spolecnosti (app_settings company_info, editovatelne v adminu, vychozi hodnoty v api/company_info.py; z nej se plni i
    verejna stranka kontakt.html). Nikdy e-mail ani web."""
    import company_info                                    # lazy: modul se registruje az na konci app.py
    info = company_info._get_company_info(cur)
    return {"name": _plain(info.get("name"), 200), "address": _plain(info.get("address"), 200), "phone": _plain(info.get("phone"), 40)}


def _contact(shop, cur=None):
    """Kontakt shopu: telefon a doba z contact_json (kazde pole bez znacky, e-mail se NIKDY nevydava). Kdyz contact_json nese "use_company": true (Robert 2026-10-02: "dej tam prostě moje kontaktní údaje")
    a je k dispozici kurzor, prida se z JEDNOHO zdroje (nastaveni spolecnosti, viz _company_contact) jmeno, adresa a telefon; to jsou udaje prodejce (zakonna identifikace jako legal.seller), proto bez
    filtru znacky, telefon ze spolecnosti ma prednost pred telefonem z radku shopu. Nikdy e-mail ani web spolecnosti."""
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
    if raw.get("use_company") is True and cur is not None:
        firma = _company_contact(cur)
        out["name"], out["address"] = firma["name"], firma["address"]
        out["phone"] = firma["phone"] or out.get("phone", "")
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
            contact = _contact(shop, cur)
    finally:
        conn.close()
    accent = shop["accent"] if shop["accent"] and _ACCENT_RE.match(shop["accent"]) else None
    countries = [c for c in (x.strip().upper() for x in (shop["countries"] or "").split(",")) if _COUNTRY_RE.match(c)]
    locale = shop["locale"] if shop["locale"] and _LOCALE_RE.match(shop["locale"]) else ctx["lang"]
    return _respond({"shop": _shop_slug(sf), "lang": ctx["lang"], "locale": locale, "currency": _currency(shop), "accent": accent, "countries": countries,
                     "contact": contact, "price_mode": shop["price_mode"], "checkout_mode": "order" if shop.get("orders_enabled") else "inquiry", "inquiry_only": not shop.get("orders_enabled"), "inquiry_enabled": bool(shop["inquiry_enabled"]), "alternates": alternates,
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
    return _respond({"categories": [{"id": c["id"], "parent_id": c["parent_id"], "slug": c["slug"], "slug_alt": [c["base_slug"]] if c["base_slug"] != c["slug"] else [], "name": c["name"], "count": counts[c["id"]]} for c in ordered]}, ctx)


@app.get("/api/miniweb/products")
@_guard
def miniweb_products():
    try:
        limit = min(MAX_LIMIT, max(1, int(request.args.get("limit", DEFAULT_LIMIT))))
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        return _respond({"error": "bad_request"}, None, 400)
    cat_slug = request.args.get("category")
    prod_slug = request.args.get("slug")                     # detail podle slugu (jazykovy nebo zakladni) BEZ ohledu na limit seznamu (externi revize 2026-10-03, #10)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            products, cats = _visible_products(cur, ctx)
    finally:
        conn.close()
    if prod_slug is not None:
        products = [p for p in products if _SLUG_RE.match(prod_slug) and prod_slug in [p["slug"]] + p["slug_alt"]]
    if cat_slug:
        target = next((c for c in cats.values() if cat_slug in (c["slug"], c["base_slug"])), None) if _SLUG_RE.match(cat_slug) else None
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
    (stranka si ji lokalizuje), BEZ osobniho e-mailu, telefonu, webu a uctu. Kontakt je neutralni kontakt shopu. `documents` = schvalene pravni dokumenty shopu v jazyce shopu (podminky, soukromi, vraceni ...; import a schvaleni jako ostatni texty), bez znacky."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            docs = _documents(cur, ctx)
            contact = _contact(ctx["shop"], cur)
            import company_info                                # lazy: modul se registruje az na konci app.py
            info = company_info._get_company_info(cur)
    finally:
        conn.close()
    s = documents.SUPPLIER
    seller = _seller(info, s)
    return _respond({"seller": seller, "contact": contact, "documents": docs}, ctx)


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


_ID_STRIP_RE = re.compile(r"[\s.\-/]")
_VAT_RE = {"SK": re.compile(r"^(SK)?[0-9]{10}\Z"), "CZ": re.compile(r"^(CZ)?[0-9]{8,10}\Z")}
_VAT_GENERIC_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{2,12}\Z")


def _norm_id(value):
    return _ID_STRIP_RE.sub("", str(value or "")).upper()[:40]


def _company_ids(raw_id, raw_vat, country):
    """Udaje firmy z poptavky (mini-shopy prodavaji JEN podnikatelum, Robert 2026-10-02: "vzdy jen firmam"): ICO je povinne (CZ a SK 6 az 8 cislic, doplni se nulami na 8; jinde 4 az 20 znaku), DIC / IC DPH je
    NEPOVINNE (pro dodani bez DPH v ramci EU), kdyz je zadane, kontroluje se syntax (SK: DIC 10 cislic nebo IC DPH SK a 10 cislic; CZ: 8 az 10 cislic s prefixem CZ nebo bez; jinde prefix zeme a 2 az 12 znaku).
    Overeni ve VIES a v registrech je OTEVRENY BOD (jen syntaxe). -> (ico, dic nebo None), jinak ShopError company_id_required / company_id_invalid / vat_id_invalid."""
    ico = _norm_id(raw_id)
    if not ico:
        raise ShopError(400, "company_id_required", "company_id")
    if not ico.strip("0"):                                                   # same nuly neni ICO (externi revize 2026-10-03, #16)
        raise ShopError(400, "company_id_invalid", "company_id")
    if country in ("CZ", "SK"):
        if not re.fullmatch(r"[0-9]{6,8}", ico):
            raise ShopError(400, "company_id_invalid", "company_id")
        ico = ico.zfill(8)
    elif not re.fullmatch(r"[A-Z0-9]{4,20}", ico):
        raise ShopError(400, "company_id_invalid", "company_id")
    vat = _norm_id(raw_vat)
    if not vat:
        return ico, None
    rx = _VAT_RE.get(country)
    ok = bool(rx.match(vat)) if rx else bool(_VAT_GENERIC_RE.match(vat) and vat[:2] == ("EL" if country == "GR" else country))
    if not ok:
        raise ShopError(400, "vat_id_invalid", "vat_id")
    return ico, vat


def _staff_message(ctx, message, country, items, company, ico=None, vat=None):
    """Text prvni zpravy v CRM (pro zamestnance, cesky): zprava zakaznika, udaje firmy (IČO a DIČ ve tvaru, ktery CRM umi vycist pri prevodu na zakaznika) a vycet polozek s konfiguraci."""
    lines = [message] if message else []
    meta = [x for x in (f"Firma: {company}" if company else "", f"IČO: {ico}" if ico else "", f"DIČ/IČ DPH: {vat}" if vat else "", f"Země: {country}" if country else "") if x]
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

    name = _plain(_str_only(body.get("name")), 120)                     # jen retezce: objekt, cislo ani pole neprojdou jako text (kontrola externi revize 2026-10-03, #16)
    email = _str_only(body.get("email")).strip().lower()
    phone = re.sub(r"[^0-9+()./ \-]", "", _plain(_str_only(body.get("phone")), 40)).strip() or None
    company = _plain(_str_only(body.get("company")), 160)
    country = _country_in(body.get("country"))
    message = _plain(_str_only(body.get("message")), 4000, multiline=True)
    if not name:
        raise ShopError(400, "name_required", "name")
    if len(email) > 254 or not _EMAIL_RE.match(email) or ".." in email:
        raise ShopError(400, "email_invalid", "email")
    if country is not None and not _COUNTRY_RE.match(country):
        raise ShopError(400, "country_invalid", "country")
    if not company:
        raise ShopError(400, "company_required", "company")
    if body.get("consent") is not True:
        raise ShopError(400, "consent_required", "consent")
    if body.get("b2b_confirm") is not True:                    # mini-shopy prodavaji jen podnikatelum: zakaznik potvrzuje, ze poptavku posila jmenem firmy
        raise ShopError(400, "b2b_confirm_required", "b2b_confirm")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ctx = _shop_context(cur)
            if not ctx["shop"]["inquiry_enabled"]:
                raise ShopError(403, "inquiry_disabled")
            countries = [c for c in (x.strip().upper() for x in (ctx["shop"]["countries"] or "").split(",")) if _COUNTRY_RE.match(c)]
            if country is None and len(countries) == 1:                   # shop s jedinou zemi dodani (napr. SK): zeme zakaznika je znama
                country = countries[0]
            if country is None:
                raise ShopError(400, "country_required", "country")
            if countries and country not in countries:                    # jako objednavka: zeme musi byt v seznamu zemi shopu (externi revize 2026-10-03, #14)
                raise ShopError(400, "country_invalid", "country")
            company_id, vat_id = _company_ids(_str_only(body.get("company_id")), _str_only(body.get("vat_id")), country)
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
            cur.execute("INSERT INTO crm_lead_messages (lead_id, sender_type, sender_name, body) VALUES (%s,'contact',%s,%s)", (lead_id, name, _staff_message(ctx, message, country, items, company, company_id, vat_id)))
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
