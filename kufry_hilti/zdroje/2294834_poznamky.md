# Hilti kufr TE 6-22 prázdný (2294834) – poznámky k modelu

Model: `kufr_2294834.mjs` (+ `p2294834_data.mjs` data z fotografie; **kód skořepiny je společný** s 2329229: `p2329229_zaklad.mjs`, `p2329229_skorepina.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2294834` → `modely/2294834.glb` (30 dílů, ~4 100 trojúhelníků, obálka 395 × 495 × 149 mm, odchylka 0/0/0 mm). Náhled `nahled/2294834.html`, srovnání `kufriky_cloud/srovnani/2294834/celo.*`.
Souřadnice a konvence stejné jako u 2329229. Víko = skupina `vicko`, pivot na pantové hraně, `extras.osa = [0,−1,0]`, `max_uhel = 135`.
Zadání (Robert): ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen, nedokončeno**.

## Je skořepina shodná s 2329229? Závěr: NE prokazatelně – proto dva datové soubory
Pro: stejné katalogové rozměry (495 × 395 × 149, hilti.cz), po normalizaci na stejný rám se siluety fotografií c01 shodují na **IoU 0,992** (spodních 74 % hloubky 0,996) – půdorys je prakticky stejný.
Proti: **reliéf víka se liší** a není to jen logo: okno madla je užší (nahoře 305 vs. 366 px z 1200, tj. 126 vs. 151 mm) a nemá šedý límec, příčka madla je užší (427 vs. 496 px), západky menší (136 × 62 vs. 166 × 77 px), čelní plató začíná výš (py ~135–160 vs. 160–205), nopy jsou širší a nižší (226 × 53 vs. 160 × 64 px), drážka s logem má užší zadní svah (25 vs. 52 px), logo je menší a výš (121 vs. 127 px vysoké, uprostřed py ~455 vs. 478). Poměr stran fotografií je 1,277 (2294834, c01 = L137214) vs. 1,232 (2329229, L128480), katalog 1,253 – část rozdílu může být perspektiva/ořez fotografií, ale rozdíl madla a západek ne.
Navíc **L137214 je generická fotografie** sdílená i s jinými kufry Hilti (README_vlna2.md: SF 6(H)-22 444 × 395 × 122, SF 4(H)-22 395 × 362 × 119 mají totéž foto), takže nemusí zobrazovat právě skořepinu 495 × 395 × 149. Rozměr platí z hilti.cz, foto je jen vizuální předloha.
Jedna GLB pro oba by tedy nebyla věrná; společný je kód (loft, pant, výšky), data se liší.

## Fotografie (jen čtena ze scratchpadu, v repu není; URL v `../fotky_url_vlna2.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L137214, 1200×940) | pohled shora na zavřený kufr, čelo nahoře, s logem | půdorys, reliéf víka, logo; porovnání `celo` |
Otevřený pohled, vnitřek a zadní/boční/spodní strany **nemá z čeho vzniknout**.

## Změřeno (z c01, px → mm: 495/1199 vodorovně, 395/939 svisle, normalizováno na obálku katalogu; ±1,5 mm)
Půdorys (silueta, rohy, pás uprostřed), okno madla (obrys, černý límec, příčka), západky, plató a drážka (hrany jasových přechodů), nopy, logo HILTI (písmena z masky bílé). Celá data v `p2294834_data.mjs`.

## Výsledky porovnání (`nastroje/srovnej_vse_2294834.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, pohled shora, téměř ortografický, render oříznut na obrys a roztažen na rozměr fotografie) | **0,985** | stejný postup jako u 2329229 |
Dvojice foto | model | překryv byla prohlédnuta (madlo, okno, západky, nopy, logo, plató). Další pohledy (otevřený, boční) pro 2294834 **neexistují**, srovnání není možné.

## ODVOZENO z 2329229 (výslovně)
Tvar a stavba skořepiny, které fotografie 2294834 neukazuje: dělicí spára (z' = 88), výška desky/plató/nopů, zaoblení horních hran, tloušťka stěn, pant (7 úseků), tvar otevřeného víka a kapsy západek, spodní/horní půlka madla, hladká dutina a hladká černá deska místo vložky (`vlozka_zjednodusena`). Hodnota úhlu otevření (max 135°) je převzata z 2329229. U 2294834 jsou všechny tyto údaje **neověřené odhady**.

## Neověřeno / zjednodušeno
- Vše výše „odvozeno"; navíc: vnitřek (dutina, vložka TE 6-22 – má jiné kapsy než SF/SI, žádná fotografie), spodek, zadní strana, nožky, žebra uvnitř víka.
- Západky jsou součástí víka (zjednodušení), pohyb západek nemodelován.
- Logo jen jako bílá ploška (nevyražené), bez textury povrchu a nápisů na západkách.
- Materiály: červená `cervena` (v c01 je o něco tmavší/oranžovější než u 2329229 – rozdíl osvětlení, ne jiný materiál; rozdíl není ověřen), černá `cerna`, logo `logo_bila`.
