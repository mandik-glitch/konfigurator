"""Kategorie (strom nad 3D scenou i e-shopem): CRUD, obsah (content_pages/
content_files), obrázky, bulk-move/reorder, export/import CSV, search,
+ /api/admin/category-price-coefficients a /api/admin/logiman-price-check.

Vyčleněno z api/app.py (PLAN_ROZDELENI_BACKENDU.md skupina 14) - čistý
přesun, žádná změna chování/URL. `_build_category_tree`,
`_category_tree_show_hidden`, `_category_products_with_images`,
`_slugify`, `ALLOWED_CATEGORY_IMAGE_EXT` zůstávají v app.py, protože je
používá i kód mimo tuhle skupinu (SSR rendering e-shopu - plán skupina
13, homepage-blocks/sidebar-blocks admin - plán skupina 2) - modul si
je jen importuje. Stejně tak `_usage_images_for_products`/
`_compatible_accessories` - products.py je importuje přímo z app.py
(nalezeno až při live restartu po mergu, bot15), takže musí zůstat v
jádru, i když je používá i tenhle modul. `logiman_price_check` NENÍ
tady - už existuje (byte-identicky) v price_scraping.py (skupina 6,
vyčleněno dřív), přesun sem by způsobil duplicitní registraci route.
"""
import csv
import io
import os
import re

from flask import request, jsonify, Response
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, require_permission, admin_required, current_user,
    log_audit, parse_bulk_ids, bulk_update_fields,
    build_category_path_fn, resolve_category_path,
    UPLOAD_DIR, ALLOWED_CATEGORY_IMAGE_EXT,
    _slugify, _build_category_tree, _category_tree_show_hidden,
    _category_products_with_images, get_setting,
    _usage_images_for_products, _compatible_accessories,
    _category_descendant_ids, CATEGORY_ID_NAPOSLEDY_PRIDANE, CATEGORY_ID_MATERIALY_ROOT,
)
# bot16, 2026-09-24 (Robert pres bot3, pravidlo 52 - rozsireni "FIO zivy
# kurz v Ceny profilu" i na eshop) - stejny import-vzor jako uz pouziva
# api/storefront_pages.py::_is_staff_request. ZAMERNE NENI primo v
# _category_products_with_images() (app.py) - ta je sdilena i se SSR
# strankou pro roboty (_category_page_response), admin-only naklad/marze
# tam NESMI nikdy proniknout, ani omylem - proto se doplnuje az tady, jen
# v interaktivnim API pro category.html.
from products import _can_view_dogus_admin_cost


def _category_product_facets(cur, cat_id):
    # bot5 2026-08-10 - dostupne hodnoty pro filtr prurezu/drazky v
    # kategorii, VZDY z celeho (nefiltrovaneho) seznamu aktivnich
    # produktu kategorie - filtr tak po vyberu nezmizi/neztenci se sam
    # sobe (facety zustavaji stabilni, meni se jen "products" vys).
    # bot5 2026-09-15 (Robert pres bot3, "filtr podle slotu chybi" u
    # kategorii jako "T šrouby"): puvodni WHERE vyzadovalo
    # cross_section_label VZDY, i kdyz se z radku pocita jen
    # groove_family - prislusenstvi bez zobaku (sroubky/matice, groove_
    # family vyplnene, cross_section_label VZDY NULL, nejsou to
    # extrudovane profily s prurezem) tak vypadlo z GROUP BY uplne,
    # facets vysly obe prazdne a renderFilters() (category.html) se
    # vubec nevykreslil. Radek ted projde, kdyz je vyplnene ALESPON
    # jedno z dvou polí.
    # bot5 2026-09-17 - stejne (category_id=primarni NEBO sekundarni pres
    # shop_product_categories) jako _category_products_with_images
    # (api/app.py), aby facety odpovidaly tomu, co se na strance skutecne
    # ukaze - viz sql/2026-09-17_shop_product_categories.sql.
    # bot7 2026-09-25 (Robert pres bot3, pravidlo 52 - dedeny vypis od
    # nadrazene kategorie dolu) - facety musi pokryt STEJNOU mnozinu
    # produktu jako _category_products_with_images (sebe + vsichni
    # potomci), jinak by filtr nabizel hodnoty, ktere se na strance
    # vubec nezobrazi. "Naposledy pridane" (viz CATEGORY_ID_NAPOSLEDY_
    # PRIDANE) nema zadny filtr - vraci prazdne facety rovnou.
    try:
        cat_id_int = int(cat_id)
    except (TypeError, ValueError):
        cat_id_int = None
    if cat_id_int == CATEGORY_ID_NAPOSLEDY_PRIDANE:
        return {"cross_sections": [], "groove_families": []}
    # Vyjimka pro vetev materialu (Robert 2026-09-25, viz stejny komentar
    # u CATEGORY_ID_MATERIALY_ROOT v app.py) - dedeni se netyka 149 a
    # jejich potomku, cross_section/groove filtry navic davaji smysl
    # prave jen u konkretni (ne dedene) kategorie profilu.
    materialy_subtree = _category_descendant_ids(cur, CATEGORY_ID_MATERIALY_ROOT)
    if cat_id_int in materialy_subtree:
        descendant_ids = [cat_id]
    else:
        descendant_ids = _category_descendant_ids(cur, cat_id)
    id_placeholders = ",".join(["%s"] * len(descendant_ids))
    cur.execute(f"""
        SELECT cross_section_label, groove_family, COUNT(*) AS n
        FROM shop_products
        WHERE (category_id IN ({id_placeholders}) OR id IN
               (SELECT product_id FROM shop_product_categories WHERE category_id IN ({id_placeholders})))
          AND active=1 AND is_archived=0
          AND (cross_section_label IS NOT NULL OR groove_family IS NOT NULL)
        GROUP BY cross_section_label, groove_family
    """, list(descendant_ids) + list(descendant_ids))
    rows = cur.fetchall()
    cross_sections = {}
    groove_families = {}
    for r in rows:
        if r["cross_section_label"] is not None:
            cross_sections[r["cross_section_label"]] = cross_sections.get(r["cross_section_label"], 0) + r["n"]
        # bot5 2026-08-10 - groove_family muze byt CSV vice hodnot
        # ("6,8,10" u prislusenstvi bez zobaku, viz _category_products_
        # with_images) - produkt se pak pocita do KAZDE z nich (vyber
        # ktehokoli filtru ho spravne zahrne).
        for g in (r["groove_family"] or "").split(","):
            g = g.strip()
            if g:
                groove_families[g] = groove_families.get(g, 0) + r["n"]

    def _cross_section_key(label):
        a, _, b = label.partition("x")
        try:
            return (int(a), int(b))
        except ValueError:
            return (0, 0)

    return {
        "cross_sections": [{"value": k, "count": v} for k, v in sorted(cross_sections.items(), key=lambda kv: _cross_section_key(kv[0]))],
        "groove_families": [{"value": k, "count": v} for k, v in sorted(groove_families.items(), key=lambda kv: int(kv[0]))],
    }

CATEGORY_IMAGE_DIR = os.path.join(UPLOAD_DIR, "categories")
os.makedirs(CATEGORY_IMAGE_DIR, exist_ok=True)

def _unique_category_slug(cur, base, exclude_id=None):
    candidate = base
    n = 2
    while True:
        if exclude_id is not None:
            cur.execute("SELECT id FROM content_categories WHERE slug=%s AND id<>%s", (candidate, exclude_id))
        else:
            cur.execute("SELECT id FROM content_categories WHERE slug=%s", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}-{n}"
        n += 1

def _save_category_image(cat_id, file, column):
    # `column` je VZDY literal ("image_filename"/"og_image_filename")
    # napevno z volajici route, nikdy z requestu - bezpecne interpolovat
    # do SQL bez rizika injection.
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_CATEGORY_IMAGE_EXT:
        return None, "Nepovolený formát obrázku (jpg/png/webp/gif)."
    stored_name = f"{cat_id}_{column}_{os.urandom(6).hex()}.{ext}"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, {column} AS old_name FROM content_categories WHERE id=%s", (cat_id,))
            row = cur.fetchone()
            if not row:
                return None, "Kategorie neexistuje."
            old_name = row["old_name"]
            file.save(os.path.join(CATEGORY_IMAGE_DIR, stored_name))
            cur.execute(f"UPDATE content_categories SET {column}=%s WHERE id=%s", (stored_name, cat_id))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(CATEGORY_IMAGE_DIR, old_name))
        except OSError:
            pass
    return stored_name, None

def _delete_category_image(cat_id, column):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {column} AS old_name FROM content_categories WHERE id=%s", (cat_id,))
            row = cur.fetchone()
            old_name = row["old_name"] if row else None
            cur.execute(f"UPDATE content_categories SET {column}=NULL WHERE id=%s", (cat_id,))
        conn.commit()
    finally:
        conn.close()
    if old_name:
        try:
            os.remove(os.path.join(CATEGORY_IMAGE_DIR, old_name))
        except OSError:
            pass

@app.get("/api/categories")
def categories_list():
    # VEREJNE (rozhodnuti 2026-07-23): strom kategorii a jejich obsah (navody,
    # videa, PDF) je bez prihlaseni, jen samotna 3D scena (scene.html) a
    # administrace zustavaji za loginem. Zalozeni/uprava/smazani kategorie
    # (POST/PUT/DELETE nize) zustava admin_required.
    #
    # Viditelnost (Robert, "kompletni infrastruktura kategorii" dle
    # Shoptet screenshotu, 2026-07-26): kategorie s is_visible=0 jsou
    # vyrazeny (i s celym podstromem) pro verejnost, ale VIDITELNE pro
    # prihlaseneho uzivatele s pravem kategorie_obsah/zobrazit (admin
    # strom je musi videt, aby je mohl zase zapnout).
    show_hidden = _category_tree_show_hidden()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            tree = _build_category_tree(cur, show_hidden)
            # Robert 2026-08-18: docasny feature-flag pro deaktivaci kosiku -
            # /api/categories je jediny endpoint, ktery uz dnes volaji
            # UPLNE VSECHNY zakaznicke stranky (index/category/product/blok)
            # bez ohledu na prihlaseni, takze je to nejlevnejsi misto, kde
            # ho frontendu predat (zadny novy endpoint/extra request).
            cart_enabled = get_setting(cur, "cart_enabled", "1")
            # Robert (pres bot3, 2026-09-04): "deaktivuj slevove kody vsude
            # v e-shopu" - stejny duvod/misto jako cart_enabled o par radku
            # vyse (jediny endpoint, ktery uz volaji VSECHNY zakaznicke
            # stranky bez ohledu na prihlaseni).
            discount_codes_enabled = get_setting(cur, "discount_codes_enabled", "1")
    finally:
        conn.close()
    return jsonify({
        "tree": tree,
        "cart_enabled": cart_enabled != "0",
        "discount_codes_enabled": discount_codes_enabled != "0",
    })

@app.get("/api/admin/category-price-coefficients")
@admin_required
def category_price_coefficients_list():
    # Robert 2026-08-09: "koeficient přepočtu cen potřebuji ještě
    # kompletně pohromadě jako tabulku, Kategorie > koeficient" + "jen
    # pro admina" - dřív šel dogus_price_coefficient upravit jen
    # jednotlivě v editaci každé kategorie zvlášť (viz categories_update
    # nize), tenhle endpoint da adminovi plochy prehled VSECH kategorii
    # s aspon 1 aktivnim Dogus produktem najednou. Ukladani jednotlivych
    # radku pak jde primo pres jiz existujici PUT /api/categories/<id>
    # (zadny novy zapisovy endpoint netreba).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.dogus_price_coefficient,
                       COUNT(p.id) AS n_products,
                       SUM(p.dogus_matched_at IS NOT NULL) AS n_dogus
                FROM content_categories c
                JOIN shop_products p ON p.category_id = c.id AND p.active=1 AND p.is_archived=0
                GROUP BY c.id, c.name, c.dogus_price_coefficient
                HAVING n_dogus > 0
                ORDER BY c.name
            """)
            rows = cur.fetchall()
            # Robert 2026-08-09: "přidej mi do tabulky vždy 1 zástupce
            # produkt z každé kategorie, s cenou z Logimanu (podle sku) a s
            # naší aktuální cenou" - 1 reprezentativni produkt na kategorii,
            # prednostne ten, co uz ma price_source_url (jde ho pak rovnou
            # zivě porovnat s logiman.cz, viz logiman_price_check nize).
            for r in rows:
                cur.execute("""
                    SELECT id, sku, name, price_source_url, price_czk_placeholder
                    FROM shop_products
                    WHERE category_id=%s AND active=1 AND is_archived=0
                    ORDER BY (price_source_url IS NOT NULL) DESC, id ASC
                    LIMIT 1
                """, (r["id"],))
                rep = cur.fetchone()
                r["rep_product"] = None
                if rep:
                    r["rep_product"] = {
                        "id": rep["id"], "sku": rep["sku"], "name": rep["name"],
                        "has_logiman_url": rep["price_source_url"] is not None,
                        "our_price_czk": float(rep["price_czk_placeholder"]) if rep["price_czk_placeholder"] is not None else None,
                    }
    finally:
        conn.close()
    for r in rows:
        r["dogus_price_coefficient"] = (
            float(r["dogus_price_coefficient"]) if r["dogus_price_coefficient"] is not None else None
        )
        r["n_products"] = int(r["n_products"])
        r["n_dogus"] = int(r["n_dogus"])
    return jsonify({"categories": rows})

@app.post("/api/categories")
@require_permission("kategorie", "vytvorit")
def categories_create():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    parent_id = body.get("parent_id")
    if not name:
        return jsonify({"error": "Vyplň název kategorie."}), 400
    slug_input = (body.get("slug") or "").strip()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if parent_id is not None:
                cur.execute("SELECT id FROM content_categories WHERE id=%s", (parent_id,))
                parent = cur.fetchone()
                if not parent:
                    return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
            slug = _unique_category_slug(cur, _slugify(slug_input or name))
            cur.execute(
                "INSERT INTO content_categories (parent_id, name, slug, sort_order) VALUES (%s,%s,%s,0)",
                (parent_id, name, slug),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "category", new_id, name)
    return jsonify({"status": "ok", "id": new_id, "slug": slug})

@app.put("/api/categories/<int:cat_id>")
@require_permission("kategorie", "upravit")
def categories_update(cat_id):
    # Rozsireno (Robert, "kompletni infrastruktura kategorii", 2026-07-26)
    # z puvodniho "jen name" na castecnou aktualizaci - klient posila
    # jen ta pole, ktera meni (stejny vzor jako shop_products_update).
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fields, params = [], []
            if "name" in body:
                name = (body.get("name") or "").strip()
                if not name:
                    return jsonify({"error": "Vyplň název kategorie."}), 400
                fields.append("name=%s"); params.append(name)
            if "slug" in body:
                cur.execute("SELECT name, slug FROM content_categories WHERE id=%s", (cat_id,))
                existing = cur.fetchone()
                old_slug = existing["slug"] if existing else None
                raw_slug = (body.get("slug") or "").strip()
                if raw_slug:
                    base_slug = _slugify(raw_slug)
                else:
                    base_slug = _slugify(existing["name"] if existing else "kategorie")
                slug = _unique_category_slug(cur, base_slug, exclude_id=cat_id)
                fields.append("slug=%s"); params.append(slug)
                if old_slug and old_slug != slug:
                    # Stara URL by jinak zacala vracet 404 a Google by prisel
                    # o dosavadni index/odkazy - viz sql/2026-08-03_seo_
                    # redirects_keyword.sql. Odstranime i pripadny redirect
                    # ktery by nyni mel stejny old_slug jako novy slug (at
                    # nezustane nesmyslny zaznam mirici sam na sebe).
                    cur.execute(
                        "INSERT INTO content_category_redirects (old_slug, category_id) VALUES (%s,%s) "
                        "ON DUPLICATE KEY UPDATE category_id=VALUES(category_id), created_at=NOW()",
                        (old_slug, cat_id),
                    )
                    cur.execute("DELETE FROM content_category_redirects WHERE old_slug=%s", (slug,))
            if "nav_label" in body:
                fields.append("nav_label=%s"); params.append((body.get("nav_label") or "").strip() or None)
            if "meta_title" in body:
                fields.append("meta_title=%s"); params.append((body.get("meta_title") or "").strip() or None)
            if "meta_description" in body:
                fields.append("meta_description=%s"); params.append((body.get("meta_description") or "").strip() or None)
            if "focus_keyword" in body:
                fields.append("focus_keyword=%s"); params.append((body.get("focus_keyword") or "").strip() or None)
            if "is_visible" in body:
                fields.append("is_visible=%s"); params.append(1 if body.get("is_visible") else 0)
            if "menu_expanded" in body:
                fields.append("menu_expanded=%s"); params.append(1 if body.get("menu_expanded") else 0)
            if "dogus_price_coefficient" in body:
                # Koeficient kategorie pro prepocet E-SHOPOVE ceny z Dogus USD
                # (scripts/2026-08-09_dogus_price_recompute.py, denne ve 3:20,
                # WORKFLOW pravidlo 9): USD x kurz Fio x koeficient, u tyci
                # x3, nahoru na cele Kc; kategorie bez koeficientu se
                # preskoci (QA missing_dogus_price_coefficient). NENI to
                # koeficient 3D sceny - ten je app_settings.scene_price_
                # coefficient (viz katalog() v app.py); scena cte e-shopovou
                # cenu (profil /3). Pole vzniklo 2026-08-08 (sql/2026-08-08_
                # dogus_pairing.sql) s puvodnim zamerem "prepocet pro 3D
                # scenu"; od 2026-08-09 ho Robert pouziva na e-shopovou cenu.
                raw = body.get("dogus_price_coefficient")
                if raw in (None, ""):
                    fields.append("dogus_price_coefficient=%s"); params.append(None)
                else:
                    try:
                        coef = float(raw)
                    except (TypeError, ValueError):
                        return jsonify({"error": "Koeficient musí být číslo."}), 400
                    fields.append("dogus_price_coefficient=%s"); params.append(coef)
            if not fields:
                return jsonify({"error": "Nic ke změně."}), 400
            params.append(cat_id)
            cur.execute(f"UPDATE content_categories SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "category", cat_id, ", ".join(fields))
    return jsonify({"status": "ok"})

@app.post("/api/categories/<int:cat_id>/image")
@require_permission("kategorie", "upravit")
def category_image_upload(cat_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    stored_name, err = _save_category_image(cat_id, f, "image_filename")
    if err:
        return jsonify({"error": err}), 400
    log_audit(current_user()["id"], "update", "category", cat_id, "obrázek kategorie")
    return jsonify({"status": "ok", "image_filename": stored_name})

@app.delete("/api/categories/<int:cat_id>/image")
@require_permission("kategorie", "upravit")
def category_image_delete(cat_id):
    _delete_category_image(cat_id, "image_filename")
    log_audit(current_user()["id"], "update", "category", cat_id, "obrázek kategorie smazán")
    return jsonify({"status": "ok"})

@app.post("/api/categories/<int:cat_id>/og-image")
@require_permission("kategorie", "upravit")
def category_og_image_upload(cat_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    stored_name, err = _save_category_image(cat_id, f, "og_image_filename")
    if err:
        return jsonify({"error": err}), 400
    log_audit(current_user()["id"], "update", "category", cat_id, "náhledový obrázek (SEO)")
    return jsonify({"status": "ok", "og_image_filename": stored_name})

@app.delete("/api/categories/<int:cat_id>/og-image")
@require_permission("kategorie", "upravit")
def category_og_image_delete(cat_id):
    _delete_category_image(cat_id, "og_image_filename")
    log_audit(current_user()["id"], "update", "category", cat_id, "náhledový obrázek (SEO) smazán")
    return jsonify({"status": "ok"})

@app.post("/api/categories/bulk-move")
@require_permission("kategorie", "upravit")
def categories_bulk_move():
    # Hromadny presun vybranych kategorii pod jinou nadrazenou kategorii
    # (V11, bot3, 2026-07-26, viz NAVRH_HROMADNE_AKCE.md - odpovida Shoptet
    # "Presunout"). Kontroluje cyklus - nelze presunout kategorii pod sebe
    # ani pod vlastniho (i neprimeho) potomka.
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    parent_id = body.get("parent_id")
    if parent_id is not None:
        try:
            parent_id = int(parent_id)
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná nadřazená kategorie."}), 400
        if parent_id in ids:
            return jsonify({"error": "Kategorii nelze přesunout samu pod sebe."}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, parent_id FROM content_categories")
            by_id = {c["id"]: c for c in cur.fetchall()}
            if parent_id is not None:
                if parent_id not in by_id:
                    return jsonify({"error": "Nadřazená kategorie neexistuje."}), 400
                current = parent_id
                seen = set()
                while current is not None and current not in seen:
                    seen.add(current)
                    if current in ids:
                        return jsonify({"error": "Nelze přesunout kategorii pod jejího vlastního potomka."}), 400
                    current = by_id.get(current, {}).get("parent_id")

            updated = bulk_update_fields(cur, "content_categories", ids, {"parent_id": parent_id})
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_move", "category", None,
              f"{updated} kategorií -> parent_id={parent_id}")
    return jsonify({"status": "ok", "updated": updated})

@app.put("/api/categories/reorder")
@require_permission("kategorie", "upravit")
def categories_reorder():
    # Drag&drop stromu v adminu (Robert 2026-07-26: "strom kategorii ...
    # ať s nima lze manipulovat"). Klient posila VZDY kompletni seznam
    # vsech kategorii s cilovym parent_id/sort_order (cely strom po
    # provedenem tahu) - jednodussi a bezpecnejsi nez pocitat diff zmen,
    # 99 kategorii je malo na to aby na tom zalezelo. Cyklus se overuje
    # z POSILANEHO payloadu (predstavuje CILOVY stav), ne z DB.
    body = request.get_json(silent=True) or {}
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "Chybí items."}), 400

    parsed = []
    parent_by_id = {}
    for it in items:
        try:
            cid = int(it.get("id"))
            sort_order = int(it.get("sort_order", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná data."}), 400
        parent_id = it.get("parent_id")
        if parent_id is not None:
            try:
                parent_id = int(parent_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Neplatná data."}), 400
        parsed.append((cid, parent_id, sort_order))
        parent_by_id[cid] = parent_id

    for cid, parent_id, _ in parsed:
        current = parent_id
        seen = set()
        while current is not None:
            if current == cid or current in seen:
                return jsonify({"error": "Neplatná struktura stromu (cyklus)."}), 400
            seen.add(current)
            current = parent_by_id.get(current)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_categories")
            existing_ids = {r["id"] for r in cur.fetchall()}
            for cid, _, _ in parsed:
                if cid not in existing_ids:
                    return jsonify({"error": f"Kategorie {cid} neexistuje."}), 400
            for cid, parent_id, sort_order in parsed:
                cur.execute(
                    "UPDATE content_categories SET parent_id=%s, sort_order=%s WHERE id=%s",
                    (parent_id, sort_order, cid),
                )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "reorder", "category", None, f"{len(parsed)} kategorií přeuspořádáno")
    return jsonify({"status": "ok"})

@app.delete("/api/categories/<int:cat_id>")
@require_permission("kategorie", "smazat")
def categories_delete(cat_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM content_categories WHERE id=%s", (cat_id,))
            existing = cur.fetchone()
            cur.execute("DELETE FROM content_categories WHERE id=%s", (cat_id,))
        conn.commit()
    finally:
        conn.close()
    import gallery_items
    gallery_items.delete_items_for_owner("category", cat_id)
    log_audit(current_user()["id"], "delete", "category", cat_id, existing["name"] if existing else None)
    return jsonify({"status": "ok"})

@app.get("/api/categories/export.csv")
@require_permission("kategorie", "zobrazit")
def categories_export():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, parent_id, name FROM content_categories ORDER BY parent_id IS NULL DESC, sort_order, name")
            cats = cur.fetchall()
    finally:
        conn.close()
    cat_path = build_category_path_fn(cats)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "category_path"])
    for c in cats:
        writer.writerow([c["id"], cat_path(c["id"])])
    log_audit(current_user()["id"], "export", "category", None, f"{len(cats)} kategorií")
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=kategorie_export.csv"},
    )

@app.post("/api/categories/import")
@require_permission("kategorie", "vytvorit")
def categories_import():
    # ADITIVNI import (viz poznamka u resolve_category_path) - kazdy
    # radek je cesta "A > B > C", chybejici uzly cesty se vytvori,
    # existujici se jen znovupouziji. Nic se nemaze ani nepresouva.
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Nahraj CSV soubor (pole 'file')."}), 400
    try:
        text = f.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "Soubor musí být v kódování UTF-8."}), 400
    reader = csv.DictReader(io.StringIO(text))
    if "category_path" not in (reader.fieldnames or []):
        return jsonify({"error": "CSV musí obsahovat sloupec category_path."}), 400
    cache = {}
    created_ids = []
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for row in reader:
                path = (row.get("category_path") or "").strip()
                if path:
                    resolve_category_path(cur, path, cache, created_ids)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "import", "category", None, f"{len(created_ids)} nových kategorií z CSV")
    return jsonify({"status": "ok", "created": len(created_ids)})

@app.get("/api/categories/<int:cat_id>/content")
def category_content_get(cat_id):
    # VEREJNE - viz poznamka u categories_list(). Vraci i produkty (sjednoceny
    # strom - kategorie muze mit obsah I produkty zaroven).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, parent_id, slug, nav_label, meta_title, meta_description, focus_keyword,
                       is_visible, menu_expanded, image_filename, og_image_filename, dogus_price_coefficient
                FROM content_categories WHERE id=%s
            """, (cat_id,))
            cat = cur.fetchone()
            if not cat:
                return jsonify({"error": "Kategorie neexistuje."}), 404
            cat["is_visible"] = bool(cat["is_visible"])
            cat["menu_expanded"] = bool(cat["menu_expanded"])
            cat["dogus_price_coefficient"] = (
                float(cat["dogus_price_coefficient"]) if cat["dogus_price_coefficient"] is not None else None
            )
            cur.execute("SELECT title, intro_html, body_html, bottom_body_html, video_url FROM content_pages WHERE category_id=%s", (cat_id,))
            page = cur.fetchone() or {"title": None, "intro_html": None, "body_html": None, "bottom_body_html": None, "video_url": None}
            cur.execute("SELECT id, filename, uploaded_at FROM content_files WHERE category_id=%s ORDER BY uploaded_at DESC", (cat_id,))
            files = cur.fetchall()
            # bot6 2026-08-09 ("seradit defaultne produkty v kategoriim od
            # nejlevnejsich") - vychozi hodnota zmenena z "name" na
            # "price_asc". Tyka se jen tohohle interaktivniho endpointu
            # (co skutecne vidi zakaznik) - SSR cesta pro roboty
            # (_category_page_response nize) zustava zamerne beze zmeny,
            # zadny SEO dopad tu nebyl pozadovany.
            sort = request.args.get("sort", "price_asc")
            # bot5 2026-08-10 - filtr podle prurezu/drazky profilu (viz
            # _category_products_with_images/_category_product_facets).
            # Repeatable query param: ?cross_section=20x20&cross_section=30x30
            cross_sections = [v for v in request.args.getlist("cross_section") if v]
            groove_families = [v for v in request.args.getlist("groove") if v]
            products = _category_products_with_images(
                cur, cat_id, sort=sort,
                cross_sections=cross_sections or None,
                groove_families=groove_families or None,
            )
            # bot16, 2026-09-24 (Robert pres bot3, pravidlo 52 - "jako admin
            # chci videt na eshopu u kazde polozky z Dogus aktualni posledni
            # cenu USD Dogus krat aktualni FIO devize prodej kurz v CZK"):
            # admin-only naklad, doplneno AZ TADY (ne v _category_products_
            # with_images vyse - viz komentar u importu _can_view_dogus_
            # admin_cost) a jen kdyz je vubec koho doplnovat (fail-closed
            # default = nedelat navic dotaz, kdyz neni potreba).
            if products and _can_view_dogus_admin_cost():
                product_ids = [p["id"] for p in products]
                placeholders = ",".join(["%s"] * len(product_ids))
                cur.execute(
                    f"SELECT id, dogus_url, dogus_list_price_usd FROM shop_products "
                    f"WHERE id IN ({placeholders}) AND dogus_url IS NOT NULL",
                    product_ids,
                )
                dogus_by_id = {r["id"]: r for r in cur.fetchall()}
                for p in products:
                    info = dogus_by_id.get(p["id"])
                    if info:
                        p["dogus_url"] = info["dogus_url"]
                        p["dogus_list_price_usd"] = (
                            float(info["dogus_list_price_usd"]) if info["dogus_list_price_usd"] is not None else None
                        )
            facets = _category_product_facets(cur, cat_id)
            # bot5 2026-08-10 (Robert: "spojovací kostky by nemeli mít tolik
            # příslušenství, podle by se nemelo zobrazit nic") - "Vhodné
            # příslušenství" ma smysl JEN u kategorii profilu ("tohle je
            # profil, ukaz mi co se na nej hodi") - kdyz je kategorie sama
            # prislusenstvim (Spojovaci kostky/Uhelniky/Uhlove spojky...),
            # nemel by se ukazovat vubec, ne jen zuzeny filtrem - jinak jde
            # o "prislusenstvi ke svym souzenim prislusenstvi", ne uzitecnou
            # napovedu k profilu, ktery zakaznik prochazi.
            cur.execute(
                "SELECT 1 FROM shop_products WHERE category_id=%s AND active=1 AND is_archived=0 "
                "AND is_profile_material=1 LIMIT 1",
                (cat_id,),
            )
            category_has_profiles = cur.fetchone() is not None
            if category_has_profiles:
                # Robert: "pokud označim filtr 40x40, nemuze v kategorii
                # zustat viditelná zádná polozka vetsi než 40x40" - "Vhodné
                # příslušenství" je SEZNAM POLOZEK, ne filtr ovladac - kdyz
                # je aktivni vyber prurezu/drazky, musi ho respektovat
                # stejne jako hlavni mrizka produktu (facets SAMOTNE se
                # nezuzuji, ale VYPIS ano). Bez aktivniho filtru se chova
                # jako drive - cely rozsah kategorie.
                compatible_accessories = _compatible_accessories(
                    cur,
                    groove_families=groove_families or [f["value"] for f in facets["groove_families"]],
                    cross_sections=cross_sections or [f["value"] for f in facets["cross_sections"]],
                )
                # bot5 2026-08-10 (Robert: "ilustracni nahledy pouziti
                # nasich prvku v praxi" -> i na kategorii profilu) -
                # odvozeno ze stejne kompatibility jako Vhodne prislusenstvi
                # vyse (vsechny obrazky pouziti vsech kompatibilnich kusu).
                usage_images = _usage_images_for_products(cur, [a["id"] for a in compatible_accessories])
            else:
                compatible_accessories = []
                usage_images = []

            # Fotogalerie kategorie (Robert, "kde se ma zobrazovat" - na
            # verejne strance kategorie, hned za hornim popisem, pred
            # produkty - viz category.html).
            # bot10, 2026-09-12: prepnuto na centralni content_photo_library
            # (Robert: "centralni fotogalerie na jednom miste v adminu",
            # nahrazuje puvodni content_gallery_items - jeden zdroj pravdy
            # misto tri nezavislych mechanismu, ktere zpusobily dnesni
            # is_public diru).
            #
            # ZAMERNE jen legacy_source='content_gallery_items' - fotky
            # vlozene primo do textu popisu (legacy_source='kategorie_popisy')
            # uz jsou videt INLINE v `body_html` (viz nize), pridat je i sem
            # by je na strance zdvojilo. Sjednoceni obou zdroju do jedne
            # galerie je samostatne, vedome rozhodnuti, ne vedlejsi efekt
            # migrace.
            cur.execute("""
                SELECT p.file_path, p.caption FROM content_photo_library p
                JOIN content_photo_library_categories c ON c.photo_id = p.id
                WHERE c.category_id=%s AND p.is_public=1 AND p.legacy_source='content_gallery_items'
                ORDER BY c.sort_order, p.id
            """, (cat_id,))
            gallery = [
                {"url": f"/{r['file_path']}", "caption": r["caption"]}
                for r in cur.fetchall()
            ]
    finally:
        conn.close()
    for f in files:
        if f.get("uploaded_at"):
            f["uploaded_at"] = f["uploaded_at"].isoformat()
    # bot4, 2026-07-26 (Robert: "zrušme na eshopu diskuze u produktů a
    # kategorií") - diskuze/komentare u kategorii ZRUSENY (viz drive
    # POST /api/categories/<id>/comments, smazano nize). Klic "comments"
    # zustava v odpovedi (prazdny seznam) kvuli zpetne kompatibilite,
    # kdyby na nej jeste nekde neco odkazovalo - data v `content_comments`
    # NEJSOU smazana (zadny DROP TABLE), jen se uz nenacitaji/nezobrazuji.
    return jsonify({"category": cat, "page": page, "files": files, "comments": [], "products": products, "gallery": gallery, "facets": facets, "compatible_accessories": compatible_accessories, "usage_images": usage_images})

@app.put("/api/categories/<int:cat_id>/content")
@require_permission("kategorie", "upravit")
def category_content_update(cat_id):
    body = request.get_json(silent=True) or {}
    title = body.get("title")
    intro_html = body.get("intro_html")
    body_html = body.get("body_html")
    bottom_body_html = body.get("bottom_body_html")
    video_url = body.get("video_url")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM content_pages WHERE category_id=%s", (cat_id,))
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE content_pages SET title=%s, intro_html=%s, body_html=%s, bottom_body_html=%s, video_url=%s WHERE category_id=%s",
                    (title, intro_html, body_html, bottom_body_html, video_url, cat_id),
                )
            else:
                cur.execute(
                    "INSERT INTO content_pages (category_id, title, intro_html, body_html, bottom_body_html, video_url) VALUES (%s,%s,%s,%s,%s,%s)",
                    (cat_id, title, intro_html, body_html, bottom_body_html, video_url),
                )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

def _strip_html(html_text):
    if not html_text:
        return ""
    return re.sub(r"<[^>]+>", " ", html_text)

def _search_snippet(text, q, radius=70):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    idx = text.lower().find(q.lower())
    if idx == -1:
        return text[:radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(q) + radius)
    snippet = text[start:end].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")

@app.get("/api/categories/search")
def categories_search():
    # VEREJNE - Robert 2026-08-08: "pridej na eshop hledaci okno, se
    # zatrzitky kde se ma hledat - produkty, text kategorii". Hleda
    # v nazvu kategorie a v textu jejiho obsahu (content_pages.body_html/
    # bottom_body_html - hruby LIKE i pres HTML znacky, snippet se pak
    # ocisti pres _strip_html pro zobrazeni ve vysledcich). Jen viditelne
    # kategorie (is_visible=1), stejne jako verejny strom v /api/categories.
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"categories": []})
    like = f"%{q}%"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.name, c.slug, p.intro_html, p.body_html, p.bottom_body_html
                FROM content_categories c
                LEFT JOIN content_pages p ON p.category_id = c.id
                WHERE c.is_visible=1
                  AND (c.name LIKE %s OR p.intro_html LIKE %s OR p.body_html LIKE %s OR p.bottom_body_html LIKE %s)
                ORDER BY c.name
                LIMIT 20
            """, (like, like, like, like))
            rows = cur.fetchall()
    finally:
        conn.close()
    results = []
    for r in rows:
        combined_text = _strip_html(r.get("intro_html")) + " " + _strip_html(r.get("body_html")) + " " + _strip_html(r.get("bottom_body_html"))
        results.append({
            "id": r["id"], "name": r["name"], "slug": r["slug"],
            "snippet": _search_snippet(combined_text, q),
        })
    return jsonify({"categories": results})

@app.post("/api/categories/<int:cat_id>/files")
@require_permission("kategorie", "upravit")
def category_content_upload(cat_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    safe_name = secure_filename(f.filename)
    stored_name = f"{cat_id}_{os.urandom(6).hex()}_{safe_name}"
    f.save(os.path.join(UPLOAD_DIR, stored_name))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO content_files (category_id, filename, stored_name) VALUES (%s,%s,%s)",
                (cat_id, safe_name, stored_name),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok", "id": new_id, "filename": safe_name, "stored_name": stored_name})

@app.delete("/api/categories/files/<int:file_id>")
@require_permission("kategorie", "smazat")
def category_content_delete_file(file_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stored_name FROM content_files WHERE id=%s", (file_id,))
            row = cur.fetchone()
            if row:
                try:
                    os.remove(os.path.join(UPLOAD_DIR, row["stored_name"]))
                except OSError:
                    pass
            cur.execute("DELETE FROM content_files WHERE id=%s", (file_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"status": "ok"})

