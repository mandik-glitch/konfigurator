#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Idempotentne aplikuje sql/2026-09-24b_shop_products_vandr_predni_azimut.sql
(shop_products.vandr_predni_azimut_deg). Samostatny soubor misto inline
prikazu - viz ostatni scripts/2026-*_*.py v repu, stejny vzor."""
import pymysql

ENV_PATH = "/opt/konfigurator/api/.env"
SQL_PATH = "/opt/konfigurator/sql/2026-09-24b_shop_products_vandr_predni_azimut.sql"


def _env():
    vals = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def main():
    e = _env()
    conn = pymysql.connect(host=e["DB_HOST"], port=int(e.get("DB_PORT", 3306)),
                            user=e["DB_USER"], password=e["DB_PASSWORD"],
                            database=e["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM shop_products LIKE 'vandr_predni_azimut_deg'")
            if cur.fetchone():
                print("sloupec uz existuje, ALTER se preskakuje")
                return
            sql = open(SQL_PATH, encoding="utf-8").read()
            stmt = sql[sql.index("ALTER TABLE"):].strip()
            cur.execute(stmt)
        conn.commit()
        print("ALTER proveden")
    finally:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM shop_products LIKE 'vandr_predni_azimut_deg'")
            print(cur.fetchone())
        conn.close()


if __name__ == "__main__":
    main()
