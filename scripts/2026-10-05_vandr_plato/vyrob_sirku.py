#!/usr/bin/env python3
"""GLB a kusovnik vysuvneho plata Vandr pro KONKRETNI sirku (bot10, 2026-10-05) - z parametrickeho GLB (`build_plato.py`) udela hotovy model a kusovnik pro sirku W (nabidka, render).

  api/venv/bin/python3 scripts/2026-10-05_vandr_plato/vyrob_sirku.py --sirka 940 --vystup /tmp/plato_940.glb --kusovnik /tmp/plato_940.json
  (zdroj: --glb, vychozi webapp/katalog/vandr/param/plato_vysuvne.glb; sirka = cela sirka vc. nohou v mm, tj. ta, co se ve Vandru jmenuje 1057)

Stejny vzorec jako kontrolni scena (webapp/kontrola.html, rezim=param): natazeni podle roviny (`vandr_param.natahni`), cena / vaha / nazvy protazenych dilu z `vandrParam.kusovnik`.
Vystupni GLB nema `vandrParam` (je to hotovy model, ne parametricky) a jeho obalka (`v3d.box`) odpovida skutecne sirce."""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vandr_param as VP

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VYCHOZI_GLB = os.path.join(REPO, "webapp/katalog/vandr/param/plato_vysuvne.glb")


def kusovnik(param, d):
    """Kusovnik, cena (Kc) a vaha (g) pro zmenu sirky o `d` mm proti vychozi: pevne dily beze zmeny, protazene s materialove prepoctenou cenou a vahou."""
    k = param.get("kusovnik")
    if not k:
        return None
    radky, cena, vaha = [], 0.0, 0.0
    for r in k["radky"]:
        c, v, jm = r["cena"], r["vaha"], r["dil"]
        if r.get("delka"):
            dl = r["delka"]
            c += dl["cena_za_mm"] * d
            v += dl["vaha_za_mm"] * d
            jm = dl["sablona"].replace("{L}", "%g" % (round((dl["delka0"] + d) * 10) / 10))
        cena += c * r["ks"]
        vaha += v * r["ks"]
        radky.append({"dil": jm, "ks": r["ks"], "cena_ks": round(c, 2), "cena": round(c * r["ks"], 2), "vaha_ks_g": round(v, 2), "zmena": bool(r.get("delka"))})
    return {"mena": k["mena"], "cena": round(cena, 2), "vaha_g": round(vaha, 2), "zdroj": k["zdroj"], "snimek_ceniku": k["snimek"], "radky": radky}


def vyrob(glb_bytes, sirka):
    """(GLB bytes, kusovnik dict) pro celkovou sirku `sirka` mm; ValueError mimo rozsah parametrizace."""
    js, blob = VP.cti_glb(glb_bytes)
    param = js["scenes"][0]["extras"]["vandrParam"]
    if not (param["wmin"] <= sirka <= param["wmax"]):
        raise ValueError("sirka %s mm je mimo rozsah %s-%s mm" % (sirka, param["wmin"], param["wmax"]))
    casti = VP.sber_mesh(js, blob, "")
    d = float(sirka) - param["w0"]
    for c in casti:
        c["P"] = VP.natahni(c["P"], param["os"], param["rovina"], d)
    vse = np.vstack([c["P"] for c in casti])
    spec = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [-1, 0, 0],
            "box": {"min": [round(float(x), 3) for x in vse.min(axis=0)], "max": [round(float(x), 3) for x in vse.max(axis=0)]}, "look": "vd"}
    bom = kusovnik(param, d)
    bom = dict(bom or {}, sirka_mm=float(sirka), svetlost_mezi_nohama_mm=(round(param["svetlost0"] + d, 3) if param.get("svetlost0") is not None else None),
               komponent=param.get("nazev"))
    return VP.zapis_glb(casti, js.get("materials", []), spec), bom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sirka", type=float, required=True, help="celkova sirka vc. nohou v mm")
    ap.add_argument("--glb", default=VYCHOZI_GLB)
    ap.add_argument("--vystup", required=True)
    ap.add_argument("--kusovnik", help="kam zapsat kusovnik / cenu / vahu (JSON)")
    a = ap.parse_args()
    data, bom = vyrob(open(a.glb, "rb").read(), a.sirka)
    with open(a.vystup, "wb") as fh:
        fh.write(data)
    if a.kusovnik:
        with open(a.kusovnik, "w", encoding="utf-8") as fh:
            json.dump(bom, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    print("ok: sirka %g mm, GLB %d B%s%s" % (a.sirka, len(data), ", cena %.2f Kc, vaha %.2f g" % (bom["cena"], bom["vaha_g"]) if bom.get("cena") is not None else "", " -> " + a.vystup))


if __name__ == "__main__":
    sys.exit(main())
