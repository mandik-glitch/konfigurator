#!/opt/konfigurator/api/venv/bin/python
"""Kosik se SKUTECNYM kodem (cart._fetch_cart_rows) nad skutecnymi kartami sestav (DB jen ke cteni): zastupce + montaz / "bez boxu".
Radky kosiku vznikaji jen v DOCASNE tabulce shop_cart_items (TEMPORARY stini ostrou, stejne indexy, bez FK) - do ostrych dat
se nezapisuje (na konci se overi, ze ostra tabulka se nezmenila). Pro kazdou aktivni kartu se zastupcem s cenou montaze:
  cena radku zastupce + montaz   == cena radku bez voleb + montaz z price_summary zastupce
  cena radku zastupce + bez boxu == cena radku bez voleb - soucet euroboxu z kusovniku zastupce
  oboji                          == obe upravy
Mutace: s puvodni (chybnou) _assembly_price_components musi test selhat (cena se NEZMENI, volba tise zmizi).

Spusteni (DB prihlaseni pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-01_zastupce_montaz_testy/test_kosik_zastupce_db.py
Kandidat pred nasazenim: PRODUCT_ASSEMBLIES_PY=/cesta/k/product_assemblies.py ...
"""
import ast
import json
import os
import sys

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(HERE, "..", "..", "api")
sys.path.insert(0, API)
sys.path.insert(0, HERE)
import app  # noqa: E402,F401  (stejne jako gunicorn "app:app"; cart.py se importuje pres nej)
import cart  # noqa: E402
from stara_funkce import STARA_FUNKCE  # noqa: E402  (puvodni chybna verze pro mutaci)

PA = os.environ.get("PRODUCT_ASSEMBLIES_PY", os.path.join(API, "product_assemblies.py"))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def nacti_komp(stara=False):
    with open(PA, encoding="utf-8") as f:
        strom = ast.parse(f.read())
    jmena = ["_num_or_none", "_eurobox_soucet_czk", "_assembly_price_components"]
    fns = [next(n for n in strom.body if isinstance(n, ast.FunctionDef) and n.name == j) for j in jmena]
    if stara:
        fns[2] = ast.parse(STARA_FUNKCE).body[0]
    ns = {"json": json}
    exec(compile(ast.Module(body=fns, type_ignores=[]), "product_assemblies", "exec"), ns)
    return ns["_assembly_price_components"], ns["_eurobox_soucet_czk"]


def connect():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


def pocet_ostrych():
    c = connect()
    try:
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM shop_cart_items")
            return cur.fetchone()["n"]
    finally:
        c.close()


pred = pocet_ostrych()
komp_nova, eurobox = nacti_komp()
komp_stara, _ = nacti_komp(stara=True)

c = connect()
with c.cursor() as cur:
    cur.execute("CREATE TEMPORARY TABLE `_tpl_shop_cart_items` LIKE `shop_cart_items`")
    cur.execute("CREATE TEMPORARY TABLE `shop_cart_items` LIKE `_tpl_shop_cart_items`")
    cur.execute("SELECT COUNT(*) AS n FROM shop_cart_items")
    if cur.fetchone()["n"] != 0:      # pojistka: docasna tabulka musi stinit ostrou (jinak by DELETE nize sahl na ostra data)
        raise SystemExit("ABORT: docasna tabulka shop_cart_items neni prazdna - nestini ostrou, koncim bez zapisu")
    cur.execute("SELECT pa.id AS aid, pa.shop_product_id AS pid, pa.data FROM product_assemblies pa "
                "JOIN shop_products sp ON sp.id = pa.shop_product_id "
                "WHERE pa.is_master=1 AND sp.active=1 AND sp.is_archived=0 AND sp.price_czk_placeholder IS NOT NULL "
                "ORDER BY pa.shop_product_id")
    mastery = cur.fetchall()

karty = []
for m in mastery:
    d = json.loads(m["data"]) if isinstance(m["data"], str) else (m["data"] or {})
    montaz = (d.get("price_summary") or {}).get("montaz_czk")
    if montaz is None:
        continue
    karty.append({"pid": m["pid"], "aid": m["aid"], "montaz": round(montaz), "boxy": eurobox(d.get("bom"))})
print(f"aktivnich karet se zastupcem a cenou montaze: {len(karty)} (z {len(mastery)} zastupcu)")
over("0 existuje aspon 1 karta k otestovani (jinak by test nic neoverovat)", len(karty) >= 1, len(karty))

SCEN = {"plain": (0, 0, 0, None), "montaz": (1, 1, 0, "praha"), "boxy": (1, 0, 1, None), "obe": (1, 1, 1, "slavicin")}
UID = {"plain": 999001, "montaz": 999002, "boxy": 999003, "obe": 999004}


def vloz_a_nacti(karta, komp, pouzit_assembly_id=True):
    """-> {scenar: radek kosiku (dict)} z cart._fetch_cart_rows nad docasnou tabulkou"""
    cart._assembly_price_components = komp
    out = {}
    with c.cursor() as cur:
        cur.execute("DELETE FROM shop_cart_items")
        for nazev, (je_assembly, montaz, boxy, misto) in SCEN.items():
            cur.execute("INSERT INTO shop_cart_items (user_id, product_id, qty, assembly_id, montaz_zvolena, bez_boxu, montaz_misto) "
                        "VALUES (%s,%s,1,%s,%s,%s,%s)",
                        (UID[nazev], karta["pid"], karta["aid"] if je_assembly else 0, montaz, boxy, misto))
    for nazev in SCEN:
        radky = cart._fetch_cart_rows(c, UID[nazev])
        out[nazev] = radky[0] if radky else None
    return out


def over_karta(karta, r, prefix):
    pid = karta["pid"]
    plain, mo, bo, ob = r["plain"], r["montaz"], r["boxy"], r["obe"]
    if not all((plain, mo, bo, ob)):
        over(f"{prefix}{pid} radky kosiku vznikly", False, {k: bool(v) for k, v in r.items()})
        return
    u0 = plain["unit_price_czk"]
    over(f"{prefix}{pid} zastupce + montaz: cena radku = bez voleb + montaz {karta['montaz']} Kc ({u0} -> {mo['unit_price_czk']})",
         abs(mo["unit_price_czk"] - (u0 + karta["montaz"])) < 0.005, (u0, mo["unit_price_czk"], karta["montaz"]))
    over(f"{prefix}{pid} zastupce + montaz: radek nese montaz_zvolena, cenu montaze a misto",
         mo["montaz_zvolena"] and mo["assembly_montaz_czk"] == karta["montaz"] and mo["montaz_misto"] == "praha", {k: mo.get(k) for k in ("montaz_zvolena", "assembly_montaz_czk", "montaz_misto")})
    if karta["boxy"] is not None:
        over(f"{prefix}{pid} zastupce + 'bez boxu': cena radku = bez voleb - boxy {karta['boxy']} Kc ({u0} -> {bo['unit_price_czk']})",
             abs(bo["unit_price_czk"] - (u0 - karta["boxy"])) < 0.005, (u0, bo["unit_price_czk"], karta["boxy"]))
        over(f"{prefix}{pid} zastupce + montaz + 'bez boxu': obe upravy",
             abs(ob["unit_price_czk"] - (u0 - karta["boxy"] + karta["montaz"])) < 0.005, (u0, ob["unit_price_czk"], karta["boxy"], karta["montaz"]))
    over(f"{prefix}{pid} radek BEZ voleb je obycejny produkt (bez assembly_id) s cenou",
         plain["assembly_id"] in (0, None) and u0 > 0, (plain["assembly_id"], u0))


try:
    for karta in karty:
        over_karta(karta, vloz_a_nacti(karta, komp_nova), "")

    # mutace: puvodni chybna funkce -> cena montaze se u zastupce NEPRICTE (volba tise zmizi)
    print("\n--- mutace: puvodni (chybna) _assembly_price_components ---")
    karta = karty[0]
    r = vloz_a_nacti(karta, komp_stara)
    u0, umo = r["plain"]["unit_price_czk"], r["montaz"]["unit_price_czk"]
    over("MUT puvodni verze: zastupce + montaz se NEPRICTE (cena stejna jako bez voleb) - chyba je reprodukovana", abs(umo - u0) < 0.005 and karta["montaz"] > 0, (u0, umo))
finally:
    cart._assembly_price_components = komp_nova
    c.rollback()
    c.close()

po = pocet_ostrych()
over("ostra tabulka shop_cart_items se nezmenila (test nic nezapsal do ostrych dat)", pred == po, (pred, po))
ok = sum(vysl)
print(f"\nVYSLEDEK kosik zastupce (skutecny kod, zive karty): {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
