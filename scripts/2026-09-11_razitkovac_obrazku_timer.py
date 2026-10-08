#!/usr/bin/env python3
"""Hlidaci timer automatickeho razitkovace obrazku - viz
scripts/obrazky_razitko.py pro celou logiku a duvody.

Robert: "nech postavit automaticky razitkovac na vsechny obrazky na webu...
nech hlida script." bot3 2026-09-11: u gallery-items/ neni tenhle timer
"jen" zachranna sit - PUT /api/gallery-items/<id> prepina is_public 0->1
PO nahrani (bot10ovo zjisteni), takze "nahraju soukrome, po revizi
zverejnim" je BEZNA cesta ke vzniku nove verejne fotky a upload-hook ji
nikdy nezachyti. Interval timeru pocita s tim - viz deploy/
konfigurator-razitkovac-obrazku.timer.

Vypinac app_settings['razitkovac_obrazku_povoleno'] - VYCHOZI VYPNUTO,
zapina Robert. Cte se na ZACATKU behu (skript je oneshot pres timer),
takze vypnuti neprerusi prave bezici beh, zabere az u dalsiho tiku.

Strop KROKU_MAX na beh - zadna nekonecna smycka, dalsi beh prijde od
casovace. 3 selhani tehoz souboru po sobe = automat uz nezkousi (fail_count
v manifestu by se hodil, ale manifest dnes fail_count nema - viz TASKS.md
poznamka na konci tohohle souboru).

Pouziti:
    api/venv/bin/python3 scripts/2026-09-11_razitkovac_obrazku_timer.py            # beh
    api/venv/bin/python3 scripts/2026-09-11_razitkovac_obrazku_timer.py --dry-run  # jen vypise kandidaty
"""
import os
import sys

sys.path.insert(0, "/opt/konfigurator/scripts")
sys.path.insert(0, "/opt/konfigurator/api")

import _env  # noqa: E402
os.environ.update(_env.load_env())

import app  # noqa: E402,F401
import obrazky_razitko as orz  # noqa: E402

KROKU_MAX = 300  # in-memory PIL, ne subprocess - snese vic nez watchdog_prace


def povoleno(cur):
    v = app.get_setting(cur, "razitkovac_obrazku_povoleno", "0")
    return str(v).strip() == "1"


def kandidati_ze_souboroveho_systemu(cur):
    """content-files/gallery (mimo products/, ten resi kandidati_gallery_
    products), homepage-blocks, sidebar-blocks - existence na disku =
    verejne viditelne (zadny is_public priznak u techhle typu)."""
    ven = []
    for d in ("content-files/gallery/vestavby_dodavek",
              "content-files/gallery/realizace_stolu",
              "content-files/homepage-blocks",
              "content-files/sidebar-blocks"):
        abs_dir = os.path.join(orz.WEBAPP_ROOT, d)
        if not os.path.isdir(abs_dir):
            continue
        for jmeno in os.listdir(abs_dir):
            abs_path = os.path.join(abs_dir, jmeno)
            if not os.path.isfile(abs_path):
                continue
            rel = f"{d}/{jmeno}"
            if orz.je_kandidat_podle_puvodu(cur, rel):
                ven.append((abs_path, rel))
    return ven


def kandidati_gallery_products(cur):
    """content-files/gallery/products/<id>/* - filtrovano uz uvnitr
    je_kandidat_podle_puvodu podle vlastnika produktu."""
    zaklad = os.path.join(orz.WEBAPP_ROOT, "content-files/gallery/products")
    ven = []
    if not os.path.isdir(zaklad):
        return ven
    for pid in os.listdir(zaklad):
        adresar = os.path.join(zaklad, pid)
        if not os.path.isdir(adresar):
            continue
        for jmeno in os.listdir(adresar):
            abs_path = os.path.join(adresar, jmeno)
            if not os.path.isfile(abs_path):
                continue
            rel = f"content-files/gallery/products/{pid}/{jmeno}"
            if orz.je_kandidat_podle_puvodu(cur, rel):
                ven.append((abs_path, rel))
    return ven


def kandidati_product_usage(cur):
    zaklad = os.path.join(orz.WEBAPP_ROOT, "content-files/product-usage")
    ven = []
    if not os.path.isdir(zaklad):
        return ven
    for jmeno in os.listdir(zaklad):
        abs_path = os.path.join(zaklad, jmeno)
        if not os.path.isfile(abs_path):
            continue
        rel = f"content-files/product-usage/{jmeno}"
        if orz.je_kandidat_podle_puvodu(cur, rel):
            ven.append((abs_path, rel))
    return ven


def kandidati_categories(cur):
    """content-files/categories/<id>_image_filename_<hash>.<ext> - Robert
    2026-09-11 osobne prohledl kontrolni list a rozhodl orazitkovat
    (vc. rozsahle zapeceneho vlastniho LOGIMAN loga - viz filtr
    puvodu). Plocha slozka, zadna DB tabulka k dotazovani netreba."""
    zaklad = os.path.join(orz.WEBAPP_ROOT, "content-files/categories")
    ven = []
    if not os.path.isdir(zaklad):
        return ven
    for jmeno in os.listdir(zaklad):
        abs_path = os.path.join(zaklad, jmeno)
        if not os.path.isfile(abs_path):
            continue
        rel = f"content-files/categories/{jmeno}"
        if orz.je_kandidat_podle_puvodu(cur, rel):
            ven.append((abs_path, rel))
    return ven


def kandidati_kategorie_popisy(cur):
    """content-files/kategorie-popisy/<id>/<soubor> - stejne rozhodnuti
    jako kandidati_categories(). POZOR (bot3 2026-09-11): '_small'
    dvojcata dostavaji razitko TAKY, ne jen velka verze - jinak by na
    webu vedle sebe byla orazitkovana i neorazitkovana podoba tehoz
    obrazku. Zadna dedup logika tady proto NENI, kazdy soubor na disku
    je vlastni kandidat."""
    zaklad = os.path.join(orz.WEBAPP_ROOT, "content-files/kategorie-popisy")
    ven = []
    if not os.path.isdir(zaklad):
        return ven
    for id_slozka in os.listdir(zaklad):
        adresar = os.path.join(zaklad, id_slozka)
        if not os.path.isdir(adresar):
            continue
        for jmeno in os.listdir(adresar):
            abs_path = os.path.join(adresar, jmeno)
            if not os.path.isfile(abs_path):
                continue
            rel = f"content-files/kategorie-popisy/{id_slozka}/{jmeno}"
            if orz.je_kandidat_podle_puvodu(cur, rel):
                ven.append((abs_path, rel))
    return ven


def kandidati_gallery_items(cur):
    """POZOR (bot10 2026-09-11): is_public muze byt 0->1 prepnuto AZ PO
    nahrani (PUT /api/gallery-items/<id>) - timer je tu HLAVNI cesta, ne
    zachranna sit. Bereme jen is_public=1, owner_type IN (category,product)."""
    cur.execute(
        "SELECT filename FROM content_gallery_items "
        "WHERE is_public=1 AND owner_type IN ('category','product')")
    ven = []
    zaklad = os.path.join(orz.WEBAPP_ROOT, "content-files/gallery-items")
    for r in cur.fetchall():
        rel = f"content-files/gallery-items/{r['filename']}"
        abs_path = os.path.join(zaklad, r["filename"])
        if os.path.isfile(abs_path) and orz.je_kandidat_podle_puvodu(cur, rel):
            ven.append((abs_path, rel))
    return ven


def main():
    dry = "--dry-run" in sys.argv
    smazano = orz.uklid_osirelych_tmp_souboru()
    if smazano:
        print(f"uklid osirelych .razitko-tmp-*: {smazano} souboru smazano")
    conn = app.get_conn()
    try:
        with conn.cursor() as cur:
            if not povoleno(cur):
                print("razitkovac_obrazku_povoleno != '1' - automat vypnuty, konci.")
                return 0
            kandidati = (kandidati_ze_souboroveho_systemu(cur)
                        + kandidati_gallery_products(cur)
                        + kandidati_product_usage(cur)
                        + kandidati_gallery_items(cur)
                        + kandidati_categories(cur)
                        + kandidati_kategorie_popisy(cur))
    finally:
        conn.close()

    print(f"kandidatu (po filtru puvodu): {len(kandidati)}")
    if dry:
        for abs_path, rel in kandidati[:KROKU_MAX]:
            print(f"  [nahled] {rel}")
        print("--dry-run: nic se neotisklo.")
        return 0

    zpracovano = {"hotovo": 0, "jiz_orazitkovano": 0, "vyrazeno_puvodem": 0, "chyba": 0}
    for abs_path, rel in kandidati[:KROKU_MAX]:
        conn = app.get_conn()
        try:
            with conn.cursor() as cur:
                cfg = orz.nacti_konfiguraci(cur)
                vysl = orz.orazitkuj_existujici_soubor(cur, abs_path, rel, cfg)
            conn.commit()
            zpracovano[vysl] = zpracovano.get(vysl, 0) + 1
        except Exception as e:  # noqa: BLE001 - jeden spatny soubor nesmi shodit cely beh
            conn.rollback()
            zpracovano["chyba"] += 1
            print(f"  CHYBA {rel}: {e}")
        finally:
            conn.close()

    print(f"vysledek: {zpracovano}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
