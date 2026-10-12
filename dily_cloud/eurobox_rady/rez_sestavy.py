"""Boční řezy sestavou (rovina napříč středem jedné dráhy) v rámu řady: ucho dráhy v kapse koncovky, trubka v háku,
box na válečcích. Vyžaduje matplotlib (jen vývojový nástroj).  Spuštění: python3 -I rez_sestavy.py [draha]
Výstup: obr_dolni_konec_<draha>.png, obr_horni_konec_<draha>.png (osy: s podél sklonu, h kolmo na rovinu válečků)."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eurobox_rady as E  # noqa: E402
import test_eurobox_rady as T  # noqa: E402


def rez(tris, osa, hodnota):
    """Úsečky průniku trojúhelníků s rovinou souřadnice `osa` = `hodnota` (vektorově)."""
    d = tris[:, :, osa] - hodnota
    out = []
    for i in range(3):
        j = (i + 1) % 3
        m = (d[:, i] < 0) != (d[:, j] < 0)
        if m.any():
            s = d[m, i] / (d[m, i] - d[m, j])
            out.append((m, tris[m, i] + s[:, None] * (tris[m, j] - tris[m, i]), i))
    seg = []
    # každý trojúhelník, který rovinu protíná, dává přesně dva body
    idx = {}
    for m, pts, i in out:
        for n, p in zip(np.nonzero(m)[0], pts):
            idx.setdefault(n, []).append(p)
    for n, ps in idx.items():
        if len(ps) == 2:
            seg.append(ps)
    return np.array(seg)


def kresli(draha="5276", odsaz=0.0, vystup=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    v = E.postav({"rady": [{"id": "R", "typ": "400x300", "vyska": 170, "smer": "delka", "pocet": 2, "x": 0, "y": 500, "z": 0}],
                  "sklon_deg": 8, "draha": draha, "odsazeni_koncovky_mm": odsaz})
    S, (o, U) = T.sestava_mesh(v)
    r = v["rady"][0]
    t0 = v["draha"][0]["pasy"][0]["t"]
    osa = 2 if r["osa_rady"] == "x" else 0
    barvy = {"modul": "#555", "koncovka": "#c0552e", "trubka": "#889", "box": "#25c"}
    # nahoře krajní koncovky jsou rotované; kreslíme levou dráhu (index 1)
    fig, ax_ = plt.subplots(2, 1, figsize=(12, 9))
    for a, (nazev, s_od, s_do) in zip(ax_, (("dolní konec (5282, zarážka)", -90, 330), ("horní konec (5281)", None, None))):
        parts = []
        for pas, j, mt, m in S["moduly"]:
            if pas == 1:
                parts.append(("modul", mt))
        for role, pas, kt, k in S["koncovky"]:
            if pas == 1 and ((role == "dolni") == (nazev.startswith("dolní"))):
                parts.append(("koncovka", kt))
        for role, tt, n in S["trubky"]:
            if (role == "dolni") == nazev.startswith("dolní"):
                parts.append(("trubka", tt))
        for b in S["boxy"]:
            parts.append(("box", b))
        for typ, t in parts:
            seg = rez(t, osa, o[osa] + t0)
            if len(seg) == 0:
                continue
            for s in seg:
                p = (s - o) @ U.T
                a.plot([p[0][0], p[1][0]], [p[0][2], p[1][2]], "-", color=barvy[typ], lw=0.7)
        sb = v["draha"][0]["telo_od_do_mm"]
        if s_od is None:
            s_od, s_do = sb[1] - 250, sb[1] + 150
        a.set_xlim(s_od, s_do)
        a.set_ylim(-70, 90) if nazev.startswith("dolní") else a.set_ylim(-70, 90)
        a.set_aspect("equal")
        a.grid(True, lw=0.3)
        a.axhline(0, color="#25c", lw=0.5, ls="--")
        a.set_title("%s, dráha %s, odsazení %.0f mm: rovina válečků h = 0 (čárkovaně); s = 0 je líc zarážky" % (nazev, draha, odsaz))
    fig.tight_layout()
    vystup = vystup or os.path.join(HERE, "obr_rez_konce_%s.png" % draha)
    fig.savefig(vystup, dpi=100)
    print(vystup)


if __name__ == "__main__":
    kresli(sys.argv[1] if len(sys.argv) > 1 else "5276")
