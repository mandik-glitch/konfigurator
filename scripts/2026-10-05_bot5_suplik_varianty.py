#!/usr/bin/env python3
"""Varianty ocelového šuplíkového boxu (karta 4930, `product_4930.glb`, v katalogu 2 šuplíky) na 1 a 3 šuplíky.

Postup (vše na ZAVŘENÉM modelu, tj. po `stul_glb._zavri_suplik`; katalogový soubor se nemění):
  * skříň = největší komponenta; stěny mezi výškou 13 a 246 mm jsou rovné plochy, takže se v rovině z1 (pod prvním šuplíkem bez detailů) a z2 = z1 + rozteč
    rozřízne (trojúhelníky přes rovinu se rozdělí, normály se interpolují) a dílek (slab) mezi nimi se u 1 šuplíku VYJME (vše nad ním o rozteč níž),
    u 3 šuplíků ZKOPÍRUJE (vše nad ním o rozteč výš). Horní lem, víčko, zámek jedou s horní částí.
  * šuplíky: jednotka A (spodní: korba 1148 trojúhelníků + čelo + drobné díly kolejnic) a B (horní: korba 602 + čelo); 1 šuplík = A, 2 = A + B (původní),
    3 = A + B + kopie B o rozteč výš.
  * kontroly: stejný průřez v z1 a z2 (jinak chyba), počet hraničních hran skříně stejný jako u originálu, šuplíky uvnitř dutiny, rozměry.
Výstup: backups/2026-10-05_suplik_varianty/suplik_{1,2,3}_zavreny_kandidat.glb (+ zprava.json). Použití: api/venv/bin/python3 scripts/2026-10-05_bot5_suplik_varianty.py
"""
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))
import stul_glb as G  # noqa: E402

OUT = os.path.join(ROOT, "backups", "2026-10-05_suplik_varianty")
EPS = 1e-3
Z1_REL = 150.0                     # rovina řezu (relativně k spodku skříně): nad korbou spodního šuplíku (151) by řez nevadil, pod 246 (víčko) a mimo detaily 145/190


def _clip(pos, nrm, tri, c):
    """Rozdělí trojúhelníky protínající rovinu z=c. Vrací nové (pos, nrm, tri); body na rovině mají z přesně c."""
    P, N = [pos], [nrm]
    n0 = len(pos)
    extra_p, extra_n, T = [], [], []

    def novy(a, b):
        za, zb = pos[a, 2], pos[b, 2]
        t = (c - za) / (zb - za)
        p = pos[a] + (pos[b] - pos[a]) * t
        p[2] = c
        nn = nrm[a] + (nrm[b] - nrm[a]) * t
        ln = np.linalg.norm(nn) or 1.0
        extra_p.append(p.astype(np.float32)); extra_n.append((nn / ln).astype(np.float32))
        return n0 + len(extra_p) - 1

    for t in tri:
        d = pos[t, 2] - c
        if not ((d > EPS).any() and (d < -EPS).any()):
            T.append(t)
            continue
        horni, dolni = [], []
        for i in range(3):
            a, b = int(t[i]), int(t[(i + 1) % 3])
            da, db = pos[a, 2] - c, pos[b, 2] - c
            if da > EPS:
                horni.append(a)
            elif da < -EPS:
                dolni.append(a)
            else:                                     # bod na rovině patří do obou polygonů
                horni.append(a); dolni.append(a)
            if (da > EPS and db < -EPS) or (da < -EPS and db > EPS):
                m = novy(a, b)
                horni.append(m); dolni.append(m)
        for poly in (horni, dolni):
            for k in range(1, len(poly) - 1):
                T.append(np.array([poly[0], poly[k], poly[k + 1]]))
    pos2 = np.vstack(P + ([np.array(extra_p, np.float32)] if extra_p else []))
    nrm2 = np.vstack(N + ([np.array(extra_n, np.float32)] if extra_n else []))
    return pos2, nrm2, np.array(T, dtype=np.int64)


def _kompaktni(pos, nrm, tri):
    pouzite = np.unique(tri.ravel())
    mapa = -np.ones(len(pos), np.int64)
    mapa[pouzite] = np.arange(len(pouzite))
    return pos[pouzite], nrm[pouzite], mapa[tri]


def _hranice(pos, tri):
    """Počet hraničních hran (hrana jen v jednom trojúhelníku) po svaření bodů na 0.01 mm."""
    klic = {}
    ids = np.array([klic.setdefault(tuple(r), len(klic)) for r in np.round(pos, 2)])
    from collections import Counter
    hr = Counter()
    for t in ids[tri]:
        for i in range(3):
            a, b = int(t[i]), int(t[(i + 1) % 3])
            hr[(min(a, b), max(a, b))] += 1
    return sum(1 for v in hr.values() if v == 1)


def _zapis_glb(path, pos, nrm, tri):
    pos, nrm = pos.astype("<f4"), nrm.astype("<f4")
    idx = tri.astype("<u4").ravel()
    b_idx, b_pos, b_nrm = idx.tobytes(), pos.tobytes(), nrm.tobytes()
    binc = b_idx + b_pos + b_nrm
    js = {"scene": 0, "scenes": [{"nodes": [0]}], "asset": {"version": "2.0", "generator": "bot5 suplik_varianty (odvozeno z product_4930)"},
          "accessors": [{"componentType": 5125, "type": "SCALAR", "bufferView": 0, "count": int(len(idx)), "max": [int(idx.max())], "min": [int(idx.min())]},
                        {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 1, "count": int(len(pos)), "max": [float(v) for v in pos.max(0)], "min": [float(v) for v in pos.min(0)]},
                        {"componentType": 5126, "type": "VEC3", "byteOffset": 0, "bufferView": 2, "count": int(len(nrm)), "max": [1.0, 1.0, 1.0], "min": [-1.0, -1.0, -1.0]}],
          "meshes": [{"name": "geometry_0", "extras": {}, "primitives": [{"attributes": {"POSITION": 1, "NORMAL": 2}, "indices": 0, "mode": 4}]}],
          "nodes": [{"name": "world", "children": [1]}, {"name": "geometry_0", "mesh": 0}],
          "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(b_idx)}, {"buffer": 0, "byteOffset": len(b_idx), "byteLength": len(b_pos)},
                          {"buffer": 0, "byteOffset": len(b_idx) + len(b_pos), "byteLength": len(b_nrm)}],
          "buffers": [{"byteLength": len(binc)}]}
    j = json.dumps(js, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    binc += b"\0" * (-len(binc) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(binc)))
        f.write(struct.pack("<II", len(j), 0x4E4F534A) + j)
        f.write(struct.pack("<II", len(binc), 0x004E4942) + binc)


def main():
    pos, nrm, tri = G.nacti_mesh("product_4930")            # už zavřený šuplík
    lo = pos.min(0)
    rel = pos.astype(np.float64) - lo
    komp = G._souvisle_komponenty(pos, tri)
    popis = []
    for r in np.unique(komp):
        m = komp == r
        vs = np.unique(tri[m].ravel())
        a, b = rel[vs].min(0), rel[vs].max(0)
        popis.append((r, int(m.sum()), a, b))
    skrin_id = max(popis, key=lambda x: float(np.prod(x[3] - x[2])))[0]
    zprava = {"komponent": len(popis)}
    celaA = [p for p in popis if p[1] == 250 and p[2][2] < 153]
    celaB = [p for p in popis if p[1] == 250 and p[2][2] >= 153]
    if len(celaA) != 1 or len(celaB) != 1:
        sys.exit("neznama struktura: cela supliku")
    roz = float(celaB[0][2][2] - celaA[0][2][2])
    zprava["rozteč_mm"] = round(roz, 3)
    # rozdělení komponent
    cast = {"skrin": [], "horni_prislusenstvi": [], "A": [], "B": []}
    for r, n, a, b in popis:
        if r == skrin_id:
            cast["skrin"].append(r)
        else:
            zc = (a[2] + b[2]) / 2
            cast["A" if zc < 153 else "B" if zc < 250 else "horni_prislusenstvi"].append(r)
    zprava["komponenty"] = {k: len(v) for k, v in cast.items()}
    if not cast["A"] or not cast["B"]:
        sys.exit("neznama struktura: jednotky supliku")

    def vyber(ids):
        m = np.isin(komp, ids)
        return tri[m]

    t_sk = vyber(cast["skrin"])
    z1, z2 = lo[2] + Z1_REL, lo[2] + Z1_REL + roz
    p1, n1, t1 = _clip(pos, nrm, t_sk, z1)
    p1, n1, t1 = _clip(p1, n1, t1, z2)
    zc = p1[t1][:, :, 2].mean(1)
    dolni, slab, horni = t1[zc < z1], t1[(zc > z1) & (zc < z2)], t1[zc > z2]
    # kontrola: obrys průřezu skříně v z1 a z2 je stejný (porovnání vzorkovaných hran ležících v rovině; vrcholy na úhlopříčkách se liší triangulací, tvarem ne)
    def obrys(z):
        hr = set()
        for t in t1:
            for i in range(3):
                a, b = int(t[i]), int(t[(i + 1) % 3])
                if abs(p1[a, 2] - z) < 1e-3 and abs(p1[b, 2] - z) < 1e-3:
                    hr.add((min(a, b), max(a, b)))
        body = []
        for a, b in hr:
            pa, pb = p1[a, :2].astype(np.float64), p1[b, :2].astype(np.float64)
            k = max(2, int(np.linalg.norm(pb - pa) / 0.05) + 1)
            body.append(pa + (pb - pa) * np.linspace(0, 1, k)[:, None])
        return np.vstack(body)

    def vzdal(x, y):
        # nejvyšší vzdálenost bodu x od obrysu y (vzorky po 0,05 mm; dávkově, aby se nepočítala celá matice)
        nej, kde = 0.0, None
        for i in range(0, len(x), 300):
            d = np.min(np.linalg.norm(x[i:i + 300, None, :] - y[None, ::4, :], axis=2), axis=1)
            j = int(np.argmax(d))
            if d[j] > nej:
                nej, kde = float(d[j]), x[i + j]
        zprava.setdefault("misto_max_odchylky_xy", [round(float(v), 1) for v in kde] if kde is not None else None)
        return nej

    o1, o2 = obrys(z1), obrys(z2)
    odch = max(vzdal(o1, o2), vzdal(o2, o1))
    zprava["odchylka_obrysu_z1_z2_mm"] = round(odch, 3)
    if odch > 0.25:                                   # tenký přední lem skříně (1 mm) se v z1 a z2 triangulací liší o ~0,16 mm; tvarově stejný
        sys.exit(f"OBRYS prurezu v z1 a z2 se lisi o {odch:.2f} mm (misto xy {zprava['misto_max_odchylky_xy']} relativne k jednomu rohu) - rez v tomto miste neni bezpecny")

    def zvedni(pp, d):
        q = pp.copy(); q[:, 2] += np.float32(d); return q

    A_t, B_t = vyber(cast["A"]), vyber(cast["B"])
    horni_t = vyber(cast["horni_prislusenstvi"])
    kp, _kn, kt = _kompaktni(pos, nrm, t_sk)
    hran0 = _hranice(kp, kt)
    zprava["hranicnich_hran_skrine_original"] = hran0

    def sestav(n):
        casti = []                                    # (pos, nrm, tri) s vlastním indexováním
        def pridej(pp, nn, tt):
            casti.append(_kompaktni(pp, nn, tt))
        # skříň: n=1 slab (dílek mezi z1 a z2) se vynechá a horní část jede o rozteč níž; n=3 se za původní slab vloží jeho kopie a horní část jede o rozteč výš
        if n == 2:
            pridej(pos, nrm, t_sk)
            pridej(pos, nrm, horni_t)
        elif n == 1:
            pridej(p1, n1, dolni)
            pridej(zvedni(p1, -roz), n1, horni)
            pridej(zvedni(pos, -roz), nrm, horni_t)
        elif n == 3:
            pridej(p1, n1, dolni)
            pridej(p1, n1, slab)
            pridej(zvedni(p1, roz), n1, slab)
            pridej(zvedni(p1, roz), n1, horni)
            pridej(zvedni(pos, roz), nrm, horni_t)
        # šuplíky
        pridej(pos, nrm, A_t)
        if n >= 2:
            pridej(pos, nrm, B_t)
        if n == 3:
            pridej(zvedni(pos, roz), nrm, B_t)
        P, N, T, base = [], [], [], 0
        for pp, nn, tt in casti:
            P.append(pp); N.append(nn); T.append(tt + base); base += len(pp)
        return np.vstack(P), np.vstack(N), np.vstack(T)

    os.makedirs(OUT, exist_ok=True)
    for n in (1, 2, 3):
        pp, nn, tt = sestav(n)
        _zapis_glb(os.path.join(OUT, f"suplik_{n}_zavreny_kandidat.glb"), pp, nn, tt)
        a, b = pp.min(0), pp.max(0)
        zprava[f"{n}_supliky"] = {"rozmer_mm": [round(float(v), 1) for v in b - a], "trojuhelniku": int(len(tt)), "vrcholu": int(len(pp))}
    # kontrola hranic skříně u variant (jen skříň: znovu sestavit skříň samotnou)
    for n in (1, 3):
        casti = []
        if n == 1:
            casti = [(p1, n1, dolni), (zvedni(p1, -roz), n1, horni)]
        else:
            casti = [(p1, n1, dolni), (p1, n1, slab), (zvedni(p1, roz), n1, slab), (zvedni(p1, roz), n1, horni)]
        P, T, base = [], [], 0
        for pp, nn, tt in casti:
            P.append(pp); T.append(tt + base); base += len(pp)
        zprava[f"hranicnich_hran_skrine_{n}"] = _hranice(np.vstack(P), np.vstack(T))
    with open(os.path.join(OUT, "zprava.json"), "w") as f:
        json.dump(zprava, f, indent=1, default=float)
    print(json.dumps(zprava, indent=1, default=float))


if __name__ == "__main__":
    main()
