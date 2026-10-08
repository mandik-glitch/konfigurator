#!/opt/konfigurator/api/venv/bin/python
# -*- coding: utf-8 -*-
"""
Demo (bot10, 2026-10-02, jen SELECT): volby -> placement (plane-warp z prototyp_parametric_morph.py) -> compose_entries()
(BEZ čtení vrcholů GLB - jen hlavičky accessorů) -> export GLB -> kontrola. Ukazuje i čas compose_entries.

  python varianty_demo.py [--shape 577]
"""
import json, os, sys, time, subprocess
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np
import prototyp_compose_glb as P
import prototyp_parametric_morph as M
import db
import struct

# ---------------------------------------------------------------- jen hlavičky GLB (bez vrcholů)
_HDR = {}


def header_bbox(file):
    if file not in _HDR:
        with open(P.KAT + file, "rb") as f:
            h = f.read(20)
            js = json.loads(f.read(struct.unpack_from("<I", h, 12)[0]))
        mn = np.full(3, np.inf); mx = np.full(3, -np.inf)
        for m in js["meshes"]:
            for p in m["primitives"]:
                a = js["accessors"][p["attributes"]["POSITION"]]
                mn = np.minimum(mn, a["min"]); mx = np.maximum(mx, a["max"])
        _HDR[file] = (mn, mx)
    return _HDR[file]


class HdrGeo:                       # náhrada CatGlb pro ProfEntry/ count_joints: jen bmin/bmax
    def __init__(self, file):
        self.bmin, self.bmax = header_bbox(file)


def compose_entries(parts, cat, card_of):
    """-> {entries:[{product_id, length_mm | width_mm+height_mm, joint_count}], joints, errors}.
    Nesahá na vrcholy: jen TRS + hlavičkové bbox katalogových GLB."""
    errors, entries = [], []
    idx_profiles = []
    for i, p in enumerate(parts):
        c = cat[p["part_id"]]
        mn, mx = header_bbox(c["glb"])
        M4 = P.trs4(p["position"], p["quaternion"], p["scale"])
        lo, hi = P.aabb_of_box_corners(M4, mn, mx)
        dims = sorted((hi - lo).tolist())
        e = {"product_id": card_of(p["part_id"], c)}
        if c["is_profile"]:
            e["length_mm"] = round(dims[2], 2)
            idx_profiles.append(i)
        elif c["is_board"]:
            e["width_mm"] = round(dims[1], 2); e["height_mm"] = round(dims[2], 2)
        entries.append(e)
    # spoje: stejný algoritmus jako count_joints, ale nad hlavičkovými bbox
    ents = {i: P.ProfEntry(i, parts[i], HdrGeo(cat[parts[i]["part_id"]]["glb"])) for i in idx_profiles}
    pairs = []
    ks = sorted(ents)
    for x in range(len(ks)):
        for y in range(x + 1, len(ks)):
            a, b = ents[ks[x]], ents[ks[y]]
            if P.touching(a, b) and P.is_real_joint(a, b):
                pairs.append((a.i, b.i))
    for i, j in pairs:                     # držitel = nižší index (jen pro určitost; součet je to, co platí)
        entries[i]["joint_count"] = entries[i].get("joint_count", 0) + 1
    return {"entries": entries, "joints": len(pairs), "errors": errors}


def main():
    c, cur = db.ro()
    cur.execute("SELECT data FROM custom_shapes WHERE id=577")
    parts = json.loads(cur.fetchone()["data"])["parts"]
    cat = P.resolve_catalog(cur, {p["part_id"] for p in parts})
    cur.execute("SELECT id,cfg_dily_id FROM shop_products WHERE cfg_dily_id IS NOT NULL AND active=1 AND is_archived=0")
    cfg2card = {}
    for r in cur.fetchall():
        cfg2card.setdefault(r["cfg_dily_id"], r["id"])

    def card_of(pid, c):
        return int(pid.split("_", 1)[1]) if pid.startswith("product_") else cfg2card.get(pid)

    # ---- základ: compose_entries vs. Node (Box3 po dílech) ----
    t = []
    for _ in range(20):
        t0 = time.perf_counter(); res = compose_entries(parts, cat, card_of); t.append(time.perf_counter() - t0)
    print("compose_entries(základ, 50 dílů): %.1f ms (medián z 20, hlavičky GLB v cache), spojů %d, položek %d" % (
        1000 * float(np.median(t)), res["joints"], len(res["entries"])))
    ref = json.load(open(os.path.join(HERE, "out", "shape577_ref_out.json")))
    bad = 0
    for i, (p, e) in enumerate(zip(parts, res["entries"])):
        rb = ref["boxes"]["per_part"][i]
        dims = sorted((np.array(rb["max"]) - np.array(rb["min"])).tolist())
        if "length_mm" in e and abs(e["length_mm"] - dims[2]) > 0.01: bad += 1
        if "width_mm" in e and (abs(e["width_mm"] - dims[1]) > 0.01 or abs(e["height_mm"] - dims[2]) > 0.01): bad += 1
    print("  rozměry položek (délka profilu, šířka×výška desky) vs. three Box3 scény: nesedí %d z %d" % (bad, len(parts)))
    agg = {}
    for e in res["entries"]:
        k = (e["product_id"], e.get("length_mm"), e.get("width_mm"), e.get("height_mm"))
        agg[k] = agg.get(k, 0) + 1
    print("  souhrn: profil 3457 délky:", sorted((k[1], n) for k, n in agg.items() if k[0] == 3457), "| desky:",
          [(k[0], k[2], k[3], n) for k, n in agg.items() if k[2]])

    # ---- varianty ----
    anchors_x = {20: "fixed"}
    for name, steps in (("x+200", [("x", 250.0, 200, anchors_x)]),
                        ("y+150", [("y", 200.0, 150, {})]),
                        ("x+200_y+150", [("x", 250.0, 200, anchors_x), ("y", 200.0, 150, {})]),
                        ("x-200", [("x", 250.0, -200, anchors_x)])):
        q = parts
        for axis, plane, d, anc in steps:
            q, _ = M.morph(q, cat, axis, plane, d, anc)
        t0 = time.perf_counter(); r = compose_entries(q, cat, card_of); dt = 1000 * (time.perf_counter() - t0)
        out = os.path.join(HERE, "out", "stul577_%s_export.glb" % name)
        slot = lambda p, c, i: 1 if c["is_board"] else (2 if c["is_profile"] else 5)
        exp, ex = P.export_variant(q, cat, slot, out)
        mn, mx = M.union_aabb(q, cat)
        lens = sorted({e["length_mm"] for e in r["entries"] if "length_mm" in e})
        boards = [(e["width_mm"], e["height_mm"]) for e in r["entries"] if "width_mm" in e]
        print("%-12s entries %.1f ms | spojů %d | AABB %s | délky profilů %s | desky %s | export %d B (%.0f+%.0f ms)" % (
            name, dt, r["joints"], np.round(mx - mn).astype(int).tolist(), lens, boards, ex["bytes"], ex["compose_ms"], ex["sanitize_ms"]))


if __name__ == "__main__":
    main()
