#!/usr/bin/env python3
"""Zaplata api/stul_glb.py: hash konfigurace nese `police_deska` JEN kdyz jsou spodni police opravdu bez desky (hashe stolu s deskou zustavaji beze zmeny). Kotvena nahrada (assert count == 1).
Pouziti: patch_glb.py <vstup stul_glb.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''    for j in range(1, 11):                                     # vyska polic: nezadana (None) / pro neexistujici polici se do hashe nepocita (hashe stolu bez teto volby zustavaji)
'''
b = '''    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:           # police BEZ DESKY (Robert 2026-10-07): do hashe jen kdyz opravdu bez desky (hashe stolu s deskou zustavaji); bez polic a v SSE volba nic nedela
        p.pop("police_deska", None)
''' + a
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
