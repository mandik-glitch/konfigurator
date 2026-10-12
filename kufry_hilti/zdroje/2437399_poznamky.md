# Hilti ProKit PKC 18-H (2437399) – poznámky k modelu

Model: `kufr_2437399.mjs` (+ `p2437399_zaklad.mjs`, `p2437399_korpus.mjs`, `p2437399_vicko.mjs`), sestavení `node kufry_hilti/vytvor.mjs 2437399` → `modely/2437399.glb` (40 dílů, ~3 100 trojúhelníků, obálka 389 × 275 × 295 mm, odchylka 0/0/0 mm). Souřadnice: X = hloubka 389 (čelo s logem do +X), Y = šířka čela 275, Z = výška 295, počátek ve středu obálky. Víko = skupina `vicko`, pivot na pantové hraně (x = −188, z' = 241,8), `extras.osa = [0,−1,0]`, `--pose vicko=88` otevře (fotografie c02/c03 ukazují víko ~86–89°).
Zadání (Robert): hlavní je ZAVŘENÁ verze a vnější pohled; **vnitřek zjednodušen (prázdná hladká dutina), nedokončeno**. Postup i generátor jsou převzaté z PKC 35 (`2437394_poznamky.md`); `p2437399_zaklad.mjs` je kopie `p2437394_zaklad.mjs` + `vanaD` (dutina nezávislá na vnějším tvaru, protože vnější tvar má hluboké kapsy).

## Fotografie (jen čteny ze scratchpadu, v repu nejsou; URL viz `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (L158755, 741×800) | přímý čelní pohled, těsně oříznutý (lem víka od okraje po okraj, osa souměrnosti px 370,5), mírná perspektiva | měření čela (px → mm: 275/741 vodorovně, 295/800 svisle), porovnání `celo` |
| c02 (L160230, 543×800) | šikmo shora zpředu-zprava, víko otevřené ~89°, vedle vložka (vanička; není součástí modelu) | kamera z obrysu, porovnání `otevreny-c02` (maska podle červené barvy, černá vložka a vnitřní příčky se nepočítají) |
| c03 (L160231, 593×800) | totéž s kótami výrobce | kontrola rozměrů, porovnání `otevreny-c03` (červená maska kvůli šipkám/popiskům) |
| c04 (L160060) | aplikační snímek (otevřený box na stavbě, vložka v ruce, osoba) | jen vizuální kontrola (žlábky na boku, žebrování víka), nepoužito k měření |
| c05 (L160116) | aplikační snímek (stoh na vozíku) | nepoužito (poměry víka shora nelze změřit) |

## Co je jinak než u PKC 35 (zjištěno z fotografií)
- **Čelo je krátká strana (275 mm), hloubka 389 mm.** Poměr c01 275:295 sedí na čelo, ne na bok. Víko je na zadní krátké straně (pant), otevírá se nahoru dozadu.
- **Madlo:** pevný černý úchyt (šestiúhelník) uprostřed čela, přes dělicí spáru víko/korpus; pod ním kapsa se šikmými boky. U PKC 35 je lišta s jazykem a po stranách rámečky západek.
- **Západky na čele nejsou.** Místo nich jen dva šrouby čepů (Y ±72,5) s drážkami nad nimi; vpravo na zkosení rohu víka malá spona (viz neověřeno).
- **Stohovací zámek je uprostřed** dole v kapse (u PKC 35 vlevo dole). Dvě patky (kolejnice) místo čtyř.
- **Víko nemá horní otvor/držadlo** (PKC 35 ano); horní hrana je zkosená (zkosení ~17 × 29 mm).

## Změřené rozměry (z čelní fotografie c01, ±1,5 mm; siluety po řádcích)
- Lem víka z' 240–249, Y ±137,5 (c01 px 1..739); skořepina víka a horní část korpusu (límec) Y ±131,5 (z' 222–277); zkosení horní hrany víka z' 277 (±131) → 295 (±102); límec korpusu se pod víkem zužuje zkosením z' 222 → 210 (±131 → ±118,4).
- Spodní díl: Y ±118,4 (z' 210) → ±115,6 (z' 37), zkosení spodní hrany z' 37 → 18,4 (±115,6 → ±96,9), patky Y 47…91 při zemi, výška 18, dno mezi patkami z' 12.
- Čelní rovná část Y ±92 (pás s logem) / ±100 (víko), zkosení rohů čelo→bok 26–31 mm v Y (v X odhad 45°).
- Pás s logem z' 109–168; logo HILTI z' 134,5–151, Y ±60 (rozklad na obdélníky z px c01).
- Kapsa madla Y ±63, podlaha z' 181 (šikmý nájezd z pásu z' 168), madlo z' 223–255 (nahoře ±53, dole ±48); šrouby Y ±72,5, z' 254,5; drážky nad nimi |Y| 66–76, z' 264–277.
- Kapsa zámku Y ±63, z' 24–106; zámek ±29,5, z' 26–82 (žebrovaná horní část z' 60–82).
- Kóty výrobce (c03): vnější 27,5 × 29,5 × 38,4 cm (hloubka tělesa 38,4; katalog 389 mm zahrnuje lem víka a pant – model drží katalog), vnitřní 24 × 31,8 × 23 cm. Katalog: vnitřní 283 × 229 × 227.

## Výsledky porovnání (IoU obrysu; `nastroje/srovnej_vse_2437399.mjs`)
| pohled | IoU | poznámka |
|---|---:|---|
| `celo` (c01, téměř ortografický pohled oříznutý na obrys) | **0,990** | rozdíl obrysu ≤ 1,5 mm kromě rohů lemu |
| `otevreny-c02` (víko 89°) | 0,946 | kamera odhadnutá z obrysu: az 41°, el 48°, fov ~17° |
| `otevreny-c03` (víko 86°) | 0,935 | az 42°, el 48°, fov ~20° |
Soubory: `kufriky_cloud/srovnani/2437399/<pohled>.png|json` (jen vlastní rendery + kamera, IoU a URL fotografie). Dvojice foto | model | překryv jsou jen ve scratchpadu a byly prohlédnuty (čelo: madlo, šrouby, logo, zámek, patky, rohy; otevřený: obrys korpusu a víka, poloha pantu).
Kamery c02 a c03 vyšly nezávisle téměř stejné (az 41–42°, el 48°), což je dobrá kontrola; ohnisko a úhel víka jsou ale **odhad z obrysu, ne měření**, a IoU u šikmých pohledů proto ukazuje i chybu kamery. Pozor: volný odhad `render/fit.mjs` (s rollem) skončil ve špatném minimu (el ~55°, roll −5°, IoU 0,936 s viditelně špatným náhledem); proto `nastroje/fit_2437399.mjs` s roll = 0 a startem podle sklonu loga (sklon řádku loga v c03 ≈ 38° ⇒ sin(el)·tan(az) ≈ 0,78). `unproject_2437399.mjs` = zpětná projekce pixelu na rovinu modelu.

## Neověřeno / odhad
- **Vnitřek zjednodušen, nedokončeno:** dutina je hladká vana (283 × 229 u dna podle katalogu → 291 × 240 u okraje podle c03 – kóta 31,8 cm u okraje se do modelu nevešla, protože čelní stěna s kapsami je silná; hloubka dutiny 224,5 mm), dno z' 16. **Chybí:** dvě černé dělicí příčky (kříž, c02), žebra ve stěnách, těsnění (černý profil na víku), vnitřní žebrování víka (víko je dutý plášť 3 mm), rohové „oušky“ na okraji dutiny, vložka. Čelní a zadní stěna jsou v modelu plné (objem ≠ skutečná hmotnost 2,78 kg; neladěno).
- **Hloubky v X** nejsou z čelní fotografie měřitelné: čelní/zadní rovina (±187/±188 odvozeno z katalogových 389 a poměrů PKC 35), hloubka kapsy madla (28 mm), kapsy zámku (18 mm), šikmých boků kapsy (podle stínů v c01), zkosení rohů v X, horní zkosení víka v X (~29 mm), poloměr zadních rohů (8 mm).
- **Spodek a zadní (pantová) strana:** na fotografiích nejsou vidět (jen zevnitř c02/c03). Délka a tvar patek v X, spodní plocha, zadní stěna, pant (5 úseků po 46 mm, kolík r 2,4) jsou odhad; poloha osy pantu odpovídá ve srovnání c02/c03, jinak nepodložená.
- **Spona vpravo na víku** (c01 px 645–715): je jen na jedné straně (vlevo ji c01 nemá); tvar a funkce neznámé – modelován jen hranol s okénkem. Svislé žlábky na bocích (c03: čára u px 392 ⇒ X ≈ +27 ±5 mm): jeden pár, hloubka 1,5 mm odhad.
- Madlo, šrouby a zámek jsou **pevné díly**; jediný pohyblivý uzel je `vicko`. Jak se víko zajišťuje, z fotografií nelze určit.
- Nápisy „PROKIT“, popisný obdélník na horní hraně víka, černé logo HILTI na madle, textura povrchu (zrnění) – nemodelováno; logo HILTI na pásu je jen ploška. Materiál: jedna červená + černé díly, odstín vůči fotografii není kalibrován.

## Zbylé viditelné rozdíly proti fotografii
- Čelo: profilovaná hrana lemu víka nad madlem a vertikální drážky u spodních pilířů (c01 px ~140–160) jsou zjednodušeny; zámek je černý hranol se žebry místo složitější vložky; patky bez gumových detailů.
- Otevřený pohled (c03): model je o ~2–5 mm širší v levém horním rohu víka a užší na pravém okraji zadní stěny; horní hrana levé dlouhé stěny je v modelu o pár mm níž.
- Nástroje: `srovnej_vse_2437399.mjs` (rebuild + IoU + rendery do `srovnani/2437399/`), `fit_2437399.mjs`, `unproject_2437399.mjs`; sdílené beze změny: `porovnej_celo.mjs`, `iou_kamera.mjs`, `maska_cervena.py`, `../kufriky_cloud/nastroje/zabal_prohlizec.mjs` (náhled `nahled/2437399.html`, název stránky změněn na „Hilti ProKit PKC 18-H 3D“).
