#!/usr/bin/env python3
"""
Import kategorii obrazku z logiman.cz (Robert: "prevezmi obrazky
kategorii z logiman.cz"). Nase kategorie byly importovany ze Shoptet
katalogu logiman.cz a jejich slugy odpovidaji realnym URL na tomto
webu - vyuzito k parovani.

Postup: pro kazdou nasi kategorii, ktera MA DETI (hub), stahne se jeji
realna stranka na logiman.cz (podle slugu) a z HTML se vytahnou
miniatury podkategorii (<img ... alt="Nazev kategorie">). Nazev se
sparuje s nasi DB (presna shoda), obrazek se stahne a ulozi presne
stejnou konvenci jako _save_category_image() v api/app.py
({cat_id}_image_filename_{hex}.{ext} v webapp/content-files/categories/),
DB sloupec content_categories.image_filename se aktualizuje primo.

Nejde pres HTTP API (zadne prihlaseni k dispozici pro tento import) -
piseme primo do DB/filesystemu, presne stejnym zpusobem jako by to
udelal _save_category_image() z api/app.py.
"""
import os
import re
import html
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

API_DIR = "/opt/konfigurator/api"
CATEGORY_IMAGE_DIR = "/opt/konfigurator/webapp/content-files/categories"
ALLOWED_EXT = {"jpg", "jpeg", "png", "webp", "gif"}
BASE_URL = "https://www.logiman.cz"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; konfigurator-import/1.0)"}

# Nase slugy (autogenerovane pri importu) se u par kategorii mirne lisi
# od realnych slugu na logiman.cz (overeno pres sitemap.xml) - typicky
# u nazvu s carkou (nas slugify udela jeden pomlcka, realny web ma "--").
SLUG_OVERRIDES = {
    182: "balici-stoly-pracoviste",
    200: "komponenty--polotovary-a-casti-stolu",
}

IMG_RE = re.compile(
    r'<img src="(https://cdn\.myshoptet\.com/[^"]*?/categories/thumb/[^"]+?)" alt="([^"]*)"'
)


def load_env():
    env_path = os.path.join(API_DIR, ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def get_conn():
    import pymysql
    return pymysql.connect(
        host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT", 3306)),
        user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_text(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_bytes(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def extract_category_images(page_html):
    out = []
    for m in IMG_RE.finditer(page_html):
        url, alt = m.group(1), html.unescape(m.group(2)).strip()
        out.append((alt, url))
    return out


def main():
    load_env()
    os.makedirs(CATEGORY_IMAGE_DIR, exist_ok=True)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, parent_id, name, slug, image_filename FROM content_categories")
            rows = cur.fetchall()
    finally:
        conn.close()

    by_id = {r["id"]: r for r in rows}
    already_has_image = {r["id"] for r in rows if r["image_filename"]}
    children_map = {}
    for r in rows:
        children_map.setdefault(r["parent_id"], []).append(r)

    hub_ids = [cid for cid in by_id if children_map.get(cid)]

    found = {}  # category_id -> image_url
    matched_names = []
    unmatched_entries = []  # (hub_name, image alt) not matching any expected child

    for hub_id in hub_ids:
        hub = by_id[hub_id]
        slug = SLUG_OVERRIDES.get(hub_id, hub["slug"])
        if not slug:
            continue
        url = f"{BASE_URL}/{slug}/"
        try:
            page = fetch_text(url)
        except Exception as e:
            print(f"SKIP hub {hub_id} ({hub['name']}): fetch error: {e}")
            continue
        pairs = extract_category_images(page)
        name_to_child = {c["name"]: c["id"] for c in children_map[hub_id]}
        for alt, img_url in pairs:
            cid = name_to_child.get(alt)
            if cid is not None:
                if cid in already_has_image:
                    continue
                if cid not in found:
                    found[cid] = img_url
                    matched_names.append((cid, by_id[cid]["name"]))
            else:
                unmatched_entries.append((hub["name"], alt))

    print(f"Hub stranek zpracovano: {len(hub_ids)}")
    print(f"Sparovano obrazku: {len(found)}")
    print(f"Nespárováno (existuje na logiman.cz, ale nemáme takovou podkategorii): {len(unmatched_entries)}")

    # download + save + update DB
    conn = get_conn()
    saved = 0
    failed = []
    try:
        with conn.cursor() as cur:
            for cid, img_url in found.items():
                ext = img_url.rsplit(".", 1)[-1].split("?")[0].lower()
                if ext not in ALLOWED_EXT:
                    failed.append((cid, "nepovolena pripona: " + ext))
                    continue
                try:
                    data = fetch_bytes(img_url)
                except Exception as e:
                    failed.append((cid, f"stahovani selhalo: {e}"))
                    continue
                stored_name = f"{cid}_image_filename_{os.urandom(6).hex()}.{ext}"
                with open(os.path.join(CATEGORY_IMAGE_DIR, stored_name), "wb") as f:
                    f.write(data)
                cur.execute(
                    "UPDATE content_categories SET image_filename=%s WHERE id=%s",
                    (stored_name, cid),
                )
                saved += 1
        conn.commit()
    finally:
        conn.close()

    print(f"Ulozeno a zapsano do DB: {saved}")
    if failed:
        print("Chyby:")
        for cid, msg in failed:
            print(f"  {cid} ({by_id[cid]['name']}): {msg}")

    # kategorie bez obrazku (pro report) - vcetne tech, co uz mely obrazek
    # PRED timhle behem (dulezite pro spravny soucet pri opakovanem behu)
    has_image_now = already_has_image | set(found)
    no_image_ids = [cid for cid in by_id if cid not in has_image_now]
    print(f"\nKategorie BEZ obrázku po importu: {len(no_image_ids)} z {len(by_id)}")


if __name__ == "__main__":
    main()
