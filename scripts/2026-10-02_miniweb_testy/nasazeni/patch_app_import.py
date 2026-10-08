#!/usr/bin/env python3
"""Patch api/app.py: importy modulu miniweb (/api/miniweb/*) a miniweb_admin (/api/admin/miniweb/*) na konec souboru za dealer_feed (bot5, 2026-10-02). Opakovatelne (kazdy import zvlast).
Pouziti: patch_app_import.py <cesta k app.py>"""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()
IMPORTY = (
    ("import miniweb  # noqa: F401", "import miniweb  # noqa: F401 - registruje mini-shop API /api/miniweb/* (config, categories, products, legal, inquiry; bot5, Robert pres bot3 2026-10-02, viz miniweb.py + sql/2026-10-02_miniweb*.sql), MUSI byt az po dealers (brand filtr), car_storefronts a documents"),
    ("import miniweb_admin  # noqa: F401", "import miniweb_admin  # noqa: F401 - registruje import a schvalovani textu mini-shopu /api/admin/miniweb/* (jen admin; bot5, Robert pres bot3 2026-10-02, viz miniweb_admin.py + webapp/miniweb-schvaleni.html), MUSI byt az po miniweb"),
)
radky = t.rstrip("\n").split("\n")
pridano = []
for zacatek, radek in IMPORTY:
    if any(r.startswith(zacatek) for r in radky):
        continue
    if not pridano and not any(r.startswith("import miniweb  # noqa") for r in radky):
        assert radky[-1].startswith("import dealer_feed  # noqa: F401"), "posledni radek app.py neni import dealer_feed: " + radky[-1][:60]
    radky.append(radek)
    pridano.append(zacatek.split()[1])
if pridano:
    open(p, "w", encoding="utf-8").write("\n".join(radky) + "\n")
    print("app.py: pridan import " + ", ".join(pridano))
else:
    print("app.py: importy miniweb a miniweb_admin uz jsou")
