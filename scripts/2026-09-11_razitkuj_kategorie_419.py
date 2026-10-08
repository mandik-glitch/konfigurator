#!/usr/bin/env python3
"""JEDNORAZOVY ostry beh na content-files/categories/ + kategorie-popisy/
(Robert pres bot3, 2026-09-11, po osobnim prohlednuti kontrolniho listu
675 nahledu: "fotky kategorii aplikovat loga" - orazitkovat vse, vc.
rozsahle zapeceneho vlastniho "LOGIMAN" loga; vanDrawee zustava vyrazena,
viz obrazky_razitko.py filtr puvodu).

NENI to zmena automatu - prepinac app_settings['razitkovac_obrazku_
povoleno'] se VUBEC necte. Kandidati ziskani stejnymi funkcemi jako
timer (kandidati_categories/kandidati_kategorie_popisy, pridano do
2026-09-11_razitkovac_obrazku_timer.py soucasne s timhle behem), takze
stejny filtr puvodu (vc. vanDrawee vyjimky) plati pro oba.

Spoustet VYHRADNE jako www-data (systemd-run, viz
2026-09-11_razitkuj_vzorek_20.py pro presny prikaz).
"""
import importlib.util
import os
import sys
from collections import Counter

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "razitkovac_timer", "/opt/konfigurator/scripts/2026-09-11_razitkovac_obrazku_timer.py")
timer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timer)

PUBLIC_BASE = "https://autovestavby.logiman.cz"


def main():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            kandidati = timer.kandidati_categories(cur) + timer.kandidati_kategorie_popisy(cur)
    finally:
        conn.close()
    print(f"kandidatu (po filtru puvodu, vc. vanDrawee vyjimky): {len(kandidati)}")

    vysledky = []
    for abs_path, rel in kandidati:
        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn.commit()
            vysledky.append((rel, vysl, None))
        except Exception as e:  # noqa: BLE001 - jeden spatny soubor nesmi shodit cely beh
            conn.rollback()
            vysledky.append((rel, "chyba", str(e)))
            print(f"  CHYBA {rel}: {e}")
        finally:
            conn.close()

    shrnuti = Counter(v[1] for v in vysledky)
    print(f"\n--- shrnuti: {dict(shrnuti)} ---")
    chyby = [(rel, txt) for rel, vysl, txt in vysledky if vysl == "chyba"]
    if chyby:
        print("\n--- chyby s duvodem ---")
        for rel, txt in chyby:
            print(f"  {rel}: {txt}")

    hotove_rely = [rel for rel, vysl, _ in vysledky if vysl in ("hotovo", "jiz_orazitkovano")]
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if hotove_rely:
                cur.execute(
                    "SELECT rel_path, original_backup_path FROM image_watermark_manifest "
                    "WHERE rel_path IN (%s) AND reverted_at IS NULL" %
                    ",".join(["%s"] * len(hotove_rely)), hotove_rely)
                manifest_radky = cur.fetchall()
            else:
                manifest_radky = []
    finally:
        conn.close()
    zaloh_existuje = sum(1 for r in manifest_radky if os.path.isfile(r["original_backup_path"]))
    print(f"\nkandidatu celkem: {len(kandidati)}")
    print(f"zpracovano (hotovo+jiz_orazitkovano): {len(hotove_rely)}")
    print(f"radku v manifestu (reverted_at IS NULL): {len(manifest_radky)}")
    print(f"z toho zaloha fyzicky existuje na disku: {zaloh_existuje}")


if __name__ == "__main__":
    main()
