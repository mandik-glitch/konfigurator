"""
Doplneni obrazku (+ body_html/meta_description) 3 dlazdicim homepage
mozaiky, ktere QA audit (homepage_block_missing_image) hlasil jako
viditelne bez obrazku (id 4, 5, 7).

Zdroje obrazku (zadne nove generovani z nuly, vsude existujici asset):
- #4 "Alu profily vhodne pro vestavby pracovnich dodavek": realna
  produktova fotka profilu 40x40 SuperLight (shop_products.id 3468,
  Robert oznacil jako "univerzalni pro vsechny uzitkove pracovni auta"),
  webapp/content-files/gallery/products/3468/1.jpg.
- #5 "Poskladejte si Vas produkt ve 3D z aluprofilu": jiz vyrenderovany
  katalogovy nahled hotove konstrukce slozene z profilu ("Dvojstul
  Tchibo", shop_products.id 3672), webapp/katalog/thumbnails/product-3672.jpg
  - nejlepsi existujici ukazka "poskladaneho produktu z aluprofilu ve 3D".
- #7 "Zastupujeme vyrobce Dogus Kalip": oficialni logo Dogus Kalip
  (stazeno z jejich verejneho webu static.doguskalip.com.tr/imgsrv/images/logo.png,
  jsme jejich smluvni obchodni zastupce pro CR, viz shop_products.dogus_*
  sloupce a supplier ucet v PRISTUPY.md) + text o zastoupeni, slozeno do
  jednoho tile obrazku pres scripts skript (viz scratchpad make_dogus_tile.py,
  vysledek zkopirovan do backups/ pro referenci).

Idempotentni: aktualizuje jen radky, kde je image_filename dnes prazdne/NULL
(stejna podminka jako QA kontrola v api/qa_checks.py:check_homepage_block_missing_image).
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

DATA = {
    4: dict(
        source="/opt/konfigurator/webapp/content-files/gallery/products/3468/1.jpg",
        ext="jpg",
        meta_description=(
            "Hliníkové profily pro vestavby do dodávek: 40x40 SuperLight univerzálně, "
            "45x45 SuperLight pro velké dodávky, 30x30 pro výsuvné rámy, 20x20/20x40 pro dvířka."
        ),
        body_html=(
            "<h3>Hliníkové profily pro vestavby do užitkových vozidel</h3>"
            "<p>Podle typu vozidla a konstrukce doporučujeme:</p>"
            "<ul>"
            "<li><strong>40x40 SuperLight</strong> – univerzální profil vhodný pro vestavby do "
            "všech typů užitkových pracovních dodávek.</li>"
            "<li><strong>45x45 SuperLight</strong> – silnější profil, jen pro velké dodávky "
            "s vyšší nosností konstrukce.</li>"
            "<li><strong>30x30</strong> – pro výsuvné rámy.</li>"
            "<li><strong>20x20 a 20x40</strong> – pro jednoboxové výsuvy a dvířka.</li>"
            "</ul>"
            "<p>Konstrukci si můžete poskládat přímo v <a href=\"/scene.html\">3D konfigurátoru</a> "
            "a rovnou vidět cenu materiálu.</p>"
        ),
    ),
    5: dict(
        source="/opt/konfigurator/webapp/katalog/thumbnails/product-3672.jpg",
        ext="jpg",
        meta_description=(
            "Postavte si konstrukci z hliníkových profilů ve 3D konfigurátoru Logiman přímo "
            "v prohlížeči – rovnou vidíte náhled i cenu materiálu a spojů."
        ),
        body_html=(
            "<h3>Poskládejte si vlastní konstrukci ve 3D</h3>"
            "<p>V našem 3D konfigurátoru si během pár minut poskládáte vlastní konstrukci "
            "z hliníkových stavebnicových profilů a příslušenství – přímo v prohlížeči, bez "
            "instalace. Vidíte rovnou 3D náhled i cenu materiálu a spojů.</p>"
            "<p><a href=\"/scene.html\">Otevřít 3D konfigurátor</a></p>"
        ),
    ),
    7: dict(
        source="/tmp/claude-0/-opt-konfigurator/c6fb6b7b-721b-4097-8178-6c1def2f1db4/scratchpad/dogus_tile.jpg",
        ext="jpg",
        meta_description=(
            "Logiman je autorizovaným obchodním zástupcem tureckého výrobce hliníkových "
            "profilů Doğuş Kalıp pro Českou republiku – jeho sortiment najdete v katalogu."
        ),
        body_html=(
            "<h3>Doğuş Kalıp – výrobce hliníkových profilových systémů</h3>"
            "<p>Jsme autorizovaným obchodním zástupcem výrobce Doğuş Kalıp pro Českou "
            "republiku. Doğuş Kalıp vyrábí širokou řadu hliníkových stavebnicových profilů "
            "a spojovacích prvků, které u nás najdete přímo v katalogu i ve 3D konfigurátoru.</p>"
        ),
    ),
}


def main():
    dry_run = "--apply" not in sys.argv
    os.makedirs(HOMEPAGE_BLOCK_IMAGE_DIR, exist_ok=True)

    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, image_filename, body_html, meta_description FROM homepage_blocks "
        "WHERE is_visible=1 AND (image_filename IS NULL OR image_filename='')"
    )
    missing = {r["id"]: r for r in cur.fetchall()}

    not_covered = [i for i in missing if i not in DATA]
    if not_covered:
        print("CHYBI DATA pro id:", not_covered)
        sys.exit(1)

    backup = {str(i): missing[i] for i in missing if i in DATA}
    backup_path = "backups/homepage_mosaic_missing_images_backfill_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2, default=str)
    print(f"Zaloha {len(backup)} radku -> {backup_path}")

    n = 0
    for block_id, spec in DATA.items():
        if block_id not in missing:
            print(f"#{block_id} uz ma obrazek, preskakuji")
            continue
        if not os.path.isfile(spec["source"]):
            print(f"CHYBI zdrojovy soubor pro #{block_id}: {spec['source']}")
            sys.exit(1)
        if dry_run:
            print(f"#{block_id} {missing[block_id]['title']!r} <- {spec['source']}")
            print(f"  meta: {spec['meta_description']} ({len(spec['meta_description'])} znaku)")
            continue
        stored_name = f"{block_id}_{os.urandom(6).hex()}.{spec['ext']}"
        shutil.copyfile(spec["source"], os.path.join(HOMEPAGE_BLOCK_IMAGE_DIR, stored_name))
        cur.execute(
            "UPDATE homepage_blocks SET image_filename=%s, body_html=%s, meta_description=%s WHERE id=%s",
            (stored_name, spec["body_html"], spec["meta_description"], block_id),
        )
        n += 1

    if dry_run:
        print(f"\nDRY RUN - {len(DATA)} dlazdic pripraveno, 0 zapsano. Spust s --apply pro skutecny zapis.")
    else:
        conn.commit()
        print(f"Zapsano {n} dlazdic.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
