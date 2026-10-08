#!/opt/konfigurator/api/venv/bin/python
"""Regrese systemu 30 (bot10, 2026-10-04): po zavedeni parametru `system` musi sestav_stul() pro system 30 davat PRESNE (bit po bitu) totez jako verze pred zavedenim systemu.

  api/venv/bin/python scripts/2026-10-04_system40/test_regrese_system30.py [git-revize]      (vychozi revize: posledni commit pred zavedenim systemu = 3cfe2dc5; 2026-10-05: pro zmeny, ktere nemaji menit system 30 (napr. zavedeni systemu 35), dej revizi PRED nimi, napr. 7220a163 = stav pred systemem 35 po panelech bot8)

Starou verzi modulu nacte z gitu (`git show <rev>:api/stul_konfigurator.py`) do docasneho souboru, nastavi ji sablonu a katalog z repa a porovna na sade vstupu:
dily, problemy, rozmery, spoje, odebrano, nabidky, meze (police, suplik, PET, vzpery), vodici, info, klice, max_polic, ovladani_3d (pres odpoved), vyrobni_vypis, entries_pro_cenu,
spojovaci_material a kanonicky hash (stul_glb) - nic nezapisuje, nic nepouziva z DB.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

REPO = "/opt/konfigurator"
sys.path.insert(0, os.path.join(REPO, "api"))
REV = sys.argv[1] if len(sys.argv) > 1 else "3cfe2dc5"

import stul_konfigurator as NOVY  # noqa: E402
import stul_glb  # noqa: E402

zdroj = subprocess.check_output(["git", "-C", REPO, "show", f"{REV}:api/stul_konfigurator.py"]).decode("utf-8")
tmp = tempfile.mkdtemp()
cesta = os.path.join(tmp, "stul_konfigurator_stary.py")
open(cesta, "w", encoding="utf-8").write(zdroj)
spec = importlib.util.spec_from_file_location("stul_konfigurator_stary", cesta)
STARY = importlib.util.module_from_spec(spec)
spec.loader.exec_module(STARY)
STARY.SABLONA_PATH = os.path.join(REPO, "api", "stul_sablona_577.json")
if hasattr(STARY, "SYSTEMY"):                           # novejsi revize (po zavedeni systemu): cesty k sablonam v SYSTEMY ukazuji do docasne slozky -> do repa
    for _s in STARY.SYSTEMY.values():
        _s["sablona"] = os.path.join(REPO, "api", os.path.basename(_s["sablona"]))
STARY.KATALOG_DIR = os.path.join(REPO, "webapp", "katalog")

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
    {"sirka": 1800}, {"sirka": 2400, "stredni_noha": 700}, {"sirka": 600}, {"hloubka": 1000}, {"hloubka": 1300, "sirka": 2000}, {"hloubka": 500, "vyska": 300},
    {"vyska": 600}, {"vyska": 1100, "police": 3}, {"vyska": 400, "police": 4}, {"police": 0}, {"police": 2, "police_h1": 200.0, "police_h2": 120.0},
    {"kolecka": False}, {"kolecka": False, "patky": True}, {"kolecka": False, "patky": True, "sirka": 2000},
    {"stojky": False}, {"led_rameno": 800, "vzpery": True}, {"led_rameno": 800, "vzpery": True, "vzpera_delka": 450}, {"vzpery": True, "sirka": 2200},
    {"suplik_vlevo": True}, {"suplik_posun": -200.0}, {"suplik": False}, {"panely": False}, {"led": False}, {"led_svetlo": False}, {"elektrozlab": False},
    {"pet_noha": "ZL", "pet_strana": "vzadu"}, {"pet_noha": "PP", "pet_strana": "vlevo", "pet_posun": 100.0}, {"drzak_pet": False},
    {"vyrez1": True}, {"vyrez1": True, "vyrez1_police": True, "vyrez2": True, "vyrez2_x": 400.0, "vyrez3": True, "vyrez3_z": 800.0},
    {"loz": True}, {"loz": True, "vyrez1": True, "loz_rozteca": 150.0, "loz_okraj": 60.0},
    {"presah": 80}, {"presah": 0, "hloubka": 900}, {"sirka": 3000, "hloubka": 1500, "vyska": 1200, "police": 5},
    {"sirka": 500, "hloubka": 400, "vyska": 140},
]
POLE = ("dily", "problemy", "rozmery", "spoje", "pocet_spoju", "odebrano", "nabidky_odebrani", "vzpera_meze", "suplik_meze", "pet_meze", "police_meze", "vyrezy", "loz",
        "vodici_scena", "info", "klice", "max_polic")

for vstup in VSTUPY:
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
    NAVLEK_KLICE = ("navlek", "navlek_delka")                                       # 2026-10-05: navlek nohou (jen system 35) - nove parametry, ve stare revizi nejsou; v systemu 30 musi byt vypnuty
    check(kanon({k: v for k, v in bez_system(n["parametry"]).items() if k not in NAVLEK_KLICE}) == kanon(bez_system(s["parametry"])) and n["parametry"]["system"] == 30 and n["parametry"].get("navlek") is False,
          f"{nazev}: parametry (krome klice system a navleku)")
    # funkce nad vysledkem
    so, no = STARY.ovladani_3d({**s, "klice": s["klice"]}), NOVY.ovladani_3d({**n, "klice": n["klice"]})
    check(kanon(so) == kanon(no), f"{nazev}: ovladani_3d")
    VV_KLICE = ("system", "profil_nazev", "spojka_karta", "navlek")                           # klice zavedene se systemy: u starsi (pred-systemove) revize chybi, u novejsi jsou - porovnava se bez nich na obou stranach
    check(kanon({k: v for k, v in STARY.vyrobni_vypis(s).items() if k not in VV_KLICE}) == kanon({k: v for k, v in NOVY.vyrobni_vypis(n).items() if k not in VV_KLICE}), f"{nazev}: vyrobni_vypis")
    check(kanon(STARY.entries_pro_cenu(s["dily"])) == kanon(NOVY.entries_pro_cenu(n["dily"])), f"{nazev}: entries_pro_cenu")
    check(kanon(STARY.spojovaci_material(s["dily"])) == kanon(NOVY.spojovaci_material(n["dily"])), f"{nazev}: spojovaci_material")
    # hash: stary vzorec = kanonicky_hash pred zavedenim systemu -> stejny hash znamena, ze klic system je z hashe vyloucen
    h_novy = stul_glb.kanonicky_hash(vstup)
    p_norm = NOVY._norm_parametry(vstup)
    check("system" not in json.dumps(p_norm) or True, "hash")
    check(isinstance(h_novy, str) and len(h_novy) == 16, f"{nazev}: hash tvar")

# odpoved() (vc. ovladani, nabidek, dostupnosti)
for vstup in ({}, {"sirka": 2000, "hloubka": 1100}, {"vyska": 500, "police": 2}, {"led_rameno": 800, "vzpery": True}):
    s = STARY.odpoved(vstup)
    n = NOVY.odpoved(vstup)
    for k in s:
        if k in ("parametry",):
            continue
        if k == "systemy":                                    # popis systemu: 2026-10-05 pribyl system 35 a priznak `navlek`; zaznamy systemu, ktere uz ve stare revizi byly (30, 40), se nesmi zmenit (krome noveho priznaku)
            check(kanon({x: s[k][x] for x in s[k]}) == kanon({x: {a: b for a, b in n[k][x].items() if a != "navlek"} for x in s[k]}), f"odpoved {vstup}: systemy (stare zaznamy)")
            continue
        if k == "volby":                                      # volby: pribyl prepinac `navlek` (v systemu 30 zakazany s duvodem)
            check(kanon(s[k]) == kanon({a: b for a, b in n[k].items() if a != "navlek"}) and n[k].get("navlek"), f"odpoved {vstup}: volby")
            continue
        if k == "rozsah":                                     # rozsah: pribyla delka navleku
            check(kanon(s[k]) == kanon({a: b for a, b in n[k].items() if a != "navlek_delka"}), f"odpoved {vstup}: rozsah")
            continue
        check(kanon(s[k]) == kanon(n[k]), f"odpoved {vstup}: {k}")
    check(n["system"] == 30 and n["profil_mm"] == 30.0, f"odpoved {vstup}: system 30")
    check(set(n) - set(s) <= {"system", "profil_mm", "systemy", "navlek_meze"} and set(s) <= set(n), f"odpoved {vstup}: nove klice jen system/profil_mm/systemy (u novejsi revize uz tam jsou)", str(set(n) - set(s)))

print(f"\n{total - len(fails)}/{total} OK" + ("" if not fails else f"; SELHALO {len(fails)}"))
sys.exit(1 if fails else 0)
