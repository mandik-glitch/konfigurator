#!/usr/bin/env python3
"""Zaplata webapp/js/lux/lux-data.js: katalog svitidel pocitadla luxu dostane LED600 (karta #5359 "Osvetleni LED 600mm 16W 1920lm"; Robert 2026-10-07: "LED 600 doplnit do generatoru").
Zname jsou JEN udaje z karty (vykon 16 W, svetelny tok 1920 lm, delka 600 mm, teleso 647 mm z modelu); vse ostatni (vyrobce, model, stitek, EAN, krytí, zivotnost...) je null = neznamo, plugin to
nezobrazuje. Optika (cosinova charakteristika, 120 stupnu) je PREDPOKLAD podle LED1200 stejne rodiny a vede se jako `hypothesis` (vysledky jsou "Orientacni odhad") - ZKONTROLOVAT podle stitku /
datoveho listu LED 600. Jediny vykonovy stupen 16 W (u LED 1200 jsou dva). Kotvena nahrada (assert count == 1) proti ZIVEMU souboru. Pouziti: patch_luxdata.py <vstup lux-data.js> <vystup>"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
a = '''      source: 'Dvě fotografie štítku a obalu svítidla; karta 4929; délka modelu v generátoru stolu'}],
'''
b = '''      source: 'Dvě fotografie štítku a obalu svítidla; karta 4929; délka modelu v generátoru stolu'},
    // LED 600 (karta 5359, 2026-10-07): zná se JEN výkon, tok a délka z karty; ostatní údaje neznámé (null), optika = PŘEDPOKLAD jako u LED1200 (hypothesis) – ověřit podle štítku / datového listu
    {productId: 5359, sku: 'LED600', type: 'linear', luminousFluxLm: 1920, powerW: 16,
      manufacturer: null, modelName: null, typeDesignation: null, labelCode: null, ean: null,
      colour: null, nominalLengthMm: 600, housingLengthMm: 647,
      labelledDimensionsMm: null, emittingLengthMm: null, beamAngleDeg: null,
      distribution: {kind: 'cosine_power', exponent: 1, beamAngleDeg: 120, status: 'hypothesis',
        source: 'předpoklad: stejná optika jako LED1200 (kosinová charakteristika, 120°); skutečná fotometrie LED 600 není známa'},
      cctK: null, criRa: null, ip: null, ik: null, indoorOnly: null,
      dimmable: false, protectionClass: null, operatingTemperatureC: null,
      lifetime: null, voltageV: null, frequencyHz: null,
      markings: [],
      defaultModeId: '16W', modeId: '16W',
      powerModes: [{id: '16W', powerW: 16, luminousFluxLm: 1920, efficacyLmPerW: 120}],
      photometryFile: null, maintenanceFactor: null,
      sources: {card: 'karta_5359'},
      source: 'Karta 5359 (Osvětlení LED 600mm 16W 1920lm): výkon, tok a délka; délka modelu v generátoru stolu (647 mm); optika předpokládána jako u LED1200'}],
'''
assert s.count(a) == 1, "kotva katalog: %d vyskytu" % s.count(a)
open(dst, "w", encoding="utf-8").write(s.replace(a, b))
print("OK ->", dst)
