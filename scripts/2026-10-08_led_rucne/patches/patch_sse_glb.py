#!/usr/bin/env python3
"""Zaplata api/stul_sse.py (IGNOROVANE) a api/stul_glb.py (kanonicky hash) pro RUCNI svitidla LED (bot8, 2026-10-08).
Pouziti: patch_sse_glb.py <vstup stul_sse.py> <vystup stul_sse.py> <vstup stul_glb.py> <vystup stul_glb.py>"""
import sys

sse_in, sse_out, glb_in, glb_out = sys.argv[1:5]


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = open(sse_in, encoding="utf-8").read()
s = nahrad(s, '''"hpolice_sklon") + tuple(f"police_h{j}" for j in range(1, 11))''', '''"hpolice_sklon") + tuple(f"police_h{j}" for j in range(1, 11)) + ("led_pocet",) + S.LED_PARAMETRY_Z''', "IGNOROVANE")
open(sse_out, "w", encoding="utf-8").write(s)

g = open(glb_in, encoding="utf-8").read()
g = nahrad(g, '''    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)) or int(round(p["led_delka"])) == S.LED_DELKA_VYCHOZI:''', '''    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)):          # RUCNI svitidla LED (Robert 2026-10-08): bez svitidla se pocet ani polohy do hashe nepocitaji
        p.pop("led_pocet", None)
        for k_led in S.LED_PARAMETRY_Z:
            p.pop(k_led, None)
    else:
        n_led = int(p["led_pocet"])
        if n_led == 1 and S.led_max_pocet(p["sirka"], S.led_telo_dilu(S.LED_TYPY[S._led_delka_int(p["led_delka"])])) == 1:          # vejde se jen jedno svitidlo: pocet nic nemeni (hashe uzkych stolu zustavaji jako pred rucnimi svitidly); u sirsiho stolu se klic nese - drive tam byl pocet automaticky
            p.pop("led_pocet", None)
        for j, k_led in enumerate(S.LED_PARAMETRY_Z, 1):                      # poloha svitidla: automaticka (None) / pro neexistujici svitidlo se do hashe nepocita
            if p.get(k_led) is None or j > n_led:
                p.pop(k_led, None)
    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)) or int(round(p["led_delka"])) == S.LED_DELKA_VYCHOZI:''', "hash")
open(glb_out, "w", encoding="utf-8").write(g)
print("OK")
