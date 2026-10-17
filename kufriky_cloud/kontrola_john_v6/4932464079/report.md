# Kontrola věrohodnosti 3D tvaru – Johnův model v6, SKU 4932464079 (Velký box na nářadí 282×411×561)

Nezávislá kontrola proti fotografiím výrobce (Milwaukee PACKOUT). Jen čtení: žádný existující soubor nebyl změněn. Hodnotí se hotový GLB `kufriky_john/nahled-modely-v6/modely/4932464079.glb` (obálka už sedí na katalog). Fotografie nejsou v repu (jen URL níže); soubory `*_model_z_kamery_foto.png` jsou naše rendery Johnova modelu z kamery odhadnuté z fotky.

## Hodnocení: **nevěrohodný**

Obálka a hrubá kvádrová silueta sedí (IoU 0,84–0,94), ale chybí/jsou špatně všechny charakteristické prvky PACKOUT: hliníkové tyče s rohovými krytkami, průchozí chytací okna v krátkých stranách, červená U-rukojeť, velké západky (poloha i velikost), tvar a členění víka.

## Fotky a IoU siluety

| foto | IoU | co ukazuje | pozn. k IoU a kameře | rms landmarků |
|---|---|---|---|---|
| c01 (Hero_1) | 0,895 | zavřený box, horní držadlo zvednuté, pohled zepředu zprava (použitelné) | IoU jen těla: z fotky vyříznuta oblast zvednutého držadla (v modelu je sklopené); kamera jen z landmarků; model zbytek bez úprav | 11.4 px |
| c02 (Hero_2) | 0,940 | otevřený box s nářadím, víko vzhůru, pohled shora zepředu (použitelné; tělo i víko) | úhel víka −95° (rotace uzlů víka kolem osy pantů v modelu) DOFITOVÁN podle IoU, proto IoU není nezávislý důkaz tvaru víka; tělo: kamera jen z landmarků | 18.1 px |
| c03 (Hero_3) | 0,923 | totéž + vyjmutá vložka vpravo (použitelné; vložka vyloučena z masky fotky) | úhel víka −95° dofitován; oddělená vložka vyloučena z masky fotky; kamera z landmarků (rms 6 px) | 6.3 px |

**Jak číst IoU.** Obálka modelu sedí na katalog, takže silueta vychází vysoko i u hrubého kvádru; IoU vypovídá hlavně o obálce, ne o detailech. Kamera z ručně změřených bodů na fotce (rohy těla/krytek) a katalogových rozměrů obálky; výška horních bodů (horní hrana krytek) je volný parametr, protože se nepodařilo spolehlivě určit její Z. Kamera NENÍ dofitována podle obrysu modelu. Přesnost kamery je odhad: zbytky landmarků viz rms_px, v obrazu ≈ ±15–20 px z 1200 (≈ ±10 mm na čele). U fotek s otevřeným víkem je úhel víka dofitovaný podle IoU, takže IoU víka není důkaz. Důkazem jsou níže uvedené viditelné rozdíly; ty (desítky mm) jsou větší než nejistota kamery.

## Viditelné rozdíly (foto | model)

| č. | foto | rozdíl | velikost | závažnost |
|---|---|---|---|---|
| 1 | c01 (potvrzeno c02, c03) | Rohy: na fotce 4 svislé hliníkové tyče (≈ 30–35 mm široké, viditelná délka ≈ 140 mm) mezi černými rohovými krytkami (≈ 50×55 mm, se šroubem) vystupující z těla. V modelu jen sloupek ochrany rohu 15×15 mm a kovová lišta 5×5 mm (zdroj GLB: roh-kov-*), prakticky bez reliéfu. | ≈ 30 mm profil × 140 mm délka | **zásadní** |
| 2 | c01, c02, c03 | Krátké strany: na fotce mezi tyčemi a tělem průchozí chytací okno (na fotce vidět bílé pozadí skrz). Model: plná rovná stěna bez otvoru (ověřeno renderem koncové stěny). | okno ≈ výška tyče (≈ 140 mm) | **viditelný** |
| 3 | c01, c02, c03 | Čelní rukojeť: na fotce červená vystupující U-rukojeť s černým gripem, ≈ 230×120 mm, těžiště o ≈ 130 mm (±15) NÍŽE než v modelu. V modelu plochý červený rámeček 186×33 mm („okno“) v horní třetině čela. | ≈ 130 mm poloha, tvar jiný | **zásadní** |
| 4 | c01, c02, c03 | Západky: na fotce velké červené západky ≈ 65×57 mm s dlouhým drátěným třmenem; model 31×38 mm, ≈ poloviční, se třmenem krátkým; těžiště modelu o ≈ 60 mm (±15) výš než na fotce (u obou západek). | ≈ 2× menší, ≈ 60 mm výš | **viditelný** |
| 5 | c01 | Horní plocha víka: na fotce 10 hlubokých kapes/prolisů (2 skupiny po 5, středové žebro, červený štítek vpravo), víko má zkosená ramena a zaoblené rohy. Model: 6 obdélníkových rámečků + 2 okrajové lišty, plný ostrý kvádr celé půdorysné plochy, červený štítek 36×24 mm (na fotce ≈ 120×20 mm podélně). | 10 vs 6 kapes; víko nad skutečný obrys přesahuje o ≈ 10–15 mm | **viditelný** |
| 6 | c01, c02, c03 (odhad kamery) | Dělení víko/tělo: horní hrana rohových krytek a těla leží na fotkách ≈ 50 mm pod rovinou víka (odhad z kamery, ±15 mm); v modelu horní okraj těla 30 mm pod vrchem víka (Z 111 z 141). Víko skutečné je tedy silnější (≈ 50 mm skořepina), model má ≈ 30 mm. | ≈ 20 mm (±15) | **viditelný** |
| 7 | c02, c03 | Víko zevnitř: na fotce hluboká skořepina se žebry a kruhovým výstupkem uprostřed (⌀ ≈ 70 mm, ±15) a ozubením u pantu; model plná deska ≈ 30 mm s plochou spodní stranou (viko-panel 8 mm) bez vnitřního reliéfu. | skořepina ≈ 40–50 mm vs plochá deska | **viditelný** |
| 8 | c02, c03 | Vnitřek těla: na fotce hluboká vana s žebry a zvlněnou stěnou; vyjmutá/vložená vložka (2 přihrádky) ≈ 60 % délky kufru × téměř plná hloubka. Model: plochá podlaha a úzká lavice 450×100×42 mm podél zadní stěny (vlozka-*), ve fotkách nic takového není. Zda je vložka součástí dodávky, fotky neříkají. | půdorys vložky ≈ 450×100 vs ≈ 350×330 mm (odhad ±50) | **viditelný** |
| 9 | c01 | Horní držadlo: foto zvednuté, model sklopené – srovnání nelze. Z fotky rozteč noh držadla ≈ 500 mm (±40), model sklopené rameno 52×354 mm. | ≈ 150 mm (odhad) | **viditelný (odhad)** |
| 10 | c01 | Logo a drobnosti: na fotce malé logo Milwaukee/PACKOUT v prohlubni nad rukojetí, kruhový otvor ⌀ ≈ 35 mm nad rukojetí, červený jazýček u dolní hrany. Model: velký červený nápis MILWAUKEE PACKOUT pod rukojetí a červený kroužek o ≈ 50 mm výš než jazýček. | kosmetické, ≈ 50 mm poloha | **kosmetický** |
| 11 | c01 | Spodní hrana čela: na fotce souvislá přímá hrana na nejnižší úrovni; v modelu je čelní hrana těla 12 mm nad nožkami (nožky odsazené od čela), obrys je tam o ≈ 8–12 mm výš. | ≈ 10 mm | **kosmetický** |

Závažnost: kosmetický = nepodstatný při běžném pohledu; viditelný = patrný na první pohled u fotky; zásadní = mění charakter výrobku nebo chybí hlavní prvek. Odhady v mm jsou z místního měřítka kamery (±15 mm).

### Poloha prvků na čele (c01), model vs foto

Stejná kamera; foto = ručně změřený střed prvku; model = promítnutý 3D střed prvku z GLB; hodnota „svisle“ = rozdíl v mm (záporná = model výš než foto).

| prvek | model [px] | foto [px] | rozdíl [px] | svisle ≈ mm |
|---|---|---|---|---|
| zapadka cervena vlevo (stred) | [162, 580] | [180, 688] | [18, 108] | -62 |
| zapadka cervena vpravo (stred) | [718, 646] | [700, 770] | [-18, 124] | -63 |
| drzadlo (cervene, stred) | [420, 604] | [432, 845] | [12, 241] | -130 |
| cerveny prvek dole uprostred (stred) | [428, 932] | [460, 1022] | [32, 90] | -51 |
| kruhovy otvor/kroužek (stred) | [428, 932] | [460, 805] | [32, -127] | 72 |

## Co nelze z fotek posoudit (neověřeno)

- Zadní strana, spodek (nožky/spojovací prvky) a koncové strany zblízka – žádná fotka (v c01 jen pravá krátká strana pod úhlem ≈ 60°).
- Horní držadlo ve sklopené poloze (c01 ukazuje jen zvednuté).
- Poloměry zaoblení, úkosy a tloušťky stěn – fotografie je nekótují.
- Přesná poloha dělení víko/tělo a výška krytek – jen odhad z kamery (±15 mm).
- Zda jsou vložky z c02/c03 součástí dodávky.

## Doporučení

- Před dalším použitím modelu přepracovat čelo: U-rukojeť (poloha o ≈ 130 mm níž), velké západky (≈ 65×57 mm, o ≈ 60 mm níž).
- Doplnit hliníkové tyče a rohové krytky jako samostatné objemové díly (≈ 30–35 mm profil, krytky ≈ 50 mm) a chytací okna v krátkých stranách.
- Víko: zkosená ramena, 10 kapes, silnější skořepina (≈ 50 mm); vnitřek víka a vany zjednodušeně zrekonstruovat podle c02/c03.
- Sklopenou polohu horního držadla doměřit na kusu nebo z další fotky; rozteč noh ověřit.

## Prohlédnuté dvojice (foto | model | překryv)

- c01: dvojice foto | model | překryv + přiblížené výřezy zleva a zprava
- c02: dvojice + výřez celé sestavy
- c03: dvojice + výřez celé sestavy

Dvojice s fotografií jsou jen ve scratchpadu (mimo repo), v repu je jen model z kamery: `c01_model_z_kamery_foto.png`, `c02_model_z_kamery_foto.png`, `c03_model_z_kamery_foto.png`. Landmarky, kamery a zbytky: `kontrola.json`.

## Zdroje fotografií (jen URL)

- c01: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464079--Hero_1.jpg?width=1200
- c02: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464079--Hero_2.jpg?width=1200
- c03: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464079--Hero_3.jpg?width=1200
- Další fotografie jsem nehledal; dostupné snímky stačily.

Poznámka: některé z výše uvedených rozdílů si John sám připouští v `kufriky_john/README_doladeni_v6.md` (tabulka návrhů); tento report je na tom nezávislý, vychází z fotek a z renderů GLB.
