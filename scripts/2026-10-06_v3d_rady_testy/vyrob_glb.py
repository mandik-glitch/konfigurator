#!/usr/bin/env python3
"""Testovaci zakaznicke GLB pro test_rady_vyber.js (bot10, 2026-10-06): slouci dva hotove modely (webapp/katalog/vandr/v3d_nahled/<karta>.glb) pres api/v3d_merge.py a doplni motions[].g
(strana spolecne nabidky) + cislovani po stranach, jak to udela server po prijeti g ve validate_spec. Pouziti: vyrob_glb.py <vystupni_slozka>. Varianty: dvoustrane.glb (leva + prava),
trojstrane.glb (leva + prava + prepazka), bez_g.glb (bez g = dosavadni jedna rada), spatne_g.glb (g = 'nahoru' / 5 = ignoruje se)."""
import copy, os, sys
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "api"))
sys.dont_write_bytecode = True
import v3d_glb, v3d_merge  # noqa: E402

ND = os.path.join(REPO, "webapp", "katalog", "vandr", "v3d_nahled")
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
nacti = lambda k: open(os.path.join(ND, k + ".glb"), "rb").read()


def s_g(glb, strany, po_stranach=True):
    """glb + seznam stran pro po sobe jdouci bloky pohybu (delky z puvodnich modelu)."""
    g, bn = v3d_glb.read_glb(glb)
    spec = g["scenes"][0]["extras"]["v3d"]
    i = 0
    for strana, pocet in strany:
        for m in spec["motions"][i:i + pocet]:
            if strana is not None:
                m["g"] = strana
        i += pocet
    if po_stranach:
        cnt = {}
        for m in spec["motions"]:
            key = (m.get("g"), m["k"], m.get("sub"))
            cnt[key] = cnt.get(key, 0) + 1
            m["n"] = cnt[key]
    return v3d_glb.write_glb(g, bn)


def bez_g(glb):
    """Odstrani g ze vsech pohybu (sluc_glb bez parametru strany ho totiz odhadne z front a polohy boxu)."""
    g, bn = v3d_glb.read_glb(glb)
    for m in g["scenes"][0]["extras"]["v3d"]["motions"]:
        m.pop("g", None)
    return v3d_glb.write_glb(g, bn)


def pocet(glb):
    return len(v3d_glb.embedded_spec(glb)["motions"])


A, B, C = nacti("4918"), nacti("4921"), nacti("4594")
nA, nB, nC = pocet(A), pocet(B), pocet(C)
m2, _ = v3d_merge.sluc_glb([A, B])
m3, _ = v3d_merge.sluc_glb([A, B, C])
open(os.path.join(out, "dvoustrane.glb"), "wb").write(s_g(m2, [("left", nA), ("right", nB)]))
open(os.path.join(out, "trojstrane.glb"), "wb").write(s_g(m3, [("left", nA), ("right", nB), ("bulkhead", nC)]))
open(os.path.join(out, "bez_g.glb"), "wb").write(bez_g(m2))
open(os.path.join(out, "spatne_g.glb"), "wb").write(s_g(m2, [("nahoru", nA), (5, nB)], po_stranach=False))
print("pocty pohybu:", nA, nB, nC)
