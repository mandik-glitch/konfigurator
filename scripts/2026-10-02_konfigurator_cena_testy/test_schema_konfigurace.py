#!/opt/konfigurator/api/venv/bin/python
"""Schema konfigurace v kosiku/objednavce (bot5, 2026-10-02): sql/2026-10-02_konfigurace_kosik_objednavka.sql.

Migrace se zkousi na DOCASNYCH kopiich (CREATE TEMPORARY TABLE ... LIKE, stejne sloupce a indexy, bez cizich klicu) tabulek shop_cart_items, shop_order_items a
product_assemblies - do ostrych dat se nezapisuje. Pred aplikaci do ostre DB se na kopie provedou prikazy z migrace, po aplikaci uz kopie nova pole maji a testuje
se jen vysledny stav. Overuje se hlavne to, co by se mohlo rozbit:
  * bezne radky kosiku se dal slucuji presne jako dosud (cart.py: INSERT ... ON DUPLICATE KEY UPDATE qty=qty+VALUES(qty)),
  * dve ruzne konfigurace stejne sestavy dostanou samostatne radky, stejna konfigurace se slouci,
  * existujici radky dostanou config_hash '' (ne NULL), nova pole jsou nullable / maji vychozi hodnotu a stary INSERT bez nich dal funguje,
  * migrace nic nemaze (zadne DROP TABLE/DELETE/TRUNCATE; jediny DROP je INDEX nahrazeny v TOMTEZ prikazu novym).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_konfigurator_cena_testy/test_schema_konfigurace.py
"""
import os
import re
import sys

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
SQL_FILE = os.path.join(HERE, "..", "..", "sql", "2026-10-02_konfigurace_kosik_objednavka.sql")
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def spoj():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych(c):
    with c.cursor() as cur:
        out = {}
        for t in ("shop_cart_items", "shop_order_items", "product_assemblies"):
            cur.execute(f"SHOW COLUMNS FROM `{t}`")
            out[t] = [r["Field"] for r in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
            out[t + "_n"] = cur.fetchone()["n"]
        return out


SQL = open(SQL_FILE, encoding="utf-8").read()
TELO = "\n".join(l for l in SQL.splitlines() if not l.strip().startswith("--"))
PRIKAZY = [s.strip() for s in TELO.split(";") if s.strip()]
TABULKY = ("shop_cart_items", "shop_order_items", "product_assemblies")

ostre = spoj()
pred = stav_ostrych(ostre)
c = spoj()
try:
    with c.cursor() as cur:
        for t in TABULKY:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
            cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
            assert cur.fetchone()["n"] == 0
        # radky ve STAREM tvaru (pred migraci) - overi se, ze po ALTER dostanou config_hash ''
        cur.execute("SHOW COLUMNS FROM shop_cart_items LIKE 'config_hash'")
        uz_migrovano = cur.fetchone() is not None
        if not uz_migrovano:
            cur.execute("INSERT INTO shop_cart_items (user_id, product_id, qty, assembly_id) VALUES (1, 10, 3, 0), (1, 11, 1, 5)")
            for s in PRIKAZY:
                cur.execute(s)           # ALTER nad DOCASNYMI kopiemi (stejny nazev tabulky, docasna zastini ostrou)
    c.commit()

    with c.cursor() as cur:
        cur.execute("SHOW COLUMNS FROM shop_cart_items")
        k = {r["Field"]: r for r in cur.fetchall()}
        over("1 shop_cart_items: configuration_json MEDIUMTEXT NULL, config_hash CHAR(16) NOT NULL s vychozi hodnotou ''",
             k["configuration_json"]["Type"] == "mediumtext" and k["configuration_json"]["Null"] == "YES" and k["config_hash"]["Type"] == "char(16)" and k["config_hash"]["Null"] == "NO" and k["config_hash"]["Default"] == "", {x: k[x] for x in ("configuration_json", "config_hash")})
        cur.execute("SHOW INDEX FROM shop_cart_items")
        idx = {}
        for r in cur.fetchall():
            idx.setdefault(r["Key_name"], []).append((r["Seq_in_index"], r["Column_name"], r["Non_unique"]))
        nove = sorted(idx.get("uq_shop_cart_user_product_assembly_cfg", []))
        over("2 unikatni klic je (user_id, product_id, assembly_id, config_hash), puvodni klic bez config_hash uz neexistuje",
             [x[1] for x in nove] == ["user_id", "product_id", "assembly_id", "config_hash"] and all(x[2] == 0 for x in nove) and "uq_shop_cart_user_product_assembly" not in idx, idx)
        if not uz_migrovano:
            cur.execute("SELECT product_id, config_hash FROM shop_cart_items ORDER BY product_id")
            over("3 radky vznikle PRED migraci dostanou config_hash '' (ne NULL) a zustanou zachovane", [(r["product_id"], r["config_hash"]) for r in cur.fetchall()] == [(10, ""), (11, "")], None)
            cur.execute("DELETE FROM shop_cart_items")
        else:
            over("3 (migrace uz je v ostre DB - kontrola vychozi hodnoty config_hash jen ze schematu)", k["config_hash"]["Default"] == "", None)

        UPSERT = ("INSERT INTO shop_cart_items (user_id, product_id, qty, cut_pieces_json, cut_service_qty, coupon_code, assembly_id, montaz_zvolena, bez_boxu, montaz_misto) "
                  "VALUES (%s,%s,%s,NULL,NULL,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE qty=qty+VALUES(qty), coupon_code=COALESCE(VALUES(coupon_code), coupon_code), "
                  "montaz_zvolena=VALUES(montaz_zvolena), bez_boxu=VALUES(bez_boxu), montaz_misto=VALUES(montaz_misto)")      # presne jako cart.py (bezny produkt)
        cur.execute(UPSERT, (7, 100, 1, None, 0, 0, 0, None))
        cur.execute(UPSERT, (7, 100, 2, None, 0, 0, 0, None))
        cur.execute(UPSERT, (7, 100, 1, None, 344, 1, 0, "praha"))
        cur.execute(UPSERT, (7, 100, 1, None, 344, 1, 0, "praha"))
        cur.execute("SELECT assembly_id, qty, config_hash FROM shop_cart_items WHERE user_id=7 ORDER BY assembly_id")
        radky = [(r["assembly_id"], r["qty"], r["config_hash"]) for r in cur.fetchall()]
        over("4 bezne radky se slucuji jako dosud: stejny produkt+varianta -> jeden radek (qty se scita), jina varianta (assembly_id) -> samostatny radek",
             radky == [(0, 3, ""), (344, 2, "")], radky)
        CFG = ("INSERT INTO shop_cart_items (user_id, product_id, qty, assembly_id, configuration_json, config_hash) VALUES (%s,%s,%s,%s,%s,%s) "
               "ON DUPLICATE KEY UPDATE qty=qty+VALUES(qty), configuration_json=VALUES(configuration_json)")
        cur.execute(CFG, (7, 200, 1, 900, '{"volby":{"deska":"dub"}}', "aaaaaaaaaaaaaaaa"))
        cur.execute(CFG, (7, 200, 1, 900, '{"volby":{"deska":"buk"}}', "bbbbbbbbbbbbbbbb"))
        cur.execute(CFG, (7, 200, 2, 900, '{"volby":{"deska":"dub"}}', "aaaaaaaaaaaaaaaa"))
        cur.execute("SELECT config_hash, qty, configuration_json FROM shop_cart_items WHERE user_id=7 AND product_id=200 ORDER BY config_hash")
        cfg = [(r["config_hash"], r["qty"]) for r in cur.fetchall()]
        over("5 dve ruzne konfigurace stejne sestavy = dva radky, stejna konfigurace (stejny hash) se slouci (qty 1+2)", cfg == [("aaaaaaaaaaaaaaaa", 3), ("bbbbbbbbbbbbbbbb", 1)], cfg)
        cur.execute("INSERT INTO shop_cart_items (user_id, product_id, qty, assembly_id) VALUES (8, 300, 1, 0)")
        cur.execute("SELECT config_hash, configuration_json FROM shop_cart_items WHERE user_id=8")
        r = cur.fetchone()
        over("6 stary INSERT bez novych poli (starsi kod) dal funguje: config_hash '' a configuration_json NULL", r["config_hash"] == "" and r["configuration_json"] is None, r)
        cur.execute("INSERT INTO shop_cart_items (user_id, product_id, qty, assembly_id) VALUES (8, 300, 1, 0) ON DUPLICATE KEY UPDATE qty=qty+VALUES(qty)")
        cur.execute("SELECT qty FROM shop_cart_items WHERE user_id=8")
        over("7 ...a opakovane pridani stejneho radku stareho tvaru se slouci (qty 2), neprobehne zadny IntegrityError", cur.fetchone()["qty"] == 2, None)

        cur.execute("SHOW COLUMNS FROM shop_order_items")
        o = {r["Field"]: r for r in cur.fetchall()}
        over("8 shop_order_items: configuration_json MEDIUMTEXT NULL, configuration_code VARCHAR(24) NULL", o["configuration_json"]["Type"] == "mediumtext" and o["configuration_json"]["Null"] == "YES"
             and o["configuration_code"]["Type"] == "varchar(24)" and o["configuration_code"]["Null"] == "YES", {x: o[x] for x in ("configuration_json", "configuration_code")})
        cur.execute("INSERT INTO shop_order_items (order_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (1, 'x', 10, 1, 10)")
        cur.execute("SELECT configuration_json, configuration_code FROM shop_order_items")
        r = cur.fetchone()
        over("9 stary INSERT do shop_order_items (bez novych poli) funguje, nova pole jsou NULL", r["configuration_json"] is None and r["configuration_code"] is None, r)
        cur.execute("SHOW COLUMNS FROM product_assemblies LIKE 'live_3d'")
        a = cur.fetchone()
        over("10 product_assemblies.live_3d: TINYINT(1) NOT NULL, vychozi 0 (fail-closed: nic neni zive, dokud to Robert nezaskrtne)", a and a["Type"] == "tinyint(1)" and a["Null"] == "NO" and a["Default"] == "0", a)
    c.commit()

    over("11 migrace ma 3 prikazy (kosik, polozky objednavky, sestavy), zadny DROP TABLE/DELETE/TRUNCATE a jediny DROP je DROP INDEX nahrazeny v TOMTEZ prikazu",
         len(PRIKAZY) == 3 and not re.search(r"\bDROP\s+TABLE\b|\bDELETE\b|\bTRUNCATE\b", TELO, re.I) and len(re.findall(r"\bDROP\b", TELO, re.I)) == 1
         and re.search(r"DROP INDEX uq_shop_cart_user_product_assembly,\s*ADD UNIQUE KEY uq_shop_cart_user_product_assembly_cfg", TELO) is not None, PRIKAZY and [p[:40] for p in PRIKAZY])
    over("12 vsechna nova pole jsou NULLable nebo maji vychozi hodnotu (stary kod je nezna a nevadi mu)", not re.search(r"ADD COLUMN \w+ [^,]*NOT NULL(?! DEFAULT)", TELO), None)
finally:
    with c.cursor() as cur:
        for t in TABULKY:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    c.commit()
    c.close()

po = stav_ostrych(ostre)
over("ostre tabulky (sloupce i pocty radku) jsou po testu beze zmeny", po == pred, (pred, po))
ostre.close()
ok = sum(vysl)
print(f"\nVYSLEDEK schema konfigurace v kosiku/objednavce: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
