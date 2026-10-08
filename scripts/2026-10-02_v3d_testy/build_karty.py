#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Postavi 7 Vandr karet (Blender na pozadi, CPU, bez GPU) pro testy test_sanitize (TestVandrOut) a test_mark.

Vstup: fixtures/ctx/ctx_<karta>.json (snimek ctx z build_ctx.py - komponenty, kusovnik, pozice, panel materialu),
       katalogove GLB z webapp/katalog (jen cteni), scripts/v3d/pohyby-vychozi.json z repa.
Vystup (MIMO repo, <OUT> = $V3D_TEST_OUT nebo <tmp>/v3d_testy):
       <OUT>/out/<karta>.glb + .json   cisty GLB z buildu + geom.json (spec v3d)
       <OUT>/out2/<karta>.offer.glb    totez po v3d_glb.sanitize (zakaznicky model)
Pouziti: build_karty.py [karta ...]      (bez argumentu vsech 7, ~15 s na kartu); preskoci uz hotove
         s FORCE=1 postavi znovu. Zadna DB, zadny zapis do repa.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import _cesty as CE  # noqa: E402

sys.path.insert(0, os.path.join(CE.REPO, "scripts", "v3d"))
sys.path.insert(0, os.path.join(CE.REPO, "api"))


def ctx_karty(k):
    with open(os.path.join(CE.FIX, "ctx", "ctx_%s.json" % k), encoding="utf-8") as f:
        ctx = json.load(f)
    ctx["glb"] = os.path.join(CE.KATALOG, ctx["glb_file"])
    with open(os.path.join(CE.REPO, "scripts", "v3d", "pohyby-vychozi.json"), encoding="utf-8") as f:
        ctx["pohyby_vychozi"] = json.load(f)
    return ctx


def main(karty):
    if not os.path.exists(CE.BLENDER):
        print("BUILD_KARTY preskoceno: Blender nenalezen (%s)" % CE.BLENDER)
        return 0
    import offer_model
    import v3d_glb
    os.makedirs(os.path.join(CE.OUT, "out"), exist_ok=True)
    os.makedirs(os.path.join(CE.OUT, "out2"), exist_ok=True)
    chyby = 0
    for k in karty:
        a = os.path.join(CE.OUT, "out", k + ".glb")
        b = os.path.join(CE.OUT, "out", k + ".json")
        c = os.path.join(CE.OUT, "out2", k + ".offer.glb")
        if os.environ.get("FORCE") != "1" and all(os.path.exists(x) for x in (a, b, c)):
            print("BUILD_KARTY %s: hotovo (FORCE=1 postavi znovu)" % k)
            continue
        ctx = ctx_karty(k)
        if not os.path.isfile(ctx["glb"]):
            print("BUILD_KARTY %s: chybi katalogove GLB %s - preskoceno" % (k, ctx["glb"]))
            chyby += 1
            continue
        clean, geom = offer_model.spust_build(ctx["glb"], ctx, 55)
        offer = v3d_glb.sanitize(clean, geom["v3d"])
        with open(a, "wb") as f:
            f.write(clean)
        with open(b, "w", encoding="utf-8") as f:
            json.dump(geom, f)
        with open(c, "wb") as f:
            f.write(offer)
        print("BUILD_KARTY %s: %d B -> %d B, pohybu %d" % (k, len(clean), len(offer), len(geom["v3d"].get("motions") or [])))
    return 1 if chyby else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(CE.KARTY)))
