#!/usr/bin/env python3
"""Demo import 1 realne sestavy z vanDrawee (bot5, 2026-09-17, Robert
pres bot7: "chce videt 1 realne importovanou vandrawee kartu jako
demo").

Zdroj: https://vandrawee.eu/cs/detail-sestavy/9f570c6e-d4a0-4f36-a496-2f26522787fa
(bot7 nasel na Robertem oznacenem "zverejnene" seznamu, JA nezavisle
overil primo WebFetch na zivou stranku - vozidlo/cena/vaha/popis
presne sedi, viz AGENTS_LOG). Predchozi pokus o jinou sestavu
(stored_models.id=84, "017bb036-...") byl bot7 stazen - lokalni
/opt/vandrawee DB kopie ma jen 331 nepublikovanych testovacich
zaznamu, shoda ceny+vahy byla nahoda (jiny navrh), ne stejny zaznam.
Tenhle import uz je end-to-end overeny jednim UUID (seznam -> live
detail -> obrazky), zadna shoda podle ceny.

Produkt NEMA product_assemblies vazbu (zadna 3D scena v tomhle
systemu) - je to samostatny staticky katalogovy zaznam, jinak nez
vsechny K-XXX regalove karty tuto session. UUID tracking (Robert pres
bot7: "budouci sledovani/propis UUID do objednavek") jde do
`alternative_product_codes` (JSON, existujici generic sloupec) -
zadny novy sloupec pro jeden demo produkt.

Obrazky (4x PNG, uz stazene bot7, ma vlastni vanDrawee vodoznak
zapecenej primo v renderu - NEPRIDAVAT dalsi, byl by to druhy
prekryvajici se vodoznak) jdou pres content_gallery_items (owner_type=
'product', is_public=1) - PRIORITNI "fotogalerie modul" pro
category_products_with_images()/product.html, ne shop_product_images
(ten je fallback pro Dogus-style bulk import bez rucni kurace).

Karta se zaklada jako active=0 (demo k prohlednuti Robertem v adminu,
ne rovnou verejne) - stejny bezpecny vychozi stav jako u kazde nove
zalozene karty tuto session.

Spusteni NA SERVERU (/opt/konfigurator):
    api/venv/bin/python3 scripts/2026-09-17_bot5_import_vandrawee_demo.py
    api/venv/bin/python3 scripts/2026-09-17_bot5_import_vandrawee_demo.py --apply
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZALOHA_DIR = os.path.join(REPO_ROOT, "backups", "2026-09-17_bot5_import_vandrawee_demo")
GALLERY_ITEMS_DIR = os.path.join(REPO_ROOT, "webapp", "content-files", "gallery-items")

SOURCE_DIR = "/tmp/claude-0/-opt-konfigurator/44c1c190-9cfa-47f2-b304-ecd43dd5d19c/scratchpad/vandrawee_demo_9f570c6e"
VANDRAWEE_UUID = "9f570c6e-d4a0-4f36-a496-2f26522787fa"
VANDRAWEE_DETAIL_URL = f"https://vandrawee.eu/cs/detail-sestavy/{VANDRAWEE_UUID}"

# bot5, 2026-09-17: bot7 doporucil 233 ("Vestavby pro Ducato, Jumper,
# Boxer" - stejna jako u predchoziho, staznuteho pokusu) - ale tohle
# vozidlo je Renault Trafic, jina znacka, spatny hub. Pouzit spravny
# existujici 285 "Vestavby pro Renault" (zatim jen znackovy uzel, bez
# modeloveho listu pro Trafic - stejny stav jako drive Mercedes/VW,
# nez bot7 doplnil listy).
CATEGORY_ID = 285

PRODUCT = {
    "sku": "VD-9f570c6e",
    "name": "Regálová vestavba – Renault Trafic L2H1 (vanDrawee)",
    "slug": "regalova-vestavba-renault-trafic-l2h1-vandrawee",
    "price_czk_placeholder": 48013,  # 1886,5 EUR bez DPH, bez montaze (dle zive stranky)
    "weight_g": 74771,  # 74770.76 g zaokrouhleno
    "description": (
        "Hliníková regálová vestavba do nákladového prostoru Renault Trafic L2H1 "
        "(3498 mm) ze sesterského systému vanDrawee - univerzální police, "
        "upínací plochy, větrání a nohy, doplněné o multibox kontejnery a "
        "ocelové zásuvky.\n\n"
        "Cena je bez montáže - tu je potřeba objednat/domluvit zvlášť."
    ),
    "short_description": (
        "Hliníková regálová vestavba pro Renault Trafic L2H1 (3498 mm) ze "
        "systému vanDrawee - police, zásuvky a multibox kontejnery, cena bez montáže."
    ),
    "meta_title": "Regálová vestavba do Renault Trafic L2H1 (vanDrawee)",
    "meta_description": (
        "Hliníková regálová vestavba do Renault Trafic L2H1 (3498 mm) ze systému "
        "vanDrawee - univerzální police, zásuvky, multibox kontejnery."
    ),
    "unit": "ks",
    "supplier_name": "vanDrawee",
}

IMAGES = [
    {"src": "first_3d_left.png", "caption": "3D pohled zepředu, levá část", "sort_order": 0},
    {"src": "second_3d_left.png", "caption": "3D pohled, druhý úhel, levá část", "sort_order": 1},
    {"src": "2d_left.png", "caption": "2D nákres, levá část", "sort_order": 2},
    {"src": "2d_left_dim.png", "caption": "2D nákres s kótami, levá část", "sort_order": 3},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    print(f"=== import vanDrawee demo (Renault Trafic L2H1) — {'APPLY' if args.apply else 'DRY-RUN'} ===\n")

    for img in IMAGES:
        path = os.path.join(SOURCE_DIR, img["src"])
        if not os.path.exists(path):
            print(f"CHYBA: chybí zdrojový soubor {path}")
            return 1

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (PRODUCT["sku"],))
            if cur.fetchone():
                print(f"Produkt se SKU {PRODUCT['sku']} už existuje, končím (idempotence).")
                return 0

            print(f"Zakládám: {PRODUCT['name']} (SKU {PRODUCT['sku']}, kategorie {CATEGORY_ID})")
            new_id = None
            if args.apply:
                alt_codes = json.dumps({"vandrawee_uuid": VANDRAWEE_UUID, "vandrawee_detail_url": VANDRAWEE_DETAIL_URL})
                cur.execute(
                    "INSERT INTO shop_products "
                    "(category_id, sku, name, slug, description, short_description, meta_title, "
                    " meta_description, unit, price_czk_placeholder, weight_g, supplier_name, "
                    " alternative_product_codes, price_visible_default, hover_show_price, active) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0)",
                    (CATEGORY_ID, PRODUCT["sku"], PRODUCT["name"], PRODUCT["slug"], PRODUCT["description"],
                     PRODUCT["short_description"], PRODUCT["meta_title"], PRODUCT["meta_description"],
                     PRODUCT["unit"], PRODUCT["price_czk_placeholder"], PRODUCT["weight_g"],
                     PRODUCT["supplier_name"], alt_codes, 1, 1),
                )
                new_id = cur.lastrowid
                print(f"  -> shop_products.id={new_id}")

                os.makedirs(ZALOHA_DIR, exist_ok=True)
                copied = []
                for img in IMAGES:
                    src = os.path.join(SOURCE_DIR, img["src"])
                    ext = os.path.splitext(img["src"])[1]
                    fname = f"product-{new_id}_{PRODUCT['slug']}-{uuid.uuid4().hex[:8]}{ext}"
                    dest = os.path.join(GALLERY_ITEMS_DIR, fname)
                    shutil.copyfile(src, dest)
                    # bot5, 2026-09-17: content-files je servirovano www-data,
                    # skript bezi jako root - chown at appka soubor precte i
                    # pripadne dalsi admin akce (mazani atd.) nesahaji na
                    # root-vlastneny soubor (feedback_root_owned_content_files).
                    subprocess.run(["chown", "www-data:www-data", dest], check=True)
                    copied.append((fname, img))
                    cur.execute(
                        "INSERT INTO content_gallery_items "
                        "(owner_type, owner_id, filename, media_type, source_url, caption, is_public, sort_order) "
                        "VALUES ('product', %s, %s, 'image', %s, %s, 1, %s)",
                        (new_id, fname, VANDRAWEE_DETAIL_URL, img["caption"], img["sort_order"]),
                    )
                    print(f"  + obrázek {fname} ({img['caption']})")

                with open(os.path.join(ZALOHA_DIR, "pridano.json"), "w", encoding="utf-8") as f:
                    json.dump({"product_id": new_id, "sku": PRODUCT["sku"], "images": copied},
                               f, ensure_ascii=False, indent=2, default=str)

        if args.apply:
            conn.commit()
            print("\nCOMMIT hotovy.")
        else:
            print("\nDRY-RUN: nic nezapsano.")
    finally:
        conn.close()

    if args.apply:
        conn2 = get_conn()
        try:
            with conn2.cursor() as cur:
                print("\n=== OVERENI z noveho spojeni ===")
                cur.execute("SELECT id, sku, name, active, category_id, price_czk_placeholder FROM shop_products WHERE sku=%s", (PRODUCT["sku"],))
                row = cur.fetchone()
                print("Karta:", row)
                cur.execute("SELECT id, filename, caption, is_public, sort_order FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s ORDER BY sort_order", (row["id"],))
                for r in cur.fetchall():
                    print(" ", r)
        finally:
            conn2.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
