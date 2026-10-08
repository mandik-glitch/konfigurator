"""Doplneni hover obrazku (shop_product_images.sort_order=1) pro category.html
z JIZ EXISTUJICICH kanonickych souboru aktivni otockove davky - zadny novy render.

Vetev podle SKU prefixu 'VD-' (bot16 2026-09-27, overeno na realnem branch1 prikladu):
  - SKU 'VD-...' (Vandr)   -> hlavni obrazek je cca 30 stupnu od cela, hover = canonical "hero_1024" (celni)
  - ostatni (nase sestavy) -> hlavni obrazek je celni,                hover = canonical "side_1024" (bok +90)

Zdroj: product_turntable_frames (is_active=1) -> batch -> canonical.json te davky
(webapp/content-files/turntable-frames/<id>/<batch>/canonical.json), soubor z
"files" dictu zkopirovan do webapp/content-files/gallery/vestavby-hover/.
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
os.makedirs(HOVER_DIR, exist_ok=True)

c = load_env()
conn = pymysql.connect(host=c["DB_HOST"], port=int(c.get("DB_PORT", 3306)), user=c["DB_USER"], password=c["DB_PASSWORD"],
                       database=c["DB_NAME"], charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

cur.execute("""
    SELECT sp.id, sp.sku, sp.thumbnail_file
    FROM shop_products sp
    WHERE sp.active=1 AND sp.is_archived=0 AND sp.category_id IS NOT NULL
      AND sp.thumbnail_file IS NOT NULL AND sp.thumbnail_file != ''
      AND NOT EXISTS (SELECT 1 FROM shop_product_images spi WHERE spi.product_id=sp.id AND spi.sort_order=1)
""")
kandidati = cur.fetchall()
print("KANDIDATU CELKEM:", len(kandidati))

# aktivni davka kazdeho produktu (jedna staci, DISTINCT)
cur.execute("SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames WHERE is_active=1")
aktivni_davka = {}
for r in cur.fetchall():
    aktivni_davka.setdefault(r["shop_product_id"], r["batch"])
print("PRODUKTU S AKTIVNI DAVKOU:", len(aktivni_davka))

vlozeno = 0
chyby = []
for p in kandidati:
    pid = p["id"]
    batch = aktivni_davka.get(pid)
    if not batch:
        chyby.append((pid, "zadna aktivni davka v product_turntable_frames"))
        continue
    canon_path = os.path.join(CF, "turntable-frames", str(pid), batch, "canonical.json")
    if not os.path.exists(canon_path):
        chyby.append((pid, "canonical.json chybi: %s" % canon_path))
        continue
    try:
        meta = json.load(open(canon_path, encoding="utf-8"))
    except Exception as e:
        chyby.append((pid, "canonical.json nejde precist: %s" % e))
        continue
    klic = "hero_1024" if (p["sku"] or "").startswith("VD-") else "side_1024"
    rel = meta.get("files", {}).get(klic)
    if not rel:
        chyby.append((pid, "canonical.json nema klic %s" % klic))
        continue
    src = os.path.join(CF, rel)
    if not os.path.exists(src):
        chyby.append((pid, "zdrojovy soubor chybi: %s" % src))
        continue
    dest_name = "product-%d-hover.jpg" % pid
    dest = os.path.join(HOVER_DIR, dest_name)
    shutil.copyfile(src, dest)
    os.chmod(dest, 0o644)
    cur.execute(
        "INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) VALUES (%s,%s,%s,1)",
        (pid, "vestavby-hover/" + dest_name, None),
    )
    if cur.rowcount != 1:
        chyby.append((pid, "INSERT rowcount=%d (ocekavano 1)" % cur.rowcount))
        continue
    vlozeno += 1

conn.commit()
print("VLOZENO:", vlozeno)
print("CHYB:", len(chyby))
for pid, duvod in chyby[:30]:
    print(" ", pid, duvod)
if len(chyby) > 30:
    print("  ... a dalsich", len(chyby) - 30)

# overeni po zapisu - skutecny pocet radku sort_order=1 pro tyto produkty
ids = [p["id"] for p in kandidati]
if ids:
    ph = ",".join(["%s"] * len(ids))
    cur.execute(f"SELECT COUNT(*) c FROM shop_product_images WHERE product_id IN ({ph}) AND sort_order=1", ids)
    print("OVERENI - hover radku pro tyto kandidaty ted v DB:", cur.fetchone()["c"])
