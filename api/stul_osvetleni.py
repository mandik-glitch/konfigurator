"""Data pro POCITADLO LUXU (John, `vystupy/pocitadlo_luxu_v2`; Robert 2026-10-05: "zakomponuj to pocitadlo luxu do generatoru") ze SKUTECNE geometrie generatoru
stolu (bot10): pracovni rovina (horni plocha pracovni desky + otvory vyrezu) a LED svitidla (obalka telesa, svitici cara) - uz v souradnicich GLB (vycentrovano, podlaha y = 0).

Kontrakt (docs/KONTRAKT_KONFIGURATOR_UI.md, "Pocitadlo luxu"; Johnuv datovy kontrakt `INTEGRACE.md`): `vodici.osvetleni = {version, units, workplane, lights[]}`.
- `workplane`: `originMm` = predni levy bod HORNI plochy pracovni desky (min x, horni y, min z), `axisU` = [0,0,1] (sirka stolu = osa z), `axisV` = [1,0,0] (hloubka = osa x),
  `normal` = [0,1,0], `widthMm` / `depthMm` = rozmer sjednocenych pracovnich desek (`prac_*`), `excludeRects` = vyrezy [u0, v0, u1, v1] v mm od pocatku (u po z, v po x).
- `lights[]`: JEN GEOMETRIE kazde LED (id, typ, type linear, startMm / endMm = svitici cara u spodni plochy telesa, direction dolu, housingBoundsMm = obalka telesa,
  housingLengthMm, nominalLengthMm, geometryStatus 'hypothesis'); vykon, tok, uhel, Ra... pridava klient z `LuxData.selectLight(sku, stupen)` (jedna kopie udaju o svitidle; `typ` -> sku mapuje klient, verejna odpoved SKU ani cisla produktu nenese).
Polohy se meri z VSECH skutecnych vrcholu LED (stejne jako John, `build_fixture.py`) a pak se posunou STEJNYM posunem jako model (`stul_glb.poskladej_glb`) - nikdy neposilat
polohy generatoru k posunutemu GLB. Svitici cara 1200 mm vystredena v telese 1247 mm je hypoteza Johna (skutecna svitici delka a fotometrie IES/LDT nejsou znamy)."""
import numpy as np

import stul_konfigurator as S

VERZE = 1
LED_PART = "product_4929"          # karta 4929 / SKU LED1200 (LEDVANCE DampProof Compact TH 1200 IP66 PS)
LED_SKU = "LED1200"                # JEN dokumentace: ve verejne odpovedi sku ani cisla produktu NESMI byt (test_stul_shop.py ZAKAZANE); klient mapuje `typ` -> katalog
TYP_LED = "led_1200"               # neutralni oznaceni typu svitidla ve verejne odpovedi (klient: js/stul-luxy.js TYP_SKU)
LED_SVITI_MM = 1200.0              # jmenovita delka = svitici cara (hypoteza); teleso vc. koncovek je S.LED_SIRKA (1247 mm)
# delky svitidla (Robert 2026-10-07): dil katalogu -> (neutralni `typ` ve verejne odpovedi, jmenovita delka = svitici cara v mm); LED 600 = karta #5359 (16 W, 1920 lm), GLB = LED 1200 zkracena o 600 mm
TYP_DILU = {S.LED_TYPY[1200]: (TYP_LED, 1200.0), S.LED_TYPY[600]: ("led_600", 600.0)}
DESKA_PART = "product_4933"
PRACOVNI_PREFIX = "prac_"          # deska_id pracovni desky (prac_0, prac_1 ... pri rozdeleni siroke desky), police jsou pol*


def _r(v, nd=3):
    return [round(float(x), nd) for x in v]


def osvetleni(r, transformuj):
    """Payload v souradnicich GENERATORU (pred posunem skladace GLB) nebo None (bez LED / bez pracovni desky). `transformuj(part_id, dil)` = `stul_glb._transformuj`
    (vrcholy dilu ve svete generatoru, mm)."""
    dily = (r or {}).get("dily") or []
    desky = [d for d in dily if d["part_id"] == DESKA_PART and str(d.get("deska_id") or "").startswith(PRACOVNI_PREFIX)]
    leds = [d for d in dily if d["part_id"] in TYP_DILU]
    if not desky or not leds:
        return None
    box = [S._aabb(d) for d in desky]
    lo = np.min([b[0] for b in box], axis=0)
    hi = np.max([b[1] for b in box], axis=0)
    sirka, hloubka = float(hi[2] - lo[2]), float(hi[0] - lo[0])
    vyrezy = []
    for v in r.get("vyrezy") or []:
        u0, u1 = sorted((float(v["z0"]) - lo[2], float(v["z1"]) - lo[2]))
        v0, v1 = sorted((float(v["x0"]) - lo[0], float(v["x1"]) - lo[0]))
        u0, u1, v0, v1 = max(0.0, u0), min(sirka, u1), max(0.0, v0), min(hloubka, v1)
        if u1 - u0 > 1e-6 and v1 - v0 > 1e-6:                       # mimo desku / nulova plocha se nepredava (lux-core by ji odmitl)
            vyrezy.append([round(float(u0), 3), round(float(v0), 3), round(float(u1), 3), round(float(v1), 3)])
    svitidla = []
    for d in leds:
        P, _, _ = transformuj(d["part_id"], d)
        svitidla.append((P.min(axis=0), P.max(axis=0), d["part_id"]))
    svitidla.sort(key=lambda b: (b[0][2] + b[1][2], b[0][0]))        # zleva doprava po sirce stolu: stabilni id
    lights = []
    for k, (a, b, pid) in enumerate(svitidla, 1):
        c = (a + b) / 2.0
        typ, sviti = TYP_DILU[pid]
        lights.append({
            "id": "led-%d" % k, "typ": typ, "type": "linear",
            "startMm": _r([c[0], a[1], c[2] - sviti / 2.0]), "endMm": _r([c[0], a[1], c[2] + sviti / 2.0]),
            "direction": [0, -1, 0], "housingBoundsMm": [_r(a), _r(b)],
            "housingLengthMm": float(S.led_telo_dilu(pid)), "nominalLengthMm": sviti, "geometryStatus": "hypothesis"})
    return {"version": VERZE, "units": "mm",
            "workplane": {"originMm": _r([lo[0], hi[1], lo[2]]), "axisU": [0, 0, 1], "axisV": [1, 0, 0], "normal": [0, 1, 0],
                          "widthMm": round(sirka, 3), "depthMm": round(hloubka, 3), "excludeRects": vyrezy},
            "lights": lights}


def v_glb(o, posun):
    """Stejny payload po posunu o `posun` (vektor generator -> GLB, `stul_glb._META_CACHE`): polohy (pocatek, konce svitici cary, obalky telesa); osy, rozmery a vyrezy
    (relativni k pocatku) se nemeni."""
    def b(v):
        return [round(float(v[i]) + float(posun[i]), 3) for i in range(3)]
    wp = dict(o["workplane"], originMm=b(o["workplane"]["originMm"]))
    lights = [dict(l, startMm=b(l["startMm"]), endMm=b(l["endMm"]), housingBoundsMm=[b(l["housingBoundsMm"][0]), b(l["housingBoundsMm"][1])]) for l in o["lights"]]
    return dict(o, workplane=wp, lights=lights)
