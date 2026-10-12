#!/usr/bin/env python3
"""Dvojice foto | model | rozdíl obrysů (šedě shoda, červeně jen model, modře jen fotografie) do scratchpadu – fotografie se do repa nekopíruje. Použití: dvojice_ts2.py foto.jpg render.png vystup.png"""
import sys
from PIL import Image
import numpy as np
foto, rend, out = sys.argv[1:4]
r = Image.open(rend).convert('RGB'); W, H = r.size
f = Image.open(foto).convert('RGB').resize((W, H), Image.LANCZOS)
rm = np.asarray(r).min(2) < 245; fm = np.asarray(f).min(2) < 236
d = np.full((H, W, 3), 255, np.uint8); d[rm & fm] = (200, 200, 200); d[rm & ~fm] = (255, 0, 0); d[~rm & fm] = (0, 0, 255)
o = Image.new('RGB', (3 * W, H), 'white'); o.paste(f, (0, 0)); o.paste(r, (W, 0)); o.paste(Image.fromarray(d), (2 * W, 0)); o.save(out)
print(out, 'IoU', round(float((rm & fm).sum() / (rm | fm).sum()), 4))
