#!/usr/bin/env python3
"""cmp.py foto render out x0 y0 x1 y1 scale  -> foto | model | rozdil-obrys vedle sebe (výřez ve px původní fotky 1200)"""
import sys
from PIL import Image, ImageFilter, ImageChops
import numpy as np
foto, rnd, out, x0, y0, x1, y1, sc = sys.argv[1:9]
x0, y0, x1, y1 = map(int, (x0, y0, x1, y1)); sc = float(sc)
f = Image.open(foto).convert('RGB').resize((1200, 1200)); r = Image.open(rnd).convert('RGB').resize((1200, 1200))
fc, rc = f.crop((x0, y0, x1, y1)), r.crop((x0, y0, x1, y1))
rm = Image.fromarray(((np.asarray(r).astype(int).min(axis=2) < 236) * 255).astype('uint8'))
edge = ImageChops.subtract(rm.filter(ImageFilter.MaxFilter(3)), rm.filter(ImageFilter.MinFilter(3))).crop((x0, y0, x1, y1))
ov = fc.copy(); ov.paste((0, 220, 255), mask=edge)
W, H = int((x1 - x0) * sc), int((y1 - y0) * sc)
c = Image.new('RGB', (W * 3, H), 'white')
for i, im in enumerate((fc, rc, ov)): c.paste(im.resize((W, H), Image.LANCZOS), (i * W, 0))
c.save(out)
