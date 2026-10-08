#!/usr/bin/env python3
"""Robert 2026-09-15 (pres bot3): "vodoznak ma byt pouze na fotkach ve
fotogaleriích !!!! a to jen tech ktere nepochazi z dogus webu." Bot3
nahlasil `content-files/categories/*` (obnoveno samostatnym skriptem
2026-09-15_obnov_vodoznak_vsechny_kategorie.py) - pri kontrole vsech
STAMP_DIRS (obrazky_razitko.py) jsem navic nasel DALSI stejnou tridu
problemu, kterou bot3 nezminil: `content-files/kategorie-popisy/*`
(obrazky VLOZENE PRIMO DO TEXTU popisu kategorie - body_html/
bottom_body_html/intro_html, viz 2026-09-12_photo_library_backfill.py)
- taky NENI fotogalerie, take spada pod stejny puvod-signal-chybi ->
vzdy-True bug jako categories/, a je jich VIC (527 porad orazitkovanych,
vs. 89 u categories/).

Bezpecny vzor prevzat 1:1 z 2026-09-15_obnov_vodoznak_vsechny_kategorie.py:
SHA overeni proti manifestu pred i po zapisu, `reverted_at` znacka
misto mazani radku.

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

PREFIX = "content-files/kategorie-popisy/%"


def main():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rel_path, original_backup_path, original_sha256 "
                "FROM image_watermark_manifest "
                "WHERE rel_path LIKE %s AND reverted_at IS NULL "
                "ORDER BY rel_path",
                (PREFIX,),
            )
            radky = cur.fetchall()
    finally:
        conn.close()

    print(f"porad orazitkovanych {PREFIX}: {len(radky)}")

    hotovo, chyby = 0, 0
    for radek in radky:
        rel = radek["rel_path"]
        abs_path = os.path.join(orz.WEBAPP_ROOT, rel)
        if not os.path.isfile(radek["original_backup_path"]):
            print(f"STOP {rel}: zaloha na disku chybi ({radek['original_backup_path']}), PRESKAKUJI")
            chyby += 1
            continue
        with open(radek["original_backup_path"], "rb") as f:
            zaloha_bytes = f.read()
        if orz._sha256(zaloha_bytes) != radek["original_sha256"]:
            print(f"STOP {rel}: zaloha se neshoduje s manifestem, PRESKAKUJI")
            chyby += 1
            continue
        orz._atomicky_zapis(abs_path, zaloha_bytes)
        with open(abs_path, "rb") as f:
            po_obnove = f.read()
        if orz._sha256(po_obnove) != radek["original_sha256"]:
            print(f"CHYBA {rel}: po obnove neshoda!")
            chyby += 1
            continue

        conn2 = app.get_conn()
        try:
            with conn2.cursor() as cur:
                orz._zapis_obnoveni(cur, rel)
            conn2.commit()
        finally:
            conn2.close()
        hotovo += 1
        if hotovo % 25 == 0:
            print(f"... {hotovo}/{len(radky)}")

    print(f"\ncelkem obnoveno: {hotovo} / {len(radky)} (chyb: {chyby})")


if __name__ == "__main__":
    main()
