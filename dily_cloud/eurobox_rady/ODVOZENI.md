# Řady euroboxů s válečkovými dráhami: odvození

Stav: 2026-10-12, agent pro bota10. Dráhy 5275 a 5276, koncovky 5281 a 5282 i trubka 3673 jsou teď **z katalogových GLB**
(`dily/katalog/product_<karta>.glb`, střed obálky v počátku, změřeno) a jejich polohy vůči sobě jsou odvozené z geometrie a ověřené
na skutečných sítích. Dříve odhadnuté tvary (hák Ω, kapsa 54,5 mm, boční doraz, disk) jsou nahrazené.

## Shrnutí (co plyne z geometrie)

- **Dráha leží na válečcích, rovina válečků = spodek nožky boxu.** Obě dráhy mají na každém konci ploché plechové **ucho** (1,5 mm, šířka 34,9 mm,
  štěrbina 8 × 12 mm). Ucho se nasouvá do **kapsy** koncovky z jejího otevřeného konce a leží na základně kapsy (vůle 0,3 mm ke stěnám); stěny kapsy
  mají zahnuté horní hrany (světlost 30,6 mm < ucho 34,9 mm), takže ucho drží.
- **Koncovka 5281/5282 = kapsa (U-žlábek) + hák na trubku.** Hák je převrácené U s okem 1,5 mm, světlost mezi rameny 27,6 mm: trubka Ø28 se zaklapne s přesahem
  0,2 mm na každé straně (změřeno: 61 mm³ na 34 mm šířky háku; plech je pružný). Trubka se dotýká stropu háku. Osa trubky je 16,8 mm před lícem zarážky
  a **10,75 mm nad základnou kapsy**, tj. 6,05 mm (5276) / 10,24 mm (5275) NAD rovinou válečků (ucho leží na základně a rovina válečků je nad uchem
  4,7 mm u 5276, 0,5 mm u 5275). Trubka tedy neleží pod dráhou, ale vedle konce dráhy (před boxem), s osou nad rovinou válečků.
- **Zarážka 5282** je svislý plech (34 mm široký) těsně za hákem, líc zarážky je v z = −11,1 (v lokálních souřadnicích dílu). Vyčnívá 28,0 mm nad vrchol háku
  (to je Robertových 28 mm) a 49,5 mm nad rovinu válečků u 5276. Box se o ni opírá předkem boxu.
- **Robertových „cca 54 až 55 mm“** = vzdálenost líce zarážky od vnější plochy příruby dráhy: kapsa je od zarážky 54,24 mm dlouhá (z = −11,1 až 43,14)
  a příruba dráhy dosedá na její otevřený konec. Výchozí `zasun_draha_mm` = 54,5 (příruba 0,26 mm za koncem kapsy). Dovolený rozsah daný štěrbinami je
  54,2 až 61,9 mm (5276) / 54,2 až 65,3 mm (5275); pod 54,24 mm příruba narazí do konce kapsy (kolize), nad rozsahem štěrbiny neleží nad sebou
  (chyba `ZASUN_MIMO_DRAZKU`).
- **Vzdálenost trubek** podél sklonu = (s_be + 54,5 + 16,8) − (−16,8), kde s_be je vnější plocha příruby posledního modulu (s = 0 je líc zarážky). Např. 5 boxů 400×300
  na délku (2004 mm): 5276 má 8 modulů a trubky 2120,9 mm od sebe; 5275 má 8 modulů a 2247,4 mm. Vzorec „délka dráhy − 2 × zasunutí“ z dřívější zprávy neplatí
  (trubka je za koncem dráhy, ne uvnitř).
- **Moduly**: 5275 = 271,66 mm (6 koleček, rozteč 33,4 mm, R 13,4, bez disků), 5276 = 255,04 mm (3 kolečka, rozteč 59,6 mm, váleček R 13,5 + disk R 28 × 2,4 mm
  na lokálním +X, disk přečnívá váleček o 14,5 mm). Moduly se v řadě řetězí **uchem na ucho (špička na špičku)**, rozteč = délka modulu; mezi poslední přírubou
  jednoho a první přírubou dalšího modulu je pak 62,0 mm (5276) / 68,5 mm (5275) bez válečků. Počet modulů m = ⌈(L − 54,5 − 2·u_příruba) / délka⌉ + 1 (L = délka řady).
- 5276 z katalogu = 5276 ze STEPu od Roberta (stejná obálka 41,0 × 61,67 × 255,04, vrcholy se liší nejvýš o 1,4 mm = jiné sítění).
- Boxy 400×300 jsou ověřené na GLB 3788 až 3796 (pozice+kvaternion na 0,02 mm, nožka dole 266 × 366 mm, výška 12 mm).

## Co ještě nesedí (poctivě)

1. **Stěny kapsy 5282 přečnívají rovinu válečků o 12,5 mm (5276) / 16,7 mm (5275)** a leží pod předkem prvního boxu (od líce zarážky 54 mm), kde je nožka boxu
   z GLB (plný blok 12 mm). Objem průniku skutečných sítí: 889 mm³ (5276), 1488 mm³ (5275). Kód to hlásí jako varování `BOX_NAD_KONCOVKOU`, ne jako chybu;
   parametr `odsazeni_koncovky_mm` ≥ 54,3 přesune koncovku před box (pak 0 mm³, ale zarážka box nezachytí). Buď má skutečný eurobox pod předkem větší vůli
   (nožka v GLB je zjednodušená), nebo se koncovka montuje jinak. **Otázka pro Roberta č. 1.**
2. **Nožka leží na válečku jen 3,8 mm** (5276: disky stojí vně boku boxu, `OPORA_NOZKY_MALA`). Disk (14,5 mm nad válečkem) je vyšší než nožka (12 mm) i než
   spodek boku boxu, takže nemůže stát pod přesahem boxu. Výchozí rozteč 282,24 mm = b − 2·(9,88 − 1,0). Stejná otázka (č. 2): je nožka eurobox širší?
3. **Ucho 5275 je o 1,0 mm nad horním okrajem válečků** (ucho 17,12 až 18,62, válečky 17,63): box se na stycích modulů opře o ucha. Kód: `UCHO_NAD_ROVINOU`.
   U 5276 je ucho 3,2 mm pod rovinou válečků, tam problém není.
4. **Spojení modulů** (ucho na ucho bez dalšího dílu) je hypotéza: STEP/GLB neukazují, jak by se dvě ucha spojila (ležela by obě ve stejné rovině).
   Podle rozměrů by mohly sloužit díly 5277 až 5280 (Z-plechy s kapsou a uchem), ale to z geometrie nevyplývá. **Otázka č. 3.**
5. Poloha ucha vůči základně kapsy: ucho leží NA základně (kapsa je hluboká 17 mm, ucho je 1,5 mm). Alternativa (ucho pod základnou) není geometrií vyloučena;
   zvolil jsem ucho v kapse, protože stěny kapsy a ucho si šířkou přesně odpovídají (35,5 vs 34,9 mm). Neověřeno.
6. Střední podpora dlouhých drah (řada až 20 m): otevřená otázka, parametr `max_rozpeti_mm` je výchozí vypnutý.

## Pravidla od Roberta (platí)

- **Boxy se naklánějí spolu s dráhami**: všechny boxy řady mají stejný sklon jako obě dráhy, spodek nožky leží v rovině válečků obou drah. Test
  `test_boxy_nakloneny_spolu_s_drahami` to měří jen z výstupu a z GLB (úhel osy boxu = úhel dráhy, vzdálenost nožka–válečky ≤ 0,1 mm, obě dráhy a všechny moduly
  v jedné rovině, řady jednoho patra v jedné šikmé rovině).
- **Strop délky řady 20 m**: `max_delka_rady_mm` (výchozí 20000), chyba `RADA_PRILIS_DLOUHA` (výstup se přesto vrátí), `max_pocet_boxu(typ, smer, mezera, strop)`:
  400×300 na délku 49 / na šířku 66; 600×400 na délku 33 / na šířku 49.

## Výklad pojmů bota10: potvrzeno

Řada = n boxů za sebou, mezera 1 mm, délka = n·a + (n−1)·1; sklon kolem vodorovné osy kolmé na osu řady, nižší konec vpředu (`nizsi_konec`); patro = řady vedle sebe
v téže výšce se společným dolním nosníkem, horní nosníky podle délky řady; mezera u kopie „nad“ = výšková vzdálenost horní okraj boxů spodního patra / nejnižší díl horního,
u kopie „vedle“ čistá vzdálenost konstrukce (nosník se nepočítá); `y` = spodek nožky prvního boxu na nižším konci. Dolní konec dráhy je vždy na nižším nosníku.

## Co je z geometrie a co odhad

Změřeno z GLB: rozměry a středy všech dílů (testy `test_katalog_glb_rozmery_a_stredy`, `test_konstanty_dilu_proti_meshi`); poloha ucha, příruby, válečků a disku dráhy;
základna, stěny, zarážka, hák a štěrbina koncovky; trubka 3673 je dutá trubka Ø28 × 1000 mm (osa Y, střed v počátku, měřítko Y = délka / 1000).
Z geometrie odvozeno: poloha koncovky vůči dráze (ucho na základně, štěrbiny nad sebou), osa trubky v háku, rozteč drah, počet modulů.
Odhad / neověřeno: spojení modulů, ucho na základně (ne pod ní), ucho 34,9 mm vs. kapsa 35,5 mm (přesah/vůle), 600×400 bez modelu (kvádr bez nožky, karty 2999 až 3003 v pořadí výšek).
Kolizní náhrady v kódu (`DILY`, `KONCOVKY`) jsou kvádry a válce obsahující mesh (test); objem průniku se ověřuje na skutečných sítích:
ucho × koncovka ≤ 5 mm³ (kontakt), moduly mezi sebou 0, dráha 5276 × box 0, koncovka × box (odsazení ≥ 54,3) 0, trubka × box a trubka × dráha 0, hák × trubka 61 mm³ (zaklapnutí).

## Výchozí rozteč dvou drah (`roztec_drah_mm`)

Válečky musí ležet pod nožkou boxu (zespodu 266 mm napříč při směru „delka“, 366 mm při „sirka“).
- 5276: disk (vnitřní plocha v 9,88 mm od osy dráhy) stojí vně boku boxu s vůlí 1 mm: **b − 17,76** = 282,24 mm (delka) / 382,24 mm (sirka). Dráha přečnívá bok boxu o 11,6 mm.
- 5275: válečky (±14,0 mm) 10 mm uvnitř hrany nožky: **nožka − 2·(14,0 + 10)** = 218,0 mm (delka) / 318,0 mm (sirka).

## Náhled (`nahled.html`, `python3 -I sestav_nahled.py`)

Boxy pevné modré nádoby (obálka a nožka podle GLB), dráhy a koncovky katalogové meshe (instance z výstupu: part_id, position, quaternion), trubky válce Ø28.
6 předvoleb (vodorovná řada, jedna skloněná, patro vedle sebe, dvě patra, „Podle fotky: 3 patra“, „Dlouhá řada v jedné lince“), pohledy zepředu zboku / z boku (osa Z) / shora.
`rez_sestavy.py` kreslí boční řezy sestavou (`obr_rez_konce_5276.png`, `obr_rez_konce_5275.png`): ucho v kapse, trubka v háku, zarážka, box na válečcích.

## Výstup `postav(spec)` (stručně)

`boxy`, `draha` (po řadách: pasy 1 a 2, moduly s part_id, position, quaternion, `tvary_nahrady`, `telo_od_do_mm`, vzdálenost trubek), `koncovky` (role `dolni` = 5282,
`horni` = 5281; `spoj` není), `nosniky` (`a`, `b`, role, patro, part_id 3673, position, quaternion, scale = [1, délka/1000, 1]), `opory` (vodorovné řady), `rady`,
`mezery_pater`, `rozmery`, `problemy`, `parametry`. Pozice dílu = požadovaný střed − R·střed GLB (všechny katalogové GLB mají střed 0,0,0, změřeno).
`x, y, z` řady = dolní roh obálky prvního boxu na nižším konci řady (spodek nožky). `kopie_rady(spec, id, "vedle"|"nad", mezera, pocet, sklon_deg=None, patro=None)`.
Parametry nově: `zasun_draha_mm` (54,5 = líc zarážky – příruba dráhy), `odsazeni_koncovky_mm` (0), `disk_vule_mm` (1); zrušené: `kapsa_hloubka_mm`, `zarazka_u`, `hrubka_zarazky_mm`.

## OTEVŘENÉ OTÁZKY PRO ROBERTA (každá s výchozí hodnotou)

1. Stěny kapsy 5282 vyčnívají 12,5 mm (5276) / 16,7 mm (5275) nad rovinu válečků a leží pod předkem boxu, kde je nožka. Je skutečná nožka eurobox pod předkem nižší (zářezy)?
   Nebo se má první box opírat o zarážku jinak? Výchozí: box u zarážky, kód hlásí varování `BOX_NAD_KONCOVKOU`; parametr `odsazeni_koncovky_mm` ≥ 54,3 to odstraní.
2. Nožka leží na válečku 5276 jen 3,8 mm (disky vně boxu). Je to záměr (box vedený disky za bok), nebo má být nožka širší? Výchozí rozteč 282,24 mm.
3. Jak se spojují dva moduly dráhy (ucho na ucho leží ve stejné rovině)? Jsou na to 5277 až 5280, nebo 5281 jako spojka? Výchozí: ucho na ucho bez dílu.
4. Je ucho dráhy v kapse NA základně (výchozí), nebo POD ní?
5. Ucho 5275 je 1,0 mm nad válečky (box se opírá o ucha u spojů modulů). Přijatelné?
6. Která dráha je výchozí? Výchozí 5276.
7. Doporučený rozsah sklonu? Výchozí varování mimo 2 až 15° (chyba nad 45° a pod 0°).
8. Euroboxy 600×400: potvrdit výšky 120/170/220/320/420 a zda mají nožku (výchozí kvádr bez nožky, karty 2999 až 3003).
9. Minimální výšková mezera pater? Výchozí varování pod 10 mm.
10. Tloušťka desky pod vodorovnou řadou? Výchozí 0 (řeší rám bota10). Přesah trubky za krajní koncovku? Výchozí 0.
11. Střední podpora drah u dlouhých řad (až 20 m)? Výchozí žádná (`max_rozpeti_mm` vypnuto).
