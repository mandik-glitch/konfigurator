#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z TZBeshop.cz pro modul 1 Řemesla
(srovnávač cen materiálu, dle profese) - bot23, 2026-08-17.

Druhý ze 2 nových dodavatelů (viz 2026-08-17_remeslo_scrape_heckl.py
pro první a plný kontext výběru - Robert přes bot3: "rozšířit z 2 na
cca 10 dodavatelů", 5 kritérií v REMESLO_KONCEPT.md). TZBeshop.cz =
TZBcentrum s.r.o. (Brno), veřejný e-shop bez přihlášení, celostátní
rozvoz ČR+SR - vybrán mj. proto, že (stejně jako HECKL) pokrývá
SOUČASNĚ trubky/fitinky/armatury I kotle/radiátory, tedy doplňuje
mezeru po obou stávajících zdrojích (Ptáček nemá trubky/tvarovky,
Aquatop nemá kotle/radiátory).

Struktura stránky (ověřeno živě 2026-08-17): statické server-rendered
HTML, žádný JSON-LD produktový blok (jen BreadcrumbList/LocalBusiness
metadata - na rozdíl od Aquatopshop.cz), nutno parsovat HTML karty
(stejný princip jako Ptáček/HECKL). Karta produktu:
    <div class="ai-ProductItem">
      ...
      <a href="produkt-slug" class="itemName" title="Název produktu">
        Název produktu
      </a>
      ...
      <span class="price">857,00 Kč</span>
      <span class="withDPH">s DPH</span>

Cena je vždy S DPH (`<span class="withDPH">s DPH</span>` u každé
položky, ověřeno živě) - konzistentní s Ptáček/Aquatop/HECKL.

DŮLEŽITÉ (bez stránkování): na rozdíl od Ptáčka/Aquatopu/HECKL nemá
TZBeshop.cz jednoduché `?page=N`/`?from=N` stránkování v generovaném
HTML - výpis kategorie se dál stránkuje přes AJAX (`aivPagWrapper`
element plněný JS), který tenhle skript (bez headless prohlížeče,
stejný princip jako ostatní skripty v projektu) nevolá. Skript proto
čte JEN PRVNÍ stránku výpisu každé kategorie (typicky 24 položek) -
v souladu s "hlavní sortiment, ne celý katalog" (REMESLO_KONCEPT.md),
ne technický nedostatek k dořešení.

robots.txt (tzbeshop.cz): žádný Crawl-delay, jen Disallow na
/objednavka, /registrace(-default), /_admin, /_service - kategorie
(`/produkty/vypis/...` zde není použito, používá se holý slug jako
`/kotle`) nejsou v disallow listu. Použit konzervativní 10s odstup
mezi kategoriemi (stejná úvaha jako u Aquatopu).

Idempotence: DELETE+INSERT při každém běhu (aktuální stav ke dni
scrapu, ne historie) - stejně jako u ostatních zdrojů.

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_tzbeshop.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_tzbeshop.py --apply
"""
import argparse
import datetime
import html as html_module
import os
import re
import sys
import time
import urllib.request

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
import remeslo_price_history  # noqa: E402

SUPPLIER_NAME = "TZBeshop.cz"
BASE_URL = "https://www.tzbeshop.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"

# Kategorie relevantní pilotní profesi (instalatér, voda/topení) -
# (nazev_kategorie_v_DB, unit, url_slug). Stejné názvy kategorií jako
# Ptáček/Aquatop/HECKL skripty, kde se sortiment překrývá (ať jde
# srovnávat napříč zdroji ve stejné remeslo_material_categories
# řádce). Každý slug ověřen živě (HTTP 200 + karty s cenou) 2026-08-17.
CATEGORIES = [
    ("Kotle", "ks", "kotle"),
    ("Radiátory", "ks", "radiatory"),
    ("Bojlery a ohřívače vody", "ks", "ohrivace-vody"),
    ("Tlakové nádoby", "ks", "expanzni-nadoby"),
    ("Topidla", "ks", "topidla"),
    ("Podlahové vytápění", "ks", "podlahove-vytapeni"),
    ("Armatury", "ks", "armatury-voda-topeni"),
    ("Fitinky (tvarovky)", "ks", "fitinky-tvarovky-"),
    ("Připojovací materiál", "ks", "pripojovaci-material"),
    ("Trubky/rozvody voda-topení", "ks", "rozvody-voda-topeni"),
    ("Sifony, vpustě, žlaby", "ks", "sifony-vpuste-zlaby"),
    ("Odpady a kanalizace", "ks", "odpady-a-kanalizace"),
    ("Čerpadla", "ks", "cerpadla-a-vodarny"),
    ("Úprava vody", "ks", "filtrace-a-uprava-vody"),
    ("Izolace potrubí", "ks", "izolace-potrubi"),
    ("Upevňovací technika", "ks", "upevnovaci-technika"),
    ("Těsnící materiál", "ks", "tesnici-materialy"),
    ("Vodovodní baterie", "ks", "vodovodni-baterie"),
    ("Sanitární keramika", "ks", "sanitarni-keramika"),
    ("Sprchový program", "ks", "sprchovy-program"),
    ("Splachovací systémy", "ks", "splachovaci-systemy"),
    ("Dřezy a výlevky", "ks", "drezy-a-vylevky"),
]

CARD_SPLIT = "ai-ProductItem"
NAME_HREF_RE = re.compile(r'<a href="([^"]+)" class="itemName" title="([^"]+)"', re.S)
PRICE_RE = re.compile(r'<span class="price">([\d\s]+,\d{2})\s*Kč</span>', re.S)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_products(html_text):
    items = []
    for card in html_text.split(CARD_SPLIT)[1:]:
        nh_m = NAME_HREF_RE.search(card)
        price_m = PRICE_RE.search(card)
        if not nh_m or not price_m:
            continue
        rel_url, name = nh_m.groups()
        price_raw = price_m.group(1).replace("\xa0", " ").replace(" ", "")
        price_czk = float(price_raw.replace(",", "."))
        full_url = rel_url if rel_url.startswith("http") else f"{BASE_URL}/{rel_url}"
        items.append((html_module.unescape(name).strip(), price_czk, full_url))
    return items


def scrape_category(slug):
    """Vraci list (nazev, cena_czk, plna_url) - jen PRVNI stranka
    vypisu (viz docstring modulu - AJAX strankovani zde neni cteno)."""
    html_text = _fetch(f"{BASE_URL}/{slug}")
    return _parse_products(html_text)


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true", help="jen vypsat, nic nezapisovat")
    grp.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    args = ap.parse_args()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM remeslo_price_sources WHERE supplier_name=%s", (SUPPLIER_NAME,))
            source_row = cur.fetchone()
            if not source_row:
                print(f"CHYBA: zdroj '{SUPPLIER_NAME}' není v remeslo_price_sources (migrace neaplikována?).")
                sys.exit(1)
            source_id = source_row["id"]

            cur.execute("SELECT id FROM remeslo_professions WHERE slug=%s", (PROFESSION_SLUG,))
            profession_row = cur.fetchone()
            if not profession_row:
                print(f"CHYBA: profese '{PROFESSION_SLUG}' není v remeslo_professions.")
                sys.exit(1)
            profession_id = profession_row["id"]

            total_written = 0
            for cat_name, unit, slug in CATEGORIES:
                cur.execute("SELECT id FROM remeslo_material_categories WHERE name=%s", (cat_name,))
                cat_row = cur.fetchone()
                if not cat_row:
                    if args.apply:
                        cur.execute(
                            "INSERT INTO remeslo_material_categories (name, unit) VALUES (%s,%s)",
                            (cat_name, unit),
                        )
                        category_id = cur.lastrowid
                        print(f"Založena nová kategorie: {cat_name} (id={category_id})")
                    else:
                        print(f"[kontrola] Kategorie '{cat_name}' zatím neexistuje, založila by se.")
                        category_id = None
                else:
                    category_id = cat_row["id"]

                print(f"\n== {cat_name} ({slug}) ==")
                items = scrape_category(slug)
                print(f"Nalezeno {len(items)} položek (1. stránka výpisu).")
                for name, price_czk, url in items[:5]:
                    print(f"  {name[:70]:70s} {price_czk:>10.2f} Kč")
                if len(items) > 5:
                    print(f"  ... a dalších {len(items) - 5}")

                if args.apply and category_id:
                    cur.execute(
                        "INSERT IGNORE INTO remeslo_material_category_professions "
                        "(category_id, profession_id) VALUES (%s,%s)",
                        (category_id, profession_id),
                    )
                    # Historie ceny (bot10, 2026-08-20) - PRED smazanim
                    # stareho stavu zachytit puvodni ceny, at je s cim
                    # porovnat novy scrape. Zapisuje se JEN kdyz se cena
                    # SKUTECNE zmenila (viz remeslo_price_history).
                    cur.execute(
                        "SELECT product_url, price_czk FROM remeslo_material_prices "
                        "WHERE category_id=%s AND source_id=%s",
                        (category_id, source_id),
                    )
                    old_prices = {r["product_url"]: r["price_czk"] for r in cur.fetchall()}
                    changed = remeslo_price_history.record_price_changes_batch(
                        cur, source_id, old_prices, items, datetime.datetime.now())
                    if changed:
                        print(f"  → {changed} cen(y) se zmenilo, zapsáno do historie")
                    cur.execute(
                        "DELETE FROM remeslo_material_prices WHERE category_id=%s AND source_id=%s",
                        (category_id, source_id),
                    )
                    for name, price_czk, url in items:
                        cur.execute(
                            "INSERT INTO remeslo_material_prices "
                            "(category_id, source_id, product_name, price_czk, product_url) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (category_id, source_id, name, price_czk, url),
                        )
                    total_written += len(items)
                # zadny Crawl-delay v robots.txt - konzervativni vlastni
                # odstup mezi kategoriemi (stejna uvaha jako Aquatop).
                time.sleep(10)

            if args.apply:
                conn.commit()
                print(f"\nOK - zapsáno {total_written} cenových záznamů.")
            else:
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
