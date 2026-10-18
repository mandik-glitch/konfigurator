#!/usr/bin/env python3
"""Svazkové vyrovnání (bundle adjustment) rozměrů stroje + 4 kamer z ručně změřených bodů (numpy, Levenberg-Marquardt).
Neznámé: rozměry těla (slovník DIMS) a pro každou fotografii kamera (poloha 3, yaw, pitch, roll, fov); hlavní bod = střed snímku
(fotografie jsou neořezané, 4:3). Měřítko: výška temene krytu Ht = 780 mm a země z=0 jsou pevné; ostatní rozměry váží slabé apriorní hodnoty.
Použití: svazek.py landmarky_dir vystup.json [--free klíč,klíč..]
Landmark soubory: l11.json l12.json l13.json l14.json  {"foto","w","h","pts":{JMENO:[px,py]}}; jméno = ID_S, kde S = E (+X) | W (−X) | bez přípony (osa)."""
import sys, json, math, glob, os
import numpy as np

HT = 780.0
D0 = dict(hw=225, Yf=-325, ys=-100, yb=130, Hb=470, zb=125, yft=-30, zft=500, yfr=135, zfb=190,
          xw=285, yw=-215, R=130, yh=-170, hwr=200, Yr=250, zbx=470, zbt=420, hpt=520, Yh=325, hz=560, zc=105, yc=215, xc=200)
SIG = dict(hw=40, Yf=15, ys=80, yb=80, Hb=100, zb=60, yft=80, zft=90, yfr=80, zfb=80, xw=45, yw=80, R=40, yh=80,
           hwr=60, Yr=60, zbx=80, zbt=80, hpt=100, Yh=30, hz=100, zc=40, yc=60, xc=60)

def P3(name, d):
    base, side = (name.rsplit('_', 1) + [''])[:2] if '_' in name else (name, '')
    s = {'E': 1, 'W': -1, '': 0}[side]
    if base == 'FT': return [s * d['hw'], d['Yf'], HT]
    if base == 'SH': return [s * d['hw'], d['ys'], HT]
    if base == 'SB': return [s * d['hw'], d['yb'], d['Hb']]
    if base == 'FB': return [s * d['hw'], d['Yf'], d['zb']]
    if base == 'FRtf': return [s * d['hw'], d['yft'], d['zft']]
    if base == 'FRbr': return [s * d['hw'], d['yfr'], d['zfb']]
    if base == 'HUB': return [s * d['xw'], d['yw'], d['R']]
    if base == 'HOLE': return [0, d['yh'], HT]
    if base == 'PBOT': return [s * d['hwr'], d['Yr'], d['zbx']]
    if base == 'RBT': return [s * d['hwr'], d['Yr'], d['zbt']]      # rear box top outer corner (rear plane)
    if base == 'RBB': return [s * d['hwr'], d['Yr'], d['zbx']]
    if base == 'TT': return [s * d['xw'], d['yw'], 2 * d['R']]
    if base == 'TB': return [s * d['xw'], d['yw'], 0.0]
    if base == 'HNDM': return [0.0, d['Yh'], d['hz']]
    if base == 'BOXT': return [s * d['hwr'], d['Yr'], d['zbt']]
    if base == 'HNDT': return [s * d['hwr'], d['Yh'], d['hz']]       # handle bar top, rear-most point, x at post
    if base == 'CST': return [s * d['xc'], d['yc'], 0.0]            # caster ground contact
    raise KeyError(name)

def cam_basis(p):
    cx, cy, cz, yaw, pitch, roll, fov = p
    ya, pi, ro = map(math.radians, (yaw, pitch, roll))
    f = np.array([math.cos(pi) * math.cos(ya), math.cos(pi) * math.sin(ya), math.sin(pi)])
    up = np.array([0, 0, 1.0]); r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    r2 = r * math.cos(ro) + u * math.sin(ro); u2 = -r * math.sin(ro) + u * math.cos(ro)
    return np.array([cx, cy, cz]), f, r2, u2

def project(p, X, w, h):
    pos, f, r, u = cam_basis(p)
    dd = X - pos; xc, yc, zc = dd @ r, dd @ u, dd @ f
    fp = (h / 2) / math.tan(math.radians(p[6]) / 2)
    return np.stack([w / 2 + fp * xc / zc, h / 2 - fp * yc / zc], axis=1)

def load(dirn):
    out = {}
    for f in sorted(glob.glob(os.path.join(dirn, 'l*.json'))):
        j = json.load(open(f)); out[j['foto']] = j
    return out

def cam_from_look(az, el, dist, tgt, fov=55):
    a, e = math.radians(az), math.radians(el)
    pos = np.array(tgt) + dist * np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    d = np.array(tgt) - pos
    yaw = math.degrees(math.atan2(d[1], d[0])); pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return [*pos, yaw, pitch, 0.0, fov]

def solve(L, free, d0=None, start=None, verbose=True, wprior=1.0, fov_prior=(55, 6), roll_sig=2.0):
    d0 = dict(D0 if d0 is None else d0)
    photos = sorted(L)
    names = {k: list(L[k]['pts'].keys()) for k in photos}
    AZ = {'11': 135, '12': 225, '13': 315, '14': 45}
    best = None
    def unpack(x):
        d = dict(d0)
        for i, k in enumerate(free): d[k] = x[i]
        cams = {k: x[len(free) + 7 * i: len(free) + 7 * i + 7] for i, k in enumerate(photos)}
        return d, cams
    def resid(x):
        d, cams = unpack(x); r = []
        for k in photos:
            w, h = L[k]['w'], L[k]['h']
            X = np.array([P3(n, d) for n in names[k]]); obs = np.array([L[k]['pts'][n] for n in names[k]], float)
            pr = project(cams[k], X, w, h)
            pos, f, _, _ = cam_basis(cams[k]); zc = (X - pos) @ f
            if (zc < 50).any(): return np.full(len(x) * 0 + 1000, 1e3)
            r.extend(((pr - obs) / (w / 1500.0)).ravel())
        for i, kk in enumerate(free): r.append(wprior * (x[i] - D0[kk]) / SIG[kk] * 8)
        for i, k in enumerate(photos):
            c = cams[k]; r.append((c[6] - fov_prior[0]) / fov_prior[1] * 8); r.append(c[5] / roll_sig * 8)
        return np.array(r)
    for trial in range(40):
        rng = np.random.default_rng(trial)
        x0 = [d0[k] for k in free]
        for k in photos:
            if start and k in start: x0 += list(start[k]); continue
            x0 += cam_from_look(AZ[k] + rng.uniform(-25, 25), rng.uniform(12, 40), rng.uniform(1700, 3200), [0, 0, 300], rng.uniform(48, 62))
        x = np.array(x0, float); lam = 1.0; r0 = resid(x); c0 = r0 @ r0
        for it in range(300):
            J = np.zeros((len(r0), len(x)))
            for i in range(len(x)):
                dx = np.zeros(len(x)); hh = 1e-4 * max(1, abs(x[i])); dx[i] = hh
                J[:, i] = (resid(x + dx) - r0) / hh
            A = J.T @ J; g = J.T @ r0
            try: st = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-6), -g)
            except Exception: break
            xn = x + st; rn = resid(xn); cn = rn @ rn
            if cn < c0: x, r0, c0 = xn, rn, cn; lam = max(lam / 3, 1e-7)
            else: lam *= 4
            if lam > 1e9: break
        if best is None or c0 < best[0]: best = (c0, x.copy())
        if verbose: print('start', trial, round(c0, 1), 'best', round(best[0], 1), file=sys.stderr)
        if start: break
    c0, x = best; d, cams = unpack(x)
    res = {}
    for k in photos:
        w, h = L[k]['w'], L[k]['h']
        X = np.array([P3(n, d) for n in names[k]]); obs = np.array([L[k]['pts'][n] for n in names[k]], float)
        pr = project(cams[k], X, w, h); res[k] = {n: round(float(np.hypot(*(pr[i] - obs[i])) / (w / 1500.0)), 1) for i, n in enumerate(names[k])}
    return d, cams, res, c0

if __name__ == '__main__':
    args = sys.argv[1:]
    free = []
    if '--free' in args: i = args.index('--free'); free = args[i + 1].split(','); del args[i:i + 2]
    for a in [a for a in args if a.startswith('--prior=')]:
        k, v = a[8:].split('='); m, sg = map(float, v.split(':')); D0[k] = m; SIG[k] = sg; args.remove(a)
    init = None
    if '--init' in args: i = args.index('--init'); init = json.load(open(args[i + 1])); del args[i:i + 2]
    L = load(args[0])
    d, cams, res, c = solve(L, free, d0=(init['dims'] if init else None), start=(init['cams'] if init else None))
    out = dict(dims={k: round(float(v), 1) for k, v in d.items()}, cams={k: [round(float(v), 3) for v in c] for k, c in cams.items()}, chyby_px_na_1500=res, cena=c)
    print(json.dumps(out, indent=1))
    if len(args) > 1: json.dump(out, open(args[1], 'w'), indent=1)
