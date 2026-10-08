#!/usr/bin/env python3
"""JEDNORAZOVY ostry beh po obrraceni Robertova rozhodnuti o vanDrawee
(2026-09-12, pres bot3): puvodni "vanDrawee zustava, jak je" zruseno -
"chce vzor i na ne, stejny jako na zbytek". Logiman SSE galerijni
vyjimka zustava beze zmeny (samostatne rozhodnuti).

Bezi pres VSECHNY kandidatni funkce z timeru (ne jen vanDrawee) - uz
drive orazitkovane soubory projdou jako 'jiz_orazitkovano' (rychla SHA
kontrola, zadne zpracovani obrazku), takze jeden beh pokryje jak nove
uvolnene vanDrawee soubory, tak potvrdi stav zbytku beze zmeny.

NENI zmena automatu - prepinac se necte.

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
import obrazky_razitko as orz  # noqa: E402,F401

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
                    + timer.kandidati_gallery_items(cur)
                    + timer.kandidati_categories(cur)
                    + timer.kandidati_kategorie_popisy(cur))
    finally:
        conn.close()


def main():
    kandidati = ziskej_kandidaty()
    print(f"kandidatu celkem (po zruseni vanDrawee vyjimky): {len(kandidati)}")

    vysledky = []
    nove_vandrawee_url = []
    for abs_path, rel in kandidati:
        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn.commit()
            vysledky.append((rel, vysl, None))
            if vysl == "hotovo" and "vandrawee" in rel.lower():
                nove_vandrawee_url.append(f"{PUBLIC_BASE}/{rel}")
        except Exception as e:  # noqa: BLE001
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

    print(f"\n--- {len(nove_vandrawee_url)} nove otisknutych vanDrawee souboru (vzorek prvnich 10 URL) ---")
    for u in nove_vandrawee_url[:10]:
        print(u)


if __name__ == "__main__":
    main()
