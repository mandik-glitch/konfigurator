#!/usr/bin/env python3
"""rek2.py foto render kamera.json osa hodnota u0 u1 v0 v1 pxmm out [mrizka]: rektifikace fotky i renderu modelu na stejnou rovinu, vedle sebe + rozdíl"""
import sys, subprocess, os
from PIL import Image
here = os.path.dirname(os.path.abspath(__file__))
foto, rnd, cam, osa, hv, u0, u1, v0, v1, pxmm, out = sys.argv[1:12]
g = sys.argv[12] if len(sys.argv) > 12 else '20'
a, b = out + '_a.png', out + '_b.png'
subprocess.run(['python3', here + '/rektif.py', foto, cam, osa, hv, u0, u1, v0, v1, pxmm, a, g], check=True, stdout=subprocess.DEVNULL)
subprocess.run(['python3', here + '/rektif.py', rnd, cam, osa, hv, u0, u1, v0, v1, pxmm, b, g], check=True, stdout=subprocess.DEVNULL)
A, B = Image.open(a), Image.open(b)
c = Image.new('RGB', (A.width * 2, A.height)); c.paste(A, (0, 0)); c.paste(B, (A.width, 0)); c.save(out)
os.remove(a); os.remove(b); print(out, c.size)
