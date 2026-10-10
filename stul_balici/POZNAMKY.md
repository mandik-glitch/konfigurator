# Poznámky k modelu Stůl balení LIDL (prototyp II)

Model je sestava dílů z katalogu (profil 40x40, laminodesky, rohové spojky, patky, úhelníky, LED) ve formátu `custom_shapes.data`, doplněná zástupnými díly pro to, co v katalogu není. Vznikl z kót výkresu (4 listy) a je změřený na reálných GLB dílech. Všechna čísla níže pocházejí z `vystup/validace.txt`, `vystup/koty.json` a `vystup/kusovnik.md`.

## 1. Rozpory a nejasnosti výkresu (nic z toho jsem neupravoval podle domněnky)

1. **Profil.** Výkres: ITEM 8 40x40 L (drážka 8 mm). Model: náš profil 40x40 SuperLight S10 (`Object_11`, SKU 1.1.10.040040.03, drážka 10 mm) - na tom se s Robertem domluvil Karel. Rozměr 40x40 je stejný, drážka se liší (jiné T-matice a šrouby, jiná hloubka zasunutí desky do drážky).
2. **List 3 - kóty v závorkách** (2020, 1450, 702, 80, 662, 590, 720, 6, 150, 670) se místy liší od kót listu 1. 2020 = 2100 - 80 a 702 = 782 - 80 ukazují na jinou základnu měření: spodek nohy 80 mm nad podlahou místo 46 mm na listu 1. Model používá nezávorkové kóty listu 1 (spodek nohy 46 mm, patka 3283 zasunutá 33 mm). Kóty (720) a (1450) i (670) se v modelu shodují (světlá hloubka mezi nohami 720, dolní hrana zadní příčky 1450, pravá rozpona 670). Kóty (662), (590) a 6 jsem na výkrese nedokázal jednoznačně přiřadit a nejsou v modelu zakótované (590 = světlá šířka rámu válečkové dráhy, rám dráhy je v modelu zjednodušený).
3. **Štítek spodní police** ("užitná plocha 350x800, nosnost 20 kg") ukazuje na spodní desku střední sekce. Na výkrese je ale ve střední sekci (570 mm široké) a bokorys ji ukazuje 650 mm hlubokou (kóta 650 + 150). Model: deska 570 x 650 mm, horní plocha 104 mm (z kóty 470 pod střední policí). Štítek a geometrie si neodpovídají.
4. **Hloubka 800 u polic 350x800 a 570x800.** Police leží mezi nohami (světlá hloubka 720); model jim dává hloubku 800 (líc v líc s vnějšími líci nohou, ve směru X jsou mezi nohami, takže nic nekoliduje). Boční pohled kresbou 800 přímo nepotvrzuje, deskami jsou skryté za nohami.
5. **Kóta 650 / 150 v bokoryse** není "rám 650 + přesah 150", ale hloubka spodní desky 650 a volný přední odstup 150.
6. **Pracovní deska** je 610 x 800 (kóty 430 | 610 | 710 v půdoryse: deska leží na nohách B..C a překrývá horní čelo nohy C). Střední police (592) je 570 x 800.
7. **Vyšší úrovně příček bez kóty** (odečteno z výkresu s přesností asi +-3 mm, parametry `y_R1`, `y_R2` ve specifikaci): kolejnice kování 370..410, rám válečkové dráhy 690..730, čelní plech 120 mm vysoký nad rámem (730..850).

## 2. Co je v modelu zjednodušeno, zástupné nebo NEOVĚŘENO

- **Válečkové dráhy 60x24 D15** (11 kusů, 782 mm, mezera 1,5 mm, horní plocha 754 mm): ZÁSTUPNĚ kvádry. Nejsou v katalogu - potřebují ID karty z DB. Počet 11 a rozměry odpovídají půdorysu; výška horní plochy (754 mm, tedy 46 mm pod stolem) je odhad, výkres ji nekótuje.
- **Čelní plech dráhy s oválným úchopem**: ZÁSTUPNĚ plochý kvádr 670 x 120 x 6.
- **Polohovací kování cca 10 poloh** (2 kusy), **pryžové dorazy**, **kolejnice kování**: kování ZÁSTUPNĚ svislé kvádry, dorazy nejsou; kolejnice je profil 40x40 (z katalogu). Skutečné vedení, úhly ani 10 poloh nejsou modelovány.
- **Rameno monitoru** (sloupek 500 mm je skutečný profil z katalogu; upínací patka, vodorovné rameno a hlava VESA 100x100 jsou ZÁSTUPNĚ kvádry; vysunutí 306 / 250 mm je dodrženo, kloubová mechanika ne). Výška ramene (~1400 mm) je odečtena z výkresu.
- **Vypínač stmívací zvonkový**: ZÁSTUPNĚ kvádr 40 x 150 x 60 u levé strany střední sekce.
- **LED osvětlení**: karta `product_4929` (SKU LED1200). GLB této karty NENÍ v checkoutu repa (`webapp/katalog/`). Poloha je spočtená z dokumentovaného středu obálky (stejný jako u `product_5359`, který v repu je) a z orientace v šabloně generátoru stolu; **neověřeno proti skutečnému GLB karty**. V náhledu je to náhradní kvádr 1247 x 81 x 85 mm. Výkres ukazuje svítidlo dlouhé asi 1212 mm a hluboké asi 64 mm, katalogové je 1247 x 85 (nesedí na 1 mm - rozdíl katalog/výkres).
- **Laminodeska 18 mm** (`product_4933`, SKU Laminodeska.SEDA.18): GLB karty také není v repu. Počítám podle kontraktu v `api/stul_hpolice.py` (1000 x 1000 x 18, vystředěno, tloušťka v lokální Z, otočení -90 stupňů kolem X, měřítko x/1000, y/1000, 1). **Neověřeno proti skutečnému GLB karty** - při vložení do Kontrolní scény zkontrolovat, že desky sedí.
- **Úhelníky držáků polic** (16 ks `product_3207`, Úhelníková spojka 40x40, SKU 2.2.001.10.4040.01): jako držák desky je použil generátor (`api/stul_hpolice.py`); výkres ukazuje plechové úhelníky, které se tvarem mohou lišit. Poloha podle `_uhelnik` (roh pod deskou na líci nohy).
- **Rohové spojky** (65 ks `product_3176`, 2.2.001.10.4040.33): jedna na každý T-spoj, poloha odvozená ze šablony generátoru stolu system 40 (20 z 20 spojek šablony má stejný zámek 3,43 mm). **Čtyři spoje jsou BEZ rohové spojky** (`MB-zadni` na obou koncích a `MB-bok-B` na obou koncích): spodní rám střední sekce leží 46..86 mm nad podlahou, těsně pod ním je deska a 34 mm pod příčkou levé sekce, spojka (37 mm) se tam nevejde (kolize s deskou 18 mm, resp. 3 mm do příčky 120..160). Fyzicky to musí být šroub přes čelo (nebo jiná poloha příček) - **rozhodnutí na konstruktérovi**. Na výkrese jsou rohové úhelníky u příček vidět jen ve vyšších úrovních.
- **Úrovně příček střední sekce** (46..86 mm, deska nahoře 104 mm) vycházejí z kót 46, 470 a 592; boční příčky `MB-bok-B` a `MB-bok-C` a kolejnice `MB-kolejnice` (z=610..650) jsem doplnil jako nutné nosníky pro desku 650 mm hlubokou (výkres je zřetelně nekóttuje).
- **Rám válečkové dráhy:** modelován jen jako rám 670 mm (zadní a přední příčka v úrovni 690..730) bez vlastních bočnic (kóta 590); dráhy leží na přední a zadní příčce.
- **Rohové výztuhy (trojúhelníkové plechy)** na horním rámu a zadní stěně, **tvar horního plechu s oblouky a drážkou úchopu**, **zaoblení plechu**, otvory v deskách, kabeláž LED a svorky nejsou modelovány.
- **Boční dosed posuvných profilů** (`posuvny-1`, `posuvny-2`, 200 mm) a sloupku ramene monitoru na přední stěnu zadních příček: profily leží stěnou na stěně (T-matice), nejde o čelní spoj. Účtují se jako 2 spoje na profil (6 spojů celkem), jinak nelze splnit součet joint_count = dotyky.

## 3. Které pravidlo spojů jsem použil u kterého typu spoje

(zdroj: `VLASTNOSTI_PROFILU.md` - nadřazená pravidla, `PRAVIDLA_SPOJU.md`, skill `3d-scena-spoje`; všude se díly určují podle `part_id`, nikdy podle názvu)

| typ spoje v modelu | počet | použité pravidlo | jak ověřeno |
|---|---:|---|---|
| příčka mezi dvěma nohami (zadní, přední, boční příčky všech úrovní, příčky zadní stěny, přední/zadní příčka horního rámu) | 62 | **T-styl (průchozí) spoj**: připojovaný profil se zkrátí o CELOU šířku průchozího, délka = světlé rozpětí; čelo celou plochou na stěně nohy | délka = světlé rozpětí měřené z Box3 u 33 příček; `touchReport` + `isValidFlushTouch` u všech 69 spojů, čelo 40x40 plně kryté |
| kolejnice mezi dvěma bočními příčkami (`MB-kolejnice`, `R1-kolejnice`) | 4 | T-styl: průchozí = boční příčka (z 40..760 mm), kolejnice zkrácená o celou šířku | totéž |
| noha pod rámem horního patra (`noha-AZ`, `noha-DZ` pod bočnicí, `noha-BZ` pod zadní příčkou) | 3 | **čelo na stěnu průchozího nosníku, celá plocha čela 40x40 uvnitř stěny nosníku** (žádné zanoření, žádné částečně kryté čelo); jediná výjimka z konvence "noha má volné čelo nahoře" - výkres horní rám takto nese (list 1 a 2) | `touchReport` y: gap 0 / overlap 0, x a z plný překryv 40 |
| spodní konce všech 8 nohou | 8 | **noha se zespoda neuzavírá profilem**, volné čelo, osazeno patkou 3283 (zásun 33 mm, základna y = 0) | dotyk dole = žádný; patka měřena z vrcholů mesh |
| horní konce 5 nohou (`noha-CZ`, `noha-AP`, `noha-BP`, `noha-CP`, `noha-DP`) | 5 | volné čelo nahoře (stejná konvence jako dole); konec lícuje s horní plochou příčky, žádný profil ho nezakrývá | měřeno |
| posuvné profily, sloupek ramene na stěnu zadních příček | 6 | plocha na ploše, žádný průnik; účtováno jako spoj (T-matice) | `touchReport`: jedna osa flush, dvě plný překryv |
| rohová spojka 3176 | 65 | **zobáček spojky zapadá do drážky obou profilů** (3,43 mm), šířka 37 mm vystředěná na osu drážky (shodně se šablonou generátoru) | zámek 3,43 mm naměřen u 65 z 65; mesh test sám zámek jako kolizi nehlásí (profil v GLB je plný kvádr bez drážky) |
| desky, úhelníky, patky | - | nejsou spojem profil-profil; desky leží na horních plochách příček a lícují s nohou, úhelník líc na líc s nohou pod deskou | Box3 + mesh test, 0 nechtěných kolizí |

Pivot: pozice každého dílu se počítá ze STŘEDU OBÁLKY změřeného z GLB (`position = střed - R*(měřítko * střed obálky)`), nikdy z `position +- size/2`. Po složení se Box3 každého profilu porovná s požadovaným rozsahem (rozdíl <= 0,01 mm).

## 4. Rozpory dokumentace a toho, co vidím na modelu (neupraveno podle domněnky)

1. **"Noha má volné čelo shora i zdola"** (VLASTNOSTI_PROFILU.md) vs. výkres: tři zadní nohy (A, B, D) jsou nahoře zakryté rámem horního patra. Použil jsem výkres a ponechal jsem to označené v `validace.txt` (oddíl 2); zda to Robert chce jinak (nohy projíždějící horním rámem), je rozhodnutí na něm.
2. **Čtyři spoje bez rohové spojky** (viz výše) - pravidla o spojích nic neříkají o případu, kdy se spojka nevejde.
3. **Profil v GLB nemá drážku** (plný kvadr 40x40x1000), proto mesh test nevidí zámek spojky; `validace.txt` ho měří přes Box3 (3,43 mm). Odpovídá poznámce v `PROFILY_KATALOG.md`.
4. **Validátor účetnictví** `scripts/2026-08-19_bookkeeping_validator.js` má natvrdo cestu `/opt/konfigurator/webapp/katalog` a počítá VŠECHNY plošné dotyky (i deska na příčce, úhelník na noze) jako spoje. Pustil jsem jeho kopii s opravenou cestou na podmnožině profilů (46 dílů, 75 dotyků, součet joint_count 75): všechny invarianty I1-I4 sedí. Na celé sestavě skončí `PRESKOCENO` (GLB karty 4933 a 4929 nejsou v repu); i s nimi by hlásil dosedy desek a úhelníků jako chybějící spoje (deska x profil 27, úhelník x profil 16, úhelník x deska 16), protože nejsou účtované.
5. **Zámek spojek a "kolize":** knihovna `2026-09-11_mesh_kolize_lib.js` hlásí 8 kolizí - všech 8 jsou závity patek v nohách (očekávané, patka zasunutá 33 mm). 0 nechtěných.

## 5. Kusovník

Generováno ze specifikace (sha 2e3cdb88d742). Díly se identifikují part_id / SKU, ne názvem.

## Profily (Object_11, SKU 1.1.10.040040.03, Profil 40x40 SuperLight S10 (drážka 10 mm))

| délka (mm) | ks | profily (id) |
|---:|---:|---|
| 2014 | 3 | noha-AZ, noha-BZ, noha-DZ |
| 1670 | 2 | horni-zadni, horni-predni |
| 1444 | 2 | noha-AP, noha-BP |
| 1280 | 2 | zed-spodni, zed-horni |
| 736 | 3 | noha-CZ, noha-CP, noha-DP |
| 720 | 13 | LB-leva, LB-prava, LM-leva, LM-prava, LT-leva, LT-prava, MB-bok-B, MB-bok-C, MM-prava, R0-prava, R1-bok-C, R1-bok-D, D-bok-stul |
| 670 | 6 | R0-zadni, R0-predni, R1-predni, R1-kolejnice, R2-zadni, R2-predni |
| 600 | 2 | horni-bok-L, horni-bok-P |
| 570 | 4 | MB-zadni, MB-kolejnice, MM-zadni, MM-predni |
| 500 | 1 | rameno-sloup |
| 350 | 6 | LB-zadni, LB-predni, LM-zadni, LM-predni, LT-zadni, LT-predni |
| 200 | 2 | posuvny-1, posuvny-2 |
| **celkem** | **46** | 36898 mm (36.90 m) |

## Desky (product_4933, SKU Laminodeska.SEDA.18, Laminovaná dřevotříska šedá 18 mm)

| deska | rozměr X x Z (mm) | tl. (mm) | plocha (m2) |
|---|---:|---:|---:|
| police-1 | 350 x 800 | 18 | 0.28 |
| police-2 | 350 x 800 | 18 | 0.28 |
| police-3 | 350 x 800 | 18 | 0.28 |
| police-S | 570 x 800 | 18 | 0.456 |
| deska-spodni | 570 x 650 | 18 | 0.371 |
| deska-stolu | 610 x 800 | 18 | 0.488 |
| **celkem** | | | **2.155** |

## Příslušenství z katalogu

| part_id | SKU | název | ks |
|---|---|---|---:|
| product_3176 | 2.2.001.10.4040.33 | 40x40 Rohová spojka | 65 |
| product_3283 | 2.3.002.1050 | Vyrovnávací šroubovací patka M10 | 8 |
| product_3207 | 2.2.001.10.4040.01 | Úhelníková spojka 40x40 (držák desky) | 16 |
| product_4929 | LED1200 | Osvětlení LED 1,2 m 33W 3960lm | 1 |

Spojů profilů: 69 T/čelních + 6 bočních dosedů (posuvné profily / sloupek ramene). Rohových spojek 3176: 65; spoje BEZ rohové spojky (šroub přes čelo): MB-bok-B -> noha-BZ, MB-zadni -> noha-BZ, MB-zadni -> noha-CZ, MB-bok-B -> noha-BP.

## Zástupné díly (NEJSOU v katalogu - potřebují ID z DB)

| id | druh | název | rozměr (mm) |
|---|---|---|---|
| valecka-draha-1 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-2 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-3 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-4 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-5 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-6 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-7 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-8 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-9 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-10 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| valecka-draha-11 | zastupne-draha | Válečková dráha 60x24 D15 (zástupně) | 59.545 x 24 x 782 |
| celni-desticka | zastupne-plech | Čelní plech válečkové dráhy s úchopem (zástupně) | 670 x 120 x 6 |
| kovani-L | zastupne-kovani | Polohovací kování cca 10 poloh - levé (zástupně) | 30 x 320 x 40 |
| kovani-P | zastupne-kovani | Polohovací kování cca 10 poloh - pravé (zástupně) | 30 x 320 x 40 |
| rameno-podstava | zastupne-rameno | Rameno monitoru - upínací patka na sloupku (zástupně) | 30 x 40 x 16 |
| rameno-vodorovne | zastupne-rameno | Rameno monitoru otočné - vodorovné rameno (zástupně) | 20 x 20 x 244 |
| rameno-hlava | zastupne-rameno | Rameno monitoru - hlava VESA 100x100 (zástupně) | 100 x 100 x 6 |
| vypinac | zastupne-vypinac | Vypínač stmívací zvonkový (zástupně) | 40 x 150 x 60 |

## 6. Kóty z výkresu x naměřeno v sestavě

| kóta z výkresu | výkres (mm) | naměřeno (mm) | rozdíl |
|---|---:|---:|---:|
| celková šířka (list 1, půdorys) | 1750 | 1750 | +0.000 |
| celková hloubka (list 1, půdorys/bokorys) | 800 | 800 | +0.000 |
| celková výška od podlahy (list 1) | 2100 | 2100 | +0.000 |
| světlá rozpona levá sekce | 350 | 350 | +0.000 |
| světlá rozpona střední sekce | 570 | 570 | +0.000 |
| světlá rozpona pravá sekce | 670 | 670 | +0.000 |
| půdorys 430 (A + levá sekce + B) | 430 | 430 | +0.000 |
| půdorys 610 (deska stolu B..C vč. nohy C) | 610 | 610 | +0.000 |
| půdorys 710 (pravá sekce vč. nohy D) | 710 | 710 | +0.000 |
| výška police 1 (horní plocha) | 1050 | 1050 | +0.000 |
| výška police 2 | 1218 | 1218 | +0.000 |
| výška police 3 | 1386 | 1386 | +0.000 |
| volná výška mezi policemi 1-2 (150) | 150 | 150 | +0.000 |
| volná výška mezi policemi 2-3 (150) | 150 | 150 | +0.000 |
| výška střední police 570x800 (592) | 592 | 592 | +0.000 |
| horní plocha pracovní desky (800) | 800 | 800 | +0.000 |
| světlá výška nad spodní deskou (470) | 470 | 470 | +0.000 |
| volná výška pod příčkou stolu (150) | 150 | 150 | +0.000 |
| hloubka spodní desky (650) | 650 | 650 | +0.000 |
| přední odstup spodní desky (150) | 150 | 150 | +0.000 |
| horní hrana skříně / zadních příček (1490) | 1490 | 1490 | +0.000 |
| dolní hrana zadní příčky (1450) | 1450 | 1450 | +0.000 |
| od spodku horního rámu po horní hranu příčky (570) | 570 | 570 | +0.000 |
| rozestup zadních příček (200) | 200 | 200 | +0.000 |
| od dolní příčky po desku stolu (650 - stavitelné) | 650 | 650 | +0.000 |
| od spodku horního rámu po desku stolu (1260) | 1260 | 1260 | +0.000 |
| sloupek ramene monitoru (500 - stavitelné) | 500 | 500 | +0.000 |
| světlá šířka zadní stěny B..D (1280) | 1280 | 1280 | +0.000 |
| délka přední/zadní příčky horního rámu (1670) | 1670 | 1670 | +0.000 |
| hloubka horního rámu (600) | 600 | 600 | +0.000 |
| spodek nohy nad podlahou (46) | 46 | 46 | +0.000 |
| spodek nejnižší příčky L/P sekce nad podlahou (120) | 120 | 120 | +0.000 |
| světlá hloubka mezi nohami (720, list 3) | 720 | 720 | +0.000 |
| délka válečkové dráhy (782) | 782 | 782 | +0.000 |
| vysunutí ramene monitoru od líce zadní nohy (306) | 306 | 306 | +0.000 |
| vysunutí ramene od podstavy (250) | 250 | 250 | +0.000 |

Výsledek: 36 kót porovnáno, všechny se shodují na 0,01 mm.

## 7. Oprava po otevření ve scéně (bot9, 2026-10-10)
- Vlastní tvar **#592** je zapsaný v DB. Laminodesky `product_4933` byly v první verzi posunuté doprava: jejich GLB nemá střed v počátku, ale v (4268; 881; 9,8) mm. Bot9 polohu přepočítal ze skutečného GLB přímo v záznamu #592; Robert a bot8 potvrdili, že police sedí. **Soubory v `vystup/` (včetně `custom_shape_data.json`) tuto opravu NEOBSAHUJÍ** – při dalším generování z `stul_balici_spec.json` je potřeba polohu 4933 počítat ze skutečného středu GLB.
- LED `product_4929` měla polohu správně.
- Žlutá barva profilů ve scéně byla barva karty v katalogu (`cfg_dily.Object_11.color_hex`), data tvaru byla v pořádku; bot8 po Robertově OK vrátil standardní hliník.
- Poučení: střed obálky dílu vždy MĚŘIT z GLB v katalogu, nepředpokládat vystředěný.
