# Řady euroboxů s válečkovými dráhami: odvození

Stav: 2026-10-12, agent pro bota10. GLB dílů 5275 až 5282 zatím NEJSOU v repu (`git fetch origin main`
je v `origin/main` nenašel), takže všechno kolem dílů je z rozměrů ze zadání a je označeno **neověřeno**.
Po dodání GLB se musí přeměřit body označené `[GLB]` níže a upravit konstanty v `DILY`
(`eurobox_rady.py`); kód pak díly zaměří stejnou cestou jako boxy.

## Shrnutí

- `eurobox_rady.py` (`postav`, `kopie_rady`, `min_vyska_patra`), `test_eurobox_rady.py` (17 testů, 980 kontrol,
  ~1 min, vč. objemu průniku s originálními GLB boxů), `nahled.html` (4 předvolby, Three.js r128 inline),
  `sestav_nahled.py` (generátor nahled.html), `odvod_konstant.py` (konstanty boxů z GLB), `rez_svg.py` → `obr_ukotveni.svg`.
- Boxy 400×300 jsou ověřené na GLB 3788 až 3796: pozice+kvaternion sedí na 0,02 mm (spodek nožky přesně v rovině
  dráhy, model je o 1 mm menší než jmenovitě, vystředěný). Z GLB: nožka dole 266 × 366 mm (nahoře ~274 × 375), výška 12 mm.
- Dráha leží svou horní plochou (rovina válečků) přesně pod spodkem nožky. Konec dráhy je zasunut 54,5 mm do kapsy
  plechu, plech má na opačném konci hák na trubku Ø28 (86,29 − 54,5 = 31,79 mm, tedy přesně hák pro Ø28 se stěnou ~1,9 mm).
- Osa trubky je 15,9 mm od vnějšího konce plechu a 15,9 mm pod jeho horní plochou. Dolní konec dráhy visí vždy na
  nižším nosníku (nosník `dolni`), horní na vyšším (`horni`). Rozdíl výšek = vzdálenost trubek × sin(sklon).
- Řady jednoho patra sdílejí JEDEN dolní nosník; horní nosníky jsou po jednom na každou různě dlouhou řadu.
- Výchozí rozteč dráhy zdůvodněna dole; výchozí dráha `5276`, výchozí zasunutí `54.5`.

## Výklad pojmů bota10: potvrzeno / opraveno

| Pojem | Verdikt |
|---|---|
| Řada = n boxů za sebou, mezera 1 mm, délka = n·a + (n−1)·1 | potvrzeno (test: 400×5+4 = 2004) |
| Sklon kolem vodorovné osy kolmé na osu řady, nižší konec vpředu | potvrzeno, `nizsi_konec` = predek/zadek (pro osu z: menší/větší z) |
| Patro = řady vedle sebe v téže výšce, společný dolní nosník | potvrzeno; stejnou výšku a sklon řad kontroluje `PATRO_NESEDI` |
| „Mezera“ u kopie nad sebou = výšková mezera horní okraj boxů spodního patra / nejnižší díl horního | potvrzeno, přes celý půdorys, vzorkování 2 mm (chyba ≤ krok·tan sklonu) |
| „Mezera“ u kopie vedle = čistá vzdálenost konstrukce (box, dráha, koncovka) | potvrzeno; nosník se nepočítá (je společný) |
| Referenční výška patra = dno boxu na nižším konci | potvrzeno (`y` = spodek nožky prvního boxu na nižším konci) |
| Dolní konec dráhy vždy na nižším nosníku | potvrzeno |

Rozpory s fyzikou / podklady (nutno potvrdit):

1. **Vzorec „vzdálenost trubek = délka dráhy − 2 × zasunutí“ z poslední zprávy neodpovídá rozměrům plechu.** Plech je 86,29 mm,
   kapsa 54,5 mm a hák 31,79 mm. Hák je na VNĚJŠÍM konci a trubka leží ZA koncem dráhy:
   vzdálenost trubek = délka dráhy + 2·(86,29 − 54,5 − 15,9) = délka dráhy + 31,8 mm (např. 8 modulů 5275: 2173,3 + 31,8 = 2205,1).
   Počet modulů se ale počítá přesně podle Roberta: viditelná část dráhy (délka dráhy − 2×zasunutí) musí pokrýt délku řady,
   tedy m = ⌈(L + 2·zasunutí) / délka modulu⌉.
2. Trubka Ø28 se do háku o vnější výšce plechu 27,75 mm celá nevejde (hák nemůže být uzavřené Ω): trubka přečnívá spodek obálky
   plechu o ~2 mm. Je to buď otevřený hák, nebo se plech 27,75 vztahuje jen k části profilu. `[GLB]`
3. Zarážka 28 mm je vyšší než nožka (12 mm), takže se box nezastaví o nožku, ale o spodní okraj stěny (zarážka působí ve výšce
   12 až 28 mm nad rovinou dráhy, ~16 mm kontaktu). To vyplývá z GLB boxu a z rozměru 5282.

## Co je z geometrie a co odhad

Z GLB boxů (měřeno): rozměr 299 × 399 × výška; střed obálky v lokálních souřadnicích (konstanty v `BOXY`); nožka dole 266 × 366,
výška 12,0 mm, k tělu se rozšiřuje na 274,2 × 375,0; tělo je dutá nádoba (v testech se uvnitř nic nepočítá jako pevné).
Lokální osy GLB: X kratší strana, Y delší, Z výška, nožka u min Z.

Ze zadání (rozměry): 5275 271,66 × 37,24 × 38,86; 5276 41,0 × 61,67 × 255,04; 5281 38,47 × 27,75 × 86,29;
5282 38,47 × 55,75 × 86,29 (z toho zarážka 28 mm); zasunutí 54,5 mm.

ODHAD (neověřeno, `[GLB]`):

- Plech: profil se tvoří v rovině (délka 86,29 × výška 27,75), šířka 38,47. Kapsa (54,5) na straně dráhy, hák (31,79) na vnějším konci.
  Horní plocha plechu je v rovině válečků (rovina h=0). Zarážka 28 mm: rozměr 55,75 = 27,75 + 28, tedy základna pod rovinou a zarážka nad ní.
- Zarážka je u otvoru kapsy (čelo boxu se opírá o zarážku v otvoru kapsy); alternativa `zarazka_u="hak"`.
- Tloušťka zarážky 1,5 mm (odhad), ve výpočtu jen pro polohu.
- Dráha 5275: tělo pod rovinou válečků na výšku 38,86 mm. Dráha 5276: rovina válečků je 28 mm pod horním okrajem (33,67 pod, 28 nad),
  boční doraz tloušťky 3 mm na VNĚJŠÍ straně dráhy (odhad; orientace lokálních os 5276 je jiná než u 5275, Z je podélně).
- Orientace lokálních os plechů: Z podél (háček na −Z), Y nahoru, X napříč. U 5276: doraz na +X lokálně; levá/pravá dráha se liší otočením o 180° kolem normály.
- Moduly dráhy na sraz, bez spojky (nic v podkladech neříká jinak).
- 600×400: bez modelu → kvádr bez nožky (není známo, zda nožku má); karty dodavatele 2999 až 3003 v pořadí výšek 120/170/220/320/420 (domněnka).

### Hypotéza uchycení (obrázek `obr_ukotveni.svg`)

Boční řez rámem sklonu (s podél dráhy, h kolmo): dráha leží svou horní plochou v h = 0 pod boxem; plech 5282/5281 navazuje v téže rovině,
dráha je zasunuta 54,5 mm do jeho kapsy; osa trubky je v (s, h) = (15,9 od vnějšího konce plechu, −15,9). Protože celý díl se sklopí spolu s dráhou,
osa trubky se pro sklon θ mění takto (v rámu řady pod dolním koncem, s_t = −86,29 + 15,9 = −70,4):
`x_t = x0 + s_t·cosθ + 15,9·sinθ`, `y_t = y0 + s_t·sinθ − 15,9·cosθ` (u nižšího konce směrem „předek“). Výšky trubek se tedy liší o D·sinθ,
D = vzdálenost trubek podél sklonu, a trubka leží tím níž pod spodkem boxu, čím je sklon větší.

## Výchozí rozteč dvou drah (parametr `roztec_drah_mm`)

Dráhy musí ležet pod nožkou boxu (spodek nožky 266 mm napříč při směru „delka“, 366 mm při „sirka“), jinak by se box opíral o dno ve výšce 12 mm.

- 5275: vnější hrana dráhy 10 mm uvnitř hrany nožky: rozteč = nožka − šířka dráhy − 2·10, tedy 208,8 mm (delka) / 308,8 mm (sirka).
- 5276: boční doraz stojí za bokem boxu s vůlí 1 mm: rozteč = šířka boxu + 2·(1 + 3) − 41, tedy 267 mm (delka) / 367 mm (sirka).
  (Doraz vyčnívá 28 mm nad rovinu válečků, tedy nad nožku 12 mm; musí stát vně boku boxu.)
- Rozteč 5275 vychází zvolenou stabilitou (široce); Robert může zadat vlastní.

## Výstup `postav(spec)` (stručně)

`boxy` (id, řada, patro, typ, vyska, part_id nebo null + `kvadr`, position, quaternion, scale, stred, rozmer_obalky, obalka AABB),
`draha` (po řadách: pasy 1 a 2, moduly s part_id, position, quaternion, `tvary_nahrady`, délka celku, viditelná délka, vzdálenost trubek),
`koncovky` (role `dolni`=5282, `horni`=5281; `spoj` není, moduly jsou na sraz), `nosniky` (`a`, `b`, role, patro, polomer 14, řady),
`opory` (vodorovné řady: obdélník desky a výška y), `rady`, `mezery_pater`, `rozmery`, `problemy`, `parametry`.
Pozice dílu = požadovaný střed − R·střed GLB (u dílů zatím střed GLB (0,0,0) = neověřeno).
`x, y, z` řady = dolní roh obálky prvního boxu na nižším konci řady (spodek nožky).
Kopie: `kopie_rady(spec, id, "vedle"|"nad", mezera, pocet, sklon_deg=None, patro=None)`; mezera „nad“ závisí na dráze a sklonu zadaných ve spec.

## OTEVŘENÉ OTÁZKY PRO ROBERTA (každá s výchozí hodnotou)

1. Jak se spojují moduly dráhy v řadě (5275 271,66 / 5276 255,04)? Plechem 5281, nebo uchem na ucho? Výchozí: na sraz, bez dílu. Bez spojky se např. 2 m řady nesou jen 2 trubkami; je potřeba střední podpora (parametr `max_rozpeti_mm`, výchozí vypnuto)?
2. Je zarážka 28 mm na plechu 5282 u otvoru kapsy (výchozí), nebo na konci s hákem?
3. Je hák plechu otevřený (trubka Ø28 vs. výška 27,75 mm)? Výchozí: osa trubky 15,9 mm od vnějšího konce plechu, 15,9 mm pod jeho horní plochou.
4. Dráha 5276: na které straně je boční doraz a jak vysoko je rovina válečků? Výchozí: doraz vně, 3 mm silný, rovina válečků 28 mm pod horním okrajem.
5. Která dráha je výchozí? Výchozí: 5276 (pořadí ve zprávě), jiná jen parametrem `draha`.
6. Zasunutí 54,5 mm odpovídá hloubce kapsy? Výchozí: ano (zasunutí = kapsa = 54,5; menší zasunutí lze zadat).
7. Doporučený rozsah sklonu? Výchozí varování mimo 2 až 15° (chyba nad 45° a pod 0°).
8. Euroboxy 600×400: potvrdit výšky 120/170/220/320/420 a zda mají nožku (výchozí: kvádr bez nožky, karty 2999 až 3003).
9. Minimální výšková mezera mezi patry? Výchozí varování pod 10 mm (kopie „nad“ dodrží jakoukoli zadanou).
10. Tloušťka desky pod vodorovnou řadou (jen pro výškovou mezeru pater)? Výchozí 0 (řeší rám bota10).
11. Nosník Ø28 u kraje patra: jak daleko přesahuje krajní koncovku? Výchozí 0 (nohy a spojky doplní rám).

## Poznámka k nahled.html (kontrola zakázaných slov)
V nahled.html nejsou slova admin, logiman, localStorage, /api/, window.open, postMessage, eval ani cizí servery. Jediné výskyty „http://“ jsou čtyři jmenné prostory XML/SVG/XHTML (`http://www.w3.org/...`) uvnitř knihovny Three.js; nejde o žádný síťový požadavek. Pokud synchronizační filtr hledá obecně řetězec „http“, je nutné ho upravit, nebo mi dát vědět a nahradím je.
