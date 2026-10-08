#!/usr/bin/env python3
"""Obrazky PRED / PO razitka (ochranne logo LOGIMAN.CZ na profilech) pro Roberta (bot8, 2026-10-08; WORKFLOW pravidlo 61): stejne konfigurace bez razitek (`razitka=False`) a s razitky (nove vychozi),
stejny pohled. GLB z generatoru -> three.js (scripts/2026-10-08_oploceni/render_glb.js) -> PNG s popiskem. Pouziti:
  api/venv/bin/python3 scripts/2026-10-08_razitka_generatory/render_obrazky.py [vystupni_adresar]    (STUL_API_OVERRIDE = kandidat; potrebuje node + playwright + internet pro three.js z jsdelivr)"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "2026-10-08_led_rucne"))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator(hermeticky=True)                      # falesne prostredi pro import stul_glb (bez DB)
import stul_razitka as RZ  # noqa: E402

VYST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("SP", "/tmp"), "razitka", "img")
os.makedirs(VYST, exist_ok=True)
KONF = [
    ("1_stul_system30", dict(system=30), "systém 30, výchozí stůl", (-38, 14)),
    ("2_stul_system45_velky", dict(system=45, sirka=3000, hloubka=1400, police=2), "systém 45, 3000 × 1400 mm, 2 police", (-38, 14)),
    ("3_stul_sse41", dict(system=41, sirka=2400), "SSE (systém 41), 2400 mm", (-38, 14)),
]
jobs, popisky = [], {}
for nazev, par, popis, (az, el) in KONF:
    r = S.sestav_stul(**par)
    h = G.kanonicky_hash(r["parametry"])
    holy = G.model_pro_parametry(r["parametry"], razitka=False)[1]
    s = G.model_pro_parametry(r["parametry"])[1]
    posun = [float(x) for x in G._META_CACHE[h]]
    rz = RZ.razitka(r, h)
    print(nazev, "hash", h, "razitek", len(rz), "GLB bez / s [B]", len(holy), len(s))
    for stav, data, titulek in (("pred", holy, "PŘED – bez razítek"), ("po", s, "PO – s razítky")):
        cesta = os.path.join(VYST, f"{nazev}_{stav}.glb")
        open(cesta, "wb").write(data)
        out = os.path.join(VYST, f"{nazev}_{stav}_celek.png")
        jobs.append({"glb": cesta, "out": out, "az": az, "el": el, "w": 1400, "h": 900, "vzdal": 0, "cil": None})
        popisky[out] = f"{titulek} | {popis}"
    for k in (0, len(rz) // 2):                                  # detail dvou razitek (kamera kolmo k jejich stene, trochu shora)
        if k >= len(rz):
            continue
        z = rz[k]
        Rm = S.kvat_na_matici(z["logo"]["q"])
        n = Rm @ [0.0, 0.0, 1.0]
        pos = [float(z["logo"]["pos"][i]) + posun[i] for i in range(3)]
        a = math.degrees(math.atan2(n[0], n[2]))
        e = max(8.0, min(35.0, math.degrees(math.asin(max(-1.0, min(1.0, n[1])))) + 14.0))
        for stav, titulek in (("pred", "PŘED"), ("po", "PO")):
            out = os.path.join(VYST, f"{nazev}_{stav}_detail{k + 1}.png")
            jobs.append({"glb": os.path.join(VYST, f"{nazev}_{stav}.glb"), "out": out, "az": a, "el": e, "w": 1400, "h": 900, "vzdal": 650, "cil": pos})
            popisky[out] = f"{titulek} | detail profilu, {popis}"
jp = os.path.join(VYST, "jobs.json")
json.dump(jobs, open(jp, "w"))
subprocess.run(["node", os.path.join(os.path.dirname(HERE), "2026-10-08_oploceni", "render_glb.js"), jp], check=False)
try:                                                              # popisek do obrazku (Pillow, kdyz je)
    from PIL import Image, ImageDraw, ImageFont
    pismo = None
    for cesta in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(cesta):
            pismo = ImageFont.truetype(cesta, 28)
    for out, popis in popisky.items():
        im = Image.open(out).convert("RGB")
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, im.width, 52], fill=(255, 255, 255))
        d.text((16, 9), popis, fill=(20, 30, 45), font=pismo)
        im.save(out)
except Exception as e:                                           # noqa: BLE001
    print("popisky nepridany:", e)
