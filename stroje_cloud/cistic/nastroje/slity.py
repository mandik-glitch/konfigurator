#!/usr/bin/env python3
"""Detekce tmavých drážek (větrací otvory) na fotografii uvnitř zadaného polygonu a jejich zpětná projekce na rovinu modelu.
Použití: slity.py foto.jpg svazek.json foto_id osa hodnota 'x1,y1;x2,y2;...' [prah=70]  -> JSON seznam {c:[u,v], p1:[..], p2:[..], mm:[a,b], delka, uhel}
(fotografie se jen čte, nic se neukládá)."""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from odpromit import unproject

def comps(mask, minpix=25):
    H, W = mask.shape; lab = np.zeros((H, W), int); out = []; n = 0
    for y0 in range(H):
        for x0 in range(W):
            if mask[y0, x0] and not lab[y0, x0]:
                n += 1; st = [(y0, x0)]; lab[y0, x0] = n; pts = []
                while st:
                    y, x = st.pop(); pts.append((x, y))
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not lab[yy, xx]: lab[yy, xx] = n; st.append((yy, xx))
                if len(pts) >= minpix: out.append(np.array(pts, float))
    return out

if __name__ == '__main__':
    foto, sv, fid, axis, val, poly = sys.argv[1:7]; thr = int(sys.argv[7]) if len(sys.argv) > 7 else 70
    P = [tuple(map(float, q.split(','))) for q in poly.split(';')]
    im = Image.open(foto).convert('L'); W, H = im.size
    pm = Image.new('L', (W, H), 0); ImageDraw.Draw(pm).polygon(P, fill=1)
    a = np.asarray(im); m = (a < thr) & (np.asarray(pm) > 0)
    J = json.load(open(sv)); cam = J['cams'][fid]
    res = []
    for pts in comps(m):
        c = pts.mean(0); cov = np.cov((pts - c).T); w, v = np.linalg.eigh(cov); ax = v[:, 1]
        t = (pts - c) @ ax; e1 = c + ax * t.min(); e2 = c + ax * t.max()
        q = [unproject(cam, W, H, *x, axis, float(val)) for x in (c, e1, e2)]
        k = [i for i in range(3) if 'xyz'[i] != axis]
        mm = [[round(float(p[i]), 1) for i in k] for p in q]
        d = math.hypot(mm[2][0] - mm[1][0], mm[2][1] - mm[1][1]); res.append(dict(c=[round(float(c[0])), round(float(c[1]))], mm=mm, delka=round(d, 1), sirka_px=round(float(math.sqrt(max(w[0], 0)) * 3.46), 1), n=len(pts)))
    print(json.dumps(res))
