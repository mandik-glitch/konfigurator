#!/usr/bin/env python3
"""Mutacni kontrola testu vykresu nabidky ze stolu (bot8, 2026-10-06).

Test (test_vykresy.js) musi chytit kazdou zamerne vnesenou chybu v `webapp/js/scene/stul-nabidka-vykresy.js`, `webapp/scene.html` a `webapp/js/scene/stul-konfigurator.js`.
Mutace se NEDELAJI v zivem stromu: pro kazdou se postavi kandidatni statika (symlinky na zive soubory, jen mutovany soubor je kopie) a most `_most_scena.py` ji
servíruje pres WEB_DIR (API zustava zive, DB se jen cte, zapisy se nepredavaji). Mutace je "chycena", kdyz test skonci nenulovym kodem (FAIL nebo spadl/vyprsel cas).

Spusteni (jako root, ~1-2 min na mutaci):  python3 scripts/2026-10-06_nabidka_vykresy_testy/mutace.py [m01 m05 ...]
CEKEJ_MS=150000 python3 ... mutace.py m01 m05  = delsi cekani na banner (pri zatezi stroje se mutace chycena jen timeoutem overuji znovu: ma selhat konkretni kontrola, ne cas).
Vystup: radek na mutaci (CHYCENA + ktere kontroly selhaly / NECHYCENA) a na konci souhrn; konci kodem 0 jen kdyz jsou chycene VSECHNY.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
WEB = os.path.join(REPO, "webapp")
PY = os.path.join(REPO, "api", "venv", "bin", "python3")
MOST = os.path.join(REPO, "scripts", "2026-10-06_nabidka_vykresy_testy", "_most_scena.py")
TEST = os.path.join(REPO, "scripts", "2026-10-06_nabidka_vykresy_testy", "test_vykresy.js")
JS = "js/scene/stul-nabidka-vykresy.js"
HTML = "scene.html"
KONF = "js/scene/stul-konfigurator.js"

# (id, popis, soubor, [(puvodni, nove), ...], scenare, cekej_ms)
MUTACE = [
    ("m01", "scena v rezimu vykresu obnovi posledni sestavu (cizi obsah ve vykresech)", HTML,
     [('  try { if (window.__nabidkaVykresy || new URLSearchParams(location.search).has("nabidka_vykresy")) return; } catch (e) { /* ignoruj */ }\n', '')], "A", 40000),
    ("m02", "narys a bokorys prohozene (narys = kamera front)", JS,
     [('vykres("side", dimStyle)', 'vykres("@@", dimStyle)'), ('vykres("front", dimStyle)', 'vykres("side", dimStyle)'), ('vykres("@@", dimStyle)', 'vykres("front", dimStyle)')], "A", 40000),
    ("m03", "krizek os se pri snimani neskryje", JS, [('    if (osyViditelne) setOriginAxisVisible(false);\n', '')], "A", 40000),
    ("m04", "krizek os se po snimani nevrati", JS, [('      if (osyViditelne) setOriginAxisVisible(true);\n', '')], "A", 40000),
    ("m05", "pixelRatio se pri snimani nenastavi na 1 (HiDPI -> jine rozmery)", JS, [('    renderer.setPixelRatio(1);\n', '')], "AD", 40000),
    ("m06", "plátno vykresu bez pevne vysky (podle okna)", JS, [('      pevnyViewport(VYKRES_SIRKA_PX, VYKRES_VYSKA_PX);\n', '')], "A", 40000),
    ("m07", "po snimani zustanou podvrzene rozmery viewportu", JS, [('      uvolniViewport();\n', '')], "A", 40000),
    ("m08", "3D snimky ve vykresovem rezimu (bile pozadi, drat)", JS, [('      setTechnicalDrawingMode(false);\n      pevnyViewport(SNIMEK_3D_SIRKA_PX', '      pevnyViewport(SNIMEK_3D_SIRKA_PX')], "A", 40000),
    ("m09", "stul-konfigurator neposle udalost po vlozeni", KONF,
     [('        vloz(q).then(ok => { try { window.dispatchEvent(new CustomEvent("stul-z-adresy-vlozen", { detail: { ok: !!ok } })); } catch (e) { /* stara scena bez CustomEvent */ } });', '        vloz(q);')], "A", 25000),
    ("m10", "vykresy se posilaji na spatnou adresu", JS, [('"/vykresy"', '"/vykres"')], "A", 40000),
    ("m11", "bez opakovani pri orezu popisku (jen vychozi okraj)", JS, [('const KOTA_OKRAJE = [undefined, 90, 115, 140];', 'const KOTA_OKRAJE = [undefined];')], "A", 40000),
    ("m12", "selhane vlozeni stolu se ignoruje (snimani nad prazdnou scenou)", JS,
     [('      if (!vlozenoOk) { chyba("Stůl se do scény nepodařilo vložit, výkresy nelze vyrobit. Zavřete kartu a vytvořte nabídku znovu.", false); return; }\n', '')], "B", 25000),
    ("m13", "\"Zkusit znovu\" nic neudela", JS, [('chyba(text, opakovat = true) {\n    stav(text, "chyba", opakovat ? [["Zkusit znovu", () => spust(true)]] : []);', 'chyba(text, opakovat = true) {\n    stav(text, "chyba", opakovat ? [["Zkusit znovu", () => {}]] : []);')], "B", 25000),
    ("m14", "chybi stul v adrese se tvari jako cekani (MA_STUL vzdy true)", JS,
     [('const MA_STUL = (() => { try { return window.__stulZAdresy === true || new URLSearchParams(location.search).has("stul"); } catch (e) { return false; } })();', 'const MA_STUL = true;')], "C", 25000),
    ("m15", "chybi 3D snimek view3d_a v odeslanych datech", JS, [('return { narys, bokorys, pudorys, view3d_a, view3d_b };', 'return { narys, bokorys, pudorys, view3d_b };')], "A", 40000),
    ("m16", "bokorys a pudorys prohozene v odeslanych datech", JS, [('return { narys, bokorys, pudorys, view3d_a, view3d_b };', 'return { narys, bokorys: pudorys, pudorys: bokorys, view3d_a, view3d_b };')], "A", 40000),
    ("m17", "captureOrthoWithDims ignoruje vetsi okraj kot (retry nema efekt)", HTML,
     [('const lay = offerKotaLayout(newW / baseH, kotaLayer);', 'const lay = offerKotaLayout(newW / baseH);')], "A", 40000),
    ("m18", "po neuspechu se banner \"ulozeno\" ukaze i pri chybe serveru (res.ok se ignoruje)", JS, [('      if (!res.ok) {\n        const kod', '      if (false) {\n        const kod')], "B", 25000),
]


def postav(src, dst, zmeny):
    """Strom dst = symlinky na src, jen soubory v `zmeny` ({relativni cesta: obsah}) jsou skutecne kopie."""
    def rec(s, d, rel):
        os.makedirs(d, exist_ok=True)
        for jmeno in os.listdir(s):
            r = (rel + "/" + jmeno) if rel else jmeno
            sp, dp = os.path.join(s, jmeno), os.path.join(d, jmeno)
            if r in zmeny:
                with open(dp, "w", encoding="utf-8") as f:
                    f.write(zmeny[r])
            elif any(k.startswith(r + "/") for k in zmeny):
                rec(sp, dp, r)
            else:
                os.symlink(sp, dp)
    rec(src, dst, "")


def spust(web_dir, scenare, cekej_ms):
    cmd = ["systemd-run", "--pipe", "--wait", "--quiet", "--property=EnvironmentFile=" + os.path.join(REPO, "api", ".env"), "--setenv=HOME=/root",
           "--setenv=WEB_DIR=" + web_dir, "--setenv=SCENARE=" + scenare, "--setenv=CEKEJ_MS=" + str(cekej_ms), "--working-directory=" + REPO, PY, MOST, TEST]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return 124, ["TIMEOUT"]
    vystup = (p.stdout or "") + (p.stderr or "")
    selhalo = re.findall(r"^FAIL (\S+)", vystup, re.M) + re.findall(r"^TEST SPADL: (.{0,70})", vystup, re.M)
    return p.returncode, selhalo


def main():
    vybrane = set(sys.argv[1:])
    tmp = tempfile.mkdtemp(prefix="vykresy_mut_")
    chycene, nechycene = [], []
    try:
        for mid, popis, soubor, nahrady, scenare, cekej in MUTACE:
            if vybrane and mid not in vybrane:
                continue
            with open(os.path.join(WEB, soubor), encoding="utf-8") as f:
                kod = f.read()
            for stary, novy in nahrady:
                if kod.count(stary) != 1:
                    print("%s CHYBA MUTACE: vzor se v %s nenasel prave jednou (%d x): %r" % (mid, soubor, kod.count(stary), stary[:70]))
                    nechycene.append(mid)
                    break
                kod = kod.replace(stary, novy)
            else:
                d = os.path.join(tmp, mid)
                postav(WEB, d, {soubor: kod})
                rc, selhalo = spust(d, scenare, int(os.environ.get("CEKEJ_MS") or cekej))
                if rc != 0:
                    chycene.append(mid)
                    print("%s CHYCENA   %-80s -> %s" % (mid, popis, ", ".join(selhalo) or "rc=%d" % rc))
                else:
                    nechycene.append(mid)
                    print("%s NECHYCENA %-80s (test prosel i s chybou!)" % (mid, popis))
                shutil.rmtree(d, ignore_errors=True)
            sys.stdout.flush()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSOUHRN: chyceno %d, nechyceno %d%s" % (len(chycene), len(nechycene), (" (" + ", ".join(nechycene) + ")") if nechycene else ""))
    return 0 if not nechycene else 1


if __name__ == "__main__":
    sys.exit(main())
