#!/opt/konfigurator/api/venv/bin/python
"""Karta "Vysuvny modul pro sverak vcetne sveraku York Lux 100" (bot5, 2026-10-07; Robert: "zalozit kartu 12400,- Kc bez DPH", obrazek = jeho fotka).
Nova NEAKTIVNI karta (pravidlo 54) v kategorii #292 "Vysuvy z dodavky na michu", cena 12 400 Kc bez DPH, 1 obrazek (fotka od Roberta) do galerie karty (content-files/gallery/products/<id>/1.<pripona>).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_bot5_karta_vysuvny_modul_sverak.py --foto /cesta/foto.png [--apply]"""
import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "api"))
from _env import get_conn  # noqa: E402
import product_slug  # noqa: E402

SKU = "LOG-VYSUV-SVERAK-YORK100"
NAZEV = "Výsuvný modul pro svěrák včetně svěráku York Lux 100"
KATEGORIE = 292                      # "Výsuvy z dodávky na míru"
CENA = 12400                         # Kč bez DPH (Robert)
POPIS = ("Výsuvný modul pro svěrák do vestavby dodávky, včetně svěráku York Lux 100. Svěrák se vysune z vestavby k práci a po použití zasune zpět.")
KRATKY = "Výsuvný modul pro svěrák včetně svěráku York Lux 100, cena bez DPH."
IMG_DIR = "/opt/konfigurator/webapp/content-files/gallery/products/{id}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.foto):
        sys.exit("foto neexistuje")
    ext = os.path.splitext(a.foto)[1].lower() or ".png"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM shop_products WHERE sku=%s", (SKU,))
        if cur.fetchone():
            sys.exit(f"ZASTAVENO: karta se SKU {SKU} uz existuje")
        cur.execute("SELECT id, name FROM content_categories WHERE id=%s", (KATEGORIE,))
        kat = cur.fetchone()
        if not kat:
            sys.exit("kategorie neexistuje")
        slug = product_slug.slug_for_name(cur, NAZEV)
        cur.execute("INSERT INTO shop_products (category_id, sku, name, slug, description, short_description, unit, active, is_archived, price_czk_placeholder, visible_in_scene) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'ks',0,0,%s,0)", (KATEGORIE, SKU, NAZEV, slug, POPIS, KRATKY, CENA))
        pid = cur.lastrowid
        d = IMG_DIR.format(id=pid)
        fn = f"1{ext}"
        print(f"karta #{pid} {NAZEV} | kategorie {KATEGORIE} {kat['name']} | {CENA} Kč bez DPH | slug {slug} | foto {d}/{fn}")
        if not a.apply:
            conn.rollback()
            print("(nahled, nic nezapsano; --apply)")
            return
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(a.foto, os.path.join(d, fn))
        cur.execute("INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) VALUES (%s,%s,NULL,0)", (pid, f"products/{pid}/{fn}"))
        cur.execute("INSERT INTO audit_log (user_id, action, entity_type, entity_id, detail) VALUES (NULL,'create','shop_product',%s,%s)", (pid, f"karta {SKU} (Robert 2026-10-07): {CENA} Kc bez DPH, neaktivni, kategorie {KATEGORIE}"))
        conn.commit()
        import grp
        import pwd
        uid, gid = pwd.getpwnam("www-data").pw_uid, grp.getgrnam("www-data").gr_gid
        os.chown(d, uid, gid)
        os.chown(os.path.join(d, fn), uid, gid)
        print(f"ZAPSANO: karta #{pid}; obrazek https://autovestavby.logiman.cz/content-files/gallery/products/{pid}/{fn}")
    except SystemExit:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
