---
name: 3d-scena-spoje
description: Pravidla a ověřovací nástroje pro geometrii spojů profilů/příslušenství ve 3D scéně konfigurátoru (webapp/scene.html) - žádné zanoření, T-styl spoje, konvence pro nohy/police. Použij PŘED jakoukoli úpravou scene.html týkající se napojování dílů, PŘED stavbou/úpravou testovací sestavy v custom_shapes, nebo když se řeší "proč se díly zanořují/nedosedají/vypadají zle spojené".
---

# 3D scéna — pravidla spojů profilů a ověřovací nástroje

Tenhle skill existuje, aby se **stejná chyba nemusela objevovat a opravovat pokaždé znovu** - shrnuje, co se v projektu (2026-07 až 2026-08) opakovaně zjistilo o geometrii spojů, a dává k dispozici HOTOVÝ, ověřený kód místo psaní vlastního znovu od nuly.

## ONBOARDING — nový bot začíná PŘESNĚ tady, v tomhle pořadí

Cíl: po projití těchto kroků umíš totéž, co bot8 uměl na konci 2026-08-19 — stavět/opravovat geometrii spojů a DOKÁZAT měřením, že je správně.

1. **Přečti `VLASTNOSTI_PROFILU.md`** (kořen repa) — od 2026-08-31 je to jen ROZCESTNÍK s ⭐ blokem nadřazených pravidel + odkazy na 8 tematických souborů (`PRAVIDLA_SPOJU.md`, `PROFILY_KATALOG.md`, `PRISLUSENSTVI_PRIPOJENI.md`, `TVARY_PREDNASTAVENE.md`, `TVARY_VLASTNI.md`, `NASTROJE_SCENY.md`, `KAROSERIE_UMISTENI.md`, `KOMPONENTY_EUROBOXY.md`). Přečti rozcestník + otevři jen ten soubor, kterého se tvůj úkol týká.
2. **Přečti posledních ~150 řádků `AGENTS_LOG.md`** — co se dělalo naposledy, jaké chyby se právě řešily.
3. **Přečti `WORKFLOW.md`** — multi-bot disciplína: `BOT_ID=botN` na každém commitu (hook to vynucuje), `scripts/lock.sh acquire/release <bot> "<pozn>" --wait` pro `DEPLOY_LOCK.json` před zásahem do `webapp/*`/`api/app.py`, nikdy `git add -A`.
4. **Připrav prostředí a ověř baseline:** `npm install` v ROOTU repa (ne ve `scripts/`), pak `node scripts/2026-08-19_regression_scene/run_all.js` — MUSÍ skončit "VSECH 10 SKRIPTU OK". Když ne, něco je rozbité UŽ PŘED tebou — zjisti co, NEŽ začneš cokoli měnit (poslední známý zelený stav: commit `062bdd9`, 2026-08-19).
5. **Teprve teď pracuj.** Pro každý typ práce viz sekce níže: pravidla → metodika ověření → hotové nástroje → postup pro novou sestavu → zápis do DB.
6. **Před commitem geometrie:** kroky 4–6 z Metodiky níže (přesná produkční kopie, regresní sada, u sestav i bookkeeping validátor).
7. **Po dokončení:** zapiš nové poznatky (sekce "Po dokončení" dole) — další bot po tobě musí najít stejně kompletní stav, jaký jsi našel ty.

## Nadřazená pravidla (shrnutí — ÚPLNÝ a AKTUÁLNÍ seznam je ⭐ blok na začátku `VLASTNOSTI_PROFILU.md`, k 2026-08-19 jich je SEDM)

1. **Žádné zanoření, žádné částečně kryté čelo.** Pro každý spoj dvou profilů: mezera=0, průnik=0, CELÁ plocha menšího/rovného čela leží uvnitř plochy druhého dílu. Platí i pro typy spojů, které appka ještě nemá napsané — je to kritérium návrhu, ne jen popis hotového kódu.
2. **Noha (svislý profil) se zpravidla neuzavírá jiným profilem ani zespoda, ani shora** (Robert 2026-08-18: "nejvyšší police nemá důvod být jiná než ty spodní... necháváme nohám čela nahoře volné jako vespod"). Volné čelo se v reálné konstrukci osazuje samostatným PŘÍSLUŠENSTVÍM (patka/kolečko/záslepka), ne profilem. Je to Logiman/vanDrawee konvence, ne fyzická nemožnost — `buildKvadrShape()` dnes dělá cap zespoda a NEVYŽADUJE opravu, jen nový kód by měl defaultně volit tuhle konvenci.
3. **T-styl (průchozí) spoj: připojovaný díl se zkracuje o CELOU šířku průchozího dílu, ne o půlku.** Jinak i při "boční" filozofii spoje vznikne reálné zanoření — připojovaný díl svou délkou zasahuje do místa, kde průchozí díl fyzicky existuje po celé své výšce (ne jen v jednom bodě jako u cap-spoje).
4. **Pivot dílu (`position`) NENÍ vždy jeho geometrický střed** — cílovou hranu vždy ZMĚŘ (`Box3`), nikdy neodvozuj z `position ± size/2`; ověřuj na SKUTEČNÉ `.glb` geometrii, ne syntetickém `BoxGeometry` (přesně takhle byl nalezen kvádr-bug 0.75mm).
5. **Montážní plocha PLOCHÉHO příslušenství se nesmí odvozovat z "nejdelší osy"** (spolehlivé jen pro podlouhlé profily) — použij `accessoryThinFaceIdx()` (nejtenší rozměr).
6. **Dvě topologie rohu = dvě RŮZNÁ kritéria platnosti** — viz Metodika níže; jejich záměna vyrábí falešné poplachy resp. přehlédnuté chyby.
7. (+ vše ostatní v ⭐ bloku `VLASTNOSTI_PROFILU.md` — ten je zdroj pravdy, tenhle seznam je jen shrnutí.)

## Metodika ověření — KRITICKÉ (každý bod tu je, protože jeho porušení už jednou stálo skutečnou chybu)

1. **"Mezera/překryv = 0 na dotykové ose" NESTAČÍ.** Zkontroluj překryv na VŠECH 3 osách zvlášť. Platný plochý spoj = přesně JEDNA osa s `gap≈0`/`overlap≈0` A ZBÝVAJÍCÍ dvě osy s PLNÝM (kladným) překryvem. Jednoosá kontrola může vypadat jako 100% úspěch a přitom skrývat dotyk jen hranou.
2. **Před posuzováním rohu klasifikuj jeho TOPOLOGII** (viz `PRAVIDLA_SPOJU.md`, "dvě topologie rohu"): smyčka **čelo-na-čelo** (uzavírací roh, oba díly tam končí) → konektorové body MUSÍ splynout, box test může lhát; spoj **čelo-na-bok** (větrník, T, regálová patra) → box test JE pravda a konektorová vzdálenost `w×√2/2` je inherentní, ne vada. Záměna kritérií vedla 2026-08-19 k falešnému poplachu, jehož "oprava" by vyrobila skutečné 15mm zaboření.
3. **Ověřuj na REÁLNÉ `.glb` geometrii** (`scripts/2026-08-19_glb_real_geometry.js`), ne syntetickém boxu — syntetický box je vždy symetrický a celou třídu chyb (pivot-offset) ze své podstaty nikdy nevyvolá.
4. **Před commitem geometrické změny otestuj PŘESNOU KOPII výsledného produkčního kódu** (ne vlastní paralelní implementaci opravy) na více reálných profilech — rozdíl mezi "moje verze opravy funguje" a "produkční kód s opravou funguje" je přesně tam, kde se 2026-08-19 projevil omyl.
5. **`webapp/` se servíruje PŘÍMO z disku** — i NEZACOMMITOVANÁ úprava je okamžitě živá pro zákazníky. Když závěrečné ověření selže, okamžitě `git checkout -- <soubor>` a ověř živý soubor přes `curl`.
6. **Před commitem čehokoli geometrického spusť regresní sadu:** `node scripts/2026-08-19_regression_scene/run_all.js` (musí skončit "VSECH 10 SKRIPTU OK"). Po uložení nové sestavy do `custom_shapes` navíc spusť `scripts/2026-08-19_bookkeeping_validator.js` (datové účetnictví je JINÁ kontrola než geometrie, obě povinné).
7. **Hranový raycasting (`objectCollidesWithWalls`/`meshWorldEdgeSample`) má slepé místo: MENŠÍ díl CELÝ VNOŘENÝ do většího, aniž by jeho hrana protnula povrch obstacle, se NEDETEKUJE** (nalezeno 2026-08-30 při srovnávání nohy 30x30 vedle 40x40 ve stejné karoserii - test hlásil "nekoliduje", i když `Box3` přesah na všech 3 osách ukázal skutečnou kolizi). Metoda testuje jen "protíná hrana kandidáta povrch překážky", ne "je kandidát uvnitř objemu překážky" - u dvou podobně tvarovaných sestav podobné velikosti (ne jedné tenké součástky vs jedné stěny) přidej DOPLŇKOVOU kontrolu přímým `Box3` přesahem na všech 3 osách mezi CELÝMI sestavami (ne jen jednotlivými díly), než závěr "nekoliduje" považuj za spolehlivý.
8. **Naopak: `Box3` přesah SÁM O SOBĚ taky není vždy důkaz kolize** u dílů se skutečnou vnořovací/stohovací geometrií (schodek, prstenec, drážka, noha s odstupňovanou patkou) - nalezeno 2026-08-30 (eurobox s 12mm nožkou zapadající do lůžka na nosnících/spojnicích): finální, Robertem potvrzená pozice vykazuje 12mm `Box3` přesah na ose Y mezi eurobxem a nosníkem, protože eurobox má na spodní straně vybrání, do kterého nosník reálně zapadá - skutečná mesh geometrie tam nekoliduje, i když bounding box ano. `Box3` neumí rozlišit "vnořený do prázdné dutiny" od "vnořený do plného materiálu" - u dílů s podezřením na stohovací/nesting geometrii (zkontroluj unikátní Z/Y hodnoty vrcholů v GLB - schodovitý profil = varovný signál) ověřuj finální pozici VIZUÁLNĚ ve scéně (Robertovo potvrzení), ne jen numerickým `Box3` testem.
9. **A jde to i OPAČNÝM směrem než #8: i skutečný mesh test (ne jen `Box3`) může ohlásit kolizi, která je záměr, ne vada** - kdyžtak proto, že GLB profilu je modelovaný jako PLNÝ, i když reálná hliníková trubka je dutá. Nalezeno 2026-09-11 (bot16, nezávislé ověření zanoření sestavy 337 přes `scripts/2026-09-11_mesh_kolize_lib.js` - SAT + volumetrické vzorkování, přesně nástroj proti pasti #8): pár **`<profil-role> + zaslepka-<profil-role>`** (např. `predni-svislice + zaslepka-predni-svislice`, `cap + zaslepka-cap`, `zadni-svislice-* + zaslepka-zadni-svislice-*`) ohlašuje reálnou objemovou kolizi s **bit přesně identickým `odsun=5.25mm`, rozměr překryvu `7.5×5.44×7.5mm`, NAPŘÍČ VŠEMI sestavami a pozicemi** (ověřeno na sestavách 336 a 337 - úplně stejné číslo). Bitová shoda přes různé sestavy/pozice je signál "je to konstanta vztahu dvou konkrétních GLB, ne nehoda umístění" - záslepka je čep, který se zasouvá do dutiny profilu na pevnou hloubku; mesh test o tom neví, protože sampluje objem podle povrchu GLB, a pokud GLB profilu nemá modelovanou skutečnou dutinu (nebo `zaslepka` GLB zahrnuje i část, která má být "uvnitř"), objemový vzorek vyjde uvnitř obojího, i když fyzicky nic nekoliduje. **NEOPRAVUJ to jako nález** - je to zapsaný, vysvětlený jev (Robert/bot3 2026-09-11), ne otevřená vada. Kdyby to někdy bylo potřeba doopravdy rozřešit: ne dalším kolizním testem, ale pohledem do katalogu (`cfg_dily`/GLB), jestli profil v definici má dutinu a jakou hloubku má mít čep - to je samostatná práce.

## Hotové nástroje (nepiš znovu od nuly)

`webapp/js/scene-geometry-shared.js` — **JEDINÝ zdroj pravdy** pro geometrické funkce (`baseQuaternion`, `dominantWallCoord`, `computeConnectorsLocal`, `crossAxisHalfWidthTowardDirection`, `worldConnectorsOf`, `isProfilePart`, `firstFreeConnectorIndex`, `linkJointPeers`, `attachEntryToParent`, `registerJoint`, `applyLengthScale`) I pro kolizní test proti karoserii (`meshWorldEdgeSample`, `ensureWallBoundsTree`, `setMeshesCollisionColor`, `objectCollidesWithWalls` — přidáno bot16 2026-08-30). Načítá ho jak `webapp/scene.html` (přes `<script src>`, funkce běží jako globály), tak Node.js (přes `require()`) — bot8 2026-08-19, žádné dvě kopie k ruční synchronizaci. **Pravidlo (Robert: "co umí 3D scéna skrze admina, musí umět Node.js skrze bota úplně stejně"):** novou funkci, kterou by mohl potřebovat i Node.js skript, piš ROVNOU sem, ne inline do `scene.html` — `.git/hooks/pre-commit` (`SCENE_SHARED_DUPLICATE`) blokuje commit, pokud `scene.html` znovu definuje jméno, které je odtud už exportované (chrání KAŽDOU budoucí přidanou funkci automaticky, bez ruční údržby seznamu), ale nerozhoduje samo, jestli nová funkce sem patří.

`scripts/2026-08-18_scene_geometry_lib.js` — Node.js knihovna, `require()`uje výše uvedený sdílený soubor + pomocné funkce (`buildRectFrameEntries` pro uzavřený obdélníkový rám, `touchReport`/`isValidFlushTouch`/`fullCollisionCheck` pro ověření podle metodiky výše, `serializeToCustomShapeParts` pro zápis do `custom_shapes.data`).

**Přestavba existujícího tvaru na jiný profil** (stejný design, jiná tloušťka, zachované vnější rozměry) — postup zapsaný v `shape_geometry_methods.name='prevod-profilu-zachovanim-rozmeru'` (aktuálně `version=3`, viz `PROFILY_KATALOG.md`, sekce "PŘESTAVBA TVARU NA JINÝ PROFIL"): změř skutečné boxy původních segmentů, rozděl rozměry na tloušťce-nezávislé (fyzické/designové) a tloušťce-závislé (odvozené vzorcem), přepočti, ověř `touchReport` na všech spojích. Dvě časté gotchas: (1) segment dotýkající se vnější hrany (podlaha/strop) má střed přesně `T/2` od té hrany, ne `T`; (2) **DŮLEŽITĚJŠÍ** — `touchReport()` sám o sobě NESTAČÍ jako důkaz správnosti: kontroluje jen spoje MEZI segmenty tvaru, ne jeho absolutní pozici vůči vnějšímu okolí (stěna karoserie). Jakýkoli vnitřní prvek (např. "cap" díl) reprezentující fyzickou/funkční vůli VŮČI VNĚJŠÍ HRANĚ musí být kotven vzdáleností OD TÉ HRANY PŘÍMO, nikdy od jiného vnitřního, už samo T-závislého prvku (odhaleno 2026-08-30 srovnávacím testem dvou profilů na identickém Z, kdy jinak vycházel 2-3mm rozdíl, protože různé profily kolidovaly se stěnou různými fyzickými částmi).

`scripts/2026-08-18_shelf_builder.js` — příklad použití knihovny: parametrizovaná stavba police/regálu (4 průběžné nohy s volnými konci, N pater, všechna T-styl). Spustit přímo (`node 2026-08-18_shelf_builder.js`) jako demo, nebo `require()`ovat `buildShelf`/`verifyShelf` z vlastního skriptu.

`scripts/2026-08-19_regression_scene/` — **regresní sada celé matematiky scény** (10 skriptů + `run_all.js`): rect/kvádr, oba prostorové L, oba L-změna-délek, T-spoj, větrník, refity rámů, záslepka, wall deska, úhelník s naučenou pozou — vše na REÁLNÉ `.glb` geometrii. Spusť `node scripts/2026-08-19_regression_scene/run_all.js` po KAŽDÉ změně `scene-geometry-shared.js` nebo build*/refit*/run*Aut funkcí, PŘED commitem. Skripty jsou kopie produkční logiky odpovídající stavu po opravách 2026-08-19 — při záměrné změně produkce aktualizuj i příslušný skript.

`scripts/2026-08-20_section_cut.js` — **přesné 2D technické řezy** (průnik trojúhelníků reálných GLB s rovinou → JSON segmenty; kreslí se matplotlib skriptem s mm mřížkou a kótami). **ZÁVAZNÉ pravidlo (Robert 2026-08-20): podklady pro schvalování umístění dílů = technické řezy, ne 3D náhledy/wireframe.** Varianty předkládat jako úplnou očíslovanou tabulku (orientace × hloubka). POZOR: tenhle rig si díl orientuje SÁM — používej ho JEN pro tabulky variant před výběrem.

`scripts/2026-08-20_live_section_cut.js` — **řez ZE ŽIVÉHO STAVU scény** (vstup = JSON s `matrixWorld` profilu i dílu + osa profilu + normála stěny, exportovaný z headless scény po `runWallAut`/apod.). **Potvrzující řez po zápisu do DB MUSÍ vznikat tímhle nástrojem, nikdy samostatným rigem** — u kolečka 3404 vlastní rig vyrobil schválený obrázek neodpovídající scéně (osa v rovině stěny vs. osa kolmo ke stěně) a Robert pak právem hlásil "nefunguje to kolečko ve scéně".

**ZÁVAZNÉ pravidlo (Robert 2026-08-20): KANONICKÝCH 5 KROKŮ učení dílu na profil** ("postup co jsme provedli s učením koleček principiálně"): (1) technické výkresy variant pozic = očíslovaná tabulka řezů ze živého stavu s kolizním verdiktem přes VŠECHNY vrcholy (point-in-polygon proti průřezu, ne jen středový řez); (2) Robertovo schválení čísla; (3) propis do scény na **Place All A Magnet** (attach_pose/attach_offset_mm, source 'robert'; číst musí runWallAut/runZaslepkaAut I findBestAccessorySnap+tažení) + headless doměření + potvrzující řez; (4) Robertovo potvrzení, že to FUNGUJE, přímo ve scéně; (5) finální zápis do DB (verified_ok, verified_by='robert', attach_learning_log + snapshot do backups/). Vzor: kolečka 3404/3386, commity 060e3ab + b3c84a6 + 68238a7.

**ZÁVAZNÉ pravidlo (Robert 2026-08-20): učení dílů je PŘÍSNĚ SEKVENČNÍ.** NIKDY nezačínat další díl, dokud předchozí není FUNKČNÍ = (1) volba v DB (`attach_pose`/`attach_offset_mm`, source `robert`, řádek v `attach_learning_log`), (2) změřená headless ověřením, (3) Robertem potvrzená nad technickým řezem ze živého stavu, A NAVÍC (4) **Robertem VÝSLOVNĚ potvrzená PŘÍMO VE SCÉNĚ** ("dokud nepotvrdím ve scéně poslední zadávaný díl, že je funkční, nejde se dál"). Schválení řezu je podklad volby, NE finální potvrzení - to dává vždy až kontrola ve scéně. Žádné paralelně rozdělané díly; teprve po potvrzení ve scéně se generuje tabulka pro další díl. (Porušeno 2026-08-20: kloub 3415 rozjet po schválení řezů koleček, ale před Robertovou kontrolou koleček ve scéně.)

`scripts/2026-08-19_bookkeeping_validator.js` — validátor ÚČETNICTVÍ spojů uložených `custom_shapes` sestav (Robert: "z pohledu matematiky počet spojů může být chybný, i když oko vidí OK"). Ověřuje 4 invarianty: lic_peers symetrie, každý geometricky změřený flush dotyk registrován v datech, sum(joint_count) == počet skutečných dotyků, used_conn indexy platné. Vstup = JSON dump z DB (shapes + part_id→glb mapa, viz hlavička souboru). Po uložení každé nové testovací sestavy do `custom_shapes` ho spusť — geometrická správnost (touchReport) a datová správnost (tenhle validátor) jsou DVĚ různé kontroly, obě povinné.

**Postup pro novou testovací sestavu:**
```bash
npm install   # jen poprvé, spustit v ROOTU repa (ne ve scripts/) - three@0.128.0, node_modules je gitignored, resolvuje se pro webapp/js/ i scripts/
cd scripts && node -e "
const lib = require('./2026-08-18_scene_geometry_lib.js');
// ... postav vlastní entries pomocí lib.attachEntryToParent / lib.buildRectFrameEntries / ...
// ověř: lib.touchReport(a, b), lib.fullCollisionCheck(placed, definedPairs)
// uloz: lib.serializeToCustomShapeParts(placed) -> JSON.stringify({parts, join_groups:[], frame_groups:[]})
"
```

Pro zápis výsledku do `custom_shapes` (žádná admin browser session potřeba, viz `TVARY_VLASTNI.md` 2an krok 5): PyMySQL je dostupný v `api/venv` (`api/venv/bin/python3`), přístupové údaje v `api/.env` (`DB_HOST/PORT/USER/PASSWORD/NAME`, POZOR na řádek `DB_PASSWORD=` ne `DB_PASS=`). `custom_shapes` a `remeslo_appky_screenshots`/`*.md` NEJSOU hlídané `DEPLOY_LOCK.json` soubory (jen `webapp/*`/`api/app.py`) — přímý zápis do DB zámek nevyžaduje.

**Skutečná geometrie profilu, ne odhad:** `scripts/2026-08-19_glb_real_geometry.js` (`parseGlbMesh`/`glbBoundingBox`/`mkRealProfileEntry`) rozparsuje `.glb` přímo (žádný GLTFLoader potřeba) do skutečné `THREE.BufferGeometry` s reálnými vertexy - používej MÍSTO `mkProfileEntry()` (ten staví jen syntetický, dokonale symetrický `BoxGeometry`), kdykoli ověřuješ novou matematiku, ne jen recykluješ už ověřenou. `parseGlbMesh` od 2026-09-18 slučuje VŠECHNY meshe souboru a od 2026-10-02 i všechna primitiva meshe (dřív četl jen `meshes[0]` - viz incident #4 níže; transformace UZLŮ neaplikuje - `glbRizikaParseru(path)` je vypíše, katalog dnes žádné nemá; test `scripts/2026-10-02_glb_parser_test.js`), používej ho tedy přímo i na vícemeshové katalogové soubory, žádný obchvat navíc netřeba. Kriticky důležité: **pivot dílu (`position`) NENÍ vždy jeho geometrický střed** - `profil_30x30_uzavreny.glb` má reálně naměřený posun ~0.75mm (ostatní testované profily zanedbatelný) - kód, který odvozuje cílovou hranu z `position ± size/2` (místo aby ji ZMĚŘIL přes `Box3`), na tomhle může tiše selhat i když vypadá správně a projde testy se syntetickým boxem. Přesně takhle byl 2026-08-19 nalezen a opraven skutečný bug v `buildKvadrShape()` (viz `PRAVIDLA_SPOJU.md`, sekce "pivot dílu NENÍ vždy geometrický střed") - žádné dosavadní ověřování (ani vizuální v prohlížeči, ani Node.js se syntetickým boxem) ho nemohlo odhalit. Pro PŘÍSLUŠENSTVÍ (ne hranaté profily) navíc box-aproximace nestačí ani pro connectory — `computeConnectorsLocal(obj, {wallSnap:true})` použije skutečnou mesh geometrii přes `dominantWallCoord`.

## ⭐ „0 nálezů" musí znamenat „změřeno a čisto", ne „nezměřeno"

Přidáno 2026-09-11, protože **tatáž kontrola ohlásila „0 kolizí" TŘIKRÁT po
sobě** z důvodu, který s čistotou nesouvisel:

1. **2026-09-05** — GLB se hledalo podle `part_id`, soubor neexistoval,
   `parseGlbMesh` vrátil `null`, kolize se tiše neměřily. Do logu se zapsalo
   *„2235 úhelníků, 0 kolizí, flush 0.0000mm"*.
2. **2026-09-11** — filtr **záměrně přeskakoval profily vlastní nohy**
   (`continue`), protože na ně úhelník legitimně dosedá. Tím oslepl
   k rozdílu mezi dosedem (0 mm) a průnikem (7–22 mm). Ověřeno, že by
   přeskočil **44 ze 44** skutečných kolizí. *(Ten řádek byl navíc od
   začátku zbytečný — test průniku flush dosed nepropustí ani bez něj.)*
3. **2026-09-11, o pár hodin později** — mapa `part_id → glb` byla natvrdo
   s **jediným** záznamem, takže tři produkty (mimo jiné **MDF deska**)
   z kontroly tiše vypadly. Po opravě stoupl počet porovnaných párů
   z 4 796 na **4 936**. Pravidlo *„part_id NENÍ název GLB, mapuj přes
   `shop_products.glb_file`"* přitom bylo po prvním výskytu zapsané —
   jen ho ten skript neuposlechl.
4. **2026-09-18** — `parseGlbMesh()` (sdílený nástroj, širokým použitím
   napříč `scripts/`) četl jen `json.meshes[0]` - tichý předpoklad
   "1 GLB = 1 mesh". Neplatí: změřeno napříč CELÝM katalogem,
   **85 z 495 `.glb` souborů (17 %)** má víc než 1 mesh (až 9), včetně
   `product_3219` (pant/závěs). Každé dosavadní měření přes tenhle
   nástroj na některém z těch 85 souborů tiše pracovalo jen s ČÁSTÍ
   skutečné geometrie - box i connectory mohly vyjít menší/posunuté,
   aniž by to cokoli ohlásilo. Nalezeno při Robertem vyžádané technické
   analýze `custom_shapes#558` (viz `AGENTS_LOG.md` 2026-09-18). Opraveno
   přímo ve sdíleném nástroji (slučuje pozice+indexy všech meshů -
   ověřeno, že všechny uzly v katalogu mají identity transform, takže
   prosté sloučení je pro celý katalog správné) - **jednorázová oprava
   v jednom místě, ne workaround v každém skriptu zvlášť.**

**Co z toho plyne pro každou geometrickou kontrolu, kterou píšeš:**

* **Vypiš ROZSAH MĚŘENÍ, ne jen výsledek.** „0 nalezeno" je nerozeznatelné
  od „nic jsem neporovnal". Vypisuj počet porovnaných párů, dílů, sestav.
  Nula nálezů z nuly porovnaných je chyba, nula z 4 936 je výsledek.
* **Nezměřitelný díl musí být hlasitá chyba, ne přeskočení.** Chybí GLB,
  chybí mapa, nejde spočítat obálka → **nenulový exit**. Tiché `continue`
  nebo `or {}` vyrobí z chybějících dat zdánlivě platný výsledek.
* **Mapu `part_id → glb` generuj z DB, nikdy ji nepiš natvrdo.** Liší se
  u `product_3045`, `product_3539`, `product_3671`, `product_3939` —
  a příště u dalších.
* **Každé vědomé vyloučení napiš do kódu i do výstupu.** Karoserie
  (`car_body_*`) se vylučují záměrně (pravidlo 25, nemají katalogový GLB) —
  to je v pořádku. Vyloučení, které není vidět, je k nerozeznání od chyby.
* **Pozor na `or {}` u chybějící struktury.** Nerozliší „pole se
  nedopočítalo" od „pole je prázdné" a zápis pak vyrobí objekt, který
  vypadá platně. 2026-09-11 takhle vzniklo 136 sestav s cenou složenou jen
  ze spojů, bez materiálu — zachyceno až kontrolou PO zápisu.

**Zapsané pravidlo nestačí.** Všechny tři výskyty se staly i přesto, že po
tom prvním pravidlo existovalo. Když jde něco udělat mechanicky nemožné
(sdílená funkce místo kopie, exit místo přeskočení), udělej to tak —
spoléhat na to, že si to příště někdo přečte, prokazatelně nefunguje.

## Po dokončení

Nový poznatek/pravidlo zapiš do PŘÍSLUŠNÉHO tematického souboru (`PRAVIDLA_SPOJU.md`/`PROFILY_KATALOG.md`/`PRISLUSENSTVI_PRIPOJENI.md`/`TVARY_PREDNASTAVENE.md`/`TVARY_VLASTNI.md`/`NASTROJE_SCENY.md`/`KAROSERIE_UMISTENI.md`/`KOMPONENTY_EUROBOXY.md` — viz rozcestník `VLASTNOSTI_PROFILU.md` pro výběr, novou `## Pravidlo profilů - ...` sekci na konec daného souboru) a do `AGENTS_LOG.md` (zamčené přes `scripts/lock.sh acquire bot8 "AGENTS_LOG.md append" --wait`, i když samotný zápis do těchhle `.md` souborů/`scripts/*.js` zámek nepotřebuje — nejsou to hlídané soubory).
