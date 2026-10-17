# Kontrola věrohodnosti tvaru: Johnův model v6, SKU 4932464078 (Pojízdný box s výsuvným držadlem, 561×472×530)

Fotky: Hero_1..9 z milwaukeetool.eu (URL v `kufriky_john/fotky/index.tsv` pro jiná SKU; pro toto SKU `…/hi/4932464078--Hero_N.jpg?width=1200`; fotky nejsou v repu). Model nemá pohyblivé části, víko se neotevírá, madlo je složené.

**Hodnocení: NEVĚROHODNÝ.** Obálka sedí, proporce a charakteristické prvky ne.

Kamery: c01 a c02 z 5 ručně změřených rohů (3D souřadnice z katalogu a z fotek, ne z modelu; hlavní bod uvolněn, zbytky 11,5 a 7,4 px; jen odhad). c05 jen odhad (az 180°, el 8°, měřítko z předpokladu, že okraj víka je 561 mm). Sloupec „z obrysu“ je horní mez, ne důkaz. Johnovy GLB mají 16bitové indexy, sdílená stránka renderu je nenačte, použita upravená kopie ve scratchpadu.

| Foto | IoU (kamera z bodů) | IoU (z obrysu, horní mez) | Poznámka |
|---|---|---|---|
| c01 (šikmo, madlo složené) | 0,839 | 0,870 | výška, madlo, šířka víka, spodek čela, západky, kola |
| c02 (šikmo, madlo vysunuté) | 0,754 | 0,796 | vysunuté madlo je jiný stav, ne chyba |
| c05 (zezadu) | 0,915* | 0,926* | *jen řádky y ≥ 790 px |
| c03, c04, c06–c09 | – | – | otevřené víko, sestavy s kartonem nebo jiné výrobky, degenerovaný fit |

Prohlédnuté trojice: c01, c02, c05, c09, detaily c03/c04.

| # | Rozdíl | Foto | Velikost | Závažnost |
|---|---|---|---|---|
| 1 | Výška od podlahy po víko ≈445 ± 15 mm, model 523–530 mm (katalogových 530 mm je výška po horní hranu složeného madla) | c05, c01, c02 | +80 mm (+18 %) | zásadní |
| 2 | Složené madlo vyčnívá ≈90–105 mm nad víko, šířka ≈350–390 mm, sloupky ≈45 mm; model proužek ≈7 mm, šířka 257 mm, sloupky 18–20 mm | c01, c02, c05 | −90 mm výška, −130 mm šířka | zásadní |
| 3 | Šířka: víko ≈561 mm, tělo ≈520 mm, vnější strany kol ≈580 mm; model víko i tělo 493 mm, kola 561 mm | c05, c01, c02 | víko −68 mm, tělo ≈ −27 mm | viditelný |
| 4 | Kola: běhoun ≈85–90 mm široký (model 34 mm), průměr sedí ≈225 vs 228 mm; skutečné s terénním vzorkem | c05, c01, c02 | −55 mm šířka | viditelný |
| 5 | Chybí vystouplý spodní panel čela a chromová drátěná smyčka (≈175 mm) | c01, c02 | celý prvek | viditelný |
| 6 | Rohové hliníkové lišty ≈36 mm × 330 mm s černými hlavicemi; model linky ≈5 mm | c01, c02 | −30 mm | viditelný |
| 7 | Dvě západky s chromovým třmenem sedí počtem i zhruba polohou; model ≈1,6× menší | c01, c02 | −20×27 mm | viditelný |
| 8 | Model má 4 nohy 21×21×32 mm; skutečný box nohy nemá, kola sahají ≈35 mm pod základnu | c01, c02, c05 | 32 mm | viditelný |
| 9 | Boční madlo skutečné červené s gumou; model plochý rámeček 165×34×5 mm | c01, c02 | tvar | viditelný |
| 10 | Víko: 8 mělkých kapes, mřížka, červená plocha; model drážky a 2 červené čtverečky | c01, c02 | vzor | viditelný |
| 11 | Zadní stěna žebrovaná s chromovým držákem; model hladký | c05 | – | kosmetický |
| 12 | Logo plochý text | c01, c02 | – | kosmetický |

Neověřeno: vnitřek a otevírání víka (c03/c04 ukazují vyjímatelnou vložku), levý bok a spodek, zdvih vysunutého madla, poloměry, hloubky kapes, tloušťky stěn, přesná poloha západek (±25 mm). Míry jsou přepočet z fotek s nejistotou ≈ ±5 %, u výšek ±15 mm.

Doporučení: opravit výšku (tělo s víkem ≈445 mm, madlo ≈90–100 mm nad víkem do 530 mm); madlo 350–390 mm široké se sloupky ≈45 mm; víko ≈561 mm, tělo ≈520 mm, kola 85–90 mm; odstranit nohy, doplnit spodní výstupek čela se smyčkou, lišty ≈36 mm a větší západky; až potom vzor víka, boční madlo a logo.
