"""Spolecne pomocne funkce testu karty z konfigurace (bot10, 2026-10-07): spojeni, stinove (TEMPORARY) tabulky a kontrola ostrych dat. Importuje test_karta_db.py a test_karta_route.py."""
import os

import pymysql


def connect():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


KARTY = {30: 4934, 35: 4955, 40: 4954, 41: 4959, 45: 5353}      # karty generatoru podle systemu (app_settings.configurator_products)
CIZI = 5351                                                      # Pricka do Multiboxu: neni konfigurovatelny stul
TABULKY = ["shop_products", "app_settings", "audit_log", "content_categories"]


def stav_ostry(K):
    c = connect()
    try:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM shop_products")
        sp = cur.fetchone()
        cur.execute("SELECT setting_value FROM app_settings WHERE setting_key='configurator_products'")
        reg = (cur.fetchone() or {}).get("setting_value")
        cur.execute("SELECT COUNT(*) n FROM app_settings WHERE setting_key LIKE 'stul\\_karta\\_%' OR setting_key LIKE 'configurator\\_default\\_%'")
        klice = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) n, COALESCE(MAX(id),0) m FROM audit_log")
        au = cur.fetchone()
        cur.execute("SELECT COUNT(*) n FROM shop_products WHERE sku LIKE 'STUL-S%'")
        stul = cur.fetchone()["n"]
        return {"shop_products": (sp["n"], sp["m"]), "registr": reg, "klice_karet": klice, "audit": (au["n"], au["m"]), "stul_karty": stul,
                "adresar": sorted(os.listdir(K.KATALOG_STUL_DIR)) if os.path.isdir(K.KATALOG_STUL_DIR) else None}
    finally:
        c.rollback()
        c.close()


def vloz_radky(cur, tabulka, radky):
    for r in radky:
        sloupce = list(r.keys())
        cur.execute("INSERT INTO " + tabulka + " (" + ",".join("`%s`" % s for s in sloupce) + ") VALUES (" + ",".join(["%s"] * len(sloupce)) + ")", [r[s] for s in sloupce])


def priprav(test, K):
    perm = connect()
    pc = perm.cursor()
    ids = list(KARTY.values()) + [CIZI]
    pc.execute("SELECT * FROM shop_products WHERE id IN (" + ",".join(["%s"] * len(ids)) + ")", ids)
    karty = pc.fetchall()
    pc.execute("SELECT * FROM app_settings WHERE setting_key='configurator_products' OR setting_key LIKE 'stul\\_%'")
    nastaveni = pc.fetchall()
    pc.execute("SELECT * FROM content_categories WHERE id=%s OR parent_id=%s", (K.KORENOVA_KATEGORIE, K.KORENOVA_KATEGORIE))
    kategorie = pc.fetchall()
    perm.rollback()
    perm.close()
    tc = test.cursor()
    for t in TABULKY:                                    # sablona ze struktury OSTRE tabulky (jine jmeno), stinova tabulka z ni: stejne indexy, bez FK (LIKE sama sebe MySQL nepusti, chyba 1066)
        tc.execute("CREATE TEMPORARY TABLE `_tpl_" + t + "` LIKE `" + t + "`")
        tc.execute("CREATE TEMPORARY TABLE `" + t + "` LIKE `_tpl_" + t + "`")
    vloz_radky(tc, "shop_products", karty)
    vloz_radky(tc, "app_settings", nastaveni)
    vloz_radky(tc, "content_categories", kategorie)
    test.commit()
    return {r["id"]: r for r in karty}, {r["id"]: r for r in kategorie}
