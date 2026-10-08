#!/usr/bin/env python3
"""Import historickych objednavek z CSV (Upgates-style export) do
shop_orders/shop_order_items.

Robert (pres bot3-koordinatora, 2026-08-21, PRIORITNI pred formatovaci
opravou Poptavky): "import" - jednorazovy prevod historickych
objednavek z puvodniho e-shopu do Konfiguratoru. Zdrojovy soubor
`scripts/2026-08-21_orders_import_source.csv` (139 KB, 216 radku /
39 objednavek).

Format CSV (analyza bot3, overeno zde znovu na realnych datech):
- kodovani Windows-1250 (cp1250), NE utf-8 - jinak se znici ceske znaky.
- oddelovac strednik ';', cteno Python `csv` modulem (ne naivni split -
  napr. "remark" ma casto vicerádkovy text uvnitr uvozovek).
- kazdy radek CSV = JEDNA POLOZKA objednavky, hlavickova data
  (code/date/statusName/zakaznik/adresy/totaly) se OPAKUJI na kazdem
  radku se stejnym "code" - radky se seskupi podle "code" (=
  order_number) pred zpracovanim. Overeno: hlavickova pole jsou
  bezezbytku shodna napric vsemi radky stejneho "code" (0 nesrovnalosti
  na vsech 39 objednavkach).
- radky s itemCode zacinajicim "SHIPPING"/"BILLING" NEJSOU realne
  produkty - jejich itemName/itemUnitPriceWithVat se pouzije na
  vyplneni shop_orders.shipping_method_name/shipping_price_czk resp.
  payment_method_name/payment_price_czk, do shop_order_items se
  nevkladaji.
- realne polozky: itemCode se paruje na shop_products.sku (presna
  shoda, zadna duplicita SKU v katalogu overena) -> product_id +
  product_name_snapshot z DB (stejna konvence jako
  api/orders.py::create_order - snapshot = aktualni nazev produktu z
  DB, ne CSV text). Bez shody (prazdny itemCode nebo kod mimo katalog -
  vlastni polozky "vestavba dle nabidky ...", REZ_*, SROUB.IMB.*,
  ZAVRT.MAT.*, UUID-styl kody) -> product_id=NULL,
  product_name_snapshot = cely itemName text z CSV. Import NEBLOKUJE
  kvuli nenalezene SKU, jen na konci vypise souhrn nesparovanych kodu
  (26/150 realnych polozek v tomto souboru, presne odpovida bot3ove
  odhadu).
- statusName -> shop_orders.status mapovani, viz STATUS_MAP nize.
  "Čeká" -> "ceka_na_zbozi" je bot3uv ODHAD (ne jistota) - pokud
  nekdo najde duvod pochybovat, nahlasit Robertovi/bot3, jinak pouzit.
- cenova pole: "With Vat" varianty (itemUnitPriceWithVat,
  itemTotalPriceWithVat, header totalPriceWithVat) jsou zdroj pravdy
  pro CZK sloupce (system pracuje v cenach s DPH). Header
  totalPriceWithVat se pouzije PRIMO jako shop_orders.total_czk (ne
  prepocitavano ze souctu polozek) - u 2 zrusenych (Storno) objednavek
  je v CSV 0,00 i pres nenulove polozky, to odpovida puvodnimu systemu
  (zrusena objednavka = neucotvana castka), nemenit.
- idempotence (Robert: "duplicitní položky ignoruj"): pred vlozenim se
  kontroluje, jestli uz shop_orders.order_number s timhle "code"
  existuje - pokud ano, CELA objednavka se preskoci. Skript jde bezpecne
  spustit znovu na prekryvajici se data.

Edge-case nalezy behem analyzy (zapsano i do AGENTS_LOG.md):
- 2 objednavky (26080058, 26080087) maji PRAZDNE email/phone/billFullName
  (zbytek profilu - adresa, castka - je vyplneny normalne) - NOT NULL
  sloupce customer_name/customer_email v shop_orders vyzaduji fallback,
  viz `_customer_fallback()` nize. Oznaceno v souhrnu na konci behu.
- 1 polozka (objednavka 26080088, kod 1.1.08.030030.03) ma neceloci
  itemAmount "14,5" (jednotka "ks", zjevne pulka kusu/rezany kus) -
  shop_order_items.qty je INT, zaokrouhleno standardnim round() na 14 -
  penezni castka (line_total_czk) se pocita PRIMO z CSV, ne z qty *
  unit_price, takze zaokrouhleni qty neovlivni ucetni soucet.

Pouziti:
    api/venv/bin/python3 scripts/2026-08-21_orders_csv_import.py            # dry-run (nic nezapise)
    api/venv/bin/python3 scripts/2026-08-21_orders_csv_import.py --apply    # skutecny zapis
"""
import argparse
import csv
import os
import re
import sys

CSV_PATH = os.path.join(os.path.dirname(__file__), "2026-08-21_orders_import_source.csv")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")

STATUS_MAP = {
    "Fakturováno": "fakturovana",
    "Expedováno": "expedovana",
    "Storno": "zrusena",
    "Připravit": "pripravit",
    "Připravit/Skladem": "pripravit",
    "Čeká": "ceka_na_zbozi",  # bot3uv odhad, viz docstring vyse
}


def load_env():
    """Nejdriv os.environ (systemd EnvironmentFile), fallback na primy
    parse api/.env - stejny vzor jako ostatni skripty v tomto adresari."""
    if all(k in os.environ for k in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")):
        return dict(os.environ)
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def get_db_conn(env):
    import pymysql
    return pymysql.connect(
        host=env.get("DB_HOST", "127.0.0.1"), port=int(env.get("DB_PORT", 3306)),
        user=env["DB_USER"], password=env["DB_PASSWORD"],
        database=env.get("DB_NAME") or env.get("DB_DATABASE"),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def parse_czk(s):
    s = (s or "").strip()
    if not s:
        return 0.0
    return float(s.replace("\xa0", "").replace(" ", "").replace(",", "."))


def parse_qty(s):
    s = (s or "").strip()
    if not s:
        return 1
    return int(round(float(s.replace(",", "."))))


def fmt_address(street, house_number, zip_code, city, country):
    line1 = " ".join(p for p in (street.strip(), house_number.strip()) if p)
    line2 = " ".join(p for p in (zip_code.strip(), city.strip()) if p)
    parts = [p for p in (line1, line2, country.strip()) if p]
    return ", ".join(parts) or None


def clean_zip(z):
    digits = re.sub(r"\D", "", z or "")
    return digits[:6] or None


def group_orders(rows):
    orders = {}
    order_seq = []
    for r in rows:
        code = r["code"]
        if code not in orders:
            orders[code] = []
            order_seq.append(code)
        orders[code].append(r)
    return [(code, orders[code]) for code in order_seq]


def _customer_fallback(h, code):
    """Par objednavek v tomto exportu ma uplne prazdne email/jmeno (viz
    docstring modulu) - customer_name/customer_email jsou v shop_orders
    NOT NULL, takze potrebuji nejaky zapis. Zretelne oznaceny placeholder
    (ne tichy podvrh), aby admin pri prohlizeni hned poznal, ze jde o
    dovezeny zaznam bez zachyceneho kontaktu, ne o skutecny e-mail."""
    name = h["billFullName"].strip() or h["deliveryFullName"].strip() or h["billCompany"].strip()
    email = h["email"].strip().lower()
    used_fallback = False
    if not name:
        name = f"Import bez jména ({code})"
        used_fallback = True
    if not email:
        email = f"import-bez-emailu-{code}@bez-udaju.invalid"
        used_fallback = True
    return name, email, used_fallback


def build_order(code, items_raw, sku_to_product):
    h = items_raw[0]

    shipping_method_name, shipping_price = None, 0.0
    payment_method_name, payment_price = None, 0.0
    order_items = []
    unmatched = []

    for r in items_raw:
        item_code = (r["itemCode"] or "").strip()
        if item_code.startswith("SHIPPING"):
            shipping_method_name = r["itemName"].strip() or None
            shipping_price = parse_czk(r["itemUnitPriceWithVat"])
            continue
        if item_code.startswith("BILLING"):
            payment_method_name = r["itemName"].strip() or None
            payment_price = parse_czk(r["itemUnitPriceWithVat"])
            continue

        product = sku_to_product.get(item_code) if item_code else None
        if product:
            product_id = product["id"]
            name_snapshot = product["name"]
        else:
            product_id = None
            name_snapshot = r["itemName"].strip() or item_code or "(bez názvu)"
            unmatched.append((code, item_code, r["itemName"].strip()))

        order_items.append({
            "product_id": product_id,
            "product_name_snapshot": name_snapshot[:255],
            "unit_price_czk": parse_czk(r["itemUnitPriceWithVat"]),
            "qty": parse_qty(r["itemAmount"]),
            "line_total_czk": parse_czk(r["itemTotalPriceWithVat"]),
        })

    status = STATUS_MAP.get(h["statusName"].strip())
    status_warning = None
    if status is None:
        status_warning = h["statusName"]
        status = "nova"

    delivery_address = fmt_address(
        h["deliveryStreet"], h["deliveryHouseNumber"], h["deliveryZip"], h["deliveryCity"], h["deliveryCountryName"]
    )
    billing_address = fmt_address(
        h["billStreet"], h["billHouseNumber"], h["billZip"], h["billCity"], h["billCountryName"]
    )
    if not delivery_address:
        delivery_address = billing_address

    customer_name, customer_email, used_contact_fallback = _customer_fallback(h, code)
    billing_name = h["billCompany"].strip() or h["billFullName"].strip() or customer_name

    order = {
        "order_number": code.strip(),
        "status": status,
        "status_warning": status_warning,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "used_contact_fallback": used_contact_fallback,
        "customer_phone": h["phone"].strip() or None,
        "delivery_address": delivery_address,
        "delivery_zip": clean_zip(h["deliveryZip"] or h["billZip"]),
        "billing_name": billing_name,
        "billing_ico": h["companyId"].strip() or None,
        "billing_dic": h["vatId"].strip() or None,
        "billing_address": billing_address,
        "shipping_method_name": shipping_method_name,
        "shipping_price_czk": shipping_price,
        "payment_method_name": payment_method_name,
        "payment_price_czk": payment_price,
        "note": h["remark"].strip() or None,
        "admin_note": h["shopRemark"].strip() or None,
        "total_czk": parse_czk(h["totalPriceWithVat"]),
        "created_at": h["date"].strip(),
        "items": order_items,
    }
    return order, unmatched


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Skutečně zapsat do DB. Bez této volby jen dry-run.")
    args = ap.parse_args()

    with open(CSV_PATH, encoding="cp1250", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    env = load_env()
    conn = get_db_conn(env)
    cur = conn.cursor()

    cur.execute("SELECT id, sku, name FROM shop_products WHERE sku IS NOT NULL AND sku<>''")
    sku_to_product = {r["sku"]: r for r in cur.fetchall()}

    groups = group_orders(rows)
    print(f"Načteno {len(rows)} řádků CSV, {len(groups)} objednávek.")

    to_insert = []
    skipped_existing = []
    all_unmatched = []
    status_warnings = {}
    contact_fallback_orders = []

    for code, items_raw in groups:
        order, unmatched = build_order(code, items_raw, sku_to_product)
        all_unmatched.extend(unmatched)
        if order["status_warning"]:
            status_warnings[order["order_number"]] = order["status_warning"]
        if order["used_contact_fallback"]:
            contact_fallback_orders.append(order["order_number"])

        cur.execute("SELECT id FROM shop_orders WHERE order_number=%s", (order["order_number"],))
        if cur.fetchone():
            skipped_existing.append(order["order_number"])
            continue
        to_insert.append(order)

    print(f"K vložení: {len(to_insert)} objednávek, přeskočeno (už existují): {len(skipped_existing)}")
    if skipped_existing:
        print(f"  přeskočené order_number: {skipped_existing}")
    if status_warnings:
        print("POZOR - neznámý statusName (dosazeno 'nova', ověřit ručně):")
        for on, s in status_warnings.items():
            print(f"  {on}: {s!r}")
    if contact_fallback_orders:
        print(f"POZOR - objednávky bez e-mailu/jména v CSV, doplněn placeholder: {contact_fallback_orders}")

    if not args.apply:
        print("\n(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")
        for order in to_insert:
            print(f"  {order['order_number']} | {order['status']} | {order['customer_name']} | "
                  f"{order['total_czk']} Kč | {len(order['items'])} položek")
    else:
        inserted_orders = 0
        inserted_items = 0
        for order in to_insert:
            cur.execute(
                "INSERT INTO shop_orders "
                "(order_number, status, is_urgent, user_id, customer_name, customer_email, "
                " customer_phone, delivery_address, delivery_zip, note, admin_note, "
                " billing_name, billing_ico, billing_dic, billing_address, "
                " shipping_method_name, shipping_price_czk, payment_method_name, payment_price_czk, "
                " total_czk, created_at) "
                "VALUES (%s,%s,0,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (order["order_number"], order["status"], order["customer_name"], order["customer_email"],
                 order["customer_phone"], order["delivery_address"], order["delivery_zip"],
                 order["note"], order["admin_note"],
                 order["billing_name"], order["billing_ico"], order["billing_dic"], order["billing_address"],
                 order["shipping_method_name"], order["shipping_price_czk"],
                 order["payment_method_name"], order["payment_price_czk"],
                 order["total_czk"], order["created_at"]),
            )
            order_id = cur.lastrowid
            for oi in order["items"]:
                cur.execute(
                    "INSERT INTO shop_order_items "
                    "(order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (order_id, oi["product_id"], oi["product_name_snapshot"],
                     oi["unit_price_czk"], oi["qty"], oi["line_total_czk"]),
                )
                inserted_items += 1
            inserted_orders += 1
        conn.commit()
        print(f"\nZAPSÁNO: {inserted_orders} objednávek, {inserted_items} položek.")

    if all_unmatched:
        print(f"\nNespárované položky (bez SKU shody, product_id=NULL): {len(all_unmatched)}")
        codes = {}
        for order_number, code, name in all_unmatched:
            codes.setdefault(code or "(prázdný)", []).append((order_number, name))
        for code, occurrences in sorted(codes.items()):
            print(f"  {code!r} ({len(occurrences)}×) - např. {occurrences[0][1]!r}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
