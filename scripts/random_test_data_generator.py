#!/usr/bin/env python3
"""
Generator nahodnych testovacich dat (Robert 2026-07-26): "kazdou minutu
zaloz 2 az 5 nahodnych objednavek i navazujici nakupni objednavky, at
to obsahuje polozky ktere je potreba delat reznym planem (v pripade
potreby zaloz takovou polozku jako novou), kazdou druhou minutu to
vyfakturuj/vyexpeduj, pridej dobirku/platbu predem/zalohove faktury -
mix moznosti at to otestujem".

Bezi jako CRON uloha KAZDOU MINUTU (viz crontab -l). Jeden beh:

1. VZDY: vytvori 2-5 novych objednavek pres verejne/administratorske
   API (ne primym zapisem do DB - tim padem projdou vsechny business
   pravidla appky - cenotvorba, slevy, sklad...). Nahodni zakaznici,
   nahodne produkty, nahodna platebni/dopravni metoda. Vetsina
   objednavek dostane i polozku profilu 30x30 (jedina prurezova
   promenna se skutecne nastavenym skladem v shop_cutting_stock, jinak
   by "Generovat rezny plan" nemel s cim pracovat) - pokud takovy
   produkt v katalogu chybi, skript ho sam zalozi. K objednavce rovnou
   vytvori navazujici nakupni objednavku se stejnymi produkty.

2. KAZDOU SUDOU MINUTU (datetime.now().minute % 2 == 0): posune
   zivotni cyklus existujicich otevrenych objednavek a nakupnich
   objednavek - status, fakturace/zalohova faktura/prijeti platby/
   dodaci list (podle toho, co GET .../documents rika, ze je zrovna
   legalni), prijem zbozi na NO.

DULEZITE - jedina vec, kterou API neumoznuje (overeno pred napsanim
tohoto skriptu, viz AGENTS_LOG.md): nastavit cut_kind/material_key/
length_mm na polozce objednavky (`shop_order_items`) - zadny endpoint
pro to neexistuje nikde v api/*.py. Tenhle skript proto pro TENHLE JEDEN
konkretni ucel pouziva primy SQL UPDATE (funkce
`_mark_order_item_as_cutting_profile`), vse ostatni jde pres HTTP API.

STOP tohoto generatoru (2 zpusoby, staci jeden):
  1. touch /opt/konfigurator/scripts/.test_data_generator_stop
     (skript na zacatku existenci souboru zkontroluje a pokud existuje,
     okamzite skonci beze zmeny - smazanim souboru se zase spusti)
  2. crontab -e -> smazat radek s "random_test_data_generator.py"
       (crontab -l pro zobrazeni aktualniho seznamu)

Pouziva dedikovany ucet "testgen@konfigurator.local" (role admin,
zalozen bot6 2026-07-26 vyhradne pro tenhle generator) - heslo v
gitignorovanem `scripts/.test_data_generator_credentials`.
"""
import datetime
import http.cookiejar
import json
import os
import random
import string
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STOP_FILE = os.path.join(SCRIPT_DIR, ".test_data_generator_stop")
LOG_FILE = os.path.join(SCRIPT_DIR, "test_data_generator.log")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, ".test_data_generator_credentials")
BASE_URL = "http://127.0.0.1:8090"

PROFILE_MATERIAL_KEY = "30x30"
PROFILE_PRODUCT_NAME_HINT = "30x30 Heavy Sigma Profile"
PROFILE_LENGTHS_MM = [500, 800, 1000, 1200, 1500, 1800, 2000, 2500, 2900]

FIRST_NAMES = ["Jan", "Petr", "Pavel", "Tomáš", "Martin", "Lucie", "Eva", "Petra", "Jana", "Michal", "Karel", "Zdeněk", "Hana", "Věra"]
LAST_NAMES = ["Novák", "Svoboda", "Novotný", "Dvořák", "Černý", "Procházka", "Kučera", "Veselý", "Krejčí", "Horák", "Němec", "Pokorný"]
SUPPLIER_NAMES = ["Alunet s.r.o.", "Profilmetal a.s.", "Dogus Kalip CZ s.r.o.", "Hliníkservis spol. s r.o.", "AL-Profily Group"]


def log(msg):
    line = f"{datetime.datetime.now().isoformat()} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_credentials():
    if not os.path.isfile(CREDENTIALS_FILE):
        log(f"CHYBA: {CREDENTIALS_FILE} neexistuje - generator nema jak se prihlasit.")
        sys.exit(1)
    creds = {}
    with open(CREDENTIALS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            creds[k] = v
    return creds.get("EMAIL"), creds.get("PASSWORD")


def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def api(opener, method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers)
    try:
        with opener.open(req, timeout=20) as r:
            raw = r.read()
            return r.status, (json.loads(raw.decode("utf-8")) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return e.code, {"error": raw.decode("utf-8", errors="replace")}


def db_conn():
    import pymysql
    env = {}
    with open(os.path.join(SCRIPT_DIR, "..", "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k, v)
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
        user=env["DB_USER"], password=env["DB_PASSWORD"], database=env["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def random_customer():
    fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
    name = f"{fn} {ln}"
    tag = "".join(random.choices(string.digits, k=5))
    email = f"testgen.{fn}.{ln}.{tag}@example.cz".lower()
    return name, email


def random_phone():
    return "+420" + "".join(random.choices(string.digits, k=9))


def ensure_cutting_profile_product(opener):
    status, resp = api(opener, "GET", "/api/shop/products?page_size=500")
    products = resp.get("products", []) if status == 200 else []
    for p in products:
        if PROFILE_PRODUCT_NAME_HINT in (p.get("name") or ""):
            return p
    sku = "TESTGEN-30x30-" + "".join(random.choices(string.digits, k=6))
    body = {
        "sku": sku, "name": f"{PROFILE_PRODUCT_NAME_HINT} (testgen)",
        "description": "Automaticky zalozeno generatorem testovacich dat pro rezny plan.",
        "unit": "mm", "price_czk_placeholder": 45.0, "active": True,
    }
    status, resp = api(opener, "POST", "/api/shop/products", body)
    if status not in (200, 201):
        log(f"  nepodarilo se zalozit profil produkt: {status} {resp}")
        return None
    new_id = resp["id"]
    api(opener, "POST", "/api/shop/stock/movements", {
        "product_id": new_id, "movement_type": "receipt", "qty": 200,
        "unit_price_czk": 45.0, "note": "testgen - pocatecni sklad pro rezny plan",
    })
    log(f"  zalozen novy produkt pro rezny plan: {sku} (id={new_id})")
    return {"id": new_id, "sku": sku, "name": f"{PROFILE_PRODUCT_NAME_HINT} (testgen)"}


def mark_order_item_as_cutting_profile(order_id, product_id):
    # Jediny primy SQL zasah v tomhle skriptu - viz docstring modulu:
    # zadny HTTP endpoint neumoznuje nastavit cut_kind/material_key/
    # length_mm na polozce objednavky.
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM shop_order_items WHERE order_id=%s AND product_id=%s LIMIT 1",
                (order_id, product_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            length_mm = random.choice(PROFILE_LENGTHS_MM)
            cur.execute(
                "UPDATE shop_order_items SET cut_kind='profil', material_key=%s, length_mm=%s WHERE id=%s",
                (PROFILE_MATERIAL_KEY, length_mm, row["id"]),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def create_orders_and_purchase_orders(opener):
    status, resp = api(opener, "GET", "/api/shop/products?page_size=3000")
    if status != 200:
        log(f"GET /api/shop/products selhalo: {status} {resp}")
        return
    products = [p for p in resp.get("products", []) if p.get("active") and not p.get("is_archived")]
    if not products:
        log("Zadne aktivni produkty v katalogu, preskakuji tvorbu objednavek.")
        return
    # Vetsina katalogu ma stock_qty=0 (import ze Shoptet bez realneho
    # skladu) - kdyby vyber byl cisty nahodny, skoro zadna objednavka by
    # nikdy neprosla prechodem nova->potvrzena (blokuje ho nedostatek
    # skladu) a "vyfakturuj/vyexpeduj" faze by nemela co delat. Proto
    # preferujeme produkty se skladem (realisticky "obvykle je skladem,
    # obcas neni" mix), ne uplne nahodny vyber z celeho katalogu.
    in_stock = [p for p in products if (p.get("stock_qty") or 0) > 0]

    profile_product = ensure_cutting_profile_product(opener)

    pm_status, pm_resp = api(opener, "GET", "/api/payment-methods")
    payment_methods = pm_resp.get("methods", []) if pm_status == 200 else []
    sm_status, sm_resp = api(opener, "GET", "/api/shipping-methods")
    shipping_methods = sm_resp.get("methods", []) if sm_status == 200 else []

    n = random.randint(2, 5)
    log(f"=== tvorba {n} novych objednavek ===")
    for _ in range(n):
        name, email = random_customer()
        pool = in_stock if in_stock and random.random() < 0.85 else products
        k = min(random.randint(1, 3), len(pool))
        chosen = random.sample(pool, k=k)
        items = [{"product_id": p["id"], "qty": random.randint(1, 5)} for p in chosen]

        needs_cutting = profile_product is not None and random.random() < 0.6
        if needs_cutting:
            items.append({"product_id": profile_product["id"], "qty": random.randint(1, 4)})

        body = {
            "items": items,
            "customer_name": name,
            "customer_email": email,
            "customer_phone": random_phone(),
            "delivery_address": "Testovací 123, 100 00 Praha",
            "delivery_zip": "10000",
            "note": "Automaticky testovací objednávka (testgen)",
        }
        if payment_methods:
            body["payment_method_id"] = random.choice(payment_methods)["id"]
        if shipping_methods:
            body["shipping_method_id"] = random.choice(shipping_methods)["id"]

        status, resp = api(opener, "POST", "/api/admin/orders", body)
        if status not in (200, 201):
            log(f"  objednavka selhala: {status} {resp}")
            continue
        order_id, order_number = resp["id"], resp.get("order_number")
        log(f"  {order_number} (id={order_id}): {len(items)} položek, cutting={needs_cutting}, "
            f"platba={body.get('payment_method_id')}")

        if needs_cutting:
            ok = mark_order_item_as_cutting_profile(order_id, profile_product["id"])
            if not ok:
                log(f"    pozn.: polozku profilu se nepodarilo najit pro nastaveni rozmeru")

        po_items = [
            {"product_id": p["id"], "qty": random.randint(10, 50), "unit_price_czk": round(random.uniform(20, 300), 2)}
            for p in chosen
        ]
        if needs_cutting:
            po_items.append({
                "product_id": profile_product["id"], "qty": random.randint(20, 100),
                "unit_price_czk": round(random.uniform(30, 60), 2),
            })
        po_body = {
            "supplier_name": random.choice(SUPPLIER_NAMES),
            "note": f"Navazující nákupní objednávka k {order_number} (testgen)",
            "items": po_items,
        }
        po_status, po_resp = api(opener, "POST", "/api/admin/purchase-orders", po_body)
        if po_status not in (200, 201):
            log(f"    navazujici NO selhala: {po_status} {po_resp}")
        else:
            log(f"    navazujici NO: {po_resp.get('po_number')}")


def randomize_order_lifecycle(opener):
    log("=== posun zivotniho cyklu existujicich objednavek/NO ===")

    status, resp = api(opener, "GET", "/api/admin/orders?status=nova&page_size=50")
    orders = resp.get("orders", []) if status == 200 else []
    for o in random.sample(orders, k=min(random.randint(1, 3), len(orders))) if orders else []:
        s, r = api(opener, "PUT", f"/api/admin/orders/{o['id']}", {"status": "potvrzena", "history_note": "testgen: auto-potvrzeno"})
        log(f"  {o.get('order_number')}: nova -> potvrzena ({s})")

    status, resp = api(opener, "GET", "/api/admin/orders?status=potvrzena&page_size=50")
    orders = resp.get("orders", []) if status == 200 else []
    for o in random.sample(orders, k=min(random.randint(1, 3), len(orders))) if orders else []:
        oid = o["id"]
        if random.random() < 0.5:
            api(opener, "PUT", f"/api/admin/orders/{oid}", {"status": "pripravit"})
            log(f"  {o.get('order_number')}: potvrzena -> pripravit")
        s, docinfo = api(opener, "GET", f"/api/admin/orders/{oid}/documents")
        actions = docinfo.get("actions", {}) if s == 200 else {}
        if actions.get("can_issue_proforma"):
            api(opener, "POST", f"/api/admin/orders/{oid}/documents/proforma")
            log(f"  {o.get('order_number')}: zálohová faktura vystavena")
        if actions.get("can_mark_payment_received") and random.random() < 0.7:
            api(opener, "POST", f"/api/admin/orders/{oid}/documents/payment-received", {})
            log(f"  {o.get('order_number')}: platba přijata")
        if actions.get("can_issue_invoice") and random.random() < 0.6:
            api(opener, "POST", f"/api/admin/orders/{oid}/documents/invoice")
            log(f"  {o.get('order_number')}: faktura vystavena")
        if actions.get("can_issue_delivery_note") and random.random() < 0.5:
            api(opener, "POST", f"/api/admin/orders/{oid}/documents/delivery-note")
            log(f"  {o.get('order_number')}: dodací list vystaven")

    status, resp = api(opener, "GET", "/api/admin/orders?status=pripravit&page_size=50")
    orders = resp.get("orders", []) if status == 200 else []
    for o in random.sample(orders, k=min(random.randint(1, 2), len(orders))) if orders else []:
        api(opener, "PUT", f"/api/admin/orders/{o['id']}", {"status": "hotova"})
        log(f"  {o.get('order_number')}: pripravit -> hotova")

    status, resp = api(opener, "GET", "/api/admin/purchase-orders?status=navrh&page_size=50")
    pos = resp.get("purchase_orders", []) if status == 200 else []
    for po in random.sample(pos, k=min(random.randint(1, 3), len(pos))) if pos else []:
        s, r = api(opener, "PUT", f"/api/admin/purchase-orders/{po['id']}", {"status": "odeslano"})
        log(f"  NO {po.get('po_number')}: navrh -> odeslano ({s})")

    status, resp = api(opener, "GET", "/api/admin/purchase-orders?status=odeslano&page_size=50")
    pos = resp.get("purchase_orders", []) if status == 200 else []
    for po in random.sample(pos, k=min(random.randint(1, 2), len(pos))) if pos else []:
        s, detail = api(opener, "GET", f"/api/admin/purchase-orders/{po['id']}")
        if s != 200:
            continue
        items = detail.get("items", [])
        if not items:
            continue
        receive_items = []
        for it in items:
            remaining = it.get("qty_ordered", 0) - it.get("qty_received", 0)
            if remaining > 0:
                receive_items.append({"item_id": it["id"], "qty": random.randint(1, remaining)})
        if receive_items:
            s2, r2 = api(opener, "POST", f"/api/admin/purchase-orders/{po['id']}/receive",
                          {"items": receive_items, "note": "testgen: automaticky castecny/plny prijem"})
            log(f"  NO {po.get('po_number')}: prijem zbozi ({s2})")


def main():
    if os.path.exists(STOP_FILE):
        log(f"STOP soubor {STOP_FILE} existuje - koncim beze zmeny.")
        return

    email, password = load_credentials()
    opener = make_opener()
    status, resp = api(opener, "POST", "/api/auth/login", {"email": email, "password": password})
    if status != 200:
        log(f"Prihlaseni selhalo: {status} {resp}")
        return

    create_orders_and_purchase_orders(opener)

    if datetime.datetime.now().minute % 2 == 0:
        randomize_order_lifecycle(opener)

    log("--- beh dokoncen ---")


if __name__ == "__main__":
    main()
