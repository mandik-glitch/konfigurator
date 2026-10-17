# Kontrola věrohodnosti tvaru: Johnův model v6, SKU 4932471723 (Kompaktní box na nářadí, 411×249×330)

Zdroj: jedna fotka c01 = Hero_1, https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932471723--Hero_1.jpg?width=1200 (fotka není v repu).

**Hodnocení: s výhradami.** Obálka, proporce těla, poloha spony na krátkém čele, otvor dole na čele i rovná horní deska víka odpovídají fotce (IoU 0,952 mimo oblast držadla). Držadlo je ale zásadně špatně, spona je asi 3× menší a víko je mnohem mělčí a jinak členěné.

Kamera: azimut 115,1°, elevace 17,9°, fov 12,3°, 4 ruční body, rms 6 px (8 neznámých, 8 rovnic, fit téměř přesně určený). Nezávislá kontrola: predikovaná přední pravá svislá hrana sedí s fotkou na ±15 px. Kamera nebyla dofitována podle obrysu modelu; body leží na obrysových rozích obálky, takže IoU na krajích je částečně dané konstrukcí a není to důkaz tvaru.

| Foto | IoU | IoU bez držadla |
|---|---|---|
| c01 | 0,868 | 0,952 |

Prohlédnuté dvojice: celek c01, výřez čela, výřez horní desky víka, výřez pravého boku, drátový model obálky.

| # | Prvek | Fotka | Model | Velikost | Závažnost |
|---|---|---|---|---|---|
| 1 | Nosné držadlo | vztyčený rám přes délku víka, čep nad sponou, vyčnívá asi 75 mm, rozpětí asi 300 mm | `vyklopne-drzadlo-sklopene` = plochý pás 157×51×5 mm, čepy X=±72, v renderu neviditelný | jiný tvar, rozměr i poloha čepů | zásadní |
| 2 | Spona na čele | červená asi 90×95 mm se zuby, kovový třmen asi 95 mm, pod ní zapuštěný černý štít | červená 31×44 mm, 2 kovové proužky, bez štítu | asi 3× menší | viditelný |
| 3 | Plášť víka | asi 45 mm, zešikmené rameno, „uši“ na předních rozích | 20 mm, ostré rohy | asi 25 mm | viditelný |
| 4 | Horní deska víka | 4 hluboké kapsy a podélný pruh se štítkem | 6 vystouplých rámečků (reliéf ven) a červený obdélník 16×24 mm | jiný počet i smysl reliéfu | viditelný |
| 5 | Rohové lišty | čelo hladké | `celo-roh-ochrana` vyčnívá 10 mm před čelo | 10 mm | viditelný |
| 6 | Spojka dole na čele | červený kroužek Ø asi 42 mm v zapuštěném sedle | červený zaoblený čtyřúhelník 29×24 mm bez sedla | poloha sedí ±10 mm | viditelný |
| 7 | Boky | tvarované, stupňovitý spodní okraj | rovné hladké stěny | asi 10 mm | kosmetický |
| 8 | Nožky | spodní příruba se zaoblenými rohy | 4 hranaté patky 31×51×12 mm a 6 lišt | tvar | kosmetický |
| 9 | Logo | větší, výš | malý text | asi 40 mm | kosmetický |

Nelze posoudit (neověřeno): pant víka, zadní stěna, levý bok, spodek (na c01 nejsou vidět); vnitřek (model má 3mm přepážku nedoloženou; další fotky výrobce Feat_2/4/5 naznačují víc přepážek a vyjímatelnou vložku, k měření nepoužito); tloušťky stěn, poloměry; jak vypadá sklopené držadlo. Dalších fotek: `…/hi/4932471723--Feat_N.jpg?width=1200`, N = 1 až 5.

Doporučení: držadlo předělat jako rám s čepy nad sponou; sponu zvětšit na asi 90×95 mm a doplnit tmavý štít; víko s pláštěm asi 45 mm a 4 kapsami (reliéf dovnitř); odstranit rohové lišty před čelem; doplnit sedlo spojky.
