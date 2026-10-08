"""Dedup remeslo_material_prices (Modul 1 katalog) - Robertovo rozhodnuti
2026-08-20, navazuje na bot11uv nalez "Kontrola kvality dat katalogu"
(AGENTS_LOG.md) - 5172 nadbytecnych radku vzniklych opakovanym --apply
scraperu bez predchoziho smazani starych radku.

Duplicitni skupina = stejny source_id + category_id + product_name +
price_czk + product_url (bit-for-bit identicke podle Robertova zadani).
V kazde skupine se ponecha JEDEN radek - nejnovejsi podle scraped_at
(tie-break: nejvyssi id) - zbytek se smaze.

Overeno PRED napsanim tohohle skriptu (viz AGENTS_LOG.md zapis "Dedup"):
- ZADNA FK vazba na remeslo_material_prices.id neexistuje v cele
  REMESLO_DB (INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS - prazdny
  vysledek).
- remeslo_shopping_list_items UMYSLNE neuklada price_id (jen
  category_id+source_id, viz komentar u POST /shopping-list v
  api/remeslo.py, presne kvuli tomuhle prescrape-churn riziku).
- remeslo_material_price_history je klicovana (source_id, url_hash),
  ne na id teto tabulky.
Dedup je tedy bezpecny bez jakehokoli repointovani cizich klicu.

Pouziti:
  python3 scripts/2026-08-20_remeslo_material_prices_dedup.py            # dry-run, jen report + export
  python3 scripts/2026-08-20_remeslo_material_prices_dedup.py --apply    # skutecne smaze
"""
import csv
import json
import sys
from collections import defaultdict

import pymysql


def load_env():
    env = {}
    for line in open("/opt/konfigurator/api/.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def connect(env):
    return pymysql.connect(
        host=env["REMESLO_DB_HOST"], port=int(env.get("REMESLO_DB_PORT", 3306)),
        user=env["REMESLO_DB_USER"], password=env["REMESLO_DB_PASSWORD"],
        database=env["REMESLO_DB_NAME"], cursorclass=pymysql.cursors.DictCursor,
    )


def find_groups(cur):
    cur.execute(
        "SELECT mp.id, mp.category_id, mp.source_id, mp.product_name, mp.price_czk, "
        "       mp.product_url, mp.scraped_at, ps.supplier_name, mc.name AS category_name "
        "FROM remeslo_material_prices mp "
        "JOIN remeslo_price_sources ps ON ps.id = mp.source_id "
        "JOIN remeslo_material_categories mc ON mc.id = mp.category_id "
        "ORDER BY mp.id"
    )
    rows = cur.fetchall()
    groups = defaultdict(list)
    for r in rows:
        key = (r["source_id"], r["category_id"], r["product_name"], str(r["price_czk"]), r["product_url"])
        groups[key].append(r)
    return rows, groups


def main():
    apply_mode = "--apply" in sys.argv
    env = load_env()
    conn = connect(env)
    with conn.cursor() as cur:
        all_rows, groups = find_groups(cur)

    total_before = len(all_rows)
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
    to_delete = []
    to_keep_summary = []
    for key, rows in dup_groups.items():
        rows_sorted = sorted(rows, key=lambda r: (r["scraped_at"], r["id"]), reverse=True)
        keep = rows_sorted[0]
        remove = rows_sorted[1:]
        to_keep_summary.append(keep)
        to_delete.extend(remove)

    print(f"Celkem radku pred: {total_before}")
    print(f"Duplicitnich skupin (>1 radek): {len(dup_groups)}")
    print(f"Radku k smazani: {len(to_delete)}")
    print(f"Ocekavany pocet po dedupu: {total_before - len(to_delete)}")

    # Audit export PRED smazanim - VZDY, i v dry-run, at je videt presne co by se smazalo.
    export_path = "/opt/konfigurator/backups/2026-08-20_dedup_material_prices_deleted.csv"
    with open(export_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source_id", "supplier_name", "category_id", "category_name",
                    "product_name", "price_czk", "product_url", "scraped_at", "kept_row_id"])
        # mapovani smazany radek -> ponechany radek jeho skupiny (pro dohledatelnost)
        key_to_keep_id = {}
        for key, rows in dup_groups.items():
            rows_sorted = sorted(rows, key=lambda r: (r["scraped_at"], r["id"]), reverse=True)
            key_to_keep_id[key] = rows_sorted[0]["id"]
        for r in to_delete:
            key = (r["source_id"], r["category_id"], r["product_name"], str(r["price_czk"]), r["product_url"])
            w.writerow([r["id"], r["source_id"], r["supplier_name"], r["category_id"], r["category_name"],
                        r["product_name"], r["price_czk"], r["product_url"], r["scraped_at"], key_to_keep_id[key]])
    print(f"Auditni export zapsan: {export_path} ({len(to_delete)} radku)")

    by_supplier = defaultdict(int)
    for r in to_delete:
        by_supplier[r["supplier_name"]] += 1
    print("Rozpad podle dodavatele:", dict(sorted(by_supplier.items(), key=lambda x: -x[1])))

    if not apply_mode:
        print("\nDRY RUN - zadna zmena v DB. Spust s --apply pro skutecne smazani.")
        return

    delete_ids = [r["id"] for r in to_delete]
    with conn.cursor() as cur:
        deleted_total = 0
        for i in range(0, len(delete_ids), 500):
            batch = delete_ids[i:i + 500]
            placeholders = ",".join(["%s"] * len(batch))
            cur.execute(f"DELETE FROM remeslo_material_prices WHERE id IN ({placeholders})", batch)
            deleted_total += cur.rowcount
        conn.commit()
    print(f"\nSMAZANO: {deleted_total} radku (ocekavano {len(delete_ids)})")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM remeslo_material_prices")
        total_after = cur.fetchone()["n"]
    print(f"Radku po dedupu: {total_after} (ocekavano {total_before - len(delete_ids)})")

    # Over, ze uz nejsou zadne zbyvajici duplicity podle stejneho klice.
    with conn.cursor() as cur:
        _, groups_after = find_groups(cur)
    remaining_dups = {k: v for k, v in groups_after.items() if len(v) > 1}
    print(f"Zbyvajici duplicitni skupiny po dedupu: {len(remaining_dups)} (ocekavano 0)")

    result = {
        "total_before": total_before, "dup_groups": len(dup_groups),
        "deleted": deleted_total, "total_after": total_after,
        "remaining_dup_groups": len(remaining_dups),
        "by_supplier": dict(by_supplier),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
