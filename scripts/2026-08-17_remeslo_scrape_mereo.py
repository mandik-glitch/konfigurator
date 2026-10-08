#!/usr/bin/env python3
"""Čtvrtý pilotní scraper materiálových cen (Mereo.cz) pro modul 1
Řemesla (srovnávač cen materiálu, dle profese) - bot11, 2026-08-17.

Kontext: navazuje na 2026-08-17_remeslo_scrape_ptacek.py (bot10),
2026-08-17_remeslo_scrape_aquatop.py (bot10) a
2026-08-17_remeslo_scrape_dek.py (bot11, tentýž den) - Robert (přes
bot3) chtěl rozšířit ze 2 na cca 10 dodavatelů celkem. Souběžně dělá
totéž bot23 na jiných dodavatelích (zkoordinováno napřímo mezi boty).

Zvažovaní, ale ZAMÍTNUTÍ kandidáti (pro dohledatelnost, ať se příště
nezkouší znovu marně):
- **SIKO Koupelny** (siko.cz) - za Cloudflare bot-ochranou (403 "Just
  a moment...", i.e. JS-challenge), nejde spolehlivě scrapovat prostým
  HTTP požadavkem bez obcházení ochrany - vědomě NEřešeno (nechceme
  stavět bypass Cloudflare výzvy).
- **Stavmat.cz** - velký celostátní řetězec, ale sortiment je čistě
  střešní krytiny/fasády/hutní materiál - žádná kategorie
  voda/topení/sanita v `product_category-sitemap.xml` (ověřeno živě,
  41 kategorií, 0 relevantních) - nesplňuje kritérium 4 (relevance
  k profesi).

Výběr Mereo.cz podle stejných 5 kritérií z REMESLO_KONCEPT.md:
1. Velikost firmy - vlastní výrobní/obchodní značka (Mereo, Klum,
   Novea...) s fyzickými prodejnami (Kyjov aj.) + celostátní e-shop.
2. Dosah - celostátní e-shop s rozvozem, `velkoobchodni-prodej`/
   `b2b-system` sekce navíc ukazují i velkoobchodní model.
3. Strukturovaný veřejný ceník - čisté server-rendered HTML (Upgates
   e-shop platforma), žádný přihlašovací blok, žádný headless
   prohlížeč potřeba (na rozdíl od zamítnutého SIKO).
4. Relevance k profesi - `instalatersky-material` kategorie (41 stránek
   po 24 položkách = ~984 SKU jen v jedné obecné kategorii) +
   desítky specifických podkategorií (baterie všech typů, kohouty,
   armatury, sifony, těsnění...).
5. Šíře sortimentu - `sitemap-categories.xml.gz` obsahuje accd. 130+
   čistých kategorií (bez filtr-permutací) jen v okruhu koupelna/
   instalace (ověřeno živě), širší než Ptáček, srovnatelné s DEK.

Struktura stránky (ověřeno živě 2026-08-17, statické server-rendered
HTML, žádný headless prohlížeč potřeba - platforma Upgates):
    <article class="b card card-item tile p-i" data-product-id="<ID>">
        <a class="pi-header" href="/p/produkt-slug">Název produktu</a>
        ...
        <div class="main-price-pi">
            <strong>199 Kč</strong> <small class="ws-n">s DPH</small>
        </div>
    </article>
Cena je VŽDY "s DPH" (stejný princip jako u ostatních 3 zdrojů).
Názvy produktů obsahují HTML entity (např. `&quot;` pro palcové
rozměry) - `html.unescape()` použit při parsování.

Stránkování: `/<kategorie>/pg-N` (ověřeno živě - "instalatersky-
material" má 41 stránek). Stejně jako u Ptáčka/DEKu omezeno na
"hlavní sortiment" výřez, NE celý katalog kategorie.

robots.txt (mereo.cz) NEuvádí Crawl-delay - použit stejný konzervativní
10s odstup jako u Aquatopshop.cz/DEK.cz.

Kategorie zvoleny ze živě ověřeného `sitemap-categories.xml.gz` -
kde existuje stejnojmenná kategorie u některého z předchozích 3
zdrojů, použit STEJNÝ název kvůli srovnatelnosti napříč zdroji ve
stejné `remeslo_material_categories` řádce; zbytek jsou Mereo-
specifické kategorie (hodně typů baterií/armatur) rozšiřující šíři
sortimentu.

Idempotence: PŘEPISUJE (DELETE+INSERT) ceny daného zdroje+kategorie
při každém běhu (stejný princip jako ostatní 3 skripty).

Bez --apply jde o READ-ONLY dry-run (jen vypíše, co by se zapsalo).

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_mereo.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_mereo.py --apply
"""
import argparse
import datetime
import html
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
import remeslo_price_history  # noqa: E402

SUPPLIER_NAME = "Mereo.cz"
BASE_URL = "https://www.mereo.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"
# Zvednuto z 10s na 20s (poucení bot10, 2026-08-20, AGENTS_LOG.md
# "Řemeslo modul 1: HECKL dokončen" + Sanitino zápisy) - konzervativnější
# odstup mezi požadavky, žádné číslo od webu (robots.txt Crawl-delay
# neuvádí), ale 20s je nový sdílený standard napříč scrapery modulu 1.
REQUEST_DELAY_S = 20
# Stejný strop jako u Ptáčka/DEKu - "hlavní sortiment", ne celá
# kategorie (Mereo má u obecné kategorie desítky stránek).
MAX_PAGES = 4

# (nazev_kategorie_v_DB, unit, cesta) - nazvy sdilene s Ptáček/
# Aquatopshop/DEK OZNAČENY komentářem kvůli srovnatelnosti, zbytek je
# Mereo-specifické rozšíření sortimentu (hodně typů baterií/armatur,
# které ostatní 3 zdroje nerozlišují tak jemně).
CATEGORIES = [
    ("Vodovodní baterie", "ks", "/vodovodni-baterie"),  # sdíleno s Ptáček/DEK
    ("Umyvadlové baterie", "ks", "/umyvadlove-baterie"),  # sdíleno s Ptáček/DEK
    ("Vanové baterie", "ks", "/vanove-baterie"),  # sdíleno s Ptáček/DEK
    ("Sprchové baterie", "ks", "/sprchove-baterie"),  # sdíleno s Ptáček/DEK
    ("Dřezové baterie", "ks", "/drezove-baterie"),
    ("Bidetové baterie", "ks", "/bidetove-baterie"),
    ("Podomítkové baterie", "ks", "/podomitkove-baterie"),
    ("Termostatické baterie", "ks", "/termostaticke-baterie"),
    ("Kulové kohouty a ventily", "ks", "/kulove-kohouty"),  # sdíleno s Aquatop/DEK
    ("Kulové kohouty plyn", "ks", "/kulove-kohouty-plyn"),
    ("Mosazné armatury", "ks", "/mosazne-armatury"),
    ("Mosazné tvarovky", "ks", "/mosazne-tvarovky"),  # sdíleno s DEK
    ("Chromované armatury", "ks", "/chromovane-armatury"),
    ("Radiátorové ventily a šroubení", "ks", "/radiatorove-ventily-a-sroubeni"),
    ("Rohové a pračkové ventily", "ks", "/rohove-a-prackove-ventily"),
    ("Sifony a výpustě", "ks", "/sifony-a-vypuste"),  # sdíleno s Aquatop/DEK
    ("Těsnící materiál", "ks", "/tesnici-materialy"),  # sdíleno s Aquatop/DEK
    ("Nerezové připojovací hadice", "ks", "/nerezove-pripojovaci-hadice"),
    ("Nerezové vlnovcové trubky", "ks", "/nerezove-vlnovcove-trubky"),
    ("WC sedátka", "ks", "/wc-sedatka"),  # sdíleno s Ptáček
    ("Moduly pro WC", "ks", "/moduly-pro-wc"),
    ("Otopné žebříky", "ks", "/otopne-zebriky"),
    ("Měřicí a regulační technika", "ks", "/merici-a-regulacni-technika"),
]

CARD_RE = re.compile(
    r'data-product-id="(\d+)"[^>]*>(.*?)'
    r'(?=<article class="b card|\Z)',
    re.S,
)
TITLE_RE = re.compile(r'class="pi-header"[^>]*>([^<]+)</a>', re.S)
PRICE_RE = re.compile(r'main-price-pi">\s*<strong>([\d\s\xa0]+)\s*Kč</strong>', re.S)
URL_RE = re.compile(r'href="(/p/[^"]+)"')


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_products(page_html):
    items = []
    for _pid, card in CARD_RE.findall(page_html):
        title_m = TITLE_RE.search(card)
        price_m = PRICE_RE.search(card)
        url_m = URL_RE.search(card)
        if not title_m or not price_m:
            continue
        price_czk = float(re.sub(r"[\s\xa0]+", "", price_m.group(1)))
        name = html.unescape(title_m.group(1).strip())
        full_url = BASE_URL + url_m.group(1) if url_m else None
        items.append((name, price_czk, full_url))
    return items


def scrape_category(path):
    """Vraci list (nazev, cena_czk, plna_url) pro danou kategorii, az
    MAX_PAGES stranek vypisu (/pg-N - overeno zive). Zastavi se driv,
    pokud nejaka stranka nema zadne polozky (kratsi kategorie)."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        url = BASE_URL + path if page == 1 else f"{BASE_URL}{path}/pg-{page}"
        page_html = _fetch(url)
        page_items = _parse_products(page_html)
        if not page_items:
            break
        items.extend(page_items)
        if page < MAX_PAGES:
            time.sleep(REQUEST_DELAY_S)
    return items


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true", help="jen vypsat, nic nezapisovat")
    grp.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    args = ap.parse_args()

    # DULEZITE (bot11): stejny fix/zduvodneni jako
    # 2026-08-17_remeslo_scrape_dek.py - get_conn() v app.py ma
    # zamerne read_timeout=25 (navrzeno pro rychle web requesty, ne
    # skript se sleep(10)x4 mezi zapisy). get_conn() se proto vola
    # ZNOVU pred KAZDOU kategorii (cerstve overeni/reconnect pres
    # `real.ping(reconnect=True)`), ne jednou na zacatku pro cely beh.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM remeslo_price_sources WHERE supplier_name=%s", (SUPPLIER_NAME,))
            source_row = cur.fetchone()
            if not source_row:
                if args.apply:
                    cur.execute(
                        "INSERT INTO remeslo_price_sources (supplier_name, website, origin) "
                        "VALUES (%s,%s,'scrape_pilot')",
                        (SUPPLIER_NAME, "https://www.mereo.cz/"),
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
        conn.commit()
    finally:
        conn.close()

    total_written = 0
    skipped = []
    for cat_name, unit, path in CATEGORIES:
        print(f"\n== {cat_name} ({path}) ==")
        # Poucení bot10 (2026-08-20, Sanitino.cz VZDÁN): pokud web u
        # jedné kategorie aktivně blokuje/padá, NEZKOUŠET donekonečna -
        # 1 rychlý retry (přechodná chyba), pak zapsat proč a jít na
        # další kategorii, ne shodit celý běh (stejná oprava jako u
        # sesterského DEK.cz skriptu, viz tamní komentář).
        items = None
        last_err = None
        for scrape_attempt in (1, 2):
            try:
                items = scrape_category(path)
                break
            except Exception as e:  # noqa: BLE001 - sirsi zachyt zamerne, viz komentar vys
                last_err = e
                if scrape_attempt == 1:
                    print(f"  [pokus 1/2] scrapování selhalo ({e}), zkouším znovu za 20s...")
                    time.sleep(REQUEST_DELAY_S)
        if items is None:
            print(f"  VYNECHÁNO - scrapování selhalo i po 2. pokusu: {last_err}")
            skipped.append((cat_name, str(last_err)))
            time.sleep(REQUEST_DELAY_S)
            continue
        print(f"Nalezeno {len(items)} položek (až {MAX_PAGES} stránek výpisu).")
        for name, price_czk, url in items[:5]:
            print(f"  {name[:70]:70s} {price_czk:>10.2f} Kč")
        if len(items) > 5:
            print(f"  ... a dalších {len(items) - 5}")

        # Cerstve spojeni AZ TEĎ, po scrapovani.
        conn = get_conn()
        try:
            with conn.cursor() as cur:
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

                if args.apply and category_id and source_id:
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
            # Commit PO KAZDE kategorii - idempotence (DELETE+INSERT
            # per kategorie) dela pripadne znovu-spusteni bezpecne.
            conn.commit()
        finally:
            conn.close()
        time.sleep(REQUEST_DELAY_S)

    if skipped:
        print(f"\nVYNECHANÉ kategorie ({len(skipped)}) - scrapování opakovaně selhalo:")
        for cat_name, err in skipped:
            print(f"  - {cat_name}: {err}")
    if args.apply:
        print(f"\nOK - zapsáno {total_written} cenových záznamů.")
    else:
        print("\n[kontrola] Nic nezapsáno (dry-run). Spusť s --apply pro skutečný zápis.")


if __name__ == "__main__":
    main()
