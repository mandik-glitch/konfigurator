#!/usr/bin/env python3
"""Zaplata api/stul_sse.py: stul SSE (system 41) nema spodni police s ramem (police lezi primo na spojnicich nohou) -> `police_deska` je v SSE ignorovana (vzdy vychozi). Kotvena nahrada.
Kotva je SMYCKA `for k in IGNOROVANE` (ne definice n-tice IGNOROVANE, kterou upravuji i jine zaplaty, napr. horni police mezi stojkami).
Pouziti: patch_sse.py <vstup stul_sse.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''    for k in IGNOROVANE:
        out[k] = S.VYCHOZI[k]
'''
b = a + '''    out["police_deska"] = S.VYCHOZI["police_deska"]                  # SSE nema ram police (deska lezi na spojnicich): volba 'bez desky' se ignoruje (jedna kanonicka podoba = jeden hash)
'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
