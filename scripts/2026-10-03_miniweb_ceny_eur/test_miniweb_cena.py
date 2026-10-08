import sys, copy, json
sys.path.insert(0, "/opt/konfigurator/api")
import miniweb_cena as c
from decimal import Decimal
ok = bad = 0
def t(n, cond):
    global ok, bad
    if cond: ok += 1
    else: bad += 1; print("CHYBA", n)
shop = {"price_mode": "shown", "currency": "EUR", "margin_pct": Decimal("20"), "eur_rate": Decimal("25")}
cfg = c.nastaveni(shop)
t("cfg", cfg and cfg["rate"] == 25)
t("2500 Kc +20 % = 120 EUR", c.cena_eur(2500, cfg) == 120)
t("pulka nahoru", c.cena_eur(Decimal("2437.5"), {"rate": Decimal(25), "margin_pct": Decimal(0)}) == 98)  # 97.5
t("zaporna delta", c.cena_eur(-250, cfg) == -12)
t("None", c.cena_eur(None, cfg) is None and c.cena_eur(5, None) is None)
t("hidden", c.nastaveni(dict(shop, price_mode="hidden")) is None)
t("mena", c.nastaveni(dict(shop, currency="CZK")) is None)
t("bez marze", c.nastaveni(dict(shop, margin_pct=None)) is None)
t("zaporna marze", c.nastaveni(dict(shop, margin_pct=-1)) is None)
c._cache.clear()
t("bez kurzu a Fio padne = zadna cena", c.nastaveni(dict(shop, eur_rate=None), fetch=lambda m: 1/0) is None)
c._cache.clear()
t("zivy kurz", c.nastaveni(dict(shop, eur_rate=None), fetch=lambda m: 24.5)["rate"] == Decimal("24.5"))
n = [0]
def f(m): n[0] += 1; return 24
c._cache.clear(); c.zivy_kurz("EUR", f, now=1000); c.zivy_kurz("EUR", f, now=1100)
t("cache", n[0] == 1)
c.zivy_kurz("EUR", f, now=1000 + c.CACHE_OK_S + 1)
t("po vyprseni znovu (zadna stara hodnota)", n[0] == 2)
c._cache.clear()
c.zivy_kurz("EUR", lambda m: 1/0, now=0)
t("chyba se drzi kratce", c._cache["EUR"][0] == c.CACHE_CHYBA_S and c._cache["EUR"][1] is None)
out = {"price": {"net": 2500, "vat_rate": 0.21, "gross": 3025, "currency": "CZK"},
       "options": {"shelf": {"on": {"price_delta": 500, "disabled": False}, "min": 0}, "led": {"on": {"price_delta": 0}}}}
r = c.na_eur(copy.deepcopy(out), cfg)
t("price", r["price"] == {"net": 120, "vat_rate": 0, "gross": 120, "currency": "EUR"})
t("delta", r["options"]["shelf"]["on"]["price_delta"] == 24 and r["options"]["led"]["on"]["price_delta"] == 0 and r["options"]["shelf"]["min"] == 0)
r = c.na_eur(copy.deepcopy(out), None)
t("bez cfg zadna Kc", "price" not in r and "price_delta" not in r["options"]["shelf"]["on"])
t("price None", c.na_eur({"price": None, "options": {}}, cfg)["price"] is None)
out2 = {"price": {"net": 2500}, "options": {"shelf": {"on": {"price_delta": 500}, "off": {"price_delta": -100, "x": 1}}, "bearings": {"on": {"price_delta": 40}, "count": {"placed": 2}}}}
r2 = c.na_eur(copy.deepcopy(out2), None)
t("bez nastaveni zmizi price_delta u VSECH voleb (on i dalsi), ne jen u 'on' (externi revize #7)", "price" not in r2 and "price_delta" not in json.dumps(r2) and r2["options"]["shelf"]["off"]["x"] == 1 and r2["options"]["bearings"]["count"] == {"placed": 2})
print("OK %d, chyb %d" % (ok, bad)); sys.exit(1 if bad else 0)
