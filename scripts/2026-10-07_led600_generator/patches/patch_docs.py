#!/usr/bin/env python3
"""Zaplata dokumentace 'LED 600 do generatoru' (bot8, 2026-10-07): docs/KONTRAKT_KONFIGURATOR_UI.md (radek tabulky zavislosti slotu + sekce 'Delka LED svitidla') a MAPA_3D_A_GENERATORU.md (radek mapy).
Kotvene nahrady (assert count == 1) proti ZIVYM souborum. Pouziti: patch_docs.py <koren_repa> (zapisuje SOUBORY V KORENI - volat uvnitr zamku bot8, nebo s koren_repa = kopie)"""
import os
import sys

root = sys.argv[1]


def uprav(rel, a, b, label):
    p = os.path.join(root, rel)
    s = open(p, encoding="utf-8").read()
    assert s.count(a) == 1, "kotva %s: %d vyskytu" % (label, s.count(a))
    open(p, "w", encoding="utf-8").write(s.replace(a, b))


KONTRAKT = "docs/KONTRAKT_KONFIGURATOR_UI.md"
uprav(KONTRAKT, '''| `panelcount`, `panellen`, `panelpos`, `panelside` | `panels` |
''', '''| `panelcount`, `panellen`, `panelpos`, `panelside` | `panels` |
| `ledlen` | `posts`, `led`, `ledlight` |
''', "tabulka")
uprav(KONTRAKT, '''## Výchozí konfigurace generátoru – admin tlačítko „Uložit jako výchozí“''', '''## Délka LED svítidla 1200 / 600 mm (bot8 2026-10-07, Robert: „LED 600 doplnit do generátoru“)
Generátory 01–03 a 05 (systémy 30 / 35 / 40 / 45; stůl SSE LED nemá) nabízejí vedle LED 1200 (karta #4929) i **LED 600** (karta #5359 „Osvětlení LED 600mm 16W 1920lm“, 1 390 Kč bez DPH). **Výchozí je 1200, takže hash/kód a model všech dosavadních konfigurací zůstávají beze změny** (zlatý otisk 465 konfigurací, `test_led_delka.py` sekce C); `rules_version` se nemění.
- **Model** `webapp/katalog/product_5359.glb` = LED 1200 s PŘESNĚ vyříznutými 600 mm ze středu (647,001 mm; `scripts/2026-10-07_led600/led_zkrat.py`), stejný průřez, stejná souřadnicová soustava a STEJNÝ STŘED bboxu jako product_4929 (X = délka): šablonový člen LED se klonuje se stejnou polohou a otočením, jen s jiným dílem.
- **Generátor:** parametr `led_delka` (1200 | 600, výchozí 1200; jiná hodnota = `StulChyba mimo_rozsah`; `?led_delka=` v dotazu staff API); **všechna svítidla stolu jsou stejně dlouhá** a řadí se vedle sebe (rozteč = délka tělesa z GLB: 1247 / 647 mm, `led_telo_dilu`), počet `max(1, floor((šířka + 47) / těleso))`, skupina vycentrovaná jako dosud, přesah ≤ 47 mm (`LED_PREVIS`). **Nevejde-li se zvolená délka (1200 od šířky 1200, 600 od šířky 600), LED se odebere jako dosud** (`odebrano`, přepínač `led`; efektivní délka se vrací na 1200) – zvolená délka se sama NEsnižuje (stoly užší než 1200 mm bez volby se chovají jako dosud). `led_info` = `{delka, typy: [{delka, telo, pocet, min_sirka, vejde}]}` (jen když je svítidlo na stole). Bez svítidla (LED / stojky / svítidlo vypnuto, nebo odebráno) je `led_delka` = 1200 a do hashe se nepromítá.
- **Veřejné API:** slot **`ledlen`** (select, skupina Příslušenství, hned za `ledlight`, `depends_on: [posts, led, ledlight]`, hodnoty `"600" | "1200"`, popisky „N mm“, výchozí `"1200"`; texty cs/en/sk vč. `help_ledlen`, další jazyky anglická záloha). `options.ledlen` = `{ "<délka>": {disabled: true, reason} }` pro délky, které se na stůl nevejdou („LED svítidlo 1200 mm se sem nevejde – potřebuje stůl široký aspoň 1200 mm.“); bez svítidla `{}`; je-li v nabídce jen 1200, `{"hidden": true}`. **U zakázaného přepínače `led`** (LED se v dosavadní délce nevejde) server nabídne **kratší svítidlo místo roztažení stolu**: `options.led.on.suggest = {"ledlen": "600"}`, `suggest_label` „Zapnout kratší LED 600 mm“ (modul voleb patch aplikuje a přepínač zapne; nevejde-li se ani 600, zůstává dosavadní nabídka roztažení). Token (`stul_shop._zabal`): klíč `K` (mm) jen u jiné než výchozí délky; odkaz na výrobní list nese `led_delka` jen u 600; shrnutí voleb ukazuje „Délka LED svítidla: 600 mm“ jen u 600; klíč cache `resolve` nese požadovanou délku i nabízené délky.
- **Nabídka veřejnosti** (`stul_shop.led_delky_pro_pozadavek`, pravidlo 54): VEŘEJNOST (host, mini-shop, embed, e-shop) dostane vždy 1200 a **600 jen když karta #5359 je aktivní, není archivovaná, má GLB a je ve scéně** (`led_delky_verejne`, cache 30 s, chyba čtení DB = jen 1200); **zaměstnanec** (platná session) a kód mimo požadavek (testy, skripty) vidí obě.
- **3D ovládání:** část `led` má v nabídce „Zvolit LED N mm“ pro druhou délku (nevejde se = zakázáno s důvodem „Tahle délka LED se sem nevejde (širší stůl).“; EN/SK v `stul_ovladani_verejne.py`); parametr `led_delka` ↔ slot `ledlen` v `PARAM_NA_SLOT`; svítidla jedou s ramenem při živém tažení (`pevne`). Mapování dílu na přepínač (`PREPINAC_DILU`), název („LED osvětlení 600 mm“ v `_NAZVY`), chybový slot (`DIL_NA_SLOT`) a materiál (`stul_glb.MATERIAL_DILU` = led) jedou pro oba díly (`S.LED_PARTY`).
- **Počítadlo luxů:** `vodici.osvetleni.lights[]` nese `typ` `led_1200` | `led_600`, `nominalLengthMm` 1200 | 600 (svítící čára vystředěná v tělese), `housingLengthMm` 1247 | 647; klient mapuje `typ` → katalog (`js/stul-luxy.js` `TYP_SKU`; `js/lux/lux-data.js`: záznam LED600 = 16 W / 1 920 lm z karty, ostatní údaje NEZNÁMÉ (`null`), optika = HYPOTÉZA jako u LED1200 (cosinus 120°) → výsledky jsou „Orientační odhad“; **k ověření podle štítku / datového listu LED 600**). Tlačítka stupňů výkonu se řídí typem svítidla (LED 1200: 33 W / 21 W, LED 600: jediný stupeň 16 W, volba stupně se schová).
- **Testy:** `scripts/2026-10-07_led600_generator/` – `test_led_delka.py` (generátor, GLB, lux data; zlatý otisk 465 konfigurací proti stavu před zavedením volby, geometrie nezávisle z vrcholů meshe, hash, `led_info`, 3D menu, GLB, degradace při chybějícím GLB), `test_led_delka_zive.py` (živé tažení ramene se svítidly 600), `test_led_delka_shop.py` (veřejné API), `test_led_delka_stranka.js` (stránka Generátor stolu v Chromiu + počítadlo luxů), `mutace.py` (60 mutací). Existující `test_stul_shop.py` upraven jen o nový select `ledlen`.

## Výchozí konfigurace generátoru – admin tlačítko „Uložit jako výchozí“''', "sekce")

MAPA = "MAPA_3D_A_GENERATORU.md"
uprav(MAPA, '''| **Formáty tabulí laminodesky, dělení desek u střední opory**''', '''| **Délka svítidla LED 1200 / 600 mm** (Robert 2026-10-07: „LED 600 doplnit do generátoru“; generátory 01–03 a 05) | parametr `led_delka` (výchozí 1200 = vše beze změny, hash i díly), všechna svítidla stolu stejně dlouhá, řadí se vedle sebe po šířce stolu; LED 600 = karta #5359, model `product_5359.glb` = LED 1200 zkrácená o 600 mm; nevejde-li se zvolená délka, LED se odebere jako dosud; veřejný slot `ledlen` (+ nabídka „Zapnout kratší LED 600 mm“ u zakázaného přepínače LED); **veřejnosti se 600 nabídne jen s AKTIVNÍ kartou #5359, zaměstnanec vidí obě**; 3D menu „Zvolit LED N mm“; počítadlo luxů zná typ `led_600` (údaje svítidla z karty, optika = hypotéza) | `api/stul_konfigurator.py` (`LED_TYPY`, `led_telo_dilu`, `led_info`), `api/stul_shop.py` (`led_delky_pro_pozadavek`, slot `ledlen`, token `K`), `api/stul_glb.py`, `api/stul_osvetleni.py`, `js/stul-luxy.js`, `js/lux/lux-data.js`, `docs/KONTRAKT_KONFIGURATOR_UI.md`, testy `scripts/2026-10-07_led600_generator/` |
| **Formáty tabulí laminodesky, dělení desek u střední opory**''', "mapa")
print("OK docs ->", root)
