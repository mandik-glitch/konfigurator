#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nezavisla referencni kontrola kolizi pohybu nad <karta>.offer.glb (pro
tests/harness_viewer.js, scenar H).

Nepouziva prohlizec ani v3d_glb: vlastni parser GLB, vlastni matice (numpy),
skutecne trojuhelniky, prunik trojuhelnik x kvadr (SAT). Parser, matice a SAT
jsou prevzate z nezavisle kontroly tmp/kontrola/motion_check.py (kontrolor
2026-10-01), metoda z tmp/kontrola/pairs.py a box_sets.py:
  - AABB meshe pohybliveho podstromu (zmensena o TOL mm) proti trojuhelnikum
    ostatnich meshi; kolize = NOVE trojuhelniky proti stavu "vse zavreno"
    (dotyk a presahy, ktere jsou v modelu uz v klidu, se nepocitaji).

Pouziti:  python3 v3d_collide_ref.py <glb>  < vstup.json  > vystup.json
  vstup:  {"pairs": true,
           "states": {"<jmeno>": {"t": {"m4": 1, ...}, "focus": "m20" | null}}}
  vystup: {"pairs": [[a, b, n], ...],          # dvojice, ktere otevrene (s rodici) narazi
           "side": {"m1": 1, ...},              # strana podle posunu teziste podel front
           "states": {"<jmeno>": {"pair": [[a, b, n]], "static": [[a, n]]}}}
  - pair: otevreny pohyb a narazi do podstromu pohybu b (otevreneho i zavreneho)
  - static: otevreny pohyb a narazi do statickeho ramu
  - focus: jen zaznamy, kde je focus jednou ze stran
"""
import json, math, re, struct, sys
import numpy as np

TOL = 1.0          # mm (stejne jako pairs.py / box_sets.py)
SIDE_MIN = 20.0    # mm


def rd(p):
    d = open(p, "rb").read()
    mg, ver, ln = struct.unpack_from("<4sII", d, 0)
    assert mg == b"glTF" and ln == len(d), "neni GLB"
    off = 12; js = None; bn = None; k = 0
    while off < ln:
        cl, ct = struct.unpack_from("<II", d, off); c = d[off + 8:off + 8 + cl]
        if k == 0: js = json.loads(c.decode("utf-8"))
        elif ct == 0x004E4942: bn = c
        off += 8 + cl; k += 1
    return js, bn


def quat_to_m3(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def local_m(n):
    if "matrix" in n:
        return np.array(n["matrix"], dtype=float).reshape(4, 4).T
    M = np.eye(4)
    M[:3, :3] = quat_to_m3(n.get("rotation", [0, 0, 0, 1])) @ np.diag(n.get("scale", [1, 1, 1]))
    M[:3, 3] = n.get("translation", [0, 0, 0])
    return M


def axis_angle(ax, deg):
    ax = np.array(ax, float); ax /= np.linalg.norm(ax)
    a = math.radians(deg); c, s = math.cos(a), math.sin(a); x, y, z = ax; C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def step_prog(m, t):
    tot = sum(max(1, s.get("ms", 300)) for s in m["steps"]); acc = 0; out = []
    for s in m["steps"]:
        d = max(1, s.get("ms", 300)); out.append(ease((t * tot - acc) / d)); acc += d
    return out


def tri_box_overlap(tris, bmin, bmax):
    """Vektorovy SAT test trojuhelniku (N,3,3) s AABB. Vraci bool pole."""
    out = np.zeros(len(tris), bool)
    if not len(tris) or np.any(bmin > bmax): return out
    c = (bmin + bmax) / 2; h = (bmax - bmin) / 2
    v = tris - c
    ok = np.all((v.min(axis=1) <= h) & (v.max(axis=1) >= -h), axis=1)
    if not ok.any(): return out
    idx = np.where(ok)[0]; vv = v[idx]
    e = [vv[:, 1] - vv[:, 0], vv[:, 2] - vv[:, 1], vv[:, 0] - vv[:, 2]]
    res = np.ones(len(idx), bool)
    n = np.cross(e[0], e[1])
    res &= np.abs(np.einsum("ij,ij->i", n, vv[:, 0])) <= np.abs(n) @ h + 1e-9
    for ei in e:
        for a in np.eye(3):
            ax = np.cross(np.broadcast_to(a, ei.shape), ei)
            p = np.einsum("nkj,nj->nk", vv, ax)
            rr = np.abs(ax) @ h
            res &= ~((p.min(axis=1) > rr + 1e-9) | (p.max(axis=1) < -rr - 1e-9))
    out[idx] = res
    return out


class Model:
    def __init__(self, path):
        self.j, self.b = rd(path)
        j = self.j
        self.nodes = j["nodes"]
        self.parent = {}
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []): self.parent[c] = i
        self.roots = j["scenes"][j.get("scene", 0)]["nodes"]
        self.spec = j["scenes"][0]["extras"]["v3d"]
        self.front = np.array(self.spec.get("front", [0, 0, 1]), float)
        self.base = [local_m(n) for n in self.nodes]
        self.pidx = {n["name"]: i for i, n in enumerate(self.nodes) if re.fullmatch(r"p\d+", n.get("name", ""))}
        self.mesh_v = {}; self.mesh_tri = {}
        for mi, me in enumerate(j["meshes"]):
            vs = []; ts = []; off = 0
            for p in me["primitives"]:
                v = self.acc(p["attributes"]["POSITION"]).astype(float)
                idx = self.acc(p["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in p else np.arange(len(v)).reshape(-1, 3)
                vs.append(v); ts.append(idx + off); off += len(v)
            self.mesh_v[mi] = np.vstack(vs); self.mesh_tri[mi] = np.vstack(ts)
        self.motions = {m["id"]: m for m in self.spec["motions"]}
        self.order = [m["id"] for m in self.spec["motions"]]
        self.driver = {}
        for m in self.spec["motions"]:
            for s in m["steps"]: self.driver.setdefault(s["p"], set()).add(m["id"])
        # hlavni pivot (posledni krok), podstrom, rodice (pohyby pivotu-predku)
        self.root = {mid: self.pidx[m["steps"][-1]["p"]] for mid, m in self.motions.items()}
        self.sub = {mid: set(self.subtree(r)) for mid, r in self.root.items()}
        self.deps = {}
        for mid in self.order:
            d = []
            for a in self.ancestors(self.root[mid]):
                d += [x for x in self.driver.get(self.nodes[a].get("name", ""), ()) if x != mid and x not in d]
            self.deps[mid] = d
        # vlastnik uzlu = nejvnitrnejsi pohyb, jehoz hlavni pivot je predek (nebo uzel sam)
        root_of = {r: mid for mid, r in self.root.items()}
        self.owner = {}
        for i in range(len(self.nodes)):
            k = i; own = None
            while k is not None:
                if k in root_of: own = root_of[k]; break
                k = self.parent.get(k)
            self.owner[i] = own
        self.mesh_nodes_all = [i for i in range(len(self.nodes)) if "mesh" in self.nodes[i]]

    def acc(self, ai):
        a = self.j["accessors"][ai]; bv = self.j["bufferViews"][a["bufferView"]]
        ct = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a["componentType"]]
        nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        es = np.dtype(ct).itemsize * nc
        st = bv.get("byteStride", es)
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        if st == es:
            arr = np.frombuffer(self.b, dtype=ct, count=a["count"] * nc, offset=off)
        else:
            raw = np.frombuffer(self.b, dtype=np.uint8, count=st * (a["count"] - 1) + es, offset=off)
            arr = np.lib.stride_tricks.as_strided(raw, shape=(a["count"], es), strides=(st, 1)).copy().view(ct)
        return arr.reshape(-1, nc) if nc > 1 else arr

    def ancestors(self, i):
        out = []
        while i in self.parent:
            i = self.parent[i]; out.append(i)
        return out

    def subtree(self, i):
        out = [i]; st = [i]
        while st:
            k = st.pop()
            for c in self.nodes[k].get("children", []): out.append(c); st.append(c)
        return out

    def world(self, state):
        L = [m.copy() for m in self.base]
        for mid, t in state.items():
            if t <= 0: continue
            m = self.motions[mid]
            for s, e in zip(m["steps"], step_prog(m, t)):
                if e <= 0: continue
                i = self.pidx[s["p"]]
                if s["op"] == "T":
                    L[i][:3, 3] += np.array(s["ax"], float) * s["v"] * e
                else:
                    L[i][:3, :3] = axis_angle(s["ax"], s["v"] * e) @ L[i][:3, :3]
        W = [None] * len(self.nodes)
        def walk(i, P):
            W[i] = P @ L[i]
            for c in self.nodes[i].get("children", []): walk(c, W[i])
        for r in self.roots: walk(r, np.eye(4))
        return W

    def verts_of(self, W, i):
        v = self.mesh_v[self.nodes[i]["mesh"]]
        return v @ W[i][:3, :3].T + W[i][:3, 3]

    def tris_all(self, W):
        """Vsechny trojuhelniky ve svete + uzel, kteremu patri."""
        T = []; own = []
        for i in self.mesh_nodes_all:
            v = self.verts_of(W, i); t = v[self.mesh_tri[self.nodes[i]["mesh"]]]
            T.append(t); own.append(np.full(len(t), i))
        return np.vstack(T), np.concatenate(own)


def new_hits(M, W, W0, TA, OA, T0, O0, A_nodes, cache0, only_nodes=None):
    """Nove trojuhelniky mimo podstrom A_nodes, ktere zasahnou do AABB meshi A.
    only_nodes: kandidatni trojuhelniky jen z techto uzlu (focus)."""
    inA = np.zeros(len(M.nodes), bool); inA[list(A_nodes)] = True
    maskS = ~inA[OA]
    if only_nodes is not None:
        inO = np.zeros(len(M.nodes), bool); inO[list(only_nodes)] = True
        maskS &= inO[OA]
    idxS = np.where(maskS)[0]
    hits = set()
    if not len(idxS): return hits
    for i in A_nodes:
        if "mesh" not in M.nodes[i]: continue
        v1 = M.verts_of(W, i)
        s1 = set(idxS[tri_box_overlap(TA[idxS], v1.min(0) + TOL, v1.max(0) - TOL)].tolist())
        if not s1: continue
        key = (i, id(A_nodes))
        if key not in cache0:
            idx0 = np.where(~inA[O0])[0]
            v0 = M.verts_of(W0, i)
            cache0[key] = set(idx0[tri_box_overlap(T0[idx0], v0.min(0) + TOL, v0.max(0) - TOL)].tolist())
        hits |= (s1 - cache0[key])
    return hits


def main():
    M = Model(sys.argv[1])
    inp = json.load(sys.stdin)
    W0 = M.world({})
    T0, O0 = M.tris_all(W0)
    cache0 = {}
    out = {"pairs": [], "side": {}, "states": {}}

    # strana: posun teziste podstromu podel front (otevreno s rodici vs zavreno)
    for mid in M.order:
        st = {d: 1.0 for d in M.deps[mid]}; st[mid] = 1.0
        W1 = M.world(st)
        nodes = [i for i in M.sub[mid] if "mesh" in M.nodes[i]]
        if not nodes: out["side"][mid] = 0; continue
        c0 = np.vstack([M.verts_of(W0, i) for i in nodes]); c1 = np.vstack([M.verts_of(W1, i) for i in nodes])
        d = float(((c1.min(0) + c1.max(0)) / 2 - (c0.min(0) + c0.max(0)) / 2) @ M.front)
        out["side"][mid] = (1 if d > 0 else -1) if abs(d) >= SIDE_MIN else 0

    if inp.get("pairs"):
        ids = M.order
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                if M.sub[a] & M.sub[b]: continue          # predek/potomek
                st = {a: 1.0, b: 1.0}
                for d in M.deps[a] + M.deps[b]: st[d] = 1.0
                W1 = M.world(st)
                va = np.vstack([M.verts_of(W1, i) for i in M.sub[a] if "mesh" in M.nodes[i]] or [np.zeros((0, 3))])
                vb = np.vstack([M.verts_of(W1, i) for i in M.sub[b] if "mesh" in M.nodes[i]] or [np.zeros((0, 3))])
                if not len(va) or not len(vb): continue
                if np.any(va.min(0) > vb.max(0)) or np.any(vb.min(0) > va.max(0)): continue
                TA, OA = M.tris_all(W1)
                n = 0
                for P, Q in ((a, b), (b, a)):
                    h = new_hits(M, W1, W0, TA, OA, T0, O0, M.sub[P], cache0)
                    n += sum(1 for k in h if OA[k] in M.sub[Q])
                if n: out["pairs"].append([a, b, n])

    for name, sdef in (inp.get("states") or {}).items():
        t = {k: float(v) for k, v in sdef.get("t", {}).items() if float(v) > 0}
        focus = sdef.get("focus")
        W = M.world(t)
        TA, OA = M.tris_all(W)
        pair = {}; stat = {}
        for a in M.order:
            if t.get(a, 0) <= 0: continue
            # focus: u ostatnich pohybu staci trojuhelniky podstromu focus
            only = M.sub[focus] if (focus and a != focus) else None
            h = new_hits(M, W, W0, TA, OA, T0, O0, M.sub[a], cache0, only)
            for k in h:
                b = M.owner[int(OA[k])]
                if b is None:
                    if focus and a != focus: continue
                    stat[a] = stat.get(a, 0) + 1
                else:
                    if focus and focus not in (a, b): continue
                    key = (a, b); pair[key] = pair.get(key, 0) + 1
        out["states"][name] = {"pair": [[a, b, n] for (a, b), n in sorted(pair.items())],
                               "static": [[a, n] for a, n in sorted(stat.items())]}
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
