#!/usr/bin/env python3
"""Zaplata EXISTUJICIHO testu scripts/2026-10-02_stul_testy/test_stul_shop.py: mnozina `select` slotu ve schematu obsahuje i nove selecty police (upshelftype, upshelfboard).
Kotva je REGEX na mnozinovy literal v radku 'typy slotu' (nezavisla na tom, co do mnoziny pridaly jine vetve: shelfboard, ...); idempotentni.   patch_testy.py <vstup.py> <vystup.py>"""
import re
import sys

s = open(sys.argv[1], encoding="utf-8").read()
if '"upshelftype"' not in s:
    m = list(re.finditer(r'(\{s\["id"\] for s in sc\["slots"\] if s\["type"\] == "select"\} == \{)([^}]*)(\})', s))
    assert len(m) == 1, f"kotva 'typy slotu': {len(m)} vyskytu (ocekavan 1)"
    s = s[:m[0].end(2)] + ', "upshelftype", "upshelfboard"' + s[m[0].end(2):]
    s = s.replace("(delka panelu, 2026-10-07)\")", "(delka panelu, 2026-10-07) + upshelftype, upshelfboard (horni police)\")", 1)
open(sys.argv[2], "w", encoding="utf-8").write(s)
