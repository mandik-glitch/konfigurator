"""
Import katalogu Shoptet (produktyshoptet.xml) do shop_products - bot2,
2026-07-26. Robert: "založ všechny sloupce u nás, ty které jsou v
souboru vyplněny... resp přibudou na skladových kartách", pak
upřesněno přes AskUserQuestion: (1) spárovat/přidat podle Shoptet CODE
(nic nemazat), (2) vybudovat stromovou strukturu kategorií.

Tahle faze resi jen produkty + kategorie (rychle, bez site). Obrazky
resi samostatny skript download_shoptet_images.py (na pozadi, protoze
stahovani tisicu obrazku trva dlouho).

Bezpecnostni pravidlo: shoptet_id je primarni klic pro parovani (VZDY
pritomny, na rozdil od CODE, ktery chybi u ~23 "variant parent"
produktu). Na existujicich (spárovaných) produktech se NIKDY neprepisuje
stock_qty/min_stock/max_stock/active/is_archived/sku - to jsou nase
provozni data.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime

LIMIT = int(os.environ.get("SHOPTET_IMPORT_LIMIT", "0")) or None

sys.path.insert(0, "/opt/konfigurator/api")
import pymysql
from pymysql.cursors import DictCursor

XML_PATH = "/tmp/produktyshoptet.xml"

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


def text_of(el, tag):
    if el is None:
        return None
    child = el.find(tag)
    if child is None or child.text is None:
        return None
    t = child.text.strip()
    return t or None


def float_of(el, tag):
    t = text_of(el, tag)
    if t is None:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def int_of(el, tag):
    f = float_of(el, tag)
    return int(f) if f is not None else None


# ---------------------------------------------------------------------------
# Kategorie - postavit strom z unikatnich cest DEFAULT_CATEGORY
# ---------------------------------------------------------------------------

def get_or_create_category(cur, cache, path_parts):
    """path_parts: list nazvu od korene. Vraci id nejhlubsi kategorie,
    cestou vytvori/znovupouzije kazdou uroven (cache klic = tuple cesty)."""
    key = tuple(path_parts)
    if key in cache:
        return cache[key]
    parent_id = None
    partial = []
    for name in path_parts:
        partial.append(name)
        pkey = tuple(partial)
        if pkey in cache:
            parent_id = cache[pkey]
            continue
        row = None
        if parent_id is None:
            cur.execute("SELECT id FROM content_categories WHERE name=%s AND parent_id IS NULL", (name,))
        else:
            cur.execute("SELECT id FROM content_categories WHERE name=%s AND parent_id=%s", (name, parent_id))
        row = cur.fetchone()
        if row:
            cat_id = row["id"]
        else:
            cur.execute(
                "INSERT INTO content_categories (parent_id, name, sort_order) VALUES (%s,%s,0)",
                (parent_id, name),
            )
            cat_id = cur.lastrowid
        cache[pkey] = cat_id
        parent_id = cat_id
    return parent_id


def main():
    conn = get_conn()
    cat_cache = {}
    stats = {"inserted": 0, "updated": 0, "skipped_no_id": 0, "categories_created_before": 0, "items_total": 0}

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM content_categories")
        stats["categories_created_before"] = cur.fetchone()["n"]

    context = ET.iterparse(XML_PATH, events=("end",))
    now = datetime.now()
    batch = 0

    with conn.cursor() as cur:
        for event, elem in context:
            if elem.tag != "SHOPITEM":
                continue
            stats["items_total"] += 1
            shoptet_id = elem.get("id")
            if not shoptet_id:
                stats["skipped_no_id"] += 1
                elem.clear()
                continue
            shoptet_id = int(shoptet_id)

            name = text_of(elem, "NAME") or f"Shoptet #{shoptet_id}"
            guid = text_of(elem, "GUID")
            code = text_of(elem, "CODE")
            ean = text_of(elem, "EAN")
            unit = text_of(elem, "UNIT") or "ks"
            price = float_of(elem, "PRICE")
            description = None
            desc_el = elem.find("DESCRIPTION")
            if desc_el is not None and desc_el.text:
                description = desc_el.text.strip() or None
            short_desc = None
            sd_el = elem.find("SHORT_DESCRIPTION")
            if sd_el is not None and sd_el.text:
                short_desc = sd_el.text.strip() or None
            manufacturer = text_of(elem, "MANUFACTURER")
            supplier = text_of(elem, "SUPPLIER")
            warranty = text_of(elem, "WARRANTY")
            visible = text_of(elem, "VISIBLE")
            active = 1 if (visible is None or visible == "1") else 0

            logistic = elem.find("LOGISTIC")
            weight_g = float_of(logistic, "WEIGHT") if logistic is not None else None
            if weight_g == 0:
                weight_g = None

            stock_el = elem.find("STOCK")
            stock_hint = int_of(stock_el, "AMOUNT") if stock_el is not None else None
            stock_min_supply = int_of(elem, "STOCK_MIN_SUPPLY")

            avail_out = text_of(elem, "AVAILABILITY_OUT_OF_STOCK")
            avail_in = text_of(elem, "AVAILABILITY_IN_STOCK")
            availability_text = avail_in or avail_out

            cats = elem.find("CATEGORIES")
            category_path = None
            category_id = None
            if cats is not None:
                dc = cats.find("DEFAULT_CATEGORY")
                if dc is not None and dc.text and dc.text.strip():
                    category_path = dc.text.strip()
                    parts = [p.strip() for p in category_path.split(">")]
                    category_id = get_or_create_category(cur, cat_cache, parts)

            alt_codes = None
            alt_el = elem.find("ALTERNATIVE_PRODUCTS")
            if alt_el is not None:
                codes = [c.text.strip() for c in alt_el.findall("CODE") if c.text and c.text.strip()]
                if codes:
                    alt_codes = json.dumps(codes, ensure_ascii=False)

            rel_codes = None
            rel_el = elem.find("RELATED_PRODUCTS")
            if rel_el is not None:
                codes = [c.text.strip() for c in rel_el.findall("CODE") if c.text and c.text.strip()]
                if codes:
                    rel_codes = json.dumps(codes, ensure_ascii=False)

            variants_el = elem.find("VARIANTS")
            has_variants = 0
            variant_count = 0
            if variants_el is not None:
                vs = variants_el.findall("VARIANT")
                if vs:
                    has_variants = 1
                    variant_count = len(vs)

            set_items_el = elem.find("SET_ITEMS")
            has_set_items = 1 if (set_items_el is not None and len(set_items_el.findall("SET_ITEM")) > 0) else 0

            sku_value = code or f"SHOPTET-{shoptet_id}"

            cur.execute("SELECT id FROM shop_products WHERE shoptet_id=%s", (shoptet_id,))
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """UPDATE shop_products SET
                        shoptet_code=%s, shoptet_guid=%s, ean=%s, name=%s, description=%s,
                        short_description=%s, unit=%s, manufacturer=%s, supplier_name=%s,
                        warranty=%s, availability_text=%s, category_path=%s, category_id=%s,
                        stock_min_supply=%s, shoptet_stock_hint=%s, alternative_product_codes=%s,
                        related_product_codes=%s, has_variants=%s, variant_count=%s, has_set_items=%s,
                        weight_g=COALESCE(%s, weight_g), price_czk_placeholder=COALESCE(%s, price_czk_placeholder),
                        shoptet_updated_at=%s
                       WHERE id=%s""",
                    (code, guid, ean, name, description, short_desc, unit, manufacturer, supplier,
                     warranty, availability_text, category_path, category_id,
                     stock_min_supply, stock_hint, alt_codes, rel_codes, has_variants, variant_count,
                     has_set_items, weight_g, price, now, existing["id"]),
                )
                stats["updated"] += 1
            else:
                cur.execute(
                    """INSERT INTO shop_products
                       (shoptet_id, shoptet_code, shoptet_guid, ean, sku, name, description,
                        short_description, unit, price_czk_placeholder, weight_g, stock_qty,
                        manufacturer, supplier_name, warranty, availability_text, category_path,
                        category_id, stock_min_supply, shoptet_stock_hint, alternative_product_codes,
                        related_product_codes, has_variants, variant_count, has_set_items,
                        active, is_archived, is_placeholder, shoptet_imported_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s, %s,%s,%s,%s,0, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,%s, %s,0,0,%s)""",
                    (shoptet_id, code, guid, ean, sku_value, name, description,
                     short_desc, unit, price, weight_g,
                     manufacturer, supplier, warranty, availability_text, category_path,
                     category_id, stock_min_supply, stock_hint, alt_codes,
                     rel_codes, has_variants, variant_count, has_set_items,
                     active, now),
                )
                stats["inserted"] += 1

            elem.clear()
            batch += 1
            if batch % 200 == 0:
                conn.commit()
                print(f"... {batch} zpracovano (inserted={stats['inserted']} updated={stats['updated']})", flush=True)
            if LIMIT and batch >= LIMIT:
                print(f"(SHOPTET_IMPORT_LIMIT={LIMIT} dosazen, konci drive)")
                break

    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM content_categories")
        stats["categories_after"] = cur.fetchone()["n"]
    conn.close()

    print("\n=== HOTOVO ===")
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
