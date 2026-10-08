#!/usr/bin/env python3
"""Jednotna dlazdice u NATIVNICH karet a u HOVER obrazku (bot4 2026-09-30, zed #20, Robert "PODRUHE": nahledy sestav
na kartach musi byt vsechny stejne velke a ve stejnem formatu).

Doplnek k 2026-09-24_vandr_hlavni_nahled_z_otocky.py (ten resi hlavni dlazdici VANDR karet a od 2026-09-30 vyrabi
jednotnou dlazdici sam). Tady se prepina to, co zbylo a co ten skript nedela:
  1) `--co tile`  - hlavni dlazdice NATIVNICH karet: prvni verejna polozka galerie zalozena turntablem (soubor
     `product-<id>_<slug>-zepredu-<hex>.jpg`, surovy 4:3 hero) se nahradi ctvercovou jednotnou dlazdici z
     cisteho ctvercoveho hero_1x1. Fotky realneho produktu (jine jmeno souboru) se NEDOTYKAJI (Robert: fotky
     maji prednost pred renderem, viz api/turntable.py::_fill_gallery_and_thumbnail).
  2) `--co hover` - hover obrazky (shop_product_images, sort_order=1, `vestavby-hover/product-<id>-hover.jpg`,
     kopie kanonickych snimku 1024x768 / 1024x1024) se prepisi na jednotnou dlazdici (novy soubor
     `vestavby-hover-t1024/product-<id>-hover.jpg` - NOVA slozka vlastnena www-data, stara `vestavby-hover/` je
     root-vlastnena po drivejsim skriptu a www-data do ni zapisovat nemuze), aby se po najeti mysi velikost
     sestavy nemenila.
Stare soubory ZUSTAVAJI na disku (jen radek v DB ukaze na novy); puvodni radky jsou v
backups/2026-09-30_dlazdice_pred_normalizaci.json. Idempotentni (hotova dlazdice = ctverec 1024 px a novy nazev).

Spusteni (MUSI jako www-data, pise do webapp/content-files/):
    systemd-run -p User=www-data -p Group=www-data --pipe --wait --quiet \\
      --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
      api/venv/bin/python3 scripts/2026-09-30_dlazdice_nativni_a_hover.py [--co tile|hover|vse] [--apply]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _env import get_conn  # noqa: E402
import _nahled_dlazdice as nd  # noqa: E402
import _thumbnail_normalizace as tn  # noqa: E402
from PIL import Image  # noqa: E402

CONTENT_FILES_ROOT = "/opt/konfigurator/webapp/content-files"
GALLERY_ITEMS_DIR = os.path.join(CONTENT_FILES_ROOT, "gallery-items")
HOVER_ROOT = os.path.join(CONTENT_FILES_ROOT, "gallery")
HOVER_NOVA_SLOZKA = "vestavby-hover-t%dv%d" % (nd.CIL, nd.VERZE)   # relativne k HOVER_ROOT (= hodnota v shop_product_images.filename)
ZALOHA = "/opt/konfigurator/backups/2026-09-30_dlazdice_pred_normalizaci.json"
VD_SKU_PREFIX = "VD-"


def _je_hotova(cesta):
    try:
        with Image.open(cesta) as im:
            return im.size == (nd.CIL, nd.CIL)
    except OSError:
        return False


def _puvodni_hover_z_zalohy():
    """{product_id: puvodni relativni nazev hover souboru} ze zalohy pred prvnim prepnutim - zdroj pro PREGENEROVANI
    (vlastni dlazdice se nenormalizuje podruhe, vzdy se jde od puvodniho snimku)."""
    import json
    try:
        with open(ZALOHA, encoding="utf-8") as fh:
            z = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {r["product_id"]: r["filename"] for r in z.get("shop_product_images", [])
            if r.get("sort_order") == 1 and str(r.get("filename", "")).startswith("vestavby-hover/")}


def tile_nativni(cur, apply, znovu=False):
    cur.execute(
        "SELECT sp.id, sp.sku, sp.slug FROM shop_products sp WHERE sp.active=1 AND sp.sku NOT LIKE %s "
        "AND EXISTS (SELECT 1 FROM product_turntable_frames f WHERE f.shop_product_id=sp.id AND f.is_active=1) ORDER BY sp.id",
        (VD_SKU_PREFIX + "%",))
    zmeneno = preskoceno = 0
    for k in cur.fetchall():
        prefix = "product-%d_%s-zepredu-" % (k["id"], k["slug"])
        cur.execute(
            "SELECT id, filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s AND is_public=1 "
            "AND filename LIKE %s ORDER BY sort_order, id LIMIT 1", (k["id"], prefix.replace("_", "\\_") + "%"))
        radek = cur.fetchone()
        if not radek:
            print("  [%s] preskoceno: galerie nema polozku zalozenou turntablem (fotky realneho produktu se nemeni)" % k["id"])
            preskoceno += 1
            continue
        stary = os.path.join(GALLERY_ITEMS_DIR, os.path.basename(radek["filename"]))
        hotova = _je_hotova(stary)
        if hotova and not znovu:
            preskoceno += 1
            continue
        zdroj, ctverec = tn.najdi_cisty_zdroj(cur, k["id"], stary)
        if hotova and not ctverec:
            print("  [%s] preskoceno: chybi cisty hero_1x1 a soucasna dlazdice uz je normalizovana (nenormalizuje se podruhe)" % k["id"])
            preskoceno += 1
            continue
        novy_nazev = "%s%s.jpg" % (prefix, os.urandom(4).hex())
        print("  [%s] %s -> %s  (zdroj %s)" % (k["id"], radek["filename"], novy_nazev, os.path.relpath(zdroj, CONTENT_FILES_ROOT)))
        if apply:
            nd.uloz_dlazdici(zdroj, os.path.join(GALLERY_ITEMS_DIR, novy_nazev))
            cur.execute("UPDATE content_gallery_items SET filename=%s WHERE id=%s", (novy_nazev, radek["id"]))
            if hotova and os.path.isfile(stary):
                os.remove(stary)         # predchozi VLASTNI dlazdice (odvozena, reprodukovatelna); puvodni surovy hero zustava
        zmeneno += 1
    return zmeneno, preskoceno


def hover(cur, apply):
    puvodni = _puvodni_hover_z_zalohy()
    cur.execute("SELECT id, product_id, filename FROM shop_product_images WHERE sort_order=1 "
                "AND (filename LIKE 'vestavby-hover/%' OR filename LIKE 'vestavby-hover-t%') ORDER BY product_id")
    zmeneno = preskoceno = chyby = 0
    for r in cur.fetchall():
        if r["filename"].startswith(HOVER_NOVA_SLOZKA + "/"):
            preskoceno += 1
            continue
        odvozena = r["filename"].startswith("vestavby-hover-t")          # starsi verze dlazdice -> jit od puvodniho snimku
        zdroj_rel = puvodni.get(r["product_id"]) if odvozena else r["filename"]
        if not zdroj_rel:
            print("  [%s] CHYBA: puvodni hover snimek neni v zaloze (%s)" % (r["product_id"], ZALOHA))
            chyby += 1
            continue
        zdroj = os.path.join(HOVER_ROOT, zdroj_rel)
        if not os.path.isfile(zdroj):
            print("  [%s] CHYBA: soubor chybi na disku: %s" % (r["product_id"], zdroj))
            chyby += 1
            continue
        novy = "%s/product-%d-hover.jpg" % (HOVER_NOVA_SLOZKA, r["product_id"])
        print("  [%s] %s -> %s  (zdroj %s)" % (r["product_id"], r["filename"], novy, zdroj_rel))
        if apply:
            os.makedirs(os.path.join(HOVER_ROOT, HOVER_NOVA_SLOZKA), exist_ok=True)
            nd.uloz_dlazdici(zdroj, os.path.join(HOVER_ROOT, novy))
            cur.execute("UPDATE shop_product_images SET filename=%s WHERE id=%s", (novy, r["id"]))
            if odvozena:
                predchozi = os.path.join(HOVER_ROOT, r["filename"])
                if os.path.isfile(predchozi):
                    os.remove(predchozi)    # predchozi VLASTNI dlazdice (odvozena); puvodni root-vlastneny snimek zustava
        zmeneno += 1
    return zmeneno, preskoceno, chyby


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--co", choices=["tile", "hover", "vse"], default="vse")
    ap.add_argument("--apply", action="store_true", help="bez toho jen nahled (dry-run)")
    ap.add_argument("--znovu", action="store_true",
                    help="nativni dlazdice: vyrobit znovu i kdyz uz jsou ctverec (po zmene algoritmu, nd.VERZE)")
    a = ap.parse_args()
    print("=== jednotna dlazdice: nativni karty + hover - %s ===" % ("APPLY" if a.apply else "DRY-RUN"))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if a.co in ("tile", "vse"):
                z, p = tile_nativni(cur, a.apply, znovu=a.znovu)
                print("nativni dlazdice: %d %s, %d preskoceno" % (z, "zmeneno" if a.apply else "by se zmenilo", p))
                if a.apply:
                    conn.commit()        # kazda cast zvlast: selhani hoveru nezahodi uz hotove dlazdice
            if a.co in ("hover", "vse"):
                z, p, ch = hover(cur, a.apply)
                print("hover: %d %s, %d uz hotovo, %d chyb" % (z, "zmeneno" if a.apply else "by se zmenilo", p, ch))
                if a.apply:
                    conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
