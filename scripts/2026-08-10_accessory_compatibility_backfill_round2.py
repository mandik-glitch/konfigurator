"""
Druhe kolo doplneni cross_section_label/groove_family pro prislusenstvi
(Robert: "projed scriptem vsechno prislusenstvi Dogus a spojky, ktere
nemaji ikonu Slotu a dava to pritom smysl"). Navazuje na
scripts/2026-08-10_accessory_compatibility_backfill.py (prvni kolo,
249/434 urceno, 185 preskoceno pro nedostatek spolehliveho signalu -
po rucnich vyjimkach ("Spojka uhel 45°") 183 zbylo).

Vsechny puvodni metody (text "drážka N"/"K6-K10", SKU 4. segment)
zustavaji, PRIDANA 1 nova metoda jako POSLEDNI fallback:

  3. CROSS-SECTION-JEDNOZNACNOST: kdyz nazev obsahuje rozmer "NNxNN" a
     tenhle prurez ma v katalogu jen JEDNU moznou drazku (overeno proti
     VSEM potvrzenym profilum is_profile_material=1 v DB - napr. 20x20
     je vzdy 6mm, 45x45 vzdy 10mm), pouzije se ta drazka. Neni to
     hadani - je to fyzikalni dusledek (zaslepka/vrtaci pripravek je
     presne narezany na rozmer KONKRETNIHO profilu, a ten profil ma v
     nasem katalogu jen jednu variantu). U PRUREZU S VICE VARIANTAMI
     (30x30, 30x60, 35x35, 40x40, 40x80, 60x60, 80x80 - overeno maji
     2 ruzne drazky mezi realnymi profily) se tahle metoda VUBEC
     nepouzije - tam zustava polozka neurcena, presne jak
     "Upínač patky"/"Pant" ukazaly v predchozim kole, ze SKU/nazev bez
     explicitniho cisla drazky nestaci.

Take pridano rozpoznani "S6"/"S8"/"S10" v nazvu (stejny vzor jako "K6"/
"K8"/"K10" - "Záslepka 40x40 S10"/"Záslepka 40x40 S8 Light", odpovida
nazvoslovi profilovych rad "Light S8"/"SuperLight S10" ve
VLASTNOSTI_PROFILU.md).

ZAMERNE STALE VYNECHANO (zustava neurceno):
  - Genericke srouby M4-M16 (2.1.20.*/2.1.21.* "Šroub se zápustnou/
    šestihrannou hlavou") - zavit NENI spolehlivy proxy pro sirku
    drazky (viz M-heuristika zamitnuta v prvnim kole).
  - "Upínač patky"/"Pant" na NEJEDNOZNACNYCH prurezech - trailing
    cislo v SKU prokazatelne NEODPOVIDA fyzicke drazce (viz prvni
    kolo, "Upínač patky 30x60 M10" tvrdilo drazku 10, ktera pro
    30x60 vubec neexistuje).
  - Polozky bez jakehokoli rozmeru v nazvu (Magnet, Madlo, Plynová
    vzpěra, Bezpečnostní zámek, Těsnicí páska...) - nemaji zadny
    signal k odvozeni.
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
GROOVE_TEXT_RE = re.compile(r"dr[áa]žk[aeyu]?\D{0,15}?(\d{1,2})\b", re.IGNORECASE)
GROOVE_K_RE = re.compile(r"\bK(6|8|10)\b")
GROOVE_S_RE = re.compile(r"\bS(6|8|10)\b")
GROOVE_SKU_RE = re.compile(r"^\d+\.\d+\.\d+\.(\d{2})\.")
GROOVE_SKU_CODE = {"06": "6", "08": "8", "10": "10"}
CROSS_SECTION_RE = re.compile(r"(?<!M)\b(\d{2,3})\s*[x×]\s*(\d{2,3})\b")


def guess_cross_section(name):
    m = CROSS_SECTION_RE.search(name)
    if m:
        return f"{int(m.group(1))}x{int(m.group(2))}"
    return None


def build_unambiguous_groove_map(cur):
    # Prurez -> jedina drazka, kdyz VSICHNI potvrzeni profily (nikoli
    # prislusenstvi - profily jsou primy, nezavisly zdroj pravdy) s tim
    # prurezem maji STEJNOU drazku. Prurezy s vice variantami se do
    # mapy vubec nedostanou (viz docstring vyse).
    cur.execute("""
        SELECT cross_section_label, groove_family FROM shop_products
        WHERE is_profile_material=1 AND active=1 AND is_archived=0 AND cross_section_label IS NOT NULL
    """)
    grooves_by_cross = {}
    for r in cur.fetchall():
        s = grooves_by_cross.setdefault(r["cross_section_label"], set())
        for g in (r["groove_family"] or "").split(","):
            g = g.strip()
            if g:
                s.add(g)
    return {cs: next(iter(g)) for cs, g in grooves_by_cross.items() if len(g) == 1}


def guess_groove(sku, name, unambiguous_map):
    m = GROOVE_TEXT_RE.search(name)
    if m and m.group(1) in VALID_GROOVES:
        return m.group(1), "nazev:drazka"
    m = GROOVE_K_RE.search(name)
    if m:
        return m.group(1), "nazev:K"
    m = GROOVE_S_RE.search(name)
    if m:
        return m.group(1), "nazev:S"
    m = GROOVE_SKU_RE.match(sku or "")
    if m and m.group(1) in GROOVE_SKU_CODE:
        return GROOVE_SKU_CODE[m.group(1)], "sku:pozice4"
    cross_section = guess_cross_section(name)
    if cross_section and cross_section in unambiguous_map:
        return unambiguous_map[cross_section], f"prurez:jednoznacny({cross_section})"
    return None, None


def main():
    dry_run = "--apply" not in sys.argv
    conn = pymysql.connect(**DB)
    cur = conn.cursor()

    unambiguous_map = build_unambiguous_groove_map(cur)
    print("Jednoznacne prurezy pouzite jako fallback zdroj:")
    for cs, g in sorted(unambiguous_map.items(), key=lambda kv: (int(kv[0].split("x")[0]), int(kv[0].split("x")[1]))):
        print(f"  {cs} -> {g}mm")

    cur.execute("""
        SELECT id, sku, name FROM shop_products
        WHERE active=1 AND is_archived=0 AND sku LIKE '2.%' AND groove_family IS NULL
    """)
    rows = cur.fetchall()

    matched = []
    unmatched = []
    for r in rows:
        groove, source = guess_groove(r["sku"], r["name"], unambiguous_map)
        if not groove:
            unmatched.append(r)
            continue
        cross_section = guess_cross_section(r["name"])
        matched.append((r["id"], r["sku"], r["name"], groove, cross_section, source))

    print(f"\nKandidatu (2. kolo, dosud bez groove_family): {len(rows)}")
    print(f"  -> groove urcena: {len(matched)}")
    print(f"  -> groove STALE NEURCENA: {len(unmatched)}")

    print("\n--- VSECHNY nove urcene (zkontroluj rucne pred --apply) ---")
    for pid, sku, name, groove, cross_section, source in matched:
        cs = cross_section or "(jakykoli prurez v drazce)"
        print(f"  #{pid} {sku:24s} {name!r:65s} -> drazka={groove:>2s}mm prurez={cs:20s} [{source}]")

    print(f"\n--- STALE NEURCENE ({len(unmatched)}, jen nazvy pro rychly prehled) ---")
    for r in unmatched:
        print(f"  #{r['id']} {r['sku']:24s} {r['name']}")

    if not matched:
        print("\nNic k zapisu.")
        return

    backup = [{"id": pid, "sku": sku, "name": name} for pid, sku, name, _, _, _ in matched]
    backup_path = "backups/accessory_compatibility_backfill_round2_20260810.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=2)
    print(f"\nZaloha {len(backup)} radku -> {backup_path}")

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
