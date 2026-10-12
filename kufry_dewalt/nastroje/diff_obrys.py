#!/usr/bin/env python3
"""Rozdílový obrázek obrysů: modrá = jen model, červená = jen fotografie, šedá = shoda. Použití: diff_obrys.py foto_orez.png render_orez.png vystup.png [vyska=900]"""
import sys, numpy as np
from PIL import Image
f = Image.open(sys.argv[1]).convert('RGB'); r = Image.open(sys.argv[2]).convert('RGB'); H = int(sys.argv[4]) if len(sys.argv) > 4 else 900
W = round(f.width * H / f.height); f = f.resize((W, H)); r = r.resize((W, H))
from PIL import ImageDraw
def fill(m):
    p = Image.new('L', (m.shape[1] + 4, m.shape[0] + 4), 0); p.paste(Image.fromarray((m * 255).astype('uint8')), (2, 2)); ImageDraw.floodfill(p, (0, 0), 128); return np.asarray(p)[2:-2, 2:-2] != 128
fm = fill(np.asarray(f).astype(int).min(axis=2) < 235); rm = fill(np.asarray(r).astype(int).min(axis=2) < 238)
o = np.full((H, W, 3), 255, 'uint8'); o[fm & rm] = (190, 190, 190); o[fm & ~rm] = (230, 40, 40); o[~fm & rm] = (40, 60, 230)
Image.fromarray(o).save(sys.argv[3]); print('IoU %.4f' % ((fm & rm).sum() / (fm | rm).sum()))
