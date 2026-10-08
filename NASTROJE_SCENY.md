# Nástroje ve scéně (výběr/tažení/magnet/cyklení)

Interaktivní nástroje 3D scény: volné pozicování, magnet/snap, lícování, cyklení ploch a konců, UI menu/barvy/export, a architektura sdíleného zdroje geometrie (`scene-geometry-shared.js`) mezi scénou a Node.js. Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31.

## Index (doplněno 2026-08-31, po testu ukázalo, že bez indexu se klíčová sekce najde jen přečtením celého souboru)

⚠️ **OPRAVENO (audit bot9, 2026-09-12): čísla řádků u položek níže byla zastaralá (posun +5 až +27, soubor přibyl obsahem od 2026-08-31) a budou se posouvat dál - NEPOUŽÍVAT je jako přímý odkaz, jen jako orientační pořadí. Před skokem na sekci ověř `grep -n "^## " NASTROJE_SCENY.md`.**

- Volné pozicování bez spoje · Lícování (L) jako spoj · "Najdi spoje" · Magnet/snap taxonomie · Uzemnit · Roztahuj — PŮVODNÍ, SMAZÁNO 2026-08-22, jen archiv · Cyklení ploch (R)/odpojení (U) · Rotační handle · Připoj + R krokování · Dvoufázové přimagnetování · Oprava R-cyklení · Export FBX · Menu nástrojů/plovoucí tlačítka · Barevné prostředí · Nové UI prvky patří do menu · Obarvit stejné · R-cyklení mezi spojenými profily · Připoj spojuje 2 profily · Doraz na konci profilu · Připoj preferuje "wall" fázi · Dvoufázový doraz · R-otáčení na stěně · **Roztahuj — NOVÉ, živé protažení příčky + 2 noh (2026-08-31)**.
- **Tlačítka horní lišty bez vlastní dokumentace** — 9 tlačítek zdokumentovaných teprve 2026-08-31, přesně tenhle typ obsahu je bez indexu nejtěžší najít.

**Aktivní SKILL k tomuhle souboru:** `.claude/skills/3d-scena-spoje/SKILL.md` - shrnuje pravidla níže + odkazuje na hotové ověřovací nástroje (`scripts/2026-08-18_scene_geometry_lib.js`, `scripts/2026-08-18_shelf_builder.js`), automaticky nabízený v seznamu dostupných skillů každé budoucí session v tomhle projektu (ne jen tenhle soubor čekající, až ho někdo otevře).

**Sdílený zdroj geometrie (bot8, 2026-08-19, "silná varianta B se sdílenými daty"):** `webapp/scene.html` a `scripts/2026-08-18_scene_geometry_lib.js` už NEJSOU dvě nezávislé kopie stejné logiky - klíčové geometrické funkce (`baseQuaternion`, `dominantWallCoord`, `computeConnectorsLocal`, `crossAxisHalfWidthTowardDirection`, `worldConnectorsOf`, `isProfilePart`, `firstFreeConnectorIndex`, `linkJointPeers`, `attachEntryToParent`, `registerJoint`, `applyLengthScale`) žijí v JEDINÉM souboru `webapp/js/scene-geometry-shared.js`. `scene.html` ho načítá přes `<script src="js/scene-geometry-shared.js">` (funkce se pak volají jako globály stejně jako předtím, beze změny chování), `scripts/2026-08-18_scene_geometry_lib.js` ho requiruje jako Node.js modul. `npm install` (three@0.128.0) se spouští v ROOTU repa (`/opt/konfigurator/package.json`), ne ve `scripts/` - resolvuje se pro obě strany. Pre-commit hook hlídá, že `scripts/2026-08-18_scene_geometry_lib.js` nepožaduje z `scene-geometry-shared.js` (destrukturalizací) název, který tam není exportovaný. Důsledek: při úpravě těchhle funkcí se edituje JEN `webapp/js/scene-geometry-shared.js` - žádné ruční kopírování mezi dvěma soubory už není potřeba ani možné.

**Rozšíření na kolizní test karoserie (bot16, 2026-08-30, Robert: "co umí 3D scéna skrze admina, musí umět Node.js skrze bota úplně stejně"):** `meshWorldEdgeSample`, `ensureWallBoundsTree`, `setMeshesCollisionColor`, `objectCollidesWithWalls` (hranový raycasting proti stěnám karoserie, dřív ruční kopie v každém Node.js skriptu pro umístění noh/regálu) přesunuty do stejného `webapp/js/scene-geometry-shared.js`. `checkCarBodyCollisions` sama (potřebuje živý `placed`) zůstává ve `scene.html`, jen volá sdílenou `objectCollidesWithWalls`. **Pravidlo pro budoucí funkce:** píšeš-li ve scéně novou funkci, kterou by mohl potřebovat i Node.js skript (ověřovací nástroj, placement algoritmus) - piš ji ROVNOU do `scene-geometry-shared.js`, ne inline do `scene.html`. Nová pre-commit kontrola (`.git/hooks/pre-commit`, `SCENE_SHARED_DUPLICATE`) hlídá, že se JEDNOU sdílená funkce nikdy tiše neduplikuje zpátky do `scene.html` - množina chráněných jmen se odvozuje vždy z aktuálního exportu `scene-geometry-shared.js`, takže se automaticky rozšiřuje s každou novou sdílenou funkcí, bez nutnosti tu kontrolu ručně udržovat. Kontrola ale NEROZHODUJE, jestli nová funkce do sdíleného souboru patří - to je pořád na tom, kdo ji píše.

## 2i. Volné pozicování v prostoru bez spoje — 3D bot (2026-07-24)

Robert: "potřebujeme pro 3D bota ve scéně rozšíření nástroje o volné pozicování v prostoru bez spoje."

Do teď každý krok bez `attach_to` (volný, nikam nepřipojený díl) skončil VŽDY přesně na `(0,0,0)` — appka neuměla takový díl umístit jinam.

**Přidáno:** nové volitelné pole `position_mm: [x,y,z]` (v mm) ve schématu `/api/ai/generate` (`AI_BUILD_TOOL`), použitelné JEN u kroku bez `attach_to`. U připojeného dílu nemá žádný efekt — jeho pozici vždy plně určuje spoj s rodičem. Y je nahoru. Server ověří přesný tvar (pole 3 čísel) a rozsah (každá souřadnice max ±5000mm, `AI_POSITION_BOUND_MM`) — neplatná hodnota se tiše ignoruje, díl pak skončí na původním `(0,0,0)`.

Volně umístěný díl MŮŽE být normálně použit jako `attach_to` cíl pro další kroky — `attachEntryToParent()` pracuje přímo s 3D transformacemi dílu, nezávisí na tom, jak k pozici díl došel. Jde tedy postavit např. samostatný sloupek na přesné místo v prostoru a pak na něj navázat normální spojovanou konstrukci; spojovací pravidla (kompatibilita průřezů, kolmé spoje) platí stejně jako u kteréhokoli jiného rodičovského kroku.

Implementace: `api/app.py` (`AI_POSITION_BOUND_MM`, schéma, systémový prompt, server-side validace v sanitizaci `steps`), `webapp/scene.html` (`runAIPlan()` použije `s.position_mm`, pokud je platné pole o 3 prvcích, místo pevného `(0,0,0)`).

## 2m. Lícování (klávesa L) jako zdroj spoje — POTVRZENO Robertem (2026-07-25)

Robert: "definovali jsme si co je spoj, dále když použijeme funkci Lícování, klávesa L, dochází v podstatě ke spoji, který se má zahrnout do živého panelu vpravo do ceny" / "ať se každý dolehnutý profil na druhý započítá do tabulky spojů v ceně."

**Rozšíření definice z 2d:** dosud vznikal "spoj" (a započítával se do ceny přes `entry.jointCount`) jen konstrukčně — přes `attachEntryToParent`/`registerJoint`, vázaný na konkrétní předem definovaný konektor (end/mid). Lícování (přidržení L během Posunu myší nebo tažení za oranžovou šipku) zastavuje pohyb na bounding-boxové ploše jiného dílu — obecný "dotek ploch", nezávislý na konkrétním konektoru. Robert potvrdil, že i TOHLE se má počítat jako reálný spoj a promítnout do ceny.

**Implementace:** `findAxisObstacleFace` (sdílená geometrická funkce používaná Lícováním) nově vrací i který díl překážející plochu poskytl. Při puštění tlačítka myši, pokud Lícování během TOHOTO konkrétního tažení skutečně něco zastavilo (díl je teď opravdu opřený o souseda, ne jen "někde v cestě"), zavolá se `registerLicJoint(pohybovaný_díl, soused)` — zvýší `entry.jointCount` (stejné pole, které `refreshSummary()` už dávno sčítá do ceny), s dedup po dvojici dílů (`entry.licPeers`), aby opakované dotčení STEJNÉHO souseda cenu nezvyšovalo vícekrát. Nový soused u stejného dílu = nový, samostatný spoj.

**Známé omezení (akceptováno):** dedup je po dvojici dílů, ne po konkrétním dotykovém bodě — teoreticky vzácný případ 2 fyzicky odlišných dotykových bodů mezi stejnými 2 díly se započítá jen jednou.

> **Oprava (2026-07-25, Robert: "zde se napočítalo 5 spojů ale jsou tam jen 4... použil jsem Lícování, potom jsem dal spočítat najít spoje"):** popsané omezení výše ("Lícování bookkeeping je oddělený od construction-time bookkeepingu") se skutečně projevilo — `attachEntryToParent`, `registerJoint` a další construction-time cesty vzniku spoje zvyšovaly `jointCount`, ale nikdy nenastavovaly `entry.licPeers`, takže dedup v Lícování/Najdi spoje (2n) takový pár neviděl jako "už spojený" a při dalším doteku ho započítal podruhé. Opraveno sdílenou funkcí `linkJointPeers(a, b)`, zavolanou ze všech 5 míst vzniku spoje při stavbě (`attachEntryToParent`, `applyFaceToFaceCandidate`, `registerJoint`, obě varianty "Tvar L (změna délek)") — `licPeers` je teď jednotný "už spojeno" seznam napříč VŠEMI mechanismy, ne jen Lícováním. Ověřeno `doublejoint_harness.js` (6 assertions, včetně přímé rekonstrukce Robertova hlášeného případu).

**Vlastnictví kódu:** samotná mechanika Lícování (klávesa L, tooltip, Posun myší) je feature bot2 — tahle změna se dotýká jen geometrické funkce `findAxisObstacleFace` (rozšířena o vrácení vlastníka překážející plochy, chování pro původní účel beze změny) a přidává napojení na existující cenový systém spojů (bot1).

## 2n. Tlačítko "Najdi spoje" — dopočítání ještě nezapočítaných spojů (2026-07-25)

Robert: "udělej funkci dopočítání počtu spojů v objektu, který je [ještě] nemá zpočítané... po označení objektu zpočítá spoje a pošle to do cenové tabulky vpravo." Třetí cesta, jak vznikne "spoj" (po construction-time `attachEntryToParent`/`registerJoint` z 2d a Lícování z 2m) — pro díly, které se fyzicky dotýkají, ale žádný z předchozích mechanismů to nezaznamenal (ručně poposunutý díl bez L, nebo nová sestava položená vedle existující konstrukce).

Tlačítko "🔗 Najdi spoje" (horní lišta) po označení dílu/dílů projde je proti VŠEM položeným dílům ve scéně (i mimo výběr) a nalezené doteky zaregistruje stejnou funkcí a stejnou dedup sadou (`entry.licPeers`) jako Lícování — takže spoj započítaný jednou cestou už druhá cesta neduplikuje, a lze tlačítko spouštět opakovaně bez rizika navýšení ceny.

> **Oprava (2026-07-25, Robert: "spoje tam jsou ale nenašel žádny"):** první verze porovnávala jen striktní shodu předem definovaných `connectorsLocal` bodů (typicky 2 "end" body na profil) — to selhává přesně u nejběžnějšího případu z Robertova screenshotu (rám: 2 sloupky + 2 příčky), kde konec vodorovné příčky dosedá na BOK sloupku (T-spoj) v místě, které neodpovídá žádnému předem definovanému konektoru sloupku. Přepsáno na stejný princip "dotyku plochy" (bounding-box), jaký už používá Lícování (`findAxisObstacleFace`): pro každou dvojici dílů se kontroluje, jestli je nějaká plocha jednoho do 0,75 mm od plochy druhého NA JEDNÉ ose, a současně se díly skutečně překrývají (ne jen jsou poblíž) na OBOU zbylých osách — teprve to je reálný fyzický dotyk, bez ohledu na to, jestli padl do nějakého konektoru. Vedlejší důsledek: funkce už nenastavuje `usedConn` na konkrétním konektoru (u obecného dotyku plochy není jednoznačné, který konektor označit) — oranžové šipky tak mohou zůstat viditelné i po nalezení spoje, na započítání do ceny to ale vliv nemá.

## 2k. Inteligentní magnet/snap — obecné napojování libovolných dílů (2026-07-24, návrh)

Robert: "promysli do hloubky možnosti magnetování, snapování objektů k sobě... musí uživateli nabídnout automaticky veškeré klíčové možnosti napojení objektů na sebe, dle pravidel, čelama profilů k sobě nebo plochama nebo kombinací." Cíl: obecný systém, který mezi DVĚMA LIBOVOLNÝMI díly ve scéně (ne jen přes pevné presety L/T/čtverec/kvádr) sám najde a nabídne všechny geometricky i pravidly povolené způsoby spojení.

**Taxonomie napojení (co systém rozpoznává):**
1. Čelo–čelo, rovně (prodloužení do přímky) — **zahrnuto** (Robertovo rozhodnutí, i když u hliníku není úplně běžné).
2. Čelo–čelo, kolmo (roh) — obecná verze dnešních L-presetů.
3. Čelo–plocha uprostřed (T-spoj) — už existující `kind:"mid"` konektor, dosud nevyužívaný obecně.
4. Čelo–plocha s odsazením k rohu (outer-corner) — stejná logika jako dnešní `crossAxisHalfWidthTowardDirection`.
5. Plocha–plocha, rovnoběžně (boční laminace/zdvojení) — **nový** typ konektoru, appka ho dosud vůbec nezná.
6. Plocha–plocha, kolmo (rošt/mřížka) — kombinace bodu 3 a 5.

**Datový model — rozšíření `connectorsLocal`:** ke stávajícím `end`×2 a `mid`×1 konektorům přibydou 4 nové `kind:"face"` konektory (jeden na každou podélnou stěnu profilu) — bod uprostřed stěny, vnější normála, rozměry stěny (délka profilu × šířka průřezu ve směru té stěny). Zpětně kompatibilní — veškerý stávající kód filtruje konektory podle `kind === "end"`/`"mid"`, takže přidání `"face"` nic nerozbije.

**Pravidla (Robertova rozhodnutí):**
- Čelní i plošné spoje se řídí STEJNOU tabulkou kompatibility průřezů jako dnes AI generátor (`PROFILE_JOIN_PAIRS` — 10×40 samo; 20×20↔20×40; 20×80 samo; 30×30↔30×60; 35×35 samo; 40×40↔40×80; 45×45↔45×90). Tabulku je třeba zpřístupnit i klientu (nový `GET` endpoint nebo vložit do `/api/katalog` odpovědi), aby fungovala živá filtrace bez nutnosti dotazu na server při každém tažení.
- Rovné prodloužení čel se nabízí, ne skrývá.

**UX (Robertovo rozhodnutí — kombinace obou přístupů):**
- **Živý magnet při tažení** — pro nově vkládaný/volně tažený díl: při přiblížení k jinému dílu se automaticky zobrazí přízračné (ghost) náhledy top-N kandidátů (seřazené podle vzdálenosti/úhlu), uživatel jeden vybere (klik nebo cyklování klávesou) a pustí.
- **Panel po označení dvou dílů** — pro už umístěné díly (dodatečné přepojení): výběr dvou dílů (stejný mechanismus jako Mikroposuv/Posun myší) zobrazí seznam všech platných způsobů napojení mezi nimi, klik provede transformaci.

**Detekční algoritmus (návrh):** pro aktivní díl (tažený, nebo pár označených) projít všechny ostatní umístěné díly v hrubém dosahu, pro každou dvojici vyzkoušet všechny kombinace konektorů (end×end, end×mid, end×face, face×face), kandidáty ohodnotit vzdáleností + potřebným úhlem dotočení a vyfiltrovat podle kompatibility průřezů, výsledek seřadit a nabídnout TOP N (ne tiše vybrat jeden — to Robert explicitně požaduje).

**AI bot:** Robert rozhodl dát stejnou detekční logiku k dispozici i AI botovi (nástroj typu "jaké spoje jsou možné mezi dílem X a Y", aby mohl sám navrhovat/aplikovat obecná napojení, ne jen presety).

**Stav:** návrh odsouhlasen, implementace probíhá — postupně: (1) rozšíření konektorového modelu o boční plochy, (2) detekční/skórovací algoritmus, (3) UI živého magnetu, (4) UI panelu pro přepojení, (5) AI nástroj.

## 2o. Uzemnit — posun výběru na podlahu (2026-07-25)

Robert: "ve scéně je základní grid v ploše x/y, bereme to jako 0mm pro osu Z, přidejme do scény tlačítko Uzemnit, tzn že spodní část objektu dolehne v ose z na 0mm."

**Důležité — značení os v appce NENÍ 1:1 se skutečnými THREE.js osami:** appka má reálné "nahoru" na THREE ose **Y** (`camera.up = (0,1,0)`, podlahový `GridHelper` leží v reálné rovině X-Z při Y=0). Robert si už dřív (viz `axisMoveWorldDir`, funkce Posun myší) vědomě nechal v UI **prohodit značení "Y"/"Z"**, aby písmeno "Z" v appce vždy znamenalo VÝŠKU — i když jde technicky o reálnou THREE osu Y. Kdykoli tedy Robert mluví o ose "Z" jako o výšce/podlaze, jde o tohle UI-značení, ne o `object3d.position.z`. Tlačítko "Uzemnit" proto posouvá po reálné ose Y.

**Implementace:** `groundSelection()` — funguje na sjednoceném výběru (1 díl, více dílů, i celá Join/rám skupina — stejný princip jako Kopírování/Najdi spoje/BoxEdit skupina). Najde nejnižší reálný world-Y bod přes CELÝ výběr a posune všechny vybrané díly o JEDNU společnou hodnotu (tuhý posun celku — nezvedá/nespouští každý díl zvlášť, jinak by se u spojené sestavy roztrhlo vzájemné vertikální uspořádání). Tlačítko "⬇ Uzemnit" v horní liště.

> **Oprava (2026-07-25, Robert: "kopíroval jsem díly v ose z ale nakládali se špatně"):** dialog Kopírování (`confirmCopyDialog`) tuhle "Z=výška" konvenci nedodržoval — stavěl offset přímo z DOM polí (`dx,dy,dz`) beze svapu, takže zadání hodnoty do pole "Z" posunulo kopii po REÁLNÉ ose Z, ne nahoru. Opraveno na `new THREE.Vector3(dx, dz, dy)`. **Známé riziko stejné chyby jinde:** BoxEdit dimension editor (`dimEditZ`) aktuálně TAKY mapuje přímo na reálnou osu Z (nekontrolováno/nehlášeno) — při podobném budoucím hlášení u BoxEdit prověřit jako první podezřelé místo.

## 2p. Roztahuj — zpětné povolení modrých šipek na ručně poskládaném rámu (2026-07-25) — POZOR: SMAZÁNO 2026-08-22, jméno tlačítka POUŽITO ZNOVU 2026-08-31 pro úplně jinou funkci (viz sekce 2an níže)

**Tenhle popis je jen HISTORIE, tlačítko a funkce popsané níže už v kódu NEEXISTUJÍ.** Tlačítko "↔ Roztahuj" bylo smazáno (Robert, 2026-08-22 — viz komentář u `RECT_FRAME_TOUCH_EPS` (OPRAVENO audit bot9 2026-09-12: dnes ve `webapp/js/scene/hdri-panels-ui.js`, přesunuto refaktoringem `abbe24cc` 2026-09-03, ne ve `scene.html`): `"puvodne vznikly pro tlacitko Roztahuj (smazano, Robert 2026-08-22 [remove-fn])"`). O 9 dní později (2026-08-31) Robert znovu zadal úplně JINOU funkci se STEJNÝM názvem tlačítka ("↕ Roztahuj") — živé protažení příčky + navazujících noh, viz sekce 2an. Kdokoli hledá "Roztahuj" v historii/kódu ať čte 2an, ne tuhle sekci — ponecháno jen jako archivní záznam původního účelu.

Robert: "zkusme udělat tlačítko na znovu nastavení modrých šipek složených objektů, název Roztahuj."

Modré natahovací šipky (2l) se dosud objevily jen u rámu postaveného přes přednastavený tvar "Čtverec/rám", protože jen ten si sám nastaví `entry.frameGroup`. Ručně poskládaný/pospojovaný rám (Lícování, Najdi spoje, magnet panel, starší uložený vlastní tvar) `frameGroup` nikdy nedostal.

**Tlačítko "↔ Roztahuj":** označ přesně 4 jednoduché 2-koncové profily tvořící uzavřený obdélník (dotýkající se v rozích v pravém úhlu) → `detectRectFrameFromSelection()` ověří strukturu (dotyková mapa + kontrola pravých úhlů) → `reverseEntryEndOrder()` podle potřeby přeznačí pořadí konců u jednotlivých dílů (bezpečný, čistě indexový krok — geometrie se nemění), aby odpovídalo konvenci, kterou už vyžaduje stávající `refitRectFrameEntries` → nastaví se `entry.frameGroup` na všech 4 dílech → modré šipky se objeví přes stávající `refreshFrameResizeHandles()`.

Neregistruje ani nemění `jointCount` — to zůstává výhradně v gesci Najdi spoje/Lícování/konstrukce (2d, 2m, 2n).

Robert: "pravidlo: natahovat oranžovýma šipkama nejde příslušenství, jen profily."

Oranžová šipka (protažení/zkrácení délky) dává smysl jen u hliníkového profilu (`layer === "alu"`) - má skutečnou proměnnou délku. Příslušenství/spojky (`layer` black/zinc) i produkty (`layer` "produkt", viz `fetch_katalog_parts()` v `app.py`) mají pevný tvar, natažení by je jen zdeformovalo bez fyzického smyslu. Vyřešeno centrálně v `refreshEndpointMarkers()` (bot1, 2026-07-28) - kontrola `entry.part.layer !== "alu"` platí pro VŠECHNY cesty vložení dílu (klik na katalog, AI generate, kopie, wizard, vlastní tvary...), ne jen pro jeden konkrétní import (SSE baked-world), který si to už dřív ošetřoval jen sám pro sebe.

## 2t. Cyklení ploch (R) a odpojení (U) připojeného příslušenství (2026-08-01)

Robert: "když je prislušenství připnuté, a označené, klavesou R by mohlo rotovat kolem osy profilu na různé plochy profilu postupně... a vymysli rozumné odpojení jak to udelat."

R je už existující nástroj (držet R + táhnout myší = rotace vybraného po 90° kolem zvolené osy, kolem centroidu výběru). Pro připojené příslušenství by ale rotace kolem vlastního centroidu vypadala špatně (odlepilo by se od povrchu profilu) - přidán nový branch: když je vybraný PRÁVĚ JEDEN už připojený neprofil (`entry.attachedTo`, nastaveno při commitu Posunu myší - viz 2s), R+tažení místo obecné rotace CYKLUJE mezi DALŠÍMI platnými kandidáty (`findAccessoryToProfileCandidates`) na STEJNÉM profilu, seřazenými deterministicky (`sortedAccessoryCandidates`) - každý krok (70px tažení) = další/předchozí plocha, živě nahlíženo (`skipBookkeeping`) během tažení (`previewAccessoryCandidateStep`), skutečně zaznamenáno (výměna `usedConn`, BEZ opětovného zvýšení `jointCount` - pořád je to jen JEDEN spoj, jen na jiné ploše) až při puštění R (`commitAccessoryCandidateStep`). Původní obecná rotace (profily, skupiny, nepřipojené díly) zůstává 100% beze změny.

Odpojení (nové): klávesa **U** (Uvolnit) - `detachAccessory(entry)`. Nemění pozici/natočení (zůstává přesně tam, kde je) - jen zruší `attachedTo`, sníží `jointCount` o 1 (už se neúčtuje v ceně) a uvolní obousměrný `licPeers` záznam, aby šel díl později znovu připojit bez blokování starým párováním.

Bonus: stavový řádek Posunu myší při výběru 1 připojeného dílu ukazuje nápovědu "📎 připnuto (R = otočit na jinou plochu, U = odpojit)".

Ověřeno Node.js testem (19 kontrol): počáteční připojení, cyklení +1 (živý náhled neměni jointCount/usedConn, commit ano), cyklení celé kolem dokola (n kroků) se vrátí na stejnou plochu a jointCount zůstává 1, krok -1 správně obtočí index, odpojení vyčistí attachedTo/jointCount/licPeers oběma směry, opakované odpojení je bezpečný no-op.

## 2u. Myší ovladatelný rotační prstenec (handle) kolem profilu (2026-08-01)

Robert: "to je celkem skoro dobré, ale ještě tam přidej kolem rotační šipku kterou když si myší vyberu, točí se to kolem profilu."

Přímá myší alternativa k držení klávesy R (viz 2t) - žádná nová logika cyklení, jen nový způsob, jak SPUSTIT/UKONČIT tu samou operaci. Přesně za stejné podmínky, za jakých by R skutečně cyklovalo (vybraný právě 1 už připojený neprofil, aspoň 2 platné plochy na jeho profilu), se kolem toho profilu objeví poloprůhledný fialový 3D prstenec (torus) - vystředěný na profil, kolmý na jeho délkovou osu, o poloměru odvozeném z půlšířek průřezu profilu (+22mm okraj, aby byl vizuálně "kolem", ne skrz geometrii).

Klik levým tlačítkem přímo na prstenec spustí úplně stejné tažení jako držení R (`startRotateDrag`/`updateRotateDrag`/`finishRotateDrag` - beze změny), jen přes nový `rotateHandleGrabbed` příznak: tažení skončí puštěním TLAČÍTKA MYŠI (nový `pointerup` listener), ne puštěním klávesy R (existující `keyup` handler má nový guard, aby nechtěně neukončil tažení rozjeté myší). Prstenec během tažení zesvětlá jako vizuální potvrzení.

Žádný zásah do dat/geometrie dílů ani do jiných nástrojů - prstenec je jen pomocný `THREE.Mesh` přidaný přímo do scény (mimo `placed`), stejně jako existující fialová čára pro R. Všechny ostatní raycasty ve scéně používají explicitní seznamy mesh z `placed`, takže prstenec nijak neovlivňuje výběr/tažení jiných dílů. Pozice/viditelnost/barva se přepočítává každý snímek z `animate()` (`refreshRotateHandle`, stejný vzor jako `updateConnectionMarkerPositions`).

Ověřeno Node.js testem (16 kontrol, `test_rotate_handle.js`): detekce cíle prstence pro všechny hraniční případy (0/2+ vybraných, profil místo příslušenství, nepřipojený díl, jen 1 kandidát plochy, mezitím smazaný profil), vzorec poloměru, a interakce `rotateHandleGrabbed` s keyup/pointerup (držení R nekončí tažení chycené myší, a naopak).

## 2v. Tlačítko "Připoj" a klik/stisk R = 1 krok 90° místo tažení (2026-08-01)

Robert: "přidej funkci P připoj, označené příslušenství připojí na označený profil." a "ohledně rotace příslušenství kolem profilu, má se rotovat o 90 každým klikem na R."

**Tlačítko Připoj:** Robert navrhl písmeno "P", to už je ale obsazené (Posun myší - toggle režimu) - implementováno jako tlačítko v toolbaru (vedle "Najdi spoje"), ne jako nová klávesová zkratka, aby nedošlo ke kolizi. Označ přesně 1 profil a 1 příslušenství (union Mikroposuvu i Posunu myší) a klikni - `attachSelectedAccessoryToProfile()` připojí příslušenství rovnou na PRVNÍ platnou plochu profilu (deterministicky seřazeno stejně jako R-cyklení), bez nutnosti předtím fyzicky přiblížit díly v scéně. Když už je příslušenství připojené k jinému profilu, nejdřív se čistě odpojí (žádné dvojité počítání `jointCount`).

**R a rotační prstenec = okamžitý krok, ne tažení:** Původní mechanika (viz 2t, 2u) vyžadovala držení R + tažení myší (70px = 1 krok), respektive chycení a tažení prstence. Nahrazeno novou funkcí `stepAccessoryFace(accEntry, step)`, která provede celý krok najednou (geometrie i účetnictví, beze změny `jointCount`) - volaná přímo z JEDNOHO stisku R (`ev.repeat` guard - držení klávesy dole neopakuje krok automaticky) nebo JEDNOHO kliknutí na prstenec. Platí POUZE pro případ "vybrané 1 už připojené příslušenství s ≥2 platnými plochami" - obecná rotace profilů/skupin kolem zvolené osy (držení+tažení) zůstává beze změny.

Původní tažecí mechanismus (`rotateAccessoryState`, `previewAccessoryCandidateStep`, `commitAccessoryCandidateStep`, `rotateHandleGrabbed` + jeho pointerup/keyup guardy) zůstává v kódu nedotčený, jen už není volaný pro tento případ - stejný princip "nemazat, jen obejít" jako u dřívějších redesignů (např. značky napojení, viz 2r→2s). Prstenec navíc krátce (220ms) zbělá po každém kroku jako vizuální potvrzení.

Ověřeno Node.js testem (20 kontrol, `test_attach_and_step.js`): tlačítko Připoj odmítá špatný počet/mix výběru, připojí na první seřazený kandidát, přepojení na jiný profil nezdvojí `jointCount`; `stepAccessoryFace` dělá přesně 1 krok, `jointCount` se při cyklení nemění, celý kruh (n kroků) se vrátí na původní plochu, no-op na nepřipojeném dílu.

**Doplněk (2026-08-02):** po úspěšném připojení tlačítkem "Připoj" se profil automaticky odznačí (z obou výběrových sad - Mikroposuv i Posun myší), příslušenství zůstává označené - hned jde použít R / rotační prstenec nebo další posun. Chybové větve výběr nemění.

## 2w. Dvoufázové přimagnetování na čelo profilu (2026-08-02)

Robert: "příslušenství tažené na konec profilu se namagnetuje na čelo profilu, ale to nechceme, nejdříve musí přijet na samotný konec profilu, zastavit se, a až dalším tažením skočit na čelo profilu."

Předtím: jakmile bylo tažené příslušenství v dosahu `ACCESSORY_SNAP_RADIUS_MM` (60mm) od "end" (čelo) konektoru profilu, hned se OKAMŽITĚ přeorientovalo a přilepilo - působilo to jako by "skočilo" dřív, než fyzicky dojelo na místo.

**Verze 1 (bezstavová, chybná) a proč nestačila:** první pokus počítal jen signed vzdálenost podél směru tažení mezi konektorem příslušenství a profilu, každý snímek nezávisle (konstanty `ACCESSORY_END_ARRIVE_MM=8`, `ACCESSORY_END_OVERSHOOT_MM=20` - "zastavení" pásmo bylo jen ~28mm široké). Robert nahlásil potřetí stejný problém ("namagnetuje se SKOKEM") - root cause: běžné tažení myší umí v JEDNOM snímku (mezi dvěma mousemove eventy) posunout volnou pozici klidně o desítky/stovky mm, takže se celé úzké "zastavení" pásmo občas přeskočilo najednou a díl skončil rovnou v "přilepit" pásmu bez viditelného zastavení.

**Verze 2 (stavová, oprava 2026-08-02):** první snímek, kdy se objeví TENHLE KONKRÉTNÍ kandidát (identifikovaný profilem + oběma konektorovými indexy) - BEZ OHLEDU na to, jak velká byla volná mezera předtím (i kdyby už byla "za" bodem doteku kvůli velkému skoku myši) - VŽDY jen zastaví (zarovná pozici přesně na bod doteku, ŽÁDNÁ přeorientace) a zapamatuje si aktuální "param" (pozici podél osy tažení) jako referenční bod. Teprve na DALŠÍCH snímcích, když uživatel táhne ještě `ACCESSORY_END_OVERSHOOT_MM` (20mm) dál - měřeno OD TOHOTO zapamatovaného bodu, ne od absolutní mezery - se skutečně přilepí/přeorientuje. Tím je zaručený aspoň 1 viditelný "zastavený" snímek před možným přilepením, bez ohledu na to, jak rychle/skokově uživatel táhne. Změna kandidáta (jiný profil/konektor) mezi snímky se považuje za "nový" a taky vždy nejdřív zastaví - žádné přenášení overshootu mezi různými cíli. Vzdálení z dosahu resetuje stav.

Boční stěny ("face") nejsou dvoufázovým mechanismem dotčené - tam zůstává původní okamžitý magnet (Robert si stěžoval výslovně jen na čelo/konec).

Ověřeno Node.js testem (`test_end_stop_v2.js`, 9 assertions) - KRITICKÝ test explicitně simuluje jeden rychlý snímek, který přeskočí 50mm ZA bod doteku (uvnitř původně "přilepit" pásma), a ověřuje, že nová verze i tak jen ZASTAVÍ (ne přilepí); dále normální pomalé přibližování, reset při vzdálení, reset při změně kandidáta. (Předchozí `test_end_stop.js`, 11 kontrol, ověřoval verzi 1 - ponechán pro historii, ale popisuje už nahrazené chování.)

**Verze 3 (flush zarovnání, upřesnění 2026-08-02):** Robert upřesnil - "příslušenství se musí zastavit na konci profilu, tak že jeho plochy lícují s čelem." Verze 2 při "zastavení" jen posunula POZICI a nechala orientaci nezměněnou (původní/volnou) - díl se tak dotýkal jedním bodem, ale mohl být pod libovolným úhlem, ne flush proti čelu.

Oprava: během "zastavení" se teď použije STEJNÁ (vizuální, `skipBookkeeping`) přeorientace jako při skutečném přilepení - `applyConnectionCandidate(..., {skipBookkeeping:true})` se volá VŽDY, jakmile je "end" kandidát v dosahu (i během čekání na overshoot), takže díl hned líčí plochou s čelem profilu. Jediná věc, co "zastavení" od "přilepení" odlišuje, je jestli už se zaznamenala skutečná vazba (`jointCount`/`usedConn`/`attachedTo` přes `st.pendingSnap`) - stavová logika (sameAsBefore/overshoot z verze 2, garantovaný aspoň 1 snímek "zastaveno, ještě nezaznamenáno" před možným přilepením) zůstává beze změny.

Ověřeno Node.js testem (`test_flush_stop.js`, 5 assertions): i první (zastavený) snímek zavolá plnou přeorientaci, `pendingSnap` se pořád nastaví až po dosažení overshoot prahu (ne dřív, i při velkém skoku myši), preview se volá každý snímek během čekání.

**Verze 4 (malé "engage" pásmo, oprava 2026-08-02):** Robert pořád (počtvrté) hlásil stejný problém: "není to, pořád to skáče na čelo z dálky." Skutečný root cause: verze 3 sice opravila natočení, ale spouštěla vizuální korekci (pozice+přeorientace) HNED, jak `findBestAccessorySnap` našel "end" kandidáta KDEKOLI v rámci širokého 60mm hledacího poloměru (`ACCESSORY_SNAP_RADIUS_MM`) - to samo o sobě vypadalo jako skok z až 60mm daleko, i když už to nebyl skok na skutečné přilepení (jen na "zastavení").

Oprava: nový, mnohem menší práh `ACCESSORY_END_ENGAGE_MM=15`. Mezi 60mm (kde `findBestAccessorySnap` poprvé najde "end" kandidáta) a tímhle 15mm prahem se díl hýbe ÚPLNĚ VOLNĚ - žádná korekce pozice ani natočení vůbec, čistý posun podél osy přesně podle myši. Teprve když je opravdu blízko (≤15mm), zapojí se dvoufázový mechanismus (zastavení s plnou přeorientací z verze 3, pak overshoot→přilepení ze stavové logiky verze 2) - beze změny.

Ověřeno Node.js testem (`test_engage_radius.js`, 11 assertions): z 50mm (uvnitř 60mm hledání, ale mimo 15mm engage) se NEVOLÁ žádná korekce vůbec (explicitně testován a opraven root cause "skoku z dálky"); postupné přibližování 50→30→10mm ukazuje korekci poprvé až pod 15mm; rychlý skok přímo na 5mm pořád jen zastaví (ne přilepí) na prvním snímku; oddálení nad 15mm resetuje stav.

**Verze 5 (rovinný clamp - finální model, 2026-08-02):** Robert upřesnil, co "zastavení na konci" doopravdy znamená: "připojené příslušenství na profilu, když se posunuje myší nebo mikroposuvem se musí zastavit na konci profilu tj. rovina čela profilu, což znamená situaci kdy kterákoli stěna příslušenství lícuje s čelem profilu a nepřesahuje délku profilu." To mění celý model: všechny 4 předchozí verze měřily vzdálenost konektor–konektor, jenže "end" konektor je ve STŘEDU čela a díl jedoucí po BOKU profilu se k němu nikdy pořádně nepřiblíží - proto to Robertovi pořád "skákalo".

Nově `clampAccessoryToProfileLength()`: promítne 8 rohů světové obalky (Box3) dílu na podélnou osu profilu (mezi oběma "end" konektory) a když volný posun přejede rovinu čela, srovná díl zpět PŘESNĚ na lícování krajní stěny s čelem - orientace se NEMĚNÍ, díl dál sedí na své boční ploše. Zapojení: (a) Posun myší - díl připojený na boční stěnu má přednostně rovinný clamp; dalším tažením o `ACCESSORY_END_OVERSHOOT_MM` (20) ZA rovinu přeskočí na čelo (garantován aspoň 1 viditelný zastavený snímek i při skokovém tažení); vzdálenostní mašinerie (verze 1-4) zůstává JEN pro NEpřipojené díly. (b) Mikroposuv - druhý průchod po posunu zastaví připojené díly na rovině čela (jen stop + toast, žádný přeskok); při posunu celé podsestavy (profil vybraný také) se vzájemná poloha nemění a clamp nic nedělá. Výjimky: díl připojený na ČELO se neomezuje (z principu přesahuje), díl delší než profil také ne. Navíc oprava `finishAxisMoveDrag`: před záznamem nového spoje se už připojený díl napřed odpojí (jinak dvojitý `jointCount`).

Ověřeno Node.js testem (`test_end_plane_clamp.js`, 33 assertions, reálný three.js): lícování přesně na rovině (vč. pootočeného profilu), obě čela, průběh volně→zastaveno→přeskok, skok myši 120mm za čelo přesto napřed zastaví, couvnutí resetuje, mikroposuv stop, kolmý posun bez zásahu, výjimky.

## 2x. Oprava R-cyklení - vynechávalo pozice (2026-08-02)

Robert: "rotace R příslušenství kolem osy profilu, cyklus vynechává některé pozice, na každé stěně lze mít příslušenství otočené 4mi směry."

Root cause: `findAccessoryToProfileCandidates()` dávala na KAŽDOU dvojici (konektor profilu × konektor příslušenství) jen JEDNO natočení (cokoli vyšlo z `THREE.Quaternion.setFromUnitVectors`) - fyzicky ale na každé takové ploše existují 4 platná natočení "naplocho" (0/90/180/270° kolem společné normály). Cyklení (R / rotační prstenec) tak fyzicky nemohlo navštívit zbývající 3 natočení na stejné ploše.

Oprava: nová funkce `findAccessoryToProfileCandidatesAllSpins()` expanduje každý původní kandidát na 4 (spin 0-3). POUZE `sortedAccessoryCandidates()` (používané R-cyklením/rotačním prstencem) na ni přepnuto - původní `findAccessoryToProfileCandidates()` zůstává beze změny pro ostatní volající (panel "Možnosti napojení", magnet-snap tažením, tlačítko Připoj), aby se jim seznam nezaplevelil 4x víc položkami. `accEntry.attachedTo` má nový field `spinIndex` (0-3) - `currentAccessoryCandidateIndex` ho teď taky porovnává (jinak by cyklení pořád "resetovalo" na spin 0 a nikdy se nedostalo za spin 1 - přesně ten bug, který Robert nahlásil).

Ověřeno Node.js testem (5 kontrol, `test_spin_fix.js`): 4 odlišné kandidáti/quaterniony na 1 dvojici konektorů (místo původního 1), 4 kroky cyklení navštíví přesně všechny 4 spiny a vrátí se na start.

## 2y. Držení R pokračuje v krokování (2026-08-02)

Robert: "rotování kolem profilu, nechť rotuje i když je tlačítko R drženo."

Předtím (po redesignu "klik = 90°", viz 2v): každý STISK R udělal přesně 1 krok a dál se nic nedělo, i když uživatel klávesu dál držel (`ev.repeat` guard schválně ignoroval OS auto-repeat keydown eventy).

Nově: první stisk krokuje ihned jako dřív, ale pokud R zůstává drženo, každých `ROTATE_ACCESSORY_HOLD_INTERVAL_MS` ms (ladil se za pochodu - postupně 350ms → 29ms → 120ms, aktuální hodnota přímo v kódu) se provede další krok - vlastní `setInterval` (`rotateAccessoryHoldTimer`), NEZÁVISLÝ na OS klávesnicovém auto-repeatu (ten má nekonzistentní zpoždění/rychlost napříč systémy/prohlížeči). Puštění R i ztráta fokusu okna (blur) interval bezpečně zastaví. Logika samotného kroku (`stepAccessoryFace`, podmínka "přesně 1 vybrané už připojené příslušenství s ≥2 platnými plochami") je beze změny - jen se teď opakuje časovačem místo jednorázově. Obecná rotace profilů/skupin (hold+drag) zůstává nedotčena.

Ověřeno Node.js testem (9 kontrol, `test_hold_rotate.js`, falešný časovač): první stisk krokuje ihned, držení pokračuje přesně v očekávaných intervalech, puštění R zastaví další kroky, neplatný výběr nezakládá žádný interval, opakované krokování správně obtáčí index přes n kandidátů.

## 2z. R-cyklení drží pozici podél profilu (2026-08-02)

Robert: "při stisku R nechť příslušenství zůstává na aktuální pozici, nech se nepřesouvá na střed ani jinam." `applyConnectionCandidate` umisťuje díl vždy na STŘED cílové stěny (konektor "face" je v jejím středu) - každý krok R proto díl teleportoval na střed délky profilu.

Oprava ve `stepAccessoryFace`: před přepnutím se zapamatuje poloha dílu PODÉL délky profilu (průmět středu světové obálky Box3 na osu mezi oběma "end" konektory), po přepnutí se díl po ose posune zpátky - "obíhá" kolem profilu na svém místě. Následně `clampAccessoryToProfileLength` (viz 2w Verze 5) zajistí, že při pootočení u konce profilu nevznikne přesah přes rovinu čela. Výjimka: kandidát na ČELO má pevné místo na konci profilu, tam se pozice nevrací. Tlačítko "Připoj" a magnet tažením beze změny.

Ověřeno Node.js testem (`test_r_keep_position.js`, 9 assertions): přepnutí stěny i spin drží polohu podél osy, u konce profilu clamp srovná přesně na lícování (žádný přesah), kandidát na čelo se nevrací.

## 2aa. Export označených dílů do FBX (2026-08-02)

Robert: "přidej do scény tlačítko na vyexportování označených objektů do fbx pro uložení na PC." Tlačítko "Export FBX" v toolbaru: označené díly (union obou výběrů, vč. celých Join skupin) se v prohlížeči převedou na Wavefront OBJ (trojúhelníky ve světových souřadnicích, mm - přesně jak stojí ve scéně; čistá geometrie bez barev, hrany a pomocné objekty se přeskakují) a pošlou na `POST /api/export-fbx`, kde je CLI nástroj `assimp` (balíček assimp-utils, doinstalován na server) převede na binární Autodesk FBX - soubor se vrátí jako stažení `konfigurator_export_RRRR-MM-DD.fbx`. three.js totiž žádný FBX exporter nemá (jen loader). Limity: prázdný vstup 400, >50 MB 413, timeout převodu 120 s.

Ověřeno: test_fbx_export.js (9 assertions) + e2e curl po nasazení (HTTP 200, FBX magic "Kaydara FBX Binary", správný Content-Disposition; prázdný vstup 400).

## 2ac. Menu nástrojů - plovoucí přetahovatelná tlačítka (2026-08-02)

Robert: přesunout všechna tlačítka hlavního panelu do menu, z kterého si každý uživatel může tlačítka přetahovat do scény a zpět jako plovoucí. Nový panel `#toolsMenuPanel` (+ zasouvací tab `#toolsMenuTab`) - stejný vzor jako Tvary/wizardPanel (draggable hlavička, sbalení s pamětí v localStorage). Obsahuje všechna dřívější akční tlačítka toolbaru (Vyčistit scénu, Odebrat poslední, Vše odznačit, Kopírovat, Najdi spoje, Připoj, Uzemnit, Export FBX, Roztahuj, Kontrola ploch, Obarvit díl, Barva označení). Selecty vykreslení/pohledu, zaškrtávátka a barevné kolečko zůstávají v původní horní liště.

Každé tlačítko v menu (`makeToolButtonRelocatable`) lze uchopit myší a vytáhnout ven do scény - pod prahem 5px pohybu funguje obyčejný klik beze změny (žádné klonování DOM uzlu, listener zůstává navázaný), po překročení prahu se stává plovoucím (`.toolFloatingBtn`, position:absolute v `#viewport`) a sleduje kurzor. Puštění nad rozbaleným panelem ho vrátí zpět do menu; jinde ve scéně zůstane na místě (ořízne se do viditelné oblasti, i při změně velikosti okna). Rozložení (co je plovoucí a kde) se ukládá do localStorage (`konfToolsMenuLayout`) - per prohlížeč/uživatel.

Ověřeno testem test_tools_menu.js (12 assertions - geometrie rozhodování "nad panelem", klamp pozice, round-trip perzistence přes JSON).

## 2ad. Barevné prostředí scény + přechod do dálky do šeda (2026-08-02)

Robert: barevné prostředí scény s přechodem do dálky do šedé, plus proužek na výběr barvy. `scene.background` je vertikální gradient (CanvasTexture) - dole zvolená (tlumená) barva prostředí, nahoru přechází do neutrální šedi `ENV_FOG_GRAY` (0x9199a3). Zároveň `scene.fog` (THREE.Fog) ve STEJNÉ šedi - geometrie při velkém oddálení bledne do stejné barvy jako pozadí (bezešvý přechod). Fog near/far (10000/80000) je hluboko za typickým pracovním prostorem, běžnou práci neovlivňuje; far-plane kamery (100000, dřívější "objekty v dálce nesmí mizet") beze změny - fog nic nedělá neviditelným, jen barevně stmívá.

Nový vodorovný "proužek" (`#envColorStrip`, vpravo nahoře) - čistý CSS gradient přes celé spektrum, klik/tažení vybere odstín (0-360°) jako "blízkou" barvu prostředí. Uloženo v localStorage (`konfEnvHue`) per prohlížeč. Výchozí odstín 210° (modrošedá).

Ověřeno testem test_env_background.js (19 assertions): shoda fog/gradient barvy, fog vzdálenosti mimo pracovní prostor, HSL převod, normalizace hue, pozice posuvníku i inverzní výpočet z kliknutí.

## 2ae. R-cyklus - oprava opakujících se pozic před přechodem na další stěnu (2026-08-02)

Robert: "zkontroluj tu rotaci kolem profilu pomocí R, některé pozice se opakují vícekrát než se přejde na další stěnu."

Příčina: `sortedAccessoryCandidates()` (zdroj kandidátů pro R-cyklus) dřív procházela úplně VŠECHNY kombinace tří nezávislých dimenzí - plocha profilu (`forcedParentConnIdx`) × vlastní konektor příslušenství (`childFaceConnIdx`) × spin (0-3). U běžného, částečně symetrického příslušenství (např. úhelník se dvěma podobnými plochami) tak R nejdřív 4× otočilo POŘÁD STEJNOU stěnu profilu - jen s jiným vlastním konektorem příslušenství, který ale často vypadá vizuálně stejně nebo velmi podobně - a teprve pak přešlo na další stěnu profilu. Odtud dojem "některé pozice se opakují".

Robertovo původní zadání (2026-08-01) ale popisovalo jen DVOUÚROVŇOVÝ cyklus: R rotuje postupně na různé plochy profilu, na každé stěně 4 směry (spiny). Vlastní konektor příslušenství se cyklit vůbec neměl - zůstává fixní na tom, kterým už je díl skutečně připojen (zvolený při prvotním připojení přes Připoj/magnet).

Oprava: `sortedAccessoryCandidates()` teď filtruje seznam kandidátů jen na tento fixní vlastní konektor (`accEntry.attachedTo.childFaceConnIdx`):

```js
function sortedAccessoryCandidates(accEntry) {
  if (!accEntry.attachedTo) return null;
  const profEntry = accEntry.attachedTo.profEntry;
  if (!placed.includes(profEntry)) return null;
  const fixedChildIdx = accEntry.attachedTo.childFaceConnIdx;
  const list = findAccessoryToProfileCandidatesAllSpins(accEntry, profEntry)
    .filter(c => c.childFaceConnIdx === fixedChildIdx);
  list.sort((a, b) => (a.forcedParentConnIdx * 4 + a.spinIndex) - (b.forcedParentConnIdx * 4 + b.spinIndex));
  return { profEntry, list };
}
```

Cyklus má teď přesně (počet platných ploch profilu) × 4 kroky - žádné opakování stejného vlastního konektoru navíc. Kombinuje se beze změny s dříve opravenou "4 spiny na stěnu" logikou (2x) a "R zachovává pozici na profilu" (2z).

Ověřeno testem test_r_cycle_no_dup.js (7 assertions, real three@0.128.0): počet kroků cyklu (6 ploch × 4 spiny = 24, ne 6×6×4=144), fixní vlastní konektor po celou dobu cyklu, správné pořadí (4 spiny na stěně, teprve pak další stěna), a správné dohledání aktuální pozice v seznamu.

## 2af. Prouzek barvy prostředí přesunut do Menu nástrojů + nové pravidlo pro budoucí UI prvky (2026-08-02)

Robert (mid-turn, během práce na R-cyklu): "a proč není ten pruh barvy nag gradient plovoucí??? pravidlo je jasné, všechny nové prvky patří do menu" + "jako odnímatelné prvky zpět na scenu".

Prouzek na výběr barvy prostředí (`#envColorStripWrap`, viz 2ad) byl přidán jako samostatný plovoucí panel s vlastní absolutní pozicí (`top:56px; right:10px`), MIMO právě dokončené Menu nástrojů (2ac). Robert to opravil a zároveň stanovil **nové standardní pravidlo jdoucí dopředu: každý nově přidaný UI prvek patří od začátku do Menu nástrojů a musí jít vytáhnout ze scény a vrátit zpět stejně jako tlačítka** - ne jako izolovaný plovoucí panel.

Provedená změna:

- `#envColorStripWrap` přesunut z vlastní absolutní pozice do `#toolsMenuList` jako běžná flex-položka (řadí se mezi tlačítka). Plovoucí stav (po vytažení ze scény) teď řeší sdílená třída `.toolFloatingBtn`, stejně jako u tlačítek.
- `makeToolButtonRelocatable(btn, opts)` rozšířen o volitelný parametr `opts.excludeSelector` - pokud `mousedown` začne uvnitř tohoto selektoru, relokace se vůbec nezahájí a gesto zůstává plně v režii vlastního listeneru prvku. Bez tohoto by tažení PO proužku (výběr odstínu) omylem vytahovalo celý prvek ze scény místo změny barvy.
- `TOOLS_MENU_BUTTON_IDS` rozšířen o `"envColorStripWrap"`, nový `TOOLS_MENU_EXCLUDE_SELECTORS = { envColorStripWrap: "#envColorStrip" }` mapuje id položky na její vyloučený vnitřní selektor.
- Šířka proužku zmenšena z 200px na 180px, aby se bezpečně vešla do 230px širokého panelu Menu nástrojů i s paddingem wrapperu (8px 10px) a jeho borderem.
- Samotný výběr barvy (drag po proužku, klik, uložení do `konfEnvHue`) beze změny funkčnosti.

Ověřeno testem test_env_strip_to_menu.js (10 assertions): mousedown přímo na wrapu/popisku spouští relokaci, mousedown na proužku/thumbu relokaci NESPOUŠTÍ, správné mapování id → excludeSelector, JSON round-trip perzistence layoutu (`konfToolsMenuLayout`) funguje shodně pro `envColorStripWrap` jako pro tlačítka, a aritmetika šířky proužku vůči panelu.

## 2ag. Nový nástroj "Obarvit stejné" - hromadné barvení stejných dílů (2026-08-02)

Robert: "připrav k barvení objektů ještě další verzi hromadné barvení stejných prvků ve scéně." Upřesněno přes AskUserQuestion: kritérium shody = stejný katalogový díl (`entry.part.id`), bez ohledu na aktuální barvu, délku či pozici; spouštění = nové samostatné tlačítko vedle "Obarvit díl" (ne checkbox rozšiřující stávající nástroj).

Nový button `btnPaintSameMode` ("🎨🔁 Obarvit stejné") v Menu nástrojů (relokovatelný jako ostatní tlačítka). Mechanika stejná jako u stávajícího "Obarvit díl" (`paintMode`) - zapni režim, najeď myší na díl ve scéně (zvýrazní se), levé tlačítko obarví aktuální barvou z kolečka; živá změna barvy funguje i během tažení po kolečku, pokud je kurzor nad dílem.

Rozdíl oproti "Obarvit díl": funkce `paintEntrySameParts(entry, colorHex)` místo obarvení jen jednoho dílu (+ jeho Join-skupiny) nejdřív najde `pid = entry.part.id`, projde celé pole `placed` a najde VŠECHNY díly se stejným `part.id` - každý z nich (+ jeho případná vlastní Join-skupina, klávesa J) se přidá do cílového seznamu (bez duplicit, `Set` podle reference) a obarví.

Záměrně BEZ další kaskády: pokud je nalezený díl součástí Join-skupiny s JINÝM dílem (jiné `part.id`), tenhle jiný díl se obarví (konzistentní se stávajícím pravidlem "spojené díly = 1 objekt ve všech funkcích"), ale další, s ním nespojené kusy TOHOTO jiného dílu už ne - jinak by klik na jeden díl mohl neočekávaně obarvit zcela nesouvisející kusy jinde ve scéně jen kvůli náhodnému spoji.

Nový režim (`paintSameMode`) se vzájemně vylučuje se všemi ostatními (Obarvit díl, Mikroposuv, Osový posuv) - stejný obousměrný vzor jako u `paintMode` (aktivace jednoho vypne všechny ostatní, guardy v obou směrech).

Ověřeno testem test_paint_same_parts.js (15 assertions): shoda podle `part.id` napříč více kusy, lhostejnost k původní barvě/délce, chování Join-skupiny bez kaskády do nesouvisejících výskytů, fallback pro díl bez `part.id`, a vzájemné vylučování režimů.

## 2ah. R-cyklení mezi již spojenými profily — potvrzené pozice (2026-08-03)

Doplnění k existujícímu R-cyklení pro **už spojené** dva profily (klávesa R na označeném, spojeném dílu cykluje mezi platnými alternativními napojeními na stejného souseda — analogie ke starší R-funkci u příslušenství, viz 2t/2v). Robert prošel všechny kandidáty přímo ve scéně přes diagnostický panel "🔍 Kontrola pozic spoje" (`openJointPositionReviewPanel()` — hover = živý náhled, klik = skutečné přepnutí) a potvrdil dvě oddělené kategorie pozic:

**a) "Krajové" (limitní) pozice — fáze "end" (`sortedProfileJointCandidates`/`profileJointPhase() === "end"`):** diskrétní, pevný seznam kandidátů, kdy se otáčený profil vždy nachází v KONCOVÉ pozici vůči pevnému (rodičovskému) profilu a jeho čelo přesně lícuje s rovinou čela rodiče (žádný přesah, žádný průnik). Potvrzené jako správné (2026-08-03):
- Čelo — rovné prodloužení
- Čelo — roh, natočení 90°
- Čelo — roh, natočení 270°
- Čelo — roh, svisle vzhůru
- Čelo — roh, svisle dolů

Implementace: `MAGNET_BASE_OPTIONS`/`MAGNET_COMPASS_DIRS` (6 kanonických orientací × kompasové směry), `applyConnectionCandidate()` — u "nahoru" (childConnIdx 1) je potřeba ruční doplnění zpětného zasunutí (childHalf pullback), protože `attachEntryToParent()` ho pro `childConnIdx !== 0` vždy vynechává (`isVerticalJoint`); u "dolů" (childConnIdx 0) totéž zajišťuje `attachEntryToParent()` sama, protože tam `isVerticalJoint` typicky vyjde `false`. Korekce je umístěná přímo v `applyConnectionCandidate()` (ne ve `stepProfileJoint()`), aby platila stejně pro živý hover-náhled v panelu i pro skutečný klik/R-press.

**b) Kontinuální pozice podél délky — fáze "wall" (`kind:"mid"`/`kind:"face"` konektory, T-spoj a plocha-na-plochu):** Robert upřesnil (2026-08-03): "dále budou existovat navíc pozice průběžně po celé délce profilu, podle toho kam si uživatel profil posune." Na rozdíl od krajových pozic výše tahle kategorie NENÍ diskrétní seznam — díl smí sedět KDEKOLI podél délky rodiče, přesně tam, kam ho uživatel sám umístí/přetáhne. R-cyklení mezi kandidáty v téhle fázi (T-spoj ↔ plocha-na-plochu) proto při přepnutí zachovává aktuální pozici podél osy rodiče (t0/t1 mechanismus ve `stepProfileJoint()`), jen ořízne o `clampAccessoryToProfileLength()`, pokud by díl přesahoval přes konec rodiče — nikdy neskáče na pevný bod (střed/konec).

**Oprava textu (2026-08-03):** `jointCandidateReviewLabel()` v panelu "Kontrola pozic spoje" původně hlásila OBA svislé kandidáty (nahoru i dolů) stejným textem "(svisle vzhůru)" — kontrolovala jen `opt.orient === "vertical"`, ne `opt.childConnIdx`. Opraveno, text teď rozlišuje "(svisle vzhůru)" / "(svisle dolů)".

**Zdroj pravdy / ověření:** Node.js harness `harness_test.js` (candidateSignature, 2-loop fáze, wall-fáze pozice+clamp, end-fáze stejný konektor, přesah nahoru/dolů obě ~0mm) + přímé potvrzení Robertem v panelu "Kontrola pozic spoje" ve skutečné scéně.

## 2ai. Tlačítko "Připoj" nově spojuje i 2 libovolné profily (2026-08-03)

Robert: "můžeme se posunout s rotací profilů kolem sebe?" — upřesněno přes AskUserQuestion na "Rotace vůči připojenému sousedovi" (už PŘIPOJENÝ profil mění orientaci napojení vůči sousedovi — ne nový typ spoje, ale jiná varianta stávajícího), pak doplněno: "aplikujme to na 2 profily nikoli z tvarů ale libovolné 2 Profily ve scéně které připojím tlačítkem připojit."

Rotace mezi už spojenými profily (R-cyklení) už existovala od sekce 2ah — chybělo jen samotné PRVNÍ spojení dvou libovolných, dosud nespojených profilů ve scéně, mimo presety/AI stavbu. Řešení: stejné tlačítko "Připoj" (`btnAttachAccessory`, dřív jen 1 profil + 1 příslušenství, viz 2v) teď navíc rozpozná výběr 2 PROFILŮ a spojí je funkcí `attachSelectedProfilesTogether(childEntry, parentEntry)` — první označený profil (child) se pohne/otočí, druhý (parent) zůstává na místě.

Volba napojení: `findConnectionCandidates(childEntry, parentEntry)`, seřazeno stejně jako R-cyklení (podle `forcedParentConnIdx` vzestupně) — protože "čelové" konektory mají index 0/1 (viz `computeConnectorsLocal`), první klik na Připoj typicky zvolí rovné/rohové napojení konec-na-konec (stejná pozice, na kterou by R-cyklení stejně jako první došlo).

**Klíčová oprava (jinak by R po prvním spojení nefungovalo vůbec):** `applyFaceToFaceCandidate` (plocha-na-plochu / T-spoj, tzv. "wall" fáze) sama o sobě nezapisuje `entry.lastJoint` — jen `attachEntryToParent`/`registerJoint`/`stepProfileJoint` to dělají. `sortedProfileJointCandidates` (základ R-cyklení) bez `lastJoint` rovnou vrátí `null`. `attachSelectedProfilesTogether` proto po `applyConnectionCandidate()` vždy ručně zapíše `lastJoint` na OBOU stranách (včetně `candidateSig`) — stejný vzor, jaký už `stepProfileJoint` dělá na konci každého svého kroku. Díky tomu funguje R/rotační prstenec hned po prvním kliknutí na Připoj, bez nutnosti nejdřív "protočit" spoj jinudy.

Opakovaný klik na Připoj na už spojenou dvojici = čistý přepoj (nejdřív `detachProfileJoint` na straně, co už měla jiný spoj, pak nové spojení) — stejný princip jako `accEntry.attachedTo → detachAccessory` u příslušenství.

**Ověřeno:** Node.js harness (`harness_test.js`, Test 9a–9c) — obecné spojení 2 libovolně umístěných/pootočených profilů, okamžité R-cyklení hned po spojení (signatura kandidáta se mění), opakovaný Připoj beze zdvojení účetnictví (`jointCount`), a specificky vynucený "wall" (plocha-na-plochu) kandidát jako první spoj s následným úspěšným R-cyklením (historicky nejrizikovější případ). `attachEntryToParent`, `applyFaceToFaceCandidate`, `clampAccessoryToProfileLength`, `stepProfileJoint`, `registerJoint`, `linkJointPeers`, `findConnectionCandidates` zůstávají beze změny (diff/awk porovnání před/po nasazením). **NEOVĚŘENO RUČNĚ V PROHLÍŽEČI** — Robert by měl v reálné scéně označit 2 libovolné, dosud nespojené profily (Mikroposuv nebo Posun myší) a zkusit Připoj + R.
> **OVĚŘENO ŽIVĚ (bot8, 2026-08-20, headless produkční scéna, reálná .glb):** 2 volně umístěné profily 40x40 → `attachSelectedProfilesTogether`: výchozí spoj wall fáze (T), flush (1 osa 0/0 + 2 plné překryvy), `lastJoint` na obou, `stepProfileJoint` hned mění signaturu. Připoj profil+příslušenství (přes skutečný výběr `selectedMoveEntries`): připojeno bez mezery, jointCount 0 (příslušenství se neúčtuje) i po opakovaném kliku, licPeers symetrické, U čistě odpojí.

## 2aj. Doraz na konci profilu (2ai/2m) neplatí pro "end-end-straight" (rovné prodloužení) (2026-08-03)

Robert otestoval 2ai v reálné scéně a nahlásil: spojení + R fungovalo, ale po ručním posunu myší další R press nesmyslně měnil pozici připojeného profilu vůči pevnému sousedovi. Potvrzeno (AskUserQuestion): oba spojované profily byly **stejně dlouhé**.

**Root cause:** `clampProfileToJointPartners` (doraz na konci profilu, zaveden týž den dříve) rozlišovala jen podle rovnoběžnosti délkových os obou profilů, aby přeskočila kolmé (rohové) spoje. Jenže "end-end-straight" (rovné prodloužení v přímce, dva profily za sebou) je *taky* rovnoběžné — a u tohoto typu spoje je připojený profil správně a úmyslně celý MIMO délku svého souseda (pokračuje za jeho koncem, to je celý smysl prodloužení). Doraz "nesmí přesahovat délku souseda" na to aplikovaný nedává smysl a nesmyslně profil posouval zpět dovnitř souseda.

**Oprava:** nová pomocná funkce `profileOverlapsParentLength(entry, profEntry)` — čistě geometrický test, jestli se projekce profilu na osu souseda vůbec substanciálně (>5mm) překrývá s vlastním rozsahem souseda `[0,L]`. Pokud ne (typicky "end-end-straight"), doraz se pro tohoto partnera vůbec nezkouší. Sdílená `clampAccessoryToProfileLength` (používaná i 4 dalšími, již ověřenými místy pro příslušenství) zůstává beze změny — nový test je jen dodatečná podmínka uvnitř `clampProfileToJointPartners`.

**Ověřeno:** Node.js harness — čerstvě spojený "end-end-straight" pár stejné délky už doraz nepřesune (dřív posun o celou délku souseda, 1000mm v testu). Všechny dřívější scénáře (wall-fázový doraz na kratším připojeném profilu, R-cyklení po ručním posunu, opakované R-cykly, kolmý spoj) beze změny výsledku. **NEOVĚŘENO RUČNĚ V PROHLÍŽEČI** — Robert by měl zopakovat přesně nahlášený scénář (Připoj, R, posun myší, R znovu) a potvrdit, že pozice už zůstává na místě.

## 2ak. Připoj (2ai) preferuje "wall" fázi místo "end" jako výchozí spoj (2026-08-03)

Robert otestoval 2aj a nahlásil dál: "při stisku R se pohyblivý profil objeví znovu na konci profilu." Skutečný root cause byl jinde, než diagnostikováno v 2aj — v samotném výběru výchozího kandidáta uvnitř `attachSelectedProfilesTogether`.

Původní řazení (jen podle `forcedParentConnIdx` vzestupně) vždy vybralo "end" fázi jako první kandidát (čela mají index 0/1). "End" fáze má ale jen diskrétní, pevné pozice (viz 2ah část a) — R-cyklení mezi jejími kandidáty záměrně NEzachovává ručně nastavenou pozici (na rozdíl od "wall" fáze, viz 2ah část b). A protože `profileJointPhase` filtr v `sortedProfileJointCandidates` drží R-cyklení natrvalo ve STEJNÉ fázi, jakmile je spoj jednou v "end" fázi, R z ní už nikdy nepřejde do "wall" fáze. Výsledek: Připoj + R vždy skončil v "end" fázi, a každý další R (i po ručním posunu myší) proto nutně skočil zpět na pevný konec profilu.

**Oprava:** stejný princip, jaký už existuje pro příslušenství (`attachSelectedAccessoryToProfile`, 2026-08-02: boční stěny mají přednost před čelem — `kindRank`), zobecněný přes `profileJointPhase()` (zahrnuje navíc "mid"/T-spoj): kandidáti se teď řadí tak, aby "wall" fáze (T-spoj/plocha, kontinuální pozice po celé délce souseda) měla přednost před "end" (pevné krajní pozice) — "end" zůstává jen jako záložní volba, když žádný wall kandidát neexistuje.

**Ověřeno:** Node.js harness — Připoj na 2 libovolné kompatibilní profily teď vybere T-spoj namísto rovného prodloužení. Všechny existující testy (9b, 9c, 10, 10b, 11, 12) beze změny výsledku. **Živě potvrzeno bot8 2026-08-20** (headless produkční scéna: výchozí fáze po Připoj = "wall"). `attachEntryToParent`, `applyFaceToFaceCandidate`, `clampAccessoryToProfileLength`, `clampProfileToJointPartners`, `stepProfileJoint`, `registerJoint`, `linkJointPeers`, `findConnectionCandidates`, `attachSelectedAccessoryToProfile` zůstávají beze změny. **NEOVĚŘENO RUČNĚ V PROHLÍŽEČI** — Robert by měl znovu zopakovat scénář (Připoj, R, posun myší, R znovu) — nový výchozí spoj by měl být T-spoj/plocha, pozice by se po R už neměla měnit.

## 2al. Dvoufázový doraz + přeskok na čelo pro 2 spojené profily při tažení myší (2026-08-03)

Robert ukázal screenshot z reálné scény: při tažení připojeného příslušenství (úhelníku) myší k okraji profilu se zobrazí tooltip "⏸ zastaveno - stěna lícuje s čelem profilu, táhni dál pro přeskok na čelo" — dvoufázový mechanismus (zastavení na rovině čela → další tažení navíc → přeskok/přeorientace na skutečné čelo), který u příslušenství existuje od 2026-08-02. Požádal o stejnou funkci pro 2 spojené profily.

Předchozí doraz pro profily (`clampProfileToJointPartners`, zaveden týž den) měl jen první fázi (prosté zastavení, žádný přeskok). Doplněny 2 nové pomocné funkce po vzoru příslušenství: `wallPeerOfProfile(entry)` (obdoba `attachedFaceProfileOf` — najde jediného "wall" partnera z `licPeers`) a `bestProfileEndCandidateAtConnector(childEntry, parentEntry, endConnIdx)` (obdoba `bestEndCandidateAtConnector`, preferuje "end-end-straight" před "end-end-corner"). `updateAxisMoveDrag` teď při tažení jednoho spojeného profilu replikuje přesně stejnou dvoufázovou logiku jako u příslušenství (stav `st.profEndClampProf`/`profEndClampSide`/`profEndClampBaseViol` — mirror `st.endClampProf` atd.), živý náhled přeskoku je jen vizuální (skipBookkeeping). Skutečné přepojení (zrušení staré "wall" vazby na obou stranách + reálná aplikace nového "end" spoje + `lastJoint` na obou stranách) se zaznamená až v `finishAxisMoveDrag` při puštění tlačítka (`st.pendingProfileSnap`).

**Ověřeno:** Node.js harness (Test 13) — přesná simulace celého tažení na kratším (300mm) profilu připojeném T-spojem uprostřed delšího (1000mm): pohyb v mezích beze zásahu, malý přesah (15mm) → zastaveno bez skoku, větší přesah (45mm, nad 20mm práh) → živý přeskok na rovné prodloužení, simulované puštění tlačítka → skutečné přepojení s korektním `lastJoint` na obou stranách, R-cyklení na tomto čerstvém "end" napojení funguje hned. `wallPeerOfProfile` na nespojeném profilu správně vrací `null`. Všechny dřívější testy beze změny výsledku. **NEOVĚŘENO RUČNĚ V PROHLÍŽEČI** — Robert by měl vyzkoušet přesně scénář ze screenshotu (tažení spojeného profilu myší ke konci souseda) a potvrdit, že se chová stejně jako u příslušenství.
> **Částečně ověřeno živě (bot8, 2026-08-20, Playwright skutečná myš na canvasu):** fáze 1 u PŘÍSLUŠENSTVÍ - reálné tažení úhelníku připojeného na čele podél profilu skončilo přesně zastavením lícem (flush) na rovině čela, bez přeskoku ani průniku. Fáze 2 (overshoot → přeskok → commit při puštění) při UI tažení nezreprodukována (pointerdown hit-test v headless prostředí se netrefil do dílu) - zůstává kryta produkční kopií v harnessu (Test 13) a Robertovým denním používáním.

## 2am. R-otáčení profil–profil na stěně: jen 4 kolmé T pozice (2026-08-04)

Robert: "otáčení profilu rozbité, některé pozice profil umístí rovnoběžně s rodičem" + "musí se před otáčením ukládat pozice a při otáčení tuto pozici načíst, takže se tím pádem otáčí na chtěném místě". Potvrzená cílová podoba: wall smyčka (čelo na stěně souseda) = **jen kolmé T pozice ve 4 směrech** (svisle vzhůru / svisle dolů / do boku 1 / do boku 2), vždy otáčení **na místě**, kam si uživatel profil posunul.

Dřívější wall smyčka měla 2× svislý T-spoj + 6× rovnoběžné "bok k boku" — vodorovné kolmé T směry chyběly (střed profilu má "mid" konektor jen na jedné průřezové ose) a rovnoběžné přiložení není rotace.

**Změny:** (1) `findConnectionCandidates` (mid větev) generuje 4 kolmé směry — druhá osa dopočtena vektorovým součinem délkové osy rodiče × normály mid konektoru; (2) `sortedProfileJointCandidates` filtruje `face-face-parallel` z R-cyklení i z panelu "Kontrola pozic spoje" (pro prvotní připojení přes panel "Možnosti napojení" zůstává bok-k-boku dostupné); (3) rozlišené popisky 4 směrů. Otáčení na místě zajišťuje stávající t0/t1 mechanismus ve `stepProfileJoint` (uložení projekce na osu rodiče před krokem, obnovení po kroku) + ořez `clampAccessoryToProfileLength`.

**Ověřeno:** harness Test 16/16b — přesně 4 kandidáty, žádný rovnoběžný, 6× R po ručním posunu na 700 mm: pozice stále 700.0, orientace vždy kolmá, cyklus dokola, všechny 4 pozice korektní dotyk bez průniku. **NEOVĚŘENO RUČNĚ V PROHLÍŽEČI.**

**Známý otevřený limit (samostatný budoucí úkol):** kandidáty se počítají z pevných světových orientací (`MAGNET_BASE_OPTIONS`, tolerance ~25°) — u rodiče pootočeného mimo pravé úhly vyjdou pozice křivé o úhel rodiče (ověřeno harness Testem 15), u 45° většina kandidátů zmizí. Oprava = počítat kandidáty relativně k natočení souseda.

## 2an. Roztahuj (2026-08-31, NOVÉ tlačítko/funkce — jméno recyklováno po smazaném 2p) — živé protažení příčky + 2 navazujících svislých profilů

Robert, doslovně: "funkci protažení zadní nohy (členité nohy) dolů/nahoru a návazně s tím posun příčky a zkrácení/natažení spodní zadní nohy chci mít jako živou funkci v ručním režimu scény. pro všechny typy nohou profil 30x30, 40x40... aplikuj to na tlačítko Roztahuj (původní funkci toho tlačítka smaž)."

**Transparentní poznámka:** tlačítko "↔ Roztahuj" s PŮVODNÍ funkcí (2p výše — povolení modrých natahovacích šipek na ručně poskládaném rámu) bylo už smazané (Robert, 2026-08-22). V době tohohle zadání tedy v kódu žádné tlačítko "Roztahuj" nebylo — tlačítko "↕ Roztahuj" popsané tady je NOVÉ, se stejným jménem, ne návrat/oprava původního.

**Mód tlačítka (ne jednorázová akce):** `btnRoztahuj` přepíná `roztahujMode` (stejná konvence jako "Obarvit díl"/"Mikroposuv"/"Posun myší" — vzájemně se vylučují, aktivace jednoho vypne ostatní). V zapnutém režimu: klik+tažení na platnou příčku ji živě posouvá po světové ose Y; klik na cokoli jiného (nebo pravé tlačítko myši, nebo opětovný klik na tlačítko) režim ukončí.

**Obecný geometrický vzor** (viz `KOMPONENTY_EUROBOXY.md` sekce "Uzavření výřezové nohy" + `PRAVIDLA_SPOJU.md` "celá plocha čela"): vodorovná "příčka" (profil) dosedá jedním koncem/plochou na HORNÍ konec jedné svislé nohy (cap-styl) a druhým koncem se BOČNÍ plochou dotýká DALŠÍ svislé nohy (T-styl) — všechny 3 díly STEJNÉHO průřezu (30×30 nebo 40×40, detekováno za běhu z `cross_section_mm`, nikdy hardcoded). Tažením příčky nahoru/dolů (jen světová osa Y — X/Z zůstávají fixní, `camera.up=(0,1,0)`, viz komentář "labely Y/Z jsou prohozene" jinde ve `scene.html` pro rozlišení UI-labelu vs. skutečné THREE osy) se OBĚ nohy délkově přizpůsobí: každá drží svůj VZDÁLENÝ konec pevně na místě, BLÍZKÝ konec ("šev" u příčky) sleduje novou výšku příčky.

**Detekce je GENERICKÁ** (`roztahujFindPartners(crossbarEntry)`, `webapp/scene.html`) — žádné hardcodované role/názvy dílů (na rozdíl od scratch skriptu `scripts/tmp_2026-08-30_build_depth_variants_both.js`, jehož řetězce `sloupek-pred-podbehem`/`pricka-uzavreni-vyrezu`/`zadni-svislice-nad-zarezem` jsou jen bookkeeping toho skriptu — appka je nikdy nevidí): pro každý jiný umístěný profil stejného průřezu s KOLMOU (skoro přesně svislou, `dot` s `(0,1,0) > 0.9`) délkovou osou se ověří, jestli některý jeho koncový ("end") bod leží (v rámci tolerance 2mm) na "švu" příčky (spodní NEBO horní plocha příčky podle její tloušťky T) A současně se s příčkou fyzicky dotýká (`profilesStillTouching`, stejná funkce jako zbytek appky pro "ještě se dotýká?"). Profil dotčený jen VPROSTŘED své délky (žádný konec u švu — např. plný sloupek, kolem kterého příčka jen prochází bokem) testem projde jako NE-partner automaticky — matematika protažení je pro cap-styl i T-styl STEJNÁ (viz níže), rozdíl je jen v tom, na které straně švu (±T/2) daný konec leží, a to se měří přímo z aktuální geometrie, ne z pevného předpokladu který styl je který konec.

**Sane clamp (Robert: nikdy nulová/záporná délka):** `roztahujComputeForY(desiredY, verticals, minLen, maxLen)` v `webapp/js/scene-geometry-shared.js` — čistá numerická funkce (žádné THREE/DOM), spočítá pro požadovanou (myší taženou) Y příčky OMEZENOU Y tak, aby délka OBOU noh zůstala v `[30, 3000]` mm (stejný rozsah jako běžné protažení oranžovou šipkou, `DRAG_MIN/MAX` u `dragState`) — tažení za hranici klamp zastaví, negeneruje degenerovanou/zápornou geometrii. Umístěna ROVNOU do sdíleného souboru (ne duplicitně jen ve `scene.html`), protože nemá žádnou závislost na THREE/DOM a je potřeba i pro Node.js ověření (`scripts/2026-08-31_roztahuj_verify.js`) — stejný princip jako `applyLengthScale` (viz "pravidlo pro budoucí funkce" v hlavičce tohohle souboru). Samotná resize aplikace na živý díl znovupoužívá `applyLengthScale(entry, scaleFactor, fixedConnIdx, endIdxA, endIdxB)` — vzdálený (fixní) konec zůstává na místě, blízký se posune s novou délkou, žádná nová transformační logika.

**Mechanika tažení myší:** stejný princip jako existující protažení oranžovou šipkou (`computeScreenDragAxis`/`alongScreenAxis`/`dragWorldToScreen`, `DRAG_MIN_SCREEN_AXIS_PX`) — promítnutí SVĚTOVÉ osy (tady vždy pevná Y, ne vlastní osa dílu) do 2D pixelů na obrazovce a tažení počítané jako poměr posunu myši podél téhle promítnuté osy, ne jako přímý 3D průsečík paprsku (ten je numericky nestabilní při pohledu téměř podél osy — viz historie u `dragState`). Nová pomocná funkce `computeScreenAxisForWorldDir` jen zopakuje stejný výpočet pro fixní směr `(0,1,0)` místo osy konkrétního dílu, žádné duplicitní reimplementování `alongScreenAxis`/`dragWorldToScreen` (ty zůstávají obecné, beze změny).

**Ověření (mechanická interakce myší nejde v tomhle prostředí simulovat):** `scripts/2026-08-31_roztahuj_verify.js` postaví reálnou GLB geometrii (`Object_7.glb`, 30×30 profil) přesně podle `buildVyrezAtDepth(326)` (D=326mm scénář z `KOMPONENTY_EUROBOXY.md` "Uzavření výřezové nohy"), zavolá `roztahujFindPartners`+`roztahujComputeForY`+`applyLengthScale` 1:1 stejnou cestou jako živá scéna a ověří: (1) detekce najde PŘESNĚ 2 partnery — `sloupek-pred-podbehem` a `zadni-svislice-nad-zarezem` — a SPRÁVNĚ VYLOUČÍ `predni-svislice` (ta je jen bytostně dotčená uprostřed své délky, žádný konec u švu); (2) pro 2 různé tažené Y (460 a 330, oproti počáteční 410) vyjdou délky/pozice obou noh přesně podle ručního výpočtu (např. Y=460 → sloupek 445mm, zadní svislice 475mm, obě konfirmováno i na reálné `worldConnectorsOf` pozici po `applyLengthScale`, ne jen na čísle); (3) extrémní tažení (Y=-500) se správně zastaví na klampu (sloupek na minimální 30mm, crossY=45). Všech 20 kontrol prošlo (`node scripts/2026-08-31_roztahuj_verify.js`, exit 0).

**UI:** `<button id="btnRoztahuj">` v horní liště vedle "🎓 Naučit napojení" (btnAttachTeach), zařazeno i do `TOOLS_MENU_BUTTON_IDS`/skupiny `joints` (viz "Menu nástrojů" 2ac) — vytáhnutelné/vratitelné jako ostatní tlačítka.

## Tlačítka horní lišty scény bez vlastní dokumentace (doplněno 2026-08-31, na Robertovu žádost "jsou ještě nějaké pravidla/postupy někde bokem" — konkrétně "funkce tlačítka ze scény")

Audit `webapp/scene.html` odhalil 9 živých tlačítek horní lišty, jejichž chování dosud nebylo zapsané v žádném z tematických souborů (jen v `title` atributu tlačítka samotného). Popisy níže jsou tooltip texty z kódu, zkráceně:

- **🔗 Spočítej spoje** (`btnFindJoints`) — bez výběru spočítá spoje v CELÉ scéně, s výběrem jen v označené sestavě. Počítá jen skutečně použité konektory (Připoj/Připoj2/AI/presety) — staré "měkké" spoje zjištěné jen dotykem (Lícování, automatické spojení při tažení) bez přesného konektoru se z ceny odečtou.
- **📎 Připoj2** (`btnAttachProfiles2`) — označ přesně 2 PROFILY, klikni, spojí je (vývojová verze "R2" spojování profil↔profil, vychází ze stavu "R1").
- **🧲 Dosah magnetu** (`btnMagnetReachToggle`) — zapne ve scéně kroužky na volných čelech příslušenství (poloměr = dosah magnetu); tažením za kroužek dosah živě zvětšíš/zmenšíš pro všechny kroužky najednou. Vypnuto = kroužky zmizí, na funkci magnetu to vliv nemá.
- **🔗 Připoj kloub** (`btnAttachKloub`) — označ přesně 2 profily + 1 kloub (nebo jiný díl s naučeným čelem i stěnou), klikni — oba profily se rovnou nasadí čelem na kloub, bez tažení/magnetu.
- **🪵 Deska do drážky** (`btnInsertBoardGroove`) — označ 2 rovnoběžné profily nebo (i neúplný) rám ve 2 směrech — vloží desku PR10 správné velikosti do jejich drážek (hrana zajede 10mm pod profil).
- **🪵 Deska na profily** (`btnInsertBoardTop`) — označ profily tvořící uzavřený/polouzavřený rám — položí desku PR10 navrch, o 2mm menší než vnější rozměr rámu.
- **🔍 Pozice úhelníku** (`btnUhelnikPoseReview`) — odklikání správné polohy dílu v rohu: najetím myší náhled, kliknutím se poloha uloží (na server, per díl) a Automat ji dál používá.
- **🟢🟡 Volné plochy** (`btnFreeConnectorsDebug`) — ověřovací/ladicí nástroj (Robert 2026-08-16: "dej do scény tlačítko které všechny volné stěny označí zeleně a volná čela žlutě") — vizualizuje `usedConn`/`attachedTo` data, žádná nová geometrie.
- **🩺 Diagnostika volných ploch** (`btnFreeConnDiag`) — navazující diagnostika: klik na plochu, kterou "🟢🟡 Volné plochy" označilo špatně, vypíše přesný rozbor PROČ, s tlačítkem na zkopírování reportu do chatu.

Zbytek horní lišty (Krok zpět, Kopírovat, Připoj, Uzemnit, Export FBX, Kontrola ploch, Kontrola pozic spoje, Automat/Úhelník/Rožek, Naučit napojení, Obarvit díl/stejné, Barva označení) je buď samovysvětlující z názvu, nebo už popsaný jinde v tomhle souboru (Automat → sekce 2k výše, Naučit napojení → `attach_learning_log` viz `PRAVIDLA_SPOJU.md`).


---

## 2az. ⭐ VRTACÍ KÓTY — pravidla pro NOHU (Robert 2026-09-10)

Přepínač **🔩 Vrtací kóty** v horní liště (`toggleDrillingDims`), nezávislý
na režimu kótování 1/2/3. Měří **na OSU** napojeného profilu, ne k jeho
stěně — střed otvoru sedí na ose připojovaného dílu.

Robert 2026-09-10 zadal pro nohu čtyři pravidla. Doslovně:

1. *„vrtací kóty na nohách obecně: vrtají se nohy / na nohy je navázán profil
   příčka nebo nosník (podélník) / vrtací bod na noze je ten, kde má napojený
   profil svůj střed"*
2. *„vždy absolutní"* — každá kóta od jedné základny, **ne po řetězu**
3. *„vrtací kóty nohy kótujeme od spodní hrany"*
4. *„vrtací kóty se buď čelní nebo boční, tzn. 2 řady, znač u toho č nebo b"*
   + *„čelní kóta souvisí s příčkou, boční kóta navazuje na nosník"*
   + *„rozlišil bych vrtací kóty čelní/boční podle barvy"* → *„písmenem i barvou"*

### Co z toho platí v kódu (`computeDrillingDimensionSegments`)

| | noha (svislý profil) | lůžko (vodorovné profily) |
|---|---|---|
| základna | **spodní hrana** nohy | začátek osy |
| hodnoty | **absolutní** od základny | **řetězené** (kraj→otvor1, otvor1→otvor2) |
| kóta na konec profilu | **není** (konec není vrtací bod) | je |
| řady | **dvě**, `č` a `b` | jedna |
| barva popisku | `č` zelená `#4ad1a0`, `b` fialová `#d17ad1` | oranžová `#e0a04a` |

⚠️ **Pravidlo pro nohu se NETÝKÁ lůžka.** Robert to musel zopakovat třikrát
(*„nech lůžko na pokoji"*, *„pravidlo pro nohy se netýká lůžka"*, *„okamžitě
vrať ty kóty na nosnících do původního stavu"*), protože jsem to nejdřív
aplikoval na všechno. Řetězení na lůžku si Robert vyžádal 2026-08-16 a
platí dál. Vrtací kóty lůžka mají vlastní pravidlo (15 / 415 / 816 / 1217
od začátku profilu) — viz `KOMPONENTY_EUROBOXY.md`.

### Jak se pozná čelní a boční řada

**Ne podle názvů dílů** — geometricky, aby to fungovalo na jakkoli natočeném
regálu v jakémkoli autě: odvodí se osa **délky regálu** z rozmístění svislých
profilů (noh), a pak platí:

* napojený díl běží **podél** délky regálu → nosník/podélník → **`b`**
* napojený díl běží **napříč** → příčka/spojnice → **`č`**

### Past, kterou to odhalilo

`groupJointCandidatesByThroughProfile()` **slučuje** intervaly dílů ležících
ve stejné výšce — tedy přesně nosník a spojnici, které mají být ve dvou
různých řadách (dva otvory ve dvou stěnách nohy). Proto noha pracuje se
**surovými dvojicemi** z `findProfileJointCandidates()`, ne se slučovanými
intervaly. Lůžko slučované používá dál.

Dva díly **téhož** směru ve stejné výšce se naopak dál berou jako **jeden**
otvor.

### Otevřené

Profil `cap` (horní část zadní nohy) vychází s kótou **−15 mm**, protože
`spojnice-horni` sedí kousek pod jeho spodní hranou. Není rozhodnuto, jestli
je záporná kóta u něj legitimní, nebo tam kóta nemá být vůbec — čeká na
Roberta.

## Pravidlo profilů - materiály ve scéně a panel jejich vlastností

Robert 2026-09-10 (postupně): *„tak kovovost co je ve scene, se nemuze
aplikovat na vsechno, jen na profily"* → *„ve scene musi mit každý materiál
vlastní nastavovani vlastností (kovovost atd)"* → *„měl by nato být dalsí
panel"*. Panel je `webapp/js/scene/material-panel.js`, otevírá se tlačítkem
z panelu tlačítek dole uprostřed.

### ⭐ Materiál se ve scéně pozná PODLE BARVY, ne podle pole „materiál"

Žádný díl nenese jméno materiálu. Přiřazení jde výhradně přes
`shop_products.color_hex` (resp. `cfg_dily.color_hex`), který se dohledá
v paletě `partMaterialColor` (`catalog-panels.js`); z ní se odvozují
`HEX_TO_METALNESS`/`HEX_TO_ROUGHNESS`. Tři důsledky, všechny ověřené
provozem:

1. **Dva materiály nesmí sdílet odstín.** Jinak je od sebe nelze rozlišit
   ani ovládat zvlášť. Proto má MDF vlastní `#5c626a` — není to kosmetika.
2. **Přiřazení se musí dělat proti PŮVODNÍMU katalogovému odstínu**, ne
   proti aktuálně nastavenému. Panel drží `PUVODNI_HEX` zachycený před
   načtením uložených hodnot; bez toho výběr barvy nefungoval vůbec
   (změna barvy materiálu odpojila už položené díly, protože ty měly
   pořád starou barvu).
3. **Špatně zařazený díl se projeví jako „ovladač nefunguje".** Není to
   chyba panelu — je to chyba dat.

### Zařazení dílů (stav k 2026-09-10)

| materiál | odstín | co na něm je |
|---|---|---|
| `alu` | `#c9cdd1` | profily — **ovládá se HDRI posuvníky**, v panelu materiálů schválně není |
| `zinc` | `#b7bcc0` | odlitky, **úhelníkové spojky** 3045/3207/3216 |
| `plast_svetly` | `#666c73` | euroboxy 3788/3793/3794/3795/3796 |
| `mdf` | `#5c626a` | výplně/dna horního bloku (3939) |
| `black` | `#242424` | záslepky |
| `guma` | `#1c1c1e` | pryžové díly |

**Úhelník je odlitek, ne plast** (Robert 2026-09-10: *„uhelník je odlitek,
ne plast !"*). Do 2026-09-10 měly úhelníkové spojky v DB odstín plastu,
takže na ovladač zinku nereagovaly — Robert to hlásil dvakrát, než se
našla příčina. Opraveno přímo v `shop_products.color_hex`, záloha
`backups/2026-09-10_uhelniky_plast_na_zinek.json`. Neplete se to s
dřívějším *„úhelníky nejsou ze stejného materiálu jako profily"* ani
*„úhelníky nejsou lesklé"*: zinek má metalness 0,45 (alu 0,6) a roughness
0,55 (alu 0,35), tedy je matnější než profil.

**POZOR (ověřeno audit bot9, 2026-09-12): 3045/3207/3216 mají DNES ZNOVU
`color_hex='#4d4d4d'`, mimo paletu výše** - stejně jako 76 ze 122
viditelných produktů katalogu. Díly mimo paletu dostávají fallback
materiál (metalness 0.35/roughness 0.4), ne zinek/plast_svetly/mdf dle
tabulky. Před spoléháním na tabulku výše ověř živě
`SELECT id,color_hex FROM shop_products WHERE id=...`.

### Kam se hodnoty ukládají a kam NE

Panel píše do `localStorage` (`konfMat_<klic>`) — každý si ladí svoje.
Renderovací větev `scripts/2026-09-09_turntable_job.py` má **vlastní kopii**
palety (`PART_MATERIAL_*`) a o `localStorage` neví: ta kopie ale slouží jen
jako fallback, když je `color_hex` prázdný — `resolve_material()` jinak bere
`color_hex` přímo z DB. **Změna zařazení dílu v DB se tedy do produktových
renderů propíše sama; změna čísel v panelu ne** (tu je nutné přepsat i tam).
