#!/opt/konfigurator/api/venv/bin/python
"""ZIVE OVERENI (jen cteni): cena varianty v KOSIKU/OBJEDNAVCE vs. to, co vidi zakaznik (verejny JSON).
Pro kazdou kartu se sestavami porovna (cena, montaz, boxy) z `_assembly_price_components` (product_assemblies.py -
volaji ji kosik i objednavka) s GET /api/shop/products/<id>/assemblies (price_czk, montaz_cena_czk, boxy_cena_czk),
tj. s tim, co zobrazuje product.html. Ocekavani: vsechny varianty vcetne zastupcu SHODNE (bot3 2026-10-01: "kosik = verejny JSON").
Nic nezapisuje (jen SELECT + GET). Pred nasazenim opravy ukaze 11 rozdilu u zastupcu (montaz/boxy None v kosiku).

Spusteni (DB pres systemd, verejna cast pres sit):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-01_zastupce_montaz_testy/overeni_kosik_vs_verejny_json.py
Kandidat pred nasazenim: PRODUCT_ASSEMBLIES_PY=/cesta/k/product_assemblies.py (verejny JSON je pak porad zivy)
"""
import ast
import json
import math
import os
import sys
import time
import urllib.request

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
PA = os.environ.get("PRODUCT_ASSEMBLIES_PY", os.path.join(HERE, "..", "..", "api", "product_assemblies.py"))
BASE = os.environ.get("VEREJNY_WEB", "https://autovestavby.logiman.cz")

with open(PA, encoding="utf-8") as f:
    strom = ast.parse(f.read())
fns = [n for n in strom.body if isinstance(n, ast.FunctionDef)
       and n.name in ("_num_or_none", "_eurobox_soucet_czk", "_assembly_price_components")]
assert len(fns) == 3, [n.name for n in fns]
ns = {"json": json, "math": math}
exec(compile(ast.Module(body=fns, type_ignores=[]), "product_assemblies", "exec"), ns)
komp = ns["_assembly_price_components"]

c = pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                    database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor)
kosik, karty = {}, []
with c.cursor() as cur:
    cur.execute("SELECT id, price_czk_placeholder FROM shop_products WHERE id IN "
                "(SELECT shop_product_id FROM product_assemblies WHERE shop_product_id IS NOT NULL AND is_master=1) "
                "AND active=1 AND is_archived=0 ORDER BY id")
    karty = cur.fetchall()
    for k in karty:
        cur.execute("SELECT id, is_master FROM product_assemblies WHERE shop_product_id=%s ORDER BY id", (k["id"],))
        for a in cur.fetchall():
            kosik[(k["id"], a["id"])] = (komp(cur, a["id"], k["id"], float(k["price_czk_placeholder"])), bool(a["is_master"]))
c.rollback()
c.close()


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "bot5-overeni/1.0 (read-only)"})
    with urllib.request.urlopen(req, timeout=30) as f:
        return json.loads(f.read().decode("utf-8"))


rozdily, shodne, mastery = [], 0, 0
for k in karty:
    j = get(f"{BASE}/api/shop/products/{k['id']}/assemblies")
    time.sleep(0.3)
    for a in j.get("assemblies", []):
        key = (k["id"], a["id"])
        if key not in kosik:
            rozdily.append((k["id"], a["id"], "verejna varianta nema sestavu v DB"))
            continue
        vypocet, je_master = kosik[key]
        verejne = (a.get("price_czk"), a.get("montaz_cena_czk"), a.get("boxy_cena_czk"))
        verejne = (None if verejne[0] is None else round(float(verejne[0])), verejne[1], verejne[2])
        v_kosiku = (None if vypocet["base_czk"] is None else round(float(vypocet["base_czk"])),
                    vypocet["montaz_czk"], vypocet["boxy_czk"])
        mastery += je_master
        if verejne == v_kosiku:
            shodne += 1
        else:
            rozdily.append((k["id"], a["id"], "ZASTUPCE" if je_master else "varianta", "verejne=%s" % (verejne,), "kosik=%s" % (v_kosiku,)))

print(f"karet: {len(karty)} | variant srovnano: {shodne + len(rozdily)} (z toho zastupcu {mastery}) | shodne: {shodne} | rozdilne: {len(rozdily)}")
for r in rozdily[:30]:
    print("  ROZDIL", r)
print("KOSIK == VEREJNY JSON u vsech variant" if not rozdily else "KOSIK SE ROZCHAZI S VEREJNYM JSON")
sys.exit(0 if not rozdily else 1)
