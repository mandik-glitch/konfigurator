# Připojování příslušenství (spojky/úhelníky/kostky) na profily

Klasifikace montážního režimu příslušenství (endcap/corner_side/wall/corner3/parallel_side/none), runtime výběr montážní plochy (MĚŘIT, ne odhadovat), historie systematického ověřování katalogových dílů. Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31. Viz taky `PRAVIDLA_SPOJU.md` pro obecnou geometrii spoje.

## 2q. Napojení příslušenství (úhelníky/spojky) na profily — "Možnosti napojení" (2026-07-28)

Robert: "jde mi o to naučit systém jak spojovat profily s úhelníky" → "úhelník je snadný, přikládá se na plochy profilů i do čela, vždy kolmo a vždy jen rovnou stěnou nikoli oblou."

Do teď panel "Možnosti napojení" (2k) fungoval VÝHRADNĚ mezi dvěma profily — jakmile byl jeden z vybraných dílů příslušenství/spojka/produkt (nemá `cross_section_mm`, viz `fetch_katalog_parts()` v `app.py`), algoritmus vrátil vždy prázdný seznam kandidátů (tvrdá brána `crossSectionsCompatible`, ne otázka geometrie).

**Řešení:** nová cesta `findAccessoryToProfileCandidates(accEntry, profEntry)` — spustí se, když vybraný díl BEZ průřezu (příslušenství/produkt) stojí proti profilu. Využívá STEJNÉ univerzální konektory jako profily (`computeConnectorsLocal` dává každému dílu, bez ohledu na tvar, 2× "end" + 1× "mid" + 4× "face" = všech 6 stěn jeho bounding-boxu) — i kompaktní/kubický tvar (úhelníková spojka) tak má 6 kandidátních rovných ploch k přiložení. Každá dvojice (plocha příslušenství, plocha NEBO čelo profilu — "face" i "end", nikdy "mid") dá jeden kandidát: normály se zarovnají přesně proti sobě, středy ploch se překryjí (stejný vzorec pozice jako existující profil-profil "plocha na plochu").

Žádný nový příznak v adminu — detekce "tohle je příslušenství, ne profil" je čistě z existujících dat (chybějící `cross_section_mm`), přesně jak Robert zvolil ("automaticky z geometrie/dat", ne ruční označení typu dílu).

**Známý limit V1:** orientace kolem společné osy dotyku ("roll") není enumerována do více variant — každá dvojice ploch dá jen JEDNU kandidátní orientaci (uživatel si vybírá mezi RŮZNÝMI PLOCHAMI/čely přes hover-preview, ne mezi natočeními jedné plochy). Pokud se ukáže potřeba i roll varianty, přidat stejným způsobem jako `MAGNET_COMPASS_DIRS` u profil-profil rohu.

Ověřeno Node.js harnessem na reálných rozměrech (profil 30×30×1000mm + úhelník 29×28×29mm — produkt 2895 "Úhelníková spojka 30x30"): 36 kandidátů (6×6), u všech potvrzeno matematicky správné zarovnání i překryv ploch.

## 2r. Znacky napojeni ve 3D scene misto panelu (2026-07-28)

Robert: "funguje to vyborne, ale namisto te tabulky moznych spoju bych si predstavoval nejake jen ukazatele kolem toho mista kde se to napojuje pri pohybu mysi kolem profilu" -> upresneno: ukazatele se maji objevit KDYKOLI je kurzor blizko profilu (ne jen behem aktivniho presouvani dilu).

Panel "Moznosti napojeni" (2k) - seznam textovych tlacitek - nahrazen plovoucimi koleckovymi znackami primo v 3D scene. Vypocet kandidatu (findConnectionCandidates/findAccessoryToProfileCandidates) se NEMENI - meni se jen prezentace. Kandidati se stejnym cilovym bodem (stejny konektor na stejnem parent dilu) se seskupi pod JEDNU znacku - typicky u prislusenstvi (az 6 ploch na 1 bod profilu). Znacka je viditelna jen kdyz je kurzor mysi do ~240px (obrazovkove vzdalenosti, CONNECTION_MARKER_REVEAL_PX) od jeji promitnute pozice - "objevi se pri priblizeni k profilu". 1 polozka ve skupine -> klik rovnou spoji. Vice polozek -> klik rozbali male okenko s variantami vedle znacky. Najeti mysi porad spousti stejny zivy nahled (magnetStartPreview) jako drive.

Stary panel (#magnetPanel, refreshMagnetPanel()) zustava v kodu definovany (nevyuzity) pro pripad potreby vratit se k nemu.

## 2s. Přichycení příslušenství tažením myší (Posun myší) — nahrazuje 2r (2026-08-01)

Robert: nejdřív "furt to problikává!!!!!!" (znacky z 2r i po dvou opravách blikaly), pak "vyřešme to jinak, je to porád špatné... připínání to chce nějak jednodušeji.. určitě myší." Navrh (2 varianty přes AskUserQuestion) - potvrzeno: použít nástroj "Posun myší" (pravý klik = cyklení aktivní osy, levý = tažení) jako JEDINÝ mechanismus pro přikládání příslušenství. Plovoucí znacky (2r) zrušeny (setInterval(recomputeConnectionMarkerGroups) odstraněn, kód funkcí zůstává nevyužitý v souboru pro případný návrat).

**Skutečná příčina blikání u 2r** (pro poučení do budoucna): najetí myší na znacku spouštělo magnetStartPreview(), který OPRAVDU (dočasně) přesouvá child díl. Přepočet znacek běžel na setInterval bez ohledu na aktivní náhled - takže se během náhledu přepočítalo z už změněné geometrie, vyšel jiný počet/seskupení, celá vrstva se zahodila a znovu vytvořila (i znacka pod kurzorem) → mouseleave → zrušení náhledu → návrat geometrie → znovu jiný výsledek → smyčka. Dvě předchozí opravy (3D-merge 80mm, pak obrazovkový 30px-merge) řešily jen POČET překrývajících se značek, ne tenhle nezávislý zdroj neustálého DOM-churnu.

**Nové řešení** - findBestAccessorySnap(accEntry): pro TAŽENÝ neprofil (příslušenství) projde všechny ostatní profily ve scéně, pro každý spočítá kandidáty (findAccessoryToProfileCandidates, respektuje Kontrolu ploch), vybere ten s nejmenší SKUTEČNOU 3D mezerou mezi konkrétními konektory dané dvojice. Mezera < ACCESSORY_SNAP_RADIUS_MM (60mm) → kandidát na přichycení.

Napojeno přímo do existujícího tažení (žádná nová interakce/vrstva):
- startAxisMoveDrag/startTypedAxisMove si navíc pamatují startQuat (natočení při uchopení).
- updateAxisMoveDrag: při tažení PRÁVĚ JEDNÉ neprofilové entry se každý snímek díl nejdřív vrátí na volnou pozici/natočení (běžný posun + startQuat), pak se zavolá findBestAccessorySnap - v dosahu → živě (jen vizuálně, skipBookkeeping) přichytí na přesné místo/natočení; jinak zůstává na běžně posunuté pozici. Status tooltip: "🧲 přichyceno: <popisek>".
- cancelAxisMoveDrag (Escape) teď vrací i quaternion (dřív vracela jen pozici).
- finishAxisMoveDrag (puštění tlačítka): pokud bylo přichycení aktivní, TEPRVE TEĎ se zavolá applyConnectionCandidate BEZ skipBookkeeping - skutečně zaznamená spoj (jointCount/usedConn/linkJointPeers).

Ověřeno Node.js testem (8 kontrol) vč. klíčové regrese: po přichycení a následném vzdálení myši se díl správně ODEPNE (není "navždy přilepený" na první nalezenou plochu).

## 2ao. Úhelník mezi profily — POUZE dotýkajícími se, NIKDY s mezerou (2026-08-16, oprava mylného výkladu fotky)

Robert poslal referenční fotku reálné sestavy dvou profilů vedle sebe s malými úhelníkovými spojkami mezi nimi. Prvotní výklad (níž popsaný jako mylný) byl, že profily mezi sebou mají MEZERU, kterou spojka přemosťuje — na základě toho byl implementován a Node.js harnessem otestovaný nový `attach_mode` = `parallel_bridge` (`findNearestParallelBridgeFrame`, `startAutoTeachParallelBridge`, tlačítko "🌉 Most mezi rovnoběžnými profily" v panelu "Naučit napojení").

**Robert opravil (2026-08-16):** "2 rovnoběžné profily žádný úhelníkem nelze napojit, pokud jsou s mezerou" / "neexistuje spojka, která spojí 2 profily s mezerou mezi nimi" / "profily se musí vždy dotýkat". Fotka tedy zobrazovala DOTÝKAJÍCÍ SE (nebo mezerou prakticky nulovou) rovnoběžné profily, ne profily s mezerou — celý předpoklad `parallel_bridge` (mezera 5–150mm jako definiční vlastnost) byl mylný.

**Následek:** `parallel_bridge` implementace (frontend `webapp/scene.html`, i whitelist v `api/app.py` `product_attach_mode`) byla 2026-08-16 celá vrácena zpět (žádná mezera-založená detekce dvou profilů dává smysl u tohoto typu spojky) — `attach_mode` zůstává jen `corner`/`corner_side`/`corner3`/`endcap`/`wall`/`none`, beze změny oproti stavu před touto poznámkou. Node.js harness (i přes 11/11 zelených testů) ověřoval jen VNITŘNÍ konzistenci kódu vůči zadání, ne jestli zadání samo odpovídá realitě — nenahrazuje pochopení skutečné fyzické situace.

**Otevřené proto zůstává:** jak přesně (jaký `attach_mode`/mechanismus) úhelník mezi DVĚMA DOTÝKAJÍCÍMI SE rovnoběžnými profily z fotky funguje — to už může být blízké existujícímu `wall` (přímé přiložení na stěnu jednoho profilu) nebo si žádá vlastní logiku pro propojení se SOUSEDNÍM (ne kolmým) profilem. Robert (2026-08-16): "nevidím důvod proč bys nemohl vkládat do scény profily na pochopení" — další krok je editorovi POSTAVIT konkrétní sestavu (přes `custom_shapes`/DB zápis, postup 2an) a nechat Roberta ohodnotit, ne se spoléhat na výklad fotek/popisů.

**Ověřeno a potvrzeno (2026-08-16, `custom_shapes` id 158, "TEST bot8 v2" - POZOR, řádek smazán při pozdějším úklidu testovacích dat, audit bot9 2026-09-12; závěr níže nezávisle potvrzen i harness testem, viz o pár odstavců dál):** dva profily `Object_11` (40×40) vedle sebe, DOTÝKAJÍCÍ se (středy 40mm od sebe = přesně na hraně, žádná mezera), s **"Plochá spojka obdélník systém 40"** (`product_3207` NE — to je 90° rohová spojka a Robert potvrdil "nikoli tím vloženým úhelníkem"; správně `product_3318`, plochá 72,5×150×4mm destička) položenou plocho přes šev, podél délky obou profilů. Robert: "idea je ok, lze to spojit" — po 2 kolech oprav (Z: destička nesmí být zanořená do profilu, jen se DOTÝKAT jeho čelní stěny; Y: libovolná výška podél délky) potvrdil "je to ok".

**Vodítko pro budoucí přesné umístění (Robert 2026-08-16):** "spojky mají otvory, středy těchto otvorů musí sedět na středy drážek profilů" — obecné pravidlo napříč VŠEMI režimy napojení (ne jen tímhle), ne jen "dotýká se plochy". Střed drážky profilu = střed té konkrétní stěny (v ose kolmé na délku) — dnešní box-`face`-konektory (`computeConnectorsLocal`) už svůj reprezentativní bod počítají přesně takhle (`center ± faceHalf`, vždy uprostřed šířky dané stěny), takže zarovnání JEDNÉ strany spojky na JEDEN profil je touhle vlastností už automaticky správné. U spojky přemosťující DVA profily (`parallel_side` níž) ale dnes nic NEOVĚŘUJE, že i DRUHÝ konec spojky skutečně padne na střed drážky DRUHÉHO profilu (jen se dosune podél délkové osy, ne kolmo) — přesnost druhého konce zatím záleží na tom, že spojka má vlastní otvory souměrně rozmístěné vůči svému středu - je potřeba to LIVE ověřit v prohlížeči (přesná poloha otvorů uvnitř geometrie spojky se z pouhého bounding boxu nedá spolehlivě zjistit), ne jen v Node.js harnessu.

**Implementován nový `attach_mode` = `parallel_side`** ("📏 Rovnoběžné profily - z boku") — vlastní tlačítko v panelu "Naučit napojení" vedle `corner_side`. Architektura je téměř identická s dřívějším (vráceným) `parallel_bridge`, jen `profilesStillTouching` (musí se DOTÝKAT) místo mezera-rozsahu:
- `findNearestParallelSidePairFrame(objPos, maxDistMm)` (`webapp/scene.html`) — hledá dvojici profilů s rovnoběžnými osami (`|dot| > 0.98`), DOTÝKAJÍCÍCH se (`profilesStillTouching(a,b,2)`), s délkovým překryvem (`axisFootprint`); bod mostu = střed délkového překryvu (rovnoběžky nemají průsečík).
- `startAutoTeachParallelSide`/`autoTeachApplyParallelSideCandidate` — kandidáti přes `findAccessoryToProfileCandidatesAllSpins` proti profilu A (plocha přivrácená k B), po aplikaci dosunutí PODÉL osy A na `bridgeCenterlinePt` (stejná oprava jako u `parallel_bridge` — Node.js harness by jinak u nesouměrné dvojice umístil díl na nesouvisející střed délky A).
- Po potvrzení `linkJointPeers` na OBA profily (stejně jako `corner_side`).
- **Ověřeno Node.js harnessem (9/9 testů):** dotykové rozlišení (musí se DOTÝKAT, gap = odmítnuto), kolmé odmítnutí, chybějící délkový překryv, celý `startAutoTeachParallelSide` tok (přes SKUTEČNÉ produkční funkce) na nesouměrné dvojici profilů (dlouhé A + krátké B) — potvrzeno, že díl přistane u skutečného místa překryvu, ne u nesouvisejícího středu A, v první náhledu i po cyklení.
- **Mimo rozsah (jako u `corner_side`/dřívějšího `parallel_bridge`):** Place All dávková automatizace zatím nezná, jen ruční osazení přes "🤖 Automaticky vyzkoušet"; trvalá "naučená póza" (`confirmAttachTeachOffset`) zatím padá do generické (jednoprofilové) větve.

**Bug nalezený a opravený živě (2026-08-16, hlásil Robert): "porad jen na stredove ose profilu, ale to je v tomto pripade spatne".** Auto-nauč nabízel u ploché spojovací destičky (`product_3318`) všech 24 kandidátů (6 stran obálky × 4 natočení) BEZ rozlišení, která z nich je fyzicky ta rovná dosedací (tenká) plocha — Robert projel všech 24 a žádný nesedl plocho na povrch (vždy nějak zabořeno). **Potvrzeno, že jde o mezeru ve SDÍLENÉM `findAccessoryToProfileCandidates`, ne bug jen v novém `parallel_side` kódu** — i existující "🧱 Stěna profilu" magnet (jednoprofilové přichycení) dělá se stejnou destičkou to samé ("magnet ji dá na střed jednoho z profilů"). Robert: "my máme profily 2 resp 2 drážky, režim magnetu musí být malinko jiný pro 1 drážku a jiný pro 2 drážky" — tahle oprava řeší JEN `parallel_side` (Auto-nauč), obecný "Stěna profilu" magnet (`findBestAccessorySnap`, sekce 2s) zůstává nedotčen, se stejnou mezerou dál.

**Oprava #1 v `startAutoTeachParallelSide`:** místo nabízení všech `childFaceConnIdx` možností (o kterou z 4-6 ploch dílu jde) se teď vybírá PŘÍMO ta nejtenčí "face" plocha dílu (nejmenší vzdálenost bodu konektoru od středu obálky = nejmenší polovina tloušťky) — spolehlivá heuristika pro "plocha, kterou se ploché/tenké díly skutečně pokládají na povrch", bez nutnosti proklikávat nesmyslné boční hrany/konce. U `product_3318` (72,5×150×4mm) tohle zúží 24 kandidátů na 8.

**Oprava #2 (zásadnější, živě odhalena Robertem po opravě #1 - "uz jednou jsme nasli spravnou pozici ale ty porad mrdas cosi"):** oprava #1 sama o sobě nestačila - filtr rodičovské plochy profilu A vybíral tu PŘIVRÁCENOU K B (`normal.dot(toB) > 0.7`), stejný model jako jednoprofilové napojení (wall/corner_side). Jenže spojovací destička takhle nefunguje - neleží na ploše přivrácené k B (to by ji strkalo DO švu), leží PLOCHO na PŘEDNÍ stěně (KOLMÉ na osu A→B) a ŠÍŘKOU přemosťuje šev. Oprava: filtr obrácen na kolmost (`|normal.dot(toB)| < 0.3` - přední/zadní stěna), a `bridgeCenterlinePt` (cílový bod dostředění) teď zahrnuje DVA kolmé offsety od osy A - k přední stěně (Z) I k samotnému švu s B (dřív chyběl, proto výsledek zůstával "na střední ose profilu A" přesně jak Robert hlásil). Auto-nauč teď dostřeďuje do DVOU os (`axisDir` + `toBAxis`, `t.accEntry.object3d.position.addScaledVector(...)` na obě), stejný princip jako `corner_side` dostředění na průsečík os (tam 2 kolmé osy taky, jen jiný cílový bod).

**Ověřeno Node.js harnessem se skutečnou geometrií `product_3318`** (bbox parsovaný z .glb, ne obecná kostka - kostka by "nejtenčí stranu" ani švovou/přední orientaci nerozlišila): výsledný střed dílu vyšel `(20.0, 500.0, 22.0)` - PŘESNĚ odpovídá dřív ručně schválené referenci (`custom_shapes` id 158, `product_3318` na `(20, 500, 22)`), na desetiny mm.

**Oprava #3 (živě, Robert: "prave jsem ulozil spravnou pozici... zkousim jestli tam naskoci automaticky, ale lepi se dal jen na 1 profil, to uz neni mozne"):** "🎯 Uložit pozici" pro `parallel_side` dřív padalo do GENERICKÉ (jednoprofilové) větve `confirmAttachTeachOffset` - ukládalo jen skalární odsazení vůči profilu A, o profilu B nevědělo, takže se vztah k druhému profilu při jakémkoli přehrání ztratil. Doplněno:
- `parallelSideFrame(a, b)` - plný ortonormální rám švu (obdoba `cornerSideFrame`): počátek = bod na švu (stejný výpočet jako `bridgeCenterlinePt`), osy `u`=délka profilu A, `v`=směr ke švu s B, `w`=kolmá (přední stěna).
- `saveParallelSidePose(entry)` (obdoba `saveCornerSidePose`) - kóduje CELOU pózu (pozice + quaternion) RELATIVNĚ k tomuto rámu, ne skalárně vůči jednomu profilu. Napojeno do `confirmAttachTeachOffset` vedle `corner_side`.
- `runParallelSideAut(accPart, opts)` (obdoba `runCornerSideAut`) - Place All pro `parallel_side`: hledá dvojice rovnoběžných DOTÝKAJÍCÍCH se profilů (ne kolmé), přehraje naučenou pózu přes `parallelSideFrame` (nebo bez ní spadne na stejný fallback jako `startAutoTeachParallelSide`), bookkeeping (`attachedTo`/`licPeers`) na oba profily. Napojeno do Place All dispatcheru (`effMode()`/`placeAllBtn` klik).
- **Ověřeno Node.js harnessem (5/5):** encode→decode round-trip pózy reprodukuje přesně naučenou pozici na STEJNÉ dvojici profilů (0.000mm odchylka) i na JINÉ, vzdálené dvojici (Place All případ použití) - relativní pozice `(20,500,22)` vůči první dvojici správně reprodukuje `(20,500,2022)` vůči druhé dvojici posunuté o 2000mm.
- **NEVYŘEŠENO (2026-08-16, živě hlásil Robert):** Place All (`runParallelSideAut`) po uložení pózy živě "nerozezná 2 profily" ("lepí se dál jen na 1 profil"). Node.js end-to-end simulace (stejný scénář - 2 dotýkající se profily, uložená póza, `loader.load` stub) prochází čistě (`attachedTo` na A, `licPeers` na OBA A i B) - chybu se nepodařilo reprodukovat mimo živý prohlížeč. Nejpravděpodobnější příčiny k prověření příště: (a) jiný konkrétní katalogový díl než testovaný `product_3318`, (b) něco specifického ve skutečné (ne syntetické) GLB geometrii, (c) stav scény při Place All odlišný od jednoduchého 2-profilového testu. Manuální Auto-nauč cesta (bez Place All) funguje a je potvrzená.

## Stage 3 - sjednocení zápisových cest spoje (2026-08-16, částečný postup)

Systematický průzkum (fork, read-only) všech míst v `scene.html`, která zapisují do `usedConn`/`attachedTo`/`lastJoint`/`licPeers`/`jointCount` - viz plán "Čistý základ pro rozpoznávání profilů/spojů/volných ploch" (Stage 3, dřív odloženo). Nalezeno a vyřešeno:

1. **Skutečná chyba, historický zápis k 2026-08-16 (OPRAVENO audit bot9 2026-09-12: `kostkaAutPlaceForPair` byla 2026-08-17 zcela odstraněna commitem `cd8c8957`, nahrazena `corner3SolveForTriple`/`runCorner3Aut` - viz sekce 2ap níže):** kostka (rohová spojka) tvořila roh DVOU profilů (P i C), ale `linkJointPeers` se volalo jen pro P. Opraveno stejným vzorem jako `uhelnikAutPlaceForPair`/`runCornerSideAut`/`autoTeachAcceptFace`: `linkJointPeers(accEntry, C)` doplněno.
2. **Duplicitní implementace sjednocena:** `registerLicJoint` (dnes `webapp/scene.html:16575` - OPRAVENO audit bot9 2026-09-12, řádek se posunul, vnořená funkce používaná Lícováním + `autoRegisterTouchedProfileJoints`) měla svou VLASTNÍ kopii symetrického zápisu do `licPeers`, identickou s `linkJointPeers` (dnes `webapp/js/scene-geometry-shared.js:273`). Nahrazeno voláním `linkJointPeers()` - chování beze změny, jen bez duplicitního kódu na dvou místech.
3. **Ověřeno jako už kompletní** (fork je flaggoval jako "potřeba dočíst", po dočtení žádná chyba): `buildSquareFrameEntries` (používá `registerJoint` 4×, kompletní kanonický zapisovač), `uhelnikAutPlaceOne` (kompletní přes svého volajícího `uhelnikAutPlaceForPair`), `handleEndpointClick` (extra zápis je záměrný, komentářem zdůvodněný).
4. **Vědomě NEuděláno teď** (nižší priorita, čistě kosmetické, žádný aktivní bug): sjednocení ~8 míst, která ručně skládají identický tvar objektu pro `attachedTo`/`lastJoint` do sdílené konstruktor-funkce. `attachEntryToParent` vs `registerJoint` nejsou skutečný duplicát (různá úroveň abstrakce - `attachEntryToParent` počítá i geometrickou pozici, `registerJoint` jen zapisuje bookkeeping pro už umístěný pár) - není potřeba sjednocovat.

## Systematické ověření všech ~17 cest (2026-08-16, fork s Node.js harnessem)

Na Robertovu výzvu ("znáš snad už celý systém spojování profilů?") - fork skutečně SPUSTIL (ne jen staticky přečetl) 16 z 17 konstrukčních/umísťovacích funkcí proti syntetickým scénám a ověřil invarianty (`licPeers` symetrie, `lastJoint` platnost, `jointCount` správnost, propojení příslušenství s OBĚMA profily). **16/16 spustitelných testů PROŠLO.** Vedlejší (nebugový) poznatek k zapamatování: `lastJoint` je záměrně jen "poslední spoj", ne úplný registr - u dílu se 3+ fyzickými spoji (např. průchozí profil prostorového L, roh čtvercového rámu) drží jen JEDEN z nich, `licPeers` (ověřeno úplné/symetrické ve všech testech) nese celou množinu. Důsledek: R-cyklení (`stepProfileJoint`) na takovém dílu procyklí jen jeho POSLEDNÍ vytvořený spoj - na starší spoj je nutné R-cyklovat z DRUHÉHO dílu toho spoje.

**Nalezena a opravená skutečná chyba, nikdy historicky neověřená:** `runCorner3Aut` (roh 3 navzájem kolmých profilů, `corner3SolveForTriple`) - v celém `AGENTS_LOG.md` je na `corner3` jen jedna letmá zmínka, žádné potvrzení živého testu (na rozdíl od `kostkaAutPlaceForPair`, to Robert vizuálně kontroloval - "L/ram -> Kostka -> piny uvnitr, vne presne krychle PROHLIZECI"). Přesný matematický test (3 vzájemně kolmé profily stejného průřezu, plochy vně zarovnané - reálná konstrukce hliníkového rohu) vyšel s odchylkou ~170mm proti toleranci 55mm - `runCorner3Aut` by takovou kostku tiše přeskočil, neosadil, i kdyby byla umístěná fyzicky správně.

**Příčina:** `corner3SolveForTriple` požadoval, aby bod na konci profilu (jeho střední osa) a bod na ploše kostky po transformaci PŘESNĚ splynuly (pozice = průměr ze 3 nezávisle spočítaných "T" posunů) - u reálného rohu (plochy vně zarovnané, osy profilů OFFSETNUTÉ o polovinu průřezu, ne sbíhající se v jednom bodě) tenhle požadavek systematicky selhává i u geometricky správně umístěné kostky.

**Oprava:** pozice se teď počítá PŘESNĚ ze 3 rovinných podmínek (bod na ploše kostky leží v rovině konce profilu, kolmé na jeho osu - ne v přesně daném bodě té roviny) místo průměrování 3 nezávislých odhadů - `dir0/1/2` tvoří ortonormální bázi, žádný residual pro pozici není potřeba, řeší se přesně. `residual` teď měří jen KOLMOU odchylku (v rovině konce profilu) bodu na ploše dílu od střední osy profilu - u fyzicky správně umístěné kostky odpovídající průřezu profilu je tahle odchylka OČEKÁVANÁ a nenulová (osa profilu je od skutečného vnějšího rohu offsetnutá o polovinu průřezu), ne chyba. Tolerance v `runCorner3Aut` proto přepočítána z `průřez+15mm` (moc těsné pro nový význam residualu) na `5×průřez+15mm`.

**Ověřeno Node.js harnessem** (3 scénáře): syntetická symetrická 40mm kostka na 40×40 profilech (residual 169.71mm, tolerance 215mm → PROJDE), SKUTEČNÁ geometrie "30 x 30 Rohová spojka kostka" `product_3345.glb` na 30×30 profilech (residual 133.64mm, tolerance 165mm → PROJDE), a kontrolní "odpadový" scénář (500mm nesmyslně předimenzovaná kostka, residual 1145mm → správně ODMÍTNUTO, tolerance není nekonečně benevolentní).

## Systematické učení katalogových dílů (2026-08-16, `attach_mode`)

Robertova výzva odhalila, že 419 z 432 katalogových dílů (příslušenství s GLB, ne profily/desky) nemělo vůbec nastavený `attach_mode` - fakticky neznámé chování pro drtivou většinu katalogu. Postupná bezpečná klasifikace podle jména (přímý zápis do `shop_products.attach_mode`, žádná hádaná geometrie - jen kategorie, kde je název jednoznačný a cílový režim už má ověřené chování):
- **`endcap`** (50 ks) - "záslepka"/"krytka profilu" - jen zaznamenává chování, které už fakticky platí přes `isEndCapPart()` heuristiku podle jména (žádná změna chování, jen zápis explicitní).
- **`none`** (176 ks) - čistě spojovací/pomocný materiál (šrouby, matice, těsnění, krycí lišty, magnety, vrtací přípravky...) - dřív by omylem spadly do výchozího "corner" chování při Place All, teď explicitně "jen ručně".
- **`corner_side`** (28 ks) - rodina "rohová spojka"/"úhelníková spojka" (2 kolmé dotýkající se profily) - stejný, dnes už dobře ověřený mechanismus jako referenční "Úhelníková spojka 40x40" (sekce 2q, 36 kandidátů matematicky ověřeno).
- **`none`** (29 ks, druhé kolo) - panty (rotační kloub, žádný existující režim to nepokrývá) a "Spojovací kus 120°/135°" (ne-90° úhel, žádný existující režim).
- **Zbylých 136 ks nejasných** (spojovací desky 2/4-way, patky, madla, konzole, klouby, vzpěry, kluzáky...) dostalo **`none`** jako bezpečný výchozí stav - NE protože by šlo o čistě ruční díly navždy, ale protože jejich přesný způsob napojení (která plocha, jaká geometrie) není z názvu ani rozměrů spolehlivě odvoditelný bez rizika stejné chyby jako `parallel_bridge`/`kostka` dřív (viz [[feedback_physical_hardware_verification]] princip). `none` je striktně lepší než `NULL` (ten dřív tiše padal na "corner", věcně špatně pro 99 % z nich) - žádný díl v katalogu už nemá skryté špatné výchozí chování. **Výsledek: VŠECH 432 katalogových dílů má teď explicitní `attach_mode`, nic už nezůstává neznámé/tiše špatné - Robertova výzva "znáš snad už celý systém?" má teď jednoznačnou odpověď pro každý jednotlivý díl** (buď ověřený automatický režim, nebo vědomé "zatím jen ručně, dokud se ověří jak"). Zvýšení kterékoli z těch 136 na konkrétní režim čeká na živé ověření (postup: 2ao/2an - postavit konkrétní testovací sestavu, nechat Roberta ohodnotit výsledek).

## Postupné zvyšování z `none` na ověřený režim (2026-08-16, bot8, pokračování)

Robertova výzva "gogo" - postupně, dávka po dávce, procházet těch 136 nejasných dílů a ověřovat, kde to jde. Postup vždy stejný: (1) najít rodinu podle jména, (2) porovnat geometrii (bbox rozměr/tvar/poměr stran) s už OVĚŘENOU referencí stejné třídy, (3) nechat díl reálně umístit produkční funkcí (`findAccessoryToProfileCandidatesAllSpins`/`applyConnectionCandidate` pro `corner_side`/`endcap`, `corner3SolveForTriple` pro `corner3`) a změřit dosednutí/průnik - ne jen věřit podobnosti jména.

**Zapsáno (`attach_mode`, vše ověřeno reálným umístěním proti referenci):**
- **9 patek** (chromované/plastové M6-M16, kovová, vyrovnávací) → `endcap` - rotačně souměrné šroubovací bloky, stejná třída jako referenční "Kovová patka M8x50" (3368). Ověřeno: 10/11 testovaných dosedne na čelo profilu přesně 0.00mm, žádný průnik. Výjimka "Chromovaný stojánek M10" (3360, zajíždí 9.4mm do profilu) ponechána `none`.
- **Plochá spojka obdelník systém 45** (3357) → `parallel_side` + `attach_pose` - stejná rodina jako referenční systém 40 (3318). Ověřeno: chová se identicky (deska přesně na švu 2 rovnoběžných profilů, 0.00mm mezera, symetrický překryv).
- **7 dvoucestných spojovacích desek** → `corner_side` - stejná rodina jako referenční "Dvoucestná spojovací deska 40X40" (3276, i s pózou). Póza (`attach_pose`) přenesena jen pro ověřenou velikost 45x45 (3295).
- **5 čtyřcestných spojovacích desek** → `wall` - stejná rodina jako referenční "Čtyřcestná spojovací deska 40x40" (3329).
- **4 "Dvoucestná hranatá rohová spojka"** (3328, 3361, 3369, 3371) → `corner_side` - tvarem (kompaktní kostkovitý blok, ne plochá deska) odpovídá referenčnímu úhelníku (3207), ne rodině spojovacích desek. Ověřeno: chová se v testu identicky jako referenční úhelník (stejný poměr "střed vs roh" ku průřezu).
- **4 "Třícestná hranatá rohová spojka"** (3319, 3376, 3365, 3378) → `corner3` - kostkovitý tvar odpovídající referenční kostce (3345). Ověřeno `corner3SolveForTriple` s reálnou geometrií: mezera k profilům ~0mm, minimální průnik (2mm u dvou 40mm kusů, srovnatelné s referenčním přesahem).

**Tvrdý strop, na který jsem narazil - `attach_pose` NEJDE odvodit z geometrie, `attach_mode` ano:** zkoušel jsem přenést naučenou pózu spojovací desky mezi velikostmi (40→45→30) přes změřený kanonický rám (osa tloušťky + střed bboxu, nezávislý na tom, jak má konkrétní GLB pootočené/posunuté lokální osy - katalogové GLB nemají jednotnou konvenci, viz [[reference_konfigurator_glb_nekonzistence]]). Zlepšilo to zapadnutí do profilu (30mm → 3.4mm), ale nedostalo se to na nulu - správné odsazení desky totiž není dané jejím tvarem, ale ROZTEČÍ DĚR, kterými se šroubuje do drážky profilu, a to z bounding boxu změřit nejde. `attach_mode` (rodina + ověření reálným umístěním) je proto spolehlivě odvoditelný, `attach_pose` musí zůstat naučená ručně přes 🎯 pro každou velikost zvlášť.

**Vědomě NEklasifikováno** (žádná rodina s dostatečnou jistotou): panty/klouby (19+4 ks, rotační spoj, žádný existující režim to nepokrývá), madla (8 ks, nejednotný tvar - trubkové 232mm mezi 2 úchyty vs. kompaktní bloky, bez spolehlivého geometrického testu), "spojovací kus 120°/135°" (ne-90°, žádný režim), "vnitřní rohová spojka v drážce" (malý dílek zapadající PŘÍMO do drážky profilu, jiný způsob upevnění než face-mount).

## Oprava rozsahu + druhé kolo (2026-08-16, bot8, Robertovo "chci napojit automaticky co nejvíc prvků")

**Důležitá oprava dřívějšího čísla:** "432 katalogových dílů" v zápisech výše bylo počítáno jen podle `glb_file IS NOT NULL`, BEZ `visible_in_scene`. Skutečný počet dílů, které se vůbec můžou objevit ve 3D scéně (`fetch_katalog_parts`/produktová větev v `api/app.py`, `WHERE visible_in_scene=1 AND glb_file IS NOT NULL`), je **115** (113 po odečtení 2 deskových materiálů, které nejdou přes `attach_mode` vůbec, mají vlastní `computeBoardEdgeConnectors` systém). Zbylých ~320 dílů má sice model, ale je v katalogu vypnuté - `attach_mode` u nich je bezpředmětný.

Na tomhle skutečném rozsahu (113 dílů) druhé kolo klasifikace - postup stejný jako předtím (rodina podle jména + reálné umístění přes produkční funkci, ne odhad):

- **5 dílů** → `corner_side`: chybějící "Třícestná spojovací deska" (20x25/40x40/45x45/45x90) - přehlédnutý sourozenec už hotové dvoucestné/čtyřcestné rodiny - a "Plochá spojka T systém 30". Ověřeno přes `findAccessoryToProfileCandidatesAllSpins`/`applyConnectionCandidate` v rohu 2 profilů - chová se identicky jako referenční dvoucestná deska (3276).
- **8 dílů** → `endcap`: "Vnitřní rohová spojka v drážce" (6/8/10mm) - PŘEKVAPENÍ, dřív odhadnuto jako "zapadá přímo do drážky" (jiný mechanismus), realita: dosedne přesně na čelo profilu (0.00mm mezera/průnik) jako běžná záslepka. "Upínač patky"/"Upevňovací kus patky" rodina (30x60/45x90/k podlaze 45x45/45x90) - taky čisté dosednutí na čelo.
- **13 dílů** → `endcap` po filtrování: širší dávka ~24 kandidátů prošla geometrickým testem (0mm mezera/průnik), ale ne všechny byly SPRÁVNĚ - položky, jejichž JMÉNO říká "posuvné"/"kluzák"/"sada magnetů"/"drážka" (jezdec v drážce, pozice kdekoli podél profilu, ne fixně na konci) i přes čistý geometrický fit vyloučeny, protože `endcap` by je vnucoval na KAŽDÝ volný konec při Place All - fyzicky nesmyslné pro díl, který se má dát libovolně podél profilu. Stejně vyloučeny dlouhé pásy/hadičky/lišty (U lišta 3000mm, těsnicí kanálek/páska - montují se podél drážky) a "Plynová vzpěra" (391mm, spojuje 2 body, nekryje jeden konec). Ponecháno: bezpečnostní zámek, držák plexiskla, kloub s aretací, krycí guma (kus, ne pás), plastové madlo se zarážkou (NE "posuvné madlo" - to vyloučeno), spojovací kus plynové vzpěry, stavitelná/naklápěcí úhlová konzole, závěsná sada, zavěšovací vidlice.

**Výsledek k 2026-09-10: 87/113 (77 %) skutečně adresovatelných dílů katalogu má teď funkční automatický režim** (40 endcap, 31 corner_side, 7 wall, 7 corner3, 2 parallel_side), zbylých 26 zůstává `none` oprávněně - buď jezdci/spotřební materiál v drážce (pozice volitelná uživatelem, ne fixní bod), nebo 45° spojky (jiná geometrická třída, žádný existující režim), nebo díly, které geometrickým testem na `endcap` neprošly (skutečná mezera/průnik, ne jen odhad).

**POZOR (ověřeno audit bot9, 2026-09-12): katalog má dnes 122 viditelných dílů (narostl), 8 s `attach_mode IS NULL`** - 3 deskové materiály (v souladu s výjimkou výše) + **5 nových dílů bez klasifikace** (`eurobox_400x300x120/170/220/270/320`, `shop_products.id` 3788/3793/3794/3795/3796). Před spoléháním na "VŠECH X dílů má attach_mode" ověřit živě a nové díly doklasifikovat.

## Pravidlo profilů - montážní plocha plochého příslušenství se nesmí odvozovat z "nejdelší osy" (2026-08-19, POTVRZENO Robertem, nalezeno matematickou kontrolou automatického osazování)

Robert: "zkontroluj hloubkově matematiku všeho" - hloubková numerická kontrola (skutečná `.glb` geometrie, změřený dotyk) všech automatických umísťovacích funkcí příslušenství ("Place All").

**Nalezeno (Node.js reprodukce se skutečnou geometrií):** bez ruční kurace (`shop_products.accessory_conn_enabled = NULL`, tj. díl ještě neprošel "Kontrolou ploch") bral `runZaslepkaAut`/`runWallAut` prostě PRVNÍ geometricky platný kandidát (`cands[0]`). U ELONGOVANÝCH dílů (jako profily) to náhodou vychází správně - "end" konektory (0/1, vybírané podle NEJDELŠÍ osy obalky, viz `computeConnectorsLocal`) SKUTEČNĚ jsou montážní plocha. Ale u PLOCHÝCH/nepodlouhlých dílů (záslepka, spojovací deska) je "nejdelší osa" NÁHODNÁ volba mezi skoro stejnými rozměry (např. záslepka 30×30×9mm - 30 a 30 jsou "delší" než 9, ale která z nich vyhraje tie-break, je implementační detail) - "end" konektor tak často vůbec neodpovídá skutečné montážní ploše (tou je vždy ta NEJTENČÍ - u záslepky 9mm strana, u ploché desky nejtenčí rozměr).

**Ověřeno přímo na reálné geometrii:**
- "Záslepka 30x30" (`product_3071.glb`, bbox 30×30×9mm): bez opravy dosedla jen 9mm z 30mm šířky - reálné částečné zaboření. Po opravě: `overlap=30.0000mm` přesně.
- "Čtyřcestná spojovací deska 30x30" (`product_3316.glb`, bbox 150×150×3mm): bez opravy jen 3mm z 150mm. Po opravě: `overlap=150.0000mm` přesně (omezeno na 30mm na ose profilu, správně - menší plocha profilu je celá podmnožinou větší plochy desky).

**Oprava:** sdílený helper `accessoryThinFaceIdx()` (`webapp/scene.html`) - mezi FACE-kind konektory dílu (NIKDY "end", to je právě ten nespolehlivý výpočet) preferuje ten s konektorovým bodem NEJBLÍŽ středu obalky dílu (= nejtenší rozměr = typicky skutečná montážní plocha). Stejný princip už měla `runParallelSideAut` (`thinFaceIdx` tam, fungovalo spolehlivě) - jen vytažený do sdílené funkce a použitý i v `runZaslepkaAut`/`runWallAut`. Bezpečné pro už kurírované díly: při existenci geometricky potvrzených ploch (`isGeoFace`) se nová logika vůbec nespouští; při existenci `accessory_conn_enabled` indexového seznamu jen PREFERUJE mezi již platnými kandidáty (nikdy nerozšiřuje mimo kurírovanou množinu).

**Co NEBYLO potřeba opravovat:**
- **`corner_side`** (úhelníky/rožky, `runUhelnikAut`) - ověřeno dnes numericky přímo (naučená poza z DB + reálný profil s pivot-offsetem `profil_30x30_uzavreny.glb` + reálná geometrie úhelníku `product_2895.glb`) - `gap=0.0000mm`/`overlap=0.0000mm` přesně na obou profilech rohu, bez chyby. Tenhle mód má vlastní naučenou pozici (`uhelnik_pose`), takže nespoléhá na naivní `cands[0]`.
- **`corner3`** (3-cestná kostka, `runCorner3Aut`/`corner3SolveForTriple`) - už dřív hloubkově ověřeno (16.8.2026, viz komentář přímo u `runCorner3Aut`) na skutečné geometrii `product_3345` - tolerance byla tehdy přímo přepočítaná podle výsledků Node.js testu. Nebylo potřeba opakovat.

**Obecné poučení pro budoucí kód:** `computeConnectorsLocal`'s "end" konektory (0/1) jsou definované jako NEJDELŠÍ osa obalky - to je spolehlivé kritérium pro PROFILY (skutečně podlouhlé), ale NÁHODNÉ/nespolehlivé pro PŘÍSLUŠENSTVÍ, které často není podlouhlé (ploché desky, kostky, záslepky). Kdykoli kód u příslušenství potřebuje "najít montážní/dosedací plochu" bez ruční kurace, použij `accessoryThinFaceIdx()` (FACE-kind konektor nejblíž středu = nejtenší rozměr), ne implicitní spoléhání na index/pořadí konektorů.

## Pravidlo profilů - runtime výběr montážní plochy příslušenství: MĚŘIT, ne odhadovat (2026-08-19, bot8, rozšíření pravidla o "nejtenčí ose" po systematickém ověření celé endcap/wall rodiny)

Pravidlo "montážní plocha plochého příslušenství ≠ nejdelší osa" (výše)
zavedlo `accessoryThinFaceIdx()` (nejtenčí "face" konektor) - ověřené
tehdy na 2 referenčních SKU. Systematický batch přes VŠECH 94
endcap/wall dílů katalogu (reálná .glb geometrie, přesná kopie produkční
logiky - `scripts/2026-08-19_endcap_wall_batch_check.js`) ale ukázal, že
i tahle heuristika selhává na 23 dílech: u NEPRAVIDELNĚ tvarovaných dílů
(patky, konzole, spojky-v-drážce, vidlice, radius záslepky) je skutečná
dosedací plocha často vlastní **"end" konektor** dílu (podélná osa),
který heuristika (jen kind==="face") vůbec neprohledává - a u
asymetrických tvarů může "bod nejblíž středu obálky" vybrat i špatnou
face plochu.

**Pravidlo:** kdykoli se automaticky vybírá montážní plocha
příslušenství bez kurátorovaných dat (geo_faces), NEODHADOVAT ji z
tvaru obálky - KAŽDÉHO kandidáta skutečně aplikovat (skipBookkeeping)
a ZMĚŘIT dotyk (gap/overlap na všech 3 osách; platný = přesně 1
dotyková osa + 2 osy plného překryvu). První měřením potvrzený flush
vyhrává. Implementace: `bestFlushAccessoryCandidateIdx()`
(webapp/scene.html, používá runZaslepkaAut + runWallAut);
`accessoryThinFaceIdx` zůstává jen jako záložní síť. Je to tentýž
princip jako "pivot ≠ střed - měř skutečnou hranu", jen aplikovaný na
runtime výběr místo stavby tvaru.

**Vedlejší poučení o naučených datech:** `attach_offset_mm` je vázaný
na KONKRÉTNÍ zvolenou plochu - když se výběr plochy opraví, offset
naučený pro starou plochu se stává škodlivým (posouvá díl přesně o
svou hodnotu mimo flush). Při každé změně výběrové logiky zkontrolovat
i uložené offsety dílů, kterých se změna týká (3315/3368/3081/3404
vyčištěny, záloha v backups/). Stejně tak nepřesná auto-detekovaná
geo_faces (3221/3151 vrácena na NULL - géo cesta má přednost před
měřením, takže špatná uložená plocha měřenou pojistku obchází).


## Node.js portování `uhelnikAutPlaceForPair`/`uhelnikAutPlaceOne` - `computeConnectorsLocal` musí běžet PŘED umístěním dílu (bot16, 2026-08-31)

Při aplikaci úhelníků na regál na euroboxy od přepážky (viz `KOMPONENTY_EUROBOXY.md`) byla celá logika "⟂ Automat → Úhelník" (`uhelnikAutPlaceForPair`, `uhelnikAutPlaceOne`, `findAccessoryToProfileCandidates(AllSpins)`, `uhelnikCornerFrameQuat`, `applyFaceToFaceCandidate`, `geoFaceSnapToCornerWalls`, `uhelnikLugAlignToSlots`) portována 1:1 do Node.js nad reálnou geometrií a reálnými daty z DB - stejný princip jako `webapp/js/scene-geometry-shared.js` (sdílený zdroj mezi prohlížečem a botem), jen dosud nepřesunuto do sdíleného souboru (zůstává jako jednorázový skript `scripts/tmp_2026-08-31_uhelniky_leg_joints.js`).

**Past nalezená při portování:** `computeConnectorsLocal(obj, opts)` bere `Box3().setFromObject(obj)`, což je SVĚTOVÝ bounding box AKTUÁLNÍ transformace objektu (ne nezávislý na pozici/rotaci/škále, jak by název "Local" mohl naznačovat). Živá scéna proto VŽDY volá `computeConnectorsLocal` na čerstvě načtené síti PŘED nastavením `position/quaternion/scale` (viz `loadCustomShapePartEntry`, `uhelnikAutPlaceForPair` - `computeConnectorsLocal(objFirst, ...)` hned po `gltf.scene`, teprve pak se objekt umísťuje) - konektorové body se tak počítají v "domovském" rámu dílu (nulová pozice, identitní rotace, ale SE započtenou vlastní škálou daného dílu, což správně zohlední i různě dlouhé instance stejného profilu). Teprve `worldConnectorsOf()` tyhle body transformuje přes `matrixWorld` DO aktuální pozice/rotace.

**Důsledek chyby:** první verze portu počítala `computeConnectorsLocal` AŽ PO `obj.position/quaternion/scale.set(...)` - `Box3` tak zachytil UŽ TRANSFORMOVANOU geometrii, `worldConnectorsOf` transformaci aplikoval PODRUHÉ, a výsledné "osy" všech profilů vyšly falešně rovnoběžné (obě legy ukazovaly světovou osu Y bez ohledu na skutečnou orientaci) - 0 spojů nalezeno místo očekávaných 21. Oprava: přehodit pořadí (`computeConnectorsLocal` před `.set(...)`), přesně jak to dělá scéna. **Poučení pro příští portování jakékoli funkce závislé na `connectorsLocal`:** vždy zkontrolovat POŘADÍ volání vůči umístění objektu, ne jen SPRÁVNOST vzorce uvnitř funkce.

## Zobecnění na znovupoužitelnou METODU `uhelniky-na-spoje-nohy` (bot16, 2026-09-01)

Robert: "naučit se vkládat úhelníky na nohy" - jednorázový port výše (na konkrétní, dnes už smazanou sestavu `id=47`) byl přepsán do obecné, parametrické metody, zapsané do `shape_geometry_methods.id=7` (`uhelniky-na-spoje-nohy`, verze 1). Funguje nad JAKOUKOLI množinou profilů jedné nohy (libovolný průřez, libovolný tvar - `plain` i `vyrez`), ne jen nad jednou konkrétní sestavou:

- **Reusable engine:** `scripts/2026-09-01_uhelniky_leg_joints_lib.js` - modul (ne skript), exportuje `findLegInternalJoints`/`cornerGeometry`/`applyUhelnikyToLeg` + všechny ported dílčí funkce jednotlivě (stejné jméno a chování jako ve `webapp/scene.html`, k 2026-09-01 verzi kódu - mezitím přibylo `applyConnectionCandidate`/`uhelnikAutGetPose` jako obálky, samotná matematika beze změny).
- **DB katalogový lookup:** `scripts/2026-09-01_fetch_uhelnik_catalog.py` - stejný filtr jako živé `uhelnikAutPart()` (SKU suffix `.01`, `attach_mode='corner_side'`, `sizes` odvozené stejným algoritmem jako `partCompatMeta()`), dumpne do `scripts/2026-09-01_uhelnik_catalog.json`. Katalog má (2026-09-01) **3 velikosti**: `product_3045` (30×30), `product_3207` (40×40), `product_3216` (45×45) - poslední dvě mají `uhelnik_pose`/`geo_faces_json` odvozené a živě ověřené už dřív (bot8, 2026-08-20, commit `f04dc9b`), tahle metoda je jen znovupoužívá.
- **Ověřeno** (`scripts/2026-09-01_uhelniky_leg_joints_verify.js`) na 4 nohách: `30×30 plain` a `30×30 vyrez` (obě D=326mm, přesně `buildPlainAtDepth`/`buildVyrezAtDepth`), `40×40` a `45×45` (syntetické, nikdy neuložené do DB, stejná "plain" šablona přeparametrizovaná na jiný profil) - u všech 4 nulová kolize mezi profily nohy, 0 NaN, správný katalogový díl podle skutečné velikosti profilu (žádné tiché dosazení špatné velikosti), a nezávisle změřená odchylka označených dosedacích ploch od stěn rohu ~0mm (řádově 1e-13mm, numerický šum). Detaily viz `shape_geometry_methods.id=7`.
- **Mimo rozsah** (jako u prvního portu): rámová konstrukce lůžka (nosníky+spojnice MEZI nohami) - stejná metoda, jen spuštěná na jiný seznam profilů (`findLegInternalJoints`/`applyUhelnikyToLeg` neví nic o "noze" jako konceptu, jen o seznamu profilů, který jí předáš). "Rožek" (SKU suffix `.33`) záměrně není součástí (jiná produktová řada, byť stejný mechanismus).

## Pravidlo profilů - kolizní úhelníky: kritérium je PRŮNIK HMOTY, ne pozice

**Verze 3 (Robert 2026-09-11).** Doslova: *„Je jasné že různé auta mají různé
tvary takže pokud se vyskytne kolizní úhelník tak nemusí mít stejnou pozici
jako v doublu."*

Tím se ruší dosavadní dvojí podmínka *„průnik A SOUČASNĚ dole v noze"*.
Kritérium je nově **čistě geometrické**: úhelník je kolizní, když se jeho
hmota překrývá s hmotou jiného dílu sestavy. **Kde na sestavě sedí, na
verdiktu nemění nic** — jiná karoserie má jiný tvar, takže tatáž vada sedí
pokaždé jinde a „stejná pozice jako v Doblu" nemůže být kritérium.

Vyplývalo to už z měření k verzi 2, které je zapsané níže: „dole" a „jinde"
je **tatáž vada** a pravidlo mazat jen kusy dole nemělo fyzikální oporu.
Drželo se jen proto, že tak znělo zadání. Robert to teď rozhodl.

### Co se s nálezem dělá

Robert 2026-09-11: **„Napřed mi je ukázat."** Nález se tedy **nemaže
automaticky**. Sweep vyrábí výpis k posouzení kus po kuse a rozhoduje
se u každého zvlášť. Jediná výjimka je skupina, kterou Robert už
odsouhlasil dřív (24 kusů dole v nohách, viz níže).

**Důsledek pro generátor** (beze změny od verze 2): metoda `id=7` smí
vyprodukovat úhelník, který se pak zahodí. Není to její chyba a **nemá se
„opravovat" tak, aby úhelník vznikl jinde** — kontrola kolize patří až ZA
generování, jako filtr.

### Proč výška nikdy nefungovala (změřeno, ne odhadnuto)

Kalibrace na dvou kusech, které Robert 2026-09-10 u vzoru Dobla C nechal
smazat (`backups/2026-09-10_pred_oznacenim_uhelniku.json`, sestava 337):

```
Y=31.5   4 úhelníky  PONECHANÉ  (níž než smazané!)
Y=53.5   1 úhelník   PONECHANÝ  (stejná výška jako smazané)
Y=53.5   2 úhelníky  SMAZANÉ
```

Žádná vodorovná rovina ty dvě skupiny neodděluje. Odděluje je jen to, jestli
se hmota překrývá.

### Jak se kolize měří (verze 3: na síti, ne na obalu)

`Box3` přesah je od verze 3 jen **předfiltr**, ne verdikt. Je to horní mez
skutečného průniku (posun o něj obaly oddělí, takže oddělí i díly), takže co
jím neprojde, kolidovat nemůže — ale co jím projde, kolidovat ještě nemusí.
Důvod je past č. 8 ze skillu `3d-scena-spoje`: u dílu s vnořovací geometrií
(eurobox s vybráním na nožce) obal přesah má a hmota se nepřekrývá. Navíc je
obal **osově zarovnaný**, takže u pootočeného dílu nadhodnocuje — a pootočený
je v těchhle sestavách skoro každý vodorovný panel.

Verdikt dává `scripts/2026-09-11_mesh_kolize_lib.js`: prostor, kde se obaly
překrývají, se navzorkuje a hledá se bod ležící uvnitř **obou skutečných
sítí**. Doplňkově se testuje průnik stěn (SAT nad dvojicemi trojúhelníků),
aby neunikl překryv tenčí než krok mřížky.

**Velikost kolize se hlásí dvěma čísly, protože jedno nestačí:**

- **`odsun`** — nejmenší posun po světové ose, po kterém se sítě přestanou
  překrývat. To je odpověď na „o kolik je zabořený" i na „šlo by to spravit
  posunutím".
- **`oblast`** — rozměry společné hmoty `[dx,dy,dz]`. Popisuje, JAK se
  překrývají.

⚠️ **Hloubkou NENÍ nejmenší rozměr společné hmoty.** U úhelníku, jehož stěna
projde skrz profil, je nejmenší rozměr překryvu roven **tloušťce plechu
úhelníku (6 mm)** — a ta je stejná, ať je zabořený o 7 mm nebo o 22 mm.
Změřeno 2026-09-11: společná hmota je `6 × 18 × 28 mm` u sestavy #79 a
`6 × 22 × 28 mm` u #116; první číslo je pořád plech, liší se druhé.
Stejně tak hloubkou není „nejhlouběji zanořený vrchol" — díly sestavy sdílejí
roviny (flush dosed je účel spoje), takže vrcholy zabořeného dílu leží přesně
NA stěně toho druhého a vzdálenost od povrchu vyjde 0, i když se objemy
překrývají. Obě pasti jsou zavřené regresním testem
`scripts/2026-09-11_test_mesh_kolize.cjs`.

**Regresní test je vázaný na Robertovu odpověď, ne na naši představu:** ze
sestavy 337 musí vybrat právě ty DVA úhelníky, které Robert nechal smazat —
ani míň (slepý test), ani víc (mazal by kusy, co drží). Spusť ho po každé
změně knihovny; musí skončit „VSECHNY KONTROLY OK".

### Co měření na síti změnilo (a co ne) — 2026-09-11, celý katalog

Rozsah: **269 sestav, 263 s úhelníky, 5 164 úhelníků, 472 185 porovnaných
dvojic.** Předfiltrem obálek prošlo **76 dvojic**, síť potvrdila kolizi
u **všech 76**. Jde o **60 úhelníků ve 22 sestavách** — 16 z nich koliduje
se dvěma díly naráz.

**Množinu nálezů tedy síť nezměnila; změnila čísla, a to zásadně.**
Přesah obálek šel od 5 do 22 mm a vypadalo to jako různě vážné vady.
Skutečný odsun potřebný k rozpojení je u všech 60 kusů **4,96 až 5,95 mm**:

| přesah obálky | 5 mm | 6 mm | 7 mm | 18 mm | 20 mm | 22 mm |
|---|---|---|---|---|---|---|
| kusů | 6 | 24 | 4 | 14 | 6 | 6 |
| **skutečný odsun** | 4,96 | 5,95 | 5,27 | 5,27 | 5,27 | 5,27 |

Čtyřnásobný rozdíl v obálce, tři různé hodnoty ve skutečnosti. Obálka
nadhodnocovala podle toho, JAK DALEKO na profilu úhelník sedí, ne podle
toho, jak hluboko je zabořený — u #116 sdílí úhelník s příčkou dokonce
tutéž hranu v X, takže obálka hlásila 22 mm a stačí ho posunout o 5,3 mm
a je venku.

**Je to tedy jedna a tatáž vada posazená pokaždé jinam** — přesně to, co
Robert řekl o různých tvarech karoserií, a nezávislé potvrzení, že pozice
kritérium být nemůže.

⚠️ **Past č. 8 se v tomhle katalogu neprojevila** — žádný přesah obálky
nebyl planý poplach. To je ale nález, ne důvod se na obálku vrátit:
obálka tady dala správný VERDIKT a špatná ČÍSLA. Že se ta past umí
projevit, drží zavřené regresní test se zasouvací geometrií (drážka
+ lišta): obálky se překrývají o 20 mm, hmota vůbec.

### Stav k 2026-09-11

Sweep: `scripts/2026-09-11_sweep_kolizni_uhelniky.cjs` (nic nemaže),
výpis k posouzení: `scripts/2026-09-11_report_kolizni_uhelniky.cjs`.

- **24 kusů** (#182, #189, #219, #289) koliduje výhradně s díly **starých
  horních bloků**, které jsou na seznamu ke smazání — po tom úklidu
  zaniknou bez zásahu a samostatné rozhodnutí nepotřebují.
- **36 kusů** v 18 sestavách čeká na Robertovo posouzení kus po kuse.
  Z toho **30 kusů „nemá kam ustoupit"** (žádný posun do 40 mm kolizi
  neodstraní, aniž by úhelník přišel o dosed) a **6 kusů** (T6, sestavy
  #116/#117/#250/#251/#320/#321) by vyřešil posun o 29 mm po ose Z.
- Skupina 24 kusů dole v nohách, odsouhlasená bot8 ještě podle pravidla v2,
  je podmnožinou těch 30 „bez ústupu" a čeká na ostrý běh
  `scripts/2026-09-11_smazat_kolizni_uhelniky.py`. **POZOR (ověřeno audit
  bot9 2026-09-12): skript se dnes sám odmítá spustit** ("odsouhlaseny
  rozsah uz neodpovida datum - NEMAZU NIC", `TOLERANCE_MM=0.2`) - 9 z 12
  sestav ze seznamu (79,83,151,152,173,210,224,280,294) se mezitím
  posunulo. Před ostrým během je nutné rozsah přegenerovat
  (`scripts/2026-09-11_sweep_kolizni_uhelniky.cjs`) a znovu odsouhlasit.
  Zbylých 6 kusů „bez
  ústupu" jsou T6 `-475|…` a odsouhlasené nejsou.
