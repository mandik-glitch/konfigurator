#!/usr/bin/env python3
"""Zpětná projekce pixelu fotografie na rovinu modelu (x=c | y=c | z=c) podle kamer ze svazek.py (odhad kamery!).
Použití: odpromit.py svazek.json foto x|y|z hodnota u1,v1 u2,v2 ...   -> vypíše zbylé dvě souřadnice (mm)"""
import sys, json, math
import numpy as np
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from svazek import cam_basis

def unproject_plane(cam, w, h, u, v, p0, n):
    pos, f, r, up = cam_basis(cam)
    fp = (h / 2) / math.tan(math.radians(cam[6]) / 2)
    d = f + r * (u - w / 2) / fp - up * (v - h / 2) / fp
    n = np.array(n, float); t = ((np.array(p0, float) - pos) @ n) / (d @ n)
    return pos + t * d

def unproject(cam, w, h, u, v, axis, val):
    pos, f, r, up = cam_basis(cam)
    fp = (h / 2) / math.tan(math.radians(cam[6]) / 2)
    d = f + r * (u - w / 2) / fp - up * (v - h / 2) / fp     # směr paprsku
    k = 'xyz'.index(axis)
    t = (val - pos[k]) / d[k]
    return pos + t * d

if __name__ == '__main__':
    if sys.argv[3] == 'sikma':     # odpromit.py sv foto sikma ys,Ht,yb,Hb u,v ...
        J = json.load(open(sys.argv[1])); foto = sys.argv[2]; ys, ht, yb, hb = map(float, sys.argv[4].split(','))
        W = {'11': (1500, 1125), '12': (1500, 1125), '13': (2000, 1500), '14': (1500, 1125)}[foto]
        n = [0, ht - hb, yb - ys]
        for pt in sys.argv[5:]:
            u, v = map(float, pt.split(','))
            q = unproject_plane(J['cams'][foto], W[0], W[1], u, v, [0, ys, ht], n)
            print(pt, '->', f'x={q[0]:.1f} y={q[1]:.1f} z={q[2]:.1f} s={(q[1]-ys)/(yb-ys)*math.hypot(yb-ys,hb-ht):.1f}')
        sys.exit()
    J = json.load(open(sys.argv[1])); foto = sys.argv[2]; axis = sys.argv[3]; val = float(sys.argv[4])
    W = {'11': (1500, 1125), '12': (1500, 1125), '13': (2000, 1500), '14': (1500, 1125)}[foto]
    for pt in sys.argv[5:]:
        u, v = map(float, pt.split(','))
        p = unproject(J['cams'][foto], W[0], W[1], u, v, axis, val)
        print(pt, '->', ' '.join(f'{c}={x:.1f}' for c, x in zip('xyz', p)))
