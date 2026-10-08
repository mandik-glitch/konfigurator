#!/opt/konfigurator/api/venv/bin/python
"""Nezavisle overeni odvozene sablony stolu SYSTEM 40 proti sablone 30 (bot10, 2026-10-04): obalka, kontakty profilu a prislusenstvi, zanoreni dilu,
ulozeni rohovych spojek v profilu (vrcholy spojky vs prurez materialu profilu: jazycek musi lezet v krcku drazky, ne v materialu)."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from _spolecne import load_glb, quat, world, tmpl, KAT

def load40():
    return json.load(open(os.path.join(HERE, 'vystup', 'stul_sablona_system40.json'), encoding='utf-8'))['parts']

def aabbs(parts):
    cache = {}; out = []
    for p in parts:
        if p['part_id'] not in cache: cache[p['part_id']] = load_glb(KAT + p['part_id'] + '.glb')[0]
        W = world(p, cache[p['part_id']]); out.append((W.min(0), W.max(0)))
    return out

def relation(a, b, tol=0.6):
    (l1, h1), (l2, h2) = a, b
    ov = np.minimum(h1, h2) - np.maximum(l1, l2)
    if np.all(ov > tol): return 'prunik', float(ov.min())
    for ax in range(3):
        others = [x for x in range(3) if x != ax]
        if all(ov[x] > 1.0 for x in others):
            g = max(l1[ax] - h2[ax], l2[ax] - h1[ax])
            if abs(g) <= tol: return 'kontakt', round(float(g), 2)
    return 'nic', 0.0

def section_loops(glb):
    V, F = load_glb(glb); ax = int(np.argmax(V.max(0) - V.min(0))); assert ax == 1
    segs = []
    for tri in F:
        P = V[tri]; d = P[:, 1]; s = np.sign(d)
        if (s > 0).all() or (s < 0).all(): continue
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if d[a] == d[b]: continue
            if (d[a] <= 0 < d[b]) or (d[b] <= 0 < d[a]):
                u = (0 - d[a]) / (d[b] - d[a]); q = P[a] + u * (P[b] - P[a]); pts.append(q[[0, 2]])
        if len(pts) == 2: segs.append(pts)
    return np.array(segs)

def inside(segs, P):
    A, B = segs[:, 0, :], segs[:, 1, :]; r = np.zeros(len(P), bool)
    for a, b in zip(A, B):
        c = ((a[1] > P[:, 1]) != (b[1] > P[:, 1])) & (P[:, 0] < (b[0] - a[0]) * (P[:, 1] - a[1]) / (b[1] - a[1] + 1e-30) + a[0]); r ^= c
    return r

def dist(segs, P):
    A, B = segs[:, 0, :], segs[:, 1, :]; AB = B - A; L2 = (AB ** 2).sum(1) + 1e-30; d = np.full(len(P), 1e9)
    for a, ab, l2 in zip(A, AB, L2):
        t = np.clip(((P - a) @ ab) / l2, 0, 1); q = a + t[:, None] * ab; d = np.minimum(d, np.hypot(*(P - q).T))
    return d

def connector_fit(parts, prof_pid, con_pid):
    """Pro kazdou spojku: nejvetsi zanoreni vrcholu spojky do MATERIALU obou jejich profilu (mm)."""
    segs = section_loops(KAT + prof_pid + '.glb'); Vc = load_glb(KAT + con_pid + '.glb')[0]
    prof = [i for i, p in enumerate(parts) if p['part_id'] == prof_pid]; con = [i for i, p in enumerate(parts) if p['part_id'] == con_pid]
    res = {}
    for c in con:
        Wc = world(parts[c], Vc); worst = 0.0; owners = [i for i in prof if c in (parts[i].get('lic_peers') or [])]
        for i in owners:
            p = parts[i]; R = quat(p['quaternion']); L = p['scale'][1] * 1000
            loc = (Wc - np.array(p['position'])) @ R           # R^T (v - pos) pro radkove vektory
            loc[:, 1] /= p['scale'][1]
            sel = np.abs(loc[:, 1] * p['scale'][1]) <= L / 2
            if not sel.any(): continue
            P2 = loc[sel][:, [0, 2]]; ins = inside(segs, P2)
            if ins.any(): worst = max(worst, float(dist(segs, P2[ins]).max()))
        res[c] = round(worst, 3)
    return res

def main():
    p30 = tmpl()['parts']; p40 = load40()
    a30, a40 = aabbs(p30), aabbs(p40)
    ok = True
    def chk(name, cond, det=''):
        nonlocal ok
        print(('OK   ' if cond else 'FAIL ') + name + ('  ' + str(det) if det != '' else '')); ok &= bool(cond)
    prof = [i for i, p in enumerate(p30) if p['part_id'] == 'Object_7']
    legs = [i for i in prof if (a30[i][1][1] - a30[i][0][1]) > 600 and abs(a30[i][1][0] - a30[i][0][0] - 30) < 1]
    # 1) obalka noh (vnejsi plochy) stejna
    lo30 = np.min([a30[i][0] for i in legs], 0); hi30 = np.max([a30[i][1] for i in legs], 0)
    lo40 = np.min([a40[i][0] for i in legs], 0); hi40 = np.max([a40[i][1] for i in legs], 0)
    chk('vnejsi rozmery noh v ose X a Z stejne (nohy dovnitr o 5 mm); dole stejne', np.allclose([lo30[0], hi30[0], lo30[2], hi30[2], lo30[1]], [lo40[0], hi40[0], lo40[2], hi40[2], lo40[1]], atol=0.05), (np.round(lo30, 1), np.round(hi30, 1), np.round(lo40, 1), np.round(hi40, 1)))
    # 2) vztahy profil-profil (kontakt/prunik) stejne
    diffs = []
    for i in prof:
        for j in prof:
            if j <= i: continue
            r30 = relation(a30[i], a30[j]); r40 = relation(a40[i], a40[j])
            if r30[0] != r40[0]: diffs.append((i, j, r30, r40))
    chk('vsechny dvojice profilu maji stejny vztah (kontakt/nic/prunik) jako v systemu 30', not diffs, diffs[:6])
    # 3) vztahy prislusenstvi-profil stejne
    acc = [i for i, p in enumerate(p30) if p['part_id'] not in ('Object_7', 'product_3158')]
    d2 = []
    for i in acc:
        for j in prof:
            r30 = relation(a30[i], a30[j]); r40 = relation(a40[i], a40[j])
            if r30[0] != r40[0]: d2.append((i, j, r30, r40))
    chk('prislusenstvi vs profily: stejne kontakty a zadne nove pruniky', not d2, d2[:6])
    # 4) pruniky profil vs prislusenstvi >0.6 v kazde ose: zadne nove
    # 5) uloziste spojek: zanoreni vrcholu spojky do materialu profilu
    f30 = connector_fit(p30, 'Object_7', 'product_3158'); f40 = connector_fit(p40, 'Object_11', 'product_3176')
    print('     zanoreni spojek do materialu (mm): 30 max %.3f | 40 max %.3f' % (max(f30.values()), max(f40.values())))
    chk('rohove spojky 40 nejsou v materialu profilu hloub nez v systemu 30 + 0,2 mm (jazycky lezi v krcku drazky)', max(f40.values()) <= max(f30.values()) + 0.2, {k: v for k, v in f40.items() if v > 0.05})
    # 6) spojky: pretin AABB s jejich dvema profily podobny
    con = [i for i, p in enumerate(p30) if p['part_id'] == 'product_3158']
    dd = []
    for c in con:
        owners = [i for i in prof if c in (p30[i].get('lic_peers') or [])]
        for i in owners:
            ov30 = np.minimum(a30[c][1], a30[i][1]) - np.maximum(a30[c][0], a30[i][0]); ov40 = np.minimum(a40[c][1], a40[i][1]) - np.maximum(a40[c][0], a40[i][0])
            if (ov30.min() > 0.3) != (ov40.min() > 0.3): dd.append((c, i, np.round(ov30, 1).tolist(), np.round(ov40, 1).tolist()))
    chk('kazda spojka se dotyka obou svych profilu stejne jako v 30 (prekryv AABB ano/ne)', not dd, dd[:5])
    # 7) pocty dilu a topologie
    chk('50 dilu, stejne lic_peers/attached_to jako sablona 30', len(p40) == len(p30) == 50 and all((p40[i].get('lic_peers') == p30[i].get('lic_peers')) and (p40[i].get('attached_to') == p30[i].get('attached_to')) for i in range(50)))
    chk('profily jsou Object_11, spojky product_3176, 18 + 20 ks', sum(p['part_id'] == 'Object_11' for p in p40) == 18 and sum(p['part_id'] == 'product_3176' for p in p40) == 20)
    # delky profilu
    L30 = sorted(round(p30[i]['scale'][1] * 1000, 1) for i in prof); L40 = sorted(round(p40[i]['scale'][1] * 1000, 1) for i in prof)
    print('     delky profilu 30:', L30); print('     delky profilu 40:', L40)
    print('VSE OK' if ok else 'NEKTERA KONTROLA SELHALA')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
