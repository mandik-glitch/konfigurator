#!/usr/bin/env python3
"""Třetí pilotní scraper materiálových cen (DEK.cz) pro modul 1 Řemesla
(srovnávač cen materiálu, dle profese) - bot11, 2026-08-17, PŘEPRACOVÁNO
2026-08-20 na jiný sortiment (viz "ZMĚNA PRIORITY" níž).

Kontext: navazuje na 2026-08-17_remeslo_scrape_ptacek.py (bot10) a
2026-08-17_remeslo_scrape_aquatop.py (bot10) - Robert (přes bot3)
chtěl rozšířit ze 2 na cca 10 dodavatelů celkem.

Výběr podle stejných 5 kritérií z REMESLO_KONCEPT.md ("Kritéria
výběru dodavatelů"):
1. Velikost firmy - DEK a.s. je jeden z největších stavebninových
   řetězců v ČR (stovky poboček).
2. Dosah - celostátní síť kamenných poboček + celostátní e-shop
   s rozvozem (ověřeno živě - `export.dek.cz/dek/sitemap.xml`,
   desítky `eshop-product-NNN.xml` souborů = řádově statisíce
   produktů v katalogu).
3. Strukturovaný veřejný ceník - server-rendered HTML
   (`comd-product-view--long` karty), žádný přihlašovací blok jako
   u Ptáčkova B2B portálu, žádné nutné headless prohlížeč/JS.
4. Relevance k profesi - viz "ZMĚNA PRIORITY" níž.
5. Šíře sortimentu - kategorický sitemap obsahuje tisíce podkategorií
   napříč celým stavebním sortimentem (ověřeno živě), výrazně širší
   než u dosavadních instalatérských zdrojů.

**ZMĚNA PRIORITY (Robert, 2026-08-20):** srovnávač dřív obsahoval
hlavně ZAŘIZOVACÍ PŘEDMĚTY z koupelnových e-shopů (baterie/bojlery/
radiátory/kotle/čerpadla - Ptáček/Aquatop/TZBeshop/HECKL, ~800 cen),
ale KALKULAČKY (Modul 9) počítají úplně jiný sortiment - SPOTŘEBNÍ
STAVEBNÍ MATERIÁL (štěrk, beton, cihly, malta, SDK desky, dlažba,
střešní krytina...). Původní DEK běh (2026-08-17, jen 20 cen/1 kat.
"PPR trubky a tvarovky") cílil na STEJNÝ instalatérský přerbytek jako
ostatní zdroje - PŘEPRACOVÁNO na kategorie, které kalkulačky SKUTEČNĚ
počítají (viz `CATEGORIES` níž), aby DEK.cz jako stavebninový
řetězec propojil srovnávač s kalkulačkami (dnes jediný průnik je
voda/topení - trubka, systémová deska). Stará instalatérská kategorie
"PPR trubky a tvarovky" (20 řádků, zdroj DEK.cz) byla ke stejnému
datu z DB smazána (přesun priority pryč, ne bug) - Aquatopshop.cz má
vlastní řádky pro tu samou `remeslo_material_categories` položku
nedotčené.

Struktura stránky (ověřeno živě 2026-08-17, statické server-rendered
HTML, žádný headless prohlížeč potřeba):
    <div class="comd-product-view--long" data-product-id="<ID>">
        ...
        <a class="comd-product-view--long__title" href="/produkty/detail/...">
            Název produktu
        </a>
        ...
        <div class="price-vat highlight">
            <div>46<span>,86</span></div>
            <span>&nbsp;Kč</span>
        </div>
        ...
    </div>
Cena je VŽDY "s DPH" (viz `price-info` text u každé karty, např.
"cena za ks s DPH") - stejný princip jako u obou dosavadních zdrojů.

Stránkování: `?page=N` (ověřeno živě - stránka má typicky 24 karet,
u menších kategorií méně). Omezeno na MAX_PAGES=4 - "hlavní
sortiment" výřez, NE celý katalog kategorie - Robert: "jen hlavní
sortiment podle profese".

Odstup mezi požadavky: 20s (REQUEST_DELAY_S, poučení bot10 2026-08-20 -
viz komentář u konstanty níž).

Kategorie (2026-08-20 přepracování) zvoleny přímo podle materiálových
položek, které jednotlivé `_calc_*` funkce v `api/remeslo.py` počítají
(Modul 9) - KAŽDÁ kategorie ověřena živě (HTTP 200 + skutečné karty
s cenou, `verify_dek_categories.py`-styl kontrola) PŘED zařazením do
seznamu. Profese je teď PER KATEGORIE (`remeslo_professions.slug`),
ne jedna globální hodnota pro celý běh - materiál z jednoho
stavebninového e-shopu logicky patří k RŮZNÝM řemeslům (zedník,
sádrokartonář, pokrývač, obkladač...), na rozdíl od původního
jednoprofesního instalatérského běhu.

Nedohledané kategorie bez čistého DEK ekvivalentu (vynechány, ne
vynucen špatný odhad): "perlinka/sklotextilní síťovina" - DEK má jen
brand-vázané stránky (weber/baumit/cemix/pci), žádnou samostatnou
kategorii napříč značkami.

Idempotence: PŘEPISUJE (DELETE+INSERT) ceny daného zdroje+kategorie
při každém běhu (stejný princip jako Ptáček/Aquatop skripty).

Bez --apply jde o READ-ONLY dry-run (jen vypíše, co by se zapsalo).

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_dek.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_dek.py --apply
"""
import argparse
import datetime
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

SUPPLIER_NAME = "DEK.cz"
BASE_URL = "https://www.dek.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
# Zvednuto z 10s na 20s (poucení bot10, 2026-08-20, AGENTS_LOG.md
# "Řemeslo modul 1: HECKL dokončen" + Sanitino zápisy) - konzervativnější
# odstup mezi požadavky, žádné číslo od webu (robots.txt Crawl-delay
# neuvádí), ale 20s je nový sdílený standard napříč scrapery modulu 1.
REQUEST_DELAY_S = 20
# Stejný strop jako u Ptáčka - "hlavní sortiment", ne celá kategorie
# (DEK má u velkých kategorií desítky stránek, viz docstring výš).
MAX_PAGES = 4

# (nazev_kategorie_v_DB, unit, profession_slug, cesta) - PŘEPRACOVÁNO
# 2026-08-20 (viz "ZMĚNA PRIORITY" v docstringu) na materiál, který
# SKUTEČNĚ počítají kalkulačky (Modul 9, api/remeslo.py), ne obecný
# instalatérský sortiment jako předtím. Každá kategorie ověřena živě
# (HTTP 200 + karty s cenou) PŘED zařazením. Profese je PER kategorie -
# jeden stavebninový e-shop pokrývá řadu různých řemesel.
CATEGORIES = [
    ("Štěrk, písek, kamenivo", "t", "betonar", "/produkty/vypis/10140-kamenivo"),
    ("Beton (suchá směs/transportbeton)", "ks", "betonar", "/produkty/vypis/6300-betony"),
    ("KARI síť", "ks", "betonar", "/produkty/vypis/6188-kari-site"),
    ("Cihly a tvárnice", "ks", "zednik", "/produkty/vypis/4208-zdici-materialy"),
    ("Zdicí malta", "ks", "zednik", "/produkty/vypis/4682-malty"),
    ("Tepelná izolace (EPS/minerální vata)", "ks", "fasadnik", "/produkty/vypis/31-mineralni-vata"),
    ("Lepicí hmota (ETICS)", "ks", "fasadnik", "/produkty/vypis/25378-lepidla-na-tepelne-izolace"),
    ("Armovací stěrka", "ks", "fasadnik", "/produkty/vypis/456-lepidla-a-sterky-weber"),
    ("Talířové hmoždinky", "ks", "fasadnik", "/produkty/vypis/20734-hmozdinky-fasadni"),
    ("Fasádní omítka", "ks", "fasadnik", "/produkty/vypis/67000-omitky"),
    ("Sádrokartonové desky", "ks", "sadrokartonar", "/produkty/vypis/11033-sadrokartonove-desky"),
    ("CD/UD profily", "ks", "sadrokartonar", "/produkty/vypis/493-profily"),
    ("Spojovací materiál do SDK", "ks", "sadrokartonar", "/produkty/vypis/3369-spojovaci-material"),
    ("Tmel na spáry", "ks", "sadrokartonar", "/produkty/vypis/10135-tmely"),
    ("Zámková dlažba", "ks", "dlazdic-dlazba", "/produkty/vypis/12068-zamkova-dlazba"),
    ("Obklady a dlažby", "ks", "obkladac", "/produkty/vypis/37760-obklady-a-dlazby"),
    ("Lepidlo na obklady a dlažbu", "ks", "obkladac", "/produkty/vypis/15823-hmoty-lepici-na-obklady-a-dlazby"),
    ("Spárovací hmota", "ks", "obkladac", "/produkty/vypis/66985-sparovaci-hmoty"),
    ("Penetrace pod omítku/obklad", "ks", "obkladac", "/produkty/vypis/66983-penetrace-pod-omitku"),
    ("Podlahová krytina", "ks", "podlahar", "/produkty/vypis/11377-podlahove-krytiny"),
    ("Podložka pod podlahu", "ks", "podlahar", "/produkty/vypis/12992-podlozky-pod-krytiny"),
    ("Soklové/podlahové lišty", "ks", "podlahar", "/produkty/vypis/1100-listy-a-parapetni-kanaly"),
    ("Střešní krytina (betonová taška)", "ks", "pokryvac", "/produkty/vypis/7447-betonove-krytiny"),
    ("Latě a kontralatě (dřevo na krov)", "ks", "pokryvac", "/produkty/vypis/7301-drevo"),
    ("Pojistná hydroizolace (difuzní fólie)", "ks", "pokryvac", "/produkty/vypis/54-stresni-folie"),
]

CARD_RE = re.compile(
    r'<div class="comd-product-view--long" data-product-id="(\d+)">(.*?)'
    r'(?=<div class="comd-product-view--long" data-product-id="\d+">|\Z)',
    re.S,
)
TITLE_RE = re.compile(r'comd-product-view--long__title"[^>]*>\s*([^<]+?)\s*</a>', re.S)
PRICE_RE = re.compile(r'price-vat highlight">\s*<div>([\d\s\xa0]+)<span>,(\d+)</span>', re.S)
URL_RE = re.compile(r'href="(/produkty/detail/[^"]+)"')


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_products(html):
    items = []
    for _pid, card in CARD_RE.findall(html):
        title_m = TITLE_RE.search(card)
        price_m = PRICE_RE.search(card)
        url_m = URL_RE.search(card)
        if not title_m or not price_m:
            continue
        whole = re.sub(r"[\s\xa0]+", "", price_m.group(1))
        price_czk = float(whole) + float(price_m.group(2)) / 100
        full_url = BASE_URL + url_m.group(1) if url_m else None
        items.append((title_m.group(1).strip(), price_czk, full_url))
    return items


def scrape_category(path):
    """Vraci list (nazev, cena_czk, plna_url) pro danou kategorii, az
    MAX_PAGES stranek vypisu (?page=N - overeno zive). Zastavi se driv,
    pokud nejaka stranka nema zadne polozky (kratsi kategorie)."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        url = BASE_URL + path if page == 1 else f"{BASE_URL}{path}?page={page}"
        html = _fetch(url)
        page_items = _parse_products(html)
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

    # DULEZITE (bot11, po 2x padu na "Lost connection to MySQL server
    # during query (timed out)"): get_conn() v app.py ma zamerne
    # read_timeout=25 (viz komentar tamtez - navrzeno pro RYCHLE web
    # requesty v gunicorn workeru, ne pro skript, ktery mezi dotazy
    # cekal desitky sekund kvuli 4x sleep(10) behem scrapovani jedne
    # kategorie). JEDNO spojeni drzene po cely beh tenhle predpoklad
    # porusi. Misto toho: get_conn() volano ZNOVU pred KAZDOU
    # kategorii - vraci ten samy thread-local pool, ale
    # `real.ping(reconnect=True)` uvnitr get_conn() pri kazdem volani
    # overi zivotnost a v tichosti znovu-pripoji, kdyz spojeni mezitim
    # (behem scrapovani) zdrhlo - presne to, k cemu je pooling
    # navrzeny (viz `_PooledConn`/`_pooled_conn_local` komentare v
    # app.py), jen ho skript musi VOLAT znovu, ne drzet handle
    # nekonecne dlouho.
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
                        (SUPPLIER_NAME, "https://www.dek.cz/"),
                    )
                    source_id = cur.lastrowid
                    print(f"Založen nový zdroj: {SUPPLIER_NAME} (id={source_id})")
                else:
                    print(f"[kontrola] Zdroj '{SUPPLIER_NAME}' zatím neexistuje, založil by se.")
                    source_id = None
            else:
                source_id = source_row["id"]

            # Profese je ted PER KATEGORIE (viz CATEGORIES vys) - nacti
            # vsechny naraz do slovniku slug->id, misto jedne globalni
            # hodnoty pro cely beh.
            needed_slugs = sorted({slug for _n, _u, slug, _p in CATEGORIES})
            cur.execute(
                f"SELECT id, slug FROM remeslo_professions WHERE slug IN ({','.join(['%s'] * len(needed_slugs))})",
                needed_slugs,
            )
            profession_ids = {r["slug"]: r["id"] for r in cur.fetchall()}
            missing_slugs = [s for s in needed_slugs if s not in profession_ids]
            if missing_slugs:
                print(f"CHYBA: profese {missing_slugs} nejsou v remeslo_professions.")
                sys.exit(1)
        conn.commit()
    finally:
        conn.close()

    total_written = 0
    skipped = []
    for cat_name, unit, profession_slug, path in CATEGORIES:
        print(f"\n== {cat_name} ({path}) ==")
        # Poucení bot10 (2026-08-20, Sanitino.cz VZDÁN): pokud web u
        # jedné kategorie aktivně blokuje/padá, NEZKOUŠET donekonečna -
        # 1 rychlý retry (přechodná chyba), pak zapsat proč a jít na
        # další kategorii, ne shodit celý běh (přesně tohle se stalo
        # DEK.cz běhu 2026-08-17 - spadl po 1. kategorii bez zápisu
        # důvodu, žádné dalších 22 kategorií se vůbec nezkusilo).
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

        # DALSI ZJISTENI (bot11): i CERSTVE spojeni (viz vys) obcas
        # zdrhlo UPROSTRED zapisu jedne kategorie (ne kvuli necinnosti -
        # padalo i behem rychle serie INSERTu bez sleep mezi nimi). To
        # odpovida komentari u get_conn() v app.py: "vzdalene spojeni
        # (Forpsi Cloud DBaaS) OBCAS zdrhne uprostred requestu" - je to
        # zdokumentovana prubezna nestabilita tohodle konkretniho
        # remote DBaaS, ne neco, co jde "opravit" spravnou strukturou
        # kodu. Web app to resi automaticky (dalsi HTTP request proste
        # dostane novy/znovu-pripojeny handle) - skript potrebuje
        # STEJNOU odolnost explicitne, protoze desitky kategorii za
        # sebou zvysuji šanci, ze na nekterou z nich zrovna padne.
        # Retry cele kategorie (DELETE+INSERT je idempotentni, bezpecne
        # zopakovat) s cerstvym spojenim, max 3 pokusy.
        for attempt in range(1, 4):
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
                            (category_id, profession_ids[profession_slug]),
                        )
                        # Historie ceny (bot10, 2026-08-20) - PRED smazanim
                        # stareho stavu zachytit puvodni ceny, at je s cim
                        # porovnat novy scrape. Zapisuje se JEN kdyz se
                        # cena SKUTECNE zmenila (viz remeslo_price_history).
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
                # Commit PO KAZDE kategorii, ne az na konci celeho behu -
                # idempotence (DELETE+INSERT per kategorie) dela pripadne
                # znovu-spusteni po vypadku bezpecne.
                conn.commit()
                break
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as e:
                print(f"  [pokus {attempt}/3] DB spojení zdrhlo ({e}), zkouším znovu...")
                if attempt == 3:
                    raise
                time.sleep(5)
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
