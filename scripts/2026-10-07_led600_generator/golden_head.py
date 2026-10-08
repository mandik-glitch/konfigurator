#!/usr/bin/env python3
"""Zlaty otisk stolu PRED zavedenim delky LED (bot8, 2026-10-07): pro mrizku konfiguraci (_spolecne.mrizka) ulozi hash a otisk dilu do golden_head.json. test_led_delka.py pak overi, ze s vychozi
delkou LED (1200) je VSE beze zmeny. Pouziti: api/venv/bin/python3 scripts/2026-10-07_led600_generator/golden_head.py  (nad API VE STAVU PRED zmenou; STUL_API_OVERRIDE = adresar api)"""
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import _spolecne as C  # noqa: E402

if __name__ == "__main__":
    S, G = C.nacti_generator()
    g = C.vypocti(S, G, C.mrizka())
    json.dump(g, open(C.GOLDEN, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print("zapsano", len(g), "konfiguraci do", C.GOLDEN)
