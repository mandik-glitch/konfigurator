#!/usr/bin/env python3
"""Zaplata api/stul_sse.py: SSE stul (system 41) nema LED - `led_delka` je mezi parametry, ktere SSE nepouziva (vzdy vychozi hodnota, jedna kanonicka podoba = jeden hash).
Kotvena nahrada (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_sse.py <vstup stul_sse.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''"panely_z", "panely_delka", "elzlab_y"'''
assert s.count(a) == 1, "kotva IGNOROVANE: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, '''"panely_z", "panely_delka", "led_delka", "elzlab_y"'''))
print("OK ->", dst)
