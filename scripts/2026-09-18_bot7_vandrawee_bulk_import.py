#!/usr/bin/env python3
"""Hromadny import vanDrawee sestav ze zive vandrawee.eu (Robert 2026-09-17:
"stahuj tedy z zive eu" - lokalni kopie neobsahuje zadnou z 322 schvalenych
polozek, overeno vycerpavajicim hledanim v 5 DB + storage + 2 SQL dumpech).

Zdroj ceny/hmotnosti: Robertuv vlastni export (parsed_322.json, sloupce
"Zverejneno"="Ano" - "tyto jsou zverejnene, tj mnou zkontrolovane").
Zdroj obrazku/nazvu vozidla/komponentu: zivy web, dotazovany PRESNE podle
stejneho UUID (zadna shoda podle ceny/vahy - to uz jednou selhalo).

Kategorie: vandrawee sestavy sedi na urovni ZNACKOVEHO HUBU (o uroven vys
nez nase vlastni Tier1 stranky modelu), Robert: "nechceme to michat do
nasich sestav... budou o uroven vyse".
"""
import sys, os, re, json, time, unicodedata, random
import requests

sys.path.insert(0, "/opt/konfigurator/scripts")
import _env

SCRATCH = "/tmp/claude-0/-opt-konfigurator/44c1c190-9cfa-47f2-b304-ecd43dd5d19c/scratchpad"
IMG_STAGING = os.path.join(SCRATCH, "vandrawee_bulk_images")
os.makedirs(IMG_STAGING, exist_ok=True)

BRAND_TO_HUB = {
    "Fiat": 269, "Citroen": 268, "Peugeot": 288, "Ford": 279,
    "VW": 271, "Volkswagen": 271, "Mercedes": 270, "Opel": 286,
    "Renault": 285, "Iveco": 287, "Toyota": 281,
}

COMPONENT_LABELS = {
    "police": "police",
    "upinaci": "upínací plochy",
    "zavetrovani": "zavětrování",
    "supliky": "zásuvky",
    "multibox": "multibox kontejnery",
    "noha": "nohy",
    "kolo": "kolečka",
    "kolecko": "kolečka",
    "madlo": "madla",
    "tyc": "tyče",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LogimanContentBot/1.0)"}

def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

def strip_length_suffix(vehicle):
    return re.sub(r"\s+\d{3,4}\s*mm\b.*$", "", vehicle).strip()

def detect_brand(vehicle):
    first = vehicle.split()[0]
    return first if first in BRAND_TO_HUB else None

def fetch_detail(uuid):
    url = f"https://vandrawee.eu/cs/detail-sestavy/{uuid}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    html = r.text
    m_vehicle = re.search(r'Navrženo pro:\s*</span>\s*<span class="text">([^<]+)</span>', html)
    vehicle_live = m_vehicle.group(1).strip() if m_vehicle else None
    imgs = re.findall(r'src="(https://vandrawee\.eu/storage/images/[a-zA-Z0-9]+_(?:first_3d|second_3d|2d)[a-zA-Z_]*)\.png\??[^"]*"', html)
    imgs = [u for u in imgs if "_small_" not in u]
    imgs = list(dict.fromkeys(imgs))  # dedupe, keep order
    # 2D obrazek nohy s kotami (Robert 2026-09-18: "chybi obrazek nohy s
    # kotami") - samostatna slozka storage/single_legs/, jiny nazev-vzor
    # nez ostatni (sdileny asset per typ nohy, ne per sestava).
    leg_imgs = re.findall(r'src="(https://vandrawee\.eu/storage/single_legs/[^"?]+)\.png\??[^"]*"', html)
    leg_imgs = list(dict.fromkeys(leg_imgs))
    imgs.extend(leg_imgs)
    # Strukturovany BOM 1:1 se zdrojem: h5 sekce (Komponenty/Nohy), volitelne
    # h6 podskupiny uvnitr, kazda s <li>Nx Nazev</li> polozkami. Zachovava
    # presne technicke nazvy a mnozstvi - Robert: "obsah detailu 1:1 se
    # zdrojem" (2026-09-18), zadne parafrazovani/humanizovani.
    sections = []
    for h5_m in re.finditer(r'<h5>([^<]+)</h5>(.*?)(?=<h5>|</article>)', html, re.S):
        sec_title = h5_m.group(1).strip()
        sec_body = h5_m.group(2)
        subgroups = list(re.finditer(r'<h6>([^<]+)</h6>\s*<ul>(.*?)</ul>', sec_body, re.S))
        items_out = []
        if subgroups:
            for sub_m in subgroups:
                sub_title = sub_m.group(1).strip()
                items = re.findall(r'<li><span class="font-weight-bold">(\d+x)</span>\s*([^<]+)</li>', sub_m.group(2))
                items_out.append((sub_title, [(q, n.strip()) for q, n in items]))
        else:
            items = re.findall(r'<li><span class="font-weight-bold">(\d+x)</span>\s*([^<]+)</li>', sec_body)
            if items:
                items_out.append((None, [(q, n.strip()) for q, n in items]))
        if items_out:
            sections.append((sec_title, items_out))

    components_raw = re.findall(r'<li><span class="font-weight-bold">(\d+x)</span>\s*([^<]+)</li>', html)
    return {"vehicle_live": vehicle_live, "images": imgs, "components_raw": components_raw,
            "sections": sections, "url": url}, None

def humanize_components(components_raw):
    labels = []
    seen = set()
    for _, name in components_raw:
        prefix = re.split(r"[.\s]", name.strip(), 1)[0].lower()
        prefix = unicodedata.normalize("NFKD", prefix).encode("ascii", "ignore").decode("ascii")
        label = COMPONENT_LABELS.get(prefix)
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
    return labels

def format_bom_text(sections):
    """Doslovny, ciselne presny vypis komponentu - zadna parafraze."""
    lines = []
    for sec_title, subgroups in sections:
        lines.append(f"{sec_title}:")
        for sub_title, items in subgroups:
            prefix = f"  {sub_title} - " if sub_title else "  "
            lines.append(prefix + ", ".join(f"{q} {n}" for q, n in items))
    return "\n".join(lines)

def caption_for(img_base_url):
    fname = img_base_url.rsplit("/", 1)[-1]
    if "single_legs/" in img_base_url:
        return "2D obrázek nohy s kótami"
    if "_left" in fname:
        side = "levá část"
    elif "_right" in fname:
        side = "pravá část"
    elif "bulkhead" in fname:
        side = "přepážka"
    else:
        side = ""
    if "first_3d" in fname:
        kind = "3D pohled zepředu"
    elif "second_3d" in fname:
        kind = "3D pohled, druhý úhel"
    elif "dim" in fname:
        kind = "2D nákres s kótami"
    else:
        kind = "2D nákres"
    return f"{kind}, {side}" if side else kind

def main(limit=None, dry_run=False):
    rows = json.load(open(os.path.join(SCRATCH, "parsed_322.json")))
    rows = [r for r in rows if r["vehicle"] and r["price_czk"] and r["weight_g"]]
    if limit:
        rows = rows[:limit]

    conn = _env.get_conn()
    cur = conn.cursor()

    ok, failed, skipped = 0, [], []

    for i, row in enumerate(rows):
        uuid = row["uuid"]
        print(f"[{i+1}/{len(rows)}] {uuid} {row['vehicle']} ...", flush=True)

        brand = detect_brand(row["vehicle"])
        if not brand:
            print("  PRESKOCENO: neznama znacka")
            skipped.append({**row, "reason": "neznama znacka"})
            continue
        hub_id = BRAND_TO_HUB[brand]

        try:
            detail, err = fetch_detail(uuid)
        except Exception as e:
            err = str(e)
            detail = None
        if err or not detail or not detail["images"]:
            print(f"  CHYBA fetch/obrazky: {err}")
            failed.append({**row, "reason": err or "zadne obrazky"})
            continue

        vehicle_display = strip_length_suffix(row["vehicle"])
        uuid8 = uuid.split('-')[0]
        # Robert 2026-09-18 ("kod plne cele!! toto neni alternativni ale
        # jediny platny") - SKU je PRIMO cely UUID, ne zkraceny prefix +
        # samostatny "alternativni kod" (matouci, jako by UUID bylo jen
        # doplnkove, kdyz je to jediny skutecny identifikator sestavy).
        sku = f"VD-{uuid}"
        slug_base = f"regalova-vestavba-{slugify(vehicle_display)}-{uuid8}-vandrawee"
        # OPRAVA 2026-09-23 - "vanDrawee" odstraneno i z nazvu (TEXT_FILTR.md
        # pravidlo 15, viz komentar u description nize).
        name = f"Regálová vestavba – {vehicle_display}"

        labels = humanize_components(detail["components_raw"])
        comp_txt = ", ".join(labels) if labels else "hliníková stavebnice na míru"
        # Robert 2026-09-18 ("popis detailu strukturovane, spise do
        # tabulky") - kusovnik jde do product_specs_json (existujici
        # generic key->value tabulka v product.html), description
        # zustava jen kratky uvod, bez duplicity.
        specs = {}
        for sec_title, subgroups in detail["sections"]:
            for sub_title, items in subgroups:
                key = f"{sec_title} – {sub_title}" if sub_title else sec_title
                specs[key] = ", ".join(f"{q} {n}" for q, n in items)
        # OPRAVA 2026-09-23 (bot5): "vanDrawee" odstranena z ceskeho
        # zakaznickeho textu (TEXT_FILTR.md pravidlo 15 - Robert: "v
        # ceskych textech ho nebudeme pouzivat", vyhrazeno jen pro
        # zahranicni marketing). Blok "Cena obsahuje" (Robert 2026-09-23)
        # uz NENI tady zapeceny - je editovatelny v adminu (app_settings,
        # viz api/admin_settings.py VANDRAWEE_CENA_OBSAHUJE_KEY) a
        # pripojuje se DYNAMICKY az na frontendu (webapp/product.html,
        # api/products.py), aby zmena nastaveni platila na vsech kartach
        # bez dalsiho backfillu.
        # OPRAVA 2026-09-23b (Robert): "tuto větu nepouzivat: Přesný
        # obsah sestavy (kusovník) najdete v tabulce specifikací níže."
        # - odstranena natrvalo (kusovnik uz je videt v samostatne
        # tabulce specifikaci sam o sobe, netreba na nej v popisu
        # odkazovat).
        description = f"Hliníková regálová vestavba do nákladového prostoru {vehicle_display}."
        short_description = (
            f"Hliníková regálová vestavba pro {vehicle_display} - "
            f"{comp_txt}, cena bez montáže."
        )

        if dry_run:
            print(f"  OK (dry-run) hub={hub_id} sku={sku} images={len(detail['images'])}")
            ok += 1
            continue

        # stahnout obrazky do stagingu
        local_images = []
        for img_base in detail["images"][:5]:
            fname_src = img_base.rsplit("/", 1)[-1] + ".png"
            local_path = os.path.join(IMG_STAGING, f"{uuid}_{fname_src}")
            try:
                ir = requests.get(img_base + ".png", headers=HEADERS, timeout=20)
                if ir.status_code == 200 and len(ir.content) > 1000:
                    with open(local_path, "wb") as f:
                        f.write(ir.content)
                    local_images.append((local_path, caption_for(img_base)))
            except Exception as e:
                print(f"    obrazek selhal: {e}")

        if not local_images:
            print("  CHYBA: zadny obrazek se nepodarilo stahnout")
            failed.append({**row, "reason": "obrazky selhaly pri stahovani"})
            continue

        try:
            cur.execute(
                "INSERT INTO shop_products (category_id, sku, name, slug, description, "
                "price_czk_placeholder, weight_g, active, manufacturer, supplier_name, "
                "short_description, product_specs_json, "
                "meta_title, meta_description) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,0,NULL,'vanDrawee',%s,%s,%s,%s)",
                (hub_id, sku, name, slug_base, description, row["price_czk"], row["weight_g"],
                 short_description, json.dumps(specs, ensure_ascii=False),
                 f"{name}", f"{short_description[:250]}")
            )
            product_id = cur.lastrowid

            for sort_order, (local_path, caption) in enumerate(local_images):
                rand_suffix = "%08x" % random.getrandbits(32)
                dest_fname = f"product-{product_id}_{slug_base}-{rand_suffix}.png"
                dest_path = f"/opt/konfigurator/webapp/content-files/gallery-items/{dest_fname}"
                os.rename(local_path, dest_path)
                os.chmod(dest_path, 0o644)
                os.chown(dest_path, 33, 33)  # www-data:www-data
                cur.execute(
                    "INSERT INTO content_gallery_items (owner_type, owner_id, filename, media_type, "
                    "source_url, caption, is_public, sort_order) "
                    "VALUES ('product', %s, %s, 'image', %s, %s, 1, %s)",
                    (product_id, dest_fname, detail["url"], caption, sort_order)
                )
            conn.commit()
            print(f"  HOTOVO id={product_id} hub={hub_id} obrazky={len(local_images)}")
            ok += 1
        except Exception as e:
            conn.rollback()
            print(f"  DB CHYBA: {e}")
            failed.append({**row, "reason": f"DB: {e}"})

        time.sleep(0.4)

    print(f"\n=== SHRNUTI: OK={ok}, FAILED={len(failed)}, SKIPPED={len(skipped)} z {len(rows)} ===")
    with open(os.path.join(SCRATCH, "bulk_import_failed.json"), "w") as f:
        json.dump(failed, f, ensure_ascii=False, indent=1)
    with open(os.path.join(SCRATCH, "bulk_import_skipped.json"), "w") as f:
        json.dump(skipped, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    dry_run = "--dry-run" in sys.argv
    main(limit=limit, dry_run=dry_run)
