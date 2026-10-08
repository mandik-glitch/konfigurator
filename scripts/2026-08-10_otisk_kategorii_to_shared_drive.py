"""
Otisk (snapshot) aktualnich textu a meta popisu vsech kategorii/
podkategorii (content_categories + content_pages), ulozeny na Sdileny
disk (slozka "SEO GEO", id=47) - Robert 2026-08-10 ("udelej do nejakeho
souboru otisk nasich textu a meta popisu kategorii a podkategorii, ten
ulozi na sdileny disk").

Sdileny disk = interni feature app (api/drive.py, tabulky
shared_drive_folders/shared_drive_files), NE Google Drive - soubory
fyzicky v private-files/shared-drive/, DB radek s nahodnym
stored_filename (stejna konvence jako ostatni privatni uploady, viz
quotes.safe_stored_filename).
"""
import json
import os
import re
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
DISPLAY_FILENAME = "otisk_kategorie_2026-08-10.md"


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_snapshot(cur):
    cur.execute("""
        SELECT c.id, c.parent_id, c.name, c.slug, c.is_visible, c.meta_title, c.meta_description, c.focus_keyword,
               p.intro_html, p.body_html, p.bottom_body_html
        FROM content_categories c
        LEFT JOIN content_pages p ON p.category_id = c.id
        ORDER BY c.parent_id IS NULL DESC, c.parent_id, c.sort_order, c.name
    """)
    rows = cur.fetchall()
    children = {}
    for r in rows:
        children.setdefault(r["parent_id"], []).append(r)

    lines = [
        "# Otisk textů a meta popisů kategorií a podkategorií — Logiman / Konfigurátor",
        "",
        "Vygenerováno automaticky z produkční DB (`content_categories` + `content_pages`), 2026-08-10.",
        f"Celkem kategorií: {len(rows)}.",
        "", "---", "",
    ]

    def render(cat, depth):
        indent = "#" * min(depth + 2, 6)
        vis = "" if cat["is_visible"] else " _(skrytá)_"
        lines.append(f"{indent} {cat['name']}{vis}")
        lines.append(f"- **ID:** {cat['id']}  **Slug:** `/kategorie/{cat['slug']}`")
        lines.append(f"- **Meta title:** {cat['meta_title'] or '_(chybí)_'}")
        lines.append(f"- **Meta description:** {cat['meta_description'] or '_(chybí)_'}")
        lines.append(f"- **Focus keyword:** {cat['focus_keyword'] or '_(chybí)_'}")
        intro = strip_html(cat["intro_html"])
        body = strip_html(cat["body_html"])
        bottom = strip_html(cat["bottom_body_html"])
        if intro:
            lines.append(f"- **Intro text:** {intro}")
        if body:
            lines.append(f"- **Obsah stránky (body):** {body}")
        if bottom:
            lines.append(f"- **Spodní obsah / FAQ:** {bottom}")
        lines.append("")
        for ch in sorted(children.get(cat["id"], []), key=lambda x: x["name"]):
            render(ch, depth + 1)

    for root in sorted(children.get(None, []), key=lambda x: x["name"]):
        render(root, 0)
        lines.append("---")
        lines.append("")

    return "\n".join(lines), len(rows)


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    content, n_cats = build_snapshot(cur)

    local_out = f"backups/{DISPLAY_FILENAME}"
    with open(local_out, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Lokální kopie -> {local_out} ({len(content)} znaků, {n_cats} kategorií)")

    if dry_run:
        print("DRY RUN - na Sdílený disk (SEO GEO) nic nenahráno. Spusť s --apply.")
        return

    os.makedirs(DRIVE_FILES_DIR, exist_ok=True)
    token = os.urandom(16).hex()
    stored_filename = f"{token}.md"
    dest = os.path.join(DRIVE_FILES_DIR, stored_filename)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
    os.chown(dest, 33, 33)  # www-data:www-data (stejny vlastnik jako ostatni uploady)
    size_bytes = os.path.getsize(dest)

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
