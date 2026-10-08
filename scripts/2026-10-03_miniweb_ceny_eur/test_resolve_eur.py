#!/usr/bin/env python3
"""Test hooku EUR v POST /api/shop/configurator/resolve (bot5, 2026-10-03). Kandidat: STUL_API_OVERRIDE=<kopie api/ s novym stul_shop.py>.
Spusteni: STUL_API_OVERRIDE=... systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator api/venv/bin/python3 scripts/2026-10-03_miniweb_ceny_eur/test_resolve_eur.py
Do DB se nic nezapisuje (radek shopu se podstrci do cache miniweb_cena)."""
import os, sys, threading, time, json
from decimal import Decimal
REPO = "/opt/konfigurator"
API = os.environ.get("STUL_API_OVERRIDE") or REPO + "/api"
os.chdir(REPO)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API); sys.path.insert(0, REPO + "/scripts")
import app as appmod, stul_shop as SH, miniweb_cena as C
threading.Thread.start = _orig
assert "miniweb_cena" in open(SH.__file__).read(), "testuje se nasazeny stul_shop, ne kandidat: " + SH.__file__
ok = bad = 0
def check(c, m):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("CHYBA", m)
PID = next(iter(SH._produkty()), None) if hasattr(SH, "_produkty") else None
SH._HOSTY_BEZ_CENY.update(t=time.time() + 10_000, hosty=set())
n = [0]
def post(host, extra=None, ip="10.8.0.%d"):
    n[0] += 1
    b = {"product_id": PID, "selection": {"w": 1500}}; b.update(extra or {})
    return appmod.app.test_client().post("/api/shop/configurator/resolve", json=b, base_url="http://" + host, headers={"X-Forwarded-For": ip % n[0]}).get_json()
def shop(host, **kw):
    row = {"price_mode": "shown", "currency": "EUR", "margin_pct": Decimal("20"), "eur_rate": Decimal("25")}; row.update(kw)
    C._SHOPY[host] = (time.time() + 1000, row)
check(PID, "produkt konfigurovatelny existuje")
base = post("jiny.test")
czk = base["price"]["net"]; check(czk > 0 and base["price"]["currency"] == "CZK", "bezny host: Kc beze zmeny")
shop("sk.test")
r = post("sk.test")
check(r["price"]["currency"] == "EUR" and r["price"]["vat_rate"] == 0 and r["price"]["net"] == r["price"]["gross"], "shown+EUR: price v EUR bez DPH")
check(r["price"]["net"] == round(czk / 25 * 1.2 + 1e-9) or abs(r["price"]["net"] - czk / 25 * 1.2) <= 0.5, "prepocet kurz 25 + marze 20 %")
check(r["hash"] == base["hash"] and r["selection"] == base["selection"], "hash a selection beze zmeny")
deltas = [v["price_delta"] for o in r["options"].values() if isinstance(o, dict) for v in o.values() if isinstance(v, dict) and "price_delta" in v]
check(deltas and all(isinstance(d, int) for d in deltas), "price_delta jsou cela EUR")
check("CZK" not in json.dumps(r.get("price")), "zadna Kc pod price")
shop("sk2.test", margin_pct=None)
r = post("sk2.test"); check("price" not in r and not any("price_delta" in v for o in r["options"].values() if isinstance(o, dict) for v in o.values() if isinstance(v, dict)), "bez marze zadna cena (ani Kc)")
shop("sk3.test", price_mode="hidden")
check(post("sk3.test")["price"]["currency"] == "CZK", "mini-shop hidden: hook nesaha (cenu skryva dosavadni mechanismus)")
r = post("sk.test", {"price": "hidden"}); check("price" not in r, "explicitni price=hidden ma prednost")
SH._HOSTY_BEZ_CENY.update(t=time.time() + 10_000, hosty={"sk.test"})
check("price" not in post("sk.test"), "host v configurator_hide_price_hosts ma prednost")
print("OK %d, chyb %d" % (ok, bad)); sys.exit(1 if bad else 0)
