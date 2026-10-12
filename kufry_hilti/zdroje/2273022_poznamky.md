# Hilti Kufr SF 4(H)-22 prázdný (č. 2273022), 395 × 362 × 119 mm – poznámky k modelu

Model: `kufr_2273022.mjs` (+ společný generátor řady SF `p2284143_zaklad.mjs`, `p2284143_korpus.mjs`, `p2284143_vicko.mjs` (sdílené s 2284143; tento soubor je jen parametrizace L × H × D)), sestavení `node kufry_hilti/vytvor.mjs 2273022` → `modely/2273022.glb` (12 dílů, ~2 800 trojúhelníků, obálka 119 × 395 × 362 mm, odchylka 0/0/0 mm). Náhled `nahled/2273022.html`.
Souřadnice: X = hloubka 119 (čelo s logem do +X), Y = délka 395, Z = výška 362 (nesená poloha, držadlo nahoře), počátek ve středu obálky. Víko = skupina `vicko`, pivot na spodní pantové hraně (x = 19, z' = 5), `extras.osa = [0,1,0]`, `max_uhel = 100`; `--pose vicko=100` otevře (víko se překlopí dopředu a dolů, vnitřek víka je nahoře).
Zadání (Robert): ZAVŘENÁ verze a VNĚJŠÍ pohled; vnitřek hladký / prázdná dutina (stěna 3 mm, bez vložky, bez žeber).

## Fotografie (jen čtena ze scratchpadu `kufry2/<číslo>/`, v repu není; URL v `../fotky_url_vlna2.tsv`)
| soubor | pohled | použití |
|---|---|---|
| `2273022/c01.jpg` (L137214, 1200 × 940) | čelo zavřeného kufru (víko s logem), držadlo a 2 západky nahoře | JEDINÝ zdroj tvaru. **Generická fotografie – stejný soubor (md5) mají 2284143, 2273022 i 2294834**; její poměr 1,277 neodpovídá ani 444/395 (1,124) ani 395/362 (1,091). |
| `2329229/c01–c04.jpg` (L128480, L128481, L128481_compartments, L128482) | čelo a otevřený pohled shora jiného kufru (495 × 395 × 149) | **jen orientace** (odvozeno, rozměry z něj nejsou): pant je řada ~7 článků na hraně mezi víkem a korpusem, na protější hraně madlo na víku + madlo a 2 černé západky na korpusu, víko i korpus jsou vany se širokým okrajem, vnitřek víka hladký s mělkými výstupky. Tvar víka/západek/pantu je tedy převzat kvalitativně, rozměry a proporce jsou podle tohoto kufru. |

## Jak je z fotografie odvozena geometrie (změřeno vs. odhad)
- **Převod px → mm je NEUNIFORMNÍ:** celá šířka fotografie (px 0..1199) = délka 395 mm (×0,329 mm/px), celá výška (py 0..939, včetně vrchu držadla) = výška 362 mm (×0,386 mm/px). Fotografie má jiný poměr stran než kufr, takže se prvky oproti ní vodorovně/svisle poměrově zmenšují nebo zvětšují (logo, západky, držadlo, polštáře). Absolutní míry těchto prvků u skutečného kufru proto **nejsou ověřeny**.
- **Změřeno z fotografie (px, řádkový/sloupcový sken):** obrys (silueta, horní "ramena", bok s mírným rozšířením pásu logem py 330–590, zkosené spodní rohy), výřez držadla (vnější okraj černého rámu px 393–806, spodek py 143) a okno (průhledný lichoběžník py 66–123, px 448–751 → 508–691), poloha západek (px 157–292 / 907–1042, py 15–79), polštáře (px 52–280 / 919–1147, py 213–265 a 648–700), pásy čela (horní zkosení py ~60–128, zapuštěný pás s logem py 345–568 se zkosenými přechody 315–345 a 568–600, spodní zkosení py 860–900, dolní lichoběžníková prohlubeň py 800–939, px ±190 → ±272 od středu), logo HILTI (písmena H I L T I po obdélnících, px 161–1036, py 394–517).
- **Odhad / zvoleno (z fotografie nezjistitelné):** hloubka dělení víko/korpus (víko 40.5 mm = 34 % hloubky, dělicí rovina x = 19); spára 0,6 mm; tloušťka stěn 3 mm; hloubky reliéfu čela (horní zkosení 8 mm, zapuštění pásu s logem 4 mm, spodní zkosení 7 mm, dolní prohlubeň 8 mm pod plochou, polštáře 2,5 mm vysoké, zkosení čelní hrany 8 mm hluboké × 15 mm široké – světlé boční pruhy na fotografii); zaoblení zadní hrany korpusu 8 mm; hloubka černého rámu držadla (víko 40.5 mm, korpus ~66 mm); hloubka západek (blok od x = 16 dopředu).
- Dutina: víko i korpus jsou duté vany otevřené v rovině dělení, vnitřek hladký (strop/dno rovné, stěna 3 mm); okno držadla je průchozí celou hloubkou (v obou polovinách).

## Výsledky porovnání (`kufriky_cloud/srovnani/2273022/`, nástroj `nastroje/porovnej_celo.mjs --dist 8000`)
| ukazatel | hodnota |
|---|---:|
| IoU obrysu čela (render oříznutý na obrys, roztažený na rozměr fotografie, téměř ortografický) | **0,987** |
| medián odchylky levého/pravého okraje obrysu po řádcích | 1 / 1 px |
| maximální odchylka okraje (rohy, nahoře u západek) | 76 / 56 px z 1200 |
| landmarky (`landmarky.json`, rozdíl model − foto v px fotografie; x0,x1,y0,y1): logo | [0, 0, 1, -1] |
| okno držadla | [1, -7, 4, -1] |
| západka vlevo / vpravo | [13, -4, 2, 0] / [5, -9, 3, 1] |
| vnější rám držadla | [12, -11, 1, -1] |
Pozn.: IoU je vysoké částečně z konstrukce (obrys modelu je z téže fotografie). Protože fotografie není tohoto kufru, nejde o ověření rozměrů, jen o ověření, že model věrně opakuje její tvar po nuceném roztažení na rozměry z hilti.cz. Dvojice foto | model | překryv byla prohlédnuta (logo, madlo, západky, polštáře, pásy). Render z `iso_zavreny.png` a `iso_otevreny_vicko100.png` jsou vlastní.

## Neověřeno / nemodelováno
- **Zadní strana, spodek, boky:** na fotografii nejsou. Zadní stěna a spodek jsou rovné (obrys čela vytažený do hloubky, zadní hrana zaoblena R 8), boky bez detailů; **nožky, stohovací prvky, spodní žebra nemodelovány**.
- **Pant:** pivot je na spodní hraně v rovině dělení; fyzické články pantu (u příbuzného 2329229 ~7 článků) **nemodelovány** (neověřitelný tvar, jen spára mezi víkem a korpusem).
- **Západky** jsou pevné černé bloky (patří korpusu), neotvírají se; jejich kapsy v čele víka (světlejší zkosené plošky kolem nich na fotografii) nemodelovány; mechanika západky neznámá. Drobné prvky (tečka na západce, očko u okna držadla, logo na madle, textura povrchu/zrnění, nápisy, šipky) nemodelovány.
- Madlo: černý rám se skosenými rameny a oknem je plný hranol (v obou polovinách), tvar a hloubka okna zjednodušeny; zda je okno průchozí i uvnitř reálného kufru (stavba madla ve dvou polovinách), nelze z fotografie rozhodnout.
- Reliéf čela (zapuštěný pás, polštáře, prohlubeň) vychází jen z odstínů fotografie (světlé/tmavé plošky) – hloubky a směry (vyvýšení vs. zapuštění) jsou **výklad stínování**, ne měření.
- Rozměr 2273022 (395 × 362 × 119) a 2284143 (444 × 395 × 122) jsou z hilti.cz; stejný vzhled řady SF u menšího kufru je **předpoklad** (fotografie je pro oba stejný soubor): tvar je roztažen na 395 × 362, takže poměry prvků jsou odlišné od 2284143 jen díky jinému měřítku.
- Barva: jediná červená `cervena` (korpus, víko), černá `cerna` (madlo, západky), bílá `bila` (logo); odstín není kalibrován na fotografii.
- Rozměry: platí z hilti.cz (D × Š × V = 395 × 362 × 119); zda jde o vnější rozměry kufru, stránka výslovně neříká.
