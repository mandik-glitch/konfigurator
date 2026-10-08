#!/opt/konfigurator/api/venv/bin/python
"""PRICKY DO MULTIBOXU v online nabidce - SKUTECNE endpointy (Flask test client) nad DOCASNYMI tabulkami (bot8, 2026-10-07; Robert: sety pricek vzdy pro celou polici / suplik s multiboxy).

  GET  /api/public/offers/<token>                 -> blok `pricky` (jen kdyz model nabidky ma multiboxy, karty dilu maji cenu a jsou aktivni; admin odkaz vidi i pred aktivaci; nikdy nespadne)
  GET  /api/public/offers/<token>/payment-qr?pr=  -> castka QR = presne castka objednavky (qty, montaz %), neplatny vyber = 400
  POST /api/public/offers/<token>/accept {pricky} -> objednavka: radky pricek, hlavicka s cenou, poznamka s rozpisem po policich; neplatny vyber = 400 BEZ zapisu prijeti
  + jednotkove: _offer_gross_total, _montaz_poznamka, orders.create_order_from_scene_offer(extra_items)

Do ostrych dat se NEZAPISUJE: scene_offers, scene_offer_order_prefs, scene_offer_acceptances, shop_orders, shop_order_items, shop_order_status_history, shop_order_number_released a shop_products jsou ve spojeni
testu zastineny TEMPORARY tabulkami (app_settings a cislovani objednavek jako kopie), model nabidky = GLB z fixtures v docasne slozce, e-mail a audit jsou vypnute; zakaznik se jen NAJDE (dedup podle e-mailu
existujiciho zakaznika, jinak by se zakladal ucet - bez nej se pruchod prijetim preskoci). Na konci se overi, ze ostre tabulky jsou beze zmeny.
Spusteni: PRICKY_CAND=/cesta/ke/kandidatum (slozka s nabidka_pricky.py, scene_offers.py, orders.py, v3d_glb.py, v3d_merge.py) PRICKY_FIX=/cesta/k/<OUT>/out2 (4921.offer.glb z build_karty.py)
  systemd-run --pipe --wait --quiet --property=EnvironmentFile=/opt/konfigurator/api/.env --setenv=HOME=/root --setenv=PRICKY_CAND=... --setenv=PRICKY_FIX=... --working-directory=/opt/konfigurator \\
    /opt/konfigurator/api/venv/bin/python3 <tento test>
(bez PRICKY_CAND se testuje zivy kod v api/)"""
import copy
import datetime
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
API = "/opt/konfigurator/api"
CAND = os.environ.get("PRICKY_CAND")
if CAND and os.path.abspath(CAND) == os.path.abspath(API):
    CAND = None                                    # kandidat = zive api/ -> testuje se primo zivy kod (kopirovani cele slozky api/ by rozbilo relativni importy ze scripts/)
FIX = os.environ.get("PRICKY_FIX") or os.path.join(os.environ.get("V3D_TEST_OUT") or os.path.join(tempfile.gettempdir(), "v3d_testy"), "out2")       # zakaznicke GLB z build_karty.py
if CAND:
    tmp_kand = tempfile.mkdtemp(prefix="kand_pricky_")
    for f in os.listdir(CAND):
        if f.endswith(".py"):
            shutil.copy(os.path.join(CAND, f), os.path.join(tmp_kand, f))
    sys.path.insert(0, tmp_kand)
sys.path.insert(1 if CAND else 0, API)
sys.dont_write_bytecode = True

import pymysql  # noqa: E402
import app as appmod  # noqa: E402
import scene_offers  # noqa: E402
import orders as ordersmod  # noqa: E402
import nabidka_pricky as P  # noqa: E402
import v3d_glb  # noqa: E402
from documents import VAT_RATE  # noqa: E402

if CAND:
    for m in (scene_offers, ordersmod, P, v3d_glb):
        assert os.path.abspath(m.__file__).startswith(os.path.abspath(tmp_kand)), f"nacetl se jiny {m.__name__}: {m.__file__}"

vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)[:400]))


def ostre_spojeni():
    return pymysql.connect(host=os.environ["DB_HOST"], user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"], database=os.environ["DB_NAME"],
                           port=int(os.environ.get("DB_PORT", 3306)), charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)


OSTRE = ("scene_offers", "scene_offer_order_prefs", "scene_offer_acceptances", "shop_orders", "shop_order_items", "shop_order_status_history", "app_users", "shop_customers", "shop_products")


def stav_ostrych():
    c = ostre_spojeni()
    try:
        with c.cursor() as cur:
            out = {}
            for t in OSTRE:
                cur.execute(f"SELECT COUNT(*) AS n, COALESCE(MAX(id),0) AS m FROM `{t}`")
                r = cur.fetchone()
                out[t] = (r["n"], r["m"])
            return out
    finally:
        c.close()


PRED = stav_ostrych()
over("0 ostre ID nabidek jsou pod 900000", PRED["scene_offers"][1] < 900000, PRED)

conn = appmod.get_conn()
real = object.__getattribute__(conn, "_real")
TEMP_LIKE = ("scene_offers", "scene_offer_order_prefs", "scene_offer_acceptances", "shop_orders", "shop_order_items", "shop_order_status_history", "shop_order_number_released", "shop_products")
TEMP_COPY = ("shop_order_number_sequence", "app_settings")


def sql(q, params=None):
    with real.cursor() as cur:
        cur.execute(q, params or ())
        out = cur.fetchall() if q.lstrip().upper().startswith(("SELECT", "SHOW")) else cur.rowcount
    real.commit()
    return out


# ---- fixture model: zakaznicke GLB karty 4921 = police 8 boxu + 2 vysuvy po 7 boxech + 3 podnosy ocelovych supliku (sk = 4), spec ma mbx se skupinami
GLB_FULL = open(os.path.join(FIX, "4921.offer.glb"), "rb").read()
# puvodni testy multiboxu bezi na modelu BEZ podnosu (stejny model, spec bez sk = 4; id b01..b22 a skupiny s1..s3 preocislovane souvisle jako dosud): police 8 + 2 vysuvy po 7
_OUT = os.path.join(os.path.dirname(FIX), "out")
_sp = copy.deepcopy(json.load(open(os.path.join(_OUT, "4921.json"), encoding="utf-8"))["v3d"])
_sp["mbx"] = [b for b in _sp["mbx"] if b["sk"] != 4]
_skmap = {}
for _i, _b in enumerate(_sp["mbx"], 1):
    _b["id"] = "b%02d" % _i
    _b["n"] = _i
    _b["s"] = _skmap.setdefault(_b["s"], len(_skmap) + 1)
GLB = v3d_glb.sanitize(open(os.path.join(_OUT, "4921.glb"), "rb").read(), _sp)
SPEC = v3d_glb.embedded_spec(GLB)
BOXY = P.boxy_ze_spec(SPEC)
MODELY = tempfile.mkdtemp(prefix="test_pricky_modely_")
scene_offers.OFFER_MODELS_DIR = MODELY
scene_offers.log_audit = lambda *a, **k: None
MAILY = []
scene_offers.send_email = lambda *a, **k: MAILY.append(a)
scene_offers._rate_limited = lambda *a, **k: False
SPAYD = []
_orig_spayd = scene_offers._build_spayd
scene_offers._build_spayd = lambda iban, amount, vs, label: (SPAYD.append(float(amount)), _orig_spayd(iban, amount, vs, label))[1]


def sirky(skupina_id):
    """(pocet 186, pocet 91) boxu skupiny z mbx spec (nezavisle na modulu: z rozmeru AABB)."""
    a = b = 0
    for bx in SPEC["mbx"]:
        if "s%d" % bx["s"] != skupina_id:
            continue
        w = min(bx["max"][0] - bx["min"][0], bx["max"][2] - bx["min"][2])
        if w > 140:
            a += 1
        else:
            b += 1
    return a, b


def ocek_net(vyber):
    """Ocekavana cena pricek (za 1 kus sestavy, bez DPH) pro {skupina: set}: pocty po boxech z NEZAVISLE tabulky mixu, cena z sirky boxu (186 mm 39 Kc, 91 mm 29 Kc)."""
    return net_boxy(parse_pr(PR(vyber)))


SK_SPEC = {}
for _bx in SPEC["mbx"]:
    SK_SPEC.setdefault("s%d" % _bx["s"], []).append(_bx["id"])
SIRKA_BOXU = {bx["id"]: min(bx["max"][0] - bx["min"][0], bx["max"][2] - bx["min"][2]) for bx in SPEC["mbx"]}
# nezavisla tabulka mixu (pocty pricek po boxech v poradi skupiny) pro skupiny po 7 a 8 boxech delky 395 mm (6 slotu) - fixture 4921
POC_SETU = {8: {"mix1": [6, 1, 6, 1, 6, 1, 6, 1], "mix2": [6, 3, 6, 3, 6, 3, 6, 3], "mix3": [6, 6, 1, 6, 6, 1, 6, 6], "mix4": [1, 1, 3, 3, 3, 3, 6, 6], "pln": [6] * 8},
            7: {"mix1": [6, 1, 6, 1, 6, 1, 6], "mix2": [6, 3, 6, 3, 6, 3, 6], "mix3": [6, 6, 1, 6, 6, 1, 6], "mix4": [1, 1, 3, 3, 3, 6, 6], "pln": [6] * 7}}


def parse_pr(txt):
    return {a: int(b) for a, b in (x.split(":") for x in txt.split(",") if x)}


def PR(sety=None, boxy=None):
    """Zapis vyberu po boxech "b01:6,b02:2" ze setu pro skupiny {s1: pln} a z vlastnich poctu {b01: 2}."""
    d = {}
    for sk, st in (sety or {}).items():
        for bid, n in zip(SK_SPEC[sk], POC_SETU[len(SK_SPEC[sk])][st]):
            d[bid] = n
    d.update(boxy or {})
    return ",".join("%s:%d" % (b, n) for b, n in sorted(d.items(), key=lambda kv: int(kv[0][1:])) if n)


def net_boxy(boxy, c186=39.0, c91=29.0):
    """Cena pricek po boxech z jejich SIRKY (nezavisle na modulu): {id boxu: pocet} -> Kc bez DPH."""
    return round(sum(n * (c186 if SIRKA_BOXU[b] > 140 else c91) for b, n in boxy.items()), 2)


with real.cursor() as cur:
    for t in TEMP_COPY:
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"INSERT INTO `_tpl_{t}` SELECT * FROM `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
        cur.execute(f"INSERT INTO `{t}` SELECT * FROM `_tpl_{t}`")
    for t in TEMP_LIKE:
        cur.execute(f"CREATE TEMPORARY TABLE `_tpl_{t}` LIKE `{t}`")
        cur.execute(f"CREATE TEMPORARY TABLE `{t}` LIKE `_tpl_{t}`")
    for t in TEMP_LIKE + TEMP_COPY:
        cur.execute(f"SHOW CREATE TABLE `{t}`")
        assert list(cur.fetchone().values())[1].startswith("CREATE TEMPORARY TABLE"), f"ABORT: {t} neni docasna"
real.commit()


def karty(c186=39, c91=29, aktivni=1, jen=None, archiv=0):
    sql("DELETE FROM shop_products")
    for klic, cena in (("p186", c186), ("p91", c91)):
        if jen and klic not in jen:
            continue
        sql("INSERT INTO shop_products (id, sku, name, price_czk_placeholder, active, is_archived) VALUES (%s,%s,%s,%s,%s,%s)",
            (990000 + (1 if klic == "p186" else 2), P.DILY[klic]["sku"], P.DILY[klic]["nazev"], cena, aktivni, archiv))


PROD = {"p186": 990001, "p91": 990002}


def vloz(id_, token, items, total, model=True, opts=None, aktivni=1, glb=None):
    fn = None
    if model:
        fn = "m%d.glb" % id_
        open(os.path.join(MODELY, fn), "wb").write(glb or GLB)
    admin_tok = token + "-admin"
    sql("INSERT INTO scene_offers (id, offer_number, items, total_price, view_narys, view_3d_a, view_3d_b, view_3d_model, editable_text_popis, editable_text_patka, view_token_hash, "
        "admin_view_token_hash, expires_at, is_active, offer_options, revision_number) VALUES (%s,%s,%s,%s,'x','x','x',%s,'','',%s,%s,%s,%s,%s,1)",
        (id_, f"TESTPR{id_}", json.dumps(items, ensure_ascii=False), total, fn, hashlib.sha256(token.encode()).hexdigest(), hashlib.sha256(admin_tok.encode()).hexdigest(),
         datetime.datetime.now() + datetime.timedelta(days=5), aktivni, json.dumps(opts or {"show_qr": True})))
    return admin_tok


ITEMS = [{"name": "Regálová vestavba", "dim": "-", "qty": "1 ks", "unit_price": 100000, "total": 100000}]
V, N = 900301, 900302
AUTO = {"show_qr": True, "vandr_single_drawing": True, "montaz_pct": 10}
ADM_V = vloz(V, "tok-v", ITEMS, 100000, True, AUTO)
ADM_N = vloz(N, "tok-n", ITEMS, 100000, False)
cl = appmod.app.test_client()


def gross(net):
    return round(net * (1 + VAT_RATE / 100), 2)


def GET(url):
    return cl.get(url)


_emb = scene_offers.v3d_glb.embedded_spec
def _boom(raw):
    raise RuntimeError("neocekavana chyba cteni modelu")
# ================================================================== jednotkove: _offer_gross_total, _montaz_poznamka
OFF = {"id": 1, "total_price": 100000, "offer_options": json.dumps({"vandr_single_drawing": True, "montaz_pct": 10})}
over("U1 bez pricek: celkem beze zmeny (100 000 + 21 % DPH)", scene_offers._offer_gross_total(OFF, {}, 0) == gross(100000), scene_offers._offer_gross_total(OFF, {}, 0))
over("U2 pricky 1 692 Kc za kus: pricitaji se pred DPH", scene_offers._offer_gross_total(OFF, {"pricky_net": 1692}, 0) == gross(101692))
over("U3 pricky se nasobi poctem kusu sestavy (qty 3)", scene_offers._offer_gross_total(OFF, {"pricky_net": 1692, "qty": 3}, 0) == gross(3 * (100000 + 1692)))
over("U4 montaz zvolena: % z ceny VCETNE pricek (10 % z 101 692)", scene_offers._offer_gross_total(OFF, {"pricky_net": 1692, "montaz_zvolena": 1, "montaz_misto": "praha"}, 0) == gross(101692 * 1.10),
     scene_offers._offer_gross_total(OFF, {"pricky_net": 1692, "montaz_zvolena": 1}, 0))
over("U5 pricky_net prazdne / None / chybi = 0", scene_offers._offer_gross_total(OFF, {"pricky_net": None}, 0) == gross(100000) and scene_offers._offer_gross_total(OFF, None, 0) == gross(100000))

# ================================================================== verejny JSON
r = GET("/api/public/offers/tok-n")
over("P1 nabidka bez 3D modelu: pricky = null, endpoint 200", r.status_code == 200 and r.get_json().get("pricky") is None and "pricky" in r.get_json(), r.get_json() and r.get_json().get("pricky"))
karty()                                            # aktivni, ceny 39 / 29
r = GET("/api/public/offers/tok-v")
pr = r.get_json().get("pricky") if r.status_code == 200 else None
over("P2 model s multiboxy + aktivni karty: blok pricky pro zakaznika", r.status_code == 200 and pr and pr["enabled"] and not pr["nahled_admin"], r.status_code)
over("P3 3 skupiny (police 8 + 2 vysuvy po 7), 22 boxu, 6 setu (bez, mix1-4, pln)", pr and [s["id"] for s in pr["skupiny"]] == ["s1", "s2", "s3"] and [s["boxu"] for s in pr["skupiny"]] == [8, 7, 7] and len(pr["boxy"]) == 22
     and [s["id"] for s in pr["sety"]] == ["bez", "mix1", "mix2", "mix3", "mix4", "pln"], pr and [(s["id"], s["boxu"]) for s in pr["skupiny"]])
over("P4 ceny setu (mixy a plny) za celou skupinu odpovidaji poctum po boxech", pr and all(pr["skupiny"][i]["sety"][v]["cena"] == ocek_net({"s%d" % (i + 1): v}) for i in range(3) for v in ("mix1", "mix2", "mix3", "mix4", "pln"))
     and all(pr["skupiny"][i]["sety"][v]["po_boxech"] == POC_SETU[pr["skupiny"][i]["boxu"]][v] for i in range(3) for v in ("mix1", "mix2", "mix3", "mix4", "pln"))
     and all(s["sety"]["bez"]["cena"] == 0 for s in pr["skupiny"]), pr and [s["sety"]["pln"]["cena"] for s in pr["skupiny"]])
over("P5 popisy skupin: police a sufliky, bez nazvu komponent", pr and [s["popis"] for s in pr["skupiny"]] == ["Police s multiboxy 1", "Výsuv s multiboxy 1", "Výsuv s multiboxy 2"], pr and [s["popis"] for s in pr["skupiny"]])
over("P6 typy boxu: max pricek 6 u 395 mm, geometrie pro libovolny pocet 0..6, dil boxu", pr and pr["typy"]["395x186"]["max"] == 6 and len(pr["typy"]["395x186"]["pocty"][6]["desky"]) == 6 and [x["n"] for x in pr["typy"]["395x186"]["pocty"]] == list(range(7))
     and pr["typy"]["395x186"]["dil"] == "p186" and pr["typy"]["395x91"]["dil"] == "p91")
over("P7 dily: dve karty s ID, cenou a nazvem", pr and [(d["klic"], d["product_id"], d["cena"]) for d in pr["dily"]] == [("p186", PROD["p186"], 39.0), ("p91", PROD["p91"], 29.0)], pr and pr["dily"])
over("P8 verejny JSON nenese jmena komponent ani SKU Vandr (jen cesty/ctx zakazane)", pr and not any(w in json.dumps(pr) for w in ("Clone", "PoliceMultibox", "VysuvMultibox", "unity")))

karty(aktivni=0)
r = GET("/api/public/offers/tok-v")
over("P9 karty NEAKTIVNI: zakaznik blok nevidi (null), endpoint 200", r.status_code == 200 and r.get_json()["pricky"] is None)
r = GET("/api/public/offers/" + ADM_V)
pa = r.get_json()["pricky"] if r.status_code == 200 else None
over("P10 karty neaktivni, ADMIN odkaz: blok je s nahled_admin = true", pa and pa["enabled"] and pa["nahled_admin"] is True, pa and pa.get("nahled_admin"))
karty(archiv=1)
over("P11 karta archivovana = neaktivni (zakaznik nevidi)", GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
karty(jen=("p186",))
over("P12 chybi karta druheho dilu: null i pro admina", GET("/api/public/offers/tok-v").get_json()["pricky"] is None and GET("/api/public/offers/" + ADM_V).get_json()["pricky"] is None)
karty()
sql("UPDATE shop_products SET price_czk_placeholder=NULL WHERE sku=%s", (P.DILY["p91"]["sku"],))
over("P13 karta bez ceny: null", GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
karty()
os.remove(os.path.join(MODELY, "m%d.glb" % V))
scene_offers._PRICKY_SPEC_CACHE.clear()
r = GET("/api/public/offers/tok-v")
over("P14 model na disku chybi: pricky null, nabidka se presto vrati (200)", r.status_code == 200 and r.get_json()["pricky"] is None and r.get_json()["offer_number"] == f"TESTPR{V}")
open(os.path.join(MODELY, "m%d.glb" % V), "wb").write(b"neni glb")
scene_offers._PRICKY_SPEC_CACHE.clear()
over("P15 rozbity soubor modelu: pricky null, endpoint 200", GET("/api/public/offers/tok-v").status_code == 200 and GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
open(os.path.join(MODELY, "m%d.glb" % V), "wb").write(GLB)
scene_offers._PRICKY_SPEC_CACHE.clear()
over("P16 po obnoveni modelu se blok vrati", GET("/api/public/offers/tok-v").get_json()["pricky"] is not None)
scene_offers.v3d_glb.embedded_spec = _boom
scene_offers._PRICKY_SPEC_CACHE.clear()
over("P19 neocekavana chyba pri cteni modelu: verejna nabidka 200 s pricky null", GET("/api/public/offers/tok-v").status_code == 200 and GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
scene_offers.v3d_glb.embedded_spec = _emb
scene_offers._PRICKY_SPEC_CACHE.clear()
modul = scene_offers.nabidka_pricky
scene_offers.nabidka_pricky = None
over("P17 modul pricek nenacten: pricky null, endpoint 200", GET("/api/public/offers/tok-v").status_code == 200 and GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
scene_offers.nabidka_pricky = modul
v3d_modul = scene_offers.v3d_glb
scene_offers.v3d_glb = None
scene_offers._PRICKY_SPEC_CACHE.clear()
over("P18 3D modul (v3d_glb) nenacten: pricky null, endpoint 200 (start sluzby nesmi zaviset na 3D modulech)", GET("/api/public/offers/tok-v").status_code == 200 and GET("/api/public/offers/tok-v").get_json()["pricky"] is None)
scene_offers.v3d_glb = v3d_modul
scene_offers._PRICKY_SPEC_CACHE.clear()

# ================================================================== QR platba
def qr(token, qs):
    SPAYD.clear()
    r = GET(f"/api/public/offers/{token}/payment-qr?{qs}")
    return r, (SPAYD[-1] if SPAYD else None)


r, a = qr("tok-v", "qty=1")
over("Q1 bez pr: castka beze zmeny (100 000 + DPH)", r.status_code == 200 and a == gross(100000), (r.status_code, a))
r, a = qr("tok-v", "qty=1&pr=" + PR({"s1": "pln"}))
over("Q2 pr = plny set police (po boxech): castka = (100 000 + pricky za policu) + DPH", r.status_code == 200 and a == gross(100000 + ocek_net({"s1": "pln"})), (r.status_code, a, gross(100000 + ocek_net({"s1": "pln"}))))
r, a = qr("tok-v", "qty=1&pr=" + PR({"s1": "pln", "s2": "mix1", "s3": "mix2"}))
over("Q3 vic skupin: soucet", r.status_code == 200 and a == gross(100000 + ocek_net({"s1": "pln", "s2": "mix1", "s3": "mix2"})), (r.status_code, a))
r, a = qr("tok-v", "qty=3&pr=" + PR({"s1": "pln", "s2": "mix1"}))
over("Q4 qty 3: pricky se nasobi poctem kusu", r.status_code == 200 and a == gross(3 * (100000 + ocek_net({"s1": "pln", "s2": "mix1"}))), (r.status_code, a))
r, a = qr("tok-v", "qty=1&pr=b01:0")
over("Q5 pr jen z nul = beze zmeny", r.status_code == 200 and a == gross(100000))
r, a = qr("tok-v", "qty=1&pr=" + PR({"s1": "pln"}) + "&deposit_pct=50")
over("Q6 zaloha 50 %: polovina castky vcetne pricek", r.status_code == 200 and a == round(gross(100000 + ocek_net({"s1": "pln"})) * 0.5, 2), (r.status_code, a))
MIX = {"b01": 2, "b02": 6, "b09": 0, SK_SPEC["s2"][0]: 3, SK_SPEC["s3"][1]: 1}
r, a = qr("tok-v", "qty=1&pr=" + PR(boxy=MIX))
over("Q6b vlastni kombinace po boxech (ruzne pocty v jedne polici): castka = soucet po boxech", r.status_code == 200 and a == gross(100000 + net_boxy({k: v for k, v in MIX.items() if v})), (r.status_code, a))
r, a = qr("tok-v", "qty=2&pr=" + PR({"s2": "pln"}, {SK_SPEC["s2"][1]: 1}))
over("Q6c set + prepsany jeden box (kombinace v jednom suplíku) a qty 2", r.status_code == 200 and a == gross(2 * (100000 + net_boxy({SK_SPEC["s2"][0]: 6, SK_SPEC["s2"][1]: 1, SK_SPEC["s2"][2]: 6, SK_SPEC["s2"][3]: 6, SK_SPEC["s2"][4]: 6, SK_SPEC["s2"][5]: 6, SK_SPEC["s2"][6]: 6}))), (r.status_code, a))
for spatny in ("b99:1", "b01:7", "b01", "s1:pln", "b01:x", "b01:6:2", "b01:6,b01:2", "b01:-1", "b01:100", "B01:1"):
    r, a = qr("tok-v", f"qty=1&pr={spatny}")
    over(f"Q7 neplatny pr {spatny!r} = 400 a zadna QR", r.status_code == 400 and a is None, r.status_code)
r, a = qr("tok-n", "qty=1&pr=b01:1")
over("Q8 nabidka bez multiboxu: pr = 400", r.status_code == 400)
karty(aktivni=0)
r, a = qr("tok-v", "qty=1&pr=" + PR({"s1": "pln"}))
over("Q9 karty neaktivni: zakaznik s pr = 400", r.status_code == 400)
r, a = qr(ADM_V, "qty=1&pr=" + PR({"s1": "pln"}))
over("Q10 karty neaktivni: admin odkaz s pr projde (nahled)", r.status_code == 200 and a == gross(100000 + ocek_net({"s1": "pln"})), (r.status_code, a))
karty()
scene_offers.v3d_glb.embedded_spec = _boom
scene_offers._PRICKY_SPEC_CACHE.clear()
r, a = qr("tok-v", "qty=1&pr=" + PR({"s1": "pln"}))
over("Q12 neocekavana chyba pri cteni modelu: QR s vyberem = 400 (ne 500), zadna QR", r.status_code == 400 and a is None, r.status_code)
scene_offers.v3d_glb.embedded_spec = _emb
scene_offers._PRICKY_SPEC_CACHE.clear()
# (montaz % z ceny vcetne pricek: jednotkove U4 a O12 nize, kde se volby ukladaji pres order-prefs)

# ================================================================== prijeti nabidky -> objednavka
zname = sql("SELECT c.email FROM shop_customers c JOIN app_users u ON u.id = c.user_id WHERE c.email IS NOT NULL AND c.email <> '' LIMIT 1")
FORM = {"name": "Test Jednatel", "company_ico": "12345678", "company_name": "Test Firma s.r.o.", "company_dic": "CZ12345678", "company_address": "Testovací 1, Praha", "contact_phone": "123456789"}
if not zname:
    print("PRESKOCENO: v databazi neni zadny existujici zakaznik pro dedup (objednavka by zakladala ucet)")
    over("O0 prijeti preskoceno (zadny existujici zakaznik)", True)
else:
    FORM["contact_email"] = zname[0]["email"]
    vloz(900311, "tok-o1", ITEMS, 100000, True, AUTO)
    vloz(900312, "tok-o2", ITEMS, 100000, True, AUTO)
    vloz(900313, "tok-o3", ITEMS, 100000, True, AUTO)
    vloz(900314, "tok-o4", ITEMS, 100000, True, AUTO)
    # O1: prijeti s vyberem
    MAILY.clear()
    r = appmod.app.test_client().post("/api/public/offers/tok-o1/accept", json=dict(FORM, pricky=PR({"s1": "pln", "s2": "mix1"})))
    over("O1 prijeti s pricky: 201 a cislo objednavky", r.status_code == 201 and r.get_json().get("order_number"), (r.status_code, r.get_json()))
    onum = (r.get_json() or {}).get("order_number")
    o = sql("SELECT * FROM shop_orders WHERE order_number=%s", (onum,))
    o = o[0] if o else None
    net = ocek_net({"s1": "pln", "s2": "mix1"})
    # auto sestava BEZ zvolene montaze (zadne prefs): jen zbozi + pricky
    over("O2 hlavicka: celkem = (zbozi + pricky) + DPH", o and abs(float(o["total_czk"]) - gross(100000 + net)) < 0.01, o and (float(o["total_czk"]), gross(100000 + net)))
    radky = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (o["id"],)) if o else []
    jm = {r_["product_name_snapshot"]: r_ for r_ in radky}
    over("O3 radky: puvodni + 1 radek na typ dilu s product_id, cenou z karty a souctem kusu", len(radky) == 3 and P.DILY["p186"]["nazev"] in jm and P.DILY["p91"]["nazev"] in jm
         and jm[P.DILY["p186"]["nazev"]]["product_id"] == PROD["p186"], [(r_["product_name_snapshot"], r_["qty"]) for r_ in radky])
    cnt1 = parse_pr(PR({"s1": "pln", "s2": "mix1"}))
    n186 = sum(n for b, n in cnt1.items() if SIRKA_BOXU[b] > 140)
    n91 = sum(n for b, n in cnt1.items() if SIRKA_BOXU[b] <= 140)
    over("O4 mnozstvi a ceny radku pricek", jm[P.DILY["p186"]["nazev"]]["qty"] == n186 and float(jm[P.DILY["p186"]["nazev"]]["unit_price_czk"]) == 39.0 and float(jm[P.DILY["p186"]["nazev"]]["line_total_czk"]) == 39.0 * n186
         and jm[P.DILY["p91"]["nazev"]]["qty"] == n91 and float(jm[P.DILY["p91"]["nazev"]]["line_total_czk"]) == 29.0 * n91, [(r_["qty"], r_["unit_price_czk"], r_["line_total_czk"]) for r_ in radky[1:]])
    over("O5 soucet radku pricek = cena pricek (bez DPH) a hlavicka sedi s QR (stejny vzorec)", abs(sum(float(r_["line_total_czk"]) for r_ in radky[1:]) - net) < 0.01 and abs(float(o["total_czk"]) - gross(100000 + net)) < 0.01)
    over("O6 poznamka objednavky: rozpis po policich / sufliccich a cena", o and "Příčky do multiboxů" in o["admin_note"] and "Police s multiboxy 1 - Plný set" in o["admin_note"] and "Výsuv s multiboxy 1 - Mix 1" in o["admin_note"] and "příček po boxech v pořadí Multibox 1…8: 6, 6, 6, 6, 6, 6, 6, 6" in o["admin_note"] and "příček po boxech v pořadí Multibox 1…7: 6, 1, 6, 1, 6, 1, 6" in o["admin_note"], o and o["admin_note"][-400:])
    over("O7 e-mail o prijeti nese rozpis pricek", MAILY and "Příčky do multiboxů" in MAILY[-1][2], MAILY and MAILY[-1][2][-300:])
    ac = sql("SELECT COUNT(*) AS n FROM scene_offer_acceptances WHERE offer_id=900311")[0]["n"]
    over("O8 prijeti zapsano jednou", ac == 1, ac)
    # O9: neplatny vyber = 400 a NIC se nezapise
    pred_o = sql("SELECT COUNT(*) AS n FROM shop_orders")[0]["n"]
    r = appmod.app.test_client().post("/api/public/offers/tok-o2/accept", json=dict(FORM, pricky="b99:1"))
    over("O9 neplatny vyber: 400 s textem, zadne prijeti, zadna objednavka", r.status_code == 400 and "příček" in r.get_json()["error"]
         and sql("SELECT COUNT(*) AS n FROM scene_offer_acceptances WHERE offer_id=900312")[0]["n"] == 0 and sql("SELECT COUNT(*) AS n FROM shop_orders")[0]["n"] == pred_o, (r.status_code, r.get_json()))
    # O10: zadny vyber = chovani jako driv
    r = appmod.app.test_client().post("/api/public/offers/tok-o3/accept", json=dict(FORM))
    o3 = sql("SELECT * FROM shop_orders WHERE order_number=%s", ((r.get_json() or {}).get("order_number"),))
    over("O10 bez vyberu: stejne jako driv (celkem 100 000 + DPH, jen puvodni radek, poznamka bez pricek)", r.status_code == 201 and o3 and abs(float(o3[0]["total_czk"]) - gross(100000)) < 0.01
         and sql("SELECT COUNT(*) AS n FROM shop_order_items WHERE order_id=%s", (o3[0]["id"],))[0]["n"] == 1 and "Příčky" not in (o3[0]["admin_note"] or ""), o3 and o3[0]["admin_note"])
    # O11: karty neaktivni + zakaznik s vyberem = 400
    karty(aktivni=0)
    r = appmod.app.test_client().post("/api/public/offers/tok-o4/accept", json=dict(FORM, pricky=PR({"s1": "mix1"})))
    over("O11 karty neaktivni: zakaznik s vyberem = 400, nic se nezapise", r.status_code == 400 and sql("SELECT COUNT(*) AS n FROM scene_offer_acceptances WHERE offer_id=900314")[0]["n"] == 0, r.status_code)
    karty()
    # O12: qty a montaz z ulozenych voleb (prefs) - QR ma shodnou castku jako objednavka
    vloz(900315, "tok-o5", ITEMS, 100000, True, AUTO)
    cl5 = appmod.app.test_client()
    rp = cl5.post("/api/public/offers/tok-o5/order-prefs", json={"qty": 2, "shipping_method": None, "payment_method": None, "delivery_state": None, "montaz_zvolena": True, "montaz_misto": "praha"})
    if rp.status_code == 200:
        SPAYD.clear()
        rq = cl5.get("/api/public/offers/tok-o5/payment-qr?qty=2&pr=" + PR({"s1": "mix2", "s3": "pln"}))
        a = SPAYD[-1] if SPAYD else None
        net = ocek_net({"s1": "mix2", "s3": "pln"})
        ocek = gross(round((100000 + net) * 2 * 1.10, 2))
        over("O12a QR s qty 2, montazi 10 % a pricky: castka = ((zbozi + pricky) x 2) x 1,10 + DPH", rq.status_code == 200 and abs(a - ocek) < 0.011, (rq.status_code, a, ocek))
        r = cl5.post("/api/public/offers/tok-o5/accept", json=dict(FORM, pricky=PR({"s1": "mix2", "s3": "pln"})))
        o5 = sql("SELECT * FROM shop_orders WHERE order_number=%s", ((r.get_json() or {}).get("order_number"),))
        over("O12b objednavka ma STEJNOU celkovou castku jako QR", r.status_code == 201 and o5 and abs(float(o5[0]["total_czk"]) - a) < 0.011, (r.status_code, o5 and float(o5[0]["total_czk"]), a))
        rr = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (o5[0]["id"],)) if o5 else []
        cnt5 = parse_pr(PR({"s1": "mix2", "s3": "pln"}))
        n186 = sum(n for b, n in cnt5.items() if SIRKA_BOXU[b] > 140) * 2
        j5 = {r_["product_name_snapshot"]: r_ for r_ in rr}
        over("O12c mnozstvi radku pricek se nasobi qty sestavy (2)", j5.get(P.DILY["p186"]["nazev"]) and j5[P.DILY["p186"]["nazev"]]["qty"] == n186, [(r_["product_name_snapshot"], r_["qty"]) for r_ in rr])
        mont = round((100000 + net) * 2 * 0.10, 2)
        mont_txt = f"{mont:,.2f}".replace(",", " ").replace(".", ",")
        mont_txt = mont_txt[:-3] if mont_txt.endswith(",00") else mont_txt
        over("O12d poznamka obsahuje montaz i pricky (castka montaze = 10 % ze zbozi VCETNE pricek x qty) a pocet kusu", o5 and "Montáž" in o5[0]["admin_note"] and f"+{mont_txt} Kč bez DPH" in o5[0]["admin_note"]
             and "Příčky do multiboxů" in o5[0]["admin_note"] and "počet kusů sestavy 2" in o5[0]["admin_note"], (o5 and o5[0]["admin_note"][-500:], mont_txt))
    else:
        print("PRESKOCENO O12 (order-prefs vratil %s: %s)" % (rp.status_code, rp.get_json()))
        over("O12 order-prefs nelze (preskoceno)", True)

if zname:
    # O13: vlastni kombinace v jedne police (ruzne pocty v boxech), pocty po boxech jdou do poznamky pro vyrobu
    vloz(900316, "tok-o6", ITEMS, 100000, True, AUTO)
    MIXO = {SK_SPEC["s1"][0]: 2, SK_SPEC["s1"][1]: 6, SK_SPEC["s1"][2]: 0, SK_SPEC["s1"][4]: 4}
    r = appmod.app.test_client().post("/api/public/offers/tok-o6/accept", json=dict(FORM, pricky=PR(boxy=MIXO)))
    o6 = sql("SELECT * FROM shop_orders WHERE order_number=%s", ((r.get_json() or {}).get("order_number"),))
    net6 = net_boxy({k: v for k, v in MIXO.items() if v})
    over("O13a vlastni kombinace: objednavka vznikla, hlavicka = (zbozi + pricky po boxech) + DPH", r.status_code == 201 and o6 and abs(float(o6[0]["total_czk"]) - gross(100000 + net6)) < 0.01, (r.status_code, o6 and float(o6[0]["total_czk"]), gross(100000 + net6)))
    nota = o6[0]["admin_note"] if o6 else ""
    over("O13b poznamka: vlastni kombinace, 3 z 8 boxu, 12 pricek a pocty po boxech v poradi Multibox 1..8", "Vlastní kombinace (3 z 8 boxů, 12 příček" in nota and "příček po boxech v pořadí Multibox 1…8: 2, 6, 0, 0, 4, 0, 0, 0" in nota, nota[-400:])
    rr6 = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (o6[0]["id"],)) if o6 else []
    over("O13c radky pricek: po dilech podle sirky boxu (soucet kusu 12) a celkem odpovida", sum(int(x["qty"]) for x in rr6[1:]) == 12 and abs(sum(float(x["line_total_czk"]) for x in rr6[1:]) - net6) < 0.01, [(x["product_name_snapshot"], x["qty"]) for x in rr6])
    r = appmod.app.test_client().post("/api/public/offers/tok-o6/accept", json=dict(FORM, pricky="b01:7"))
    over("O13d pocet pricek nad pocet slotu boxu (b01:7) = 400", r.status_code in (400, 409), r.status_code)

# ================================================================== orders.create_order_from_scene_offer(extra_items) primo
if zname:
    offer = {"id": 900321, "offer_number": "TESTPR321", "items": json.dumps(ITEMS), "offer_options": json.dumps({})}
    with real.cursor() as cur:
        oid, onum = ordersmod.create_order_from_scene_offer(cur, offer, name="T", company_ico="12345678", company_name="Test s.r.o.", company_dic="CZ1", company_address="A",
                                                            contact_email=FORM["contact_email"], contact_phone="1", total_czk=1234, qty_multiplier=3,
                                                            extra_items=[{"product_id": 990001, "name": "Příčka X", "qty": 4, "unit_price": 39.5}])
    real.commit()
    rr = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (oid,))
    over("D1 extra_items: radek ma qty 4 x 3 = 12, cena 39,5, celkem 474, product_id", len(rr) == 2 and rr[1]["qty"] == 12 and float(rr[1]["unit_price_czk"]) == 39.5 and float(rr[1]["line_total_czk"]) == 474.0 and rr[1]["product_id"] == 990001, [(r_["qty"], r_["line_total_czk"]) for r_ in rr])
    with real.cursor() as cur:
        oid2, _ = ordersmod.create_order_from_scene_offer(cur, dict(offer, id=900322), name="T", company_ico="12345678", company_name="Test s.r.o.", company_dic="CZ1", company_address="A",
                                                         contact_email=FORM["contact_email"], contact_phone="1", total_czk=1)
    real.commit()
    over("D2 bez extra_items beze zmeny (1 radek)", sql("SELECT COUNT(*) AS n FROM shop_order_items WHERE order_id=%s", (oid2,))[0]["n"] == 1)


# ================================================================== v5: podnosy ocelovych supliku (sk = 4) - model 4921 se vsemi dily (22 multiboxu + 3 podnosy 950 x 384 x 101), gating po skupinach
SPEC_F = v3d_glb.embedded_spec(GLB_FULL)
BOXY_F = P.boxy_ze_spec(SPEC_F)
TRAY = [b["id"] for b in BOXY_F if b["sk"] == "suplik"]
SK_F = {}
for _b in BOXY_F:
    SK_F.setdefault(_b["s"], []).append(_b["id"])
over("X0 model: 22 multiboxu a 3 podnosy supliku, skupiny s1 police 8, s2 vysuv 7, s3 podnos, s4 vysuv 7, s5 a s6 podnos", len(BOXY_F) == 25 and len(TRAY) == 3 and sorted(SK_F, key=lambda x: int(x[1:])) == ["s1", "s2", "s3", "s4", "s5", "s6"]
     and [len(SK_F[x]) for x in ("s1", "s2", "s3", "s4", "s5", "s6")] == [8, 7, 1, 7, 1, 1] and TRAY == ["b16", "b24", "b25"], (TRAY, {k_: len(v_) for k_, v_ in SK_F.items()}))
PROD_SUP = 990010


def karty_sup(cena=59, aktivni=1, archiv=0):
    """karta dilu ps384v101 (podnosy 950 x 384 x 101 z modelu 4921); cena None = karta chybi (karty() ji nezaklada, jen multiboxove)"""
    sql("DELETE FROM shop_products WHERE sku=%s", (P.DILY["ps384v101"]["sku"],))
    if cena is not None:
        sql("INSERT INTO shop_products (id, sku, name, price_czk_placeholder, active, is_archived) VALUES (%s,%s,%s,%s,%s,%s)", (PROD_SUP, P.DILY["ps384v101"]["sku"], P.DILY["ps384v101"]["nazev"], cena, aktivni, archiv))


VF, VF2 = 900330, 900331
ADM_F = vloz(VF, "tok-f", ITEMS, 100000, True, AUTO, glb=GLB_FULL)
vloz(VF2, "tok-f2", ITEMS, 100000, True, AUTO, glb=GLB_FULL)
scene_offers._PRICKY_SPEC_CACHE.clear()


def prf(token):
    r_ = GET("/api/public/offers/" + token)
    return r_.get_json().get("pricky") if r_.status_code == 200 else "HTTP %d" % r_.status_code


karty(); karty_sup(None)
pv, pa = prf("tok-f"), prf(ADM_F)
over("X1 jen multiboxove karty (karta supliku chybi): verejnost i admin vidi jen multiboxove skupiny s1, s2, s4 (22 boxu), dily p186 + p91", all(p_ and [s_["id"] for s_ in p_["skupiny"]] == ["s1", "s2", "s4"] and len(p_["boxy"]) == 22 and [d["klic"] for d in p_["dily"]] == ["p186", "p91"] and sorted(p_["typy"]) == ["395x186", "395x91"] for p_ in (pv, pa)), (pv and [s_["id"] for s_ in pv["skupiny"]], pa and [s_["id"] for s_ in pa["skupiny"]]))
karty_sup(59, aktivni=0)
pv, pa = prf("tok-f"), prf(ADM_F)
over("X2 karta supliku neaktivni: verejnost dal jen multiboxy, ADMIN vidi vsech 6 skupin (podnosy s3, s5, s6 skryto = true) a banner", pv and [s_["id"] for s_ in pv["skupiny"]] == ["s1", "s2", "s4"] and pv["nahled_admin"] is False
     and pa and [s_["id"] for s_ in pa["skupiny"]] == ["s1", "s2", "s3", "s4", "s5", "s6"] and [s_["skryto"] for s_ in pa["skupiny"]] == [False, False, True, False, True, True] and pa["nahled_admin"] is True, (pa and [(s_["id"], s_["skryto"]) for s_ in pa["skupiny"]]))
over("X3 admin: dil ps384v101 s ID karty a cenou 59, typ S950x384x101", pa and [(d["klic"], d["product_id"], d["cena"]) for d in pa["dily"]] == [("p186", PROD["p186"], 39.0), ("p91", PROD["p91"], 29.0), ("ps384v101", PROD_SUP, 59.0)] and "S950x384x101" in pa["typy"], pa and pa["dily"])
karty_sup(59, aktivni=1)
pv = prf("tok-f")
over("X4 karta supliku aktivni: verejnost vidi vsech 6 skupin bez banneru, dily p186, p91, ps384v101", pv and [s_["id"] for s_ in pv["skupiny"]] == ["s1", "s2", "s3", "s4", "s5", "s6"] and pv["nahled_admin"] is False and not any(s_["skryto"] for s_ in pv["skupiny"])
     and [d["klic"] for d in pv["dily"]] == ["p186", "p91", "ps384v101"] and len(pv["boxy"]) == 25, pv and [s_["id"] for s_ in pv["skupiny"]])
t3 = pv["typy"]["S950x384x101"]
over("X5 typ podnosu: max 9, druh suplik, osa b, L 950 x W 384 x H 101, lem 0, pocty 0..9 s deskami zepredu dozadu, dil ps384v101", t3["max"] == 9 and t3["druh"] == "suplik" and t3["os"] == "b" and (t3["L"], t3["W"], t3["H"], t3["lem"]) == (950.0, 384.0, 101.0, 0.0)
     and [x["n"] for x in t3["pocty"]] == list(range(10)) and t3["dil"] == "ps384v101" and all(d["r"] == [2.0, 93.0, 362.0] for d in t3["pocty"][9]["desky"]) and [d["s"][0] for d in t3["pocty"][9]["desky"]] == [75.0 + 100.0 * j for j in range(9)], t3["pocty"][9]["desky"][:2])
sk3 = [s_ for s_ in pv["skupiny"] if s_["id"] == "s3"][0]
over("X6 skupina s podnosem: popis 'Suplíky 1', druh suplik, jediny podnos -> jen sety bez a pln (mixy se shoduji s plnym), pln = 9 pricek za 531", sk3["popis"] == "Šuplíky 1" and sk3["k"] == "suplik" and sk3["boxu"] == 1 and list(sk3["sety"]) == ["bez", "pln"]
     and sk3["sety"]["pln"]["priccek"] == 9 and sk3["sety"]["pln"]["cena"] == 531.0 and sk3["sety"]["pln"]["dily"] == {"ps384v101": 9}, sk3)
over("X7 popisy supliku podle poradi: Suplíky 1, 2, 3 (s3, s5, s6); multiboxove skupiny maji sve popisy", [s_["popis"] for s_ in pv["skupiny"] if s_["k"] == "suplik"] == ["Šuplíky 1", "Šuplíky 2", "Šuplíky 3"]
     and [s_["popis"] for s_ in pv["skupiny"] if s_["k"] != "suplik"] == ["Police s multiboxy 1", "Výsuv s multiboxy 1", "Výsuv s multiboxy 2"])
over("X8 verejny JSON nenese jmena komponent ani Default / Suplik", not any(w in json.dumps(pv) for w in ("Clone", "Suplikocel", "suplikyocel", "Default", "unity")))
karty(aktivni=0); karty_sup(59, aktivni=1)
pv, pa = prf("tok-f"), prf(ADM_F)
over("X9 multiboxove karty neaktivni, karta supliku aktivni: verejnost vidi jen podnosy (s3, s5, s6), admin vsech 6", pv and [s_["id"] for s_ in pv["skupiny"]] == ["s3", "s5", "s6"] and [d["klic"] for d in pv["dily"]] == ["ps384v101"]
     and pa and len(pa["skupiny"]) == 6 and [s_["skryto"] for s_ in pa["skupiny"]] == [True, True, False, True, False, False], (pv and [s_["id"] for s_ in pv["skupiny"]]))
karty(); karty_sup(None)
karty(jen=("p186",)); karty_sup(59, aktivni=1)
pv = prf("tok-f")
over("X11 chybi karta p91: vsechny multiboxove skupiny maji i 91 mm boxy -> nenabizeji se, zustanou podnosy", pv and [s_["id"] for s_ in pv["skupiny"]] == ["s3", "s5", "s6"], pv and [s_["id"] for s_ in pv["skupiny"]])
karty(); karty_sup(59, aktivni=1)

# ---- QR platba: vyber po boxech zahrnuje podnosy (b16 = 9 slotu, b24, b25); b01 = multibox 395 x 186 (6 slotu)
def qrf(token, qs):
    SPAYD.clear()
    r_ = GET(f"/api/public/offers/{token}/payment-qr?{qs}")
    return r_, (SPAYD[-1] if SPAYD else None)


r, a = qrf("tok-f", "qty=1&pr=b16:9")
over("XQ1 podnos plny (9 pricek x 59 = 531): castka = (100 000 + 531) + DPH", r.status_code == 200 and a == gross(100000 + 531), (r.status_code, a, gross(100000 + 531)))
r, a = qrf("tok-f", "qty=2&pr=b01:6,b02:6,b16:9,b24:4")
over("XQ2 multiboxy + podnosy, qty 2: (2 x 6 x 39 + 13 x 59 = 468 + 767) = 1 235 za kus, x 2", r.status_code == 200 and a == gross(2 * (100000 + 468 + 767)), (r.status_code, a, gross(2 * (100000 + 1235))))
r, a = qrf("tok-f", "qty=1&pr=b16:10")
over("XQ3 pocet pricek nad sloty podnosu (10 > 9) = 400, zadna QR", r.status_code == 400 and a is None, r.status_code)
r, a = qrf("tok-f", "qty=1&pr=b24:5,b25:9")
over("XQ4 dva podnosy: 5 + 9 = 14 pricek x 59 = 826", r.status_code == 200 and a == gross(100000 + 14 * 59), (r.status_code, a))
karty_sup(59, aktivni=0)
r, a = qrf("tok-f", "qty=1&pr=b16:9")
over("XQ5 karta supliku neaktivni: zakaznik s podnosem = 400", r.status_code == 400 and a is None, r.status_code)
r, a = qrf("tok-f", "qty=1&pr=b01:6")
over("XQ6 karta supliku neaktivni: multibox dal projde (skupiny jsou nezavisle)", r.status_code == 200 and a == gross(100000 + 6 * 39), (r.status_code, a))
r, a = qrf(ADM_F, "qty=1&pr=b16:9")
over("XQ7 karta supliku neaktivni: admin odkaz s podnosem projde (nahled)", r.status_code == 200 and a == gross(100000 + 531), (r.status_code, a))
karty_sup(59, aktivni=1)

# ---- poznamka objednavky: slova podle druhu (jednotkove nad vysledkem spocti)
CENY_F = {"p186": {"id": PROD["p186"], "cena": 39.0, "nazev": P.DILY["p186"]["nazev"], "aktivni": True}, "p91": {"id": PROD["p91"], "cena": 29.0, "nazev": P.DILY["p91"]["nazev"], "aktivni": True},
          "ps384v101": {"id": PROD_SUP, "cena": 59.0, "nazev": P.DILY["ps384v101"]["nazev"], "aktivni": True}}
SKF = P.skupiny_z_boxu(BOXY_F, CENY_F)
res_s = P.spocti(BOXY_F, SKF, {"b16": 9, "b24": 4}, CENY_F)
txt_s = scene_offers._pricky_poznamka(res_s, 1)
over("XN1 poznamka jen podnosy: nadpis 'Priccky do suplíku', skupiny Suplíky 1 / 2 a jednotky suplíku", txt_s.startswith("Příčky do šuplíků (cena za 1 ks sestavy bez DPH): ") and "Šuplíky 1 - Plný set (1 z 1 šuplíků, 9 příček, 531 Kč; příček po šuplících v pořadí Šuplík 1…1: 9)" in txt_s
     and "Šuplíky 2 - Vlastní kombinace (1 z 1 šuplíků, 4 příček, 236 Kč; příček po šuplících v pořadí Šuplík 1…1: 4)" in txt_s and txt_s.endswith("celkem 767 Kč."), txt_s)
res_m = P.spocti(BOXY_F, SKF, {"b01": 6, "b16": 9}, CENY_F)
txt_m = scene_offers._pricky_poznamka(res_m, 2)
over("XN2 poznamka smisena: nadpis 'Priccky do multiboxu a suplíku', multibox boxy / Multibox, podnos suplíky, pocet kusu", txt_m.startswith("Příčky do multiboxů a šuplíků (") and "Police s multiboxy 1 - Vlastní kombinace (1 z 8 boxů, 6 příček, 234 Kč; příček po boxech v pořadí Multibox 1…8: 6, 0, 0, 0, 0, 0, 0, 0)" in txt_m and "Šuplíky 1 - Plný set (1 z 1 šuplíků" in txt_m and "počet kusů sestavy 2" in txt_m, txt_m)
over("XN3 poznamka jen multibox: puvodni nadpis 'Priccky do multiboxu' beze zmeny", scene_offers._pricky_poznamka(P.spocti(BOXY_F, SKF, {"b01": 6}, CENY_F), 1).startswith("Příčky do multiboxů (cena za 1 ks sestavy bez DPH): "))

# ---- prijeti nabidky s podnosy (stejny tok jako O1): radky po dilech vcetne dilu supliku, hlavicka = QR, poznamka
if zname:
    vloz(900332, "tok-fo", ITEMS, 100000, True, AUTO, glb=GLB_FULL)
    MAILY.clear()
    r = appmod.app.test_client().post("/api/public/offers/tok-fo/accept", json=dict(FORM, pricky="b01:6,b16:9,b24:4"))
    over("XO1 prijeti s multiboxem a podnosy: 201 a cislo objednavky", r.status_code == 201 and r.get_json().get("order_number"), (r.status_code, r.get_json()))
    of = sql("SELECT * FROM shop_orders WHERE order_number=%s", ((r.get_json() or {}).get("order_number"),))
    of = of[0] if of else None
    rf = sql("SELECT * FROM shop_order_items WHERE order_id=%s ORDER BY id", (of["id"],)) if of else []
    jf = {x["product_name_snapshot"]: x for x in rf}
    nf = 6 * 39 + 13 * 59
    over("XO2 radky: puvodni + p186 (6 x 39) + ps384v101 (13 x 59, product_id karty supliku), hlavicka = (zbozi + pricky) + DPH", of and abs(float(of["total_czk"]) - gross(100000 + nf)) < 0.01 and len(rf) == 3
         and jf[P.DILY["p186"]["nazev"]]["qty"] == 6 and jf[P.DILY["ps384v101"]["nazev"]]["qty"] == 13 and jf[P.DILY["ps384v101"]["nazev"]]["product_id"] == PROD_SUP and float(jf[P.DILY["ps384v101"]["nazev"]]["unit_price_czk"]) == 59.0
         and float(jf[P.DILY["ps384v101"]["nazev"]]["line_total_czk"]) == 767.0, [(x["product_name_snapshot"], x["qty"], x["line_total_czk"]) for x in rf])
    over("XO3 poznamka objednavky: smisena (multiboxy a suplíky) s pocty po podnosech a e-mail o prijeti ji nese", of and "Příčky do multiboxů a šuplíků" in of["admin_note"] and "Šuplíky 1 - Plný set" in of["admin_note"] and "Šuplíky 2 - Vlastní kombinace (1 z 1 šuplíků, 4 příček" in of["admin_note"]
         and MAILY and "Šuplíky 1" in MAILY[-1][2], of and of["admin_note"][-400:])
    pred_o = sql("SELECT COUNT(*) AS n FROM shop_orders")[0]["n"]
    vloz(900333, "tok-fo2", ITEMS, 100000, True, AUTO, glb=GLB_FULL)
    karty_sup(59, aktivni=0)
    r = appmod.app.test_client().post("/api/public/offers/tok-fo2/accept", json=dict(FORM, pricky="b16:9"))
    over("XO4 karta supliku neaktivni: zakaznik s podnosem = 400, nic se nezapise", r.status_code == 400 and sql("SELECT COUNT(*) AS n FROM scene_offer_acceptances WHERE offer_id=900333")[0]["n"] == 0 and sql("SELECT COUNT(*) AS n FROM shop_orders")[0]["n"] == pred_o, r.status_code)
    r = appmod.app.test_client().post("/api/public/offers/tok-fo2/accept", json=dict(FORM, pricky="b16:10"))
    over("XO5 pocet nad sloty podnosu (b16:10) = 400", r.status_code == 400, r.status_code)
    karty_sup(59, aktivni=1)

# ================================================================== uklid a kontrola ostrych tabulek
with real.cursor() as cur:
    for t in TEMP_LIKE + TEMP_COPY:
        cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `{t}`")
        cur.execute(f"DROP TEMPORARY TABLE IF EXISTS `_tpl_{t}`")
real.commit()
shutil.rmtree(MODELY, ignore_errors=True)
PO = stav_ostrych()
over("Z ostre tabulky nabidek, voleb, prijeti, objednavek, polozek, uzivatelu, zakazniku a produktu jsou beze zmeny", PRED == PO, (PRED, PO))
ok = sum(vysl)
print(f"\nVYSLEDEK pricky do multiboxu - backend: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
