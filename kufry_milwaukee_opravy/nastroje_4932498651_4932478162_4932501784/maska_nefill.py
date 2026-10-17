#!/usr/bin/env python3
"""Maska produktu z fotografie na bílém pozadí BEZ vyplnění děr (otvor madla zůstane průhledný). Výstup stejný formát jako foto_maska.py.
Použití: maska_nefill.py foto.jpg maska.bin [delsi_strana=600] [prah=236]"""
import sys, struct
from PIL import Image, ImageFilter
import numpy as np
src, out = sys.argv[1], sys.argv[2]
L = int(sys.argv[3]) if len(sys.argv) > 3 else 600
thr = int(sys.argv[4]) if len(sys.argv) > 4 else 236
im = Image.open(src).convert('RGB')
sc = L / max(im.size); im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
a = np.asarray(im).astype(int)
fg = (a.min(axis=2) < thr)
m = Image.fromarray((fg * 255).astype('uint8')).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
mask = (np.asarray(m) > 0).astype('uint8')
with open(out, 'wb') as f:
    f.write(struct.pack('<II', mask.shape[1], mask.shape[0])); f.write(mask.tobytes())
print(out, mask.shape[1], mask.shape[0], 'pokrytí', round(mask.mean(), 3))
