# Hilti ProKit PKC 61 (2437354, Box na nářadí ProKit XL) – poznámky k modelu

Model: `kufr_2437354.mjs` (+ `p2437354_zaklad.mjs`, `p2437354_korpus.mjs`, `p2437354_vicko.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2437354` → `modely/2437354.glb` (78 dílů, 9 444 trojúhelníků, obálka 387 × 561 × 422 mm, odchylka 0/0/0 mm). Souřadnice: X = hloubka (čelo s logem do +X), Y = délka, Z = výška, počátek ve středu obálky. Víko = skupina `vicko`, pivot na pantové hraně (x = −187, z' = 368), `extras.osa = [0,−1,0]`, `--pose vicko=95` otevře.
Zadání (Robert, schválil PKC 35): hlavní je ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen, nedokončeno**. Postup a nástroje převzaty z PKC 35 (`2437394_poznamky.md`); půdorysný loft je kopie `p2437394_zaklad.mjs` se změněnými konstantami (ZC = 211, převod px → mm pro novou fotografii).

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `../fotky_url.tsv` a `2437354_dalsi_fotky.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L153710; měřeno na f2000, 1200 × 913 px) | přímý čelní pohled, těsně oříznutý (boční madla jsou na krajích) | měření čela (1200 px = 561 mm, 913 px = 422 mm), porovnání `celo` |
| c02 (L156512, 834 × 1200) | šikmo shora zepředu a z boku, víko otevřené (~91°) | kamera z 5 ručních bodů + obrys, porovnání `otevreny-c02` |
| c03 (L156505, 948 × 1200) | totéž s kótami výrobce | kontrola kót, kamera z 6 bodů + obrys (maska podle červené barvy, aby šipky a popisky nekazily obrys), `otevreny-c03` |
| L153711_ISO (na hilti.cz jen 250 × 234 px, zvětšeno 4× jen pro masku) | zavřený, šikmo zepředu a z boku; **není mezi c01–c09**, stažen jen do scratchpadu, URL v `2437354_dalsi_fotky.tsv` | tvar horní plochy (bez otvoru), boční madlo, pant, kamera z 5 bodů, `zavreny-iso-L153711` |
| c04, c05 | aplikační snímky (vozík, regál) | nepoužitelné k měření (c04 ukazuje tvar bočního madla) |
| c06–c09 | miniatury souvisejících produktů | ignorovány |
Sourozenecké fotografie nebyly pro rozměry použity (PKC 35 jen jako šablona).

## Co je změřeno (c01, ±1,5 mm, vyšší rozlišení než u PKC 35)
- Obálka 387 × 561 × 422 (katalog); celková šířka 561 = boční madla (c01 sahají od kraje ke kraji); lem víka ±279,5, plášť víka ±274, tělo ±251,6 (dole) → ±255,7 (nahoře; boky se mírně rozbíhají, c01 obrys).
- **Víko je tvarem shodné s víkem PKC 35** (rozdíl výšek 422 − 267 = 155 mm = `DZ`): šrouby čepů (c01 y −217/−134/+134/+217, z' 381), rámečky západek (y −208…−140 a +140…+210), kapsa madla (y ±106; rozdíl proti PKC 35 ≤ 2,7 mm), lem z' 365–373, zkosení horní hrany z' 403–422. Polohy prvků víka, které se přebírají z c01 PKC 35, jsou v kódu přes `lY/lZ`; ty, které šly přeměřit v c01 PKC 61, jsou měřeny přímo (`pY/pZ`).
- Horní pás s kapsou madla z' 308–366,5 (podlaha kapsy 308, c01 py 245), římsa pod pásem z' 293,5 (py 278), čelní panel s logem z' 131–288 (y ±234), pruhy vtlačeného panelu u okrajů (px 100–135 / 1065–1110).
- Logo HILTI: obdélníky písmen vyčtené z masky bílé barvy (px 694–1014 × 335–380 → y 44…193, z' 246…267).
- Sokl (z' 12–131): spodní hrana panelu je „šipka“ (z' 132 u konců → 113 u výřezu; c01 py 628 → 668), výřez uprostřed y ±67,8 (z' 29–113), stohovací zámek vlevo (kapsa y −165…−121, z' 21…71, osmiúhelník), 4 nožky (y −211/−73/+74/+212; z' 0–13; patky 0–20), zkosení spodní hrany ve 4 stupních (z' 12–30: y ±235 → ±252).
- Boční madla: černý blok y ±252…±280,5, z' 267…331 (c01 px 0–55, py 200–335) s červeným držákem nad ním do lemu víka (z' 331–365).
- Kóty výrobce (c03): vnitřní 35,1 × 50,6 × 34,8 cm; vnější 38,7 × 56,1 × 42,2 cm. Vnitřní rozměry model dodržuje: dutina 351 (X) × 506 (Y u horního okraje) × 348 (hloubka od okraje 366,5 ke dnu z' 18).

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2437354.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, téměř ortografický pohled oříznutý na obrys) | **0,984** | `porovnej_celo_2437354.mjs` (kopie s větším záběrem – kufr je vyšší) |
| `otevreny-c02` (víko 91°) | 0,955 | ruční body + obrys; v kamerách c02/c03 vyšel shodně az ≈ 42°, el ≈ 50° |
| `otevreny-c03` (víko 94°) | 0,955 | červená maska |
| `zavreny-iso-L153711` | 0,966 | foto jen 250 × 234 px, kamera z 5 bodů (ohnisko vyšlo téměř ortografické – slabě určené) |
Dvojice foto | model | překryv byly prohlédnuty (ne jen IoU): čelo (logo, západky, madlo, šrouby, zámek, nožky, rohy), ISO (poloha loga, madla, západek i bočního madla sedí na pár pixelů). Kamera je odhad z ručně změřených bodů (landmarky v `landmarky/2437354_*_vstup.json`), ohnisko není změřené – IoU u šikmých pohledů ukazuje i chybu kamery. Model je ve vlastních renderech `kufriky_cloud/srovnani/2437354/*.png` (jen naše rendery + json s kamerou a odkazem na fotku; cizí fotografie nejsou).

## Neověřeno / odhad / zjednodušeno
- **Vnitřek zjednodušen, nedokončeno:** dutina je hladká vana (dno z' 18), **chybí** vše, co c02/c03 ukazují uvnitř: žebra a vybrání ve stěnách a dnu, přihrádková žebra víka (víko je dutý plášť, stěna 3 mm), zámky. **Tloušťky stěn (X 9–11,5 mm, Y 3,5 mm a u okraje 21 mm) jsou dopočtené z kót 351 × 506, nikoli měřené**; vnitřní šířka 506 platí u horního okraje, níže je dutina kvůli sklonu bočních stěn užší (~497).
- **Hloubky v X** (z čelních a šikmých pohledů nezměřitelné, odhad): kapsa madla 28 mm, kapsa stohovacího zámku 18 mm, výřez v soklu 40 mm (v c01 má pravá stěna šikmou plochu, v modelu je kolmá a souměrná), rámečky západek 6 mm, vtlačené pruhy 1,2 mm, výška klínu soklu 2,5 mm. Čelní a zadní rovina (xF = 186, xR = −183) a zkosení rohů (20–22 mm) převzaty z PKC 35 a jsou neověřené.
- **Boční madlo:** délka ve směru X (z −100 do +70, tj. necentrované) je jen odhad z c03/c02 (zpětná projekce a ISO, ±15 mm); tvar rámu (dvě vzpěry, úchop, příčka, okno) přibližný, drobné detaily (otvor, popis) chybí.
- **Zadní (pantová) strana a spodek** na fotografiích nejsou: zadní stěna, pant (7 úseků po ~71 mm, kolík, klínové bloky s okénky podle ISO), spodní strana nožek a zadní řada nožek jsou přibližné. Vlastní tvar horní plochy víka (plató z' 413, rampa k pantu na 422) je převzat z PKC 35; ISO ukazuje hladkou desku s rýhou uprostřed a vybráním při předním okraji – **nemodelováno**. Na rozdíl od PKC 35 zde není otvor pro horní držadlo (ISO L153711 ho nemá).
- Svislý čep zámku víka vpravo od madla (c01 px 845–862) je jen kvádr 3 mm; západky (červené jazyky), drátové třmeny a madla jsou **pevné díly** (jediný pohyblivý uzel je `vicko`); jak se západky a drát pohybují, z fotografií nejde určit.
- Nápisy: „PROKIT“ vyražený vlevo nahoře na víku, štítek na čelní šikmině víka (c01 px 490–710, py 5–35), šipka u zámku, jemná textura povrchu – nemodelováno; logo HILTI je jen ploška.
- Svislé žebrování/drážky bočních stěn (viditelné v ISO a c03) a svislé rohové kapsy – nemodelováno.
- Materiál: jediná červená (`cervena`) pro korpus i víko, černé madlo/západky/patky; odstín není kalibrován. Hmotnost 5,9 kg neověřena (model je jen povrch).

## Zbylé viditelné rozdíly proti fotografii
- Čelo: lem víka nad západkami je jednoduchý pás (fotografie: profilované žebro), drážky u rámečků jen naznačeny, zámek v kapse zjednodušen na osmiúhelník + proužek; madlo bez vyraženého loga.
- Šikmé pohledy: víko je o ~10 px (1 %) mimo (poloha pivotu je odhad), stěny koncových desek bez žeber; výřez soklu je v modelu mělčí než ve fotografii.
- Nástroje: `nastroje/porovnej_celo_2437354.mjs`, `unproject_2437354.mjs`, `srovnej_vse_2437354.sh` jsou kopie s číslem 2437354; ostatní nástroje (`fit_lm.mjs`, `iou_kamera.mjs`, `kalibruj.py`, `maska_cervena.py`) se používají beze změny přes argumenty. `fit_lm.mjs --pose-fix` pro zavřený pohled (ISO). Volný odhad kamery `render/srovnej.mjs` u ISO vyšel z opačné strany (azim 218°, IoU zdánlivých 0,95), proto se kamera pro ISO odhaduje z landmarků.
