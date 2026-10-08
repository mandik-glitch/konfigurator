"""
Extrakce schematickych/pouzitich obrazku z PDF katalogu Dogus Kalip
("Konstrukční hliníkový systém Dogus - Logiman.pdf", nahran na sdileny
disk 2026-08-10, slozka "Dogus" id=51) a jejich ulozeni jako nove
soubory ve sdilenem disku (Robert: "nahraju na sdileny disk katalog
pdf kde jsou dily v tabulkach podle sku, najdes pobliz techto tabulek
schematicke nahledy tykajici se danych polozek... postahuj vsechny,
uloz vedle pdf katalogu na disku").

Postup:
1. Pro kazdou stranku PDF zkontroluje, jestli obsahuje SKU vzor
   (\\d.\\d.NNN.cislice... - presne format shop_products.sku, napr.
   "2.1.012.08.01") - to jsou stranky s produktovou tabulkou.
2. Na takove strance vytahne VSECHNY vlozene obrazky (schemata,
   parametricke vykresy, fotky pouziti - overeno rucne na strane 79
   proti Robertovu screenshotu, presne odpovida).
3. Male obrazky (<100px na kratsi strane - ikonky/loga v hlavicce)
   se preskakuji.
4. Ulozi do NOVE podslozky "Schémata dílů (z PDF katalogu)" pod
   slozkou "Dogus" (id=51) - fyzicky soubory do
   private-files/shared-drive/ (stejna konvence jako PRIVATE_FILES_DIR/
   shared-drive v api/drive.py), zaznamy do shared_drive_files, aby se
   zobrazily v adminu na Sdilenem disku hned vedle puvodniho PDF.

Overeno pred spustenim: 402 obrazku napric 101 strankami se SKU, jen
1 duplicitni pár (md5 shoda) - katalog neobsahuje vyznamnou redundanci
(zadne opakujici se logo/hlavicka nad limitem 100px).
"""
import hashlib
import json
import os
import re
import sys

import pymupdf
import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

PRIVATE_FILES_DIR = "/opt/konfigurator/private-files"
DRIVE_FILES_DIR = os.path.join(PRIVATE_FILES_DIR, "shared-drive")
PDF_PATH = os.path.join(DRIVE_FILES_DIR, "aad9e5b5ddcfea80a383cbae2efd34c1.pdf")
DOGUS_FOLDER_ID = 51
NEW_FOLDER_NAME = "Schémata dílů (z PDF katalogu)"
MIN_DIM = 100
UPLOADED_BY = 1  # stejny ucet, ktery nahral PDF (id=1)

SKU_RE = re.compile(r"\b\d\.\d\.\d{2,3}\.[\d.]+\b")


def safe_stored_filename(ext):
    ext = re.sub(r"[^a-zA-Z0-9]", "", ext)[:10].lower()
    token = os.urandom(16).hex()
    return f"{token}.{ext}" if ext else token


def content_type_for(ext):
    return {"jpeg": "image/jpeg", "jpg": "image/jpeg", "png": "image/png"}.get(ext, f"image/{ext}")


def main():
    dry_run = "--apply" not in sys.argv
    if not os.path.exists(PDF_PATH):
        print("CHYBA: PDF nenalezeno na", PDF_PATH)
        sys.exit(1)

    doc = pymupdf.open(PDF_PATH)
    plan = []
    seen_hashes_global = {}
    for i, page in enumerate(doc):
        text = page.get_text()
        skus = list(dict.fromkeys(SKU_RE.findall(text)))
        if not skus:
            continue
        seen_xrefs = set()
        idx = 0
        for img in page.get_images(full=True):
            xref = img[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            base = doc.extract_image(xref)
            w, h = base.get("width", 0), base.get("height", 0)
            if min(w, h) < MIN_DIM:
                continue
            content_hash = hashlib.md5(base["image"]).hexdigest()
            if content_hash in seen_hashes_global:
                continue  # identicky obrazek uz zpracovan (napr. na jine strane)
            seen_hashes_global[content_hash] = True
            idx += 1
            sku_part = "+".join(s.replace(".", "-") for s in skus[:2])
            if len(skus) > 2:
                sku_part += "+dalsi"
            fname = f"str{i + 1:03d}_{sku_part}_{idx}.{base['ext']}"
            plan.append({
                "page": i + 1, "skus": skus, "ext": base["ext"],
                "image": base["image"], "filename": fname,
            })

    pages_count = len(set(p["page"] for p in plan))
    print(f"Stranek se SKU tabulkou: {pages_count}")
    print(f"Obrazku k ulozeni (po filtru velikosti/duplicit): {len(plan)}")
    print(f"Celkova velikost: {sum(len(p['image']) for p in plan) / 1024 / 1024:.1f} MB")
    print("\nNahled prvnich 15:")
    for p in plan[:15]:
        print(f"  str.{p['page']:3d}  {p['skus']}  -> {p['filename']}")
    if len(plan) > 15:
        print(f"  ... a dalsich {len(plan) - 15}")

    if dry_run:
        print("\nDRY RUN - nic neulozeno/nezapsano. Spust s --apply pro skutecne ulozeni.")
        return

    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM shared_drive_folders WHERE parent_folder_id=%s AND name=%s",
        (DOGUS_FOLDER_ID, NEW_FOLDER_NAME),
    )
    existing = cur.fetchone()
    if existing:
        folder_id = existing["id"]
        print(f"\nPodslozka '{NEW_FOLDER_NAME}' uz existuje (id={folder_id}), pridavam do ni.")
    else:
        cur.execute(
            "INSERT INTO shared_drive_folders (parent_folder_id, name, created_by) VALUES (%s,%s,%s)",
            (DOGUS_FOLDER_ID, NEW_FOLDER_NAME, UPLOADED_BY),
        )
        conn.commit()
        folder_id = cur.lastrowid
        print(f"\nVytvorena podslozka '{NEW_FOLDER_NAME}' (id={folder_id}) pod Dogus (id={DOGUS_FOLDER_ID}).")

    manifest = []
    n = 0
    for p in plan:
        stored = safe_stored_filename(p["ext"])
        with open(os.path.join(DRIVE_FILES_DIR, stored), "wb") as f:
            f.write(p["image"])
        cur.execute(
            "INSERT INTO shared_drive_files "
            "(folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by, sort_order) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (folder_id, p["filename"], stored, content_type_for(p["ext"]), len(p["image"]), UPLOADED_BY, p["page"]),
        )
        manifest.append({"page": p["page"], "skus": p["skus"], "filename": p["filename"], "stored_filename": stored})
        n += 1
    conn.commit()

    manifest_path = "backups/dogus_katalog_schemata_manifest_20260810.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Zapsano {n} obrazku do slozky id={folder_id}. Manifest -> {manifest_path}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
