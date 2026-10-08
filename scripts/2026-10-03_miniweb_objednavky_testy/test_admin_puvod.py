#!/opt/konfigurator/api/venv/bin/python
"""Admin prehled objednavek: puvod (mini-shop host + jazyk, hlavni e-shop), filtr podle puvodu a podle 'doprava ke schvaleni', seznam puvodu (bot5, 2026-10-03; patch orders.py.patch).
Skutecna routa GET /api/admin/orders pres test client nad DOCASNYMI tabulkami; kandidat ORDERS_PY (jinak zivy soubor, kdyz uz patch obsahuje, jinak kopie s patchem ze sady).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-03_miniweb_objednavky_testy/test_admin_puvod.py"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(HERE, "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_adm_puvod_")
os.makedirs(os.path.join(tmp, "api"))
if os.environ.get("ORDERS_PY"):
    shutil.copy(os.environ["ORDERS_PY"], os.path.join(tmp, "orders.py"))
else:
    live = open(os.path.join(API, "orders.py"), encoding="utf-8").read()
    shutil.copy(os.path.join(API, "orders.py"), os.path.join(tmp, "api", "orders.py"))
    if "origin_label" not in live:
        subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, "orders.py.patch")], check=True)
    shutil.copy(os.path.join(tmp, "api", "orders.py"), os.path.join(tmp, "orders.py"))
sys.path.insert(0, API)
sys.path.insert(0, tmp)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:500]))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def pocet_ostre():
    c = ostre()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM shop_orders")
            return cur.fetchone()["n"]
    finally:
        c.close()


PRED = pocet_ostre()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


try:
    with real.cursor() as cur:
        for t in ("shop_orders", "shop_documents", "shop_order_items"):
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        for sl, df in (("shipping_review", "TINYINT(1) NOT NULL DEFAULT 0"), ("vat_mode", "VARCHAR(20) DEFAULT NULL"), ("vat_check", "VARCHAR(20) DEFAULT NULL")):
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_orders' AND COLUMN_NAME=%s", (sl,))
            if not list(cur.fetchone().values())[0]:
                cur.execute(f"ALTER TABLE `shop_orders` ADD COLUMN `{sl}` {df}")
    real.commit()

    def obj(cislo, host=None, lang=None, review=0, test=0):
        sql("INSERT INTO shop_orders (order_number, status, delivery_state, billing_state, customer_name, customer_email, total_czk, order_host, order_lang, shipping_review, vat_mode, vat_check, is_test) "
            "VALUES (%s,'nova','nova','nevyfakturovano','Z','z@x.test',100,%s,%s,%s,%s,%s,%s)", (cislo, host, lang, review, "reverse_charge" if host else None, "vies_valid" if host else None, test))

    obj("A-1")
    obj("B-1", "baliace-stoly.top", "sk", 1)
    obj("B-2", "baliace-stoly.top", "sk", 0)
    obj("C-1", "packstations.top", "en", 1)
    obj("T-1", "baliace-stoly.top", "sk", 1, test=1)
    uzivatel = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1")[0]["id"]
    cookie = {"Cookie": "session=" + SecureCookieSessionInterface().get_signing_serializer(appmod.app).dumps({"user_id": uzivatel})}
    cl = appmod.app.test_client(use_cookies=False)

    def seznam(q=""):
        appmod._rate_limit_buckets.clear()
        r = cl.get("/api/admin/orders" + q, headers=cookie)
        return r.status_code, r.get_json()

    code, d = seznam()
    by = {o["order_number"]: o for o in d["orders"]}
    over("P1 seznam: kazda objednavka nese order_host, order_lang a origin_label (mini-shop 'host · jazyk', hlavni e-shop 'e-shop'), shipping_review, vat_mode a vat_check; testovaci objednavka se nepocita",
         code == 200 and set(by) == {"A-1", "B-1", "B-2", "C-1"} and by["A-1"]["origin_label"] == "e-shop" and by["A-1"]["order_host"] is None and by["B-1"]["origin_label"] == "baliace-stoly.top · sk"
         and by["B-1"]["order_lang"] == "sk" and by["B-1"]["shipping_review"] == 1 and by["B-2"]["shipping_review"] == 0 and by["B-1"]["vat_mode"] == "reverse_charge" and by["B-1"]["vat_check"] == "vies_valid"
         and by["A-1"]["vat_mode"] is None and by["C-1"]["origin_label"] == "packstations.top · en", (code, {k: v["origin_label"] for k, v in by.items()}))
    over("P2 origins pro filtr: nejdriv e-shop, pak kazdy mini-shop (host + jazyk) s poctem objednavek (bez testovacich)",
         d["origins"] == [{"key": "eshop", "label": "e-shop"}, {"key": "baliace-stoly.top", "label": "baliace-stoly.top · sk", "count": 2}, {"key": "packstations.top", "label": "packstations.top · en", "count": 1}], d["origins"])
    _, d1 = seznam("?origin=eshop")
    _, d2 = seznam("?origin=baliace-stoly.top")
    _, d3 = seznam("?shipping_review=1")
    _, d4 = seznam("?origin=baliace-stoly.top&shipping_review=1")
    _, d5 = seznam("?origin=nezname.example")
    _, d6 = seznam("?include_test=1&origin=baliace-stoly.top")
    over("P3 filtry: origin=eshop jen hlavni e-shop, origin=<host> jen ten mini-shop, shipping_review=1 jen ke schvaleni, kombinace (AND), neznamy puvod = prazdny seznam, include_test pridava testovaci",
         [o["order_number"] for o in d1["orders"]] == ["A-1"] and sorted(o["order_number"] for o in d2["orders"]) == ["B-1", "B-2"] and sorted(o["order_number"] for o in d3["orders"]) == ["B-1", "C-1"]
         and [o["order_number"] for o in d4["orders"]] == ["B-1"] and d5["orders"] == [] and sorted(o["order_number"] for o in d6["orders"]) == ["B-1", "B-2", "T-1"],
         ([o["order_number"] for o in d1["orders"]], [o["order_number"] for o in d2["orders"]], [o["order_number"] for o in d3["orders"]], d5["orders"]))
    over("P4 pocty v tabech (counts) zustavaji pro cely seznam bez ohledu na puvod (stabilni tab cisla)", d1["counts"]["all"] == 4 and d1["counts"]["nova"] == 4, d1["counts"])
    appmod._rate_limit_buckets.clear()
    r = cl.get("/api/admin/orders?origin=" + "x" * 400, headers=cookie)
    over("P5 nesmyslne dlouhy puvod nespadne (500)", r.status_code == 200 and r.get_json()["orders"] == [], r.status_code)
    appmod._rate_limit_buckets.clear()
    r = cl.get("/api/admin/orders")
    over("P6 bez prihlaseni je seznam nedostupny (401/403)", r.status_code in (401, 403), r.status_code)
finally:
    with real.cursor() as cur:
        for t in ("shop_orders", "shop_documents", "shop_order_items"):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()
over("ostre objednavky beze zmeny", pocet_ostre() == PRED, (PRED, pocet_ostre()))
ok = sum(vysl)
print(f"\nVYSLEDEK admin prehled objednavek: puvod a filtry: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
