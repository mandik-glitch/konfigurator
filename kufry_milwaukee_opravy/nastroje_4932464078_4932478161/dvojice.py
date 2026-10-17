#!/usr/bin/env python3
"""foto | model | překryv (obrys modelu cyan přes foto, obrys fota červeně) -> výstup jen do scratchpadu. dvojice.py foto render out [vyska] [maska.bin]"""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageChops, ImageDraw
foto, rnd, out = sys.argv[1:4]; H = int(sys.argv[4]) if len(sys.argv) > 4 else 640
f = Image.open(foto).convert('RGB'); r = Image.open(rnd).convert('RGB')
f = f.resize((round(f.width * H / f.height), H), Image.LANCZOS); r = r.resize((round(r.width * H / r.height), H), Image.LANCZOS)
rm = Image.fromarray(((np.asarray(r).astype(int).min(axis=2) < 236) * 255).astype('uint8')).resize(f.size, Image.NEAREST)
fm = Image.fromarray(((np.asarray(f).astype(int).min(axis=2) < 236) * 255).astype('uint8'))
fm = fm.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
def edge(m): return ImageChops.subtract(m.filter(ImageFilter.MaxFilter(3)), m.filter(ImageFilter.MinFilter(3)))
ov = f.copy(); ov.paste((255, 0, 0), mask=edge(fm)); ov.paste((0, 200, 255), mask=edge(rm))
canvas = Image.new('RGB', (f.width + r.width + ov.width, H + 16), 'white'); d = ImageDraw.Draw(canvas)
canvas.paste(f, (0, 16)); canvas.paste(r, (f.width, 16)); canvas.paste(ov, (f.width + r.width, 16))
d.text((4, 2), 'foto (jen k mereni)', fill='black'); d.text((f.width + 4, 2), 'nas model', fill='black'); d.text((f.width + r.width + 4, 2), 'prekryv: cervene = foto, cyan = model', fill='black')
canvas.save(out)
