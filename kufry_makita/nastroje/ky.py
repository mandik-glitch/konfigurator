#!/usr/bin/env python3
"""Vertikální roztažení fotografie (kompenzace anizotropního měřítka zdrojového obrázku): ky.py foto.jpg vystup.png ky   (výška / ky). Výstup jen do scratchpadu."""
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB'); ky = float(sys.argv[3])
im.resize((im.width, round(im.height / ky)), Image.LANCZOS).save(sys.argv[2])
