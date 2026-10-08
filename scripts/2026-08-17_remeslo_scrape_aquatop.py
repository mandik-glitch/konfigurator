#!/usr/bin/env python3
"""Pilotní scraper materiálových cen z Aquatopshop.cz pro modul 1
Řemesla (srovnávač cen materiálu, dle profese) - bot10, 2026-08-17.

Druhý ze 2 schválených pilotních dodavatelů (viz
2026-08-17_remeslo_scrape_ptacek.py pro první a plný kontext výběru).
Stejná kategorie "Domácí vodárna" jako u Ptáčka (jiná URL cesta na
tomto webu), aby šlo výsledné ceny porovnávat napříč zdroji ve
stejné `remeslo_material_categories` řádce.

Struktura stránky (ověřeno živě 2026-08-17): na rozdíl od
Ptáček-shop.cz je tu čistý strukturovaný JSON-LD blok
(`<script type="application/ld+json">`, @graph obsahuje ItemList s
itemListElement[].item.{name,url,offers.price}), ne nutnost
parsovat HTML kartu ručně - offers.price odpovídá zobrazené ceně
S DPH (stránka vedle toho ukazuje i cenu "bez DPH" a přeškrtnutou
"cenu před slevou", ale JSON-LD offers.price je ta hlavní/aktuální
cena s DPH, stejně jako `price__base` u Ptáčka).

robots.txt (aquatopshop.cz) neuvádí Crawl-delay - použit konzervativní
10s odstup mezi kategoriemi (žádná číslem podložená hodnota od webu,
proto zvoleno o něco kratší než u Ptáčka, kde 15s bylo explicitně
dané).

Použití:
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_aquatop.py --kontrola
    api/venv/bin/python3 scripts/2026-08-17_remeslo_scrape_aquatop.py --apply
"""
import argparse
import datetime
import json
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

SUPPLIER_NAME = "Aquatopshop.cz"
BASE_URL = "https://www.aquatopshop.cz"
USER_AGENT = "Mozilla/5.0 (compatible; KonfiguratorRemesloPriceBot/1.0)"
PROFESSION_SLUG = "instalater"

# Kategorie relevantní pilotní profesi (instalatér, voda/topení) -
# (nazev_kategorie_v_DB - MUSÍ odpovídat názvu použitému ve scraperu
# pro Ptáčka, aby šlo porovnávat napříč zdroji, unit, url_cesta).
#
# Rozšířeno 2026-08-17 (bot12, Robert přes bot3: "stovky položek, ne
# jen pár desítek" + doplnění "kolena/fitinky, armatury, drobnosti -
# spojovací materiál, těsnění, malé díly") - z 1 na 22 kategorií napříč
# celým sortimentem relevantním instalatérské profesi, od velkých kusů
# (trubkové systémy) po drobnosti (těsnění, vodoměry, kotvící
# materiál). Každá URL ověřena živě (HTTP 200 + přítomný JSON-LD
# ItemList) před přidáním sem. "Kotle" a "radiátory" (topná tělesa) v
# katalogu tohoto dodavatele NEEXISTUJÍ - Aquatopshop.cz je zaměřený
# na vodo-instalatérský sortiment (voda/odpady/armatury), ne topnou
# techniku - nedoplňováno uměle, viz REMESLO_KONCEPT.md "jen hlavní
# sortiment PODLE PROFESE, NE celý katalog" (tady naopak - nenutit
# kategorie, které dodavatel vůbec nemá).
CATEGORIES = [
    ("Domácí vodárna", "ks", "/domaci-vodarny-s-ponornym-cerpadlem"),
    ("Mosazné fitinky", "ks", "/MOSAZNE-FITINKY-c1_1_2.htm"),
    ("PPR trubky a tvarovky", "ks", "/PPR-SYSTEM-c1_74_2.htm"),
    ("Kulové kohouty a ventily", "ks", "/KULOVE-KOHOUTY-VENTILY-c1_57_2.htm"),
    ("Mosazné šroubení", "ks", "/MOSAZNE-SROUBENI-c1_40_2.htm"),
    ("PE trubky (polyetylen)", "m", "/PE-POLYETHYLEN-c1_61_2.htm"),
    ("Vodovodní baterie a doplňky", "ks", "/VODOVODNI-BATERIE-A-DOPLNKY-c2_0_1.htm"),
    ("Mosazná kolena", "ks", "/MOSAZNA-KOLENA-c1_2_3.htm"),
    ("HT vnitřní odpady", "ks", "/HT-VNITRNI-ODPADY-c1_75_2.htm"),
    ("KG odpad a kanalizace", "ks", "/KG-ODPAD-KANALIZACE-c1_1528_2.htm"),
    ("PEX-AL-PEX trubky", "m", "/PEX-AL-PEX-PERT-AL-PERT-c4_251_2.htm"),
    ("CU tvarovky pájecí", "ks", "/CU-TVAROVKY-PAJECI-LETOVACI-c4_1527_2.htm"),
    ("Kotvící materiál a objímky", "ks", "/KOTVICI-MATERIAL-OBJIMKY-c1_1894_2.htm"),
    ("Vodoměry", "ks", "/VODOMERY-c1_316_2.htm"),
    ("WC příslušenství", "ks", "/wc-prislusenstvi"),
    ("Těsnící materiál", "ks", "/TESNICI-MATERIAL-c1_379_2.htm"),
    ("Sifony a výpustě", "ks", "/SIFONY-A-VYPUSTE-c14_0_1.htm"),
    ("Pojistné ventily a regulátory", "ks", "/POJISTNE-VENTILY-REGULATORY-c5_0_1.htm"),
    ("Rohové ventily", "ks", "/ROHOVE-VENTILY-c6_0_1.htm"),
    ("Nerezové flexi hadičky", "ks", "/NEREZOVE-FLEXI-HADICKY-c7_0_1.htm"),
    ("PVC trubky a spojky", "ks", "/pvc-trubky-a-spojky"),
    ("Filtrace a úprava vody", "ks", "/FILTRACE-UPRAVA-VODY-c9_0_1.htm"),
]

JSON_LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def scrape_category(url_path):
    """Vraci list (nazev, cena_czk, plna_url) pro danou kategorii, cteno
    z JSON-LD ItemList bloku (strukturovana data primo z webu, ne
    parsovani HTML karet)."""
    html = _fetch(BASE_URL + url_path)
    items = []
    for m in JSON_LD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph", [data]) if isinstance(data, dict) else data
        for node in graph:
            if not isinstance(node, dict) or node.get("@type") != "ItemList":
                continue
            for li in node.get("itemListElement", []):
                item = li.get("item") or {}
                name = item.get("name")
                url = item.get("url")
                price = (item.get("offers") or {}).get("price")
                if not name or not url or price is None:
                    continue
                items.append((name.strip(), float(price), url))
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
                print(f"Nalezeno {len(items)} položek.")
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
                # zadny explicitni Crawl-delay v robots.txt - konzervativni
                # 10s odstup mezi kategoriemi z vlastni opatrnosti.
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
