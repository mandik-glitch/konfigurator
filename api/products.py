"""
Produkty e-shopu + skladove pohyby - bot3, 2026-08-08 (vytazeno z app.py).

Kontext: api/app.py naroste s kazdou funkci a je nejcasteji soubezne
editovanym souborem napric vsemi boty (viz AGENTS_LOG diskuze o
kolizich sdileneho working directory) - tahle sekce (produkty, jejich
CSV import/export, prirezy profilu, skladove pohyby/prijemky/vydejky)
byla dnes nejrusnejsi (Toptrans rozmery, "Hover okno produktu", zalozky
skladove karty se vsechno sesly tady). Vytazeno do vlastniho modulu
stejnym zpusobem jako uz drive cart.py/orders.py/gallery_items.py atd. -
zadna zmena chovani, jen presun. Endpointy i URL adresy zustavaji stejne
(Flask nerozlisuje, ve kterem souboru je route registrovana).

Aktivace: na konec app.py pridat AZ PO `import gallery_items` (produkty
mazou sve fotky pres gallery_items.delete_items_for_owner*, potrebuji
uz nactenej modul v sys.modules):

    import products  # noqa: F401 - registruje /api/shop/products + /api/shop/stock/*

api/cart.py a api/orders.py importuji nekolik helperu odsud primo
(_validate_cut_pieces, _rods_needed_for_cuts, _cut_service_price_czk,
_waste_breakdown) - viz jejich vlastni "from products import ..." radky.
"""
import csv
import io
import json
import os
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pymysql
import cutting_algo  # cisty vypocetni modul (zadne Flask/DB zavislosti) - pack_1d pro dopocet poctu tyci u prirezu
import gallery_items  # uklid fotek pri mazani produktu/skladoveho pohybu
import product_duplicate  # duplikace karty produktu (cisty modul, zadna Flask zavislost)
import product_slug  # adresy produktu - jediny mechanismus (tvorba, prejmenovani, 301 ze stare)

from flask import jsonify, request, Response
from werkzeug.utils import secure_filename

from app import (
    app, get_conn, current_user, require_permission, parse_bulk_ids, log_audit,
    get_pagination_args, paginated_query, PROFILE_MAX_LENGTH_MM,
    resolve_category_path, build_category_path_fn, UPLOAD_DIR,
    _compatible_accessories, _usage_images_for_products, _product_slug_for_name,
    PERMISSION_ROLES, get_setting, verejny_popisek_galerie, has_permission,
)

# Robert PRIMO (pres bot3, 2026-09-26, AGENTS_LOG.md 6511c930) - presne
# SKU "hlavniho profilu" pro rez/schema v galerii detailu (viz
# shop_products_get nize), pro nominalni rozmery, kde odvozeni pres
# cfg_dily.visible_in_scene=1 nedava jednoznacnou odpoved (30x30 ma dve
# stejne "viditelne ve scene" polozky). Klic = nominalni rozmer (mm),
# hodnota = presne to SKU, ktere Robert oznacil za "ten hlavni". NEODVOZOVAT
# jinak pro tyto 3 rozmery, ani kdyz by cfg_dily naznacovalo neco jineho.
PROFIL_SCHEMA_CANONICAL_SKU = {
    30: "1.1.08.030030.03",
    40: "1.1.10.040040.03",
    45: "1.1.10.045045.03",
}

# Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): tahle pole nemaji
# zadne verejne pouziti (overeno grepem webapp/*.html + webapp/js/*.js -
# jen admin.html) a jsou interni (dodavatel, skladove limity, zdroj
# cen, dealerska sleva) - staff (PERMISSION_ROLES) je dostane beze
# zmeny, nepřihlášený/role='user' návštěvník ne. `stock_qty`,
# `supplier_name` a `product_specs_json` ZAMERNE NEVYRAZENO - jsou
# soucasti existujici verejne zobrazovane specifikace produktu
# (product.html renderMetaTable/scene.html/category.html), rozhodnuti
# Robert/bot3.
_PRODUCT_STAFF_ONLY_FIELDS = (
    "supplier_id", "min_stock", "max_stock", "price_source_url", "dealer_discount_percent",
)


def _verejne_specs(val):
    """product_specs_json (retezec JSON / dict / None) -> dict verejne specifikace pro seznam (?include=specs): bez dlouheho textu "Kusovník"; neplatna hodnota = prazdny dict."""
    if isinstance(val, str):
        try:
            val = json.loads(val)
        except (TypeError, ValueError):
            return {}
    if not isinstance(val, dict):
        return {}
    return {k: v for k, v in val.items() if k != "Kusovník"}


def _is_staff_request():
    user = current_user()
    return bool(user and user["role"] in PERMISSION_ROLES)


def _strip_staff_only_fields(rows_or_row):
    # Stejny bug jako u _apply_dogus_admin_cost_gate() nize (bot3,
    # 2026-09-30) - "isinstance(rows_or_row, list)" je spatne, protoze
    # pymysql cur.fetchall() vraci tuple, ne list. Tady zatim "spi", protoze
    # jediny volajici (shop_products_list) tenhle branch spousti jen pro
    # not is_staff a v praxi ho vola vzdy jen staff admin.html - kdyby se
    # nekdy zavolalo pro verejny/neprihlaseny pozadavek s >=1 radkem, spadlo
    # by to identicky. Test musi rozlisovat "jeden radek" (dict) od
    # "kolekce radku" (list/tuple), ne naopak.
    rows = [rows_or_row] if isinstance(rows_or_row, dict) else rows_or_row
    for r in rows:
        for f in _PRODUCT_STAFF_ONLY_FIELDS:
            r.pop(f, None)


# Robert pres bot3, 2026-09-24 (WORKFLOW.md pravidlo 52, rozsireni zadani
# "FIO zivy kurz v Ceny profilu" i na eshop storefront): "jako admin chci
# videt na eshopu u kazde polozky z Dogus, aktualni posledni cenu USD
# Dogus krat aktualni FIO devize prodej kurz tzn v CZK" - primo odvoditelna
# dodavatelska marze, proto UZSI gate nez ostatni _PRODUCT_STAFF_ONLY_FIELDS
# (ty pousti libovolnou PERMISSION_ROLES roli). `dogus_url`/
# `dogus_list_price_usd` smi videt jen role se stejnym opravnenim jako
# zivy kurz v adminu (api/admin_profily.py::admin_profily_fio_rate,
# "ceny_profilu"/"zobrazit" - bot16, 2026-09-29: prejmenovano z
# "ceny_prislusenstvi" pri granularnim deleni, viz AGENTS_LOG.md) -
# JEDNO misto pravdy pro "kdo smi videt marzi", stejne jako fio_rate.py
# je jedno misto pravdy pro definici kurzu.
_DOGUS_ADMIN_COST_FIELDS = ("dogus_url", "dogus_list_price_usd")


def _can_view_dogus_admin_cost():
    # `user["active"]` navic oproti _is_staff_request() vyse (ta ho
    # nekontroluje) - primo odvoditelna marze si zaslouzi aspon stejne
    # prisny fail-closed test jako require_permission()/login_required()
    # dekoratory (deaktivovany ucet se starou session cookie tak fields
    # nedostane, i kdyz by mu has_permission() jinak rekl "admin, vzdy True").
    user = current_user()
    return bool(user and user["active"] and has_permission(user, "ceny_profilu", "zobrazit"))


def _apply_dogus_admin_cost_gate(rows_or_row):
    """Zavola se VZDY po SELECTu, ktery obsahuje dogus_url/dogus_list_price_usd
    (shop_products_list/shop_products_get) - kdyz aktualni pozadavek nema
    opravneni (vc. zcela neprihlaseneho navstevnika), pole se ze zaznamu
    ÚPLNĚ ODSTRANÍ (ne jen nastavi na null), aby v JSON odpovedi vubec
    nebyla pritomna - server-side vynuceni, zadne spolehnuti na to, ze
    frontend hodnotu jen schova."""
    # Bug (bot3, 2026-09-30): puvodni "isinstance(rows_or_row, list)" bylo
    # spatne - pymysql cur.fetchall() (viz paginated_query) vraci TUPLE, ne
    # list, takze cely radkovy vypis (shop_products_list) skoncil obalenim
    # CELEHO tuple do [tuple] a pri iteraci pad "'tuple' object has no
    # attribute 'get'/'pop'" pri KAZDEM volani (i s 0 vysledky) - zive od
    # 2026-09-25 12:36 (den po nasazeni teto funkce), 18x v logu za 6 dni,
    # nikym nenahlaseno (admin Produkty tab se zjevne otviral zridka).
    # Nahlaseno Robertem 2026-09-30 jako "Nepodarilo se nacist produkty" pri
    # hledani "elekt" - text hledani s tim nemel nic spolecneho, spadlo by
    # to na cemkoli. Test musi rozlisovat "jeden radek" (dict) od "kolekce
    # radku" (list/tuple), ne naopak.
    rows = [rows_or_row] if isinstance(rows_or_row, dict) else rows_or_row
    if _can_view_dogus_admin_cost():
        for r in rows:
            if r.get("dogus_list_price_usd") is not None:
                r["dogus_list_price_usd"] = float(r["dogus_list_price_usd"])
    else:
        for r in rows:
            for f in _DOGUS_ADMIN_COST_FIELDS:
                r.pop(f, None)

# Souvisejici dokumenty (PDF/video) - Robert 2026-08-08: "souvisejici
# dokumenty napr pdf a videa". Vlastni slozka mimo gallery-items (viz
# products.py docstring nahore - proc NEsdilet content_gallery_items).
PRODUCT_DOCS_DIR = os.path.join(UPLOAD_DIR, "product-documents")
os.makedirs(PRODUCT_DOCS_DIR, exist_ok=True)
PRODUCT_DOC_EXT = {"pdf": {"pdf"}, "video": {"mp4", "webm", "mov"}}

# Robert 2026-08-11 ("skupinovani pro souvisejici produkty stylem jako
# ty zavity, udelej vsechno prislusenstvi a spojky") - normalizace
# nazvu produktu pro skupiny "stejny prvek, jiny parametr": zavit
# (M6, M8x20), rozmer (30x30, 45 x 90) a drazka/system (drazka 8,
# Channel 10, system 45, S10) se nahradi zastupnym znakem; produkty se
# shodnym zbytkem nazvu tvori skupinu. Regexy 1:1 overene na zivem
# katalogu (viz commit message) - nemenit bez opakovani te analyzy.
_NAME_THREAD_RE = re.compile(r"(?<![A-Za-z0-9])M(\d{1,2})(x\d{1,3})?(?!\d)")
_NAME_DIM_RE = re.compile(r"(?<!\d)(\d{2,3})\s*[xX]\s*(\d{2,3})(?!\d)")
_NAME_GROOVE_RE = re.compile(r"(dr[áa][žz]ka|channel|syst[ée]m(?:u)?|S)\s*(\d{1,2})(?!\d)", re.I)

# Vetve stromu kategorii, kde se jmenne skupiny uplatnuji: 150 =
# Prislusenstvi profilu, 152 = Spojovaci prvky (obe pod Hlinikove
# stavebnicove profily). U profilu samotnych by slucovani pres rozmer
# spojilo nesouvisejici prurezy, proto zamerne jen tyto 2 vetve.
_ACCESSORY_BRANCH_PRODUCTS_SQL = """
    WITH RECURSIVE branch AS (
        SELECT id FROM content_categories WHERE id IN (150, 152)
        UNION ALL
        SELECT c.id FROM content_categories c JOIN branch b ON c.parent_id = b.id
    )
    SELECT p.sku, p.name FROM shop_products p
    WHERE p.active=1 AND p.is_archived=0
      AND p.category_id IN (SELECT id FROM branch)
    ORDER BY p.sku
"""


def _normalized_name_group_key(name):
    if not name:
        return None
    n = name
    hit = False
    if _NAME_THREAD_RE.search(n):
        n = _NAME_THREAD_RE.sub("M#", n)
        hit = True
    if _NAME_DIM_RE.search(n):
        n = _NAME_DIM_RE.sub("#x#", n)
        hit = True
    if _NAME_GROOVE_RE.search(n):
        n = _NAME_GROOVE_RE.sub(lambda m: m.group(1) + " #", n)
        hit = True
    if not hit:
        # zadny parametr v nazvu = zadna skupina (kazde slovo navic by
        # jinak tvorilo falesnou "skupinu" identickych nazvu)
        return None
    return re.sub(r"\s+", " ", n).strip().lower()


# --- Skladovy system - produkty eshopu (kategorie jsou SJEDNOCENE se
# stromem vyse - viz content_categories / /api/categories) ---
# Robert 2026-07-25: "udelej backend skladovy system s produkty a
# kategoriemi, produkty klidne pouzij stejne co tam jsou, potom je smazeme
# a budeme zde mit vlastni produkty" -> pak "chci sjednotit kategorie,
# oddelit sklad polozek, a zobrazit vse navenek" -> "jeden strom, produkty
# i obsah spolu". Puvodni samostatna tabulka shop_categories byla
# zrusena a jeji obsah (123 kategorii) premigrovan do content_categories
# (viz AGENTS_LOG.md) - produkty (shop_products.category_id) ted odkazuji
# primo tam. Puvodni seed data (293 produktu prevzatych ze struktury
# skladapp jako docasny placeholder, priznak is_placeholder) byla po
# naimportovani realneho Shoptet katalogu smazana - sloupec is_placeholder
# uz nemel zadny radek na 1 a byl proto odstranen cely (bot5, 2026-07-27,
# viz sql/2026-07-27_drop_placeholder_column.sql).
@app.get("/api/shop/products")
def shop_products_list():
    # VEREJNE - pro zobrazeni v eshopu. ?category_id= filtruje na jednu
    # kategorii (bez potomku - frontend si pripadne dotahne potomky ze
    # stromu a zavola vicekrat). ?q= hleda v nazvu, ?sku= samostatne v
    # SKU (Robert: "pridej filtr na SKU" - admin Produkty). Archivovane polozky
    # (Robert 2026-07-25: "rozšířená evidence položek... archivace
    # položek místo mazání") jsou defaultne skryte i z admin vypisu (?all=1)
    # - musi se explicitne pozadat ?archived=1, aby se zobrazily/filtrovaly
    # jen ony. ?low_stock=1 vrati jen polozky pod nastavenym minimem.
    # ?category_id=none je sentinel pro "bez kategorie" (Robert: "pridej
    # do produktu filtraci: bez kategorie") - cist jako raw string PRED
    # type=int pokusem, jinak by "none" tise spadlo na None/ignorovano.
    category_id_raw = request.args.get("category_id")
    category_id_none = category_id_raw == "none"
    category_id = request.args.get("category_id", type=int) if not category_id_none else None
    supplier_id = request.args.get("supplier_id", type=int)
    q = (request.args.get("q") or "").strip()
    sku_q = (request.args.get("sku") or "").strip()
    is_staff = _is_staff_request()
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): "all=1" (vc.
    # neaktivnich/archivovanych polozek) je urceno jen pro staff nastroje
    # (admin.html, capture.html - overeno grepem, zadna verejna stranka
    # ho nevola) - u nestaff pozadavku se tise ignoruje (padne na
    # bezpecny vychozi active-only vypis), misto chyby.
    only_active = True if not is_staff else request.args.get("all") != "1"
    show_archived = request.args.get("archived") == "1"
    low_stock_only = request.args.get("low_stock") == "1"
    # Robert 2026-08-08 ("novou produktovou sestavu nevidím v produktech"):
    # nove sestavy ze sceny (viz product_assemblies_create) se zakladaji jako
    # neaktivni navrh (active=0), ale seznam je defaultne razeny abecedne
    # (name) - u stovek existujicich produktu se navrh snadno "ztrati"
    # nekde uprostred abecedy. active_only/inactive_only (admin #shopProdActiveFilter)
    # jsou nezavisle na "all" (verejny eshop je nikdy neposila) - inactive_only
    # navic prehazuje razeni na nejnovejsi-prvni, aby prave ulozeny navrh byl
    # rovnou nahore.
    active_only_flag = request.args.get("active_only") == "1"
    inactive_only_flag = request.args.get("inactive_only") == "1"
    # Robert 2026-08-11 ("zatrzitko ktere vyfiltruje vsechny polozky
    # ktere jsou ve scene") - filtr admin tabulky produktu na produkty
    # s visible_in_scene=1 (= viditelne v katalogu 3D sceny).
    in_scene_only = request.args.get("in_scene") == "1"
    # bot5, 2026-10-07 (Robert pres bot9: "stitky pro rychle filtrovani podle delky / tabulka s cenami, ne desitky stejnych obrazku"): ?include=specs prida k radkum `specs` - verejnou
    # specifikaci produktu (product_specs_json, stejna data jako verejny detail; bez textu "Kusovník", ten je dlouhy a patri jen na detail). Tabulka/filtry kategorie tak nehadaji
    # parametry z nazvu a nevolaji detail pro kazdy radek. Bez parametru se odpoved nemeni.
    include_specs = "specs" in (request.args.get("include") or "").split(",")
    # Stránkování (task #78/79) - opt-in přes ?page_size=, veřejný eshop
    # (bez page_size) dostane pořád vše jako dřív.
    page, page_size = get_pagination_args()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where, params = [], []
            if inactive_only_flag:
                where.append("active=0")
            elif active_only_flag or only_active:
                where.append("active=1")
            if show_archived:
                where.append("is_archived=1")
            else:
                where.append("is_archived=0")
            if category_id_none:
                where.append("category_id IS NULL")
            elif category_id is not None:
                where.append("category_id=%s")
                params.append(category_id)
            if supplier_id is not None:
                where.append("supplier_id=%s")
                params.append(supplier_id)
            if q:
                # Robert 2026-08-08 ("proč to nenašel?" - hledal SKU kód v
                # obecnem vyhledavacim okne na eshopu) - ?q= drive hledalo
                # jen v nazvu, SKU melo vlastni oddeleny ?sku= parametr
                # (pouzivany admin filtrem sloupce). Obecne vyhledavani
                # (eshop hledaci okno, viz index/category/product.html)
                # ocekava, ze uzivatel muze zadat klidne i kod produktu -
                # ?q= ted hleda v OBOJIM.
                where.append("(name LIKE %s OR sku LIKE %s)")
                params.append(f"%{q}%")
                params.append(f"%{q}%")
            if sku_q:
                where.append("sku LIKE %s")
                params.append(f"%{sku_q}%")
            if low_stock_only:
                where.append("min_stock IS NOT NULL AND stock_qty < min_stock")
            if in_scene_only:
                where.append("visible_in_scene=1")
            base_sql = ("SELECT id, category_id, sku, name, slug, description, unit, price_czk_placeholder, weight_g, "
                        "cfg_dily_id, is_board_material, is_profile_material, "
                        "stock_qty, min_stock, max_stock, active, is_archived, "
                        # bot2, 2026-07-28: FBX/GLB stav pro tlacitko "Nahrat FBX" v adminu
                        "fbx_original_name, fbx_uploaded_at, glb_file, visible_in_scene, "
                        # bot2, 2026-07-28: zdroj pro tydenni auto-refresh ceny
                        "price_source_url, price_last_refreshed_at, "
                        # bot6, 2026-08-01: vazba na dodavatele pro nabizeni v nakupni objednavce
                        "supplier_id, supplier_name, "
                        # bot4, 2026-08-08 (Robert: "pridej k vyhledavani obrazky pokud existuji")
                        # - nahledovy obrazek, stejny vzor jako cart.py/_category_products_with_images.
                        "(SELECT filename FROM shop_product_images WHERE product_id=shop_products.id "
                        "ORDER BY sort_order, id LIMIT 1) AS image_filename, "
                        # bot16, 2026-09-24 (Robert pres bot3, pravidlo 52) - admin-only
                        # dodavatelsky naklad, viz _apply_dogus_admin_cost_gate() nize.
                        "dogus_url, dogus_list_price_usd"
                        + (", product_specs_json " if include_specs else " ")
                        + "FROM shop_products")
            where_sql = (" WHERE " + " AND ".join(where)) if where else ""
            order_sql = " ORDER BY created_at DESC" if inactive_only_flag else " ORDER BY name"
            rows, total = paginated_query(cur, base_sql, where_sql, params, order_sql, page, page_size)
    finally:
        conn.close()
    for r in rows:
        if r.get("price_czk_placeholder") is not None:
            r["price_czk_placeholder"] = float(r["price_czk_placeholder"])
        if r.get("fbx_uploaded_at") is not None:
            r["fbx_uploaded_at"] = r["fbx_uploaded_at"].isoformat()
        if r.get("price_last_refreshed_at") is not None:
            r["price_last_refreshed_at"] = r["price_last_refreshed_at"].isoformat()
        image_filename = r.pop("image_filename", None)
        r["image_url"] = f"/content-files/gallery/{image_filename}" if image_filename else None
        if include_specs:
            r["specs"] = _verejne_specs(r.pop("product_specs_json", None))
    if not is_staff:
        _strip_staff_only_fields(rows)
    _apply_dogus_admin_cost_gate(rows)
    resp = {"products": rows}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.get("/api/shop/products/<int:product_id>")
def shop_products_get(product_id):
    # VEREJNE (jako /api/categories/<id>/content) - napaje verejnou
    # stranku detailu produktu (webapp/product.html, Robert: "ty a hned").
    # Nikde v adminu se nevolala jen GET varianta (jen PUT), rozsireno
    # proto bez rizika kolize s existujicim admin UI.
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, category_id, sku, name, slug, description, short_description, unit, "
                "price_czk_placeholder, weight_g, cfg_dily_id, stock_qty, min_stock, max_stock, active, is_archived, "
                "manufacturer, supplier_name, warranty, ean, availability_text, "
                "category_path, alternative_product_codes, related_product_codes, has_variants, variant_count, "
                # bot7, 2026-08-07: glb_file/visible_in_scene rikaji adminu,
                # jestli je smysluplne nabidnout editaci "Barva ve 3D scene"
                # (color_hex) - viz sql/2026-08-07_product_scene_color.sql.
                "glb_file, visible_in_scene, color_hex, is_board_material, is_profile_material, "
                "cross_section_label, groove_family, "
                "fbx_original_name, place_vertical, "
                "board_sheet_width_mm, board_sheet_height_mm, "
                "length_mm, width_mm, height_mm, meta_title, meta_description, "
                "dealer_discount_percent, sale_price_czk, sale_price_from, sale_price_until, "
                "product_specs_json, "
                # bot16, 2026-09-24 (Robert pres bot3, pravidlo 52) - admin-only
                # dodavatelsky naklad, viz _apply_dogus_admin_cost_gate() nize.
                "dogus_url, dogus_list_price_usd, "
                # bot7 2026-09-25 (Robert pres bot3, pravidlo 52 - graficke
                # stitky profil+umisteni) - umisteni_id primo na shop_products
                # (Vandr karty, bot10), vandr_hlavni_prurez_mm stejne (bot10,
                # zavadi se prave ted). U nativnich sestav se oboji bere z
                # product_assemblies nize (assembly_row).
                "umisteni_id, vandr_hlavni_prurez_mm "
                "FROM shop_products WHERE id=%s",
                (product_id,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Produkt neexistuje."}), 404
            is_staff = _is_staff_request()
            # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, zive overeno):
            # zadny active/is_archived filtr tu drive nebyl - kazdy anonym
            # videl i neaktivni/archivovany produkt (soft-404, navic vc.
            # interni pole nize). Staff (napr. nahled pred aktivaci) dal
            # vidi vse beze zmeny.
            if not is_staff and (not row["active"] or row["is_archived"]):
                return jsonify({"error": "Produkt neexistuje."}), 404

            # bot14, 2026-09-02 (Robert pres bot3: "zakreslovani pouze u
            # produktovych sestav") - "Zakreslena pripominka" na product.html
            # se ma nabizet JEN u produktu, ktery je ve skutecnosti export
            # konkretni sestavy (product_assemblies.shop_product_id), ne u
            # beznych katalogovych dilu (uhelnik, sroub...). Prvni/jedina
            # navazana sestava (1:1 vztah v praxi - shop_product_id je u
            # sestavy nepovinne, ale kdyz je nastavene, je to export prave
            # TOHOTO produktu).
            cur.execute(
                "SELECT id, umisteni_id, profil_mm FROM product_assemblies WHERE shop_product_id=%s LIMIT 1",
                (product_id,),
            )
            assembly_row = cur.fetchone()
            row["assembly_id"] = assembly_row["id"] if assembly_row else None
            # bot7 2026-09-25 (Robert pres bot3, pravidlo 52 - graficke
            # stitky profil+umisteni na karte i v detailu) - primy sloupec
            # na shop_products (Vandr) ma prednost, jinak fallback na
            # product_assemblies (nase sestavy). Kod/nazev umisteni az
            # dole, jednim spolecnym dotazem na regal_umisteni (viz nize).
            umisteni_id = row.get("umisteni_id")
            if umisteni_id is None and assembly_row:
                umisteni_id = assembly_row.get("umisteni_id")
            profil_mm = row.get("vandr_hlavni_prurez_mm")
            if profil_mm is None and assembly_row:
                profil_mm = assembly_row.get("profil_mm")
            row.pop("umisteni_id", None)
            row.pop("vandr_hlavni_prurez_mm", None)
            row["profil_mm"] = profil_mm
            # Robert pres bot3, 2026-09-26 ("v galerii ať se objeví zaroveň
            # řez/schema hlavního profilu") - "hlavni profil" tu je jen
            # NOMINALNI rozmer (cislo, viz profil_mm vyse), ne konkretni
            # katalogove ID - vice profilovych SKU muze sdilet stejny
            # nominalni prurez (api/admin_profily.py: "nekolik ID sdili
            # stejny nominalni prurez, napr. Object_7/8/9 = 30x30").
            #
            # OPRAVA (Robert pres bot3, tyz den): puvodni "prvni podle sku"
            # bylo VECNE SPATNE - u 40x40 existuje 9 SKU s groove_family=8
            # (sku "1.1.08...") a 6 SKU s groove_family=10 (sku "1.1.10..."),
            # razeni podle sku vzdy vyhralo "08" pred "10" retezcove/cisel,
            # ale REALNY profil pouzivany ve vestavbach ma drazku 10 - ukazal
            # se tak zakaznikovi technicky spatny narys (8mm misto 10mm) na
            # VSECH Vandr kartach s profil_mm 40/45 (82 produktu). Skutecny
            # "hlavni profil" neurcuje poradi SKU, ale cfg_dily.visible_in_
            # scene=1 (katalog 3D sceny - TOHLE je profil, ktery se doopravdy
            # staví do sestav, propojeni cfg_dily.id = shop_products.
            # cfg_dily_id). Fallback na puvodni sku-razeni zustava JEN pro
            # rozmer, ktery v cfg_dily vubec nema scenicky profil (dosud
            # zadny takovy rozmer nenalezen mezi profil_mm v aktivnim pouziti,
            # ale ne kazdy mozny rozmer katalogu ma nutne scenicky protejsek).
            #
            # ZNAMA NEJEDNOZNACNOST: 30x30 ma DVE cfg_dily.visible_in_scene=1
            # polozky soucasne (Object_7 a profil_30x30_uzavreny, obe groove_
            # family=8 - tedy spravna drazka v obou pripadech, jen dva mozne
            # konkretni tvary profilu) - cfg_dily samo o sobe tu neda
            # jednoznacnou odpoved. Robert PRIMO nadiktoval presne SKU pro
            # tento a dalsi 2 rozmery (bot3, AGENTS_LOG.md 6511c930) - u
            # 40x40/45x45 se kryje s tim, co by cfg_dily samo vybralo
            # (jedina visible_in_scene=1 polozka), u 30x30 je to Robertovo
            # zavazne rozhodnuti mezi dvema moznostmi. PROFIL_SCHEMA_
            # CANONICAL_SKU je proto zdroj pravdy PRED cfg_dily odvozenim,
            # ne naopak - pro tyto 3 rozmery se cfg_dily logika vubec
            # nepouzije. Pro VSECHNY OSTATNI rozmery (20x20/20x40/20x80/
            # 30x60/35x35/40x80 a cokoli dalsiho v budoucnu) plati cfg_dily.
            # visible_in_scene=1 odvozeni beze zmeny.
            row["profil_schema_url"] = None
            if profil_mm is not None:
                canonical_sku = PROFIL_SCHEMA_CANONICAL_SKU.get(profil_mm)
                schema_row = None
                if canonical_sku:
                    cur.execute(
                        "SELECT dogus_image_schema_url FROM shop_products "
                        "WHERE sku=%s AND dogus_image_schema_url IS NOT NULL",
                        (canonical_sku,),
                    )
                    schema_row = cur.fetchone()
                if not schema_row:
                    cur.execute(
                        "SELECT sp.dogus_image_schema_url FROM shop_products sp "
                        "JOIN cfg_dily cd ON cd.id = sp.cfg_dily_id "
                        "WHERE sp.is_profile_material=1 AND sp.cross_section_label=%s "
                        "AND cd.visible_in_scene=1 AND sp.dogus_image_schema_url IS NOT NULL "
                        "ORDER BY cd.id ASC LIMIT 1",
                        (f"{profil_mm}x{profil_mm}",),
                    )
                    schema_row = cur.fetchone()
                if not schema_row:
                    cur.execute(
                        "SELECT dogus_image_schema_url FROM shop_products "
                        "WHERE is_profile_material=1 AND cross_section_label=%s "
                        "AND dogus_image_schema_url IS NOT NULL ORDER BY sku ASC LIMIT 1",
                        (f"{profil_mm}x{profil_mm}",),
                    )
                    schema_row = cur.fetchone()
                if schema_row:
                    row["profil_schema_url"] = schema_row["dogus_image_schema_url"]
            row["umisteni_kod"] = None
            row["umisteni_nazev"] = None
            if umisteni_id is not None:
                cur.execute("SELECT kod, nazev FROM regal_umisteni WHERE id=%s", (umisteni_id,))
                umisteni_row = cur.fetchone()
                if umisteni_row:
                    row["umisteni_kod"] = umisteni_row["kod"]
                    row["umisteni_nazev"] = umisteni_row["nazev"]
            # bot5, 2026-09-23 (Robert: "ty 3D modely bez textu to tam nema
            # co delat") - cely sestaveny model (Vandr karta NEBO klasicky
            # sestava-export) nepatri na verejnou "3D model" zalozku
            # produktove stranky VUBEC, pro NIKOHO vcetne staff - jen
            # podepsany odkaz smi ukazat interaktivni model (viz
            # project_ochrana_3d_modelu_sestav). Puvodni sestavy tohle uz
            # splnovaly nahodou (nikdy nemaji glb_file), Vandr karty ho ale
            # MAJI (render pipeline ho cte primo z DB) - tady se to musi
            # hlidat rucne, jinak zalozka + raw netexturovany model naskoci
            # kazdemu navstevnikovi.
            if row["assembly_id"] is not None or (row.get("sku") or "").startswith(("VD-", "STUL-S")):          # STUL-S* = karta stolu z konfigurace (api/stul_karta.py, bot10 2026-10-07): model lezi v katalogu jen pro render, stranka karty ma zivy konfigurator
                row["glb_file"] = None
            # bot5, 2026-09-25 (Robert primo: "chci aby zakreslovaci rezim
            # byl i na vandr sestavach, neni podminkou product_assemblies
            # ani nic jineho" - vyslovne oddeleno od razitek, ta jsou u
            # Vandr v poradku) - puvodni gating "Zakreslena pripominka"
            # (viz komentar u assembly_id vyse) byl navazany na
            # product_assemblies, coz Vandr karty vetsinou nemaji (jen 1
            # z 19 aktivnich ma bot4uv stub kvuli razitkum). Rozsireno o
            # SKU "VD-*" jako druhou, nezavislou podminku - Vandr karta JE
            # skutecny export sestavy, jen bez zaznamu v product_assemblies.
            row["allow_markup"] = bool(row["assembly_id"]) or (row.get("sku") or "").startswith("VD-")
            # Robert 2026-08-08 ("PR10 ma cenu za m2, ne za bezny metr") -
            # cena/hmotnost za bezny metr davaji smysl jen u PROFILU (tyc ma
            # jeden prurez po cele delce). U deskovych materialu (is_board_material)
            # by to ukazalo zavadejici "Kc / 1 m" u produktu, ktery se neprodava
            # na metry - pocita se misto toho cena/hmotnost za m2 primo z
            # tohoto produktu (price_czk_placeholder/weight_g jsou "za
            # celou tabuli", viz board_sheet_width/height_mm a
            # _sheets_needed_for_cuts v cart.py, ktere nakupuji cele
            # tabule).
            if row.get("is_board_material"):
                sheet_m2 = _plocha_tabule_m2(row)
                if sheet_m2:
                    # Cena za tabuli i za m2 se odvozuje pres cena_desky() -
                    # deska muze mit cenu ulozenou v obou jednotkach a delit
                    # ji plochou naslepo by u desky s unit='m2' dalo sestinu
                    # (u MDF 1000 -> 172,53 Kc/m2 misto 1000).
                    za_tabuli, za_m2 = cena_desky(row, row.get("price_czk_placeholder"))
                    if za_m2 is not None:
                        row["unit_price_per_m2_czk"] = za_m2
                    if za_tabuli is not None:
                        row["price_per_sheet_czk"] = round(float(za_tabuli), 2)
                    if row.get("weight_g") is not None:
                        row["unit_weight_per_m2_kg"] = round(float(row["weight_g"]) / 1000.0 / sheet_m2, 3)
            elif row.get("is_profile_material"):
                # Robert 2026-08-09 ("najdi chybejici merne ceny na 1 m u
                # profilu" -> "dej u vsech vypocet pouze z hlavni ceny za
                # 3m") - drive se cena/hmotnost za metr cetla z cfg_dily
                # (jen kdyz mel profil hotovy 3D model), takze 79 ze 101
                # aktivnich profilu (bez cfg_dily_id) mernou cenu vubec
                # neukazovaly. Ted se vzdy pocita primo z price_czk_placeholder/
                # weight_g tohoto produktu (nase jednotka "1 ks = 3000 mm"),
                # nezavisle na existenci 3D modelu - cfg_dily.price_czk_approx
                # uz je stejne jen zrcadlo teze hodnoty (viz shop_products_update()
                # v tomto souboru + scripts/2026-08-09_dogus_price_recompute.py).
                if row.get("price_czk_placeholder") is not None:
                    row["unit_price_per_m_czk"] = round(float(row["price_czk_placeholder"]) / 3.0, 2)
                if row.get("weight_g") is not None:
                    row["unit_weight_per_m_kg"] = round(float(row["weight_g"]) / 1000.0 / 3.0, 3)
            # bot10, 2026-09-12 (stejna dira jako api/categories.py, nalez
            # bot3): chybejici is_public filtr na VEREJNE strance produktu.
            cur.execute("""
                SELECT id, filename, caption FROM content_gallery_items
                WHERE owner_type='product' AND owner_id=%s AND is_public=1 ORDER BY sort_order, id
            """, (product_id,))
            # Popisek se u sestav sklada v turntable.py z PRACOVNIHO nazvu
            # sestavy, takze sem propadalo interni znaceni (kod karoserie,
            # "[10/30mm od kolize]") - viz verejny_popisek_galerie v app.py.
            gallery = [
                {"id": r["id"], "url": f"/content-files/gallery-items/{r['filename']}",
                 "caption": verejny_popisek_galerie(r["caption"])}
                for r in cur.fetchall()
            ]
            if not gallery:
                cur.execute("""
                    SELECT id, filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order, id
                """, (product_id,))
                gallery = [{"id": r["id"], "url": f"/content-files/gallery/{r['filename']}", "caption": None} for r in cur.fetchall()]

            # Robert 2026-08-02: "jako na logiman.cz... vcetne souvisejicich
            # produktu" - related_product_codes je jen seznam SKU (text), tady
            # se dopoji na skutecna data (nazev/cena/obrazek/dostupnost), aby
            # frontend mohl vykreslit skutecne produktove karty, ne holy text.
            related = []
            raw_related = row.get("related_product_codes")
            related_skus = []
            if isinstance(raw_related, str):
                try:
                    related_skus = json.loads(raw_related) or []
                except (TypeError, ValueError):
                    related_skus = []
            elif isinstance(raw_related, list):
                related_skus = raw_related
            # Robert 2026-08-11 ("skupiny podle SKU... se projevi tim, ze
            # se vzajemne budou zobrazovat jako souvisejici produkty") -
            # sourozenci podle SKU kmene (SKU bez posledniho segmentu:
            # 2.1.005.08.04 -> kmen 2.1.005.08) se automaticky doplni za
            # rucne/Shoptetem dane related_product_codes. Kmen musi mit
            # aspon 2 tecky (3 segmenty), jinak by byl prilis obecny
            # (napr. "2.2" by slucoval pul katalogu) - overeno na zivych
            # datech 2026-08-11: vsechny kmenove skupiny (2-19 produktu,
            # matice/srouby/spojky/zaslepky/profily stejneho rozmeru)
            # jsou koherentni, zadne falesne slouceni; jen 3 aktivni
            # produkty z 538 kmen nemaji. Sourozenec = kmen + PRESNE
            # jeden dalsi segment (NOT LIKE '%.%.%' za kmenem), at se
            # nepritahne hlubsi vetev ciselniku.
            own_sku = row.get("sku") or ""
            if own_sku.count(".") >= 3:
                sku_stem = own_sku.rsplit(".", 1)[0]
                cur.execute(
                    "SELECT sku FROM shop_products "
                    "WHERE active=1 AND is_archived=0 AND sku LIKE %s "
                    "AND sku NOT LIKE %s AND sku<>%s ORDER BY sku",
                    (sku_stem + ".%", sku_stem + ".%.%", own_sku),
                )
                for sib in cur.fetchall():
                    if sib["sku"] not in related_skus:
                        related_skus.append(sib["sku"])
            # Robert 2026-08-11 ("skupinovani pro souvisejici produkty
            # stylem jako ty zavity, udelej vsechno prislusenstvi a
            # spojky" + "jde nam o propojeni produktu formou
            # souvisejici") - druha vrstva skupin: podle NAZVU (stejny
            # princip jako odznak Zavit - parametr se cte primo z nazvu).
            # V nazvu se zavit (M6, M8x20), rozmer (30x30, 45 x 90) a
            # drazka/system (drazka 8, Channel 10, system 45, S10)
            # nahradi zastupnym znakem - produkty se pak shodnym zbytkem
            # nazvu jsou "stejny prvek, jiny parametr" a doplni se za
            # SKU sourozence. Pokryva pripady, kde SKU kmen nestaci
            # (jina vetev ciselniku: Spojovaci sroub M6/M8/M10,
            # Uhelnikova spojka 30x30/40x40/45x45...). Overeno na zivem
            # katalogu 2026-08-11: +85 skupin nad ramec SKU kmenu,
            # vsechny koherentni. Zamerne JEN vetve Prislusenstvi
            # profilu (150) a Spojovaci prvky (152) - u profilu by
            # slucovani pres rozmer spojilo nesouvisejici prurezy,
            # Robert vyslovne rekl "prislusenstvi a spojky".
            own_norm = _normalized_name_group_key(row.get("name"))
            if own_norm:
                cur.execute(_ACCESSORY_BRANCH_PRODUCTS_SQL)
                branch_rows = cur.fetchall()
                # produkt sam musi do vetvi patrit (fetch vraci jen
                # produkty vetvi, takze staci najit vlastni SKU)
                if any(c["sku"] == own_sku for c in branch_rows):
                    for cand in branch_rows:
                        if cand["sku"] == own_sku or cand["sku"] in related_skus:
                            continue
                        if _normalized_name_group_key(cand["name"]) == own_norm:
                            related_skus.append(cand["sku"])
            if related_skus:
                placeholders = ",".join(["%s"] * len(related_skus))
                cur.execute(
                    f"SELECT id, sku, name, slug, price_czk_placeholder, stock_qty, availability_text, "
                    f"unit, cfg_dily_id, is_board_material, is_profile_material, "
                    f"cross_section_label, groove_family "
                    f"FROM shop_products WHERE sku IN ({placeholders}) AND active=1 AND is_archived=0",
                    related_skus,
                )
                related_rows = {r["sku"]: r for r in cur.fetchall()}
                # Vykonnostni audit bot5 2026-09-03 (schvaleno bot3/
                # Robert): drivejsi verze delala 1 SELECT na obrazek PRO
                # KAZDY souvisejici produkt (klidne 10-30+ u spojovaciho
                # materialu) - na vzdalene DB (~21-25ms RTT/dotaz) to
                # zbytecne prodluzovalo nejnavstevovanejsi typ stranky.
                # Jeden davkovy dotaz + prvni radek na product_id v
                # Pythonu (razeni product_id, sort_order, id -> prvni
                # vyskyt na product_id = stejny radek jako drivejsi
                # "ORDER BY sort_order, id LIMIT 1" korelovany dotaz).
                related_ids = [r["id"] for r in related_rows.values()]
                thumb_by_product_id = {}
                if related_ids:
                    img_placeholders = ",".join(["%s"] * len(related_ids))
                    cur.execute(
                        f"SELECT product_id, filename FROM shop_product_images "
                        f"WHERE product_id IN ({img_placeholders}) ORDER BY product_id, sort_order, id",
                        related_ids,
                    )
                    for img_row in cur.fetchall():
                        thumb_by_product_id.setdefault(img_row["product_id"], img_row["filename"])
                for sku in related_skus:
                    r = related_rows.get(sku)
                    if not r:
                        continue
                    thumb_filename = thumb_by_product_id.get(r["id"])
                    related.append({
                        "id": r["id"], "sku": r["sku"], "name": r["name"], "slug": r.get("slug"),
                        "price_czk_placeholder": float(r["price_czk_placeholder"]) if r["price_czk_placeholder"] is not None else None,
                        "stock_qty": r["stock_qty"],
                        "availability_text": r["availability_text"],
                        "unit": r["unit"],
                        "is_board_material": bool(r.get("is_board_material")),
                        "is_profile_material": bool(r.get("is_profile_material")),
                        "cross_section_label": r.get("cross_section_label"),
                        "groove_family": r.get("groove_family"),
                        "image_url": f"/content-files/gallery/{thumb_filename}" if thumb_filename else None,
                    })

            # Souvisejici dokumenty (Robert 2026-08-08: "souvisejici
            # dokumenty napr pdf a videa").
            cur.execute(
                "SELECT id, filename, original_name, doc_type, caption, sort_order "
                "FROM shop_product_documents WHERE product_id=%s ORDER BY sort_order, id",
                (product_id,),
            )
            documents = [
                {
                    "id": d["id"],
                    "url": (f"https://www.youtube.com/embed/{d['filename']}" if d["doc_type"] == "youtube"
                            else f"/content-files/product-documents/{d['filename']}"),
                    "original_name": d["original_name"], "doc_type": d["doc_type"],
                    "caption": d["caption"], "sort_order": d["sort_order"],
                }
                for d in cur.fetchall()
            ]

            # bot5 2026-08-10 (Robert: "prichozi na eshop mohl velmi
            # rychle pochopit ktere prislusenstvi nebo spojka je
            # kompatibilní se kterym profilem") - jen u profilu se
            # znamou drazkou (backfill nepokryl uplne vsechny, viz
            # scripts/2026-08-10_product_cross_section_groove_backfill.py).
            compatible_accessories = []
            if row.get("is_profile_material") and row.get("groove_family"):
                compatible_accessories = _compatible_accessories(
                    cur,
                    groove_families=[row["groove_family"]],
                    cross_sections=[row["cross_section_label"]] if row.get("cross_section_label") else None,
                )

            # bot5 2026-08-10 (Robert: "navrhni kam to na eshop
            # umistime... jsou to ilustracni nahledy pouziti nasich
            # prvku v praxi") - u profilu odvozeno ze stejne
            # kompatibility jako compatible_accessories vyse (obrazky
            # jeho vhodneho prislusenstvi), u prislusenstvi PRIMO jeho
            # vlastni obrazky (product_id = tento produkt).
            usage_image_source_ids = [product_id] + [a["id"] for a in compatible_accessories]
            usage_images = _usage_images_for_products(cur, usage_image_source_ids)

            # Cenova hierarchie (viz _effective_unit_price vyse) - kupon
            # z ?coupon= query parametru (Robert: "zadani kodu na
            # product.html"), dealerska sleva podle prihlaseneho uzivatele.
            coupon_code = (request.args.get("coupon") or "").strip() or None
            effective_price, price_basis = _effective_unit_price(
                cur, row, user=current_user(), coupon_code=coupon_code,
            )
            # Montaz jako volitelna sluzba u dodavatelskych (vanDrawee)
            # karet (Robert 2026-09-18: "pridat volbu montaze" -> "neuvadet
            # 20% na webu, jen v adminu v koeficientech" - stejny princip
            # jako montaz_pct pro nase sestavy, ale SAMOSTATNY klic (jina
            # sluzba, jina cena), viz api/admin_settings.py +
            # api/cart.py::is_supplier_montaz. Procento se NEPOSILA na
            # klienta, jen uz hotova castka v Kc.
            vandrawee_montaz_czk = None
            vandrawee_cena_obsahuje_text = None
            if row.get("supplier_name") == "vanDrawee":
                if row.get("price_czk_placeholder") is not None:
                    pct = get_setting(cur, "vandrawee_montaz_pct", "20")
                    try:
                        vandrawee_montaz_czk = round(float(row["price_czk_placeholder"]) * float(pct) / 100.0, 2)
                    except (TypeError, ValueError):
                        vandrawee_montaz_czk = None
                # "Cena obsahuje" blok (Robert 2026-09-23: "tento text
                # chci editovatelný v adminu, protože se bude opakovat
                # na vsech Vandr sestavach") - CTENO DYNAMICKY z
                # app_settings (editace viz api/admin_settings.py
                # VANDRAWEE_CENA_OBSAHUJE_KEY), NE zapecene do
                # `description` jednotlive karty - zmena nastaveni se
                # projevi okamzite na vsech Vandr kartach.
                vandrawee_cena_obsahuje_text = get_setting(
                    cur, "vandrawee_cena_obsahuje_text",
                    "Cena obsahuje:\n- výrobu stavebnice\n- dodání ve zcela rozloženém stavu, profily v ochranné fólii\n"
                    "- obecný montážní návod v PDF a ručně doplněné popisy ve 3D náhledech",
                )
    finally:
        conn.close()
    if row.get("price_czk_placeholder") is not None:
        row["price_czk_placeholder"] = float(row["price_czk_placeholder"])
    for col in ("alternative_product_codes", "related_product_codes"):
        val = row.get(col)
        if isinstance(val, str):
            try:
                row[col] = json.loads(val)
            except (TypeError, ValueError):
                row[col] = []
    for col in ("dealer_discount_percent", "sale_price_czk"):
        if row.get(col) is not None:
            row[col] = float(row[col])
    for col in ("sale_price_from", "sale_price_until"):
        if row.get(col) is not None:
            row[col] = row[col].isoformat()
    val = row.get("product_specs_json")
    if isinstance(val, str):
        try:
            row["product_specs_json"] = json.loads(val)
        except (TypeError, ValueError):
            row["product_specs_json"] = None
    row["effective_price_czk"] = effective_price
    row["price_basis"] = price_basis
    row["vandrawee_montaz_czk"] = vandrawee_montaz_czk
    row["vandrawee_cena_obsahuje_text"] = vandrawee_cena_obsahuje_text
    if not is_staff:
        _strip_staff_only_fields(row)
    _apply_dogus_admin_cost_gate(row)
    return jsonify({"product": row, "gallery": gallery, "related_products": related, "documents": documents, "compatible_accessories": compatible_accessories, "usage_images": usage_images})


# --- Prirezy profilu (bot3, 2026-08-06) - Robert: "u kazdeho profilu v
# eshopu musi byt uvedeno: 1ks = 3000mm, moznost zadat prirezy". Cena je
# podle poctu CELYCH spotrebovanych tyci (3000mm), dopoctenych
# bin-packingem ze zadanych prirezu (delka+pocet) - stejna funkce
# (cutting_algo.pack_1d) jako pouziva admin rezny plan v api/cutting.py,
# jen s jedinou "skladovou" delkou (PROFILE_MAX_LENGTH_MM) misto
# tabulky shop_cutting_stock (ta je vazana na material_key, ktery
# shop_products/cfg_dily dnes nema - viz plan). Objednavat lze jen cele
# tyce (Robert: "3, 6, 9, 12..."), prirezy uvnitr jsou libovolne,
# zbytky patri klientovi (nic z toho se tu neresi - jen pocet tyci). ---
MAX_CUT_PIECE_ROWS = 100
MAX_CUT_PIECE_TOTAL_QTY = 2000

TZ_PRAGUE = ZoneInfo("Europe/Prague")


def now_local():
    """"Ted" pro porovnavani s casovymi poli akcni ceny/kuponu
    (sale_price_from/until, valid_from/until) - bot3/revize kodu,
    2026-09-02: admin.html pouziva <input type="datetime-local">
    (zadna zona, jen holy retezec typu "2026-09-03T10:00"), backend
    ho uklada 1:1 do DATETIME sloupce (viz komentar u PUT produktu
    nize - "datumy jdou primo") - hodnota v DB tak VZDY reprezentuje
    prazsky mistni cas admina, NIKDY UTC. DB server (MariaDB) i tenhle
    API server ale bezi v UTC (system_time_zone) - `datetime.utcnow()`
    by tak porovnaval UTC se skutecne prazskym casem a slevy/kupony by
    zacinaly/koncily o 1-2 h POZDEJI, nez admin zadal (posun podle
    aktualniho letniho/zimniho casu - zoneinfo DST resi samo, proto
    NE pevny posun +2h). `.replace(tzinfo=None)` vraci naivni datetime
    (bez zony) prave proto, aby slo primo srovnavat s naivnimi hodnotami
    z DATETIME sloupcu (tz-aware vs naive by Python odmitl porovnat).
    Jediny zdroj tehle logiky - volat odsud, ne duplikovat utcnow()."""
    return datetime.now(TZ_PRAGUE).replace(tzinfo=None)


# --- Cenova hierarchie (bot3, 2026-08-08; rozsireno bot4, 2026-08-08) -
# Robert postupne upresnil slevove mechanismy: dealerska sleva (%, jen
# pro schvalene dealery), akcni cena (pevna castka, casove omezena),
# kupon (per-produkt, sdileny kod), skupinova sleva zakaznika (%, viz
# shop_customer_groups/orders.py V3). Robert explicitne potvrdil
# ("ad 4 je špatně, nesmí se slevy nikdy sčítat, platí jedna nebo
# druhá"): VSECHNY 4 mechanismy jsou VZAJEMNE VYLUCNE kandidati, NIKDY
# se nekombinuji/nenasobi mezi sebou - bere se jen ta NEJNIZSI
# (nejvyhodnejsi pro zakaznika) z aplikovatelnych cen. Puvodne (do
# tohoto commitu) orders.py skupinovou slevu chybne NASOBIL AZ NA
# VYSLEDEK teto funkce (base_price * (1 - discount_percent/100)) -
# tim se skupinova sleva vzdy kombinovala s vyherni cenou z techto 3,
# coz je presne to, co Robert zakazal. Oprava: skupinova sleva je ted
# 4. rovnocenny kandidat primo tady, orders.py uz zadnou dalsi
# nasobici slevu neaplikuje (viz jeho komentar u volani teto funkce).
# "basis" v navratove hodnote rika, ktera z nich vyhrala (pro
# transparentni zobrazeni "Akční cena"/"Dealerská cena"/"Cena s
# kupónem"/"Skupinová sleva" na strance produktu/v košíku).
def _plocha_tabule_m2(product):
    """Plocha jedne tabule v m2, nebo None kdyz rozmery chybi."""
    w, h = product.get("board_sheet_width_mm"), product.get("board_sheet_height_mm")
    if not w or not h:
        return None
    plocha = (float(w) / 1000.0) * (float(h) / 1000.0)
    return plocha if plocha > 0 else None


def cena_desky(product, jednotkova_cena):
    """(cena za CELOU TABULI, cena za m2) - bez ohledu na to, jak je ulozena.

    Robert 2026-08-07: "u deskovych materialu se cena zadava za 1m2". Jenze
    v katalogu jsou desky ulozene RUZNE - MDF (3939) ma unit='m2', PR10
    (3539) a laminovana (3671) maji unit='ks' a cenu za celou tabuli. E-shop
    pritom nakupuje CELE TABULE (_sheets_needed_for_cuts) a nasobi jejich
    poctem, takze u desky s unit='m2' by tabule 2070x2800 vysla na 1000 Kc
    misto 5796 - sestina skutecne ceny.

    Dnes to nikam netece jen proto, ze 3939 nema `cutting_material_key` a
    kosik ji nepusti dal (cart.py). Je to ale past nastrazena na toho, kdo
    ten klic doplni: spustil by prodej za sestinu a nemel by jak tusit proc.

    PODMINKA (bot8 2026-09-11): rozhoduje `is_board_material` A `unit`
    dohromady - ne samotna jednotka. Kdyby m2 dostalo neco jineho nez deska,
    tenhle prepocet se toho nesmi chytit.
    """
    if not product.get("is_board_material") or jednotkova_cena is None:
        return jednotkova_cena, None
    plocha = _plocha_tabule_m2(product)
    jednotka = str(product.get("unit") or "").strip().lower()
    if jednotka == "m2":
        za_m2 = float(jednotkova_cena)
        za_tabuli = round(za_m2 * plocha, 2) if plocha else za_m2
    else:
        za_tabuli = float(jednotkova_cena)
        za_m2 = round(za_tabuli / plocha, 2) if plocha else None
    return za_tabuli, za_m2


def _effective_unit_price(cur, product, user=None, coupon_code=None, now=None):
    base = float(product.get("price_czk_placeholder") or 0)
    now = now or now_local()
    best_price, best_basis = base, "base"

    sale_price = product.get("sale_price_czk")
    if sale_price is not None:
        sf, su = product.get("sale_price_from"), product.get("sale_price_until")
        if (sf is None or now >= sf) and (su is None or now <= su):
            sale_price = float(sale_price)
            if sale_price < best_price:
                best_price, best_basis = sale_price, "sale"

    customer = None
    if user:
        # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02): g.active=1 v
        # ON podmince (ne WHERE) - zakaznik s deaktivovanou skupinou
        # zustane najit (LEFT JOIN porad vrati radek), jen group_discount_percent
        # vyjde NULL (bez slevy), misto aby JOIN cely radek zahodil.
        cur.execute(
            "SELECT c.is_dealer_approved, g.discount_percent AS group_discount_percent "
            "FROM shop_customers c LEFT JOIN shop_customer_groups g ON g.id = c.group_id AND g.active=1 "
            "WHERE c.user_id=%s",
            (user["id"],),
        )
        customer = cur.fetchone()

    if customer and customer["is_dealer_approved"] and product.get("dealer_discount_percent"):
        pct = float(product["dealer_discount_percent"])
        dealer_price = round(base * (1 - pct / 100), 2)
        if dealer_price < best_price:
            best_price, best_basis = dealer_price, "dealer"

    if customer and customer.get("group_discount_percent"):
        pct = float(customer["group_discount_percent"])
        if pct:
            group_price = round(base * (1 - pct / 100), 2)
            if group_price < best_price:
                best_price, best_basis = group_price, "group"

    # Robert (přes bot3, 2026-09-04): "deaktivuj slevové kódy všude v
    # e-shopu" - reverzibilní feature-flag, stejný vzor jako cart_enabled
    # (Robert, 2026-08-18). Kupónová větev se přeskočí úplně, i kdyby byl
    # coupon_code technicky platný - žádné volání _effective_unit_price()
    # (produktová stránka, náhled přířezu, košík, checkout - viz komentáře
    # u ostatních volání) tak kupón neaplikuje, dokud se flag znovu nezapne.
    if coupon_code and get_setting(cur, "discount_codes_enabled", "1") != "0":
        cur.execute(
            "SELECT discount_type, discount_value, valid_from, valid_until, active "
            "FROM shop_product_coupons WHERE product_id=%s AND code=%s",
            (product["id"], coupon_code),
        )
        c = cur.fetchone()
        if c and c["active"]:
            cf, cu = c["valid_from"], c["valid_until"]
            if (cf is None or now >= cf) and (cu is None or now <= cu):
                if c["discount_type"] == "percent":
                    coupon_price = round(base * (1 - float(c["discount_value"]) / 100), 2)
                else:
                    coupon_price = max(0.0, round(base - float(c["discount_value"]), 2))
                if coupon_price < best_price:
                    best_price, best_basis = coupon_price, "coupon"

    return best_price, best_basis


def _validate_cut_pieces(raw_cuts):
    """Zvaliduje a ocisti seznam prirezu z requestu (spolecne pro
    /cut-plan-preview i pro api/cart.py). Vraci (clean_cuts, error) -
    error je None pri uspechu."""
    if not isinstance(raw_cuts, list) or not raw_cuts:
        return None, "Zadej alespoň jeden přířez (délka + počet kusů)."
    if len(raw_cuts) > MAX_CUT_PIECE_ROWS:
        return None, f"Příliš mnoho řádků přířezů (max {MAX_CUT_PIECE_ROWS})."
    clean = []
    total_qty = 0
    for row in raw_cuts:
        if not isinstance(row, dict):
            return None, "Neplatný řádek přířezu."
        try:
            length_mm = float(row.get("length_mm"))
            qty = int(row.get("qty"))
        except (TypeError, ValueError):
            return None, "Neplatná délka nebo počet kusů u přířezu."
        if length_mm <= 0 or length_mm > PROFILE_MAX_LENGTH_MM:
            return None, f"Délka přířezu musí být 1–{PROFILE_MAX_LENGTH_MM} mm."
        if qty <= 0:
            return None, "Počet kusů přířezu musí být kladné celé číslo."
        total_qty += qty
        if total_qty > MAX_CUT_PIECE_TOTAL_QTY:
            return None, f"Příliš mnoho kusů celkem (max {MAX_CUT_PIECE_TOTAL_QTY})."
        clean.append({"length_mm": length_mm, "qty": qty})
    return clean, None


def _rods_needed_for_cuts(clean_cuts, kerf_mm=4.0):
    """clean_cuts uz musi projit _validate_cut_pieces() vyse. Vraci
    (rods_needed:int, pack_result:dict) - pack_result je cely vystup
    cutting_algo.pack_1d (staci na "kolik tyci"/waste, do DB se neuklada,
    jen cut_pieces_json se zadanim vstupu, viz api/cart.py).

    kerf_mm=4.0 (Robert 2026-08-06: "pozor kotouč pily má 4mm") - sirka
    rezu odebrana z tyce pri kazdem rezu navic, viz cutting_algo.pack_1d.
    """
    pieces = [
        {"id": str(i), "length_mm": c["length_mm"], "qty": c["qty"]}
        for i, c in enumerate(clean_cuts)
    ]
    stock = [{
        "id": 1, "label": f"Tyč {PROFILE_MAX_LENGTH_MM:.0f} mm",
        "length_mm": float(PROFILE_MAX_LENGTH_MM), "qty": None, "price_czk": 0.0,
    }]
    result = cutting_algo.pack_1d(pieces, stock, kerf_mm=kerf_mm)
    # unplaced (kus delsi nez tyc uz odfiltruje _validate_cut_pieces, ale
    # pro jistotu - kdyby nekdy pribyla druha skladova delka apod.)
    # se pocitaji jako dalsi (neefektivni) samostatne tyce, at cena nikdy
    # neschazi ani v neocekavanem pripade.
    rods_needed = len(result.get("bars", [])) + sum(u["qty"] for u in result.get("unplaced", []))
    return max(rods_needed, 1), result


# --- Prirezy DESEK (bot4, 2026-08-08, Robert: "nahraju ti testovací
# objednávku profily s přířezy a desky, uchop to napoj reálně funkčně
# na řezné plány" - "nebudou se prodavat cele desky ale přířezy") -
# presny mirror _validate_cut_pieces/_rods_needed_for_cuts vyse, jen 2D
# (width_mm+height_mm misto jedne length_mm, cutting_algo.pack_2d misto
# pack_1d). Na rozdil od profilu (jedna pevna PROFILE_MAX_LENGTH_MM
# konstanta pro vsechny prurezy) maji desky ruznou velikost skladove
# tabule podle materialu, proto se stock cte ze shop_cutting_stock
# podle product["cutting_material_key"] (nove pole, viz
# sql/2026-08-08_board_cutting_material_key.sql) - produkt bez
# nastaveneho cutting_material_key v adminu prirezy nabizet nemuze
# (viz chybova hlaska nize).
def _validate_cut_pieces_2d(raw_cuts):
    """Mirror _validate_cut_pieces() vyse, jen pro desky."""
    if not isinstance(raw_cuts, list) or not raw_cuts:
        return None, "Zadej alespoň jeden přířez (šířka × výška + počet kusů)."
    if len(raw_cuts) > MAX_CUT_PIECE_ROWS:
        return None, f"Příliš mnoho řádků přířezů (max {MAX_CUT_PIECE_ROWS})."
    clean = []
    total_qty = 0
    for row in raw_cuts:
        if not isinstance(row, dict):
            return None, "Neplatný řádek přířezu."
        try:
            width_mm = float(row.get("width_mm"))
            height_mm = float(row.get("height_mm"))
            qty = int(row.get("qty"))
        except (TypeError, ValueError):
            return None, "Neplatná šířka, výška nebo počet kusů u přířezu."
        if width_mm <= 0 or height_mm <= 0:
            return None, "Šířka i výška přířezu musí být kladné číslo."
        if qty <= 0:
            return None, "Počet kusů přířezu musí být kladné celé číslo."
        total_qty += qty
        if total_qty > MAX_CUT_PIECE_TOTAL_QTY:
            return None, f"Příliš mnoho kusů celkem (max {MAX_CUT_PIECE_TOTAL_QTY})."
        clean.append({"width_mm": width_mm, "height_mm": height_mm, "qty": qty})
    return clean, None


def _fetch_board_stock_and_kerf(cur, material_key):
    """Stejny dotaz jako _fetch_stock_and_kerf() v api/cutting.py
    (cut_kind='deska' pevne) - zkopirovano sem misto cross-module
    importu, protoze products.py se importuje driv nez cutting.py (viz
    hlavicka souboru)."""
    cur.execute(
        "SELECT id, label, stock_width_mm, stock_height_mm, price_czk "
        "FROM shop_cutting_stock WHERE cut_kind='deska' AND material_key=%s AND active=1 "
        "ORDER BY sort_order",
        (material_key,),
    )
    stock_rows = cur.fetchall()
    cur.execute("SELECT kerf_mm FROM shop_cutting_settings WHERE material_key=%s", (material_key,))
    settings_row = cur.fetchone()
    kerf_mm = float(settings_row["kerf_mm"]) if settings_row else 3.0
    return stock_rows, kerf_mm


def _sheets_needed_for_cuts(cur, clean_cuts, material_key):
    """clean_cuts uz musi projit _validate_cut_pieces_2d() vyse. Vraci
    (sheets_needed:int|None, pack_result:dict|None, error:str|None) -
    error kdyz material_key nema zadnou aktivni skladovou variantu
    (admin jeste v adminu nenastavil cutting_material_key produktu,
    nebo pro nej chybi shop_cutting_stock radek)."""
    stock_rows, kerf_mm = _fetch_board_stock_and_kerf(cur, material_key)
    if not stock_rows:
        return None, None, "Pro tento materiál není nastavená žádná skladová varianta desky."
    pieces = [
        {"id": str(i), "width_mm": c["width_mm"], "height_mm": c["height_mm"], "qty": c["qty"]}
        for i, c in enumerate(clean_cuts)
    ]
    stock = [{
        "id": s["id"], "label": s["label"],
        "width_mm": float(s["stock_width_mm"]), "height_mm": float(s["stock_height_mm"]),
        "qty": None, "price_czk": float(s["price_czk"]),
    } for s in stock_rows]
    result = cutting_algo.pack_2d(pieces, stock, kerf_mm=kerf_mm)
    sheets_needed = result["stats"]["sheets_used"] + sum(u["qty"] for u in result.get("unplaced", []))
    return max(sheets_needed, 1), result, None


def _waste_breakdown(plan):
    """Kolik dlouhych zbytku (a v jakych poctech) klientovi po rezani
    zustane - Robert 2026-08-06: 'doplňujme vždy jak dlouhé zbytky
    dostane klient a v jakých počtech'. Zbytky z tyci patri klientovi
    (viz Robert drive: 'zbytky z tyčí patří klientovi'), takze se
    vypocitavaji ze skutecneho rozrezaneho planu (cutting_algo.pack_1d),
    ne odhadem. Zanedbatelne zbytky (<1mm, napr. kus presne na konec
    tyce) se vynechavaji, stejny prah jako pro pocet rezu vyse."""
    counts = {}
    for b in plan.get("bars", []):
        waste = b.get("waste_mm") or 0.0
        if waste <= 0.5:
            continue
        length = round(waste)
        counts[length] = counts.get(length, 0) + 1
    return [
        {"length_mm": length, "qty": qty}
        for length, qty in sorted(counts.items(), reverse=True)
    ]


def _cut_service_price_czk(cur, cfg_dily_id):
    """Cena za 1 rez pro dany profil (Robert 2026-08-06: "ceny řezů jsou
    v adminu u cen profilů") - cfg_dily.price_per_cut_czk, stejne pole,
    ktere uz pouziva 3D scena pro cenu spoju (viz komentar u
    "Kazdy profil ve scene si v realu vyzadal rez" vyse v tomhle
    souboru). None, pokud cena rezu jeste neni pro tenhle profil v
    adminu nastavena - v tom pripade se "Řezy" polozka vubec neprida
    (radeji nic, nez vymyslena castka)."""
    if not cfg_dily_id:
        return None
    cur.execute("SELECT price_per_cut_czk FROM cfg_dily WHERE id=%s", (cfg_dily_id,))
    row = cur.fetchone()
    price = (row or {}).get("price_per_cut_czk")
    return float(price) if price is not None else None


@app.post("/api/shop/products/<int:product_id>/cut-plan-preview")
def shop_product_cut_plan_preview(product_id):
    """Verejny (bez prihlaseni, stejne jako GET /api/shop/products/<id>)
    "kalkulator" pro produktovou stranku - zadane prirezy -> kolik
    celych 3000mm tyci je potreba + cena. Cenu i pocet tyci pak server
    znovu (nezavisle) dopocita i pri skutecnem pridani do kosiku
    (api/cart.py) - tenhle endpoint je jen nahled, nic neuklada."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, cfg_dily_id, is_board_material, is_profile_material, cutting_material_key, "
                "price_czk_placeholder, sale_price_czk, sale_price_from, sale_price_until, dealer_discount_percent "
                "FROM shop_products WHERE id=%s AND active=1",
                (product_id,),
            )
            product = cur.fetchone()
            if not product:
                return jsonify({"error": "Produkt neexistuje nebo není dostupný."}), 404

            body = request.get_json(silent=True) or {}
            # Zivy nalez (bot3/revize kodu, 2026-09-02): nahled rezu pouzival
            # holy price_czk_placeholder, ne _effective_unit_price() jako
            # stranka produktu/kosik - jakmile by byla aktivni akce/
            # dealerska/skupinova sleva nebo kupon, zakaznik by tu videl
            # jinou cenu nez pak v kosiku. Stejny mechanismus jako
            # GET /api/shop/products/<id> (kupon z tela, ne query - tenhle
            # endpoint je POST).
            coupon_code = (body.get("coupon") or "").strip() or None
            unit_price, price_basis = _effective_unit_price(
                cur, product, user=current_user(), coupon_code=coupon_code,
            )

            # Deska (Robert 2026-08-08: "nahraju ti testovací objednávku
            # profily s přířezy a desky" - "nebudou se prodavat cele
            # desky ale přířezy, deskám chybí 2. rozměr Y") - samostatna
            # vetev, jina navratova struktura (sheets_needed/2D, zadna
            # cena za rez - viz _sheets_needed_for_cuts docstring).
            if product.get("is_board_material"):
                if not product.get("cutting_material_key"):
                    return jsonify({"error": "Pro tento produkt zatím není v adminu nastavený materiál pro řezný plán."}), 400
                clean_cuts_2d, err = _validate_cut_pieces_2d(body.get("cuts"))
                if err:
                    return jsonify({"error": err}), 400
                sheets_needed, board_plan, stock_err = _sheets_needed_for_cuts(cur, clean_cuts_2d, product["cutting_material_key"])
                if stock_err:
                    return jsonify({"error": stock_err}), 400
                # Nakupuji se CELE TABULE, takze se musi nasobit cenou za
                # tabuli - u desky s unit='m2' je `unit_price` za metr
                # ctverecni a tabule by vysla na sestinu (viz cena_desky).
                cena_za_tabuli, cena_za_m2 = cena_desky(product, unit_price)
                sheets_total = round(sheets_needed * cena_za_tabuli, 2)
                return jsonify({
                    "sheets_needed": sheets_needed,
                    "unit_price_czk": cena_za_tabuli,
                    "unit_price_per_m2_czk": cena_za_m2,
                    "price_basis": price_basis,
                    "total_price_czk": sheets_total,
                    "total_cuts": board_plan["stats"]["total_cuts"],
                    "waste_area_mm2": board_plan["stats"]["total_waste_area_mm2"],
                    "grand_total_czk": sheets_total,
                })

            if not product.get("is_profile_material"):
                return jsonify({"error": "Tenhle produkt není profil ani deska na přířez."}), 400

            clean_cuts, err = _validate_cut_pieces(body.get("cuts"))
            if err:
                return jsonify({"error": err}), 400

            rods_needed, plan = _rods_needed_for_cuts(clean_cuts)
            cut_price = _cut_service_price_czk(cur, product["cfg_dily_id"])
    finally:
        conn.close()

    total_cuts = plan.get("stats", {}).get("total_cuts") or 0
    # Robert: "vždy když klient zadá přířezy je nutné do objenávky
    # přidat automaticky řezy, musí figurovat v košíku" - viditelne uz
    # v nahledu na produktove strance, ne az jako prekvapeni v kosiku.
    cut_service_total = round(total_cuts * cut_price, 2) if cut_price is not None else None
    rods_total = round(rods_needed * unit_price, 2)
    return jsonify({
        "rods_needed": rods_needed,
        "unit_price_czk": unit_price,
        "price_basis": price_basis,
        "total_price_czk": rods_total,
        "rod_length_mm": PROFILE_MAX_LENGTH_MM,
        "total_cut_length_mm": plan.get("stats", {}).get("total_used_mm"),
        "waste_mm": plan.get("stats", {}).get("total_waste_mm"),
        "total_cuts": total_cuts,
        "cut_service_unit_price_czk": cut_price,
        "cut_service_total_czk": cut_service_total,
        "grand_total_czk": round(rods_total + (cut_service_total or 0), 2),
        "waste_breakdown": _waste_breakdown(plan),
    })


@app.post("/api/shop/products")
@require_permission("sklad_karty", "vytvorit")
def shop_products_create():
    body = request.get_json(silent=True) or {}
    sku = (body.get("sku") or "").strip()
    name = (body.get("name") or "").strip()
    if not sku or not name:
        return jsonify({"error": "Vyplň SKU i název."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE sku=%s", (sku,))
            if cur.fetchone():
                return jsonify({"error": "Produkt s tímto SKU už existuje."}), 400
            # slug hned pri vzniku (bot15, 2026-09-02, viz app._unique_product_slug)
            cur.execute(
                """INSERT INTO shop_products
                   (category_id, sku, name, slug, description, unit, price_czk_placeholder, weight_g,
                    min_stock, max_stock, active)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (body.get("category_id"), sku, name, _product_slug_for_name(cur, name), body.get("description"),
                 (body.get("unit") or "ks"), body.get("price_czk_placeholder"),
                 body.get("weight_g"), body.get("min_stock"), body.get("max_stock"),
                 1 if body.get("active", True) else 0),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "shop_product", new_id, f"{sku} - {name}")
    return jsonify({"status": "ok", "id": new_id})


# Robert pres bot3, 2026-09-30 ("potrebujeme mit moznost duplikovat/kopirovat
# skladovou polozku, produkt"). Co se kopiruje a co ne, a proc, je v
# product_duplicate.py (registr tabulek + vynulovane sloupce). Kopie vznika
# NEAKTIVNI (funkce, ne rucni prepnuti `active`). Pravo: stejne jako zalozeni
# noveho produktu - kopie je nova karta.
@app.post("/api/shop/products/<int:product_id>/duplicate")
@require_permission("sklad_karty", "vytvorit")
def shop_product_duplicate(product_id):
    # current_user() PRED get_conn(): get_conn() je sdilene spojeni na thread a jeho
    # close() dela rollback - zavolane uprostred transakce by odrolovalo necommitnute
    # INSERTy kopie (pooled-conn past).
    user = current_user()
    conn = get_conn()
    result = None
    try:
        with conn.cursor() as cur:
            result = product_duplicate.duplicate_product(
                cur, product_id, slug_for_name=_product_slug_for_name,
                created_by=user["id"], created_role=user.get("role"),
                gallery_dir=gallery_items.GALLERY_ITEMS_DIR, docs_dir=PRODUCT_DOCS_DIR)
        conn.commit()
    except product_duplicate.ProductNotFound:
        conn.rollback()
        return jsonify({"error": "Produkt neexistuje."}), 404
    except BaseException:
        conn.rollback()
        if result:  # selhal az commit: soubory uz existuji, DB radky ne
            product_duplicate.remove_files(result["created_files"])
        raise
    finally:
        conn.close()
    log_audit(user["id"], "duplicate", "shop_product", result["id"],
              f"z #{product_id}: {result['sku']} - {result['name']}")
    result.pop("created_files")
    return jsonify({"status": "ok", **result}), 201


# Robert 2026-10-01 ("aby se prostě strojově vytvářely pěkné URL adresy pro SEO, ale ne ručně botem"): adresu
# (slug) produktu tvori a meni JEN product_slug.py. Tenhle endpoint sjednoti adresy VEREJNYCH produktu, ktere
# neodpovidaji nazvu (po prejmenovani, z puvodniho importu, s internim nazvem dodavatele): `dry_run` (vychozi) jen
# ukaze, co by se zmenilo (provede se a vrati zpet = presny nahled); `ids` omezi vyber (tlacitko v karte).
# Kazda zmenena adresa zapise 301 ze stare.
@app.post("/api/shop/products/normalize-slugs")
@require_permission("sklad_karty", "upravit")
def shop_products_normalize_slugs():
    body = request.get_json(silent=True) or {}
    dry_run = bool(body.get("dry_run", True))
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    user = current_user()  # PRED get_conn() - pooled-conn past
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            zmeny = product_slug.apply(cur, product_slug.proposals(cur, ids=ids or None))
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    if zmeny and not dry_run:
        log_audit(user["id"], "normalize_slugs", "shop_product", None, f"{len(zmeny)} adres produktu")
    return jsonify({"status": "ok", "dry_run": dry_run, "count": len(zmeny), "changes": zmeny[:500]})


@app.put("/api/shop/products/<int:product_id>")
@require_permission("sklad_karty", "upravit")
def shop_products_update(product_id):
    body = request.get_json(silent=True) or {}
    # Nazev a SKU: prazdna hodnota by se ulozila (a prazdne SKU by pak kolidovalo s dalsi kartou), prilis
    # dlouha by spadla na DataError (500). bot5, 2026-09-30 (nazev karty je od ted editovatelny).
    for klic, max_delka, hlaska in (
        ("name", 200, "Název"),
        ("sku", 150, "SKU"),
    ):
        if klic in body:
            hodnota = body[klic].strip() if isinstance(body[klic], str) else ""
            if not hodnota:
                return jsonify({"error": f"{hlaska} nesmí být prázdné." if klic == "sku" else f"{hlaska} nesmí být prázdný."}), 400
            if len(hodnota) > max_delka:
                return jsonify({"error": f"{hlaska} může mít nejvýš {max_delka} znaků."}), 400
            body[klic] = hodnota
    fields, params = [], []
    for key in ("category_id", "sku", "name", "description", "unit", "price_czk_placeholder",
                "weight_g", "min_stock", "max_stock",
                # Robert 2026-08-08 ("dej do skladových karet deskový
                # materiálů ten formát tabule k vyplňování"): referencni
                # rozmer cele tabule, ze ktere se rezou kusy - viz
                # sql/2026-08-08_product_board_sheet_format.sql.
                "board_sheet_width_mm", "board_sheet_height_mm",
                # Robert 2026-08-08 ("napoj reálně funkčně na řezné plány"):
                # mapovani produktu na shop_cutting_stock.material_key (viz
                # sql/2026-08-08_board_cutting_material_key.sql), aby
                # objednavky prirezu teto desky sly zaradit do rezneho planu.
                "cutting_material_key",
                # Robert 2026-08-08 ("tak založ v kartách produktů také
                # rozměry"): rozmery pro vypocet objemu Toptrans dopravy u
                # produktu BEZ cfg_dily_id (prislusenstvi/scena) - viz
                # sql/2026-08-08_toptrans_volume.sql a
                # api/orders.py::_product_unit_volume_m3.
                "length_mm", "width_mm", "height_mm",
                # Robert 2026-07-26: "a mělo by to být uvnitř karet" - Shoptet
                # importem naplnena pole (task #68) byla doteď jen k cteni,
                # ted editovatelna primo ve skladove karte (viz #stockCardShoptet).
                "manufacturer", "supplier_name", "warranty", "ean",
                "availability_text", "category_path",
                # bot2, 2026-07-28: zdrojova URL na logiman.cz pro tydenni
                # automaticky refresh ceny (viz shop_products_refresh_price/
                # run_product_price_refresh_cli) - editovatelna stejne jako
                # ostatni doplnkova pole ve skladove karte.
                "price_source_url",
                # Robert 2026-08-08 ("GEO/SEO(udelat)"): SEO meta pole na
                # skladove karte, stejny vzor jako content_categories.meta_title/
                # meta_description - viz sql/2026-08-08_product_seo_meta.sql.
                "meta_title", "meta_description",
                # Robert 2026-08-08 ("akcni cena s casovou platnosti") -
                # datumy jdou primo, JS posila ISO string, MySQL DATETIME
                # sloupec to prijme.
                "sale_price_czk", "sale_price_from", "sale_price_until"):
        if key in body:
            fields.append(f"{key}=%s")
            params.append(body[key])
    # Robert 2026-08-08 ("dealerska sleva... pouze pro admina") - jen
    # admin smi menit procento slevy, vynuceno tady (ne jen skryto v
    # UI) - stejny vzor jako drivejsi "Testovaci data" admin-only fix.
    if "dealer_discount_percent" in body:
        if current_user()["role"] != "admin":
            return jsonify({"error": "Dealerskou slevu smí nastavit jen administrátor."}), 403
        fields.append("dealer_discount_percent=%s")
        params.append(body["dealer_discount_percent"])
    # bot7, 2026-08-07: vychozi barva produktu ve 3D scene (viz
    # sql/2026-08-07_product_scene_color.sql) - "" (zruseni v adminu)
    # se musi ulozit jako NULL, ne jako prazdny retezec (na rozdil od
    # ostatnich textovych poli vyse zde prazdna hodnota ma jasny vyznam
    # "zadna barva", ne jen chybejici vstup).
    if "color_hex" in body:
        fields.append("color_hex=%s")
        params.append(body["color_hex"] or None)
    # bot7, 2026-08-07 ("postavit 2D protahovani pro desky") - viz
    # sql/2026-08-07_product_board_material.sql.
    if "is_board_material" in body:
        fields.append("is_board_material=%s")
        params.append(1 if body["is_board_material"] else 0)
    # Robert 2026-08-08 ("do 3Dsceny nebudou vsechny produkty z eshopu,
    # ani vsechny ktere maji stp, ale pouze produkty s priznakem:
    # ProScenu") - vlastni explicitni prepinac, uz se NEnastavuje
    # automaticky pri uspesnem prevodu STP/FBX (viz
    # shop_products_fbx_upload v app.py).
    if "visible_in_scene" in body:
        fields.append("visible_in_scene=%s")
        params.append(1 if body["visible_in_scene"] else 0)
    # Robert 2026-08-09 ("toto bych potreboval natocit kulatinou nahoru") -
    # vychozi orientace pri vlozeni ze sceny, viz placeAtOrigin ve
    # scene.html a fetch_katalog_parts v app.py.
    if "place_vertical" in body:
        fields.append("place_vertical=%s")
        params.append(1 if body["place_vertical"] else 0)
    # bot4, 2026-08-08 ("Hover okno produktu") - viz
    # sql/2026-08-08_product_hover_price.sql.
    for key in ("price_visible_default", "hover_show_price", "hover_show_availability"):
        if key in body:
            fields.append(f"{key}=%s")
            params.append(1 if body[key] else 0)
    # alternative_product_codes/related_product_codes jsou JSON sloupce -
    # frontend posila list[str] (uz rozparsovany z comma-separated inputu).
    for key in ("alternative_product_codes", "related_product_codes"):
        if key in body:
            val = body[key]
            fields.append(f"{key}=%s")
            params.append(json.dumps(val) if val else None)
    if "active" in body:
        fields.append("active=%s")
        params.append(1 if body["active"] else 0)
    if "is_archived" in body:
        fields.append("is_archived=%s")
        params.append(1 if body["is_archived"] else 0)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    price_changed = "price_czk_placeholder=%s" in fields
    params.append(product_id)
    nova_adresa = None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Adresa (slug) SLEDUJE nazev a tvori se strojove (product_slug.py): prejmenovani -> nova adresa + 301 ze
            # stare, aktivace produktu bez adresy -> adresa vznikne. Nikdy se nepise rucne (Robert 2026-10-01).
            puvodni = None
            if "name" in body or body.get("active"):
                cur.execute("SELECT name, slug FROM shop_products WHERE id=%s", (product_id,))
                puvodni = cur.fetchone()
            try:
                cur.execute(f"UPDATE shop_products SET {', '.join(fields)} WHERE id=%s", params)
            except pymysql.err.IntegrityError as e:
                # 1062 na SKU: dve karty by mely stejne SKU (typicky po duplikaci) - hlaska misto holeho 500
                conn.rollback()
                if e.args[0] == 1062 and "sku" in str(e.args[1]):
                    return jsonify({"error": "Produkt s tímto SKU už existuje."}), 400
                raise
            if puvodni:
                prejmenovano = "name" in body and body["name"] != puvodni["name"]
                if prejmenovano or not puvodni["slug"]:
                    nova = product_slug.slug_for_name(cur, body.get("name", puvodni["name"]), exclude_id=product_id)
                    if product_slug.change_slug(cur, product_id, nova):
                        nova_adresa = nova
            # Robert ("cena za metr se ma pocitat z ceny za kus... automaticky
            # sama") - cena za metr pro 3D scenu (cfg_dily.price_czk_approx) se
            # jinak prepocitava az nocnim batchem (run_price_refresh_cli), po
            # rucni zmene v adminu by tak chvili zaostavala za novou cenou za
            # kus. Dopocita se hned, ve stejne transakci.
            if price_changed:
                cur.execute(
                    "SELECT cfg_dily_id, price_czk_placeholder FROM shop_products WHERE id=%s",
                    (product_id,),
                )
                row = cur.fetchone()
                if row and row.get("cfg_dily_id") and row.get("price_czk_placeholder") is not None:
                    cur.execute(
                        "UPDATE cfg_dily SET price_czk_approx=%s WHERE id=%s",
                        (round(float(row["price_czk_placeholder"]) / 3.0, 2), row["cfg_dily_id"]),
                    )
        conn.commit()
    finally:
        conn.close()
    action = "archive" if body.get("is_archived") else ("unarchive" if "is_archived" in body else "update")
    log_audit(current_user()["id"], action, "shop_product", product_id,
              ", ".join(fields) + (f" (adresa -> {nova_adresa})" if nova_adresa else ""))
    return jsonify({"status": "ok", **({"slug": nova_adresa} if nova_adresa else {})})


# --- Souvisejici dokumenty (PDF/video) - Robert 2026-08-08: "zalozka
# nova Souvisejici... souvisejici dokumenty napr pdf a videa". ---
@app.post("/api/shop/products/<int:product_id>/documents")
@require_permission("sklad_karty", "upravit")
def shop_product_document_upload(product_id):
    doc_type = request.form.get("doc_type")
    if doc_type not in PRODUCT_DOC_EXT:
        return jsonify({"error": "Neplatný typ dokumentu (pdf/video)."}), 400
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chybí soubor."}), 400
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in PRODUCT_DOC_EXT[doc_type]:
        return jsonify({"error": f"Nepovolená přípona pro {doc_type}: .{ext}"}), 400
    caption = (request.form.get("caption") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                return jsonify({"error": "Produkt neexistuje."}), 404
            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM shop_product_documents WHERE product_id=%s",
                (product_id,),
            )
            next_sort = cur.fetchone()["m"] + 1
            safe_base = secure_filename(f.filename.rsplit(".", 1)[0]) or "dokument"
            stored_name = f"product-{product_id}_{safe_base}-{os.urandom(4).hex()}.{ext}"
            f.save(os.path.join(PRODUCT_DOCS_DIR, stored_name))
            cur.execute(
                "INSERT INTO shop_product_documents (product_id, filename, original_name, doc_type, caption, sort_order) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (product_id, stored_name, f.filename, doc_type, caption, next_sort),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "shop_product_document", new_id, f"produkt {product_id}: {f.filename}")
    return jsonify({
        "status": "ok", "id": new_id, "url": f"/content-files/product-documents/{stored_name}",
        "original_name": f.filename, "doc_type": doc_type, "caption": caption, "sort_order": next_sort,
    }), 201


@app.delete("/api/shop/products/documents/<int:doc_id>")
@require_permission("sklad_karty", "upravit")
def shop_product_document_delete(doc_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM shop_product_documents WHERE id=%s", (doc_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Dokument neexistuje."}), 404
            cur.execute("DELETE FROM shop_product_documents WHERE id=%s", (doc_id,))
        conn.commit()
    finally:
        conn.close()
    try:
        os.remove(os.path.join(PRODUCT_DOCS_DIR, row["filename"]))
    except OSError:
        pass
    log_audit(current_user()["id"], "delete", "shop_product_document", doc_id, None)
    return jsonify({"status": "ok"})


# Robert 2026-08-09: "do zalozky Souvisejici, pridej moznost vlozit do
# detailu produktu video jako embed z youtube" - vedle nahravaneho
# souboru (doc_type='video', mp4/webm/mov) jde ted pridat i YouTube
# odkaz bez nahravani souboru. U doc_type='youtube' se sloupec filename
# nepouziva pro nazev souboru na disku, ale pro extrahovane 11znakove
# YouTube video ID - product.html/admin.html z nej sestavi embed
# (https://www.youtube.com/embed/<id>).
YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


@app.post("/api/shop/products/<int:product_id>/documents/youtube")
@require_permission("sklad_karty", "upravit")
def shop_product_document_youtube_add(product_id):
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    m = YOUTUBE_ID_RE.search(url)
    if not m:
        return jsonify({"error": "Nepodařilo se z odkazu rozpoznat YouTube video (očekávám youtube.com/watch?v=..., youtu.be/... nebo youtube.com/shorts/...)."}), 400
    video_id = m.group(1)
    caption = (body.get("caption") or "").strip() or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                return jsonify({"error": "Produkt neexistuje."}), 404
            cur.execute(
                "SELECT COALESCE(MAX(sort_order), -1) AS m FROM shop_product_documents WHERE product_id=%s",
                (product_id,),
            )
            next_sort = cur.fetchone()["m"] + 1
            cur.execute(
                "INSERT INTO shop_product_documents (product_id, filename, original_name, doc_type, caption, sort_order) "
                "VALUES (%s,%s,NULL,'youtube',%s,%s)",
                (product_id, video_id, caption, next_sort),
            )
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "shop_product_document", new_id, f"produkt {product_id}: youtube {video_id}")
    return jsonify({
        "status": "ok", "id": new_id, "video_id": video_id,
        "doc_type": "youtube", "caption": caption, "sort_order": next_sort,
    }), 201


# --- Kupony (per-produkt, sdileny kod) - Robert 2026-08-08: "kuponovy
# system (forma jednorazove slevy)", upresneno: jen konkretni produkt,
# jeden sdileny kod (ne jednorazove kody na osobu). ---
@app.get("/api/shop/products/<int:product_id>/coupons")
@require_permission("sklad_karty", "zobrazit")
def shop_product_coupons_list(product_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, code, discount_type, discount_value, valid_from, valid_until, active "
                "FROM shop_product_coupons WHERE product_id=%s ORDER BY id DESC",
                (product_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    for r in rows:
        r["discount_value"] = float(r["discount_value"])
        for col in ("valid_from", "valid_until"):
            if r.get(col) is not None:
                r[col] = r[col].isoformat()
        r["active"] = bool(r["active"])
    return jsonify({"coupons": rows})


@app.post("/api/shop/products/<int:product_id>/coupons")
@require_permission("sklad_karty", "upravit")
def shop_product_coupon_create(product_id):
    body = request.get_json(silent=True) or {}
    code = (body.get("code") or "").strip().upper()
    if not code:
        return jsonify({"error": "Chybí kód kupónu."}), 400
    discount_type = body.get("discount_type") if body.get("discount_type") in ("percent", "fixed") else "percent"
    try:
        discount_value = float(body.get("discount_value"))
    except (TypeError, ValueError):
        return jsonify({"error": "Neplatná hodnota slevy."}), 400
    if discount_value <= 0 or (discount_type == "percent" and discount_value > 100):
        return jsonify({"error": "Neplatná hodnota slevy."}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE id=%s", (product_id,))
            if not cur.fetchone():
                return jsonify({"error": "Produkt neexistuje."}), 404
            try:
                cur.execute(
                    "INSERT INTO shop_product_coupons "
                    "(product_id, code, discount_type, discount_value, valid_from, valid_until, active) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (product_id, code, discount_type, discount_value,
                     body.get("valid_from") or None, body.get("valid_until") or None,
                     1 if body.get("active", True) else 0),
                )
            except pymysql.err.IntegrityError:
                return jsonify({"error": f"Kód '{code}' už existuje - zvol jiný."}), 400
            new_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "create", "shop_product_coupon", new_id, f"produkt {product_id}: {code}")
    return jsonify({"status": "ok", "id": new_id}), 201


@app.put("/api/shop/products/coupons/<int:coupon_id>")
@require_permission("sklad_karty", "upravit")
def shop_product_coupon_update(coupon_id):
    body = request.get_json(silent=True) or {}
    fields, params = [], []
    if "active" in body:
        fields.append("active=%s")
        params.append(1 if body["active"] else 0)
    for key in ("valid_from", "valid_until"):
        if key in body:
            fields.append(f"{key}=%s")
            params.append(body[key] or None)
    if "discount_value" in body:
        try:
            fields.append("discount_value=%s")
            params.append(float(body["discount_value"]))
        except (TypeError, ValueError):
            return jsonify({"error": "Neplatná hodnota slevy."}), 400
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    params.append(coupon_id)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE shop_product_coupons SET {', '.join(fields)} WHERE id=%s", params)
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "shop_product_coupon", coupon_id, None)
    return jsonify({"status": "ok"})


@app.delete("/api/shop/products/coupons/<int:coupon_id>")
@require_permission("sklad_karty", "upravit")
def shop_product_coupon_delete(coupon_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM shop_product_coupons WHERE id=%s", (coupon_id,))
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "delete", "shop_product_coupon", coupon_id, None)
    return jsonify({"status": "ok"})


@app.put("/api/shop/products/bulk")
@require_permission("sklad_karty", "upravit")
def shop_products_bulk_update():
    # Hromadna uprava vice produktu najednou (Robert 2026-07-25:
    # "rozšířená evidence položek" - "hromadná úprava" jako ve skladapp).
    # Podporuje jen bezpecnou podmnozinu poli, at se hromadne neprepisi
    # veci jako SKU/nazev, kde by kolize byla nebezpecna.
    body = request.get_json(silent=True) or {}
    ids = body.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "Vyber alespoň jeden produkt."}), 400
    fields, params = [], []
    if "category_id" in body:
        fields.append("category_id=%s")
        params.append(body["category_id"])
    if "is_archived" in body:
        fields.append("is_archived=%s")
        params.append(1 if body["is_archived"] else 0)
    if "active" in body:
        fields.append("active=%s")
        params.append(1 if body["active"] else 0)
    if not fields:
        return jsonify({"error": "Nic ke změně."}), 400
    placeholders = ",".join(["%s"] * len(ids))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE shop_products SET {', '.join(fields)} WHERE id IN ({placeholders})",
                params + ids,
            )
            updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "bulk_update", "shop_product", None,
              f"{updated} produktů: {', '.join(fields)}")
    return jsonify({"status": "ok", "updated": updated})


def _purge_product_files(product_ids, composite_filenames):
    """Uklid souboru na disku PO uspesnem commitu smazani produktu (bot3
    2026-09-02): snimky otocneho nahledu `turntable-frames/<pid>/` +
    kanonicke obrazky `turntable/<slug>/` (turntable.py) a kompozity
    zakreslenych pripominek (product_markups.py). Radky v DB uz odnesl FK
    CASCADE. Best-effort - jakakoli chyba jde jen do logu, smazani produktu
    (uz commitnute) nikdy neshodi. Importy lokalne: oba moduly se v app.py
    importuji az po products."""
    import turntable
    import product_markups
    for pid in product_ids:
        try:
            turntable.purge_product_files(pid)
        except Exception:
            app.logger.exception("uklid turntable souboru produktu %s selhal", pid)
    try:
        product_markups.purge_composites(composite_filenames)
    except Exception:
        app.logger.exception("uklid kompozitu pripominek selhal (%d souboru)", len(composite_filenames))


@app.post("/api/shop/products/bulk-delete")
@require_permission("sklad_karty", "smazat")
def shop_products_bulk_delete():
    # Hromadne smazani vybranych produktu (V11, bot3, 2026-07-26, viz
    # NAVRH_HROMADNE_AKCE.md).
    #
    # Robert 2026-08-02 ("proc nejde mazat bulk produkty?"): puvodni
    # verze sla radek po radku a pro KAZDY produkt navic otevirala nove
    # DB spojeni na uklid fotek (gallery_items.delete_items_for_owner) -
    # DB bezi na vzdalenem hostu, takze pri stovkach produktu (po
    # "Vybrat vsechny odpovidajici filtru" klidne 900+) to preslo 60s
    # gunicorn timeout, worker byl zabit a CELA transakce se odvolala -
    # nesmazalo se nic a UI jen "nefungovalo". Prepsano na davky:
    # 1. DELETE ... WHERE id IN (davka 200) - jeden dotaz misto 200
    # 2. pri IntegrityError v davce (produkt pouzity v nakupni
    #    objednavce - FK bez CASCADE) fallback na radkove mazani JEN
    #    te davky, aby se identifikovaly preskocene
    # 3. commit po kazde davce - i kdyby request umrel na timeoutu,
    #    dosud smazane davky zustanou smazane
    # 4. uklid fotek hromadne az na konci (jedno spojeni, jeden SELECT
    #    filenames + jeden DELETE), soubory z disku pak mimo DB
    # 5. (bot3 2026-09-02) turntable snimky + kompozity pripominek: nazvy
    #    kompozitu se ctou PRED DELETE (FK CASCADE), soubory se mazou az
    #    po commitu, viz _purge_product_files
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    deleted_ids = []
    failed = []
    composites = {}  # pid -> [composite_filename] (jen skutecne smazane se pak uklidi)
    CHUNK = 200
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for start in range(0, len(ids), CHUNK):
                chunk = ids[start:start + CHUNK]
                placeholders = ",".join(["%s"] * len(chunk))
                cur.execute(f"SELECT id, sku FROM shop_products WHERE id IN ({placeholders})", chunk)
                existing = {r["id"]: r["sku"] for r in cur.fetchall()}
                for pid in chunk:
                    if pid not in existing:
                        failed.append({"id": pid, "error": "Produkt neexistuje."})
                chunk_live = [pid for pid in chunk if pid in existing]
                if not chunk_live:
                    continue
                cur.execute(
                    f"SELECT product_id, composite_filename FROM product_markups WHERE product_id IN ({','.join(['%s'] * len(chunk_live))})",
                    chunk_live,
                )
                for r in cur.fetchall():
                    composites.setdefault(r["product_id"], []).append(r["composite_filename"])
                try:
                    ph = ",".join(["%s"] * len(chunk_live))
                    cur.execute(f"DELETE FROM shop_products WHERE id IN ({ph})", chunk_live)
                    deleted_ids.extend(chunk_live)
                except pymysql.err.IntegrityError:
                    # v davce je aspon jeden produkt s FK vazbou (nakupni
                    # objednavka) - projit radkove, preskocit jen viniky
                    for pid in chunk_live:
                        try:
                            cur.execute("DELETE FROM shop_products WHERE id=%s", (pid,))
                            deleted_ids.append(pid)
                        except pymysql.err.IntegrityError:
                            failed.append({
                                "id": pid,
                                "error": f"Produkt {existing[pid]} je použit v nákupní objednávce, nelze smazat.",
                            })
                conn.commit()
    finally:
        conn.close()
    if deleted_ids:
        gallery_items.delete_items_for_owners_bulk("product", deleted_ids)
        _purge_product_files(deleted_ids, [f for pid in deleted_ids for f in composites.get(pid, ())])
    log_audit(current_user()["id"], "bulk_delete", "shop_product", None,
              f"{len(deleted_ids)} produktů smazáno" + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "deleted": len(deleted_ids), "failed": failed})


@app.delete("/api/shop/products/<int:product_id>")
@require_permission("sklad_karty", "smazat")
def shop_products_delete(product_id):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT sku, name FROM shop_products WHERE id=%s", (product_id,))
            existing = cur.fetchone()
            import product_markups
            composites = product_markups.composite_filenames_for_products(cur, [product_id])
            cur.execute("DELETE FROM shop_products WHERE id=%s", (product_id,))
        conn.commit()
    finally:
        conn.close()
    gallery_items.delete_items_for_owner("product", product_id)
    if existing:
        _purge_product_files([product_id], composites)
    detail = f"{existing['sku']} - {existing['name']}" if existing else None
    log_audit(current_user()["id"], "delete", "shop_product", product_id, detail)
    return jsonify({"status": "ok"})


@app.get("/api/shop/products/export.csv")
@require_permission("sklad_karty", "zobrazit")
def shop_products_export():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, parent_id, name FROM content_categories")
            cats = cur.fetchall()
            cur.execute("""
                SELECT sku, name, category_id, description, unit, price_czk_placeholder, weight_g,
                       stock_qty, min_stock, max_stock, active, is_archived,
                       manufacturer, supplier_name, ean, warranty,
                       category_path AS category_path_shoptet, availability_text,
                       alternative_product_codes, related_product_codes
                FROM shop_products ORDER BY sku
            """)
            products = cur.fetchall()
    finally:
        conn.close()
    cat_path = build_category_path_fn(cats)

    def _codes_to_csv(raw):
        # alternative_product_codes/related_product_codes jsou JSON sloupce
        # (viz shop_products_update) - pro CSV se serializuji jako seznam
        # oddeleny ", " (stejny format jako scfAltCodes/scfRelCodes v
        # admin.html - codesToText()/split(",")).
        if not raw:
            return ""
        try:
            lst = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return ""
        return ", ".join(lst) if isinstance(lst, list) else ""

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["sku", "name", "category_path", "description", "unit", "price_czk_placeholder",
                      "weight_g", "stock_qty", "min_stock", "max_stock", "active", "is_archived",
                      "manufacturer", "supplier_name", "ean", "warranty", "category_path_shoptet",
                      "availability_text", "alternative_codes", "related_codes"])
    for p in products:
        writer.writerow([
            p["sku"], p["name"], cat_path(p["category_id"]), p["description"] or "", p["unit"],
            p["price_czk_placeholder"] if p["price_czk_placeholder"] is not None else "",
            p["weight_g"] if p["weight_g"] is not None else "",
            p["stock_qty"], p["min_stock"] if p["min_stock"] is not None else "",
            p["max_stock"] if p["max_stock"] is not None else "", p["active"], p["is_archived"],
            p["manufacturer"] or "", p["supplier_name"] or "", p["ean"] or "", p["warranty"] or "",
            p["category_path_shoptet"] or "", p["availability_text"] or "",
            _codes_to_csv(p["alternative_product_codes"]), _codes_to_csv(p["related_product_codes"]),
        ])
    log_audit(current_user()["id"], "export", "shop_product", None, f"{len(products)} produktů")
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=produkty_export.csv"},
    )


@app.post("/api/shop/products/import")
@require_permission("sklad_karty", "vytvorit")
def shop_products_import():
    # Upsert podle SKU: existujici SKU se aktualizuje, nove se zalozi.
    # category_path (napr. "Elektro > Baterie") ma prednost pred
    # category_id, pokud jsou v CSV oba - umoznuje presunout export z
    # jineho stromu bez znalosti numerickych ID.
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Nahraj CSV soubor (pole 'file')."}), 400
    try:
        text = f.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"error": "Soubor musí být v kódování UTF-8."}), 400
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = set(reader.fieldnames or [])
    if not {"sku", "name"}.issubset(fieldnames):
        return jsonify({"error": "CSV musí obsahovat alespoň sloupce sku,name."}), 400

    def to_float(v):
        v = (v or "").strip()
        try:
            return float(v) if v else None
        except ValueError:
            return None

    def to_int(v):
        v = (v or "").strip()
        try:
            return int(v) if v else None
        except ValueError:
            return None

    present = set(reader.fieldnames or [])
    has_category_col = "category_path" in present or "category_id" in present

    created, updated, errors = 0, 0, []
    cat_cache = {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for i, row in enumerate(reader, start=2):
                sku = (row.get("sku") or "").strip()
                name = (row.get("name") or "").strip()
                if not sku or not name:
                    errors.append(f"Řádek {i}: chybí sku nebo name.")
                    continue

                category_id = None
                if (row.get("category_path") or "").strip():
                    category_id = resolve_category_path(cur, row["category_path"], cat_cache)
                elif (row.get("category_id") or "").strip():
                    category_id = to_int(row.get("category_id"))

                # Jen sloupce skutecne pritomne v hlavicce CSV se pouziji
                # pri UPDATE - chybejici sloupec = "nemenit", ne "vynulovat".
                update_values = {}
                if has_category_col:
                    update_values["category_id"] = category_id
                if "description" in present:
                    update_values["description"] = (row.get("description") or "").strip() or None
                if "unit" in present:
                    update_values["unit"] = (row.get("unit") or "ks").strip() or "ks"
                if "price_czk_placeholder" in present:
                    update_values["price_czk_placeholder"] = to_float(row.get("price_czk_placeholder"))
                if "weight_g" in present:
                    update_values["weight_g"] = to_float(row.get("weight_g"))
                if "min_stock" in present:
                    update_values["min_stock"] = to_int(row.get("min_stock"))
                if "max_stock" in present:
                    update_values["max_stock"] = to_int(row.get("max_stock"))
                # Robert 2026-07-28 (po dotazu na Zaruku): puvodne CSV
                # export/import zahrnoval jen zakladni pole, chybelo 8
                # sloupcu spravovanych i pres Nastaveni/skladovou kartu.
                if "manufacturer" in present:
                    update_values["manufacturer"] = (row.get("manufacturer") or "").strip() or None
                if "supplier_name" in present:
                    update_values["supplier_name"] = (row.get("supplier_name") or "").strip() or None
                if "ean" in present:
                    update_values["ean"] = (row.get("ean") or "").strip() or None
                if "warranty" in present:
                    update_values["warranty"] = (row.get("warranty") or "").strip() or None
                if "category_path_shoptet" in present:
                    update_values["category_path"] = (row.get("category_path_shoptet") or "").strip() or None
                if "availability_text" in present:
                    update_values["availability_text"] = (row.get("availability_text") or "").strip() or None
                if "alternative_codes" in present:
                    codes = [c.strip() for c in (row.get("alternative_codes") or "").split(",") if c.strip()]
                    update_values["alternative_product_codes"] = json.dumps(codes) if codes else None
                if "related_codes" in present:
                    codes = [c.strip() for c in (row.get("related_codes") or "").split(",") if c.strip()]
                    update_values["related_product_codes"] = json.dumps(codes) if codes else None

                cur.execute("SELECT id FROM shop_products WHERE sku=%s", (sku,))
                existing = cur.fetchone()
                if existing:
                    set_sql = ", ".join(f"{k}=%s" for k in update_values) + (", " if update_values else "") + "name=%s"
                    cur.execute(
                        f"UPDATE shop_products SET {set_sql} WHERE id=%s",
                        list(update_values.values()) + [name, existing["id"]],
                    )
                    updated += 1
                else:
                    # Novy produkt - pro chybejici sloupce pouzij rozumne vychozi
                    # hodnoty (unit "ks", zbytek NULL), zadna existujici hodnota
                    # tu neni, takze neni co prepisovat.
                    cur.execute(
                        """INSERT INTO shop_products
                           (category_id, sku, name, slug, description, unit, price_czk_placeholder, weight_g,
                            min_stock, max_stock, active, manufacturer, supplier_name, ean, warranty,
                            category_path, availability_text, alternative_product_codes, related_product_codes)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (update_values.get("category_id"), sku, name, _product_slug_for_name(cur, name),
                         update_values.get("description"), update_values.get("unit", "ks"),
                         update_values.get("price_czk_placeholder"), update_values.get("weight_g"),
                         update_values.get("min_stock"), update_values.get("max_stock"),
                         update_values.get("manufacturer"), update_values.get("supplier_name"),
                         update_values.get("ean"), update_values.get("warranty"),
                         update_values.get("category_path"), update_values.get("availability_text"),
                         update_values.get("alternative_product_codes"), update_values.get("related_product_codes")),
                    )
                    created += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "import", "shop_product", None,
              f"CSV import: {created} nových, {updated} aktualizováno, {len(errors)} chyb")
    return jsonify({"status": "ok", "created": created, "updated": updated, "errors": errors})


# --- Skladove pohyby (prijemky/vydejky) + skladova karta (Robert
# 2026-07-25: "začni rozšiřovat možnosti skladového systému, přijemky,
# vydejky, skladové karty" - inspirace strukturou ST_Transaction ze
# skladapp/inventory/models.py, ale zjednodusene: bez fyzickych
# skladu/polic/HMI, jen produkt + typ pohybu + mnozstvi + volitelna cena/
# poznamka/cislo dokladu. shop_products.stock_qty je bezici stav zasoby,
# udrzovany transakcne pri kazdem zapisu pohybu; shop_stock_movements je
# auditni historie = "skladova karta" produktu.
@app.get("/api/shop/stock/movements")
@require_permission("sklad_pohyby", "zobrazit")
def shop_stock_movements_list():
    # Dva rezimy (Robert 2026-07-25: "je potřeba je mít i jako oddělenou
    # kategorii kde se budou filtrovat" - samostatna zalozka Skladove
    # pohyby v adminu, vedle puvodnich rychlych tlacitek u produktu):
    #  - ?product_id=X (bez mode) - puvodni "skladova karta" jednoho
    #    produktu, beze zmeny kvuli zpetne kompatibilite s existujicim
    #    Karta modalem.
    #  - ?mode=list - seznam VSECH pohybu napric produkty s volitelnymi
    #    filtry (product_id, movement_type, q - hledani v nazvu/SKU/
    #    dokladu/poznamce, date_from, date_to).
    if request.args.get("mode") != "list":
        product_id = request.args.get("product_id", type=int)
        if not product_id:
            return jsonify({"error": "Chybí product_id."}), 400
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                # Robert (task #68): "zobraz nova Shoptet pole na skladove
                # karte" - manufacturer/supplier_name/warranty/ean/
                # category_path/availability_text/alternative_product_codes/
                # related_product_codes/has_variants/variant_count pribyly
                # importem katalogu Shoptet (viz sql/2026-07-26_shoptet_import.sql),
                # doteď se nikde v API nevracely.
                cur.execute("""
                    SELECT id, name, sku, slug, unit, stock_qty, manufacturer, supplier_name, warranty, ean,
                           category_path, availability_text, alternative_product_codes,
                           related_product_codes, has_variants, variant_count,
                           fbx_original_name, fbx_uploaded_at, glb_file, visible_in_scene,
                           price_source_url, price_last_refreshed_at, color_hex, is_board_material,
                           board_sheet_width_mm, board_sheet_height_mm, cutting_material_key,
                           cfg_dily_id, length_mm, width_mm, height_mm,
                           price_visible_default, hover_show_price, hover_show_availability,
                           meta_title, meta_description,
                           dealer_discount_percent, sale_price_czk, sale_price_from, sale_price_until,
                           dogus_url, dogus_stock_code, dogus_image_render_url, dogus_image_schema_url,
                           product_specs_json, dogus_matched_at, dogus_list_price_usd, dogus_price_rate_used
                    FROM shop_products WHERE id=%s
                """, (product_id,))
                product = cur.fetchone()
                if not product:
                    return jsonify({"error": "Produkt neexistuje."}), 404
                cur.execute("""
                    SELECT m.id, m.movement_type, m.qty, m.unit_price_czk, m.note, m.document_number,
                           m.created_at, u.name AS user_name, u.email AS user_email
                    FROM shop_stock_movements m LEFT JOIN app_users u ON u.id = m.user_id
                    WHERE m.product_id=%s ORDER BY m.created_at DESC, m.id DESC
                """, (product_id,))
                movements = cur.fetchall()
                cur.execute("""
                    SELECT filename FROM shop_product_images WHERE product_id=%s
                    ORDER BY sort_order, id
                """, (product_id,))
                images = [f"/content-files/gallery/{row['filename']}" for row in cur.fetchall()]
        finally:
            conn.close()
        for m in movements:
            if m.get("created_at"):
                m["created_at"] = m["created_at"].isoformat()
            if m.get("unit_price_czk") is not None:
                m["unit_price_czk"] = float(m["unit_price_czk"])
        for col in ("alternative_product_codes", "related_product_codes"):
            val = product.get(col)
            if isinstance(val, str):
                try:
                    product[col] = json.loads(val)
                except (TypeError, ValueError):
                    product[col] = None
        if product.get("fbx_uploaded_at") is not None:
            product["fbx_uploaded_at"] = product["fbx_uploaded_at"].isoformat()
        if product.get("price_last_refreshed_at") is not None:
            product["price_last_refreshed_at"] = product["price_last_refreshed_at"].isoformat()
        for col in ("sale_price_from", "sale_price_until"):
            if product.get(col) is not None:
                product[col] = product[col].isoformat()
        for col in ("dealer_discount_percent", "sale_price_czk", "dogus_list_price_usd", "dogus_price_rate_used"):
            if product.get(col) is not None:
                product[col] = float(product[col])
        val = product.get("product_specs_json")
        if isinstance(val, str):
            try:
                product["product_specs_json"] = json.loads(val)
            except (TypeError, ValueError):
                product["product_specs_json"] = None
        if product.get("dogus_matched_at") is not None:
            product["dogus_matched_at"] = product["dogus_matched_at"].isoformat()
        product["is_board_material"] = bool(product.get("is_board_material"))
        product["images"] = images
        return jsonify({"product": product, "movements": movements})

    # --- mode=list ---
    product_id = request.args.get("product_id", type=int)
    movement_type = request.args.get("type")
    q = (request.args.get("q") or "").strip()
    date_from = (request.args.get("date_from") or "").strip()
    date_to = (request.args.get("date_to") or "").strip()

    where, params = [], []
    if product_id:
        where.append("m.product_id=%s")
        params.append(product_id)
    if movement_type in ("receipt", "issue"):
        where.append("m.movement_type=%s")
        params.append(movement_type)
    if q:
        where.append("(p.name LIKE %s OR p.sku LIKE %s OR m.document_number LIKE %s OR m.note LIKE %s)")
        params.extend([f"%{q}%"] * 4)
    if date_from:
        where.append("m.created_at >= %s")
        params.append(date_from + " 00:00:00")
    if date_to:
        where.append("m.created_at <= %s")
        params.append(date_to + " 23:59:59")

    base_sql = """
        SELECT m.id, m.product_id, p.name AS product_name, p.sku AS product_sku, p.unit AS product_unit,
               m.movement_type, m.qty, m.unit_price_czk, m.note, m.document_number, m.created_at,
               u.name AS user_name, u.email AS user_email
        FROM shop_stock_movements m
        JOIN shop_products p ON p.id = m.product_id
        LEFT JOIN app_users u ON u.id = m.user_id
    """
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    # Stránkování (task #78/85) - nahrazuje puvodni pevny LIMIT 500 bez
    # celkoveho poctu/dalsich stranek.
    page, page_size = get_pagination_args(default_page_size=50)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            movements, total = paginated_query(cur, base_sql, where_sql, params,
                                                " ORDER BY m.created_at DESC, m.id DESC", page, page_size)
    finally:
        conn.close()
    for m in movements:
        if m.get("created_at"):
            m["created_at"] = m["created_at"].isoformat()
        if m.get("unit_price_czk") is not None:
            m["unit_price_czk"] = float(m["unit_price_czk"])
    resp = {"movements": movements}
    if page_size:
        resp.update(total=total, page=page, page_size=page_size)
    return jsonify(resp)


@app.post("/api/shop/stock/movements")
@require_permission("sklad_pohyby", "vytvorit")
def shop_stock_movements_create():
    body = request.get_json(silent=True) or {}
    product_id = body.get("product_id")
    movement_type = body.get("movement_type")
    qty = body.get("qty")
    if not product_id or movement_type not in ("receipt", "issue"):
        return jsonify({"error": "Vyplň produkt a typ pohybu (příjem/výdej)."}), 400
    try:
        qty = int(qty)
    except (TypeError, ValueError):
        qty = 0
    if qty <= 0:
        return jsonify({"error": "Množství musí být kladné číslo."}), 400
    unit_price_czk = body.get("unit_price_czk")
    note = (body.get("note") or "").strip() or None
    document_number = (body.get("document_number") or "").strip() or None
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, stock_qty FROM shop_products WHERE id=%s FOR UPDATE", (product_id,))
            product = cur.fetchone()
            if not product:
                conn.rollback()
                return jsonify({"error": "Produkt neexistuje."}), 404
            if movement_type == "issue" and product["stock_qty"] < qty:
                conn.rollback()
                return jsonify({"error": f"Nedostatek zásoby (aktuální stav: {product['stock_qty']})."}), 400
            delta = qty if movement_type == "receipt" else -qty
            cur.execute("UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s", (delta, product_id))
            cur.execute(
                """INSERT INTO shop_stock_movements
                   (product_id, movement_type, qty, unit_price_czk, note, document_number, user_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (product_id, movement_type, qty, unit_price_czk, note, document_number, user["id"]),
            )
            new_id = cur.lastrowid
            cur.execute("SELECT stock_qty FROM shop_products WHERE id=%s", (product_id,))
            new_stock = cur.fetchone()["stock_qty"]
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], movement_type, "shop_product", product_id,
              f"{'+' if movement_type == 'receipt' else '-'}{qty} (doklad: {document_number or '-'})")
    released, needs_review = [], []
    if movement_type == "receipt":
        # Robert 2026-07-31: "automaticky pri naskladneni" - prijem zbozi
        # muze odblokovat objednavky cekajici ve stavu "ceka_na_zbozi".
        import orders as _orders
        released, needs_review = _orders.try_release_waiting_orders()
    return jsonify({"status": "ok", "id": new_id, "stock_qty": new_stock,
                    "released_orders": released, "needs_manual_review_orders": needs_review})


def reverse_and_delete_stock_movements(cur, ids):
    """
    Sdilena logika mazani 1..N skladovych pohybu i s vracenim jejich ucinku
    na shop_products.stock_qty (presny opak delty pouzite pri vytvoreni
    pohybu) - pouziva ji jak shop_stock_movements_bulk_delete nize, tak
    documents._unlink_and_delete_documents (Robert 2026-08-01: "pokud admin
    zadá smazat doklad, smaže se i se všemi navázanými pohyby").
    Kazdy pohyb se zpracovava samostatne v cyklu (jeden problematicky radek
    nezastavi zbytek davky, jen skonci v "failed"). Pokud by vraceni ucinku
    poslalo stock_qty do zaporu, dany pohyb se NESMAZE, zbytek davky
    pokracuje dal. Vraci (deleted_ids, failed) - volajici si po commitu sam
    dodela gallery_items cleanup + audit log (viz oba callery).
    """
    deleted_ids = []
    failed = []
    for mv_id in ids:
        cur.execute(
            "SELECT id, product_id, movement_type, qty FROM shop_stock_movements WHERE id=%s",
            (mv_id,),
        )
        mv = cur.fetchone()
        if not mv:
            failed.append({"id": mv_id, "error": "Pohyb neexistuje."})
            continue
        cur.execute("SELECT id, stock_qty FROM shop_products WHERE id=%s FOR UPDATE", (mv["product_id"],))
        product = cur.fetchone()
        if not product:
            failed.append({"id": mv_id, "error": "Produkt pohybu neexistuje."})
            continue
        reversal = -mv["qty"] if mv["movement_type"] == "receipt" else mv["qty"]
        new_stock = product["stock_qty"] + reversal
        if new_stock < 0:
            failed.append({
                "id": mv_id,
                "error": f"Smazání by snížilo sklad do záporu (aktuální stav: {product['stock_qty']}, "
                         f"po smazání: {new_stock}).",
            })
            continue
        cur.execute("UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s",
                    (reversal, mv["product_id"]))
        cur.execute("DELETE FROM shop_stock_movements WHERE id=%s", (mv_id,))
        deleted_ids.append(mv_id)
    return deleted_ids, failed


@app.post("/api/shop/stock/movements/bulk-delete")
@require_permission("sklad_pohyby", "smazat")
def shop_stock_movements_bulk_delete():
    """Hromadne smazani vybranych skladovych pohybu (Robert: "mazat musí být
    všude !!!" - 2026-07-26), viz reverse_and_delete_stock_movements() vyse
    pro vysvetleni, proc nejde pouzit sdileny bulk_delete()/holy DELETE."""
    body = request.get_json(silent=True) or {}
    ids, err = parse_bulk_ids(body)
    if err:
        return err
    user = current_user()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            deleted_ids, failed = reverse_and_delete_stock_movements(cur, ids)
        conn.commit()
    finally:
        conn.close()
    for mv_id in deleted_ids:
        gallery_items.delete_items_for_owner("stock_movement", mv_id)
    log_audit(user["id"], "bulk_delete", "stock_movement", None,
              f"{len(deleted_ids)} skladových pohybů smazáno (stav skladu vrácen zpět)"
              + (f", {len(failed)} přeskočeno" if failed else ""))
    return jsonify({"status": "ok", "deleted": len(deleted_ids), "failed": failed})


@app.post("/api/shop/stock/test-receipts")
@require_permission("sklad_pohyby", "vytvorit")
def shop_stock_generate_test_receipts():
    # Generator testovacich prijemek (Robert 2026-07-25: "převezmi sem ze
    # skladapp i testovací přijmy se stejnou logikou" -> po ukazani, ze
    # skladapp verze je provazana s fyzickymi regaly/vahovou kapacitou
    # police (ktere v konfiguratoru vubec neexistuji), upresneno pres
    # AskUserQuestion na jednoduchou variantu BEZ regalu: vygeneruje
    # zadany pocet nahodnych prijmovych pohybu na nahodne (nearchivovane)
    # produkty v nahodnem mnozstvi 1-200 ks - stejny rozsah mnozstvi jako
    # skladapp/inventory/views.py generate_test_receipts, jen bez jeho
    # skladove/vahove kapacitni logiky. Jen role admin (stejne jako ve
    # skladapp - "generator prijmu jen pro admina", oprava 2026-07-23 tam).
    # Kazdy radek jde pres stejnou cestu jako rucni prijem (UPDATE
    # stock_qty + INSERT do shop_stock_movements), aby se choval identicky
    # a byl videt ve Skladove karte i v Audit logu.
    body = request.get_json(silent=True) or {}
    try:
        count = int(body.get("count", 50))
    except (TypeError, ValueError):
        count = 50
    count = max(1, min(count, 200))
    try:
        item_pct = int(body.get("item_pct", 100))
    except (TypeError, ValueError):
        item_pct = 100
    item_pct = max(1, min(100, item_pct))

    user = current_user()
    # Robert 2026-08-08 ("toto nech vidí jen admin"): generator uz mel
    # tenhle zamer v komentari vyse ("Jen role admin"), ale nikdy nebyl
    # skutecne vynucen - @require_permission("sklad_karty", "vytvorit")
    # pusti kohokoli s tim opravnenim, ne jen admina. Skryti tlacitka v
    # adminu (viz #testDataGenSection) resi jen UI, tenhle check resi
    # samotne API.
    if user["role"] != "admin":
        return jsonify({"error": "Generátor testovacích dat je jen pro administrátory."}), 403
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM shop_products WHERE is_archived=0")
            all_ids = [r["id"] for r in cur.fetchall()]
            if not all_ids:
                return jsonify({"error": "Nejsou žádné (nearchivované) produkty ke generování."}), 400
            if item_pct < 100:
                sample_size = max(1, round(len(all_ids) * item_pct / 100))
                pool_ids = random.sample(all_ids, sample_size)
            else:
                pool_ids = all_ids

            created = 0
            for _ in range(count):
                product_id = random.choice(pool_ids)
                qty = random.randint(1, 200)
                cur.execute("UPDATE shop_products SET stock_qty = stock_qty + %s WHERE id=%s", (qty, product_id))
                cur.execute(
                    """INSERT INTO shop_stock_movements
                       (product_id, movement_type, qty, note, user_id)
                       VALUES (%s,'receipt',%s,%s,%s)""",
                    (product_id, qty, "Testovací příjem (generátor)", user["id"]),
                )
                created += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "generate_test_data", "shop_product", None,
              f"{created} testovacích příjemek vygenerováno (item_pct={item_pct})")
    return jsonify({"status": "ok", "created": created})


@app.post("/api/shop/stock/test-issues")
@require_permission("sklad_pohyby", "vytvorit")
def shop_stock_generate_test_issues():
    # Generator testovacich vydejek (Robert: "pridej tlacitko vygenerovat
    # vydeje ve stejnem duchu jako jsou prijmy") - zrcadli generator
    # prijemek vyse, ale VYDEJ nemuze prekrocit aktualni sklad (stejne
    # omezeni jako u rucniho vydeje - "Nedostatek zasoby", viz
    # shop_stock_movements_create). Vybira proto jen z produktu se
    # stock_qty>0 a mnozstvi omezuje na min(nahodne 1-200, aktualni
    # stav) - stav si navic PRUBEZNE odecita LOKALNE behem generovani
    # (ne jen v DB), aby stejny produkt vybrany vickrat po sobe za
    # sebou nikdy nesel do zaporu.
    body = request.get_json(silent=True) or {}
    try:
        count = int(body.get("count", 50))
    except (TypeError, ValueError):
        count = 50
    count = max(1, min(count, 200))
    try:
        item_pct = int(body.get("item_pct", 100))
    except (TypeError, ValueError):
        item_pct = 100
    item_pct = max(1, min(100, item_pct))

    user = current_user()
    # Robert 2026-08-08 ("toto nech vidí jen admin") - stejny duvod/vzor
    # jako u shop_stock_generate_test_receipts vyse.
    if user["role"] != "admin":
        return jsonify({"error": "Generátor testovacích dat je jen pro administrátory."}), 403
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, stock_qty FROM shop_products WHERE is_archived=0 AND stock_qty > 0")
            rows = cur.fetchall()
            if not rows:
                return jsonify({"error": "Žádný (nearchivovaný) produkt nemá skladem, ze kterého by šlo vydat."}), 400
            stock_by_id = {r["id"]: r["stock_qty"] for r in rows}
            pool_ids = list(stock_by_id.keys())
            if item_pct < 100:
                sample_size = max(1, round(len(pool_ids) * item_pct / 100))
                pool_ids = random.sample(pool_ids, sample_size)

            created = 0
            for _ in range(count):
                available_ids = [pid for pid in pool_ids if stock_by_id[pid] > 0]
                if not available_ids:
                    break
                product_id = random.choice(available_ids)
                qty = random.randint(1, min(200, stock_by_id[product_id]))
                stock_by_id[product_id] -= qty
                cur.execute("UPDATE shop_products SET stock_qty = stock_qty - %s WHERE id=%s", (qty, product_id))
                cur.execute(
                    """INSERT INTO shop_stock_movements
                       (product_id, movement_type, qty, note, user_id)
                       VALUES (%s,'issue',%s,%s,%s)""",
                    (product_id, qty, "Testovací výdej (generátor)", user["id"]),
                )
                created += 1
        conn.commit()
    finally:
        conn.close()
    log_audit(user["id"], "generate_test_data", "shop_product", None,
              f"{created} testovacích výdejek vygenerováno (item_pct={item_pct})")
    result = {"status": "ok", "created": created}
    if created < count:
        result["note"] = f"Zastaveno po {created} z {count} - vybraným produktům došel sklad."
    return jsonify(result)


# ==================== VYBER GLB DO 3D SCENY ====================
# Robert 2026-08-11: "priprav mi klikaci tabulku prislusenstvi a spojek
# 'obrazky' ktere ma hotovy glb, ty co znacim muzeme nasypat do sceny" -
# obrazkova mrizka (webapp/glb-vyber.html) vsech produktu z vetvi
# Prislusenstvi profilu (150) a Spojovaci prvky (152), ktere maji
# prevedeny .glb model. Kliknuti prepina visible_in_scene - presne ten
# priznak, kterym se produkt dostava do katalogu 3D sceny (viz
# app.py::/api/parts, podminka visible_in_scene=1 AND glb_file).
@app.get("/api/admin/scene-glb-picker")
@require_permission("sklad_karty", "zobrazit")
def scene_glb_picker_list():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                WITH RECURSIVE branch AS (
                    SELECT id FROM content_categories WHERE id IN (150, 152)
                    UNION ALL
                    SELECT c.id FROM content_categories c JOIN branch b ON c.parent_id = b.id
                )
                SELECT p.id, p.sku, p.name, p.visible_in_scene, p.glb_file,
                       c.name AS category_name,
                       (SELECT filename FROM shop_product_images i
                        WHERE i.product_id = p.id ORDER BY i.sort_order, i.id LIMIT 1) AS image_filename
                FROM shop_products p
                LEFT JOIN content_categories c ON c.id = p.category_id
                WHERE p.active=1 AND p.is_archived=0
                  AND p.glb_file IS NOT NULL AND p.glb_file <> ''
                  AND p.category_id IN (SELECT id FROM branch)
                ORDER BY c.name, p.name
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    return jsonify({"products": [{
        "id": r["id"], "sku": r["sku"], "name": r["name"],
        "category": r["category_name"] or "(bez kategorie)",
        "visible_in_scene": bool(r["visible_in_scene"]),
        "image_url": f"/content-files/gallery/{r['image_filename']}" if r["image_filename"] else None,
    } for r in rows]})


@app.post("/api/admin/scene-glb-picker/<int:product_id>")
@require_permission("sklad_karty", "upravit")
def scene_glb_picker_toggle(product_id):
    body = request.get_json(force=True, silent=True) or {}
    visible = 1 if body.get("visible") else 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # jen produkty s glb - bez modelu nema priznak ve scene smysl.
            # Existence se overuje SELECTem, ne pres UPDATE rowcount -
            # ten je 0 i pri zapisu stejne hodnoty (dvojklik by falesne
            # vratil 404 a UI by omylem vratilo stav zpet).
            cur.execute(
                "SELECT id FROM shop_products "
                "WHERE id=%s AND glb_file IS NOT NULL AND glb_file <> ''",
                (product_id,),
            )
            if not cur.fetchone():
                return jsonify({"error": "Produkt neexistuje nebo nemá GLB model."}), 404
            cur.execute(
                "UPDATE shop_products SET visible_in_scene=%s WHERE id=%s",
                (visible, product_id),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "scene_visibility", "shop_product", product_id,
              f"visible_in_scene={visible} (glb-vyber.html)")
    return jsonify({"status": "ok", "visible_in_scene": bool(visible)})
