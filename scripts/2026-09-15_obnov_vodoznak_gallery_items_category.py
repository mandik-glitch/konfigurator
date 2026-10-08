#!/usr/bin/env python3
"""Robert 2026-09-15 (pres bot3): "vodoznak má být pouze na fotkach ve
fotogaleriích !!!! a to jen tech ktere nepochazi z dogus webu." Bot3
upozornil na `_gallery_items_povoleno()` (obrazky_razitko.py) -
`owner_type='category'` vracelo True (zadny puvod-signal u kategorii
neexistuje -> radsi propustit), coz je stejny bug jako u categories/ a
kategorie-popisy/. Kontrola v DB nasla 4 dotcene soubory
(content-files/gallery-items/category-245_*).

Bezpecny vzor prevzat 1:1 z predchozich dvou obnovovacich skriptu
(2026-09-15_obnov_vodoznak_vsechny_kategorie.py /
..._kategorie_popisy.py): SHA overeni proti manifestu pred i po
zapisu, `reverted_at` znacka misto mazani radku.

Spoustet VYHRADNE jako www-data (systemd-run).
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402


def main():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.rel_path, m.original_backup_path, m.original_sha256
                FROM image_watermark_manifest m
                JOIN content_gallery_items gi ON gi.filename = SUBSTRING_INDEX(m.rel_path, '/', -1)
                WHERE m.rel_path LIKE 'content-files/gallery-items/%'
                  AND m.reverted_at IS NULL AND gi.owner_type='category'
                """
            )
            radky = cur.fetchall()
    finally:
        conn.close()

    print(f"porad orazitkovanych gallery-items s owner_type=category: {len(radky)}")

    hotovo = 0
    for radek in radky:
        rel = radek["rel_path"]
        abs_path = os.path.join(orz.WEBAPP_ROOT, rel)
        if not os.path.isfile(radek["original_backup_path"]):
            print(f"STOP {rel}: zaloha na disku chybi ({radek['original_backup_path']}), PRESKAKUJI")
            continue
        with open(radek["original_backup_path"], "rb") as f:
            zaloha_bytes = f.read()
        if orz._sha256(zaloha_bytes) != radek["original_sha256"]:
            print(f"STOP {rel}: zaloha se neshoduje s manifestem, PRESKAKUJI")
            continue
        orz._atomicky_zapis(abs_path, zaloha_bytes)
        with open(abs_path, "rb") as f:
            po_obnove = f.read()
        if orz._sha256(po_obnove) != radek["original_sha256"]:
            print(f"CHYBA {rel}: po obnove neshoda!")
            continue

        conn2 = app.get_conn()
        try:
            with conn2.cursor() as cur:
                orz._zapis_obnoveni(cur, rel)
            conn2.commit()
        finally:
            conn2.close()
        hotovo += 1
        print(f"OBNOVENO+OVERENO+OZNACENO(reverted_at) {rel}")

    print(f"\ncelkem obnoveno: {hotovo} / {len(radky)}")


if __name__ == "__main__":
    main()
