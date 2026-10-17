#!/usr/bin/env python3
"""Detail: výřez foto | render | překryv (50 %) ve stejném záběru (render musí mít rozměr fotografie). detail.py foto render out x0 y0 x1 y1 [zoom=1.5]"""
import sys
from PIL import Image, ImageDraw
foto, rnd, out = sys.argv[1:4]; x0, y0, x1, y1 = map(int, sys.argv[4:8]); z = float(sys.argv[8]) if len(sys.argv) > 8 else 1.5
f = Image.open(foto).convert('RGB'); r = Image.open(rnd).convert('RGB').resize(f.size, Image.LANCZOS)
b = Image.blend(f, r, 0.5)
box = (x0, y0, x1, y1)
parts = [im.crop(box).resize((round((x1 - x0) * z), round((y1 - y0) * z)), Image.LANCZOS) for im in (f, r, b)]
W = sum(p.width for p in parts) + 8
c = Image.new('RGB', (W, parts[0].height), 'white'); x = 0
for p in parts:
    c.paste(p, (x, 0)); x += p.width + 4
d = ImageDraw.Draw(c)
for k, p in enumerate(parts):
    ox = k * (parts[0].width + 4)
    for gx in range((x0 // 50 + 1) * 50, x1, 50): d.line([(ox + (gx - x0) * z, 0), (ox + (gx - x0) * z, 6)], fill=(0, 160, 255)); d.text((ox + (gx - x0) * z + 2, 6), str(gx), fill=(0, 120, 255))
    for gy in range((y0 // 50 + 1) * 50, y1, 50): d.line([(ox, (gy - y0) * z), (ox + 6, (gy - y0) * z)], fill=(0, 160, 255)); d.text((ox + 8, (gy - y0) * z - 5), str(gy), fill=(0, 120, 255))
c.save(out); print(out, c.size)
