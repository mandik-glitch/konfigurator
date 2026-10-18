#!/usr/bin/env python3
"""Dvojice foto | model | překryv (do scratchpadu, NE do repa). Použití: dvojice.py foto.jpg render.png out.png [sirka_panelu=560] [maska.json]
Výřez = obálka polygonu masky + okraj 40 px. Překryv: fotografie 50 % + model 50 %; polygon masky se kreslí červeně na fotografii a na překryv."""
import sys, json
from PIL import Image, ImageDraw
foto, rend, out = sys.argv[1:4]; PW = int(sys.argv[4]) if len(sys.argv) > 4 else 560
f = Image.open(foto).convert('RGB'); r = Image.open(rend).convert('RGB').resize(f.size, Image.LANCZOS)
box = (0, 0, f.width, f.height); P = None
if len(sys.argv) > 5:
    P = json.load(open(sys.argv[5]))['polygon']; xs = [p[0] for p in P]; ys = [p[1] for p in P]
    box = (max(0, min(xs) - 40), max(0, min(ys) - 40), min(f.width, max(xs) + 40), min(f.height, max(ys) + 40))
import os
if os.environ.get('CROP'): box = tuple(int(v) for v in os.environ['CROP'].split(','))
f = f.crop(box); r = r.crop(box); sc = PW / f.width; H = round(f.height * sc)
fs = f.resize((PW, H), Image.LANCZOS); rs = r.resize((PW, H), Image.LANCZOS); ov = Image.blend(fs, rs, 0.5)
if P:
    pts = [((x - box[0]) * sc, (y - box[1]) * sc) for x, y in P]
    for im in (fs, ov): ImageDraw.Draw(im).line(pts + [pts[0]], fill=(255, 0, 0), width=2)
W = Image.new('RGB', (PW * 3 + 8, H), (255, 255, 255)); W.paste(fs, (0, 0)); W.paste(rs, (PW + 4, 0)); W.paste(ov, (2 * PW + 8, 0)); W.save(out)
