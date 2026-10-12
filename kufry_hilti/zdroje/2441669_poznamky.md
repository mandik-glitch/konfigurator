# Hilti ProKit PKC 37-O (2441669) - poznámky k modelu

Model: `kufr_2441669.mjs` (+ `p2441669_zaklad.mjs`, `p2441669_telo.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2441669` → `modely/2441669.glb` (72 dílů, ~5 000 trojúhelníků, obálka 378 × 545 × 279 mm, odchylka 0/0/0 mm, střed 0/0/0). Souřadnice: X = hloubka (čelo s logem do +X), Y = délka, Z = výška, počátek ve středu obálky. Katalog: 378 × 545 × 279 mm, vnitřní 288 × 498 × 259 mm, 3,54 kg.

## Je to přepravka BEZ víka
Podle fotografií c01-c03 je to **otevřená přepravka bez víka** (nahoře široký lem, dutina dokořán, žádné panty ani západky na lemu); „-O“ v typu a název „Přepravka“ to potvrzují (z názvu soubor sám jistotu nedává - rozhodují fotografie). Model je proto jediná skupina `telo`, **žádný pohyblivý uzel, žádné víko**. Zavřená verze neexistuje. Dělicí příčka (černá, ve fotografii c02) **není modelována** - není jasné, zda je součástí dodávky (c03 stejný záběr ji nemá).

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL v `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L158745, 800 × 410) | přímý čelní pohled na dlouhou stranu, těsně oříznutý na obrys | měření čela (800 px = 545 mm, 409,6 px = 279 mm, stejné měřítko v obou směrech), porovnání `celo` |
| c02 (L160241, 792 × 800) | šikmo shora, s dělicí příčkou | kamera z 6 ručních bodů + obrys, porovnání `otevreny-c02` |
| c03 (L160242, 800 × 759) | **stejný záběr jako c02**, s kótami výrobce, bez příčky | kontrola rozměrů, porovnání `otevreny-c03` (maska podle červené barvy, aby šipky/popisky nekazily obrys) |
| c04 (L160116) | aplikační snímek (stavba, zavazadlový vozík, zavřené boxy) | nepoužitelné k měření, tuto přepravku neukazuje |
c02 a c03 jsou **jeden a tentýž záběr**, nejsou to dva nezávislé pohledy (shoda kamer 42,1° / 50,7° to potvrzuje) - druhé srovnání proto potvrzuje hlavně rozmístění detailů, ne nový úhel.

## Změřeno (z čelní fotografie c01, ±1,5 mm; obrys přesně)
- Délka lemu 545 mm, výška 279 mm (celá šířka a výška c01); tělo pod lemem je dlouhé 500 mm (obrys: Y ±250 u z' 105-170, ±248 u soklu), lem přečnívá ve směru Y o 22 mm na každém konci a nahoře se zkosuje (horní hrana Y ±244 u z' 279, rampa k ±270 u z' 259).
- Pás lemu z' 219-259: štítek (zapuštěný obdélník, px 327-474, py 41-77), logo HILTI (bílé obdélníky vektorizované přímo z masky c01, px 606-742, py 49-69), vyražený nápis PROKIT vlevo (nemodelován).
- Horní řada 8 okének v čele lemu (px 40-72, 110-218, 222-272, 315-392, 402-476, 520-572, 578-683, 725-740; z' 260-277), pozice z jasu řádku fotografie.
- Tři žebra mezi poli (px 211-229, 386-404, 562-580), vodorovná lišta z' 197-203, tři očka pod lemem (px 118, 398, 680).
- Sokl (podstavec): čelo z' 34-78, šikmá horní plocha z' 78-105, stohovací kapsa vlevo (px 160-222, z' 34-104) s černým zámkem.
- 4 nožky: Y středy px 92, 300, 498, 707 (± 209,4 a ± 68 mm), výška ~12 mm, šířka ~44/37 mm.
- Kóty výrobce (c03): vnější 37,8 × 55 × 28 cm, vnitřní 28 × 50,5 × 25 cm.

## Odhad (z c02/c03, kamera z bodů na čelní rovině; hloubky ve směru X)
- **Obálka X ±189 tvoří sokl; svislá rovina lemu/loga/štítku leží podle c02/c03 jen ~157-176 mm od osy** (homografie 6 bodů na této rovině: zbytek 1,7 px; šikmá rovina by zbytek zhoršila). Model používá lem **±176** (čelo i zadní strana, symetricky), sokl ±189, zapuštěnou stěnu ±150. Hodnoty 150/176 jsou odhad (shoda obrysu v c03 byla nejlepší pro lem 172-180); u zadní strany to z fotografií vůbec nejde ověřit.
- Zadní (-X) dlouhá strana není na žádné fotografii vidět zvenčí: model ji dělá zrcadlově shodnou s přední (žebra, okénka, lišta, očka), **bez loga, štítku a stohovací kapsy** - neověřeno.
- Koncové stěny (±Y) také zrcadlově shodné (c02/c03 ukazuje jen jednu zvenčí, druhou zevnitř): průchozí madlo (otvor ±60 mm × z' 224-250, hluboký ~16 mm skrz lem, polohu a velikost z c02/c03 jen ±10 mm), kapsa pod madlem (z' 192-224, hloubka ~8-16 mm), 6 větracích otvorů na zkosené horní hraně (rozteč ~22 mm; modelovány jako tmavé plošky, nikoli skutečné otvory).
- Hloubky okének (14 mm), štítku (1,2 mm), stohovací kapsy (do x = 158), úhel zkosení rohů lemu (30 mm) a soklu (12-16 mm) - odhad.
- Délka nožek ve směru X (±166) a černé patky - odhad (spodní strana na fotografiích není).

## Neověřeno / zjednodušeno
- **Vnitřek zjednodušen, nedokončeno:** dutina je hladká vana (podlaha z' 20, stěny mírně šikmé), **chybí** dělicí příčka, vnitřní žebra a sloupky, stupně na podlaze, vnitřní tvar madel a drážky na lemu zevnitř (c02/c03 ukazují členité vnitřní stěny). Tloušťky stěn jsou odhad (stěna ~6 mm nad dutinou ±144 mm, konce ~12-25 mm).
- **Vnitřní půdorys neodpovídá katalogu:** dutina je 288 × ~480 × 259 mm (Y ±240 nahoře, ±234 u podlahy). Katalogových 498 mm (a 505 mm na kótě c03) se s obrysem c01 nedá sloučit: tělo je venku jen 500 mm dlouhé, takže vnitřní 498 mm by znamenalo stěnu ~1 mm. Hodnota 498/505 mm je zřejmě změřená jinde (např. v rozích lemu) - **neověřeno**.
- Nemodelováno: nápis PROKIT, šipka u zámku, jemná textura/zrnění soklu, logo HILTI je jen ploška; spodní strana je plochá deska s nožkami (tvar spodku, vnitřní žebra dna neznámé).
- Materiál: jediná červená (`cervena`) + černá (zámek, patky, dna okének) + bílá (logo); odstín není kalibrován.
- Žádné pohyblivé části (zámek je pevný díl).

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2441669.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, téměř ortografický, oříznuto na obrys) | **0,992** | rozdíl obrysu ≤ 1,5 mm kromě horních rohů |
| `otevreny-c02` (kamera az 42,1°, el 50,7°, téměř ortografická) | 0,976 | červená maska (dělicí příčka uvnitř se nepočítá) |
| `otevreny-c03` (kamera az 42,1°, el 50,8°) | 0,976 | červená maska |
Dvojice foto | model | překryv byly prohlédnuty (ne jen IoU): shodují se obrys, logo, štítek, žebra, kapsa zámku, nožky, rampa s větráky a madlo (poloha ± ~10 px, tj. ±10 mm). Kamera u c02/c03 je odhad z bodů na čelní rovině + obrys; ohnisko téměř ortografické (fov ~3°), takže hloubku ve směru X určuje obrys, nikoli perspektiva - proto jsou odhady X (výše) nejméně jisté.

Nástroje (jen pro 2441669, v `nastroje/`): `fit_2441669.mjs` (kopie `fit_lm.mjs`, landmarky nepovinné, bez víka), `dvojice_2441669.mjs` (foto | model | překryv při uložené kameře), `srovnej_vse_2441669.sh`; landmarky v `landmarky_2441669_c02.json`, `landmarky_2441669_c03.json`; srovnání (jen vlastní rendery + json) v `kufriky_cloud/srovnani/2441669/`. Převzaté beze změny: `porovnej_celo.mjs`, `iou_kamera.mjs`, `kalibruj.py`, `maska_cervena.py`.
