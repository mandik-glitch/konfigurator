#!/opt/konfigurator/api/venv/bin/python
"""Dealersky program, krok 2 (bot5, 2026-10-02): CTENI provizi - api/dealer_commissions.py nad DOCASNYMI tabulkami.

Provize se pro kazdou objednavku pocita z dat, ktera uz v DB jsou (zaplaceni, expedice, storno, vratky) - zadne hooky, zadne nove tabulky, nic se nezapisuje.
Docasne kopie (CREATE TEMPORARY TABLE ... LIKE, bez FK): dealers, dealer_rates, shop_orders, shop_order_items, shop_returns, shop_return_items, shop_order_status_history,
app_settings. Ostre shop_products, content_categories a app_users se jen ctou. Pro endpointy Flask test client (spojeni vlakna vidi docasne tabulky).

Cast A  zaklad a sazby (cena polozek bez DPH a bez dopravy/platby, sazba dealer > kategorie > nastaveni, smazany produkt)
Cast B  stavy a 14denni lhuta od POZDEJSIHO z zaplaceni a expedice, castecna platba, storno, nastaveni dnu
Cast C  vraceni: otevrena blokuje, zamitnuta se ignoruje, vyrizena s refund kraci pomerne po polozkach, cela = zrusena, strop na cenu polozky
Cast D  panel dealera a admin (opravneni, jen vlastni objednavky, bez osobnich udaju zakaznika, souhrn, filtry, strankovani, nic se nezapisuje)
Cast E  mutace (puvodni/chybne verze logiky MUSI selhat)
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator \\
  /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-02_dealeri_testy/test_provize.py     (kandidati: --setenv=DEALERS_PY=... --setenv=COMMISSIONS_PY=...)
"""
import ast
import datetime
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
DEALERS_PY = os.environ.get("DEALERS_PY")
COMMISSIONS_PY = os.environ.get("COMMISSIONS_PY")
MIGRACE = os.path.join(REPO, "sql", "2026-10-02_dealers.sql")
if DEALERS_PY or COMMISSIONS_PY:
    tmp = tempfile.mkdtemp(prefix="kand_provize_")
    for env, jmeno in ((DEALERS_PY, "dealers.py"), (COMMISSIONS_PY, "dealer_commissions.py")):
        if env:
            shutil.copy(env, os.path.join(tmp, jmeno))
    sys.path.insert(0, tmp)
sys.path.insert(1 if (DEALERS_PY or COMMISSIONS_PY) else 0, API)

import pymysql  # noqa: E402
import app as appmod  # noqa: E402

for sekce in ("dealeri", "dealer_provize", "dealer_klice"):
    if sekce not in appmod.PERMISSION_SECTIONS:
        appmod.PERMISSION_SECTIONS = tuple(appmod.PERMISSION_SECTIONS) + (sekce,)
import dealers  # noqa: E402
import dealer_commissions as dc  # noqa: E402
dealers.log_audit = lambda *a, **k: None

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def ostre():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


TABULKY = ("dealers", "dealer_rates", "shop_orders", "shop_order_items", "shop_returns", "shop_return_items", "shop_order_status_history", "app_settings")
CIL = ("dealers", "dealer_rates", "shop_orders", "shop_order_items", "shop_returns", "shop_return_items", "shop_order_status_history")


def stav_ostrych():
    c = ostre()
    try:
        with c.cursor() as cur:
            out = {}
            for t in ("shop_orders", "shop_order_items", "shop_returns", "shop_order_status_history", "app_settings"):
                cur.execute(f"SELECT COUNT(*) AS n FROM `{t}`")
                out[t] = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM audit_log")
            out["audit"] = cur.fetchone()["n"]
            return out
    finally:
        c.close()


pred = stav_ostrych()
wrap = appmod.get_conn()
real = object.__getattribute__(wrap, "_real")
SQL = open(MIGRACE, encoding="utf-8").read()
PRIKAZY = [s.strip() for s in "\n".join(l for l in SQL.splitlines() if not l.strip().startswith("--")).split(";") if s.strip()]
FK_RE = re.compile(r",\s*CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", re.I)


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith("SELECT") else cur.rowcount
    real.commit()
    return out


try:
    with real.cursor() as cur:
        cur.execute("CREATE TEMPORARY TABLE `_tpl_app_settings` LIKE `app_settings`")
        cur.execute("INSERT INTO `_tpl_app_settings` SELECT * FROM `app_settings`")
        cur.execute("CREATE TEMPORARY TABLE `app_settings` LIKE `_tpl_app_settings`")
        cur.execute("INSERT INTO `app_settings` SELECT * FROM `_tpl_app_settings`")
        cur.execute("DELETE FROM app_settings WHERE setting_key='dealer_commission_hold_days' OR setting_key='dealer_commission_default_pct'")
        for t in ("shop_orders", "shop_order_items", "shop_returns", "shop_return_items", "shop_order_status_history"):
            cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
            cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
            cur.execute(f"SHOW CREATE TABLE `{t}`")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
        for s in PRIKAZY:
            if s.startswith("CREATE TABLE IF NOT EXISTS dealers") or s.startswith("CREATE TABLE IF NOT EXISTS dealer_rates"):
                cur.execute(FK_RE.sub("", re.sub(r"^CREATE TABLE IF NOT EXISTS", "CREATE TEMPORARY TABLE", s)))
        cur.execute("SHOW COLUMNS FROM shop_orders LIKE 'dealer_id'")
        if not cur.fetchone():
            alter = re.sub(r",\s*ADD CONSTRAINT\s+\w+\s+FOREIGN KEY\s*\([^)]*\)\s*REFERENCES\s+\w+\s*\([^)]*\)\s*ON DELETE\s+\w+", "", [s for s in PRIKAZY if s.startswith("ALTER TABLE shop_orders")][0])
            cur.execute("SHOW CREATE TABLE shop_orders")
            assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE")
            cur.execute(alter)
    real.commit()

    SEKUNDA = datetime.timedelta(seconds=1)
    NOW = datetime.datetime(2026, 10, 2, 12, 0, 0)
    DEN = datetime.timedelta(days=1)
    CITR = [0]

    def dealer(name, ref, comm=10.0, user_id=None, status="active"):
        sql("INSERT INTO dealers (ref_code, name, status, default_commission_pct, user_id) VALUES (%s,%s,%s,%s,%s)", (ref, name, status, comm, user_id))
        return sql("SELECT * FROM dealers WHERE ref_code=%s", (ref,))[0]

    def objednavka(d, status="expedovana", path="our", total=1210.0, paid_at=None, paid_total=None, is_test=0, created=None, shipping=0.0):
        CITR[0] += 1
        sql("INSERT INTO shop_orders (order_number, status, customer_name, customer_email, customer_phone, delivery_address, total_czk, shipping_price_czk, payment_price_czk, payment_received_at, "
            "payment_received_total_czk, dealer_id, order_path, is_test, created_at) VALUES (%s,%s,'Jan Novak','zakaznik@example.cz','+420777111222','Ulice 1, Praha',%s,%s,50,%s,%s,%s,%s,%s,%s)",
            (f"PRV{CITR[0]:05d}", status, total, shipping, paid_at, (paid_total if paid_total is not None else (total if paid_at else 0)), d["id"] if d else None, path, is_test, created or NOW - 30 * DEN))
        return sql("SELECT id FROM shop_orders ORDER BY id DESC LIMIT 1")[0]["id"]

    def polozka(oid, product_id, qty, line, name="Polozka"):
        sql("INSERT INTO shop_order_items (order_id, product_id, product_name_snapshot, unit_price_czk, qty, line_total_czk) VALUES (%s,%s,%s,%s,%s,%s)", (oid, product_id, name, round(line / qty, 2), qty, line))
        return sql("SELECT id FROM shop_order_items ORDER BY id DESC LIMIT 1")[0]["id"]

    def historie(oid, status, when):
        sql("INSERT INTO shop_order_status_history (order_id, status, changed_at) VALUES (%s,%s,%s)", (oid, status, when))

    def vratka(oid, status, resolution, polozky, typ="odstoupeni"):
        CITR[0] += 1
        sql("INSERT INTO shop_returns (order_id, return_number, return_type, status, resolution) VALUES (%s,%s,%s,%s,%s)", (oid, f"VR{CITR[0]:05d}", typ, status, resolution))
        rid = sql("SELECT id FROM shop_returns ORDER BY id DESC LIMIT 1")[0]["id"]
        for item_id, qty, cena in polozky:
            sql("INSERT INTO shop_return_items (return_id, order_item_id, qty, unit_price_czk) VALUES (%s,%s,%s,%s)", (rid, item_id, qty, cena))
        return rid

    # produkty v ruznych kategoriich (jen cteni): P150 = produkt v PODKATEGORII kategorie 149, PJINA = produkt mimo strom 149
    p150 = sql("SELECT p.id, p.category_id FROM shop_products p JOIN content_categories cc ON cc.id=p.category_id WHERE cc.parent_id=149 LIMIT 1")
    kandidati = sql("SELECT id, category_id FROM shop_products WHERE category_id IS NOT NULL AND category_id <> 149 ORDER BY category_id DESC LIMIT 400")
    pjina = None
    with real.cursor() as cc_:
        for k in kandidati:
            retez, _skryta = dealers._category_chain(cc_, k["category_id"])
            if 149 not in [x["id"] for x in retez]:
                pjina = k
                break
    assert p150 and pjina, "chybi vzorove produkty (podkategorie 149 / mimo 149)"
    P150, PJINA = p150[0]["id"], pjina["id"]

    with real.cursor() as c:
        D = dealer("Alfa", "alfa000001", comm=10.0)
        HOLD = dc.hold_days(c)
        over("0 vychozi lhuta na vraceni je 14 dni (app_settings.dealer_commission_hold_days neni nastaveno)", HOLD == 14, HOLD)

        def vyhodnot(oid, now=NOW, dealer_row=None):
            o = sql("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id FROM shop_orders WHERE id=%s", (oid,))[0]
            return dc.order_commission(c, o, dealer_row or sql("SELECT * FROM dealers WHERE id=%s", (o["dealer_id"],))[0], dc.hold_days(c), now)

        # ======================================================================================================== A) zaklad a sazby
        print("== A zaklad a sazby")
        o1 = objednavka(D, total=1815.0, shipping=300.0, paid_at=NOW - 40 * DEN)
        polozka(o1, PJINA, 1, 1000.0, "A")
        polozka(o1, PJINA, 1, 500.0, "B")
        historie(o1, "expedovana", NOW - 35 * DEN)
        r = vyhodnot(o1)
        over("A1 zaklad = soucet cen polozek bez DPH (1 500), doprava 300 a platba 50 se do zakladu NEpocitaji, vychozi sazba dealera 10 % -> provize 150,00",
             r["base_net_czk"] == 1500.0 and r["commission_czk"] == 150.0 and all(x["commission_pct"] == 10.0 for x in r["lines"]), r)
        sql("INSERT INTO dealer_rates (dealer_id, category_id, discount_pct, commission_pct) VALUES (%s,149,NULL,15)", (D["id"],))      # sazba na NADRAZENE kategorii
        o2 = objednavka(D, paid_at=NOW - 40 * DEN)
        polozka(o2, P150, 1, 1000.0, "v kategorii 150 (podkategorie 149)")
        polozka(o2, PJINA, 1, 500.0, "jina kategorie")
        historie(o2, "expedovana", NOW - 35 * DEN)
        r = vyhodnot(o2)
        over("A2 sazba kategorie 149 (15 %) plati i pro podkategorii 150: 1 000 x 15 % + 500 x 10 % (vychozi) = 200,00", r["commission_czk"] == 200.0 and [x["commission_pct"] for x in r["lines"]] == [15.0, 10.0], r)
        o3 = objednavka(D, paid_at=NOW - 40 * DEN)
        polozka(o3, None, 1, 400.0, "smazany produkt")
        polozka(o3, 987654321, 1, 600.0, "neexistujici produkt")
        historie(o3, "expedovana", NOW - 35 * DEN)
        r = vyhodnot(o3)
        over("A3 produkt, ktery uz neexistuje (product_id NULL / smazany): sazba dealera (10 %), provize 100,00", r["commission_czk"] == 100.0, r)
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_commission_default_pct','12.5') ON DUPLICATE KEY UPDATE setting_value='12.5'")
        D2 = dealer("Bez sazby", "bezs000002", comm=None)
        o4 = objednavka(D2, paid_at=NOW - 40 * DEN)
        polozka(o4, PJINA, 1, 800.0)
        historie(o4, "expedovana", NOW - 35 * DEN)
        over("A4 dealer bez vlastni sazby a bez kategorie: plati nastaveni (app_settings.dealer_commission_default_pct 12,5 %): 800 -> 100,00", vyhodnot(o4)["commission_czk"] == 100.0, vyhodnot(o4))
        sql("DELETE FROM app_settings WHERE setting_key='dealer_commission_default_pct'")
        over("A5 ...a bez nastaveni 10 %: 800 -> 80,00", vyhodnot(o4)["commission_czk"] == 80.0, vyhodnot(o4))
        over("A6 vysledek obsahuje jen ciselne a stavove udaje: zadny e-mail, jmeno, telefon ani adresa zakaznika", not re.search(r"zakaznik@|Jan Novak|\+420|Ulice 1", json.dumps(vyhodnot(o1))), None)

        # ======================================================================================================== B) stavy a lhuta
        print("== B stavy a 14denni lhuta")

        def stav(**kw):
            oid = objednavka(D, **{k: v for k, v in kw.items() if k in ("status", "total", "paid_at", "paid_total", "path")})
            polozka(oid, PJINA, 1, 1000.0)
            for st, kdy in kw.get("hist", []):
                historie(oid, st, kdy)
            return vyhodnot(oid, kw.get("now", NOW))

        s = stav(status="nova")
        over("B1 nezaplacena -> ceka_na_zaplaceni (hold_until None)", s["status"] == "ceka_na_zaplaceni" and s["hold_until"] is None and s["commission_czk"] == 100.0, s)
        s = stav(paid_at=NOW - 3 * DEN, paid_total=500.0, status="potvrzena")
        over("B2 castecna uhrada (prijato 500 z 1 210) se NEpocita jako zaplaceno -> ceka_na_zaplaceni", s["status"] == "ceka_na_zaplaceni", s)
        s = stav(paid_at=NOW - 3 * DEN, paid_total=1209.5, status="potvrzena")
        over("B3 tolerance 1 Kc na zaokrouhleni (prijato 1 209,50 z 1 210) = zaplaceno -> ceka_na_expedici", s["status"] == "ceka_na_expedici", s)
        s = stav(paid_at=NOW - 20 * DEN, status="pripravit")
        over("B4 zaplaceno, ale neexpedovano -> ceka_na_expedici (lhuta jeste nezacala, hold_until None)", s["status"] == "ceka_na_expedici" and s["hold_until"] is None, s)
        s = stav(paid_at=NOW - 20 * DEN, hist=[("expedovana", NOW - 5 * DEN)])
        over("B5 lhuta bezi od POZDEJSIHO z (zaplaceno 20 dni, expedovano 5 dni zpet) = od expedice: hold_until = expedice + 14 dni -> ceka_na_lhutu",
             s["status"] == "ceka_na_lhutu" and s["hold_until"] == (NOW - 5 * DEN + 14 * DEN).isoformat(), s)
        s = stav(paid_at=NOW - 5 * DEN, hist=[("expedovana", NOW - 30 * DEN)])
        over("B6 expedovano driv nez zaplaceno (zaplaceno 5 dni zpet): lhuta od zaplaceni -> ceka_na_lhutu s hold_until = zaplaceno + 14", s["status"] == "ceka_na_lhutu" and s["hold_until"] == (NOW - 5 * DEN + 14 * DEN).isoformat(), s)
        s = stav(paid_at=NOW - 40 * DEN, hist=[("expedovana", NOW - 30 * DEN)])
        over("B7 obe udalosti starsi nez 14 dni -> k_vyplate", s["status"] == "k_vyplate" and s["commission_czk"] == 100.0, s)
        konec = NOW - 14 * DEN
        s1 = stav(paid_at=NOW - 40 * DEN, hist=[("expedovana", konec + SEKUNDA * 60)])
        s2 = stav(paid_at=NOW - 40 * DEN, hist=[("expedovana", konec - SEKUNDA * 60)])
        over("B8 hranice: o minutu pred koncem lhuty jeste ceka_na_lhutu, o minutu po konci k_vyplate", s1["status"] == "ceka_na_lhutu" and s2["status"] == "k_vyplate", (s1["status"], s2["status"]))
        s = stav(paid_at=NOW - 40 * DEN, hist=[("fakturovana", NOW - 30 * DEN)])
        over("B9 stav 'fakturovana' bez zaznamu 'expedovana' se taky bere jako expedovano", s["status"] == "k_vyplate", s)
        s = stav(paid_at=NOW - 40 * DEN, hist=[("expedovana", NOW - 30 * DEN), ("expedovana", NOW - 2 * DEN)])
        over("B10 vic zaznamu expedice: bere se prvni (nejstarsi)", s["status"] == "k_vyplate", s)
        sql("INSERT INTO app_settings (setting_key, setting_value) VALUES ('dealer_commission_hold_days','7') ON DUPLICATE KEY UPDATE setting_value='7'")
        s = stav(paid_at=NOW - 20 * DEN, hist=[("expedovana", NOW - 10 * DEN)])
        over("B11 delka lhuty je nastavitelna (app_settings.dealer_commission_hold_days = 7): expedice pred 10 dny -> k_vyplate", s["status"] == "k_vyplate", s)
        sql("DELETE FROM app_settings WHERE setting_key='dealer_commission_hold_days'")
        s = stav(paid_at=NOW - 20 * DEN, hist=[("expedovana", NOW - 10 * DEN)])
        over("B12 ...a s vychozimi 14 dny stejna objednavka ceka_na_lhutu", s["status"] == "ceka_na_lhutu", s)
        s = stav(status="zrusena", paid_at=NOW - 40 * DEN, hist=[("expedovana", NOW - 30 * DEN)])
        over("B13 zrusena objednavka (i zaplacena a expedovana) -> zrusena, reason order_cancelled, provize 0", s["status"] == "zrusena" and s["reason"] == "order_cancelled" and s["commission_czk"] == 0.0, s)
        s = stav(status="zrusena")
        over("B14 zrusena ma prednost pred nezaplacenou", s["status"] == "zrusena", s)

        # ======================================================================================================== C) vraceni
        print("== C vraceni")

        def k_vyplate(polozky):
            oid = objednavka(D, paid_at=NOW - 40 * DEN)
            ids = [polozka(oid, pid, qty, line) for pid, qty, line in polozky]
            historie(oid, "expedovana", NOW - 30 * DEN)
            return oid, ids

        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        over("C0 vychozi stav pokusne objednavky: k_vyplate, provize 100", vyhodnot(oid)["status"] == "k_vyplate" and vyhodnot(oid)["commission_czk"] == 100.0, vyhodnot(oid))
        for st in ("pozadovano", "posuzovano", "schvaleno", "prijato"):
            oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
            vratka(oid, st, None, [(it, 1, 500.0)])
            r = vyhodnot(oid)
            over(f"C1 otevrene vraceni ({st}) blokuje vyplatu -> ceka_na_vraceni", r["status"] == "ceka_na_vraceni", r["status"])
        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        vratka(oid, "zamitnuto", "rejected", [(it, 1, 500.0)])
        vratka(oid, "zruseno", None, [(it, 1, 500.0)])
        r = vyhodnot(oid)
        over("C2 zamitnute a zrusene vraceni se ignoruje -> k_vyplate, provize beze zmeny", r["status"] == "k_vyplate" and r["commission_czk"] == 100.0 and r["refunded_net_czk"] == 0.0, r)
        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(it, 1, 500.0)])
        r = vyhodnot(oid)
        over("C3 vyrizene vraceni s vracenim penez (1 z 2 ks po 500) kraci provizi POMERNE: (1 000 - 500) x 10 % = 50,00, vraceno 500", r["status"] == "k_vyplate" and r["commission_czk"] == 50.0 and r["refunded_net_czk"] == 500.0 and r["lines"][0]["refunded_czk"] == 500.0, r)
        for res in ("repair", "rejected", None):
            oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
            vratka(oid, "vyrizeno", res, [(it, 1, 500.0)])
            over(f"C4 vyrizene vraceni bez vraceni penez (resolution {res}) provizi nekrati", vyhodnot(oid)["commission_czk"] == 100.0, vyhodnot(oid))
        oid, (i1, i2) = k_vyplate([(PJINA, 1, 1000.0), (P150, 1, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(i2, 1, 1000.0)])
        r = vyhodnot(oid)
        over("C5 vraceni jen jedne polozky kraci jen jeji provizi (sazba kategorie 15 %): 1 000 x 10 % + 0 = 100,00, stav k_vyplate", r["commission_czk"] == 100.0 and r["status"] == "k_vyplate" and r["refunded_net_czk"] == 1000.0, r)
        oid, (i1, i2) = k_vyplate([(PJINA, 1, 1000.0), (P150, 1, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(i1, 1, 1000.0)])
        r = vyhodnot(oid)
        over("C6 ...a vraceni polozky v kategorii 150 (15 %): zustane 1 000 x 15 % = 150,00 z druhe polozky (10 % z vracene se neodecita)", r["commission_czk"] == 150.0, r)
        oid, (i1, i2) = k_vyplate([(PJINA, 1, 1000.0), (PJINA, 1, 500.0)])
        vratka(oid, "vyrizeno", "refund", [(i1, 1, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(i2, 1, 500.0)])
        r = vyhodnot(oid)
        over("C7 vsechny polozky vracene -> zrusena, reason fully_returned, provize 0", r["status"] == "zrusena" and r["reason"] == "fully_returned" and r["commission_czk"] == 0.0 and r["refunded_net_czk"] == 1500.0, r)
        oid, (it,) = k_vyplate([(PJINA, 1, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(it, 3, 1000.0)])
        r = vyhodnot(oid)
        over("C8 vracena castka se omezi cenou polozky (3 x 1 000 z radku za 1 000 -> 1 000), nikdy zaporna provize", r["refunded_net_czk"] == 1000.0 and r["commission_czk"] == 0.0 and r["status"] == "zrusena", r)
        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(it, 1, 250.0)])
        vratka(oid, "vyrizeno", "refund", [(it, 1, 250.0)])
        r = vyhodnot(oid)
        over("C9 vic vyrizenych vraceni stejne polozky se scitaji: 250 + 250 = 500 -> provize 50,00", r["refunded_net_czk"] == 500.0 and r["commission_czk"] == 50.0, r)
        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [])
        over("C10 vraceni bez radku polozek (jen hlavicka) provizi nekrati a nespadne", vyhodnot(oid)["commission_czk"] == 100.0, vyhodnot(oid))
        oid, (it,) = k_vyplate([(PJINA, 2, 1000.0)])
        vratka(oid, "vyrizeno", "refund", [(it, 1, 500.0)])
        vratka(oid, "posuzovano", None, [(it, 1, 500.0)])
        r = vyhodnot(oid)
        over("C11 pri otevrenem dalsim vraceni se ceka (ceka_na_vraceni), uz vyrizena cast je ale odectena (provize 50)", r["status"] == "ceka_na_vraceni" and r["commission_czk"] == 50.0, r)

        # ======================================================================================================== D) panel a admin
        print("== D panel dealera a admin")
        uzivatele = [r_["id"] for r_ in sql("SELECT id FROM app_users WHERE role='user' AND active=1 ORDER BY id LIMIT 3")]
        admin_id = sql("SELECT id FROM app_users WHERE role='admin' AND active=1 LIMIT 1")[0]["id"]
        sql("UPDATE dealers SET user_id=%s WHERE id=%s", (uzivatele[0], D["id"]))
        Dx = dealer("Cizi dealer", "cizi000003", comm=20.0, user_id=uzivatele[1])
        sql("DELETE FROM shop_returns")
        sql("DELETE FROM shop_return_items")
        sql("DELETE FROM shop_order_items")
        sql("DELETE FROM shop_order_status_history")
        sql("DELETE FROM shop_orders")
        sql("DELETE FROM dealer_rates")
        sql("UPDATE dealers SET default_commission_pct=10 WHERE id=%s", (D["id"],))

        def hotova(d, line, paid_ago=40, ship_ago=30, **kw):
            oid = objednavka(d, paid_at=NOW - paid_ago * DEN if paid_ago is not None else None, created=kw.get("created"), is_test=kw.get("is_test", 0), path=kw.get("path", "our"), status=kw.get("status", "expedovana"))
            polozka(oid, PJINA, 1, line)
            if ship_ago is not None:
                historie(oid, "expedovana", NOW - ship_ago * DEN)
            return oid

        a1 = hotova(D, 1000.0, created=NOW - 60 * DEN)          # k_vyplate 100
        a2 = hotova(D, 2000.0, created=NOW - 50 * DEN, paid_ago=None, ship_ago=None, status="nova")   # ceka_na_zaplaceni 200
        a3 = hotova(D, 500.0, created=NOW - 10 * DEN, paid_ago=3, ship_ago=2)                           # ceka_na_lhutu 50
        a4 = hotova(D, 300.0, created=NOW - 45 * DEN, status="zrusena")                                 # zrusena
        a5 = hotova(D, 900.0, created=NOW - 20 * DEN, path="dealer")                                    # cesta dealer: bez provize
        a6 = hotova(D, 999.0, is_test=1)                                                                  # testovaci - vynechat
        a7 = hotova(Dx, 4000.0)                                                                           # cizi dealer
        a8 = hotova(None, 700.0)                                                                          # bez dealera
        pocty_pred = {t: sql(f"SELECT COUNT(*) AS n FROM `{t}`")[0]["n"] for t in CIL}
        dealer_k = appmod.app.test_client()
        with dealer_k.session_transaction() as s_:
            s_["user_id"] = uzivatele[0]
        monkey_now = dc._now
        dc._now = lambda: NOW                       # pevny cas pro deterministicke stavy v endpointech
        try:
            r = dealer_k.get("/api/dealer/commissions")
            j = r.get_json()
            ids = [x["order_id"] for x in j["commissions"]]
            over("D1 panel /api/dealer/commissions: jen jeho objednavky cesty 'our' (4: k_vyplate, zaplaceni, lhuta, zrusena), bez cesty dealer, testovaci, cizich a bez dealera; nejnovejsi prvni",
                 r.status_code == 200 and ids == [a3, a4, a2, a1], (r.status_code, ids, [a3, a4, a2, a1]))
            over("D2 souhrn podle stavu: k_vyplate 1 x 100, ceka_na_zaplaceni 1 x 200, ceka_na_lhutu 1 x 50, zrusena 1 x 0", j["summary"] == {"k_vyplate": {"orders": 1, "commission_czk": 100.0}, "ceka_na_zaplaceni": {"orders": 1, "commission_czk": 200.0},
                 "ceka_na_lhutu": {"orders": 1, "commission_czk": 50.0}, "zrusena": {"orders": 1, "commission_czk": 0.0}}, j["summary"])
            over("D3 v odpovedi jsou jen cisla a stavy: zadny e-mail, jmeno, telefon ani adresa zakaznika; je tam hold_days a Cache-Control no-store", not re.search(r"zakaznik@|Jan Novak|\\+420|Ulice 1", r.get_data(as_text=True)) and j["hold_days"] == 14 and r.headers.get("Cache-Control") == "private, no-store", None)
            jo = dealer_k.get("/api/dealer/orders").get_json()
            over("D4 /api/dealer/orders: stejne objednavky + objednavka cesty 'dealer' (status None, provize 0, reason no_commission_path), stale bez testovacich a cizich",
                 {x["order_id"] for x in jo["orders"]} == {a1, a2, a3, a4, a5} and next(x for x in jo["orders"] if x["order_id"] == a5)["status"] is None and next(x for x in jo["orders"] if x["order_id"] == a5)["reason"] == "no_commission_path", jo["total"])
            over("D5 filtr ?status=k_vyplate vrati jen tu jednu, souhrn zustane za vsechny stavy", [x["order_id"] for x in dealer_k.get("/api/dealer/commissions?status=k_vyplate").get_json()["commissions"]] == [a1]
                 and len(dealer_k.get("/api/dealer/commissions?status=k_vyplate").get_json()["summary"]) == 4, None)
            vyber = dealer_k.get(f"/api/dealer/commissions?from={(NOW - 55 * DEN).date()}&to={(NOW - 40 * DEN).date()}").get_json()
            over("D6 filtr ?from=&to= podle data objednavky (vcetne obou dnu): a2 (50 dni zpet) a a4 (45 dni zpet)", {x["order_id"] for x in vyber["commissions"]} == {a2, a4}, [x["order_id"] for x in vyber["commissions"]])
            st1 = dealer_k.get("/api/dealer/commissions?page=1&page_size=3").get_json()
            st2 = dealer_k.get("/api/dealer/commissions?page=2&page_size=3").get_json()
            over("D7 strankovani: 3 + 1 radek, total 4, souhrn za vsechny; neplatna stranka/velikost spadne na vychozi, velikost max 200",
                 len(st1["commissions"]) == 3 and len(st2["commissions"]) == 1 and st1["total"] == 4 and dealer_k.get("/api/dealer/commissions?page=abc&page_size=-4").status_code == 200
                 and dealer_k.get("/api/dealer/commissions?page_size=5000").get_json()["page_size"] == 200, (len(st1["commissions"]), len(st2["commissions"])))
            det = dealer_k.get(f"/api/dealer/commissions/{a1}")
            over("D8 detail vlastni objednavky: radky s nazvem, cenou, sazbou a provizi; cizi/testovaci/bez provize/neexistujici objednavka 404",
                 det.status_code == 200 and det.get_json()["commission"]["lines"][0]["commission_czk"] == 100.0 and all(dealer_k.get(f"/api/dealer/commissions/{x}").status_code == 404 for x in (a5, a6, a7, a8, 99999999)), det.status_code)
            ciz = appmod.app.test_client()
            with ciz.session_transaction() as s_:
                s_["user_id"] = uzivatele[2]
            nepr = appmod.app.test_client()
            over("D9 ucet bez dealera: 404 not_a_dealer na vsech 3 endpointech; nepřihlášený 401", all(ciz.get(u).status_code == 404 and ciz.get(u).get_json()["code"] == "not_a_dealer" for u in ("/api/dealer/commissions", "/api/dealer/orders", f"/api/dealer/commissions/{a1}"))
                 and all(nepr.get(u).status_code == 401 for u in ("/api/dealer/commissions", "/api/dealer/orders")), None)
            admin = appmod.app.test_client()
            with admin.session_transaction() as s_:
                s_["user_id"] = admin_id
            ra = admin.get("/api/admin/dealer-commissions").get_json()
            over("D10 admin: provize VSECH dealeru (vcetne cizi 4 000 x 20 %), souhrn k_vyplate = 100 + 800, ?dealer_id= filtruje, jmeno dealera v radcich",
                 ra["summary"]["k_vyplate"] == {"orders": 2, "commission_czk": 900.0} and any(x["dealer_name"] == "Cizi dealer" and x["commission_czk"] == 800.0 for x in ra["commissions"])
                 and {x["dealer_id"] for x in admin.get(f"/api/admin/dealer-commissions?dealer_id={Dx['id']}").get_json()["commissions"]} == {Dx["id"]}, ra["summary"])
            over("D11 admin: detail provize libovolneho dealera, objednavka cesty dealer / bez dealera / neexistujici -> 404; zakaznik (role user) a nepřihlášený nemaji pristup (403/401)",
                 admin.get(f"/api/admin/dealer-commissions/{a7}").get_json()["commission"]["dealer_name"] == "Cizi dealer" and all(admin.get(f"/api/admin/dealer-commissions/{x}").status_code == 404 for x in (a5, a8, 99999999))
                 and dealer_k.get("/api/admin/dealer-commissions").status_code == 403 and nepr.get("/api/admin/dealer-commissions").status_code == 401, None)
        finally:
            dc._now = monkey_now
        pocty_po = {t: sql(f"SELECT COUNT(*) AS n FROM `{t}`")[0]["n"] for t in CIL}
        over("D12 cteni nic nezapisuje: pocty radku vsech docasnych tabulek jsou po vsech dotazech stejne", pocty_po == pocty_pred, (pocty_pred, pocty_po))
        over("D13 modul nema zadny zapis ani e-mail: bez INSERT/UPDATE/DELETE, commit, send_email", not re.search(r"\bINSERT\b|\bUPDATE\b|\bDELETE\b|\.commit\(|send_email|smtp", open(dc.__file__, encoding="utf-8").read(), re.I), None)

        # ======================================================================================================== E) mutace
        print("== E mutace")
        modul = open(dc.__file__, encoding="utf-8").read()

        def mutant(stare, nove):
            t = ast.parse(modul)
            node = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == "order_commission")
            src = ast.get_source_segment(modul, node)
            assert src.count(stare) == 1, f"'{stare}' nalezeno {src.count(stare)}x"
            ns = dict(vars(dc))
            exec(src.replace(stare, nove), ns)
            return ns["order_commission"]

        def porovnej(mut, oid):
            o = sql("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id FROM shop_orders WHERE id=%s", (oid,))[0]
            d = sql("SELECT * FROM dealers WHERE id=%s", (o["dealer_id"],))[0]
            return mut(c, o, d, 14, NOW)["status"], dc.order_commission(c, o, d, 14, NOW)["status"]

        sql("DELETE FROM shop_order_items")
        sql("DELETE FROM shop_order_status_history")
        sql("DELETE FROM shop_orders")
        sql("DELETE FROM shop_returns")
        sql("DELETE FROM shop_return_items")
        e1 = objednavka(D, paid_at=NOW - 5 * DEN)
        polozka(e1, PJINA, 1, 1000.0)
        historie(e1, "expedovana", NOW - 30 * DEN)                       # expedovano driv, zaplaceno 5 dni zpet -> lhuta od zaplaceni
        mut, spravne = porovnej(mutant("max(paid_at, shipped_at)", "shipped_at"), e1)
        over("E1 mutace: lhuta jen od expedice (ne od pozdejsiho z obou) by vyplatila provizi pred koncem lhuty -> test B6 ji zachyti", mut == "k_vyplate" and spravne == "ceka_na_lhutu", (mut, spravne))
        e2 = objednavka(D, paid_at=NOW - 40 * DEN)
        i2 = polozka(e2, PJINA, 1, 1000.0)
        historie(e2, "expedovana", NOW - 30 * DEN)
        vratka(e2, "posuzovano", None, [(i2, 1, 1000.0)])
        mut, spravne = porovnej(mutant("elif open_return:", "elif False:"), e2)
        over("E2 mutace: otevrene vraceni neblokuje vyplatu -> test C1 ji zachyti", mut == "k_vyplate" and spravne == "ceka_na_vraceni", (mut, spravne))
        e3 = objednavka(D, status="zrusena", paid_at=NOW - 40 * DEN)
        polozka(e3, PJINA, 1, 1000.0)
        historie(e3, "expedovana", NOW - 30 * DEN)
        mut, spravne = porovnej(mutant('if order["status"] == "zrusena":', "if False:"), e3)
        over("E3 mutace: zrusena objednavka se vyplaci -> test B13 ji zachyti", mut == "k_vyplate" and spravne == "zrusena", (mut, spravne))
        e4 = objednavka(D, paid_at=NOW - 40 * DEN, paid_total=100.0)
        polozka(e4, PJINA, 1, 1000.0)
        historie(e4, "expedovana", NOW - 30 * DEN)
        mut, spravne = porovnej(mutant("fully_paid = paid_at is not None and float(order[\"payment_received_total_czk\"] or 0) >= float(order[\"total_czk\"] or 0) - 1.0", "fully_paid = paid_at is not None"), e4)
        over("E4 mutace: castecna uhrada se bere jako zaplaceno -> test B2 ji zachyti", mut == "k_vyplate" and spravne == "ceka_na_zaplaceni", (mut, spravne))
        e5 = objednavka(D, paid_at=NOW - 40 * DEN)
        i5 = polozka(e5, PJINA, 2, 1000.0)
        historie(e5, "expedovana", NOW - 30 * DEN)
        vratka(e5, "vyrizeno", "refund", [(i5, 1, 500.0)])
        o5 = sql("SELECT id, order_number, status, created_at, payment_received_at, payment_received_total_czk, total_czk, order_path, dealer_id FROM shop_orders WHERE id=%s", (e5,))[0]
        m_ = mutant("item_commission = round((net - back) * pct / 100.0, 2)", "item_commission = round(net * pct / 100.0, 2)")(c, o5, D, 14, NOW)
        over("E5 mutace: vracene zbozi se z provize neodecita -> test C3 ji zachyti", m_["commission_czk"] == 100.0 and dc.order_commission(c, o5, D, 14, NOW)["commission_czk"] == 50.0, m_["commission_czk"])
finally:
    with real.cursor() as cur:
        for t in TABULKY + tuple(f"_tpl_{x}" for x in ("shop_orders", "shop_order_items", "shop_returns", "shop_return_items", "shop_order_status_history", "app_settings")):
            cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
    real.commit()

po = stav_ostrych()
over("ostre tabulky (objednavky, polozky, vratky, historie, nastaveni, audit_log) jsou po testu beze zmeny", po == pred, (pred, po))
ok = sum(vysl)
print(f"\nVYSLEDEK dealersky program krok 2 - provize (cteni): {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
