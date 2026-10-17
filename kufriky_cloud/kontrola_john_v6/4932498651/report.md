# Kontrola věrohodnosti tvaru: 4932498651 Pojízdný box s čelní zásuvkou (Johnův model v6)

Model: `kufriky_john/nahled-modely-v6/modely/4932498651.glb` (obálka 480 × 610 × 550 mm, sedí). Hodnoceno jen proti fotografiím výrobce a katalogu. Nic v repu nebylo upraveno, jen vznikla tato složka.
Fotografie (jen URL, kopie v repu nejsou):
- c01 = Hero_1 `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932498651--Hero_1.jpg?width=1200`
- c02 = Hero_2 `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932498651--Hero_2.jpg?width=1200`

Soubory: `c01_render.png`, `c02_render.png` (render modelu z odhadnuté kamery), `c01_kamera.json`, `c02_kamera.json` (kamera, ruční body, IoU), nástroje v `../nastroje_4932498651_4932478162_4932501784/`.

## Hodnocení: S VÝHRADAMI
Silueta, rozložení a hlavní prvky (zásuvka v čele, dvě kola vzadu, boční rukojeti, teleskopické vedení vzadu, horní víko) odpovídají fotkám. Povrch je ale velmi zjednodušený (hladké čelo, ploché „lišty“ místo rukojetí, chybí hliníkové rohové tyče, zásuvka bez žeber a kolečka) a vysunutou polohu madla model nemá. Pro zákazníka je to rozpoznatelný, ale hrubý model.

## Tabulka foto | IoU | nejdůležitější rozdíly
| foto | kamera | IoU | nejdůležitější rozdíly |
|---|---|---|---|
| c01 (zavřená zásuvka, madlo vytažené, pohled zleva-zepředu, az ≈ 40°) | z 6 ručních bodů + apriorní ohnisko, slabě určená | 0.943 pod řádkem y=600 px (bez madla); 0.664 celé | vytažené teleskopické madlo v modelu není (viz bod 1), čelo hladké, hliníková tyč ≈ 5 mm místo ≈ 25 mm, boční rukojeť plochý rámeček |
| c02 (zásuvka vysunutá, madlo zasunuté, az ≈ 28°) | DOFITOVÁNO podle obrysu se zásuvkou posunutou o 300 mm; IoU NENÍ důkaz | 0.947 | zásuvka hladká bez žeber, bez kolečka a bez přepážek ve stěnách, červené úchopy jen tenké pásky |

Kamera c01: ruční body (rohy víka, spodní rohy, náboj kola, spodek kola), neznámé souřadnice (šířka těla, osa kola) s apriorním rozptylem, ohnisko 18 ± 5° převzaté z kalibrace XL fotek stejné série. Reprojekční chyby ručních bodů 0.4 až 21.8 px (rohy víka vzadu 21.8 px), hlavní bod se odchýlil na cy ≈ 830 px. Kamera c01 je tedy jen hrubý odhad; IoU 0.943 bere jako orientační, ne jako důkaz. Kamera c02: pokus ze 4 ručních bodů vyšel nedourčený (az 20°, el 12°, neodpovídá pohledu), zamítnut; použita kamera dofitovaná podle obrysu s ručně zadaným posunem zásuvky (zkoušeno 200/300/400 mm, IoU 0.923/0.949/0.955; skutečný zdvih nelze z fotky změřit).

## Konkrétní rozdíly (prohlédnuté dvojice foto | model | překryv: c01 celek + výřez těla, c02 celek)
Odhady mm = pixely / (≈0.93 px/mm na c01, ≈1.7 px/mm na c02), zaokrouhleně.
1. c01, teleskopické madlo: na fotce vytažené, výška nad víkem ≈ 600 mm, dvě svislé trubky a červená příčka s úchopem (≈ 250 × 40 mm, šířka přibližně jako v modelu), uprostřed ještě červená vodicí spona. Model má jen zasunutou polohu (vedení v zadní stěně a červená příčka 266 × 18 mm na horní zadní hraně). Zásadní jen jako chybějící pohled; zasunutou polohu potvrzuje c02, kde červená příčka na zadní hraně víka sedí (šířka ≈ 75 až 80 % šířky víka v obou). Závažnost: viditelný (stav neodpovídá c01, ale model je výslovně v přepravní poloze).
2. c01+c02, čelo (zásuvka): fotka má stupňovité čelo se zamykací červenou lištou nahoře uprostřed (≈ 60 × 55 mm, vybrání pod ní), červenou rukojetí s prohlubní (≈ 120 × 35 mm), velké logo, žebrování a spodní lištu s kolejnicemi pro spojení. Model: hladká deska, červená lišta ≈ 164 × 12 mm bez prohlubně, malé červené očko ≈ 30 mm. Viditelný.
3. c01+c02, hliníkové rohové tyče: na fotce široká hliníková leštěná tyč (≈ 22 px ≈ 25 mm) na přední hraně a vzadu, s černými rohovými patkami. V modelu roh-kov ≈ 5 mm tenká lišta zapuštěná v rohu, v renderu jen tenká světlá čárka. Viditelný.
4. c01+c02, boční rukojeť: fotka velká červeno-černá rukojeť v zapuštěném pouzdru (≈ 160 × 120 mm, vyčnívá ≈ 40 mm). Model: plochý červený obdélník ≈ 168 × 34 mm, vystupuje 5 mm. Viditelný.
5. c01+c02, víko: fotka víko přesahuje tělo (okraj, zkosení, ≈ 10 kapes pro moduly, červený štítek). Model: plochá deska s 4 mělkými rámečky/drážkami. Viditelný (kosmetický při pohledu zdálky).
6. c01+c02, kolo: průměr ≈ 228 mm a poloha dozadu na boku sedí (překryv kruhu). Fotka má pryžovou dezénovou pneumatiku, 10 širokých paprsků a vyčnívající matici osy (≈ 25 px); model je prakticky hladký černý kotouč s tmavými paprsky a malou osou. Tvar a poloha sedí; detail kosmetický.
7. c02, vysunutá zásuvka: fotka je otevřená nádoba s žebrovanou stěnou, okrajem s výřezy, třemi svislými štěrbinami na boku, červenou zámkovou lištou nahoře uprostřed a dvěma kolečky ve spodních rozích (≈ 55 × 35 px ≈ 30 × 20 mm). Model: hladký kvádr bez kolečka, bez štěrbin. Viditelný. Výška a šířka zásuvky vypadají shodně (překryv obrysu).
8. c01, spodek těla: fotka má zalomený spodní okraj s patkami a výřezy; model rovné dno s malými patkami uvnitř obrysu. Obrys modelu přesahuje fotku vlevo dole o ≈ 15 px (≈ 15 mm). Kosmetický až viditelný.
9. c01, horní obrys: obrys modelu přesahuje fotku v levém horním rohu víka o ≈ 15 až 25 px (≈ 15 až 25 mm; model má ostrý kvádr, fotka zkosený roh víka). Kosmetický.

## Co nelze z fotek posoudit (neověřeno)
Tloušťky stěn, poloměry, úkosy (nejsou kótované); zadní strana, spodek a levá strana (nejsou vidět); vnitřek zásuvky a skutečný zdvih vysunutí; mechanika a zdvih teleskopického madla; průměr vnějších rozměrů (katalog uvádí rozpor 665 × 570 × 480 vs. 550 × 610 × 480; fotka nemá měřítko, nerozhoduje); vzdálená strana kol (je skrytá).

## Doporučení
Model je použitelný pro rozměrovou představu a rozpoznání typu. Pro věrohodnější vzhled: (1) doplnit pohled s vytaženým madlem nebo animaci vysunutí, (2) hliníkové tyče a rohové patky dát na plnou šířku ≈ 25 mm a vytáhnout je z těla, (3) boční rukojeť jako zapuštěné pouzdro s úchopem, (4) čelo zásuvky s vybráním pro rukojeť a zamykací lištou, (5) kolečka na zásuvce a žebra, (6) víko s přesahem a zkosením.

Pozn.: render je světlejší šedý než skutečná černá (osvětlení prohlížeče), barvu jsem nehodnotil.
