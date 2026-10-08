#!/usr/bin/env python3
"""Integracni most "KOSIK A OBJEDNAVKA": SKUTECNY front-end (vlozeny generator stolu /embed/stul.html, kosik na product.html, admin.html) nad SKUTECNYM kodem kosiku a objednavek
(api/cart.py, api/konfigurace_kosik.py, api/orders.py, api/stul_objednavka_host.py, api/stul_montaz.py, api/miniweb_objednavky_admin.py) a generatoru stolu (api/stul_shop.py) - vse nad DOCASNYMI
tabulkami (stejna technika jako testy bot5: scripts/2026-10-02_konfigurace_kosik_testy, scripts/2026-10-04_stul_host_testy). Zadna data v provozu: kosik, objednavky, produkty, zakaznici,
nastaveni, e-maily atd. jsou na spojeni TEMPORARY (kontrola pred kazdym API dotazem; kdyby docasna tabulka zmizela, most se zastavi), e-maily a audit se jen zachytavaji (SMTP je zakazano)
a na konci se porovnaji pocty a stav ostrych tabulek. Z ostre DB se jen CTE (app_users pro prihlaseni testovaciho zakaznika - jeho jmeno/e-mail se prohlizeci nepredava, katalog dilu pro cenu).
Soubory backendu hosta, ktere zive jeste nejsou patchnute (nasazeni 3:30/12:30), se pripravuji jako kopie z HEAD + patch ze sady (jako u bot5); az budou nasazene, pouziji se zive.
DULEZITE: server je JEDNOVLAKNOVY a bezi v hlavnim vlakne - docasne tabulky patri spojeni vlakna (get_conn() je per-thread), dalsi vlakno by otevrelo ostre spojeni.
Rizeni z testu (stejny origin): /__bridge/anon?on=1|0 (nepřihlášený host / prihlaseny zakaznik), /__bridge/orders (docasne objednavky a polozky), /__bridge/emails (zachycene e-maily), /__bridge/setting?key=&value=.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
    api/venv/bin/python3 scripts/2026-10-02_miniweb_frontend_testy/bridge_kosik.py <testovaci_skript.js>
Skript dostane BASE (adresa mostu), PID (id aktivniho testovaciho stolu), PID_NEAKT (id neaktivniho = jako karta pred zapnutim)."""
import json, os, shutil, smtplib, subprocess, sys, tempfile, threading, time
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi (viz hlavicka)"); sys.exit(2)
if len(sys.argv) < 2:
    print("pouziti: bridge_kosik.py <test.js>"); sys.exit(2)

# ---- kandidati: zive soubory, nebo (kdyz nejsou patchnute) kopie z HEAD s patchem ze sady nasazeni
KIT = os.path.join(REPO, "scripts", "2026-10-03_miniweb_objednavky_testy", "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_kosik_most_")
os.makedirs(os.path.join(tmp, "api"))
if os.path.exists(os.path.join(API, "stul_objednavka_host.py")):
    for f, marker, patch in (("orders.py", "_montaz_radek", "stul_orders.py.patch"), ("konfigurace_kosik.py", "stul_montaz", "stul_konfigurace_kosik.py.patch"),
                             ("miniweb_objednavky_admin.py", "od 2026-10-04 i objednavky hlavniho e-shopu", "stul_miniweb_objednavky_admin.py.patch")):
        live = open(os.path.join(API, f), encoding="utf-8").read()
        if marker in live:
            shutil.copy(os.path.join(API, f), os.path.join(tmp, f))
        else:                                                              # patche se pocitaji proti HEAD (zive soubory muzou mit cizi rozpracovane zmeny)
            head = subprocess.run(["git", "show", f"HEAD:api/{f}"], cwd=REPO, capture_output=True, text=True, check=True).stdout
            open(os.path.join(tmp, "api", f), "w", encoding="utf-8").write(head)
            subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, patch)], check=True)
            shutil.copy(os.path.join(tmp, "api", f), os.path.join(tmp, f))
sys.path.insert(0, API); sys.path.insert(0, tmp)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, os.path.join(REPO, "scripts"))
try:
    import pymysql
    import app as appmod
    import cart as cartmod
    import orders as ordersmod
    import documents as docs
    import konfigurace_kosik as kk
    import stul_api
    import stul_shop
    try:
        import stul_ulozeni as ULOZ        # ulozena konfigurace (bot16 2026-10-05); starsi strom bez modulu: testy ulozeni se nespusti
        import ulozeni_testovaci as UT
    except ImportError:
        ULOZ = UT = None
    import dealers
    try:
        import stul_montaz  # noqa: F401  (registruje /api/stul/montaz)
        import stul_objednavka_host as soh  # noqa: F401  (registruje /api/shop/stul/quote a /order)
        import miniweb_objednavky_admin as moa
    except ImportError:
        soh = moa = None
    from flask.sessions import SecureCookieSessionInterface
finally:
    threading.Thread.start = _orig

AUDIT, EMAILS, QUEUE = [], [], []
for m in (appmod, cartmod, ordersmod, soh, moa, sys.modules.get("stul_montaz")):
    if m is not None:
        m.log_audit = lambda *a, **k: AUDIT.append((a, k))
ordersmod._send_order_emails_bg = lambda result: EMAILS.append(("objednavka", result))
ordersmod._send_status_change_email = lambda *a, **k: EMAILS.append(("stav", a))
docs._auto_email_after_issue = lambda order_id, doc_id: QUEUE.append((order_id, doc_id))
dealers.attach_attribution = lambda *a, **k: None


def _zakazano(*a, **k):
    EMAILS.append(("smtp", a))
    raise AssertionError("TEST: odesilani e-mailu je zakazane")


appmod.send_email = _zakazano
smtplib.SMTP = _zakazano
smtplib.SMTP_SSL = _zakazano
stul_api._ctx_ceny()                      # katalog dilu se nacte JEDNOU pred zalozenim docasnych tabulek (jinak by se cetl z prazdne docasne shop_products)
stul_api.CTX_TTL_S = 10 ** 9


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE_TABULKY = ("shop_cart_items", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_products", "shop_stock_movements", "shop_payment_methods",
                 "shop_shipping_methods", "shop_customers", "shop_customer_groups", "sestava_typ_sluzba", "app_settings", "audit_log", "shop_emails")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE_TABULKY:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('stul_montaz_pct','cart_enabled','configurator_products') ORDER BY 1")
            out["nastaveni"] = [tuple(r.values()) for r in cur.fetchall()]
            cur.execute("SELECT id, active, price_czk_placeholder FROM shop_products WHERE id=4934")
            out["karta4934"] = tuple(str(v) for v in (cur.fetchone() or {}).values())
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_order_number_sequence")
            out["seq_obj"] = int(cur.fetchone()["s"])
            cur.execute("SELECT COALESCE(SUM(next_number),0) AS s FROM shop_document_sequences")
            out["seq_dok"] = int(cur.fetchone()["s"])
            return out
    finally:
        c.close()


PRED = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_cart_items", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "shop_products", "shop_payment_methods",
             "shop_shipping_methods", "shop_stock_movements", "shop_customers", "shop_customer_groups", "sestava_typ_sluzba", "shop_product_images", "shop_emails", "system_emails",
             "storefront_hosts", "car_storefronts", "crm_leads", "crm_lead_messages")
TEMP_COPY = ("shop_document_sequences", "shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


def jsou_docasne():
    for t in TEMP_LIKE + TEMP_COPY + (("stul_ulozene_konfigurace",) if ULOZ else ()):
        r = sql(f"SHOW CREATE TABLE `{t}`")
        if not list(r[0].values())[1].startswith("CREATE TEMPORARY TABLE"):
            return False
    return True


with real.cursor() as cur:
    for t in TEMP_COPY:
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
    for t in TEMP_LIKE:
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
if ULOZ:
    with real.cursor() as cur:
        cur.execute(ULOZ.DDL.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", 1))
    UT.instal(ULOZ)
real.commit()
if not jsou_docasne():
    print("ABORT: nektera tabulka neni docasna"); sys.exit(3)
sql("DELETE FROM app_settings WHERE setting_key IN ('cart_enabled')")

# ---- docasna data: aktivni a neaktivni stul, platby, doprava, zakaznik bez skupinove slevy (ceny v kosiku = ceny v generatoru)
sql("INSERT INTO shop_payment_methods (id, name, price_czk, requires_advance_invoice, active) VALUES (1,'Platba předem',0,1,1),(2,'Dobírka',0,0,1)")
sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (1,'Osobní odběr',0,1,0,'fixed'),(4,'Toptrans',0,1,1,'zip_weight')")


def vloz(tabulka, **h):
    sql(f"INSERT INTO {tabulka} ({', '.join(h)}) VALUES ({', '.join(['%s'] * len(h))})", list(h.values()))


def produkt(sku, name, active):
    vloz("shop_products", sku=sku, name=name, price_czk_placeholder=None, stock_qty=0, weight_g=0, active=active, unit="ks")
    return sql("SELECT id FROM shop_products WHERE sku=%s", (sku,))[0]["id"]


CFG = produkt("T-STUL", "Konfigurovatelný balicí a pracovní stůl (test)", 1)
CFG_NEAKT = produkt("T-STUL-N", "Neaktivní konfigurovatelný stůl (test)", 0)
stul_shop._PRODUKTY.update(t=time.time() + 10 ** 9, map={str(CFG): stul_shop.RECEPT, str(CFG_NEAKT): stul_shop.RECEPT})
uzivatel = sql("SELECT id FROM app_users WHERE role='user' AND active=1 AND email NOT IN ('mandik@logiman.cz','logiman.sklad@seznam.cz') ORDER BY id LIMIT 1")
if not uzivatel:
    print("ABORT: v ostre DB neni zadny aktivni zakaznik pro prihlaseni (jen cteni)"); sys.exit(3)
UA = uzivatel[0]["id"]
cols = {c["Field"] for c in sql("SHOW COLUMNS FROM shop_customers")}
vloz("shop_customers", **{k: v for k, v in {"user_id": UA, "full_name": "Test Zákazník", "email": "test@example.test", "billing_zip": "11000", "delivery_zip": "11000", "delivery_address": "Testovací 1, Praha",
                                            "billing_address": "Testovací 1, Praha"}.items() if k in cols})
_si = SecureCookieSessionInterface()
COOKIE = "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": UA})
client = appmod.app.test_client(use_cookies=False)
WEB = os.path.abspath(os.environ.get("WEB_OVERRIDE") or os.path.join(REPO, "webapp"))      # WEB_OVERRIDE: kandidatni staticke soubory (nezasahuje do zive statiky)
TYPY = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".hdr": "application/octet-stream", ".glb": "model/gltf-binary"}
FAKE_ME = {"user": {"id": UA, "email": "test@example.test", "role": "user", "name": "Test Zákazník", "permissions": {}}}      # prohlizeci se nikdy nepredava skutecne jmeno/e-mail zakaznika
stav = {"duvod": None, "anon": False}


def _jsonable(o):
    if isinstance(o, Decimal):
        return float(o)
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, default=_jsonable, ensure_ascii=False).encode(), "application/json")

    def _handle(self):
        u = urlparse(self.path); p = u.path; q = parse_qs(u.query)
        if p == "/__bridge/anon":
            stav["anon"] = (q.get("on") or ["1"])[0] == "1"; return self._json(200, {"anon": stav["anon"]})
        if p == "/__bridge/orders":
            orders = sql("SELECT * FROM shop_orders ORDER BY id")
            for o in orders:
                o["items"] = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (o["id"],))
            return self._json(200, {"orders": orders, "emails": [e[0] for e in EMAILS], "queue": len(QUEUE)})
        if p == "/__bridge/setting":
            sql("DELETE FROM app_settings WHERE setting_key=%s", ((q.get("key") or [""])[0],))
            if (q.get("value") or [None])[0] is not None:
                sql("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s)", ((q.get("key") or [""])[0], q["value"][0]))
            return self._json(200, {"ok": True})
        if ULOZ and p in ("/__bridge/registry", "/__bridge/ulozeni"):
            return self._json(*UT.rizeni(p, q, sql))
        if p == "/api/auth/me":
            return self._json(401, {"user": None}) if stav["anon"] else self._json(200, FAKE_ME)
        if p.startswith("/api/"):
            if not jsou_docasne():                                     # pojistka: kdyby spojeni zaniklo, docasne tabulky by zmizely a zapisovalo by se do ostrych
                stav["duvod"] = "docasne tabulky zmizely"; return self._json(500, {"error": "abort"})
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            appmod._rate_limit_buckets.clear()
            hdr = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            if not stav["anon"]:
                hdr["Cookie"] = COOKIE
            r = client.open(self.path, method=self.command, data=body, headers=hdr)
            return self._send(r.status_code, r.get_data(), r.headers.get("Content-Type", "application/json"))
        f = os.path.normpath(os.path.join(WEB, p.lstrip("/")))
        if f.startswith(WEB) and os.path.isfile(f):
            return self._send(200, open(f, "rb").read(), TYPY.get(os.path.splitext(f)[1], "application/octet-stream"))
        self._send(404, b"nf", "text/plain")
    do_GET = do_POST = do_PUT = do_DELETE = _handle


class S(HTTPServer):
    request_queue_size = 128


srv = S(("127.0.0.1", 0), H)
srv.timeout = 0.2
base = "http://127.0.0.1:%d" % srv.server_address[1]
proc = subprocess.Popen(["node", sys.argv[1]], env=dict(os.environ, BASE=base, PID=str(CFG), PID_NEAKT=str(CFG_NEAKT)))
while proc.poll() is None and not stav["duvod"]:
    srv.handle_request()
if stav["duvod"]:
    proc.kill(); print("ABORT:", stav["duvod"]); sys.exit(4)
PO = stav_ostrych()
zmena = {k: (PRED[k], PO[k]) for k in PRED if PRED[k] != PO[k]}
print("KONTROLA OSTRYCH TABULEK:", "beze zmeny (nic se nezapsalo)" if not zmena else "ZMENA! %r" % zmena)
print("E-MAILY zachycene (zadny se neodeslal):", len(EMAILS), "| zaradeno do fronty:", len(QUEUE))
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(proc.returncode or (5 if zmena else 0))
