"""
Rucni doplneni cross_section_label/groove_family pro 2 konkretni
produkty "Spojka uhel 45°" (Robert, po diskuzi o nespolehlivosti
posledniho dvojcisli SKU napric katalogem - viz
scripts/2026-08-10_accessory_compatibility_backfill.py docstring a
AGENTS_LOG.md - u "Upínač patky"/"Pant" bylo prokazano, ze posledni
dvojcisli NENI obecne drazka. Robert i tak explicitne rozhodl pro
TYHLE DVA konkretni produkty: "dej jim hned ikonu slotu podle
posledniho dvojcisli sku").

    2.2.006.4040.08 "Spojka úhel 45° systém 40" -> 40x40, drazka 8
    2.2.006.4545.10 "Spojka úhel 45° systém 45" -> 45x45, drazka 10

NEPOUZIVAT jako precedens pro plosne prehodnoceni ostatnich 183
"neurcenych" polozek - je to vyslovne rucni vyjimka pro tyto 2 SKU, ne
zmena obecneho pravidla v backfill skriptu.
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

TARGETS = {
    "2.2.006.4040.08": ("40x40", "8"),
    "2.2.006.4545.10": ("45x45", "10"),
}


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, sku, name, cross_section_label, groove_family FROM shop_products "
        "WHERE sku IN (%s, %s)", tuple(TARGETS.keys()),
    )
    rows = {r["sku"]: r for r in cur.fetchall()}

    missing = [sku for sku in TARGETS if sku not in rows]
    if missing:
        print("CHYBA - SKU nenalezeno v DB:", missing)
        sys.exit(1)

    backup = [dict(rows[sku]) for sku in TARGETS]
    backup_path = "backups/spojka_uhel45_slot_manual_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha {len(backup)} radku -> {backup_path}")

    for sku, (cross_section, groove) in TARGETS.items():
        r = rows[sku]
        print(f"#{r['id']} {sku} {r['name']!r}: "
              f"cross_section {r['cross_section_label']!r} -> {cross_section!r}, "
              f"groove {r['groove_family']!r} -> {groove!r}")
        if not dry_run:
            cur.execute(
                "UPDATE shop_products SET cross_section_label=%s, groove_family=%s WHERE id=%s",
                (cross_section, groove, r["id"]),
            )

    if dry_run:
        print("\nDRY RUN - 0 zapsano. Spust s --apply pro skutecny zapis.")
    else:
        conn.commit()
        print(f"\nZapsano {len(TARGETS)} produktu.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
