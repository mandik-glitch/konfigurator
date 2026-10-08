#!/usr/bin/env python3
"""Vecerni davkove zpracovani fronty pozadavku na dohledani polozky do
Srovnavace (Modul 1, bot9, 2026-08-20). REMESLO_KONCEPT.md "Dohledani
polozky na vyzadani" - Robert: "kazdy registrovany si muze pridat
polozky ke srovnani, ktere tam nemame, a my mu je automaticky
doplnime - databaze poroste podle skutecne poptavky, ne podle naseho
odhadu."

DULEZITE - Robertovo vyslovne rozhodnuti o architekture:
- ZADNE externi vyhledavaci API, zadny placeny klic - hleda se pres
  VLASTNI vyhledavani kazdeho dodavatele (staticke HTML/JSON), presne
  jako davkove kategoricke scrapery scripts/*_scrape_*.py.
- NENI to okamzite - pozadavky se behem dne hromadi ve fronte
  (remeslo_material_requests, status='pending') a zpracuji se
  DAVKOVE JEDNOU DENNE VECER.
- Spousti se RUCNE Z TERMINALU (bot ho spusti) - ZADNY cron, ZADNY
  worker na pozadi.

Rozdeleni prace (koordinovano s konfigurator-c8/bot11, 2026-08-20):
- api/remeslo_price_search.py (bot11/c8) - "search_supplier(supplier_name,
  query) -> list[{"name","url","price_czk"|None}]" per dodavatel,
  cisté funkce, zadne DB/side-efekty.
- Tenhle skript (bot9) - orchestrace: nacte frontu, zavola search per
  dodavatel, aplikuje matching heuristiku (STEJNA jako
  remeslo._match_pricelist_item - presna shoda nazvu, pak podretezec,
  ZADNE fuzzy/AI), dotahne chybejici cenu pres uz hotovy
  remeslo_price_refresh._EXTRACTORS na URL kandidata, zalozi/znovupouzije
  remeslo_material_categories + remeslo_material_prices (obe URL dle
  "dve URL cesty" pravidla), oznaci pozadavek jako done/not_found.

Politika nalezu (Robert 2026-08-20): publikuje se i pri CASTECNEM
pokryti (nalezeno jen u 1-2 z vice zkousenych dodavatelu) - lepsi
polozka s nekolika dodavateli nez zadna. Transparentne se uklada
suppliers_tried/suppliers_found, UI to ma ukazat, ne predstirat
uplnost. Nenajde-li se NIKDE, stav 'not_found' (zadne nekonecne
opakovani, remeslnik muze zadat znovu s presnejsim nazvem).

Zadne schvalovani navic - rucni vecerni spusteni z terminalu UZ JE
kontrolni bod (stejna duvera jako u davkovych kategorickych scraperu
bez schvalovaci fronty).

Pouziti: python scripts/2026-08-20_remeslo_material_request_batch.py
         python scripts/2026-08-20_remeslo_material_request_batch.py --dry-run

--dry-run (bot10, 2026-08-20, hloubkova kontrola na Robertovo zadani
"spust ho nanecisto a over, ze funguje") - provede VSECHNO stejne
(nacte frontu, zavola search_supplier per dodavatel, matching, dotazeni
chybejici ceny pres extraktory) az na SAMOTNY zapis do DB - zadny
INSERT/UPDATE/commit, fronta zustava beze zmeny stavu ('pending').
Vypis do konzole je STEJNY jako ostry beh (vc. 'NALEZENO'/'NENALEZENO'
za kazdy pozadavek), jen posledni radek jasne oznaci, ze slo o nanecisto
beh a nic se nezapsalo.
"""
import argparse
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
for _line in open(os.path.join(os.path.dirname(__file__), "..", "api", ".env")):
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))

import remeslo
import remeslo_price_refresh

try:
    import remeslo_price_search
except ImportError:
    remeslo_price_search = None  # modul jeste nemusi existovat - viz main()

# Bot-f7uv zivy nalez 2026-08-20 (GET /compare, "cena na vyzadani"):
# "bounded timeout" bounded jen PER POKUS nestaci, potreba bounded
# CELKEM - stejna past by tu hrozila u velke fronty/pomaleho dodavatele.
MAX_TOTAL_SECONDS = 25 * 60
# "Rucni zadani (admin)" ma supplier_name bez odpovidajiciho search
# adapteru zamerne - neni to skutecny e-shop k prohledavani.
EXCLUDED_SUPPLIER = "Ruční zadání (admin)"


def _tokens(normalized_text):
    return {t for t in normalized_text.split() if len(t) > 2}  # kratka slova (predlozky) mimo


def _pick_best_match(candidates, target_normalized):
    """Puvodne presna shoda + podretezec, STEJNA heuristika jako
    remeslo._match_pricelist_item - ZAMENENO za prekryv slov po
    zivem testu (mock_remeslo_price_search.py): "Lepidlo na obklady
    XY" vs. realny nazev produktu "Lepidlo na obklady XY 25kg" NENI
    podretezec ani jednim smerem (znacka/rozmer navic), a presne tak
    vypadaji BEZNE nazvy e-shopovych produktu, ne kratke generice
    nazvy z Ceniku, na ktere byl puvodni _match_pricelist_item psany.

    Bere PRVNIHO kandidata (= poradi, jak ho vratilo VLASTNI
    vyhledavani dodavatele - jeho relevance razeni, nepresazujeme ho
    vlastnim), ktery ma bud presnou shodu, nebo aspon polovinu
    vyznamovych slov dotazu spolecnych s nazvem. Porad zadne
    fuzzy/AI - jen mnozinovy prunik slov, snadno vysvetlitelne."""
    target_tokens = _tokens(target_normalized)
    if not target_tokens:
        return None
    for c in candidates:
        cname = remeslo._normalize_text(c.get("name") or "")
        if not cname:
            continue
        if cname == target_normalized:
            return c
        overlap = len(target_tokens & _tokens(cname))
        if overlap / len(target_tokens) >= 0.5:
            return c
    return None


def _resolve_price(source_name, match):
    """Kandidat z vyhledavani muze, ale nemusi, obsahovat cenu rovnou
    (napr. Mereo.cz /search/suggest vraci jen nazev/URL) - kdyz ne,
    dotahne se pres uz hotovy remeslo_price_refresh extraktor na
    produktovou stranku (ta uz je overena S DPH pro vsech 8 dodavatelu)."""
    if match.get("price_czk") is not None:
        return match["price_czk"]
    if not remeslo_price_refresh.supplier_supported(source_name):
        return None
    try:
        html = remeslo_price_refresh._fetch(match["url"])
    except Exception:
        return None
    extractor = remeslo_price_refresh._EXTRACTORS[source_name]
    try:
        return extractor(html)
    except Exception:
        return None


def _find_or_create_category(cur, requested_name, unit, profession_id):
    """Presna shoda nazvu (normalizovana) proti JIZ existujicim
    kategoriim -> znovupouzije (nechceme "Zdici malta" a "Zdici malta 2"
    vedle sebe jen kvuli dvema mirne odlisne napsanym pozadavkum).
    Zadny podretezec tady zamerne - substring match napric 148
    kategoriemi by snadno spletl uzsi/sirsi kategorii (napr. "Malta"
    by se podretezcove trefilo do "Zdici malta")."""
    target = remeslo._normalize_text(requested_name)
    cur.execute("SELECT id, name FROM remeslo_material_categories")
    for row in cur.fetchall():
        if remeslo._normalize_text(row["name"]) == target:
            cat_id = row["id"]
            break
    else:
        cur.execute(
            "INSERT INTO remeslo_material_categories (name, unit) VALUES (%s,%s)",
            (requested_name, unit),
        )
        cat_id = cur.lastrowid
    cur.execute(
        "INSERT IGNORE INTO remeslo_material_category_professions (category_id, profession_id) VALUES (%s,%s)",
        (cat_id, profession_id),
    )
    return cat_id


def _upsert_price(cur, category_id, source_id, name, url, price_czk, now):
    """Dve URL cesty (TRVALE PRAVIDLO, REMESLO_KONCEPT.md) - u cerstve
    dohledane polozky jsou product_url i price_source_url STEJNA URL
    (jedina, kterou jsme fetchli), presne tak, jak uz pravidlo pocita
    s dodavateli bez odděleneho zdroje ceny - vedome slabsi mechanismus,
    ne tise predstirany silnejsi."""
    cur.execute(
        "SELECT id FROM remeslo_material_prices WHERE category_id=%s AND source_id=%s",
        (category_id, source_id),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE remeslo_material_prices SET product_name=%s, price_czk=%s, product_url=%s, "
            "price_source_url=%s, scraped_at=%s WHERE id=%s",
            (name, price_czk, url, url, now, existing["id"]),
        )
    else:
        cur.execute(
            "INSERT INTO remeslo_material_prices "
            "(category_id, source_id, product_name, price_czk, product_url, price_source_url, scraped_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (category_id, source_id, name, price_czk, url, url, now),
        )


def process_request(req, sources, started):
    """Zkusi vsechny podporovane dodavatele pro JEDEN pozadavek. Vraci
    (tried: int, found: list[(source_row, name, url, price_czk)])."""
    target = remeslo._normalize_text(req["requested_name"])
    tried = 0
    found = []
    for source in sources:
        if time.monotonic() - started > MAX_TOTAL_SECONDS:
            print(f"    [casovy rozpocet vycerpan behem zpracovani #{req['id']}, zbyli dodavatele preskoceni]")
            break
        if not remeslo_price_search.search_supported(source["supplier_name"]):
            continue
        tried += 1
        try:
            candidates = remeslo_price_search.search_supplier(source["supplier_name"], req["requested_name"])
        except Exception as exc:
            print(f"    {source['supplier_name']}: chyba hledani ({exc})")
            continue
        if not candidates:
            print(f"    {source['supplier_name']}: 0 kandidatu")
            continue
        match = _pick_best_match(candidates, target)
        if not match:
            print(f"    {source['supplier_name']}: {len(candidates)} kandidatu, zadny neprosel shodou nazvu")
            continue
        price = _resolve_price(source["supplier_name"], match)
        if price is None:
            print(f"    {source['supplier_name']}: shoda '{match['name']}', ale cenu se nepodarilo zjistit")
            continue
        print(f"    {source['supplier_name']}: NALEZENO '{match['name']}' za {price} Kc")
        found.append((source, match["name"], match["url"], price))
    return tried, found


def main(dry_run=False):
    if remeslo_price_search is None:
        print("CHYBA: api/remeslo_price_search.py jeste neexistuje - dohledavaci modul "
              "(bot11/konfigurator-c8) jeste neni hotovy. Konci beze zmen.")
        sys.exit(1)

    if dry_run:
        print("*** NANECISTO (--dry-run) - zadny zapis do DB, fronta zustane beze zmeny ***\n")

    started = time.monotonic()
    conn = remeslo.get_remeslo_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM remeslo_material_requests WHERE status='pending' ORDER BY created_at")
            pending = cur.fetchall()
            cur.execute(
                "SELECT id, supplier_name FROM remeslo_price_sources WHERE active=1 AND supplier_name != %s",
                (EXCLUDED_SUPPLIER,),
            )
            sources = cur.fetchall()

        supported = [s["supplier_name"] for s in sources if remeslo_price_search.search_supported(s["supplier_name"])]
        print(f"Fronta: {len(pending)} pozadavku. Podporovani dodavatele pro hledani: "
              f"{', '.join(supported) if supported else '(zadny)'}.")

        done_n = not_found_n = 0
        for req in pending:
            if time.monotonic() - started > MAX_TOTAL_SECONDS:
                print(f"\nCasovy rozpocet ({MAX_TOTAL_SECONDS}s) vycerpan - zbyle pozadavky "
                      f"pockaji na pristi vecer, zustavaji 'pending'.")
                break
            print(f"\n--- #{req['id']}: '{req['requested_name']}' ({req['unit']}) ---")
            with conn.cursor() as cur:
                cur.execute("SELECT profession_id FROM remeslo_craftsmen WHERE id=%s", (req["craftsman_id"],))
                craftsman = cur.fetchone()
            if not craftsman:
                print("  remeslnik uz neexistuje, preskakuji")
                continue

            tried, found = process_request(req, sources, started)
            now = datetime.datetime.now()
            if dry_run:
                # Zadny zapis - jen ohlas, co by se stalo (kategorie
                # se JEN CTE, nikdy nezaklada, at dry-run nemuze
                # vytvorit "ghost" kategorii, kterou by pak ostry beh
                # nenasel jako jiz existujici pod jinym pravopisem).
                if found:
                    print(f"  -> (nanecisto) NALEZENO u {len(found)}/{tried} zkousenych dodavatelu, "
                          f"zapsalo by se: status='done'")
                    done_n += 1
                else:
                    print(f"  -> (nanecisto) NENALEZENO (zkouseno {tried} dodavatelu), "
                          f"zapsalo by se: status='not_found'")
                    not_found_n += 1
                continue
            with conn.cursor() as cur:
                if found:
                    cat_id = _find_or_create_category(cur, req["requested_name"], req["unit"], craftsman["profession_id"])
                    for source, name, url, price in found:
                        _upsert_price(cur, cat_id, source["id"], name, url, price, now)
                    cur.execute(
                        "UPDATE remeslo_material_requests SET status='done', matched_category_id=%s, "
                        "suppliers_tried=%s, suppliers_found=%s, processed_at=%s WHERE id=%s",
                        (cat_id, tried, len(found), now, req["id"]),
                    )
                    print(f"  -> NALEZENO u {len(found)}/{tried} zkousenych dodavatelu (kategorie #{cat_id})")
                    done_n += 1
                else:
                    cur.execute(
                        "UPDATE remeslo_material_requests SET status='not_found', suppliers_tried=%s, "
                        "suppliers_found=0, processed_at=%s WHERE id=%s",
                        (tried, now, req["id"]),
                    )
                    print(f"  -> NENALEZENO (zkouseno {tried} dodavatelu)")
                    not_found_n += 1
            conn.commit()
    finally:
        conn.close()

    elapsed = time.monotonic() - started
    print(f"\nHotovo za {elapsed:.0f}s - nalezeno {done_n}, nenalezeno {not_found_n}, "
          f"celkem zpracovano {done_n + not_found_n}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Nic nezapisuje do DB, jen ohlasi, co by se stalo.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
