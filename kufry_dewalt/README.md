# Kufry DeWalt TSTAK / TOUGHSYSTEM 2.0 – podklady pro 3D modely (2026-10-12)

Data: `kufriky_dewalt.csv` (sloupce jako u Hilti + `zdroj_prodejnosti`, `poznamka`), odkazy na fotografie: `fotky_url.tsv` (sloupce: číslo, soubor, URL, stav, rozlišení, pohled). Fotografie se do repa neukládají (jen scratchpad session).

Konvence rozměrů: `D_mm` = delší strana půdorysu (čelo), `S_mm` = hloubka, `V_mm` = výška.

## Jak byl výběr proveden

Doložená prodejnost = **zbozi.cz (Seznam)**, řazení „Podle oblíbenosti“, dotazy „dewalt tstak“, „dewalt dwst“, „dewalt toughsystem“, „dewalt kufr“ a dotazy na konkrétní čísla, stav 2026-10-12. U položky je počet hodnocení zákazníků a počet obchodů, které ji nabízejí. **Není to prodejní žebříček** – jen nepřímý ukazatel rozšířenosti.

| číslo | typ | hodnocení | obchodů |
|---|---|---|---|
| DWST83346-1 | TSTAK hluboký IP54 | 57 (95 %) | 41 |
| DWST83345-1 | TSTAK II mělký IP54 | 22 (95 %) | 30 |
| DWST83294-1 | TOUGHSYSTEM 2.0 DS300 | 15 (96 %) | 32 |
| DWST83342-1 | TOUGHSYSTEM 2.0 DS400 | 15 (91 %) | 28 |
| DWST83295-1 | TOUGHSYSTEM 2.0 DS450 (pojízdný) | 11 (96 %) | 24 |

Co nebylo možné: **heureka.cz, alza.cz, kaufland.cz a mall.cz** z prostředí session odmítly přístup (ochrana proti robotům / 403 / 404); hornbach.cz a naradi-brno.cz jsem neanalyzoval. Žádný e-shopový žebříček „nejprodávanější“ tedy nemám.

### Co bylo záměrně vynecháno nebo nahrazeno

- **DWST82968-1** (TSTAK IP54 organizér s průhledným víkem, 35 hodnocení, 40 obchodů – ve skutečnosti 2. nejvíc hodnocený): **nahrazen**, protože na dewalt.cz/.co.uk/.de/.pl **nemá oficiální stránku ani fotografii** (jen datasheet: 440 × 332 × 119 mm). Do pořadí se může vrátit, pokud se použijí fotografie prodejců.
- **DWST83402-1** (21 hodnocení) a **DWST83395-1** (28 hodnocení, „TSTAK IP54 Combo Kit“): jsou to **sady více kufrů / kufr + zásuvky**, ne jeden kufr.
- **DWST1-70705 (TSTAK III, 16 hodnocení)** a **DWST1-70706 (TSTAK IV, 11)**: zásuvkové jednotky bez víka; na oficiálních stránkách ani v datasheetu nemají rozměry.
- **DWST1-71194 / DWST1-71195** (původní TSTAK V/VI): na zbozi.cz jen 4 hodnocení, na dewalt.cz bez stránky.
- **DWST83344-1** (TSTAK IP54 s horním organizérem, 7 hodnocení, 24 obchodů; 440 × 332 × 183 mm; datasheet + 3 oficiální fotky na dewalt.co.uk) – rezerva, kdyby se DS450 ukázal nevhodný.
- „TSTAK I–V“ z původní řady (DWST1-70xxx) tedy v pětce nejsou; novější IP54 provedení (DWST833xx) mají na zbozi.cz víc hodnocení.

## Rozměry a hmotnost

- **dewalt.cz rozměry u těchto kufrů neuvádí** (tabulka specifikací má jen typ, materiál, barvu, uzamykatelnost, čárový kód).
- Rozměry (šířka × hloubka/délka × výška) jsou z **datasheetu DeWalt** (jednostránkové PDF hostované na `assets.cef.co.uk/downloads/pdg/dewalt_<sku>_datasheet/…`, sestavuje ho výrobce, hostuje britský prodejce CEF). Uvedeno proto jako sekundární oficiální zdroj; ostatní prodejci se rozměry shodují (např. DWST83346-1 440 × 333 × 302, DS300 554 × 371 × 308).
- **DS450 (DWST83295-1)**: datasheet uvádí 554 × 500 × 685 mm; výška 685 mm pravděpodobně zahrnuje výsuvnou rukojeť (netestováno), nosnost 113 kg.
- **Vnitřní rozměry nejsou nikde uvedeny.** **Hmotnost výrobce neuvádí** (prázdný sloupec). Orientačně od prodejců (neověřeno, málo zdrojů): DWST83346-1 ≈ 4,7 kg (jeden prodejce), DS300 ≈ 4,7 kg (dva prodejci shodně, jeden 5,5 kg), DS400 ≈ 5,6 kg (zbozi.cz).

## Fotografie (scratchpad `kufry2/<číslo>/cNN.jpg`)

Oficiální `assets.dewalt.cz/EMEA/PRODUCT/IMAGES/HIRES/WHITEBG/<číslo>_<n>_2560.webp` (z JSON stránky produktu na dewalt.cz), **převedeno z WebP do JPG**, průhledné pozadí vyplněno bílou. Studiové („Beauty“) záběry jsou čtvercové 2560 × 2560 (předmět zabírá jen část), „Application“ jsou fotky ze stavby (kufr je v záběru malý, použitelné jen k orientaci).

| číslo | kufr | fotek celkem | z toho studiových | pohledy studiových |
|---|---|---|---|---|
| DWST83346-1 | TSTAK hluboký | 7 | 3 | šikmo zavřený, čelo (rovně), čelo + vyjmutá vnitřní vložka |
| DWST83345-1 | TSTAK II mělký | 5 | 3 | šikmo zavřený, zepředu, kufr postavený na bok (logo DEWALT, boční stohovací západky) |
| DWST83294-1 | DS300 | 7 | 3 | šikmo zavřený, šikmo zavřený (jiný úhel), otevřený s vnitřkem |
| DWST83342-1 | DS400 | 7 | 3 | šikmo zavřený, šikmo zavřený (jiný úhel), otevřený s vnitřkem |
| DWST83295-1 | DS450 | 5 | **1** | jen šikmo zavřený s výsuvnou rukojetí a koly |

Žádná fotografie nemá kóty. Z oficiálních zdrojů se nepodařilo získat více než 3 studiové záběry na kufr.

## Vhodnost pro model

- **Velmi vhodné:** `DWST83346-1`, `DWST83345-1` (TSTAK – shodný půdorys 440 × 333, liší se výška 302/162 → jedna parametrická skořepina, kovové západky, madlo na víku, boční stohovací západky) – ale chybí otevřený pohled.
- **Vhodné:** `DWST83294-1`, `DWST83342-1` (ToughSystem 2.0 – shodný půdorys 554 × 371, výška 308/408; mají i otevřený pohled s vnitřkem a kovové drátové západky).
- **Problémové:** `DWST83295-1` (DS450 – pojízdný, výsuvná rukojeť a kola, jen 1 studiový záběr, rozměr 685 mm nejasný); všechny kufry jsou jen odvozeny z úhlů a bez kót, vnitřní žebra a tvar zámků je třeba domodelovat odhadem.
