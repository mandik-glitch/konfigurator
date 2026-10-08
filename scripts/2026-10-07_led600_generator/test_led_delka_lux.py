#!/usr/bin/env python3
"""Test POCITADLA LUXU s LED 600 (bot8, 2026-10-07; Robert: "LED 600 doplnit do generatoru"): payload ze serveru (`stul_osvetleni.osvetleni`) + katalog svitidel `webapp/js/lux/lux-data.js` (zaznam LED600)
+ LuxCore (Node) - bez prohlizece a bez DB. Platny AZ PO nasazeni statickeho JS (`apply_js.sh`); pred nasazenim ho pust z kandidatniho korene (prepis webapp, viz prepare_cand_web.sh):
  cd $SP/led/mirror2 && api/venv/bin/python3 scripts/2026-10-07_led600_generator/test_led_delka_lux.py        (koren = kam ukazuje cesta skriptu; STUL_API_OVERRIDE se nepouziva, api/ je v kandidatnim koreni)
Hlida: zaznam LED600 (16 W, 1920 lm, jediny stupen 16W, delka 600 / teleso 647, neznama pole = null, optika 'hypothesis'), vypocet LuxCore nad payloadem LED 600 (konecne cifry, odhad), linearitu
v toku, nezavislou kontrolu proti LED 1200 (2 x LED 600 na stole 1294 mm vs 1 x LED 1200: pomer prumernych luxu odpovida pomeru toku 3840 / 3960 s ohledem na jinou delku svitici cary)."""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _spolecne as C  # noqa: E402

S, G = C.nacti_generator()
import stul_osvetleni  # noqa: E402

OK, FAILS = 0, []


def check(cond, msg):
    global OK
    if cond:
        OK += 1
    else:
        FAILS.append(msg)
        print(f"  CHYBA: {msg}")


def payload(**kw):
    r = S.sestav_stul(**{"led_pocet": getattr(S, "LED_MAX", 1), **kw})                     # od 2026-10-08 RUCNI pocet svitidel: tento test overuje svitidla podle sirky = nejvic, co se vejde
    return stul_osvetleni.osvetleni(r, G._transformuj)


vstupy = [{"nazev": "led600_1294", "o": payload(sirka=1294, led_delka=600), "mode": "16W"},
          {"nazev": "led1200_1294", "o": payload(sirka=1294), "mode": "33W"},
          {"nazev": "led600_2000", "o": payload(sirka=2000, led_delka=600), "mode": "16W"},
          {"nazev": "led600_900", "o": payload(sirka=900, led_delka=600), "mode": "16W"}]
JS = r'''
const fs = require("fs"), path = require("path");
const REPO = process.argv[2], LuxCore = require(path.join(REPO, "webapp/js/lux/lux-core.js")), LuxData = require(path.join(REPO, "webapp/js/lux/lux-data.js"));
const TYP_SKU = { led_1200: "LED1200", led_600: "LED600" };
const vstupy = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = { katalog: LuxData.catalogue.filter(l => l.sku === "LED600")[0] || null, vysledky: {} };
for (const v of vstupy) {
  const o = v.o, svetla = (k) => o.lights.map(g => Object.assign({}, LuxData.selectLight(TYP_SKU[g.typ], v.mode), g, { dimmingFactor: 1, luminousFluxLm: LuxData.selectLight(TYP_SKU[g.typ], v.mode).luminousFluxLm * k }));
  const calc = (k) => LuxCore.calculate({ version: o.version, units: o.units, workplane: o.workplane, lights: svetla(k) }, { allowEstimate: true });
  const a = calc(1), b = calc(2);
  out.vysledky[v.nazev] = { mean: a.meanLux, min: a.minLux === undefined ? null : a.minLux, mean2: b.meanLux, estimated: a.estimated === undefined ? null : a.estimated, n: o.lights.length, mode: o.lights.length ? LuxData.selectLight(TYP_SKU[o.lights[0].typ], v.mode).modeId : null };
}
console.log(JSON.stringify(out));
'''
with tempfile.TemporaryDirectory() as d:
    json.dump(vstupy, open(os.path.join(d, "v.json"), "w"))
    open(os.path.join(d, "t.js"), "w").write(JS)
    p = subprocess.run(["node", os.path.join(d, "t.js"), C.REPO, os.path.join(d, "v.json")], capture_output=True, text=True, timeout=300)
if p.returncode != 0:
    print("CHYBA: node selhal:", p.stderr[-600:])
    sys.exit(1)
res = json.loads(p.stdout.strip().splitlines()[-1])
k = res["katalog"]
check(k is not None and k["sku"] == "LED600" and k["productId"] == 5359, "katalog svitidel ma zaznam LED600 (produkt 5359)")
if k:
    check(k["luminousFluxLm"] == 1920 and k["powerW"] == 16 and k["nominalLengthMm"] == 600 and k["housingLengthMm"] == 647, f"LED600: 16 W, 1920 lm, delka 600, teleso 647 ({k['powerW']}, {k['luminousFluxLm']}, {k['nominalLengthMm']}, {k['housingLengthMm']})")
    check([m["id"] for m in k["powerModes"]] == ["16W"] and k["defaultModeId"] == "16W" and k["powerModes"][0]["luminousFluxLm"] == 1920 and k["powerModes"][0]["powerW"] == 16, f"LED600: jediny vykonovy stupen 16W ({k['powerModes']})")
    check(k["distribution"]["status"] == "hypothesis" and k["distribution"]["kind"] == "cosine_power" and "předpoklad" in k["distribution"]["source"], "LED600: optika je vedena jako hypoteza (cosinova, zdroj = predpoklad)")
    neznama = ["manufacturer", "modelName", "typeDesignation", "labelCode", "ean", "colour", "labelledDimensionsMm", "emittingLengthMm", "beamAngleDeg", "cctK", "criRa", "ip", "ik", "indoorOnly", "protectionClass", "operatingTemperatureC", "lifetime", "voltageV", "frequencyHz", "photometryFile", "maintenanceFactor"]
    check(all(k[x] is None for x in neznama), f"LED600: neznama pole (nevymyslene udaje) jsou null ({[x for x in neznama if k[x] is not None]})")
v = res["vysledky"]
check(all(x["mean"] is not None and x["mean"] > 0 and x["n"] >= 1 for x in v.values()), f"vypocet LuxCore je konecny pro vsechny konfigurace ({ {n: round(x['mean']) for n, x in v.items()} })")
check(all(abs(x["mean2"] / x["mean"] - 2.0) < 1e-9 for x in v.values()), "prumerne luxy jsou linearni v toku (2 x tok = 2 x lux)")
check(v["led600_1294"]["n"] == 2 and v["led1200_1294"]["n"] == 1 and v["led600_1294"]["mode"] == "16W" and v["led1200_1294"]["mode"] == "33W", f"stoly 1294: 2 x LED 600 vs 1 x LED 1200 ({v['led600_1294']['n']}, {v['led1200_1294']['n']})")
pomer = v["led600_1294"]["mean"] / v["led1200_1294"]["mean"]
check(0.85 < pomer < 1.05, f"stul 1294: 2 x LED 600 (3840 lm, svitici cara 2 x 600) vs 1 x LED 1200 (3960 lm, cara 1200): pomer prumernych luxu {pomer:.3f} v rozumnem pasmu 0,85-1,05 (pomer toku 0,970)")
check(v["led600_2000"]["n"] == 3 and v["led600_900"]["n"] == 1, "stoly 2000 a 900: 3 / 1 svitidlo 600")
print(f"\n==> {OK}/{OK + len(FAILS)} kontrol OK" + (f", SELHALO {len(FAILS)}: " + "; ".join(FAILS[:5]) if FAILS else ""))
sys.exit(1 if FAILS else 0)
