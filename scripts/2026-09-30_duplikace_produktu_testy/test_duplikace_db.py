#!/opt/konfigurator/api/venv/bin/python
"""Test duplikace produktu (api/product_duplicate.py) nad DOCASNYMI tabulkami.

Nic se nezapisuje do ostrych dat: pro SOUBEZNE spojeni se vytvori TEMPORARY tabulky
se stejnymi nazvy jako ostre (stini je), naplni se kopii jednoho skutecneho produktu
a modul bezi nad nimi. Soubory se kopiruji do docasneho adresare. Na konci se na
NOVEM spojeni overi, ze ostre tabulky ani adresare se nezmenily.

Spusteni (DB prihlaseni pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \
    --working-directory=/opt/konfigurator \
    /opt/konfigurator/api/venv/bin/python3 scripts/2026-09-30_duplikace_produktu_testy/test_duplikace_db.py
Konci kodem 0 jen kdyz VSE prosla.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unicodedata

import pymysql

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api"))
import product_duplicate as pd  # noqa: E402

SRC = 3045            # Uhelnikova spojka 30x30: obrazky, obrazky pouziti, JSON specifikace, Dogus, stock 315
GAL_OWNER = 4925      # produkt s realnou galerii (2 soubory) - radky se presunou na SRC
REAL_GALLERY = "/opt/konfigurator/webapp/content-files/gallery-items"
REAL_DOCS = "/opt/konfigurator/webapp/content-files/product-documents"
TABLES = ["shop_products", "shop_product_categories", "shop_product_images",
          "product_usage_images", "shop_product_documents", "content_gallery_items"]

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def connect():
    return pymysql.connect(
        host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def slug_for_name(cur, name):
    """Stejny kontrakt jako app._product_slug_for_name(cur, name): unikatni slug z nazvu."""
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base = "".join(ch if ch.isalnum() else "-" for ch in base).strip("-") or "produkt"
    cand, n = base, 2
    while True:
        cur.execute("SELECT 1 FROM shop_products WHERE slug=%s", (cand,))
        if not cur.fetchone():
            return cand
        cand, n = f"{base}-{n}", n + 1


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def permanent_state():
    """Stav OSTRYCH tabulek/adresaru na novem spojeni (temp tabulky tam nejsou videt)."""
    c = connect()
    try:
        with c.cursor() as cur:
            st = {}
            for t in TABLES:
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                st[t] = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM shop_products WHERE sku LIKE %s", ("%-kopie%",))
            st["kopie_sku"] = cur.fetchone()["n"]
            # MySQL 8 drzi AUTO_INCREMENT v information_schema v cache (vychozi 24 h) - bez tohohle by
            # porovnani "pred/po" nikdy nic nezachytilo
            cur.execute("SET SESSION information_schema_stats_expiry=0")
            cur.execute("SELECT AUTO_INCREMENT AS ai FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
            st["auto_increment"] = cur.fetchone()["ai"]
    finally:
        c.close()
    st["gallery_soubory"] = len(os.listdir(REAL_GALLERY))
    st["docs_soubory"] = len(os.listdir(REAL_DOCS))
    return st


def setup_temp(cur, tmp_docs_src):
    where = {"shop_products": ("id=%s", SRC), "shop_product_categories": ("product_id=%s", SRC),
             "shop_product_images": ("product_id=%s", SRC), "product_usage_images": ("product_id=%s", SRC),
             "shop_product_documents": ("product_id=%s", SRC),
             "content_gallery_items": ("owner_type='product' AND owner_id=%s", GAL_OWNER)}
    for t in TABLES:
        w, arg = where[t]
        cur.execute(f"CREATE TEMPORARY TABLE `_src_{t}` AS SELECT * FROM `{t}` WHERE {w}", (arg,))
    for t in TABLES:                                   # sablony ze struktury OSTRYCH tabulek (jina jmena)
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
    for t in TABLES:                                   # stinove tabulky: stejne nazvy i indexy, bez FK
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")   # (LIKE sama sebe MySQL nepusti, chyba 1066)
    for t in TABLES:
        cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_src_{t}`")
    cur.execute("UPDATE content_gallery_items SET owner_id=%s", (SRC,))
    # zdrojovy radek: hodnoty, ktere se v kopii maji vynulovat / prenastavit, a ktere skutecny radek nema
    cur.execute(
        "UPDATE shop_products SET shoptet_id=999001, shoptet_code='T-CODE-1', shoptet_guid='g-1', ean='8590000000000', "
        "cfg_dily_id='dil_test', glb_file='product_3045.glb', thumbnail_file='t.png', fbx_original_name='x.fbx', "
        "vandr_stored_model_uuid=UUID(), vandr_razitka_json='{\"x\":1}', vandr_predni_azimut_deg=90, "
        "has_variants=1, variant_count=3, has_set_items=1, visible_in_scene=1, activated_at=NOW(), "
        "supplier_name='Dodavatel X', alternative_product_codes='[\"A1\",\"B2\"]' WHERE id=%s", (SRC,))
    cur.execute("SELECT id FROM content_categories ORDER BY id LIMIT 1")
    cur.execute("INSERT INTO shop_product_categories (product_id, category_id) VALUES (%s,%s)", (SRC, cur.fetchone()["id"]))
    # dokumenty: 1 existujici PDF, 1 s chybejicim souborem, 1 youtube (bez souboru)
    with open(os.path.join(tmp_docs_src, "product-3045_manual-deadbeef.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 test manual\n")
    cur.execute(
        "INSERT INTO shop_product_documents (product_id, filename, original_name, doc_type, caption, sort_order) VALUES "
        "(%s,'product-3045_manual-deadbeef.pdf','manual.pdf','pdf','Manual',0),"
        "(%s,'product-3045_chybi-00000000.pdf','chybi.pdf','pdf',NULL,1),"
        "(%s,'dQw4w9WgXcQ',NULL,'youtube',NULL,2)", (SRC, SRC, SRC))


def main():
    pred = permanent_state()
    tmp = tempfile.mkdtemp(prefix="dup_test_")
    g_dst, d_src, d_dst = (os.path.join(tmp, x) for x in ("gallery_dst", "docs_src", "docs_dst"))
    for d in (g_dst, d_src, d_dst):
        os.makedirs(d)
    conn = connect()
    try:
        with conn.cursor() as cur:
            setup_temp(cur, d_src)
            conn.commit()
            cur.execute("SELECT COUNT(*) AS n FROM content_gallery_items")
            print(f"pripraveno: produkt {SRC}, radku galerie v docasne tabulce: {cur.fetchone()['n']}")
            cur.execute("SELECT filename FROM content_gallery_items")
            zdroj_gal = [r["filename"] for r in cur.fetchall()]
            over("0 realne soubory galerie existuji", all(os.path.isfile(os.path.join(REAL_GALLERY, f)) for f in zdroj_gal), zdroj_gal)

            cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='shop_products'")
            ctype = {r["COLUMN_NAME"]: r["COLUMN_TYPE"] for r in cur.fetchall()}
            cur.execute("SELECT * FROM shop_products WHERE id=%s", (SRC,))
            src = cur.fetchone()

            kw = dict(slug_for_name=slug_for_name, created_by=793, created_role="skladnik",
                      gallery_dir=REAL_GALLERY, docs_dir=d_src, gallery_dst_dir=g_dst, docs_dst_dir=d_dst)

            # ---- T1: zakladni kopie ------------------------------------------------
            res = pd.duplicate_product(cur, SRC, **kw)
            conn.commit()
            cur.execute("SELECT * FROM shop_products WHERE id=%s", (res["id"],))
            nov = cur.fetchone()
            over("T1.1 nove ID a SKU '<sku>-kopie'", res["id"] != SRC and res["sku"] == src["sku"] + "-kopie" == nov["sku"], res)
            over("T1.2 nazev '(kopie)' a nový slug", nov["name"] == src["name"] + " (kopie)" and nov["slug"] and nov["slug"] != src["slug"], (nov["name"], nov["slug"]))
            zle = []
            for name, typ in ctype.items():
                if name in ("id", "created_at", "sku", "name", "slug"):
                    continue
                if name in pd.FORCE_VALUE:
                    ocek = pd.FORCE_VALUE[name]
                elif name in pd.RESET_NULL:
                    ocek = None
                else:
                    ocek = src[name]
                a, b = nov[name], ocek
                if typ == "json" and isinstance(a, str) and isinstance(b, str):
                    a, b = json.loads(a), json.loads(b)
                if a != b:
                    zle.append((name, a, b))
            over("T1.3 VSECHNY sloupce maji ocekavanou hodnotu (kopie / vynulovano / pevne)", not zle, zle)
            over("T1.4 sklad 315 -> 0, neaktivni, mimo scenu, bez EAN/Shoptet/cfg_dily/3D",
                 src["stock_qty"] == 315 and nov["stock_qty"] == 0 and nov["active"] == 0 and nov["visible_in_scene"] == 0
                 and nov["ean"] is None and nov["shoptet_id"] is None and nov["cfg_dily_id"] is None and nov["glb_file"] is None
                 and nov["has_variants"] == 0 and nov["vandr_stored_model_uuid"] is None,
                 {k: nov[k] for k in ("stock_qty", "active", "visible_in_scene", "ean", "shoptet_id", "cfg_dily_id", "glb_file")})
            over("T1.5 Dogus parovani a JSON specifikace se zdedily",
                 nov["dogus_url"] == src["dogus_url"] and json.loads(nov["product_specs_json"]) == json.loads(src["product_specs_json"]),
                 (nov["dogus_url"], src["dogus_url"]))
            over("T1.6 pocty zkopirovanych radku", res["copied"] == {"categories": 1, "images": 1, "usage_images": 2, "documents": 2, "gallery": len(zdroj_gal)}, res["copied"])
            over("T1.7 chybejici soubor dokumentu se ohlasi (missing_files=1)", res["missing_files"] == 1, res["missing_files"])

            cur.execute("SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY id", (SRC,))
            src_imgs = [r["filename"] for r in cur.fetchall()]
            cur.execute("SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY id", (res["id"],))
            over("T1.8 obrazky z importu sdili soubor s originalem", [r["filename"] for r in cur.fetchall()] == src_imgs and src_imgs, src_imgs)
            cur.execute("SELECT filename, created_by, created_role FROM content_gallery_items WHERE owner_id=%s AND owner_type='product' ORDER BY sort_order, id", (res["id"],))
            gal = cur.fetchall()
            over("T1.9 galerie: VLASTNI soubory v ciloveho adresari, stejny obsah, jiny nazev",
                 len(gal) == len(zdroj_gal) and all(
                     g["filename"] not in zdroj_gal and g["filename"].startswith(f"product-{res['id']}_")
                     and os.path.isfile(os.path.join(g_dst, g["filename"])) for g in gal)
                 and sorted(sha(os.path.join(g_dst, g["filename"])) for g in gal) == sorted(sha(os.path.join(REAL_GALLERY, f)) for f in zdroj_gal),
                 [g["filename"] for g in gal])
            over("T1.10 galerie: created_by/created_role = ten, kdo duplikuje", all(g["created_by"] == 793 and g["created_role"] == "skladnik" for g in gal), gal)
            cur.execute("SELECT filename, doc_type FROM shop_product_documents WHERE product_id=%s ORDER BY sort_order", (res["id"],))
            docs = cur.fetchall()
            over("T1.11 dokumenty: PDF ma novy soubor, youtube zustal, chybejici vynechan",
                 len(docs) == 2 and docs[0]["doc_type"] == "pdf" and docs[0]["filename"] != "product-3045_manual-deadbeef.pdf"
                 and os.path.isfile(os.path.join(d_dst, docs[0]["filename"])) and docs[1]["filename"] == "dQw4w9WgXcQ", docs)
            ocek_soubory = sorted([os.path.join(g_dst, g["filename"]) for g in gal] + [os.path.join(d_dst, docs[0]["filename"])])
            over("T1.12 created_files obsahuje vsechny vytvorene soubory", sorted(res["created_files"]) == ocek_soubory, res["created_files"])

            # ---- T2/T3: dalsi kopie, kopie kopie -----------------------------------
            res2 = pd.duplicate_product(cur, SRC, **kw)
            conn.commit()
            over("T2 druha kopie: SKU '-kopie-2', nazev '(kopie 2)', jiny slug", res2["sku"].endswith("-kopie-2") and res2["name"].endswith(" (kopie 2)") and res2["slug"] not in (nov["slug"], src["slug"]), res2)
            res3 = pd.duplicate_product(cur, res["id"], **kw)
            conn.commit()
            over("T3 kopie kopie se nezretezuje ('-kopie-3', ne '-kopie-kopie')", res3["sku"] == src["sku"] + "-kopie-3" and res3["name"] == src["name"] + " (kopie 3)", res3["sku"])

            # ---- T4: souboh o SKU -> INSERT 1062 -> opakovani ------------------------
            orig = pd.pick_identity
            calls = {"n": 0}

            def flaky(cur_, sku, name, slug_fn, start=1):
                calls["n"] += 1
                if calls["n"] == 1:
                    return 1, sku, name, slug_fn(cur_, name + " x")   # SKU zdroje -> kolize
                return orig(cur_, sku, name, slug_fn, start)
            pd.pick_identity = flaky
            try:
                cur.execute("SELECT COUNT(*) AS n FROM shop_products")
                pred_n = cur.fetchone()["n"]
                res4 = pd.duplicate_product(cur, SRC, **kw)
                conn.commit()
                cur.execute("SELECT COUNT(*) AS n FROM shop_products")
                over("T4 kolize SKU pri INSERTu se zopakuje a vznikne prave 1 radek", calls["n"] == 2 and cur.fetchone()["n"] == pred_n + 1 and res4["sku"].endswith("-kopie-4"), (calls, res4["sku"]))
            finally:
                pd.pick_identity = orig

            # ---- T5: neexistujici produkt --------------------------------------------
            try:
                pd.duplicate_product(cur, 99999999, **kw)
                over("T5 neexistujici produkt -> ProductNotFound", False)
            except pd.ProductNotFound:
                over("T5 neexistujici produkt -> ProductNotFound", True)

            # ---- T6: selhani uprostred -> uklid souboru + rollback ---------------------
            cur.execute("SELECT COUNT(*) AS n FROM shop_products")
            pred_n = cur.fetchone()["n"]
            pred_soubory = sorted(os.listdir(d_dst)) + sorted(os.listdir(g_dst))
            try:
                pd.duplicate_product(cur, SRC, **dict(kw, gallery_dst_dir=os.path.join(tmp, "neexistuje")))
                over("T6 selhani kopie souboru se propusti jako vyjimka", False)
            except OSError:
                over("T6.1 selhani kopie souboru se propusti jako vyjimka", True)
            over("T6.2 soubory vytvorene pred selhanim (PDF v docs_dst) funkce sama smazala", sorted(os.listdir(d_dst)) + sorted(os.listdir(g_dst)) == pred_soubory, os.listdir(d_dst))
            conn.rollback()
            cur.execute("SELECT COUNT(*) AS n FROM shop_products")
            over("T6.3 po rollbacku po selhani nezustal zadny novy radek", cur.fetchone()["n"] == pred_n)

            # ---- T7: generika unikatnich sloupcu ---------------------------------------
            real_u = pd._unique_single_columns
            pd._unique_single_columns = lambda c, t: real_u(c, t) | {"supplier_name"}
            try:
                r7 = pd.duplicate_product(cur, SRC, **kw)
                conn.commit()
                cur.execute("SELECT supplier_name FROM shop_products WHERE id=%s", (r7["id"],))
                over("T7.1 novy nullable unikatni sloupec se v kopii vynuluje", cur.fetchone()["supplier_name"] is None)
                pd._unique_single_columns = lambda c, t: real_u(c, t) | {"unit"}          # NOT NULL
                try:
                    pd.duplicate_product(cur, SRC, **kw)
                    over("T7.2 NOT NULL unikatni sloupec bez osetreni hlasite selze", False)
                except RuntimeError:
                    over("T7.2 NOT NULL unikatni sloupec bez osetreni hlasite selze", True)
                conn.rollback()
            finally:
                pd._unique_single_columns = real_u

            # ---- T8: registr souvisejicich tabulek ---------------------------------------
            over("T8.1 kazda tabulka s odkazem na produkt je v registru (COPIED/SKIPPED)", pd.unclassified_reference_tables(cur) == [], pd.unclassified_reference_tables(cur))
            saved = pd.SKIPPED_TABLES.pop("product_markups")
            try:
                over("T8.2 kontrola OPRAVDU odhali chybejici zaznam (pouzije se na stavu pred opravou)", pd.unclassified_reference_tables(cur) == ["product_markups"], pd.unclassified_reference_tables(cur))
            finally:
                pd.SKIPPED_TABLES["product_markups"] = saved
    finally:
        conn.close()
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- T9: ostre tabulky a adresare se nezmenily ----------------------------------------
    po = permanent_state()
    over("T9 ostre tabulky, AUTO_INCREMENT ani adresare se souborem se nezmenily", po == pred, {"pred": pred, "po": po})

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK duplikace produktu: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
