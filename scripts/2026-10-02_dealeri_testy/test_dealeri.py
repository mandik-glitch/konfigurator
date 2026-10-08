#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, etapa 1, krok 1 (bot5, 2026-10-02): klice a domeny, proklik s atribuci, administrace dealeru, pohled na produkt pro dealery.

SKUTECNY kod api/dealers.py (nebo kandidat, viz nize) nad DOCASNYMI tabulkami: dealers, dealer_rates, dealer_keys, dealer_domains,
dealer_clicks a shop_orders (+4 sloupce), app_settings jsou ve spojeni testu zastineny TEMPORARY tabulkami (struktura se bere z
sql/2026-10-02_dealers.sql, bez FK), do ostrych dat se NEZAPISUJE (shop_products, content_categories, app_users, parties se jen cetou, log_audit
je vypnuty). Endpointy jedou pres Flask test client, spojeni je to, co vraci app.get_conn() (1 spojeni na vlakno), takze vidi docasne tabulky.

Cast A  klice (tvar, hash, tajny token), domeny (normalizace, Origin, wildcard), cil presmerovani (open redirect), procenta
Cast B  resolve_public_key / resolve_secret_key (platny, odvolany, vypresly, spatny, dealer pozastaven, Origin, scope, IP, limit, last_used)
Cast C  GET /api/dealer/go/<kod> (klik, cookie dlr, presmerovani, robot, neaktivni dealer) a atribuce objednavky (30 dni, vlastni nakup, test, last-click)
Cast D  sazby: dealerska sleva a provize (produkt > kategorie nejblizsi nadrazena > vychozi dealera > nastaveni), dealerska cena vs akcni cena
Cast E  dealer_product_view (whitelist, fail closed: sestavy, VD-*, neaktivni, bez ceny, znacka, neviditelna kategorie; ceny retail/none/dealer_final)
Cast F  administrace (admin) + partnersky panel: opravneni, vytvoreni, uprava, sazby, domeny, klice (tajne se ukaze jednou, v DB jen hash), rotace, odvolani
Cast G  staticke kontrakty (kandidati app.py/orders.py, migrace) a mutace (puvodni/chybne verze funkci MUSI selhat)

Spusteni (DB prihlaseni pres systemd):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
    /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_dealeri.py
Kandidat pred nasazenim: --setenv=DEALERS_PY=/cesta/dealers.py [--setenv=APP_PY=/cesta/app.py --setenv=ORDERS_PY=/cesta/orders.py]
"""
import ast
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
DEALERS_PY = os.environ.get("DEALERS_PY")
APP_PY = os.environ.get("APP_PY", os.path.join(API, "app.py"))
ORDERS_PY = os.environ.get("ORDERS_PY", os.path.join(API, "orders.py"))
MIGRACE = os.path.join(REPO, "sql", "2026-10-02_dealers.sql")
if DEALERS_PY:     # kandidat: slozka s JEDINYM dealers.py pred api/
    tmp = tempfile.mkdtemp(prefix="kand_dealers_")
    shutil.copy(DEALERS_PY, os.path.join(tmp, "dealers.py"))
    sys.path.insert(0, tmp)
sys.path.insert(1 if DEALERS_PY else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402

for sekce in ("dealeri", "dealer_provize", "dealer_klice"):      # pred nasazenim app.py je jeste nezna (kandidat app.py je ma, viz cast G)
    if sekce not in appmod.PERMISSION_SECTIONS:
        appmod.PERMISSION_SECTIONS = tuple(appmod.PERMISSION_SECTIONS) + (sekce,)
import dealers  # noqa: E402

if DEALERS_PY:
    assert os.path.abspath(dealers.__file__).startswith(os.path.abspath(tmp)), f"nacetl se jiny dealers.py: {dealers.__file__}"
dealers.log_audit = lambda *a, **k: None          # zadne zapisy do ostreho audit_log

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre_spojeni()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders")
            n = cur.fetchone()["n"]
            cur.execute("SHOW COLUMNS FROM shop_orders")
            cols = [r["Field"] for r in cur.fetchall()]
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name LIKE 'dealer%'")
            tabs = sorted(r["table_name"] if "table_name" in r else r["TABLE_NAME"] for r in cur.fetchall())
            cur.execute("SELECT COUNT(*) AS n FROM audit_log")
            audit = cur.fetchone()["n"]
            return {"orders": n, "orders_cols": cols, "dealer_tables": tabs, "audit": audit}
    finally:
        c.close()


pred = stav_ostrych()

# ---------------------------------------------------------------------------------------------------------------- docasne tabulky
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
SQL = open(MIGRACE, encoding="utf-8").read()
TELO = "\n".join(l for l in SQL.splitlines() if not l.strip().startswith("--"))
PRIKAZY = [s.strip() for s in TELO.split(";") if s.strip()]
FK_RE = re.compile(r",\s*CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", re.I)

with real.cursor() as cur:
    cur.execute("CREATE TEMPORARY TABLE `_tpl_app_settings` LIKE `app_settings`")
    cur.execute("INSERT INTO `_tpl_app_settings` SELECT * FROM `app_settings`")
    cur.execute("CREATE TEMPORARY TABLE `app_settings` LIKE `_tpl_app_settings`")
    cur.execute("INSERT INTO `app_settings` SELECT * FROM `_tpl_app_settings`")
    cur.execute("DELETE FROM app_settings WHERE setting_key IN ('dealer_commission_default_pct','dealer_attribution_days')")
    cur.execute("CREATE TEMPORARY TABLE `_tpl_shop_orders` LIKE `shop_orders`")
    cur.execute("CREATE TEMPORARY TABLE `shop_orders` LIKE `_tpl_shop_orders`")
    cur.execute("SHOW CREATE TABLE shop_orders")
    assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), "ABORT: shop_orders neni docasna - nestini ostrou"
    cur.execute("SELECT COUNT(*) AS n FROM shop_orders")
    assert cur.fetchone()["n"] == 0
    for s in PRIKAZY:
        if s.startswith("CREATE TABLE IF NOT EXISTS"):
            cur.execute(FK_RE.sub("", re.sub(r"^CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", s)))
    cur.execute("SHOW COLUMNS FROM shop_orders LIKE 'dealer_id'")
    if not cur.fetchone():       # pred aplikaci migrace do ostre DB: pridat 4 sloupce jen do DOCASNE kopie
        alter = re.sub(r",\s*ADD CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", "",
                       [s for s in PRIKAZY if s.startswith("ALTER TABLE shop_orders")][0])      # docasna tabulka nesmi mit FK
        cur.execute("SHOW CREATE TABLE shop_orders")
        assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE")
        cur.execute(alter)
real.commit()

NYNI = datetime.datetime.now()


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def vloz_dealera(ref, name, status="active", is_active=1, order_path="our", email=None, ico=None, user_id=None, disc=None, comm=None):
    sql("INSERT INTO dealers (ref_code, name, status, is_active, order_path, contact_email, ico, user_id, default_discount_pct, default_commission_pct) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (ref, name, status, is_active, order_path, email, ico, user_id, disc, comm))
    return sql("SELECT * FROM dealers WHERE ref_code=%s", (ref,))[0]


def vloz_klic(dealer_id, kind, public_id, secret=None, scopes=None, ips=None, rate=120, active=1, expires=None, revoked=None):
    sql("INSERT INTO dealer_keys (dealer_id, kind, public_id, secret_hash, scopes, allowed_ips, rate_per_min, is_active, expires_at, revoked_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (dealer_id, kind, public_id, dealers.hash_secret(secret) if secret else None, scopes, ips, rate, active, expires, revoked))


try:
    # ============================================================================================================ A) cista logika
    print("== A klice, domeny, presmerovani, procenta")
    pk = dealers.new_widget_key()
    over("A1 verejny klic widgetu: pk_ + 24 hex, kazdy novy je jiny", re.match(r"^pk_[0-9a-f]{24}$", pk) and dealers.new_widget_key() != pk, pk)
    pid, secret, token = dealers.new_secret_key("api")
    over("A2 tajny klic api: sk_<8 hex>_<tajna>, parse vrati (public_id, tajna), hash = sha256 tajne a tajna neni v public_id",
         re.match(r"^sk_[0-9a-f]{8}$", pid) and token == f"{pid}_{secret}" and dealers.parse_secret_token(token) == (pid, secret)
         and dealers.hash_secret(secret) == hashlib.sha256(secret.encode()).hexdigest() and secret not in pid and len(secret) >= 40, (pid, token))
    over("A3 tajna cast s podtrzitky a pomlckami se parsuje spravne (token_urlsafe je obsahuje)", all(
        dealers.parse_secret_token(dealers.new_secret_key("feed")[2]) is not None for _ in range(200)), None)
    over("A4 spatne tokeny se nepouziji: prazdny, bez predpony, kratka tajna, pk_ misto sk_, cizi znaky",
         all(dealers.parse_secret_token(t) is None for t in ("", None, "abc", "sk_12345678", "sk_12345678_short", "pk_" + "a" * 24, "sk_zzzzzzzz_" + "a" * 40, "sk_12345678_" + "a b" * 15)), None)
    over("A5 Authorization: 'Bearer x' i holy token", dealers.bearer_token("Bearer abc ") == "abc" and dealers.bearer_token("bearer  abc") == "abc" and dealers.bearer_token("abc") == "abc" and dealers.bearer_token(None) == "", None)
    ND = dealers.normalize_domain
    over("A6 normalize_domain: schema/cesta/port/velka pismena/nadbytecne tecky", ND("https://Www.Example.cz:8080/cesta?x=1#a") == "www.example.cz" and ND("  Shop.EXAMPLE.cz. ") == "shop.example.cz", ND("https://Www.Example.cz:8080/cesta"))
    over("A7 normalize_domain: IDN -> punycode, wildcard zustane", ND("příklad.cz") == "xn--pklad-zsa96e.cz" and ND("*.Partner.cz") == "*.partner.cz", (ND("příklad.cz"), ND("*.Partner.cz")))
    over("A8 normalize_domain odmita: prazdne, IP, localhost, bez tecky, mezery, uzivatel@, javascript:, pouze wildcard",
         all(ND(x) is None for x in ("", None, "192.168.1.1", "localhost", "example", "exa mple.cz", "-a.cz", "a..cz", "*.", "*")), [x for x in ("", None, "192.168.1.1", "localhost", "example", "exa mple.cz", "-a.cz", "a..cz", "*.", "*") if ND(x) is not None])
    OH = dealers.origin_host
    over("A9 origin_host: https/http, port, velka pismena; 'null', bez schematu, IP, prazdne -> None",
         OH("https://Shop.Example.cz:8443") == "shop.example.cz" and OH("http://shop.example.cz") == "shop.example.cz"
         and all(OH(x) is None for x in ("null", "shop.example.cz", "https://10.0.0.1", "", None, "https://localhost")), None)
    DM = dealers.domain_matches
    over("A10 domain_matches: presna shoda; *.x.cz = jen subdomeny (ne apex, ne podobny retezec evilx.cz)",
         DM("shop.example.cz", "shop.example.cz") and not DM("shop.example.cz", "example.cz") and DM("a.partner.cz", "*.partner.cz") and DM("a.b.partner.cz", "*.partner.cz")
         and not DM("partner.cz", "*.partner.cz") and not DM("evilpartner.cz", "*.partner.cz") and not DM("partner.cz.evil.cz", "*.partner.cz") and not DM("", "a.cz") and not DM("a.cz", ""), None)
    SL = dealers.sanitize_landing
    over("A11 sanitize_landing: bezna cesta projde, vsechny pokusy o open redirect -> '/'",
         SL("/produkt/profil-30x30?a=1") == "/produkt/profil-30x30?a=1" and SL("/") == "/"
         and all(SL(x) == "/" for x in ("//evil.com", "/\\evil.com", "http://evil.com", "https://evil.com/x", "evil.com", "", None, "javascript:alert(1)", "/a\r\nSet-Cookie: x=1", "/" + "a" * 300, "//", "/\t/evil.com")),
         [x for x in ("//evil.com", "/\\evil.com", "http://evil.com", "https://evil.com/x", "evil.com", "", None, "javascript:alert(1)", "/a\r\nSet-Cookie: x=1", "//", "/\t/evil.com") if SL(x) != "/"])
    P = dealers._pct
    over("A12 _pct: None/'' -> None, 0 a 100 platne, carka, zaokrouhleni na 2 mista", P(None) is None and P("") is None and P(0) == 0.0 and P(100) == 100.0 and P("12,5") == 12.5 and P(7.556) == 7.56, None)
    chyby_pct = []
    for x in (-1, 100.01, "abc", True, float("nan"), [], {}):
        try:
            P(x)
            chyby_pct.append(x)
        except ValueError:
            pass
    over("A13 _pct: zaporne, nad 100, text, bool, NaN, seznam -> ValueError", not chyby_pct, chyby_pct)
    over("A14 _plain_text: HTML tagy pryc, entity, mezery, limit", dealers._plain_text("<p>Ahoj&nbsp;<b>svete</b> &amp; spol.</p>\n\n  dal") == "Ahoj svete & spol. dal" and len(dealers._plain_text("x" * 5000)) == 2000, dealers._plain_text("<p>Ahoj&nbsp;<b>svete</b></p>"))
    over("A15 _brand_hit: Logiman, konfigurator, vandrawee, Vandr, dodavatel profilu (jakakoli velikost); bezny text ne",
         all(dealers._brand_hit(x) for x in ("Logiman s.r.o.", "KONFIGURÁTOR", "konfigurator", "vanDrawee", "Vandr", "DOGUS", "profil Dogus 30x30")) and not any(dealers._brand_hit(x) for x in ("Profil 30x30 hlinik", "", None, "Eurobox 400x300")), None)
    with appmod.app.test_request_context("/"):
        r429 = dealers.DealerAuthError(429, "rate_limited").response()
        r401 = dealers.DealerAuthError(401, "invalid_key").response()
        over("A16 DealerAuthError.response: 429 s Retry-After, 401 bez, oboje Cache-Control no-store a JSON {error, code}",
             r429.status_code == 429 and r429.headers.get("Retry-After") == "60" and r401.status_code == 401 and "Retry-After" not in r401.headers
             and r429.headers.get("Cache-Control") == "private, no-store" and r401.get_json()["code"] == "invalid_key" and r401.get_json()["error"], (r429.status_code, dict(r429.headers)))

    # ============================================================================================================ B) overeni klicu
    print("== B resolve_public_key / resolve_secret_key")
    A = vloz_dealera("alfa000001", "Alfa s.r.o.", email="alfa@example.cz", ico="12 345 678")
    B2 = vloz_dealera("beta000002", "Beta", order_path="dealer", disc=20)
    G3 = vloz_dealera("gama000003", "Gama", status="suspended")
    D4 = vloz_dealera("delt000004", "Delta", status="pending")
    E5 = vloz_dealera("epsi000005", "Epsilon", is_active=0)
    for d_id, dom in ((A["id"], "shop.example.cz"), (A["id"], "*.partner.cz"), (B2["id"], "beta.cz"), (G3["id"], "gama.cz")):
        sql("INSERT INTO dealer_domains (dealer_id, domain) VALUES (%s,%s)", (d_id, dom))
    sql("INSERT INTO dealer_domains (dealer_id, domain, is_active) VALUES (%s,%s,0)", (A["id"], "vypnuta.example.cz"))
    PK = {n: "pk_" + (f"{i:02d}" * 12)[:24] for i, n in enumerate(("ok", "revoked", "expired", "gama", "wrongkind", "inactive", "ratelim", "alfa_od", "touch"), start=1)}
    vloz_klic(A["id"], "widget", PK["ok"])
    vloz_klic(A["id"], "widget", PK["revoked"], active=0, revoked=NYNI)
    vloz_klic(A["id"], "widget", PK["expired"], expires=NYNI - datetime.timedelta(minutes=1))
    vloz_klic(G3["id"], "widget", PK["gama"])
    vloz_klic(A["id"], "api", PK["wrongkind"], secret="x" * 40)
    vloz_klic(A["id"], "widget", PK["inactive"], active=0)
    vloz_klic(A["id"], "widget", PK["ratelim"], rate=3)
    vloz_klic(A["id"], "widget", PK["touch"])
    RPK = dealers.resolve_public_key

    def chyba(fn, *a, **k):
        try:
            fn(*a, **k)
            return None
        except dealers.DealerAuthError as e:
            return (e.status, e.code)

    d, k = RPK(PK["ok"], "https://shop.example.cz", "1.1.1.1")
    over("B1 platny widget klic + povolena domena -> (dealer, klic)", d["id"] == A["id"] and k["public_id"] == PK["ok"], (d, k))
    over("B2 wildcard *.partner.cz pusti subdomenu, ne apex", RPK(PK["ok"], "https://x.partner.cz", "1.1.1.1")[0]["id"] == A["id"] and chyba(RPK, PK["ok"], "https://partner.cz", "1.1.1.1") == (403, "origin_not_allowed"), chyba(RPK, PK["ok"], "https://partner.cz", "1.1.1.1"))
    over("B3 jina domena -> 403 origin_not_allowed, vypnuta (is_active=0) domena taky", chyba(RPK, PK["ok"], "https://evil.cz", "1.1.1.1") == (403, "origin_not_allowed") and chyba(RPK, PK["ok"], "https://vypnuta.example.cz", "1.1.1.1") == (403, "origin_not_allowed"), None)
    over("B4 bez Origin / 'null' / IP -> 403 origin_missing", all(chyba(RPK, PK["ok"], o, "1.1.1.1") == (403, "origin_missing") for o in (None, "", "null", "https://10.1.2.3")), None)
    over("B5 neznamy, spatny tvar, odvolany, vypresly, neaktivni klic -> 401 invalid_key",
         all(chyba(RPK, x, "https://shop.example.cz", "1.1.1.1") == (401, "invalid_key") for x in ("pk_" + "f" * 24, "", None, "pk_short", PK["revoked"], PK["expired"], PK["inactive"], PK["wrongkind"])), [chyba(RPK, x, "https://shop.example.cz", "1.1.1.1") for x in (PK["revoked"], PK["expired"], PK["inactive"], PK["wrongkind"])])
    over("B6 klic pozastaveneho dealera -> 403 dealer_inactive (i pending/is_active=0)", chyba(RPK, PK["gama"], "https://gama.cz", "1.1.1.1") == (403, "dealer_inactive"), chyba(RPK, PK["gama"], "https://gama.cz", "1.1.1.1"))
    r1 = [chyba(RPK, PK["ratelim"], "https://shop.example.cz", "2.2.2.2") for _ in range(5)]
    over("B7 limit pozadavku na klic (3/min): 4. a 5. volani -> 429 rate_limited", r1 == [None, None, None, (429, "rate_limited"), (429, "rate_limited")], r1)
    sql("UPDATE dealer_keys SET last_used_at=NULL, last_used_ip=NULL WHERE public_id=%s", (PK["touch"],))
    RPK(PK["touch"], "https://shop.example.cz", "3.3.3.3")
    t1 = sql("SELECT last_used_at, last_used_ip FROM dealer_keys WHERE public_id=%s", (PK["touch"],))[0]
    RPK(PK["touch"], "https://shop.example.cz", "4.4.4.4")
    t2 = sql("SELECT last_used_at, last_used_ip FROM dealer_keys WHERE public_id=%s", (PK["touch"],))[0]
    over("B8 last_used se zapise pri prvnim pouziti a dalsi do minuty nezapisuje (neni zapis na kazdy pozadavek)", t1["last_used_at"] is not None and t1["last_used_ip"] == "3.3.3.3" and t2 == t1, (t1, t2))
    with real.cursor() as c:
        sql("UPDATE dealer_keys SET last_used_at=NULL WHERE public_id=%s", (PK["touch"],))
        RPK(PK["touch"], "https://shop.example.cz", "5.5.5.5", cur=c)
    over("B9 s predanym cur se NIC nezapisuje (last_used zustane NULL)", sql("SELECT last_used_at FROM dealer_keys WHERE public_id=%s", (PK["touch"],))[0]["last_used_at"] is None, None)

    SK_API = dealers.new_secret_key("api")
    SK_FEED = dealers.new_secret_key("feed")
    SK_IP = dealers.new_secret_key("api")
    SK_REV = dealers.new_secret_key("api")
    SK_EXP = dealers.new_secret_key("api")
    SK_G = dealers.new_secret_key("api")
    SK_RATE = dealers.new_secret_key("api")
    vloz_klic(B2["id"], "api", SK_API[0], secret=SK_API[1], scopes="orders,quote")
    vloz_klic(B2["id"], "feed", SK_FEED[0], secret=SK_FEED[1], scopes="feed")
    vloz_klic(B2["id"], "api", SK_IP[0], secret=SK_IP[1], scopes="orders", ips="9.9.9.9, 8.8.8.8")
    vloz_klic(B2["id"], "api", SK_REV[0], secret=SK_REV[1], scopes="orders", active=0, revoked=NYNI)
    vloz_klic(B2["id"], "api", SK_EXP[0], secret=SK_EXP[1], scopes="orders", expires=NYNI - datetime.timedelta(seconds=5))
    vloz_klic(G3["id"], "api", SK_G[0], secret=SK_G[1], scopes="orders")
    vloz_klic(B2["id"], "api", SK_RATE[0], secret=SK_RATE[1], scopes="orders", rate=2)
    RSK = dealers.resolve_secret_key
    d, k = RSK("Bearer " + SK_API[2], "7.7.7.7", scope="orders")
    over("B10 platny tajny klic + scope -> (dealer, klic)", d["id"] == B2["id"] and k["public_id"] == SK_API[0], None)
    over("B11 feed klic nema scope orders (403 scope_denied), ale feed ano", chyba(RSK, "Bearer " + SK_FEED[2], "7.7.7.7", scope="orders") == (403, "scope_denied") and RSK(SK_FEED[2], "7.7.7.7", scope="feed")[0]["id"] == B2["id"], chyba(RSK, "Bearer " + SK_FEED[2], "7.7.7.7", scope="orders"))
    spatna_tajna = f"{SK_API[0]}_{'A' * 43}"
    over("B12 spravne public_id + spatna tajna / neznamy klic / bez predpony Bearer / prazdny -> 401 invalid_key (stejne hlaseni)",
         all(chyba(RSK, x, "7.7.7.7", scope="orders") == (401, "invalid_key") for x in (spatna_tajna, "sk_00000000_" + "A" * 43, "x", "", None, "Bearer ")), None)
    over("B13 odvolany a vypresly klic -> 401 invalid_key (nerozlisuje se od neznameho)", chyba(RSK, SK_REV[2], "7.7.7.7", scope="orders") == (401, "invalid_key") and chyba(RSK, SK_EXP[2], "7.7.7.7", scope="orders") == (401, "invalid_key"), None)
    over("B14 klic pozastaveneho dealera -> 403 dealer_inactive", chyba(RSK, SK_G[2], "7.7.7.7", scope="orders") == (403, "dealer_inactive"), chyba(RSK, SK_G[2], "7.7.7.7", scope="orders"))
    over("B15 seznam IP u klice: povolena IP projde, jina 403 ip_not_allowed; klic bez seznamu pusti vsechny", RSK(SK_IP[2], "8.8.8.8", scope="orders")[0]["id"] == B2["id"] and chyba(RSK, SK_IP[2], "1.2.3.4", scope="orders") == (403, "ip_not_allowed"), chyba(RSK, SK_IP[2], "1.2.3.4", scope="orders"))
    r2 = [chyba(RSK, SK_RATE[2], "6.6.6.6", scope="orders") for _ in range(4)]
    over("B16 limit pozadavku na tajny klic (2/min): 3. volani -> 429", r2 == [None, None, (429, "rate_limited"), (429, "rate_limited")], r2)
    over("B17 klic widgetu nelze pouzit jako tajny a naopak (pk_ v Authorization = 401)", chyba(RSK, PK["ok"], "7.7.7.7") == (401, "invalid_key") and chyba(RPK, SK_API[2], "https://beta.cz", "7.7.7.7") == (401, "invalid_key"), None)
    uloz = sql("SELECT public_id, secret_hash FROM dealer_keys WHERE public_id=%s", (SK_API[0],))[0]
    over("B18 v DB je jen sha256 tajne casti (tajna ani cely token se nikde neuklada)", uloz["secret_hash"] == hashlib.sha256(SK_API[1].encode()).hexdigest() and SK_API[1] not in json.dumps(uloz, default=str), uloz)

    # ============================================================================================================ C) proklik a atribuce
    print("== C /api/dealer/go a atribuce objednavky")
    klient = appmod.app.test_client()

    def go(ref, to=None, ua="Mozilla/5.0 (X11; Linux) Firefox/130.0", ip="10.1.1.1"):
        q = f"/api/dealer/go/{ref}" + (f"?to={to}" if to is not None else "")
        return klient.get(q, headers={"User-Agent": ua, "X-Real-IP": ip})

    def cookie_dlr(resp):
        for h in resp.headers.getlist("Set-Cookie"):
            if h.startswith("dlr="):
                return h
        return None

    r = go("alfa000001", "/produkt/profil-30x30")
    set_cookie = cookie_dlr(r)
    over("C1 platny dealer: 302 na ?to= (relativne), Cache-Control no-store", r.status_code == 302 and r.headers["Location"] == "/produkt/profil-30x30" and r.headers.get("Cache-Control") == "no-store", (r.status_code, r.headers.get("Location")))
    over("C2 cookie dlr: 32 hex, 30 dni (2592000 s), HttpOnly, Secure, SameSite=Lax, Path=/",
         bool(set_cookie) and re.match(r"^dlr=[0-9a-f]{32};", set_cookie) and "Max-Age=2592000" in set_cookie and "HttpOnly" in set_cookie and "Secure" in set_cookie and "SameSite=Lax" in set_cookie and "Path=/" in set_cookie, set_cookie)
    token1 = re.match(r"^dlr=([0-9a-f]{32})", set_cookie).group(1) if set_cookie else None
    kl = sql("SELECT * FROM dealer_clicks WHERE token=%s", (token1,))
    over("C3 klik je v DB: dealer, token, cil, ip_hash (ne IP), cas", len(kl) == 1 and kl[0]["dealer_id"] == A["id"] and kl[0]["landing"] == "/produkt/profil-30x30" and kl[0]["ip_hash"] and "10.1.1.1" not in str(kl[0]["ip_hash"]) and len(kl[0]["ip_hash"]) == 16, kl)
    n_pred = sql("SELECT COUNT(*) AS n FROM dealer_clicks")[0]["n"]
    nic = {}
    nic["neznamy"] = go("nonexist01", "/x")
    nic["suspended"] = go("gama000003", "/x")
    nic["pending"] = go("delt000004", "/x")
    nic["neaktivni"] = go("epsi000005", "/x")
    nic["cesta_dealer"] = go("beta000002", "/x")
    nic["robot"] = go("alfa000001", "/x", ua="Googlebot/2.1 (+http://www.google.com/bot.html)")
    nic["curl"] = go("alfa000001", "/x", ua="curl/8.4.0")
    nic["spatny_kod"] = go("AB'; DROP TABLE dealers;--", "/x")
    over("C4 neznamy / pozastaveny / pending / neaktivni dealer / dealer s cestou 'dealer' / robot / curl / zlomyslny kod: STEJNE presmerovani, ale zadna cookie a zadny zapis",
         all(v.status_code in (302, 404) and cookie_dlr(v) is None for v in nic.values()) and sql("SELECT COUNT(*) AS n FROM dealer_clicks")[0]["n"] == n_pred
         and all(nic[k].headers.get("Location") == "/x" for k in ("neznamy", "suspended", "pending", "neaktivni", "cesta_dealer", "robot", "curl")), {k: (v.status_code, v.headers.get("Location"), cookie_dlr(v)) for k, v in nic.items()})
    over("C5 open redirect: //evil.com, /\\evil.com, http://evil.com, bez to -> vzdy '/' na nasem webu (a klik se i tak zapise u platneho dealera)",
         all(go("alfa000001", x).headers["Location"] == "/" for x in ("//evil.com", "/%5Cevil.com".replace("%5C", "\\"), "http://evil.com", "javascript:alert(1)")) and go("alfa000001").headers["Location"] == "/", [go("alfa000001", x).headers["Location"] for x in ("//evil.com", "http://evil.com")])
    sql("DELETE FROM dealer_clicks WHERE landing='/'")
    rl = [go("alfa000001", "/limit", ip="10.9.9.9").status_code for _ in range(125)]
    kliku = sql("SELECT COUNT(*) AS n FROM dealer_clicks WHERE landing='/limit'")[0]["n"]
    over("C6 limit 120 prokliku za minutu z jedne IP: dal se jen presmeruje (302), nezapisuje se", set(rl) == {302} and kliku == 120, (set(rl), kliku))

    # --- atribuce objednavky
    def vloz_objednavku(email="zakaznik@example.cz", ico=None, is_test=0):
        sql("INSERT INTO shop_orders (order_number, status, customer_name, customer_email, billing_ico, is_test) VALUES (%s,'nova','Jan Novak',%s,%s,%s)",
            (f"T{datetime.datetime.now().strftime('%H%M%S%f')}", email, ico, is_test))
        return sql("SELECT id FROM shop_orders ORDER BY id DESC LIMIT 1")[0]["id"]

    AFN = dealers.attribution_for_new_order
    with real.cursor() as c:
        ok = AFN(c, token1, {"id": 999999}, "zakaznik@example.cz")
        over("C7 platny klik < 30 dni, aktivni dealer s cestou 'our' -> {dealer_id, click_id, order_path:'our'}", ok and ok["dealer_id"] == A["id"] and ok["order_path"] == "our" and ok["click_id"] == kl[0]["id"], ok)
        over("C8 neznamy / spatny tvar / prazdny token / testovaci objednavka -> None", all(AFN(c, t, None, "a@b.cz") is None for t in ("0" * 32, "x", "", None)) and AFN(c, token1, None, "a@b.cz", is_test=True) is None, None)
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI - datetime.timedelta(days=29, hours=23), token1))
        c1 = AFN(c, token1, None, "a@b.cz")
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI - datetime.timedelta(days=30, minutes=5), token1))
        c2 = AFN(c, token1, None, "a@b.cz")
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI, token1))
        over("C9 platnost 30 dni od prokliku: po 29 d 23 h jeste ano, po 30 d 5 min uz ne", c1 is not None and c2 is None, (c1, c2))
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_attribution_days','7') ON DUPLICATE KEY UPDATE setting_value='7'")
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI - datetime.timedelta(days=8), token1))
        c3 = AFN(c, token1, None, "a@b.cz")
        sql("DELETE FROM app_settings WHERE setting_key='dealer_attribution_days'")
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI, token1))
        over("C10 delka atribuce je nastavitelna (app_settings.dealer_attribution_days=7: po 8 dnech uz ne)", c3 is None, c3)
        sql("UPDATE dealers SET user_id=%s WHERE id=%s", (424242, A["id"]))
        over("C11 vlastni nakup dealera: prihlaseny je ucet dealera / e-mail kontaktu (bez ohledu na velikost pismen) / ICO (s mezerami) -> None, jiny zakaznik ano",
             AFN(c, token1, {"id": 424242}, "x@y.cz") is None and AFN(c, token1, {"id": 1}, " ALFA@Example.cz ") is None and AFN(c, token1, {"id": 1}, "x@y.cz", billing_ico="12345678") is None
             and AFN(c, token1, {"id": 1}, "x@y.cz", billing_ico="99999999") is not None, None)
        sql("UPDATE dealers SET user_id=NULL WHERE id=%s", (A["id"],))
        sql("UPDATE dealers SET status='suspended' WHERE id=%s", (A["id"],))
        s1 = AFN(c, token1, None, "a@b.cz")
        sql("UPDATE dealers SET status='active', order_path='dealer' WHERE id=%s", (A["id"],))
        s2 = AFN(c, token1, None, "a@b.cz")
        sql("UPDATE dealers SET order_path='our', is_active=0 WHERE id=%s", (A["id"],))
        s3 = AFN(c, token1, None, "a@b.cz")
        sql("UPDATE dealers SET is_active=1 WHERE id=%s", (A["id"],))
        over("C12 dealer mezitim pozastaven / prepnut na cestu 'dealer' / vypnut -> atribuce None (provize se nepripise)", s1 is None and s2 is None and s3 is None, (s1, s2, s3))

        oid = vloz_objednavku()
        okc = dealers.attach_attribution(c, oid, {"id": 1}, click_token=token1)
        radek = sql("SELECT dealer_id, dealer_click_id, order_path FROM shop_orders WHERE id=%s", (oid,))[0]
        over("C13 attach_attribution pripise objednavku dealerovi (dealer_id, dealer_click_id, order_path='our')", okc is True and radek["dealer_id"] == A["id"] and radek["dealer_click_id"] == kl[0]["id"] and radek["order_path"] == "our", radek)
        over("C14 uz pripsana objednavka se neprepisuje (druhy klik jineho dealera ji nezmeni)", dealers.attach_attribution(c, oid, {"id": 1}, click_token="a" * 32) is False and sql("SELECT dealer_id FROM shop_orders WHERE id=%s", (oid,))[0]["dealer_id"] == A["id"], None)
        def attach_bez_cookie(cur_, order_id_):
            with appmod.app.test_request_context("/"):          # bez cookie dlr
                return dealers.attach_attribution(cur_, order_id_, {"id": 1})
        oid2 = vloz_objednavku(email="alfa@example.cz")
        oid3 = vloz_objednavku(is_test=1)
        oid4 = vloz_objednavku()
        over("C15 vlastni nakup (e-mail dealera) a testovaci objednavka se nepripisuji, bez cookie ani klik nic", dealers.attach_attribution(c, oid2, {"id": 1}, click_token=token1) is False and dealers.attach_attribution(c, oid3, {"id": 1}, click_token=token1) is False
             and attach_bez_cookie(c, oid4) is False and all(sql("SELECT dealer_id FROM shop_orders WHERE id=%s", (o,))[0]["dealer_id"] is None for o in (oid2, oid3, oid4)), None)
        over("C16 neexistujici objednavka nebo chyba v DB: vrati False a NEvyhodi vyjimku (objednavka se nesmi rozbit)", dealers.attach_attribution(c, 987654321, {"id": 1}, click_token=token1) is False, None)
    # last-click: druhy prokliv jineho dealera prepise cookie, atribuce bere ten posledni (klient drzi jen jednu cookie)
    r_b = go("alfa000001", "/druhy")
    over("C17 last-click: dalsi prokliv vydava novou cookie s jinym tokenem (stary token zustava v historii)", cookie_dlr(r_b) and cookie_dlr(r_b).split(";")[0] != set_cookie.split(";")[0], None)

    # ============================================================================================================ D) sazby
    print("== D dealerska sleva, provize, cena")
    cat_profily = 149
    c150 = sql("SELECT id, parent_id FROM content_categories WHERE id=150")[0]
    over("D0 predpoklad: kategorie 150 je podkategorie 149 (profily)", c150["parent_id"] == 149, c150)
    DEA = sql("SELECT * FROM dealers WHERE id=%s", (A["id"],))[0]
    with real.cursor() as c:
        over("D1 provize bez nastaveni: vychozi 10 %", dealers.dealer_commission_pct(c, DEA, None) == 10.0 and dealers.dealer_commission_pct(c, DEA, 150) == 10.0, None)
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_commission_default_pct','12.5') ON DUPLICATE KEY UPDATE setting_value='12.5'")
        over("D2 vychozi provize z nastaveni (app_settings.dealer_commission_default_pct = 12,5)", dealers.dealer_commission_pct(c, DEA, 150) == 12.5, None)
        sql("DELETE FROM app_settings WHERE setting_key='dealer_commission_default_pct'")
        sql("UPDATE dealers SET default_commission_pct=8 WHERE id=%s", (A["id"],))
        DEA = sql("SELECT * FROM dealers WHERE id=%s", (A["id"],))[0]
        over("D3 vychozi provize dealera (8) prebije nastaveni", dealers.dealer_commission_pct(c, DEA, 150) == 8.0, None)
        sql("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct, commission_pct) VALUES (%s,%s,NULL,15)", (A["id"], cat_profily))
        over("D4 sazba kategorie 149 (15 %) plati i pro podkategorii 150 (dedi se), pro jinou kategorii ne",
             dealers.dealer_commission_pct(c, DEA, 149) == 15.0 and dealers.dealer_commission_pct(c, DEA, 150) == 15.0 and dealers.dealer_commission_pct(c, DEA, 1) == 8.0, (dealers.dealer_commission_pct(c, DEA, 150), dealers.dealer_commission_pct(c, DEA, 1)))
        sql("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct, commission_pct) VALUES (%s,150,NULL,5)", (A["id"],))
        over("D5 nejblizsi nadrazena vyhrava: sazba primo na 150 (5 %) prebije 149 (15 %)", dealers.dealer_commission_pct(c, DEA, 150) == 5.0 and dealers.dealer_commission_pct(c, DEA, 149) == 15.0, None)
        sql("UPDATE dealer_rates SET commission_pct=NULL WHERE dealer_id=%s AND category_id=150", (A["id"],))
        over("D6 NULL na podkategorii = zdedit od nadrazene (15 %)", dealers.dealer_commission_pct(c, DEA, 150) == 15.0, None)
        P0 = {"id": 1, "category_id": 150, "dealer_discount_percent": None, "price_czk_placeholder": 1000}
        over("D7 dealerska sleva bez zadneho nastaveni = None (dealer nema cenu)", dealers.dealer_discount_pct(c, DEA, P0) is None and dealers.dealer_effective_price(c, P0, DEA) == (None, None), None)
        sql("UPDATE dealers SET default_discount_pct=10 WHERE id=%s", (A["id"],))
        DEA = sql("SELECT * FROM dealers WHERE id=%s", (A["id"],))[0]
        sql("UPDATE dealer_rates SET discount_pct=25 WHERE dealer_id=%s AND category_id=149", (A["id"],))
        over("D8 sleva: vychozi dealera 10, sazba kategorie 149 = 25 (plati i pro 150), jina kategorie 10", dealers.dealer_discount_pct(c, DEA, P0) == 25.0 and dealers.dealer_discount_pct(c, DEA, dict(P0, category_id=1)) == 10.0, None)
        over("D9 sleva primo na produktu (existujici shop_products.dealer_discount_percent = 40) prebije vse, 0 se bere jako nenastaveno",
             dealers.dealer_discount_pct(c, DEA, dict(P0, dealer_discount_percent=40)) == 40.0 and dealers.dealer_discount_pct(c, DEA, dict(P0, dealer_discount_percent=0)) == 25.0, None)
        over("D10 sleva bez kategorie produktu (category_id NULL) -> vychozi dealera", dealers.dealer_discount_pct(c, DEA, dict(P0, category_id=None)) == 10.0, None)
        prod = sql("SELECT * FROM shop_products WHERE active=1 AND is_archived=0 AND price_czk_placeholder>=100 AND sale_price_czk IS NULL AND id NOT IN (SELECT shop_product_id FROM product_assemblies WHERE shop_product_id IS NOT NULL) AND sku NOT LIKE 'VD-%%' LIMIT 1")[0]
        sql("UPDATE dealer_rates SET discount_pct=NULL WHERE dealer_id=%s", (A["id"],))
        cena, zaklad = dealers.dealer_effective_price(c, dict(prod, category_id=None, dealer_discount_percent=None), DEA)
        over("D11 dealerska cena = cena z ceniku x (1 - 10 %), zaklad 'dealer'", zaklad == "dealer" and abs(cena - round(float(prod["price_czk_placeholder"]) * 0.9, 2)) < 0.005, (cena, zaklad, prod["price_czk_placeholder"]))
        sale = round(float(prod["price_czk_placeholder"]) * 0.5, 2)
        cena2, zaklad2 = dealers.dealer_effective_price(c, dict(prod, category_id=None, dealer_discount_percent=None, sale_price_czk=sale, sale_price_from=None, sale_price_until=None), DEA)
        over("D12 akcni cena nizsi nez dealerska -> plati akcni (jedna nejnizsi z vylucnych cen), zaklad 'sale'", zaklad2 == "sale" and abs(cena2 - sale) < 0.005, (cena2, zaklad2))

    # ============================================================================================================ E) pohled na produkt
    print("== E dealer_product_view (whitelist, fail closed)")
    ZAKAZANA_POLE = {"glb_file", "fbx_original_name", "supplier_name", "supplier_id", "dogus_url", "dogus_list_price_usd", "price_source_url", "cfg_dily_id", "min_stock", "max_stock",
                     "stock_qty", "source_url", "dealer_discount_percent", "sale_price_czk", "price_czk_placeholder", "dealer_price", "markup", "markup_pct", "dealer_price_net"}
    with real.cursor() as c:
        pv = dealers.dealer_product_view(c, prod["id"], "retail")
        over("E1 bezny produkt, retail: whitelist poli, cena bez/s DPH (x1,21), zadne zakazane pole",
             pv and set(pv) >= {"id", "sku", "name", "slug", "description", "unit", "category_path", "images", "availability", "price_net_czk", "price_gross_czk", "vat_rate"} and not (set(pv) & ZAKAZANA_POLE)
             and abs(pv["price_gross_czk"] - round(pv["price_net_czk"] * 1.21, 2)) < 0.011 and pv["vat_rate"] == 21.0, pv and sorted(pv))
        over("E2 images jen /content-files/gallery/<cesta k souboru> (zadny zdrojovy URL, zadne .., jen pole path)", pv["images"] and all(re.match(r"^/content-files/gallery/[^?#:]+$", i["path"]) and ".." not in i["path"] and set(i) == {"path"} for i in pv["images"]), pv["images"][:2])
        nv = dealers.dealer_product_view(c, dict(prod), "none")
        over("E3 mode 'none' = bez jakychkoli cen (price_*, vat_rate)", nv and not any(k.startswith("price") or k == "vat_rate" for k in nv), nv and sorted(nv))
        over("E4 pohled se vzdy nacte z DB znovu: uvadene hodnoty od volajiciho se ignoruji (podvrzena cena/nazev)",
             dealers.dealer_product_view(c, dict(prod, price_czk_placeholder=1, name="PODVRH"), "retail")["name"] == prod["name"] and dealers.dealer_product_view(c, dict(prod, price_czk_placeholder=1), "retail")["price_net_czk"] == pv["price_net_czk"], None)
        DEA = sql("SELECT * FROM dealers WHERE id=%s", (B2["id"],))[0]
        dv = dealers.dealer_product_view(c, prod["id"], "dealer_final", dealer=DEA, markup_pct=30)
        zaklad_dealer = round(float(prod["price_czk_placeholder"]) * 0.8, 2)
        over("E5 dealer_final: cena = dealerska cena (sleva 20 %) x 1,30, do vysledku jde JEN cena (zadna dealerska cena, zadna prirazka, zadna sleva)",
             dv and abs(dv["price_net_czk"] - round(zaklad_dealer * 1.3, 2)) < 0.011 and not (set(dv) & ZAKAZANA_POLE) and "discount" not in json.dumps(dv).lower() and "markup" not in json.dumps(dv).lower(), dv and (dv.get("price_net_czk"), zaklad_dealer))
        over("E6 dealer_final bez dealera / bez prirazky / dealer bez slevy -> None (fail closed, nikdy cena bez prirazky)",
             dealers.dealer_product_view(c, prod["id"], "dealer_final") is None and dealers.dealer_product_view(c, prod["id"], "dealer_final", dealer=DEA) is None
             and dealers.dealer_product_view(c, prod["id"], "dealer_final", dealer=dict(DEA, default_discount_pct=None), markup_pct=10) is None, None)
        try:
            dealers.dealer_product_view(c, prod["id"], "nesmysl")
            e7 = False
        except ValueError:
            e7 = True
        over("E7 neznamy mode -> ValueError", e7, None)
        vd = sql("SELECT id FROM shop_products WHERE active=1 AND is_archived=0 AND sku LIKE 'VD-%%' AND price_czk_placeholder>0 LIMIT 1")
        asm = sql("SELECT sp.id FROM shop_products sp JOIN product_assemblies pa ON pa.shop_product_id=sp.id WHERE sp.active=1 AND sp.is_archived=0 AND sp.price_czk_placeholder>0 LIMIT 1")
        typ = sql("SELECT id FROM shop_products WHERE active=1 AND is_archived=0 AND zalozeno_automaticky_typologie_id IS NOT NULL AND price_czk_placeholder>0 LIMIT 1")
        nea = sql("SELECT id FROM shop_products WHERE active=0 LIMIT 1")
        arch = sql("SELECT id FROM shop_products WHERE is_archived=1 LIMIT 1")
        bez_ceny = sql("SELECT id FROM shop_products WHERE active=1 AND is_archived=0 AND (price_czk_placeholder IS NULL OR price_czk_placeholder<=0) LIMIT 1")
        nevid = sql("SELECT p.id FROM shop_products p JOIN content_categories cc ON cc.id=p.category_id WHERE p.active=1 AND p.is_archived=0 AND cc.is_visible=0 AND p.price_czk_placeholder>0 LIMIT 1")
        PV = lambda row: dealers.dealer_product_view(c, row[0]["id"], "retail") if row else None      # chybejici vzorek: bez nalezu (viz poznamka v popisku)
        over(f"E8 sestavy se nenabizeji: Vandr VD-* / karta s product_assemblies / automaticky zalozena karta typologie -> None (vzorky: VD {len(vd)}, sestava {len(asm)}, typologie {len(typ)})",
             PV(vd) is None and PV(asm) is None and PV(typ) is None and len(vd) >= 1, [PV(vd), PV(asm), PV(typ)])
        over(f"E9 neaktivni, archivovany, bez ceny, v neviditelne kategorii -> None, neexistujici id -> None (vzorky: {len(nea)}/{len(arch)}/{len(bez_ceny)}/{len(nevid)})",
             PV(nea) is None and PV(arch) is None and PV(bez_ceny) is None and PV(nevid) is None and dealers.dealer_product_view(c, 2147483000, "retail") is None and len(nea) >= 1, [PV(nea), PV(arch), PV(bez_ceny), PV(nevid)])
        puvodni_re = dealers._BRAND_RE
        slova = re.findall(r"\w{3,}", prod["name"])
        slovo = slova[0] if slova else prod["name"]
        dealers._BRAND_RE = re.compile(re.escape(slovo), re.I)
        v_nazev = dealers.dealer_product_view(c, prod["id"], "retail")
        dealers._BRAND_RE = re.compile("QQQ_NIKDY_NENI_V_NAZVU", re.I)
        v_ok = dealers.dealer_product_view(c, prod["id"], "retail")
        cesta_slovo = (pv["category_path"] or [None])[0]
        if cesta_slovo:
            dealers._BRAND_RE = re.compile(re.escape(cesta_slovo), re.I)
            v_kat = dealers.dealer_product_view(c, prod["id"], "retail")
        else:
            v_kat = None
        dealers._BRAND_RE = puvodni_re
        over("E10 fail closed na znacku: slovo v nazvu (a v nazvu kategorie) = produkt se VYNECHA, bez nalezu normalne vyjde", v_nazev is None and v_ok is not None and (v_kat is None), (slovo, v_nazev and 1, v_ok and 1, cesta_slovo))
        # prochazka vsemi produkty: nic zakazaneho neunikne a vse ma pole z whitelistu
        vsechny = sql("SELECT id FROM shop_products WHERE active=1 AND is_archived=0")
        videno, zakazano, text_znacka = 0, 0, 0
        for r_ in vsechny:
            v_ = dealers.dealer_product_view(c, r_["id"], "retail")
            if not v_:
                continue
            videno += 1
            if set(v_) & ZAKAZANA_POLE:
                zakazano += 1
            if dealers._brand_hit(json.dumps(v_, ensure_ascii=False)):
                text_znacka += 1
        over(f"E12 vsechny aktivni produkty ({len(vsechny)}): pro dealery je viditelnych {videno}, zadny nenese zakazane pole ani znacku v textu", videno > 100 and zakazano == 0 and text_znacka == 0, (videno, zakazano, text_znacka))

    # ============================================================================================================ F) administrace a panel
    print("== F administrace dealeru a partnersky panel")
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]
    user_ids = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 3")]
    staff = sql("SELECT id FROM app_users WHERE role IN ('skladnik','ucetni') AND active=1 LIMIT 1")

    def jako(user_id):
        k = appmod.app.test_client()
        if user_id is not None:
            with k.session_transaction() as s:
                s["user_id"] = user_id
        return k

    adm = jako(admin_id)
    over("F1 bez prihlaseni 401, zakaznik (role user) a zamestnanec bez prava 403 na vsech admin endpointech",
         all(jako(None).get(u).status_code == 401 for u in ("/api/admin/dealers", "/api/admin/dealers/1")) and jako(user_ids[0]).get("/api/admin/dealers").status_code == 403
         and (not staff or jako(staff[0]["id"]).get("/api/admin/dealers").status_code == 403) and jako(user_ids[0]).post("/api/admin/dealers/1/keys", json={"kind": "widget"}).status_code == 403, jako(user_ids[0]).get("/api/admin/dealers").status_code)
    r = adm.post("/api/admin/dealers", json={"name": "Novy Dealer s.r.o.", "contact_email": "novy@example.cz", "ico": "87654321", "status": "active", "default_discount_pct": "15,5", "default_commission_pct": 7})
    nd = r.get_json()["dealer"] if r.status_code == 201 else None
    over("F2 vytvoreni dealera: 201, ref_code 10 znaku z povolene abecedy, vychozi cesta 'our', sazby ulozeny, No-store", r.status_code == 201 and re.match(r"^[abcdefghjkmnpqrstuvwxyz23456789]{10}$", nd["ref_code"]) and nd["order_path"] == "our"
         and nd["default_discount_pct"] == 15.5 and nd["default_commission_pct"] == 7.0 and r.headers.get("Cache-Control") == "private, no-store" and nd["link_path"] == f"/api/dealer/go/{nd['ref_code']}", (r.status_code, r.get_json()))
    chyby_vstupu = {
        "bez nazvu": adm.post("/api/admin/dealers", json={"contact_email": "a@b.cz"}),
        "spatny e-mail": adm.post("/api/admin/dealers", json={"name": "X", "contact_email": "neni-email"}),
        "sleva nad 100": adm.post("/api/admin/dealers", json={"name": "X", "default_discount_pct": 101}),
        "provize zaporna": adm.post("/api/admin/dealers", json={"name": "X", "default_commission_pct": -1}),
        "stav": adm.post("/api/admin/dealers", json={"name": "X", "status": "ahoj"}),
        "cesta": adm.post("/api/admin/dealers", json={"name": "X", "order_path": "xxx"}),
        "ucet neexistuje": adm.post("/api/admin/dealers", json={"name": "X", "user_id": 99999999}),
        "adresar neexistuje": adm.post("/api/admin/dealers", json={"name": "X", "party_id": 99999999}),
        "zamestnanecky ucet": adm.post("/api/admin/dealers", json={"name": "X", "user_id": admin_id}),
    }
    over("F3 nesmyslne vstupy -> 400 s ceskou zpravou (bez nazvu, e-mail, sleva/provize mimo 0-100, stav, cesta, neexistujici/zamestnanecky ucet, adresar)",
         all(v.status_code == 400 and v.get_json().get("error") for v in chyby_vstupu.values()), {k: v.status_code for k, v in chyby_vstupu.items()})
    over("F4 nic se nezapsalo pri chybach (pocet dealeru se zvysil jen o jednoho novy)", sql("SELECT COUNT(*) AS n FROM dealers")[0]["n"] == 6, sql("SELECT COUNT(*) AS n FROM dealers")[0]["n"])
    ra = adm.post("/api/admin/dealers", json={"name": "S uctem", "user_id": user_ids[0], "status": "active"})
    rb = adm.post("/api/admin/dealers", json={"name": "Stejny ucet", "user_id": user_ids[0]})
    over("F5 stejny zakaznicky ucet nejde prirazet dvema dealerum (409), prvni projde", ra.status_code == 201 and rb.status_code == 409 and rb.get_json()["code"] == "duplicate", (ra.status_code, rb.status_code))
    did = nd["id"]
    ru = adm.put(f"/api/admin/dealers/{did}", json={"status": "suspended", "order_path": "dealer", "note": "poznamka", "default_discount_pct": None, "ico": " 111 "})
    nu = ru.get_json()["dealer"]
    over("F6 uprava: stav, cesta, poznamka, vymazani slevy (None), orezani textu; ostatni pole beze zmeny", ru.status_code == 200 and nu["status"] == "suspended" and nu["order_path"] == "dealer" and nu["note"] == "poznamka" and nu["default_discount_pct"] is None
         and nu["ico"] == "111" and nu["name"] == "Novy Dealer s.r.o." and nu["default_commission_pct"] == 7.0, nu)
    over("F7 uprava neexistujiciho dealera 404, prazdny nazev 400", adm.put("/api/admin/dealers/99999", json={"name": "x"}).status_code == 404 and adm.put(f"/api/admin/dealers/{did}", json={"name": "  "}).status_code == 400, None)
    rr = adm.put(f"/api/admin/dealers/{did}/rates", json={"rates": [{"category_id": 149, "discount_pct": 22, "commission_pct": None}, {"category_id": 150, "discount_pct": None, "commission_pct": 4}]})
    rates = {x["category_id"]: x for x in rr.get_json()["dealer"]["rates"]}
    over("F8 sazby podle kategorii: ulozeno, NULL = zdedit", rr.status_code == 200 and rates[149]["discount_pct"] == 22.0 and rates[149]["commission_pct"] is None and rates[150]["commission_pct"] == 4.0, rates)
    rr2 = adm.put(f"/api/admin/dealers/{did}/rates", json={"rates": [{"category_id": 149, "discount_pct": 30}]})
    rates2 = {x["category_id"]: x for x in rr2.get_json()["dealer"]["rates"]}
    over("F9 sazby se nemazou: kategorie vypustena ze seznamu dostane NULL/NULL, radek zustane (kategorie 150), 149 se prepise", rates2[149]["discount_pct"] == 30.0 and rates2[150]["discount_pct"] is None and rates2[150]["commission_pct"] is None and len(rates2) == 2, rates2)
    over("F10 spatne sazby: kategorie neexistuje / sleva nad 100 / chybi seznam -> 400, nic se nezmenilo",
         adm.put(f"/api/admin/dealers/{did}/rates", json={"rates": [{"category_id": 99999999, "discount_pct": 5}]}).status_code == 400 and adm.put(f"/api/admin/dealers/{did}/rates", json={"rates": [{"category_id": 149, "discount_pct": 150}]}).status_code == 400
         and adm.put(f"/api/admin/dealers/{did}/rates", json={}).status_code == 400 and adm.get(f"/api/admin/dealers/{did}").get_json()["dealer"]["rates"][0]["discount_pct"] in (30.0, None), None)
    rd = adm.post(f"/api/admin/dealers/{did}/domains", json={"domain": "https://Moje-Prodejna.cz/katalog"})
    domeny = rd.get_json()["dealer"]["domains"]
    over("F11 pridani domeny: normalizovana, bez duplicity pri opakovani, neplatna 400", rd.status_code == 201 and [x["domain"] for x in domeny] == ["moje-prodejna.cz"] and adm.post(f"/api/admin/dealers/{did}/domains", json={"domain": "moje-prodejna.cz"}).status_code == 201
         and len(adm.get(f"/api/admin/dealers/{did}").get_json()["dealer"]["domains"]) == 1 and adm.post(f"/api/admin/dealers/{did}/domains", json={"domain": "ahoj"}).status_code == 400, domeny)
    ro = adm.delete(f"/api/admin/dealers/{did}/domains/{domeny[0]['id']}")
    over("F12 domena se nemaze, jen deaktivuje (is_active=0, radek zustane); cizi/neexistujici id 404", ro.status_code == 200 and ro.get_json()["dealer"]["domains"][0]["is_active"] in (0, False) and sql("SELECT COUNT(*) AS n FROM dealer_domains WHERE dealer_id=%s", (did,))[0]["n"] == 1
         and adm.delete(f"/api/admin/dealers/{did}/domains/999999").status_code == 404, None)
    sql("UPDATE dealers SET status='active' WHERE id=%s", (did,))
    kw = adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "widget", "label": "web"})
    kapi = adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "api", "label": "objednavky", "scopes": ["orders", "quote"], "allowed_ips": "1.2.3.4", "rate_per_min": 30})
    kfeed = adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "feed"})
    over("F13 vytvoreni klicu: widget pk_ (token None), api sk_ + token, feed ft_ + token; scopes/ip/limit se ulozi", kw.status_code == 201 and kw.get_json()["token"] is None and kw.get_json()["key"]["public_id"].startswith("pk_")
         and kapi.get_json()["token"].startswith(kapi.get_json()["key"]["public_id"] + "_") and kapi.get_json()["key"]["scopes"] == "orders,quote" and kapi.get_json()["key"]["allowed_ips"] == "1.2.3.4" and kapi.get_json()["key"]["rate_per_min"] == 30
         and kfeed.get_json()["key"]["public_id"].startswith("ft_") and kfeed.get_json()["key"]["scopes"] == "feed", (kw.status_code, kapi.status_code))
    token_api = kapi.get_json()["token"]
    detail = adm.get(f"/api/admin/dealers/{did}").get_json()["dealer"]
    over("F14 tajemstvi se ukaze jednou: ve vypisu klicu uz neni token ani secret_hash a v DB je jen hash", all("secret_hash" not in k_ and "token" not in k_ for k_ in detail["keys"]) and token_api not in json.dumps(detail)
         and sql("SELECT secret_hash FROM dealer_keys WHERE public_id=%s", (kapi.get_json()["key"]["public_id"],))[0]["secret_hash"] == hashlib.sha256(dealers.parse_secret_token(token_api)[1].encode()).hexdigest(), None)
    over("F15 vytvoreny klic funguje: resolve_secret_key s vydanym tokenem projde, scope feed na api klici ne", dealers.resolve_secret_key(token_api, "1.2.3.4", scope="orders")[0]["id"] == did and chyba(dealers.resolve_secret_key, token_api, "1.2.3.4", scope="feed") == (403, "scope_denied"), None)
    over("F16 neplatny druh/scope/limit -> 400", adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "xyz"}).status_code == 400 and adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "api", "scopes": ["hack"]}).status_code == 400
         and adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "api", "scopes": ["orders"], "rate_per_min": 99999}).status_code == 400 and adm.post("/api/admin/dealers/99999/keys", json={"kind": "widget"}).status_code == 404, None)
    for _ in range(dealers.MAX_ACTIVE_KEYS_PER_KIND):
        adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "widget"})
    over("F17 strop aktivnich klicu na druh (5): dalsi widget klic -> 400 s navodem odvolat jeden", adm.post(f"/api/admin/dealers/{did}/keys", json={"kind": "widget"}).status_code == 400, None)
    kid = kapi.get_json()["key"]["id"]
    rot = adm.post(f"/api/admin/dealers/{did}/keys/{kid}/rotate")
    novy = rot.get_json()
    stary = sql("SELECT expires_at, revoked_at, is_active FROM dealer_keys WHERE id=%s", (kid,))[0]
    delta = (stary["expires_at"] - datetime.datetime.now()).total_seconds() if stary["expires_at"] else None
    over("F18 rotace: novy klic stejneho druhu/rozsahu/limitu, stary plati jeste ~7 dni (prekryv), oba funguji", rot.status_code == 201 and novy["key"]["scopes"] == "orders,quote" and novy["key"]["rate_per_min"] == 30 and novy["token"] and novy["key"]["id"] != kid
         and delta and 6.9 * 86400 < delta < 7.1 * 86400 and dealers.resolve_secret_key(token_api, "1.2.3.4", scope="orders") and dealers.resolve_secret_key(novy["token"], "1.2.3.4", scope="orders"), (rot.status_code, delta))
    rv = adm.post(f"/api/admin/dealers/{did}/keys/{kid}/revoke")
    over("F19 odvolani: klic okamzite nefunguje (401), radek zustane (revoked_at), cizi/neexistujici klic 404", rv.status_code == 200 and chyba(dealers.resolve_secret_key, token_api, "1.2.3.4", scope="orders") == (401, "invalid_key")
         and sql("SELECT revoked_at FROM dealer_keys WHERE id=%s", (kid,))[0]["revoked_at"] is not None and adm.post(f"/api/admin/dealers/{did}/keys/99999/revoke").status_code == 404 and adm.post(f"/api/admin/dealers/{B2['id']}/keys/{kid}/revoke").status_code == 404, None)
    rl_ = adm.get("/api/admin/dealers").get_json()["dealers"]
    over("F20 seznam: neaktivni (is_active=0) dealeri se skryji, ?all=1 je ukaze, hledani podle nazvu/ICO/kodu, filtr stavu, pocty (klice, kliky, objednavky)",
         all(d_["id"] != E5["id"] for d_ in rl_) and any(d_["id"] == E5["id"] for d_ in adm.get("/api/admin/dealers?all=1").get_json()["dealers"]) and [d_["name"] for d_ in adm.get("/api/admin/dealers?q=Alfa").get_json()["dealers"]] == ["Alfa s.r.o."]
         and all(d_["status"] == "suspended" for d_ in adm.get("/api/admin/dealers?status=suspended").get_json()["dealers"]) and next(d_ for d_ in rl_ if d_["id"] == A["id"])["orders_total"] == 1
         and next(d_ for d_ in rl_ if d_["id"] == A["id"])["clicks_30d"] >= 2, [(d_["name"], d_.get("orders_total"), d_.get("clicks_30d")) for d_ in rl_])

    # partnersky panel
    muj_user = user_ids[0]
    pan = jako(muj_user)
    me = pan.get("/api/dealer/me")
    over("F21 panel: /api/dealer/me vrati dealera tohoto uctu (jeho sazby, domeny, klice bez tajemstvi), bez interni poznamky", me.status_code == 200 and me.get_json()["dealer"]["name"] == "S uctem" and "note" not in me.get_json()["dealer"], (me.status_code, me.get_json()))
    over("F22 panel: ucet bez dealera 404 not_a_dealer, nepřihlášený 401", jako(user_ids[1]).get("/api/dealer/me").status_code == 404 and jako(None).get("/api/dealer/me").status_code == 401, None)
    kp = pan.post("/api/dealer/keys", json={"kind": "widget", "label": "moje"})
    over("F23 panel: dealer si vystavi widget klic; api klic ne u dealera s cestou 'our' (403); feed ano", kp.status_code == 201 and pan.post("/api/dealer/keys", json={"kind": "api", "scopes": ["orders"]}).status_code == 403
         and pan.post("/api/dealer/keys", json={"kind": "feed"}).status_code == 201, (kp.status_code,))
    sql("UPDATE dealers SET order_path='dealer' WHERE user_id=%s", (muj_user,))
    ka = pan.post("/api/dealer/keys", json={"kind": "api"})
    over("F24 panel: u dealera s cestou 'dealer' vznikne api klic (vychozi rozsah orders,quote), token se ukaze jednou", ka.status_code == 201 and ka.get_json()["key"]["scopes"] == "orders,quote" and ka.get_json()["token"], ka.get_json())
    pd_ = pan.post("/api/dealer/domains", json={"domain": "Moje-Domena.cz"})
    over("F25 panel: dealer si prida svou domenu (normalizovana), nesmyslnou odmitne, deaktivuje jen svou", pd_.status_code == 201 and pd_.get_json()["domain"] == "moje-domena.cz" and pan.post("/api/dealer/domains", json={"domain": "xx"}).status_code == 400, pd_.get_json())
    me2 = pan.get("/api/dealer/me").get_json()["dealer"]
    dom_id = next(x["id"] for x in me2["domains"] if x["domain"] == "moje-domena.cz")
    cizi_dom = sql("SELECT id FROM dealer_domains WHERE dealer_id=%s LIMIT 1", (B2["id"],))[0]["id"]
    over("F26 panel: cizi domenu a cizi klic dealer nema pristup (404), svuj klic odvola", pan.delete(f"/api/dealer/domains/{cizi_dom}").status_code == 404 and pan.delete(f"/api/dealer/domains/{dom_id}").status_code == 200
         and pan.post("/api/dealer/keys/%d/revoke" % sql("SELECT id FROM dealer_keys WHERE dealer_id=%s LIMIT 1", (B2["id"],))[0]["id"]).status_code == 404 and pan.post(f"/api/dealer/keys/{kp.get_json()['key']['id']}/revoke").status_code == 200, None)
    sql("UPDATE dealers SET status='pending' WHERE user_id=%s", (muj_user,))
    over("F27 panel: dealer, ktery neni aktivni (pending), si klic ani domenu nevystavi (403), ale vidi svuj profil", pan.post("/api/dealer/keys", json={"kind": "widget"}).status_code == 403 and pan.post("/api/dealer/domains", json={"domain": "dalsi.cz"}).status_code == 403 and pan.get("/api/dealer/me").status_code == 200, None)
    over("F28 vsechny odpovedi /api/dealer/* a /api/admin/dealers* maji Cache-Control: private, no-store", all(x.headers.get("Cache-Control") == "private, no-store" for x in (me, pan.get("/api/dealer/me"), adm.get("/api/admin/dealers"))), None)

    # ============================================================================================================ G) staticke kontrakty a mutace
    print("== G staticke kontrakty a mutace")
    app_src = open(APP_PY, encoding="utf-8").read()
    ord_src = open(ORDERS_PY, encoding="utf-8").read()
    over("G1 app.py: sekce dealeri, dealer_provize, dealer_klice jsou v PERMISSION_SECTIONS DRIV nez se importuje dealers (require_permission je kontroluje pri importu)",
         all(re.search(r'"' + s + r'"', app_src[:app_src.index("import dealers")] if "import dealers" in app_src else "") for s in ("dealeri", "dealer_provize", "dealer_klice")), "kandidat app.py chybi nebo jeste neni nasazeny" if "import dealers" not in app_src else None)
    def pozice_importu(m):
        r_ = re.search(rf"^import {m}\b", app_src, re.M)
        return r_.start() if r_ else -1
    over("G2 app.py: import dealers je az za importy documents, products, orders, cart a product_assemblies", pozice_importu("dealers") > 0 and all(0 < pozice_importu(m) < pozice_importu("dealers") for m in ("documents", "products", "orders", "cart", "product_assemblies")),
         {m: pozice_importu(m) for m in ("dealers", "documents", "products", "orders", "cart", "product_assemblies")})
    tree = ast.parse(ord_src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "orders_create")
    zdroj_fn = ast.get_source_segment(ord_src, fn)
    i_ins = zdroj_fn.find("INSERT INTO shop_order_status_history")
    i_att = zdroj_fn.find("dealers.attach_attribution(cur, result[\"order_id\"], user)")
    i_com = zdroj_fn.find("conn.commit()")
    i_ema = zdroj_fn.find("_send_order_emails_bg(result)")
    over("G3 orders_create: atribuce dealera se vola PO vlozeni objednavky a historie stavu, PRED commitem a PRED e-maily, v try/except (nikdy nerozbije objednavku)",
         0 < i_ins < i_att < i_com < i_ema and re.search(r"try:\s*\n\s*import dealers\s*\n\s*dealers\.attach_attribution[^\n]*\n\s*except Exception:", zdroj_fn) is not None, (i_ins, i_att, i_com, i_ema) if "attach_attribution" in zdroj_fn else "volani v orders_create jeste neni")
    over("G4 migrace: 5 tabulek + ALTER shop_orders (4 sloupce), vsechny cizi klice RESTRICT (nic se nemaze), zadne DROP/DELETE/TRUNCATE", len([s for s in PRIKAZY if s.startswith("CREATE TABLE IF NOT EXISTS")]) == 5 and "ADD COLUMN dealer_id" in SQL and "ON DELETE CASCADE" not in SQL and "ON DELETE SET NULL" not in SQL
         and not re.search(r"\bDROP\b|\bTRUNCATE\b|(?<!ON )\bDELETE\s+FROM\b", TELO, re.I), None)
    modul = open(dealers.__file__, encoding="utf-8").read()
    over("G5 dealers.py: zadne DELETE FROM ani DROP (nic se nemaze, jen is_active/revoked_at) a neposila zadne e-maily", not re.search(r"DELETE\s+FROM|DROP\s+TABLE|TRUNCATE", modul, re.I) and "send_email" not in modul and "smtp" not in modul.lower(), None)
    over("G6 dealers.py: /api/dealer/* a /api/admin/dealers* nevraci CORS hlavicky (server-to-server) a nikde se nenastavuje Access-Control", "Access-Control" not in modul, None)

    def mutant(funkce, stare, nove, globals_extra=None):
        """Funkce z dealers.py s jednou zamenou v kodu - musi se zamenit PRAVE JEDNOU."""
        t = ast.parse(modul)
        node = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        src = ast.get_source_segment(modul, node)
        assert src.count(stare) == 1, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x"
        ns = dict(vars(dealers))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    m1 = mutant("domain_matches", "host.endswith(domain[1:])", "host.endswith(domain[2:])")
    over("G7 mutace: wildcard *.x.cz, ktery pusti i podobny retezec evilx.cz -> test A10 ji zachyti", m1("evilpartner.cz", "*.partner.cz") is True and not dealers.domain_matches("evilpartner.cz", "*.partner.cz"), None)
    m2 = mutant("sanitize_landing", ' or "\\\\" in s', "")
    over("G8 mutace: povoleny zpetne lomitko v cili presmerovani (/\\evil.com = open redirect v prohlizeci) -> test A11 ji zachyti", m2("/\\evil.com") != "/" and dealers.sanitize_landing("/\\evil.com") == "/", m2("/\\evil.com"))
    with real.cursor() as c:
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI - datetime.timedelta(days=90), token1))
        m3 = mutant("attribution_for_new_order", '(_now() - click["created_at"]) > datetime.timedelta(days=attribution_days(cur))', "False")
        over("G9 mutace: bez kontroly stari prokliku by se pripsala i 90 dni stara objednavka -> test C9 ji zachyti", m3(c, token1, None, "a@b.cz") is not None and AFN(c, token1, None, "a@b.cz") is None, None)
        sql("UPDATE dealer_clicks SET created_at=%s WHERE token=%s", (NYNI, token1))
        m4 = mutant("attribution_for_new_order", "if is_test or not click_token", "if not click_token")
        over("G10 mutace: testovaci objednavky se pripisuji dealerovi -> test C8 ji zachyti", m4(c, token1, None, "a@b.cz", is_test=True) is not None and AFN(c, token1, None, "a@b.cz", is_test=True) is None, None)
    m5 = mutant("resolve_secret_key", "hmac.compare_digest(hash_secret(secret), expected)", "True")
    over("G11 mutace: tajny klic bez overeni tajne casti (staci znat public_id) -> test B12 ji zachyti", chyba(m5, spatna_tajna, "7.7.7.7", scope="orders") is None and chyba(RSK, spatna_tajna, "7.7.7.7", scope="orders") == (401, "invalid_key"), None)
    m6 = mutant("resolve_public_key", "origin_host(origin)", "'shop.example.cz'")
    over("G12 mutace: Origin se neoveruje -> test B3 ji zachyti", chyba(m6, PK["ok"], "https://evil.cz", "1.1.1.1") is None and chyba(RPK, PK["ok"], "https://evil.cz", "1.1.1.1") == (403, "origin_not_allowed"), None)
    m7 = mutant("dealer_product_view", "if _is_assembly_product(cur, p):", "if False:")
    with real.cursor() as c:
        vzorek = (asm or typ)[0]["id"]          # karta sestavy bez znacky v textu (Vandr VD-* ma znacku uz ve slugu, vyradil by je i filtr znacky)
        over("G13 mutace: sestavy (product_assemblies / automaticky zalozena karta) by se nabizely dealerum -> test E8 ji zachyti", m7(c, vzorek, "retail") is not None and dealers.dealer_product_view(c, vzorek, "retail") is None, None)
finally:
    with real.cursor() as cur:
        for t in ("dealer_clicks", "dealer_keys", "dealer_domains", "dealer_rates", "dealers", "shop_orders", "app_settings", "_tpl_shop_orders", "_tpl_app_settings"):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("Z ostre tabulky a schema jsou po testu beze zmeny (pocet objednavek, sloupce shop_orders, tabulky dealer*, audit_log)", po == pred, (pred, po))

ok = sum(vysl)
print(f"\nVYSLEDEK dealersky program krok 1: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
