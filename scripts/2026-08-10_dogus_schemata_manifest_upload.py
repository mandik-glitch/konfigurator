"""
Ulozeni vazeb obrazek->SKU->produkt (viz predchozi Artifact tabulka
parovani) natrvalo na sdileny disk, vedle uz nahranych 283 obrazku
(slozka "Schémata dílů (z PDF katalogu)", id=52) - Robert: "zkusme to
tedy nahrat nejdrive s temito vazbami na sdileny, pro dalsi pouziti".

Ocekava jako vstup backups/dogus_katalog_schemata_manifest_20260810.json
(puvodni extrakce) + zivy stav shared_drive_files (po promazani
profilove casti) + shop_products (pro sparovani SKU->produkt).

Vystup 2 soubory nahrane do stejne slozky (id=52):
  - prirazeni_k_produktum.json - strojove citelny manifest (bez
    obrazovych dat, jen vazby) pro pozdejsi automatizovane napojeni
    obrazku na produktove galerie.
  - prirazeni_k_produktum.csv - lidsky citelny prehled (1 radek na
    dvojici obrazek+SKU), otevrat lze primo v Excelu/Sheets.

sort_order=-1 u obou (zobrazi se prvni v seznamu slozky, pred
samotnymi 283 obrazky se sort_order=cislo stranky).
"""
import csv
import io
import json
import os
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
FOLDER_ID = 52
UPLOADED_BY = 1
WWW_DATA_UID = 33
WWW_DATA_GID = 33


def build_rows(cur):
    cur.execute("SELECT id, filename, stored_filename, sort_order FROM shared_drive_files WHERE folder_id=%s", (FOLDER_ID,))
    current = {r["stored_filename"]: r for r in cur.fetchall()}

    manifest = json.load(open("backups/dogus_katalog_schemata_manifest_20260810.json", encoding="utf-8"))
    remaining = [m for m in manifest if m["stored_filename"] in current]

    all_skus = set()
    for m in remaining:
        all_skus.update(m["skus"])
    placeholders = ",".join(["%s"] * len(all_skus))
    cur.execute(f"SELECT id, sku, name, active FROM shop_products WHERE sku IN ({placeholders})", list(all_skus))
    found = {r["sku"]: r for r in cur.fetchall()}

    rows = []
    for m in remaining:
        fid = current[m["stored_filename"]]["id"]
        matches = []
        for sku in m["skus"]:
            p = found.get(sku)
            matches.append({"sku": sku, "product_id": p["id"] if p else None,
                             "product_name": p["name"] if p else None,
                             "product_active": bool(p["active"]) if p else None})
        n_matched = sum(1 for x in matches if x["product_id"])
        status = "full" if n_matched == len(matches) else ("partial" if n_matched else "none")
        rows.append({"shared_drive_file_id": fid, "page": m["page"], "filename": m["filename"],
                     "status": status, "matches": matches})
    rows.sort(key=lambda r: r["page"])
    return rows


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    rows = build_rows(cur)
    print(f"Radku (obrazku): {len(rows)}")

    json_bytes = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["obrazek_id", "strana", "soubor", "sku", "produkt_id", "nazev_produktu", "aktivni", "stav_parovani"])
    for r in rows:
        for m in r["matches"]:
            w.writerow([r["shared_drive_file_id"], r["page"], r["filename"], m["sku"], m["product_id"] or "",
                        m["product_name"] or "NENALEZENO",
                        "ano" if m["product_active"] else ("ne" if m["product_active"] is False else ""),
                        r["status"]])
    csv_bytes = ("﻿" + buf.getvalue()).encode("utf-8")

    print(f"JSON: {len(json_bytes)} B, CSV: {len(csv_bytes)} B")
    if dry_run:
        print("\nDRY RUN - nic nenahrano. Spust s --apply pro skutecne nahrani.")
        return

    for fname, ctype, data in [
        ("prirazeni_k_produktum.json", "application/json", json_bytes),
        ("prirazeni_k_produktum.csv", "text/csv", csv_bytes),
    ]:
        stored = f"{os.urandom(16).hex()}.{fname.rsplit('.', 1)[-1]}"
        path = os.path.join(DRIVE_FILES_DIR, stored)
        with open(path, "wb") as f:
            f.write(data)
        os.chown(path, WWW_DATA_UID, WWW_DATA_GID)
        cur.execute(
            "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by, sort_order) "
            "VALUES (%s,%s,%s,%s,%s,%s,-1)",
            (FOLDER_ID, fname, stored, ctype, len(data), UPLOADED_BY),
        )
        print(f"Nahrano: {fname} -> {stored}")
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
