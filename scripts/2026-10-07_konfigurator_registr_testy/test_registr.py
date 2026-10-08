#!/opt/konfigurator/api/venv/bin/python
"""Rozcestnik konfiguratoru stul / dopravnik (bot5, 2026-10-07): api/konfigurator_registr.py + delegace v routach api/stul_shop.py (schema, resolve, model, glb).
SKUTECNE routy pres test_client; modul dopravniku je v testu ZASTUPNY (types.ModuleType v sys.modules), mapovani produktu (app_settings.configurator_products) se podstrci do cache modulu -
nic se nezapisuje a DB se jen cte. Stolova vetev musi zustat beze zmeny (schema, resolve, glb stolu, 404 pro cizi produkt, 403 pro spatny token).
Spusteni: systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 scripts/2026-10-07_konfigurator_registr_testy/test_registr.py"""
import importlib.machinery
import os
import sys
import threading
import time
import types

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.path.join(REPO, "api")
os.chdir(REPO)
if not os.environ.get("DB_HOST"):
    print("CHYBA: chybi DB_* v prostredi - spust pres systemd-run --property=EnvironmentFile=api/.env")
    sys.exit(2)
_orig = threading.Thread.start
threading.Thread.start = lambda self, *a, **k: None if self.name == "render-dozorce" else _orig(self, *a, **k)
sys.path.insert(0, API)
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.dont_write_bytecode = True
try:
    import app as appmod  # noqa: E402
    import stul_shop as SH  # noqa: E402
    import stul_konfigurator as S  # noqa: E402
    import stul_api as _stul_api  # noqa: E402
    import konfigurator_registr as R  # noqa: E402
finally:
    threading.Thread.start = _orig
S.nastav_pravidla({})
_stul_api.obnov_pravidla = lambda force=False: None
if hasattr(SH, "_DELKY_CACHE"):
    SH._DELKY_CACHE.update(t=time.time() + 1e7, set=frozenset(S.PANEL_DELKY))
assert os.path.abspath(R.__file__).startswith(API), R.__file__

vysl = []


def over(n, p, d=None):
    vysl.append(bool(p))
    print(("OK   " if p else "FAIL ") + n + ("" if p else "  -> " + repr(d)))


PID_STUL, PID_DOP, PID_JINY = 9876, 9877, 9878
SH._PRODUKTY.update(t=time.time() + 10_000, map={str(PID_STUL): SH.RECEPT, str(PID_DOP): R.RECEPT_DOPRAVNIK})
c = appmod.app.test_client()
from flask import jsonify  # noqa: E402

print("== rozcestnik bez modulu dopravniku")
sys.modules.pop("dopravnik_shop", None)
R._HLEDANI.update(t=time.time(), existuje=False)                      # modul se nehleda (30 s), v testu soubor mozna jeste neexistuje
over("R1 recept produktu: stul, dopravnik, neznamy, neplatne id", R.recept_produktu(PID_STUL) == SH.RECEPT and R.recept_produktu(PID_DOP) == R.RECEPT_DOPRAVNIK and R.recept_produktu(PID_JINY) is None and R.recept_produktu(None) is None and R.recept_produktu("x") is None)
over("R2 je_dopravnik jen u receptu dopravniku", R.je_dopravnik(PID_DOP) and not R.je_dopravnik(PID_STUL) and not R.je_dopravnik(PID_JINY))
over("R3 bez modulu: dopravnik_modul / dopravnik_pro = None, konfigurovatelny jen stul", R.dopravnik_modul() is None and R.dopravnik_pro(PID_DOP) is None and R.konfigurovatelny(PID_STUL) and not R.konfigurovatelny(PID_DOP) and not R.konfigurovatelny(PID_JINY))
over("R4 bez modulu se dopravnik chova jako dosud: schema 404, resolve 404", c.get(f"/api/shop/products/{PID_DOP}/configurator").status_code == 404 and c.post("/api/shop/configurator/resolve", json={"product_id": PID_DOP, "selection": {}}).status_code == 404)

print("== se zastupnym modulem dopravniku")
VOLANI = []
fake = types.ModuleType("dopravnik_shop")
fake.__spec__ = importlib.machinery.ModuleSpec("dopravnik_shop", None)
fake.odpoved_schema = lambda pid: (VOLANI.append(("schema", pid)), jsonify({"zastupny": "schema", "pid": pid}))[1]
fake.odpoved_resolve = lambda body, skryt: (VOLANI.append(("resolve", body.get("product_id"), skryt)), jsonify({"zastupny": "resolve"}))[1]
fake.zna_hash = lambda h: h == "abc123"
fake.odpoved_model = lambda h: (VOLANI.append(("model", h)), jsonify({"zastupny": "model"}))[1]
fake.odpoved_glb = lambda t: (VOLANI.append(("glb", t)), jsonify({"zastupny": "glb"}))[1]
fake.pro_objednavku = lambda sel, rv, lang, pid: {"ok": True, "zastupny": "pro_objednavku", "pid": pid}
fake.glb_bytes = lambda sel, razitka=False: b"GLB-ZASTUPNY" + (b"-R" if razitka else b"")
sys.modules["dopravnik_shop"] = fake
over("R5 s modulem: dopravnik_modul, dopravnik_pro (jen dopravnik), konfigurovatelny", R.dopravnik_modul() is fake and R.dopravnik_pro(PID_DOP) is fake and R.dopravnik_pro(PID_STUL) is None and R.dopravnik_pro(PID_JINY) is None and R.konfigurovatelny(PID_DOP))
j = c.get(f"/api/shop/products/{PID_DOP}/configurator").get_json()
over("R6 schema dopravniku jde pres modul dopravniku", j == {"zastupny": "schema", "pid": PID_DOP} and ("schema", PID_DOP) in VOLANI, j)
rs = c.get(f"/api/shop/products/{PID_STUL}/configurator")
js = rs.get_json()
over("R7 schema stolu beze zmeny (zadny zastupny klic, ma sloty a rules_version)", rs.status_code == 200 and "zastupny" not in js and js.get("slots") and js.get("rules_version"), rs.status_code)
over("R8 cizi produkt = 404 jako dosud", c.get(f"/api/shop/products/{PID_JINY}/configurator").status_code == 404)
rr = c.post("/api/shop/configurator/resolve", json={"product_id": PID_DOP, "selection": {}, "price": "hidden"})
over("R9 resolve dopravniku jde pres modul, `skryt_cenu` se predava", rr.get_json() == {"zastupny": "resolve"} and ("resolve", PID_DOP, True) in VOLANI, rr.get_json())
rst = c.post("/api/shop/configurator/resolve", json={"product_id": PID_STUL, "selection": {}})
jst = rst.get_json()
over("R10 resolve stolu beze zmeny (cena, platnost, model)", rst.status_code == 200 and "zastupny" not in jst and jst.get("price") and jst.get("valid") is True and jst.get("model"), rst.status_code)
over("R11 resolve neznameho produktu = 404", c.post("/api/shop/configurator/resolve", json={"product_id": PID_JINY, "selection": {}}).status_code == 404)
over("R12 model znamy hash dopravniku jde pres modul", c.get("/api/shop/configurator/model/abc123").get_json() == {"zastupny": "model"} and ("model", "abc123") in VOLANI)
over("R13 model neznamy hash = 404 jako dosud", c.get("/api/shop/configurator/model/neznamy").status_code == 404)
over("R14 glb s prefixem dop. jde pres modul dopravniku", c.get("/api/shop/configurator/glb/dop.neco.1.sig").get_json() == {"zastupny": "glb"} and ("glb", "dop.neco.1.sig") in VOLANI)
over("R15 glb se spatnym tokenem stolu = 403 jako dosud", c.get("/api/shop/configurator/glb/neco.123.sig").status_code == 403)
tok = SH.podepis_model(S.sestav_stul(**SH.normalizuj({}, 30)[0])["parametry"])
rg = c.get("/api/shop/configurator/glb/" + tok)
over("R16 glb stolu s platnym tokenem = 200 model/gltf-binary (stolova vetev beze zmeny)", rg.status_code == 200 and rg.mimetype == "model/gltf-binary" and rg.data[:4] == b"glTF", (rg.status_code, rg.mimetype))
over("R17 token stolu nezacina prefixem dopravniku", not tok.startswith(R.PREFIX_TOKENU_DOPRAVNIKU), tok[:10])

print("== funkce pro kosik a nabidku")
over("R18 pro_objednavku: dopravnik -> modul dopravniku", R.pro_objednavku({}, None, "cs", PID_DOP).get("zastupny") == "pro_objednavku")
po = R.pro_objednavku({}, None, "cs", PID_STUL)
over("R19 pro_objednavku: stul -> stul_shop (ok, cena, kod)", po.get("ok") and po.get("price") and po.get("kod") and "zastupny" not in po, sorted(po)[:6])
over("R20 glb_bytes: dopravnik -> modul (vychozi S razitky, pravidlo 61; bez nich jen vyslovne), stul -> GLB stolu", R.glb_bytes({}, PID_DOP) == b"GLB-ZASTUPNY-R" and R.glb_bytes({}, PID_DOP, razitka=False) == b"GLB-ZASTUPNY" and R.glb_bytes({}, PID_STUL)[:4] == b"glTF")
sys.modules.pop("dopravnik_shop", None)
print("\n%d/%d kontrol OK" % (sum(vysl), len(vysl)))
sys.exit(0 if all(vysl) else 1)
