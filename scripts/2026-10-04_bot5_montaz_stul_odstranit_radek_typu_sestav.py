#!/opt/konfigurator/api/venv/bin/python
"""Odstrani radek sluzby 'Montaz' u typu sestavy STUL_SKLAD v sestava_typ_sluzba (zalozil ho scripts/2026-10-04_bot5_montaz_stul_12.py), protoze od nasazeni sady 'stul' ma sazbu montaze stolu
JEDINE rozhodnuti v app_settings stul_montaz_pct (Generator stolu, api/stul_montaz.py); radek v Typech sestav uz nema ucinek a Robert by menil dve mista (bot9 2026-10-04). Bez --apply jen vypise.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-04_bot5_montaz_stul_odstranit_radek_typu_sestav.py [--apply]"""
import os
import sys

import pymysql

apply_ = "--apply" in sys.argv
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT s.id, s.klic, s.pricing_mode, s.hodnota, s.nazev FROM sestava_typ_sluzba s JOIN sestava_typ t ON t.id = s.sestava_typ_id WHERE t.kod='STUL_SKLAD' AND s.klic='montaz'")
radky = cur.fetchall()
print("nalezeno:", radky)
if len(radky) != 1:
    sys.exit("ocekavan presne jeden radek, nic se nemaze")
r = radky[0]
if r["pricing_mode"] != "procento_z_ceny" or r["nazev"] != "Montáž":
    sys.exit("radek neodpovida tomu, co zalozil skript (nazev Montáž, procento_z_ceny), nic se nemaze")
if not apply_:
    print("(dry-run, --apply pro smazani)")
    sys.exit(0)
cur.execute("DELETE FROM sestava_typ_sluzba WHERE id=%s", (r["id"],))
assert cur.rowcount == 1
cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'delete','sestava_typ_sluzba',%s,%s)", (r["id"], "montaz STUL_SKLAD odstranen: sazba je nove v app_settings stul_montaz_pct (bot5 2026-10-04, bot9)"))
conn.commit()
print("odstraneno id", r["id"])
