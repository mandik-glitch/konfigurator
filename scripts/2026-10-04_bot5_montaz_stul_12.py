#!/opt/konfigurator/api/venv/bin/python
"""Montaz konfigurovaneho stolu (typ sestavy STUL_SKLAD): sluzba 'Montaz' = 12 % z ceny konfigurace bez DPH (bot5, 2026-10-04; Robert pres bot9: "cena montaze jako mnou nastavitelne % z celkove ceny stolu,
vychozi je 12 %"). Zadny novy mechanismus: existuje sestava_typ_sluzba (klic montaz, procento_z_ceny), kterou cte konfigurace_kosik.montaz_pct_pro_typ (kosik, objednavka) a kterou admin upravuje v obrazovce
Typy sestav (PUT /api/admin/sestava-typ-sluzby/<id>) - hodnotu v % tam Robert kdykoli zmeni. Skript jen zalozi radek, kdyz chybi (jinak nic nemeni). Bez --apply jen vypise.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-04_bot5_montaz_stul_12.py [--apply]"""
import os
import sys

import pymysql

apply_ = "--apply" in sys.argv
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                       cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id FROM sestava_typ WHERE kod='STUL_SKLAD'")
typ = cur.fetchone()
assert typ, "typ sestavy STUL_SKLAD neexistuje"
cur.execute("SELECT id, hodnota, aktivni, pricing_mode FROM sestava_typ_sluzba WHERE sestava_typ_id=%s AND klic='montaz'", (typ["id"],))
radek = cur.fetchone()
if radek:
    print("radek montaz u STUL_SKLAD uz existuje, nic se nemeni:", radek)
    sys.exit(0)
cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM sestava_typ_sluzba WHERE sestava_typ_id=%s", (typ["id"],))
poradi = cur.fetchone()["n"]
print("zalozim: STUL_SKLAD / montaz / procento_z_ceny / 12 % / aktivni, poradi", poradi)
if not apply_:
    print("(dry-run, --apply pro zapis)")
    sys.exit(0)
cur.execute("INSERT INTO sestava_typ_sluzba (sestava_typ_id, klic, nazev, pricing_mode, hodnota, vyzaduje_dalsi_pole, aktivni, sort_order) VALUES (%s,'montaz','Montáž','procento_z_ceny',12,0,1,%s)", (typ["id"], poradi))
assert cur.rowcount == 1
new_id = cur.lastrowid
cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'create','sestava_typ_sluzba',%s,%s)", (new_id, "montaz STUL_SKLAD 12 % (bot5 2026-10-04, Robert pres bot9)"))
conn.commit()
print("zalozeno id", new_id)
