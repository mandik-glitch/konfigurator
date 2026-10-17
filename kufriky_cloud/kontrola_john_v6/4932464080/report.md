# Kontrola věrohodnosti 3D tvaru – Johnův model v6, SKU 4932464080 (Box na nářadí 165×411×561)

Nezávislá kontrola proti fotografiím výrobce (Milwaukee PACKOUT). Jen čtení: žádný existující soubor nebyl změněn. Hodnotí se hotový GLB `kufriky_john/nahled-modely-v6/modely/4932464080.glb` (obálka už sedí na katalog). Fotografie nejsou v repu (jen URL níže); soubory `*_model_z_kamery_foto.png` jsou naše rendery Johnova modelu z kamery odhadnuté z fotky.

## Hodnocení: **nevěrohodný**

Obálka sedí, ale model je hladký kvádr: chybí tyče a rohové krytky, chytací okna, červená U-rukojeť je nahrazena plochým rámečkem o ≈ 100 mm výš, západky jsou ≈ 2,5× menší a o ≈ 85 mm výš, víko nemá zkosená ramena ani 10 kapes.

## Fotky a IoU siluety

| foto | IoU | co ukazuje | pozn. k IoU a kameře | rms landmarků |
|---|---|---|---|---|
| c01 (Hero_1) | 0,844 | zavřený box zepředu zprava (použitelné) | kamera jen z landmarků (rms 19 px; dva body mají zbytek ≈ 30–35 px, tj. nejistota kamery je tady největší); IoU celého obrysu | 19.5 px |
| c02 (Hero_2) | 0,885 | otevřený box, 2 boční vyjmuté přihrádky, drátěné třmeny západek svěšené (použitelné; boční přihrádky a třmeny vyloučeny z masky) | úhel víka −92° (osa pantů v modelu) DOFITOVÁN podle IoU → není nezávislý důkaz; rms 2,4 px je optimistické (7 parametrů na 12 rovnic); vyloučeny boční přihrádky a svěšené třmeny; tělo: kamera z landmarků | 2.4 px |
| – | – | c03 (Hero_3): červený velký box PACKOUT – jiný produkt (jiná barva, zjevně vyšší kufr), nepoužito. | | |

**Jak číst IoU.** Obálka modelu sedí na katalog, takže silueta vychází vysoko i u hrubého kvádru; IoU vypovídá hlavně o obálce, ne o detailech. Kamera z ručně změřených bodů na fotce (rohy těla/krytek) a katalogových rozměrů obálky; výška horních bodů (horní hrana krytek) je volný parametr, protože se nepodařilo spolehlivě určit její Z. Kamera NENÍ dofitována podle obrysu modelu. Přesnost kamery je odhad: zbytky landmarků viz rms_px, v obrazu ≈ ±15–20 px z 1200 (≈ ±10 mm na čele). U fotek s otevřeným víkem je úhel víka dofitovaný podle IoU, takže IoU víka není důkaz. Důkazem jsou níže uvedené viditelné rozdíly; ty (desítky mm) jsou větší než nejistota kamery.

## Viditelné rozdíly (foto | model)

| č. | foto | rozdíl | velikost | závažnost |
|---|---|---|---|---|
| 1 | c01 (potvrzeno c02) | Rohy: 4 hliníkové tyče (≈ 30 mm široké, viditelná délka ≈ 55–60 mm) s rohovými krytkami ≈ 50 mm; model: ochrana rohu 15×15 mm a lišta 4×5×111 mm, bez reliéfu. | ≈ 30 mm profil | **zásadní** |
| 2 | c01, c02 | Krátké strany: na fotce průchozí chytací okna mezi tyčemi (viditelné bílé pozadí); model plná stěna. | okno ≈ výška tyče | **viditelný** |
| 3 | c01, c02 | Čelní rukojeť: na fotce červená vystupující U-rukojeť ≈ 225×110 mm s černým gripem v dolní polovině čela; model: plochý červený rámeček 186×33 mm v horní polovině, těžiště modelu o ≈ 100 mm (±15) výš (u boxu výšky 165 mm). | ≈ 100 mm poloha, tvar jiný | **zásadní** |
| 4 | c01, c02 | Západky: na fotce ≈ 70×73 mm červené těleso s drátěným třmenem; model 31×22 mm; těžiště modelu o ≈ 85 mm (±15) výš (na fotce uprostřed čela, v modelu u horní hrany). | ≈ 2,5× menší, ≈ 85 mm výš | **zásadní** |
| 5 | c01 | Horní plocha víka: na fotce 10 kapes (2×5), středové žebro, zkosená ramena a zaoblené rohy; model 6 rámečků + 2 lišty, ostrý kvádr; víko v modelu přesahuje skutečný obrys nahoře o ≈ 10–15 mm. | 10 vs 6 kapes | **viditelný** |
| 6 | c01, c02 (odhad kamery) | Dělení víko/tělo: horní okraj krytek/těla ≈ 50 mm pod vrchem víka (odhad ±15 mm); v modelu 20 mm. | ≈ 30 mm (±15) | **viditelný** |
| 7 | c02 | Víko zevnitř: hluboká skořepina s žebry, kruhový výstupek uprostřed; model plná deska ≈ 20 mm s plochou spodní stranou. | skořepina ≈ 40–50 mm vs plochá deska | **viditelný** |
| 8 | c02 | Vnitřek: na fotce 3+3 přihrádky (matice/podložky vlevo, šrouby/hmoždinky vpravo) a volný střed, dvě vyjmuté boční přihrádky s víčky (levá s dělením, pravá otevřená). Model: prázdná podlaha a úzká lavice 450×100 mm vzadu, boční přihrádky nejsou. Zda jsou vložky součástí dodávky, fotky neříkají. | celé vložky chybí | **viditelný** |
| 9 | c01 | Logo/otvor/jazýček: na fotce kruhový otvor nad rukojetí a logo; model velký nápis MILWAUKEE PACKOUT pod rukojetí a červený kroužek dole. | kosmetické | **kosmetický** |

Závažnost: kosmetický = nepodstatný při běžném pohledu; viditelný = patrný na první pohled u fotky; zásadní = mění charakter výrobku nebo chybí hlavní prvek. Odhady v mm jsou z místního měřítka kamery (±15 mm).

### Poloha prvků na čele (c01), model vs foto

Stejná kamera; foto = ručně změřený střed prvku; model = promítnutý 3D střed prvku z GLB; hodnota „svisle“ = rozdíl v mm (záporná = model výš než foto).

| prvek | model [px] | foto [px] | rozdíl [px] | svisle ≈ mm |
|---|---|---|---|---|
| zapadka cervena vlevo (stred) | [152, 484] | [182, 645] | [30, 161] | -90 |
| zapadka cervena vpravo (stred) | [721, 548] | [712, 720] | [-9, 172] | -81 |
| drzadlo (stred ruzove casti) | [409, 509] | [440, 705] | [31, 196] | -101 |

## Co nelze z fotek posoudit (neověřeno)

- Zadní strana, spodek a koncová strana zblízka – nejsou na žádné použitelné fotce.
- Poloměry, úkosy a tloušťky stěn – nekótováno.
- Počet a rozměr vnitřních přihrádek mimo c02, zda jsou součástí dodávky.
- Dělení víko/tělo a výška krytek – jen odhad z kamery (±15 mm).

## Doporučení

- Čelo: U-rukojeť a západky přesunout o ≈ 85–100 mm níž a zvětšit na ≈ 70×73 mm (západky) a ≈ 225×110 mm (rukojeť).
- Doplnit tyče, krytky, chytací okna; víko se zkosenými rameny a 10 kapsami.
- Interiér: boční přihrádky a vložky podle c02 jen pokud jsou součástí dodávky (ověřit u výrobce).

## Prohlédnuté dvojice (foto | model | překryv)

- c01: dvojice + přiblížené výřezy zleva a zprava
- c02: dvojice + výřez celé sestavy

Dvojice s fotografií jsou jen ve scratchpadu (mimo repo), v repu je jen model z kamery: `c01_model_z_kamery_foto.png`, `c02_model_z_kamery_foto.png`. Landmarky, kamery a zbytky: `kontrola.json`.

## Zdroje fotografií (jen URL)

- c01: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464080--Hero_1.jpg?width=1200
- c02: https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932464080--Hero_2.jpg?width=1200
- Další fotografie jsem nehledal; dostupné snímky stačily.

Poznámka: některé z výše uvedených rozdílů si John sám připouští v `kufriky_john/README_doladeni_v6.md` (tabulka návrhů); tento report je na tom nezávislý, vychází z fotek a z renderů GLB.
