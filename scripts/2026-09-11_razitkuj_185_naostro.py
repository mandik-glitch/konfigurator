#!/usr/bin/env python3
"""JEDNORAZOVY ostry beh na CELY schvaleny seznam kandidatu (Robert pres
bot3, 2026-09-11: "pustit vsech 185 ted" - vzhled i hustotu 1,5016 bere).

NENI to instalace automatu - prepinac app_settings['razitkovac_obrazku_
povoleno'] se VUBEC necte a timer se NEINSTALUJE (bot3 vyslovne: "Nezapinej
timer a nezakladej prepinac. Tohle je jednorazovy beh na muj pokyn, ne
spusteni automatu."). Kandidati se ziskaji STEJNYMI funkcemi jako
timer (2026-09-11_razitkovac_obrazku_timer.py) - stejny filtr puvodu,
tedy uz BEZ obou vyrazenych fotoshootu (Logiman SSE, vanDrawee) a bez
kategorii/popisu (ty jeste cekaji na Robertuv kontrolni list).

Spoustet VYHRADNE jako www-data (systemd-run, viz
2026-09-11_razitkuj_vzorek_20.py pro presny prikaz) - bot3: "Mas tam
sice od bot4 kontrolu os.geteuid(), ale spolehat na pojistku misto na
postup je presne to, cemu se vyhybame."
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


def ziskej_kandidaty():
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            return (timer.kandidati_ze_souboroveho_systemu(cur)
                    + timer.kandidati_gallery_products(cur)
                    + timer.kandidati_product_usage(cur)
                    + timer.kandidati_gallery_items(cur))
    finally:
        conn.close()


def main():
    kandidati = ziskej_kandidaty()
    print(f"kandidatu (po filtru puvodu, vc. vyrazenych fotoshootu): {len(kandidati)}")

    vysledky = []  # (rel, vysledek, chyba_text|None)
    for abs_path, rel in kandidati:
        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn.commit()
            vysledky.append((rel, vysl, None))
            print(f"  {vysl:20} {rel}")
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

    # over pocet radku v manifestu a zaloh pro presne tyhle rel_path
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
    print(f"radku v manifestu (reverted_at IS NULL) pro tyhle soubory: {len(manifest_radky)}")
    print(f"z toho zaloha fyzicky existuje na disku: {zaloh_existuje}")

    print("\n--- pripravene URL pro namatkovou kontrolu (par z ruznych kategorii, Ctrl+F5!) ---")


if __name__ == "__main__":
    main()
