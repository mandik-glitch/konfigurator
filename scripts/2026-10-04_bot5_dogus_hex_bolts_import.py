#!/opt/konfigurator/api/venv/bin/python
"""Import kategorie Dogus "Hex Head Bolts" (https://en.doguskalip.com.tr/Products/76/hex-head-bolts) do e-shopu - bot5, 2026-10-04.

Robert (klik v okne bot16, 2026-10-04): "toto jsme vubec neimportovali?" -> ne, "Jen srouby": naimportovat kategorii 76 (19 polozek M4x8 az M10x30, ocel 8.8 podle crawlu 2026-08-10).
Plexisklo (21 ks) Robert NECHCE importovat.

Stejny postup jako predchozi importy Dogus (scripts/2026-08-11_dogus_dynamic_shelving_import.py, jehoz crawl, parser a pomocne funkce se tu NACITAJI beze zmeny, ne kopiruji): INSERT novych
shop_products podle SKU = Dogus Stock Code, cesky nazev "Sroub se sestihrannou hlavou M..", popis stejnou sablonou jako u srouby se zapustnou hlavou (kat. 263), 2 obrazky (schema/render),
manufacturer, dogus_url/dogus_stock_code (podle nich je cena prepocitana KAZDOU NOC podle pravidla 9: List Price USD x kurz Fio x koeficient kategorie 263 (1,2), kus, ceil; do prvniho nocniho behu je cena
prazdna = "cena na dotaz"), hmotnost z "Weight (gr)". Cilova kategorie 263 "Srouby" (kus, koeficient 1,2 - tam uz jsou srouby se zapustnou hlavou).
Dogus: VZDY jen cteni (GET verejnych stranek, zadne prihlaseni). Zdroj dat = CERSTVY crawl kategorie (od srpna se mohl pocet zmenit), ne stara zaloha.

Rezimy: --report (crawl -> JSON v backups/, nic v DB) | bez --apply = dry-run vuci DB | --apply = zapis + obrazky. Opakovane spusteni je bezpecne (existujici SKU se preskoci).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-04_bot5_dogus_hex_bolts_import.py [--report|--apply] [--catalog-in JSON]"""
import argparse
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("dogus_import_base", os.path.join(HERE, "2026-08-11_dogus_dynamic_shelving_import.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

SUB_ID = "76"
M.SUBCATEGORY_HREFS = {SUB_ID: "/Urunler/76/hex-head-bolts"}
CATEGORY_ID = 263                                             # "Srouby" (kus, koeficient 1,2)
NAME_RE = re.compile(r"^Hex Head Bolt (M\d+x\d+)$", re.I)
STEEL_RE = re.compile(r"^\s*([\d.,]+)\s*steel\s*$", re.I)
PURPOSE = "Šroub se šestihrannou hlavou pro šroubové spoje konstrukcí."
BACKUP = os.path.join(os.path.dirname(HERE), "backups", "2026-10-04_dogus_hex_head_bolts_crawl.json")


def name_cs(stock_name):
    m = NAME_RE.match((stock_name or "").strip())
    return f"Šroub se šestihrannou hlavou {m.group(1)}" if m else None


def material_cs(raw):
    m = STEEL_RE.match(raw or "")
    return f"ocel pevnostní třídy {m.group(1).replace(',', '.')}" if m else M.translate_material(raw)


def description(nm, specs):
    bits = []
    mat = material_cs(specs.get("Material"))
    if mat:
        bits.append(f"z materiálu {mat}")
    w = (specs.get("Weight (gr)") or "").strip()
    if w and w != "-":
        bits.append(f"hmotnost cca {w} g")
    return f"{nm}" + (f" ({', '.join(bits)})" if bits else "") + f". {PURPOSE}"


def weight_g(specs):
    try:
        return round(float((specs.get("Weight (gr)") or "").replace(",", ".")))
    except ValueError:
        return None


def crawl_retry(tries=4):
    """Crawl kategorie jako M.crawl(), ale s opakovanim kratkych vypadku spojeni (Dogus obcas zavre spojeni); chybejici produkt po vsech pokusech = chyba, ne tiche vynechani."""
    import time
    catalog = []
    products = M.discover_products(M.SUBCATEGORY_HREFS[SUB_ID])
    print(f"[{SUB_ID}] {len(products)} produktu v kategorii", file=sys.stderr)
    for pid, href in products:
        for pokus in range(tries):
            try:
                variants, render, schema = M.parse_product(href)
                break
            except Exception as e:
                print(f"  pokus {pokus + 1}/{tries} {href}: {e}", file=sys.stderr)
                time.sleep(3 * (pokus + 1))
        else:
            sys.exit(f"CHYBA: produkt {href} se nepodarilo nacist, crawl neni uplny")
        for v in variants:
            catalog.append({"sub_id": SUB_ID, "product_id": pid, "product_url": M.BASE + href, "stock_code": v["stock_code"], "stock_name": v["stock_name"], "specs": v["specs"],
                            "image_render_url": render, "image_schema_url": schema})
    return catalog


def build_rows(catalog):
    rows, problems = [], []
    for r in catalog:
        nm = name_cs(r["stock_name"])
        if not nm or not r["stock_code"]:
            problems.append((r["stock_code"], r["stock_name"]))
            continue
        rows.append({"sku": r["stock_code"], "name": nm, "description": description(nm, r["specs"]), "dogus_url": r["product_url"], "weight_g": weight_g(r["specs"]),
                     "render": r["image_render_url"], "schema": r["image_schema_url"], "specs": r["specs"]})
    return rows, problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--catalog-in")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.catalog_in:
        catalog = json.load(open(a.catalog_in))
    else:
        catalog = crawl_retry()
        json.dump(catalog, open(BACKUP, "w"), ensure_ascii=False, indent=1)
        print(f"Crawl: {len(catalog)} polozek, ulozeno do {BACKUP}", file=sys.stderr)
    if a.report:
        for r in catalog:
            print(r["stock_code"], "|", r["stock_name"], "|", r["specs"].get("Material"), "|", r["specs"].get("Weight (gr)"))
        return
    rows, problems = build_rows(catalog)
    if problems:
        print("POZOR: vynechano (nazev neodpovida 'Hex Head Bolt Mx..'):", problems, file=sys.stderr)
    if len({r["sku"] for r in rows}) != len(rows):
        sys.exit("CHYBA: duplicitni stock code v crawlu")
    conn = M.get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, dogus_price_coefficient, dogus_sale_unit FROM content_categories WHERE id=%s", (CATEGORY_ID,))
            cat = cur.fetchone()
            cur.execute("SELECT sku FROM shop_products WHERE sku IN %s", (tuple(r["sku"] for r in rows),)) if rows else None
            existing = {x["sku"] for x in cur.fetchall()} if rows else set()
    finally:
        conn.close()
    assert cat, f"kategorie {CATEGORY_ID} neexistuje"
    todo = [r for r in rows if r["sku"] not in existing]
    print(f"Kategorie {CATEGORY_ID}: {cat['name']}; naparsovano {len(catalog)}, platnych {len(rows)}, uz existuje {len(existing)}, K VYTVORENI {len(todo)}", file=sys.stderr)
    for r in todo:
        print(f"  {r['sku']}  {r['name']}  | {r['weight_g']} g | {r['description'][:110]}", file=sys.stderr)
    if not a.apply:
        print("(dry-run, nic nezapsano; --apply pro zapis)", file=sys.stderr)
        return
    conn = M.get_db_conn()
    created = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT slug FROM shop_products WHERE slug IS NOT NULL")
            taken = {x["slug"] for x in cur.fetchall()}
            for r in todo:
                slug = M._unique_product_slug(cur, M._slugify(r["name"]), taken)
                cur.execute("""INSERT INTO shop_products (category_id, sku, name, slug, description, unit, active, manufacturer, is_profile_material, dogus_url, dogus_stock_code,
                               dogus_image_render_url, dogus_image_schema_url, product_specs_json, dogus_matched_at, price_visible_default, weight_g)
                               VALUES (%s,%s,%s,%s,%s,'ks',1,'Dogus',0,%s,%s,%s,%s,%s,NOW(),0,%s)""",
                            (CATEGORY_ID, r["sku"], r["name"], slug, r["description"], r["dogus_url"], r["sku"], r["render"], r["schema"], json.dumps(r["specs"], ensure_ascii=False), r["weight_g"]))
                if cur.rowcount != 1:
                    raise RuntimeError(f"INSERT {r['sku']} nezapsal radek")
                created.append((cur.lastrowid, r))
        conn.commit()
    finally:
        conn.close()
    print(f"Vytvoreno {len(created)} produktu: id {[i for i, _ in created]}", file=sys.stderr)
    # obrazky: stejna logika jako model (schema, render; stejna URL jen jednou), vlastnik www-data
    conn = M.get_db_conn()
    ok = bad = 0
    try:
        with conn.cursor() as cur:
            for pid, r in created:
                d = M.IMG_DIR_TPL.format(id=pid)
                os.makedirs(d, exist_ok=True)
                seen, order = set(), 0
                for url in (r["schema"], r["render"]):
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    fn = f"{order + 1}{os.path.splitext(M.urllib.parse.urlsplit(url).path)[1] or '.jpg'}"
                    try:
                        M.download_image(url, os.path.join(d, fn))
                    except Exception as e:
                        print(f"  CHYBA obrazek {pid}: {e}", file=sys.stderr)
                        bad += 1
                        continue
                    cur.execute("INSERT INTO shop_product_images (product_id, filename, source_url, sort_order) VALUES (%s,%s,%s,%s)", (pid, f"products/{pid}/{fn}", url, order))
                    ok += 1
                    order += 1
        conn.commit()
    finally:
        conn.close()
    import grp
    import pwd
    uid, gid = pwd.getpwnam("www-data").pw_uid, grp.getgrnam("www-data").gr_gid
    for pid, _ in created:
        d = M.IMG_DIR_TPL.format(id=pid)
        if os.path.isdir(d):
            os.chown(d, uid, gid)
            for f in os.listdir(d):
                os.chown(os.path.join(d, f), uid, gid)
    print(f"Obrazky: {ok} stazeno, {bad} chyb.", file=sys.stderr)


if __name__ == "__main__":
    main()
