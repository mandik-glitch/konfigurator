#!/usr/bin/env python3
"""Rendery pro aktivni produkty BEZ JAKEHOKOLI obrazku (Robert 2026-10-07: "vsechny produkty ktere nemaji zadny obrazek, i z generatoru,
proste kazdy produkt ktery je aktivni a nema obrazek, vytvorime mu 2 rendery z 3D modelu"). bot4.

Kazdy produkt dostane 2 snimky (dva pohledy) STEJNOU cestou jako karty a nabidky (sablona, pozadi, HDRI, materialy z panelu Rendering;
scripts/2026-09-09_turntable_render.py --nabidka-dily), zarazene JAKO DRZITEL RENDEROVACIHO KLICE (/root/.konfigurator_render_klic) a podle pauzy.
Nic nemeni v DB ani na webu - vysledky ukladaji do backups/2026-10-07_produkty_bez_obrazku/ k prohlednuti; nahrani do galerie je zvlast.

  seznam                         jen vypise produkty bez obrazku (a zda maji GLB)
  zaradit ID [ID ...] [--glb ID=cesta]   zaradi 2 rendery kazdemu; --glb pro produkt bez shop_products.glb_file (stoly z generatoru)
  sber                           zkopiruje hotove PNG (z private-files/blender-renders, kde je hodinova lhuta) do slozky vystupu

Spusteni (jako root, DB env pres _env): api/venv/bin/python3 scripts/2026-10-07_produkty_bez_obrazku.py seznam
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
sys.path.insert(0, os.path.join(REPO, "api"))
import _env  # noqa: E402

os.environ.update(_env.load_env())
CLI = os.path.join(REPO, "scripts", "2026-09-09_turntable_render.py")
RENDER_OUT = os.path.join(REPO, "private-files", "blender-renders")
VYSTUP = os.path.join(REPO, "backups", "2026-10-07_produkty_bez_obrazku")
STAV = os.path.join(VYSTUP, "joby.json")
KLIC = "/root/.konfigurator_render_klic"          # klic bot4 (spravce renderu), viz scripts/_render_klic.py
# dva pohledy (azimut ve konvenci SCENY, elevace) - Robert 2026-10-07: 'vzdy jeden celni, a druhy tak jak mas': 1) CELNI (az 180 = az 270 otocky = FRONT_AZIMUTH_DEG,
# elevace 5), 2) 3/4 shora zprava
POHLEDY = ((180.0, 5.0), (-50.0, 25.0))


def produkty_bez_obrazku(cur):
    cur.execute("""SELECT sp.id, sp.sku, sp.name, sp.glb_file,
        (SELECT COUNT(*) FROM shop_product_images i WHERE i.product_id=sp.id) n_img,
        (SELECT COUNT(*) FROM content_gallery_items g WHERE g.owner_type='product' AND g.owner_id=sp.id AND g.is_public=1) n_gal,
        (SELECT COUNT(*) FROM product_turntable_frames f WHERE f.shop_product_id=sp.id AND f.is_active=1) n_tt,
        sp.thumbnail_file FROM shop_products sp WHERE sp.active=1 ORDER BY sp.id""")
    import re
    stul_karta = re.compile(r"^STUL-S\d{2}-[0-9a-f]{8}$")      # karty stolu z generatoru: rendery resi jejich automat (otocka), ne tenhle skript
    return [r for r in cur.fetchall() if not r["n_img"] and not r["n_gal"] and not r["n_tt"] and not r["thumbnail_file"]
            and not stul_karta.match(r["sku"] or "")]


def nacti_stav():
    try:
        with open(STAV, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"joby": []}


def uloz_stav(st):
    os.makedirs(VYSTUP, exist_ok=True)
    with open(STAV, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=1, ensure_ascii=False)


def celni_pohled(pid):
    """CELNI pohled (azimut sceny, elevace): obecne predek (180, 5); u PLOCHYCH dilu (panely, desky, pricky: dva nejvetsi rozmery
    aspon 4x vetsi nez nejmensi a druhy nejvetsi >= 0,2 nejvetsiho) Robert 2026-10-07: 'u panelu celni se mysli ta plocha' -> kolmo na
    velkou plochu (nejmensi rozmer y: shora el 89; z: az -90; x: az 0). Rozmery z POSITION min/max v GLB katalogu."""
    import struct
    try:
        b = open(os.path.join(REPO, "webapp", "katalog", "product_%d.glb" % pid), "rb").read()
        js = json.loads(b[20:20 + struct.unpack("<I", b[12:16])[0]])
        lo, hi = [1e18] * 3, [-1e18] * 3
        for m in js["meshes"]:
            for p in m["primitives"]:
                a = js["accessors"][p["attributes"]["POSITION"]]
                for i in range(3):
                    lo[i], hi[i] = min(lo[i], a["min"][i]), max(hi[i], a["max"][i])
        d = [hi[i] - lo[i] for i in range(3)]
    except (OSError, ValueError, KeyError):
        return POHLEDY[0]
    razene = sorted(d)
    if razene[0] * 4 <= razene[1] and razene[1] >= 0.2 * razene[2]:
        osa = d.index(razene[0])
        return {1: (180.0, 89.0), 2: (-90.0, 0.0), 0: (0.0, 0.0)}[osa]
    return POHLEDY[0]


def panel_args():
    import _render_prirazeni_lib as lib
    conn = _env.get_conn()
    try:
        with conn.cursor() as cur:
            return list(lib.nacti_nastaveni_pro_automat(cur))
    finally:
        conn.close()


def zarad(pid, cislo, az, el, panel, glb_vlastni=None):
    job = uuid.uuid4().hex
    soubor = os.path.join(VYSTUP, "dily_%s_%d.json" % (pid, cislo))
    os.makedirs(VYSTUP, exist_ok=True)
    cast = {"part_id": "product_%s" % pid, "position": [0, 0, 0], "quaternion": [0, 0, 0, 1], "scale": [1, 1, 1]}
    json.dump([cast], open(soubor, "w"))
    env = dict(os.environ, KONFIGURATOR_RENDER_KLIC_SOUBOR=KLIC, BOT_ID="bot4")
    env.pop("KONFIGURATOR_NABIDKA_Z_API", None)             # jako DRZITEL KLICE, ne jako API
    p = subprocess.run([sys.executable, CLI, "--nabidka-dily", soubor, "--nabidka-azimut", repr(az), "--nabidka-elevace", repr(el),
                        "--nabidka-job", job] + panel, env=env, capture_output=True, text=True, timeout=300)
    if p.returncode != 0:
        raise RuntimeError("zarazeni produktu %s (pohled %d) selhalo: %s" % (pid, cislo, (p.stdout + p.stderr)[-600:]))
    return job


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("seznam")
    z = sp.add_parser("zaradit")
    z.add_argument("ids", nargs="+", type=int)
    sp.add_parser("sber")
    a = ap.parse_args()
    conn = _env.get_conn()
    try:
        with conn.cursor() as cur:
            bez = produkty_bez_obrazku(cur)
    finally:
        conn.close()
    if a.cmd == "seznam":
        print("aktivnich produktu bez jakehokoli obrazku: %d" % len(bez))
        for r in bez:
            print("  %5d  %-40s %-44s %s" % (r["id"], (r["sku"] or "")[:40], (r["name"] or "")[:44], r["glb_file"] or "BEZ GLB"))
        return 0
    if a.cmd == "zaradit":
        platne = {r["id"]: r for r in bez}
        panel = panel_args()
        st = nacti_stav()
        for pid in a.ids:
            if pid not in platne:
                print("PRESKOCENO %d: neni aktivni bez obrazku" % pid)
                continue
            if not platne[pid]["glb_file"]:
                print("PRESKOCENO %d: produkt nema glb_file (stul z generatoru - ceka na GLB od bot8)" % pid)
                continue
            for cislo, (az, el) in enumerate((celni_pohled(pid), POHLEDY[1]), 1):
                job = zarad(pid, cislo, az, el, panel)
                st["joby"].append({"produkt": pid, "pohled": cislo, "job": job, "zarazeno": time.time(), "hotovo": False})
                uloz_stav(st)
                print("ZARAZENO produkt %d pohled %d: job %s" % (pid, cislo, job))
        return 0
    if a.cmd == "sber":
        st = nacti_stav()
        zbyva = 0
        for j in st["joby"]:
            if j.get("hotovo"):
                continue
            sf = os.path.join(RENDER_OUT, j["job"] + ".status.json")
            png = os.path.join(RENDER_OUT, j["job"] + ".png")
            try:
                stav = json.load(open(sf, encoding="utf-8"))
            except (OSError, ValueError):
                stav = {}
            if stav.get("state") == "done" and os.path.isfile(png):
                cil = os.path.join(VYSTUP, "%d_%d.png" % (j["produkt"], j["pohled"]))
                shutil.copyfile(png, cil)
                j["hotovo"] = True
                print("HOTOVO produkt %d pohled %d -> %s" % (j["produkt"], j["pohled"], cil))
            elif stav.get("state") == "error":
                j["hotovo"], j["chyba"] = True, (stav.get("error") or "?")[:300]
                print("CHYBA produkt %d pohled %d: %s" % (j["produkt"], j["pohled"], j["chyba"]))
            else:
                zbyva += 1
                print("CEKA produkt %d pohled %d: %s" % (j["produkt"], j["pohled"], stav.get("state") or "stav nenalezen (uklizen?)"))
        uloz_stav(st)
        print("zbyva %d" % zbyva)
        return 0


if __name__ == "__main__":
    sys.exit(main())
