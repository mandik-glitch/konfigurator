# Organizéry PACKOUT: oprava vyčnívajících částí, v5

John, 7. 10. 2026. Přečtené AGENTS.md včetně 4d/4e/4f a celé zadání včetně doplnění 6, všech jeho upřesnění a doplnění 7. Navázáno na existující v4 a schválený katalog; žádný nový katalog od začátku.

Náhled: https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v5/

## Vidím v kódu, skutečných modelech a fotografiích

První tři organizéry jsou **4932471064, 4932464082, 4932471065**. Výška 117 mm z původního snímku odpovídá **4932464082**. Zkontrolovány a upraveny také **4932478625** a **4932498323**, tedy všech pět organizérů v katalogu.

### 1. Ve v4 zůstaly samostatné čelní desky

Soubor: `vytvor_doladene_tvary_v4.js:356`. Uzly `celo-roh-ochrana--1` a `celo-roh-ochrana-1` byly úzké vysoké doplněné části před původním užším trupem. Jejich přesah byl **16 mm** u obou nízkých organizérů a **15,44 mm** u běžného a hlubokého organizéru. Kontrola patek je neměřila jako patky, protože jde o jiné součásti. V bočním pohledu působily jako samostatné svislé plochy. Původní spodní patky v4 již byly správně pod dnem; doplnění 7 odhalilo další problém.

Oprava: `vytvor_doladene_tvary_v5.js:617` a `:669`. Rohy nyní tvoří **spojitý zaoblený obrys trupu**, čelní vybrání, dno i okraj víka. Původní uzly desek u organizérů nejsou v exportu. Dno a víko respektují stejné čelní vybrání, aby nevznikla nová vystupující tenká hrana. Patky se odvozují z nového skutečného dna. Změna není skrývání částí prohlížečem.

### 2. Nesprávná červená smyčka a spodní odjištění

Soubor: `vytvor_doladene_tvary_v4.js:396`. `zamek-packout-cerveny` byl obecný obdélníkový díl; u hlubokého organizéru ležel výrazně níže než držadlo. Fotografie výrobce a nové fotografie spodku ukazují čelní prvek tvaru C a oddělené spodní tlačítko. Červený zavěšený papírový štítek na fotografiích TIM je **obal výrobku**, nebyl převzat do modelu.

Oprava: `vytvor_doladene_tvary_v5.js:644`, `:701` a `:704`. U běžného a hlubokého organizéru je čelní C místo generické smyčky. Červené pouzdro úchopu je podle čelních fotografií tvaru U otevřeného nahoře místo původního uzavřeného obdélníku. Spodní tlačítko je zapuštěné do dna, má skutečný objem a nezačíná pod spodní plochou trupu. U nízkých organizérů je malé čelní odjištění. U výklopného organizéru je doplněné připojené čelní odjištění pod držadlem podle Hero_4/5 (`:605`).

### 3. Generické spodní pole neodpovídalo dvěma doloženým variantám

Ve v4 dostával každý organizér stejných šest velkých spojovacích pozic. Nový přímý spodek **4932464082** ukazuje 3 řady po 4 pozicích, tedy **3 × 4 = 12**. Nový slovenský snímek **4932471065** ukazuje **3 × 2 = 6**. Oprava je v `vytvor_doladene_tvary_v5.js:625`: správná rodinná topologie, menší oddělené pozice s prolisy, bez širokých podstavných desek před čelem.

Fotografie potvrzují počet a orientaci u těchto dvou SKU. Přesné rozteče a průřezy nejsou z fotografií kótované. Přenos rodinného řešení na nízký široký a hluboký organizér zůstává **označená rekonstrukce**, nikoli doměřený spoj.

### 4. Kontrolní prvky a čitelnost náhledu

Kóty, obálka i barvení součástí jsou ve výchozím stavu vypnuté. Jsou samostatně zapínatelné. Každý organizér má 6 hlavních a 4 šikmé pohledy, oba boky také s barevným rozlišením a všechny diagnostické snímky uložené. Barvení zahrnuje i průhledné díly; barevný seznam uvádí skutečné názvy součástí. Pohled zespodu má doplňkové osvětlení. Vlastní rendery jsou veřejné; cizí fotografie jsou pouze odkazy.

## Nové fotografie a úhly

Soukromá tabulka: `zdroje/doladeni-v5/fotografie.json` a `fotografie.csv`. Celkem **77 snímků / zdrojů**, z nich **39 nově načtených**. Různé velikosti stejné výrobní fotografie ani kopie od různých prodejců neznamenají další nezávislé úhly.

| SKU | Použité snímky / zdroje | Doložené úhly a oprava |
|---|---:|---|
| 4932471064 | 11 | Dva zavřené šikmé pohledy, horní, otevřený a použití při přenášení / stohování. Dvě desky s přesahem 16 mm nahrazené souvislým trupem; malé čelní a zapuštěné spodní odjištění. Přímý vlastní spodek nezískán. |
| 4932464082 | 19 | Nově celá rotace TIM: shora, oba přímé boky, spodek a šikmé úhly víka i spodku, navíc otevřený stav a stohování výrobce. Desky s přesahem 15,44 mm odstraněné z geometrie; C a spodní tlačítko místo smyčky; 12 spodních pozic. |
| 4932471065 | 13 | Nově přímý spodek slovenského prodejce, otevřený pohled a detail přihrádek; dále zavřený šikmý, horní a složený stav. Desky s přesahem 16 mm nahrazené souvislým trupem; zapuštěné spodní odjištění, šest spodních pozic. |
| 4932478625 | 19 | Zavřený šikmý a horní, otevřený s děliči i bez nich, manipulace s děliči a složené kusy z více směrů. Desky s přesahem 15,44 mm nahrazené trupem; nízko umístěná smyčka nahrazená čelním C a zapuštěným tlačítkem. Přímý vlastní spodek nezískán. |
| 4932498323 | 15 | Přímý čelní, šikmé zavřené i otevřené boxy, boční přepravní poloha a složený stav; nově ověřený český prodejce. Žádná vyčnívající podstava nenalezena; doplněné odjištění pod držadlem. Přímý spodek nezískán. |

Hlavní nové podklady:

- [Rotace a produktová stránka TIM, 4932464082](https://www.tim.pl/organizer-narzedziowy-10-pojemnikow-na-akcesoria-packout-4932464082/p/0001-00018-63769), [přímý spodek](https://www.tim.pl/media/wysiwyg/w360/0001-00018-63769/images/Photo007.jpg), [pravý bok](https://www.tim.pl/media/wysiwyg/w360/0001-00018-63769/images/Photo004.jpg), [levý bok](https://www.tim.pl/media/wysiwyg/w360/0001-00018-63769/images/Photo010.jpg).
- [Slovenská galerie 4932471065](https://www.stavbaeu.sk/milwaukee-packout-slim-kompaktny-organizer-4932471065-235267), [přímý spodek](https://www.stavbaeu.sk/image/cache/data/productsdetail/D/DE_4932471065_3-800x800.jpg).
- [Výrobní galerie organizérů](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/), [výklopný organizér](https://www.milwaukeetool.eu/en-eu/packout-tip-bin-organiser/packout-tip-bin-organiser/).
- [Další galerie nízkého organizéru](https://www.paulimot.de/milwaukee-packout-organiser-slim), [kompaktního organizéru](https://www.paulimot.de/en-gb/milwaukee-packout-organiser-slim-compact), [hlubokého organizéru](https://www.paulimot.de/milwaukee-packout-organiser-tief), [česká galerie výklopného organizéru](https://www.elglobal.cz/packout--organizer-s-vyklapecimi-boxy/).

Nedostupné adresy jsou zapsané v tabulce čtení; ochrany nebyly obcházené. Nebyl založen účet, vyplněn formulář ani odeslána zpráva.

## Číselné ověření a vzorce [mm]

Původní přesah prvních tří typů byl:

- 4932471064: `414/2 − (−16/2 + (414−16)/2) = 207 − 191 = 16 mm`.
- 4932464082: `386/2 − (−15,44/2 + (386−15,44)/2) = 193 − 177,56 = 15,44 mm`.
- 4932471065 před otočením: `411/2 − (−16/2 + (411−16)/2) = 205,5 − 189,5 = 16 mm`; po otočení je čelo na +Y.

V5 používá skutečný spojitý obrys dna: u 4932471064 plné krajní X `−414/2 až +414/2 = −207 až +207`, u 4932464082 `−193 až +193`, u kompaktního organizéru po otočení Y `−205,5 až +205,5`. Uprostřed je čelní vybrání; **obálka nestačí jako důkaz opory**. Každý vrchol a horní plocha patky mají ověřený zásah do skutečné spodní plochy dna, včetně vybrání. Přesah každé součásti se zapisuje po všech osách, zvlášť proti dnu a trupu.

Výpočet přesahu součásti v ose X: `max(0; X_min_trupu − X_min_dílu; X_max_dílu − X_max_trupu)`; totéž v Y a Z. Digitální tolerance je 0,01 mm. Záměrné výškové rozdíly víka a patek se vykazují, nejsou potichu přeskočené. U organizérů není žádná součást mimo plný půdorysný rozsah trupu; uzavřené západky a úchopy jsou za jeho rohy. Počet změřených dílů nikdy není nula a chybějící GLB je chyba.

**Čisté ověření:** 21 GLB, 2 199 součástí, 1 178 032 skutečných vrcholů, 364 spodních dílů a 19 304 bodů jejich styčných ploch. Zdrojové obálky, vnitřní kóty i průměry kol zachované. Sedm regresních testů zachytí původní desky v4, přesah libovolně pojmenované a červené součásti, přesah rohu se středem stále uvnitř a chybějící díl; kontroluje i skutečné vybrání dna. Osm navazujících kontrol rozměrů, dutin a uchycení prošlo. Katalogový parser ověřil 21 modelů a tři skutečné katalogové reference. Konvence mm, X = šířka, Y = délka, Z = výška, bez dodatečného natažení po osách.

522 vybraných připojených součástí / 1 795 kandidátních kontaktů má svědka na skutečné síti. Vzorkovaný audit dutin: 82 párů / 2 916 materiálových vzorků, bez zachyceného společného vzorku. Kontrola 744 tenkých detailů nehlásí nulovou či téměř nulovou plochu. Největší GLB má 2 733 308 B, pod cílem 3 MB.

Výsledky: `overeni-tvar-v5/soucasti.json`, `soucasti.csv`, `soucasti-pred-v4.json`, `rozmery.json`, `uchyceni.json`, `katalogovy-parser.json`, `renderovani.json`, `prohlizec.json`. Veřejná tabulka měření obsahuje i očekávané výškové přesahy, proto nenulový sloupec Z není automaticky chyba.

## Domnívám se / neověřeno

Tvar je vlastní fotografická rekonstrukce v ověřené obálce. Nekótované poloměry, tloušťky, úkosy, přesná poloha dutiny, hloubky kapes a rozteče spojovacích zubů nejsou fyzicky změřené. Část vzhledových parametrů navazuje na v4. Fotografie potvrzují topologii a viditelnou polohu, nejsou kalibrovaný výrobní výkres. U tří SKU nebyl získán přímý spodek jejich konkrétní varianty. Současné podklady umožnily odstranit chyby geometrie, **ne potvrdit přesný výrobní CAD ani funkční stohovací vůle**. K jejich ověření je třeba fyzické doměření, sken nebo licencovaný kótovaný CAD. Přesných výrobcem ověřených CAD je nadále 0.

Dřívější omezení profesních vložek, nové varianty XL a rozpor kót pojízdné zásuvky zůstávají uvedené. Mimo pět organizérů je 16 GLB bitově shodných s v4; jejich podstavy i oba boky byly znovu kontrolované. Historie v4 je zachovaná: 634 místních a veřejných souborů ověřeno původním SHA-256. Režie animací nebyla změněná.

## Nahraný a veřejně ověřený náhled

Nahráno **465 statických souborů** pouze do nové vlastní složky náhledu v5. Hlavní stránka ověřená přes curl: **HTTP 200**. Každý veřejný soubor následně načten metodou GET: všech 465 odpovědí HTTP 200, SHA-256 shodné s místní ověřenou kopií. Vlastní stránka byla ověřená i přímo veřejným prohlížečem: všech pět organizérů, deset kontrolních pohledů, barevné rozlišení součástí a mobilní šířka; žádné chyby ani požadavky mimo vlastní statickou složku. Žádná přihlášení ani odesílání formulářů.

Doklady: `overeni-tvar-v5/nahrani.json`, `verejny-get.json`, `verejny-prohlizec.json`, `verejny-desktop.png`, `historie-v4.json`. Po nahrání znovu ověřeno všech **634 souborů historie v4**, žádná změna. Přehled práce aktualizován na **ceka_na_schvaleni** s odkazem na v5; starší odkazy zachované.

## Opakování bez DB a sítě

```bash
python3 vystupy/kufriky/over_organizery_v5.py
python3 vystupy/kufriky/over_organizery_v5.py --test
python3 vystupy/kufriky/over_doladeni_v5.py
python3 vystupy/kufriky/audit_kolizi_v5.py
python3 vystupy/kufriky/over_tenke_plochy_v5.py
node vystupy/kufriky/over_v5_katalogovym_parserem.js
node vystupy/kufriky/over_nahled_v5.js
```

Generátor je `vytvor_doladene_tvary_v5.js`; historické generátory v1–v4 nespouštět nad aktuálním katalogem. Průzkum internetu a veřejné ověření nahraných souborů jsou oddělené od čistých testů. Nové fotky zůstávají výhradně ve vlastních soukromých podkladech.

Zbývá Robertovo posouzení v5 a přesné doměření nekótovaných detailů. Zapojení do živého katalogu provede vlastník až po schválení. John.
