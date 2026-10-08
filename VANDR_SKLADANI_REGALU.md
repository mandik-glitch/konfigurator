# Vandr — logika skládání regálu (odděleně od naší vlastní)

**Robert, 2026-09-06: oddělit od naší vlastní logiky, nemíchat v jednom
souboru.** Tenhle soubor drží POZOROVÁNÍ o tom, jak regál skládá
Vandr (Unity/C#) — je to jiná logika než naše vlastní
`PRAVIDLA_SPOJU.md`/`TVARY_VLASTNI.md`/`scripts/2026-08-18_shelf_builder.js`.
Cíl (Robert): mít v Three.js OBĚ logiky vedle sebe, ne je slévat do
jedné hybridní. O případném převzetí kusu do naší logiky se rozhoduje
vždy vědomě a zvlášť.

## Algoritmus (ověřeno přímo v C# kódu, 2026-09-06)

- Noha nemá N pater — má přesně DVĚ zóny: "bottom" (vždy přítomná) a
  "top" (volitelná — fyzicky přidává/odebírá skutečné hliníkové díly,
  `LegScript.cs` `HasTopArea()`/`EnableTopArea()`/`DisableTopArea()`).
  Žádné třetí patro v kódu neexistuje.
- Uvnitř JEDNÉ zóny je vertikální pozice VOLNÁ (drag&drop kamkoli v
  rozsahu zóny, `SideComponentScript.placeInLeg()`), ne rozdělená na
  diskrétní úrovně/patra.
- Komponenta se váže na JEDNU nohu z páru (tu bližší,
  `SideComponentScript.TryPlaceInLegs()`), ne na "mezeru mezi dvěma
  nohama". Šířka komponenty vs. šířka mezery se přitom vůbec neřeší.
- Šířka "sloupce" = šířka KATALOGOVÉ dvojice noh — diskrétní položka
  z předdefinované sady délek (`ComponentsMenuListAdapter.cs`, pole
  `lengths`), ne libovolné číslo, ne odvozená z komponent. Nohy se
  řadí sekvenčně podél stěny (`PlaceLegsScript.Place()`,
  `LegsAreaScript.findLegsPosZ/X`), zkrátí se, pokud se nevejdou do
  zbývajícího místa.
- Kolize hlídá Unity FYZIKÁLNÍ trigger engine (`LegScript.cs`
  `OnTriggerEnter/OnTriggerExit`) — jen obarví červeně, NEBLOKUJE
  umístění. Je to slabší mechanismus než naše přesná matematika
  (`touchReport`/`Box3` na všech 3 osách). Při vlastní implementaci
  NEPŘEBÍRAT tenhle měkký přístup, jen princip skládání — validaci
  dělat naší vlastní přesnou metodou.
- **"Univerzální" komponenty** (`is_universal=1`, "universal"/
  "univerzalni" v názvu) se GEOMETRICKY ŠKÁLUJÍ na šířku mezery mezi
  nohama minus pevná vůle (`SetWidth()` v C#, přeškáluje jednotlivé
  díly + přepočítá pozice bočnic) — skutečné škálování, ne opakování
  kusů vedle sebe. Podle Roberta (2026-09-06) škálují libovolně šířku
  i hloubku. **OPRAVENO (audit bot9, 2026-09-12):** `SetDepth()` NENÍ
  "nedohledaná" - je to POVINNÁ součást stejného C# rozhraní
  `IUniversalComponent` jako `SetWidth()` (obě metody deklarované v
  `IUniversalComponent.cs`, implementované ve všech 33 třídách v
  `ComponentScripts/Universal/`). **Nuance, kterou stojí za to znát:**
  ne všech 33 implementací funkčně škáluje - 26 tříd dělá reálné
  geometrické přeškálování (stejný vzor jako `SetWidth`), 5 má tělo
  jen no-op a `Police_0D_univerzalni.cs` má `SetDepth()` přímo
  `throw new NotImplementedException()` (a ve vlastním `Start()` ji
  ani nevolá - používá jen `SetWidth`). Robertovo "škálují libovolně
  šířku i hloubku" tedy platí pro drtivou většinu, ne bezvýjimečně.
- **Fixní (ne-univerzální) komponenty** se do nabídky filtrují přímým
  ČÍSELNÝM porovnáním rozsahu `min_width`/`max_width` proti skutečné
  mezeře mezi nohama (`ComponentsMenuListAdapter.cs`) — NE podle
  kategorie/`category_id` (ta jen štítkuje pro přehlednost v adminu,
  nerozhoduje o kompatibilitě).
- `.top` v názvu komponenty ↔ `is_top=1` ↔ patří do horní zóny nohy.
- **Síla profilu MUSÍ sedět mezi nohou a komponentou** (Robert
  2026-09-07): nohám z profilu 45 (45x45) patří komponenty z profilu
  45, k nohám z profilu 40 (40x40) patří komponenty z profilu 40 —
  NIKDY křížit. V DB je to `components_list_id` (viz
  `VANDR_RENDER_HOWTO.md`, seznam 9="Nohy 40x40", 10="Nohy 45x45";
  reálně chycená chyba: `Police.S40.0D.univerzalni` patří do 40x40, ne
  do 45x45, přestože název zní univerzálně). **Existují výjimky** —
  Robert zmínil šuplíky ("existují výjimky jako šuplíky různé typy") —
  zatím NEROZKLÍČOVÁNO, jak přesně výjimka funguje v DB/kódu, jen
  zaznamenáno, že pravidlo "síla profilu musí sedět" není 100% bez
  výjimek. Než se bude implementovat filtrování podle síly profilu,
  tohle je třeba doohledat v C# kódu (`ComponentsMenuListAdapter.cs`
  nebo obdoba) nebo se zeptat Roberta na konkrétní příklad.
  - **Konkrétní dohledaný příklad výjimky** (2026-09-07): komponenta
    `2supliky.ocel.20kg.130.1029.459` (id=102 v `vandrawee_work.
    components`) je zapsaná SOUČASNĚ v `components_components_lists`
    pro `components_list_id=9` ("Nohy 40x40") I `components_list_id=10`
    ("Nohy 45x45") — tenhle šuplík je tedy kompatibilní s OBĚMA silami
    profilu zároveň, na rozdíl od police/dveří, které jsou vždy jen v
    jednom seznamu. Mechanismus PROČ (jestli je to obecná vlastnost
    typu "šuplík" nebo vlastnost jen tohohle konkrétního kusu) zůstává
    nerozklíčovaný — tohle je jen první potvrzený příklad, ne úplné
    vysvětlení.
  - **Šuplíky navíc nedosedají čelem na stěnu nohy jako police/dveře**
    (ověřeno na Movano, `Suplik.ocel.100.1057.459` i `Suplik.maxi.30.
    200.1057.459`, oba nezávisle): konzistentní **45mm mezera** mezi
    koncovým nosníkem šuplíku a stěnou nohy na OBOU stranách, místo
    0mm jako u police/dveří. Vypadá to jako záměrný odstup pro
    výsuvný mechanismus (šuplík se musí umět vysunout, na rozdíl od
    pevně stojící police) — NEPOTVRZENO z C# kódu, jen pozorování ze
    dvou nezávislých šuplíků se stejným výsledkem. Při umísťování
    šuplíku tedy NEOČEKÁVAT gapFront/gapRear=0 jako u ostatních
    hlavních komponent — 45mm je (zatím pozorovaný) správný stav, ne
    chyba k opravě.
- **Zóna pro "hlavní komponenty" (výškový rozsah) = rozpětí ZADNÍHO
  sloupku nohy, ne celá výška nohy** (Robert 2026-09-07, ověřeno na
  Sprinter H1 1580 přes skutečné FBX mesh názvy a Box3 měření). Noha
  je rám ze 2 svislých sloupků (`*_noha` mesh) + vodorovné vzpěry
  (`*_Zx1`/`*_Zx2` mesh) mezi nimi:
  - **PŘEDNÍ sloupek** = ten DELŠÍ, kladné Z (u přístupové strany) —
    vždy plná nominální výška nohy (`45x45x1580_noha`, Y 0→1580mm u
    obou variant Sprinter H1 - normální i výřez, nemění se).
  - **ZADNÍ sloupek** = ten KRATŠÍ, záporné Z (u stěny/karoserie,
    stejná strana jako `feedback_regal_orientace_predni_zadni`
    konvence "výřez = zadní") — jeho SVISLÝ ROZSAH (Y min→max) přesně
    definuje, odkud kam se smí vkládat hlavní komponenty:
    - normální noha: `45x45x1200_noha`, Y ≈ 0 → 1177,5mm → hlavní
      komponenty od podlahy až do ~1177,5mm.
    - noha s výřezem (STEJNÝ model, jen zadní sloupek zkrácený zdola):
      `45x45x795_noha`, Y ≈ 382,5 → 1177,5mm → horní hranice STEJNÁ
      (1177,5mm), ale SPODNÍ hranice se posune nahoru na 382,5mm —
      výřez tedy neposouvá strop zóny, jen zvedá její podlahu (kvůli
      uvolnění místa pro překážku, např. podběh kola).
    - Prostor NAD zadním sloupkem (zde ~1177,5 → ~1557,5mm, odpovídá
      samostatné 380mm vzpěře `45x45x380_Zx1` u vrcholu) do zóny
      hlavních komponentů NEPATŘÍ — je to kandidát na propojení s už
      dokumentovanou "top" zónou (`.top`/`is_top=1`) výše, ne
      potvrzeno křížovou kontrolou, jen pozorovaná shoda rozměrů.
  - **Identifikace v kódu/scriptu: NIKDY podle barvy z `colorize()`**
    (ta je jen náhodná podle pořadí meshů v souboru, viz
    `VANDR_RENDER_HOWTO.md` ⭐ pravidlo) — vždy podle skutečného jména
    meshe (`*_noha` = svislý sloupek, `*_Zx1`/`*_Zx2` = vzpěra) a
    znaménka Z (kladné=přední, záporné=zadní).
  - **Vizuálně ověřeno (2026-09-07, Sprinter H1 1580):** 3 komponenty
    zároveň mezi stejným párem noh bez kolize — `Police.1D.1057.459`
    (hlavní zóna, spodek 400mm), `Police.uzka.A.1057.459` (hlavní
    zóna, spodek 720mm, VOLNĚ zvolená výška, ne pevné patro) a
    `Police.1D.1057.414.top` (`is_top=1`, horní zóna, spodek 1207,5mm
    — nad hranicí 1177,5mm hlavní zóny). Potvrzuje C# nález výše
    ("vertikální pozice VOLNÁ v rámci zóny") i vizuálně, ze 4 úhlů
    (iso/front/side/top), ne jen výpočtem.
  - **ZÁVAZNÉ pravidlo (Robert 2026-09-07): čelo profilu komponenty
    musí dolehat na stěnu profilu nohy — STEJNÝ princip jako Pravidlo
    č.1 z naší vlastní `PRAVIDLA_SPOJU.md`** ("žádné zanoření, žádné
    částečně kryté čelo"), teď aplikovaný na Vandr komponenty. Platí
    jak v hlavním těle (větší hloubka 459mm), tak ve vrchním bloku
    (414mm) — NENÍ to shoda náhodou, je to fyzická vlastnost dílu
    (koncový nosník komponenty, `alu` mesh s nejmenším/největším X, se
    zasouvá do mezery MEZI předním a zadním sloupkem nohy a jeho čelo
    musí přesně lícovat s vnitřní stěnou obou sloupků).
    - **Ověřeno měřením** (Sprinter H1 1580, `Police.1D.1057.459`):
      koncový nosník `45x45x369_Zx2` má čelo–stěna mezeru přesně 0mm
      na obou stranách (vůči přednímu i zadnímu sloupku hlavní zóny).
    - **DŮLEŽITÁ past — vrchní blok má VLASTNÍ, ASYMETRICKOU zadní
      stěnu:** hlavní zadní sloupek nohy (`*_noha`, kratší) nesahá do
      vrchní zóny (končí na hranici hlavní/top zóny, viz výše). Místo
      něj tam je SAMOSTATNÝ díl (`*_Zx1`, u Sprinter H1 1580 jde o
      `45x45x380_Zx1`), který sedí o 45mm BLÍŽ K PŘEDKU než by byl
      hlavní zadní sloupek (vnitřní stěna na Z=-139,5mm místo -184,5mm
      hlavní zóny). Když se top komponenta vystředí STEJNÝM symetrickým
      vzorcem jako hlavní tělo, vznikne 22,5mm mezera na OBOU stranách
      (koncový nosník top komponenty je navíc i kratší — 324mm místo
      369mm, přesně o těch 45mm). **Správný postup:** nevystřeďovat top
      komponentu symetricky — zarovnat čelo koncového nosníku na
      PŘEDNÍ stěnu (stejná jako hlavní tělo, sloupek tam sahá po celé
      výšce), zadní čelo pak dosedne samo (ověřeno: mezera 0mm na obou
      stranách po opravě). Obecně: **nikdy nepředpokládej, že vrchní
      zóna sdílí stejnou zadní stěnu jako hlavní zóna — vždy ji najdi
      měřením** (hledej `alu` mesh nad hranicí hlavní zóny, se
      záporným Z).
    - Číselná kontrola (ne vizuální odhad): `komponenta.max.z -
      noha.frontWallZ` (přesah/mezera vepředu) a `komponenta.min.z -
      noha.rearWallZ` (přesah/mezera vzadu, POZOR použij zadní stěnu
      PRO DANOU ZÓNU, ne automaticky hlavní zónu) — obě musí být 0.
  - **ZÁVAZNÉ pravidlo (Robert 2026-09-07, potvrzeno "to je v podstatě
    pravidlo"): STEJNÝ princip dosednutí platí i SVISLE (osa Y), ne jen
    vodorovně (osa Z).** Když je zadní sloupek nohy přerušený (výřez) a
    níž pod přerušením je samostatný přemosťovací díl, jeho VRCHNÍ
    plocha je "obnažené čelo" — boční profil NEJNIŽŠÍ komponenty v té
    zóně na něj musí přesně dosednout, ne se vznášet s libovolnou
    rezervou nad ním.
    - **Reálně chycená chyba** (Movano H1 1490, `Suplik.ocel.100.1057.459`
      jako nejnižší šuplík v bottom zóně): umístil jsem šuplík do
      výšky 400mm jako "bezpečnou rezervu" nad odhadnutou hranicí
      výřezu (357,5mm) — Robert: "na spodní profil zadní nohy...
      musí dosednout boční profil nejnižšího komponentu". Správně:
      žádná rezerva, přesné dosednutí. Skutečná (změřená, ne
      odhadnutá) výška exponovaného čela v tomhle transformačním
      řetězci vyšla 380,0mm (liší se od hrubého odhadu 357,5mm — vždy
      měř PO aplikaci stejné transformace jako produkční kód, ne v
      izolovaném rámci modelu).
    - **Reference pro "boční profil" komponenty je STEJNÝ díl jako
      `endBracketOf()`** (koncový nosník, `alu` mesh s nejmenším X) —
      NE celý bbox komponenty, ten obsahuje šrouby/kolečkové drážky
      čnějící o pár mm níž (-27/-31mm vs -22,5mm u samotného nosníku).
      Stejná třída chyby jako všude výše: měř funkční díl, ne celý box.
    - Číselná kontrola: `nejnizsiKomponenta.endBracket.min.y -
      noha.exponovanaPodlahaY` musí být přesně 0.
- Je to ŽIVÝ běžící algoritmus, ne jen precomputed tabulka: stejná
  funkce `TryPlace()` se volá jak z živého přetahování myší, tak z
  načtení uložené sestavy. `stored_model_parts.data` (JSON) je cache
  VSTUPNÍCH PARAMETRŮ (pozice/délka) pro tenhle algoritmus, ne náhrada
  za něj.

- **Dotyková stěna pro flush-fit komponenty v ose Z = VNITŘNÍ stěna
  předního/zadního sloupku, ne celková `structuralZRange()` obálka nohy**
  (reálně chycená chyba, 2026-09-07, Ducato H2.1700.459 +
  `Police.1D.1057.459`): noha je RÁM (2 svislé sloupky `*_noha` + vzpěry
  `*_Zx1`/`*_Zx2` MEZI nimi, viz výše "Zóna pro hlavní komponenty").
  `structuralZRange()` (všechny `alu` meshe) dá CELKOVOU obálku obou
  sloupků (u "459" rodiny 459mm, vnější hrana-vnější hrana) — když se
  podle NÍ počítá gap komponenty, vyjde falešná 45mm mezera na obou
  stranách (přesně šířka jednoho profilu), přestože komponenta ve
  skutečnosti flush-fituje. Správná dotyková reference je VNITŘNÍ stěna
  sloupků (u "459" rodiny 369mm rozpon — přesně odpovídá hloubce vzpěry
  `*_Zx2`, viz `Police.1D.1057.459`, jehož koncové nosníky mají STEJNÝCH
  369mm) — nová funkce `innerWallZRangeOf(legObj)` v
  `scripts/2026-09-07_vandr_render/vandr_geometry_lib.js`. Použij ji
  VŽDY pro flush-check komponenty vůči noze; `structuralZRange()` nech
  jen pro celkovou hloubku SAMOTNÉ nohy (např. porovnání dvou různých
  noh mezi sebou).
- **Ověřeno funkční** (2026-09-07): Ducato H2.1700.459 (DB `legs.id=121`,
  `components_list_id=10`) + `Police.1D.1057.459` (id=4, `min_width=
  max_width=967`) — outer span 1057mm (přesně fyzická šířka komponenty),
  gapFront/gapRear ±0,001mm po opravě reference, floor-flush 0mm. Render
  + izolovaná 2D kontrola: `scripts/2026-09-07_vandr_render/
  render_ducato_l2h2.html` + `render_ducato_l2h2_2dcheck.html`.
- **Y-reference pro "sedí na podlaze/volně nad předchozím dílem" = CELÝ
  bbox komponenty, NIKDY `endBracketOf().min.y`** (reálně chycená chyba,
  2026-09-07, `Suplik.ocel.200.1057.459`): u šuplíků sedí boční montážní
  nosník (ta samá "alu" část, co slouží pro Z-centrování) výš než
  skutečné dno krabice — nosník je pro ZAVĚŠENÍ do zóny na boku nohy, ne
  pro dosednutí na podlahu. Když se `yBottomTarget` navázal na
  `endBracketOf().min.y` (jako u trvale ověřené `Police.1D.1057.459`,
  kde se to shoduje), tělo šuplíku viselo ~90mm POD podlahou nohy, i
  když číselná kontrola gapFront/gapRear (ta je NEZÁVISLÁ, pořád jen o
  ose Z) hlásila 0. **Endbracket pro CENTROVÁNÍ v X/Z ano, ale pro
  vertikální umístění (Y) vždy `Box3().setFromObject(comp).min.y`** —
  u komponent, kde nosník sedí u dna (Police, dvířka), vyjde stejně;
  u šuplíků je to jediná správná volba. Tohle je NEZÁVISLÝ nález na
  dřívější "45mm mezera u šuplíků" poznámku níže (ta je o ose Z) — možná
  související, ale NEPOTVRZENO křížovou kontrolou, viz poznámka tam.
- **Ne každá "459" komponenta má symetrický pár bočních koncových
  nosníků, kde funguje generický `endBracketOf()`** (2026-09-07,
  `Police.uzka.A.1057.459` a `Odkladaci.plocha.A.1057.459`): některé
  komponenty (potvrzeno na těchto dvou) nemají boční "alu" nosníky
  vůbec — jen přední/zadní příčky (`Zx2` spanning celou šířku na
  VNĚJŠÍCH Z hranicích, ne na vnitřní stěně) nebo asymetrický rámeček
  posazený jen k jedné straně hloubky. `endBracketOf()` (nejmenší min.x
  "alu" mesh) pak vybere úplně jinou funkční část než u
  `Police.1D.1057.459`/`Stul.A.1057.459` (ty MAJÍ symetrický pár
  bočních nosníků, 369mm hloubka, a fungují správně) — vyšla falešná
  164mm mezera. Než se pro tenhle typ komponenty napíše specializovaná
  logika, NEPOUŽÍVAT generické centrování — buď vybrat jinou komponentu
  se stejnou stavbou jako `Police.1D.1057.459`, nebo nejdřív zjistit
  `.alu` breakdown a rozhodnout reference ručně.
- **NEVYŘEŠENÁ POCHYBNOST o "šuplíky nedosedají, 45mm mezera je
  správný stav"** (viz poznámka o `Suplik.ocel.100.1057.459` a
  `Suplik.maxi.30.200.1057.459` na Movano, výše): ten 45mm nález byl
  změřen PŘED objevem `innerWallZRangeOf()` (tedy proti tehdy jediné
  dostupné `structuralZRange()` referenci) — přesně ta samá chyba, co
  na Ducatu vyrobila falešných 45mm u `Police.1D.1057.459`. Možné, že
  šuplíky ve skutečnosti TAKÉ flush-fitují na 0mm a ten dřívější závěr
  byl mylný. **Než se na tenhle poznatek bude cokoli stavět, přeměř
  Movano případ znovu s `innerWallZRangeOf()`** — Ducato
  `Suplik.ocel.200.1057.459` v tomhle novém běhu vyšel na 0mm
  (gapFront/gapRear −0,001), což tu pochybnost jen posiluje, ale je to
  jiný konkrétní soubor (200 vs 100/maxí.30.200), takže to NENÍ
  automaticky důkaz pro Movano případ.

## ⭐ Pravidlo pro rekonstrukci geometrie z receptu (Robert, 2026-09-19)

**Noha je vždy nedělitelný celek, každý komponent je vždy nedělitelný
celek.** Doslovné znění Robertovo. Platí pro KAŽDÝ pokus poskládat
geometrii sestavy z jejího JSON receptu (`GET vandrawee.eu/api/work/
stored_models/{uuid}`, viz `left_data`/`right_data`/`bulkhead_data`
stromy) — noha (`left_leg`/`right_leg`) i každá komponenta
(`components[]`) se vkládá jako JEDEN atomický objekt (celý její FBX
naimportovaný vcelku, s vlastním `unity_id`+`position`+`rotation`),
NIKDY rozložená na jednotlivé kusy/sub-díly. `replaced_parts` (parametricky
zkrácené profily uvnitř nohy/komponenty) se řeší jako přeškálování
POJMENOVANÉHO sub-meshe UVNITŘ už takhle vloženého celku (`zScale =
new_length/original_length` podél lokální osy dílu) — NIKDY jako nový,
samostatně umístěný objekt vedle ostatních.

**Proč je to tady zapsané:** 2026-09-18/19, pokus poskládat geometrii
sestavy z receptu (Python/Blender, `build_v3.py`) rozkládal/přeskupoval
nohy a komponenty na jednotlivé kusy místo aby je vložil vcelku podle
stromu receptu — Robert výsledek označil za "úplně špatně" DVAKRÁT, než
den poté dal tuhle konkrétní diagnózu. Viz i osobní paměť bota, který na
tom pracoval (`vandrawee_fbx_export_dead_ends.md`) — úkol byl mezitím
uzavřen ("s timto koncime"), tohle pravidlo čeká na chvíli, kdy se
případně znovu otevře.

## Srovnání s naší `buildShelf()` (`scripts/2026-08-18_shelf_builder.js`)

Jiný TVAR výsledku, ne jen jiná implementace:
- **My:** 4 nohy v rozích uzavřeného obdélníkového rámu, explicitní
  pole výšek všech pater, na každém patře kompletní rám (T-styl spoj).
- **Vandr:** 2 nohy (pár) u jedné stěny auta, přesně 2 zóny, žádný
  "rám" na patře — komponenta visí na jedné noze, druhá strana volná
  nebo na sousední noze jiné komponenty.

## Navržený první krok k vyzkoušení (neimplementováno, čeká na rozhodnutí)

Postavit Vandr-styl jako DRUHOU, samostatnou možnost vedle
`buildShelf()`: pár noh + 1 volně umístitelná komponenta v bottom
zóně, s NAŠÍ vlastní přesnou kolizní kontrolou (ne měkkým Unity
přístupem). Horní zóna jako samostatný druhý přírůstek až po tomhle.
