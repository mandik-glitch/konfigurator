"""Vraci zpet posledni zapis (sloupek-pred-podbehem vyska + zaslepky) ze
zalohy backups/2026-09-13_sloupek_vyska_fix/pred_zapisem.json - Robert:
"vrat ty posledni opravy"."""
import json
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

BACKUP_FILE = "/opt/konfigurator/backups/2026-09-13_sloupek_vyska_fix/pred_zapisem.json"

zaloha = json.load(open(BACKUP_FILE, encoding="utf-8"))
conn = get_conn()
try:
    with conn.cursor() as cur:
        for aid_str, row in zaloha.items():
            cur.execute(
                "UPDATE product_assemblies SET data=%s WHERE id=%s",
                (row["data"], int(aid_str)),
            )
            print(f"#{aid_str} vraceno na puvodni stav")
    conn.commit()
    print(f"\nCOMMIT hotovy, {len(zaloha)} sestav vraceno.")
finally:
    conn.close()
