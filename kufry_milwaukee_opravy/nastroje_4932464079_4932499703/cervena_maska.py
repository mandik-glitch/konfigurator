#!/usr/bin/env python3
"""Červená maska fotografie v daném rozlišení -> raw bin (uint32 w, uint32 h, w*h bajtů 0/1). cervena_maska.py foto out velikost"""
import sys, struct, numpy as np
from PIL import Image
im = Image.open(sys.argv[1]).convert('RGB'); L = int(sys.argv[3]); im = im.resize((L, L), Image.LANCZOS)
a = np.asarray(im).astype(int); R, G, B = a[..., 0], a[..., 1], a[..., 2]
m = ((R > 130) & (G < 95) & (B < 95) & (R - G > 60)).astype('uint8')
open(sys.argv[2], 'wb').write(struct.pack('<II', L, L) + m.tobytes())
