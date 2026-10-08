"""
Stazeni obrazku produktu ze Shoptet exportu do lokalniho uloziste -
bot2, 2026-07-26, faze 2 navazujici na import_shoptet_products.py.

Bezi na pozadi (muze trvat dlouho - tisice obrazku). Pro kazdy produkt
s shoptet_id najde odpovidajici SHOPITEM v XML, stahne az MAX_PER_PRODUCT
obrazku z IMAGES/IMAGE, ulozi do
webapp/content-files/gallery/products/<shoptet_id>/<n>.<ext> a zapise
radek do shop_product_images. Idempotentni - produkty, ktere uz maji
alespon 1 radek v shop_product_images, se preskakuji (lze bezpecne
znovu spustit po preruseni).
"""
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, "/opt/konfigurator/api")
import pymysql
from pymysql.cursors import DictCursor

XML_PATH = "/tmp/produktyshoptet.xml"
IMG_DIR_BASE = "/opt/konfigurator/webapp/content-files/gallery/products"
MAX_PER_PRODUCT = 4

from _env import load_env as _load_env

_cfg = _load_env()
DB_HOST = _cfg["DB_HOST"]
DB_USER = _cfg["DB_USER"]
DB_PASSWORD = _cfg["DB_PASSWORD"]
DB_NAME = _cfg["DB_NAME"]


def get_conn():
    return pymysql.connect(
        host=DB_HOST, port=3306, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
    )


def already_done_ids(cur):
    cur.execute(
        "SELECT DISTINCT p.shoptet_id FROM shop_product_images i "
        "JOIN shop_products p ON p.id = i.product_id WHERE p.shoptet_id IS NOT NULL"
    )
    return {r["shoptet_id"] for r in cur.fetchall()}


def fetch_bytes(url, timeout=15):
    safe_url = urllib.parse.quote(url, safe=":/?&=%")
    req = urllib.request.Request(safe_url, headers={"User-Agent": "Mozilla/5.0 (konfigurator-shoptet-import)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def ext_from_url(url):
    path = url.split("?")[0]
    ext = path.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    return ext


def main():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, shoptet_id FROM shop_products WHERE shoptet_id IS NOT NULL")
        product_by_shoptet_id = {r["shoptet_id"]: r["id"] for r in cur.fetchall()}
        done = already_done_ids(cur)
    conn.close()

    print(f"produktu s shoptet_id: {len(product_by_shoptet_id)}, uz hotovo: {len(done)}", flush=True)

    todo_ids = set(product_by_shoptet_id) - done
    stats = {"products_done": 0, "images_downloaded": 0, "images_failed": 0, "products_no_images": 0}

    context = ET.iterparse(XML_PATH, events=("end",))
    conn = get_conn()
    cur = conn.cursor()
    processed_since_commit = 0

    for event, elem in context:
        if elem.tag != "SHOPITEM":
            continue
        sid_raw = elem.get("id")
        if not sid_raw:
            elem.clear()
            continue
        sid = int(sid_raw)
        if sid not in todo_ids:
            elem.clear()
            continue

        images_el = elem.find("IMAGES")
        urls = []
        if images_el is not None:
            for img in images_el.findall("IMAGE"):
                if img.text and img.text.strip():
                    urls.append(img.text.strip())
        urls = urls[:MAX_PER_PRODUCT]

        if not urls:
            stats["products_no_images"] += 1
            todo_ids.discard(sid)
            elem.clear()
            continue

        product_id = product_by_shoptet_id[sid]
        out_dir = os.path.join(IMG_DIR_BASE, str(sid))
        os.makedirs(out_dir, exist_ok=True)

        saved_any = False
        for idx, url in enumerate(urls, start=1):
            ext = ext_from_url(url)
            filename = f"{idx}.{ext}"
            local_path = os.path.join(out_dir, filename)
            try:
                data = fetch_bytes(url)
                with open(local_path, "wb") as fh:
                    fh.write(data)
                cur.execute(
                    "INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) "
                    "VALUES (%s,%s,%s,%s)",
                    (product_id, f"products/{sid}/{filename}", url, idx),
                )
                stats["images_downloaded"] += 1
                saved_any = True
            except Exception as e:
                stats["images_failed"] += 1
                print(f"  chyba stazeni {url}: {e}", flush=True)

        if saved_any:
            stats["products_done"] += 1
        todo_ids.discard(sid)
        elem.clear()
        processed_since_commit += 1

        if processed_since_commit >= 25:
            conn.commit()
            processed_since_commit = 0
            print(f"... produktu hotovo={stats['products_done']} obrazku={stats['images_downloaded']} "
                  f"chyb={stats['images_failed']} bez_obrazku={stats['products_no_images']} "
                  f"(zbyva ~{len(todo_ids)})", flush=True)

    conn.commit()
    conn.close()
    print("\n=== HOTOVO ===")
    print(stats)


if __name__ == "__main__":
    main()
