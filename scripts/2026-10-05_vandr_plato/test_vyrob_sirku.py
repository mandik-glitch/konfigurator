#!/usr/bin/env python3
"""Test vyrob_sirku.py (GLB + kusovnik plata pro konkretni sirku; bot10, 2026-10-05). Bez DB.
  api/venv/bin/python3 scripts/2026-10-05_vandr_plato/test_vyrob_sirku.py
NEZAVISLE: delky dilu se meri z vrcholu vystupniho GLB, cena / vaha / nazvy z JSON ceniku (`kusovnik_plato.json`) a pevneho seznamu delkove zavislych dilu."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "api"))
import vandr_param as VP  # noqa: E402
import vyrob_sirku as V  # noqa: E402
import v3d_glb  # noqa: E402

OK, FAILS = 0, []


def check(cond, name, detail=""):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(name)
        print("  CHYBA:", name, detail)


base = open(V.VYCHOZI_GLB, "rb").read()
js0, blob0 = VP.cti_glb(base)
par0 = js0["scenes"][0]["extras"]["vandrParam"]
KUS = json.load(open(os.path.join(HERE, "kusovnik_plato.json"), encoding="utf-8"))
DELKOVE = ("20x40x908_Zx4", "CUB6_917x413")


def delky(glb):
    js, blob = VP.cti_glb(glb)
    casti = VP.sber_mesh(js, blob, "")
    return casti, js


c0, _ = delky(base)
d0 = {c["jmeno"]: (c["P"][:, 2].min(), c["P"][:, 2].max()) for c in c0}
print("1) hotove GLB pro ruzne sirky")
for W in (449, 780, 940, 1057, 1100, 1679):
    d = W - 1057
    glb, bom = V.vyrob(base, W)
    casti, js = delky(glb)
    dl = {c["jmeno"]: c["P"][:, 2].max() - c["P"][:, 2].min() for c in casti}
    check(len(casti) == 33, f"W={W}: 33 casti")
    check(all(abs(dl[k] - (908 + d)) < 0.02 for k in ("20x40x908_Zx4", "20x40x908_Zx4_2")) and abs(dl["CUB6_915x413"] - (917 + d)) < 0.02, f"W={W}: podelne profily {908 + d} mm, dno {917 + d} mm", str({k: dl[k] for k in ("20x40x908_Zx4", "CUB6_915x413")}))
    vse = np.vstack([c["P"] for c in casti])
    vse0 = np.vstack([c["P"] for c in c0])
    check(abs((vse[:, 2].max() - vse[:, 2].min()) - (vse0[:, 2].max() - vse0[:, 2].min()) - d) < 0.02, f"W={W}: celkova sirka o {d} mm")
    nohy = sorted([c for c in casti if c["jmeno"].startswith("45x45x1700_noha")], key=lambda c: c["P"][:, 2].min())
    check(len(nohy) == 2 and all(abs((c["P"][:, 2].max() - c["P"][:, 2].min()) - 45.0) < 0.02 for c in nohy), f"W={W}: dve nohy 45 mm, nezdeformovane")
    ostatni_ok = all(abs((c["P"][:, 2].max() - c["P"][:, 2].min()) - (d0[c["jmeno"]][1] - d0[c["jmeno"]][0])) < 0.02 for c in casti if c["jmeno"] not in ("20x40x908_Zx4", "20x40x908_Zx4_2", "CUB6_915x413"))
    check(ostatni_ok, f"W={W}: ostatni dily zachovaly rozmer (jen posun)")
    spec = js["scenes"][0]["extras"]["v3d"]
    try:
        v3d_glb.validate_spec(spec)
        platny = True
    except Exception as e:                                          # noqa: BLE001
        platny = str(e)
    check(platny is True and "vandrParam" not in js["scenes"][0]["extras"], f"W={W}: spec v3d prochazi validate_spec, hotovy model bez vandrParam", str(platny))
    check(abs(spec["box"]["max"][2] - spec["box"]["min"][2] - (vse[:, 2].max() - vse[:, 2].min())) < 0.01, f"W={W}: obalka v3d.box odpovida skutecne sirce")
    # cena / vaha / nazvy z JSON ceniku
    cena = vaha = 0.0
    jmena = []
    for r in KUS["radky"]:
        c, v, jm = r["cena"], r["vaha"], r["dil"]
        if r["dil"] in DELKOVE:
            c += r["material"]["cena_za_mm"] * d
            v += r["material"]["vaha_za_mm"] * d
            jm = ("CUB6_%gx413" % (917 + d)) if r["dil"] == "CUB6_917x413" else ("20x40x%g_Zx4" % (908 + d))
        cena += c * r["ks"]
        vaha += v * r["ks"]
        jmena.append(jm)
    check(abs(bom["cena"] - cena) < 0.006 and abs(bom["vaha_g"] - vaha) < 0.006, f"W={W}: cena {cena:.2f} Kc a vaha {vaha:.2f} g = nezavisly vypocet", f"{bom['cena']} vs {cena}")
    check([r["dil"] for r in bom["radky"]] == jmena and sum(1 for r in bom["radky"] if r["zmena"]) == 2, f"W={W}: nazvy dilu v kusovniku ({jmena[3]}, {jmena[4]})")
    check(abs(sum(r["cena"] for r in bom["radky"]) - bom["cena"]) < 0.02, f"W={W}: soucet radku = cena")
    check(bom["sirka_mm"] == W and abs(bom["svetlost_mezi_nohama_mm"] - (967 + d)) < 0.01, f"W={W}: sirka a svetlost mezi nohama {967 + d} mm v kusovniku")
    if W == 1057:
        check(len(casti) == len(c0) and all(np.abs(a["P"] - b["P"]).max() < 1e-3 for a, b in zip(casti, c0)), "W=1057: geometrie shodna s vychozi (vrchol po vrcholu, po poradi)")
        check(abs(bom["cena"] - 4677.59) < 0.005, "W=1057: cena 4 677,59 Kc (cena komponentu ve Vandru)")

print("2) mimo rozsah a CLI")
for W in (448, 1680, 0, -5):
    try:
        V.vyrob(base, W)
        chyba = False
    except ValueError:
        chyba = True
    check(chyba, f"sirka {W} mm mimo rozsah 449-1679 = ValueError")
import subprocess, tempfile  # noqa: E402,E401
with tempfile.TemporaryDirectory() as tmp:
    out_glb, out_json = os.path.join(tmp, "p.glb"), os.path.join(tmp, "p.json")
    pr = subprocess.run([sys.executable, "-B", os.path.join(HERE, "vyrob_sirku.py"), "--sirka", "940", "--vystup", out_glb, "--kusovnik", out_json], capture_output=True, text=True)
    check(pr.returncode == 0 and os.path.getsize(out_glb) > 100000 and json.load(open(out_json, encoding="utf-8"))["sirka_mm"] == 940.0, "CLI: --sirka 940 zapise GLB a kusovnik", pr.stderr[:200])
    check("cena" in pr.stdout, "CLI vypise cenu a vahu", pr.stdout[:100])

print(f"\n{OK} kontrol OK" + ("" if not FAILS else f"; SELHALO {len(FAILS)}"))
sys.exit(1 if FAILS else 0)
