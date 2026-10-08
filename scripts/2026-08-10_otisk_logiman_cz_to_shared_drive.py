"""
Otisk (snapshot) textu a meta popisu kategorii ZIVEHO webu logiman.cz
(Shoptet, PRED migraci na konfigurator) - Robert 2026-08-10: "projdi
jeste kategorie logiman.cz pripis to jako dalsi soubor (meta popisy
kategorii podkategorii a text kategorii stejne jako ostatni)".

Navazuje na scripts/2026-08-10_otisk_kategorii_to_shared_drive.py
(otisk NASI DB) - tenhle skript misto DB stahuje verejne HTML stranky
www.logiman.cz (title/meta description/H1/text mezi H1 a vypisem
produktu, ocistene o Shoptet radici listu a paticku/cookie banner) a
uklada stejnym zpusobem na Sdileny disk, slozka "SEO GEO" (id 47).

Zdrojova data (JSON po stazeni + cisteni) jsou v /tmp scratchpad teto
session, ne v repu - tenhle skript ocekava, ze uz existuji (spustit
napřed crawl_logiman.py + build_logiman_md.py ze stejne slozky, pripadne
prepsat na primy crawl, pokud se bude spoustet znovu za delsi dobu).
"""
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
SEO_GEO_FOLDER_ID = 47
DISPLAY_FILENAME = "otisk_logiman_cz_2026-08-10.md"
SOURCE_MD = "/tmp/claude-0/-opt-konfigurator/c6fb6b7b-721b-4097-8178-6c1def2f1db4/scratchpad/otisk_logiman_cz_2026-08-10.md"


def main():
    dry_run = "--apply" not in sys.argv
    if not os.path.isfile(SOURCE_MD):
        print(f"CHYBI zdrojovy soubor: {SOURCE_MD} (spust nejdriv crawl_logiman.py + build_logiman_md.py)")
        sys.exit(1)
    with open(SOURCE_MD, encoding="utf-8") as f:
        content = f.read()

    local_out = f"backups/{DISPLAY_FILENAME}"
    with open(local_out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Lokální kopie -> {local_out} ({len(content)} znaků)")

    if dry_run:
        print("DRY RUN - na Sdílený disk (SEO GEO) nic nenahráno. Spusť s --apply.")
        return

    os.makedirs(DRIVE_FILES_DIR, exist_ok=True)
    token = os.urandom(16).hex()
    stored_filename = f"{token}.md"
    dest = os.path.join(DRIVE_FILES_DIR, stored_filename)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    os.chown(dest, 33, 33)  # www-data:www-data
    size_bytes = os.path.getsize(dest)

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO shared_drive_files (folder_id, filename, stored_filename, content_type, size_bytes, uploaded_by) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (SEO_GEO_FOLDER_ID, DISPLAY_FILENAME, stored_filename, "text/markdown", size_bytes, None),
    )
    conn.commit()
    file_id = cur.lastrowid
    cur.close()
    conn.close()
    print(f"Nahráno na Sdílený disk (složka SEO GEO, id={SEO_GEO_FOLDER_ID}) jako soubor #{file_id}, {size_bytes} bytes.")


if __name__ == "__main__":
    main()
