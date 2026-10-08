"""Dealersky program - jadro etapy 1 (bot5, 2026-10-02; zadani Robert pres bot3, TASKS.md "ZADANO 2026-10-02 ... dealersky program").

Dealer prodava nase bezne produkty a dily na svem webu. Dve cesty objednavky (dealer si vybere, dealers.order_path):
  our    = zakaznik dokonci objednavku U NAS po prokliku z odkazu dealera -> provize dealerovi (etapa 1, krok 2+),
  dealer = objednavka se dokonci NA WEBU DEALERA, dealer ji zada u nas (API/panel) za dealerskou cenu, zadna provize (krok 4).

Tenhle soubor (krok 1) obsahuje:
  * pomocne funkce klicu a domen, DealerAuthError, resolve_public_key / resolve_secret_key (jedine misto, kde se overuje klic dealera),
  * dealer_product_view (JEDINA projekce produktu pro dealery: widget i feed, fail-closed, bez znacky, bez 3D, bez nakladu),
  * ceny dealera (dealer_discount_pct / dealer_commission_pct / dealer_effective_price),
  * atribuce: GET /api/dealer/go/<ref_code> (proklik, cookie dlr 30 dni, last-click) + attach_attribution pro orders_create,
  * administrace dealeru (/api/admin/dealers*, sekce dealeri / dealer_klice) a partnersky panel (/api/dealer/me|keys|domains).
Provize, vyuctovani, objednavka z webu dealera a feed pridavaji dalsi kroky (dealer_commissions.py, dealer_orders.py, dealer_feed.py).

Pravidla, ktera tu platila pri navrhu (nemenit bez Roberta):
  * dealerskou cenu ani prirazku dealera NIKDY verejne (dealer_product_view mode=dealer_final vraci jen vysledek, pri nejasnosti produkt vynecha),
  * zadna znacka (Logiman/konfigurator/vandrawee, dodavatel profilu) v textech pro dealery (TEXT_FILTR pravidlo 5): pole se znackou = produkt se
    VYNECHA (fail closed), v etape 1 jen bezne produkty a dily - zadne sestavy (VD-*, product_assemblies), zadne rendery/otocky, nikdy glb,
  * klic v DB jen jako hash (sha256), tajna cast se ukaze jednou, srovnani konstantnim casem, /api/dealer/* bez CORS a s Cache-Control no-store,
  * nic se nemaze (FK RESTRICT, is_active), odchozi e-maily tenhle modul neposila vubec.
"""
import datetime
import hashlib
import hmac
import html
import json
import re
import secrets
import urllib.parse
from decimal import Decimal

from flask import request, jsonify, redirect

from app import (app, get_conn, require_permission, current_user, login_required, log_audit, get_setting,
                 _client_ip, _rate_limited)

DEALER_STATUSES = ("pending", "active", "suspended")
ORDER_PATHS = ("our", "dealer")
KEY_KINDS = ("widget", "api", "feed")
KEY_SCOPES = ("feed", "quote", "orders")
CLICK_COOKIE = "dlr"
DEFAULT_COMMISSION_PCT = 10.0       # app_settings.dealer_commission_default_pct, kdyz neni nastaveno
DEFAULT_ATTRIBUTION_DAYS = 30       # app_settings.dealer_attribution_days
MAX_ACTIVE_KEYS_PER_KIND = 5        # na dealera, kvuli panelu (self-service)
ROTATE_OVERLAP_DAYS = 7             # stary klic po rotaci plati jeste tuhle dobu
_REF_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"      # bez 0 o 1 l i
_PK_RE = re.compile(r"^pk_[0-9a-f]{24}$")
_SECRET_RE = re.compile(r"^(sk|ft)_([0-9a-f]{8})_([A-Za-z0-9_-]{32,64})$")
_REF_RE = re.compile(r"^[a-z0-9]{6,16}$")
_CLICK_TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_BOT_UA_RE = re.compile(r"bot|crawl|spider|slurp|facebookexternalhit|preview|headless|monitor|curl|wget|python-requests|scrapy", re.I)
# znacka a dodavatel: pole s nalezem se pro dealery VYNECHA (qa_checks._STOREFRONT_BRAND_RE + dodavatel profilu a Vandr)
_BRAND_RE = re.compile(r"logiman|konfigur[aá]tor|vandrawee|vandr|dogus", re.I)

PERMISSION_DEALERI = "dealeri"
PERMISSION_KLICE = "dealer_klice"


# ---------------------------------------------------------------------------------------------------------------- pomocne
def _now():
    return datetime.datetime.now()


def _ser(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def _ser_row(row):
    return {k: _ser(v) for k, v in dict(row).items()} if row else row


def _clean(value, max_len):
    if value is None:
        return None
    s = str(value).strip()
    return s[:max_len] if s else None


def _pct(value):
    """Procento 0-100 na 2 desetinna mista, None = nezadano. ValueError pri nesmyslu (volajici vrati 400)."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("Procento musí být číslo od 0 do 100.")
    try:
        v = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("Procento musí být číslo od 0 do 100.")
    if v != v or v < 0 or v > 100:
        raise ValueError("Procento musí být číslo od 0 do 100.")
    return round(v, 2)


def _setting_float(cur, key, default):
    try:
        v = float(get_setting(cur, key, str(default)))
        return v if v >= 0 else float(default)
    except (TypeError, ValueError):
        return float(default)


def attribution_days(cur):
    return int(_setting_float(cur, "dealer_attribution_days", DEFAULT_ATTRIBUTION_DAYS))


def _no_store(resp):
    resp.headers["Cache-Control"] = "private, no-store"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _json(payload, status=200):
    resp = jsonify(payload)
    resp.status_code = status
    return _no_store(resp)


def _err(message, code, status):
    return _json({"error": message, "code": code}, status)


# ---------------------------------------------------------------------------------------------------------------- klice
def new_widget_key():
    """Verejny klic widgetu (pk_ + 24 hex) - patri do kodu na webu dealera, nic tajneho nechrani."""
    return "pk_" + secrets.token_hex(12)


def new_secret_key(kind):
    """-> (public_id, secret, cely_token). kind 'api' (sk_) nebo 'feed' (ft_). Token se ukaze jednou, v DB je jen sha256(secret)."""
    prefix = {"api": "sk", "feed": "ft"}[kind]
    public_id = f"{prefix}_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    return public_id, secret, f"{public_id}_{secret}"


def hash_secret(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def parse_secret_token(token):
    """'sk_ab12cd34_<tajna>' -> (public_id, secret) nebo None."""
    m = _SECRET_RE.match((token or "").strip())
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}", m.group(3)


def bearer_token(authorization):
    a = (authorization or "").strip()
    if a.lower().startswith("bearer "):
        a = a[7:].strip()
    return a


# ---------------------------------------------------------------------------------------------------------------- domeny
_DOMAIN_RE = re.compile(r"^(\*\.)?([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+([a-z]{2,63}|xn--[a-z0-9-]{2,59})$")


def normalize_domain(value):
    """'https://Www.Example.cz:8080/cesta' -> 'www.example.cz'; '*.example.cz' = jen subdomeny; IDN -> punycode; jinak None."""
    s = (value or "").strip().lower()
    if not s:
        return None
    wildcard = s.startswith("*.")
    if wildcard:
        s = s[2:]
    if "://" in s:
        s = urllib.parse.urlsplit(s).netloc
    s = s.split("/")[0].split("?")[0].split("#")[0]
    s = s.rsplit("@", 1)[-1]
    if s.count(":") == 1:
        s = s.split(":")[0]
    s = s.strip(".")
    if not s or len(s) > 253:
        return None
    try:
        s = s.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    s = ("*." if wildcard else "") + s
    return s if _DOMAIN_RE.match(s) else None


def origin_host(origin):
    """Hlavicka Origin ('https://shop.example.cz:8443') -> 'shop.example.cz' (punycode, male), jinak None. 'null' a IP adresy se nepousti."""
    o = (origin or "").strip()
    if not o or o.lower() == "null" or "://" not in o:
        return None
    host = urllib.parse.urlsplit(o).hostname
    if not host:
        return None
    n = normalize_domain(host)
    return n if n and not n.startswith("*.") else None


def domain_matches(host, domain):
    """Presna shoda, nebo 'domain' ve tvaru '*.example.cz' (jen subdomeny, samotne example.cz musi byt uvedene zvlast)."""
    if not host or not domain:
        return False
    if domain.startswith("*."):
        return host.endswith(domain[1:]) and host != domain[2:]
    return host == domain


# ---------------------------------------------------------------------------------------------------------------- overeni klice
class DealerAuthError(Exception):
    """status = HTTP stav, code = kratky stroje citelny kod (invalid_key, dealer_inactive, origin_missing, origin_not_allowed, scope_denied,
    ip_not_allowed, rate_limited). Pro tajne klice (api/feed) se neznamy/odvolany/spatny klic vzdy hlasi stejne jako invalid_key."""
    MESSAGES = {
        "invalid_key": "Neplatný klíč.",
        "dealer_inactive": "Účet dealera není aktivní.",
        "origin_missing": "Chybí hlavička Origin.",
        "origin_not_allowed": "Doména není u dealera povolená.",
        "scope_denied": "Klíč nemá oprávnění pro tuhle akci.",
        "ip_not_allowed": "IP adresa není u klíče povolená.",
        "rate_limited": "Příliš mnoho požadavků.",
    }

    def __init__(self, status, code, message=None):
        super().__init__(message or self.MESSAGES.get(code, code))
        self.status = status
        self.code = code
        self.message = message or self.MESSAGES.get(code, code)

    def response(self):
        resp = _err(self.message, self.code, self.status)
        if self.status == 429:
            resp.headers["Retry-After"] = "60"
        return resp


def _dealer_usable(dealer):
    return bool(dealer) and dealer["status"] == "active" and bool(dealer["is_active"])


def _key_usable(key, now):
    if not key["is_active"] or key["revoked_at"] is not None:
        return False
    return key["expires_at"] is None or key["expires_at"] > now


def _load_key(cur, public_id):
    cur.execute("SELECT * FROM dealer_keys WHERE public_id=%s", (public_id,))
    return cur.fetchone()


def _load_dealer(cur, dealer_id):
    cur.execute("SELECT * FROM dealers WHERE id=%s", (dealer_id,))
    return cur.fetchone()


def _touch_key(cur, key, ip, now):
    """last_used_at/ip nejvyse jednou za minutu (zapis do DB nesmi pribyt na kazdy pozadavek)."""
    last = key.get("last_used_at")
    if last is None or (now - last).total_seconds() >= 60:
        cur.execute("UPDATE dealer_keys SET last_used_at=%s, last_used_ip=%s WHERE id=%s", (now, (ip or "")[:45], key["id"]))


def _rate_check(key, ip):
    if _rate_limited(f"dealer_key:{key['id']}", int(key.get("rate_per_min") or 120), 60):
        raise DealerAuthError(429, "rate_limited")
    if _rate_limited(f"dealer_key_ip:{ip}", 600, 60):
        raise DealerAuthError(429, "rate_limited")


def _with_cursor(cur, fn):
    """Kdyz volajici da cur, pouzije se (cte se, nezapisuje a necommituje). Jinak vlastni kratke spojeni se zapisem last_used."""
    if cur is not None:
        return fn(cur, False)
    conn = get_conn()
    try:
        with conn.cursor() as c:
            out = fn(c, True)
        conn.commit()
        return out
    finally:
        conn.close()


def resolve_public_key(pk, origin, ip, cur=None):
    """Overeni VEREJNEHO klice widgetu (pk_...). -> (dealer, key) nebo DealerAuthError.
    Kontroluje: tvar klice, aktivni nevypresly klic druhu widget, aktivniho dealera, hlavicku Origin proti dealer_domains (presne nebo *.domena),
    limit pozadavku na klic a na IP. Volat PRED otevrenim vlastniho spojeni, nebo predat cur (pak se nic nezapisuje a necommituje)."""
    pk = (pk or "").strip()
    if not _PK_RE.match(pk):
        raise DealerAuthError(401, "invalid_key")
    now = _now()

    def run(c, write):
        key = _load_key(c, pk)
        if not key or key["kind"] != "widget" or not _key_usable(key, now):
            raise DealerAuthError(401, "invalid_key")
        dealer = _load_dealer(c, key["dealer_id"])
        if not _dealer_usable(dealer):
            raise DealerAuthError(403, "dealer_inactive")
        host = origin_host(origin)
        if not host:
            raise DealerAuthError(403, "origin_missing")
        c.execute("SELECT domain FROM dealer_domains WHERE dealer_id=%s AND is_active=1", (dealer["id"],))
        if not any(domain_matches(host, r["domain"]) for r in c.fetchall()):
            raise DealerAuthError(403, "origin_not_allowed")
        _rate_check(key, ip)
        if write:
            _touch_key(c, key, ip, now)
        return dealer, key

    return _with_cursor(cur, run)


def resolve_secret_key(authorization, ip, scope=None, cur=None):
    """Overeni TAJNEHO klice (Authorization: Bearer sk_.../ft_...). -> (dealer, key) nebo DealerAuthError.
    Neznamy, odvolany, vypresly i spatny klic se hlasi stejne (401 invalid_key). Kontroluje aktivniho dealera, scope, volitelny seznam IP a limit."""
    parsed = parse_secret_token(bearer_token(authorization))
    if not parsed:
        raise DealerAuthError(401, "invalid_key")
    public_id, secret = parsed
    now = _now()

    def run(c, write):
        key = _load_key(c, public_id)
        ok = bool(key) and key["kind"] in ("api", "feed") and key["secret_hash"] is not None
        # konstantni cas i pro neexistujici klic (porovnava se s nulovym hashem)
        expected = key["secret_hash"] if ok else "0" * 64
        hash_ok = hmac.compare_digest(hash_secret(secret), expected)
        if not (ok and hash_ok and _key_usable(key, now)):
            raise DealerAuthError(401, "invalid_key")
        dealer = _load_dealer(c, key["dealer_id"])
        if not _dealer_usable(dealer):
            raise DealerAuthError(403, "dealer_inactive")
        scopes = {s.strip() for s in (key["scopes"] or "").split(",") if s.strip()}
        if scope and scope not in scopes:
            raise DealerAuthError(403, "scope_denied")
        allowed = {s.strip() for s in re.split(r"[\s,;]+", key["allowed_ips"] or "") if s.strip()}
        if allowed and ip not in allowed:
            raise DealerAuthError(403, "ip_not_allowed")
        _rate_check(key, ip)
        if write:
            _touch_key(c, key, ip, now)
        return dealer, key

    return _with_cursor(cur, run)


# ---------------------------------------------------------------------------------------------------------------- kategorie a sazby
def _category_chain(cur, category_id):
    """[category_id, rodic, prarodic, ...] (nejblizsi prvni) + priznak, zda je nejaka z nich neviditelna."""
    chain, hidden, seen = [], False, set()
    cid = category_id
    while cid and cid not in seen and len(chain) < 12:
        seen.add(cid)
        cur.execute("SELECT id, parent_id, name, is_visible FROM content_categories WHERE id=%s", (cid,))
        row = cur.fetchone()
        if not row:
            break
        chain.append(row)
        hidden = hidden or not row["is_visible"]
        cid = row["parent_id"]
    return chain, hidden


def _category_rate(cur, dealer_id, category_id, column):
    """Sazba (discount_pct | commission_pct) pro kategorii: nejblizsi nadrazena kategorie, ktera ma pro dealera nastavenou nenulovou (NOT NULL) hodnotu."""
    if column not in ("discount_pct", "commission_pct"):
        raise ValueError(column)
    chain, _hidden = _category_chain(cur, category_id)
    for cat in chain:
        cur.execute(f"SELECT {column} AS v FROM dealer_rates WHERE dealer_id=%s AND category_id=%s", (dealer_id, cat["id"]))
        row = cur.fetchone()
        if row and row["v"] is not None:
            return float(row["v"])
    return None


def dealer_commission_pct(cur, dealer, category_id):
    """Provize v % pro dealera a kategorii: sazba kategorie (nejblizsi nadrazena) > vychozi dealera > app_settings (10)."""
    v = _category_rate(cur, dealer["id"], category_id, "commission_pct") if category_id else None
    if v is None and dealer.get("default_commission_pct") is not None:
        v = float(dealer["default_commission_pct"])
    if v is None:
        v = _setting_float(cur, "dealer_commission_default_pct", DEFAULT_COMMISSION_PCT)
    return v


def dealer_discount_pct(cur, dealer, product):
    """Dealerska sleva v % pro produkt: sazba primo na produktu (shop_products.dealer_discount_percent, existujici pole) > sazba kategorie
    (nejblizsi nadrazena) > vychozi dealera. None = dealer pro tenhle produkt nema cenu (nemuze objednat, ve widgetu dealer_final se produkt vynecha)."""
    own = product.get("dealer_discount_percent")
    if own is not None and float(own) > 0:
        return float(own)
    v = _category_rate(cur, dealer["id"], product.get("category_id"), "discount_pct") if product.get("category_id") else None
    if v is None and dealer.get("default_discount_pct") is not None:
        v = float(dealer["default_discount_pct"])
    return v


def dealer_effective_price(cur, product, dealer):
    """-> (cena_bez_dph, zaklad) nebo (None, None). Dealerska cena = cena z ceniku x (1 - sleva), ale NIKDY vic nez bezna akcni cena (platí
    jedna nejnizsi z vzajemne vylucnych cen, skupinova sleva a kupon se u dealera neuplatni). zaklad: 'dealer' | 'sale'."""
    import products as _products
    pct = dealer_discount_pct(cur, dealer, product)
    if pct is None or product.get("price_czk_placeholder") is None:
        return None, None
    list_price = float(product["price_czk_placeholder"])
    dealer_price = round(list_price * (1 - pct / 100.0), 2)
    retail, basis = _products._effective_unit_price(cur, product, user=None)
    if retail is not None and float(retail) < dealer_price:
        return float(retail), basis
    return dealer_price, "dealer"


# ---------------------------------------------------------------------------------------------------------------- pohled na produkt
_PRODUCT_COLUMNS = ("id, sku, name, slug, description, unit, price_czk_placeholder, sale_price_czk, sale_price_from, sale_price_until, "
                    "dealer_discount_percent, weight_g, length_mm, width_mm, height_mm, stock_qty, availability_text, is_board_material, "
                    "board_sheet_width_mm, board_sheet_height_mm, category_id, active, is_archived, zalozeno_automaticky_typologie_id")


def _plain_text(value, limit=2000):
    s = re.sub(r"<[^>]+>", " ", str(value or ""))
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


def _brand_hit(*texts):
    return any(t and _BRAND_RE.search(str(t)) for t in texts)


def _is_assembly_product(cur, product):
    """Sestavy (karty s product_assemblies, Vandr VD-*, automaticky zalozene karty typologii) se dealerum v etape 1 NENABIZEJI (rendery az v etape 2)."""
    sku = str(product.get("sku") or "")
    if sku.upper().startswith("VD-") or product.get("zalozeno_automaticky_typologie_id"):
        return True
    cur.execute("SELECT 1 AS x FROM product_assemblies WHERE shop_product_id=%s LIMIT 1", (product["id"],))
    return cur.fetchone() is not None


def dealer_product_view(cur, product, mode="retail", dealer=None, markup_pct=None):
    """Projekce produktu pro dealery (widget i feed) - JEDINA, whitelist poli, FAIL CLOSED: vraci None, kdyz produkt nesmi ven.
    product = id nebo radek shop_products (vzdy se nacte znovu z DB, caller nic neurcuje). mode:
      'retail'       - bezna verejna cena (bez i s DPH), tak jak ji vidi zakaznik v e-shopu,
      'none'         - bez ceny,
      'dealer_final' - dealerska cena x (1 + markup_pct/100) = cena na webu dealera; do vysledku jde JEN tahle cena (ani dealerska cena,
                       ani prirazka), vyzaduje dealer a markup_pct, jinak se produkt vynecha.
    Nikdy: glb/fbx, dodavatel, naklady, interni poznamky, zdrojove URL obrazku, presny sklad."""
    if mode not in ("retail", "none", "dealer_final"):
        raise ValueError("neznamy mode")
    pid = int(product["id"] if isinstance(product, dict) else product)
    cur.execute(f"SELECT {_PRODUCT_COLUMNS} FROM shop_products WHERE id=%s", (pid,))
    p = cur.fetchone()
    if not p or not p["active"] or p["is_archived"]:
        return None
    if p["price_czk_placeholder"] is None or float(p["price_czk_placeholder"]) <= 0:
        return None
    if _is_assembly_product(cur, p):
        return None
    chain, hidden = _category_chain(cur, p["category_id"]) if p["category_id"] else ([], False)
    if hidden:
        return None
    category_path = [c["name"] for c in reversed(chain)]
    if _brand_hit(p["name"], p["description"], p["slug"], p["sku"], *category_path):
        return None
    out = {
        "id": p["id"], "sku": p["sku"], "name": p["name"], "slug": p["slug"],
        "description": _plain_text(p["description"]), "unit": p["unit"] or "ks",
        "category_path": category_path,
        "weight_g": p["weight_g"], "length_mm": _ser(p["length_mm"]), "width_mm": _ser(p["width_mm"]), "height_mm": _ser(p["height_mm"]),
        "availability": "skladem" if (p["stock_qty"] or 0) > 0 else (_clean(p["availability_text"], 80) or "na_dotaz"),
    }
    if p["is_board_material"]:
        out["board_sheet_mm"] = [p["board_sheet_width_mm"], p["board_sheet_height_mm"]]
    if _brand_hit(out["description"], out["availability"]):
        return None
    cur.execute("SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order, id", (pid,))
    # nazev souboru je soucasti verejne adresy obrazku: soubor se znackou/dodavatelem v nazvu se vynecha (fail closed po obrazcich, bot5 2026-10-02, krok 5 feed)
    out["images"] = [{"path": f"/content-files/gallery/{r['filename']}"} for r in cur.fetchall()
                     if r["filename"] and ".." not in r["filename"] and not _BRAND_RE.search(r["filename"])]
    if mode == "none":
        return out
    from documents import VAT_RATE
    if mode == "retail":
        import products as _products
        net, _basis = _products._effective_unit_price(cur, p, user=None)
    else:
        if dealer is None or markup_pct is None:
            return None
        dealer_net, _basis = dealer_effective_price(cur, p, dealer)
        if dealer_net is None:
            return None
        net = round(dealer_net * (1 + float(markup_pct) / 100.0), 2)
    if net is None:
        return None
    net = float(net)
    out["price_net_czk"] = round(net, 2)
    out["price_gross_czk"] = round(net * (1 + float(VAT_RATE) / 100.0), 2)
    out["vat_rate"] = float(VAT_RATE)
    return out


# ---------------------------------------------------------------------------------------------------------------- atribuce
def sanitize_landing(to):
    """Cil presmerovani: jen cesta na NASEM webu ('/produkt/x?a=b'), nikdy jina domena (open redirect). Nesmysl -> '/'."""
    s = (to or "").strip()
    if not s or len(s) > 255 or not s.startswith("/") or s.startswith("//") or "\\" in s or re.search(r"[\x00-\x1f\x7f]", s):
        return "/"
    parts = urllib.parse.urlsplit(s)
    if parts.scheme or parts.netloc:
        return "/"
    return s


def _ip_hash(ip):
    return hashlib.sha256((str(app.secret_key) + "|" + (ip or "")).encode("utf-8")).hexdigest()[:16]


@app.get("/api/dealer/go/<ref_code>")
def dealer_go(ref_code):
    """Proklik z webu dealera na nas: zaznamena klik, nastavi cookie dlr (30 dni od prokliku, last-click) a presmeruje na ?to= (jen cesta u nas).
    Neplatny/neaktivni dealer, robot nebo prekroceny limit: presmerovani probehne STEJNE, jen se nic nezapise a cookie se nenastavi."""
    target = sanitize_landing(request.args.get("to"))
    resp = redirect(target, code=302)
    resp.headers["Cache-Control"] = "no-store"
    ip = _client_ip()
    if not _REF_RE.match(ref_code or "") or _BOT_UA_RE.search(request.headers.get("User-Agent") or "") or _rate_limited(f"dealer_go:{ip}", 120, 60):
        return resp
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, status, is_active, order_path FROM dealers WHERE ref_code=%s", (ref_code,))
            d = cur.fetchone()
            if not d or d["status"] != "active" or not d["is_active"] or d["order_path"] != "our":
                return resp
            token = secrets.token_hex(16)
            cur.execute("INSERT INTO dealer_clicks (dealer_id, token, landing, ip_hash) VALUES (%s,%s,%s,%s)",
                        (d["id"], token, target[:255], _ip_hash(ip)))
            days = attribution_days(cur)
        conn.commit()
    except Exception:       # klik nikdy nesmi zabranit zakaznikovi dostat se na stranku
        app.logger.exception("dealer_go: zapis prokliku selhal")
        conn.rollback()
        return resp
    finally:
        conn.close()
    resp.set_cookie(CLICK_COOKIE, token, max_age=days * 86400, httponly=True, secure=True, samesite="Lax", path="/")
    return resp


def attribution_for_new_order(cur, click_token, user, customer_email, is_test=False, billing_ico=None):
    """-> {'dealer_id', 'click_id', 'order_path'} nebo None. Pravidla: platny klik (token v dealer_clicks) mladsi nez dealer_attribution_days,
    aktivni dealer s cestou 'our', ne testovaci objednavka, ne nakup dealera sam sobe (jeho ucet, jeho e-mail kontaktu, jeho ICO)."""
    if is_test or not click_token or not _CLICK_TOKEN_RE.match(click_token):
        return None
    cur.execute("SELECT id, dealer_id, created_at FROM dealer_clicks WHERE token=%s", (click_token,))
    click = cur.fetchone()
    if not click or (_now() - click["created_at"]) > datetime.timedelta(days=attribution_days(cur)):
        return None
    dealer = _load_dealer(cur, click["dealer_id"])
    if not _dealer_usable(dealer) or dealer["order_path"] != "our":
        return None
    if user and dealer["user_id"] and user.get("id") == dealer["user_id"]:
        return None
    if customer_email and dealer["contact_email"] and customer_email.strip().lower() == dealer["contact_email"].strip().lower():
        return None
    if billing_ico and dealer["ico"] and re.sub(r"\s", "", billing_ico) == re.sub(r"\s", "", dealer["ico"]):
        return None
    return {"dealer_id": dealer["id"], "click_id": click["id"], "order_path": "our"}


def attach_attribution(cur, order_id, user, click_token=None):
    """Volano z orders_create PO vytvoreni objednavky, PRED commitem: prida k objednavce dealera podle cookie dlr. NIKDY nevyhodi vyjimku
    (objednavka se nesmi kvuli dealerovi rozbit) - selhani jen zaloguje a vrati False. True = objednavka pripsana dealerovi."""
    try:
        if click_token is None:
            click_token = request.cookies.get(CLICK_COOKIE)
        if not click_token:
            return False
        cur.execute("SELECT customer_email, billing_ico, is_test, dealer_id FROM shop_orders WHERE id=%s", (order_id,))
        o = cur.fetchone()
        if not o or o["dealer_id"] is not None:
            return False
        attr = attribution_for_new_order(cur, click_token, user, o["customer_email"], bool(o["is_test"]), o["billing_ico"])
        if not attr:
            return False
        cur.execute("UPDATE shop_orders SET dealer_id=%s, dealer_click_id=%s, order_path=%s WHERE id=%s AND dealer_id IS NULL",
                    (attr["dealer_id"], attr["click_id"], attr["order_path"], order_id))
        return cur.rowcount == 1
    except Exception:
        app.logger.exception("attach_attribution: pripsani objednavky %s dealerovi selhalo", order_id)
        return False


# ---------------------------------------------------------------------------------------------------------------- administrace (admin)
_DEALER_TEXT_FIELDS = {"name": 255, "contact_name": 255, "contact_email": 255, "contact_phone": 50, "ico": 20, "dic": 20,
                       "billing_street": 255, "billing_city": 120, "billing_zip": 6, "bank_account": 64, "note": 4000}


def _gen_ref_code(cur):
    for _ in range(20):
        code = "".join(secrets.choice(_REF_ALPHABET) for _ in range(10))
        cur.execute("SELECT 1 AS x FROM dealers WHERE ref_code=%s", (code,))
        if not cur.fetchone():
            return code
    raise RuntimeError("nepodarilo se vygenerovat unikatni ref_code")


def _dealer_public(d):
    """Radek dealera pro admin/panel (bez ref_code logiky navic)."""
    out = _ser_row(d)
    out["link_path"] = f"/api/dealer/go/{d['ref_code']}"
    return out


def _validate_dealer_body(cur, body, partial):
    """-> (pole_k_zapisu dict, chyba str|None). partial=True = PUT (jen zadane klice)."""
    fields = {}
    for name, max_len in _DEALER_TEXT_FIELDS.items():
        if name in body:
            fields[name] = _clean(body.get(name), max_len)
    if not partial and not fields.get("name"):
        return None, "Chybí název dealera."
    if "name" in fields and not fields["name"]:
        return None, "Název dealera nesmí být prázdný."
    if fields.get("contact_email") and not _EMAIL_RE.match(fields["contact_email"]):
        return None, "E-mail kontaktu není ve správném formátu."
    try:
        if "default_discount_pct" in body:
            fields["default_discount_pct"] = _pct(body.get("default_discount_pct"))
        if "default_commission_pct" in body:
            fields["default_commission_pct"] = _pct(body.get("default_commission_pct"))
    except ValueError as e:
        return None, str(e)
    if "status" in body:
        if body["status"] not in DEALER_STATUSES:
            return None, "Neplatný stav dealera."
        fields["status"] = body["status"]
    if "order_path" in body:
        if body["order_path"] not in ORDER_PATHS:
            return None, "Neplatná cesta objednávky."
        fields["order_path"] = body["order_path"]
    if "is_active" in body:
        fields["is_active"] = 1 if body["is_active"] else 0
    if "party_id" in body:
        pid = body["party_id"]
        if pid in (None, ""):
            fields["party_id"] = None
        else:
            cur.execute("SELECT id FROM parties WHERE id=%s", (pid,))
            if not cur.fetchone():
                return None, "Záznam v adresáři neexistuje."
            fields["party_id"] = int(pid)
    if "user_id" in body:
        uid = body["user_id"]
        if uid in (None, ""):
            fields["user_id"] = None
        else:
            cur.execute("SELECT id, role FROM app_users WHERE id=%s", (uid,))
            u = cur.fetchone()
            if not u:
                return None, "Uživatelský účet neexistuje."
            if u["role"] != "user":
                return None, "Účet dealera musí být běžný zákaznický účet (role user), ne zaměstnanecký."
            fields["user_id"] = int(uid)
    return fields, None


def _dealer_detail(cur, dealer_id):
    d = _load_dealer(cur, dealer_id)
    if not d:
        return None
    out = _dealer_public(d)
    cur.execute("SELECT id, category_id, discount_pct, commission_pct FROM dealer_rates WHERE dealer_id=%s ORDER BY category_id", (dealer_id,))
    out["rates"] = [_ser_row(r) for r in cur.fetchall()]
    cur.execute("SELECT id, domain, is_active, created_at FROM dealer_domains WHERE dealer_id=%s ORDER BY id", (dealer_id,))
    out["domains"] = [_ser_row(r) for r in cur.fetchall()]
    cur.execute("SELECT id, kind, public_id, scopes, allowed_ips, label, rate_per_min, is_active, expires_at, revoked_at, last_used_at, last_used_ip, created_at "
                "FROM dealer_keys WHERE dealer_id=%s ORDER BY id", (dealer_id,))
    out["keys"] = [_ser_row(r) for r in cur.fetchall()]
    return out


@app.get("/api/admin/dealers")
@require_permission(PERMISSION_DEALERI, "zobrazit")
def admin_dealers_list():
    q = (request.args.get("q") or "").strip()
    status = request.args.get("status")
    show_inactive = request.args.get("all") == "1"
    where, params = [], []
    if not show_inactive:
        where.append("d.is_active=1")
    if status in DEALER_STATUSES:
        where.append("d.status=%s")
        params.append(status)
    if q:
        where.append("(d.name LIKE %s OR d.ico LIKE %s OR d.contact_email LIKE %s OR d.ref_code LIKE %s)")
        params += [f"%{q}%"] * 4
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT d.*, (SELECT COUNT(*) FROM dealer_keys k WHERE k.dealer_id=d.id AND k.is_active=1 AND k.revoked_at IS NULL) AS active_keys, "
                "(SELECT COUNT(*) FROM dealer_clicks c WHERE c.dealer_id=d.id AND c.created_at >= NOW() - INTERVAL 30 DAY) AS clicks_30d, "
                "(SELECT COUNT(*) FROM shop_orders o WHERE o.dealer_id=d.id) AS orders_total "
                "FROM dealers d" + ((" WHERE " + " AND ".join(where)) if where else "") + " ORDER BY d.name", params)
            rows = [_dealer_public(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return _json({"dealers": rows})


@app.get("/api/admin/dealers/<int:dealer_id>")
@require_permission(PERMISSION_DEALERI, "zobrazit")
def admin_dealers_get(dealer_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            out = _dealer_detail(cur, dealer_id)
    finally:
        conn.close()
    if not out:
        return _err("Dealer neexistuje.", "not_found", 404)
    return _json({"dealer": out})


@app.post("/api/admin/dealers")
@require_permission(PERMISSION_DEALERI, "vytvorit")
def admin_dealers_create():
    body = request.get_json(silent=True) or {}
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fields, error = _validate_dealer_body(cur, body, partial=False)
            if error:
                return _err(error, "validation", 400)
            fields["ref_code"] = _gen_ref_code(cur)
            cols = list(fields.keys())
            try:
                cur.execute(f"INSERT INTO dealers ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", [fields[c] for c in cols])
            except Exception as e:      # napr. UNIQUE user_id (ucet uz je u jineho dealera)
                conn.rollback()
                if "Duplicate" in str(e):
                    return _err("Tenhle uživatelský účet už patří jinému dealerovi.", "duplicate", 409)
                raise
            dealer_id = cur.lastrowid
            out = _dealer_detail(cur, dealer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "dealer", dealer_id, {"name": fields["name"], "ref_code": fields["ref_code"]})
    return _json({"dealer": out}, 201)


@app.put("/api/admin/dealers/<int:dealer_id>")
@require_permission(PERMISSION_DEALERI, "upravit")
def admin_dealers_update(dealer_id):
    body = request.get_json(silent=True) or {}
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            before = _load_dealer(cur, dealer_id)
            if not before:
                return _err("Dealer neexistuje.", "not_found", 404)
            fields, error = _validate_dealer_body(cur, body, partial=True)
            if error:
                return _err(error, "validation", 400)
            if fields:
                try:
                    cur.execute(f"UPDATE dealers SET {', '.join(f'{c}=%s' for c in fields)} WHERE id=%s", list(fields.values()) + [dealer_id])
                except Exception as e:
                    conn.rollback()
                    if "Duplicate" in str(e):
                        return _err("Tenhle uživatelský účet už patří jinému dealerovi.", "duplicate", 409)
                    raise
            out = _dealer_detail(cur, dealer_id)
        conn.commit()
    finally:
        conn.close()
    changed = {k: [_ser(before.get(k)), _ser(v)] for k, v in fields.items() if _ser(before.get(k)) != _ser(v)}
    if changed:
        log_audit(user["id"], "update", "dealer", dealer_id, changed)
    return _json({"dealer": out})


@app.put("/api/admin/dealers/<int:dealer_id>/rates")
@require_permission(PERMISSION_DEALERI, "upravit")
def admin_dealers_rates_put(dealer_id):
    """Nahradi sazby podle kategorii: {"rates": [{"category_id": 149, "discount_pct": 20, "commission_pct": 8}, ...]} (NULL = zdedit)."""
    body = request.get_json(silent=True) or {}
    rates = body.get("rates")
    if not isinstance(rates, list) or len(rates) > 500:
        return _err("Chybí seznam sazeb (rates).", "validation", 400)
    user = current_user()
    clean = {}
    try:
        for r in rates:
            cid = int(r.get("category_id"))
            clean[cid] = (_pct(r.get("discount_pct")), _pct(r.get("commission_pct")))
    except (TypeError, ValueError, AttributeError) as e:
        return _err(str(e) if isinstance(e, ValueError) and "Procento" in str(e) else "Neplatná sazba nebo kategorie.", "validation", 400)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not _load_dealer(cur, dealer_id):
                return _err("Dealer neexistuje.", "not_found", 404)
            for cid in clean:
                cur.execute("SELECT id FROM content_categories WHERE id=%s", (cid,))
                if not cur.fetchone():
                    return _err(f"Kategorie {cid} neexistuje.", "validation", 400)
            cur.execute("SELECT category_id FROM dealer_rates WHERE dealer_id=%s", (dealer_id,))
            existing = {r["category_id"] for r in cur.fetchall()}
            for cid, (disc, comm) in clean.items():
                if cid in existing:
                    cur.execute("UPDATE dealer_rates SET discount_pct=%s, commission_pct=%s WHERE dealer_id=%s AND category_id=%s", (disc, comm, dealer_id, cid))
                else:
                    cur.execute("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct, commission_pct) VALUES (%s,%s,%s,%s)", (dealer_id, cid, disc, comm))
            # sazby se nemazou: kategorie vypustena ze seznamu dostane NULL/NULL (= zdedit), radek zustane
            for cid in existing - set(clean):
                cur.execute("UPDATE dealer_rates SET discount_pct=NULL, commission_pct=NULL WHERE dealer_id=%s AND category_id=%s", (dealer_id, cid))
            out = _dealer_detail(cur, dealer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_rates", dealer_id, {"rates": {str(k): list(v) for k, v in clean.items()}})
    return _json({"dealer": out})


def _add_domain(cur, dealer_id, raw):
    dom = normalize_domain(raw)
    if not dom:
        return None, "Neplatná doména."
    cur.execute("SELECT id, is_active FROM dealer_domains WHERE dealer_id=%s AND domain=%s", (dealer_id, dom))
    row = cur.fetchone()
    if row:
        if not row["is_active"]:
            cur.execute("UPDATE dealer_domains SET is_active=1 WHERE id=%s", (row["id"],))
        return dom, None
    cur.execute("INSERT INTO dealer_domains (dealer_id, domain) VALUES (%s,%s)", (dealer_id, dom))
    return dom, None


@app.post("/api/admin/dealers/<int:dealer_id>/domains")
@require_permission(PERMISSION_DEALERI, "upravit")
def admin_dealers_domain_add(dealer_id):
    body = request.get_json(silent=True) or {}
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not _load_dealer(cur, dealer_id):
                return _err("Dealer neexistuje.", "not_found", 404)
            dom, error = _add_domain(cur, dealer_id, body.get("domain"))
            if error:
                return _err(error, "validation", 400)
            out = _dealer_detail(cur, dealer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "dealer_domain", dealer_id, {"domain": dom})
    return _json({"dealer": out}, 201)


@app.delete("/api/admin/dealers/<int:dealer_id>/domains/<int:domain_id>")
@require_permission(PERMISSION_DEALERI, "upravit")
def admin_dealers_domain_off(dealer_id, domain_id):
    """Domena se nemaze, jen deaktivuje (is_active=0)."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE dealer_domains SET is_active=0 WHERE id=%s AND dealer_id=%s", (domain_id, dealer_id))
            if cur.rowcount != 1:
                return _err("Doména neexistuje.", "not_found", 404)
            out = _dealer_detail(cur, dealer_id)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_domain", domain_id, {"is_active": 0})
    return _json({"dealer": out})


def _parse_scopes(value, kind):
    if kind == "widget":
        return None, None
    if kind == "feed":
        return "feed", None
    items = value if isinstance(value, list) else [s for s in re.split(r"[\s,;]+", str(value or "")) if s]
    if not items:
        items = ["orders", "quote"]          # vychozi rozsah api klice
    bad = [s for s in items if s not in KEY_SCOPES]
    if bad or not items:
        return None, "Neplatný rozsah klíče (povoleno: feed, quote, orders)."
    return ",".join(sorted(set(items))), None


def _create_key(cur, dealer, kind, label, scopes, allowed_ips, rate_per_min, created_by):
    """-> (radek klice bez tajemstvi, secret|None, token|None). Hlida limit aktivnich klicu na druh."""
    cur.execute("SELECT COUNT(*) AS n FROM dealer_keys WHERE dealer_id=%s AND kind=%s AND is_active=1 AND revoked_at IS NULL "
                "AND (expires_at IS NULL OR expires_at > NOW())", (dealer["id"], kind))
    if cur.fetchone()["n"] >= MAX_ACTIVE_KEYS_PER_KIND:
        raise ValueError(f"Dealer už má {MAX_ACTIVE_KEYS_PER_KIND} aktivních klíčů tohoto druhu - nejdřív jeden odvolejte.")
    scope_str, scope_err = _parse_scopes(scopes, kind)
    if scope_err:
        raise ValueError(scope_err)
    rate = int(rate_per_min) if rate_per_min else 120
    if rate < 1 or rate > 6000:
        raise ValueError("Limit požadavků za minutu musí být 1 až 6000.")
    ips = _clean(allowed_ips, 500) if kind == "api" else None
    secret = token = None
    if kind == "widget":
        public_id, secret_hash = new_widget_key(), None
    else:
        public_id, secret, token = new_secret_key(kind)
        secret_hash = hash_secret(secret)
    cur.execute("INSERT INTO dealer_keys (dealer_id, kind, public_id, secret_hash, scopes, allowed_ips, label, rate_per_min, created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (dealer["id"], kind, public_id, secret_hash, scope_str, ips, _clean(label, 100), rate, created_by))
    key_id = cur.lastrowid
    cur.execute("SELECT id, kind, public_id, scopes, allowed_ips, label, rate_per_min, is_active, expires_at, revoked_at, last_used_at, created_at "
                "FROM dealer_keys WHERE id=%s", (key_id,))
    return _ser_row(cur.fetchone()), secret, token


@app.post("/api/admin/dealers/<int:dealer_id>/keys")
@require_permission(PERMISSION_KLICE, "vytvorit")
def admin_dealers_key_create(dealer_id):
    """Vytvori klic: {"kind": "widget"|"api"|"feed", "label", "scopes", "allowed_ips", "rate_per_min"}. U api/feed je v odpovedi `token` -
    UKAZE SE JEDNOU (v DB je jen hash), widget klic je verejny a ukaze se vzdy."""
    body = request.get_json(silent=True) or {}
    kind = body.get("kind")
    if kind not in KEY_KINDS:
        return _err("Neplatný druh klíče.", "validation", 400)
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            dealer = _load_dealer(cur, dealer_id)
            if not dealer:
                return _err("Dealer neexistuje.", "not_found", 404)
            try:
                key, secret, token = _create_key(cur, dealer, kind, body.get("label"), body.get("scopes"), body.get("allowed_ips"),
                                                 body.get("rate_per_min"), user["id"])
            except ValueError as e:
                return _err(str(e), "validation", 400)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "create", "dealer_key", key["id"], {"dealer_id": dealer_id, "kind": kind, "public_id": key["public_id"]})
    return _json({"key": key, "token": token}, 201)


@app.post("/api/admin/dealers/<int:dealer_id>/keys/<int:key_id>/revoke")
@require_permission(PERMISSION_KLICE, "upravit")
def admin_dealers_key_revoke(dealer_id, key_id):
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE dealer_keys SET is_active=0, revoked_at=COALESCE(revoked_at, NOW()) WHERE id=%s AND dealer_id=%s", (key_id, dealer_id))
            cur.execute("SELECT id FROM dealer_keys WHERE id=%s AND dealer_id=%s", (key_id, dealer_id))
            if not cur.fetchone():
                return _err("Klíč neexistuje.", "not_found", 404)
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_key", key_id, {"revoked": True})
    return _json({"status": "ok"})


@app.post("/api/admin/dealers/<int:dealer_id>/keys/<int:key_id>/rotate")
@require_permission(PERMISSION_KLICE, "upravit")
def admin_dealers_key_rotate(dealer_id, key_id):
    """Rotace: vznikne novy klic stejneho druhu a nastaveni, stary plati jeste ROTATE_OVERLAP_DAYS dni (prekryv, dealer stihne vymenit)."""
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            dealer = _load_dealer(cur, dealer_id)
            cur.execute("SELECT * FROM dealer_keys WHERE id=%s AND dealer_id=%s", (key_id, dealer_id))
            old = cur.fetchone()
            if not dealer or not old or old["revoked_at"] is not None:
                return _err("Klíč neexistuje.", "not_found", 404)
            try:
                key, secret, token = _create_key(cur, dealer, old["kind"], old["label"], old["scopes"] if old["kind"] == "api" else None,
                                                 old["allowed_ips"], old["rate_per_min"], user["id"])
            except ValueError as e:
                return _err(str(e), "validation", 400)
            until = _now() + datetime.timedelta(days=ROTATE_OVERLAP_DAYS)
            cur.execute("UPDATE dealer_keys SET expires_at=%s WHERE id=%s AND (expires_at IS NULL OR expires_at > %s)", (until, key_id, until))
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "update", "dealer_key", key_id, {"rotated_to": key["public_id"]})
    return _json({"key": key, "token": token}, 201)


# ---------------------------------------------------------------------------------------------------------------- partnersky panel (dealer sam)
def _my_dealer(cur):
    user = current_user()
    if not user:
        return None
    cur.execute("SELECT * FROM dealers WHERE user_id=%s AND is_active=1", (user["id"],))
    return cur.fetchone()


@app.get("/api/dealer/me")
@login_required
def dealer_me():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = _my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            out = _dealer_detail(cur, d["id"])
    finally:
        conn.close()
    # dealer vidi sve sazby, ne cizi; poznamku a interni pole ne
    out.pop("note", None)
    out.pop("created_at", None)
    return _json({"dealer": out})


@app.post("/api/dealer/domains")
@login_required
def dealer_domain_add():
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = _my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            if not _dealer_usable(d):
                return _err("Účet dealera zatím není aktivní.", "dealer_inactive", 403)
            cur.execute("SELECT COUNT(*) AS n FROM dealer_domains WHERE dealer_id=%s AND is_active=1", (d["id"],))
            if cur.fetchone()["n"] >= 20:
                return _err("Dealer může mít nejvýš 20 aktivních domén.", "limit", 400)
            dom, error = _add_domain(cur, d["id"], body.get("domain"))
            if error:
                return _err(error, "validation", 400)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "dealer_domain", d["id"], {"domain": dom, "by": "dealer"})
    return _json({"domain": dom}, 201)


@app.delete("/api/dealer/domains/<int:domain_id>")
@login_required
def dealer_domain_off(domain_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = _my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            cur.execute("UPDATE dealer_domains SET is_active=0 WHERE id=%s AND dealer_id=%s", (domain_id, d["id"]))
            if cur.rowcount != 1:
                return _err("Doména neexistuje.", "not_found", 404)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "dealer_domain", domain_id, {"is_active": 0, "by": "dealer"})
    return _json({"status": "ok"})


@app.post("/api/dealer/keys")
@login_required
def dealer_key_create():
    """Dealer si sam vystavi klic (widget pk_ / api sk_ / feed ft_). api a feed klic ma jen dealer s cestou 'dealer' (objednavky z jeho webu) -
    feed i dealer s cestou 'our' (soubor produktu). Tajna cast se ukaze JEDNOU."""
    body = request.get_json(silent=True) or {}
    kind = body.get("kind")
    if kind not in KEY_KINDS:
        return _err("Neplatný druh klíče.", "validation", 400)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = _my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            if not _dealer_usable(d):
                return _err("Účet dealera zatím není aktivní.", "dealer_inactive", 403)
            if kind == "api" and d["order_path"] != "dealer":
                return _err("API klíč pro objednávky je jen u dealera s objednávkou na jeho webu.", "forbidden", 403)
            try:
                key, secret, token = _create_key(cur, d, kind, body.get("label"), body.get("scopes"), body.get("allowed_ips"), None, current_user()["id"])
            except ValueError as e:
                return _err(str(e), "validation", 400)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "dealer_key", key["id"], {"dealer_id": d["id"], "kind": kind, "by": "dealer"})
    return _json({"key": key, "token": token}, 201)


@app.post("/api/dealer/keys/<int:key_id>/revoke")
@login_required
def dealer_key_revoke(key_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            d = _my_dealer(cur)
            if not d:
                return _err("K tomuto účtu není přiřazený dealer.", "not_a_dealer", 404)
            cur.execute("SELECT id FROM dealer_keys WHERE id=%s AND dealer_id=%s", (key_id, d["id"]))
            if not cur.fetchone():
                return _err("Klíč neexistuje.", "not_found", 404)
            cur.execute("UPDATE dealer_keys SET is_active=0, revoked_at=COALESCE(revoked_at, NOW()) WHERE id=%s", (key_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "dealer_key", key_id, {"revoked": True, "by": "dealer"})
    return _json({"status": "ok"})
