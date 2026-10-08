#!/usr/bin/env python3
"""Priprava GLB "vysuvne plato s promennou sirkou" ze sestavy z Vandru (bot10, 2026-10-05; Robert: "potrebuju upravitelnou sirku nekterych komponentu z vandr",
upresneni: "nohy nepotrebuju roztahovaci, jen to plato do sirky" - nohy se NIKDY nedeformuji, jen se posunou jako celek, natahuje se jen plato).

  api/venv/bin/python3 scripts/2026-10-05_vandr_plato/build_plato.py --uuid e1dd5c1b-6c5e-4edf-b9f7-c3f7a6af4a75 --koren Nohy2MasterH21700459 \
      --vystup webapp/katalog/vandr/param/plato_vysuvne.glb [--wmin 527 --wmax 1357] [--glb hotove.glb] [--kusovnik scripts/2026-10-05_vandr_plato/kusovnik_plato.json]
      [--delka-dil 20x40x --delka-od 300 --delka-do 1530]      (rozsah sirky z delky protahovaneho dilu; jinak --wmin / --wmax)

Postup: FBX export sestavy (/opt/vandrawee/web/storage/app/exported_models/<uuid>/<uuid>.fbx) -> GLB v mm STEJNYM postupem jako automat konverze
(scripts/2026-09-23_vandr_fbx_konverze_auto_dispatch.py; bez zapisu do DB) -> podstrom `--koren` (nohy + plato) s vypecenymi transformacemi -> posun do pocatku
(rovina natazeni z = 0, stred x, podlaha y = 0) -> GLB se spec v3d (look vd) a popisem parametrizace v `scenes[0].extras.vandrParam` (osa, rovina, vychozi sirka,
rozsah, natahovane dily s delkami). Pravidlo natazeni a jeho predpoklady: vandr_param.py. GLB patri do CHRANENE slozky webapp/katalog/vandr/ (jen zamestnanci)."""
import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vandr_param as VP

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXPORT_DIR = "/opt/vandrawee/web/storage/app/exported_models"


def preved_fbx(uuid, scratch):
    """FBX sestavy -> final.glb (mm) postupem automatu konverze; vraci cestu k GLB. Bez DB."""
    spec = importlib.util.spec_from_file_location("konverze", os.path.join(REPO, "scripts/2026-09-23_vandr_fbx_konverze_auto_dispatch.py"))
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    fbx = os.path.join(EXPORT_DIR, uuid, uuid + ".fbx")
    if not os.path.isfile(fbx):
        raise SystemExit("FBX neexistuje: " + fbx)
    r3d = d.priprav_render3d(scratch)
    httpd = d.spust_http_server(r3d)
    try:
        ok, final, msg = d.preved_jeden(r3d, httpd.server_address[1], fbx, scratch)
    finally:
        httpd.shutdown()
    if not ok:
        raise SystemExit("konverze selhala: " + str(msg)[:500])
    return final


def pripoj_kusovnik(kus, natahovane):
    """Kusovnik, cena a vaha z `vandr_kusovnik.py` (snimek DB Vandru) + pro kazdy PROTAHOVANY dil jeho radek: nazev se sablonou delky ({L} misto prvniho cisla za materialem),
    cena a vaha za 1 mm delky z materialu (Vandr oceni novy rozmer z materialu, viz vandr_kusovnik.py). Radek se hleda podle materialu (predpona nazvu), delky (+-3 mm) a poctu kusu;
    kdyz neni presne jeden, stavba selze (kusovnik a model by si neodpovidaly)."""
    radky = [dict(r) for r in kus["radky"]]
    for n in natahovane.values():
        shoda = []
        for i, r in enumerate(radky):
            m = r.get("material")
            if not m or not n["dil"].startswith(m["jmeno"]):
                continue
            cislo = re.match(r"[0-9.]+", r["dil"][len(m["jmeno"]):])
            if cislo and abs(float(cislo.group(0)) - n["delka0"]) <= 3.0 and r["ks"] == n["ks"]:
                shoda.append((i, m, cislo.group(0)))
        if len(shoda) != 1:
            raise SystemExit("protahovany dil %s (%d ks, delka %.1f): v kusovniku %d shod (cekam presne 1)" % (n["dil"], n["ks"], n["delka0"], len(shoda)))
        i, m, c = shoda[0]
        d = radky[i]["dil"]
        radky[i]["delka"] = {"sablona": d[:len(m["jmeno"])] + "{L}" + d[len(m["jmeno"]) + len(c):], "delka0": float(c), "cena_za_mm": m["cena_za_mm"], "vaha_za_mm": m["vaha_za_mm"]}
    return {"v": kus["v"], "mena": kus["mena"], "komponent": kus["komponent"], "zdroj": kus["zdroj"], "snimek": kus["snimek"], "cena0": kus["cena0"], "vaha0_g": kus["vaha0_g"], "radky": radky}


def sestav(glb_bytes, koren, wmin, wmax, nazev, os_=2, kusovnik=None, rozsah_delky=None, svetlost0=None):
    js, blob = VP.cti_glb(glb_bytes)
    casti = VP.sber_mesh(js, blob, koren)
    if not casti:
        raise SystemExit("v GLB neni podstrom '%s*' s mesi" % koren)
    vse = np.vstack([c["P"] for c in casti])
    lo, hi = vse.min(axis=0), vse.max(axis=0)
    w0 = float(hi[os_] - lo[os_])
    if abs(w0 - round(w0)) < 0.05:
        w0 = float(round(w0))                              # skutecny rozmer 1057,008 = Vandr "1057" (8 mikrometru zaokrouhleni modelu); vychozi sirka je cele cislo
    rovina, pres = VP.najdi_rovinu(casti, os_, float((lo[os_] + hi[os_]) / 2.0))
    # do pocatku: stred x, podlaha y = 0, rovina natazeni z = 0
    posun = np.array([-(lo[0] + hi[0]) / 2.0, -lo[1], -rovina])
    for c in casti:
        c["P"] = c["P"] + posun
    rovina_o = 0.0
    natahovane = {}
    for c in VP.protinajici(casti, os_, rovina_o):
        k = re.sub(r"_\d+$", "", c["jmeno"])                # "20x40x908_Zx4" a "20x40x908_Zx4_2" = stejny dil, 2 ks
        natahovane.setdefault(k, {"dil": k, "ks": 0, "delka0": round(float(c["P"][:, os_].max() - c["P"][:, os_].min()), 3)})["ks"] += 1
    vse = np.vstack([c["P"] for c in casti])
    lo, hi = vse.min(axis=0), vse.max(axis=0)
    # leva/prava noha = casti cele za / pred rovinou, jejich vnejsi okraje -> sirka svetla mezi nohama (jen informativne)
    nohy_pred = [c for c in casti if c["P"][:, os_].max() < rovina_o and c["jmeno"].startswith("45x45x1700")]
    nohy_za = [c for c in casti if c["P"][:, os_].min() > rovina_o and c["jmeno"].startswith("45x45x1700")]
    if svetlost0 is None:                                  # bez zadani z noh v podstromu (sestava s nohama); samostatny komponent: zadat z Vandru (components.min_width)
        svetlost0 = (round(float(min(c["P"][:, os_].min() for c in nohy_za) - max(c["P"][:, os_].max() for c in nohy_pred)), 3)
                     if nohy_pred and nohy_za else None)
    rozsah = None
    if rozsah_delky:                                       # rozsah zadany DELKOU protahovaneho dilu (Robert: "delky profilu 20x40 300 az 1530") -> sirka celku
        dil, od, do = rozsah_delky
        shoda = [n for n in natahovane.values() if n["dil"].startswith(dil)]
        if len(shoda) != 1:
            raise SystemExit("rozsah delky: protahovany dil '%s*' nalezen %d x (cekam presne 1)" % (dil, len(shoda)))
        wmin, wmax = w0 + (od - shoda[0]["delka0"]), w0 + (do - shoda[0]["delka0"])
        rozsah = {"dil": shoda[0]["dil"], "od": float(od), "do": float(do)}
    # obalka pro rameovani kamery = NEJSIRSI sestava (wmax), ne vychozi: model se natahuje v prohlizeci a kamera nesmi nic uriznout
    lo_b, hi_b = lo.copy(), hi.copy()
    pridat = max(0.0, (max(float(wmax), w0) - w0) / 2.0)
    lo_b[os_] -= pridat
    hi_b[os_] += pridat
    spec = {"v": 1, "u": "mm", "up": [0, 1, 0], "front": [-1, 0, 0],
            "box": {"min": [round(float(x), 3) for x in lo_b], "max": [round(float(x), 3) for x in hi_b]}, "look": "vd"}
    param = {"v": 1, "nazev": nazev, "os": os_, "rovina": rovina_o, "w0": round(w0, 3), "wmin": float(wmin), "wmax": float(wmax), "rozsah": rozsah,
             "svetlost0": svetlost0, "natahovane": sorted(natahovane.values(), key=lambda r: r["dil"]),
             "kusovnik": pripoj_kusovnik(kusovnik, natahovane) if kusovnik else None,
             "poznamka": "Natazeni podle roviny (vandr_param.natahni): vrcholy za rovinou +delta/2, pred rovinou -delta/2; nohy se jen posunou, natahuji se jen dily, ktere rovinu protinaji."}
    return VP.zapis_glb(casti, js.get("materials", []), spec, {"vandrParam": param}), param, len(casti)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uuid", help="UUID sestavy z Vandru (stored_models.uuid) - FBX export na serveru")
    ap.add_argument("--glb", help="uz prevedene GLB v mm (preskoci konverzi FBX)")
    ap.add_argument("--koren", required=True, help="predpona jmena korenoveho uzlu podstromu (napr. Nohy2MasterH21700459)")
    ap.add_argument("--vystup", required=True)
    ap.add_argument("--wmin", type=float, default=527.0)
    ap.add_argument("--wmax", type=float, default=1357.0)
    ap.add_argument("--delka-dil", help="predpona nazvu protahovaneho dilu, jehoz delka urcuje rozsah (napr. 20x40x)")
    ap.add_argument("--delka-od", type=float, help="nejmensi delka tohoto dilu v mm (urci wmin)")
    ap.add_argument("--delka-do", type=float, help="nejvetsi delka tohoto dilu v mm (urci wmax)")
    ap.add_argument("--kusovnik", help="JSON z vandr_kusovnik.py (kusovnik, cena a vaha komponentu); pripoji se k parametrizaci")
    ap.add_argument("--nazev", default="Výsuvné plato 3×43 (nohy Master H2 1700)")
    a = ap.parse_args()
    scratch = tempfile.mkdtemp(prefix="vandr_plato_")
    try:
        src = a.glb or preved_fbx(a.uuid, scratch)
        kus = json.load(open(a.kusovnik, encoding="utf-8")) if a.kusovnik else None
        rozsah_delky = (a.delka_dil, a.delka_od, a.delka_do) if (a.delka_dil and a.delka_od is not None and a.delka_do is not None) else None
        data, param, n = sestav(open(src, "rb").read(), a.koren, a.wmin, a.wmax, a.nazev, kusovnik=kus, rozsah_delky=rozsah_delky)
        os.makedirs(os.path.dirname(os.path.abspath(a.vystup)), exist_ok=True)
        with open(a.vystup, "wb") as fh:
            fh.write(data)
        print(json.dumps({"vystup": a.vystup, "bytes": len(data), "casti": n, "parametrizace": param}, ensure_ascii=False, indent=1))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
