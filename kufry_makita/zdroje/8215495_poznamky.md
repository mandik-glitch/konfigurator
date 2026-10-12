# Makita MAKPAC Typ 1 (821549-5, kód 8215495) – poznámky k modelu

Model: `kufr_8215495.mjs` → `makpac.mjs` (sdílený sestavovač) + `makpac_zaklad.mjs` (půdorysný loft, extruze, barva `tyrkys`), `makpac_par.mjs` (rozměry a půdorysné snímky, **jediný parametr je výška V = 105 mm**), `makpac_korpus.mjs`, `makpac_vicko.mjs`, `makpac_madlo.mjs`, `makpac_logo.mjs`. Sestavení `node kufry_makita/vytvor.mjs` → `modely/8215495.glb` (24 dílů, ~8 100–8 600 trojúhelníků, ~0,33 MB, obálka **295 × 395 × 105 mm, odchylka 0/0/0 mm** při madle sklopeném). Souřadnice: X = hloubka 295 (čelo se západkami a madlem do +X), Y = délka 395, Z = výška, počátek ve středu obálky. Všechny čtyři typy mají stejný korpus i víko, liší se jen výškou V (105 / 157 / 210 / 315); generátor `sestav(sku, V)` je jeden.
Zadání: ZAVŘENÁ verze a vnější pohled, **vnitřek hladký** (dutina se stěnou 3 mm, rovné dno).

## Pohyblivé uzly
- `vicko`: pivot na pantové hraně (x = −143,5, z' = V − 25), `extras.osa = [0,−1,0]`, `max_uhel` 110° (`--pose vicko=100` otevře, viz srovnání `c04`).
- `vicko/madlo`: vnořená skupina, pivot na ose čepů madla (x = 48, rovnoběžně s Y), `extras.osa = [0,1,0]`, `max_uhel` 100°. **Výchozí poloha (0°) = sklopené do kapsy ve víku** (z toho je obálka 295 × 395 × 105); vztyčené madlo (90°) sahá cca 66 mm nad horní plochu a obálku překračuje (stejně jako výklopné díly u ostatních modelů).
- Západky (čelní i koncové) jsou pevné díly (otevírání z fotografií nelze určit).

## Rozměry
- Katalog makita.cz 395×295×105 (makitauk.com: 110). Na zbozi.cz veden pod novým číslem 821549-5 (staré 142770-6). Rozdíl výšek 5 mm mezi zdroji **nelze rozhodnout**; v modelu je hodnota z CSV (makita.cz). Délka 395 a hloubka 295 jsou z katalogu (makitauk.com u Typu 3 uvádí 396 × 296 – 1 mm, v tolerance obálky ±1 mm).
- Vnitřní rozměry a hmotnost výrobce neuvádí.

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `../fotky_url.tsv`)
c01 šikmo zleva, c02 šikmo zprava, c03 čelo shora, c04 otevřený; c05–c07 jsou detaily západky/stohování (bajtově shodné u všech čtyř typů, nejde o daný typ), c08 schéma stohování. Žádné kóty, rozlišení max 1000 px.

## Změřeno (z fotografií, ±2–3 mm; měřítko z celkové šířky 395 mm resp. výšky; Typ 4 c03/c09 jako referenční pohled, kontrola na Typu 2 a 1)
- Spára víko/korpus 26 mm pod horní plochou; víko je na čele o 0,6 mm vysunuté (lem).
- Čelní západka: rámeček Y 140…181 mm (od osy), černá západka 35 mm široká, horní hrana kapsy 5,3 mm pod horní plochou, dolní 77,6 mm (u Typu 1 přechází kapsa západky do nožkové kapsy).
- Stohovací kapsa dole: Y 140…181, výška 45,7 mm, se dvěma zuby (13 mm vysokými) v každé kapse (poloha ±12,5 mm od středu západky z c03 Typu 4).
- Vtlačený čelní panel: Y ±84,4, horní hrana 52 mm pod horní plochou, rohy R 17; prstová jamka v čele víka Y ±52.
- Kapsa madla ve víku 276 × 120 mm (X −62…58, Y ±138), logo-plocha X 74…136, Y ±118; madlo 268 mm široké (Y ±134), ramena 82 mm; poloha čepů a kapsy zpětnou projekcí c03 na rovinu horní plochy (Typ 4).
- Koncové stěny (±Y): vtlačený panel, západka u zadní strany (X −123…−88; z c01/c02), zadní nožková kapsa, štěrbina u přední hrany – poloha z c01/c02.

## Odhad (z fotografií nelze změřit)
Poloměr svislých rohů 8 mm a zaoblení horních/spodních hran; hloubky kapes (západka 13, nožka 12, panel 2, prstová jamka 14, kapsa madla 22, rameno stohování 5 mm); tloušťka stěn 3 mm; výška zubů v nožkových kapsách; tloušťka madla 16 mm a tvar jeho ramen; poloha zadní koncové západky.

## Neověřeno / nemodelováno
- **Zadní (pantová) strana a spodek** na fotografiích nejsou: zadní stěna je hladká, **pant a čepy nejsou modelovány**; spodní plocha je rovná.
- Vnitřek korpusu a vnitřek víka (žebra, kapsa madla zevnitř – vidět na c04): hladký / nemodelováno.
- Vroubkování západek (jen černý tvar + proužek), tečkování gumové vložky madla (jen tmavá ploška s malými válečky), reliéfní nápisy na západkách.
- Logo: **jednoduché bílé tahové písmo „Makita“ na plošce** – není to věrné logo (ochranná známka), jen orientační popisek.
- Odstín tyrkysu: z fotografií čelní plocha ≈ sRGB (0, 115–125, 132–145); v GLB `tyrkys` lineárně (0; 0,17; 0,24), drsnost 0,65 – není kalibrováno proti reálnému plastu. Materiály: `tyrkys` (korpus, víko), `cerna` (madlo, západky), `cerna_mat` (vložka madla, vroubky), `bila` (logo). V `jadro/glb.js` je `tyrkys` světlejší (0; 0,32; 0,38) – model ho přepisuje jen v paměti při generování (jádro se nemění).
- Hmotnost, nosnost, přesná podoba stohovacích zámků.

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse.sh`, `nastroje/celo.mjs`)
| pohled | fotografie | IoU | póza | landmarky (průměrná chyba) |
|---|---|---:|---|---|
| `c01` | šikmo zavřený zleva (C2L0, madlo vztyčené) | **0.947** | madlo 86° | bez landmarků |
| `c02` | šikmo zavřený zprava (C8R0) | **0.952** | madlo 90° | bez landmarků |
| `c03` | čelo shora, téměř přímý pohled (C1C0) | **0.951** | madlo 90° | bez landmarků |
| `c04` | otevřený, víko ~100° (F_001) | **0.960** | vicko 101° | bez landmarků |

Dvojice foto | model | překryv obrysu byly prohlédnuty (ne jen IoU). Kamera je odhad z obrysu (a u části pohledů z ručních bodů, `zdroje/landmarky/*.json`), ohnisko není změřené; IoU u šikmých pohledů proto zahrnuje i chybu kamery. Póza madla/víka se při odhadu doladila; doladěný úhel madla vyšel 70–96° (u části pohledů na dolní mezi 70°) – kompenzuje i chyby tvaru madla a kamery, **není to měření úhlu** (na fotografiích výrobce vypadá madlo svisle).
**Systematický rozdíl:** fotografie výrobce má u šikmých/čelních pohledů horní hrany víka sražené a horní rohy víka „ušaté“ (vystupující lem nad západkami); model má jednoduše zaoblený obdélník. Fotografie je také o 2–4 % širší oproti výšce, než odpovídá katalogovým rozměrům při jednotné perspektivě (ruční landmarky dávají nekonzistentní poměr stran) – to je buď nepřesnost mých landmarků, nebo jiný poměr stran snímku; neověřeno.
Nástroje: `nastroje/srovnej.mjs` (odhad kamery + póz, render + json do `kufriky_cloud/srovnani/8215495/`), `celo.mjs` (téměř ortografický pohled oříznutý na obrys), `kalibruj.py` (kamera z ručních bodů, kopie z kufry_hilti), `unproject.mjs` (zpětná projekce pixelu na rovinu modelu), `maska_barva.py`.
