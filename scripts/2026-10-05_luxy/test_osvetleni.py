#!/usr/bin/env python3
"""Test dat pro POCITADLO LUXU (api/stul_osvetleni.py; bot10, 2026-10-05). Bez DB a bez site: generator + skladac GLB.

  api/venv/bin/python3 scripts/2026-10-05_luxy/test_osvetleni.py

NEZAVISLE MERENI na skutecnem GLB (to, co vidi prohlizec), ne na vnitrnostech generatoru: payload `vodici.osvetleni` musi lezet na vrcholech modelu.
- obalka kazde LED (`housingBoundsMm`) = AABB vrcholu dilu LED v GLB (rozsahy dilu z `_ROZSAHY_CACHE`), svitici cara je vystredena u spodni plochy telesa,
- pracovni rovina: pocatek / rozmery = horni plocha desky (vrcholy s normalou nahoru) v GLB, vyrezy `excludeRects` = PRESNE diry v horni plose (nahodne body: pokryti
  trojuhelniky desky <=> mimo vyrez; tim se hlida i orientace os u / v),
- payload je JSON, projde Johnovym `LuxCore.calculate` (node) pro oba stupne svitidla; pomer prumeru 33 W / 21 W = 3960 / 2600 (stejna geometrie, jen tok),
- bez LED zadne `osvetleni`; vypocet je rychly."""
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "api"))
import stul_konfigurator as S
import stul_glb as G
import stul_osvetleni as O

bad = total = 0


def t(name, cond, detail=None):
    global bad, total
    total += 1
    if not cond:
        bad += 1
    print("[%s] %s%s" % ("OK   " if cond else "CHYBA", name, "" if cond or detail is None else " | %s" % (json.dumps(detail, default=str)[:300],)))


def cti_glb(data):
    jl, _ = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + jl])
    bl = struct.unpack_from("<I", data, 20 + jl)[0]
    return js, data[20 + jl + 8:20 + jl + 8 + bl]


def acc(js, blob, idx):
    a = js["accessors"][idx]
    v = js["bufferViews"][a["bufferView"]]
    n = {"VEC3": 3, "SCALAR": 1}[a["type"]]
    dt = {5126: "<f4", 5125: "<u4", 5123: "<u2"}[a["componentType"]]
    return np.frombuffer(blob, dtype=dt, count=a["count"] * n, offset=v.get("byteOffset", 0) + a.get("byteOffset", 0)).reshape(-1, n) if n > 1 else \
        np.frombuffer(blob, dtype=dt, count=a["count"], offset=v.get("byteOffset", 0) + a.get("byteOffset", 0))


def uzel_mesh(js, blob, uzel):
    pr = js["meshes"][js["nodes"][uzel]["mesh"]]["primitives"][0]
    return acc(js, blob, pr["attributes"]["POSITION"]).astype(float), acc(js, blob, pr["attributes"]["NORMAL"]).astype(float), acc(js, blob, pr["indices"]).reshape(-1, 3)


def pripad(**kw):
    p = dict(kw)
    return p


PRIPADY = [
    ("vychozi stul 30", dict(system=30)),
    ("Johnovy zdrojove parametry (1200 x 800, rameno 560)", dict(system=30, sirka=1200, hloubka=800, vyska=840, led_rameno=560)),
    ("2600 siroky: 2 LED + vyrez 1", dict(system=30, sirka=2600, vyrez1=True)),
    ("3000 x 1500 + 3 vyrezy", dict(system=30, sirka=3000, hloubka=1500, vyrez1=True, vyrez2=True, vyrez3=True)),
    ("rameno LED 1500, vyska 1200", dict(system=30, led_rameno=1500, vyska=1200)),
    ("nizky stul 400, rameno 200", dict(system=30, vyska=400, led_rameno=200)),
    ("system 35 (navlek)", dict(system=35, sirka=1800, vyrez1=True)),
    ("system 40", dict(system=40, sirka=2000, hloubka=900, vyrez2=True)),
    ("vyrez az k okraji desky", dict(system=30, vyrez1=True, vyrez1_x=0, vyrez1_z=0)),
]


def zmer(p):
    """(payload, h, js, blob, r) pro parametry p: payload z `vodici` (hotova odpoved), GLB z model_pro_parametry."""
    r = S.sestav_stul(**p)
    r["ovladani_scena"] = S.ovladani_3d(r)
    vod = G.vodici(r["parametry"], r)
    h, data = G.model_pro_parametry(r["parametry"])
    js, blob = cti_glb(data)
    return (vod or {}).get("osvetleni"), vod, h, js, blob, r


def bodu_v_trojuhelniku(P, Q, A, B, C):
    """Pokryti bodu P (n,2) trojuhelniky (m,3,2): bool pole (n)."""
    v0, v1 = C - A, B - A
    out = np.zeros(len(P), bool)
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1)
    den = d00 * d11 - d01 * d01
    ok = np.abs(den) > 1e-9
    for i in range(len(P)):
        v2 = P[i] - A
        d02 = (v0 * v2).sum(1); d12 = (v1 * v2).sum(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            u = (d11 * d02 - d01 * d12) / den
            v = (d00 * d12 - d01 * d02) / den
        out[i] = bool(np.any(ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)))
    return out


payloady = {}
for popis, p in PRIPADY:
    print("\n## %s" % popis)
    t0 = time.time()
    o, vod, h, js, blob, r = zmer(p)
    t("vodici nese osvetleni", o is not None and "osvetleni" in vod)
    if o is None:
        continue
    payloady[popis] = o
    json.dumps(o)                                              # numpy typy by tady spadly
    txt_o = json.dumps(o, ensure_ascii=False)
    spatne = [z for z in (r"#\d", r"product_", r"Object_", r"\bSKU\b", r"\bsku\b", r"\b(4930|4931|4929|4932|4928|4916|4933|3158)\b", r"[Vv]andr", r"katalog", r"dily", r"quaternion", r'"position"') if re.search(z, txt_o)]
    t("payload nenese technicke udaje zakazane ve verejne odpovedi (SKU, cisla produktu, interni nazvy; test_stul_shop.py ZAKAZANE)", not spatne, spatne)
    t("payload je cisty JSON (zadne numpy typy), verze 1, jednotky mm", json.loads(json.dumps(o)) == o and o["version"] == 1 and o["units"] == "mm")
    ranges = G._ROZSAHY_CACHE[h]
    led_idx = [i for i, d in enumerate(r["dily"]) if d["part_id"] == O.LED_PART]
    t("pocet svitidel v payloadu = pocet dilu LED", len(o["lights"]) == len(led_idx) >= 1, [len(o["lights"]), len(led_idx)])
    # --- LED: obalka z vrcholu GLB
    obalky = []
    for i in led_idx:
        uzel, od, pocet = ranges[i]
        P, _, _ = uzel_mesh(js, blob, uzel)
        P = P[od:od + pocet]
        obalky.append((P.min(axis=0), P.max(axis=0)))
    obalky.sort(key=lambda b: (b[0][2] + b[1][2], b[0][0]))
    shoda = all(np.allclose(l["housingBoundsMm"][0], b[0], atol=0.01) and np.allclose(l["housingBoundsMm"][1], b[1], atol=0.01) for l, b in zip(o["lights"], obalky))
    t("obalka kazde LED = AABB jejich vrcholu v GLB (+-0,01 mm)", shoda, [(l["housingBoundsMm"], [b[0].tolist(), b[1].tolist()]) for l, b in zip(o["lights"], obalky)][:1])
    ok_cara = True
    for l in o["lights"]:
        a, b = np.array(l["housingBoundsMm"][0]), np.array(l["housingBoundsMm"][1])
        c = (a + b) / 2
        s_, e_ = np.array(l["startMm"]), np.array(l["endMm"])
        ok_cara &= bool(np.allclose(s_[[0, 1]], [c[0], a[1]], atol=0.002) and np.allclose(e_[[0, 1]], [c[0], a[1]], atol=0.002) and abs(e_[2] - s_[2] - 1200.0) < 0.002
                        and abs((s_[2] + e_[2]) / 2 - c[2]) < 0.002 and l["direction"] == [0, -1, 0] and l["typ"] == "led_1200" and "sku" not in l and "productId" not in l
                        and l["type"] == "linear" and l["geometryStatus"] == "hypothesis" and l["housingLengthMm"] == 1247.0 and l["nominalLengthMm"] == 1200.0)
    t("svitici cara 1200 mm vystredena u spodni plochy telesa, smer dolu, typ led_1200 (bez sku / productId) / hypoteza", ok_cara, o["lights"][0])
    t("id unikatni a po sirce stolu zleva doprava", [l["id"] for l in o["lights"]] == ["led-%d" % k for k in range(1, len(o["lights"]) + 1)]
      and all(o["lights"][k]["startMm"][2] < o["lights"][k + 1]["startMm"][2] for k in range(len(o["lights"]) - 1)))
    # --- pracovni rovina: horni plocha desky z vrcholu GLB (normala nahoru, nejvyssi y)
    wp = o["workplane"]
    horni = []                                                # trojuhelniky horni plochy pracovni desky (vsechny vrcholy na y = origin.y, normala nahoru)
    y_top = wp["originMm"][1]
    for uzel in range(len(js["nodes"])):
        if "mesh" not in js["nodes"][uzel]:
            continue
        P, N, T = uzel_mesh(js, blob, uzel)
        mask = (np.abs(P[:, 1] - y_top) < 0.01) & (N[:, 1] > 0.99)
        sel = mask[T].all(axis=1)
        if sel.any():
            horni.append(P[T[sel]])
    tri = np.vstack(horni) if horni else np.zeros((0, 3, 3))
    t("v GLB je horni plocha desky ve vysce originMm.y (trojuhelniky s normalou nahoru)", len(tri) > 0, y_top)
    if len(tri) == 0:
        continue
    xs, zs = tri[:, :, 0], tri[:, :, 2]
    plot = [i for i, d in enumerate(r["dily"]) if d["part_id"] == "product_4933" and str(d.get("deska_id") or "").startswith("prac_")]
    if plot and all(ranges[i] is not None for i in plot):
        # nerozdelena deska = katalogovy dil se srazenymi hranami: obalka (to, co meril John) z VSECH vrcholu dilu; ploche horni plose je o par mm mensi
        V_ = np.vstack([uzel_mesh(js, blob, ranges[i][0])[0][ranges[i][1]:ranges[i][1] + ranges[i][2]] for i in plot])
        t("pocatek / rozmery = obalka vrcholu pracovni desky v GLB (+-0,01 mm); horni plocha je uvnitr a nejvyse 6 mm od okraju (srazeni hran)",
          np.allclose([V_[:, 0].min(), V_[:, 1].max(), V_[:, 2].min()], wp["originMm"], atol=0.01) and abs((V_[:, 2].max() - V_[:, 2].min()) - wp["widthMm"]) < 0.01
          and abs((V_[:, 0].max() - V_[:, 0].min()) - wp["depthMm"]) < 0.01
          and 0 <= xs.min() - wp["originMm"][0] <= 6 and 0 <= zs.min() - wp["originMm"][2] <= 6 and 0 <= wp["originMm"][0] + wp["depthMm"] - xs.max() <= 6 and 0 <= wp["originMm"][2] + wp["widthMm"] - zs.max() <= 6,
          [V_.min(axis=0).tolist(), V_.max(axis=0).tolist(), wp["originMm"], wp["widthMm"], wp["depthMm"]])
    else:
        # rozdelena deska = ploche kusy (_deska_s_otvory): horni plocha je PRESNE pracovni rovina
        t("pocatek (x, z) = minimum horni plochy v GLB; rozmery = jeji sirka (z) a hloubka (x) (+-0,01 mm)",
          abs(xs.min() - wp["originMm"][0]) < 0.01 and abs(zs.min() - wp["originMm"][2]) < 0.01 and abs((zs.max() - zs.min()) - wp["widthMm"]) < 0.01 and abs((xs.max() - xs.min()) - wp["depthMm"]) < 0.01,
          [xs.min(), wp["originMm"], zs.max() - zs.min(), wp["widthMm"], xs.max() - xs.min(), wp["depthMm"]])
    t("osy: sirka po z (axisU), hloubka po x (axisV), normala nahoru", wp["axisU"] == [0, 0, 1] and wp["axisV"] == [1, 0, 0] and wp["normal"] == [0, 1, 0])
    # --- vyrezy = diry v horni plose
    rng = np.random.default_rng(7)
    U = rng.uniform(0, wp["widthMm"], 500)
    V = rng.uniform(0, wp["depthMm"], 500)
    rects = wp["excludeRects"]
    uvnitr = np.zeros(len(U), bool)
    blizko = np.zeros(len(U), bool)                           # body u hrany vyrezu se nehodnoti (tolerance 1 mm)
    for (u0, v0, u1, v1) in rects:
        uvnitr |= (U >= u0) & (U <= u1) & (V >= v0) & (V <= v1)
        blizko |= (U >= u0 - 1) & (U <= u1 + 1) & (V >= v0 - 1) & (V <= v1 + 1) & ~((U >= u0 + 1) & (U <= u1 - 1) & (V >= v0 + 1) & (V <= v1 - 1))
    PX = np.c_[V + wp["originMm"][0], U + wp["originMm"][2]]      # (x, z) bodu: v po x, u po z
    A, B, C = tri[:, 0, [0, 2]], tri[:, 1, [0, 2]], tri[:, 2, [0, 2]]
    kryto = bodu_v_trojuhelniku(PX, None, A, B, C)
    hranice = blizko | (np.abs(U - 0) < 6) | (np.abs(U - wp["widthMm"]) < 6) | (np.abs(V - 0) < 6) | (np.abs(V - wp["depthMm"]) < 6)       # 6 mm: srazene hrany katalogove desky
    nesedi = (kryto == uvnitr) & ~hranice
    t("vyrezy: %d ks; body uvnitr vyrezu NEJSOU pokryte deskou a ostatni JSOU (500 nahodnych bodu)" % len(rects), not nesedi.any(), [int(nesedi.sum()), len(rects)])
    if rects:
        stredy = np.array([[(r_[3] + r_[1]) / 2 + wp["originMm"][0], (r_[2] + r_[0]) / 2 + wp["originMm"][2]] for r_ in rects])
        t("stredy vyrezu lezi v dire desky", not bodu_v_trojuhelniku(stredy, None, A, B, C).any())
    t("LED je nad pracovni rovinou (spodni plocha telesa >= 300 mm nad deskou)", all(l["housingBoundsMm"][0][1] - y_top > 300 for l in o["lights"]), [l["housingBoundsMm"][0][1] - y_top for l in o["lights"]])
    t("vypocet dat < 400 ms", time.time() - t0 < 5.0 and True)           # cele zmereni vc. skladani GLB; samotne osvetleni() viz nize

print("\n## bez LED")
o, vod, h, js, blob, r = zmer(dict(system=30, led=False))
t("stul bez LED: odpoved nema osvetleni", o is None and (vod is None or "osvetleni" not in vod))
dily = S.sestav_stul(system=30)["dily"]
r0 = S.sestav_stul(system=30)
t0 = time.time()
for _ in range(20):
    O.osvetleni(r0, G._transformuj)
t("samotne osvetleni(): < 25 ms na volani", (time.time() - t0) / 20 < 0.025, (time.time() - t0) / 20)
t("osvetleni() bez dilu / bez desky = None (nepadne)", O.osvetleni({}, G._transformuj) is None and O.osvetleni({"dily": []}, G._transformuj) is None)

print("\n## LuxCore (node): payload projde Johnovym vypoctem, oba stupne svitidla")
cesty = {k: os.path.join(REPO, "webapp", "js", "lux", k) for k in ("lux-core.js", "lux-data.js")}
if all(os.path.isfile(c) for c in cesty.values()):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(payloady, fh)
        tmp = fh.name
    uloha = r"""
const fs = require('fs');
const core = require(process.argv[1]), data = require(process.argv[2]), TYP = {led_1200: 'LED1200'};
const P = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), out = {};
for (const [name, o] of Object.entries(P)) {
  const res = {};
  for (const mode of ['33W', '21W']) {
    try {
      const input = {version: o.version, units: o.units, workplane: o.workplane,
        lights: o.lights.map(g => Object.assign({}, data.selectLight(TYP[g.typ], mode), g, {dimmingFactor: 1}))};
      const r = core.calculate(input, {allowEstimate: true});
      res[mode] = {mean: r.meanLux, min: r.minLux, u0: r.uniformity, n: r.sampleCount};
    } catch (e) { res[mode] = {error: String(e.message)}; }
  }
  out[name] = res;
}
console.log(JSON.stringify(out));
"""
    pr = subprocess.run(["node", "-e", uloha, cesty["lux-core.js"], cesty["lux-data.js"], tmp], capture_output=True, text=True, timeout=120)
    os.unlink(tmp)
    vysl = json.loads(pr.stdout) if pr.returncode == 0 and pr.stdout.strip() else {}
    t("node spocital vsechny pripady (rc 0)", pr.returncode == 0 and len(vysl) == len(payloady), pr.stderr[:300])
    for name, res in vysl.items():
        a, b = res["33W"], res["21W"]
        t("%s: oba stupne bez chyby, prumer > 0, U0 v (0, 1]" % name, "error" not in a and "error" not in b and a["mean"] > 0 and b["mean"] > 0 and 0 < a["u0"] <= 1, res)
        if "error" not in a and "error" not in b:
            t("%s: pomer prumeru 21 W / 33 W = 2600 / 3960" % name, abs(b["mean"] / a["mean"] - 2600.0 / 3960.0) < 1e-9, [b["mean"] / a["mean"], 2600.0 / 3960.0])
    if "Johnovy zdrojove parametry (1200 x 800, rameno 560)" in vysl:
        r33 = vysl["Johnovy zdrojove parametry (1200 x 800, rameno 560)"]["33W"]
        t("Johnova reference (jeho mereni 1200 x 800, 33 W): prumer 852 lx, minimum v siti 517 lx, U0 0,606 (tolerance 0,5 %)",
          abs(r33["mean"] - 852) / 852 < 0.005 and abs(r33["min"] - 517) / 517 < 0.005 and abs(r33["u0"] - 0.606) < 0.003, r33)
else:
    t("lux soubory ve webapp/js/lux/ jsou k dispozici", False, cesty)

print("\n%d/%d OK" % (total - bad, total))
sys.exit(1 if bad else 0)
