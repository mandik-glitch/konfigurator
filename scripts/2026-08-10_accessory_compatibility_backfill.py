"""
Doplneni kompatibility prislusenstvi/spojek s profily (Robert: "chci
filtraci i na to aby prichozi na eshop mohl velmi rychle pochopit
ktere prislusenstvi nebo spojka je kompatibilní se kterým profilem").

Zamerne ZADNY novy sloupec - znovupouziva `cross_section_label`/
`groove_family` na `shop_products` (stejne jako profily, viz
sql/2026-08-10_product_cross_section_groove.sql), jen s jinou
semantikou u prislusenstvi:
  - groove_family: POZADOVANA drazka (6/8/10) - produkt sedi jen na
    profil se stejnou drazkou.
  - cross_section_label: KONKRETNI pozadovany prurez, NEBO NULL =
    sedi na JAKYKOLI prurez v ramci te drazkove rodiny (typicky
    sroubovaci/vnitrni spojky do drazky - nejsou vazane na konkretni
    rozmer profilu, jen na sirku drazky).

Cely katalog prislusenstvi/spojek ma SKU s prefixem "2." (oddelene od
profilu "1.x" - overeno: 434/537 aktivnich produktu ma SKU zacinajici
"2.", cistý rozestup bez prekryvu). Napric temito 434 produkty ale
NENI jednotny format SKU (na rozdil od profilu) - nekolik desitek
podskupin s ruznou logikou. Misto rucniho rozepsani kazde podskupiny
zvlast pouzit 2 nezavisle metody, prvni uspesna vyhrava:

  1. TEXT NAZVU (nejspolehlivejsi, casto doslovny vyrobcem pouzity
     popis): "drážka 8 mm"/"v drážce 8 mm", "K8"/"K10" oznaceni,
     "M8"/"M10" zavitovy rozmer (jen 6/8/10 - M4/M5 NEMAJI zname
     mapovani na drazkovou rodinu, zamerne vynechany). Prurez z
     "NNxNN" vzoru v nazvu (s negativnim lookbehind na "M", aby
     "M10x30" - zavit x delka sroubu - nebylo omylem cteno jako
     prurez 10x30).
  2. SKU 4. tecka-segment == "06"/"08"/"10" (fallback, kdyz nazev
     drazku vubec nezminuje - overeno na vzorku ze pokryva cca 53 %
     produktu, napr. "Třícestná hranatá rohová spojka 20x20" ma
     drazku jen v SKU: "2.2.001.06.2020.08").

Produkty, kde se nepodarilo urcit ani drazku, se PRESKAKUJI (zadne
hadani) - vypisou se zvlast pro rucni kontrolu. Idempotentni: aktualizuje
jen radky s groove_family IS NULL (nemeni uz drive rucne/jinak
nastavene hodnoty).

DULEZITE: pred --apply si VZDY projdi cely dry-run vypis rucne - jde o
tvrzeni "tohle sedi k vasemu profilu" viditelne primo zakaznikovi,
spatny zapis by mohl doporucit nekompatibilni kombinaci.
"""
import json
import re
import sys

import pymysql

from _env import load_env as _load_env

_cfg = _load_env()
DB = dict(
    host=_cfg["DB_HOST"], port=int(_cfg.get("DB_PORT", 3306)), user=_cfg["DB_USER"],
    password=_cfg["DB_PASSWORD"], database=_cfg["DB_NAME"], charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

VALID_GROOVES = {"6", "8", "10"}
# bot5 2026-08-10: "mm" byl puvodne POVINNY, coz u nazvu bez nej (napr.
# "Obdélníková matice M6 - drážka 8", tedy bez "mm" za cislem) padalo
# skrz na slabsi GROOVE_M_RE heuristiku - ta cte velikost ZAVITU (M6),
# ne sirku drazky, a u matic/T-matic se casto LISI (presne tenhle
# produkt je M6 zavit do 8mm drazky). Nalezeno rucni kontrolou dry-run
# vystupu pred --apply (viz docstring vyse - proto se kontroluje rucne).
# "mm" je ted VOLITELNE, aby "drážka 8" bez jednotky melo prednost
# pred M-cislem, presne jak by melo.
GROOVE_TEXT_RE = re.compile(r"dr[áa]žk[aeyu]?\D{0,15}?(\d{1,2})\b", re.IGNORECASE)
GROOVE_K_RE = re.compile(r"\bK(6|8|10)\b")
GROOVE_M_RE = re.compile(r"\bM(6|8|10)\b(?!\d)")
GROOVE_SKU_RE = re.compile(r"^\d+\.\d+\.\d+\.(\d{2})\.")
GROOVE_SKU_CODE = {"06": "6", "08": "8", "10": "10"}
CROSS_SECTION_RE = re.compile(r"(?<!M)\b(\d{2,3})\s*[x×]\s*(\d{2,3})\b")


def guess_groove(sku, name):
    m = GROOVE_TEXT_RE.search(name)
    if m and m.group(1) in VALID_GROOVES:
        return m.group(1), "nazev:drazka"
    m = GROOVE_K_RE.search(name)
    if m:
        return m.group(1), "nazev:K"
    # GROOVE_M_RE (zavit M6/M8/M10 v nazvu) ZAMERNE NEPOUZITO jako zdroj
    # drazky - rucni kontrola dry-run vystupu odhalila, ze zavit sroubu
    # NENI spolehlivy proxy pro sirku drazky (napr. "Upínač patky 30x60"
    # existuje v M6/M8/M10 variantach, ale profil 30x60 ma podle
    # VLASTNOSTI_PROFILU.md jen JEDNU drazkovou rodinu - M-cislo tam
    # zjevne popisuje variantu upevnovaciho sroubu, ne pozadovanou
    # drazku profilu). Radeji produkt preskocit (chybi info) nez tvrdit
    # nejistou kompatibilitu zakaznikovi.
    m = GROOVE_SKU_RE.match(sku or "")
    if m and m.group(1) in GROOVE_SKU_CODE:
        return GROOVE_SKU_CODE[m.group(1)], "sku:pozice4"
    return None, None


def guess_cross_section(name):
    m = CROSS_SECTION_RE.search(name)
    if m:
        return f"{int(m.group(1))}x{int(m.group(2))}"
    return None


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, sku, name FROM shop_products
        WHERE active=1 AND is_archived=0 AND sku LIKE '2.%' AND groove_family IS NULL
    """)
    rows = cur.fetchall()

    matched = []
    unmatched = []
    for r in rows:
        groove, source = guess_groove(r["sku"], r["name"])
        if not groove:
            unmatched.append(r)
            continue
        cross_section = guess_cross_section(r["name"])
        matched.append((r["id"], r["sku"], r["name"], groove, cross_section, source))

    print(f"Kandidatu (sku LIKE '2.%', dosud bez groove_family): {len(rows)}")
    print(f"  -> groove urcena: {len(matched)}")
    print(f"  -> groove NEURCENA (preskoceno, nutna rucni kontrola): {len(unmatched)}")

    print("\n--- VSECHNY urcene (zkontroluj rucne pred --apply) ---")
    for pid, sku, name, groove, cross_section, source in matched:
        cs = cross_section or "(jakykoli prurez v drazce)"
        print(f"  #{pid} {sku:30s} {name!r:70s} -> drazka={groove:>2s}mm prurez={cs:22s} [{source}]")

    print("\n--- NEURCENE (preskoceno) ---")
    for r in unmatched:
        print(f"  #{r['id']} {r['sku']} {r['name']!r}")

    if not matched:
        print("\nNic k zapisu.")
        return

    backup = [{"id": pid, "sku": sku, "name": name} for pid, sku, name, _, _, _ in matched]
    backup_path = "backups/accessory_compatibility_backfill_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"\nZaloha {len(backup)} radku (puvodni stav pred zapisem, oba sloupce byly NULL) -> {backup_path}")

    if dry_run:
        print(f"\nDRY RUN - {len(matched)} pripraveno, 0 zapsano. Spust s --apply pro skutecny zapis.")
        return

    for pid, sku, name, groove, cross_section, source in matched:
        cur.execute(
            "UPDATE shop_products SET cross_section_label=%s, groove_family=%s WHERE id=%s",
            (cross_section, groove, pid),
        )
    conn.commit()
    print(f"Zapsano {len(matched)} produktu.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
