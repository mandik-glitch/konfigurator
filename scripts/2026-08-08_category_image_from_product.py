#!/usr/bin/env python3
"""
Doplneni obrazku kategoriim, ktere zadny nemaji (Robert, 2026-08-08:
"zaloz pravidlo, kdyz kategorii chybi obrazek, vloz tam nejvhodnejsi z
produktu uvnitr kategorie"). Pravidlo zapsano ve WORKFLOW.md ("AKTIVNI
POKYNY OD ROBERTA", bod 8).

Pro kazdou LISTOVOU kategorii (bez podkategorii) s image_filename IS
NULL se zkusi postupne 3 zdroje (prvni uspesny vyhrava):

  1. Prvni aktivni produkt v kategorii (podle id), ktery ma obrazek v
     shop_product_images - preferuje se fotorealisticky render (vyssi
     sort_order) pred technickym schematem.
  2. Vlastni fotogalerie kategorie (content_gallery_items,
     owner_type='category') - prvni polozka podle sort_order.
  3. Prvni "rozumne velky" <img> v content_pages.body_html dane
     kategorie (starsi obsah stranek zkopirovany z logiman.cz casto
     ma fotky vlozene primo v popisu, ne v samostatne galerii) -
     obrazky mensi nez MIN_DIM px (typicky podpisy/loga v patce textu,
     viz kategorie 237 "mandik.jpg" 141x15) se preskakuji.

Vybrany obrazek se zkopiruje do stejne konvence jako
_save_category_image() v api/app.py ({cat_id}_image_filename_{hex}.{ext}
v webapp/content-files/categories/), content_categories.image_filename
se aktualizuje primo (zadne HTTP API, stejny pristup jako drivejsi
2026-07-26_import_category_images_logiman.py).

Idempotentni - kategorie, co uz obrazek maji, se preskoci. Bezpecne
spoustet opakovane (napr. kdyz pribyde nova kategorie bez obrazku).
"""
import os
import re
import shutil

import pymysql
from PIL import Image

API_DIR = "/opt/konfigurator/api"
CATEGORY_IMAGE_DIR = "/opt/konfigurator/webapp/content-files/categories"
GALLERY_ROOT = "/opt/konfigurator/webapp/content-files/gallery"
GALLERY_ITEMS_DIR = "/opt/konfigurator/webapp/content-files/gallery-items"
CONTENT_FILES_ROOT = "/opt/konfigurator/webapp/content-files"
MIN_DIM = 100
IMG_RE = re.compile(r'<img [^>]*src="([^"]+)"')


def load_env():
    env = {}
    with open(os.path.join(API_DIR, ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def get_conn(env):
    return pymysql.connect(
        host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)),
        user=env["DB_USER"], password=env["DB_PASSWORD"],
        database=env["DB_NAME"], cursorclass=pymysql.cursors.DictCursor,
    )


def is_big_enough(path):
    try:
        with Image.open(path) as im:
            w, h = im.size
        return w >= MIN_DIM and h >= MIN_DIM
    except Exception:
        return False


def find_source_image(cur, cat):
    # 1) produkt uvnitr kategorie
    cur.execute(
        "SELECT sp.id FROM shop_products sp WHERE sp.category_id=%s AND sp.active=1 ORDER BY sp.id",
        (cat["id"],),
    )
    for row in cur.fetchall():
        cur.execute(
            "SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order DESC LIMIT 1",
            (row["id"],),
        )
        img = cur.fetchone()
        if img:
            path = os.path.join(GALLERY_ROOT, img["filename"])
            if os.path.exists(path) and is_big_enough(path):
                return path, f"produkt {row['id']}"

    # 2) vlastni fotogalerie kategorie
    cur.execute(
        "SELECT filename FROM content_gallery_items WHERE owner_type='category' AND owner_id=%s "
        "ORDER BY sort_order LIMIT 1",
        (cat["id"],),
    )
    row = cur.fetchone()
    if row:
        path = os.path.join(GALLERY_ITEMS_DIR, row["filename"])
        if os.path.exists(path) and is_big_enough(path):
            return path, "vlastni galerie kategorie"

    # 3) prvni rozumne velky <img> v popisu kategorie
    cur.execute("SELECT body_html FROM content_pages WHERE category_id=%s", (cat["id"],))
    row = cur.fetchone()
    body = (row or {}).get("body_html") or ""
    for src in IMG_RE.findall(body):
        if not src.startswith("/content-files/"):
            continue
        path = CONTENT_FILES_ROOT + src[len("/content-files"):]
        if os.path.exists(path) and is_big_enough(path):
            return path, "obrazek v popisu kategorie"

    return None, None


def main():
    env = load_env()
    os.makedirs(CATEGORY_IMAGE_DIR, exist_ok=True)
    conn = get_conn(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, image_filename FROM content_categories")
            categories = cur.fetchall()
            cur.execute("SELECT id, parent_id FROM content_categories")
            has_children = set()
            for r in cur.fetchall():
                if r["parent_id"] is not None:
                    has_children.add(r["parent_id"])

            missing = [c for c in categories if not c["image_filename"] and c["id"] not in has_children]
            print(f"Listovych kategorii bez obrazku: {len(missing)}")

            updated, skipped = [], []
            for cat in missing:
                src_path, source_desc = find_source_image(cur, cat)
                if not src_path:
                    skipped.append((cat["id"], cat["name"], "zadny vhodny zdroj obrazku"))
                    continue

                ext = src_path.rsplit(".", 1)[-1].lower()
                stored_name = f"{cat['id']}_image_filename_{os.urandom(6).hex()}.{ext}"
                dest_path = os.path.join(CATEGORY_IMAGE_DIR, stored_name)
                shutil.copyfile(src_path, dest_path)
                os.system(f"chown www-data:www-data {dest_path!r}")
                cur.execute(
                    "UPDATE content_categories SET image_filename=%s WHERE id=%s",
                    (stored_name, cat["id"]),
                )
                updated.append((cat["id"], cat["name"], source_desc, stored_name))
        conn.commit()
    finally:
        conn.close()

    print(f"\nDoplneno: {len(updated)}")
    for u in updated:
        print(" ", u)
    print(f"\nPreskoceno (nema z ceho vzit obrazek): {len(skipped)}")
    for s in skipped:
        print(" ", s)


if __name__ == "__main__":
    main()
