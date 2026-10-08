#!/usr/bin/env python3
"""!!! DEPRECATED - NESPOUSTET !!! (bot10, 2026-08-22, pozdeji tehoz dne)

Tenhle skript vychazel z MYLNEHO predpokladu - viz AGENTS_LOG.md zaznam
"OMYL, revert" ze stejneho dne. Robert primym porovnanim se SKUTECNYM
admin zaznamem na zivem logiman.cz potvrdil, ze cenove sloupce (total_czk/
shipping_price_czk atd.) u puvodne importovanych objednavek JSOU spravne
ulozene JAKO GROSS (s DPH) - presne odpovidaji realnym castkam na
objednavce i realne prijate platbe. Zadny bug v importu nebyl.

Tenhle skript uz BYL jednou spusten (--apply) a pak OKAMZITE VRACEN
skriptem scripts/2026-08-22_orders_csv_vat_fix_REVERT.py (39 objednavek/
150 polozek vraceno na puvodni spravne hodnoty). Ponechano v repozitari
jen jako historicky zaznam prubehu vysetrovani - NIKDY uz znovu nespoustet,
zpusobilo by to STEJNOU chybnou zmenu dat znovu.

---
(puvodni, mylny popis nize, ponechano pro kontext)

Oprava DPH bugu v puvodnim importu historickych objednavek
(scripts/2026-08-21_orders_csv_import.py) - bot10, 2026-08-22.

Kontext (Robert pres bot3, zjisteno pri lade bankovniho parovani): import
skript pouzil "WithVat" (s DPH) CSV pole jako zdroj pro shop_orders/
shop_order_items cenove sloupce, na zaklade chybneho predpokladu ve
vlastnim docstringu ("system pracuje v cenach s DPH"). Autoritativni,
drivejsi konvence (sql/2026-07-25_documents.sql: "ceny v e-shopu jsou BEZ
DPH -> na dokladech se pripocitava 21% DPH") rika presny opak - vsech
39 importovanych objednavek (CELY aktualni obsah shop_orders, zadne jine
objednavky v systemu jeste nejsou) ma proto total_czk/unit_price_czk/
line_total_czk/shipping_price_czk/payment_price_czk ulozene JAKO GROSS
(s DPH), misto NET (bez DPH), jak ocekava zbytek systemu (dokladova
generace v api/documents.py VZDY pricita 21% DPH navic k temhle
sloupcum - u techhle 39 objednavek by to znamenalo dvoji zdaneni na
papire, kdyby nekdo vygeneroval fakturu/zalohovku).

Tenhle skript PREPOCITA cenove sloupce zpet na NET primo ze stejneho
zdrojoveho CSV (scripts/2026-08-21_orders_import_source.csv), pouzitim
"WithoutVat" poli (presne, ne delenim 1,21 - vyhne se zaokrouhlovacim
nepresnostem). UPDATE IN PLACE (zachovava id, bank_paid/bank_paid_at,
FK reference ze shop_documents/shop_emails) - NE DELETE+reinsert.

Polozky (shop_order_items) se paruji podle POZICE v ramci objednavky
(existujici radky ORDER BY id ASC vs. nove prepocitane polozky ve
stejnem poradi jako v CSV) - spolehlive, protoze puvodni import vkladal
polozky presne v poradi CSV radku (viz build_order() vyse).

Pouziti:
    api/venv/bin/python3 scripts/2026-08-22_orders_csv_vat_fix.py            # dry-run (jen tisk diffu)
    api/venv/bin/python3 scripts/2026-08-22_orders_csv_vat_fix.py --apply    # skutecny zapis
"""
import argparse
import csv
import os
import re

CSV_PATH = os.path.join(os.path.dirname(__file__), "2026-08-21_orders_import_source.csv")
ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")


def load_env():
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


def group_orders(rows):
    orders, order_seq = {}, []
    for r in rows:
        code = r["code"]
        if code not in orders:
            orders[code] = []
            order_seq.append(code)
        orders[code].append(r)
    return [(code, orders[code]) for code in order_seq]


def build_correct_order(code, items_raw):
    """Zrcadli build_order() z 2026-08-21_orders_csv_import.py, ale cte
    WithoutVat (NET) pole misto WithVat."""
    h = items_raw[0]
    shipping_price = 0.0
    payment_price = 0.0
    item_prices = []  # [(unit_price_net, line_total_net), ...] ve stejnem poradi jako realne polozky

    for r in items_raw:
        item_code = (r["itemCode"] or "").strip()
        if item_code.startswith("SHIPPING"):
            shipping_price = parse_czk(r["itemUnitPriceWithoutVat"])
            continue
        if item_code.startswith("BILLING"):
            payment_price = parse_czk(r["itemUnitPriceWithoutVat"])
            continue
        item_prices.append((
            parse_czk(r["itemUnitPriceWithoutVat"]),
            parse_czk(r["itemTotalPriceWithoutVat"]),
        ))

    return {
        "order_number": code.strip(),
        "shipping_price_czk": shipping_price,
        "payment_price_czk": payment_price,
        "total_czk": parse_czk(h["totalPriceWithoutVat"]),
        "item_prices": item_prices,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Skutečně zapsat do DB. Bez této volby jen dry-run.")
    args = ap.parse_args()

    with open(CSV_PATH, encoding="cp1250", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
    groups = group_orders(rows)
    print(f"Načteno {len(rows)} řádků CSV, {len(groups)} objednávek.")

    env = load_env()
    conn = get_db_conn(env)
    cur = conn.cursor()

    updated_orders = 0
    updated_items = 0
    mismatched_item_counts = []

    for code, items_raw in groups:
        corrected = build_correct_order(code, items_raw)
        cur.execute(
            "SELECT id, shipping_price_czk, payment_price_czk, total_czk FROM shop_orders WHERE order_number=%s",
            (corrected["order_number"],),
        )
        order_row = cur.fetchone()
        if not order_row:
            print(f"  PŘESKOČENO (order_number {corrected['order_number']} v DB neexistuje): {code}")
            continue
        order_id = order_row["id"]

        cur.execute(
            "SELECT id, unit_price_czk, line_total_czk FROM shop_order_items WHERE order_id=%s ORDER BY id ASC",
            (order_id,),
        )
        existing_items = cur.fetchall()
        if len(existing_items) != len(corrected["item_prices"]):
            mismatched_item_counts.append((corrected["order_number"], len(existing_items), len(corrected["item_prices"])))
            print(f"  POZOR - {corrected['order_number']}: počet položek v DB ({len(existing_items)}) "
                  f"≠ počet reálných položek v CSV ({len(corrected['item_prices'])}) - PŘESKOČENO, nutná ruční kontrola.")
            continue

        print(f"  {corrected['order_number']}: shipping {order_row['shipping_price_czk']} -> {corrected['shipping_price_czk']}, "
              f"payment {order_row['payment_price_czk']} -> {corrected['payment_price_czk']}, "
              f"total {order_row['total_czk']} -> {corrected['total_czk']}")

        if args.apply:
            cur.execute(
                "UPDATE shop_orders SET shipping_price_czk=%s, payment_price_czk=%s, total_czk=%s WHERE id=%s",
                (corrected["shipping_price_czk"], corrected["payment_price_czk"], corrected["total_czk"], order_id),
            )
            for existing, (unit_net, line_net) in zip(existing_items, corrected["item_prices"]):
                cur.execute(
                    "UPDATE shop_order_items SET unit_price_czk=%s, line_total_czk=%s WHERE id=%s",
                    (unit_net, line_net, existing["id"]),
                )
            updated_items += len(existing_items)
        updated_orders += 1

    if args.apply:
        conn.commit()
        print(f"\nAPLIKOVÁNO: {updated_orders} objednávek, {updated_items} položek opraveno.")
    else:
        print(f"\n(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")
        print(f"Bylo by opraveno: {updated_orders} objednávek.")
    if mismatched_item_counts:
        print(f"\nPOZOR - {len(mismatched_item_counts)} objednávek s neshodným počtem položek (přeskočeno, nutná ruční kontrola):")
        for on, db_n, csv_n in mismatched_item_counts:
            print(f"  {on}: DB={db_n}, CSV={csv_n}")

    conn.close()


if __name__ == "__main__":
    main()
