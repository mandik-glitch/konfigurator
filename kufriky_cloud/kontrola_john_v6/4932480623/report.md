# Kontrola věrohodnosti tvaru: Johnův model v6, SKU 4932480623 (Skříň s předními dvířky, 508×381×381)

Zdroje fotek (nejsou v repu): c01 = Hero_1, c02 = Hero_2, c03 = Hero_3 z https://static.milwaukeetool.eu/remote.axd/milwaukee-media-images.s3.amazonaws.com/hi/4932480623--Hero_N.jpg?width=1200

**Hodnocení: s výhradami.** Obálka, těleso, hloubka dutiny a hlavní uspořádání (čelní dvířka, červená spona dole, horní víko) sedí. Víko, členění dvířek, spona, nožky a podlaha dutiny se ale od fotek výrazně liší.

| Foto | IoU | Kamera |
|---|---|---|
| c01 (zpředu-zleva-shora) | 0,945 | rms 22 px, slabší |
| c02 (čelní) | 0,957 | rms 9 px, středně spolehlivá |
| c03 (shora, dvířka odklopená) | 0,894 | rms 38 px, jen orientační odhad |

Kamery z ručně změřených bodů, ne dofitované podle modelu. Prohlédnuté dvojice: c01 celek a výřez, c02 celek a výřez, c03 (model bez dvířek vedle fotky; model nemá pózu pro otevřená dvířka, porovnána prázdná dutina po skrytí uzlů `dvere-*`).

| # | Prvek | Fotka | Model | Velikost | Závažnost |
|---|---|---|---|---|---|
| 1 | Plášť víka | hluboký asi 58 mm, přesahuje tělo o 5–10 mm, zkosené horní rohy asi 30 mm, boční „uši“ | strop 23 mm, ostré rohy | asi 35 mm | viditelný |
| 2 | Horní deska víka | 8 kapes (2×4) + středový pruh s červenou západkou a kulatým otvorem | 8 skupin úzkých štěrbin a červený obdélník 23×33 mm | jiný tvar | viditelný |
| 3 | Členění dvířek | 3 panely, boční asi 99 mm, střední asi 205 mm | 1 panel 442 mm se žebry | dělicí hrany asi 75 mm jinde | viditelný |
| 4 | Svislá poloha dvířek | z asi 50–335 mm | z 108–358 mm | spodní hrana asi 55 mm výš, horní asi 20 mm | viditelný |
| 5 | Spona | červená asi 85×36 mm (z 61–99), tmavý lichoběžníkový kryt asi 137 mm | červená 91×18 mm (z 109–127), bez krytu | asi 50 mm výš | viditelný |
| 6 | Podlaha dutiny | u prahu asi 45–55 mm nad zemí | plná deska do z=106 | asi 55 mm | viditelný |
| 7 | Vnitřek | boční svislé kolejnice se zářezy, prolisy zadní stěny, práh s dorazem | hladká dutina | chybí detaily | kosmetický až viditelný |
| 8 | Nožky a spodní lišta | nožky Y≈±(138–186), 3 červené jazýčky pod dvířky | 4 nožky Y=±(188–253), jazýčky chybí | asi 50–65 mm | viditelný |
| 9 | Šířka těla | užší než lem víka, zužuje se dolů | stejně široké jako víko | 6–14 mm | kosmetický |
| 10 | Pravý bok | dvě svislé kapsy u víka, zešikmené stěny | hladká stěna | tvar | kosmetický |
| 11 | Logo | asi 170 mm široké | asi 108 mm | asi 60 mm | kosmetický |
| 12 | Dvířka otevřená (c03) | zvednutá do vodorovné polohy pod víkem | zavřená, bez pózy | – | neposouzeno |

Nelze posoudit (neověřeno): levý a zadní bok, spodek, pant dvířek, kinematika otvírání, tloušťky stěn, vnitřní rozměry. Míry z c03 jsou jen orientační. Odečty mm z fotek mají nejistotu zhruba ±10 %.

Doporučení: víko prohloubit na asi 58 mm se zkosenými rohy; dvířka na 3 panely 99/205/99 mm a posunout na z 50–335; sponu zvětšit a doplnit kryt; podlahu dutiny snížit z 106 na asi 50 mm; nožky posunout dovnitř a doplnit jazýčky; tělo zúžit oproti víku.
