#!/usr/bin/env python3
"""Generator GLB perforovanych oceloveho panelu na naradi (bot8, 2026-10-07; Robert: "integruj do generatoru dalsi velikosti perforovanych panelu ... nejvetsi je 1975 x 460, ten si musis vyrobit").

Tvar je odmereny na stavajicim panelu 1190 x 460 (karta 4931) a na CAD modelech 1481 / 1671 (Rhino .3dm od Roberta, rozmery upresnil 1481 a 1671 mm):
  * plech 1,288 mm, po obvodu lem (stena 1,0 mm) vysoky 15 mm (celkova tloustka dilu 15 mm), lem probiha po vsech ctyrech stranach;
  * ctvercove otvory 10 x 10 mm v pravidelne mrizce: svisle 12 radku s roztecí 38 mm (okraj (vyska - 11 x 38 - 10) / 2: 16 mm u vysky 460, 13,5 mm u 455);
    vodorovne ROZTEC SE PRIZPUSOBUJE delce (pocet sloupcu a okraj dava CAD: 1481 -> 40 sloupcu, okraj 19 mm; 1671 -> 44, okraj 26,8; 1975 (dorobeno, ve stylu 1671, stejna hustota otvoru) -> 52, okraj 26,8);
  * mrizka je SYMETRICKA v obrysu (CAD ma ve vodorovne mrizce jednu nepravidelnost, ta je vyrovnana).
Souradnice dilu STEJNE jako GLB karty 4931 (sablony stolu s nimi pocitaji): X = delka, Y = tloustka (plech u Y = 0, lem nahoru do Y = 15), Z = vyska; pocatek ve STREDU obalky.
Vystup: GLB bez materialu (barvu urcuje `render_material_key`/scena), jeden mesh, ploche normaly, uzel bez transformace (pozadavek stul_glb.nacti_mesh).

Pouziti (z korene repa):
  api/venv/bin/python3 scripts/2026-10-07_perfopanel/gen_perfopanel.py --typ 1481 --vystup /cesta/product_XXXX.glb
  api/venv/bin/python3 scripts/2026-10-07_perfopanel/gen_perfopanel.py --vse /cesta/adresar        # product_<id>.glb pro vsechny typy podle PANELY_ID (po zalozeni karet)
  ... --kontrola   jen vypise rozmery / pocet otvoru / vodotesnost"""
import argparse
import os
import sys

import numpy as np
import trimesh

TL_PLECH = 1.288          # tloustka plechu (mm) - z GLB karty 4931 i z CAD
TL_LEM = 1.0              # tloustka steny lemu (mm)
VYSKA_LEMU = 15.0         # celkova tloustka dilu = vyska lemu (mm)
OTVOR = 10.0              # ctvercovy otvor 10 x 10 mm
RADKY = 12                # svislych radku otvoru
ROZTEC_Z = 38.0

# typ (delka v mm) -> parametry mrizky; vyska, pocet sloupcu a okraj (od hrany plechu k hrane krajniho otvoru, mm)
TYPY = {
    1190: dict(vyska=460.0, sloupcu=31, okraj=20.0, roztec=38.0),         # stavajici karta 4931 (kontrolni typ: generator ho musi vyrobit shodne s katalogem)
    1481: dict(vyska=460.0, sloupcu=40, okraj=19.0),
    1671: dict(vyska=455.0, sloupcu=44, okraj=26.8),
    1975: dict(vyska=460.0, sloupcu=52, okraj=26.8),
}


def hrany_otvoru(delka, sloupcu, okraj, roztec=None):
    """[(x0, x1)] sloupcu otvoru: okraj od obou konci, rovnomerna roztec (rozdil stredu); roztec=None = dopocte se, aby mrizka vyplnila obrys symetricky."""
    if roztec is None:
        roztec = (delka - 2 * okraj - OTVOR) / (sloupcu - 1)
    x0 = (delka - ((sloupcu - 1) * roztec + OTVOR)) / 2.0
    return [(x0 + k * roztec, x0 + k * roztec + OTVOR) for k in range(sloupcu)], roztec


def hrany_radku(vyska):
    z0 = (vyska - ((RADKY - 1) * ROZTEC_Z + OTVOR)) / 2.0
    return [(z0 + k * ROZTEC_Z, z0 + k * ROZTEC_Z + OTVOR) for k in range(RADKY)]


def sestav(delka, vyska, sloupcu, okraj, roztec=None):
    """(vertices, normals, faces, info): watertight sit; bunkova mrizka (kazda bunka = otvor / plech / lem) -> vsechny steny mezi sousedy."""
    sx, roztec_x = hrany_otvoru(delka, sloupcu, okraj, roztec)
    sz = hrany_radku(vyska)
    xs = sorted({0.0, TL_LEM, delka - TL_LEM, delka, *[v for h in sx for v in h]})
    zs = sorted({0.0, TL_LEM, vyska - TL_LEM, vyska, *[v for h in sz for v in h]})
    xs = np.array(xs); zs = np.array(zs)
    nx, nz = len(xs) - 1, len(zs) - 1
    cx = (xs[:-1] + xs[1:]) / 2.0; cz = (zs[:-1] + zs[1:]) / 2.0
    h = np.zeros((nx, nz))
    for i in range(nx):
        for j in range(nz):
            lem = cx[i] < TL_LEM or cx[i] > delka - TL_LEM or cz[j] < TL_LEM or cz[j] > vyska - TL_LEM
            if lem:
                h[i, j] = VYSKA_LEMU
            else:
                v_otvoru = any(a < cx[i] < b for a, b in sx) and any(a < cz[j] < b for a, b in sz)
                h[i, j] = 0.0 if v_otvoru else TL_PLECH
    quady = []          # (4 rohy CCW zvenku, normala)

    def q(p0, p1, p2, p3, n):
        quady.append(((p0, p1, p2, p3), n))
    for i in range(nx):
        for j in range(nz):
            hh = h[i, j]
            if hh <= 0:
                continue
            x0, x1, z0, z1 = xs[i], xs[i + 1], zs[j], zs[j + 1]
            # dno (y = 0, normala -Y) a vrch (y = hh, normala +Y); osy: X, Y(tloustka), Z
            q((x0, 0, z0), (x1, 0, z0), (x1, 0, z1), (x0, 0, z1), (0, -1, 0))
            q((x0, hh, z0), (x0, hh, z1), (x1, hh, z1), (x1, hh, z0), (0, 1, 0))
            # steny k sousedum: vyssi bunka kryje rozdil vysek
            for (di, dj, nrm) in ((1, 0, (1, 0, 0)), (-1, 0, (-1, 0, 0)), (0, 1, (0, 0, 1)), (0, -1, (0, 0, -1))):
                ii, jj = i + di, j + dj
                hs = h[ii, jj] if (0 <= ii < nx and 0 <= jj < nz) else 0.0
                if hs >= hh:
                    continue
                if di == 1:
                    q((x1, hs, z0), (x1, hh, z0), (x1, hh, z1), (x1, hs, z1), nrm)
                elif di == -1:
                    q((x0, hs, z1), (x0, hh, z1), (x0, hh, z0), (x0, hs, z0), nrm)
                elif dj == 1:
                    q((x0, hs, z1), (x1, hs, z1), (x1, hh, z1), (x0, hh, z1), nrm)
                else:
                    q((x1, hs, z0), (x0, hs, z0), (x0, hh, z0), (x1, hh, z0), nrm)
    P = np.array([p for qq, n in quady for p in qq], dtype=np.float64).reshape(-1, 3)
    N = np.repeat(np.array([n for qq, n in quady], dtype=np.float64), 4, axis=0)
    F = np.arange(len(P)).reshape(-1, 4)
    tri = np.vstack([F[:, [0, 1, 2]], F[:, [0, 2, 3]]])
    # sloucit shodne (poloha, normala) vrcholy
    klic = np.round(np.hstack([P, N]), 4)
    uniq, inv = np.unique(klic, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    V = uniq[:, :3]; Nn = uniq[:, 3:]
    T = inv[tri]
    # odstranit degenerovane trojuhelniky
    A = V[T[:, 1]] - V[T[:, 0]]; B = V[T[:, 2]] - V[T[:, 0]]
    ok = np.linalg.norm(np.cross(A, B), axis=1) > 1e-9
    T = T[ok]
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True)
    assert float(((fn * Nn[T[:, 0]]).sum(axis=1)).min()) > 0.999, "otaceni trojuhelniku nesedi s deklarovanou normalou"
    # stred obalky do pocatku
    lo, hi = V.min(0), V.max(0)
    V = V - (lo + hi) / 2.0
    info = {"delka": delka, "vyska": vyska, "sloupcu": sloupcu, "radku": RADKY, "otvoru": sloupcu * RADKY, "roztec_x": roztec_x, "okraj_x": float(sx[0][0]), "okraj_z": float(sz[0][0])}
    return V, Nn, T, info


def vyrob(delka, vystup=None, kontrola=False):
    par = dict(TYPY[delka])
    V, N, T, info = sestav(delka, par["vyska"], par["sloupcu"], par["okraj"], par.get("roztec"))
    m = trimesh.Trimesh(vertices=V.astype(np.float32), faces=T, vertex_normals=N.astype(np.float32), process=False)
    info.update(vodotesny=bool(m.is_watertight), jednotne_otaceni=bool(m.is_winding_consistent), objem_mm3=float(m.volume), trojuhelniku=int(len(T)), vrcholu=int(len(V)),
                rozmer=[round(float(v), 3) for v in (m.bounds[1] - m.bounds[0])])
    if vystup and not kontrola:
        os.makedirs(os.path.dirname(os.path.abspath(vystup)), exist_ok=True)
        data = m.export(file_type="glb")
        with open(vystup, "wb") as f:
            f.write(data)
        info["soubor"] = vystup
        info["bajtu"] = len(data)
    return info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--typ", type=int, choices=sorted(TYPY))
    ap.add_argument("--vystup")
    ap.add_argument("--vse", help="adresar: zapise product_<id>.glb podle PANELY_ID")
    ap.add_argument("--kontrola", action="store_true")
    a = ap.parse_args()
    if a.vse:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "api"))
        PANELY_ID = {1481: None, 1671: None, 1975: None}      # po zalozeni karet doplnit (viz zaloz_karty.py -> vypise id)
        raise SystemExit("--vse: pouzij --typ + --vystup (id karet viz zaloz_karty.py)")
    typy = [a.typ] if a.typ else sorted(TYPY)
    for t in typy:
        print(vyrob(t, a.vystup if a.typ else None, kontrola=a.kontrola or not a.vystup))


if __name__ == "__main__":
    main()
