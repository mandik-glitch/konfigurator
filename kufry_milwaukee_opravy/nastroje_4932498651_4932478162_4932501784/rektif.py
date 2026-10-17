#!/usr/bin/env python3
"""Rektifikace fotografie na rovinu modelu při uložené kameře (jen do zadaného výstupu, nic do repa).
Použití: rektif.py foto.jpg kamera.json osa(X|Y|Z) hodnota u0 u1 v0 v1 pxmm out.png [mrizka_mm=20]
Rovina X=h: u=Y (doprava při pohledu z +X: -Y..), v=Z ; rovina Y=h: u=X, v=Z ; rovina Z=h: u=Y, v=X (nahoru = +X).
Vykreslí mřížku po mm (popisky = mm)."""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw
foto, camf, osa, hv, u0, u1, v0, v1, pxmm, out = sys.argv[1:11]
grid = float(sys.argv[11]) if len(sys.argv) > 11 else 20
hv, u0, u1, v0, v1, pxmm = map(float, (hv, u0, u1, v0, v1, pxmm))
j = json.load(open(camf)); c = j.get('kamera', j)
W, H = c.get('w', 1200), c.get('h', 1200)
sx = c['shiftX'] if 'shiftX' in c else (c['cx'] - W / 2) / W
sy = c['shiftY'] if 'shiftY' in c else (c['cy'] - H / 2) / H
az, el, dist, fov, roll = [math.radians(c[k]) if k in ('azim', 'elev') else c.get(k, 0) for k in ('azim', 'elev', 'dist', 'fov', 'roll')]
pos = dist * np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
f = -pos / dist; r = np.cross(f, [0, 0, 1.0]); r /= np.linalg.norm(r); u = np.cross(r, f)
ro = math.radians(roll); r2 = r * math.cos(ro) + u * math.sin(ro); u2 = -r * math.sin(ro) + u * math.cos(ro)
t = math.tan(math.radians(fov) / 2)
def proj(P):
    d = P - pos; xc, yc, zc = d @ r2, d @ u2, d @ f
    return W * (0.5 + (xc / zc) / (t * W / H) / 2) + sx * W, H * (0.5 - (yc / zc) / t / 2) + sy * H
nu, nv = int((u1 - u0) * pxmm), int((v1 - v0) * pxmm)
U = u0 + (np.arange(nu) + 0.5) / pxmm; V = v1 - (np.arange(nv) + 0.5) / pxmm
UU, VV = np.meshgrid(U, V)
if osa == 'X': P = np.stack([np.full_like(UU, hv), UU, VV], -1)
elif osa == 'Y': P = np.stack([UU, np.full_like(UU, hv), VV], -1)
else: P = np.stack([VV, UU, np.full_like(UU, hv)], -1)   # u=Y, v=X
px, py = proj(P.reshape(-1, 3).T.T) if False else (None, None)
Pf = P.reshape(-1, 3); d = Pf - pos; xc, yc, zc = d @ r2, d @ u2, d @ f
PX = W * (0.5 + (xc / zc) / (t * W / H) / 2) + sx * W; PY = H * (0.5 - (yc / zc) / t / 2) + sy * H
im = Image.open(foto).convert('RGB'); sc = im.width / W
a = np.asarray(im).astype(float)
x = np.clip(PX * sc, 0, im.width - 1.001); y = np.clip(PY * sc, 0, im.height - 1.001)
x0 = x.astype(int); y0 = y.astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
s = a[y0, x0] * (1 - fx) * (1 - fy) + a[y0, x0 + 1] * fx * (1 - fy) + a[y0 + 1, x0] * (1 - fx) * fy + a[y0 + 1, x0 + 1] * fx * fy
res = Image.fromarray(s.reshape(nv, nu, 3).astype('uint8'))
d = ImageDraw.Draw(res)
g = grid
k = math.ceil(u0 / g) * g
while k < u1:
    X = (k - u0) * pxmm; d.line([(X, 0), (X, nv)], fill=(0, 200, 255) if abs(k) > 1e-6 else (255, 0, 255), width=1); d.text((X + 2, 2), f'{k:g}', fill=(255, 255, 0)); k += g
k = math.ceil(v0 / g) * g
while k < v1:
    Y = (v1 - k) * pxmm; d.line([(0, Y), (nu, Y)], fill=(0, 200, 255) if abs(k) > 1e-6 else (255, 0, 255), width=1); d.text((2, Y + 2), f'{k:g}', fill=(255, 255, 0)); k += g
res.save(out); print(out, res.size)
