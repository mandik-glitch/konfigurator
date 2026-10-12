# Hilti Kufr 2-tools (M) SF/SI+TE (2329206) – poznámky k modelu

Model: `kufr_2329206.mjs` (+ `p2329206_zaklad.mjs`, `p2329206_korpus.mjs`, `p2329206_vicko.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2329206` → `modely/2329206.glb` (43 dílů, ~4 100 trojúhelníků, 0,18 MB, obálka 461 × 595 × 175 mm, odchylka 0/0/0 mm, střed 0/0/0). Katalog: 595 × 461 × 175 mm (`vrtacky_hilti.csv`, hilti.cz; vnitřní rozměry a hmotnost hilti.cz neuvádí). Souřadnice: X = hloubka 461 (čelo s madlem a západkami do +X), Y = délka 595, Z = výška 175, počátek ve středu obálky; v kódu se výšky píší jako z' (od spodní plochy, 0..175).
Zadání (Robert): hlavní je **ZAVŘENÁ verze a vnější pohled; vnitřek zjednodušen (hladká prázdná dutina), dodělat později.** Víko = skupina `vicko`, pivot na pantové hraně (X −223,7, z' = SP), `extras.osa = [0,−1,0]`, `max_uhel 140`; `--pose vicko=105` otevře jako na fotografii.

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL v `../fotky_url_vlna2.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L128476, 1200 × 940) | **zavřený kufr přesně shora** (víko nahoře, čelo s madlem nahoře na snímku), ořez těsně na obrys | měření všech půdorysných rozměrů (1200 px = 595 mm → 0,496 mm/px vodorovně = Y; 940 px = 461 mm → 0,490 mm/px svisle = X; vpravo na snímku = −Y); porovnání `shora` |
| c02 (L128477, 933 × 1200) | **otevřený kufr** (víko ~105°) shora s pohledem zepředu, prázdná vložka | kamera z 6 ručních bodů + obrys; porovnání `otevreny-c02` |
| c03 (L128477_compartments) | **tentýž záběr jako c02** s číslovanými přihrádkami 1-4 | porovnání `otevreny-c03` (stejný obrys, tedy nejde o nový úhel) |
| c04 (L128478, 930 × 1200) | tentýž záběr s vloženým nářadím (TE 6-22, SF 6H-22, C 6-22, baterie) | porovnání `otevreny-c04`; nářadí leží uvnitř obrysu |
Žádná fotografie není z boku, zezadu ani zespodu, žádná nemá kóty. Z c01 jsou měřitelné jen půdorysné míry vrchní plochy; **všechny výšky (dělicí spára, sklony, reliéf) jsou odhad.**

## Změřeno z c01 (±1,5 mm; mapování px → mm viz `p2329206_zaklad.mjs`: `pX`, `pY`)
- Obrys půdorysu (maska c01): čelní hrana X 223,6 (py 14), rovná do Y ±220, pak zkosený roh s mezibody (px/py 170/18, 100/25, 54/36, 30/42, 14/48, 7/60) k boku; šířka těla 589 mm, **boční vybouleniny** do ±297,5 mm v pásu X −58,8…78,5 (py 310…590, 2,5 mm na stranu); zadní část kufru (X < −201, py > 880) užší o ~12 mm; zadní hrana X −228 uprostřed (|Y| < 124) a −230,5 na krajích (články pantu, c01 py 934/939). Zaoblení zadních rohů ~10 mm.
- Madlo: průchozí **bílé okno** (lichoběžník px 448..750 × py 66..125, zúžení od py 80; X 169…198, Y ±75 → ±51), šedý rám kolem (px 383..814, py 0..75, zúžení k py 143), černá rukojeť u čela (px 400..800, py 0..70). Čelní hrana červeného víka stoupá k madlu (px 300 → 385, py 16 → 1).
- Západky: černé bloky v kapsách čelní hrany (px 157..292 a 905..1045, py 15..77 → Y ±152,5…219,5, X 192,7…223,1), kapsa px 131..299, py 15..100.
- Víko shora: čelní „plató“ končí v py 130 (sklon 54 mm od čela), po stranách pás ~47 mm; **drážka přes celou šířku** py 320..600 (stěny 15 mm: py 320-350 a 570-600; dno py 350..570) s bílým logem HILTI; zadní plató od py 600 do 800 (zadní sklon 34 mm, py 800..870); čtyři stohovací desky se sraženými konci (px 50..277 / 920..1147, py 210..265 a 648..698).
- Logo HILTI: 11 bílých obdélníků vektorizovaných z masky c01 (px 161..1037, py 395..518); tloušťka 0,5 mm (jen ploška).
- c02: konce pantu (62, 548) a (862, 548) px, zámky ve vzdálenosti (135/243, 690/800; py 1127) px – použito jako landmarky (`landmarky_2329206_c02.json`).
- Barvy z fotografií: červená těla (205, 32, 43) ≈ materiál `cervena` (201, 28, 47) – odpovídá; černé madlo/západky/vložka (15-25) → `cerna_mat`; šedý rám (63-67) → `seda` (82); logo 255 → `bila` (231, materiály v `glb.js` se nemění).

## Odhad (z fotografií nezjistitelné; hodnoty v kódu)
- **Dělicí spára víko/korpus z' = 90 mm** (`SP`, env `KUF_SP`): žádný boční pohled. Fit kamery na c02 je k ní téměř slepý (IoU 0,975 / 0,979 / 0,977 / 0,976 / 0,976 pro SP 70 / 85 / 100 / 115 / 130), nepatrné maximum kolem 85-100; hodnota 90 je kompromis, neověřeno. Hloubka víka tedy 85 mm (do horní plochy 175), hloubka korpusu 90 mm.
- Výšky víka: horní plocha skořepiny z' 163 (dno drážky s logem), plató 172, vrch stohovacích desek 175 (= katalog), sklon koruny tedy jen 9 mm na 54 / 47 / 34 mm; hloubka drážky 9 mm; výška desek 3 mm. Všechno odhad (podle odstínů na c01).
- Stěny: 3,5 mm (korpus), 3 mm (víko); dno vnitřní vložky z' 9; spodní hrana zkosená 4,5 mm. Tvar spodku, nožky, žebra dna, boky pod víkem – **neověřeno** (žádná fotografie).
- Hloubka kapes západek (do X 181,5), svislé stěny kapes, tloušťka rámu madla a rukojeti (z' 166-171,5), druhé madlo korpusu (červený držák z' 72-89,5 + černá příčka) – odhad; okno madla je modelováno jako 175 mm dlouhý šachtový průchod (na fotografii je jen bílé okno).
- Počet a rozteč článků pantu (7 po ~81 mm; na c02 je víc menších článků), poloměr 6,8 mm (uprostřed 5,6 mm, aby seděl obrys c01 na zadní hraně).
- Zadní plató: hrana se zkosenými rohy v c01 (py 800/835) zjednodušena na přímku py 818; boční svah zadní části 24 mm podle dolní části c01.
- Vypouklé „bulge“ boků je v modelu v celé výšce víka i korpusu; z c01 nelze říct, v jakém rozsahu z' ve skutečnosti je.

## Neověřeno / zjednodušeno
- **Vnitřek zjednodušen, nedokončeno:** korpus = červená vana + hladká černá vložka (rovné dno, svislé stěny), **chybí** všech 4 přihrádky vložky (c02-c04: tvarované kapsy pro vrtací kladivo, vrtačku, baterie a nabíječku), bílé číslice, vnitřní žebrování víka (c02 ukazuje reliéf desek a drážky zevnitř), vnitřní strana západek a drátů. Víko je dutý hladký plášť.
- Západky jsou **pevné díly** (černé bloky; na korpusu v otevřené poloze a znovu na víku v zavřené poloze – po otevření víka zůstane blok u víka, ne překlopený); jediný pohyblivý uzel je `vicko`. Pohyb západky z fotografií nelze určit.
- Malá oválná poutka v okně madla (c01 px 690-720, py 100-120), nápisy (HILTI na západkách, „63030“ na vložce, logo na stohovacích deskách), jemná textura – nemodelováno.
- Tvary pod rámem madla na c02 (zespodu klenutý červený držák) jsou jen náznakem.

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2329206.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `shora` (c01, zavřený, téměř ortografický, render ořezán na obrys, el 89,97°, dist 8000) | **0,986** | maska bez bílého loga (v obou), okno madla v masce zůstává otevřené |
| `otevreny-c02` (víko 105,2°) | 0,978 | kamera z 6 bodů + obrys, díry v masce vyplněny |
| `otevreny-c03` | 0,978 | stejný záběr jako c02 → stejný výsledek |
| `otevreny-c04` (víko 107,5°) | 0,979 | stejný záběr, nářadí uvnitř |
Dvojice foto | model | překryv byly prohlédnuty (ne jen IoU): u `shora` se shodují obrys, rohy, madlo, okno, západky, logo i stohovací desky (rozdíl ≤ 2 mm); největší zbytková odchylka je horní hrana okna madla (model ~6 mm níž, perspektiva přes 175 mm dlouhý průchod při nenulové vzdálenosti kamery). Vedlejší měření (jen orientační, závislé na prahu jasu): tmavé prvky 0,75, logo 0,91 (hrany ±1 px). Otevřené pohledy: kamera je odhad (ohnisko a vzdálenost degenerují, 2900-4400 mm / fov 11-16°), úhel víka je výsledek fitu (105-108°); fit k dělicí spáře SP je téměř slepý (viz výše), proto IoU u šikmých pohledů potvrzuje obrys a polohu pantu/madla/západek, ne výšky.

Nástroje (jen pro 2329206, v `nastroje/`): `fit_lm_2329206.mjs`, `iou_kamera_2329206.mjs` (kopie `fit_lm.mjs`/`iou_kamera.mjs` + vyplnění děr v masce renderu), `srovnej_vse_2329206.sh`, `detaily_2329206.py`; landmarky `zdroje/landmarky_2329206_c02.json`; srovnání (jen vlastní rendery + json, žádné cizí fotografie) v `kufriky_cloud/srovnani/2329206/`. Převzaté beze změny: `porovnej_celo.mjs`, `kalibruj.py`/`maska_cervena.py` (nepoužity), `render/srovnej.mjs`, `nastroje/zabal_prohlizec.mjs`; `p2329206_zaklad.mjs` je kopie `p2437394_zaklad.mjs` rozšířená o polygonové výřezy čelní hrany, zúžení zadních rohů, mezibody zkoseného rohu, díry v dně a rozdělení vany na plášť a vložku. Náhled: `nahled/2329206.html`.
