#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator animovaneho GLB "Pripni cokoli" (stavebnice-demo.glb): hlinikovy profil 40x40 S10 (realny Dogus STEP -> GLB), katalogove matice
(KAMEN = T matice M6 drazka 10, produkt 3592; OTOCNA = ozubena matice M6 drazka 10, produkt 3582), katalogove dily (uhelnik 30x30 produkt 3045
= NOVY prevod STEP ve vysoke kvalite zdroje/uhelnik_3045_vysoka_kvalita.glb; pant 40x40 produkt 3325), dva proceduralni zapustne sroubky M6 imbus,
jeden zacyklený klip `demo` (30 fps, LINEAR), metadata v scenes[0].extras (v3d = specifikace pro viewer3d.js; demo = cues, steps, camera, nodes, fastenings)
a uzly s extras {g} a kotvami a_<uzel>.

MODULARITA: vse, co se k sestave pridava, je v default_fastenings() (oddil 8): jedno upevneni = matice + dil + sroub + poloha x + casy + cues + kamera.
Pridani dalsiho dilu = pridat dict do seznamu; g-cisla, kroky (steps), cues, kamera, kotvy, uzly i zaverecny cue "cokoli" + rozpusteni se generuji.
Globalni tempo klipu: TIME_SCALE (casy pohybu v "autorskych sekundach" se nasobi); pauzy (intro/slot/zaver) jsou v realnych sekundach.

Pouziti (vsechny cesty jsou parametry; nic se nestahuje, nezapisuje se nic mimo --out / --drazka-json / --extras-json):
  python build_demo_glb.py --profile /cesta/profil_40x40_sl_s10.glb --katalog /opt/konfigurator/webapp/katalog \
      --out stavebnice-demo.glb [--drazka-json drazka.json] [--extras-json demo_extras.json] [--uhelnik-glb jiny.glb] [--zdroje adresar]
      [--kamen 3592|3066] [--head csk|cap]

Souradnice sceny (mm): X = delka profilu (cela s drazkou pro kamen na -X), Y nahoru (spodek profilu Y=0, horni plocha Y=40), Z k divakovi.
Matice a dily se z katalogu berou beze zmeny tvaru (kamen jen quadric decimaci na 3000 tr., vrcholy zustavaji na puvodnich souradnicich).
GLB se zapisuje vlastnim malym zapisovacem JSON+BIN (deterministicky: stejny vstup = stejne bajty). Zavislost: jen numpy.
"""
import argparse, json, math, os, struct, sys
import numpy as np

# ======================================================================================================================
# 1) cteni GLB (jen POSITION + indices, normaly se pocitaji znovu s hranou)
# ======================================================================================================================
_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_TN = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    data = open(path, 'rb').read()
    magic, ver, length = struct.unpack('<III', data[:12])
    if magic != 0x46546C67:
        raise ValueError('neni GLB: ' + path)
    off, js, bn = 12, None, None
    while off < length:
        clen, ctype = struct.unpack('<II', data[off:off + 8]); off += 8
        chunk = data[off:off + clen]; off += clen
        if ctype == 0x4E4F534A: js = json.loads(chunk.decode('utf-8'))
        elif ctype == 0x004E4942: bn = chunk
    return js, bn


def _accessor(js, bn, idx):
    a = js['accessors'][idx]; bv = js['bufferViews'][a['bufferView']]
    dt = np.dtype(_CT[a['componentType']]); nc = _TN[a['type']]
    off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride') or dt.itemsize * nc
    cnt = a['count']
    if stride == dt.itemsize * nc:
        arr = np.frombuffer(bn, dtype=dt, count=cnt * nc, offset=off).reshape(cnt, nc)
    else:
        arr = np.stack([np.frombuffer(bn, dtype=dt, count=nc, offset=off + i * stride) for i in range(cnt)])
    return arr.copy()


def _node_matrix(n):
    if 'matrix' in n:
        return np.array(n['matrix'], float).reshape(4, 4).T
    M = np.eye(4)
    if 'scale' in n: M = M @ np.diag(list(n['scale']) + [1.0])
    if 'rotation' in n:
        x, y, z, w = n['rotation']
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M3 = np.eye(4); M3[:3, :3] = R; M = M3 @ M
    if 'translation' in n:
        T = np.eye(4); T[:3, 3] = n['translation']; M = T @ M
    return M


def load_glb_geometry(path):
    """vsechny meshe souboru v jednom (V (n,3) float64, F (m,3) int64), s transformacemi uzlu"""
    js, bn = read_glb(path)
    Vs, Fs, base = [], [], 0
    def walk(ni, M):
        nonlocal base
        n = js['nodes'][ni]; M2 = M @ _node_matrix(n)
        if 'mesh' in n:
            for pr in js['meshes'][n['mesh']]['primitives']:
                if pr.get('mode', 4) != 4: continue
                P = _accessor(js, bn, pr['attributes']['POSITION']).astype(float)
                P = (np.c_[P, np.ones(len(P))] @ M2.T)[:, :3]
                F = _accessor(js, bn, pr['indices']).astype(np.int64).reshape(-1, 3) if 'indices' in pr else np.arange(len(P)).reshape(-1, 3)
                Vs.append(P); Fs.append(F + base); base += len(P)
        for c in n.get('children', []): walk(c, M2)
    for sn in js['scenes'][js.get('scene', 0)]['nodes']: walk(sn, np.eye(4))
    return np.vstack(Vs), np.vstack(Fs)


# ======================================================================================================================
# 2) mesh utility: svarovani, zahozeni degenerovanych, normaly s hranou (crease), transformace
# ======================================================================================================================
def weld(V, F, tol=1e-4):
    key = np.round(V / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.reshape(-1)
    V2 = V[first]; F2 = inv[F]
    ok = (F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 0] != F2[:, 2])
    F2 = F2[ok]
    a = V2[F2[:, 1]] - V2[F2[:, 0]]; b = V2[F2[:, 2]] - V2[F2[:, 0]]
    area = np.linalg.norm(np.cross(a, b), axis=1)
    F2 = F2[area > 1e-9]
    used = np.unique(F2)
    remap = -np.ones(len(V2), np.int64); remap[used] = np.arange(len(used))
    return V2[used], remap[F2]


def crease_normals(V, F, angle_deg=35.0):
    """vrati (V2, N2, F2): vrcholy rozdelene podle hran ostrejsich nez angle_deg, normaly vazene uhlem u vrcholu"""
    V = np.asarray(V, float); F = np.asarray(F, np.int64)
    nF = len(F)
    e1 = V[F[:, 1]] - V[F[:, 0]]; e2 = V[F[:, 2]] - V[F[:, 0]]
    fn = np.cross(e1, e2); ar = np.linalg.norm(fn, axis=1); fn = fn / np.maximum(ar[:, None], 1e-30)
    # uhly u rohu
    ang = np.zeros((nF, 3))
    for k in range(3):
        a = V[F[:, (k + 1) % 3]] - V[F[:, k]]; b = V[F[:, (k + 2) % 3]] - V[F[:, k]]
        ca = np.einsum('ij,ij->i', a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-30)
        ang[:, k] = np.arccos(np.clip(ca, -1, 1))
    cv = F.ravel(); cf = np.repeat(np.arange(nF), 3); cw = ang.ravel()
    order = np.argsort(cv, kind='stable'); cv_s = cv[order]
    starts = np.r_[0, np.nonzero(np.diff(cv_s))[0] + 1, len(cv_s)]
    cos_t = math.cos(math.radians(angle_deg))
    newV, newN, cornermap = [], [], np.zeros(len(cv), np.int64)
    for gi in range(len(starts) - 1):
        idx = order[starts[gi]:starts[gi + 1]]
        v = cv[idx[0]]
        fns = fn[cf[idx]]; ws = cw[idx]
        D = fns @ fns.T
        keys = {}
        for ci in range(len(idx)):
            m = D[ci] >= cos_t
            n = (fns[m] * ws[m][:, None]).sum(0)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-12 else fns[ci]
            key = tuple(np.round(n, 3))
            if key not in keys:
                keys[key] = len(newV); newV.append(V[v]); newN.append(n)
            cornermap[idx[ci]] = keys[key]
    F2 = cornermap.reshape(-1, 3)
    return np.array(newV), np.array(newN), F2


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Mesh:
    """V (n,3), N (n,3), F (m,3) + nazev materialu"""
    def __init__(self, V, N, F, material):
        self.V = np.asarray(V, float); self.N = np.asarray(N, float); self.F = np.asarray(F, np.int64); self.material = material

    def transformed(self, R=None, t=None, S=None):
        V = self.V.copy(); N = self.N.copy()
        if S is not None: V = V * np.asarray(S)
        if R is not None:
            R = np.asarray(R, float)
            if abs(np.linalg.det(R) - 1.0) > 1e-6: raise ValueError('transformace mesh neni proper rotace (det=%.3f)' % np.linalg.det(R))
            V = V @ R.T; N = N @ R.T
        if t is not None: V = V + np.asarray(t, float)
        return Mesh(V, N, self.F.copy(), self.material)

    @property
    def tris(self): return len(self.F)

    def bounds(self): return self.V.min(0), self.V.max(0)


def decimate_qem(V, F, target_faces, flip_dot=0.35, endpoints_only=True):
    """zjednoduseni uzavrene site (quadric error metrics, Garland-Heckbert): sklapeni hran az na target_faces trojuhelniku.
    Zachovava tvar (male detaily jako zavit v dirce se slouci jako prvni); hrany, ktere by prevratily trojuhelnik nebo porusily
    varietu, se preskoci."""
    import heapq
    V = np.array(V, float); F = np.array(F, np.int64)
    n = len(V)
    face = [tuple(f) for f in F]
    alive = [True] * len(face)
    vf = [set() for _ in range(n)]
    for fi, (a, b, c) in enumerate(face):
        vf[a].add(fi); vf[b].add(fi); vf[c].add(fi)
    nb = [set() for _ in range(n)]
    for (a, b, c) in face:
        nb[a].update((b, c)); nb[b].update((a, c)); nb[c].update((a, b))
    Q = np.zeros((n, 4, 4))
    def fplane(a, b, c):
        nrm = np.cross(V[b] - V[a], V[c] - V[a]); ar = np.linalg.norm(nrm)
        if ar < 1e-12: return None, 0.0
        nrm = nrm / ar
        return np.append(nrm, -nrm @ V[a]), ar / 2.0
    for (a, b, c) in face:
        pl, ar = fplane(a, b, c)
        if pl is None: continue
        K = np.outer(pl, pl) * ar
        Q[a] += K; Q[b] += K; Q[c] += K
    ver = [0] * n
    def best_pos(a, b):
        Qm = Q[a] + Q[b]
        A = Qm.copy(); A[3] = [0, 0, 0, 1]
        cands = [V[a], V[b]] if endpoints_only else [V[a], V[b], 0.5 * (V[a] + V[b])]
        if (not endpoints_only) and abs(np.linalg.det(A)) > 1e-12:
            try:
                x = np.linalg.solve(A, np.array([0, 0, 0, 1.0]))[:3]
                if np.linalg.norm(x - cands[2]) <= 1.5 * np.linalg.norm(V[a] - V[b]) + 1e-9: cands.insert(0, x)
            except np.linalg.LinAlgError:
                pass
        bestc, bestx = None, None
        for x in cands:
            xv = np.append(x, 1.0); c = float(xv @ Qm @ xv)
            if bestc is None or c < bestc: bestc, bestx = c, x
        return bestc, bestx
    heap = []; cnt = 0
    for a in range(n):
        for b in nb[a]:
            if a < b:
                c, x = best_pos(a, b); heap.append((c, cnt, a, b, ver[a], ver[b], x)); cnt += 1
    heapq.heapify(heap)
    nfaces = len(face)
    while heap and nfaces > target_faces:
        c, _, a, b, va, vb, x = heapq.heappop(heap)
        if ver[a] != va or ver[b] != vb or b not in nb[a]: continue
        shared = vf[a] & vf[b]
        if len(shared) != 2 or len(nb[a] & nb[b]) != 2: continue      # varieta (link condition)
        ok = True
        for fi in (vf[a] | vf[b]) - shared:
            f = face[fi]
            old = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])
            g = [a if q in (a, b) else q for q in f]
            P = [x if q == a else V[q] for q in g]
            new = np.cross(P[1] - P[0], P[2] - P[0])
            lo, ln = np.linalg.norm(old), np.linalg.norm(new)
            if ln < 1e-10 or lo < 1e-12 or (old @ new) / (lo * ln) < flip_dot: ok = False; break
        if not ok: continue
        # sklopeni b -> a
        V[a] = x; Q[a] = Q[a] + Q[b]; ver[a] += 1; ver[b] += 1
        for fi in shared:
            alive[fi] = False; nfaces -= 1
            for q in face[fi]: vf[q].discard(fi)
        for fi in list(vf[b]):
            face[fi] = tuple(a if q == b else q for q in face[fi]); vf[a].add(fi)
        vf[b] = set()
        for w in nb[b]:
            nb[w].discard(b)
            if w != a: nb[w].add(a); nb[a].add(w)
        nb[a].discard(a); nb[a].discard(b); nb[b] = set()
        for w in nb[a]:
            ca, xa = best_pos(a, w) if a < w else best_pos(w, a)
            lo_, hi_ = (a, w) if a < w else (w, a)
            heapq.heappush(heap, (ca, cnt, lo_, hi_, ver[lo_], ver[hi_], xa)); cnt += 1
    keep = [i for i in range(len(face)) if alive[i]]
    F2 = np.array([face[i] for i in keep], np.int64)
    used = np.unique(F2)
    remap = -np.ones(n, np.int64); remap[used] = np.arange(len(used))
    return V[used], remap[F2]


# ======================================================================================================================
# 3) zapisovac GLB (JSON + BIN), deterministicky
# ======================================================================================================================
class GLBWriter:
    def __init__(self):
        self.bin = bytearray(); self.views = []; self.accessors = []

    def _view(self, data, target=None):
        while len(self.bin) % 4: self.bin.append(0)
        off = len(self.bin); self.bin.extend(data)
        v = {'buffer': 0, 'byteOffset': off, 'byteLength': len(data)}
        if target: v['target'] = target
        self.views.append(v); return len(self.views) - 1

    def accessor(self, arr, ctype, atype, target=None, minmax=False):
        arr = np.ascontiguousarray(arr)
        vi = self._view(arr.tobytes(), target)
        a = {'bufferView': vi, 'componentType': ctype, 'count': int(arr.shape[0]), 'type': atype}
        if minmax:
            a2 = arr.reshape(arr.shape[0], -1)
            a['min'] = [float(x) for x in a2.min(0)]; a['max'] = [float(x) for x in a2.max(0)]
        self.accessors.append(a); return len(self.accessors) - 1

    def finish(self, gltf):
        gltf = dict(gltf)
        gltf['bufferViews'] = self.views; gltf['accessors'] = self.accessors
        gltf['buffers'] = [{'byteLength': len(self.bin)}]
        js = json.dumps(gltf, ensure_ascii=True, separators=(',', ':')).encode('ascii')
        while len(js) % 4: js += b' '
        bn = bytes(self.bin)
        while len(bn) % 4: bn += b'\x00'
        total = 12 + 8 + len(js) + 8 + len(bn)
        out = struct.pack('<III', 0x46546C67, 2, total)
        out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
        return out


# ======================================================================================================================
# 4) prurez profilu a merení T-drazky (z rezu GLB, bez zavislosti na trimesh)
# ======================================================================================================================
def section_segments(V, F, axis, level):
    d = V[F, axis] - level
    s = d > 0
    mix = s.any(1) & (~s).any(1)
    segs = []
    for f, dd in zip(F[mix], d[mix]):
        pts = []
        for i in range(3):
            j = (i + 1) % 3
            if (dd[i] > 0) != (dd[j] > 0):
                t = dd[i] / (dd[i] - dd[j])
                pts.append(V[f[i]] + t * (V[f[j]] - V[f[i]]))
        if len(pts) == 2: segs.append(pts)
    return np.array(segs)


def chain_loops(segs, tol=1e-4):
    key = lambda p: tuple(np.round(p / tol).astype(np.int64))
    adj = {}
    for i, (a, b) in enumerate(segs):
        adj.setdefault(key(a), []).append((i, 0)); adj.setdefault(key(b), []).append((i, 1))
    used = np.zeros(len(segs), bool); loops = []
    for i0 in range(len(segs)):
        if used[i0]: continue
        used[i0] = True
        pts = [segs[i0][0], segs[i0][1]]; cur = key(segs[i0][1]); start = key(segs[i0][0]); guard = 0
        while cur != start and guard < len(segs) + 5:
            guard += 1; nxt = None
            for (j, e) in adj.get(cur, []):
                if not used[j]: nxt = (j, e); break
            if nxt is None: break
            j, e = nxt; used[j] = True
            p = segs[j][1 - e]; pts.append(p); cur = key(p)
        loops.append(np.array(pts[:-1] if cur == start else pts))
    return loops


def poly_area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def drop_collinear(p, tol=1e-6):
    keep = []
    n = len(p)
    for i in range(n):
        a = p[(i - 1) % n]; b = p[i]; c = p[(i + 1) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cr) > tol * max(1.0, np.linalg.norm(c - a)): keep.append(i)
    return p[keep]


def profile_section(profile_glb):
    V, F = load_glb_geometry(profile_glb); V, F = weld(V, F)
    z0, z1 = V[:, 2].min(), V[:, 2].max()
    segs = section_segments(V, F, 2, 0.5 * (z0 + z1) + 0.37)
    loops = [drop_collinear(l[:, :2]) for l in chain_loops(segs)]
    return V, F, loops, (float(z0), float(z1))


def slot_polyline(outer):
    """usek vnejsi smycky: od horniho povrchu (leva zem) dolu pres drazku a zpet nahoru (zleva doprava)"""
    ymax = outer[:, 1].max(); n = len(outer)
    cand = [i for i in range(n) if abs(outer[i, 0]) < 1.0 and outer[i, 1] > 0 and outer[i, 1] < ymax - 5]
    seed = min(cand, key=lambda i: abs(outer[i, 0]))
    top = lambda i: outer[i % n, 1] >= ymax - 1e-6
    i0 = seed
    while not top(i0): i0 -= 1
    i1 = seed
    while not top(i1): i1 += 1
    pl = np.array([outer[k % n] for k in range(i0, i1 + 1)])
    if pl[0, 0] > pl[-1, 0]: pl = pl[::-1]
    return pl


def measure_slot(profile_glb):
    V, F, loops, (z0, z1) = profile_section(profile_glb)
    areas = [abs(poly_area(l)) for l in loops]
    outer = loops[int(np.argmax(areas))]
    pl = slot_polyline(outer)
    ymax = float(outer[:, 1].max()); half = float(outer[:, 0].max())
    p = pl
    ok = (abs(p[0, 0] - p[1, 0]) < 1e-6 and abs(p[1, 1] - p[2, 1]) < 1e-6 and abs(p[2, 0] - p[3, 0]) < 1e-6 and
          abs(p[3, 1] - p[4, 1]) < 1e-6 and abs(p[4, 0] - p[5, 0]) < 1e-6)
    if not ok: raise RuntimeError('prurez drazky nema ocekavanou strukturu T-drazky: ' + repr(p[:8].tolist()))
    d = {}
    d['povrch_y'] = ymax
    d['zapusteni_pul_sirka'] = float(-p[0, 0]); d['zapusteni_hloubka'] = float(ymax - p[1, 1])
    d['okraj_horni_y'] = float(p[1, 1]); d['okraj_horni_sirka'] = float(p[2, 0] - p[1, 0])
    d['krcek_pul_sirka'] = float(-p[2, 0]); d['krcek_sirka'] = float(-2 * p[2, 0])
    d['krcek_hloubka'] = float(p[2, 1] - p[3, 1])
    d['strop_komory_y'] = float(p[3, 1])
    d['komora_pul_sirka'] = float(-p[4, 0]); d['komora_sirka'] = float(-2 * p[4, 0])
    d['komora_svisla_stena_dole_y'] = float(p[5, 1]); d['komora_svisla_vyska'] = float(p[3, 1] - p[5, 1])
    d['sikmina_dole'] = [float(-p[6, 0]), float(p[6, 1])]
    d['sikmina_uhel_deg'] = float(math.degrees(math.atan2(p[5, 1] - p[6, 1], p[6, 0] - p[5, 0]))) if p[6, 0] > p[5, 0] else None
    fl = p[6:len(p) - 6]
    fl = fl[np.abs(fl[:, 0]) <= abs(p[6, 0]) + 1e-6]
    d['dno_y_min'] = float(fl[:, 1].min()); d['dno_y_max'] = float(fl[:, 1].max())
    center = fl[np.argmin(np.abs(fl[:, 0]))]
    d['dno_stred_y'] = float(center[1])
    d['komora_hloubka_pod_stropem_max'] = float(p[3, 1] - fl[:, 1].min())
    d['polyline'] = [[float(a), float(b)] for a, b in pl]
    d['prurez_smycky'] = [len(l) for l in loops]
    d['profil_z_rozsah'] = [z0, z1]
    d['profil_vnejsi_pul_sirka'] = half
    d['plocha_materialu_mm2'] = float(max(areas) - sum(sorted(areas)[:-1]))
    return d, loops


# ======================================================================================================================
# 5) sroub M6 imbus (proceduralni): hlava valcova (cap) nebo zapustna (csk), imbus, zavit jako sroubovice
# ======================================================================================================================
def _ring(n, r, y, rfun=None):
    th = 2 * np.pi * np.arange(n) / n
    rr = np.full(n, r, float) if rfun is None else np.array([rfun(t) for t in th])
    return np.stack([rr * np.cos(th), np.full(n, y), -rr * np.sin(th)], 1)


def _hex_r(theta, s):
    """polomer sestiuhelniku (rozmer pres ploky s) ve smeru theta (vrcholy v 0, 60, ... deg)"""
    ap = s / 2.0
    k = (theta % (np.pi / 3)) - np.pi / 6
    return ap / math.cos(k)


def make_screw(L, head='csk', n=40, pitch=1.5, crest=3.0, root=2.55, material='sroub'):
    """lokalni soustava: pocatek uprostred dosedaci plochy hlavy na ose, hlava +Y, drik -Y (delka L); zavit pravotocivy"""
    rows = []
    if head == 'cap':
        hk, hr = 6.0, 5.0
        sock_depth, sock_s = 3.0, 5.0
        rows.append(('pt', np.array([[0, hk - sock_depth, 0]])))
        rows.append(('ring', _ring(n, 0, hk - sock_depth, lambda t: _hex_r(t, sock_s))))
        rows.append(('ring', _ring(n, 0, hk, lambda t: _hex_r(t, sock_s))))
        rows.append(('ring', _ring(n, hr - 0.45, hk)))
        rows.append(('ring', _ring(n, hr, hk - 0.45)))
        rows.append(('ring', _ring(n, hr, 0.4)))
        rows.append(('ring', _ring(n, hr - 0.4, 0.0)))
        rows.append(('ring', _ring(n, crest, 0.0)))
    else:   # csk (ISO 10642): dk 12, k 3.3, imbus 4
        hk = 3.3; sock_depth, sock_s = 2.4, 4.0
        rows.append(('pt', np.array([[0, hk - sock_depth, 0]])))
        rows.append(('ring', _ring(n, 0, hk - sock_depth, lambda t: _hex_r(t, sock_s))))
        rows.append(('ring', _ring(n, 0, hk, lambda t: _hex_r(t, sock_s))))
        rows.append(('ring', _ring(n, 5.8, hk)))
        rows.append(('ring', _ring(n, 6.0, hk - 0.2)))
        rows.append(('ring', _ring(n, 6.0, 3.0)))
        rows.append(('ring', _ring(n, crest, 0.0)))
    dy = pitch / 4.0
    ytip0 = -(L - 0.9)
    y = 0.0
    th = 2 * np.pi * np.arange(n) / n
    ys = []
    while y > ytip0 + 1e-9:
        ys.append(y); y -= dy
    ys.append(ytip0)
    for yy in ys:
        ph = yy / pitch - th / (2 * np.pi)
        fr = ph - np.floor(ph)
        tri = 1.0 - np.abs(2 * fr - 1.0)
        rr = root + (crest - root) * tri
        rows.append(('ring', np.stack([rr * np.cos(th), np.full(n, yy), -rr * np.sin(th)], 1)))
    rows.append(('ring', _ring(n, root - 0.35, -L)))
    rows.append(('pt', np.array([[0, -L, 0]])))
    verts, faces = [], []
    prev = None
    for kind, data in rows:
        start = len(verts)
        verts.extend(data.tolist())
        cur = (kind, start, len(data))
        if prev is not None:
            pk, ps, pn = prev
            if pk == 'pt':
                for i in range(n): faces.append([ps, start + (i + 1) % n, start + i])
            elif kind == 'pt':
                for i in range(n): faces.append([ps + i, ps + (i + 1) % n, start])
            else:
                for i in range(n):
                    a, b = ps + i, ps + (i + 1) % n; c, d = start + i, start + (i + 1) % n
                    faces.append([a, c, b]); faces.append([b, c, d])
        prev = cur
    V = np.array(verts); F = np.array(faces, np.int64)
    vol = np.einsum('ij,ij->', V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])) / 6.0
    if vol < 0: F = F[:, ::-1]
    V, F = weld(V, F, 1e-6)
    V2, N2, F2 = crease_normals(V, F, 40.0)
    return Mesh(V2, N2, F2, material)


# ======================================================================================================================
# 6) katalogove dily: orientace, osa dirky, dosedaci vyska sroubu (z geometrie)
# ======================================================================================================================
def fit_circle(p):
    x, y = p[:, 0], p[:, 1]
    A = np.stack([2 * x, 2 * y, np.ones_like(x)], 1)
    sol, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
    cx, cy = sol[0], sol[1]
    return float(cx), float(cy), float(np.sqrt(max(sol[2] + cx * cx + cy * cy, 0)))


def ray_down_first_hit(V, F, pts_xz, y_from):
    """prvni zasah svisleho paprsku (smer -Y) z vysky y_from pro body (x,z); vrati vysku zasahu (nan = mimo)"""
    v0 = V[F[:, 0]]; e1 = V[F[:, 1]] - v0; e2 = V[F[:, 2]] - v0
    d = np.array([0.0, -1.0, 0.0])
    h = np.cross(d, e2); a = np.einsum('ij,ij->i', e1, h)
    ok = np.abs(a) > 1e-12
    f = np.zeros_like(a); f[ok] = 1.0 / a[ok]
    out = np.full(len(pts_xz), np.nan)
    for k, (x, z) in enumerate(pts_xz):
        o = np.array([x, y_from, z]); s = o - v0
        u = f * np.einsum('ij,ij->i', s, h)
        q = np.cross(s, e1); v = f * (q @ d); t = f * np.einsum('ij,ij->i', e2, q)
        m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
        if m.any(): out[k] = y_from - t[m].min()
    return out


def orient_part(cat, key, spec):
    """nacte dil (spec['file']: cesta relativne ke katalogu, nebo absolutni), otoci ho do sceny (osa dirky svisle, dosedaci rovina Y=0,
    telo nahoru), pocatek na ose dirky"""
    path = spec['file'] if os.path.isabs(spec['file']) else os.path.join(cat, spec['file'])
    V, F = load_glb_geometry(path); V, F = weld(V, F)
    tris_orig = len(F)
    if spec.get('target_tris') and len(F) > spec['target_tris']:
        V, F = decimate_qem(V, F, spec['target_tris'])
    R = spec['R']
    if abs(np.linalg.det(R) - 1) > 1e-9: raise ValueError('R neni proper rotace: ' + key)
    Vr = V @ R.T
    # osa dirky: kruznice z vrcholu dosedaci roviny (Y = min) blizko ocekavane polohy
    ymin = Vr[:, 1].min()
    base = Vr[np.abs(Vr[:, 1] - ymin) < 1e-4]
    ap = np.array(spec['hole_approx_xz'], float)
    sel = base[np.hypot(base[:, 0] - ap[0], base[:, 2] - ap[1]) < spec['hole_search_r']]
    cx, cz, r = fit_circle(sel[:, [0, 2]])
    if spec.get('axis_from_bbox'):      # matice: osa dirky = stred obalky dosedaci plochy (zavit vrta kruznici o ~0,2 mm)
        cx = 0.5 * (base[:, 0].min() + base[:, 0].max()); cz = 0.5 * (base[:, 2].min() + base[:, 2].max())
    Vl = Vr - np.array([cx, ymin, cz])
    m = Mesh(*crease_normals(Vl, F, 35.0), spec['material'])
    # profil povrchu kolem dirky (vyska povrchu nad dosedaci rovinou) pro dosedaci vysku sroubu
    angs = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    radii = np.arange(r + 0.05, 6.6, 0.1)
    prof = {}
    for rr in radii:
        pts = np.stack([rr * np.cos(angs), rr * np.sin(angs)], 1)
        hs = ray_down_first_hit(Vl, F, pts, 60.0)
        prof[round(float(rr), 3)] = hs
    return m, dict(hole_r=r, hole_center_partlocal=[cx, cz], base_y_before=float(ymin), funnel=prof, V=Vl, F=F, tris_orig=tris_orig)


def seat_height(info, head='csk'):
    """nejnizsi vyska dosedaci roviny hlavy nad dosedaci rovinou dilu tak, aby hlava nezasahla do dilu"""
    best = 0.0
    for rr, hs in info['funnel'].items():
        if head == 'cap':
            if rr > 5.0: continue
            g = max(0.0, rr - 4.6)
        else:
            if rr > 6.0: continue
            g = rr - 3.0
        h = np.nanmax(hs) if np.isfinite(hs).any() else 0.0
        best = max(best, h - g)
    return float(best) + 0.05   # rezerva: funel je mnohouhelnik a paprsky ho vzorkuji po 0,1 mm


# ======================================================================================================================
# 7) animace: easing, trajektorie uzlu po 1/30 s
# ======================================================================================================================
FPS = 30


def clamp01(x): return np.clip(x, 0.0, 1.0)
def ramp(t, a, b): return clamp01((np.asarray(t, float) - a) / (b - a))
def e_io(p): return p * p * (3 - 2 * p)
def e_out(p): return 1 - (1 - p) ** 3
def e_in(p): return p ** 3
def e_lin(p): return p


def e_trap(p, r=0.18):
    """lichobeznikovy profil rychlosti (rozjezd r, konstantni rychlost, dobrzdeni r): p v <0,1> -> poloha <0,1>"""
    p = np.asarray(p, float); v = 1.0 / (1.0 - r)
    a = v * p * p / (2 * r)
    b = v * (r / 2 + (p - r))
    c = 1 - v * (1 - p) ** 2 / (2 * r)
    return np.where(p < r, a, np.where(p <= 1 - r, b, c))


def quat_y(a):
    a = np.asarray(a, float)
    q = np.zeros(a.shape + (4,)); q[..., 1] = np.sin(a / 2); q[..., 3] = np.cos(a / 2)
    return q


# ======================================================================================================================
# 8) DATOVA CAST: casovani a seznam upevneni. SEM se pridavaji dalsi dily (viz README "Jak pridat dalsi dil").
# ======================================================================================================================
# Casy pohybu se zapisuji v "autorskych sekundach" A (tempo puvodni verze 1) a nasobi se globalni konstantou TIME_SCALE; pauzy (intro,
# slot, zaverecne "cokoli") jsou v REALNYCH sekundach a TIME_SCALE se na ne neuplatnuje (popisek musi zustat citelny aspon MIN_CUE_S).
TIME_SCALE = 1.0 / 1.4        # klip je 1,4x rychlejsi nez verze 1 (29,2 s -> ~21 s)
INTRO_S = 2.2                 # pauza: profil sam, pomaly pohled (cue intro)
SLOT_S = 2.2                  # pauza: pohled na celo drazky (cue slot)
FINAL_HOLD_S = 2.2            # pauza na konci: vse pripnuto, celek (cue cokoli, pred rozpustenim)
MIN_CUE_S = 2.2               # nejkratsi povolena delka cue (test_kroky.py to kontroluje)
GROW_S = 0.3                  # nabeh meritka 0 -> 1 / zanik 1 -> 0 v REALNYCH s (rychly narust, nikdy skok)
DISSOLVE_A = 2.2              # rozpusteni na konci (A): sroubky mizi prvni, pak dily a matice, nakonec neviditelny navrat do vychozich poloh
# stavebni kameny jednoho upevneni (A): sroub se zasune bez otaceni (INS), pak otaci a zasouva (TURN), nakonec klid (SETTLE)
SCREW_INS_A, SCREW_TURN_A, SCREW_SETTLE_A = (0.1, 1.1), 3.2, 0.5
PART_DESCEND_A = 1.4          # dil sjede shora o PART_HEIGHT mm
PART_HEIGHT = 55.0
SCREW_HEIGHT = 35.0           # sroub se zasouva z teto vysky nad dotykem
NUT_DROP_HEIGHT = 60.0        # otocna matice sjizdi z teto vysky

MATERIALS = {
    # nazev: (baseColor linearne, metallic, roughness)
    'alu_profil': ([0.50, 0.49, 0.46, 1.0], 1.0, 0.28),      # svetly hlinik (podpis hliniku vieweru: kovovy, 0,3-0,7, drsnost 0,15-0,45)
    'kamen': ([0.60, 0.62, 0.66, 1.0], 0.90, 0.55),          # pozinkovana ocel
    'otocna': ([0.62, 0.40, 0.10, 1.0], 0.90, 0.38),         # mosaz / zlute chromatovani
    'sroub': ([0.030, 0.030, 0.035, 1.0], 0.60, 0.42),       # cerneny sroub
    'dil1': ([0.52, 0.56, 0.62, 1.0], 0.85, 0.45),           # zinek (uhelnik)
    'dil2': ([0.14, 0.16, 0.19, 1.0], 0.75, 0.42),           # tmava ocel (pant)
}


def K(at, dA, tx, ty, az, el, fit, ease='inout', absx=False):
    """klic kamery pro upevneni: cas = (at: 'start'|'part'|'screw'|'end') + dA autorskych s; cil (tx [relativne k x upevneni, s absx=True absolutne], ty, 0),
    azimut az (0 = zepredu z +Z, kladny k -X), elevace el (st.), fit = polomer (mm), ktery se musi vejit do zaberu"""
    return dict(at=at, dA=dA, tx=tx, ty=ty, az=az, el=el, fit=fit, ease=ease, absx=absx)


# Jedno upevneni = matice (nut) + dil (part) + sroub (screw) na pozici x (mm podel profilu). Poradi v seznamu = poradi v klipu.
#   nut.kind: 'slide' = kamen: zasune se z cela profilu podel drazky a pri dotahovani se zvedne k okrajum;
#             'drop_turn' = otocna matice: sjede shora podel drazky na dno komory, pri dotahovani se sama otoci o 90 st. a zvedne
#   file: product_<id>.glb relativne ke katalogu (--katalog), nebo 'zdroje/...' relativne k tomuto skriptu (--zdroje)
#   R: otoceni dilu z lokalnich os GLB do sceny (osa dirky svisle = Y, dosedaci rovina = nejnizsi Y); hole_approx_xz = stred dirky v osach po R
#   t (A, od zacatku upevneni): part = zacatek sjezdu dilu, screw = zacatek sroubu, cue_split = konec cue matice, end = konec (klid)
#   g: cislo uzlu pro viewer (klik/zvyrazneni); bez g se prideli dalsi volne cislo (stavajici zustavaji stabilni)
def default_fastenings():
    return [
        dict(id='kamen', x=-60.0,
             nut=dict(node='kamen', g=1, kind='slide', file='product_3592.glb', material='kamen', R=rot_y(math.pi / 2), hole_approx_xz=(0, 0),
                      hole_search_r=3.6, axis_from_bbox=True, target_tris=3000, head_zmin=5.2, anchor=(6.0, 8.0, 0.0)),
             part=dict(node='dil1', g=5, file='zdroje/uhelnik_3045_vysoka_kvalita.glb', material='dil1', R=rot_x(math.pi / 2),
                       hole_approx_xz=(15.0, 14.0), hole_search_r=4.2, anchor=(9.0, 3.0, 0.0)),
             screw=dict(node='sroub1', g=3, L=12.0, turns=4, anchor=(3.8, 2.0, 0.0)),
             t=dict(part=3.5, screw=5.3, cue_split=3.5, end=10.1),
             cues=[dict(id='kamen', anchor='nut', side='left', g=['nut']),
                   dict(id='srouby1', anchor='screw', side='right', g=['part', 'screw', 'nut'])],
             camera=[K('start', 0.0, -150, 32, 60, 15, 42, absx=True), K('start', 0.7, -150, 32, 56, 18, 42, 'linear', absx=True),
                     K('start', 1.9, -108, 34, 54, 24, 46, 'linear', absx=True), K('start', 3.1, -2, 38, 40, 30, 48),
                     K('part', 0.3, 0, 54, 18, 26, 55), K('screw', 0.0, 0, 58, -26, 28, 52), K('screw', 1.1, 0, 46, -34, 34, 38),
                     K('end', -0.5, 0, 46, -34, 34, 38)]),
        dict(id='otocna', x=140.0,
             nut=dict(node='otocna', g=2, kind='drop_turn', file='product_3582.glb', material='otocna', R=np.eye(3), hole_approx_xz=(0, 0),
                      hole_search_r=3.6, axis_from_bbox=True, plate_y_range=(5.5, 7.0), sense=-1, anchor=(6.5, 3.0, 0.0)),
             part=dict(node='dil2', g=6, file='product_3325.glb', material='dil2', R=np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], float),
                       hole_approx_xz=(40.0, 12.1), hole_search_r=4.4, anchor=(-15.0, 4.5, 0.0)),
             screw=dict(node='sroub2', g=4, L=14.0, turns=4, anchor=(3.8, 2.0, 0.0)),
             t=dict(part=1.7, screw=3.2, cue_split=3.2, end=8.0),
             cues=[dict(id='otocna', anchor='nut', side='right', g=['nut', 'part']),
                   dict(id='srouby2', anchor='screw', side='left', g=['screw', 'nut', 'part'])],
             camera=[K('start', 0.4, -5, 57, 0, 30, 48), K('part', 0.2, -8, 60, 14, 28, 62),
                     K('screw', 1.7, 0, 33, -66, 12, 27), K('end', 0.0, 0, 33, -64, 14, 27)]),
    ]


# alternativni kamen: ctvercova matice M6 (produkt 3066), do drazky se nevejde (viz README) - jen pro srovnani (--kamen 3066)
ALT_STONE_3066 = dict(node='kamen', g=1, kind='slide', file='product_3066.glb', material='kamen', R=rot_x(-math.pi / 2), hole_approx_xz=(0, 0),
                      hole_search_r=3.6, axis_from_bbox=True, anchor=(6.0, 3.0, 0.0))


# ======================================================================================================================
# 9) sestaveni sceny: rozmery, polohy, casovani a trajektorie (obecne pro libovolny pocet upevneni)
# ======================================================================================================================
def build(args):
    cat = args.katalog
    here = os.path.dirname(os.path.abspath(__file__))
    zdroje = args.zdroje or os.path.join(here, 'zdroje')
    slot, loops = measure_slot(args.profile)
    Y0 = 20.0     # posun profilu: spodek Y=0, horni plocha Y=40
    surf = Y0 + slot['povrch_y']                  # 40
    ceil_y = Y0 + slot['strop_komory_y']          # 34   (spodek okraju = strop komory)
    pl = np.array(slot['polyline'])
    floor_peak = float(pl[(np.abs(pl[:, 0]) <= 5.4) & (pl[:, 1] < 10)][:, 1].max())   # nejvyssi bod dna pod ploskym spodkem matice
    head = args.head
    xmin_prof, xmax_prof = -150.0, 150.0

    # ---- profil (X = 0,3 pz + 150; Y = py + 20; Z = -px; proper rotace + meritko delky)
    V, F = load_glb_geometry(args.profile); V, F = weld(V, F)
    Vs = np.stack([0.3 * V[:, 2] + 150.0, V[:, 1] + Y0, -V[:, 0]], 1)
    Vp, Np, Fp = crease_normals(Vs, F, 35.0)
    profil = Mesh(Vp, Np, Fp, 'alu_profil')

    # ---- upevneni: zdroje, orientace, rozmery
    FS = default_fastenings()
    if args.kamen == 3066:
        FS[0]['nut'] = dict(ALT_STONE_3066)
    def src(spec, override=None):
        f = override or spec['file']
        spec['file'] = os.path.join(zdroje, f[len('zdroje/'):]) if f.startswith('zdroje/') else f
    for f in FS:
        for role in ('nut', 'part'):
            src(f[role], args.uhelnik_glb if (args.uhelnik_glb and f[role]['node'] == 'dil1') else None)
    for f in FS:
        for role in ('nut', 'part'):
            m, inf = orient_part(cat, f[role]['node'], f[role])
            f[role]['mesh'] = m; f[role]['info'] = inf
        nm, nu = f['nut']['mesh'], f['nut']
        kv = nm.V
        nu['top'] = float(kv[:, 1].max())
        if nu['kind'] == 'slide':
            nu['head_top'] = float(kv[np.abs(kv[:, 2]) > nu['head_zmin']][:, 1].max()) if nu.get('head_zmin') else nu['top']
            nu['y_tight'] = ceil_y - nu['head_top'] - 0.08         # hlava kamene dosedne na strop komory (0,08 mm rezerva proti sumu decimace)
            nu['y_start'] = nu['y_tight'] - 0.4                    # pri zasouvani je 0,4 mm pod okraji
        elif nu['kind'] == 'drop_turn':
            lo, hi = nu['plate_y_range']
            nu['plate_top'] = float(kv[(kv[:, 1] > lo) & (kv[:, 1] < hi)][:, 1].max())     # spicky zubu
            nu['y_start'] = Y0 + floor_peak + 0.01                 # dno komory (hrebeny dna)
            nu['y_tight'] = ceil_y - nu['plate_top']
        else:
            raise ValueError('neznamy druh matice: ' + nu['kind'])
        f['seat'] = seat_height(f['part']['info'], head)
        sc = f['screw']
        sc['y_seat'] = surf + f['seat']
        sc['y_contact'] = nu['y_start'] + nu['top'] + sc['L']
        sc['travel'] = sc['y_contact'] - sc['y_seat']
        sc['pitch'] = sc['travel'] / sc['turns']
        sc['mesh'] = make_screw(sc['L'], head, pitch=sc['pitch'])

    # ---- casovani (s): upevneni za sebou, pak zaverecna pauza + rozpusteni; vse pocitano z dat
    A = lambda a: a * TIME_SCALE
    t = INTRO_S + SLOT_S
    T = {'intro': 0.0, 'slot': INTRO_S, 'first': t}
    for f in FS:
        f['t0'] = t
        f['T'] = {k: f['t0'] + A(v) for k, v in f['t'].items()}
        t = f['T']['end']
    T['cokoli'] = t                       # konec posledniho upevneni = zacatek zaverecne pauzy
    T['reset'] = t + FINAL_HOLD_S         # zacatek rozpusteni
    D = math.ceil((T['reset'] + A(DISSOLVE_A)) * FPS - 1e-9) / FPS
    T['D'] = D
    N = int(round(D * FPS)) + 1
    ts = np.arange(N) / FPS
    gl0 = T['reset'] + A(1.45 + 0.1); gl1 = D - 0.05
    G = e_io(ramp(ts, gl0, gl1))          # neviditelny navrat na vychozi polohu po zmizeni: posledni snimek == prvni
    ZERO = np.zeros(N)
    traj = {}

    def scale_curve(t_grow0, shrink0, shrink1):
        return e_io(ramp(ts, t_grow0, t_grow0 + GROW_S)) * (1.0 - e_io(ramp(ts, shrink0, shrink1)))

    def finish(pos_path, start_pos, final_pos, ang, scale):
        pos = np.asarray(pos_path, float) + G[:, None] * (np.asarray(start_pos, float) - np.asarray(final_pos, float))[None, :]
        return dict(pos=pos, ang=ang, scale=scale)

    sh_part = (T['reset'] + A(0.4), T['reset'] + A(1.4))
    sh_screw = (T['reset'], T['reset'] + A(0.5))
    for f in FS:
        x = f['x']; nu, pa, sc = f['nut'], f['part'], f['screw']
        tf0, tp, tsr = f['t0'], f['T']['part'], f['T']['screw']
        ins0, ins1 = tsr + A(SCREW_INS_A[0]), tsr + A(SCREW_INS_A[1])
        turn0 = ins1; turn1 = turn0 + A(SCREW_TURN_A)
        # matice
        if nu['kind'] == 'slide':
            x_start = xmin_prof - 26.0
            Xn = x_start + (x - x_start) * e_io(ramp(ts, tf0 + A(0.25), tf0 + A(3.25)))
            Yn = nu['y_start'] + (nu['y_tight'] - nu['y_start']) * e_io(ramp(ts, turn1 - A(0.6), turn1))
            pos = np.stack([Xn, Yn, ZERO], 1); ang = ZERO.copy()
            traj[nu['node']] = finish(pos, (x_start, nu['y_start'], 0), (x, nu['y_tight'], 0), ang, scale_curve(tf0, *sh_part))
        else:
            Yn = nu['y_start'] + NUT_DROP_HEIGHT * (1.0 - e_out(ramp(ts, tf0 + A(0.1), tf0 + A(1.5))))
            Yn = Yn + (nu['y_tight'] - nu['y_start']) * e_io(ramp(ts, turn0, turn0 + A(0.45)))
            th = e_io(ramp(ts, turn0, turn0 + A(1.4)))
            ang = nu['sense'] * (math.pi / 2) * th * (1.0 - G)
            pos = np.stack([np.full(N, x), Yn, ZERO], 1)
            traj[nu['node']] = finish(pos, (x, nu['y_start'] + NUT_DROP_HEIGHT, 0), (x, nu['y_tight'], 0), ang, scale_curve(tf0, *sh_part))
        # dil: sjede shora
        Yd = surf + PART_HEIGHT * (1.0 - e_out(ramp(ts, tp, tp + A(PART_DESCEND_A))))
        traj[pa['node']] = finish(np.stack([np.full(N, x), Yd, ZERO], 1), (x, surf + PART_HEIGHT, 0), (x, surf, 0), ZERO.copy(), scale_curve(tp, *sh_part))
        # sroub: zasun bez otaceni, pak otaceni + zasouvani do dosednuti hlavy
        d_desc = e_io(ramp(ts, ins0, ins1))
        rot = e_trap(ramp(ts, turn0, turn1))
        Ys = sc['y_contact'] + SCREW_HEIGHT * (1.0 - d_desc) - sc['travel'] * rot
        traj[sc['node']] = finish(np.stack([np.full(N, x), Ys, ZERO], 1), (x, sc['y_contact'] + SCREW_HEIGHT, 0), (x, sc['y_seat'], 0),
                                  -2 * math.pi * sc['turns'] * rot, scale_curve(tsr, *sh_screw))

    # ---- uzly: poradi (profil, dily, matice, sroubky); g-cisla: explicitni zustavaji, ostatni dalsi volne
    nodes = [dict(name='profil', kind='profil', fastening=None, g=0, mesh=profil, anchor=None)]
    for role in ('part', 'nut', 'screw'):
        for f in FS:
            s = f[role]
            nodes.append(dict(name=s['node'], kind=role, fastening=f['id'], g=s.get('g'), mesh=s['mesh'] if role != 'screw' else s['mesh'], anchor=s['anchor']))
    used = {n['g'] for n in nodes if n['g'] is not None}
    nxt = 1
    for n in nodes:
        if n['g'] is None:
            while nxt in used: nxt += 1
            n['g'] = nxt; used.add(nxt)
    names = [n['name'] for n in nodes]
    if len(set(names)) != len(names): raise ValueError('nazvy uzlu musi byt jedinecne: %r' % names)
    gmap = {n['name']: n['g'] for n in nodes}

    ctx = dict(T=T, D=D, N=N, ts=ts, traj=traj, slot=slot, loops=loops, profil=profil, fastenings=FS, nodes=nodes, gmap=gmap, surf=surf, Y0=Y0,
               ceil_y=ceil_y, floor_peak=floor_peak, head=head, xrange=(xmin_prof, xmax_prof))
    return ctx


# ======================================================================================================================
# 10) metadata (extras.v3d, extras.demo: cues, steps, camera generovane z dat upevneni) a export GLB
# ======================================================================================================================
CUES_TEXT_NOTE = 'cue id = semanticky klic pro texty stranky; t0/t1 v s; anchor = uzel GLB (kotva) nebo null; side = kam dat popisek'


def make_extras(ctx):
    T = ctx['T']; D = ctx['D']; FS = ctx['fastenings']; gm = ctx['gmap']
    A = lambda a: a * TIME_SCALE
    r3 = lambda v: round(float(v), 3)
    gl = lambda f, roles: [gm[f[r]['node']] for r in roles]
    cues = [dict(id='intro', t0=0.0, t1=r3(T['slot']), anchor=None, side='top', g=[0], step='profil'),
            dict(id='slot', t0=r3(T['slot']), t1=r3(T['first']), anchor='a_slot', side='left', g=[0], step='profil')]
    steps = [dict(id='profil', t0=0.0, t1=r3(T['first']), g=[0], cues=['intro', 'slot'])]
    for f in FS:
        tf0 = f['t0']; split = f['T']['cue_split']; end = f['T']['end']
        ids = []
        for k, c in enumerate(f['cues']):
            t0 = tf0 if k == 0 else split
            t1 = split if k == 0 else end
            cues.append(dict(id=c['id'], t0=r3(t0), t1=r3(t1), anchor='a_' + f[c['anchor']]['node'], side=c['side'], g=gl(f, c['g']), step=f['id']))
            ids.append(c['id'])
        steps.append(dict(id=f['id'], t0=r3(tf0), t1=r3(end), g=gl(f, ('nut', 'part', 'screw')), cues=ids))
    allg = [n['g'] for n in ctx['nodes'] if n['kind'] != 'profil']
    cues.append(dict(id='cokoli', t0=r3(T['cokoli']), t1=r3(D), anchor=None, side='top', g=allg, step='cokoli'))
    steps.append(dict(id='cokoli', t0=r3(T['cokoli']), t1=r3(T['reset']), g=[], cues=['cokoli']))
    steps.append(dict(id='konec', t0=r3(T['reset']), t1=r3(D), g=[], cues=['cokoli']))

    def orbit(target, az, el, fit, aspect=4.0 / 3.0, fov=45.0, pad=1.12):
        """pozice kamery pro cil, azimut (0 = zepredu z +Z, kladny smerem k -X), elevaci a polomer `fit` (mm), ktery se musi vejit (pomer 4:3)"""
        th = math.tan(math.radians(fov) / 2); d = pad * fit / min(th, th * aspect)
        a, e = math.radians(az), math.radians(el)
        return [target[0] - d * math.sin(a) * math.cos(e), target[1] + d * math.sin(e), target[2] + d * math.cos(a) * math.cos(e)]

    def cam(tt, target, az, el, fit, ease='inout'):
        pos = orbit(target, az, el, fit)
        return dict(t=round(tt, 3), pos=[round(v, 1) for v in pos], target=[round(v, 1) for v in target], ease=ease, fit=fit)
    wide = lambda tt, ease='inout': cam(tt, (0, 22, 0), 40, 28, 140, ease)
    camera = [wide(0.0, 'linear'), cam(INTRO_S - 0.5, (-20, 24, 0), 42, 27, 130), cam(INTRO_S + 1.0, (-150, 32, 0), 60, 15, 42)]
    for f in FS:
        for k in f['camera']:
            tt = f['t0'] if k['at'] == 'start' else f['T'][k['at']]
            tt += A(k['dA'])
            camera.append(cam(tt, ((0.0 if k['absx'] else f['x']) + k['tx'], k['ty'], 0.0), k['az'], k['el'], k['fit'], k['ease']))
    # zaver: plynuly odjezd od posledniho upevneni na celek (mezikrok, aby se smer pohledu netocil prilis rychle), pak pauza na celku
    xl = FS[-1]['x']
    camera += [cam(T['cokoli'] + 0.8, (xl - 25, 33, 0), -40, 18, 60), cam(T['cokoli'] + 1.5, (xl / 2, 34, 0), 0, 22, 100),
               cam(T['reset'] - 0.1, (35, 32, 0), 38, 26, 140), cam(T['reset'], (35, 32, 0), 38, 26, 140), wide(D, 'linear')]
    for a, b in zip(camera, camera[1:]):
        if not b['t'] > a['t'] + 1e-6: raise ValueError('klice kamery musi mit rostouci cas: %r -> %r' % (a, b))
    nodes = {n['name']: dict(g=n['g'], kind=n['kind'], fastening=n['fastening']) for n in ctx['nodes']}
    fast = [dict(id=f['id'], x=f['x'], nut=f['nut']['node'], part=f['part']['node'], screw=f['screw']['node'], nut_kind=f['nut']['kind']) for f in FS]
    demo = dict(v=1, duration=r3(D), fps=FPS, loop=True, clip='demo', poster=r3(T['reset'] - 0.1), time_scale=round(1.0 / TIME_SCALE, 3),
                g=ctx['gmap'], nodes=nodes, fastenings=fast, cues=cues, steps=steps, camera=camera, fade=None, note=CUES_TEXT_NOTE)
    v3d = dict(v=1, u='mm', up=[0, 1, 0], front=[0, 0, 1],
               box=dict(min=[-150, 0, -22], max=[150, 72, 28]), look='nat', dims=[], motions=[])
    return v3d, demo


def anchors(ctx):
    sl = ctx['slot']
    out = {'a_slot': ('profil', (ctx['xrange'][0], round(ctx['Y0'] + sl['strop_komory_y'] + sl['krcek_hloubka'] / 2, 3), 0.0))}
    for n in ctx['nodes']:
        if n['anchor'] is not None: out['a_' + n['name']] = (n['name'], tuple(n['anchor']))
    return out


def export_glb(ctx, out_path, extras_path=None):
    W = GLBWriter()
    nl = ctx['nodes']
    mat_index, materials = {}, []
    for n in nl:
        mn = n['mesh'].material
        if mn not in mat_index:
            col, me, ro = MATERIALS[mn]
            mat_index[mn] = len(materials)
            materials.append({'name': mn, 'pbrMetallicRoughness': {'baseColorFactor': col, 'metallicFactor': me, 'roughnessFactor': ro},
                              'extras': {'smooth': True}})
    meshes = []
    for n in nl:
        m = n['mesh']
        idx_dt = np.uint16 if len(m.V) < 65535 else np.uint32
        pa = W.accessor(m.V.astype(np.float32), 5126, 'VEC3', 34962, minmax=True)
        na = W.accessor(m.N.astype(np.float32), 5126, 'VEC3', 34962)
        ia = W.accessor(m.F.astype(idx_dt).reshape(-1), 5123 if idx_dt == np.uint16 else 5125, 'SCALAR', 34963)
        meshes.append({'name': 'm_' + n['name'], 'primitives': [{'attributes': {'POSITION': pa, 'NORMAL': na}, 'indices': ia,
                                                                'material': mat_index[m.material], 'mode': 4}]})
    anc = anchors(ctx)
    node_ids = {n['name']: i for i, n in enumerate(nl)}
    anchor_ids = {an: len(nl) + i for i, an in enumerate(anc)}
    traj = ctx['traj']
    nodes_json = []
    for i, n in enumerate(nl):
        nj = {'name': n['name'], 'mesh': i, 'extras': {'g': n['g']},
              'children': [anchor_ids[a] for a, (p, _) in anc.items() if p == n['name']]}
        if n['name'] in traj:
            tr = traj[n['name']]
            nj['translation'] = [float(v) for v in tr['pos'][0]]
            nj['rotation'] = [float(v) for v in quat_y(tr['ang'][0])]
            s = float(tr['scale'][0]); nj['scale'] = [s, s, s]
        nodes_json.append(nj)
    for an, (p, pos) in anc.items():
        nodes_json.append({'name': an, 'translation': [float(v) for v in pos]})
    ts = ctx['ts'].astype(np.float32)
    ti = W.accessor(ts, 5126, 'SCALAR', None, minmax=True)
    samplers, channels = [], []
    for n in nl:
        if n['name'] not in traj: continue
        tr = traj[n['name']]
        pa = W.accessor(tr['pos'].astype(np.float32), 5126, 'VEC3')
        qa = W.accessor(quat_y(tr['ang']).astype(np.float32), 5126, 'VEC4')
        sa = W.accessor(np.repeat(tr['scale'][:, None], 3, 1).astype(np.float32), 5126, 'VEC3')
        for path, acc in (('translation', pa), ('rotation', qa), ('scale', sa)):
            samplers.append({'input': ti, 'output': acc, 'interpolation': 'LINEAR'})
            channels.append({'sampler': len(samplers) - 1, 'target': {'node': node_ids[n['name']], 'path': path}})
    v3d, demo = make_extras(ctx)
    gltf = {'asset': {'version': '2.0', 'generator': 'build_demo_glb.py (Pripni cokoli)'},
            'scene': 0,
            'scenes': [{'name': 'stavebnice', 'nodes': [node_ids[n['name']] for n in nl], 'extras': {'v3d': v3d, 'demo': demo}}],
            'nodes': nodes_json, 'meshes': meshes, 'materials': materials,
            'animations': [{'name': 'demo', 'samplers': samplers, 'channels': channels}]}
    data = W.finish(gltf)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + '.tmp'
    with open(tmp, 'wb') as f: f.write(data)
    os.replace(tmp, out_path)
    if extras_path:
        with open(extras_path, 'w', encoding='utf-8') as f:
            json.dump({'v3d': v3d, 'demo': demo}, f, ensure_ascii=False, indent=1)
    return data, gltf


def _r3(x):
    if isinstance(x, (float, np.floating)): return round(float(x), 3)
    if isinstance(x, dict): return {k: _r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [_r3(v) for v in x]
    return x


def drazka_report(ctx, profile_name):
    """drazka.json: namerene rozmery T-drazky (z rezu GLB profilu) + rozmery, vule a polohy matic, dilu a sroubu (z meshi)"""
    sl_c = ctx['slot']
    out = {
        'jednotky': 'mm',
        'profil': profile_name,
        'soustava_prurezu': 'x = napric drazkou (osa drazky x = 0), y = nahoru (povrch profilu u horni drazky y = +20, stred profilu y = 0); '
                            've scene GLB je Y = y + 20 (spodek profilu Y = 0, horni plocha Y = 40), X = podel profilu, Z = -x',
        'odvozeni': [
            'Rez: GLB profilu (z Dogus STEP) se protne rovinou kolmou k ose delky v polovine delky; segmenty rezu se spoji do 6 uzavrenych smycek '
            '(vnejsi obrys, stredovy otvor, 4 rohove dutiny), kolinearni body se vyhodi.',
            'Vnejsi obrys obsahuje na kazde strane T-drazku jako vybeh; horni drazka = usek obrysu od horniho povrchu (y = 20, leva zem) pres '
            'zapusteni, krcek, strop komory, komoru a dno az zpet k hornimu povrchu (prava zem). Vsechny rozmery jsou presne souradnice vrcholu '
            'tohoto useku (zadne rastrovani); GLB je float32, hodnoty zaokrouhleny na 0,001 mm.',
            'Struktura useku: (-a,20) (-a,18,5) (-b,18,5) (-b,14,0) (-C,14,0) (-C,10,969) (-fx,fy) dno ... : zapusteni 2 x a (hloubka 1,5), '
            'okraj nahore y = 18,5, krcek 2 x b, strop komory (spodek okraju) y = 14,0, komora 2 x C, svisla stena do y = 10,969, pote sikmina 45 st. '
            'k okraji dna (+-6,275; 7,195), dno je mirne zvlnene (7,188 u osy, 6,322 pri +-4,3, strednim zlabkem 6,764).',
            'Vule matic: rozdily polosirek proti drazce; matice se z katalogu berou beze zmeny tvaru (kamen jen quadric decimaci na 3000 trojuhelniku, '
            'vrcholy zustavaji na puvodnich souradnicich).',
        ],
        'drazka': _r3(dict({k: v for k, v in sl_c.items() if k not in ('polyline',)}, dno_nejvyssi_bod_pod_matici_y=ctx['floor_peak'],
                           poznamka_dno='dno_y_max je okraj sikminy (+-6,275); plocha spodek matice (+-5,4) lezi na hrebenech dna 7,188 u osy')),
        'drazka_polyline_levy_k_pravemu': _r3(sl_c['polyline']),
        'upevneni': [],
    }
    for f in ctx['fastenings']:
        nu, pa, sc = f['nut'], f['part'], f['screw']
        v = nu['mesh'].V; fe = {'id': f['id'], 'x': f['x']}
        base = {'trojuhelniku': nu['mesh'].tris, 'trojuhelniku_original': nu['info']['tris_orig'], 'otvor_polomer_stredni': nu['info']['hole_r'],
                'vyska_celkem': float(v[:, 1].max()), 'delka_x': float(v[:, 0].max() - v[:, 0].min()), 'sirka_z': float(v[:, 2].max() - v[:, 2].min()),
                'druh': nu['kind'], 'zdroj': os.path.basename(nu['file'])}
        if nu['kind'] == 'slide':
            ht = nu['head_top']; hs = float(np.abs(v[v[:, 1] <= ht - 0.5][:, 2]).max()); bs = float(np.abs(v[v[:, 1] > ht + 0.05][:, 2]).max())
            base.update(hlava_vyska=ht, hlava_sirka=2 * hs, nabeh_sirka_pricne=2 * bs, vule_hlava_na_stranu=sl_c['komora_pul_sirka'] - hs,
                        vule_nabeh_na_stranu=sl_c['krcek_pul_sirka'] - bs, poloha_y_posun_pod_dilem=nu['y_start'], poloha_y_dotazeny_hlava_na_stropu=nu['y_tight'])
        else:
            vy = v[v[:, 1] > 6.2]
            base.update(vyska_zuby_horni=nu['plate_top'], vystupek_v_krcku_pricne_po_otoceni=float(2 * np.abs(vy[:, 0]).max()),
                        vystupek_v_krcku_podel_po_otoceni=float(2 * np.abs(vy[:, 2]).max()),
                        vule_delka_do_komory_na_stranu=sl_c['komora_pul_sirka'] - float(v[:, 0].max()),
                        vule_sirka_do_krcku_na_stranu=sl_c['krcek_pul_sirka'] - float(v[:, 2].max()),
                        poloha_y_na_dne_komory=nu['y_start'], poloha_y_zaklesnuta_zuby_na_stropu=nu['y_tight'],
                        stoupani_pri_dotahovani=nu['y_tight'] - nu['y_start'],
                        smysl_otaceni='po smeru hodin pri pohledu shora (zaoblene rohy napred)' if nu['sense'] < 0 else 'proti smeru hodin pri pohledu shora')
        fe['matice'] = _r3(base)
        pv = pa['mesh'].V
        fe['dil'] = _r3({'zdroj': os.path.basename(pa['file']), 'trojuhelniku': pa['mesh'].tris, 'trojuhelniku_original': pa['info']['tris_orig'],
                         'otvor_polomer': pa['info']['hole_r'], 'dosedaci_vyska_sroubu_nad_dilem': f['seat'],
                         'rozmer_obalu': [float(pv[:, i].max() - pv[:, i].min()) for i in range(3)]})
        fe['sroub'] = _r3({'typ': 'M6 imbus, hlava ' + ('zapustna (ISO 10642, 90 st.)' if ctx['head'] == 'csk' else 'valcova 10 x 6'), 'delka': sc['L'],
                           'stoupani_zavitu_vizualni': sc['pitch'], 'otacek': sc['turns'], 'posuv_po_dotyku': sc['travel'],
                           'trojuhelniku': sc['mesh'].tris})
        out['upevneni'].append(fe)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--profile', required=True, help='GLB profilu 40x40 S10 (z Dogus STEP, delka v ose Z, rozsah z in [-1000,0])')
    ap.add_argument('--katalog', default='/opt/konfigurator/webapp/katalog', help='adresar s product_<id>.glb')
    ap.add_argument('--zdroje', default=None, help='adresar se zdroji "zdroje/..." (vychozi: zdroje/ vedle skriptu)')
    ap.add_argument('--uhelnik-glb', default=None, help='GLB uhelniku (dil1); vychozi zdroje/uhelnik_3045_vysoka_kvalita.glb (novy prevod STEP, viz priprava_uhelnik_3045.py)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--drazka-json', default=None)
    ap.add_argument('--extras-json', default=None)
    ap.add_argument('--kamen', type=int, default=3592, choices=(3592, 3066), help='katalogovy produkt kamene (T matice 3592 / ctvercova 3066)')
    ap.add_argument('--head', default='csk', choices=('cap', 'csk'), help='hlava sroubu: zapustna ISO 10642 (csk, vychozi: dily maji 90 st. zahloubeni) / valcova O10x6 (cap)')
    args = ap.parse_args(argv)
    ctx = build(args)
    data, gltf = export_glb(ctx, args.out, args.extras_json)
    if args.drazka_json:
        with open(args.drazka_json, 'w', encoding='utf-8') as f:
            json.dump(drazka_report(ctx, 'Hlinikovy stavebnicovy profil 40x40 mm SuperLight S10 (Dogus STEP 1.1.10.040040.03)'), f, ensure_ascii=False, indent=1)
    tri = {n['name']: n['mesh'].tris for n in ctx['nodes']}
    print('GLB %s: %d B, D=%.3f s, N=%d vzorku, trojuhelniky: %s' % (args.out, len(data), ctx['D'], ctx['N'], tri))
    return ctx


if __name__ == '__main__':
    main()
