"""
Uplna zaloha shop_orders (vsechny sloupce, vsechny radky) PRED ALTER
TABLE (sql/2026-09-04_shop_orders_delivery_billing_state.sql) - bot18,
2026-09-04. Samostatna od zalohy uvnitr backfill skriptu (ta zalohuje
jen 4 sloupce TESNE pred UPDATE) - tahle je bod-v-case snapshot cele
tabulky pred samotnou zmenou schematu.

Pouziti: systemd-run ... scripts/2026-09-04_shop_orders_full_backup.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymysql


def main():
    conn = pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM shop_orders ORDER BY id")
    rows = cur.fetchall()

    def conv(v):
        if isinstance(v, (datetime.date, datetime.datetime)):
            return v.isoformat()
        if hasattr(v, "__class__") and v.__class__.__name__ == "Decimal":
            return float(v)
        return v

    data = [{k: conv(v) for k, v in r.items()} for r in rows]
    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backups", "2026-09-04_shop_orders_uplna_zaloha_pred_alter.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"ulozeno {len(data)} radku do {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
