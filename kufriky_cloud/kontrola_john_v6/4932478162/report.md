# Kontrola věrohodnosti tvaru: 4932478162 Box na nářadí XL (Johnův model v6)

Model: `kufriky_john/nahled-modely-v6/modely/4932478162.glb` (obálka 394 × 554 × 422 mm, sedí). Nic v repu nebylo upraveno, jen vznikla tato složka.
Fotografie (jen URL, kopie v repu nejsou): c01 = Hero_1 `https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932478162--Hero_1.jpg?width=1200`.
Pomocné (jen pro vnitřek, jen ve scratchpadu): Feat_1 a Feat_2 `.../hi/4932478162--Feat_1.jpg`, `--Feat_2.jpg` (otevřené víko). Další použitelné pohledy nebyly (App_ fotky jsou aplikační, nepoužito).
Soubory: `c01_render.png`, `c01_kamera.json`, `doplnek_shora_render.png`, `doplnek_bez_vika_render.png` (jen náš model, ne srovnání), `shoda_glb_obou_XL.json`.

## Shoda se SKU 4932501784
GLB 4932478162 a 4932501784 jsou **geometricky identické**: binární blok (vrcholy, normály, indexy) je shodný bajt po bajtu, JSON se liší jen v poli `asset.extras.sku` (viz `shoda_glb_obou_XL.json`). Ověřeno porovnáním obou souborů. Fotky ale ukazují, že SKU 4932501784 má zdvižené nosné madlo, které 4932478162 na své fotce nemá (viz report 4932501784).

## Hodnocení: S VÝHRADAMI
Hlavní hmota, rozložení (dvě přední spony, boční rukojeti, spodní zámek, 4 rohové ochrany, víko s kapsami) a obrys odpovídají fotce (IoU 0.943 s kamerou nezávislou na modelu). Tvar je ale v podstatě hladký kvádr s drobnými červenými nášivkami: chybí viditelné hliníkové nosné tyče s rohovými patkami, boční výřezy, tvarované víko a spodní zámková šachta, spony jsou o třetinu menší.

## Tabulka foto | IoU | nejdůležitější rozdíly
| foto | kamera | IoU | nejdůležitější rozdíly |
|---|---|---|---|
| c01 (zepředu zleva-zprava, az ≈ 21°, el ≈ 17°, fov ≈ 18°) | ruční body (8 bodů na rohových ochranách) + obrys fotky vs. KVÁDR obálky z katalogu, nezávislé na tvaru modelu | 0.943 | chybí hliníkové tyče a rohové ochrany (viditelný), boční výřezy 13 mm × 250 mm vyplněné (viditelný), spony ≈ 60 % velikosti (viditelný), spodní zámková šachta a nohy (viditelný), víko bez zkosení, bez žeber (kosmetický až viditelný) |

Kamera: reprojekční chyby ručních bodů 5 až 16 px (≈ 3 až 9 mm) (z rohových ochran jen odhadnuto ±15 mm). 5 nejlepších řešení se shoduje (az 19 až 21°, el 17°, fov 14 až 19°). Kamera je odhad, ale ne dofitovaná podle modelu.

## Konkrétní rozdíly (prohlédnuté: celá dvojice foto | model | překryv a 4 výřezy: levý a pravý horní roh, levý a pravý spodní roh)
Odhady mm = pixely / ≈ 1.7 px/mm.
1. Rohové ochrany + hliníkové tyče: fotka má 4 černé rohové patky (nahoře ≈ 36 × 49 mm) spojené leštěnou hliníkovou tyčí (≈ 15 až 20 mm široká, délka ≈ 250 mm), která stojí ≈ 15 mm od stěny (na siluetě je v c01 vlevo bílá mezera mezi tyčí a tělem, y ≈ 380 až 790 px). Model má tenký pásek roh-kov ≈ 4 mm zapuštěný do stěny a těleso vyplňuje celou obálku; obrys modelu tak přesahuje fotku vlevo o ≈ 55 px (≈ 33 mm včetně tyče a mezery) po výšce ≈ 250 mm. Viditelný, na obou stranách.
2. Spony (2 ks, levá změřena): fotka červená část ≈ 54 × 72 mm, třmen ≈ 65 × 89 mm, uložena v prohlubni čela. Model: červená část ≈ 31 × 50 mm (≈ 58 % šířky, 70 % výšky), třmen ≈ 41 × 69 mm, bez prohlubně; svislá poloha se liší o ≈ 10 až 20 mm. Počet (2) a vodorovná poloha sedí. Viditelný.
3. Víko: fotka má zkosený okraj víka, na čele víka středovou nástavbu se žebrovým větráním (≈ 57 × 42 mm), šroub a výlisek; na horní ploše 10 kapes (2 × 5: 2 malé, 1 dlouhá, 2 malé na každé polovině). Model: plochá deska bez zkosení, bez větrání, 6 mělkých rámečků (3 na každé polovině) a malý červený štítek uprostřed. Viditelný (kapsy 10 vs. 6).
4. Čelo dole: fotka má spodní zámkovou šachtu (≈ 160 mm široká) s černou žebrovanou lištou a velkou červenou rukojetí zámku (≈ 79 × 67 mm), pod čelem nohy ≈ 30 mm. Model: hladké čelo, červené očko zámku ≈ 28 × 24 mm, patky jen 12 mm. Viditelný až zásadní pro vzhled spodku.
5. Spodní okraj a nohy: fotka má předsunuté nohy, zalomení a výřezy; obrys modelu je u pravé nohy až ≈ 25 px (≈ 15 mm) výš než fotka (noha ve fotce sahá níž). Kosmetický.
6. Boční rukojeti: fotka velká červeno-černá rukojeť v pouzdře na pravé boční straně (≈ 60 × 120 mm, zešikmené, hloubka neověřena), model plochý červený obdélník (≈ 134 × 34 mm, 5 mm). Viditelný.
7. Logo: fotka velké logotypové „Milwaukee PACKOUT“, model text MILWAUKEE/PACKOUT prostým písmem a menší. Kosmetický.
8. Čelní prolis/zadní stupně: fotka čelo je stupňovité (vystouplý střed pod víkem, boční zahloubení spon), model plochý. Viditelný.

## Doplněk: vnitřek (z oddělených fotek Feat_1/Feat_2 s otevřeným víkem, z modelu se skrytým víkem)
Prohlédnuto: Feat_1, Feat_2 (fotky) a `doplnek_bez_vika_render.png` (model, jiný úhel, jen orientační). Odnímatelná vložka je na fotce ≈ polovinu šířky těla (podél osy Y) a skoro celou hloubku, s dělicím žebrem; v modelu je vložka na plnou šířku (436 mm) a jen 112 mm hluboká u zadní stěny. Dno na fotce má několik (≥ 3) vyvýšených podložek, model rovné dno. Zásadní pro vnitřek (viditelné jen při otevřeném víku, model víko neotevírá). Neověřeno přesnými rozměry.

## Co nelze z fotek posoudit (neověřeno)
Tloušťky a poloměry (nekótované); zadní strana, spodek a levá strana (nevidět); přesná hloubka a počet vyvýšenin dna; vůle a profil spojů PACKOUT; hloubka kapes na víku; skutečná výška hliníkových tyčí vůči rohovým patkám (z jen odhad ±15 mm); barva modelu (render je světlejší).

## Doporučení
1. Zpřesnit rohy: 4 rohové ochrany + stojící hliníkové tyče (≈ 20 mm, 13 mm od stěny) a vyříznout boční mezery. 2. Spony zvětšit na ≈ 54 × 72 mm (červená část) a zapustit do prohlubně. 3. Spodní zámkovou šachtu s rukojetí (≈ 160 mm široká) a předsunuté nohy. 4. Víko se zkosením, větráním a 10 kapsami. 5. Vložku přerozměrovat podle Feat_1 (≈ polovina šířky, skoro celá hloubka).
