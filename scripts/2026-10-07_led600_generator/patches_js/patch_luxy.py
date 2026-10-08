#!/usr/bin/env python3
"""Zaplata webapp/js/stul-luxy.js: pocitadlo luxu zna svitidlo LED 600 (Robert 2026-10-07: "LED 600 doplnit do generatoru"): `typ` led_600 -> katalog LED600; stupne vykonu (tlacitka 33 W / 21 W u LED 1200,
jediny stupen 16 W u LED 600) se ridi TYPEM svitidla v aktualnim modelu: pri zmene typu (volba delky svitidla ve 3D nahledu) se tlacitka postavi znovu, zvoleny stupen, ktery novy typ nema, se vrati na
vychozi stupen typu a skupina tlacitek se u typu s jedinym stupnem schova. Kotvene nahrady (assert count == 1) proti ZIVEMU souboru; piny ?v= pak prepise scripts/stul_verze.py (apply_js.sh).
Pouziti: patch_luxy.py <vstup stul-luxy.js> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def nahrad(s, a, b, label):
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    return s.replace(a, b)


s = nahrad(s, '''var TYP_SKU = { led_1200: "LED1200" };''', '''var TYP_SKU = { led_1200: "LED1200", led_600: "LED600" };''', "TYP_SKU")
s = nahrad(s, '''          if (!sku) throw new Error("Neznámý typ svítidla: " + g.typ);
          return Object.assign({}, LD.selectLight(sku, mode || undefined), g, { dimmingFactor: 1 });''',
           '''          if (!sku) throw new Error("Neznámý typ svítidla: " + g.typ);
          var entry = LD.catalogue.filter(function (l) { return l.sku === sku; })[0];
          var m = mode && entry && entry.powerModes && entry.powerModes.some(function (x) { return x.id === mode; }) ? mode : undefined;       // stupen, ktery typ nema (1200: 33 W / 21 W, 600: 16 W) -> vychozi stupen typu
          return Object.assign({}, LD.selectLight(sku, m), g, { dimmingFactor: 1 });''', "build")
s = nahrad(s, '''    function sync() {
      updateBar();''', '''    function sync() {
      postavModes();                       // typ svitidla se mohl zmenit (volba delky): tlacitka stupnu odpovidaji typu v aktualnim modelu
      updateBar();''', "sync")
s = nahrad(s, '''        modesEl.hidden = !(enabled && ready && o);''', '''        modesEl.hidden = !(enabled && ready && o) || modesEl.childNodes.length < 2;               // typ s jedinym stupnem (LED 600: 16 W) volbu stupne nema''', "updateBar")
s = nahrad(s, '''    function postavModes() {
      if (!modesEl || modesEl.childNodes.length || !ready) return;
      var o = payloadShown(), sku = o && TYP_SKU[o.lights[0].typ], entry = sku && global.LuxData.catalogue.filter(function (l) { return l.sku === sku; })[0];
      if (!entry || !entry.powerModes) return;
      if (!mode) mode = entry.defaultModeId;
''', '''    var modesSku = null;
    function postavModes() {
      if (!modesEl || !ready) return;
      var o = payloadShown(), sku = o && TYP_SKU[o.lights[0].typ], entry = sku && global.LuxData.catalogue.filter(function (l) { return l.sku === sku; })[0];
      if (!entry || !entry.powerModes) return;
      if (modesSku === sku && modesEl.childNodes.length) return;                   // tlacitka uz odpovidaji typu svitidla
      modesEl.textContent = ""; modesSku = sku;
      if (!mode || !entry.powerModes.some(function (m) { return m.id === mode; })) mode = entry.defaultModeId;          // stupen predchoziho typu tento typ nema
''', "postavModes")
open(dst, "w", encoding="utf-8").write(s)
print("OK ->", dst)
