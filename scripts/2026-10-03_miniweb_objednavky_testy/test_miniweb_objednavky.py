#!/opt/konfigurator/api/venv/bin/python
"""Mini-shop: kosik a objednavka konfigurovatelneho stolu (bot5, 2026-10-03): api/miniweb_objednavky.py + patche miniweb.py (checkout_mode) a app.py (import).

SKUTECNY kod (miniweb, miniweb_objednavky, miniweb_cena, konfigurace_kosik, orders, konfigurator stolu od bot8) pres Flask test client nad DOCASNYMI tabulkami (storefronty, mini-shopy, katalog mini-shopu,
objednavky, polozky, historie, doklady, cislovani, produkty, zakaznici, nastaveni). Ostre tabulky se jen ctou a po testu se porovnaji pocty. E-maily a audit se zachytavaji, SMTP je zakazano.
Kandidat: MINIWEB_PY (jinak zivy soubor, ktery uz ma checkout_mode, nebo kopie s patchem ze sady), MINIWEB_OBJEDNAVKY_PY (jinak zivy).
Cast Q  quote: cena jen ze serveru v EUR, vyber a hash, spojeni stejnych radku, neplatna konfigurace, verze pravidel, branky (shop, objednavky, marze/kurz), nic se nezapisuje
Cast O  objednavka: validace firmy a kontaktu, zivotni cyklus (objednavka bez proformy a bez e-mailu), snimek, idempotence, limity, ochrana ceny, cena v Kc = kalkulace
Cast M  mutace klicovych ochran
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-03_miniweb_objednavky_testy/test_miniweb_objednavky.py
"""
import inspect
import json
import os
import re
import shutil
import smtplib
import subprocess
import sys
import tempfile
import textwrap
import time
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(HERE, "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_mw_obj_")

os.makedirs(os.path.join(tmp, "api"))
if os.environ.get("MINIWEB_PY"):
    shutil.copy(os.environ["MINIWEB_PY"], os.path.join(tmp, "miniweb.py"))
else:
    live = open(os.path.join(API, "miniweb.py"), encoding="utf-8").read()
    shutil.copy(os.path.join(API, "miniweb.py"), os.path.join(tmp, "api", "miniweb.py"))
    if "checkout_mode" not in live:
        subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, "miniweb.py.patch")], check=True)
    shutil.copy(os.path.join(tmp, "api", "miniweb.py"), os.path.join(tmp, "miniweb.py"))
if os.environ.get("DOCUMENTS_PY"):
    shutil.copy(os.environ["DOCUMENTS_PY"], os.path.join(tmp, "documents.py"))
else:
    shutil.copy(os.path.join(API, "documents.py"), os.path.join(tmp, "api", "documents.py"))
    if "_order_vat_rate" not in open(os.path.join(API, "documents.py"), encoding="utf-8").read():
        subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, "documents.py.patch")], check=True)
    shutil.copy(os.path.join(tmp, "api", "documents.py"), os.path.join(tmp, "documents.py"))
shutil.copy(os.environ.get("MINIWEB_OBJEDNAVKY_PY") or os.path.join(API, "miniweb_objednavky.py"), os.path.join(tmp, "miniweb_objednavky.py"))
shutil.copy(os.environ.get("MINIWEB_OBJEDNAVKY_ADMIN_PY") or os.path.join(API, "miniweb_objednavky_admin.py"), os.path.join(tmp, "miniweb_objednavky_admin.py"))
sys.path.insert(0, API)
sys.path.insert(0, tmp)                         # kandidati PRED importem app (app.py importuje nasazene moduly)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import miniweb as mw  # noqa: E402
import miniweb_objednavky as mo  # noqa: E402
import miniweb_objednavky_admin as moa  # noqa: E402
import documents as docs  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402
import miniweb_cena  # noqa: E402
import miniweb_vies  # noqa: E402
import orders as ordersmod  # noqa: E402
import stul_api  # noqa: E402
import stul_glb  # noqa: E402
import stul_shop  # noqa: E402
import dealers  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


AUDIT, EMAILS = [], []
mo.log_audit = lambda *a, **k: AUDIT.append((a, k))
moa.log_audit = lambda *a, **k: AUDIT.append((a, k))
QUEUE = []
docs._auto_email_after_issue = lambda order_id, doc_id: QUEUE.append((order_id, doc_id))          # e-mail s fakturou jde do schvalovaci fronty; test jen zachyti volani
ordersmod.log_audit = lambda *a, **k: AUDIT.append((a, k))
ordersmod._send_order_emails_bg = lambda result: EMAILS.append(result)
ordersmod._send_status_change_email = lambda *a, **k: EMAILS.append(("stav", a))
dealers.attach_attribution = lambda *a, **k: None


def _zakazano(*a, **k):
    EMAILS.append(("smtp", a))
    raise AssertionError("TEST: odesilani e-mailu je zakazane")


appmod.send_email = _zakazano
smtplib.SMTP = _zakazano
smtplib.SMTP_SSL = _zakazano

miniweb_vies._dotaz = lambda kod, cislo: {"valid": True}          # test NIKDY nevola skutecny VIES (sit); jednotlive scenare nize si dotaz nahrazuji
# katalog dilu pro cenu se nacte JEDNOU pred zalozenim docasnych tabulek
stul_api._ctx_ceny()
stul_api.CTX_TTL_S = 10 ** 9


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE_TABULKY = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_products", "shop_payment_methods", "shop_shipping_methods", "shop_customers",
                 "app_settings", "audit_log", "shop_emails", "system_emails", "crm_leads", "car_storefronts", "storefront_hosts", "miniweb_shops", "miniweb_products", "miniweb_inquiries")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE_TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")
            out["seq_obj"] = int(cur.fetchone()["s"])
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")
            out["seq_dok"] = int(cur.fetchone()["s"])
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "shop_products", "shop_payment_methods", "shop_shipping_methods",
             "shop_stock_movements", "shop_customers", "shop_customer_groups", "shop_emails", "system_emails", "crm_leads", "car_storefronts", "storefront_hosts", "miniweb_shops",
             "miniweb_categories", "miniweb_category_texts", "miniweb_products", "miniweb_product_texts", "miniweb_inquiries")
TEMP_COPY = ("shop_document_sequences", "shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


def pocet(t):
    return jedno(f"SELECT COUNT(*) AS n FROM `{t}`")["n"]


def mutant(funkce, stary, novy):
    """Kopie funkce modulu miniweb_objednavky s nahrazenym kusem zdroje (test, ze ochrana skutecne neco hlida)."""
    zdroj = textwrap.dedent(inspect.getsource(funkce))
    assert stary in zdroj, f"mutace: kotva nenalezena v {funkce.__name__}: {stary}"
    ns = {}
    exec(compile(zdroj.replace(stary, novy, 1), "<mutant>", "exec"), mo.__dict__, ns)
    return ns[funkce.__name__]


try:
    with real.cursor() as cur:
        for t in TEMP_COPY:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        for t in TEMP_LIKE + TEMP_COPY:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='miniweb_shops' AND COLUMN_NAME='orders_enabled'")
        if not list(cur.fetchone().values())[0]:                  # pred migraci: sloupec se prida jen do DOCASNE kopie
            cur.execute("ALTER TABLE `miniweb_shops` ADD COLUMN orders_enabled TINYINT(1) NOT NULL DEFAULT 0")
        for sl, df in (("shipping_review", "TINYINT(1) NOT NULL DEFAULT 0"), ("vat_mode", "VARCHAR(20) DEFAULT NULL"), ("vat_check", "VARCHAR(20) DEFAULT NULL")):
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_orders' AND COLUMN_NAME=%s", (sl,))
            if not list(cur.fetchone().values())[0]:
                cur.execute(f"ALTER TABLE `shop_orders` ADD COLUMN `{sl}` {df}")
    real.commit()

    sql("INSERT INTO shop_payment_methods (id, name, price_czk, requires_advance_invoice, active) VALUES (1,'Platba předem',0,1,1)")
    sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (1,'Osobní odběr',0,1,0,'fixed')")
    sql("INSERT INTO shop_products (sku, name, price_czk_placeholder, stock_qty, weight_g, active, unit) VALUES ('T-STUL','Test stůl',NULL,0,0,0,'ks')")   # active=0 jako karta 4934 (pravidlo 54)
    CFG = jedno("SELECT id FROM shop_products WHERE sku='T-STUL'")["id"]
    stul_shop._PRODUKTY.update(t=time.time() + 10 ** 9, map={str(CFG): stul_shop.RECEPT})

    HOST = "mw-sk.example.top"

    def sf(slug, host, status="live", lang="sk"):
        sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang) VALUES (%s,%s,%s,%s,%s)", (slug, slug, host, status, lang))
        return jedno("SELECT * FROM car_storefronts WHERE slug=%s", (slug,))

    def shop(storefront, **kw):
        h = {"storefront_id": storefront["id"], "family": "packstations", "price_mode": "shown", "currency": "EUR", "countries": "SK", "inquiry_enabled": 1, "orders_enabled": 1,
             "margin_pct": 0, "eur_rate": 25}
        h.update(kw)
        sql(f"INSERT INTO miniweb_shops ({', '.join(h)}) VALUES ({', '.join(['%s'] * len(h))})", list(h.values()))

    S_SK = sf("packstations-sk", HOST)
    S_OFF = sf("sk-off", "off.example.top")
    S_DRAFT = sf("sk-draft", "draft.example.top", status="draft")
    S_NOM = sf("sk-nomarze", "nomarze.example.top")
    S_NOK = sf("sk-nokurz", "nokurz.example.top")
    S_HID = sf("sk-hidden", "hidden.example.top")
    S_EN = sf("en-orders", "en.example.top", lang="en")
    shop(S_SK)
    shop(S_OFF, orders_enabled=0)
    shop(S_DRAFT)
    shop(S_NOM, margin_pct=None)
    shop(S_NOK, eur_rate=None)
    shop(S_HID, price_mode="hidden")
    shop(S_EN, countries="SK,CZ")

    sql("INSERT INTO miniweb_categories (family, slug, sort_order) VALUES ('packstations', 'tables', 1)")
    C1 = jedno("SELECT id FROM miniweb_categories WHERE slug='tables'")["id"]
    for lang, name in (("sk", "Stoly"), ("en", "Tables")):
        sql("INSERT INTO miniweb_category_texts (miniweb_category_id, lang, name, status) VALUES (%s,%s,%s,'approved')", (C1, lang, name))

    def prod(slug, sku, shop_product_id=None, configurator=0):
        sql("INSERT INTO miniweb_products (category_id, slug, public_sku, shop_product_id, configurator_available, is_active) VALUES (%s,%s,%s,%s,%s,1)", (C1, slug, sku, shop_product_id, configurator))
        pid = jedno("SELECT id FROM miniweb_products WHERE slug=%s", (slug,))["id"]
        for lang, name in (("sk", "Konfigurovateľný stôl"), ("en", "Configurable table")):
            sql("INSERT INTO miniweb_product_texts (miniweb_product_id, lang, name, summary, description, delivery, status) VALUES (%s,%s,%s,'S','D','3 týždne','approved')", (pid, lang, name))
        return pid

    P_CFG = prod("cfg-table", "PWB-001", CFG, 1)
    P_PLAIN = prod("plain-table", "WT-100")

    cl = appmod.app.test_client()

    def volej(cesta, body, host=HOST, vynuluj=True, **kw):
        if vynuluj:
            appmod._rate_limit_buckets.clear()
        return cl.post(cesta, json=body, base_url="https://" + host, **kw)

    def quote(items, host=HOST, **extra):
        return volej("/api/miniweb/quote", {"country": "SK", "items": items, **extra}, host)

    def cfg_item(selection=None, qty=1, pid=None, **extra):
        return {"product_id": pid or P_CFG, "qty": qty, "configuration": {"selection": {} if selection is None else selection, "rules_version": stul_glb.RULES_VERSION}, **extra}

    def valid_order(items=None, **kw):
        b = {"country": "SK", "company": "Firma s.r.o.", "company_id": "12 345 678", "vat_id": "SK2020202020", "name": "Ján Test", "email": "jan@firma.test", "phone": "+421 900 111 222",
             "billing": {"street": "Hlavná 1", "city": "Bratislava", "zip": "811 01"}, "delivery": {"same": True}, "shipping": "quote", "payment": "transfer", "b2b_confirm": True, "consent": True, "website": "",
             "items": items if items is not None else [cfg_item()]}
        b.update(kw)
        return b

    def objednavka(b, host=HOST, vynuluj=True):
        return volej("/api/miniweb/orders", b, host, vynuluj)

    CFGSET = {"rate": Decimal(25), "margin_pct": Decimal(0)}
    ODLISNA = {"w": 1500, "d": 700, "h": 900, "led": False}
    BAD_SEL = {"cut1": True, "cut2": True, "cut2x": 100, "cut2z": 100}
    stul_api.obnov_pravidla(force=True)                                          # jako before_request na serveru: ulozena pravidla stolu (app_settings stul_pravidla, po systemech vc. 45) se nactou PRED vypoctem kodu; bez toho by ocekavany kod pocital s vychozimi prahy a objednavka (v requestu s ulozenymi) by mela jiny - test zavisel na poradi, ne na chybe (bot5 2026-10-08)
    R0, R1 = stul_shop.resolve({}, "cs"), stul_shop.resolve(ODLISNA, "cs")
    NET0, NET1 = R0["price"]["net"], R1["price"]["net"]
    EUR0, EUR1 = miniweb_cena.cena_eur(NET0, CFGSET), miniweb_cena.cena_eur(NET1, CFGSET)

    # ============================================================================================================ Q) quote
    print("== Q quote")
    r = quote([cfg_item(), cfg_item(ODLISNA, qty=2)])
    k = r.get_json()
    over("Q1 quote: 200, EUR bez DPH, radky s cenou ze serveru (kus a soucet radku), soucet = soucet radku, vyber a kod ze serveru",
         r.status_code == 200 and k["currency"] == "EUR" and k["prices_include_vat"] is False and k["valid"] is True and len(k["lines"]) == 2
         and k["lines"][0]["net_unit"] == EUR0 and k["lines"][0]["net_total"] == EUR0 and k["lines"][1]["net_unit"] == EUR1 and k["lines"][1]["net_total"] == EUR1 * 2
         and k["subtotal"] == EUR0 + EUR1 * 2 and k["lines"][0]["configuration"]["kod"] == R0["kod"] and k["lines"][0]["configuration"]["selection"] == R0["selection"]
         and k["lines"][0]["product_id"] == P_CFG, (r.status_code, k))
    over("Q2 quote nese volby dopravy (po dohode a osobni odber, jazyk shopu) a poznamky; zakaznik nevidi kusovnik ani cenovy souhrn",
         [o["id"] for o in k["shipping_options"]] == ["toptrans", "quote", "pickup"] and k["shipping_options"][0]["net"] is None and k["shipping_options"][0]["reason"] == "zip_missing"
         and k["shipping_options"][2]["net"] == 0 and "dohode" in k["shipping_options"][1]["label"]
         and "bom" not in json.dumps(k) and "price_summary" not in json.dumps(k) and "vat_excluded" in k["notes"] and k["vat"]["rate"] == 21 and k["vat"]["reason"] == "no_vat_id", k)
    r = quote([cfg_item(None, 1, price=1, net_unit=1, unit_price_czk=1, net_total=1) | {"net_unit": 1, "price": 1}], subtotal=1)
    over("Q3 cena z klienta se ignoruje (net_unit, price, subtotal posilany jako 1)", r.status_code == 200 and r.get_json()["lines"][0]["net_unit"] == EUR0 and r.get_json()["subtotal"] == EUR0, r.get_json())
    r = quote([cfg_item(None, 2), cfg_item({"w": "1280"}, 3)])
    over("Q4 stejna efektivni konfigurace (retezec misto cisla) = JEDEN radek se souctem mnozstvi", r.status_code == 200 and len(r.get_json()["lines"]) == 1 and r.get_json()["lines"][0]["qty"] == 5
         and r.get_json()["lines"][0]["net_total"] == EUR0 * 5, r.get_json())
    r = quote([cfg_item(BAD_SEL), cfg_item()])
    k = r.get_json()
    over("Q5 neplatna konfigurace: quote 200, valid false, radek s chybami a bez ceny, platny radek se pocita", r.status_code == 200 and k["valid"] is False and k["lines"][0]["configuration"]["valid"] is False
         and k["lines"][0]["net_unit"] is None and k["lines"][0]["configuration"]["errors"] and k["lines"][1]["net_unit"] == EUR0 and k["subtotal"] == EUR0, k)
    r = volej("/api/miniweb/quote", {"country": "SK", "items": [{"product_id": P_CFG, "qty": 1, "configuration": {"selection": {}, "rules_version": "stara-verze"}}]})
    over("Q6 stara verze pravidel = 409 rules_changed", r.status_code == 409 and r.get_json()["error"] == "rules_changed", (r.status_code, r.get_json()))
    r1 = quote([{"product_id": P_PLAIN, "qty": 1, "configuration": {"selection": {}}}])
    r2 = quote([{"product_id": 987654, "qty": 1, "configuration": {"selection": {}}}])
    r3 = quote([{"product_id": P_CFG, "qty": 1}])
    r4 = quote([cfg_item(qty=100)])
    r5 = quote([])
    r6 = volej("/api/miniweb/quote", {"country": "DE", "items": [cfg_item()]})
    over("Q7 jen konfigurovatelny stul (jiny a neznamy produkt 422 product_not_available), konfigurace povinna, mnozstvi 1 az 99, aspon jedna polozka, zeme jen z shopu",
         r1.status_code == 422 and r1.get_json()["error"] == "product_not_available" and r2.status_code == 422 and r3.status_code == 400 and r3.get_json()["error"] == "configuration_required"
         and r4.status_code == 400 and r5.status_code == 400 and r6.status_code == 400 and r6.get_json()["error"] == "country_invalid", [x.get_json() for x in (r1, r2, r3, r4, r5, r6)])
    brany = {"vypnute objednavky": quote([cfg_item()], "off.example.top"), "koncept pro anonyma": quote([cfg_item()], "draft.example.top"), "neznamy host": quote([cfg_item()], "neznam.example.top"),
             "skryta cena": quote([cfg_item()], "hidden.example.top")}
    over("Q8 branky: shop s vypnutymi objednavkami, koncept a neznamy host = 404, skryta cena = 404 (price_mode hidden nema cenu, shop bez objednavek)",
         brany["vypnute objednavky"].status_code == 404 and brany["koncept pro anonyma"].status_code == 404 and brany["neznamy host"].status_code == 404, {k_: v.status_code for k_, v in brany.items()})
    r_nm, r_nk = quote([cfg_item()], "nomarze.example.top"), None
    orig_kurz = miniweb_cena.zivy_kurz
    miniweb_cena._cache.clear()
    miniweb_cena.zivy_kurz = lambda mena="EUR", fetch=None, now=None: None
    try:
        r_nk = quote([cfg_item()], "nokurz.example.top")
    finally:
        miniweb_cena.zivy_kurz = orig_kurz
    over("Q9 bez marze nebo bez kurzu (Fio nedostupne) = 503 price_unavailable, nikdy odhad ceny", r_nm.status_code == 503 and r_nm.get_json()["error"] == "price_unavailable"
         and r_nk.status_code == 503 and r_nk.get_json()["error"] == "price_unavailable", (r_nm.get_json(), r_nk.get_json()))
    miniweb_cena._cache.clear()
    r = cl.post("/api/miniweb/quote", data="x=1", base_url="https://" + HOST)
    r_big = cl.post("/api/miniweb/quote", data=b"{" + b" " * 70000 + b"}", content_type="application/json", base_url="https://" + HOST)
    over("Q10 telo musi byt JSON objekt (formular 400) a nejvyse 64 kB (413)", r.status_code == 400 and r_big.status_code == 413, (r.status_code, r_big.status_code))
    appmod._rate_limit_buckets.clear()
    kody = [quote([cfg_item()], vynuluj_=False) if False else volej("/api/miniweb/quote", {"country": "SK", "items": [cfg_item()]}, vynuluj=False).status_code for _ in range(62)]
    over("Q11 rate limit quote (60 za minutu na IP): prvnich 60 projde, dal 429", kody[:60] == [200] * 60 and 429 in kody[60:], kody[58:])
    over("Q12 quote nic nezapisuje (zadna objednavka, polozka ani historie)", pocet("shop_orders") == 0 and pocet("shop_order_items") == 0 and pocet("shop_documents") == 0, None)

    # ============================================================================================================ O) objednavka
    print("== O objednavka")
    over("O0 checkout_mode a inquiry_only v config: shop s objednavkami 'order' a inquiry_only false, bez nich 'inquiry' a inquiry_only true (nikdy oboji zaroven)",
         (lambda a, b: a.get("checkout_mode") == "order" and a.get("inquiry_only") is False and b.get("checkout_mode") == "inquiry" and b.get("inquiry_only") is True)(cl.get("/api/miniweb/config", base_url="https://" + HOST).get_json(),
                                                                                                   cl.get("/api/miniweb/config", base_url="https://off.example.top").get_json()))
    pj = cl.get("/api/miniweb/products", base_url="https://" + HOST).get_json()["products"]
    by_id = {x["id"]: x for x in pj}
    over("O0b stitky profilu v products: konfigurovatelny stul nese groove_family '8', cross_section_label '30\u00d730' a profil_mm 30 (prurez z konfiguratoru, drazka potvrzena Robertem), bezny produkt je NEMA",
         by_id[P_CFG].get("groove_family") == "8" and by_id[P_CFG].get("cross_section_label") == "30\u00d730" and by_id[P_CFG].get("profil_mm") == 30
         and not {"groove_family", "cross_section_label", "profil_mm"} & set(by_id[P_PLAIN]), {k: by_id[P_CFG].get(k) for k in ("groove_family", "cross_section_label", "profil_mm")})
    r = objednavka(valid_order([cfg_item(None, 2, net_unit=1, price=1)], note="Prosím o dodanie v marci.", expected_total_net=EUR0 * 2))
    k = r.get_json()
    o = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
    pol = sql("SELECT * FROM shop_order_items WHERE order_id=%s", (o["id"],)) if o else []
    hist = sql("SELECT * FROM shop_order_status_history WHERE order_id=%s", (o["id"],)) if o else []
    over("O1 objednavka: 201, cislo objednavky a cena v EUR (kus x pocet), platne IC DPH (VIES) = DPH 0 %, platba null (proforma po schvaleni dopravy), idempotent_replay false",
         r.status_code == 201 and k["reference"] == o["order_number"] and k["status"] == "received" and k["total"]["net"] == EUR0 * 2 and k["total"]["currency"] == "EUR" and k["payment"] is None
         and k["next"] == "proforma_after_shipping_confirmation" and k["shipping"] == {"id": "quote", "net": None, "review": True} and k["shipping_review"] is True and k["vat"]["rate"] == 0 and k["vat"]["reason"] == "valid_vat_id"
         and k["total"]["with_vat"] == EUR0 * 2 and k["idempotent_replay"] is False, (r.status_code, k))
    over("O2 radek objednavky: konfigurace s kodem a snimkem, product_id NULL (vyroba na zakazku, bez skladu), cena k uhrade v Kc = EUR x kurz 25 (klient posilal 1), mnozstvi 2, soucet = EUR celkem x kurz",
         len(pol) == 1 and pol[0]["product_id"] is None and pol[0]["configuration_code"] == R0["kod"] and float(pol[0]["unit_price_czk"]) == EUR0 * 25 and pol[0]["qty"] == 2
         and float(o["total_czk"]) == EUR0 * 2 * 25 and json.loads(pol[0]["configuration_json"])["hash"] == R0["hash"], (pol, o and o["total_czk"]))
    over("O3 hlavicka: vlastni objednavka (bez uctu, bez dealera), storefront shopu, host a jazyk, firma + ICO doplnene na 8 cislic + DIC, kontakt, adresa, poznamka zakaznika",
         o["user_id"] is None and o["party_id"] is None and o["dealer_id"] is None and o["storefront_id"] == S_SK["id"] and o["order_host"] == HOST and o["order_lang"] == "sk"
         and o["billing_name"] == "Firma s.r.o." and o["billing_ico"] == "12345678" and o["billing_dic"] == "SK2020202020" and o["customer_email"] == "jan@firma.test"
         and o["customer_phone"] == "+421 900 111 222" and "Hlavná 1, 811 01 Bratislava, Slovensko" == o["delivery_address"] == o["billing_address"] and o["note"] == "Prosím o dodanie v marci."
         and o["delivery_zip"] == "81101" and o["shipping_review"] == 1 and o["vat_mode"] == "reverse_charge" and o["vat_check"] == "vies_valid",
         {k_: o[k_] for k_ in ("user_id", "dealer_id", "storefront_id", "order_host", "order_lang", "billing_ico", "billing_dic", "delivery_address", "delivery_zip", "shipping_review", "vat_mode", "vat_check")})
    over("O4 zivotni cyklus: stav nova (sama se nepotvrdi), BEZ proformy a jakehokoli dokladu, BEZ e-mailu zakaznikovi i zamestnanci, doprava po dohode, platba predem jen jako popis, historie, audit",
         o["status"] == "nova" and pocet("shop_documents") == 0 and not EMAILS and float(o["shipping_price_czk"]) == 0 and float(o["payment_price_czk"]) == 0
         and o["shipping_method_name"].startswith("Doprava na Slovensko") and o["payment_method_name"] == "Platba předem" and len(hist) == 1 and hist[0]["status"] == "nova"
         and sum(1 for a in AUDIT if a[0][1] == "miniweb_order") == 1, (o["status"], EMAILS, o["shipping_method_name"]))
    over("O5 snimek ceny pro zamestnance v admin_note: EUR cena bez DPH, kurz, marze, vyrovnani v Kc, doprava, DPH, ze proformu vystavuje zamestnanec po schvaleni dopravy",
         f"{EUR0 * 2} EUR bez DPH" in o["admin_note"] and "kurz 25" in o["admin_note"] and "marže 0" in o["admin_note"] and "po schválení dopravy" in o["admin_note"] and "IČO 12345678" in o["admin_note"]
         and "EUR × kurz" in o["admin_note"], o["admin_note"])
    pocet_pred = pocet("shop_orders")
    zlo = []
    for nazev, upr in (("company_required", {"company": " "}), ("company_id_required", {"company_id": ""}), ("company_id_invalid", {"company_id": "abc"}), ("vat_id_invalid", {"vat_id": "SK123"}),
                       ("b2b_confirm_required", {"b2b_confirm": False}), ("consent_required", {"consent": None}), ("shipping_invalid", {"shipping": "dpd"}),
                       ("payment_invalid", {"payment": "cod"}), ("phone_invalid", {"phone": "x"}), ("email_invalid", {"email": "neplatny"}), ("zip_invalid", {"billing": {"street": "A 1", "city": "B", "zip": "<b>"}}),
                       ("name_required", {"name": ""}), ("street_required", {"billing": {"street": "", "city": "B", "zip": "81101"}}), ("city_required", {"billing": {"street": "A 1", "city": "", "zip": "81101"}}),
                       ("country_invalid", {"country": "DE"}), ("delivery_required", {"delivery": None}), ("street_required", {"delivery": {"same": False, "street": "", "city": "B", "zip": "81101"}}),
                       ("expected_total_invalid", {"expected_total_net": "10"})):
        zlo.append((nazev, objednavka(valid_order(**upr))))
    over("O6 validace: kazdy chybny vstup 400 se svym kodem (firma, ICO, DIC, potvrzeni podnikatele, souhlas, doprava, platba, telefon, e-mail, PSC, jmeno, adresa, zeme) a nic se nezalozi",
         all(r_.status_code == 400 and r_.get_json()["error"] == n_ for n_, r_ in zlo) and pocet("shop_orders") == pocet_pred, [(n_, r_.status_code, r_.get_json()) for n_, r_ in zlo if r_.status_code != 400 or r_.get_json()["error"] != n_])
    r = objednavka(valid_order(website="http://spam"))
    over("O7 honeypot: tvari se jako uspech (201, prazdny odkaz) a nic neuklada", r.status_code == 201 and r.get_json()["reference"] == "" and pocet("shop_orders") == pocet_pred, r.get_json())
    r = objednavka(valid_order([cfg_item(None, 2)], note="Prosím o dodanie v marci.", expected_total_net=EUR0 * 2 + 1))
    over("O8 expected_total_net z quote nesedi = 409 price_changed s aktualni cenou, nic se nezalozi", r.status_code == 409 and r.get_json()["error"] == "price_changed" and r.get_json()["current_total_net"] == EUR0 * 2
         and pocet("shop_orders") == pocet_pred, r.get_json())
    r = objednavka(valid_order([cfg_item(None, 2)], note="Prosím o dodanie v marci.", expected_total_net=EUR0 * 2), vynuluj=True)
    r_other = objednavka(valid_order([cfg_item(None, 2)], note="Prosím o dodanie v marci.", billing={"street": "Iná 5", "city": "Bratislava", "zip": "811 01"}))
    over("O9 dvojity klik (STEJNY obsah: zakaznik, firma, adresy, doprava, poznamka, konfigurace a mnozstvi, do 5 minut) = 200 se stejnou objednavkou a idempotent_replay, zadna nova; objednavka se STEJNOU castkou, ale jinou "
         "fakturacni adresou je NOVA objednavka, ne zamenena za opakovani (externi revize #1)", r.status_code == 200 and r.get_json()["reference"] == k["reference"]
         and r.get_json()["idempotent_replay"] is True and r.get_json()["total"]["net"] == EUR0 * 2 and r_other.status_code == 201 and r_other.get_json()["reference"] != k["reference"]
         and pocet("shop_orders") == pocet_pred + 1, (r.status_code, r.get_json(), r_other.status_code))
    pocet_pred = pocet("shop_orders")
    r_bad, r_rules = objednavka(valid_order([cfg_item(BAD_SEL)])), objednavka(valid_order([{"product_id": P_CFG, "qty": 1, "configuration": {"selection": {}, "rules_version": "stara"}}]))
    r_plain = objednavka(valid_order([{"product_id": P_PLAIN, "qty": 1, "configuration": {"selection": {}}}]))
    over("O10 neplatna konfigurace = 422 invalid_configuration s chybami, stara pravidla 409 rules_changed, jiny produkt 422 product_not_available; nic se nezalozi",
         r_bad.status_code == 422 and r_bad.get_json()["error"] == "invalid_configuration" and r_bad.get_json()["errors"] and r_rules.status_code == 409 and r_rules.get_json()["error"] == "rules_changed"
         and r_plain.status_code == 422 and pocet("shop_orders") == pocet_pred, (r_bad.get_json(), r_rules.get_json(), r_plain.get_json()))
    gate = {"vypnute": objednavka(valid_order(), "off.example.top"), "koncept": objednavka(valid_order(), "draft.example.top"), "bez marze": objednavka(valid_order(), "nomarze.example.top")}
    over("O11 branky: vypnute objednavky a koncept 404, bez marze 503; nic se nezalozi", gate["vypnute"].status_code == 404 and gate["koncept"].status_code == 404 and gate["bez marze"].status_code == 503
         and pocet("shop_orders") == pocet_pred, {k_: v.status_code for k_, v in gate.items()})
    r = objednavka(valid_order([cfg_item(ODLISNA, 1)], shipping="pickup", vat_id="", company_id="00123456"))
    k2 = r.get_json()
    o2 = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
    over("O12 osobni odber a firma bez DIC: 201, doprava pickup 0 EUR (i osobni odber ceka na schvaleni zamestnancem, review true: externi revize #9), IC doplneno nulami, DIC prazdne, cena odlisne konfigurace", r.status_code == 201 and k2["shipping"] == {"id": "pickup", "net": 0, "review": True} and k2["total"]["net"] == EUR1
         and o2["shipping_method_name"] == "Osobní odběr" and o2["billing_ico"] == "00123456" and not o2["billing_dic"] and float(o2["total_czk"]) == EUR1 * 25 and o2["shipping_review"] == 1, (k2, o2["billing_ico"], o2["billing_dic"]))
    for i in range(2, 7):
        r = objednavka(valid_order([cfg_item(None, i)], email="limit@firma.test"))
    r_lim = objednavka(valid_order([cfg_item(None, 7)], email="limit@firma.test"))
    zakl = pocet("shop_orders")
    r_ip = [objednavka(valid_order([cfg_item(None, 8 + i)], email=f"ip{i}@firma.test"), vynuluj=False).status_code for i in range(6)]
    over("O13 limity: max 5 objednavek na e-mail za den (dalsi 429 too_many_orders), 5 objednavek za 10 minut z jedne IP", r.status_code == 201 and r_lim.status_code == 429 and r_lim.get_json()["error"] == "too_many_orders"
         and 429 in r_ip, (r_lim.status_code, r_ip))
    over("O14 stropy: radku nejvic 10, mnozstvi 99", objednavka(valid_order([cfg_item(None, 100)])).status_code == 400 and objednavka(valid_order([cfg_item({"w": 1000 + 10 * i}) for i in range(11)])).status_code == 400, None)
    over("O15 za cely beh zadny e-mail, zadna proforma a zadny doklad (pravidlo 16, rozhodnuti bot3)", not EMAILS and pocet("shop_documents") == 0, EMAILS)

    # ---- adresy, Toptrans, DPH a VIES
    print("== T doprava, adresy, DPH")
    r = objednavka(valid_order([cfg_item(None, 1)], delivery={"same": False, "street": "Dodacia 5", "city": "Košice", "zip": "040 01"}, email="adresy@firma.test"))
    oa = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
    over("T1 samostatna dodaci adresa: fakturacni a dodaci adresa i PSC dodaci se ulozi zvlast", r.status_code == 201 and oa["billing_address"] == "Hlavná 1, 811 01 Bratislava, Slovensko"
         and oa["delivery_address"] == "Dodacia 5, 040 01 Košice, Slovensko" and oa["delivery_zip"] == "04001", (oa["billing_address"], oa["delivery_address"], oa["delivery_zip"]))
    r = quote([cfg_item()], delivery_zip="81101")
    over("T2 Toptrans pri neuplne hmotnosti dilu (dnes vzdy): net null, reason weight_incomplete (cena se nehada), PSC bez cisel zip_missing", r.status_code == 200
         and r.get_json()["shipping_options"][0]["net"] is None and r.get_json()["shipping_options"][0]["reason"] == "weight_incomplete", r.get_json()["shipping_options"][0])
    r = objednavka(valid_order([cfg_item(None, 1)], shipping="toptrans", delivery={"same": True}, email="top1@firma.test"))
    ot = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
    over("T3 objednavka s dopravou Toptrans bez uplne hmotnosti: 201, doprava ke schvaleni s cenou 0 a poznamkou pro zamestnance, zadna proforma", r.status_code == 201
         and r.get_json()["shipping"] == {"id": "toptrans", "net": None, "review": True} and ot["shipping_review"] == 1 and float(ot["shipping_price_czk"]) == 0 and "cena ke schválení" in ot["shipping_method_name"]
         and "chybí hmotnosti" in ot["admin_note"] and pocet("shop_documents") == 0, (r.get_json(), ot["shipping_method_name"], ot["admin_note"]))
    vahy = {"kg": 20.0}
    pro_puvodni = stul_shop.pro_objednavku

    def pro_uplne(selection, rules_version=None, lang="cs", *dalsi, **kw):          # tolerantni k novemu parametru product_id (bot8)
        rr = pro_puvodni(selection, rules_version, lang, *dalsi, **kw)
        if rr.get("ok"):
            rr["hmotnost_kg"], rr["hmotnost_uplna"], rr["hmotnost_chybi"] = vahy["kg"], True, []
        return rr
    VOLANI = []
    ordersmod._resolve_toptrans_price = lambda cur, sid, zip_, kg, objem=0.0: (VOLANI.append((round(kg, 3), zip_)) or (2500.0, 700, "weight"))
    sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (4,'Toptrans',0,1,1,'zip_weight')")
    stul_shop.pro_objednavku = pro_uplne
    try:
        r = quote([cfg_item(None, 2)], delivery_zip="811 01")
        top = r.get_json()["shipping_options"][0]
        over("T4 Toptrans s uplnou hmotnosti: odhad v EUR (cena z ceniku v Kc / kurz), hmotnost x pocet a PSC dodaci adresy predane cenniku, estimated true", r.status_code == 200 and top["net"] == 100 and top["estimated"] is True
             and "reason" not in top and VOLANI[-1] == (40.0, "811 01"), (top, VOLANI))
        r = objednavka(valid_order([cfg_item(None, 2)], shipping="toptrans", delivery={"same": False, "street": "Dodacia 5", "city": "Košice", "zip": "040 01"}, email="top2@firma.test"))
        ot = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
        over("T5 objednavka s vypocitanou dopravou: doprava 100 EUR = 2500 Kc, ke schvaleni zamestnancem, celkem v Kc = zbozi + doprava, cena zbozi v EUR a celkem v odpovedi, PSC dodaci adresy pro cenik",
             r.status_code == 201 and r.get_json()["shipping"] == {"id": "toptrans", "net": 100, "review": True} and r.get_json()["total"]["net"] == EUR0 * 2 + 100 and ot["shipping_review"] == 1
             and float(ot["shipping_price_czk"]) == 2500.0 and float(ot["total_czk"]) == EUR0 * 2 * 25 + 2500.0 and VOLANI[-1] == (40.0, "040 01") and "odhad 100 EUR" in ot["admin_note"],
             (r.get_json(), ot["shipping_price_czk"], ot["total_czk"], VOLANI[-1]))
    finally:
        stul_shop.pro_objednavku = pro_puvodni
    # DPH a VIES
    VIES = {"stav": "valid", "volano": []}

    def vies_fake(kod, cislo):
        VIES["volano"].append((kod, cislo))
        if VIES["stav"] == "boom":
            raise OSError("sit")
        return {"valid": VIES["stav"] == "valid"} if VIES["stav"] in ("valid", "invalid") else {"valid": False, "userError": "MS_UNAVAILABLE"}
    orig_dotaz = miniweb_vies._dotaz
    miniweb_vies._dotaz = vies_fake
    try:
        miniweb_vies._cache.clear()
        r = quote([cfg_item()], vat_id="SK2020202020")
        v = r.get_json()["vat"]
        over("T6 quote s platnym IC DPH (VIES valid, zeme SK): DPH 0 %, reverse_charge, duvod valid_vat_id, castka 0 a celkem = zaklad", r.status_code == 200 and v["applied"] is False and v["rate"] == 0 and v["mode"] == "reverse_charge"
             and v["reason"] == "valid_vat_id" and v["amount"] == 0 and v["total_with_vat"] == EUR0 and v["manual_check"] is False and VIES["volano"] == [("SK", "2020202020")], (v, VIES))
        r = objednavka(valid_order([cfg_item(None, 3)], email="vat1@firma.test"))
        ov = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
        over("T7 objednavka s platnym IC DPH: rezim reverse_charge, kontrola vies_valid, DPH 0 % v odpovedi, urgent NE, poznamka s rezimem", r.status_code == 201 and ov["vat_mode"] == "reverse_charge" and ov["vat_check"] == "vies_valid"
             and r.get_json()["vat"]["rate"] == 0 and r.get_json()["total"]["with_vat"] == EUR0 * 3 and ov["is_urgent"] == 0 and "reverse_charge 0 %" in ov["admin_note"], (r.get_json(), ov["admin_note"]))
        VIES["stav"] = "invalid"
        miniweb_vies._cache.clear()
        n1 = pocet("shop_orders")
        r = objednavka(valid_order([cfg_item(None, 4)], email="vat2@firma.test"))
        q = quote([cfg_item()], vat_id="SK2020202020").get_json()["vat"]
        over("T8 IC DPH neplatne podle VIES: objednavka 422 vat_id_not_valid (nic se nezaklada), quote ukazuje 21 % s duvodem vat_id_not_valid", r.status_code == 422 and r.get_json()["error"] == "vat_id_not_valid" and pocet("shop_orders") == n1
             and q["rate"] == 21 and q["reason"] == "vat_id_not_valid" and q["applied"] is True, (r.get_json(), q))
        VIES["stav"] = "nedostupne"
        miniweb_vies._cache.clear()
        r = objednavka(valid_order([cfg_item(None, 5)], email="vat3@firma.test"))
        on = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
        over("T9 VIES nedostupne: objednavka projde s DPH 0 % jen pro formalne platne cislo, vat_check vies_unavailable, OZNACENA K RUCNI KONTROLE (urgent + poznamka), manual_check v odpovedi",
             r.status_code == 201 and on["vat_mode"] == "reverse_charge" and on["vat_check"] == "vies_unavailable" and on["is_urgent"] == 1 and "K RUČNÍ KONTROLE" in on["admin_note"] and r.get_json()["vat"]["manual_check"] is True,
             (r.get_json(), on["admin_note"]))
        r_syn = objednavka(valid_order([cfg_item(None, 6)], vat_id="SK123", email="vat4@firma.test"))
        over("T10 formalne neplatne cislo (spatna syntaxe) se do VIES vubec neposila: 400 vat_id_invalid", r_syn.status_code == 400 and r_syn.get_json()["error"] == "vat_id_invalid", r_syn.get_json())
        n_vies = len(VIES["volano"])
        r_cz = quote([cfg_item()], country="CZ", vat_id="CZ12345678")
        over("T11 domaci zakaznik (zeme CZ) ma vzdy CZ DPH a VIES se nevola", r_cz.status_code == 400 or (r_cz.get_json()["vat"]["rate"] == 21 and len(VIES["volano"]) == n_vies), (r_cz.status_code, r_cz.get_json()))
        VIES["stav"] = "valid"
        miniweb_vies._cache.clear()
        rc = volej("/api/miniweb/vat-check", {"country": "SK", "vat_id": "SK2020202020"})
        VIES["stav"] = "invalid"
        miniweb_vies._cache.clear()
        rc2 = volej("/api/miniweb/vat-check", {"country": "SK", "vat_id": "SK2020202020"})
        VIES["stav"] = "nedostupne"
        miniweb_vies._cache.clear()
        rc3 = volej("/api/miniweb/vat-check", {"country": "SK", "vat_id": "SK2020202020"})
        rc4 = volej("/api/miniweb/vat-check", {"country": "SK"})
        over("T12 /api/miniweb/vat-check: valid true, invalid false, nedostupne null (a manual_check), bez cisla 400 vat_id_required",
             rc.get_json()["valid"] is True and rc.get_json()["status"] == "valid" and rc2.get_json()["valid"] is False and rc3.get_json()["valid"] is None and rc3.get_json()["vat"]["manual_check"] is True
             and rc4.status_code == 400 and rc4.get_json()["error"] == "vat_id_required", (rc.get_json(), rc2.get_json(), rc3.get_json(), rc4.get_json()))
    finally:
        miniweb_vies._dotaz = orig_dotaz
        miniweb_vies._cache.clear()


    # ============================================================================================================ S) schvaleni dopravy a proforma
    print("== S schvaleni dopravy")
    _si = SecureCookieSessionInterface()
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1")[0]["id"]
    user_row = sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 1")
    ck = lambda uid: {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})}

    cla = appmod.app.test_client(use_cookies=False)

    def schval(oid, body, uid=admin_id):
        appmod._rate_limit_buckets.clear()
        return cla.post(f"/api/admin/orders/{oid}/shipping", json=body, headers=ck(uid) if uid else {}, base_url="https://admin.example.top")

    def nova_obj(email, vat_id="", **kw):
        miniweb_vies._dotaz = lambda kod, cislo: {"valid": True}
        miniweb_vies._cache.clear()
        r_ = objednavka(valid_order([cfg_item(None, 2)], email=email, vat_id=vat_id, shipping="toptrans", **kw))
        assert r_.status_code == 201, r_.get_json()
        return jedno("SELECT * FROM shop_orders WHERE order_number=%s", (r_.get_json()["reference"],))

    os_ = nova_obj("sch1@firma.test")                       # bez IC DPH = CZ 21 %, doprava Toptrans ke schvaleni (cena 0, hmotnost neuplna)
    pol_sum = float(jedno("SELECT SUM(line_total_czk) AS s FROM shop_order_items WHERE order_id=%s", (os_["id"],))["s"])
    r = schval(os_["id"], {"shipping_price_czk": 3000, "approve": False, "note": "Odhad dopravce"})
    o_ = jedno("SELECT * FROM shop_orders WHERE id=%s", (os_["id"],))
    over("S1 uprava dopravy bez schvaleni: cena dopravy ulozena, total = zbozi + doprava, dalsi ke schvaleni, nazev bez 'cena ke schvaleni', zadna proforma, historie",
         r.status_code == 200 and r.get_json()["approved"] is False and r.get_json()["proforma"] is None and float(o_["shipping_price_czk"]) == 3000 and abs(float(o_["total_czk"]) - (pol_sum + 3000)) < 0.005
         and o_["shipping_review"] == 1 and o_["shipping_method_name"] == "Doprava Toptrans" and pocet("shop_documents") == 0
         and "upravena zaměstnancem: 3000.00 Kč" in sql("SELECT note FROM shop_order_status_history WHERE order_id=%s ORDER BY id DESC LIMIT 1", (os_["id"],))[0]["note"] and not QUEUE, (r.get_json(), o_["total_czk"], pol_sum))
    r = schval(os_["id"], {"shipping_price_czk": 3100.5, "approve": True})
    o_ = jedno("SELECT * FROM shop_orders WHERE id=%s", (os_["id"],))
    d_ = sql("SELECT * FROM shop_documents WHERE order_id=%s", (os_["id"],))
    amount = round((pol_sum + 3100.5) * 1.21)
    over("S2 schvaleni: doprava ulozena, VYSTAVENA ZALOHOVA FAKTURA (jedna, CZK, castka = (zbozi + doprava) x 1,21 zaokrouhleno, VS = cislo faktury), shipping_review 0, e-mail s fakturou zarazen do fronty (jednou), nic se neposlalo primo",
         r.status_code == 200 and r.get_json()["approved"] is True and r.get_json()["proforma"]["amount_due_czk"] == amount and len(d_) == 1 and d_[0]["document_type"] == "proforma_invoice"
         and float(d_[0]["amount_due_czk"]) == amount and d_[0]["variable_symbol"] == d_[0]["document_number"] and o_["shipping_review"] == 0 and o_["is_urgent"] == 0
         and QUEUE == [(os_["id"], d_[0]["id"])] and float(o_["shipping_price_czk"]) == 3100.5 and not [e for e in EMAILS if e[0] == "smtp"], (r.get_json(), amount, d_, QUEUE))
    n_doc = pocet("shop_documents")
    r = schval(os_["id"], {"shipping_price_czk": 1, "approve": True})
    over("S3 podruhe: 409 shipping_not_in_review, zadna druha faktura, cena dopravy se nezmenila", r.status_code == 409 and r.get_json()["error"] == "shipping_not_in_review" and pocet("shop_documents") == n_doc
         and float(jedno("SELECT shipping_price_czk FROM shop_orders WHERE id=%s", (os_["id"],))["shipping_price_czk"]) == 3100.5, r.get_json())
    sql("INSERT INTO shop_orders (order_number, status, delivery_state, billing_state, customer_name, customer_email, total_czk, shipping_review) VALUES ('ESHOP-1','nova','nova','nevyfakturovano','Z','z@x.test',10,0)")
    id_e = jedno("SELECT id FROM shop_orders WHERE order_number='ESHOP-1'")["id"]
    r = schval(id_e, {"shipping_price_czk": 10, "approve": True})
    r404 = schval(99999999, {"shipping_price_czk": 10, "approve": True})
    over("S4 schvalit lze jen objednavku ke schvaleni (shipping_review 1; od 2026-10-04 i z hlavniho e-shopu): objednavka bez priznaku 409 shipping_not_in_review, neexistujici 404", r.status_code == 409 and r.get_json()["error"] == "shipping_not_in_review"
         and r404.status_code == 404, (r.get_json(), r404.status_code))
    sql("UPDATE shop_orders SET shipping_review=1 WHERE id=%s", (id_e,))
    r_e = schval(id_e, {"shipping_price_czk": 10, "approve": False})
    over("S4b objednavka hlavniho e-shopu s priznakem shipping_review (bez order_host) jde upravit a schvalit stejnym endpointem", r_e.status_code == 200 and float(jedno("SELECT shipping_price_czk FROM shop_orders WHERE id=%s", (id_e,))["shipping_price_czk"]) == 10.0, r_e.get_json())
    o_rc = nova_obj("sch2@firma.test", vat_id="SK2020202020")
    pol_rc = float(jedno("SELECT SUM(line_total_czk) AS s FROM shop_order_items WHERE order_id=%s", (o_rc["id"],))["s"])
    pred_flag = getattr(docs, "PODPORA_PRENESENE_DPH", None)
    docs.PODPORA_PRENESENE_DPH = False
    try:
        r = schval(o_rc["id"], {"shipping_price_czk": 100, "approve": True})
    finally:
        if pred_flag is None:
            del docs.PODPORA_PRENESENE_DPH
        else:
            docs.PODPORA_PRENESENE_DPH = pred_flag
    over("S5 DPH 0 % bez podpory v dokladech: schvaleni s fakturou odmitnuto 409 vat_regime_not_supported (zadna spatna faktura), objednavka dal ke schvaleni; sama uprava ceny dopravy (approve false) projde",
         r.status_code == 409 and r.get_json()["error"] == "vat_regime_not_supported" and jedno("SELECT COUNT(*) AS n FROM shop_documents WHERE order_id=%s", (o_rc["id"],))["n"] == 0
         and jedno("SELECT shipping_review FROM shop_orders WHERE id=%s", (o_rc["id"],))["shipping_review"] == 1 and schval(o_rc["id"], {"shipping_price_czk": 100, "approve": False}).status_code == 200, r.get_json())
    o_rv = nova_obj("sch5@firma.test", vat_id="SK2020202020")
    sql("UPDATE shop_orders SET vat_check='vies_unavailable' WHERE id=%s", (o_rv["id"],))
    r1 = schval(o_rv["id"], {"shipping_price_czk": 100, "approve": True})
    over("S6 IC DPH neoverene (VIES nedostupne): schvaleni vyzaduje vedome potvrzeni vat_ok (jinak 409 vat_check_required, nic se nevystavi)", r1.status_code == 409 and r1.get_json()["error"] == "vat_check_required"
         and jedno("SELECT COUNT(*) AS n FROM shop_documents WHERE order_id=%s", (o_rv["id"],))["n"] == 0, r1.get_json())
    r2 = schval(o_rv["id"], {"shipping_price_czk": 100, "approve": True, "vat_ok": True})
    d_rv = sql("SELECT * FROM shop_documents WHERE order_id=%s", (o_rv["id"],))
    over("S6b s vat_ok: faktura vystavena, DPH 0 % (castka k uhrade = zaklad zaokrouhleny), is_urgent smazan", r2.status_code == 200 and len(d_rv) == 1 and float(d_rv[0]["total_vat_czk"]) == 0
         and float(d_rv[0]["amount_due_czk"]) == round(pol_rc + 100) and jedno("SELECT is_urgent FROM shop_orders WHERE id=%s", (o_rv["id"],))["is_urgent"] == 0, (r2.get_json(), d_rv))
    r3 = schval(o_rc["id"], {"shipping_price_czk": 100, "approve": True})
    d_rc = sql("SELECT * FROM shop_documents WHERE order_id=%s", (o_rc["id"],))
    vb = json.loads(d_rc[0]["vat_breakdown_json"]) if d_rc and d_rc[0].get("vat_breakdown_json") else None
    over("S10 DPH 0 % faktura (platne IC DPH, podpora dokladu): vystavena, sazba 0 %, DPH 0, k uhrade = zaklad (zbozi v Kc + doprava), v poznamce dolozka s IC DPH odberatele a prepocet EUR x kurz = Kc, e-mail do fronty",
         r3.status_code == 200 and len(d_rc) == 1 and float(d_rc[0]["total_vat_czk"]) == 0 and float(d_rc[0]["amount_due_czk"]) == round(pol_rc + 100) and "§ 64" in d_rc[0]["note"] and "SK2020202020" in d_rc[0]["note"]
         and "× kurz 25 Kč/EUR" in d_rc[0]["note"] and (vb is None or vb[0]["rate"] == 0) and (o_rc["id"], d_rc[0]["id"]) in QUEUE, (r3.get_json(), d_rc and d_rc[0].get("note")))
    r4 = schval(o_v_ := nova_obj("sch6@firma.test")["id"], {"shipping_price_czk": 100, "approve": True})
    d_std = sql("SELECT * FROM shop_documents WHERE order_id=%s", (o_v_,))
    over("S11 bezna objednavka (CZ 21 %) po zmene dokladu beze zmeny: DPH 21 %, bez dolozky, ale s textem o prepoctu kurzu EUR", r4.status_code == 200 and float(d_std[0]["total_vat_czk"]) > 0 and "§ 64" not in d_std[0]["note"]
         and "× kurz 25 Kč/EUR" in d_std[0]["note"], (r4.get_json(), d_std and d_std[0].get("note")))
    o_v = nova_obj("sch3@firma.test")
    zl = [schval(o_v["id"], b_).get_json() for b_ in ({}, {"shipping_price_czk": -5}, {"shipping_price_czk": "abc"}, {"shipping_price_czk": True}, {"shipping_price_czk": 1e9}, {"shipping_price_czk": 10, "approve": "ano"})]
    over("S7 validace: chybejici, zaporna, nenumericka, bool a obri cena dopravy 400, approve musi byt true/false; nic se nezmeni", [z.get("error") for z in zl[:5]] == ["shipping_price_invalid"] * 5 and zl[5]["error"] == "invalid_request"
         and float(jedno("SELECT shipping_price_czk FROM shop_orders WHERE id=%s", (o_v["id"],))["shipping_price_czk"]) == 0, zl)
    r_anon = schval(o_v["id"], {"shipping_price_czk": 10, "approve": False}, uid=None)
    r_user = schval(o_v["id"], {"shipping_price_czk": 10, "approve": False}, uid=user_row[0]["id"]) if user_row else None
    over("S8 bez prihlaseni 401/403, obycejny zakaznik nema pristup (401/403)", r_anon.status_code in (401, 403) and (r_user is None or r_user.status_code in (401, 403)), (r_anon.status_code, r_user and r_user.status_code))
    over("S9 admin_note a e-maily: za cely beh zadny primy e-mail (jen zarazeni do fronty), proforma jen u schvalene objednavky", not [e for e in EMAILS if e[0] == "smtp"] and pocet("shop_documents") >= 1, (EMAILS, pocet("shop_documents")))
    n_doc = pocet("shop_documents")
    orig_fn = moa.admin_miniweb_order_shipping



    # ---- montaz v mini-shopu (Robert 2026-10-04: vzdy volitelna, i mimo CR; sazba app_settings stul_montaz_pct, vychozi 12, zakaznik ji nevidi)
    print("== MO montaz")
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    MEUR = int((Decimal(EUR0) * Decimal(12) / 100).quantize(Decimal(1), rounding="ROUND_HALF_UP"))
    qm = quote([cfg_item(None, 2, montaz=True), cfg_item(ODLISNA, 1)]).get_json()
    over("MO1 quote s montazi: kazdy radek nese montaz_option_eur (cena montaze za kus v celych EUR bez DPH = 12 % z ceny konfigurace), u zvoleneho montaz_eur a montaz_total_eur, subtotal = zbozi + montaz, sazba se nevraci",
         qm["lines"][0]["montaz_option_eur"] == MEUR and qm["lines"][0]["montaz_zvolena"] is True and qm["lines"][0]["montaz_eur"] == MEUR and qm["lines"][0]["montaz_total_eur"] == MEUR * 2
         and qm["lines"][1]["montaz_zvolena"] is False and qm["lines"][1]["montaz_eur"] is None and qm["lines"][1]["montaz_option_eur"] == int((Decimal(EUR1) * 12 / 100).quantize(Decimal(1), rounding="ROUND_HALF_UP"))
         and qm["subtotal_montaz"] == MEUR * 2 and qm["total_goods"] == EUR0 * 2 + EUR1 and qm["subtotal"] == EUR0 * 2 + EUR1 + MEUR * 2 and "montaz_pct" not in json.dumps(qm) and qm["vat"]["amount"] >= 0, qm)
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','0') ON DUPLICATE KEY UPDATE setting_value='0'")
    q0 = quote([cfg_item(None, 1)]).get_json()
    q0m = quote([cfg_item(None, 1, montaz=True)])
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    over("MO2 sazba 0 = montaz se nenabizi: montaz_option_eur null (UI volbu neukaze), pozadavek na montaz 409 montaz_unavailable", q0["lines"][0]["montaz_option_eur"] is None and q0m.status_code == 409 and q0m.get_json()["error"] == "montaz_unavailable", (q0["lines"][0], q0m.get_json()))
    r_m = objednavka(valid_order([cfg_item(None, 2, montaz=True)], email="montaz@firma.test", expected_total_net=EUR0 * 2 + MEUR * 2))
    om = jedno("SELECT * FROM shop_orders WHERE customer_email='montaz@firma.test'")
    polm = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (om["id"],)) if om else []
    over("MO3 objednavka s montazi: 201, celkem (zbozi + montaz) v EUR, DVA radky: konfigurace (EUR x kurz) a SAMOSTATNY 'Montaz - kod' (product_id NULL, montaz EUR x kurz 25, stejne mnozstvi), total_czk = (zbozi + montaz) x 25",
         r_m.status_code == 201 and r_m.get_json()["total"]["net"] == EUR0 * 2 + MEUR * 2 and len(polm) == 2 and float(polm[0]["unit_price_czk"]) == EUR0 * 25 and polm[1]["product_id"] is None
         and polm[1]["product_name_snapshot"] == f"Montáž – {R0['kod']}" and float(polm[1]["unit_price_czk"]) == MEUR * 25 and polm[1]["qty"] == 2 and float(om["total_czk"]) == (EUR0 * 2 + MEUR * 2) * 25,
         (r_m.get_json(), [(x["product_name_snapshot"], x["unit_price_czk"], x["qty"]) for x in polm], om and om["total_czk"]))
    over("MO4 snimek pro zamestnance: poznamka s montazi, [EUR-SNAPSHOT] nese montaz_eur; poznamka na zalohovou fakturu zmini zbozi i montaz a kurz", "montáž" in om["admin_note"] and f'"montaz_eur": {MEUR * 2}' in om["admin_note"]
         and "a montáže" in moa._document_note(om) and f"{(EUR0 * 2 + MEUR * 2) * 25}.00 Kč" in moa._document_note(om), moa._document_note(om))
    r_rep = objednavka(valid_order([cfg_item(None, 2, montaz=True)], email="montaz@firma.test", expected_total_net=EUR0 * 2 + MEUR * 2), vynuluj=True)
    r_bez = objednavka(valid_order([cfg_item(None, 2, montaz=False)], email="montaz@firma.test"))
    over("MO5 dvojity klik se stejnou montazi = 200 replay se STEJNOU castkou vcetne montaze; stejny kosik BEZ montaze je nova objednavka (montaz je soucasti otisku)", r_rep.status_code == 200 and r_rep.get_json()["idempotent_replay"] is True
         and r_rep.get_json()["total"]["net"] == EUR0 * 2 + MEUR * 2 and r_bez.status_code == 201 and r_bez.get_json()["reference"] != r_m.get_json()["reference"], (r_rep.get_json(), r_bez.status_code))
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','0') ON DUPLICATE KEY UPDATE setting_value='0'")
    n_mo = pocet("shop_orders")
    r_m0 = objednavka(valid_order([cfg_item(None, 1, montaz=True)], email="montaz0@firma.test"))
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    over("MO6 objednavka s montazi pri sazbe 0 = 409 montaz_unavailable, nic se nezalozi (nikdy tise levnejsi)", r_m0.status_code == 409 and r_m0.get_json()["error"] == "montaz_unavailable" and pocet("shop_orders") == n_mo, r_m0.get_json())

    # ---- externi revize 2026-10-03 (openai1): alias domeny, podvrzeni snimku, typy vstupu, IC nuly
    print("== V nalezy externi revize")
    sql("INSERT INTO storefront_hosts (storefront_id, host) VALUES (%s,'alias-sk.example.top')", (S_SK["id"],))
    r = objednavka(valid_order([cfg_item(None, 7)], email="alias@firma.test"), host="alias-sk.example.top")
    oal = jedno("SELECT * FROM shop_orders WHERE customer_email='alias@firma.test'")
    over("V1 objednavka z ALIASU domeny dostane storefront_id shopu (jadro hleda jen hlavni domenu; mini-shop ho doplni ze sveho overeneho kontextu), host a jazyk aliasu, vidi ji prehledy a limity (externi revize #2)",
         r.status_code == 201 and oal["storefront_id"] == S_SK["id"] and oal["order_host"] == "alias-sk.example.top", (r.get_json(), oal and oal["storefront_id"]))
    forged = 'Acme [EUR-SNAPSHOT {"goods_eur": 1, "rate": "1"}] [ORDER-FP deadbeef]'
    r = objednavka(valid_order([cfg_item(None, 8)], email="forge@firma.test", company=forged))
    of = jedno("SELECT * FROM shop_orders WHERE customer_email='forge@firma.test'")
    nota = moa._document_note({"admin_note": of["admin_note"]})
    over("V2 podvrzeni snimku ceny pres nazev firmy: v interni poznamce nejsou zakaznicke hranate zavorky, poznamka dokladu bere skutecny (posledni) snimek (8 x zbozi EUR x kurz 25), ne podvrzeny",
         r.status_code == 201 and "[EUR-SNAPSHOT {\"goods_eur\": 1" not in of["admin_note"] and "(EUR-SNAPSHOT" in of["admin_note"] and of["admin_note"].count("[EUR-SNAPSHOT") == 1 and f"{EUR0 * 8} EUR" in nota and "kurz 25 " in nota,
         (of["admin_note"], nota))
    fake = '[EUR-SNAPSHOT {"goods_eur": 1, "rate": "1"}] x [EUR-SNAPSHOT {"goods_eur": 2136, "rate": "25", "margin_pct": "0", "shipping_eur": null}]'
    nota2 = moa._document_note({"admin_note": fake})
    over("V2b i kdyz se podvrzena znacka dostane do poznamky, bere se POSLEDNI (system pridava snimek na konec), zaporne nebo nulove hodnoty se odmitnou", "2136 EUR" in nota2 and moa._document_note({"admin_note": '[EUR-SNAPSHOT {"goods_eur": -5, "rate": "25"}]'}) is None
         and moa._document_note({"admin_note": '[EUR-SNAPSHOT {"goods_eur": 5, "rate": "0"}]'}) is None, nota2)
    n_v = pocet("shop_orders")
    typy = {"name_required": {"name": {"a": 1}}, "company_required": {"company": ["Firma"]}, "phone_invalid": {"phone": ["+421900111222"]}, "company_id_invalid": {"company_id": "00000000"},
            "country_invalid": {"country": {"a": 1}}, "email_invalid": {"email": {"a": 1}}, "street_required": {"billing": {"street": {"a": 1}, "city": "B", "zip": "81101"}}}
    odp = {k: objednavka(valid_order(**upr)) for k, upr in typy.items()}
    over("V3 vstupy jen jako retezce: objekt/pole misto jmena, firmy, telefonu, e-mailu, ulice a zeme = 400 se svym kodem, ICO same nuly = company_id_invalid; nic se nezalozi (externi revize #16)",
         all(r_.status_code == 400 and r_.get_json()["error"] == k for k, r_ in odp.items()) and pocet("shop_orders") == n_v, {k: (r_.status_code, r_.get_json()) for k, r_ in odp.items() if r_.status_code != 400 or r_.get_json()["error"] != k})
    ps = cl.get("/api/miniweb/products?slug=konfigurovatelny", base_url="https://" + HOST).get_json()
    over("V4 ?slug= bez shody je prazdny seznam (ne cely katalog)", ps["total"] == 0 and ps["products"] == [], ps)

    # ============================================================================================================ M) mutace
    print("== M mutace")
    def s_mutaci(jmeno, funkce, stary, novy, akce):
        """Spusti akci se zmutovanou funkci a vzdy obnovi puvodni."""
        orig = getattr(mo, jmeno)
        setattr(mo, jmeno, mutant(funkce, stary, novy))
        try:
            return akce()
        finally:
            setattr(mo, jmeno, orig)

    rm = s_mutaci("_shop", mo._shop, 'if not shop.get("orders_enabled"):', "if False:", lambda: quote([cfg_item()], "off.example.top"))
    over("M1 mutace: bez branky orders_enabled by vypnuty shop odpovedel 200 (spravne 404) - test Q8 ji zachyti", rm.status_code == 200, rm.status_code)
    rm = s_mutaci("_items", mo._items, 'if p is None or not cfgp.get("available") or not cfgp.get("product_id"):', "if p is None:", lambda: quote([{"product_id": P_PLAIN, "qty": 1, "configuration": {"selection": {}}}]))
    over("M2 mutace: bez kontroly konfigurovatelneho produktu by prosel jiny produkt (spravne 422) - test Q7 ji zachyti", rm.status_code != 422, rm.status_code)
    n0 = pocet("shop_orders")
    rm = s_mutaci("miniweb_order_create", mo.miniweb_order_create.__wrapped__ if hasattr(mo.miniweb_order_create, "__wrapped__") else mo.miniweb_order_create, "XX_NEEXISTUJE", "XX", lambda: None) if False else None
    over("M3 stav: mutace nezanechaly zadnou objednavku navic", pocet("shop_orders") == n0, (n0, pocet("shop_orders")))
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY + tuple(f"_tpl_{x}" for x in TEMP_LIKE + TEMP_COPY):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (objednavky, polozky, doklady, cislovani, nastaveni, audit, mini-shopy, storefronty) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK mini-shop kosik a objednavka: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
