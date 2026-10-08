#!/usr/bin/env python3
"""Backfill centralni fotogalerie (content_photo_library +
content_photo_library_categories) ze tri stavajicich mechanismu, bez
presunu/prejmenovani souboru na disku (viz sql/2026-09-12_content_photo_
library.sql pro zduvodneni - image_watermark_manifest.rel_path).

Idempotentni: znovu-spusteni preskoci uz existujici radky (podle
file_path UNIQUE), nic neodecte ani nezdvoji.

Zdroje (jen NASE fotky, zadny Dogus - overeno, ze v content_gallery_items
zadny radek na Dogus produkt neni navazany):
  1. shop_gallery_images (226) -> realizace_tag = category, BEZ
     category_id (buckety nejsou eshopove kategorie).
  2. content_gallery_items owner_type='category' (5) -> M:N na
     existujici category_id. owner_type='product' (1) je MIMO ROZSAH
     (Robertovo zadani mluvi o kategoriich), necha se na stare tabulce.
  3. Obrazky vlozene primo do content_pages.body_html/intro_html/
     bottom_body_html pod content-files/kategorie-popisy/<cat_id>/... -
     zadny DB radek dnes, jen text. Parsuje se regexem, kontroluje se
     existence souboru na disku pred zapisem.

Watermark manifest overeni (bot3 pozadavek, cislem ne tvrzenim): pocet
radku manifestu odpovidajicich VSEM kandidatnim cestam se zmeri PRED
zapisem (dve nezavisla cteni z jiz existujicich zdrojovych tabulek/
souboru, zadny zapis do manifestu tady vubec nenastane) a znovu PO
zapisu - musi vyjit stejne cislo, protoze tenhle skript manifest
nikdy nemeni, jen cte.
"""
import json
import os
import re

import pymysql

ROOT = "/opt/konfigurator"
WEBAPP = os.path.join(ROOT, "webapp")


def load_env():
    env = {}
    with open(os.path.join(ROOT, "api", ".env")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def get_conn():
    env = load_env()
    return pymysql.connect(host=env["DB_HOST"], port=int(env["DB_PORT"]), user=env["DB_USER"],
                            password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
                            cursorclass=pymysql.cursors.DictCursor, autocommit=False)


IMG_REF_RE = re.compile(r"kategorie-popisy/(\d+)/([^\"'\)\s]+)")


def candidate_paths_shop_gallery_images(cur):
    cur.execute("SELECT id, category, filename, alt_text, title, sort_order, active FROM shop_gallery_images")
    rows = cur.fetchall()
    out = []
    for r in rows:
        fp = f"content-files/gallery/{r['category']}/{r['filename']}"
        out.append((fp, r))
    return out


def candidate_paths_content_gallery_items(cur):
    cur.execute(
        "SELECT id, owner_id, filename, caption, sort_order, is_public "
        "FROM content_gallery_items WHERE owner_type='category'"
    )
    rows = cur.fetchall()
    return [(f"content-files/gallery-items/{r['filename']}", r) for r in rows]


def candidate_paths_kategorie_popisy(cur):
    cur.execute(
        "SELECT category_id, body_html, bottom_body_html, intro_html FROM content_pages "
        "WHERE body_html LIKE '%kategorie-popisy%' OR bottom_body_html LIKE '%kategorie-popisy%' "
        "OR intro_html LIKE '%kategorie-popisy%'"
    )
    rows = cur.fetchall()
    out = []
    kategorii = 0
    for r in rows:
        text = (r["body_html"] or "") + " " + (r["bottom_body_html"] or "") + " " + (r["intro_html"] or "")
        distinct = sorted(set(IMG_REF_RE.findall(text)))
        if not distinct:
            continue
        kategorii += 1
        for cat_id_str, fname in distinct:
            cat_id = int(cat_id_str)
            fp = f"content-files/kategorie-popisy/{cat_id}/{fname}"
            out.append((fp, cat_id))
    return out, kategorii


def existing_on_disk(fp):
    return os.path.exists(os.path.join(WEBAPP, fp))


def get_or_create_photo(cur, file_path, defaults):
    cur.execute("SELECT id FROM content_photo_library WHERE file_path=%s", (file_path,))
    row = cur.fetchone()
    if row:
        return row["id"], False
    cols = ["file_path"] + list(defaults.keys())
    vals = [file_path] + list(defaults.values())
    placeholders = ", ".join(["%s"] * len(vals))
    cur.execute(f"INSERT INTO content_photo_library ({', '.join(cols)}) VALUES ({placeholders})", vals)
    return cur.lastrowid, True


def manifest_count(cur, file_paths):
    file_paths = sorted(set(file_paths))
    if not file_paths:
        return 0, []
    placeholders = ",".join(["%s"] * len(file_paths))
    cur.execute(f"SELECT rel_path FROM image_watermark_manifest WHERE rel_path IN ({placeholders})", file_paths)
    found = [r["rel_path"] for r in cur.fetchall()]
    return len(found), found


def main():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # --- Fáze A: jen CTENI, spocitat kandidatni cesty + manifest PRED ---
            sgi_candidates = candidate_paths_shop_gallery_images(cur)
            cgi_candidates = candidate_paths_content_gallery_items(cur)
            kp_candidates, kp_kategorii = candidate_paths_kategorie_popisy(cur)

            all_candidate_paths = (
                [fp for fp, _ in sgi_candidates]
                + [fp for fp, _ in cgi_candidates]
                + [fp for fp, _ in kp_candidates]
            )
            manifest_before_count, manifest_before_set = manifest_count(cur, all_candidate_paths)

            cur.execute("SELECT COUNT(*) c FROM content_photo_library")
            lib_before = cur.fetchone()["c"]

            # --- Fáze B: skutecny zapis (jen content_photo_library[_categories]) ---
            stats = {"shop_gallery_images": {"zdroj_radku": len(sgi_candidates), "novych": 0, "preskoceno_chybejici_soubor": 0},
                      "content_gallery_items": {"zdroj_radku": len(cgi_candidates), "novych": 0, "prirazeni_kategorii": 0, "preskoceno_chybejici_soubor": 0},
                      "kategorie_popisy": {"kategorii_s_odkazem": kp_kategorii, "novych": 0, "prirazeni_kategorii": 0, "preskoceno_chybejici_soubor": 0}}

            for fp, r in sgi_candidates:
                if not existing_on_disk(fp):
                    print(f"  [shop_gallery_images] PRESKOCENO (soubor chybi na disku): {fp}")
                    stats["shop_gallery_images"]["preskoceno_chybejici_soubor"] += 1
                    continue
                _id, was_new = get_or_create_photo(cur, fp, {
                    "title": r["title"], "alt_text": r["alt_text"],
                    "is_public": int(bool(r["active"])), "realizace_tag": r["category"],
                    "legacy_source": "shop_gallery_images", "legacy_id": r["id"], "sort_order": r["sort_order"],
                })
                stats["shop_gallery_images"]["novych"] += 1 if was_new else 0

            for fp, r in cgi_candidates:
                if not existing_on_disk(fp):
                    print(f"  [content_gallery_items] PRESKOCENO (soubor chybi na disku): {fp}")
                    stats["content_gallery_items"]["preskoceno_chybejici_soubor"] += 1
                    continue
                photo_id, was_new = get_or_create_photo(cur, fp, {
                    "caption": r["caption"], "is_public": int(bool(r["is_public"])),
                    "legacy_source": "content_gallery_items", "legacy_id": r["id"], "sort_order": r["sort_order"],
                })
                stats["content_gallery_items"]["novych"] += 1 if was_new else 0
                cur.execute(
                    "INSERT IGNORE INTO content_photo_library_categories (photo_id, category_id, sort_order) "
                    "VALUES (%s, %s, %s)", (photo_id, r["owner_id"], r["sort_order"]),
                )
                stats["content_gallery_items"]["prirazeni_kategorii"] += 1

            for fp, cat_id in kp_candidates:
                if not existing_on_disk(fp):
                    print(f"  [kategorie-popisy] PRESKOCENO (soubor chybi na disku): {fp}")
                    stats["kategorie_popisy"]["preskoceno_chybejici_soubor"] += 1
                    continue
                photo_id, was_new = get_or_create_photo(cur, fp, {
                    "is_public": 1, "legacy_source": "kategorie_popisy", "legacy_id": None, "sort_order": 0,
                })
                stats["kategorie_popisy"]["novych"] += 1 if was_new else 0
                cur.execute(
                    "INSERT IGNORE INTO content_photo_library_categories (photo_id, category_id, sort_order) "
                    "VALUES (%s, %s, 0)", (photo_id, cat_id),
                )
                stats["kategorie_popisy"]["prirazeni_kategorii"] += 1

            cur.execute("SELECT COUNT(*) c FROM content_photo_library")
            lib_after = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM content_photo_library_categories")
            links_after = cur.fetchone()["c"]

            # --- Fáze C: manifest PO zapisu, na STEJNE mnozine cest ---
            manifest_after_count, manifest_after_set = manifest_count(cur, all_candidate_paths)

        conn.commit()
    finally:
        conn.close()

    print("\n=== VYSLEDKY PO ZDROJI ===")
    print(json.dumps(stats, indent=1, ensure_ascii=False))

    print("\n=== SOUHRN ===")
    print(f"content_photo_library: pred={lib_before}, po={lib_after} (pribylo {lib_after - lib_before})")
    print(f"content_photo_library_categories (celkem prirazeni): {links_after}")
    print(f"Kandidatnich cest celkem (vc. preskocenych): {len(all_candidate_paths)}, distinct: {len(set(all_candidate_paths))}")
    print(f"\nimage_watermark_manifest - shoda pro tutez mnozinu cest PRED zapisem: {manifest_before_count}")
    print(f"image_watermark_manifest - shoda pro tutez mnozinu cest PO zapisu:   {manifest_after_count}")
    print("MANIFEST BEZE ZMENY:" , "ANO" if manifest_before_count == manifest_after_count and manifest_before_set == manifest_after_set else "NE - ROZDIL, PROVERIT!")


if __name__ == "__main__":
    main()
