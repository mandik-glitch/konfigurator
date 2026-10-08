#!/opt/konfigurator/api/venv/bin/python
"""Puvod objednavky (domena, jazyk), aliasy hostu a prirazeni mini-shopu dealerovi (bot5, 2026-10-02; navrh A-D schvalil bot3, pravidla Roberta v TASKS.md).

Skutecny kod (nebo kandidati DEALERS_PY, CAR_STOREFRONTS_PY, ORDERS_PY) nad DOCASNYMI tabulkami: shop_orders (+polozky, historie, citace), car_storefronts, storefront_hosts, storefront_dealers, dealers,
dealer_clicks, shop_products a spol., app_settings. Ostre tabulky se jen ctou, e-maily a audit se jen zachytavaji. Objednavky z e-shopu jedou PRES SKUTECNE POST /api/orders (hlavicka Host + session).

Cast A  rozpoznani storefrontu: hlavni host i alias (jeden storefront vic hostu), normalizace, koncept se nerozpozna, knihovna aliasu (pridat/odebrat/validace/duplicity), jazyk podle nadrazene domeny
Cast B  snimek puvodu: order_host a order_lang pri vzniku (primo funkce i skutecna objednavka), nemenny, nikdy nevyhodi vyjimku, hook v obou zakaznickych cestach, rucni objednavka ho nema
Cast C  atribuce: mini-shop s prirazenim rozhoduje i proti cookie z prokliku, bez prirazeni klik jako dosud, vlastni nakup/test/neaktivni dealer = objednavka nase BEZ navratu ke kliku, cas (platnost od-do)
Cast D  knihovna prirazeni (assign_storefront / end_assignment): nikdy zpetne, jedno prirazeni bez konce, planovany zacatek, nic se nemaze, stare objednavky se nemeni; schema (FK RESTRICT, unikatni klice)
Cast E  admin API storefrontu: lang, jazyk dedeny po nadrazene domene, aliasy v kontrole duplicit, mazani s historii (409), pole puvodu v admin serializaci objednavky
Cast F  mutace (chybne verze funkci MUSI selhat)
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_storefront.py   (kandidati: --setenv=DEALERS_PY=... --setenv=CAR_STOREFRONTS_PY=... --setenv=ORDERS_PY=...)
"""
import ast
import datetime
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KANDIDATI = {"dealers.py": os.environ.get("DEALERS_PY"), "car_storefronts.py": os.environ.get("CAR_STOREFRONTS_PY"), "orders.py": os.environ.get("ORDERS_PY")}
if any(KANDIDATI.values()):
    tmp = tempfile.mkdtemp(prefix="kand_storefront_")
    for jmeno, cesta in KANDIDATI.items():
        if cesta:
            shutil.copy(cesta, os.path.join(tmp, jmeno))
    sys.path.insert(0, tmp)
sys.path.insert(1 if any(KANDIDATI.values()) else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

for sekce in ("dealeri", "dealer_provize", "dealer_klice"):
    if sekce not in appmod.PERMISSION_SECTIONS:
        appmod.PERMISSION_SECTIONS = tuple(appmod.PERMISSION_SECTIONS) + (sekce,)
import dealers  # noqa: E402
import car_storefronts as cs  # noqa: E402
import orders as orders_mod  # noqa: E402

dealers.log_audit = lambda *a, **k: None
cs.log_audit = lambda *a, **k: None
EMAILS = []
orders_mod._send_order_emails_bg = lambda result: EMAILS.append(result)

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_orders", "shop_order_items", "shop_documents", "car_storefronts", "storefront_hosts", "storefront_dealers", "dealers", "dealer_clicks", "shop_products",
                      "app_settings", "app_users", "shop_customers", "shop_emails", "audit_log"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")
            out["seq_obj"] = int(cur.fetchone()["s"])
            cur.execute("SELECT GROUP_CONCAT(lang ORDER BY id) AS l FROM car_storefronts")
            out["jazyky_storefrontu"] = cur.fetchone()["l"]
            return out
    finally:
        c.close()


PRED_OSTRE = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "dealers", "dealer_rates", "dealer_keys", "dealer_domains",
             "dealer_clicks", "car_storefronts", "storefront_hosts", "storefront_dealers", "shop_products", "content_categories", "product_assemblies", "shop_product_images")
TEMP_COPY = ("shop_document_sequences", "shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


def jedno(q, params=None):
    r = sql(q, params)
    return r[0] if r else None


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
        cur.execute("DELETE FROM app_settings WHERE setting_key IN ('cart_enabled') OR setting_key LIKE 'dealer_%'")
    real.commit()
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('cart_enabled','1')")

    NOW = datetime.datetime.now().replace(microsecond=0)
    CAS = [NOW]
    dealers._now = lambda: CAS[0]
    DEN = datetime.timedelta(days=1)

    # ---- mini-shopy (docasne): hlavni e-shop nema radek, 7 storefrontu s ruznymi jazyky
    def storefront(name, host, status="live", lang="cs", kind="model"):
        sql("INSERT INTO car_storefronts (name, slug, primary_domain, status, lang, kind) VALUES (%s,%s,%s,%s,%s,%s)", (name, name.lower().replace(" ", "-"), host, status, lang, kind))
        return jedno("SELECT * FROM car_storefronts WHERE primary_domain=%s", (host,))

    S_BASE = storefront("Zaklad DE", "de-shop.example.de", lang="de")           # nase zakladni domena nemeckeho shopu
    S_DEAL = storefront("Dealer Alfa", "alfa.de-shop.example.de", lang="de", kind="dealer")    # subdomena dealera
    S_CZ = storefront("Cesky shop", "cz-shop.example.cz")                       # cs
    S_DRAFT = storefront("Koncept", "koncept.example.cz", status="draft", lang="en")
    S_BAD = storefront("Spatny jazyk", "spatny.example.cz", lang="xx1")
    HOST_MAIN = "hlavni-eshop.example.cz"                                       # neni v zadne tabulce = hlavni e-shop

    # ---- uzivatele, dealeri, produkt
    uzivatele = [r["id"] for r in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 3")]
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]

    def dealer(name, ref, **kw):
        d = {"ref_code": ref, "name": name, "status": "active", "order_path": "our", "default_commission_pct": 10.0, "contact_email": f"{ref}@dealer.example", "ico": "11111111"}
        d.update(kw)
        sql(f"INSERT INTO dealers ({', '.join(d)}) VALUES ({', '.join(['%s'] * len(d))})", list(d.values()))
        return jedno("SELECT * FROM dealers WHERE ref_code=%s", (ref,))

    DA = dealer("Alfa", "alfa000001", user_id=uzivatele[0], ico="11111111")
    DB = dealer("Beta", "beta000002", ico="22222222")
    DC = dealer("Gama (pozastaven)", "gama000003", status="suspended", ico="33333333")
    DD = dealer("Delta (cesta dealer)", "delt000004", order_path="dealer", ico="44444444")
    sql("INSERT INTO shop_products (sku, name, price_czk_placeholder, stock_qty, active, weight_g, unit) VALUES ('T-PROD','Testovaci dil',100.00,50,1,100,'ks')")
    PID = jedno("SELECT id FROM shop_products WHERE sku='T-PROD'")["id"]

    def prirazeni(storefront_id, dealer_id, od, do=None):
        sql("INSERT INTO storefront_dealers (storefront_id, dealer_id, valid_from, valid_to) VALUES (%s,%s,%s,%s)", (storefront_id, dealer_id, od, do))

    def klik(dealer_id, stari=datetime.timedelta(hours=1)):
        token = os.urandom(16).hex()
        sql("INSERT INTO dealer_clicks (dealer_id, token, landing, created_at) VALUES (%s,%s,'/',%s)", (dealer_id, token, datetime.datetime.now() - stari))
        return token, jedno("SELECT id FROM dealer_clicks WHERE token=%s", (token,))["id"]

    _si = SecureCookieSessionInterface()

    def cookie_hlavicka(uid=None, dlr=None):
        casti = []
        if uid is not None:
            casti.append("session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid}))
        if dlr:
            casti.append(f"dlr={dlr}")
        return "; ".join(casti)

    cl = appmod.app.test_client(use_cookies=False)          # cookie (session, dlr) posilam rucne hlavickou Cookie, klient je nesmi prepsat vlastnim jarem

    def objednej(host, uid, dlr=None, email=None, ico=None, test_email=None):
        """SKUTECNA zakaznicka objednavka POST /api/orders z daneho hostu (hlavicka Host) jako dany uzivatel, s cookie dlr (klik) nebo bez."""
        appmod._rate_limit_buckets.clear()
        body = {"items": [{"product_id": PID, "qty": 1}], "customer_name": "Jan Novak", "customer_email": email or f"zakaznik{os.urandom(3).hex()}@example.cz",
                "delivery_address": "Ulice 5, Praha", "delivery_zip": "11000", "billing_zip": "11000"}
        if ico:
            body["billing_ico"] = ico
        r = cl.post("/api/orders", json=body, base_url=f"http://{host}", headers={"Cookie": cookie_hlavicka(uid, dlr)})
        o = jedno("SELECT * FROM shop_orders WHERE id=%s", (r.get_json().get("id"),)) if r.status_code == 201 else None
        return r, o

    def radek_objednavky(storefront_id=None, email="x@example.cz", test=0, dealer_id=None):
        sql("INSERT INTO shop_orders (order_number, status, customer_name, customer_email, total_czk, storefront_id, is_test, dealer_id) VALUES (%s,'nova','Jan',%s,100,%s,%s,%s)",
            (f"T{os.urandom(4).hex()}", email, storefront_id, test, dealer_id))
        return jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")

    def kontext(host, fn):
        with appmod.app.test_request_context("/", base_url=f"http://{host}"), real.cursor() as cur:
            out = fn(cur)
            real.commit()                 # PRED opustenim kontextu pozadavku: jeho teardown spojeni vraci a odrolluje
        return out

    def objednavka_podle_id(oid):
        return jedno("SELECT * FROM shop_orders WHERE id=%s", (oid,))

    # ============================================================================================================ A) rozpoznani storefrontu, aliasy, jazyk
    print("== A rozpoznani storefrontu, aliasy hostu, jazyk")
    res = lambda host: kontext(host, lambda cur: cs.resolve_storefront(cur, host=host))          # noqa: E731
    over("A1 hlavni host i s velkymi pismeny, portem a www se rozpozna jako storefront; neznamy host (hlavni e-shop) = None", res("DE-SHOP.example.de:8443")["id"] == S_BASE["id"] and res("www.cz-shop.example.cz")["id"] == S_CZ["id"]
         and res(HOST_MAIN) is None, None)
    over("A2 koncept (status draft) se nerozpozna (storefront_id u objednavky by byl NULL)", res("koncept.example.cz") is None, res("koncept.example.cz"))
    ALIAS = "obchod.dealer-alfa.de"

    def pridej(host, sf=None, note=None):
        with real.cursor() as cur:
            try:
                out = cs.add_storefront_host(cur, (sf or S_DEAL)["id"], host, note=note, created_by=admin_id)
            finally:
                real.commit()
        return out

    a_id = pridej("Obchod.Dealer-Alfa.DE:443")
    over("A3 alias (vlastni domena dealera): ulozi se normalizovany (male pismena, bez portu), a stejny storefront se rozpozna z hlavniho hostu I z aliasu; objednavky maji tentyz storefront_id",
         jedno("SELECT host FROM storefront_hosts WHERE id=%s", (a_id,))["host"] == ALIAS and res(ALIAS)["id"] == res("alfa.de-shop.example.de")["id"] == S_DEAL["id"] and res("www." + ALIAS)["id"] == S_DEAL["id"], None)
    pridej("alias-koncept.example.cz", S_DRAFT)
    pridej("shop2.dealer-cz.cz", S_CZ)
    over("A4 alias koncepcniho storefrontu se nerozpozna, alias jineho storefrontu rozpozna svuj storefront a aliasy dvou storefrontu se nemichaji",
         res("alias-koncept.example.cz") is None and res("shop2.dealer-cz.cz")["id"] == S_CZ["id"] and res(ALIAS)["id"] == S_DEAL["id"], None)
    chyby = {}
    for nazev, host in (("wildcard", "*.dealer.cz"), ("mezera", "obchod dealer.cz"), ("IP adresa", "10.0.0.1"), ("bez TLD", "obchod"), ("cesta", "obchod.cz/shop"), ("prazdny", ""), ("localhost", "localhost"),
                        ("podtrzitko", "ob_chod.cz"), ("dlouhy stitek", "a" * 64 + ".cz"), ("None", None), ("pomlcka na zacatku", "-obchod.cz")):
        with real.cursor() as cur:
            try:
                cs.add_storefront_host(cur, S_DEAL["id"], host)
                chyby[nazev] = "PROSLO"
            except ValueError as e:
                chyby[nazev] = "ValueError"
            real.rollback()
    over("A5 neplatne hosty (wildcard, mezera, IP, bez TLD, cesta, prazdny, localhost, podtrzitko, 64znakovy stitek, None, pomlcka) se odmitnou ValueError", set(chyby.values()) == {"ValueError"}, chyby)
    dup = {}
    for nazev, host, sf in (("jako hlavni domena jineho storefrontu", "cz-shop.example.cz", S_DEAL), ("jako vlastni hlavni domena", "alfa.de-shop.example.de", S_DEAL), ("jako existujici alias", ALIAS, S_CZ),
                             ("s www", "www." + ALIAS, S_DEAL)):
        with real.cursor() as cur:
            try:
                cs.add_storefront_host(cur, sf["id"], host)
                dup[nazev] = "PROSLO"
            except ValueError:
                dup[nazev] = "ValueError"
            real.rollback()
    with real.cursor() as cur:
        try:
            cs.add_storefront_host(cur, 999999, "neexistuje.example.cz")
            dup["storefront neexistuje"] = "PROSLO"
        except ValueError:
            dup["storefront neexistuje"] = "ValueError"
        real.rollback()
    over("A6 duplicity: host uz pouzity jako hlavni domena (i vlastni) nebo alias jakehokoli storefrontu, i s www, a neexistujici storefront -> ValueError", set(dup.values()) == {"ValueError"}, dup)
    try:
        sql("INSERT INTO storefront_hosts (storefront_id, host) VALUES (%s,%s)", (S_CZ["id"], ALIAS))
        db_unikat = False
    except pymysql.err.IntegrityError:
        db_unikat = True
        real.rollback()
    over("A7 v samotne tabulce je host unikatni (druha vrstva ochrany pri souboji)", db_unikat, None)
    over("A8 storefront_hosts_of: hlavni host vzdy prvni, pak aliasy v poradi vzniku; neexistujici storefront = prazdny seznam", kontext(HOST_MAIN, lambda cur: cs.storefront_hosts_of(cur, S_DEAL["id"])) == ["alfa.de-shop.example.de", ALIAS]
         and kontext(HOST_MAIN, lambda cur: cs.storefront_hosts_of(cur, 999999)) == [], kontext(HOST_MAIN, lambda cur: cs.storefront_hosts_of(cur, S_DEAL["id"])))
    odebrano = kontext(HOST_MAIN, lambda cur: (cs.remove_storefront_host(cur, S_DEAL["id"], "www.OBCHOD.dealer-alfa.de:80"), cs.remove_storefront_host(cur, S_DEAL["id"], ALIAS),
                                                cs.remove_storefront_host(cur, S_DEAL["id"], "alfa.de-shop.example.de")))
    over("A9 odebrani aliasu (i zapsaneho jinak) funguje jednou, hlavni domenu odebrat nejde (neni v tabulce aliasu) a po odebrani se alias uz nerozpozna", odebrano == (True, False, False) and res(ALIAS) is None and res("alfa.de-shop.example.de") is not None, odebrano)
    pridej(ALIAS)
    over("A10 jazyk podle nadrazene domeny: subdomena nasi domene dedi jeji jazyk, nejdelsi pripona vyhraje, jina domena ani sama zakladni domena nededi",
         kontext(HOST_MAIN, lambda cur: (cs.inherited_lang(cur, "novy.de-shop.example.de"), cs.inherited_lang(cur, "x.alfa.de-shop.example.de"), cs.inherited_lang(cur, "de-shop.example.de"), cs.inherited_lang(cur, "novy.cz-shop.example.cz"),
                                         cs.inherited_lang(cur, "jina.example.com"), cs.inherited_lang(cur, "x.spatny.example.cz"))) == ("de", "de", None, "cs", None, None), None)
    over("A11 clean_lang: DE -> de, de_DE -> de-de, ' en ' -> en; neplatne (x, english, cislo, prazdne, None) -> None; clean_host totez pro hosty", (cs.clean_lang("DE"), cs.clean_lang("de_DE"), cs.clean_lang(" en ")) == ("de", "de-de", "en")
         and all(cs.clean_lang(x) is None for x in ("x", "english", "d3", "", None, "de-d")) and cs.clean_host("WWW.Obchod.Cz:80") == "obchod.cz" and cs.clean_host("*.x.cz") is None, None)

    # ============================================================================================================ B) snimek puvodu
    print("== B snimek puvodu objednavky")
    o1 = radek_objednavky(S_DEAL["id"])
    over("B1 record_order_origin z hlavniho hostu storefrontu (velka pismena, port, www): order_host normalizovany, order_lang podle DOMENY (storefront lang de)",
         kontext("WWW.Alfa.DE-shop.example.de:8443", lambda cur: cs.record_order_origin(cur, o1["id"])) is True and (lambda r: (r["order_host"], r["order_lang"]))(objednavka_podle_id(o1["id"])) == ("alfa.de-shop.example.de", "de"), objednavka_podle_id(o1["id"]))
    o2 = radek_objednavky(S_DEAL["id"])
    kontext(ALIAS, lambda cur: cs.record_order_origin(cur, o2["id"]))
    over("B2 z ALIASU: order_host je skutecny host (alias), order_lang jazyk storefrontu; storefront_id objednavky je tentyz jako u hlavniho hostu", (lambda r: (r["order_host"], r["order_lang"], r["storefront_id"]))(objednavka_podle_id(o2["id"])) == (ALIAS, "de", S_DEAL["id"]), objednavka_podle_id(o2["id"]))
    o3 = radek_objednavky(None)
    kontext(HOST_MAIN, lambda cur: cs.record_order_origin(cur, o3["id"]))
    o4 = radek_objednavky(None)
    kontext("koncept.example.cz", lambda cur: cs.record_order_origin(cur, o4["id"]))
    o5 = radek_objednavky(S_BAD["id"])
    kontext("spatny.example.cz", lambda cur: cs.record_order_origin(cur, o5["id"]))
    over("B3 hlavni e-shop (host neni v tabulkach) = order_lang cs a host zaznamenan; koncept a storefront s neplatnym jazykem v DB spadnou na cs (host zaznamenan)",
         (lambda a, b, c: ((a["order_host"], a["order_lang"]), (b["order_host"], b["order_lang"]), (c["order_host"], c["order_lang"])))(objednavka_podle_id(o3["id"]), objednavka_podle_id(o4["id"]), objednavka_podle_id(o5["id"]))
         == ((HOST_MAIN, "cs"), ("koncept.example.cz", "cs"), ("spatny.example.cz", "cs")), None)
    pred = objednavka_podle_id(o1["id"])
    druhy = kontext("jiny-host.example.cz", lambda cur: cs.record_order_origin(cur, o1["id"]))
    over("B4 snimek je NEMENNY: druhe zavolani z jineho hostu nic neprepise a vrati False", druhy is False and (lambda r: (r["order_host"], r["order_lang"]))(objednavka_podle_id(o1["id"])) == (pred["order_host"], pred["order_lang"]), None)

    class Rozbity:
        def execute(self, *a, **k):
            raise RuntimeError("DB chyba")

    appmod.app.logger.disabled = True            # simulovana chyba DB se loguje jako vyjimka, v testu to jen zahlcuje vystup
    with appmod.app.test_request_context("/", base_url="http://x.example.cz"):
        vysl_rozbity = cs.record_order_origin(Rozbity(), 1)
    appmod.app.logger.disabled = False
    over("B5 zapis puvodu NIKDY nevyhodi vyjimku (chyba DB = False, objednavka se nerozbije)", vysl_rozbity is False, vysl_rozbity)
    r_b, ob = objednej("alfa.de-shop.example.de", uzivatele[1])
    over("B6 SKUTECNA zakaznicka objednavka POST /api/orders z hostu storefrontu: 201, storefront_id z hostu, order_host a order_lang (de) zapsane hookem v orders_create",
         r_b.status_code == 201 and ob["storefront_id"] == S_DEAL["id"] and ob["order_host"] == "alfa.de-shop.example.de" and ob["order_lang"] == "de", (r_b.status_code, r_b.get_json(), ob and (ob["storefront_id"], ob["order_host"], ob["order_lang"])))
    r_c, oc = objednej(ALIAS, uzivatele[1])
    over("B7 totez z ALIASU: stejny storefront_id, order_host = alias, jazyk de", r_c.status_code == 201 and oc["storefront_id"] == S_DEAL["id"] and oc["order_host"] == ALIAS and oc["order_lang"] == "de", oc and (oc["storefront_id"], oc["order_host"]))
    r_d, od_ = objednej(HOST_MAIN, uzivatele[1])
    over("B8 z hlavniho e-shopu: storefront_id NULL, order_host = host, order_lang cs", r_d.status_code == 201 and od_["storefront_id"] is None and od_["order_host"] == HOST_MAIN and od_["order_lang"] == "cs", od_ and (od_["storefront_id"], od_["order_host"]))
    zdroj_orders = open(orders_mod.__file__, encoding="utf-8").read()
    t_ast = ast.parse(zdroj_orders)

    def vola(funkce, nazev):
        node = next(n for n in t_ast.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        return any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == nazev for n in ast.walk(node))

    over("B9 hook puvodu je v OBOU zakaznickych cestach (orders_create a objednavka z prijate online nabidky), v rucni objednavce (admin_orders_create) a v jadru objednavky NENI",
         vola("orders_create", "record_order_origin") and vola("create_order_from_scene_offer", "record_order_origin") and not vola("admin_orders_create", "record_order_origin")
         and not vola("_resolve_and_insert_order", "record_order_origin") and zdroj_orders.count("record_order_origin(") == 2, zdroj_orders.count("record_order_origin("))
    jadro_row = None
    with appmod.app.test_request_context("/", base_url="http://alfa.de-shop.example.de"), real.cursor() as cur:
        res_j = orders_mod._resolve_and_insert_order(cur, {"items": [{"product_id": PID, "qty": 1}], "customer_name": "Jan", "customer_email": "j@example.cz", "delivery_address": "A", "delivery_zip": "11000", "billing_zip": "11000"},
                                                      attribute_user_id=None, profile_user_id=None)
        real.commit()
        jadro_row = objednavka_podle_id(res_j["order_id"])
    over("B10 objednavka vytvorena PRIMO jadrem (jako rucni zadani adminem) puvod NEMA (NULL), storefront_id ano - rucni objednavka neni 'z domeny'", jadro_row["order_host"] is None and jadro_row["order_lang"] is None, jadro_row["order_host"])

    # ============================================================================================================ C) atribuce podle mini-shopu
    print("== C atribuce objednavky dealerovi podle mini-shopu")
    prirazeni(S_DEAL["id"], DA["id"], NOW - DEN)             # dealer Alfa ma mini-shop od vcera, bez konce
    pr_od = jedno("SELECT id FROM storefront_dealers WHERE storefront_id=%s", (S_DEAL["id"],))
    r1, oa = objednej("alfa.de-shop.example.de", uzivatele[1])
    over("C1 objednavka z mini-shopu s prirazenim: dealer_id = dealer mini-shopu, order_path 'our', dealer_source 'storefront', bez kliku (dealer_click_id NULL)",
         r1.status_code == 201 and oa["dealer_id"] == DA["id"] and oa["order_path"] == "our" and oa["dealer_source"] == "storefront" and oa["dealer_click_id"] is None, oa and (oa["dealer_id"], oa["order_path"], oa["dealer_source"]))
    r2, ob2 = objednej(ALIAS, uzivatele[1])
    over("C2 totez z ALIASU (vlastni domena dealera): stejny dealer a zdroj storefront, order_host = alias - alias nic neprepina", r2.status_code == 201 and ob2["dealer_id"] == DA["id"] and ob2["dealer_source"] == "storefront" and ob2["order_host"] == ALIAS, ob2 and ob2["dealer_id"])
    tok_b, klik_b = klik(DB["id"])
    r3, oc3 = objednej("alfa.de-shop.example.de", uzivatele[1], dlr=tok_b)
    over("C3 mini-shop s dealerem ROZHODUJE i proti cookie z prokliku JINEHO dealera (dealer Alfa, ne Beta, zdroj storefront)", r3.status_code == 201 and oc3["dealer_id"] == DA["id"] and oc3["dealer_source"] == "storefront" and oc3["dealer_click_id"] is None, oc3 and oc3["dealer_id"])
    r4, od4 = objednej("alfa.de-shop.example.de", uzivatele[0], dlr=tok_b)
    over("C4 vlastni nakup dealera (ucet dealera) v jeho mini-shopu: objednavka zustava NASE a NEPRIPISE se dealerovi z kliku (zadny navrat ke kliku)", r4.status_code == 201 and od4["dealer_id"] is None and od4["dealer_source"] is None, od4 and od4["dealer_id"])
    r5, od5 = objednej("alfa.de-shop.example.de", uzivatele[1], dlr=tok_b, email="alfa000001@dealer.example")
    r6, od6 = objednej("alfa.de-shop.example.de", uzivatele[1], dlr=tok_b, ico="11 11 11 11")
    over("C5 vlastni nakup podle e-mailu kontaktu dealera nebo jeho ICO (i s mezerami) - nase, bez navratu ke kliku", od5["dealer_id"] is None and od6["dealer_id"] is None, (od5["dealer_id"], od6["dealer_id"]))
    r7, od7 = objednej("cz-shop.example.cz", uzivatele[1], dlr=tok_b)
    over("C6 mini-shop BEZ prirazeni: rozhoduje klik jako dosud (dealer Beta, dealer_source 'click', dealer_click_id vyplnene)", od7["dealer_id"] == DB["id"] and od7["dealer_source"] == "click" and od7["dealer_click_id"] == klik_b, od7 and (od7["dealer_id"], od7["dealer_source"]))
    r8, od8 = objednej("cz-shop.example.cz", uzivatele[1])
    r9, od9 = objednej(HOST_MAIN, uzivatele[1], dlr=tok_b)
    r10, od10 = objednej(HOST_MAIN, uzivatele[1])
    over("C7 mini-shop bez prirazeni a bez kliku = nase (dealer_id NULL, zdroj NULL); hlavni e-shop s klikem = dealer z kliku ('click'); bez kliku nase",
         od8["dealer_id"] is None and od8["dealer_source"] is None and od9["dealer_id"] == DB["id"] and od9["dealer_source"] == "click" and od10["dealer_id"] is None, (od8["dealer_id"], od9["dealer_id"], od10["dealer_id"]))
    stary_tok, _stary_id = klik(DB["id"], stari=datetime.timedelta(days=31))
    r11, od11 = objednej("cz-shop.example.cz", uzivatele[1], dlr=stary_tok)
    over("C8 klik starsi nez 30 dni nic nepripise (chovani kliku beze zmeny)", od11["dealer_id"] is None, od11["dealer_id"])
    # dealer nepouzitelny / jina cesta / testovaci objednavka u mini-shopu s prirazenim
    prirazeni(S_CZ["id"], DC["id"], NOW - DEN)                # pozastaveny dealer
    r12, od12 = objednej("cz-shop.example.cz", uzivatele[1], dlr=tok_b)
    over("C9 mini-shop s prirazenim POZASTAVENEMU dealerovi: objednavka zustava nase a NEPRIPISE se dealerovi z kliku (mini-shop rozhoduje, i kdyz dealera nelze pripsat)", r12.status_code == 201 and od12["dealer_id"] is None, od12 and od12["dealer_id"])
    sql("UPDATE storefront_dealers SET valid_to=%s WHERE storefront_id=%s", (NOW - datetime.timedelta(hours=1), S_CZ["id"]))
    prirazeni(S_CZ["id"], DD["id"], NOW - datetime.timedelta(minutes=30))     # dealer s cestou 'dealer'
    r13, od13 = objednej("cz-shop.example.cz", uzivatele[1], dlr=tok_b)
    over("C10 mini-shop s prirazenim dealerovi s cestou 'dealer' (API): neprirazuje se (provize by se nepocitala), objednavka nase, bez navratu ke kliku", od13["dealer_id"] is None, od13["dealer_id"])
    o_test = radek_objednavky(S_DEAL["id"], test=1)
    over("C11 testovaci objednavka (is_test) se dealerovi nepripisuje ani u mini-shopu s prirazenim", kontext("alfa.de-shop.example.de", lambda cur: dealers.attach_attribution(cur, o_test["id"], {"id": uzivatele[1]})) is False and objednavka_podle_id(o_test["id"])["dealer_id"] is None, None)
    o_hotovy = radek_objednavky(S_DEAL["id"], dealer_id=DB["id"])
    over("C12 objednavka, ktera uz dealera ma, se nezmeni (idempotence) a funkce vrati False", kontext("alfa.de-shop.example.de", lambda cur: dealers.attach_attribution(cur, o_hotovy["id"], {"id": uzivatele[1]})) is False
         and objednavka_podle_id(o_hotovy["id"])["dealer_id"] == DB["id"], None)
    appmod.app.logger.disabled = True
    with appmod.app.test_request_context("/", base_url="http://alfa.de-shop.example.de"):
        vysl_roz = dealers.attach_attribution(Rozbity(), 1, None)
    appmod.app.logger.disabled = False
    over("C13 atribuce NIKDY nevyhodi vyjimku (chyba DB = False, objednavka se nerozbije)", vysl_roz is False, vysl_roz)
    # cas: platnost od-do, stare objednavky se nemeni
    over("C14 platnost: prirazeni v budoucnosti jeste nema vliv, prirazeni po vyprseni uz nema vliv (storefront_assignment k danemu okamziku)",
         (lambda: (kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_DEAL["id"], at=NOW)) is not None,
                   kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_DEAL["id"], at=NOW - 3 * DEN)) is None,
                   kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_CZ["id"], at=NOW - datetime.timedelta(hours=2)))["dealer_id"] == DC["id"],
                   kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_CZ["id"], at=NOW - datetime.timedelta(minutes=45))) is None,
                   kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_CZ["id"], at=NOW))["dealer_id"] == DD["id"]))() == (True, True, True, True, True), None)
    # stare objednavky se pri zmene prirazeni nemeni
    pred_dealeri = {r["id"]: r["dealer_id"] for r in sql("SELECT id, dealer_id FROM shop_orders")}

    # ============================================================================================================ D) knihovna prirazeni
    print("== D knihovna prirazeni (assign_storefront / end_assignment) a schema")
    S_NOVY = storefront("Novy shop", "novy.cz-shop.example.cz")
    S_PLAN = storefront("Planovany shop", "plan.cz-shop.example.cz")

    def assign(sf, dealer_id, od=None, note=None):
        with real.cursor() as cur:
            try:
                return cs_dealers_assign(cur, sf["id"], dealer_id, od, note)
            finally:
                real.commit()

    def cs_dealers_assign(cur, sf_id, dealer_id, od, note):
        return dealers.assign_storefront(cur, sf_id, dealer_id, valid_from=od, note=note, created_by=admin_id)

    def chyba_assign(sf_id, dealer_id, od=None):
        with real.cursor() as cur:
            try:
                dealers.assign_storefront(cur, sf_id, dealer_id, valid_from=od)
                real.rollback()
                return "PROSLO"
            except ValueError as e:
                real.rollback()
                return str(e)

    id1 = assign(S_NOVY, DA["id"], note="prvni")
    r1_ = jedno("SELECT * FROM storefront_dealers WHERE id=%s", (id1,))
    over("D1 prirazeni od ted: valid_from = ted, valid_to NULL, poznamka a kdo; dealer nema nova prava zpetne (objednavky pred prirazenim zustavaji nase)", r1_["valid_from"] == NOW and r1_["valid_to"] is None and r1_["note"] == "prvni" and r1_["created_by"] == admin_id, r1_)
    CAS[0] = NOW + datetime.timedelta(minutes=10)
    id2 = assign(S_NOVY, DB["id"])
    r1b, r2b = jedno("SELECT * FROM storefront_dealers WHERE id=%s", (id1,)), jedno("SELECT * FROM storefront_dealers WHERE id=%s", (id2,))
    over("D2 zmena dealera: dosavadni prirazeni se ZAVRE (valid_to = zacatek noveho), nove zalozi, historie zustava; v kazdem okamziku plati nejvyse jedno",
         r1b["valid_to"] == r2b["valid_from"] == CAS[0] and r2b["valid_to"] is None and sql("SELECT COUNT(*) AS n FROM storefront_dealers WHERE storefront_id=%s", (S_NOVY["id"],))[0]["n"] == 2
         and kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_NOVY["id"], at=NOW + datetime.timedelta(minutes=5)))["dealer_id"] == DA["id"]
         and kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_NOVY["id"], at=CAS[0] + datetime.timedelta(minutes=1)))["dealer_id"] == DB["id"], (r1b, r2b))
    over("D3 odmitnuto (ValueError): zpetny zacatek, neexistujici mini-shop a dealer, pozastaveny dealer, dealer s cestou 'dealer', stejny dealer znovu",
         chyba_assign(S_NOVY["id"], DC["id"]).startswith("Dealer musí být aktivní") and chyba_assign(S_NOVY["id"], DD["id"]).startswith("Dealer musí mít cestu") and chyba_assign(S_NOVY["id"], DB["id"]).startswith("Tento dealer už je")
         and chyba_assign(999999, DA["id"]).startswith("Mini-shop neexistuje") and chyba_assign(S_NOVY["id"], 999999).startswith("Dealer neexistuje") and "zpětně" in chyba_assign(S_NOVY["id"], DA["id"], CAS[0] - datetime.timedelta(hours=2)), None)
    S_TOL = storefront("Tolerance shop", "tol.cz-shop.example.cz")
    id_tol = assign(S_TOL, DA["id"], od=CAS[0] - datetime.timedelta(seconds=30))
    over("D4 zacatek v poslednich 60 sekundach se toleruje (rozdil hodin), o hodinu zpet uz ne", jedno("SELECT valid_from FROM storefront_dealers WHERE id=%s", (id_tol,))["valid_from"] == CAS[0] - datetime.timedelta(seconds=30)
         and "zpětně" in chyba_assign(S_PLAN["id"], DB["id"], CAS[0] - datetime.timedelta(hours=1)), None)
    # planovany zacatek
    assign(S_PLAN, DA["id"])
    budoucnost = CAS[0] + datetime.timedelta(hours=1)
    assign(S_PLAN, DB["id"], od=budoucnost)
    over("D5 planovany zacatek: dosavadni dealer plati DO nej, novy OD nej (storefront_assignment k ruznym okamzikum), konflikt s uz naplanovanym se odmitne",
         kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_PLAN["id"], at=CAS[0] + datetime.timedelta(minutes=30)))["dealer_id"] == DA["id"]
         and kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_PLAN["id"], at=budoucnost + datetime.timedelta(minutes=1)))["dealer_id"] == DB["id"]
         and "Naplánované" in chyba_assign(S_PLAN["id"], DA["id"], od=CAS[0] + datetime.timedelta(minutes=30)), None)
    try:
        sql("INSERT INTO storefront_dealers (storefront_id, dealer_id, valid_from) VALUES (%s,%s,%s)", (S_NOVY["id"], DA["id"], CAS[0]))
        druhy_otevreny = False
    except pymysql.err.IntegrityError:
        druhy_otevreny = True
        real.rollback()
    over("D6 databaze sama nepusti DRUHE prirazeni bez konce na stejny mini-shop (unikatni klic nad generovanym sloupcem)", druhy_otevreny, None)
    with real.cursor() as cur:
        konec = dealers.end_assignment(cur, S_NOVY["id"])
        druhy_konec = dealers.end_assignment(cur, S_NOVY["id"])
        real.commit()
    r2c = jedno("SELECT * FROM storefront_dealers WHERE id=%s", (id2,))
    over("D7 end_assignment: nastavi konec (valid_to = ted), podruhe False (nic aktivniho), po konci mini-shop zadneho dealera nema a nove objednavky jsou nase", konec is True and druhy_konec is False and r2c["valid_to"] == CAS[0]
         and kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_NOVY["id"], at=CAS[0] + datetime.timedelta(minutes=1))) is None, r2c)
    with real.cursor() as cur:
        zruseno = dealers.end_assignment(cur, S_PLAN["id"])           # posledni prirazeni bez konce je NAPLANOVANE (dealer Beta od "budoucnost") = zruseni
        real.commit()
    plan_radky = sql("SELECT dealer_id, valid_from, valid_to FROM storefront_dealers WHERE storefront_id=%s ORDER BY id", (S_PLAN["id"],))
    over("D8 zruseni NAPLANOVANE zmeny dealera: planovane prirazeni se zneplatni (konec = zacatek, nic nepripise) a puvodni dealer Alfa POKRACUJE dal (jeho prirazeni se znovu otevre), ne aby po zruseni skoncilo",
         zruseno is True and plan_radky[1]["valid_to"] == plan_radky[1]["valid_from"] and plan_radky[0]["valid_to"] is None
         and kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_PLAN["id"], at=budoucnost + datetime.timedelta(hours=1)))["dealer_id"] == DA["id"], plan_radky)
    with real.cursor() as cur:
        konec_a = dealers.end_assignment(cur, S_PLAN["id"])
        druhy_konec_a = dealers.end_assignment(cur, S_PLAN["id"])
        real.commit()
    over("D8b po zruseni je dalsi end_assignment uz skutecne ukonceni puvodniho prirazeni (konec = ted), potom nic aktivniho", konec_a is True and druhy_konec_a is False
         and jedno("SELECT valid_to FROM storefront_dealers WHERE id=%s", (jedno("SELECT id FROM storefront_dealers WHERE storefront_id=%s ORDER BY id LIMIT 1", (S_PLAN["id"],))["id"],))["valid_to"] == CAS[0], None)
    with real.cursor() as cur:
        try:
            dealers.end_assignment(cur, S_NOVY["id"], valid_to=CAS[0] - datetime.timedelta(hours=1))
            zpetne_konec = "PROSLO"
        except ValueError:
            zpetne_konec = "ValueError"
        real.rollback()
    over("D9 ukonceni zpetne (valid_to v minulosti) -> ValueError", zpetne_konec == "ValueError", zpetne_konec)
    po_dealeri = {r["id"]: r["dealer_id"] for r in sql("SELECT id, dealer_id FROM shop_orders") if r["id"] in pred_dealeri}
    over("D10 STARE OBJEDNAVKY se zadnou zmenou prirazeni nemeni (dealer_id vsech drive vzniklych objednavek zustal)", po_dealeri == pred_dealeri, None)
    zdroj_dealers = open(dealers.__file__, encoding="utf-8").read()
    t_d = ast.parse(zdroj_dealers)
    nove_funkce = [n for n in t_d.body if isinstance(n, ast.FunctionDef) and n.name in ("storefront_assignment", "storefront_attribution", "attach_attribution", "assign_storefront", "end_assignment", "_own_purchase")]
    zdroj_nove = "\n".join(ast.get_source_segment(zdroj_dealers, n) for n in nove_funkce)
    over("D11 nic se nemaze: v novem kodu (atribuce, prirazeni) neni DELETE/DROP/TRUNCATE a nikde se zpetne neprepisuje dealer_id existujici objednavky (UPDATE jen s podminkou dealer_id IS NULL)",
         len(nove_funkce) == 6 and not re.search(r"DELETE\s+FROM|DROP\s+TABLE|TRUNCATE", zdroj_nove, re.I) and "WHERE id=%s AND dealer_id IS NULL" in zdroj_nove, len(nove_funkce))
    c = ostre()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT constraint_name AS n, delete_rule AS d FROM information_schema.referential_constraints WHERE constraint_schema=DATABASE() AND constraint_name IN "
                        "('fk_storefront_dealers_storefront','fk_storefront_dealers_dealer','fk_storefront_hosts_storefront')")
            fk = {(r.get("n") or r.get("CONSTRAINT_NAME")): (r.get("d") or r.get("DELETE_RULE")) for r in cur.fetchall()}
            cur.execute("SELECT index_name AS i, non_unique AS u FROM information_schema.statistics WHERE table_schema=DATABASE() AND index_name IN ('uq_storefront_dealers_active','uq_storefront_hosts_host') GROUP BY index_name, non_unique")
            uq = {(r.get("i") or r.get("INDEX_NAME")): (r.get("u") if r.get("u") is not None else r.get("NON_UNIQUE")) for r in cur.fetchall()}
    finally:
        c.close()
    over("D12 schema (zive tabulky): cizi klice vsude RESTRICT (nic se nemaze) a unikatni klice na jedno aktivni prirazeni a na host aliasu", fk == {"fk_storefront_dealers_storefront": "RESTRICT", "fk_storefront_dealers_dealer": "RESTRICT", "fk_storefront_hosts_storefront": "RESTRICT"}
         and uq == {"uq_storefront_dealers_active": 0, "uq_storefront_hosts_host": 0}, (fk, uq))

    # ============================================================================================================ E) admin API storefrontu a serializace
    print("== E admin API storefrontu (lang, aliasy, mazani) a admin serializace objednavky")

    def admin(metoda, cesta, body=None):
        return getattr(cl, metoda)(cesta, json=body, headers={"Cookie": cookie_hlavicka(admin_id)}) if body is not None else getattr(cl, metoda)(cesta, headers={"Cookie": cookie_hlavicka(admin_id)})

    r_e1 = admin("post", "/api/admin/storefronts", {"name": "Dealer Beta DE", "primary_domain": "beta.de-shop.example.de"})
    id_e1 = r_e1.get_json().get("id")
    r_e2 = admin("post", "/api/admin/storefronts", {"name": "Cizi domena", "primary_domain": "nezavisla.example.org"})
    r_e3 = admin("post", "/api/admin/storefronts", {"name": "Anglicky", "primary_domain": "en.example.org", "lang": "EN"})
    r_e4 = admin("post", "/api/admin/storefronts", {"name": "Spatny", "primary_domain": "spatny2.example.org", "lang": "x1"})
    r_e5 = admin("post", "/api/admin/storefronts", {"name": "Duplicita alias", "primary_domain": ALIAS})
    langy = {r["primary_domain"]: r["lang"] for r in sql("SELECT primary_domain, lang FROM car_storefronts WHERE primary_domain IN ('beta.de-shop.example.de','nezavisla.example.org','en.example.org')")}
    over("E1 vytvoreni mini-shopu: subdomena nasi domene dedi jeji jazyk (de), nezavisla domena dostane cs, vyslovne lang EN se ulozi jako en, neplatny jazyk 400, domena shodna s aliasem 409",
         r_e1.status_code == 201 and langy == {"beta.de-shop.example.de": "de", "nezavisla.example.org": "cs", "en.example.org": "en"} and r_e4.status_code == 400 and r_e5.status_code == 409 and r_e2.status_code == 201, (langy, r_e4.status_code, r_e5.status_code))
    r_g = admin("get", f"/api/admin/storefronts/{id_e1}")
    over("E2 detail i seznam mini-shopu nesou lang", r_g.status_code == 200 and r_g.get_json()["lang"] == "de" and all("lang" in s for s in admin("get", "/api/admin/storefronts").get_json()["storefronts"]), r_g.get_json())
    r_u1 = admin("put", f"/api/admin/storefronts/{id_e1}", {"lang": "De_AT"})
    r_u2 = admin("put", f"/api/admin/storefronts/{id_e1}", {"lang": "123"})
    r_u3 = admin("put", f"/api/admin/storefronts/{id_e1}", {"primary_domain": ALIAS})
    r_u4 = admin("put", f"/api/admin/storefronts/{S_DEAL['id']}", {"primary_domain": "alfa.de-shop.example.de", "name": "Dealer Alfa"})
    over("E3 uprava: lang se normalizuje (de-at), neplatny 400, zmena hlavni domeny na host, ktery je aliasem, 409, beze zmeny domeny OK",
         r_u1.status_code == 200 and jedno("SELECT lang FROM car_storefronts WHERE id=%s", (id_e1,))["lang"] == "de-at" and r_u2.status_code == 400 and r_u3.status_code == 409 and r_u4.status_code == 200, (r_u1.status_code, r_u2.status_code, r_u3.status_code, r_u4.status_code))
    over("E4 neprihlaseny 401 a uzivatel bez opravneni nemuze menit jazyk mini-shopu", cl.put(f"/api/admin/storefronts/{id_e1}", json={"lang": "en"}).status_code == 401
         and cl.put(f"/api/admin/storefronts/{id_e1}", json={"lang": "en"}, headers={"Cookie": cookie_hlavicka(uzivatele[1])}).status_code in (401, 403), None)

    class ProxyKurzor:
        def __init__(self, k):
            self.k = k

        def execute(self, q, *a, **kw):
            if q.lstrip().upper().startswith("DELETE FROM CAR_STOREFRONTS"):
                raise pymysql.err.IntegrityError(1451, "Cannot delete or update a parent row")
            return self.k.execute(q, *a, **kw)

        def __getattr__(self, n):
            return getattr(self.k, n)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return self.k.__exit__(*a)

    class ProxySpojeni:
        def __init__(self, c):
            self.c = c

        def cursor(self, *a, **kw):
            return ProxyKurzor(self.c.cursor(*a, **kw))

        def __getattr__(self, n):
            return getattr(self.c, n)

    puvodni_get_conn = cs.get_conn
    cs.get_conn = lambda: ProxySpojeni(puvodni_get_conn())
    try:
        r_del = admin("delete", f"/api/admin/storefronts/{S_DEAL['id']}")
    finally:
        cs.get_conn = puvodni_get_conn
    over("E5 smazani mini-shopu s aliasy nebo historii prirazeni dealerovi (FK RESTRICT): srozumitelna odpoved 409 misto 500, nic se nesmaze", r_del.status_code == 409 and "smazat nejde" in r_del.get_json()["error"]
         and jedno("SELECT id FROM car_storefronts WHERE id=%s", (S_DEAL["id"],)) is not None, (r_del.status_code, r_del.get_json()))
    r_del2 = admin("delete", f"/api/admin/storefronts/{id_e1}")
    over("E6 mini-shop bez aliasu a historie se smazat da (200) - bezne chovani beze zmeny", r_del2.status_code == 200 and jedno("SELECT id FROM car_storefronts WHERE id=%s", (id_e1,)) is None, r_del2.get_json())
    row_ser = jedno("SELECT * FROM shop_orders WHERE id=%s", (oa["id"],))
    ser_admin, ser_zak = orders_mod._serialize_order(row_ser), orders_mod._serialize_order_for_customer(row_ser)
    over("F1 admin serializace objednavky nese storefront_id, order_host, order_lang a dealer_source; zakaznicka serializace nic z toho nema",
         (ser_admin["storefront_id"], ser_admin["order_host"], ser_admin["order_lang"], ser_admin["dealer_source"]) == (S_DEAL["id"], "alfa.de-shop.example.de", "de", "storefront")
         and not ({"storefront_id", "order_host", "order_lang", "dealer_source"} & set(ser_zak)), ser_admin.get("order_host"))

    # ============================================================================================================ F) mutace
    print("== F mutace (chybne verze MUSI selhat)")
    zd_cs = open(cs.__file__, encoding="utf-8").read()

    def mutant(zdroj, modul, funkce, stare, nove):
        t_ = ast.parse(zdroj)
        node = next(n for n in t_.body if isinstance(n, ast.FunctionDef) and n.name == funkce)
        src = ast.get_source_segment(zdroj, node)
        assert src.count(stare) == 1, f"{funkce}: '{stare}' nalezeno {src.count(stare)}x"
        ns = dict(vars(modul))
        exec(src.replace(stare, nove), ns)
        return ns[funkce]

    o_m1 = radek_objednavky(S_DEAL["id"])
    tok_m, klik_m = klik(DB["id"])
    m1 = mutant(zdroj_dealers, dealers, "attach_attribution", 'if o["storefront_id"]:', "if False:")
    with appmod.app.test_request_context("/", base_url="http://alfa.de-shop.example.de", headers={"Cookie": f"dlr={tok_m}"}), real.cursor() as cur:
        spr = dealers.attach_attribution(cur, o_m1["id"], {"id": uzivatele[1]})
        real.commit()
    o_m1b = radek_objednavky(S_DEAL["id"])
    with appmod.app.test_request_context("/", base_url="http://alfa.de-shop.example.de", headers={"Cookie": f"dlr={tok_m}"}), real.cursor() as cur:
        chyb = m1(cur, o_m1b["id"], {"id": uzivatele[1]})
        real.commit()
    over("M1 mutace: bez rozhodovani podle mini-shopu by klik jineho dealera prebil prirazeni (spravne Alfa, mutant Beta) - testy C3 a C4 ji zachyti",
         spr is True and objednavka_podle_id(o_m1["id"])["dealer_id"] == DA["id"] and chyb is True and objednavka_podle_id(o_m1b["id"])["dealer_id"] == DB["id"], (objednavka_podle_id(o_m1["id"])["dealer_id"], objednavka_podle_id(o_m1b["id"])["dealer_id"]))
    m2 = mutant(zdroj_dealers, dealers, "storefront_assignment", "(valid_to IS NULL OR valid_to > %s)", "(valid_to IS NULL OR valid_to > %s OR 1=1)")
    try:
        ukonceno = kontext(HOST_MAIN, lambda cur: m2(cur, S_NOVY["id"], at=CAS[0] + datetime.timedelta(minutes=1)))
    except Exception as e:
        ukonceno = repr(e)
    over("M2 mutace: bez podminky konce platnosti by skoncene prirazeni dal pripisovalo objednavky (spravne None) - test D7 ji zachyti", kontext(HOST_MAIN, lambda cur: dealers.storefront_assignment(cur, S_NOVY["id"], at=CAS[0] + datetime.timedelta(minutes=1))) is None
         and isinstance(ukonceno, dict), ukonceno)
    m3 = mutant(zd_cs, cs, "record_order_origin", " AND order_host IS NULL", "")
    o_m3 = radek_objednavky(None)
    kontext("prvni.example.cz", lambda cur: cs.record_order_origin(cur, o_m3["id"]))
    kontext("druhy.example.cz", lambda cur: m3(cur, o_m3["id"]))
    over("M3 mutace: bez podminky 'order_host IS NULL' by se snimek puvodu prepsal druhym zavolanim (test B4 ji zachyti)", objednavka_podle_id(o_m3["id"])["order_host"] == "druhy.example.cz", objednavka_podle_id(o_m3["id"])["order_host"])
    m4 = mutant(zd_cs, cs, "resolve_storefront", "WHERE h.host=%s AND s.status='live'\"", "WHERE h.host=%s AND s.status='live' AND 1=0\"")
    with appmod.app.test_request_context("/", base_url="http://x.example.cz"), real.cursor() as cur:
        spravne_a, mutant_a = cs.resolve_storefront(cur, host=ALIAS), m4(cur, host=ALIAS)
    over("M4 mutace: bez rozpoznani aliasu by objednavka z vlastni domeny dealera ztratila mini-shop (spravne najde storefront, mutant None) - test A3 ji zachyti", spravne_a is not None and spravne_a["id"] == S_DEAL["id"] and mutant_a is None, (spravne_a and spravne_a["id"], mutant_a))
    m5 = mutant(zdroj_dealers, dealers, "assign_storefront", "if valid_from < now - datetime.timedelta(seconds=60):", "if False:")
    S_RETRO = storefront("Retro shop", "retro.cz-shop.example.cz")
    with real.cursor() as cur:
        try:
            m5(cur, S_RETRO["id"], DA["id"], valid_from=CAS[0] - datetime.timedelta(days=30))
            zpetne_ok = True
        except Exception as e:
            zpetne_ok = repr(e)
        real.commit()
    over("M5 mutace: bez kontroly by sel dealerovi nastavit zacatek ZPETNE (30 dni v minulosti) - spravna verze to odmita (test D3)", zpetne_ok is True and "zpětně" in chyba_assign(S_RETRO["id"], DA["id"], CAS[0] - datetime.timedelta(days=30)), zpetne_ok)
    m6 = mutant(zdroj_dealers, dealers, "storefront_attribution", "return True, None\n    return True, {", "return False, None\n    return True, {")
    o_m6 = radek_objednavky(S_DEAL["id"], email="alfa000001@dealer.example")
    spravne_m6 = kontext("alfa.de-shop.example.de", lambda cur: dealers.storefront_attribution(cur, S_DEAL["id"], {"id": uzivatele[1]}, "alfa000001@dealer.example", False, None))
    mutant_m6 = kontext("alfa.de-shop.example.de", lambda cur: m6(cur, S_DEAL["id"], {"id": uzivatele[1]}, "alfa000001@dealer.example", False, None))
    over("M6 mutace: kdyby vlastni nakup u mini-shopu vracel 'nerozhodl', spadlo by se na klik (spravne (True, None), mutant (False, None)) - test C4 ji zachyti", spravne_m6 == (True, None) and mutant_m6 == (False, None), (spravne_m6, mutant_m6))
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY + tuple(f"_tpl_{x}" for x in TEMP_LIKE + TEMP_COPY):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (objednavky, polozky, doklady, mini-shopy, aliasy, prirazeni, dealeri, kliky, produkty, nastaveni, uzivatele, zakaznici, e-maily, audit, citace, jazyky mini-shopu) jsou po testu beze zmeny", po == PRED_OSTRE, (PRED_OSTRE, po))
ok = sum(vysl)
print(f"\nVYSLEDEK puvod objednavky, aliasy hostu a prirazeni mini-shopu: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
