#!/usr/bin/env python3
"""JEDNORAZOVA oprava: karta 3943 (Doblo K-075) ma sdileny CANONICAL_DIR
slot pro VSECH 7 navazanych sestav (341-347), ale kazda commituje svou
otocku nezavisle - `_write_canonical()` pise vzdy na STEJNE nazvy souboru
(podle SLUGU produktu, ne podle assembly), takze posledni commitnuta
sestava (346, 2026-09-13 00:26) prepsala hero/side/top obrazky patrici
is_master sestave (344, commitnuta driv, 2026-09-12 23:40). Totez
`content_gallery_items.id=238` (vlastnena turntablem, `gallery_item_id`
v canonical.json davky 344).

Nahlaseno bot5 (2026-09-13), nezavisle overeno primo v DB (mtime souboru
`turntable/<slug>/*.jpg` = 2026-09-13 00:26:3x, presne cas commitu 346,
NE 344).

Tenhle skript NEMENI zadny kod (regenerate_canonical/commit_batch), jen
jednorazove prepise sdileny slot zpatky na obsah aktualne oznaceneho
is_master (344), stejnym zpusobem, jakym by to udelal spravne
assembly_id-scoped regenerate_canonical (ktery zatim neexistuje - viz
navrh opravy v AGENTS_LOG.md/zprava bot5).

Spustit: api/venv/bin/python3 scripts/tmp_2026-09-13_bot8_fix_canonical_3943_344.py
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402
import turntable as tt  # noqa: E402

SHOP_PRODUCT_ID = 3943
ASSEMBLY_ID = 344
BATCH = "20260912234050-cec1f6280e94"

conn = app.get_conn()
try:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT batch, elevation_deg, azimuth_deg, tier_px, filename, bytes, created_at "
            "FROM product_turntable_frames WHERE shop_product_id=%s AND assembly_id=%s AND batch=%s AND is_active=1",
            (SHOP_PRODUCT_ID, ASSEMBLY_ID, BATCH),
        )
        frames = cur.fetchall()
        assert len(frames) == 54, f"cekano 54 snimku, nalezeno {len(frames)} - STOP"
        slug, product_name = tt._product_slug(cur, SHOP_PRODUCT_ID)
        cur.execute("SELECT name FROM product_assemblies WHERE id=%s", (ASSEMBLY_ID,))
        assembly_name = cur.fetchone()["name"]
finally:
    conn.close()

print(f"slug={slug!r} assembly_name={assembly_name!r} snimku={len(frames)}")

prev_meta = tt._read_batch_json(SHOP_PRODUCT_ID, BATCH, "canonical.json") or {}
front = prev_meta.get("front_azimuth_deg", tt.FRONT_AZIMUTH_DEG)
print("prev_meta (vlastni canonical.json davky 344):", prev_meta)

# 1) prepsat SDILENE kanonicke soubory (CANONICAL_DIR/<slug>/...) obsahem z 344
files = tt._write_canonical(SHOP_PRODUCT_ID, BATCH, frames, slug, marks=prev_meta, front=front)
print("\nZapsano kanonickych souboru:", len(files))
for k, v in files.items():
    print(" ", k, "->", v)

# 2) galerie + thumbnail - stejna funkce jako komitovana cesta, jen mimo staged rezim
conn = app.get_conn()
disk = {"written": [], "remove_after_commit": []}
try:
    with conn.cursor() as cur:
        hero_rel = files.get("hero")
        gallery_added, thumbnail_set, marks, disk = tt._fill_gallery_and_thumbnail(
            cur, SHOP_PRODUCT_ID, assembly_name, slug, hero_rel, prev_meta, disk=disk,
        )
    conn.commit()
    print(f"\ngallery_added={gallery_added} thumbnail_set={thumbnail_set} marks={marks}")
except Exception:
    conn.rollback()
    for p in disk["written"]:
        try:
            os.remove(p)
        except OSError:
            pass
    raise
finally:
    conn.close()

for p in disk["remove_after_commit"]:
    try:
        os.remove(p)
        print("smazan stary soubor galerie:", p)
    except OSError as e:
        print("nepodarilo se smazat", p, e)

# 3) cerstve overeni primo z DB + z disku
conn = app.get_conn()
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, caption FROM content_gallery_items WHERE id=%s", (marks.get("gallery_item_id"),))
        print("\nOVERENO content_gallery_items:", cur.fetchone())
        cur.execute("SELECT thumbnail_file FROM shop_products WHERE id=%s", (SHOP_PRODUCT_ID,))
        print("OVERENO shop_products.thumbnail_file:", cur.fetchone())
finally:
    conn.close()

hero_abs = os.path.join(tt.UPLOAD_DIR, files["hero"])
print("\nOVERENO mtime hero souboru:", os.path.getmtime(hero_abs))
import time
print("aktualni cas:", time.time(), " (mel by byt cerstvy, ne 2026-09-13 00:26)")
