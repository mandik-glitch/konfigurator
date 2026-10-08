# Vlastnosti profilů — rozcestník

Tenhle soubor byl do 2026-08-31 jeden rostoucí dokument (přes 1380 řádků) o 3D geometrii/profilech/spojích v projektu Konfigurator. Na Robertovu žádost ("čekáme sotva na začátku projektu, je to formát vhodný pro další růst?") byl rozdělený TEMATICKY do 8 samostatných souborů níže — každý bot session si načte jen ten soubor, který potřebuje pro svůj úkol, ne celý balík najednou.

**Aktivní SKILL:** `.claude/skills/3d-scena-spoje/SKILL.md` — shrnuje klíčová pravidla + odkazuje na hotové ověřovací nástroje, automaticky nabízený v seznamu dostupných skillů každé budoucí session.

## ⭐ Nadřazená pravidla (číst PRVNÍ, platí univerzálně pro každý spoj/tvar/profil)

- Žádné zanoření, žádné částečně kryté čelo — mezera=0, průnik=0, CELÁ plocha čela na dotyku, u KAŽDÉHO spoje, i budoucího nenapsaného
- Noha se zespoda zpravidla neuzavírá jiným profilem — Logiman/vanDrawee konvence, ne fyzický zákaz (konkurence to používá)
- T-styl (průchozí) spoj — připojovaný díl se zkracuje o CELOU šířku průchozího, ne o půlku
- I nejvyšší patro/police je stejný T-styl spoj jako ostatní — noha má volné čelo nahoře STEJNĚ jako dole, žádné patro ji "necapuje"
- Pivot dílu (position) NENÍ vždy geometrický střed — vždy MĚŘIT skutečnou hranu (`Box3`), nikdy neodvozovat z `position ± size/2`; ověřovat na SKUTEČNÉ `.glb` geometrii, ne na syntetickém `BoxGeometry`
- Montážní plocha PLOCHÉHO příslušenství (záslepka, deska) se nesmí odvozovat z "nejdelší osy" — použij `accessoryThinFaceIdx()` (nejtenší rozměr)
- Dvě topologie rohu = dvě RŮZNÁ kritéria platnosti: smyčka čelo-na-čelo → konektorové body musí splynout (box test může lhát); spoj čelo-na-bok (větrník/T) → box test JE pravda
- Runtime výběr montážní plochy příslušenství: MĚŘIT každého kandidáta, ne odhadovat z obálky
- Schvalování umístění dílů: bot PŘEDKLÁDÁ TECHNICKÉ ŘEZY ze ŽIVÉHO STAVU SCÉNY (Robert, závazné)
- Učení dílů je PŘÍSNĚ SEKVENČNÍ — nikdy nezačínat další díl, dokud předchozí není FUNKČNÍ a Robert to VÝSLOVNĚ nepotvrdil PŘÍMO VE SCÉNĚ
- U STEJNĚ VELKÉ přípojné plochy použij hraniční střed obálky, ne plošně vážené těžiště
- `Matrix4.makeBasis(a,b,c)` zásadně nevolit se všemi 3 osami nezávisle zvolenými — třetí osu vždy dopočítej křížovým součinem. DOPLNĚNO (audit bot9, 2026-09-12): jediná schválená výjimka je `corner3SolveForTriple()` (třícestný roh/"kostka", `webapp/scene.html`) — tam se 3 osy měří nezávisle ZÁMĚRNĚ (jsou to 3 skutečně naměřené konektory), ale funkce si hned za tím kontroluje determinant výsledné matice (`|det-1| > 0.15` → zahodit jako zrcadlení/degenerované) - nejde tedy o porušení pravidla, je to jeho explicitní runtime pojistka pro případ, kdy křížový součin nejde použít.
- 3D model v karoserii je povinný VŽDY jako kontrola učení — ale NENAHRAZUJE 2D dimenzní kontrolu, kdykoli je ve hře víc mm-kritických proměnných (obě kontroly povinné, ne jedna náhradou druhé)
- `Box3` přesah SÁM O SOBĚ není vždy důkaz kolize — u dílů se stohovací/nesting geometrií (schodek, drážka) může jít o záměrné vnoření do dutiny, ne do plného materiálu
- V matematických simulacích, při ukládání pozic a při práci s objekty vždy identifikovat díly podle SKU, nikdy podle názvu (názvy jsou nejednoznačné a nestabilní)
- **Role dílů jsou SDÍLENÝ jmenný prostor.** Nový prefix ověř proti všem generátorům, které role zapisují, a proti všem skriptům, které podle nich mažou nebo filtrují — `startswith` filtr cizího generátoru tvůj díl tiše pohltí. Konkrétní případ (bot8, 2026-09-11): razítková výplň drážky se jmenovala `vypln-drazky-N`, jenže prefix `vypln-` už patřil generátoru horních bloků (`vypln-zada`, `vypln-dno`, `vypln-police`, `vypln-celo`, `vypln-bok-prepazka`). Mazací skript starých horních bloků maže podle `role.startswith("vypln-")`, takže by **výplně smazal a loga nechal viset nad otevřenými drážkami** — přesně ta vada, kvůli které výplň existuje. Opraveno sjednocením na jeden prefix (`logo-ochrana-logo-N` / `logo-ochrana-vypln-N`).

Detail a zdůvodnění každého bodu je v příslušném souboru níže.

## Kde co najdeš

- **`PRAVIDLA_SPOJU.md`** — univerzální geometrie spoje (přesný spoj profil↔profil, T-styl, definice fyzického spoje/šroubu, polarita), metodika ověření (touchReport, Box3 na všech 3 osách), kanonický proces učení dílů (5 kroků), gotchas (pivot není střed, makeBasis zrcadlení, edge-raycasting slepé místo, Box3 přesah u nesting geometrie).
- **`PROFILY_KATALOG.md`** — řezání/max délka, tabulka drážek a kompatibility profilů, přestavba tvaru na jiný profil se zachováním rozměrů (`prevod-profilu-zachovanim-rozmeru`), placeholder sekce (orientace, nosnost, povrch, otvory/hardware).
- **`PRISLUSENSTVI_PRIPOJENI.md`** — klasifikace montážního režimu příslušenství (endcap/corner_side/wall/corner3/none), runtime výběr montážní plochy, historie systematického ověřování katalogových dílů.
- **`TVARY_PREDNASTAVENE.md`** — Tvar L, Čtverec/rám, Prostorový L, Kvádr (`buildKvadrShape`), oprava uzavíracího rohu, kotvení na společný vnější roh, natažení uzavřeného tvaru.
- **`TVARY_VLASTNI.md`** — custom_shapes (panel "Vlastní tvary"), ruční vytvoření z výkresu, obecná funkce `buildShelf()`, stav testovacích sestav.
- **`NASTROJE_SCENY.md`** — magnet/snap, lícování, cyklení ploch/konců, UI menu/barvy/export, sdílený zdroj geometrie (`scene-geometry-shared.js`) mezi scénou a Node.js.
- **`KAROSERIE_UMISTENI.md`** — výběr karoserie podle kóty dveří, kolizní krokování, pravidlo o nezávislosti pozic noh na prohnutí stěny (a jeho rozšíření na tuze spojené sestavy), otočení karoserie CI14 o 180°.
- **`KOMPONENTY_EUROBOXY.md`** — noha Jumpy 30x30/40x40, změna hloubky nohy, matice ukládání euroboxů do lůžek, kompletní postup vložení produktu eurobox. **Obsahuje i "Dvířka horního bloku" (krok 1-7, cca řádek 1128)** — sklopná dvířka na pantech místo plastové výplně, velikostní stupně typ1/2/3, doraz — přestože název souboru o dvířkách nic neříká.

**DB jako zdroj pravdy pro čísla:** `car_body_placement_methods` a `shape_geometry_methods` tabulky drží verzované, strukturované recepty (JSON) — markdown soubory výše hlavně vysvětlují PROČ a odkazují na `id`/`version`, nekopírují je duplicitně.
