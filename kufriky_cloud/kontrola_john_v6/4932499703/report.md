# Kontrola věrohodnosti 3D tvaru – Johnův model v6, SKU 4932499703 (Box pro elektrikáře 165×410×560)

Nezávislá kontrola proti fotografiím výrobce (Milwaukee PACKOUT). Jen čtení: žádný existující soubor nebyl změněn. Hodnotí se hotový GLB `kufriky_john/nahled-modely-v6/modely/4932499703.glb` (obálka už sedí na katalog). Fotografie nejsou v repu (jen URL níže); soubory `*_model_z_kamery_foto.png` jsou naše rendery Johnova modelu z kamery odhadnuté z fotky.

## Hodnocení: **nevěrohodný**

Jediná fotka (shora, otevřený kufr) ukazuje, že vložka v modelu neodpovídá: místo dvou vložných panelů a 4 vysokých látkových kapes je jeden panel a 5 malých kapes 60×60 mm, víko bez pásu úchytů. Vnější tvar (stěny, rohy, tyče, západky) z této fotky posoudit nelze.

## Fotky a IoU siluety

| foto | IoU | co ukazuje | pozn. k IoU a kameře | rms landmarků |
|---|---|---|---|---|
| c01 (Hero_1) | 0,909 | otevřený kufr shora, víko vzadu (použitelné jen pro vnitřek a obrys; fotka je BAJT PO BAJTU STEJNÁ jako u 4932499704, md5 shodné) | kamera jen ze 4 rohů těla (téměř kolmý pohled, fov ≈ 10°, el ≈ 79°), 4 body na 6 parametrů: rms 2,4 px je zavádějící, kamera je slabě určená (perspektiva víka nejistá, IoU víka jen orientační); úhel víka −118° DOFITOVÁN podle IoU; svěšené třmeny západek vyloučeny z masky | 2.4 px |

**Jak číst IoU.** Obálka modelu sedí na katalog, takže silueta vychází vysoko i u hrubého kvádru; IoU vypovídá hlavně o obálce, ne o detailech. Kamera z ručně změřených bodů na fotce (rohy těla/krytek) a katalogových rozměrů obálky; výška horních bodů (horní hrana krytek) je volný parametr, protože se nepodařilo spolehlivě určit její Z. Kamera NENÍ dofitována podle obrysu modelu. Přesnost kamery je odhad: zbytky landmarků viz rms_px, v obrazu ≈ ±15–20 px z 1200 (≈ ±10 mm na čele). U fotek s otevřeným víkem je úhel víka dofitovaný podle IoU, takže IoU víka není důkaz. Důkazem jsou níže uvedené viditelné rozdíly; ty (desítky mm) jsou větší než nejistota kamery.

## Viditelné rozdíly (foto | model)

| č. | foto | rozdíl | velikost | závažnost |
|---|---|---|---|---|
| 1 | c01 | Vložné panely: na fotce DVA panely – levý hladký černý (viditelná část ≈ 135×300 mm, zbytek je pod pravým) a pravý červeně lemovaný panel ≈ 350×290 mm s kapsami při zadní hraně; společně ≈ 490×300 mm. Model: jediný panel 434×275 mm s červeným rámem. | celek ≈ 490×300 vs 434×275 mm (±5 %) | **viditelný** |
| 2 | c01 | Kapsy: na fotce 4 vysoké látkové kapsy (každá ≈ 75 mm široká × ≈ 130 mm vysoká) v pravém panelu při zadní hraně; model 5 kapes 60×60 mm (hloubka 43 mm) v řadě po celé šířce panelu. | 4 vs 5 kapes; ≈ 75×130 vs 60×60 mm | **zásadní** |
| 3 | c01 | Víko zevnitř: na fotce černý panel s červeným lemem, červeným štítkem Milwaukee vlevo nahoře a dlouhým pásem červených pružných úchytů přes šířku víka (odhad ≈ 380×45 mm, ±15 %); model jen červený rám 340×488 mm bez pásu a štítku. | pás úchytů a štítek chybí | **viditelný** |
| 4 | c01 | Poloha západek: třmeny na fotce při čele na ≈ ±160 mm od osy; model ±179 mm (rozdíl ≈ 20 mm). | ≈ 20 mm | **kosmetický** |
| 5 | c01 | Víko: na fotce silný rám s žebrovaným okrajem a viditelnými pantovými články; model plochý panel bez dutiny. Rozměr rozdílu nelze určit (perspektiva víka při slabé kameře). | nelze změřit | **viditelný** |

Závažnost: kosmetický = nepodstatný při běžném pohledu; viditelný = patrný na první pohled u fotky; zásadní = mění charakter výrobku nebo chybí hlavní prvek. Odhady v mm jsou z místního měřítka kamery (±15 mm).

## Co nelze z fotek posoudit (neověřeno)

- Celý vnějšek (čelo, boky, rohy, tyče, spodek): z jediného pohledu shora nelze; zda má kufr hliníkové tyče a chytací okna jako PACKOUT box, neví se.
- Rozdíl mezi variantou pro elektrikáře a instalatéry: výrobce používá TUTÉŽ fotku (md5 shodné), Hero_2–5 na CDN neexistují (404); GLB obou SKU jsou binárně shodné.
- Přesná poloha vložek vůči podlaze (jen obrys shora).
- Poloměry, úkosy, tloušťky; úhel otevření víka.

## Doporučení

- Vnější tvar pro tato SKU ověřit na dalších fotkách (zavřený kufr zepředu a z boku) – bez nich nelze hodnotit.
- Vložku přepracovat podle c01: dva panely, 4 vysoké kapsy, pás úchytů ve víku.
- Rozhodnout, zda mají mít SKU 4932499703 a 4932499704 různý model (fotky to nerozlišují).

## Prohlédnuté dvojice (foto | model | překryv)

- c01: dvojice foto | model | překryv; výřezy vnitřku těla a víka

Dvojice s fotografií jsou jen ve scratchpadu (mimo repo), v repu je jen model z kamery: `c01_model_z_kamery_foto.png`. Landmarky, kamery a zbytky: `kontrola.json`.

## Zdroje fotografií (jen URL)

- c01: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932499703--Hero_1.jpg?width=1200
- Při kontrole dohledán další zdroj: Hero_2–Hero_5 pro 4932499703/-04 na CDN výrobce neexistují (404).

Poznámka: některé z výše uvedených rozdílů si John sám připouští v `kufriky_john/README_doladeni_v6.md` (tabulka návrhů); tento report je na tom nezávislý, vychází z fotek a z renderů GLB.
