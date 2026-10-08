"""
Robert po prohlednuti klikaci galerie extrahovanych schemat (viz
scripts/2026-08-10_dogus_katalog_schemata_extract.py): "v prvni casti
jsou jen samotne profily to muzes promazat sam ne? od 1 po S.067
smazat ja pokracuju dal" - stranky 1-67 (fakticky prvni obrazek az na
strane 21, viz manifest) jsou vyhradne profily (SKU prefix "1.x"),
strana 69+ uz zacina prislusenstvim (SKU prefix "2.x", strana 68 bez
SKU tabulky/obrazku). Odstranuje jen tuhle profilovou cast - zbytek
(prislusenstvi, str. 69+) zustava, Robert ho projde rucne v galerii.

Idempotentni - druhe spusteni uz nic nenajde (WHERE sort_order BETWEEN
1 AND 67 na jiz smazanych radcich vrati 0 radku).
"""
import json
import os
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

DRIVE_FILES_DIR = "/opt/konfigurator/private-files/shared-drive"
FOLDER_ID = 52
PAGE_FROM = 1
PAGE_TO = 67


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, filename, stored_filename, sort_order FROM shared_drive_files "
        "WHERE folder_id=%s AND sort_order BETWEEN %s AND %s ORDER BY sort_order, id",
        (FOLDER_ID, PAGE_FROM, PAGE_TO),
    )
    rows = cur.fetchall()
    print(f"K odstraneni (strany {PAGE_FROM}-{PAGE_TO}): {len(rows)}")
    if not rows:
        print("Nic k odstraneni (uz smazano, nebo spatny rozsah).")
        return

    backup = [dict(r) for r in rows]
    backup_path = "backups/dogus_katalog_schemata_removed_profiles_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha (metadata, ne binarni obsah) -> {backup_path}")

    if dry_run:
        for r in rows[:10]:
            print(f"  #{r['id']} str.{r['sort_order']:03d} {r['filename']}")
        if len(rows) > 10:
            print(f"  ... a dalsich {len(rows) - 10}")
        print("\nDRY RUN - nic nesmazano. Spust s --apply pro skutecne smazani.")
        return

    ids = [r["id"] for r in rows]
    placeholders = ",".join(["%s"] * len(ids))
    cur.execute(f"DELETE FROM shared_drive_files WHERE id IN ({placeholders})", ids)
    conn.commit()

    removed_files = 0
    for r in rows:
        path = os.path.join(DRIVE_FILES_DIR, r["stored_filename"])
        if os.path.exists(path):
            os.remove(path)
            removed_files += 1
    print(f"Smazano {len(rows)} zaznamu z DB, {removed_files} fyzickych souboru z disku.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
