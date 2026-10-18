#!/usr/bin/env python3
"""Nakreslí polygon masky na fotografii (jen do scratchpadu): polygon_nahled.py foto.jpg maska.json out.png [x0 y0 x1 y1 scale]"""
import sys, json
from PIL import Image, ImageDraw
im = Image.open(sys.argv[1]).convert('RGB'); P = json.load(open(sys.argv[2]))['polygon']
x0, y0, x1, y1, sc = 0, 0, im.width, im.height, 1.0
if len(sys.argv) > 8: x0, y0, x1, y1 = map(int, sys.argv[4:8]); sc = float(sys.argv[8])
im = im.crop((x0, y0, x1, y1)); im = im.resize((int(im.width * sc), int(im.height * sc)))
d = ImageDraw.Draw(im); pts = [((x - x0) * sc, (y - y0) * sc) for x, y in P]
d.line(pts + [pts[0]], fill=(255, 0, 0), width=2)
for i, p in enumerate(pts): d.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], outline=(255, 255, 0))
im.save(sys.argv[3])
