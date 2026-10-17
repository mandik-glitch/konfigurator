#!/usr/bin/env python3
"""Segmentace červených oblastí fotografie (složky spojitosti) -> bbox a těžiště v px. cervena.py foto [min_pixelu=300]
Jen čtení fotografie (scratchpad); výstup na stdout."""
import sys, numpy as np
from PIL import Image
from collections import deque
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int); mn = int(sys.argv[2]) if len(sys.argv) > 2 else 300
r, g, b = a[..., 0], a[..., 1], a[..., 2]
m = (r > 130) & (g < 95) & (b < 95) & (r - g > 60)
H, W = m.shape; lab = np.zeros((H, W), int); n = 0
for y in range(H):
    for x in range(W):
        if m[y, x] and not lab[y, x]:
            n += 1; q = deque([(y, x)]); lab[y, x] = n; pts = []
            while q:
                cy, cx = q.popleft(); pts.append((cy, cx))
                for dy in (-2, -1, 0, 1, 2):
                    for dx in (-2, -1, 0, 1, 2):
                        yy, xx = cy + dy, cx + dx
                        if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]: lab[yy, xx] = n; q.append((yy, xx))
            if len(pts) >= mn:
                ys = np.array([p[0] for p in pts]); xs = np.array([p[1] for p in pts])
                print(f'#{n} px={len(pts)} x {xs.min()}..{xs.max()} y {ys.min()}..{ys.max()} c=({int(xs.mean())},{int(ys.mean())})')
