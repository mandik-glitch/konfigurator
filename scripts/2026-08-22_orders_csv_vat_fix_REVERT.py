#!/usr/bin/env python3
"""REVERT skriptu 2026-08-22_orders_csv_vat_fix.py - bot10, 2026-08-22.

Puvodni "oprava" byla ZALOZENA NA MYLNEM predpokladu (bot3/Robert,
nasledne opraveno primym porovnanim se skutecnym admin zaznamem na
zivem logiman.cz): shop_orders.total_czk/shipping_price_czk atd. JSOU
spravne ulozene jako GROSS (s DPH) - "Cena celkem vcetne DPH: 2 505,55
Kc" + "Doprava: 250 Kc + 21% DPH = 302,50 Kc" presne sedi s puvodnimi
hodnotami v DB. Zadny bug v importu nebyl.

Tenhle skript vraci vsech 39 objednavek + 150 polozek zpet na PUVODNI
(spravne) hodnoty - cte STEJNE CSV, ale "With Vat" pole (presne jako
puvodni scripts/2026-08-21_orders_csv_import.py pred mou chybnou
"opravou"), UPDATE IN PLACE (zachova id/bank_paid/bank_paid_at/FK).

Pouziti:
    api/venv/bin/python3 scripts/2026-08-22_orders_csv_vat_fix_REVERT.py            # dry-run
    api/venv/bin/python3 scripts/2026-08-22_orders_csv_vat_fix_REVERT.py --apply    # skutecny zapis
"""
import argparse
import csv
import os

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


def build_original_order(code, items_raw):
    """Presne puvodni logika (pred vat_fix) - WithVat pole."""
    h = items_raw[0]
    shipping_price = 0.0
    payment_price = 0.0
    item_prices = []

    for r in items_raw:
        item_code = (r["itemCode"] or "").strip()
        if item_code.startswith("SHIPPING"):
            shipping_price = parse_czk(r["itemUnitPriceWithVat"])
            continue
        if item_code.startswith("BILLING"):
            payment_price = parse_czk(r["itemUnitPriceWithVat"])
            continue
        item_prices.append((
            parse_czk(r["itemUnitPriceWithVat"]),
            parse_czk(r["itemTotalPriceWithVat"]),
        ))

    return {
        "order_number": code.strip(),
        "shipping_price_czk": shipping_price,
        "payment_price_czk": payment_price,
        "total_czk": parse_czk(h["totalPriceWithVat"]),
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

    for code, items_raw in groups:
        original = build_original_order(code, items_raw)
        cur.execute(
            "SELECT id, shipping_price_czk, payment_price_czk, total_czk FROM shop_orders WHERE order_number=%s",
            (original["order_number"],),
        )
        order_row = cur.fetchone()
        if not order_row:
            print(f"  PŘESKOČENO (order_number {original['order_number']} v DB neexistuje)")
            continue
        order_id = order_row["id"]

        cur.execute(
            "SELECT id, unit_price_czk, line_total_czk FROM shop_order_items WHERE order_id=%s ORDER BY id ASC",
            (order_id,),
        )
        existing_items = cur.fetchall()
        if len(existing_items) != len(original["item_prices"]):
            print(f"  POZOR - {original['order_number']}: počet položek nesedí, PŘESKOČENO.")
            continue

        print(f"  {original['order_number']}: shipping {order_row['shipping_price_czk']} -> {original['shipping_price_czk']}, "
              f"payment {order_row['payment_price_czk']} -> {original['payment_price_czk']}, "
              f"total {order_row['total_czk']} -> {original['total_czk']}")

        if args.apply:
            cur.execute(
                "UPDATE shop_orders SET shipping_price_czk=%s, payment_price_czk=%s, total_czk=%s WHERE id=%s",
                (original["shipping_price_czk"], original["payment_price_czk"], original["total_czk"], order_id),
            )
            for existing, (unit_gross, line_gross) in zip(existing_items, original["item_prices"]):
                cur.execute(
                    "UPDATE shop_order_items SET unit_price_czk=%s, line_total_czk=%s WHERE id=%s",
                    (unit_gross, line_gross, existing["id"]),
                )
            updated_items += len(existing_items)
        updated_orders += 1

    if args.apply:
        conn.commit()
        print(f"\nAPLIKOVÁNO (REVERT): {updated_orders} objednávek, {updated_items} položek obnoveno na původní hodnoty.")
    else:
        print(f"\n(dry-run - nic nezapsáno, spusť s --apply pro skutečný zápis)")

    conn.close()


if __name__ == "__main__":
    main()
