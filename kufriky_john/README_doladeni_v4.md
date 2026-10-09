# Kufříky: oprava podstav a kontrola všech typů, v4

John, 7. 10. 2026. Navázáno na hotový katalog a náhled v3, nikoli nový katalog.

Náhled: https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v4/

## Vidím v zadání, kódu a skutečných GLB

První tři organizéry v pořadí náhledu jsou **4932471064 – Nízký organizér**, **4932464082 – Organizér**, **4932471065 – Kompaktní nízký organizér**. Výška 117 mm na Robertově snímku identifikuje 4932464082. Jeho upřesnění výslovně určuje spodní plošky; nejde o otevřená dvířka ani o pomocnou obálku. Černá dolní ploška v původním modelu je `patka-1-*`; červená svislá část výše je západka/odjištění a je samostatnou součástí.

### 1. Patky počítané z větší obálky místo skutečného dna

**Soubor a řádky:** `vytvor_doladene_tvary_v3.js:57`, `:299`.

`feet()` pracovalo s celou vnější šířkou, ale tělo `standard()` bylo o rezervu pro přední díly užší a mělo posunutý střed. Přední dvě patky proto přečnívaly před jeho čelo. Celková obálka přesto seděla: chybná patka sama určovala kraj modelu. Pouhá kontrola rozměrů tento problém neodhalila.

Opraveno v `vytvor_doladene_tvary_v4.js:179`: obrys každé rohové patky vzniká z průniku její rohové oblasti se **skutečnou spodní styčnou plochou dna**. Ta se čte z vrcholů výsledného tělesa, včetně zaoblení a sražení. Horní plocha patky dosedá přesně na spodní plochu dna. Patky mají objem; žádná nulová plocha nenahrazuje díl.

### 2. Spodní spojovací prvky nezohledňovaly střed těla

**Soubor a řádek:** `vytvor_doladene_tvary_v3.js:335`.

`docking()` dostávalo šířku těla, ale umisťovalo pole kolem souřadnice 0. Tělo mělo střed `-rezerva/2`. Ve v4 je celé spodní spojovací pole posunuté podle skutečně změřeného středu dna. Každý zub se ověřuje proti odpovídající spojovací patce; patka se ověřuje proti dnu. Zub sám nemusí sahat až ke dnu.

### 3. Generická červená smyčka u nízkých organizérů

**Soubor a řádek:** `vytvor_doladene_tvary_v3.js:336`.

Stejný velký prvek byl přidaný i k nízkým organizérům a zasahoval příliš nízko. Na fotografiích 4932471064 a 4932471065 je malé odjišťovací tlačítko v držadle. Ve v4 je tento prvek nahrazen tlačítkem. U 4932464082 je smyčka přesunutá do otvoru držadla a dosedá na čelní stěnu. Kontrola skutečného kontaktu zahrnuje i tyto červené díly.

### 4. Čelní západky pojízdných kufrů schované v těle

**Soubor a řádky:** `vytvor_doladene_tvary_v3.js:485` a `:486`, poloha západek `bd/2-6` před plnou čelní stěnou; oprava `vytvor_doladene_tvary_v4.js:537`.

U **4932464078 a 4932478161** kolmé čelní snímky odhalily západky zakryté tělem. Fotografie výrobce ukazují západky v čelním vybrání mezi rohy. Ve v4 je upravená pouze vnější čelní stěna mezi rohy; západky jsou viditelné a označení přímo dosedá na tuto stěnu. Vnější obálka, vnitřní kóty, patky, polohy a průměry kol se nezměnily. Reces je vzhledová rekonstrukce, nikoli nová ověřená výrobní kóta.

## Výpočty prvních tří organizérů [mm]

Nízký organizér 4932471064: `rezerva = min(414 × 0,04; 16) = 16`; šířka těla `414 − 16 = 398`; střed `−16 / 2 = −8`. Přední hrana těla `−8 + 398/2 = 191`. Původní patka končila na `414/2 = 207`. **Přesah 207 − 191 = 16 mm.**

Organizér 4932464082: `rezerva = min(386 × 0,04; 16) = 15,44`; šířka těla `386 − 15,44 = 370,56`; střed `−15,44 / 2 = −7,72`. Přední hrana `−7,72 + 370,56/2 = 177,56`; patka končila na `386/2 = 193`. **Přesah 193 − 177,56 = 15,44 mm.**

Kompaktní nízký organizér 4932471065: před otočením je čelo na lokální kratší straně, `rezerva = min(411 × 0,04; 16) = 16`; šířka těla `411 − 16 = 395`; střed `−8`; hrana `−8 + 395/2 = 189,5`; patka `411/2 = 205,5`. **Přesah 205,5 − 189,5 = 16 mm.** Po otočení do katalogové konvence je toto čelo na ose +Y, ne +X.

Tato rezerva byla parametr původní rekonstrukce; není rozměrem deklarovaným výrobcem. Nové umístění se již odvozuje z reálné plochy modelového dna, nikoli z rezervy. Půdorysy těchto tří kusů jsou v náhledu jako odkazy „Půdorys podstavy v mm“; čerpají přímo ze styčných vrcholů GLB.

Ochrany čelních rohů jsou samostatné objemové části doložené fotografiemi. Vnější kótu nyní určuje tělo/ochrana rohu, nikoli vysunutá patka. Neproběhlo dodatečné natažení modelu po osách ani změna zdrojových vnitřních rozměrů.

## Kontrola každého typu

Číselná tolerance digitálního testu je **0,01 mm**. Dovolený přesah podstavných prvků vůči dnu je **0 mm**, bez výjimek odhadnutých z fotografie. Zkontrolovány všechny vrcholy a středy, výškové dosednutí, skutečný kontakt a zrcadlová souměrnost. U rohových patek se porovnává celá zaoblená styčná plocha, nikoli jen obálka. U přepravky a pojízdné zásuvky model nemá samostatné čtyři rohové nožky; jejich skutečné spojovací patky se měří všechny a výjimka je výslovně ve výsledku.

Níže „přesah v3“ znamená osový přesah rohových patek před tělo; dodatečné přesahy za zaoblený obrys jsou uložené zvlášť v `podstavy-pred.json`. U 19 SKU našla kontrola původních styčných obrysů problém. Ve v4 prošlo všech 21 SKU.

| SKU | Typ | Přesah patek v3 [mm] | Změněné spodní díly | Změna / stav v4 |
|---|---|---:|---:|---|
| 4932471064 | Nízký organizér | 16.000 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Červená smyčka nahrazena malým čelním tlačítkem podle fotografie. Všechny spodní díly ověřené. |
| 4932464082 | Organizér | 15.440 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Červené odjištění přesunuto do otvoru čelního držadla a dosedá na tělo. Všechny spodní díly ověřené. |
| 4932471065 | Kompaktní nízký organizér | 16.000 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Červená smyčka nahrazena malým čelním tlačítkem podle fotografie. Všechny spodní díly ověřené. |
| 4932471723 | Kompaktní box na nářadí | 10.275 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932471724 | Otevřená přepravka | 0.000 | 0/12 | Spodní spojovací prvky beze změny: úplná kontrola potvrdila správné umístění pod skutečným dnem. Všechny spodní díly ověřené. |
| 4932498323 | Organizér s výklopnými boxy | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932478625 | Hluboký organizér | 15.440 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932480623 | Skříň s předními dvířky | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932501784 | Box na nářadí XL | 9.850 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932478162 | Box na nářadí XL | 9.850 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932499703 | Box pro elektrikáře | 10.250 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932499704 | Box pro instalatéry | 10.250 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932464078 | Pojízdný box s výsuvným držadlem | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Odkryté čelní západky v zapuštěné stěně mezi rohy; označení dosedá na tuto stěnu. Vnitřní kóty, kola a obálka zachované. Všechny spodní díly ověřené. |
| 4932464079 | Velký box na nářadí | 10.275 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932464080 | Box na nářadí | 10.275 | 16/16 | Patky přesunuté pod skutečné dno, obrys každé plošky podle spodní styčné plochy; spodní spojovací pozice vystředěné na tělo. Čelní ochrany rohů oddělené od spodních patek. Všechny spodní díly ověřené. |
| 4932472129 | Box se 2 zásuvkami | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932472130 | Box se 3 zásuvkami | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932493189 | Box se 4 zásuvkami | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932493190 | Box se zásuvkami 2 + 1 | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Všechny spodní díly ověřené. |
| 4932498651 | Pojízdný box s čelní zásuvkou | 0.000 | 0/12 | Spodní spojovací prvky beze změny: úplná kontrola potvrdila správné umístění pod skutečným dnem. Všechny spodní díly ověřené. |
| 4932478161 | Pojízdná bedna na nářadí | 0.000 | 4/16 | Čtyři rohové podstavy upravené podle skutečné zaoblené spodní plochy dna. Spojovací prvky byly uvnitř obrysu už ve v3. Odkryté čelní západky v zapuštěné stěně mezi rohy; označení dosedá na tuto stěnu. Vnitřní kóty, kola a obálka zachované. Všechny spodní díly ověřené. |

## Fotografie a domnívám se / dosud neověřeno

Použité fotografie a jejich původní URL zůstávají u každého typu v katalogu a náhledu; původní galerie jsou soukromě v `zdroje/doladeni-v3/`. Při opravě prvních tří organizérů byly prohlédnuté čelní, šikmé, horní a otevřené fotografie z těchto galerií. Aktuální veřejný GET stránky organizérů výrobce ověřil HTTP 200 a všechna tři SKU; doklad je `zdroje/doladeni-v4/vyrobce-organizery-overeni.json`. Pojízdné kufry se porovnávaly také s jejich Hero a dalšími snímky výrobce. Nezaložen žádný účet a neodeslán formulář. Přehled dřívějšího průzkumu CAD a licencí zůstává zachovaný.

Vidím na snímcích ochranné rohy a čelní díly; **přesné nekótované polohy, rádiusy a tloušťky z fotografií neznám**. U předních ochran a recesů jde nadále o označenou rekonstrukci. Nové testy dokazují polohu spodních dílů **v našem modelu**, nikoli rozměry podstav skutečného výrobku. Počet, rozteče a profil zubů PACKOUT, fyzická stohovací kompatibilita a nekótované detaily potřebují měření kusu, sken nebo licencovaný kótovaný CAD. Proto katalog nadále uvádí **0 výrobcem ověřených přesných CAD**, nikoli nepravdivé „hotové přesné modely“.

Zůstávají dřívější slabá místa profesních vložek, nové varianty XL a rozpor zdrojových rozměrů pojízdné zásuvky. Původní kóty, ceny, odkazy a upozornění nebyly přepsané. Směr fotograﬁe je orientační; společný směr modelů v3/v4 je reprodukovatelný, objektiv výrobce není kalibrovaný.

## Ověření

- **21 GLB, 990956 skutečných vrcholů, 439984 trojúhelníků**, všechny vnější kóty v toleranci 0,01 mm, bez natažení po osách; největší soubor 1710708 B.
- **328 spodních dílů, 180960 vrcholů podstav**, všechny středy i obrysy uvnitř skutečného dna, dosed i souměrnost ověřené.
- 499 vybraných čelních/bočních a vyčnívajících součástí; 1454 kandidátních kontaktů, každý má doložený kontakt na skutečné síti.
- 1930 součástí, 477 tenkých detailů vypsáno; žádná součást s nulovým/téměř nulovým rozsahem nebo objemem. Toto není ověření fyzických tlouštěk.
- Vzorkovaný audit vnitřních nádob, zásuvek a dvířek: 82 párů, 2916 materiálových vzorků, 0 zachycených společných vzorků. Není to úplná kolizní certifikace.
- 6 regresních testů podstav prošlo, včetně původní chyby v3, záměrně posunuté patky se středem stále uvnitř těla a patky bez výškového dosedu.
- 8 navazujících geometrických testů prošlo; stejný katalogový parser ověřil 21 modelů a tři skutečné katalogové reference. Konvence X=šířka, Y=délka, Z=výška, mm.
- Očima prohlédnutých všech 100 kolmých kontrolních pohledů v4 (20 typů × čelo / oba boky / shora / zespodu), plus nové snímky obou opravených pojízdných kufrů. Veřejný náhled obsahuje vlastní rendery v3/v4 a pouze odkazy na cizí fotografie.
- Historie v3: všech 94 místních i veřejných souborů má původní SHA-256; v1/v2 nezměněné. Režie animací nezměněná.

### Opakování bez DB a sítě

Historické generátory v1/v2/v3 nespouštět přes nový katalog.

```bash
node vystupy/kufriky/vytvor_doladene_tvary_v4.js
python3 vystupy/kufriky/over_podstavy_v4.py --baseline
python3 vystupy/kufriky/over_podstavy_v4.py
python3 vystupy/kufriky/dopln_vysledky_v4.py
python3 vystupy/kufriky/sestav_nahled_v4.py
python3 vystupy/kufriky/test_podstavy_v4.py
python3 vystupy/kufriky/over_doladeni_v4.py
python3 vystupy/kufriky/audit_kolizi_v4.py
python3 vystupy/kufriky/over_tenke_plochy_v4.py
node vystupy/kufriky/over_v4_katalogovym_parserem.js
node vystupy/kufriky/renderuj_kontrolu_v4.js
python3 vystupy/kufriky/vykresli_podstavy_v4.py
node vystupy/kufriky/over_nahled_v4.js
```

Průzkum výrobce a veřejné přečtení nahraného náhledu jsou oddělené od těchto čistých kontrol. Výsledky jsou v `overeni-tvar-v4/`, zdrojové poznámky a původní katalog v `zdroje/doladeni-v4/`, modely v `modely/` a zachovaná v3 v `modely-v3/`. Každý model má v katalogu konkrétní opravu, výsledek kontroly a neověřené detaily.

## Zbývá

Robertovo posouzení náhledu v4. Přesné nekótované detaily a funkční spoje je potřeba doměřit; případnou integraci do živého katalogu provede jeho vlastník až po schválení. John upravil pouze vlastní výstupy, vlastní statický náhled a přehled práce.

John.

Prohlížeč v4: PASS; 20 typů, oba boky, pět kontrolních obrázků u každého typu, otevření a skrývání, mobil, 0 chyb a 0 nepovolených požadavků. Nahráno 317 statických souborů; curl hlavní stránky vrací HTTP 200.

Veřejné přečtení: PASS; všech 317 souborů HTTP 200 a shodný SHA-256 s místním ověřeným náhledem. Přehled práce atomicky aktualizovaný na `ceka_na_schvaleni`.
