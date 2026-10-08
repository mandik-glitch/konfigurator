"""
Robert po animovanem GIFu (predchozi pokus, viz
scripts/2026-08-10_homepage_block5_assembly_animation.py): "dobra,
snaha byla, ale je to bida. video rusim to si udelam sam, dej do
dlazdice nekolik screenshotu z cele 3D sceny, vloz si tam sestavu
Dvojstul".

Nahrazuje animaci statickym 2x2 kolazem 4 screenshotu SKUTECNE
konstrukce "Dvojstul Tchibo" (shop_products.id 3672,
webapp/katalog/product_3672.glb - realny, uz drive existujici model v
katalogu, ne vymyslena geometrie) z ruznych uhlu (izometricky hero
pohled, celni, bocni, horni 3/4), vyrenderovanych stejnym headless
Playwright+Three.js pipeline jako predchozi pokus (viz tamten skript
pro poznamky k infrastrukture), tentokrat bez animace - jen kvalitni
staticke snimky s jemnym stinem pod modelem.

Idempotentni v tom smyslu, ze jen prepisuje jeden konkretni radek (id=5)
znamym novym souborem - cilena vymena, ne obecny backfill.
"""
import json
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

HOMEPAGE_BLOCK_IMAGE_DIR = "/opt/konfigurator/webapp/content-files/homepage-blocks"
COLLAGE_SOURCE = "/tmp/claude-0/-opt-konfigurator/c6fb6b7b-721b-4097-8178-6c1def2f1db4/scratchpad/dvojstul_collage.jpg"

NEW_BODY_HTML = (
    "<h3>Poskládejte si vlastní konstrukci ve 3D</h3>"
    "<p>Ukázka reálné konstrukce postavené v našem 3D konfigurátoru z hliníkových "
    "stavebnicových profilů a příslušenství – dvoupatrová pracovní sestava "
    "\"Dvojstůl\" ze čtyř úhlů. Stejně tak si přímo v prohlížeči, bez instalace, "
    "poskládáte konstrukci vlastní a rovnou vidíte 3D náhled i cenu materiálu a spojů.</p>"
    "<p><a href=\"/scene.html\">Otevřít 3D konfigurátor</a></p>"
)
NEW_META_DESCRIPTION = (
    "Ukázka reálné konstrukce (\"Dvojstůl\") postavené z hliníkových profilů v 3D "
    "konfigurátoru Logiman – poskládejte si tu svou přímo v prohlížeči, s cenou materiálu na místě."
)


def main():
    dry_run = "--apply" not in sys.argv
    if not os.path.isfile(COLLAGE_SOURCE):
        print(f"CHYBI zdrojovy kolaz: {COLLAGE_SOURCE}")
        sys.exit(1)

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id, title, image_filename, body_html, meta_description FROM homepage_blocks WHERE id=5")
    row = cur.fetchone()
    if not row:
        print("Dlaždice #5 nenalezena.")
        sys.exit(1)

    backup_path = "backups/homepage_block5_collage_replace_backup_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha puvodniho stavu -> {backup_path}")

    if dry_run:
        print(f"DRY RUN - nahradil bych image_filename={row['image_filename']!r} kolazem "
              f"({os.path.getsize(COLLAGE_SOURCE)} bytes), aktualizoval body_html/meta_description.")
        print("Spust s --apply pro skutecny zapis.")
        return

    old_name = row["image_filename"]
    stored_name = f"5_{os.urandom(6).hex()}.jpg"
    shutil.copyfile(COLLAGE_SOURCE, os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, stored_name))
    cur.execute(
        "UPDATE homepage_blocks SET image_filename=%s, body_html=%s, meta_description=%s WHERE id=5",
        (stored_name, NEW_BODY_HTML, NEW_META_DESCRIPTION),
    )
    conn.commit()
    cur.close()
    conn.close()

    if old_name:
        old_path = os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, old_name)
        try:
            os.remove(old_path)
            print(f"Smazan stary soubor {old_path}")
        except OSError as e:
            print(f"Stary soubor se nepodarilo smazat ({e}), ponechano.")
    print(f"Hotovo, novy soubor: {stored_name}")


if __name__ == "__main__":
    main()
