"""Oprava hover obrazku vetve 1 (nase sestavy, SKU NEZACINA 'VD-'): puvodni
skript pouzil canonical "side" (+90 stupnu od cela), Robert chce jen JEDEN
krok vedle cela (+30 stupnu, stejny smer jako puvodni side). Zadny novy
render - vsech 9 azimutu (krok 30 stupnu) z aktivni davky zustava trvale
v product_turntable_frames, i po commitu.

Meni jen radky vestavby-hover/*, ktere zapsal scripts/2026-09-27_hover_populate.py
(pozna se podle cesty souboru). Vandr radky (hero_1024, cela vetev 2) NEDOTCENY -
Robert si stezoval jen na vetev 1.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
import pymysql
from _env import load_env

CF = "/opt/konfigurator/webapp/content-files"
HOVER_DIR = os.path.join(CF, "gallery", "vestavby-hover")
KROK_DEG = 30

c = load_env()
conn = pymysql.connect(host=c["DB_HOST"], port=int(c.get("DB_PORT", 3306)), user=c["DB_USER"], password=c["DB_PASSWORD"],
                       database=c["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

cur.execute("""
    SELECT spi.id AS radek_id, sp.id AS product_id, sp.sku
    FROM shop_product_images spi
    JOIN shop_products sp ON sp.id = spi.product_id
    WHERE spi.sort_order = 1 AND spi.filename LIKE 'vestavby-hover/%%'
      AND sp.sku NOT LIKE 'VD-%%'
""")
kandidati = cur.fetchall()
print("VETEV 1 RADKU K OPRAVE:", len(kandidati))

cur.execute("SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames WHERE is_active=1")
aktivni_davka = {}
for r in cur.fetchall():
    aktivni_davka.setdefault(r["shop_product_id"], r["batch"])

opraveno = 0
chyby = []
for p in kandidati:
    pid = p["product_id"]
    batch = aktivni_davka.get(pid)
    if not batch:
        chyby.append((pid, "zadna aktivni davka")); continue
    canon_path = os.path.join(CF, "turntable-frames", str(pid), batch, "canonical.json")
    if not os.path.exists(canon_path):
        chyby.append((pid, "canonical.json chybi")); continue
    meta = json.load(open(canon_path, encoding="utf-8"))
    front = meta.get("front_azimuth_deg")
    if front is None:
        chyby.append((pid, "canonical.json nema front_azimuth_deg")); continue
    cil_az = (int(front) + KROK_DEG) % 360
    cur.execute(
        "SELECT filename FROM product_turntable_frames WHERE shop_product_id=%s AND batch=%s "
        "AND is_active=1 AND elevation_deg=0 AND azimuth_deg=%s AND tier_px=1024",
        (pid, batch, cil_az),
    )
    row = cur.fetchone()
    if not row:
        chyby.append((pid, "chybi snimek pro azimut %d (front=%s)" % (cil_az, front))); continue
    src = os.path.join(CF, row["filename"])
    if not os.path.exists(src):
        chyby.append((pid, "soubor na disku chybi: %s" % src)); continue
    dest_name = "product-%d-hover.jpg" % pid
    dest = os.path.join(HOVER_DIR, dest_name)
    shutil.copyfile(src, dest)
    os.chmod(dest, 0o644)
    cur.execute(
        "UPDATE shop_product_images SET filename=%s WHERE id=%s",
        ("vestavby-hover/" + dest_name, p["radek_id"]),
    )
    if cur.rowcount != 1:
        chyby.append((pid, "UPDATE rowcount=%d (ocekavano 1)" % cur.rowcount)); continue
    opraveno += 1

conn.commit()
print("OPRAVENO:", opraveno)
print("CHYB:", len(chyby))
for pid, duvod in chyby[:30]:
    print(" ", pid, duvod)
