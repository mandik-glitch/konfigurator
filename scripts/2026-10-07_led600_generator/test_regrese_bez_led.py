#!/usr/bin/env python3
"""REGRESE proti revizi v gitu s ODFILTROVANYM prirustkem LED 600 (bot8, 2026-10-07): spusti scripts/2026-10-07_system45/test_s45_regrese.py (porovnani `sestav_stul()`, `odpoved()`, `ovladani_3d()`, vyrobni vypis,
ceny... noveho kodu s revizi v gitu, vychozi HEAD) tak, ze se pri POROVNANI vynechaji JEN prirustky LED 600: klic `led_info`, parametr `led_delka` a polozky 3D menu svitidla ("Zvolit LED N mm", parametr
led_delka v casti led). Vsechno ostatni musi byt bit po bitu stejne => dukaz, ze volba delky svitidla nic jineho nezmenila. (Samotny test_s45_regrese.py tyto prirustky hlasi jako rozdil: porovnava
s revizi PRED zmenou; po commitu zmeny, kdy je HEAD uz obsahuje, projde.)
  api/venv/bin/python -B scripts/2026-10-07_led600_generator/test_regrese_bez_led.py [git-revize]        (novy kod z api/ vedle tohoto skriptu: zivy nebo kandidatni koren)"""
import os
import sys

ORIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "2026-10-07_system45", "test_s45_regrese.py")
src = open(ORIG, encoding="utf-8").read()
a = "import stul_konfigurator as NOVY  # noqa: E402\n"
assert src.count(a) == 1, "kotva importu v test_s45_regrese.py: %d" % src.count(a)
src = src.replace(a, a + '''
_orig_odp = NOVY.odpoved
NOVY.odpoved = lambda v: {k: x for k, x in _orig_odp(v).items() if k != "led_info"}          # klic odpovedi pribyl (led_info); vnitrky generatoru se nemeni
''')
k = '''def kanon(o):
    return json.dumps(o, sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
'''
assert src.count(k) == 1, "kotva kanon v test_s45_regrese.py: %d" % src.count(k)
src = src.replace(k, '''def _bez_led(o):
    """Vynecha prirustek LED 600: klice led_info / led_delka kdekoli, polozky 3D menu svitidla 'Zvolit LED N mm' a parametr led_delka v casti led."""
    if isinstance(o, dict):
        out = {kk: _bez_led(v) for kk, v in o.items() if kk not in ("led_info", "led_delka")}
        if out.get("id") == "led" and isinstance(out.get("menu"), list):
            out["menu"] = [m for m in out["menu"] if not str(m.get("text", "")).startswith("Zvolit LED")]
        if out.get("id") == "led" and isinstance(out.get("param"), list):
            out["param"] = [x for x in out["param"] if x != "led_delka"]
        return out
    if isinstance(o, (list, tuple)):
        return [_bez_led(x) for x in o]
    return o


def kanon(o):
    return json.dumps(_bez_led(o), sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
''')
g = {"__name__": "__main__", "__file__": os.path.abspath(__file__)}
exec(compile(src, ORIG, "exec"), g)
