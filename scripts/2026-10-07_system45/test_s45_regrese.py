#!/usr/bin/env python3
"""REGRESE systemu 30 / 35 / 40 pri zavedeni systemu 45 (bot10, 2026-10-07) - odvozeno z scripts/2026-10-04_system40/test_regrese_35_40_navlek.py.

Pridani systemu 45 (hluboky stul az 2500 mm: rozsahy hloubky po systemech, stredni rada noh, cena podle systemu parametru) nesmi nijak zmenit stoly systemu 30 / 35 / 40: `sestav_stul()` a
funkce nad jeho vysledkem musi davat PRESNE (bit po bitu) totez jako revize pred zavedenim 45. Starou revizi nacte z gitu (`git show <rev>:api/stul_konfigurator.py`) do docasneho souboru
a porovna na sade vstupu: dily, problemy, rozmery, spoje, odebrano, nabidky, meze, info, klice, max_polic, parametry (krome klice system), ovladani_3d, vyrobni_vypis, entries_pro_cenu,
spojovaci_material, cely `odpoved()` (zaznamy systemu 30 / 35 / 40 v `systemy` se nesmi zmenit; nove smi pribyt jen zaznam systemu 45).

  api/venv/bin/python -B scripts/2026-10-07_system45/test_s45_regrese.py [git-revize]       (vychozi revize HEAD; revize pred zavedenim 45 = 7e3c36bc: pak se porovnavaji systemy 30 / 35 / 40; revize s 45: i system 45)
Novy kod se bere z api/ vedle tohoto skriptu (zivy strom, nebo kandidatni strom pri testu pred nasazenim); nic nezapisuje, nic nepouziva z DB."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

KAND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))          # strom s NOVYM kodem (zivy nebo kandidatni)
GIT = "/opt/konfigurator"                                                                     # repo, ze ktereho se bere STARA revize
sys.path.insert(0, os.path.join(KAND, "api"))
sys.dont_write_bytecode = True
REV = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
SYSTEMY_TEST = (30, 35, 40)

import stul_konfigurator as NOVY  # noqa: E402
import stul_glb  # noqa: E402

zdroj = subprocess.check_output(["git", "-C", GIT, "show", f"{REV}:api/stul_konfigurator.py"]).decode("utf-8")
tmp = tempfile.mkdtemp()
cesta = os.path.join(tmp, "stul_konfigurator_stary.py")
open(cesta, "w", encoding="utf-8").write(zdroj)
spec = importlib.util.spec_from_file_location("stul_konfigurator_stary", cesta)
STARY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(STARY)
STARY.SABLONA_PATH = os.path.join(KAND, "api", "stul_sablona_577.json")
for _s in STARY.SYSTEMY.values():
    _s["sablona"] = os.path.join(KAND, "api", os.path.basename(_s["sablona"]))
STARY.KATALOG_DIR = os.path.join(KAND, "webapp", "katalog")
MA45 = 45 in STARY.SYSTEMY                                  # revize uz system 45 obsahuje (zmena po zavedeni 45, napr. nova pravidla po systemech): porovnava se i system 45
assert 45 in NOVY.SYSTEMY, "novy kod nema system 45"
if MA45:
    SYSTEMY_TEST = (30, 35, 40, 45)

fails, total = [], 0


def check(ok, nazev, detail=""):
    global total
    total += 1
    if not ok:
        fails.append(nazev)
        print("FAIL", nazev, detail)


def kanon(o):
    return json.dumps(o, sort_keys=True, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))


def bez_system(p):
    return {k: v for k, v in p.items() if k != "system"}


VSTUPY = [
    {},
    {"sirka": 1800}, {"sirka": 2400, "stredni_noha": 700}, {"sirka": 600}, {"hloubka": 1000}, {"hloubka": 1300, "sirka": 2000}, {"hloubka": 500, "vyska": 300}, {"hloubka": 1500, "vyska": 450, "police": 2},
    {"vyska": 600}, {"vyska": 1100, "police": 3}, {"vyska": 400, "police": 4}, {"police": 0}, {"police": 2, "police_h1": 200.0, "police_h2": 120.0},
    {"kolecka": False}, {"kolecka": False, "patky": True}, {"kolecka": False, "patky": True, "sirka": 2000},
    {"stojky": False}, {"led_rameno": 800, "vzpery": True}, {"led_rameno": 800, "vzpery": True, "vzpera_delka": 450}, {"vzpery": True, "sirka": 2200},
    {"suplik_vlevo": True}, {"suplik_posun": -200.0}, {"suplik": False}, {"panely": False}, {"led": False}, {"led_svetlo": False}, {"elektrozlab": False},
    {"pet_noha": "ZL", "pet_strana": "vzadu"}, {"pet_noha": "PP", "pet_strana": "vlevo", "pet_posun": 100.0}, {"drzak_pet": False},
    {"vyrez1": True}, {"vyrez1": True, "vyrez1_police": True, "vyrez2": True, "vyrez2_x": 400.0, "vyrez3": True, "vyrez3_z": 800.0},
    {"loz": True}, {"loz": True, "vyrez1": True, "loz_rozteca": 150.0, "loz_okraj": 60.0},
    {"presah": 80}, {"presah": 0, "hloubka": 900}, {"sirka": 3000, "hloubka": 1500, "vyska": 1200, "police": 5},
    {"sirka": 500, "hloubka": 400, "vyska": 140},
    {"sirka": 1800, "hloubka": 1500, "navlek": True, "navlek_delka": 250.0}, {"sirka": 2200, "hloubka": 1400, "panely_pocet": 2, "led": True, "vzpery": True},
    {"hloubka": 2000},                                                                        # mimo rozsah systemu 30 / 35 / 40: stejna chyba jako dosud
    {"hloubka": 1501}, {"hloubka": 2500, "sirka": 1800},
    {"hloubka": 1600, "sirka": 1800, "police": 2}, {"hloubka": 2000, "sirka": 2400, "kolecka": False, "patky": True}, {"hloubka": 2500, "sirka": 3000, "vyska": 450},          # hluboky stul (jen system 45; jinde stejna chyba)
]
POLE = ("dily", "problemy", "rozmery", "spoje", "pocet_spoju", "odebrano", "nabidky_odebrani", "vzpera_meze", "navlek_meze", "suplik_meze", "pet_meze", "police_meze", "vyrezy", "loz",
        "vodici_scena", "info", "klice", "max_polic")

VSTUPY_SYS = [{**v, "system": sy} for sy in SYSTEMY_TEST for v in VSTUPY]
for vstup in VSTUPY_SYS:
    nazev = json.dumps(vstup, sort_keys=True)
    try:
        s = STARY.sestav_stul(**vstup)
    except STARY.StulChyba as e:
        try:
            NOVY.sestav_stul(**vstup)
            check(False, f"{nazev}: stary vyhodil chybu, novy ne", str(e))
        except NOVY.StulChyba as e2:
            check(str(e) == str(e2), f"{nazev}: stejna chyba", f"{e} | {e2}")
        continue
    n = NOVY.sestav_stul(**vstup)
    for pole in POLE:
        check(kanon(s[pole]) == kanon(n[pole]), f"{nazev}: {pole}")
    check(kanon(bez_system(n["parametry"])) == kanon(bez_system(s["parametry"])) and n["parametry"]["system"] == vstup["system"], f"{nazev}: parametry (krome klice system)")
    check(kanon(STARY.ovladani_3d({**s, "klice": s["klice"]})) == kanon(NOVY.ovladani_3d({**n, "klice": n["klice"]})), f"{nazev}: ovladani_3d")
    check(kanon(STARY.vyrobni_vypis(s)) == kanon(NOVY.vyrobni_vypis(n)), f"{nazev}: vyrobni_vypis")
    check(kanon(STARY.entries_pro_cenu(s["dily"])) == kanon(NOVY.entries_pro_cenu(n["dily"])), f"{nazev}: entries_pro_cenu")
    check(kanon(STARY.spojovaci_material(s["dily"])) == kanon(NOVY.spojovaci_material(n["dily"])), f"{nazev}: spojovaci_material")
    check(NOVY.system_z_dilu(n["dily"]) == STARY.system_z_dilu(s["dily"]) and (vstup["system"] == 45 or NOVY.system_z_dilu(n["dily"]) == vstup["system"]), f"{nazev}: system_z_dilu (45 se z dilu pozna jako 40)")
    h = stul_glb.kanonicky_hash(vstup)
    check(isinstance(h, str) and len(h) == 16, f"{nazev}: hash tvar")

# odpoved() (vc. ovladani, nabidek, dostupnosti)
for vstup in [{**v, "system": sy} for sy in SYSTEMY_TEST for v in ({}, {"sirka": 2000, "hloubka": 1100}, {"vyska": 500, "police": 2}, {"led_rameno": 800, "vzpery": True}, {"hloubka": 1500, "sirka": 2600})]:
    s = STARY.odpoved(vstup)
    n = NOVY.odpoved(vstup)
    for k in s:
        if k == "systemy":                                    # nove smi pribyt jen zaznam systemu 45; zaznamy 30 / 35 / 40 (a SSE) se nesmi zmenit
            check(kanon(s[k]) == kanon({x: n[k][x] for x in s[k]}) and set(n[k]) - set(s[k]) == (set() if MA45 else {"45"}), f"odpoved {vstup}: systemy (stare zaznamy beze zmeny{'' if MA45 else ', pribyl jen 45'})", str(set(n[k]) - set(s[k])))
            continue
        check(kanon(s[k]) == kanon(n[k]), f"odpoved {vstup}: {k}")
    check(n["system"] == vstup["system"] and set(n) == set(s), f"odpoved {vstup}: stejne klice a system", str(set(n) ^ set(s)))

print(f"\n{total - len(fails)}/{total} OK" + ("" if not fails else f"; SELHALO {len(fails)}"))
sys.exit(1 if fails else 0)
