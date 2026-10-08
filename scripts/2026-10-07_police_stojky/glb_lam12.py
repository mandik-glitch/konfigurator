#!/usr/bin/env python3
"""GLB laminovane dreviny 12 mm (bot8, 2026-10-07; Robert: "u 30/35 krome laminodesky 18mm i 12mm"): deska 1000 x 1000 x 12 mm, STEJNA souradnicova soustava jako ostatni desky
(MDF 8 mm `deska_mdf_seda_8.glb`, PR10 `pr10.glb`): X, Y = rozmer (1000), Z = tloustka, vycentrovana v pocatku (generator desku otaci kvaternionem Q_RX_M90, tloustka nahoru).
Jednoduchy kvadr (24 vrcholu, 12 trojuhelniku, normaly po plochach); soubor pouziva zaloz_kartu_lam12.py (karta) i testy (kandidatni katalog).

  api/venv/bin/python3 scripts/2026-10-07_police_stojky/glb_lam12.py <vystupni.glb>"""
import json
import struct
import sys

import numpy as np

SIRKA, TLOUSTKA = 1000.0, 12.0


def kvadr(sx=SIRKA, sy=SIRKA, sz=TLOUSTKA):
    hx, hy, hz = sx / 2.0, sy / 2.0, sz / 2.0
    P, N, T = [], [], []
    plochy = [((1, 0, 0), [(hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz)]),
              ((-1, 0, 0), [(-hx, -hy, -hz), (-hx, -hy, hz), (-hx, hy, hz), (-hx, hy, -hz)]),
              ((0, 1, 0), [(-hx, hy, -hz), (-hx, hy, hz), (hx, hy, hz), (hx, hy, -hz)]),
              ((0, -1, 0), [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, -hy, hz), (-hx, -hy, hz)]),
              ((0, 0, 1), [(-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]),
              ((0, 0, -1), [(-hx, -hy, -hz), (-hx, hy, -hz), (hx, hy, -hz), (hx, -hy, -hz)])]
    for n, rohy in plochy:
        b = len(P)
        for r in rohy:
            P.append(r)
            N.append(n)
        # orientace trojuhelniku podle normaly (proti smeru hodin pri pohledu zvenku)
        a, c = np.array(rohy[1]) - np.array(rohy[0]), np.array(rohy[2]) - np.array(rohy[0])
        if float(np.dot(np.cross(a, c), n)) > 0:
            T += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
        else:
            T += [(b, b + 2, b + 1), (b, b + 3, b + 2)]
    return np.array(P, dtype="<f4"), np.array(N, dtype="<f4"), np.array(T, dtype="<u4")


def zapis(cesta, P, N, T):
    idx = T.astype("<u4").ravel()
    b_idx, b_pos, b_nor = idx.tobytes(), P.astype("<f4").tobytes(), N.astype("<f4").tobytes()
    binary = b_idx + b_pos + b_nor
    while len(binary) % 4:
        binary += b"\0"
    j = {"asset": {"version": "2.0", "generator": "bot8 glb_lam12.py"}, "scene": 0, "scenes": [{"nodes": [0]}],
         "nodes": [{"name": "world", "children": [1]}, {"name": "geometry_0", "mesh": 0}],
         "meshes": [{"name": "geometry_0", "extras": {}, "primitives": [{"attributes": {"POSITION": 1, "NORMAL": 2}, "indices": 0, "mode": 4}]}],
         "accessors": [{"componentType": 5125, "type": "SCALAR", "bufferView": 0, "count": int(idx.size), "max": [int(idx.max())], "min": [int(idx.min())]},
                       {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 1, "count": int(len(P)), "max": [float(v) for v in P.max(axis=0)], "min": [float(v) for v in P.min(axis=0)]},
                       {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 2, "count": int(len(N)), "max": [1.0, 1.0, 1.0], "min": [-1.0, -1.0, -1.0]}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(b_idx)}, {"buffer": 0, "byteOffset": len(b_idx), "byteLength": len(b_pos)},
                         {"buffer": 0, "byteOffset": len(b_idx) + len(b_pos), "byteLength": len(b_nor)}],
         "buffers": [{"byteLength": len(binary)}]}
    jb = json.dumps(j, separators=(",", ":")).encode()
    while len(jb) % 4:
        jb += b" "
    with open(cesta, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(jb) + 8 + len(binary)))
        f.write(struct.pack("<II", len(jb), 0x4E4F534A))
        f.write(jb)
        f.write(struct.pack("<II", len(binary), 0x004E4942))
        f.write(binary)


def bytes_glb():
    import os
    import tempfile
    fd, p = tempfile.mkstemp(suffix=".glb")
    os.close(fd)
    try:
        zapis(p, *kvadr())
        return open(p, "rb").read()
    finally:
        os.unlink(p)


if __name__ == "__main__":
    zapis(sys.argv[1], *kvadr())
    print("zapsano", sys.argv[1])
