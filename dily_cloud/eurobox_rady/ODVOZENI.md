# Řady euroboxů s válečkovými dráhami: odvození

Stav: 2026-10-12, agent pro bota10. Dráha **5276** je od Roberta jako STEP (dily/5276_2.2.016.027.037.03.step) a je
převedená na skutečný mesh `dily/5276.glb`; její rozměry a tvar jsou z geometrie. Díly **5275, 5281, 5282** (GLB ani STEP) zatím NEJSOU,
takže jejich tvar a uchycení jsou z rozměrů ze zadání a jsou označené **neověřeno** (body `[GLB]`). Po dodání se konstanty v `DILY`
(`eurobox_rady.py`) přeměří stejným postupem jako 5276 (`dily/step_na_glb.py`).

## Shrnutí

- `eurobox_rady.py` (`postav`, `kopie_rady`, `min_vyska_patra`), `test_eurobox_rady.py` (22 testů, ~9000 kontrol,
  ~3 min, vč. objemu průniku s originálními GLB boxů a s meshem dráhy 5276), `nahled.html` (6 předvoleb, Three.js r128 inline),
  `sestav_nahled.py` (generátor nahled.html), `odvod_konstant.py` (konstanty boxů z GLB), `rez_svg.py` → `obr_ukotveni.svg`, `dily/step_na_glb.py` (STEP → GLB přes OCP) a `dily/5276.glb`.
- Boxy 400×300 jsou ověřené na GLB 3788 až 3796: pozice+kvaternion sedí na 0,02 mm (spodek nožky přesně v rovině
  dráhy, model je o 1 mm menší než jmenovitě, vystředěný). Z GLB: nožka dole 266 × 366 mm (nahoře ~274 × 375), výška 12 mm.
- Dráha leží svou horní plochou (rovina válečků) přesně pod spodkem nožky. Konec dráhy je zasunut 54,5 mm do kapsy
  plechu, plech má na opačném konci hák na trubku Ø28 (86,29 − 54,5 = 31,79 mm, tedy přesně hák pro Ø28 se stěnou ~1,9 mm).
- Osa trubky je 15,9 mm od vnějšího konce plechu a 15,9 mm pod jeho horní plochou. Dolní konec dráhy visí vždy na
  nižším nosníku (nosník `dolni`), horní na vyšším (`horni`). Rozdíl výšek = vzdálenost trubek × sin(sklon).
- Řady jednoho patra sdílejí JEDEN dolní nosník; horní nosníky jsou po jednom na každou různě dlouhou řadu.
- Výchozí rozteč dráhy zdůvodněna dole; výchozí dráha `5276`, výchozí zasunutí `54.5`.

## Pravidla od Roberta doplněná později

- **Boxy se naklánějí spolu s dráhami** („aby jely po té dvojici válečkových drah“): všechny boxy řady mají stejný sklon jako obě dráhy,
  spodek nožky leží v rovině válečků obou drah. Test `test_boxy_nakloneny_spolu_s_drahami` to měří jen z výstupu a z GLB: úhel osy boxu = úhel dráhy
  (4 desetinná místa), normála boxu = normála roviny drah, vzdálenost spodku nožky od roviny válečků ≤ 0,1 mm (naměřeno max. 0,0007 mm),
  obě dráhy a všechny moduly leží v jedné rovině a řady jednoho patra tvoří jednu šikmou rovinu. Platí pro obě dráhy, obě orientace boxu, obě osy a oba nižší konce.
- **Strop délky řady 20 m**: parametr `max_delka_rady_mm` (výchozí 20000). Delší řada vrací chybu `RADA_PRILIS_DLOUHA` (text s délkou, stropem a nejvyšším počtem boxů,
  dotčené id řady), `postav` ale výstup přesto vrátí. `max_pocet_boxu(typ, smer, mezera_mm=1, max_delka_mm=20000)` dá nejvyšší počet pro nabídku:
  400×300 na délku 49 (49·400+48 = 19648), na šířku 66; 600×400 na délku 33 (33·600+32 = 19832), na šířku 49. Stejné číslo je ve výstupu `rady[].max_pocet_boxu`.
  `kopie_rady` řadu na stropu zkopíruje bez chyby; kopie řady nad stropem nese chybu u každé řady. Řada na stropu projde, +1 box je chyba (test `test_strop_delky_rady_20_m`).
  Poznámka: u řady dlouhé desítky metrů je střední podpora dráhy stále OTEVŘENÁ OTÁZKA (viz otázka 1); parametr `max_rozpeti_mm` je výchozí vypnutý.

## Náhled (změny po připomínce Roberta)

Boxy se kreslí jako pevné modré nádoby (obálka a nožka podle GLB, stěny 6 mm a dno 5 mm jsou jen vizuální), dráhy jako souvislá lišta stejné barvy;
u 5275 s ozdobnými válečky (polomer 10 mm, rozteč 26 mm; horní hrana válečků je přesně v rovině spodku nožky), u 5276 se kreslí skutečný mesh `dily/5276.glb` (STEP) v pozicích a natočeních modulů z výstupu `postav()`, trubky světle šedé, zarážka oranžová. Předvolby: vodorovná řada,
jedna skloněná, patro vedle sebe, dvě patra s různým sklonem, „Podle fotky: 3 patra“ (výchozí, pohled 3/4 zepředu zboku), „Dlouhá řada v jedné lince“ (11 boxů, 5°).
Pohled z boku podél osy Z je tlačítkem. Skutečná chyba, která dělala dojem „boxy nejsou v jedné lince“: původní náhled skládal natočení z levotočivé báze
(zrcadlo), takže se boxy kreslily s jiným sklonem než dráhy. Data z `postav()` byla v pořádku; opraveno jen v náhledu (báze se před převodem na kvaternion zpravotočivní).

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
- Dráha 5275: tělo pod rovinou válečků na výšku 38,86 mm.
- **Dráha 5276 = STEP (změřeno, [GLB] hotovo):** modul 41,0 × 61,67 × 255,04 mm se skládá z 12 těles (osy STEPu: X šířka, Y nahoru, Z podél; střed obálky ve STEPu
  (0; 28,335; 95,0), v `dily/5276.glb` je posunut do počátku):
  - lišta (tělo) 40,5 × 36,5 × 190 mm (Y −1,0 až 35,5);
  - 2 koncové plechy 41,0 × 44,0 × 88,9 mm (Y −2,5 až 41,5), zasahují 56,4 mm do těla a o 32,52 mm přečnívají (rozměr = „spojovací plech střední“ 5278);
  - 3 kolečka (rozteč 59,6 mm, osa rovnoběžná s X, střed Y = 31,2): váleček R 13,5 (Ø27, X −11,92 až 9,88, tedy 21,8 mm), jádro R 12,5, osička R 1,75, na straně +X
    DISK („talířek“) R 28,0 (Ø56) tloušťky 2,4 mm (X 9,88 až 12,28); horní okraj válečku Y = 44,7, horní okraj disku Y = 59,2: **disk přečnívá váleček o 14,5 mm**;
  - kolíky/příčky 35,7 × 12 × 6 a 3 hlavičky 2,4 × 6,4 × 6,4 (drobnosti uvnitř těla).
  Rovina, na které leží nožka boxu, je horní okraj válečků (Y = 44,7 ve STEPu). Disk **není** na okraji modulu: z těla zbývá za diskem 8 mm a před válečkem 8,4 mm.
  Mesh se tvoří z STEPu skriptem `dily/step_na_glb.py` (OCP, odchylka sítění 0,1 mm, 20 000 trojúhelníků, objemy těles sedí s STEPem na 1 %);
  kolizní náhrady v kódu (`STEP_5276`: 3 kvádry + 6 válců) kontroluje test proti meshi.
  Odvození rozteče: disk (vnitřní plocha v X = 9,88 od osy dráhy, výška nad rovinou válečků 14,5 mm) je vyšší než nožka (12 mm) i než spodek boku boxu, takže nemůže
  stát pod přesahem boxu a musí stát VNĚ boku boxu (vůle `disk_vule_mm`, výchozí 1 mm). U každé dráhy je disk na lokálním +X; levá dráha se otočí o 180°
  kolem normály (modul je podél souměrný jen přibližně: kolečka jsou na Z −58,0 / 1,6 / 61,2, tj. o 1,6 mm mimo střed), takže disky míří vždy ven.
- Orientace lokálních os plechů: Z podél (háček na −Z), Y nahoru, X napříč. U 5276 je disk na +X lokálně (viz výše).
- Moduly dráhy se řetězí v rozteči 255,04 mm (konec koncového plechu na konec koncového plechu), bez dalšího dílu. Mezi posledním kolečkem jednoho a prvním dalšího
  modulu pak vychází mezera 135,8 mm bez válečků (jinak 59,6 mm), box je přes ni stále podepřen (nožka 366 mm). Skutečný způsob spojení modulů ze STEPu nevyplývá
  (plechy 41,0 × 44,0 × 88,9 mm přečnívají 32,52 mm a nejsou užší než tělo, takže nejde o zasunutí jednoho modulu do druhého) `[GLB]`.
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
- 5276: boxy se vedou mezi disky; disk stojí vně boku boxu s vůlí 1 mm (parametr `disk_vule_mm`). Vnitřní plocha disku je v X = 9,88 od osy dráhy, proto
  rozteč = šířka boxu − 2·(9,88 − 1,0) = b − 17,76: **282,24 mm** (400×300 na délku) / **382,24 mm** (na šířku). Dráha pak přečnívá bok boxu o 11,6 mm (tělo 41 mm kolem osy).
  Váleček (X −11,92 až 9,88, 21,8 mm) leží pod nožkou jen na úseku mezi hranou nožky a diskem: nožka (zespodu 266 mm, tj. 17 mm od boku boxu) a vnitřní
  plocha disku je 1 mm vně boku, takže **nožka leží na každém válečku jen 3,8 mm své šířky**. Kód to hlásí jako varování `OPORA_NOZKY_MALA` (není to chyba: box se
  opírá o válečky, ale okrajem nožky). Zdánlivě těsná podpora může být zjednodušením nožky v GLB boxu (266 × 366 × 12 mm); rozteč je parametr `roztec_drah_mm`.
  Test (`test_drahy_5276_skutecna_geometrie_a_kolize_s_boxem`): na skutečných sítích (mesh dráhy z STEPu × originální GLB boxu) je objem průniku 0, horní okraj válečků
  = spodek nožky (≤ 0,2 mm, daň sítění), disky vně boxu s vůlí ≥ 1 mm; při rozteči 250 mm (disk pod přesahem boxu) objem průniku vychází > 0 a kód hlásí `KOLIZE`.
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
4. Dráha 5276, disky: disk je Ø56 × 2,4 mm, přečnívá váleček o 14,5 mm, takže stojí vně boku boxu (výchozí vůle 1 mm → rozteč 282,24 / 382,24 mm), a nožka pak leží
   na válečku jen 3,8 mm své šířky. Je to tak správně (a je nožka eurobox ve skutečnosti širší)? Nebo má být rozteč menší a nožka/box si mezi disky vybrat zářezy? Výchozí: disky vně boxu.
5. STEP dráhy 5276 obsahuje na koncích plechy 41,0 × 44,0 × 88,9 mm (rozměr 5278), které zasahují 56,4 mm do těla. Jsou to koncovky modulu, a jak se moduly řetězí dál
   (výchozí: konec plechu na konec plechu, bez dalšího dílu, mezera bez válečků 135,8 mm)? Jsou 5281/5282 něco jiného (jak na ně dosedají plechy 41,0 × 44,0 mm, když 5282 je
   38,47 × 55,75 mm a kapsa 27,75 mm vysoká)? Platí Robertových „54 až 55 mm“ zasunutí pro plech v těle (56,4 mm), nebo pro dráhu v 5281/5282? Výchozí: dráha v 5281/5282 54,5 mm.
5a. Při zasunutí 54,5 mm do 5281/5282 by první disk (od konce modulu 41,5 mm) zasahoval 13 mm do kapsy; kód to hlásí `DISK_V_KAPSE`. Výchozí: ponecháno 54,5 mm a varování.
6. Která dráha je výchozí? Výchozí: 5276 (pořadí ve zprávě), jiná jen parametrem `draha`.
7. Zasunutí 54,5 mm odpovídá hloubce kapsy? Výchozí: ano (zasunutí = kapsa = 54,5; menší zasunutí lze zadat).
8. Doporučený rozsah sklonu? Výchozí varování mimo 2 až 15° (chyba nad 45° a pod 0°).
9. Euroboxy 600×400: potvrdit výšky 120/170/220/320/420 a zda mají nožku (výchozí: kvádr bez nožky, karty 2999 až 3003).
10. Minimální výšková mezera mezi patry? Výchozí varování pod 10 mm (kopie „nad“ dodrží jakoukoli zadanou).
11. Tloušťka desky pod vodorovnou řadou (jen pro výškovou mezeru pater)? Výchozí 0 (řeší rám bota10).
12. Nosník Ø28 u kraje patra: jak daleko přesahuje krajní koncovku? Výchozí 0 (nohy a spojky doplní rám).

## Poznámka k nahled.html (kontrola zakázaných slov)
V nahled.html nejsou slova admin, logiman, localStorage, /api/, window.open, postMessage, eval ani cizí servery. Jediné výskyty „http://“ jsou čtyři jmenné prostory XML/SVG/XHTML (`http://www.w3.org/...`) uvnitř knihovny Three.js; nejde o žádný síťový požadavek. Pokud synchronizační filtr hledá obecně řetězec „http“, je nutné ho upravit, nebo mi dát vědět a nahradím je.
