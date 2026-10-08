#!/usr/bin/env python3
"""Crawl www.logiman.cz (verejny Shoptet storefront, JE NAS vlastni web,
ne cizi zdroj) a naplni `logiman_cz_price_reference` (SKU -> cena/1m,
cena/ks, URL, datum stazeni) pro novy srovnavaci sloupec v adminu
"Ceny profilu" (webapp/admin/js/ceny.js).

Robert pres bot3, 2026-09-24 (WORKFLOW.md pravidlo 52 "nic se
neodklada"), doslovne: "naopak chci tam videt cenu profilu z 1 m z
original logiman.cz (samozrejme SKU je parovaci znak)".

*** DULEZITE ROZLISENI *** (viz i komentar v sql/2026-09-24c_logiman_cz_
price_reference.sql a v api/admin_profily.py u puvodni poznamky "Robert
2026-08-08: z logiman uz nic nebudeme tahat"): tenhle skript NEOBNOVUJE
nasi vlastni prodejni cenu/hmotnost profilu (ta se pocita z Dogus, viz
scripts/2026-08-09_dogus_price_recompute.py) - je to CISTE READ-ONLY
srovnavaci/referencni udaj, jen aby admin videl vedle sebe "nase cena"
vs. "cena na live logiman.cz webu se stejnym SKU". Zadny jiny kod nesmi
tuhle tabulku pouzit jako VSTUP do naseho cenoveho vypoctu.

Zdroj dat na produktove strance (overeno rucne 2026-09-24 - curl na
hlinikovy-stavebnicovy-profil-20x20/):
- SKU: <meta itemprop="sku" content="...">  (== "Kod produktu" v tabulce
  Parametry, stejne pole jako nase shop_products.sku)
- Cena za 1 m: radek "Merna cena" v tabulce Product-detail, tvar
  "<cislo> Kc&nbsp;/&nbsp;1&nbsp;m" - POUZIVAME PRIMO tenhle udaj (ne
  vlastni prepocet z ceny/ks), protoze logiman.cz ho sam takhle uvadi.
  Kusove zbozi (zaslepky apod.) tenhle radek nema vubec -> NULL, ne 0.
- Cena za ks: cislo pred "<span class="pr-list-unit">/&nbsp;ks</span>"
  za productCardPrice - jen SANITY CHECK (merna_cena * delka tyce/1000
  by mela odpovidat), NEUKLADA se jako primarni hodnota nikam jinam.
- Nazev: <meta property="og:title">

Rozsah crawle: SEZNAM URL Z `sitemap.xml`, filtrovany na ty, ktere v
sobe maji "profil" (case-insensitive) - pokryva vsechny kategorie
hlinikovych profilu i prislusenstvi/zaslepek (162 URL k datu psani,
overeno rucne). Nase admin tabulka "Ceny profilu" ma jen 22 radku, ale
crawl schvalne bere sirsi mnozinu (cele "profil" kategorie), aby
zachytil i pripady, kdy nase SKU nesedi 1:1 na "ocekavany" slug URL
(zjisteno pri overovani: stranka .../hlinikovy-stavebnicovy-profil-
30x30/ ma SKU 1.1.08.030030.02, ne .03, jak by se dalo cekat - matching
je tedy VZDY az podle SKU z <meta>, nikdy podle URL/slugu). Kategorie
stranky (1 segment cesty, zadne SKU meta) se tise preskoci - nejsou
chyba, jen nejsou produkt.

Cely web (1409 URL v sitemape) NEcrawlujeme - zbytecne by to zatezovalo
Robertuv vlastni e-shop kvuli funkci, ktera potrebuje jen profily.
Rozsireni na cely katalog (kdyby Robert chtel srovnani i u ostatniho
zbozi) je pak jen zmena FILTER_SUBSTRING nize.

Sekvencni crawl s prodlevou (REQUEST_DELAY_S) mezi requesty - je to
Robertuv vlastni web, ale nema smysl ho zbytecne zatezovat naraz.

Pouziti:
    python3 scripts/2026-09-24_logiman_price_reference_crawl.py            # dry-run, jen vypis
    python3 scripts/2026-09-24_logiman_price_reference_crawl.py --apply    # skutecny zapis do DB
"""
import argparse
import datetime
import re
import sys
import time
import urllib.request

sys.path.insert(0, "/opt/konfigurator/scripts")
from _env import load_env  # noqa: E402

import pymysql  # noqa: E402

SITEMAP_URL = "https://www.logiman.cz/sitemap.xml"
FILTER_SUBSTRING = "profil"  # case-insensitive filtr sitemap URL, viz hlavicka
UA = "Mozilla/5.0 (compatible; LogimanKonfiguratorPairingSync/1.0; +https://logiman.cz)"
REQUEST_DELAY_S = 1.5
REQUEST_TIMEOUT_S = 20

LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
SKU_RE = re.compile(r'<meta itemprop="sku" content="([^"]+)"')
MERNA_CENA_RE = re.compile(
    r"Měrná cena.*?<span>\s*([\d\s ]+(?:,\d+)?)\s*Kč&nbsp;/&nbsp;1&nbsp;m", re.S
)
PIECE_PRICE_RE = re.compile(
    r'productCardPrice">.*?</span>\s*([\d \s]+(?:,\d{1,2})?)\s*Kč\s*(?:<[^>]*>\s*)*<span class="pr-list-unit">\s*/&nbsp;ks',
    re.S,
)
TITLE_RE = re.compile(r'property="og:title" content="([^"]*)"')


def _parse_czk_number(raw):
    """'1 234,50' / '332' / '246' -> float. Cisti nbsp/mezery, carku na tecku."""
    cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".")
    return float(cleaned)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S).read().decode("utf-8", errors="ignore")


def fetch_sitemap_urls():
    html = fetch(SITEMAP_URL)
    locs = LOC_RE.findall(html)
    return [u for u in locs if FILTER_SUBSTRING in u.lower()]


def parse_product_page(html, url):
    """Vraci dict s daty produktu, nebo None, kdyz stranka neni produktovy
    detail (kategorie/listing stranky nemaji <meta itemprop="sku">)."""
    sku_m = SKU_RE.search(html)
    if not sku_m:
        return None
    sku = sku_m.group(1).strip()

    merna_m = MERNA_CENA_RE.search(html)
    price_per_m = _parse_czk_number(merna_m.group(1)) if merna_m else None

    piece_m = PIECE_PRICE_RE.search(html)
    price_per_piece = _parse_czk_number(piece_m.group(1)) if piece_m else None

    title_m = TITLE_RE.search(html)
    name = title_m.group(1).strip() if title_m else None

    return {
        "sku": sku,
        "price_per_m_czk": price_per_m,
        "price_per_piece_czk": price_per_piece,
        "product_url": url,
        "product_name": name,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Skutecne zapsat do DB. Bez teto volby jen dry-run.")
    ap.add_argument("--limit", type=int, default=None, help="Jen prvnich N URL (test/debug).")
    args = ap.parse_args()

    print(f"Stahuji {SITEMAP_URL} ...")
    urls = fetch_sitemap_urls()
    if args.limit:
        urls = urls[: args.limit]
    print(f"{len(urls)} URL obsahujicich '{FILTER_SUBSTRING}' k projiti.")

    env = load_env()
    conn = None
    if args.apply:
        conn = pymysql.connect(
            host=env["DB_HOST"], port=int(env.get("DB_PORT", 3306)), user=env["DB_USER"],
            password=env["DB_PASSWORD"], database=env["DB_NAME"], charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    matched = []
    skipped_category = 0
    errors = []
    fetched_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

    for i, url in enumerate(urls):
        try:
            html = fetch(url)
        except Exception as e:
            errors.append((url, str(e)))
            time.sleep(REQUEST_DELAY_S)
            continue

        row = parse_product_page(html, url)
        if row is None:
            skipped_category += 1
        else:
            matched.append(row)
            per_m = f"{row['price_per_m_czk']} Kč/m" if row["price_per_m_czk"] is not None else "(bez ceny/m)"
            print(f"  [{i+1}/{len(urls)}] {row['sku']:<20} {per_m:<16} {row['product_name']}")
            if args.apply:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO logiman_cz_price_reference "
                        "(sku, price_per_m_czk, price_per_piece_czk, product_url, product_name, fetched_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s) "
                        "ON DUPLICATE KEY UPDATE price_per_m_czk=VALUES(price_per_m_czk), "
                        "price_per_piece_czk=VALUES(price_per_piece_czk), product_url=VALUES(product_url), "
                        "product_name=VALUES(product_name), fetched_at=VALUES(fetched_at)",
                        (
                            row["sku"], row["price_per_m_czk"], row["price_per_piece_czk"],
                            row["product_url"], row["product_name"], fetched_at,
                        ),
                    )
                conn.commit()

        time.sleep(REQUEST_DELAY_S)

    print()
    print(f"Hotovo: {len(matched)} produktovych stranek se SKU, {skipped_category} kategorie/listing preskoceno, {len(errors)} chyb.")
    if errors:
        print("Chyby:")
        for url, err in errors:
            print(f"  {url}: {err}")
    if not args.apply:
        print("(dry-run - nic nezapsáno do DB, spusť s --apply pro skutečný zápis)", file=sys.stderr)

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
