#!/usr/bin/env python3
"""Zaplata api/stul_ovladani_verejne.py: verejne id a preklady pro RUCNI svitidla LED (pocet `ledcount`, poloha `ledpos1..4`, casti `ledlamp1..4`) - bot8, 2026-10-08.
Pouziti: patch_ovladani_verejne.py <vstup> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''for _n in range(1, S.MAX_VYREZU + 1):
    PARAM_NA_SLOT.update(''', '''PARAM_NA_SLOT.update({"led_pocet": "ledcount", **{f"led_z{_k}": f"ledpos{_k}" for _k in range(1, S.LED_MAX + 1)}})          # svitidla LED RUCNE: pocet a poloha kazdeho (Robert 2026-10-08)
for _n in range(1, S.MAX_VYREZU + 1):
    PARAM_NA_SLOT.update(''', "PARAM_NA_SLOT")
s = nahrad(s, '''"vzpery": "braces", "ram": "frame", "hpolice": "upshelf"}''', '''"vzpery": "braces", "ram": "frame", "hpolice": "upshelf",
            **{f"led_{_k}": f"ledlamp{_k}" for _k in range(1, S.LED_MAX + 1)}}              # jednotliva svitidla LED (cast "led" = cele osvetleni)''', "ID_CASTI")
s = nahrad(s, '''"elzlab_z": "socketside", **{f"police_h{_k}": f"sh{_k}" for _k in range(1, S.MAX_POLIC + 1)}}''',
           '''"elzlab_z": "socketside", **{f"police_h{_k}": f"sh{_k}" for _k in range(1, S.MAX_POLIC + 1)},
           **{f"led_z{_k}": f"ledpos{_k}" for _k in range(1, S.LED_MAX + 1)}}''', "ID_TAHU")
s = nahrad(s, '''] + S._hpol().PREKLADY''', '''    # svitidla LED RUCNE (Robert 2026-10-08): pridat / odebrat svitidlo, posun kazdeho podel profilu
    ("Přidat svítidlo LED", "Add an LED light", "Pridať svietidlo LED"),
    ("Další svítidlo LED se sem nevejde (jejich délky dohromady by přesáhly šířku stolu).", "Another LED light does not fit here (their lengths together would exceed the table width).",
     "Ďalšie svietidlo LED sa sem nezmestí (ich dĺžky dokopy by presiahli šírku stola)."),
    ("Odebrat toto svítidlo", "Remove this light", "Odstrániť toto svietidlo"),
    ("Vrátit svítidlo na výchozí místo", "Move the light back to its default place", "Vrátiť svietidlo na pôvodné miesto"),
    ("Svítidlo LED", "LED light", "Svietidlo LED"), ("Posun svítidla LED", "LED light position", "Posun svietidla LED"),
    *[(f"Svítidlo LED {_k}", f"LED light {_k}", f"Svietidlo LED {_k}") for _k in range(1, S.LED_MAX + 1)],
    *[(f"Posun svítidla LED {_k}", f"LED light {_k} position", f"Posun svietidla LED {_k}") for _k in range(1, S.LED_MAX + 1)],
    ("od levého okraje stolu", "from the left edge of the table", "od ľavého okraja stola"), ("od pravého okraje stolu", "from the right edge of the table", "od pravého okraja stola"),
    ("od levého svítidla", "from the left light", "od ľavého svietidla"), ("od pravého svítidla", "from the right light", "od pravého svietidla"),
] + S._hpol().PREKLADY''', "preklady")
open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
