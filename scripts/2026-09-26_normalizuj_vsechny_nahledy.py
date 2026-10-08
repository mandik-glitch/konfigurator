#!/usr/bin/env python3
"""2026-09-26_normalizuj_vsechny_nahledy.py - jednorazovy davkovy prubeh
pres VSECHNY existujici webapp/katalog/thumbnails/product-*.jpg (bot4,
Robert: "vsechny rendery musi mit stejny kabat").

Pouziva scripts/_thumbnail_normalizace.py (stejny modul, ktery `api/
turntable.py` pouziva i pro NOVE karty, viz tamni patch) - jeden zdroj
pravdy pro algoritmus, zadna druha kopie k rucni synchronizaci.

Spustit na serveru JAKO www-data (pravidlo: skripty co pisi do webapp/
obsahu vzdy pres systemd-run, viz feedback_root_owned_content_files):
    sudo systemd-run --uid=www-data --gid=www-data --wait --pipe --collect \\
      --working-directory=/opt/konfigurator \\
      --property=EnvironmentFile=/opt/konfigurator/api/.env \\
      api/venv/bin/python3 scripts/2026-09-26_normalizuj_vsechny_nahledy.py [--dry-run]
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _thumbnail_normalizace as tn  # noqa: E402

import pymysql  # noqa: E402


def _env():
    env = {}
    for line in open(os.path.join(tn.REPO, "api", ".env")):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k] = v
    return env


def _conn():
    e = _env()
    return pymysql.connect(
        host=e["DB_HOST"], port=int(e["DB_PORT"]), user=e["DB_USER"],
        password=e["DB_PASSWORD"], database=e["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def _assembly_typu_ids(cur):
    """Jen 'sestavove' produkty (nativni regaly + Vandr karty) - u
    JEDNOTLIVYCH katalogovych dilu (spojka, zaslepka, lista na metry...)
    je vyplneni ramu blizko 100 % SPRAVNE (bezny produktovy detail-zaber,
    zadna otacecí kamera na nejhorsi uhel se tam vubec neresi) a
    normalizace by je jen zbytecne oddalila od kamery. Zjisteno 2026-09-26
    - prvni bezny mereni na CELY katalog ukazalo 156/216 u hrany, ale
    vzorek (3045 uhelnikova spojka, 3070/3071 zaslepky, 3171/3184 U
    listy, 3209 tesnici paska) jsou vsechno jednotlive dily, ne sestavy."""
    cur.execute(
        "SELECT sp.id FROM shop_products sp WHERE sp.sku LIKE 'VD-%' "
        "OR EXISTS (SELECT 1 FROM product_assemblies pa WHERE pa.shop_product_id=sp.id)"
    )
    return {r["id"] for r in cur.fetchall()}


def main():
    dry_run = "--dry-run" in sys.argv
    soubory = sorted(glob.glob(os.path.join(tn.KATALOG_THUMBNAIL_DIR, "product-*.jpg")))
    conn = _conn()
    hotovo = 0
    chyby = 0
    preskoceno_nesestava = 0
    zdroj_hero1x1 = 0
    zdroj_primy = 0
    try:
        with conn.cursor() as cur:
            assembly_ids = _assembly_typu_ids(cur)
            print("Nalezeno %d nahledu celkem, z toho sestavovych (cil normalizace): bude videt niz."
                  % len(soubory))
            for cesta in soubory:
                jmeno = os.path.basename(cesta)
                try:
                    shop_product_id = int(jmeno[len("product-"):-len(".jpg")])
                except ValueError:
                    print("  ! preskakuji, nejde rozparsovat ID:", jmeno)
                    continue
                if shop_product_id not in assembly_ids:
                    preskoceno_nesestava += 1
                    continue
                try:
                    zdroj, je_cisty = tn.najdi_cisty_zdroj(cur, shop_product_id, cesta)
                    if je_cisty:
                        zdroj_hero1x1 += 1
                    else:
                        zdroj_primy += 1
                    out_img = tn.normalizuj(zdroj)
                    if dry_run:
                        print("  by se prepsalo:", jmeno, "(zdroj:", os.path.basename(zdroj), ")")
                    else:
                        tmp = cesta + ".tmp"
                        out_img.save(tmp, "JPEG", quality=92, optimize=True)
                        os.replace(tmp, cesta)
                    hotovo += 1
                except Exception as e:
                    chyby += 1
                    print("  ! CHYBA u", jmeno, ":", repr(e))
    finally:
        conn.close()

    print("\nHOTOVO: %d zpracovano (%d z cisteho hero_1x1, %d primo z thumbnail), "
          "%d preskoceno (nejsou sestava - jednotlivy dil), %d chyb, rezim=%s"
          % (hotovo, zdroj_hero1x1, zdroj_primy, preskoceno_nesestava, chyby,
             "DRY-RUN" if dry_run else "ZAPSANO"))
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main())
