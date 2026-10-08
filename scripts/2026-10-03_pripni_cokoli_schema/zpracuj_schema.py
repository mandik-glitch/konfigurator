#!/opt/konfigurator/api/venv/bin/python
"""Schemata profilu pro stranku "Pripni cokoli" (bot10, 2026-10-03; Robert: "schema profilu 30x30 s drazkou 8 mm, aby bylo jasne ze to plati i pro jine profily",
"nemusi to byt 3D, jen doplneni informaci").

Zdroj: dodavatelske vykresy ulozene v galerii produktu (3457 = 30x30 Light, 3468 = 40x40 SuperLight S10; soubor 2.jpg, 400x360 px). Siluetu pruřezu
(tmave sede pixely, bez cervenych koty a cisel) prevede na ostry vektor (marching squares nad 4x zvetsenym polem + Douglas-Peucker + hladke krivky) a
rozmery nakresli znovu (cisla jsou jazykove neutralni). Vystup: webapp/pripni-cokoli/schema-<profil>.svg (tmave pozadi stranky, svetly profil, oranzova kota drazky).
Pouze numpy + Pillow (v api venv). Spusteni: api/venv/bin/python -B scripts/2026-10-03_pripni_cokoli_schema/zpracuj_schema.py [--nahled DIR]
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAL = os.path.join(REPO, "webapp", "content-files", "gallery", "products")
OUT = os.path.join(REPO, "webapp", "pripni-cokoli")
UP = 4          # zvetseni pole pred hledanim vrstevnice (subpixelove hladke okraje)
SIGMA = 0.85    # rozmazani v px puvodniho vykresu (potlaceni sumu JPEG)

PROFILY = [
    # klic, produkt, soubor, rozmer profilu (mm), drazka (mm), popisek rozmeru
    dict(key="40x40-d10", pid=3468, soubor="2.jpg", strana=40.0, drazka=10.2),
    dict(key="30x30-d8", pid=3457, soubor="2.jpg", strana=30.0, drazka=8.2),
]


def pole(img):
    """Pole 'tmavosti' 0..1 pro profil (svetle seda vypln + tmavy obrys); bile pozadi = 0. Cervene koty a cisla se doplni podle okoli
    (jinak by pres profil vedly rezy po cervenych carach). Zvetsene UP-krat."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    valid = ~((r - np.maximum(g, b)) > 28)                    # cervene (R >> G,B) = kota nebo cislo
    lum = np.where(valid, lum, 255.0)
    for _ in range(10):                                       # zalepit cervene pixely prumerem platnych sousedu
        if valid.all(): break
        acc = np.zeros_like(lum); cnt = np.zeros_like(lum)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0: continue
                v = np.roll(np.roll(valid, dy, axis=0), dx, axis=1)
                l = np.roll(np.roll(lum, dy, axis=0), dx, axis=1)
                acc += np.where(v, l, 0.0); cnt += v
        fill = (~valid) & (cnt > 0)
        lum = np.where(fill, acc / np.maximum(cnt, 1), lum)
        valid = valid | fill
    dark = np.clip((210.0 - lum) / 22.0, 0, 1)                # vypln ~160-200 = plne uvnitr, bila 255 = venku
    im = Image.fromarray((dark * 255).astype(np.uint8))
    im = im.resize((im.width * UP, im.height * UP), Image.BICUBIC)
    f = np.asarray(im, dtype=np.float32) / 255.0
    return blur(f, SIGMA * UP)


def blur(f, sigma):
    """Separabilni gaussovo rozmazani (jen numpy): potlaci sum JPEG a zvlneni okraju pred hledanim vrstevnice."""
    n = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-n, n + 1) / sigma) ** 2); k /= k.sum()
    for ax in (0, 1):
        out = np.zeros_like(f)
        for i, w in enumerate(k):
            out += w * np.roll(f, i - n, axis=ax)
        f = out
    return f


def symetrizuj(f, stred):
    """Profil je souměrny (otoceni o 90 st. + zrcadleni): pole se zprumeruje pres vsech 8 symetrii kolem stredu obrysu. Stopy cervenych kot a sum JPEG
    jsou v kazde symetrii jinde, takze se zrusi; obrys je cisty a presne souměrny. Vraci (pole, (ox, oy)) - posun vyrezu vuci puvodnimu poli."""
    cx, cy, rad = stred                                        # stred a polovicni velikost obrysu v indexech pole (z velkych smycek, ne z drobku)
    h = int(rad) + 12
    pad = np.pad(f, h + 1)                                   # bile okraje (0) nasledne orezat
    g = pad[cy + 1:cy + 2 * h + 2, cx + 1:cx + 2 * h + 2]    # ctverec (2h+1)^2 se stredem presne v (h,h)
    g = (g + np.rot90(g, 1) + np.rot90(g, 2) + np.rot90(g, 3)) / 4.0
    g = (g + g[:, ::-1]) / 2.0
    return g, (cx - h, cy - h)


def marching(f, t=0.5):
    """Marching squares nad polem f -> uzavrene smycky [(x,y)...] (souradnice pole)."""
    h, w = f.shape
    b = f >= t
    c = (b[:-1, :-1].astype(np.uint8) << 3) | (b[:-1, 1:].astype(np.uint8) << 2) | (b[1:, 1:].astype(np.uint8) << 1) | b[1:, :-1].astype(np.uint8)
    ys, xs = np.nonzero((c != 0) & (c != 15))

    def ip(p0, p1, v0, v1):
        d = (t - v0) / (v1 - v0) if v1 != v0 else 0.5
        return (p0[0] + (p1[0] - p0[0]) * d, p0[1] + (p1[1] - p0[1]) * d)

    segs = {}
    adj = {}
    def add(k1, p1, k2, p2):
        adj.setdefault(k1, []).append(k2); adj.setdefault(k2, []).append(k1)
        segs[k1] = p1; segs[k2] = p2
    # hrany: 0 = horni, 1 = prava, 2 = dolni, 3 = leva; klic hrany je (typ, x, y)
    TABLE = {1: [(3, 2)], 2: [(2, 1)], 3: [(3, 1)], 4: [(0, 1)], 5: [(0, 3), (2, 1)], 6: [(0, 2)], 7: [(0, 3)],
             8: [(0, 3)], 9: [(0, 2)], 10: [(0, 1), (3, 2)], 11: [(0, 1)], 12: [(3, 1)], 13: [(2, 1)], 14: [(3, 2)]}
    for y, x in zip(ys.tolist(), xs.tolist()):
        v = (f[y, x], f[y, x + 1], f[y + 1, x + 1], f[y + 1, x])      # TL, TR, BR, BL
        P = ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1))

        def edge(e):
            if e == 0: return (("h", x, y), ip(P[0], P[1], v[0], v[1]))
            if e == 1: return (("v", x + 1, y), ip(P[1], P[2], v[1], v[2]))
            if e == 2: return (("h", x, y + 1), ip(P[3], P[2], v[3], v[2]))
            return (("v", x, y), ip(P[0], P[3], v[0], v[3]))
        for e1, e2 in TABLE[int(c[y, x])]:
            (k1, p1), (k2, p2) = edge(e1), edge(e2)
            add(k1, p1, k2, p2)
    seen = set(); loops = []
    for k0 in list(adj):
        if k0 in seen: continue
        loop = [k0]; seen.add(k0); prev = None; cur = k0
        while True:
            nxt = None
            for kn in adj[cur]:
                if kn != prev and kn not in seen:
                    nxt = kn; break
            if nxt is None: break
            loop.append(nxt); seen.add(nxt); prev, cur = cur, nxt
        if len(loop) > 8:
            loops.append([segs[k] for k in loop])
    return loops


def area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = np.array(pts[0]), np.array(pts[-1]); ab = b - a; n = np.hypot(*ab)
    def cross2(u, v): return u[0] * v[1] - u[1] * v[0]
    d = [abs(cross2(ab, np.array(p) - a)) / n if n > 1e-9 else np.hypot(*(np.array(p) - a)) for p in pts[1:-1]]
    i = int(np.argmax(d)) + 1
    if d[i - 1] > eps:
        return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]


def rdp_closed(pts, eps):
    # rozdelit smycku v nejvzdalenejsich bodech, aby se nezkreslil start
    n = len(pts); i0 = 0
    j = max(range(n), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
    a = rdp(pts[:j + 1], eps); b = rdp(pts[j:] + [pts[0]], eps)
    return a[:-1] + b[:-1]


def srovnej(pts, tol=2.2):
    """Skoro vodorovne/svisle hrany (odchylka < tol jednotek = 0,22 mm) se srovnaji na presne; sikme (45 st.) a oblouky zustavaji."""
    pts = [list(q) for q in pts]; n = len(pts)
    for _ in range(3):
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            if abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) > 4 * tol:
                m = (a[0] + b[0]) / 2; a[0] = b[0] = m
            elif abs(a[1] - b[1]) < tol and abs(a[0] - b[0]) > 4 * tol:
                m = (a[1] + b[1]) / 2; a[1] = b[1] = m
    return [tuple(q) for q in pts]


def smooth_path(pts, r=0.35):
    """Polygon -> SVG cesta: rohy zaoblene kvadratickymi krivkami (r = podil delky hrany), hladsi nez ostry polygon z trasovani."""
    n = len(pts); d = []
    for i in range(n):
        p0 = np.array(pts[i - 1]); p1 = np.array(pts[i]); p2 = np.array(pts[(i + 1) % n])
        a = p1 + (p0 - p1) * min(r, 3.0 / max(np.hypot(*(p0 - p1)), 1e-6)); b = p1 + (p2 - p1) * min(r, 3.0 / max(np.hypot(*(p2 - p1)), 1e-6))
        d.append(("M%.2f %.2f" if i == 0 else "L%.2f %.2f") % tuple(a))
        d.append("Q%.2f %.2f %.2f %.2f" % (p1[0], p1[1], b[0], b[1]))
    return "".join(d) + "Z"


def zpracuj(p, nahled=None):
    src = os.path.join(GAL, str(p["pid"]), p["soubor"])
    img = Image.open(src)
    f = pole(img)
    l0 = [l for l in marching(f) if abs(area(l)) > 10 * UP * UP]      # 1. pruchod: jen na zjisteni stredu obrysu
    xs0 = [q[0] for l in l0 for q in l]; ys0 = [q[1] for l in l0 for q in l]
    stred = (int(round((min(xs0) + max(xs0)) / 2)), int(round((min(ys0) + max(ys0)) / 2)), max(max(xs0) - min(xs0), max(ys0) - min(ys0)) / 2)
    f, (ox, oy) = symetrizuj(f, stred)
    loops = [l for l in marching(f) if abs(area(l)) > 10 * UP * UP]       # zahodit drobky (text, sipky)
    loops = [[((x + ox) / UP, (y + oy) / UP) for x, y in l] for l in loops]
    loops.sort(key=lambda l: -abs(area(l)))
    xs = [q[0] for l in loops for q in l]; ys = [q[1] for l in loops for q in l]      # obrys = vsechny kusy pruřezu dohromady
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = ((x1 - x0) + (y1 - y0)) / 2 / p["strana"]            # px na mm
    paths = [smooth_path(rdp_closed(l, 0.30)) for l in loops]
    return dict(loops=loops, paths=paths, bbox=(x0, y0, x1, y1), sc=sc, size=img.size)


def svg(p, d):
    x0, y0, x1, y1 = d["bbox"]; sc = d["sc"]
    pad = 26 * 1.0
    # sloupec 'mm' -> jednotky SVG: 1 mm = 10 jednotek
    K = 10.0 / sc
    def T(q): return ((q[0] - x0) * K, (q[1] - y0) * K)
    W = p["strana"] * 10; H = W
    WMAX = 400.0                                  # oba profily ve stejnem platne a meritku (30x30 je proti 40x40 mensi), cisla stejne velka
    ox = (WMAX - W) / 2; oy = (WMAX - H) / 2
    # cesty: vsechny smycky v jedne ceste, evenodd (dutiny jsou diry)
    segs = []
    for l in d["loops"]:
        pts = [T(q) for q in l]
        from_path = smooth_path(srovnej(rdp_closed(pts, 0.30 * K)))
        segs.append(from_path)
    path = "".join(segs)
    vb = (-60, -62, WMAX + 120, WMAX + 124)
    # kota drazky: dole uprostred, sirka p.drazka mm
    cx = W / 2; gap = p["drazka"] * 10
    ya = H + 30
    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" role="img" aria-label="Profil %s, drazka %s mm">' % (vb[0], vb[1], vb[2], vb[3], p["key"].split("-")[0].replace("x", "x"), str(p["drazka"]).replace(".", ",")))
    o.append('<style>.p{fill:#d3dde6;fill-rule:evenodd}.d{stroke:#ff7a3d;stroke-width:1.6;fill:none}.s{stroke:#9fb0c0;stroke-width:1.2;fill:none}.t{font:600 24px -apple-system,Segoe UI,Roboto,Arial,sans-serif;fill:#e8eff6;text-anchor:middle}.h{font:700 26px -apple-system,Segoe UI,Roboto,Arial,sans-serif;fill:#ff7a3d;text-anchor:middle}.a{fill:#ff7a3d}.g{fill:#9fb0c0}</style>')
    o.append('<g transform="translate(%g %g)">' % (ox, oy))
    o.append('<path class="p" d="%s"/>' % path)
    # celkova sirka nahore
    yt = -26
    o.append('<line class="s" x1="0" y1="%g" x2="0" y2="-4"/><line class="s" x1="%g" y1="%g" x2="%g" y2="-4"/>' % (yt - 6, W, yt - 6, W))
    o.append('<line class="s" x1="0" y1="%g" x2="%g" y2="%g"/>' % (yt, W, yt))
    o.append('<path class="g" d="M0 %g l9 -4 v8 z M%g %g l-9 -4 v8 z"/>' % (yt, W, yt))
    o.append('<text class="t" x="%g" y="%g">%s</text>' % (W / 2, yt - 8, ("%g" % p["strana"])))
    # kota drazky dole (oranzova, zvyraznena)
    o.append('<line class="d" x1="%g" y1="%g" x2="%g" y2="%g"/><line class="d" x1="%g" y1="%g" x2="%g" y2="%g"/>' % (cx - gap / 2, H + 2, cx - gap / 2, ya + 8, cx + gap / 2, H + 2, cx + gap / 2, ya + 8))
    o.append('<line class="d" x1="%g" y1="%g" x2="%g" y2="%g"/>' % (cx - gap / 2 - 18, ya, cx + gap / 2 + 18, ya))
    o.append('<path class="a" d="M%g %g l-10 -4.5 v9 z M%g %g l10 -4.5 v9 z"/>' % (cx - gap / 2, ya, cx + gap / 2, ya))
    o.append('<text class="h" x="%g" y="%g">%s</text>' % (cx, ya + 30, str(p["drazka"]).replace(".", ",")))
    o.append('</g></svg>')
    return "".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nahled", default=None, help="adresar pro kontrolni PNG (jen pro vlastni kontrolu)")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for p in PROFILY:
        d = zpracuj(p)
        s = svg(p, d)
        fn = os.path.join(OUT, "schema-%s.svg" % p["key"])
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(s)
        x0, y0, x1, y1 = d["bbox"]
        print("%s: smycek %d, bbox %.1fx%.1f px, %.2f px/mm, svg %d B" % (p["key"], len(d["loops"]), x1 - x0, y1 - y0, d["sc"], len(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
