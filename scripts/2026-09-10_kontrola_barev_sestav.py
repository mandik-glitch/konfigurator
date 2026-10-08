#!/usr/bin/env python3
"""Kontrola MATERIÁLŮ/BAREV dílů použitých ve stávajících sestavách.

Robert 2026-09-10: *„záslepky mají být ve scéně černé, úhelníky nejsou ze
stejného materiálu jako profily, ale obyčejné šedé"* → *„původní sestavy tak
zůstaly staré materiály/barvy, tak udělej script který projede i stávající
sestavy"*.

CO JE POTŘEBA VĚDĚT NEŽ SE TENHLE SKRIPT POUŽIJE:

`product_assemblies.data.parts` ani `custom_shapes.data.parts` **barvu
neukládají** — díl v nich nese jen `part_id`, `position`, `quaternion`,
`scale` a `role`. Barva se bere ŽIVĚ z katalogu (`shop_products.color_hex`,
jinak `cfg_dily.color_hex`/`layer`) až při vykreslení. Přebarvení dílu v
katalogu se tedy do všech sestav propíše samo — **stačí obnovit stránku
scény**, v otevřené záložce zůstane stará barva z doby načtení.

Tenhle skript proto nic v sestavách nepřebarvuje (nebylo by co). Dělá to
užitečnější: projde VŠECHNY sestavy, zjistí, které katalogové díly se v nich
skutečně používají a v jaké roli, a nahlásí ty, které by se vykreslily
špatně — tedy díl, jehož barva NENÍ v paletě (spadl by na obecný fallback),
nebo díl v roli, kde se kovový lesk nečeká.

    api/venv/bin/python3 scripts/2026-09-10_kontrola_barev_sestav.py
    api/venv/bin/python3 scripts/2026-09-10_kontrola_barev_sestav.py --vse
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))

import pymysql  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Paleta materiálů scény - musí sedět na partMaterialColor/partMaterialMetalness
# ve webapp/js/scene/catalog-panels.js. Díl, jehož color_hex tu NENÍ, spadne
# ve scéně na obecný fallback "#9aa0a6" a vypadá jako nic konkrétního.
PALETA = {
    "#c9cdd1": ("alu", 0.60),
    "#b7bcc0": ("zinc", 0.45),
    "#242424": ("black", 0.10),
    "#1c1c1e": ("guma", 0.05),
    "#666c73": ("plast_svetly", 0.10),
}
# Role, u kterých se kovový lesk NEČEKÁ (Robert 2026-09-10: "úhelníky nejsou
# lesklé", "záslepky mají být černé"). Práh: cokoli nad 0.35 už vypadá jako kov.
NEKOVOVE_ROLE = ("zaslepka", "uhelnik", "vypln", "eurobox")
PRAH_LESKU = 0.35


def env():
    out = {}
    with open(os.path.join(REPO, "api", ".env"), encoding="utf-8") as fh:
        for radek in fh:
            radek = radek.strip()
            if radek and not radek.startswith("#") and "=" in radek:
                k, v = radek.split("=", 1)
                out[k] = v
    return out


def main():
    p = argparse.ArgumentParser(description="Kontrola barev dílů ve stávajících sestavách.")
    p.add_argument("--vse", action="store_true", help="vypsat i díly, které jsou v pořádku")
    args = p.parse_args()

    e = env()
    conn = pymysql.connect(host=e.get("DB_HOST", "127.0.0.1"), port=int(e.get("DB_PORT", 3306)),
                           user=e["DB_USER"], password=e["DB_PASSWORD"], database=e["DB_NAME"],
                           charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, color_hex FROM shop_products")
            katalog = {"product_%d" % r["id"]: (r["color_hex"], r["name"]) for r in cur.fetchall()}
            cur.execute("SELECT id, name, color_hex, layer FROM cfg_dily")
            for r in cur.fetchall():
                # cfg_dily díl bez vlastní barvy bere barvu podle vrstvy
                vychozi = {"alu": "#c9cdd1"}.get(r["layer"])
                katalog.setdefault(r["id"], (r["color_hex"] or vychozi, r["name"]))

            pouziti = collections.defaultdict(collections.Counter)   # role -> part_id -> ks
            zdroje = collections.defaultdict(set)                    # part_id -> id sestav
            for tab, sloupec in (("product_assemblies", "sestava"), ("custom_shapes", "tvar")):
                cur.execute("SELECT id, data FROM " + tab)
                for r in cur.fetchall():
                    try:
                        dily = json.loads(r["data"]).get("parts") or []
                    except (ValueError, TypeError):
                        continue
                    for d in dily:
                        role = (d.get("role") or "?").split("-")[0]
                        pouziti[role][d["part_id"]] += 1
                        zdroje[d["part_id"]].add("%s %s" % (sloupec, r["id"]))
    finally:
        conn.close()

    nalezy = []
    print("%-14s %-18s %8s  %-9s %-14s %s" % ("ROLE", "PART_ID", "KUSŮ", "BARVA", "MATERIÁL", "NÁZEV"))
    print("-" * 104)
    for role in sorted(pouziti):
        for pid, n in pouziti[role].most_common():
            barva, nazev = katalog.get(pid, (None, "?"))
            klic = (barva or "").lower()
            mat = PALETA.get(klic)
            if pid.startswith("car_body"):
                continue                       # karoserie se nerenderuje, viz PRODUKTOVE_RENDERY.md
            popis = "%s (%.2f)" % mat if mat else "MIMO PALETU"
            spatne = None
            if not mat:
                spatne = "barva %s není v paletě → obecný fallback" % (barva or "žádná")
            elif role.startswith(NEKOVOVE_ROLE) and mat[1] > PRAH_LESKU:
                spatne = "role %s, ale kovovost %.2f (lesklé)" % (role, mat[1])
            if spatne or args.vse:
                print("%-14s %-18s %8d  %-9s %-14s %s" % (role, pid, n, barva or "-", popis, (nazev or "")[:34]))
            if spatne:
                nalezy.append((role, pid, n, spatne, sorted(zdroje[pid])[:3]))

    print()
    if not nalezy:
        print("V POŘÁDKU: každý díl použitý v sestavách má barvu z palety a žádný")
        print("nekovový díl není lesklý.")
        print()
        print("Pozn.: sestavy barvu neukládají, bere se živě z katalogu - když ve")
        print("scéně pořád vidíš starou barvu, je to načtená stránka. Obnov ji.")
        return 0
    print("NÁLEZY: %d" % len(nalezy))
    for role, pid, n, proc, kde in nalezy:
        print("  %-14s %-18s %5d ks  %s" % (role, pid, n, proc))
        print("                 např. %s" % ", ".join(kde))
    return 1


if __name__ == "__main__":
    sys.exit(main())
