#!/opt/konfigurator/api/venv/bin/python
"""Test obalu endpointu shop_product_duplicate (api/products.py) BEZ Flasku a BEZ DB.

Zdrojovy kod funkce se z products.py vytahne pres ast a spusti s atrapami (spojeni,
uzivatel, audit, product_duplicate). Overuje to, co DB test nevidi: RBAC sekci a
akci, cestu, pořadi current_user() PRED get_conn() (pooled-conn past), mapovani
404, rollback + uklid souboru pri selhani, tvar odpovedi a zapis do auditu. Nedefinovane
jmeno v kodu endpointu (preklep) skonci NameErrorem.

Spusteni: api/venv/bin/python3 scripts/2026-09-30_duplikace_produktu_testy/test_endpoint_duplikace.py
Kandidat pred nasazenim: PRODUCTS_PY=/cesta/k/products.py ... test_endpoint_duplikace.py
"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "api"))
import product_duplicate as pd  # noqa: E402

PRODUCTS = os.environ.get("PRODUCTS_PY", os.path.join(HERE, "..", "..", "api", "products.py"))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


class FakeCur:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self, log, fail_commit=False):
        self.log, self.fail_commit = log, fail_commit

    def cursor(self):
        return FakeCur()

    def commit(self):
        self.log.append("commit")
        if self.fail_commit:
            raise RuntimeError("commit selhal")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def load(log, fail_commit=False):
    zachyceno = {"routes": [], "perms": []}
    app = types.SimpleNamespace(post=lambda *a, **k: (zachyceno["routes"].append(a[0]) or (lambda f: f)))
    ns = {
        "app": app,
        "require_permission": lambda *a: (zachyceno["perms"].append(a) or (lambda f: f)),
        "current_user": lambda: (log.append("current_user") or {"id": 793, "role": "skladnik"}),
        "get_conn": lambda: (log.append("get_conn") or FakeConn(log, fail_commit)),
        "jsonify": lambda d: d,
        "log_audit": lambda *a: log.append(("audit",) + a),
        "gallery_items": types.SimpleNamespace(GALLERY_ITEMS_DIR="/g"),
        "PRODUCT_DOCS_DIR": "/d",
        "_product_slug_for_name": lambda cur, name: "slug",
        "product_duplicate": pd,
    }
    tree = ast.parse(open(PRODUCTS, encoding="utf-8").read())
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "shop_product_duplicate"), None)
    if fn is None:
        raise SystemExit("FAIL: v products.py neni funkce shop_product_duplicate")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PRODUCTS, "exec"), ns)
    return ns["shop_product_duplicate"], zachyceno, tree


def main():
    # --- import na urovni modulu + RBAC + cesta ----------------------------------------
    log = []
    endpoint, zach, tree = load(log)
    over("0.1 products.py importuje product_duplicate na urovni modulu",
         any(isinstance(n, ast.Import) and any(a.name == "product_duplicate" for a in n.names) for n in tree.body))
    over("0.2 cesta POST /api/shop/products/<int:product_id>/duplicate", zach["routes"] == ["/api/shop/products/<int:product_id>/duplicate"], zach["routes"])
    over("0.3 pravo sklad_karty/vytvorit (kopie je nova karta)", zach["perms"] == [("sklad_karty", "vytvorit")], zach["perms"])

    orig_dup, orig_rm = pd.duplicate_product, pd.remove_files
    try:
        # --- 1: uspech --------------------------------------------------------------------
        log.clear()
        volano = {}
        removed = []

        def fake_ok(cur, pid, **kw):
            volano.update(pid=pid, **kw)
            return {"id": 5001, "sku": "X-kopie", "name": "X (kopie)", "slug": "x-kopie",
                    "copied": {"gallery": 1}, "missing_files": 0, "created_files": ["/g/a.jpg"]}
        pd.duplicate_product, pd.remove_files = fake_ok, removed.extend
        odp, status = endpoint(3045)
        over("1.1 uspech: 201 a tvar odpovedi bez created_files", status == 201 and odp["status"] == "ok" and odp["id"] == 5001
             and odp["sku"] == "X-kopie" and "created_files" not in odp and odp["copied"] == {"gallery": 1}, (status, odp))
        over("1.2 current_user() se vola PRED get_conn() (pooled-conn past)", log.index("current_user") < log.index("get_conn"), log)
        over("1.3 commit, pak close; zadny rollback", log[log.index("commit"):][:2] == ["commit", "close"] and "rollback" not in log, log)
        over("1.4 audit: duplicate / shop_product / nove id", ("audit", 793, "duplicate", "shop_product", 5001, "z #3045: X-kopie - X (kopie)") in log, log)
        over("1.5 predava zdroj, uzivatele a adresare souboru",
             volano.get("pid") == 3045 and volano.get("created_by") == 793 and volano.get("created_role") == "skladnik"
             and volano.get("gallery_dir") == "/g" and volano.get("docs_dir") == "/d" and callable(volano.get("slug_for_name")), volano)
        over("1.6 pri uspechu se zadne soubory nemazou", removed == [], removed)

        # --- 2: neexistujici produkt --------------------------------------------------------
        log.clear()

        def fake_404(cur, pid, **kw):
            raise pd.ProductNotFound(pid)
        pd.duplicate_product = fake_404
        odp, status = endpoint(99)
        over("2.1 neexistujici produkt: 404 s hlaskou", status == 404 and odp == {"error": "Produkt neexistuje."}, (status, odp))
        over("2.2 rollback + close, zadny commit ani audit", "rollback" in log and "close" in log and "commit" not in log
             and not any(isinstance(x, tuple) for x in log), log)

        # --- 3: duplicate_product selze (vyjimka se propusti, uklid je na modulu) ----------------
        log.clear()
        removed.clear()

        def fake_boom(cur, pid, **kw):
            raise RuntimeError("boom")
        pd.duplicate_product = fake_boom
        try:
            endpoint(3045)
            over("3.1 selhani se propusti jako vyjimka", False)
        except RuntimeError:
            over("3.1 selhani se propusti jako vyjimka", True)
        over("3.2 rollback + close, bez commitu a auditu; endpoint nemaze soubory (nic nevznikl)",
             "rollback" in log and "close" in log and "commit" not in log and removed == [] and not any(isinstance(x, tuple) for x in log), (log, removed))

        # --- 4: selze az commit -> smazat soubory, ktere uz lezi na disku -----------------------------
        log.clear()
        removed.clear()
        endpoint4, _, _ = load(log, fail_commit=True)
        pd.duplicate_product = fake_ok
        try:
            endpoint4(3045)
            over("4.1 selhani commitu se propusti jako vyjimka", False)
        except RuntimeError:
            over("4.1 selhani commitu se propusti jako vyjimka", True)
        over("4.2 po selhani commitu: rollback, close, uklid souboru, zadny audit",
             "rollback" in log and "close" in log and removed == ["/g/a.jpg"] and not any(isinstance(x, tuple) for x in log), (log, removed))
    finally:
        pd.duplicate_product, pd.remove_files = orig_dup, orig_rm

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK endpoint duplikace: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
