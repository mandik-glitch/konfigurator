#!/usr/bin/env python3
"""Zaplata api/stul_osvetleni.py: pocitadlo luxu zna obe delky svitidla LED (Robert 2026-10-07: "LED 600 doplnit do generatoru"): `typ` led_1200 / led_600, jmenovita delka = svitici cara
(1200 / 600 mm, vystredena v telese), `housingLengthMm` = delka tělesa z GLB (1247 / 647 mm). Verejna odpoved SKU ani cisla produktu nenese (klient mapuje `typ` -> katalog: js/stul-luxy.js).
Kotvene nahrady (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_osvetleni.py <vstup stul_osvetleni.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''LED_SVITI_MM = 1200.0              # jmenovita delka = svitici cara (hypoteza); teleso vc. koncovek je S.LED_SIRKA (1247 mm)
''', '''LED_SVITI_MM = 1200.0              # jmenovita delka = svitici cara (hypoteza); teleso vc. koncovek je S.LED_SIRKA (1247 mm)
# delky svitidla (Robert 2026-10-07): dil katalogu -> (neutralni `typ` ve verejne odpovedi, jmenovita delka = svitici cara v mm); LED 600 = karta #5359 (16 W, 1920 lm), GLB = LED 1200 zkracena o 600 mm
TYP_DILU = {S.LED_TYPY[1200]: (TYP_LED, 1200.0), S.LED_TYPY[600]: ("led_600", 600.0)}
''', "typy")
s = nahrad(s, '''    leds = [d for d in dily if d["part_id"] == LED_PART]
''', '''    leds = [d for d in dily if d["part_id"] in TYP_DILU]
''', "leds")
s = nahrad(s, '''        P, _, _ = transformuj(LED_PART, d)
        svitidla.append((P.min(axis=0), P.max(axis=0)))
''', '''        P, _, _ = transformuj(d["part_id"], d)
        svitidla.append((P.min(axis=0), P.max(axis=0), d["part_id"]))
''', "transformuj")
s = nahrad(s, '''    for k, (a, b) in enumerate(svitidla, 1):
        c = (a + b) / 2.0
        lights.append({
            "id": "led-%d" % k, "typ": TYP_LED, "type": "linear",
            "startMm": _r([c[0], a[1], c[2] - LED_SVITI_MM / 2.0]), "endMm": _r([c[0], a[1], c[2] + LED_SVITI_MM / 2.0]),
            "direction": [0, -1, 0], "housingBoundsMm": [_r(a), _r(b)],
            "housingLengthMm": float(S.LED_SIRKA), "nominalLengthMm": LED_SVITI_MM, "geometryStatus": "hypothesis"})
''', '''    for k, (a, b, pid) in enumerate(svitidla, 1):
        c = (a + b) / 2.0
        typ, sviti = TYP_DILU[pid]
        lights.append({
            "id": "led-%d" % k, "typ": typ, "type": "linear",
            "startMm": _r([c[0], a[1], c[2] - sviti / 2.0]), "endMm": _r([c[0], a[1], c[2] + sviti / 2.0]),
            "direction": [0, -1, 0], "housingBoundsMm": [_r(a), _r(b)],
            "housingLengthMm": float(S.led_telo_dilu(pid)), "nominalLengthMm": sviti, "geometryStatus": "hypothesis"})
''', "svetla")
open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
