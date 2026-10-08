#!/usr/bin/env python3
"""Mutacni kontrola testu DELEK PANELU (bot8, 2026-10-07): test_panely_delky.py a test_panely_delky_shop.py musi chytit kazdou zamerne vnesenou chybu v api/stul_konfigurator.py,
stul_shop.py, stul_glb.py, stul_koty.py a stul_sse.py. Mutace se NEDELAJI v zivem stromu: pro kazdou se postavi docasny strom (symlinky na zive soubory, jen mutovany soubor je kopie;
KATALOG_DIR se odvozuje z umisteni modulu -> tmp/webapp = symlink na zive webapp) a test se pusti nad nim pres STUL_API_OVERRIDE. Mutace je "chycena", kdyz test skonci nenulovym kodem.

Spusteni (z korene repa, jako root):  api/venv/bin/python3 scripts/2026-10-07_perfopanel/mutace.py [m01 s03 ...]      (STUL_API_OVERRIDE=<adresar api> = zdroj mutaci misto zivych souboru)
Vystup: radek na mutaci (CHYCENA + ktere kontroly selhaly / NECHYCENA) a souhrn; konci kodem 0 jen kdyz jsou chycene VSECHNY."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ZDROJ = os.environ.get("STUL_API_OVERRIDE") or os.path.join(REPO, "api")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
TEST_CORE = os.path.join(REPO, "scripts", "2026-10-07_perfopanel", "test_panely_delky.py")
TEST_SHOP = os.path.join(REPO, "scripts", "2026-10-07_perfopanel", "test_panely_delky_shop.py")
K, SH, GL, KO, SS, OV = "stul_konfigurator.py", "stul_shop.py", "stul_glb.py", "stul_koty.py", "stul_sse.py", "stul_ovladani_verejne.py"

# (id, popis, soubor, [(puvodni, nove), ...], test)
MUTACE = [
    ("m01", "zadne snizeni delky (zvolena se nevejde -> rovnou nejkratsi)", K, [("for d in sorted((x for x in PANEL_DELKY if x <= pozad), reverse=True):", "for d in [pozad]:")], "core"),
    ("m02", "dil panelu zustane vzdy 4931 (nova delka nema svuj dil)", K, [('                clenove[klic_pan]["part_id"] = pg["part"]                    # dil katalogu zvolene delky (stejne otoceni jako panel sablony)\n', "")], "core"),
    ("m03", "elektrozlab drzi odstup od STREDU misto od leve hrany panelu (jina delka = jina poloha)", K, [('"zlab_od_z": float(ls[2] - lo0[2])}', '"zlab_od_z": float(ls[2] - lo0[2]) + (s1 - 1190.0) / 2.0}')], "core"),
    ("m04", "panel_limity ignoruje delku", K, [("pg, P = _panel_geometrie(delka), _P()", "pg, P = _panel_geometrie(), _P()")], "core"),
    ("m05", "neplatna necela delka se prijme (1190.5)", K, [("or abs(pd_ - round(pd_)) > 1e-6 or int(round(pd_)) not in PANEL_TYPY", "or int(round(pd_)) not in PANEL_TYPY")], "core"),
    ("m06", "typy: kazda delka se 'vejde'", K, [('"vejde": v_s and v_v,', '"vejde": True,')], "core"),
    ("m07", "hash nese i vychozi delku 1190", GL, [(' or int(round(p["panely_delka"])) == S.PANEL_DELKA_VYCHOZI:          # delka panelu', ':          # delka panelu')], "core"),
    ("m08", "hash delku panelu nikdy nepocita", GL, [('    if not (p["panely"] and p["stojky"]) or int(round(p["panely_delka"])) == S.PANEL_DELKA_VYCHOZI:', '    if True:')], "core"),
    ("m09", "3D menu panelu bez voleb delky", K, [('    for t_ in (pi_.get("typy") or []):', '    for t_ in []:')], "core"),
    ("m10", "SSE nechava delku panelu", SS, [('"panely_posun", "panely_z", "panely_delka", "elzlab_y"', '"panely_posun", "panely_z", "elzlab_y"')], "core"),
    ("m11", "kóty mezer panelu jen u dilu 4931", KO, [('        if d["part_id"] in S.PANEL_PARTY:\n', '        if d["part_id"] == S.PANEL_PART:\n')], "core"),
    ("m12", "nove panely bez materialu ocel", GL, [('MATERIAL_DILU.update({pid_: "ocel" for pid_ in S.PANEL_PARTY})', 'MATERIAL_DILU.update({})')], "core"),
    ("m13", "spojka se nevynecha, kdyz by se zanorila do noveho panelu", K, [('if cd["druh"] != "deska" and cd["part_id"] not in PANEL_PARTY:', 'if cd["druh"] != "deska" and cd["part_id"] != PANEL_PART:')], "core"),
    ("m14", "zadne snizeni: panel se misto toho odebere (efektivni delka = zvolena)", K, [('            if _sloupcu_panelu(zl, zr, zm, rez, d) >= 1 and _rad_panelu(pg, volna_vyska) >= 1:\n                return d, rez\n', '            return d, rez\n')], "core"),
    # m15 (elektrozlab pocita s geometrii panelu 1190 misto zvolene delky) je EKVIVALENTNI mutace: odstupy zlabu jsou na delce nezavisle (zlab_od_y / zlab_od_z jdou ze sablony), kod ji nehlida zamerne
    ("s01", "verejna volba delky se ignoruje (vzdy 1190)", SH, [("    return float(d) if (d in S.PANEL_TYPY and (povolene is None or d in povolene)) else float(S.PANEL_DELKA_VYCHOZI)", "    return float(S.PANEL_DELKA_VYCHOZI)")], "shop"),
    ("s02", "zadne oznameni o snizeni delky", SH, [('    if p["panely"] and pozad_delka and int(pozad_delka) > int(round(p["panely_delka"])):', '    if False:')], "shop"),
    ("s03", "options.panellen vzdy prazdne (zadne zakazane delky)", SH, [('        options["panellen"] = {str(t_["delka"]): {"disabled": True, "reason": NENI_V_NABIDCE[lang] if t_["delka"] not in delky else _duvod_delky(lang, p, t_)}\n                               for t_ in (pi.get("typy") or []) if t_["delka"] not in delky or not t_["vejde"]}\n', '        options["panellen"] = {}\n')], "shop"),
    ("s04", "token nenese delku panelu", SH, [('            out["L"] = int(round(float(p["panely_delka"])))                                  # delka panelu (mm; bez klice = 1190)\n', '            pass\n')], "shop"),
    ("s05", "shrnuti ukazuje delku i bez panelu", SH, [('skryt.update(("panelcount", "panellen", "panelpos", "panelside"))', 'skryt.update(("panelcount", "panelpos", "panelside"))')], "shop"),
    ("s06", "normalizace ignoruje vyber delky", SH, [('p["panely_delka"] = _panellen(sel.get("panellen"), delky_pro_pozadavek() if delky is None else delky) if p["panely"] else float(S.PANEL_DELKA_VYCHOZI)', 'p["panely_delka"] = float(S.PANEL_DELKA_VYCHOZI)')], "shop"),
    ("s07", "odkaz na vyrobni list nese i vychozi delku", SH, [(' and not (k == "panely_delka" and int(round(float(v))) == S.PANEL_DELKA_VYCHOZI)})', '})')], "shop"),
    ("s08", "slot panellen nezavisi na panels", SH, [('"panellen": ["panels"], ', '')], "shop"),
    ("s09", "vyber vraci POZADOVANOU misto efektivni delky", SH, [('    norm["panellen"] = str(int(round(p["panely_delka"]))) if p["panely"] else str(S.PANEL_DELKA_VYCHOZI)       # efektivni delka panelu (po snizeni, kdyz se zvolena nevejde)\n', '')], "shop"),
    ("s10", "DIL_NA_SLOT nezna nove panely (chybove hlasky bez slotu)", SH, [('DIL_NA_SLOT = {**{pid_: "panels" for pid_ in S.PANEL_PARTY},', 'DIL_NA_SLOT = {"product_4931": "panels",')], "shop"),
    ("m16", "radu panelu na stojkach se nepocita (vyska panelu se ignoruje)", K, [('    return max(0, min(PANELY_MAX_RAD, int((volna_vyska + 1e-3) // (_P() + pg["v"] + 2.0 * PANEL_MEZERA))))', '    return PANELY_MAX_RAD')], "core"),
    ("m17", "nazvy novych dilu bez delky", K, [('_NAZVY.update({pid_: f"perforovaný panel {d_} mm" for d_, pid_ in PANEL_TYPY.items() if pid_ != PANEL_PART})', '_NAZVY.update({pid_: "perforovaný panel" for d_, pid_ in PANEL_TYPY.items() if pid_ != PANEL_PART})')], "core"),
    ("m18", "po odebrani panelu zustane zvolena delka", K, [('        p["panely_delka"] = float(PANEL_DELKA_VYCHOZI)               # ... ani delka panelu\n', '')], "core"),
    ("m19", "chybejici GLB jedne delky shodi vychozi cestu", K, [('    try:\n        return _panel_geometrie(d)\n    except StulChyba:\n        return None\n', '    return _panel_geometrie(d)\n')], "core"),
    ("m21", "nove dily panelu nepatri k prepinaci panely (automaticke odebrani je nezna)", K, [('**{pid_: "panely" for pid_ in PANEL_PARTY}, "product_4929": "led"', '"product_4931": "panely", "product_4929": "led"')], "core"),
    ("m20", "3D menu posila delku jako cislo misto textu (verejne id volby je text)", OV, [('            out[slot] = str(int(round(float(v))))                                 # verejne id volby delky panelu je text ("1481"), stejne jako ve schematu', '            out[slot] = v')], "core"),
    ("s11", "klic cache resolve bez POZADOVANE delky (oznameni se michaji)", SH, [(', norm.get("panellen"), tuple(sorted(delky)))', ', tuple(sorted(delky)))')], "shop"),
    ("s12", "verejnost dostane vsechny delky (zadny gating)", SH, [('    if not has_request_context() or _je_staff():\n        return frozenset(S.PANEL_DELKY)\n    return delky_verejne()', '    return frozenset(S.PANEL_DELKY)')], "shop"),
    ("s13", "zamestnanec dostane jen verejne delky", SH, [('    if not has_request_context() or _je_staff():', '    if not has_request_context():')], "shop"),
    ("s14", "verejnosti jen s 1190 se volba delky nescova (hidden chybi)", SH, [('    elif len(delky) < 2:\n        options["panellen"] = {"hidden": True}\n', '')], "shop"),
    ("s15", "normalizace nezahodi nenabizenou delku", SH, [('_panellen(sel.get("panellen"), delky_pro_pozadavek() if delky is None else delky)', '_panellen(sel.get("panellen"))')], "shop"),
    ("s16", "duvod u neaktivni delky je jen 'nevejde se'", SH, [('NENI_V_NABIDCE[lang] if t_["delka"] not in delky else _duvod_delky(lang, p, t_)', '_duvod_delky(lang, p, t_)')], "shop"),
    ("s17", "duvod nevejde se na stojky se nerozlisuje od sirky", SH, [('    if typ.get("vejde_sirka", True) and not typ.get("vejde_vyska", True):', '    if False:')], "shop"),
]


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
    env = dict(os.environ, STUL_API_OVERRIDE=os.path.join(tmp, "api"))
    if druh == "core":
        cmd = [PY, TEST_CORE]
    else:
        cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=" + os.path.join(REPO, "api", ".env"), "--setenv=HOME=/root", "--setenv=STUL_API_OVERRIDE=" + env["STUL_API_OVERRIDE"],
               "--working-directory=" + REPO, PY, TEST_SHOP]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=env, cwd=REPO)
    except subprocess.TimeoutExpired:
        return 124, ["TIMEOUT"]
    vystup = (p.stdout or "") + (p.stderr or "")
    selhalo = re.findall(r"^\s*CHYBA: (.{0,95})", vystup, re.M)[:3] + re.findall(r"^Traceback.*\n(?:.*\n){0,12}?(\w*(?:Error|Chyba)[^\n]{0,60})", vystup, re.M)[:1]
    return p.returncode, selhalo


def main():
    vybrane = set(sys.argv[1:])
    chycene, nechycene = [], []
    for mid, popis, soubor, nahrady, druh in MUTACE:
        if vybrane and mid not in vybrane:
            continue
        with open(os.path.join(ZDROJ, soubor), encoding="utf-8") as f:
            kod = f.read()
        chyba = False
        for stary, novy in nahrady:
            if kod.count(stary) != 1:
                print("%s CHYBA MUTACE: vzor se v %s nenasel prave jednou (%d x): %r" % (mid, soubor, kod.count(stary), stary[:80]))
                nechycene.append(mid)
                chyba = True
                break
            kod = kod.replace(stary, novy)
        if chyba:
            continue
        tmp = tempfile.mkdtemp(prefix="panely_mut_")
        try:
            postav(os.path.join(tmp, "k"), soubor, kod)
            rc, selhalo = spust(os.path.join(tmp, "k"), druh)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if rc != 0:
            chycene.append(mid)
            print("%s CHYCENA   %-72s -> %s" % (mid, popis, " | ".join(selhalo) or "rc=%d" % rc))
        else:
            nechycene.append(mid)
            print("%s NECHYCENA %-72s (test prosel i s chybou!)" % (mid, popis))
        sys.stdout.flush()
    print("\nSOUHRN: chyceno %d, nechyceno %d%s" % (len(chycene), len(nechycene), (" (" + ", ".join(nechycene) + ")") if nechycene else ""))
    return 0 if not nechycene else 1


if __name__ == "__main__":
    sys.exit(main())
