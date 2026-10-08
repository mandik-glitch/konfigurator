#!/usr/bin/env python3
"""Zaplata api/stul_razitka.py (bot8, 2026-10-08, WORKFLOW pravidlo 61): jen hlavicka modulu (razitka uz nejsou "jen model v nabidce"); pravidla umisteni a kod beze zmeny.
Pouziti: patch_razitka_doc.py <vstup> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
if "NA VSECH 3D modelech generatoru (bot8" in s:            # uz aplikovano (commit 3b7d5076): vystup = vstup
    open(dst, "w", encoding="utf-8").write(s)
    print("stul_razitka.py: hlavicka uz je aktualni (3b7d5076), nic se nemeni")
    sys.exit(0)


def sub(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


sub('"""Razitka (ochranne 3D logo LOGIMAN.CZ) na profilech STOLU z generatoru - jen pro MODEL V ONLINE NABIDCE (bot8, 2026-10-06).',
    '"""Razitka (ochranne 3D logo LOGIMAN.CZ) na profilech STOLU z generatoru - NA VSECH 3D modelech generatoru (bot8, 2026-10-06; od 2026-10-08 VYCHOZI, WORKFLOW pravidlo 61).')
sub("""Robert (pres bot5 / bot9, 2026-10-06): razitka loga v 3D modelu online nabidky maji byt i u stolu z generatoru; pravidlo z 2026-09-06: razitkovani = stupen 2 = model v nabidce, verejny
generator a kosik zustavaji bez razitek (`stul_glb.model_pro_parametry(..., razitka=False)` je vychozi).""",
    """Robert (pres bot5 / bot9, 2026-10-06): razitka loga v 3D modelu online nabidky maji byt i u stolu z generatoru; do 2026-10-08 platilo pravidlo z 2026-09-06 (razitkovani = stupen 2 = model v nabidce,
verejny generator a kosik bez razitek). WORKFLOW pravidlo 61 (Robert 2026-10-08, doslova: "razitka budou na vsech 3D modelech ve vsech generatorech") ho PREBILO: `stul_glb.model_pro_parametry` ma razitka
VYCHOZI (`RAZITKA_VYCHOZI`; zive 3D, kosik, nabidka, karta), pravidla umisteni nize se nemenila.""")
sub("profily vsech systemu stolu (30 / 35 / 40; drazka podle profilu, zmereno z GLB profilu)", "profily vsech systemu stolu (30 / 35 / 40 / 41 / 45; 41 a 45 maji profil jako 40; drazka podle profilu, zmereno z GLB profilu)")
open(dst, "w", encoding="utf-8").write(s)
print("OK stul_razitka.py: hlavicka")
