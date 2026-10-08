#!/usr/bin/env python3
"""Test slucovani multiboxu (v3d_merge.sluc_glb) - bot8 2026-10-07. Spusteni: python3 test_merge_mbx.py <cesta_k_api> <slozka_out2_z_build_karty>"""
import os, sys
API, FIX = sys.argv[1], sys.argv[2]
sys.path.insert(0, API)
sys.dont_write_bytecode = True
import v3d_glb, v3d_merge  # noqa: E402
bad = total = 0


def t(name, cond, detail=None):
    global bad, total
    total += 1
    bad += 0 if cond else 1
    print("[%s] %s%s" % ("OK   " if cond else "CHYBA", name, "" if cond or detail is None else " | %r" % (detail,)))


nacti = lambda k: open(os.path.join(FIX, k + ".offer.glb"), "rb").read()
A, B, C = nacti("4918"), nacti("4921"), nacti("4917")
sa, sb, sc = (v3d_glb.embedded_spec(x) for x in (A, B, C))
na, nb, nc = len(sa["mbx"]), len(sb["mbx"]), len(sc["mbx"])

glb, gm = v3d_merge.sluc_glb([A, B], strany=["left", "right"])
sp = v3d_glb.embedded_spec(glb)
ids = [b["id"] for b in sp["mbx"]]
t("2 zdroje: pocet = soucet", len(sp["mbx"]) == na + nb, (len(sp["mbx"]), na, nb))
t("2 zdroje: id unikatni a navazuji", len(set(ids)) == len(ids) and ids[0] == "b01" and ids[na] == "b%02d" % (na + 1), ids[:3] + ids[na - 1:na + 2])
t("2 zdroje: strana g podle zdroje", [b["g"] for b in sp["mbx"]] == ["left"] * na + ["right"] * nb)
t("2 zdroje: n pocita zvlast po stranach", [b["n"] for b in sp["mbx"] if b["g"] == "right"][:3] == [1, 2, 3] and [b["n"] for b in sp["mbx"] if b["g"] == "left"][-1] == na, [b["n"] for b in sp["mbx"]][:3])
piv = {m["steps"][0]["p"] for m in sp["motions"]} | {p for m in sp["motions"] for p in m["pick"]}
t("2 zdroje: kazdy mbx.p je pivot nejakeho pohybu slouceneho modelu", all(b["p"] in piv for b in sp["mbx"]))
pivA = {int(st["p"][1:]) for m in sa["motions"] for st in m["steps"]} | {int(p[1:]) for m in sa["motions"] for p in m["pick"]} | {int(b["p"][1:]) for b in sa["mbx"] if b["p"]}
offA = max(pivA)
t("2 zdroje: pivot kazdeho boxu druheho zdroje = puvodni pivot + posun (nejvyssi pivot prvniho zdroje), stejne jako u pohybu", [int(b["p"][1:]) for b in sp["mbx"][na:]] == [int(b["p"][1:]) + offA for b in sb["mbx"]],
  ([int(b["p"][1:]) for b in sp["mbx"][na:]][:4], [int(b["p"][1:]) + offA for b in sb["mbx"]][:4]))
t("2 zdroje: pivoty druheho zdroje precislovane (p > pivoty prvniho)", int(sp["mbx"][-1]["p"][1:]) > int(sp["mbx"][0]["p"][1:]))
t("2 zdroje: souradnice beze zmeny", sp["mbx"][na]["min"] == sb["mbx"][0]["min"] and sp["mbx"][na]["max"] == sb["mbx"][0]["max"])
ska = {b["s"] for b in sa["mbx"]}; skb = {b["s"] for b in sb["mbx"]}
t("2 zdroje: cisla skupin navazuji (druhy zdroj o pocet skupin prvniho vys), druh sk zachovan", sorted({b["s"] for b in sp["mbx"][na:]}) == sorted(x + len(ska) for x in skb)
  and [b["sk"] for b in sp["mbx"]] == [b["sk"] for b in sa["mbx"]] + [b["sk"] for b in sb["mbx"]], sorted({b["s"] for b in sp["mbx"]}))
t("2 zdroje: e zachovano", [b["e"] for b in sp["mbx"]] == [b["e"] for b in sa["mbx"]] + [b["e"] for b in sb["mbx"]])

# tri zdroje + zdroj bez mbx
glb3, _ = v3d_merge.sluc_glb([A, B, C], strany=["left", "right", "bulkhead"])
s3 = v3d_glb.embedded_spec(glb3)
t("3 zdroje: pocet", len(s3["mbx"]) == na + nb + nc, len(s3["mbx"]))
t("3 zdroje: id unikatni", len({b["id"] for b in s3["mbx"]}) == na + nb + nc)
t("3 zdroje: cisla skupin unikatni mezi zdroji (soucet poctu skupin)", len({b["s"] for b in s3["mbx"]}) == len({b["s"] for b in sa["mbx"]}) + len({b["s"] for b in sb["mbx"]}) + len({b["s"] for b in sc["mbx"]}))
t("3 zdroje: g bulkhead pro treti", all(b["g"] == "bulkhead" for b in s3["mbx"][na + nb:]))
t("3 zdroje: e = -1 z 4917 zustava", sum(1 for b in s3["mbx"][na + nb:] if b["e"] == -1) == sum(1 for b in sc["mbx"] if b["e"] == -1))

# zdroj bez mbx (zmenime spec kopie): slouceni dal funguje a mbx jen z druheho
g1, bn1 = v3d_glb.read_glb(A)
g1["scenes"][0]["extras"]["v3d"].pop("mbx")
A0 = v3d_glb.write_glb(g1, bn1)
glb0, _ = v3d_merge.sluc_glb([A0, B], strany=["left", "right"])
s0 = v3d_glb.embedded_spec(glb0)
t("zdroj bez mbx: jen druhy, id od b01", len(s0["mbx"]) == nb and s0["mbx"][0]["id"] == "b01" and s0["mbx"][0]["g"] == "right", [b["id"] for b in s0["mbx"]][:2])
glbn, _ = v3d_merge.sluc_glb([A0, v3d_glb.write_glb(*(lambda gg, bb: (gg, bb))(*(lambda r: (r[0], r[1]))(v3d_glb.read_glb(A0))))], strany=["left", "right"])
t("oba bez mbx: klic mbx ve spec neni", "mbx" not in v3d_glb.embedded_spec(glbn))

# chyby: mbx.p na neexistujici pivot
g2, bn2 = v3d_glb.read_glb(B)
g2["scenes"][0]["extras"]["v3d"]["mbx"][0]["p"] = "p99"
try:
    v3d_merge.sluc_glb([A, v3d_glb.write_glb(g2, bn2)], strany=["left", "right"])
    t("mbx.p na neexistujici pivot = V3DError", False)
except v3d_glb.V3DError:
    t("mbx.p na neexistujici pivot = V3DError", True)
print("\n%d/%d OK" % (total - bad, total))
sys.exit(1 if bad else 0)
