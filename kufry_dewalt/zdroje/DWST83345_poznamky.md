# DeWalt TSTAK II IP54 mělký (DWST83345-1) – poznámky k modelu

Model: `kufr_DWST83345.mjs` + **táž** sdílená parametrická skořepina jako hluboký DWST83346 (`tstak_kufr.mjs`, `tstak_zaklad.mjs`, `tstak_korpus.mjs`, `tstak_vicko.mjs`; parametr výšky H = 162 mm, `celoMadlo: true` přidá madlo v čelní kapse). Sestavení `node kufry_dewalt/vytvor_tstak.mjs` → `modely/DWST83345.glb` (~56 dílů, ~2 600 trojúhelníků, obálka 333 × 440 × 162 mm, odchylka 0/0/−0,1 mm).
Souřadnice: X = hloubka (čelo se západkami do +X), Y = délka (±220), Z = výška, počátek ve středu obálky. Skupiny: `korpus`, `vicko` (v něm `drzadlo`). Zavřená verze, vnější pohled; víko i vnitřek zjednodušeny.
Rozměry 440 × 333 × 162 jsou z datasheetu DeWalt (ne z dewalt.cz); vnitřní rozměry a hmotnost výrobce neuvádí. Půdorys i víko jsou shodné s DWST83346 – liší se **jen výška korpusu** (90 mm místo 230 mm; víko 72 mm je v obou stejné) a čelní madlo v kapse.

## Víko a pant
Stejně jako u hlubokého: samostatná skupina `vicko` (pivot [−160, 0, spára], osa −Y, `--pose vicko=70`). **Pant na fotografiích není vidět**; poloha osy je odhad (viz `DWST83346_poznamky.md`). Držadlo `drzadlo` (pivot vpředu v kapse); na c01/c02 je zvednuté (fitovaný úhel viz tabulka níže).

## Fotografie (jen čteny ze scratchpadu `kufry2/DWST83345-1/`, v repu nejsou; URL viz `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (2560², studio) | šikmo zepředu zprava, držadlo zvednuté | srovnání `sikmo-c01` (kamera z landmarků + obrysu, úhel držadla fitován); čelní madlo v kapse, konec |
| c02 (2560², studio) | téměř přímo zepředu, držadlo zvednuté | **hlavní měřicí fotografie** (čelo, kapsa s madlem, štítky, obrys), srovnání `celo-c02` |
| c03 (2560², studio, „na bok“) | kufr postavený na bok/překlopený (logo DEWALT vzhůru nohama, žluté boční západky, vpravo konec s kapsou) | **jednoznačně neinterpretováno** – pohled jsem nedokázal spolehlivě přiřadit ke stranám kufru; nepoužito k měření ani srovnání |
| c04, c05 (aplikační) | kufry ve stohu na vozíku | jen orientačně: čelní madlo v kapse mělkého kufru je vidět i zde (potvrzuje, že je to vlastnost mělkého kufru, ne vložka) |

## Změřeno (c02; měřítko = 440 mm = šířka víka 2 427 px, ≈ 5,5 px/mm; přesnost ±1,5 mm)
- Spára víko/korpus a štítky/západky sedí na stejné výšky vůči spáře jako u hlubokého kufru (ověřeno překryvem v rámu fotografie, kamera z landmarků) → výška víka ≈ 72 mm, výška korpusu ≈ 90 mm.
- Kapsa vpředu |y| < 93 (z c02 přes celou výšku korpusu, horní okraj ≈ 5 mm pod spárou), v ní madlo: dva svislé držáky |y| 70–93 a hmatnice |y| < 72 při dně (z' 7–30).
- Západky |y| 113–167, z' 41–110; štítek IP54 y −162…−118; štítek TSTAK y ±47; žlutý proužek na římse; rozměry víka a zkosení shodné s hlubokým.

## Odhad (hodnota není z fotografie přímo měřitelná)
- Hloubky čelních panelů, římsy, kapsy, boční kapsy, tloušťky stěn – stejně jako u DWST83346.
- Tvar madla v kapse (držáky + válcová hmatnice) a jeho hloubka v kapse (x 140,5…156) jsou zjednodušené; skutečné madlo má výřez, hmatník s vroubky a jazyk – z jedné čelní a jedné šikmé fotografie nelze určit. Madlo je modelováno jako pevný díl.
- Výška korpusu: model ji bere jako H − 72 = 90 mm. Hrubé přímé měření z c02 (bez perspektivy) dávalo ≈ 83 mm; po zahrnutí kamery z překryvu v rámu fotografie sedí 90 mm lépe, ale odchylka ±3 mm zůstává.

## Výsledky porovnání (IoU obrysu v rámu fotografie, `nastroje/srovnej_vse_tstak.sh`)
@@IOU@@

## Neověřeno / zjednodušeno
- **Zadní strana, pant, spodek, vnitřek:** na fotografiích nejsou (c03 možná ukazuje spodek/zadek, ale nepodařilo se ho spolehlivě přiřadit). Zadní stěna rovná, spodek rovný se zkosením, vnitřek hladká vana, víko dutý plášť.
- **Hloubka 333 mm** (z datasheetu) dodržena; stejná poznámka jako u hlubokého – obrys v šikmém c01 by vycházel lépe s mírně kratší zadní stranou.
- Stohovací hák na konci a boční kapsa (jen rámeček + tmavá vložka) jsou naznačeny; kinematika západek a držadel není modelována (pevné díly kromě `vicko`, `drzadlo`).
- Povrchová struktura, nápisy a logo (jen žlutá ploška), text na štítcích.
- Materiály: `cerna`, `cerna_mat`, `zluta`, `pozink` (západky), `cira` (kryt štítku); `seda_svetla` se nepoužívá.

## Zbylé viditelné rozdíly proti fotografii
- Čelní madlo v kapse je zjednodušené (bez jazyka, vroubků a zkosení); horní plocha víka bez žeber; sloupky/ostrůvek hranaté; zkosení rohů 45° místo zaoblení; západky bez ohybu.
