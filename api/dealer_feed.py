"""Dealersky program, krok 5 (bot5, 2026-10-02; zadani Robert pres bot3, zelena bot3 2026-10-02): FEED PRODUKTU pro dealery s vlastnim e-shopem (CSV + XML).

Dealer si feed stahuje (nebo ho importuje do sveho e-shopu) pomoci TAJNEHO FEED TOKENU (ft_..., scope feed; admin/dealer ho vydava stejne jako ostatni klice):
  GET /api/dealer/v1/feed.csv      GET /api/dealer/v1/feed.xml       Authorization: Bearer ft_...   (nebo ?token=ft_... pro importery, kteri neumi hlavicku)
  ?markup=<0-500>   povinne u cesty 'dealer': prirazka dealera v % - v feedu je jen VYSLEDNA cena = dealerska cena x (1 + markup/100), dealerska cena sama se nikdy neuvede.

Pravidla (nemenit bez Roberta, stejna jako u widgetu - dealers.py):
  * JEDINA projekce produktu je dealers.dealer_product_view (whitelist, fail closed): zadna znacka (Logiman, konfigurator, vandrawee, dodavatel profilu), zadne sestavy a VD-*, zadny 3D model,
    zadne naklady ani interni poznamky, zadny presny sklad. Nad tim se pred zapisem kazdeho radku jeste jednou zkontroluje znacka ve VSECH textech vcetne adres (fail closed po radcich),
  * cesta 'dealer' -> mode dealer_final (jen vysledna cena, produkty bez dealerske ceny se vynechaji), cesta 'our' -> mode retail (verejna cena) + odkaz pres jeho prokliku (provize),
  * verejna adresa pro odkazy a obrazky = app_settings dealer_public_base_url (NEUTRALNI domena, rozhodne Robert, nginx se nemeni). Dokud neni nastavena (https, bez znacky), feed vraci 503 feed_not_configured,
  * odpoved se v procesu drzi 10 minut (klic dealer + format + prirazka) a ma ETag (If-None-Match -> 304); feed nic nezapisuje (jen last_used klice) a nic neodesila.
"""
import csv
import datetime
import hashlib
import io
import re
import threading
import time
import urllib.parse
from xml.sax.saxutils import escape as _xml_escape

from flask import request, Response

from app import app, get_conn, get_setting, _client_ip, _rate_limited
import dealers
from dealers import DealerAuthError, _err

MAX_MARKUP_PCT = 500.0
CACHE_SECONDS = 600
MAX_CACHE_ENTRIES = 40           # strop pameti: jeden feed ma stovky kB, kazda prirazka je jiny klic
MAX_BUILDS_PER_MIN = 10          # sestaveni feedu stoji ~2 s DB prace, jeden dealer ho nesmi vynucovat po sobe (jine prirazky)
MAX_IMAGES = 5
CSV_COLUMNS = ["id", "sku", "name", "description", "unit", "category", "weight_g", "length_mm", "width_mm", "height_mm", "availability",
               "price_net_czk", "price_gross_czk", "vat_rate", "currency", "link"] + [f"image_{i}" for i in range(1, MAX_IMAGES + 1)]
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_BASE_URL_RE = re.compile(r"^https://[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+(:\d{2,5})?(/[A-Za-z0-9._~/-]*)?$")
_XML_BAD_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
_CSV_FORMULA_RE = re.compile(r"^[=+\-@\t\r]")


def _now():
    return time.time()


def _base_url(cur):
    """Verejna adresa pro odkazy a obrazky: app_settings dealer_public_base_url (https, bez koncoveho lomitka, bez znacky) nebo None (feed pak neni nakonfigurovany)."""
    raw = (get_setting(cur, "dealer_public_base_url", "") or "").strip().rstrip("/")
    if not raw or not _BASE_URL_RE.match(raw) or dealers._BRAND_RE.search(raw):
        return None
    return raw


def _auth():
    header = request.headers.get("Authorization")
    token = request.args.get("token")
    if not header and token:
        header = "Bearer " + token
    return dealers.resolve_secret_key(header, _client_ip(), scope="feed")


def _parse_markup(dealer):
    """-> markup % (cesta 'dealer', povinne) nebo None (cesta 'our'). Vyhodi ValueError(text) pri chybe."""
    raw = request.args.get("markup")
    if dealer["order_path"] != "dealer":
        return None
    if raw is None or str(raw).strip() == "":
        raise ValueError("Chybí parametr markup (vaše přirážka v %, 0 až 500) - ve feedu je jen výsledná cena.")
    try:
        v = float(str(raw).replace(",", "."))
    except ValueError:
        raise ValueError("Parametr markup musí být číslo (přirážka v %).")
    if v != v or v < 0 or v > MAX_MARKUP_PCT:
        raise ValueError(f"Parametr markup musí být od 0 do {int(MAX_MARKUP_PCT)}.")
    return round(v, 2)


def _num(value):
    """Cislo bez zbytecnych nul (200.0 -> 200, 12.50 -> 12.5), prazdne pro NULL."""
    return "" if value is None else f"{float(value):g}"


def build_rows(cur, dealer, markup, base):
    """Radky feedu (dict) - jen to, co projde dealers.dealer_product_view a final kontrolou znacky. Kazdy radek je plochy dict podle CSV_COLUMNS."""
    mode = "dealer_final" if dealer["order_path"] == "dealer" else "retail"
    cur.execute("SELECT id FROM shop_products WHERE active=1 AND is_archived=0 ORDER BY id")
    ids = [r["id"] for r in cur.fetchall()]
    rows = []
    for pid in ids:
        v = dealers.dealer_product_view(cur, pid, mode=mode, dealer=dealer if mode == "dealer_final" else None, markup_pct=markup)
        if v is None or "price_net_czk" not in v:
            continue
        link = ""
        if dealer["order_path"] == "our" and v.get("slug"):
            link = f"{base}/api/dealer/go/{dealer['ref_code']}?to=" + urllib.parse.quote(f"/produkt/{v['slug']}", safe="/")
        row = {
            "id": v["id"], "sku": v["sku"], "name": v["name"], "description": v["description"], "unit": v["unit"], "category": " > ".join(v["category_path"]),
            "weight_g": _num(v["weight_g"]), "length_mm": _num(v["length_mm"]), "width_mm": _num(v["width_mm"]), "height_mm": _num(v["height_mm"]),
            "availability": v["availability"], "price_net_czk": f"{v['price_net_czk']:.2f}", "price_gross_czk": f"{v['price_gross_czk']:.2f}", "vat_rate": f"{v['vat_rate']:g}",
            "currency": "CZK", "link": link,
        }
        for i in range(1, MAX_IMAGES + 1):
            row[f"image_{i}"] = base + v["images"][i - 1]["path"] if i <= len(v["images"]) else ""
        # final: znacka v JAKEMKOLI textu radku (vcetne adres) = radek se vynecha
        if dealers._brand_hit(*[str(x) for x in row.values()]):
            continue
        rows.append(row)
    return rows


def _csv_cell(key, value):
    s = _XML_BAD_RE.sub("", "" if value is None else str(value))      # ridici znaky pryc (v CSV i XML nemaji co delat)
    if key in ("name", "description", "sku", "category") and _CSV_FORMULA_RE.match(s):
        s = "'" + s              # ochrana pred vzorci v Excelu (=, +, -, @)
    return s


def render_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow([_csv_cell(k, r[k]) for k in CSV_COLUMNS])
    return buf.getvalue().encode("utf-8")


def _x(value):
    return _xml_escape(_XML_BAD_RE.sub("", "" if value is None else str(value)), {'"': "&quot;"})


def render_xml(rows, generated):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<products generated="{_x(generated)}" count="{len(rows)}">']
    for r in rows:
        out.append("<product>")
        for k in ("id", "sku", "name", "description", "unit"):
            out.append(f"<{k}>{_x(r[k])}</{k}>")
        out.append("<categories>" + "".join(f"<category>{_x(c)}</category>" for c in r["category"].split(" > ") if c) + "</categories>")
        out.append(f"<weight_g>{_x(r['weight_g'])}</weight_g>")
        out.append(f'<dimensions_mm length="{_x(r["length_mm"])}" width="{_x(r["width_mm"])}" height="{_x(r["height_mm"])}"/>')
        out.append(f"<availability>{_x(r['availability'])}</availability>")
        out.append(f'<price currency="CZK" vat_rate="{_x(r["vat_rate"])}" net="{_x(r["price_net_czk"])}" gross="{_x(r["price_gross_czk"])}"/>')
        out.append(f"<link>{_x(r['link'])}</link>")
        out.append("<images>" + "".join(f"<image>{_x(r[f'image_{i}'])}</image>" for i in range(1, MAX_IMAGES + 1) if r[f"image_{i}"]) + "</images>")
        out.append("</product>")
    out.append("</products>")
    return ("\n".join(out) + "\n").encode("utf-8")


def _serve(fmt):
    dealer, _key = _auth()
    markup = _parse_markup(dealer)
    cache_key = (dealer["id"], fmt, markup)
    with _CACHE_LOCK:
        hit = _CACHE.get(cache_key)
    if hit and hit[0] > _now():
        body, etag = hit[2], hit[1]
    else:
        if _rate_limited(f"dealer_feed_build:{dealer['id']}", MAX_BUILDS_PER_MIN, 60):
            raise DealerAuthError(429, "rate_limited")
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                base = _base_url(cur)
                if base is None:
                    return _err("Veřejná adresa pro dealery zatím není nastavena, feed je nedostupný.", "feed_not_configured", 503)
                rows = build_rows(cur, dealer, markup, base)
        finally:
            conn.close()
        body = render_csv(rows) if fmt == "csv" else render_xml(rows, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        etag = '"' + hashlib.sha256(body if fmt == "csv" else re.sub(rb' generated="[^"]*"', b"", body)).hexdigest()[:20] + '"'
        with _CACHE_LOCK:
            _CACHE[cache_key] = (_now() + CACHE_SECONDS, etag, body)
            for k in [k for k, v in _CACHE.items() if v[0] <= _now()]:
                _CACHE.pop(k, None)
            while len(_CACHE) > MAX_CACHE_ENTRIES:              # nejstarsi (nejdriv vyprsi) pryc
                _CACHE.pop(min(_CACHE, key=lambda k: _CACHE[k][0]), None)
    if request.headers.get("If-None-Match") == etag:
        resp = Response(status=304)
    else:
        resp = Response(body, mimetype="text/csv" if fmt == "csv" else "application/xml")
        resp.headers["Content-Type"] = ("text/csv" if fmt == "csv" else "application/xml") + "; charset=utf-8"
        resp.headers["Content-Disposition"] = f'inline; filename="produkty.{fmt}"'
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def _guard(fmt):
    try:
        return _serve(fmt)
    except DealerAuthError as e:
        return e.response()
    except ValueError as e:
        return _err(str(e), "invalid_request", 400)
    except Exception:
        app.logger.exception("dealer feed: neocekavana chyba")
        return _err("Interní chyba, zkuste to později.", "internal_error", 500)


@app.get("/api/dealer/v1/feed.csv")
def dealer_feed_csv():
    """Feed produktu pro dealera ve formatu CSV (UTF-8, strednik, CRLF). Autorizace feed tokenem, viz hlavicka modulu."""
    return _guard("csv")


@app.get("/api/dealer/v1/feed.xml")
def dealer_feed_xml():
    """Feed produktu pro dealera ve formatu XML. Autorizace feed tokenem, viz hlavicka modulu."""
    return _guard("xml")
