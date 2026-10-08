#!/usr/bin/env python3
"""Obrazky rucnich svitidel LED (GLB z generatoru -> three.js -> PNG) do $SP/led_rucne/img (bot8, 2026-10-08): (1) stul 2400 mm, 2 RUCNE pridana svitidla 600; (2) 3 kratsi svitidla s mezerami (stul 3000);
(3) posun jednoho svitidla podel profilu (vychozi uprostred x posunute doprava). Kazdy ve dvou pohledech (cely stul / detail osvetleni) + popisek.
Pouziti: api/venv/bin/python3 scripts/2026-10-08_led_rucne/render_obrazky.py [vystupni_adresar]    (STUL_API_OVERRIDE = kandidat; potrebuje node + playwright + internet pro three.js z jsdelivr)"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator(hermeticky=True)                      # falesne prostredi pro import stul_glb (bez DB)
VYST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("SP", "/tmp"), "led_rucne", "img")
os.makedirs(VYST, exist_ok=True)
KONF = [
    ("1_dve_svitidla_2400", dict(sirka=2400, led_delka=600, led_pocet=2), "Stůl 2400 mm: 2 svítidla LED 600 přidaná ručně (těsně vedle sebe, uprostřed)"),
    ("2_tri_svitidla_s_mezerami", dict(sirka=3000, led_delka=600, led_pocet=3, led_z1=-1000.0, led_z2=0.0, led_z3=900.0), "Stůl 3000 mm: 3 kratší svítidla (600) s mezerami, každé posunuté zvlášť"),
    ("3a_posun_vychozi", dict(sirka=2400, led_delka=600), "Stůl 2400 mm, výchozí stav: 1 svítidlo uprostřed"),
    ("3b_posun_doprava", dict(sirka=2400, led_delka=600, led_z1=700.0), "Totéž svítidlo posunuté podél profilu doprava (o 731 mm)"),
]
jobs, popisky = [], {}
for nazev, par, popis in KONF:
    r = S.sestav_stul(**par)
    h, glb = G.model_pro_parametry(r["parametry"])
    cesta = os.path.join(VYST, nazev + ".glb")
    open(cesta, "wb").write(glb)
    posun = G._META_CACHE.get(h)                                 # generator -> GLB (vycentrovani v X / Z, podlaha y = 0)
    lamp = [S._aabb(d) for d in r["dily"] if d["part_id"] in C.LED_PARTY]
    stred = [float((lamp[0][0][i] + lamp[-1][1][i]) / 2.0 + posun[i]) for i in range(3)]          # stred skupiny svitidel v souradnicich GLB (mm)
    print(nazev, "hash", h, "svitidel", C.pocet_svitidel(r), "polohy", r["led_info"]["polohy"], "stred GLB", [round(x) for x in stred], "problemy", [x["kod"] for x in r["problemy"]])
    for jm, az, el, vz, cil in (("celek", -38, 14, 0, None), ("detail", -64, 8, 3300, [stred[0], stred[1] - 300, 0.0])):          # pohled zepredu (X = hloubka dozadu, svitidla visi na zadnim ramu)
        out = os.path.join(VYST, "%s_%s.png" % (nazev, jm))
        jobs.append({"glb": cesta, "out": out, "az": az, "el": el, "w": 1400, "h": 900, "vzdal": vz, "cil": cil})
        popisky[out] = popis
jp = os.path.join(VYST, "jobs.json")
json.dump(jobs, open(jp, "w"))
subprocess.run(["node", os.path.join(os.path.dirname(HERE), "2026-10-08_oploceni", "render_glb.js"), jp], check=False)
try:                                                              # popisek do obrazku (Pillow, kdyz je)
    from PIL import Image, ImageDraw, ImageFont
    pismo = None
    for cesta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cesta):
            pismo = ImageFont.truetype(cesta, 30)
    for out, popis in popisky.items():
        im = Image.open(out).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width, 52], fill=(255, 255, 255))
        d.text((16, 9), popis, fill=(20, 30, 45), font=pismo)
        im.save(out)
except Exception as e:                                           # noqa: BLE001
    print("popisky nepridany:", e)
