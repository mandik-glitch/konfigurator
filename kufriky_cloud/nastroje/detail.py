#!/usr/bin/env python3
"""Zvětšený detail dvojice (fotografie | model) – stejný výřez z obou panelů. Použití: detail.py dvojice.png x0 y0 x1 y1 [zvetseni=2] vystup.png
Souřadnice jsou v prostoru JEDNOHO panelu (panel = šířka dvojice / 3)."""
import sys
from PIL import Image
src = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6]); k = float(sys.argv[6]) if len(sys.argv) > 6 else 2; out = sys.argv[7] if len(sys.argv) > 7 else 'detail.png'
im = Image.open(src).convert('RGB'); pw = im.width // 3
y0 += 18; y1 += 18  # titulek
a = im.crop((x0, y0, x1, y1)); b = im.crop((pw + x0, y0, pw + x1, y1))
a = a.resize((int(a.width * k), int(a.height * k)), Image.LANCZOS); b = b.resize(a.size, Image.LANCZOS)
c = Image.new('RGB', (a.width * 2 + 6, a.height), 'white'); c.paste(a, (0, 0)); c.paste(b, (a.width + 6, 0)); c.save(out); print(out, c.size)
