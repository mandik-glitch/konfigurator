#!/opt/konfigurator/api/venv/bin/python
"""Test endpointu shop_products_normalize_slugs (api/products.py) BEZ Flasku a BEZ DB: nahled (dry_run, vychozi) NEKOMITUJE
(rollback), provedeni komituje a zapise audit, `ids` omezi vyber, current_user() se vola PRED get_conn() (pooled-conn past),
pri vyjimce rollback + close, odpoved je omezena na 500 zmen. Funkce se z products.py vytahne pres ast.

Spusteni: api/venv/bin/python3 scripts/2026-09-30_duplikace_produktu_testy/test_endpoint_normalize_slugs.py
Kandidat pred nasazenim: PRODUCTS_PY=/cesta/k/products.py ...
"""
import ast
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
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
    def __init__(self, log):
        self.log = log

    def cursor(self):
        return FakeCur()

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def zavolej(body, zmeny=None, selze=False):
    log = []
    zmeny = [{"id": 1, "name": "A", "old": "x", "new": "a", "reason": "nesedi"}] if zmeny is None else zmeny
    zachyceno = {"routes": [], "perms": []}

    def proposals(cur, ids=None):
        log.append(("proposals", ids))
        return ["navrh"]

    def apply(cur, items):
        log.append(("apply", items))
        if selze:
            raise RuntimeError("boom")
        return zmeny

    ns = {
        "app": types.SimpleNamespace(post=lambda *a, **k: (zachyceno["routes"].append(a[0]) or (lambda f: f))),
        "require_permission": lambda *a: (zachyceno["perms"].append(a) or (lambda f: f)),
        "request": types.SimpleNamespace(get_json=lambda silent=True: body),
        "jsonify": lambda d: d,
        "current_user": lambda: (log.append("current_user") or {"id": 7, "role": "admin"}),
        "get_conn": lambda: (log.append("get_conn") or FakeConn(log)),
        "log_audit": lambda *a: log.append(("audit",) + a),
        "product_slug": types.SimpleNamespace(proposals=proposals, apply=apply),
    }
    tree = ast.parse(open(PRODUCTS, encoding="utf-8").read())
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "shop_products_normalize_slugs"), None)
    if fn is None:
        raise SystemExit("FAIL: v products.py neni funkce shop_products_normalize_slugs")
    exec(compile(ast.Module(body=[fn], type_ignores=[]), PRODUCTS, "exec"), ns)
    try:
        return ns["shop_products_normalize_slugs"](), log, zachyceno, None
    except Exception as e:                                   # noqa: BLE001
        return None, log, zachyceno, e


def main():
    odp, log, zach, _ = zavolej({})
    over("0.1 cesta POST /api/shop/products/normalize-slugs a pravo sklad_karty/upravit",
         zach["routes"] == ["/api/shop/products/normalize-slugs"] and zach["perms"] == [("sklad_karty", "upravit")], zach)
    over("1.1 bez parametru je to NAHLED: rollback, zadny commit ani audit, odpoved nese zmeny", odp["dry_run"] is True and "rollback" in log and "commit" not in log
         and not any(isinstance(x, tuple) and x[0] == "audit" for x in log) and odp["count"] == 1 and odp["changes"][0]["new"] == "a", (odp, log))
    over("1.2 current_user() se vola PRED get_conn() (pooled-conn past)", log.index("current_user") < log.index("get_conn"), log)

    odp, log, _, _ = zavolej({"dry_run": False})
    over("2.1 dry_run=false PROVEDE: commit, bez rollbacku, audit normalize_slugs s poctem", odp["dry_run"] is False and "commit" in log and "rollback" not in log
         and ("audit", 7, "normalize_slugs", "shop_product", None, "1 adres produktu") in log, (odp, log))
    odp, log, _, _ = zavolej({"dry_run": False}, zmeny=[])
    over("2.2 kdyz neni co menit, nezapisuje se audit", odp["count"] == 0 and not any(isinstance(x, tuple) and x[0] == "audit" for x in log), (odp, log))

    odp, log, _, _ = zavolej({"ids": [5, "9", "x", 3.5]})
    over("3 `ids` omezi vyber (jen cela cisla)", ("proposals", [5, 9]) in log, log)

    odp, log, _, vyj = zavolej({"dry_run": False}, selze=True)
    over("4 vyjimka pri provadeni: rollback + close, bez commitu a auditu, vyjimka se propusti", odp is None and isinstance(vyj, RuntimeError) and "rollback" in log
         and "close" in log and "commit" not in log and not any(isinstance(x, tuple) and x[0] == "audit" for x in log), (odp, vyj, log))

    mnoho = [{"id": i, "name": "N", "old": "o", "new": "n", "reason": "nesedi"} for i in range(800)]
    odp, log, _, _ = zavolej({}, zmeny=mnoho)
    over("5 odpoved je omezena na 500 zmen, pocet je ale skutecny (800)", odp["count"] == 800 and len(odp["changes"]) == 500, (odp["count"], len(odp["changes"])))

    selhalo = vysl.count(False)
    print(f"\nVYSLEDEK endpoint normalize-slugs: {len(vysl) - selhalo}/{len(vysl)} OK")
    sys.exit(1 if selhalo else 0)


if __name__ == "__main__":
    main()
