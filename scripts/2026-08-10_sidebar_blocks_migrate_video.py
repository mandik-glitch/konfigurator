"""
Vytvori prvni radek v nove tabulce sidebar_blocks ("Vestavby do aut na
míru") a presune video/poster z docasneho umisteni
(webapp/content-files/videos/, zavedeno drive v teto session pred
rozhodnutim udelat radnou admin sekci) do konvence
SIDEBAR_BLOCK_IMAGE_DIR/SIDEBAR_BLOCK_VIDEO_DIR pouzivane admin CRUD
endpointy (api/app.py).

Idempotentni: pokud radek se stejnym slug uz existuje, skript ho
NEDUPLIKUJE (jen vypise a skonci).
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

SRC_VIDEO = "/opt/konfigurator/webapp/content-files/videos/vestavby-do-aut-na-miru.mp4"
SRC_POSTER = "/opt/konfigurator/webapp/content-files/videos/vestavby-do-aut-na-miru-poster.jpg"
IMAGE_DIR = "/opt/konfigurator/webapp/content-files/sidebar-blocks"
VIDEO_DIR = "/opt/konfigurator/webapp/content-files/sidebar-blocks-video"

TITLE = "Vestavby do aut na míru"
SLUG = "vestavby-do-aut-na-miru"
META_DESCRIPTION = "Ukázka stavebnicové vestavby do užitkového vozidla z hliníkových profilů Logiman – zásuvky, úchyty a uspořádání na míru."
BODY_HTML = (
    "<p>Krátká ukázka, jak vypadá hotová stavebnicová vestavba do užitkového vozidla "
    "postavená z hliníkových profilů Logiman – zásuvkové systémy, úchyty a uspořádání "
    "podle konkrétních potřeb řemeslníka.</p>"
)


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    cur.execute("SELECT id FROM sidebar_blocks WHERE slug=%s", (SLUG,))
    existing = cur.fetchone()
    if existing:
        print(f"Radek uz existuje (id={existing['id']}), nic se nedeje.")
        return

    print(f"Vytvorim novy radek: title={TITLE!r} slug={SLUG!r}")
    if dry_run:
        print("DRY RUN - nic nezapsano. Spust s --apply pro skutecne provedeni.")
        return

    cur.execute(
        "INSERT INTO sidebar_blocks (title, slug, meta_description, body_html, sort_order, is_visible) "
        "VALUES (%s,%s,%s,%s,1,1)",
        (TITLE, SLUG, META_DESCRIPTION, BODY_HTML),
    )
    block_id = cur.lastrowid

    image_stored = f"{block_id}_{os.urandom(6).hex()}.jpg"
    video_stored = f"{block_id}_{os.urandom(6).hex()}.mp4"
    shutil.copyfile(SRC_POSTER, os.path.join(IMAGE_DIR, image_stored))
    shutil.copyfile(SRC_VIDEO, os.path.join(VIDEO_DIR, video_stored))
    os.chown(os.path.join(IMAGE_DIR, image_stored), 33, 33)
    os.chown(os.path.join(VIDEO_DIR, video_stored), 33, 33)

    cur.execute(
        "UPDATE sidebar_blocks SET image_filename=%s, video_filename=%s WHERE id=%s",
        (image_stored, video_stored, block_id),
    )
    conn.commit()
    print(f"Hotovo: id={block_id}, image={image_stored}, video={video_stored}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
