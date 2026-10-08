#!/usr/bin/env python3
"""
QA suita D: integrita DB + drift migraci - bot13, 2026-09-02 (vypujcka
z /opt/no-sim, Robert pres bot3: "kontrolni mechanismy na cely system
konfiguratoru... hledat chyby, delat skripty na hledani chyb, hledat
moznosti ke zlepseni"). Spolecny ramec viz scripts/qa/_common.py
(bot14) - JEDEN JSON kontrakt sdileny napric vsemi QA suitami.

READ-ONLY (get_conn() nastavuje SET SESSION TRANSACTION READ ONLY) -
tenhle skript NIC neopravuje ani nemaze, jen hlasi. Vsechny nalezy
overeny zivym dotazem proti realne DB, ne odhadem ze schematu.

Co uz existujici api/qa_checks.py hlida (NEDUPLIKOVANO tady, viz
CHECKS registr tam): missing_price/image/description, duplicate_sku,
orphaned_gallery_items (owner reference gallery_items -> vlastnik),
orphaned_cfg_dily_ref, missing_glb_file, missing_dogus_price_
coefficient a dalsich ~40 kontrol nad produkty/kategoriemi/UI kodem.
Tahle suita cili na SIROKSI zaber - tabulky, ktere qa_checks.py vubec
nezna (product_markups, product_turntable_frames, product_assemblies,
CRM/objednavky/dodavatele/system_emails...), existenci SOUBORU na
disku (ne jen DB->DB reference), schema/drift migraci.

Mapovani sloupec->cilova tabulka i soubor->adresar je RUCNI a OVERENE
v kodu (grep skutecnych INSERT/save() mist v api/*.py, scripts/*.py -
viz komentare u FK_MAP/FILE_MAP nize), ne heuristika podle jmena
adresare - db je malá (max ~3000 řádků v tabulce), takže přesnost byla
levnější než rychlost.

Pouziti:
  cd /opt/konfigurator
  api/venv/bin/python3 scripts/qa/db_integrity.py            # cloveci text
  api/venv/bin/python3 scripts/qa/db_integrity.py --json      # JSON kontrakt
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "api"))

from _common import get_conn, finding, run_suite, ram_watchdog_alert_active  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(REPO_ROOT, "webapp", "content-files")
PRIVATE_FILES_DIR = os.path.join(REPO_ROOT, "private-files")
SQL_DIR = os.path.join(REPO_ROOT, "sql")
API_DIR = os.path.join(REPO_ROOT, "api")

MAX_SAMPLE = 10
MAX_ORPHAN_ROWS_SCANNED = 5000  # LIMIT v dotazu - pojistka proti neocekavane velke tabulce


# ---------------------------------------------------------------------------
# A) Sirotci (cizi klic bez skutecneho FOREIGN KEY constraintu v DB)
# ---------------------------------------------------------------------------
# Overeno kazde jednotlive (tabulka, sloupec) rucne v kodu (INSERT/
# UPDATE mista v api/*.py) pred pridanim sem - ne odhad podle jmena.
# Vyjimka: crm_leads.craftsman_id je VYNECHANO zamerne - remeslo_*
# tabulky ted zijou v samostatne DB "Remeslnik" (REMESLO_DB_* env,
# viz api/db_migrate_remeslo.py), takze remeslo_craftsmen v TETO DB je
# stara/opustena kopie (viz info nalez DB_STALE_REMESLO_TABLES nize) -
# orphan check proti ni by byl zavadejici cross-DB tvrzeni.
FK_MAP = {
    ("product_markups", "product_id"): "shop_products",
    ("product_markups", "lead_id"): "crm_leads",
    ("product_markups", "gallery_item_id"): "content_gallery_items",
    ("product_turntable_frames", "shop_product_id"): "shop_products",
    ("product_turntable_frames", "assembly_id"): "product_assemblies",
    ("product_assemblies", "category_id"): "content_categories",
    ("product_assemblies", "car_model_id"): "car_models",
    ("product_assemblies", "created_by"): "app_users",
    ("product_assemblies", "shop_product_id"): "shop_products",
    ("shop_orders", "user_id"): "app_users",
    ("shop_orders", "storefront_id"): "car_storefronts",
    ("shop_order_items", "order_id"): "shop_orders",
    ("shop_order_items", "product_id"): "shop_products",
    ("crm_leads", "customer_id"): "shop_customers",
    ("crm_leads", "assigned_to"): "app_users",
    ("crm_leads", "order_id"): "shop_orders",
    ("crm_leads", "drive_folder_id"): "shared_drive_folders",
    ("crm_lead_messages", "lead_id"): "crm_leads",
    ("crm_lead_messages", "sender_user_id"): "app_users",
    ("crm_lead_message_attachments", "message_id"): "crm_lead_messages",
    ("crm_lead_notes", "lead_id"): "crm_leads",
    ("crm_lead_notes", "author_id"): "app_users",
    ("crm_lead_tasks", "lead_id"): "crm_leads",
    ("crm_lead_tasks", "created_by"): "app_users",
    ("crm_quotes", "lead_id"): "crm_leads",
    ("crm_quotes", "customer_id"): "shop_customers",
    ("crm_quotes", "created_by"): "app_users",
    ("crm_quotes", "approved_by"): "app_users",
    ("crm_quote_files", "quote_id"): "crm_quotes",
    ("crm_quote_files", "folder_id"): "crm_quote_folders",
    ("crm_quote_files", "source_message_id"): "crm_lead_messages",
    ("crm_quote_files", "uploaded_by"): "app_users",
    ("shop_purchase_orders", "supplier_id"): "shop_suppliers",
    ("shop_purchase_orders", "created_by"): "app_users",
    ("shop_purchase_orders", "source_order_id"): "shop_orders",
    ("shop_purchase_order_items", "purchase_order_id"): "shop_purchase_orders",
    ("shop_purchase_order_items", "product_id"): "shop_products",
    ("shop_customers", "user_id"): "app_users",
    ("shop_customers", "group_id"): "shop_customer_groups",
    ("system_emails", "user_id"): "app_users",
    ("system_emails", "sent_by_user_id"): "app_users",
    ("shop_cart_items", "user_id"): "app_users",
    ("shop_cart_items", "product_id"): "shop_products",
    ("shop_emails", "order_id"): "shop_orders",
    ("shop_emails", "purchase_order_id"): "shop_purchase_orders",
    ("shop_emails", "document_id"): "shop_documents",
    ("shop_emails", "sent_by_user_id"): "app_users",
    ("shop_products", "category_id"): "content_categories",
    ("shop_products", "supplier_id"): "shop_suppliers",
    ("content_categories", "parent_id"): "content_categories",
    ("shop_documents", "order_id"): "shop_orders",
    ("shop_documents", "related_document_id"): "shop_documents",
    ("shop_documents", "approved_by"): "app_users",
    ("incoming_documents", "reviewed_by"): "app_users",
    ("incoming_documents", "paid_bank_transaction_id"): "bank_transactions",
    ("content_files", "category_id"): "content_categories",
    ("shop_product_images", "product_id"): "shop_products",
    ("shop_product_documents", "product_id"): "shop_products",
    ("product_usage_images", "product_id"): "shop_products",
}


def check_orphans(cur):
    out = []
    for (table, col), target in FK_MAP.items():
        try:
            cur.execute(
                f"SELECT `{table}`.`id` AS rid FROM `{table}` "
                f"WHERE `{table}`.`{col}` IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM `{target}` t WHERE t.`id`=`{table}`.`{col}`) "
                f"LIMIT {MAX_ORPHAN_ROWS_SCANNED}"
            )
            rows = cur.fetchall()
        except Exception as e:  # schema driftlo od pruzkumu, nebo tabulka/sloupec chybi
            out.append(finding("info", "DB_ORPHAN_CHECK_SKIPPED",
                                f"Kontrola sirotků {table}.{col} přeskočena (chyba dotazu)",
                                str(e), where=f"{table}.{col}"))
            continue
        if rows:
            ids = [str(r["rid"]) for r in rows]
            sample = ", ".join(ids[:MAX_SAMPLE])
            more = f" … a dalších {len(ids) - MAX_SAMPLE}" if len(ids) > MAX_SAMPLE else ""
            severity = "critical" if table in ("shop_order_items", "shop_purchase_order_items") else "warning"
            out.append(finding(
                severity, "DB_ORPHAN_ROW",
                f"{len(ids)} sirotčích řádků: {table}.{col} → {target}",
                f"{table}.id in ({sample}{more}) odkazuje přes {col} na neexistující {target}.id.",
                where=f"{table}.{col}",
                fix_hint=f"Ověřit ručně a buď smazat sirotčí řádky {table}, nebo doplnit chybějící {target} záznamy.",
            ))
    return out


def check_unmapped_id_columns(cur):
    """Info-only inventura (bot3: 'neznamé nahlas jako info nemapováno') -
    vsechny INT sloupce koncici na _id, ktere NEJSOU v FK_MAP - at je
    videt rozsah toho, co se JESTE nekontroluje, bez tvrzeni o platnosti."""
    cur.execute(
        "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA=DATABASE() AND COLUMN_NAME LIKE '%%\\_id' "
        "AND COLUMN_NAME<>'id' AND DATA_TYPE IN ('int','bigint','smallint','mediumint') "
        "ORDER BY TABLE_NAME, COLUMN_NAME"
    )
    all_cols = [(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()]
    unmapped = [f"{t}.{c}" for (t, c) in all_cols if (t, c) not in FK_MAP and not t.startswith("_zzz_remeslo_")]
    if not unmapped:
        return []
    sample = ", ".join(unmapped[:40])
    more = f" … a dalších {len(unmapped) - 40}" if len(unmapped) > 40 else ""
    return [finding(
        "info", "DB_ORPHAN_UNMAPPED_COLUMN",
        f"{len(unmapped)} _id sloupců zatím bez ověřené kontroly sirotků",
        f"Nejsou v FK_MAP (buď skutečně nemají cizí klíč - např. externí ID, nebo jen zatím nezmapováno): {sample}{more}",
        where="scripts/qa/db_integrity.py:FK_MAP",
        fix_hint="Případné doplnění FK_MAP až po ověření v kódu, ne odhadem podle jména.",
    )]


# ---------------------------------------------------------------------------
# B) Soubory - DB reference vs. disk, oběma směry
# ---------------------------------------------------------------------------
# (tabulka, sloupec) -> (base_dir, poddir) - OVĚŘENO grepem skutečného
# save()/INSERT místa v kódu (viz AGENTS_LOG.md zápis téhle suity pro
# přesné odkazy), ne odhad podle názvu adresáře.
FILE_MAP = [
    ("shop_product_images", "filename", os.path.join(UPLOAD_DIR, "gallery")),
    ("shop_product_documents", "filename", os.path.join(UPLOAD_DIR, "product-documents")),
    ("product_usage_images", "filename", os.path.join(UPLOAD_DIR, "product-usage")),
    # shop_gallery_images NENI tady - cesta je gallery/<category>/<filename>,
    # ne plochy gallery/<filename> (viz _category_dir() v api/gallery.py,
    # overeno zivym behem - prvni pokus s plochym adresarem nahlasil 226
    # falesnych "chybejicich" souboru, ktere ve skutecnosti existovaly jen
    # o adresar niz). Resi se zvlast v _shop_gallery_images_missing() nize.
    ("content_files", "stored_name", UPLOAD_DIR),
    ("product_turntable_frames", "filename", UPLOAD_DIR),  # filename uz obsahuje "turntable-frames/..." prefix
    ("product_markups", "composite_filename", os.path.join(PRIVATE_FILES_DIR, "product-markups")),
    ("incoming_documents", "stored_filename", os.path.join(PRIVATE_FILES_DIR, "incoming-documents")),
    ("crm_quote_files", "stored_filename", os.path.join(PRIVATE_FILES_DIR, "crm-quotes")),
]

# crm_lead_message_attachments: quotes.py komentář ("stare radky tam
# mohou jeste existovat z doby pred bot10 2026-08-22") explicitne
# rika, ze STARE radky mohou byt v QUOTE_FILES_DIR misto vlastni
# LEAD_ATTACHMENTS_DIR - kontroluju OBA adresare, chybi-li jen v
# jednom, neni to sirotek.
LEAD_ATTACHMENT_DIRS = [
    os.path.join(PRIVATE_FILES_DIR, "crm-lead-attachments"),
    os.path.join(PRIVATE_FILES_DIR, "crm-quotes"),
]


def _db_files_missing_on_disk(cur):
    out = []
    for table, col, base_dir in FILE_MAP:
        try:
            cur.execute(f"SELECT id, `{col}` AS fn FROM `{table}` WHERE `{col}` IS NOT NULL AND `{col}`<>''")
            rows = cur.fetchall()
        except Exception as e:
            out.append(finding("info", "DB_FILE_CHECK_SKIPPED", f"Kontrola souborů {table}.{col} přeskočena", str(e), where=f"{table}.{col}"))
            continue
        missing, zero_size = [], []
        for r in rows:
            p = os.path.join(base_dir, r["fn"])
            if not os.path.isfile(p):
                missing.append((r["id"], r["fn"]))
            elif os.path.getsize(p) == 0:
                zero_size.append((r["id"], r["fn"]))
        if missing:
            sample = ", ".join(f"#{i}:{fn}" for i, fn in missing[:MAX_SAMPLE])
            out.append(finding(
                "critical", "DB_FILE_MISSING",
                f"{len(missing)}× {table}.{col} odkazuje na neexistující soubor",
                f"Chybí pod {base_dir}. Ukázka: {sample}" + (" …" if len(missing) > MAX_SAMPLE else ""),
                where=f"{table}.{col}",
                fix_hint="Ověřit, jestli soubor jen chybí na disku (obnovit ze zálohy) nebo je záznam zastaralý (smazat řádek).",
            ))
        if zero_size:
            sample = ", ".join(f"#{i}:{fn}" for i, fn in zero_size[:MAX_SAMPLE])
            out.append(finding(
                "warning", "DB_FILE_ZERO_SIZE",
                f"{len(zero_size)}× {table}.{col} odkazuje na prázdný (0 B) soubor",
                f"Pod {base_dir}. Ukázka: {sample}" + (" …" if len(zero_size) > MAX_SAMPLE else ""),
                where=f"{table}.{col}",
                fix_hint="Prázdný soubor typicky znamená přerušený upload - přenahrát nebo smazat řádek.",
            ))

    # crm_lead_message_attachments - dvoji-adresarova vyjimka
    try:
        cur.execute("SELECT id, stored_filename AS fn FROM crm_lead_message_attachments WHERE stored_filename IS NOT NULL AND stored_filename<>''")
        rows = cur.fetchall()
        missing = [(r["id"], r["fn"]) for r in rows if not any(os.path.isfile(os.path.join(d, r["fn"])) for d in LEAD_ATTACHMENT_DIRS)]
        if missing:
            sample = ", ".join(f"#{i}:{fn}" for i, fn in missing[:MAX_SAMPLE])
            out.append(finding(
                "critical", "DB_FILE_MISSING",
                f"{len(missing)}× crm_lead_message_attachments.stored_filename odkazuje na neexistující soubor",
                f"Chybí v OBOU možných adresářích ({', '.join(LEAD_ATTACHMENT_DIRS)}). Ukázka: {sample}" + (" …" if len(missing) > MAX_SAMPLE else ""),
                where="crm_lead_message_attachments.stored_filename",
                fix_hint="Ověřit, jestli soubor jen chybí na disku nebo je záznam zastaralý.",
            ))
    except Exception as e:
        out.append(finding("info", "DB_FILE_CHECK_SKIPPED", "Kontrola crm_lead_message_attachments přeskočena", str(e), where="crm_lead_message_attachments.stored_filename"))

    # content_gallery_items - is_public rozhoduje o adresari, ale
    # kontroluju OBA (viz hlavicka souboru - lepe mensi presnost nez
    # falesny poplach ze spatne interpretovaneho is_public).
    try:
        cur.execute("SELECT id, filename FROM content_gallery_items WHERE filename IS NOT NULL AND filename<>''")
        rows = cur.fetchall()
        gdirs = [os.path.join(UPLOAD_DIR, "gallery-items"), os.path.join(PRIVATE_FILES_DIR, "gallery-items")]
        missing = [(r["id"], r["filename"]) for r in rows if not any(os.path.isfile(os.path.join(d, r["filename"])) for d in gdirs)]
        if missing:
            sample = ", ".join(f"#{i}:{fn}" for i, fn in missing[:MAX_SAMPLE])
            out.append(finding(
                "critical", "DB_FILE_MISSING",
                f"{len(missing)}× content_gallery_items.filename odkazuje na neexistující soubor",
                f"Chybí v obou možných adresářích (public/private gallery-items). Ukázka: {sample}" + (" …" if len(missing) > MAX_SAMPLE else ""),
                where="content_gallery_items.filename",
                fix_hint="Ověřit is_public a hledaný adresář, případně obnovit/smazat záznam.",
            ))
    except Exception as e:
        out.append(finding("info", "DB_FILE_CHECK_SKIPPED", "Kontrola content_gallery_items souborů přeskočena", str(e), where="content_gallery_items.filename"))

    out.extend(_shop_gallery_images_missing(cur))
    return out


def _shop_gallery_images_missing(cur):
    """shop_gallery_images.filename NENI plochy soubor pod gallery/ -
    zivá cesta je gallery/<category>/<filename> (viz api/gallery.py
    _category_dir()). Overeno zivym behem (prvni verze s plochym
    adresarem hlasila 226 falesnych "chybi" nalezu)."""
    try:
        cur.execute("SELECT id, category, filename FROM shop_gallery_images WHERE filename IS NOT NULL AND filename<>''")
        rows = cur.fetchall()
    except Exception as e:
        return [finding("info", "DB_FILE_CHECK_SKIPPED", "Kontrola shop_gallery_images přeskočena", str(e), where="shop_gallery_images.filename")]
    missing = [(r["id"], r["category"], r["filename"]) for r in rows
               if not os.path.isfile(os.path.join(UPLOAD_DIR, "gallery", r["category"] or "", r["filename"]))]
    if not missing:
        return []
    sample = ", ".join(f"#{i}:{cat}/{fn}" for i, cat, fn in missing[:MAX_SAMPLE])
    return [finding(
        "critical", "DB_FILE_MISSING",
        f"{len(missing)}× shop_gallery_images.filename odkazuje na neexistující soubor",
        f"Chybí pod {os.path.join(UPLOAD_DIR, 'gallery')}/<category>/. Ukázka: {sample}" + (" …" if len(missing) > MAX_SAMPLE else ""),
        where="shop_gallery_images.filename",
        fix_hint="Ověřit, jestli soubor jen chybí na disku (obnovit ze zálohy) nebo je záznam zastaralý (smazat řádek).",
    )]


def _disk_files_without_db(cur):
    """Opačný směr - soubory na disku, na které žádný řádek v DB
    neukazuje. Jen pro adresáře, které jsou VÝHRADNĚ obsluhované
    přesně jedním sloupcem výše (ne sdílené/smíšené adresáře), ať
    nehlásíme jako "sirotka" soubor, co ve skutečnosti patří jinému
    sloupci se stejným adresářem."""
    out = []
    single_owner_dirs = [
        ("product-documents", "shop_product_documents", "filename"),
        ("product-usage", "product_usage_images", "filename"),
    ]
    for subdir, table, col in single_owner_dirs:
        d = os.path.join(UPLOAD_DIR, subdir)
        if not os.path.isdir(d):
            continue
        on_disk = {f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and not f.startswith("_")}
        cur.execute(f"SELECT `{col}` AS fn FROM `{table}`")
        in_db = {r["fn"] for r in cur.fetchall()}
        extra = on_disk - in_db
        if extra:
            total_bytes = sum(os.path.getsize(os.path.join(d, f)) for f in extra)
            sample = ", ".join(sorted(extra)[:MAX_SAMPLE])
            out.append(finding(
                "info", "DISK_FILE_ORPHAN",
                f"{len(extra)} souborů v {subdir}/ bez odpovídajícího řádku v {table}",
                f"Součet velikosti: {total_bytes/1024/1024:.1f} MB. Ukázka: {sample}",
                where=f"webapp/content-files/{subdir}/",
                fix_hint="Nic nemazat automaticky - ověřit ručně, jestli jde o zastaralý upload nebo import mimo tenhle sloupec.",
            ))
    return out


def check_turntable_orphan_dirs(cur):
    """Adresáře dávek pod turntable-frames/<shop_product_id>/<batch>/,
    na které NEEXISTUJE ŽÁDNÝ řádek v product_turntable_frames (ani
    aktivní, ani neaktivní). Bot3: 'is_active=0 dávka mladší 24h není
    sirotek' - ALE `deactivated_at` sloupec zatím v DB NENÍ (migrace
    sql/2026-09-02_turntable_deactivated_at.sql čeká na Roberta, viz
    check_migration_drift), takže "kdy" u neaktivní dávky nejde zjistit.
    Schema-tolerantní řešení: dávky, které V DB VŮBEC NEEXISTUJÍ (ani
    is_active=0), se hlásí; dávky, co existují jen jako is_active=0,
    se VYNECHÁVAJÍ celé (bezpečnější než špatně odhadnutá 24h hranice)."""
    tf_dir = os.path.join(UPLOAD_DIR, "turntable-frames")
    if not os.path.isdir(tf_dir):
        return []
    cur.execute("SELECT DISTINCT shop_product_id, batch FROM product_turntable_frames")
    known = {(str(r["shop_product_id"]), r["batch"]) for r in cur.fetchall()}
    orphan_dirs = []
    total_bytes = 0
    for pid in os.listdir(tf_dir):
        pdir = os.path.join(tf_dir, pid)
        if not os.path.isdir(pdir):
            continue
        for batch in os.listdir(pdir):
            bdir = os.path.join(pdir, batch)
            if not os.path.isdir(bdir) or (pid, batch) in known:
                continue
            size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(bdir) for f in fs)
            total_bytes += size
            orphan_dirs.append(f"{pid}/{batch}")
    out = []
    if orphan_dirs:
        sample = ", ".join(orphan_dirs[:MAX_SAMPLE])
        out.append(finding(
            "info", "DISK_TURNTABLE_ORPHAN_DIR",
            f"{len(orphan_dirs)} dávek turntable-frames na disku zcela bez záznamu v DB",
            f"Součet velikosti: {total_bytes/1024/1024:.1f} MB. Ukázka: {sample}",
            where="webapp/content-files/turntable-frames/",
            fix_hint="Bezpečné k prozkoumání/smazání ručně - v DB o nich není ani neaktivní záznam.",
        ))
    # QA nalez (bot3/bot5, 2026-09-05): tenhle finding byl natvrdo
    # nepodmineny (vzdy hlasil "ceka na Roberta"), i kdyz migrace
    # sql/2026-09-02_turntable_deactivated_at.sql uz byla ZIVE APLIKOVANA
    # 2026-09-03 (overeno bot18, znovu bot5 2026-09-05 - SHOW COLUMNS
    # potvrzuje sloupec existuje). api/turntable.py::_sweep_expired_batches
    # uz aktivne beh grace-period logiku sama pri kazdem commitu/sweepu,
    # takze duplikovat ji tady by jen riskovalo rozjeti - staci zjistit
    # zive, jestli sloupec existuje, a limitaci uz nehlasit, kdyz neplati.
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() "
        "AND table_name='product_turntable_frames' AND column_name='deactivated_at'"
    )
    if not cur.fetchone():
        out.append(finding(
            "info", "DB_TURNTABLE_GRACE_PERIOD_LIMITED",
            "Kontrola neaktivních (is_active=0) turntable dávek NENÍ dělaná",
            "sql/2026-09-02_turntable_deactivated_at.sql (deactivated_at sloupec) v repu existuje, ale v DB zatím není aplikovaná (čeká na Roberta) - bez něj nejde spočítat 24h grace period, takže is_active=0 dávky se z file-orphan kontroly úplně vynechávají, ne odhadují.",
            where="product_turntable_frames.deactivated_at",
            fix_hint="Až migrace proběhne, doplnit sem skutečnou 24h grace-period logiku místo úplného vynechání.",
        ))
    return out


# ---------------------------------------------------------------------------
# C) Duplicity
# ---------------------------------------------------------------------------
def check_duplicates(cur):
    out = []

    cur.execute("SELECT slug, GROUP_CONCAT(id) ids, COUNT(*) c FROM shop_products WHERE slug IS NOT NULL AND slug<>'' GROUP BY slug HAVING c>1")
    for r in cur.fetchall():
        out.append(finding("critical", "DB_DUPLICATE_SLUG", f"Duplicitní shop_products.slug '{r['slug']}'",
                            f"ID: {r['ids']} ({r['c']}×)", where="shop_products.slug",
                            fix_hint="slug má UNIQUE index podle information_schema - pokud tohle nachází duplicity, index buď chybí, nebo je case-insensitive kolize."))

    cur.execute("SELECT slug, GROUP_CONCAT(id) ids, COUNT(*) c FROM content_categories WHERE slug IS NOT NULL AND slug<>'' GROUP BY slug HAVING c>1")
    for r in cur.fetchall():
        out.append(finding("critical", "DB_DUPLICATE_SLUG", f"Duplicitní content_categories.slug '{r['slug']}'",
                            f"ID: {r['ids']} ({r['c']}×)", where="content_categories.slug"))

    # case-insensitive + trim e-maily zakazniku
    cur.execute("""
        SELECT LOWER(TRIM(email)) e, GROUP_CONCAT(id) ids, COUNT(*) c FROM shop_customers
        WHERE email IS NOT NULL AND email<>'' GROUP BY LOWER(TRIM(email)) HAVING c>1
    """)
    for r in cur.fetchall():
        out.append(finding("warning", "DB_DUPLICATE_EMAIL", f"Duplicitní e-mail zákazníka '{r['e']}'",
                            f"shop_customers.id: {r['ids']} ({r['c']}×)", where="shop_customers.email"))

    cur.execute("""
        SELECT LOWER(TRIM(email)) e, GROUP_CONCAT(id) ids, COUNT(*) c FROM app_users
        WHERE email IS NOT NULL AND email<>'' GROUP BY LOWER(TRIM(email)) HAVING c>1
    """)
    for r in cur.fetchall():
        out.append(finding("critical", "DB_DUPLICATE_EMAIL", f"Duplicitní e-mail uživatele '{r['e']}'",
                            f"app_users.id: {r['ids']} ({r['c']}×) - app_users.email má být UNIQUE", where="app_users.email"))

    # nazvy produktu v ramci jedne kategorie
    cur.execute("""
        SELECT category_id, LOWER(TRIM(name)) n, GROUP_CONCAT(id) ids, COUNT(*) c
        FROM shop_products WHERE active=1 AND is_archived=0 AND category_id IS NOT NULL
        GROUP BY category_id, LOWER(TRIM(name)) HAVING c>1
    """)
    for r in cur.fetchall():
        out.append(finding("info", "DB_DUPLICATE_PRODUCT_NAME", f"Duplicitní název produktu v kategorii #{r['category_id']}: '{r['n']}'",
                            f"shop_products.id: {r['ids']} ({r['c']}×)", where=f"shop_products (category_id={r['category_id']})"))

    return out


# ---------------------------------------------------------------------------
# D) Konzistence
# ---------------------------------------------------------------------------
def check_consistency(cur):
    out = []

    cur.execute("SELECT id, name FROM product_assemblies WHERE is_public=1 AND shop_product_id IS NULL")
    rows = cur.fetchall()
    if rows:
        sample = ", ".join(f"#{r['id']}:{r['name']}" for r in rows[:MAX_SAMPLE])
        out.append(finding("warning", "DB_ASSEMBLY_PUBLIC_NO_PRODUCT",
                            f"{len(rows)} veřejných sestav (product_assemblies.is_public=1) bez napojeného shop_product_id",
                            f"Ukázka: {sample}", where="product_assemblies.shop_product_id",
                            fix_hint="Veřejná sestava bez produktu se pravděpodobně nikde nezobrazí zákazníkovi jako koupitelná položka."))

    # shop_products.category_id dangling je uz pokryte FK_MAP/check_orphans
    # (shop_products.category_id -> content_categories) - schvalne se tu
    # NEDUPLIKUJE dalsim dotazem.

    # category_path (denormalizovany retezec) vs skutecny strom parent_id
    cur.execute("SELECT id, parent_id, name, slug FROM content_categories")
    cats = {r["id"]: r for r in cur.fetchall()}

    def _real_path(cid, seen=None):
        seen = seen or set()
        if cid in seen or cid not in cats:
            return None
        seen.add(cid)
        c = cats[cid]
        seg = c["slug"] or c["name"]
        if c["parent_id"]:
            parent_path = _real_path(c["parent_id"], seen)
            return f"{parent_path}/{seg}" if parent_path else seg
        return seg

    cur.execute("SELECT id, name, category_id, category_path FROM shop_products WHERE category_path IS NOT NULL AND category_path<>'' AND category_id IS NOT NULL")
    drift = []
    for r in cur.fetchall():
        expected = _real_path(r["category_id"])
        if expected and r["category_path"].strip("/") != expected.strip("/"):
            drift.append((r["id"], r["name"], r["category_path"], expected))
    if drift:
        sample = "; ".join(f"#{i} '{cp}' != '{exp}'" for i, n, cp, exp in drift[:MAX_SAMPLE])
        out.append(finding("info", "DB_CATEGORY_PATH_DRIFT",
                            f"{len(drift)} produktů má shop_products.category_path neodpovídající aktuálnímu stromu content_categories",
                            f"Ukázka: {sample}", where="shop_products.category_path",
                            fix_hint="category_path je zřejmě denormalizovaný cache sloupec - přepočítat, nebo ověřit, jestli se vůbec ještě používá."))

    # objednavky - soucet polozek vs total_czk (s tolerenci na dopravu/platbu/slevu)
    cur.execute("""
        SELECT o.id, o.total_czk, o.shipping_price_czk, o.payment_price_czk,
               COALESCE(SUM(oi.line_total_czk), 0) AS items_sum
        FROM shop_orders o LEFT JOIN shop_order_items oi ON oi.order_id=o.id
        WHERE o.status<>'zrusena'
        GROUP BY o.id
    """)
    # status='zrusena' (zrušená) vyloučeno - total_czk=0 u zrušené
    # objednávky je očekávané chování, ne bug (ověřeno živě: #120/#134
    # v prvním běhu byly obě 'zrusena', false positive opraveno).
    bad_totals = []
    for r in cur.fetchall():
        expected = float(r["items_sum"]) + float(r["shipping_price_czk"] or 0) + float(r["payment_price_czk"] or 0)
        actual = float(r["total_czk"])
        # sleva zakaznicke skupiny muze snizit total pod prosty soucet - tolerance jen na HRUBOU odchylku
        if abs(actual - expected) > max(5, expected * 0.5):
            bad_totals.append((r["id"], actual, expected))
    if bad_totals:
        sample = "; ".join(f"#{i} total={a} vs polozky+doprava+platba={e:.0f}" for i, a, e in bad_totals[:MAX_SAMPLE])
        out.append(finding("warning", "DB_ORDER_TOTAL_MISMATCH",
                            f"{len(bad_totals)} objednávek má total_czk hrubě neodpovídající součtu položek",
                            f"Tolerance 50% (slevy nejsou v dotazu zahrnuté, jen hrubá anomálie). Ukázka: {sample}",
                            where="shop_orders.total_czk", fix_hint="Ručně ověřit - může jít o legitimní ruční slevu, nebo o chybu při vytvoření objednávky."))

    cur.execute("SELECT COUNT(*) c FROM system_emails WHERE status='pending' AND created_at < NOW() - INTERVAL 24 HOUR")
    n = cur.fetchone()["c"]
    if n:
        out.append(finding("warning", "DB_SYSTEM_EMAIL_STUCK_PENDING", f"{n} system_emails visí ve stavu 'pending' déle než 24h",
                            "Frontu ke schválení nikdo neřeší, nebo schvalovací UI má bug.", where="system_emails.status"))
    cur.execute("SELECT COUNT(*) c FROM system_emails WHERE status='failed'")
    n = cur.fetchone()["c"]
    if n:
        out.append(finding("warning", "DB_SYSTEM_EMAIL_FAILED", f"{n} system_emails ve stavu 'failed'",
                            "Odeslání selhalo a nikdo to zjevně neřešil.", where="system_emails.status"))

    cur.execute("SELECT COUNT(*) c FROM shop_emails WHERE status='pending' AND created_at < NOW() - INTERVAL 24 HOUR")
    n = cur.fetchone()["c"]
    if n:
        out.append(finding("warning", "DB_SYSTEM_EMAIL_STUCK_PENDING", f"{n} shop_emails visí ve stavu 'pending' déle než 24h",
                            "Objednávkové/dokladové e-maily čekající na schválení admina.", where="shop_emails.status"))

    # schvalovaci fronty (approval_status) - crm_quotes, shop_documents, incoming_documents
    for table in ("crm_quotes", "shop_documents", "incoming_documents"):
        cur.execute(f"SELECT COUNT(*) c FROM `{table}` WHERE approval_status='pending' AND created_at < NOW() - INTERVAL 7 DAY")
        n = cur.fetchone()["c"]
        if n:
            out.append(finding("warning", "DB_APPROVAL_STUCK_PENDING", f"{n} řádků v {table} čeká na schválení (approval_status='pending') déle než 7 dní",
                                "", where=f"{table}.approval_status"))

    cur.execute("SELECT id, email FROM app_users WHERE role IS NULL OR role=''")
    rows = cur.fetchall()
    if rows:
        sample = ", ".join(f"#{r['id']}:{r['email']}" for r in rows[:MAX_SAMPLE])
        out.append(finding("critical", "DB_USER_NO_ROLE", f"{len(rows)} app_users bez role",
                            f"role je NOT NULL enum v DB, ale prázdný/None obsah signalizuje bug v cestě, co uživatele vytváří. Ukázka: {sample}", where="app_users.role"))

    cur.execute("SELECT id, email, LENGTH(password_hash) len FROM app_users WHERE password_hash IS NULL OR LENGTH(password_hash) < 20")
    rows = cur.fetchall()
    if rows:
        sample = ", ".join(f"#{r['id']}:{r['email']} (len={r['len']})" for r in rows[:MAX_SAMPLE])
        out.append(finding("critical", "DB_USER_WEAK_PASSWORD_HASH", f"{len(rows)} app_users s podezřele krátkým/chybějícím password_hash",
                            f"Skutečné hashe (werkzeug) jsou typicky 90+ znaků. Ukázka: {sample}", where="app_users.password_hash"))

    # timestampy v budoucnosti / updated < created
    for table, ts_col in (("shop_orders", "created_at"), ("crm_leads", "created_at"), ("shop_products", "created_at")):
        cur.execute(f"SELECT COUNT(*) c FROM `{table}` WHERE `{ts_col}` > NOW()")
        n = cur.fetchone()["c"]
        if n:
            out.append(finding("warning", "DB_TIMESTAMP_IN_FUTURE", f"{n} řádků v {table}.{ts_col} je v budoucnosti",
                                "Typicky špatná timezone při importu/vkladu.", where=f"{table}.{ts_col}"))

    cur.execute("SELECT COUNT(*) c FROM shop_orders WHERE updated_at < created_at")
    n = cur.fetchone()["c"]
    if n:
        out.append(finding("warning", "DB_UPDATED_BEFORE_CREATED", f"{n} shop_orders má updated_at < created_at", "", where="shop_orders.updated_at"))

    return out


# ---------------------------------------------------------------------------
# E) Schéma
# ---------------------------------------------------------------------------
def check_schema(cur):
    out = []

    cur.execute("""
        SELECT t.TABLE_NAME FROM information_schema.TABLES t
        WHERE t.TABLE_SCHEMA=DATABASE() AND t.TABLE_TYPE='BASE TABLE'
        AND NOT EXISTS (
            SELECT 1 FROM information_schema.KEY_COLUMN_USAGE k
            WHERE k.TABLE_SCHEMA=t.TABLE_SCHEMA AND k.TABLE_NAME=t.TABLE_NAME AND k.CONSTRAINT_NAME='PRIMARY'
        )
    """)
    rows = cur.fetchall()
    if rows:
        names = [r["TABLE_NAME"] for r in rows]
        out.append(finding("warning", "DB_TABLE_NO_PK", f"{len(names)} tabulek bez primárního klíče",
                            ", ".join(names), where="information_schema", fix_hint="Ověřit, jestli je to záměr (log/agregační tabulka), nebo chybějící PK."))

    cur.execute("""
        SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' AND (ENGINE IS NULL OR ENGINE<>'InnoDB')
    """)
    rows = cur.fetchall()
    if rows:
        sample = ", ".join(f"{r['TABLE_NAME']}({r['ENGINE']})" for r in rows[:MAX_SAMPLE])
        out.append(finding("warning", "DB_NON_INNODB_ENGINE", f"{len(rows)} tabulek nemá engine InnoDB", sample, where="information_schema"))

    cur.execute("""
        SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE() AND (TABLE_COLLATION NOT LIKE 'utf8mb4%%' OR TABLE_COLLATION IS NULL)
    """)
    rows = cur.fetchall()
    if rows:
        sample = ", ".join(f"{r['TABLE_NAME']}({r['TABLE_COLLATION']})" for r in rows[:MAX_SAMPLE])
        out.append(finding("critical", "DB_NON_UTF8MB4_TABLE", f"{len(rows)} tabulek NENÍ utf8mb4", sample, where="information_schema",
                            fix_hint="Riziko poškození 4-bajtových znaků (emoji apod.) a chyb při JOINu s utf8mb4 tabulkami."))

    cur.execute("""
        SELECT TABLE_COLLATION, COUNT(*) c FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_COLLATION LIKE 'utf8mb4%%' GROUP BY TABLE_COLLATION
    """)
    collations = cur.fetchall()
    if len(collations) > 1:
        mix = ", ".join(f"{r['TABLE_COLLATION']}: {r['c']}×" for r in collations)
        out.append(finding("info", "DB_MIXED_UTF8MB4_COLLATION", "Databáze míchá víc utf8mb4 kolací",
                            f"{mix} - JOIN mezi sloupci s různou kolací je v MySQL 8 dovolený, ale méně efektivní a u ORDER BY/porovnání může dát nečekané pořadí.",
                            where="information_schema", fix_hint="Sjednotit na jednu kolaci (typicky tu novější, utf8mb4_0900_ai_ci) při vhodné příležitosti - není urgentní."))

    # TEXT/JSON sloupce s radky > 1MB
    cur.execute("""
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND DATA_TYPE IN ('text','mediumtext','longtext','json')
    """)
    big_cols = [(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()]
    for table, col in big_cols:
        try:
            cur.execute(f"SELECT id FROM `{table}` WHERE LENGTH(`{col}`) > 1048576 LIMIT {MAX_SAMPLE}")
            rows = cur.fetchall()
        except Exception:
            continue
        if rows:
            ids = ", ".join(f"#{r['id']}" for r in rows)
            out.append(finding("info", "DB_LARGE_TEXT_COLUMN", f"{table}.{col} má řádky > 1 MB",
                                f"Ukázka ID: {ids}", where=f"{table}.{col}"))

    # AUTO_INCREMENT nad 50 % limitu typu
    cur.execute("""
        SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.COLUMN_TYPE, t.AUTO_INCREMENT
        FROM information_schema.COLUMNS c
        JOIN information_schema.TABLES t ON t.TABLE_SCHEMA=c.TABLE_SCHEMA AND t.TABLE_NAME=c.TABLE_NAME
        WHERE c.TABLE_SCHEMA=DATABASE() AND c.EXTRA='auto_increment' AND t.AUTO_INCREMENT IS NOT NULL
    """)
    type_max = {"tinyint": 127, "smallint": 32767, "mediumint": 8388607, "int": 2147483647, "bigint": 9223372036854775807}
    for r in cur.fetchall():
        is_unsigned = "unsigned" in (r["COLUMN_TYPE"] or "")
        base_max = type_max.get(r["DATA_TYPE"])
        if not base_max:
            continue
        limit = base_max * 2 + 1 if is_unsigned else base_max
        if r["AUTO_INCREMENT"] and r["AUTO_INCREMENT"] > limit * 0.5:
            out.append(finding("warning", "DB_AUTO_INCREMENT_HALFWAY", f"{r['TABLE_NAME']}.{r['COLUMN_NAME']} AUTO_INCREMENT přes 50 % limitu typu {r['COLUMN_TYPE']}",
                                f"Aktuálně {r['AUTO_INCREMENT']} / max {limit}", where=f"{r['TABLE_NAME']}.{r['COLUMN_NAME']}"))

    # index na _id sloupcich pouzitych v api/*.py WHERE/JOIN, ale bez indexu v DB
    cur.execute("""
        SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE() AND COLUMN_NAME LIKE '%%\\_id' AND COLUMN_NAME<>'id'
        AND DATA_TYPE IN ('int','bigint','smallint','mediumint','varchar','char')
    """)
    id_cols = [(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()]
    cur.execute("""
        SELECT DISTINCT TABLE_NAME, COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE()
    """)
    indexed = {(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()}
    api_text = _read_api_source()
    unindexed_used = []
    for table, col in id_cols:
        if (table, col) in indexed:
            continue
        # jen sloupce, ktere se v api/ kodu skutecne pouzivaji v dotazu (WHERE/JOIN na dany nazev)
        if re.search(rf"\b{re.escape(col)}\b\s*=", api_text) or re.search(rf"WHERE.*{re.escape(col)}", api_text, re.I):
            unindexed_used.append(f"{table}.{col}")
    if unindexed_used:
        sample = ", ".join(unindexed_used[:MAX_SAMPLE])
        more = f" … a dalších {len(unindexed_used)-MAX_SAMPLE}" if len(unindexed_used) > MAX_SAMPLE else ""
        out.append(finding("info", "DB_UNINDEXED_ID_COLUMN", f"{len(unindexed_used)} _id sloupců použitých v api/ WHERE/JOIN kódu bez indexu",
                            f"Heuristika (regex hledání jména sloupce u WHERE/rovnítka v api/*.py) - u malé DB (max ~3000 řádků/tabulka) nemusí bolet teď, ale roste s daty. {sample}{more}",
                            where="information_schema.STATISTICS", fix_hint="Přidat index při reálném nárůstu dat / zpomalení dotazu."))

    return out


def _read_api_source():
    parts = []
    for fname in sorted(os.listdir(API_DIR)):
        if fname.endswith(".py"):
            try:
                with open(os.path.join(API_DIR, fname), encoding="utf-8") as f:
                    parts.append(f.read())
            except OSError:
                pass
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# F) Drift migrací
# ---------------------------------------------------------------------------
_CREATE_TABLE_RE = re.compile(r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?([a-zA-Z0-9_]+)`?", re.I)
_ALTER_TABLE_RE = re.compile(r"ALTER\s+TABLE\s+`?([a-zA-Z0-9_]+)`?", re.I)
# "ADD COLUMN IF NOT EXISTS <col>" (bezny vzor v tomhle repu, viz
# sql/2026-08-24_crm_lead_message_email_status.sql) - bez volitelne
# skupiny IF NOT EXISTS by regex omylem chytil slovo "IF" jako nazev
# sloupce (ozkouseno naostro, opraveno po prvnim behu skriptu).
_ADD_COLUMN_RE = re.compile(r"ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([a-zA-Z0-9_]+)`?", re.I)
_ADD_INDEX_RE = re.compile(r"ADD\s+(?:UNIQUE\s+)?(?:INDEX|KEY)\s+`?([a-zA-Z0-9_]+)`?", re.I)
_RENAME_TABLE_RE = re.compile(r"RENAME\s+TABLE\s+`?([a-zA-Z0-9_]+)`?\s+TO\s+`?([a-zA-Z0-9_]+)`?", re.I)


def _build_rename_map(sql_dir):
    """Vsechny RENAME TABLE X TO Y napric sql/ - reseno POZOR na
    retezeni (A->B, pak pozdeji B->C = A ma nakonec zit jako C).
    Skutecny pripad v repu: news_items -> announcement_items (bez
    tohohle by check_migration_drift hlasil "news_items v DB chybi",
    presne opak reality - viz AGENTS_LOG.md zivy nalez pri prvnim
    behu skriptu)."""
    rename_map = {}
    for fname in sorted(os.listdir(sql_dir)):
        if not fname.endswith(".sql"):
            continue
        try:
            with open(os.path.join(sql_dir, fname), encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            continue
        for m in _RENAME_TABLE_RE.finditer(raw):
            rename_map[m.group(1)] = m.group(2)
    # rozresit retezce (A->B->C se stane primo A->C), max 10 kroku jako pojistka proti cyklu
    resolved = {}
    for old in rename_map:
        cur_name = old
        for _ in range(10):
            nxt = rename_map.get(cur_name)
            if not nxt or nxt == cur_name:
                break
            cur_name = nxt
        resolved[old] = cur_name
    return resolved

# Znamy cekajici stav (bot3 zadani) - nehlasit jako novy prekvapivy nalez,
# jen potvrdit, ze skript vidi presne to, co uz Robert cekal.
KNOWN_PENDING_MIGRATIONS = {
    "2026-09-02_turntable_deactivated_at.sql": "deactivated_at sloupec pro product_turntable_frames - čeká na Roberta (viz check_turntable_orphan_dirs).",
}


def check_migration_drift(cur):
    out = []
    cur.execute("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()")
    live_tables = {r["TABLE_NAME"] for r in cur.fetchall()}
    cur.execute("""
        SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE()
    """)
    live_columns = {(r["TABLE_NAME"], r["COLUMN_NAME"]) for r in cur.fetchall()}
    cur.execute("SELECT DISTINCT TABLE_NAME, INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE()")
    live_indexes = {(r["TABLE_NAME"], r["INDEX_NAME"]) for r in cur.fetchall()}

    sql_files = sorted(f for f in os.listdir(SQL_DIR) if f.endswith(".sql"))
    tables_created_by_sql = set()
    rename_map = _build_rename_map(SQL_DIR)

    for fname in sql_files:
        path = os.path.join(SQL_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            continue
        # remeslo_* migrace bezi proti JINE DB (viz api/db_migrate.py pojistka) - drift proti hlavni DB by byl zavadejici
        if re.search(r"\bremeslo_[a-z_]+\b", raw, re.I) and "remeslo_" in fname.lower():
            continue

        body_wo_comments = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("--"))

        for m in _CREATE_TABLE_RE.finditer(body_wo_comments):
            created_as = m.group(1)
            if created_as.startswith("remeslo_"):
                continue
            # tabulka mohla byt POZDEJI prejmenovana jinou migraci (viz
            # news_items -> announcement_items) - kontrolovat existenci
            # pod FINALNIM jmenem, ne pod puvodnim CREATE TABLE nazvem
            t = rename_map.get(created_as, created_as)
            tables_created_by_sql.add(t)
            if t not in live_tables:
                note = KNOWN_PENDING_MIGRATIONS.get(fname)
                rename_note = f" (přejmenováno na '{t}' pozdější migrací)" if t != created_as else ""
                out.append(finding(
                    "info" if note else "warning", "DB_MIGRATION_TABLE_MISSING",
                    f"Tabulka '{t}' je v {fname}{rename_note}, ale v DB chybí",
                    note or "CREATE TABLE z SQL souboru v repu nemá odpovídající tabulku v živé DB.",
                    where=f"sql/{fname}", fix_hint=f"Spustit: api/venv/bin/python api/db_migrate.py sql/{fname}" if not note else None,
                ))

        for stmt_m in _ALTER_TABLE_RE.finditer(body_wo_comments):
            t = stmt_m.group(1)
            if t.startswith("remeslo_") or t not in live_tables:
                continue
            # vezmi text ALTER prikazu od tohohle bodu az po dalsi strednik (nebo konec)
            start = stmt_m.end()
            semi = body_wo_comments.find(";", start)
            stmt_body = body_wo_comments[start: semi if semi != -1 else None]

            for cm in _ADD_COLUMN_RE.finditer(stmt_body):
                col = cm.group(1)
                if (t, col) not in live_columns:
                    note = KNOWN_PENDING_MIGRATIONS.get(fname)
                    out.append(finding(
                        "info" if note else "warning", "DB_MIGRATION_COLUMN_MISSING",
                        f"Sloupec '{t}.{col}' je v {fname}, ale v DB chybí",
                        note or "ALTER TABLE ADD COLUMN z SQL souboru v repu nemá odpovídající sloupec v živé DB.",
                        where=f"sql/{fname}", fix_hint=f"Spustit: api/venv/bin/python api/db_migrate.py sql/{fname}" if not note else None,
                    ))
            for im in _ADD_INDEX_RE.finditer(stmt_body):
                idx = im.group(1)
                if (t, idx) not in live_indexes:
                    out.append(finding("info", "DB_MIGRATION_INDEX_MISSING", f"Index '{idx}' na {t} je v {fname}, ale v DB nenalezen (podle jména)",
                                        "Může být i falešný nález, pokud MySQL index pojmenoval jinak, než je v SQL - ověřit ručně.",
                                        where=f"sql/{fname}"))

    # opacny smer - tabulky v DB, ktere zadny sql/*.sql soubor nezaklada
    # (heuristika: hleda CREATE TABLE <jmeno> v CELEM obsahu sql/, ne per-soubor)
    all_sql_text = ""
    for fname in sql_files:
        try:
            with open(os.path.join(SQL_DIR, fname), encoding="utf-8") as f:
                all_sql_text += f.read() + "\n"
        except OSError:
            pass
    undocumented = sorted(t for t in live_tables if t not in tables_created_by_sql and not t.startswith("remeslo_") and not t.startswith("_zzz_remeslo_"))
    if undocumented:
        sample = ", ".join(undocumented[:MAX_SAMPLE])
        more = f" … a dalších {len(undocumented)-MAX_SAMPLE}" if len(undocumented) > MAX_SAMPLE else ""
        out.append(finding("info", "DB_TABLE_NO_MIGRATION_FILE", f"{len(undocumented)} tabulek v DB nemá odpovídající CREATE TABLE v žádném sql/*.sql",
                            f"Mohou být založené ručně (mimo repo) nebo jménem, co regex CREATE_TABLE_RE nezachytil. {sample}{more}",
                            where="sql/", fix_hint="Není nutně chyba - jen info pro přehled o tom, co repo dokumentuje vs. co reálně existuje."))

    out.extend(_check_unused_tables(cur, live_tables))
    return out


def _check_unused_tables(cur, live_tables):
    """Tabulky, na jejichz jmeno api/*.py kod vubec nikde neodkazuje -
    kandidati na uklid (bot3 explicitne zadal, patri do Schema sekce
    v zadani, tady spolu s drift kontrolou at se soubor necte 2x)."""
    api_text = _read_api_source()
    unused = []
    for t in sorted(live_tables):
        if t.startswith("remeslo_") or t.startswith("_zzz_remeslo_"):
            continue
        if not re.search(rf"\b{re.escape(t)}\b", api_text):
            cur.execute(f"SELECT COUNT(*) c FROM `{t}`")
            n = cur.fetchone()["c"]
            unused.append(f"{t} ({n} řádků)")
    out = []
    if unused:
        sample = "; ".join(unused[:MAX_SAMPLE])
        more = f" … a dalších {len(unused)-MAX_SAMPLE}" if len(unused) > MAX_SAMPLE else ""
        out.append(finding("info", "DB_TABLE_UNUSED_IN_API", f"{len(unused)} tabulek, na které žádný api/*.py soubor jménem neodkazuje",
                            f"Heuristika (hledání jména tabulky jako celého slova v api/) - nezahrnuje scripts/ ani webapp/ přímé volání. {sample}{more}",
                            where="api/", fix_hint="Ověřit ručně před jakýmkoli úklidem - může se používat jen ve scripts/ nebo přes jinou DB."))

    # zvlast zminit stale remeslo_* tabulky v hlavni DB (zjisteno pri pruzkumu teto suity)
    cur.execute("""
        SELECT TABLE_NAME, TABLE_ROWS, UPDATE_TIME, CREATE_TIME FROM information_schema.TABLES
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'remeslo_%%' ORDER BY TABLE_NAME
    """)
    remeslo_rows = cur.fetchall()
    if remeslo_rows:
        total_rows = sum(r["TABLE_ROWS"] or 0 for r in remeslo_rows)
        oldest = min(r["CREATE_TIME"] for r in remeslo_rows if r["CREATE_TIME"])
        out.append(finding(
            "info", "DB_STALE_REMESLO_TABLES",
            f"{len(remeslo_rows)} remeslo_* tabulek žije i v HLAVNÍ DB ({total_rows} řádků celkem), přestože Řemeslo má od 2026-08 vlastní DB",
            f"REMESLO_DB_NAME (samostatná DB) je aktivní produkční cesta (viz api/remeslo_verification_worker.py, api/db_migrate_remeslo.py) - "
            f"tyhle tabulky v hlavní DB ({os.environ.get('DB_NAME', '?')}) vypadají jako pozůstatek z doby PŘED přesunem (nejstarší CREATE_TIME {oldest}), "
            "UPDATE_TIME je u všech NULL (žádný zaznamenaný zápis od založení).",
            where="information_schema (remeslo_*)",
            fix_hint="Ověřit s Robertem, jestli je bezpečné tyhle tabulky v hlavní DB smazat (cutover na REMESLO_DB je zjevně dokončený) - výrazný úklid schématu.",
        ))
    return out


# ---------------------------------------------------------------------------
# G) Testovací účty v produkční DB (bot3, 2026-09-02)
# ---------------------------------------------------------------------------
TEST_ACCOUNT_EMAIL_PATTERNS = (
    "%@test.local", "%@example.invalid", "%example.com",
    "tmp-%", "tmp_%", "bot%@%",
)


def check_test_accounts(cur):
    """Zivy nalez bot3 (2026-09-02): id 662 bot8-test-scene@test.local
    (role ADMIN, zalozeno 2026-08-20), 765 bot13-mobile-...@test.local
    (remeslnik) - testovaci ucty botu, ktere se dostaly do produkcni DB
    a zustaly tam. Trvala hlidka, at se to nevraci - NIC nemaze (mazani
    662/765 je na Robertovi, produkcni data), jen hlasi."""
    out = []
    where_sql = " OR ".join(["email LIKE %s"] * len(TEST_ACCOUNT_EMAIL_PATTERNS))
    cur.execute(
        f"SELECT id, email, role, created_at FROM app_users WHERE {where_sql} ORDER BY id",
        TEST_ACCOUNT_EMAIL_PATTERNS,
    )
    for r in cur.fetchall():
        severity = "critical" if r["role"] == "admin" else "warning"
        out.append(finding(
            severity, "DB_TEST_ACCOUNT_IN_PROD",
            f"Testovací účet v produkční DB: {r['email']} (role {r['role']})",
            f"app_users.id={r['id']}, založeno {r['created_at']}" + (
                " - role ADMIN, vyšší dopad případného zneužití" if r["role"] == "admin" else ""
            ),
            where=f"app_users.id={r['id']}",
            fix_hint="Ověřit s Robertem, jestli jde smazat (produkční data - nemazat automaticky/bez schválení).",
        ))
    return out


# ---------------------------------------------------------------------------
# H) Velikosti tabulek (pro bot14 trend)
# ---------------------------------------------------------------------------
def compute_stats(cur):
    cur.execute("""
        SELECT TABLE_NAME, TABLE_ROWS, ROUND((DATA_LENGTH+INDEX_LENGTH)/1024/1024, 2) AS size_mb
        FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE'
        ORDER BY (DATA_LENGTH+INDEX_LENGTH) DESC LIMIT 15
    """)
    top15 = [{"table": r["TABLE_NAME"], "rows": r["TABLE_ROWS"], "size_mb": float(r["size_mb"] or 0)} for r in cur.fetchall()]
    cur.execute("SELECT COUNT(*) c FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()")
    total_tables = cur.fetchone()["c"]
    return {"total_tables": total_tables, "top15_tables_by_size": top15}


# ---------------------------------------------------------------------------
def collect():
    findings = []
    ram_warning = ram_watchdog_alert_active()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if ram_warning:
                findings.append(finding("warning", "QA_RAM_WATCHDOG_ACTIVE", "RAM watchdog alert byl aktivní při startu suity",
                                         "Dotazy proti malé DB (max ~3000 řádků/tabulka) - pokračuji, ale je to varování k zaznamenání.", where="/run/ram-watchdog-alert"))
            findings.extend(check_orphans(cur))
            findings.extend(check_unmapped_id_columns(cur))
            findings.extend(_db_files_missing_on_disk(cur))
            findings.extend(_disk_files_without_db(cur))
            findings.extend(check_turntable_orphan_dirs(cur))
            findings.extend(check_duplicates(cur))
            findings.extend(check_consistency(cur))
            findings.extend(check_schema(cur))
            findings.extend(check_migration_drift(cur))
            findings.extend(check_test_accounts(cur))
            stats = compute_stats(cur)
    finally:
        conn.close()
    return findings, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    run_suite("db_integrity", collect, args.json)


if __name__ == "__main__":
    main()
