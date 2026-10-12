# Hilti ProKit PKC 19 (2437355) – poznámky k modelu

Model: `kufr_2437355.mjs` (+ `p2437355_zaklad.mjs`, `p2437355_korpus.mjs`, `p2437355_vicko.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2437355` → `modely/2437355.glb` (75 dílů, ~5 400 trojúhelníků, obálka 387 × 554 × 168 mm, odchylka 0/0/0 mm). Souřadnice: X = hloubka (čelo s madlem do +X), Y = délka, Z = výška, počátek ve středu obálky. Víko = skupina `vicko`, pivot na pantové hraně (x = −187, z' = 121), `extras.osa = [0,−1,0]`, `--pose vicko=100` otevře. Šablona = PKC 35 (2437394, stejná řada, stejný postup „půdorysný loft“); tvar a poměry jsou přeměřeny z fotografií PKC 19, nic se nepřebíralo ze šablony bez ověření (míry PKC 35 slouží jen jako počáteční odhad u neviditelných částí – viz „neověřeno“).
Zadání (Robert): hlavní je ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen, nedokončeno**.

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `2437355_dalsi_fotky.tsv`, `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L153708, 800×243; měřeno ve velikosti 1200×365, `2437355_dalsi_fotky.tsv`) | přímý čelní pohled, těsně oříznutý | měření čela (px → mm: 554/1200 vodorovně, 168/365 svisle), porovnání `celo` |
| L153709 (ISO, 1200×659; stránka hilti.cz ho uvádí jako „L153709_ISO“) | zavřený, šikmo zepředu a z konce (+Y), shora | **koncová stěna, logo, nožky, horní plocha, pant**, kamera z landmarků, porovnání `zavreny-iso-L153709` |
| c02 (L156735), c03 (L156503 s kótami) | otevřený, shora | jen kóty a orientace uvnitř (porovnání s fotografií nebylo děláno – zadání je zavřená verze) |
| c04 (L154588) | aplikační snímek | nepoužitelné k měření |
| c05–c08 | miniatury souvisejících produktů | ignorovány |
Sourozenci (2437394/-354/-399, 2441669) – jen pro orientaci; rozměry z nich nejsou.

## Změřené rozměry (z čelní fotografie c01, ±1,5 mm; profil Y z obrysu po 2–3 mm výšky)
- Délka 554 (lem víka, celá šířka c01), výška 168 (celá výška c01), hloubka 387 (katalog; z čelní fotografie neměřitelná).
- Lem víka z' 118,2–127,3 (±277), rovný plášť víka ±271,5 do z' 149,4, odtud zkosení konců na ±243,1 v z' 167,8 (sklon 1,52). Límec korpusu ±271,7 (z' 100,6–119), rameno z' 91 → 100,6 (±257,1 → ±271,7), spodní stěna ±256,5…257,1.
- Spodní hrana: zkosení od z' 29 (±254,6) po z' 12,2 (±234,5). Rovná část čelní hrany končí v Y = ±237,8 (spodek) / ±245 (límec); šikmý roh pod ~45°.
- Spára víko/korpus z' 119,5; vnitřní hloubka 102 → dno z' 17,5 (katalog 102).
- Madlo: výřez šířky 210,6 (px 372–828, Y ±105,3 v lemu víka, ±108,5 ve spodní části), černý rám: horní příčka s deskou (logo HILTI černé na černém), dva sloupky Y ±70,6…±108,5, spodní úchop z' 12–36, vnitřní kapsa Y ±70,6 s černým jazykem (Y ±27,7, z' 38–65).
- Západky: kapsy Y −205,9…−139,9 / +139,9…+205,9, z' 87,3–119, červený jazyk 34,7 mm široký (z' 98,8–116,2); šrouby čepů Y ±133,4 / ±214,5, z' 134,6, boss Ø 15, hlava Ø 10; drážky nad šrouby 7 mm.
- Nožky: 4 (Y ±69,3, ±208,7; šířka 43–48 mm; z' 0–12,8), černé patky Y ±9.
- Logo HILTI (bílá plocha) je na KONCOVÉ stěně +Y (ne na čele): X +41,4 … −46,5, z' 71–83 (zpětná projekce ISO na rovinu Y = 256,5, ±3 mm).
- Kóty výrobce (c03): vnější 38,7 × 55,4 × 16,8 cm, vnitřní 51,6 × 31,8 × 10,2 cm. **Rozpor:** katalog (zadání) uvádí vnitřní hloubku 365 mm, c03 kótuje 31,8 cm. Model drží katalog (365 × 516 × 102 u okraje); 31,8 cm patrně platí u dna (tam je dutina užší – římsa u pantu, šikmé stěny) – neověřeno.

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2437355.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, rovnoběžný pohled oříznutý na obrys) | **0,989** | rozdíl obrysu ≤ 1,5 mm, kromě nožek (tvar patek) |
| `zavreny-iso-L153709` | 0,948–0,950 | kamera z 4 landmarků (šrouby, rovina čela) + obrys; **hloubka (osa X) není landmarky omezena** – část zbytkové odchylky je chyba kamery, ne modelu. Zbylé rozdíly: zadní horní hrana víka (fotografie ~5–10 px výš: kloubová oka vzadu), tvar spodní strany a nožek |
Překryvy foto | model byly prohlédnuty (ne jen IoU): čelo (madlo, kapsy západek, šrouby, rozměr rámu) sedí; ISO – čelo, šrouby, madlo, kapsy sedí, konec a logo v poloze. Dvojice se generují jen lokálně do scratchpadu; v repu jsou jen naše rendery + json (`../../kufriky_cloud/srovnani/2437355/`).
Otevřené pohledy (c02, c03) s modelem porovnány NEBYLY (zadání: zavřená verze).

## Neověřeno / zjednodušeno
- **Vnitřek zjednodušen, nedokončeno:** dutina je hladká vana (stěna 3,5 mm, rovné dno), **chybí** dvě černé dělicí příčky (c02), žebra a vybrání ve stěnách a podlaze (hnízda, zářezy v dně), vnitřní trojúhelníkové žebrování víka, těsnění. Víko je dutý plášť (stěna 3 mm).
- **Spodek a zadní (pantová) strana:** na žádné fotografii nejsou vidět. Spodní plocha, zadní stěna, hloubka všech výřezů a poloha zadních zkosení jsou **neověřené odhady**. Nožky: z ISO je u konce vidět blok jen v X ≈ −125…+66; před ním a za ním je nožka v modelu nižší (spojka z' 6) – tvar je odhad. Pant (7 úseků po ~71 mm, kolík, kloubová oka na horní hraně) je přibližný.
- Hloubka kapsy madla (X dno = 150, tj. 37 mm), kapsy západek (6 mm), drážek nad šrouby (3 mm), výška a hloubka černých sloupků a úchopu madla: odhad (z čela neměřitelné). Madlo/úchop je pevný díl.
- Horní plocha: v modelu je plató z' 160 a zadní lem do z' 168 (obrys z čela dává 167,8 v celé šířce ±243); skutečné členění horní strany (obdélníkový panel, zářezy, kruhové logo, hřebeny) je v modelu jen naznačeno (kloubová oka zadní hrany); poloha čelního zkosení víka (X 187 → 160) je odhad.
- Západky (červené jazyky), třmeny a madlo jsou **pevné díly**; jediný pohyblivý uzel je `vicko`. Jak se západky/madlo pohybují, z fotografií nelze určit.
- Nápisy: „PROKIT“ vyražený vlevo nahoře na čelním zkosení víka, červený obdélníkový nášlapný „pad“ uprostřed zkosení, kruhový znak na horní ploše, drobné nápisy, jemná textura povrchu (zrnění), logo HILTI na černé příčce madla – nemodelováno; logo na konci je jen ploška.
- Materiál: jediná červená (`cervena`) pro korpus i víko, černé díly madla a patek. Odstín vůči fotografii není kalibrován.

## Zbylé viditelné rozdíly proti fotografii
- Čelo: madlo nemá zaoblený úchop (v modelu zkosený hranol), sloupky bez vnitřních žeber a háčků; spona vpravo od madla (svislé žebro) zjednodušena na kvádr; lem víka bez zaoblení horní hrany.
- Rohy: zkosení rohu čelo→konec (cfx 19/26) je odhad; zrnitá šikmá plocha rohu na fotografii je v modelu hladká.
- ISO: zadní horní hrana víka; poloha a tvar nožek a spodní hrany; nesedí drobné horní prvky.
- Nástroje: `nastroje/fit_lm_2437355.mjs` (kopie `fit_lm.mjs` s dolní mezí ohniska 1,2°; ISO fotografie je téměř ortografická, fov ≈ 2,3°), `nastroje/unproject_2437355.mjs` (zpětná projekce pixelu na rovinu modelu, hodnoty ±3 mm), `nastroje/srovnej_vse_2437355.sh`. Sdílené: `porovnej_celo.mjs`, `../earcut2.mjs`, `kufriky_cloud/render/*`.
