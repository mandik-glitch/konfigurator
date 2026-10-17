#!/usr/bin/env python3
"""Výřez překryvu: fotografie + obrys modelu (cyan, z renderu na bílém pozadí) + volitelně hrany renderu; vedle sebe foto | model | překryv.
ovl.py foto render out x0 y0 x1 y1 [zoom=2] [krok=50]. Jen scratchpad; fotografie se jen čte."""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageChops, ImageDraw
foto, rnd, out = sys.argv[1:4]; x0, y0, x1, y1 = map(int, sys.argv[4:8]); z = float(sys.argv[8]) if len(sys.argv) > 8 else 2; st = int(sys.argv[9]) if len(sys.argv) > 9 else 50
f = Image.open(foto).convert('RGB'); r = Image.open(rnd).convert('RGB').resize(f.size, Image.LANCZOS)
rm = Image.fromarray(((np.asarray(r).astype(int).min(axis=2) < 244) * 255).astype('uint8'))
fm = Image.fromarray(((np.asarray(f).astype(int).min(axis=2) < 240) * 255).astype('uint8')).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
def edge(m): return ImageChops.subtract(m.filter(ImageFilter.MaxFilter(3)), m.filter(ImageFilter.MinFilter(3)))
ov = f.copy(); ov.paste((255, 0, 0), mask=edge(fm)); ov.paste((0, 200, 255), mask=edge(rm))
# vnitřní hrany modelu (gradient renderu) ve žluté
g = np.asarray(r.convert('L')).astype(float); gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1])); gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
ed = ((gx + gy) > 14) & (np.asarray(rm) > 0)
ovn = np.asarray(ov).copy(); ovn[ed] = (255, 230, 0); ov = Image.fromarray(ovn)
box = (x0, y0, x1, y1)
def prep(im):
    c = im.crop(box); c = c.resize((round(c.width * z), round(c.height * z)), Image.LANCZOS); d = ImageDraw.Draw(c)
    for x in range((x0 // st + 1) * st, x1, st):
        X = (x - x0) * z; d.line([(X, 0), (X, 6)], fill=(255, 255, 0)); d.text((X + 2, 2), str(x), fill=(255, 255, 0))
    for y in range((y0 // st + 1) * st, y1, st):
        Y = (y - y0) * z; d.line([(0, Y), (6, Y)], fill=(255, 255, 0)); d.text((8, Y - 4), str(y), fill=(255, 255, 0))
    return c
A, B, C = prep(f), prep(r), prep(ov)
W = Image.new('RGB', (A.width * 3 + 8, A.height), 'white'); W.paste(A, (0, 0)); W.paste(B, (A.width + 4, 0)); W.paste(C, (2 * A.width + 8, 0)); W.save(out); print(out, W.size)
