# Kufříky PACKOUT – reálné tvary v2

John, 5. 10. 2026. Přečteno AGENTS.md včetně 4d, celé zadání včetně doplnění 1–4 a povinné geometrické podklady. Práce pokračuje ze schválených 20 úložných typů (21 SKU); dalších 14 dílů systému zůstává mimo modelování.

Náhled: [reálné tvary v2](https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-modely-v2/). Původní náhled v1 je zachovaný.

## Co je hotové

Všech 21 souborů v `modely/<SKU>.glb` obsahuje vlastní geometrii výrobku místo jediného kvádru. Obálky jsou zachované odděleně v `obalky-v1/`; náhled v1 a schválená tabulka nebyly změněny. Nový náhled nabízí přepínání typů, fotografie se zdrojem, kóty, otáčení, horní a spodní pohled, otevření víka, vysunutí zásuvek, otevření dvířek, výklopné přihrádky a volitelné zobrazení kontrolní obálky. Otevření je názorná vizualizace, nikoli ověřená kinematika mechanismu.

Organizéry mají samostatný spodní díl, průhledné víko s prolisy a skutečně duté vyjímatelné přihrádky. Plné organizéry mají deset přihrádek podle fotografie; kompaktní nízký má pět. Výklopný organizér má osm malých a dvě velké průhledné přihrádky podle popisu výrobce. Zásuvkové boxy mají různé počty čel, duté zásuvky, přepážky, výsuvy a zajišťovací lištu. Skříň má samostatná čelní dvířka. Přepravka má otevřený vnitřek a průchozí otvory držadel. Pojízdné výrobky obsahují dvě kola s náboji, paprsky a vzorkem, oddělené madlo a vlastní tělo. Horní drážky, lišty, spodní zuby, patky, zaoblení, ochrany rohů, žebra a prolisy jsou modelovaná geometrie. Názvy komponent a jejich role jsou uvnitř GLB.

## Vidím ve zdroji / v souborech

Vnější rozměry, dostupnost v CZ/SK, SKU, EAN, ceny, původní rozpory a původní odkazy z katalogu etapy 1 jsou zachované beze změny; čistý test je porovnává se zmrazeným vstupem. Fotografie výrobce byly běžným veřejným GET uloženy v rozlišení 1000 × 1000 do `zdroje/fotografie-tvar-v2/`. Manifest `zdroje.json` obsahuje pro každý typ URL fotografie, produktovou stránku a účel. Náhled používá výhradně místní kopie fotografií, knihoven a modelů. Fotografie nejsou vydávané za volně licencované dílo; slouží zde pro interní noindex přehled.

Nový průzkum celých CAD navazuje na předchozí průzkum. [3D CAD Browser](https://www.3dcadbrowser.com/3d-model/milwaukee-toolbox) výslovně vyžaduje účet a zakazuje další distribuci zdrojového modelu; nebyl stažen. Předchozí kandidáti jsou zachovaní v `zdroje/cad_etapa2/pruzkum.json`; nový souhrn v `zdroje/cad_tvar_v2.json`. Nebyl získán úplný model správného evropského SKU s ověřenou licencí a stažením bez účtu. Toto není tvrzení, že nikde neexistuje. Žádný účet, přihlášení, e-mail, formulář ani objednávka nebyly použity.

Konvence z místního katalogu: X = kratší vodorovná strana, Y = délka, Z = výška; čísla v mm. Stejný katalogový parser měří nové GLB a tři původní referenční modely. Pivot nových souborů je ve středu jejich zavřené obálky, uzly bez transformací; všechny souřadnice jsou zapečené do vrcholů. Zobrazovací otočení kolem X o −90° je pouze ve stránce.

## Domnívám se / limity rekonstrukce

**Jde o reálný tvar rekonstruovaný podle fotografie, nikoli o přesný výrobcem ověřený CAD.** Fotografie určují přítomnost a vzhled viditelných komponent, ale neurčují jejich úplné prostorové souřadnice. Vizuální proporce v generátoru jsou výslovně rekonstrukční parametry; nejsou nové ověřené technické hodnoty.

Generátor vytvoří duté komponenty, použije známé vnitřní rozměry jako počáteční vodítko a následně celý tvar po osách přizpůsobí publikované vnější obálce. `envelope_fit` v každém měřicím listu a GLB ukládá původní rozsah a všechny tři koeficienty přizpůsobení. Tato operace prokazuje správné celkové měřítko, **neprokazuje přesnost vnitřních rozměrů, průměrů kol ani jednotlivých detailů po přizpůsobení**. Publikované vnitřní rozměry v katalogu zůstávají zdrojovým údajem; digitální poloha a geometrie dutiny nejsou ověřené měřením fyzického kusu.

Neověřené jsou přesné poloměry a úkosy, tloušťky, posuny dutin, šířky a polohy kol, rozsah výsuvu madel, mechanismy, spojovací profily a vůle PACKOUT. Horní/spodní spojovací prvky jsou vzhledovou rekonstrukcí; model nepoužívat jako podklad pro výrobu adaptéru, toleranční kolize ani potvrzení skutečné spojitelnosti. Volné výšky nebo průchody mezi detaily musí být doměřeny.

Přepravní poloha: výklopná držadla velkého a kompaktního boxu jsou sklopená, teleskopická madla jsou zasunutá. Fotografie často ukazují zdvižené držadlo; jeho zdvih není zdrojově kótovaný. U XL jsou soubory pro dvě SKU samostatné, ale společný rekonstruovaný tvar nepotvrzuje konstrukční identitu revizí. U profesních kufrů stejná výrobní fotografie neurčuje rozdíly jejich vložek. Rozpor rozměrů pojízdné zásuvky a ostatní upozornění zůstávají viditelné. Průchozí otvory držadel přepravky jsou vytvořené; přesné výlisky a odlehčení stěn zbývá doměřit.

Obyčejné geometrické nápisy MILWAUKEE / PACKOUT připomínají označení výrobku; nekopírují přesný tvar loga. Písmo Helvetiker pochází z místní knihovny Three.js; jeho povolení a copyright jsou uloženy u fontu, uvnitř GLB a v náhledu. Three.js má místně uloženou MIT licenci. Není připojena žádná cizí služba ani CDN.

Datový stav je `vlastni_rekonstrukce_tvaru`, úroveň detailu `realny_tvar`, `physical_accuracy_verified = false`, fyzická tolerance `null`. Počet ověřených přesných CAD zůstává 0; počet reálných tvarů je 20. Žádná neověřená vlastnost nebyla zapsána jako ověřená specifikace výrobku.

## Čisté ověření

```bash
node vystupy/kufriky/vytvor_realne_tvary.js
python3 vystupy/kufriky/sestav_nahled_tvar_v2.py
python3 vystupy/kufriky/over_realne_tvary.py
node vystupy/kufriky/over_tvary_katalogovym_parserem.js
node vystupy/kufriky/over_nahled_tvar_v2.js
```

Příprava a testy nepotřebují DB, síť ani hesla. Browser obsluhuje všechny statické požadavky z disku. Staré skripty `vytvor_obalky.py` a `over_modely.py` jsou historická etapa v1; negenerovat jimi nový katalog, přepsaly by rekonstruované tvary zpět na obálky.

Sedm kontrol ověřuje zachování podkladů, všechny skutečné vrcholy všech 21 GLB, velikosti souborů, absenci náhradního kvádru, pravdivý stav přesnosti, počty a otevřenou topologii přihrádek a zásuvek, průchozí otvory držadel, kola a pravidla veřejné stránky. Nezávislý katalogový parser kontroluje stejné rozměry. Browser ověřuje všechny typy, otevření, skrývání částí, rozměry, zdroje, fotografii, hledání a mobilní šířku. Žádný test nepotvrzuje shodu každého povrchu se skutečným kusem.

Měřeno 21 GLB, 959862 vrcholů a 425324 trojúhelníků. Největší soubor 1686252 B; všechny pod 3 MB. Maximální digitální odchylka obálky 0.0 mm při toleranci 0,01 mm.

## Výpočty a stav po typech

Rozměr = maximum − minimum skutečných vrcholů na dané ose. L = nejdelší publikovaná vodorovná strana; Š = kratší. Pro středový pivot jsou hranice X = ±Š/2, Y = ±L/2, Z = ±V/2.

| SKU | Typ | L × Š × V [mm] | Výpočet X; Y; Z [mm] | Částí / MB | Stav | Zdroj rozměrů |
|---|---|---|---|---|---|---|
| 4932471064 | Nízký organizér | 500 × 414 × 64 | 207 − (−207) = 414; 250 − (−250) = 500; 32 − (−32) = 64 | 82 / 1.17 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932464082 | Organizér | 500 × 386 × 117 | 193 − (−193) = 386; 250 − (−250) = 500; 58.5 − (−58.5) = 117 | 82 / 1.16 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932471065 | Kompaktní nízký organizér | 411 × 249 × 64 | 124.5 − (−124.5) = 249; 205.5 − (−205.5) = 411; 32 − (−32) = 64 | 58 / 0.86 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932471723 | Kompaktní box na nářadí | 411 × 249 × 330 | 124.5 − (−124.5) = 249; 205.5 − (−205.5) = 411; 165 − (−165) = 330 | 87 / 1.45 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932471724 | Otevřená přepravka | 475 × 389 × 251 | 194.5 − (−194.5) = 389; 237.5 − (−237.5) = 475; 125.5 − (−125.5) = 251 | 50 / 0.87 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-crate/packout-crate/) |
| 4932498323 | Organizér s výklopnými boxy | 500 × 386 × 170 | 193 − (−193) = 386; 250 − (−250) = 500; 85 − (−85) = 170 | 55 / 0.77 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-tip-bin-organiser/packout-tip-bin-organiser/) |
| 4932478625 | Hluboký organizér | 507 × 386 × 178 | 193 − (−193) = 386; 253.5 − (−253.5) = 507; 89 − (−89) = 178 | 82 / 1.17 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-organisers/packout-organisers/) |
| 4932480623 | Skříň s předními dvířky | 508 × 381 × 381 | 190.5 − (−190.5) = 381; 254 − (−254) = 508; 190.5 − (−190.5) = 381 | 62 / 1.09 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-cabinet/packout-cabinet/) |
| 4932501784 / 4932478162 | Box na nářadí XL | 554 × 394 × 422 | 197 − (−197) = 394; 277 − (−277) = 554; 211 − (−211) = 422 | 83 / 1.34 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932499703 | Box pro elektrikáře | 560 × 410 × 165 | 205 − (−205) = 410; 280 − (−280) = 560; 82.5 − (−82.5) = 165 | 87 / 1.41 | Reálný tvar; detaily neověřeny | [zdroj](https://myloesch.com/de/milwaukee-koffer-fuer-elektriker-560-x-410-165-mm-packout-leer/90-9813) |
| 4932499704 | Box pro instalatéry | 560 × 410 × 165 | 205 − (−205) = 410; 280 − (−280) = 560; 82.5 − (−82.5) = 165 | 87 / 1.41 | Reálný tvar; detaily neověřeny | [zdroj](https://www.muellershop.ch/?artId=101138385&groupId=100040772&markid=MI4932499704&pg=det&srv=marken) |
| 4932464078 | Pojízdný box s výsuvným držadlem | 561 × 472 × 530 | 236 − (−236) = 472; 280.5 − (−280.5) = 561; 265 − (−265) = 530 | 162 / 1.42 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-trolley-box/packout-trolley-box/) |
| 4932464079 | Velký box na nářadí | 561 × 411 × 282 | 205.5 − (−205.5) = 411; 280.5 − (−280.5) = 561; 141 − (−141) = 282 | 102 / 1.69 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932464080 | Box na nářadí | 561 × 411 × 165 | 205.5 − (−205.5) = 411; 280.5 − (−280.5) = 561; 82.5 − (−82.5) = 165 | 83 / 1.34 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-boxes/packout-boxes/) |
| 4932472129 | Box se 2 zásuvkami | 564 × 414 × 363 | 207 − (−207) = 414; 282 − (−282) = 564; 181.5 − (−181.5) = 363 | 81 / 1.35 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932472130 | Box se 3 zásuvkami | 564 × 414 × 363 | 207 − (−207) = 414; 282 − (−282) = 564; 181.5 − (−181.5) = 363 | 90 / 1.48 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932493189 | Box se 4 zásuvkami | 564 × 414 × 363 | 207 − (−207) = 414; 282 − (−282) = 564; 181.5 − (−181.5) = 363 | 99 / 1.61 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932493190 | Box se zásuvkami 2 + 1 | 564 × 414 × 363 | 207 − (−207) = 414; 282 − (−282) = 564; 181.5 − (−181.5) = 363 | 90 / 1.48 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-drawer-tool-boxes/packout-drawer-tool-boxes/) |
| 4932498651 | Pojízdný box s čelní zásuvkou | 610 × 480 × 550 | 240 − (−240) = 480; 305 − (−305) = 610; 275 − (−275) = 550 | 161 / 1.42 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-rolling-drawer/packout-rolling-drawer/) |
| 4932478161 | Pojízdná bedna na nářadí | 965 × 609 × 401 | 304.5 − (−304.5) = 609; 482.5 − (−482.5) = 965; 200.5 − (−200.5) = 401 | 160 / 1.37 | Reálný tvar; detaily neověřeny | [zdroj](https://www.milwaukeetool.eu/en-eu/packout-rolling-tool-chest/packout-rolling-tool-chest/) |

## Veřejný náhled ověřen

Nová složka v2 obsahuje 74 statických souborů. Veřejné čtení stránky, skriptů, katalogu a všech 21 GLB vrátilo HTTP 200; všech 25 přečtených souborů má stejný SHA-256 jako místní podklad. `overeni-tvar-v2/nahrani.json` dokládá kopii a zachování v1; `verejny-get.json` ukládá URL, stav, délku a hash každého čtení. Offline browser skončil PASS bez chyb a bez požadavků mimo místní statické soubory. Nejsou změněné žádné služby ani produkční kód.

## Co zbývá

Robert posoudí nový náhled. K přesnosti každého povrchu a funkčních spojů je potřeba úplný kótovaný CAD s právem použití, kalibrovaný sken správného SKU nebo měření kusu. Konkrétní chybějící měření jsou nadále v `mereni/`; rekonstrukční zprávy v `mereni-tvar-v2/`. Do živého katalogu zapojí schválené podklady příslušný vlastník. John nezměnil produkční kód, DB, služby ani starší veřejné náhledy.

John.
