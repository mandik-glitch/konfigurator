#!/usr/bin/env python3
"""Vytiskne data JSON sestavy na stdout (pro Node driver wide_process.js)."""
import sys
sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import get_conn  # noqa: E402

aid = int(sys.argv[1])
conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT data FROM product_assemblies WHERE id=%s", (aid,))
        row = cur.fetchone()
        if not row:
            sys.exit(f"CHYBA: id={aid} neexistuje")
        print(row["data"])
finally:
    conn.close()
