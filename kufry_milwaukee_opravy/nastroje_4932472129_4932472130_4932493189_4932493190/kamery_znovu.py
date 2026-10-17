#!/usr/bin/env python3
"""Přepočet kamer z RUČNĚ změřených obrysových rohů (landmarky z kontrolního reportu John v6) s opravenými výškami rohů.
V reportu byly použity hypotézy z-úrovně rohů (víko +167/+172, dno −152/−181,5). Z čelní fotografie 3189/3190 c01 (profil obrysu, viz
zdroje/*_poznamky.md) vychází: horní hrana rohového bloku (ucha) z = +170, spodní hrana dolního rohového bloku z ≈ −163 (uprostřed −163, na okraji −156; nejníž −181,5 sahají jen nohy
předního soklu, ty nejsou obrysovým rohem). Pixelové landmarky se přebírají beze změny; mění se jen 3D body, ke kterým se přiřazují.
Kalibrace = kalibruj.py z kufry_hilti/nastroje (Levenberg-Marquardt, azim, elev, dist, fov, cx, cy). Výstup: kufriky_cloud/srovnani_opravy/<SKU>/cNN.json
Použití: kamery_znovu.py <SKU> [zlid zbase]"""
import sys, json, os, importlib.util
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
spec = importlib.util.spec_from_file_location('kalibruj', os.path.join(REPO, 'kufry_hilti/nastroje/kalibruj.py')); K = importlib.util.module_from_spec(spec); spec.loader.exec_module(K)
sku = sys.argv[1]; zl = float(sys.argv[2]) if len(sys.argv) > 2 else 170.0; zb = float(sys.argv[3]) if len(sys.argv) > 3 else -163.0
D = os.path.join(REPO, 'kufriky_cloud/kontrola_john_v6', sku); OUT = os.path.join(REPO, 'kufriky_cloud/srovnani_opravy', sku); os.makedirs(OUT, exist_ok=True)
P3 = {'FLlid': (207, -282, zl), 'FRlid': (207, 282, zl), 'BLlid': (-207, -282, zl), 'BRlid': (-207, 282, zl),
      'FLbase': (207, -282, zb), 'FRbase': (207, 282, zb), 'BLbase': (-207, -282, zb), 'BRbase': (-207, 282, zb)}
for f in sorted(os.listdir(D)):
    if not f.endswith('_landmarky.json'): continue
    pohled = f[:3]; j = json.load(open(os.path.join(D, f))); k0 = j['kamera']
    zb_p = -156.0 if k0['azim'] == 0.0 else zb          # čelní pohled: krajní roh bloku (−156); šikmé pohledy: obrysový vrchol leží na zkoseném spodku níž (≈ −163)
    P3 = {'FLlid': (207, -282, zl), 'FRlid': (207, 282, zl), 'BLlid': (-207, -282, zl), 'BRlid': (-207, 282, zl),
          'FLbase': (207, -282, zb_p), 'FRbase': (207, 282, zb_p), 'BLbase': (-207, -282, zb_p), 'BRbase': (-207, 282, zb_p)}
    # 3190 c03: landmark BLlid (zadní levý roh víka, jen na tomto snímku, rezidua 11,8 px) zkresluje řešení – vynechán (c02 téhož záběru ho nemá)
    VYNECH = {('4932493190', 'c03'): ['BLlid']}
    lm = {n: v for n, v in j['landmarky'].items() if n not in VYNECH.get((sku, pohled), [])}
    body = [[*P3[n], v[0], v[1], 1.0] for n, v in lm.items()]
    data = {'w': k0['w'], 'h': k0['h'], 'body': body, 'free': j.get('free', [0, 1, 2, 3, 4, 5]), 'az0': k0['azim'], 'el0': k0['elev']}
    if k0['azim'] == 0.0:                                   # čelní pohled: azimut 0 (symetrie), fov 24° jen předpoklad
        P = [0.0, k0['elev'], k0['dist'], 24.0, k0['cx'], k0['cy'], 0.0]
        import numpy as np
        free = tuple(data['free']); X = np.array([b[:3] for b in body], float); obs = np.array([b[3:5] for b in body], float)
        lam = 1.0
        def res(P): return ((K.project(P, X, data['w'], data['h']) - obs)).ravel()
        r0 = res(P); c0 = r0 @ r0
        for it in range(300):
            J = np.zeros((len(r0), len(free)))
            for kk, i in enumerate(free):
                dP = P.copy() if hasattr(P, 'copy') else list(P); dP = np.array(dP, float); h = 1e-3 * max(1, abs(P[i])); dP[i] += h; J[:, kk] = (res(dP) - r0) / h
            A = J.T @ J + lam * np.diag(np.diag(J.T @ J) + 1e-9); g = J.T @ r0; step = np.linalg.solve(A, -g)
            Pn = np.array(P, float)
            for kk, i in enumerate(free): Pn[i] += step[kk]
            rn = res(Pn); cn = rn @ rn
            if cn < c0: P, r0, c0 = Pn, rn, cn; lam = max(lam / 3, 1e-6)
            else: lam *= 4
            if lam > 1e8: break
        err = np.hypot(*(K.project(np.array(P, float), X, data['w'], data['h']) - obs).T)
    else:
        P, err = K.solve(data, tuple(data['free']))
    az, el, dist, fov, cx, cy, roll = [float(v) for v in P]
    cam = {'azim': az, 'elev': el, 'dist': dist, 'fov': fov, 'cx': cx, 'cy': cy, 'roll': 0.0, 'w': k0['w'], 'h': k0['h'], 'shiftX': (cx - k0['w'] / 2) / k0['w'], 'shiftY': (cy - k0['h'] / 2) / k0['h']}
    rms = float((err ** 2).mean() ** 0.5); import numpy as np; rms0 = float((np.array(list(j['landmarky'].values()))[:, 2] ** 2).mean() ** 0.5)
    json.dump({'sku': sku, 'pohled': pohled, 'kamera': cam, 'landmarky_px': {n: v[:2] for n, v in lm.items()}, 'z_rohu': {'lid': zl, 'base': zb_p}, 'chyby_px': [round(float(e), 1) for e in err],
               'rms_px': round(rms, 1), 'rms_px_report': rms0, 'poznamka': 'kamera přepočtena z původních ručních landmarků (rohy obrysu) s opravenými z-úrovněmi rohů; bez dofitování podle tvaru modelu'}, open(os.path.join(OUT, pohled + '.json'), 'w'), indent=1, ensure_ascii=False)
    print(sku, pohled, 'azim %.1f elev %.1f dist %.0f fov %.1f' % (az, el, dist, fov), 'RMS px nový %.1f' % rms, 'původní %.1f' % rms0, 'chyby', [round(float(e), 1) for e in err])

