#!/usr/bin/env python3
"""Průsvitný překryv: fotografie (jen k měření, mimo repo) + náš render ve stejném rámu (render/srovnej.mjs --reuse) → PNG do scratchpadu.
Použití: prekryv.py foto.jpg render.png vystup.png [alfa=0.55] [x0,y0,x1,y1 výřez ve zlomcích 0..1]"""
import sys, numpy as np
from PIL import Image
f = Image.open(sys.argv[1]).convert('RGB'); r = Image.open(sys.argv[2]).convert('RGB').resize(f.size)
a = float(sys.argv[4]) if len(sys.argv) > 4 else 0.55
fa = np.asarray(f).astype(float); ra = np.asarray(r).astype(float)
m = (ra.min(axis=2) < 238)[..., None]
o = np.where(m, fa * (1 - a) + ra * a, fa).astype('uint8')
im = Image.fromarray(o)
if len(sys.argv) > 5:
    x0, y0, x1, y1 = [float(v) for v in sys.argv[5].split(',')]; im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
sc = min(1600 / im.width, 1600 / im.height); im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS); im.save(sys.argv[3])
