# Hilti ProKit PKC 35 (2437394) – poznámky k modelu

Model: `kufr_2437394.mjs` (+ `p2437394_zaklad.mjs`, `p2437394_korpus.mjs`, `p2437394_vicko.mjs`), sestavení `node kufry_hilti/vytvor.mjs` → `modely/2437394.glb` (70 dílů, ~9 100 trojúhelníků, obálka 387 × 554 × 267 mm, odchylka 0/0/0 mm). Souřadnice: X = hloubka (čelo s logem do +X), Y = délka, Z = výška, počátek ve středu obálky. Víko = skupina `vicko`, pivot na pantové hraně (x = −187, z' = 213), `extras.osa = [0,−1,0]`, `--pose vicko=100` otevře.
Zadání se změnilo (Robert): hlavní je ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen, nedokončeno**.

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `2437394_dalsi_fotky.tsv`, `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L153706, 800×390) | přímý čelní pohled, těsně oříznutý | měření čela (px → mm: 554/800 vodorovně, 267/390 svisle), porovnání `celo` |
| c02 (L156736, 614×800) | šikmo shora, otevřený (víko ~98°) | kamera z 6 ručních bodů + obrys, porovnání `otevreny-c02` |
| c03 (L156504, 693×800) | totéž s kótami výrobce | kontrola rozměrů, porovnání `otevreny-c03` (maska podle červené barvy, aby šipky/popisky nekazily obrys) |
| L153707 (ISO, 800×562; stránka hilti.cz ho uvádí jako „L153707_ISO“; stažen i 1200×843) | zavřený, šikmo zepředu a z boku | **konec boxu, pant, horní držadlo**, kamera z 11 bodů, porovnání `zavreny-iso-L153707` |
| c04 (L154716) | aplikační snímek (stavba, vozík) | nepoužitelné k měření |
| c05–c08 | miniatury souvisejících produktů (c08 brašna) | ignorovány |
Sourozenci (2437354/-355/-399, 2441669) – jen pro orientaci (zámky, madlo, vzhled stohování); rozměry z nich nejsou.

## Změřené rozměry (z čelní fotografie c01 a ISO, ±1,5 mm)
- Délka 554 (celá šířka c01), výška 267 (celá výška c01), hloubka 387 (katalog; z čelní fotografie neměřitelná).
- Spára víko/korpus z' = 211,5 (c01 py 81); lem víka z' 210–218 vyčnívá o 6 mm na každém konci (Y ±277, c01 px 0..799, rozšířený lem).
- Horní pás čela z' 154–211 (spára py 165), levý/pravý konec čela y = ±241 (přímá část), pak zkosení rohu 22 mm.
- Madlo (černá lišta s jazykem) y ±104,6 (px 249–551), z' 182–211, kapsa madla zapuštěná o ~28 mm, podlaha kapsy z' 155.
- Západky: rámečky y −208…−141 / +141…+206 (px 101–198 / 604–698), z' 136–211; červený jazyk 37 mm široký; šrouby čepů px 90, 208, 592, 706 (z' 227).
- Logo HILTI: bílá plocha, px 462–676 × py 205–235 (y 43…191, z' 137…158), tloušťka znaků 11 mm, souřadnice znaků změřeny v c01.
- Stohovací zámek: černá kapsa vlevo dole (y −158…−122, z' 17…57), osmiúhelník podle c01 px 160–232 × py 277–361.
- Nožky: 4 patky (c01 px 91, 297, 503, 709), výška 8–9 mm (červené lišty) + černé patky 16 mm; mezery mezi nimi výřezy v hraně dna.
- Spodní hrana: zkosení v pěti stupních od z' 8 (y ±232) po z' 36 (y ±254); konce boxu mají svislé drážky (zpětná projekce ISO: y ±256, X −50…+32, z' 38…176).
- Horní otvor pro držadlo víka: osmiúhelník X −78…+81, Y ±116 (rektifikace ISO na rovinu z' 258), ±8 mm.
- Zkosení víka: z' 250 (y 271,5) → 267 (y 245) – c01 (obrys); horní plató z' 258.
- Kóty výrobce (c03): vnitřní 35,6 × 51,5 × 19,5 cm; vnější 26,7 × 55,4 × 38,7 cm. Vnitřní hloubka dutiny v modelu 194,8 mm (dno z' 16,7 → okraj 211,5; cíl 195). Vnitřní půdorys (356 × 515) model **nedodržuje přesně** – viz „vnitřek“ níže.

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse.sh`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, rovnoběžný pohled, oříznuto na obrys) | **0,987** | rozdíl obrysu ≤ 1,5 mm kromě horních rohů (≤ 5 mm) |
| `otevreny-c02` (víko 98°) | 0,966 | ruční body + obrys (volný fit kamery degeneruje, viz níže) |
| `otevreny-c03` (víko 94°) | 0,961 | červená maska |
| `zavreny-iso-L153707` | 0,958 | |
Dvojice foto | model | překryv byly prohlédnuty (ne jen IoU) pro čelo (madlo, západky, šrouby, logo, zámek, nožky, rohy) a ISO (konec, pant, horní držadlo). Kamera je odhad z ručně změřených bodů, ohnisko není změřené – IoU u šikmých pohledů proto ukazuje i chybu kamery, ne jen modelu.

## Neověřeno / zjednodušeno
- **Vnitřek zjednodušen, nedokončeno:** dutina je hladká vana (stěna 3,5 mm, rovné dno), **chybí** dělicí příčka (c02/c03 ji ukazují, černá, uprostřed), vnitřní žebrování víka, žebra a vybrání ve stěnách, čtvercová prohlubeň v podstropí víka. Vnitřní půdorys neodpovídá přesně kótě 35,6 × 51,5 cm (tloušťky stěn jsou jen odhad, nikoli měřené). Víko je dutý plášť (stěna 3 mm).
- **Spodek a zadní (pantová) strana:** ve fotografiích nejsou vidět. Tvar spodní plochy, zadní stěna a hloubka X všech výřezů jsou **neověřené odhady**; nožky mají jen tvar podle čelního pohledu (spodní stranu ani zadní řadu nožek nelze měřit). Zadní pant (články ve spodní/horní části) je přibližný (7 úseků po ~71 mm), kolík a okénka klínů podle ISO – neověřeno.
- Hloubka kapes: madla (28 mm), stohovacího zámku (18 mm), rámečků západek (6 mm), svislých drážek (4 mm) a rohových výřezů (20 mm) – odhad, z čelního/ISO pohledu nelze změřit.
- Horní držadlo (černý třmen v otvoru v horní ploše): tvar a poloha jen přibližné; kapsa je 36 mm hluboká (odhad).
- Západky (červené jazyky), drátové třmeny a madla jsou **pevné díly** (žádné pohyblivé uzly); jediný pohyblivý uzel je `vicko`. Jak se západky/drát pohybují, z fotografií nelze určit.
- Nápisy: „PROKIT“ vyražený vlevo nahoře na víku, šipka u zámku, malý znak na dně horního otvoru, jemná textura povrchu (zrnění) – nemodelováno; logo HILTI je jen ploška.
- Materiál: jediná červená (`cervena`) pro korpus i víko; stopa „horní rukojeť/drát“ černě. Odstín vůči fotografii není kalibrován.

## Zbylé viditelné rozdíly proti fotografii
- Čelo: lem víka nad západkami je v modelu jednoduchý pás (fotografie: profilované žebro s klínovými náběhy), drážky u rámečků jen naznačeny; madlo bez vyraženého loga HILTI (černé na černém); zámek v kapse zjednodušen na osmiúhelník + proužek.
- Horní pohled: žebrované klínové bloky na zadní hraně víka (okénka) jsou zjednodušeny na klíny s tmavým proužkem; drát pantu (černý) je jen válec.
- Rohy: zkosení spodního okraje a rohové výřezy ±3 mm; spodní levý roh v ISO pohledu ~4 mm výš než na fotografii.
- Nástroje: volný odhad kamery `render/srovnej.mjs` pro těsně oříznuté fotografie degeneruje (kamera se „nafoukne“, IoU 0,94 je zdánlivé); proto `nastroje/porovnej_celo.mjs` (téměř ortografický pohled oříznutý na obrys) a `nastroje/kalibruj.py` + `fit_lm.mjs` (kamera z ručních bodů, landmarky v `zdroje/landmarky/`). `unproject.mjs` = zpětná projekce pixelu na rovinu modelu (měření). `earcut2.mjs` je kopie `kufriky_cloud/earcut_cloud.mjs` (triangulace otvoru ve víku).
