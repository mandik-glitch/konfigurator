#!/usr/bin/env python3
"""Rucni beh razitkovace na VYSLOVNY seznam souboru - pro prvni ostry
vzorek pred plosnym nasazenim (Robert pres bot3, 2026-09-11): "Nejdrív
malý vzorek naostro... asi dvacet fotek z gallery/realizace_stolu nebo
vestavby_dodavek... at jsou mezi nimi svetle i tmave a aspon jedna s
rusnym pozadim; ne dvacet skoro stejnych."

Seznam nize vybran z 167 aktivnich (active=1) souboru v obou kategoriich
podle zmereneho jasu (ImageStat mean 0-255) + rozptylu (std - vyssi =
rusnejsi pozadi), rucne prohlednuto tak, aby zadna dvojice nebyla ze
stejne rady skoro identickych fotek (napr. jen JEDNA z "stavebnice-do-
aut-vandrawee-*", jen JEDNA z "kryt-priklad-*").

POZOR: spoustet VYHRADNE jako www-data (viz _over_ze_nebezi_pod_rootem
v obrazky_razitko.py - pod rootem konci vyjimkou uz na prvnim souboru):
    systemd-run --uid=www-data --gid=www-data --pipe --wait \
      --property=EnvironmentFile=/opt/konfigurator/api/.env \
      /opt/konfigurator/api/venv/bin/python3 \
      /opt/konfigurator/scripts/2026-09-11_razitkuj_vzorek_20.py

Prepinac app_settings['razitkovac_obrazku_povoleno'] se tu VUBEC necte -
tenhle skript je rucni jednorazovy beh na explicitni seznam, ne
prubezny automat (ten je v 2026-09-11_razitkovac_obrazku_timer.py).
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402

VZOREK = [
    ("vestavby_dodavek", "vestavba-filmoveho-stabu.jpg"),
    ("vestavby_dodavek", "mobilni-kancelar.jpg"),
    ("vestavby_dodavek", "regal-do-fiat-ducato-l2h1.jpg"),
    ("vestavby_dodavek", "supliky-organizery-do-auta.jpg"),
    ("vestavby_dodavek", "regalovy-system-do-aut-1.jpg"),
    ("vestavby_dodavek", "stavebnice-do-aut-vandrawee-2020-foto-00.jpg"),
    ("vestavby_dodavek", "skrine-do-dodavky-na-miru.jpg"),
    ("vestavby_dodavek", "regaly-do-transportera.jpg"),
    ("realizace_stolu", "logiman-sse-vratkove-stoly.jpg"),
    ("realizace_stolu", "kryt-priklad-7.jpg"),
    ("vestavby_dodavek", "regal-v-aute.jpg"),
    ("realizace_stolu", "balici-nastavitelne-stoly.jpg"),
    ("vestavby_dodavek", "nastupni-schudek-do-auta.jpg"),
    ("realizace_stolu", "balici-ergonomicke-stoly.jpg"),
    ("vestavby_dodavek", "3d-model-vestavby-do-auta.jpg"),
    ("realizace_stolu", "ramy-stroju-ukazka2.jpg"),
    ("vestavby_dodavek", "ford-transit-doublefloor-01.jpg"),
    ("vestavby_dodavek", "vysuvy-z-podlahy-na-miru.jpg"),
    ("realizace_stolu", "esse-2000-900-ergo-zdvih-450-950.jpg"),
    ("realizace_stolu", "rezacka-zakazka.jpg"),
]

PUBLIC_BASE = "https://autovestavby.logiman.cz"


def main():
    vysledky = []
    for kategorie, filename in VZOREK:
        rel = f"content-files/gallery/{kategorie}/{filename}"
        abs_path = os.path.join(orz.WEBAPP_ROOT, rel)
        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn.commit()
        except Exception as e:  # noqa: BLE001 - jeden spatny soubor nesmi shodit zbytek vzorku
            conn.rollback()
            vysl = f"CHYBA: {e}"
        finally:
            conn.close()
        url = f"{PUBLIC_BASE}/{rel}"
        vysledky.append((vysl, url))
        print(f"{vysl:20} {url}")

    print("\n--- shrnuti ---")
    from collections import Counter
    print(Counter(v[0] for v in vysledky))
    print("\n--- URL seznam ---")
    for _, url in vysledky:
        print(url)


if __name__ == "__main__":
    main()
