"""Migrace (bot16, 2026-10-05, idempotentni - CREATE TABLE IF NOT EXISTS): tabulka stul_ulozene_konfigurace pro "Ulozit konfiguraci" v generatoru stolu (api/stul_ulozeni.py).
Kazdy zaznam = jedna ulozena konfigurace (overene ICO, e-mail, telefon, token jen jako SHA-256, odkaz plati 90 dni) + vazba na lead v CRM (crm_lead_id).

DULEZITE: tabulka je zaroven VYPINAC funkce - dokud neexistuje, endpointy vraci 503 unavailable a UI tlacitko Ulozit konfiguraci se vubec neukaze. Spustit AZ PO schvaleni textu ochrany
osobnich udaju (e-mail, telefon a ICO jsou osobni udaje; text pripravuje bot7, schvaluje Robert).
DDL v produkci spousti bot3 / Robert (bot ho kvuli sandboxu nespusti). Definice se bere z api/stul_ulozeni.py (promenna DDL), aby nevznikly dve verze.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 sql/2026-10-05_stul_ulozene_konfigurace.py"""
import os
import re

import pymysql

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api", "stul_ulozeni.py"), encoding="utf-8").read()
DDL = re.search(r'DDL = """(CREATE TABLE IF NOT EXISTS stul_ulozene_konfigurace .*?)"""', SRC, re.S).group(1)
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", "3306")), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], autocommit=True)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='stul_ulozene_konfigurace'")
existovala = cur.fetchone()[0]
cur.execute(DDL)
print("tabulka stul_ulozene_konfigurace:", "uz existovala" if existovala else "vytvorena")
print("hotovo")
