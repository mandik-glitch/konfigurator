#!/usr/bin/env python3
"""IoU červených prvků (rukojeť, západky, štítek, kroužek) mezi fotografií a renderem při téže kameře. cervena_iou.py foto render [oblast x0,y0,x1,y1 v px fotografie]
Práh: r>130, g<95, b<95, r-g>60 (stejný pro obě). Fotografie se jen čte. Vypíše JSON."""
import sys, json, numpy as np
from PIL import Image
f = Image.open(sys.argv[1]).convert('RGB'); r = Image.open(sys.argv[2]).convert('RGB').resize(f.size, Image.LANCZOS)
def red(im):
    a = np.asarray(im).astype(int); R, G, B = a[..., 0], a[..., 1], a[..., 2]
    return (R > 130) & (G < 95) & (B < 95) & (R - G > 60)
mf, mr = red(f), red(r)
if len(sys.argv) > 3:
    x0, y0, x1, y1 = map(int, sys.argv[3].split(',')); m = np.zeros_like(mf); m[y0:y1, x0:x1] = True; mf &= m; mr &= m
I = (mf & mr).sum(); U = (mf | mr).sum()
print(json.dumps({'iou_cervena': round(float(I / U), 4) if U else 0, 'px_foto': int(mf.sum()), 'px_model': int(mr.sum())}))
