"""
Zkopiruje ilustracni obrazky pouziti (extrahovane z Dogus PDF katalogu,
viz scripts/2026-08-10_dogus_katalog_schemata_extract.py) z privatniho
sdileneho disku (private-files/shared-drive/, slozka "Schémata dílů"
id=52) do VEREJNEHO webapp/content-files/product-usage/ a napoji je na
konkretni produkty pres novou tabulku product_usage_images (viz
sql/2026-08-10_product_usage_images.sql).

Robert: "navrhni kam to na eshop umistime... jsou to ilustracni
nahledy pouziti nasich prvku v praxi" -> zvolil zobrazit na detailu
produktu prislusenstvi I na strankach profilu (kompatibilita uz
existuje, viz _compatible_accessories v api/app.py).

Pouziva stejnou parovaci logiku jako predchozi Artifact tabulka
(scripts/2026-08-10_dogus_schemata_manifest_upload.py) - jen produkty
se STATUS "full" nebo "partial" (aspon 1 SKU na obrazku se nasel v
katalogu). "none" (0 shod) se preskakuje - neni na co napojit.

Idempotentni: kontroluje existujici (product_id, source_page) dvojice
v product_usage_images pred vlozenim, aby opakovane spusteni
neduplikovalo.
"""
import os
import shutil
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

DRIVE_FILES_DIR = "/opt/konfigurator/private-files/shared-drive"
PUBLIC_DIR = "/opt/konfigurator/webapp/content-files/product-usage"
FOLDER_ID = 52
WWW_DATA_UID = 33
WWW_DATA_GID = 33


def build_matches(cur):
    cur.execute(
        "SELECT id, filename, stored_filename, sort_order FROM shared_drive_files WHERE folder_id=%s",
        (FOLDER_ID,),
    )
    images = cur.fetchall()

    import json
    manifest = json.load(open("backups/dogus_katalog_schemata_manifest_20260810.json", encoding="utf-8"))
    manifest_by_stored = {m["stored_filename"]: m for m in manifest}

    all_skus = set()
    for img in images:
        m = manifest_by_stored.get(img["stored_filename"])
        if m:
            all_skus.update(m["skus"])
    placeholders = ",".join(["%s"] * len(all_skus))
    cur.execute(f"SELECT id, sku FROM shop_products WHERE sku IN ({placeholders})", list(all_skus))
    sku_to_pid = {r["sku"]: r["id"] for r in cur.fetchall()}

    # (stored_filename, source_page) -> set(product_id)
    plan = []
    for img in images:
        m = manifest_by_stored.get(img["stored_filename"])
        if not m:
            continue
        pids = sorted({sku_to_pid[s] for s in m["skus"] if s in sku_to_pid})
        if not pids:
            continue
        plan.append({"stored_filename": img["stored_filename"], "page": img["sort_order"], "product_ids": pids})
    return plan


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    plan = build_matches(cur)
    total_links = sum(len(p["product_ids"]) for p in plan)
    print(f"Obrazku s aspon 1 shodou: {len(plan)}, celkem vazeb (obrazek x produkt): {total_links}")

    cur.execute("SELECT product_id, source_page FROM product_usage_images")
    existing = {(r["product_id"], r["source_page"]) for r in cur.fetchall()}
    to_insert = []
    for p in plan:
        for pid in p["product_ids"]:
            if (pid, p["page"]) in existing:
                continue
            to_insert.append((p["stored_filename"], p["page"], pid))

    print(f"Novych vazeb k vlozeni (jiz existujici preskoceny): {len(to_insert)}")
    if dry_run:
        for stored, page, pid in to_insert[:15]:
            print(f"  produkt #{pid} <- str.{page} ({stored})")
        if len(to_insert) > 15:
            print(f"  ... a dalsich {len(to_insert) - 15}")
        print("\nDRY RUN - nic nezkopirovano/nezapsano. Spust s --apply pro skutecne provedeni.")
        return

    copied_cache = {}  # stored_filename -> public filename (kopirovat kazdy fyzicky soubor jen 1x)
    n = 0
    for stored, page, pid in to_insert:
        if stored not in copied_cache:
            token = os.urandom(16).hex()
            ext = stored.rsplit(".", 1)[-1]
            public_name = f"usage_{token}.{ext}"
            src = os.path.join(DRIVE_FILES_DIR, stored)
            dst = os.path.join(PUBLIC_DIR, public_name)
            shutil.copyfile(src, dst)
            os.chown(dst, WWW_DATA_UID, WWW_DATA_GID)
            copied_cache[stored] = public_name
        public_name = copied_cache[stored]
        cur.execute(
            "INSERT INTO product_usage_images (product_id, filename, source_page, sort_order) VALUES (%s,%s,%s,%s)",
            (pid, public_name, page, page),
        )
        n += 1
    conn.commit()
    print(f"Zkopirovano {len(copied_cache)} unikatnich souboru, vlozeno {n} vazeb produkt<->obrazek.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
