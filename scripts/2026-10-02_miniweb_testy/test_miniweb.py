#!/opt/konfigurator/api/venv/bin/python
"""Mini-shop (Packstations), FAZE 1: cteci API /api/miniweb/* (bot5, 2026-10-02; navrh schvalil bot3, tvary odpovedi z webapp/miniweb/demo-api.js od bot16).

SKUTECNY kod (nebo kandidat MINIWEB_PY) pres Flask test client nad DOCASNYMI tabulkami: car_storefronts, storefront_hosts, miniweb_shops, miniweb_categories, miniweb_category_texts, miniweb_products,
miniweb_product_texts. Ostre tabulky se jen ctou (app_users pro session staffu a zakaznika), nic se nezapisuje. Host se posila pres base_url, session pres hlavicku Cookie.

Cast A  rozpoznani shopu: host, alias, neznamy host, storefront bez mini-shopu, koncept (jen staff, server), ?shop= a ?lang= jen pro staff, jazyk podle storefrontu a zakladni jazyk (en-ie -> en)
Cast B  /config: tvar, hodnoty, kontakt a alternates bez znacky, price_mode, preview
Cast C  /categories a /products: viditelnost (aktivni, schvaleny text v jazyce, retezec rodicu), pocty vcetne podkategorii, filtr kategorie, strankovani, tvar produktu 1:1 s demem
Cast D  /products/<id>, ceny se nevydavaji, text jen cisty, parametry, interni udaje neodchazeji
Cast E  BEZ ZNACKY (fail closed, vsechny endpointy) a vyjimka legal.seller; /legal
Cast F  hlavicky, limit pozadavku, jen GET, nic se nezapisuje; mutace
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_miniweb_testy/test_miniweb.py      (kandidat: --setenv=MINIWEB_PY=/cesta/miniweb.py)
"""
import ast
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
MINIWEB_PY = os.environ.get("MINIWEB_PY") or (os.path.join(API, "miniweb.py") if os.path.exists(os.path.join(API, "miniweb.py")) else os.path.join(HERE, "nasazeni", "miniweb.py"))
tmp = tempfile.mkdtemp(prefix="kand_miniweb_")
shutil.copy(MINIWEB_PY, os.path.join(tmp, "miniweb.py"))
sys.path.insert(0, API)
sys.path.insert(0, tmp)                    # kandidat PRED importem app: app.py importuje miniweb (nasazeno), jinak by kandidat vyhrala nasazena kopie z cache modulu

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

import miniweb as mw  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents", "app_users", "crm_leads", "audit_log"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_documents")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


BRAND = re.compile(r"logiman|konfigur[aá]tor|vandrawee|vandr|dogus", re.I)

try:
    with real.cursor() as cur:
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    def sf(slug, host, status="live", lang="en", name=None):
        sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES (%s,%s,%s,%s,%s)", (name or slug, slug, host, status, lang))
        return jedno("SELECT * FROM car_storefronts WHERE slug=%s", (slug,))

    def shop(storefront, family="packstations", price_mode="hidden", currency="EUR", locale=None, accent=None, countries=None, contact=None):
        sql("INSERT INTO miniweb_shops (storefront_id, family, price_mode, currency, locale, accent, countries, contact_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (storefront["id"], family, price_mode, currency, locale, accent, countries, json.dumps(contact) if contact is not None else None))

    S_EN = sf("packstations-en", "packstations.example.top")
    S_DE = sf("packstationen-de", "packstationen.example.top", lang="de")
    S_DRAFT = sf("packstations-draft", "draft.packstations.example.top", status="draft")
    S_IE = sf("packstations-ie", "ie.packstations.example.top", lang="en-ie")
    S_CARS = sf("cars", "cars.example.top")
    S_FR = sf("logiman-fr", "logiman-packstations.example.top", lang="fr")           # domena se znackou
    S_DRAFT_ALT = sf("packstations-es", "es.packstations.example.top", status="draft", lang="es")
    S_WORK = sf("worktables-pl", "worktables.example.top", lang="pl")           # jina RODINA shopu (worktables), jazyk pl: nesmi se objevit v alternates packstations
    ALIAS = "shop.alias-packstations.com"
    sql("INSERT INTO storefront_hosts (storefront_id, host) VALUES (%s,%s)", (S_EN["id"], ALIAS))
    shop(S_EN, locale="en-IE", accent="#2dd4bf", countries="CZ,SK,de,AT,PL,xx1,POL", contact={"email": "hello@packstations.example", "phone": "+353 1 555 0100", "hours": "Mon-Fri 9:00-17:00"})
    shop(S_DE, locale="de-DE", contact={"email": "info@example.cz", "phone": "+49 30 555 0100", "hours": "Mo-Fr 9-17 (Logiman office)"})
    shop(S_DRAFT, contact={"email": "draft@packstations.example"})
    shop(S_IE, price_mode="indicative", accent="nesmysl")
    shop(S_FR, currency="eur", locale="bad locale!")
    shop(S_WORK, family="worktables")
    shop(S_DRAFT_ALT)

    def kat(slug, parent=None, sort=0, active=1, family="packstations"):
        sql("INSERT INTO miniweb_categories (parent_id, family, slug, sort_order, is_active) VALUES (%s,%s,%s,%s,%s)", (parent, family, slug, sort, active))
        return jedno("SELECT id FROM miniweb_categories WHERE family=%s AND slug=%s", (family, slug))["id"]

    def kat_text(cid, lang, name, status="approved"):
        sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,%s,%s,%s)", (cid, lang, name, status))

    C1 = kat("tables", sort=1)
    C2 = kat("packing-stations", C1, sort=1)
    C3 = kat("inactive-cat", sort=3, active=0)
    C4 = kat("draft-text-cat", sort=4)
    C5 = kat("brand-cat", sort=5)
    C6 = kat("child-of-hidden", C5, sort=1)
    C7 = kat("storage", sort=2)
    kat_text(C1, "en", "Tables")
    kat_text(C1, "de", "Tische")
    kat_text(C2, "en", "Packing stations")
    kat_text(C2, "de", "Packstationen")
    kat_text(C3, "en", "Inactive")
    kat_text(C4, "en", "Draft category", status="draft")
    kat_text(C5, "en", "Logiman tables")
    kat_text(C6, "en", "Nested")
    kat_text(C7, "En", "Storage")                                    # jazyk zapsany s jinou velikosti pismen nesmi produkt skryt

    def prod(slug, sku, cat, sort=0, active=1, shop_product_id=None, configurator=0):
        sql("INSERT INTO miniweb_products (category_id, slug, public_sku, shop_product_id, configurator_available, sort_order, is_active) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (cat, slug, sku, shop_product_id, configurator, sort, active))
        return jedno("SELECT id FROM miniweb_products WHERE slug=%s", (slug,))["id"]

    def prod_text(pid, lang, name, summary="Summary", description="Description", delivery="3-4 weeks", specs=None, status="approved"):
        sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, summary, description, delivery, specs_json, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (pid, lang, name, summary, description, delivery, specs if isinstance(specs, str) or specs is None else json.dumps(specs), status))

    SPECS = [{"name": "Dimensions", "value": "1316 × 1925 × 1285 mm"}, {"name": "Load", "value": "150 kg"}]
    P1 = prod("packing-station-ps120", "PS-120", C2, sort=1, shop_product_id=777, configurator=1)
    prod_text(P1, "en", "Packing station PS-120", "Height-adjustable packing table", "<p>Robust <b>aluminium</b> frame.</p>\n<p>Second paragraph &amp; more.</p>", specs=SPECS)
    prod_text(P1, "de", "Packstation PS-120", "Höhenverstellbarer Packtisch", "Stabiler Rahmen.", delivery="3-4 Wochen", specs=[{"name": "Abmessungen", "value": "1316 × 1925 × 1285 mm"}])
    P2 = prod("packing-station-ps90", "PS-90", C2, sort=2)
    prod_text(P2, "en", "Packing station PS-90", status="draft")
    P3 = prod("inactive-product", "IN-1", C2, active=0)
    prod_text(P3, "en", "Inactive product")
    P4 = prod("brand-in-description", "BR-1", C2)
    prod_text(P4, "en", "Brand description", description="Made by Logiman in Prague.")
    P5 = prod("in-inactive-category", "IC-1", C3)
    prod_text(P5, "en", "In inactive category")
    P6 = prod("only-german", "DE-1", C2, sort=6)
    prod_text(P6, "de", "Nur Deutsch")
    P7 = prod("brand-in-specs", "SP-1", C2)
    prod_text(P7, "en", "Brand in specs", specs=[{"name": "Profile", "value": "Dogus 40x40"}])
    P8 = prod("work-table-wt100", "WT-100", C1, sort=2)
    prod_text(P8, "en", "Work table WT-100", "Sturdy work table", "Plain description.",
              specs=[1, "x", {"name": "", "value": "v"}, {"name": "Weight", "value": "20 kg"}, {"name": "<b>Color</b>", "value": "grey &amp; black"}, {"name": "NoValue", "value": ""}, {"value": "no name"}])
    P9 = prod("in-child-of-hidden", "CH-1", C6)
    prod_text(P9, "en", "Child of hidden category")
    P10 = prod("storage-rack-st1", "ST-1", C7, sort=1)
    prod_text(P10, "EN", "Storage rack ST-1")                          # totez u produktu
    P11 = prod("logiman-table", "LT-1", C1)
    prod_text(P11, "en", "Slug with brand")
    P12 = prod("table-bad-specs", "BS-1", C1, sort=3)
    prod_text(P12, "en", "Table with broken specs", specs='{"neni": "seznam"}')            # validni JSON, ale ne seznam (sloupec JSON nevalidni text odmitne)
    P13 = prod("table-konfigurator-cz", "KZ-1", C1)
    prod_text(P13, "en", "Czech word konfigurátor in name")
    P14 = prod("sanitize-me", "SN-1", C2, sort=9)                          # jen nemecky, aby nemenil pocty v anglickem shopu
    prod_text(P14, "de", "<b>Sanitize</b> me", "Load > 150 kg and width < 20 mm", "&lt;script&gt;alert(1)&lt;/script&gt;Safe text<script>evil()</script> and <style>p{x:y}</style>more<!-- hidden --> end<br>line two<img src=x onerror=alert(1)>",
              delivery="  2   weeks\x00\x07  ", specs=[{"name": "<i>Weight</i>", "value": "12 &lt; 15 kg"}])

    W1 = kat("tables", family="worktables", sort=1)                                # stejny slug jako v packstations: unikatnost je v ramci rodiny
    W2 = kat("heavy-duty", parent=W1, family="worktables", sort=1)
    kat_text(W1, "pl", "Stoly robocze")
    kat_text(W2, "pl", "Stoly ciezkie")
    kat_text(W1, "en", "Work tables")
    kat_text(W2, "en", "Heavy duty")
    PW = prod("heavy-table-h1", "WT-9", W2, sort=1)
    prod_text(PW, "pl", "Stol ciezki H1")
    prod_text(PW, "en", "Heavy table H1")
    uzivatele = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 1")]
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]
    _si = SecureCookieSessionInterface()
    cl = appmod.app.test_client(use_cookies=False)

    def cookie(uid):
        return {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})} if uid else {}

    def get(host, cesta, uid=None, **params):
        appmod._rate_limit_buckets.clear()
        return cl.get(cesta, base_url=f"http://{host}", query_string=params or None, headers=cookie(uid))

    H = "packstations.example.top"
    ALL_TEXT = []                                       # vsechny odpovedi anonymniho verejneho shopu pro skenovani znacky

    def veřejně(cesta, host=H, **params):
        r = get(host, cesta, **params)
        ALL_TEXT.append((cesta, r.get_data(as_text=True)))
        return r

    # ============================================================================================================ A) rozpoznani shopu
    print("== A rozpoznani shopu a brana")
    r = veřejně("/api/miniweb/config")
    over("A1 shop podle hosta: 200, shop packstations-en, jazyk en, preview false", r.status_code == 200 and r.get_json()["shop"] == "packstations-en" and r.get_json()["lang"] == "en" and r.get_json()["preview"] is False, r.get_json())
    ra = veřejně("/api/miniweb/config", host=ALIAS)
    over("A2 ALIAS hostu da stejny shop (jeden storefront vic hostu) a stejna data", ra.status_code == 200 and ra.get_json() == r.get_json(), ra.status_code)
    over("A3 host s www, velkymi pismeny a portem se rozpozna", get("WWW.Packstations.Example.TOP:8443", "/api/miniweb/config").status_code == 200, None)
    over("A4 neznamy host -> 404 shop_not_found (JSON, ne HTML); storefront bez radku v miniweb_shops (auta) -> 404",
         get("neznamy.example.top", "/api/miniweb/config").status_code == 404 and get("neznamy.example.top", "/api/miniweb/config").get_json() == {"error": "shop_not_found"}
         and get("cars.example.top", "/api/miniweb/categories").status_code == 404, None)
    DH = "draft.packstations.example.top"
    over("A5 KONCEPT (status draft): anonym 404, prihlaseny zakaznik 404 (server brana, ne jen JS), staff 200 s preview true",
         get(DH, "/api/miniweb/config").status_code == 404 and get(DH, "/api/miniweb/config", uid=uzivatele[0]).status_code == 404 and get(DH, "/api/miniweb/config", uid=admin_id).status_code == 200
         and get(DH, "/api/miniweb/config", uid=admin_id).get_json()["preview"] is True, None)
    over("A6 ?shop=<slug> na cizim hostu: jen staff (anonym a zakaznik 404), staff dostane shop; neznamy slug 404; ?shop= na hostu, ktery shop uz urcuje, se ignoruje",
         get("spolecna.example.org", "/api/miniweb/config", shop="packstations-en").status_code == 404 and get("spolecna.example.org", "/api/miniweb/config", uid=uzivatele[0], shop="packstations-en").status_code == 404
         and get("spolecna.example.org", "/api/miniweb/config", uid=admin_id, shop="packstations-en").get_json()["shop"] == "packstations-en"
         and get("spolecna.example.org", "/api/miniweb/config", uid=admin_id, shop="nic").status_code == 404 and get("spolecna.example.org", "/api/miniweb/config", uid=admin_id, shop="cars").status_code == 404
         and get(H, "/api/miniweb/config", uid=admin_id, shop="packstations-draft").get_json()["shop"] == "packstations-en", None)
    over("A7 jazyk urcuje DOMENA: nemecky shop servi nemecke texty; ?lang= funguje jen pro staff (anonym dostane jazyk domeny)",
         get("packstationen.example.top", "/api/miniweb/products").get_json()["products"][0]["name"] == "Packstation PS-120" and get(H, "/api/miniweb/products", lang="de").get_json()["products"][0]["name"] == "Packing station PS-120"
         and get(H, "/api/miniweb/products", uid=admin_id, lang="de").get_json()["products"][0]["name"] == "Packstation PS-120", None)
    over("A8 regionalni jazyk shopu (en-ie) spadne na zakladni texty (en), config nese lang en-ie", get("ie.packstations.example.top", "/api/miniweb/config").get_json()["lang"] == "en-ie"
         and get("ie.packstations.example.top", "/api/miniweb/products").get_json()["products"][0]["name"] == "Packing station PS-120", None)

    # ============================================================================================================ B) config
    print("== B config")
    cfg = r.get_json()
    over("B1 config ma presne ocekavane klice a hodnoty (mena, barva, zeme jen platne kody, neutralni kontakt, hidden, jen poptavka)",
         set(cfg) - {"checkout_mode"} == {"shop", "lang", "locale", "currency", "accent", "countries", "contact", "price_mode", "inquiry_only", "inquiry_enabled", "alternates", "preview"} and cfg.get("checkout_mode", "inquiry") == "inquiry" and cfg["currency"] == "EUR" and cfg["locale"] == "en-IE"
         and cfg["accent"] == "#2dd4bf" and cfg["countries"] == ["CZ", "SK", "DE", "AT", "PL"] and cfg["price_mode"] == "hidden" and cfg["inquiry_only"] is True and cfg["inquiry_enabled"] is True
         and cfg["contact"] == {"phone": "+353 1 555 0100", "hours": "Mon-Fri 9:00-17:00"}, cfg)
    over("B2 alternates: jen ZIVE jazykove verze stejne rodiny (nemecka), ne koncept, ne vlastni jazyk, ne domena se znackou; staff vidi i koncepty",
         cfg["alternates"] == [{"lang": "de", "href": "https://packstationen.example.top/"}, {"lang": "en-ie", "href": "https://ie.packstations.example.top/"}]
         and any(a["lang"] == "es" for a in get(H, "/api/miniweb/config", uid=admin_id).get_json()["alternates"]) and not any(a["lang"] == "fr" for a in get(H, "/api/miniweb/config", uid=admin_id).get_json()["alternates"]), cfg["alternates"])
    cde = get("packstationen.example.top", "/api/miniweb/config").get_json()
    over("B3 kontakt: e-mail z contact_json se NIKDY nevydava (pravidlo: zadny zivy e-mail na webu), pole se znackou se nevyda (prazdny retezec), ostatni pole zustanou; neplatna barva -> null; locale chybi -> jazyk", cde["contact"] == {"phone": "+49 30 555 0100", "hours": ""}
         and get("ie.packstations.example.top", "/api/miniweb/config").get_json()["accent"] is None and get("ie.packstations.example.top", "/api/miniweb/config").get_json()["locale"] == "en-ie", cde["contact"])

    # ============================================================================================================ C) kategorie a produkty
    print("== C kategorie a produkty")
    cats = veřejně("/api/miniweb/categories").get_json()["categories"]
    over("C1 kategorie ve tvaru {id, parent_id, slug, name, count}, jen viditelne: aktivni, s schvalenym textem v jazyce, bez znacky a s viditelnym retezcem rodicu (neaktivni, koncept, znacka, potomek skryte)",
         all(set(c) - {"slug_alt"} == {"id", "parent_id", "slug", "name", "count"} for c in cats) and [(c["slug"], c["name"], c["parent_id"]) for c in cats] == [("tables", "Tables", None), ("packing-stations", "Packing stations", C1), ("storage", "Storage", None)], cats)
    over("C2 count = viditelne produkty vcetne podkategorii (stoly: PS-120 v podkategorii + WT-100 + tabulka se spatnymi parametry = 3, packing stations 1, storage 1)", {c["slug"]: c["count"] for c in cats} == {"tables": 3, "packing-stations": 1, "storage": 1}, cats)
    prods = veřejně("/api/miniweb/products").get_json()
    over("C3 produkty: jen viditelne a serazene podle sort_order a id (PS-120, storage, WT-100, tabulka se spatnymi parametry), total sedi; skryte: koncept textu, neaktivni, neaktivni kategorie, jen nemecky, znacka v popisu/parametrech/slugu/nazvu, potomek skryte kategorie",
         [p["sku"] for p in prods["products"]] == ["PS-120", "ST-1", "WT-100", "BS-1"] and prods["total"] == 4, [p["sku"] for p in prods["products"]])
    p1 = prods["products"][0]
    over("C4 tvar produktu 1:1 s demem (id, slug, sku, category_id, name, summary, description, price_from, currency, delivery, configurator{available, default_view, product_id}, specs[{name,value}])",
         set(p1) - {"groove_family", "cross_section_label", "profil_mm", "slug_alt"} == {"id", "slug", "sku", "category_id", "name", "summary", "description", "price_from", "currency", "delivery", "configurator", "specs"} and set(p1["configurator"]) == {"available", "default_view", "product_id"}
         and p1["configurator"] == {"available": True, "default_view": "configurator", "product_id": 777} and p1["specs"] == SPECS and p1["category_id"] == C2 and p1["currency"] == "EUR", p1)
    over("C5 popis je cisty text (HTML pryc, entity rozbalene, odstavce zustanou), vsechny texty bez znacek <>", p1["description"] == "Robust aluminium frame.\n\nSecond paragraph & more." and not any("<" in str(v) for v in (p1["name"], p1["summary"], p1["description"])), p1["description"])
    wt = [p for p in prods["products"] if p["sku"] == "WT-100"][0]
    over("C6 produkt bez konfiguratoru: available false a product_id null (interni id karty neodchazi); parametry, ktere nejsou seznam, daji prazdny seznam (produkt zustane)",
         wt["configurator"] == {"available": False, "default_view": "configurator", "product_id": None} and [p for p in prods["products"] if p["sku"] == "BS-1"][0]["specs"] == [], None)
    over("C6b parametry se cisti: nesmysly (cislo, retezec, prazdny nazev nebo hodnota, chybejici nazev) vypadnou, HTML a entity se zpracuji", wt["specs"] == [{"name": "Weight", "value": "20 kg"}, {"name": "Color", "value": "grey & black"}], wt["specs"])
    f_ = veřejně("/api/miniweb/products", category="tables").get_json()
    f2 = veřejně("/api/miniweb/products", category="packing-stations").get_json()
    f3 = veřejně("/api/miniweb/products", category="storage").get_json()
    f4 = veřejně("/api/miniweb/products", category="neexistuje").get_json()
    f5 = veřejně("/api/miniweb/products", category="brand-cat").get_json()
    f6 = veřejně("/api/miniweb/products", category="'; DROP TABLE x;--").get_json()
    over("C7 filtr kategorie: nadrazena zahrne podkategorie (3), podkategorie jen svoje (1), jina (1), neexistujici, skryta kategorie a nesmysl = prazdny seznam s total 0 (bez chyby)",
         (f_["total"], f2["total"], f3["total"], f4["total"], f5["total"], f6["total"]) == (3, 1, 1, 0, 0, 0) and [p["sku"] for p in f_["products"]] == ["PS-120", "WT-100", "BS-1"], (f_["total"], f2["total"], f3["total"]))
    pg = veřejně("/api/miniweb/products", limit=2, offset=1).get_json()
    over("C8 strankovani: limit a offset, total zustava celkovy; limit se omezuje (0 -> 1, 9999 -> 200), nesmysl 400",
         [p["sku"] for p in pg["products"]] == ["ST-1", "WT-100"] and pg["total"] == 4 and len(veřejně("/api/miniweb/products", limit=0).get_json()["products"]) == 1 and veřejně("/api/miniweb/products", limit=9999).status_code == 200
         and veřejně("/api/miniweb/products", limit="abc").status_code == 400 and veřejně("/api/miniweb/products", offset=-5).get_json()["total"] == 4, pg)
    de_prods = get("packstationen.example.top", "/api/miniweb/products").get_json()
    over("C9 nemecky shop: vidi jen produkty s nemeckym textem (PS-120, Nur Deutsch a testovaci SN-1), kategorie Tische a Packstationen (storage nema nemecky text, neni videt)",
         [p["sku"] for p in de_prods["products"]] == ["PS-120", "DE-1", "SN-1"] and [(c["slug"], c["name"]) for c in get("packstationen.example.top", "/api/miniweb/categories").get_json()["categories"]] == [("tables", "Tische"), ("packing-stations", "Packstationen")], [p["sku"] for p in de_prods["products"]])
    st = get(DH, "/api/miniweb/products", uid=admin_id).get_json()["products"]
    st_cats = get(DH, "/api/miniweb/categories", uid=admin_id).get_json()["categories"]
    over("C10 staff v NAHLEDU konceptu vidi i texty ve stavu draft (PS-90, kategorie koncept) s text_status 'draft', schvalene bez priznaku; anonym na zivem shopu draft nevidi",
         [p["sku"] for p in st] == ["PS-120", "ST-1", "PS-90", "WT-100", "BS-1"] and [p.get("text_status") for p in st] == [None, None, "draft", None, None] and "draft-text-cat" in [c["slug"] for c in st_cats]
         and "PS-90" not in [p["sku"] for p in prods["products"]] and "draft-text-cat" not in [c["slug"] for c in cats], [p["sku"] for p in st])
    ss = get(H, "/api/miniweb/products", uid=admin_id).get_json()["products"]
    ss_d = get(H, "/api/miniweb/products", uid=admin_id, drafts="1").get_json()["products"]
    over("C11 staff na ZIVEM shopu vidi stejne co verejnost (jen schvalene), draft texty az s ?drafts=1", [p["sku"] for p in ss] == ["PS-120", "ST-1", "WT-100", "BS-1"] and "PS-90" in [p["sku"] for p in ss_d], [p["sku"] for p in ss])

    # rodiny shopu: katalog patri rodine
    WH = "worktables.example.top"
    w_cats = veřejně("/api/miniweb/categories", host=WH).get_json()["categories"]
    w_prods = veřejně("/api/miniweb/products", host=WH).get_json()
    p_cats_after = veřejně("/api/miniweb/categories").get_json()["categories"]
    over("C12 katalog patri RODINE: shop jine rodiny (worktables) vidi jen svoje kategorie a produkty (stejny slug 'tables' existuje v obou rodinach nezavisle), shop packstations vidi stale sve (beze zmeny)",
         [(c["slug"], c["name"], c["count"]) for c in w_cats] == [("tables", "Stoly robocze", 1), ("heavy-duty", "Stoly ciezkie", 1)] and [p["sku"] for p in w_prods["products"]] == ["WT-9"] and w_prods["total"] == 1
         and [c["slug"] for c in p_cats_after] == [c["slug"] for c in cats] and "WT-9" not in [p["sku"] for p in prods["products"]], (w_cats, w_prods, p_cats_after))
    over("C13 produkt jine rodiny je v shopu packstations 404 (detail i filtr kategorie), v sve rodine 200; polsky shop jine rodiny se neobjevi v alternates packstations",
         veřejně(f"/api/miniweb/products/{PW}").status_code == 404 and veřejně(f"/api/miniweb/products/{PW}", host=WH).status_code == 200
         and veřejně("/api/miniweb/products", category="heavy-duty").get_json()["total"] == 0 and veřejně("/api/miniweb/products", host=WH, category="tables").get_json()["total"] == 1
         and all(a["lang"] != "pl" for a in veřejně("/api/miniweb/config").get_json()["alternates"]), None)
    try:
        sql("INSERT INTO miniweb_categories (family, slug) VALUES ('packstations', 'tables')")
        dup_ok = False
    except pymysql.err.IntegrityError:
        dup_ok = True
    over("C14 slug kategorie je unikatni v ramci rodiny (duplicita ve stejne rodine je v DB odmitnuta)", dup_ok, None)

    # ============================================================================================================ D) detail, ceny, interni udaje
    print("== D detail produktu, ceny, interni udaje")
    d1 = veřejně(f"/api/miniweb/products/{P1}")
    over("D1 detail viditelneho produktu: 200 {product} stejny jako v seznamu", d1.status_code == 200 and d1.get_json() == {"product": p1}, d1.status_code)
    nf = {}
    for nazev, pid in (("koncept textu", P2), ("neaktivni", P3), ("brand v popisu", P4), ("neaktivni kategorie", P5), ("jen nemecky", P6), ("brand v parametrech", P7), ("potomek skryte", P9), ("brand ve slugu", P11),
                       ("brand v nazvu", P13), ("neexistuje", 99999)):
        rr = veřejně(f"/api/miniweb/products/{pid}")
        nf[nazev] = (rr.status_code, rr.get_json())
    over("D2 detail skryteho/neexistujiciho produktu: 404 {error: not_found} (stejne pro vsechny duvody, nic neprozradi); nesmyslne id 404", all(v == (404, {"error": "not_found"}) for v in nf.values()) and get(H, "/api/miniweb/products/abc").status_code == 404, nf)
    ie = get("ie.packstations.example.top", "/api/miniweb/products").get_json()["products"][0]
    over("D3 CENY se nevydavaji: price_from je vzdy null (i u price_mode indicative, dokud neni rozhodnuto o mene a zdroji ceny), zadne pole s cenou ani kurzem v zadne odpovedi",
         all(p["price_from"] is None for p in prods["products"]) and ie["price_from"] is None and not re.search(r'"(price|cena|net|gross|vat|rate)"', json.dumps([t for _c, t in ALL_TEXT])), ie["price_from"])
    vsechno = " ".join(t for _c, t in ALL_TEXT)
    over("D4 interni udaje neodchazeji: ani interni SKU/ids tabulek, shop_product_id, status, schvalovatel; konfigurator dostane jen configurator.product_id u dostupneho produktu",
         "shop_product_id" not in vsechno and "approved_by" not in vsechno and "is_active" not in vsechno and "sort_order" not in vsechno and "miniweb_" not in vsechno, None)

    sn = get("packstationen.example.top", f"/api/miniweb/products/{P14}").get_json()["product"]
    over("D5 cisteni textu: HTML a bloky script/style/komentare pryc (i zakodovane jako entity), <br> novy radek, ridici znaky pryc, mezery sjednocene, znaky < a > v bezne vete zustanou",
         sn["name"] == "Sanitize me" and sn["summary"] == "Load > 150 kg and width < 20 mm" and sn["description"] == "Safe text and more end\nline two" and sn["delivery"] == "2 weeks"
         and sn["specs"] == [{"name": "Weight", "value": "12 < 15 kg"}] and not re.search(r"<\s*/?\s*(script|style|img|b|i)\b|onerror|alert|evil", json.dumps(sn)), sn)
    ie_cfg = get("logiman-packstations.example.top", "/api/miniweb/config").get_json()
    over("D6 neplatne hodnoty shopu se nevydaji: locale s nesmyslem -> jazyk shopu, mena malymi pismeny -> null (produkty maji currency null), slug storefrontu se znackou -> neutralni 'shop'",
         ie_cfg["locale"] == "fr" and ie_cfg["currency"] is None and ie_cfg["shop"] == "shop", ie_cfg)

    # ============================================================================================================ E) znacka
    print("== E znacka (fail closed) a legal")
    lg = veřejně("/api/miniweb/legal")
    ls = lg.get_json()
    over("E1 /legal: prodejce = nazev, adresa, kod zeme, ICO, DIC (bez e-mailu, telefonu, webu a uctu), neutralni kontakt shopu, documents prazdne (texty dodava Robert)",
         lg.status_code == 200 and set(ls["seller"]) == {"name", "address", "country_code", "id", "vat_id"} and ls["seller"]["name"] == "LOGIMAN s.r.o." and ls["seller"]["country_code"] == "CZ" and re.match(r"^\d{8}$", ls["seller"]["id"])
         and ls["seller"]["vat_id"].startswith("CZ") and ls["contact"] == {"phone": "+353 1 555 0100", "hours": "Mon-Fri 9:00-17:00"} and ls["documents"] == []
         and not re.search(r"@|\+420|logiman\.cz|2100198113|www\.", json.dumps(ls["seller"])), ls)
    texty_bez_legal = [(c, t) for c, t in ALL_TEXT if "/legal" not in c]
    unik = [(c, m.group(0)) for c, t in texty_bez_legal for m in [BRAND.search(t)] if m]
    over("E2 VSECHNY verejne odpovedi mimo /legal (config, kategorie, produkty, detaily, filtry) jsou bez znacky a dodavatele (logiman, konfigurator, vandrawee, dogus)", not unik and len(texty_bez_legal) >= 12, unik)
    adresy = [(c, m.group(0)) for c, t_ in ALL_TEXT for m in [re.search(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", t_)] if m]
    over("E2b ZADNA verejna odpoved (config, kategorie, produkty, detaily, legal) neobsahuje e-mailovou adresu (Robertovo pravidlo 2026-09-06: na webu zadny zivy e-mail), ani kdyz je ulozena v contact_json", not adresy and len(ALL_TEXT) >= 12, adresy)
    over("E3 v /legal je znacka JEN v seller.name (zakonna identifikace), nikde jinde v te odpovedi", [m.group(0).lower() for m in BRAND.finditer(lg.get_data(as_text=True))] == ["logiman"], lg.get_data(as_text=True)[:200])
    skryte = [p for p in prods["products"] if BRAND.search(json.dumps(p))]
    over("E4 fail closed: produkt se znackou v popisu, parametru, slugu nebo nazvu (i cesky 'konfigurator') se nevydava ani v seznamu, ani v detailu, ani v poctu kategorii; kategorie se znackou skryje cely podstrom", not skryte
         and {p["sku"] for p in prods["products"]}.isdisjoint({"BR-1", "SP-1", "LT-1", "KZ-1", "CH-1"}) and "brand-cat" not in [c["slug"] for c in cats] and "child-of-hidden" not in [c["slug"] for c in cats], None)
    legal_draft = get(DH, "/api/miniweb/legal")
    over("E5 /legal na konceptu: anonym 404, staff 200", legal_draft.status_code == 404 and get(DH, "/api/miniweb/legal", uid=admin_id).status_code == 200, None)

    # ============================================================================================================ F) hlavicky, limit, jen GET, nic se nezapisuje
    print("== F hlavicky, limit, metody, nic se nezapisuje")
    rv = get(H, "/api/miniweb/products")
    rs = get(H, "/api/miniweb/products", uid=admin_id)
    rd = get(DH, "/api/miniweb/products", uid=admin_id)
    r404 = get("neznamy.example.top", "/api/miniweb/config")
    over("F1 hlavicky: vsechny odpovedi X-Robots-Tag noindex; zive verejne Cache-Control public 60 s, staff, koncept i chyby no-store", all(x.headers.get("X-Robots-Tag") == "noindex, nofollow" for x in (rv, rs, rd, r404))
         and rv.headers["Cache-Control"] == "public, max-age=60" and rs.headers["Cache-Control"] == "no-store" and rd.headers["Cache-Control"] == "no-store" and r404.headers["Cache-Control"] == "no-store", rv.headers.get("Cache-Control"))
    over("F2 jen GET: POST, PUT a DELETE na vsechny endpointy 405", all(cl.open(c, method=m, base_url=f"http://{H}").status_code == 405 for c in ("/api/miniweb/config", "/api/miniweb/categories", "/api/miniweb/products", f"/api/miniweb/products/{P1}", "/api/miniweb/legal") for m in ("POST", "PUT", "DELETE")), None)
    appmod._rate_limit_buckets.clear()
    odp = [cl.get("/api/miniweb/config", base_url=f"http://{H}").status_code for _ in range(mw.READ_LIMIT_PER_MIN + 3)]
    over("F3 limit pozadavku na IP (240/min): dalsi pozadavky 429 {error: rate_limited}", odp[:mw.READ_LIMIT_PER_MIN] == [200] * mw.READ_LIMIT_PER_MIN and odp[mw.READ_LIMIT_PER_MIN:] == [429] * 3
         and cl.get("/api/miniweb/config", base_url=f"http://{H}").get_json() == {"error": "rate_limited"}, odp[-5:])
    appmod._rate_limit_buckets.clear()
    zdroj = open(mw.__file__, encoding="utf-8").read()
    cteci = "\n".join(ast.get_source_segment(zdroj, n_) for n_ in ast.parse(zdroj).body if isinstance(n_, ast.FunctionDef) and n_.name != "miniweb_inquiry")
    over("F4 cteci cast nic nezapisuje: zadna funkce krome miniweb_inquiry (poptavka, test_miniweb_poptavka.py) neobsahuje INSERT/UPDATE/DELETE/DROP/ALTER ani odesilani e-mailu",
         len(cteci) > 3000 and not re.search(r"INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|send_email|smtp|\.commit\(", cteci, re.I), None)

    # ============================================================================================================ K) slovensky shop = dalsi jazyk bez zasahu do kodu
    print("== K slovensky shop (Robert 2026-10-02: nejdriv slovenska verze, anglictina druha)")
    S_SK = sf("packstations-sk", "baliace-stoly.example.top", lang="sk")
    shop(S_SK, locale="sk-SK", currency="EUR", countries="SK,CZ,AT,HU,PL", contact={"email": "info@baliace-stoly.example", "phone": "+421 2 5555 0100", "hours": "Po-Pi 9:00-17:00"})
    kat_text(C1, "sk", "Stoly")
    kat_text(C2, "sk", "Baliace stoly")
    prod_text(P1, "sk", "Baliaci stôl PS-120", "Výškovo nastaviteľný baliaci stôl", "<p>Robustný <b>hliníkový</b> rám.</p>", delivery="3-4 týždne", specs=[{"name": "Rozmery", "value": "1316 × 1925 × 1285 mm"}])
    prod_text(P4, "sk", "Popis so značkou", description="Vyrobené firmou Logiman v Prahe.")
    prod_text(P2, "sk", "Baliaci stôl PS-90", status="draft")
    HSK = "baliace-stoly.example.top"
    cfg_sk = get(HSK, "/api/miniweb/config").get_json()
    cats_sk = get(HSK, "/api/miniweb/categories").get_json()["categories"]
    prods_sk = get(HSK, "/api/miniweb/products").get_json()
    leg_sk, leg_en = get(HSK, "/api/miniweb/legal").get_json(), get(H, "/api/miniweb/legal").get_json()
    cfg_en2 = get(H, "/api/miniweb/config").get_json()
    over("K1 slovensky shop podle domeny BEZ zasahu do kodu: lang sk, locale sk-SK, mena EUR, zeme, neutralni kontakt (telefon a doba, e-mail nikdy), jen poptavka; v alternates je anglicky shop a v anglickem slovensky",
         cfg_sk["lang"] == "sk" and cfg_sk["locale"] == "sk-SK" and cfg_sk["currency"] == "EUR" and cfg_sk["countries"] == ["SK", "CZ", "AT", "HU", "PL"] and cfg_sk["contact"] == {"phone": "+421 2 5555 0100", "hours": "Po-Pi 9:00-17:00"}
         and cfg_sk["price_mode"] == "hidden" and cfg_sk["inquiry_only"] is True and {"lang": "en", "href": "https://packstations.example.top/"} in cfg_sk["alternates"]
         and {"lang": "sk", "href": "https://baliace-stoly.example.top/"} in cfg_en2["alternates"], (cfg_sk, cfg_en2["alternates"]))
    over("K2 katalog ve slovenstine: kategorie a produkty jen se SCHVALENYM slovenskym textem (P1), nazev, shrnuti, popis (bezpecne HTML), dodani a parametry slovensky; zadny anglicky text se neprosadi; produkt jen s konceptem (PS-90) a se znackou (BR-1) se neverejni",
         [c["slug"] for c in cats_sk] == ["tables", "packing-stations"] and [c["name"] for c in cats_sk] == ["Stoly", "Baliace stoly"] and [p["sku"] for p in prods_sk["products"]] == ["PS-120"]
         and prods_sk["products"][0]["name"] == "Baliaci stôl PS-120" and prods_sk["products"][0]["delivery"] == "3-4 týždne" and prods_sk["products"][0]["specs"] == [{"name": "Rozmery", "value": "1316 × 1925 × 1285 mm"}]
         and prods_sk["products"][0]["id"] == P1 and "Packing" not in json.dumps(prods_sk, ensure_ascii=False) and "Tables" not in json.dumps(cats_sk, ensure_ascii=False), (cats_sk, prods_sk))
    over("K3 pravni udaje prodejce (legal.seller: nazev, adresa, ICO, DIC, zeme) jsou STEJNE pro vsechny jazyky (jedno misto, zakonna identifikace) a existuji i pro slovensky shop; kontakt je neutralni kontakt slovenskeho shopu",
         leg_sk["seller"] == leg_en["seller"] and leg_sk["seller"]["name"] and leg_sk["seller"]["id"] and leg_sk["seller"]["vat_id"] and leg_sk["seller"]["country_code"] == "CZ" and leg_sk["seller"]["address"]
         and leg_sk["contact"] == cfg_sk["contact"] and leg_sk["documents"] == [], leg_sk)
    over("K4 staff si muze slovenske texty prohlednout i na jine domene (?lang=sk, koncepty ?drafts=1) pred spustenim shopu; anonym dostane jazyk domeny",
         get(H, "/api/miniweb/products", uid=admin_id, lang="sk").get_json()["products"][0]["name"] == "Baliaci stôl PS-120" and get(H, "/api/miniweb/products", lang="sk").get_json()["products"][0]["name"] == "Packing station PS-120"
         and any(p["sku"] == "PS-90" and p["name"] == "Baliaci stôl PS-90" for p in get(HSK, "/api/miniweb/products", uid=admin_id, drafts="1").get_json()["products"]), None)

    # ============================================================================================================ L) pravni dokumenty (podminky, soukromi, vraceni) u poptavkoveho formulare
    print("== L pravni dokumenty")

    def doc(kind, lang, title, body, status="approved", family="packstations", approved_at="2026-10-05 10:00:00"):
        sql("INSERT INTO miniweb_documents (family, kind, lang, title, body, status, approved_at) VALUES (%s,%s,%s,%s,%s,%s,%s)", (family, kind, lang, title, body, status, approved_at if status == "approved" else None))

    legal0 = get(HSK, "/api/miniweb/legal").get_json()
    doc("returns", "sk", "Vrátenie tovaru", "<p>Tovar môžete vrátiť do 14 dní.</p>\n<p>Druhý odsek &amp; viac.</p><script>zle()</script>")
    doc("terms", "sk", "Obchodné podmienky", "Predávajúcim je LOGiMAN  s.r.o., IČO 28337638.\nPodmienky objednávky.")
    doc("privacy", "sk", "Ochrana osobných údajov", "Osobné údaje spracúvame len na vybavenie dopytu.", status="draft")
    doc("shipping", "sk", "Doprava", "Dodanie do 3-5 týždňov. Dopravu zabezpečuje Logiman.")                    # znacka mimo zakonneho nazvu -> neverejni se
    doc("cookies", "sk", "Cookies", "Používame [DOPLNIŤ: zoznam] cookies.")                                       # zastupna znacka -> neverejni se
    doc("returns", "en", "Returns", "Goods may be returned within 14 days.")
    doc("terms", "de", "AGB", "Allgemeine Geschäftsbedingungen.")
    doc("terms", "sk", "Obchodné podmienky inej rodiny", "Iná rodina.", family="worktables")
    leg = get(HSK, "/api/miniweb/legal").get_json()
    over("L1 pravni dokumenty ve slovenstine u slovenskeho shopu: jen SCHVALENE v poradi terms, returns (privacy je draft, shipping ma znacku, cookies zastupnou znacku), text jako cisty text s odstavci, datum schvaleni, ne dokument jine rodiny ani jineho jazyka",
         [d["kind"] for d in leg["documents"]] == ["terms", "returns"] and [d["title"] for d in leg["documents"]] == ["Obchodné podmienky", "Vrátenie tovaru"]
         and leg["documents"][1]["body"] == "Tovar môžete vrátiť do 14 dní.\n\nDruhý odsek & viac." and leg["documents"][0]["updated"] == "2026-10-05" and all(set(d) == {"kind", "title", "body", "updated"} for d in leg["documents"])
         and legal0["documents"] == [], (legal0["documents"], leg["documents"]))
    over("L2 zakonny nazev prodejce v dokumentu je povolen (jen presne zakonny nazev, bez ohledu na velikost pismen a mezer), jina znacka (samotne Logiman v dokumentu Doprava) dokument zablokuje; seller, kontakt a sada klicu legal beze zmeny",
         "LOGiMAN" in leg["documents"][0]["body"] and not any(d["kind"] == "shipping" for d in leg["documents"]) and set(leg) == {"seller", "contact", "documents"} and leg["seller"]["name"], leg["documents"])
    over("L3 jazyk urcuje domena: anglicky shop vydava anglicky dokument (returns), nemecky jen nemecky (terms), shop jine rodiny jine dokumenty; staff v nahledu vidi i koncepty (privacy), anonym ne",
         [d["kind"] for d in get(H, "/api/miniweb/legal").get_json()["documents"]] == ["returns"] and [d["kind"] for d in get("packstationen.example.top", "/api/miniweb/legal").get_json()["documents"]] == ["terms"]
         and [d["kind"] for d in get(HSK, "/api/miniweb/legal", uid=admin_id, drafts="1").get_json()["documents"]] == ["terms", "privacy", "returns"]
         and [d["kind"] for d in get(HSK, "/api/miniweb/legal").get_json()["documents"]] == ["terms", "returns"], None)
    over("L4 regionalni jazyk shopu (en-ie) spadne na zakladni dokument (en); dokumenty se nevydavaji bez schvaleneho textu ani s prazdnym nazvem nebo textem",
         [d["kind"] for d in get("ie.packstations.example.top", "/api/miniweb/legal").get_json()["documents"]] == ["returns"], get("ie.packstations.example.top", "/api/miniweb/legal").get_json()["documents"])
    sql("UPDATE miniweb_documents SET body='' WHERE kind='returns' AND lang='sk'")
    over("L5 dokument s prazdnym textem se nevydava", [d["kind"] for d in get(HSK, "/api/miniweb/legal").get_json()["documents"]] == ["terms"], None)

    # ============================================================================================================ N) kontakt z nastaveni spolecnosti (Robert: "dej tam proste moje kontaktni udaje")
    print("== N kontakt z nastaveni spolecnosti")
    import company_info as firma_mod
    with real.cursor() as cur:
        FIRMA = firma_mod._get_company_info(cur)                 # nastaveni spolecnosti (app_settings company_info + vychozi hodnoty): jediny zdroj kontaktu
    real.rollback()
    sql("UPDATE miniweb_shops SET contact_json=%s WHERE storefront_id=%s", (json.dumps({"use_company": True, "hours": "Po-Pi 9:00-17:00", "email": "x@y.example", "phone": "123"}), S_SK["id"]))
    c_cfg, c_leg = get(HSK, "/api/miniweb/config"), get(HSK, "/api/miniweb/legal")
    ocek = {"phone": FIRMA["phone"], "hours": "Po-Pi 9:00-17:00", "name": FIRMA["name"], "address": FIRMA["address"]}
    celek = c_cfg.get_data(as_text=True) + c_leg.get_data(as_text=True)
    over("N1 kontakt z nastaveni spolecnosti (contact_json use_company true): jmeno, adresa a telefon z JEDNOHO zdroje (nastaveni spolecnosti company_info), doba z radku shopu; telefon z radku se neuplatni (jeden zdroj); /config i /legal shodne; "
         "zadny e-mail ani web (v odpovedich neni zavinac ani e-mail spolecnosti ani z contact_json)",
         c_cfg.get_json()["contact"] == ocek and c_leg.get_json()["contact"] == ocek and "@" not in celek and FIRMA["email"] not in celek and "x@y.example" not in celek and FIRMA["phone"] and FIRMA["name"] and FIRMA["address"], (c_cfg.get_json()["contact"], ocek))
    for hodnota in ("true", 1, False, None, "yes"):
        sql("UPDATE miniweb_shops SET contact_json=%s WHERE storefront_id=%s", (json.dumps({"use_company": hodnota, "phone": "+421 2 5555 0100"}), S_SK["id"]))
    over("N2 jen presne true zapina kontakt ze spolecnosti (retezec 'true', 1, 'yes', false, null se ignoruji): kontakt zustane jen telefon a doba z radku shopu", get(HSK, "/api/miniweb/config").get_json()["contact"] == {"phone": "+421 2 5555 0100", "hours": ""}, get(HSK, "/api/miniweb/config").get_json()["contact"])
    sql("UPDATE miniweb_shops SET contact_json=%s WHERE storefront_id=%s", (json.dumps({"use_company": 1, "phone": "+421 2 5555 0100"}), S_SK["id"]))
    over("N3 ostatni shopy beze zmeny: anglicky shop ma dal jen telefon a dobu z radku shopu (bez jmena a adresy spolecnosti)", set(get(H, "/api/miniweb/config").get_json()["contact"]) == {"phone", "hours"}, get(H, "/api/miniweb/config").get_json()["contact"])

    # mutace
    def mutant(funkce, stare, nove, n=1):
        t_ = ast.parse(zdroj)
        node = next(n_ for n_ in t_.body if isinstance(n_, ast.FunctionDef) and n_.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == n, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x, ocekavano {n}x"
        ns = dict(vars(mw))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    def v_kontextu(host, fn, uid=None, **params):
        with appmod.app.test_request_context("/", base_url=f"http://{host}", query_string=params or None, headers=cookie(uid)), real.cursor() as cur:
            return fn(cur)

    ctx_en = v_kontextu(H, lambda cur: mw._shop_context(cur))
    prod_spravne = v_kontextu(H, lambda cur: [p["sku"] for p in mw._visible_products(cur, ctx_en)[0]])
    m1 = mutant("_product_json", "dealers._brand_hit(", "False and dealers._brand_hit(")
    mw_orig = mw._product_json
    mw._product_json = m1
    try:
        prod_m1 = v_kontextu(H, lambda cur: [p["sku"] for p in mw._visible_products(cur, ctx_en)[0]])
    finally:
        mw._product_json = mw_orig
    over("M1 mutace: bez filtru znacky by se vydaly produkty se znackou (BR-1, SP-1, LT-1, KZ-1) - testy C3 a E4 ji zachyti", prod_spravne == ["PS-120", "ST-1", "WT-100", "BS-1"] and {"BR-1", "SP-1", "LT-1", "KZ-1"} <= set(prod_m1), prod_m1)
    mw_vc = mw._visible_categories
    mw._visible_categories = mutant("_visible_categories", ' AND family=%s ORDER BY sort_order, id", (ctx["shop"]["family"],))', ' ORDER BY sort_order, id")')
    try:
        prod_m7 = v_kontextu(H, lambda cur: [p["sku"] for p in mw._visible_products(cur, ctx_en)[0]])
    finally:
        mw._visible_categories = mw_vc
    over("M7 mutace: bez filtru rodiny by shop packstations videl i produkt jine rodiny (WT-9) - testy C12 a C13 ji zachyti", "WT-9" in prod_m7 and "WT-9" not in prod_spravne, prod_m7)
    m2 = mutant("_shop_context", "if not live and not staff:", "if False:")
    mw_ctx = mw._shop_context
    mw._shop_context = m2
    try:
        r_m2 = get(DH, "/api/miniweb/config")
    finally:
        mw._shop_context = mw_ctx
    over("M2 mutace: bez serverove brany by koncept videl kdokoli (spravne 404) - test A5 ji zachyti", r_m2.status_code == 200, r_m2.status_code)
    m3 = mutant("_texts", "ctx[\"statuses\"]", "[\"approved\", \"draft\"]", n=2)
    mw_txt = mw._texts
    mw._texts = m3
    try:
        prod_m3 = v_kontextu(H, lambda cur: [p["sku"] for p in mw._visible_products(cur, ctx_en)[0]])
    finally:
        mw._texts = mw_txt
    over("M3 mutace: bez filtru stavu textu by verejnost videla i neschvalene texty (PS-90) - testy C3 a C10 ji zachyti", "PS-90" in prod_m3 and "PS-90" not in prod_spravne, prod_m3)
    m4 = mutant("miniweb_categories", "counts[cid] += 1", "pass")
    vf_orig = appmod.app.view_functions["miniweb_categories"]
    appmod.app.view_functions["miniweb_categories"] = mw._guard(m4)
    try:
        cnt_m4 = {c["slug"]: c["count"] for c in get(H, "/api/miniweb/categories").get_json()["categories"]}
    finally:
        appmod.app.view_functions["miniweb_categories"] = vf_orig
    over("M4 mutace: bez pocitani produktu by vsechny kategorie mely count 0 (spravne 3/1/1) - test C2 ji zachyti", set(cnt_m4.values()) == {0} and {c["slug"]: c["count"] for c in cats} == {"tables": 3, "packing-stations": 1, "storage": 1}, cnt_m4)
    m5 = mutant("_storefront_by_host", "FROM storefront_hosts h", "FROM storefront_hosts_xx h")
    try:
        v_kontextu(H, lambda cur: m5(cur, ALIAS))
        alias_m5 = "PROSLO"
    except Exception:
        alias_m5 = "chyba"
    real.rollback()
    m6 = mutant("_is_staff", 'user.get("role") in PERMISSION_ROLES', "True")
    mw_staff = mw._is_staff
    mw._is_staff = m6
    try:
        r_m6 = get(DH, "/api/miniweb/config", uid=uzivatele[0])
    finally:
        mw._is_staff = mw_staff
    over("M6 mutace: kdyby se staff poznal jen podle prihlaseni (bez role), videl by koncept i bezny zakaznik (spravne 404) - test A5 ji zachyti", r_m6.status_code == 200, r_m6.status_code)
    over("M5 mutace: kdyby se alias hledal jinde nez v storefront_hosts, alias hostu by shop nenasel (spravne nasel) - test A2", alias_m5 == "chyba" and v_kontextu(H, lambda cur: mw._storefront_by_host(cur, ALIAS))["id"] == S_EN["id"], alias_m5)
    m8 = mutant("_contact", 'if raw.get("use_company") is True and cur is not None:', 'if raw.get("use_company") and cur is not None:')
    with real.cursor() as cur_m8:
        kontakt_m8, kontakt_ok = m8({"contact_json": {"use_company": "false"}}, cur_m8), mw._contact({"contact_json": {"use_company": "false"}}, cur_m8)
    real.rollback()
    over("M8 mutace: kdyby kontakt ze spolecnosti zapinala jakakoli pravdiva hodnota (retezec 'false'), jmeno a adresa spolecnosti by se vydaly i tam, kde to nikdo nechtel (spravne jen true) - test N2 ji zachyti",
         "name" in kontakt_m8 and "name" not in kontakt_ok, (kontakt_m8, kontakt_ok))
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + tuple(f"_tpl_{x}" for x in TEMP_LIKE):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (mini-shopy, kategorie, produkty, texty, storefronty, aliasy, uzivatele, poptavky, audit) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK mini-shop faze 1 - cteci API /api/miniweb/*: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
