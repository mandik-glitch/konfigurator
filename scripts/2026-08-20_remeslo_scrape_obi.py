#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z obi.cz pro modul 1 Řemesla
(srovnávač cen materiálu, dle profese) - bot10, 2026-08-20.

Kontext: pokračování v rozšiřování z 5 na cca 10 dodavatelů (Ptáček-
shop.cz, Aquatopshop.cz, TZBeshop.cz, HECKL hotové; DEK.cz/Mereo.cz
rozpracovává bot11 souběžně - NESAHAT). Robert zadal přímo: "vezmi si
SIKO Koupelny plus jednoho dalšího kandidáta, kterého si sám vybereš".
**SIKO Koupelny (siko.cz) vyzkoušeno a VZDÁNO** - celý web (vč. sitemap
XML) je za Cloudflare s aktivním JS challenge (`cf-mitigated: challenge`
hlavička na KAŽDÉM požadavku, i na homepage, i bez konkrétní kategorie)
- na rozdíl od Sanitina (nejednoznačné, přerušované 404) jde o zjevnou,
jednoznačnou aktivní ochranu proti scrapování bez spuštění JS/řešení
challenge, což by vyžadovalo headless prohlížeč (Playwright) - jiná
třída řešení než zbytek modulu 1, a fakticky obcházení bot-ochrany.
Robertovo poučení ze Sanitina ("při aktivní obraně webu vzdát") platí
tady ještě jasněji - SIKO se do modulu 1 NEPŘIDÁVÁ, žádný skript pro
něj nevznikl.

**OBI.cz vybráno jako náhrada** (samostatný výběr, ověřeno proti 5
kritériím z REMESLO_KONCEPT.md PŘED psaním skriptu):
1. Velikost/dosah: mezinárodní DIY hypermarketový řetězec (německý
   OBI), desítky kamenných poboček napříč ČR + celostátní e-shop.
2. Strukturovaný ceník: `sitemap_obi-category.xml` má tisíce leaf
   kategorií (`/{parent}/{kategorie}/c/{id}`), produktové karty mají
   stabilní `class="product-wrapper"` s `title`/`href`/cenou v
   `data-csscontent` atributu - ověřeno živě, žádný Cloudflare
   challenge (na rozdíl od SIKO), plain `curl` bez problému.
3. Šíře sortimentu: kategorie `koupelna/vany` má přes 100 položek
   (2 stránky po 71), typická kategorie desítky.
4. Relevance k profesi: koupelnové/instalatérské kategorie (baterie,
   sifony, ventily, vany, umyvadla, WC, sanitární instalace) přímo pro
   profesi `instalater`.
5. Šíře - viz bod 3, mnohem větší katalog než malý lokální obchod
   (Instalmat, dřívější zamítnutý kandidát bez zjevné celostátní sítě).

Struktura kategorie (ověřeno živě, statické server-rendered HTML):
    <a class="product-wrapper" href="/slug/nazev-produktu/p/12345"
       title="Název produktu" data-position="1" data-pagenum="1" ...>
      ...
      <span data-ui-name="aues.product.N.price.span"
            data-csscontent="599,- Kč*"></span>
    </a>
Cena je vždy uvedena bez desetinných míst pozorovaná ve formátu
"599,- Kč" (čárka+pomlčka = "0 haléřů", žádný desetinný tvar
pozorován u zkoumaných kategorií) - parsováno jako celé číslo Kč.

Stránkování: `?page=N` (N od 1, `page=1` implicitní i bez parametru).

robots.txt (obi.cz) nemá Crawl-delay pro obecného bota (jen specifické
Disallow cesty, žádné z nich nekolidují s `/{kategorie}/c/{id}`
vzorem) - přesto konzervativní 15s odstup (mezi HECKLových 12s a
Sanitinových 20s, protože jde o nový, dřív nevyzkoušený zdroj).

**Poučení ze Sanitina aplikovaná OD ZAČÁTKU** (Robert: "drž se svých
vlastních poučení"):
- `conn.commit()` po KAŽDÉ kategorii (ne jednou na konci) - jinak
  implicitní transakce drží MDL zámek na `remeslo_professions`/
  `remeslo_material_categories` po celou dobu běhu a blokuje cizí
  `ALTER TABLE` (viz bot13ho nález u Sanitina).
- `_fetch()` má retry s backoffem (0/30s/90s) na tranzientní chyby.
- Kategorie, která spadne i po retry, se PŘESKOČÍ (ne pád celého
  běhu) - u opakovaného selhání STEJNÉ kategorie napříč více běhy je
  to signál aktivní obrany (viz SIKO/Sanitino výš), ne důvod
  donekonečna zkoušet.

Idempotence: DELETE+INSERT při každém běhu (aktuální stav ke dni
scrapu, ne historie) - stejný vzor jako ostatní zdroje.

Použití:
    api/venv/bin/python3 scripts/2026-08-20_remeslo_scrape_obi.py --kontrola
    api/venv/bin/python3 scripts/2026-08-20_remeslo_scrape_obi.py --apply
"""
import argparse
import datetime
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
# POZOR: remeslo_* tabulky ZIJI OD 2026-08-19 VE VLASTNI DB "Remeslnik" -
# get_conn() z app.py miri na HLAVNI (zmrzlou) DB, viz bot14ho nalez.
from remeslo import get_remeslo_conn as get_conn  # noqa: E402
import remeslo_price_history  # noqa: E402

SUPPLIER_NAME = "OBI.cz"
SUPPLIER_URL = "https://www.obi.cz/"
BASE_URL = "https://www.obi.cz"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
PROFESSION_SLUG = "instalater"
# "Hlavní sortiment", ne celý katalog (REMESLO_KONCEPT.md) - 5 stránek
# (71 položek/stránka pozorováno živě) = až 355 položek/kategorii.
MAX_PAGES = 5
REQUEST_DELAY = 15

# (nazev_kategorie_v_DB, unit, url_cesta_relativni_k_BASE_URL). Kde
# existuje stejná reálná kategorie už u jiného zdroje, použit STEJNÝ
# název (srovnatelnost napříč zdroji - viz DESCRIBE remeslo_material_
# categories před psaním, ověřeno živě). "Kuchyňské baterie" a
# "Sprchové vaničky" nemají dosud ekvivalent - nové kategorie.

# **PRIORITIZACE ZMĚNĚNA 2026-08-20 (Robert, přes bota, po jeho dotazu):**
# dosavadní srovnávač (Ptáček/Aquatop/TZBeshop/HECKL) obsahuje skoro
# výhradně KOUPELNOVÉ/INSTALATÉRSKÉ ZAŘIZOVACÍ PŘEDMĚTY (baterie,
# bojlery, radiátory, kotle - ~800 cen), zatímco Modul 9 KALKULAČKY
# (Zámková dlažba, Obklady a dlažby, Malování, Sádrokarton, Podlahy,
# Fasáda a zateplení, Betonáž, Zemní práce, Zdění...) počítají úplně
# JINÝ sortiment - spotřební STAVEBNÍ MATERIÁL. Překryv mezi
# srovnávačem a tím, co kalkulačky reálně potřebují, byl dosud
# minimální (ověřeno: `remeslo_pricelist_items`, tabulka, ze které
# kalkulačky READ cenu, měla k tomuto datu 0 řádků ve VŠECH 14
# systémových kategoriích - kalkulačky tedy dosud počítaly jen
# množství, nikdy Kč). OBI je DIY hypermarket, který nese OBOJÍ -
# proto tady prioritizovány kategorie, které skutečně matchují
# vstupy kalkuláček (štěrk/písek, beton/cement, KARI síť, cihly/
# tvárnice, malta, EPS/minerální vata, lepidlo, stěrka, perlinka,
# hmoždinky, omítka, sádrokarton, obklady/dlažba, spárovací hmota,
# penetrace, podlahové krytiny, soklové lišty, malířská barva,
# dřevěné hranoly, impregnace dřeva) - PŘED dřívějšími koupelnovými
# kategoriemi (baterie/WC/sifony/ventily), které OBI taky má, ale
# které už srovnávač pokrývá jinými zdroji. Střešní tašky/latě/
# difúzní fólie/podložka pod podlahu Robert taky zmínil, ale OBI pro
# ně NEMÁ samostatnou kategorii v `sitemap_obi-category.xml` (obecný
# DIY hypermarket, ne střešní velkoobchod) - vynecháno, ne přehlédnuto.
CATEGORIES = [
    ("Štěrk, písek a kamenivo", "ks", "kameny-a-sterky/sypke-materialy/c/671"),  # nova
    ("Cihly", "ks", "kameny-a-sterky/cihly/c/550"),  # nova
    ("Tvárnice", "ks", "kameny-a-sterky/porobetonove-tvarnice/c/614"),  # nova
    ("Cement a vápno", "ks", "omitky-malty-a-cement/cement-a-vapno/c/828"),  # nova
    ("KARI síť", "ks", "omitky-malty-a-cement/konstrukcni-ocel-a-kari-site/c/174"),  # nova
    ("Malta", "ks", "omitky-malty-a-cement/malta/c/765"),  # nova
    ("Omítky", "ks", "omitky-malty-a-cement/omitky/c/620"),  # nova
    ("Stěrky (vyrovnávací hmoty)", "ks", "omitky-malty-a-cement/vyrovnavaci-hmoty/c/136"),  # nova
    ("Perlinka a omítací lišty", "ks", "omitky-malty-a-cement/omitaci-a-apu-listy-s-perlinkou/c/621"),  # nova
    ("EPS izolace (polystyren)", "ks", "izolacni-materialy/penove-izolace/c/368"),  # nova
    ("Minerální vata", "ks", "izolacni-materialy/izolace-z-mineralnich-vlaken/c/565"),  # nova
    ("Lepidlo na obklady a dlažbu", "ks", "prislusenstvi-k-obkladum-a-dlazbam/lepidla-na-obklady-a-dlazby/c/310"),  # nova
    ("Spárovací hmota", "ks", "prislusenstvi-k-obkladum-a-dlazbam/sparovaci-hmoty/c/318"),  # nova
    ("Penetrace (základní nátěry)", "ks", "barvy-a-laky/zakladni-natery/c/2982"),  # nova
    ("Obklady", "ks", "obklady-a-dlazby/obklady/c/786"),  # nova
    ("Dlažba", "ks", "obklady-a-dlazby/dlazba/c/1150"),  # nova
    ("Hmoždinky", "ks", "zelezarske-zbozi/hmozdinky/c/1366"),  # nova
    ("Sádrokartonové desky", "ks", "sucha-vystavba/sadrokartonove-desky/c/375"),  # nova
    ("Sádrokarton - příslušenství", "ks", "sucha-vystavba/prislusenstvi-pro-sadrokartonove-desky/c/841"),  # nova
    ("Podlahové krytiny", "ks", "bydleni/podlahove-krytiny/c/201"),  # nova
    ("Soklové lišty", "ks", "bydleni/soklove-listy/c/4842"),  # nova
    ("Malířská barva", "ks", "barvy-a-laky/barvy-na-zed/c/2979"),  # nova
    ("Dřevěné hranoly", "ks", "stavebni-drevo/konstrukcni-drevo-a-lepene-vrstvene-hranoly/c/1823"),  # nova
    ("Impregnace a ošetření dřeva", "ks", "lazury-a-barvy-na-drevo/osetreni-dreva/c/3074"),  # nova
    # Nizsi priorita (koupelnove zarizovaci predmety - srovnavac uz je
    # castecne pokryty jinymi zdroji), ale OBI je ma taky - zaradit,
    # dokud jde o rozsireni pokryti bez extra prace navic.
    ("Vanové baterie", "ks", "koupelna/vodovodni-baterie-do-koupelny/vanove-baterie/c/790"),
    ("Umyvadlové baterie", "ks", "koupelna/vodovodni-baterie-do-koupelny/umyvadlove-baterie/c/800"),
    ("Sprchové baterie", "ks", "koupelna/vodovodni-baterie-do-koupelny/sprchove-baterie/c/1221"),
    ("WC sedátka", "ks", "toalety/wc-zachodova-prkenka/c/1199"),
    ("Umyvadla", "ks", "koupelna/umyvadla/c/4361"),
    ("Vany", "ks", "koupelna/vany/c/4160"),
]

NAME_RE = re.compile(r'href="([^"]+)"[^>]*title="([^"]+)"', re.S)
# Pozorovany format vzdy "1 029,- Kč*" (cele cislo, "-" = 0 haleru) -
# druha skupina je bud "-" nebo 2 cislice, kdyby nejaka polozka mela
# realne desetiny (nepozorovano ve vzorku, ale nechci to tise zahodit).
PRICE_RE = re.compile(r'data-csscontent="([\d\s ]+),(-|\d{2})\s*Kč', re.S)


def _fetch(url):
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


def _parse_products(html_text):
    items = []
    for card in html_text.split('<a class="product-wrapper')[1:]:
        nh_m = NAME_RE.search(card)
        price_m = PRICE_RE.search(card)
        if not nh_m or not price_m:
            continue
        rel_url, name = nh_m.groups()
        whole = price_m.group(1).replace(" ", "").replace(" ", "").strip()
        dec = "00" if price_m.group(2) == "-" else price_m.group(2)
        try:
            price_czk = float(f"{whole}.{dec}")
        except ValueError:
            continue
        full_url = rel_url if rel_url.startswith("http") else f"{BASE_URL}{rel_url}"
        items.append((html_module.unescape(name).strip(), price_czk, full_url))
    return items


def scrape_category(path):
    items = []
    for page in range(1, MAX_PAGES + 1):
        url = f"{BASE_URL}/{path}" if page == 1 else f"{BASE_URL}/{path}?page={page}"
        html_text = _fetch(url)
        page_items = _parse_products(html_text)
        if not page_items:
            break
        items.extend(page_items)
        if page < MAX_PAGES:
            time.sleep(REQUEST_DELAY)
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
            for cat_name, unit, path in CATEGORIES:
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

                print(f"\n== {cat_name} ({path}) ==")
                try:
                    items = scrape_category(path)
                except urllib.error.URLError as exc:
                    print(f"PŘESKOČENO (opakovaná síťová chyba i po retry): {exc}")
                    time.sleep(REQUEST_DELAY)
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

                # KRITICKE: commit po KAZDE kategorii, ne az na konci -
                # viz Sanitino oprava (e296297), stejny duvod platí zde
                # od zacatku (implicitni transakce jinak drzi MDL zamek
                # po celou dobu behu a blokuje cizi ALTER TABLE).
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
