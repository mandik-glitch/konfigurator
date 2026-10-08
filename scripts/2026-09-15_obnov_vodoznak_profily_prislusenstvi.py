#!/usr/bin/env python3
"""Robert 2026-09-15 (ALL-CAPS urgence): "vsude na samotnych profilech a
prislusenstvi jsou vodoznaky omylem" - kategorie pod "Hlinikove
stavebnicove profily" (id=149) maji nahledovy obrazek (`content_categories.
image_filename`) casto kopii Dogus dodavatelske fotky, ale
`je_kandidat_podle_puvodu()` (obrazky_razitko.py:311,339) u
`content-files/categories/` NEMA zadny puvod-signal k dispozici (kategorie
nejsou vazane na konkretni produkt/dodavatele) a vraci vzdy True - proto
je 2026-09-11 davka (2026-09-11_razitkuj_kategorie_419.py, tehdy Robertem
schvalene "orazitkovat VSE vc. kategorii") otiskla i tyhle.

Bezpecny vzor prevzat 1:1 z 2026-09-11_obnov_kontaminovane_ze_vzorku.py:
SHA overeni proti manifestu pred i po zapisu, `reverted_at` znacka misto
mazani radku (historie "bylo otisknuto, pak obnoveno" zustava).

Spoustet VYHRADNE jako www-data (systemd-run, viz
2026-09-11_razitkuj_vzorek_20.py pro presny prikaz).
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
                WITH RECURSIVE sub AS (
                    SELECT id, image_filename FROM content_categories WHERE id=149
                    UNION ALL
                    SELECT c.id, c.image_filename FROM content_categories c
                    JOIN sub s ON c.parent_id = s.id
                )
                SELECT image_filename FROM sub WHERE image_filename IS NOT NULL ORDER BY id
                """
            )
            soubory = [r["image_filename"] for r in cur.fetchall()]
            rel_paths = [f"content-files/categories/{f}" for f in soubory]
            ph = ",".join(["%s"] * len(rel_paths))
            cur.execute(
                f"SELECT rel_path, original_backup_path, original_sha256, reverted_at "
                f"FROM image_watermark_manifest WHERE rel_path IN ({ph})",
                rel_paths,
            )
            radky = {r["rel_path"]: r for r in cur.fetchall()}
    finally:
        conn.close()

    print(f"kandidatu (kategorie 149 + potomci, s image_filename): {len(rel_paths)}")
    print(f"nalezeno v manifestu: {len(radky)}")

    hotovo = 0
    for rel in rel_paths:
        radek = radky.get(rel)
        if not radek:
            print(f"CHYBA {rel}: neni v manifestu, preskakuji")
            continue
        if radek["reverted_at"] is not None:
            print(f"UZ OBNOVENO drive {rel}")
            continue
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

    print(f"\ncelkem obnoveno: {hotovo} / {len(rel_paths)}")


if __name__ == "__main__":
    main()
