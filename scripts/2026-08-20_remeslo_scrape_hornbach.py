#!/usr/bin/env python3
"""Scraper materiálových cen z hornbach.cz pro modul 1 Řemesla
(srovnávač cen materiálu dle profese) - bot9, 2026-08-20.

ZAMĚŘENÍ (zadání Roberta): srovnávač dosud obsahoval skoro výhradně
zařizovací předměty z koupelnových e-shopů (baterie/bojlery/radiátory,
~3500 cen v 68 kategoriích - VŠECHNY instalatérské), zatímco
KALKULAČKY Řemesla počítají úplně jiný sortiment: spotřební stavební
materiál. Ověřeno dotazem do DB před psaním skriptu - v srovnávači
nebyl ANI JEDEN pytel cementu, deska polystyrenu nebo sádrokarton.
Tenhle skript proto cílí přesně na to, co kalkulačky počítají:
kamenivo, beton/cement/malta, KARI síť a výztuž, cihly a tvárnice,
tepelná izolace, omítky, sádrokarton (desky, profily, vruty), obklady
a dlažba vč. lepidel a spárovaček, podlahy s podložkami a lištami,
malířské barvy, střešní krytiny, dřevo a impregnace, zámková dlažba a
obrubníky.

**Ověření proti 5 kritériím z REMESLO_KONCEPT.md (PŘED psaním kódu):**
1. Velikost: HORNBACH Baumarkt AG, mezinárodní DIY řetězec, v ČR síť
   kamenných hobbymarketů - velká firma dle kritéria 1.
2. Dosah: pobočky napříč ČR + celostátní e-shop s dopravou.
3. Strukturovaný veřejný ceník: ANO a v nejlepší možné podobě -
   kategorie mají schema.org `ItemList` v `<script type="application/
   ld+json">` s poli name / offers.price / priceCurrency / url. Žádné
   parsování rozsypaného HTML jako u Dogusu.
4. Relevance k profesi: DIY se stavebninami - přesně chybějící
   sortiment kalkulaček (zedník, betonář, fasádník, sádrokartonář,
   obkladač, podlahář, malíř, pokrývač, tesař, dlaždič, zemní práce).
5. Šíře sortimentu: 2412 kategorií v sitemap, z toho ~440 relevantních
   ke stavebnímu materiálu - výrazně širší než dosavadní úzce
   koupelnové zdroje.

**Bot-ochrana: pozor na výklad.** První pokus (UA předstírající Chrome,
jak to dělá scraper OBI) vrátil na KAŽDÉ URL - včetně robots.txt a
sitemap - JS "Client Challenge" stránku (Fastly, 3038 B). Vypadá to
jako případ SIKO/Sanitino ("při aktivní obraně vzdát"), ale NENÍ:
se **pravdivou identifikací bota** v User-Agent server vrací normální
obsah (HTTP 200, plné HTML). Challenge tedy míří na klienty, kteří se
VYDÁVAJÍ za prohlížeč a nespustí JS - ne na slušné crawlery. Proto se
tady NEPOUŽÍVÁ maskování za Chrome: bot se představuje pravdivě a
drží se robots.txt. (Kdyby Hornbach challenge nasadil i na tuhle
cestu, platí Robertovo pravidlo: vzdát a zapsat proč - žádné
obcházení.)

**robots.txt (hornbach.cz) se respektuje doslova**: Disallow má
/checkout, /customer/, /cart/, /wishlist/, /contact/, /comparison/,
/hornbach/cms/, /ordertracking/ a **/frontend/**. Kategorie ani
produkty zakázané nejsou, žádný Crawl-delay uveden - přesto 20s
odstup dle zadání.

**Důsledek, který je potřeba znát: 8 položek na kategorii.** Server
vykreslí do JSON-LD jen prvních 8 produktů, zbytek výpisu si stránka
dotahuje GraphQL dotazem na `/frontend/query` - a `/frontend/` je
robots.txt ZAKÁZANÝ, takže se nepoužívá, i když by to technicky šlo a
dalo by řádově víc dat. Ověřeno i to, že se strop nedá zvednout
povolenou cestou (`?page=2` vrátí stránku bez ItemList, `?limit=48`/
`?perPage=48`/`?count=48` nemají vliv). Šířka se proto bere počtem
KATEGORIÍ, ne hloubkou výpisu - což odpovídá i pravidlu z konceptu
"jen hlavní sortiment, ne celý katalog".

**Nepokryto (poctivá mezera):** Hornbach CZ nemá v katalogu pálené/
betonové střešní tašky, střešní latě ani difuzní fólie (ověřeno
hledáním v sitemap) - kalkulačka Střechy tedy z tohohle zdroje dostane
jen krytiny asfaltové/plechové/plastové. Zbytek by měl pokrýt DEK
(bot11), který je typově stavebninový, ne hobby.

Idempotence: DELETE+INSERT per (kategorie, zdroj) při každém běhu -
aktuální stav ke dni scrapu, ne historie (stejný vzor jako ostatní
zdroje modulu 1).

Použití:
    api/venv/bin/python3 scripts/2026-08-20_remeslo_scrape_hornbach.py --kontrola
    api/venv/bin/python3 scripts/2026-08-20_remeslo_scrape_hornbach.py --apply
"""
import argparse
import datetime
import gzip
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
# remeslo_* tabulky zijí od 2026-08-19 ve vlastni DB "Remeslnik" -
# get_conn() z app.py miri na hlavni DB (viz nalez bot14).
from remeslo import get_remeslo_conn as get_conn  # noqa: E402
import remeslo_price_history  # noqa: E402

SUPPLIER_NAME = "HORNBACH.cz"
SUPPLIER_URL = "https://www.hornbach.cz/"
BASE_URL = "https://www.hornbach.cz/c/"
# Pravdiva identifikace bota - viz rozbor bot-ochrany v docstringu.
# ZADNE maskovani za Chrome (to je presne to, co server challenguje).
USER_AGENT = "LogimanRemesloBot/1.0 (+https://remeslnik.pro; srovnavac cen materialu pro remeslniky)"
REQUEST_DELAY = 20

# (nazev kategorie v DB, jednotka, [slugy profesi], cesta v katalogu).
# Nazvy jsou nove - dosavadnich 68 kategorii je vyhradne instalaterskych,
# takze neni s cim slucovat (overeno SELECTem pred psanim). Jednotka je
# jednotka, v jake dodavatel polozku PRODAVA (pytel/balení = "bal"),
# ne jednotka kalkulacky - srovnavac porovnava ceny produktu, prepocet
# na m2 je vec kalkulacky.
CATEGORIES = [
    # --- zdivo, sucha smes, vyztuz (kalkulacky Zdeni, Betonaz) ---
    ("Cihly", "ks", ["zednik"], "stavebniny/hruba-stavba/zdivo/cihly/S22267/"),
    ("Tvárnice porobetonové", "ks", ["zednik"], "stavebniny/hruba-stavba/zdivo/porobeton/S22268/"),
    ("Ztracené bednění", "ks", ["zednik", "betonar"], "stavebniny/hruba-stavba/zdivo/ztracene-bedneni/S21821/"),
    ("Malta", "bal", ["zednik"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/malta/S25635/"),
    ("Cement", "bal", ["zednik", "betonar"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/cement/S25636/"),
    ("Vápno", "bal", ["zednik"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/vapno/S25637/"),
    ("Betonová směs", "bal", ["betonar"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/beton/S25634/"),
    ("Betonové potěry", "bal", ["betonar", "podlahar"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/betonove-potery/S11712/"),
    ("Samonivelační stěrky", "bal", ["podlahar"], "stavebniny/hruba-stavba/suche-smesi-a-stavebni-chemie/samonivelacni-sterky/S25639/"),
    ("Stavební ocel (výztuž)", "ks", ["betonar"], "stavebniny/hruba-stavba/stavebni-ocel/S11717/"),
    ("KARI sítě", "ks", ["betonar"], "zelezarstvi/profily-a-plechy/kari-site/S12015/"),
    ("Štěrk a kamenivo", "bal", ["zemni-prace", "dlazdic-dlazba"], "zahrada/tvorba-zahrady/kameny/sterk/S12290/"),
    ("Montážní pěny, silikony a tmely", "ks", ["univerzalni-remeslnik"], "stavebniny/hruba-stavba/montazni-peny-silikony-a-tmely/S20643/"),
    ("Chemické kotvy", "ks", ["zednik", "betonar"], "stavebniny/hruba-stavba/montazni-peny-silikony-a-tmely/chemicka-kotva/S28559/"),

    # --- omitky (Zdeni, Fasada) ---
    ("Jádrové omítky", "bal", ["zednik"], "stavebniny/hruba-stavba/omitky/jadrove-omitky/S22737/"),
    ("Fasádní omítky", "bal", ["fasadnik"], "stavebniny/hruba-stavba/omitky/fasadni-omitky/S22739/"),
    ("Omítkové profily", "ks", ["zednik", "fasadnik"], "stavebniny/hruba-stavba/omitky/omitkove-profily/S22740/"),
    ("Sanační omítky", "bal", ["zednik"], "stavebniny/hruba-stavba/omitky/sanacni-omitky/S22824/"),

    # --- zatepleni a izolace (Fasada a zatepleni) ---
    ("Tepelná izolace", "ks", ["fasadnik"], "stavebniny/tepelna-izolace/S11686/"),
    ("Dřevovláknitá izolace", "ks", ["fasadnik"], "stavebniny/tepelna-izolace/drevovlaknita-izolace/S34026/"),
    ("Hmoždinky do polystyrenu", "bal", ["fasadnik"], "zelezarstvi/spojovaci-material/hmozdinky/hmozdinky-do-polystyrenu/S21383/"),
    ("Hydroizolace", "ks", ["zednik", "fasadnik"], "stavebniny/hydroizolace/S11719/"),
    ("Hydroizolační stěrky", "bal", ["obkladac"], "stavebniny/hydroizolace/hydroizolacni-sterky/S25680/"),

    # --- sadrokarton (Sadrokarton) ---
    ("Sádrokartonové desky", "ks", ["sadrokartonar"], "stavebniny/sucha-vystavba/sadrokartonove-desky/S11676/"),
    ("Suchá výstavba - profily a příslušenství", "ks", ["sadrokartonar"], "stavebniny/sucha-vystavba/S11674/"),
    ("Stropní závěsný systém", "ks", ["sadrokartonar"], "stavebniny/sucha-vystavba/stropni-zavesny-system/S11684/"),
    ("Cementotřískové desky", "ks", ["sadrokartonar"], "stavebniny/sucha-vystavba/cementotriskove-desky/S22046/"),
    ("Vruty do sádrokartonu", "bal", ["sadrokartonar"], "zelezarstvi/spojovaci-material/vruty-do-sadrokartonu/pan-head/S11887/"),

    # --- obklady a dlazby (Obklady a dlazby) ---
    ("Obklady", "m2", ["obkladac"], "podlahove-krytiny-obklady-a-dlazby/obklady-dlazby-a-prislusenstvi-obkladu-a-dlazeb/obklady/S14081/"),
    ("Dlažby", "m2", ["obkladac", "dlazdic-dlazba"], "podlahove-krytiny-obklady-a-dlazby/obklady-dlazby-a-prislusenstvi-obkladu-a-dlazeb/dlazby/S11831/"),
    ("Chemie pro obklady a dlažby", "bal", ["obkladac"], "podlahove-krytiny-obklady-a-dlazby/obklady-dlazby-a-prislusenstvi-obkladu-a-dlazeb/chemie-pro-obklady-a-dlazby/S11839/"),
    ("Nivelační hmoty", "bal", ["obkladac", "podlahar"], "podlahove-krytiny-obklady-a-dlazby/obklady-dlazby-a-prislusenstvi-obkladu-a-dlazeb/chemie-pro-obklady-a-dlazby/nivelacni-hmoty/S11842/"),
    ("Materiál pro obkladače", "ks", ["obkladac"], "podlahove-krytiny-obklady-a-dlazby/obklady-dlazby-a-prislusenstvi-obkladu-a-dlazeb/material-pro-obkladace/S11838/"),

    # --- podlahy (Podlahy) ---
    ("Laminátové podlahy", "m2", ["podlahar"], "podlahove-krytiny-obklady-a-dlazby/podlahove-krytiny/laminatove-podlahy/S11807/"),
    ("Vinylové podlahy", "m2", ["podlahar"], "podlahove-krytiny-obklady-a-dlazby/podlahove-krytiny/vinylove-podlahy/S11809/"),
    ("Dřevěné podlahy", "m2", ["podlahar"], "podlahove-krytiny-obklady-a-dlazby/podlahove-krytiny/drevene-podlahy/S11808/"),
    ("Podložky pod podlahy", "m2", ["podlahar"], "podlahove-krytiny-obklady-a-dlazby/podlahove-krytiny/prislusenstvi-pro-podlahy/krocejova-izolace/podlozky-univerzalni/S29496/"),
    ("Podlahové lišty a tvarovky", "ks", ["podlahar"], "podlahove-krytiny-obklady-a-dlazby/podlahove-krytiny/prislusenstvi-pro-podlahy/listy-a-tvarovky/S25923/"),

    # --- malovani (Malovani) ---
    ("Interiérové barvy a omítky", "ks", ["malir"], "barvy-tapety-a-oblozeni-sten/barvy-laky/interierove-barvy-omitky/S12056/"),
    ("Fasádní barvy", "ks", ["malir", "fasadnik"], "barvy-tapety-a-oblozeni-sten/barvy-laky/fasadni-barvy/S12069/"),
    ("Penetrační nátěry", "ks", ["malir"], "barvy-tapety-a-oblozeni-sten/malirske-a-tapetovaci-prislusenstvi/prislusenstvi-pro-tapetovani/penetracni-natery-pod-tapety/S12100/"),
    ("Tmelicí a stěrkové hmoty", "bal", ["malir", "sadrokartonar"], "barvy-tapety-a-oblozeni-sten/tmelici-a-sterkove-hmoty/S12035/"),

    # --- strecha (Strechy) - viz "nepokryto" v docstringu ---
    ("Střešní krytiny", "ks", ["pokryvac"], "stavebniny/stresni-krytiny/S11703/"),
    ("Asfaltové střešní krytiny", "ks", ["pokryvac"], "stavebniny/stresni-krytiny/asfaltove-stresni-krytiny/S11704/"),
    ("Plechové střešní krytiny", "ks", ["pokryvac"], "stavebniny/stresni-krytiny/plechove-stresni-krytiny/S11706/"),

    # --- drevo (Pergoly, tesarina) ---
    ("Dřevěné hranoly", "ks", ["truhlar-tesar"], "drevo-okna-a-dvere/drevo/stavebni-drevo/drevene-hranoly/S11746/"),
    ("Stavební dřevo", "ks", ["truhlar-tesar"], "drevo-okna-a-dvere/drevo/stavebni-drevo/S11672/"),
    ("Nátěry a ochrana dřeva", "ks", ["truhlar-tesar", "malir"], "barvy-tapety-a-oblozeni-sten/barvy-laky/natery-a-ochrana-dreva/S12063/"),

    # --- zamkova dlazba (Zamkova dlazba) ---
    ("Zámková dlažba", "m2", ["dlazdic-dlazba"], "zahrada/tvorba-zahrady/zahradni-stavebniny/venkovni-dlazby/zamkove-dlazby/S31559/"),
    ("Betonové dlažby", "m2", ["dlazdic-dlazba"], "zahrada/tvorba-zahrady/zahradni-stavebniny/venkovni-dlazby/betonove-dlazby/S20770/"),
    ("Betonové obrubníky a palisády", "ks", ["dlazdic-dlazba"], "zahrada/tvorba-zahrady/zahradni-stavebniny/betonove-obrubniky-a-palisady/S12248/"),
]

_LD_JSON_RE = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
_CHALLENGE_MARK = "Client Challenge"


class ActiveDefence(Exception):
    """Server misto obsahu vratil JS challenge - viz pravidlo 'pri
    aktivni obrane vzdat', necekat na to donekonecna."""


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    last_exc = None
    for backoff in (0, 30, 90):
        if backoff:
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", errors="replace")
                if _CHALLENGE_MARK in text:
                    raise ActiveDefence(url)
                return text
        except urllib.error.URLError as exc:
            last_exc = exc
    raise last_exc


def _parse_products(html_text):
    """Cteni schema.org ItemList (JSON-LD), ne regex nad HTML - dodavatel
    ho publikuje sam pro vyhledavace, takze je to nejstabilnejsi
    dostupna podoba dat."""
    items = []
    for block in _LD_JSON_RE.findall(html_text):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if data.get("@type") != "ItemList":
            continue
        for entry in data.get("itemListElement", []):
            product = entry.get("item") or {}
            name = (product.get("name") or "").strip()
            offers = product.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            offers = offers or {}
            if (offers.get("priceCurrency") or "CZK") != "CZK":
                continue  # cizi mena by v ceniku byla zavadejici
            try:
                price = float(offers.get("price"))
            except (TypeError, ValueError):
                continue
            url = offers.get("url") or product.get("url") or ""
            if name and price > 0:
                items.append((name, price, url))
    return items


def main():
    ap = argparse.ArgumentParser()
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--kontrola", action="store_true", help="jen vypsat, nic nezapisovat")
    grp.add_argument("--apply", action="store_true", help="skutecne zapsat do DB")
    ap.add_argument("--limit", type=int, default=0, help="zpracovat jen prvnich N kategorii (ladeni)")
    args = ap.parse_args()

    categories = CATEGORIES[: args.limit] if args.limit else CATEGORIES

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM remeslo_price_sources WHERE supplier_name=%s", (SUPPLIER_NAME,))
            row = cur.fetchone()
            if row:
                source_id = row["id"]
            elif args.apply:
                cur.execute(
                    "INSERT INTO remeslo_price_sources (supplier_name, website, origin) VALUES (%s,%s,%s)",
                    (SUPPLIER_NAME, SUPPLIER_URL, "scrape_pilot"),
                )
                source_id = cur.lastrowid
                conn.commit()
                print(f"Založen nový zdroj: {SUPPLIER_NAME} (id={source_id})")
            else:
                source_id = None
                print(f"[kontrola] Zdroj '{SUPPLIER_NAME}' zatím neexistuje, založil by se.")

            cur.execute("SELECT id, slug FROM remeslo_professions")
            prof_ids = {r["slug"]: r["id"] for r in cur.fetchall()}
            missing = {s for _, _, slugs, _ in categories for s in slugs} - set(prof_ids)
            if missing:
                print(f"CHYBA: neznámé profese v seznamu: {sorted(missing)}")
                sys.exit(1)

            total_written = 0
            skipped = []
            for cat_name, unit, prof_slugs, path in categories:
                cur.execute("SELECT id FROM remeslo_material_categories WHERE name=%s", (cat_name,))
                cat_row = cur.fetchone()
                if cat_row:
                    category_id = cat_row["id"]
                elif args.apply:
                    cur.execute(
                        "INSERT INTO remeslo_material_categories (name, unit) VALUES (%s,%s)",
                        (cat_name, unit),
                    )
                    category_id = cur.lastrowid
                    print(f"Založena nová kategorie: {cat_name} (id={category_id})")
                else:
                    category_id = None

                print(f"\n== {cat_name} [{', '.join(prof_slugs)}] ==")
                try:
                    items = _parse_products(_fetch(BASE_URL + path))
                except ActiveDefence:
                    # Zadani Roberta: pri aktivni obrane vzdat, ne obchazet.
                    print("PŘERUŠENO: server vrátil JS challenge místo obsahu "
                          "(aktivní obrana) - viz docstring, nescrapovat dál.")
                    conn.commit()
                    sys.exit(2)
                except urllib.error.URLError as exc:
                    print(f"PŘESKOČENO (síťová chyba i po retry): {exc}")
                    skipped.append(cat_name)
                    time.sleep(REQUEST_DELAY)
                    continue

                print(f"Nalezeno {len(items)} položek.")
                for name, price, _ in items[:3]:
                    print(f"   {name[:66]:66s} {price:>9.2f} Kč")
                if len(items) > 3:
                    print(f"   ... a dalších {len(items) - 3}")
                if not items:
                    skipped.append(cat_name)

                if args.apply and category_id and source_id:
                    for slug in prof_slugs:
                        cur.execute(
                            "INSERT IGNORE INTO remeslo_material_category_professions "
                            "(category_id, profession_id) VALUES (%s,%s)",
                            (category_id, prof_ids[slug]),
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
                    for name, price, url in items:
                        cur.execute(
                            "INSERT INTO remeslo_material_prices "
                            "(category_id, source_id, product_name, price_czk, product_url) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (category_id, source_id, name, price, url),
                        )
                    total_written += len(items)

                # commit po KAZDE kategorii - dlouha transakce jinak drzi
                # MDL zamek a blokuje cizi migrace (nalez bot13 u Sanitina,
                # poucenie prevzato od bot10)
                conn.commit()
                time.sleep(REQUEST_DELAY)

            print("\n" + "=" * 60)
            if args.apply:
                print(f"OK - zapsáno {total_written} cenových záznamů z {len(categories)} kategorií.")
            else:
                print(f"[kontrola] Nic nezapsáno (dry-run), {len(categories)} kategorií projito.")
            if skipped:
                print(f"Bez položek/přeskočeno ({len(skipped)}): {', '.join(skipped)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
