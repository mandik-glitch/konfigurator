"""
Duplikace skladove karty / produktu (`shop_products`) - bot5, 2026-09-30
(Robert pres bot3: "potrebujeme mit moznost duplikovat/kopirovat skladovou
polozku, produkt").

Cisty modul BEZ Flask/app zavislosti (stejny duvod jako `cutting_algo.py`):
pracuje nad obycejnym DB kurzorem (DictCursor), takze se da otestovat v
docasnych tabulkach bez zapisu do ostrych dat - viz
`scripts/2026-09-30_duplikace_produktu_testy/`. Endpoint je v `products.py`
(`shop_product_duplicate`) a jen sem preda kurzor, funkci na slug a cesty k
adresarum se soubory. COMMIT/ROLLBACK DELA VOLAJICI (tady se nikdy nekomituje).

CO SE KOPIROVAT NEMA (proc) - jediny zdroj pravdy je tento soubor:
  * shop_products: `RESET_NULL` a `FORCE_VALUE` nize. Vse ostatni se kopiruje
    (i sloupce, ktere pribudou pozdeji - "kopirovat vse, vyjmenovat vyjimky").
  * souvisejici tabulky: `COPIED_TABLES` (kopiruji se) a `SKIPPED_TABLES`
    (nekopiruji se, vcetne duvodu). QA kontrola
    `product_duplicate_unclassified_table` (api/qa_checks.py) hlasi tabulku,
    ktera na produkt odkazuje a neni ani v jedne - aby nova tabulka nezustala
    v kopii tise chybet.

SOUBORY: fotogalerie a dokumenty produktu se pri smazani (polozky i produktu)
mazou z disku (`gallery_items.delete_items_for_owner`, smazani dokumentu) - kopie
proto dostane VLASTNI fyzicke soubory, jinak by smazani kopie (nebo originalu)
druhemu vzalo obrazky. Obrazky z importu (`shop_product_images`) a obrazky
pouziti (`product_usage_images`) nema zadny kod jak smazat, sdili se soubory.
"""
import json
import os
import re
import shutil

import pymysql


class ProductNotFound(LookupError):
    """Zdrojovy produkt neexistuje."""


# --- shop_products: co se v kopii NEDEDI --------------------------------------
# Identita a puvod z importu. Unikatni sloupce (shoptet_*, vandr_stored_model_uuid)
# by kopii srazily s originalem; EAN identifikuje fyzicke zbozi (dva produkty se
# stejnym EAN rozbijeji feedy a porovnavace).
RESET_NULL = (
    "shoptet_id", "shoptet_code", "shoptet_guid", "shoptet_imported_at",
    "shoptet_updated_at", "shoptet_stock_hint", "ean",
    # zalozeno automatem podle typologie (card_auto_link) - rucni kopie neni "auto"
    "zalozeno_automaticky_typologie_id",
    # kopie jeste nebyla aktivovana
    "activated_at",
    # vazba na dil konfiguratoru: kod ji cte jako 1:1 (admin_profily.py, LEFT JOIN
    # "zadny cfg_dily_id nema vic nez 1 navazany produkt"), druha karta by ji rozbila
    "cfg_dily_id",
    # 3D model a jeho stav: soubory patri originalu, kopie si model nahraje sama
    "glb_file", "thumbnail_file", "fbx_original_name", "fbx_uploaded_at",
    # stav a identita Vandr pipeline (razitka, konverze, rendery) - vazane na konkretni model
    "vandr_razitka_json", "vandr_razitka_glb_otisk", "vandr_razitka_hotovo_at",
    "vandr_razitka_chyba_otisk", "vandr_konverze_chyba_fbx_otisk",
    "vandr_render_razitka_otisk", "vandr_stored_model_uuid",
    "vandr_predni_azimut_deg", "vandr_hlavni_prurez_mm",
)

# Pevna hodnota v kopii (neni to rucni prepnuti `active` botem - je to chovani
# funkce: rozdelana duplicitni karta se nesmi dostat na web sama).
FORCE_VALUE = {
    "stock_qty": 0,            # skladovy stav a pohyby se nekopiruji
    "active": 0,
    "is_archived": 0,
    "visible_in_scene": 0,     # kopie bez 3D modelu nema byt v katalogu sceny
    # priznaky z importu ze Shoptetu (varianty/sety); data k nim kopie nema
    "has_variants": 0, "variant_count": 0, "has_set_items": 0,
}

# Sloupce, ktere se nekopiruji nikdy (PK a razitko vzniku - vznikne samo).
_SKIP_COLUMNS = ("id", "created_at")
_CHILD_SKIP_COLS = ("id", "created_at")

# --- souvisejici tabulky ------------------------------------------------------
COPIED_TABLES = {
    "shop_product_categories": "dalsi kategorie produktu",
    "shop_product_images": "obrazky z importu ze Shoptetu (soubory se sdili)",
    "product_usage_images": "obrazky pouziti z katalogu (soubory se sdili)",
    "shop_product_documents": "souvisejici dokumenty (soubory se kopiruji)",
    "content_gallery_items": "fotogalerie produktu, owner_type='product' (soubory se kopiruji)",
}
SKIPPED_TABLES = {
    "product_markups": "zakaznicka oznaceni na obrazku (kontaktni e-mail, telefon, IP, vazba na lead) - osobni udaje",
    "product_assemblies": "sestavy drzi vlastni ID a kod_sestavy (pravidlo 45), kopie karty neni sestava",
    "product_turntable_frames": "otocne rendery patri konkretni sestave/modelu",
    "product_turntable_selected_views": "vyber pohledu otocky patri konkretni sestave/modelu",
    "vandr_fbx_queue": "fronta prevodu FBX",
    "render_hdri_test_requests": "zadosti o testovaci rendery",
    "attach_learning_log": "zaznamy uceni napojovani dilu ve scene",
    "komponenty_varianty": "rozmerove varianty komponent 3D sestav vazane na konkretni kartu",
    "product_views": "statistika zobrazeni",
    "product_views_daily": "statistika zobrazeni",
    "shop_cart_items": "kosiky - provozni data",
    "shop_order_items": "objednavky - provozni data",
    "shop_purchase_order_items": "nakupni objednavky - provozni data",
    "shop_reorder_items": "doobjednani - provozni data",
    "shop_stock_movements": "skladovy stav a pohyby (kopie zacina na 0)",
    "shop_product_redirects": "301 presmerovani drzi puvodni URL",
    "shop_product_coupons": "kupony maji unikatni kod a patri konkretnimu produktu",
    "dealer_clicks": "proklikove zaznamy dealerskeho programu (kam navstevnik vstoupil, ip_hash) - provozni data, kopie karty je nema",
    "miniweb_products": "polozka katalogu mini-shopu (verejny kod, texty po jazycich, odkaz na kartu sestavy pro konfigurator) - kopie karty mini-shopovou polozku nezaklada",
}

_SKU_MAX = 150
_NAME_MAX = 200
_SKU_COPY_RE = re.compile(r"-kopie(?:-\d+)?$")
_NAME_COPY_RE = re.compile(r" \(kopie(?: \d+)?\)$")
# nazev ulozeneho souboru: <prefix>-<id>_<zaklad>-<8 hex>.<pripona> (gallery_items, dokumenty)
_STORED_NAME_RE = re.compile(r"^[a-z_]+-\d+_(?P<base>.+)-[0-9a-f]{8}\.(?P<ext>[A-Za-z0-9]+)$")
_MAX_INSERT_TRIES = 6


def _fit(base, suffix, maxlen):
    return base[:maxlen - len(suffix)] + suffix


def _copy_sku(base, n):
    return _fit(base, "-kopie" if n == 1 else f"-kopie-{n}", _SKU_MAX)


def _copy_name(base, n):
    return _fit(base, " (kopie)" if n == 1 else f" (kopie {n})", _NAME_MAX)


def _db_value(v):
    # JSON sloupec muze prijit jako dict/list - zpet do textu, jinak pymysql spadne
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _columns(cur, table):
    cur.execute(
        "SELECT COLUMN_NAME, IS_NULLABLE, EXTRA FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY ORDINAL_POSITION", (table,))
    return cur.fetchall()


def _unique_single_columns(cur, table):
    """Sloupce s jednosloupcovym UNIQUE indexem (krome PRIMARY)."""
    cur.execute(
        "SELECT INDEX_NAME, COLUMN_NAME FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND NON_UNIQUE=0 AND INDEX_NAME<>'PRIMARY'",
        (table,))
    by_index = {}
    for r in cur.fetchall():
        by_index.setdefault(r["INDEX_NAME"], []).append(r["COLUMN_NAME"])
    return {cols[0] for cols in by_index.values() if len(cols) == 1}


def pick_identity(cur, src_sku, src_name, slug_for_name, start=1):
    """Vybere volne SKU (`<sku>-kopie`, `-kopie-2`...), odpovidajici nazev a slug.
    Kopie kopie se nezretezuje (`X-kopie` -> `X-kopie-2`, ne `X-kopie-kopie`)."""
    base_sku = _SKU_COPY_RE.sub("", src_sku)
    base_name = _NAME_COPY_RE.sub("", src_name)
    n = start
    while True:
        sku = _copy_sku(base_sku, n)
        cur.execute("SELECT 1 FROM shop_products WHERE sku=%s", (sku,))
        if not cur.fetchone():
            break
        n += 1
        if n > 1000:
            raise RuntimeError("Nepodarilo se najit volne SKU pro kopii.")
    name = _copy_name(base_name, n)
    return n, sku, name, slug_for_name(cur, name)


def remove_files(paths):
    """Best-effort uklid souboru vytvorenych kopii (pri selhani transakce)."""
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def _new_stored_name(old_name, new_id):
    m = _STORED_NAME_RE.match(old_name)
    if m:
        base, ext = m.group("base"), m.group("ext")
    else:
        stem, dot, ext = old_name.rpartition(".")
        if not dot:
            stem, ext = old_name, ""
        base = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-")[:60] or "soubor"
    stored = f"product-{new_id}_{base}-{os.urandom(4).hex()}"
    return f"{stored}.{ext}" if ext else stored


def _copy_file(src_dir, dst_dir, old_name, new_id, created):
    """Zkopiruje soubor pod nove jmeno, vrati nove jmeno. None = zdroj chybi
    (radek se pak nekopiruje, at nevznikne odkaz na neexistujici soubor)."""
    if not old_name or os.path.basename(old_name) != old_name:
        return None
    src = os.path.join(src_dir, old_name)
    if not os.path.isfile(src):
        return None
    new_name = _new_stored_name(old_name, new_id)
    dst = os.path.join(dst_dir, new_name)
    shutil.copyfile(src, dst)
    created.append(dst)
    return new_name


def _copy_child_rows(cur, table, fk_col, source_id, new_id, extra_where="", order_sql="", per_row=None):
    """Zkopiruje radky `table` s fk_col=source_id na fk_col=new_id (vsechny sloupce
    krome id/created_at, tedy i budouci). per_row(dict)->dict|None muze radek upravit
    nebo vyradit. Vraci (zkopirovano, vyrazeno)."""
    cur.execute(f"SELECT * FROM `{table}` WHERE `{fk_col}`=%s {extra_where} {order_sql}", (source_id,))
    copied = skipped = 0
    for row in cur.fetchall():
        new = {k: _db_value(v) for k, v in row.items() if k not in _CHILD_SKIP_COLS}
        new[fk_col] = new_id
        if per_row is not None:
            new = per_row(new)
            if new is None:
                skipped += 1
                continue
        cols = list(new)
        cur.execute(
            f"INSERT INTO `{table}` ({','.join('`%s`' % c for c in cols)}) "
            f"VALUES ({','.join(['%s'] * len(cols))})",
            [new[c] for c in cols])
        copied += 1
    return copied, skipped


def duplicate_product(cur, source_id, *, slug_for_name, created_by=None, created_role=None,
                      gallery_dir, docs_dir, gallery_dst_dir=None, docs_dst_dir=None):
    """Vytvori NEAKTIVNI kopii produktu `source_id` a vrati dict s novym id, SKU,
    nazvem, slugem, pocty zkopirovanych radku a `created_files` (soubory vytvorene
    na disku - pri selhani commitu je volajici smaze pres remove_files).

    Nekomituje. Pri chybe uvnitr sam smaze soubory, ktere uz vytvoril, a vyjimku
    propusti dal (volajici dela rollback). Vyhodi ProductNotFound."""
    gallery_dst_dir = gallery_dst_dir or gallery_dir
    docs_dst_dir = docs_dst_dir or docs_dir

    cur.execute("SELECT * FROM shop_products WHERE id=%s", (source_id,))
    src = cur.fetchone()
    if not src:
        raise ProductNotFound(source_id)

    unique_cols = _unique_single_columns(cur, "shop_products")
    insert_cols, base_values = [], {}
    for col in _columns(cur, "shop_products"):
        name = col["COLUMN_NAME"]
        if name in _SKIP_COLUMNS or "GENERATED" in (col["EXTRA"] or "").replace("DEFAULT_GENERATED", ""):
            continue
        nullable = col["IS_NULLABLE"] == "YES"
        if name in FORCE_VALUE:
            value = FORCE_VALUE[name]
        elif name in RESET_NULL:
            if not nullable:
                continue                      # NOT NULL: nech pusobit vychozi hodnotu tabulky
            value = None
        elif name in unique_cols and name not in ("sku", "slug"):
            # novy unikatni sloupec, o kterem tenhle modul nevi: NULL nekoliduje;
            # kdyz nejde NULL, radeji hlasite selhat nez vyrobit kolizi
            if not nullable:
                raise RuntimeError(f"Duplikace: unikatni sloupec shop_products.{name} neni osetren.")
            value = None
        else:
            value = _db_value(src[name])
        insert_cols.append(name)
        base_values[name] = value

    sql = ("INSERT INTO shop_products (" + ",".join(f"`{c}`" for c in insert_cols) + ") VALUES ("
           + ",".join(["%s"] * len(insert_cols)) + ")")

    created = []
    try:
        n = 1
        for attempt in range(_MAX_INSERT_TRIES):
            n, sku, new_name, slug = pick_identity(cur, src["sku"], src["name"], slug_for_name, start=n)
            values = dict(base_values, sku=sku, name=new_name, slug=slug)
            try:
                cur.execute(sql, [values[c] for c in insert_cols])
                break
            except pymysql.err.IntegrityError as e:
                # 1062 = duplicita: nekdo si mezi vyberem SKU/slugu a INSERTem vzal stejne
                if e.args[0] != 1062 or attempt == _MAX_INSERT_TRIES - 1:
                    raise
                n += 1
        new_id = cur.lastrowid

        categories, _ = _copy_child_rows(cur, "shop_product_categories", "product_id", source_id, new_id)
        images, _ = _copy_child_rows(cur, "shop_product_images", "product_id", source_id, new_id,
                                     order_sql="ORDER BY sort_order, id")
        usage, _ = _copy_child_rows(cur, "product_usage_images", "product_id", source_id, new_id,
                                    order_sql="ORDER BY sort_order, id")

        def doc_row(new):
            if new.get("doc_type") == "youtube":      # filename je ID videa, zadny soubor
                return new
            fn = _copy_file(docs_dir, docs_dst_dir, new.get("filename"), new_id, created)
            if fn is None:
                return None
            new["filename"] = fn
            return new

        def gallery_row(new):
            fn = _copy_file(gallery_dir, gallery_dst_dir, new.get("filename"), new_id, created)
            if fn is None:
                return None
            new["filename"] = fn
            if new.get("audio_filename"):
                new["audio_filename"] = _copy_file(gallery_dir, gallery_dst_dir, new["audio_filename"], new_id, created)
            new["created_by"], new["created_role"] = created_by, created_role
            return new

        documents, docs_missing = _copy_child_rows(
            cur, "shop_product_documents", "product_id", source_id, new_id,
            order_sql="ORDER BY sort_order, id", per_row=doc_row)
        gallery, gallery_missing = _copy_child_rows(
            cur, "content_gallery_items", "owner_id", source_id, new_id,
            extra_where="AND owner_type='product'", order_sql="ORDER BY sort_order, id", per_row=gallery_row)
    except BaseException:
        remove_files(created)
        raise

    return {
        "id": new_id, "sku": sku, "name": new_name, "slug": slug,
        "copied": {"categories": categories, "images": images, "usage_images": usage,
                   "documents": documents, "gallery": gallery},
        "missing_files": docs_missing + gallery_missing,
        "created_files": created,
    }


def unclassified_reference_tables(cur):
    """Tabulky, ktere odkazuji na shop_products (FK nebo sloupec product_id /
    shop_product_id), ale nejsou v COPIED_TABLES ani SKIPPED_TABLES. Pro QA kontrolu."""
    cur.execute(
        "SELECT TABLE_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME<>'shop_products' "
        "AND COLUMN_NAME IN ('product_id','shop_product_id') "
        "UNION "
        "SELECT TABLE_NAME FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='shop_products'")
    known = set(COPIED_TABLES) | set(SKIPPED_TABLES)
    return sorted({r["TABLE_NAME"] for r in cur.fetchall()} - known)
