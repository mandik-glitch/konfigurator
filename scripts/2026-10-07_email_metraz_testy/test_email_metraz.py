#!/opt/konfigurator/api/venv/bin/python
"""Potvrzovaci e-mail objednavky: metraz = "x N m", ne "ks" (bot5, 2026-10-07; Robert pres bot9: valeckova draha se prodava po metrech). Cista funkce orders._order_confirmation_email_body, nic se neposila
(pravidlo 16), DB se nepouziva; staticka kontrola, ze polozka objednavky nese product_unit z karty. Spusteni: api/venv/bin/python3 scripts/2026-10-07_email_metraz_testy/test_email_metraz.py (v prostredi s DB_* pres systemd-run, app se importuje)."""
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
API = os.path.abspath(os.path.join(HERE, "..", "..", "api"))
sys.path.insert(0, API)
sys.dont_write_bytecode = True
_o = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _o(self, *a, **k)
import app  # noqa: E402,F401
import orders  # noqa: E402
vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)))


def radek(**kw):
    it = {"product_name_snapshot": "Zboží", "qty": 3, "line_total_czk": 834.0}
    it.update(kw)
    return orders._order_confirmation_email_body("OBJ-1", [it], 834.0).split("\n")
def jeden(**kw):
    return next(l for l in radek(**kw) if l.startswith("  - "))


over("E1 metraz (unit m): '× 3 m'", jeden(product_unit="m") == "  - Zboží × 3 m = 834.00 Kč", jeden(product_unit="m"))
over("E2 plocha (m2): '× 3 m²'", jeden(product_unit="m2") == "  - Zboží × 3 m² = 834.00 Kč")
over("E3 kus (ks, None, chybi klic): beze zmeny '× 3 ks'", jeden(product_unit="ks") == "  - Zboží × 3 ks = 834.00 Kč" and jeden(product_unit=None) == jeden() == "  - Zboží × 3 ks = 834.00 Kč")
over("E4 profil po 3 m: '× 3 ks (3 m)' beze zmeny", jeden(product_unit="ks", is_profile_material=True) == "  - Zboží × 3 ks (3 m) = 834.00 Kč")
src = open(os.path.join(API, "orders.py"), encoding="utf-8").read()
over("S1 SELECT produktu v tvorbe objednavky bere sloupec unit a polozka nese product_unit", "sale_price_until, category_id, unit \"" in src and "\"product_unit\": product.get(\"unit\")" in src)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
