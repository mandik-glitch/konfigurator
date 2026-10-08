#!/opt/konfigurator/api/venv/bin/python
"""Sazba montaze pro konkretni nabidku (offer_options.montaz_pct) - backend (bot5, 2026-10-01).

Robert: "montaz v online nabidce chci pred vytvorenim nabidky zvolit jako % castku". Sazba se zvoli v dialogu pri vytvoreni nabidky ve
scene, ulozi se do offer_options.montaz_pct a rozhoduje o ni JEDINA funkce `_offer_montaz_pct` (verejny payload, QR platba, objednavka).
Nabidky bez vlastni sazby (vsechny starsi + Vandr) pouzivaji ZIVOU vychozi sazbu z app_settings - jako dosud.

Cast A  _sanitize_montaz_pct          (cislo 0-100, carka, bool/NaN/zaporne/nesmysl -> None)
Cast B  _sanitize_offer_options       (nove pole; ostatni klice BEZE ZMENY oproti puvodni verzi)
Cast C  _offer_montaz_pct             (vlastni vyhrava; 0 NENI "chybi"; jinak vychozi)
Cast D  _offer_gross_total            (QR + objednavka: vlastni sazba, 0; BEZ vlastni sazby shodne s puvodni funkci na cele mrizce)
Cast E  admin_scene_offer_update      (SKUTECNY handler z AST + atrapy DB: sazba z formulare se ulozi; chybejici klic ji ZACHOVA, nesmaze ji
                                       starsi admin.html v cache; priznak Vandr zustava)
Cast F  staticke kontrakty            (verejny payload i QR/objednavka jdou pres _offer_montaz_pct / _offer_gross_total, nikde jinde se montaz
                                       nepocita)
Cast G  mutace                        (puvodni funkce MUSI na A-E selhat)
Bez DB a bez Flasku, nic nezapisuje.     Spusteni: api/venv/bin/python3 test_montaz_pct_backend.py
Kandidat pred nasazenim: SCENE_OFFERS_PY=/cesta/k/scene_offers.py api/venv/bin/python3 test_montaz_pct_backend.py
"""
import ast
import datetime
import itertools
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SO = os.environ.get("SCENE_OFFERS_PY", os.path.join(HERE, "..", "..", "api", "scene_offers.py"))
from stara_verze import STARA_ADMIN_SCENE_OFFER_UPDATE, STARA_OFFER_GROSS_TOTAL, STARA_SANITIZE_OFFER_OPTIONS  # noqa: E402

ZDROJ = open(SO, encoding="utf-8").read()
STROM = ast.parse(ZDROJ)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def funkce(jmeno, strom=STROM):
    n = next((x for x in strom.body if isinstance(x, ast.FunctionDef) and x.name == jmeno), None)
    assert n is not None, f"{SO}: chybi funkce {jmeno}"
    n.decorator_list = []
    return n


def slovnik(stara_sanitize=False, stara_gross=False, stara_update=False, extra=None, ref_gross=False):
    """Namespace se SKUTECNYMI funkcemi ze zdroje (volitelne nahrazenymi puvodni verzi - mutace)."""
    jmena = ["_sanitize_montaz_pct", "_sanitize_discount_pct", "_sanitize_offer_options", "_offer_options_from_row", "_offer_montaz_pct", "_je_auto_sestava", "_offer_discount_pct", "_offer_discount_net", "_offer_montaz_net", "_offer_gross_total",
             "_je_rucni", "_rucni_cislo", "_rucni_mnozstvi", "_vycisti_rucni_polozku", "_over_rucni_polozky",      # rucni polozky (bot8, 2026-10-06): handler je vola
             "admin_scene_offer_update"]
    fns = {}
    for j in jmena:
        try:
            fns[j] = funkce(j, ast.parse(ZDROJ))
        except AssertionError:
            fns[j] = None            # nova funkce v puvodni verzi neexistuje
    if stara_sanitize:
        fns["_sanitize_offer_options"] = ast.parse(STARA_SANITIZE_OFFER_OPTIONS).body[0]
    if stara_gross:
        fns["_offer_gross_total"] = ast.parse(STARA_OFFER_GROSS_TOTAL).body[0]
        fns["_offer_montaz_net"] = None
    if ref_gross:                                   # puvodni vypocet + JEDINA zmena (Robert 2026-10-06): zvolena montaz sestavy do auta VYLUCUJE dopravu (Toptrans se nepricita)
        fns["_offer_gross_total"] = ast.parse(STARA_OFFER_GROSS_TOTAL.replace(
            'if prefs and prefs.get("shipping_method") == "toptrans":',
            'if prefs and prefs.get("shipping_method") == "toptrans" and not (is_vehicle and prefs.get("montaz_zvolena") and _offer_montaz_pct(offer_options, montaz_pct)):')).body[0]
        fns["_offer_montaz_net"] = None
    if stara_update:
        fns["admin_scene_offer_update"] = ast.parse(STARA_ADMIN_SCENE_OFFER_UPDATE).body[0]
    ns = {"json": json, "datetime": datetime, "VAT_RATE": 21, "re": re, "os": os, "OFFER_IMAGES_DIR": "/nonexistent", "KATALOG_GLB_DIR": "/nonexistent"}
    if extra:
        ns.update(extra)
    # konstanty MANUAL_* (limity ruznych poli) ze zdroje - handler s nimi pracuje pres _over_rucni_polozky
    konst = [n for n in STROM.body if isinstance(n, ast.Assign) and any(isinstance(x, ast.Name) and x.id.startswith("MANUAL_")
                                                                          for t in n.targets for x in ast.walk(t))]
    telo = konst + [f for f in (fns[j] for j in jmena) if f is not None]
    exec(compile(ast.Module(body=telo, type_ignores=[]), "scene_offers", "exec"), ns)
    return ns


NS = slovnik()


chybi = [j for j in ("_sanitize_montaz_pct", "_offer_montaz_pct") if NS.get(j) is None]
if chybi:
    over(f"0 soubor {os.path.basename(SO)} obsahuje funkce {chybi}", False, "chybi - puvodni verze souboru, sazba montaze pro nabidku neni implementovana")
    print(f"\nVYSLEDEK sazba montaze pro nabidku - backend: 0/{len(vysl)} OK (puvodni verze)")
    sys.exit(1)

# ------------------------------------------------------------------------------------------------------------------ A
print("== A _sanitize_montaz_pct")
san = NS["_sanitize_montaz_pct"]
PRIPADY_A = [(None, None), ("", None), (0, 0.0), ("0", 0.0), (15, 15.0), (15.0, 15.0), ("12,5", 12.5), ("12.5", 12.5), (100, 100.0),
             (100.01, None), (-1, None), (-0.01, None), ("abc", None), (True, None), (False, None), (float("nan"), None),
             (float("inf"), None), ([], None), ({}, None), ("  ", None)]
for vstup, cekano in PRIPADY_A:
    try:
        got = san(vstup)
    except Exception as e:                       # noqa: BLE001
        got = f"VYJIMKA {e!r}"
    over(f"A _sanitize_montaz_pct({vstup!r}) == {cekano!r}", got == cekano and type(got) == type(cekano), got)
over("A zaokrouhleni na 2 desetinna mista: 7.556 -> 7.56", san(7.556) == 7.56, san(7.556))

# ------------------------------------------------------------------------------------------------------------------ B
print("== B _sanitize_offer_options")
san_opt = NS["_sanitize_offer_options"]
stara_opt = slovnik(stara_sanitize=True)["_sanitize_offer_options"]
over("B vychozi volby (prazdny vstup) maji montaz_pct None = vychozi sazba z nastaveni", san_opt({})["montaz_pct"] is None, san_opt({}))
over("B montaz_pct 15 se ulozi jako 15.0", san_opt({"montaz_pct": 15})["montaz_pct"] == 15.0, None)
over("B montaz_pct 0 se ulozi jako 0.0 (platna volba 'bez montaze', ne None)", san_opt({"montaz_pct": 0})["montaz_pct"] == 0.0 and san_opt({"montaz_pct": 0})["montaz_pct"] is not None, None)
over("B nesmyslna hodnota (150, 'x', zaporna) -> None (plati vychozi)", all(san_opt({"montaz_pct": v})["montaz_pct"] is None for v in (150, "x", -3)), None)
over("B vstup, ktery neni slovnik, nespadne a da vychozi", san_opt(None)["montaz_pct"] is None and san_opt("x")["montaz_pct"] is None, None)
VSTUPY_B = [{}, None, {"show_qr": False, "delivery_term": " 4-6 tydnu ", "hidden_payment_method": "dobirka", "fixed_deposit_pct": 70,
                      "hide_bom_prices": True, "hidden_delivery_state": "smontovano", "is_vehicle_assembly": True,
                      "manual_assembled_shipping_czk": "1500", "vandr_single_drawing": True},
            {"fixed_deposit_pct": 20, "hidden_payment_method": "x", "manual_assembled_shipping_czk": -5},
            {"montaz_pct": 12.5, "show_qr": False}]
shoda = True
for v in VSTUPY_B:
    nove, stare = dict(san_opt(v)), dict(stara_opt(v))
    nove.pop("montaz_pct")
    nove.pop("discount_pct", None)                       # sleva (bot16, 2026-10-07) je dalsi nove pole, testuje ho test_sleva_backend.py
    if nove != stare:
        shoda = False
        print("   rozdil u vstupu", v, nove, stare)
over("B vsechny OSTATNI klice jsou beze zmeny oproti puvodni verzi (5 sad vstupu)", shoda, None)
over("B JSON-serializovatelne (uklada se do sloupce JSON)", bool(json.dumps(san_opt({"montaz_pct": "12,5"}))), None)

# ------------------------------------------------------------------------------------------------------------------ C
print("== C _offer_montaz_pct")
mp = NS["_offer_montaz_pct"]
PRIPADY_C = [
    ({"montaz_pct": 15}, "20", 15.0, "vlastni sazba prebije vychozi"),
    ({"montaz_pct": 0}, "20", 0.0, "vlastni 0 = bez montaze (NEpadne zpet na vychozi)"),
    ({"montaz_pct": None}, "20", 20.0, "None = vychozi sazba"),
    ({}, "20", 20.0, "bez klice = vychozi (starsi nabidky)"),
    (None, "20", 20.0, "offer_options neni slovnik = vychozi"),
    ({"montaz_pct": 15}, None, 15.0, "vychozi chybi, vlastni plati"),
    ({}, None, 0.0, "vsude nic = 0"),
    ({}, "x", 0.0, "nesmyslna vychozi = 0"),
    ({}, "-5", 0.0, "zaporna vychozi = 0"),
    ({"montaz_pct": 150}, "20", 20.0, "nesmyslna vlastni = vychozi"),
    ({"montaz_pct": "12,5"}, "20", 12.5, "vlastni jako text s carkou"),
    ({}, 35, 35.0, "vychozi jako cislo"),
]
for opt, glob, cekano, popis in PRIPADY_C:
    got = mp(opt, glob)
    over(f"C {popis}: ({opt!r}, {glob!r}) -> {cekano}", got == cekano and isinstance(got, float), got)
over("C zmena vychozi sazby se projevi hned u nabidky BEZ vlastni sazby, u nabidky s vlastni ne",
     mp({}, "20") == 20.0 and mp({}, "25") == 25.0 and mp({"montaz_pct": 15}, "20") == mp({"montaz_pct": 15}, "25") == 15.0, None)

# ------------------------------------------------------------------------------------------------------------------ D
print("== D _offer_gross_total")
gross = NS["_offer_gross_total"]
gross_stara = slovnik(ref_gross=True)["_offer_gross_total"]                # pozn.: "stara" = puvodni vypocet s JEDINOU zmenou (montaz u kazde nabidky, 2026-10-06)


def nabidka(total, options=None, as_str=True):
    o = options if options is not None else None
    return {"total_price": total, "offer_options": (json.dumps(o) if (as_str and o is not None) else o)}


auto = {"is_vehicle_assembly": True}
zvolena = {"montaz_zvolena": 1, "qty": 1}
# vozidlo + zvolena montaz: 10 000 + 15 % = 11 500 bez DPH -> 13 915 s DPH
over("D vlastni sazba 15 % (vychozi 20 %): 10 000 + 1 500 = 11 500 bez DPH -> 13 915,00 s DPH",
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), zvolena, "20") == 13915.0, gross(nabidka(10000, {**auto, "montaz_pct": 15}), zvolena, "20"))
over("D vlastni sazba 0 = bez montaze, i kdyz ji zakaznik zvolil (vychozi 20 %): 10 000 -> 12 100",
     gross(nabidka(10000, {**auto, "montaz_pct": 0}), zvolena, "20") == 12100.0, gross(nabidka(10000, {**auto, "montaz_pct": 0}), zvolena, "20"))
over("D bez vlastni sazby plati ZIVA vychozi: 20 % -> 12 000 bez DPH -> 14 520; po zmene na 25 % -> 15 125",
     gross(nabidka(10000, auto), zvolena, "20") == 14520.0 and gross(nabidka(10000, auto), zvolena, "25") == 15125.0, None)
over("D montaz se pocita z ceny VCETNE poctu kusu (3 ks, 15 %): 3 x 10 000 = 30 000 + 4 500 = 34 500 -> 41 745",
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 3}, "20") == 41745.0, None)
over("D zakaznik montaz NEzvolil -> v cene neni (vlastni sazba nic nemeni): 12 100",
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") == 12100.0, None)
over("D montaz k platbe se u nabidky, ktera NENI sestava do auta (stul, ostatni), NEpridava ani kdyz je v ulozenych volbach zvolena (Robert 2026-10-06: Praha/Slavicin jen u sestav do aut): 12 100",
     gross(nabidka(10000, {"montaz_pct": 15}), zvolena, "20") == 12100.0, gross(nabidka(10000, {"montaz_pct": 15}), zvolena, "20"))
over("D nabidka z Vandr karty (vandr_single_drawing) je sestava do auta i bez rucniho priznaku: montaz se pridava, 10 000 + 15 % = 11 500 -> 13 915",
     gross(nabidka(10000, {"vandr_single_drawing": True, "montaz_pct": 15}), zvolena, "20") == 13915.0, None)
over("D ... a sazba 0 = montaz se nenabizi, ani kdyz je v ulozenych volbach zvolena (nabidky z konfigurace mimo CR): 12 100",
     gross(nabidka(10000, {"montaz_pct": 0}), zvolena, "20") == 12100.0, None)
over("D nezvolena montaz se u bezne nabidky nepricita: 12 100",
     gross(nabidka(10000, {"montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") == 12100.0, None)
over("D zvolena montaz (sestava do auta) VYLUCUJE dopravu: Toptrans se nepricita, (10 000 + 1 500) x 1,21 = 13 915,00",
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13915.0,
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20"))
over("D sestava do auta BEZ zvolene montaze a s Toptransem: doprava se pricita, (10 000 + 1 000) x 1,21 = 13 310,00",
     gross(nabidka(10000, {**auto, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13310.0, None)
over("D montaz s nulovou sazbou (nenabizi se) doprava NEvylucuje: (10 000 + 1 000) x 1,21 = 13 310,00",
     gross(nabidka(10000, {**auto, "montaz_pct": 0}), {"montaz_zvolena": 1, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13310.0, None)
over("D stul (nabidka z konfigurace) s Toptransem: doprava se pricita jako dosud, montaz nic nevylucuje: (10 000 + 1 000) x 1,21 = 13 310,00",
     gross(nabidka(10000, {"source": "configurator", "montaz_pct": 12}), {"montaz_zvolena": 1, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13310.0, None)
over("D offer_options uz jako slovnik (ne text) taky projde (_offer_options_from_row)", gross(nabidka(10000, {**auto, "montaz_pct": 15}, as_str=False), zvolena, "20") is not None, None)

# regrese: BEZ vlastni sazby musi nova funkce davat TOTEZ co puvodni (mrizka vsech kombinaci)
shody, pocet = 0, 0
for total, qty, ship, vozidlo, zvol, glob, ruc in itertools.product(
        (1, 999, 10000, 27353, 123456), (None, 1, 2, 7), (None, "vlastni", "toptrans"), (False, True), (None, 0, 1),
        ("0", "20", "25.5", None, 0, 7), (None, 1500.0)):
    opts = {"is_vehicle_assembly": vozidlo, "manual_assembled_shipping_czk": ruc}
    prefs = None if qty is None else {"qty": qty, "shipping_method": ship, "toptrans_price_czk": 800, "delivery_state": "smontovano",
                                      "montaz_zvolena": zvol}
    a = gross(nabidka(total, opts), prefs, glob)
    b = gross_stara(nabidka(total, opts), prefs, glob)
    pocet += 1
    if a != b and os.environ.get("LADENI"):
        print("   rozdil:", total, qty, ship, vozidlo, zvol, glob, ruc, "nova", a, "stara", b)
    if a == b:
        shody += 1
    elif pocet - shody < 4:
        print("   rozdil:", total, prefs, vozidlo, glob, a, b)
over(f"D bez vlastni sazby shodne s puvodni funkci (jen s vylouceni dopravy pri zvolene montazi sestavy do auta) na cele mrizce ({pocet} kombinaci)", shody == pocet, (shody, pocet))
shody2 = all(gross({"total_price": 5000, "offer_options": None}, p, g) == gross_stara({"total_price": 5000, "offer_options": None}, p, g)
             for p in (None, {}, {"qty": 2}) for g in ("0", "20"))
over("D starsi nabidka bez offer_options (NULL) se pocita jako drive", shody2, None)

# ------------------------------------------------------------------------------------------------------------------ E
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


def spust_update(ns, body, aktualni_options, rev=3):
    stav = {"sql": [], "radek": {"items": json.dumps(body["items"]), "total_price": 1000, "editable_text_popis": "", "editable_text_patka": "",
                                 "offer_options": (json.dumps(aktualni_options) if aktualni_options is not None else None),
                                 "revision_number": rev}}
    ns2 = dict(ns)
    ns2.update({"request": Pozadavek(body), "jsonify": lambda x: x, "current_user": lambda: {"id": 7},
                "get_conn": lambda: FakeConn(stav), "log_audit": lambda *a, **k: None})
    exec(compile(ast.Module(body=[ns2.pop("_FN")], type_ignores=[]), "update", "exec"), ns2)
    odp = ns2["admin_scene_offer_update"](42)
    ulozene = None
    for sql, params in stav["sql"]:
        if sql.startswith("UPDATE scene_offers SET"):
            ulozene = json.loads(params[4])
    return odp, ulozene, stav


def ns_pro_update(**kw):
    n = slovnik(**kw)
    fn = n.pop("admin_scene_offer_update", None)
    # slovnik() uz funkci vykonal v namespace; pro handler potrebujeme jeho AST znovu
    n["_FN"] = (ast.parse(STARA_ADMIN_SCENE_OFFER_UPDATE).body[0] if kw.get("stara_update") else funkce("admin_scene_offer_update", ast.parse(ZDROJ)))
    return n


BODY = {"items": [{"name": "x", "total": 1000}], "total_price": 1000, "editable_text": {"popis": "p", "patka": "f"}, "change_note": "t"}


def body_s(options):
    b = dict(BODY)
    if options is not ...:
        b["offer_options"] = options
    return b


NSU = ns_pro_update()
odp, ul, st = spust_update(NSU, body_s({"show_qr": True, "montaz_pct": 15}), {"montaz_pct": 10})
over("E1 sazba z formulare (15) se ulozi (drive 10)", ul is not None and ul["montaz_pct"] == 15.0 and odp.get("status") == "ok", (ul, odp))
odp, ul, st = spust_update(NSU, body_s({"show_qr": True, "montaz_pct": None}), {"montaz_pct": 10})
over("E2 prazdna sazba z formulare (None) = zpet na vychozi sazbu z nastaveni", ul is not None and ul["montaz_pct"] is None, ul)
odp, ul, st = spust_update(NSU, body_s({"show_qr": True}), {"montaz_pct": 15})
over("E3 formular sazbu NEPOSLAL (starsi admin.html v cache) -> ulozena sazba 15 se ZACHOVA", ul is not None and ul["montaz_pct"] == 15.0, ul)
odp, ul, st = spust_update(NSU, body_s(...), {"montaz_pct": 15})
over("E4 pozadavek bez offer_options vubec -> sazba zustane (ostatni volby se vraci na vychozi jako drive)", ul is not None and ul["montaz_pct"] == 15.0, ul)
odp, ul, st = spust_update(NSU, body_s({"montaz_pct": 0}), {"montaz_pct": 15})
over("E5 sazba 0 z formulare se ulozi jako 0.0 (ne None)", ul is not None and ul["montaz_pct"] == 0.0 and ul["montaz_pct"] is not None, ul)
odp, ul, st = spust_update(NSU, body_s({"montaz_pct": 150}), {"montaz_pct": 15})
over("E6 nesmyslna sazba z formulare (150) se neulozi (None = vychozi)", ul is not None and ul["montaz_pct"] is None, ul)
odp, ul, st = spust_update(NSU, body_s({"show_qr": True}), None)
over("E7 starsi nabidka bez offer_options (NULL) + formular bez sazby -> None, nic nespadne", ul is not None and ul["montaz_pct"] is None, ul)
odp, ul, st = spust_update(NSU, body_s({"show_qr": False, "montaz_pct": 12.5}), {"vandr_single_drawing": True, "montaz_pct": 10})
over("E8 priznak Vandr nabidky zustava (regrese) a sazba se zmeni", ul is not None and ul.get("vandr_single_drawing") is True and ul["montaz_pct"] == 12.5, ul)
over("E9 pred zapisem se do revizi archivuje puvodni stav (INSERT scene_offer_revisions), revize +1",
     any(s.startswith("INSERT INTO scene_offer_revisions") for s, _ in st["sql"]) and odp.get("revision_number") == 4, odp)

# ------------------------------------------------------------------------------------------------------------------ F
print("== F staticke kontrakty")


def zdroj_funkce(jmeno):
    n = next(x for x in ast.parse(ZDROJ).body if isinstance(x, ast.FunctionDef) and x.name == jmeno)
    return ast.get_source_segment(ZDROJ, n)


pub = zdroj_funkce("public_offer_get")
over("F1 verejny payload bere montaz_pct z _offer_montaz_pct(vlastni volby nabidky, vychozi z nastaveni)",
     re.search(r'"montaz_pct":\s*_offer_montaz_pct\(\s*_offer_options_from_row\(offer\)\s*,\s*montaz_pct\s*\)', pub) is not None, None)
over("F2 verejny payload cte vychozi sazbu ZIVE z app_settings (get_setting(cur, \"montaz_pct\"...))", 'get_setting(cur, "montaz_pct", "0")' in pub, None)
over("F3 QR platba predava _offer_gross_total vychozi sazbu z app_settings (a nic jineho nepocita)",
     re.search(r'amount = _offer_gross_total\(offer, prefs_for_total, montaz_pct\)', ZDROJ) is not None
     and re.search(r'montaz_pct = get_setting\(cur, "montaz_pct", "0"\) if offer else "0"', ZDROJ) is not None, None)
over("F4 prijeti nabidky (objednavka) pocita castku pres _offer_gross_total s vychozi sazbou z app_settings",
     ('total_czk=_offer_gross_total(offer, order_prefs_for_total, montaz_pct_for_total)' in ZDROJ or 'total_czk=_offer_gross_total(offer, prefs_celkem, montaz_pct_for_total)' in ZDROJ)       # prefs_celkem = order_prefs + pricky (bot8)
     and 'montaz_pct_for_total = get_setting(cur, "montaz_pct", "0")' in ZDROJ, None)
# jedine misto, kde se montaz nasobi procentem, je _offer_gross_total (a pomocna funkce ji vybira)
nasobeni = re.findall(r"^[^#\n]*montaz_pct\s*/\s*100", ZDROJ, re.M)          # jen radky kodu, ne komentare
over("F5 procento montaze se nasobi jen na jednom miste a to v _offer_montaz_net (volana z _offer_gross_total i z poznamky objednavky)",
     len(nasobeni) == 1 and re.search(r"montaz_pct\s*/\s*100", zdroj_funkce("_offer_montaz_net")) is not None
     and "_offer_montaz_net(" in zdroj_funkce("_offer_gross_total") and "_offer_montaz_net(" in zdroj_funkce("_montaz_poznamka"), len(nasobeni))
over("F6 funkce rozhodujici o sazbe je jedina (_offer_montaz_pct): definice + public_offer_get + _offer_montaz_net + _montaz_poznamka (jen text procenta) + order-prefs (vylouceni dopravy)",
     len(re.findall(r"_offer_montaz_pct\(", ZDROJ)) == 5, len(re.findall(r"_offer_montaz_pct\(", ZDROJ)))
over("F7 OFFER_OPTIONS_DEFAULT (z nej vychazeji Vandr nabidky) vznikne ze sanitizeru, takze nese montaz_pct None",
     "OFFER_OPTIONS_DEFAULT = _sanitize_offer_options({})" in ZDROJ and san_opt({})["montaz_pct"] is None, None)

# ------------------------------------------------------------------------------------------------------------------ G
print("== G mutace (puvodni funkce MUSI selhat)")
stara_ns = slovnik(stara_sanitize=True, stara_gross=True)
mut_ok = 0
mut_dotazy = [
    ("G1 puvodni _sanitize_offer_options nezna montaz_pct (klic chybi -> volba by se pri ulozeni ztratila)",
     "montaz_pct" not in stara_ns["_sanitize_offer_options"]({"montaz_pct": 15})),
    ("G2 puvodni _offer_gross_total ignoruje vlastni sazbu (15 % misto 20 % -> stejna cena)",
     stara_ns["_offer_gross_total"](nabidka(10000, {**auto, "montaz_pct": 15}), zvolena, "20")
     == stara_ns["_offer_gross_total"](nabidka(10000, auto), zvolena, "20")),
]
for popis, zachyceno in mut_dotazy:
    over(popis + " -> mutace ZACHYCENA", zachyceno, None)
# puvodni update handler: sazbu z formulare by zahodil (sanitizer ji nezna) a pri chybejicim klici nezachova
ns_stara_upd = ns_pro_update(stara_sanitize=True, stara_update=True)
odp, ul, st = spust_update(ns_stara_upd, body_s({"show_qr": True, "montaz_pct": 15}), {"montaz_pct": 10})
over("G3 puvodni update handler: sazba z formulare se NEulozi (v ulozenych volbach montaz_pct neni) -> mutace ZACHYCENA", ul is not None and "montaz_pct" not in ul, ul)
ns_nova_san_stary_upd = ns_pro_update(stara_update=True)
odp, ul, st = spust_update(ns_nova_san_stary_upd, body_s({"show_qr": True}), {"montaz_pct": 15})
over("G4 update handler BEZ zachovani chybejiciho klice: starsi formular by sazbu smazal (None misto 15) -> mutace ZACHYCENA", ul is not None and ul["montaz_pct"] is None, ul)

ok = sum(vysl)
print(f"\nVYSLEDEK sazba montaze pro nabidku - backend: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
