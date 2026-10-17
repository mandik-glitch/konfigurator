# Kontrola věrohodnosti tvaru – John v6 – 4932472129 (Box se 2 zásuvkami)

Hodnocený model: `kufriky_john/nahled-modely-v6/modely/4932472129.glb` (obálka 414 × 564 × 363 mm, sedí na katalog). Vlastní model pro toto SKU neexistuje, hodnotí se jen Johnův model proti fotografiím výrobce a katalogu (`kufriky_john/kufriky.csv`). Nic v repu nebylo upraveno; sem se zapisují jen vlastní rendery a čísla.

## Hodnocení: **s výhradami**

Počet (2) a rozložení zásuvek i držadel sedí; tvar těla je ale jednoduchý kvádr bez víka se 10 kapsami, bez volných hliníkových trubek a bez předního soklu s nožkami.

Důvod ve zkratce: hrubá stavba (počet zásuvek, jejich rozložení, jedno červené držadlo na zásuvku, třmen se dvěma dráty, 4 kovové rohové prvky, rozměry) odpovídá fotkám; tvar těla je ale „kvádr s plochými čely“ a chybí řada při pohledu zřetelných detailů (viz tabulka rozdílů). Nelze říct „nevěrohodný“, protože hlavní uspořádání i siluetu (IoU 0,90–0,94 při nezávislé kameře) model dává; nelze říct „věrohodný“, protože víko, boční hliníková madla a spodek vypadají jinak a rozdíly jsou vidět na první pohled.

## Fotografie a srovnání

Zdroj fotografií: web výrobce (`static.milwaukeetool.eu/.../hi/4932472129--Hero_N.jpg`, cNN = Hero_N); fotografie ani jejich kopie nejsou v repu. Dvojice foto | model | překryv jsem pro všechny níže uvedené snímky vytvořil ve scratchpadu a **prohlédl** (Read): ano pro všech 2 snímků.

| foto | stav na fotce | IoU | RMS landmarků (px) | nejdůležitější rozdíly |
|---|---|---|---|---|
| c01 (Hero_1) | 3/4 zleva, třmen (bail) vztyčen | **0.9251** | 11.0 | R1–R7; model pod čelem nemá přední sokl, v místech trubek není průhled (R2, R4) |
| c02 (Hero_2) | 3/4 zleva, třmen sklopen dolů | **0.9234** | 11.8 | R1–R7; třmen sklopen (R5) |

IoU = průnik/sjednocení siluety fotky (práh jasu < 245, bez vyplňování děr) a siluety Johnova modelu z kamery určené jen z fotky (viz Metoda). Hodnoty 0,90–0,94 odpovídají správné hrubé stavbě; zbytek tvoří zjednodušené rohy, sokl a víko (červená/modrá místa v překryvech) i chyba kamery (viz Metoda). Kameru jsem nedofitovával podle obrysu.

## Rozdíly tvar / detail (foto vs. Johnův model)

Velikosti jsou z kamery a ≈ ±5–10 mm (viz Metoda). Závažnost: K = kosmetický, V = viditelný, Z = zásadní.

| č. | foto | rozdíl | velikost | závažnost |
|---|---|---|---|---|
| R1 | všechny | Víko: ve fotce 10 zapuštěných kapes (2 skupiny po 5: 2 malé vzadu, 1 dlouhá uprostřed, 2 malé vpředu), zaoblené a zkosené hrany, na bočních stěnách víka vroubkované madlo; model má plochou desku s 6 **vyvýšenými** obdélníkovými rámečky (2 × 3) a ostrými hranami | 4 kapsy navíc; kapsy ≈ 100–180 × 45–65 mm; zaoblení a zkosení hran víka (neměřeno) | V |
| R2 | všechny | Hliníková boční madla: ve fotce 4 svislé hliníkové trubky ≈ 22 mm široké, ≈ 235 mm dlouhé (z ≈ −126…+110), volně stojící v rohových výřezech těla s průhledem mezi trubkou a tělem (≈ 15–20 mm); model má 4 proužky 4,6 × 4,6 mm délky 276 mm (z −139…+136) přilepené k hraně rohu bez průhledu | průřez 22 vs 4,6 mm; délka +40 mm; střed v ose y ≈ ±266 vs ±280 mm | V až Z (funkční prvek, na fotkách nejvýraznější) |
| R3 | všechny | Čela zásuvek: počet správný; ve fotce jsou čela o ≈ 4–15 mm vyšší s mezerami ≈ 4 mm a obklopená zvýšeným rámem; model má plochá čela se širokými mezerami (10–18 mm), čela užší než rám | viz „Zásuvky“ níže (odchylky hran 7–20 mm) | K až V |
| R4 | všechny (nejvíc c02, c03, čelní c01) | Spodek: ve fotce je tělo ve dně zvednuté (okraj rohových bloků ≈ z −152) a nejníž (z −181,5) sahá jen široký přední sokl s červenými svorkami třmenu; model má plné dno k z ≈ −169,5, čtyři rohové nožky 53 × 72 mm a šest spodních patek uprostřed, přední sokl chybí | 15–30 mm v siluetě dole (modrá/červená oblast v překryvu) | V |
| R5 | všechny (sklopený třmen: 2129/2130 c02, 3189/3190 c03) | Třmen (bail): ve fotce drát ≈ 4–5 mm, svislé dráty ve vzdálenosti ≈ ±63 mm, nahoře ho drží červený zámek 70 × 15 mm na přední hraně víka, dole červené svorky na soklu; na snímcích se sklopeným třmenem je drát položen dolů před sokl. Model: dráty ø 5 mm v ±73,3 mm (≈ 10 mm moc daleko), nahoře jen 2 malé červené kotvy 10 × 13 mm a můstek, červená destička 25 × 37 mm uprostřed víka (ve fotce tam žádná není; červený štítek je ve fotce až v pravé velké kapse), sklopená poloha nelze (uzly nemají osu) | rozteč drátů +10 mm; zámek 70 × 15 vs 2 × 10 × 13 mm | V |
| R6 | všechny | Držadla zásuvek: jedno na zásuvku, vystředěné (správně); ve fotce rýhovaná červená lišta ≈ 190 × 16–20 mm vsazená do tmavého prolisu ≈ 35 mm pod ní, model hladký proužek 180 × 12 mm bez prolisu | −10 mm šířka, −4…−8 mm výška, chybí prolis | K |
| R7 | všechny | Rám kolem čel a rohové šrouby/zesílení: ve fotce plasticky tvarovaný rám se šrouby v rozích víka a těla; model rovné hrany | několik mm | K |
| R8 | c04, c05, c06 (otevřené zásuvky) | Zásuvka: fotka – silná stěna (≈ 8–10 mm), teleskopické kolejnice po straně, mřížka červených přepážek (8–12 přihrádek; přepážky jsou ale vyjímatelné příslušenství); model – tenké stěny, 2 červené přepážky v jedné ose, kolejnice jako 2 drátky, zásuvka bez vodítek (uzly „drawer-N“ nemají osu výsuvu; po vysunutí o ≈ 375 mm se zásuvka odděluje od těla, protože je jen 332 mm dlouhá) | přepážky 2 vs 8–12; výsuv ≈ 375 mm (úplný) a ≈ 240 mm (částečný) odečteno z fotek | V (jen u otevřených stavů; přepážky K) |
| R9 | c02/c03 (3/4) | Boky a záda: fotka – boční stěna s lisovanými žebry a výrazným stupněm u soklu; model – plocha s několika tenkými žebry | několik mm | K |

## Zásuvky: počet, výška, rozložení, držadla

2 zásuvky, každá ve fotce ≈ polovina výšky těla. Model: 2 čela po 132 mm (z +5,8…+137,8 a −142,8…−10,8), mezera 16,6 mm. Fotka (c01/c02, odečteno z kamery, ±10 mm): mezera mezi čely je v prostředku výšky (z ≈ +8…+26 mm), spodní čelo končí ≈ −148 mm, horní čelo začíná výš (≈ +150 mm). Počet a rozložení (2 stejné zásuvky nad sebou) sedí; polohy hran se liší o ≈ 10–20 mm (u tohoto SKU nejistější, protože pro něj nemáme čelní fotku a výška kamery je závislá na odhadu z rohů).

Držadla: 1 červené držadlo na každou zásuvku, vystředěné v ose y (fotka i model) – sedí.

## Metoda a spolehlivost kamery (poctivě)

- Kamera pro každou fotku z ručně/poloautomaticky změřených **obrysových rohů fotky** (levý horní roh víka, zadní horní roh, pravý horní roh víka, spodní rohy podstavy – vrcholy konvexního obalu siluety) a známé obálky 414 × 564 mm (nástroj `kufry_hilti/nastroje/kalibruj.py`, Levenberg–Marquardt, 6 parametrů: azimut, elevace, vzdálenost, fov, hlavní bod). Tvar Johnova modelu se do kamery **nepromítl** (žádné dofitování podle obrysu; IoU je tedy nezávislá míra).
- Nejistoty: (1) rohy jsou zaoblené, odečtení ±3–5 px (≈ ±2–3 mm); (2) z-úroveň rohů víka/podstavy není v katalogu – zkusil jsem 2 hypotézy (víko +172 / dno −181,5 mm, nebo +167 / −152 mm; druhá plyne z čelní fotky Hero_1 u 3189/3190, kde se zdvih rohového bloku nad nejnižším soklem dá změřit) a pro každou fotku vzal tu s menším RMS landmarků; záměna hypotéz mění IoU o ≈ 0,01; (3) fov je z rohů špatně určený (17–31°) a vzdálenost s ním koreluje; u čelních snímků (c01 3189/3190) jsem fixoval azimut 0° (symetrie fotky) a **fov 24° jen jako předpoklad**; (4) RMS landmarků 3–12 px (≈ 2–7 mm) je v tabulce; kvůli tomu IoU má chybu ≈ ±0,01–0,02 a rozdíly menší než ≈ 6 mm nejsou z fotek interpretovatelné.
- Poloha hran zásuvek je odečtena z jasových skoků ve sloupci fotky promítnutém kamerou na rovinu čel (x = 198 mm); u 2/3-zásuvkových boxů nemáme čelní fotku, takže tam platí větší nejistota (± 10–15 mm).
- Otevřené zásuvky (Hero_4–6): vysunutí odečteno z polohy levého horního rohu čela zásuvky na fotce (ne z obrysu): úplný výsuv ≈ 369–380 mm, částečný ≈ 240 mm (konzistentní ve všech fotkách napříč kamerami). Model se zásuvkami nepohybuje; pro srovnání jsem posunul uzly `drawer-N` o tuto hodnotu v +X (jen hypotetická poloha, John výsuv nenavrhl).
- Stejná kamera pro SKU 2129 a 2130 (Hero_1 a Hero_2 mají shodné siluety víka, IoU masek 0,998/0,999); pro 3189 a 3190 jsou kamery spočítány zvlášť.

## Co z fotek NELZE posoudit (neověřeno)

- Zadní stěna, spodní plocha a vnitřek víka, tloušťky stěn, poloměry zaoblení, hloubka kapes ve víku (jen šikmé pohledy shora).
- Pravá strana těla je vidět jen zešikma; levá strana a záda nejsou vidět.
- Skutečná délka zásuvky a vedení v těle (vidět jen vysunutou část u Hero_4–6).
- Přesné rozměry hliníkových trubek, svorek a zámku (měřeno z jednoho pohledu, ±5 mm).
- Mřížka přepážek v zásuvkách je vyjímatelné příslušenství, tvar zásuvky bez nich ověřitelný jen u 3190 Hero_5.
- Další fotografie (feature / aplikační) jsem nestahoval ani nehodnotil; seznam jejich URL je v metadatech GLB (`photo_sources`).

## Doporučení

1. Víko: zapuštěných 10 kapes (2 × 5, dlouhé střední) místo 6 vyvýšených rámečků, zaoblit horní hrany, přidat boční madlo víka.
2. Rohové hliníkové trubky: průřez ≈ 22 mm, délka ≈ 235 mm (z −126…+110), s volným průhledem k tělu; polohu zkontrolovat proti Hero_1 (čelní).
3. Spodek: zvednout dno těla na z ≈ −152 a nejníž (−181,5) nechat jen široký přední sokl; odstranit rohové nožky.
4. Čela zásuvek: snížit mezery na ≈ 4 mm a upravit rozteč (4 zásuvky 72 mm; 2+1 podle měření výše); držadla do prolisu, výška 16–20 mm.
5. Třmen: dráty ±63 mm, červený zámek 70 × 15 mm na víku, sklopná poloha (osa u soklu).
6. Zásuvky: výsuv po ose x (≈ 375 mm), silnější stěna, kolejnice; přepážky jako volitelné příslušenství.

## Soubory

- `cNN_model.png` – render Johnova GLB z kamery fotky (bez fotky); `cNN_kamera.json` – kamera (+ výsuv zásuvek); `cNN_landmarky.json` – změřené landmarky (pixely) a zbytky; `iou.json` – IoU a počty pixelů rozdílu.
- Nástroje (mimo repo): scratchpad `k6/` (lmcam.py, rend.mjs, cmp.py, sil.py, stranka.html – kopie `kufriky_cloud/render/stranka.html` s podporou 16bit indexů GLB, protože původní stránka Johnův GLB nenačte).
