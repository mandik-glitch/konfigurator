#!/usr/bin/env python3
"""Zaplata api/stul_ovladani_verejne.py: delka svitidla LED (Robert 2026-10-07: "LED 600 doplnit do generatoru") ve verejnem popisu ovladani ve 3D: parametr `led_delka` <-> slot `ledlen`
(verejne id volby je TEXT "600" | "1200"), prelozene polozky menu "Zvolit LED N mm" a jejich duvod (cs / en / sk; dalsi jazyky: zaloha z anglictiny).
Kotvene nahrady (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_ovladani_verejne.py <vstup stul_ovladani_verejne.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''"panely_delka": "panellen", ''', '''"panely_delka": "panellen", "led_delka": "ledlen", ''', "PARAM_NA_SLOT")
s = nahrad(s, '''        if k == "panely_delka":
''', '''        if k == "led_delka":
            out[slot] = str(int(round(float(v))))                                 # verejne id volby delky LED je text ("600"), stejne jako ve schematu
        if k == "panely_delka":
''', "nastav_na_sloty")
s = nahrad(s, '''    *[(f"Zvolit panel {_d} mm", f"Use the {_d} mm panel", f"Zvoliť panel {_d} mm") for _d in S.PANEL_DELKY],
''', '''    # delka svitidla LED (Robert 2026-10-07): polozky menu svitidla
    *[(f"Zvolit LED {_d} mm", f"Use the {_d} mm LED light", f"Zvoliť LED {_d} mm") for _d in S.LED_DELKY],
    ("Tahle délka LED se sem nevejde (širší stůl).", "This LED length does not fit here (a wider table).", "Táto dĺžka LED sa sem nezmestí (širší stôl)."),
    *[(f"Zvolit panel {_d} mm", f"Use the {_d} mm panel", f"Zvoliť panel {_d} mm") for _d in S.PANEL_DELKY],
''', "PREKLADY")
open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
