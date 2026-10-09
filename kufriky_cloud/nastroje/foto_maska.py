#!/usr/bin/env python3
"""Maska produktu z fotografie na bílém pozadí -> raw .bin (uint32 w, uint32 h, w*h bajtů 0/1) pro render/fit.mjs.
Fotografie se jen ČTE (z kufriky_john/fotky/ nebo ze scratchpadu), nic se neukládá do repa.
Použití: foto_maska.py foto.jpg maska.bin [delsi_strana=320] [prah=236] [--ignore-pravy-okraj px]"""
import sys, struct
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
src, out = sys.argv[1], sys.argv[2]
L = int(sys.argv[3]) if len(sys.argv) > 3 else 320
thr = int(sys.argv[4]) if len(sys.argv) > 4 else 236
im = Image.open(src).convert('RGB')
sc = L / max(im.size); im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
a = np.asarray(im).astype(int)
fg = (a.min(axis=2) < thr)
m = Image.fromarray((fg * 255).astype('uint8'))
m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))        # uzavření drobných mezer
# vyplnění děr: zaplavení pozadí od okraje
pad = Image.new('L', (m.width + 4, m.height + 4), 0); pad.paste(m, (2, 2))          # rámeček 0 kolem: pozadí zůstane spojité
ImageDraw.floodfill(pad, (0, 0), 128)
arr = np.asarray(pad)[2:-2, 2:-2]; mask = (arr != 128).astype('uint8')
with open(out, 'wb') as f:
    f.write(struct.pack('<II', mask.shape[1], mask.shape[0])); f.write(mask.tobytes())
Image.fromarray(mask * 255).save(out + '.png')
print(out, mask.shape[1], mask.shape[0], 'pokrytí', round(mask.mean(), 3))
