#!/usr/bin/env python3 -I
"""Ruční/poloautomatické landmarky: fotografie (L137214, jen čtena ze scratchpadu) vs. náš čelní render (kufriky_cloud/srovnani/<sku>/celo.png, oříznutý na obrys a roztažený na rozměr fotografie).
Měří stejnými prahy na obou obrázcích: logo (bílé), okno držadla (bílé, nahoře uprostřed), černé západky a rám držadla (tmavé pixely), obrys. Výstup landmarky.json (jen čísla, žádné pixely fotografie).
Použití: landmarky_2284143.py <foto.jpg> <sku>"""
import sys, json, os
import numpy as np
from PIL import Image
foto, sku = sys.argv[1:3]
here = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(here, '../../kufriky_cloud/srovnani', sku)
F = np.asarray(Image.open(foto).convert('RGB')).astype(int)
R = np.asarray(Image.open(os.path.join(out, 'celo.png')).convert('RGB')).astype(int)
def bbox(m, x0=0, x1=None, y0=0, y1=None):
    s = m[y0:y1, x0:x1]; ys, xs = np.where(s)
    return None if not len(xs) else [int(xs.min() + x0), int(xs.max() + x0), int(ys.min() + y0), int(ys.max() + y0)]
white = lambda a: a.min(axis=2) > 200
dark = lambda a: a.max(axis=2) < 80
res = {}
for nm, fn, args in [
    ('logo', white, (100, 1100, 370, 540)),
    ('okno_drzadla', white, (430, 780, 60, 135)),
    ('zapadka_leva', dark, (120, 330, 0, 100)),
    ('zapadka_prava', dark, (870, 1080, 0, 100)),
    ('ram_drzadla', dark, (360, 840, 0, 160)),
]:
    a = bbox(fn(F), *args); b = bbox(fn(R), *args)
    res[nm] = {'foto_px': a, 'model_px': b, 'rozdil_px': None if not (a and b) else [b[i] - a[i] for i in range(4)], 'format': 'x0,x1,y0,y1 v pixelech fotografie 1200x940'}
sil = lambda a: a.min(axis=2) < 235
bf, bm = sil(F), sil(R)
res['obrys_IoU'] = round(float((bf & bm).sum() / (bf | bm).sum()), 4)
# odchylka obrysu po řádcích (levý/pravý okraj) – maximum a medián v px
dl, dr = [], []
for y in range(0, 939, 3):
    xf, xm = np.where(bf[y])[0], np.where(bm[y])[0]
    if len(xf) and len(xm): dl.append(int(xm.min() - xf.min())); dr.append(int(xm.max() - xf.max()))
res['obrys_okraje_px'] = {'leve_max_abs': int(np.abs(dl).max()), 'prave_max_abs': int(np.abs(dr).max()), 'leve_median_abs': float(np.median(np.abs(dl))), 'prave_median_abs': float(np.median(np.abs(dr)))}
json.dump(res, open(os.path.join(out, 'landmarky.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps(res, indent=1, ensure_ascii=False))
