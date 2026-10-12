"""STEP -> GLB (jen vývojový nástroj, vyžaduje `pip install cadquery-ocp`; testy ani modul ho nepotřebují).
Použití:  python3 -I step_na_glb.py <vstup.step> <výstup.glb> [lin_deflection_mm]
Postup: každé těleso (solid) STEPu se protriangulujeme BRepMesh_IncrementalMesh, vrcholy se po plochách ZACHOVAJÍ
nesdílené (hladké normály jen uvnitř jedné plochy), výsledek se POSUNE tak, aby STŘED OBÁLKY CELKU byl v počátku
(úmluva: pozice dílu = požadovaný střed − R·střed GLB, tedy střed GLB = (0,0,0)); původní střed obálky ve STEPu se
zapíše do `extras.posun_ze_stepu`. Každé těleso je samostatná primitiva se jménem (`extras`: index, bbox ve STEP souřadnicích).
Osy zůstávají jako ve STEPu (SolidWorks, mm): X šířka, Y nahoru, Z podél dráhy."""
import json
import struct
import sys

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Bnd import Bnd_Box
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS


def nacti(cesta):
    r = STEPControl_Reader()
    r.ReadFile(cesta)
    r.TransferRoots()
    return r.OneShape()


def bbox(sh):
    b = Bnd_Box()
    BRepBndLib.Add_s(sh, b)
    a, c = b.CornerMin(), b.CornerMax()
    return np.array([a.X(), a.Y(), a.Z()]), np.array([c.X(), c.Y(), c.Z()])


def sit_telesa(solid, defl):
    BRepMesh_IncrementalMesh(solid, defl, False, 0.2, True)
    P, N, I = [], [], []
    n0 = 0
    f = TopExp_Explorer(solid, TopAbs_FACE)
    while f.More():
        face = TopoDS.Face(f.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            tr = loc.Transformation()
            pts = np.array([[tri.Node(i).Transformed(tr).X(), tri.Node(i).Transformed(tr).Y(), tri.Node(i).Transformed(tr).Z()]
                            for i in range(1, tri.NbNodes() + 1)])
            tt = np.array([[tri.Triangle(i).Value(1), tri.Triangle(i).Value(2), tri.Triangle(i).Value(3)]
                           for i in range(1, tri.NbTriangles() + 1)]) - 1
            if face.Orientation() == TopAbs_REVERSED:
                tt = tt[:, [0, 2, 1]]
            fn = np.cross(pts[tt[:, 1]] - pts[tt[:, 0]], pts[tt[:, 2]] - pts[tt[:, 0]])
            nv = np.zeros_like(pts)
            for k in range(3):
                np.add.at(nv, tt[:, k], fn)
            l = np.linalg.norm(nv, axis=1, keepdims=True)
            nv = nv / np.where(l > 0, l, 1)
            P.append(pts)
            N.append(nv)
            I.append(tt + n0)
            n0 += len(pts)
        f.Next()
    return np.concatenate(P), np.concatenate(N), np.concatenate(I)


def main():
    step, out = sys.argv[1], sys.argv[2]
    defl = float(sys.argv[3]) if len(sys.argv) > 3 else 0.15
    s = nacti(step)
    mn, mx = bbox(s)
    stred = (mn + mx) / 2
    telesa = []
    e = TopExp_Explorer(s, TopAbs_SOLID)
    while e.More():
        so = TopoDS.Solid(e.Current())
        a, b = bbox(so)
        P, N, I = sit_telesa(so, defl)
        telesa.append((P - stred, N, I, a, b))
        e.Next()
    buf = bytearray()
    views, accs, prims = [], [], []

    def pridej(arr, typ, comp, target, minmax=False, count_type="VEC3"):
        while len(buf) % 4:
            buf.append(0)
        off = len(buf)
        buf.extend(arr.tobytes())
        views.append({"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes, "target": target})
        a = {"bufferView": len(views) - 1, "componentType": comp, "count": int(len(arr)), "type": count_type}
        if minmax:
            a["min"] = [float(x) for x in arr.min(0)]
            a["max"] = [float(x) for x in arr.max(0)]
        accs.append(a)
        return len(accs) - 1

    for i, (P, N, I, a, b) in enumerate(telesa):
        ip = pridej(P.astype("<f4"), 5126, 5126, 34962, True)
        inn = pridej(N.astype("<f4"), 5126, 5126, 34962)
        ii = pridej(I.astype("<u4").reshape(-1), 5125, 5125, 34963, False, "SCALAR")
        prims.append({"attributes": {"POSITION": ip, "NORMAL": inn}, "indices": ii, "mode": 4,
                      "extras": {"index": i, "bbox_step": [[round(float(x), 3) for x in a], [round(float(x), 3) for x in b]]}})
    gltf = {
        "asset": {"version": "2.0", "generator": "step_na_glb.py (OCP)"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "draha_5276"}],
        "meshes": [{"name": "draha_5276", "primitives": prims,
                    "extras": {"posun_ze_stepu": [round(float(x), 4) for x in stred], "jednotky": "mm",
                               "osy": "X sirka, Y nahoru, Z podel drahy; stred obalky v pocatku"}}],
        "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    while len(buf) % 4:
        buf.append(0)
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(out, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(buf), 0x004E4942) + bytes(buf))
    print(out, len(telesa), "těles,", sum(len(t[2]) for t in telesa), "trojúhelníků,", round(total / 1024), "kB; střed STEP", stred.round(3).tolist())


if __name__ == "__main__":
    main()
