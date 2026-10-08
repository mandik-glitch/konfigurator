#!/usr/bin/env python3
"""Kontaktni archy fotogalerie s ID pro rucni trideni (bot16, 2026-10-07): realna fotka x render / produktovy snimek x fotka s viditelnym textem druhe znacky x duplicita.
Vysledek tridenicho kroku je seznam VYLOUCENE v webapp/js/realizace-foto.js (rendery se nesmi tvarit jako "realna fotografie", TEXT_FILTR pravidlo 7). Po nahrani nove fotky do galerie
(admin Fotogalerie) staci spustit znovu a zkontrolovat nova ID.
Pouziti: python3 kontaktni_arch.py <vystupni_slozka> [vestavby_dodavek|realizace_stolu]   (cte verejne API /api/gallery a soubory z webapp/, nic nezapisuje do repa)"""
import json, os, sys, urllib.request
from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
TAGY = [sys.argv[2]] if len(sys.argv) > 2 else ["vestavby_dodavek", "realizace_stolu"]
WEBAPP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "webapp")
os.makedirs(OUT, exist_ok=True)
try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
except Exception:
    FONT = None
for tag in TAGY:
    d = json.load(urllib.request.urlopen("https://autovestavby.logiman.cz/api/gallery?category=" + tag))
    im, per, cols, th = d["images"], 24, 6, (300, 200)
    for n in range(0, len(im), per):
        grp = im[n:n + per]
        sheet = Image.new("RGB", (cols * (th[0] + 6), ((len(grp) + cols - 1) // cols) * (th[1] + 6)), "#222")
        dr = ImageDraw.Draw(sheet)
        for k, i in enumerate(grp):
            try:
                x = Image.open(os.path.join(WEBAPP, i["url"].lstrip("/"))).convert("RGB"); x.thumbnail(th)
                px, py = (k % cols) * (th[0] + 6), (k // cols) * (th[1] + 6)
                sheet.paste(x, (px, py)); dr.rectangle([px, py, px + 70, py + 26], fill="#000"); dr.text((px + 4, py + 2), str(i["id"]), fill="#ffeb3b", font=FONT)
            except Exception as e:
                print("preskoceno", i["id"], e)
        fn = os.path.join(OUT, "%s_%d.png" % (tag, n // per + 1)); sheet.save(fn); print(fn)
