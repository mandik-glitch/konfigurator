"""Řemeslo - Srovnávač: "match group" párování napříč dodavateli
(bot14, 2026-08-20, Robertovo zadání - pilot; rozšíření na další
kategorie 2026-08-20 podle počtu dodavatelů, koordinováno bot3, viz
AGENTS_LOG.md "otázka konzervativní vs. shovívavější párování
nechávám na Robertovi... do té doby pokračuj bezpečnou částí"). Viz
sql/2026-08-20_remeslo_material_match_groups.sql pro schéma a
zdůvodnění.

Typová pravidla jsou PER-KATEGORIE (CATEGORY_RULES níž, klíč =
category_id) - slovník "koleno/nátrubek/T-kus" platí jen pro trubky a
tvarovky, jiné kategorie (baterie, ventily, keramika...) mají vlastní
slovník. Extrakce rozměru (mm/palec/úhel) je SDÍLENÁ napříč
kategoriemi - metrické/palcové značení funguje stejně všude.

Extrakce je ÚMYSLNĚ KONZERVATIVNÍ (raději nespárovat, než spárovat
špatně - viz Robertovo "ručně zkontroluj vzorek, ne slepě důvěřuj
regexpu"): pokud typ nebo rozměr nejde s jistotou vytáhnout, položka
zůstane nespárovaná (beze změny chování v /api/remeslo/compare).

Použití:
    python3 2026-08-20_remeslo_match_groups_pilot.py --category-id 3              # dry-run, jen report
    python3 2026-08-20_remeslo_match_groups_pilot.py --category-id 3 --commit     # zapíše match groups + vazby
    python3 2026-08-20_remeslo_match_groups_pilot.py --all --commit               # všechny kategorie v CATEGORY_RULES
"""
import argparse
import re
import sys

import pymysql


def load_env():
    env = {}
    for line in open("/opt/konfigurator/api/.env"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v
    return env


def get_conn(env):
    return pymysql.connect(
        host=env["REMESLO_DB_HOST"], port=int(env["REMESLO_DB_PORT"]),
        user=env["REMESLO_DB_USER"], password=env["REMESLO_DB_PASSWORD"],
        database=env["REMESLO_DB_NAME"], cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


# ---------------------------------------------------------------------------
# CATEGORY_RULES[category_id] = (nazev_pro_info, prefix_material_nebo_None, TYPE_RULES)
#   TYPE_RULES: ORDER MATTERS (nejspecifičtější frázi napřed, aby se
#   "T-kus redukovaný" nesplácl na obecné "T-kus" atd.). Každé pravidlo:
#   (kanonický_typ, [všechny tyhle fragmenty musí být v názvu (lowercase,
#   bez ohledu na pořadí)]).
#   prefix_material: řetězec připojený před kanonický název při zobrazení
#   (napr. "PPR"), None = žádný prefix (typ už material obsahuje sám,
#   nebo kategorie material nerozlišuje).
# ---------------------------------------------------------------------------
CATEGORY_RULES = {
    3: ("PPR trubky a tvarovky", "PPR", [
        ("T-kus jednoznačný", ["t-kus", "jednoznačn"]),
        ("T-kus redukovaný", ["t-kus", "redukovan"]),
        ("koleno nástěnné", ["koleno", "nástěnn"]),
        ("koleno s převlečnou maticí", ["koleno", "převlečnou matic"]),
        ("koleno čepové", ["koleno", "čepov"]),
        ("koleno", ["koleno"]),
        ("nátrubek redukovaný", ["nátrubek", "redukovan"]),
        ("nátrubek s vypouštěním", ["nátrubek", "vypouštění"]),
        ("nátrubek", ["nátrubek"]),
        ("přechod pro sádrokarton", ["přechod", "sádrokarton"]),
        # Ruční kontrola (bot14, 2026-08-20) odhalila chybu: "přechodka s
        # převlečnou maticí" (rozebíratelný spoj) a "přechodka se
        # závitem" (pevný závitový spoj) jsou MECHANICKY jiné produkty i
        # při stejném rozměru - dřívější bare "přechodka" pravidlo je
        # omylem slučovalo do jedné skupiny. Rozděleno stejně jako u
        # "koleno" výš.
        ("přechodka s převlečnou maticí", ["přechodka", "převlečnou matic"]),
        ("přechodka se závitem", ["přechodka", "závit"]),
        ("přechodka", ["přechodka"]),
        ("redukce", ["redukce"]),
        ("montážní zátka tlaková", ["zátka", "tlakov"]),
        ("montážní zátka závitová", ["zátka", "závitov"]),
        ("zátka k nástěnnému kompletu", ["zátka", "nástěnnému kompletu"]),
        ("montážní zátka", ["zátka"]),
        ("šroubení vnější", ["šroubení", "vnější"]),
        ("šroubení vnitřní", ["šroubení", "vnitřní"]),
        ("dvojpříchytka s klipem", ["dvojpříchytka", "klip"]),
        ("dvojpříchytka se závitem", ["dvojpříchytka", "závit"]),
        ("dvojpříchytka s třmenem", ["dvojpříchytka", "třmen"]),
        ("dvojpříchytka", ["dvojpříchytka"]),
        ("příchytka dvojitá s třmenem", ["příchytka dvojitá", "třmen"]),
        ("příchytka s třmenem", ["příchytka", "třmen"]),
        ("příchytka natloukací", ["příchytka", "natloukac"]),
        ("příchytka plastová", ["příchytka plastová"]),
        ("příchytka", ["příchytka"]),
        ("montážní nosníková konzole", ["nosníková konzole"]),
        ("montážní nosník", ["nosník"]),
        ("trubka PP-R", ["trubka"]),
        ("řezák trubek", ["řezák"]),
    ]),
}

# Typy, u kterých je úhel (45°/90°) součástí identity (jiný úhel = jiná
# položka i při stejném průměru) - klíčováno kanonickým typem obsahujícím
# tenhle fragment (case-insensitive substring).
ANGLE_SENSITIVE_TYPE_FRAGMENTS = ["koleno"]

# Fragmenty, které se mají z názvu odstranit PŘED hledáním rozměru, aby se
# nepletl balicí počet/délka tyče s rozměrem součástky (nalezeno živě na
# "Příchytka dvojitá s třmenem Capricorn 25 ks" a "4 m tyč").
_STRIP_BEFORE_DIM = [
    re.compile(r"\d+\s*ks\b", re.I),
    re.compile(r"\d+\s*m\s*tyč\b", re.I),
]

_DIM_MM_PAIR = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*mm", re.I)
_DIM_MM_TRIPLE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*mm", re.I)
_DIM_D_PREFIX = re.compile(r"\bd\s*(\d+(?:[.,]\d+)?)\b", re.I)
_DIM_MM_SINGLE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.I)
_DIM_INCH = re.compile(r"(\d+(?:/\d+)?)\s*[\"“]")
_DIM_MM_X_INCH = re.compile(r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:/\d+)?)\s*[\"“]", re.I)
_DIM_BARE_TRIPLE = re.compile(r"\b(\d{1,4})\s*x\s*(\d{1,4})\s*x\s*(\d{1,4})\s*mm\b", re.I)
_DIM_INCH_PAIR = re.compile(r"(\d+(?:/\d+)?)\s*[\"“]\s*x\s*(\d+(?:/\d+)?)\s*[\"“]", re.I)
_DIM_DN = re.compile(r"\bDN\s*(\d+(?:[.,]\d+)?)\b", re.I)


def _norm_num(s):
    return s.replace(",", ".")


def extract_dimension(name):
    """Vrátí (dimension_key, human_readable) nebo (None, None), pokud
    žádný rozměr nejde s jistotou najít. ROZMĚR X JEDNOTKA metrů se
    KOMBINUJE s palcovou frakcí, když jsou obě přítomné (přechodky/
    koleno s převlečnou maticí typicky "20x1/2""), protože to je
    PODSTATNÁ součást identity položky (jiná palcová strana = jiný
    produkt), ne šum."""
    s = name
    for pat in _STRIP_BEFORE_DIM:
        s = pat.sub("", s)

    m = _DIM_MM_X_INCH.search(s)
    if m:
        return f"{_norm_num(m.group(1))}x{m.group(2)}in", f"{m.group(1)}×{m.group(2)}\""

    m = _DIM_INCH_PAIR.search(s)
    if m:
        return f"{m.group(1)}inx{m.group(2)}in", f"{m.group(1)}\"×{m.group(2)}\""

    m = _DIM_BARE_TRIPLE.search(s) or _DIM_MM_TRIPLE.search(s)
    if m:
        a, b, c = (_norm_num(x) for x in m.groups())
        return f"{a}x{b}x{c}mm", f"{m.group(1)}×{m.group(2)}×{m.group(3)} mm"

    m = _DIM_MM_PAIR.search(s)
    if m:
        a, b = (_norm_num(x) for x in m.groups())
        return f"{a}x{b}mm", f"{m.group(1)}×{m.group(2)} mm"

    m = _DIM_DN.search(s)
    if m:
        v = _norm_num(m.group(1))
        return f"DN{v}", f"DN{m.group(1)}"

    m = _DIM_D_PREFIX.search(s)
    if m:
        v = _norm_num(m.group(1))
        return f"{v}mm", f"{m.group(1)} mm"

    m = _DIM_MM_SINGLE.search(s)
    if m:
        v = _norm_num(m.group(1))
        return f"{v}mm", f"{m.group(1)} mm"

    m = _DIM_INCH.search(s)
    if m:
        return f"{m.group(1)}in", f"{m.group(1)}\""

    return None, None


_ANGLE = re.compile(r"(\d+)\s*°")


def extract_type(name, type_rules):
    low = name.lower()
    for canonical, fragments in type_rules:
        if all(frag in low for frag in fragments):
            return canonical
    return None


def extract(name, type_rules, material_prefix):
    """Vrátí (item_type, dimension_key, canonical_name_pro_zobrazeni) nebo
    (None, ...), když typ nebo rozměr chybí - položka se pak NEPÁRUJE."""
    item_type = extract_type(name, type_rules)
    dim_key, dim_human = extract_dimension(name)
    angle_m = _ANGLE.search(name)
    angle = angle_m.group(1) + "°" if angle_m else None
    if not item_type or not dim_key:
        return None, None, None
    if angle and any(frag in item_type.lower() for frag in ANGLE_SENSITIVE_TYPE_FRAGMENTS):
        dim_key = f"{angle}_{dim_key}"
        dim_human = f"{angle} {dim_human}"
    prefix = ""
    if material_prefix and material_prefix.lower() not in item_type.lower():
        prefix = f"{material_prefix} "
    canonical = f"{prefix}{item_type} {dim_human}".replace("  ", " ")
    return item_type, dim_key, canonical


def process_category(cur, category_id, type_rules, material_prefix, verbose=True):
    cur.execute(
        "SELECT mp.id, mp.product_name, mp.price_czk, s.supplier_name "
        "FROM remeslo_material_prices mp JOIN remeslo_price_sources s ON s.id = mp.source_id "
        "WHERE mp.category_id=%s AND s.active=1 ORDER BY mp.product_name",
        (category_id,),
    )
    rows = cur.fetchall()

    groups = {}  # (item_type, dim_key) -> {"canonical": ..., "items": [row,...]}
    unmatched = []
    for row in rows:
        item_type, dim_key, canonical = extract(row["product_name"], type_rules, material_prefix)
        if not item_type:
            unmatched.append(row)
            continue
        key = (item_type, dim_key)
        g = groups.setdefault(key, {"canonical": canonical, "items": []})
        g["items"].append(row)

    multi = {k: g for k, g in groups.items() if len({it["supplier_name"] for it in g["items"]}) >= 2}
    single = {k: g for k, g in groups.items() if len({it["supplier_name"] for it in g["items"]}) == 1}

    if verbose:
        print(f"\nCelkem položek v kategorii {category_id}: {len(rows)}")
        print(f"=== SKUPINY SE 2+ DODAVATELI (přímé srovnání, {len(multi)} skupin) ===")
        for key, g in sorted(multi.items(), key=lambda kv: kv[1]["canonical"]):
            print(f"\n[{g['canonical']}]  (type={key[0]!r} dim={key[1]!r})")
            for it in sorted(g["items"], key=lambda x: x["price_czk"]):
                print(f"    {it['supplier_name']:15s} {it['price_czk']:>8} Kč   <- {it['product_name']}")
        print(f"\nSkupin s 1 dodavatelem: {len(single)}  ({sum(len(g['items']) for g in single.values())} položek)")
        print(f"Nespárováno: {len(unmatched)} položek")
        total_in_multi = sum(len(g["items"]) for g in multi.values())
        print(f"SOUHRN kat.{category_id}: celkem={len(rows)} multi_groups={len(multi)}({total_in_multi} pol.) "
              f"single_groups={len(single)}({sum(len(g['items']) for g in single.values())} pol.) nespárováno={len(unmatched)}")

    return {"rows": rows, "groups": groups, "multi": multi, "single": single, "unmatched": unmatched}


def commit_category(cur, category_id, result, exclude_keys=None):
    exclude_keys = exclude_keys or set()
    n_groups = 0
    n_links = 0
    n_skipped = 0
    for key, g in result["groups"].items():
        if key in exclude_keys:
            n_skipped += 1
            continue
        item_type, dim_key = key
        cur.execute(
            "INSERT INTO remeslo_material_match_groups (category_id, canonical_name, item_type, dimension_key, match_method) "
            "VALUES (%s,%s,%s,%s,'auto_regex') "
            "ON DUPLICATE KEY UPDATE canonical_name=VALUES(canonical_name)",
            (category_id, g["canonical"], item_type, dim_key),
        )
        cur.execute(
            "SELECT id FROM remeslo_material_match_groups WHERE category_id=%s AND item_type=%s AND dimension_key=%s",
            (category_id, item_type, dim_key),
        )
        group_id = cur.fetchone()["id"]
        n_groups += 1
        for it in g["items"]:
            cur.execute(
                "INSERT IGNORE INTO remeslo_material_price_match (material_price_id, match_group_id) VALUES (%s,%s)",
                (it["id"], group_id),
            )
            n_links += cur.rowcount
    return n_groups, n_links, n_skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="skutečně zapsat do DB (jinak jen report)")
    ap.add_argument("--category-id", type=int, default=None)
    ap.add_argument("--all", action="store_true", help="zpracovat všechny kategorie v CATEGORY_RULES")
    args = ap.parse_args()

    if not args.all and args.category_id is None:
        print("Zadej --category-id N nebo --all"); sys.exit(1)

    env = load_env()
    conn = get_conn(env)
    cur = conn.cursor()

    cat_ids = list(CATEGORY_RULES.keys()) if args.all else [args.category_id]
    grand_total = grand_multi_items = grand_multi_groups = grand_single_groups = grand_single_items = grand_unmatched = 0
    for cid in cat_ids:
        if cid not in CATEGORY_RULES:
            print(f"(kategorie {cid} nemá pravidla v CATEGORY_RULES, přeskakuji)")
            continue
        name, material_prefix, type_rules = CATEGORY_RULES[cid]
        print(f"\n{'='*70}\nKategorie {cid}: {name}\n{'='*70}")
        result = process_category(cur, cid, type_rules, material_prefix)
        grand_total += len(result["rows"])
        grand_multi_groups += len(result["multi"])
        grand_multi_items += sum(len(g["items"]) for g in result["multi"].values())
        grand_single_groups += len(result["single"])
        grand_single_items += sum(len(g["items"]) for g in result["single"].values())
        grand_unmatched += len(result["unmatched"])
        if args.commit:
            n_groups, n_links, n_skipped = commit_category(cur, cid, result)
            conn.commit()
            print(f"--- ZAPSÁNO kat.{cid}: {n_groups} match groups, {n_links} nových vazeb ---")

    if len(cat_ids) > 1:
        print(f"\n{'='*70}\nCELKOVÝ SOUHRN ({len(cat_ids)} kategorií)\n{'='*70}")
        print(f"Celkem položek:                 {grand_total}")
        print(f"Skupin se 2+ dodavateli:        {grand_multi_groups}  ({grand_multi_items} položek)")
        print(f"Skupin s 1 dodavatelem:         {grand_single_groups}  ({grand_single_items} položek)")
        print(f"Nespárováno:                    {grand_unmatched} položek")

    if not args.commit:
        print("\n(dry-run, nic se nezapisovalo - spusť s --commit pro zápis do DB)")

    conn.close()


if __name__ == "__main__":
    main()
