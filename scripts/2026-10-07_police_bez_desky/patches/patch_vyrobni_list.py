#!/usr/bin/env python3
"""Zaplata api/stul_vyrobni_list.py: poznamka u desek v vyrobnim listu nezminuje police, kdyz jsou spodni police BEZ DESKY (jen ram). Kotvena nahrada.
Pouziti: patch_vyrobni_list.py <vstup stul_vyrobni_list.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''             + (' Pracovní deska a police jsou u střední nohy / vestavěného rámu <b>dělené na dvě desky</b> (levá a pravá část při pohledu zepředu); každá se vejde do tabule laminodesky. '
                'Pracovní deska a police u střední nohy na sebe navazují bez mezery, spodní police u vestavěného rámu jsou kratší o mezeru pro svislý profil rámu.' if deleny else '') + '</div>')'''
b = '''             + (((' Pracovní deska je u střední nohy / vestavěného rámu <b>dělená na dvě desky</b> (levá a pravá část při pohledu zepředu); každá se vejde do tabule laminodesky. '
                  'Pracovní deska u střední nohy navazuje bez mezery.') if (par.get("police") and not par.get("police_deska", True)) else
                 (' Pracovní deska a police jsou u střední nohy / vestavěného rámu <b>dělené na dvě desky</b> (levá a pravá část při pohledu zepředu); každá se vejde do tabule laminodesky. '
                  'Pracovní deska a police u střední nohy na sebe navazují bez mezery, spodní police u vestavěného rámu jsou kratší o mezeru pro svislý profil rámu.')) if deleny else '') + '</div>')'''
assert s.count(a) == 1, "kotva: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
