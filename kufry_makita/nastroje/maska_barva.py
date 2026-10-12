#!/usr/bin/env python3
"""Maska výrobku podle barvy (tyrkys + černá), ne podle bílého pozadí – pro fotografie se šipkami/kótami/popisky. Výstup jako foto_maska.py (uint32 w, uint32 h, w*h bajtů 0/1).
Použití: maska_barva.py foto.jpg maska.bin [delsi_strana=320] [vse|tyrkys]   (tyrkys = jen tyrkysové plochy, bez černého madla a západek)"""
import sys, struct
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
src, out = sys.argv[1], sys.argv[2]; L = int(sys.argv[3]) if len(sys.argv) > 3 else 320
im = Image.open(src).convert('RGB'); sc = L / max(im.size); im = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS)
a = np.asarray(im).astype(int)
teal = (a[:, :, 1] - a[:, :, 0] > 25) & (a[:, :, 2] - a[:, :, 0] > 25)
dark = a.max(axis=2) < 80
mode = sys.argv[4] if len(sys.argv) > 4 else "vse"
fg = teal if mode == "tyrkys" else (teal | dark)
m = Image.fromarray((fg * 255).astype('uint8')).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
pad = Image.new('L', (m.width + 4, m.height + 4), 0); pad.paste(m, (2, 2)); ImageDraw.floodfill(pad, (0, 0), 128)
arr = np.asarray(pad)[2:-2, 2:-2]; mask = (arr != 128).astype('uint8')
open(out, 'wb').write(struct.pack('<II', mask.shape[1], mask.shape[0]) + mask.tobytes())
Image.fromarray(mask * 255).save(out + '.png'); print(out, mask.shape[1], mask.shape[0], 'pokrytí', round(mask.mean(), 3))
