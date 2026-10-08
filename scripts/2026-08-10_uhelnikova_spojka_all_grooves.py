"""
Uhelnikove spojky nemaji "zobak" (fyzicky vystupek, ktery by je vazal
na konkretni sirku drazky) - jen plochou desku sroubovanou do profilu,
takze sedi na JAKOUKOLI drazku (Robert: "vyjimka: uhelniky nemaji
zobaky, takze pasují na libovolnou drážku, dej jim vsechny 3 ikony").

groove_family se u techto 3 produktu meni z jedne konkretni hodnoty
(odvozene puvodne ze SKU pozice 4, ktera u nich ve skutecnosti popisuje
jen VELIKOST bracketu, ne pozadovanou drazku) na CSV "6,8,10" - novou
konvenci pro "sedi na libovolnou drazku v ramci prislusenstvi" (viz
_groove_badges_html/_category_products_with_images v api/app.py,
grooveBadgesHtml() v category.html/product.html).

cross_section_label zustava beze zmeny (30x30/40x40/45x45 - to je
skutecna velikost bracketu, spravne uz drive).

Cilene jen 3 SKU, NENI to precedens pro dalsi "Plocha rohova spojka"/
"Prima rohova spojka" produkty v podobnem stylu - Robert vyslovne
rekl "opravime pozdeji" k tem ostatnim.
"""
import json
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

TARGET_SKUS = ["2.2.001.08.3030.01", "2.2.001.10.4040.01", "2.2.001.10.4545.01"]
NEW_GROOVE = "6,8,10"


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    placeholders = ",".join(["%s"] * len(TARGET_SKUS))
    cur.execute(
        f"SELECT id, sku, name, cross_section_label, groove_family FROM shop_products WHERE sku IN ({placeholders})",
        TARGET_SKUS,
    )
    rows = {r["sku"]: r for r in cur.fetchall()}

    missing = [sku for sku in TARGET_SKUS if sku not in rows]
    if missing:
        print("CHYBA - SKU nenalezeno v DB:", missing)
        sys.exit(1)

    backup = [dict(rows[sku]) for sku in TARGET_SKUS]
    backup_path = "backups/uhelnikova_spojka_all_grooves_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha {len(backup)} radku -> {backup_path}")

    for sku in TARGET_SKUS:
        r = rows[sku]
        print(f"#{r['id']} {sku} {r['name']!r}: groove {r['groove_family']!r} -> {NEW_GROOVE!r} "
              f"(cross_section {r['cross_section_label']!r} beze zmeny)")
        if not dry_run:
            cur.execute("UPDATE shop_products SET groove_family=%s WHERE id=%s", (NEW_GROOVE, r["id"]))

    if dry_run:
        print("\nDRY RUN - 0 zapsano. Spust s --apply pro skutecny zapis.")
    else:
        conn.commit()
        print(f"\nZapsano {len(TARGET_SKUS)} produktu.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
