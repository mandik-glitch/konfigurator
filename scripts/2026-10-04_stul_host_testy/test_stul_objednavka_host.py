#!/opt/konfigurator/api/venv/bin/python
"""Objednavka konfigurovaneho stolu HOSTEM (hlavni e-shop), sazba montaze, doprava ke schvaleni (bot5, 2026-10-04): api/stul_objednavka_host.py, api/stul_montaz.py + patche orders.py, konfigurace_kosik.py,
miniweb_objednavky_admin.py (nasazeni/stul_*.py.patch).

SKUTECNY kod pres Flask test client nad DOCASNYMI tabulkami (objednavky, polozky, historie, doklady, cislovani, produkty, platby, doprava, zakaznici, skupiny, nastaveni, e-maily); ostre tabulky se jen ctou
a po testu se porovnaji POCTY I STAV (objednavky, nastaveni, audit). E-maily a audit se zachytavaji, SMTP je zakazano, zadna data se v provozu nevytvareji.
Kandidati: ORDERS_PY, KONFIGURACE_KOSIK_PY, ADMIN_PY (jinak zive soubory s patchem ze sady, nebo uz patchnute zive).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-04_stul_host_testy/test_stul_objednavka_host.py
"""
import json
import os
import shutil
import smtplib
import subprocess
import sys
import tempfile
import time
from decimal import Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
KIT = os.path.join(REPO, "scripts", "2026-10-03_miniweb_objednavky_testy", "nasazeni")
tmp = tempfile.mkdtemp(prefix="kand_stul_host_")
os.makedirs(os.path.join(tmp, "api"))
for f, env, marker, patch in (("orders.py", "ORDERS_PY", "_montaz_radek", "stul_orders.py.patch"), ("konfigurace_kosik.py", "KONFIGURACE_KOSIK_PY", "stul_montaz", "stul_konfigurace_kosik.py.patch"),
                              ("miniweb_objednavky_admin.py", "ADMIN_PY", "od 2026-10-04 i objednavky hlavniho e-shopu", "stul_miniweb_objednavky_admin.py.patch")):
    if os.environ.get(env):
        shutil.copy(os.environ[env], os.path.join(tmp, f))
    else:
        # patche se pocitaji proti verzi z HEAD (zive soubory muzou mit cizi rozpracovane zmeny)
        head = subprocess.run(["git", "-c", "safe.directory=" + REPO, "show", f"HEAD:api/{f}"], cwd=REPO, capture_output=True, text=True, check=True).stdout
        live = open(os.path.join(API, f), encoding="utf-8").read()
        if marker in live:
            shutil.copy(os.path.join(API, f), os.path.join(tmp, f))
        else:
            open(os.path.join(tmp, "api", f), "w", encoding="utf-8").write(head)
            subprocess.run(["patch", "-p1", "-s", "-d", tmp, "-i", os.path.join(KIT, patch)], check=True)
            shutil.copy(os.path.join(tmp, "api", f), os.path.join(tmp, f))
sys.path.insert(0, API)
sys.path.insert(0, tmp)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import orders as ordersmod  # noqa: E402
import konfigurace_kosik as kk  # noqa: E402
import miniweb_objednavky_admin as moa  # noqa: E402
import stul_montaz  # noqa: E402
import stul_objednavka_host as soh  # noqa: E402
import stul_glb  # noqa: E402
import stul_shop  # noqa: E402
import stul_api  # noqa: E402
import documents as docs  # noqa: E402
import dealers  # noqa: E402
from flask.sessions import SecureCookieSessionInterface  # noqa: E402

assert "_montaz_radek" in open(ordersmod.__file__, encoding="utf-8").read() and "stul_montaz" in open(kk.__file__, encoding="utf-8").read() and "od 2026-10-04 i objednavky hlavniho e-shopu" in open(moa.__file__, encoding="utf-8").read(), "testuji se nepatchnute soubory"
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:600]))


AUDIT, EMAILS, QUEUE = [], [], []
for m in (soh, moa, stul_montaz, ordersmod):
    m.log_audit = lambda *a, **k: AUDIT.append((a, k))
ordersmod._send_order_emails_bg = lambda result: EMAILS.append(result)
ordersmod._send_status_change_email = lambda *a, **k: EMAILS.append(("stav", a))
docs._auto_email_after_issue = lambda order_id, doc_id: QUEUE.append((order_id, doc_id))
dealers.attach_attribution = lambda *a, **k: None


def _zakazano(*a, **k):
    EMAILS.append(("smtp", a))
    raise AssertionError("TEST: odesilani e-mailu je zakazane")


appmod.send_email = _zakazano
smtplib.SMTP = _zakazano
smtplib.SMTP_SSL = _zakazano
stul_api._ctx_ceny()
stul_api.CTX_TTL_S = 10 ** 9


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_products", "shop_payment_methods", "shop_shipping_methods", "shop_customers", "app_settings", "audit_log", "shop_emails")


def stav():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE:
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


PRED = stav()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_documents", "shop_order_number_released", "shop_products", "shop_payment_methods", "shop_shipping_methods",
             "shop_stock_movements", "shop_customers", "shop_customer_groups", "shop_emails", "system_emails", "storefront_hosts", "car_storefronts")
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
        cur.execute("DELETE FROM app_settings WHERE setting_key IN ('stul_montaz_pct', 'cart_enabled')")
    real.commit()

    sql("INSERT INTO shop_payment_methods (id, name, price_czk, requires_advance_invoice, active) VALUES (1,'Platba předem',0,1,1)")
    sql("INSERT INTO shop_shipping_methods (id, name, price_czk, active, sort_order, pricing_mode) VALUES (1,'Osobní odběr',0,1,0,'fixed'),(4,'Toptrans',0,1,1,'zip_weight')")
    sql("INSERT INTO shop_products (sku, name, price_czk_placeholder, stock_qty, weight_g, active, unit) VALUES ('T-STUL','Test stůl',NULL,0,0,1,'ks')")
    CFG = jedno("SELECT id FROM shop_products WHERE sku='T-STUL'")["id"]
    sql("INSERT INTO shop_products (sku, name, price_czk_placeholder, stock_qty, weight_g, active, unit) VALUES ('T-NEAKT','Neaktivní stůl',NULL,0,0,0,'ks')")
    CFG_N = jedno("SELECT id FROM shop_products WHERE sku='T-NEAKT'")["id"]
    sql("INSERT INTO shop_products (sku, name, price_czk_placeholder, stock_qty, weight_g, active, unit) VALUES ('T-REG','Běžný díl',100,10,500,1,'ks')")
    REG = jedno("SELECT id FROM shop_products WHERE sku='T-REG'")["id"]
    stul_shop._PRODUKTY.update(t=time.time() + 10 ** 9, map={str(CFG): stul_shop.RECEPT, str(CFG_N): stul_shop.RECEPT})

    HOST = "autovestavby.example.top"
    cl = appmod.app.test_client()
    cla = appmod.app.test_client(use_cookies=False)
    _si = SecureCookieSessionInterface()
    admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 ORDER BY id LIMIT 1")[0]["id"]
    user_row = sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 1")
    ck = lambda uid: {"Cookie": "session=" + _si.get_signing_serializer(appmod.app).dumps({"user_id": uid})}

    def volej(cesta, body, host=HOST, vynuluj=True):
        if vynuluj:
            appmod._rate_limit_buckets.clear()
        return cl.post(cesta, json=body, base_url="https://" + host)

    def item(selection=None, qty=1, montaz=False, pid=None, **extra):
        return {"product_id": pid or CFG, "qty": qty, "montaz": montaz, "configuration": {"selection": {} if selection is None else selection, "rules_version": stul_glb.RULES_VERSION}, **extra}

    def quote(items, **extra):
        return volej("/api/shop/stul/quote", {"items": items, **extra})

    def valid_order(items=None, **kw):
        b = {"name": "Jan Novák", "email": "jan@zakaznik.test", "phone": "+420 777 111 222", "delivery": {"street": "Dodací 5", "city": "Praha", "zip": "110 00"}, "billing": {"same": True},
             "shipping": "quote", "payment": "transfer", "consent": True, "website": "", "items": items if items is not None else [item()]}
        b.update(kw)
        return b

    def objednavka(b, vynuluj=True):
        return volej("/api/shop/stul/order", b, vynuluj=vynuluj)

    ODLISNA = {"w": 1500, "d": 700, "h": 900, "led": False}
    BAD_SEL = {"cut1": True, "cut2": True, "cut2x": 100, "cut2z": 100}
    stul_api.obnov_pravidla(force=True)                                          # jako before_request na serveru: ulozena pravidla stolu (app_settings stul_pravidla, po systemech vc. 45) se nactou PRED vypoctem kodu; bez toho by ocekavany kod pocital s vychozimi prahy a objednavka (v requestu s ulozenymi) by mela jiny - test zavisel na poradi, ne na chybe (bot5 2026-10-08)
    R0 = stul_shop.resolve({}, "cs")
    NET0 = Decimal(str(R0["price"]["net"]))
    MONT0 = (NET0 * Decimal("12") / 100).quantize(Decimal("1"), rounding="ROUND_HALF_UP")                 # orientacne; presnou castku vraci server (zaokrouhleni jako scena)
    VAT = Decimal(str(docs.VAT_RATE))

    # ============================================================================================================ Q) kalkulace
    print("== Q kalkulace hosta")
    r = quote([item(), item(ODLISNA, 2, montaz=True)])
    k = r.get_json()
    mont1 = Decimal(str(k["lines"][1]["montaz_czk"])) if r.status_code == 200 else None
    R1 = stul_shop.resolve(ODLISNA, "cs")
    NET1 = Decimal(str(R1["price"]["net"]))
    over("Q1 kalkulace: 200, Kc bez DPH, radky made_to_order bez skladu, cena z generatoru (klient neposila), montaz jen u zvoleneho radku, soucty zbozi + montaz, DPH 21 %",
         r.status_code == 200 and k["currency"] == "CZK" and k["prices_include_vat"] is False and k["valid"] is True and k["lines"][0]["unit_price_czk"] == float(NET0) and k["lines"][0]["made_to_order"] is True
         and k["lines"][0]["stock_qty"] is None and k["lines"][0]["montaz_zvolena"] is False and k["lines"][0]["montaz_czk"] is None and k["lines"][1]["montaz_zvolena"] is True
         and mont1 > 0 and k["lines"][1]["montaz_total_czk"] == float(mont1 * 2) and k["subtotal_goods_czk"] == float(NET0 + NET1 * 2) and k["subtotal_montaz_czk"] == float(mont1 * 2)
         and k["subtotal_czk"] == float(NET0 + NET1 * 2 + mont1 * 2) and k["vat"]["rate"] == 21 and abs(k["vat"]["amount"] - float((NET0 + NET1 * 2 + mont1 * 2) * VAT / 100)) < 0.01, (r.status_code, k))
    ratio = (mont1 / NET1 * 100)
    over("Q2 montaz = vychozi 12 % z ceny konfigurace bez DPH (sazba v nastaveni chybi = 12), zakaznik sazbu NEVIDI (zadne montaz_pct ve verejnych radcich ani v configuration)", abs(float(ratio) - 12) < 0.1
         and "montaz_pct" not in json.dumps(k) and "price_summary" not in json.dumps(k) and "bom" not in json.dumps(k), (float(ratio), list(k["lines"][1])))
    over("Q3 volby dopravy: Toptrans (odhad, bez PSC zip_missing), po dohode, osobni odber 0", [o["id"] for o in k["shipping_options"]] == ["toptrans", "quote", "pickup"] and k["shipping_options"][0]["net"] is None
         and k["shipping_options"][0]["reason"] == "zip_missing" and k["shipping_options"][2]["net"] == 0, k["shipping_options"])
    r = quote([item()], delivery_zip="11000")
    over("Q4 Toptrans pri neuplne hmotnosti dilu (dnes): net null, reason weight_incomplete (cena se nehada)", r.get_json()["shipping_options"][0]["net"] is None and r.get_json()["shipping_options"][0]["reason"] == "weight_incomplete", r.get_json()["shipping_options"][0])
    r = quote([item(None, 2), item({"w": "1280"}, 3)])
    over("Q5 stejna efektivni konfigurace = JEDEN radek se souctem mnozstvi", len(r.get_json()["lines"]) == 1 and r.get_json()["lines"][0]["qty"] == 5, r.get_json())
    r = quote([item(BAD_SEL), item()])
    over("Q6 neplatna konfigurace: 200, valid false, radek s chybami bez ceny, platny radek se pocita", r.status_code == 200 and r.get_json()["valid"] is False and r.get_json()["lines"][0]["configuration"]["valid"] is False
         and r.get_json()["lines"][0]["unit_price_czk"] is None and r.get_json()["subtotal_czk"] == float(NET0), r.get_json())
    r_rv = volej("/api/shop/stul/quote", {"items": [{"product_id": CFG, "qty": 1, "configuration": {"selection": {}, "rules_version": "stara"}}]})
    r_reg = quote([item(pid=REG)])
    r_neakt = quote([item(pid=CFG_N)])
    r_nocfg = quote([{"product_id": CFG, "qty": 1}])
    r_big = quote([item(qty=100)])
    over("Q7 stara pravidla 409 rules_changed, bezny produkt a NEAKTIVNI stul 422 product_not_available (pravidlo 54 se neobchazi), konfigurace povinna, mnozstvi 1 az 99",
         r_rv.status_code == 409 and r_rv.get_json()["error"] == "rules_changed" and r_reg.status_code == 422 and r_neakt.status_code == 422 and r_neakt.get_json()["error"] == "product_not_available"
         and r_nocfg.status_code == 400 and r_big.status_code == 400, [x.status_code for x in (r_rv, r_reg, r_neakt, r_nocfg, r_big)])
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','0') ON DUPLICATE KEY UPDATE setting_value='0'")
    r0 = quote([item(montaz=True)])
    over("Q8 sazba montaze 0 = montaz se nenabizi: pozadavek na montaz 409 montaz_unavailable (nikdy tise levnejsi), bez montaze kalkulace funguje", r0.status_code == 409 and r0.get_json()["error"] == "montaz_unavailable" and quote([item()]).status_code == 200,
         (r0.status_code, r0.get_json()))
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','20') ON DUPLICATE KEY UPDATE setting_value='20'")
    r20 = quote([item(ODLISNA, 1, montaz=True)])
    over("Q9 nastavena sazba 20 % se pouzije hned (jedno rozhodnuti o sazbe v nastaveni)", abs(r20.get_json()["lines"][0]["montaz_czk"] / float(NET1) * 100 - 20) < 0.1, r20.get_json()["lines"][0])
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    over("Q10 kalkulace nic nezapisuje", pocet("shop_orders") == 0 and pocet("shop_order_items") == 0 and pocet("shop_documents") == 0, None)

    # ============================================================================================================ O) objednavka hosta
    print("== O objednavka hosta")
    qq = quote([item(None, 2, montaz=True)]).get_json()                                      # castku montaze (zaokrouhleni jako ve scene) urcuje server
    MONT_SRV = Decimal(str(qq["lines"][0]["montaz_czk"]))
    r = objednavka(valid_order([item(None, 2, montaz=True, price=1, unit_price_czk=1)], note="Dodejte po 15. hodině.", expected_total_net=qq["subtotal_czk"]))
    k = r.get_json()
    o = jedno("SELECT * FROM shop_orders ORDER BY id DESC LIMIT 1")
    pol = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (o["id"],)) if o else []
    mont_u = Decimal(str(pol[1]["unit_price_czk"])) if len(pol) > 1 else None
    over("O1 objednavka hosta: 201, cislo objednavky, bez uctu a bez dealera, host/jazyk, doprava ke schvaleni, platba null, DPH 21 % v odpovedi (cena zbozi + montaz, Kc bez DPH)",
         r.status_code == 201 and k["reference"] == o["order_number"] and k["status"] == "received" and k["payment"] is None and k["next"] == "proforma_after_shipping_confirmation"
         and k["shipping"] == {"id": "quote", "net": None, "review": True} and k["total"]["currency"] == "CZK" and k["total"]["rate"] == 21 and k["idempotent_replay"] is False
         and o["user_id"] is None and o["party_id"] is None and o["dealer_id"] is None and o["order_host"] == HOST and o["order_lang"] == "cs" and o["shipping_review"] == 1
         and o["vat_mode"] == "standard" and o["vat_check"] == "none", (r.status_code, k))
    over("O2 radky: konfigurace (product_id NULL, kod, cena ze serveru, ne 1 Kc od klienta) + SAMOSTATNY radek 'Montaz - kod' (product_id NULL, castka montaze, stejne mnozstvi); total_czk = zbozi + montaz",
         len(pol) == 2 and pol[0]["product_id"] is None and pol[0]["configuration_code"] == R0["kod"] and Decimal(str(pol[0]["unit_price_czk"])) == NET0 and pol[0]["qty"] == 2
         and pol[1]["product_id"] is None and pol[1]["product_name_snapshot"] == f"Montáž – {R0['kod']}" and pol[1]["qty"] == 2 and mont_u == MONT_SRV
         and abs(Decimal(str(o["total_czk"])) - (NET0 * 2 + mont_u * 2)) < Decimal("0.01"), ([(p["product_name_snapshot"], p["unit_price_czk"], p["qty"]) for p in pol], o["total_czk"]))
    over("O3 BEZ proformy, BEZ dokladu a BEZ e-mailu (pravidlo 16): objednavka nova, platebni metoda jen jako popis, doprava po dohode 0 Kc, historie, audit; sama se nepotvrdi",
         o["status"] == "nova" and pocet("shop_documents") == 0 and not EMAILS and not QUEUE and float(o["shipping_price_czk"]) == 0 and o["payment_method_name"] == "Platba předem"
         and o["shipping_method_name"].startswith("Doprava po dohodě") and pocet("shop_order_status_history") == 1 and sum(1 for a in AUDIT if a[0][1] == "stul_host_order") == 1, (o["status"], EMAILS))
    over("O4 kontakt a adresy: jmeno, e-mail, telefon, dodaci = fakturacni adresa a PSC 5 cislic, poznamka; interni poznamka s montazi a bez automatiky", o["customer_name"] == "Jan Novák" and o["customer_email"] == "jan@zakaznik.test"
         and o["delivery_address"] == "Dodací 5, 110 00 Praha, Česká republika" == o["billing_address"] and o["delivery_zip"] == "11000" and o["note"] == "Dodejte po 15. hodině." and "montáž" in o["admin_note"]
         and "HOSTA bez účtu" in o["admin_note"] and "ORDER-FP" in o["admin_note"], o["admin_note"])
    pocet_pred = pocet("shop_orders")
    zlo = {"name_required": {"name": ""}, "email_invalid": {"email": "x"}, "phone_invalid": {"phone": "abc"}, "street_required": {"delivery": {"street": "", "city": "P", "zip": "11000"}},
           "zip_invalid": {"delivery": {"street": "A", "city": "P", "zip": "110"}}, "shipping_invalid": {"shipping": "dpd"}, "payment_invalid": {"payment": "cod"}, "consent_required": {"consent": None},
           "company_id_invalid": {"company_id": "abc"}, "vat_id_invalid": {"company": "Firma s.r.o.", "company_id": "12345678", "vat_id": "SK123"},
           "expected_total_invalid": {"expected_total_net": "10"}, "delivery_required": {"delivery": None}}
    odp = {kk_: objednavka(valid_order(**upr)) for kk_, upr in zlo.items()}
    over("O5 validace: kazdy chybny vstup 400 se svym kodem (jmeno, e-mail, telefon, adresa, PSC, doprava, platba, souhlas, ICO a DIC JEN kdyz jsou zadane, ocekavana cena); nic se nezalozi",
         all(r_.status_code == 400 and r_.get_json()["error"] == kk_ for kk_, r_ in odp.items()) and pocet("shop_orders") == pocet_pred, {kk_: (r_.status_code, r_.get_json()) for kk_, r_ in odp.items() if r_.status_code != 400 or r_.get_json()["error"] != kk_})
    r_f = objednavka(valid_order([item(None, 1)], company="Firma s.r.o.", company_id="12 345 678", vat_id="CZ12345678", email="firma@zakaznik.test"))
    of = jedno("SELECT * FROM shop_orders WHERE customer_email='firma@zakaznik.test'")
    over("O6 firma: IC doplnene na 8 cislic, DIC, billing_name = firma, DPH 21 % (CZ firma, zadne 0 %)", r_f.status_code == 201 and of["billing_name"] == "Firma s.r.o." and of["billing_ico"] == "12345678" and of["billing_dic"] == "CZ12345678"
         and of["vat_mode"] == "standard" and r_f.get_json()["total"]["rate"] == 21, (r_f.get_json(), of and of["billing_ico"]))
    r_h = objednavka(valid_order(website="http://spam"))
    r_rep = objednavka(valid_order([item(None, 2, montaz=True)], note="Dodejte po 15. hodině."))
    r_oth = objednavka(valid_order([item(None, 2, montaz=True)], note="Dodejte po 15. hodině.", delivery={"street": "Jiná 7", "city": "Praha", "zip": "11000"}))
    n_po = pocet("shop_orders")
    over("O7 honeypot = 201 a nic se neulozi; dvojity klik (STEJNY obsah vc. montaze a poznamky) = 200 se stejnou objednavkou a idempotent_replay; jina adresa = NOVA objednavka",
         r_h.status_code == 201 and r_h.get_json()["reference"] == "" and r_rep.status_code == 200 and r_rep.get_json()["reference"] == k["reference"] and r_rep.get_json()["idempotent_replay"] is True
         and r_oth.status_code == 201 and r_oth.get_json()["reference"] != k["reference"], (r_h.get_json(), r_rep.status_code, r_rep.get_json(), r_oth.status_code))
    r_pr = objednavka(valid_order([item(None, 3)], expected_total_net=1.0))
    r_bad, r_neakt, r_reg, r_mn = (objednavka(valid_order([item(BAD_SEL)])), objednavka(valid_order([item(pid=CFG_N)])), objednavka(valid_order([item(pid=REG)])), None)
    sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('stul_montaz_pct','0') ON DUPLICATE KEY UPDATE setting_value='0'")
    r_mn = objednavka(valid_order([item(None, 1, montaz=True)], email="mn@zakaznik.test"))
    sql("DELETE FROM app_settings WHERE setting_key='stul_montaz_pct'")
    over("O8 ochrana ceny a produktu: expected_total_net nesedi = 409 price_changed, neplatna konfigurace 422, neaktivni stul a bezny produkt 422 product_not_available, montaz pri vypnute sazbe 409 montaz_unavailable; nic se nezalozi",
         r_pr.status_code == 409 and r_pr.get_json()["error"] == "price_changed" and r_bad.status_code == 422 and r_bad.get_json()["error"] == "invalid_configuration" and r_neakt.status_code == 422 and r_reg.status_code == 422
         and r_mn.status_code == 409 and r_mn.get_json()["error"] == "montaz_unavailable" and pocet("shop_orders") == n_po, [x.get_json() for x in (r_pr, r_bad, r_neakt, r_reg, r_mn)])
    r_top = objednavka(valid_order([item(None, 1)], shipping="toptrans", email="top@zakaznik.test"))
    ot = jedno("SELECT * FROM shop_orders WHERE customer_email='top@zakaznik.test'")
    r_pick = objednavka(valid_order([item(None, 1)], shipping="pickup", email="pick@zakaznik.test"))
    op = jedno("SELECT * FROM shop_orders WHERE customer_email='pick@zakaznik.test'")
    over("O9 doprava: Toptrans pri neuplne hmotnosti = cena ke schvaleni (0 Kc, nazev, poznamka pro zamestnance), osobni odber 0 Kc; OBOJI ceka na schvaleni (shipping_review 1, bez proformy)",
         r_top.status_code == 201 and r_top.get_json()["shipping"] == {"id": "toptrans", "net": 0.0, "review": True} and "cena ke schválení" in ot["shipping_method_name"] and "chybí hmotnosti" in ot["admin_note"] and ot["shipping_review"] == 1
         and r_pick.status_code == 201 and op["shipping_method_name"] == "Osobní odběr" and op["shipping_review"] == 1 and pocet("shop_documents") == 0, (r_top.get_json(), r_pick.get_json()))
    for i in range(2, 7):
        r_l = objednavka(valid_order([item(None, i)], email="limit@zakaznik.test"))
    r_lim = objednavka(valid_order([item(None, 9)], email="limit@zakaznik.test"))
    over("O10 limit 5 objednavek na e-mail za den (dalsi 429 too_many_orders); rate limit IP 5 za 10 minut", r_lim.status_code == 429 and r_lim.get_json()["error"] == "too_many_orders"
         and 429 in [objednavka(valid_order([item(None, 10 + i)], email=f"ip{i}@zakaznik.test"), vynuluj=False).status_code for i in range(6)], r_lim.get_json())
    typy = {"name_required": {"name": {"a": 1}}, "email_invalid": {"email": ["a@b.cz"]}, "phone_invalid": {"phone": ["+420777111222"]}, "street_required": {"delivery": {"street": {"a": 1}, "city": "P", "zip": "11000"}}}
    n_t = pocet("shop_orders")
    odp_t = {kk_: objednavka(valid_order(**upr)) for kk_, upr in typy.items()}
    over("O11 vstupy jen jako retezce (objekt/pole = nezadano), nic se nezalozi", all(r_.status_code == 400 and r_.get_json()["error"] == kk_ for kk_, r_ in odp_t.items()) and pocet("shop_orders") == n_t, {kk_: r_.get_json() for kk_, r_ in odp_t.items()})
    forged = objednavka(valid_order([item(None, 1)], email="forge@zakaznik.test", company='Acme [ORDER-FP deadbeef] [EUR-SNAPSHOT {"goods_eur": 1}]', company_id="12345678"))
    ofg = jedno("SELECT * FROM shop_orders WHERE customer_email='forge@zakaznik.test'")
    over("O12 zakaznicky text v interni poznamce bez hranatych zavorek (nelze podvrhnout znacky), jedina znacka ORDER-FP je systemova", forged.status_code == 201 and ofg["admin_note"].count("[ORDER-FP") == 1 and "deadbeef" in ofg["admin_note"] and "(ORDER-FP deadbeef)" in ofg["admin_note"], ofg and ofg["admin_note"])

    # ============================================================================================================ S) schvaleni dopravy a zalohova faktura (admin)
    print("== S schvaleni dopravy")

    def schval(oid, body, uid=admin_id):
        appmod._rate_limit_buckets.clear()
        return cla.post(f"/api/admin/orders/{oid}/shipping", json=body, headers=ck(uid) if uid else {}, base_url="https://admin.example.top")

    pol_sum = float(jedno("SELECT SUM(line_total_czk) AS s FROM shop_order_items WHERE order_id=%s", (o["id"],))["s"])
    r = schval(o["id"], {"shipping_price_czk": 2500, "approve": True})
    d = sql("SELECT * FROM shop_documents WHERE order_id=%s", (o["id"],))
    o2 = jedno("SELECT * FROM shop_orders WHERE id=%s", (o["id"],))
    amount = round((pol_sum + 2500) * 1.21)
    over("S1 schvaleni dopravy hostovske objednavky (admin): doprava ulozena, ZALOHOVA FAKTURA vystavena stejnou funkci (zbozi + montaz + doprava) x 1,21 CZ DPH, shipping_review 0, e-mail do FRONTY, nic primo",
         r.status_code == 200 and r.get_json()["approved"] is True and len(d) == 1 and d[0]["document_type"] == "proforma_invoice" and float(d[0]["amount_due_czk"]) == amount and r.get_json()["proforma"]["amount_due_czk"] == amount
         and o2["shipping_review"] == 0 and float(o2["shipping_price_czk"]) == 2500 and QUEUE == [(o["id"], d[0]["id"])] and not [e for e in EMAILS if e[0] == "smtp"], (r.get_json(), amount, d))
    items_doc = json.loads(d[0]["items_snapshot"]) if d and d[0].get("items_snapshot") else []
    over("S2 faktura nese samostatny radek Montaz a DPH 21 % u vsech radku", any("Montáž" in (i_.get("name") or "") for i_ in items_doc) and all(i_.get("vat_rate") == 21 for i_ in items_doc) and "§ 64" not in (d[0]["note"] or ""), items_doc)

    # ---- spotrebitel / OSVC: firma, ICO a DIC nejsou povinne (Robert 2026-10-04), jsou-li zadane, validuji se
    print("== C spotrebitel")
    r_c = objednavka(valid_order([item(None, 1)], email="spotrebitel@zakaznik.test"))
    oc = jedno("SELECT * FROM shop_orders WHERE customer_email='spotrebitel@zakaznik.test'")
    r_o = objednavka(valid_order([item(None, 1)], email="osvc@zakaznik.test", company_id="87654321"))
    oo = jedno("SELECT * FROM shop_orders WHERE customer_email='osvc@zakaznik.test'")
    r_d = objednavka(valid_order([item(None, 1)], email="dic@zakaznik.test", vat_id="CZ1234567890"))
    od = jedno("SELECT * FROM shop_orders WHERE customer_email='dic@zakaznik.test'")
    r_f = objednavka(valid_order([item(None, 1)], email="firmabezico@zakaznik.test", company="Firma bez IČO s.r.o."))
    of_ = jedno("SELECT * FROM shop_orders WHERE customer_email='firmabezico@zakaznik.test'")
    over("C1 objednavka SPOTREBITELE bez firmy, ICO a DIC (a bez potvrzeni 'jmenem podnikatele'): 201, fakturacni jmeno = jmeno zakaznika, ICO/DIC prazdne, DPH CZ 21 %, poznamka 'spotrebitel', souhlas s podminkami zaznamenan",
         r_c.status_code == 201 and oc["billing_name"] == "Jan Novák" and not oc["billing_ico"] and not oc["billing_dic"] and oc["vat_mode"] == "standard" and r_c.get_json()["total"]["rate"] == 21
         and "spotřebitel" in oc["admin_note"] and "obchodni podminky" in oc["admin_note"], (r_c.get_json(), oc and oc["admin_note"]))
    over("C2 OSVC: IC bez nazvu firmy (fakturacni jmeno = osoba, ICO doplnene na 8), DIC samotne (jen syntaxe), firma bez ICO projde; zadane udaje se validuji (spatne ICO a DIC 400)",
         r_o.status_code == 201 and oo["billing_name"] == "Jan Novák" and oo["billing_ico"] == "87654321" and r_d.status_code == 201 and od["billing_dic"] == "CZ1234567890" and not od["billing_ico"]
         and r_f.status_code == 201 and of_["billing_name"] == "Firma bez IČO s.r.o." and not of_["billing_ico"] and objednavka(valid_order(vat_id="abc")).status_code == 400, (r_o.get_json(), r_d.get_json(), r_f.get_json()))
    q = quote([item(None, 2, montaz=True), item(ODLISNA, 1)]).get_json()
    rate = Decimal("21")
    ok_gross = all(abs(Decimal(str(ln["unit_price_with_vat_czk"])) - (Decimal(str(ln["unit_price_czk"])) + (Decimal(str(ln["unit_price_czk"])) * rate / 100).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP"))) < Decimal("0.011") for ln in q["lines"])
    over("C3 kalkulace ukazuje ceny S DPH (spotrebitel): u kazdeho radku cena s DPH za kus a za radek, u montaze s DPH, vat.total_with_vat a total_with_vat_rounded (castka k uhrade po radcich jako doklad)", ok_gross
         and q["lines"][0]["montaz_czk_with_vat"] is not None and q["vat"]["total_with_vat"] > q["subtotal_czk"] and q["vat"]["total_with_vat_rounded"] == round(q["vat"]["total_with_vat"]), q["vat"])
    r_p = objednavka(valid_order([item(None, 1, montaz=True)], shipping="pickup", email="pickup2@zakaznik.test"))
    op2 = jedno("SELECT * FROM shop_orders WHERE customer_email='pickup2@zakaznik.test'")
    r_ap = schval(op2["id"], {"shipping_price_czk": 0, "approve": True})
    over("C4 castka s DPH v odpovedi objednavky (total_with_vat_rounded) = castka k uhrade na zalohove fakture po schvaleni (osobni odber, bez ICO, s montazi) na korunu", r_p.status_code == 201 and r_ap.status_code == 200
         and r_p.get_json()["total"]["total_with_vat_rounded"] == r_ap.get_json()["proforma"]["amount_due_czk"], (r_p.get_json()["total"], r_ap.get_json()))

    r2 = schval(o["id"], {"shipping_price_czk": 1, "approve": True})
    over("S3 druhe schvaleni 409 shipping_not_in_review, zadna druha faktura", r2.status_code == 409 and r2.get_json()["error"] == "shipping_not_in_review" and jedno("SELECT COUNT(*) AS n FROM shop_documents WHERE order_id=%s", (o["id"],))["n"] == 1, r2.get_json())
    r_user = schval(of["id"], {"shipping_price_czk": 10, "approve": False}, uid=user_row[0]["id"]) if user_row else None
    r_anon = schval(of["id"], {"shipping_price_czk": 10, "approve": False}, uid=None)
    over("S4 bez prihlaseni 401/403, zakaznik 401/403", r_anon.status_code in (401, 403) and (r_user is None or r_user.status_code in (401, 403)), (r_anon.status_code, r_user and r_user.status_code))

    # ============================================================================================================ M) sazba montaze v nastaveni (zamestnanec)
    print("== M sazba montaze")

    def montaz(metoda, body=None, uid=admin_id):
        appmod._rate_limit_buckets.clear()
        return cla.open("/api/stul/montaz", method=metoda, json=body, headers=ck(uid) if uid else {}, base_url="https://admin.example.top")

    g0 = montaz("GET").get_json()
    over("M1 cteni: nenastaveno = vychozi 12 %, available true, stored false", g0["pct"] == 12.0 and g0["default"] == 12.0 and g0["available"] is True and g0["stored"] is False, g0)
    p1 = montaz("PUT", {"pct": 15.5})
    g1 = montaz("GET").get_json()
    q_after = quote([item(ODLISNA, 1, montaz=True)])
    over("M2 ulozeni 15,5 %: ulozeno, cteni, audit; kalkulace stolu hned pouziva novou sazbu (jedno rozhodnuti)", p1.status_code == 200 and g1["pct"] == 15.5 and g1["stored"] is True
         and abs(q_after.get_json()["lines"][0]["montaz_czk"] / float(NET1) * 100 - 15.5) < 0.1 and any(a[0][1] == "update" and "stul_montaz_pct" in str(a[0][4]) for a in AUDIT), (p1.get_json(), g1))
    zlo_m = {"pct_invalid": [{"pct": -1}, {"pct": 101}, {"pct": "abc"}, {"pct": True}, {"pct": None}, {"pct": ""}, {"pct": [12]}], "pct_required": [{}, {"x": 1}]}
    odp_m = [(kod, montaz("PUT", b)) for kod, bs in zlo_m.items() for b in bs]
    over("M3 validace: mimo 0-100, text, bool, null, pole = 400 pct_invalid, chybejici pct 400 pct_required; hodnota se nezmenila", all(r_.status_code == 400 and r_.get_json()["error"] == kod for kod, r_ in odp_m)
         and montaz("GET").get_json()["pct"] == 15.5, [(kod, r_.get_json()) for kod, r_ in odp_m if r_.status_code != 400 or r_.get_json()["error"] != kod])
    p0 = montaz("PUT", {"pct": 0})
    over("M4 0 = montaz se nenabizi (available false, kalkulace s montazi 409), 100 projde", p0.status_code == 200 and montaz("GET").get_json()["available"] is False and quote([item(montaz=True)]).status_code == 409 and montaz("PUT", {"pct": 100}).status_code == 200, p0.get_json())
    r_u = montaz("PUT", {"pct": 5}, uid=user_row[0]["id"]) if user_row else None
    r_a = montaz("PUT", {"pct": 5}, uid=None)
    g_u = montaz("GET", uid=user_row[0]["id"]) if user_row else None
    over("M5 zakaznik ani anonym sazbu nevidi ani nemeni (401/403), verejne API sazbu nevraci", r_a.status_code in (401, 403) and (r_u is None or r_u.status_code in (401, 403)) and (g_u is None or g_u.status_code in (401, 403))
         and "15.5" not in json.dumps(quote([item(montaz=True)]).get_json() if False else {}), (r_a.status_code, r_u and r_u.status_code))
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY + tuple(f"_tpl_{x}" for x in TEMP_LIKE + TEMP_COPY):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav()
over("ostre tabulky, nastaveni (sazba montaze, mapovani konfiguratoru), karta 4934, cislovani a audit jsou po testu beze zmeny", po == PRED, (PRED, po))
ok = sum(vysl)
print(f"\nVYSLEDEK objednavka hosta, montaz, doprava ke schvaleni: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
