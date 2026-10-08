import sys
sys.path.insert(0, "/opt/konfigurator/api")
import miniweb_vies as v
ok = bad = 0
def t(n, c):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("CHYBA", n)
t("rozdel SK s prefixem", v.rozdel("SK", "SK 2020-2020 20") == ("SK", "2020202020"))
t("rozdel bez prefixu", v.rozdel("SK", "2020202020") == ("SK", "2020202020"))
t("rozdel GR = EL", v.rozdel("GR", "EL123456789") == ("EL", "123456789"))
t("rozdel spatny format", v.rozdel("SK", "<b>")[1] is None and v.rozdel("SK", "")[1] is None)
def st(r, **kw):
    v._cache.clear(); return v.vies_stav("SK", "SK2020202020", fetch=lambda k, c: r, **kw)
t("valid", st({"valid": True}) == "valid")
t("invalid", st({"valid": False}) == "invalid")
t("MS_UNAVAILABLE neni invalid", st({"valid": False, "userError": "MS_UNAVAILABLE"}) == "unavailable")
t("errorWrappers = nedostupne", st({"valid": False, "errorWrappers": [{"error": "SERVICE_UNAVAILABLE"}]}) == "unavailable")
t("nesmysl = nedostupne", st("x") == "unavailable" and st({}) == "unavailable")
v._cache.clear()
def boom(k, c): raise OSError("sit")
t("vyjimka = nedostupne", v.vies_stav("SK", "SK2020202020", fetch=boom) == "unavailable")
t("spatny format se do VIES neposila", v.vies_stav("SK", "<b>", fetch=boom) == "invalid")
n = [0]
def f(k, c): n[0] += 1; return {"valid": True}
v._cache.clear(); v.vies_stav("SK", "2020202020", fetch=f, now=100); v.vies_stav("SK", "SK2020202020", fetch=f, now=200)
t("cache", n[0] == 1)
v.vies_stav("SK", "2020202020", fetch=f, now=100 + v.CACHE_OK_S + 1)
t("po vyprseni znovu, zadna stara hodnota", n[0] == 2)
v._cache.clear(); v.vies_stav("SK", "2020202020", fetch=boom, now=0)
t("nedostupne se drzi kratce", v._cache[("SK", "2020202020")][0] == v.CACHE_CHYBA_S)
print("OK %d, chyb %d" % (ok, bad)); sys.exit(1 if bad else 0)
