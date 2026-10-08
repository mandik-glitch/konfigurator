#!/usr/bin/env python3
"""Presne znackove/SKU shody DEK.cz vuci uz existujicim produktum
(Ptáček-shop.cz/Aquatopshop.cz) v remeslo_material_prices - bot11,
2026-08-17.

Kontext: Robert (přes bot3) upřesnil cíl srovnávače - primárně hledat
STEJNÉ produkty/modely (ne jen "co e-shop nabízí navíc"), aby šlo
reálně porovnat cenu STEJNÉ položky napříč dodavateli vedle sebe.
Doplňuje 2026-08-17_remeslo_scrape_dek.py (obecný kategoriový scraper -
Robert následně potvrdil, že OBOJÍ má zůstat, generické položky
srovnatelné podle rozměru/typu i přesné značkové shody).

METODA (offline matching, žádné dodatečné HTTP dotazy na hledání):
1. Načteny všechny distinct `product_name` z Ptáček/Aquatop.
2. Z každého extrahovány "brand token" (vedoucí VELKÁ písmena/čísla
   před prvním obyčejným českým popisným slovem, např. "ARISTON
   ANDRIS LUX 15" -> ["ariston","andris","lux","15"]).
3. Tokeny porovnány proti `export.dek.cz/dek/sitemap/eshop-product-*.xml`
   (83 083 URL, staženo živě 2026-08-17) - shoda vyžaduje PŘESNOU shodu
   na úrovni SLOV ve slugu (rozdělených podle pomlčky, číselné DEK ID
   na začátku odstraněno), NE libovolný podřetězec (první pokus měl
   bug - "50" jako token se náhodně shodoval s koncem číselného ID
   produktu, ne se skutečným modelem - opraveno na exact-word-match).
4. Ručně vyřazeny nejednoznačné/rizikové shody, kde DEK slug obsahoval
   EXTRA odlišující slovo (wifi/sestava/pack), které NENÍ v našem
   vlastním názvu - u "ARISTON VELIS PRO 50/80/100 EU" (bez WiFi)
   DEK nabízí jen WiFi variantu (jiné SKU, typicky jiná cena) -
   vyřazeno jako mismatch, ne domýšleno. "PROTHERM RAY 14KE" ->
   DEK jen jako "sestava" (kotel+zásobník bundle, jiný produkt) -
   vyřazeno. "JIKA PURE" (stacionární WC) -> DEK jen "pack" varianta
   ZÁVĚSNÉHO WC (jiný typ instalace) - vyřazeno.
   "ARISTON LYDOS HYBRID 80/100 WiFi" naopak PONECHÁNO - "WiFi" je
   součástí i NAŠEHO vlastního názvu (jen extraktor tokenů ho
   nezachytil kvůli smíšené velikosti písmen "WiFi"), takže to NENÍ
   mismatch.

Výsledek: 26 jednoznačných shod (viz PRODUCTS níž) - všechny ověřeny
ručně, ne jen automaticky.

Skript stáhne KAŽDOU z 26 produktových stránek (živě, respektuje
10s odstup), přečte skutečnou cenu (stejná HTML struktura jako
obecný DEK scraper - `price-vat highlight`), a zapíše do
`remeslo_material_prices` se `source_id`=DEK.cz. Kategorie se
přebírá ze STEJNÉ kategorie, jakou má odpovídající produkt u
Ptáčka/Aquatopu (skutečná srovnatelnost - stejná kategorie napříč
zdroji), ne nová DEK-specifická kategorie.

Bez --apply jde o READ-ONLY dry-run.

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_dek_exact_matches.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_dek_exact_matches.py --apply
"""
import argparse
import os
import re
import sys
import time
import urllib.request

import pymysql

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
for _line in open(_ENV_PATH, encoding="utf-8"):
    _line = _line.strip()
    if not _line or _line.startswith("#") or "=" not in _line:
        continue
    _k, _v = _line.split("=", 1)
    os.environ.setdefault(_k, _v)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
# POZOR: remeslo_* tabulky ZIJI OD 2026-08-19 VE VLASTNI DB "Remeslnik"
# (viz REMESLO_KONCEPT.md "Infrastruktura - presun na vlastni DB").
# get_conn() z app.py miri na HLAVNI DB, kde uz jsou remeslo_* tabulky
# jen zmrzly snimek - zapis pres nej by tise skoncil v nepouzivane
# kopii. Proto get_remeslo_conn(). Nalezeno auditem (bot14, 2026-08-19).
from remeslo import get_remeslo_conn as get_conn  # noqa: E402

SUPPLIER_NAME = "DEK.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"

# (existujici_product_name_u_Ptacka/Aquatopu, existujici_kategorie_v_DB, DEK_produkt_url)
PRODUCTS = [
    ("ARISTON ANDRIS LUX 15 zásobníkový ohřívač 15 l, elektrický, nad umyvadlo", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000048810-ariston-andris-lux-15-ohrivac-elektricky-tlakovy-nad-umyvadlo-3100364"),
    ("ARISTON ANDRIS LUX 30 zásobníkový ohřívač 30 l, elektrický, nad umyvadlo", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000048830-ariston-andris-lux-30-ohrivac-elektricky-tlakovy-nad-umyvadlo-3100369"),
    ("ARISTON ARKSH 5U EU zásobníkový ohřívač 5 l, elektrický, beztlakový, pod umyvadlo, s umyvadlovou baterií", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000022810-ariston-arksh-5u-eu-ohrivac-elektricky-beztlakovy-pod-umyvadlo-vc-baterie-3100659"),
    ("ARISTON ARKSH 5O EU zásobníkový ohřívač 5 l, elektrický, beztlakový, nad umyvadlo, s umyvadlovou baterií", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000022850-ariston-arksh-5o-eu-ohrivac-elektricky-beztlakovy-nad-umyvadlo-vc-baterie-3100658"),
    ("ARISTON QUADRIS 120 WIFI FR EU zásobníkový ohřívač 120 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000048962-ariston-quadris-120-wifi-fr-eu-3060883"),
    ("ARISTON QUADRIS 150 WIFI FR EU zásobníkový ohřívač 150 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000048964-ariston-quadris-150-wifi-fr-eu-3060884"),
    ("ARISTON VELIS PRO WIFI 80 EU zásobníkový ohřívač 65 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000119545-ariston-velis-pro-wifi-80-eu-ohrivac-elektricky-plochy-3100946"),
    ("ARISTON VELIS PRO WIFI 100 EU zásobníkový ohřívač 80 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000167439-ariston-velis-pro-wifi-100-eu-ohrivac-elektricky-plochy-3100947"),
    ("ARISTON VELIS PRO WIFI 50 EU zásobníkový ohřívač 45 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000119535-ariston-velis-pro-wifi-50-eu-ohrivac-elektricky-plochy-3100945"),
    ("ARISTON LYDOS HYBRID 80 WiFi zásobníkový ohřívač s funkcí TČ 1,2 kW, 80 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000167391-ariston-lydos-hybrid-80-wifi-ohrivac-elektricky-svisly-s-tepelnym-cerpadlem-3629064"),
    ("ARISTON LYDOS HYBRID 100 WiFi zásobníkový ohřívač s funkcí TČ 1,2 kW, 100 l, elektrický, závěsný", "Bojlery a ohřívače vody",
     "https://www.dek.cz/produkty/detail/6000167381-ariston-lydos-hybrid-100-wifi-ohrivac-elektricky-svisly-s-tepelnym-cerpadlem-3629065"),
    ("ATMOS DC 22 S kotel na dřevo 22 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000170960-atmos-dc-22-s-kotel-na-drevo"),
    ("ROJEK KTP 25 kotel na dřevo/uhlí 25 kW", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000384002-rojek-ktp-25-teplovodni-kotel-na-drevo-hnede-uhli"),
    ("ROJEK KTP 30 kotel na dřevo/uhlí 30 kW", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000384004-rojek-ktp-30-teplovodni-kotel-na-drevo-hnede-uhli"),
    ("ATMOS C 15 S KOMBI kotel na uhlí 16 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171108-atmos-c-15-s-kotel-kombi-na-hnede-uhli-drevo"),
    ("ATMOS C 18 S KOMBI kotel na uhlí 20 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171110-atmos-c-18-s-kotel-kombi-na-hnede-uhli-drevo-pravy"),
    ("ATMOS DC 15 GS kotel na dřevo 15 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171043-atmos-dc-15-gs-kotel-na-drevo-generator"),
    ("ATMOS DC 32 GS kotel na dřevo 32 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171060-atmos-dc-32-gs-kotel-na-drevo-generator"),
    ("ATMOS DC 40 SX kotel na dřevo 40 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171070-atmos-dc-40-sx-kotel-na-drevo"),
    ("ATMOS C 32 ST KOMBI kotel na uhlí 32 kW, zplyňovací, pravý", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171135-atmos-c-32-st-kotel-kombi-na-hnede-uhli-drevo-pravy"),
    ("ATMOS DC 50 S kotel na dřevo 49,9 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000170995-atmos-dc-50-s-kotel-na-drevo"),
    ("ATMOS DC 20 GS kotel na dřevo 20 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171045-atmos-dc-20-gs-kotel-na-drevo-generator"),
    ("ATMOS DC 25 GS kotel na dřevo 25 kW, zplyňovací", "Kotle na tuhá paliva",
     "https://www.dek.cz/produkty/detail/6000171050-atmos-dc-25-gs-kotel-na-drevo-generator"),
    ("WILO EXTRACT FIRST SE 303 ponorné čerpadlo, Hmax 37,1 m, s kabelem 10 m", "Kalová čerpadla",
     "https://www.dek.cz/produkty/detail/6000964376-6093857-wilo-extract-first-se-303-em-a"),
    ("WILO EXTRACT FIRST SE 304 ponorné čerpadlo, Hmax 47,7 m, s kabelem 10 m", "Kalová čerpadla",
     "https://www.dek.cz/produkty/detail/6000964378-6093858-wilo-extract-first-se-304-em-a"),
    ("GROHE EUROSMART sprchová podomítková baterie, chrom", "Sprchové baterie",
     "https://www.dek.cz/produkty/detail/6000007110-g33300002-vanova-nastenna-baterie-grohe-eurosmart"),
]

CARD_RE_TITLE = re.compile(r'comd-product-view--long__title"[^>]*>\s*([^<]+?)\s*</a>|<h1[^>]*>\s*([^<]+?)\s*</h1>', re.S)
PRICE_RE = re.compile(r'price-vat[^"]*">\s*<div>([\d\s\xa0]+)<span>,(\d+)</span>', re.S)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def scrape_product(url):
    html = _fetch(url)
    price_m = PRICE_RE.search(html)
    if not price_m:
        return None, None
    whole = re.sub(r"[\s\xa0]+", "", price_m.group(1))
    price_czk = float(whole) + float(price_m.group(2)) / 100
    title_m = re.search(r'<h1[^>]*>\s*([^<]+?)\s*</h1>', html, re.S)
    dek_name = title_m.group(1).strip() if title_m else None
    return dek_name, price_czk


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true")
    grp.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM remeslo_price_sources WHERE supplier_name=%s", (SUPPLIER_NAME,))
            row = cur.fetchone()
            if not row:
                print(f"CHYBA: zdroj '{SUPPLIER_NAME}' není v remeslo_price_sources.")
                sys.exit(1)
            source_id = row["id"]
    finally:
        conn.close()

    written = 0
    for existing_name, cat_name, url in PRODUCTS:
        dek_name, price_czk = scrape_product(url)
        if price_czk is None:
            print(f"[POZOR] Cena nenalezena: {url}")
            time.sleep(10)
            continue
        print(f"{existing_name[:55]:55s} <-> {(dek_name or '?')[:55]:55s} {price_czk:>10.2f} Kč")

        for attempt in range(1, 4):
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM remeslo_material_categories WHERE name=%s", (cat_name,))
                    cat_row = cur.fetchone()
                    if not cat_row:
                        print(f"  [POZOR] kategorie '{cat_name}' neexistuje, přeskakuji.")
                        break
                    category_id = cat_row["id"]
                    if args.apply:
                        cur.execute(
                            "DELETE FROM remeslo_material_prices "
                            "WHERE category_id=%s AND source_id=%s AND product_url=%s",
                            (category_id, source_id, url),
                        )
                        cur.execute(
                            "INSERT INTO remeslo_material_prices "
                            "(category_id, source_id, product_name, price_czk, product_url) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (category_id, source_id, dek_name or existing_name, price_czk, url),
                        )
                        written += 1
                conn.commit()
                break
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
                print(f"  [pokus {attempt}/3] DB spojení zdrhlo ({e}), zkouším znovu...")
                if attempt == 3:
                    raise
                time.sleep(5)
            finally:
                conn.close()
        time.sleep(10)

    if args.apply:
        print(f"\nOK - zapsáno {written} přesných shod.")
    else:
        print("\n[kontrola] Nic nezapsáno (dry-run).")


if __name__ == "__main__":
    main()
