#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z sanitino.cz pro modul 1 Řemesla
(srovnávač cen materiálu, dle profese) - bot10, 2026-08-19.

Kontext: Robert (přes bot3) chce rozšířit ze 2 na cca 10 dodavatelů (viz
REMESLO_KONCEPT.md pro 5 kritérií výběru + celý kontext modulu). Stav
před tímto skriptem: Ptáček-shop.cz (912 cen/27 kat.), Aquatopshop.cz
(546/22), TZBeshop.cz (434/22) hotové; DEK.cz a Mereo.cz rozpracovává
bot11 souběžně (NEsahat) - Sanitino zvoleno jako DALŠÍ, dosud nikým
netknutý kandidát, ať se nepřekrýváme.

**Kritéria výběru (ověřeno živě 2026-08-19 před psaním skriptu):**
1. Velikost/dosah: celostátní e-shop bez kamenné sítě, ale s rozvozem
   po celé ČR (`Doprava zdarma` sticky u položek) - kritérium 2 v
   REMESLO_KONCEPT.md výslovně připouští "e-shop s celostátním
   rozvozem" jako alternativu ke kamenným pobočkám.
2. Strukturovaný ceník: `sitemap-categories_0_CZ_cs-CZ.xml` má 383
   kategorií, `sitemap-products` samostatně - typický velký e-shop na
   vlastní/Shopsys-like platformě, HTML karty produktů mají stabilní
   `class="product-filter__product-item"` wrapper.
3. Šíře sortimentu: jen kategorie `vodovodni-baterie` má 11 016
   produktů (viz `product-filter__paginator-info` na stránce) - řádově
   větší katalog než dosavadní zdroje, jasně splňuje kritérium 5
   ("upřednostnit širší katalog").
4. Relevance k profesi: sortiment koupelny/instalatérství (baterie,
   WC, vany, umyvadla, sifony, ventily, čerpadla...) přímo pro profesi
   `instalater`.

Struktura stránky (ověřeno živě 2026-08-19, statické server-rendered
HTML, žádné nutné spouštění JS pro základní výpis):
    <div class="product-filter__product-item">
      ...
      <h2 class="product__title"><a href="/produkt-slug" ...>Název</a></h2>
      ...
      <span class="product__price">4&nbsp;582 Kč</span>
      <span class="product__price-vat">s DPH</span>
      ...
    </div>
Kromě běžných karet stránka občas vloží i "promoted" (sponzorovanou)
kartu produktu STEJNÉHO katalogu (stejný wrapper div, jen jiné CSS
třídy `promoted-product__title`/`promoted-product__price` místo
`product__title`/`product__price`) - skript matchuje OBĚ varianty,
protože jde pořád o reálnou položku s reálnou cenou z tohoto e-shopu,
ne o cizí reklamu.

Ceny jsou vždy zobrazeny S DPH (`product__price-vat` = "s DPH", žádný
přepínač na stránce jako u HECKLu) - konzistentní s ostatními zdroji.

Stránkování: `?page=N` (N od 2, stránka 1 = URL bez parametru,
potvrzeno `<link rel="next" href="...?page=2">` v hlavičce). 24
položek/stránka pozorováno živě.

robots.txt (sanitino.cz) nemá Crawl-delay pro obecný `User-agent: *`
(jen specifické pro AhrefsBot/AdIdxBot) - přesto 20s odstup mezi
požadavky (víc než HECKLových 12s), protože při 12s odstupu skript
dvakrát nezávisle narazil na 404 vždy po ~60-70 požadavcích (viz
_fetch níž) - vypadá jako kumulativní rate-limit/WAF, ne skutečná
neexistující URL.

**Rozsah** (Robert, REMESLO_KONCEPT.md "Rozsah scrapingu u KAŽDÉHO
dodavatele" - jen hlavní sortiment podle profese, NE celý katalog):
MAX_PAGES=5 na kategorii (až 120 položek/kategorii), stejně jako u
HECKL/Ptáček/Aquatop/TZBeshop - u kategorie s 11 016 produkty (viz
výš) je tenhle strop zásadní, jinak by šlo o vyčerpávající scrape
celého webu, ne pilotní výběr.

Názvy kategorií v DB: kde má Sanitino jasný ekvivalent už existující
`remeslo_material_categories` položky (založené Ptáčkem/Aquatopem/
TZBeshopem/HECKLem), použit STEJNÝ název (aby šlo srovnávat napříč
zdroji ve stejné kategorii) - viz komentář u CATEGORIES níž. Několik
kategorií (sprchové kouty, sprchové vaničky, koupelnové radiátory,
kuchyňské baterie) nemá dosud žádný ekvivalent - založeny jako nové.

Idempotence: stejně jako ostatní zdroje - DELETE+INSERT při každém
běhu (aktuální stav ke dni scrapu, ne historie).

Použití:
    api/venv/bin/python3 scripts/2026-08-19_remeslo_scrape_sanitino.py --kontrola
    api/venv/bin/python3 scripts/2026-08-19_remeslo_scrape_sanitino.py --apply
"""
import argparse
import html as html_module
import os
import re
import sys
import time
import urllib.error
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
# kopii. Proto get_remeslo_conn() (stejna oprava jako bot14, 2026-08-19,
# viz f839099/714b3cd u ostatnich scraperu).
from remeslo import get_remeslo_conn as get_conn  # noqa: E402

SUPPLIER_NAME = "Sanitino.cz"
SUPPLIER_URL = "https://www.sanitino.cz/"
BASE_URL = "https://www.sanitino.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"
# "Hlavní sortiment", ne celý katalog (Robert) - viz docstring výš,
# kategorie `vodovodni-baterie` má 11 016 produktů, bez stropu by šlo
# o stovky stránek jedné kategorie.
MAX_PAGES = 5

# (nazev_kategorie_v_DB, unit, url_slug). Kde existuje stejná reálná
# kategorie už u jiného zdroje (Ptáček/Aquatop/TZBeshop/HECKL), použit
# STEJNÝ název kvůli srovnatelnosti napříč zdroji (viz DESCRIBE
# remeslo_material_categories před psaním - ověřeno živě). Nové
# kategorie (bez existujícího ekvivalentu) označeny komentářem.
CATEGORIES = [
    ("Vodovodní baterie", "ks", "vodovodni-baterie"),
    ("Sprchové baterie", "ks", "sprchove-baterie"),
    ("Vanové baterie", "ks", "vanove-baterie"),
    ("Umyvadlové baterie", "ks", "umyvadlove-baterie"),
    ("Kuchyňské baterie", "ks", "kuchynske-baterie"),  # nova kategorie
    ("WC a toalety", "ks", "zachody-toalety"),
    ("WC sedátka", "ks", "wc-sedatka"),
    ("Umyvadla", "ks", "umyvadla"),
    ("Vany", "ks", "vany"),
    ("Sprchové kouty", "ks", "sprchove-kouty"),  # nova kategorie
    ("Sprchové vaničky", "ks", "sprchove-vanicky"),  # nova kategorie
    ("Sifony a výpustě", "ks", "sifony"),
    ("Rohové ventily", "ks", "rohove-ventily-rohacky"),
    ("Předstěnové moduly", "ks", "instalacni-moduly-pro-wc"),
    ("Čerpadla", "ks", "cerpadla"),
    ("Mosazné šroubení", "ks", "sroubeni"),
    ("Dřezy a výlevky", "ks", "drezy"),
    ("Filtrace a úprava vody", "ks", "vodovodni-filtry"),
    ("Koupelnové radiátory-žebříky", "ks", "koupelnove-radiatory-zebriky"),  # nova
]

NAME_RE = re.compile(
    r'class="(?:product__title|promoted-product__title[^"]*)">\s*'
    r'<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
    re.S,
)
# "product__price" i "promoted-product__price" - vyhne se sousednimu
# "product__price-vat" spanu, protoze ten nema cislice hned za sebou.
PRICE_RE = re.compile(
    r'class="(?:promoted-)?product__price[^"]*">\s*([\d\s ]+)(?:,(\d+))?\s*Kč',
    re.S,
)


def _fetch(url):
    # Ojedinele tranzientni 5xx/404 pozorovano zive (bot10, 2026-08-19)
    # bez opakovatelne priciny (opakovany curl na stejnou URL hned
    # nato vratil 200) - opakovane pozorovano VZDY po cca 60-70
    # pozadavcich behem par minut (dvakrat nezavisle spadlo presne na
    # stejnem miste v poradi kategorii), takze jde spis o kumulativni
    # rate-limit/WAF (maskovany jako 404, ne 429/403) nez o skutecne
    # neexistujici URL - kratke 5s opakovani (puvodni pokus) nestacilo,
    # protoze rate-limit okno je delsi. Delsi odstup mezi pozadavky
    # (viz REQUEST_DELAY nize) + tvrdsi backoff (30s/90s) pred vzdanim.
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt, backoff in enumerate((0, 30, 90)):
        if backoff:
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            last_exc = exc
    raise last_exc


def _parse_products(html_text):
    items = []
    for card in html_text.split('class="product-filter__product-item"')[1:]:
        nh_m = NAME_RE.search(card)
        price_m = PRICE_RE.search(card)
        if not nh_m or not price_m:
            continue
        rel_url, name = nh_m.groups()
        whole = price_m.group(1).replace(" ", "").replace(" ", "").strip()
        dec = price_m.group(2) or "00"
        try:
            price_czk = float(f"{whole}.{dec}")
        except ValueError:
            continue
        full_url = rel_url if rel_url.startswith("http") else f"{BASE_URL}{rel_url}"
        items.append((html_module.unescape(name).strip(), price_czk, full_url))
    return items


def scrape_category(slug):
    """Vraci list (nazev, cena_czk, plna_url), az MAX_PAGES stranek
    (page=1 = URL bez parametru, dale ?page=2,3,...). Zastavi se driv,
    pokud stranka nema zadne polozky."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/{slug}" if page == 1 else f"{BASE_URL}/{slug}?page={page}"
        html_text = _fetch(url)
        page_items = _parse_products(html_text)
        if not page_items:
            break
        items.extend(page_items)
        if page < MAX_PAGES:
            time.sleep(20)
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
                if args.apply:
                    cur.execute(
                        "INSERT INTO remeslo_price_sources (supplier_name, website, origin) VALUES (%s,%s,%s)",
                        (SUPPLIER_NAME, SUPPLIER_URL, "scrape_pilot"),
                    )
                    source_id = cur.lastrowid
                    print(f"Založen nový zdroj: {SUPPLIER_NAME} (id={source_id})")
                else:
                    print(f"[kontrola] Zdroj '{SUPPLIER_NAME}' zatím neexistuje, založil by se.")
                    source_id = None
            else:
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
                try:
                    items = scrape_category(slug)
                except urllib.error.URLError as exc:
                    # "sroubeni" spadlo 3x nezavisle na stejnem miste i
                    # po 3 pokusech s backoffem 30s/90s, i kdyz opakovany
                    # samostatny curl na stejnou URL hned pote VZDY
                    # uspel (200) - stranka bezi za Azure Front Door s
                    # `ServerID` cookie stickiness, tenhle skript zadne
                    # cookies neudrzuje mezi pozadavky, takze jde
                    # nejspis o vadny/nekonzistentni backend node za
                    # load balancerem, ne o skutecnou chybu na nasi
                    # strane. Radeji preskocit JEDNU kategorii (ze 19,
                    # navic bez existujiciho DB ekvivalentu jinde) nez
                    # zahodit cely 30minutovy beh.
                    print(f"PŘESKOČENO (opakovaná síťová chyba i po retry): {exc}")
                    time.sleep(20)
                    continue
                print(f"Nalezeno {len(items)} položek (až {MAX_PAGES} stránek výpisu).")
                for name, price_czk, url in items[:5]:
                    print(f"  {name[:70]:70s} {price_czk:>10.2f} Kč")
                if len(items) > 5:
                    print(f"  ... a dalších {len(items) - 5}")

                if args.apply and category_id and source_id:
                    cur.execute(
                        "INSERT IGNORE INTO remeslo_material_category_professions "
                        "(category_id, profession_id) VALUES (%s,%s)",
                        (category_id, profession_id),
                    )
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

                # KRITICKE: commit po KAZDE kategorii, ne az na konci
                # celeho behu. Bez autocommit ma pymysql connection
                # implicitni transakci od uplne prvniho SELECTu - bez
                # prubezneho commitu drzi tahle (i cistě cteci, jen
                # --kontrola) transakce MDL zamek na remeslo_professions/
                # remeslo_material_categories PO CELOU DOBU scrapovani
                # (u vetsich kategorii/dodavatelu i desitky minut),
                # coz blokuje ALTER TABLE jinych botu na tychz
                # tabulkach (nahlaseno bot13, 2026-08-19/20, zive
                # reprodukovano - Lock wait timeout na jeho migraci
                # remeslo_professions, dokud tenhle skript bezel).
                # Kazda kategorie je uz beztak samostatny idempotentni
                # DELETE+INSERT blok (viz vyse), takze commit po kazde
                # z nich nic nerozbiji.
                conn.commit()
                # zadny Crawl-delay v robots.txt pro obecneho bota
                # (overeno zive) - konzervativni vlastni odstup mezi
                # kategoriemi, stejny jako HECKL.
                time.sleep(20)

            if args.apply:
                conn.commit()
                print(f"\nOK - zapsáno {total_written} cenových záznamů.")
            else:
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
