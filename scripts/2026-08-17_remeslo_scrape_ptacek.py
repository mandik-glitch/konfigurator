#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z Ptáček-shop.cz pro modul 1
Řemesla (srovnávač cen materiálu, dle profese) - bot10, 2026-08-17.

Kontext: REMESLO_KONCEPT.md, "Co jde první implementovat" - Robert
(přes bot3) zvolil pilotní profesi instalatér (voda/topení) a
schválil výběr 2 dodavatelů (Ptáček-shop.cz, Aquatopshop.cz) podle
5 kritérií (velikost firmy, celostátní dosah, strukturovaný veřejný
ceník, relevance k profesi, šíře sortimentu - viz koncept). Tenhle
skript řeší PRVNÍHO z nich; Aquatopshop.cz přijde v samostatném
skriptu (jiná HTML struktura, jiný parser - stejný princip jako
Dogus skript potřeboval 2 parsery i pro jednoho dodavatele).

Rozsah (Robert: "jen hlavní sortiment podle profese, NE celý
katalog"): scrapuje jen VYBRANÉ kategorie relevantní instalatérské
profesi. Seznam kategorií je v `CATEGORIES` níž - rozšiřuje se ručně.

Rozšíření 2026-08-17 (Robert, přes bot3: "pořádně rozjet", cíl řádu
stovek položek): `CATEGORIES` rozšířena z 1 na ~2 tucty kategorií
napříč celým hlavním sortimentem instalatéra (ohřev vody, kotle,
tepelná čerpadla, radiátory + příslušenství, čerpadla, tlakové
nádoby, úprava vody, baterie, sanitární keramika, předstěnové
moduly, sprchové příslušenství) + přidána stránkování (`MAX_PAGES`
na kategorii, `?from=N` - ověřeno živě v HTML paginaci, není v
robots.txt disallow listu).

DŮLEŽITÉ ZJIŠTĚNÍ (2026-08-17): veřejný retail e-shop ptacek-shop.cz
NEMÁ browsovatelné kategorie pro trubky/tvarovky/armatury/spojovací
materiál/těsnění (ověřeno - v sitemap_product_categories.xml žádná
taková kategorie není). Firemní B2B velkoobchodní portál
(eshop.ptacek.cz) tohle sortiment má, ale je za přihlášením
(redirect na /prihlaseni) - NEPŘISTUPOVÁNO (žádné vytváření/obcházení
B2B účtu). Tahle mezera je vědomě ponechána na Aquatopshop.cz (ten
naopak trubky/tvarovky/armatury veřejně nabízí), ne řešena falešným
zdrojem dat zde.

Struktura stránky (ověřeno živě 2026-08-17, statické server-rendered
HTML, žádný headless prohlížeč potřeba):
    <div class="productCard" id="snippet-productList-main-productCard-<ID>-productCard">
        ...
        <h3 class="productCard__title"><a href="/relativni-url" title="Nazev">Nazev</a></h3>
        ...
        <div class="productCard__code">Kód: <cislo></div>
        ...
        <div class="price__base"> 10 913 Kč </div>   -- CENA S DPH (stránka
            sama uvádí "Všechny ceny uvedeny včetně DPH")
    </div>

Idempotence: PŘEPISUJE (DELETE+INSERT) ceny daného zdroje+kategorie
při každém běhu, ne postupné přidávání duplicit - cena je "aktuální
stav ke dni scrapu", ne historie (na rozdíl od `dogus_list_price_usd`
sloupce, který drží jen POSLEDNÍ hodnotu na produktu samotném; tady
je to samostatná řádková tabulka, historie by šla přidat později
přidáním `is_current`/archivace, teď zjednodušeno).

Bez --apply jde o READ-ONLY dry-run (jen vypíše, co by se zapsalo).

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_ptacek.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_ptacek.py --apply
"""
import argparse
import datetime
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

SUPPLIER_NAME = "Ptáček-shop.cz"
BASE_URL = "https://www.ptacek-shop.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"
# Strop stranek na kategorii - i u velkych kategorii (kotle 152ks,
# cerpadla 178ks) staci pro "hlavni sortiment" rozumny vyber, ne
# uplne vsechno do posledni podstranky (Robert: "jen hlavni sortiment,
# ne cely katalog"). 18 polozek/stranka * 5 = az 90 na kategorii.
MAX_PAGES = 5

# Kategorie relevantní pilotní profesi (instalatér, voda/topení) -
# (nazev_kategorie_v_DB, unit, url_cesta). Rozsireno 2026-08-17 (Robert:
# "poradne rozjet", cil radu stovek polozek) na cely hlavni sortiment
# ohrevu vody/topeni/sanitarni techniky, ktery ptacek-shop.cz verejne
# nabizi (trubky/tvarovky/armatury v jejich VEREJNEM katalogu NEJSOU,
# viz docstring modulu vyse - to pokryva Aquatopshop.cz). "Tepelna
# cerpadla" (/tepelna-cerpadla) zkousena a VYNECHANA - stranka existuje
# (H1 "Tepelna cerpadla vzduch - voda"), ale 0 productCard (zadny
# skutecny vypis produktu, zrejme prodej jen pres poptavku/konzultaci).
CATEGORIES = [
    ("Domácí vodárna", "ks", "/domaci-vodarny"),
    ("Bojlery a ohřívače vody", "ks", "/bojlery-a-ohrivace-vody"),
    ("Kotle", "ks", "/kotle"),
    ("Elektrické kotle", "ks", "/elektricke-kotle"),
    ("Deskové radiátory", "ks", "/deskove-radiatory"),
    ("Radiátory", "ks", "/radiatory"),
    ("Radiátorové ventily", "ks", "/ventily-radiatorove"),
    ("Termostatické hlavice", "ks", "/termostaticke-hlavice"),
    ("Příslušenství k radiátorům", "ks", "/prislusenstvi-k-radiatorum"),
    ("Čerpadla", "ks", "/cerpadla"),
    ("Oběhová čerpadla", "ks", "/obehova-cerpadla"),
    ("Ponorná čerpadla", "ks", "/ponorna-cerpadla"),
    ("Kalová čerpadla", "ks", "/kalova-cerpadla"),
    ("Tlakové nádoby", "ks", "/tlakove-nadoby"),
    ("Úprava vody", "ks", "/uprava-vody"),
    ("Vodovodní baterie", "ks", "/vodovodni-baterie"),
    ("Umyvadlové baterie", "ks", "/umyvadlove-baterie"),
    ("Vanové baterie", "ks", "/vanove-baterie"),
    ("Sprchové baterie", "ks", "/sprchove-baterie"),
    ("Sanitární keramika", "ks", "/sanitarni-keramika"),
    ("Umyvadla", "ks", "/umyvadla"),
    ("WC a toalety", "ks", "/wc-toalety"),
    ("WC sedátka", "ks", "/wc-sedatka"),
    ("Vany", "ks", "/vany"),
    ("Předstěnové moduly", "ks", "/predstenove-moduly"),
    ("Sprchové hadice", "ks", "/sprchove-hadice"),
    ("Sprchová ramena", "ks", "/sprchova-ramena"),
]

PRODUCT_CARD_RE = re.compile(
    r'<div class="productCard" id="snippet-productList-main-productCard-\d+-productCard">(.*?)'
    r'(?=<div class="productCard" id="snippet-productList-main-productCard-\d+-productCard">|'
    r'<div id="snippet--productListAppend-more"|\Z)',
    re.S,
)
TITLE_RE = re.compile(r'productCard__title">\s*<a href="([^"]+)"[^>]*>([^<]+)</a>', re.S)
PRICE_RE = re.compile(r'price__base">\s*([\d\s]+)\s*Kč', re.S)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_products(html):
    items = []
    for card in PRODUCT_CARD_RE.findall(html):
        title_m = TITLE_RE.search(card)
        price_m = PRICE_RE.search(card)
        if not title_m or not price_m:
            continue
        rel_url, name = title_m.groups()
        price_raw = price_m.group(1).replace("\xa0", " ")
        price_czk = float(re.sub(r"\s+", "", price_raw))
        full_url = rel_url if rel_url.startswith("http") else BASE_URL + rel_url
        items.append((name.strip(), price_czk, full_url))
    return items


def scrape_category(url_path):
    """Vraci list (nazev, cena_czk, plna_url) pro danou kategorii,
    az MAX_PAGES stranek vypisu (?from=N pagination - overeno zive,
    neni v robots.txt disallow listu). Zastavi se driv, pokud nejaka
    stranka nema zadne polozky (kratsi kategorie)."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        url = BASE_URL + url_path if page == 1 else f"{BASE_URL}{url_path}?from={page}"
        html = _fetch(url)
        page_items = _parse_products(html)
        if not page_items:
            break
        items.extend(page_items)
        if page < MAX_PAGES:
            time.sleep(15)
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
            for cat_name, unit, url_path in CATEGORIES:
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

                print(f"\n== {cat_name} ({url_path}) ==")
                items = scrape_category(url_path)
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
                # robots.txt (ptacek-shop.cz) vyslovne uvadi "Crawl-delay: 15" -
                # dodrzujeme presne, ne kratsi "slusnou" hodnotu od oka (mezi
                # kategoriemi - mezi strankami stejne kategorie viz
                # scrape_category() vyse).
                time.sleep(15)

            if args.apply:
                conn.commit()
                print(f"\nOK - zapsáno {total_written} cenových záznamů.")
            else:
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
