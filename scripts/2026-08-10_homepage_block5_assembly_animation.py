"""
Nahrazeni statickeho obrazku dlazdice #5 ("Poskladejte si Vas produkt ve
3D z aluprofilu") animovanym GIFem, ktery skutecne ukazuje sestavovani
konstrukce z realnych katalogovych 3D dilu (Robert 2026-08-10: "chci tam
neco co prichoziho uchvati, akcni dlazdice, musi kratke animaci najit
pointu co to umi").

Animace: ctvercovy ram 1000x1000mm ze 4 profilu 30x30
(webapp/katalog/profil_30x30_uzavreny.glb) + 4 rohove kostky
(webapp/katalog/product_3345.glb) - REALNA katalogova geometrie
projektu, zadny vymysleny tvar. Dily postupne "priletaji" a zapadnou na
misto, kamera pomalu obiha kolem hotoveho ramu. Vyrenderovano headless
Playwright + Three.js (stejna verze/loadery jako scene.html) - viz
/tmp scratchpad session teto prace pro puvodni build skripty
(assembly_anim2.html, capture_frames.js, make_gif.py) - nejsou soucasti
repa, protoze projekt zatim nema zadnou Node/Playwright zavislost;
pokud se podobne animace budou delat casteji, stoji za uvahu presunout
tenhle pipeline do scripts/ natrvalo.

Idempotentni v tom smyslu, ze jen prepisuje jeden konkretni radek (id=5)
znamym novym souborem - neni to obecny "doplnit chybejici" backfill
jako predchozi skripty, je to cilena vymena existujiciho obrazku.
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
GIF_SOURCE = "/tmp/claude-0/-opt-konfigurator/c6fb6b7b-721b-4097-8178-6c1def2f1db4/scratchpad/assembly.gif"

NEW_BODY_HTML = (
    "<h3>Poskládejte si vlastní konstrukci ve 3D</h3>"
    "<p>V našem 3D konfigurátoru si během pár minut poskládáte vlastní konstrukci "
    "z hliníkových stavebnicových profilů a příslušenství – přímo v prohlížeči, bez "
    "instalace. Vidíte rovnou 3D náhled i cenu materiálu a spojů.</p>"
    "<p><a href=\"/scene.html\">Otevřít 3D konfigurátor</a></p>"
)
NEW_META_DESCRIPTION = (
    "Sledujte, jak se konstrukce sama poskládá z hliníkových profilů, a postavte si "
    "tu svou ve 3D konfigurátoru Logiman – rovnou s cenou materiálu a spojů."
)


def main():
    dry_run = "--apply" not in sys.argv
    if not os.path.isfile(GIF_SOURCE):
        print(f"CHYBI zdrojovy GIF: {GIF_SOURCE}")
        sys.exit(1)

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id, title, image_filename, body_html, meta_description FROM homepage_blocks WHERE id=5")
    row = cur.fetchone()
    if not row:
        print("Dlaždice #5 nenalezena.")
        sys.exit(1)

    backup_path = "backups/homepage_block5_image_replace_backup_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(row, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha puvodniho stavu -> {backup_path}")

    if dry_run:
        print(f"DRY RUN - nahradil bych image_filename={row['image_filename']!r} novym GIFem "
              f"({os.path.getsize(GIF_SOURCE)} bytes), aktualizoval body_html/meta_description.")
        print("Spust s --apply pro skutecny zapis.")
        return

    old_name = row["image_filename"]
    stored_name = f"5_{os.urandom(6).hex()}.gif"
    shutil.copyfile(GIF_SOURCE, os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, stored_name))
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
            print(f"Smazan stary obrazek {old_path}")
        except OSError as e:
            print(f"Stary obrazek se nepodarilo smazat ({e}), ponechano.")
    print(f"Hotovo, novy soubor: {stored_name}")


if __name__ == "__main__":
    main()
