#!/opt/konfigurator/api/venv/bin/python
"""Test shop_products_update (api/products.py) BEZ Flasku a BEZ DB: (a) validace - prazdny/prilis dlouhy nazev a SKU -> 400,
duplicitni SKU (MySQL 1062) -> 400 s hlaskou misto 500; (b) adresa produktu (slug) sleduje nazev - prejmenovani vytvori
novou adresu + 301 (product_slug.change_slug), aktivace produktu bez adresy adresu vytvori, beze zmeny nazvu se adresa nemeni.
Funkce se z products.py vytahne pres ast a spusti s atrapami (stejny princip jako test_endpoint_duplikace.py).

Spusteni: api/venv/bin/python3 scripts/2026-09-30_duplikace_produktu_testy/test_update_validace.py
Kandidat pred nasazenim: PRODUCTS_PY=/cesta/k/products.py ... test_update_validace.py
"""
import ast
import json
import os
import sys
import types

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
PRODUCTS = os.environ.get("PRODUCTS_PY", os.path.join(HERE, "..", "..", "api", "products.py"))
vysl = []
PUVODNI = {"name": "Starý název", "slug": "stary-nazev"}


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


class FakeCur:
    def __init__(self, log, chyba_update, puvodni):
        self.log, self.chyba_update, self.puvodni, self.posledni = log, chyba_update, puvodni, ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.posledni = sql
        self.log.append(("sql", sql, params))
        if sql.startswith("UPDATE shop_products SET") and self.chyba_update:
            raise self.chyba_update

    def fetchone(self):
        if self.posledni.startswith("SELECT name, slug"):
            return self.puvodni
        return {"cfg_dily_id": None, "price_czk_placeholder": None}


class FakeConn:
    def __init__(self, log, chyba_update, puvodni):
        self.log, self.chyba_update, self.puvodni = log, chyba_update, puvodni

    def cursor(self):
        return FakeCur(self.log, self.chyba_update, self.puvodni)

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def zavolej(body, chyba_update=None, puvodni=PUVODNI, zmenit_adresu=True):
    log = []
    slug = types.SimpleNamespace(
        slug_for_name=lambda cur, name, exclude_id=None: (log.append(("slug_for_name", name, exclude_id)) or "slug-z-" + name),
        change_slug=lambda cur, pid, novy: (log.append(("change_slug", pid, novy)) or zmenit_adresu),
    )
    ns = {
        "app": types.SimpleNamespace(put=lambda *a, **k: (lambda f: f)),
        "require_permission": lambda *a: (lambda f: f),
        "request": types.SimpleNamespace(get_json=lambda silent=True: body),
        "jsonify": lambda d: d,
        "get_conn": lambda: (log.append("get_conn") or FakeConn(log, chyba_update, puvodni)),
        "current_user": lambda: {"id": 1, "role": "admin"},
        "log_audit": lambda *a: log.append(("audit",) + a),
        "json": json,
        "pymysql": pymysql,
        "product_slug": slug,
    }
    tree = ast.parse(open(PRODUCTS, encoding="utf-8").read())
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "shop_products_update"), None)
    if fn is None:
        raise SystemExit("FAIL: v products.py neni funkce shop_products_update")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PRODUCTS, "exec"), ns)
    try:
        odp = ns["shop_products_update"](3671)
        return odp, log, None
    except Exception as e:                                   # noqa: BLE001 - test sleduje i propustene vyjimky
        return None, log, e


def volani(log, jmeno):
    return [x for x in log if isinstance(x, tuple) and x[0] == jmeno]


def main():
    # ---- (a) validace ------------------------------------------------------------------------------------------
    odp, log, _ = zavolej({"name": "   "})
    over("1 prazdny nazev -> 400 a DB se vubec neotevre", odp == ({"error": "Název nesmí být prázdný."}, 400) and "get_conn" not in log, (odp, log))
    odp, log, _ = zavolej({"name": None})
    over("2 nazev null -> 400", isinstance(odp, tuple) and odp[1] == 400, odp)
    odp, log, _ = zavolej({"name": "x" * 201})
    over("3 nazev nad 200 znaku -> 400 s hlaskou o delce", isinstance(odp, tuple) and odp[1] == 400 and "200" in odp[0]["error"], odp)
    odp, log, _ = zavolej({"sku": ""})
    over("4 prazdne SKU -> 400", odp == ({"error": "SKU nesmí být prázdné."}, 400), odp)
    odp, log, _ = zavolej({"sku": "S" * 151})
    over("5 SKU nad 150 znaku -> 400", isinstance(odp, tuple) and odp[1] == 400 and "150" in odp[0]["error"], odp)

    odp, log, _ = zavolej({"name": "  Nový název  "})
    upd = [x for x in log if isinstance(x, tuple) and x[0] == "sql" and x[1].startswith("UPDATE shop_products SET")]
    over("6 platny nazev se ulozi OREZANY, commit, audit a odpoved ok s novou adresou",
         odp == {"status": "ok", "slug": "slug-z-Nový název"} and len(upd) == 1 and upd[0][2] == ["Nový název", 3671] and "commit" in log
         and any(isinstance(x, tuple) and x[0] == "audit" and x[2] == "update" for x in log), (odp, upd, log))

    chyba = pymysql.err.IntegrityError(1062, "Duplicate entry 'DUP' for key 'shop_products.sku'")
    odp, log, vyjimka = zavolej({"sku": "DUP"}, chyba_update=chyba)
    over("7 duplicitni SKU (1062) -> 400 s hlaskou, rollback, bez auditu", odp == ({"error": "Produkt s tímto SKU už existuje."}, 400)
         and "rollback" in log and "close" in log and not any(isinstance(x, tuple) and x[0] == "audit" for x in log), (odp, log, vyjimka))

    chyba2 = pymysql.err.IntegrityError(1062, "Duplicate entry 'x' for key 'shop_products.uq_shop_products_slug'")
    odp, log, vyjimka = zavolej({"name": "Jiný"}, chyba_update=chyba2)
    over("8 jina duplicita (slug) se NEschova za hlasku o SKU, ale propusti se", odp is None and isinstance(vyjimka, pymysql.err.IntegrityError), (odp, vyjimka))

    odp, log, _ = zavolej({"unit": "ks"})
    over("9 zmena bez nazvu a SKU (jen unit) projde beze zmeny a na adresy ani nesahne",
         odp == {"status": "ok"} and not volani(log, "change_slug") and not any(isinstance(x, tuple) and x[0] == "sql" and x[1].startswith("SELECT name, slug") for x in log), (odp, log))

    # ---- (b) adresa sleduje nazev ----------------------------------------------------------------------------------
    odp, log, _ = zavolej({"name": "Nový název"})
    poradi = [i for i, x in enumerate(log) if isinstance(x, tuple) and x[0] == "sql" and (x[1].startswith("SELECT name, slug") or x[1].startswith("UPDATE shop_products SET"))]
    over("10 prejmenovani: nova adresa z NOVEHO nazvu, change_slug (= 301 ze stare) ve stejne transakci PRED commitem, odpoved nese adresu",
         odp == {"status": "ok", "slug": "slug-z-Nový název"} and volani(log, "slug_for_name") == [("slug_for_name", "Nový název", 3671)]
         and volani(log, "change_slug") == [("change_slug", 3671, "slug-z-Nový název")] and log.index(volani(log, "change_slug")[0]) < log.index("commit"), (odp, log))
    over("11 puvodni nazev/adresa se cte PRED zmenou (UPDATE)", len(poradi) == 2 and log[poradi[0]][1].startswith("SELECT name, slug"), log)
    over("12 audit zaznamena i zmenu adresy", any(isinstance(x, tuple) and x[0] == "audit" and "adresa -> slug-z-Nový název" in x[5] for x in log), log)

    odp, log, _ = zavolej({"name": "Starý název"})
    over("13 stejny nazev (jen preulozeni) adresu NEmeni", odp == {"status": "ok"} and not volani(log, "change_slug"), (odp, log))

    odp, log, _ = zavolej({"active": True}, puvodni={"name": "Bez adresy", "slug": None})
    over("14 aktivace produktu BEZ adresy ji vytvori z nazvu", odp == {"status": "ok", "slug": "slug-z-Bez adresy"} and volani(log, "change_slug") == [("change_slug", 3671, "slug-z-Bez adresy")], (odp, log))
    odp, log, _ = zavolej({"active": True})
    over("15 aktivace produktu, ktery adresu uz ma, ji nemeni", odp == {"status": "ok"} and not volani(log, "change_slug"), (odp, log))
    odp, log, _ = zavolej({"name": "Nový název"}, zmenit_adresu=False)
    over("16 kdyz se adresa nezmenila (change_slug=False), odpoved ji neuvadi", odp == {"status": "ok"}, odp)

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK shop_products_update (validace + adresa): {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
