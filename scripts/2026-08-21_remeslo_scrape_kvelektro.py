#!/usr/bin/env python3
"""Pilotni scraper materialovych cen z kvelektro.cz pro modul 1 Remesla
(srovnavac cen materialu, dle profese) - bot14, 2026-08-21.

Kontext: profese Elektrikar (`remeslo_professions.slug='elektrikar'`,
id=13) mela k tomuto datu **0% pokryti materialem** v celem katalogu
srovnavace (zjisteno bot10, 2026-08-20, viz TASKS.md) - zdaleka
nejvetsi mezera napric profesemi, naleznuta cestou pri overovani
Instalmat.cz/Megaflex.cz (oba vyrazeni, viz TASKS.md/AGENTS_LOG.md,
"jinny obor"/"jednoosobova firma bez e-shopu"). K&V ELEKTRO a.s.
zdokumentovan bot10 jako slibny kandidat, dodatecne overeno bot14 proti
5 kriteriim z REMESLO_KONCEPT.md PRED psanim tohoto skriptu:

1. Velikost firmy: a.s., 22 pobocek + >10 000 vydejnich mist partneru
   v CR (overeno zive na homepage).
2. Dosah: kamenne pobocky napric CR + celostatni e-shop (maloobchod
   ~20 000 produktu, dle homepage).
3. Strukturovany verejny cenik: `robots.txt` uvadi
   `https://www.kvelektro.cz/sitemap/categories.xml` (1825 kategorii)
   a `products-001.xml` - ZADNA Cloudflare/bot ochrana zjistena (plain
   `curl` bez problemu, na rozdil od SIKO). Ceny VEREJNE bez prihlaseni
   (na rozdil od Sonepar CR / Elfetex.cz, oba zamitnuti bot10 kvuli
   B2B prihlasovaci steny). Web je Next.js SSR aplikace - data NEJSOU
   jen v plain HTML (na rozdil od puvodni bot10 poznamky "krehci
   parsing"), ale ve strukturovanem JSON uvnitr `__NEXT_DATA__`
   (`dehydratedState.queries[].state.data.products[]`, pole
   `id`/`urlId`/`title`/`priceWithVat.amount`/`dispo`) - SPOLEHLIVEJSI
   nez HTML-atribut parsing u OBI/HORNBACH, protoze jde o syrova data
   pred renderem, ne o vyparsovani vizualniho rozlozeni.
4. Relevance k profesi: kategorie primo elektroinstalacni (jistice,
   proudove chranice, rozvadece/rozvodnice, elektroinstalacni krabice,
   silove kabely CYKY/CYSY, vypinace a zasuvky, DIN listy) - presne
   "hlavni sortiment" Elektrikare, ne prilezitostny prodej elektro
   veci u DIY hypermarketu.
5. Sire sortimentu: ~20 000 produktu celkem, jednotlive relevantni
   kategorie v radu stovek az tisicu polozek (viz CATEGORIES nize) -
   vyrazne sirsi nez OBI/HORNBACH "Elektroinstalace" podsekce
   zvazovane jako levnejsi alternativa v TASKS.md, proto zvoleno misto
   ni (kriterium 5: "mezi kandidaty splnujicimi 1-4 se upredustni ti s
   VETSIM katalogem").

**Objeveny mechanismus stranovani** (nedokumentovano nikde na webu,
zjisteno zivym testovanim): Next.js interni data-fetch endpoint
`/_next/data/{buildId}/{slug}.json` vraci CISTE JSON (bez HTML obalky,
~600KB vs ~750KB plne stranky) - `?page=N` (N od 1) posouva `from` o
`size`=24 na stranku. `buildId` se meni při kazdem nasazeni webu -
NEDA SE hardcodovat, zjistuje se na zacatku behu z hlavni stranky.

**Rozsah** (jako u ostatnich zdroju - "hlavni sortiment", NE cely
katalog): `MAX_PAGES=6` (144 polozek/kategorie strop), 12 kategorii
vybranych jako jadro elektrikarske prace (jistice, chranice,
rozvadece, krabice, kabely CYKY/CYSY, DIN listy, vypinace/zasuvky
souhrnne, chranicky/trubky, kabelova oka a spojky) - vypinace/zasuvky
maji desitky znackovych/designovych podkategorii (Schneider Unica,
Legrand Valena, ABB...) - pouzita SOUHRNNA rodicovska kategorie
(`vypinace-a-zasuvky-32`, categoryPath agreguje vsechny potomky), ne
kazda znackova rada zvlast (bylo by stovky radku CATEGORIES navic bez
pridane hodnoty pro srovnani cen).

robots.txt nema Crawl-delay - konzervativnich 15s odstup jako u OBI
(novy, drive nevyzkouseny zdroj, stejna uvaha).

Pouziti:
    api/venv/bin/python3 scripts/2026-08-21_remeslo_scrape_kvelektro.py --kontrola
    api/venv/bin/python3 scripts/2026-08-21_remeslo_scrape_kvelektro.py --apply
"""
import argparse
import datetime
import json
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
# POZOR: remeslo_* tabulky ziji od 2026-08-19 ve vlastni DB "Remeslnik" -
# get_conn() z app.py miri na HLAVNI (zmrzlou) DB.
from remeslo import get_remeslo_conn as get_conn  # noqa: E402
import remeslo_price_history  # noqa: E402

SUPPLIER_NAME = "KVelektro.cz"
SUPPLIER_URL = "https://www.kvelektro.cz/"
BASE_URL = "https://www.kvelektro.cz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
PROFESSION_SLUG = "elektrikar"
MAX_PAGES = 6
PAGE_SIZE = 24
REQUEST_DELAY = 15

# (nazev_kategorie_v_DB, unit, kvelektro_slug). Nazvy zvoleny obecne
# (ne znackove), zadny dosavadni zdroj elektro-kategorie nema, tedy
# vsechny nove.
CATEGORIES = [
    ("Jističe", "ks", "jistice-do-125a-83"),
    ("Výkonové jističe", "ks", "vykonove-jistice-202"),
    ("Proudové chrániče", "ks", "proudove-chranice-86"),
    ("Rozváděče a rozvodnice", "ks", "rozvadece-rozvodnice-24"),
    ("Elektroinstalační krabice pod omítku", "ks", "elektroinstalacni-krabice-pod-omitku-361"),
    ("Elektroinstalační krabice na povrch", "ks", "elektroinstalacni-krabice-na-povrch-360"),
    ("Kabely CYKY", "ks", "Kabely-CYKY-247"),
    ("Kabely CYSY a CYLY", "ks", "Kabely-CYSY-CYLY-243"),
    ("DIN lišty a rozvaděčové kanály", "ks", "din-listy-rozvadecove-kanaly-a-spiraly-219"),
    ("Vypínače a zásuvky", "ks", "vypinace-a-zasuvky-32"),
    ("Ohebné trubky a chráničky", "ks", "ohebne-trubky-chranicky-292"),
    ("Kabelová oka a spojky", "ks", "kabelova-oka-spojky-dutinky-fastony-konektory-72"),
]

_BUILD_ID_RE = re.compile(r'"buildId":"(\d+)"')


def _fetch_raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    last_exc = None
    for backoff in (0, 30, 90):
        if backoff:
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            last_exc = exc
    raise last_exc


def get_build_id():
    html_text = _fetch_raw(BASE_URL + "/")
    m = _BUILD_ID_RE.search(html_text)
    if not m:
        raise RuntimeError("buildId nenalezen na hlavni strance - zmenila se struktura webu.")
    return m.group(1)


def _parse_products(data):
    dh = data["pageProps"]["dehydratedState"]
    for q in dh["queries"]:
        if q["queryKey"][0] == "products":
            d = q["state"]["data"]
            return d["total"], d["products"]
    return 0, []


def scrape_category(build_id, slug):
    items = []
    total = None
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/_next/data/{build_id}/{slug}.json"
        if page > 1:
            url += f"?page={page}"
        raw = _fetch_raw(url)
        data = json.loads(raw)
        total, products = _parse_products(data)
        if not products:
            break
        for p in products:
            name = (p.get("title") or "").strip()
            url_id = p.get("urlId")
            price = (p.get("priceWithVat") or {}).get("amount")
            if not name or not url_id or price is None:
                continue
            items.append((name, float(price), f"{BASE_URL}/{url_id}"))
        if len(products) < PAGE_SIZE or page * PAGE_SIZE >= total:
            break
        time.sleep(REQUEST_DELAY)
    return items, total


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true", help="jen vypsat, nic nezapisovat")
    grp.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    args = ap.parse_args()

    build_id = get_build_id()
    print(f"buildId = {build_id}")

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
                    conn.commit()
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
                    items, total = scrape_category(build_id, slug)
                except (urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
                    print(f"PŘESKOČENO (opakovaná chyba i po retry): {exc}")
                    time.sleep(REQUEST_DELAY)
                    continue
                print(f"Nalezeno {len(items)} položek (z celkových {total}, strop {MAX_PAGES} stránek).")
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

                # KRITICKE: commit po KAZDE kategorii, ne az na konci -
                # jinak implicitni transakce drzi MDL zamek po celou
                # dobu behu a blokuje cizi ALTER TABLE (viz Sanitino
                # oprava, e296297, aplikovano od zacatku i zde).
                conn.commit()
                time.sleep(REQUEST_DELAY)

            if args.apply:
                print(f"\nOK - zapsáno {total_written} cenových záznamů.")
            else:
                print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
