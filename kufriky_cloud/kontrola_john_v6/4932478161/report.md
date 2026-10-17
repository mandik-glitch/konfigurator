# Kontrola věrohodnosti tvaru: Johnův model v6, SKU 4932478161 (Pojízdná bedna na nářadí, 609×965×401)

Fotky: Hero_1..6 z milwaukeetool.eu (`…/hi/4932478161--Hero_N.jpg?width=1200`; nejsou v repu). Model nemá pohyblivé části, víko se neotevírá, madlo je složené.

**Hodnocení: S VÝHRADAMI.** Silueta a proporce sedí: výška ≈395 vs 401 mm, délka těla ≈40 mm větší, kolo má stejný průměr na stejném místě (střed Y ≈366 vs 367 mm). Detaily chybí nebo jsou jiné; pro orientační náhled stačí, pro věrný model ne.

Kamery: c06 téměř boční, měřítko 1,162 px/mm z délky obálky 965 mm, elevace 8° odhad (dofit obrysu dal 9,8°). c01 bez nezávislých bodů, kamera jen dofitovaná na obrys (horní mez). Johnovy GLB mají 16bitové indexy, použita upravená kopie renderu ve scratchpadu.

| Foto | IoU (kamera z rozměrů fotky) | IoU (z obrysu, horní mez) | Poznámka |
|---|---|---|---|
| c06 (boční, madlo složené) | 0,863 | 0,927 | západky, víko bez kapes/loga/okraje, chybí koncový blok u kol |
| c01 (šikmo, madlo vysunuté) | – | 0,956 od x=235 px (celá fotka 0,928) | vysunuté madlo je jiný stav, ne chyba |
| c05 (nakloněná na kolech) | – | – | póza nereprodukována, jen vizuální srovnání |
| c02–c04 | – | – | víko otevřené, vysunuté madlo |

Prohlédnuté trojice: c06, c01, c05, detaily levého a pravého konce, c03.

| # | Rozdíl (c06, měřítko 1,162 px/mm, ±5 %, polohy ±25 mm) | Velikost | Závažnost |
|---|---|---|---|
| 1 | Poloha západek: skutečné středy Y ≈ −290 a +219 mm (rozteč ≈510 mm), model ±304 mm (rozteč 609 mm) | 14 a 85 mm | viditelný |
| 2 | Velikost západek: páčka ≈75×65 mm, třmen ≈93 mm; model 53×45 mm, 70 mm | ≈0,7× | viditelný |
| 3 | Víko: skutečné s přečnívajícím okrajem, 2×6 mělkých kapes, červená plaketa s logem ≈115×45 mm, délka ≈910 mm; model plochá deska 951 mm | +41 mm, vzor | viditelný |
| 4 | Čelní stěna: vybrání pod víkem, výlisky kolem západek, stupňovitý spodek; model plochá s rýhou | – | viditelný |
| 5 | Černý koncový blok nad koly ≈100×120 mm chybí | ≈100×120 mm | viditelný |
| 6 | Kolo: průměr a poloha sedí; skutečné s pneumatikou, 5paprskovým diskem; model hladký disk; šířka neověřena | – | kosmetický |
| 7 | Model 4 sloupkové nohy 21×21×35 mm; skutečný spodek široké patky | – | viditelný |
| 8 | Složené madlo drátěný chromový rám kolem konce víka; model černý blok 315×8×45 mm; vysunuté madlo model nemá | – | viditelný / neověřitelné |
| 9 | Levý spodní roh zkosený, model ostrý | ≈15 mm | kosmetický |
| 10 | Logo plochý text | – | kosmetický |

Neověřeno: vnitřek (c02/c03 hluboká vana a vyjímatelná vložka), šířka kol, druhý dlouhý bok, spodek, zdvih a kinematika madla, poloha c05.

Doporučení: přesunout a zvětšit západky (středy Y ≈ −290 a +219, páčka ≈75×65 mm); doplnit okraj víka, kapsy a plaketu, zkrátit víko na ≈910 mm, přidat koncový blok u kol; kolo s pneumatikou, nohy nahradit patkami; vysunuté madlo a otevírání víka řešit až po opravě tvaru.
