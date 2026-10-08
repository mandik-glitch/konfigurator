#!/usr/bin/env python3
"""Vandr komponent s PROMENNOU SIRKOU (bot10, 2026-10-05; Robert: "potrebuju upravitelnou sirku nekterych komponentu z vandr", sestava UUID e1dd5c1b-...).

Princip ("natazeni podle roviny"): sestava (nohy + plato) lezi podel osy `os`. Rovina kolmá na osu uprostred sestavy rozdeli vrcholy na dve poloviny; zmena sirky o
delta = W - w0 posune vrcholy za rovinou o +delta/2 a pred rovinou o -delta/2 (stred zustane). Dil, ktery lezi cely na jedne strane (noha, madlo, pojezd, vlozka), se tim
posune jako CELEK (zadna deformace); dil, ktery rovinu protina (kolejnice, deska plata), se prodlouzi / zkrati - presne to, co sirka plata znamena. Predpoklad (hlida
`najdi_rovinu` a test): protinajici dily maji u roviny jen rovne steny (zadne vrcholy v pasmu +-`OKRAJ_MM`), jinak by se detail utrhl.

Modul je bez zavislosti na API (numpy + json + struct): pouziva ho `build_plato.py` (priprava GLB), test a kontrolni scena (stejny vzorec v JS)."""
import json
import struct
import numpy as np

GLB_MAGIC, GLB_VERSION = 0x46546C67, 2
OKRAJ_MM = 30.0                  # protinajici dil nesmi mit vrcholy blize k rovine (jinak by se detail u roviny natahl / utrhl)


# ------------------------------------------------------------------ cteni GLB
def cti_glb(data):
    """(json, bin) z bytes GLB."""
    magic, ver, _ = struct.unpack_from("<III", data, 0)
    if magic != GLB_MAGIC or ver != GLB_VERSION:
        raise ValueError("neni GLB 2.0")
    jl, _ = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + jl].decode("utf-8"))
    bl = struct.unpack_from("<I", data, 20 + jl)[0]
    return js, bytes(data[20 + jl + 8:20 + jl + 8 + bl])


_CT = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def cti_accessor(js, blob, idx):
    a = js["accessors"][idx]
    v = js["bufferViews"][a["bufferView"]]
    ct, nc, n = a["componentType"], _NC[a["type"]], a["count"]
    dt = np.dtype("<" + _CT[ct])
    off = v.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = v.get("byteStride") or dt.itemsize * nc
    if stride == dt.itemsize * nc:
        return np.frombuffer(blob, dtype=dt, count=n * nc, offset=off).reshape(n, nc).copy()
    out = np.empty((n, nc), dt)
    for i in range(n):
        out[i] = np.frombuffer(blob, dtype=dt, count=nc, offset=off + i * stride)
    return out


def _lokalni(n):
    M = np.eye(4)
    if "matrix" in n:
        return np.array(n["matrix"], float).reshape(4, 4).T
    t, q, s = n.get("translation", [0, 0, 0]), n.get("rotation", [0, 0, 0, 1]), n.get("scale", [1, 1, 1])
    x, y, z, w = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    M[:3, :3] = R * np.array(s, float)
    M[:3, 3] = t
    return M


def sber_mesh(js, blob, koren_predpona):
    """Vsechny meshe podstromu, jehoz koren se jmenuje `koren_predpona*` (prvni nalezeny, vcetne potomku), se svetovymi transformacemi VYPECENYMI do vrcholu.
    Vraci seznam {jmeno, cesta, P (n,3 mm), N (n,3), T (m,3 int), mat (index v js['materials'])}; zrcadlena transformace (det < 0) otoci orientaci trojuhelniku."""
    uzly, vystup = js["nodes"], []

    def jde(ni, M, cesta, uvnitr):
        n = uzly[ni]
        W = M @ _lokalni(n)
        jm = n.get("name", "?")
        uv = uvnitr or jm.startswith(koren_predpona)
        if uv and "mesh" in n:
            R3 = W[:3, :3]
            norm_m = np.linalg.inv(R3).T
            zrcadlo = np.linalg.det(R3) < 0
            for pr in js["meshes"][n["mesh"]]["primitives"]:
                if pr.get("mode", 4) != 4:
                    raise ValueError("primitiva neni trojuhelniky")
                P = cti_accessor(js, blob, pr["attributes"]["POSITION"]).astype(float)
                P = (np.c_[P, np.ones(len(P))] @ W.T)[:, :3]
                if "NORMAL" in pr["attributes"]:
                    N = cti_accessor(js, blob, pr["attributes"]["NORMAL"]).astype(float) @ norm_m.T
                    ln = np.linalg.norm(N, axis=1, keepdims=True)
                    N = N / np.where(ln == 0, 1, ln)
                else:
                    N = np.zeros_like(P)
                T = cti_accessor(js, blob, pr["indices"]).astype(np.int64).reshape(-1, 3) if "indices" in pr else np.arange(len(P)).reshape(-1, 3)
                if zrcadlo:
                    T = T[:, [0, 2, 1]]
                vystup.append({"jmeno": jm, "cesta": cesta + "/" + jm, "P": P, "N": N, "T": T, "mat": pr.get("material", 0)})
        for c in n.get("children", []):
            jde(c, W, cesta + "/" + jm, uv)

    for r in js["scenes"][js.get("scene", 0)]["nodes"]:
        jde(r, np.eye(4), "", False)
    return vystup


# ------------------------------------------------------------------ pravidlo natazeni
def natahni(P, os_, rovina, delta):
    """Vrcholy P (n,3) po zmene sirky o `delta` mm: za rovinou +delta/2, pred rovinou -delta/2 (po ose `os_`); vrcholy PRESNE na rovine zustavaji (nemaji tam byt)."""
    Q = np.array(P, float, copy=True)
    s = Q[:, os_]
    Q[:, os_] = s + np.where(s > rovina, delta / 2.0, np.where(s < rovina, -delta / 2.0, 0.0))
    return Q


def protinajici(casti, os_, rovina):
    """Casti, jejichz vrcholy lezi na obou stranach roviny."""
    return [c for c in casti if c["P"][:, os_].min() < rovina < c["P"][:, os_].max()]


def najdi_rovinu(casti, os_, stred, okno_mm=150.0, krok_mm=0.5):
    """Rovina nejblize `stred` (po ose `os_`), ktera NEprotina zadny dil blizko jeho vrcholu (vsechny protinajici dily maji v pasmu +-OKRAJ_MM nulu vrcholu).
    Vraci (rovina, [casti ktere protina]); ValueError, kdyz v okne zadna takova neni (stredova rovina by trhala detail)."""
    kandidati = [stred] + [stred + s * k for k in np.arange(krok_mm, okno_mm + krok_mm, krok_mm) for s in (1, -1)]
    for r in kandidati:
        pr = protinajici(casti, os_, r)
        if all(not (np.abs(c["P"][:, os_] - r) < OKRAJ_MM).any() for c in pr):
            return float(r), pr
    raise ValueError("v okne +-%.0f mm kolem stredu neni rovina bez detailu u protinajicich dilu" % okno_mm)


# ------------------------------------------------------------------ zapis GLB
def zapis_glb(casti, materialy, spec, extras_navic=None):
    """GLB (bytes): kazda cast = jeden uzel s jednou sit (jmeno zachovano), materialy z predlohy, `scenes[0].extras.v3d` = spec, `extras_navic` = dalsi klice extras."""
    blob = bytearray()
    views, accessors, meshes, nodes = [], [], [], []

    def pridej(data, target):
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        return len(views) - 1

    pouzite, mapa = [], {}
    for c in casti:
        if c["mat"] not in mapa:
            mapa[c["mat"]] = len(pouzite)
            pouzite.append(materialy[c["mat"]])
    for c in casti:
        P, N, T = c["P"].astype("<f4"), c["N"].astype("<f4"), c["T"].astype("<u4").ravel()
        vp, vn, vi = pridej(P.tobytes(), 34962), pridej(N.tobytes(), 34962), pridej(T.tobytes(), 34963)
        accessors.append({"bufferView": vp, "componentType": 5126, "count": len(P), "type": "VEC3",
                          "min": [float(x) for x in P.min(axis=0)], "max": [float(x) for x in P.max(axis=0)]})
        a = len(accessors) - 1
        accessors.append({"bufferView": vn, "componentType": 5126, "count": len(N), "type": "VEC3"})
        accessors.append({"bufferView": vi, "componentType": 5125, "count": len(T), "type": "SCALAR"})
        meshes.append({"primitives": [{"attributes": {"POSITION": a, "NORMAL": a + 1}, "indices": a + 2, "material": mapa[c["mat"]], "mode": 4}]})
        nodes.append({"name": c["jmeno"], "mesh": len(meshes) - 1})
    extras = {"v3d": spec}
    extras.update(extras_navic or {})
    js = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": list(range(len(nodes))), "extras": extras}],
          "nodes": nodes, "meshes": meshes, "materials": pouzite, "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    jb = json.dumps(js, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    jb += b" " * ((4 - len(jb) % 4) % 4)
    while len(blob) % 4:
        blob.append(0)
    celkem = 12 + 8 + len(jb) + 8 + len(blob)
    return (struct.pack("<III", GLB_MAGIC, GLB_VERSION, celkem) + struct.pack("<II", len(jb), 0x4E4F534A) + jb +
            struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))
