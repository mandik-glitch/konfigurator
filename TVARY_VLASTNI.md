# Vlastní tvary (custom_shapes)

Panel "Vlastní tvary" — uložení sestavy jako přednastaveného tvaru, ruční vytvoření z výkresu/obrázku (GLB parsing), přenos vazby připojeného příslušenství, obecná funkce `buildShelf()`. Vydělené z `VLASTNOSTI_PROFILU.md` 2026-08-31.

## 2j. Panel "Vlastní tvary" — uložení vlastní sestavy jako přednastaveného tvaru (2026-07-24)

Robert: "na scéně si nakreslím nějaký objekt, označím ho, přes CTRL+S se tento tvar uloží jako nový přednastavený tvar; systém si vyžádá jeho název a založí jej jako nové tlačítko; klik na tlačítko vloží uložený objekt do scény." Upřesněno: "před použitím Ctrl+S musím objekt označit" — ukládá se AKTUÁLNÍ VÝBĚR (Mikroposuv nebo Posun myší), ne celá scéna.

**Datový model:** nová DB tabulka `custom_shapes` (`id`, `name`, `data` — JSON pole dílů, `created_by`, `created_at`). Každý díl výběru se ukládá jako `part_id` + jeho aktuální 3D transform (`position`, `quaternion`, `scale` — `scale` nese i případné protažení z tažení koncovky) + volitelně `color` (ruční obarvení) a `used_conn` (indexy již obsazených konektorů, aby po znovu-vložení fungovalo správně napojování). Limit `CUSTOM_SHAPE_MAX_PARTS = 60` dílů na jeden uložený tvar.

**API:** `GET/POST /api/custom-shapes`, `DELETE /api/custom-shapes/<id>` (vše `@login_required`). `POST` validuje každý `part_id` proti aktuálnímu katalogu (`fetch_katalog_parts()`) — neplatný odkaz na díl se odmítne, ne tiše zahodí.

**Rekonstrukce ve scéně:** při načtení uloženého tvaru se pro každý díl nejdřív čerstvě spočítá `connectorsLocal` z geometrie GLB (dokud je objekt v identitě), a teprve POTOM se aplikuje uložený `position`/`quaternion`/`scale` — stejný princip, jaký appka používá i za běhu (`placeAtOrigin`, `applyLengthScale`). Nové tlačítko vloží tvar vedle stávajícího obsahu scény (stejný `keepExisting` + `applyAutoPlacementOffset` vzorec jako u vestavěných tvarů z Průvodce) — NENAHRAZUJE existující sestavu.

Implementace: `api/app.py` (tabulka, konstanta, validace, 3 endpointy), `webapp/scene.html` (Ctrl+S handler, sekce "Vlastní tvary" v panelu Tvary, `loadCustomShapePartEntry`/`insertCustomShape`).

> **Rozšíření (2026-07-25, Robert: "musí se přenést veškeré vlastnosti a spojitosti, tzn i počet spojů se ukládá"):** původní verze ukládala jen geometrii/barvu/obsazené konektory - po znovu-vložení tvaru se ztrácel `jointCount` (už zaplacené spoje zmizely z ceny) i příslušnost ke skupině Join (J) / Čtverci-rámu (`frameGroup`). Doplněno stejným principem, jaký používá Kopírování (`duplicateEntries`): `serializeEntryForSave()` ukládá i `joint_count`/`hidden_end_conn`/`was_through`/`was_attached`/`vertical`; nová `serializeSelectionRelations()` ukládá propojení MEZI díly (Lícování/Najdi-spoje `licPeers`, Join skupiny, `frameGroup`) jako indexy do pole `parts` - jen když je DRUHÁ strana spoje (resp. CELÁ skupina/rám) taky součástí ukládaného výběru. Formát sloupce `data` v DB změněn z prostého pole na `{parts, join_groups, frame_groups}`, čtení zůstává zpětně kompatibilní se starými záznamy (prosté pole = bez skupin/spojů). Ověřeno `customshape_harness.js` (23 assertions) + `customshape_py_harness.py` (27 assertions).

## 2ab. Vlastní tvary přenáší vazbu připojeného příslušenství (2026-08-02)

Robert: uložený vlastní tvar (Ctrl+S) s napojeným příslušenstvím musí po smazání originálu a vložení tvaru zpět mít všechny vazby originálu. Ukládání už déle přenášelo usedConn/jointCount/licPeers/Join skupiny/rámy, ale chyběl `attachedTo` (novější vazba "připojeno k profilu") - vložený díl pak vypadal připojeně, ale nefungovalo R/prstenec, U, zámek osy, zastavení na čele ani Ctrl+C-kopie-vedle.

Nově: `parts[i].attached_to = {prof, parent_conn, child_conn, spin}` (indexový odkaz jako u lic_peers, ukládá se jen když je profil také součástí výběru), obnovení v `insertCustomShape` na novou JS referenci. Server (`api/app.py`): `attached_to` přidán do validačního whitelistu (jinak by ho server zahodil) + kontrola rozsahu indexu. Ověřeno testem test_shape_attached.js (11 assertions) + izolovaným testem serverové validace.

## 2an. Postup: ruční vytvoření vlastního tvaru (`custom_shapes`) z výkresu/obrázku, bez sestavování ve scéně (2026-08-05)

Robert potvrdil tvar "Noha 1 Trafic H1 1250x349 výřez" (`custom_shapes.id=19`, POZOR - řádek smazán při pozdějším úklidu testovacích dat, audit bot9 2026-09-12 ověřil `SELECT id FROM custom_shapes WHERE id=19` → 0 řádků; postup níže tím neztrácí platnost, jen už nejde znovu dohledat konkrétní záznam) vytvořený přímým zápisem z okótovaného výkresu — bez ručního skládání ve scéně. Zapsáno jako obecný postup pro příště (předávka od bot1, dopočet dělal bot5).

**Kdy tohle použít:** Robert pošle okótovaný výkres/skicu vlastního tvaru a chce ho rovnou v katalogu "Vlastní tvary", bez nutnosti ho nejdřív ručně poskládat ve scéně a uložit přes UI.

**Postup:**

1. **Najdi part_id profilu** v `cfg_dily` podle průřezu (`glb_file IS NOT NULL`, `visible_in_scene=1`) — nejdelší rozměr = délka (L0), zbylé dva = průřez.

2. **Zjisti počátek GLB PŘÍMO Z GEOMETRIE, nehádej a nespoléhej na kalibraci z jiného uloženého tvaru** — starší postup (odvodit "frac" z `position`/`scale` nějakého dřívějšího Robertova tvaru se stejným profilem) je křehký a nefunguje, když `custom_shapes` zrovna nemá žádný vhodný záznam (stalo se — tabulka byla prázdná). Místo toho rozparsuj `.glb` soubor přímo (glTF je čitelný JSON chunk, žádná 3D knihovna netřeba):
   ```python
   import struct, json
   data = open("webapp/katalog/<glb_file>", "rb").read()
   _, _, length = struct.unpack("<4sII", data[0:12])
   offset = 12
   while offset < length:
       clen, ctype = struct.unpack("<II", data[offset:offset+8])
       if ctype == 0x4E4F534A:  # "JSON"
           gltf = json.loads(data[offset+8:offset+8+clen])
       offset += 8 + clen
   acc = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
   print(acc["min"], acc["max"])  # min/max na delkove ose -> stred (frac=0.5) vs konec (frac=0)
   ```
   Podle `min`/`max` na délkové ose (typicky Y) hned poznáš: symetrické kolem 0 (`[-L0/2, L0/2]`) = počátek uprostřed, `[0, L0]` = počátek na konci. U Object_11 (40×40) vyšlo `[-500, 500]` = **uprostřed** — u ostatních profilů to může být jinak, vždy ověřit, ne předpokládat.

3. **Dopočítej `position`/`scale` každého dílu** z reálných souřadnic výkresu (mm): `scale[délková osa] = požadovaná_délka / L0`, `position = střed reálného rozpětí dílu na všech 3 osách` (funguje přímo takhle jen když je počátek uprostřed — viz krok 2; u počátku na konci by šlo o `min + frac·délka`). Svislý díl: `quaternion [0,0,0,1]`. Vodorovný díl (délková osa Y otočená do X): `quaternion [0,0,-0.7071,0.7071]` (-90° kolem Z).

4. **Vazby (spoje) mezi díly** ukládej jen přes pole, která appka skutečně čte — **ověř si to přímo v `_validate_custom_shape_parts()` (`api/app.py`), ne z paměti/staršího zadání.** Aktuálně (2026-08-05) validátor uznává: `part_id, position, quaternion, scale, color, used_conn, joint_count, hidden_end_conn, was_through, was_attached, vertical, lic_peers, attached_to`. Cokoli jiného (např. starší formát `last_joint`) se PŘI ZÁPISU PŘES `POST /api/custom-shapes` tiše zahodí — `joint_count`+`lic_peers` (index peer dílu v poli `parts`) stačí na vyjádření "tenhle díl je už spojený s dílem na indexu N".

5. **Zápis:** zkus nejdřív `POST /api/custom-shapes` (přihlášený admin → `is_public=1` automaticky, navíc serverová validace zdarma). Když není k dispozici admin session (a nechceš/nemůžeš získat heslo — správně), přímý `INSERT INTO custom_shapes (name, data, created_by, is_public) VALUES (..., '{"parts":[...],"join_groups":[],"frame_groups":[]}', NULL, 1)` se STEJNOU strukturou JSON, jakou by vyprodukoval validátor — appka pak čte/zobrazí tvar úplně stejně, jen bez serverové kontroly (proto dvojnásob důležité mít pole z kroku 4 správně).

6. **Ověření bez GUI:** zpětně přečti řádek z DB, ověř počet dílů a že `data` je platný JSON se strukturou `{"parts":[...], "join_groups":[], "frame_groups":[]}`. Vizuální kontrolu (rozestavení, R-cyklení, počet spojů) musí nakonec udělat Robert ve scéně — žádný headless render tu k dispozici není.

**J. Testovací sestavy (`custom_shapes`) — stav k 2026-08-18, VŠECHNY ŘÁDKY SMAZÁNY (audit bot9, 2026-09-12: `SELECT id FROM custom_shapes WHERE id IN (158,160,168..176)` → 0 řádků, úklid testovacích dat).** Tabulka níže je historický záznam validace, ne odkaz na dohledatelná data - závěry (T-styl, `buildShelf()` generalizace) zůstávají platné, jen konkrétní řádky už neexistují:

| id | Popis | Stav |
|---|---|---|
| 158 | Úhelník mezi rovnoběžnými profily (product_3318) | validováno (Robert "je to ok") |
| 160 | Přehled typů spojů (referenční sestava) | validováno |
| 168 | Plochá spirála, 20 profilů různých délek (Object_11) | validováno (bot8) |
| 169 | Točité schodiště, 20 profilů, 3 osy X/Y/Z | validováno po 2 kolech oprav (bot8) |
| 170 | Konstrukce stolu bez desky, 1500×900×1000mm | validováno (bot8) |
| 171–173 | 3 druhy křížů (plochý stohovaný / trojosý / T-křížový plus) | validováno (Robert "sedí") |
| 174 | Regál 30×30, 400×500mm, 3 police (VŠECHNA patra T-styl, noha volná nahoře i dole) | validováno (bot8) — viz `AGENTS_LOG.md` 2026-08-18 pro plnou historii chyb/oprav |
| 175 | Regál 30×30, 400×500mm, 6 polic (víc komponent, stejný builder) | validováno (bot8) |
| 176 | Regál 40×40, 600×400mm půdorys, výška 1100mm, 3 police (jiný profil/rozměr) | validováno (bot8) |

**Obecná funkce `buildShelf()`** (zobecnění regálu id=174, PO opravě "i nejvyšší patro je T-styl" - viz pravidlo níže) - parametrizovaný "police builder": profil, průřez, půdorys (Lx×Ly), seznam výšek VŠECH pater (žádné "cap", noha vždy přečnívá nad posledním patrem). **Committnuto v repu** (ne jen scratchpad): `scripts/2026-08-18_scene_geometry_lib.js` (knihovna) + `scripts/2026-08-18_shelf_builder.js` (builder) + `.claude/skills/3d-scena-spoje/SKILL.md` (návod, automaticky nabízený v budoucích sessions). Kdyby měla appka dostat tlačítko "Regál"/"Police" jako nový přednastavený tvar, tohle je hotový, ověřený základ pro `webapp/scene.html`, ne nutnost začínat od nuly.

## 2xx. Import objektu (FBX) → rozpojená skladba dílů → Vlastní tvar (2026-09-29, bot8)

Robert: *„nechci jednorázový script, postav univerzální funkci, která importuje
libovolný objekt"* — 1) rozpojené díly, které se od sebe nevzdálí (totéž co
`SSE.vzor.01 - ROZPOJENO`, custom_shapes #561), 2) ruční mapování dílů na
existující profily/příslušenství v katalogu, 3) nenamapované díly = nové
karty s novým SKU, 4) funguje živý pravý panel (cena, spoje) i online nabídka.
**Pro bota, který na importu pracuje:** mechanismy, neporušitelné invarianty, otevřená chyba a ověřování
jsou ve skillu `import-fbx-scena` (`.claude/skills/`); testy `scripts/2026-09-30_universal_import_harness.js`
(18 testů) + `…_harness_mutace.py` (10 umyslných chyb, které harness musí chytit).
**Samoobslužné, bez bota** — panel **„Import objektu (FBX)"** ve scéně (vedle
Vlastních tvarů), backend `api/universal_import.py`.

**Postup:** nahrát FBX (z Rhina: mm, jeden objekt = jeden díl, názvy objektů se
přenesou) → „Rozebrat na díly" → díly se ukážou ve scéně přesně na svých
místech (dočasné katalogové řádky `tmpimport_*`, nikdy se neukládají) → v
tabulce u každého dílu: *existující díl* (hledání v katalogu, profily i
produkty; rozpoznané profily podle průřezu jsou předvyplněné, tlačítko „použít
rozpoznané profily"), *nový díl* (název + SKU `<kód>.DIL-NNN`, přepsatelné,
„zbytek jako nové díly"), nebo *přeskočit* → název tvaru, kód, kategorie →
„Sestavit tvar". Klik na řádek zvýrazní díl ve scéně, výběr dílu ve scéně
(Posun myší) odskroluje na řádek.

**Co se zapíše:** nové díly = `shop_products` (`visible_in_scene=1`,
`active=0`, cena a kategorie NULL — doplní Robert v adminu → Sklad) + GLB
`webapp/katalog/product_<id>.glb` **vycentrované na střed bboxu** (karta je
tím použitelná i jako běžný katalogový díl, na rozdíl od SSE dílů) s
`position=<střed>`; existující profil = pozice střed bboxu, rotace podle
nejdelší osy, `scale=[1, délka/L0, 1]` (stejná logika jako Rozklad FBX na
profily); existující příslušenství = střed bboxu + osově zarovnaný odhad
rotace (doladit ve scéně); `lic_peers` jen profil–profil (dotyk bboxů, jako
`dimension_match_fbx`); 1× `custom_shapes` (`is_public=1`). Jedna transakce —
při chybě nic nezůstane. Drobné CAD operace exportované jako samostatné meshe
(SolidWorks: `Zaoblit`, `Odebrat vysunutím`, díry…) se sloučí do nejbližšího
dílu (mezera bboxů ≤ 15 mm), u Rhina se to netýká ničeho.

**Pasti:** nahraný FBX i náhledy jdou do privátního `api/tmp_universal_import/
<token>/` (ne do veřejně servírovaného `content-files`), po sestavení se
smažou, staré tokeny (>24 h) při dalším importu. Transformace uzlů FBX se
záměrně NEaplikují (Unity export by vyšel 10× menší; SolidWorks má identity) a
assimp `PreTransformVertices` se nesmí použít (slévá meshe podle materiálu) —
viz hlavička `api/fbx_mesh_extract_worker.py`. Nativní `.SLDPRT/.SLDASM`
otevřít nejde, vstup musí být FBX.

**Spojit označené (J)** (Robert 2026-09-30, *„některý díl se nahraje jako
rozpojený, i když jej chci mít spojený"*): v kroku mapování označ díly
(zaškrtnutím v tabulce nebo výběrem ve scéně přes Posun myší) a stiskni **J**
(nebo tlačítko „spojit označené") — slijí se do jednoho dílu s jednou
geometrií a jedním mapováním; náhled ve scéně se překreslí. U spojeného
dílu je „rozpojit" (vrátí původní díly). Backend `POST /api/admin/
universal-import/<token>/join` a `/split`, původní díly se drží v
`joined_from` v `meta.json` tokenu.

**Smazat / zrušit** (Robert 2026-09-30, *„nějaké delete tlačítko se hodí"*):
**✕** u dílu (nebo označit + **Delete** / „smazat označené") díl z importu úplně
odstraní — nebude ve tvaru ani v katalogu (na rozdíl od „přeskočit", které ho
nechá v tabulce). **„zrušit import"** zahodí rozpracovaný import (nic se
nezaložilo). Backend `POST .../<token>/remove`, `DELETE .../<token>`.

**Průběžné ukládání a rozpoznání katalogu** (Robert 2026-09-30, *„u většího
tvaru to sestavování celkem trvá, chce to ukládat v průběhu, a dej tam
funkci rozpoznat stávající tvary"*): rozpracované mapování (název, kód,
kategorie, rozhodnutí u dílů) se **ukládá automaticky** ~1 s po každé změně
(`POST .../<token>/draft`, stav „uloženo HH:MM" u tlačítka Sestavit) a po
obnovení stránky se nabídne v **„Rozpracované importy"** (pokračovat /
zahodit; `GET .../drafts`, `GET .../<token>`); import s uloženým
rozpracováním se drží 14 dní, holý token 24 h. **Rozpoznání** proti celému
katalogu (profily i produkty, index z hlaviček GLB ~0,25 s): *profil* podle
průřezu (má přednost — cena/natahování jde jen přes katalogový profil),
*stejný díl* (rozměry ±0,6 mm + stejný počet vrcholů/trojúhelníků = tentýž
export, např. kolo založené minulým importem), *podobný rozměr* (jen
rozměry ±2 mm — jen nápověda, u řádku „použít"). „použít rozpoznané" bere
stejný díl + profil; „rozpoznat znovu" po spojení dílů nebo když mezitím
přibyly karty (`POST .../<token>/recognize`).

**Šum (ploché útržky)** (Robert 2026-09-30, *„jsou tam spousty malých dílů,
to je co?"*): Rhino exportuje nespojené plochy tělesa jako samostatné meshe
— ploché útržky bez objemu (`58×2×0`) a drobky (< 10 mm). Při rozboru se
přilepí k nejbližšímu skutečnému dílu do 15 mm (jako CAD operace, počítají se
do „+N op."), co zbyde osamocené, má štítek **„šum"** a jde smazat najednou
tlačítkem **„smazat šum (N)"** (nebo přilepit k dílu přes J). Prahy
`FRAGMENT_FLAT_MM=0,5` / `FRAGMENT_TINY_MM=10` v `api/universal_import.py`;
legitimní tenké díly (záslepka 3 mm, hardware 9,8 mm) se neflagují (ověřeno).

**Detekce profilů z Rhina** (Robert 2026-09-30, *„mechanismus musí
detekovat profily"*): profil z Rhina přichází jako sada plochých stěn bez
jediného tělesa, takže průřez nebylo z čeho poznat. Rozbor teď osamocené
útržky **slepí podle sdílených vrcholů** (stěny jednoho tělesa sdílejí
hranové vrcholy na 0,01 mm; dvě různá tělesa, i když se dotýkají, mají jinou
tesselaci — bbox-blízkost by slila celý rám) → vznikne díl 30×30×L a
rozpozná se jako profil. Navíc profil **podle názvu** („30x30",
„profil 45x45x1200") když bbox nesedí (přilepené příslušenství, zkosený
konec). Díl spojený přes J se rozpozná hned. Ověřeno synteticky (2 profily
30×30 dotýkající se čelem, 4 stěny každý → 2 díly, oba `Object_7`).

**Rozpoznání podle tvaru průřezu** (Robert 2026-09-30, *„tytéž průřezy a
tvary mají profily, se kterými pracujeme, pocházejí z téhož geometrického
tvaru"*): nejvyšší priorita — vrcholy dílu promítnuté kolmo k délce se
porovnají s průřezem katalogového GLB profilu (pokrytí bodů do 0,6 mm, obě
strany ≥ 85 %, přes 8 symetrií čtverce; nezávisle na délce, natočení a
tesselaci). Odliší i varianty se stejným obrysem (30×30 vs. 30×30 uzavřený:
pokrytí 0,64 → neshoda). Ověřeno: SolidWorks noha 45×45 → `Object_2` (1,00),
Unity 40×40 → `Object_11` (1,00). Bere jen skutečné profily (vzorek 1000 mm,
název „Profil…"), ne pomocné díly cfg_dily. Pak teprve průřez podle bboxu,
název, stejný díl, podobný rozměr.

**Seskupení stejných dílů + automatické přiřazení** (Robert 2026-09-30, *„předešlé
tlačítko krásně identifikovalo naše profily a tady je milion dílů"*): rozbor
rozpoznal stejných 18 profilů jako starý „Rozklad FBX na profily", ten ale zbylé
meshe tiše zahodil. Tabulka je teď ve třech sekcích: **Rozpoznané profily**
(přiřazené automaticky hned po rozboru, sbalené), **Ostatní díly**, **Šum**.
Díly se **stejnými rozměry bboxu (do 1 mm)** tvoří jeden řádek „×N" s jedním
mapováním (4 kolečka = 1 řádek); počet vrcholů se neporovnává (Rhino síťuje
instance různě). „Nový díl" u skupiny = **jedna karta** použitá N× (backend:
stejné SKU v jednom importu → 1 produkt, další kusy s vlastní pozicí a
natočením dopočítaným z geometrie mezi 24 osovými rotacemi; když geometrie
nesedí žádnou rotací — zrcadlová dvojice — založí se vlastní karta `SKU-2` a
přijde warning). Zaškrtnutí řádku = celá skupina (J / Delete).

**Drobné díly + červené zvýraznění** (Robert 2026-09-30, *„u SSE importu jsem
neřešil mikrodíly… když na řádek kliknu, musí se ten díl pořádně zvýraznit"*):
nerozpoznané díly s max. rozměrem do hranice (pole „drobné do … mm", výchozí
60) se **hned po rozboru přilepí k nejbližšímu většímu dílu** (do 15 mm) —
`POST .../<token>/merge-small`; nikdy ne k dílům mapovaným na EXISTUJÍCÍ
katalogový díl (profily, stejné díly, ruční přiřazení — ty ve tvaru nahradí
katalogové GLB, přilepená geometrie by zmizela a posunutý bbox by profil špatně
umístil). Co nemá souseda, zůstane v sekci **Drobné díly** (typicky spojky/
záslepky u konců profilů — ty patří na katalogové příslušenství). Tlačítko
„přilepit drobné k sousedům" to spustí kdykoli znovu (i na starší import). Klik
na řádek obarví celou skupinu **červeně** (klon materiálu per mesh, zpět při
výběru jiné skupiny).

**Import nikdy nemaže scénu** (Robert 2026-09-30, *„když importuju nový FBX,
nesmí se nic ve scéně smazat"*): `universal-import.js` nevolá `clearAll()`.
Náhled (`tmpimport_*`) i hotový tvar se vkládají přes `insertCustomShape(…,
{inPlace:true})` + `applyAutoPlacementOffset` **vedle** stávajícího obsahu
(+X, mezera 300 mm; do prázdné scény beze změny). Odebírá se vždy jen sám
náhled (`removeTmpEntries` — spoje, výběr i pravý panel se přepočtou). První
náhled jen posune pohled kamery na nový obsah (bez změny úhlu).
Díly náhledu jsou pro scénu „neexistující" (`isImportPreviewEntry()` ve
`scene.html`): nejsou v ceně, kusovníku, uložení/„Uložit opravu", kroku zpět
ani kontrolním kusovníku; **online nabídka se při otevřeném náhledu odmítne**
hláškou (dokonči „Sestavit tvar" nebo zruš import). Otevřená sestava/tvar
(`currentAssemblyMeta`) a klíč pro F5 zůstávají; jeden **Krok zpět** vrátí
celý import. **J/Delete** patří importu, jen když je označený díl importu a
zároveň nejsou označené skutečné díly scény (nebo je fokus v panelu importu) —
skutečné díly scény nikdy nesmaže ani nespojí. „Vymazat vše" / Krok zpět
náhled smaže jako cokoli jiného a sám se nevrací — vykreslí ho znovu až další
úprava dílů v tabulce (spojit/rozpojit/smazat/přilepit drobné) nebo po
obnovení stránky „pokračovat" v Rozpracovaných importech.
