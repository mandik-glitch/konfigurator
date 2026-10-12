#!/usr/bin/env python3
"""Odhad kamery z ručně změřených korespondencí 3D bod modelu <-> pixel fotografie (jen numpy, Levenberg-Marquardt).
Parametry: azim, elev, dist, fov (svisle), cx, cy (hlavní bod v px; fotografie je oříznutá, takže není ve středu). Náklon (roll) = 0.
Vstup: JSON {"w":614,"h":800,"body":[[X,Y,Z,px,py,vaha],...]} (souřadnice modelu, z = skutečné Z modelu, tj. z' - 133.5). Výstup: JSON s kamerou + zbytky.
Použití: kalibruj.py vstup.json [vystup.json]"""
import sys, json, math
import numpy as np

def project(P, X, W, H):
    az, el, dist, fov, cx, cy, roll = P
    a, e = math.radians(az), math.radians(el)
    pos = dist * np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])
    f = -pos / np.linalg.norm(pos)
    up = np.array([0, 0, 1.0]); r = np.cross(f, up); r /= np.linalg.norm(r); u = np.cross(r, f)
    ro = math.radians(roll)
    r2 = r * math.cos(ro) + u * math.sin(ro); u2 = -r * math.sin(ro) + u * math.cos(ro)
    d = X - pos
    xc, yc, zc = d @ r2, d @ u2, d @ f
    fp = (H / 2) / math.tan(math.radians(fov) / 2)
    return np.stack([cx + fp * xc / zc, cy - fp * yc / zc], axis=1)

def solve(data, free=(0, 1, 2, 3, 4, 5), start=None):
    W, H = data['w'], data['h']
    B = np.array(data['body'], float); X = B[:, :3]; obs = B[:, 3:5]; wt = B[:, 5] if B.shape[1] > 5 else np.ones(len(B))
    best = None
    for fov0 in (8, 14, 22, 32, 45):
        for az0 in (data.get('az0', 40) - 8, data.get('az0', 40) + 8):
            for el0 in (data.get('el0', 38) - 8, data.get('el0', 38) + 8):
                P = np.array([az0, el0, 1500 * (14 / fov0) ** 0.9, fov0, W / 2, H / 2, 0.0])
                lam = 1.0
                def res(P):
                    return ((project(P, X, W, H) - obs) * wt[:, None]).ravel()
                r0 = res(P); c0 = r0 @ r0
                for it in range(200):
                    J = np.zeros((len(r0), len(free)))
                    for k, i in enumerate(free):
                        dP = P.copy(); h = 1e-3 * max(1, abs(P[i])); dP[i] += h
                        J[:, k] = (res(dP) - r0) / h
                    A = J.T @ J + lam * np.diag(np.diag(J.T @ J) + 1e-9); g = J.T @ r0
                    try: step = np.linalg.solve(A, -g)
                    except Exception: break
                    Pn = P.copy()
                    for k, i in enumerate(free): Pn[i] += step[k]
                    if not (4 < Pn[3] < 70 and 300 < Pn[2] < 20000 and 0 < Pn[1] < 89): lam *= 4; continue
                    rn = res(Pn); cn = rn @ rn
                    if cn < c0: P, r0, c0 = Pn, rn, cn; lam = max(lam / 3, 1e-6)
                    else: lam *= 4
                    if lam > 1e8: break
                if best is None or c0 < best[0]: best = (c0, P.copy())
    c0, P = best
    pr = project(P, X, W, H)
    return P, np.hypot(*(pr - obs).T)

if __name__ == '__main__':
    data = json.load(open(sys.argv[1]))
    free = tuple(data.get('free', (0, 1, 2, 3, 4, 5)))
    P, err = solve(data, free)
    out = dict(azim=P[0], elev=P[1], dist=P[2], fov=P[3], cx=P[4], cy=P[5], roll=P[6], chyby_px=[round(float(e), 1) for e in err])
    print(json.dumps(out, indent=1))
    if len(sys.argv) > 2: json.dump(out, open(sys.argv[2], 'w'), indent=1)
