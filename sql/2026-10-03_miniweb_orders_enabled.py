"""Migrace (bot5, 2026-10-03, idempotentni, jen PRIDAVA nullable/vychozi sloupce): objednavky mini-shopu (api/miniweb_objednavky.py).
  miniweb_shops.orders_enabled  TINYINT(1) vychozi 0   objednavky (kosik a pokladna) mini-shopu, 0 = jen kontaktni formular
  shop_orders.shipping_review   TINYINT(1) vychozi 0   1 = doprava ke schvaleni zamestnancem (objednavka z mini-shopu, proforma az po schvaleni)
  shop_orders.vat_mode          VARCHAR(20) NULL        'standard' (CZ sazba) | 'reverse_charge' (platne IC DPH z jineho clenskeho statu, 0 %), NULL = starsi objednavky (CZ sazba)
  shop_orders.vat_check         VARCHAR(20) NULL        'none' | 'vies_valid' | 'vies_unavailable' | 'vies_invalid'
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 sql/2026-10-03_miniweb_orders_enabled.py"""
import os
import pymysql
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], autocommit=True)
cur = conn.cursor()
PLAN = (("miniweb_shops", "orders_enabled", "TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'objednavky mini-shopu (kosik a pokladna), 0 = jen poptavka'"),
        ("shop_orders", "shipping_review", "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1 = doprava ke schvaleni zamestnancem (mini-shop)'"),
        ("shop_orders", "vat_mode", "VARCHAR(20) DEFAULT NULL COMMENT 'standard | reverse_charge, NULL = CZ sazba'"),
        ("shop_orders", "vat_check", "VARCHAR(20) DEFAULT NULL COMMENT 'none | vies_valid | vies_unavailable | vies_invalid'"))
for tabulka, sloupec, definice in PLAN:
    cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s", (tabulka, sloupec))
    if not cur.fetchone()[0]:
        cur.execute(f"ALTER TABLE `{tabulka}` ADD COLUMN `{sloupec}` {definice}")
        print("+", tabulka, sloupec)
print("hotovo")
