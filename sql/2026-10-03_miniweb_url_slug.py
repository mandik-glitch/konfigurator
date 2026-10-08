"""Migrace (bot5, 2026-10-03, idempotentni): URL slug po jazycich (SEO adresy) - `url_slug` v miniweb_category_texts a miniweb_product_texts (NULL = pouzije se zakladni jazykove neutralni slug),
unikatni v ramci jazyka (UNIQUE lang + url_slug; NULL hodnot muze byt vic). Sloupec se jmenuje url_slug (ne slug), aby se nepralo s `slug` kategorie/produktu v dotazech s t.*.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 sql/2026-10-03_miniweb_url_slug.py"""
import os
import pymysql
conn = pymysql.connect(host=os.environ["DB_HOST"], port=int(os.environ["DB_PORT"]), user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], autocommit=True)
cur = conn.cursor()
for tabulka in ("miniweb_category_texts", "miniweb_product_texts"):
    cur.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME='url_slug'", (tabulka,))
    if not cur.fetchone()[0]:
        cur.execute(f"ALTER TABLE `{tabulka}` ADD COLUMN `url_slug` VARCHAR(100) DEFAULT NULL COMMENT 'URL slug v jazyce textu, NULL = zakladni slug'")
        print("+", tabulka, "url_slug")
    cur.execute("SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND INDEX_NAME='uq_lang_url_slug'", (tabulka,))
    if not cur.fetchone()[0]:
        cur.execute(f"ALTER TABLE `{tabulka}` ADD UNIQUE KEY `uq_lang_url_slug` (`lang`, `url_slug`)")
        print("+ index", tabulka)
print("hotovo")
