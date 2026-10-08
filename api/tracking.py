"""
Anonymni geograficky/page-view tracking (Robert pres bot3, 2026-08-22:
"totez nasadit na vandrawee.cz" - stejny princip jako geo-tracking prave
postaveny na /opt/toscanaccio, adaptovany na konfigurator, ktery zadne
recepty/mapove vrstvy nema, viz TASKS.md).

PRVNI zavedeni HMAC ip_hash vzoru v tomhle repu - zadna syrova IP se tu
NIKDY neuklada u noveho kodu. Konfigurator uz ma starsi
scene_offer_views.ip_address (api/scene_offers.py, "Online nabidky" -
mrtve/nikdy nezapojene UI) - ten je VEDOME NEDOTCEN timhle ukolem (jina
feature, min privacy-conscious vzor, ne k napodobeni pro novy kod; kdyby
se mel dosypat hashem, je to samostatny ukol na zeptani).
"""
import hashlib
import hmac
import re

from flask import request, jsonify

from app import app, get_conn, admin_required, _client_ip, _rate_limited
import geoip


def _ip_hash(ip):
    # Stejny HMAC vzor jako _ip_hash() na toscanacciu - hash s uz
    # existujicim app.secret_key, zadny novy secret k sprave.
    key = app.secret_key.encode("utf-8") if isinstance(app.secret_key, str) else app.secret_key
    return hmac.new(key, ip.encode("utf-8"), hashlib.sha256).hexdigest()


def _classify_device_type():
    """Mobil/tablet/desktop podle User-Agent hlavicky (Robert pres
    bot3, 2026-08-22: "pouzite zarizeni"). Stejne rozhodnuti jako
    bot10 na toscanacciu - cteno SERVEROVE z HTTP hlavicky (identicky
    retezec jako navigator.userAgent na klientu), takze funguje
    automaticky pro vsechny tracking endpointy bez nutnosti, aby si to
    kazde volajici misto v JS samo pocitalo a posilalo.

    Jednoducha heuristika (zadna plna UA-parsing knihovna) - poradi
    zalezi: tablet nejdriv (Android bez "Mobile" tokenu = tablet, ne
    telefon), pak mobile, jinak desktop."""
    ua = (request.headers.get("User-Agent") or "").lower()
    if not ua:
        return ""
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobile" in ua or "iphone" in ua or "ipod" in ua or "android" in ua:
        return "mobile"
    return "desktop"


def _classify_browser():
    """Chrome/Safari/Firefox/Edge/... podle stejne User-Agent hlavicky
    jako _classify_device_type() (Robert pres bot3, dodatecne: "vedle
    zarizeni i prohlizec"). Poradi zalezi - Edge/Opera/Samsung Internet
    obsahuji ve svem UA i token "chrome" (jsou postavene na Chromiu) a
    Chrome na iOS obsahuje "safari", takze specifictejsi prohlizece se
    MUSI testovat driv, jinak by je heuristika omylem oznacila za
    Chrome/Safari."""
    ua = (request.headers.get("User-Agent") or "").lower()
    if not ua:
        return ""
    if "edg/" in ua or "edga/" in ua or "edgios/" in ua:
        return "Edge"
    if "opr/" in ua or "opera" in ua:
        return "Opera"
    if "samsungbrowser" in ua:
        return "Samsung Internet"
    if "firefox" in ua or "fxios" in ua:
        return "Firefox"
    if "crios" in ua or "chrome" in ua:
        return "Chrome"
    if "safari" in ua:
        return "Safari"
    return "jiný"


_PAGE_TYPES = {
    "domov", "kategorie", "produkt", "blok", "nabidka_online",
    "poptavka_stul", "realizace", "remeslo", "jine",
    # Robert, 2026-09-14: "chci nastavit statistiky navstev, pouziti...
    # statistiky ukladat v Geo prehledu" - pouziti nastroje "Zakreslit"
    # na detailu produktu (webapp/product.html, image-markup.js) se
    # posila STEJNYM genericky endpointem (/api/track/page-view) jako
    # ostatni typy, jen s vlastnim page_type a synteticke path
    # (produktova cesta + "/zakreslit-pripominka", aby NEKOLIDOVALO s
    # UNIQUE(path, ip_hash) radkem, ktery pro tu samou cestu uz existuje
    # z bezneho page-view trackingu produktove stranky - viz komentar u
    # uq_page_view). Zadny novy endpoint/tabulka, cely existujici Geo
    # prehled (casovy filtr, geo/zarizeni/prohlizec rozpad) funguje beze
    # zmeny kodu.
    "zakresleni",
}

# Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): 4 verejne POST
# endpointy nize nemely zadny rate limit ani validaci "path" - libovolny
# retezec z klienta + UNIQUE(path, ip_hash) umoznoval jedne IP zaplavit
# page_views/denni agregace neomezenym poctem novych radku (kazdy jiny
# "path" = novy radek). _rate_limited per IP (429 pri prekroceni) +
# "path" musi vypadat jako skutecna relativni cesta - zacina "/", jen
# bezne URL znaky, zadne mezery/ridici znaky (400 pri neplatnem tvaru).
_TRACK_PATH_RE = re.compile(r"/[A-Za-z0-9_\-./?=&%]*")


def _track_guard():
    """None = OK, pokracuj. Jinak (jsonify(...), http_kod) k rovnou vraceni."""
    if _rate_limited(f"tracking:{_client_ip()}", max_requests=30, window_seconds=60):
        return jsonify({"error": "Příliš mnoho požadavků."}), 429
    return None


def _valid_track_path(path):
    return bool(path) and bool(_TRACK_PATH_RE.fullmatch(path))


# ---------------------------------------------------------------------------
# Denni bucket tabulky pro casovy filtr v Geo prehledu (Robert pres bot3,
# 2026-08-22, adaptace vzoru z toscanaccia - viz
# sql/2026-08-22_geo_tracking_daily_device_dwell.sql pro cely
# architektonicky duvod - stavajici tabulky drzi jen kumulativni soucet
# za VSECHNU dobu na navstevnika, "za poslednich N dni" se z nich
# nespocita). country/city/device_type/browser se ukladaji jako ''
# (NE None/NULL) - MySQL UNIQUE KEY by jinak bral kazdy NULL jako
# odlisny od jineho NULL a misto agregace by se zakladaly porad nove
# radky.
# ---------------------------------------------------------------------------

def _bump_page_view_daily(cur, path, page_type, country, city, device_type, browser):
    cur.execute(
        "INSERT INTO page_views_daily (path, page_type, den, country, city, device_type, browser, view_count) "
        "VALUES (%s,%s,CURDATE(),%s,%s,%s,%s,1) "
        "ON DUPLICATE KEY UPDATE view_count=view_count+1",
        (path, page_type, country or "", city or "", device_type or "", browser or ""),
    )


def _bump_page_dwell_daily(cur, path, page_type, country, city, device_type, browser, ms):
    cur.execute(
        "INSERT INTO page_views_daily (path, page_type, den, country, city, device_type, browser, dwell_ms_total, dwell_count) "
        "VALUES (%s,%s,CURDATE(),%s,%s,%s,%s,%s,1) "
        "ON DUPLICATE KEY UPDATE dwell_ms_total=dwell_ms_total+%s, dwell_count=dwell_count+1",
        (path, page_type, country or "", city or "", device_type or "", browser or "", ms, ms),
    )


def _bump_product_view_daily(cur, product_id, country, city, device_type, browser):
    cur.execute(
        "INSERT INTO product_views_daily (product_id, den, country, city, device_type, browser, view_count) "
        "VALUES (%s,CURDATE(),%s,%s,%s,%s,1) "
        "ON DUPLICATE KEY UPDATE view_count=view_count+1",
        (product_id, country or "", city or "", device_type or "", browser or ""),
    )


def _bump_category_view_daily(cur, category_id, country, city, device_type, browser):
    cur.execute(
        "INSERT INTO category_views_daily (category_id, den, country, city, device_type, browser, view_count) "
        "VALUES (%s,CURDATE(),%s,%s,%s,%s,1) "
        "ON DUPLICATE KEY UPDATE view_count=view_count+1",
        (category_id, country or "", city or "", device_type or "", browser or ""),
    )


@app.post("/api/track/page-view")
def public_track_page_view():
    """Obecny page-view tracking pro CELY verejny web - volano z
    webapp/track.js (sdileny <script>, viz tam pro seznam
    instrumentovanych stranek). Dedup-agregacni vzor (UNIQUE
    (path, ip_hash)), NE log kazde jednotlive navstevy."""
    guard = _track_guard()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()[:255]
    page_type = (body.get("page_type") or "jine").strip()
    if page_type not in _PAGE_TYPES:
        page_type = "jine"
    if not _valid_track_path(path):
        return jsonify({"error": "Neplatná cesta."}), 400
    ip = _client_ip()
    ip_hash = _ip_hash(ip)
    country, region, city = geoip.resolve_geo(ip)
    device_type = _classify_device_type()
    browser = _classify_browser()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO page_views (path, page_type, ip_hash, country, region, city, device_type, browser) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE view_count=view_count+1, last_viewed_at=NOW(), "
                "device_type=VALUES(device_type), browser=VALUES(browser)",
                (path, page_type, ip_hash, country, region, city, device_type, browser),
            )
            _bump_page_view_daily(cur, path, page_type, country, city, device_type, browser)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/track/page-dwell")
def public_track_page_dwell():
    """Straveny cas na obecne strance (Robert pres bot3, 2026-08-22:
    "stravany cas (dwell time)... pridej dwell-tracking i do obecneho
    page_views stejnym vzorem jako u receptu [na toscanacciu]").
    navigator.sendBeacon() pri odchodu ze stranky, viz webapp/track.js.
    page_views nema jiny primarni klic nez (path, ip_hash), proto
    ON DUPLICATE KEY UPDATE na tu samou dvojici."""
    guard = _track_guard()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    path = (body.get("path") or "").strip()[:255]
    page_type = (body.get("page_type") or "jine").strip()
    if page_type not in _PAGE_TYPES:
        page_type = "jine"
    try:
        ms = int(body.get("ms") or 0)
    except (TypeError, ValueError):
        ms = 0
    if not _valid_track_path(path):
        return jsonify({"error": "Neplatná cesta."}), 400
    if ms <= 0 or ms > 3600_000:  # sanitni strop 1h
        return jsonify({"status": "ok"})
    ip = _client_ip()
    ip_hash = _ip_hash(ip)
    # Dwell samo o sobe nenese polohu/zarizeni - dwell-only udalost
    # potrebuje vedet, KTEROU dnesni radku (den, country, city, device,
    # browser) navysit. Znovu-resolve je levny (lokalni mmdb dotaz,
    # zadny externi pristup).
    country, _region, city = geoip.resolve_geo(ip)
    device_type = _classify_device_type()
    browser = _classify_browser()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO page_views (path, page_type, ip_hash, total_dwell_ms) VALUES (%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE total_dwell_ms=total_dwell_ms+%s, last_viewed_at=NOW()",
                (path, page_type, ip_hash, ms, ms),
            )
            _bump_page_dwell_daily(cur, path, page_type, country, city, device_type, browser, ms)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/track/product-view")
def public_track_product_view():
    """Geo-breakdown NAVIC k existujicimu produktu - "odkud se divaji
    na TENHLE produkt" (analogie recipe_views na toscanacciu). Volano
    z product.html (uz ma productId v JS, viz track.js)."""
    guard = _track_guard()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    try:
        product_id = int(body.get("product_id"))
    except (TypeError, ValueError):
        return jsonify({"status": "ok"})
    ip = _client_ip()
    ip_hash = _ip_hash(ip)
    country, region, city = geoip.resolve_geo(ip)
    device_type = _classify_device_type()
    browser = _classify_browser()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                return jsonify({"status": "ok"})
            cur.execute(
                "INSERT INTO product_views (product_id, ip_hash, country, region, city, device_type, browser) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE view_count=view_count+1, last_viewed_at=NOW(), "
                "device_type=VALUES(device_type), browser=VALUES(browser)",
                (product_id, ip_hash, country, region, city, device_type, browser),
            )
            _bump_product_view_daily(cur, product_id, country, city, device_type, browser)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


@app.post("/api/track/category-view")
def public_track_category_view():
    guard = _track_guard()
    if guard:
        return guard
    body = request.get_json(silent=True) or {}
    try:
        category_id = int(body.get("category_id"))
    except (TypeError, ValueError):
        return jsonify({"status": "ok"})
    ip = _client_ip()
    ip_hash = _ip_hash(ip)
    country, region, city = geoip.resolve_geo(ip)
    device_type = _classify_device_type()
    browser = _classify_browser()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_categories WHERE id=%s", (category_id,))
            if not cur.fetchone():
                return jsonify({"status": "ok"})
            cur.execute(
                "INSERT INTO category_views (category_id, ip_hash, country, region, city, device_type, browser) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE view_count=view_count+1, last_viewed_at=NOW(), "
                "device_type=VALUES(device_type), browser=VALUES(browser)",
                (category_id, ip_hash, country, region, city, device_type, browser),
            )
            _bump_category_view_daily(cur, category_id, country, city, device_type, browser)
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})


_GEO_RANGES = {"all": None, "7d": 7, "30d": 30}
_GEO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@app.get("/api/admin/geo-tracking/overview")
@admin_required
def admin_geo_tracking_overview():
    """Admin prehled geografickeho trackingu (Robert pres bot3,
    2026-08-22, rozsireno stejny den o casovy filtr + mesto + zarizeni
    + prohlizec + straveny cas) - stejny princip jako "Geo přehled" na
    toscanacciu, jen misto receptu/mapovych vrstev produkty/kategorie.
    @admin_required (ne @require_permission) - cisty reporting panel
    bez existujici domenove sekce v PERMISSION_SECTIONS.

    `?range=all|7d|30d`: "all" (vychozi, beze zmeny chovani) cte ze
    stavajicich kumulativnich tabulek (unikatni navstevnici za CELOU
    dobu). "7d"/"30d" cte z *_daily tabulek (proste denni pocty, viz
    sql/2026-08-22_geo_tracking_daily_device_dwell.sql pro
    architektonicky duvod, proc kumulativni tabulky "za poslednich N
    dni" neumeji spocitat vubec).

    `?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` (Robert pres bot3,
    dodatecne: "casovy filtr chci i na dny") - MA PREDNOST pred
    `range`, pokud je zadany aspon jeden z nich. Jeden konkretni den =
    date_from==date_to (chybejici druhy parametr se dopocita z
    prvniho, takze staci poslat jen jeden). Cte ze stejnych *_daily
    tabulek jako 7d/30d presety, jen jiny rozsah dat."""
    range_key = request.args.get("range", "all")
    if range_key not in _GEO_RANGES:
        range_key = "all"
    days = _GEO_RANGES[range_key]

    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()
    if date_from and not _GEO_DATE_RE.match(date_from):
        date_from = ""
    if date_to and not _GEO_DATE_RE.match(date_to):
        date_to = ""

    if date_from or date_to:
        date_from = date_from or date_to
        date_to = date_to or date_from
        use_daily = True
        date_where = "den BETWEEN %s AND %s"
        date_params = (date_from, date_to)
    elif days is not None:
        use_daily = True
        date_where = "den >= CURDATE() - INTERVAL %s DAY"
        date_params = (days,)
    else:
        use_daily = False
        date_where = None
        date_params = ()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if not use_daily:
                # Robert pres bot3, dodatecne ("chci z toho pochopit kdo
                # kdy a naco se divail... pridej sloupce, aby to bylo
                # zrejme") - "naco" = path (dosud se v teto tabulce
                # ztracelo, agregovalo se pres VSECHNY stranky dohromady).
                # "kdy" (konkretni den) NEJDE z kumulativni tabulky
                # ziskat vubec (drzi jen prvni/posledni navstevu za
                # CELOU dobu, ne kazdy den zvlast) - den je proto v
                # tomhle vetvi vzdy NULL, frontend zobrazi "—" a da
                # najevo, ze presny den je dostupny jen v 7d/30d/rozsah
                # pohledu (viz vetev nize).
                cur.execute(
                    "SELECT NULL AS den, path, country, city, device_type, browser, SUM(view_count) AS views, "
                    "  ROUND(SUM(total_dwell_ms)/1000) AS dwell_seconds_total "
                    "FROM page_views WHERE country IS NOT NULL "
                    "GROUP BY path, country, city, device_type, browser ORDER BY views DESC LIMIT 100"
                )
                top_countries = cur.fetchall()

                cur.execute(
                    "SELECT page_type, SUM(view_count) AS views FROM page_views "
                    "GROUP BY page_type ORDER BY views DESC"
                )
                page_type_totals = cur.fetchall()

                cur.execute(
                    "SELECT NULL AS den, p.id AS product_id, p.name AS product_name, pv.country, pv.city, pv.device_type, pv.browser, "
                    "  SUM(pv.view_count) AS views "
                    "FROM product_views pv JOIN shop_products p ON p.id = pv.product_id "
                    "WHERE pv.country IS NOT NULL "
                    "GROUP BY pv.product_id, pv.country, pv.city, pv.device_type, pv.browser ORDER BY p.name, views DESC"
                )
                product_countries = cur.fetchall()

                cur.execute(
                    "SELECT NULL AS den, c.id AS category_id, c.name AS category_name, cv.country, cv.city, cv.device_type, cv.browser, "
                    "  SUM(cv.view_count) AS views "
                    "FROM category_views cv JOIN content_categories c ON c.id = cv.category_id "
                    "WHERE cv.country IS NOT NULL "
                    "GROUP BY cv.category_id, cv.country, cv.city, cv.device_type, cv.browser ORDER BY c.name, views DESC"
                )
                category_countries = cur.fetchall()
            else:
                # date_where je JEDNA ze dvou pevne dane konstanty
                # (nikdy odvozena primo z uzivatelskeho vstupu) - f-string
                # tady jen sklada SQL text, hodnoty jdou porad parametrizovane
                # pres date_params. Denni tabulky MAJI sloupec den, takze
                # tady se "kdy"/"naco" (den/path) da rovnou pridat do
                # GROUP BY a razeni od nejnovejsiho dne - presne "kdo kdy
                # naco" pozadavek.
                cur.execute(
                    "SELECT den, path, country, city, device_type, browser, SUM(view_count) AS views, "
                    "  ROUND(SUM(dwell_ms_total)/1000) AS dwell_seconds_total "
                    f"FROM page_views_daily WHERE {date_where} AND country != '' "
                    "GROUP BY den, path, country, city, device_type, browser ORDER BY den DESC, views DESC LIMIT 100",
                    date_params,
                )
                top_countries = cur.fetchall()

                cur.execute(
                    "SELECT page_type, SUM(view_count) AS views FROM page_views_daily "
                    f"WHERE {date_where} GROUP BY page_type ORDER BY views DESC",
                    date_params,
                )
                page_type_totals = cur.fetchall()

                cur.execute(
                    "SELECT pvd.den, p.id AS product_id, p.name AS product_name, pvd.country, pvd.city, pvd.device_type, pvd.browser, "
                    "  SUM(pvd.view_count) AS views "
                    "FROM product_views_daily pvd JOIN shop_products p ON p.id = pvd.product_id "
                    f"WHERE {date_where.replace('den', 'pvd.den')} AND pvd.country != '' "
                    "GROUP BY pvd.den, p.id, pvd.country, pvd.city, pvd.device_type, pvd.browser "
                    "ORDER BY pvd.den DESC, p.name, views DESC",
                    date_params,
                )
                product_countries = cur.fetchall()

                cur.execute(
                    "SELECT cvd.den, c.id AS category_id, c.name AS category_name, cvd.country, cvd.city, cvd.device_type, cvd.browser, "
                    "  SUM(cvd.view_count) AS views "
                    "FROM category_views_daily cvd JOIN content_categories c ON c.id = cvd.category_id "
                    f"WHERE {date_where.replace('den', 'cvd.den')} AND cvd.country != '' "
                    "GROUP BY cvd.den, c.id, cvd.country, cvd.city, cvd.device_type, cvd.browser "
                    "ORDER BY cvd.den DESC, c.name, views DESC",
                    date_params,
                )
                category_countries = cur.fetchall()
    finally:
        conn.close()
    return jsonify({
        "top_countries": top_countries,
        "page_type_totals": page_type_totals,
        "product_countries": product_countries,
        "category_countries": category_countries,
    })
