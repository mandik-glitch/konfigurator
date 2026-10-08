# -*- coding: utf-8 -*-
"""Utoky na GLB pro tests/test_mark.py (jen cteni vstupu, vsechno v pameti).

Funkce berou a vraci GLB bajty. Utoky na POSITION pracuji nad LOKALNIMI
souradnicemi meshe (tak je zapisuje export) a pocitaji se ve svetove
soustave uzlu; transformace celeho modelu jsou ve dvou variantach:
  wrap_root  - nad scenu se pridat uzel s matici (vrcholy se nemeni),
  bake       - transformace se "upece" do vrcholu (OBJ, Apply transforms).
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "api"))
import v3d_glb  # noqa: E402
import v3d_mark as M  # noqa: E402


def _segments(g):
    segs, _ = M._position_segments(g)
    return segs


def map_positions(glb, fn, seed=0):
    """fn(Pw[N,3] svetove, rng) -> Pw2; zapise zpet do lokalnich souradnic (float32)."""
    g, b = v3d_glb.read_glb(glb)
    rng = np.random.RandomState(seed)
    buf = bytearray(b)
    for s in _segments(g):
        v = M._acc_view(g, buf, s.acc, True)
        Pl = np.array(v, dtype=np.float64)
        Pw = Pl @ s.R.T + s.t
        Pw2 = fn(Pw, rng)
        P32 = ((Pw2 - s.t) @ s.Rinv.T).astype(np.float32)
        v[:] = P32
        a = g["accessors"][s.acc]
        a["min"] = [float(x) for x in P32.min(0)]
        a["max"] = [float(x) for x in P32.max(0)]
    return v3d_glb.write_glb(g, bytes(buf))


def round_to(glb, step):
    return map_positions(glb, lambda P, r: np.round(P / step) * step)


def round_local(glb, step):
    """Zaokrouhli LOKALNI souradnice (jak by to udelal exporter s omezenou presnosti)."""
    g, b = v3d_glb.read_glb(glb)
    buf = bytearray(b)
    for s in _segments(g):
        v = M._acc_view(g, buf, s.acc, True)
        P = np.round(np.array(v, dtype=np.float64) / step) * step
        v[:] = P.astype(np.float32)
        a = g["accessors"][s.acc]
        a["min"] = [float(x) for x in v.min(0)]
        a["max"] = [float(x) for x in v.max(0)]
    return v3d_glb.write_glb(g, bytes(buf))


def add_noise(glb, sigma, kind="gauss", seed=1):
    if kind == "gauss":
        return map_positions(glb, lambda P, r: P + r.normal(0, sigma, P.shape), seed)
    return map_positions(glb, lambda P, r: P + r.uniform(-sigma, sigma, P.shape), seed)


def float32_roundtrip(glb):
    return map_positions(glb, lambda P, r: P)


def keep_meshes(glb, frac, seed=3, contiguous=False):
    """Necha jen cast uzlu s meshem (frac 0..1); ostatnim se mesh odebere."""
    g, b = v3d_glb.read_glb(glb)
    ids = [i for i, n in enumerate(g["nodes"]) if "mesh" in n]
    rng = np.random.RandomState(seed)
    k = max(1, int(round(frac * len(ids))))
    keep = set(ids[:k]) if contiguous else set(rng.choice(ids, k, replace=False).tolist())
    for i in ids:
        if i not in keep:
            del g["nodes"][i]["mesh"]
    return v3d_glb.write_glb(g, b), len(keep), len(ids)


def rot_axis(ax, deg):
    ax = np.asarray(ax, float)
    ax = ax / np.linalg.norm(ax)
    a = np.radians(deg)
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def similarity(scale=1.0, R=None, t=(0, 0, 0)):
    R = np.eye(3) if R is None else R
    return scale, R, np.asarray(t, float)


def bake(glb, tf):
    s, R, t = tf
    return map_positions(glb, lambda P, r: s * (P @ R.T) + t)


def wrap_root(glb, tf):
    """Nad scenu prida uzel s matici (vrcholy zustavaji)."""
    s, R, t = tf
    g, b = v3d_glb.read_glb(glb)
    Mx = np.eye(4)
    Mx[:3, :3] = s * R
    Mx[:3, 3] = t
    g["nodes"].append({"name": "n%d" % len(g["nodes"]), "children": list(g["scenes"][0]["nodes"]),
                       "matrix": [float(x) for x in Mx.T.reshape(-1)]})
    g["scenes"][0]["nodes"] = [len(g["nodes"]) - 1]
    # final_check by to odmitl (jmeno ok, matrix ok) - tady jen zapisujeme
    return v3d_glb.write_glb(g, b)


def points_to_glb_points(glb):
    return M.world_points(glb)


def synth_glb(npts=6000, seed=0, nodes=None):
    """Maly syntetický GLB: jeden mesh = nahodne trojuhelniky v krychli 100 mm (+ NORMAL, indices),
    jeden uzel na kazdy prvek `nodes` (dict s TRS) - vice uzlu = vice instanci TOHOTO meshe
    (sdileny accessor). Jmena n<i> (projde final_check)."""
    rng = np.random.RandomState(seed)
    P = (rng.uniform(0, 100, (npts, 3))).astype(np.float32)
    N = np.tile(np.array([[0, 1, 0]], np.float32), (npts, 1))
    idx = np.arange(npts - npts % 3, dtype=np.uint32)
    pb, nb, ib = P.tobytes(), N.tobytes(), idx.tobytes()
    b = pb + nb + ib
    g = {
        "asset": {"version": "2.0"}, "scene": 0,
        "scenes": [{"nodes": []}],
        "nodes": [], "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": 2}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": npts, "type": "VEC3",
             "min": [float(x) for x in P.min(0)], "max": [float(x) for x in P.max(0)]},
            {"bufferView": 1, "componentType": 5126, "count": npts, "type": "VEC3"},
            {"bufferView": 2, "componentType": 5125, "count": len(idx), "type": "SCALAR"}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(pb), "target": 34962},
                        {"buffer": 0, "byteOffset": len(pb), "byteLength": len(nb), "target": 34962},
                        {"buffer": 0, "byteOffset": len(pb) + len(nb), "byteLength": len(ib), "target": 34963}],
        "buffers": [{"byteLength": len(b)}],
    }
    for k, n in enumerate(nodes or [{}]):
        d = {"name": "n%d" % k, "mesh": 0}
        d.update(n)
        g["nodes"].append(d)
        g["scenes"][0]["nodes"].append(k)
    return v3d_glb.write_glb(g, b)
