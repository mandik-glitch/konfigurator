#!/usr/bin/env python3
"""Mutacni kontrola testu 'spodni police BEZ DESKY' (bot8, 2026-10-07): test_police_bez_desky.py (jadro) a test_police_bez_desky_shop.py (verejne API) musi chytit kazdou zamerne vnesenou
chybu v api/stul_konfigurator.py, stul_glb.py, stul_sse.py, stul_koty.py, stul_vyrobni_list.py, stul_shop.py a stul_ovladani_verejne.py. Mutace se NEDELAJI v zivem stromu: pro kazdou se postavi
docasny strom (symlinky na zive polozky repa, api = symlinky na ZDROJ, jen mutovany soubor je kopie; KATALOG_DIR se odvozuje z umisteni modulu -> tmp/webapp = symlink na zive webapp) a test se
pusti nad nim pres STUL_API_OVERRIDE. Mutace je "chycena", kdyz nektery z testu skonci nenulovym kodem (jadro v rychlem rezimu POLICE_TEST_KROK=24, pak shop).

Spusteni (z korene repa, jako root; po aplikaci zaplat na zive soubory, nebo s STUL_API_OVERRIDE=<kandidatni adresar api>):
  api/venv/bin/python3 scripts/2026-10-07_police_bez_desky/mutace.py [-j 3] [m01 s03 ...]
Vystup: radek na mutaci (CHYCENA + ktere kontroly selhaly / NECHYCENA) a souhrn; konci kodem 0 jen kdyz jsou chycene VSECHNY."""
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ZDROJ = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
TEST_CORE = os.path.join(REPO, "scripts", "2026-10-07_police_bez_desky", "test_police_bez_desky.py")
TEST_SHOP = os.path.join(REPO, "scripts", "2026-10-07_police_bez_desky", "test_police_bez_desky_shop.py")
K, SH, GL, KO, SS, OV, VL = "stul_konfigurator.py", "stul_shop.py", "stul_glb.py", "stul_koty.py", "stul_sse.py", "stul_ovladani_verejne.py", "stul_vyrobni_list.py"

# (id, popis, soubor, [(puvodni, nove), ...], [testy v poradi])
MUTACE = [
    ("m01", "vychozi hodnota police_deska je False (police bez desky)", K, [('"police_deska": True,         # Robert 2026-10-07: spodni police MAJI DESKU', '"police_deska": False,        # Robert 2026-10-07: spodni police MAJI DESKU')], ["core"]),
    ("m02", "normalizace nepretypuje na bool (0 zustane 0)", K, [('    out["police_deska"] = bool(out["police_deska"])\n', '    pass\n')], ["core"]),
    ("m03", "bez spodnich polic zustane ucinny parametr False", K, [('    if not n_pol:\n        p["police_deska"] = True', '    if False:\n        p["police_deska"] = True')], ["core"]),
    ("m04", "deska police se nikdy neodebira", K, [('    if not p.get("police_deska", True):\n        a -= {DESKA_POLICE}', '    if not p.get("police_deska", True):\n        pass')], ["core"]),
    ("m05", "deska police se odebira vzdy (i vychozi stul)", K, [('    if not p.get("police_deska", True):\n        a -= {DESKA_POLICE}', '    if True:\n        a -= {DESKA_POLICE}')], ["core"]),
    ("m06", "dotaz staff API police_deska nezna", K, [('"loz", "vzpery", "suplik_vlevo", "led_svetlo", "police_deska"):', '"loz", "vzpery", "suplik_vlevo", "led_svetlo"):')], ["core"]),
    ("m07", "patro ramu police: vyssi police nemaji ram", K, [('    if len(klic) == 3 and klic[0] == "polic" and tuple(klic[2]) in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):\n        return int(klic[1])\n', '')], ["core"]),
    ("m08", "patro ramu police: jen leva bocni pricka", K, [('    if klic in (("t", XRAIL_POL_L), ("t", XRAIL_POL_P)):\n        return 0', '    if klic == ("t", XRAIL_POL_L):\n        return 0')], ["core"]),
    ("m09", "3D ovladani: police bez desky nema cast (patro se nesklada z ramu)", K, [('    if not p.get("police_deska", True) and p["police"] >= 1:', '    if False and p["police"] >= 1:')], ["core"]),
    ("m10", "3D ovladani: nabidka vzdy 'odebrat desku' (nastav False)", K, [('{"police_deska": not p.get("police_deska", True)}))', '{"police_deska": False}))')], ["core"]),
    ("m11", "3D ovladani: cast police nema param police_deska", K, [('"param": ["police", "police_deska"], "aabb": aabb(ids_p)', '"param": ["police"], "aabb": aabb(ids_p)')], ["core"]),
    ("m12", "montaz: texty bez desek se nepouziji", K, [('({**MONTAZNI_KROKY, **MONTAZNI_KROKY_BEZ_DESEK_POLIC} if (p["police"] and not p.get("police_deska", True)) else MONTAZNI_KROKY)', 'MONTAZNI_KROKY')], ["core"]),
    ("m13", "montaz: texty bez desek se pouziji vzdy, kdyz jsou police", K, [('if (p["police"] and not p.get("police_deska", True)) else MONTAZNI_KROKY)', 'if (p["police"]) else MONTAZNI_KROKY)')], ["core"]),
    ("m14", "podpery pod policí vznikaji i bez desky", K, [('    if bocni_profil and p["police"] and ("t", DESKA_POLICE) in clenove:\n        useky =', '    if bocni_profil and p["police"]:\n        useky =')], ["core"]),
    ("m15", "montaz krok 3 bez textu o policich bez desek (jen podpery)", K, [('spodní police jsou BEZ DESEK – tvoří je jen rám z profilů "\n       "(do rámu police se podpěrné profily nevkládají); ', '')], ["core"]),
    ("g01", "hash vzdy nese police_deska", GL, [('    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:', '    if False:')], ["core"]),
    ("g02", "hash police_deska nikdy nenese", GL, [('    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:', '    if True:')], ["core"]),
    ("g03", "hash: bez polic nese police_deska", GL, [('    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:', '    if p["police_deska"] or sys_ == S.SYSTEM_SSE:')], ["core"]),
    ("g04", "hash: v SSE nese police_deska", GL, [('    if p["police_deska"] or not p["police"] or sys_ == S.SYSTEM_SSE:', '    if p["police_deska"] or not p["police"]:')], ["core"]),
    ("e01", "SSE police_deska neignoruje", SS, [('    out["police_deska"] = S.VYCHOZI["police_deska"]', '    pass')], ["core"]),
    ("k01", "koty: police bez desky bez kot", KO, [('    if not police and not p.get("police_deska", True) and p.get("police"):', '    if False:')], ["core"]),
    ("k02", "koty: horni rovina police = spodek ramu", KO, [('"dno": y1, "vrch": y1}', '"dno": y1, "vrch": y0}')], ["core"]),
    ("k03", "koty: jen patro 0", KO, [('            k_ = S._patro_ramu_police(klic(i))\n            if k_ is not None:', '            k_ = S._patro_ramu_police(klic(i))\n            if k_ == 0:')], ["core"]),
    ("v01", "vyrobni list: poznamka o policich i bez desek", VL, [('if (par.get("police") and not par.get("police_deska", True)) else', 'if False else')], ["shop"]),
    ("s01", "shop: slot shelfboard neni mezi prepinaci", SH, [('"braces": "vzpery", "shelfboard": "police_deska"}', '"braces": "vzpery"}')], ["shop", "core"]),
    ("s02", "shop: vychozi vyber nema shelfboard", SH, [('"posts": True, "shelf": 1, "shelfboard": True, "wheels": True,', '"posts": True, "shelf": 1, "wheels": True,')], ["shop"]),
    ("s03", "shop: bez polic se 'bez desky' nezahodi", SH, [('    if p["police"] < 1:\n        p["police_deska"] = True', '    if False:\n        p["police_deska"] = True')], ["shop"]),
    ("s04", "shop: token nikdy nenese klic B", SH, [('    if p.get("police") and not p.get("police_deska", True):\n        out["B"] = 0', '    if False:\n        out["B"] = 0')], ["shop"]),
    ("s05", "shop: token B se pri rozbaleni ignoruje", SH, [('    p["police_deska"] = "B" not in o\n', '    p["police_deska"] = True\n')], ["shop"]),
    ("s06", "shop: shrnuti ukazuje desku vzdy", SH, [('    if sel.get("shelfboard", True) or not sel.get("shelf"):\n        skryt.add("shelfboard")', '    if False:\n        skryt.add("shelfboard")')], ["shop"]),
    ("s07", "shop: shrnuti desku neukazuje nikdy", SH, [('    if sel.get("shelfboard", True) or not sel.get("shelf"):\n        skryt.add("shelfboard")', '    if True:\n        skryt.add("shelfboard")')], ["shop"]),
    ("s08", "shop: odkaz na vyrobni list nese i vychozi police_deska", SH, [(' and not (k == "police_deska" and v)})', '})')], ["shop"]),
    ("s09", "shop: slot shelfboard bez polic neni skryty (options.hidden)", SH, [('        options["shelfboard"]["hidden"] = True', '        options["shelfboard"]["hidden"] = False')], ["shop"]),
    ("s10", "shop: toggle shelfboard bez napovedy", SH, [('{**toggle("shelfboard", "g_frame"), "help": t["help_shelfboard"]},', 'toggle("shelfboard", "g_frame"),')], ["shop"]),
    ("s11", "shop: cesky popisek slotu jiny", SH, [('        "shelfboard": "Desky na spodních policích",', '        "shelfboard": "Desky na policích",')], ["shop"]),
    ("s12", "shop: slovensky popisek slotu jiny", SH, [('    "shelfboard": "Dosky na spodných policiach",', '    "shelfboard": "Dosky na policiach",')], ["shop"]),
    ("o01", "ovladani verejne: parametr police_deska bez slotu", OV, [('"police": "shelf", "police_deska": "shelfboard", ', '"police": "shelf", ')], ["core", "shop"]),
    ("o02", "ovladani verejne: anglicky text 'vratit desku' jiny", OV, [('("Vrátit desku police", "Put the shelf board back", "Vrátiť dosku police")', '("Vrátit desku police", "Put the shelf board back!", "Vrátiť dosku police")')], ["core", "shop"]),
    ("o03", "ovladani verejne: chybi preklad 'Odebrat desky vsech polic'", OV, [('("Odebrat desky všech polic", "Remove the boards of all shelves", "Odstrániť dosky všetkých políc"), ', '')], ["core", "shop"]),
]


# mutace ZDUVODNENE EKVIVALENTNI: mutovany kod je obrana do hloubky, jeho vliv uz zajistuje jina cast - nechycena je v poradku (vypise se duvod, do 'nechyceno' se nepocita)
EKVIVALENTNI = {"g04": "hash: podminka 'sys_ == SSE' je redundantni obrana - SSE ma police_deska uz po normalizaci (stul_sse.over_parametry) vzdy True, prvni cast podminky ho odstrani tak jako tak; "
                       "normalizaci hlida mutace e01 a kontrola A7"}


def postav(tmp, soubor, obsah):
    """tmp = koren (symlinky na zive polozky repa), tmp/api = symlinky na ZDROJ, jen `soubor` je kopie s upravenym obsahem."""
    os.makedirs(os.path.join(tmp, "api"))
    for jm in os.listdir(REPO):
        if jm not in ("api", ".git"):
            os.symlink(os.path.join(REPO, jm), os.path.join(tmp, jm))
    for jm in os.listdir(ZDROJ):
        if jm in ("__pycache__",) or jm.startswith("tmp_"):
            continue
        cil = os.path.join(tmp, "api", jm)
        if jm == soubor:
            with open(cil, "w", encoding="utf-8") as f:
                f.write(obsah)
        else:
            os.symlink(os.path.realpath(os.path.join(ZDROJ, jm)) if os.path.islink(os.path.join(ZDROJ, jm)) else os.path.join(ZDROJ, jm), cil)


def spust(tmp, druh):
    env = dict(os.environ, STUL_API_OVERRIDE=os.path.join(tmp, "api"), POLICE_TEST_KROK="24", POLICE_TEST_NAHODNYCH="15", PYTHONDONTWRITEBYTECODE="1")
    if druh == "core":
        cmd = [PY, TEST_CORE]
    else:
        cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=" + os.path.join(REPO, "api", ".env"), "--setenv=HOME=/root", "--setenv=PYTHONDONTWRITEBYTECODE=1", "--setenv=STUL_API_OVERRIDE=" + env["STUL_API_OVERRIDE"],
               "--working-directory=" + REPO, PY, TEST_SHOP]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1500, env=env, cwd=REPO)
    except subprocess.TimeoutExpired:
        return 124, ["TIMEOUT"]
    vystup = (p.stdout or "") + (p.stderr or "")
    selhalo = re.findall(r"^\s*CHYBA: (.{0,95})", vystup, re.M)[:3] + re.findall(r"^Traceback.*\n(?:.*\n){0,12}?(\w*(?:Error|Chyba|Preklad)[^\n]{0,70})", vystup, re.M)[:1]
    return p.returncode, selhalo


def zpracuj(m):
    mid, popis, soubor, nahrady, testy = m
    with open(os.path.join(ZDROJ, soubor), encoding="utf-8") as f:
        kod = f.read()
    for stary, novy in nahrady:
        if kod.count(stary) != 1:
            return mid, popis, None, ["CHYBA MUTACE: vzor se v %s nenasel prave jednou (%d x): %r" % (soubor, kod.count(stary), stary[:80])]
        kod = kod.replace(stary, novy)
    tmp = tempfile.mkdtemp(prefix="police_mut_")
    try:
        postav(os.path.join(tmp, "k"), soubor, kod)
        rc, selhalo = 0, []
        for druh in testy:
            rc, selhalo = spust(os.path.join(tmp, "k"), druh)
            if rc != 0:
                selhalo = ["[%s]" % druh] + selhalo
                break
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return mid, popis, rc, selhalo


def main():
    argv = sys.argv[1:]
    paralelne = 3
    if "-j" in argv:
        i = argv.index("-j")
        paralelne = int(argv[i + 1])
        del argv[i:i + 2]
    vybrane = set(argv)
    seznam = [m for m in MUTACE if not vybrane or m[0] in vybrane]
    # ZAKLADNI BEH bez mutace: musi PROJIT (jinak by kazda mutace byla "chycena" jen proto, ze test v rychlem rezimu selhava sam)
    if os.environ.get("MUT_BEZ_M00") != "1":                              # MUT_BEZ_M00=1: preskocit zakladni beh (rychle prekontrolovani nekolika mutaci)
        mid0, popis0, rc0, sel0 = zpracuj(("m00", "bez mutace (zakladni beh)", K, [], ["core", "shop"]))
        if rc0 != 0:
            print("m00 ZAKLADNI BEH SELHAL (test selhava i bez mutace) -> %s" % (" | ".join(sel0) or "rc=%s" % rc0))
            return 2
        print("m00 zakladni beh bez mutace PROSEL (jadro v rychlem rezimu i shop)")
    chycene, nechycene, ekviv = [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=paralelne) as ex:
        for mid, popis, rc, selhalo in ex.map(zpracuj, seznam):
            if rc is None:
                print("%s %s" % (mid, selhalo[0]))
                nechycene.append(mid)
            elif rc != 0:
                chycene.append(mid)
                print("%s CHYCENA   %-72s -> %s" % (mid, popis, " | ".join(selhalo) or "rc=%d" % rc))
            elif mid in EKVIVALENTNI:
                ekviv.append(mid)
                print("%s EKVIVALENTNI %-69s (%s)" % (mid, popis, EKVIVALENTNI[mid]))
            else:
                nechycene.append(mid)
                print("%s NECHYCENA %-72s (testy prosly i s chybou!)" % (mid, popis))
            sys.stdout.flush()
    print("\nSOUHRN: chyceno %d, zduvodnene ekvivalentni %d%s, nechyceno %d%s" % (len(chycene), len(ekviv), (" (" + ", ".join(ekviv) + ")") if ekviv else "", len(nechycene), (" (" + ", ".join(nechycene) + ")") if nechycene else ""))
    return 0 if not nechycene else 1


if __name__ == "__main__":
    sys.exit(main())
