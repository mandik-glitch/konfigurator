#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Idempotentne aplikuje sql/2026-10-08_shop_emails_sent_at.sql (sloupec sent_at v shop_emails a system_emails + zpetne doplneni z audit_log) - bot5, 2026-10-08.
ALTER se preskoci, kdyz sloupec uz existuje; UPDATE plni jen radky se sent_at IS NULL, takze opakovane spusteni nic neprepise.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-08_bot5_sent_at_migrace.py"""
import os
import re
import sys

import pymysql

SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql", "2026-10-08_shop_emails_sent_at.sql")


def _sql_prikazy():
    text = re.sub(r"^--.*$", "", open(SQL, encoding="utf-8").read(), flags=re.M)
    return [p.strip() for p in text.split(";") if p.strip()]


def main():
    conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, autocommit=True)
    cur = conn.cursor()
    for q in _sql_prikazy():
        m = re.match(r"ALTER TABLE (\w+) ADD COLUMN (\w+)", q)
        if m:
            cur.execute("SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s", (m.group(1), m.group(2)))
            if cur.fetchone()["n"]:
                print("preskoceno (sloupec uz je): %s.%s" % (m.group(1), m.group(2)))
                continue
        cur.execute(q)
        print("%s -> %d radku" % (q.split("\n")[0][:70], cur.rowcount))
    for t in ("shop_emails", "system_emails"):
        cur.execute("SELECT id, status, created_at, sent_at FROM %s ORDER BY id" % t)
        for r in cur.fetchall():
            if r["status"] == "sent" or r["sent_at"]:
                print("  %s #%d %s zarazeno %s odeslano %s" % (t, r["id"], r["status"], r["created_at"], r["sent_at"]))
    print("hotovo")


if __name__ == "__main__":
    sys.exit(main())
