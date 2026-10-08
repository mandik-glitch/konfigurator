#!/usr/bin/env python3
"""Zaplata api/stul_glb.py: delka LED svitidla (Robert 2026-10-07: "LED 600 doplnit do generatoru") - material dilu LED 600 (stejny jako 4929) a kanonicky hash: klic `led_delka` se do hashe
promitne JEN kdyz je svitidlo na stole a delka neni vychozi 1200 (hashe vsech stavajicich konfiguraci zustavaji). Kotvene nahrady (assert count == 1) proti ZIVEMU souboru.
Pouziti: patch_glb.py <vstup stul_glb.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''POREDI_MATERIALU = [''', '''MATERIAL_DILU.update({pid_: "led" for pid_ in S.LED_PARTY})                   # svitidla LED vsech delek (karty #4929 LED1200, #5359 LED600): material "led" jako 4929
POREDI_MATERIALU = [''', "material")

s = nahrad(s, '''        p.pop("led_svetlo", None)
''', '''        p.pop("led_svetlo", None)
    if not (p["led"] and p["stojky"] and p.get("led_svetlo", True)) or int(round(p["led_delka"])) == S.LED_DELKA_VYCHOZI:          # delka svitidla LED (Robert 2026-10-07): vychozi 1200 / bez svitidla se do hashe nepocita (hashe stolu s LED 1200 zustavaji)
        p.pop("led_delka", None)
''', "hash")

open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
