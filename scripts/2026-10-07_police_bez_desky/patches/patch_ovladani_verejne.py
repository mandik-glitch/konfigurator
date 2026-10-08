#!/usr/bin/env python3
"""Zaplata api/stul_ovladani_verejne.py: verejna podoba 3D ovladani zna parametr `police_deska` (slot shelfboard) a texty nove polozky nabidky police (cs / en / sk). Kotvene nahrady.
Pouziti: patch_ovladani_verejne.py <vstup stul_ovladani_verejne.py> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''"drzak_pet": "pet", "police": "shelf", "suplik_posun": "boxpos",''', '''"drzak_pet": "pet", "police": "shelf", "police_deska": "shelfboard", "suplik_posun": "boxpos",''', "PARAM_NA_SLOT")
s = nahrad(s, '''    ("Přidat spodní polici", "Add a lower shelf", "Pridať spodnú policu"), ("Odebrat spodní polici", "Remove a lower shelf", "Odstrániť spodnú policu"),
''', '''    ("Přidat spodní polici", "Add a lower shelf", "Pridať spodnú policu"), ("Odebrat spodní polici", "Remove a lower shelf", "Odstrániť spodnú policu"),
    ("Odebrat desku police", "Remove the shelf board", "Odstrániť dosku police"), ("Vrátit desku police", "Put the shelf board back", "Vrátiť dosku police"),
    ("Odebrat desky všech polic", "Remove the boards of all shelves", "Odstrániť dosky všetkých políc"), ("Vrátit desky všech polic", "Put the boards back on all shelves", "Vrátiť dosky na všetky police"),
''', "PREKLADY")
open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
