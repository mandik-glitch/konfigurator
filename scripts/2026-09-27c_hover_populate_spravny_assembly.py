"""OPRAVA hover obrazku - spatny vyber davky u produktu s vice sestavami
na jedne skladove karte (nalezl bot3, 2026-09-27 pozdni vecer).

Puvodni chyba: 2026-09-27_hover_populate.py i ..._o1_krok.py delaly
`SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames
WHERE is_active=1` BEZ ORAZENI - kdyz ma produkt vic soucasne aktivnich
davek (ruzne assembly_id, normalni stav u "nase sestavy" karet - jedna
skladova karta = vic K-XXX variant), vyber byl nedeterministicky a mohl
trefit UPLNE JINOU variantu, nez jakou karta ukazuje jako hlavni foto.

Tenhle skript mirroruje PRESNE stejnou logiku vyberu jako produkce
(api/turntable.py::turntable_public_info, volana bez assembly_id -
presne to, co pouziva hlavni foto karty na category.html i storefrontu):
  1) mezi aktivnimi davkami s NEPRAZDNYM assembly_id preferuj
     product_assemblies.is_master=1, jinak nejmensi assembly_id
  2) kdyz produkt nema ZADNOU davku s assembly_id (jednoducha
     karta/Vandr), vezmi jakoukoli aktivni davku (stejne jako produkce -
     tam kde je jen jedna, neni na cem se splest)

PREPISUJE (UPDATE, ne INSERT) VSECHNY dosavadni hover radky, ktere
zapsaly oba predchozi skripty (pozna se podle 'vestavby-hover/' cesty) -
bot3 doporucil povazovat vsech 97+12 za nedoveryhodne, tohle je jejich
jednotny prepocet+oprava, ne dalsi dilici patch.
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


def spravna_davka(pid):
    """Presne stejna logika jako turntable_public_info() bez assembly_id."""
    cur.execute(
        "SELECT f.assembly_id FROM product_turntable_frames f "
        "LEFT JOIN product_assemblies a ON a.id = f.assembly_id "
        "WHERE f.shop_product_id=%s AND f.is_active=1 AND f.assembly_id IS NOT NULL "
        "ORDER BY COALESCE(a.is_master, 0) DESC, f.assembly_id ASC LIMIT 1",
        (pid,),
    )
    pref = cur.fetchone()
    assembly_id = pref["assembly_id"] if pref else None
    if assembly_id is not None:
        cur.execute(
            "SELECT batch FROM product_turntable_frames WHERE shop_product_id=%s "
            "AND is_active=1 AND assembly_id=%s LIMIT 1",
            (pid, assembly_id),
        )
    else:
        cur.execute(
            "SELECT batch FROM product_turntable_frames WHERE shop_product_id=%s AND is_active=1 LIMIT 1",
            (pid,),
        )
    row = cur.fetchone()
    return (row["batch"] if row else None), assembly_id


# VSECHNY produkty, ktere maji hover radek z nasich dvou predchozich behu
# (pozna se podle cesty), PLUS puvodnich 112 kandidatu (kdyby nejaky mezi
# behy pribyl/zmenil se) - sjednoceny seznam.
cur.execute("""
    SELECT spi.id AS radek_id, sp.id AS product_id, sp.sku
    FROM shop_product_images spi
    JOIN shop_products sp ON sp.id = spi.product_id
    WHERE spi.sort_order = 1 AND spi.filename LIKE 'vestavby-hover/%%'
""")
existujici = {r["product_id"]: r for r in cur.fetchall()}

cur.execute("""
    SELECT sp.id, sp.sku
    FROM shop_products sp
    WHERE sp.active=1 AND sp.is_archived=0 AND sp.category_id IS NOT NULL
      AND sp.thumbnail_file IS NOT NULL AND sp.thumbnail_file != ''
""")
vsichni_kandidati = {r["id"]: r for r in cur.fetchall()}

# sjednoceni: vsichni puvodni kandidati (i kdyby jeste nemeli radek) +
# cokoli uz existujiciho z nasich behu
cilovy_seznam = dict(vsichni_kandidati)
cilovy_seznam.update({pid: {"id": pid, "sku": r["sku"]} for pid, r in existujici.items()})

print("CELKEM K PREPOCTU:", len(cilovy_seznam))

opraveno = 0
chyby = []
zmeneno_assembly = 0
for pid, p in cilovy_seznam.items():
    batch, assembly_id = spravna_davka(pid)
    if not batch:
        chyby.append((pid, "zadna aktivni davka")); continue
    canon_path = os.path.join(CF, "turntable-frames", str(pid), batch, "canonical.json")
    if not os.path.exists(canon_path):
        chyby.append((pid, "canonical.json chybi: %s" % canon_path)); continue
    meta = json.load(open(canon_path, encoding="utf-8"))
    je_vandr = (p["sku"] or "").startswith("VD-")
    if je_vandr:
        rel = meta.get("files", {}).get("hero_1024")
    else:
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
            chyby.append((pid, "chybi snimek pro azimut %d (front=%s, davka=%s)" % (cil_az, front, batch))); continue
        rel = row["filename"]
    if not rel:
        chyby.append((pid, "chybi cesta k souboru (davka=%s)" % batch)); continue
    src = os.path.join(CF, rel)
    if not os.path.exists(src):
        chyby.append((pid, "soubor na disku chybi: %s" % src)); continue

    dest_name = "product-%d-hover.jpg" % pid
    dest = os.path.join(HOVER_DIR, dest_name)
    shutil.copyfile(src, dest)
    os.chmod(dest, 0o644)
    novy_filename = "vestavby-hover/" + dest_name

    if pid in existujici:
        cur.execute("UPDATE shop_product_images SET filename=%s WHERE id=%s",
                     (novy_filename, existujici[pid]["radek_id"]))
        ok_rowcount = 1
    else:
        cur.execute(
            "INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) VALUES (%s,%s,%s,1)",
            (pid, novy_filename, None),
        )
        ok_rowcount = 1
    if cur.rowcount != ok_rowcount:
        chyby.append((pid, "DB zapis rowcount=%d (ocekavano %d)" % (cur.rowcount, ok_rowcount))); continue
    opraveno += 1

conn.commit()
print("OPRAVENO/DOPLNENO:", opraveno)
print("CHYB:", len(chyby))
for pid, duvod in chyby[:40]:
    print(" ", pid, duvod)
if len(chyby) > 40:
    print("  ... a dalsich", len(chyby) - 40)

# overeni
ids = list(cilovy_seznam.keys())
ph = ",".join(["%s"] * len(ids))
cur.execute(f"SELECT COUNT(*) c FROM shop_product_images WHERE product_id IN ({ph}) AND sort_order=1", ids)
print("OVERENI - hover radku v DB ted:", cur.fetchone()["c"])
