#!/opt/konfigurator/api/venv/bin/python
"""GET /api/shop/products?include=specs (bot5, 2026-10-07): verejna specifikace v seznamu pro tabulku/filtry kategorie dopravniku. SKUTECNY endpoint pres test_client, jen CTENI ostre DB (zadny zapis).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-07_produkty_include_specs_testy/test_include_specs.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import app as appmod  # noqa: E402
import products  # noqa: E402

assert os.path.abspath(products.__file__).startswith(API), products.__file__
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)))


c = appmod.app.test_client()
print("== cista funkce")
over("F1 None, nesmysl a ne-dict = prazdny dict", products._verejne_specs(None) == {} and products._verejne_specs("neni json") == {} and products._verejne_specs("[1,2]") == {} and products._verejne_specs(5) == {})
over("F2 retezec JSON i dict, bez klice Kusovník", products._verejne_specs('{"A": "1", "Kusovník": "x"}') == {"A": "1"} and products._verejne_specs({"B": "2", "Kusovník": "y"}) == {"B": "2"})

print("== endpoint")
r0 = c.get("/api/shop/products?category_id=324&page_size=100")
j0 = r0.get_json()
over("E1 bez parametru se odpoved nemeni (zadny klic specs ani product_specs_json)", r0.status_code == 200 and j0["products"] and all("specs" not in p and "product_specs_json" not in p for p in j0["products"]), r0.status_code)
r = c.get("/api/shop/products?category_id=324&page_size=100&include=specs")
j = r.get_json()
ps = j["products"]
over("E2 include=specs: 200, vsechny aktivni dopravniky maji dict specs, total shodne s e1", r.status_code == 200 and len(ps) == j0["total"] == j["total"] and all(isinstance(p.get("specs"), dict) for p in ps), (r.status_code, len(ps), j0["total"]))
over("E3 specs nenese Kusovník ani product_specs_json", all("Kusovník" not in p["specs"] and "product_specs_json" not in p for p in ps))
atr = ("Typ válečku", "Roller", "Roller length", "Conveyor Length", "Height", "Between the Roller Axes", "Side Barrier")
chybi = [p["sku"] for p in ps if any(k not in p["specs"] for k in atr)]
over("E4 kazdy dopravnik ma vsechny filtrovatelne atributy", not chybi, chybi[:3])
over("E5 typy valecku: hladky + vroubkovany + ocel", {p["specs"]["Typ válečku"] for p in ps} == {"Hliník hladký", "Hliník vroubkovaný", "Ocel"}, {p["specs"].get("Typ válečku") for p in ps})
over("E6 anonym nevidi interni pole ani s include (supplier_id, dogus_url)", all("supplier_id" not in p and "dogus_url" not in p for p in ps), sorted(ps[0].keys()))
over("E7 neaktivni karty (13 bez ceny) se anonymovi nevraci", all(p["active"] == 1 and p["price_czk_placeholder"] is not None for p in ps))
rx = c.get("/api/shop/products?category_id=324&page_size=5&include=foo")
over("E8 neznama hodnota include = bez specs", rx.status_code == 200 and all("specs" not in p for p in rx.get_json()["products"]))
rk = c.get("/api/shop/products?category_id=325&page_size=100&include=specs,x")
jk = rk.get_json()
over("E9 jina kategorie (valecky) + vice hodnot include: specs je dict u vsech", rk.status_code == 200 and jk["products"] and all(isinstance(p["specs"], dict) for p in jk["products"]), rk.status_code)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
