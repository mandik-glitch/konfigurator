#!/usr/bin/env python3
"""Dvojice: fotografie | náš render | překryv (obrys renderu přes fotografii). Výstup jen do zadaného (scratchpad) souboru.
Použití: porovnej.py foto.jpg render.png vystup.png [vyska=700]"""
import sys
from PIL import Image, ImageFilter, ImageChops, ImageDraw
foto, rnd, out = sys.argv[1:4]; H = int(sys.argv[4]) if len(sys.argv) > 4 else 700
f = Image.open(foto).convert('RGB'); r = Image.open(rnd).convert('RGB')
r = r.resize((round(f.width * H / f.height) if False else round(r.width * H / r.height), H), Image.LANCZOS)
f = f.resize((round(f.width * H / f.height), H), Image.LANCZOS)
# obrys renderu: neprázdné (ne bílé) pixely -> hrana
rm = Image.fromarray(((__import__('numpy').asarray(r).astype(int).min(axis=2) < 236) * 255).astype('uint8')).resize(f.size, Image.NEAREST)
edge = ImageChops.subtract(rm.filter(ImageFilter.MaxFilter(3)), rm.filter(ImageFilter.MinFilter(3)))
ov = f.copy(); ov.paste((0, 200, 255), mask=edge)
W = f.width + r.width + ov.width
canvas = Image.new('RGB', (W, H + 18), 'white'); d = ImageDraw.Draw(canvas)
canvas.paste(f, (0, 18)); canvas.paste(r, (f.width, 18)); canvas.paste(ov, (f.width + r.width, 18))
d.text((4, 2), 'fotografie (jen k mereni, neni v repu)', fill='black'); d.text((f.width + 4, 2), 'nas model', fill='black'); d.text((f.width + r.width + 4, 2), 'prekryv obrysu modelu', fill='black')
canvas.save(out); print(out, canvas.size)
