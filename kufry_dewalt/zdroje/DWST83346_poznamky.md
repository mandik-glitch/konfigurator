# DeWalt TSTAK IP54 hluboký (DWST83346-1) – poznámky k modelu

Model: `kufr_DWST83346.mjs` + sdílená parametrická skořepina `tstak_kufr.mjs` / `tstak_zaklad.mjs` / `tstak_korpus.mjs` / `tstak_vicko.mjs` (stejný kód staví i mělký DWST83345, liší se jen parametr výšky H = 302 / 162 mm a čelní madlo v kapse). Sestavení `node kufry_dewalt/vytvor_tstak.mjs` → `modely/DWST83346.glb` (~53 dílů, ~2 400 trojúhelníků, obálka 333 × 440 × 302 mm, odchylka 0/0/−0,1 mm).
Souřadnice: X = hloubka (čelo se západkami do +X), Y = délka (±220), Z = výška, počátek ve středu obálky. Skupiny: `korpus` (spodní díl), `vicko` (víko; v něm vnořená skupina `drzadlo`, sklopné horní držadlo). Zadání: zavřená verze, vnější pohled; víko i vnitřek zjednodušeny (otevřený pohled na fotografiích chybí).
Rozměry 440 × 333 × 302 jsou z datasheetu DeWalt (ne z dewalt.cz, viz `README.md`); vnitřní rozměry ani hmotnost výrobce neuvádí.

## Víko a pant
Víko je samostatná skupina `vicko` (pivot [−160, 0, spára], `extras.osa = [0,−1,0]`, `--pose vicko=70` ho otevře). **Pant na fotografiích není vidět** (zadní strana se nefotí, všechny záběry jsou zepředu/zprava) – že je vzadu, plyne jen z toho, že západky jsou vpředu. Poloha osy (zadní hrana spáry, x = −160) je **odhad**; žádná geometrie pantu (kolena, kolík) se nemodeluje, víko při otevření jen odjede kolem té osy. Držadlo na víku je skupina `drzadlo` (pivot vpředu v kapse, osa +Y, kladný úhel zvedá; zavřené = sklopené v kapse, `--pose drzadlo=60` odpovídá c01).

## Fotografie (jen čteny ze scratchpadu `kufry2/DWST83346-1/`, v repu nejsou; URL viz `../fotky_url.tsv`)
| soubor | pohled | použití |
|---|---|---|
| c01 (2560², studio) | šikmo zepředu zprava, **držadlo zvednuté** | tvar konce (boční kapsa, drážky), římsa lemu, držadlo; srovnání `sikmo-c01` (kamera z landmarků + obrysu, úhel držadla fitován) |
| c02 (2560², studio) | téměř přímo zepředu, mírně shora, držadlo sklopené | **hlavní měřicí fotografie** (čelo: sloupky, západky, kapsa, štítky, obrys víka/korpusu), srovnání `celo-c02` |
| c03 (2560², studio) | totéž + vyjmutá vnitřní vložka pod kufrem | vložka se v maskách ořízne (řádky ≥ 1735); srovnání `celo-c03`; vložka ukazuje vnitřek (miska s držadlem) – **nemodelováno** |
| c04 – c07 (aplikační, ze stavby) | kufry ve stohu, malé, perspektivní | jen orientačně: boční kapsa pro stohovací hák a žlutý hák (c06, c07), poloha držadla; k měření nepoužito |

## Změřeno (c02, měřítko = 440 mm = šířka víka 2 423 px, ≈ 5,5 px/mm; přesnost ±1,5 mm, perspektiva c02 ≈ 3,2 m způsobuje ±1–2 % rozdíl měřítka mezi předním a zadním)
- Korpus: šířka 424,9 mm (±212,5); víko 440 (±220). Spára lem/korpus ve výšce ≈ 230 mm (výška víka ≈ 72 mm), ověřeno překryvem v rámu fotografie (u mělkého kufru sedí stejně).
- Čelo korpusu: vnější sloupky |y| > 171, zapuštěné zóny západek |y| 109–171, vystupující střední panel |y| < 108, kapsa vpředu dole |y| < 93, výška 0–85 mm, uprostřed horního okraje kapsy lichoběžníkový jazyk (±48 → ±38, hloubka 10).
- Západky (pozinkovaný plech) |y| 113–167, výška z' 181–250 (přes spáru), tři vylisovaná žebra.
- Štítek IP54 vlevo na čele sloupku: y −162…−118, z' 253–284; štítek TSTAK (oranžový, čirý kryt) y ±47, z' 266–281; žlutý proužek na římse y −90…−36.
- Stohovací háky (žluté) na horní ploše u obou konců, x ≈ −44…+90, |y| ≈ 180…200.
- Kapsa pro sklopné držadlo: |y| < 89, x −52…+62, držadlo 174 mm široké.
- Boční kapsa pro stohovací hák (c01, pravý konec): x ≈ −54…+92, z' 0…68, otevřená dole.

## Odhad (hodnota není z fotografie přímo měřitelná)
- Hloubky: čelní panely vystupují 161/157/155 mm (střed/sloupky/zóny), dno kapsy 140; římsa lemu před lícem víka ≈ 14 mm (c01); tloušťky stěn 4 mm (korpus), 3,5 mm (víko); hloubka kapsy držadla 16 mm; sklon konců víka (220 → 199 mm do výšky 302); zkosení rohů víka 24–25 mm; spodní hrana zkosená o 7 mm.
- Zadní část (hloubka X −166,5…): rovná stěna, **zcela neověřeno**; viz „Neověřeno“.
- Žlutý odstín: `zluta` z `jadro/glb.js` má sRGB ≈ (250, 207, 0), foto ≈ (248, 190, 45) – jádro se nemění, rozdíl je viditelný jen mírně.

## Výsledky porovnání (IoU obrysu v rámu fotografie, `nastroje/srovnej_vse_tstak.sh`)
@@IOU@@

## Neověřeno / zjednodušeno
- **Zadní strana, pant, spodek, vnitřek:** na žádné fotografii nejsou vidět. Zadní stěna a zadní zkosení víka jsou odhad; spodní plocha je rovná se zkosením (c03 mělkého kufru naznačuje nožky/žebra – nemodelováno); vnitřek je hladká vana (stěna 4 mm), víko dutý plášť (3,5 mm), bez žeber, příček a vložky.
- **Skutečná hloubka 333 mm:** model ji dodržuje (obálka ±1 mm podle zadání), ale v c01 vychází obrys lépe, když je zadní strana o ~10–15 mm kratší (IoU c01 0,958 → 0,969 při zkrácení o 16 mm). Nevíme, zda 333 mm zahrnuje vyčnívající západky/pant, nebo je rozdíl chyba kamery/ostatních tvarů; zachována hodnota z datasheetu.
- Stohovací zámek/hák na konci je jen zjednodušený klín na horní ploše; háček přes konec víka, boční kapsa (jen rámeček + tmavá vložka, nevyříznuto) a drážky na konci jsou naznačeny.
- Západky, držadlo a víko jsou pevné díly kromě `vicko` a `drzadlo`; kinematika západek (otočný čep, háky na korpusu) z fotografií nejde určit a není modelována.
- Čelní plocha: vroubkování povrchu (zrnění), vylisované nápisy, DEWALT logo jen jako žlutá ploška, text na štítcích nemodelován; štítek IP54 je jen žlutý rám s černým polem.
- Materiály: `cerna` (korpus, víko), `cerna_mat` (kapsy, hmatnice, pole štítků), `zluta` (štítky, háky, logo), `pozink` (západky), `cira` (kryt štítku). `seda_svetla` se nepoužívá (na fotografiích není šedý plast; šedé jsou jen odlesky).

## Zbylé viditelné rozdíly proti fotografii
- Horní plocha víka: v kapse chybí příčky a žebra, hrany lemu kolem kapsy jsou zjednodušené, stohovací důlky jsou jen tmavé terčíky.
- Čelo víka: sloupky a ostrůvek jsou hranaté bloky bez fazet a drážek z fotografie; římsa lemu jen jako pás.
- Hrany: zkosení rohů (sklon 45°) místo zaoblení; západky bez ohybu a bez kloubu k lemu.
