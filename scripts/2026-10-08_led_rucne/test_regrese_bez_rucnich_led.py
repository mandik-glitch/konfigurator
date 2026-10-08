#!/usr/bin/env python3
"""REGRESE proti revizi v gitu s ODFILTROVANYM prirustkem RUCNICH SVITIDEL LED (bot8, 2026-10-08): spusti scripts/2026-10-07_system45/test_s45_regrese.py (porovnani `sestav_stul()`, `odpoved()`,
`ovladani_3d()`, vyrobni vypis, ceny... noveho kodu s revizi v gitu, vychozi HEAD = stav PRED rucnimi svitidly) tak, ze se pri POROVNANI vynechaji JEN prirustky: parametry `led_pocet` a `led_z1..4`,
nove klice `led_info` (zustane jen `delka` a `typy`), casti `led_<k>` a tahy `led_z<k>` ve 3D ovladani a polozka nabidky "Přidat svítidlo LED". Novy kod se vola s `led_pocet` = nejvic (drivejsi
AUTOMATICKY pocet svitidel podle sirky stolu). Vsechno ostatni musi byt bit po bitu stejne => dukaz, ze rucni svitidla nic jineho nezmenila. (Po commitu zmeny, kdy je HEAD uz obsahuje, projde
primo test_s45_regrese.py; tenhle skript je pro beh PRED nasazenim.)
  api/venv/bin/python -B scripts/2026-10-08_led_rucne/test_regrese_bez_rucnich_led.py [git-revize]        (novy kod z api/ vedle tohoto skriptu: zivy nebo kandidatni koren)"""
import os
import sys

ORIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "2026-10-07_system45", "test_s45_regrese.py")
src = open(ORIG, encoding="utf-8").read()
a = "import stul_konfigurator as NOVY  # noqa: E402\n"
assert src.count(a) == 1, "kotva importu v test_s45_regrese.py: %d" % src.count(a)
src = src.replace(a, a + '''
if hasattr(NOVY, "LED_MAX"):                                  # novy kod: drivejsi automaticky pocet svitidel = nejvic, co se vejde (led_pocet se v generatoru orizne)
    _sestav_novy = NOVY.sestav_stul
    NOVY.sestav_stul = lambda **kw: _sestav_novy(**{"led_pocet": NOVY.LED_MAX, **kw})
''')
k = '''def kanon(o):
    return json.dumps(o, sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
'''
assert src.count(k) == 1, "kotva kanon v test_s45_regrese.py: %d" % src.count(k)
src = src.replace(k, '''import re

NOVE_KLICE = ("led_pocet", "led_z1", "led_z2", "led_z3", "led_z4")


def _bez_rucnich(o):
    """Vynecha prirustek rucnich svitidel: parametry led_pocet / led_z<k>, nove klice led_info, casti led_<k>, tahy led_z<k> a polozku nabidky 'Přidat svítidlo LED'."""
    if isinstance(o, dict):
        out = {kk: _bez_rucnich(v) for kk, v in o.items() if kk not in NOVE_KLICE}
        if isinstance(out.get("led_info"), dict):
            out["led_info"] = {kk: v for kk, v in out["led_info"].items() if kk in ("delka", "typy")}
        if "typy" in out and "delka" in out and "pocet" in out and "telo" in out:                    # samotny slovnik led_info (porovnava se primo `odpoved()["led_info"]`)
            out = {kk: v for kk, v in out.items() if kk in ("delka", "typy")}
        if out.get("id") in ("sirka", "hloubka", "vyska") and "zive" in out:
            out.pop("zive")                                          # NAHLED zive tazeni rozmeru se meri sondou (+-100 / +-30 mm): u sirky 2347-2446 mm uz sonda +100 nepreskoci prah 2447 mm (drive tam pribyvalo druhe svitidlo),
                                                                     # takze se opira o jiny krok; presnost ma hlidat test_stul_zive_vyska.py (model ze serveru), ne tento otisk
        if out.get("id") == "led" and isinstance(out.get("menu"), list):
            out["menu"] = [m for m in out["menu"] if not str(m.get("text", "")).startswith("Přidat svítidlo LED")]
        if isinstance(out.get("casti"), list):
            out["casti"] = [c for c in out["casti"] if not (isinstance(c, dict) and re.fullmatch(r"led_\\d", str(c.get("id", ""))))]
        if isinstance(out.get("tahy"), list):
            out["tahy"] = [t for t in out["tahy"] if not (isinstance(t, dict) and re.fullmatch(r"led_z\\d", str(t.get("id", ""))))]
        return out
    if isinstance(o, (list, tuple)):
        return [_bez_rucnich(x) for x in o]
    return o


def kanon(o):
    return json.dumps(_bez_rucnich(o), sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
''')
g = {"__name__": "__main__", "__file__": os.path.abspath(__file__)}
exec(compile(src, ORIG, "exec"), g)
