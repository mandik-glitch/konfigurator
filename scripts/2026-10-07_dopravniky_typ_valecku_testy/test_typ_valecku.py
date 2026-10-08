#!/opt/konfigurator/api/venv/bin/python
"""Test klice "Typ válečku" u dopravniku: cista logika + kontrola zapsanych dat v DB (jen cteni).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-07_dopravniky_typ_valecku_testy/test_typ_valecku.py"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(REPO, "scripts"))
spec = importlib.util.spec_from_file_location("tv", os.path.join(REPO, "scripts", "2026-10-07_dopravniky_typ_valecku_specs.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)))


over("T1 typ podle prefixu SKU (ocel / vroubkovany / hladky)", M.typ_podle_sku("16.10.01.051.0600.2000.0") == "Ocel" and M.typ_podle_sku("16.12.01.050.0300.1000.0") == "Hliník vroubkovaný" and M.typ_podle_sku("16.10.01.050.0450.3000.0") == "Hliník hladký")
over("T2 cizi SKU a None se nemeni", M.typ_podle_sku("3.009.03.50.290") is None and M.typ_podle_sku(None) is None)
o = M.uprav_specs({"Height": "800", "Roller": "Ø50", "Kusovník": "x"}, "Ocel")
over("T3 klic hned za Roller, poradi ostatnich zachovano", list(o) == ["Height", "Roller", "Typ válečku", "Kusovník"], o)
over("T4 opakovane pouziti je idempotentni a bez Roller jde na konec", M.uprav_specs(o, "Ocel") == o and list(M.uprav_specs({"A": "1"}, "Ocel")) == ["A", "Typ válečku"])

from _env import get_conn  # noqa: E402
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT id, sku, product_specs_json FROM shop_products WHERE category_id=324 AND sku REGEXP '^16\\\\.1[02]\\\\.01\\\\.05[01]\\\\.'")
radky = cur.fetchall()
spatne = [r["sku"] for r in radky if json.loads(r["product_specs_json"]).get("Typ válečku") != M.typ_podle_sku(r["sku"])]
chybi_klic = [r["sku"] for r in radky if any(k not in json.loads(r["product_specs_json"]) for k in ("Roller", "Roller length", "Conveyor Length", "Height", "Between the Roller Axes", "Side Barrier"))]
over("D1 vsech %d dopravniku ma spravny Typ valecku" % len(radky), len(radky) == 90 and not spatne, spatne[:3])
over("D2 vsechny maji i ostatni filtrovatelne atributy (Roller, Roller length, Conveyor Length, Height, osy, vodici)", not chybi_klic, chybi_klic[:3])
conn.close()
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
