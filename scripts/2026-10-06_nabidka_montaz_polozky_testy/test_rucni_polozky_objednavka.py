#!/opt/konfigurator/api/venv/bin/python
"""RUCNI POLOZKY v online nabidce -> OBJEDNAVKA z prijate nabidky (bot8, 2026-10-06): orders.create_order_from_scene_offer s polozkami items[].manual (z katalogu / volny text).
SKUTECNY kod (orders.py) nad DOCASNYMI tabulkami objednavek (shop_orders, shop_order_items, shop_order_status_history, shop_order_number_released + kopie cislovani a nastaveni) - do ostrych dat se
nezapisuje; zakaznik se jen NAJDE (dedup podle e-mailu existujiciho zakaznika, jinak by se zakladal ucet) - kdyz zadny neni, test se preskoci. Katalog (shop_products) se jen cte.
Overuje: rucni polozky jsou v objednavce jako radky (nazev, mnozstvi x pocet kusu sestavy, cena, celkem x pocet kusu), z katalogu s product_id, volny text bez product_id, obycejne radky beze zmeny.
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --working-directory=/opt/konfigurator \\
            api/venv/bin/python3 scripts/2026-10-06_nabidka_montaz_polozky_testy/test_rucni_polozky_objednavka.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import orders as ordersmod  # noqa: E402

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_orders", "shop_order_items", "shop_order_status_history", "app_users", "shop_customers", "shop_order_number_sequence"):
                cur.execute(f"SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `{t}`") if t != "shop_order_number_sequence" else cur.execute(f"SELECT COUNT(*) AS n, 0 AS m FROM `{t}`")
                r = cur.fetchone()
                out[t] = (r["n"], r["m"])
            return out
    finally:
        c.close()


PRED = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
TEMP_LIKE = ("shop_orders", "shop_order_items", "shop_order_status_history", "shop_order_number_released")
TEMP_COPY = ("shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


try:
    with real.cursor() as cur:
        for t in TEMP_COPY:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
        for t in TEMP_LIKE:
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        for t in TEMP_LIKE + TEMP_COPY:
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
    real.commit()

    zname = sql("SELECT c.email FROM shop_customers c JOIN app_users u ON u.id = c.user_id WHERE c.email IS NOT NULL AND c.email <> '' LIMIT 1")
    if not zname:
        print("PRESKOCENO: v databazi neni zadny existujici zakaznik pro dedup (objednavka by zakladala ucet)")
        over("O0 test objednavky preskocen (zadny existujici zakaznik)", True)
    else:
        prod = sql("SELECT id FROM shop_products WHERE glb_file IS NOT NULL AND is_archived=0 ORDER BY id LIMIT 1")[0]["id"]
        items = [
            {"name": "Řádek ze scény", "dim": "-", "qty": "4 ks", "unit_price": 100, "total": 400, "mesh_group": 1},
            {"name": "Zaměření a doprava", "dim": "1× výjezd", "qty": "3 ks", "unit_price": 1500, "total": 4500, "manual": {"typ": "text", "popis": "Popis", "obrazky": []}},
            {"name": "Šuplíkový box", "dim": "800 × 600 mm", "qty": "2 ks", "unit_price": 1234.5, "total": 2469, "product_id": prod, "layer": "produkt", "manual": {"typ": "katalog", "popis": "", "model": True}},
            {"name": "Zkrácený profil", "dim": "1000 mm", "qty": "1 ks", "unit_price": 50, "total": 50, "product_id": prod, "layer": "produkt", "manual": {"typ": "katalog", "popis": ""}},
        ]
        offer = {"id": 900201, "offer_number": "TESTRPO", "items": json.dumps(items, ensure_ascii=False), "offer_options": json.dumps({"show_qr": True})}
        with real.cursor() as cur:
            oid, onum = ordersmod.create_order_from_scene_offer(cur, offer, name="Test Jednatel", company_ico="12345678", company_name="Test Firma s.r.o.", company_dic="CZ12345678",
                                                                company_address="Testovací 1, Praha", contact_email=zname[0]["email"], contact_phone="123456789", total_czk=99999, qty_multiplier=2)
        real.commit()
        radky = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (oid,))
        pod = {r["product_name_snapshot"]: r for r in radky}
        over("O1 objednavka ma vsechny 4 radky (1 obycejny + 3 rucni) ve stejnem poradi", [r["product_name_snapshot"] for r in radky] == ["Řádek ze scény", "Zaměření a doprava", "Šuplíkový box", "Zkrácený profil - 1000 mm"], [r["product_name_snapshot"] for r in radky])
        r1 = pod["Řádek ze scény"]
        over("O2 obycejny radek beze zmeny: 4 ks x 2 = 8, cena 100, celkem 800", r1["qty"] == 8 and float(r1["unit_price_czk"]) == 100 and float(r1["line_total_czk"]) == 800 and r1["product_id"] is None, r1)
        r2 = pod["Zaměření a doprava"]
        over("O3 rucni volny text: bez product_id, 3 ks x 2 = 6, cena 1 500, celkem 9 000", r2["product_id"] is None and r2["qty"] == 6 and float(r2["unit_price_czk"]) == 1500 and float(r2["line_total_czk"]) == 9000, r2)
        r3 = pod["Šuplíkový box"]
        over("O4 rucni z katalogu: product_id, 2 ks x 2 = 4, cena 1 234,5, celkem 4 938 (2 469 x 2), rozmer s krizkem se do delky neprevadi", r3["product_id"] == prod and r3["qty"] == 4 and float(r3["unit_price_czk"]) == 1234.5 and float(r3["line_total_czk"]) == 4938 and r3["length_mm"] is None, r3)
        r4 = pod["Zkrácený profil - 1000 mm"]
        over("O5 rucni z katalogu s rozmerem '1000 mm': delka 1000 mm se zapise a pripoji k nazvu (stejne jako u ostatnich radku nabidky)", float(r4["length_mm"]) == 1000 and r4["qty"] == 2, r4)
        hlavicka = sql("SELECT total_czk, source_scene_offer_id FROM shop_orders WHERE id=%s", (oid,))[0]
        over("O6 hlavicka objednavky: celkova castka prevzata od volajiciho (99 999), vazba na nabidku", float(hlavicka["total_czk"]) == 99999 and hlavicka["source_scene_offer_id"] == 900201, hlavicka)
finally:
    with real.cursor() as cur:
        for t in TEMP_LIKE + TEMP_COPY:
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
    real.commit()

PO = stav_ostrych()
over("Z ostre tabulky objednavek, polozek, historie, uzivatelu, zakazniku a cislovani jsou beze zmeny", PRED == PO, (PRED, PO))
ok = sum(vysl)
print(f"\nVYSLEDEK rucni polozky -> objednavka z nabidky: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
