# Připni cokoli - v2 (nový úhelník, 1,4x rychlejší klip, modulární generátor)

Hotový soubor: `v2/repo/webapp/stavebnice/stavebnice-demo.glb` (863 kB, 21,1 s, jeden zacyklený klip `demo`, 30 fps, LINEAR), kopie `v2/stavebnice-demo.glb`.
Generátor: `v2/repo/scripts/stavebnice/build_demo_glb.py`, zdroj úhelníku `v2/repo/scripts/stavebnice/zdroje/uhelnik_3045_vysoka_kvalita.glb`
(+ `priprava_uhelnik_3045.py`, jak vznikl). Metadata: `v2/demo_extras.json`, `v2/drazka.json`. Testy: `run_tests.sh` (výstup `v2/_testy_vystup.txt`, 0 FAIL).
Sestavení: `./build_v2.sh` (nebo přímo `python build_demo_glb.py --profile ... --out ...`, parametry viz hlavička generátoru). Deterministické (2x stejný sha256).
V1 (`repo/`, `v0/`, `v1/`, `README.md`) zůstává beze změny. Obrázky pro oko: `v2/shots/`.

## 1. Úhelník ze STEPu (změna 1)

Katalogový `product_2895.glb` je hrubý převod (188 trojúhelníků, otvory ~6úhelníky). Zdroj `webapp/content-files/product_fbx/2895.step` jsem převedl znovu přes
`api/step_convert.convert_single_step(..., quality='high')` (OpenCascade v `api/step_venv`, pod společným zámkem, nic v `webapp/` ani `api/` jsem nezměnil):

| varianta | trojúhelníků | otvor | poznámka |
|---|---|---|---|
| katalog (quality low, decimace) | 188 | 11-14úhelník, apotéma 2,7 mm | původ workaroundu se zvětšováním válcové části |
| `quality='high'` | 3040 | kruh 108 segmentů, r = 3,250 | uzavřený; obsahuje i výrobní rytinu (logo) v boku x = 0 (~2000 tr.) |
| explicitně odchylka 0,15 / 0,08 / 0,04 / 0,02 mm, bez decimace, logo odfiltrováno | 786 / 907 / 1075 / 1362 | kruh 42-84 segmentů | síť NENÍ uzavřená (odfiltrované plochy loga nechají okna v boku), zamítnuto |

Vybráno `quality='high'` + rytina logo srovnaná do roviny boku (vrcholy zahloubení 0 < x < 0,6 mm se posunou na x = 0, stěny rytiny zdegenerují a odpadnou, dno vyplní okna):
**2300 trojúhelníků, uzavřený, objem 7700 mm3 (přesný objem dílu bez rytiny), bez loga/jména ve scéně**. Otvor Ø6,5 je kruh (108 segmentů, apotéma = poloměr s přesností 0,01 mm),
zahloubení je kuželové 90° do Ø12,6 (sklon 1,00), zaoblení hladká (`srovnani_uhelnik_katalog_vs_novy.png`). Orientace a poloha zůstaly (stejná `R`, střed otvoru
(15; 14), stejné rozměry 29 x 28 x 29). **Workaround odstraněn** (žádné zvětšování válcové části, žádné `hole_nominal_r`).
Šroub je nyní výchozí **zápustný M6 ISO 10642 (`--head csk`)**: kužel hlavy 90° leží v zahloubení s mezerou 0,04 mm, hlava je 0,14 mm pod horní plochou dílu; šroub má jmenovitý Ø6,0
(dřív kvůli hrubému otvoru 5,76). Válcová hlava zůstala volbou `--head cap`. Pant (3325) má stejné kuželové zahloubení, takže csk sedí i v něm.

Pant, kámen, otočná: katalogové GLB `product_3325/3582/3592.glb` jsou **bajtově shodné** s převodem ze STEPu v kvalitě high (ověřeno `cmp`), lepší zdroj tedy není.
Zkvalitnění je jen v mém zjednodušení: **pant bez decimace (8448 tr., dřív 7000)**, **kámen 3000 tr. (dřív 1500; závit v otvoru už není rozbitý, `srovnani_kamen_1500_3000_8808tr.png`)**,
otočná 1900 tr. beze změny (beze ztráty). Tvar drážky ani kinematika se nezměnily.

Trojúhelníky: profil 3452, úhelník 2300, pant 8448, kámen 3000, otočná 1900, šroub 1 2478, šroub 2 2958 (celkem ~24,5 tis.).
Viewer vynucuje `flatShading = true`; hladké otvory/válce vyžadují v pluginu `mat.flatShading = false` u materiálů s `userData.smooth` (viz v1 README, otevřený bod).

## 2. Tempo: 1,4x rychlejší (změna 2)

Jedna konstanta `TIME_SCALE = 1/1.4` v generátoru násobí všechny délky POHYBŮ (zapsané v „autorských sekundách“ A = tempo v1); pauzy jsou v reálných sekundách:
`INTRO_S = 2.2`, `SLOT_S = 2.2`, `FINAL_HOLD_S = 2.2`, `GROW_S = 0.3` (nárůst měřítka), rozpuštění `DISSOLVE_A = 2.2`. Navíc jsem zkrátil prostoje uvnitř upevnění
(klid po dotažení 1,3 -> 0,5 A, mezera mezi nátokem dílu a šroubem). Klip 29,2 s -> **21,1 s** (-28 % délky = 1,38x celkově; pohyby jsou 1,4x rychlejší, pauzy jen zkráceny na 2,2 s).

Časy (s), `extras.demo`:

| cue | t0 | t1 | délka | kotva | strana | g |
|---|---|---|---|---|---|---|
| intro | 0,00 | 2,20 | 2,20 | - | top | 0 |
| slot | 2,20 | 4,40 | 2,20 | a_slot | left | 0 |
| kamen | 4,40 | 6,90 | 2,50 | a_kamen | left | 1 |
| srouby1 | 6,90 | 11,61 | 4,71 | a_sroub1 | right | 5, 3, 1 |
| otocna | 11,61 | 13,90 | 2,29 | a_otocna | right | 2, 6 |
| srouby2 | 13,90 | 17,33 | 3,43 | a_sroub2 | left | 4, 2, 6 |
| cokoli | 17,33 | 21,10 | 3,77 | - | top | 5, 6, 1, 2, 3, 4 |

| step | t0 | t1 | g | cues |
|---|---|---|---|---|
| profil | 0,00 | 4,40 | 0 | intro, slot |
| kamen | 4,40 | 11,61 | 1, 5, 3 | kamen, srouby1 |
| otocna | 11,61 | 17,33 | 2, 6, 4 | otocna, srouby2 |
| cokoli | 17,33 | 19,53 | - | cokoli |
| konec | 19,53 | 21,10 | - | cokoli |

`poster` = 19,43 s (vše připnuto, celek před rozpuštěním). Všechny cues mají aspoň 2,2 s (kontroluje `test_kroky.py`). Hranice kroků jsou v klidu (rychlost dílů 0 mm/s, rotace 0 st/s),
poslední snímek == první (všechny uzly: poloha, rotace, měřítko).
Rychlosti: šroub max 25,6 st./snímek (limit 30; 4 otáčky za 2,3 s), otočná matice max 10,8 st./snímek, díly max 5,6 mm/snímek (viditelné), skryté dílce při neviditelném návratu max 14 mm/snímek.
Kamera (4:3): max 21,6 mm/snímek, směr pohledu max 92 st./s (limit 100), nejblíž 56 mm od profilu; 9:16: max 36 mm/snímek (vzdálenost kamery je 1,78x větší), vždy aktivní díly celé v záběru
a kotva cue v záběru pro 4:3, 16:9 i 9:16. Kamera před druhým upevněním vyjíždí už na konci dotahování prvního (jinak by matice naskočila mimo záběr); mezi upevněními jsem zmenšil
rozdíl azimutu (jinak 170 st./s), závěrečný odjezd má mezikroky.

## 3. Modularita: jak přidat další díl (změna 3)

Všechno, co se k sestavě přidává, je v `default_fastenings()` (oddíl 8 generátoru): **jedno upevnění = matice (`nut`) + díl (`part`) + šroub (`screw`) + poloha `x` + časy `t` + `cues` + `camera`**.
Z toho se samo generuje: uzly, materiály, g-čísla (explicitní `g` zůstávají, nové dostanou další volné: 7, 8, 9...), kotvy `a_<uzel>`, steps, cues, kamera, kroky v klipu,
závěrečný cue `cokoli` a rozpuštění (vždy poslední, `cokoli` + `konec`), `poster`, `extras.demo.nodes` a `extras.demo.fastenings`. `TIME_SCALE` zrychlí i nové upevnění.

Postup:
1. **Zdroj dílu.** Katalogový `product_<id>.glb` (`file='product_<id>.glb'`, `--katalog`), nebo vlastní GLB do `scripts/stavebnice/zdroje/` (`file='zdroje/<jméno>.glb'`). Je-li katalogový model hrubý
   (jako byl úhelník), udělej nový převod ze STEPu: `priprava_uhelnik_3045.py` je šablona (`quality='high'` + srovnání rytiny).
2. **Orientace.** `R` otočí lokální osy GLB tak, aby osa otvoru pro šroub byla svisle (Y) a dosedací rovina měla nejnižší Y; `hole_approx_xz` = střed otvoru v osách po `R`
   (`hole_search_r` = okno hledání kružnice). Kontrola: v `drazka.json` -> `upevneni[].dil.otvor_polomer` musí vyjít poloměr otvoru (např. 3,25); díl s kuželovým zahloubením 90° použije výchozí šroub csk
   (`seat_height` si výšku dosednutí spočítá z geometrie).
3. **Matice.** `nut.kind`: `'slide'` = kámen (zasune se z čela, při dotahování se zvedne k okrajům; `head_zmin` = Z-práh hlavy kamene) nebo `'drop_turn'` = otočná (sjede shora na dno komory, při dotahování se sama otočí o 90 st.;
   `plate_y_range` = výška zubů, `sense`). Jiný druh = nová větev v `build()` (kinematika matice) a v `drazka_report()`.
4. **Data upevnění.** Jedinečné názvy uzlů ASCII (`nut.node`, `part.node`, `screw.node`), `anchor` = bod UVNITŘ materiálu dílu (kotva), `x` (mm podél profilu, díly od sebe aspoň ~60 mm a v rozsahu -150..150),
   `L` a `turns` šroubu, materiál (nový přidat do `MATERIALS`), `t` v A od začátku upevnění (`part` = začátek sjezdu dílu, `screw` = začátek šroubu, `cue_split` = konec cue matice, `end`; vzor: 3,5/5,3/3,5/10,1 pro kámen, 1,7/3,2/3,2/8,0 pro otočnou),
   `cues` (id pro texty stránky, kotva `nut|part|screw`, strana, g), `camera` (klíče `K(...)`: čas relativně k `start|part|screw|end`; po předchozím upevnění nech kameru uvolnit místo klíčem `K('end', -0.5, ...)`, a první klíč nového upevnění dej aspoň 0,4 A po `start`).
5. **Sestav a testuj:** `./build_v2.sh`, pak `./run_tests.sh` (celá sada, ~12 min) nebo rychle: `python test_struktura.py; test_smycka.py; test_kroky.py; test_kotvy.py; test_kamera.py` (vše generické pro libovolný počet upevnění) + `test_penetrace.py` (průniky všech dvojic uzlů).
   `test_modularita.py` je živý příklad: sestaví klip se třetím upevněním (držák magnetu 3084 + otočná matice) čistě změnou dat a prožene ho obecnými testy (10/10 OK; `shots/demo_tretiho_upevneni_magnet.png`).
6. Stránka/plugin: nové cue/step id a g čtou z `extras.demo` (`cues`, `steps`, `nodes`, `fastenings`); texty pro nová cue id je třeba doplnit na straně stránky.

## 4. Výsledky měření

Celá sada `run_tests.sh` nad v2: **0 FAIL**, všech 12 testů exit 0 (`_testy_vystup.txt`): struktura 21/21, smyčka 8/8, kroky 5/5 (včetně min. délky cue), kotvy 8/8, kamera 8/8, průniky OK, otočná matice OK,
nový úhelník 13/13, alternativa kamene OK, modularita 10/10, reprodukovatelnost OK (stejné bajty), živý viewer3d.js: `legacy:false`, `warnings:[]`, bez chyb v konzoli, plugin s AnimationMixerem přehraje klip.

Zanoření v celém klipu (profil přes přesné SDF průřezu po 1/30 s, mesh-mesh dvojice všech 6 pohyblivých uzlů bodovým vzorkováním + test uvnitř uzavřené sítě):

| dvojice | nejhorší zanoření (mm) | poznámka |
|---|---|---|
| úhelník, pant vs profil | 0,000 | dosednutí na země (dotyk plochou) |
| kámen vs profil | -0,080 | vůle; hlava pod okraji s rezervou 0,08 |
| šrouby vs profil | -1,48 | vůle |
| **otočná matice vs profil** | **0,181** (t = 15,2 s, otočení 47 st.) | spodní hrany desky proti 45st. zkosení komory; zuby 0,13, výstupek v krčku 0,13-0,15 (tolerance zadavatele 0,35); cíl 0,15 překročen o 0,03 mm; opačný smysl otáčení 0,57-0,75 |
| **úhelník vs šroub / kámen / pant / otočná** | **0** (dřív 0,12-0,16) | žádný bod jedné sítě uvnitř druhé; hlava csk sedí s mezerou 0,04 mm |
| všechny ostatní mesh-mesh dvojice | 0 | nejmenší odstup obalů kámen-úhelník 1,1 mm, otočná-pant 3,3 mm, ostatní > 140 mm |
| závit: šroub x matice | 0,31-0,51 | záměrný překryv (šroub Ø6,0 proti otvoru matice Ø5,0-5,5) |

## 5. Otevřené body

1. Kámen je T matice 3592, ne čtvercová 3066 (nevejde se: zanoření 0,70-1,25 mm) - potvrdit s Robertem (beze změny od v1).
2. Otočná matice zasahuje při otáčení do profilu max. 0,18 mm (reálný model; cíl 0,15). Snížit lze jen úpravou modelu matice.
3. Hlava šroubu csk je 0,14 mm pod horní plochou úhelníku (a podobně u pantu) - věrné zapuštění; válcová hlava `--head cap` zůstala.
4. Viewer vynucuje `flatShading = true` všem materiálům; hladké válce plugin přepne `flatShading = false` u materiálů s `userData.smooth`.
5. Úhelník: logo vyrobce jsem ze zdroje odstranil (srovnání rytiny do roviny boku), takže ve scéně i v repu není; zdroj `2895.step` zůstal beze změny.
6. Délka 21,1 s místo cílových ~20,9 (pauzy 3x 2,2 s se nezkracují); kamera `pos` je nominální pro 4:3, vzdálenost si plugin dopočítá z `fit` (viz v1 README).
7. `test_penetrace` měří mesh-mesh po 1/30 s; jemné měření po 1/90 s (`--jemne`, ~15 min) jsem pro v2 nespouštěl (v1 dávalo shodné hodnoty, 0,181 vs 0,179).
8. Ověřeno jen offline (SwiftShader, plain three.js, viewer3d.js 1.8.0), neověřeno na skutečném zařízení ani s vaším pluginem.

---
## Poznámky bot10 (2026-10-03)
- Generátor je tady, jeho TESTY (test_*.py, test_viewer.js, run_tests.sh, tools/, snímky) jsou ve staré pracovní složce agenta: archiv `private-files/archiv/stavebnice_model_pracovni_slozka_2026-10-03.tar.gz` (rozbalit a spustit `run_tests.sh`; cesty uvnitř míří do `scratchpad`, uprav `cd` a cestu k profilu). Vstupní profil `profil_40x40_sl_s10.glb` je v archivu (`stavebnice/`) - vzniká z Dogus STEP (`scripts/2026-10-03_dogus_stp_jeden_profil.py`).
- Přestavění: `python build_demo_glb.py --profile profil_40x40_sl_s10.glb --katalog /opt/konfigurator/webapp/katalog --out stavebnice-demo.glb`; výsledek jde do `webapp/pripni-cokoli/stavebnice-demo.glb` (soubor je pod zámkem jako celé `webapp/`) a zvýší se `PC_V` v `webapp/pripni-cokoli.html` (cache).
- KÁMEN = produkt 3592 (T matice M6 - drážka 10), NE čtvercová 3066: v katalogu se „T matice - kámen“ jmenují 3057/3230/3265/3308, čtvercová 3066 se do komory (svisle 3,03 mm) nevejde. Poster pro „omezit animace“ je ve v2 přímo v extras (smontovaný stav). Plugin `demo-stavebnice.js` navíc nastavuje hladké stínování materiálům s `extras.smooth` (viewer jinak vynucuje flatShading).
- Test stránky se syntetickým modelem: `scripts/2026-10-03_pripni_cokoli_testy/run_all.sh`.
