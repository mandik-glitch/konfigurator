"""
Nahrani SEO_KONKURENCE_NASTENKA.md (existujici soubor v repu, prehled
konkurence) na Sdileny disk, slozka "SEO GEO" (id 47), vedle otisku
nasi DB a otisku logiman.cz - Robert 2026-08-10: "a ti konkurenti dej
to tam taky at to mam".
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
DISPLAY_FILENAME = "SEO_KONKURENCE_NASTENKA.md"
SOURCE_MD = "/opt/konfigurator/SEO_KONKURENCE_NASTENKA.md"


def main():
    dry_run = "--apply" not in sys.argv
    with open(SOURCE_MD, encoding="utf-8") as f:
        content = f.read()
    print(f"Zdroj: {SOURCE_MD} ({len(content)} znaků)")

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
