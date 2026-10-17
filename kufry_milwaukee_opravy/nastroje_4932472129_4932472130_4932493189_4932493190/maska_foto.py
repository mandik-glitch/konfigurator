#!/usr/bin/env python3
"""Maska produktu z fotografie (jas < 245, jako v kontrole John v6; bez vyplňování děr) → raw .bin (uint32 w, uint32 h, w*h bajtů 0/1) pro fit_kamera.mjs.
Fotografie se jen ČTE (scratchpad), do repa se nic neukládá. Použití: maska_foto.py foto.jpg maska.bin [rozlišení=400]"""
import sys, struct
from PIL import Image
import numpy as np
src, out = sys.argv[1], sys.argv[2]; L = int(sys.argv[3]) if len(sys.argv) > 3 else 400
im = Image.open(src).convert('L'); m = (np.asarray(im) < 245).astype(np.float32)
k = im.width // L; m = m[:L * k, :L * k].reshape(L, k, L, k).mean(axis=(1, 3)) > 0.5
open(out, 'wb').write(struct.pack('<II', L, L) + m.astype('uint8').tobytes())
