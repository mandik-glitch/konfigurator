# Připni cokoli, varianta 30×30 (drážka 8 mm): fakty z DB a disku

bot10, 2026-10-03, na žádost bot3 pro externího bota Johna. Jen ověřená fakta (DB a soubory ke dni zápisu), co ověřeno nebylo, je označeno „NEOVĚŘENO“. Cesty jsou v `/opt/konfigurator`.

## 1. Profil 30×30, drážka 8 mm
- Produkt **3457**, SKU **`1.1.08.030030.03`** („Hliníkový stavebnicový profil 30 x 30 mm Light“), `cfg_dily_id` = **`Object_7`**, drážka 8 (kanonické SKU dle Roberta 2026-09-26, `PROFILY_KATALOG.md` oddíl 2c). Další 30×30: 3458 (`…02`), 3460 (`…02.01` černý elox), 3461 (uzavřený), 3459 (radius), 3466 (těžký sigma `1.1.08.030030.01`); do animace jen 3457.
- **Použitelný průřez v 3D na disku NENÍ.** `webapp/katalog/Object_7.glb` je hrubý scénový model (100 vrcholů, 50 trojúhelníků, drážky jen obdélníkové, 30 × 1000 × 30 mm, délka v ose Y) a pro měření drážky se nehodí. STEP profilu 30×30 na disku není (do `private-files/dogus-stp/` jsem stáhl jen 40×40 `1.1.10.040040.03.step`).
- Dostupné podklady: výkres průřezu z karty (kóty 30, 23,5, drážka **8,2**, Ø7, Ø3,2, 1,4) `webapp/content-files/gallery/products/3457/2.jpg` (400×360 px) a z něj trasovaný obrys `webapp/pripni-cokoli/schema-30x30-d8.svg` (symetrizovaný, přesnost řádově 0,2 mm, jen schéma, ne pro měření vůlí).
- Přesný průřez = STEP z Dogus: profily se jinak nestahují, 40×40 jsem stáhl na Robertův výslovný pokyn. Pro 30×30 je potřeba Robertovo svolení, pak: `api/venv/bin/python scripts/2026-10-03_dogus_stp_jeden_profil.py --sku 1.1.08.030030.03 --apply` (nic nezapisuje do DB, uloží `private-files/dogus-stp/1.1.08.030030.03.step`) a převod `api/step_convert.py convert_single_step(step, glb, quality='high')`. Dostupnost CAD souboru pro toto SKU jsem dnes zkoušel (jen zjištění odkazu, bez stažení) a spojení bylo odmítnuto (`Connection reset`): **NEOVĚŘENO**, zda soubor existuje.
- Tvar drážky Light 30×30 se může lišit od SuperLight S10 u 40×40 (generátor ji měří z řezu a předpokládá tvar S10, viz oddíl 5).

## 2. Matice pro drážku 8 mm (GLB `webapp/katalog/product_<id>.glb`, STEP `webapp/content-files/product_fbx/<id>.step`, oba soubory existují)
Obálky v mm (osy GLB: x, y = výška od 0 nahoru, z), počet trojúhelníků v GLB.

| role | M | id | SKU | obálka x × y × z | tr |
|---|---|---|---|---|---|
| **kámen** = T matice | M4 / M5 / **M6** / M8 | 3586 / 3587 / **3588** / 3589 | `2.1.006.08.04` / `.05` / **`.06`** / `.08` | 15,9 × 5,9 × 16,0 | 5492 / 5384 / **4702** / 4694 |
| **otočná** = ozubená matice | M4 / M5 / **M6** | 3577 / 3578 / **3579** | `2.1.001.08.04` / `.05` / **`.06`** | 16,0 × 6,1 × 7,9 | 1574 / 1590 / **1606** |

- Ozubená M8 pro drážku 8 v katalogu **není**. 3182 (`2.1.001.08.06.00` rýhovaná nerezová M6) má stejnou obálku i velikost souboru jako 3579 (pravděpodobně stejná geometrie).
- Náhrada za dnešní pár 40×40 (jiná velikost, stejná osová konvence, počátek ve středu x/z, y od spodku): kámen 3592 (`2.1.006.10.06`, 19,7 × 10,5 × 20,0, 8808 tr) a otočná 3582 (`2.1.001.10.06`, 19,0 × 8,7 × 10,0, 1900 tr). Že orientační matice `R` v generátoru platí i pro 3588/3579 je potřeba ověřit.
- Šířka otočné 3579 je 7,9 mm proti hrdlu drážky 8,2 (vůle 0,15 mm na stranu; u 40×40 je 10,0 proti 10,2). **NEOVĚŘENO**, zda se nejdelší rozměr 16,0 mm otočí o 90° v komoře profilu 30×30 (rozměry komory z řezu chybí). Ostatní matice drážky 8 (obdélníková 3052–3055, pružinová 3594–3596, rýhovaná se čepem 3061 a další) nejsou pro tuto ukázku určené.

## 3. Šrouby
- Generátor šrouby nebere z katalogu, dělá je procedurálně (`make_screw(L, head, ...)`: M6 imbus, hlava zápustná 90° (`--head csk`) nebo válcová 10 × 6, šroubovicový závit). Dnes `L=12` (úhelník) a `L=14` (pant), 4 otáčky, jmenovitý Ø6,0. Pro 30×30 přepočítat délky: tloušťka matice je jiná (otočná 6,1 místo 8,7 mm) a díly mají jinou tloušťku.
- Katalogové šrouby se zápustnou hlavou jako srovnání: M5 3629 / 3630 / 3631 (`2.1.20.0510` / `0512` / `0516`), M6 3632 / 3633 / 3634 (`2.1.20.0612` / `0616` / `0620`), GLB `product_<id>.glb`. Šroub s válcovou hlavou imbus jsem mezi výsledky hledání „šroub“ + M5/M6 nenašel.

## 4. Díly pro 30×30
- **Úhelník**: produkt **3045**, SKU `2.2.001.08.3030.01` („Úhelníková spojka 30x30“, `.08.` = drážka 8, tedy pro 30×30 je to nativní díl). Katalogový `glb_file` = `product_2895.glb` (188 tr), zdrojový STEP je `webapp/content-files/product_fbx/2895.step` (`3045.step` neexistuje). Vysoká kvalita (2300 tr, kulatý otvor Ø6,5, kuželové zahloubení 90° na Ø12,6): `scripts/stavebnice/zdroje/uhelnik_3045_vysoka_kvalita.glb`, postup `zdroje/priprava_uhelnik_3045.py`. Obálka 29,0 × 28,0 × 29,0 mm.
- **Pant** pro 30×30: **3302** `2.2.003.3030.01` (kovový pant 3030; GLB 9702 tr, obálka 49,6 × 10,8 × 50,3, STEP 243 kB), dále 3642 / 3643 (`2.2.003.3030.05` / `.06`, pant 30×30 pravý / levý, STEP 117 kB), 3211 (tenká řada) a 3219 (plastový 3030). V animaci 40×40 je kovový pant 3325 (`2.2.003.4040.01`, 38,5 × 11,8 × 50,0).
- Dnešní animace 40×40 používá úhelník 3045 i na profilu 40×40; pro 30×30 jde o jeho přirozené použití.

## 5. Kde je v `scripts/stavebnice/build_demo_glb.py` napevno 40×40 (ověřeno čtením kódu)
- Hlavička/docstring ř. 4–6, 19 a argument `--profile` ř. 1016 („GLB profilu 40x40 S10, délka v ose Z, rozsah z v [-1000,0]“), název ve výstupu měření ř. 1030.
- `build()` ř. 690–693: `Y0 = 20.0` (polovina profilu), horní plocha `Y = 40`, strop komory `Y = 34`; ř. 701: osy profilu a délka `X = 0,3·z + 150` (profil 300 mm, `xmin_prof, xmax_prof = -150, 150` ř. 697); GLB profilu musí mít stejnou konvenci jako náš 40×40 (délka v z od −1000 do 0), katalogový `Object_7.glb` má délku v y a nehodí se.
- `measure_slot()` / `slot_polyline()` ř. 372–420: měří skutečný řez, ale indexuje vrcholy drážky podle tvaru S10 (zapuštění ±6,1, krček, komora, 45° zkosení, zvlněné dno); u Light 30×30 přepsat podle skutečného řezu.
- `default_fastenings()` ř. 649–676: produkty 3592 a 3582 (nut.file), úhelník a pant (`part.file`), `hole_approx_xz=(40.0, 12.1)` (otvor pantu 3325), `plate_y_range=(5.5, 7.0)`, `head_zmin=5.2`, délky šroubů, časy a všechny klíče kamery `K(...)` (cíle a poloměry `fit` pro 40×40); konstanty `PART_HEIGHT`, `SCREW_HEIGHT`, `NUT_DROP_HEIGHT` ř. 620–623. `make_extras()` ř. 825 a `anchors()` ř. 878 mají pevné souřadnice kotev a pohledu (`(0, 22, 0)`).
- Generátor je modulární pro další upevnění (README „Jak přidat další díl“), ale rozměry profilu jsou parametrem jen částečně: pro 30×30 je potřeba nahradit `Y0`, měření drážky, polohy děr a kamery.

## 6. Jak se model staví a ověřuje
`python build_demo_glb.py --profile <profil.glb> --katalog /opt/konfigurator/webapp/katalog --out stavebnice-demo.glb [--head csk|cap]` (README `scripts/stavebnice/README.md`). Testy modelu (12 sad: struktura, smyčka, kroky, kotvy, kamera, otočení, průniky, modularita) jsou ve staré pracovní složce agenta v archivu `private-files/archiv/stavebnice_model_pracovni_slozka_2026-10-03.tar.gz` (cesty uvnitř míří do scratchpadu, je potřeba je upravit). Test stránky, pluginu a prvku do mřížky: `scripts/2026-10-03_pripni_cokoli_testy/run_all.sh`. Plugin a stránka berou model z `webapp/pripni-cokoli/stavebnice-demo.glb`; stránka má zkušební parametr `?model=<soubor.glb>` (soubor v `/pripni-cokoli/`), prvek do mřížky zatím jen pevný název (přidat volbu `model` by byla malá změna v `pripni-cokoli-tile.js`).
