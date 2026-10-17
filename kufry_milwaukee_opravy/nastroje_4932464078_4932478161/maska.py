#!/usr/bin/env python3
"""Maska produktu z fotografie na bílém pozadí -> raw .bin (uint32 w, uint32 h, w*h bajtů 0/1). BEZ vyplnění děr (okno madla, mezera za bočním madlem zůstanou prázdné),
volitelně s vyplněním (--vyplnit) jako ve sdíleném foto_maska.py (kvůli srovnání se starými IoU z kontroly). maska.py foto out.bin [delsi_strana=320] [prah=236] [--vyplnit]"""
import sys, struct
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
args = [a for a in sys.argv[1:] if not a.startswith('--')]; fill = '--vyplnit' in sys.argv
src, out = args[0], args[1]
L = int(args[2]) if len(args) > 2 else 320
thr = int(args[3]) if len(args) > 3 else 236
im = Image.open(src).convert('RGB')
sc = L / max(im.size); im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
a = np.asarray(im).astype(int)
fg = (a.min(axis=2) < thr)
m = Image.fromarray((fg * 255).astype('uint8'))
if fill:
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    pad = Image.new('L', (m.width + 4, m.height + 4), 0); pad.paste(m, (2, 2))
    ImageDraw.floodfill(pad, (0, 0), 128)
    arr = np.asarray(pad)[2:-2, 2:-2]; mask = (arr != 128).astype('uint8')
else:
    mask = (np.asarray(m) > 0).astype('uint8')
with open(out, 'wb') as f:
    f.write(struct.pack('<II', mask.shape[1], mask.shape[0])); f.write(mask.tobytes())
Image.fromarray(mask * 255).save(out + '.png')
