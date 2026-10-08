#!/usr/bin/env python3
"""Zkraceni modelu LED 1200 (product_4929.glb) na LED 600 vyriznutim PRESNE 600 mm ze stredu (bot8, 2026-10-07; Robert: "udelej mu 3D model zkracenim LED 1200").

Postup (bez knihoven, jen numpy): 1) presny rez dvema rovinami x = X1 a x = X2 (Sutherland-Hodgman po trojuhelnicich, vrcholy na rovine = nove sdilene vrcholy po hranach),
2) pravy dil se posune o -(X2 - X1) (a oba dily o +/- tak, aby stred bboxu zustal na stejnem miste jako u LED 1200), 3) steny dilu se SLOUCI: vrcholy druheho dilu lezici uvnitr hrany
rezu se do prvniho dilu vlozi (deleni trojuhelniku) a naopak, takze obe hrany rezu maji STEJNE vrcholy (zadne T-spoje), 4) vrcholy na stejnem miste se stejnou normalou se spoji.
Rez musi byt mimo vruby (prurezy v X1 a X2 nejsou presne shodne - povrch je tesselovany tenkymi trojuhelniky s nepatrnymi zlomy - proto se vrcholy rezu praveho dilu PRICHYTI na okraj leveho, max 0,05 mm).

Pouziti:  api/venv/bin/python3 scripts/2026-10-07_led600/led_zkrat.py webapp/katalog/product_4929.glb product_5359.glb 320 920
(X1, X2 = rezne roviny v mm od zacatku modelu; musi lezet mimo vruby 324-356 / 605-637 / 884-916; X2 - X1 = vyrezana delka, tj. 600)."""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glbio import cti

EPS = 1e-7


def orez(P, N, T, x0, nechat_mensi):
    """Ponecha cast trojuhelniku s x <= x0 (nechat_mensi) nebo x >= x0; vrati (P, N, T) nove (kompaktni)."""
    s = (P[:, 0] - x0) * (1.0 if not nechat_mensi else -1.0)          # s >= 0 = ponechat
    in_ = s >= -EPS
    nove_P, nove_N = [p for p in P], [n for n in N]
    hrany = {}
    def prus(a, b):
        k = (min(a, b), max(a, b))
        if k in hrany:
            return hrany[k]
        t = (x0 - P[a, 0]) / (P[b, 0] - P[a, 0])
        p = P[a] + t * (P[b] - P[a]); p[0] = x0
        n = N[a] + t * (N[b] - N[a]); n = n / max(np.linalg.norm(n), 1e-12)
        nove_P.append(p); nove_N.append(n)
        hrany[k] = len(nove_P) - 1
        return hrany[k]
    vysl = []
    for tri in T:
        v = [int(t) for t in tri]
        vn = [in_[a] for a in v]
        if all(vn):
            vysl.append(v)
        elif not any(vn):
            continue
        else:
            poly = []
            for i in range(3):
                a, b = v[i], v[(i + 1) % 3]
                if in_[a]:
                    poly.append(a)
                if in_[a] != in_[b]:
                    poly.append(prus(a, b))
            for i in range(1, len(poly) - 1):
                vysl.append([poly[0], poly[i], poly[i + 1]])
    P2, N2 = np.array(nove_P), np.array(nove_N)
    T2 = np.array(vysl, dtype=np.int64)
    # vyhodit degenerovane (nulova plocha) trojuhelniky
    A = P2[T2[:, 1]] - P2[T2[:, 0]]; B = P2[T2[:, 2]] - P2[T2[:, 0]]
    pl = np.linalg.norm(np.cross(A, B), axis=1) / 2.0
    T2 = T2[pl > 1e-9]
    return P2, N2, T2


def kompakt(P, N, T):
    pouz = np.unique(T.ravel())
    mapa = -np.ones(len(P), dtype=np.int64); mapa[pouz] = np.arange(len(pouz))
    return P[pouz], N[pouz], mapa[T]


def hrany_rezu(P, T, x0):
    """hrany trojuhelniku lezici cele v rovine x = x0 a pouzite JEDNOU (okraj rezu): {(a,b): (index_trojuhelniku, protilehly_vrchol)} se smerem a->b jako v trojuhelniku"""
    cnt = {}
    for ti, tri in enumerate(T):
        for i in range(3):
            a, b, c = int(tri[i]), int(tri[(i + 1) % 3]), int(tri[(i + 2) % 3])
            k = (min(a, b), max(a, b))
            cnt.setdefault(k, []).append((ti, a, b, c))
    out = {}
    for k, lst in cnt.items():
        if len(lst) == 1 and abs(P[k[0], 0] - x0) < 1e-6 and abs(P[k[1], 0] - x0) < 1e-6:
            out[k] = lst[0]
    return out


def vloz_vrcholy(P, N, T, x0, cizi_body):
    """Do hran rezu (x = x0) vlozi vrcholy `cizi_body` (pole (y, z)), ktere lezi uvnitr hrany; deli trojuhelnik vejirem. Vraci nove (P, N, T)."""
    P, N = list(map(np.array, P)), list(map(np.array, N))
    P_, N_ = [p for p in P], [n for n in N]
    P_arr = np.array(P_)
    T_list = [list(map(int, t)) for t in T]
    zmena = True
    nove = 0
    while zmena:
        zmena = False
        Pa = np.array(P_)
        hr = hrany_rezu(Pa, np.array(T_list), x0)
        for (ka, kb), (ti, a, b, c) in hr.items():
            pa, pb = Pa[a][1:], Pa[b][1:]
            d = pb - pa; L2 = float(d @ d)
            if L2 < 1e-12:
                continue
            kandidati = []
            for q in cizi_body:
                t = float((q - pa) @ d) / L2
                if 1e-6 < t < 1 - 1e-6 and np.linalg.norm(pa + t * d - q) < 1e-5:
                    kandidati.append((t, q))
            if not kandidati:
                continue
            kandidati.sort(key=lambda x: x[0])
            vrch = [a]
            for t, q in kandidati:
                pnew = Pa[a] + t * (Pa[b] - Pa[a]); pnew[0] = x0
                nnew = N_[a] + t * (N_[b] - N_[a]); nnew = nnew / max(np.linalg.norm(nnew), 1e-12)
                P_.append(pnew); N_.append(nnew); vrch.append(len(P_) - 1)
            vrch.append(b)
            nahradit = [[vrch[i], vrch[i + 1], c] for i in range(len(vrch) - 1)]
            T_list[ti] = nahradit[0]
            T_list.extend(nahradit[1:])
            nove += len(kandidati)
            zmena = True
            break                                                    # po zmene znovu najit hrany rezu
    return np.array(P_), np.array(N_), np.array(T_list, dtype=np.int64), nove



def segmenty_rezu(P, T, x0):
    """okrajove hrany rezu: seznam (a, b, ti, c) - indexy vrcholu hrany, trojuhelnik a protilehly vrchol; podle indexu (kazdy trojuhelnik rezu ma presne jednu hranu v rovine)"""
    return [(v[1], v[2], v[0], v[3]) for v in hrany_rezu(P, T, x0).values()]


def nejblizsi(q, A, B):
    d = B - A; L2 = np.maximum((d * d).sum(1), 1e-18)
    t = np.clip(((q - A) * d).sum(1) / L2, 0.0, 1.0)
    p = A + t[:, None] * d
    dist = np.linalg.norm(p - q, axis=1)
    i = int(np.argmin(dist))
    return i, float(t[i]), p[i], float(dist[i])


def vloz_body(P, N, T, x0, body, tol):
    """Vlozi body (pole (y, z)) do okrajovych hran rezu x = x0: kazdy bod do NEJBLIZSI hrany (do vzdalenosti tol); bod, ktery uz je vrcholem (<1e-6), se preskoci. Deli trojuhelnik vejirem (zachova orientaci)."""
    P_, N_ = [p for p in P], [n for n in N]
    T_ = [list(map(int, t)) for t in T]
    seg = segmenty_rezu(np.array(P_), np.array(T_), x0)
    if not seg:
        return np.array(P_), np.array(N_), np.array(T_, dtype=np.int64), 0, 0
    A = np.array([P_[a][1:] for a, b, ti, c in seg]); B = np.array([P_[b][1:] for a, b, ti, c in seg])
    prirad = {}
    preskoceno = 0
    for q in body:
        i, t, p, dist = nejblizsi(q, A, B)
        if np.linalg.norm(q - A[i]) < 1e-6 or np.linalg.norm(q - B[i]) < 1e-6:
            preskoceno += 1
            continue
        # i jinde (sousedni hrana) uz muze byt vrchol rovny q
        if min(np.linalg.norm(A - q, axis=1).min(), np.linalg.norm(B - q, axis=1).min()) < 1e-6:
            preskoceno += 1
            continue
        if dist > tol:
            raise SystemExit("bod %s je %.4f mm od hrany rezu (limit %.4f)" % (q, dist, tol))
        prirad.setdefault(i, []).append((t, q))
    vlozeno = 0
    for i, lst in prirad.items():
        a, b, ti, c = seg[i]
        lst.sort(key=lambda x: x[0])
        vrch = [a]
        for t, q in lst:
            pnew = np.array([x0, q[0], q[1]]); nnew = N_[a] + t * (N_[b] - N_[a]); nnew = nnew / max(np.linalg.norm(nnew), 1e-12)
            P_.append(pnew); N_.append(nnew); vrch.append(len(P_) - 1)
        vrch.append(b)
        nahr = [[vrch[k], vrch[k + 1], c] for k in range(len(vrch) - 1)]
        T_[ti] = nahr[0]; T_.extend(nahr[1:])
        vlozeno += len(lst)
    return np.array(P_), np.array(N_), np.array(T_, dtype=np.int64), vlozeno, preskoceno


def prichyt_a_vloz(PL, NL, TL, PR, NR, TR, x0, tol=0.05):
    """Seve se sevrou: 1) vrcholy rezu praveho dilu se prichyti na nejblizsi bod okraje leveho dilu (max tol mm), 2) tyto body se vlozi do leveho dilu, 3) vrcholy leveho dilu, ktere pravy nema, se vlozi do praveho."""
    mL = np.abs(PL[:, 0] - x0) < 1e-6
    segL = segmenty_rezu(PL, TL, x0)
    A = np.array([PL[a][1:] for a, b, ti, c in segL]); B = np.array([PL[b][1:] for a, b, ti, c in segL])
    PR = PR.copy()
    nejv = 0.0
    for i in np.where(np.abs(PR[:, 0] - x0) < 1e-6)[0]:
        _, _, p, dist = nejblizsi(PR[i][1:], A, B)
        if dist > tol:
            raise SystemExit("vrchol rezu praveho dilu je %.4f mm od okraje leveho (limit %.4f)" % (dist, tol))
        nejv = max(nejv, dist)
        PR[i, 1:] = p
    print("  prichyceni praveho rezu k levemu: nejvetsi posun vrcholu %.4f mm" % nejv)
    posR = np.unique(np.round(PR[np.abs(PR[:, 0] - x0) < 1e-6][:, 1:], 7), axis=0)
    PL, NL, TL, v1, s1 = vloz_body(PL, NL, TL, x0, posR, tol)
    posL = np.unique(np.round(PL[np.abs(PL[:, 0] - x0) < 1e-6][:, 1:], 7), axis=0)
    PR, NR, TR, v2, s2 = vloz_body(PR, NR, TR, x0, posL, tol)
    print("  vlozeno do leveho %d, do praveho %d vrcholu" % (v1, v2))
    return PL, NL, TL, PR, NR, TR


def sekce(P, T, x0):
    """Body pruniku hran trojuhelniku s rovinou x = x0 jako mnozina (y, z) (zaokrouhleno)."""
    body = set()
    for tri in T:
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            xa, xb = P[a, 0] - x0, P[b, 0] - x0
            if xa == 0 and xb == 0:
                continue
            if (xa <= 0 <= xb or xb <= 0 <= xa) and xa != xb:
                t = xa / (xa - xb)
                p = P[a] + t * (P[b] - P[a])
                body.add((round(float(p[1]), 3), round(float(p[2]), 3)))
    return body


def hrany_otevrene(P, T, tol=3):
    """pocet hran pouzitych jen jednou po SLOUCENI vrcholu podle polohy (kontrola uzavrenosti)"""
    key = {}
    ids = np.empty(len(P), dtype=np.int64)
    for i, p in enumerate(P):
        k = tuple(np.round(p, tol))
        ids[i] = key.setdefault(k, len(key))
    cnt = {}
    for tri in T:
        a, b, c = ids[tri[0]], ids[tri[1]], ids[tri[2]]
        if len({a, b, c}) < 3:
            continue
        for u, v in ((a, b), (b, c), (c, a)):
            k = (min(u, v), max(u, v))
            cnt[k] = cnt.get(k, 0) + 1
    return sum(1 for v in cnt.values() if v == 1), sum(1 for v in cnt.values() if v > 2)


def zapis_glb(j0, P, N, T, cesta):
    pos = P.astype("<f4"); nor = N.astype("<f4"); idx = T.astype("<u4").ravel()
    b_idx, b_pos, b_nor = idx.tobytes(), pos.tobytes(), nor.tobytes()
    binary = b_idx + b_pos + b_nor
    while len(binary) % 4:
        binary += b"\0"
    j = json.loads(json.dumps(j0))
    j["accessors"][0].update(count=int(idx.size), max=[int(idx.max())], min=[int(idx.min())])
    j["accessors"][1].update(count=int(len(pos)), max=[float(v) for v in pos.max(axis=0)], min=[float(v) for v in pos.min(axis=0)])
    j["accessors"][2].update(count=int(len(nor)), max=[float(v) for v in nor.max(axis=0)], min=[float(v) for v in nor.min(axis=0)])
    j["bufferViews"][0].update(byteOffset=0, byteLength=len(b_idx))
    j["bufferViews"][1].update(byteOffset=len(b_idx), byteLength=len(b_pos))
    j["bufferViews"][2].update(byteOffset=len(b_idx) + len(b_pos), byteLength=len(b_nor))
    j["buffers"][0]["byteLength"] = len(binary)
    jb = json.dumps(j, separators=(",", ":")).encode()
    while len(jb) % 4:
        jb += b" "
    total = 12 + 8 + len(jb) + 8 + len(binary)
    with open(cesta, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(jb), 0x4E4F534A)); f.write(jb)
        f.write(struct.pack("<II", len(binary), 0x004E4942)); f.write(binary)


def main(vstup, vystup, X1, X2):
    j0, P, N, T = cti(vstup)
    x_min = P[:, 0].min()
    stred0 = (P.min(axis=0) + P.max(axis=0)) / 2.0
    A1, A2 = x_min + X1, x_min + X2
    print("vstup: %d vrcholu, %d trojuhelniku, delka %.3f, otevrenych hran (po slouceni polohou) %s" % (len(P), len(T), P[:, 0].max() - x_min, hrany_otevrene(P, T)))
    s1, s2 = sekce(P, T, A1), sekce(P, T, A2)
    print("prurez v X1=%.1f: %d bodu; v X2=%.1f: %d bodu; shoda: %s" % (X1, len(s1), X2, len(s2), s1 == s2))
    PL, NL, TL = orez(P, N, T, A1, True)
    PR, NR, TR = orez(P, N, T, A2, False)
    PL, NL, TL = kompakt(PL, NL, TL); PR, NR, TR = kompakt(PR, NR, TR)
    d = X2 - X1
    PR = PR.copy(); PR[:, 0] -= d
    # seam vrcholy kazdeho dilu (y, z)
    def seam(Pk):
        m = np.abs(Pk[:, 0] - A1) < 1e-6
        return np.unique(np.round(Pk[m][:, 1:], 6), axis=0)
    sL, sR = seam(PL), seam(PR)
    print("vrcholu na rezu: levy %d, pravy %d" % (len(sL), len(sR)))
    PL, NL, TL, PR, NR, TR = prichyt_a_vloz(PL, NL, TL, PR, NR, TR, A1)
    # sloucit
    Pc = np.vstack([PL, PR]); Nc = np.vstack([NL, NR]); Tc = np.vstack([TL, TR + len(PL)])
    # sloucit vrcholy na rezu (stejna poloha i normala)
    m = np.abs(Pc[:, 0] - A1) < 1e-6
    mapa = np.arange(len(Pc))
    skupiny = {}
    for i in np.where(m)[0]:
        k = tuple(np.round(Pc[i], 5))
        sk = skupiny.setdefault(k, [])
        for r in sk:                                              # normala podobna -> stejny vrchol (tvrda hrana profilu ma normaly ruzne -> zustane rozdelena)
            if float(Nc[i] @ Nc[r]) > 0.9:
                mapa[i] = r
                nn = Nc[r] + Nc[i]; Nc[r] = nn / max(np.linalg.norm(nn), 1e-12)
                break
        else:
            sk.append(i)
    Tc = mapa[Tc]
    Pc, Nc, Tc = kompakt(Pc, Nc, Tc)
    g_ = np.cross(Pc[Tc[:, 1]] - Pc[Tc[:, 0]], Pc[Tc[:, 2]] - Pc[Tc[:, 0]])
    vyradit = (np.linalg.norm(g_, axis=1) / 2.0 < 1e-8) | (Tc[:, 0] == Tc[:, 1]) | (Tc[:, 1] == Tc[:, 2]) | (Tc[:, 0] == Tc[:, 2])
    print("  vyrazeno degenerovanych trojuhelniku (plocha < 1e-8 mm2): %d" % int(vyradit.sum()))
    Tc = Tc[~vyradit]
    Pc, Nc, Tc = kompakt(Pc, Nc, Tc)
    # vycentrovat: stred bboxu stejny jako u vstupu (levy dil +d/2, pravy dil -d/2 vuci rezu): staci posunout cely objekt o +d/2 v x
    Pc[:, 0] += d / 2.0
    stred1 = (Pc.min(axis=0) + Pc.max(axis=0)) / 2.0
    print("stred bboxu: vstup %s | vystup %s | rozdil %s" % (np.round(stred0, 4), np.round(stred1, 4), np.round(stred1 - stred0, 6)))
    print("vystup: %d vrcholu, %d trojuhelniku, delka %.3f, otevrenych hran (po slouceni polohou, >2x pouzitych) %s" % (len(Pc), len(Tc), Pc[:, 0].max() - Pc[:, 0].min(), hrany_otevrene(Pc, Tc)))
    # shoda orientace trojuhelniku s normalami vrcholu
    def shoda(Pk, Nk, Tk):
        g = np.cross(Pk[Tk[:, 1]] - Pk[Tk[:, 0]], Pk[Tk[:, 2]] - Pk[Tk[:, 0]]); nn = Nk[Tk].mean(axis=1)
        return float(np.mean(np.einsum("ij,ij->i", g, nn) > 0))
    print("podil trojuhelniku s orientaci shodnou s normalami: vstup %.4f | vystup %.4f" % (shoda(P, N, T), shoda(Pc, Nc, Tc)))
    zapis_glb(j0, Pc, Nc, Tc, vystup)
    print("zapsano", vystup)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
