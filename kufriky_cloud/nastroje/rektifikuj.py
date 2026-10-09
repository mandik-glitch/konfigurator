#!/usr/bin/env python3
"""Z šikmé fotografie vyrobí 'rektifikovaný' přímý pohled na ROVINU modelu (čelo, bok, vršek) – k měření poloh prvků v mm.
Používá kameru odhadnutou z obrysu (srovnani/<SKU>/<pohled>.json), shodnou s render.mjs (three.js, shiftX/shiftY = setViewOffset).
Prvky ležící v dané rovině mají správné rozměry, prvky vyčnívající z roviny jsou posunuté úměrně vzdálenosti od roviny (perspektiva).
Použití: rektifikuj.py foto.jpg kamera.json osa hodnota a0 a1 b0 b1 vystup.png [px_na_mm=4] [--mrizka 10]
  osa 'x': rovina X=hodnota, vodorovně Y (a0..a1), svisle Z (b0..b1, nahoře b1)
  osa 'y': rovina Y=hodnota, vodorovně X (a0..a1), svisle Z
  osa 'z': rovina Z=hodnota, vodorovně Y (a0..a1), svisle X (nahoře b1)
Souřadnice jsou v počátku obálky (střed). Fotografie se jen čte, výstup patří do scratchpadu (ne do repa)."""
import sys, json, math
import numpy as np
from PIL import Image, ImageDraw

def camera_basis(cam):
    az, el = math.radians(cam['azim']), math.radians(cam['elev'])
    tgt = np.array(cam.get('target', [0, 0, 0]), float)
    pos = tgt + cam['dist'] * np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)])
    f = tgt - pos; f /= np.linalg.norm(f)
    up = np.array([0, 0, 1.0]); r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    ro = math.radians(cam.get('roll', 0) or 0)
    r2 = r * math.cos(ro) + u * math.sin(ro); u2 = -r * math.sin(ro) + u * math.cos(ro)
    return pos, f, r2, u2

def project(cam, P, W, H):
    pos, f, r, u = camera_basis(cam)
    d = P - pos
    xc, yc, zc = d @ r, d @ u, d @ f
    t = math.tan(math.radians(cam['fov']) / 2)
    ndx = (xc / zc) / (t * W / H); ndy = (yc / zc) / t
    px = W * (0.5 + ndx / 2) + (cam.get('shiftX', 0) or 0) * W
    py = H * (0.5 - ndy / 2) + (cam.get('shiftY', 0) or 0) * H
    return px, py

def sample(img, px, py):
    a = np.asarray(img).astype(float); H, W = a.shape[:2]
    x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int); fx = px - x0; fy = py - y0
    def g(yy, xx): return a[np.clip(yy, 0, H - 1), np.clip(xx, 0, W - 1)]
    out = (g(y0, x0) * ((1 - fx) * (1 - fy))[..., None] + g(y0, x0 + 1) * (fx * (1 - fy))[..., None] + g(y0 + 1, x0) * ((1 - fx) * fy)[..., None] + g(y0 + 1, x0 + 1) * (fx * fy)[..., None])
    return out.clip(0, 255).astype('uint8')

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    foto, camf, axis, val, a0, a1, b0, b1, out = args[:9]
    ppm = float(args[9]) if len(args) > 9 else 4.0
    val, a0, a1, b0, b1 = map(float, (val, a0, a1, b0, b1))
    cam = json.load(open(camf)); cam = cam.get('kamera', cam)
    img = Image.open(foto).convert('RGB'); W, H = img.size
    wpx, hpx = int((a1 - a0) * ppm), int((b1 - b0) * ppm)
    A = a0 + (np.arange(wpx) + 0.5) / ppm; B = b1 - (np.arange(hpx) + 0.5) / ppm
    AA, BB = np.meshgrid(A, B)
    if axis == 'x': P = np.stack([np.full_like(AA, val), AA, BB], -1)
    elif axis == 'y': P = np.stack([AA, np.full_like(AA, val), BB], -1)
    else: P = np.stack([BB, AA, np.full_like(AA, val)], -1)
    px, py = project(cam, P.reshape(-1, 3), W, H)
    res = Image.fromarray(sample(img, px.reshape(hpx, wpx), py.reshape(hpx, wpx)))
    if '--mrizka' in sys.argv:
        step = float(sys.argv[sys.argv.index('--mrizka') + 1]); d = ImageDraw.Draw(res)
        k = math.ceil(a0 / step) * step
        while k <= a1: x = (k - a0) * ppm; d.line([(x, 0), (x, hpx)], fill=(0, 160, 255) if int(round(k / step)) % 5 else (255, 0, 160), width=1); d.text((x + 2, 2), f'{k:g}', fill=(255, 0, 160)); k += step
        k = math.ceil(b0 / step) * step
        while k <= b1: y = (b1 - k) * ppm; d.line([(0, y), (wpx, y)], fill=(0, 160, 255) if int(round(k / step)) % 5 else (255, 0, 160), width=1); d.text((2, y + 2), f'{k:g}', fill=(255, 0, 160)); k += step
    res.save(out); print(out, res.size)
