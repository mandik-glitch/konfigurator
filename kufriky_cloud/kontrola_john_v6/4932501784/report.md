# Kontrola věrohodnosti tvaru: 4932501784 Box na nářadí XL, nová revize (Johnův model v6)

Model: `kufriky_john/nahled-modely-v6/modely/4932501784.glb` (obálka 394 × 554 × 422 mm, sedí). Nic v repu nebylo upraveno, jen vznikla tato složka.
Fotografie (jen URL, kopie v repu nejsou):
- c01 = Hero_1 `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932501784--Hero_1.jpg?width=1200`
- c02 = Hero_2 `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932501784--Hero_2.jpg?width=1200`
(URL jsem ověřil: stažený soubor se shoduje s fotkou ve scratchpadu.)
Soubory: `c01_render.png`, `c02_render.png`, `c01_kamera.json`, `c02_kamera.json`, `shoda_glb_obou_XL.json`.

## Shoda se SKU 4932478162 (úkol: jsou geometricky shodné?)
**Ano, jsou geometricky identické.** Binární blok GLB (vrcholy, normály, indexy; 1 412 160 B) je shodný bajt po bajtu, 95 uzlů se stejnými názvy, rozměry i materiály; soubory (stejně velké, 1 498 380 B, jiný md5) se liší pouze řetězcem `asset.extras.sku`. Žádný rozdíl v tvaru není (viz `shoda_glb_obou_XL.json`, test provedl porovnáním obou souborů).

## Hodnocení: NEVĚROHODNÝ jako model tohoto SKU (tělo samo jako pro 4932478162 s výhradami)
Na obou fotkách SKU 4932501784 je zdvižené U-madlo nad víkem (výška nad víkem ≈ 160 mm, po šířce ≈ 94 % šířky těla, černá ramena s hliníkovou a gumovou částí). Žádný takový prvek v GLB není (nejvyšší bod je víko, z = +211 mm, obálka 422 sedí na tělo bez madla), a protože je GLB totožný s modelem staršího SKU, který toto madlo na své fotce nemá, neodpovídá nová revize modelu v jejím definujícím rysu. Je to zásadní rozdíl. Zbytek těla má stejné výhrady jako u 4932478162.

## Tabulka foto | IoU | nejdůležitější rozdíly
| foto | kamera | IoU | nejdůležitější rozdíly |
|---|---|---|---|
| c01 (zepředu zprava, az ≈ 26°, el ≈ 12°, fov ≈ 17.5°) | ruční body (8 bodů na rohových ochranách) + obrys fotky pod řádkem y=365 px vs. KVÁDR obálky z katalogu; nezávislé na modelu | 0.742 celé; 0.962 pod řádkem y=365 px (bez madla) | chybí zdvižené madlo (zásadní), chybí hliníkové tyče + rohové ochrany (viditelný), spony ≈ 60 % (viditelný), spodní zámková šachta a nohy (viditelný), víko bez zkosení, 6 vs. 10 kapes (viditelný) |
| c02 (čelně, az ≈ 0°, el ≈ 21°, fov ≈ 20°) | ruční body (8 bodů) + obrys pod řádkem y=345 px vs. KVÁDR obálky; nezávislé na modelu | 0.767 celé; 0.963 pod řádkem y=345 px (bez madla) | totéž; bokem symetrické: spony, rukojeť zámku a rohové patky v modelu menší nebo chybí |

Kamera: reprojekční chyby ručních bodů 0.2 až 20 px (c01: 0.9 až 20 px, c02: 0.2 až 4.4 px); u c02 je elevace určena slabě (5 nejlepších řešení má el 18 až 29°) a u c01 jsem horní část víka kvůli madlu v členu „fotka mimo kvádr“ nepočítal (nejhorší je bod „BR cap spodní horní konec“, 20 px). Kamera je odhad, ne dofitování podle modelu. IoU 0.96 pod řádkem je tedy věrohodná, ale i tak jen orientační; počítá se bez horní části víka a bez madla.

## Konkrétní rozdíly (prohlédnuté dvojice foto | model | překryv: c01 celek, c02 celek + výřezy pravého a levého horního rohu)
Odhady mm = pixely / ≈ 1.7 px/mm.
1. c01+c02, nosné madlo: na fotce zdvižené U-madlo (ramena černé, příčka hliník + černý gumový úchop ≈ 145 mm, celková šířka ≈ 94 % šířky těla, výška nad zadní hranou víka ≈ 150 až 160 mm, měřeno na c02). Model: nic. Zásadní.
2. c01+c02, hliníkové tyče a rohové patky: viz 4932478162 (patky ≈ 36 × 49 mm, tyč ≈ 15 až 20 mm, odsazená ≈ 15 mm od stěny); v modelu tenký pásek 4 mm zapuštěný do těla. Viditelný.
3. c01+c02, spony: fotka červená část ≈ 61 × 69 mm (změřeno v c02 vlevo), třmen ≈ 72 mm vysoký. Model ≈ 31 × 44 mm (≈ 50 % šířky, 65 % výšky). Počet 2 a vodorovná poloha sedí; model nemá prohlubeň kolem spony. Viditelný.
4. c01+c02, víko: model plochá deska, 6 mělkých rámečků; fotka 10 kapes (po 5 na polovině), zkosený okraj, žebrované větrání na čele víka, středový výlisek. Viditelný.
5. c01+c02, spodek čela: fotka má vystupující zámkovou šachtu s velkou červenou rukojetí (c02: rukojeť ≈ 95 × 47 mm) a hluboký žebrovaný rám; model hladké čelo a malé očko ≈ 28 × 24 mm, patky 12 mm (c02 vidět rovný spodek modelu proti zalomenému spodku fotky). Viditelný.
6. c01, boční rukojeť (vpravo): fotka červeno-černá rukojeť v pouzdře; model plochý červený obdélník (134 × 34 mm, 5 mm vystupuje). Viditelný.
7. c01+c02, horní plocha víka: při překryvu model nahoře přesahuje fotku (hrana víka ≈ 15 až 25 px výš), ale protože okraj kvádru nahoře je odvozen z kamery s neurčitou elevací, tento rozdíl nehodnotím (neověřeno).
8. Logo: fotka velké logo, model prostý text. Kosmetický.

## Co nelze z fotek posoudit (neověřeno)
Zda je madlo sklopné a kam se sklápí (v modelu i v katalogu není zdvih ani rozměr; katalog zachovává výšku 422 jako u staršího SKU); tloušťky a poloměry; vnitřek, zadní strana a spodek; přesná výška víka vs. kamera (el nejistá); z fotek nelze rozlišit, jestli má revize jiný vnitřek (vložka) než 4932478162.

## Doporučení
Model 4932501784 nepoužívat jako shodu s fotkou, dokud nemá madlo: doplnit zdvižené U-madlo (≈ 94 % šířky těla, úchop ≈ 145 mm, výška ≈ 150 až 160 mm nad víkem), případně sklopnou polohu uvnitř obálky 422 mm. Ostatní doporučení jako u 4932478162 (rohové tyče a patky, spony 54 × 72 mm, zámková šachta, víko s 10 kapsami).
