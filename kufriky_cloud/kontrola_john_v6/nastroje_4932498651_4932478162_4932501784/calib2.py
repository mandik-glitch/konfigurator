#!/usr/bin/env python3
"""Kalibrace kamery NEZÁVISLE na tvaru Johnova modelu: (1) ručně změřené body (rohové ochrany, 3D = obálka z katalogu, z jen s apriorním rozptylem),
(2) obrys fotografie vs. promítnutý KVÁDR obálky z katalogu (ne Johnův tvar). Vstup JSON: viz soubory cfg_*.json. Výstup: cam_*.json + log."""
import sys, json, math, struct
import numpy as np
from PIL import Image, ImageDraw
cfg = json.load(open(sys.argv[1])); out = sys.argv[2]
W, H = cfg['w'], cfg['h']
# maska fotografie (stejný práh jako foto_maska.py), L=300
def mask_of(path, L=300, thr=236):
    from PIL import ImageFilter
    im = Image.open(path).convert('RGB'); sc = L / max(im.size); im = im.resize((round(im.width*sc), round(im.height*sc)), Image.LANCZOS)
    a = np.asarray(im).astype(int); fg = a.min(axis=2) < thr
    m = Image.fromarray((fg*255).astype('uint8')).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    pad = Image.new('L', (m.width+4, m.height+4), 0); pad.paste(m, (2, 2)); ImageDraw.floodfill(pad, (0, 0), 128)
    return (np.asarray(pad)[2:-2, 2:-2] != 128), sc
M, sc = mask_of(cfg['foto'])
h, w = M.shape
yc = int(cfg.get('y_cut', 0) * sc)           # řádky nad y_cut se ignorují (např. zdvižené madlo mimo obálku)
valid = np.ones_like(M); valid[:yc, :] = False
if 'x_cut' in cfg: valid[:, :int(cfg['x_cut'][0]*sc)] = False; valid[:, int(cfg['x_cut'][1]*sc):] = False
box = cfg.get('box') or [-1,1,-1,1,-1,1]  # [xmin,xmax,ymin,ymax,zmin,zmax]
cor = np.array([[x, y, z] for x in box[0:2] for y in box[2:4] for z in box[4:6]], float)
def cam(P):
    az, el, dist, fov, cx, cy = P[:6]
    a, e = math.radians(az), math.radians(el)
    pos = dist*np.array([math.cos(e)*math.cos(a), math.cos(e)*math.sin(a), math.sin(e)])
    f = -pos/np.linalg.norm(pos); up = np.array([0, 0, 1.0]); r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    return pos, f, r, u
def proj(P, X):
    pos, f, r, u = cam(P); d = X-pos; xc, yc_, zc = d@r, d@u, d@f
    fp = (H/2)/math.tan(math.radians(P[3])/2)
    return np.stack([P[4]+fp*xc/zc, P[5]-fp*yc_/zc], axis=1)
# ruční body: [X,Y,zkey,px,py,název]; zkey = číslo (pevné z) nebo jméno parametru z s apriorem
lm = cfg['body']; zpri = cfg.get('zpri', cfg.get('ppri', {})); zn = sorted(zpri)
def split(P): return P[:6], dict(zip(zn, P[6:]))
def lm_res(P):
    cp, zs = split(P); res = []
    for (X, Y, zk, px, py, *_ ) in lm:
        g = lambda v: ((-zs[v[1:]]) if v.startswith('-') else zs[v]) if isinstance(v, str) else v
        q = proj(cp, np.array([[g(X), g(Y), g(zk)]]))[0]; res += [q[0]-px, q[1]-py]
    return np.array(res)
def cost(P, detail=False):
    cp, zs = split(P)
    if not (6 < cp[3] < 50 and 600 < cp[2] < 9000 and 0 < cp[1] < 80): return 1e9
    q = proj(cp, cor); 
    if (q[:,0] < -50).any(): pass
    im = Image.new('L', (w, h), 0); hull = _hull(q*sc); ImageDraw.Draw(im).polygon([tuple(p) for p in hull], fill=1)
    S = np.asarray(im).astype(bool)
    pv = M & valid; sv = S & valid
    out_ = (pv & ~sv).sum()/max(pv.sum(), 1); empty = (S & ~M).sum()/max(S.sum(), 1)
    r = lm_res(P); lmerr = np.sqrt((r**2).reshape(-1, 2).sum(1)).mean() if len(r) else 0
    pri = sum(((zs[k]-zpri[k][0])/zpri[k][1])**2 for k in zn)*0.002
    pp = (((cp[4]-W/2)/(0.06*W))**2+((cp[5]-H/2)/(0.06*H))**2)*0.002
    fp_ = ((cp[3]-cfg['fovpri'][0])/cfg['fovpri'][1])**2*0.002 if 'fovpri' in cfg else 0
    c = fp_+(3*out_+cfg.get('wempty', 0.7)*empty if cfg.get('box') else 0)+cfg.get('wlm', 0.004)*lmerr+pri+pp
    return (c, out_, empty, lmerr) if detail else c
def _hull(pts):
    pts = sorted(map(tuple, pts)); 
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo = []; 
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1]+up[:-1]
def nm(f, x0, st, iters=400):
    n = len(x0); pts = [np.array(x0, float)]
    for i in range(n): p = np.array(x0, float); p[i] += st[i]; pts.append(p)
    vals = [f(p) for p in pts]
    for it in range(iters):
        idx = np.argsort(vals); pts = [pts[i] for i in idx]; vals = [vals[i] for i in idx]
        if abs(vals[-1]-vals[0]) < 1e-7: break
        c = np.mean(pts[:-1], axis=0); al = lambda t: c+t*(pts[-1]-c)
        xr = al(-1); fr = f(xr)
        if fr < vals[0]:
            xe = al(-2); fe = f(xe)
            if fe < fr: pts[-1], vals[-1] = xe, fe
            else: pts[-1], vals[-1] = xr, fr
        elif fr < vals[-2]: pts[-1], vals[-1] = xr, fr
        else:
            xc = al(-0.5) if fr < vals[-1] else al(0.5); fc = f(xc)
            if fc < min(fr, vals[-1]): pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, n+1): pts[i] = pts[0]+0.5*(pts[i]-pts[0]); vals[i] = f(pts[i])
    b = int(np.argmin(vals)); return pts[b], vals[b]
rng = np.random.default_rng(1)
best = []
az0 = cfg.get('az0', [0, 40]); el0 = cfg.get('el0', [10, 40])
for trial in range(cfg.get('trials', 40)):
    fov = rng.uniform(10, 35); dist = 1700*(20/fov)**0.9*rng.uniform(.7, 1.3)
    P0 = [rng.uniform(*az0), rng.uniform(*el0), dist, fov, W/2, H/2]+[zpri[k][0] for k in zn]
    st = [6, 6, dist*.2, 4, 15, 15]+[10]*len(zn)
    P, c = nm(cost, P0, st, 300); P, c = nm(cost, P, [2, 2, dist*.05, 1, 5, 5]+[4]*len(zn), 300)
    best.append((c, P))
best.sort(key=lambda t: t[0])
c, P = best[0]
det = cost(P, True)
print('nejlepsi cena %.4f  mimo=%.3f prazdno=%.3f lm_px=%.1f' % det)
for c2, P2 in best[:5]: print(' ', round(c2, 4), np.round(P2, 1).tolist())
cp, zs = split(P)
# reprojekční chyby ručních bodů
r = lm_res(P).reshape(-1, 2)
res = {'azim': cp[0], 'elev': cp[1], 'dist': cp[2], 'fov': cp[3], 'cx': cp[4], 'cy': cp[5], 'w': W, 'h': H, 'roll': 0,
       'z_parametry_mm': zs, 'cena': det[0], 'podil_fotky_mimo_kvadr': det[1], 'podil_kvadru_mimo_fotku': det[2], 'lm_chyba_px_prumer': det[3],
       'lm_chyby_px': [{'bod': l[5] if len(l) > 5 else i, 'chyba_px': round(float(math.hypot(*r[i])), 1)} for i, l in enumerate(lm)],
       'nejlepsi_5_azim_elev_fov': [[round(float(p[0]), 1), round(float(p[1]), 1), round(float(p[3]), 1), round(float(cc), 4)] for cc, p in best[:5]]}
json.dump(res, open(out, 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items() if k in ('azim', 'elev', 'dist', 'fov', 'cx', 'cy', 'z_parametry_mm')}, ensure_ascii=False))
print(res['lm_chyby_px'])
