#!/usr/bin/env python3
"""Rozdíl obrysů: rozdil.py foto.jpg maska_modelu.bin maska.json out.png [sirka=900]
Barvy přes fotografii: zelená = oba, červená = jen fotografie (model chybí), modrá = jen model (přebývá). Výstup do scratchpadu."""
import sys, json, struct
import numpy as np
from PIL import Image, ImageDraw
foto, mb, mj, out = sys.argv[1:5]; PW = int(sys.argv[5]) if len(sys.argv) > 5 else 900
f = Image.open(foto).convert('RGB'); b = open(mb, 'rb').read(); w, h = struct.unpack('<II', b[:8]); m = np.frombuffer(b[8:], dtype=np.uint8).reshape(h, w)
P = json.load(open(mj))['polygon']; sc = w / f.width
pm = Image.new('L', (w, h), 0); ImageDraw.Draw(pm).polygon([(x * sc, y * sc) for x, y in P], fill=1); pm = np.asarray(pm)
col = np.zeros((h, w, 3), np.uint8); both = (m > 0) & (pm > 0); only_f = (pm > 0) & (m == 0); only_m = (m > 0) & (pm == 0)
col[both] = (0, 200, 0); col[only_f] = (255, 0, 0); col[only_m] = (0, 80, 255)
ov = Image.blend(f.resize((w, h)), Image.fromarray(col), 0.55)
ys, xs = np.where((m > 0) | (pm > 0)); box = (max(xs.min() - 15, 0), max(ys.min() - 15, 0), min(xs.max() + 15, w), min(ys.max() + 15, h))
ov = ov.crop(box); ov = ov.resize((PW, round(ov.height * PW / ov.width)), Image.NEAREST); ov.save(out)
print('IoU', both.sum() / ((m > 0) | (pm > 0)).sum())
