#!/usr/bin/env python3
"""Zalozeni tabulek Vandr systemu `vd_komponenty`, `vd_komponenty_dily` (bot10, 2026-10-05). Idempotentni (CREATE TABLE IF NOT EXISTS), nedotyka se zadne jine tabulky.

  api/venv/bin/python3 scripts/vandr_system/zaloz_tabulky.py                 (nahled: vypise DDL a co uz existuje)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/vandr_system/zaloz_tabulky.py --apply"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
import pymysql  # noqa: E402
import vandr_system as VS  # noqa: E402

apply = "--apply" in sys.argv
if not os.environ.get("DB_HOST"):
    print("DDL, ktere se provede (nahled bez DB):\n")
    for sql in VS.DDL:
        print(sql, "\n")
    sys.exit(0)
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                       database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SHOW TABLES LIKE 'vd\\_%'")
print("existuje:", [list(r.values())[0] for r in cur.fetchall()] or "nic")
if not apply:
    print("(nahled, nic nezapsano; zapis: --apply)")
    sys.exit(0)
VS.zaloz_schema(cur)
conn.commit()
cur.execute("SHOW TABLES LIKE 'vd\\_%'")
tb = sorted(list(r.values())[0] for r in cur.fetchall())
print("po zalozeni:", tb)
assert tb == ["vd_komponenty", "vd_komponenty_dily"], tb
