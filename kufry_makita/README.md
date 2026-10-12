# Kufry Makita MAKPAC – podklady pro 3D modely (2026-10-12)

Data: `kufriky_makita.csv` (sloupce jako u Hilti + `zdroj_prodejnosti`, `poznamka`), odkazy na fotografie: `fotky_url.tsv` (sloupce: číslo, soubor, URL, stav, rozlišení). Fotografie se do repa neukládají (jen scratchpad session).

Konvence rozměrů: `D_mm` = delší strana půdorysu (čelo s madlem a západkami), `S_mm` = hloubka, `V_mm` = výška. Čísla u Hilti ProKit/vlny 2 jsou opsaná tak, jak je uvádí hilti.cz.

## Jak byl výběr proveden

Doložená prodejnost = **zbozi.cz (Seznam)**, dotaz „makita makpac“, řazení „Podle oblíbenosti“ (výchozí), stav 2026-10-12: u každé položky počet hodnocení zákazníků a počet obchodů, které ji nabízejí. To je jediný použitelný veřejný ukazatel, který se dal získat. **Není to prodejní žebříček** – hodnocení a počet nabízejících obchodů jen nepřímo vypovídají o prodejích.

| pořadí podle hodnocení | číslo | typ | hodnocení | obchodů |
|---|---|---|---|---|
| 1 | 821550-0 | MAKPAC Typ 2 | 200 (93 %) | 40 |
| 2 | 821551-8 | MAKPAC Typ 3 | 146 (92 %) | 49 |
| 3 | 821552-6 | MAKPAC Typ 4 | 85 (93 %) | 46 |
| 4 | 821549-5 | MAKPAC Typ 1 | 31 (90 %) | 39 |
| 5 | 191X80-2 | MAKPAC organizér s krabičkami (Makor1) | 8 (100 %) | 32 |

Co nebylo možné: **heureka.cz, alza.cz, kaufland.cz a mall.cz** z prostředí session odmítly přístup (ochrana proti robotům / 403 / 404), takže z nich nejsou žádné údaje. hornbach.cz a naradi-brno.cz jsem neanalyzoval. Žádné pořadí „nejprodávanější“ z e-shopu jsem tedy nezískal. Výběr typů 1–4 odpovídá zadání (systémová řada MAKPAC Typ 1–4) a potvrzuje ho zbozi.cz.

- Pátá pozice (`191X80-2`) je další položka v pořadí; je to **organizér s průhledným víkem a 13 krabičkami**, ne běžný kufr. Rezerva s výrazně jiným tvarem: `MAKTRAK P-91001` (pojízdný box, 1 hodnocení, 32 obchodů, 23 oficiálních fotek) – mimo zadání (nejde o prostý kufr).
- Typ 1 je na zbozi.cz veden pod novým číslem 821549-5 (31 hodnocení); staré číslo 142770-6 (3 hodnocení) je totéž zboží.

## Rozměry a hmotnost

- Zdroj: `katalog.makita.cz` (oficiální katalog Makita ČR – rozměr je v názvu položky) a `makitauk.com` (oficiální web Makita UK, pole „Product Dimensions (L x W x H)“).
- **Rozdíl ve výšce o 5 mm mezi zdroji** (např. Typ 1: 105 × 110, Typ 2: 157 × 163, Typ 3: 210 × 215, Typ 4: 315 × 320). V CSV jsou hodnoty z `makita.cz`; u Typu 3 odpovídají datasheetu Makita UK (396 × 296 × 210 – ten jsem viděl jen ve výsledku vyhledávání, ne stažený). Která hodnota je „vnější včetně nožek/madla“, nevím.
- `191X80-2`: makita.cz rozměr neuvádí, použito 110 mm z makitauk.com.
- **Vnitřní rozměry nejsou nikde uvedeny** (prázdné sloupce).
- **Hmotnost oficiálně uvedena není** (prázdný sloupec). Hodnoty od prodejců (neověřené, nesouhlasí): Typ 2 1,5 kg a Typ 4 2,5 kg (popis na zbozi.cz), Typ 3 1,9 kg u jednoho prodejce (jiné uvádějí 3,1 / 1,0 / 0,7 kg).

## Fotografie (scratchpad `kufry2/<číslo>/cNN.jpg`)

Oficiální `fi.makitamedia.com/images/3_Makita/304_accessories_GS1/30410_JPG_zoom/…` (odkaz z `makitauk.com`); **nejvyšší dostupné rozlišení je 1000 px na delší straně**, bílé pozadí.

| číslo | typ | fotek | pohledy |
|---|---|---|---|
| 821549-5 | Typ 1 | 8 | šikmo zavřený zleva (C2L0) a zprava (C8R0), čelo shora (C1C0), otevřený (F_001), 3× detail západky/stohování (F_002–F_004), schéma stohování (F_005) |
| 821550-0 | Typ 2 | 8 | totéž |
| 821551-8 | Typ 3 | 8 | totéž |
| 821552-6 | Typ 4 | 9 | totéž + `C1N1` (čelo, další varianta) |
| 191X80-2 | organizér | 2 | c01 (C2L0) otevřený s krabičkami, c02 (C1N1) zavřený šikmo s průhledným víkem |

(Pozn.: F_002–F_004 jsou u Typů 1–4 bajtově shodné soubory – detaily západky/stohování, ne foto daného typu; F_005 je schéma stohování zvlášť pro každý typ.) Žádné kóty na fotkách nejsou.

## Vhodnost pro model

- **Velmi vhodné:** `821549-5`, `821550-0`, `821551-8`, `821552-6` – jednoduchý hranatý korpus, víko s madlem, dvě západky, otevřené pohledy, stejná konstrukce (liší se výška) → jeden parametrický model s výškou 105/157/210/315 mm.
- **Problémové:** `191X80-2` – průhledné víko, vnitřek se 13 krabičkami (jen 2 fotografie, žádný čelní pohled kolmo); vyžaduje průhledný materiál a vložené krabičky.
