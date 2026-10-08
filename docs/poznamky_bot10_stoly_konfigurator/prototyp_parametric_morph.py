#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""
PROTOTYP 2 (bot10, 2026-10-02, jen SELECT): parametrická změna rozměru uložené sestavy "rovinným rozkladem" (plane-warp):
  - rovina na ose a ve světových souřadnicích, díly celé pod rovinou stojí, celé nad rovinou se posunou o delta,
    díly přes rovinu, které jsou natažitelné (profil s podélnou osou || a, deska), se natáhnou (měřítko podél delky) tak,
    že jejich "dolní" hrana zůstane a "horní" se posune o delta; ostatní díly (komponenty) se řadí podle středu / podle
    přepisu (anchors).
Ověřuje na #577 (stůl): invariantnost spojů (stejné DVOJICE profilů i počet), délky profilů +delta, AABB +delta,
žádný nový průnik profil-profil. Výsledek tisknu - NEJDE O HOTOVÝ MODUL.

  python prototyp_parametric_morph.py [--shape 577]
"""
import argparse, json, sys, os, math
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import prototyp_compose_glb as P
import db

AX = {"x": 0, "y": 1, "z": 2}


def part_world_aabb(p, geo):
    M = P.trs4(p["position"], p["quaternion"], p["scale"])
    return P.aabb_of_box_corners(M, geo.bmin, geo.bmax)


def local_axis_for_world(p, a):
    """lokální osa dílu, která leží (po otočení) na světové ose a (rotace po 90 st.)."""
    R = P.quat_to_mat3(p["quaternion"])
    k = int(np.argmax(np.abs(R[a, :])))
    return k if abs(R[a, k]) > 0.9 else None


def morph(parts, cat, axis, plane, delta, anchors=None, eps=0.5):
    a = AX[axis]
    anchors = anchors or {}
    out, report = [], []
    for i, p in enumerate(parts):
        c = cat[p["part_id"]]
        geo = P.catglb(c["glb"])
        mn, mx = part_world_aabb(p, geo)
        q = json.loads(json.dumps(p))
        lo, hi = mn[a], mx[a]
        mode = anchors.get(i)
        k = local_axis_for_world(p, a)
        stretchable = (c["is_profile"] and k is not None and
                       int(np.argmax(geo.bmax - geo.bmin)) == k) or (c["is_board"] and k is not None
                                                                     and (geo.bmax[k] - geo.bmin[k]) > 100)
        if mode is None:
            if hi <= plane + eps:
                mode = "fixed"
            elif lo >= plane - eps:
                mode = "shift"
            elif stretchable:
                mode = "stretch"
            else:                                  # komponent přes rovinu bez přepisu -> FAIL-CLOSED (výběr varianty/SKU je věc receptu)
                raise ValueError("díl %d (%s) leží přes rovinu %s=%.0f a není natažitelný - recept musí určit politiku "
                                 "(fixed/shift/swap SKU)" % (i, c.get("name"), axis, plane))
        if mode == "shift":
            q["position"][a] += delta
        elif mode == "stretch":
            if not stretchable:
                raise ValueError("díl %d nelze natáhnout" % i)
            L = hi - lo
            q["scale"][k] = p["scale"][k] * (L + delta) / L
            mn2, mx2 = part_world_aabb(q, geo)
            q["position"][a] += lo - mn2[a]        # dolní hrana zůstává
        out.append(q)
        report.append((i, mode))
    return out, report


def pair_set(parts, cat):
    n, pairs = P.count_joints(parts, cat, False)
    return n, set(pairs)


def profile_overlaps(parts, cat, tol=0.5):
    """průnik profil-profil > tol mm na všech 3 osách (= nové zanoření)"""
    ents = [(i, P.ProfEntry(i, p, P.catglb(cat[p["part_id"]]["glb"]))) for i, p in enumerate(parts) if cat[p["part_id"]]["is_profile"]]
    bad = []
    for x in range(len(ents)):
        for y in range(x + 1, len(ents)):
            a, b = ents[x][1], ents[y][1]
            ov = [min(a.bmax[k], b.bmax[k]) - max(a.bmin[k], b.bmin[k]) for k in range(3)]
            if all(o > tol for o in ov):
                bad.append((ents[x][0], ents[y][0], np.round(ov, 1).tolist()))
    return bad


def union_aabb(parts, cat):
    mn = np.full(3, np.inf); mx = np.full(3, -np.inf)
    for p in parts:
        lo, hi = part_world_aabb(p, P.catglb(cat[p["part_id"]]["glb"]))
        mn = np.minimum(mn, lo); mx = np.maximum(mx, hi)
    return mn, mx


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--shape", type=int, default=577); a = ap.parse_args()
    c, cur = db.ro()
    cur.execute("SELECT data,name FROM custom_shapes WHERE id=%s", (a.shape,)); r = cur.fetchone()
    parts = json.loads(r["data"])["parts"]
    cat = P.resolve_catalog(cur, {p["part_id"] for p in parts})
    n0, pairs0 = pair_set(parts, cat)
    mn0, mx0 = union_aabb(parts, cat)
    print("základ: %d dílů, %d spojů (geometricky), AABB %s .. %s, průniků profil-profil: %d" % (
        len(parts), n0, np.round(mn0).tolist(), np.round(mx0).tolist(), len(profile_overlaps(parts, cat))))
    # roviny a přepisy pro #577 (stůl 800 x 1200 x 822): šířka X mezi levou a pravou nohou, hloubka Z mezi předními a zadními
    # nohami, výška Y nad kolečky (y 101) a pod spodním rámem (y 315). Zásuvky (díl 20) jsou při šířce kotvené vlevo,
    # (díl 22 elektrožlab a 23/24 perfopanely jsou celé na pravé straně -> posun), LED (21) vlevo.
    cases = [
        ("x", 250.0, [-200, +200, +400], {20: "fixed"}),
        ("y", 200.0, [-100, +150, +300], {}),
        ("z", 400.0, [+300], {}),                       # BEZ politik: musí selhat (komponenty LED/perfopanel/zásuvky přes rovinu)
        ("z", 400.0, [+300, +600], {20: "fixed", 21: "fixed", 23: "fixed", 24: "fixed"}),   # s politikami (komponenty se nemění)
    ]
    allok = True
    for axis, plane, deltas, anchors in cases:
        a_i = AX[axis]
        for d in deltas:
            try:
                q, rep = morph(parts, cat, axis, plane, d, anchors)
            except ValueError as e:
                print("osa %s rovina %.0f delta %+5d: ODMÍTNUTO (fail-closed): %s" % (axis, plane, d, e))
                continue
            n1, pairs1 = pair_set(q, cat)
            ov = profile_overlaps(q, cat)
            mn1, mx1 = union_aabb(q, cat)
            grow = (mx1 - mn1)[a_i] - (mx0 - mn0)[a_i]
            # délky profilů: kolik profilů změnilo délku o presne delta
            changed = 0
            for i, (p0, p1) in enumerate(zip(parts, q)):
                if cat[p0["part_id"]]["is_profile"]:
                    m0, x0 = part_world_aabb(p0, P.catglb(cat[p0["part_id"]]["glb"]))
                    m1, x1 = part_world_aabb(p1, P.catglb(cat[p1["part_id"]]["glb"]))
                    if abs((x1 - m1)[a_i] - (x0 - m0)[a_i] - d) < 1e-3:
                        changed += 1
            notes = [x for x in rep if isinstance(x, str)]
            ok = (pairs1 == pairs0) and not ov and abs(grow - d) < 1e-3
            allok &= ok
            print("osa %s rovina %.0f delta %+5d: spojů %d (stejné dvojice: %s) | AABB roste o %.1f mm | profilů prodlouženo o delta: %d | nové průniky: %d | %s%s" % (
                axis, plane, d, n1, pairs1 == pairs0, grow, changed, len(ov), "OK" if ok else "PROBLÉM",
                ("  [" + "; ".join(notes) + "]") if notes else ""))
            if not ok:
                print("   rozdíl párů:", sorted(pairs0 ^ pairs1)[:10], "průniky:", ov[:4])
    print("VÝSLEDEK:", "všechny varianty zachovaly topologii spojů a bez nových průniků" if allok else "NĚKTERÁ VARIANTA SELHALA")


if __name__ == "__main__":
    main()
