#!/usr/bin/env python3
"""Výřez fotografie se souřadnicovou mřížkou (pixely původní fotografie) -> PNG (scratchpad). crop.py foto out x0 y0 x1 y1 [zoom=2] [krok=50]"""
import sys
from PIL import Image, ImageDraw
foto, out = sys.argv[1:3]; x0, y0, x1, y1 = map(int, sys.argv[3:7]); z = float(sys.argv[7]) if len(sys.argv) > 7 else 2; st = int(sys.argv[8]) if len(sys.argv) > 8 else 50
im = Image.open(foto).convert('RGB').crop((x0, y0, x1, y1)); im = im.resize((round(im.width * z), round(im.height * z)), Image.LANCZOS)
d = ImageDraw.Draw(im)
for x in range((x0 // st + 1) * st, x1, st):
    X = (x - x0) * z; d.line([(X, 0), (X, im.height)], fill=(0, 255, 255) if x % (st * 2) == 0 else (0, 120, 255), width=1); d.text((X + 2, 2), str(x), fill=(255, 255, 0))
for y in range((y0 // st + 1) * st, y1, st):
    Y = (y - y0) * z; d.line([(0, Y), (im.width, Y)], fill=(0, 255, 255) if y % (st * 2) == 0 else (0, 120, 255), width=1); d.text((2, Y + 2), str(y), fill=(255, 255, 0))
im.save(out); print(out, im.size)
