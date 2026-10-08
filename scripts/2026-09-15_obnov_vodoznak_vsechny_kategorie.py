#!/usr/bin/env python3
"""Robert 2026-09-15 (pres bot3), po drivejsi castecne oprave (jen strom
kategorie 149, "profily a prislusenstvi"): "vodoznak ma byt pouze na
fotkach ve fotogaleriích !!!! a to jen tech ktere nepochazi z dogus
webu." Kategorie (`content-files/categories/*`) nemaji mit vodoznak
NIKDY - bez ohledu na puvod (Dogus/nase vlastni), na rozdil od
fotogalerii, kde Dogus-puvod pravidlo zustava.

Obnovuje VSECHNY zbyle orazitkovane `content-files/categories/%`
soubory (`image_watermark_manifest.reverted_at IS NULL`), ne jen
predchozi uzsi strom kategorie 149. Bezpecny vzor prevzat 1:1 z
2026-09-15_obnov_vodoznak_profily_prislusenstvi.py /
2026-09-11_obnov_kontaminovane_ze_vzorku.py: SHA overeni proti
manifestu pred i po zapisu, `reverted_at` znacka misto mazani radku.

Doplnuje se soucasne s opravou `je_kandidat_podle_puvodu()`/
`_gallery_items_povoleno()` (obrazky_razitko.py) - `content-files/
categories/` uz nikdy nebude kandidat na orazitkovani, takze se tohle
nema pri pristi davce opakovat.

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
                "SELECT rel_path, original_backup_path, original_sha256 "
                "FROM image_watermark_manifest "
                "WHERE rel_path LIKE 'content-files/categories/%' AND reverted_at IS NULL "
                "ORDER BY rel_path"
            )
            radky = cur.fetchall()
    finally:
        conn.close()

    print(f"porad orazitkovanych content-files/categories/%: {len(radky)}")

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
