#!/opt/konfigurator/api/venv/bin/python
"""Sleva v online nabidce (offer_options.discount_pct) - backend (bot16, 2026-10-07).

Robert: "chci v cenovem souhrnu online nabidky nabidnout slevu, i v te 0133 zpetne". Sleva v % z ceny ZBOZI (bez dopravy a montaze) se nastavi u nabidky (admin: Upravit nabidku,
zpetne i u uz rozeslane), ulozi se do offer_options.discount_pct a rozhoduje o ni JEN `_offer_discount_pct` / `_offer_discount_net` (verejny payload, QR platba, objednavka a e-mail;
montaz se pocita z ceny PO sleve).

Cast A  _sanitize_discount_pct   (cislo >0 az 100, carka, 0 / bool / NaN / zaporne / nesmysl -> None)
Cast B  _sanitize_offer_options  (nove pole; ostatni klice BEZE ZMENY oproti puvodni verzi)
Cast C  _offer_discount_pct / _offer_discount_net
Cast D  _offer_gross_total       (sleva z ceny zbozi vcetne ks, montaz z ceny po sleve, doprava beze zmeny; BEZ slevy shodne s puvodni funkci na cele mrizce)
Cast E  admin_scene_offer_update (SKUTECNY handler z AST + atrapy DB: sleva z formulare se ulozi, prazdna = None, chybejici klic ji ZACHOVA, ostatni klice beze zmeny)
Cast F  staticke kontrakty       (verejny payload nese discount_pct z _offer_discount_pct; montaz poznamka pocita z ceny po sleve)
Cast G  mutace                   (puvodni funkce MUSI na B, D, E selhat)
Bez DB a bez Flasku, nic nezapisuje.     Spusteni: api/venv/bin/python3 test_sleva_backend.py     Kandidat: SCENE_OFFERS_PY=/cesta/k/scene_offers.py api/venv/bin/python3 test_sleva_backend.py
"""
import ast
import datetime
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SO = os.environ.get("SCENE_OFFERS_PY", os.path.join(HERE, "..", "..", "api", "scene_offers.py"))
from stara_verze_sleva import STARA_ADMIN_SCENE_OFFER_UPDATE, STARA_OFFER_GROSS_TOTAL, STARA_SANITIZE_OFFER_OPTIONS  # noqa: E402

ZDROJ = open(SO, encoding="utf-8").read()
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def funkce(jmeno):
    n = next((x for x in ast.parse(ZDROJ).body if isinstance(x, ast.FunctionDef) and x.name == jmeno), None)
    if n is None:
        return None
    n.decorator_list = []
    return n


JMENA = ["_sanitize_montaz_pct", "_sanitize_discount_pct", "_sanitize_offer_options", "_offer_options_from_row", "_offer_montaz_pct", "_je_auto_sestava", "_offer_discount_pct",
         "_offer_discount_net", "_offer_montaz_net", "_offer_gross_total", "_je_rucni", "_rucni_cislo", "_rucni_mnozstvi", "_vycisti_rucni_polozku", "_over_rucni_polozky", "admin_scene_offer_update"]


def slovnik(stara_sanitize=False, stara_gross=False, stara_update=False):
    fns = {j: funkce(j) for j in JMENA}
    if stara_sanitize:
        fns["_sanitize_offer_options"] = ast.parse(STARA_SANITIZE_OFFER_OPTIONS).body[0]
    if stara_gross:
        fns["_offer_gross_total"] = ast.parse(STARA_OFFER_GROSS_TOTAL).body[0]
    if stara_update:
        fns["admin_scene_offer_update"] = ast.parse(STARA_ADMIN_SCENE_OFFER_UPDATE).body[0]
    ns = {"json": json, "datetime": datetime, "VAT_RATE": 21, "re": re, "os": os, "OFFER_IMAGES_DIR": "/nonexistent", "KATALOG_GLB_DIR": "/nonexistent"}
    konst = [n for n in ast.parse(ZDROJ).body if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id.startswith("MANUAL_") for t in n.targets for x in ast.walk(t))]
    telo = konst + [f for f in (fns[j] for j in JMENA) if f is not None]
    exec(compile(ast.Module(body=telo, type_ignores=[]), "scene_offers", "exec"), ns)
    return ns


NS = slovnik()
chybi = [j for j in ("_sanitize_discount_pct", "_offer_discount_pct", "_offer_discount_net") if NS.get(j) is None]
if chybi:
    over(f"0 soubor {os.path.basename(SO)} obsahuje funkce {chybi}", False, "chybi - puvodni verze souboru, sleva neni implementovana")
    print(f"\nVYSLEDEK sleva v online nabidce - backend: 0/{len(vysl)} OK (puvodni verze)")
    sys.exit(1)

print("== A _sanitize_discount_pct")
san = NS["_sanitize_discount_pct"]
PRIPADY_A = [(None, None), ("", None), (0, None), ("0", None), (0.0, None), (10, 10.0), (10.0, 10.0), ("12,5", 12.5), ("12.5", 12.5), (100, 100.0), (100.01, None), (-1, None), (-0.01, None),
             ("abc", None), (True, None), (False, None), (float("nan"), None), (float("inf"), None), ([], None), ({}, None), ("  ", None), (0.004, None), (7.556, 7.56)]
for vstup, cekano in PRIPADY_A:
    try:
        got = san(vstup)
    except Exception as e:                       # noqa: BLE001
        got = f"VYJIMKA {e!r}"
    over(f"A _sanitize_discount_pct({vstup!r}) == {cekano!r}", got == cekano and type(got) == type(cekano), got)

print("== B _sanitize_offer_options")
san_opt = NS["_sanitize_offer_options"]
stara_opt = slovnik(stara_sanitize=True)["_sanitize_offer_options"]
over("B vychozi volby (prazdny vstup) maji discount_pct None = bez slevy", san_opt({})["discount_pct"] is None, san_opt({}))
over("B discount_pct 10 se ulozi jako 10.0, '12,5' jako 12.5", san_opt({"discount_pct": 10})["discount_pct"] == 10.0 and san_opt({"discount_pct": "12,5"})["discount_pct"] == 12.5, None)
over("B discount_pct 0 / nesmysl / zaporne -> None (bez slevy)", all(san_opt({"discount_pct": v})["discount_pct"] is None for v in (0, "0", 150, "x", -3, True)), None)
over("B vstup, ktery neni slovnik, nespadne a da vychozi", san_opt(None)["discount_pct"] is None and san_opt("x")["discount_pct"] is None, None)
VSTUPY_B = [{}, None, {"show_qr": False, "delivery_term": " 4-6 tydnu ", "hidden_payment_method": "dobirka", "fixed_deposit_pct": 70, "hide_bom_prices": True, "hidden_delivery_state": "smontovano",
                      "is_vehicle_assembly": True, "manual_assembled_shipping_czk": "1500", "vandr_single_drawing": True, "montaz_pct": 15},
            {"fixed_deposit_pct": 20, "hidden_payment_method": "x", "manual_assembled_shipping_czk": -5}, {"discount_pct": 12.5, "show_qr": False, "montaz_pct": 0}]
shoda = True
for v in VSTUPY_B:
    nove, stare = dict(san_opt(v)), dict(stara_opt(v))
    nove.pop("discount_pct")
    if nove != stare:
        shoda = False
        print("   rozdil u vstupu", v, nove, stare)
over("B vsechny OSTATNI klice (vc. montaz_pct) jsou beze zmeny oproti puvodni verzi (5 sad vstupu)", shoda, None)
over("B JSON-serializovatelne (uklada se do sloupce JSON)", bool(json.dumps(san_opt({"discount_pct": "12,5"}))), None)

print("== C _offer_discount_pct / _offer_discount_net")
dp, dn = NS["_offer_discount_pct"], NS["_offer_discount_net"]
over("C bez slevy: None / {} / 0 / nesmysl / neslovnik -> 0.0", all(dp(o) == 0.0 and isinstance(dp(o), float) for o in (None, {}, {"discount_pct": None}, {"discount_pct": 0}, {"discount_pct": "x"}, {"discount_pct": 150}, "abc")), None)
over("C sleva 10 % -> 10.0, '12,5' -> 12.5", dp({"discount_pct": 10}) == 10.0 and dp({"discount_pct": "12,5"}) == 12.5, None)
over("C castka slevy: 10 % z 12 345 = 1 234,50; 12,5 % z 10 000 = 1 250; bez slevy 0.0", dn({"discount_pct": 10}, 12345) == 1234.5 and dn({"discount_pct": 12.5}, 10000) == 1250.0 and dn({}, 10000) == 0.0, (dn({"discount_pct": 10}, 12345), dn({"discount_pct": 12.5}, 10000)))
over("C zaokrouhleni na halire: pul halire NAHORU jako JS Math.round na strance - 7,5 % z 1 001 = 75,075 -> 75,08; 12,5 % z 27 353 = 3 419,125 -> 3 419,13", dn({"discount_pct": 7.5}, 1001) == 75.08 and dn({"discount_pct": 12.5}, 27353) == 3419.13, (dn({"discount_pct": 7.5}, 1001), dn({"discount_pct": 12.5}, 27353)))

print("== D _offer_gross_total")
gross = NS["_offer_gross_total"]
gross_stara = slovnik(stara_gross=True)["_offer_gross_total"]


def nabidka(total, options=None):
    return {"total_price": total, "offer_options": (json.dumps(options) if options is not None else None)}


auto = {"is_vehicle_assembly": True}
over("D sleva 10 % z 10 000: 9 000 bez DPH -> 10 890,00 s DPH", gross(nabidka(10000, {"discount_pct": 10}), {}, "0") == 10890.0, gross(nabidka(10000, {"discount_pct": 10}), {}, "0"))
over("D sleva a pocet kusu (3 ks, 10 %): 30 000 - 3 000 = 27 000 -> 32 670,00", gross(nabidka(10000, {"discount_pct": 10}), {"qty": 3}, "0") == 32670.0, gross(nabidka(10000, {"discount_pct": 10}), {"qty": 3}, "0"))
over("D sleva 12,5 % z 8 000: 7 000 -> 8 470,00", gross(nabidka(8000, {"discount_pct": 12.5}), {}, "0") == 8470.0, None)
over("D sleva 100 % = nula", gross(nabidka(10000, {"discount_pct": 100}), {}, "0") == 0.0, None)
over("D sestava do auta, zvolena montaz 15 % z ceny PO sleve (10 000 - 10 % = 9 000, montaz 1 350): 10 350 -> 12 523,50",
     gross(nabidka(10000, {**auto, "discount_pct": 10, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1}, "20") == 12523.5, gross(nabidka(10000, {**auto, "discount_pct": 10, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1}, "20"))
over("D vychozi sazba montaze z nastaveni (20 %) se bere z ceny po sleve: 9 000 + 1 800 = 10 800 -> 13 068,00",
     gross(nabidka(10000, {**auto, "discount_pct": 10}), {"montaz_zvolena": 1, "qty": 1}, "20") == 13068.0, None)
over("D doprava (Toptrans) se NESLEVNUJE: 10 000 - 10 % + 1 000 doprava = 10 000 -> 12 100,00",
     gross(nabidka(10000, {"discount_pct": 10}), {"qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "0") == 12100.0, gross(nabidka(10000, {"discount_pct": 10}), {"qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "0"))
over("D rucne zadana cena dopravy 'smontovano' se NESLEVNUJE: 9 000 + 1 500 = 10 500 -> 12 705,00",
     gross(nabidka(10000, {"discount_pct": 10, "manual_assembled_shipping_czk": 1500}), {"qty": 1, "shipping_method": "toptrans", "delivery_state": "smontovano", "toptrans_price_czk": 800}, "0") == 12705.0, None)
over("D nezvolena montaz se nepricita ani se slevou: 9 000 -> 10 890,00", gross(nabidka(10000, {**auto, "discount_pct": 10, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") == 10890.0, None)
over("D offer_options NULL (starsi nabidka) se pocita jako drive: 10 000 -> 12 100,00", gross({"total_price": 10000, "offer_options": None}, {}, "0") == 12100.0, None)
shody, pocet = 0, 0
for total, qty, ship, vozidlo, zvol, glob, ruc, mpct in itertools.product((1, 999, 10000, 27353, 123456), (None, 1, 2, 7), (None, "vlastni", "toptrans"), (False, True), (None, 0, 1), ("0", "20", "25.5", None, 0, 7),
                                                                              (None, 1500.0), (None, 0, 12.5)):
    opts = {"is_vehicle_assembly": vozidlo, "manual_assembled_shipping_czk": ruc, "montaz_pct": mpct}
    prefs = None if qty is None else {"qty": qty, "shipping_method": ship, "toptrans_price_czk": 800, "delivery_state": "smontovano", "montaz_zvolena": zvol}
    pocet += 1
    shody += gross(nabidka(total, opts), prefs, glob) == gross_stara(nabidka(total, opts), prefs, glob)
over(f"D BEZ slevy shodne s puvodni funkci na cele mrizce ({pocet} kombinaci)", shody == pocet, (shody, pocet))
over("D sleva None / 0 / nesmysl v ulozenych volbach = stejne jako bez slevy", all(gross(nabidka(10000, {"discount_pct": v}), {"qty": 2}, "0") == gross(nabidka(10000, {}), {"qty": 2}, "0") for v in (None, 0, "x", -5, 150)), None)

print("== E admin_scene_offer_update (skutecny handler)")


class Pozadavek:
    def __init__(self, body):
        self.body = body

    def get_json(self, silent=False):
        return self.body


class FakeCur:
    def __init__(self, stav):
        self.stav = stav

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.stav["sql"].append((" ".join(sql.split()), params))
        self.posledni = " ".join(sql.split())

    def fetchone(self):
        return self.stav["radek"] if self.posledni.startswith("SELECT items") else None


class FakeConn:
    def __init__(self, stav):
        self.stav = stav

    def cursor(self):
        return FakeCur(self.stav)

    def commit(self):
        self.stav["commit"] = True

    def rollback(self):
        self.stav["rollback"] = True

    def close(self):
        pass


def spust_update(ns, fn_ast, body, aktualni_options, rev=3):
    stav = {"sql": [], "radek": {"items": json.dumps(body["items"]), "total_price": 1000, "editable_text_popis": "", "editable_text_patka": "",
                                 "offer_options": (json.dumps(aktualni_options) if aktualni_options is not None else None), "revision_number": rev}}
    ns2 = dict(ns)
    ns2.update({"request": Pozadavek(body), "jsonify": lambda x: x, "current_user": lambda: {"id": 7}, "get_conn": lambda: FakeConn(stav), "log_audit": lambda *a, **k: None})
    exec(compile(ast.Module(body=[fn_ast], type_ignores=[]), "update", "exec"), ns2)
    odp = ns2["admin_scene_offer_update"](42)
    ulozene = None
    for sql, params in stav["sql"]:
        if sql.startswith("UPDATE scene_offers SET"):
            ulozene = json.loads(params[4])
    return odp, ulozene, stav


BODY = {"items": [{"name": "x", "total": 1000}], "total_price": 1000, "editable_text": {"popis": "p", "patka": "f"}, "change_note": "t"}


def body_s(options):
    b = dict(BODY)
    if options is not ...:
        b["offer_options"] = options
    return b


FN = funkce("admin_scene_offer_update")
NSU = slovnik()
NSU.pop("admin_scene_offer_update", None)
odp, ul, st = spust_update(NSU, FN, body_s({"show_qr": True, "discount_pct": 10}), None)
over("E1 sleva z formulare (10) se ulozi (zpetne u nabidky bez slevy)", ul is not None and ul["discount_pct"] == 10.0 and odp.get("status") == "ok", (ul, odp))
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s({"show_qr": True, "discount_pct": None}), {"discount_pct": 10})
over("E2 prazdna sleva z formulare (None) = sleva zrusena", ul is not None and ul["discount_pct"] is None, ul)
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s({"show_qr": True}), {"discount_pct": 10})
over("E3 formular slevu NEPOSLAL (starsi admin.html v cache) -> ulozena sleva 10 se ZACHOVA", ul is not None and ul["discount_pct"] == 10.0, ul)
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s(...), {"discount_pct": 10})
over("E4 pozadavek bez offer_options vubec -> sleva zustane", ul is not None and ul["discount_pct"] == 10.0, ul)
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s({"discount_pct": 150}), {"discount_pct": 10})
over("E5 nesmyslna sleva z formulare (150) se neulozi (None = bez slevy)", ul is not None and ul["discount_pct"] is None, ul)
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s({"show_qr": False, "discount_pct": 5, "montaz_pct": 12.5}), {"vandr_single_drawing": True, "montaz_pct": 10, "discount_pct": 20})
over("E6 priznak Vandr nabidky zustava (regrese), montaz a sleva se zmeni nezavisle", ul is not None and ul.get("vandr_single_drawing") is True and ul["montaz_pct"] == 12.5 and ul["discount_pct"] == 5.0, ul)
FN = funkce("admin_scene_offer_update")
odp, ul, st = spust_update(NSU, FN, body_s({"show_qr": True}), None)
over("E7 starsi nabidka bez offer_options (NULL) + formular bez slevy -> None, nic nespadne", ul is not None and ul["discount_pct"] is None, ul)
over("E8 pred zapisem se do revizi archivuje puvodni stav (INSERT scene_offer_revisions), revize +1", any(s.startswith("INSERT INTO scene_offer_revisions") for s, _ in st["sql"]) and odp.get("revision_number") == 4, odp)

print("== F staticke kontrakty")


def zdroj_funkce(jmeno):
    n = next(x for x in ast.parse(ZDROJ).body if isinstance(x, ast.FunctionDef) and x.name == jmeno)
    return ast.get_source_segment(ZDROJ, n)


pub = zdroj_funkce("public_offer_get")
over("F verejny payload nese discount_pct z _offer_discount_pct", '"discount_pct": _offer_discount_pct(' in pub, None)
over("F poznamka o montazi pocita z ceny PO sleve (_offer_discount_net) a to pise do textu", "_offer_discount_net(" in zdroj_funkce("_montaz_poznamka") and "po slevě" in zdroj_funkce("_montaz_poznamka"), None)
over("F _offer_gross_total pouziva _offer_discount_net (jedine misto vypoctu slevy)", "_offer_discount_net(" in zdroj_funkce("_offer_gross_total"), None)
over("F nikde jinde se sleva nenasobi procentem (pct / 100 jen v _offer_discount_net a montazi)", len(re.findall(r"discount_pct|_offer_discount_pct", ZDROJ)) >= 6, None)

print("== G mutace: puvodni funkce MUSI selhat")
over("G puvodni _sanitize_offer_options nema discount_pct (B by propadlo)", "discount_pct" not in stara_opt({"discount_pct": 10}), stara_opt({"discount_pct": 10}))
over("G puvodni _offer_gross_total ignoruje slevu (D by propadlo): 10 000 + sleva 10 % -> 12 100 misto 10 890", gross_stara(nabidka(10000, {"discount_pct": 10}), {}, "0") == 12100.0, None)
FN_STARA = ast.parse(STARA_ADMIN_SCENE_OFFER_UPDATE).body[0]
odp, ul, st = spust_update(slovnik(stara_update=True) | {}, FN_STARA, body_s({"show_qr": True}), {"discount_pct": 10})
over("G puvodni admin_scene_offer_update slevu pri chybejicim klici ZAHODI (E3 by propadlo)", ul is not None and ul.get("discount_pct") is None, ul)

# H server a stranka musi vychazet na stejne haliře: krizova kontrola proti JS vzorci stranky `Math.round(cena * pct) / 100` na mrizce cen a procent (vc. pul haliru)
import subprocess
GRID = [[c, p] for c in (1, 7, 99, 1001, 10001, 12345, 27353, 136905, 273810, 999999) for p in (0.5, 1, 2.5, 7.3, 7.5, 10, 12.5, 15, 33.33, 99.99)]
js_out = json.loads(subprocess.check_output(["node", "-e", "const g=%s; console.log(JSON.stringify(g.map(([c,p])=>Math.round(c*p)/100)))" % json.dumps(GRID)], text=True))
py_out = [dn({"discount_pct": p}, c) for c, p in GRID]
over("H castka slevy: Python _offer_discount_net == JS Math.round(cena * pct) / 100 na mrizce %d kombinaci (vc. pul haliru)" % len(GRID), js_out == py_out, [(g, a, b) for g, a, b in zip(GRID, js_out, py_out) if a != b][:5])

ok = sum(vysl)
print(f"\nVYSLEDEK sleva v online nabidce - backend: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
