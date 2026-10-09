# Nářaďové kufříky Milwaukee PACKOUT – etapa 1

Autor: John. Průzkum 5. 10. 2026. Zadání i obě doplnění přečteny celé. Zpracovaná je pouze tabulka; nevznikl 3D model ani stažený CAD. Etapa 2 čeká na Robertovo schválení tabulky oznámené botem9.

Náhled: https://autovestavby.logiman.cz/nahled-john/kufriky-milwaukee-tabulka-v1/

## Výsledek

- 20 typů pevných kufrů, boxů, zásuvkových boxů, skříně, přepravky a organizérů.
- 14 dalších dílů: vložka s držadlem, dva vozíky, pracovní deska, dva termoboxy, lékárnička a sedm brašen/batohů. Tyto výrobky jsou oddělené od hlavních kufříků.
- U všech 34 zahrnutých typů je konkrétní nabídka v ČR i SR a cena bez DPH. U XL jsou nové i staré objednací číslo a jejich nabídky oddělené v jednom řádku.
- 34 skutečných fotografií výrobce, lokální miniatury široké 240 px. Samotné obrázky mají celkem 299 912 bajtů.
- Osm vyřazených variant: sedm pod hranicí délky a jedna sestava již uvedených boxů. Další skupiny příslušenství a sestav mají vysvětlené vyřazení. Dvě americké varianty bez dohledaného CZ/SK prodeje jsou uvedené zvlášť, nikoli v hlavním seznamu.
- V každém řádku jsou SKU, vnější rozměry, hmotnost, nosnost, prodejci, ceny a zdroje. Rozbalení zpřístupní EAN, vnitřní rozměry, původní pořadí os, výpočty převodu a popis úchytů. Údaje, které zdroj neuvádí, zůstávají prázdné nebo označené „neuvedeno“.

## Vidím ve zdroji

Produktové stránky výrobce EU a jejich CZ/SK varianty obsahují identifikátory a rozměrové tabulky. U většiny typů je pořadí výslovně **H × W × D**, nikoli L × Š × V. V katalogu zůstává uložený původní text, pořadí a URL; nepřebírám americké rozměry pro evropské SKU. Prodej je doložen produktovými stránkami CZ/SK prodejců se správným SKU, veřejnou cenou a dostupností. Nabídka na objednání se rozlišuje od položky skladem.

Výrobce zpravidla neuvádí hmotnost. Použité hmotnosti prodejců mají zdroj a poznámku, že není doloženo vážení bez obalu. Nejde o potvrzenou vlastní hmotnost předmětu. Nosnost není odvozena z objemu nebo hmotnosti. U zásuvkových boxů platí celkových 22 kg a údaj 11 kg pro jednu zásuvku; tyto hodnoty se nesčítají do vyšší celkové nosnosti. Pojízdná zásuvka má zvlášť 68 kg uvnitř a 113 kg na horní straně.

Profesní kufry 4932499703 a 4932499704 nemají v dohledané tabulce výrobce rozměry. Vnější rozměry 560 × 410 × 165 mm pocházejí od konkrétních prodejců; jsou tak označené. Pro elektrikářský kufr je doložen převod 56 cm × 41 cm × 16,5 cm na mm. Instalatérský kufr má navíc rozpor s údajem 561 mm u dalšího prodejce. Část přímých prodejních stránek vrátila 403; jejich ochrana nebyla obcházena. U instalatérského kufru je podkladem veřejný index stránky s označenými osami, což je v tabulce výslovně uvedené. Označení os lékárničky XL je doloženo veřejnou stránkou Klium, zatímco výrobce uvádí trojici bez názvů os.

## Rozhodnutí Johna a co netvrdím

Pro filtrování používám **L = delší vodorovná strana**, Š = druhá vodorovná strana a V = výška, v běžné orientaci uvedené výrobcem. Převod je L = max(W, D), Š = min(W, D), V = H. Je to výslovná konvence tohoto přehledu, nikoli tvrzení, že výrobce nazývá W délkou. Hranice je ostrá: L musí být > 400 mm. Vysoký batoh proto automaticky nepatří mezi dlouhé kufry.

Příklady ověřené skriptem:

- Kompaktní box: H × W × D = 330 × 249 × 411; L = max(249, 411) = 411, Š = 249, V = 330 mm → zahrnutý.
- Dvoukolový vozík: H × W × D = 1200 × 510 × 660; L = max(510, 660) = 660, Š = 510, V = 1200 mm → další díl systému.
- Starší batoh 4932471131: H × W × D = 508 × 381 × 292; L = max(381, 292) = 381 mm ≤ 400 mm → vyřazený, i když je vysoký 508 mm.
- Elektrikářský kufr: L = 56 × 10 = 560, Š = 41 × 10 = 410, V = 16,5 × 10 = 165 mm → podle prodejce, výrobce nepotvrdil.

Rozměrová specifikace stránky výrobce není měřením skutečné obálky včetně západek, držadel a kol. U brašen navíc nejde o pevný obrys. Z těchto údajů zatím nelze slíbit přesný 3D model spojů. Úplnost znamená pokrytí 42 variant prověřených veřejných EU produktových rodin; není to záruka zachycení neindexované novinky nebo individuálního dovozu.

## Rozpory a otevřené věci

| Typ / SKU | Vidím ve zdroji | Další krok před 3D |
|---|---|---|
| Pojízdná zásuvka 4932498651 | Současná EU/CZ/SK stránka H × W × D = 550 × 610 × 480 mm, katalog výrobce 2025 = 665 × 570 × 480 mm. | Výrobce musí potvrdit skutečnou obálku, nebo změřit fyzický kus. |
| Nízký kompaktní organizér 4932471065 | Současná stránka H × W × D = 64 × 249 × 411 mm; katalog 2020/21 má 250 × 380 × 65 mm. | Potvrdit správné rozměry i splnění hranice 400 mm pro skutečný kus. |
| Kompaktní box 4932471723 | Výrobce 411 × 249 × 330 mm a 2,50 kg; ELKOV v popisu 411 × 254 × 330 mm a v parametrech 3,07 kg. | Potvrdit šířku a hmotnost bez obalu. |
| Box 4932464080 / velký box 4932464079 | Prodejce používá 560 × 410 × 170 / 290 mm; výrobce 561 × 411 × 165 / 282 mm v konvenci L × Š × V. | Rozlišit starší zaokrouhlené hodnoty od fyzické obálky. |
| Profesní kufry 4932499703 / 4932499704 | Rozměry od prodejců, nikoli v tabulce výrobce; nosnost a vnitřní rozměry nedohledané. | Vyžádat technický list nebo změřit konkrétní kus. |
| XL 4932501784 / 4932478162 | Stránka výrobce spojuje staré a nové číslo se specifikací XL; EAN a hmotnosti se liší. | Ověřit konstrukční shodu verzí; netvrdím ji pouze podle stejné rozměrové tabulky. |
| Organizéry a část dalších dílů | Nosnost není veřejně doložená. | Vyžádat ji od výrobce; nepřepisovat odhadovanou hodnotu. |
| Všechny typy | Chybí kótování drážek PACKOUT, zámků a držadel; polohy z fotografie neurčuji. | Až po schválení etapy 1 řešit CAD a podmínky licence, nebo přesné měření. |

## Zdroje a reprodukce

Primární přehledy: [boxy](https://www.milwaukeetool.eu/en-eu/storage/packout/packout-tool-boxes/), [organizéry](https://www.milwaukeetool.eu/en-eu/storage/packout/packout-organisers/), [pojízdné díly](https://www.milwaukeetool.eu/en-eu/storage/packout/packout-rolling-storage/), [brašny](https://www.milwaukeetool.eu/en-eu/storage/packout/packout-totes-and-bags/), [termoboxy](https://www.milwaukeetool.eu/en-eu/storage/packout/packout-tumblers-and-coolers/). Každý číselný údaj, EAN, prodejní nabídka a fotografie má vlastní URL v `kufriky.json` a v detailu tabulky. Hlavní prodejní zdroje: V-V nářadí, OK nářadí, Elglobal, ELKOV, ELVIN a CIME.

- `kufriky.json` a `kufriky.csv`: datové soubory se schématem pro další výrobce/řady. `model_file` je null a stav uvádí čekání na schválení.
- `nahled/`: pouze veřejné statické soubory určené pro vlastní náhled. Všechny fotografie jsou lokální; žádné CDN, analytika, formuláře nebo runtime dotazy na jiné služby. Zdrojové odkazy otevírá až uživatel.
- `zdroje/`: soukromé pracovní výpisy veřejných specifikací, prodejní doklady a kontrolní součty fotografií. Nejsou součástí veřejného náhledu. Při průzkumu veřejné výrobní stránky obsahovaly identifikátory vyhledávací služby; původní pracovní HTML `zdroje/official-boxes.html` bylo odstraněno a do výstupů se nepřenáší.
- `sestav_katalog.py`: sestavení ze zdrojových výpisů bez sítě. `nacti_vyrobce.py`, `cti_verejne.py`, `dopln_zdroje.py`, `sber_verejnych_podkladu.py` a `stahni_miniatury.py` slouží pouze k autorizovanému čtení veřejných podkladů; nejsou testy. Doplněk některých prodejců z veřejného indexu je výslovně označený.
- `over_katalog.py`: devět čistých kontrol dat, os, zdrojů, cen bez DPH, EAN, fotografií a pravidel statického náhledu.
- `over_nahled.js`: osm skupin skutečných kontrol prohlížeče z místních souborů; veškeré požadavky zachyceny a obslouženy offline. První pokus o simulované stažení CSV v prohlížeči se zrušil, protože syntetická adresa nemá síťový server. Finální kontrola proto ověřuje místní cíle odkazů a obsah exportů, nikoli reálné síťové stažení. Žádná ochrana není obcházena.
- `overeni/prohlizec.json`, `tabulka-desktop.png`, `tabulka-mobil.png`: doklady funkčnosti a vzhledu. Všechny finální kontroly prošly.
- `overeni/nahrani.json`: všech 40 statických souborů bylo zkopírováno do nové vlastní náhledové složky a porovnáno bajt po bajtu. Veřejnou stránku, JSON a jednu miniaturu jsem následně přečetl běžným veřejným GET: všechny vrátily 200 a shodný obsah (`overeni/precteny_verejny_nahled.json`). Čisté testy zůstaly offline; toto bylo samostatné čtení zveřejněných podkladů.

Čisté opakování kontrol:

```bash
python3 vystupy/kufriky/over_katalog.py
node vystupy/kufriky/over_nahled.js
```

Prohlížečový skript používá pouze existující místní knihovnu Playwright a místní Chromium. Nepotřebuje DB, internet ani přihlášení a ukládá své soubory pouze do vlastního výstupu.

Fotografie slouží jako interní miniatury s noindex. Jejich práva náležejí výrobci; volnou licenci pro další použití netvrdím. Žádný účet, e-mail, formulář, objednávka ani přihlášení nebyly použity. Cizí kód ani služby nebyly změněny.
