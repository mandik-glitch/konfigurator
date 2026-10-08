"""
Navrh textu (meta popisy + text kategorie) pro VSECHNY kategorie na
zivem logiman.cz, aby je Robert mohl rovnou zkopirovat/upravit primo
v administraci Shoptetu - Robert 2026-08-10: "podle textu napis novy
soubor, kde budou pro stavajici logiman.cz nejvhodnejsi texty pro
kategorie a metapopisy, tak aby vypadali maximalne lidske, ja je tam
podle toho doplnim a prepisu".

Zdroje podle priority (viz SEO_STANDARD_TEXTY_KATEGORII.md - "stavajici
texty na logiman.cz maji prednost pred vymyslenim od nuly", "stavajici
schvalene texty v nasi DB nemazat/neprepisovat, jen doplnovat"):
1. logiman_geo_obsah.docx - uz schvaleny GEO obsah, kde existuje (5 z
   112 kategorii na zivem webu nema zadny vlastni text a docx je pro
   ne pripraveny presne na miru).
2. Konfigurator (nase DB) - kde uz existuje text pro STEJNOU kategorii
   (102 kategorii, shoda overena normalizaci nazvu H1/name).
3. Nove napsano od nuly - jen 5 kategorii bez zdroje v obou predchozich
   (Kontrolní a kompletační stoly, Kuličkové ložiskové stoly, Rámy
   strojů a zařízení, Řezací stojany, Speciální hliníkové profily).

Vstupni data (stazeny+ocisteny obsah logiman.cz, otisk DB) jsou v /tmp
scratchpad teto session - tenhle skript jen nahrava uz HOTOVY vysledny
soubor (navrh_texty_logiman_cz_2026-08-10.md, sestaveny
build_navrh_texty.py ze stejne slozky) na Sdileny disk.
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
DISPLAY_FILENAME = "navrh_texty_logiman_cz_2026-08-10.md"
SOURCE_MD = "/tmp/claude-0/-opt-konfigurator/c6fb6b7b-721b-4097-8178-6c1def2f1db4/scratchpad/navrh_texty_logiman_cz_2026-08-10.md"


def main():
    dry_run = "--apply" not in sys.argv
    if not os.path.isfile(SOURCE_MD):
        print(f"CHYBI zdrojovy soubor: {SOURCE_MD} (spust nejdriv build_navrh_texty.py)")
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
    os.chown(dest, 33, 33)
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
