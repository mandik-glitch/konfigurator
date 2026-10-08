#!/usr/bin/env python3
"""Mutace ZASLEPEK NA VOLNE KONCE PROFILU (bot8, 2026-10-06): kazda umyslna chyba v api/stul_konfigurator.py / api/stul_glb.py MUSI shodit test_zaslepky_konce.py (CHYCENA = dobre).
Kandidat = kopie api/ (symlinky + jeden upraveny soubor) v docasne slozce; test bere `STUL_API_DIR`. Po 4 paralelne.
  api/venv/bin/python3 scripts/2026-10-06_zaslepky_konce/mutace.py [nazev_mutace ...]"""
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST = os.path.join(REPO, "scripts", "2026-10-06_zaslepky_konce", "test_zaslepky_konce.py")
PY = os.environ.get("PY") or sys.executable

# (nazev, soubor v api/, puvodni text (prave 1x), nahrada)
MUTACE = [
    ("c01_zadne_zaslepky", "stul_konfigurator.py", "    for k_prof, znak, bod, dvn in _volne_konce(clenove, spojky):", "    for k_prof, znak, bod, dvn in []:"),
    ("c03_dotyk_jen_na_plose", "stul_konfigurator.py", "ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM, ZASLEPKA_ZMENSENI_MM = 1.5, 2.5, 1.0", "ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM, ZASLEPKA_ZMENSENI_MM = 0.2, 0.2, 1.0"),
    ("c04_dotyk_cely_prurez", "stul_konfigurator.py", "ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM, ZASLEPKA_ZMENSENI_MM = 1.5, 2.5, 1.0", "ZASLEPKA_DOTYK_PRED_MM, ZASLEPKA_DOTYK_ZA_MM, ZASLEPKA_ZMENSENI_MM = 1.5, 2.5, -12.0"),
    ("c05_poloha_uvnitr", "stul_konfigurator.py", "bod + dvn * _sd()[\"zaslepka_vyska\"], \"prisl\", src=None)", "bod, \"prisl\", src=None)"),
    ("c06_zatka_ven", "stul_konfigurator.py", "_q_zaslepky(-dvn), [1.0, 1.0, 1.0], bod + dvn", "_q_zaslepky(dvn), [1.0, 1.0, 1.0], bod + dvn"),
    ("c07_poradi_zaslepek", "stul_konfigurator.py", "poradi = ([k for k in clenove if not _je_vz(k) and not _je_zasl(k)] + [k for k in spojky if not _je_vz(k)]", "poradi = ([k for k in clenove if not _je_vz(k)] + [k for k in spojky if not _je_vz(k)]"),
    ("c08_rozmery_se_zaslepkami", "stul_konfigurator.py", "\"rozmery\": _rozmery([b for b, k in zip(bb, poradi) if not _je_zasl(k)]),", "\"rozmery\": _rozmery(bb),"),
    ("c10_role_zaslepky", "stul_konfigurator.py", "    if t == \"zasl\":\n        return \"zaslepka\", \"záslepka volného konce profilu\"\n", ""),
    ("c11_montazni_krok", "stul_konfigurator.py", "kat == \"konec\" or kat == \"kolecko\" or kat == \"zaslepka\"", "kat == \"konec\" or kat == \"kolecko\""),
    ("c12_kolize_se_spojkou", "stul_konfigurator.py", " if c[\"druh\"] in (\"prisl\", \"deska\") and not _je_zasl(k)]", " if c[\"druh\"] in (\"prisl\", \"deska\")]"),
    ("c13_otoceni_osy_x", "stul_konfigurator.py", "ref = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])", "ref = np.array([0.0, 0.0, 1.0]) if abs(z[2]) < 0.9 else np.array([1.0, 0.0, 0.0])"),
    ("c14_verze_pravidel", "stul_glb.py", "RULES_VERSION = \"2026-10-06.1\"", "RULES_VERSION = \"2026-10-05.2\""),
    ("c15_zaslepka_mimo_osu", "stul_konfigurator.py", "bod = stred + dvn * (L / 2.0)", "bod = stred + dvn * (L / 2.0) + a1 * 0.5"),
    ("c16_konec_s_odchylkou", "stul_konfigurator.py", "bod = stred + dvn * (L / 2.0)", "bod = stred + dvn * (L / 2.0 - 1.0)"),
]


def spust(m):
    nazev, soubor, puvodni, nahrada = m
    d = tempfile.mkdtemp(prefix="mut_zasl_")
    try:
        os.makedirs(os.path.join(d, "api"))
        for f in glob.glob(os.path.join(REPO, "api", "*")):
            os.symlink(f, os.path.join(d, "api", os.path.basename(f)))
        for jm in ("webapp", "scripts"):
            os.symlink(os.path.join(REPO, jm), os.path.join(d, jm))
        cil = os.path.join(d, "api", soubor)
        os.remove(cil)
        s = open(os.path.join(REPO, "api", soubor), encoding="utf-8").read()
        if s.count(puvodni) != 1:
            return nazev, None, f"puvodni text se v {soubor} nenasel prave jednou ({s.count(puvodni)}x)"
        open(cil, "w", encoding="utf-8").write(s.replace(puvodni, nahrada))
        p = subprocess.run([PY, TEST], capture_output=True, text=True, timeout=1500, env=dict(os.environ, STUL_API_DIR=os.path.join(d, "api")))
        return nazev, p.returncode, p.stdout.count("FAIL") + (1 if p.returncode not in (0, 1) else 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    vyber = set(sys.argv[1:])
    seznam = [m for m in MUTACE if not vyber or m[0] in vyber]
    necytene = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for nazev, rc, info in ex.map(spust, seznam):
            if rc is None:
                print(f"mutace {nazev}: CHYBA MUTACE - {info}")
                necytene.append(nazev)
                continue
            chycena = rc != 0
            print(f"mutace {nazev}: rc={rc} ({'CHYCENA' if chycena else 'NECHYCENA'})  {info} FAIL")
            if not chycena:
                necytene.append(nazev)
    print(f"\n==> {len(seznam) - len(necytene)}/{len(seznam)} mutaci chyceno" + (f"; NECHYCENE / VADNE: {', '.join(necytene)}" if necytene else " - VSECHNY CHYCENY"))
    sys.exit(1 if necytene else 0)
