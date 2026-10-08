#!/usr/bin/env python3
"""Mutace RAZITEK LOGA NA PROFILECH STOLU (bot8, 2026-10-06): kazda umyslna chyba v api/stul_razitka.py / api/stul_glb.py MUSI shodit test_razitka_stolu.py (CHYCENA = dobre).
Kandidat = kopie api/ (symlinky + jeden upraveny soubor) v docasne slozce; test bere `STUL_API_DIR`. Po 4 paralelne.
  api/venv/bin/python3 scripts/2026-10-06_razitka_stolu/mutace.py [nazev_mutace ...]"""
import concurrent.futures
import glob
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST = os.path.join(REPO, "scripts", "2026-10-06_razitka_stolu", "test_razitka_stolu.py")
PY = os.environ.get("PY") or sys.executable

# (nazev, soubor v api/, puvodni text (prave 1x), nahrada)
MUTACE = [
    ("s01_bez_blokace", "stul_razitka.py", "blok = (ws.max(axis=1) >= w_min) & (ws.min(axis=1) <= DOHLED_MM) & (vs.max(axis=1) >= -v_mez) & (vs.min(axis=1) <= v_mez)", "blok = np.zeros(len(ws), bool)"),
    ("s02_bez_exponovani", "stul_razitka.py", "(ws.min(axis=1) <= DOHLED_MM)", "(ws.min(axis=1) <= h + 5.0)"),
    ("s03_kazdy_treti", "stul_razitka.py", "if kk % R.KAZDY_NTY == posun)", "if True)"),
    ("s04_rozestup", "stul_razitka.py", "        if any(abs(t - s) < R.LOGO_DELKA_MM + R.MIN_ROZESTUP_LOG_MM - 1e-6 for s in zakazane):\n            povolene", "        if False:\n            povolene"),
    ("s05_odsazeni_loga", "stul_razitka.py", "bod(h + R.LOGO_ODSAZENI_PIVOTU_MM)", "bod(h - R.LOGO_ODSAZENI_PIVOTU_MM)"),
    ("s06_vypln_poloha", "stul_razitka.py", "bod(h - drazka_d / 2.0)", "bod(h)"),
    ("s07_drazka_prohozena", "stul_razitka.py", "\"Object_7\": (8.2, 10.0)", "\"Object_7\": (10.0, 8.2)"),
    ("s08_text_obracene", "stul_razitka.py", "if R._je_text_o_180_stupnu(normala, osa, y):", "if False:"),
    ("s10_seed", "stul_razitka.py", "R._nahodne_0_1(\"posun\", seed, lok_idx)", "R._nahodne_0_1(\"posun\", \"x\", lok_idx)"),
    ("s11_posun_modelu", "stul_glb.py", "\"translation\": [round(float(v), 4) for v in (np.array(rz[\"logo\"][\"pos\"], float) + posun)]", "\"translation\": [round(float(v), 4) for v in np.array(rz[\"logo\"][\"pos\"], float)]"),
    ("s12_verejny_s_razitky", "stul_glb.py", "def model_pro_parametry(parametry, razitka=False):", "def model_pro_parametry(parametry, razitka=True):"),
    ("s13_vypln_do_oceli", "stul_glb.py", "        g = skupiny[\"alu\"]\n        g[\"P\"].append(Pm.astype(np.float64) @ Rv.T", "        g = skupiny[\"ocel\"]\n        g[\"P\"].append(Pm.astype(np.float64) @ Rv.T"),
    ("s14_barva_loga", "stul_glb.py", "\"baseColorFactor\": RZ.LOGO_BARVA,", "\"baseColorFactor\": [1.0, 1.0, 1.0, 1.0],"),
    ("s15_logo_neni_instance", "stul_glb.py", "            nodes.append({\"name\": f\"n{len(nodes)}\", \"mesh\": mesh_loga,", "            meshes.append(dict(meshes[mesh_loga])); mesh_loga = len(meshes) - 1\n            nodes.append({\"name\": f\"n{len(nodes)}\", \"mesh\": mesh_loga,"),
]


def spust(m):
    nazev, soubor, puvodni, nahrada = m
    d = tempfile.mkdtemp(prefix="mut_razitka_")
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
