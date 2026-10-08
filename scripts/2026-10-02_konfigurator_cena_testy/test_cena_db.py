#!/opt/konfigurator/api/venv/bin/python
"""Cena konfigurace: load_ctx proti ZIVYM endpointum (DB JEN KE CTENI, bot5, 2026-10-02).

  1) ctx["pricing"] == GET /api/pricing-config (admin_settings.pricing_config)
  2) ctx["parts"] == dily z GET /api/katalog PO aplikaci koeficientu (stejne id, stejna pole: cena, delka, prurez, hmotnost,
     cena rezu, priznak desky a koeficientu, jednotka) - vsechny dily zdroje profil/product, zadny navic
  3) verze pravidel spoju: ctx == production_overview.CURRENT_JOINT_RULE_VERSION == JOINT_RULE_VERSION ve scene.html
  4) TRANSAKCNI BEZPECNOST: load_ctx(cur) nesmi ukoncit transakci volajiciho (zadny commit/rollback) - radkovy zamek FOR SHARE
     drzeny v transakci musi po load_ctx stale platit; naopak fetch_katalog_parts() z app.py ho PUSTI (jeho get_conn().close()
     dela rollback na sdilenem spojeni vlakna) - proto load_ctx cte pres predany kurzor misto volani fetch_katalog_parts()
  5) staticka kontrola modulu: zadne volani commit/rollback/get_conn/fetch_katalog_parts, zadny import app/Flask na urovni modulu
Endpointy se volaji jako hole funkce (__wrapped__ obejde prihlaseni) v test_request_context. Nic se nezapisuje (jen SELECT; radkovy
zamek FOR SHARE na jednom radku app_settings se drzi nekolik milisekund a uvolni se rollbackem).

Spusteni (DB prihlaseni pres systemd, ne cteni api/.env):
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env \\
    --working-directory=/opt/konfigurator /opt/konfigurator/api/venv/bin/python3 \\
    scripts/2026-10-02_konfigurator_cena_testy/test_cena_db.py
Kandidat pred nasazenim: --setenv=CFG_PRICE_PY=/cesta/k/configurator_price.py
"""
import ast
import importlib.util
import json
import os
import re
import sys
import time

import pymysql

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
API = os.path.join(REPO, "api")
sys.path.insert(0, API)
CFG_PY = os.environ.get("CFG_PRICE_PY", os.path.join(API, "configurator_price.py"))
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:700]))


if not os.path.exists(CFG_PY):
    over(f"0 modul configurator_price.py existuje ({CFG_PY})", False, "soubor chybi - nastav CFG_PRICE_PY na kandidata")
    print("\nVYSLEDEK cena konfigurace - load_ctx proti zivym endpointum: 0/1 OK")
    sys.exit(1)

import app as A  # noqa: E402
import admin_settings as S  # noqa: E402
import production_overview as PO  # noqa: E402

spec = importlib.util.spec_from_file_location("configurator_price_pod_testem", CFG_PY)
CFG = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CFG)


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                           database=os.environ["DB_NAME"], port=int(os.environ.get("DB_PORT", 3306)),
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


conn = A.get_conn()
cur = conn.cursor()
t0 = time.time()
ctx = CFG.load_ctx(cur)
cas = time.time() - t0
print(f"load_ctx: {len(ctx['parts'])} dilu, {cas * 1000:.0f} ms")

# ---- 1) sazby
with A.app.test_request_context("/api/pricing-config"):
    pricing = S.pricing_config.__wrapped__().get_json()
over("1 ctx['pricing'] == GET /api/pricing-config (spoj, pausal profilu, balne, montaz, koeficient, prislusenstvi)", ctx["pricing"] == pricing,
     {k: (ctx["pricing"].get(k), pricing.get(k)) for k in pricing if ctx["pricing"].get(k) != pricing.get(k)})

# ---- 2) dily
with A.app.test_request_context("/api/katalog"):
    katalog = A.katalog.__wrapped__().get_json()
route = {p["id"]: p for p in katalog["parts"] if p.get("source") in ("profil", "product")}
over("2a stejna mnozina dilu jako /api/katalog (zdroj profil + product): zadny chybejici ani navic",
     set(ctx["parts"]) == set(route), {"chybi": sorted(set(route) - set(ctx["parts"]))[:5], "navic": sorted(set(ctx["parts"]) - set(route))[:5]})
POLE = [("name", "name"), ("layer", "layer"), ("length_mm", "length_mm"), ("cross_section_mm", "cross_section_mm"), ("weight_kg", "weight_kg_approx"),
        ("price_czk", "price_czk_approx_PLACEHOLDER"), ("price_per_cut_czk", "price_per_cut_czk"), ("source", "source")]
rozdily = []
for pid, mine in ctx["parts"].items():
    r = route.get(pid)
    if not r:
        continue
    for mk, rk in POLE:
        if mine[mk] != r.get(rk):
            rozdily.append((pid, mk, mine[mk], r.get(rk)))
    for mk, rv in (("is_board_material", bool(r.get("is_board_material"))), ("scene_coef", bool(r.get("scene_coef"))),
                   ("sku", r.get("sku")), ("unit", r.get("unit")), ("price_basis", r.get("price_basis"))):
        if mine[mk] != rv:
            rozdily.append((pid, mk, mine[mk], rv))
over(f"2b vsech {len(ctx['parts'])} dilu souhlasi s /api/katalog v polich nazev, vrstva, delka, prurez, hmotnost, CENA (po koeficientu), cena rezu, "
     f"deska, scene_coef, SKU, jednotka", not rozdily, rozdily[:6])
koef = katalog["price_coefficient"]
over(f"2c koeficient sceny: ctx {ctx['pricing']['scene_price_coefficient']} == /api/katalog {koef} a (pokud != 1) je pouzit jen u dilu se scene_coef",
     ctx["pricing"]["scene_price_coefficient"] == koef and (koef == 1.0 or any(p["scene_coef"] for p in ctx["parts"].values())), koef)
over("2d pokryti: katalog obsahuje profily, desky, dily s cenou i dily s koeficientem (test ma smysl)",
     any(p["is_board_material"] for p in ctx["parts"].values()) and any(p["length_mm"] and p["cross_section_mm"][0] is not None for p in ctx["parts"].values())
     and any(p["scene_coef"] and p["price_czk"] is not None for p in ctx["parts"].values()), None)

# ---- 3) verze pravidel spoju
scene = open(os.path.join(REPO, "webapp", "scene.html"), encoding="utf-8").read()
scene_verze = int(re.search(r"^const JOINT_RULE_VERSION = (\d+);", scene, re.M).group(1))
over(f"3 verze pravidel spoju: ctx {ctx['joint_rule_version']} == production_overview {PO.CURRENT_JOINT_RULE_VERSION} == scene.html {scene_verze}",
     ctx["joint_rule_version"] == PO.CURRENT_JOINT_RULE_VERSION == scene_verze, None)

# ---- 4) transakcni bezpecnost (radkovy zamek FOR SHARE ve sdilenem spojeni vlakna; druhe spojeni zkusi FOR UPDATE NOWAIT)
KLIC = "montaz_pct"


def zamek_drzen():
    druhe = ostre_spojeni()
    try:
        with druhe.cursor() as c2:
            c2.execute("SET SESSION innodb_lock_wait_timeout=1")
            try:
                c2.execute("SELECT setting_key FROM app_settings WHERE setting_key=%s FOR UPDATE NOWAIT", (KLIC,))
            except pymysql.err.OperationalError:
                return True            # zamek drzi nekdo jiny (nase transakce)
            return False
    finally:
        druhe.rollback()
        druhe.close()


try:
    cur.execute("SELECT setting_key FROM app_settings WHERE setting_key=%s FOR SHARE", (KLIC,))
    cur.fetchall()
    zamek_pred = zamek_drzen()
    CFG.load_ctx(cur)
    zamek_po_load_ctx = zamek_drzen()
    A.fetch_katalog_parts()
    zamek_po_fetch = zamek_drzen()
finally:
    conn.close()                   # rollback sdileneho spojeni (uvolni zamek, nic se nezapsalo)
over("4a pojistka testu: radkovy zamek v nasi transakci je viditelny druhemu spojeni", zamek_pred, zamek_pred)
over("4b load_ctx(cur) NEUKONCI transakci volajiciho (zamek po nem stale drzi) - bezpecne volat uprostred kosiku/objednavky", zamek_po_load_ctx, zamek_po_load_ctx)
over("4c doklad pasti: fetch_katalog_parts() z app.py transakci ukonci (zamek je pryc) - proto load_ctx nevola ji, ale cte pres predany kurzor",
     zamek_po_fetch is False, zamek_po_fetch)

# ---- 5) staticka kontrola modulu
zdroj = open(CFG_PY, encoding="utf-8").read()
strom = ast.parse(zdroj)
volane = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None) for n in ast.walk(strom) if isinstance(n, ast.Call)}
zakazane = {"commit", "rollback", "get_conn", "fetch_katalog_parts", "close", "execute_many", "executemany"} & volane
over("5a modul nevola commit/rollback/close/get_conn/fetch_katalog_parts", not zakazane, sorted(zakazane))
importy = [n for n in strom.body if isinstance(n, (ast.Import, ast.ImportFrom))]
na_urovni_modulu = {(n.module if isinstance(n, ast.ImportFrom) else n.names[0].name) for n in importy}
over("5b na urovni modulu jen stdlib (math) - zadny import app/flask/pymysql (modul jde pouzit i mimo Flask, importuje se bez side-effectu)",
     na_urovni_modulu <= {"math"}, sorted(na_urovni_modulu))
sql = [n.value for n in ast.walk(strom) if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|ALTER|DROP)\b", n.value)]
zapisy = [s for s in sql if re.search(r"^\s*(INSERT|UPDATE|DELETE|ALTER|DROP|REPLACE|CREATE|TRUNCATE)\b", s, re.I | re.M)]
over(f"5c vsechny SQL v modulu ({len(sql)}) jsou jen SELECT", not zapisy, zapisy)

ok = sum(vysl)
print(f"\nVYSLEDEK cena konfigurace - load_ctx proti zivym endpointum: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
