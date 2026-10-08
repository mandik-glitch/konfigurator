"""Migrace (bot5, 2026-10-03, idempotentni): miniweb_shops - price_mode i 'shown', sloupce eur_rate a margin_pct (pro api/miniweb_cena.py).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 sql/2026-10-03_miniweb_ceny_eur.py"""
import sys
sys.path.insert(0, "/opt/konfigurator/api")
import pymysql, os
conn = pymysql.connect(host=os.environ.get("DB_HOST", "localhost"), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], autocommit=True)
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='miniweb_shops'")
cols = dict(cur.fetchall())
if "shown" not in cols.get("price_mode", ""):
    cur.execute("ALTER TABLE miniweb_shops MODIFY price_mode ENUM('hidden','indicative','shown') NOT NULL DEFAULT 'hidden'")
    print("price_mode: +shown")
if "eur_rate" not in cols:
    cur.execute("ALTER TABLE miniweb_shops ADD COLUMN eur_rate DECIMAL(10,4) DEFAULT NULL COMMENT 'rucni kurz Kc za 1 EUR, NULL = zivy kurz Fio'")
    print("+eur_rate")
if "margin_pct" not in cols:
    cur.execute("ALTER TABLE miniweb_shops ADD COLUMN margin_pct DECIMAL(5,2) DEFAULT NULL COMMENT 'marze v % k prepoctu na EUR, NULL = cena se nevydava'")
    print("+margin_pct")
print("hotovo")
