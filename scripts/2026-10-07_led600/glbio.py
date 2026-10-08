"""Minimalni cteni/zapis jednomeshoveho GLB (POSITION + NORMAL + indices) - bot8 2026-10-07 (LED 600)."""
import json, struct
import numpy as np


def cti(path):
    d = open(path, "rb").read()
    jl, _ = struct.unpack_from("<II", d, 12)
    j = json.loads(d[20:20 + jl])
    bl, _ = struct.unpack_from("<II", d, 20 + jl)
    b = d[28 + jl: 28 + jl + bl]
    acc = j["accessors"]; bv = j["bufferViews"]
    prim = j["meshes"][0]["primitives"][0]

    def arr(i, dt, n):
        a = acc[i]; v = bv[a["bufferView"]]
        return np.frombuffer(b, dtype=dt, count=a["count"] * n, offset=v.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, n) if n > 1 else \
            np.frombuffer(b, dtype=dt, count=a["count"], offset=v.get("byteOffset", 0) + a.get("byteOffset", 0))
    pos = arr(prim["attributes"]["POSITION"], "<f4", 3).astype(np.float64)
    nrm = arr(prim["attributes"]["NORMAL"], "<f4", 3).astype(np.float64)
    idx = arr(prim["indices"], "<u4", 1).astype(np.int64).reshape(-1, 3)
    return j, pos, nrm, idx
