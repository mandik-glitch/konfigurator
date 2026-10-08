#!/usr/bin/env python3
"""Zaplata api/stul_koty.py: koty spodnich polic BEZ DESKY (vyska horni hrany ramu police od podlahy a mezery mezi policemi) - deska uz neni, patro zastupuje jeho ram. Kotvena nahrada.
Pouziti: patch_koty.py <vstup stul_koty.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''        police[k] = {"x": x0, "x_zad": x1, "z": z1, "dno": y0, "vrch": y1}
    seznam = '''
b = '''        police[k] = {"x": x0, "x_zad": x1, "z": z1, "dno": y0, "vrch": y1}
    if not police and not p.get("police_deska", True) and p.get("police"):          # police BEZ DESKY (Robert 2026-10-07): deska uz neni, kota patri hornimu lici ramu police (horni hrana bocnich pricek)
        patra = {}
        for i in range(len(dily)):
            k_ = S._patro_ramu_police(klic(i))
            if k_ is not None:
                patra.setdefault(k_, []).append(i)
        for k, ids in patra.items():
            x0, y0, z0, x1, y1, z1 = sjednoceni(ids)
            police[k] = {"x": x0, "x_zad": x1, "z": z1, "dno": y1, "vrch": y1}
    seznam = '''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
