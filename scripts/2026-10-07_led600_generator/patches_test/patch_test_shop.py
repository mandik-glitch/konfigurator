#!/usr/bin/env python3
"""Zaplata scripts/2026-10-02_stul_testy/test_stul_shop.py: verejne schema ma od 2026-10-07 dalsi select `ledlen` (delka svitidla LED; Robert: "LED 600 doplnit do generatoru") - seznam select slotu v kontrole
typu slotu o nej vzrostl. Jina zmena v testu neni. Kotvena nahrada (assert count == 1). Pouziti: patch_test_shop.py <vstup test_stul_shop.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''== {"petleg", "petface", "midsupport", "panellen"}, "typy slotu: slider/toggle + selecty petleg, petface, midsupport, panellen (delka panelu, 2026-10-07)")'''
b = '''== {"petleg", "petface", "midsupport", "panellen", "ledlen"}, "typy slotu: slider/toggle + selecty petleg, petface, midsupport, panellen (delka panelu), ledlen (delka svitidla LED, 2026-10-07)")'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
