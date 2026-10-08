#!/usr/bin/env python3
"""Zapis app_settings.configurator_hide_price_hosts (bot8, 2026-10-02): seznam hostname mini-shopu, na ktere verejne API konfiguratoru stolu NIKDY
nevraci cenu (api/stul_shop.py _hosty_bez_ceny, cache 60 s). Slovensky mini-shop: baliace-stoly.top (+www). Jediny zapis (INSERT ... ON DUPLICATE KEY UPDATE),
overi rowcount a prectenim zpet; nic jineho nemeni.

Spusteni (DB pres systemd-run kvuli prihlasovacim udajum, jednim radkem):
  cd /opt/konfigurator && systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-02_stul_skryta_cena_zapis.py
Zruseni (smazani nastaveni):  ... skryta_cena_zapis.py --smazat
"""
import json
import os
import sys

import pymysql

KLIC = "configurator_hide_price_hosts"
HOSTY = ["baliace-stoly.top", "www.baliace-stoly.top"]

conn = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                       database=os.environ.get("DB_NAME", "konfigurator_v3"), cursorclass=pymysql.cursors.DictCursor, charset="utf8mb4", autocommit=False)
cur = conn.cursor()
cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
pred = cur.fetchone()
print("pred zapisem:", pred["setting_value"] if pred else "(zaznam neexistuje)")
if "--smazat" in sys.argv:
    n = cur.execute("DELETE FROM app_settings WHERE setting_key=%s", (KLIC,))
    print("smazano radku:", n)
    ocek_po = None
else:
    hodnota = json.dumps(HOSTY)
    n = cur.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)", (KLIC, hodnota))
    print("rowcount:", n, "(1 = nove vlozeno, 2 = zmeneno, 0 = uz tam bylo totez)")
    ocek_po = hodnota
cur.execute("SELECT setting_value FROM app_settings WHERE setting_key=%s", (KLIC,))
po = cur.fetchone()
hodnota_po = po["setting_value"] if po else None
if hodnota_po != ocek_po:
    conn.rollback()
    print("CHYBA: po zapisu je v DB", hodnota_po, "misto", ocek_po, "- zapis vracen (rollback)")
    sys.exit(1)
conn.commit()
print("OK, v DB je:", hodnota_po, "- do 60 s se projevi (cache v api/stul_shop.py), restart neni treba")
