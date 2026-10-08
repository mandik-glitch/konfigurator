#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z shop.heckl.cz pro modul 1
Řemesla (srovnávač cen materiálu, dle profese) - bot23, 2026-08-17.

Kontext: Robert (přes bot3) chce rozšířit ze 2 na cca 10 dodavatelů
(viz REMESLO_KONCEPT.md pro 5 kritérií výběru + celý kontext modulu).
HECKL vybrán jako jeden ze 2 nových dodavatelů (druhý viz
2026-08-17_remeslo_scrape_tzbeshop.py) - česká rodinná firma 30+ let,
vlastní výroba (Rumburk) + centrála (Kralupy n. Vltavou) + 13+
regionálních prodejen/velkoskladů napříč ČR, veřejné ceny bez
přihlášení. Souběžně bot11 dělá totéž s DEK.cz/SIKO Koupelny -
koordinace přes TASKS.md, ať nevznikne duplicitní výběr.

Struktura stránky (ověřeno živě 2026-08-17, statické server-rendered
HTML): kategorie na `shop.heckl.cz/<slug>` (krátké slugy ze
sitemap_1.xml, ne vnořená `/kategorie/.../.../` cesta - obě fungují,
sitemap dává kratší kanonickou verzi), stránkování `?page=N`
(potvrzeno v `page-link`/`pagination` markupu). Karta produktu je
oddělená HTML komentářem `<!-- Item -->`:
    <!-- Item -->
    <div class="col-sm-6 col-md-4">
      ...
      <h3 class="mb-1"><a href="produkt-slug" ...>
        <span class="animate-target">Název produktu</span>
      </a></h3>
      ...
      <div class="price-primary-color">...
        <span style="...">Vaše cena:</span> <span>216&nbsp;Kč/ks</span>
        NEBO (položky s desetinami): <span>41,<small>08</small>&nbsp;Kč/m</span>
      </div>

DŮLEŽITÉ (cena s/bez DPH): stránka má JS přepínač "Ceny bez DPH" /
"Ceny s DPH" (`#vatSwitch`), ale úvodní server-rendered HTML (bez
spuštění JS, jak tenhle skript stránku čte) odpovídá stavu
`checked="checked"` atributu, a ten je ve zdrojovém HTML vždy
přítomný - z JS `const withVat = this.checked;` plyne, že
`checked=true` = zobrazeny ceny S DPH. Přepočet na jiný režim (bez
DPH) se děje AŽ při `change` eventu (uživatelský klik), ne automaticky
při načtení stránky - tenhle skript tedy čte ceny S DPH, stejně jako
Ptáček/Aquatop/TZBeshop (konzistence napříč zdroji pro srovnávač).

robots.txt (shop.heckl.cz) je prázdný (žádný Disallow, žádný
Crawl-delay, ověřeno živě) - použit konzervativní 12s odstup mezi
kategoriemi/stránkami (o něco kratší než Ptáčkových explicitních 15s,
delší než Aquatopových 10s - žádná číslem podložená hodnota od webu).

Idempotence: stejně jako u Ptáčka/Aquatopu - DELETE+INSERT při
každém běhu (aktuální stav ke dni scrapu, ne historie).

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_heckl.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_heckl.py --apply
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

SUPPLIER_NAME = "HECKL"
BASE_URL = "https://shop.heckl.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"
# Stejná úvaha jako u Ptáčka/Aquatopu - "hlavní sortiment", ne celý
# katalog (Robert). 18 položek/stránka * 5 = až 90 na kategorii.
MAX_PAGES = 5

# Kategorie relevantní pilotní profesi (instalatér, voda/topení) -
# (nazev_kategorie_v_DB, unit, url_slug). MUSÍ používat stejné názvy
# kategorií jako Ptáček/Aquatop skripty, kde se sortiment překrývá
# (aby šlo srovnávat napříč zdroji ve stejné remeslo_material_categories
# řádce - viz jejich komentáře). Každý slug ověřen živě (HTTP 200 +
# přítomné karty produktů s cenou) před přidáním sem.
CATEGORIES = [
    ("Kotle", "ks", "kotle"),
    ("Radiátory", "ks", "radiatory-a-konvektory"),
    ("Radiátorové ventily", "ks", "radiatorove-ventily"),
    ("Tlakové nádoby", "ks", "expanzni-nadoby"),
    ("Bojlery a ohřívače vody", "ks", "ohrivace-vody-a-zasobniky"),
    ("Domácí vodárna", "ks", "domaci-vodarny"),
    ("Čerpadla", "ks", "cerpadla"),
    ("PPR trubky a tvarovky", "ks", "ppr-trubky-tvarovky"),
    ("Trubky", "ks", "trubky-2"),
    ("Trubky a tvarovky PP", "ks", "trubky-a-tvarovky-pp"),
    ("Mosazné fitinky", "ks", "fitinky-tvarovky"),
    ("Mosazné fitinky pro plyn", "ks", "mosazne-fitinky"),
    ("Mosazná kolena", "ks", "kolena"),
    ("Kulové kohouty a ventily", "ks", "kulove-kohouty-3"),
    ("Ventily", "ks", "ventily-6"),
    ("Rohové ventily", "ks", "rohove-ventily-2"),
    ("Filtry, koše, klapky", "ks", "filtry-kose-klapky"),
    ("Vodovodní baterie", "ks", "vodovodni-baterie"),
    ("Sprchové baterie", "ks", "sprchove-baterie"),
    ("Vanové baterie", "ks", "vanove-baterie"),
    ("Umyvadlové baterie", "ks", "umyvadlove-baterie"),
    ("Dřezové baterie", "ks", "drezove-baterie"),
    ("Spojovací materiál", "ks", "spojovaci-material"),
    ("Těsnící materiál", "ks", "tesneni"),
    ("Vodoměry", "ks", "vodomery"),
]

CARD_SPLIT = "<!-- Item -->"
NAME_HREF_RE = re.compile(
    r'<a href="([^"]+)"[^>]*>\s*<span class="animate-target">([^<]+)</span>', re.S
)
# Cena bud cele cislo ("216&nbsp;Kč/ks") nebo s desetinami rozdelenymi
# do <small> ("41,<small>08</small>&nbsp;Kč/m") - viz docstring vyse.
PRICE_RE = re.compile(
    r'Vaše cena:</span>\s*<span>([\d\s&nbsp;]+?)(?:,?<small>(\d+)</small>)?(?:&nbsp;)?\s*Kč', re.S
)


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
        whole = price_m.group(1).replace("&nbsp;", "").replace(" ", "").strip()
        dec = price_m.group(2) or "00"
        try:
            price_czk = float(f"{whole}.{dec}")
        except ValueError:
            continue
        full_url = rel_url if rel_url.startswith("http") else f"{BASE_URL}/{rel_url}"
        items.append((html_module.unescape(name).strip(), price_czk, full_url))
    return items


def scrape_category(slug):
    """Vraci list (nazev, cena_czk, plna_url), az MAX_PAGES stranek
    (?page=N, 0-indexovano dle pozorovaneho markupu 'page=0'/'page=2').
    Zastavi se driv, pokud stranka nema zadne polozky."""
    items = []
    for page in range(0, MAX_PAGES):
        url = f"{BASE_URL}/{slug}" if page == 0 else f"{BASE_URL}/{slug}?page={page}"
        html_text = _fetch(url)
        page_items = _parse_products(html_text)
        if not page_items:
            break
        items.extend(page_items)
        if page < MAX_PAGES - 1:
            time.sleep(12)
    return items


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
                print(f"Nalezeno {len(items)} položek (až {MAX_PAGES} stránek výpisu).")
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
                # zadny Crawl-delay v robots.txt (prazdny soubor, overeno
                # zive) - konzervativni vlastni odstup mezi kategoriemi.
                time.sleep(12)

            if args.apply:
                conn.commit()
                print(f"\nOK - zapsáno {total_written} cenových záznamů.")
            else:
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
