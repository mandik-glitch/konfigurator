#!/opt/konfigurator/api/venv/bin/python
"""Montaz (Praha / Slavicin) u online nabidky - backend (bot8 2026-10-06, UPRAVENO bot5 2026-10-06 podle Roberta: JEN sestavy do aut, vylucuje dopravu): `_offer_montaz_net` (jedine misto nasobeni sazbou;
toliko u sestavy do auta - rucni priznak nebo Vandr nabidka), `_offer_gross_total` (zvolena montaz vylucuje Toptrans; stul a ostatni: montaz se k platbe nepricita; sazba 0 = nic), `_montaz_poznamka` (text pro poznamku objednavky a e-mail o prijeti: misto + cena) + staticke kontrakty (accept predava poznamku do create_order_from_scene_offer
a do e-mailu, orders.py ji pripoji do admin_note). AST harness - SKUTECNE funkce ze scene_offers.py, bez DB a bez Flasku, nic nezapisuje.
Spusteni: api/venv/bin/python3 scripts/2026-10-06_nabidka_montaz_polozky_testy/test_montaz_backend.py      Kandidat: SCENE_OFFERS_PY=... ORDERS_PY=..."""
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SO = os.environ.get("SCENE_OFFERS_PY", os.path.join(HERE, "..", "..", "api", "scene_offers.py"))
OR = os.environ.get("ORDERS_PY", os.path.join(HERE, "..", "..", "api", "orders.py"))
ZDROJ = open(SO, encoding="utf-8").read()
ORDERS = open(OR, encoding="utf-8").read()
STROM = ast.parse(ZDROJ)
vysl = []


def over(nazev, podminka, detail=None):
    vysl.append(bool(podminka))
    print(("OK   " if podminka else "FAIL ") + nazev + ("" if podminka else "  -> " + repr(detail)))


def funkce(jmeno):
    n = next(x for x in STROM.body if isinstance(x, ast.FunctionDef) and x.name == jmeno)
    n.decorator_list = []
    return n


class Kurzor:
    def __init__(self, mista):
        self.mista = mista

    def execute(self, sql, params=()):
        self.sql = sql

    def fetchall(self):
        return [{"klic": k, "nazev": n} for k, n in self.mista.items()]


MISTA = {"praha": "Praha", "slavicin": "Slavičín"}
ns = {"json": json, "VAT_RATE": 21, "_montaz_mista_map": lambda cur, jen_aktivni=True: {r["klic"]: r["nazev"] for r in (cur.fetchall() if cur.execute("x") is None else [])}}
jmena = ["_sanitize_montaz_pct", "_sanitize_discount_pct", "_offer_options_from_row", "_offer_montaz_pct", "_je_auto_sestava", "_offer_discount_pct", "_offer_discount_net", "_offer_montaz_net", "_montaz_poznamka", "_offer_gross_total"]       # sleva (2026-10-07): _offer_gross_total a _montaz_poznamka ji pouzivaji
exec(compile(ast.Module(body=[funkce(j) for j in jmena], type_ignores=[]), "scene_offers", "exec"), ns)
net, poz, gross = ns["_offer_montaz_net"], ns["_montaz_poznamka"], ns["_offer_gross_total"]


def nab(total, opts=None):
    return {"total_price": total, "offer_options": json.dumps(opts) if opts is not None else None}


zv = {"montaz_zvolena": 1, "qty": 1, "montaz_misto": "slavicin"}
AU = {"is_vehicle_assembly": True}                       # sestava do auta (rucni priznak)
print("== A _offer_montaz_net (jedine misto nasobeni)")
over("A1 zvolena montaz 15 % z 10 000 = 1 500 (sestava do auta)", net({**AU, "montaz_pct": 15}, 10000.0, zv, "20") == 1500.0, net({**AU, "montaz_pct": 15}, 10000.0, zv, "20"))
over("A2 nezvolena = 0", net({**AU, "montaz_pct": 15}, 10000.0, {"montaz_zvolena": 0}, "20") == 0.0 and net({**AU, "montaz_pct": 15}, 10000.0, None, "20") == 0.0, None)
over("A3 sazba 0 = 0 i kdyz zvolena", net({**AU, "montaz_pct": 0}, 10000.0, zv, "20") == 0.0, None)
over("A4 bez vlastni sazby plati vychozi 20 %: 2 000", net(AU, 10000.0, zv, "20") == 2000.0, None)
over("A5 vychozi 0 a bez vlastni sazby = 0", net(AU, 10000.0, zv, "0") == 0.0, None)
over("A6 stul / ostatni nabidka (NENI sestava do auta): zvolena montaz k platbe se NEnasobi - 0 (Robert 2026-10-06: Praha / Slavicin jen u sestav do aut)",
     net({"montaz_pct": 15}, 10000.0, zv, "20") == 0.0 and net({"source": "configurator", "montaz_pct": 12}, 10000.0, zv, "20") == 0.0 and net({}, 10000.0, zv, "20") == 0.0, None)
over("A7 nabidka z Vandr karty (vandr_single_drawing) je sestava do auta i bez rucniho priznaku: 1 500", net({"vandr_single_drawing": True, "montaz_pct": 15}, 10000.0, zv, "20") == 1500.0, None)

print("== B _offer_gross_total (montaz jen sestava do auta; vylucuje dopravu)")
over("B1 bezna nabidka / stul (neni sestava do auta): montaz se k platbe NEpricita ani kdyz je v ulozenych volbach: 12 100", gross(nab(10000, {"montaz_pct": 15}), zv, "20") == 12100.0, gross(nab(10000, {"montaz_pct": 15}), zv, "20"))
over("B2 sestava do auta: 10 000 + 15 % = 11 500 -> 13 915", gross(nab(10000, {"montaz_pct": 15, "is_vehicle_assembly": True}), zv, "20") == 13915.0, None)
over("B3 sazba 0: 12 100", gross(nab(10000, {**AU, "montaz_pct": 0}), zv, "20") == 12100.0, None)
over("B4 nezvolena: 12 100", gross(nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") == 12100.0, None)
over("B5 3 ks: (30 000 + 4 500) x 1,21 = 41 745", gross(nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 3}, "20") == 41745.0, None)
over("B6 sestava do auta: zvolena montaz VYLUCUJE dopravu - Toptrans 1 000 se nepricita: (10 000 + 1 500) x 1,21 = 13 915", gross(nab(10000, {**AU, "montaz_pct": 15}), {**zv, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13915.0, None)
over("B6b sestava do auta BEZ zvolene montaze: Toptrans se pricita: (10 000 + 1 000) x 1,21 = 13 310", gross(nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13310.0, None)
over("B6c stul / ostatni: zvolena montaz (neplatna) doprava nic nevylucuje - Toptrans se pricita: (10 000 + 1 000) x 1,21 = 13 310", gross(nab(10000, {"montaz_pct": 15}), {**zv, "shipping_method": "toptrans", "toptrans_price_czk": 1000}, "20") == 13310.0, None)
over("B7 rucni cena dopravy 'Smontovano' (jen u nabidky, ktera NENI sestava do auta) zustava: (10 000 + 1 200) x 1,21 (montaz se u ne-auto nepricita)",
     gross(nab(10000, {"montaz_pct": 15, "manual_assembled_shipping_czk": 1200}), {**zv, "shipping_method": "toptrans", "delivery_state": "smontovano", "toptrans_price_czk": 999}, "20") == round(11200 * 1.21, 2), None)

print("== C _montaz_poznamka")
cur = Kurzor(MISTA)
ns["_montaz_mista_map"] = lambda c, jen_aktivni=True: dict(MISTA)
t = poz(cur, nab(10000, {**AU, "montaz_pct": 15}), zv, "20")
over("C1 text: misto Slavicin, +1 500 Kc bez DPH, 15 % z ceny zbozi", t == "Montáž: ano, místo Slavičín, +1 500 Kč bez DPH (15 % z ceny zboží)", t)
t = poz(cur, nab(10000, {**AU, "montaz_pct": 12.5}), {"montaz_zvolena": 1, "qty": 2, "montaz_misto": "praha"}, "20")
over("C2 2 ks a sazba 12,5: 20 000 x 12,5 % = 2 500, text s carkou", t == "Montáž: ano, místo Praha, +2 500 Kč bez DPH (12,5 % z ceny zboží)", t)
over("C3 nezvolena = prazdny text", poz(cur, nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") == "" and poz(cur, nab(10000, {**AU, "montaz_pct": 15}), None, "20") == "", None)
over("C4 sazba 0 = prazdny text", poz(cur, nab(10000, {**AU, "montaz_pct": 0}), zv, "20") == "", None)
t = poz(cur, nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1, "montaz_misto": None}, "20")
over("C5 zvolena bez mista: 'misto neurceno'", "místo neurčeno" in t, t)
t = poz(cur, nab(10000, {**AU, "montaz_pct": 15}), {"montaz_zvolena": 1, "qty": 1, "montaz_misto": "plzen"}, "20")
over("C6 neznamy klic mista (smazane misto) -> 'misto neurceno' (nespadne)", "místo neurčeno" in t, t)
over("C7 cena v poznamce = cena, ktera je v QR / objednavce (montaz_net z _offer_gross_total)",
     abs(gross(nab(10000, {**AU, "montaz_pct": 15}), zv, "20") - gross(nab(10000, {"montaz_pct": 15}), {"montaz_zvolena": 0, "qty": 1}, "20") - 1500 * 1.21) < 0.011, None)

print("== D staticke kontrakty")
over("D1 jedine misto nasobeni sazbou je _offer_montaz_net", len(re.findall(r"^[^#\n]*montaz_pct\s*/\s*100", ZDROJ, re.M)) == 1, None)
over("D2 accept predava poznamku o montazi do create_order_from_scene_offer (extra_note) i do e-mailu",
     ("extra_note=montaz_poznamka or None" in ZDROJ or "extra_note=poznamky_objednavky or None" in ZDROJ)                           # po pricich do multiboxu (bot8) jde i pole pricek do poznamky
     and ('montaz_poznamka = _montaz_poznamka(cur, offer, order_prefs_for_total, montaz_pct_for_total)' in ZDROJ or 'montaz_poznamka = _montaz_poznamka(cur, offer, prefs_celkem, montaz_pct_for_total)' in ZDROJ)
     and ('(f"{montaz_poznamka}\\n" if montaz_poznamka else "")' in ZDROJ or '(f"{poznamky_objednavky}\\n" if poznamky_objednavky else "")' in ZDROJ), None)
over("D3 orders.py: create_order_from_scene_offer ma nepovinne extra_note a pripoji ho k admin_note",
     re.search(r"def create_order_from_scene_offer\(.*extra_note=None(, extra_items=None)?\):", ORDERS, re.S) is not None and "if extra_note:" in ORDERS and 'admin_note += f"\\n{extra_note}"' in ORDERS, None)
over("D5 verejny payload nese priznak montaz_volba JEN u sestav do aut (stul a ostatni ho maji false: montaz je u nich jen informace)", '"montaz_volba": _je_auto_sestava(_offer_options_from_row(offer)),' in ZDROJ, None)
over("D4 konfiguracni snimek v create_order_from_scene_offer zustava (UPDATE shop_order_items ... configuration_json)", "configuration_json=%s, configuration_code=%s" in ORDERS, None)

ok = sum(vysl)
print(f"\nVYSLEDEK montaz u kazde nabidky - backend: {ok}/{len(vysl)} OK")
sys.exit(0 if ok == len(vysl) else 1)
