#!/usr/bin/env python3
"""
JEDNORAZOVY skript (Robert 2026-07-31: "udelejme od kazdeho dokladu jeden
testovaci pohyb resp. jedna objednavka jednoho produktu vydej zalohova
faktura faktura dodaci list nejaky rezany plan musi byt polozka profil").

Na rozdil od scripts/random_test_data_generator.py (nahodny, davkovy,
bezel v cronu kazdou minutu - 2026-07-31 vypnut) tenhle udela PRESNE
JEDEN kompletni retez, deterministicky, a na konci vypise co vzniklo:

  1. Objednavka (2 polozky: bezny produkt + profil 30x30 pro rezny plan)
  2. Prijemka na sklad (movement_type=receipt)
  3. Vydej ze skladu (vznikne automaticky pri potvrzeni objednavky)
  4. Zalohova faktura (proforma_invoice)
  5. Danovy doklad k prijate platbe (payment_tax_document / VDD)
  6. Faktura (invoice)
  7. Dodaci list (delivery_note)
  8. Rezny plan (potrebuje polozku s cut_kind='profil')
  9. Nakupni objednavka + prijem zbozi
 10. E-mail (potvrzeni objednavky zakaznikovi)

Vse pres HTTP API (projdou business pravidla appky) - jedina vyjimka je
nastaveni cut_kind/material_key/length_mm na polozce objednavky, pro
ktere zadny endpoint neexistuje (stejne jako u puvodniho generatoru).

Spusteni:  /opt/konfigurator/api/venv/bin/python3 scripts/one_full_test_chain.py
"""
import datetime
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "/opt/konfigurator/api")
import pymysql

BASE = "http://127.0.0.1:8090"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = "/opt/konfigurator/api/.env"

PROFILE_MATERIAL_KEY = "30x30"   # musi sedet se shop_cutting_stock.material_key
PROFILE_LENGTH_MM = 1200


def env(key):
    for line in open(ENV_FILE):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return None


def db_conn():
    return pymysql.connect(host=env("DB_HOST"), user=env("DB_USER"), password=env("DB_PASSWORD"),
                           database=env("DB_NAME"), cursorclass=pymysql.cursors.DictCursor)


def api(opener, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def step(n, text):
    print(f"[{n}] {text}")


def main():
    if len(sys.argv) < 3:
        print("Pouziti: one_full_test_chain.py <admin_email> <heslo>")
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    s, r = api(opener, "POST", "/api/auth/login", {"email": email, "password": password})
    if s != 200:
        print(f"Prihlaseni selhalo: {s} {r}")
        sys.exit(1)

    created = {}

    # --- vybrat bezny produkt se skladem + zajistit profilovy produkt ---
    s, r = api(opener, "GET", "/api/shop/products?all=1&page_size=500")
    products = [p for p in r.get("products", []) if p.get("active") and not p.get("is_archived")]
    in_stock = [p for p in products if (p.get("stock_qty") or 0) > 0]
    if not in_stock:
        print("Zadny produkt se skladem - koncim.")
        sys.exit(1)
    normal = in_stock[0]

    profile = next((p for p in products if "Profil 30x30" in (p.get("name") or "")), None)
    if not profile:
        s, r = api(opener, "POST", "/api/shop/products", {
            "sku": "TESTCHAIN-30x30", "name": "Profil 30x30 (testovací řetěz)",
            "description": "Založeno skriptem one_full_test_chain.py pro řezný plán.",
            "unit": "mm", "price_czk_placeholder": 45.0, "active": True,
        })
        if s not in (200, 201):
            print(f"Zalozeni profilu selhalo: {s} {r}")
            sys.exit(1)
        profile = {"id": r["id"], "name": "Profil 30x30 (testovací řetěz)"}
        step("*", f"založen profilový produkt id={profile['id']}")

    # --- 2) PRIJEMKA na sklad ---
    s, r = api(opener, "POST", "/api/shop/stock/movements", {
        "product_id": profile["id"], "movement_type": "receipt", "qty": 50,
        "unit_price_czk": 45.0, "note": "Testovací řetěz - příjemka",
    })
    created["prijemka"] = r.get("id")
    step(2, f"příjemka na sklad: pohyb id={r.get('id')} ({s})")

    # --- 1) OBJEDNAVKA (bezny produkt + profil) ---
    s, r = api(opener, "GET", "/api/payment-methods")
    pms = r.get("methods", []) if s == 200 else []
    s, r = api(opener, "GET", "/api/shipping-methods")
    sms = r.get("methods", []) if s == 200 else []

    body = {
        "items": [{"product_id": normal["id"], "qty": 2},
                  {"product_id": profile["id"], "qty": 3}],
        "customer_name": "Testovací řetěz s.r.o.",
        "customer_email": "robert.mandik@gmail.com",
        "customer_phone": "+420777123456",
        "delivery_address": "Testovací 123, 100 00 Praha",
        "delivery_zip": "10000",
        "note": "Kompletní testovací řetěz (one_full_test_chain.py)",
    }
    if pms:
        body["payment_method_id"] = pms[0]["id"]
    if sms:
        body["shipping_method_id"] = sms[0]["id"]
    s, r = api(opener, "POST", "/api/admin/orders", body)
    if s not in (200, 201):
        print(f"Objednavka selhala: {s} {r}")
        sys.exit(1)
    order_id, order_number = r["id"], r.get("order_number")
    created["objednavka"] = f"{order_number} (id={order_id})"
    step(1, f"objednávka {order_number} (id={order_id}), 2 položky")

    # --- polozka profilu -> rezny plan (jediny primy SQL, viz docstring) ---
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_order_items WHERE order_id=%s AND product_id=%s LIMIT 1",
                        (order_id, profile["id"]))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE shop_order_items SET cut_kind='profil', material_key=%s, length_mm=%s WHERE id=%s",
                            (PROFILE_MATERIAL_KEY, PROFILE_LENGTH_MM, row["id"]))
        conn.commit()
    finally:
        conn.close()
    step("*", f"položka profilu označena pro řezný plán ({PROFILE_MATERIAL_KEY}, {PROFILE_LENGTH_MM} mm)")

    # --- 3) VYDEJ (potvrzeni objednavky snizi sklad + zapise pohyb) ---
    s, r = api(opener, "PUT", f"/api/admin/orders/{order_id}",
               {"status": "potvrzena", "history_note": "Testovací řetěz - potvrzeno"})
    step(3, f"objednávka potvrzena -> výdej ze skladu ({s})")

    # --- 4-7) DOKLADY ---
    s, r = api(opener, "POST", f"/api/admin/orders/{order_id}/documents/proforma")
    created["zalohova_faktura"] = r.get("document_number")
    step(4, f"zálohová faktura: {r.get('document_number')} ({s})")

    s, r = api(opener, "POST", f"/api/admin/orders/{order_id}/documents/payment-received", {})
    created["vdd"] = r.get("document_number")
    step(5, f"daňový doklad k přijaté platbě: {r.get('document_number')} ({s})")

    s, r = api(opener, "POST", f"/api/admin/orders/{order_id}/documents/invoice")
    created["faktura"] = r.get("document_number")
    step(6, f"faktura: {r.get('document_number')} ({s})")

    s, r = api(opener, "POST", f"/api/admin/orders/{order_id}/documents/delivery-note")
    created["dodaci_list"] = r.get("document_number")
    step(7, f"dodací list: {r.get('document_number')} ({s})")

    # --- 8) REZNY PLAN ---
    s, r = api(opener, "POST", "/api/admin/cutting-plan/generate", {})
    created["rezny_plan"] = "ano" if s in (200, 201) else f"CHYBA {s} {r}"
    step(8, f"řezný plán: {s} {json.dumps(r, ensure_ascii=False)[:120]}")

    # --- 9) NAKUPNI OBJEDNAVKA + prijem zbozi ---
    s, r = api(opener, "POST", "/api/admin/purchase-orders", {
        "supplier_name": "Testovací dodavatel s.r.o.",
        "note": f"Navazující nákupní objednávka k {order_number} (testovací řetěz)",
        "items": [{"product_id": normal["id"], "qty": 20, "unit_price_czk": 15.0},
                  {"product_id": profile["id"], "qty": 40, "unit_price_czk": 42.0}],
    })
    po_id, po_number = r.get("id"), r.get("po_number")
    created["nakupni_objednavka"] = f"{po_number} (id={po_id})"
    step(9, f"nákupní objednávka {po_number} (id={po_id}) ({s})")

    if po_id:
        api(opener, "PUT", f"/api/admin/purchase-orders/{po_id}", {"status": "odeslano"})
        s, r = api(opener, "GET", f"/api/admin/purchase-orders/{po_id}")
        items = (r.get("purchase_order") or r).get("items", []) if s == 200 else []
        recv = [{"item_id": it["id"], "qty": it["qty_ordered"]} for it in items]
        if recv:
            s, r = api(opener, "POST", f"/api/admin/purchase-orders/{po_id}/receive",
                       {"items": recv, "note": "Testovací řetěz - příjem zboží"})
            step("9b", f"příjem zboží na NO: {s}")

    # --- 10) E-MAIL potvrzeni objednavky ---
    s, r = api(opener, "POST", f"/api/admin/orders/{order_id}/emails",
               {"kind": "order_confirmation"})
    created["email"] = f"{s}"
    step(10, f"e-mail (potvrzení objednávky): {s} {json.dumps(r, ensure_ascii=False)[:120]}")

    print("\n=== VYTVORENO ===")
    for k, v in created.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
